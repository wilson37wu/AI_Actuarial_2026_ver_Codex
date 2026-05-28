"""
Unit tests for par_model_v2.risk.risk_metrics
=============================================

Tests cover:
  1. ConfidenceLevel enum properties
  2. LossDistribution construction (from_array, from_scenario_pv, from_deterministic_stress)
  3. Empirical VaR correctness (known Normal, verified against scipy)
  4. Empirical ES correctness (analytical cross-check)
  5. Parametric (Normal) VaR and ES (closed-form analytical check)
  6. Empirical vs Parametric comparison (both_methods_comparison)
  7. Reliability flags (unreliable when n < threshold)
  8. Stress test report structure and monotonicity
  9. Measure='Q' triggers UserWarning
  10. RiskReport.to_dataframe() shape and columns
  11. Full report (full_report) with both methods

SOA Reference: ASOP 56 §3.5 (adequacy), ASOP 7 §3.3 (tail metrics).
"""

from __future__ import annotations

import warnings
import numpy as np
import pandas as pd
import pytest
from scipy import stats as scipy_stats

from par_model_v2.risk.risk_metrics import (
    ALL_CONFIDENCE_LEVELS,
    ConfidenceLevel,
    ESResult,
    LossDistribution,
    RiskMetrics,
    RiskReport,
    VaRResult,
    _empirical_es,
    _empirical_var,
    _parametric_es,
    _parametric_var,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

RNG_SEED = 42
N_LARGE = 10_000   # Large enough for reliable 99.5% estimates
N_SMALL = 100      # Small enough to trigger reliability warnings


@pytest.fixture
def normal_losses_large():
    """N(50_000, 20_000) loss distribution, n=10_000."""
    rng = np.random.default_rng(RNG_SEED)
    return rng.normal(loc=50_000, scale=20_000, size=N_LARGE)


@pytest.fixture
def normal_losses_small():
    """N(50_000, 20_000) loss distribution, n=100 (below all thresholds)."""
    rng = np.random.default_rng(RNG_SEED)
    return rng.normal(loc=50_000, scale=20_000, size=N_SMALL)


@pytest.fixture
def ldf_large(normal_losses_large):
    return LossDistribution.from_array(
        normal_losses_large, label="Large test dist", measure="P"
    )


@pytest.fixture
def ldf_small(normal_losses_small):
    return LossDistribution.from_array(
        normal_losses_small, label="Small test dist", measure="P"
    )


@pytest.fixture
def rm_large(ldf_large):
    return RiskMetrics(ldf_large)


@pytest.fixture
def rm_small(ldf_small):
    return RiskMetrics(ldf_small)


# ---------------------------------------------------------------------------
# 1. ConfidenceLevel enum
# ---------------------------------------------------------------------------

class TestConfidenceLevel:
    def test_values(self):
        assert ConfidenceLevel.CL_95.value == pytest.approx(0.95)
        assert ConfidenceLevel.CL_99.value == pytest.approx(0.99)
        assert ConfidenceLevel.CL_995.value == pytest.approx(0.995)

    def test_labels(self):
        assert ConfidenceLevel.CL_95.label == "95.0%"
        assert ConfidenceLevel.CL_99.label == "99.0%"
        assert ConfidenceLevel.CL_995.label == "99.5%"

    def test_min_scenarios_ordering(self):
        assert (
            ConfidenceLevel.CL_95.min_scenarios
            < ConfidenceLevel.CL_99.min_scenarios
            < ConfidenceLevel.CL_995.min_scenarios
        )

    def test_recommended_ge_min(self):
        for cl in ALL_CONFIDENCE_LEVELS:
            assert cl.recommended_scenarios >= cl.min_scenarios

    def test_all_confidence_levels_count(self):
        assert len(ALL_CONFIDENCE_LEVELS) == 3


# ---------------------------------------------------------------------------
# 2. LossDistribution construction
# ---------------------------------------------------------------------------

class TestLossDistributionConstruction:
    def test_from_array_basic(self, normal_losses_large):
        ldf = LossDistribution.from_array(normal_losses_large, label="test", measure="P")
        assert ldf.n_scenarios == N_LARGE
        assert ldf.measure == "P"

    def test_from_array_shape_check(self):
        with pytest.raises(ValueError, match="1-D"):
            LossDistribution(losses=np.ones((10, 10)), label="bad")

    def test_from_array_measure_check(self):
        with pytest.raises(ValueError, match="measure"):
            LossDistribution.from_array([1, 2, 3], label="test", measure="X")

    def test_q_measure_warning(self):
        with pytest.warns(UserWarning, match="Q-measure"):
            LossDistribution.from_array([1, 2, 3], label="test", measure="Q")

    def test_risk_metrics_rejects_q_measure(self):
        with pytest.warns(UserWarning, match="Q-measure"):
            q_ldf = LossDistribution.from_array([1, 2, 3], label="test", measure="Q")
        with pytest.raises(ValueError, match="measure='P'"):
            RiskMetrics(q_ldf)

    def test_from_scenario_pv(self):
        df = pd.DataFrame({
            "asset_pv":     [100_000, 95_000, 80_000, 110_000],
            "liability_pv": [90_000, 100_000, 95_000,  85_000],
        })
        ldf = LossDistribution.from_scenario_pv(df)
        expected_losses = np.array([-10_000, 5_000, 15_000, -25_000])
        np.testing.assert_allclose(ldf.losses, expected_losses)

    def test_from_scenario_pv_missing_column(self):
        df = pd.DataFrame({"asset_pv": [1, 2, 3]})
        with pytest.raises(KeyError, match="liability_pv"):
            LossDistribution.from_scenario_pv(df)

    def test_from_deterministic_stress(self):
        ldf = LossDistribution.from_deterministic_stress(
            base_pv=100_000,
            shocked_pvs=[80_000, 70_000, 95_000],
        )
        expected = np.array([20_000, 30_000, 5_000])
        np.testing.assert_allclose(ldf.losses, expected)
        assert ldf.measure == "P"

    def test_summary_stats_keys(self, ldf_large):
        stats = ldf_large.summary_stats
        for key in ["mean_loss", "std_loss", "p95_loss", "p99_loss", "p995_loss", "skewness"]:
            assert key in stats.index

    def test_summary_stats_n_scenarios(self, ldf_large):
        assert ldf_large.summary_stats["n_scenarios"] == N_LARGE


# ---------------------------------------------------------------------------
# 3. Empirical VaR — correctness
# ---------------------------------------------------------------------------

class TestEmpiricalVaR:
    def test_var_vs_numpy_percentile(self, normal_losses_large):
        """Empirical VaR must match numpy.percentile exactly."""
        for cl in ALL_CONFIDENCE_LEVELS:
            expected = np.percentile(normal_losses_large, cl.value * 100)
            result = _empirical_var(np.sort(normal_losses_large), cl.value)
            assert result == pytest.approx(expected, rel=1e-10)

    def test_var_ordering(self, rm_large):
        """VaR must be monotone in confidence level."""
        var_95 = rm_large.empirical_var(ConfidenceLevel.CL_95).var_value
        var_99 = rm_large.empirical_var(ConfidenceLevel.CL_99).var_value
        var_995 = rm_large.empirical_var(ConfidenceLevel.CL_995).var_value
        assert var_95 <= var_99 <= var_995

    def test_var_result_method(self, rm_large):
        result = rm_large.empirical_var(ConfidenceLevel.CL_99)
        assert result.method == "empirical"
        assert result.scenario_count == N_LARGE

    def test_var_reliable_large(self, rm_large):
        for cl in ALL_CONFIDENCE_LEVELS:
            assert rm_large.empirical_var(cl).is_reliable

    def test_var_unreliable_small(self, rm_small):
        # n=100 is below all minimum thresholds
        for cl in ALL_CONFIDENCE_LEVELS:
            assert not rm_small.empirical_var(cl).is_reliable
            assert rm_small.empirical_var(cl).reliability_warning != ""

    def test_var_approximate_normal(self, normal_losses_large):
        """For large N~Normal(50k,20k), empirical VaR_99.5 ≈ analytical Normal VaR."""
        mean, std = 50_000.0, 20_000.0
        analytical = mean + scipy_stats.norm.ppf(0.995) * std
        empirical = _empirical_var(np.sort(normal_losses_large), 0.995)
        # Allow 1% relative tolerance (sampling error for n=10,000)
        assert abs(empirical - analytical) / analytical < 0.01


# ---------------------------------------------------------------------------
# 4. Empirical ES — correctness
# ---------------------------------------------------------------------------

class TestEmpiricalES:
    def test_es_ge_var(self, rm_large):
        """ES must be >= VaR at same confidence level."""
        for cl in ALL_CONFIDENCE_LEVELS:
            var_r = rm_large.empirical_var(cl)
            es_r = rm_large.empirical_es(cl)
            assert es_r.es_value >= var_r.var_value

    def test_es_ordering(self, rm_large):
        """ES must be monotone in confidence level."""
        es_95 = rm_large.empirical_es(ConfidenceLevel.CL_95).es_value
        es_99 = rm_large.empirical_es(ConfidenceLevel.CL_99).es_value
        es_995 = rm_large.empirical_es(ConfidenceLevel.CL_995).es_value
        assert es_95 <= es_99 <= es_995

    def test_es_tail_count_positive(self, rm_large):
        for cl in ALL_CONFIDENCE_LEVELS:
            assert rm_large.empirical_es(cl).tail_count > 0

    def test_es_reliable_large(self, rm_large):
        for cl in ALL_CONFIDENCE_LEVELS:
            assert rm_large.empirical_es(cl).is_reliable

    def test_es_unreliable_small(self, rm_small):
        # n=100 → tail count at 99.5% is only ~0.5 scenarios → unreliable
        result = rm_small.empirical_es(ConfidenceLevel.CL_995)
        assert not result.is_reliable

    def test_es_approximate_normal(self, normal_losses_large):
        """For large N~Normal(50k,20k), empirical ES_99.5 ≈ parametric ES."""
        mean, std = float(np.mean(normal_losses_large)), float(np.std(normal_losses_large, ddof=1))
        alpha = 0.995
        par_es, _ = _parametric_es(mean, std, alpha)
        emp_es, _, _ = _empirical_es(np.sort(normal_losses_large), alpha)
        # Allow 2% relative tolerance
        assert abs(emp_es - par_es) / abs(par_es) < 0.02


# ---------------------------------------------------------------------------
# 5. Parametric (Normal) VaR and ES
# ---------------------------------------------------------------------------

class TestParametricVaR:
    def test_parametric_var_formula(self):
        mean, std, alpha = 50_000.0, 20_000.0, 0.99
        expected = mean + scipy_stats.norm.ppf(alpha) * std
        result = _parametric_var(mean, std, alpha)
        assert result == pytest.approx(expected, rel=1e-12)

    def test_parametric_es_formula(self):
        mean, std, alpha = 50_000.0, 20_000.0, 0.99
        z = scipy_stats.norm.ppf(alpha)
        expected_es = mean + std * scipy_stats.norm.pdf(z) / (1 - alpha)
        result_es, _ = _parametric_es(mean, std, alpha)
        assert result_es == pytest.approx(expected_es, rel=1e-12)

    def test_parametric_var_method_label(self, rm_large):
        result = rm_large.parametric_var(ConfidenceLevel.CL_99)
        assert result.method == "parametric_normal"

    def test_parametric_es_ge_var(self, rm_large):
        for cl in ALL_CONFIDENCE_LEVELS:
            par_es = rm_large.parametric_es(cl)
            assert par_es.es_value >= par_es.var_value


# ---------------------------------------------------------------------------
# 6. Comparison: empirical vs parametric
# ---------------------------------------------------------------------------

class TestMethodsComparison:
    def test_both_methods_dataframe_columns(self, rm_large):
        df = rm_large.both_methods_comparison()
        for col in ["confidence_level", "metric", "empirical", "parametric_normal",
                    "divergence_pct", "normal_adequate"]:
            assert col in df.columns

    def test_both_methods_rows(self, rm_large):
        df = rm_large.both_methods_comparison()
        # 3 confidence levels × 2 metrics = 6 rows
        assert len(df) == 6

    def test_normal_adequate_for_normal_dist(self, rm_large):
        """For true Normal input with large n, Normal approx should be adequate."""
        df = rm_large.both_methods_comparison()
        # At 95% and 99% should be adequate (divergence < 20%)
        for cl_label in ["95.0%", "99.0%"]:
            rows = df[df["confidence_level"] == cl_label]
            assert rows["normal_adequate"].all(), (
                f"Normal approximation unexpectedly inadequate at {cl_label}"
            )


# ---------------------------------------------------------------------------
# 7. Stress test report
# ---------------------------------------------------------------------------

class TestStressTestReport:
    def test_stress_report_baseline_row(self, rm_large):
        df = rm_large.stress_test_report({"Shock +5k": 5_000})
        baseline = df[df["scenario"] == "Base (no stress)"].iloc[0]
        assert baseline["var_change"] == pytest.approx(0.0)
        assert baseline["es_change"] == pytest.approx(0.0)

    def test_stress_report_monotone(self, rm_large):
        """Larger additive shock must produce larger VaR and ES."""
        df = rm_large.stress_test_report({
            "Small shock": 1_000,
            "Large shock": 20_000,
        })
        var_col = "var_99.5%"
        small_var = df[df["scenario"] == "Small shock"][var_col].iloc[0]
        large_var = df[df["scenario"] == "Large shock"][var_col].iloc[0]
        assert large_var > small_var

    def test_stress_report_includes_all_scenarios(self, rm_large):
        shocks = {"S1": 1_000, "S2": 5_000, "S3": 10_000}
        df = rm_large.stress_test_report(shocks)
        assert len(df) == 1 + len(shocks)  # baseline + 3 shocked

    def test_stress_report_pct_change_direction(self, rm_large):
        """Positive shock (losses worsen) should give positive pct change in VaR."""
        df = rm_large.stress_test_report({"Adverse": 10_000})
        adverse = df[df["scenario"] == "Adverse"].iloc[0]
        assert adverse["var_pct_change"] > 0


# ---------------------------------------------------------------------------
# 8. RiskReport
# ---------------------------------------------------------------------------

class TestRiskReport:
    def test_full_report_empirical(self, rm_large):
        report = rm_large.full_report(method="empirical")
        assert isinstance(report, RiskReport)
        assert len(report.var_results) == 3
        assert len(report.es_results) == 3

    def test_full_report_parametric(self, rm_large):
        report = rm_large.full_report(method="parametric_normal")
        for cl in ALL_CONFIDENCE_LEVELS:
            assert report.var_results[cl].method == "parametric_normal"

    def test_full_report_invalid_method(self, rm_large):
        with pytest.raises(ValueError, match="method"):
            rm_large.full_report(method="bootstrap")

    def test_to_dataframe_shape(self, rm_large):
        df = rm_large.full_report().to_dataframe()
        assert len(df) == 6  # 3 CL × 2 metrics
        for col in ["metric", "confidence_level", "value", "is_reliable"]:
            assert col in df.columns

    def test_report_has_measure_note(self, rm_large):
        report = rm_large.full_report()
        assert "Measure.P" in report.measure_note or "real-world" in report.measure_note

    def test_print_summary_runs_without_error(self, rm_large, capsys):
        report = rm_large.full_report()
        report.print_summary()
        captured = capsys.readouterr()
        assert "VaR" in captured.out
        assert "ES" in captured.out


# ---------------------------------------------------------------------------
# 9. VaRResult and ESResult as_dict
# ---------------------------------------------------------------------------

class TestResultDicts:
    def test_var_result_dict_keys(self, rm_large):
        result = rm_large.empirical_var(ConfidenceLevel.CL_99)
        d = result.as_dict()
        for key in ["metric", "confidence_level", "value", "method",
                    "n_scenarios", "is_reliable"]:
            assert key in d

    def test_es_result_dict_keys(self, rm_large):
        result = rm_large.empirical_es(ConfidenceLevel.CL_99)
        d = result.as_dict()
        for key in ["metric", "confidence_level", "value", "var_threshold",
                    "tail_scenarios", "method", "n_scenarios", "is_reliable"]:
            assert key in d
