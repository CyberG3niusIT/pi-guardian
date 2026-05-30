"""Guardian actions API: read the whitelist/history, trigger allowed actions.

Reads are open (behind the same network boundary as the rest of the read API);
the write endpoint is auth-gated and still passes through the engine's whitelist,
cooldown and dry-run guards — the caller cannot bypass them.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict

from guardian.app.actions.models import GuardianActionDecision
from guardian.app.auth import require_api

router = APIRouter(prefix="/actions", tags=["actions"])


class ActionExecuteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action_id: str


@router.get("")
async def list_actions(request: Request, limit: int = 20) -> dict[str, Any]:
    registry = request.app.state.action_registry
    store = request.app.state.guardian_store
    history = await store.list_actions(limit=max(int(limit), 1))
    return {
        "enabled": registry.enabled,
        "dry_run": registry.dry_run,
        "whitelist": [rule.model_dump() for rule in registry.all_rules()],
        "history": [record.model_dump() for record in history.items],
    }


@router.post("/execute", response_model=GuardianActionDecision, dependencies=[Depends(require_api)])
async def execute_action(payload: ActionExecuteRequest, request: Request) -> GuardianActionDecision:
    engine = request.app.state.action_engine
    return await engine.execute_by_id(payload.action_id, source="api")
