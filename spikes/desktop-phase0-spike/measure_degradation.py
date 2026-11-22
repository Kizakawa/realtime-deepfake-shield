"""Measure audio and video forensic signal degradation across VoIP / screen capture.

Supports both real WAV/image comparisons and a synthetic `--self-test` mode
that runs on CPU using NumPy + Pillow without requiring GPU or external media.
"""

from __future__ import annotations

import argparse
import json
import wave
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

try:
    import cv2  # type: ignore
except ImportError:
    cv2 = None


@dataclass(slots=True)
class AudioSignalMetrics:
    """Acoustic degradation metrics relevant to AASIST / CodecFake robustness."""

    sample_rate_hz: int
    duration_sec: float
    rms_dbfs: float
    high_freq_ratio_above_4khz: float
    packet_drop_silence_ratio: float
    spectral_flatness: float


@dataclass(slots=True)
class VideoSignalMetrics:
    """Spatial & forensic noise metrics relevant to MobileNetV2-SRM robustness."""

    width: int
    height: int
    laplacian_sharpness: float
    srm_high_freq_energy: float
    black_frame_ratio: float


def load_wav_mono_float(path: Path) -> tuple[np.ndarray, int]:
    """Read a PCM16 WAV file into normalized float32 mono samples in [-1, 1]."""
    with wave.open(str(path), "rb") as wf:
        sr = wf.getframerate()
        channels = wf.getnchannels()
        sampwidth = wf.getsampwidth()
        frames = wf.readframes(wf.getnframes())
    if sampwidth != 2:
        raise ValueError(f"Expected 16-bit PCM WAV, got sample width {sampwidth} bytes")
    pcm = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
    if channels > 1:
        pcm = pcm.reshape(-1, channels).mean(axis=1)
    return pcm, sr


def compute_audio_metrics(samples: np.ndarray, sample_rate_hz: int) -> AudioSignalMetrics:
    """Compute RMS, high-frequency energy retention (>4kHz), silence ratio, and flatness."""
    if samples.size == 0:
        return AudioSignalMetrics(sample_rate_hz, 0.0, -120.0, 0.0, 1.0, 0.0)

    rms = float(np.sqrt(np.mean(samples**2) + 1e-12))
    rms_dbfs = float(20.0 * np.log10(max(rms, 1e-6)))

    frame_len = max(1, int(0.02 * sample_rate_hz))
    trimmed = samples[: (samples.size // frame_len) * frame_len]
    if trimmed.size > 0:
        frames = trimmed.reshape(-1, frame_len)
        frame_rms = np.sqrt(np.mean(frames**2, axis=1))
        silence_ratio = float(np.mean(frame_rms < 1e-3))
    else:
        silence_ratio = 0.0

    spectrum = np.abs(np.fft.rfft(samples)) ** 2 + 1e-12
    freqs = np.fft.rfftfreq(samples.size, d=1.0 / sample_rate_hz)
    total_energy = float(np.sum(spectrum))
    hf_energy = float(np.sum(spectrum[freqs >= 4000.0]))
    high_freq_ratio = hf_energy / total_energy

    geo_mean = float(np.exp(np.mean(np.log(spectrum))))
    arith_mean = float(np.mean(spectrum))
    spectral_flatness = geo_mean / max(arith_mean, 1e-12)

    return AudioSignalMetrics(
        sample_rate_hz=sample_rate_hz,
        duration_sec=round(samples.size / float(sample_rate_hz), 3),
        rms_dbfs=round(rms_dbfs, 2),
        high_freq_ratio_above_4khz=round(high_freq_ratio, 5),
        packet_drop_silence_ratio=round(silence_ratio, 4),
        spectral_flatness=round(spectral_flatness, 5),
    )


def _convolve_3x3(gray: np.ndarray, kernel: np.ndarray) -> np.ndarray:
    padded = np.pad(gray, ((1, 1), (1, 1)), mode="edge")
    out = np.zeros_like(gray, dtype=np.float32)
    for dy in range(3):
        for dx in range(3):
            out += kernel[dy, dx] * padded[dy : dy + gray.shape[0], dx : dx + gray.shape[1]]
    return out


def compute_video_metrics(rgb_frame: np.ndarray) -> VideoSignalMetrics:
    """Compute Laplacian sharpness, SRM high-pass residual energy, and black-frame check."""
    if rgb_frame.ndim != 3 or rgb_frame.shape[2] < 3:
        raise ValueError("Expected RGB frame of shape (H, W, 3)")
    h, w = rgb_frame.shape[:2]
    gray = np.dot(rgb_frame[..., :3].astype(np.float32), [0.299, 0.587, 0.114])

    black_ratio = float(np.mean(gray < 5.0))

    if cv2 is not None:
        lap = cv2.Laplacian(gray, cv2.CV_32F)
    else:
        lap_kernel = np.array([[0.0, 1.0, 0.0], [1.0, -4.0, 1.0], [0.0, 1.0, 0.0]], dtype=np.float32)
        lap = _convolve_3x3(gray, lap_kernel)
    sharpness = float(np.var(lap))

    # Simplified SRM 2nd-order high-pass residual kernel used in spatial forensics.
    srm_kernel = np.array([[-1.0, 2.0, -1.0], [2.0, -4.0, 2.0], [-1.0, 2.0, -1.0]], dtype=np.float32) / 4.0
    srm_res = _convolve_3x3(gray, srm_kernel)
    srm_energy = float(np.mean(srm_res**2))

    return VideoSignalMetrics(
        width=w,
        height=h,
        laplacian_sharpness=round(sharpness, 3),
        srm_high_freq_energy=round(srm_energy, 4),
        black_frame_ratio=round(black_ratio, 4),
    )


def load_image_rgb(path: Path) -> np.ndarray:
    """Load an image file as an RGB uint8 NumPy array."""
    with Image.open(path) as img:
        return np.array(img.convert("RGB"))


def run_synthetic_self_test() -> dict[str, object]:
    """Simulate clean vs Zalo-compressed audio & video to verify metric sensitivity."""
    rng = np.random.default_rng(42)
    sr = 16000
    t = np.linspace(0.0, 2.0, sr * 2, endpoint=False, dtype=np.float32)
    clean_audio = (
        0.35 * np.sin(2 * np.pi * 220.0 * t)
        + 0.25 * np.sin(2 * np.pi * 5200.0 * t)
        + 0.04 * rng.normal(size=t.size).astype(np.float32)
    )
    # Simulate narrowband VoIP low-pass + packet drops (300ms drop).
    zalo_audio = 0.35 * np.sin(2 * np.pi * 220.0 * t) + 0.005 * rng.normal(size=t.size).astype(np.float32)
    zalo_audio[8000:12800] = 0.0

    clean_a_metrics = compute_audio_metrics(clean_audio, sr)
    zalo_a_metrics = compute_audio_metrics(zalo_audio, sr)

    # Create textured 224x224 synthetic face ROI and compressed blurred copy.
    xx, yy = np.meshgrid(np.arange(224), np.arange(224))
    clean_img = np.stack(
        [
            ((xx * 3 + yy * 5) % 256).astype(np.uint8),
            ((xx * 7 + rng.integers(0, 18, (224, 224))) % 256).astype(np.uint8),
            ((yy * 4 + rng.integers(0, 18, (224, 224))) % 256).astype(np.uint8),
        ],
        axis=-1,
    )
    degraded_pil = (
        Image.fromarray(clean_img)
        .resize((112, 112), Image.Resampling.BILINEAR)
        .filter(ImageFilter.GaussianBlur(radius=1.8))
        .resize((224, 224), Image.Resampling.BILINEAR)
    )
    degraded_img = np.array(degraded_pil)

    clean_v_metrics = compute_video_metrics(clean_img)
    zalo_v_metrics = compute_video_metrics(degraded_img)

    return {
        "mode": "synthetic_self_test",
        "audio": {
            "clean": asdict(clean_a_metrics),
            "voip_degraded": asdict(zalo_a_metrics),
            "hf_retention_ratio": round(
                zalo_a_metrics.high_freq_ratio_above_4khz
                / max(clean_a_metrics.high_freq_ratio_above_4khz, 1e-9),
                4,
            ),
        },
        "video": {
            "clean": asdict(clean_v_metrics),
            "voip_degraded": asdict(zalo_v_metrics),
            "srm_retention_ratio": round(
                zalo_v_metrics.srm_high_freq_energy
                / max(clean_v_metrics.srm_high_freq_energy, 1e-9),
                4,
            ),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Measure VoIP degradation on Audio & Video samples")
    parser.add_argument("--self-test", action="store_true", help="Run CPU synthetic degradation test")
    parser.add_argument("--clean-wav", type=Path, help="Path to clean reference WAV (PCM16)")
    parser.add_argument("--degraded-wav", type=Path, help="Path to Zalo/VoIP recorded WAV (PCM16)")
    parser.add_argument("--clean-img", type=Path, help="Path to clean reference face ROI image")
    parser.add_argument("--degraded-img", type=Path, help="Path to Zalo/MediaProjection ROI image")
    args = parser.parse_args()

    if args.self_test:
        result = run_synthetic_self_test()
        print(json.dumps(result, indent=2))
        return 0

    report: dict[str, object] = {}
    if args.clean_wav and args.degraded_wav:
        c_pcm, c_sr = load_wav_mono_float(args.clean_wav)
        d_pcm, d_sr = load_wav_mono_float(args.degraded_wav)
        report["audio"] = {
            "clean": asdict(compute_audio_metrics(c_pcm, c_sr)),
            "degraded": asdict(compute_audio_metrics(d_pcm, d_sr)),
        }
    if args.clean_img and args.degraded_img:
        c_img = load_image_rgb(args.clean_img)
        d_img = load_image_rgb(args.degraded_img)
        report["video"] = {
            "clean": asdict(compute_video_metrics(c_img)),
            "degraded": asdict(compute_video_metrics(d_img)),
        }

    if not report:
        parser.error("Provide --self-test or pair(s) of --clean-wav/--degraded-wav or --clean-img/--degraded-img.")

    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
