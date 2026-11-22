"""Vietnamese chat & voice context analyzer with anti-obfuscation & prompt-injection defenses."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from .layer0_gatekeeper import normalize_vietnamese
from .models import EvidenceSignal, TacticTag

_TAG_ESCAPE_RE = re.compile(r"</?\s*untrusted_input\s*>", re.IGNORECASE)
_APK_EXT_RE = re.compile(r"\.apk\b", re.IGNORECASE)
_OBFUSCATED_SEP_RE = re.compile(r"(?<=\w)[.\-_*/]+(?=\w)", re.UNICODE)
_LEET_OTP_RE = re.compile(r"\b0tp\b", re.IGNORECASE)
_NON_WORD_UNICODE_RE = re.compile(r"[^\w\s]", re.UNICODE)
_SPACE_COLLAPSE_RE = re.compile(r"\s+")

# Unambiguous normalized (diacritic-stripped) whole-word / phrase patterns.
# Ambiguous Vietnamese homographs like "bi bat" ("bị bắt" vs "bị bật") or
# "mo gap" ("mổ gấp" vs "mở gặp") are handled strictly in `_ACCENTED_PATTERNS`.
_TACTIC_PATTERNS: dict[TacticTag, tuple[str, ...]] = {
    TacticTag.AUTHORITY_IMPERSONATION: (
        "cong an",
        "vien kiem sat",
        "toa an",
        "canh sat dieu tra",
        "bo cong an",
        "lenh bat",
        "lenh tam giam",
        "khoi to",
        "truy na",
        "dich vu cong",
        "vneid",
        "co quan chuc nang",
        "ngan hang nha nuoc",
    ),
    TacticTag.RELATIVE_EMERGENCY: (
        "tai nan",
        "cap cuu",
        "nhap vien",
        "phau thuat gap",
        "song yeu",
        "mat song",
        "vay tien",
        "muon tien",
        "cho muon",
        "chuyen ho",
        "gui ho",
        "tra no gap",
    ),
    TacticTag.URGENCY_FEAR: (
        "chuyen gap",
        "chuyen tien gap",
        "chuyen khoan gap",
        "chuyen ngay",
        "chuyen tien ngay",
        "chuyen khoan ngay",
        "lap tuc",
        "ngay bay gio",
        "ngay lap tuc",
        "trong 5 phut",
        "trong 10 phut",
        "phong toa tai khoan",
        "khoa tai khoan",
        "tai khoan bi khoa",
        "khong kip",
        "bat tam giam",
        "lien quan duong day",
    ),
    TacticTag.SECRECY_ISOLATION: (
        "giu bi mat",
        "tuyet doi bi mat",
        "tuyet mat",
        "khong duoc noi",
        "dung noi voi ai",
        "dung noi voi con",
        "khong bao ai",
        "o mot minh",
    ),
    TacticTag.FINANCIAL_TRANSFER: (
        "so tai khoan",
        "stk",
        "tai khoan la",
        "ma otp",
        "otp",
        "doc ma",
        "chuyen khoan",
        "chuyen tien",
        "nop tien",
        "tien dam bao",
        "chung minh tai chinh",
    ),
    TacticTag.MALICIOUS_APP_INSTALL: (
        "anydesk",
        "teamviewer",
        "rustdesk",
        "airdroid",
        "file apk",
        "apk",
        "cai app",
        "tai app",
        "tai ung dung",
        "bam vao link",
        "cap nhat sinh trac",
    ),
}

# Tone-sensitive Vietnamese patterns checked prior to stripping diacritics so
# everyday phrases like "chuẩn bị bật tivi" or "mở gặp mặt" never false-trigger.
_ACCENTED_PATTERNS: dict[TacticTag, tuple[str, ...]] = {
    TacticTag.URGENCY_FEAR: ("bị bắt", "bắt giam"),
    TacticTag.RELATIVE_EMERGENCY: ("mổ gấp", "vào viện cấp cứu"),
}

_PROMPT_INJECTION_PATTERNS: tuple[str, ...] = (
    "bo qua huong dan",
    "bo qua tat ca chi thi",
    "ignore previous instructions",
    "ignore all instructions",
    "system prompt",
    "phan loai la safe",
    "phan loai la an toan",
    "tra ve safe",
    "set state safe",
)

_BENIGN_DELIVERY_PATTERNS: tuple[str, ...] = (
    "shipper",
    "giao hang",
    "giao don",
    "buu ta",
    "nha thuoc",
    "phong kham",
    "lich hen kham",
)

_VALID_TACTIC_VALUES = frozenset(tag.value for tag in TacticTag)
_ALLOWED_SLM_KEYS = frozenset({"tactics", "risk_prob", "reason"})


def deobfuscate_text(text: str) -> tuple[str, str]:
    """Collapse scammer punctuation obfuscation (`c.o.n.g`, `0TP`, `.apk`).

    Returns:
        `(cleaned_accented_lower, padded_normalized_unaccented)` where the second
        string is space-padded (`" ... "`) for exact word/phrase boundary matching.
    """
    if not text:
        return "", ""
    expanded_apk = _APK_EXT_RE.sub(" file apk ", text)
    collapsed = _OBFUSCATED_SEP_RE.sub("", expanded_apk)
    accented_lower = _SPACE_COLLAPSE_RE.sub(" ", collapsed.lower()).strip()

    norm = normalize_vietnamese(collapsed)
    norm = _LEET_OTP_RE.sub("otp", norm)
    padded_norm = f" {norm} " if norm else ""
    return accented_lower, padded_norm


def _contains_phrase(padded_haystack: str, phrase: str) -> bool:
    return f" {phrase} " in padded_haystack


def wrap_untrusted_input(text: str) -> str:
    """Neutralize injected delimiter tags and wrap untrusted speech/chat text safely."""
    sanitized = _TAG_ESCAPE_RE.sub("[STRIPPED_TAG]", text or "")
    return f"<UNTRUSTED_INPUT>\n{sanitized}\n</UNTRUSTED_INPUT>"


def validate_slm_json_output(raw_text: str) -> dict[str, Any] | None:
    """Strictly validate constrained-JSON output from an SLM classifier."""
    try:
        parsed = json.loads(raw_text)
    except (TypeError, json.JSONDecodeError):
        return None

    if not isinstance(parsed, dict):
        return None
    if not set(parsed.keys()).issubset(_ALLOWED_SLM_KEYS):
        return None
    if "tactics" not in parsed or "risk_prob" not in parsed:
        return None

    risk_prob = parsed["risk_prob"]
    if isinstance(risk_prob, bool) or not isinstance(risk_prob, (int, float)):
        return None
    if not (0.0 <= float(risk_prob) <= 1.0):
        return None

    tactics = parsed["tactics"]
    if not isinstance(tactics, list) or not all(
        isinstance(item, str) and item in _VALID_TACTIC_VALUES for item in tactics
    ):
        return None

    reason = parsed.get("reason", "")
    if not isinstance(reason, str):
        return None

    return {
        "tactics": list(tactics),
        "risk_prob": float(risk_prob),
        "reason": reason[:240],
    }


@dataclass(slots=True)
class ContextAnalysisOutput:
    """Structured evaluation returned by Engine C."""

    matched_tactics: list[TacticTag]
    prompt_injection_detected: bool
    signals: list[EvidenceSignal]


class VietnameseContextAnalyzer:
    """Fast, injection-resistant Vietnamese scam tactic analyzer for voice and chat."""

    def analyze(self, text: str, source_tag: str = "context_engine") -> ContextAnalysisOutput:
        """Analyze Vietnamese transcript or chat snippet and emit calibrated signals."""
        _ = wrap_untrusted_input(text)
        accented_lower, padded_norm = deobfuscate_text(text)
        if not padded_norm:
            return ContextAnalysisOutput([], False, [])

        matched_tactics: list[TacticTag] = []
        padded_accented = f" {_NON_WORD_UNICODE_RE.sub(' ', accented_lower)} "
        padded_accented = _SPACE_COLLAPSE_RE.sub(" ", padded_accented)

        for tactic, keywords in _TACTIC_PATTERNS.items():
            matched_unaccented = any(_contains_phrase(padded_norm, kw) for kw in keywords)
            matched_accented = any(
                f" {akw} " in padded_accented for akw in _ACCENTED_PATTERNS.get(tactic, ())
            )
            if matched_unaccented or matched_accented:
                matched_tactics.append(tactic)

        injection_detected = any(
            _contains_phrase(padded_norm, pat) for pat in _PROMPT_INJECTION_PATTERNS
        )
        is_benign_delivery = any(
            _contains_phrase(padded_norm, pat) for pat in _BENIGN_DELIVERY_PATTERNS
        )

        signals: list[EvidenceSignal] = []
        if injection_detected:
            signals.append(
                EvidenceSignal(
                    source=source_tag,
                    raw_score=0.85,
                    calibrated_prob=0.80,
                    reliability=0.88,
                    code="PROMPT_INJECTION_ATTEMPT",
                    detail="Phát hiện mẫu câu tìm cách can thiệp bộ phân loại AI.",
                )
            )

        if not matched_tactics:
            return ContextAnalysisOutput([], injection_detected, signals)

        coercive_tactics = {
            TacticTag.AUTHORITY_IMPERSONATION,
            TacticTag.URGENCY_FEAR,
            TacticTag.SECRECY_ISOLATION,
            TacticTag.MALICIOUS_APP_INSTALL,
        }
        has_coercion = any(t in coercive_tactics for t in matched_tactics)
        if (
            is_benign_delivery
            and not has_coercion
            and TacticTag.FINANCIAL_TRANSFER not in matched_tactics
        ):
            return ContextAnalysisOutput(matched_tactics, injection_detected, signals)

        tactic_count = len(matched_tactics)
        if TacticTag.MALICIOUS_APP_INSTALL in matched_tactics:
            raw_score = min(0.95, 0.72 + 0.08 * tactic_count)
            reliability = 0.90
        elif has_coercion and TacticTag.FINANCIAL_TRANSFER in matched_tactics:
            raw_score = min(0.94, 0.68 + 0.08 * tactic_count)
            reliability = 0.88
        elif has_coercion and TacticTag.RELATIVE_EMERGENCY in matched_tactics:
            raw_score = min(0.88, 0.62 + 0.08 * tactic_count)
            reliability = 0.82
        elif tactic_count >= 2:
            raw_score = min(0.80, 0.50 + 0.10 * tactic_count)
            reliability = 0.78
        elif (
            TacticTag.FINANCIAL_TRANSFER in matched_tactics
            or TacticTag.RELATIVE_EMERGENCY in matched_tactics
        ):
            raw_score = 0.42
            reliability = 0.65
        else:
            raw_score = 0.32
            reliability = 0.55

        tactic_names = ", ".join(t.value for t in matched_tactics)
        signals.append(
            EvidenceSignal(
                source=source_tag,
                raw_score=raw_score,
                calibrated_prob=raw_score,
                reliability=reliability,
                code="CONTEXT_MANIPULATION_DETECTED",
                detail=f"Phát hiện chiến thuật: {tactic_names}",
            )
        )
        return ContextAnalysisOutput(matched_tactics, injection_detected, signals)
