"""Core v2.0 package for Realtime Deepfake Shield."""

from .context_engine import VietnameseContextAnalyzer, validate_slm_json_output, wrap_untrusted_input
from .fusion_engine import (
    CrossChannelShieldEngine,
    ProvisionalThresholds,
    calibrate_probability,
    compute_noisy_or,
)
from .layer0_gatekeeper import (
    EMERGENCY_NUMBERS,
    REMOTE_ACCESS_PACKAGES,
    VN_BANKING_PACKAGES,
    FamilyAllowlist,
    GatekeeperDecision,
    Layer0Gatekeeper,
    is_emergency_number,
    normalize_vietnamese,
)
from .models import (
    AppUsageEvent,
    CallEvent,
    ChannelType,
    ChatEvent,
    DecisionResult,
    EvidenceSignal,
    LeastPrivilegeSosPayload,
    SuspicionSession,
    SystemState,
    TacticTag,
)
from .replay_harness import ReplayBenchmarkReport, ReplayHarness, ScenarioRecord

__all__ = [
    "AppUsageEvent",
    "CallEvent",
    "ChannelType",
    "ChatEvent",
    "CrossChannelShieldEngine",
    "DecisionResult",
    "EMERGENCY_NUMBERS",
    "EvidenceSignal",
    "FamilyAllowlist",
    "GatekeeperDecision",
    "Layer0Gatekeeper",
    "LeastPrivilegeSosPayload",
    "ProvisionalThresholds",
    "REMOTE_ACCESS_PACKAGES",
    "ReplayBenchmarkReport",
    "ReplayHarness",
    "ScenarioRecord",
    "SuspicionSession",
    "SystemState",
    "TacticTag",
    "VN_BANKING_PACKAGES",
    "VietnameseContextAnalyzer",
    "calibrate_probability",
    "compute_noisy_or",
    "is_emergency_number",
    "normalize_vietnamese",
    "validate_slm_json_output",
    "wrap_untrusted_input",
]
