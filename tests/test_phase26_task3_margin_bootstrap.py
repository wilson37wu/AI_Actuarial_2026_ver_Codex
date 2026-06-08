"""Phase 26 Task 3 - frozen-copula margin bootstrap unit tests."""
from __future__ import annotations

import numpy as np
import pytest

from par_model_v2.projection.management_actions import ManagementActionRule
from par_model_v2.projection.pathwise_composition_bootstrap import (
    SE_GATE_FRACTION,
    bootstrap_digest,
    composition_bootstrap_use_restrictions,
    composition_margin_bootstrap,
    decompose_residual_gap,
    summarise_ci,
)

DRIVERS = ("rate", "equity", "credit", "lapse", "mortality", "fx", "liquidity")


def _synthetic_inputs(seed=7, n_obs=120):
    rng = np.random.default_rng(seed)
    losses = {k: np.abs(rng.normal(1000.0, 300.0, size=n_obs)) for k in DRIVERS}
    anchors = {k: float(np.mean(losses[k])) for k in DRIVERS}
    rho = np.eye(7)
    l_fit = 100000.0
    return losses, rho, l_fit, anchors


def _run(start, stop, n_replicates=12, n_sim=1500, also_gaussian=True):
    losses, rho, l_fit, anchors = _synthetic_inputs()
    return composition_margin_bootstrap(
        losses_without=losses, correlation=rho, rule=ManagementActionRule(),
        l_fit=l_fit, anchor_means=anchors, df=2.9451, sigma=0.225,
        alpha=0.75, benefit_share=0.84, n_replicates=n_replicates,
        n_sim=n_sim, master_seed=20260608, confidence=0.995,
        replicate_start=start, replicate_stop=stop, also_gaussian=also_gaussian)


def test_records_have_required_keys():
    recs = _run(0, 3)["records"]
    assert len(recs) == 3
    for r in recs:
        for k in ("replicate_index", "scr_component_t", "scr_level_t",
                  "scr_without_t", "scr_component_g"):
            assert k in r
        # actions reduce the liability tail -> with-action SCR <= without
        assert r["scr_component_t"] <= r["scr_without_t"] + 1e-6
        assert r["scr_level_t"] <= r["scr_without_t"] + 1e-6


def test_chunk_independence_resume_safe():
    """[0,4)+[4,8) reproduces [0,8) bit-identically (SeedSequence spawn)."""
    a = _run(0, 4, n_replicates=8)["records"]
    b = _run(4, 8, n_replicates=8)["records"]
    full = _run(0, 8, n_replicates=8)["records"]
    merged = {r["replicate_index"]: r for r in (a + b)}
    assert sorted(merged) == list(range(8))
    for r in full:
        m = merged[r["replicate_index"]]
        assert r["scr_component_t"] == m["scr_component_t"]
        assert r["scr_component_g"] == m["scr_component_g"]


def test_idempotent_same_seed():
    a = _run(0, 5, n_replicates=10)["records"]
    b = _run(0, 5, n_replicates=10)["records"]
    for x, y in zip(a, b):
        assert x["scr_component_t"] == y["scr_component_t"]


def test_frozen_inputs_not_mutated():
    losses, rho, l_fit, anchors = _synthetic_inputs()
    rho0 = rho.copy()
    losses0 = {k: v.copy() for k, v in losses.items()}
    composition_margin_bootstrap(
        losses_without=losses, correlation=rho, rule=ManagementActionRule(),
        l_fit=l_fit, anchor_means=anchors, df=2.9451, sigma=0.225, alpha=0.75,
        benefit_share=0.84, n_replicates=4, n_sim=1200, replicate_stop=2)
    assert np.array_equal(rho, rho0)
    for k in DRIVERS:
        assert np.array_equal(losses[k], losses0[k])


def test_summarise_ci_structure_and_bounds():
    s = summarise_ci([10.0, 12.0, 11.0, 13.0, 9.0, 14.0], 0.95)
    assert s["ci_lo"] <= s["mean"] <= s["ci_hi"]
    assert s["se"] > 0.0
    assert abs(s["se_frac_of_mean"] - s["se"] / s["mean"]) < 1e-12
    assert s["min"] <= s["ci_lo"] and s["ci_hi"] <= s["max"]


def test_decompose_gap_identity_and_dominance():
    d = decompose_residual_gap(
        scr_component_t=39975.7, scr_component_g=35210.1,
        nested_scr=46638.9, relief_surface_rel_err=0.01164368805922599)
    # additive identity: relief-surface + copula-form = total gap
    assert abs(d["relief_surface_part_abs"] + d["copula_form_residual_abs"]
               - d["gap_total_abs"]) < 1e-6
    assert abs(d["relief_surface_share_of_gap"]
               + d["copula_form_share_of_gap"] - 1.0) < 1e-9
    # the real-data finding: copula-form dominates the residual
    assert d["copula_form_dominant"] is True
    assert d["copula_form_residual_abs"] > d["relief_surface_part_abs"]
    assert d["gap_total_abs"] > 0.0


def test_decompose_residual_exceeds_t_g_sensitivity():
    d = decompose_residual_gap(39975.7, 35391.5, 46638.9, 0.01164368805922599)
    # nested gap (~6663) exceeds the entire gaussian->t move (~4584)
    assert d["residual_exceeds_t_g_sensitivity"] is True


def test_bootstrap_digest_order_independent():
    recs = _run(0, 6)["records"]
    import random
    shuffled = list(recs)
    random.Random(1).shuffle(shuffled)
    assert bootstrap_digest(recs) == bootstrap_digest(shuffled)


def test_se_gate_fraction_constant():
    assert SE_GATE_FRACTION == 0.05


def test_use_restrictions_educational():
    u = composition_bootstrap_use_restrictions()
    assert u["classification"] == "EDUCATIONAL"
    assert len(u["restrictions"]) >= 3
