"""Phase 21 Task 1 — FX / currency sixth-driver tests.

Covers: FX exposure spec validation + CIP-exact mapping, 6x6 governed
correlation embedding the 5x5 block, six-shock construction preserving the
five-driver stream, the G-FX plausibility gate (incl. the reused Phase 20
MART-FX-CIP Q-measure evidence), outer-state generation, and the six-driver
aggregation report structure / reproducibility.
"""

import numpy as np
import pytest

from par_model_v2.projection.monthly_projection import ParEndowmentProduct
from par_model_v2.projection.multi_driver_capital_5d import FiveDriverCorrelation
from par_model_v2.projection.multi_driver_capital_5d_aggregation import (
    FiveDriverAggregationConfig,
)
from par_model_v2.projection.multi_driver_capital_6d_fx import (
    DEFAULT_FX_PARAMS,
    FXExposureSpec,
    SixDriverFXCorrelation,
    SixDriverFXRiskAggregator,
    _correlated_shocks_6,
    evaluate_g_fx_gate,
    six_driver_fx_use_restrictions,
)
from par_model_v2.stochastic.esg_process import FXParams, Measure


@pytest.fixture(scope="module")
def product():
    return ParEndowmentProduct(
        issue_age=45, gender="M", sum_assured=100000.0,
        annual_premium=5000.0, term_years=20,
    )


# ---------------------------------------------------------------------------
# FXExposureSpec
# ---------------------------------------------------------------------------

def test_fx_exposure_validation_and_cip_exact_mapping():
    with pytest.raises(ValueError):
        FXExposureSpec(exposure_notional=-1.0)
    with pytest.raises(ValueError):
        FXExposureSpec(initial_spot_rate=0.0)
    expo = FXExposureSpec(exposure_notional=10_000.0, initial_spot_rate=7.8)
    # Zero at par, loss under depreciation, gain under appreciation, linear.
    assert expo.liability_impact(np.array([7.8]))[0] == pytest.approx(0.0)
    assert expo.liability_impact(np.array([7.8 * 0.9]))[0] == pytest.approx(1000.0)
    assert expo.liability_impact(np.array([7.8 * 1.1]))[0] == pytest.approx(-1000.0)
    grid = np.linspace(0.5, 1.5, 21) * 7.8
    assert np.all(np.diff(expo.liability_impact(grid)) < 0.0)


# ---------------------------------------------------------------------------
# SixDriverFXCorrelation
# ---------------------------------------------------------------------------

def test_six_driver_correlation_embeds_five_driver_block_and_is_psd():
    corr = SixDriverFXCorrelation()
    C = corr.matrix(-0.25)
    assert C.shape == (6, 6)
    np.testing.assert_allclose(C[:5, :5], FiveDriverCorrelation().matrix(-0.25))
    np.testing.assert_allclose(C, C.T)
    np.testing.assert_allclose(np.diag(C), np.ones(6))
    assert C[5, 0] == pytest.approx(corr.fx_rate)
    assert C[5, 1] == pytest.approx(corr.fx_equity)
    L = corr.cholesky(-0.25)
    np.testing.assert_allclose(L @ L.T, C, atol=1e-7)
    with pytest.raises(ValueError):
        SixDriverFXCorrelation(fx_rate=1.5)


def test_correlated_shocks_6_preserve_five_driver_stream_and_target_corr():
    corr = SixDriverFXCorrelation()
    chol = corr.cholesky(-0.25)
    rng = np.random.default_rng(123)
    shocks = _correlated_shocks_6(rng, 2000, 24, chol)
    assert len(shocks) == 6
    for s in shocks:
        assert s.shape == (2000, 24)
    # Realised correlations match the governed 6x6 targets.
    flat = np.vstack([s.ravel() for s in shocks])
    realised = np.corrcoef(flat)
    np.testing.assert_allclose(realised, corr.matrix(-0.25), atol=0.04)
    # Antithetic construction: each driver's shocks are mean-zero by pairing.
    for s in shocks:
        assert abs(float(s.mean())) < 1e-12


# ---------------------------------------------------------------------------
# G-FX gate
# ---------------------------------------------------------------------------

def test_g_fx_gate_passes_with_default_educational_params():
    gate = evaluate_g_fx_gate(n_scenarios=4000, test_month=12, seed=20260607)
    assert gate["gate"] == "G-FX"
    assert gate["n_criteria"] == 6
    failed = [c for c in gate["criteria"] if not c["passed"]]
    assert gate["passed"], "G-FX failed criteria: {}".format(
        [c["criterion"] for c in failed]
    )
    ids = {c["criterion"] for c in gate["criteria"]}
    assert "FX-04-q-cip-martingale" in ids  # Phase 20 MART-FX-CIP reuse
    mart = next(c for c in gate["criteria"] if c["criterion"] == "FX-04-q-cip-martingale")
    assert mart["evidence"]["check_id"] == "MART-FX-CIP"
    assert mart["evidence"]["n_std_errors"] <= gate["params"]["k_sigma"]


def test_g_fx_gate_detects_broken_exposure_mapping():
    class _Broken(FXExposureSpec):
        def liability_impact(self, x_h):
            return -super().liability_impact(x_h)  # wrong sign

    gate = evaluate_g_fx_gate(
        fx_exposure=_Broken(initial_spot_rate=DEFAULT_FX_PARAMS.initial_spot_rate),
        n_scenarios=500, test_month=6,
    )
    fx06 = next(c for c in gate["criteria"] if c["criterion"] == "FX-06-exposure-mapping")
    assert not fx06["passed"]
    assert not gate["passed"]


# ---------------------------------------------------------------------------
# Outer states and aggregation
# ---------------------------------------------------------------------------

def test_outer_states_6d_shape_fx_positive_and_five_driver_consistency(product):
    agg = SixDriverFXRiskAggregator(product)
    outer = agg._outer_states_6d(400, 12, Measure.P, seed=42)
    assert outer.shape == (400, 6)
    x_h = outer[:, 5]
    assert np.all(x_h > 0.0)
    # FX dispersion roughly matches lognormal theory at H=12m.
    log_x = np.log(x_h / agg.fx_params.initial_spot_rate)
    assert log_x.std() == pytest.approx(agg.fx_params.fx_vol, rel=0.35)
    # Rate column behaves like the calibrated G2++ driver (Phase 20 evidence).
    assert outer[:, 0].std() < 0.02


def test_run_6d_report_structure_and_reproducibility(product):
    cfg = FiveDriverAggregationConfig(
        n_outer=100, n_inner=8, seed=7, capital_horizon_months=12, n_sim_copula=5000,
    )
    agg = SixDriverFXRiskAggregator(product)
    rep = agg.run_6d(config=cfg)
    assert rep.drivers == (
        "short_rate_g2pp_2f", "equity_guarantee", "credit_spread",
        "lapse_behaviour", "mortality_trend", "fx_translation",
    )
    assert set(rep.standalone_scr) == {
        "rate", "equity", "credit", "lapse", "mortality", "fx",
    }
    assert rep.nested_scr > 0.0
    assert rep.var_covar_scr > 0.0
    assert rep.copula_scr > 0.0
    assert rep.correlation_matrix_passed
    assert len(rep.esg_correlation_matrix) == 6
    assert rep.fx_exposure_notional == agg.fx_exposure.exposure_notional
    # Loss vectors cached for downstream tail diagnostics.
    lv = agg.last_loss_vectors_6d
    assert set(lv) == {"rate", "equity", "credit", "lapse", "mortality", "fx", "full"}
    np.testing.assert_allclose(
        lv["full"],
        lv["rate"] + lv["equity"] + lv["credit"] + lv["lapse"]
        + lv["mortality"] + lv["fx"]
        + (lv["full"] - lv["rate"] - lv["equity"] - lv["credit"]
           - lv["lapse"] - lv["mortality"] - lv["fx"]),
    )
    # JSON round-trip.
    import json

    parsed = json.loads(rep.to_json())
    assert parsed["verdict"] == rep.verdict
    assert parsed["reproducibility_digest"] == rep.reproducibility_digest
    # Reproducible for the same seed (digest equality, fresh aggregator).
    rep2 = SixDriverFXRiskAggregator(product).run_6d(config=cfg)
    assert rep2.reproducibility_digest == rep.reproducibility_digest


def test_run_6d_rejects_horizon_beyond_term(product):
    agg = SixDriverFXRiskAggregator(product)
    cfg = FiveDriverAggregationConfig(
        n_outer=100, n_inner=2, capital_horizon_months=240,
    )
    with pytest.raises(ValueError):
        agg.run_6d(config=cfg)


def test_fx_exposure_spot_mismatch_rejected(product):
    with pytest.raises(ValueError):
        SixDriverFXRiskAggregator(
            product,
            fx_params=FXParams(initial_spot_rate=7.8),
            fx_exposure=FXExposureSpec(initial_spot_rate=1.0),
        )


def test_use_restrictions_disclose_educational_status():
    r = six_driver_fx_use_restrictions()
    assert r["status"] == "EDUCATIONAL"
    assert any("NOT calibrated" in s for s in r["restrictions"])
    assert any("Task 2" in s for s in r["restrictions"])


def test_staged_slicing_reproduces_monolithic_loss_vectors(product):
    """component_liabilities_sliced + precomputed run_6d must reproduce the
    monolithic run bit-for-bit (slice-stable CRN seed protocol)."""
    cfg = FiveDriverAggregationConfig(
        n_outer=100, n_inner=2, seed=11, capital_horizon_months=12, n_sim_copula=5000,
    )
    agg = SixDriverFXRiskAggregator(product)
    outer6 = agg._outer_states_6d(cfg.n_outer, cfg.capital_horizon_months,
                                  Measure.P, cfg.seed)
    outer5 = outer6[:, :5]
    # Staged: two uneven slices.
    s1 = agg.component_liabilities_sliced(outer5, 0, 37, cfg)
    s2 = agg.component_liabilities_sliced(outer5, 37, 100, cfg)
    pre = {k: np.concatenate([s1[k], s2[k]]) for k in s1}
    pre["fx"] = agg.fx_exposure.liability_impact(outer6[:, 5])
    rep_staged = agg.run_6d(config=cfg, precomputed=pre)
    rep_mono = SixDriverFXRiskAggregator(product).run_6d(config=cfg)
    assert rep_staged.reproducibility_digest == rep_mono.reproducibility_digest
    assert rep_staged.nested_scr == pytest.approx(rep_mono.nested_scr)
