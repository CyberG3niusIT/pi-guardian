"""Collect Docker container states for the Guardian watchdog.

Adapts ``router/app/tools/docker_status_tool.py`` (``docker ps`` + ``docker
inspect``). Whitelisted containers are inspected for authoritative state,
health and restart count; discovered containers are read from ``docker ps -a``
only. All subprocess work runs in a worker thread.
"""

from __future__ import annotations

import asyncio
import json
import re
import shutil
import subprocess

from guardian.app.docker.models import GuardianDockerContainerState, GuardianDockerCollectorState

_HEALTH_RE = re.compile(r"\((healthy|unhealthy|health: starting)\)")


def _health_from_status(status_text: str) -> str:
    match = _HEALTH_RE.search(status_text or "")
    if not match:
        return "none"
    value = match.group(1)
    return "starting" if value == "health: starting" else value


class DockerCollector:
    """Inspects whitelisted containers and discovers the rest."""

    def __init__(self, *, watched_containers: list[str], discover: bool = True, timeout_seconds: float = 10.0) -> None:
        self._watched = list(dict.fromkeys(watched_containers))
        self._discover = discover
        self._timeout = timeout_seconds

    async def collect(self) -> GuardianDockerCollectorState:
        return await asyncio.to_thread(self._collect_sync)

    def _collect_sync(self) -> GuardianDockerCollectorState:
        if shutil.which("docker") is None:
            return GuardianDockerCollectorState(
                available=False,
                notes=["docker ist auf diesem Host nicht verfuegbar."],
            )

        errors: list[str] = []
        try:
            raw = self._run(["ps", "-a", "--no-trunc", "--format", "{{json .}}"])
        except Exception as exc:  # noqa: BLE001 - degrade gracefully
            return GuardianDockerCollectorState(
                available=False,
                errors=[f"docker ps: {exc}"],
                notes=["docker ps konnte nicht ausgefuehrt werden."],
            )

        by_name: dict[str, dict[str, str]] = {}
        for line in raw.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            try:
                payload = json.loads(stripped)
            except json.JSONDecodeError:
                continue
            name = payload.get("Names", "")
            if name:
                by_name[name] = payload

        watched_set = set(self._watched)
        containers: list[GuardianDockerContainerState] = []

        for name in self._watched:
            payload = by_name.get(name)
            if payload is None:
                containers.append(
                    GuardianDockerContainerState(
                        name=name,
                        whitelisted=True,
                        expected_running=True,
                        present=False,
                        state="missing",
                    )
                )
                continue
            containers.append(self._build(name, payload, whitelisted=True, expected_running=True, inspect=True, errors=errors))

        if self._discover:
            for name, payload in by_name.items():
                if name in watched_set:
                    continue
                containers.append(
                    self._build(name, payload, whitelisted=False, expected_running=False, inspect=False, errors=errors)
                )

        return GuardianDockerCollectorState(containers=containers, errors=errors)

    def _build(
        self,
        name: str,
        payload: dict[str, str],
        *,
        whitelisted: bool,
        expected_running: bool,
        inspect: bool,
        errors: list[str],
    ) -> GuardianDockerContainerState:
        state = (payload.get("State", "") or "unknown").lower()
        status_text = payload.get("Status", "") or ""
        image = payload.get("Image", "") or ""
        health = _health_from_status(status_text)
        restart_count: int | None = None

        if inspect:
            try:
                detail = self._run(
                    [
                        "inspect",
                        "--format",
                        "{{.State.Status}}|{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}|{{.RestartCount}}",
                        name,
                    ]
                ).strip()
                parts = detail.split("|")
                if len(parts) == 3:
                    state = (parts[0] or state).lower()
                    health = parts[1] or health
                    try:
                        restart_count = int(parts[2])
                    except ValueError:
                        restart_count = None
            except Exception as exc:  # noqa: BLE001 - inspect is best-effort
                errors.append(f"{name} inspect: {exc}")

        return GuardianDockerContainerState(
            name=name,
            whitelisted=whitelisted,
            expected_running=expected_running,
            present=True,
            state=state,
            status_text=status_text,
            health=health,
            restart_count=restart_count,
            image=image,
        )

    def _run(self, args: list[str]) -> str:
        result = subprocess.run(
            ["docker", *args],
            capture_output=True,
            text=True,
            timeout=self._timeout,
            check=True,
        )
        return result.stdout
