import asyncio

from app.api.routes_agents import agent_import
from app.api.routes_skills import skill_import
from app.models.agent_models import (
    AgentDefinition,
    AgentBehaviorSettings,
    AgentImportRequest,
    AgentPersonalitySettings,
)
from app.models.skill_models import SkillCreateRequest, SkillDefinition, SkillImportRequest, SkillUpdateRequest
from app.skills.registry import create_skill, delete_skill, get_skill, update_skill


def test_custom_skill_create_execute_update_delete(monkeypatch):
    monkeypatch.setattr("app.skills.registry.registry._persist", lambda: None)

    payload = SkillCreateRequest(
        name="json_triage",
        description="JSON-Triage für Router-Befunde",
        prompt_template="Fasse die Eingabe zusammen: {input_json}",
        input_schema={
            "type": "object",
            "required": ["message"],
            "properties": {"message": {"type": "string"}},
        },
        output_schema={
            "type": "object",
            "required": ["summary"],
            "properties": {"summary": {"type": "string"}},
        },
        preferred_model="qwen2.5-coder:1.5b",
    )

    created = create_skill(payload)
    assert created.name == "json_triage"
    assert created.skill_type == "custom"

    skill = get_skill("json_triage")
    assert skill is not None

    async def fake_generate_with_ollama(model, prompt, request_id, stream=False):
        assert model == "qwen2.5-coder:1.5b"
        assert "JSON-Triage" in prompt
        return {"response": '{"summary":"ok"}'}

    monkeypatch.setattr("app.skills.custom.generate_with_ollama", fake_generate_with_ollama)
    result = skill.execute(skill.validate_arguments({"message": "router timeout"}))
    assert result.success is True
    assert result.output == {"summary": "ok"}

    updated = update_skill(
        "json_triage",
        SkillUpdateRequest(
            description="Aktualisierte Triage",
            prompt_template="Antworte knapp: {message}",
            preferred_model="qwen2.5-coder:3b",
        ),
    )
    assert updated.description == "Aktualisierte Triage"
    assert updated.preferred_model == "qwen2.5-coder:3b"

    delete_skill("json_triage")
    assert get_skill("json_triage") is None


def test_agent_import_from_github_payload(monkeypatch):
    imported_names: list[str] = []

    monkeypatch.setattr(
        "app.api.routes_agents.fetch_json_from_github",
        lambda url: {
            "agents": [
                {
                    "name": "github_guard",
                    "description": "Importierter Guard",
                    "allowed_tools": ["system_status"],
                    "read_only": True,
                    "settings": {
                        "active": True,
                        "preferred_model": None,
                        "max_steps": 4,
                        "timeout_seconds": 90,
                        "read_only": True,
                        "policy": {
                            "allowed_tools": ["system_status"],
                            "allowed_skills": [],
                            "allowed_actions": [],
                            "read_only": True,
                            "can_propose_actions": False,
                            "can_use_logs": False,
                            "can_use_services": False,
                            "can_use_docker": False,
                            "max_steps": 4,
                            "max_tool_calls": None,
                        },
                        "behavior": AgentBehaviorSettings().model_dump(mode="json"),
                        "personality": AgentPersonalitySettings().model_dump(mode="json"),
                        "custom_instruction": None,
                    },
                }
            ]
        },
    )
    monkeypatch.setattr(
        "app.api.routes_agents.create_agent",
        lambda request: imported_names.append(request.name)
        or AgentDefinition(
            name=request.name,
            description=request.description,
            agent_type="custom",
            allowed_tools=request.allowed_tools,
            settings=request.settings,
            system_prompt="pending",
        ),
    )

    response = asyncio.run(agent_import(AgentImportRequest(github_url="https://github.com/org/repo/blob/main/agents.json")))
    assert response.source == "https://raw.githubusercontent.com/org/repo/main/agents.json"
    assert imported_names == ["github_guard"]
    assert response.imported_agents[0].name == "github_guard"


def test_skill_import_from_github_payload(monkeypatch):
    imported: list[tuple[str, str]] = []

    monkeypatch.setattr(
        "app.api.routes_skills.fetch_json_from_github",
        lambda url: {
            "skills": [
                {
                    "name": "github_skill",
                    "description": "Importierter Skill",
                    "prompt_template": "Prüfe: {input_json}",
                    "input_schema": {"type": "object"},
                    "output_schema": {"type": "object"},
                    "preferred_model": "qwen2.5-coder:1.5b",
                }
            ]
        },
    )
    monkeypatch.setattr(
        "app.api.routes_skills.create_skill",
        lambda request, skill_type="custom": imported.append((request.name, skill_type))
        or SkillDefinition(
            name=request.name,
            description=request.description,
            skill_type=skill_type,
            allowed_tools=[],
            input_schema=request.input_schema,
            output_schema=request.output_schema,
            prompt_template=request.prompt_template,
            preferred_model=request.preferred_model,
            source_url=request.source_url,
            read_only=True,
            version=request.version,
            enabled=True,
        ),
    )

    response = asyncio.run(skill_import(SkillImportRequest(github_url="https://github.com/org/repo/blob/main/skills.json")))
    assert response.source == "https://raw.githubusercontent.com/org/repo/main/skills.json"
    assert imported == [("github_skill", "github_imported")]
    assert response.imported_skills[0].name == "github_skill"
