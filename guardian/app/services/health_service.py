from __future__ import annotations

import asyncio

from guardian.app.actions import GuardianActionEngine
from guardian.app.alerting import GuardianAlertingService
from guardian.app.collectors import RouterCollector
from guardian.app.docker import DockerCollector, DockerEvaluator
from guardian.app.evaluators import GuardianOverviewEvaluator, GuardianStatusResponse, RouterEvaluator
from guardian.app.policy import GuardianPolicyEvaluator
from guardian.app.storage import GuardianSQLiteStore, GuardianSnapshotInput
from guardian.app.system import SystemCollector, SystemEvaluator
from guardian.app.systemd import SystemdCollector, SystemdEvaluator


class GuardianHealthService:
    """Coordinates one Guardian read-evaluate-persist-policy cycle."""

    def __init__(
        self,
        *,
        router_collector: RouterCollector,
        router_evaluator: RouterEvaluator,
        system_collector: SystemCollector,
        system_evaluator: SystemEvaluator,
        overview_evaluator: GuardianOverviewEvaluator,
        policy_evaluator: GuardianPolicyEvaluator,
        alerting_service: GuardianAlertingService | None = None,
        store: GuardianSQLiteStore,
        systemd_collector: SystemdCollector | None = None,
        systemd_evaluator: SystemdEvaluator | None = None,
        docker_collector: DockerCollector | None = None,
        docker_evaluator: DockerEvaluator | None = None,
        action_engine: GuardianActionEngine | None = None,
    ) -> None:
        self._router_collector = router_collector
        self._router_evaluator = router_evaluator
        self._system_collector = system_collector
        self._system_evaluator = system_evaluator
        self._overview_evaluator = overview_evaluator
        self._policy_evaluator = policy_evaluator
        self._alerting_service = alerting_service
        self._store = store
        self._systemd_collector = systemd_collector
        self._systemd_evaluator = systemd_evaluator
        self._docker_collector = docker_collector
        self._docker_evaluator = docker_evaluator
        self._action_engine = action_engine

    async def run(self, started_component: str, started_version: str) -> GuardianStatusResponse:
        systemd_enabled = self._systemd_collector is not None and self._systemd_evaluator is not None
        docker_enabled = self._docker_collector is not None and self._docker_evaluator is not None

        tasks = [self._router_collector.collect(), self._system_collector.collect()]
        if systemd_enabled:
            tasks.append(self._systemd_collector.collect())
        if docker_enabled:
            tasks.append(self._docker_collector.collect())

        results = await asyncio.gather(*tasks)
        router_state = results[0]
        system_state = results[1]
        index = 2
        systemd_state = results[index] if systemd_enabled else None
        index += 1 if systemd_enabled else 0
        docker_state = results[index] if docker_enabled else None

        router_evaluation = self._router_evaluator.evaluate(router_state)
        system_evaluation = self._system_evaluator.evaluate(system_state)
        systemd_evaluation = self._systemd_evaluator.evaluate(systemd_state) if systemd_enabled else None
        docker_evaluation = self._docker_evaluator.evaluate(docker_state) if docker_enabled else None

        overview = self._overview_evaluator.evaluate(
            router_evaluation,
            system_evaluation,
            systemd_evaluation,
            docker_evaluation,
        )
        response = GuardianStatusResponse(
            status=overview.status,
            component=started_component,
            version=started_version,
            router=router_state,
            router_evaluation=router_evaluation,
            system=system_state,
            system_evaluation=system_evaluation,
            systemd=systemd_state,
            systemd_evaluation=systemd_evaluation,
            docker=docker_state,
            docker_evaluation=docker_evaluation,
            evaluation=overview,
        )
        persistence = await self._store.record_cycle(self._build_snapshot_input(response))
        policy = await self._policy_evaluator.evaluate(response, persistence, self._store)
        alerting = None
        if self._alerting_service is not None:
            alerting = await self._alerting_service.evaluate_and_dispatch(response, policy, persistence)
        enriched = response.model_copy(
            update={"persistence": persistence, "policy": policy, "alerting": alerting}
        )
        action = None
        if self._action_engine is not None:
            action = await self._action_engine.consider(enriched, policy)
        return enriched.model_copy(update={"action": action})

    def _build_snapshot_input(self, response: GuardianStatusResponse) -> GuardianSnapshotInput:
        router_state = response.router
        system_state = response.system
        return GuardianSnapshotInput(
            checked_at=response.checked_at,
            guardian_status=response.status,
            router_status=response.router_evaluation.status,
            system_status=response.system_evaluation.status,
            overview_summary=response.evaluation.summary,
            router_summary=response.router_evaluation.summary,
            system_summary=response.system_evaluation.summary,
            overview_reason_codes=[reason.code for reason in response.evaluation.reasons],
            router_reason_codes=[reason.code for reason in response.router_evaluation.reasons],
            system_reason_codes=[reason.code for reason in response.system_evaluation.reasons],
            systemd_status=response.systemd_evaluation.status if response.systemd_evaluation else None,
            docker_status=response.docker_evaluation.status if response.docker_evaluation else None,
            systemd_summary=response.systemd_evaluation.summary if response.systemd_evaluation else "",
            docker_summary=response.docker_evaluation.summary if response.docker_evaluation else "",
            systemd_reason_codes=(
                [reason.code for reason in response.systemd_evaluation.reasons]
                if response.systemd_evaluation
                else []
            ),
            docker_reason_codes=(
                [reason.code for reason in response.docker_evaluation.reasons]
                if response.docker_evaluation
                else []
            ),
            router_access_state=router_state.access_state.value,
            router_readiness_state=router_state.readiness_state.value,
            router_reachable=router_state.reachable,
            router_auth_required=router_state.auth_required,
            system_running_as_root=system_state.running_as_root,
            system_cpu_usage_percent=system_state.cpu_usage_percent,
            system_memory_usage_percent=system_state.memory_usage_percent,
            system_disk_usage_percent=system_state.disk_usage_percent,
            system_temperature_c=system_state.temperature_c,
            evidence={
                "router": {
                    "base_url": router_state.base_url,
                    "health_path": router_state.health_path,
                    "status_path": router_state.status_path,
                    "health_status": router_state.health.status if router_state.health else None,
                    "service_active": (
                        router_state.service_status.active if router_state.service_status is not None else None
                    ),
                },
                "system": {
                    "hostname": system_state.hostname,
                    "cpu_count": system_state.cpu_count,
                    "load_avg_1m": system_state.load_avg_1m,
                    "memory_available_bytes": system_state.memory_available_bytes,
                    "disk_mountpoint": system_state.disk_mountpoint,
                    "temperature_source": system_state.temperature_source,
                },
            },
        )
