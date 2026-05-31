from __future__ import annotations

from guardian.app.core.domain import GuardianSeverity
from guardian.app.systemd import (
    GuardianSystemdCollectorState,
    GuardianSystemdUnitState,
    SystemdEvaluator,
)


def _unit(name: str, active_state: str, *, whitelisted: bool = True, expected_active: bool = True, **kw) -> GuardianSystemdUnitState:
    return GuardianSystemdUnitState(
        name=name,
        whitelisted=whitelisted,
        expected_active=expected_active,
        active_state=active_state,
        sub_state=kw.get("sub_state", "running" if active_state == "active" else "dead"),
        load_state=kw.get("load_state", "loaded"),
        unit_file_state=kw.get("unit_file_state", "enabled"),
    )


def _state(*units: GuardianSystemdUnitState, available: bool = True) -> GuardianSystemdCollectorState:
    return GuardianSystemdCollectorState(available=available, units=list(units))


def test_all_active_is_ok():
    state = _state(_unit("nginx", "active"), _unit("docker", "active"))
    result = SystemdEvaluator().evaluate(state)
    assert result.status == GuardianSeverity.OK
    assert any(r.code == "systemd_state_healthy" for r in result.reasons)


def test_failed_whitelisted_is_critical():
    state = _state(_unit("nginx", "active"), _unit("kids-controller", "failed"))
    result = SystemdEvaluator().evaluate(state)
    assert result.status == GuardianSeverity.CRITICAL
    assert any(r.code == "systemd_kids_controller_failed" for r in result.reasons)


def test_inactive_whitelisted_is_critical():
    state = _state(_unit("pi-guardian-router", "inactive"))
    result = SystemdEvaluator().evaluate(state)
    assert result.status == GuardianSeverity.CRITICAL
    assert any(r.code == "systemd_pi_guardian_router_inactive" for r in result.reasons)


def test_not_loaded_is_critical():
    state = _state(_unit("nginx", "inactive", load_state="not-found"))
    result = SystemdEvaluator().evaluate(state)
    assert result.status == GuardianSeverity.CRITICAL
    assert any(r.code == "systemd_nginx_not_loaded" for r in result.reasons)


def test_activating_is_warn():
    state = _state(_unit("docker", "activating"))
    result = SystemdEvaluator().evaluate(state)
    assert result.status == GuardianSeverity.WARN
    assert any(r.code == "systemd_docker_transitional" for r in result.reasons)


def test_discovered_failed_observed_only_by_default():
    discovered = _unit("foo", "failed", whitelisted=False, expected_active=False)
    state = _state(_unit("nginx", "active"), discovered)
    result = SystemdEvaluator(discovery_alert=False).evaluate(state)
    assert result.status == GuardianSeverity.OK  # INFO does not escalate
    assert any(r.code == "systemd_discovered_foo_failed" for r in result.reasons)


def test_discovered_failed_warns_when_enabled():
    discovered = _unit("foo", "failed", whitelisted=False, expected_active=False)
    state = _state(_unit("nginx", "active"), discovered)
    result = SystemdEvaluator(discovery_alert=True).evaluate(state)
    assert result.status == GuardianSeverity.WARN


def test_unavailable_systemd_is_info():
    result = SystemdEvaluator().evaluate(_state(available=False))
    assert result.status == GuardianSeverity.OK
    assert any(r.code == "systemd_unavailable" for r in result.reasons)
