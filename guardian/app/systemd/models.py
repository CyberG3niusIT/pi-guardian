from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field


class GuardianSystemdUnitState(BaseModel):
    """Normalized state of a single systemd unit."""

    name: str
    whitelisted: bool
    expected_active: bool
    active_state: str = "unknown"      # active / inactive / failed / activating / ...
    sub_state: str = "unknown"         # running / dead / exited / ...
    load_state: str = "unknown"        # loaded / not-found / masked / ...
    unit_file_state: str = "unknown"   # enabled / disabled / static / ...
    main_pid: int | None = None
    description: str = ""
    error: str | None = None


class GuardianSystemdCollectorState(BaseModel):
    checked_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    available: bool = True
    units: list[GuardianSystemdUnitState] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
