from __future__ import annotations

import asyncio
import json
import os
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock

from guardian.app.core.domain import GuardianSeverity
from guardian.app.storage.models import (
    GuardianActionHistory,
    GuardianActionInput,
    GuardianActionRecord,
    GuardianAlertHistory,
    GuardianAlertInput,
    GuardianAlertRecord,
    GuardianPersistenceReceipt,
    GuardianSnapshotHistory,
    GuardianSnapshotInput,
    GuardianSnapshotRecord,
    GuardianStateTransitionRecord,
)


@dataclass(frozen=True, slots=True)
class GuardianStorageConfig:
    path: str

    @classmethod
    def from_env(cls) -> "GuardianStorageConfig":
        path = os.getenv("GUARDIAN_STORAGE_PATH", "guardian/data/guardian.sqlite3").strip()
        if not path:
            path = "guardian/data/guardian.sqlite3"
        return cls(path=path)


class GuardianSQLiteStore:
    """Small SQLite store for Guardian snapshots and status transitions."""

    def __init__(self, config: GuardianStorageConfig) -> None:
        self._config = config
        self._lock = Lock()
        self._path = Path(config.path)
        self._init_error: str | None = None
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._ensure_schema()
        except Exception as exc:  # pragma: no cover - startup fallback
            self._init_error = str(exc)

    @property
    def path(self) -> Path:
        return self._path

    async def record_cycle(self, snapshot: GuardianSnapshotInput) -> GuardianPersistenceReceipt:
        return await asyncio.to_thread(self._record_cycle_sync, snapshot)

    async def get_last_snapshot(self) -> GuardianSnapshotRecord | None:
        return await asyncio.to_thread(self._get_last_snapshot_sync)

    async def get_last_status(self) -> GuardianSeverity | None:
        snapshot = await self.get_last_snapshot()
        return snapshot.guardian_status if snapshot is not None else None

    async def list_transitions(self, limit: int = 20) -> list[GuardianStateTransitionRecord]:
        return await asyncio.to_thread(self._list_transitions_sync, limit)

    async def list_snapshots(self, limit: int = 20) -> GuardianSnapshotHistory:
        return await asyncio.to_thread(self._list_snapshots_sync, limit)

    async def list_metric_points(self, limit: int = 120) -> list[dict]:
        return await asyncio.to_thread(self._list_metric_points_sync, limit)

    async def record_alert(self, alert: GuardianAlertInput) -> GuardianAlertRecord:
        return await asyncio.to_thread(self._record_alert_sync, alert)

    async def list_alerts(self, limit: int = 20) -> GuardianAlertHistory:
        return await asyncio.to_thread(self._list_alerts_sync, limit)

    async def get_last_alert_for_key(self, alert_key: str) -> GuardianAlertRecord | None:
        return await asyncio.to_thread(self._get_last_alert_for_key_sync, alert_key)

    async def record_action(self, action: GuardianActionInput) -> GuardianActionRecord:
        return await asyncio.to_thread(self._record_action_sync, action)

    async def list_actions(self, limit: int = 20) -> GuardianActionHistory:
        return await asyncio.to_thread(self._list_actions_sync, limit)

    async def list_actions_for_id(self, action_id: str, since_iso: str) -> list[GuardianActionRecord]:
        return await asyncio.to_thread(self._list_actions_for_id_sync, action_id, since_iso)

    def _connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._path, timeout=5.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        return conn

    def _ensure_schema(self) -> None:
        with self._connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS status_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    checked_at TEXT NOT NULL,
                    guardian_status TEXT NOT NULL,
                    router_status TEXT NOT NULL,
                    system_status TEXT NOT NULL,
                    overview_summary TEXT NOT NULL,
                    router_summary TEXT NOT NULL,
                    system_summary TEXT NOT NULL,
                    overview_reason_codes_json TEXT NOT NULL,
                    router_reason_codes_json TEXT NOT NULL,
                    system_reason_codes_json TEXT NOT NULL,
                    router_access_state TEXT NOT NULL,
                    router_readiness_state TEXT NOT NULL,
                    router_reachable INTEGER NOT NULL,
                    router_auth_required INTEGER NOT NULL,
                    system_running_as_root INTEGER NOT NULL,
                    system_cpu_usage_percent REAL,
                    system_memory_usage_percent REAL,
                    system_disk_usage_percent REAL,
                    system_temperature_c REAL,
                    evidence_json TEXT NOT NULL,
                    stored_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS state_transitions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    previous_snapshot_id INTEGER,
                    current_snapshot_id INTEGER NOT NULL,
                    from_status TEXT NOT NULL,
                    to_status TEXT NOT NULL,
                    reason_codes_json TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    evidence_json TEXT NOT NULL,
                    FOREIGN KEY(previous_snapshot_id) REFERENCES status_snapshots(id),
                    FOREIGN KEY(current_snapshot_id) REFERENCES status_snapshots(id)
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_status_snapshots_checked_at ON status_snapshots(checked_at DESC)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_state_transitions_created_at ON state_transitions(created_at DESC)"
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS alert_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    checked_at TEXT NOT NULL,
                    sent_at TEXT,
                    alert_key TEXT NOT NULL,
                    dedupe_key TEXT NOT NULL,
                    alert_kind TEXT NOT NULL,
                    outcome TEXT NOT NULL,
                    should_send INTEGER NOT NULL,
                    sent INTEGER NOT NULL,
                    suppressed_reason TEXT,
                    current_status TEXT NOT NULL,
                    previous_status TEXT,
                    policy_outcome TEXT NOT NULL,
                    changed INTEGER NOT NULL,
                    transition_relevant INTEGER NOT NULL,
                    cooldown_seconds INTEGER NOT NULL,
                    cooldown_remaining_seconds INTEGER,
                    telegram_ready INTEGER NOT NULL,
                    telegram_ready_reason TEXT NOT NULL,
                    telegram_chat_id TEXT,
                    telegram_message_id INTEGER,
                    telegram_error TEXT,
                    reason_codes_json TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    message_text TEXT NOT NULL,
                    evidence_json TEXT NOT NULL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_alert_events_checked_at ON alert_events(checked_at DESC)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_alert_events_key ON alert_events(alert_key, checked_at DESC)"
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS action_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    action_id TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    target TEXT NOT NULL,
                    outcome TEXT NOT NULL,
                    dry_run INTEGER NOT NULL,
                    trigger TEXT NOT NULL,
                    trigger_snapshot_id INTEGER,
                    executed INTEGER NOT NULL,
                    success INTEGER NOT NULL,
                    exit_code INTEGER,
                    duration_ms INTEGER,
                    command TEXT NOT NULL,
                    error TEXT,
                    source TEXT NOT NULL,
                    evidence_json TEXT NOT NULL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_action_events_created_at ON action_events(created_at DESC)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_action_events_action_id ON action_events(action_id, created_at DESC)"
            )
            self._migrate_columns(conn)

    def _migrate_columns(self, conn: sqlite3.Connection) -> None:
        """Additively add newer nullable columns to existing databases."""

        existing = {row["name"] for row in conn.execute("PRAGMA table_info(status_snapshots)").fetchall()}
        additions = {
            "systemd_status": "TEXT",
            "docker_status": "TEXT",
            "systemd_summary": "TEXT",
            "docker_summary": "TEXT",
            "systemd_reason_codes_json": "TEXT",
            "docker_reason_codes_json": "TEXT",
            "system_load_avg_1m": "REAL",
            "system_network_rx_bps": "REAL",
            "system_network_tx_bps": "REAL",
        }
        for column, column_type in additions.items():
            if column not in existing:
                conn.execute(f"ALTER TABLE status_snapshots ADD COLUMN {column} {column_type}")

    def _record_cycle_sync(self, snapshot: GuardianSnapshotInput) -> GuardianPersistenceReceipt:
        if self._init_error is not None:
            return GuardianPersistenceReceipt(
                ok=False,
                database_path=str(self._path),
                error=self._init_error,
            )

        try:
            with self._lock, self._connection() as conn:
                previous = self._load_last_snapshot_row(conn)
                snapshot_id = self._insert_snapshot(conn, snapshot)
                transition_id = None
                changed = False
                previous_status = previous["guardian_status"] if previous is not None else None
                current_status = snapshot.guardian_status

                if previous is not None and previous_status != current_status.value:
                    changed = True
                    transition_id = self._insert_transition(
                        conn,
                        previous_snapshot_id=int(previous["id"]),
                        current_snapshot_id=snapshot_id,
                        from_status=GuardianSeverity(previous_status),
                        to_status=current_status,
                        reason_codes=list(snapshot.overview_reason_codes),
                        summary=f"{previous_status} -> {current_status.value}",
                        evidence={
                            "previous_summary": previous["overview_summary"],
                            "current_summary": snapshot.overview_summary,
                            "previous_checked_at": previous["checked_at"],
                            "current_checked_at": snapshot.checked_at.isoformat(),
                        },
                    )

                return GuardianPersistenceReceipt(
                    ok=True,
                    database_path=str(self._path),
                    snapshot_id=snapshot_id,
                    transition_id=transition_id,
                    changed=changed,
                    previous_status=GuardianSeverity(previous_status) if previous_status is not None else None,
                    current_status=current_status,
                )
        except Exception as exc:  # pragma: no cover - defensive fallback
            return GuardianPersistenceReceipt(
                ok=False,
                database_path=str(self._path),
                error=str(exc),
                current_status=snapshot.guardian_status,
            )

    def _insert_snapshot(self, conn: sqlite3.Connection, snapshot: GuardianSnapshotInput) -> int:
        stored_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        cursor = conn.execute(
            """
            INSERT INTO status_snapshots (
                checked_at,
                guardian_status,
                router_status,
                system_status,
                overview_summary,
                router_summary,
                system_summary,
                overview_reason_codes_json,
                router_reason_codes_json,
                system_reason_codes_json,
                systemd_status,
                docker_status,
                systemd_summary,
                docker_summary,
                systemd_reason_codes_json,
                docker_reason_codes_json,
                router_access_state,
                router_readiness_state,
                router_reachable,
                router_auth_required,
                system_running_as_root,
                system_cpu_usage_percent,
                system_memory_usage_percent,
                system_disk_usage_percent,
                system_temperature_c,
                system_load_avg_1m,
                system_network_rx_bps,
                system_network_tx_bps,
                evidence_json,
                stored_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                snapshot.checked_at.isoformat().replace("+00:00", "Z"),
                snapshot.guardian_status.value,
                snapshot.router_status.value,
                snapshot.system_status.value,
                snapshot.overview_summary,
                snapshot.router_summary,
                snapshot.system_summary,
                self._json(snapshot.overview_reason_codes),
                self._json(snapshot.router_reason_codes),
                self._json(snapshot.system_reason_codes),
                snapshot.systemd_status.value if snapshot.systemd_status is not None else None,
                snapshot.docker_status.value if snapshot.docker_status is not None else None,
                snapshot.systemd_summary,
                snapshot.docker_summary,
                self._json(snapshot.systemd_reason_codes),
                self._json(snapshot.docker_reason_codes),
                snapshot.router_access_state,
                snapshot.router_readiness_state,
                int(snapshot.router_reachable),
                int(snapshot.router_auth_required),
                int(snapshot.system_running_as_root),
                snapshot.system_cpu_usage_percent,
                snapshot.system_memory_usage_percent,
                snapshot.system_disk_usage_percent,
                snapshot.system_temperature_c,
                snapshot.system_load_avg_1m,
                snapshot.system_network_rx_bps,
                snapshot.system_network_tx_bps,
                self._json(snapshot.evidence),
                stored_at,
            ),
        )
        return int(cursor.lastrowid)

    def _insert_transition(
        self,
        conn: sqlite3.Connection,
        *,
        previous_snapshot_id: int,
        current_snapshot_id: int,
        from_status: GuardianSeverity,
        to_status: GuardianSeverity,
        reason_codes: list[str],
        summary: str,
        evidence: dict[str, object],
    ) -> int:
        created_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        cursor = conn.execute(
            """
            INSERT INTO state_transitions (
                created_at,
                previous_snapshot_id,
                current_snapshot_id,
                from_status,
                to_status,
                reason_codes_json,
                summary,
                evidence_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                created_at,
                previous_snapshot_id,
                current_snapshot_id,
                from_status.value,
                to_status.value,
                self._json(reason_codes),
                summary,
                self._json(evidence),
            ),
        )
        return int(cursor.lastrowid)

    def _get_last_snapshot_sync(self) -> GuardianSnapshotRecord | None:
        if self._init_error is not None:
            return None
        with self._lock, self._connection() as conn:
            row = self._load_last_snapshot_row(conn)
            if row is None:
                return None
            return self._row_to_snapshot_record(row)

    def _list_transitions_sync(self, limit: int) -> list[GuardianStateTransitionRecord]:
        if self._init_error is not None:
            return []
        safe_limit = max(int(limit), 1)
        with self._lock, self._connection() as conn:
            rows = conn.execute(
                """
                SELECT id, created_at, previous_snapshot_id, current_snapshot_id, from_status, to_status,
                       reason_codes_json, summary, evidence_json
                FROM state_transitions
                ORDER BY id DESC
                LIMIT ?
                """,
                (safe_limit,),
            ).fetchall()
        return [self._row_to_transition_record(row) for row in rows]

    def _list_snapshots_sync(self, limit: int) -> GuardianSnapshotHistory:
        if self._init_error is not None:
            return GuardianSnapshotHistory()
        safe_limit = max(int(limit), 1)
        with self._lock, self._connection() as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM status_snapshots
                ORDER BY id DESC
                LIMIT ?
                """,
                (safe_limit,),
            ).fetchall()
        return GuardianSnapshotHistory(items=[self._row_to_snapshot_record(row) for row in rows])

    def _list_metric_points_sync(self, limit: int) -> list[dict]:
        if self._init_error is not None:
            return []
        safe_limit = max(min(int(limit), 1000), 1)
        with self._lock, self._connection() as conn:
            rows = conn.execute(
                """
                SELECT checked_at,
                       system_cpu_usage_percent, system_memory_usage_percent,
                       system_disk_usage_percent, system_temperature_c,
                       system_load_avg_1m, system_network_rx_bps, system_network_tx_bps
                FROM status_snapshots
                ORDER BY id DESC
                LIMIT ?
                """,
                (safe_limit,),
            ).fetchall()
        points = [
            {
                "t": row["checked_at"],
                "cpu": row["system_cpu_usage_percent"],
                "memory": row["system_memory_usage_percent"],
                "disk": row["system_disk_usage_percent"],
                "temperature": row["system_temperature_c"],
                "load": row["system_load_avg_1m"],
                "net_rx_bps": row["system_network_rx_bps"],
                "net_tx_bps": row["system_network_tx_bps"],
            }
            for row in rows
        ]
        points.reverse()  # oldest -> newest for charting
        return points

    def _record_alert_sync(self, alert: GuardianAlertInput) -> GuardianAlertRecord:
        if self._init_error is not None:
            raise RuntimeError(self._init_error)
        with self._lock, self._connection() as conn:
            sent_at = datetime.now(UTC).isoformat().replace("+00:00", "Z") if alert.sent else None
            cursor = conn.execute(
                """
                INSERT INTO alert_events (
                    checked_at,
                    sent_at,
                    alert_key,
                    dedupe_key,
                    alert_kind,
                    outcome,
                    should_send,
                    sent,
                    suppressed_reason,
                    current_status,
                    previous_status,
                    policy_outcome,
                    changed,
                    transition_relevant,
                    cooldown_seconds,
                    cooldown_remaining_seconds,
                    telegram_ready,
                    telegram_ready_reason,
                    telegram_chat_id,
                    telegram_message_id,
                    telegram_error,
                    reason_codes_json,
                    summary,
                    message_text,
                    evidence_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    alert.checked_at.isoformat().replace("+00:00", "Z"),
                    sent_at,
                    alert.alert_key,
                    alert.dedupe_key,
                    alert.alert_kind,
                    alert.outcome,
                    int(alert.should_send),
                    int(alert.sent),
                    alert.suppressed_reason,
                    alert.current_status.value,
                    alert.previous_status.value if alert.previous_status else None,
                    alert.policy_outcome,
                    int(alert.changed),
                    int(alert.transition_relevant),
                    alert.cooldown_seconds,
                    alert.cooldown_remaining_seconds,
                    int(alert.telegram_ready),
                    alert.telegram_ready_reason,
                    alert.telegram_chat_id,
                    alert.telegram_message_id,
                    alert.telegram_error,
                    self._json(alert.reason_codes),
                    alert.summary,
                    alert.message_text,
                    self._json(alert.evidence),
                ),
            )
            row = conn.execute("SELECT * FROM alert_events WHERE id = ?", (int(cursor.lastrowid),)).fetchone()
            if row is None:
                raise RuntimeError("failed to load inserted alert event")
            return self._row_to_alert_record(row)

    def _list_alerts_sync(self, limit: int) -> GuardianAlertHistory:
        if self._init_error is not None:
            return GuardianAlertHistory()
        safe_limit = max(int(limit), 1)
        with self._lock, self._connection() as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM alert_events
                ORDER BY id DESC
                LIMIT ?
                """,
                (safe_limit,),
            ).fetchall()
        return GuardianAlertHistory(items=[self._row_to_alert_record(row) for row in rows])

    def _get_last_alert_for_key_sync(self, alert_key: str) -> GuardianAlertRecord | None:
        if self._init_error is not None:
            return None
        with self._lock, self._connection() as conn:
            row = conn.execute(
                """
                SELECT *
                FROM alert_events
                WHERE alert_key = ?
                ORDER BY id DESC
                LIMIT 1
                """,
                (alert_key,),
            ).fetchone()
        if row is None:
            return None
        return self._row_to_alert_record(row)

    def _record_action_sync(self, action: GuardianActionInput) -> GuardianActionRecord:
        if self._init_error is not None:
            raise RuntimeError(self._init_error)
        with self._lock, self._connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO action_events (
                    created_at, action_id, kind, target, outcome, dry_run, trigger,
                    trigger_snapshot_id, executed, success, exit_code, duration_ms,
                    command, error, source, evidence_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    action.created_at.isoformat().replace("+00:00", "Z"),
                    action.action_id,
                    action.kind,
                    action.target,
                    action.outcome,
                    int(action.dry_run),
                    action.trigger,
                    action.trigger_snapshot_id,
                    int(action.executed),
                    int(action.success),
                    action.exit_code,
                    action.duration_ms,
                    action.command,
                    action.error,
                    action.source,
                    self._json(action.evidence),
                ),
            )
            row = conn.execute("SELECT * FROM action_events WHERE id = ?", (int(cursor.lastrowid),)).fetchone()
            if row is None:
                raise RuntimeError("failed to load inserted action event")
            return self._row_to_action_record(row)

    def _list_actions_sync(self, limit: int) -> GuardianActionHistory:
        if self._init_error is not None:
            return GuardianActionHistory()
        safe_limit = max(int(limit), 1)
        with self._lock, self._connection() as conn:
            rows = conn.execute(
                "SELECT * FROM action_events ORDER BY id DESC LIMIT ?",
                (safe_limit,),
            ).fetchall()
        return GuardianActionHistory(items=[self._row_to_action_record(row) for row in rows])

    def _list_actions_for_id_sync(self, action_id: str, since_iso: str) -> list[GuardianActionRecord]:
        if self._init_error is not None:
            return []
        with self._lock, self._connection() as conn:
            rows = conn.execute(
                """
                SELECT * FROM action_events
                WHERE action_id = ? AND created_at >= ?
                ORDER BY id DESC
                """,
                (action_id, since_iso),
            ).fetchall()
        return [self._row_to_action_record(row) for row in rows]

    def _row_to_action_record(self, row: sqlite3.Row) -> GuardianActionRecord:
        return GuardianActionRecord(
            id=int(row["id"]),
            created_at=self._parse_datetime(row["created_at"]),
            action_id=row["action_id"],
            kind=row["kind"],
            target=row["target"],
            outcome=row["outcome"],
            dry_run=bool(row["dry_run"]),
            trigger=row["trigger"],
            trigger_snapshot_id=row["trigger_snapshot_id"],
            executed=bool(row["executed"]),
            success=bool(row["success"]),
            exit_code=row["exit_code"],
            duration_ms=row["duration_ms"],
            command=row["command"],
            error=row["error"],
            source=row["source"],
            evidence=self._json_loads(row["evidence_json"]),
        )

    def _load_last_snapshot_row(self, conn: sqlite3.Connection) -> sqlite3.Row | None:
        row = conn.execute(
            """
            SELECT *
            FROM status_snapshots
            ORDER BY id DESC
            LIMIT 1
            """
        ).fetchone()
        return row

    def _row_to_snapshot_record(self, row: sqlite3.Row) -> GuardianSnapshotRecord:
        return GuardianSnapshotRecord(
            id=int(row["id"]),
            checked_at=self._parse_datetime(row["checked_at"]),
            guardian_status=GuardianSeverity(row["guardian_status"]),
            router_status=GuardianSeverity(row["router_status"]),
            system_status=GuardianSeverity(row["system_status"]),
            overview_summary=row["overview_summary"],
            router_summary=row["router_summary"],
            system_summary=row["system_summary"],
            overview_reason_codes=self._json_loads(row["overview_reason_codes_json"]),
            router_reason_codes=self._json_loads(row["router_reason_codes_json"]),
            system_reason_codes=self._json_loads(row["system_reason_codes_json"]),
            systemd_status=GuardianSeverity(row["systemd_status"]) if row["systemd_status"] else None,
            docker_status=GuardianSeverity(row["docker_status"]) if row["docker_status"] else None,
            systemd_summary=row["systemd_summary"] or "",
            docker_summary=row["docker_summary"] or "",
            systemd_reason_codes=self._json_loads(row["systemd_reason_codes_json"]) or [],
            docker_reason_codes=self._json_loads(row["docker_reason_codes_json"]) or [],
            router_access_state=row["router_access_state"],
            router_readiness_state=row["router_readiness_state"],
            router_reachable=bool(row["router_reachable"]),
            router_auth_required=bool(row["router_auth_required"]),
            system_running_as_root=bool(row["system_running_as_root"]),
            system_cpu_usage_percent=row["system_cpu_usage_percent"],
            system_memory_usage_percent=row["system_memory_usage_percent"],
            system_disk_usage_percent=row["system_disk_usage_percent"],
            system_temperature_c=row["system_temperature_c"],
            system_load_avg_1m=row["system_load_avg_1m"],
            system_network_rx_bps=row["system_network_rx_bps"],
            system_network_tx_bps=row["system_network_tx_bps"],
            evidence=self._json_loads(row["evidence_json"]),
            stored_at=self._parse_datetime(row["stored_at"]),
        )

    def _row_to_transition_record(self, row: sqlite3.Row) -> GuardianStateTransitionRecord:
        return GuardianStateTransitionRecord(
            id=int(row["id"]),
            created_at=self._parse_datetime(row["created_at"]),
            previous_snapshot_id=row["previous_snapshot_id"],
            current_snapshot_id=int(row["current_snapshot_id"]),
            from_status=GuardianSeverity(row["from_status"]),
            to_status=GuardianSeverity(row["to_status"]),
            reason_codes=self._json_loads(row["reason_codes_json"]),
            summary=row["summary"],
            evidence=self._json_loads(row["evidence_json"]),
        )

    def _row_to_alert_record(self, row: sqlite3.Row) -> GuardianAlertRecord:
        sent_at_raw = row["sent_at"]
        return GuardianAlertRecord(
            id=int(row["id"]),
            checked_at=self._parse_datetime(row["checked_at"]),
            sent_at=self._parse_datetime(sent_at_raw) if sent_at_raw else None,
            alert_key=row["alert_key"],
            dedupe_key=row["dedupe_key"],
            alert_kind=row["alert_kind"],
            outcome=row["outcome"],
            should_send=bool(row["should_send"]),
            sent=bool(row["sent"]),
            suppressed_reason=row["suppressed_reason"],
            current_status=GuardianSeverity(row["current_status"]),
            previous_status=GuardianSeverity(row["previous_status"]) if row["previous_status"] else None,
            policy_outcome=row["policy_outcome"],
            changed=bool(row["changed"]),
            transition_relevant=bool(row["transition_relevant"]),
            cooldown_seconds=int(row["cooldown_seconds"]),
            cooldown_remaining_seconds=row["cooldown_remaining_seconds"],
            telegram_ready=bool(row["telegram_ready"]),
            telegram_ready_reason=row["telegram_ready_reason"],
            telegram_chat_id=row["telegram_chat_id"],
            telegram_message_id=row["telegram_message_id"],
            telegram_error=row["telegram_error"],
            reason_codes=self._json_loads(row["reason_codes_json"]),
            summary=row["summary"],
            message_text=row["message_text"],
            evidence=self._json_loads(row["evidence_json"]),
        )

    def _json(self, value: object) -> str:
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))

    def _json_loads(self, raw: str | None) -> object:
        if raw is None or raw == "":
            return {}
        return json.loads(raw)

    def _parse_datetime(self, raw: str) -> datetime:
        value = raw.replace("Z", "+00:00")
        return datetime.fromisoformat(value)
