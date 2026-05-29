"""
Tests for par_model_v2.stochastic.esg_process.

Phase 4, Task 1: GBM/Hull-White sample ESG generator.
"""

from __future__ import annotations

from datetime import date
import warnings

import numpy as np
import pandas as pd
import pytest

from par_model_v2.stochastic.esg_adapter import (
    ESGAdapter,
    ScenarioAdequacyWarning,
)
from par_model_v2.stochastic.esg_process import (
    CalibrationDataInterface,
    CalibrationFieldSpec,
    CalibrationSource,
    GBMEquityProcess,
    GBMParams,
    HullWhiteParams,
    HullWhiteRateProcess,
    Measure,
    ParameterSnapshot,
    ScenarioSet,
    ScenarioMetadata,
    default_phase6_calibration_interfaces,
)


class TestHullWhiteRateProcess:
    def test_simulate_returns_expected_schema_and_shape(self):
        df = HullWhiteRateProcess().simulate(
            n_scenarios=3,
            T_months=12,
            measure=Measure.Q,
            seed=7,
        )

        assert len(df) == 3 * 13
        assert list(df.columns) == [
            "scenario_id",
            "month",
            "r_short",
            "zcb_1y",
            "zcb_10y",
            "measure",
        ]

    def test_initial_short_rate_is_at_month_zero_for_all_scenarios(self):
        params = HullWhiteParams(initial_short_rate=0.027)
        df = HullWhiteRateProcess(params).simulate(5, 6, Measure.Q, seed=3)

        month0 = df[df["month"] == 0]
        assert np.allclose(month0["r_short"].to_numpy(), 0.027)

    def test_output_is_reproducible_for_same_seed(self):
        process = HullWhiteRateProcess()
        a = process.simulate(10, 24, Measure.Q, seed=42)
        b = process.simulate(10, 24, Measure.Q, seed=42)

        pd.testing.assert_frame_equal(a, b)

    def test_different_seed_changes_paths(self):
        process = HullWhiteRateProcess()
        a = process.simulate(10, 24, Measure.Q, seed=42)
        b = process.simulate(10, 24, Measure.Q, seed=43)

        assert not np.allclose(a["r_short"].to_numpy(), b["r_short"].to_numpy())

    def test_rates_and_zcbs_respect_adapter_ranges(self):
        df = HullWhiteRateProcess().simulate(100, 120, Measure.Q, seed=11)

        assert df["r_short"].between(-0.02, 0.15).all()
        assert df["zcb_1y"].between(0.0, 1.0, inclusive="right").all()
        assert df["zcb_10y"].between(0.0, 1.0, inclusive="right").all()

    def test_string_measure_is_accepted_and_normalized(self):
        df = HullWhiteRateProcess().simulate(2, 2, "q", seed=1)

        assert set(df["measure"]) == {"Q"}

    def test_invalid_measure_raises_value_error(self):
        with pytest.raises(ValueError, match="measure"):
            HullWhiteRateProcess().simulate(2, 2, "X", seed=1)

    def test_invalid_dimensions_raise_value_error(self):
        with pytest.raises(ValueError, match="n_scenarios"):
            HullWhiteRateProcess().simulate(0, 12, Measure.Q)
        with pytest.raises(ValueError, match="T_months"):
            HullWhiteRateProcess().simulate(1, -1, Measure.Q)

    def test_p_measure_terminal_mean_exceeds_q_with_default_params(self):
        process = HullWhiteRateProcess()
        p_df = process.simulate(2_000, 120, Measure.P, seed=9)
        q_df = process.simulate(2_000, 120, Measure.Q, seed=9)

        p_mean = p_df[p_df["month"] == 120]["r_short"].mean()
        q_mean = q_df[q_df["month"] == 120]["r_short"].mean()
        assert p_mean > q_mean + 0.001


class TestGBMEquityProcess:
    def test_simulate_returns_expected_schema_and_shape(self):
        df = GBMEquityProcess().simulate(4, 12, Measure.P, seed=5)

        assert len(df) == 4 * 13
        assert list(df.columns) == [
            "scenario_id",
            "month",
            "equity_index",
            "equity_return_1m",
            "measure",
        ]

    def test_equity_index_is_positive(self):
        df = GBMEquityProcess().simulate(200, 240, Measure.P, seed=99)

        assert (df["equity_index"] > 0).all()

    def test_month_zero_return_is_zero(self):
        df = GBMEquityProcess().simulate(6, 24, Measure.P, seed=6)
        month0 = df[df["month"] == 0]

        assert np.allclose(month0["equity_return_1m"].to_numpy(), 0.0)

    def test_reproducible_for_same_seed(self):
        process = GBMEquityProcess()
        a = process.simulate(20, 36, Measure.P, seed=22)
        b = process.simulate(20, 36, Measure.P, seed=22)

        pd.testing.assert_frame_equal(a, b)

    def test_rate_paths_shape_is_validated(self):
        bad_rate_paths = np.full((3, 12), 0.02)

        with pytest.raises(ValueError, match="rate_paths"):
            GBMEquityProcess().simulate(
                3,
                12,
                Measure.Q,
                rate_paths=bad_rate_paths,
            )

    def test_p_measure_has_higher_terminal_mean_than_q(self):
        params = GBMParams(equity_vol=0.10, equity_risk_premium=0.05)
        process = GBMEquityProcess(params)
        rate_paths = np.full((2_000, 121), 0.02)

        p_df = process.simulate(2_000, 120, Measure.P, rate_paths=rate_paths, seed=12)
        q_df = process.simulate(2_000, 120, Measure.Q, rate_paths=rate_paths, seed=12)

        p_mean = p_df[p_df["month"] == 120]["equity_index"].mean()
        q_mean = q_df[q_df["month"] == 120]["equity_index"].mean()
        assert p_mean > q_mean * 1.30


class TestScenarioSetGenerate:
    def test_generate_returns_scenario_set_with_expected_metadata(self):
        scenarios = ScenarioSet.generate(25, 36, Measure.Q, seed=101)

        assert scenarios.n_scenarios == 25
        assert scenarios.T_months == 36
        assert scenarios.measure == Measure.Q
        assert scenarios.seed == 101
        assert scenarios.metadata.measure == Measure.Q
        assert scenarios.metadata.n_scenarios == 25
        assert scenarios.metadata.projection_months == 36
        assert scenarios.metadata.parameter_snapshot_id == scenarios.parameter_snapshot.snapshot_id

    def test_generate_returns_combined_adapter_schema(self):
        scenarios = ScenarioSet.generate(10, 12, Measure.P, seed=19)

        for col in ESGAdapter.required_columns():
            assert col in scenarios.data.columns
        assert "equity_return_1m" in scenarios.data.columns
        assert len(scenarios.data) == 10 * 13

    def test_generated_data_passes_esg_adapter_validation(self):
        scenarios = ScenarioSet.generate(500, 2, Measure.Q, seed=23)

        with warnings.catch_warnings():
            warnings.simplefilter("error", ScenarioAdequacyWarning)
            loaded = ESGAdapter().load_from_dataframe(scenarios.data)

        assert loaded["scenario_id"].nunique() == 500

    def test_path_returns_single_scenario(self):
        scenarios = ScenarioSet.generate(7, 18, Measure.P, seed=8)
        path = scenarios.path(3)

        assert len(path) == 19
        assert set(path["scenario_id"]) == {3}
        assert path["month"].tolist() == list(range(19))

    def test_summary_stats_has_rate_and_equity_columns(self):
        scenarios = ScenarioSet.generate(20, 12, Measure.P, seed=10)
        stats = scenarios.summary_stats()

        assert "r_short_mean" in stats.columns
        assert "equity_index_p95" in stats.columns
        assert stats.index.min() == 0
        assert stats.index.max() == 12

    def test_generate_is_reproducible_for_same_seed(self):
        a = ScenarioSet.generate(20, 24, Measure.Q, seed=77)
        b = ScenarioSet.generate(20, 24, Measure.Q, seed=77)

        pd.testing.assert_frame_equal(a.data, b.data)

    def test_generate_changes_when_seed_changes(self):
        a = ScenarioSet.generate(20, 24, Measure.Q, seed=77)
        b = ScenarioSet.generate(20, 24, Measure.Q, seed=78)

        assert not np.allclose(
            a.data["equity_index"].to_numpy(),
            b.data["equity_index"].to_numpy(),
        )

    def test_generated_rate_equity_correlation_is_directional(self):
        hw_params = HullWhiteParams(short_rate_vol=0.006)
        gbm_params = GBMParams(rate_equity_correlation=-0.70, equity_vol=0.18)
        scenarios = ScenarioSet.generate(
            1_000,
            120,
            Measure.P,
            hw_params=hw_params,
            gbm_params=gbm_params,
            seed=123,
        )

        pivot_rates = scenarios.data.pivot(
            index="scenario_id",
            columns="month",
            values="r_short",
        )
        rate_changes = pivot_rates.diff(axis=1).iloc[:, 1:].to_numpy().reshape(-1)
        equity_returns = scenarios.data[scenarios.data["month"] > 0][
            "equity_return_1m"
        ].to_numpy()

        corr = np.corrcoef(rate_changes, equity_returns)[0, 1]
        assert corr < -0.45

    def test_zero_month_horizon_is_supported(self):
        scenarios = ScenarioSet.generate(3, 0, Measure.Q, seed=1)

        assert len(scenarios.data) == 3
        assert set(scenarios.data["month"]) == {0}
        assert np.allclose(scenarios.data["equity_return_1m"].to_numpy(), 0.0)

    def test_invalid_generate_dimensions_raise_value_error(self):
        with pytest.raises(ValueError, match="n_scenarios"):
            ScenarioSet.generate(0, 12, Measure.Q)
        with pytest.raises(ValueError, match="T_months"):
            ScenarioSet.generate(1, -1, Measure.Q)

    def test_generate_accepts_custom_phase6_metadata_inputs(self):
        scenarios = ScenarioSet.generate(
            5,
            12,
            Measure.P,
            seed=44,
            scenario_set_id="SCEN-HKD-P-20260529",
            model_version="test-version",
            base_currency="HKD",
            valuation_date=date(2026, 5, 29),
        )

        assert scenarios.metadata.scenario_set_id == "SCEN-HKD-P-20260529"
        assert scenarios.metadata.model_version == "test-version"
        assert scenarios.metadata.base_currency == "HKD"
        assert scenarios.metadata.valuation_date == date(2026, 5, 29)
        assert scenarios.parameter_snapshot.base_currency == "HKD"


class TestScenarioMetadataAndParameterSnapshot:
    def test_parameter_snapshot_from_process_params_captures_required_fields(self):
        snapshot = ParameterSnapshot.from_process_params(
            measure="q",
            base_currency="hkd",
            calibration_date="2026-05-29",
            hw_params=HullWhiteParams(initial_short_rate=0.031),
            gbm_params=GBMParams(equity_vol=0.18),
        )

        assert snapshot.measure == Measure.Q
        assert snapshot.base_currency == "HKD"
        assert snapshot.calibration_date == date(2026, 5, 29)
        assert snapshot.parameters["rate.hw1f.initial_short_rate"] == 0.031
        assert snapshot.parameters["equity.gbm.equity_vol"] == 0.18
        assert snapshot.sources[0].source_id == "SRC-PLACEHOLDER-HKD"
        assert "IFACE-CURVE-HK-HKD" in {
            interface.interface_id for interface in snapshot.calibration_interfaces
        }

    def test_parameter_snapshot_rejects_missing_parameters(self):
        with pytest.raises(ValueError, match="parameters"):
            ParameterSnapshot(
                snapshot_id="PS-EMPTY",
                calibration_date=date(2026, 5, 29),
                measure=Measure.P,
                base_currency="CNY",
                parameters={},
            )

    def test_calibration_source_rejects_bad_currency(self):
        with pytest.raises(ValueError, match="currency"):
            CalibrationSource(
                source_id="SRC-BAD",
                source_type="curve",
                market="HK",
                currency="Hong Kong Dollar",
                as_of_date=date(2026, 5, 29),
                provider="test",
                dataset_name="test",
            )

    def test_scenario_metadata_rejects_snapshot_measure_mismatch(self):
        snapshot = ParameterSnapshot.from_process_params(
            measure=Measure.P,
            base_currency="CNY",
            calibration_date=date(2026, 5, 29),
        )

        with pytest.raises(ValueError, match="measure"):
            ScenarioMetadata.from_generation(
                n_scenarios=10,
                T_months=12,
                measure=Measure.Q,
                seed=1,
                parameter_snapshot=snapshot,
                valuation_date=date(2026, 5, 29),
            )

    def test_metadata_and_snapshot_to_dict_are_json_ready(self):
        scenarios = ScenarioSet.generate(
            3,
            2,
            Measure.Q,
            seed=7,
            valuation_date=date(2026, 5, 29),
        )

        metadata = scenarios.metadata.to_dict()
        snapshot = scenarios.parameter_snapshot.to_dict()

        assert metadata["measure"] == "Q"
        assert metadata["valuation_date"] == "2026-05-29"
        assert snapshot["calibration_date"] == "2026-05-29"
        assert snapshot["sources"][0]["as_of_date"] == "2026-05-29"
        assert snapshot["calibration_interfaces"][0]["required_fields"][0]["name"] == "date"


class TestPhase6CalibrationDataInterfaces:
    def test_default_interfaces_cover_required_source_types(self):
        interfaces = default_phase6_calibration_interfaces()
        source_types = {interface.source_type for interface in interfaces}

        assert {"curve", "equity_index", "fx", "credit_spread", "correlation"} <= source_types
        assert len({interface.interface_id for interface in interfaces}) == len(interfaces)

    def test_curve_interface_validates_required_columns_and_ranges(self):
        interface = CalibrationDataInterface.risk_free_curve("HK", "HKD")
        valid = pd.DataFrame({
            "date": ["2026-05-29", "2026-05-29"],
            "tenor_years": [1.0, 10.0],
            "zero_rate": [0.025, 0.031],
            "discount_factor": [0.975, 0.735],
        })

        assert interface.validate_frame(valid) is True

        missing = valid.drop(columns=["zero_rate"])
        with pytest.raises(ValueError, match="zero_rate"):
            interface.validate_frame(missing)

        bad_rate = valid.copy()
        bad_rate.loc[0, "zero_rate"] = 1.25
        with pytest.raises(ValueError, match="zero_rate"):
            interface.validate_frame(bad_rate)

    def test_fx_interface_rejects_bad_quotation_convention(self):
        interface = CalibrationDataInterface.fx_rates("HK", "HKD")
        data = pd.DataFrame({
            "date": pd.date_range("2026-05-27", periods=252),
            "pair": ["USDHKD"] * 252,
            "spot_rate": [7.8] * 252,
            "quotation": ["SIDEWAYS"] * 252,
        })

        with pytest.raises(ValueError, match="quotation"):
            interface.validate_frame(data)

    def test_correlation_interface_rejects_out_of_range_entries(self):
        interface = CalibrationDataInterface.correlation_matrix()
        data = pd.DataFrame({
            "as_of_date": ["2026-05-29"],
            "factor_id_1": ["RATE_SHORT_HKD"],
            "factor_id_2": ["EQUITY_HK_CN"],
            "correlation": [1.25],
            "matrix_version": ["corr-20260529"],
        })

        with pytest.raises(ValueError, match="correlation"):
            interface.validate_frame(data)

    def test_duplicate_field_specs_are_rejected(self):
        with pytest.raises(ValueError, match="unique"):
            CalibrationDataInterface(
                interface_id="IFACE-DUP",
                source_type="curve",
                market="HK",
                currency="HKD",
                required_fields=(
                    CalibrationFieldSpec("date", "date"),
                    CalibrationFieldSpec("date", "string"),
                ),
            )
