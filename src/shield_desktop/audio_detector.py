"""Modular Audio Anti-Spoofing adapters (ONNX AASIST-L + resampling + CPU baseline)."""

from __future__ import annotations

import logging
import math
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from shield_core.fusion_engine import calibrate_probability

logger = logging.getLogger(__name__)


def resample_audio_16k(
    samples: np.ndarray,
    orig_sr: int,
    target_sr: int = 16000,
) -> np.ndarray:
    """Resample mono float32 waveform to `target_sr` (16 kHz) with anti-alias smoothing."""
    arr = np.asarray(samples, dtype=np.float32).reshape(-1)
    if arr.size == 0 or orig_sr <= 0 or orig_sr == target_sr:
        return arr

    # Apply simple low-pass moving average prior to downsampling (e.g., 48 kHz -> 16 kHz)
    # so ultrasonic/high-band noise does not alias into the 0-8 kHz speech band.
    if orig_sr > target_sr:
        decim_factor = max(2, int(round(orig_sr / float(target_sr))))
        kernel = np.ones(decim_factor, dtype=np.float32) / float(decim_factor)
        arr = np.convolve(arr, kernel, mode="same").astype(np.float32)

    new_len = max(1, int(round(arr.size * float(target_sr) / float(orig_sr))))
    old_idx = np.linspace(0.0, 1.0, num=arr.size, endpoint=False)
    new_idx = np.linspace(0.0, 1.0, num=new_len, endpoint=False)
    return np.interp(new_idx, old_idx, arr).astype(np.float32)


@dataclass(slots=True)
class AudioDetectionResult:
    """Normalized prediction returned by Engine A adapters."""

    raw_score: float
    calibrated_prob: float
    backend_name: str


class AudioDeepfakeDetector(ABC):
    """Abstract interface for streaming mono audio spoof detectors."""

    @abstractmethod
    def predict(self, samples_16k: np.ndarray, sample_rate_hz: int = 16000) -> AudioDetectionResult:
        """Score a mono float32 waveform window in [-1, 1] (auto-resampled to 16 kHz)."""


class OnnxAudioDetector(AudioDeepfakeDetector):
    """ONNX Runtime inference wrapper for AASIST / AASIST-L INT8/FP32 models.

    Note on class index:
        Official `clovaai/aasist` checkpoints emit 2 logits `[spoof, bonafide]`,
        where index `0` is the spoof/deepfake class (`spoof_class_index=0` default).
        Pass `spoof_class_index=1` if using custom exports ordered `[bonafide, spoof]`.
    """

    def __init__(
        self,
        model_path: str | Path,
        target_samples: int = 64600,
        spoof_class_index: int = 0,
        temperature: float = 1.0,
        bias: float = 0.0,
    ) -> None:
        import onnxruntime as ort

        if spoof_class_index not in (0, 1):
            raise ValueError("spoof_class_index must be 0 or 1")

        self.model_path = Path(model_path)
        self.target_samples = target_samples
        self.spoof_class_index = spoof_class_index
        self.temperature = temperature
        self.bias = bias
        self.session = ort.InferenceSession(
            str(self.model_path),
            providers=["CPUExecutionProvider"],
        )
        self.input_name = self.session.get_inputs()[0].name

    def _prepare_window(self, samples: np.ndarray, sample_rate_hz: int) -> np.ndarray:
        arr = resample_audio_16k(samples, orig_sr=sample_rate_hz, target_sr=16000)
        if arr.size == 0:
            arr = np.zeros(self.target_samples, dtype=np.float32)
        elif arr.size < self.target_samples:
            reps = math.ceil(self.target_samples / arr.size)
            arr = np.tile(arr, reps)[: self.target_samples]
        elif arr.size > self.target_samples:
            arr = arr[-self.target_samples :]
        return arr.reshape(1, self.target_samples)

    @staticmethod
    def logits_to_spoof_prob(logits: np.ndarray, spoof_class_index: int = 0) -> float:
        """Convert 1D or 2-class model logits into spoof probability."""
        flat = np.asarray(logits, dtype=np.float64).reshape(-1)
        if flat.size == 1:
            return float(1.0 / (1.0 + math.exp(-float(flat[0]))))
        if not (0 <= spoof_class_index < flat.size):
            raise ValueError(
                f"spoof_class_index {spoof_class_index} out of bounds for {flat.size} logits"
            )
        shifted = flat - np.max(flat)
        exps = np.exp(shifted)
        probs = exps / np.sum(exps)
        return float(probs[spoof_class_index])

    def predict(self, samples_16k: np.ndarray, sample_rate_hz: int = 16000) -> AudioDetectionResult:
        window = self._prepare_window(samples_16k, sample_rate_hz=sample_rate_hz)
        outputs = self.session.run(None, {self.input_name: window})
        raw_prob = self.logits_to_spoof_prob(
            outputs[0],
            spoof_class_index=self.spoof_class_index,
        )
        cal_prob = calibrate_probability(raw_prob, temperature=self.temperature, bias=self.bias)
        return AudioDetectionResult(
            raw_score=raw_prob,
            calibrated_prob=cal_prob,
            backend_name=f"onnx:{self.model_path.name}",
        )


class HeuristicAcousticBaseline(AudioDeepfakeDetector):
    """Lightweight CPU acoustic baseline used only as a pipeline stub before ONNX weights exist."""

    def predict(self, samples_16k: np.ndarray, sample_rate_hz: int = 16000) -> AudioDetectionResult:
        arr = resample_audio_16k(samples_16k, orig_sr=sample_rate_hz, target_sr=16000)
        if arr.size < 256:
            return AudioDetectionResult(0.0, 0.0, "heuristic_acoustic_baseline")

        rms = float(np.sqrt(np.mean(arr**2) + 1e-12))
        if rms < 1e-4:
            return AudioDetectionResult(0.0, 0.0, "heuristic_acoustic_baseline")

        spectrum = np.abs(np.fft.rfft(arr)) ** 2 + 1e-12
        freqs = np.fft.rfftfreq(arr.size, d=1.0 / 16000.0)
        hf_ratio = float(np.sum(spectrum[freqs >= 4000.0]) / np.sum(spectrum))
        flatness = float(np.exp(np.mean(np.log(spectrum))) / max(float(np.mean(spectrum)), 1e-12))

        cutoff_cue = 1.0 - min(hf_ratio / 0.05, 1.0)
        flatness_cue = min(flatness * 4.0, 1.0)
        raw_score = float(min(max(0.25 * cutoff_cue + 0.15 * flatness_cue, 0.0), 0.45))
        cal_prob = calibrate_probability(raw_score)
        return AudioDetectionResult(
            raw_score=round(raw_score, 4),
            calibrated_prob=round(cal_prob, 4),
            backend_name="heuristic_acoustic_baseline",
        )


def load_audio_detector(
    model_path: str | Path | None = None,
    spoof_class_index: int = 0,
) -> AudioDeepfakeDetector:
    """Load ONNX AASIST detector if weights exist; otherwise return CPU baseline."""
    if model_path is not None:
        path = Path(model_path)
        if path.is_file():
            return OnnxAudioDetector(path, spoof_class_index=spoof_class_index)
        logger.warning("Audio ONNX model not found at %s; falling back to heuristic baseline.", path)
    return HeuristicAcousticBaseline()
