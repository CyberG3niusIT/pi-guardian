from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel
from sqlmodel import Session, select

from app.database import get_session
from app.memory.agent_memory import (
    add_agent_memory,
    confirm_memory,
    delete_memory,
    extract_from_run,
    get_agent_memories,
)
from app.memory.models import AgentMemoryEntry, AgentRunRecord
from app.router.auth import authorize_protected_request

logger = logging.getLogger(__name__)

router = APIRouter(tags=["agent-memory"])


def _require_agents_access(
    request: Request,
    session: Session = Depends(get_session),
) -> None:
    authorize_protected_request(request, session, "/agents")


class AgentMemoryEntryRead(BaseModel):
    id: int
    agent_name: str
    memory_type: str
    content: str
    active: bool
    priority: int
    source_run_id: str | None
    times_confirmed: int
    created_at: str
    updated_at: str


class AgentMemoryEntryCreate(BaseModel):
    memory_type: str = "instruction"  # "finding"|"failure"|"feedback"|"instruction"
    content: str
    priority: int = 3
    source_run_id: str | None = None


def _to_read(entry: AgentMemoryEntry) -> AgentMemoryEntryRead:
    return AgentMemoryEntryRead(
        id=entry.id or 0,
        agent_name=entry.agent_name,
        memory_type=entry.memory_type,
        content=entry.content,
        active=entry.active,
        priority=entry.priority,
        source_run_id=entry.source_run_id,
        times_confirmed=entry.times_confirmed,
        created_at=entry.created_at.isoformat(),
        updated_at=entry.updated_at.isoformat(),
    )


@router.get(
    "/agents/{agent_name}/memory",
    response_model=list[AgentMemoryEntryRead],
    dependencies=[Depends(_require_agents_access)],
)
async def list_agent_memory(agent_name: str) -> list[AgentMemoryEntryRead]:
    entries = get_agent_memories(agent_name, limit=50)
    return [_to_read(e) for e in entries]


@router.post(
    "/agents/{agent_name}/memory",
    response_model=AgentMemoryEntryRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(_require_agents_access)],
)
async def create_agent_memory(
    agent_name: str,
    payload: AgentMemoryEntryCreate,
) -> AgentMemoryEntryRead:
    entry = add_agent_memory(
        agent_name=agent_name,
        memory_type=payload.memory_type,
        content=payload.content,
        priority=payload.priority,
        source_run_id=payload.source_run_id,
    )
    if entry is None:
        raise HTTPException(status_code=500, detail="Speichern des Memory-Eintrags fehlgeschlagen")
    return _to_read(entry)


@router.put(
    "/agents/{agent_name}/memory/{memory_id}/confirm",
    response_model=AgentMemoryEntryRead,
    dependencies=[Depends(_require_agents_access)],
)
async def confirm_agent_memory(agent_name: str, memory_id: int) -> AgentMemoryEntryRead:
    entry = confirm_memory(memory_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Memory-Eintrag nicht gefunden")
    if entry.agent_name != agent_name:
        raise HTTPException(status_code=404, detail="Memory-Eintrag nicht gefunden")
    return _to_read(entry)


@router.delete(
    "/agents/{agent_name}/memory/{memory_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(_require_agents_access)],
)
async def deactivate_agent_memory(agent_name: str, memory_id: int) -> Response:
    deleted = delete_memory(memory_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Memory-Eintrag nicht gefunden")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/agents/{agent_name}/memory/extract",
    response_model=list[AgentMemoryEntryRead],
    dependencies=[Depends(_require_agents_access)],
)
async def extract_memory_from_last_run(
    agent_name: str,
    session: Session = Depends(get_session),
) -> list[AgentMemoryEntryRead]:
    # Find the last successful run for this agent
    run = session.exec(
        select(AgentRunRecord)
        .where(AgentRunRecord.agent_name == agent_name)
        .where(AgentRunRecord.success == True)  # noqa: E712
        .order_by(AgentRunRecord.started_at.desc())
    ).first()
    if run is None:
        raise HTTPException(
            status_code=404,
            detail=f"Kein erfolgreicher Lauf für Agent '{agent_name}' gefunden",
        )
    entries = extract_from_run(run.run_id)
    return [_to_read(e) for e in entries]
