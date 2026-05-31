"""Aggregate read endpoints for the Guardian Overview dashboard.

Everything here is derived from data Guardian already collects/persists — no
synthetic values. Endpoints: /overview (top status tiles), /policies (active
monitoring features), /events (merged timeline), /incidents (non-OK periods).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Request

from guardian.app.core.domain import GuardianSeverity

router = APIRouter(tags=["dashboard"])


def _count_healthy(items, predicate) -> tuple[int, int]:
    monitored = [i for i in items if getattr(i, "whitelisted", True)]
    healthy = sum(1 for i in monitored if predicate(i))
    return healthy, len(monitored)


@router.get("/overview")
async def overview(request: Request) -> dict[str, Any]:
    """Compact data for the six top status tiles."""

    state = request.app.state
    store = state.guardian_store
    config = state.guardian_config

    snapshot = await store.get_last_snapshot()
    overall = snapshot.guardian_status if snapshot else None

    systemd_state = await state.systemd_collector.collect()
    docker_state = await state.docker_collector.collect()
    units_healthy, units_total = _count_healthy(systemd_state.units, lambda u: u.active_state == "active")
    cont_healthy, cont_total = _count_healthy(
        docker_state.containers, lambda c: c.state == "running" and c.health != "unhealthy"
    )

    telegram_ready, telegram_reason = state.telegram_client.is_ready()
    policies = _policy_list(state)
    active_policies = sum(1 for p in policies if p["active"])

    return {
        "guardian_core": {
            "status": overall.value if overall else "unknown",
            "label": "Healthy" if overall == GuardianSeverity.OK else (overall.value if overall else "unknown"),
        },
        "alert_manager": {
            "operational": telegram_ready,
            "detail": "Telegram-Alerts aktiv" if telegram_ready else telegram_reason,
        },
        "event_store": {
            "online": store.path.exists(),
            "path": store.path.name,
        },
        "policy_layer": {
            "active_policies": active_policies,
            "total_policies": len(policies),
        },
        "docker_monitoring": {"healthy": cont_healthy, "total": cont_total},
        "systemd_monitoring": {"healthy": units_healthy, "total": units_total},
    }


def _policy_list(state) -> list[dict[str, Any]]:
    config = state.guardian_config
    telegram_ready, _ = state.telegram_client.is_ready()
    alerting_enabled = getattr(state.alerting_service, "_config", None)
    alerting_on = bool(alerting_enabled.enabled) if alerting_enabled is not None else False
    actions = config.actions
    return [
        {
            "id": "systemd_monitoring",
            "name": "systemd Monitoring",
            "description": "Ueberwacht systemd-Units und Fehlerzustaende",
            "active": len(config.watch.systemd) > 0,
        },
        {
            "id": "docker_monitoring",
            "name": "Docker Monitoring",
            "description": "Ueberwacht Docker-Container und Restarts",
            "active": len(config.watch.docker) > 0,
        },
        {
            "id": "telegram_alerting",
            "name": "Telegram Alerting",
            "description": "Sendet Alerts via Telegram-Bot",
            "active": alerting_on and telegram_ready,
        },
        {
            "id": "threshold_evaluation",
            "name": "Threshold Evaluation",
            "description": "Bewertet Metriken gegen Schwellenwerte",
            "active": True,
        },
        {
            "id": "alert_deduplication",
            "name": "Alert Deduplication",
            "description": "Verhindert doppelte Alerts im Zeitfenster",
            "active": alerting_on,
        },
        {
            "id": "recovery_throttling",
            "name": "Recovery Throttling",
            "description": "Begrenzt Recovery-Aktionen und Restart-Stuerme",
            "active": actions.enabled,
        },
        {
            "id": "recovery_actions",
            "name": "Recovery Actions",
            "description": "Automatische Restarts" + (" (dry-run)" if actions.dry_run else " (scharf)"),
            "active": actions.enabled,
        },
    ]


@router.get("/policies")
async def policies(request: Request) -> dict[str, Any]:
    return {"policies": _policy_list(request.app.state)}


_SEV_RANK = {"ok": 0, "info": 1, "warn": 2, "critical": 3}


@router.get("/events")
async def events(request: Request, limit: int = 20) -> dict[str, Any]:
    """Merged, normalized event timeline (transitions + alerts + actions)."""

    store = request.app.state.guardian_store
    safe = max(int(limit), 1)
    transitions = await store.list_transitions(limit=safe)
    alerts = await store.list_alerts(limit=safe)
    actions = await store.list_actions(limit=safe)

    items: list[dict[str, Any]] = []
    for t in transitions:
        items.append({
            "time": t.created_at.isoformat(),
            "type": "state_change",
            "severity": t.to_status.value,
            "title": f"Status {t.from_status.value} → {t.to_status.value}",
            "detail": t.summary,
            "source": "guardian",
        })
    for a in alerts.items:
        if not a.sent:
            continue
        items.append({
            "time": a.checked_at.isoformat(),
            "type": "alert",
            "severity": a.current_status.value,
            "title": a.summary or f"Alert: {a.alert_kind}",
            "detail": a.alert_kind,
            "source": "alerting",
        })
    for ac in actions.items:
        sev = "critical" if ac.outcome == "failed" else ("warn" if ac.executed else "info")
        items.append({
            "time": ac.created_at.isoformat(),
            "type": "action",
            "severity": sev,
            "title": f"{ac.action_id} → {ac.target} ({ac.outcome})",
            "detail": ac.command or ac.error or "",
            "source": "actions",
        })

    items.sort(key=lambda x: x["time"], reverse=True)
    return {"events": items[:safe], "count": min(len(items), safe)}


@router.get("/incidents")
async def incidents(request: Request, limit: int = 50) -> dict[str, Any]:
    """Incidents derived from non-OK periods in the status transition history."""

    store = request.app.state.guardian_store
    transitions = await store.list_transitions(limit=max(int(limit) * 4, 40))
    # transitions come newest-first; process oldest-first to pair enter/leave.
    ordered = list(reversed(transitions))

    incidents: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for t in ordered:
        to = t.to_status.value
        if to != "ok":
            if current is None:
                current = {
                    "title": t.summary or f"Status {to}",
                    "severity": to,
                    "severity_rank": _SEV_RANK.get(to, 0),
                    "started": t.created_at.isoformat(),
                    "_started_dt": t.created_at,
                    "status": "active",
                    "ended": None,
                    "duration_seconds": None,
                }
            else:
                if _SEV_RANK.get(to, 0) > current["severity_rank"]:
                    current["severity"] = to
                    current["severity_rank"] = _SEV_RANK.get(to, 0)
        else:
            if current is not None:
                current["status"] = "resolved"
                current["ended"] = t.created_at.isoformat()
                current["duration_seconds"] = int((t.created_at - current["_started_dt"]).total_seconds())
                current.pop("_started_dt", None)
                current.pop("severity_rank", None)
                incidents.append(current)
                current = None

    if current is not None:
        snapshot = await store.get_last_snapshot()
        if snapshot is not None:
            current["duration_seconds"] = int((snapshot.checked_at - current["_started_dt"]).total_seconds())
        current.pop("_started_dt", None)
        current.pop("severity_rank", None)
        incidents.append(current)

    incidents.reverse()  # newest first
    return {"incidents": incidents[: int(limit)], "count": len(incidents)}
