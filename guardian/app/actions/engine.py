"""Recovery action engine.

Turns a critical Guardian state into at most one restart per affected target,
guarded by cooldown and a rate limit, honouring a global dry-run switch. Every
decision (executed, dry-run, suppressed, failed) is persisted to ``action_events``.

There are two entry points:
- :meth:`consider` — automatic path, driven by the policy ACTION_CANDIDATE signal.
- :meth:`execute_by_id` — manual path for the API / router (still whitelist-gated).
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from guardian.app.actions.executor import GuardianActionExecutor
from guardian.app.actions.models import (
    GuardianActionDecision,
    GuardianActionKind,
    GuardianActionOutcome,
    GuardianActionReport,
)
from guardian.app.actions.registry import GuardianActionRegistry
from guardian.app.config.models import ActionRule
from guardian.app.core.domain import GuardianSeverity
from guardian.app.policy.models import GuardianPolicyDecision, GuardianPolicyOutcome
from guardian.app.storage import GuardianActionInput, GuardianActionRecord, GuardianSQLiteStore

if TYPE_CHECKING:
    from guardian.app.evaluators.overview import GuardianStatusResponse

logger = logging.getLogger("guardian.actions")

# Outcomes that count as an actual attempt for cooldown / rate-limit accounting.
_ATTEMPT_OUTCOMES = {
    GuardianActionOutcome.EXECUTED.value,
    GuardianActionOutcome.FAILED.value,
    GuardianActionOutcome.DRY_RUN.value,
}


class GuardianActionEngine:
    def __init__(
        self,
        *,
        registry: GuardianActionRegistry,
        executor: GuardianActionExecutor,
        store: GuardianSQLiteStore,
    ) -> None:
        self._registry = registry
        self._executor = executor
        self._store = store

    async def consider(
        self,
        response: GuardianStatusResponse,
        policy: GuardianPolicyDecision,
    ) -> GuardianActionReport:
        report = GuardianActionReport(
            actions_enabled=self._registry.enabled,
            dry_run=self._registry.dry_run,
        )

        if not self._registry.enabled:
            report.summary = "Recovery-Aktionen sind deaktiviert."
            return report

        is_candidate = (
            policy.outcome == GuardianPolicyOutcome.ACTION_CANDIDATE or policy.candidate_action
        )
        if not is_candidate:
            report.summary = "Kein Action-Kandidat (Policy)."
            return report

        report.considered = True
        snapshot_id = policy.snapshot_id

        candidates = self._critical_targets(response)
        if not candidates:
            report.summary = "Kritischer Zustand, aber kein passendes Whitelist-Target."
            return report

        for kind, target, trigger in candidates:
            rule = self._registry.find(kind, target)
            if rule is None:
                continue
            decision = await self._decide_and_run(
                rule, trigger=trigger, snapshot_id=snapshot_id, source="policy"
            )
            report.decisions.append(decision)

        executed = [d for d in report.decisions if d.outcome == GuardianActionOutcome.EXECUTED]
        if report.decisions:
            report.summary = (
                f"{len(report.decisions)} Aktion(en) erwogen, {len(executed)} ausgefuehrt"
                f"{' (dry-run)' if self._registry.dry_run else ''}."
            )
        else:
            report.summary = "Kritischer Zustand, aber kein passendes Whitelist-Target."
        return report

    async def execute_by_id(self, action_id: str, *, source: str = "manual") -> GuardianActionDecision:
        rule = self._registry.get(action_id)
        if rule is None:
            return GuardianActionDecision(
                action_id=action_id,
                kind=GuardianActionKind.SYSTEMD_RESTART,
                target="",
                outcome=GuardianActionOutcome.NOT_WHITELISTED,
                dry_run=self._registry.dry_run,
                trigger="manual",
                source=source,
                error="Action-ID ist nicht in der Whitelist.",
            )
        if not self._registry.enabled:
            decision = GuardianActionDecision(
                action_id=rule.id,
                kind=GuardianActionKind(rule.kind),
                target=rule.target,
                outcome=GuardianActionOutcome.DISABLED,
                dry_run=self._registry.dry_run,
                trigger="manual",
                source=source,
                error="Recovery-Aktionen sind deaktiviert.",
            )
            await self._persist(decision)
            return decision
        return await self._decide_and_run(rule, trigger="manual", snapshot_id=None, source=source)

    async def _decide_and_run(
        self,
        rule: ActionRule,
        *,
        trigger: str,
        snapshot_id: int | None,
        source: str,
    ) -> GuardianActionDecision:
        cfg = self._registry.config
        now = datetime.now(UTC)

        # Rate limit: too many attempts within the window.
        window_since = (now - timedelta(seconds=cfg.window_seconds)).isoformat().replace("+00:00", "Z")
        window_attempts = await self._attempts(rule.id, window_since)
        if len(window_attempts) >= cfg.max_attempts_per_window:
            decision = self._decision(
                rule, GuardianActionOutcome.SUPPRESSED_RATE_LIMIT, trigger, snapshot_id, source,
                error=f"Rate-Limit erreicht ({cfg.max_attempts_per_window}/{cfg.window_seconds}s).",
            )
            await self._persist(decision)
            return decision

        # Cooldown: a recent attempt blocks a new one.
        cooldown_since = (now - timedelta(seconds=cfg.cooldown_seconds)).isoformat().replace("+00:00", "Z")
        cooldown_attempts = await self._attempts(rule.id, cooldown_since)
        if cooldown_attempts:
            last = cooldown_attempts[0].created_at
            remaining = cfg.cooldown_seconds - int((now - last).total_seconds())
            decision = self._decision(
                rule, GuardianActionOutcome.SUPPRESSED_COOLDOWN, trigger, snapshot_id, source,
                cooldown_remaining_seconds=max(remaining, 0),
                error=f"Cooldown aktiv ({max(remaining, 0)}s verbleibend).",
            )
            await self._persist(decision)
            return decision

        command = " ".join(self._executor.build_command(rule))

        if cfg.dry_run:
            decision = self._decision(
                rule, GuardianActionOutcome.DRY_RUN, trigger, snapshot_id, source, command=command,
            )
            logger.info("Recovery (dry-run): %s -> %s", rule.id, command)
            await self._persist(decision)
            return decision

        logger.warning("Recovery-Aktion wird ausgefuehrt: %s -> %s", rule.id, command)
        execution = await self._executor.execute(rule)
        outcome = GuardianActionOutcome.EXECUTED if execution.success else GuardianActionOutcome.FAILED
        decision = self._decision(
            rule, outcome, trigger, snapshot_id, source,
            command=execution.command,
            executed=execution.executed,
            success=execution.success,
            exit_code=execution.exit_code,
            duration_ms=execution.duration_ms,
            error=execution.error,
        )
        await self._persist(decision)
        return decision

    def _critical_targets(self, response: GuardianStatusResponse) -> list[tuple[str, str, str]]:
        """Return (kind, target, trigger_code) for each critical, actionable signal."""

        targets: list[tuple[str, str, str]] = []
        seen: set[tuple[str, str]] = set()

        def add(kind: str, target: str, trigger: str) -> None:
            key = (kind, target)
            if target and key not in seen:
                seen.add(key)
                targets.append((kind, target, trigger))

        if response.systemd_evaluation is not None:
            for reason in response.systemd_evaluation.reasons:
                if reason.severity == GuardianSeverity.CRITICAL:
                    name = str(reason.evidence.get("name", "")) if reason.evidence else ""
                    add(GuardianActionKind.SYSTEMD_RESTART.value, name, reason.code)

        if response.docker_evaluation is not None:
            for reason in response.docker_evaluation.reasons:
                if reason.severity == GuardianSeverity.CRITICAL:
                    name = str(reason.evidence.get("name", "")) if reason.evidence else ""
                    add(GuardianActionKind.DOCKER_RESTART.value, name, reason.code)

        # Router unreachable/critical: recover the live systemd router service.
        if response.router_evaluation is not None and response.router_evaluation.status == GuardianSeverity.CRITICAL:
            add(GuardianActionKind.SYSTEMD_RESTART.value, "pi-guardian-router", "router_critical")

        return targets

    async def _attempts(self, action_id: str, since_iso: str) -> list[GuardianActionRecord]:
        records = await self._store.list_actions_for_id(action_id, since_iso)
        return [r for r in records if r.outcome in _ATTEMPT_OUTCOMES]

    def _decision(
        self,
        rule: ActionRule,
        outcome: GuardianActionOutcome,
        trigger: str,
        snapshot_id: int | None,
        source: str,
        *,
        command: str = "",
        executed: bool = False,
        success: bool = False,
        exit_code: int | None = None,
        duration_ms: int | None = None,
        cooldown_remaining_seconds: int | None = None,
        error: str | None = None,
    ) -> GuardianActionDecision:
        return GuardianActionDecision(
            action_id=rule.id,
            kind=GuardianActionKind(rule.kind),
            target=rule.target,
            outcome=outcome,
            dry_run=self._registry.dry_run,
            trigger=trigger,
            trigger_snapshot_id=snapshot_id,
            executed=executed,
            success=success,
            exit_code=exit_code,
            duration_ms=duration_ms,
            command=command,
            cooldown_remaining_seconds=cooldown_remaining_seconds,
            error=error,
            source=source,
        )

    async def _persist(self, decision: GuardianActionDecision) -> None:
        try:
            await self._store.record_action(
                GuardianActionInput(
                    created_at=decision.created_at,
                    action_id=decision.action_id,
                    kind=decision.kind.value,
                    target=decision.target,
                    outcome=decision.outcome.value,
                    dry_run=decision.dry_run,
                    trigger=decision.trigger,
                    trigger_snapshot_id=decision.trigger_snapshot_id,
                    executed=decision.executed,
                    success=decision.success,
                    exit_code=decision.exit_code,
                    duration_ms=decision.duration_ms,
                    command=decision.command,
                    error=decision.error,
                    source=decision.source,
                    evidence={"cooldown_remaining_seconds": decision.cooldown_remaining_seconds},
                )
            )
        except Exception:  # noqa: BLE001 - persistence must not break the cycle
            logger.exception("Action-Event konnte nicht persistiert werden: %s", decision.action_id)
