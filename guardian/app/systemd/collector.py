"""Collect systemd unit states for the Guardian watchdog.

Adapts the inspection approach of ``router/app/tools/service_status_tool.py``
(``systemctl show``) but works over a configurable whitelist plus optional
auto-discovery of failed units. All subprocess work runs in a worker thread.
"""

from __future__ import annotations

import asyncio
import shutil
import subprocess

from guardian.app.systemd.models import GuardianSystemdCollectorState, GuardianSystemdUnitState

_SHOW_PROPERTIES = "ActiveState,SubState,LoadState,UnitFileState,MainPID,Description,ActiveEnterTimestamp,NRestarts"


class SystemdCollector:
    """Inspects whitelisted systemd units and discovers failed ones."""

    def __init__(self, *, watched_units: list[str], discover: bool = True, timeout_seconds: float = 8.0) -> None:
        self._watched = list(dict.fromkeys(watched_units))  # de-dupe, keep order
        self._discover = discover
        self._timeout = timeout_seconds

    async def collect(self) -> GuardianSystemdCollectorState:
        return await asyncio.to_thread(self._collect_sync)

    def _collect_sync(self) -> GuardianSystemdCollectorState:
        if shutil.which("systemctl") is None:
            return GuardianSystemdCollectorState(
                available=False,
                notes=["systemctl ist auf diesem Host nicht verfuegbar."],
            )

        units: list[GuardianSystemdUnitState] = []
        errors: list[str] = []
        seen: set[str] = set()

        for name in self._watched:
            seen.add(name)
            units.append(self._inspect(name, whitelisted=True, expected_active=True, errors=errors))

        if self._discover:
            for name in self._list_failed_units(errors):
                if name in seen:
                    continue
                seen.add(name)
                units.append(self._inspect(name, whitelisted=False, expected_active=False, errors=errors))

        return GuardianSystemdCollectorState(units=units, errors=errors)

    def _inspect(
        self,
        name: str,
        *,
        whitelisted: bool,
        expected_active: bool,
        errors: list[str],
    ) -> GuardianSystemdUnitState:
        try:
            result = subprocess.run(
                ["systemctl", "show", name, f"--property={_SHOW_PROPERTIES}"],
                capture_output=True,
                text=True,
                timeout=self._timeout,
                check=True,
            )
        except subprocess.CalledProcessError as exc:
            detail = (exc.stderr or exc.stdout or "").strip()
            errors.append(f"{name}: {detail or exc}")
            return GuardianSystemdUnitState(
                name=name,
                whitelisted=whitelisted,
                expected_active=expected_active,
                error=detail or str(exc),
            )
        except Exception as exc:  # noqa: BLE001 - degrade gracefully per unit
            errors.append(f"{name}: {exc}")
            return GuardianSystemdUnitState(
                name=name,
                whitelisted=whitelisted,
                expected_active=expected_active,
                error=str(exc),
            )

        props: dict[str, str] = {}
        for line in result.stdout.splitlines():
            key, _, value = line.partition("=")
            if key:
                props[key.strip()] = value.strip()

        try:
            parsed_pid = int(props.get("MainPID", "0"))
        except ValueError:
            parsed_pid = 0

        try:
            restart_count = int(props.get("NRestarts", "")) if props.get("NRestarts") else None
        except ValueError:
            restart_count = None

        active_since = props.get("ActiveEnterTimestamp", "") or None
        if active_since in ("", "n/a"):
            active_since = None

        return GuardianSystemdUnitState(
            name=name,
            whitelisted=whitelisted,
            expected_active=expected_active,
            active_state=props.get("ActiveState", "unknown") or "unknown",
            sub_state=props.get("SubState", "unknown") or "unknown",
            load_state=props.get("LoadState", "unknown") or "unknown",
            unit_file_state=props.get("UnitFileState", "unknown") or "unknown",
            main_pid=parsed_pid if parsed_pid > 0 else None,
            description=props.get("Description", "") or "",
            active_since=active_since,
            restart_count=restart_count,
        )

    def _list_failed_units(self, errors: list[str]) -> list[str]:
        try:
            result = subprocess.run(
                [
                    "systemctl",
                    "list-units",
                    "--type=service",
                    "--state=failed",
                    "--no-legend",
                    "--plain",
                    "--no-pager",
                ],
                capture_output=True,
                text=True,
                timeout=self._timeout,
                check=True,
            )
        except Exception as exc:  # noqa: BLE001 - discovery is best-effort
            errors.append(f"discovery: {exc}")
            return []

        names: list[str] = []
        for line in result.stdout.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            unit = stripped.split()[0]
            if unit.endswith(".service"):
                names.append(unit)
        return names
