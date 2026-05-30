from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from guardian.app.actions import GuardianActionEngine, GuardianActionExecutor, GuardianActionRegistry
from guardian.app.api import actions_router, report_router
from guardian.app.auth import GuardianAuthConfig, GuardianAuthGuard
from guardian.app.config.models import ActionRule, ActionsConfig
from guardian.app.reporting import GuardianReportService
from guardian.app.storage import GuardianSQLiteStore, GuardianStorageConfig


def _build_app(tmp_path, *, require_api_key: bool):
    store = GuardianSQLiteStore(GuardianStorageConfig(path=str(tmp_path / "g.sqlite3")))
    config = ActionsConfig(
        enabled=True,
        dry_run=True,
        allow=[ActionRule(id="restart-ollama", kind="docker_restart", target="ollama")],
    )
    registry = GuardianActionRegistry(config)
    engine = GuardianActionEngine(
        registry=registry,
        executor=GuardianActionExecutor(),
        store=store,
    )

    app = FastAPI()
    app.include_router(actions_router)
    app.include_router(report_router)
    app.state.guardian_store = store
    app.state.action_registry = registry
    app.state.action_engine = engine
    app.state.report_service = GuardianReportService(store=store, telegram_client=None)
    app.state.auth_guard = GuardianAuthGuard(
        GuardianAuthConfig(
            require_api_key=require_api_key,
            api_key="secret",
            allowed_ip="",
            cookie_name="pi_guardian_api_key",
        )
    )
    return app


def test_actions_list_is_open(tmp_path):
    client = TestClient(_build_app(tmp_path, require_api_key=False))
    resp = client.get("/actions")
    assert resp.status_code == 200
    body = resp.json()
    assert body["dry_run"] is True
    assert [r["id"] for r in body["whitelist"]] == ["restart-ollama"]


def test_execute_dry_run_open_when_auth_disabled(tmp_path):
    client = TestClient(_build_app(tmp_path, require_api_key=False))
    resp = client.post("/actions/execute", json={"action_id": "restart-ollama"})
    assert resp.status_code == 200
    assert resp.json()["outcome"] == "dry_run"


def test_execute_requires_key_when_enabled(tmp_path):
    client = TestClient(_build_app(tmp_path, require_api_key=True))
    assert client.post("/actions/execute", json={"action_id": "restart-ollama"}).status_code == 401
    assert client.post(
        "/actions/execute", json={"action_id": "restart-ollama"}, headers={"x-api-key": "wrong"}
    ).status_code == 403
    ok = client.post(
        "/actions/execute", json={"action_id": "restart-ollama"}, headers={"x-api-key": "secret"}
    )
    assert ok.status_code == 200
    assert ok.json()["outcome"] == "dry_run"


def test_report_requires_key_when_enabled(tmp_path):
    client = TestClient(_build_app(tmp_path, require_api_key=True))
    assert client.get("/report").status_code == 401
    assert client.get("/report", headers={"x-api-key": "secret"}).status_code == 200
