"""Domain models and schemas for Realtime Deepfake Shield v2.0."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class SystemState(str, Enum):
    """Five-level cross-channel state machine defined in architecture v2.0."""

    IDLE_ALLOWLISTED = "IDLE_ALLOWLISTED"
    MONITORING = "MONITORING"
    SUSPICION_SESSION = "SUSPICION_SESSION"
    YELLOW_VERIFY = "YELLOW_VERIFY"
    RED_INTERCEPT = "RED_INTERCEPT"


class TacticTag(str, Enum):
    """Six Vietnamese social-engineering manipulation tactics."""

    AUTHORITY_IMPERSONATION = "AUTHORITY_IMPERSONATION"
    RELATIVE_EMERGENCY = "RELATIVE_EMERGENCY"
    URGENCY_FEAR = "URGENCY_FEAR"
    SECRECY_ISOLATION = "SECRECY_ISOLATION"
    FINANCIAL_TRANSFER = "FINANCIAL_TRANSFER"
    MALICIOUS_APP_INSTALL = "MALICIOUS_APP_INSTALL"


class ChannelType(str, Enum):
    """Supported communication and device telemetry channels."""

    ZALO_VIDEO = "ZALO_VIDEO"
    ZALO_VOICE = "ZALO_VOICE"
    ZALO_CHAT = "ZALO_CHAT"
    MESSENGER_VIDEO = "MESSENGER_VIDEO"
    MESSENGER_CHAT = "MESSENGER_CHAT"
    PSTN_CALL = "PSTN_CALL"
    SMS = "SMS"
    APP_LAUNCH = "APP_LAUNCH"


@dataclass(slots=True)
class CallEvent:
    """Incoming or completed call telemetry observed on client device."""

    timestamp_sec: float
    channel: ChannelType
    caller_id: str
    display_name: str
    duration_sec: float
    is_video: bool = False
    is_abrupt_hangup: bool = False
    blur_score: float = 0.0
    avg_fps: float = 24.0
    audio_deepfake_prob: float | None = None
    audio_silenced: bool = False
    video_deepfake_prob: float | None = None
    lip_sync_mismatch_prob: float | None = None
    transcript: str = ""


@dataclass(slots=True)
class ChatEvent:
    """Chat or SMS notification preview observed during/after call."""

    timestamp_sec: float
    channel: ChannelType
    sender_id: str
    display_name: str
    text: str


@dataclass(slots=True)
class AppUsageEvent:
    """Foreground app launch or package installation observed on device."""

    timestamp_sec: float
    package_name: str
    event_type: str = "APP_OPENED"  # APP_OPENED | PACKAGE_INSTALLED_SIDELOAD


@dataclass(slots=True)
class EvidenceSignal:
    """Single calibrated risk signal contributed by a detector or heuristic."""

    source: str
    raw_score: float
    calibrated_prob: float
    reliability: float
    code: str
    detail: str = ""


@dataclass(slots=True)
class SuspicionSession:
    """Ephemeral in-RAM cross-channel suspicion session with bounded TTL."""

    session_id: str
    started_at_sec: float
    last_event_sec: float
    ttl_sec: float
    counterparty_name: str
    signals: dict[str, EvidenceSignal] = field(default_factory=dict)
    max_risk_prob: float = 0.0
    state: SystemState = SystemState.SUSPICION_SESSION

    def is_expired(self, current_ts_sec: float) -> bool:
        """Return True when the session has exceeded its inactivity TTL."""
        return (current_ts_sec - self.last_event_sec) > self.ttl_sec


@dataclass(slots=True)
class LeastPrivilegeSosPayload:
    """Guardian SOS notification payload compliant with Law 91/2025/QH15.

    By design, `transcript_included` defaults to False and no raw audio, video,
    or verbatim message content is attached.
    """

    alert_id: str
    schema_version: str
    timestamp_sec: float
    elderly_profile_id: str
    event_type: str
    state: SystemState
    calibrated_risk_prob: float
    active_session_minutes: float
    evidence_codes: list[str]
    transcript_included: bool = False
    recommended_action: str = (
        "Gọi lại trực tiếp bằng số di động đã lưu để kiểm chứng với Cha/Mẹ ngay."
    )

    def to_dict(self) -> dict[str, Any]:
        """Serialize payload into a Least-Privilege JSON dictionary (no free-text fields)."""
        return {
            "alert_id": self.alert_id,
            "schema_version": self.schema_version,
            "timestamp_sec": round(self.timestamp_sec, 3),
            "elderly_profile_id": self.elderly_profile_id,
            "event_type": self.event_type,
            "decision": {
                "state": self.state.value,
                "calibrated_risk_prob": round(self.calibrated_risk_prob, 4),
                "active_session_minutes": round(self.active_session_minutes, 2),
            },
            "evidence_codes": list(self.evidence_codes),
            "transcript_included": self.transcript_included,
        }


@dataclass(slots=True)
class DecisionResult:
    """Output produced by the cross-channel state machine per incoming event."""

    timestamp_sec: float
    state: SystemState
    calibrated_risk_prob: float
    active_evidence: list[EvidenceSignal]
    point_of_loss_triggered: bool = False
    audio_bypassed_silenced: bool = False
    out_of_band_prompt: str = ""
    sos_payload: LeastPrivilegeSosPayload | None = None
