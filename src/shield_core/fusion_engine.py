"""Calibrated Noisy-OR fusion and per-counterparty 5-state cross-channel decision machine."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from .context_engine import VietnameseContextAnalyzer
from .layer0_gatekeeper import (
    REMOTE_ACCESS_PACKAGES,
    VN_BANKING_PACKAGES,
    FamilyAllowlist,
    Layer0Gatekeeper,
    is_emergency_number,
)
from .models import (
    AppUsageEvent,
    CallEvent,
    ChatEvent,
    DecisionResult,
    EvidenceSignal,
    LeastPrivilegeSosPayload,
    SuspicionSession,
    SystemState,
)

_STATE_RANK: dict[SystemState, int] = {
    SystemState.IDLE_ALLOWLISTED: 0,
    SystemState.MONITORING: 1,
    SystemState.SUSPICION_SESSION: 2,
    SystemState.YELLOW_VERIFY: 3,
    SystemState.RED_INTERCEPT: 4,
}


@dataclass(frozen=True)
class ProvisionalThresholds:
    """Provisional decision thresholds pending Replay Corpus calibration."""

    tau_uncertain: float = 0.35
    tau_yellow: float = 0.70
    tau_red: float = 0.85
    session_ttl_sec: float = 3600.0
    short_call_sec: float = 15.0
    blur_threshold: float = 0.65
    is_provisional: bool = True


def calibrate_probability(score: float, temperature: float = 1.0, bias: float = 0.0) -> float:
    """Apply bounded logistic temperature scaling to map raw scores into [0, 1]."""
    clipped = min(max(float(score), 1e-4), 1.0 - 1e-4)
    if abs(temperature - 1.0) < 1e-9 and abs(bias) < 1e-9:
        return clipped
    logit = math.log(clipped / (1.0 - clipped))
    scaled = (logit / max(temperature, 1e-3)) + bias
    return float(1.0 / (1.0 + math.exp(-scaled)))


def compute_noisy_or(signals: list[EvidenceSignal]) -> float:
    """Compute P_risk = 1 - prod_k (1 - r_k * p_k) without diluting strong single cues."""
    if not signals:
        return 0.0
    probs = np.array([min(max(s.calibrated_prob, 0.0), 1.0) for s in signals], dtype=np.float64)
    rels = np.array([min(max(s.reliability, 0.0), 1.0) for s in signals], dtype=np.float64)
    survival = np.prod(1.0 - (rels * probs))
    return float(min(max(1.0 - survival, 0.0), 1.0))


class CrossChannelShieldEngine:
    """Stateful v2.0 cross-channel fusion engine isolated per counterparty."""

    def __init__(
        self,
        allowlist: FamilyAllowlist | None = None,
        thresholds: ProvisionalThresholds | None = None,
        elderly_profile_id: str = "usr_parent_demo",
    ) -> None:
        self.thresholds = thresholds or ProvisionalThresholds()
        self.gatekeeper = Layer0Gatekeeper(allowlist=allowlist)
        self.context_analyzer = VietnameseContextAnalyzer()
        self.elderly_profile_id = elderly_profile_id

        self.sessions: dict[str, SuspicionSession] = {}
        self.current_state: SystemState = SystemState.IDLE_ALLOWLISTED
        self._session_seq = 0
        self._sos_seq = 0

    @property
    def active_session(self) -> SuspicionSession | None:
        """Return the highest-risk unexpired session (if any)."""
        if not self.sessions:
            return None
        return max(
            self.sessions.values(),
            key=lambda s: (_STATE_RANK[s.state], s.max_risk_prob, s.last_event_sec),
        )

    def process_call(
        self,
        event: CallEvent,
        extra_signals: list[EvidenceSignal] | None = None,
    ) -> DecisionResult:
        """Evaluate incoming/ended call telemetry and update counterparty session."""
        self._expire_sessions_if_needed(event.timestamp_sec)

        gate = self.gatekeeper.evaluate_counterparty(event.caller_id, event.display_name)
        if gate.status == "EMERGENCY_BYPASS":
            return DecisionResult(
                timestamp_sec=event.timestamp_sec,
                state=SystemState.IDLE_ALLOWLISTED,
                calibrated_risk_prob=0.0,
                active_evidence=[],
                out_of_band_prompt="Cuộc gọi khẩn cấp được miễn trừ hoàn toàn.",
            )

        if gate.status == "ALLOWLISTED":
            return DecisionResult(
                timestamp_sec=event.timestamp_sec,
                state=self.current_state,
                calibrated_risk_prob=0.0,
                active_evidence=[],
            )

        new_signals: list[EvidenceSignal] = list(gate.signals)
        if extra_signals:
            new_signals.extend(extra_signals)
        audio_bypassed = False

        if event.audio_silenced:
            audio_bypassed = True
        elif event.audio_deepfake_prob is not None:
            p_audio = calibrate_probability(event.audio_deepfake_prob)
            if p_audio >= 0.40:
                new_signals.append(
                    EvidenceSignal(
                        source="engine_a_audio",
                        raw_score=event.audio_deepfake_prob,
                        calibrated_prob=p_audio,
                        reliability=0.92,
                        code="AUDIO_DEEPFAKE_SUSPECTED",
                        detail="Phát hiện nhiễu giọng nói tổng hợp / Voice Clone.",
                    )
                )

        if event.is_video:
            if event.video_deepfake_prob is not None:
                p_vid = calibrate_probability(event.video_deepfake_prob)
                if p_vid >= 0.40:
                    new_signals.append(
                        EvidenceSignal(
                            source="engine_b_spatial_srm",
                            raw_score=event.video_deepfake_prob,
                            calibrated_prob=p_vid,
                            reliability=0.80,
                            code="VIDEO_SPATIAL_ARTIFACT",
                            detail="Bất thường vùng khuôn mặt trên khung hình nén.",
                        )
                    )
            if event.lip_sync_mismatch_prob is not None:
                p_lip = calibrate_probability(event.lip_sync_mismatch_prob)
                if p_lip >= 0.45:
                    new_signals.append(
                        EvidenceSignal(
                            source="engine_b_lipsync",
                            raw_score=event.lip_sync_mismatch_prob,
                            calibrated_prob=p_lip,
                            reliability=0.78,
                            code="CLIP_LIP_SYNC_MISMATCH",
                            detail="Lệch pha khẩu hình miệng trong đoạn video ngắn.",
                        )
                    )

            is_short = event.duration_sec <= self.thresholds.short_call_sec
            is_glitchy = (
                event.blur_score >= self.thresholds.blur_threshold
                or event.is_abrupt_hangup
                or event.avg_fps < 10.0
            )
            if is_short and is_glitchy:
                new_signals.append(
                    EvidenceSignal(
                        source="engine_b_behavior",
                        raw_score=0.65,
                        calibrated_prob=0.60,
                        reliability=0.65,
                        code="SHORT_GLITCHY_VIDEO_CALL",
                        detail="Cuộc gọi video từ người lạ rất ngắn, mờ/giật hoặc cúp máy đột ngột.",
                    )
                )

        if event.transcript.strip():
            ctx = self.context_analyzer.analyze(event.transcript, source_tag="engine_c_voice")
            new_signals.extend(ctx.signals)

        key = self._counterparty_key(event.caller_id, event.display_name)
        return self._update_session_and_decide(
            session_key=key,
            timestamp_sec=event.timestamp_sec,
            counterparty_name=event.display_name or event.caller_id,
            new_signals=new_signals,
            audio_bypassed=audio_bypassed,
        )

    def process_chat(
        self,
        event: ChatEvent,
        extra_signals: list[EvidenceSignal] | None = None,
    ) -> DecisionResult:
        """Evaluate incoming Zalo/Messenger/SMS chat preview and merge into counterparty session."""
        self._expire_sessions_if_needed(event.timestamp_sec)

        gate = self.gatekeeper.evaluate_counterparty(event.sender_id, event.display_name)
        if gate.status in {"EMERGENCY_BYPASS", "ALLOWLISTED"}:
            return DecisionResult(
                timestamp_sec=event.timestamp_sec,
                state=self.current_state,
                calibrated_risk_prob=0.0,
                active_evidence=[],
            )

        new_signals: list[EvidenceSignal] = list(gate.signals)
        ctx = self.context_analyzer.analyze(event.text, source_tag="engine_c_chat")
        new_signals.extend(ctx.signals)
        if extra_signals:
            new_signals.extend(extra_signals)

        key = self._counterparty_key(event.sender_id, event.display_name)
        existing = self.sessions.get(key)
        has_content_signals = bool(ctx.signals or extra_signals)
        if existing is not None and not has_content_signals:
            return DecisionResult(
                timestamp_sec=event.timestamp_sec,
                state=existing.state,
                calibrated_risk_prob=existing.max_risk_prob,
                active_evidence=list(existing.signals.values()),
            )

        return self._update_session_and_decide(
            session_key=key,
            timestamp_sec=event.timestamp_sec,
            counterparty_name=event.display_name or event.sender_id,
            new_signals=new_signals,
        )

    def process_app_usage(self, event: AppUsageEvent) -> DecisionResult:
        """Intercept banking/wallet launches during suspicion sessions and remote-access installs."""
        self._expire_sessions_if_needed(event.timestamp_sec)
        pkg = (event.package_name or "").strip()

        is_remote_tool = pkg in REMOTE_ACCESS_PACKAGES
        is_sideload = event.event_type == "PACKAGE_INSTALLED_SIDELOAD"
        is_banking = pkg in VN_BANKING_PACKAGES

        top_session = self.active_session

        if is_remote_tool or is_sideload:
            code = "REMOTE_ACCESS_APP_DETECTED" if is_remote_tool else "UNKNOWN_APK_SIDELOADED"
            sig = EvidenceSignal(
                source="point_of_loss_guard",
                raw_score=0.96,
                calibrated_prob=0.95,
                reliability=0.96,
                code=code,
                detail=f"Phát hiện cài đặt/mở ứng dụng rủi ro cao: {pkg}",
            )
            target_key = (
                self._find_key_for_session(top_session) if top_session is not None else "__pol_guard__"
            )
            return self._update_session_and_decide(
                session_key=target_key,
                timestamp_sec=event.timestamp_sec,
                counterparty_name=top_session.counterparty_name if top_session else "PointOfLossGuard",
                new_signals=[sig],
                point_of_loss=True,
                event_type="POINT_OF_LOSS_REMOTE_OR_APK",
            )

        if is_banking and top_session is not None:
            sig = EvidenceSignal(
                source="point_of_loss_guard",
                raw_score=0.95,
                calibrated_prob=0.94,
                reliability=0.95,
                code="BANKING_APP_OPENED_DURING_SESSION",
                detail=f"Mở ứng dụng tài chính ({pkg}) ngay sau cuộc gọi/tin nhắn nghi vấn.",
            )
            target_key = self._find_key_for_session(top_session)
            return self._update_session_and_decide(
                session_key=target_key,
                timestamp_sec=event.timestamp_sec,
                counterparty_name=top_session.counterparty_name,
                new_signals=[sig],
                point_of_loss=True,
                event_type="POINT_OF_LOSS_BANKING_INTERCEPT",
            )

        return DecisionResult(
            timestamp_sec=event.timestamp_sec,
            state=self.current_state,
            calibrated_risk_prob=top_session.max_risk_prob if top_session else 0.0,
            active_evidence=list(top_session.signals.values()) if top_session else [],
        )

    def handle_dial_attempt(self, phone_number: str) -> bool:
        """Safety invariant: never block calls to 113/114/115 regardless of active alerts."""
        if is_emergency_number(phone_number):
            return True
        return True

    @staticmethod
    def _counterparty_key(raw_id: str, display_name: str) -> str:
        norm_id = (raw_id or "").strip().lower()
        return norm_id if norm_id else f"name:{(display_name or 'unknown').strip().lower()}"

    def _find_key_for_session(self, target: SuspicionSession) -> str:
        for k, sess in self.sessions.items():
            if sess.session_id == target.session_id:
                return k
        return "__pol_guard__"

    def _expire_sessions_if_needed(self, current_ts_sec: float) -> None:
        expired_keys = [k for k, s in self.sessions.items() if s.is_expired(current_ts_sec)]
        for k in expired_keys:
            del self.sessions[k]
        top = self.active_session
        self.current_state = top.state if top is not None else SystemState.IDLE_ALLOWLISTED

    def _update_session_and_decide(
        self,
        session_key: str,
        timestamp_sec: float,
        counterparty_name: str,
        new_signals: list[EvidenceSignal],
        audio_bypassed: bool = False,
        point_of_loss: bool = False,
        event_type: str = "CROSS_CHANNEL_SCAM_ALERT",
    ) -> DecisionResult:
        session = self.sessions.get(session_key)
        if not new_signals and session is None:
            top = self.active_session
            self.current_state = top.state if top is not None else SystemState.IDLE_ALLOWLISTED
            return DecisionResult(
                timestamp_sec=timestamp_sec,
                state=SystemState.IDLE_ALLOWLISTED,
                calibrated_risk_prob=0.0,
                active_evidence=[],
                audio_bypassed_silenced=audio_bypassed,
            )

        if session is None:
            self._session_seq += 1
            session = SuspicionSession(
                session_id=f"sess_{self._session_seq:04d}",
                started_at_sec=timestamp_sec,
                last_event_sec=timestamp_sec,
                ttl_sec=self.thresholds.session_ttl_sec,
                counterparty_name=counterparty_name,
            )
            self.sessions[session_key] = session
        else:
            session.last_event_sec = timestamp_sec

        for sig in new_signals:
            existing = session.signals.get(sig.code)
            if existing is None or sig.calibrated_prob > existing.calibrated_prob:
                session.signals[sig.code] = sig

        all_signals = list(session.signals.values())
        p_risk = compute_noisy_or(all_signals)
        session.max_risk_prob = max(session.max_risk_prob, p_risk)

        if p_risk >= self.thresholds.tau_red or point_of_loss:
            next_state = SystemState.RED_INTERCEPT
        elif p_risk >= self.thresholds.tau_yellow:
            next_state = SystemState.YELLOW_VERIFY
        elif p_risk >= self.thresholds.tau_uncertain:
            next_state = SystemState.SUSPICION_SESSION
        else:
            next_state = SystemState.MONITORING

        session.state = next_state

        prompt = ""
        sos_payload: LeastPrivilegeSosPayload | None = None
        if next_state == SystemState.YELLOW_VERIFY:
            prompt = (
                "Cẩn trọng: Hãy hỏi Mật khẩu Gia đình hoặc bấm Tạm dừng — Gọi lại số đã lưu."
            )
        elif next_state == SystemState.RED_INTERCEPT:
            self._sos_seq += 1
            prompt = (
                "KHOAN CHUYỂN TIỀN! Có dấu hiệu giả mạo hoặc cài app nguy hiểm. "
                "Bấm TẠM DỪNG — GỌI LẠI SỐ ĐÃ LƯU để xác minh với người thân."
            )
            sos_payload = LeastPrivilegeSosPayload(
                alert_id=f"sos_{session.session_id}_{self._sos_seq:04d}_{int(timestamp_sec * 1000)}",
                schema_version="2.0",
                timestamp_sec=timestamp_sec,
                elderly_profile_id=self.elderly_profile_id,
                event_type=event_type,
                state=next_state,
                calibrated_risk_prob=p_risk,
                active_session_minutes=(timestamp_sec - session.started_at_sec) / 60.0,
                evidence_codes=sorted(session.signals.keys()),
                transcript_included=False,
            )

        if next_state == SystemState.MONITORING:
            self.sessions.pop(session_key, None)

        top = self.active_session
        self.current_state = top.state if top is not None else SystemState.IDLE_ALLOWLISTED

        return DecisionResult(
            timestamp_sec=timestamp_sec,
            state=next_state,
            calibrated_risk_prob=p_risk,
            active_evidence=all_signals,
            point_of_loss_triggered=point_of_loss,
            audio_bypassed_silenced=audio_bypassed,
            out_of_band_prompt=prompt,
            sos_payload=sos_payload,
        )
