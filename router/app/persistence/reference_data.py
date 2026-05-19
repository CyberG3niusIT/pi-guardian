from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path

from sqlmodel import Session
from sqlmodel import select

from app.config import settings
from app.memory.models import AgentRecord, AgentSettingsRecord, ActionRecord, SkillRecord
from app.models.agent_models import AgentDefinition

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parents[2]
LEGACY_AGENT_STORE_PATH = BASE_DIR / "data" / "agents.json"


def _json_dump(value) -> str:
    return json.dumps(value, ensure_ascii=False)


def _json_load(value: str, fallback):
    try:
        return json.loads(value)
    except Exception:
        return fallback


def _agent_record_to_definition(record: AgentRecord, settings_record: AgentSettingsRecord | None) -> AgentDefinition:
    from app.models.agent_models import AgentBehaviorSettings, AgentPersonalitySettings, AgentPolicySettings, AgentSettings
    from app.agents.prompt_builder import build_system_prompt

    behavior = _json_load(settings_record.behavior if settings_record else "{}", {})
    personality = _json_load(settings_record.personality if settings_record else "{}", {})
    policy = _json_load(settings_record.policy if settings_record else "{}", {})
    settings_model = AgentSettings(
        active=record.enabled,
        preferred_model=settings_record.preferred_model if settings_record else None,
        max_steps=settings_record.max_steps if settings_record else 5,
        timeout_seconds=settings_record.timeout_seconds if settings_record else None,
        read_only=record.read_only,
        policy=AgentPolicySettings.model_validate(policy) if policy else AgentPolicySettings(),
        behavior=AgentBehaviorSettings.model_validate(behavior) if behavior else AgentBehaviorSettings(),
        personality=AgentPersonalitySettings.model_validate(personality) if personality else AgentPersonalitySettings(),
        custom_instruction=settings_record.custom_instruction if settings_record else None,
    )
    definition = AgentDefinition(
        name=record.name,
        description=record.description,
        agent_type=record.agent_type,  # type: ignore[arg-type]
        allowed_tools=list(settings_model.policy.allowed_tools),
        settings=settings_model,
        system_prompt="pending",
    )
    return definition.model_copy(update={"system_prompt": build_system_prompt(definition)})


def _definition_to_agent_record(definition: AgentDefinition) -> AgentRecord:
    return AgentRecord(
        name=definition.name,
        agent_type=definition.agent_type,
        description=definition.description,
        enabled=definition.settings.active,
        read_only=definition.settings.read_only,
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )


def _definition_to_settings_record(definition: AgentDefinition) -> AgentSettingsRecord:
    return AgentSettingsRecord(
        agent_name=definition.name,
        preferred_model=definition.settings.preferred_model,
        max_steps=definition.settings.max_steps,
        timeout_seconds=definition.settings.timeout_seconds,
        behavior=definition.settings.behavior.model_dump_json(),
        personality=definition.settings.personality.model_dump_json(),
        policy=definition.settings.policy.model_dump_json(),
        custom_instruction=definition.settings.custom_instruction,
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )


def load_agent_definitions(session: Session) -> list[AgentDefinition]:
    try:
        records = session.exec(select(AgentRecord).order_by(AgentRecord.name)).all()
    except Exception as exc:
        logger.warning("Agent-Definitions konnten nicht aus SQLite gelesen werden: %s", exc)
        records = []

    definitions: list[AgentDefinition] = []
    for record in records:
        try:
            settings_record = session.exec(
                select(AgentSettingsRecord).where(AgentSettingsRecord.agent_name == record.name)
            ).first()
            definitions.append(_agent_record_to_definition(record, settings_record))
        except Exception as exc:
            logger.warning("Agent-Definition %s konnte nicht geladen werden: %s", record.name, exc)

    if definitions:
        return definitions

    if LEGACY_AGENT_STORE_PATH.exists():
        try:
            payload = json.loads(LEGACY_AGENT_STORE_PATH.read_text(encoding="utf-8"))
            agents = payload.get("agents", []) if isinstance(payload, dict) else []
            return [
                AgentDefinition.model_validate(agent)
                for agent in agents
                if isinstance(agent, dict)
            ]
        except Exception as exc:
            logger.warning("Legacy agents.json konnte nicht gelesen werden: %s", exc)

    return []


def save_agent_definitions(session: Session, definitions: list[AgentDefinition]) -> None:
    try:
        existing_names = set(session.exec(select(AgentRecord.name)).all())
        next_names = {definition.name for definition in definitions}

        for name in existing_names - next_names:
            agent_record = session.exec(
                select(AgentRecord).where(AgentRecord.name == name)
            ).first()
            settings_record = session.exec(
                select(AgentSettingsRecord).where(AgentSettingsRecord.agent_name == name)
            ).first()
            if agent_record is not None:
                session.delete(agent_record)
            if settings_record is not None:
                session.delete(settings_record)

        for definition in definitions:
            agent_record = session.exec(
                select(AgentRecord).where(AgentRecord.name == definition.name)
            ).first()
            settings_record = session.exec(
                select(AgentSettingsRecord).where(AgentSettingsRecord.agent_name == definition.name)
            ).first()

            if agent_record is None:
                session.add(_definition_to_agent_record(definition))
            else:
                agent_record.agent_type = definition.agent_type
                agent_record.description = definition.description
                agent_record.enabled = definition.settings.active
                agent_record.read_only = definition.settings.read_only
                agent_record.updated_at = datetime.now()
                session.add(agent_record)

            if settings_record is None:
                session.add(_definition_to_settings_record(definition))
            else:
                settings_record.preferred_model = definition.settings.preferred_model
                settings_record.max_steps = definition.settings.max_steps
                settings_record.timeout_seconds = definition.settings.timeout_seconds
                settings_record.behavior = definition.settings.behavior.model_dump_json()
                settings_record.personality = definition.settings.personality.model_dump_json()
                settings_record.policy = definition.settings.policy.model_dump_json()
                settings_record.custom_instruction = definition.settings.custom_instruction
                settings_record.updated_at = datetime.now()
                session.add(settings_record)

        session.commit()
    except Exception as exc:
        session.rollback()
        logger.warning("Agent-Definitions konnten nicht gespeichert werden: %s", exc)
        raise


def save_skill_definitions(session: Session) -> None:
    from app.skills.registry import is_skill_enabled, list_all_skills

    try:
        existing = {
            row[0]
            for row in session.exec(select(SkillRecord.name)).all()
        }
        definitions = list_all_skills()
        next_names = {skill.name for skill in definitions}
        for name in existing - next_names:
            record = session.exec(select(SkillRecord).where(SkillRecord.name == name)).first()
            if record is not None:
                session.delete(record)
        for skill in definitions:
            record = session.exec(select(SkillRecord).where(SkillRecord.name == skill.name)).first()
            payload = {
                "name": skill.name,
                "skill_type": getattr(skill, "skill_type", "system"),
                "description": skill.description,
                "allowed_tools": _json_dump(list(skill.allowed_tools)),
                "input_schema": _json_dump(getattr(skill, "input_schema_json", skill.input_schema.model_json_schema())),
                "output_schema": _json_dump(getattr(skill, "output_schema_json", skill.output_schema.model_json_schema())),
                "prompt_template": getattr(skill, "prompt_template", None),
                "preferred_model": getattr(skill, "preferred_model", None),
                "source_url": getattr(skill, "source_url", None),
                "read_only": skill.read_only,
                "version": skill.version,
                "created_at": datetime.now(),
                "updated_at": datetime.now(),
            }
            if record is None:
                session.add(SkillRecord(**payload, enabled=is_skill_enabled(skill.name)))
            else:
                for key, value in payload.items():
                    if key not in {"created_at", "enabled"}:
                        setattr(record, key, value)
                record.enabled = is_skill_enabled(skill.name)
                session.add(record)
        session.commit()
    except Exception as exc:
        session.rollback()
        logger.warning("Skill-Definitions konnten nicht gespeichert werden: %s", exc)
        raise


def save_action_definitions(session: Session) -> None:
    from app.actions.registry import list_actions

    try:
        existing = {
            row[0]
            for row in session.exec(select(ActionRecord.name)).all()
        }
        definitions = list_actions()
        next_names = {action.name for action in definitions}
        for name in existing - next_names:
            record = session.exec(select(ActionRecord).where(ActionRecord.name == name)).first()
            if record is not None:
                session.delete(record)
        for action in definitions:
            record = session.exec(select(ActionRecord).where(ActionRecord.name == action.name)).first()
            payload = {
                "name": action.name,
                "description": action.description,
                "allowed_targets": _json_dump(list(action.allowed_targets)),
                "input_schema": _json_dump(action.input_schema.model_json_schema()),
                "output_schema": _json_dump(action.output_schema.model_json_schema()),
                "read_only": action.read_only,
                "requires_approval": action.requires_approval,
                "version": action.version,
                "enabled": action.enabled,
                "created_at": datetime.now(),
                "updated_at": datetime.now(),
            }
            if record is None:
                session.add(ActionRecord(**payload))
            else:
                for key, value in payload.items():
                    if key not in {"created_at"}:
                        setattr(record, key, value)
                session.add(record)
        session.commit()
    except Exception as exc:
        session.rollback()
        logger.warning("Action-Definitions konnten nicht gespeichert werden: %s", exc)
        raise


def bootstrap_reference_data(session: Session) -> None:
    try:
        from app.agents.registry import registry as agent_registry
        agent_registry.reload_persisted()
        save_agent_definitions(session, agent_registry.list())
    except Exception as exc:
        logger.warning("Agent-Referenzdaten konnten nicht gebootstrapped werden: %s", exc)

    try:
        from app.skills.registry import registry as skill_registry
        skill_registry.reload_persisted()
        save_skill_definitions(session)
    except Exception as exc:
        logger.warning("Skill-Referenzdaten konnten nicht gebootstrapped werden: %s", exc)

    try:
        save_action_definitions(session)
    except Exception as exc:
        logger.warning("Action-Referenzdaten konnten nicht gebootstrapped werden: %s", exc)
