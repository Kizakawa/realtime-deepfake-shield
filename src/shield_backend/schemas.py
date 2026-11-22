"""Strict Pydantic v2 schemas enforcing Auth, Least-Privilege SOS, and code-only fields."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

SafeIdStr = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9_.:-]{3,80}$")]
EvidenceCodeStr = Annotated[str, StringConstraints(pattern=r"^[A-Z][A-Z0-9_]{2,63}$")]


class ProfileRegisterRequest(BaseModel):
    """Register an elderly device profile to obtain device and pairing credentials."""

    model_config = ConfigDict(extra="forbid")

    elderly_profile_id: SafeIdStr


class GuardianPairRequest(BaseModel):
    """Pair a guardian (child/caregiver) to an elderly user profile."""

    model_config = ConfigDict(extra="forbid")

    elderly_profile_id: SafeIdStr
    guardian_id: SafeIdStr
    display_name: str = Field(min_length=1, max_length=80)
    fcm_token: str = Field(min_length=4, max_length=512)
    backup_phone_e164: Annotated[str, StringConstraints(pattern=r"^\+?[0-9]{8,16}$")]
    telegram_chat_id: str | None = Field(default=None, max_length=64)


class SosDecisionPayload(BaseModel):
    """Summary risk state sent to guardians without raw biometrics."""

    model_config = ConfigDict(extra="forbid")

    state: Literal["YELLOW_VERIFY", "RED_INTERCEPT"]
    calibrated_risk_prob: float = Field(ge=0.0, le=1.0)
    active_session_minutes: float = Field(ge=0.0)


class SosAlertRequest(BaseModel):
    """Least-privilege SOS payload: rejects free text, transcripts, and raw media."""

    model_config = ConfigDict(extra="forbid")

    alert_id: SafeIdStr
    schema_version: Literal["2.0"] = "2.0"
    timestamp_sec: float = Field(ge=0.0)
    elderly_profile_id: SafeIdStr
    event_type: EvidenceCodeStr
    decision: SosDecisionPayload
    evidence_codes: list[EvidenceCodeStr] = Field(min_length=1, max_length=20)
    transcript_included: Literal[False] = False


class SosAckRequest(BaseModel):
    """Guardian acknowledgment canceling server SMS escalation."""

    model_config = ConfigDict(extra="forbid")

    guardian_id: SafeIdStr
    action_taken: EvidenceCodeStr
    timestamp_sec: float | None = Field(default=None, ge=0.0)


class HeartbeatRequest(BaseModel):
    """Client health & permission heartbeat for anti-tamper monitoring."""

    model_config = ConfigDict(extra="forbid")

    elderly_profile_id: SafeIdStr
    timestamp_sec: float = Field(ge=0.0)
    service_running: bool
    notification_listener_ok: bool
    usage_stats_ok: bool
    active_suspicion_session: bool = False


class RemoteConfigUpdateRequest(BaseModel):
    """Versioned dynamic thresholds and package lists for MLOps remote config."""

    model_config = ConfigDict(extra="forbid")

    tau_uncertain: float = Field(gt=0.0, lt=1.0)
    tau_yellow: float = Field(gt=0.0, lt=1.0)
    tau_red: float = Field(gt=0.0, lt=1.0)
    session_ttl_sec: float = Field(ge=60.0, le=86400.0)
    banking_packages: list[SafeIdStr] = Field(min_length=1)
    remote_access_packages: list[SafeIdStr] = Field(min_length=1)
    note: str = Field(default="", max_length=200)

    @model_validator(mode="after")
    def _validate_monotonic_thresholds(self) -> RemoteConfigUpdateRequest:
        if not (self.tau_uncertain < self.tau_yellow < self.tau_red):
            raise ValueError("Thresholds must satisfy tau_uncertain < tau_yellow < tau_red")
        return self


class TelemetryCounterRequest(BaseModel):
    """Privacy-preserving anonymous aggregate counters (no raw text/media/PII)."""

    model_config = ConfigDict(extra="forbid")

    elderly_profile_hash: SafeIdStr
    device_tier: Literal["TIER_1", "TIER_2", "TIER_3"]
    silenced_audio_count: int = Field(ge=0)
    false_alarm_dismissals: int = Field(ge=0)
    avg_inference_latency_ms: float = Field(ge=0.0)
