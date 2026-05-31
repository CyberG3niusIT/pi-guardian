"""Read-only Guardian status API.

These endpoints derive from live collectors (no persistence side effects) or the
last persisted snapshot, so they are cheap to poll from a dashboard.
"""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from guardian.app.docker import DockerCollector, DockerEvaluator
from guardian.app.storage import GuardianSnapshotRecord
from guardian.app.system import SystemCollector, SystemEvaluator
from guardian.app.system.host_info import collect_host_info
from guardian.app.systemd import SystemdCollector, SystemdEvaluator

router = APIRouter(tags=["status"])


@router.get("/system/info")
async def system_info() -> dict[str, Any]:
    """Host facts (model/OS/kernel/uptime/IP) for the dashboard device card."""

    return await asyncio.to_thread(collect_host_info)


@router.get("/status", response_model=GuardianSnapshotRecord)
async def status(request: Request) -> GuardianSnapshotRecord:
    """Latest persisted Guardian snapshot (written by the monitoring loop)."""

    store = request.app.state.guardian_store
    snapshot = await store.get_last_snapshot()
    if snapshot is None:
        raise HTTPException(status_code=503, detail="Noch kein Snapshot vorhanden.")
    return snapshot


@router.get("/metrics")
async def metrics(request: Request) -> dict[str, Any]:
    """Live system metrics + evaluation, without persisting a snapshot."""

    collector: SystemCollector = request.app.state.system_collector
    evaluator: SystemEvaluator = request.app.state.system_evaluator
    state = await collector.collect()
    evaluation = evaluator.evaluate(state)
    return {"status": evaluation.status, "summary": evaluation.summary, "system": state, "evaluation": evaluation}


@router.get("/metrics/history")
async def metrics_history(request: Request, limit: int = 120) -> dict[str, Any]:
    """Time series of persisted system metrics for sparklines (oldest -> newest)."""

    store = request.app.state.guardian_store
    points = await store.list_metric_points(limit=limit)
    temps = [p["temperature"] for p in points if p["temperature"] is not None]
    return {
        "points": points,
        "count": len(points),
        "temperature_min": min(temps) if temps else None,
        "temperature_max": max(temps) if temps else None,
    }


@router.get("/services")
async def services(request: Request) -> dict[str, Any]:
    """Live systemd unit states + evaluation."""

    collector: SystemdCollector | None = getattr(request.app.state, "systemd_collector", None)
    evaluator: SystemdEvaluator | None = getattr(request.app.state, "systemd_evaluator", None)
    if collector is None or evaluator is None:
        raise HTTPException(status_code=503, detail="systemd-Ueberwachung ist nicht aktiv.")
    state = await collector.collect()
    evaluation = evaluator.evaluate(state)
    return {"status": evaluation.status, "summary": evaluation.summary, "evaluation": evaluation}


@router.get("/containers")
async def containers(request: Request) -> dict[str, Any]:
    """Live Docker container states + evaluation."""

    collector: DockerCollector | None = getattr(request.app.state, "docker_collector", None)
    evaluator: DockerEvaluator | None = getattr(request.app.state, "docker_evaluator", None)
    if collector is None or evaluator is None:
        raise HTTPException(status_code=503, detail="Docker-Ueberwachung ist nicht aktiv.")
    state = await collector.collect()
    evaluation = evaluator.evaluate(state)
    return {"status": evaluation.status, "summary": evaluation.summary, "evaluation": evaluation}


@router.get("/config")
async def config(request: Request) -> dict[str, Any]:
    """Effective Guardian operational configuration (no secrets)."""

    guardian_config = request.app.state.guardian_config
    return guardian_config.model_dump()
