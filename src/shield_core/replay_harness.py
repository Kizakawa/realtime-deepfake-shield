"""Offline replay evaluation harness for calibrating thresholds and measuring KPIs."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .fusion_engine import CrossChannelShieldEngine, ProvisionalThresholds
from .layer0_gatekeeper import FamilyAllowlist
from .models import AppUsageEvent, CallEvent, ChannelType, ChatEvent, DecisionResult, SystemState


@dataclass(slots=True)
class ScenarioRecord:
    """Single cross-channel scenario loaded from JSONL replay corpus."""

    scenario_id: str
    label: str  # ATTACK | BENIGN | EMERGENCY
    description: str
    verified_caller_ids: list[str] = field(default_factory=list)
    verified_relative_names: list[str] = field(default_factory=list)
    events: list[dict[str, Any]] = field(default_factory=list)


@dataclass(slots=True)
class ScenarioOutcome:
    """Replay outcome for one scenario."""

    scenario_id: str
    label: str
    highest_state: SystemState
    max_risk_prob: float
    red_intercepted: bool
    time_to_red_sec: float | None
    sos_transcript_included: bool
    passed_expectation: bool


@dataclass(slots=True)
class ReplayBenchmarkReport:
    """Aggregated evaluation KPIs across the replay corpus."""

    total_scenarios: int
    attack_total: int
    attack_detected_red_or_yellow: int
    attack_detected_red: int
    benign_total: int
    benign_false_red: int
    projected_false_red_per_user_month: float
    emergency_total: int
    emergency_blocked_or_red: int
    privacy_leaks_transcript_sent: int
    outcomes: list[ScenarioOutcome]


_STATE_PRIORITY: dict[SystemState, int] = {
    SystemState.IDLE_ALLOWLISTED: 0,
    SystemState.MONITORING: 1,
    SystemState.SUSPICION_SESSION: 2,
    SystemState.YELLOW_VERIFY: 3,
    SystemState.RED_INTERCEPT: 4,
}


class ReplayHarness:
    """Replays recorded/synthetic cross-channel scenarios against CrossChannelShieldEngine."""

    def __init__(self, thresholds: ProvisionalThresholds | None = None) -> None:
        self.thresholds = thresholds or ProvisionalThresholds()

    @staticmethod
    def load_jsonl(path: str | Path) -> list[ScenarioRecord]:
        """Load JSONL scenario corpus."""
        records: list[ScenarioRecord] = []
        with Path(path).open("r", encoding="utf-8") as fh:
            for line_num, raw_line in enumerate(fh, start=1):
                stripped = raw_line.strip()
                if not stripped:
                    continue
                obj = json.loads(stripped)
                records.append(
                    ScenarioRecord(
                        scenario_id=obj["scenario_id"],
                        label=obj["label"],
                        description=obj.get("description", f"Scenario {line_num}"),
                        verified_caller_ids=obj.get("verified_caller_ids", []),
                        verified_relative_names=obj.get("verified_relative_names", []),
                        events=obj.get("events", []),
                    )
                )
        return records

    def run_scenario(self, scenario: ScenarioRecord) -> ScenarioOutcome:
        """Execute all events in a scenario on an isolated engine instance."""
        allowlist = FamilyAllowlist(
            verified_caller_ids=set(scenario.verified_caller_ids),
            verified_relative_names=set(scenario.verified_relative_names),
        )
        engine = CrossChannelShieldEngine(allowlist=allowlist, thresholds=self.thresholds)

        highest_state = SystemState.IDLE_ALLOWLISTED
        max_prob = 0.0
        first_ts: float | None = None
        time_to_red_sec: float | None = None
        transcript_leaked = False

        for raw_evt in scenario.events:
            kind = raw_evt["kind"]
            ts = float(raw_evt["timestamp_sec"])
            if first_ts is None:
                first_ts = ts

            res: DecisionResult
            if kind == "call":
                res = engine.process_call(
                    CallEvent(
                        timestamp_sec=ts,
                        channel=ChannelType(raw_evt["channel"]),
                        caller_id=raw_evt["caller_id"],
                        display_name=raw_evt.get("display_name", ""),
                        duration_sec=float(raw_evt["duration_sec"]),
                        is_video=bool(raw_evt.get("is_video", False)),
                        is_abrupt_hangup=bool(raw_evt.get("is_abrupt_hangup", False)),
                        blur_score=float(raw_evt.get("blur_score", 0.0)),
                        avg_fps=float(raw_evt.get("avg_fps", 24.0)),
                        audio_deepfake_prob=raw_evt.get("audio_deepfake_prob"),
                        audio_silenced=bool(raw_evt.get("audio_silenced", False)),
                        video_deepfake_prob=raw_evt.get("video_deepfake_prob"),
                        lip_sync_mismatch_prob=raw_evt.get("lip_sync_mismatch_prob"),
                        transcript=raw_evt.get("transcript", ""),
                    )
                )
            elif kind == "chat":
                res = engine.process_chat(
                    ChatEvent(
                        timestamp_sec=ts,
                        channel=ChannelType(raw_evt["channel"]),
                        sender_id=raw_evt["sender_id"],
                        display_name=raw_evt.get("display_name", ""),
                        text=raw_evt["text"],
                    )
                )
            elif kind == "app_usage":
                res = engine.process_app_usage(
                    AppUsageEvent(
                        timestamp_sec=ts,
                        package_name=raw_evt["package_name"],
                        event_type=raw_evt.get("event_type", "APP_OPENED"),
                    )
                )
            else:
                raise ValueError(f"Unsupported event kind: {kind}")

            if _STATE_PRIORITY[res.state] > _STATE_PRIORITY[highest_state]:
                highest_state = res.state
            max_prob = max(max_prob, res.calibrated_risk_prob)
            if res.state == SystemState.RED_INTERCEPT and time_to_red_sec is None:
                time_to_red_sec = ts - first_ts
            if res.sos_payload is not None and res.sos_payload.transcript_included:
                transcript_leaked = True

        red_intercepted = highest_state == SystemState.RED_INTERCEPT
        if scenario.label == "ATTACK":
            passed = red_intercepted and not transcript_leaked
        elif scenario.label in {"BENIGN", "EMERGENCY"}:
            passed = highest_state in {
                SystemState.IDLE_ALLOWLISTED,
                SystemState.MONITORING,
                SystemState.SUSPICION_SESSION,
            }
        else:
            raise ValueError(f"Unknown scenario label: {scenario.label}")

        return ScenarioOutcome(
            scenario_id=scenario.scenario_id,
            label=scenario.label,
            highest_state=highest_state,
            max_risk_prob=max_prob,
            red_intercepted=red_intercepted,
            time_to_red_sec=time_to_red_sec,
            sos_transcript_included=transcript_leaked,
            passed_expectation=passed,
        )

    def evaluate(
        self,
        scenarios: list[ScenarioRecord],
        assumed_benign_events_per_month: float = 150.0,
    ) -> ReplayBenchmarkReport:
        """Evaluate all scenarios and compute user-centric KPI metrics."""
        outcomes = [self.run_scenario(sc) for sc in scenarios]
        attacks = [o for o in outcomes if o.label == "ATTACK"]
        benigns = [o for o in outcomes if o.label == "BENIGN"]
        emergencies = [o for o in outcomes if o.label == "EMERGENCY"]

        benign_false_red = sum(1 for o in benigns if o.red_intercepted)
        false_red_rate = (benign_false_red / len(benigns)) if benigns else 0.0
        projected_monthly = false_red_rate * assumed_benign_events_per_month

        return ReplayBenchmarkReport(
            total_scenarios=len(outcomes),
            attack_total=len(attacks),
            attack_detected_red_or_yellow=sum(
                1
                for o in attacks
                if o.highest_state in {SystemState.YELLOW_VERIFY, SystemState.RED_INTERCEPT}
            ),
            attack_detected_red=sum(1 for o in attacks if o.red_intercepted),
            benign_total=len(benigns),
            benign_false_red=benign_false_red,
            projected_false_red_per_user_month=projected_monthly,
            emergency_total=len(emergencies),
            emergency_blocked_or_red=sum(1 for o in emergencies if o.red_intercepted),
            privacy_leaks_transcript_sent=sum(1 for o in outcomes if o.sos_transcript_included),
            outcomes=outcomes,
        )
