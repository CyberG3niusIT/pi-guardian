from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

from guardian.app.core.domain import GuardianSeverity


class GuardianSnapshotInput(BaseModel):
    checked_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    guardian_status: GuardianSeverity
    router_status: GuardianSeverity
    system_status: GuardianSeverity
    overview_summary: str
    router_summary: str
    system_summary: str
    overview_reason_codes: list[str] = Field(default_factory=list)
    router_reason_codes: list[str] = Field(default_factory=list)
    system_reason_codes: list[str] = Field(default_factory=list)
    systemd_status: GuardianSeverity | None = None
    docker_status: GuardianSeverity | None = None
    systemd_summary: str = ""
    docker_summary: str = ""
    systemd_reason_codes: list[str] = Field(default_factory=list)
    docker_reason_codes: list[str] = Field(default_factory=list)
    router_access_state: str
    router_readiness_state: str
    router_reachable: bool
    router_auth_required: bool
    system_running_as_root: bool
    system_cpu_usage_percent: float | None = None
    system_memory_usage_percent: float | None = None
    system_disk_usage_percent: float | None = None
    system_temperature_c: float | None = None
    system_load_avg_1m: float | None = None
    system_network_rx_bps: float | None = None
    system_network_tx_bps: float | None = None
    evidence: dict[str, Any] = Field(default_factory=dict)


class GuardianSnapshotRecord(GuardianSnapshotInput):
    id: int
    stored_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class GuardianStateTransitionRecord(BaseModel):
    id: int
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    previous_snapshot_id: int | None = None
    current_snapshot_id: int
    from_status: GuardianSeverity
    to_status: GuardianSeverity
    reason_codes: list[str] = Field(default_factory=list)
    summary: str
    evidence: dict[str, Any] = Field(default_factory=dict)


class GuardianPersistenceReceipt(BaseModel):
    ok: bool
    database_path: str
    stored_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    snapshot_id: int | None = None
    transition_id: int | None = None
    changed: bool = False
    previous_status: GuardianSeverity | None = None
    current_status: GuardianSeverity | None = None
    error: str | None = None


class GuardianSnapshotHistory(BaseModel):
    items: list[GuardianSnapshotRecord] = Field(default_factory=list)


class GuardianAlertInput(BaseModel):
    checked_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    alert_key: str
    dedupe_key: str
    alert_kind: str
    outcome: str
    should_send: bool
    sent: bool
    suppressed_reason: str | None = None
    current_status: GuardianSeverity
    previous_status: GuardianSeverity | None = None
    policy_outcome: str
    changed: bool = False
    transition_relevant: bool = False
    cooldown_seconds: int = 0
    cooldown_remaining_seconds: int | None = None
    telegram_ready: bool = False
    telegram_ready_reason: str = "unconfigured"
    telegram_chat_id: str | None = None
    telegram_message_id: int | None = None
    telegram_error: str | None = None
    reason_codes: list[str] = Field(default_factory=list)
    summary: str
    message_text: str = ""
    evidence: dict[str, Any] = Field(default_factory=dict)


class GuardianAlertRecord(GuardianAlertInput):
    id: int
    sent_at: datetime | None = None


class GuardianAlertHistory(BaseModel):
    items: list[GuardianAlertRecord] = Field(default_factory=list)


class GuardianHistoryResponse(BaseModel):
    checked_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    limit: int = 10
    snapshots: list[GuardianSnapshotRecord] = Field(default_factory=list)
    transitions: list[GuardianStateTransitionRecord] = Field(default_factory=list)
    alerts: list[GuardianAlertRecord] = Field(default_factory=list)


class GuardianActionInput(BaseModel):
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    action_id: str
    kind: str
    target: str
    outcome: str
    dry_run: bool = True
    trigger: str = ""
    trigger_snapshot_id: int | None = None
    executed: bool = False
    success: bool = False
    exit_code: int | None = None
    duration_ms: int | None = None
    command: str = ""
    error: str | None = None
    source: str = "policy"
    evidence: dict[str, Any] = Field(default_factory=dict)


class GuardianActionRecord(GuardianActionInput):
    id: int


class GuardianActionHistory(BaseModel):
    items: list[GuardianActionRecord] = Field(default_factory=list)
