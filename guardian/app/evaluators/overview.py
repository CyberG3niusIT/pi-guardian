from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field

from guardian.app.actions.models import GuardianActionReport
from guardian.app.collectors.router_collector import GuardianRouterCollectorState
from guardian.app.alerting.models import GuardianAlertDecision
from guardian.app.core.domain import GuardianSeverity, GuardianSignalSource
from guardian.app.docker.evaluator import GuardianDockerEvaluation
from guardian.app.docker.models import GuardianDockerCollectorState
from guardian.app.evaluators.common import GuardianEvaluationReason
from guardian.app.evaluators.router_evaluator import GuardianRouterEvaluation
from guardian.app.storage.models import GuardianPersistenceReceipt
from guardian.app.system.evaluator import GuardianSystemEvaluation
from guardian.app.system.models import GuardianSystemCollectorState
from guardian.app.systemd.evaluator import GuardianSystemdEvaluation
from guardian.app.systemd.models import GuardianSystemdCollectorState
from guardian.app.policy.models import GuardianPolicyDecision


class GuardianOverviewEvaluation(BaseModel):
    status: GuardianSeverity
    summary: str
    checked_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    reasons: list[GuardianEvaluationReason] = Field(default_factory=list)
    router: GuardianRouterEvaluation
    system: GuardianSystemEvaluation
    systemd: GuardianSystemdEvaluation | None = None
    docker: GuardianDockerEvaluation | None = None


class GuardianStatusResponse(BaseModel):
    status: GuardianSeverity
    component: str = "guardian"
    version: str = "0.1.0"
    checked_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    router: GuardianRouterCollectorState
    router_evaluation: GuardianRouterEvaluation
    system: GuardianSystemCollectorState
    system_evaluation: GuardianSystemEvaluation
    systemd: GuardianSystemdCollectorState | None = None
    systemd_evaluation: GuardianSystemdEvaluation | None = None
    docker: GuardianDockerCollectorState | None = None
    docker_evaluation: GuardianDockerEvaluation | None = None
    evaluation: GuardianOverviewEvaluation
    persistence: GuardianPersistenceReceipt | None = None
    policy: GuardianPolicyDecision | None = None
    alerting: GuardianAlertDecision | None = None
    action: GuardianActionReport | None = None


class GuardianOverviewEvaluator:
    """Combines router and system evaluations into a single Guardian view."""

    def evaluate(
        self,
        router_evaluation: GuardianRouterEvaluation,
        system_evaluation: GuardianSystemEvaluation,
        systemd_evaluation: GuardianSystemdEvaluation | None = None,
        docker_evaluation: GuardianDockerEvaluation | None = None,
    ) -> GuardianOverviewEvaluation:
        reasons: list[GuardianEvaluationReason] = []

        # (domain code, source, evaluation) for each present subsystem.
        domains: list[tuple[str, GuardianSignalSource, object]] = [
            ("router", GuardianSignalSource.ROUTER, router_evaluation),
            ("system", GuardianSignalSource.SYSTEM, system_evaluation),
        ]
        if systemd_evaluation is not None:
            domains.append(("systemd", GuardianSignalSource.SERVICE, systemd_evaluation))
        if docker_evaluation is not None:
            domains.append(("docker", GuardianSignalSource.CONTAINER, docker_evaluation))

        severities = [evaluation.status for _, _, evaluation in domains]
        if GuardianSeverity.CRITICAL in severities:
            status = GuardianSeverity.CRITICAL
            summary = "Guardian has a critical condition."
        elif GuardianSeverity.WARN in severities:
            status = GuardianSeverity.WARN
            summary = "Guardian needs attention."
        else:
            status = GuardianSeverity.OK
            summary = "Guardian is healthy."

        for code, source, evaluation in domains:
            if evaluation.status == GuardianSeverity.OK:
                continue
            reasons.append(
                GuardianEvaluationReason(
                    code=f"{code}_{evaluation.status.value}",
                    summary=f"{code} evaluation returned {evaluation.status.value}.",
                    severity=evaluation.status,
                    source=source,
                    detail=evaluation.summary,
                    evidence={
                        "reason_codes": [reason.code for reason in evaluation.reasons],
                        "reason_count": len(evaluation.reasons),
                    },
                )
            )

        if not reasons:
            reasons.append(
                GuardianEvaluationReason(
                    code="guardian_overall_ok",
                    summary="All evaluated subsystems are healthy.",
                    severity=GuardianSeverity.OK,
                    source=GuardianSignalSource.EXTERNAL,
                    evidence={code: evaluation.status for code, _, evaluation in domains},
                )
            )

        return GuardianOverviewEvaluation(
            status=status,
            summary=summary,
            reasons=reasons,
            router=router_evaluation,
            system=system_evaluation,
            systemd=systemd_evaluation,
            docker=docker_evaluation,
        )
