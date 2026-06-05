"""
Tests for Phase 13 Task 4: IA TAS M validation suite (G-06).
"""

from __future__ import annotations

import json
from pathlib import Path

from par_model_v2.validation import (
    ValidationCategory,
    ValidationStatus,
    run_phase13_ia_tas_m_validation,
)
from par_model_v2.validation.phase13_ia_tas_m import (
    REPORT_JSON_NAME,
    REPORT_MD_NAME,
    build_phase13_validation_requirements,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_phase13_requirement_builder_attaches_all_checks() -> None:
    reqs = build_phase13_validation_requirements(REPO_ROOT)

    assert len(reqs) == 31
    assert all(req.check_fn is not None for req in reqs)


def test_phase13_g06_suite_reaches_threshold_and_archives_reports(tmp_path) -> None:
    result = run_phase13_ia_tas_m_validation(
        repo_root=REPO_ROOT,
        output_dir=tmp_path,
        write_reports=True,
        persist_governance=False,
    )
    report = result.validation_report

    assert report.total == 31
    assert report.compliance_pct() >= 80.0
    assert report.compliance_pct(ValidationCategory.STOCHASTIC) == 100.0
    assert report.compliance_pct(ValidationCategory.DATA) == 100.0
    assert report.critical_failures == []
    assert result.gate_g06.status == "PASS"

    json_path = tmp_path / REPORT_JSON_NAME
    md_path = tmp_path / REPORT_MD_NAME
    assert json_path.exists()
    assert md_path.exists()
    parsed = json.loads(json_path.read_text(encoding="utf-8"))
    assert parsed["summary"]["total"] == 31


def test_phase13_suite_keeps_production_residuals_visible(tmp_path) -> None:
    result = run_phase13_ia_tas_m_validation(
        repo_root=REPO_ROOT,
        output_dir=tmp_path,
        write_reports=True,
        persist_governance=False,
    )
    statuses = {r.req_id: r.status for r in result.validation_report.results}

    assert statuses["VR-B01"] == ValidationStatus.PARTIAL
    assert statuses["VR-B02"] == ValidationStatus.PARTIAL
    assert statuses["VR-B03"] == ValidationStatus.PARTIAL
    assert statuses["VR-G03"] == ValidationStatus.PARTIAL
    assert statuses["VR-G05"] == ValidationStatus.WAIVED
    assert any("G-09" in item for item in result.residual_items)
