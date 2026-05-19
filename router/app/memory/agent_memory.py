from __future__ import annotations

import logging
from datetime import datetime

from sqlmodel import Session, select

from app.database import engine
from app.memory.models import AgentMemoryEntry, AgentRunRecord, AgentStepRecord

logger = logging.getLogger(__name__)


def _safe_execute(callback):
    try:
        with Session(engine) as session:
            return callback(session)
    except Exception as exc:
        logger.warning("AgentMemory-Operation fehlgeschlagen: %s", exc)
        return None


def get_agent_memories(agent_name: str, limit: int = 5) -> list[AgentMemoryEntry]:
    def _callback(session: Session) -> list[AgentMemoryEntry]:
        entries = session.exec(
            select(AgentMemoryEntry)
            .where(AgentMemoryEntry.agent_name == agent_name)
            .where(AgentMemoryEntry.active == True)  # noqa: E712
            .order_by(
                AgentMemoryEntry.priority.desc(),
                AgentMemoryEntry.times_confirmed.desc(),
                AgentMemoryEntry.created_at.desc(),
            )
            .limit(limit)
        ).all()
        return list(entries)

    result = _safe_execute(_callback)
    return result if result is not None else []


def add_agent_memory(
    *,
    agent_name: str,
    memory_type: str,
    content: str,
    source_run_id: str | None = None,
    priority: int = 3,
) -> AgentMemoryEntry | None:
    def _callback(session: Session) -> AgentMemoryEntry:
        entry = AgentMemoryEntry(
            agent_name=agent_name,
            memory_type=memory_type,
            content=content,
            source_run_id=source_run_id,
            priority=priority,
            active=True,
            times_confirmed=0,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        session.add(entry)
        session.commit()
        session.refresh(entry)
        return entry

    return _safe_execute(_callback)


def confirm_memory(memory_id: int) -> AgentMemoryEntry | None:
    def _callback(session: Session) -> AgentMemoryEntry | None:
        entry = session.get(AgentMemoryEntry, memory_id)
        if entry is None:
            return None
        entry.times_confirmed += 1
        entry.updated_at = datetime.now()
        session.add(entry)
        session.commit()
        session.refresh(entry)
        return entry

    return _safe_execute(_callback)


def delete_memory(memory_id: int) -> bool:
    def _callback(session: Session) -> bool:
        entry = session.get(AgentMemoryEntry, memory_id)
        if entry is None:
            return False
        entry.active = False
        entry.updated_at = datetime.now()
        session.add(entry)
        session.commit()
        return True

    result = _safe_execute(_callback)
    return bool(result)


def extract_from_run(run_id: str) -> list[AgentMemoryEntry]:
    def _callback(session: Session) -> list[AgentMemoryEntry]:
        # Check for existing entries for this run to avoid duplicates
        existing = session.exec(
            select(AgentMemoryEntry).where(AgentMemoryEntry.source_run_id == run_id)
        ).first()
        if existing is not None:
            return []

        run = session.exec(
            select(AgentRunRecord).where(AgentRunRecord.run_id == run_id)
        ).first()
        if run is None:
            return []

        steps = session.exec(
            select(AgentStepRecord).where(AgentStepRecord.run_id == run_id)
        ).all()

        created: list[AgentMemoryEntry] = []

        # Create a "finding" entry if run was successful and has a non-empty final_answer
        if run.success and run.final_answer and run.final_answer.strip():
            raw_content = run.final_answer.strip()
            content = raw_content[:280] if len(raw_content) > 280 else raw_content
            entry = AgentMemoryEntry(
                agent_name=run.agent_name,
                memory_type="finding",
                content=content,
                source_run_id=run_id,
                priority=3,
                active=True,
                times_confirmed=0,
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )
            session.add(entry)
            created.append(entry)

        # Create a "failure" entry if any step had action_type="parse_error" or run failed
        has_parse_error = any(s.action_type == "parse_error" for s in steps)
        if has_parse_error or not run.success:
            if has_parse_error:
                error_step = next(s for s in steps if s.action_type == "parse_error")
                error_info = error_step.observation or "Parse-Fehler ohne Details"
            else:
                error_info = f"Lauf fehlgeschlagen: {run.final_answer[:200]}" if run.final_answer else "Lauf fehlgeschlagen ohne Details"

            content = error_info[:280] if len(error_info) > 280 else error_info
            entry = AgentMemoryEntry(
                agent_name=run.agent_name,
                memory_type="failure",
                content=content,
                source_run_id=run_id,
                priority=4,
                active=True,
                times_confirmed=0,
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )
            session.add(entry)
            created.append(entry)

        if created:
            session.commit()
            for e in created:
                session.refresh(e)

        return created

    result = _safe_execute(_callback)
    return result if result is not None else []
