"""
Unit Tests — Calibration Framework
===================================

Tests for par_model_v2/calibration/calibration_framework.py

Coverage:
- VR-C01: HullWhiteCalibrator input validation
- VR-C02: HullWhiteCalibrator.calibrate() L-BFGS-B optimization
- VR-C03: HullWhiteCalibrator goodness-of-fit table
- VR-C04: GBMCalibrator input validation
- VR-C05: GBMCalibrator.calibrate() vol blending and ERP
- VR-C06: GBMCalibrator helper methods
- VR-C07: CalibrationResult dataclass methods
- VR-C08: martingale_test Q-measure validation
- VR-C09: martingale_test P-measure rejection
- VR-C10: Integration with ScenarioSet.generate()

Standards Reference:
- SOA ASOP 56 §3.4: Calibration methodology
- SOA ASOP 25 §3.3: Credibility of assumptions
- IA TAS M §3.5: Assumption appropriateness
- docs/PARAMETER_CALIBRATION_METHODOLOGY.md §5-7

Phase 4, Task 3: Implement parameter calibration methodology
"""

import warnings
from datetime import date
from typing import List

import numpy as np
import pandas as pd
import pytest

from par_model_v2.calibration import (
    CalibrationResult,
    GBMCalibrationInputs,
    GBMCalibrator,
    HullWhiteCalibrationInputs,
    HullWhiteCalibrator,
    SwaptionQuote,
    martingale_test,
)
from par_model_v2.stochastic.esg_process import Measure, ScenarioSet


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def sample_spot_curve() -> pd.Series:
    """Sample CNY government bond spot curve."""
    tenors = [0.25, 0.5, 1.0, 2.0, 3.0, 5.0, 7.0, 10.0, 15.0, 20.0]
    rates = [0.018, 0.019, 0.020, 0.022, 0.024, 0.026, 0.027, 0.028, 0.029, 0.030]
    return pd.Series(rates, index=tenors)


@pytest.fixture
def sample_swaption_quotes() -> List[SwaptionQuote]:
    """Sample ATM payer swaption quotes for HW1F calibration."""
    return [
        SwaptionQuote(expiry_years=1.0, swap_tenor_years=5.0, normal_vol_bps=42.0),
        SwaptionQuote(expiry_years=2.0, swap_tenor_years=5.0, normal_vol_bps=40.0),
        SwaptionQuote(expiry_years=5.0, swap_tenor_years=5.0, normal_vol_bps=38.0),
        SwaptionQuote(expiry_years=5.0, swap_tenor_years=10.0, normal_vol_bps=35.0),
        SwaptionQuote(expiry_years=10.0, swap_tenor_years=10.0, normal_vol_bps=30.0),
    ]


@pytest.fixture
def hw_calibration_inputs(
    sample_spot_curve, sample_swaption_quotes
) -> HullWhiteCalibrationInputs:
    """Complete HW1F calibration inputs."""
    return HullWhiteCalibrationInputs(
        calibration_date=date(2026, 5, 23),
        initial_short_rate=0.022,
        spot_curve=sample_spot_curve,
        swaption_quotes=sample_swaption_quotes,
        regulatory_rate_cap=0.03,
    )


@pytest.fixture
def sample_equity_returns() -> pd.Series:
    """Sample 5-year daily log-returns for CSI 300."""
    np.random.seed(42)
    n_days = 252 * 5
    dates = pd.date_range(start="2021-01-01", periods=n_days, freq="B")
    daily_vol = 0.20 / np.sqrt(252)
    returns = np.random.normal(0.0005, daily_vol, n_days)
    return pd.Series(returns, index=dates)


@pytest.fixture
def sample_rf_returns() -> pd.Series:
    """Sample 5-year daily risk-free rate series."""
    np.random.seed(43)
    n_days = 252 * 5
    dates = pd.date_range(start="2021-01-01", periods=n_days, freq="B")
    base_rate = 0.025
    noise = np.random.normal(0, 0.001, n_days)
    rates = base_rate + np.cumsum(noise) * 0.01
    rates = np.clip(rates, 0.01, 0.04)
    return pd.Series(rates, index=dates)


@pytest.fixture
def sample_dividend_yield() -> pd.Series:
    """Sample 3-year monthly dividend yield series."""
    dates = pd.date_range(start="2023-01-31", periods=36, freq="ME")
    yields = np.linspace(0.022, 0.028, 36) + np.random.normal(0, 0.001, 36)
    return pd.Series(yields, index=dates)


@pytest.fixture
def gbm_calibration_inputs(
    sample_equity_returns, sample_rf_returns, sample_dividend_yield
) -> GBMCalibrationInputs:
    """Complete GBM calibration inputs."""
    return GBMCalibrationInputs(
        calibration_date=date(2026, 5, 23),
        equity_returns=sample_equity_returns,
        rf_returns=sample_rf_returns,
        dividend_yield_monthly=sample_dividend_yield,
        implied_vol_atm=0.22,
        implied_vol_weight=0.60,
        erp_survivorship_adjustment=0.007,
        erp_upper_bound=0.05,
    )


# =============================================================================
# Test Classes
# =============================================================================


class TestSwaptionQuote:
    """Tests for SwaptionQuote dataclass."""

    def test_default_weight(self):
        """Default weight should be 1.0."""
        q = SwaptionQuote(expiry_years=1.0, swap_tenor_years=5.0, normal_vol_bps=42.0)
        assert q.weight == 1.0

    def test_custom_weight(self):
        """Custom weight should be respected."""
        q = SwaptionQuote(expiry_years=1.0, swap_tenor_years=5.0, normal_vol_bps=42.0, weight=0.5)
        assert q.weight == 0.5

    def test_zero_weight_excluded(self):
        """Zero weight should exclude quote from calibration."""
        q = SwaptionQuote(expiry_years=1.0, swap_tenor_years=5.0, normal_vol_bps=42.0, weight=0.0)
        assert q.weight == 0.0


class TestHullWhiteCalibrationInputs:
    """Tests for HullWhiteCalibrationInputs dataclass."""

    def test_default_bounds(self, sample_spot_curve, sample_swaption_quotes):
        """Default optimizer bounds should be set."""
        inputs = HullWhiteCalibrationInputs(
            calibration_date=date(2026, 5, 23),
            initial_short_rate=0.022,
            spot_curve=sample_spot_curve,
            swaption_quotes=sample_swaption_quotes,
        )
        assert inputs.optimizer_bounds["a"] == (0.001, 1.0)
        assert inputs.optimizer_bounds["sigma_r"] == (0.001, 0.10)

    def test_regulatory_rate_cap_default(self, sample_spot_curve, sample_swaption_quotes):
        """Default CBIRC cap should be 3.0%."""
        inputs = HullWhiteCalibrationInputs(
            calibration_date=date(2026, 5, 23),
            initial_short_rate=0.022,
            spot_curve=sample_spot_curve,
            swaption_quotes=sample_swaption_quotes,
        )
        assert inputs.regulatory_rate_cap == 0.03


class TestHullWhiteCalibrator:
    """Tests for HullWhiteCalibrator class (VR-C01, VR-C02, VR-C03)."""

    def test_input_validation_rate_cap_warning(self, sample_spot_curve, sample_swaption_quotes):
        """VR-C01: Should warn when r(0) exceeds CBIRC cap."""
        inputs = HullWhiteCalibrationInputs(
            calibration_date=date(2026, 5, 23),
            initial_short_rate=0.035,  # exceeds 3.0% cap
            spot_curve=sample_spot_curve,
            swaption_quotes=sample_swaption_quotes,
            regulatory_rate_cap=0.03,
        )
        with pytest.warns(UserWarning, match="CBIRC regulatory cap"):
            HullWhiteCalibrator(inputs)

    def test_input_validation_few_quotes_warning(self, sample_spot_curve):
        """VR-C01: Should warn when fewer than 3 swaption quotes."""
        inputs = HullWhiteCalibrationInputs(
            calibration_date=date(2026, 5, 23),
            initial_short_rate=0.022,
            spot_curve=sample_spot_curve,
            swaption_quotes=[
                SwaptionQuote(expiry_years=1.0, swap_tenor_years=5.0, normal_vol_bps=42.0),
                SwaptionQuote(expiry_years=5.0, swap_tenor_years=5.0, normal_vol_bps=38.0),
            ],
        )
        with pytest.warns(UserWarning, match="Minimum 3 quotes"):
            HullWhiteCalibrator(inputs)

    def test_input_validation_spot_curve_too_short(self, sample_swaption_quotes):
        """VR-C01: Should raise when spot curve has < 2 points."""
        inputs = HullWhiteCalibrationInputs(
            calibration_date=date(2026, 5, 23),
            initial_short_rate=0.022,
            spot_curve=pd.Series([0.02], index=[1.0]),
            swaption_quotes=sample_swaption_quotes,
        )
        with pytest.raises(ValueError, match="at least 2 tenor points"):
            HullWhiteCalibrator(inputs)

    def test_calibrate_returns_result(self, hw_calibration_inputs):
        """VR-C02: calibrate() should return CalibrationResult."""
        calibrator = HullWhiteCalibrator(hw_calibration_inputs)
        result = calibrator.calibrate()
        assert isinstance(result, CalibrationResult)

    def test_calibrate_not_placeholder(self, hw_calibration_inputs):
        """VR-C02: calibrate() should set is_placeholder=False."""
        calibrator = HullWhiteCalibrator(hw_calibration_inputs)
        result = calibrator.calibrate()
        assert result.is_placeholder is False

    def test_calibrate_a_in_bounds(self, hw_calibration_inputs):
        """VR-C02: Calibrated a should be within optimizer bounds."""
        calibrator = HullWhiteCalibrator(hw_calibration_inputs)
        result = calibrator.calibrate()
        bounds = hw_calibration_inputs.optimizer_bounds["a"]
        assert bounds[0] <= result.a <= bounds[1]

    def test_calibrate_sigma_r_in_bounds(self, hw_calibration_inputs):
        """VR-C02: Calibrated σ_r should be within optimizer bounds."""
        calibrator = HullWhiteCalibrator(hw_calibration_inputs)
        result = calibrator.calibrate()
        bounds = hw_calibration_inputs.optimizer_bounds["sigma_r"]
        assert bounds[0] <= result.sigma_r <= bounds[1]

    def test_calibrate_r0_preserved(self, hw_calibration_inputs):
        """VR-C02: r0 should match input initial_short_rate."""
        calibrator = HullWhiteCalibrator(hw_calibration_inputs)
        result = calibrator.calibrate()
        assert result.r0 == hw_calibration_inputs.initial_short_rate

    def test_calibrate_fit_table_present(self, hw_calibration_inputs):
        """VR-C03: Goodness-of-fit table should be populated."""
        calibrator = HullWhiteCalibrator(hw_calibration_inputs)
        result = calibrator.calibrate()
        assert result.swaption_fit_table is not None
        assert isinstance(result.swaption_fit_table, pd.DataFrame)
        assert len(result.swaption_fit_table) == len(hw_calibration_inputs.swaption_quotes)

    def test_calibrate_rmse_present(self, hw_calibration_inputs):
        """VR-C03: RMSE should be computed."""
        calibrator = HullWhiteCalibrator(hw_calibration_inputs)
        result = calibrator.calibrate()
        assert result.swaption_rmse_bps is not None
        assert result.swaption_rmse_bps >= 0

    def test_goodness_of_fit_table_columns(self, hw_calibration_inputs):
        """VR-C03: Fit table should have required columns."""
        calibrator = HullWhiteCalibrator(hw_calibration_inputs)
        df = calibrator.goodness_of_fit_table(a=0.10, sigma_r=0.012)
        required_cols = ["expiry_years", "swap_tenor_years", "market_vol_bps", "model_vol_bps", "error_bps"]
        for col in required_cols:
            assert col in df.columns

    def test_loss_function_positive(self, hw_calibration_inputs):
        """Loss function should return non-negative value."""
        calibrator = HullWhiteCalibrator(hw_calibration_inputs)
        loss = calibrator.loss([0.10, 0.012])
        assert loss >= 0

    def test_loss_function_infeasible_params(self, hw_calibration_inputs):
        """Loss function should return large value for infeasible params."""
        calibrator = HullWhiteCalibrator(hw_calibration_inputs)
        loss = calibrator.loss([-0.01, 0.012])  # negative a
        assert loss >= 1e10


class TestGBMCalibrationInputs:
    """Tests for GBMCalibrationInputs dataclass."""

    def test_default_implied_vol_weight(
        self, sample_equity_returns, sample_rf_returns, sample_dividend_yield
    ):
        """Default implied vol weight should be 60%."""
        inputs = GBMCalibrationInputs(
            calibration_date=date(2026, 5, 23),
            equity_returns=sample_equity_returns,
            rf_returns=sample_rf_returns,
            dividend_yield_monthly=sample_dividend_yield,
        )
        assert inputs.implied_vol_weight == 0.60

    def test_default_erp_adjustment(
        self, sample_equity_returns, sample_rf_returns, sample_dividend_yield
    ):
        """Default ERP survivorship adjustment should be 0.7%."""
        inputs = GBMCalibrationInputs(
            calibration_date=date(2026, 5, 23),
            equity_returns=sample_equity_returns,
            rf_returns=sample_rf_returns,
            dividend_yield_monthly=sample_dividend_yield,
        )
        assert inputs.erp_survivorship_adjustment == 0.007


class TestGBMCalibrator:
    """Tests for GBMCalibrator class (VR-C04, VR-C05, VR-C06)."""

    def test_input_validation_short_history_warning(
        self, sample_rf_returns, sample_dividend_yield
    ):
        """VR-C04: Should warn when equity return history < 5 years."""
        short_returns = pd.Series(
            np.random.normal(0, 0.01, 500),
            index=pd.date_range("2024-01-01", periods=500, freq="B"),
        )
        short_rf = pd.Series(
            np.full(500, 0.025),
            index=pd.date_range("2024-01-01", periods=500, freq="B"),
        )
        inputs = GBMCalibrationInputs(
            calibration_date=date(2026, 5, 23),
            equity_returns=short_returns,
            rf_returns=short_rf,
            dividend_yield_monthly=sample_dividend_yield,
        )
        with pytest.warns(UserWarning, match="Minimum.*5 years"):
            GBMCalibrator(inputs)

    def test_input_validation_length_mismatch(
        self, sample_equity_returns, sample_dividend_yield
    ):
        """VR-C04: Should raise when equity/rf series lengths differ."""
        short_rf = pd.Series(
            np.full(500, 0.025),
            index=pd.date_range("2024-01-01", periods=500, freq="B"),
        )
        inputs = GBMCalibrationInputs(
            calibration_date=date(2026, 5, 23),
            equity_returns=sample_equity_returns,
            rf_returns=short_rf,
            dividend_yield_monthly=sample_dividend_yield,
        )
        with pytest.raises(ValueError, match="same length"):
            GBMCalibrator(inputs)

    def test_calibrate_returns_result(self, gbm_calibration_inputs):
        """VR-C05: calibrate() should return CalibrationResult."""
        calibrator = GBMCalibrator(gbm_calibration_inputs)
        result = calibrator.calibrate()
        assert isinstance(result, CalibrationResult)

    def test_calibrate_not_placeholder(self, gbm_calibration_inputs):
        """VR-C05: calibrate() should set is_placeholder=False."""
        calibrator = GBMCalibrator(gbm_calibration_inputs)
        result = calibrator.calibrate()
        assert result.is_placeholder is False

    def test_calibrate_sigma_s_reasonable(self, gbm_calibration_inputs):
        """VR-C05: Calibrated σ_S should be in reasonable range."""
        calibrator = GBMCalibrator(gbm_calibration_inputs)
        result = calibrator.calibrate()
        assert 0.10 <= result.sigma_S <= 0.50

    def test_calibrate_erp_bounded(self, gbm_calibration_inputs):
        """VR-C05: Calibrated ERP should respect upper bound."""
        calibrator = GBMCalibrator(gbm_calibration_inputs)
        result = calibrator.calibrate()
        assert 0 <= result.erp <= gbm_calibration_inputs.erp_upper_bound

    def test_calibrate_rho_reasonable(self, gbm_calibration_inputs):
        """VR-C05: Rate-equity correlation should be in [-1, 1]."""
        calibrator = GBMCalibrator(gbm_calibration_inputs)
        result = calibrator.calibrate()
        assert -1.0 <= result.rho <= 1.0

    def test_calibrate_blended_vol_with_implied(self, gbm_calibration_inputs):
        """VR-C05: With implied vol, should use blended estimate."""
        calibrator = GBMCalibrator(gbm_calibration_inputs)
        result = calibrator.calibrate()
        assert result.equity_vol_implied is not None
        assert "blended" in result.notes

    def test_calibrate_historical_only_when_no_implied(
        self, sample_equity_returns, sample_rf_returns, sample_dividend_yield
    ):
        """VR-C05: Without implied vol, should fall back to historical."""
        inputs = GBMCalibrationInputs(
            calibration_date=date(2026, 5, 23),
            equity_returns=sample_equity_returns,
            rf_returns=sample_rf_returns,
            dividend_yield_monthly=sample_dividend_yield,
            implied_vol_atm=np.nan,  # unavailable
        )
        calibrator = GBMCalibrator(inputs)
        result = calibrator.calibrate()
        assert result.equity_vol_implied is None
        assert "historical-only" in result.notes

    def test_compute_historical_volatility(self, gbm_calibration_inputs):
        """VR-C06: Historical vol should be annualised correctly."""
        calibrator = GBMCalibrator(gbm_calibration_inputs)
        vol = calibrator.compute_historical_volatility()
        assert 0.10 <= vol <= 0.40

    def test_compute_dividend_yield(self, gbm_calibration_inputs):
        """VR-C06: Dividend yield should be reasonable."""
        calibrator = GBMCalibrator(gbm_calibration_inputs)
        dy = calibrator.compute_dividend_yield()
        assert 0.01 <= dy <= 0.05

    def test_compute_rate_equity_correlation(self, gbm_calibration_inputs):
        """VR-C06: Rate-equity correlation should be in valid range."""
        calibrator = GBMCalibrator(gbm_calibration_inputs)
        rho = calibrator.compute_rate_equity_correlation()
        assert -1.0 <= rho <= 1.0


class TestCalibrationResult:
    """Tests for CalibrationResult dataclass (VR-C07)."""

    def test_summary_string(self):
        """VR-C07: summary() should return formatted string."""
        result = CalibrationResult(calibration_date=date(2026, 5, 23))
        summary = result.summary()
        assert "Calibration Result" in summary
        assert "Hull-White" in summary
        assert "GBM" in summary

    def test_to_hw_params_dict(self):
        """VR-C07: to_hw_params_dict() should return correct keys."""
        result = CalibrationResult(
            calibration_date=date(2026, 5, 23),
            a=0.15,
            sigma_r=0.010,
            lambda_r=0.0,
            r0=0.022,
        )
        hw_dict = result.to_hw_params_dict()
        assert hw_dict["a"] == 0.15
        assert hw_dict["sigma_r"] == 0.010
        assert hw_dict["lambda_r"] == 0.0
        assert hw_dict["r0"] == 0.022

    def test_to_gbm_params_dict(self):
        """VR-C07: to_gbm_params_dict() should return correct keys."""
        result = CalibrationResult(
            calibration_date=date(2026, 5, 23),
            sigma_S=0.22,
            erp=0.045,
            dividend_yield=0.025,
            rho=-0.15,
        )
        gbm_dict = result.to_gbm_params_dict()
        assert gbm_dict["sigma_S"] == 0.22
        assert gbm_dict["erp"] == 0.045
        assert gbm_dict["delta"] == 0.025
        assert gbm_dict["rho"] == -0.15

    def test_placeholder_default_true(self):
        """VR-C07: Default is_placeholder should be True."""
        result = CalibrationResult(calibration_date=date(2026, 5, 23))
        assert result.is_placeholder is True


class TestMartingaleTest:
    """Tests for martingale_test() function (VR-C08, VR-C09, VR-C10)."""

    def test_p_measure_rejection(self):
        """VR-C09: Should reject P-measure scenarios."""
        scenario_set = ScenarioSet.generate(
            n=100, T_months=24, measure=Measure.P, seed=42
        )
        with pytest.raises(ValueError, match="Q-measure"):
            martingale_test(scenario_set)

    def test_q_measure_accepted(self):
        """VR-C08: Should accept Q-measure scenarios."""
        scenario_set = ScenarioSet.generate(
            n=500, T_months=24, measure=Measure.Q, seed=42
        )
        result = martingale_test(scenario_set, horizons_years=(1.0, 2.0))
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 2

    def test_returns_dataframe_with_required_columns(self):
        """VR-C08: Result should have required columns."""
        scenario_set = ScenarioSet.generate(
            n=500, T_months=24, measure=Measure.Q, seed=42
        )
        result = martingale_test(scenario_set, horizons_years=(1.0,))
        required_cols = ["horizon_years", "expected_discounted_value", "initial_price", "relative_error", "pass"]
        for col in required_cols:
            assert col in result.columns

    def test_horizon_exceeds_scenario_length(self):
        """VR-C08: Should handle horizons exceeding scenario length."""
        scenario_set = ScenarioSet.generate(
            n=500, T_months=12, measure=Measure.Q, seed=42
        )
        result = martingale_test(scenario_set, horizons_years=(1.0, 5.0))
        assert len(result) == 2
        assert result[result["horizon_years"] == 5.0]["pass"].values[0] == False

    def test_tolerance_attribute(self):
        """VR-C08: Tolerance should be recorded in DataFrame attrs."""
        scenario_set = ScenarioSet.generate(
            n=500, T_months=24, measure=Measure.Q, seed=42
        )
        result = martingale_test(scenario_set, horizons_years=(1.0,), tolerance=0.02)
        assert result.attrs["tolerance"] == 0.02

    def test_n_scenarios_attribute(self):
        """VR-C08: n_scenarios should be recorded in DataFrame attrs."""
        scenario_set = ScenarioSet.generate(
            n=500, T_months=24, measure=Measure.Q, seed=42
        )
        result = martingale_test(scenario_set, horizons_years=(1.0,))
        assert result.attrs["n_scenarios"] == 500

    def test_all_pass_attribute_true(self):
        """VR-C08: all_pass should be True when all horizons pass."""
        scenario_set = ScenarioSet.generate(
            n=1000, T_months=24, measure=Measure.Q, seed=42
        )
        result = martingale_test(scenario_set, horizons_years=(1.0,), tolerance=0.10)
        if result["pass"].all():
            assert result.attrs["all_pass"] is True

    def test_custom_initial_price(self):
        """VR-C08: Custom initial_equity_price should be used."""
        scenario_set = ScenarioSet.generate(
            n=500, T_months=24, measure=Measure.Q, seed=42
        )
        result = martingale_test(scenario_set, horizons_years=(1.0,), initial_equity_price=200.0)
        assert result["initial_price"].values[0] == 200.0

    def test_integration_with_scenario_set(self):
        """VR-C10: Should integrate correctly with ScenarioSet.generate()."""
        scenario_set = ScenarioSet.generate(
            n=500, T_months=60, measure=Measure.Q, seed=123
        )
        result = martingale_test(
            scenario_set,
            horizons_years=(1.0, 2.0, 3.0, 5.0),
            tolerance=0.05,
        )
        assert len(result) == 4
        assert "all_pass" in result.attrs


class TestHWCalibrationConvergence:
    """Tests for HW1F calibration convergence behavior."""

    def test_calibration_improves_loss(self, hw_calibration_inputs):
        """Calibrated params should have lower loss than placeholders."""
        calibrator = HullWhiteCalibrator(hw_calibration_inputs)
        
        loss_placeholder = calibrator.loss([0.10, 0.012])
        result = calibrator.calibrate()
        loss_calibrated = calibrator.loss([result.a, result.sigma_r])
        
        assert loss_calibrated <= loss_placeholder

    def test_calibration_reproducible(self, hw_calibration_inputs):
        """Calibration should be reproducible."""
        cal1 = HullWhiteCalibrator(hw_calibration_inputs)
        cal2 = HullWhiteCalibrator(hw_calibration_inputs)
        
        result1 = cal1.calibrate()
        result2 = cal2.calibrate()
        
        assert abs(result1.a - result2.a) < 1e-6
        assert abs(result1.sigma_r - result2.sigma_r) < 1e-6


class TestGBMCalibrationEdgeCases:
    """Tests for GBM calibration edge cases."""

    def test_erp_capped_at_upper_bound(
        self, sample_rf_returns, sample_dividend_yield
    ):
        """ERP should be capped at upper bound even with high returns."""
        np.random.seed(99)
        n_days = 252 * 5
        dates = pd.date_range(start="2021-01-01", periods=n_days, freq="B")
        high_returns = np.random.normal(0.003, 0.02, n_days)
        high_eq_returns = pd.Series(high_returns, index=dates)
        
        rf_returns = pd.Series(np.full(n_days, 0.02), index=dates)
        
        inputs = GBMCalibrationInputs(
            calibration_date=date(2026, 5, 23),
            equity_returns=high_eq_returns,
            rf_returns=rf_returns,
            dividend_yield_monthly=sample_dividend_yield,
            erp_upper_bound=0.05,
        )
        calibrator = GBMCalibrator(inputs)
        result = calibrator.calibrate()
        
        assert result.erp <= 0.05

    def test_erp_floored_at_zero(
        self, sample_rf_returns, sample_dividend_yield
    ):
        """ERP should be floored at zero even with negative returns."""
        np.random.seed(98)
        n_days = 252 * 5
        dates = pd.date_range(start="2021-01-01", periods=n_days, freq="B")
        low_returns = np.random.normal(-0.002, 0.02, n_days)
        low_eq_returns = pd.Series(low_returns, index=dates)
        
        rf_returns = pd.Series(np.full(n_days, 0.03), index=dates)
        
        inputs = GBMCalibrationInputs(
            calibration_date=date(2026, 5, 23),
            equity_returns=low_eq_returns,
            rf_returns=rf_returns,
            dividend_yield_monthly=sample_dividend_yield,
        )
        calibrator = GBMCalibrator(inputs)
        result = calibrator.calibrate()
        
        assert result.erp >= 0


class TestCalibrationDocumentation:
    """Tests verifying calibration documentation compliance."""

    def test_hw_result_has_notes(self, hw_calibration_inputs):
        """HW calibration result should have notes."""
        calibrator = HullWhiteCalibrator(hw_calibration_inputs)
        result = calibrator.calibrate()
        assert len(result.notes) > 0

    def test_gbm_result_has_notes(self, gbm_calibration_inputs):
        """GBM calibration result should have notes."""
        calibrator = GBMCalibrator(gbm_calibration_inputs)
        result = calibrator.calibrate()
        assert len(result.notes) > 0
        assert "sigma_S=" in result.notes
        assert "ERP=" in result.notes

    def test_calibration_date_preserved(self, hw_calibration_inputs):
        """Calibration date should be preserved in result."""
        calibrator = HullWhiteCalibrator(hw_calibration_inputs)
        result = calibrator.calibrate()
        assert result.calibration_date == hw_calibration_inputs.calibration_date


# =============================================================================
# Run configuration
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
