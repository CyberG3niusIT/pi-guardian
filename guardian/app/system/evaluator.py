from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field

from guardian.app.config.models import GuardianThresholds
from guardian.app.core.domain import GuardianSeverity, GuardianSignalSource
from guardian.app.core.evaluation import GuardianEvaluationReason
from guardian.app.system.models import GuardianSystemCollectorState


class GuardianSystemEvaluation(BaseModel):
    status: GuardianSeverity
    summary: str
    checked_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    reasons: list[GuardianEvaluationReason] = Field(default_factory=list)
    system: GuardianSystemCollectorState


class SystemEvaluator:
    """Deterministically evaluates the normalized local system state.

    Thresholds come from configuration; the defaults reproduce the values that
    were previously hard-coded here.
    """

    def __init__(self, *, thresholds: GuardianThresholds | None = None) -> None:
        self._t = thresholds or GuardianThresholds()

    def evaluate(self, system_state: GuardianSystemCollectorState) -> GuardianSystemEvaluation:
        reasons: list[GuardianEvaluationReason] = []

        status = GuardianSeverity.OK
        summary = "Local system state is healthy."

        self._evaluate_cpu(system_state, reasons)
        self._evaluate_memory(system_state, reasons)
        self._evaluate_swap(system_state, reasons)
        self._evaluate_disk(system_state, reasons)
        self._evaluate_temperature(system_state, reasons)
        self._evaluate_privileges(system_state, reasons)
        self._evaluate_collection_quality(system_state, reasons)

        if any(reason.severity == GuardianSeverity.CRITICAL for reason in reasons):
            status = GuardianSeverity.CRITICAL
            summary = "Local system state is critical."
        elif any(reason.severity == GuardianSeverity.WARN for reason in reasons):
            status = GuardianSeverity.WARN
            summary = "Local system state needs attention."
        elif reasons:
            summary = "Local system state is healthy."
        else:
            reasons.append(
                GuardianEvaluationReason(
                    code="system_state_healthy",
                    summary="All collected system metrics are within expected bounds.",
                    severity=GuardianSeverity.OK,
                    source=GuardianSignalSource.SYSTEM,
                    evidence={
                        "running_as_root": system_state.running_as_root,
                        "cpu_usage_percent": system_state.cpu_usage_percent,
                        "memory_usage_percent": system_state.memory_usage_percent,
                        "disk_usage_percent": system_state.disk_usage_percent,
                        "temperature_c": system_state.temperature_c,
                    },
                )
            )

        return GuardianSystemEvaluation(
            status=status,
            summary=summary,
            reasons=reasons,
            system=system_state,
        )

    def _evaluate_cpu(
        self,
        system_state: GuardianSystemCollectorState,
        reasons: list[GuardianEvaluationReason],
    ) -> None:
        cpu_usage = system_state.cpu_usage_percent
        load_ratio = system_state.cpu_load_ratio_1m
        if cpu_usage is None:
            reasons.append(
                GuardianEvaluationReason(
                    code="system_cpu_unavailable",
                    summary="CPU usage could not be read.",
                    severity=GuardianSeverity.WARN,
                    source=GuardianSignalSource.SYSTEM,
                    detail="The collector did not provide a CPU usage sample.",
                    evidence={"cpu_count": system_state.cpu_count},
                )
            )
            return

        if cpu_usage >= self._t.cpu.usage_critical_percent or (
            load_ratio is not None and load_ratio >= self._t.cpu.load_ratio_critical
        ):
            reasons.append(
                GuardianEvaluationReason(
                    code="system_cpu_critical",
                    summary="CPU load is critical.",
                    severity=GuardianSeverity.CRITICAL,
                    source=GuardianSignalSource.SYSTEM,
                    detail="CPU usage or normalized load exceeded the critical threshold.",
                    evidence={
                        "cpu_usage_percent": cpu_usage,
                        "cpu_count": system_state.cpu_count,
                        "load_avg_1m": system_state.load_avg_1m,
                        "cpu_load_ratio_1m": load_ratio,
                    },
                )
            )
        elif cpu_usage >= self._t.cpu.usage_warn_percent or (
            load_ratio is not None and load_ratio >= self._t.cpu.load_ratio_warn
        ):
            reasons.append(
                GuardianEvaluationReason(
                    code="system_cpu_warn",
                    summary="CPU load is elevated.",
                    severity=GuardianSeverity.WARN,
                    source=GuardianSignalSource.SYSTEM,
                    detail="CPU usage or normalized load crossed the warning threshold.",
                    evidence={
                        "cpu_usage_percent": cpu_usage,
                        "cpu_count": system_state.cpu_count,
                        "load_avg_1m": system_state.load_avg_1m,
                        "cpu_load_ratio_1m": load_ratio,
                    },
                )
            )

    def _evaluate_memory(
        self,
        system_state: GuardianSystemCollectorState,
        reasons: list[GuardianEvaluationReason],
    ) -> None:
        memory_usage = system_state.memory_usage_percent
        memory_available = system_state.memory_available_bytes
        if memory_usage is None:
            reasons.append(
                GuardianEvaluationReason(
                    code="system_memory_unavailable",
                    summary="Memory usage could not be read.",
                    severity=GuardianSeverity.WARN,
                    source=GuardianSignalSource.SYSTEM,
                    detail="The collector did not provide a memory usage sample.",
                )
            )
            return

        if memory_usage >= self._t.memory.usage_critical_percent or (
            memory_available is not None and memory_available <= self._t.memory.available_critical_bytes
        ):
            reasons.append(
                GuardianEvaluationReason(
                    code="system_memory_critical",
                    summary="Memory pressure is critical.",
                    severity=GuardianSeverity.CRITICAL,
                    source=GuardianSignalSource.SYSTEM,
                    detail="Available memory dropped below the critical threshold.",
                    evidence={
                        "memory_usage_percent": memory_usage,
                        "memory_available_bytes": memory_available,
                        "memory_total_bytes": system_state.memory_total_bytes,
                    },
                )
            )
        elif memory_usage >= self._t.memory.usage_warn_percent or (
            memory_available is not None and memory_available <= self._t.memory.available_warn_bytes
        ):
            reasons.append(
                GuardianEvaluationReason(
                    code="system_memory_warn",
                    summary="Memory pressure is elevated.",
                    severity=GuardianSeverity.WARN,
                    source=GuardianSignalSource.SYSTEM,
                    detail="Available memory crossed the warning threshold.",
                    evidence={
                        "memory_usage_percent": memory_usage,
                        "memory_available_bytes": memory_available,
                        "memory_total_bytes": system_state.memory_total_bytes,
                    },
                )
            )

    def _evaluate_swap(
        self,
        system_state: GuardianSystemCollectorState,
        reasons: list[GuardianEvaluationReason],
    ) -> None:
        swap_total = system_state.swap_total_bytes
        swap_usage = system_state.swap_usage_percent
        # No swap configured, or unreadable -> nothing to evaluate.
        if not swap_total or swap_usage is None:
            return

        if swap_usage >= self._t.swap.usage_critical_percent:
            reasons.append(
                GuardianEvaluationReason(
                    code="system_swap_critical",
                    summary="Swap usage is critical.",
                    severity=GuardianSeverity.CRITICAL,
                    source=GuardianSignalSource.SYSTEM,
                    detail="Swap usage crossed the critical threshold.",
                    evidence={
                        "swap_usage_percent": swap_usage,
                        "swap_total_bytes": swap_total,
                        "swap_free_bytes": system_state.swap_free_bytes,
                    },
                )
            )
        elif swap_usage >= self._t.swap.usage_warn_percent:
            reasons.append(
                GuardianEvaluationReason(
                    code="system_swap_warn",
                    summary="Swap usage is elevated.",
                    severity=GuardianSeverity.WARN,
                    source=GuardianSignalSource.SYSTEM,
                    detail="Swap usage crossed the warning threshold.",
                    evidence={
                        "swap_usage_percent": swap_usage,
                        "swap_total_bytes": swap_total,
                        "swap_free_bytes": system_state.swap_free_bytes,
                    },
                )
            )

    def _evaluate_disk(
        self,
        system_state: GuardianSystemCollectorState,
        reasons: list[GuardianEvaluationReason],
    ) -> None:
        disk_usage = system_state.disk_usage_percent
        disk_free = system_state.disk_free_bytes
        if disk_usage is None:
            reasons.append(
                GuardianEvaluationReason(
                    code="system_disk_unavailable",
                    summary="Disk usage could not be read.",
                    severity=GuardianSeverity.WARN,
                    source=GuardianSignalSource.SYSTEM,
                    detail="The collector did not provide a disk usage sample.",
                    evidence={"disk_mountpoint": system_state.disk_mountpoint},
                )
            )
            return

        if disk_usage >= self._t.disk.usage_critical_percent or (
            disk_free is not None and disk_free <= self._t.disk.free_critical_bytes
        ):
            reasons.append(
                GuardianEvaluationReason(
                    code="system_disk_critical",
                    summary="Disk usage is critical.",
                    severity=GuardianSeverity.CRITICAL,
                    source=GuardianSignalSource.SYSTEM,
                    detail="Free disk space crossed the critical threshold.",
                    evidence={
                        "disk_mountpoint": system_state.disk_mountpoint,
                        "disk_usage_percent": disk_usage,
                        "disk_free_bytes": disk_free,
                        "disk_total_bytes": system_state.disk_total_bytes,
                    },
                )
            )
        elif disk_usage >= self._t.disk.usage_warn_percent or (
            disk_free is not None and disk_free <= self._t.disk.free_warn_bytes
        ):
            reasons.append(
                GuardianEvaluationReason(
                    code="system_disk_warn",
                    summary="Disk usage is elevated.",
                    severity=GuardianSeverity.WARN,
                    source=GuardianSignalSource.SYSTEM,
                    detail="Free disk space crossed the warning threshold.",
                    evidence={
                        "disk_mountpoint": system_state.disk_mountpoint,
                        "disk_usage_percent": disk_usage,
                        "disk_free_bytes": disk_free,
                        "disk_total_bytes": system_state.disk_total_bytes,
                    },
                )
            )

    def _evaluate_temperature(
        self,
        system_state: GuardianSystemCollectorState,
        reasons: list[GuardianEvaluationReason],
    ) -> None:
        temperature = system_state.temperature_c
        if temperature is None:
            reasons.append(
                GuardianEvaluationReason(
                    code="system_temperature_unavailable",
                    summary="Temperature sensor is unavailable.",
                    severity=GuardianSeverity.INFO,
                    source=GuardianSignalSource.SYSTEM,
                    detail="The collector could not read a system temperature sensor.",
                )
            )
            return

        if temperature >= self._t.temperature.critical_c:
            reasons.append(
                GuardianEvaluationReason(
                    code="system_temperature_critical",
                    summary="System temperature is critical.",
                    severity=GuardianSeverity.CRITICAL,
                    source=GuardianSignalSource.SYSTEM,
                    detail="Temperature crossed the critical threshold.",
                    evidence={
                        "temperature_c": temperature,
                        "temperature_source": system_state.temperature_source,
                    },
                )
            )
        elif temperature >= self._t.temperature.warn_c:
            reasons.append(
                GuardianEvaluationReason(
                    code="system_temperature_warn",
                    summary="System temperature is elevated.",
                    severity=GuardianSeverity.WARN,
                    source=GuardianSignalSource.SYSTEM,
                    detail="Temperature crossed the warning threshold.",
                    evidence={
                        "temperature_c": temperature,
                        "temperature_source": system_state.temperature_source,
                    },
                )
            )

    def _evaluate_privileges(
        self,
        system_state: GuardianSystemCollectorState,
        reasons: list[GuardianEvaluationReason],
    ) -> None:
        if not system_state.running_as_root:
            reasons.append(
                GuardianEvaluationReason(
                    code="system_not_running_as_root",
                    summary="Guardian is not running as root.",
                    severity=GuardianSeverity.WARN,
                    source=GuardianSignalSource.SYSTEM,
                    detail="Privileged operations and some host checks will remain limited.",
                    evidence={
                        "process_pid": system_state.process_pid,
                        "process_name": system_state.process_name,
                        "hostname": system_state.hostname,
                    },
                )
            )

    def _evaluate_collection_quality(
        self,
        system_state: GuardianSystemCollectorState,
        reasons: list[GuardianEvaluationReason],
    ) -> None:
        missing_core_metrics: list[str] = []
        for key, value in (
            ("cpu_usage_percent", system_state.cpu_usage_percent),
            ("memory_usage_percent", system_state.memory_usage_percent),
            ("disk_usage_percent", system_state.disk_usage_percent),
        ):
            if value is None:
                missing_core_metrics.append(key)

        if missing_core_metrics:
            reasons.append(
                GuardianEvaluationReason(
                    code="system_core_metrics_missing",
                    summary="Some core system metrics are unavailable.",
                    severity=GuardianSeverity.WARN,
                    source=GuardianSignalSource.SYSTEM,
                    detail="The collector did not provide a complete core metric set.",
                    evidence={
                        "missing_core_metrics": missing_core_metrics,
                        "errors": system_state.errors,
                    },
                )
            )

        if system_state.errors:
            reasons.append(
                GuardianEvaluationReason(
                    code="system_collection_errors",
                    summary="System collection reported errors.",
                    severity=GuardianSeverity.WARN,
                    source=GuardianSignalSource.SYSTEM,
                    detail="One or more collection steps failed and were degraded gracefully.",
                    evidence={"errors": system_state.errors},
                )
            )
