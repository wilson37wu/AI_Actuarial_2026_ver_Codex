"""Phase 31 Task 2 - owner decision pack assembly tests."""

from __future__ import annotations

import copy
import json

import pytest

from par_model_v2.governance.owner_decision_package import (
    ESCALATION_OPTION_ID,
    NEUTRALITY_FORBIDDEN_PHRASES,
    OWNER_OPTION_IDS,
    PACK_DOC_ID,
    PACK_DOC_VERSION,
    REQUIRED_GLOSSARY_TERMS,
    REQUIRED_PACK_SECTIONS,
    assemble_owner_pack,
    decision_record_template,
    evidence_pack_registry,
    owner_options,
    signoff_workflow,
    validate_assembled_pack,
    validate_owner_package,
)


@pytest.fixture(scope="module")
def doc():
    return assemble_owner_pack()


@pytest.fixture(scope="module")
def gate(doc):
    return validate_assembled_pack(doc)


class TestBitForBitReproduction:
    def test_evidence_section_is_the_registry(self, doc):
        assert doc["evidence_pack"] == evidence_pack_registry()

    def test_options_section_is_the_registry(self, doc):
        assert doc["owner_options"] == owner_options()

    def test_workflow_section_is_the_registry(self, doc):
        assert doc["signoff_workflow"] == signoff_workflow()

    def test_option_order_fixed(self, doc):
        assert tuple(doc["owner_option_order"]) == OWNER_OPTION_IDS
        assert doc["escalation_option_id"] == ESCALATION_OPTION_ID

    def test_task1_gate_passes_on_assembled_sections(self, doc):
        base = validate_owner_package(
            doc["evidence_pack"], doc["owner_options"], doc["signoff_workflow"])
        assert base["ok"] and base["n_checks"] == 21

    def test_assembly_is_deterministic(self, doc):
        assert assemble_owner_pack() == doc


class TestNeutrality:
    def test_no_steering_language_anywhere(self, doc):
        text = json.dumps(doc, default=float).lower()
        for phrase in NEUTRALITY_FORBIDDEN_PHRASES:
            assert phrase not in text

    def test_decision_record_blank(self, doc):
        tmpl = doc["decision_record_template"]
        for k in ("decision_option_id", "rationale", "decided_by",
                  "decided_at", "peer_reviewer", "follow_up_change_record_id"):
            assert tmpl[k] == ""

    def test_template_helper_matches(self, doc):
        assert doc["decision_record_template"] == decision_record_template()

    def test_reading_guide_says_registry_order_not_preference(self, doc):
        assert any("not preference order" in h for h in doc["how_to_read"])


class TestSelfContainment:
    def test_all_required_sections_present(self, doc):
        for s in REQUIRED_PACK_SECTIONS:
            assert s in doc

    def test_glossary_defines_required_terms(self, doc):
        for t in REQUIRED_GLOSSARY_TERMS:
            assert t in doc["glossary"]
            assert len(doc["glossary"][t]) > 20

    def test_provenance_for_every_headline_figure(self, doc):
        for k in ("governed_headline", "vine2_point", "vine2_bootstrap",
                  "tree3_bootstrap", "nested_reference", "residual_ladder",
                  "gap_decomposition"):
            assert "par_model_v2" in doc["figure_provenance"][k]

    def test_purpose_quotes_key_figures(self, doc):
        assert "3,637.3" in doc["purpose"]
        assert "39,975.7" in doc["purpose"]
        assert "46,638.9" in doc["purpose"]

    def test_metadata_identity(self, doc):
        md = doc["metadata"]
        assert md["pack_id"] == PACK_DOC_ID
        assert md["pack_version"] == PACK_DOC_VERSION
        assert md["classification"] == "EDUCATIONAL"
        assert md["no_model_parameter_changes"] is True

    def test_json_serialisable(self, doc):
        assert json.loads(json.dumps(doc, default=float))


class TestAssemblyGate:
    def test_gate_ok_16_checks(self, gate):
        assert gate["ok"] is True
        assert gate["n_checks"] == 16
        assert all(gate["checks"].values())

    def test_gate_catches_evidence_tamper(self, doc):
        bad = copy.deepcopy(doc)
        bad["evidence_pack"]["governed_headline"]["value"] += 1.0
        g = validate_assembled_pack(bad)
        assert not g["ok"]
        assert not g["checks"]["evidence_bit_for_bit"]
        assert not g["checks"]["task1_gate_ok_on_assembled_pack"]

    def test_gate_catches_steering_language(self, doc):
        bad = copy.deepcopy(doc)
        bad["purpose"] += " We recommend option O2."
        g = validate_assembled_pack(bad)
        assert not g["ok"]
        assert not g["checks"]["no_steering_language"]

    def test_gate_catches_prefilled_decision(self, doc):
        bad = copy.deepcopy(doc)
        bad["decision_record_template"]["decision_option_id"] = "O2"
        g = validate_assembled_pack(bad)
        assert not g["ok"]
        assert not g["checks"]["decision_fields_blank"]

    def test_gate_catches_missing_section(self, doc):
        bad = copy.deepcopy(doc)
        del bad["glossary"]
        with pytest.raises(KeyError):
            validate_assembled_pack(bad)

    def test_gate_catches_option_reorder(self, doc):
        bad = copy.deepcopy(doc)
        bad["owner_option_order"] = list(reversed(bad["owner_option_order"]))
        g = validate_assembled_pack(bad)
        assert not g["ok"]
        assert not g["checks"]["option_order_is_registry_order"]


class TestBuilder:
    def test_builder_main_pass(self, tmp_path, monkeypatch):
        import scripts.build_phase31_task2_assemble_owner_pack as b
        monkeypatch.chdir(tmp_path)
        res = b.main(use_governance=False)
        assert res["verdict"] == "PASS" and res["gate_ok"] is True
        payload = json.loads(
            (tmp_path / "docs/validation/PHASE31_TASK2_OWNER_DECISION_PACK.json").read_text())
        assert payload["assembly_gate"]["ok"] is True
        md = (tmp_path / "docs/validation/PHASE31_TASK2_OWNER_DECISION_PACK.md").read_text()
        for needle in ("39,975.654628", "42,458.5527", "46,638.9", "3,637.3",
                       "O1_adopt_disclosed_vine_readout",
                       "O2_accept_residual_with_monitoring",
                       "O3_fund_second_independent_nested_run",
                       "Decision record (blank",
                       "Glossary"):
            assert needle in md

    def test_markdown_neutral(self, tmp_path, monkeypatch):
        import scripts.build_phase31_task2_assemble_owner_pack as b
        monkeypatch.chdir(tmp_path)
        b.main(use_governance=False)
        md = (tmp_path / "docs/validation/PHASE31_TASK2_OWNER_DECISION_PACK.md").read_text().lower()
        for phrase in NEUTRALITY_FORBIDDEN_PHRASES:
            assert phrase not in md
