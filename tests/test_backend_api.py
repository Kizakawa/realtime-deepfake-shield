"""Integration & security-invariant tests for the authenticated Phase 1 FastAPI Backend."""

from fastapi.testclient import TestClient

from shield_backend.app import create_app


def _sample_sos(alert_id: str = "sos_001", timestamp_sec: float = 100.0) -> dict:
    return {
        "alert_id": alert_id,
        "schema_version": "2.0",
        "timestamp_sec": timestamp_sec,
        "elderly_profile_id": "usr_parent_001",
        "event_type": "POINT_OF_LOSS_BANKING_INTERCEPT",
        "decision": {
            "state": "RED_INTERCEPT",
            "calibrated_risk_prob": 0.94,
            "active_session_minutes": 3.5,
        },
        "evidence_codes": [
            "LOOKALIKE_RELATIVE_NAME",
            "SHORT_GLITCHY_VIDEO_CALL",
            "BANKING_APP_OPENED_DURING_SESSION",
        ],
        "transcript_included": False,
    }


def _bootstrap_profile_and_guardians(client: TestClient) -> dict[str, str]:
    reg = client.post(
        "/api/v1/profiles/register",
        json={"elderly_profile_id": "usr_parent_001"},
    )
    assert reg.status_code == 200
    creds = reg.json()
    device_token = creds["device_token"]
    pairing_secret = creds["pairing_secret"]

    tokens: dict[str, str] = {
        "device_token": device_token,
        "pairing_secret": pairing_secret,
    }
    for gid, name, phone, tg in (
        ("g_son", "Con trai Minh", "+84901234567", "tg_101"),
        ("g_daughter", "Con gái Lan", "+84907654321", None),
    ):
        resp = client.post(
            "/api/v1/guardians/pair",
            json={
                "elderly_profile_id": "usr_parent_001",
                "guardian_id": gid,
                "display_name": name,
                "fcm_token": f"token_{gid}",
                "backup_phone_e164": phone,
                "telegram_chat_id": tg,
            },
            headers={"X-Pairing-Secret": pairing_secret},
        )
        assert resp.status_code == 200
        tokens[gid] = resp.json()["guardian_token"]
    return tokens


def test_least_privilege_sos_rejects_transcript_free_text_and_raw_media() -> None:
    app = create_app(db_path=":memory:")
    client = TestClient(app)
    tokens = _bootstrap_profile_and_guardians(client)
    dev_headers = {"X-Device-Token": tokens["device_token"]}

    bad_flag = _sample_sos()
    bad_flag["transcript_included"] = True
    assert client.post("/api/v1/sos/alert", json=bad_flag, headers=dev_headers).status_code == 422

    bad_extra = _sample_sos()
    bad_extra["transcript"] = "Chuyển 20 triệu ngay"
    assert client.post("/api/v1/sos/alert", json=bad_extra, headers=dev_headers).status_code == 422

    bad_rec = _sample_sos()
    bad_rec["recommended_action"] = "Free text smuggled"
    assert client.post("/api/v1/sos/alert", json=bad_rec, headers=dev_headers).status_code == 422

    bad_code_smuggle = _sample_sos()
    bad_code_smuggle["evidence_codes"] = ["Chuyen 20 trieu vao STK 19001234"]
    assert client.post("/api/v1/sos/alert", json=bad_code_smuggle, headers=dev_headers).status_code == 422


def test_multi_guardian_sos_dispatch_ack_and_sms_escalation() -> None:
    app = create_app(db_path=":memory:", ack_timeout_sec=30.0, admin_token="adm_test_secret")
    client = TestClient(app)
    tokens = _bootstrap_profile_and_guardians(client)
    dev_headers = {"X-Device-Token": tokens["device_token"]}
    adm_headers = {"X-Admin-Token": "adm_test_secret"}

    guardians = client.get("/api/v1/guardians/usr_parent_001", headers=dev_headers).json()
    assert guardians["guardian_count"] == 2
    assert guardians["multi_guardian_recommended_met"] is True

    r1 = client.post("/api/v1/sos/alert", json=_sample_sos("sos_unacked", 100.0), headers=dev_headers)
    assert r1.status_code == 200
    assert r1.json()["transcript_included"] is False
    assert len(app.state.hub.fcm_dispatches) == 2
    assert len(app.state.hub.telegram_dispatches) == 1

    esc_early = client.post("/api/v1/sos/escalate-pending?now_sec=120.0", headers=adm_headers).json()
    assert esc_early["escalated_count"] == 0

    esc_late = client.post("/api/v1/sos/escalate-pending?now_sec=131.0", headers=adm_headers).json()
    assert esc_late["escalated_alert_ids"] == ["sos_unacked"]
    assert len(app.state.hub.sms_dispatches) == 2

    client.post("/api/v1/sos/alert", json=_sample_sos("sos_acked", 200.0), headers=dev_headers)
    ack = client.post(
        "/api/v1/sos/sos_acked/ack",
        json={"guardian_id": "g_son", "action_taken": "CALLED_PARENT_BACK", "timestamp_sec": 210.0},
        headers={"X-Guardian-Token": tokens["g_son"]},
    )
    assert ack.status_code == 200
    assert ack.json()["status"] == "ACKED"

    # Replaying duplicate SOS alert_id must NOT overwrite ACKED status back to PENDING_ACK
    dup = client.post("/api/v1/sos/alert", json=_sample_sos("sos_acked", 200.0), headers=dev_headers)
    assert dup.status_code == 200
    assert dup.json()["duplicate_ignored"] is True
    assert dup.json()["status"] == "ACKED"

    esc_after_ack = client.post("/api/v1/sos/escalate-pending?now_sec=250.0", headers=adm_headers).json()
    assert esc_after_ack["escalated_count"] == 0

    tlog = client.get("/api/v1/transparency/usr_parent_001", headers=dev_headers).json()
    assert len(tlog["entries"]) == 3


def test_anti_tamper_heartbeat_and_stale_detection() -> None:
    app = create_app(db_path=":memory:", stale_heartbeat_sec=300.0, admin_token="adm_test_secret")
    client = TestClient(app)
    tokens = _bootstrap_profile_and_guardians(client)
    dev_headers = {"X-Device-Token": tokens["device_token"]}
    adm_headers = {"X-Admin-Token": "adm_test_secret"}

    hb_ok = client.post(
        "/api/v1/heartbeat",
        json={
            "elderly_profile_id": "usr_parent_001",
            "timestamp_sec": 1000.0,
            "service_running": True,
            "notification_listener_ok": True,
            "usage_stats_ok": True,
            "active_suspicion_session": True,
        },
        headers=dev_headers,
    ).json()
    assert hb_ok["tamper_alerted"] is False

    stale = client.post("/api/v1/heartbeat/check-stale?now_sec=1350.0", headers=adm_headers).json()
    assert stale["stale_alerted_profiles"] == ["usr_parent_001"]
    assert len(app.state.hub.fcm_dispatches) == 2

    hb_revoked = client.post(
        "/api/v1/heartbeat",
        json={
            "elderly_profile_id": "usr_parent_001",
            "timestamp_sec": 1400.0,
            "service_running": True,
            "notification_listener_ok": False,
            "usage_stats_ok": True,
            "active_suspicion_session": True,
        },
        headers=dev_headers,
    ).json()
    assert hb_revoked["tamper_alerted"] is True
    assert "NOTIFICATION_LISTENER_REVOKED" in hb_revoked["tamper_reasons"]


def test_remote_config_update_rollback_and_privacy_telemetry() -> None:
    app = create_app(db_path=":memory:", admin_token="adm_test_secret")
    client = TestClient(app)
    adm_headers = {"X-Admin-Token": "adm_test_secret"}

    v1 = client.get("/api/v1/config/active").json()
    assert v1["version"] == 1
    assert v1["tau_red"] == 0.85

    bad_cfg = {
        "tau_uncertain": 0.70,
        "tau_yellow": 0.50,
        "tau_red": 0.85,
        "session_ttl_sec": 3600.0,
        "banking_packages": ["com.VCB"],
        "remote_access_packages": ["com.anydesk.anydeskandroid"],
    }
    assert client.post("/api/v1/config/update", json=bad_cfg, headers=adm_headers).status_code == 422

    v2_resp = client.post(
        "/api/v1/config/update",
        json={
            "tau_uncertain": 0.30,
            "tau_yellow": 0.65,
            "tau_red": 0.80,
            "session_ttl_sec": 2400.0,
            "banking_packages": ["com.VCB", "com.mservice.momotransfer"],
            "remote_access_packages": ["com.anydesk.anydeskandroid"],
            "note": "Calibrated after Replay Batch #2",
        },
        headers=adm_headers,
    )
    assert v2_resp.status_code == 200
    assert v2_resp.json()["version"] == 2

    rb = client.post("/api/v1/config/rollback", headers=adm_headers)
    assert rb.status_code == 200
    assert rb.json()["version"] == 1
    assert rb.json()["tau_red"] == 0.85

    ok_tel = client.post(
        "/api/v1/telemetry/counters",
        json={
            "elderly_profile_hash": "sha256_9b8c7d6e5f4a",
            "device_tier": "TIER_1",
            "silenced_audio_count": 3,
            "false_alarm_dismissals": 0,
            "avg_inference_latency_ms": 42.5,
        },
    )
    assert ok_tel.status_code == 200

    bad_tel = {
        "elderly_profile_hash": "sha256_9b8c7d6e5f4a",
        "device_tier": "TIER_1",
        "silenced_audio_count": 0,
        "false_alarm_dismissals": 0,
        "avg_inference_latency_ms": 10.0,
        "raw_message_text": "Lộ thông tin",
    }
    assert client.post("/api/v1/telemetry/counters", json=bad_tel).status_code == 422
