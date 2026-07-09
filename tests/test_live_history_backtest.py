"""
Tests for the item-#6 live-history backtest bridge
==================================================

Covers (roadmap §4.1 #6 DoD: "populate BacktestEngine with live CNY curve /
CSI 300 series (item 1 dependency); Kupiec POF + coverage tests on >=10y
history; recalibration triggers evaluated"):

  * scipy-free Kupiec chi-square(df=1) survival hardening (offline CI),
  * annual-history loader resolving through item #1's pipeline tiers + SHA-256,
  * the history source satisfying the Phase-13 contract,
  * an end-to-end >=10y backtest producing Kupiec POF + coverage + G-09,
  * the structured recalibration-trigger evaluation,
  * governed-headline isolation (no run_model import, no headline artifact).

unittest only (scipy / pytest are unavailable in the offline sandbox).
"""

import json
import math
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from par_model_v2.calibration.backtesting import (
    BacktestResult,
    _chi2_sf_df1,
    _kupiec_pof_pvalue,
)
from par_model_v2.risk.risk_metrics import ConfidenceLevel
from par_model_v2.calibration.live_market_data_pipeline import SnapshotCache
from par_model_v2.calibration.market_data_source import DataLineageRecord
from par_model_v2.calibration.live_history_backtest import (
    DEFAULT_HISTORY_FIXTURE,
    SCHEMA,
    CNYBacktestHistoryLoader,
    PipelineBacktestHistorySource,
    RecalibrationTriggerReport,
    _AnnualBacktestHistoryInterface,
    evaluate_recalibration_triggers,
    run_live_history_backtest,
)


def _mk_result(
    rate_cov=0.9,
    eq_cov=0.9,
    var95_exc=0.05,
    var99_exc=0.0,
    kupiec95=0.5,
    kupiec99=0.5,
    martingale_pass=True,
    requires_recal=False,
):
    """Build a minimal BacktestResult for trigger unit tests."""
    mg = pd.DataFrame({"horizon_years": [1.0], "passed": [martingale_pass]})
    mg.attrs["all_pass"] = bool(martingale_pass)
    detail = pd.DataFrame({"realised_loss": [1.0], "var95": [2.0], "var99": [3.0]})
    return BacktestResult(
        detail=detail,
        rate_coverage_pct=rate_cov,
        equity_coverage_pct=eq_cov,
        var95_exception_rate=var95_exc,
        var99_exception_rate=var99_exc,
        es95_mean=0.0,
        es99_mean=0.0,
        kupiec_pvalue_95=kupiec95,
        kupiec_pvalue_99=kupiec99,
        martingale_results=mg,
        requires_recalibration=requires_recal,
        run_id="test",
    )


class TestScipyFreeKupiec(unittest.TestCase):
    def test_chi2_sf_df1_known_values(self):
        self.assertAlmostEqual(_chi2_sf_df1(0.0), 1.0, places=12)
        self.assertAlmostEqual(_chi2_sf_df1(3.8414588), 0.05, places=4)
        self.assertAlmostEqual(_chi2_sf_df1(6.6348966), 0.01, places=4)

    def test_chi2_sf_df1_matches_erfc_identity(self):
        for x in (0.0, 0.5, 1.0, 2.7, 5.0, 10.0):
            self.assertAlmostEqual(_chi2_sf_df1(x), math.erfc(math.sqrt(x / 2.0)), places=12)

    def test_chi2_sf_df1_monotone_in_unit_interval(self):
        xs = [0.0, 1.0, 2.0, 4.0, 8.0]
        vals = [_chi2_sf_df1(x) for x in xs]
        for v in vals:
            self.assertGreaterEqual(v, 0.0)
            self.assertLessEqual(v, 1.0)
        self.assertTrue(all(vals[i] > vals[i + 1] for i in range(len(vals) - 1)))

    def test_kupiec_pvalue_runs_without_scipy(self):
        p0 = _kupiec_pof_pvalue(0, 12, ConfidenceLevel.CL_95)
        p1 = _kupiec_pof_pvalue(1, 12, ConfidenceLevel.CL_95)
        for p in (p0, p1):
            self.assertGreaterEqual(p, 0.0)
            self.assertLessEqual(p, 1.0)
        with self.assertRaises(ValueError):
            _kupiec_pof_pvalue(0, 0, ConfidenceLevel.CL_95)
        with self.assertRaises(ValueError):
            _kupiec_pof_pvalue(13, 12, ConfidenceLevel.CL_95)


class TestAnnualHistoryInterface(unittest.TestCase):
    def test_rejects_too_few_rows(self):
        iface = _AnnualBacktestHistoryInterface()
        frame = pd.DataFrame(
            {"year": [2014, 2015], "start_short_rate": [0.03, 0.03],
             "end_short_rate": [0.03, 0.03], "equity_return": [0.1, 0.1]}
        )
        with self.assertRaises(ValueError):
            iface.validate_frame(frame)

    def test_rejects_out_of_bounds_and_nonmonotone(self):
        iface = _AnnualBacktestHistoryInterface()
        base = {"year": list(range(2014, 2026)),
                "start_short_rate": [0.03] * 12, "end_short_rate": [0.03] * 12,
                "equity_return": [0.1] * 12}
        bad_rate = dict(base); bad_rate["end_short_rate"] = [0.03] * 11 + [0.99]
        with self.assertRaises(ValueError):
            iface.validate_frame(pd.DataFrame(bad_rate))
        dup = dict(base); dup["year"] = [2014] * 12
        with self.assertRaises(ValueError):
            iface.validate_frame(pd.DataFrame(dup))


class TestPipelineLoaderProvenance(unittest.TestCase):
    def test_fixture_tier_and_sha(self):
        with tempfile.TemporaryDirectory() as d:
            loader = CNYBacktestHistoryLoader(SnapshotCache(Path(d)))
            res = loader.load()
            self.assertEqual(res.provenance, "file_fixture")
            self.assertTrue(res.sha256)
            self.assertEqual(len(res.frame), 12)
            for col in ("year", "start_short_rate", "end_short_rate", "equity_return"):
                self.assertIn(col, res.frame.columns)
            recs = CNYBacktestHistoryLoader.to_annual_records(res)
            self.assertEqual(len(recs), 12)
            self.assertEqual([r["year"] for r in recs], sorted(r["year"] for r in recs))
            self.assertEqual(set(recs[0]), {"year", "start_short_rate", "end_short_rate", "equity_return"})

    def test_cache_promotion_second_load(self):
        with tempfile.TemporaryDirectory() as d:
            cache = SnapshotCache(Path(d))
            first = CNYBacktestHistoryLoader(cache).load()
            self.assertEqual(first.provenance, "file_fixture")
            # a fixture load seals a snapshot; a second load now resolves the
            # cached tier (item #1's three-tier resolution), same sealed sha.
            second = CNYBacktestHistoryLoader(cache).load()
            self.assertEqual(second.provenance, "cached_snapshot")
            self.assertEqual(second.sha256, first.sha256)


class TestPipelineSource(unittest.TestCase):
    def test_source_contract(self):
        with tempfile.TemporaryDirectory() as d:
            src = PipelineBacktestHistorySource(cache_dir=Path(d))
            self.assertEqual(src.market, "CNY")
            self.assertEqual(src.provenance, "file_fixture")
            recs = src.fetch_annual_records()
            self.assertGreaterEqual(len(recs), 10)
            basis = src.fetch_loss_basis()
            self.assertEqual(
                set(basis),
                {"base_equity_index", "deterministic_discount_rate",
                 "guarantee_notional", "equity_weight", "duration_years"},
            )
            in_years, oos_years = src.fetch_window_years()
            self.assertEqual(len(in_years), 7)
            self.assertEqual(len(oos_years), 5)
            self.assertIsInstance(src.build_lineage_record(), DataLineageRecord)


class TestEndToEnd(unittest.TestCase):
    def test_run_ge_10y_kupiec_coverage_and_gate(self):
        with tempfile.TemporaryDirectory() as d:
            art = Path(d) / "LIVE_HISTORY_BACKTEST.json"
            rep = run_live_history_backtest(
                cache_dir=Path(d) / "cache", n_scenarios=400, seed=7,
                artifact_path=art, write_artifact=True,
            )
            self.assertEqual((rep.n_full, rep.n_in_sample, rep.n_oos), (12, 7, 5))
            self.assertGreaterEqual(rep.n_full, 10)  # >=10y history
            fr = rep.full_summary
            # Kupiec p-values + coverage present, finite, in range.
            for k in ("kupiec_pvalue_95", "kupiec_pvalue_99"):
                self.assertGreaterEqual(fr[k], 0.0)
                self.assertLessEqual(fr[k], 1.0)
            for k in ("rate_coverage_pct", "equity_coverage_pct"):
                self.assertGreaterEqual(fr[k], 0.0)
                self.assertLessEqual(fr[k], 1.0)
            # G-09 data criteria hold on this seeded fixture -> gate PASS.
            self.assertGreaterEqual(fr["rate_coverage_pct"], 0.70)
            self.assertGreaterEqual(fr["equity_coverage_pct"], 0.70)
            self.assertGreater(fr["kupiec_pvalue_95"], 0.05)
            self.assertLessEqual(fr["var99_exception_rate"], 0.05)
            self.assertEqual(rep.gate_g09["status"], "PASS")
            self.assertEqual(rep.provenance, "file_fixture")
            self.assertTrue(rep.unsigned)
            # artifact persisted and round-trips
            self.assertTrue(art.exists())
            j = json.loads(art.read_text())
            self.assertEqual(j["schema"], SCHEMA)
            self.assertIn("recalibration", j)
            self.assertIn("gate_g09", j)

    def test_inputs_digest_idempotent(self):
        with tempfile.TemporaryDirectory() as d:
            a = run_live_history_backtest(cache_dir=Path(d) / "a", n_scenarios=300, seed=11, write_artifact=False)
            b = run_live_history_backtest(cache_dir=Path(d) / "b", n_scenarios=300, seed=11, write_artifact=False)
            self.assertEqual(a.inputs_digest, b.inputs_digest)
            self.assertEqual(a.data_sha256, b.data_sha256)


class TestRecalibrationTriggers(unittest.TestCase):
    def test_all_pass_no_action(self):
        rep = evaluate_recalibration_triggers(_mk_result())
        self.assertIsInstance(rep, RecalibrationTriggerReport)
        self.assertEqual(rep.n_breached, 0)
        self.assertEqual(rep.max_severity, "NONE")
        self.assertEqual(rep.recommendation, "NO_ACTION_MONITOR")
        json.dumps(rep.to_dict())  # JSON-serialisable

    def test_coverage_breach_is_critical(self):
        rep = evaluate_recalibration_triggers(_mk_result(rate_cov=0.5))
        self.assertIn("rate_band_coverage", rep.breached_names())
        self.assertEqual(rep.max_severity, "CRITICAL")
        self.assertEqual(rep.recommendation, "RECALIBRATION_REQUIRED")

    def test_kupiec_breach_schedules(self):
        rep = evaluate_recalibration_triggers(_mk_result(kupiec95=0.01))
        self.assertIn("kupiec_var95_pof", rep.breached_names())
        self.assertEqual(rep.recommendation, "SCHEDULE_RECALIBRATION")

    def test_var95_only_is_enhanced_monitoring(self):
        rep = evaluate_recalibration_triggers(_mk_result(var95_exc=0.5))
        self.assertIn("var95_breach_rate", rep.breached_names())
        self.assertEqual(rep.recommendation, "ENHANCED_MONITORING")

    def test_martingale_failure_is_critical(self):
        rep = evaluate_recalibration_triggers(_mk_result(martingale_pass=False))
        self.assertIn("martingale_q_measure", rep.breached_names())
        self.assertEqual(rep.recommendation, "RECALIBRATION_REQUIRED")

    def test_oos_drift_trigger(self):
        full = _mk_result(rate_cov=0.9, eq_cov=0.9)
        oos = _mk_result(rate_cov=0.5, eq_cov=0.9)  # 0.4 drift > 0.20
        rep = evaluate_recalibration_triggers(full, oos)
        self.assertIn("oos_coverage_drift", rep.breached_names())
        # every trigger exposes its observed/threshold/comparator
        for t in rep.triggers:
            self.assertIn(t.comparator, (">=", ">", "<="))
            self.assertIsInstance(t.observed, float)
            self.assertIsInstance(t.threshold, float)


class TestGovernedHeadlineIsolation(unittest.TestCase):
    def test_module_does_not_import_run_model(self):
        src = Path("par_model_v2/calibration/live_history_backtest.py").read_text()
        self.assertNotIn("run_model", src)
        self.assertNotIn("RUN_MODEL_AGGREGATION_REPORT", src)

    def test_write_artifact_false_writes_nothing(self):
        with tempfile.TemporaryDirectory() as d:
            art = Path(d) / "should_not_exist.json"
            run_live_history_backtest(
                cache_dir=Path(d) / "c", n_scenarios=200, seed=3,
                artifact_path=art, write_artifact=False,
            )
            self.assertFalse(art.exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
