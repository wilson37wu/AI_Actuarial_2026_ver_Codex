"""Tests for Phase 12 calibration assumption pack generation."""

from __future__ import annotations

import json

import pytest

from par_model_v2.calibration import (
    CalibrationAssumptionCard,
    Phase12CalibrationPack,
    build_credit_calibration_cards,
    build_curve_calibration_cards,
    build_equity_calibration_cards,
    build_liability_calibration_cards,
    build_phase12_calibration_pack,
    validate_calibration_cards,
)


class TestCalibrationCards:
    def test_curve_cards_cover_starter_currencies(self):
        cards = build_curve_calibration_cards("2026-06-04")
        currencies = {card.metadata["currency"] for card in cards}
        assert {"USD", "EUR", "HKD", "CNY", "JPY"}.issubset(currencies)

    def test_equity_cards_cover_phase8_markets(self):
        cards = build_equity_calibration_cards("2026-06-04")
        markets = {card.metadata["market"] for card in cards}
        assert {"US", "EU", "HK_CN", "JP", "ASIA_EX_JP"}.issubset(markets)

    def test_credit_cards_include_public_and_private_credit(self):
        cards = build_credit_calibration_cards()
        ids = {card.assumption_id for card in cards}
        assert "CREDIT-HK_CORP_A_7Y_EDU" in ids
        assert "PRIVATE-CREDIT-HK_PC_DIRECT_LENDING_EDU" in ids

    def test_liability_cards_include_declaration_rates(self):
        cards = build_liability_calibration_cards()
        names = {card.assumption_name for card in cards}
        assert "HK cash dividend declared rate" in names
        assert "HK reversionary bonus declared rate" in names
        assert "HK terminal bonus declared percentage" in names

    def test_card_requires_supported_status(self):
        with pytest.raises(ValueError, match="validation_status"):
            CalibrationAssumptionCard(
                category="curve",
                assumption_id="BAD",
                assumption_name="Bad card",
                basis="test",
                value=0.01,
                unit="decimal",
                source_id="SRC",
                limitation_id="LIM",
                validation_status="UNKNOWN",
                owner_role="Owner",
            )


class TestPhase12CalibrationPack:
    def test_full_pack_has_required_categories(self):
        pack = build_phase12_calibration_pack("2026-06-04")
        assert isinstance(pack, Phase12CalibrationPack)
        assert set(pack.category_summary()) == {"curve", "equity", "credit", "liability"}

    def test_pack_status_is_placeholder_disclosed(self):
        pack = build_phase12_calibration_pack("2026-06-04")
        assert pack.completeness_status == "EDUCATIONAL_PLACEHOLDER"

    def test_all_checks_pass_for_full_pack(self):
        pack = build_phase12_calibration_pack("2026-06-04")
        assert all(check.status == "PASS" for check in pack.input_checks)

    def test_to_dict_json_serialisable(self):
        pack = build_phase12_calibration_pack("2026-06-04")
        payload = json.dumps(pack.to_dict())
        loaded = json.loads(payload)
        assert loaded["completeness_status"] == "EDUCATIONAL_PLACEHOLDER"
        assert len(loaded["assumption_cards"]) == len(pack.assumption_cards)

    def test_write_json_and_markdown(self, tmp_path):
        pack = build_phase12_calibration_pack("2026-06-04")
        json_path = pack.write_json(tmp_path / "pack.json")
        md_path = pack.write_markdown(tmp_path / "pack.md")
        assert json_path.exists()
        assert md_path.exists()
        assert "Phase 12 Calibration Assumption Pack" in md_path.read_text(encoding="utf-8")

    def test_category_filter(self):
        pack = build_phase12_calibration_pack("2026-06-04", categories=("curve", "liability"))
        assert set(pack.category_summary()) == {"curve", "liability"}
        failing = [check for check in pack.input_checks if check.check_id == "P12-CAL-01"]
        assert failing[0].status == "FAIL"

    def test_unknown_category_rejected(self):
        with pytest.raises(ValueError, match="unknown calibration categories"):
            build_phase12_calibration_pack(categories=("curve", "bad"))

    def test_validation_detects_duplicate_ids(self):
        cards = build_liability_calibration_cards()
        duplicate = cards + [cards[0]]
        checks = validate_calibration_cards(duplicate)
        dup_check = next(check for check in checks if check.check_id == "P12-CAL-02")
        assert dup_check.status == "FAIL"
