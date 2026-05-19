from __future__ import annotations

from collections.abc import Iterable

from app.database import engine
from app.models.skill_models import SkillCreateRequest, SkillDefinition, SkillUpdateRequest
from app.skills.base import BaseSkill
from app.skills.custom import (
    CustomPromptSkill,
    payload_to_skill_definition,
    request_to_custom_skill_payload,
)
from app.skills.store import load_custom_skill_payloads
from sqlmodel import Session

from app.persistence.reference_data import save_skill_definitions
from sqlmodel import Session, select


class SkillRegistry:
    def __init__(self) -> None:
        self._skills: dict[str, BaseSkill] = {}
        self._builtin_names: set[str] = set()
        self._disabled_names: set[str] = set()
        self._load_disabled_from_db()

    def _load_disabled_from_db(self) -> None:
        try:
            from app.memory.models import SkillRecord
            with Session(engine) as session:
                records = session.exec(
                    select(SkillRecord).where(SkillRecord.enabled == False)  # noqa: E712
                ).all()
                self._disabled_names = {r.name for r in records}
        except Exception:
            self._disabled_names = set()

    def _set_enabled_in_db(self, name: str, enabled: bool) -> None:
        try:
            from app.memory.models import SkillRecord
            with Session(engine) as session:
                record = session.exec(
                    select(SkillRecord).where(SkillRecord.name == name)
                ).first()
                if record is not None:
                    record.enabled = enabled
                    session.add(record)
                    session.commit()
        except Exception:
            pass

    def register(self, skill: BaseSkill, *, builtin: bool = False) -> None:
        name = skill.name.strip()
        if not name:
            raise ValueError("Skill-Name darf nicht leer sein")
        if name in self._skills:
            raise ValueError(f"Skill bereits registriert: {name}")
        self._skills[name] = skill
        if builtin:
            self._builtin_names.add(name)

    def get(self, skill_name: str) -> BaseSkill | None:
        return self._skills.get(skill_name)

    def list_skills(self) -> list[BaseSkill]:
        return [self._skills[name] for name in sorted(self._skills) if name not in self._disabled_names]

    def list_all_skills(self) -> list[BaseSkill]:
        return [self._skills[name] for name in sorted(self._skills)]

    def names(self) -> list[str]:
        return [name for name in sorted(self._skills) if name not in self._disabled_names]

    def is_enabled(self, skill_name: str) -> bool:
        return skill_name in self._skills and skill_name not in self._disabled_names

    def reload_persisted(self) -> None:
        self._skills = {
            name: skill for name, skill in self._skills.items() if name in self._builtin_names
        }
        for payload in load_custom_skill_payloads():
            self._skills[payload.name] = CustomPromptSkill(payload)

    def _persist(self) -> None:
        with Session(engine) as session:
            save_skill_definitions(session)

    def ensure_allowed(self, allowed_skills: Iterable[str]) -> list[str]:
        normalized: list[str] = []
        for name in allowed_skills:
            stripped = name.strip()
            if not stripped:
                raise ValueError("allowed_skills enthält leere Einträge")
            if stripped not in self._skills:
                raise ValueError(f"Unbekannter Skill: {stripped}")
            if stripped not in normalized:
                normalized.append(stripped)
        return normalized

    def create(self, payload: SkillCreateRequest, *, skill_type: str = "custom") -> SkillDefinition:
        if payload.name in self._skills:
            raise ValueError(f"Skill existiert bereits: {payload.name}")
        if payload.name in self._builtin_names:
            raise ValueError(f"System-Skill ist reserviert: {payload.name}")
        custom_payload = request_to_custom_skill_payload(payload, skill_type=skill_type)
        skill = CustomPromptSkill(custom_payload)
        self._skills[skill.name] = skill
        self._persist()
        return payload_to_skill_definition(custom_payload)

    def update(self, skill_name: str, payload: SkillUpdateRequest) -> SkillDefinition:
        skill = self._skills.get(skill_name)
        if skill is None:
            raise ValueError("Skill nicht gefunden")
        if skill_name in self._builtin_names:
            raise ValueError("System-Skills dürfen nicht geändert werden")

        current = SkillCreateRequest(
            name=skill.name,
            description=skill.description,
            prompt_template=getattr(skill, "prompt_template", ""),
            input_schema=getattr(skill, "input_schema_json", skill.input_schema.model_json_schema()),
            output_schema=getattr(skill, "output_schema_json", skill.output_schema.model_json_schema()),
            preferred_model=getattr(skill, "preferred_model", None),
            source_url=getattr(skill, "source_url", None),
            version=getattr(skill, "version", "1.0"),
            read_only=True,
        )
        merged = current.model_copy(
            update={
                key: value
                for key, value in payload.model_dump(exclude_unset=True).items()
                if value is not None
            }
        )
        new_payload = request_to_custom_skill_payload(
            SkillCreateRequest.model_validate(merged.model_dump(mode="json")),
            skill_type=getattr(skill, "skill_type", "custom"),
        )
        self._skills[skill_name] = CustomPromptSkill(new_payload)
        self._persist()
        return payload_to_skill_definition(new_payload)

    def delete(self, skill_name: str) -> None:
        if skill_name not in self._skills:
            raise ValueError("Skill nicht gefunden")
        if skill_name in self._builtin_names:
            raise ValueError("System-Skills dürfen nicht gelöscht werden")
        del self._skills[skill_name]
        self._persist()

    def enable(self, skill_name: str) -> None:
        if skill_name not in self._skills:
            raise ValueError("Skill nicht gefunden")
        if skill_name in self._builtin_names:
            raise ValueError("System-Skills können nicht deaktiviert werden")
        self._disabled_names.discard(skill_name)
        self._set_enabled_in_db(skill_name, True)

    def disable(self, skill_name: str) -> None:
        if skill_name not in self._skills:
            raise ValueError("Skill nicht gefunden")
        if skill_name in self._builtin_names:
            raise ValueError("System-Skills können nicht deaktiviert werden")
        self._disabled_names.add(skill_name)
        self._set_enabled_in_db(skill_name, False)

    def get_any(self, skill_name: str) -> BaseSkill | None:
        """Return a skill regardless of enabled/disabled state."""
        return self._skills.get(skill_name)


registry = SkillRegistry()


def register_skill(skill: BaseSkill) -> None:
    registry.register(skill)


def register_builtin_skill(skill: BaseSkill) -> None:
    registry.register(skill, builtin=True)


def get_skill(skill_name: str) -> BaseSkill | None:
    return registry.get(skill_name)


def list_skills() -> list[BaseSkill]:
    return registry.list_skills()


def list_all_skills() -> list[BaseSkill]:
    return registry.list_all_skills()


def list_skill_names() -> list[str]:
    return registry.names()


def create_skill(payload: SkillCreateRequest, *, skill_type: str = "custom") -> SkillDefinition:
    return registry.create(payload, skill_type=skill_type)


def update_skill(skill_name: str, payload: SkillUpdateRequest) -> SkillDefinition:
    return registry.update(skill_name, payload)


def delete_skill(skill_name: str) -> None:
    registry.delete(skill_name)


def enable_skill(skill_name: str) -> None:
    registry.enable(skill_name)


def disable_skill(skill_name: str) -> None:
    registry.disable(skill_name)


def get_skill_any(skill_name: str) -> BaseSkill | None:
    """Return a skill regardless of enabled/disabled state."""
    return registry.get_any(skill_name)


def is_skill_enabled(skill_name: str) -> bool:
    return registry.is_enabled(skill_name)


from app.skills import standard as _standard_skills  # noqa: E402,F401
