"""Internal asyncio monitoring loop.

Drives :class:`GuardianHealthService` on a fixed cadence so Guardian observes
continuously instead of only when ``/health`` is polled. The loop is resilient:
a failed cycle is logged and the loop keeps running.
"""

from __future__ import annotations

import asyncio
import logging

from guardian.app.services import GuardianHealthService

logger = logging.getLogger("guardian.scheduler")


class GuardianScheduler:
    """Runs the Guardian evaluation cycle on a recurring interval."""

    def __init__(
        self,
        *,
        health_service: GuardianHealthService,
        interval_seconds: int,
        component: str,
        version: str,
    ) -> None:
        self._health_service = health_service
        self._interval_seconds = max(int(interval_seconds), 5)
        self._component = component
        self._version = version
        self._task: asyncio.Task[None] | None = None
        self._stopping = asyncio.Event()

    def start(self) -> None:
        if self._task is not None and not self._task.done():
            return
        self._stopping.clear()
        self._task = asyncio.create_task(self._run(), name="guardian-monitor-loop")
        logger.info("Guardian-Scheduler gestartet (Intervall %ss).", self._interval_seconds)

    async def stop(self) -> None:
        self._stopping.set()
        if self._task is None:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        finally:
            self._task = None
            logger.info("Guardian-Scheduler gestoppt.")

    async def run_once(self) -> None:
        """Execute a single evaluation cycle (also reused by start-up warmup)."""

        await self._health_service.run(self._component, self._version)

    async def _run(self) -> None:
        # Run an immediate cycle so the first snapshot lands without waiting.
        await self._safe_cycle()
        while not self._stopping.is_set():
            try:
                await asyncio.wait_for(self._stopping.wait(), timeout=self._interval_seconds)
            except asyncio.TimeoutError:
                pass
            if self._stopping.is_set():
                break
            await self._safe_cycle()

    async def _safe_cycle(self) -> None:
        try:
            await self.run_once()
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 - loop must survive any cycle failure
            logger.exception("Guardian-Evaluierungszyklus fehlgeschlagen; Loop laeuft weiter.")
