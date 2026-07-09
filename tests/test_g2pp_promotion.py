"""Roadmap 4.1 #7 - G2++ two-factor rate-model production promotion.

Covers: rate_model selector + fail-loud resolution, the HW1F byte-identity
fallback guarantee, G2++ factor columns / reproducibility / measure + bounds
enforcement, Q-measure martingale evidence on the promoted G2++ path, the
CurveTwistValidator (genuine non-parallel twist vs the one-factor benchmark),
the G2++ parameter snapshot, and the swaption-calibration -> generate ->
martingale evidence chain. numpy/pandas + unittest only (scipy-free).
"""

import hashlib
import unittest

import numpy as np
import pandas as pd

import par_model_v2.stochastic.esg_process as e


# Pinned digest of the governed default (HW1F) Q path. If this ever changes,
# a supposedly-additive edit has moved a governed headline - fail loudly.
HW1F_Q_DIGEST = "1aa0b3f4cc460a2f85477d3548a998346a8e9fdaa18056dcadefd564677b8d1a"
HW1F_P_DIGEST = "bf7ede63cdbdb5e99be1cc8882caeaf11f98a75203f557d33adb5c0ed78ce37e"

_GOVERNED_COLS = [
    "scenario_id", "month", "r_short", "zcb_1y", "zcb_10y",
    "equity_index", "equity_return_1m", "measure",
]


def _digest(df):
    cols = [c for c in _GOVERNED_COLS if c in df.columns]
    return hashlib.sha256(df[cols].round(12).to_csv(index=False).encode()).hexdigest()


def _cny_curve():
    return e.RiskFreeCurve(
        tenors_years=(0.25, 1, 2, 3, 5, 7, 10, 20, 30),
        zero_rates=(0.018, 0.020, 0.022, 0.024, 0.026, 0.028, 0.030, 0.032, 0.033),
        currency="CNY", market="CNY",
    )


# G2++ generation has a per-row ZCB loop, so the heavy scenario sets used by the
# martingale / curve-twist tests are built ONCE and shared (N=600 already
# reconciles the antithetic martingale to ~2.2% rel err, well inside tolerance).
_SHARED = {}


def _shared():
    if not _SHARED:
        curve = _cny_curve()
        _SHARED["curve"] = curve
        _SHARED["g2"] = e.ScenarioSet.generate(
            n=600, T_months=120, measure=e.Measure.Q, seed=42,
            rate_model="g2pp", initial_curve=curve)
        _SHARED["hw"] = e.ScenarioSet.generate(
            n=600, T_months=120, measure=e.Measure.Q, seed=42,
            rate_model="hw1f", initial_curve=curve)
    return _SHARED


class TestRateModelResolver(unittest.TestCase):
    def test_none_defaults_to_hw1f(self):
        self.assertEqual(e.resolve_rate_model(None), "hw1f")
        self.assertEqual(e.DEFAULT_RATE_MODEL, "hw1f")

    def test_aliases_map_to_canonical(self):
        for a in ("hw1f", "HW1F", "hull-white", "Hull_White", "one-factor", " hw "):
            self.assertEqual(e.resolve_rate_model(a), "hw1f")
        for a in ("g2pp", "G2++", "g2plus", "two-factor", " G2PP ", "g2"):
            self.assertEqual(e.resolve_rate_model(a), "g2pp")

    def test_unknown_is_fail_loud(self):
        with self.assertRaises(ValueError):
            e.resolve_rate_model("garch")
        with self.assertRaises(ValueError):
            e.resolve_rate_model("vasicek")

    def test_available_models(self):
        self.assertEqual(e.available_rate_models(), ("g2pp", "hw1f"))


class TestHW1FByteIdentityFallback(unittest.TestCase):
    """The default path MUST be byte-for-byte unchanged (governed headline)."""

    def test_default_matches_pinned_digest(self):
        q = e.ScenarioSet.generate(n=200, T_months=120, measure=e.Measure.Q, seed=42)
        p = e.ScenarioSet.generate(n=200, T_months=120, measure=e.Measure.P, seed=42)
        self.assertEqual(_digest(q.data), HW1F_Q_DIGEST)
        self.assertEqual(_digest(p.data), HW1F_P_DIGEST)

    def test_explicit_hw1f_equals_default(self):
        d = e.ScenarioSet.generate(n=200, T_months=120, measure=e.Measure.Q, seed=42)
        x = e.ScenarioSet.generate(n=200, T_months=120, measure=e.Measure.Q, seed=42,
                                   rate_model="hw1f")
        self.assertEqual(_digest(d.data), _digest(x.data))

    def test_default_has_no_g2pp_columns(self):
        d = e.ScenarioSet.generate(n=100, T_months=36, measure=e.Measure.Q, seed=7)
        self.assertNotIn("g2pp_x", d.data.columns)
        self.assertNotIn("g2pp_y", d.data.columns)

    def test_default_snapshot_all_numeric_and_hw1f(self):
        d = e.ScenarioSet.generate(n=100, T_months=36, measure=e.Measure.Q, seed=7)
        params = d.parameter_snapshot.to_dict()["parameters"]
        # every parameter value must be a finite number (no string markers)
        for k, v in params.items():
            self.assertTrue(np.isfinite(float(v)), k)
        self.assertTrue(any(k.startswith("rate.hw1f.") for k in params))
        self.assertFalse(any(k.startswith("rate.g2pp.") for k in params))
        self.assertIn("HW1F", d.parameter_snapshot.discretisation)


class TestG2PPSelectable(unittest.TestCase):
    def test_g2pp_adds_factor_columns(self):
        g = e.ScenarioSet.generate(n=300, T_months=60, measure=e.Measure.Q, seed=42,
                                   rate_model="g2pp", initial_curve=_cny_curve())
        self.assertIn("g2pp_x", g.data.columns)
        self.assertIn("g2pp_y", g.data.columns)
        self.assertEqual(len(g.data), 300 * (60 + 1))
        # the base governed columns are all still present
        for c in _GOVERNED_COLS:
            self.assertIn(c, g.data.columns)

    def test_g2pp_reproducible_and_alias_stable(self):
        a = e.ScenarioSet.generate(n=250, T_months=48, measure=e.Measure.Q, seed=11,
                                   rate_model="g2pp", initial_curve=_cny_curve())
        b = e.ScenarioSet.generate(n=250, T_months=48, measure=e.Measure.Q, seed=11,
                                   rate_model="G2++", initial_curve=_cny_curve())
        c = e.ScenarioSet.generate(n=250, T_months=48, measure=e.Measure.Q, seed=99,
                                   rate_model="g2pp", initial_curve=_cny_curve())
        self.assertTrue(a.data["r_short"].equals(b.data["r_short"]))
        self.assertTrue(a.data["g2pp_x"].equals(b.data["g2pp_x"]))
        self.assertFalse(np.allclose(a.data["r_short"], c.data["r_short"]))

    def test_g2pp_does_not_perturb_hw1f_stream(self):
        # generating g2pp must not change what hw1f produces (independent draws)
        before = _digest(e.ScenarioSet.generate(n=200, T_months=120,
                                                 measure=e.Measure.Q, seed=42).data)
        e.ScenarioSet.generate(n=200, T_months=120, measure=e.Measure.Q, seed=42,
                               rate_model="g2pp", initial_curve=_cny_curve())
        after = _digest(e.ScenarioSet.generate(n=200, T_months=120,
                                               measure=e.Measure.Q, seed=42).data)
        self.assertEqual(before, after)
        self.assertEqual(after, HW1F_Q_DIGEST)

    def test_g2pp_measure_enforced(self):
        with self.assertRaises(Exception):
            e.ScenarioSet.generate(n=50, T_months=12, measure="not-a-measure",
                                   rate_model="g2pp")
        for m in (e.Measure.P, e.Measure.Q):
            g = e.ScenarioSet.generate(n=60, T_months=24, measure=m, seed=3,
                                       rate_model="g2pp", initial_curve=_cny_curve())
            self.assertEqual(set(g.data["measure"].unique()), {m.value})

    def test_g2pp_rate_bounds_respected(self):
        params = e.G2PlusParams(short_rate_floor=-0.01, short_rate_ceiling=0.09)
        g = e.ScenarioSet.generate(n=400, T_months=120, measure=e.Measure.P, seed=5,
                                   rate_model="g2pp", g2_params=params,
                                   initial_curve=_cny_curve())
        self.assertGreaterEqual(g.data["r_short"].min(), -0.01 - 1e-12)
        self.assertLessEqual(g.data["r_short"].max(), 0.09 + 1e-12)


class TestG2PPMartingale(unittest.TestCase):
    def test_q_measure_martingale_passes(self):
        sh = _shared()
        report = e.QMeasureMartingaleValidator().validate(sh["curve"], sh["g2"].data)
        self.assertTrue(report.passed, [c.to_dict() for c in report.failed_checks()])


class TestCurveTwistValidator(unittest.TestCase):
    def setUp(self):
        sh = _shared()
        self.curve = sh["curve"]
        self.g2 = sh["g2"]
        self.hw = sh["hw"]

    def test_g2pp_passes_twist_hw1f_fails(self):
        v = e.CurveTwistValidator()
        rg = v.validate(self.g2.data, benchmark_data=self.hw.data, rate_model="g2pp")
        rh = v.validate(self.hw.data, rate_model="hw1f")
        self.assertTrue(rg.passed, [c.to_dict() for c in rg.failed_checks()])
        # a one-factor model cannot produce genuine twist -> decorrelation check fails
        self.assertFalse(rh.passed)

    def test_g2pp_more_decorrelated_than_benchmark(self):
        v = e.CurveTwistValidator()
        rg = v.validate(self.g2.data, benchmark_data=self.hw.data, rate_model="g2pp")
        g2c = rg.diagnostics["short_long_change_correlation"]
        hwc = rg.diagnostics["benchmark_short_long_change_correlation"]
        self.assertLess(g2c, hwc)
        self.assertGreater(rg.diagnostics["decorrelation_gap_vs_benchmark"], 0.02)

    def test_factor_correlation_recovered(self):
        # empirical corr of factor increments should recover the param (-0.70)
        v = e.CurveTwistValidator()
        rg = v.validate(self.g2.data, rate_model="g2pp")
        self.assertAlmostEqual(rg.diagnostics["factor_change_correlation"], -0.70,
                               delta=0.05)

    def test_missing_columns_fail_loud(self):
        v = e.CurveTwistValidator()
        bad = self.g2.data.drop(columns=["zcb_10y"])
        rep = v.validate(bad, rate_model="g2pp")
        self.assertFalse(rep.passed)
        self.assertEqual(rep.checks[0].check_id, "CT-COLUMNS")

    def test_constructor_guards(self):
        with self.assertRaises(ValueError):
            e.CurveTwistValidator(max_twist_correlation=1.5)
        with self.assertRaises(ValueError):
            e.CurveTwistValidator(short_tenor_years=10.0, long_tenor_years=1.0)

    def test_report_to_dict_roundtrip(self):
        v = e.CurveTwistValidator()
        rep = v.validate(self.g2.data, benchmark_data=self.hw.data, rate_model="g2pp")
        d = rep.to_dict()
        self.assertEqual(d["rate_model"], "g2pp")
        self.assertIn("checks", d)
        self.assertTrue(all("check_id" in c for c in d["checks"]))


class TestG2PPSnapshot(unittest.TestCase):
    def test_snapshot_records_g2pp_params(self):
        g = e.ScenarioSet.generate(n=120, T_months=36, measure=e.Measure.Q, seed=1,
                                   rate_model="g2pp", initial_curve=_cny_curve())
        params = g.parameter_snapshot.to_dict()["parameters"]
        self.assertGreaterEqual(sum(k.startswith("rate.g2pp.") for k in params), 10)
        self.assertEqual(sum(k.startswith("rate.hw1f.") for k in params), 0)
        for k, v in params.items():
            self.assertTrue(np.isfinite(float(v)), k)
        self.assertEqual(g.parameter_snapshot.model_equation_refs[0],
                         "G2PlusRateProcess._simulate_arrays")
        self.assertIn("G2++", g.parameter_snapshot.discretisation)
        self.assertTrue(g.parameter_snapshot.is_placeholder)


class TestSwaptionCalibrationChain(unittest.TestCase):
    """Swaption-calibrated G2++ params flow through the promoted ESG path."""

    def test_calibrated_params_generate_and_reconcile(self):
        try:
            import par_model_v2.stochastic.g2pp_swaption as sw
        except Exception as exc:  # pragma: no cover
            self.skipTest("g2pp_swaption unavailable: {}".format(exc))
        cal = sw.calibrate_g2pp_to_swaptions()
        self.assertTrue(cal.converged)
        params = cal.params
        self.assertIsInstance(params, e.G2PlusParams)
        curve = _cny_curve()
        g = e.ScenarioSet.generate(n=600, T_months=120, measure=e.Measure.Q, seed=42,
                                   rate_model="g2pp", g2_params=params,
                                   initial_curve=curve)
        report = e.QMeasureMartingaleValidator().validate(curve, g.data)
        self.assertTrue(report.passed, [c.to_dict() for c in report.failed_checks()])
        twist = e.CurveTwistValidator().validate(g.data, rate_model="g2pp")
        self.assertTrue(twist.passed)


if __name__ == "__main__":
    unittest.main(verbosity=2)
