"""Phase 28 Task 3 -- grouped t-copula margin bootstrap unit tests.

Verifies the pre-registered Task 3 gates from the Phase 28 Task 1 design note:
the common-random-number grouped-t-vs-single-t contrast (shared Gaussian
latent), the SE gate, the residual-gap RE-decomposition arithmetic + the
change vs the skew-t-reconfirmed 6,114.9 (and frozen-t 6,120.2) baselines, the
chunk-independent / idempotent digest, and the report verdict. EDUCATIONAL model.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from par_model_v2.projection.grouped_t_copula_aggregation import (
    BLOCKS,
    FROZEN_T_COPULA_FORM_RESIDUAL_ABS,
    NESTED_PATHWISE_SCR_REFERENCE,
    RANK_INVARIANCE_DF,
    SKEWT_RECONFIRMED_COPULA_FORM_RESIDUAL_ABS,
    simulate_grouped_t_copula_uniforms,
)
from par_model_v2.projection.grouped_t_copula_bootstrap import (
    GROUPED_T_BOOTSTRAP_MASTER_SEED,
    RELIEF_SURFACE_REL_ERR_SOURCE,
    SE_GATE_FRACTION,
    _draw_uniforms_both,
    bootstrap_digest,
    grouped_t_bootstrap_use_restrictions,
    grouped_t_margin_bootstrap,
    redecompose_residual_gap,
    summarise_ci,
)
from par_model_v2.projection.management_actions import ManagementActionRule
from par_model_v2.projection.t_copula_tail_matched_aggregation import (
    simulate_t_copula_uniforms,
)

DRIVERS = ("rate", "equity", "credit", "lapse", "mortality", "fx", "liquidity")
P23T2 = Path("/var/tmp/p23t2_stage/losses.npz")
P23T4 = Path("/var/tmp/p23t4_stage/losses_with_actions.npz")
P26T2V = Path("/var/tmp/p26t2_stage/verified_inputs.npz")
P28T2_FIT = Path("/var/tmp/p28t2_build/fit_result.json")
REPORT = Path("docs/validation/PHASE28_TASK3_GROUPED_T_BOOTSTRAP_REPORT.json")

_staged = (P23T2.exists() and P23T4.exists() and P26T2V.exists()
           and P28T2_FIT.exists())
needs_stage = pytest.mark.skipif(not _staged, reason="staged inputs absent")


def _corr7(rho=0.4):
    R = np.full((7, 7), rho)
    np.fill_diagonal(R, 1.0)
    return R


# --------------------------------------------------------------------------
# Self-contained gates (no staged inputs needed)
# --------------------------------------------------------------------------
def test_crn_single_variant_recovers_single_df_t_uniforms():
    """The single-df t variant of _draw_uniforms_both (homogeneous boundary,
    shared mixing) reproduces the frozen single-df t-copula uniforms EXACTLY,
    and shares the Gaussian latent with the grouped-t variant (CRN)."""
    R = _corr7()
    df = RANK_INVARIANCE_DF
    U_grp, U_sng = _draw_uniforms_both(
        cop_seed=777, n_sim=30000, correlation=R,
        block_dfs=[37.866, 8.506], blocks=BLOCKS, homogeneous_df=df)
    # single variant == direct single-df t draw at the same seed (bit-identical)
    U_ref = simulate_t_copula_uniforms(np.random.default_rng(777), 30000, R, df)
    assert np.max(np.abs(U_sng - U_ref)) == 0.0
    # grouped variant differs (the per-block mixing IS the lever)
    assert np.max(np.abs(U_grp - U_sng)) > 0.0


def test_summarise_ci_basic():
    a = list(range(1, 201))
    ci = summarise_ci(a, 0.95)
    assert ci["n"] == 200
    assert abs(ci["mean"] - 100.5) < 1e-9
    assert ci["ci_lo"] < ci["mean"] < ci["ci_hi"]
    assert ci["min"] == 1.0 and ci["max"] == 200.0


def test_redecompose_residual_arithmetic_and_widening():
    """The re-decomposition splits the gap into relief + copula-form parts and
    quantifies the change vs the skew-t-reconfirmed baseline; a grouped-t
    component BELOW the frozen-t WIDENS the copula-form residual."""
    nested = NESTED_PATHWISE_SCR_REFERENCE
    relief_rel = RELIEF_SURFACE_REL_ERR_SOURCE
    comp_g = 35604.39894619743
    comp_s = 39975.654628199336
    d = redecompose_residual_gap(comp_g, comp_s, nested, relief_rel)
    # exact identities
    assert abs(d["gap_total_abs"] - (nested - comp_g)) < 1e-6
    assert abs(d["relief_surface_part_abs"] - relief_rel * nested) < 1e-6
    assert abs(d["copula_form_residual_abs"]
               - (d["gap_total_abs"] - d["relief_surface_part_abs"])) < 1e-6
    # change vs the two baselines
    assert abs(d["copula_form_residual_change_vs_skewt_abs"]
               - (d["copula_form_residual_abs"]
                  - SKEWT_RECONFIRMED_COPULA_FORM_RESIDUAL_ABS)) < 1e-6
    assert abs(d["copula_form_residual_change_vs_frozen_t_abs"]
               - (d["copula_form_residual_abs"]
                  - FROZEN_T_COPULA_FORM_RESIDUAL_ABS)) < 1e-6
    # the grouped-t dilutes (comp_g < comp_s) -> residual WIDENS vs skew-t
    assert d["grouped_minus_single_lift"] < 0.0
    assert d["copula_form_residual_widened_vs_skewt"] is True
    assert d["residual_closed_by_grouped_t"] is False


def test_bootstrap_digest_order_independent():
    recs = [{"replicate_index": i, "scr_component_grouped_t": 100.0 + i,
             "scr_component_single_t": 200.0 + i,
             "scr_without_grouped_t": 300.0 + i} for i in range(10)]
    d1 = bootstrap_digest(recs)
    d2 = bootstrap_digest(list(reversed(recs)))
    assert d1 == d2 and len(d1) == 12


def test_use_restrictions_educational():
    r = grouped_t_bootstrap_use_restrictions()
    assert r["classification"] == "EDUCATIONAL"
    assert len(r["restrictions"]) >= 4


# --------------------------------------------------------------------------
# Staged-input gates (real frozen basis)
# --------------------------------------------------------------------------
def _inputs():
    z = np.load(P23T2); w = np.load(P23T4); s = np.load(P26T2V)
    losses = {k: np.asarray(z[k], float) for k in DRIVERS}
    anchors = {k: float(w[k + "_anchor_mean"][0]) for k in DRIVERS}
    block_dfs = [float(g) for g in
                 json.loads(P28T2_FIT.read_text(encoding="utf-8"))["block_dfs_hat"]]
    return (losses, anchors, np.asarray(s["rho"], float), float(w["l_fit"][0]),
            float(s["sigma"][0]), float(s["alpha"][0]), float(s["beta_fit"][0]),
            block_dfs)


@needs_stage
def test_small_bootstrap_deterministic_and_dilutes():
    """A small chunked bootstrap is deterministic (chunk-independent) and the
    grouped-t dilutes vs the single-df t on common random numbers."""
    losses, anchors, rho, l_fit, sigma, alpha, beta, block_dfs = _inputs()
    kw = dict(losses_without=losses, correlation=rho, rule=ManagementActionRule(),
              l_fit=l_fit, anchor_means=anchors, block_dfs=block_dfs,
              homogeneous_df=RANK_INVARIANCE_DF, sigma=sigma, alpha=alpha,
              benefit_share=beta, n_replicates=8, n_sim=8000,
              master_seed=GROUPED_T_BOOTSTRAP_MASTER_SEED)
    a = grouped_t_margin_bootstrap(replicate_start=0, replicate_stop=4, **kw)
    b = grouped_t_margin_bootstrap(replicate_start=4, replicate_stop=8, **kw)
    full = grouped_t_margin_bootstrap(replicate_start=0, replicate_stop=8, **kw)
    recs = a["records"] + b["records"]
    assert bootstrap_digest(recs) == bootstrap_digest(full["records"])
    # CRN dilution: grouped-t component below single-df t in every replicate
    for r in full["records"]:
        assert r["grouped_minus_single"] < 0.0


@needs_stage
def test_report_verdict_pass_se_gate_and_redecomposition():
    rep = json.loads(REPORT.read_text(encoding="utf-8"))
    r = rep["result"]
    assert rep["verdict"] == "PASS"
    assert r["se_gate_pass"] is True
    assert r["grouped_t_component_scr_ci"]["se_frac_of_mean"] <= SE_GATE_FRACTION
    # nested OUTSIDE the grouped-t CI -> headline re-decomposition branch
    assert r["headline_nested_inside_95ci"] is False
    d = r["residual_gap_redecomposition_point"]
    # the disclosed widening vs the skew-t-reconfirmed baseline
    assert d["copula_form_residual_widened_vs_skewt"] is True
    assert d["copula_form_residual_change_vs_skewt_abs"] > 0.0
    # directional disclosed (two-sided lever) -> DOWN this cycle
    assert r["directional_disclosed_direction"] == "down"
    # all non-raw gates PASS
    assert all(v for k, v in r["gates"].items()
               if k != "C1_headline_nested_inside_95ci_raw")


@needs_stage
def test_report_archive_crosscheck_points_bit_identical():
    rep = json.loads(REPORT.read_text(encoding="utf-8"))
    r = rep["result"]
    assert r["task2_frozen_t_component_point"] == 39975.654628199336
    assert r["task2_grouped_t_component_point"] == 35604.39894619743
