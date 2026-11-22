"""Thread-safe SQLite repository with SHA-256 credential hashing and idempotent SOS storage."""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import sqlite3
import threading
import time
from typing import Any

from shield_core.layer0_gatekeeper import REMOTE_ACCESS_PACKAGES, VN_BANKING_PACKAGES

from .schemas import (
    GuardianPairRequest,
    HeartbeatRequest,
    RemoteConfigUpdateRequest,
    SosAlertRequest,
    TelemetryCounterRequest,
)


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class BackendRepository:
    """Persistent or in-memory SQLite store backing the Shield SOS & MLOps API."""

    def __init__(self, db_path: str = ":memory:") -> None:
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        with self._lock, self._conn:
            self._conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS profiles (
                    elderly_profile_id TEXT PRIMARY KEY,
                    device_token_hash TEXT NOT NULL,
                    pairing_secret_hash TEXT NOT NULL,
                    created_at REAL NOT NULL
                );

                CREATE TABLE IF NOT EXISTS guardians (
                    elderly_profile_id TEXT NOT NULL,
                    guardian_id TEXT NOT NULL,
                    display_name TEXT NOT NULL,
                    fcm_token TEXT NOT NULL,
                    backup_phone_e164 TEXT NOT NULL,
                    telegram_chat_id TEXT,
                    guardian_token_hash TEXT NOT NULL,
                    paired_at REAL NOT NULL,
                    PRIMARY KEY (elderly_profile_id, guardian_id)
                );

                CREATE TABLE IF NOT EXISTS sos_alerts (
                    alert_id TEXT PRIMARY KEY,
                    elderly_profile_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    state TEXT NOT NULL,
                    calibrated_risk_prob REAL NOT NULL,
                    active_session_minutes REAL NOT NULL,
                    evidence_codes_json TEXT NOT NULL,
                    created_at_sec REAL NOT NULL,
                    status TEXT NOT NULL,
                    acked_by TEXT,
                    acked_at_sec REAL
                );

                CREATE TABLE IF NOT EXISTS transparency_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    elderly_profile_id TEXT NOT NULL,
                    timestamp_sec REAL NOT NULL,
                    alert_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    shared_with_guardians_json TEXT NOT NULL,
                    summary_vn TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS heartbeats (
                    elderly_profile_id TEXT PRIMARY KEY,
                    last_timestamp_sec REAL NOT NULL,
                    service_running INTEGER NOT NULL,
                    notification_listener_ok INTEGER NOT NULL,
                    usage_stats_ok INTEGER NOT NULL,
                    active_suspicion_session INTEGER NOT NULL,
                    tamper_alerted INTEGER NOT NULL DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS config_versions (
                    version INTEGER PRIMARY KEY AUTOINCREMENT,
                    payload_json TEXT NOT NULL,
                    is_active INTEGER NOT NULL,
                    created_at REAL NOT NULL
                );

                CREATE TABLE IF NOT EXISTS telemetry_counters (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    elderly_profile_hash TEXT NOT NULL,
                    device_tier TEXT NOT NULL,
                    silenced_audio_count INTEGER NOT NULL,
                    false_alarm_dismissals INTEGER NOT NULL,
                    avg_inference_latency_ms REAL NOT NULL,
                    received_at REAL NOT NULL
                );
                """
            )
            existing_cfg = self._conn.execute("SELECT COUNT(*) FROM config_versions").fetchone()[0]
            if existing_cfg == 0:
                default_cfg = {
                    "tau_uncertain": 0.35,
                    "tau_yellow": 0.70,
                    "tau_red": 0.85,
                    "session_ttl_sec": 3600.0,
                    "banking_packages": sorted(VN_BANKING_PACKAGES),
                    "remote_access_packages": sorted(REMOTE_ACCESS_PACKAGES),
                    "note": "Initial provisional v2.0 config",
                }
                self._conn.execute(
                    "INSERT INTO config_versions (payload_json, is_active, created_at) VALUES (?, 1, ?)",
                    (json.dumps(default_cfg), time.time()),
                )

    def register_profile(self, elderly_profile_id: str) -> dict[str, str]:
        """Register a new elderly profile once; raises FileExistsError on duplicate ID."""
        device_token = f"dev_{secrets.token_urlsafe(24)}"
        pairing_secret = f"pair_{secrets.token_urlsafe(18)}"
        with self._lock, self._conn:
            existing = self._conn.execute(
                "SELECT 1 FROM profiles WHERE elderly_profile_id = ?",
                (elderly_profile_id,),
            ).fetchone()
            if existing is not None:
                raise FileExistsError(f"Profile '{elderly_profile_id}' is already registered")
            self._conn.execute(
                """
                INSERT INTO profiles (
                    elderly_profile_id, device_token_hash, pairing_secret_hash, created_at
                ) VALUES (?, ?, ?, ?)
                """,
                (
                    elderly_profile_id,
                    _hash_token(device_token),
                    _hash_token(pairing_secret),
                    time.time(),
                ),
            )
        return {
            "elderly_profile_id": elderly_profile_id,
            "device_token": device_token,
            "pairing_secret": pairing_secret,
        }

    def verify_device_token(self, elderly_profile_id: str, token: str | None) -> bool:
        if not token:
            return False
        with self._lock:
            row = self._conn.execute(
                "SELECT device_token_hash FROM profiles WHERE elderly_profile_id = ?",
                (elderly_profile_id,),
            ).fetchone()
            if row is None:
                return False
            return hmac.compare_digest(row["device_token_hash"], _hash_token(token))

    def verify_pairing_secret(self, elderly_profile_id: str, secret: str | None) -> bool:
        if not secret:
            return False
        with self._lock:
            row = self._conn.execute(
                "SELECT pairing_secret_hash FROM profiles WHERE elderly_profile_id = ?",
                (elderly_profile_id,),
            ).fetchone()
            if row is None:
                return False
            return hmac.compare_digest(row["pairing_secret_hash"], _hash_token(secret))

    def verify_guardian_token(
        self,
        elderly_profile_id: str,
        guardian_id: str,
        token: str | None,
    ) -> bool:
        if not token:
            return False
        with self._lock:
            row = self._conn.execute(
                """
                SELECT guardian_token_hash FROM guardians
                WHERE elderly_profile_id = ? AND guardian_id = ?
                """,
                (elderly_profile_id, guardian_id),
            ).fetchone()
            if row is None:
                return False
            return hmac.compare_digest(row["guardian_token_hash"], _hash_token(token))

    def verify_any_guardian_for_profile(self, elderly_profile_id: str, token: str | None) -> bool:
        if not token:
            return False
        candidate = _hash_token(token)
        with self._lock:
            rows = self._conn.execute(
                "SELECT guardian_token_hash FROM guardians WHERE elderly_profile_id = ?",
                (elderly_profile_id,),
            ).fetchall()
            return any(hmac.compare_digest(r["guardian_token_hash"], candidate) for r in rows)

    def pair_guardian(
        self,
        req: GuardianPairRequest,
        existing_guardian_token: str | None = None,
        device_token: str | None = None,
    ) -> tuple[list[dict[str, Any]], str]:
        """Pair or update a guardian up to 5 guardians; prevents unauthenticated overwrite."""
        with self._lock, self._conn:
            current = self.list_guardians(req.elderly_profile_id)
            already = any(g["guardian_id"] == req.guardian_id for g in current)
            if already:
                authorized_overwrite = self.verify_guardian_token(
                    req.elderly_profile_id, req.guardian_id, existing_guardian_token
                ) or self.verify_device_token(req.elderly_profile_id, device_token)
                if not authorized_overwrite:
                    raise PermissionError(
                        "Updating an existing guardian requires valid X-Guardian-Token or X-Device-Token"
                    )
            elif len(current) >= 5:
                raise ValueError("Maximum 5 guardians allowed per elderly profile")

            new_guardian_token = f"grd_{secrets.token_urlsafe(24)}"
            self._conn.execute(
                """
                INSERT INTO guardians (
                    elderly_profile_id, guardian_id, display_name,
                    fcm_token, backup_phone_e164, telegram_chat_id,
                    guardian_token_hash, paired_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(elderly_profile_id, guardian_id) DO UPDATE SET
                    display_name=excluded.display_name,
                    fcm_token=excluded.fcm_token,
                    backup_phone_e164=excluded.backup_phone_e164,
                    telegram_chat_id=excluded.telegram_chat_id,
                    guardian_token_hash=excluded.guardian_token_hash,
                    paired_at=excluded.paired_at
                """,
                (
                    req.elderly_profile_id,
                    req.guardian_id,
                    req.display_name,
                    req.fcm_token,
                    req.backup_phone_e164,
                    req.telegram_chat_id,
                    _hash_token(new_guardian_token),
                    time.time(),
                ),
            )
        return self.list_guardians(req.elderly_profile_id), new_guardian_token

    def list_guardians(self, elderly_profile_id: str) -> list[dict[str, Any]]:
        """Return paired guardians for an elderly profile."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM guardians WHERE elderly_profile_id = ? ORDER BY paired_at ASC",
                (elderly_profile_id,),
            ).fetchall()
            return [dict(row) for row in rows]

    def record_sos_alert(
        self,
        req: SosAlertRequest,
        guardian_names: list[str],
        summary_vn: str,
    ) -> tuple[dict[str, Any], bool]:
        """Idempotently store an SOS alert without overwriting ACKed/escalated alerts.

        Returns:
            `(stored_alert_dict, created_new)` where `created_new` is False on duplicate replay.
        """
        with self._lock, self._conn:
            existing = self.get_sos_alert(req.alert_id)
            if existing is not None:
                return existing, False

            self._conn.execute(
                """
                INSERT INTO sos_alerts (
                    alert_id, elderly_profile_id, event_type, state,
                    calibrated_risk_prob, active_session_minutes,
                    evidence_codes_json, created_at_sec, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'PENDING_ACK')
                """,
                (
                    req.alert_id,
                    req.elderly_profile_id,
                    req.event_type,
                    req.decision.state,
                    req.decision.calibrated_risk_prob,
                    req.decision.active_session_minutes,
                    json.dumps(req.evidence_codes),
                    req.timestamp_sec,
                ),
            )
            self._append_transparency_log(
                elderly_profile_id=req.elderly_profile_id,
                timestamp_sec=req.timestamp_sec,
                alert_id=req.alert_id,
                event_type=req.event_type,
                guardian_names=guardian_names,
                summary_vn=summary_vn,
            )
        return self.get_sos_alert(req.alert_id), True  # type: ignore[return-value]

    def get_sos_alert(self, alert_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM sos_alerts WHERE alert_id = ?", (alert_id,)
            ).fetchone()
            return dict(row) if row else None

    def ack_sos_alert(self, alert_id: str, guardian_id: str, acked_at_sec: float) -> dict[str, Any] | None:
        with self._lock, self._conn:
            row = self.get_sos_alert(alert_id)
            if row is None:
                return None
            self._conn.execute(
                """
                UPDATE sos_alerts
                SET status = 'ACKED', acked_by = ?, acked_at_sec = ?
                WHERE alert_id = ?
                """,
                (guardian_id, acked_at_sec, alert_id),
            )
        return self.get_sos_alert(alert_id)

    def find_pending_alerts_past_deadline(self, now_sec: float, ack_timeout_sec: float) -> list[dict[str, Any]]:
        cutoff = now_sec - ack_timeout_sec
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT * FROM sos_alerts
                WHERE status = 'PENDING_ACK' AND created_at_sec <= ?
                ORDER BY created_at_sec ASC
                """,
                (cutoff,),
            ).fetchall()
            return [dict(r) for r in rows]

    def mark_alert_sms_escalated(
        self,
        alert: dict[str, Any],
        now_sec: float,
        guardian_names: list[str],
    ) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                "UPDATE sos_alerts SET status = 'SMS_FALLBACK_SENT' WHERE alert_id = ?",
                (alert["alert_id"],),
            )
            self._append_transparency_log(
                elderly_profile_id=alert["elderly_profile_id"],
                timestamp_sec=now_sec,
                alert_id=alert["alert_id"],
                event_type="SERVER_SMS_FALLBACK",
                guardian_names=guardian_names,
                summary_vn="Không thấy con cái xác nhận sau 30 giây, hệ thống đã gửi SMS dự phòng.",
            )

    def upsert_heartbeat(self, req: HeartbeatRequest) -> dict[str, Any]:
        tamper_reasons: list[str] = []
        if not req.service_running:
            tamper_reasons.append("SERVICE_STOPPED")
        if not req.notification_listener_ok:
            tamper_reasons.append("NOTIFICATION_LISTENER_REVOKED")
        if not req.usage_stats_ok:
            tamper_reasons.append("USAGE_STATS_REVOKED")

        with self._lock, self._conn:
            self._conn.execute(
                """
                INSERT INTO heartbeats (
                    elderly_profile_id, last_timestamp_sec, service_running,
                    notification_listener_ok, usage_stats_ok,
                    active_suspicion_session, tamper_alerted
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(elderly_profile_id) DO UPDATE SET
                    last_timestamp_sec=excluded.last_timestamp_sec,
                    service_running=excluded.service_running,
                    notification_listener_ok=excluded.notification_listener_ok,
                    usage_stats_ok=excluded.usage_stats_ok,
                    active_suspicion_session=excluded.active_suspicion_session,
                    tamper_alerted=excluded.tamper_alerted
                """,
                (
                    req.elderly_profile_id,
                    req.timestamp_sec,
                    int(req.service_running),
                    int(req.notification_listener_ok),
                    int(req.usage_stats_ok),
                    int(req.active_suspicion_session),
                    int(bool(tamper_reasons)),
                ),
            )
        return {"tamper_reasons": tamper_reasons}

    def find_stale_heartbeats(self, now_sec: float, stale_after_sec: float) -> list[dict[str, Any]]:
        cutoff = now_sec - stale_after_sec
        with self._lock, self._conn:
            rows = self._conn.execute(
                """
                SELECT * FROM heartbeats
                WHERE last_timestamp_sec <= ? AND tamper_alerted = 0
                """,
                (cutoff,),
            ).fetchall()
            result = [dict(r) for r in rows]
            for row in result:
                self._conn.execute(
                    "UPDATE heartbeats SET tamper_alerted = 1 WHERE elderly_profile_id = ?",
                    (row["elderly_profile_id"],),
                )
            return result

    def append_tamper_transparency(
        self,
        elderly_profile_id: str,
        timestamp_sec: float,
        alert_id: str,
        event_type: str,
        guardian_names: list[str],
        summary_vn: str,
    ) -> None:
        with self._lock, self._conn:
            self._append_transparency_log(
                elderly_profile_id=elderly_profile_id,
                timestamp_sec=timestamp_sec,
                alert_id=alert_id,
                event_type=event_type,
                guardian_names=guardian_names,
                summary_vn=summary_vn,
            )

    def _append_transparency_log(
        self,
        elderly_profile_id: str,
        timestamp_sec: float,
        alert_id: str,
        event_type: str,
        guardian_names: list[str],
        summary_vn: str,
    ) -> None:
        self._conn.execute(
            """
            INSERT INTO transparency_logs (
                elderly_profile_id, timestamp_sec, alert_id, event_type,
                shared_with_guardians_json, summary_vn
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                elderly_profile_id,
                timestamp_sec,
                alert_id,
                event_type,
                json.dumps(guardian_names, ensure_ascii=False),
                summary_vn,
            ),
        )

    def get_transparency_logs(self, elderly_profile_id: str) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT id, elderly_profile_id, timestamp_sec, alert_id, event_type,
                       shared_with_guardians_json, summary_vn
                FROM transparency_logs
                WHERE elderly_profile_id = ?
                ORDER BY id DESC
                """,
                (elderly_profile_id,),
            ).fetchall()
            out: list[dict[str, Any]] = []
            for row in rows:
                item = dict(row)
                item["shared_with_guardians"] = json.loads(item.pop("shared_with_guardians_json"))
                out.append(item)
            return out

    def get_active_config(self) -> dict[str, Any]:
        with self._lock:
            row = self._conn.execute(
                "SELECT version, payload_json, created_at FROM config_versions WHERE is_active = 1 ORDER BY version DESC LIMIT 1"
            ).fetchone()
            assert row is not None
            payload = json.loads(row["payload_json"])
            return {"version": row["version"], "created_at": row["created_at"], **payload}

    def update_config(self, req: RemoteConfigUpdateRequest) -> dict[str, Any]:
        with self._lock, self._conn:
            self._conn.execute("UPDATE config_versions SET is_active = 0 WHERE is_active = 1")
            self._conn.execute(
                "INSERT INTO config_versions (payload_json, is_active, created_at) VALUES (?, 1, ?)",
                (req.model_dump_json(), time.time()),
            )
        return self.get_active_config()

    def rollback_config(self) -> dict[str, Any] | None:
        with self._lock, self._conn:
            active = self.get_active_config()
            prev = self._conn.execute(
                "SELECT version FROM config_versions WHERE version < ? ORDER BY version DESC LIMIT 1",
                (active["version"],),
            ).fetchone()
            if prev is None:
                return None
            self._conn.execute("UPDATE config_versions SET is_active = 0")
            self._conn.execute(
                "UPDATE config_versions SET is_active = 1 WHERE version = ?",
                (prev["version"],),
            )
        return self.get_active_config()

    def record_telemetry(self, req: TelemetryCounterRequest) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                """
                INSERT INTO telemetry_counters (
                    elderly_profile_hash, device_tier, silenced_audio_count,
                    false_alarm_dismissals, avg_inference_latency_ms, received_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    req.elderly_profile_hash,
                    req.device_tier,
                    req.silenced_audio_count,
                    req.false_alarm_dismissals,
                    req.avg_inference_latency_ms,
                    time.time(),
                ),
            )

    def get_telemetry_summary(self) -> dict[str, Any]:
        with self._lock:
            row = self._conn.execute(
                """
                SELECT COUNT(*) AS reports,
                       COALESCE(SUM(silenced_audio_count), 0) AS total_silenced_audio,
                       COALESCE(SUM(false_alarm_dismissals), 0) AS total_false_dismissals,
                       COALESCE(AVG(avg_inference_latency_ms), 0.0) AS avg_latency_ms
                FROM telemetry_counters
                """
            ).fetchone()
            return dict(row)
