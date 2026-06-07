"""
Tests — Phase 21 Task 3: Liquidity-premium driver (7th), calibration, G-LIQ gate.

Covers:
  1. LiquidityPremiumParams validation + properties.
  2. LiquidityPremiumProcess simulation (shape, reproducibility, bounds,
     P/Q anchor ordering, measure enforcement, DataFrame contract).
  3. _inner_q_liquidity_process conditioning.
  4. forced_sale_haircut_fraction helper.
  5. LiquidityPremiumCalibrator recovery from synthesized history (delegated
     CIR OLS) + lambda backout.
  6. Fixture loader / lineage / synthesis determinism.
  7. G-LIQ gate criteria and failure modes.
  8. run_phase21_liquidity_calibration pipeline on an in-memory store
     (ChangeRecord APPROVED, PARAM_CHANGE audit, MR refresh, markdown).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from par_model_v2.calibration.liquidity_calibrator import (
    LiquidityCalibrationInputs,
    LiquidityPremiumCalibrator,
)
from par_model_v2.calibration.liquidity_market_data_source import (
    LAMBDA_MAX,
    LONG_RUN_MAX,
    LONG_RUN_MIN,
    MIN_OBS,
    build_liquidity_loader,
    check_liquidity_calibration,
    evaluate_liquidity_gate,
    synthesize_premium_history,
    FileBasedLiquidityPremiumSource,
)
from par_model_v2.calibration.phase21_liquidity_calibration import (
    run_phase21_liquidity_calibration,
)
from par_model_v2.governance.audit_trail import GovernanceStore
from par_model_v2.stochastic.esg_process import Measure
from par_model_v2.stochastic.liquidity_premium import (
    LiquidityPremiumParams,
    LiquidityPremiumProcess,
    _inner_q_liquidity_process,
    forced_sale_haircut_fraction,
)


# ---------------------------------------------------------------------------
# 1. Params
# ---------------------------------------------------------------------------

class TestLiquidityPremiumParams:
    def test_defaults_valid(self):
        p = LiquidityPremiumParams()
        assert p.initial_x >= 0
        assert p.long_run_x_p > 0
        assert p.is_placeholder

    def test_rejects_nonpositive_kappa(self):
        with pytest.raises(ValueError):
            LiquidityPremiumParams(mean_reversion_speed=0.0)

    def test_rejects_nonpositive_vol(self):
        with pytest.raises(ValueError):
            LiquidityPremiumParams(premium_vol=-0.01)

    def test_rejects_initial_below_shift(self):
        with pytest.raises(ValueError):
            LiquidityPremiumParams(initial_premium=0.0005, shift=0.001)

    def test_rejects_floor_above_ceiling(self):
        with pytest.raises(ValueError):
            LiquidityPremiumParams(premium_floor=0.2, premium_ceiling=0.1)


# ---------------------------------------------------------------------------
# 2. Process
# ---------------------------------------------------------------------------

class TestLiquidityPremiumProcess:
    def test_simulate_frame_contract(self):
        df = LiquidityPremiumProcess().simulate(8, 12, Measure.P, seed=42)
        assert list(df.columns) == ["scenario_id", "month", "liquidity_premium", "measure"]
        assert len(df) == 8 * 13
        assert (df["measure"] == Measure.P.value).all()

    def test_reproducible_same_seed(self):
        a = LiquidityPremiumProcess().simulate(6, 24, Measure.P, seed=7)
        b = LiquidityPremiumProcess().simulate(6, 24, Measure.P, seed=7)
        pd.testing.assert_frame_equal(a, b)

    def test_premium_within_bounds(self):
        p = LiquidityPremiumParams(premium_ceiling=0.10)
        df = LiquidityPremiumProcess(p).simulate(50, 120, Measure.P, seed=3)
        prem = df["liquidity_premium"].to_numpy()
        assert prem.min() >= 0.0
        assert prem.max() <= 0.10 + 1e-12

    def test_q_long_run_exceeds_p(self):
        """Positive lambda_l => Q long-run premium above P (insurer-loss sign)."""
        p = LiquidityPremiumParams(market_price_of_liquidity_risk=0.5)
        proc = LiquidityPremiumProcess(p)
        assert proc._long_run_x(Measure.Q) > proc._long_run_x(Measure.P)

    def test_mean_converges_toward_long_run(self):
        p = LiquidityPremiumParams(
            mean_reversion_speed=1.5, initial_premium=0.002,
            long_run_premium_p=0.008, premium_vol=0.01, shift=0.001,
        )
        df = LiquidityPremiumProcess(p).simulate(4000, 120, Measure.P, seed=11)
        terminal = df[df["month"] == 120]["liquidity_premium"].mean()
        assert abs(terminal - 0.008) < 0.0015

    def test_shock_shape_validation(self):
        proc = LiquidityPremiumProcess()
        with pytest.raises(ValueError):
            proc._simulate_array(4, 12, Measure.P, np.zeros((4, 11)))


# ---------------------------------------------------------------------------
# 3. Inner conditioning
# ---------------------------------------------------------------------------

class TestInnerConditioning:
    def test_inner_starts_at_state(self):
        base = LiquidityPremiumParams()
        inner = _inner_q_liquidity_process(0.0234, base)
        assert inner.params.initial_premium == pytest.approx(0.0234)
        assert inner.params.mean_reversion_speed == base.mean_reversion_speed

    def test_inner_handles_deep_tail_below_shift(self):
        base = LiquidityPremiumParams(shift=0.001)
        inner = _inner_q_liquidity_process(0.0004, base)
        assert inner.params.initial_x >= 0.0


# ---------------------------------------------------------------------------
# 4. Haircut helper
# ---------------------------------------------------------------------------

class TestForcedSaleHaircut:
    def test_zero_premium_zero_haircut(self):
        h = forced_sale_haircut_fraction(np.zeros((5, 13)))
        assert np.allclose(h, 0.0)

    def test_constant_premium_closed_form(self):
        paths = np.full((3, 13), 0.01)  # 12 months at 100 bp
        h = forced_sale_haircut_fraction(paths)
        assert np.allclose(h, 1.0 - np.exp(-0.01), rtol=1e-12)

    def test_monotone_in_premium(self):
        lo = forced_sale_haircut_fraction(np.full((1, 13), 0.005))[0]
        hi = forced_sale_haircut_fraction(np.full((1, 13), 0.02))[0]
        assert hi > lo

    def test_rejects_1d(self):
        with pytest.raises(ValueError):
            forced_sale_haircut_fraction(np.zeros(13))


# ---------------------------------------------------------------------------
# 5. Calibrator
# ---------------------------------------------------------------------------

def _synth_series(kappa=0.6, theta=0.006, sigma=0.022, shift=0.001, n_years=20, seed=123):
    rng = np.random.default_rng(seed)
    dt = 1.0 / 12.0
    n = n_years * 12
    b = theta - shift
    x = np.empty(n)
    x[0] = 0.005 - shift
    for t in range(1, n):
        xp = max(x[t - 1], 0.0)
        x[t] = max(x[t - 1] + kappa * (b - x[t - 1]) * dt + sigma * np.sqrt(xp) * np.sqrt(dt) * rng.standard_normal(), 0.0)
    idx = pd.date_range("2006-01-31", periods=n, freq="ME")
    return pd.Series(x + shift, index=idx)


class TestLiquidityCalibrator:
    def test_recovers_long_run_and_sigma(self):
        series = _synth_series()
        from datetime import date
        inputs = LiquidityCalibrationInputs(
            calibration_date=date(2026, 1, 1),
            premium_history=series,
            shift=0.001,
            risk_neutral_long_run_premium=0.0075,
        )
        res = LiquidityPremiumCalibrator(inputs).calibrate()
        assert res.long_run_premium_p == pytest.approx(0.006, abs=0.002)
        assert res.premium_vol == pytest.approx(0.022, rel=0.35)
        assert 0.05 <= res.mean_reversion_speed <= 3.0
        assert not res.is_placeholder

    def test_lambda_from_rn_anchor_nonnegative_capped(self):
        series = _synth_series()
        from datetime import date
        inputs = LiquidityCalibrationInputs(
            calibration_date=date(2026, 1, 1),
            premium_history=series,
            shift=0.001,
            risk_neutral_long_run_premium=0.0075,
        )
        res = LiquidityPremiumCalibrator(inputs).calibrate()
        assert 0.0 <= res.market_price_of_liquidity_risk <= LAMBDA_MAX

    def test_to_params_roundtrip(self):
        series = _synth_series()
        from datetime import date
        inputs = LiquidityCalibrationInputs(
            calibration_date=date(2026, 1, 1), premium_history=series, shift=0.001,
        )
        params = LiquidityPremiumCalibrator(inputs).calibrate().to_params()
        assert isinstance(params, LiquidityPremiumParams)
        # The calibrated params must simulate without error.
        LiquidityPremiumProcess(params).simulate(4, 12, Measure.Q, seed=1)

    def test_rejects_negative_history(self):
        from datetime import date
        idx = pd.date_range("2024-01-31", periods=12, freq="ME")
        with pytest.raises(ValueError):
            LiquidityCalibrationInputs(
                calibration_date=date(2026, 1, 1),
                premium_history=pd.Series([-0.001] + [0.005] * 11, index=idx),
            )

    def test_rejects_shift_above_min(self):
        from datetime import date
        idx = pd.date_range("2024-01-31", periods=12, freq="ME")
        with pytest.raises(ValueError):
            LiquidityCalibrationInputs(
                calibration_date=date(2026, 1, 1),
                premium_history=pd.Series([0.004] * 12, index=idx),
                shift=0.005,
            )


# ---------------------------------------------------------------------------
# 6. Fixture loader
# ---------------------------------------------------------------------------

class TestFixtureLoader:
    def test_loader_loads_and_validates(self):
        loader = build_liquidity_loader("HKD")
        inputs, lineage = loader.load()
        assert len(inputs.premium_history) >= MIN_OBS
        assert lineage.market == "HKD"
        assert lineage.lineage_id.startswith("LINLIQ_HKD_")
        assert len(lineage.sha256_checksum) == 64

    def test_synthesis_deterministic(self):
        import json
        from par_model_v2.calibration.liquidity_market_data_source import default_fixture_dir
        spec = json.load(open(default_fixture_dir() / "hkd_liquidity_premium_history_20260101.json"))
        s1, d1 = synthesize_premium_history(spec)
        s2, d2 = synthesize_premium_history(spec)
        pd.testing.assert_series_equal(s1, s2)
        assert d1 == d2

    def test_missing_fixture_raises(self):
        with pytest.raises(FileNotFoundError):
            FileBasedLiquidityPremiumSource("/nonexistent/fixture.json")


# ---------------------------------------------------------------------------
# 7. G-LIQ gate
# ---------------------------------------------------------------------------

class _FakeResult:
    def __init__(self, kappa=0.5, lr=0.006, sigma=0.02, lam=0.5, placeholder=False):
        self.mean_reversion_speed = kappa
        self.long_run_premium_p = lr
        self.premium_vol = sigma
        self.market_price_of_liquidity_risk = lam
        self.is_placeholder = placeholder


class TestGLIQGate:
    def test_pass_inside_bands(self):
        check = check_liquidity_calibration("HKD", 240, _FakeResult(), True)
        gate = evaluate_liquidity_gate(check)
        assert gate.status == "PASS"
        assert gate.gate_id == "G-LIQ"
        assert check.all_pass()

    def test_fail_long_run_out_of_band(self):
        check = check_liquidity_calibration("HKD", 240, _FakeResult(lr=LONG_RUN_MAX * 2), True)
        assert evaluate_liquidity_gate(check).status == "FAIL"
        assert not check.criteria["c3_long_run_in_band"]

    def test_fail_too_few_obs(self):
        check = check_liquidity_calibration("HKD", 10, _FakeResult(), True)
        assert not check.criteria["c1_min_obs"]
        assert evaluate_liquidity_gate(check).status == "FAIL"

    def test_fail_placeholder_or_no_audit(self):
        check = check_liquidity_calibration("HKD", 240, _FakeResult(placeholder=True), True)
        assert not check.criteria["c6_not_placeholder_with_audit"]
        check2 = check_liquidity_calibration("HKD", 240, _FakeResult(), False)
        assert not check2.criteria["c6_not_placeholder_with_audit"]

    def test_long_run_band_sane(self):
        assert 0.0 < LONG_RUN_MIN < LONG_RUN_MAX < 0.10


# ---------------------------------------------------------------------------
# 8. Pipeline (in-memory governance store; no disk writes)
# ---------------------------------------------------------------------------

class TestPipeline:
    @pytest.fixture(scope="class")
    def report(self):
        store = GovernanceStore()
        return run_phase21_liquidity_calibration(
            governance_store=store, write_report=False, persist_governance=False,
        )

    def test_gate_passes(self, report):
        assert report.gate_gliq.status == "PASS", report.gate_gliq.evidence

    def test_change_record_approved(self, report):
        assert report.change_record_status == "APPROVED"
        assert report.change_record_id

    def test_audit_entries_recorded(self, report):
        assert len(report.audit_entry_ids) == 1

    def test_summary_within_bands(self, report):
        s = report.summary
        assert LONG_RUN_MIN <= s.long_run_premium_p <= LONG_RUN_MAX
        assert s.n_obs >= MIN_OBS
        assert s.market == "HKD"

    def test_markdown_built(self, report):
        assert "G-LIQ" in report.markdown
        assert "seventh" in report.markdown.lower() or "SEVENTH" in report.markdown

    def test_mr_refresh_on_fresh_store_not_found(self, report):
        # In-memory empty store has no MR-011/MR-012 entries: honest NOT_FOUND.
        assert report.mr011_status in ("NOT_FOUND", "mitigated", "MITIGATED")
        assert report.mr012_status in ("NOT_FOUND", "mitigated", "MITIGATED")

    def test_to_json_serialisable(self, report):
        import json as _json
        parsed = _json.loads(report.to_json())
        assert parsed["gate_gliq"]["gate_id"] == "G-LIQ"
