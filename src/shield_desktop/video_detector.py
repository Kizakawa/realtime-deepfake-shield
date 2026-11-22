"""Modular Video Forensics & Face-ROI Call-Quality adapters (ONNX SRM + CPU baseline)."""

from __future__ import annotations

import logging
import math
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image

from shield_core.fusion_engine import calibrate_probability

logger = logging.getLogger(__name__)

_SRM_KERNEL = np.array(
    [[-1.0, 2.0, -1.0], [2.0, -4.0, 2.0], [-1.0, 2.0, -1.0]],
    dtype=np.float32,
) / 4.0

_LAP_KERNEL = np.array(
    [[0.0, 1.0, 0.0], [1.0, -4.0, 1.0], [0.0, 1.0, 0.0]],
    dtype=np.float32,
)

_IMAGENET_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
_IMAGENET_STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)


def _convolve_3x3(gray: np.ndarray, kernel: np.ndarray) -> np.ndarray:
    padded = np.pad(gray, ((1, 1), (1, 1)), mode="edge")
    out = np.zeros_like(gray, dtype=np.float32)
    for dy in range(3):
        for dx in range(3):
            out += kernel[dy, dx] * padded[dy : dy + gray.shape[0], dx : dx + gray.shape[1]]
    return out


def crop_face_or_center_roi(
    rgb_frame: np.ndarray,
    face_bbox: tuple[int, int, int, int] | None = None,
) -> np.ndarray:
    """Crop explicit `(x1, y1, x2, y2)` face ROI or center square when given wide screenshots."""
    h, w = rgb_frame.shape[:2]
    if face_bbox is not None:
        x1, y1, x2, y2 = face_bbox
        x1 = max(0, min(x1, w - 1))
        y1 = max(0, min(y1, h - 1))
        x2 = max(x1 + 1, min(x2, w))
        y2 = max(y1 + 1, min(y2, h))
        return rgb_frame[y1:y2, x1:x2]

    if w > int(h * 1.25):
        side = h
        start_x = (w - side) // 2
        return rgb_frame[:, start_x : start_x + side]
    return rgb_frame


def compute_frame_quality_metrics(rgb_frame: np.ndarray) -> tuple[float, float, float]:
    """Return (blur_score in [0,1], black_frame_ratio in [0,1], srm_energy)."""
    gray = np.dot(rgb_frame[..., :3].astype(np.float32), [0.299, 0.587, 0.114])
    black_ratio = float(np.mean(gray < 5.0))
    lap_var = float(np.var(_convolve_3x3(gray, _LAP_KERNEL)))
    blur_score = float(min(max(1.0 - (lap_var / 500.0), 0.0), 1.0))
    srm_res = _convolve_3x3(gray, _SRM_KERNEL)
    srm_energy = float(np.mean(srm_res**2))
    return blur_score, black_ratio, srm_energy


@dataclass(slots=True)
class VideoDetectionResult:
    """Normalized prediction and call-quality telemetry from Engine B."""

    spatial_score: float | None
    blur_score: float
    black_frame_ratio: float
    backend_name: str


class VideoForensicsDetector(ABC):
    """Abstract interface for MobileNetV2-SRM and frame quality detectors."""

    @abstractmethod
    def predict(
        self,
        rgb_frame: np.ndarray,
        face_bbox: tuple[int, int, int, int] | None = None,
    ) -> VideoDetectionResult:
        """Analyze an RGB face ROI (or crop from screen frame)."""


class OnnxVideoSrmDetector(VideoForensicsDetector):
    """ONNX Runtime wrapper for MobileNetV2 / Dual-Stream MobileNetV2-SRM detectors."""

    def __init__(
        self,
        model_path: str | Path,
        input_size: int = 224,
        normalize_imagenet: bool = True,
        spoof_class_index: int = 1,
    ) -> None:
        import onnxruntime as ort

        self.model_path = Path(model_path)
        self.input_size = input_size
        self.normalize_imagenet = normalize_imagenet
        self.spoof_class_index = spoof_class_index
        self.session = ort.InferenceSession(
            str(self.model_path),
            providers=["CPUExecutionProvider"],
        )
        self.inputs = self.session.get_inputs()

    def _format_layout(self, hwc_tensor: np.ndarray, shape: list[object]) -> np.ndarray:
        if len(shape) == 4 and shape[1] == 3:
            return np.transpose(hwc_tensor, (2, 0, 1))[None, ...]
        return hwc_tensor[None, ...]

    def _prepare_feeds(self, roi_rgb: np.ndarray) -> dict[str, np.ndarray]:
        resized_u8 = np.array(
            Image.fromarray(roi_rgb.astype(np.uint8)).resize(
                (self.input_size, self.input_size),
                Image.Resampling.BILINEAR,
            )
        )
        rgb_float = resized_u8.astype(np.float32) / 255.0
        if self.normalize_imagenet:
            rgb_norm = (rgb_float - _IMAGENET_MEAN) / _IMAGENET_STD
        else:
            rgb_norm = rgb_float

        feeds: dict[str, np.ndarray] = {
            self.inputs[0].name: self._format_layout(rgb_norm, self.inputs[0].shape)
        }
        if len(self.inputs) >= 2:
            # Dual-stream MobileNetV2 + SRM model: compute 3-channel high-pass SRM residual.
            srm_channels = [
                _convolve_3x3(resized_u8[..., ch].astype(np.float32) / 255.0, _SRM_KERNEL)
                for ch in range(3)
            ]
            srm_hwc = np.stack(srm_channels, axis=-1).astype(np.float32)
            feeds[self.inputs[1].name] = self._format_layout(srm_hwc, self.inputs[1].shape)
        return feeds

    def predict(
        self,
        rgb_frame: np.ndarray,
        face_bbox: tuple[int, int, int, int] | None = None,
    ) -> VideoDetectionResult:
        roi = crop_face_or_center_roi(rgb_frame, face_bbox=face_bbox)
        blur_score, black_ratio, _ = compute_frame_quality_metrics(roi)
        outputs = self.session.run(None, self._prepare_feeds(roi))
        flat = np.asarray(outputs[0], dtype=np.float64).reshape(-1)
        if flat.size == 1:
            raw_prob = float(1.0 / (1.0 + math.exp(-float(flat[0]))))
        else:
            idx = min(max(self.spoof_class_index, 0), flat.size - 1)
            shifted = flat - np.max(flat)
            probs = np.exp(shifted) / np.sum(np.exp(shifted))
            raw_prob = float(probs[idx])
        return VideoDetectionResult(
            spatial_score=calibrate_probability(raw_prob),
            blur_score=round(blur_score, 4),
            black_frame_ratio=round(black_ratio, 4),
            backend_name=f"onnx:{self.model_path.name}",
        )


class HeuristicVideoBaseline(VideoForensicsDetector):
    """CPU frame-quality & blur baseline feeding `ShortGlitchyCall` without fake spatial claims."""

    def predict(
        self,
        rgb_frame: np.ndarray,
        face_bbox: tuple[int, int, int, int] | None = None,
    ) -> VideoDetectionResult:
        roi = crop_face_or_center_roi(rgb_frame, face_bbox=face_bbox)
        blur_score, black_ratio, _ = compute_frame_quality_metrics(roi)
        return VideoDetectionResult(
            spatial_score=None,
            blur_score=round(blur_score, 4),
            black_frame_ratio=round(black_ratio, 4),
            backend_name="heuristic_video_quality_baseline",
        )


def load_video_detector(model_path: str | Path | None = None) -> VideoForensicsDetector:
    """Load ONNX MobileNetV2-SRM detector if weights exist; otherwise return quality baseline."""
    if model_path is not None:
        path = Path(model_path)
        if path.is_file():
            return OnnxVideoSrmDetector(path)
        logger.warning("Video ONNX model not found at %s; falling back to quality baseline.", path)
    return HeuristicVideoBaseline()
