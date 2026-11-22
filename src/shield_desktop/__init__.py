"""Desktop Research Testbed & Modular AI Adapters (Phase 1 Track A)."""

from __future__ import annotations

from typing import Any

from .audio_detector import (
    AudioDeepfakeDetector,
    AudioDetectionResult,
    HeuristicAcousticBaseline,
    OnnxAudioDetector,
    load_audio_detector,
)
from .context_slm_adapter import ContextSlmAdapter, SlmAdapterResult
from .video_detector import (
    HeuristicVideoBaseline,
    OnnxVideoSrmDetector,
    VideoDetectionResult,
    VideoForensicsDetector,
    load_video_detector,
)


def __getattr__(name: str) -> Any:
    """Lazy-load runner to avoid runpy RuntimeWarning on `python -m shield_desktop.desktop_runner`."""
    if name == "DesktopShieldRunner":
        from .desktop_runner import DesktopShieldRunner

        return DesktopShieldRunner
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "AudioDeepfakeDetector",
    "AudioDetectionResult",
    "ContextSlmAdapter",
    "DesktopShieldRunner",
    "HeuristicAcousticBaseline",
    "HeuristicVideoBaseline",
    "OnnxAudioDetector",
    "OnnxVideoSrmDetector",
    "SlmAdapterResult",
    "VideoDetectionResult",
    "VideoForensicsDetector",
    "load_audio_detector",
    "load_video_detector",
]
