from __future__ import annotations

import json
import logging
import uuid

from fastapi import HTTPException

from app.agents.prompt_builder import build_prompt
from app.agents.registry import get_agent
from app.agents.tool_parser import parse_action_proposal, parse_skill_call, parse_tool_call
from app.memory.service import record_action_proposal, record_agent_run
from app.models.action_models import ActionProposal
from app.models.agent_models import (
    AgentRunRequest,
    AgentRunResponse,
    AgentRunState,
    AgentStep,
    ToolCall,
    ToolResult,
)
from app.models.skill_models import SkillExecutionContext, SkillResult
from app.models.tool_models import ToolExecutionContext
from app.router.classifier import select_model_for_prompt
from app.router.errors import RouterApiError
from app.router.inference.wrapper import TIMEOUT_AGENT
from app.router.ollama_client import generate_with_ollama
from app.skills.executor import executor as skill_executor
from app.tools.executor import ToolExecutor

logger = logging.getLogger(__name__)


class AgentRuntime:
    def __init__(self, tool_executor: ToolExecutor | None = None) -> None:
        self.tool_executor = tool_executor or ToolExecutor()

    def _resolve_model(self, request: AgentRunRequest) -> str:
        if request.preferred_model:
            return request.preferred_model
        if request.agent_name:
            agent = get_agent(request.agent_name)
            if agent and agent.settings.preferred_model:
                return agent.settings.preferred_model
        return select_model_for_prompt(request.prompt)

    @staticmethod
    def _tool_result_to_observation(result: ToolResult) -> str:
        if result.success:
            return json.dumps(result.output, ensure_ascii=False, default=str)
        return result.error or "Tool fehlgeschlagen."

    @staticmethod
    def _skill_result_to_observation(result: SkillResult) -> str:
        if result.success:
            return json.dumps(result.output, ensure_ascii=False, default=str)
        return result.error or "Skill fehlgeschlagen."

    @staticmethod
    def _requires_skill_before_final_answer(
        agent_name: str,
        state: AgentRunState,
    ) -> tuple[bool, str | None]:
        if agent_name != "kids_controller_supervisor":
            return False, None
        if state.skill_call_count > 0:
            return False, None
        return True, "Agent muss zuerst den Skill kids_controller_repetition_review aufrufen."

    async def run(self, request: AgentRunRequest) -> AgentRunResponse:
        run_id = str(uuid.uuid4())
        agent = get_agent(request.agent_name)
        if agent is None:
            return AgentRunResponse(
                run_id=run_id,
                agent_name=request.agent_name,
                success=False,
                final_answer="",
                errors=[f"Unbekannter Agent: {request.agent_name}"],
                used_model=None,
            )

        if not agent.settings.active:
            return AgentRunResponse(
                run_id=run_id,
                agent_name=agent.name,
                success=False,
                final_answer="",
                errors=[f"Agent ist deaktiviert: {agent.name}"],
                used_model=agent.settings.preferred_model or self._resolve_model(request),
            )

        policy = agent.settings.policy
        effective_max_steps = request.max_steps or agent.settings.max_steps
        effective_max_steps = min(effective_max_steps, agent.settings.max_steps, policy.max_steps)
        model = self._resolve_model(request)
        state = AgentRunState(
            agent_name=agent.name,
            current_step=0,
            max_steps=effective_max_steps,
            tool_call_count=0,
            skill_call_count=0,
            context_history=[],
            completed=False,
        )
        steps: list[AgentStep] = []
        tool_calls: list[ToolCall] = []
        errors: list[str] = []
        final_answer = ""
        proposed_action: dict[str, object] | None = None

        logger.info(
            "agent_run_start agent=%s run_id=%s model=%s max_steps=%s",
            agent.name,
            run_id,
            model,
            effective_max_steps,
        )

        for step_number in range(1, effective_max_steps + 1):
            state.current_step = step_number
            prompt = build_prompt(agent, request.prompt, state)

            try:
                model_result = await generate_with_ollama(
                    model=model,
                    prompt=prompt,
                    request_id=run_id,
                    stream=False,
                    timeout=TIMEOUT_AGENT,
                    session_id=run_id,
                )
            except RouterApiError as exc:
                error = f"Ollama-Fehler: {exc.code} - {exc.message}"
                logger.warning(
                    "agent_run_model_error agent=%s run_id=%s step=%s error=%s",
                    agent.name,
                    run_id,
                    step_number,
                    error,
                )
                errors.append(error)
                steps.append(
                    AgentStep(
                        step_number=step_number,
                        action="abort",
                        tool_call_or_response={},
                        observation=error,
                    )
                )
                state.context_history.append(steps[-1])
                break
            except HTTPException as exc:
                error = f"HTTP-Fehler bei Modellaufruf: {exc.detail}"
                logger.warning(
                    "agent_run_http_error agent=%s run_id=%s step=%s error=%s",
                    agent.name,
                    run_id,
                    step_number,
                    error,
                )
                errors.append(error)
                steps.append(
                    AgentStep(
                        step_number=step_number,
                        action="abort",
                        tool_call_or_response={},
                        observation=error,
                    )
                )
                state.context_history.append(steps[-1])
                break
            except Exception as exc:
                error = f"Unerwarteter Fehler beim Modellaufruf: {exc}"
                logger.exception(
                    "agent_run_unexpected_model_error agent=%s run_id=%s step=%s",
                    agent.name,
                    run_id,
                    step_number,
                )
                errors.append(error)
                steps.append(
                    AgentStep(
                        step_number=step_number,
                        action="abort",
                        tool_call_or_response={},
                        observation=error,
                    )
                )
                state.context_history.append(steps[-1])
                break

            response_text = (model_result.get("response") or "").strip()
            if not response_text:
                error = "Leere Modellantwort erhalten."
                logger.warning(
                    "agent_run_empty_response agent=%s run_id=%s step=%s",
                    agent.name,
                    run_id,
                    step_number,
                )
                errors.append(error)
                steps.append(
                    AgentStep(
                        step_number=step_number,
                        action="parse_error",
                        tool_call_or_response="",
                        observation=error,
                    )
                )
                state.context_history.append(steps[-1])
                continue

            steps.append(
                AgentStep(
                    step_number=step_number,
                    action="model_response",
                    tool_call_or_response=response_text,
                    observation=None,
                )
            )
            state.context_history.append(steps[-1])

            tool_parse = parse_tool_call(response_text, allowed_tools=agent.allowed_tools)
            if tool_parse.error:
                errors.append(tool_parse.error)
                logger.warning(
                    "agent_run_parse_error agent=%s run_id=%s step=%s error=%s",
                    agent.name,
                    run_id,
                    step_number,
                    tool_parse.error,
                )
                steps.append(
                    AgentStep(
                        step_number=step_number,
                        action="parse_error",
                        tool_call_or_response=tool_parse.raw_payload or response_text,
                        observation=tool_parse.error,
                    )
                )
                state.context_history.append(steps[-1])
                continue
            if tool_parse.tool_call is not None:
                tool_call = tool_parse.tool_call
                tool_calls.append(tool_call)
                state.tool_call_count = len(tool_calls)
                steps.append(
                    AgentStep(
                        step_number=step_number,
                        action="tool_call",
                        tool_call_or_response=tool_call,
                        observation=tool_call.reason,
                    )
                )
                state.context_history.append(steps[-1])

                context = ToolExecutionContext(
                    agent_name=agent.name,
                    tool_name=tool_call.tool_name,
                    step_number=step_number,
                    request_id=run_id,
                    allowed_tools=agent.allowed_tools,
                    tool_call_number=state.tool_call_count,
                    policy=policy,
                )
                tool_result = await self.tool_executor.execute(
                    tool_call.tool_name,
                    tool_call.arguments,
                    allowed_tools=agent.allowed_tools,
                    context=context,
                )
                observation = self._tool_result_to_observation(tool_result)
                steps.append(
                    AgentStep(
                        step_number=step_number,
                        action="tool_result",
                        tool_call_or_response=tool_result,
                        observation=observation,
                    )
                )
                state.context_history.append(steps[-1])
                if not tool_result.success:
                    errors.append(tool_result.error or f"Tool {tool_call.tool_name} fehlgeschlagen.")
                continue

            skill_parse = parse_skill_call(response_text, allowed_skills=policy.allowed_skills)
            if skill_parse.error:
                errors.append(skill_parse.error)
                logger.warning(
                    "agent_run_skill_parse_error agent=%s run_id=%s step=%s error=%s",
                    agent.name,
                    run_id,
                    step_number,
                    skill_parse.error,
                )
                steps.append(
                    AgentStep(
                        step_number=step_number,
                        action="parse_error",
                        tool_call_or_response=skill_parse.raw_payload or response_text,
                        observation=skill_parse.error,
                    )
                )
                state.context_history.append(steps[-1])
                continue
            if skill_parse.skill_call is not None:
                skill_call = skill_parse.skill_call
                state.skill_call_count += 1
                steps.append(
                    AgentStep(
                        step_number=step_number,
                        action="skill_call",
                        tool_call_or_response=skill_call,
                        observation=skill_call.reason,
                    )
                )
                state.context_history.append(steps[-1])

                context = SkillExecutionContext(
                    agent_name=agent.name,
                    skill_name=skill_call.skill_name,
                    step_number=step_number,
                    request_id=run_id,
                    allowed_skills=policy.allowed_skills,
                    policy=policy,
                )
                skill_result = await skill_executor.execute(
                    skill_call.skill_name,
                    skill_call.arguments,
                    allowed_skills=policy.allowed_skills,
                    context=context,
                )
                observation = self._skill_result_to_observation(skill_result)
                steps.append(
                    AgentStep(
                        step_number=step_number,
                        action="skill_result",
                        tool_call_or_response=skill_result,
                        observation=observation,
                    )
                )
                state.context_history.append(steps[-1])
                if not skill_result.success:
                    errors.append(skill_result.error or f"Skill {skill_call.skill_name} fehlgeschlagen.")
                continue

            action_parse = parse_action_proposal(
                response_text,
                allowed_actions=policy.allowed_actions,
            )
            if action_parse.error:
                errors.append(action_parse.error)
                logger.warning(
                    "agent_run_action_parse_error agent=%s run_id=%s step=%s error=%s",
                    agent.name,
                    run_id,
                    step_number,
                    action_parse.error,
                )
                steps.append(
                    AgentStep(
                        step_number=step_number,
                        action="parse_error",
                        tool_call_or_response=action_parse.raw_payload or response_text,
                        observation=action_parse.error,
                    )
                )
                state.context_history.append(steps[-1])
                continue
            if action_parse.action_proposal is not None:
                proposal: ActionProposal = action_parse.action_proposal
                if not policy.can_propose_actions:
                    error = f"Action-Vorschläge sind für diesen Agenten nicht erlaubt: {proposal.action_name}"
                    errors.append(error)
                    steps.append(
                        AgentStep(
                            step_number=step_number,
                            action="parse_error",
                            tool_call_or_response=proposal,
                            observation=error,
                        )
                    )
                    state.context_history.append(steps[-1])
                    continue
                if proposal.action_name not in policy.allowed_actions:
                    error = f"Action nicht für diesen Agenten erlaubt: {proposal.action_name}"
                    errors.append(error)
                    steps.append(
                        AgentStep(
                            step_number=step_number,
                            action="parse_error",
                            tool_call_or_response=proposal,
                            observation=error,
                        )
                    )
                    state.context_history.append(steps[-1])
                    continue

                proposal_id = str(uuid.uuid4())
                proposed_action = {
                    **proposal.model_dump(mode="json"),
                    "proposal_id": proposal_id,
                }
                steps.append(
                    AgentStep(
                        step_number=step_number,
                        action="action_proposal",
                        tool_call_or_response=proposal,
                        observation="Freigabe erforderlich.",
                    )
                )
                state.context_history.append(steps[-1])
                record_action_proposal(
                    proposal_id=proposal_id,
                    run_id=run_id,
                    agent_name=agent.name,
                    action_name=proposal.action_name,
                    arguments=proposal.arguments,
                    reason=proposal.reason,
                    target=proposal.target,
                    requires_approval=proposal.requires_approval,
                )
                final_answer = (
                    f"Action vorgeschlagen: {proposal.action_name}. "
                    "Freigabe erforderlich."
                )
                state.completed = True
                break

            requires_skill_first, enforcement_error = self._requires_skill_before_final_answer(
                agent.name,
                state,
            )
            if requires_skill_first and enforcement_error is not None:
                errors.append(enforcement_error)
                logger.warning(
                    "agent_run_final_answer_rejected agent=%s run_id=%s step=%s error=%s",
                    agent.name,
                    run_id,
                    step_number,
                    enforcement_error,
                )
                steps.append(
                    AgentStep(
                        step_number=step_number,
                        action="parse_error",
                        tool_call_or_response=response_text,
                        observation=enforcement_error,
                    )
                )
                state.context_history.append(steps[-1])
                continue

            final_answer = response_text
            state.completed = True
            steps.append(
                AgentStep(
                    step_number=step_number,
                    action="final_answer",
                    tool_call_or_response=response_text,
                    observation="Modell hat ohne weitere Struktur abgeschlossen.",
                )
            )
            state.context_history.append(steps[-1])
            break

        if not state.completed and not final_answer:
            final_answer = (
                "Abgebrochen, bevor ein Abschluss erreicht wurde. "
                f"Maximale Schrittzahl {effective_max_steps} erreicht."
            )
            if not errors:
                errors.append("max_steps erreicht")
            logger.info(
                "agent_run_aborted agent=%s run_id=%s steps=%s",
                agent.name,
                run_id,
                effective_max_steps,
            )

        logger.info(
            "agent_run_end agent=%s run_id=%s success=%s steps=%s tool_calls=%s skill_calls=%s errors=%s",
            agent.name,
            run_id,
            state.completed,
            len(steps),
            len(tool_calls),
            state.skill_call_count,
            len(errors),
        )
        response = AgentRunResponse(
            run_id=run_id,
            agent_name=agent.name,
            success=state.completed,
            final_answer=final_answer,
            steps=steps,
            tool_calls=tool_calls,
            proposed_action=proposed_action,
            errors=errors,
            used_model=model,
        )
        record_agent_run(request, response)
        try:
            from app.memory.agent_memory import extract_from_run
            extract_from_run(response.run_id)
        except Exception:
            pass
        return response


runtime = AgentRuntime()


async def run_agent(request: AgentRunRequest) -> AgentRunResponse:
    return await runtime.run(request)
