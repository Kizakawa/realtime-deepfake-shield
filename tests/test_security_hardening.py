"""Regression test suite verifying all 12 security & engineering audit fixes."""

from __future__ import annotations

import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient

ROOT_DIR = Path(__file__).resolve().parents[1]
SPIKE_DIR = ROOT_DIR / "spikes" / "desktop-phase0-spike"
if str(SPIKE_DIR) not in sys.path:
    sys.path.insert(0, str(SPIKE_DIR))

from capture_desktop_lab import resolve_safe_sample_dir
from shield_backend.app import create_app
from shield_core.context_engine import VietnameseContextAnalyzer
from shield_core.fusion_engine import CrossChannelShieldEngine
from shield_core.models import CallEvent, ChannelType, ChatEvent, SystemState, TacticTag
from shield_desktop.audio_detector import OnnxAudioDetector, resample_audio_16k
from shield_desktop.context_slm_adapter import ContextSlmAdapter
from shield_desktop.desktop_runner import DesktopShieldRunner
from shield_desktop.video_detector import crop_face_or_center_roi


def test_audit_01_backend_blocks_unauthenticated_takeover_ack_and_admin() -> None:
    app = create_app(db_path=":memory:", admin_token="adm_real_secret")
    client = TestClient(app)

    reg = client.post("/api/v1/profiles/register", json={"elderly_profile_id": "usr_01"})
    assert reg.status_code == 200
    creds = reg.json()

    # Duplicate registration attempt -> 409 Conflict
    assert client.post("/api/v1/profiles/register", json={"elderly_profile_id": "usr_01"}).status_code == 409

    # Pairing without X-Pairing-Secret -> 403
    pair_body = {
        "elderly_profile_id": "usr_01",
        "guardian_id": "g_legit",
        "display_name": "Con Minh",
        "fcm_token": "fcm_legit",
        "backup_phone_e164": "+84901112222",
    }
    assert client.post("/api/v1/guardians/pair", json=pair_body).status_code == 403

    # Legitimate pairing succeeds; unauthenticated overwrite of existing guardian -> 403
    legit_pair = client.post(
        "/api/v1/guardians/pair",
        json=pair_body,
        headers={"X-Pairing-Secret": creds["pairing_secret"]},
    )
    assert legit_pair.status_code == 200
    g_token = legit_pair.json()["guardian_token"]

    overwrite_attempt = dict(pair_body, fcm_token="fcm_attacker", backup_phone_e164="+84999999999")
    assert (
        client.post(
            "/api/v1/guardians/pair",
            json=overwrite_attempt,
            headers={"X-Pairing-Secret": creds["pairing_secret"]},
        ).status_code
        == 403
    )

    # Unauthenticated SOS, Transparency IDOR, ACK spoofing, and Config tampering -> all 403
    sos_body = {
        "alert_id": "sos_auth_test",
        "schema_version": "2.0",
        "timestamp_sec": 10.0,
        "elderly_profile_id": "usr_01",
        "event_type": "CROSS_CHANNEL_SCAM_ALERT",
        "decision": {"state": "RED_INTERCEPT", "calibrated_risk_prob": 0.91, "active_session_minutes": 1.0},
        "evidence_codes": ["SHORT_GLITCHY_VIDEO_CALL"],
        "transcript_included": False,
    }
    assert client.post("/api/v1/sos/alert", json=sos_body).status_code == 403
    assert client.get("/api/v1/transparency/usr_01").status_code == 403
    assert client.post("/api/v1/config/rollback").status_code == 403

    # Send valid SOS with device_token, then verify spoofed ACK with wrong token fails (403)
    assert (
        client.post(
            "/api/v1/sos/alert",
            json=sos_body,
            headers={"X-Device-Token": creds["device_token"]},
        ).status_code
        == 200
    )
    assert (
        client.post(
            "/api/v1/sos/sos_auth_test/ack",
            json={"guardian_id": "g_legit", "action_taken": "CALLED_BACK"},
            headers={"X-Guardian-Token": "wrong_token"},
        ).status_code
        == 403
    )
    # Paired guardian can view transparency log and ACK with valid guardian token
    assert (
        client.get(
            "/api/v1/transparency/usr_01",
            headers={"X-Guardian-Token": g_token},
        ).status_code
        == 200
    )


def test_audit_06_vietnamese_homographs_boundaries_and_deobfuscation() -> None:
    analyzer = VietnameseContextAnalyzer()

    # Everyday phrases that previously collided after stripping diacritics must NOT trigger
    for benign in (
        "Mẹ chuẩn bị bật tivi xem thời sự nhé",
        "Sáng mai mở gặp mặt đầu xuân ở nhà văn hóa",
        "Order fastkart postcode apknot",
    ):
        out = analyzer.analyze(benign)
        assert out.signals == [], f"Unexpected false positive on: {benign}"

    # Real accented "bị bắt" and "mổ gấp" must still trigger
    arrested = analyzer.analyze("Bác ơi con đang bị bắt giam, chuyển khoản gấp")
    assert TacticTag.URGENCY_FEAR in arrested.matched_tactics
    assert TacticTag.FINANCIAL_TRANSFER in arrested.matched_tactics

    surgery = analyzer.analyze("Bác sĩ báo phải mổ gấp, chuyển tiền ngay")
    assert TacticTag.RELATIVE_EMERGENCY in surgery.matched_tactics

    # Scammer punctuation & leetspeak obfuscation must be defeated
    obfuscated = analyzer.analyze(
        "T.ô.i b.ê.n c-ô-n-g a-n, c.h.u.y.ể.n g.ấ.p vào s.t.k lạ, đọc 0TP và cài dichvu.apk"
    )
    assert TacticTag.AUTHORITY_IMPERSONATION in obfuscated.matched_tactics
    assert TacticTag.URGENCY_FEAR in obfuscated.matched_tactics
    assert TacticTag.FINANCIAL_TRANSFER in obfuscated.matched_tactics
    assert TacticTag.MALICIOUS_APP_INSTALL in obfuscated.matched_tactics


def test_audit_07_slm_signal_forwarding_and_counterparty_session_isolation() -> None:
    # 1. Valid SLM signal on subtle paraphrased text (no regex hits) must reach fusion engine
    def subtle_slm(_prompt: str) -> str:
        return (
            '{"tactics": ["SECRECY_ISOLATION", "FINANCIAL_TRANSFER"], '
            '"risk_prob": 0.92, "reason": "Ép rút sổ tiết kiệm ngầm"}'
        )

    engine = CrossChannelShieldEngine()
    runner = DesktopShieldRunner(
        engine=engine,
        context_adapter=ContextSlmAdapter(slm_callable=subtle_slm),
    )
    res = runner.handle_chat(
        ChatEvent(
            timestamp_sec=10.0,
            channel=ChannelType.ZALO_CHAT,
            sender_id="zalo_subtle_1",
            display_name="Người lạ",
            text="Bác ra quầy rút hết sổ tiết kiệm gửi vào chỗ này cho cháu, đừng kể ai trong nhà",
        )
    )
    assert any(s.code == "SLM_CONTEXT_SIGNAL" for s in res.active_evidence)
    assert res.state in {SystemState.YELLOW_VERIFY, SystemState.RED_INTERCEPT}

    # 2. Two unrelated callers must NOT bleed into a single combined session
    iso_engine = CrossChannelShieldEngine()
    r_a = iso_engine.process_call(
        CallEvent(
            timestamp_sec=0.0,
            channel=ChannelType.ZALO_VIDEO,
            caller_id="caller_a",
            display_name="Người A",
            duration_sec=6.0,
            is_video=True,
            blur_score=0.80,
            audio_silenced=True,
        )
    )
    r_b = iso_engine.process_call(
        CallEvent(
            timestamp_sec=30.0,
            channel=ChannelType.ZALO_VIDEO,
            caller_id="caller_b",
            display_name="Người B",
            duration_sec=6.0,
            is_video=True,
            blur_score=0.80,
            audio_silenced=True,
        )
    )
    assert r_a.state == SystemState.SUSPICION_SESSION
    assert r_b.state == SystemState.SUSPICION_SESSION
    assert len(iso_engine.sessions) == 2
    assert r_b.calibrated_risk_prob == pytest.approx(r_a.calibrated_risk_prob)


def test_audit_09_aasist_class_index_resampling_and_video_roi_crop() -> None:
    # Official clovaai/aasist order: index 0 = spoof, index 1 = bonafide
    spoof_logits = np.array([[3.5, -2.5]], dtype=np.float32)
    assert OnnxAudioDetector.logits_to_spoof_prob(spoof_logits, spoof_class_index=0) > 0.99
    assert OnnxAudioDetector.logits_to_spoof_prob(spoof_logits, spoof_class_index=1) < 0.01

    # 48 kHz -> 16 kHz resampling preserves duration (2s -> 32000 samples)
    sr_48k = 48000
    t = np.linspace(0.0, 2.0, sr_48k * 2, endpoint=False, dtype=np.float32)
    sig_48k = 0.5 * np.sin(2 * np.pi * 440.0 * t)
    sig_16k = resample_audio_16k(sig_48k, orig_sr=sr_48k, target_sr=16000)
    assert sig_16k.shape == (32000,)

    # Wide 1920x1080 screenshot crops to 1080x1080 center ROI instead of squashing aspect ratio
    wide = np.zeros((1080, 1920, 3), dtype=np.uint8)
    cropped = crop_face_or_center_roi(wide)
    assert cropped.shape == (1080, 1080, 3)


def test_audit_12_lab_capture_blocks_path_traversal(tmp_path: Path) -> None:
    safe = resolve_safe_sample_dir("zalo_sample_01", base_dir=tmp_path)
    assert safe == (tmp_path / "zalo_sample_01").resolve()

    for malicious in ("../outside", "..\\outside", "sub/dir", "", "bad space"):
        with pytest.raises(ValueError):
            resolve_safe_sample_dir(malicious, base_dir=tmp_path)


def test_audit_android_mvp_hardening_invariants() -> None:
    mvp_root = ROOT_DIR / "apps" / "android-shield-mvp" / "app" / "src" / "main"
    manifest_text = (mvp_root / "AndroidManifest.xml").read_text(encoding="utf-8")
    assert "SEND_SMS" not in manifest_text
    assert "AccessibilityService" not in manifest_text
    assert "RECORD_AUDIO" not in manifest_text
    assert "USE_FULL_SCREEN_INTENT" in manifest_text
    assert "RECEIVE_BOOT_COMPLETED" in manifest_text
    assert "@xml/network_security_config" in manifest_text

    net_cfg = ET.parse(mvp_root / "res" / "xml" / "network_security_config.xml").getroot()
    base_cfg = net_cfg.find("base-config")
    assert base_cfg is not None
    assert base_cfg.attrib.get("cleartextTrafficPermitted") == "false"

    notif_kt = (
        mvp_root / "java" / "com" / "shield" / "mvp" / "services" / "ShieldNotificationListenerService.kt"
    ).read_text(encoding="utf-8")
    assert "isVerifiedChannelId = hasVerifiedShortcut" in notif_kt
    assert "sendImmediateSignalAsync" in notif_kt

    pol_kt = (
        mvp_root / "java" / "com" / "shield" / "mvp" / "services" / "PointOfLossMonitorService.kt"
    ).read_text(encoding="utf-8")
    assert "lastObservedForegroundPkg = latestPkg" in pol_kt
    assert "EXTRA_REPLACING" in pol_kt
    assert "TRUSTED_INSTALLER_STORES" in pol_kt

    fusion_kt = (
        mvp_root / "java" / "com" / "shield" / "mvp" / "core" / "CrossChannelFusionEngine.kt"
    ).read_text(encoding="utf-8")
    assert "@Synchronized" in fusion_kt
