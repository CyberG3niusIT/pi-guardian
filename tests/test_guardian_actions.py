from __future__ import annotations

import asyncio

from guardian.app.actions import GuardianActionEngine, GuardianActionRegistry
from guardian.app.actions.models import GuardianActionExecution, GuardianActionOutcome
from guardian.app.config.models import ActionRule, ActionsConfig
from guardian.app.core.domain import GuardianSeverity
from guardian.app.core.evaluation import GuardianEvaluationReason
from guardian.app.core.domain import GuardianSignalSource
from guardian.app.docker.evaluator import GuardianDockerEvaluation
from guardian.app.docker.models import GuardianDockerCollectorState
from guardian.app.policy.models import GuardianPolicyDecision, GuardianPolicyOutcome
from guardian.app.storage import GuardianSQLiteStore, GuardianStorageConfig


class RecordingExecutor:
    """Executor stub: records calls, never runs a real command."""

    def __init__(self, *, success: bool = True) -> None:
        self.calls: list[str] = []
        self._success = success

    def build_command(self, rule: ActionRule) -> list[str]:
        if rule.kind == "systemd_restart":
            return ["sudo", "-n", "systemctl", "restart", rule.target]
        return ["docker", "restart", rule.target]

    async def execute(self, rule: ActionRule) -> GuardianActionExecution:
        self.calls.append(rule.id)
        return GuardianActionExecution(
            executed=True,
            success=self._success,
            exit_code=0 if self._success else 1,
            command=" ".join(self.build_command(rule)),
            error=None if self._success else "boom",
        )


def _store(tmp_path) -> GuardianSQLiteStore:
    return GuardianSQLiteStore(GuardianStorageConfig(path=str(tmp_path / "g.sqlite3")))


def _config(*, dry_run: bool, enabled: bool = True, cooldown: int = 600, max_attempts: int = 2) -> ActionsConfig:
    return ActionsConfig(
        enabled=enabled,
        dry_run=dry_run,
        cooldown_seconds=cooldown,
        max_attempts_per_window=max_attempts,
        window_seconds=3600,
        allow=[
            ActionRule(id="restart-ollama", kind="docker_restart", target="ollama"),
            ActionRule(id="restart-router-service", kind="systemd_restart", target="pi-guardian-router"),
        ],
    )


def _docker_critical_response():
    reason = GuardianEvaluationReason(
        code="docker_ollama_stopped",
        summary="stopped",
        severity=GuardianSeverity.CRITICAL,
        source=GuardianSignalSource.CONTAINER,
        evidence={"name": "ollama"},
    )
    docker_eval = GuardianDockerEvaluation(
        status=GuardianSeverity.CRITICAL,
        summary="crit",
        reasons=[reason],
        docker=GuardianDockerCollectorState(),
    )

    class _Resp:
        systemd_evaluation = None
        docker_evaluation = docker_eval

        class router_evaluation:  # noqa: N801 - simple stub holder
            status = GuardianSeverity.OK

    return _Resp()


def _policy(snapshot_id: int = 1) -> GuardianPolicyDecision:
    return GuardianPolicyDecision(
        outcome=GuardianPolicyOutcome.ACTION_CANDIDATE,
        relevance=GuardianSeverity.CRITICAL,
        summary="crit",
        candidate_action=True,
        current_status=GuardianSeverity.CRITICAL,
        snapshot_id=snapshot_id,
    )


def _engine(tmp_path, executor, config):
    return GuardianActionEngine(
        registry=GuardianActionRegistry(config),
        executor=executor,
        store=_store(tmp_path),
    )


def test_dry_run_does_not_execute(tmp_path):
    executor = RecordingExecutor()
    engine = _engine(tmp_path, executor, _config(dry_run=True))
    report = asyncio.run(engine.consider(_docker_critical_response(), _policy()))
    assert report.considered is True
    assert executor.calls == []
    assert any(d.outcome == GuardianActionOutcome.DRY_RUN for d in report.decisions)


def test_armed_executes_real_command(tmp_path):
    executor = RecordingExecutor()
    engine = _engine(tmp_path, executor, _config(dry_run=False))
    report = asyncio.run(engine.consider(_docker_critical_response(), _policy()))
    assert executor.calls == ["restart-ollama"]
    assert any(d.outcome == GuardianActionOutcome.EXECUTED for d in report.decisions)


def test_cooldown_suppresses_second_attempt(tmp_path):
    executor = RecordingExecutor()
    engine = _engine(tmp_path, executor, _config(dry_run=False, cooldown=600))
    asyncio.run(engine.consider(_docker_critical_response(), _policy()))
    report2 = asyncio.run(engine.consider(_docker_critical_response(), _policy()))
    assert executor.calls == ["restart-ollama"]  # only the first ran
    assert any(d.outcome == GuardianActionOutcome.SUPPRESSED_COOLDOWN for d in report2.decisions)


def test_rate_limit_suppresses(tmp_path):
    executor = RecordingExecutor()
    # cooldown 0 so only the rate limit governs; max 2 attempts per window
    engine = _engine(tmp_path, executor, _config(dry_run=False, cooldown=0, max_attempts=2))
    asyncio.run(engine.consider(_docker_critical_response(), _policy()))
    asyncio.run(engine.consider(_docker_critical_response(), _policy()))
    report3 = asyncio.run(engine.consider(_docker_critical_response(), _policy()))
    assert len(executor.calls) == 2
    assert any(d.outcome == GuardianActionOutcome.SUPPRESSED_RATE_LIMIT for d in report3.decisions)


def test_disabled_does_nothing(tmp_path):
    executor = RecordingExecutor()
    engine = _engine(tmp_path, executor, _config(dry_run=False, enabled=False))
    report = asyncio.run(engine.consider(_docker_critical_response(), _policy()))
    assert report.considered is False
    assert executor.calls == []


def test_manual_unknown_id_is_rejected(tmp_path):
    executor = RecordingExecutor()
    engine = _engine(tmp_path, executor, _config(dry_run=False))
    decision = asyncio.run(engine.execute_by_id("does-not-exist"))
    assert decision.outcome == GuardianActionOutcome.NOT_WHITELISTED
    assert executor.calls == []


def test_manual_execute_runs_whitelisted(tmp_path):
    executor = RecordingExecutor()
    engine = _engine(tmp_path, executor, _config(dry_run=False))
    decision = asyncio.run(engine.execute_by_id("restart-ollama"))
    assert decision.outcome == GuardianActionOutcome.EXECUTED
    assert executor.calls == ["restart-ollama"]
