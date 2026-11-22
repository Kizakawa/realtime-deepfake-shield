"""Unit tests for Layer 0 Gatekeeper, Vietnamese normalization, and emergency bypass."""

from shield_core.layer0_gatekeeper import (
    FamilyAllowlist,
    Layer0Gatekeeper,
    is_emergency_number,
    normalize_vietnamese,
)


def test_normalize_vietnamese_strips_diacritics_and_d_stroke() -> None:
    assert normalize_vietnamese("Đang điều tra — Chuyển gấp!") == "dang dieu tra chuyen gap"
    assert normalize_vietnamese("Con Trai Minh") == "con trai minh"


def test_emergency_numbers_always_bypass() -> None:
    gatekeeper = Layer0Gatekeeper()
    for raw in ("113", "114", "115", " 115 ", "1-1-3"):
        assert is_emergency_number(raw) is True
        decision = gatekeeper.evaluate_counterparty(raw, "Bệnh viện")
        assert decision.status == "EMERGENCY_BYPASS"
        assert decision.signals == ()


def test_allowlisted_contact_is_exempt_from_inspection() -> None:
    allowlist = FamilyAllowlist(
        verified_caller_ids={"zalo:son_minh_real", "0901234567"},
        verified_relative_names={"Con trai Minh"},
    )
    gatekeeper = Layer0Gatekeeper(allowlist=allowlist)
    decision = gatekeeper.evaluate_counterparty("zalo:son_minh_real", "Con trai Minh")
    assert decision.status == "ALLOWLISTED"
    assert decision.signals == ()


def test_lookalike_relative_name_triggers_spoofing_signal() -> None:
    allowlist = FamilyAllowlist(
        verified_caller_ids={"zalo:son_minh_real"},
        verified_relative_names={"Con trai Minh", "Con gái Lan"},
    )
    gatekeeper = Layer0Gatekeeper(allowlist=allowlist)

    # Unverified account mimicking trusted relative display name
    decision = gatekeeper.evaluate_counterparty("zalo_new_991", "Con trai Minh (Số mới)")
    assert decision.status == "INSPECT"
    codes = {sig.code for sig in decision.signals}
    assert "LOOKALIKE_RELATIVE_NAME" in codes
    assert "FOREIGN_OR_UNKNOWN_CALLER" in codes
