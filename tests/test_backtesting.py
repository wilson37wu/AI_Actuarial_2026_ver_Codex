"""
Unit tests - calibration backtesting framework.

Coverage:
- VR-BT01: synthetic dataset generation
- VR-BT02: dataset validation
- VR-BT03: loss proxy monotonicity
- VR-BT04: Kupiec POF helper
- VR-BT05: backtest historical replay outputs
- VR-BT06: governance integration
- VR-BT07: recalibration flag on extreme breaches
"""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
import pytest

from par_model_v2.calibration import (
    BACKTEST_HORIZON_MONTHS,
    BacktestDataset,
    BacktestEngine,
    BacktestReport,
    generate_backtest_report,
)
from par_model_v2.calibration.backtesting import (
    _kupiec_pof_pvalue,
    _loss_from_market_outcome,
)
from par_model_v2.calibration.calibration_framework import CalibrationResult
from par_model_v2.governance.audit_trail import GovernanceStore
from par_model_v2.risk.risk_metrics import ConfidenceLevel


@pytest.fixture
def calibration_result() -> CalibrationResult:
    return CalibrationResult(
        calibration_date=date(2026, 5, 23),
        a=0.12,
        sigma_r=0.010,
        lambda_r=0.001,
        r0=0.024,
        sigma_S=0.18,
        erp=0.040,
        dividend_yield=0.022,
        rho=-0.20,
        notes="Test calibration",
        is_placeholder=False,
    )


class TestBacktestDataset:
    def test_vr_bt01_synthetic_dataset_has_required_schema(self, calibration_result):
        dataset = BacktestDataset.synthetic(calibration_result, n_observations=5, seed=7)
        assert dataset.horizon_months == BACKTEST_HORIZON_MONTHS
        assert dataset.n_observations == 5
        assert list(dataset.observations.columns) == [
            "observation_date",
            "initial_short_rate",
            "initial_equity_index",
            "realised_rate_1y",
            "realised_equity_return_1y",
            "realised_loss",
        ]

    def test_vr_bt01_synthetic_dataset_is_reproducible(self, calibration_result):
        lhs = BacktestDataset.synthetic(calibration_result, n_observations=4, seed=9)
        rhs = BacktestDataset.synthetic(calibration_result, n_observations=4, seed=9)
        pd.testing.assert_frame_equal(lhs.observations, rhs.observations)

    def test_vr_bt02_missing_columns_rejected(self):
        with pytest.raises(ValueError, match="required columns"):
            BacktestDataset(pd.DataFrame({"observation_date": ["2026-12-31"]}))

    def test_vr_bt02_non_positive_horizon_rejected(self):
        data = pd.DataFrame(
            {
                "observation_date": ["2026-12-31"],
                "initial_short_rate": [0.02],
                "initial_equity_index": [100.0],
                "realised_rate_1y": [0.021],
                "realised_equity_return_1y": [0.05],
                "realised_loss": [0.0],
            }
        )
        with pytest.raises(ValueError, match="horizon_months"):
            BacktestDataset(data, horizon_months=0)


class TestBacktestHelpers:
    def test_vr_bt03_loss_increases_when_rate_falls_or_equity_crashes(self):
        benign = _loss_from_market_outcome(0.04, 0.10, 0.035, 1_000_000, 0.35, 5.0)
        stressed = _loss_from_market_outcome(0.01, -0.20, 0.035, 1_000_000, 0.35, 5.0)
        assert stressed > benign

    def test_vr_bt03_vectorised_loss_shape_preserved(self):
        losses = _loss_from_market_outcome(
            np.array([0.03, 0.02]),
            np.array([0.02, -0.10]),
            0.035,
            1_000_000,
            0.35,
            5.0,
        )
        assert losses.shape == (2,)

    def test_vr_bt04_kupiec_returns_high_pvalue_near_expected_rate(self):
        pvalue = _kupiec_pof_pvalue(5, 100, ConfidenceLevel.CL_95)
        assert 0.05 < pvalue <= 1.0

    def test_vr_bt04_kupiec_rejects_invalid_inputs(self):
        with pytest.raises(ValueError, match="positive"):
            _kupiec_pof_pvalue(1, 0, ConfidenceLevel.CL_99)
        with pytest.raises(ValueError, match="between 0 and n_observations"):
            _kupiec_pof_pvalue(11, 10, ConfidenceLevel.CL_99)


class TestBacktestEngine:
    def test_vr_bt05_run_returns_detail_frame_and_summary_metrics(self, calibration_result):
        dataset = BacktestDataset.synthetic(calibration_result, n_observations=12, seed=21)
        engine = BacktestEngine(calibration_result)

        result = engine.run(dataset, n_scenarios=300, seed=100)

        assert len(result.detail) == dataset.n_observations
        assert {"es95", "es99", "var95_excess", "var99_excess"}.issubset(result.detail.columns)
        assert 0.0 <= result.rate_coverage_pct <= 1.0
        assert 0.0 <= result.equity_coverage_pct <= 1.0
        assert 0.0 <= result.var95_exception_rate <= 1.0
        assert 0.0 <= result.var99_exception_rate <= 1.0
        assert result.es95_mean >= result.detail["var95"].mean()
        assert result.es99_mean >= result.detail["var99"].mean()
        assert "all_pass" in result.martingale_results.attrs
        assert result.run_id.startswith("backtest-")

    def test_vr_bt05_summary_contains_core_fields(self, calibration_result):
        dataset = BacktestDataset.synthetic(calibration_result, n_observations=6, seed=22)
        result = BacktestEngine(calibration_result).run(dataset, n_scenarios=250, seed=88)
        summary = result.summary()
        assert "rate_coverage_pct" in summary
        assert "equity_coverage_pct" in summary
        assert "es99_mean" in summary
        assert "requires_recalibration" in summary

    def test_vr_bt05_tail_summary_and_worst_observation_are_available(self, calibration_result):
        dataset = BacktestDataset.synthetic(calibration_result, n_observations=8, seed=18)
        result = BacktestEngine(calibration_result).run(dataset, n_scenarios=250, seed=77)

        tail = result.tail_summary()
        worst = result.worst_observation()

        assert tail["mean_es95"] >= tail["mean_var95"]
        assert tail["mean_es99"] >= tail["mean_var99"]
        assert "realised_loss" in worst
        assert "observation_date" in worst

    def test_vr_bt05_invalid_horizon_rejected(self, calibration_result):
        dataset = BacktestDataset.synthetic(calibration_result, n_observations=2, seed=3)
        mutated = BacktestDataset(dataset.observations.copy(), horizon_months=6)
        with pytest.raises(ValueError, match="12-month horizon"):
            BacktestEngine(calibration_result).run(mutated, n_scenarios=200)

    def test_vr_bt05_low_scenario_count_rejected(self, calibration_result):
        dataset = BacktestDataset.synthetic(calibration_result, n_observations=2, seed=3)
        with pytest.raises(ValueError, match="at least 100"):
            BacktestEngine(calibration_result).run(dataset, n_scenarios=99)

    def test_vr_bt05_synthetic_history_is_generally_well_behaved(self, calibration_result):
        dataset = BacktestDataset.synthetic(calibration_result, n_observations=60, seed=30)
        result = BacktestEngine(calibration_result).run(dataset, n_scenarios=250, seed=400)
        assert result.rate_coverage_pct >= 0.70
        assert result.equity_coverage_pct >= 0.70
        assert result.requires_recalibration is False

    def test_vr_bt06_governance_entries_appended(self, calibration_result):
        dataset = BacktestDataset.synthetic(calibration_result, n_observations=5, seed=15)
        store = GovernanceStore()

        result = BacktestEngine(calibration_result, governance_store=store).run(
            dataset,
            n_scenarios=200,
            seed=200,
        )

        assert len(store.audit_trail.all()) == 2
        assert result.audit_entry_id is not None

    def test_vr_bt07_extreme_losses_trigger_recalibration_flag(self, calibration_result):
        dataset = BacktestDataset.synthetic(calibration_result, n_observations=10, seed=11)
        stressed = dataset.observations.copy()
        stressed["realised_loss"] = stressed["realised_loss"] + 10_000_000.0
        stressed["realised_equity_return_1y"] = -0.50
        stressed_dataset = BacktestDataset(stressed)

        result = BacktestEngine(calibration_result).run(stressed_dataset, n_scenarios=250, seed=500)

        assert result.var99_exception_rate > 0.05
        assert result.requires_recalibration is True


class TestBacktestReporting:
    def test_vr_bt08_markdown_report_contains_tail_analysis(self, calibration_result):
        dataset = BacktestDataset.synthetic(calibration_result, n_observations=12, seed=32)
        result = BacktestEngine(calibration_result).run(dataset, n_scenarios=300, seed=44)

        report = BacktestReport(
            calibration_result=calibration_result,
            dataset=dataset,
            backtest_result=result,
            report_year=2026,
        )
        markdown = report.to_markdown()

        assert "# Calibration Backtest Report 2026" in markdown
        assert "## 2. Tail Loss Analysis" in markdown
        assert "Kupiec POF p-values" in markdown
        assert result.run_id in markdown

    def test_vr_bt08_generate_report_writes_expected_file(self, calibration_result, tmp_path):
        dataset = BacktestDataset.synthetic(calibration_result, n_observations=5, seed=33)
        result = BacktestEngine(calibration_result).run(dataset, n_scenarios=250, seed=55)

        path = generate_backtest_report(
            calibration_result=calibration_result,
            dataset=dataset,
            backtest_result=result,
            report_year=2030,
            docs_dir=tmp_path,
        )

        assert path.name == "CALIBRATION_BACKTEST_REPORT_2030.md"
        assert path.exists()
        assert "Tail Loss Analysis" in path.read_text(encoding="utf-8")
