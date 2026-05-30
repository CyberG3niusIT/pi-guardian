from __future__ import annotations

import asyncio
import contextlib
import os
import socket
import time
from pathlib import Path

from guardian.app.system.models import GuardianSystemCollectorState


class SystemCollector:
    """Collects a minimal, root-compatible snapshot of the local host."""

    def __init__(self, mountpoint: str = "/") -> None:
        self._mountpoint = mountpoint

    async def collect(self) -> GuardianSystemCollectorState:
        return await asyncio.to_thread(self._collect_sync)

    def _collect_sync(self) -> GuardianSystemCollectorState:
        notes: list[str] = []
        errors: list[str] = []

        hostname = socket.gethostname()
        process_pid = os.getpid()
        process_name = self._read_process_name()
        running_as_root = bool(getattr(os, "geteuid", lambda: -1)() == 0)
        if not running_as_root:
            notes.append("Guardian is not running as root; privileged operations will be limited.")

        try:
            cpu_usage_percent = self._read_cpu_usage_percent()
        except Exception as exc:  # pragma: no cover - defensive fallback
            cpu_usage_percent = None
            errors.append(f"cpu usage read failed: {exc}")

        try:
            load_avg = os.getloadavg()
            load_avg_1m, load_avg_5m, load_avg_15m = map(float, load_avg)
        except Exception:
            load_avg_1m = load_avg_5m = load_avg_15m = None
            notes.append("System load average is unavailable.")

        cpu_count = os.cpu_count()
        cpu_load_ratio_1m = (load_avg_1m / cpu_count) if load_avg_1m is not None and cpu_count else None

        try:
            memory_total_bytes, memory_available_bytes, memory_used_bytes, memory_usage_percent = self._read_memory()
        except Exception as exc:  # pragma: no cover - defensive fallback
            memory_total_bytes = memory_available_bytes = memory_used_bytes = None
            memory_usage_percent = None
            errors.append(f"memory read failed: {exc}")

        try:
            swap_total_bytes, swap_free_bytes, swap_used_bytes, swap_usage_percent = self._read_swap()
        except Exception as exc:  # pragma: no cover - defensive fallback
            swap_total_bytes = swap_free_bytes = swap_used_bytes = None
            swap_usage_percent = None
            errors.append(f"swap read failed: {exc}")

        try:
            (
                disk_total_bytes,
                disk_free_bytes,
                disk_used_bytes,
                disk_usage_percent,
            ) = self._read_disk_usage(self._mountpoint)
        except Exception as exc:  # pragma: no cover - defensive fallback
            disk_total_bytes = disk_free_bytes = disk_used_bytes = None
            disk_usage_percent = None
            errors.append(f"disk read failed for {self._mountpoint}: {exc}")

        try:
            temperature_c, temperature_source = self._read_temperature()
            if temperature_c is None:
                notes.append("System temperature sensor is unavailable.")
        except Exception as exc:  # pragma: no cover - defensive fallback
            temperature_c = None
            temperature_source = None
            errors.append(f"temperature read failed: {exc}")

        try:
            process_uptime_seconds = self._read_process_uptime_seconds()
        except Exception as exc:  # pragma: no cover - defensive fallback
            process_uptime_seconds = None
            errors.append(f"process uptime read failed: {exc}")

        return GuardianSystemCollectorState(
            hostname=hostname,
            running_as_root=running_as_root,
            process_pid=process_pid,
            process_name=process_name,
            process_uptime_seconds=process_uptime_seconds,
            cpu_count=cpu_count,
            cpu_usage_percent=cpu_usage_percent,
            load_avg_1m=load_avg_1m,
            load_avg_5m=load_avg_5m,
            load_avg_15m=load_avg_15m,
            cpu_load_ratio_1m=cpu_load_ratio_1m,
            memory_total_bytes=memory_total_bytes,
            memory_available_bytes=memory_available_bytes,
            memory_used_bytes=memory_used_bytes,
            memory_usage_percent=memory_usage_percent,
            swap_total_bytes=swap_total_bytes,
            swap_free_bytes=swap_free_bytes,
            swap_used_bytes=swap_used_bytes,
            swap_usage_percent=swap_usage_percent,
            disk_mountpoint=self._mountpoint,
            disk_total_bytes=disk_total_bytes,
            disk_free_bytes=disk_free_bytes,
            disk_used_bytes=disk_used_bytes,
            disk_usage_percent=disk_usage_percent,
            temperature_c=temperature_c,
            temperature_source=temperature_source,
            notes=notes,
            errors=errors,
        )

    def _read_process_name(self) -> str:
        for path in (Path("/proc/self/comm"),):
            with contextlib.suppress(Exception):
                return path.read_text(encoding="utf-8").strip() or "python"
        return "python"

    def _read_cpu_usage_percent(self) -> float | None:
        first_total, first_idle = self._read_cpu_times()
        time.sleep(0.1)
        second_total, second_idle = self._read_cpu_times()
        total_delta = second_total - first_total
        idle_delta = second_idle - first_idle
        if total_delta <= 0:
            return None
        usage = (1.0 - (idle_delta / total_delta)) * 100.0
        return max(0.0, min(usage, 100.0))

    def _read_cpu_times(self) -> tuple[int, int]:
        first_line = Path("/proc/stat").read_text(encoding="utf-8").splitlines()[0]
        parts = first_line.split()
        values = [int(part) for part in parts[1:]]
        total = sum(values)
        idle = values[3] if len(values) > 3 else 0
        iowait = values[4] if len(values) > 4 else 0
        return total, idle + iowait

    def _read_memory(self) -> tuple[int | None, int | None, int | None, float | None]:
        meminfo: dict[str, int] = {}
        for line in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
            parts = line.split()
            if len(parts) < 2:
                continue
            key = parts[0].rstrip(":")
            value = int(parts[1])
            unit = parts[2] if len(parts) > 2 else ""
            meminfo[key] = value * 1024 if unit.lower() == "kb" else value

        total = meminfo.get("MemTotal")
        available = meminfo.get("MemAvailable", meminfo.get("MemFree"))
        if total is None or available is None:
            return total, available, None, None
        used = max(total - available, 0)
        usage_percent = (used / total) * 100.0 if total else None
        return total, available, used, usage_percent

    def _read_swap(self) -> tuple[int | None, int | None, int | None, float | None]:
        swap: dict[str, int] = {}
        for line in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
            parts = line.split()
            if len(parts) < 2 or parts[0].rstrip(":") not in ("SwapTotal", "SwapFree"):
                continue
            key = parts[0].rstrip(":")
            value = int(parts[1])
            unit = parts[2] if len(parts) > 2 else ""
            swap[key] = value * 1024 if unit.lower() == "kb" else value

        total = swap.get("SwapTotal")
        free = swap.get("SwapFree")
        if total is None or free is None:
            return total, free, None, None
        if total == 0:
            return 0, 0, 0, 0.0
        used = max(total - free, 0)
        usage_percent = (used / total) * 100.0
        return total, free, used, usage_percent

    def _read_disk_usage(self, mountpoint: str) -> tuple[int | None, int | None, int | None, float | None]:
        stat = os.statvfs(mountpoint)
        total = stat.f_frsize * stat.f_blocks
        free = stat.f_frsize * stat.f_bavail
        used = max(total - free, 0)
        usage_percent = (used / total) * 100.0 if total else None
        return total, free, used, usage_percent

    def _read_temperature(self) -> tuple[float | None, str | None]:
        candidates = (
            Path("/sys/class/thermal/thermal_zone0/temp"),
            Path("/sys/devices/virtual/thermal/thermal_zone0/temp"),
        )
        for path in candidates:
            if not path.exists():
                continue
            raw = path.read_text(encoding="utf-8").strip()
            if not raw:
                continue
            value = float(raw)
            if value > 1000.0:
                value = value / 1000.0
            return value, str(path)
        return None, None

    def _read_process_uptime_seconds(self) -> float | None:
        uptime_raw = Path("/proc/uptime").read_text(encoding="utf-8").split()[0]
        uptime_seconds = float(uptime_raw)
        stat_parts = Path("/proc/self/stat").read_text(encoding="utf-8").split()
        if len(stat_parts) < 22:
            return None
        start_ticks = int(stat_parts[21])
        ticks_per_second = os.sysconf(os.sysconf_names["SC_CLK_TCK"])
        process_start_seconds = start_ticks / ticks_per_second
        return max(uptime_seconds - process_start_seconds, 0.0)
