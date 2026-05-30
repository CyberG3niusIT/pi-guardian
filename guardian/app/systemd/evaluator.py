from __future__ import annotations

import re
from datetime import UTC, datetime

from pydantic import BaseModel, Field

from guardian.app.core.domain import GuardianSeverity, GuardianSignalSource
from guardian.app.core.evaluation import GuardianEvaluationReason
from guardian.app.systemd.models import GuardianSystemdCollectorState, GuardianSystemdUnitState

_SLUG = re.compile(r"[^a-z0-9]+")


def _slug(name: str) -> str:
    return _SLUG.sub("_", name.lower()).strip("_")


class GuardianSystemdEvaluation(BaseModel):
    status: GuardianSeverity
    summary: str
    checked_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    reasons: list[GuardianEvaluationReason] = Field(default_factory=list)
    systemd: GuardianSystemdCollectorState


class SystemdEvaluator:
    """Deterministically evaluates systemd unit states."""

    def __init__(self, *, discovery_alert: bool = False) -> None:
        self._discovery_alert = discovery_alert

    def evaluate(self, state: GuardianSystemdCollectorState) -> GuardianSystemdEvaluation:
        reasons: list[GuardianEvaluationReason] = []

        if not state.available:
            reasons.append(
                GuardianEvaluationReason(
                    code="systemd_unavailable",
                    summary="systemd ist nicht verfuegbar.",
                    severity=GuardianSeverity.INFO,
                    source=GuardianSignalSource.SERVICE,
                    detail="; ".join(state.notes) or None,
                )
            )
            return self._finalize(reasons, state)

        for unit in state.units:
            if unit.whitelisted:
                self._evaluate_whitelisted(unit, reasons)
            else:
                self._evaluate_discovered(unit, reasons)

        return self._finalize(reasons, state)

    def _evaluate_whitelisted(
        self,
        unit: GuardianSystemdUnitState,
        reasons: list[GuardianEvaluationReason],
    ) -> None:
        slug = _slug(unit.name)
        evidence = {
            "name": unit.name,
            "active_state": unit.active_state,
            "sub_state": unit.sub_state,
            "load_state": unit.load_state,
            "main_pid": unit.main_pid,
        }

        if unit.error is not None:
            reasons.append(
                GuardianEvaluationReason(
                    code=f"systemd_{slug}_unavailable",
                    summary=f"systemd-Dienst {unit.name} konnte nicht gelesen werden.",
                    severity=GuardianSeverity.WARN,
                    source=GuardianSignalSource.SERVICE,
                    detail=unit.error,
                    evidence=evidence,
                )
            )
            return

        if unit.load_state in ("not-found", "masked", "error"):
            reasons.append(
                GuardianEvaluationReason(
                    code=f"systemd_{slug}_not_loaded",
                    summary=f"systemd-Dienst {unit.name} ist nicht geladen ({unit.load_state}).",
                    severity=GuardianSeverity.CRITICAL,
                    source=GuardianSignalSource.SERVICE,
                    evidence=evidence,
                )
            )
            return

        if unit.active_state == "active":
            return  # healthy, no reason emitted

        if unit.active_state == "failed":
            reasons.append(
                GuardianEvaluationReason(
                    code=f"systemd_{slug}_failed",
                    summary=f"systemd-Dienst {unit.name} ist fehlgeschlagen.",
                    severity=GuardianSeverity.CRITICAL,
                    source=GuardianSignalSource.SERVICE,
                    detail=f"sub_state={unit.sub_state}",
                    evidence=evidence,
                )
            )
        elif unit.active_state in ("inactive", "deactivating"):
            reasons.append(
                GuardianEvaluationReason(
                    code=f"systemd_{slug}_inactive",
                    summary=f"systemd-Dienst {unit.name} ist nicht aktiv ({unit.active_state}).",
                    severity=GuardianSeverity.CRITICAL,
                    source=GuardianSignalSource.SERVICE,
                    detail="Dienst wird als aktiv erwartet.",
                    evidence=evidence,
                )
            )
        else:  # activating, reloading, unknown
            reasons.append(
                GuardianEvaluationReason(
                    code=f"systemd_{slug}_transitional",
                    summary=f"systemd-Dienst {unit.name} ist im Uebergang ({unit.active_state}).",
                    severity=GuardianSeverity.WARN,
                    source=GuardianSignalSource.SERVICE,
                    evidence=evidence,
                )
            )

    def _evaluate_discovered(
        self,
        unit: GuardianSystemdUnitState,
        reasons: list[GuardianEvaluationReason],
    ) -> None:
        # Discovered units come from the failed-units scan; observe (or warn if enabled).
        severity = GuardianSeverity.WARN if self._discovery_alert else GuardianSeverity.INFO
        reasons.append(
            GuardianEvaluationReason(
                code=f"systemd_discovered_{_slug(unit.name)}_failed",
                summary=f"Nicht-gewhitelisteter Dienst {unit.name} ist fehlgeschlagen.",
                severity=severity,
                source=GuardianSignalSource.SERVICE,
                detail="Auto-Discovery (nur Beobachtung)." if not self._discovery_alert else None,
                evidence={"name": unit.name, "active_state": unit.active_state},
            )
        )

    def _finalize(
        self,
        reasons: list[GuardianEvaluationReason],
        state: GuardianSystemdCollectorState,
    ) -> GuardianSystemdEvaluation:
        status = GuardianSeverity.OK
        summary = "Alle ueberwachten systemd-Dienste sind aktiv."

        if any(r.severity == GuardianSeverity.CRITICAL for r in reasons):
            status = GuardianSeverity.CRITICAL
            summary = "Mindestens ein ueberwachter systemd-Dienst ist kritisch."
        elif any(r.severity == GuardianSeverity.WARN for r in reasons):
            status = GuardianSeverity.WARN
            summary = "Mindestens ein ueberwachter systemd-Dienst braucht Aufmerksamkeit."

        if not reasons:
            reasons.append(
                GuardianEvaluationReason(
                    code="systemd_state_healthy",
                    summary="Alle ueberwachten systemd-Dienste sind aktiv.",
                    severity=GuardianSeverity.OK,
                    source=GuardianSignalSource.SERVICE,
                    evidence={"unit_count": len(state.units)},
                )
            )

        return GuardianSystemdEvaluation(
            status=status,
            summary=summary,
            reasons=reasons,
            systemd=state,
        )
