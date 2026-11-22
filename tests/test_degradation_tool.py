"""Tests for the Phase 0 audio/video VoIP degradation measurement tool."""

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
SPIKE_DIR = ROOT_DIR / "spikes" / "desktop-phase0-spike"
if str(SPIKE_DIR) not in sys.path:
    sys.path.insert(0, str(SPIKE_DIR))

from measure_degradation import run_synthetic_self_test


def test_synthetic_degradation_captures_hf_and_srm_loss() -> None:
    res = run_synthetic_self_test()
    assert res["mode"] == "synthetic_self_test"

    audio = res["audio"]
    assert audio["voip_degraded"]["packet_drop_silence_ratio"] > 0.1
    assert audio["hf_retention_ratio"] < 0.05

    video = res["video"]
    assert video["clean"]["laplacian_sharpness"] > video["voip_degraded"]["laplacian_sharpness"] * 10
    assert video["srm_retention_ratio"] < 0.05
