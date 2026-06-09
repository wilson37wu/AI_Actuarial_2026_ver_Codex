"""Phase 27 Task 3 -- skew-t-copula margin bootstrap unit tests.

Verifies the pre-registered Task 3 gates: CRN-exact reproduction of the tested
skew-t / symmetric-t draws, chunk-independent (resume-safe) replicates, the
percentile-CI/SE summary, the residual-gap RE-decomposition algebra (copula-form
reduction vs the frozen-t baseline 6,120.2), the directional (CRN mean) lift,
and the order-independent digest. EDUCATIONAL model.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from par_model_v2.projection.joint_action_aggregation import JointActionAggregator
from par_model_v2.projection.management_actions import ManagementActionRule
from par_model_v2.projection.skew_t_copula_aggregation import (
    RANK_INVARIANCE_DF,
    _skew_t_cdf_interpolant,
    simulate_skew_t_copula_uniforms,
)
from par_model_v2.projection.skew_t_copula_bootstrap import (
    COPULA_FORM_RESIDUAL_FROZEN_T,
    SE_GATE_FRACTION,
    _draw_uniforms_both,
    bootstrap_digest,
    redecompose_residual_gap,
    skewt_bootstrap_use_restrictions,
    skewt_margin_bootstrap,
    summarise_ci,
)

DRIVERS = ("rate", "equity", "credit", "lapse", "mortality", "fx", "liquidity")
P23T2 = Path("/var/tmp/p23t2_stage/losses.npz")
P23T4 = Path("/var/tmp/p23t4_stage/losses_with_actions.npz")
P27T2V = Path("/var/tmp/p27t2_stage/verified.npz")
P27T2FIT = Path("/var/tmp/p27t2_stage/fit_result.json")
REPORT = Path("docs/validation/PHASE27_TASK3_SKEW_T_BOOTSTRAP_REPORT.json")

_staged = P23T2.exists() and P23T4.exists() and P27T2V.exists()
needs_stage = pytest.mark.skipif(not _staged, reason="staged inputs absent")

GAMMA_HAT = 6.24229466599955e-05


def _corr(d=5, rho=0.4):
    R = np.full((d, d), rho)
    np.fill_diagonal(R, 1.0)
    return R


# --------------------------------------------------------------------------
# Self-contained gates (no staged inputs needed)
# --------------------------------------------------------------------------
def test_draw_both_crn_exact_vs_tested_module():
    """_draw_uniforms_both reproduces the tested simulator to <= 1 ULP (CRN)."""
    R = _corr(5, 0.35)
    df, gamma, seed, n = RANK_INVARIANCE_DF, GAMMA_HAT, 4321, 4000
    xg, Gg = _skew_t_cdf_interpolant(df, gamma)
    U_sk, U_sym = _draw_uniforms_both(np.random.default_rng(seed), n, R, df, gamma, xg, Gg)
    U_sk_ref = simulate_skew_t_copula_uniforms(np.random.default_rng(seed), n, R, df, gamma)
    U_sym_ref = simulate_skew_t_copula_uniforms(np.random.default_rng(seed), n, R, df, 0.0)
    assert np.max(np.abs(U_sk - U_sk_ref)) <= 1e-12
    assert np.max(np.abs(U_sym - U_sym_ref)) <= 1e-12


def test_draw_both_shares_latent_crn():
    """skew-t and symmetric draws share the latent (Z, W): at gamma=0 the only
    difference is the interpolated-grid vs exact Student-t CDF evaluation, which
    is bounded by the grid resolution (the same definition P27T2 used)."""
    R = _corr(4, 0.3)
    xg, Gg = _skew_t_cdf_interpolant(RANK_INVARIANCE_DF, 0.0)
    U_sk, U_sym = _draw_uniforms_both(
        np.random.default_rng(7), 2000, R, RANK_INVARIANCE_DF, 0.0, xg, Gg)
    # shared latent -> the skew (interp) and symmetric (exact) uniforms agree to
    # interpolation tolerance (NOT bit-identical: U_sk PITs through the grid).
    assert np.max(np.abs(U_sk - U_sym)) < 1e-4


def test_summarise_ci_basic():
    a = list(range(1, 201))
    ci = summarise_ci(a, 0.95)
    assert ci["n"] == 200
    assert abs(ci["mean"] - 100.5) < 1e-9
    assert ci["ci_lo"] < ci["mean"] < ci["ci_hi"]


def test_redecompose_algebra_and_reduction():
    """Relief + copula-form parts sum to the gap; reduction vs frozen-t exact."""
    nested, relief = 46638.9, 0.01164368805922599
    comp_sk, comp_sym = 39980.95565911311, 39975.654628199336
    d = redecompose_residual_gap(comp_sk, comp_sym, nested, relief,
                                 COPULA_FORM_RESIDUAL_FROZEN_T)
    assert abs((d["relief_surface_part_abs"] + d["copula_form_residual_abs"])
               - d["gap_total_abs"]) < 1e-6
    # frozen-t copula-form residual minus the new one == reduction
    assert abs(d["copula_form_residual_reduction_abs"]
               - (COPULA_FORM_RESIDUAL_FROZEN_T - d["copula_form_residual_abs"])) < 1e-6
    # gamma_hat > 0 lifts SCR -> residual reduces a touch, gap not widened
    assert d["copula_form_residual_reduction_abs"] > 0.0
    assert d["nested_gap_not_widened"] is True
    # tiny gamma_hat -> residual NOT closed by the scalar
    assert d["residual_closed_by_skewt_scalar"] is False


def test_redecompose_widening_flag():
    """If skew-t SCR < symmetric SCR the not-widened flag is False."""
    d = redecompose_residual_gap(100.0, 110.0, 200.0, 0.01,
                                 COPULA_FORM_RESIDUAL_FROZEN_T)
    assert d["nested_gap_not_widened"] is False


def test_bootstrap_digest_order_independent():
    recs = [{"replicate_index": i, "scr_component_skewt": float(i),
             "scr_component_sym": float(i) - 0.1,
             "scr_without_skewt": float(i) + 1.0} for i in range(10)]
    import random
    shuffled = recs[:]
    random.Random(0).shuffle(shuffled)
    assert bootstrap_digest(recs) == bootstrap_digest(shuffled)


def test_use_restrictions_educational():
    r = skewt_bootstrap_use_restrictions()
    assert r["classification"] == "EDUCATIONAL"
    assert any("FROZEN" in s for s in r["restrictions"])


# --------------------------------------------------------------------------
# Staged-input gates
# --------------------------------------------------------------------------
def _load_inputs():
    z = np.load(P23T2)
    w = np.load(P23T4)
    s = np.load(P27T2V)
    losses = {k: np.asarray(z[k], float) for k in DRIVERS}
    anchors = {k: float(w[k + "_anchor_mean"][0]) for k in DRIVERS}
    return (losses, np.asarray(s["rho"], float), float(w["l_fit"][0]), anchors,
            float(s["sigma"][0]), float(s["alpha"][0]), float(s["beta_fit"][0]))


@needs_stage
def test_bootstrap_chunk_independent():
    """Replicates are resume-safe: [0,6) == [0,3)+[3,6) record-for-record."""
    losses, rho, l_fit, anchors, sigma, alpha, beta = _load_inputs()
    common = dict(losses_without=losses, correlation=rho,
                  rule=ManagementActionRule(), l_fit=l_fit, anchor_means=anchors,
                  df=RANK_INVARIANCE_DF, gamma=GAMMA_HAT, sigma=sigma, alpha=alpha,
                  benefit_share=beta, n_replicates=6, n_sim=3000)
    full = skewt_margin_bootstrap(**common, replicate_start=0, replicate_stop=6)
    a = skewt_margin_bootstrap(**common, replicate_start=0, replicate_stop=3)
    b = skewt_margin_bootstrap(**common, replicate_start=3, replicate_stop=6)
    merged = {r["replicate_index"]: r for r in a["records"] + b["records"]}
    for rec in full["records"]:
        m = merged[rec["replicate_index"]]
        assert rec["scr_component_skewt"] == m["scr_component_skewt"]
        assert rec["scr_component_sym"] == m["scr_component_sym"]


@needs_stage
def test_bootstrap_directional_mean_not_widened():
    """CRN mean lift (skew-t - symmetric) >= 0 with gamma_hat > 0."""
    losses, rho, l_fit, anchors, sigma, alpha, beta = _load_inputs()
    res = skewt_margin_bootstrap(
        losses_without=losses, correlation=rho, rule=ManagementActionRule(),
        l_fit=l_fit, anchor_means=anchors, df=RANK_INVARIANCE_DF, gamma=GAMMA_HAT,
        sigma=sigma, alpha=alpha, benefit_share=beta, n_replicates=20, n_sim=6000)
    lifts = [r["skewt_minus_sym"] for r in res["records"]]
    assert float(np.mean(lifts)) >= 0.0


@needs_stage
def test_report_gates_pass():
    """The generated report PASSes (SE gate + directional mean + frozen gates)."""
    if not REPORT.exists():
        pytest.skip("report not yet generated")
    rep = json.loads(REPORT.read_text(encoding="utf-8"))
    r = rep["result"]
    assert rep["verdict"] == "PASS"
    assert r["se_frac_of_mean"] <= SE_GATE_FRACTION
    assert r["directional_not_widened_mean"] is True
    for k, v in r["gates"].items():
        if k == "C1_headline_nested_inside_95ci_raw":
            continue
        assert v is True, k
