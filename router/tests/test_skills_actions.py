from __future__ import annotations

import asyncio

from app.actions.executor import ActionExecutor
from app.agents.registry import get_agent
from app.agents.runtime import run_agent
from app.models.action_models import ActionExecutionContext, ActionProposal
from app.models.agent_models import AgentRunRequest, ToolResult
from app.models.skill_models import SkillExecutionContext
from app.skills.executor import executor as skill_executor
from app.skills.registry import get_skill


def test_system_snapshot_skill_returns_normalized_output(monkeypatch):
    skill = get_skill("system_snapshot")
    assert skill is not None

    async def fake_execute(self, tool_name, arguments, *, allowed_tools, context):
        return ToolResult(
            tool_name=tool_name,
            success=True,
            output={"uptime_seconds": 123, "memory": {"used_percent": 12.5}},
        )

    monkeypatch.setattr("app.skills.standard.ToolExecutor.execute", fake_execute)

    result = skill.execute(skill.validate_arguments({}))

    assert result.success is True
    assert result.output["status"] == "ok"
    assert result.output["system"]["uptime_seconds"] == 123


def test_service_log_correlation_skill_combines_service_and_logs(monkeypatch):
    skill = get_skill("service_log_correlation")
    assert skill is not None

    async def fake_execute(self, tool_name, arguments, *, allowed_tools, context):
        if tool_name == "service_status":
            return ToolResult(
                tool_name=tool_name,
                success=True,
                output={
                    "service_name": arguments["service_name"],
                    "active_state": "inactive",
                    "sub_state": "dead",
                    "main_pid": None,
                },
            )
        return ToolResult(
            tool_name=tool_name,
            success=True,
            output={
                "source": "router.log",
                "requested_limit": 5,
                "returned_count": 2,
                "entries": [
                    {"level": "error", "source": "app.router", "message": "ollama timeout"},
                    {"level": "warn", "source": "app.router", "message": "retry"},
                ],
            },
        )

    monkeypatch.setattr("app.skills.standard.ToolExecutor.execute", fake_execute)

    result = skill.execute(skill.validate_arguments({"service_name": "ollama", "log_limit": 5}))

    assert result.success is True
    assert result.output["severity"] == "high"
    assert result.output["service"]["active_state"] == "inactive"
    assert len(result.output["logs"]["related_hits"]) == 1


def test_incident_summary_skill_prioritizes_findings():
    skill = get_skill("incident_summary")
    assert skill is not None

    result = skill.execute(
        skill.validate_arguments(
            {
                "title": "Cluster Lage",
                "findings": [
                    {"severity": "medium", "summary": "Router reagiert verzögert"},
                    {"severity": "high", "likely_cause": "Dienst startet nicht"},
                ],
            }
        )
    )

    assert result.success is True
    assert result.output["severity"] == "high"
    assert result.output["top_findings"] == [
        "Router reagiert verzögert",
        "Dienst startet nicht",
    ]


def test_agent_health_check_skill_reports_platform_state():
    skill = get_skill("agent_health_check")
    assert skill is not None

    result = skill.execute(skill.validate_arguments({}))

    assert result.success is True
    assert result.output["registry_ok"] is True
    assert "/agents" in result.output["details"]["routes"]
    assert "/skills" in result.output["details"]["routes"]
    assert "/actions" in result.output["details"]["routes"]


def test_kids_controller_repetition_skill_flags_frequent_arrangement():
    skill = get_skill("kids_controller_repetition_review")
    assert skill is not None

    result = skill.execute(
        skill.validate_arguments(
            {
                "observation": {
                    "pos1": 1,
                    "pos2": 2,
                    "pos3": 3,
                    "trend": {
                        "arrangement_signature": "123",
                        "comparable_draw_count": 5,
                        "same_arrangement_count": 4,
                        "same_arrangement_ratio": 0.8,
                        "repeated_arrangement": True,
                    },
                    "observed_at": "2026-05-18T20:55:12Z",
                }
            }
        )
    )

    assert result.success is True
    assert result.output["status"] == "recommend_review"
    assert "sehr oft" in result.output["message"]
    assert result.output["source"] == "kids_controller_repetition_review"


def test_skill_executor_blocks_unauthorized_skill():
    context = SkillExecutionContext(
        agent_name="guardian_supervisor",
        skill_name="router_log_review",
        step_number=1,
        request_id="req-1",
        allowed_skills=["system_snapshot"],
    )

    result = asyncio.run(
        skill_executor.execute(
            "router_log_review",
            {"limit": 2},
            allowed_skills=["system_snapshot"],
            context=context,
        )
    )

    assert result.success is False
    assert "Skill nicht für Agent freigegeben" in (result.error or "")


def test_action_executor_blocks_unapproved_execution():
    action_executor = ActionExecutor(timeout_seconds=1)
    proposal = ActionProposal(
        action_name="restart_service",
        arguments={"service_name": "pi-guardian-router"},
        reason="Dienst neu starten",
        target="pi-guardian-router",
        requires_approval=True,
    )
    policy = get_agent("service_operator").settings.policy

    result = action_executor.execute(
        proposal,
        policy=policy,
        approved=False,
        context=ActionExecutionContext(
            agent_name="service_operator",
            action_name="restart_service",
            request_id="req-2",
            approved=False,
            target="pi-guardian-router",
        ),
    )

    assert result.success is False
    assert "nicht freigegeben" in (result.error or "")


def test_action_executor_blocks_policy_denied_target():
    action_executor = ActionExecutor(timeout_seconds=1)
    proposal = ActionProposal(
        action_name="restart_service",
        arguments={"service_name": "ssh"},
        reason="Verboten",
        target="ssh",
        requires_approval=True,
    )
    policy = get_agent("service_operator").settings.policy

    result = action_executor.execute(
        proposal,
        policy=policy,
        approved=True,
        context=ActionExecutionContext(
            agent_name="service_operator",
            action_name="restart_service",
            request_id="req-3",
            approved=True,
            target="ssh",
        ),
    )

    assert result.success is False
    assert "nicht erlaubt" in (result.error or "")


def test_service_operator_runtime_proposes_action(monkeypatch):
    responses = iter(
        [
            {
                "response": '{"skill_name":"service_triage","arguments":{"service_name":"pi-guardian-router"},"reason":"Dienst bewerten"}'
            },
            {
                "response": '{"action_name":"restart_service","arguments":{"service_name":"pi-guardian-router"},"reason":"Dienst hängt","target":"pi-guardian-router","requires_approval":true}'
            },
        ]
    )

    async def fake_generate_with_ollama(model, prompt, request_id, stream=False, **kwargs):
        return next(responses)

    async def fake_execute(self, tool_name, arguments, *, allowed_tools, context):
        return ToolResult(
            tool_name=tool_name,
            success=True,
            output={
                "service_name": arguments["service_name"],
                "active_state": "inactive",
                "sub_state": "dead",
                "main_pid": None,
            },
        )

    monkeypatch.setattr("app.agents.runtime.generate_with_ollama", fake_generate_with_ollama)
    monkeypatch.setattr("app.skills.standard.ToolExecutor.execute", fake_execute)
    monkeypatch.setattr("app.agents.runtime.record_action_proposal", lambda **kwargs: None)
    monkeypatch.setattr("app.agents.runtime.record_agent_run", lambda request, response: None)
    monkeypatch.setattr("app.memory.agent_memory.extract_from_run", lambda run_id: None)

    result = asyncio.run(
        run_agent(
            AgentRunRequest.model_validate(
                {
                    "agent_name": "service_operator",
                    "input": "Service prüfen und falls nötig Handlung vorschlagen",
                    "max_steps": 3,
                }
            )
        )
    )

    assert result.success is True
    assert result.agent_name == "service_operator"
    assert result.proposed_action is not None
    assert result.proposed_action["action_name"] == "restart_service"
    assert result.steps[-1].action == "action_proposal"
