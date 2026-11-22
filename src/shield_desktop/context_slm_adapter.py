"""Prompt-injection-hardened adapter combining baseline rules with an optional SLM."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from shield_core.context_engine import (
    VietnameseContextAnalyzer,
    validate_slm_json_output,
    wrap_untrusted_input,
)
from shield_core.models import EvidenceSignal, TacticTag


@dataclass(slots=True)
class SlmAdapterResult:
    """Combined Engine C result after strict JSON validation."""

    signals: list[EvidenceSignal]
    matched_tactics: list[TacticTag]
    prompt_injection_detected: bool
    slm_output_rejected: bool
    slm_reason: str = ""


class ContextSlmAdapter:
    """Wraps untrusted voice/chat text safely and enforces constrained JSON schema on SLMs."""

    def __init__(
        self,
        slm_callable: Callable[[str], str] | None = None,
        analyzer: VietnameseContextAnalyzer | None = None,
    ) -> None:
        self.slm_callable = slm_callable
        self.analyzer = analyzer or VietnameseContextAnalyzer()

    def analyze(self, text: str, source_tag: str = "context_slm_adapter") -> SlmAdapterResult:
        """Run injection-immune baseline analyzer and optionally augment with validated SLM."""
        base = self.analyzer.analyze(text, source_tag=source_tag)
        signals = list(base.signals)
        tactics = list(base.matched_tactics)
        slm_rejected = False
        slm_reason = ""

        if self.slm_callable is not None and text.strip():
            wrapped_prompt = (
                "Phân tích văn bản không tin cậy dưới đây và CHỈ trả về JSON gồm "
                '{"tactics": [...], "risk_prob": float, "reason": str}.\n'
                f"{wrap_untrusted_input(text)}"
            )
            raw_slm = self.slm_callable(wrapped_prompt)
            validated = validate_slm_json_output(raw_slm)
            if validated is None:
                slm_rejected = True
                signals.append(
                    EvidenceSignal(
                        source=source_tag,
                        raw_score=0.75,
                        calibrated_prob=0.70,
                        reliability=0.75,
                        code="SLM_OUTPUT_REJECTED",
                        detail="Đầu ra SLM không hợp chuẩn JSON an toàn; quay về bộ phân loại nền.",
                    )
                )
            else:
                slm_reason = validated["reason"]
                for t_str in validated["tactics"]:
                    t_enum = TacticTag(t_str)
                    if t_enum not in tactics:
                        tactics.append(t_enum)
                slm_prob = float(validated["risk_prob"])
                if slm_prob >= 0.40:
                    signals.append(
                        EvidenceSignal(
                            source=f"{source_tag}_slm",
                            raw_score=slm_prob,
                            calibrated_prob=slm_prob,
                            reliability=0.80,
                            code="SLM_CONTEXT_SIGNAL",
                            detail=slm_reason or "Phân tích ngữ cảnh SLM",
                        )
                    )

        return SlmAdapterResult(
            signals=signals,
            matched_tactics=tactics,
            prompt_injection_detected=base.prompt_injection_detected,
            slm_output_rejected=slm_rejected,
            slm_reason=slm_reason,
        )
