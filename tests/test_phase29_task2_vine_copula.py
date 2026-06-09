"""Phase 29 Task 2 - vine / pair-copula prototype tests."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from par_model_v2.projection.joint_action_aggregation import JointActionAggregator
from par_model_v2.projection.management_actions import ManagementActionRule
from par_model_v2.projection.vine_copula_pair_aggregation import (
    FIT_FRACTION,
    TAIL_LEVEL_P,
    _rank_pit,
    fit_vine_pair_families,
    simulate_vine_pair_copula_uniforms,
    vine_pair_copula_use_restrictions,
)
from par_model_v2.projection.t_copula_tail_matched_aggregation import (
    simulate_t_copula_uniforms,
)
from par_model_v2.projection.vine_copula_upgrade import (
    DRIVER_NAMES,
    FIRST_TREE_EDGES,
    FROZEN_T_COMPONENT_SCR_REFERENCE,
    PAIR_FAMILY_CANDIDATES,
    RANK_INVARIANCE_DF,
    SECOND_TREE_EDGES,
    VINE_BOUNDARY_RECOVERY_TOL,
    VINE_ROOT_DRIVER,
)


DRIVERS = tuple(DRIVER_NAMES)
P23T2 = Path("/var/tmp/p23t2_stage/losses.npz")
P23T4 = Path("/var/tmp/p23t4_stage/losses_with_actions.npz")
P26T2V = Path("/var/tmp/p26t2_stage/verified_inputs.npz")
REPORT = Path("docs/validation/PHASE29_TASK2_VINE_COPULA_REPORT.json")

_staged = P23T2.exists() and P23T4.exists() and P26T2V.exists()
needs_stage = pytest.mark.skipif(not _staged, reason="staged inputs absent")


def _corr7(rho=0.35):
    R = np.full((7, 7), rho)
    np.fill_diagonal(R, 1.0)
    return R


def _synthetic_losses(n=6000, seed=29):
    rng = np.random.default_rng(seed)
    z = rng.standard_normal((n, 7)) @ np.linalg.cholesky(_corr7(0.25)).T
    # Force a credit / liquidity / fx upper-tail corner so the family fit has
    # something real to select without using holdout data.
    credit_tail = np.maximum(z[:, 2] - np.quantile(z[:, 2], 0.85), 0.0)
    z[:, 6] += 1.25 * credit_tail
    z[:, 5] += 0.90 * credit_tail
    return {name: z[:, i] for i, name in enumerate(DRIVERS)}


def test_boundary_mode_bit_identical_to_single_t_uniforms():
    losses = _synthetic_losses()
    fit = fit_vine_pair_families(losses, DRIVERS)
    r1 = np.random.default_rng(123)
    U_t = simulate_t_copula_uniforms(r1, 30000, _corr7(), RANK_INVARIANCE_DF)
    r2 = np.random.default_rng(123)
    U_b = simulate_vine_pair_copula_uniforms(
        r2, 30000, _corr7(), RANK_INVARIANCE_DF, fit, mode="frozen_t_boundary"
    )
    assert np.max(np.abs(U_t - U_b)) <= VINE_BOUNDARY_RECOVERY_TOL


def test_pre_registered_edges_and_family_set_pinned():
    assert VINE_ROOT_DRIVER == 2
    assert all(VINE_ROOT_DRIVER in e for e in FIRST_TREE_EDGES)
    assert all(e[2] == VINE_ROOT_DRIVER for e in SECOND_TREE_EDGES)
    assert set(PAIR_FAMILY_CANDIDATES) == {
        "gaussian",
        "student_t",
        "survival_clayton",
        "survival_gumbel",
    }


def test_fit_uses_disjoint_fit_and_holdout_rows():
    fit = fit_vine_pair_families(_synthetic_losses(), DRIVERS, fit_fraction=FIT_FRACTION)
    assert fit.fit_indices_digest != fit.holdout_indices_digest
    assert len(fit.selections) == len(FIRST_TREE_EDGES) + len(SECOND_TREE_EDGES)
    assert set(fit.to_dict()["family_counts"]) == set(PAIR_FAMILY_CANDIDATES)
    assert all(sel.n_fit > 0 for sel in fit.selections)
    assert all(sel.n_holdout > 0 for sel in fit.selections)


def test_fit_selects_only_allowed_families_and_records_holdout_metrics():
    fit = fit_vine_pair_families(_synthetic_losses(), DRIVERS)
    allowed = set(PAIR_FAMILY_CANDIDATES)
    for sel in fit.selections:
        assert sel.family in allowed
        assert set(sel.candidate_scores) == allowed
        assert sel.holdout_upper >= 0.0
        assert sel.holdout_lower >= 0.0
        assert sel.fit_score == pytest.approx(sel.candidate_scores[sel.family])


def test_candidate_preserves_uniform_margins_by_reranking():
    losses = _synthetic_losses()
    fit = fit_vine_pair_families(losses, DRIVERS)
    U = simulate_vine_pair_copula_uniforms(
        np.random.default_rng(7), 80000, _corr7(), RANK_INVARIANCE_DF, fit, mode="candidate"
    )
    assert np.all(np.abs(U.mean(axis=0) - 0.5) < 0.01)
    assert np.all(np.abs(np.quantile(U, 0.90, axis=0) - 0.90) < 0.01)


def test_pair_fit_reacts_to_credit_tail_corner():
    fit = fit_vine_pair_families(_synthetic_losses(), DRIVERS)
    credit_liq = [s for s in fit.selections if s.edge == (2, 6)][0]
    assert credit_liq.fit_upper >= credit_liq.fit_lower
    assert credit_liq.family in {"survival_gumbel", "student_t"}


def test_use_restrictions_reference_mr016():
    r = vine_pair_copula_use_restrictions()
    assert r["classification"] == "EDUCATIONAL"
    assert r["references"]["existing_risk"] == "MR-016"
    assert any("frozen_t_boundary" in x for x in r["restrictions"])


@needs_stage
def test_stage_inputs_can_fit_and_preserve_boundary():
    from scripts.build_phase29_task2_vine_copula import _aggregator
    from par_model_v2.projection.vine_copula_pair_aggregation import (
        composition_vine_pair_readout,
    )

    z = np.load(P23T2)
    w = np.load(P23T4)
    s = np.load(P26T2V)
    rho = np.asarray(s["rho"], dtype=float)
    agg = _aggregator(z, w, rho)
    losses = {k: np.asarray(z[k], dtype=float) for k in DRIVERS}
    fit = fit_vine_pair_families(losses, DRIVERS)
    ro = composition_vine_pair_readout(
        agg,
        200000,
        20260607,
        fit,
        float(s["sigma"][0]),
        float(s["alpha"][0]),
        float(s["beta_fit"][0]),
        0.995,
        mode="frozen_t_boundary",
    )
    assert ro["scr_component"] == FROZEN_T_COMPONENT_SCR_REFERENCE


@needs_stage
def test_report_verdict_pass_when_built():
    if not REPORT.exists():
        pytest.skip("Phase 29 Task 2 report not built")
    rep = json.loads(REPORT.read_text(encoding="utf-8"))
    assert rep["verdict"] == "PASS"
    assert all(rep["result"]["gates"].values())
    assert rep["result"]["boundary_recovery_dev"] <= VINE_BOUNDARY_RECOVERY_TOL

