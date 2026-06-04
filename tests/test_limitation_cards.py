"""Tests for Phase 12 model limitation cards."""

from __future__ import annotations

import json

import pytest

from par_model_v2.governance import (
    ModelLimitationCard,
    build_limitation_card_report,
    default_model_limitation_cards,
    write_default_limitation_cards,
)


def test_default_cards_cover_esg_and_liability():
    cards = default_model_limitation_cards()
    areas = {card.module_area for card in cards}
    assert areas == {"ESG", "Liability"}


def test_default_cards_cover_material_components():
    cards = default_model_limitation_cards()
    names = {card.module_name for card in cards}
    assert "Hull-White 1F rate process" in names
    assert "Regional equity GBM factors" in names
    assert "FX translation factors" in names
    assert "HK cash dividend mechanics" in names
    assert "HK reversionary bonus mechanics" in names
    assert "Liability reporting views" in names


def test_cards_have_unique_limitation_ids():
    cards = default_model_limitation_cards()
    ids = [card.limitation_id for card in cards]
    assert len(ids) == len(set(ids))


def test_cards_disclose_unsuitable_uses_and_standards():
    for card in default_model_limitation_cards():
        assert card.unsuitable_uses
        assert card.standards_reference
        assert card.current_mitigation
        assert card.required_upgrade


def test_invalid_severity_rejected():
    with pytest.raises(ValueError, match="severity"):
        ModelLimitationCard(
            limitation_id="BAD",
            module_area="ESG",
            module_name="Bad",
            component_path="x.y",
            severity="URGENT",
            limitation="bad",
            unsuitable_uses=("pricing",),
            current_mitigation="none",
            required_upgrade="fix",
            owner_role="Owner",
            standards_reference=("SOA ASOP 56",),
        )


def test_report_summary_and_json_serialisation():
    report = build_limitation_card_report()
    assert report.by_area()["ESG"] >= 6
    assert report.by_area()["Liability"] >= 5
    payload = json.dumps(report.to_dict())
    loaded = json.loads(payload)
    assert loaded["open_critical_count"] >= 2


def test_report_filters_by_area_and_severity():
    report = build_limitation_card_report(module_area="Liability", severity="CRITICAL")
    assert report.cards
    assert all(card.module_area == "Liability" for card in report.cards)
    assert all(card.severity == "CRITICAL" for card in report.cards)


def test_markdown_contains_detail_sections():
    report = build_limitation_card_report()
    text = report.to_markdown()
    assert "Phase 12 Model Limitation Cards" in text
    assert "HK-LC-003" in text
    assert "ESG-LC-001" in text


def test_write_default_reports(tmp_path):
    report = write_default_limitation_cards(tmp_path)
    assert report.cards
    assert (tmp_path / "phase12_model_limitation_cards.json").exists()
    assert (tmp_path / "phase12_model_limitation_cards.md").exists()
