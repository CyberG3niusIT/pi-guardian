from __future__ import annotations

import asyncio

from guardian.app.core.domain import GuardianSeverity
from guardian.app.reporting import GuardianReportService
from guardian.app.storage import GuardianSQLiteStore, GuardianSnapshotInput, GuardianStorageConfig


def _store(tmp_path) -> GuardianSQLiteStore:
    return GuardianSQLiteStore(GuardianStorageConfig(path=str(tmp_path / "guardian.sqlite3")))


def _snapshot(**kw) -> GuardianSnapshotInput:
    base = dict(
        guardian_status=GuardianSeverity.WARN,
        router_status=GuardianSeverity.OK,
        system_status=GuardianSeverity.WARN,
        overview_summary="needs attention",
        router_summary="ok",
        system_summary="warn",
        router_access_state="reachable",
        router_readiness_state="healthy",
        router_reachable=True,
        router_auth_required=False,
        system_running_as_root=False,
        systemd_status=GuardianSeverity.OK,
        docker_status=GuardianSeverity.CRITICAL,
        system_reason_codes=["system_not_running_as_root"],
        docker_reason_codes=["docker_ollama_stopped"],
    )
    base.update(kw)
    return GuardianSnapshotInput(**base)


def test_report_without_data(tmp_path):
    service = GuardianReportService(store=_store(tmp_path))
    report = asyncio.run(service.build_report())
    assert report.have_data is False
    assert "Noch keine Snapshots" in report.text


def test_report_summarizes_last_snapshot(tmp_path):
    store = _store(tmp_path)
    asyncio.run(store.record_cycle(_snapshot()))
    service = GuardianReportService(store=store)
    report = asyncio.run(service.build_report())

    assert report.have_data is True
    assert report.overall_status == GuardianSeverity.WARN
    assert report.docker_status == GuardianSeverity.CRITICAL
    assert report.systemd_status == GuardianSeverity.OK
    assert "docker_ollama_stopped" in report.text
    assert "PI Guardian" in report.text


def test_generate_and_send_skips_without_telegram(tmp_path):
    store = _store(tmp_path)
    asyncio.run(store.record_cycle(_snapshot()))
    service = GuardianReportService(store=store, telegram_client=None)
    result = asyncio.run(service.generate_and_send(send=True))
    assert result.sent is False
    assert result.send_skipped_reason == "telegram_unconfigured"
