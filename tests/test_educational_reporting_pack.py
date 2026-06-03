"""
Tests for Phase 11 Task 5: Educational Reporting Pack.

Covers structural correctness, JSON serialisability, Markdown generation,
and end-to-end pack assembly.  Actual metric values are not asserted (they
depend on synthetic portfolio distributions); structural and type checks
are used throughout.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from par_model_v2.projection.educational_reporting_pack import (
    EducationalReportingPack,
    ModelRunLog,
    MovementAnalysis,
    RiskMetricsSummary,
    SignOffChecklist,
    ValidationExceptionsReport,
    build_educational_reporting_pack,
    build_model_run_log,
    build_movement_analysis,
    build_risk_metrics_summary,
    build_sign_off_checklist,
    build_validation_exceptions_report,
)
from par_model_v2.projection.portfolio_generator import (
    PortfolioGenerationConfig,
    generate_hk_par_portfolio,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def small_portfolio() -> pd.DataFrame:
    cfg = PortfolioGenerationConfig(n_policies=500, seed=42)
    return generate_hk_par_portfolio(cfg).policies


@pytest.fixture(scope="module")
def run_meta():
    return {"run_id": "RUN-ABCD1234", "lock_id": "ALK-EFGH5678"}


@pytest.fixture(scope="module")
def all_pass_suite():
    return {
        "checks": [
            {"check_id": "V-RECON-01", "check_name": "Reconciliation", "status": "PASS",
             "message": "OK", "threshold": None, "observed": None},
            {"check_id": "V-COUNT-01", "check_name": "Policy count", "status": "PASS",
             "message": "OK", "threshold": None, "observed": None},
        ]
    }


@pytest.fixture(scope="module")
def mixed_suite():
    return {
        "checks": [
            {"check_id": "V-RECON-01", "check_name": "Reconciliation", "status": "PASS",
             "message": "OK", "threshold": None, "observed": None},
            {"check_id": "V-RECON-02", "check_name": "Chunk failures", "status": "FAIL",
             "message": "2 chunks failed", "threshold": 0.05, "observed": 0.20},
            {"check_id": "V-SA-01", "check_name": "SA movement", "status": "WARN",
             "message": "Movement at boundary", "threshold": 0.10, "observed": 0.09},
        ]
    }


# ---------------------------------------------------------------------------
# ModelRunLog
# ---------------------------------------------------------------------------

class TestModelRunLog:
    def test_returns_correct_type(self, run_meta):
        log = build_model_run_log(
            run_id=run_meta["run_id"], lock_id=run_meta["lock_id"],
            cycle_label="2026-Q2", n_policies=500,
            n_chunks=5, n_chunks_done=5, n_chunks_failed=0,
        )
        assert isinstance(log, ModelRunLog)

    def test_has_five_entries(self, run_meta):
        log = build_model_run_log(
            run_id=run_meta["run_id"], lock_id=run_meta["lock_id"],
            cycle_label="2026-Q2", n_policies=500,
            n_chunks=5, n_chunks_done=5, n_chunks_failed=0,
        )
        assert len(log.entries) == 5

    def test_run_id_stored(self, run_meta):
        log = build_model_run_log(
            run_id=run_meta["run_id"], lock_id=run_meta["lock_id"],
            cycle_label="2026-Q2", n_policies=500,
            n_chunks=5, n_chunks_done=5, n_chunks_failed=0,
        )
        assert log.run_id == run_meta["run_id"]

    def test_to_dict_json_serialisable(self, run_meta):
        log = build_model_run_log(
            run_id=run_meta["run_id"], lock_id=run_meta["lock_id"],
            cycle_label="2026-Q2", n_policies=500,
            n_chunks=5, n_chunks_done=5, n_chunks_failed=0,
        )
        j = json.dumps(log.to_dict())
        assert "run_id" in json.loads(j)

    def test_to_markdown_contains_cycle_label(self, run_meta):
        log = build_model_run_log(
            run_id=run_meta["run_id"], lock_id=run_meta["lock_id"],
            cycle_label="2026-Q2", n_policies=500,
            n_chunks=5, n_chunks_done=5, n_chunks_failed=0,
        )
        md = log.to_markdown()
        assert "2026-Q2" in md

    def test_failed_chunks_in_notes(self, run_meta):
        log = build_model_run_log(
            run_id=run_meta["run_id"], lock_id=run_meta["lock_id"],
            cycle_label="Test", n_policies=500,
            n_chunks=5, n_chunks_done=4, n_chunks_failed=1,
        )
        notes_texts = " ".join(e.notes for e in log.entries)
        assert "1 failed" in notes_texts


# ---------------------------------------------------------------------------
# MovementAnalysis
# ---------------------------------------------------------------------------

class TestMovementAnalysis:
    def test_returns_correct_type(self, small_portfolio):
        result = build_movement_analysis(small_portfolio)
        assert isinstance(result, MovementAnalysis)

    def test_closing_n_matches_portfolio(self, small_portfolio):
        result = build_movement_analysis(small_portfolio)
        assert result.closing_n_policies == len(small_portfolio)

    def test_has_six_movements(self, small_portfolio):
        result = build_movement_analysis(small_portfolio)
        assert len(result.movements) == 6

    def test_closing_sa_positive(self, small_portfolio):
        result = build_movement_analysis(small_portfolio)
        assert result.closing_sum_assured > 0

    def test_to_dict_json_serialisable(self, small_portfolio):
        result = build_movement_analysis(small_portfolio)
        j = json.dumps(result.to_dict())
        assert "closing_n_policies" in json.loads(j)

    def test_to_markdown_contains_header(self, small_portfolio):
        result = build_movement_analysis(small_portfolio)
        md = result.to_markdown()
        assert "Movement Analysis" in md

    def test_opening_line_present(self, small_portfolio):
        result = build_movement_analysis(small_portfolio)
        categories = [m.category for m in result.movements]
        assert "Opening in-force" in categories

    def test_closing_line_present(self, small_portfolio):
        result = build_movement_analysis(small_portfolio)
        categories = [m.category for m in result.movements]
        assert "Closing in-force" in categories


# ---------------------------------------------------------------------------
# RiskMetricsSummary
# ---------------------------------------------------------------------------

class TestRiskMetricsSummary:
    def test_returns_correct_type(self, small_portfolio):
        result = build_risk_metrics_summary(small_portfolio)
        assert isinstance(result, RiskMetricsSummary)

    def test_has_five_metrics(self, small_portfolio):
        result = build_risk_metrics_summary(small_portfolio)
        assert len(result.metrics) == 5

    def test_var_95_positive(self, small_portfolio):
        result = build_risk_metrics_summary(small_portfolio)
        var = next(m for m in result.metrics if "VaR" in m.metric_name)
        assert var.value > 0

    def test_es_95_ge_var_95(self, small_portfolio):
        result = build_risk_metrics_summary(small_portfolio)
        var_val = next(m.value for m in result.metrics if "VaR" in m.metric_name)
        es_val = next(m.value for m in result.metrics if "ES-95" in m.metric_name)
        assert es_val >= var_val

    def test_total_sa_matches_portfolio(self, small_portfolio):
        result = build_risk_metrics_summary(small_portfolio)
        total = next(m.value for m in result.metrics if "Total" in m.metric_name)
        expected = float(small_portfolio["sum_assured"].sum())
        assert abs(total - expected) < 1.0

    def test_to_dict_json_serialisable(self, small_portfolio):
        result = build_risk_metrics_summary(small_portfolio)
        j = json.dumps(result.to_dict())
        assert "metrics" in json.loads(j)

    def test_to_markdown_contains_header(self, small_portfolio):
        result = build_risk_metrics_summary(small_portfolio)
        md = result.to_markdown()
        assert "Risk Metrics" in md

    def test_n_policies_matches(self, small_portfolio):
        result = build_risk_metrics_summary(small_portfolio)
        assert result.n_policies == len(small_portfolio)


# ---------------------------------------------------------------------------
# ValidationExceptionsReport
# ---------------------------------------------------------------------------

class TestValidationExceptionsReport:
    def test_all_pass_gives_clear(self, run_meta, all_pass_suite):
        result = build_validation_exceptions_report(run_meta["run_id"], all_pass_suite)
        assert result.overall_status == "CLEAR"

    def test_all_pass_no_exceptions(self, run_meta, all_pass_suite):
        result = build_validation_exceptions_report(run_meta["run_id"], all_pass_suite)
        assert result.n_exceptions == 0
        assert result.exceptions == []

    def test_mixed_gives_exceptions_status(self, run_meta, mixed_suite):
        result = build_validation_exceptions_report(run_meta["run_id"], mixed_suite)
        assert result.overall_status == "EXCEPTIONS"

    def test_mixed_counts_fail_and_warn(self, run_meta, mixed_suite):
        result = build_validation_exceptions_report(run_meta["run_id"], mixed_suite)
        assert result.n_exceptions == 2  # 1 FAIL + 1 WARN

    def test_exception_check_ids(self, run_meta, mixed_suite):
        result = build_validation_exceptions_report(run_meta["run_id"], mixed_suite)
        ids = {e.check_id for e in result.exceptions}
        assert "V-RECON-02" in ids
        assert "V-SA-01" in ids

    def test_recommended_action_populated(self, run_meta, mixed_suite):
        result = build_validation_exceptions_report(run_meta["run_id"], mixed_suite)
        for exc in result.exceptions:
            assert exc.recommended_action != ""

    def test_to_dict_json_serialisable(self, run_meta, all_pass_suite):
        result = build_validation_exceptions_report(run_meta["run_id"], all_pass_suite)
        j = json.dumps(result.to_dict())
        assert "overall_status" in json.loads(j)

    def test_to_markdown_all_clear(self, run_meta, all_pass_suite):
        result = build_validation_exceptions_report(run_meta["run_id"], all_pass_suite)
        md = result.to_markdown()
        assert "No validation exceptions" in md

    def test_to_markdown_lists_exceptions(self, run_meta, mixed_suite):
        result = build_validation_exceptions_report(run_meta["run_id"], mixed_suite)
        md = result.to_markdown()
        assert "V-RECON-02" in md


# ---------------------------------------------------------------------------
# SignOffChecklist
# ---------------------------------------------------------------------------

class TestSignOffChecklist:
    def test_returns_correct_type(self, run_meta):
        result = build_sign_off_checklist(
            run_id=run_meta["run_id"], lock_id=run_meta["lock_id"],
            cycle_label="2026-Q2", reviewer="Test Actuary",
            governance_cleared=True,
        )
        assert isinstance(result, SignOffChecklist)

    def test_pack_id_prefix(self, run_meta):
        result = build_sign_off_checklist(
            run_id=run_meta["run_id"], lock_id=run_meta["lock_id"],
            cycle_label="2026-Q2", reviewer="Test Actuary",
            governance_cleared=True,
        )
        assert result.pack_id.startswith("ERP-")

    def test_all_complete_when_governance_cleared(self, run_meta):
        result = build_sign_off_checklist(
            run_id=run_meta["run_id"], lock_id=run_meta["lock_id"],
            cycle_label="2026-Q2", reviewer="Test Actuary",
            governance_cleared=True,
        )
        assert result.all_complete

    def test_not_all_complete_without_governance(self, run_meta):
        result = build_sign_off_checklist(
            run_id=run_meta["run_id"], lock_id=run_meta["lock_id"],
            cycle_label="2026-Q2", reviewer="Test Actuary",
            governance_cleared=False,
        )
        assert not result.all_complete

    def test_has_nine_items(self, run_meta):
        result = build_sign_off_checklist(
            run_id=run_meta["run_id"], lock_id=run_meta["lock_id"],
            cycle_label="2026-Q2", reviewer="Test Actuary",
            governance_cleared=True,
        )
        assert len(result.items) == 9

    def test_to_dict_json_serialisable(self, run_meta):
        result = build_sign_off_checklist(
            run_id=run_meta["run_id"], lock_id=run_meta["lock_id"],
            cycle_label="2026-Q2", reviewer="Test Actuary",
            governance_cleared=True,
        )
        j = json.dumps(result.to_dict())
        assert "all_complete" in json.loads(j)

    def test_to_markdown_contains_reviewer(self, run_meta):
        result = build_sign_off_checklist(
            run_id=run_meta["run_id"], lock_id=run_meta["lock_id"],
            cycle_label="2026-Q2", reviewer="Jane Actuary",
            governance_cleared=True,
        )
        md = result.to_markdown()
        assert "Jane Actuary" in md


# ---------------------------------------------------------------------------
# EducationalReportingPack (integration)
# ---------------------------------------------------------------------------

class TestEducationalReportingPack:
    def test_returns_correct_type(self, small_portfolio, run_meta):
        pack = build_educational_reporting_pack(
            portfolio=small_portfolio,
            run_id=run_meta["run_id"],
            lock_id=run_meta["lock_id"],
        )
        assert isinstance(pack, EducationalReportingPack)

    def test_pack_id_prefix(self, small_portfolio, run_meta):
        pack = build_educational_reporting_pack(
            portfolio=small_portfolio,
            run_id=run_meta["run_id"],
            lock_id=run_meta["lock_id"],
        )
        assert pack.pack_id.startswith("ERP-")

    def test_cycle_label_stored(self, small_portfolio, run_meta):
        pack = build_educational_reporting_pack(
            portfolio=small_portfolio,
            run_id=run_meta["run_id"],
            lock_id=run_meta["lock_id"],
            cycle_label="2026-Q3",
        )
        assert pack.cycle_label == "2026-Q3"

    def test_all_sections_present(self, small_portfolio, run_meta):
        pack = build_educational_reporting_pack(
            portfolio=small_portfolio,
            run_id=run_meta["run_id"],
            lock_id=run_meta["lock_id"],
        )
        assert isinstance(pack.run_log, ModelRunLog)
        assert isinstance(pack.movement_analysis, MovementAnalysis)
        assert isinstance(pack.risk_metrics, RiskMetricsSummary)
        assert isinstance(pack.validation_exceptions, ValidationExceptionsReport)
        assert isinstance(pack.sign_off_checklist, SignOffChecklist)

    def test_to_dict_json_serialisable(self, small_portfolio, run_meta):
        pack = build_educational_reporting_pack(
            portfolio=small_portfolio,
            run_id=run_meta["run_id"],
            lock_id=run_meta["lock_id"],
        )
        j = json.dumps(pack.to_dict())
        d = json.loads(j)
        for key in ("pack_id", "run_log", "movement_analysis", "risk_metrics",
                    "validation_exceptions", "sign_off_checklist"):
            assert key in d, f"Missing key: {key}"

    def test_write_json(self, small_portfolio, run_meta, tmp_path):
        pack = build_educational_reporting_pack(
            portfolio=small_portfolio,
            run_id=run_meta["run_id"],
            lock_id=run_meta["lock_id"],
            output_dir=tmp_path,
        )
        path = pack.write_json(tmp_path / "edpack.json")
        assert path.exists()
        data = json.loads(path.read_text())
        assert data["pack_id"] == pack.pack_id

    def test_write_markdown(self, small_portfolio, run_meta, tmp_path):
        pack = build_educational_reporting_pack(
            portfolio=small_portfolio,
            run_id=run_meta["run_id"],
            lock_id=run_meta["lock_id"],
            output_dir=tmp_path,
        )
        path = pack.write_markdown(tmp_path / "edpack.md")
        assert path.exists()
        text = path.read_text()
        assert "Educational Reporting Pack" in text

    def test_markdown_contains_all_sections(self, small_portfolio, run_meta, tmp_path):
        pack = build_educational_reporting_pack(
            portfolio=small_portfolio,
            run_id=run_meta["run_id"],
            lock_id=run_meta["lock_id"],
        )
        md = pack.write_markdown(tmp_path / "full.md").read_text()
        for heading in ("Model Run Log", "Movement Analysis", "Risk Metrics",
                        "Validation Exceptions", "Sign-Off Checklist"):
            assert heading in md, f"Missing section: {heading}"

    def test_section_text_run_log(self, small_portfolio, run_meta):
        pack = build_educational_reporting_pack(
            portfolio=small_portfolio,
            run_id=run_meta["run_id"],
            lock_id=run_meta["lock_id"],
        )
        text = pack.section_text("run_log")
        assert "Model Run Log" in text

    def test_section_text_invalid_raises(self, small_portfolio, run_meta):
        pack = build_educational_reporting_pack(
            portfolio=small_portfolio,
            run_id=run_meta["run_id"],
            lock_id=run_meta["lock_id"],
        )
        with pytest.raises(ValueError, match="Unknown section"):
            pack.section_text("nonexistent")

    def test_with_exceptions_in_suite(self, small_portfolio, run_meta, mixed_suite):
        pack = build_educational_reporting_pack(
            portfolio=small_portfolio,
            run_id=run_meta["run_id"],
            lock_id=run_meta["lock_id"],
            validation_suite_dict=mixed_suite,
        )
        assert pack.validation_exceptions.overall_status == "EXCEPTIONS"
        assert pack.validation_exceptions.n_exceptions == 2

    def test_version_field_present(self, small_portfolio, run_meta):
        pack = build_educational_reporting_pack(
            portfolio=small_portfolio,
            run_id=run_meta["run_id"],
            lock_id=run_meta["lock_id"],
        )
        assert pack.version == "1.0.0"
