"""Periodic Guardian status report.

Aggregates the most recent persisted snapshot plus recent transitions and alert
events into a compact summary and (optionally) sends it via Telegram. Designed
to be invoked every few hours by a systemd timer, independent of the HTTP API.
"""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field

from guardian.app.alerting import GuardianTelegramClient
from guardian.app.core.domain import GuardianSeverity
from guardian.app.storage import GuardianSQLiteStore


class GuardianReport(BaseModel):
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    have_data: bool = False
    overall_status: GuardianSeverity | None = None
    router_status: GuardianSeverity | None = None
    system_status: GuardianSeverity | None = None
    systemd_status: GuardianSeverity | None = None
    docker_status: GuardianSeverity | None = None
    recent_transition_count: int = 0
    recent_alert_count: int = 0
    recent_sent_alert_count: int = 0
    text: str = ""


class GuardianReportResult(BaseModel):
    report: GuardianReport
    sent: bool = False
    send_skipped_reason: str | None = None
    send_error: str | None = None


_EMOJI = {
    GuardianSeverity.OK: "🟢",
    GuardianSeverity.INFO: "🔵",
    GuardianSeverity.WARN: "🟡",
    GuardianSeverity.CRITICAL: "🔴",
}


def _badge(status: GuardianSeverity | None) -> str:
    if status is None:
        return "⚪ n/a"
    return f"{_EMOJI.get(status, '⚪')} {status.value}"


class GuardianReportService:
    """Builds and optionally dispatches the periodic status report."""

    def __init__(
        self,
        *,
        store: GuardianSQLiteStore,
        telegram_client: GuardianTelegramClient | None = None,
        history_limit: int = 20,
    ) -> None:
        self._store = store
        self._telegram = telegram_client
        self._history_limit = history_limit

    async def build_report(self) -> GuardianReport:
        snapshot = await self._store.get_last_snapshot()
        transitions = await self._store.list_transitions(limit=self._history_limit)
        alerts = await self._store.list_alerts(limit=self._history_limit)

        sent_alerts = [a for a in alerts.items if a.sent]

        if snapshot is None:
            return GuardianReport(
                have_data=False,
                recent_transition_count=len(transitions),
                recent_alert_count=len(alerts.items),
                recent_sent_alert_count=len(sent_alerts),
                text="PI Guardian Bericht\nNoch keine Snapshots vorhanden.",
            )

        lines = [
            "📋 PI Guardian Statusbericht",
            f"Stand: {snapshot.checked_at.strftime('%Y-%m-%d %H:%M:%S UTC')}",
            "",
            f"Gesamt:  {_badge(snapshot.guardian_status)}",
            f"Router:  {_badge(snapshot.router_status)}",
            f"System:  {_badge(snapshot.system_status)}",
            f"Dienste: {_badge(snapshot.systemd_status)}",
            f"Docker:  {_badge(snapshot.docker_status)}",
            "",
            f"Übergänge (letzte {self._history_limit}): {len(transitions)}",
            f"Alerts (letzte {self._history_limit}): {len(alerts.items)} (gesendet: {len(sent_alerts)})",
        ]

        active_codes = [
            code
            for code in (
                list(snapshot.router_reason_codes)
                + list(snapshot.system_reason_codes)
                + list(snapshot.systemd_reason_codes)
                + list(snapshot.docker_reason_codes)
            )
            if not code.endswith("_healthy") and not code.endswith("_ok")
        ]
        if active_codes:
            lines.append("")
            lines.append("Aktive Hinweise:")
            lines.extend(f"• {code}" for code in active_codes[:12])

        return GuardianReport(
            have_data=True,
            overall_status=snapshot.guardian_status,
            router_status=snapshot.router_status,
            system_status=snapshot.system_status,
            systemd_status=snapshot.systemd_status,
            docker_status=snapshot.docker_status,
            recent_transition_count=len(transitions),
            recent_alert_count=len(alerts.items),
            recent_sent_alert_count=len(sent_alerts),
            text="\n".join(lines),
        )

    async def generate_and_send(self, *, send: bool) -> GuardianReportResult:
        report = await self.build_report()
        if not send:
            return GuardianReportResult(report=report, sent=False, send_skipped_reason="send_disabled")
        if self._telegram is None:
            return GuardianReportResult(report=report, sent=False, send_skipped_reason="telegram_unconfigured")

        ready, reason = self._telegram.is_ready()
        if not ready:
            return GuardianReportResult(report=report, sent=False, send_skipped_reason=reason)

        result = await self._telegram.send_message(report.text)
        if result.ok:
            return GuardianReportResult(report=report, sent=True)
        return GuardianReportResult(report=report, sent=False, send_error=result.error)
