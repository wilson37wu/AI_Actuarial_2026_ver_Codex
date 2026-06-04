"""Phase 14 Task 5 — Merton jump-diffusion equity process & Q-measure martingale tests.

Covers the optional stochastic-sophistication equity model added behind the
PAR_ESG_EQUITY_MODEL feature flag:

  * JumpDiffusionParams validation, compensator, GBM promotion
  * JumpDiffusionEquityProcess output contract & measure enforcement
  * Feature-flag resolution (arg / env var / default) and the GBM default being
    left byte-for-byte unchanged
  * Q-measure martingale evidence — constant-rate (exact-forward) and stochastic
    HW1F-rate paths, via EquityForwardMartingaleValidator
  * P-measure terminal mean strictly above Q (ERP drift)

SOA ASOP 56 §3.1.3/§3.4/§3.5; IA TAS M §3.4/§3.6.
"""

import math
import os

import numpy as np
import pandas as pd
import pytest

from par_model_v2.stochastic.esg_process import (
    DEFAULT_EQUITY_MODEL,
    EQUITY_PROCESS_REGISTRY,
    EquityForwardMartingaleValidator,
    GBMEquityProcess,
    GBMParams,
    JumpDiffusionEquityProcess,
    JumpDiffusionParams,
    Measure,
    MeasureEnforcementError,
    ScenarioSet,
    available_equity_models,
    build_equity_process,
    resolve_equity_model,
)


# ---------------------------------------------------------------------------
# JumpDiffusionParams
# ---------------------------------------------------------------------------

class TestJumpDiffusionParams:
    def test_defaults_are_placeholder(self):
        p = JumpDiffusionParams()
        assert p.is_placeholder is True

    def test_compensator_matches_lognormal_formula(self):
        p = JumpDiffusionParams(jump_mean=-0.10, jump_vol=0.15)
        expected = math.exp(-0.10 + 0.5 * 0.15 ** 2) - 1.0
        assert p.jump_compensator == pytest.approx(expected)

    def test_zero_intensity_is_valid(self):
        p = JumpDiffusionParams(jump_intensity=0.0)
        assert p.jump_intensity == 0.0

    @pytest.mark.parametrize("kwargs", [
        {"jump_intensity": -0.1},
        {"jump_vol": -0.01},
        {"jump_mean": 5.0},
        {"equity_vol": 0.0},
        {"rate_equity_correlation": 1.0},
    ])
    def test_invalid_params_rejected(self, kwargs):
        with pytest.raises(ValueError):
            JumpDiffusionParams(**kwargs)

    def test_from_gbm_params_inherits_continuous_block(self):
        gbm = GBMParams(equity_vol=0.27, dividend_yield=0.03,
                        equity_risk_premium=0.05, rate_equity_correlation=-0.2,
                        initial_index_level=100.0)
        jd = JumpDiffusionParams.from_gbm_params(gbm, jump_intensity=0.4)
        assert jd.equity_vol == 0.27
        assert jd.dividend_yield == 0.03
        assert jd.equity_risk_premium == 0.05
        assert jd.rate_equity_correlation == -0.2
        assert jd.jump_intensity == 0.4

    def test_from_gbm_params_type_checked(self):
        with pytest.raises(TypeError):
            JumpDiffusionParams.from_gbm_params(object())


# ---------------------------------------------------------------------------
# Process output contract & measure enforcement
# ---------------------------------------------------------------------------

class TestJumpDiffusionProcess:
    def test_supported_measures(self):
        assert JumpDiffusionEquityProcess.SUPPORTED_MEASURES == (Measure.P, Measure.Q)

    def test_output_columns_and_shape(self):
        df = JumpDiffusionEquityProcess().simulate(5, 12, Measure.P, seed=5)
        assert list(df.columns) == [
            "scenario_id", "month", "equity_index",
            "equity_return_1m", "equity_jump_count", "measure",
        ]
        assert len(df) == 5 * 13

    def test_index_strictly_positive(self):
        df = JumpDiffusionEquityProcess().simulate(200, 120, Measure.P, seed=9)
        assert (df["equity_index"] > 0).all()

    def test_month_zero_return_is_zero(self):
        df = JumpDiffusionEquityProcess().simulate(8, 24, Measure.Q, seed=4)
        m0 = df[df["month"] == 0]
        assert np.allclose(m0["equity_return_1m"].to_numpy(), 0.0)
        assert np.allclose(m0["equity_jump_count"].to_numpy(), 0.0)

    def test_reproducible(self):
        proc = JumpDiffusionEquityProcess()
        a = proc.simulate(50, 36, Measure.P, seed=22)
        b = proc.simulate(50, 36, Measure.P, seed=22)
        pd.testing.assert_frame_equal(a, b)

    def test_jump_counts_increase_with_intensity(self):
        low = JumpDiffusionEquityProcess(JumpDiffusionParams(jump_intensity=0.1))
        high = JumpDiffusionEquityProcess(JumpDiffusionParams(jump_intensity=3.0))
        n_low = low.simulate(2000, 120, Measure.Q, seed=1)["equity_jump_count"].sum()
        n_high = high.simulate(2000, 120, Measure.Q, seed=1)["equity_jump_count"].sum()
        assert n_high > n_low * 3

    def test_rate_paths_shape_validated(self):
        with pytest.raises(ValueError, match="rate_paths"):
            JumpDiffusionEquityProcess().simulate(
                3, 12, Measure.Q, rate_paths=np.full((3, 12), 0.02))

    def test_unsupported_measure_rejected(self):
        with pytest.raises((MeasureEnforcementError, ValueError)):
            JumpDiffusionEquityProcess().simulate(4, 6, "not-a-measure")

    def test_gbm_params_promoted_on_construction(self):
        proc = JumpDiffusionEquityProcess(GBMParams(equity_vol=0.3))
        assert isinstance(proc.params, JumpDiffusionParams)
        assert proc.params.equity_vol == 0.3

    def test_bad_params_type_rejected(self):
        with pytest.raises(TypeError):
            JumpDiffusionEquityProcess(params=object())

    def test_p_measure_terminal_mean_above_q(self):
        params = JumpDiffusionParams(equity_vol=0.12, equity_risk_premium=0.05,
                                     jump_intensity=0.3)
        proc = JumpDiffusionEquityProcess(params)
        rate_paths = np.full((4000, 121), 0.02)
        p = proc.simulate(4000, 120, Measure.P, rate_paths=rate_paths, seed=12)
        q = proc.simulate(4000, 120, Measure.Q, rate_paths=rate_paths, seed=12)
        assert p[p["month"] == 120]["equity_index"].mean() > \
            q[q["month"] == 120]["equity_index"].mean() * 1.25


# ---------------------------------------------------------------------------
# Feature flag / registry
# ---------------------------------------------------------------------------

class TestEquityModelFeatureFlag:
    def test_available_models(self):
        assert available_equity_models() == ("gbm", "jump_diffusion")

    def test_registry_maps_labels(self):
        assert EQUITY_PROCESS_REGISTRY["gbm"][0] is GBMEquityProcess
        assert EQUITY_PROCESS_REGISTRY["jump_diffusion"][0] is JumpDiffusionEquityProcess
        assert EQUITY_PROCESS_REGISTRY["merton"][0] is JumpDiffusionEquityProcess

    def test_default_is_gbm(self):
        assert DEFAULT_EQUITY_MODEL == "gbm"
        assert resolve_equity_model(None) == "gbm"

    def test_explicit_arg_overrides(self):
        assert resolve_equity_model("jump_diffusion") == "jump_diffusion"
        assert resolve_equity_model("MERTON") == "merton"

    def test_env_var_resolution(self, monkeypatch):
        monkeypatch.setenv("PAR_ESG_EQUITY_MODEL", "jump_diffusion")
        assert resolve_equity_model(None) == "jump_diffusion"

    def test_explicit_arg_beats_env_var(self, monkeypatch):
        monkeypatch.setenv("PAR_ESG_EQUITY_MODEL", "jump_diffusion")
        assert resolve_equity_model("gbm") == "gbm"

    def test_unknown_model_rejected(self):
        with pytest.raises(ValueError, match="unknown equity model"):
            resolve_equity_model("heston_typo")

    def test_build_factory_types(self):
        assert isinstance(build_equity_process("gbm"), GBMEquityProcess)
        assert isinstance(build_equity_process("jump_diffusion"), JumpDiffusionEquityProcess)

    def test_build_promotes_gbm_params_for_jump_model(self):
        proc = build_equity_process("merton", GBMParams(equity_vol=0.25))
        assert isinstance(proc.params, JumpDiffusionParams)
        assert proc.params.equity_vol == 0.25


# ---------------------------------------------------------------------------
# ScenarioSet.generate integration — GBM default must be unchanged
# ---------------------------------------------------------------------------

class TestScenarioSetEquityModel:
    def test_default_equals_explicit_gbm(self):
        a = ScenarioSet.generate(300, 36, Measure.Q, seed=11)
        b = ScenarioSet.generate(300, 36, Measure.Q, seed=11, equity_model="gbm")
        pd.testing.assert_frame_equal(a.data, b.data)
        assert "equity_jump_count" not in a.data.columns

    def test_jump_model_changes_equity_path(self):
        g = ScenarioSet.generate(200, 24, Measure.P, seed=1, equity_model="gbm")
        j = ScenarioSet.generate(200, 24, Measure.P, seed=1, equity_model="jump_diffusion")
        assert not np.allclose(g.data["equity_index"], j.data["equity_index"])

    def test_env_flag_switches_generate(self, monkeypatch):
        monkeypatch.setenv("PAR_ESG_EQUITY_MODEL", "jump_diffusion")
        flagged = ScenarioSet.generate(100, 12, Measure.P, seed=1)
        monkeypatch.delenv("PAR_ESG_EQUITY_MODEL")
        default = ScenarioSet.generate(100, 12, Measure.P, seed=1)
        assert not np.allclose(flagged.data["equity_index"], default.data["equity_index"])

    def test_snapshot_records_jump_params(self):
        s = ScenarioSet.generate(100, 12, Measure.Q, seed=1, equity_model="jump_diffusion")
        params = s.parameter_snapshot.to_dict()["parameters"]
        assert "equity.jumpdiffusion.jump_intensity" in params
        assert "equity.jumpdiffusion.jump_compensator" in params

    def test_unknown_model_rejected_in_generate(self):
        with pytest.raises(ValueError):
            ScenarioSet.generate(10, 6, Measure.Q, equity_model="nope")


# ---------------------------------------------------------------------------
# Q-measure martingale evidence
# ---------------------------------------------------------------------------

class TestQMeasureMartingale:
    def _constant_rate_q_frame(self, params, n=20000, T=48, r=0.02, seed=7):
        rate_paths = np.full((n, T + 1), r)
        df = JumpDiffusionEquityProcess(params).simulate(
            n, T, Measure.Q, rate_paths=rate_paths, seed=seed).copy()
        df["r_short"] = r
        return df, r, T

    def test_constant_rate_forward_matches_analytic(self):
        # E[S(t)] = S0 * exp((r - q) t); zero dividend simplifies to exp(r t).
        params = JumpDiffusionParams(equity_vol=0.20, dividend_yield=0.0,
                                     jump_intensity=0.6, jump_mean=-0.12, jump_vol=0.18)
        df, r, T = self._constant_rate_q_frame(params)
        terminal = df[df["month"] == T]["equity_index"].mean()
        analytic = 100.0 * math.exp(r * T / 12.0)
        assert terminal == pytest.approx(analytic, rel=0.01)

    def test_martingale_validator_passes_constant_rate(self):
        params = JumpDiffusionParams(equity_vol=0.20, dividend_yield=0.0,
                                     jump_intensity=0.6, jump_mean=-0.12, jump_vol=0.18)
        df, _, _ = self._constant_rate_q_frame(params)
        report = EquityForwardMartingaleValidator(
            dividend_yield=0.0, relative_tolerance=0.04, absolute_tolerance=0.6
        ).validate(df)
        assert report.passed
        assert report.diagnostics["max_relative_error"] < 0.02

    def test_martingale_independent_of_jump_params(self):
        # Compensator should preserve the forward regardless of jump severity.
        params = JumpDiffusionParams(equity_vol=0.25, dividend_yield=0.0,
                                     jump_intensity=2.0, jump_mean=-0.25, jump_vol=0.30)
        df, _, _ = self._constant_rate_q_frame(params, seed=3)
        report = EquityForwardMartingaleValidator(
            dividend_yield=0.0, relative_tolerance=0.05, absolute_tolerance=0.8
        ).validate(df)
        assert report.passed

    def test_martingale_with_dividend(self):
        q = 0.025
        params = JumpDiffusionParams(equity_vol=0.18, dividend_yield=q,
                                     jump_intensity=0.4)
        df, _, _ = self._constant_rate_q_frame(params, seed=5)
        report = EquityForwardMartingaleValidator(
            dividend_yield=q, relative_tolerance=0.04, absolute_tolerance=0.6
        ).validate(df)
        assert report.passed

    def test_martingale_with_stochastic_hw1f_rates(self):
        s = ScenarioSet.generate(4000, 48, Measure.Q, seed=11,
                                  equity_model="jump_diffusion")
        report = EquityForwardMartingaleValidator(
            dividend_yield=0.025, relative_tolerance=0.05, absolute_tolerance=1.0
        ).validate(s.data)
        assert report.passed

    def test_validator_rejects_p_measure(self):
        params = JumpDiffusionParams(dividend_yield=0.0)
        rate_paths = np.full((500, 25), 0.02)
        df = JumpDiffusionEquityProcess(params).simulate(
            500, 24, Measure.P, rate_paths=rate_paths, seed=2).copy()
        df["r_short"] = 0.02
        report = EquityForwardMartingaleValidator(dividend_yield=0.0).validate(df)
        assert not report.passed
        ids = {c.check_id for c in report.failed_checks()}
        assert "QME-EQUITY-MEASURE-Q" in ids

    def test_validator_rejects_missing_columns(self):
        df = pd.DataFrame({"scenario_id": [0], "month": [0], "measure": ["Q"]})
        report = EquityForwardMartingaleValidator().validate(df)
        assert not report.passed

    def test_report_is_json_ready(self):
        params = JumpDiffusionParams(dividend_yield=0.0)
        df, _, _ = self._constant_rate_q_frame(params, n=2000, T=12)
        report = EquityForwardMartingaleValidator(
            dividend_yield=0.0, absolute_tolerance=2.0, max_standard_error=5.0
        ).validate(df)
        d = report.to_dict()
        assert d["measure"] == "Q"
        assert any(c["check_id"] == "QME-EQUITY-FORWARD" for c in d["checks"])
