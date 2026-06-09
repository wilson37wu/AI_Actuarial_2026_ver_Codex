"""Phase 28 Task 2 -- grouped t-copula re-aggregation unit tests.

Verifies the pre-registered Task 2 gates from the Phase 28 Task 1 design
note: homogeneous-boundary EXACT recovery of the frozen single-df t-copula,
frozen (homogeneous df, Sigma) rank invariance, uniform per-block margins,
the within-block-vs-cross-block tail-dependence heterogeneity mechanism, the
leakage-free per-block df fit, the pre-registered partition, and the component
re-aggregation read-out. EDUCATIONAL model.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from par_model_v2.projection.joint_action_aggregation import JointActionAggregator
from par_model_v2.projection.management_actions import ManagementActionRule
from par_model_v2.projection.pathwise_composition_transform import (
    composition_joint_readout,
)
from par_model_v2.projection.grouped_t_copula_aggregation import (
    BLOCKS,
    FIN_BLOCK,
    FROZEN_T_COMPONENT_SCR_REFERENCE,
    HOMOGENEOUS_RECOVERY_TOL,
    NONFIN_BLOCK,
    RANK_INVARIANCE_DF,
    TAIL_LEVEL_P,
    _avg_pairwise_upper_codependence_over_pairs,
    _tail_dependence_blocks,
    _within_pairs,
    composition_grouped_t_readout,
    fit_grouped_t_block_dfs,
    grouped_t_copula_use_restrictions,
    realised_block_codependence,
    simulate_grouped_t_copula_uniforms,
)
from par_model_v2.projection.t_copula_tail_matched_aggregation import (
    simulate_t_copula_uniforms,
)

DRIVERS = ("rate", "equity", "credit", "lapse", "mortality", "fx", "liquidity")
P23T2 = Path("/var/tmp/p23t2_stage/losses.npz")
P23T4 = Path("/var/tmp/p23t4_stage/losses_with_actions.npz")
P26T2V = Path("/var/tmp/p26t2_stage/verified_inputs.npz")
REPORT = Path("docs/validation/PHASE28_TASK2_GROUPED_T_COPULA_REPORT.json")

_staged = P23T2.exists() and P23T4.exists() and P26T2V.exists()
needs_stage = pytest.mark.skipif(not _staged, reason="staged inputs absent")


def _corr7(rho=0.4):
    R = np.full((7, 7), rho)
    np.fill_diagonal(R, 1.0)
    return R


# --------------------------------------------------------------------------
# Self-contained gates (no staged inputs needed)
# --------------------------------------------------------------------------
def test_homogeneous_boundary_uniforms_bit_identical_to_single_t():
    """G1 core: all df_g = frozen df + shared mixing reproduces the single-df
    t-copula uniforms EXACTLY (the freeze is the homogeneous boundary)."""
    R = _corr7()
    df = RANK_INVARIANCE_DF
    r1 = np.random.default_rng(123)
    U_sym = simulate_t_copula_uniforms(r1, 40000, R, df)
    r2 = np.random.default_rng(123)
    U_grp = simulate_grouped_t_copula_uniforms(
        r2, 40000, R, [df, df], BLOCKS, shared_mixing=True)
    assert np.max(np.abs(U_grp - U_sym)) == 0.0


def test_block_partition_constants():
    assert set(FIN_BLOCK) == {2, 5, 6}
    assert set(NONFIN_BLOCK) == {0, 1, 3, 4}
    members = sorted(i for blk in BLOCKS for i in blk)
    assert members == list(range(7))


@pytest.mark.parametrize("dfs", [[15.0, 2.5], [8.0, 3.0]])
def test_margins_uniform_per_block(dfs):
    """Per-block t marginal keeps each margin uniform (frozen margins untouched)."""
    R = _corr7(rho=0.3)
    U = simulate_grouped_t_copula_uniforms(
        np.random.default_rng(9), 150000, R, dfs, BLOCKS, shared_mixing=False)
    means = U.mean(axis=0)
    q90 = np.quantile(U, 0.90, axis=0)
    assert np.all(np.abs(means - 0.5) < 0.01)
    assert np.all(np.abs(q90 - 0.90) < 0.01)


def test_within_block_tail_dependence_rises_as_fin_df_falls():
    """Mechanism: a heavier FIN block (lower df_fin) lifts within-FIN upper
    tail dependence above the cross-block level (heterogeneity a single pooled
    df cannot produce)."""
    R = _corr7(rho=0.4)
    het = {}
    for df_fin in (5.0, 2.2):
        U = simulate_grouped_t_copula_uniforms(
            np.random.default_rng(5), 200000, R, [20.0, df_fin], BLOCKS,
            shared_mixing=False)
        td = _tail_dependence_blocks(U, BLOCKS, 0.95)
        het[df_fin] = td["heterogeneity_upper"]
    assert het[2.2] > het[5.0]
    assert het[2.2] > 0.0


def test_simulator_rejects_non_partition_blocks():
    with pytest.raises(ValueError):
        simulate_grouped_t_copula_uniforms(
            np.random.default_rng(0), 100, _corr7(), [3.0, 3.0],
            [(0, 1, 2), (3, 4, 5)], shared_mixing=False)  # 6 missing


def test_simulator_rejects_nonpositive_df():
    with pytest.raises(ValueError):
        simulate_grouped_t_copula_uniforms(
            np.random.default_rng(0), 100, _corr7(), [3.0, -1.0], BLOCKS,
            shared_mixing=False)


def test_use_restrictions_educational():
    r = grouped_t_copula_use_restrictions()
    assert r["classification"] == "EDUCATIONAL"
    assert len(r["restrictions"]) >= 4


# --------------------------------------------------------------------------
# Staged-input gates (real frozen basis)
# --------------------------------------------------------------------------
def _aggregator():
    z = np.load(P23T2); w = np.load(P23T4); s = np.load(P26T2V)
    agg = JointActionAggregator(
        standalone_losses={k: np.asarray(z[k], float) for k in DRIVERS},
        correlation=np.asarray(s["rho"], float), rule=ManagementActionRule(),
        l_fit=float(w["l_fit"][0]),
        anchor_means={k: float(w[k + "_anchor_mean"][0]) for k in DRIVERS})
    return agg, s, z


@needs_stage
def test_gate1_homogeneous_exact_recovery_of_frozen_t_component():
    agg, s, _ = _aggregator()
    sigma, alpha, beta = (float(s["sigma"][0]), float(s["alpha"][0]),
                          float(s["beta_fit"][0]))
    ro_t = composition_joint_readout(agg, 200000, 20260607, RANK_INVARIANCE_DF,
                                     sigma, alpha, beta, 0.995)
    ro_hom = composition_grouped_t_readout(
        agg, 200000, 20260607, [RANK_INVARIANCE_DF, RANK_INVARIANCE_DF], BLOCKS,
        sigma, alpha, beta, 0.995, shared_mixing=True)
    assert ro_t["scr_component"] == FROZEN_T_COMPONENT_SCR_REFERENCE
    assert abs(ro_hom["scr_component"] - ro_t["scr_component"]) <= \
        HOMOGENEOUS_RECOVERY_TOL
    # G8 single-df variant equals frozen exactly; G4 without-basis bit-identical
    assert ro_hom["scr_component"] == FROZEN_T_COMPONENT_SCR_REFERENCE
    assert ro_hom["scr_without"] == ro_t["scr_without"]


@needs_stage
def test_gate6_block_df_fit_leakage_free_converges():
    """Per-block df_g fit converges; realised within-block co-exceedances do
    NOT show within-FIN >> cross-block concentration (so the leakage-free fit
    does not pin df low -- the disclosed material finding)."""
    agg, s, z = _aggregator()
    losses = {k: np.asarray(z[k], float) for k in DRIVERS}
    fit = fit_grouped_t_block_dfs(
        losses, DRIVERS, np.asarray(s["rho"], float), BLOCKS, p=TAIL_LEVEL_P,
        n_sim=60000, seed=20260608)
    assert fit["all_converged"]
    assert len(fit["block_dfs_hat"]) == 2
    realised = realised_block_codependence(losses, DRIVERS, BLOCKS, TAIL_LEVEL_P)
    # within-FIN realised co-exceedance is not above the cross-block level
    assert realised["within_block"][1] <= realised["cross_block"] + 1e-9


@needs_stage
def test_report_verdict_pass_and_all_gates():
    rep = json.loads(REPORT.read_text(encoding="utf-8"))
    assert rep["verdict"] == "PASS"
    assert all(rep["result"]["gates"].values())
    assert rep["df_frozen"] == RANK_INVARIANCE_DF
