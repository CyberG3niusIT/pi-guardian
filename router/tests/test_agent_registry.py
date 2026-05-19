import asyncio
import importlib

import pytest

from app.agents.registry import AgentRegistry, delete_agent, get_agent, list_agents
from app.models.agent_models import AgentBehaviorSettings, AgentDefinition, AgentPersonalitySettings, AgentPolicySettings, AgentSettings
from app.models.agent_models import AgentRunRequest
from app.api.routes_agents import agent_run


def test_guardian_supervisor_is_registered():
    agent = get_agent("guardian_supervisor")
    assert agent is not None
    assert agent.name == "guardian_supervisor"
    assert agent.settings.read_only is True
    assert agent.allowed_tools == [
        "system_status",
        "docker_status",
        "service_status",
    ]


def test_service_diagnose_is_registered():
    agent = get_agent("service_diagnose")
    assert agent is not None
    assert agent.name == "service_diagnose"
    assert agent.agent_type == "system"
    assert agent.settings.read_only is True
    assert agent.allowed_tools == [
        "service_status",
        "system_status",
    ]


def test_log_analyst_is_registered():
    agent = get_agent("log_analyst")
    assert agent is not None
    assert agent.name == "log_analyst"
    assert agent.agent_type == "system"
    assert agent.settings.read_only is True
    assert agent.allowed_tools == [
        "router_logs",
        "service_status",
        "system_status",
    ]


def test_service_operator_is_registered():
    agent = get_agent("service_operator")
    assert agent is not None
    assert agent.agent_type == "actor"
    assert agent.settings.read_only is True
    assert agent.settings.policy.can_propose_actions is True
    assert agent.settings.policy.allowed_actions == [
        "restart_service",
        "rerun_health_check",
    ]


def test_kids_controller_supervisor_is_registered():
    agent = get_agent("kids_controller_supervisor")
    assert agent is not None
    assert agent.agent_type == "system"
    assert agent.settings.read_only is True
    assert agent.settings.max_steps == 5
    assert agent.settings.policy.allowed_skills == ["kids_controller_repetition_review"]
    assert agent.allowed_tools == ["system_status"]


def test_agent_registry_lists_guardian_supervisor():
    names = [agent.name for agent in list_agents()]
    assert "guardian_supervisor" in names
    assert "service_diagnose" in names
    assert "log_analyst" in names
    assert "service_operator" in names
    assert "kids_controller_supervisor" in names


def test_system_agent_defaults_are_not_overridden_by_persisted_records(monkeypatch):
    agent_registry_module = importlib.import_module("app.agents.registry")
    stale_definition = AgentDefinition(
        name="kids_controller_supervisor",
        description="stale",
        agent_type="system",
        allowed_tools=["system_status"],
        settings=AgentSettings(
            active=True,
            preferred_model=None,
            max_steps=3,
            timeout_seconds=45,
            read_only=True,
            policy=AgentPolicySettings(
                allowed_tools=["system_status"],
                allowed_skills=["kids_controller_repetition_review"],
                allowed_actions=[],
                read_only=True,
                max_steps=3,
            ),
            behavior=AgentBehaviorSettings(),
            personality=AgentPersonalitySettings(),
        ),
        system_prompt="pending",
    )

    monkeypatch.setattr(agent_registry_module, "load_agent_records", lambda: [stale_definition])

    isolated_registry = AgentRegistry()
    agent = isolated_registry.get("kids_controller_supervisor")

    assert agent is not None
    assert agent.settings.max_steps == 5


def test_service_diagnose_is_not_deletable():
    with pytest.raises(ValueError, match="System- und Aktor-Agenten dürfen nicht gelöscht werden"):
        delete_agent("service_diagnose")


def test_log_analyst_is_not_deletable():
    with pytest.raises(ValueError, match="System- und Aktor-Agenten dürfen nicht gelöscht werden"):
        delete_agent("log_analyst")


def test_service_operator_is_not_deletable():
    with pytest.raises(ValueError, match="System- und Aktor-Agenten dürfen nicht gelöscht werden"):
        delete_agent("service_operator")


def test_fastapi_registers_agent_routes():
    from app.main import app

    paths = {route.path for route in app.routes}
    assert "/agents" in paths
    assert "/agents/{agent_name}" in paths
    assert "/agents/run" in paths


def test_agents_run_endpoint_accepts_service_diagnose(monkeypatch):
    async def fake_run_agent(payload):
        from app.models.agent_models import AgentRunResponse

        return AgentRunResponse(
            agent_name=payload.agent_name,
            success=True,
            final_answer="ok",
            steps=[],
            tool_calls=[],
            errors=[],
            used_model="mock-model",
        )

    monkeypatch.setattr("app.api.routes_agents.run_agent", fake_run_agent)

    response = asyncio.run(
        agent_run(
            AgentRunRequest(
                agent_name="service_diagnose",
                prompt="Prüfe den Dienst",
                max_steps=3,
            )
        )
    )

    assert response.agent_name == "service_diagnose"
    assert response.success is True
    assert response.used_model == "mock-model"


def test_agents_run_endpoint_accepts_log_analyst(monkeypatch):
    async def fake_run_agent(payload):
        from app.models.agent_models import AgentRunResponse

        return AgentRunResponse(
            agent_name=payload.agent_name,
            success=True,
            final_answer="ok",
            steps=[],
            tool_calls=[],
            errors=[],
            used_model="mock-model",
        )

    monkeypatch.setattr("app.api.routes_agents.run_agent", fake_run_agent)

    response = asyncio.run(
        agent_run(
            AgentRunRequest(
                agent_name="log_analyst",
                prompt="Analysiere die Logs",
                max_steps=3,
            )
        )
    )

    assert response.agent_name == "log_analyst"
    assert response.success is True
    assert response.used_model == "mock-model"
