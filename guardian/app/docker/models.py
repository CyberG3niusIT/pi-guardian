from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field


class GuardianDockerContainerState(BaseModel):
    """Normalized state of a single Docker container."""

    name: str
    whitelisted: bool
    expected_running: bool
    present: bool = True
    state: str = "unknown"        # running / exited / restarting / paused / dead / missing
    status_text: str = ""         # e.g. "Up 5 days (healthy)"
    health: str = "none"          # healthy / unhealthy / starting / none / unknown
    restart_count: int | None = None
    image: str = ""
    cpu_percent: float | None = None
    memory_usage: str | None = None      # z.B. "312MiB"
    memory_percent: float | None = None
    started_at: str | None = None        # ISO (inspect, nur Whitelist)
    uptime_text: str | None = None       # docker ps RunningFor, z.B. "5 days"
    error: str | None = None


class GuardianDockerCollectorState(BaseModel):
    checked_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    available: bool = True
    containers: list[GuardianDockerContainerState] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
