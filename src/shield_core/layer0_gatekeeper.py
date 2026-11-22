"""Layer 0 metadata gatekeeper, family allowlist, and emergency bypass."""

from __future__ import annotations

import difflib
import re
import unicodedata
from dataclasses import dataclass, field

from .models import EvidenceSignal

EMERGENCY_NUMBERS: frozenset[str] = frozenset({"113", "114", "115"})

VN_BANKING_PACKAGES: frozenset[str] = frozenset(
    {
        "com.VCB",
        "com.vnpay.bidv",
        "com.mbmobile",
        "vn.com.techcombank.bb.app",
        "com.vietinbank.ipay",
        "com.vnpay.Agribank3g",
        "mobile.acb.com.vn",
        "com.vnpay.vpbankonline",
        "com.mservice.momotransfer",
        "vn.com.vng.zalopay",
    }
)

REMOTE_ACCESS_PACKAGES: frozenset[str] = frozenset(
    {
        "com.anydesk.anydeskandroid",
        "com.teamviewer.teamviewer.market.mobile",
        "com.carriez.flutter_hbb",  # RustDesk
        "com.sand.airdroid",
    }
)

_WHITESPACE_RE = re.compile(r"\s+")
_NON_ALNUM_RE = re.compile(r"[^a-z0-9\s]")


def normalize_vietnamese(text: str) -> str:
    """Lowercase, strip Vietnamese diacritics (including đ/Đ), and normalize spacing."""
    if not text:
        return ""
    replaced = text.replace("đ", "d").replace("Đ", "D")
    decomposed = unicodedata.normalize("NFD", replaced)
    without_marks = "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")
    cleaned = _NON_ALNUM_RE.sub(" ", without_marks.lower())
    return _WHITESPACE_RE.sub(" ", cleaned).strip()


def is_emergency_number(caller_id: str) -> bool:
    """Return True if caller_id is a hardcoded Vietnamese emergency number (113/114/115)."""
    digits = re.sub(r"\D", "", caller_id or "")
    return digits in EMERGENCY_NUMBERS


@dataclass
class FamilyAllowlist:
    """Verified family phone numbers / OTT IDs and their authentic display names."""

    verified_caller_ids: set[str] = field(default_factory=set)
    verified_relative_names: set[str] = field(default_factory=set)

    def __post_init__(self) -> None:
        self._normalized_ids: set[str] = {
            cid.strip().lower() for cid in self.verified_caller_ids if cid.strip()
        }
        self._normalized_names: set[str] = {
            normalize_vietnamese(name)
            for name in self.verified_relative_names
            if normalize_vietnamese(name)
        }

    def is_verified_id(self, caller_id: str) -> bool:
        """Return True if caller_id matches a verified family contact."""
        norm = (caller_id or "").strip().lower()
        return bool(norm and norm in self._normalized_ids)

    def find_lookalike_relative(self, display_name: str, threshold: float = 0.82) -> str | None:
        """Return matched trusted relative name if display_name closely mimics one."""
        norm_disp = normalize_vietnamese(display_name)
        if not norm_disp:
            return None
        for rel_name in self._normalized_names:
            if norm_disp == rel_name:
                return rel_name
            if len(rel_name) >= 6 and (rel_name in norm_disp or norm_disp in rel_name):
                return rel_name
            ratio = difflib.SequenceMatcher(None, norm_disp, rel_name).ratio()
            if ratio >= threshold:
                return rel_name
        return None


@dataclass(frozen=True)
class GatekeeperDecision:
    """Outcome from Layer 0 evaluation before launching heavier AI modules."""

    status: str  # EMERGENCY_BYPASS | ALLOWLISTED | INSPECT
    signals: tuple[EvidenceSignal, ...] = ()


class Layer0Gatekeeper:
    """Ultra-lightweight metadata filter running before any biometric or NLP models."""

    def __init__(self, allowlist: FamilyAllowlist | None = None) -> None:
        self.allowlist = allowlist or FamilyAllowlist()

    def evaluate_counterparty(self, caller_id: str, display_name: str) -> GatekeeperDecision:
        """Check emergency whitelist, trusted family contacts, and lookalike spoofing."""
        if is_emergency_number(caller_id):
            return GatekeeperDecision(status="EMERGENCY_BYPASS")

        if self.allowlist.is_verified_id(caller_id):
            return GatekeeperDecision(status="ALLOWLISTED")

        signals: list[EvidenceSignal] = []
        matched_name = self.allowlist.find_lookalike_relative(display_name)
        if matched_name is not None:
            signals.append(
                EvidenceSignal(
                    source="layer0_gatekeeper",
                    raw_score=0.75,
                    calibrated_prob=0.68,
                    reliability=0.72,
                    code="LOOKALIKE_RELATIVE_NAME",
                    detail=f"Tài khoản chưa xác thực mạo danh tên tương tự '{matched_name}'.",
                )
            )

        if self._is_foreign_or_anonymous_id(caller_id):
            signals.append(
                EvidenceSignal(
                    source="layer0_gatekeeper",
                    raw_score=0.35,
                    calibrated_prob=0.30,
                    reliability=0.45,
                    code="FOREIGN_OR_UNKNOWN_CALLER",
                    detail="Số gọi đến từ đầu số quốc tế hoặc tài khoản OTT chưa lưu danh bạ.",
                )
            )

        return GatekeeperDecision(status="INSPECT", signals=tuple(signals))

    @staticmethod
    def _is_foreign_or_anonymous_id(caller_id: str) -> bool:
        cid = (caller_id or "").strip().lower()
        if cid.startswith("+") and not cid.startswith("+84"):
            return True
        return cid.startswith(("unknown", "zalo_new_", "fb_new_"))
