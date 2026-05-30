from __future__ import annotations

from guardian.app.core.domain import GuardianSeverity
from guardian.app.docker import (
    DockerEvaluator,
    GuardianDockerCollectorState,
    GuardianDockerContainerState,
)


def _container(
    name: str,
    state: str,
    *,
    whitelisted: bool = True,
    expected_running: bool = True,
    present: bool = True,
    health: str = "none",
    restart_count: int | None = 0,
) -> GuardianDockerContainerState:
    return GuardianDockerContainerState(
        name=name,
        whitelisted=whitelisted,
        expected_running=expected_running,
        present=present,
        state=state,
        health=health,
        restart_count=restart_count,
    )


def _state(*containers: GuardianDockerContainerState, available: bool = True) -> GuardianDockerCollectorState:
    return GuardianDockerCollectorState(available=available, containers=list(containers))


def test_running_healthy_is_ok():
    result = DockerEvaluator().evaluate(_state(_container("ollama", "running", health="healthy")))
    assert result.status == GuardianSeverity.OK
    assert any(r.code == "docker_state_healthy" for r in result.reasons)


def test_exited_is_critical():
    result = DockerEvaluator().evaluate(_state(_container("ollama", "exited")))
    assert result.status == GuardianSeverity.CRITICAL
    assert any(r.code == "docker_ollama_stopped" for r in result.reasons)


def test_missing_is_critical():
    result = DockerEvaluator().evaluate(_state(_container("ollama", "missing", present=False)))
    assert result.status == GuardianSeverity.CRITICAL
    assert any(r.code == "docker_ollama_missing" for r in result.reasons)


def test_unhealthy_is_critical():
    result = DockerEvaluator().evaluate(_state(_container("pihole", "running", health="unhealthy")))
    assert result.status == GuardianSeverity.CRITICAL
    assert any(r.code == "docker_pihole_unhealthy" for r in result.reasons)


def test_health_starting_is_warn():
    result = DockerEvaluator().evaluate(_state(_container("pihole", "running", health="starting")))
    assert result.status == GuardianSeverity.WARN
    assert any(r.code == "docker_pihole_health_starting" for r in result.reasons)


def test_high_restart_count_is_warn():
    result = DockerEvaluator(restart_count_warn=3).evaluate(
        _state(_container("ollama", "running", restart_count=5))
    )
    assert result.status == GuardianSeverity.WARN
    assert any(r.code == "docker_ollama_restart_count" for r in result.reasons)


def test_restarting_is_warn():
    result = DockerEvaluator().evaluate(_state(_container("ollama", "restarting")))
    assert result.status == GuardianSeverity.WARN
    assert any(r.code == "docker_ollama_restarting" for r in result.reasons)


def test_discovered_stopped_observed_only_by_default():
    discovered = _container("scratch", "exited", whitelisted=False, expected_running=False)
    result = DockerEvaluator(discovery_alert=False).evaluate(
        _state(_container("ollama", "running"), discovered)
    )
    assert result.status == GuardianSeverity.OK
    assert any(r.code.startswith("docker_discovered_scratch") for r in result.reasons)


def test_discovered_stopped_warns_when_enabled():
    discovered = _container("scratch", "exited", whitelisted=False, expected_running=False)
    result = DockerEvaluator(discovery_alert=True).evaluate(
        _state(_container("ollama", "running"), discovered)
    )
    assert result.status == GuardianSeverity.WARN


def test_discovered_running_is_silent():
    discovered = _container("scratch", "running", whitelisted=False, expected_running=False)
    result = DockerEvaluator().evaluate(_state(_container("ollama", "running"), discovered))
    assert result.status == GuardianSeverity.OK
    assert not any("scratch" in r.code for r in result.reasons)
