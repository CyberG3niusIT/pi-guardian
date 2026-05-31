from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field


class GuardianSystemCollectorState(BaseModel):
    checked_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    hostname: str
    running_as_root: bool
    process_pid: int
    process_name: str
    process_uptime_seconds: float | None = None
    cpu_count: int | None = None
    cpu_usage_percent: float | None = None
    load_avg_1m: float | None = None
    load_avg_5m: float | None = None
    load_avg_15m: float | None = None
    cpu_load_ratio_1m: float | None = None
    memory_total_bytes: int | None = None
    memory_available_bytes: int | None = None
    memory_used_bytes: int | None = None
    memory_usage_percent: float | None = None
    swap_total_bytes: int | None = None
    swap_free_bytes: int | None = None
    swap_used_bytes: int | None = None
    swap_usage_percent: float | None = None
    disk_mountpoint: str = "/"
    disk_total_bytes: int | None = None
    disk_free_bytes: int | None = None
    disk_used_bytes: int | None = None
    disk_usage_percent: float | None = None
    temperature_c: float | None = None
    temperature_source: str | None = None
    network_interface: str | None = None
    network_rx_bytes_per_s: float | None = None
    network_tx_bytes_per_s: float | None = None
    notes: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
