from __future__ import annotations

import json
import logging

from sqlmodel import Session, select

from app.database import engine
from app.memory.models import SkillRecord
from app.models.skill_models import SkillCreateRequest
from app.skills.custom import CustomSkillPayload, request_to_custom_skill_payload

logger = logging.getLogger(__name__)


def load_custom_skill_payloads() -> list[CustomSkillPayload]:
    try:
        with Session(engine) as session:
            records = session.exec(
                select(SkillRecord)
                .where(SkillRecord.skill_type != "system")
                .order_by(SkillRecord.name)
            ).all()
    except Exception as exc:
        logger.warning("Custom-Skills konnten nicht aus SQLite geladen werden: %s", exc)
        return []

    loaded: list[CustomSkillPayload] = []
    for record in records:
        try:
            request = SkillCreateRequest(
                name=record.name,
                description=record.description,
                prompt_template=record.prompt_template or "",
                input_schema=json.loads(record.input_schema or "{}"),
                output_schema=json.loads(record.output_schema or "{}"),
                preferred_model=record.preferred_model,
                source_url=record.source_url,
                version=record.version,
                read_only=record.read_only,
            )
            loaded.append(
                request_to_custom_skill_payload(request, skill_type=record.skill_type or "custom")
            )
        except Exception as exc:
            logger.warning("Custom-Skill %s übersprungen: %s", record.name, exc)
    return loaded
