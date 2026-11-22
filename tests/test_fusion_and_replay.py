"""Unit & integration tests for Calibrated Noisy-OR fusion, TTL, and Replay Harness."""

from pathlib import Path

from shield_core.fusion_engine import CrossChannelShieldEngine, compute_noisy_or
from shield_core.layer0_gatekeeper import FamilyAllowlist
from shield_core.models import (
    AppUsageEvent,
    CallEvent,
    ChannelType,
    ChatEvent,
    EvidenceSignal,
    SystemState,
)
from shield_core.replay_harness import ReplayHarness


def test_noisy_or_does_not_dilute_strong_single_signal() -> None:
    strong = EvidenceSignal("engine_a", 0.96, 0.96, 0.92, "AUDIO_DEEPFAKE_SUSPECTED")
    weak = EvidenceSignal("engine_b", 0.0, 0.0, 0.80, "VIDEO_OK")
    score_single = compute_noisy_or([strong])
    score_combined = compute_noisy_or([strong, weak])
    assert score_single >= 0.88
    assert score_combined == score_single


def test_silenced_audio_is_never_fed_into_engine_a() -> None:
    engine = CrossChannelShieldEngine()
    res = engine.process_call(
        CallEvent(
            timestamp_sec=0.0,
            channel=ChannelType.ZALO_VOICE,
            caller_id="0912000999",
            display_name="Người lạ",
            duration_sec=20.0,
            audio_deepfake_prob=0.99,  # Stale/meaningless if OS silenced the stream
            audio_silenced=True,
        )
    )
    assert res.audio_bypassed_silenced is True
    assert res.state == SystemState.IDLE_ALLOWLISTED
    assert all(s.code != "AUDIO_DEEPFAKE_SUSPECTED" for s in res.active_evidence)


def test_cross_channel_short_video_chat_and_banking_intercept() -> None:
    allowlist = FamilyAllowlist(
        verified_caller_ids={"zalo:son_minh_real"},
        verified_relative_names={"Con trai Minh"},
    )
    engine = CrossChannelShieldEngine(allowlist=allowlist)

    r1 = engine.process_call(
        CallEvent(
            timestamp_sec=0.0,
            channel=ChannelType.ZALO_VIDEO,
            caller_id="zalo_new_991",
            display_name="Con trai Minh",
            duration_sec=5.0,
            is_video=True,
            is_abrupt_hangup=True,
            blur_score=0.85,
            audio_silenced=True,
        )
    )
    assert r1.state in {SystemState.SUSPICION_SESSION, SystemState.YELLOW_VERIFY}

    r2 = engine.process_chat(
        ChatEvent(
            timestamp_sec=20.0,
            channel=ChannelType.ZALO_CHAT,
            sender_id="zalo_new_991",
            display_name="Con trai Minh",
            text="Sóng yếu quá mẹ chuyển gấp 20 triệu vào STK mới này nhé",
        )
    )
    assert r2.state in {SystemState.YELLOW_VERIFY, SystemState.RED_INTERCEPT}

    r3 = engine.process_app_usage(
        AppUsageEvent(timestamp_sec=45.0, package_name="com.VCB", event_type="APP_OPENED")
    )
    assert r3.state == SystemState.RED_INTERCEPT
    assert r3.point_of_loss_triggered is True
    assert r3.sos_payload is not None
    assert r3.sos_payload.transcript_included is False
    assert "TẠM DỪNG" in r3.out_of_band_prompt
    assert "TẮT MÁY NGAY" not in r3.out_of_band_prompt


def test_suspicion_session_expires_after_ttl() -> None:
    engine = CrossChannelShieldEngine()
    r1 = engine.process_call(
        CallEvent(
            timestamp_sec=0.0,
            channel=ChannelType.ZALO_VIDEO,
            caller_id="02438889999",
            display_name="Phòng khám",
            duration_sec=8.0,
            is_video=True,
            blur_score=0.80,
            audio_silenced=True,
        )
    )
    assert r1.state == SystemState.SUSPICION_SESSION

    # Banking opened after TTL (3600s) -> must NOT intercept
    r2 = engine.process_app_usage(
        AppUsageEvent(timestamp_sec=4000.0, package_name="com.VCB", event_type="APP_OPENED")
    )
    assert r2.state == SystemState.IDLE_ALLOWLISTED
    assert r2.point_of_loss_triggered is False


def test_replay_harness_vietnam_phase0_benchmark() -> None:
    scenarios_path = (
        Path(__file__).resolve().parents[1]
        / "spikes"
        / "desktop-phase0-spike"
        / "scenarios"
        / "vietnam_phase0_scenarios.jsonl"
    )
    harness = ReplayHarness()
    scenarios = harness.load_jsonl(scenarios_path)
    report = harness.evaluate(scenarios)

    assert report.total_scenarios == 10
    assert report.attack_detected_red == report.attack_total
    assert report.benign_false_red == 0
    assert report.projected_false_red_per_user_month <= 0.5
    assert report.emergency_blocked_or_red == 0
    assert report.privacy_leaks_transcript_sent == 0
