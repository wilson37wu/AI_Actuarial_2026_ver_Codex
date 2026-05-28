"""
Tests for par_model_v2.projection.tvog — Phase 4, Task 2.

VR-T01  TVOGEngine rejects P-measure scenarios
VR-T02  TVOGEngine rejects scenario horizon shorter than product term
VR-T03  ScenarioCountWarning raised below minimum
VR-T04  TVOG is positive for low-rate Q-measure environment (qualitative)
VR-T05  TVOG = 0 when stochastic discount rate == deterministic rate
VR-T06  compute() is reproducible for same ScenarioSet seed
VR-T07  per-scenario PVs have correct shape (n_scenarios,)
VR-T08  pv_p5 <= pv_stochastic_mean <= pv_p95
VR-T09  TVOG = mean(scenario_pvs) - pv_deterministic identity
VR-T10  higher deterministic rate raises TVOG (lower determ base)
VR-T11  longer term increases absolute TVOG (more guarantee exposure)
VR-T12  summary() returns all required keys
VR-T13  is_negative_tvog flag set correctly
VR-T14  _scenario_discount_factors month-0 anchor = 1.0
VR-T15  _scenario_discount_factors is monotonically non-increasing for r > 0
VR-T16  _guaranteed_pv_single_scenario: PV < sum_assured (discounting reduces value)
VR-T17  _guaranteed_pv_single_scenario: PV > 0 for any valid product
VR-T18  GovernanceStore integration: 2 audit entries appended on compute()
VR-T19  audit_entry_id populated when governance_store provided
VR-T20  TVOGResult.run_id is unique per call
VR-T21  TVOGEngine with custom annual_qx_fn changes result
VR-T22  Scenario horizon larger than term uses only product-term months
VR-T23  10y product TVOG is numerically stable (no NaN/Inf)
VR-T24  TVOG range sanity: between -10% and +100% of sum_assured
VR-T25  TVOGResult fields accessible after compute()
"""

from __future__ import annotations

import warnings

import numpy as np
import pytest

from par_model_v2.governance.audit_trail import GovernanceStore
from par_model_v2.projection.monthly_projection import ParEndowmentProduct
from par_model_v2.projection.tvog import (
    TVOG_MINIMUM_SCENARIOS,
    ScenarioCountWarning,
    TVOGEngine,
    TVOGResult,
    _guaranteed_pv_single_scenario,
    _scenario_discount_factors,
)
from par_model_v2.stochastic.esg_process import Measure, ScenarioSet


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

def _product(term_years=5):
    return ParEndowmentProduct(
        term_years=term_years,
        issue_age=35,
        gender="M",
        sum_assured=100_000.0,
        annual_premium=5_000.0,
    )


def _q_scenarios(n=500, T_months=60, seed=42):
    return ScenarioSet.generate(n=n, T_months=T_months, measure=Measure.Q, seed=seed)


def _p_scenarios(n=500, T_months=60, seed=42):
    return ScenarioSet.generate(n=n, T_months=T_months, measure=Measure.P, seed=seed)


# ---------------------------------------------------------------------------
# VR-T01  P-measure rejected
# ---------------------------------------------------------------------------

class TestInputValidation:
    def test_vr_t01_p_measure_rejected(self):
        p_scen = _p_scenarios()
        with pytest.raises(ValueError, match="Q-measure"):
            TVOGEngine(_product(), p_scen)

    def test_vr_t02_scenario_horizon_too_short(self):
        short_scen = _q_scenarios(T_months=48)  # < 60 months for 5y product
        with pytest.raises(ValueError, match="horizon"):
            TVOGEngine(_product(5), short_scen)

    def test_vr_t03_scenario_count_warning_below_minimum(self):
        tiny = ScenarioSet.generate(
            n=TVOG_MINIMUM_SCENARIOS - 1,
            T_months=60,
            measure=Measure.Q,
            seed=1,
        )
        with pytest.warns(ScenarioCountWarning, match="minimum"):
            TVOGEngine(_product(), tiny)


# ---------------------------------------------------------------------------
# VR-T04 -- VR-T13  Core computation properties
# ---------------------------------------------------------------------------

class TestTVOGComputation:
    def test_vr_t04_tvog_positive_in_low_rate_environment(self):
        # Default HW params have r(0)=2%, long-run=2.5%; below the 3.5% det rate
        # => Q-mean PV > deterministic PV => TVOG > 0
        engine = TVOGEngine(_product(), _q_scenarios())
        result = engine.compute()
        assert result.tvog > 0, "Expected positive TVOG in low-rate environment"

    def test_vr_t05_tvog_near_zero_when_rates_match_deterministic(self):
        # Build a ScenarioSet with ~flat rates near the deterministic rate
        from par_model_v2.stochastic.esg_process import (
            HullWhiteParams, ScenarioSet, Measure
        )
        det_rate = 0.035
        # Very fast mean-reversion with low vol snaps to initial_short_rate
        hw = HullWhiteParams(
            initial_short_rate=det_rate,
            long_run_rate_p=det_rate,
            mean_reversion_speed=5.0,
            short_rate_vol=0.0001,
        )
        scen = ScenarioSet.generate(
            n=500, T_months=60, measure=Measure.Q,
            hw_params=hw, seed=1
        )
        engine = TVOGEngine(_product(), scen, deterministic_discount_rate=det_rate)
        result = engine.compute()
        # TVOG should be very small (within 0.5% of sum_assured)
        assert abs(result.tvog) < 0.005 * _product().sum_assured

    def test_vr_t06_reproducible_same_seed(self):
        scen_a = _q_scenarios(seed=7)
        scen_b = _q_scenarios(seed=7)
        result_a = TVOGEngine(_product(), scen_a).compute()
        result_b = TVOGEngine(_product(), scen_b).compute()
        assert np.isclose(result_a.tvog, result_b.tvog)

    def test_vr_t07_scenario_pvs_correct_shape(self):
        n = 500
        result = TVOGEngine(_product(), _q_scenarios(n=n)).compute()
        assert result.scenario_pvs.shape == (n,)

    def test_vr_t08_percentile_ordering(self):
        result = TVOGEngine(_product(), _q_scenarios()).compute()
        assert result.pv_p5 <= result.pv_guaranteed_stochastic_mean
        assert result.pv_guaranteed_stochastic_mean <= result.pv_p95

    def test_vr_t09_tvog_identity(self):
        result = TVOGEngine(_product(), _q_scenarios()).compute()
        expected = result.scenario_pvs.mean() - result.pv_guaranteed_deterministic
        assert np.isclose(result.tvog, expected, rtol=1e-10)

    def test_vr_t10_higher_deterministic_rate_raises_tvog(self):
        scen = _q_scenarios()
        low_det = TVOGEngine(_product(), scen, deterministic_discount_rate=0.020).compute()
        high_det = TVOGEngine(_product(), scen, deterministic_discount_rate=0.050).compute()
        # Higher det rate -> lower det PV -> higher TVOG
        assert high_det.tvog > low_det.tvog

    def test_vr_t11_longer_term_increases_absolute_tvog(self):
        scen_5y = _q_scenarios(T_months=60)
        scen_10y = _q_scenarios(T_months=120)
        tvog_5y = abs(TVOGEngine(_product(5), scen_5y).compute().tvog)
        tvog_10y = abs(TVOGEngine(_product(10), scen_10y).compute().tvog)
        assert tvog_10y > tvog_5y

    def test_vr_t12_summary_keys(self):
        result = TVOGEngine(_product(), _q_scenarios()).compute()
        s = result.summary()
        required_keys = {
            "tvog", "pv_guaranteed_stochastic_mean", "pv_guaranteed_deterministic",
            "deterministic_discount_rate", "n_scenarios", "T_months",
            "pv_p5", "pv_p95", "is_negative_tvog", "run_id",
        }
        assert required_keys.issubset(set(s.keys()))

    def test_vr_t13_is_negative_tvog_flag(self):
        result = TVOGEngine(_product(), _q_scenarios()).compute()
        assert result.is_negative_tvog == (result.tvog < 0.0)


# ---------------------------------------------------------------------------
# VR-T14 -- VR-T17  Helper function unit tests
# ---------------------------------------------------------------------------

class TestHelpers:
    def test_vr_t14_discount_factors_month_zero_anchor(self):
        r_path = np.full(61, 0.03)
        d = _scenario_discount_factors(r_path, 60)
        assert d[0] == 1.0

    def test_vr_t15_discount_factors_monotone_for_positive_rate(self):
        r_path = np.full(61, 0.03)
        d = _scenario_discount_factors(r_path, 60)
        assert np.all(np.diff(d) <= 0)

    def test_vr_t16_guaranteed_pv_less_than_sum_assured(self):
        product = _product()
        r_path = np.full(61, 0.03)
        d = _scenario_discount_factors(r_path, 60)
        pv = _guaranteed_pv_single_scenario(product, d)
        assert pv < product.sum_assured

    def test_vr_t17_guaranteed_pv_positive(self):
        product = _product()
        r_path = np.full(61, 0.03)
        d = _scenario_discount_factors(r_path, 60)
        pv = _guaranteed_pv_single_scenario(product, d)
        assert pv > 0.0

    def test_discount_factors_zero_rate_is_all_ones(self):
        r_path = np.zeros(13)
        d = _scenario_discount_factors(r_path, 12)
        assert np.allclose(d, 1.0)

    def test_discount_factors_shape(self):
        r_path = np.full(25, 0.02)
        d = _scenario_discount_factors(r_path, 24)
        assert d.shape == (25,)


# ---------------------------------------------------------------------------
# VR-T18 -- VR-T20  Governance integration
# ---------------------------------------------------------------------------

class TestGovernanceIntegration:
    def test_vr_t18_two_audit_entries_appended(self):
        store = GovernanceStore()
        initial = len(store.audit_trail.all())
        TVOGEngine(_product(), _q_scenarios()).compute(governance_store=store)
        assert len(store.audit_trail.all()) == initial + 2

    def test_vr_t19_audit_entry_id_populated(self):
        store = GovernanceStore()
        result = TVOGEngine(_product(), _q_scenarios()).compute(governance_store=store)
        assert result.audit_entry_id is not None
        assert isinstance(result.audit_entry_id, str)

    def test_vr_t20_run_id_unique_per_call(self):
        engine = TVOGEngine(_product(), _q_scenarios())
        r1 = engine.compute()
        r2 = engine.compute()
        assert r1.run_id != r2.run_id


# ---------------------------------------------------------------------------
# VR-T21 -- VR-T25  Edge cases and stability
# ---------------------------------------------------------------------------

class TestEdgeCasesAndStability:
    def test_vr_t21_custom_qx_fn_changes_result(self):
        scen = _q_scenarios()
        default_result = TVOGEngine(_product(), scen).compute()

        def high_mortality(age, gender):
            return 0.05  # 5% annual mortality -- much higher

        custom_result = TVOGEngine(
            _product(), scen, annual_qx_fn=high_mortality
        ).compute()
        assert not np.isclose(
            default_result.pv_guaranteed_stochastic_mean,
            custom_result.pv_guaranteed_stochastic_mean,
        )

    def test_vr_t22_scenario_horizon_larger_than_term_uses_only_term_months(self):
        # 10y scenarios, 5y product -- should only use months 0..60
        scen_long = _q_scenarios(T_months=120)
        product_5y = _product(5)
        result = TVOGEngine(product_5y, scen_long).compute()
        assert result.T_months == product_5y.term_months

    def test_vr_t23_10y_product_no_nan_or_inf(self):
        scen = _q_scenarios(T_months=120)
        result = TVOGEngine(_product(10), scen).compute()
        assert np.isfinite(result.tvog)
        assert np.all(np.isfinite(result.scenario_pvs))

    def test_vr_t24_tvog_within_sanity_range(self):
        product = _product()
        result = TVOGEngine(product, _q_scenarios()).compute()
        # TVOG should be between -10% and +100% of sum_assured
        lower = -0.10 * product.sum_assured
        upper = 1.00 * product.sum_assured
        assert lower <= result.tvog <= upper

    def test_vr_t25_result_fields_accessible(self):
        result = TVOGEngine(_product(), _q_scenarios()).compute()
        assert isinstance(result.tvog, (float, np.floating))
        assert isinstance(result.pv_guaranteed_stochastic_mean, (float, np.floating))
        assert isinstance(result.pv_guaranteed_deterministic, (float, np.floating))
        assert isinstance(result.n_scenarios, int)
        assert isinstance(result.T_months, int)
        assert isinstance(result.run_id, str)
        assert isinstance(result.scenario_pvs, np.ndarray)
