"""Tests for Phase 26 Task 4 full-vs-reanchored delta matrix."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from par_model_v2.projection.pathwise_delta_matrix import (
    BASES,
    COPULAS,
    MR_REFRESH_TRIGGER_FRACTION,
    attach_marginal_cis,
    build_paired_deltas,
    build_point_matrix,
    delta_matrix_digest,
    delta_matrix_use_restrictions,
    mr_refresh_trigger,
    rank_invariance_ok,
)

REPORT = Path("docs/validation/PHASE26_TASK4_DELTA_MATRIX_REPORT.json")
TASK2 = Path("docs/validation/PHASE26_TASK2_COMPOSITION_TRANSFORM_REPORT.json")
TASK3 = Path("docs/validation/PHASE26_TASK3_MARGIN_BOOTSTRAP_REPORT.json")


def _task_reports():
    return (
        json.loads(TASK2.read_text(encoding="utf-8")),
        json.loads(TASK3.read_text(encoding="utf-8")),
    )


def _bootstrap_records():
    records = []
    for p in sorted(Path("/var/tmp/p26t3_stage").glob("partial_*.json")):
        records.extend(json.loads(p.read_text(encoding="utf-8"))["records"])
    if not records:
        pytest.skip("Task 3 staged bootstrap partials not available")
    return records


def test_point_matrix_contains_all_bases_and_copulas():
    task2, _ = _task_reports()
    matrix = build_point_matrix(task2["result"])
    assert tuple(matrix) == BASES
    for basis in BASES:
        assert set(matrix[basis]) == set(COPULAS)
    assert matrix["without"]["t"] > matrix["component"]["t"]
    assert matrix["component"]["t"] >= matrix["level"]["t"]


def test_bootstrap_ci_attached_from_task3():
    _, task3 = _task_reports()
    cis = attach_marginal_cis(task3["result"])
    ci = cis["component"]["t"]
    assert ci["mean"] == pytest.approx(
        task3["result"]["component_t_scr_ci"]["mean"], abs=1e-9)
    assert ci["se_frac_of_mean"] <= 0.05


def test_paired_deltas_show_significant_but_sub_one_percent_correction():
    paired = build_paired_deltas(_bootstrap_records())
    trig = mr_refresh_trigger(paired)
    assert paired["composition_correction_t"]["excludes_zero"] is True
    assert paired["composition_correction_g"]["excludes_zero"] is True
    assert trig["threshold"] == MR_REFRESH_TRIGGER_FRACTION
    assert trig["trigger_fired"] is False
    assert trig["max_abs_rel"] < MR_REFRESH_TRIGGER_FRACTION


def test_rank_invariance_evidence_passes():
    task2, task3 = _task_reports()
    ev = rank_invariance_ok(
        task3["df_rematched"], task3["rho_max_abs_diff"], 2.9451, 1e-4, 1e-12)
    assert ev["rank_invariant"] is True
    assert abs(ev["df_rematched"] - task2["df_rematched"]) <= 1e-12


def test_digest_is_deterministic():
    task2, _ = _task_reports()
    point = build_point_matrix(task2["result"])
    paired = {
        "x": {"mean": 1.0, "ci_lo": 0.5, "ci_hi": 1.5},
        "y": {"mean": 2.0, "ci_lo": 1.0, "ci_hi": 3.0},
    }
    assert delta_matrix_digest(point, paired) == delta_matrix_digest(dict(point), paired)


def test_use_restrictions_are_educational():
    r = delta_matrix_use_restrictions()
    assert r["classification"] == "EDUCATIONAL"
    assert len(r["scope"]) >= 3


@pytest.mark.skipif(not REPORT.exists(), reason="Task 4 report not built")
class TestPublishedReport:
    @pytest.fixture(scope="class")
    def rep(self):
        return json.loads(REPORT.read_text(encoding="utf-8"))

    def test_verdict_and_gates(self, rep):
        assert rep["verdict"] == "PASS"
        assert rep["result"]["gates"]["D1_rank_invariance_reverified"] is True
        assert rep["result"]["gates"]["D2_delta_matrix_assembled_with_cis"] is True
        assert rep["result"]["gates"]["D3_mr_trigger_rechecked"] is True
        assert rep["result"]["gates"]["D4_idempotent_digest_stable"] is True

    def test_mr_refresh_not_required(self, rep):
        assert rep["result"]["mr_trigger"]["trigger_fired"] is False
        assert rep["result"]["mr_trigger"]["max_abs_rel"] < 0.01

    def test_nested_reference_outside_task3_ci_disclosed(self, rep):
        # Published report key was restructured: the old flat
        # ``distance_to_nested{nested_reference, t_component_rel_gap}`` is now
        # ``config.nested_pathwise_reference`` plus the per-basis/copula
        # ``gap_to_nested`` matrix. Read the live keys (frozen-test-vs-moving-
        # repo guard, mirroring the Finding(3) fix); intent is unchanged: the
        # nested reference is 46638.9 and the component/t basis point sits more
        # than 14% below the nested truth (outside the Task 3 CI, disclosed).
        assert rep["result"]["config"]["nested_pathwise_reference"] == pytest.appro