"""Phase 21 Task 4 tests — seven-driver tail-dependent aggregation + tail
diagnostics.

Covers: calibrated liquidity-parameter loading, the analytic CIR-affine
forced-sale haircut (incl. the Monte-Carlo cross-check), the baseline-centred
liquidity exposure mapping, the 7x7 governed correlation, bit-compatibility
of the seven-driver outer joint with the Phase 21 Task 1 six-driver engine,
the full run_7d report (structure, reproducibility digest, staged-vs-direct
equivalence), and the tail diagnostics (convergence, bootstrap CIs, RQMC).

SOA ASOP 56 3.1.3/3.5; SOA ASOP 25 3.3; IA TAS M 3.6; Solvency II Art. 234.
"""

import numpy as np
import pytest

from par_model_v2.projection.monthly_projection import ParEndowmentProduct
from par_model_v2.projection.multi_driver_capital_5d_aggregation import (
    FiveDriverAggregationConfig,
)
from par_model_v2.projection.multi_driver_capital_6d_fx import (
    SixDriverFXRiskAggregator,
)
from par_model_v2.projection.multi_driver_capital_7d_aggregation import (
    DRIVERS_7D,
    LiquidityExposureSpec,
    SevenDriverCorrelation,
    SevenDriverLiquidityRiskAggregator,
    SevenDriverTailConfig,
    SevenDriverTailDiagnostics,
    calibrated_liquidity_params,
    cir_affine_haircut,
    seven_driver_use_restrictions,
)
from par_model_v2.stochastic.esg_process import GBMParams, Measure
from par_model_v2.stochastic.liquidity_premium import (
    LiquidityPremiumParams,
    _inner_q_liquidity_process,
    forced_sale_haircut_fraction,
)


@pytest.fixture(scope="module")
def product():
    return ParEndowmentProduct(
        issue_age=45, gender="M", sum_assured=100000.0,
        annual_premium=5000.0, term_years=20,
    )


@pytest.fixture(scope="module")
def small_cfg():
    return FiveDriverAggregationConfig(
        n_outer=100, n_inner=2, seed=11, capital_horizon_months=12,
        n_sim_copula=5000,
    )


@pytest.fixture(scope="module")
def small_tail_cfg():
    return SevenDriverTailConfig(
        n_sim_grid=(2_000, 4_000), n_bootstrap_sim=60, n_bootstrap_nested=200,
        vr_n=512, vr_replications=5, seed=3,
    )


_RUN_CACHE = {}


def _direct_report(product, small_cfg, small_tail_cfg):
    if "direct" not in _RUN_CACHE:
        agg = SevenDriverLiquidityRiskAggregator(product)
        _RUN_CACHE["direct"] = (
            agg.run_7d(config=small_cfg, tail_config=small_tail_cfg),
            {k: v.copy() for k, v in agg.last_loss_vectors_7d.items()},
        )
    return _RUN_CACHE["direct"]


# ---------------------------------------------------------------------------
# Calibrated parameters + analytic haircut
# ---------------------------------------------------------------------------

def test_calibrated_liquidity_params_load_task3_values():
    p = calibrated_liquidity_params()
    # Phase 21 Task 3 G-LIQ calibration (HKD educational proxy).
    assert p.mean_reversion_speed == pytest.approx(0.9345, abs=0.01)
    assert 0.003 < p.long_run_premium_p < 0.012
    assert 0.01 < p.premium_vol < 0.05
    assert 0.0 <= p.market_price_of_liquidity_risk <= 2.0


def test_cir_affine_haircut_matches_monte_carlo():
    p = calibrated_liquidity_params()
    tau_m = 120
    tau = tau_m / 12.0
    for l_h in (0.004, 0.02):
        proc = _inner_q_liquidity_process(l_h, p)
        frame = proc.simulate(2000, tau_m, Measure.Q, seed=123)
        arr = frame["liquidity_premium"].to_numpy().reshape(2000, tau_m + 1)
        mc = float(forced_sale_haircut_fraction(arr).mean())
        an = float(cir_affine_haircut(l_h, p, tau))
        assert an == pytest.approx(mc, rel=5e-3)


def test_cir_affine_haircut_monotone_bounded_and_validates():
    p = calibrated_liquidity_params()
    grid = np.array([0.002, 0.005, 0.01, 0.03, 0.08])
    h = cir_affine_haircut(grid, p, 19.0)
    assert np.all(np.diff(h) > 0.0)          # widening premium => larger haircut
    assert np.all((h > 0.0) & (h < 1.0))
    with pytest.raises(ValueError):
        cir_affine_haircut(0.01, p, 0.0)


def test_liquidity_exposure_is_baseline_centred_and_signed():
    p = calibrated_liquidity_params()
    spec = LiquidityExposureSpec(exposure_notional=30_000.0)
    base = spec.liability_impact(p.initial_premium, p, 19.0)
    assert float(base) == pytest.approx(0.0, abs=1e-9)
    widened = float(spec.liability_impact(p.initial_premium + 0.01, p, 19.0))
    tightened = float(spec.liability_impact(max(p.initial_premium - 0.003, 0.0), p, 19.0))
    assert widened > 0.0 > tightened
    with pytest.raises(ValueError):
        LiquidityExposureSpec(exposure_notional=-1.0)


# ---------------------------------------------------------------------------
# 7x7 correlation
# ---------------------------------------------------------------------------

def test_seven_driver_correlation_embeds_six_driver_block_and_is_psd():
    corr = SevenDriverCorrelation()
    g = GBMParams().rate_equity_correlation
    C = corr.matrix(g)
    assert C.shape == (7, 7)
    np.testing.assert_allclose(C, C.T)
    np.testing.assert_allclose(np.diag(C), 1.0)
    np.testing.assert_array_equal(C[:6, :6], corr.six_driver.matrix(g))
    assert np.linalg.eigvalsh(C).min() > 0.0
    L = corr.cholesky(g)
    np.testing.assert_allclose(L @ L.T, C, atol=1e-10)
    with pytest.raises(ValueError):
        SevenDriverCorrelation(liq_spread=1.5)


# ---------------------------------------------------------------------------
# Outer joint bit-compatibility with the six-driver engine
# ---------------------------------------------------------------------------

def test_outer_states_7d_bit_identical_first_six_columns(product):
    a7 = SevenDriverLiquidityRiskAggregator(product)
    a6 = SixDriverFXRiskAggregator(product)
    o7 = a7._outer_states_7d(64, 12, Measure.P, 42)
    o6 = a6._outer_states_6d(64, 12, Measure.P, 42)
    assert o7.shape == (64, 7)
    np.testing.assert_array_equal(o7[:, :6], o6)
    lp = a7.liquidity_params
    assert np.all(o7[:, 6] >= lp.premium_floor)
    assert np.all(o7[:, 6] <= lp.premium_ceiling)


# ---------------------------------------------------------------------------
# Full run: structure, digest, staged equivalence
# ---------------------------------------------------------------------------

def test_run_7d_report_structure(product, small_cfg, small_tail_cfg):
    report, loss = _direct_report(product, small_cfg, small_tail_cfg)
    d = report.to_dict()
    assert tuple(d["drivers"]) == DRIVERS_7D
    assert set(d["standalone_scr"]) == set(DRIVERS_7D)
    assert d["standalone_scr_sum"] == pytest.approx(
        sum(d["standalone_scr"].values()))
    assert len(d["esg_correlation_matrix"]) == 7
    assert d["correlation_matrix_passed"] is True
    assert d["var_covar_scr"] > 0.0
    assert d["nested_scr"] > 0.0
    assert d["copula_selected"] in ("gaussian", "student_t", "survival_clayton")
    assert d["verdict"] in ("PASS", "REVIEW")
    assert len(d["reproducibility_digest"]) == 64
    assert set(loss) == set(DRIVERS_7D) | {"full"}
    for k, v in loss.items():
        assert v.shape == (small_cfg.n_outer,)
        assert np.all(np.isfinite(v))
    # The liquidity component is exactly the analytic centred haircut of the
    # outer premium states (no inner noise) — sanity: not all zero, bounded
    # by the exposure notional.
    agg_notional = report.liquidity_exposure_notional
    assert np.any(loss["liquidity"] != 0.0)
    assert np.all(np.abs(loss["liquidity"]) <= agg_notional)


def test_run_7d_staged_precomputed_reproduces_direct(product, small_cfg, small_tail_cfg):
    direct_report, direct_loss = _direct_report(product, small_cfg, small_tail_cfg)
    agg = SevenDriverLiquidityRiskAggregator(product)
    outer7 = agg._outer_states_7d(
        small_cfg.n_outer, small_cfg.capital_horizon_months,
        small_cfg.outer_measure, small_cfg.seed,
    )
    # Staged protocol: slices of the full outer array, CRN child seeds.
    pre = {k: np.empty(small_cfg.n_outer) for k in
           ("rate", "equity", "credit", "lapse", "mortality", "full5")}
    for (i0, i1) in ((0, 37), (37, 80), (80, 100)):
        part = agg.component_liabilities_sliced(outer7[:, :5], i0, i1, small_cfg)
        for k in pre:
            pre[k][i0:i1] = part[k]
    tau = agg._liquidity_tau_years(small_cfg.capital_horizon_months)
    pre["fx"] = agg.fx_exposure.liability_impact(outer7[:, 5])
    pre["liquidity"] = agg.liquidity_exposure.liability_impact(
        outer7[:, 6], agg.liquidity_params, tau)
    staged_report = agg.run_7d(
        config=small_cfg, precomputed=pre, tail_config=small_tail_cfg)
    for k in DRIVERS_7D:
        np.testing.assert_array_equal(
            agg.last_loss_vectors_7d[k], direct_loss[k])
    assert (staged_report.reproducibility_digest
            == direct_report.reproducibility_digest)
    assert staged_report.nested_scr == pytest.approx(direct_report.nested_scr)


def test_run_7d_rejects_bad_precomputed_and_horizon(product, small_cfg):
    agg = SevenDriverLiquidityRiskAggregator(product)
    with pytest.raises(ValueError, match="missing keys"):
        agg.run_7d(config=small_cfg, precomputed={"rate": np.zeros(100)})
    bad = FiveDriverAggregationConfig(
        n_outer=100, n_inner=2, capital_horizon_months=240, n_sim_copula=5000)
    with pytest.raises(ValueError, match="capital_horizon_months"):
        agg.run_7d(config=bad)


# ---------------------------------------------------------------------------
# Tail diagnostics
# ---------------------------------------------------------------------------

def test_tail_diagnostics_structure_and_sanity(product, small_cfg, small_tail_cfg):
    report, _loss = _direct_report(product, small_cfg, small_tail_cfg)
    td = report.tail_diagnostics
    assert td["skipped"] is False
    assert td["n_sim_grid"] == [2_000, 4_000]
    assert len(td["var_convergence_path"]) == 2
    assert len(td["successive_var_rel_deltas"]) == 1
    assert isinstance(td["converged"], bool)
    sb = td["simulated_bootstrap"]
    nb = td["nested_bootstrap"]
    for boot in (sb, nb):
        assert boot["var_ci"][0] < boot["var_ci"][1]
        assert boot["es_ci"][0] < boot["es_ci"][1]
        assert boot["var_se"] > 0.0
        assert boot["var_ci_rel_halfwidth"] > 0.0
    # ES dominates VaR in the upper tail.
    assert sb["es_point"] >= sb["var_point"]
    assert nb["es_point"] >= nb["var_point"]
    assert "SMALL" in nb["disclosure"]
    vr = td["variance_reduction"]
    assert vr["crude_var_of_var"] > 0.0
    assert vr["sobol_var_of_var"] > 0.0
    assert vr["qmc_variance_reduction_ratio"] > 0.0


def test_tail_diagnostics_validates_inputs():
    with pytest.raises(ValueError, match="ascending"):
        SevenDriverTailConfig(n_sim_grid=(5000, 1000))
    with pytest.raises(ValueError, match="loss_matrix"):
        SevenDriverTailDiagnostics(np.zeros((10, 3)), np.zeros(10))
    with pytest.raises(ValueError, match="nested_full"):
        SevenDriverTailDiagnostics(np.zeros((10, 7)), np.zeros(9))


def test_tail_diagnostics_reproducible_same_seed():
    rng = np.random.default_rng(0)
    L = rng.standard_normal((150, 7)) * np.array([5, 4, 3, 2, 1, 1, 0.5])
    full = L.sum(axis=1)
    cfg = SevenDriverTailConfig(
        n_sim_grid=(1_000, 2_000), n_bootstrap_sim=50, n_bootstrap_nested=50,
        vr_n=256, vr_replications=5, seed=7)
    a = SevenDriverTailDiagnostics(L, full).run(cfg)
    b = SevenDriverTailDiagnostics(L, full).run(cfg)
    assert a["var_convergence_path"] == b["var_convergence_path"]
    assert a["simulated_bootstrap"]["var_ci"] == b["simulated_bootstrap"]["var_ci"]
    assert (a["variance_reduction"]["qmc_variance_reduction_ratio"]
            == b["variance_reduction"]["qmc_variance_reduction_ratio"])


# ---------------------------------------------------------------------------
# Use restrictions
# ---------------------------------------------------------------------------

def test_use_restrictions_disclose_educational_status():
    r = seven_driver_use_restrictions()
    assert r["status"] == "EDUCATIONAL"
    assert any("APS X2" in p for p in r["prohibited_uses"])
    assert any("placeholder" in k.lower() for k in r["key_limitations"])
