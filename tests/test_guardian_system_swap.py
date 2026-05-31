from __future__ import annotations

from guardian.app.config.models import GuardianThresholds, SwapThresholds
from guardian.app.core.domain import GuardianSeverity
from guardian.app.system import GuardianSystemCollectorState, SystemEvaluator


def _state(**kw) -> GuardianSystemCollectorState:
    base = dict(
        hostname="pi",
        running_as_root=True,  # avoid the not-root WARN so swap is isolated
        process_pid=1,
        process_name="guardian",
        cpu_usage_percent=5.0,
        memory_usage_percent=40.0,
        disk_usage_percent=40.0,
    )
    base.update(kw)
    return GuardianSystemCollectorState(**base)


def test_no_swap_is_ignored():
    result = SystemEvaluator().evaluate(_state(swap_total_bytes=0, swap_usage_percent=0.0))
    assert result.status == GuardianSeverity.OK
    assert not any("swap" in r.code for r in result.reasons)


def test_swap_warn():
    result = SystemEvaluator().evaluate(
        _state(swap_total_bytes=2_000_000_000, swap_usage_percent=70.0)
    )
    assert result.status == GuardianSeverity.WARN
    assert any(r.code == "system_swap_warn" for r in result.reasons)


def test_swap_critical():
    result = SystemEvaluator().evaluate(
        _state(swap_total_bytes=2_000_000_000, swap_usage_percent=95.0)
    )
    assert result.status == GuardianSeverity.CRITICAL
    assert any(r.code == "system_swap_critical" for r in result.reasons)


def test_swap_threshold_is_configurable():
    thresholds = GuardianThresholds(swap=SwapThresholds(usage_warn_percent=20.0, usage_critical_percent=30.0))
    result = SystemEvaluator(thresholds=thresholds).evaluate(
        _state(swap_total_bytes=2_000_000_000, swap_usage_percent=25.0)
    )
    assert result.status == GuardianSeverity.WARN
    assert any(r.code == "system_swap_warn" for r in result.reasons)
