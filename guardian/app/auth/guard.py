"""Lightweight API auth for Guardian.

Mirrors the router's approach (``router/app/router/auth.py``): an API key via
``X-API-Key`` header or cookie, plus an IP allowlist (single IP or CIDR). Unlike
the router there is no client database — Guardian uses a single configured key.

When ``GUARDIAN_REQUIRE_API_KEY`` is false the guard is a no-op, which is the
expected mode when Guardian is only reachable locally / behind nginx.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from ipaddress import ip_address, ip_network

from fastapi import HTTPException, Request


@dataclass(frozen=True, slots=True)
class GuardianAuthConfig:
    require_api_key: bool
    api_key: str
    allowed_ip: str
    cookie_name: str

    @classmethod
    def from_env(cls) -> "GuardianAuthConfig":
        return cls(
            require_api_key=os.getenv("GUARDIAN_REQUIRE_API_KEY", "false").strip().lower() in ("1", "true", "yes"),
            api_key=os.getenv("GUARDIAN_API_KEY", "").strip(),
            allowed_ip=os.getenv("GUARDIAN_ALLOWED_IP", "").strip(),
            cookie_name=os.getenv("GUARDIAN_SESSION_COOKIE_NAME", "pi_guardian_api_key").strip()
            or "pi_guardian_api_key",
        )


def _extract_client_ip(request: Request) -> str:
    peer_host = request.client.host if request.client else "unknown"
    try:
        is_loopback = peer_host != "unknown" and ip_address(peer_host).is_loopback
    except ValueError:
        is_loopback = False
    if peer_host == "unknown" or is_loopback:
        forwarded = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
        if forwarded:
            return forwarded
        real_ip = request.headers.get("x-real-ip", "").strip()
        if real_ip:
            return real_ip
    return peer_host


def _ip_allowed(allowed: str, ip: str) -> bool:
    if not allowed:
        return True
    try:
        if "/" in allowed:
            return ip_address(ip) in ip_network(allowed, strict=False)
        return ip == allowed
    except ValueError:
        return False


class GuardianAuthGuard:
    """FastAPI dependency factory for API-key + IP enforcement."""

    def __init__(self, config: GuardianAuthConfig) -> None:
        self._config = config

    def __call__(self, request: Request) -> None:
        if not self._config.require_api_key:
            return
        if not self._config.api_key:
            # Misconfiguration: required but no key set -> deny rather than open up.
            raise HTTPException(status_code=503, detail="Guardian-API-Key ist nicht konfiguriert.")

        provided = request.headers.get("x-api-key", "").strip()
        if not provided:
            provided = request.cookies.get(self._config.cookie_name, "").strip()
        if not provided:
            raise HTTPException(status_code=401, detail="X-API-Key fehlt.")
        if provided != self._config.api_key:
            raise HTTPException(status_code=403, detail="API-Key ungueltig.")

        client_ip = _extract_client_ip(request)
        if client_ip != "unknown" and not _ip_allowed(self._config.allowed_ip, client_ip):
            raise HTTPException(status_code=403, detail="Client-IP ist nicht erlaubt.")


def require_api(request: Request) -> None:
    """FastAPI dependency that enforces the configured Guardian API auth."""

    guard = getattr(request.app.state, "auth_guard", None)
    if guard is None:
        guard = GuardianAuthGuard(GuardianAuthConfig.from_env())
        request.app.state.auth_guard = guard
    guard(request)
