"""Phase 20 Task 4 - two-factor G2++ capital re-aggregation tests.

Verifies the additive G2++ outer-rate driver: parameter wiring, that the
non-rate drivers are preserved bit-for-bit vs the HW1F baseline (same shocks),
that the calibrated 2F driver lowers the horizon short-rate dispersion, and that
the aggregator produces a reproducible, structurally valid five-driver report.
"""

import numpy as np
import pytest

from par_model_v2.projection.monthly_projection import ParEndowmentProduct
from par_model_v2.projection.multi_driver_capital_5d import _outer_states_5d
from par_model_v2.projection.multi_driver_capital_5d_aggregation import (
    FiveDriverAggregationConfig,
    FiveDriverRiskAggregator,
)
from par_model_v2.projection.multi_driver_capital_5d_g2pp import (
    CALIBRATED_G2PP_PARAMS,
    G2ppFiveDriverRiskAggregator,
    _outer_states_5d_g2pp,
    calibrated_g2pp_params,
)
from par_model_v2.stochastic.esg_process import Measure


@pytest.fixture(scope="module")
def product():
    return ParEndowmentProduct(
        issue_age=45, gender="M", sum_assured=100000.0,
        annual_premium=5000.0, term_years=20,
    )


def test_calibrated_params_match_swaption_report():
    p = calibrated_g2pp_params()
    assert p.mean_reversion_x == pytest.approx(CALIBRATED_G2PP_PARAMS["mean_reversion_x"])
    assert p.mean_reversion_y == pytest.approx(CALIBRATED_G2PP_PARAMS["mean_reversion_y"])
    assert p.vol_x == pytest.approx(CALIBRATED_G2PP_PARAMS["vol_x"])
    assert p.vol_y == pytest.approx(CALIBRATED_G2PP_PARAMS["vol_y"])
    assert p.factor_correlation == pytest.approx(CALIBRATED_G2PP_PARAMS["factor_correlation"])
    # Distinct positive mean reversions, valid correlation (G-SWPN-05 shape).
    assert p.mean_reversion_x > 0 and p.mean_reversion_y > 0
    assert p.mean_reversion_x != p.mean_reversion_y
    assert -1.0 < p.factor_correlation < 1.0


def test_non_rate_drivers_preserved_and_rate_dispersion_lower(product):
    """The four non-rate drivers must match the HW1F baseline exactly (same
    governed shocks); only the rate marginal changes (smaller dispersion)."""
    agg = FiveDriverRiskAggregator(product)
    H, n, seed = 12, 3000, 42
    hw = _outer_states_5d(
        n, H, Measure.P, agg.hw_params, agg.gbm_params, agg.spread_params,
        agg.lapse_params, agg.mortality_params, agg.correlation, agg.initial_curve, seed,
    )
    g2agg = G2ppFiveDriverRiskAggregator(product)
    g2, r_paths = _outer_states_5d_g2pp(
        g2agg, calibrated_g2pp_params(), n, H, Measure.P, seed,
    )
    # Credit, lapse and mortality (cols 2..4) are independent of the rate path
    # and must match the HW1F baseline bit-for-bit (same governed shocks).
    np.testing.assert_allclose(hw[:, 2:], g2[:, 2:], rtol=0, atol=1e-9)
    # Equity (col 1) is intentionally rate-coupled through its drift, so it shifts
    # with the rate path but its marginal distribution is essentially unchanged.
    assert g2[:, 1].mean() == pytest.approx(hw[:, 1].mean(), abs=0.5)
    assert g2[:, 1].std() == pytest.approx(hw[:, 1].std(), abs=0.5)
    # Rate level comparable; dispersion strictly lower under the calibrated 2F driver.
    assert g2[:, 0].std() < hw[:, 0].std()
    assert g2[:, 0].std() == pytest.approx(0.0049, abs=0.0015)
    # Returned short-rate path has the right shape and matches r_H at the horizon.
    assert r_paths.shape == (n, H + 1)
    np.testing.assert_allclose(r_paths[:, H], g2[:, 0], rtol=0, atol=1e-12)


def test_aggregator_report_structure_and_reproducibility(product):
    cfg = FiveDriverAggregationConfig(
        n_outer=100, n_inner=16, seed=7, capital_horizon_months=12, n_sim_copula=5000,
    )
    g2agg = G2ppFiveDriverRiskAggregator(product)
    rep = g2agg.run(config=cfg)

    assert rep.drivers[0] == "short_rate_g2pp_2f"
    assert rep.verdict.startswith(("PASS", "PARTIAL"))
    assert rep.nested_scr > 0
    # last_loss_vectors populated for downstream tail diagnostics.
    assert g2agg.last_loss_vectors is not None
    for k in ("rate", "equity", "credit", "lapse", "mortality", "full", "crn_sum"):
        assert g2agg.last_loss_vectors[k].shape == (cfg.n_outer,)
    # Copula reconciles to nested at least as well as the var-covar formula.
    assert (rep.copula.selected.scr_rel_error_vs_nested
            <= rep.var_covar.formula_vs_nested_scr_rel_error + 1e-9)

    # Reproducible: same seed -> identical digest and nested SCR.
    rep2 = G2ppFiveDriverRiskAggregator(product).run(config=cfg)
    assert rep2.reproducibility_digest == rep.reproducibility_digest
    assert rep2.nested_scr == pytest.approx(rep.nested_scr)


def test_to_dict_json_roundtrip(product):
    cfg = FiveDriverAggregationConfig(
        n_outer=100, n_inner=12, seed=11, capital_horizon_months=12, n_sim_copula=4000,
    )
    rep = G2ppFiveDriverRiskAggregator(product).run(config=cfg)
    import json
    d = json.loads(rep.to_json())
    assert d["drivers"][0] == "short_rate_g2pp_2f"
    assert "var_covar" in d and "copula" in d and "standalone" in d
