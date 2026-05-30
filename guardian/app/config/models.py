"""Typed Guardian configuration model.

The operational configuration (thresholds, watch targets, recovery actions,
schedule) lives in a YAML file so it can be edited without touching code.
Secrets (Telegram token, API keys) stay in the process environment and are
loaded by the existing ``*.from_env()`` configs of the alerting/storage layers.

All defaults intentionally mirror the values that were previously hard-coded in
``guardian/app/system/evaluator.py``. Loading an empty or missing YAML file
therefore reproduces the prior behaviour exactly.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class CpuThresholds(BaseModel):
    usage_warn_percent: float = 80.0
    usage_critical_percent: float = 95.0
    load_ratio_warn: float = 1.5
    load_ratio_critical: float = 2.5


class MemoryThresholds(BaseModel):
    usage_warn_percent: float = 85.0
    usage_critical_percent: float = 95.0
    available_warn_bytes: int = 1024 * 1024 * 1024
    available_critical_bytes: int = 256 * 1024 * 1024


class SwapThresholds(BaseModel):
    # Swap is only meaningful when swap space exists; evaluated leniently.
    usage_warn_percent: float = 60.0
    usage_critical_percent: float = 90.0


class DiskThresholds(BaseModel):
    usage_warn_percent: float = 85.0
    usage_critical_percent: float = 95.0
    free_warn_bytes: int = 10 * 1024 * 1024 * 1024
    free_critical_bytes: int = 2 * 1024 * 1024 * 1024


class TemperatureThresholds(BaseModel):
    warn_c: float = 80.0
    critical_c: float = 90.0


class GuardianThresholds(BaseModel):
    cpu: CpuThresholds = Field(default_factory=CpuThresholds)
    memory: MemoryThresholds = Field(default_factory=MemoryThresholds)
    swap: SwapThresholds = Field(default_factory=SwapThresholds)
    disk: DiskThresholds = Field(default_factory=DiskThresholds)
    temperature: TemperatureThresholds = Field(default_factory=TemperatureThresholds)


class WatchTargets(BaseModel):
    """Curated whitelists of critical targets that may raise alerts/actions."""

    systemd: list[str] = Field(default_factory=list)
    docker: list[str] = Field(default_factory=list)


class DiscoveryConfig(BaseModel):
    """Auto-discovery observes non-whitelisted targets without alerting."""

    enabled: bool = True
    # When False, discovered (non-whitelisted) targets are observed/logged only.
    alert: bool = False


class DockerWatchConfig(BaseModel):
    # RestartCount delta that escalates a container to WARN within the window.
    restart_count_warn: int = 3


class ActionRule(BaseModel):
    """One whitelisted recovery action. No free-form commands are ever run."""

    id: str
    kind: str  # "systemd_restart" | "docker_restart"
    target: str  # unit name or container name (must also be in WatchTargets)
    description: str = ""
    enabled: bool = True


class ActionsConfig(BaseModel):
    enabled: bool = False
    # Global safety switch: when True, actions are decided and logged but never executed.
    dry_run: bool = True
    cooldown_seconds: int = 600
    max_attempts_per_window: int = 2
    window_seconds: int = 3600
    command_timeout_seconds: int = 30
    allow: list[ActionRule] = Field(default_factory=list)


class ScheduleConfig(BaseModel):
    # Internal async loop cadence for continuous monitoring.
    interval_seconds: int = 45
    loop_enabled: bool = True
    # The 6h status report is triggered externally by a systemd timer.
    report_enabled: bool = True


class GuardianConfig(BaseModel):
    thresholds: GuardianThresholds = Field(default_factory=GuardianThresholds)
    watch: WatchTargets = Field(default_factory=WatchTargets)
    discovery: DiscoveryConfig = Field(default_factory=DiscoveryConfig)
    docker: DockerWatchConfig = Field(default_factory=DockerWatchConfig)
    actions: ActionsConfig = Field(default_factory=ActionsConfig)
    schedule: ScheduleConfig = Field(default_factory=ScheduleConfig)
