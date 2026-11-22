"""Desktop Companion Runner connecting AI engines to CrossChannelShieldEngine & SOS Backend."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np

from shield_core.fusion_engine import CrossChannelShieldEngine
from shield_core.layer0_gatekeeper import FamilyAllowlist
from shield_core.models import (
    AppUsageEvent,
    CallEvent,
    ChannelType,
    ChatEvent,
    DecisionResult,
)

from .audio_detector import AudioDeepfakeDetector, load_audio_detector
from .context_slm_adapter import ContextSlmAdapter
from .video_detector import VideoForensicsDetector, load_video_detector


class DesktopShieldRunner:
    """Orchestrates live/simulated desktop frames, audio windows, chats, and authenticated SOS."""

    def __init__(
        self,
        engine: CrossChannelShieldEngine,
        audio_detector: AudioDeepfakeDetector | None = None,
        video_detector: VideoForensicsDetector | None = None,
        context_adapter: ContextSlmAdapter | None = None,
        api_client: Any | None = None,
        device_token: str | None = None,
    ) -> None:
        self.engine = engine
        self.audio_detector = audio_detector or load_audio_detector()
        self.video_detector = video_detector or load_video_detector()
        self.context_adapter = context_adapter or ContextSlmAdapter()
        self.api_client = api_client
        self.device_token = device_token

    def handle_call_media(
        self,
        *,
        timestamp_sec: float,
        channel: ChannelType,
        caller_id: str,
        display_name: str,
        duration_sec: float,
        audio_samples: np.ndarray | None = None,
        audio_sample_rate_hz: int = 16000,
        rgb_frame: np.ndarray | None = None,
        face_bbox: tuple[int, int, int, int] | None = None,
        transcript: str = "",
        is_abrupt_hangup: bool = False,
    ) -> DecisionResult:
        """Run Audio/Video/SLM detectors on RAM buffers and feed CrossChannelShieldEngine."""
        audio_prob: float | None = None
        if audio_samples is not None and audio_samples.size > 0:
            audio_res = self.audio_detector.predict(audio_samples, sample_rate_hz=audio_sample_rate_hz)
            audio_prob = audio_res.calibrated_prob

        is_video = rgb_frame is not None
        video_prob: float | None = None
        blur_score = 0.0
        if rgb_frame is not None:
            vid_res = self.video_detector.predict(rgb_frame, face_bbox=face_bbox)
            video_prob = vid_res.spatial_score
            blur_score = vid_res.blur_score

        slm_signals = []
        if transcript.strip():
            ctx_res = self.context_adapter.analyze(transcript, source_tag="desktop_voice_slm")
            slm_signals = [
                s for s in ctx_res.signals if s.code in {"SLM_CONTEXT_SIGNAL", "SLM_OUTPUT_REJECTED"}
            ]

        res = self.engine.process_call(
            CallEvent(
                timestamp_sec=timestamp_sec,
                channel=channel,
                caller_id=caller_id,
                display_name=display_name,
                duration_sec=duration_sec,
                is_video=is_video,
                is_abrupt_hangup=is_abrupt_hangup,
                blur_score=blur_score,
                audio_deepfake_prob=audio_prob,
                audio_silenced=audio_samples is None,
                video_deepfake_prob=video_prob,
                transcript=transcript,
            ),
            extra_signals=slm_signals,
        )
        self._dispatch_sos_if_needed(res)
        return res

    def handle_chat(self, event: ChatEvent) -> DecisionResult:
        """Evaluate chat with both baseline + validated SLM signals prior to Noisy-OR fusion."""
        ctx_res = self.context_adapter.analyze(event.text, source_tag="desktop_chat_slm")
        slm_extra = [
            s for s in ctx_res.signals if s.code in {"SLM_CONTEXT_SIGNAL", "SLM_OUTPUT_REJECTED"}
        ]
        res = self.engine.process_chat(event, extra_signals=slm_extra)
        self._dispatch_sos_if_needed(res)
        return res

    def handle_app_usage(self, event: AppUsageEvent) -> DecisionResult:
        """Process banking / remote-access app event and dispatch SOS if intercepted."""
        res = self.engine.process_app_usage(event)
        self._dispatch_sos_if_needed(res)
        return res

    def _dispatch_sos_if_needed(self, res: DecisionResult) -> None:
        if self.api_client is not None and res.sos_payload is not None:
            headers = {"X-Device-Token": self.device_token} if self.device_token else {}
            resp = self.api_client.post(
                "/api/v1/sos/alert",
                json=res.sos_payload.to_dict(),
                headers=headers,
            )
            resp.raise_for_status()


def run_t1_desktop_simulation() -> dict[str, Any]:
    """Run an authenticated end-to-end T1 simulation against in-process FastAPI Backend."""
    from fastapi.testclient import TestClient

    from shield_backend.app import create_app

    app = create_app(db_path=":memory:")
    client = TestClient(app)

    # Register elderly profile to obtain device_token + pairing_secret.
    reg = client.post(
        "/api/v1/profiles/register",
        json={"elderly_profile_id": "usr_parent_demo"},
    )
    reg.raise_for_status()
    creds = reg.json()
    device_token = creds["device_token"]
    pairing_secret = creds["pairing_secret"]

    # Pair 2 guardians using the scoped X-Pairing-Secret.
    for gid, name, phone in (
        ("g_son_minh", "Con trai Minh", "+84901234567"),
        ("g_daughter_lan", "Con gái Lan", "+84907654321"),
    ):
        client.post(
            "/api/v1/guardians/pair",
            json={
                "elderly_profile_id": "usr_parent_demo",
                "guardian_id": gid,
                "display_name": name,
                "fcm_token": f"fcm_{gid}",
                "backup_phone_e164": phone,
            },
            headers={"X-Pairing-Secret": pairing_secret},
        ).raise_for_status()

    allowlist = FamilyAllowlist(
        verified_caller_ids={"zalo:son_minh_real"},
        verified_relative_names={"Con trai Minh"},
    )
    engine = CrossChannelShieldEngine(allowlist=allowlist, elderly_profile_id="usr_parent_demo")
    runner = DesktopShieldRunner(
        engine=engine,
        api_client=client,
        device_token=device_token,
    )

    blurry_frame = np.full((224, 224, 3), 120, dtype=np.uint8)
    r1 = runner.handle_call_media(
        timestamp_sec=0.0,
        channel=ChannelType.ZALO_VIDEO,
        caller_id="zalo_new_991",
        display_name="Con trai Minh",
        duration_sec=5.0,
        audio_samples=None,
        rgb_frame=blurry_frame,
        is_abrupt_hangup=True,
    )

    r2 = runner.handle_chat(
        ChatEvent(
            timestamp_sec=20.0,
            channel=ChannelType.ZALO_CHAT,
            sender_id="zalo_new_991",
            display_name="Con trai Minh",
            text="Sóng yếu quá mẹ ơi, con cần chuyển gấp 20 triệu vào STK mới này",
        )
    )

    r3 = runner.handle_app_usage(
        AppUsageEvent(timestamp_sec=45.0, package_name="com.VCB", event_type="APP_OPENED")
    )

    transparency = client.get(
        "/api/v1/transparency/usr_parent_demo",
        headers={"X-Device-Token": device_token},
    ).json()
    return {
        "step1_state": r1.state.value,
        "step2_state": r2.state.value,
        "step3_state": r3.state.value,
        "step3_point_of_loss": r3.point_of_loss_triggered,
        "fcm_dispatches_count": len(app.state.hub.fcm_dispatches),
        "transparency_entries_count": len(transparency["entries"]),
        "transcript_included": r3.sos_payload.transcript_included if r3.sos_payload else None,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Realtime Deepfake Shield Desktop Runner")
    parser.add_argument(
        "--simulate-t1",
        action="store_true",
        help="Run end-to-end T1 simulation against in-process FastAPI SOS Backend",
    )
    args = parser.parse_args()

    if args.simulate_t1:
        summary = run_t1_desktop_simulation()
        print(json.dumps(summary, indent=2, ensure_ascii=False))
        return 0 if summary["step3_state"] == "RED_INTERCEPT" and summary["transcript_included"] is False else 1

    parser.print_help()
    return 0


if __name__ == "__main__":
    root_src = Path(__file__).resolve().parents[1]
    if str(root_src) not in sys.path:
        sys.path.insert(0, str(root_src))
    raise SystemExit(main())
