"""
Tests for Phase 13 Task 5 — Live-Data Out-of-Sample Backtest (Gate G-09).

Covers the live backtest-history data source, the dataset loader and
in/out-of-sample split, in-sample calibration, the G-09 gate evaluator, and the
end-to-end orchestrator (governance audit entry + populated annual report).
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from par_model_v2.calibration.phase13_backtest import (
    G09_COVERAGE_MIN,
    G09_MIN_OBSERVATIONS,
    FileBasedBacktestHistorySource,
    LiveBacktestDataLoader,
    build_file_based_backtest_loader,
    calibrate_from_history,
    evaluate_g09_gate,
    run_phase13_backtest,
)
from par_model_v2.calibration.backtesting import BacktestDataset
from par_model_v2.calibration.calibration_framework import CalibrationResult
from par_model_v2.governance.audit_trail import GovernanceStore

FIXTURE_NAME = "cny_backtest_history_20260101.json"
N_SCEN = 800
SEED = 20260604


def _fixture_path() -> Path:
    return Path("par_model_v2/calibration/fixtures") / FIXTURE_NAME


# --------------------------------------------------------------------------
# Data source
# --------------------------------------------------------------------------
class TestBacktestHistorySource:
    def test_loads_at_least_ten_records(self):
        src = FileBasedBacktestHistorySource(_fixture_path())
        recs = src.fetch_annual_records()
        assert len(recs) >= G09_MIN_OBSERVATIONS
        assert src.market == "CNY"

    def test_record_fields_typed(self):
        src = FileBasedBacktestHistorySource(_fixture_path())
        r = src.fetch_annual_records()[0]
        assert set(r) == {"year", "start_short_rate", "end_short_rate", "equity_return"}
        assert isinstance(r["year"], int)
        assert isinstance(r["start_short_rate"], float)

    def test_lineage_has_source_and_checksum(self):
        src = FileBasedBacktestHistorySource(_fixture_path())
        lin = src.build_lineage_record()
        assert lin.market == "CNY"
        assert lin.source_detail
        assert len(lin.sha256_checksum) == 64  # real sha256 hex digest

    def test_loss_basis_uses_post_mr001_discount_rate(self):
        src = FileBasedBacktestHistorySource(_fixture_path())
        basis = src.fetch_loss_basis()
        # MR-001: reserving/backtest discount basis at or below the 3.0% cap.
        assert basis["deterministic_discount_rate"] <= 0.030 + 1e-9

    def test_missing_file_raises(self):
        with pytest.raises(FileNotFoundError):
            FileBasedBacktestHistorySource("does/not/exist.json")


# --------------------------------------------------------------------------
# Loader
# --------------------------------------------------------------------------
class TestLiveBacktestDataLoader:
    def test_full_dataset_columns_and_size(self):
        loader = build_file_based_backtest_loader()
        ds = loader.load_full()
        assert isinstance(ds, BacktestDataset)
        assert ds.n_observations >= G09_MIN_OBSERVATIONS
        for col in BacktestDataset.REQUIRED_COLUMNS:
            assert col in ds.observations.columns

    def test_split_is_disjoint_and_covers_full(self):
        loader = build_file_based_backtest_loader()
        in_ds, oos_ds, in_records = loader.load_split()
        full = loader.load_full()
        assert in_ds.n_observations + oos_ds.n_observations == full.n_observations
        assert oos_ds.n_observations >= 1
        assert len(in_records) == in_ds.n_observations

    def test_losses_non_negative(self):
        loader = build_file_based_backtest_loader()
        ds = loader.load_full()
        assert (ds.observations["realised_loss"] >= 0).all()


# --------------------------------------------------------------------------
# Calibration
# --------------------------------------------------------------------------
class TestCalibrateFromHistory:
    def test_returns_non_placeholder_with_sane_params(self):
        loader = build_file_based_backtest_loader()
        _in_ds, _oos_ds, in_records = loader.load_split()
        cal = calibrate_from_history(in_records, calibration_date=date(2026, 1, 1))
        assert isinstance(cal, CalibrationResult)
        assert cal.is_placeholder is False
        assert 0.02 <= cal.a <= 1.0
        assert 0.003 <= cal.sigma_r <= 0.05
        assert 0.10 <= cal.sigma_S <= 0.45
        assert -0.95 <= cal.rho <= 0.95

    def test_requires_two_records(self):
        with pytest.raises(ValueError):
            calibrate_from_history(
                [{"year": 2020, "start_short_rate": 0.02, "end_short_rate": 0.02, "equity_return": 0.0}],
                calibration_date=date(2026, 1, 1),
            )

    def test_buffer_widens_vol(self):
        loader = build_file_based_backtest_loader()
        _i, _o, recs = loader.load_split()
        base = calibrate_from_history(recs, date(2026, 1, 1), param_uncertainty_buffer=1.0)
        buf = calibrate_from_history(recs, date(2026, 1, 1), param_uncertainty_buffer=1.20)
        assert buf.sigma_r >= base.sigma_r
        assert buf.sigma_S >= base.sigma_S


# --------------------------------------------------------------------------
# Gate evaluator
# --------------------------------------------------------------------------
class TestEvaluateG09Gate:
    def _pass_kwargs(self):
        return dict(
            n_observations=12,
            loaded_from_live_file=True,
            rate_coverage_pct=0.80,
            equity_coverage_pct=0.85,
            kupiec_pvalue_95=0.40,
            var99_exception_rate=0.0,
            annual_report_populated=True,
            audit_entry_id="abc123",
        )

    def test_all_criteria_pass(self):
        g = evaluate_g09_gate(**self._pass_kwargs())
        assert g.status == "PASS"
        assert g.gate_id == "G-09"

    def test_fails_when_below_min_obs(self):
        kw = self._pass_kwargs(); kw["n_observations"] = 8
        assert evaluate_g09_gate(**kw).status == "FAIL"

    def test_fails_on_low_coverage(self):
        kw = self._pass_kwargs(); kw["rate_coverage_pct"] = 0.50
        assert evaluate_g09_gate(**kw).status == "FAIL"

    def test_fails_on_kupiec_reject(self):
        kw = self._pass_kwargs(); kw["kupiec_pvalue_95"] = 0.01
        assert evaluate_g09_gate(**kw).status == "FAIL"

    def test_fails_without_audit_entry(self):
        kw = self._pass_kwargs(); kw["audit_entry_id"] = None
        assert evaluate_g09_gate(**kw).status == "FAIL"


# --------------------------------------------------------------------------
# End-to-end orchestrator
# --------------------------------------------------------------------------
class TestRunPhase13Backtest:
    @pytest.fixture(scope="class")
    def result(self, tmp_path_factory):
        d = tmp_path_factory.mktemp("g09")
        gs = GovernanceStore()
        rep = run_phase13_backtest(
            governance_store=gs,
            n_scenarios=N_SCEN,
            seed=SEED,
            annual_report_path=d / "CALIBRATION_BACKTEST_REPORT_2026.md",
            oos_report_path=d / "PHASE13_OOS_BACKTEST_REPORT.md",
        )
        return rep, gs, d

    def test_gate_g09_passes(self, result):
        rep, _gs, _d = result
        assert rep.gate_g09.status == "PASS"

    def test_coverage_meets_threshold(self, result):
        rep, _gs, _d = result
        assert rep.full_result.rate_coverage_pct >= G09_COVERAGE_MIN
        assert rep.full_result.equity_coverage_pct >= G09_COVERAGE_MIN

    def test_var99_breach_within_limit(self, result):
        rep, _gs, _d = result
        assert rep.full_result.var99_exception_rate <= 0.05

    def test_full_series_has_at_least_ten_obs(self, result):
        rep, _gs, _d = result
        assert rep.n_full >= G09_MIN_OBSERVATIONS
        assert rep.n_oos >= 1
        assert rep.n_in_sample + rep.n_oos == rep.n_full

    def test_governance_audit_entry_recorded(self, result):
        rep, gs, _d = result
        assert rep.audit_entry_id is not None
        entries = [e for e in gs.audit_trail._entries]
        assert any(e.entry_id == rep.audit_entry_id for e in entries)

    def test_annual_report_written_and_populated(self, result):
        rep, _gs, d = result
        path = d / "CALIBRATION_BACKTEST_REPORT_2026.md"
        assert path.exists()
        text = path.read_text(encoding="utf-8")
        assert "synthetic development scaffold" not in text
        assert "LIVE realised CNY market history" in text
        assert "Out-of-Sample" in text

    def test_oos_report_json_roundtrips(self, result):
        rep, _gs, d = result
        import json
        j = json.loads((d / "PHASE13_OOS_BACKTEST_REPORT.json").read_text())
        assert j["gate_g09"]["status"] == "PASS"
        assert j["observations"]["full"] >= G09_MIN_OBSERVATIONS

    def test_determinism_same_seed(self, tmp_path):
        gs1 = GovernanceStore(); gs2 = GovernanceStore()
        r1 = run_phase13_backtest(governance_store=gs1, n_scenarios=N_SCEN, seed=SEED,
                                  annual_report_path=tmp_path / "a.md", oos_report_path=tmp_path / "ao.md")
        r2 = run_phase13_backtest(governance_store=gs2, n_scenarios=N_SCEN, seed=SEED,
                                  annual_report_path=tmp_path / "b.md", oos_report_path=tmp_path / "bo.md")
        assert r1.full_result.rate_coverage_pct == r2.full_result.rate_coverage_pct
        assert r1.full_result.var99_exception_rate == r2.full_result.var99_exception_rate
