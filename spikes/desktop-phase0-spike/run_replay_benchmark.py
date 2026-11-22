"""Run the Phase 0 Offline Replay Evaluation Harness on Vietnamese scenarios."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from tabulate import tabulate

ROOT_DIR = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from shield_core.replay_harness import ReplayHarness


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Offline Replay Benchmark for Shield v2.0")
    parser.add_argument(
        "--scenarios",
        type=Path,
        default=Path(__file__).resolve().parent / "scenarios" / "vietnam_phase0_scenarios.jsonl",
        help="Path to JSONL scenario file",
    )
    args = parser.parse_args()

    harness = ReplayHarness()
    scenarios = harness.load_jsonl(args.scenarios)
    report = harness.evaluate(scenarios)

    rows = [
        [
            o.scenario_id,
            o.label,
            o.highest_state.value,
            f"{o.max_risk_prob:.3f}",
            "YES" if o.red_intercepted else "NO",
            f"{o.time_to_red_sec:.1f}s" if o.time_to_red_sec is not None else "-",
            "PASS" if o.passed_expectation else "FAIL",
        ]
        for o in report.outcomes
    ]
    print("\n=== OFFLINE REPLAY EVALUATION HARNESS (v2.0 PROVISIONAL THRESHOLDS) ===\n")
    print(
        tabulate(
            rows,
            headers=[
                "Scenario ID",
                "Label",
                "Highest State",
                "Max P_risk",
                "RED?",
                "Time-to-RED",
                "Result",
            ],
            tablefmt="github",
        )
    )
    print("\n=== SUMMARY KPIs ===")
    print(f"- Attack Detection (RED):        {report.attack_detected_red}/{report.attack_total}")
    print(f"- Benign False Red Alerts:       {report.benign_false_red}/{report.benign_total}")
    print(
        f"- Projected False Red / User/Mo: {report.projected_false_red_per_user_month:.2f} "
        "(target <= 0.50)"
    )
    print(f"- Emergency 113/114/115 Blocked: {report.emergency_blocked_or_red}/{report.emergency_total}")
    print(f"- Transcript Privacy Leaks:      {report.privacy_leaks_transcript_sent}")

    all_passed = all(o.passed_expectation for o in report.outcomes)
    return 0 if all_passed and report.privacy_leaks_transcript_sent == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
