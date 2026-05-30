"""Executes whitelisted recovery commands.

The executor never builds a command from free-form input: it maps a declared
:class:`ActionRule` to a fixed argv. systemd restarts go through ``sudo`` (the
matching NOPASSWD rule must exist in ``/etc/sudoers.d/pi-guardian-actions``);
docker restarts use the ``docker`` CLI (the service user is in the docker group).
"""

from __future__ import annotations

import asyncio
import shlex
import subprocess
import time

from guardian.app.actions.models import GuardianActionExecution, GuardianActionKind
from guardian.app.config.models import ActionRule


class GuardianActionExecutor:
    def __init__(self, *, timeout_seconds: int = 30) -> None:
        self._timeout = timeout_seconds

    def build_command(self, rule: ActionRule) -> list[str]:
        if rule.kind == GuardianActionKind.SYSTEMD_RESTART:
            return ["sudo", "-n", "systemctl", "restart", rule.target]
        if rule.kind == GuardianActionKind.DOCKER_RESTART:
            return ["docker", "restart", rule.target]
        raise ValueError(f"unsupported action kind: {rule.kind}")

    async def execute(self, rule: ActionRule) -> GuardianActionExecution:
        argv = self.build_command(rule)
        return await asyncio.to_thread(self._run, argv)

    def _run(self, argv: list[str]) -> GuardianActionExecution:
        command = shlex.join(argv)
        start = time.monotonic()
        try:
            result = subprocess.run(
                argv,
                capture_output=True,
                text=True,
                timeout=self._timeout,
                check=False,
            )
        except FileNotFoundError as exc:
            return GuardianActionExecution(executed=False, success=False, command=command, error=str(exc))
        except subprocess.TimeoutExpired as exc:
            duration_ms = int((time.monotonic() - start) * 1000)
            return GuardianActionExecution(
                executed=True,
                success=False,
                command=command,
                duration_ms=duration_ms,
                error=f"timeout nach {exc.timeout}s",
            )

        duration_ms = int((time.monotonic() - start) * 1000)
        return GuardianActionExecution(
            executed=True,
            success=result.returncode == 0,
            exit_code=result.returncode,
            duration_ms=duration_ms,
            command=command,
            stdout=(result.stdout or "").strip()[:2000],
            stderr=(result.stderr or "").strip()[:2000],
            error=None if result.returncode == 0 else (result.stderr or "").strip()[:500] or f"exit {result.returncode}",
        )
