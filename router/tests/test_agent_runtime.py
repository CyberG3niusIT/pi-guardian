import asyncio

from app.agents.runtime import run_agent
from app.models.skill_models import SkillResult
from app.models.agent_models import AgentRunRequest, ToolResult


def test_agent_runtime_completes_after_tool_call(monkeypatch):
    responses = iter(
        [
            {
                "response": '{"tool_name":"system_status","arguments":{},"reason":"Systemzustand erfassen"}'
            },
            {"response": "Systemzustand ist unauffällig."},
        ]
    )

    async def fake_generate_with_ollama(model, prompt, request_id, stream=False, **kwargs):
        return next(responses)

    async def fake_execute(tool_name, arguments, *, allowed_tools, context):
        return ToolResult(
            tool_name=tool_name,
            success=True,
            output={"uptime_seconds": 123},
            error=None,
        )

    monkeypatch.setattr("app.agents.runtime.generate_with_ollama", fake_generate_with_ollama)
    monkeypatch.setattr("app.agents.runtime.runtime.tool_executor.execute", fake_execute)

    result = asyncio.run(
        run_agent(
            AgentRunRequest.model_validate(
                {
                    "agent_name": "guardian_supervisor",
                    "input": "Analysiere den Systemzustand",
                    "max_steps": 3,
                }
            )
        )
    )

    assert result.success is True
    assert result.final_answer == "Systemzustand ist unauffällig."
    assert result.used_model is not None
    assert len(result.tool_calls) == 1
    assert result.steps[-1].action == "final_answer"


def test_agent_runtime_aborts_after_max_steps(monkeypatch):
    async def fake_generate_with_ollama(model, prompt, request_id, stream=False, **kwargs):
        return {
            "response": '{"tool_name":"forbidden_tool","arguments":{},"reason":"Nicht erlaubt"}'
        }

    monkeypatch.setattr("app.agents.runtime.generate_with_ollama", fake_generate_with_ollama)

    result = asyncio.run(
        run_agent(
            AgentRunRequest.model_validate(
                {
                    "agent_name": "guardian_supervisor",
                    "input": "Analysiere alles",
                    "max_steps": 2,
                }
            )
        )
    )

    assert result.success is False
    assert result.used_model is not None
    assert any("nicht für diesen Agenten erlaubt" in error for error in result.errors)
    assert "Maximale Schrittzahl" in result.final_answer


def test_service_diagnose_runtime_uses_safe_tools(monkeypatch):
    responses = iter(
        [
            {
                "response": '{"tool_name":"service_status","arguments":{"service_name":"ollama"},"reason":"Ollama-Dienst prüfen"}'
            },
            {"response": "Ollama läuft, keine akute Störung erkennbar."},
        ]
    )

    async def fake_generate_with_ollama(model, prompt, request_id, stream=False, **kwargs):
        return next(responses)

    async def fake_execute(tool_name, arguments, *, allowed_tools, context):
        return ToolResult(
            tool_name=tool_name,
            success=True,
            output={
                "service_name": arguments.get("service_name", "ollama"),
                "active_state": "active",
                "sub_state": "running",
            },
            error=None,
        )

    monkeypatch.setattr("app.agents.runtime.generate_with_ollama", fake_generate_with_ollama)
    monkeypatch.setattr("app.agents.runtime.runtime.tool_executor.execute", fake_execute)

    result = asyncio.run(
        run_agent(
            AgentRunRequest.model_validate(
                {
                    "agent_name": "service_diagnose",
                    "input": "Prüfe den ollama Dienst",
                    "max_steps": 3,
                }
            )
        )
    )

    assert result.success is True
    assert result.agent_name == "service_diagnose"
    assert result.used_model is not None
    assert len(result.tool_calls) == 1
    assert result.tool_calls[0].tool_name == "service_status"
    assert result.steps[-1].action == "final_answer"


def test_log_analyst_runtime_uses_router_logs(monkeypatch):
    responses = iter(
        [
            {
                "response": '{"tool_name":"router_logs","arguments":{"limit":3,"level":"error"},"reason":"Fehlerlog prüfen"}'
            },
            {"response": "Es gibt wiederkehrende Fehler im Router-Log, vermutlich durch Konfigurations- oder Verfügbarkeitsprobleme."},
        ]
    )

    async def fake_generate_with_ollama(model, prompt, request_id, stream=False, **kwargs):
        return next(responses)

    async def fake_execute(tool_name, arguments, *, allowed_tools, context):
        return ToolResult(
            tool_name=tool_name,
            success=True,
            output={
                "source": "router.log",
                "requested_limit": arguments.get("limit", 3),
                "returned_count": 2,
                "entries": [
                    {"level": "error", "source": "app.api.routes_agents", "message": "failed"},
                    {"level": "error", "source": "app.agents.runtime", "message": "timeout"},
                ],
            },
            error=None,
        )

    monkeypatch.setattr("app.agents.runtime.generate_with_ollama", fake_generate_with_ollama)
    monkeypatch.setattr("app.agents.runtime.runtime.tool_executor.execute", fake_execute)

    result = asyncio.run(
        run_agent(
            AgentRunRequest.model_validate(
                {
                    "agent_name": "log_analyst",
                    "input": "Analysiere aktuelle Router-Logs",
                    "max_steps": 3,
                }
            )
        )
    )

    assert result.success is True
    assert result.agent_name == "log_analyst"
    assert result.used_model is not None
    assert len(result.tool_calls) == 1
    assert result.tool_calls[0].tool_name == "router_logs"
    assert result.steps[-1].action == "final_answer"


def test_kids_controller_supervisor_runtime_uses_repetition_skill(monkeypatch):
    responses = iter(
        [
            {
                "response": (
                    '{"skill_name":"kids_controller_repetition_review",'
                    '"arguments":{"observation":{"pos1":1,"pos2":2,"pos3":3,'
                    '"trend":{"arrangement_signature":"123","comparable_draw_count":5,'
                    '"same_arrangement_count":4,"same_arrangement_ratio":0.8,'
                    '"repeated_arrangement":true}}},'
                    '"reason":"Wiederholung fachlich bewerten"}'
                )
            },
            {"response": "Diese Aufstellung kam in letzter Zeit sehr oft vor."},
        ]
    )

    async def fake_generate_with_ollama(model, prompt, request_id, stream=False, **kwargs):
        return next(responses)

    async def fake_skill_execute(skill_name, arguments, *, allowed_skills, context):
        assert skill_name == "kids_controller_repetition_review"
        assert allowed_skills == ["kids_controller_repetition_review"]
        return SkillResult(
            skill_name=skill_name,
            success=True,
            output={
                "status": "recommend_review",
                "message": "Diese Aufstellung kam in letzter Zeit sehr oft vor.",
                "source": "kids_controller_repetition_review",
            },
            error=None,
        )

    monkeypatch.setattr("app.agents.runtime.generate_with_ollama", fake_generate_with_ollama)
    monkeypatch.setattr("app.agents.runtime.skill_executor.execute", fake_skill_execute)

    result = asyncio.run(
        run_agent(
            AgentRunRequest.model_validate(
                {
                    "agent_name": "kids_controller_supervisor",
                    "input": "Beobachte die aktuelle Aufstellung",
                    "max_steps": 5,
                }
            )
        )
    )

    assert result.success is True
    assert result.agent_name == "kids_controller_supervisor"
    assert result.used_model is not None
    assert result.steps[-1].action == "final_answer"
    assert any(step.action == "skill_call" for step in result.steps)
    assert any(step.action == "skill_result" for step in result.steps)
    assert "sehr oft" in result.final_answer


def test_kids_controller_supervisor_rejects_free_text_before_skill(monkeypatch):
    responses = iter(
        [
            {"response": "Freie Analyse ohne Skill-Aufruf."},
            {
                "response": (
                    '{"skill_name":"kids_controller_repetition_review",'
                    '"arguments":{"observation":{"pos1":1,"pos2":2,"pos3":3,'
                    '"trend":{"arrangement_signature":"123","comparable_draw_count":5,'
                    '"same_arrangement_count":4,"same_arrangement_ratio":0.8,'
                    '"repeated_arrangement":true}}},'
                    '"reason":"Wiederholung zuerst fachlich bewerten"}'
                )
            },
            {"response": "Diese Aufstellung kam in letzter Zeit sehr oft vor."},
        ]
    )

    async def fake_generate_with_ollama(model, prompt, request_id, stream=False, **kwargs):
        return next(responses)

    async def fake_skill_execute(skill_name, arguments, *, allowed_skills, context):
        return SkillResult(
            skill_name=skill_name,
            success=True,
            output={
                "status": "recommend_review",
                "message": "Diese Aufstellung kam in letzter Zeit sehr oft vor.",
                "source": "kids_controller_repetition_review",
            },
            error=None,
        )

    monkeypatch.setattr("app.agents.runtime.generate_with_ollama", fake_generate_with_ollama)
    monkeypatch.setattr("app.agents.runtime.skill_executor.execute", fake_skill_execute)

    result = asyncio.run(
        run_agent(
            AgentRunRequest.model_validate(
                {
                    "agent_name": "kids_controller_supervisor",
                    "input": "Beobachte die aktuelle Aufstellung",
                    "max_steps": 5,
                }
            )
        )
    )

    assert result.success is True
    assert "sehr oft" in result.final_answer
    assert any(
        step.action == "parse_error"
        and step.observation == "Agent muss zuerst den Skill kids_controller_repetition_review aufrufen."
        for step in result.steps
    )
    assert any(step.action == "skill_call" for step in result.steps)
