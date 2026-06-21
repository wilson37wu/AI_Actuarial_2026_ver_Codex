"""Phase 29 Task 3 - vine margin bootstrap unit tests (small-scale)."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from par_model_v2.projection.management_actions import ManagementActionRule
from par_model_v2.projection.vine_copula_pair_aggregation import (
    VinePairFit,
    fit_vine_pair_families,
    simulate_vine_pair_copula_uniforms,
    vine_pair_fit_from_dict,
)
from par_model_v2.projection.t_copula_tail_matched_aggregation import (
    simulate_t_copula_uniforms,
)
from par_model_v2.projection.vine_copula_bootstrap import (
    SE_GATE_FRACTION,
    VINE_BOOTSTRAP_MASTER_SEED,
    VINE_BOOTSTRAP_N_SIM,
    VINE_BOOTSTRAP_REPLICATES,
    VINE_CANDIDATE_COMPONENT_SCR_POINT,
    _draw_uniforms_both,
    redecompose_vine_residual_gap,
    vine_bootstrap_digest,
    vine_bootstrap_use_restrictions,
    vine_fit_digest,
    vine_margin_bootstrap,
)
from par_model_v2.projection.vine_copula_upgrade import (
    DRIVER_NAMES,
    FROZEN_T_COMPONENT_SCR_REFERENCE,
    GROUPED_T_COPULA_FORM_RESIDUAL_ABS,
    NESTED_PATHWISE_SCR_REFERENCE,
    RANK_INVARIANCE_DF,
    SKEWT_RECONFIRMED_COPULA_FORM_RESIDUAL_ABS,
)

DRIVERS = tuple(DRIVER_NAMES)
N_SIM = 1_500

P23T2 = Path("/var/tmp/p23t2_stage/losses.npz")
P23T4 = Path("/var/tmp/p23t4_stage/losses_with_actions.npz")
P29T2V = Path("/var/tmp/p29t2_stage/verified_inputs.npz")
P29T2_FIT = Path("/var/tmp/p29t2_stage/vine_pair_fit.json")

_staged = (P23T2.exists() and P23T4.exists() and P29T2V.exists()
           and P29T2_FIT.exists())
needs_stage = pytest.mark.skipif(not _staged, reason="staged inputs absent")


def _corr7(rho=0.4):
    R = np.full((7, 7), rho)
    np.fill_diagonal(R, 1.0)
    return R


@pytest.fixture(scope="module")
def staged():
    z = np.load(P23T2)
    w = np.load(P23T4)
    s = np.load(P29T2V)
    losses = {k: np.asarray(z[k], dtype=float) for k in DRIVERS}
    anchors = {k: float(w[k + "_anchor_mean"][0]) for k in DRIVERS}
    fit = vine_pair_fit_from_dict(
        json.loads(P29T2_FIT.read_text(encoding="utf-8")))
    return dict(losses=losses, rho=np.asarray(s["rho"], float),
                anchors=anchors, l_fit=float(w["l_fit"][0]),
                sigma=float(s["sigma"][0]), alpha=float(s["alpha"][0]),
                beta=float(s["beta_fit"][0]), fit=fit)


def test_frozen_boundary_is_candidate_base():
    rng = np.random.default_rng(20260611)
    base = rng.multivariate_normal(np.zeros(7), _corr7(), size=96)
    losses = {k: np.exp(0.4 * base[:, i]) * (40.0 + 6.0 * i)
              for i, k in enumerate(DRIVERS)}
    fit = fit_vine_pair_families(losses, DRIVERS, fit_fraction=0.7,
                                 seed=20260609, p=0.90)
    R = _corr7()
    U_cand, U_frz = _draw_uniforms_both(12345, N_SIM, R, fit)
    rng = np.random.default_rng(12345)
    U_ref = simulate_t_copula_uniforms(rng, N_SIM, R, RANK_INVARIANCE_DF)
    assert np.array_equal(U_frz, U_ref)
    assert U_cand.shape == U_frz.shape
    # candidate preserves marginal ranks (re-ranked to uniforms)
    for j in range(U_cand.shape[1]):
        assert abs(float(np.mean(U_cand[:, j])) - 0.5) < 0.05


@needs_stage
def test_chunk_independence_digest(staged):
    kw = dict(losses_without=staged["losses"], correlation=staged["rho"],
              rule=ManagementActionRule(), l_fit=staged["l_fit"],
              anchor_means=staged["anchors"], fit=staged["fit"],
              sigma=staged["sigma"], alpha=staged["alpha"],
              benefit_share=staged["beta"],
              n_replicates=6, n_sim=N_SIM, master_seed=777)
    full = vine_margin_bootstrap(replicate_start=0, replicate_stop=6, **kw)
    a = vine_margin_bootstrap(replicate_start=0, replicate_stop=3, **kw)
    b = vine_margin_bootstrap(replicate_start=3, replicate_stop=6, **kw)
    d_full = vine_bootstrap_digest(full["records"])
    d_join = vine_bootstrap_digest(a["records"] + b["records"])
    assert d_full == d_join
    assert len(full["records"]) == 6
    # idempotent re-run
    again = vine_margin_bootstrap(replicate_start=0, replicate_stop=6, **kw)
    assert vine_bootstrap_digest(again["records"]) == d_full


@needs_stage
def test_records_fields_and_crn_lift(staged):
    res = vine_margin_bootstrap(
        losses_without=staged["losses"], correlation=staged["rho"],
        rule=ManagementActionRule(), l_fit=staged["l_fit"],
        anchor_means=staged["anchors"], fit=staged["fit"],
        sigma=staged["sigma"], alpha=staged["alpha"],
        benefit_share=staged["beta"], n_replicates=2, n_sim=N_SIM,
        master_seed=99, replicate_start=0, replicate_stop=2)
    for rec in res["records"]:
        assert rec["scr_component_vine"] > 0.0
        assert rec["scr_component_frozen_t"] > 0.0
        assert rec["vine_minus_frozen"] == pytest.approx(
            rec["scr_component_vine"] - rec["scr_component_frozen_t"])
    assert res["df_frozen"] == RANK_INVARIANCE_DF
    assert res["fit_structure"] == staged["fit"].structure


def test_redecompose_identities():
    d = redecompose_vine_residual_gap(
        scr_component_vine=VINE_CANDIDATE_COMPONENT_SCR_POINT,
        scr_component_frozen_t=FROZEN_T_COMPONENT_SCR_REFERENCE)
    nested = NESTED_PATHWISE_SCR_REFERENCE
    assert d["gap_total_abs"] == pytest.approx(
        nested - VINE_CANDIDATE_COMPONENT_SCR_POINT)
    assert d["relief_surface_part_abs"] + d["copula_form_residual_abs"] == \
        pytest.approx(d["gap_total_abs"])
    assert d["copula_form_residual_change_vs_grouped_t_abs"] == pytest.approx(
        d["copula_form_residual_abs"] - GROUPED_T_COPULA_FORM_RESIDUAL_ABS)
    assert d["copula_form_residual_change_vs_skewt_abs"] == pytest.approx(
        d["copula_form_residual_abs"] - SKEWT_RECONFIRMED_COPULA_FORM_RESIDUAL_ABS)
    # archived point basis: vine NARROWS the residual vs BOTH baselines
    assert d["copula_form_residual_narrowed_vs_skewt"] is True
    assert d["copula_form_residual_change_vs_grouped_t_abs"] < 0.0
    assert d["vine_minus_frozen_lift"] > 0.0


def test_constants_and_restrictions():
    assert VINE_BOOTSTRAP_REPLICATES >= 200
    assert VINE_BOOTSTRAP_N_SIM >= 20_000
    assert 0.0 < SE_GATE_FRACTION <= 0.05
    u = vine_bootstrap_use_restrictions()
    assert u["classification"] == "EDUCATIONAL"
    assert len(u["restrictions"]) >= 4
    assert isinstance(VINE_BOOTSTRAP_MASTER_SEED, int)


@needs_stage
def test_fit_digest_stable(staged):
    d1 = vine_fit_digest(staged["fit"].to_dict())
    d2 = vine_fit_digest(staged["fit"].to_dict())
    assert d1 == d2 and len(d1) == 12
