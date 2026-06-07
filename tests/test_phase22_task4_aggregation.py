"""Phase 22 Task 4 tests - seven-driver aggregation re-run with the
G-LIQX-CALIBRATED liquidity exposure notional + 7x7 couplings.

Covers: calibrated-loader wiring, PSD of the calibrated 7x7 correlation,
bit-identity of the first six outer columns under coupling changes (the CRN
slice-reuse justification), baseline-centred exposure impact, the calibrated
wording of the run notes, and the integrity of the persisted Task 4 report.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pytest

from par_model_v2.projection.monthly_projection import ParEndowmentProduct
from par_model_v2.projection.multi_driver_capital_5d_aggregation import (
    FiveDriverAggregationConfig,
)
from par_model_v2.projection.multi_driver_capital_7d_aggregation import (
    LiquidityExposureSpec,
    SevenDriverCorrelation,
    SevenDriverLiquidityRiskAggregator,
    calibrated_liquidity_exposure_notional,
    calibrated_liquidity_params,
    calibrated_seven_driver_correlation,
    cir_affine_haircut,
)
from par_model_v2.stochastic.esg_process import (
    CorrelationMatrixValidator,
    Measure,
)

REPO = Path(__file__).resolve().parents[1]
TASK3_REPORT = REPO / "docs/validation/PHASE22_TASK3_LIQUIDITY_EXPOSURE_REPORT.json"
TASK4_REPORT = REPO / "docs/validation/PHASE22_TASK4_AGGREGATION_REPORT.json"

COUPLING_NAMES = ("liq_rate", "liq_equity", "liq_spread",
                  "liq_lapse", "liq_mortality", "liq_fx")


def _product():
    return ParEndowmentProduct(
        issue_age=45, gender="M", sum_assured=100000.0,
        annual_premium=5000.0, term_years=20,
    )


# ---------------------------------------------------------------------------
# Calibrated loaders
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not TASK3_REPORT.exists(), reason="Task 3 report absent")
class TestCalibratedLoaders:
    def test_exposure_notional_is_calibrated(self):
        notional, is_placeholder = calibrated_liquidity_exposure_notional()
        assert not is_placeholder
        assert notional == pytest.approx(22_000.0, rel=1e-9)

    def test_notional_reproducible_from_balance_sheet_inputs(self):
        r = json.loads(TASK3_REPORT.read_text(encoding="utf-8"))
        e = r["exposure"]
        assert e["exposure_notional"] == pytest.approx(
            e["backing_asset_mv"] * e["illiquid_share"] * e["forced_sale_fraction"]
        )

    def test_couplings_match_task3_estimates(self):
        corr7, is_placeholder = calibrated_seven_driver_correlation()
        assert not is_placeholder
        est = json.loads(TASK3_REPORT.read_text(encoding="utf-8"))["estimated_couplings"]
        for name in COUPLING_NAMES:
            assert getattr(corr7, name) == pytest.approx(est[name], abs=5e-5)

    def test_calibrated_couplings_differ_from_placeholders(self):
        corr7, _ = calibrated_seven_driver_correlation()
        placeholder = SevenDriverCorrelation()
        assert any(
            getattr(corr7, n) != getattr(placeholder, n) for n in COUPLING_NAMES
        )


# ---------------------------------------------------------------------------
# Calibrated 7x7 correlation
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not TASK3_REPORT.exists(), reason="Task 3 report absent")
class TestCalibratedCorrelation:
    def test_matrix_psd_and_validator_passes(self):
        corr7, _ = calibrated_seven_driver_correlation()
        C = corr7.matrix(-0.25)
        w = np.linalg.eigvalsh(C)
        assert w.min() > 0.0
        C_t = tuple(tuple(float(v) for v in row) for row in C)
        assert CorrelationMatrixValidator().validate_matrix(C_t, repair=False).passed

    def test_six_driver_block_unchanged(self):
        corr7, _ = calibrated_seven_driver_correlation()
        C_cal = corr7.matrix(-0.25)
        C_ph = SevenDriverCorrelation().matrix(-0.25)
        assert np.array_equal(C_cal[:6, :6], C_ph[:6, :6])

    def test_cholesky_rows_0_to_5_independent_of_couplings(self):
        """The CRN slice-reuse justification at the matrix level."""
        corr7, _ = calibrated_seven_driver_correlation()
        L_cal = corr7.cholesky(-0.25)
        L_ph = SevenDriverCorrelation().cholesky(-0.25)
        assert np.array_equal(L_cal[:6, :6], L_ph[:6, :6])
        assert not np.array_equal(L_cal[6, :], L_ph[6, :])


# ---------------------------------------------------------------------------
# Outer-state bit-identity (CRN slice reuse justification, end to end)
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not TASK3_REPORT.exists(), reason="Task 3 report absent")
def test_outer_columns_0_to_5_bit_identical_under_coupling_change():
    corr_cal, _ = calibrated_seven_driver_correlation()
    notional, _ = calibrated_liquidity_exposure_notional()
    agg_cal = SevenDriverLiquidityRiskAggregator(
        _product(),
        liquidity_exposure=LiquidityExposureSpec(exposure_notional=notional),
        correlation7=corr_cal,
    )
    agg_ph = SevenDriverLiquidityRiskAggregator(_product())
    o_cal = agg_cal._outer_states_7d(8, 12, Measure.P, 42)
    o_ph = agg_ph._outer_states_7d(8, 12, Measure.P, 42)
    assert np.array_equal(o_cal[:, :6], o_ph[:, :6])
    assert not np.array_equal(o_cal[:, 6], o_ph[:, 6])


# ---------------------------------------------------------------------------
# Baseline-centred exposure impact under the calibrated notional
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not TASK3_REPORT.exists(), reason="Task 3 report absent")
class TestCalibratedExposureImpact:
    def test_zero_at_initial_premium_and_monotone(self):
        params = calibrated_liquidity_params()
        notional, _ = calibrated_liquidity_exposure_notional()
        spec = LiquidityExposureSpec(exposure_notional=notional)
        l0 = params.initial_premium
        grid = np.array([l0 - 0.002, l0, l0 + 0.002, l0 + 0.01])
        impact = spec.liability_impact(grid, params, 19.0)
        assert impact[1] == pytest.approx(0.0, abs=1e-12)
        assert np.all(np.diff(impact) > 0.0)

    def test_impact_scales_with_notional(self):
        params = calibrated_liquidity_params()
        l_h = params.initial_premium + 0.01
        a = LiquidityExposureSpec(22_000.0).liability_impact(l_h, params, 19.0)
        b = LiquidityExposureSpec(30_000.0).liability_impact(l_h, params, 19.0)
        assert float(a) == pytest.approx(float(b) * 22.0 / 30.0, rel=1e-12)

    def test_haircut_in_unit_interval(self):
        params = calibrated_liquidity_params()
        h = cir_affine_haircut(
            np.array([0.0, 0.005, 0.02, 0.10]), params, 19.0
        )
        assert np.all(h >= 0.0) and np.all(h < 1.0)


# ---------------------------------------------------------------------------
# Persisted Task 4 report integrity
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not TASK4_REPORT.exists(), reason="Task 4 report not built")
class TestTask4Report:
    @pytest.fixture(scope="class")
    def report(self):
        return json.loads(TASK4_REPORT.read_text(encoding="utf-8"))

    def test_verdict_pass_and_audit_ok(self, report):
        assert report["aggregation"]["verdict"] == "PASS"
        assert report["audit_integrity_ok"] is True

    def test_calibrated_inputs_recorded_not_placeholder(self, report):
        cal = report["calibration_inputs"]
        assert cal["exposure_is_placeholder"] is False
        assert cal["couplings_are_placeholder"] is False
        assert cal["exposure_notional"] == pytest.approx(22_000.0)
        assert report["aggregation"]["liquidity_exposure_notional"] == pytest.approx(22_000.0)

    def test_notes_flag_calibrated_wording(self, report):
        notes = " ".join(report["aggregation"]["notes"])
        assert "G-LIQX-CALIBRATED" in notes
        assert "no longer placeholders" in notes

    def test_comparison_vs_placeholder_baseline(self, report):
        comp = report["comparison_vs_placeholder"]
        assert comp["baseline_available"] is True
        s = comp["standalone_scr_liquidity"]
        # calibrated notional 22,000 < placeholder 30,000 -> smaller standalone SCR
        assert s["calibrated"] < s["placeholder"]
        assert comp["var_covar_scr"]["placeholder"] > 0.0
        assert comp["nested_scr"]["calibrated"] > 0.0

    def test_seven_drivers_and_correlation_valid(self, report):
        agg = report["aggregation"]
        assert list(agg["drivers"]) == [
            "rate", "equity", "credit", "lapse", "mortality", "fx", "liquidity"]
        assert agg["correlation_matrix_passed"] is True
        C = np.array(agg["esg_correlation_matrix"])
        assert C.shape == (7, 7)
        est = json.loads(TASK3_REPORT.read_text(encoding="utf-8"))["estimated_couplings"]
        for j, name in enumerate(COUPLING_NAMES):
            assert C[6, j] == pytest.approx(round(est[name], 4), abs=5e-5)

    def test_tail_diagnostics_rerun_and_converged(self, report):
        td = report["aggregation"]["tail_diagnostics"]
        assert td["converged"] is True
        assert td["successive_var_rel_deltas"][-1] <= 0.01
        assert td["variance_reduction"]["qmc_variance_reduction_ratio"] > 1.0

    def test_governance_recorded(self, report):
        assert report["change_record_status"] == "OWNER_REVIEW"
        assert report["mr010_status"] == "MITIGATED"
        assert report["mr012_status"] == "MITIGATED"
