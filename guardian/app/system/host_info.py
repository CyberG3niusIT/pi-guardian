"""Static-ish host facts for the dashboard device card (read on demand)."""

from __future__ import annotations

import os
import socket
from pathlib import Path


def _read_first_line(path: str) -> str | None:
    try:
        return Path(path).read_text(encoding="utf-8", errors="replace").strip().replace("\x00", "")
    except OSError:
        return None


def _os_pretty_name() -> str | None:
    try:
        for line in Path("/etc/os-release").read_text(encoding="utf-8").splitlines():
            if line.startswith("PRETTY_NAME="):
                return line.split("=", 1)[1].strip().strip('"')
    except OSError:
        pass
    return None


def _primary_ip() -> str | None:
    # No traffic is sent; this just selects the kernel's default-route source IP.
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("192.168.50.245", 1))
        return sock.getsockname()[0]
    except OSError:
        return None
    finally:
        sock.close()


def collect_host_info() -> dict[str, object]:
    uptime_seconds: float | None = None
    line = _read_first_line("/proc/uptime")
    if line:
        try:
            uptime_seconds = float(line.split()[0])
        except (ValueError, IndexError):
            uptime_seconds = None

    try:
        load1, load5, load15 = os.getloadavg()
    except OSError:
        load1 = load5 = load15 = None

    temperature_c: float | None = None
    for candidate in ("/sys/class/thermal/thermal_zone0/temp",):
        raw = _read_first_line(candidate)
        if raw:
            try:
                val = float(raw)
                temperature_c = val / 1000.0 if val > 1000 else val
            except ValueError:
                temperature_c = None
            break

    uname = os.uname()
    return {
        "hostname": socket.gethostname(),
        "ip": _primary_ip(),
        "model": _read_first_line("/proc/device-tree/model") or _read_first_line("/sys/firmware/devicetree/base/model"),
        "os": _os_pretty_name(),
        "kernel": uname.release,
        "arch": uname.machine,
        "cpu_count": os.cpu_count(),
        "uptime_seconds": uptime_seconds,
        "load_avg_1m": load1,
        "load_avg_5m": load5,
        "load_avg_15m": load15,
        "cpu_temperature_c": temperature_c,
    }
