from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Mapping


class GuardianSeverity(StrEnum):
    """Normalized severity levels used by Guardian decisions."""

    OK = "ok"
    INFO = "info"
    WARN = "warn"
    CRITICAL = "critical"


class GuardianSignalSource(StrEnum):
    """Where a Guardian observation originated from."""

    ROUTER = "router"
    SYSTEM = "system"
    SERVICE = "service"
    CONTAINER = "container"
    STORAGE = "storage"
    JOURNAL = "journal"
    EXTERNAL = "external"


class GuardianAction(StrEnum):
    """Deterministic actions the Guardian may eventually emit."""

    NONE = "none"
    ALERT = "alert"
    RETRY = "retry"
    RESTART_ROUTER = "restart_router"
    BLOCK_REQUESTS = "block_requests"
    ESCALATE = "escalate"


@dataclass(frozen=True, slots=True)
class RouterStatus:
    """Snapshot of router state as seen by Guardian."""

    reachable: bool | None = None
    service_active: bool | None = None
    host: str | None = None
    port: int | None = None
    health_path: str = "/health"
    service_name: str = "pi-guardian-router"
    last_checked_at: datetime | None = None
    raw: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class GuardianFinding:
    """One normalized observation that may contribute to a decision."""

    code: str
    summary: str
    severity: GuardianSeverity
    source: GuardianSignalSource
    detail: str | None = None
    evidence: Mapping[str, object] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(frozen=True, slots=True)
class GuardianAssessment:
    """Result of a Guardian evaluation cycle."""

    status: GuardianSeverity
    router: RouterStatus
    findings: tuple[GuardianFinding, ...] = ()
    notes: tuple[str, ...] = ()
    evaluated_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(frozen=True, slots=True)
class GuardianHealth:
    """Minimal service health payload for the Guardian itself."""

    status: str = "ok"
    component: str = "guardian"
    version: str = "0.1.0"
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))

