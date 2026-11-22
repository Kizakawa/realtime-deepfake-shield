"""Authenticated FastAPI service for Shield SOS, Anti-Tamper, and MLOps Remote Config."""

from __future__ import annotations

import hmac
import os
import secrets
import time
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Query

from .notifiers import DispatcherHub
from .schemas import (
    GuardianPairRequest,
    HeartbeatRequest,
    ProfileRegisterRequest,
    RemoteConfigUpdateRequest,
    SosAckRequest,
    SosAlertRequest,
    TelemetryCounterRequest,
)
from .storage import BackendRepository

_SERVER_RECOMMENDED_ACTION = (
    "Gọi lại trực tiếp bằng số di động đã lưu để kiểm chứng với Cha/Mẹ ngay."
)


def create_app(
    db_path: str = ":memory:",
    ack_timeout_sec: float = 30.0,
    stale_heartbeat_sec: float = 300.0,
    admin_token: str | None = None,
) -> FastAPI:
    """Create a configured, token-authenticated FastAPI service for Shield v2.0."""
    app = FastAPI(
        title="Realtime Deepfake Shield Backend",
        version="2.0.1",
        description="Authenticated Least-Privilege SOS, Anti-Tamper & Remote Config API",
    )
    repo = BackendRepository(db_path=db_path)
    hub = DispatcherHub()
    effective_admin_token = (
        admin_token
        or os.environ.get("SHIELD_ADMIN_TOKEN")
        or f"adm_{secrets.token_urlsafe(24)}"
    )

    app.state.repo = repo
    app.state.hub = hub
    app.state.ack_timeout_sec = ack_timeout_sec
    app.state.stale_heartbeat_sec = stale_heartbeat_sec
    app.state.admin_token = effective_admin_token

    def _require_admin(x_admin_token: str | None) -> None:
        if not x_admin_token or not hmac.compare_digest(x_admin_token, app.state.admin_token):
            raise HTTPException(status_code=403, detail="Invalid or missing X-Admin-Token")

    def _require_device(elderly_profile_id: str, x_device_token: str | None) -> None:
        if not repo.verify_device_token(elderly_profile_id, x_device_token):
            raise HTTPException(status_code=403, detail="Invalid or missing X-Device-Token")

    def _require_device_or_guardian(
        elderly_profile_id: str,
        x_device_token: str | None,
        x_guardian_token: str | None,
    ) -> None:
        if repo.verify_device_token(elderly_profile_id, x_device_token):
            return
        if repo.verify_any_guardian_for_profile(elderly_profile_id, x_guardian_token):
            return
        raise HTTPException(
            status_code=403,
            detail="Valid X-Device-Token or paired X-Guardian-Token required",
        )

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "schema_version": "2.0"}

    @app.post("/api/v1/profiles/register")
    def register_profile(req: ProfileRegisterRequest) -> dict[str, str]:
        try:
            return repo.register_profile(req.elderly_profile_id)
        except FileExistsError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post("/api/v1/guardians/pair")
    def pair_guardian(
        req: GuardianPairRequest,
        x_pairing_secret: str | None = Header(default=None),
        x_guardian_token: str | None = Header(default=None),
        x_device_token: str | None = Header(default=None),
    ) -> dict[str, Any]:
        if not repo.verify_pairing_secret(req.elderly_profile_id, x_pairing_secret):
            raise HTTPException(status_code=403, detail="Invalid or missing X-Pairing-Secret")
        try:
            guardians, issued_guardian_token = repo.pair_guardian(
                req,
                existing_guardian_token=x_guardian_token,
                device_token=x_device_token,
            )
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        return {
            "elderly_profile_id": req.elderly_profile_id,
            "guardian_id": req.guardian_id,
            "guardian_token": issued_guardian_token,
            "guardian_count": len(guardians),
            "multi_guardian_recommended_met": len(guardians) >= 2,
            "guardians": [
                {"guardian_id": g["guardian_id"], "display_name": g["display_name"]}
                for g in guardians
            ],
        }

    @app.get("/api/v1/guardians/{elderly_profile_id}")
    def list_guardians(
        elderly_profile_id: str,
        x_device_token: str | None = Header(default=None),
        x_guardian_token: str | None = Header(default=None),
    ) -> dict[str, Any]:
        _require_device_or_guardian(elderly_profile_id, x_device_token, x_guardian_token)
        guardians = repo.list_guardians(elderly_profile_id)
        return {
            "elderly_profile_id": elderly_profile_id,
            "guardian_count": len(guardians),
            "multi_guardian_recommended_met": len(guardians) >= 2,
            "guardians": [
                {"guardian_id": g["guardian_id"], "display_name": g["display_name"]}
                for g in guardians
            ],
        }

    @app.post("/api/v1/sos/alert")
    def receive_sos_alert(
        req: SosAlertRequest,
        x_device_token: str | None = Header(default=None),
    ) -> dict[str, Any]:
        _require_device(req.elderly_profile_id, x_device_token)
        guardians = repo.list_guardians(req.elderly_profile_id)
        guardian_names = [g["display_name"] for g in guardians]
        codes_str = ", ".join(req.evidence_codes)
        summary_vn = (
            f"Cảnh báo [{req.decision.state}] ({req.decision.calibrated_risk_prob:.0%}): "
            f"{codes_str}. Không gửi nội dung hội thoại."
        )
        stored, created_new = repo.record_sos_alert(
            req,
            guardian_names=guardian_names,
            summary_vn=summary_vn,
        )
        dispatched_count = 0
        if created_new:
            dispatches = hub.send_primary_push(
                guardians=guardians,
                elderly_profile_id=req.elderly_profile_id,
                alert_id=req.alert_id,
                event_type=req.event_type,
                message=f"{summary_vn} {_SERVER_RECOMMENDED_ACTION}",
            )
            dispatched_count = len(dispatches)
        return {
            "alert_id": stored["alert_id"],
            "status": stored["status"],
            "duplicate_ignored": not created_new,
            "transcript_included": False,
            "dispatched_count": dispatched_count,
            "ack_deadline_sec": app.state.ack_timeout_sec,
        }

    @app.post("/api/v1/sos/{alert_id}/ack")
    def ack_sos(
        alert_id: str,
        req: SosAckRequest,
        x_guardian_token: str | None = Header(default=None),
    ) -> dict[str, Any]:
        existing = repo.get_sos_alert(alert_id)
        if existing is None:
            raise HTTPException(status_code=404, detail="SOS alert not found")
        if not repo.verify_guardian_token(
            existing["elderly_profile_id"], req.guardian_id, x_guardian_token
        ):
            raise HTTPException(status_code=403, detail="Invalid or unauthorized X-Guardian-Token")

        ts = req.timestamp_sec if req.timestamp_sec is not None else time.time()
        updated = repo.ack_sos_alert(alert_id, guardian_id=req.guardian_id, acked_at_sec=ts)
        assert updated is not None
        return {
            "alert_id": updated["alert_id"],
            "status": updated["status"],
            "acked_by": updated["acked_by"],
        }

    @app.post("/api/v1/sos/escalate-pending")
    def escalate_pending(
        now_sec: float | None = Query(default=None, ge=0.0),
        x_admin_token: str | None = Header(default=None),
    ) -> dict[str, Any]:
        _require_admin(x_admin_token)
        current = now_sec if now_sec is not None else time.time()
        pending = repo.find_pending_alerts_past_deadline(current, app.state.ack_timeout_sec)
        escalated_ids: list[str] = []
        for alert in pending:
            guardians = repo.list_guardians(alert["elderly_profile_id"])
            guardian_names = [g["display_name"] for g in guardians]
            hub.send_server_sms_fallback(
                guardians=guardians,
                elderly_profile_id=alert["elderly_profile_id"],
                alert_id=alert["alert_id"],
                event_type="SERVER_SMS_FALLBACK",
                message=(
                    f"[LA CHAN SOS] Canh bao khan cap ({alert['event_type']}) chua duoc xac nhan. "
                    "Vui long goi kiem chung cho Cha/Me NGAY."
                ),
            )
            repo.mark_alert_sms_escalated(alert, now_sec=current, guardian_names=guardian_names)
            escalated_ids.append(alert["alert_id"])
        return {"escalated_count": len(escalated_ids), "escalated_alert_ids": escalated_ids}

    @app.get("/api/v1/transparency/{elderly_profile_id}")
    def get_transparency_log(
        elderly_profile_id: str,
        x_device_token: str | None = Header(default=None),
        x_guardian_token: str | None = Header(default=None),
    ) -> dict[str, Any]:
        _require_device_or_guardian(elderly_profile_id, x_device_token, x_guardian_token)
        logs = repo.get_transparency_logs(elderly_profile_id)
        return {"elderly_profile_id": elderly_profile_id, "entries": logs}

    @app.post("/api/v1/heartbeat")
    def submit_heartbeat(
        req: HeartbeatRequest,
        x_device_token: str | None = Header(default=None),
    ) -> dict[str, Any]:
        _require_device(req.elderly_profile_id, x_device_token)
        res = repo.upsert_heartbeat(req)
        reasons = res["tamper_reasons"]
        tamper_alerted = False
        if reasons:
            guardians = repo.list_guardians(req.elderly_profile_id)
            guardian_names = [g["display_name"] for g in guardians]
            alert_id = f"tamper_{req.elderly_profile_id}_{int(req.timestamp_sec * 1000)}"
            summary_vn = (
                "Cảnh báo chống phá hoại: Ứng dụng bảo vệ bị tắt hoặc thu hồi quyền "
                f"({', '.join(reasons)})."
            )
            hub.send_primary_push(
                guardians=guardians,
                elderly_profile_id=req.elderly_profile_id,
                alert_id=alert_id,
                event_type="TAMPER_ALERT",
                message=summary_vn,
            )
            repo.append_tamper_transparency(
                elderly_profile_id=req.elderly_profile_id,
                timestamp_sec=req.timestamp_sec,
                alert_id=alert_id,
                event_type="TAMPER_ALERT",
                guardian_names=guardian_names,
                summary_vn=summary_vn,
            )
            tamper_alerted = True
        return {"ok": True, "tamper_alerted": tamper_alerted, "tamper_reasons": reasons}

    @app.post("/api/v1/heartbeat/check-stale")
    def check_stale_heartbeats(
        now_sec: float | None = Query(default=None, ge=0.0),
        x_admin_token: str | None = Header(default=None),
    ) -> dict[str, Any]:
        _require_admin(x_admin_token)
        current = now_sec if now_sec is not None else time.time()
        stale_profiles = repo.find_stale_heartbeats(current, app.state.stale_heartbeat_sec)
        alerted: list[str] = []
        for row in stale_profiles:
            pid = row["elderly_profile_id"]
            guardians = repo.list_guardians(pid)
            guardian_names = [g["display_name"] for g in guardians]
            alert_id = f"tamper_stale_{pid}_{int(current * 1000)}"
            note = (
                "Mất tín hiệu ứng dụng bảo vệ khi đang có phiên nghi vấn!"
                if row["active_suspicion_session"]
                else "Ứng dụng bảo vệ ngừng gửi tín hiệu định kỳ (nghi vấn bị tắt/gỡ)."
            )
            hub.send_primary_push(
                guardians=guardians,
                elderly_profile_id=pid,
                alert_id=alert_id,
                event_type="TAMPER_ALERT_STALE_HEARTBEAT",
                message=note,
            )
            repo.append_tamper_transparency(
                elderly_profile_id=pid,
                timestamp_sec=current,
                alert_id=alert_id,
                event_type="TAMPER_ALERT_STALE_HEARTBEAT",
                guardian_names=guardian_names,
                summary_vn=note,
            )
            alerted.append(pid)
        return {"stale_alerted_profiles": alerted}

    @app.get("/api/v1/config/active")
    def get_active_config() -> dict[str, Any]:
        return repo.get_active_config()

    @app.post("/api/v1/config/update")
    def update_config(
        req: RemoteConfigUpdateRequest,
        x_admin_token: str | None = Header(default=None),
    ) -> dict[str, Any]:
        _require_admin(x_admin_token)
        return repo.update_config(req)

    @app.post("/api/v1/config/rollback")
    def rollback_config(x_admin_token: str | None = Header(default=None)) -> dict[str, Any]:
        _require_admin(x_admin_token)
        rolled = repo.rollback_config()
        if rolled is None:
            raise HTTPException(status_code=400, detail="No previous config version to roll back to")
        return rolled

    @app.post("/api/v1/telemetry/counters")
    def submit_telemetry(req: TelemetryCounterRequest) -> dict[str, Any]:
        repo.record_telemetry(req)
        return {"accepted": True}

    @app.get("/api/v1/telemetry/summary")
    def telemetry_summary(x_admin_token: str | None = Header(default=None)) -> dict[str, Any]:
        _require_admin(x_admin_token)
        return repo.get_telemetry_summary()

    return app
