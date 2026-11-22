"""Desktop Phase 0 Lab Capture (Windows WASAPI Loopback + Screen Capture).

Privacy-by-Design & Path Safety:
- Operates in Zero-Retention RAM mode by default.
- Requires `--i-have-written-consent` and validates `--sample-id` against path traversal
  so files can never be written outside the git-ignored `data/consented_lab/` folder.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import wave
from dataclasses import asdict
from pathlib import Path

import numpy as np
from PIL import ImageGrab

ROOT_DIR = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from measure_degradation import compute_audio_metrics, compute_video_metrics
from shield_desktop.audio_detector import resample_audio_16k

CONSENTED_LAB_DIR = ROOT_DIR / "data" / "consented_lab"
_SAFE_SAMPLE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def resolve_safe_sample_dir(sample_id: str, base_dir: Path = CONSENTED_LAB_DIR) -> Path:
    """Validate sample_id and ensure resolved output directory stays inside base_dir."""
    if not _SAFE_SAMPLE_ID_RE.fullmatch(sample_id or ""):
        raise ValueError(
            f"Unsafe sample_id '{sample_id}': only [A-Za-z0-9_-] (1..64 chars) allowed"
        )
    base_resolved = base_dir.resolve()
    candidate = (base_resolved / sample_id).resolve()
    if not candidate.is_relative_to(base_resolved):
        raise ValueError(f"Path traversal blocked for sample_id '{sample_id}'")
    return candidate


def capture_wasapi_loopback(duration_sec: float) -> tuple[np.ndarray, int]:
    """Capture system speaker output via Windows WASAPI Loopback and resample to 16 kHz."""
    try:
        import pyaudiowpatch as pyaudio  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "pyaudiowpatch is required for WASAPI loopback capture on Windows. "
            "Install optional dependencies: pip install -e .[desktop]"
        ) from exc

    pa = pyaudio.PyAudio()
    try:
        wasapi_info = pa.get_host_api_info_by_type(pyaudio.paWASAPI)
        default_speakers = pa.get_device_info_by_index(wasapi_info["defaultOutputDevice"])
        if not default_speakers.get("isLoopbackDevice"):
            for loopback in pa.get_loopback_device_info_generator():
                if default_speakers["name"] in loopback["name"]:
                    default_speakers = loopback
                    break

        channels = int(default_speakers["maxInputChannels"])
        rate = int(default_speakers["defaultSampleRate"])
        chunk = 1024
        stream = pa.open(
            format=pyaudio.paInt16,
            channels=channels,
            rate=rate,
            input=True,
            frames_per_buffer=chunk,
            input_device_index=int(default_speakers["index"]),
        )
        chunks: list[bytes] = []
        total_chunks = max(1, int((rate / chunk) * duration_sec))
        for _ in range(total_chunks):
            chunks.append(stream.read(chunk, exception_on_overflow=False))
        stream.stop_stream()
        stream.close()
    finally:
        pa.terminate()

    raw_pcm = np.frombuffer(b"".join(chunks), dtype=np.int16).astype(np.float32) / 32768.0
    if channels > 1:
        raw_pcm = raw_pcm.reshape(-1, channels).mean(axis=1)
    pcm_16k = resample_audio_16k(raw_pcm, orig_sr=rate, target_sr=16000)
    return pcm_16k, 16000


def main() -> int:
    parser = argparse.ArgumentParser(description="Phase 0 Desktop Lab Capture & Metrics")
    parser.add_argument("--duration", type=float, default=5.0, help="Capture duration in seconds")
    parser.add_argument("--sample-id", type=str, default=f"lab_{int(time.time())}", help="Sample ID")
    parser.add_argument(
        "--i-have-written-consent",
        action="store_true",
        help="Required flag to save WAV/PNG into git-ignored data/consented_lab/",
    )
    args = parser.parse_args()

    out_dir = resolve_safe_sample_dir(args.sample_id)

    audio_samples, sr = capture_wasapi_loopback(args.duration)
    audio_metrics = compute_audio_metrics(audio_samples, sr)

    screenshot = ImageGrab.grab().convert("RGB")
    video_metrics = compute_video_metrics(np.array(screenshot))

    output = {
        "sample_id": args.sample_id,
        "zero_retention_mode": not args.i_have_written_consent,
        "audio_metrics": asdict(audio_metrics),
        "video_metrics": asdict(video_metrics),
    }

    if args.i_have_written_consent:
        out_dir.mkdir(parents=True, exist_ok=True)
        wav_path = out_dir / "wasapi_loopback_16k.wav"
        pcm16 = (np.clip(audio_samples, -1.0, 1.0) * 32767.0).astype(np.int16)
        with wave.open(str(wav_path), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sr)
            wf.writeframes(pcm16.tobytes())
        screenshot.save(out_dir / "screen_frame.png")
        output["saved_to"] = str(out_dir)

    print(json.dumps(output, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
