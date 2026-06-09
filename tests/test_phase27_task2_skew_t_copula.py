"""Phase 27 Task 2 -- GH skew-t copula re-aggregation unit tests.

Verifies the pre-registered Task 2 gates from the Phase 27 Task 1 design
note: gamma = 0 EXACT recovery of the frozen symmetric t-copula, frozen
(df, Sigma) rank invariance, uniform margins for gamma > 0, the
upper-tail-asymmetry mechanism, the leakage-free gamma fit, and the
component re-aggregation read-out. EDUCATIONAL model.
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
from par_model_v2.projection.skew_t_copula_aggregation import (
    FROZEN_T_COMPONENT_SCR_REFERENCE,
    GAMMA_ZERO_RECOVERY_TOL,
    RANK_INVARIANCE_DF,
    TAIL_LEVEL_P,
    _avg_pairwise_upper_codependence,
    composition_skewt_readout,
    fit_gamma_to_upper_tail,
    realised_upper_tail_codependence,
    simulate_skew_t_copula_uniforms,
    skew_t_marginal_cdf,
    skew_t_copula_use_restrictions,
)
from par_model_v2.projection.t_copula_tail_matched_aggregation import (
    simulate_t_copula_uniforms,
)
from scipy import stats

DRIVERS = ("rate", "equity", "credit", "lapse", "mortality", "fx", "liquidity")
P23T2 = Path("/var/tmp/p23t2_stage/losses.npz")
P23T4 = Path("/var/tmp/p23t4_stage/losses_with_actions.npz")
P26T2V = Path("/var/tmp/p26t2_stage/verified_inputs.npz")
REPORT = Path("docs/validation/PHASE27_TASK2_SKEW_T_COPULA_REPORT.json")

_staged = P23T2.exists() and P23T4.exists() and P26T2V.exists()
needs_stage = pytest.mark.skipif(not _staged, reason="staged inputs absent")


def _corr(d=5, rho=0.4):
    R = np.full((d, d), rho)
    np.fill_diagonal(R, 1.0)
    return R


# --------------------------------------------------------------------------
# Self-contained gates (no staged inputs needed)
# --------------------------------------------------------------------------
def test_gamma0_uniforms_bit_identical_to_symmetric_t():
    """G1 core: gamma=0 reproduces the symmetric t-copula uniforms exactly."""
    R = _corr()
    df = 2.9451
    r1 = np.random.default_rng(123)
    U_sym = simulate_t_copula_uniforms(r1, 40000, R, df)
    r2 = np.random.default_rng(123)
    U_sk = simulate_skew_t_copula_uniforms(r2, 40000, R, df, 0.0)
    assert np.max(np.abs(U_sk - U_sym)) == 0.0


def test_skewt_marginal_cdf_gamma0_is_student_t():
    df = 2.9451
    x = np.linspace(-6, 8, 41)
    assert np.allclose(skew_t_marginal_cdf(x, df, 0.0), stats.t.cdf(x, df))


def test_skewt_marginal_cdf_quadrature_limit_matches_student_t():
    """Quadrature path at tiny gamma is close to the exact Student-t."""
    df = 2.9451
    x = np.linspace(-5, 7, 25)
    quad = skew_t_marginal_cdf(x, df, 1e-9)
    assert np.max(np.abs(quad - stats.t.cdf(x, df))) < 1e-4


@pytest.mark.parametrize("gamma", [0.3, 0.7, 1.5])
def test_margins_uniform_for_positive_gamma(gamma):
    """Margins stay uniform for gamma>0 (frozen empirical margins untouched)."""
    R = _corr(d=4, rho=0.3)
    U = simulate_skew_t_copula_uniforms(np.random.default_rng(9), 150000, R,
                                        2.9451, gamma)
    means = U.mean(axis=0)
    q90 = np.quantile(U, 0.90, axis=0)
    assert np.all(np.abs(means - 0.5) < 0.01)
    assert np.all(np.abs(q90 - 0.90) < 0.01)


def test_upper_tail_dependence_rises_with_gamma():
    """Mechanism: positive gamma lifts upper-tail dependence and asymmetry."""
    R = _corr(d=5, rho=0.4)
    df = 2.9451
    lam = {}
    for g in (0.0, 0.5, 1.0):
        U = simulate_skew_t_copula_uniforms(np.random.default_rng(5), 200000,
                                            R, df, g)
        lam[g] = _avg_pairwise_upper_codependence(U, 0.95)
    assert lam[0.5] > lam[0.0] and lam[1.0] > lam[0.5]


def test_simulator_rejects_negative_gamma():
    with pytest.raises(ValueError):
        simulate_skew_t_copula_uniforms(np.random.default_rng(0), 100,
                                        _corr(), 3.0, -0.1)


def test_use_restrictions_educational():
    r = skew_t_copula_use_restrictions()
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
def test_gate1_gamma0_exact_recovery_of_frozen_t_component():
    agg, s, _ = _aggregator()
    sigma, alpha, beta = (float(s["sigma"][0]), float(s["alpha"][0]),
                          float(s["beta_fit"][0]))
    ro_t = composition_joint_readout(agg, 200000, 20260607, RANK_INVARIANCE_DF,
                                     sigma, alpha, beta, 0.995)
    ro_sk0 = composition_skewt_readout(agg, 200000, 20260607,
                                       RANK_INVARIANCE_DF, 0.0, sigma, alpha,
                                       beta, 0.995)
    assert ro_t["scr_component"] == FROZEN_T_COMPONENT_SCR_REFERENCE
    assert abs(ro_sk0["scr_component"] - ro_t["scr_component"]) <= \
        GAMMA_ZERO_RECOVERY_TOL
    # G4 margins-unchanged: without-actions basis bit-identical
    assert ro_sk0["scr_without"] == ro_t["scr_without"]


@needs_stage
def test_gate6_gamma_fit_leakage_free_pins_low():
    """Realised standalone upper co-exceedance < symmetric-t => gamma_hat ~ 0."""
    agg, s, z = _aggregator()
    losses = {k: np.asarray(z[k], float) for k in DRIVERS}
    fit = fit_gamma_to_upper_tail(losses, DRIVERS,
                                  np.asarray(s["rho"], float),
                                  RANK_INVARIANCE_DF, p=TAIL_LEVEL_P,
                                  n_sim=80000, seed=20260608)
    assert fit["fit_converged"]
    assert fit["target_realised_codependence"] < \
        fit["model_codependence_at_gamma0"]
    assert fit["gamma_hat"] < 1e-2


@needs_stage
def test_gate5_sign_gate_skewt_ge_frozen_t():
    agg, s, z = _aggregator()
    sigma, alpha, beta = (float(s["sigma"][0]), float(s["alpha"][0]),
                          float(s["beta_fit"][0]))
    # at an illustrative positive gamma the component SCR exceeds the frozen-t
    ro = composition_skewt_readout(agg, 150000, 20260607, RANK_INVARIANCE_DF,
                                   0.5, sigma, alpha, beta, 0.995)
    assert ro["scr_component"] >= FROZEN_T_COMPONENT_SCR_REFERENCE - 1e-9
    assert ro["radial_asymmetry"] > 0.0


@needs_stage
def test_report_verdict_pass_and_all_gates():
    rep = json.loads(REPORT.read_text(encoding="utf-8"))
    assert rep["verdict"] == "PASS"
    assert all(rep["result"]["gates"].values())
    assert rep["df_frozen"] == RANK_INVARIANCE_DF
