from __future__ import annotations

import re
from datetime import UTC, datetime

from pydantic import BaseModel, Field

from guardian.app.core.domain import GuardianSeverity, GuardianSignalSource
from guardian.app.core.evaluation import GuardianEvaluationReason
from guardian.app.docker.models import GuardianDockerContainerState, GuardianDockerCollectorState

_SLUG = re.compile(r"[^a-z0-9]+")


def _slug(name: str) -> str:
    return _SLUG.sub("_", name.lower()).strip("_")


class GuardianDockerEvaluation(BaseModel):
    status: GuardianSeverity
    summary: str
    checked_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    reasons: list[GuardianEvaluationReason] = Field(default_factory=list)
    docker: GuardianDockerCollectorState


class DockerEvaluator:
    """Deterministically evaluates Docker container states."""

    def __init__(self, *, discovery_alert: bool = False, restart_count_warn: int = 3) -> None:
        self._discovery_alert = discovery_alert
        self._restart_count_warn = restart_count_warn

    def evaluate(self, state: GuardianDockerCollectorState) -> GuardianDockerEvaluation:
        reasons: list[GuardianEvaluationReason] = []

        if not state.available:
            reasons.append(
                GuardianEvaluationReason(
                    code="docker_unavailable",
                    summary="Docker ist nicht verfuegbar.",
                    severity=GuardianSeverity.INFO,
                    source=GuardianSignalSource.CONTAINER,
                    detail="; ".join(state.notes) or "; ".join(state.errors) or None,
                )
            )
            return self._finalize(reasons, state)

        for container in state.containers:
            if container.whitelisted:
                self._evaluate_whitelisted(container, reasons)
            else:
                self._evaluate_discovered(container, reasons)

        return self._finalize(reasons, state)

    def _evaluate_whitelisted(
        self,
        container: GuardianDockerContainerState,
        reasons: list[GuardianEvaluationReason],
    ) -> None:
        slug = _slug(container.name)
        evidence = {
            "name": container.name,
            "state": container.state,
            "health": container.health,
            "restart_count": container.restart_count,
            "status_text": container.status_text,
        }

        if not container.present or container.state == "missing":
            reasons.append(
                GuardianEvaluationReason(
                    code=f"docker_{slug}_missing",
                    summary=f"Container {container.name} existiert nicht.",
                    severity=GuardianSeverity.CRITICAL,
                    source=GuardianSignalSource.CONTAINER,
                    detail="Erwarteter Container wurde nicht gefunden.",
                    evidence=evidence,
                )
            )
            return

        if container.state in ("exited", "dead"):
            reasons.append(
                GuardianEvaluationReason(
                    code=f"docker_{slug}_stopped",
                    summary=f"Container {container.name} ist gestoppt ({container.state}).",
                    severity=GuardianSeverity.CRITICAL,
                    source=GuardianSignalSource.CONTAINER,
                    evidence=evidence,
                )
            )
            return

        if container.state == "restarting":
            reasons.append(
                GuardianEvaluationReason(
                    code=f"docker_{slug}_restarting",
                    summary=f"Container {container.name} startet wiederholt neu.",
                    severity=GuardianSeverity.WARN,
                    source=GuardianSignalSource.CONTAINER,
                    evidence=evidence,
                )
            )
            return

        if container.state == "paused":
            reasons.append(
                GuardianEvaluationReason(
                    code=f"docker_{slug}_paused",
                    summary=f"Container {container.name} ist pausiert.",
                    severity=GuardianSeverity.WARN,
                    source=GuardianSignalSource.CONTAINER,
                    evidence=evidence,
                )
            )
            return

        # state == running (or created/unknown)
        if container.health == "unhealthy":
            reasons.append(
                GuardianEvaluationReason(
                    code=f"docker_{slug}_unhealthy",
                    summary=f"Container {container.name} ist unhealthy.",
                    severity=GuardianSeverity.CRITICAL,
                    source=GuardianSignalSource.CONTAINER,
                    evidence=evidence,
                )
            )
            return

        if container.health == "starting":
            reasons.append(
                GuardianEvaluationReason(
                    code=f"docker_{slug}_health_starting",
                    summary=f"Container {container.name} startet (health: starting).",
                    severity=GuardianSeverity.WARN,
                    source=GuardianSignalSource.CONTAINER,
                    evidence=evidence,
                )
            )
            return

        if container.restart_count is not None and container.restart_count >= self._restart_count_warn:
            reasons.append(
                GuardianEvaluationReason(
                    code=f"docker_{slug}_restart_count",
                    summary=f"Container {container.name} hat {container.restart_count} Restarts.",
                    severity=GuardianSeverity.WARN,
                    source=GuardianSignalSource.CONTAINER,
                    evidence=evidence,
                )
            )

    def _evaluate_discovered(
        self,
        container: GuardianDockerContainerState,
        reasons: list[GuardianEvaluationReason],
    ) -> None:
        if container.state == "running":
            return  # discovered + running: nothing to report

        severity = GuardianSeverity.WARN if self._discovery_alert else GuardianSeverity.INFO
        reasons.append(
            GuardianEvaluationReason(
                code=f"docker_discovered_{_slug(container.name)}_{container.state or 'stopped'}",
                summary=f"Nicht-gewhitelisteter Container {container.name} ist {container.state}.",
                severity=severity,
                source=GuardianSignalSource.CONTAINER,
                detail="Auto-Discovery (nur Beobachtung)." if not self._discovery_alert else None,
                evidence={"name": container.name, "state": container.state},
            )
        )

    def _finalize(
        self,
        reasons: list[GuardianEvaluationReason],
        state: GuardianDockerCollectorState,
    ) -> GuardianDockerEvaluation:
        status = GuardianSeverity.OK
        summary = "Alle ueberwachten Container laufen erwartungsgemaess."

        if any(r.severity == GuardianSeverity.CRITICAL for r in reasons):
            status = GuardianSeverity.CRITICAL
            summary = "Mindestens ein ueberwachter Container ist kritisch."
        elif any(r.severity == GuardianSeverity.WARN for r in reasons):
            status = GuardianSeverity.WARN
            summary = "Mindestens ein ueberwachter Container braucht Aufmerksamkeit."

        if not reasons:
            reasons.append(
                GuardianEvaluationReason(
                    code="docker_state_healthy",
                    summary="Alle ueberwachten Container laufen erwartungsgemaess.",
                    severity=GuardianSeverity.OK,
                    source=GuardianSignalSource.CONTAINER,
                    evidence={"container_count": len(state.containers)},
                )
            )

        return GuardianDockerEvaluation(
            status=status,
            summary=summary,
            reasons=reasons,
            docker=state,
        )
