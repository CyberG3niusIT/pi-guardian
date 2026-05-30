from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class GuardianActionKind(StrEnum):
    SYSTEMD_RESTART = "systemd_restart"
    DOCKER_RESTART = "docker_restart"


class GuardianActionOutcome(StrEnum):
    EXECUTED = "executed"               # real command ran successfully
    DRY_RUN = "dry_run"                 # decided but not executed (dry_run mode)
    FAILED = "failed"                   # real command ran but failed
    SUPPRESSED_COOLDOWN = "suppressed_cooldown"
    SUPPRESSED_RATE_LIMIT = "suppressed_rate_limit"
    DISABLED = "disabled"               # actions globally disabled
    NOT_WHITELISTED = "not_whitelisted" # requested action id is not in the whitelist
    NO_CANDIDATE = "no_candidate"       # nothing matched a critical target


class GuardianActionExecution(BaseModel):
    """Result of actually running (or attempting) a whitelisted command."""

    executed: bool = False
    success: bool = False
    exit_code: int | None = None
    duration_ms: int | None = None
    command: str = ""
    stdout: str = ""
    stderr: str = ""
    error: str | None = None


class GuardianActionDecision(BaseModel):
    """One action decision for a single whitelisted rule in one cycle."""

    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    action_id: str
    kind: GuardianActionKind
    target: str
    outcome: GuardianActionOutcome
    dry_run: bool
    trigger: str = ""
    trigger_snapshot_id: int | None = None
    executed: bool = False
    success: bool = False
    exit_code: int | None = None
    duration_ms: int | None = None
    command: str = ""
    error: str | None = None
    cooldown_remaining_seconds: int | None = None
    source: str = "policy"  # "policy" (automatic) or "manual" (API/router)


class GuardianActionReport(BaseModel):
    """Aggregate of all action decisions taken during one evaluation cycle."""

    considered: bool = False
    actions_enabled: bool = False
    dry_run: bool = True
    summary: str = "No action considered."
    decisions: list[GuardianActionDecision] = Field(default_factory=list)
