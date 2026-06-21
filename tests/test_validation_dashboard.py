"""
Tests for par_model_v2.validation.validation_dashboard
=======================================================

Phase 12, Task 4 — Validation Dashboards and Markdown Reports

Test coverage
-------------
T01  build_validation_dashboard returns a ValidationDashboard instance
T02  report_id is a non-empty UUID string
T03  generated_at is ISO-8601 UTC
T04  Section 1: HealthPanel — correct type, fields, pass_rate_pct
T05  Section 1: overall_status is one of PASS/WARN/FAIL
T06  Section 2: IAValidationPanel — correct totals (31 requirements)
T07  Section 2: layer_summary covers all 7 layers
T08  Section 2: critical_failures is a list
T09  Section 3: LimitationCardPanel — correct counts from default cards
T10  Section 3: area_summary keys are strings
T11  Section 4: CalibrationPanel — all_converged True, 4 modules
T12  Section 5: SuitePanel — total >= 1000, area_counts dict
T13  Section 6: PhaseTrackerPanel — 12 phases, completion_pct
T14  Section 7: ReadinessVerdict — verdict is valid enum value
T15  Section 7: production_cleared is always False
T16  to_dict returns a dict with 'sections' key
T17  to_json is valid JSON with expected keys
T18  to_markdown contains all 7 section headers
T19  to_markdown contains educational disclaimer
T20  HealthPanel.to_markdown contains check IDs
T21  IAValidationPanel.to_markdown contains layer labels
T22  LimitationCardPanel.to_markdown contains area rows
T23  CalibrationPanel.to_markdown contains market names
T24  SuitePanel.to_markdown lists heavy suites
T25  PhaseTrackerPanel.to_markdown contains progress bar
T26  ReadinessVerdict.to_markdown contains verdict string
T27  write_validation_dashboard writes two files
T28  Written JSON file is valid JSON
T29  Written Markdown file is non-empty
T30  _pct helper: correct percentage and zero-denominator guard
T31  HealthPanel pass_rate_pct: 10/10 = 100.0
T32  PhaseTrackerPanel completion_pct: consistent with done/total
T33  IAValidationPanel layer_summary values are dicts of int
T34  LimitationCardPanel critical_open is a list of strings
T35  CalibrationPanel modules list matches CALIBRATION_EVIDENCE
T36  to_dict sections keys follow naming convention
T37  re-running build_validation_dashboard produces fresh report_id
T38  ValidationDashboard report_version matches REPORT_VERSION constant
T39  ValidationDashboard model_version matches MODEL_VERSION constant
T40  write_validation_dashboard custom filenames respected
T41  HealthPanel total = passed + warned + failed + skipped
T42  IAValidationPanel total = passed + failed + partial + not_run + waived
T43  PhaseTrackerPanel phases_complete <= 12
T44  ReadinessVerdict gates_met is non-empty list
T45  ReadinessVerdict gates_not_met is a list (may be empty)
T46  LimitationCardPanel open_count + mitigated_count <= total
T47  CalibrationPanel to_dict includes 'all_converged' key
T48  SuitePanel to_dict includes 'total_tests' key
T49  governance/__init__.py imports resolve without SyntaxError
T50  Full markdown round-trip: to_markdown then check section count
"""
from __future__ import annotations

import json
import os
import sys
import tempfile

import pytest

# Ensure the repo root is on the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from par_model_v2.validation.validation_dashboard import (
    CALIBRATION_EVIDENCE,
    MODEL_VERSION,
    REPORT_VERSION,
    CalibrationPanel,
    HealthPanel,
    IAValidationPanel,
    LimitationCardPanel,
    PhaseTrackerPanel,
    ReadinessVerdict,
    SuitePanel,
    ValidationDashboard,
    _build_calibration_panel,
    _build_health_panel,
    _build_ia_validation_panel,
    _build_limitation_card_panel,
    _build_phase_tracker,
    _build_test_suite_panel,
    _pct,
    build_validation_dashboard,
    write_validation_dashboard,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def dashboard() -> ValidationDashboard:
    """Build one dashboard for the whole module — expensive section takes ~1s."""
    return build_validation_dashboard()


# ---------------------------------------------------------------------------
# T01-T03  Top-level attributes
# ---------------------------------------------------------------------------

def test_t01_returns_validation_dashboard(dashboard):
    assert isinstance(dashboard, ValidationDashboard)


def test_t02_report_id_is_uuid_string(dashboard):
    import uuid
    assert isinstance(dashboard.report_id, str)
    assert len(dashboard.report_id) == 36
    uuid.UUID(dashboard.report_id)  # raises ValueError if malformed


def test_t03_generated_at_is_iso8601(dashboard):
    from datetime import datetime, timezone
    dt = datetime.strptime(dashboard.generated_at, "%Y-%m-%dT%H:%M:%SZ")
    assert dt.year >= 2026


# ---------------------------------------------------------------------------
# T04-T05  Section 1 — Health
# ---------------------------------------------------------------------------

def test_t04_health_panel_fields(dashboard):
    h = dashboard.health
    assert isinstance(h, HealthPanel)
    assert isinstance(h.total, int) and h.total > 0
    assert isinstance(h.passed, int)
    assert 0.0 <= h.pass_rate_pct <= 100.0


def test_t05_health_overall_status_valid(dashboard):
    assert dashboard.health.overall_status in ("PASS", "WARN", "FAIL")


# ---------------------------------------------------------------------------
# T06-T08  Section 2 — IA Validation
# ---------------------------------------------------------------------------

def test_t06_ia_panel_31_requirements(dashboard):
    assert dashboard.ia_validation.total == 31


def test_t07_ia_layer_summary_7_layers(dashboard):
    layers = set(dashboard.ia_validation.layer_summary.keys())
    expected = {"Unit", "Integration", "Stochastic", "Sensitivity", "Backtest", "Governance", "Data"}
    assert layers == expected


def test_t08_ia_critical_failures_list(dashboard):
    assert isinstance(dashboard.ia_validation.critical_failures, list)


# ---------------------------------------------------------------------------
# T09-T10  Section 3 — Limitation Cards
# ---------------------------------------------------------------------------

def test_t09_limitation_card_panel_counts(dashboard):
    lc = dashboard.limitation_cards
    assert isinstance(lc, LimitationCardPanel)
    assert lc.total >= 11  # 11 default cards
    assert lc.open_count >= 0


def test_t10_area_summary_string_keys(dashboard):
    for k in dashboard.limitation_cards.area_summary:
        assert isinstance(k, str)


# ---------------------------------------------------------------------------
# T11  Section 4 — Calibration
# ---------------------------------------------------------------------------

def test_t11_calibration_all_converged_4_modules(dashboard):
    cal = dashboard.calibration
    assert isinstance(cal, CalibrationPanel)
    assert cal.all_converged is True
    assert len(cal.modules) == 4


# ---------------------------------------------------------------------------
# T12  Section 5 — Test Suite
# ---------------------------------------------------------------------------

def test_t12_test_suite_total_at_least_1000(dashboard):
    ts = dashboard.test_suite
    assert isinstance(ts, SuitePanel)
    assert ts.total_tests >= 1000
    assert isinstance(ts.area_counts, dict)


# ---------------------------------------------------------------------------
# T13  Section 6 — Phase Tracker
# ---------------------------------------------------------------------------

def test_t13_phase_tracker_12_phases(dashboard):
    pt = dashboard.phase_tracker
    assert isinstance(pt, PhaseTrackerPanel)
    assert len(pt.phases) == 12
    assert 0.0 <= pt.completion_pct <= 100.0


# ---------------------------------------------------------------------------
# T14-T15  Section 7 — Readiness
# ---------------------------------------------------------------------------

def test_t14_readiness_verdict_valid(dashboard):
    valid = {"READY_FOR_EDUCATIONAL_USE", "NEEDS_ATTENTION", "NOT_READY"}
    assert dashboard.readiness.verdict in valid


def test_t15_production_cleared_always_false(dashboard):
    assert dashboard.readiness.production_cleared is False


# ---------------------------------------------------------------------------
# T16-T19  Serialisation
# ---------------------------------------------------------------------------

def test_t16_to_dict_has_sections_key(dashboard):
    d = dashboard.to_dict()
    assert isinstance(d, dict)
    assert "sections" in d
    assert len(d["sections"]) == 7


def test_t17_to_json_valid(dashboard):
    j = dashboard.to_json()
    parsed = json.loads(j)
    assert parsed["model_version"] == MODEL_VERSION
    assert "sections" in parsed


def test_t18_to_markdown_has_7_section_headers(dashboard):
    md = dashboard.to_markdown()
    for n in range(1, 8):
        assert f"## Section {n}" in md


def test_t19_to_markdown_has_disclaimer(dashboard):
    md = dashboard.to_markdown()
    assert "EDUCATIONAL MODEL" in md
    assert "Not cleared for production" in md


# ---------------------------------------------------------------------------
# T20-T26  Per-section markdown
# ---------------------------------------------------------------------------

def test_t20_health_markdown_contains_check_ids(dashboard):
    md = dashboard.health.to_markdown()
    for i in range(1, 11):
        assert f"VR-H{i:02d}" in md


def test_t21_ia_markdown_contains_layer_labels(dashboard):
    md = dashboard.ia_validation.to_markdown()
    assert "Layer 1 — Unit" in md
    assert "Layer 7 — Data" in md


def test_t22_limitation_card_markdown_has_area_rows(dashboard):
    md = dashboard.limitation_cards.to_markdown()
    for area in dashboard.limitation_cards.area_summary:
        assert area in md


def test_t23_calibration_markdown_has_market_names(dashboard):
    md = dashboard.calibration.to_markdown()
    assert "USD" in md
    assert "HK/CN" in md


def test_t24_test_suite_markdown_lists_heavy_suites(dashboard):
    md = dashboard.test_suite.to_markdown()
    assert "Monte Carlo" in md


def test_t25_phase_tracker_markdown_has_progress_bar(dashboard):
    md = dashboard.phase_tracker.to_markdown()
    assert "█" in md or "░" in md


def test_t26_readiness_markdown_has_verdict(dashboard):
    md = dashboard.readiness.to_markdown()
    assert dashboard.readiness.verdict in md


# ---------------------------------------------------------------------------
# T27-T29  write_validation_dashboard
# ---------------------------------------------------------------------------

def test_t27_write_creates_two_files():
    with tempfile.TemporaryDirectory() as tmpdir:
        j, m = write_validation_dashboard(output_dir=tmpdir)
        assert os.path.isfile(j)
        assert os.path.isfile(m)


def test_t28_written_json_is_valid():
    with tempfile.TemporaryDirectory() as tmpdir:
        j, _ = write_validation_dashboard(output_dir=tmpdir)
        with open(j, encoding="utf-8") as f:
            parsed = json.load(f)
        assert "sections" in parsed


def test_t29_written_markdown_non_empty():
    with tempfile.TemporaryDirectory() as tmpdir:
        _, m = write_validation_dashboard(output_dir=tmpdir)
        with open(m, encoding="utf-8") as f:
            content = f.read()
        assert len(content) > 1000


# ---------------------------------------------------------------------------
# T30-T32  Helper / computation checks
# ---------------------------------------------------------------------------

def test_t30_pct_helper():
    assert _pct(5, 10) == 50.0
    assert _pct(10, 10) == 100.0
    assert _pct(0, 0) == 0.0     # zero-denominator guard


def test_t31_health_pass_rate_10_of_10():
    panel = _build_health_panel()
    if panel.total == 10 and panel.passed == 10:
        assert panel.pass_rate_pct == 100.0


def test_t32_phase_tracker_completion_consistent():
    pt = _build_phase_tracker()
    expected = round(100.0 * pt.done_tasks / pt.total_tasks, 1)
    assert abs(pt.completion_pct - expected) < 0.01


# ---------------------------------------------------------------------------
# T33-T36  Data integrity
# ---------------------------------------------------------------------------

def test_t33_ia_layer_summary_values_are_dicts(dashboard):
    for layer, counts in dashboard.ia_validation.layer_summary.items():
        assert isinstance(counts, dict)
        for k, v in counts.items():
            assert isinstance(k, str)
            assert isinstance(v, int)


def test_t34_limitation_critical_open_list_of_strings(dashboard):
    for item in dashboard.limitation_cards.critical_open:
        assert isinstance(item, str)


def test_t35_calibration_modules_match_evidence(dashboard):
    assert len(dashboard.calibration.modules) == len(CALIBRATION_EVIDENCE)
    for m in dashboard.calibration.modules:
        assert "module" in m and "status" in m


def test_t36_to_dict_section_keys_naming(dashboard):
    sections = dashboard.to_dict()["sections"]
    keys = list(sections.keys())
    assert keys[0].startswith("1_")
    assert keys[-1].startswith("7_")


# ---------------------------------------------------------------------------
# T37-T40  Miscellaneous
# ---------------------------------------------------------------------------

def test_t37_fresh_report_id_each_call():
    d1 = build_validation_dashboard()
    d2 = build_validation_dashboard()
    assert d1.report_id != d2.report_id


def test_t38_report_version_matches_constant(dashboard):
    assert dashboard.report_version == REPORT_VERSION


def test_t39_model_version_matches_constant(dashboard):
    assert dashboard.model_version == MODEL_VERSION


def test_t40_custom_filenames_respected():
    with tempfile.TemporaryDirectory() as tmpdir:
        j, m = write_validation_dashboard(
            output_dir=tmpdir,
            json_filename="custom.json",
            md_filename="custom.md",
        )
        assert j.endswith("custom.json")
        assert m.endswith("custom.md")


# ---------------------------------------------------------------------------
# T41-T45  Arithmetic invariants
# ---------------------------------------------------------------------------

def test_t41_health_counts_sum_to_total(dashboard):
    h = dashboard.health
    assert h.passed + h.warned + h.failed + h.skipped == h.total


def test_t42_ia_counts_sum_to_total(dashboard):
    ia = dashboard.ia_validation
    assert ia.passed + ia.failed + ia.partial + ia.not_run + ia.waived == ia.total


def test_t43_phases_complete_at_most_12(dashboard):
    assert dashboard.phase_tracker.phases_complete <= 12


def test_t44_readiness_gates_met_non_empty(dashboard):
    assert len(dashboard.readiness.gates_met) > 0


def test_t45_readiness_gates_not_met_is_list(dashboard):
    assert isinstance(dashboard.readiness.gates_not_met, list)


# ---------------------------------------------------------------------------
# T46-T50  Edge cases and structural checks
# ---------------------------------------------------------------------------

def test_t46_limitation_open_plus_mitigated_le_total(dashboard):
    lc = dashboard.limitation_cards
    assert lc.open_count + lc.mitigated_count <= lc.total


def test_t47_calibration_to_dict_has_all_converged():
    cal = _build_calibration_panel()
    d = cal.to_dict()
    assert "all_converged" in d


def test_t48_test_suite_to_dict_has_total_tests():
    ts = _build_test_suite_panel()
    d = ts.to_dict()
    assert "total_tests" in d


def test_t49_governance_init_imports_cleanly():
    """Regression: governance/__init__.py was truncated — verify it imports."""
    from par_model_v2.governance import GovernanceStore, LimitationCardReport
    assert GovernanceStore is not None
    assert LimitationCardReport is not None


def test_t50_markdown_section_count():
    """Full markdown must contain exactly 7 '## Section N' headers."""
    dashboard = build_validation_dashboard()
    md = dashboard.to_markdown()
    count = sum(1 for line in md.splitlines() if line.startswith("## Section"))
    assert count == 7
