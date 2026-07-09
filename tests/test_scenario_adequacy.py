"""
Tests - Roadmap §4.1 #5 (C-ROSS gap #6): scenario-adequacy convergence study
============================================================================

Pure-stdlib ``unittest`` (numpy only) so the suite runs without SciPy/pytest.

Covers :mod:`par_model_v2.analysis.scenario_adequacy`:
  * per-count analytic (iid) and empirical (antithetic-aware) Monte-Carlo error,
  * 95% CI bands and the ``1/sqrt(N)`` convergence diagnostics,
  * the analytic scenario-count sizing vs the CBIRC C-ROSS >= 2,000 floor,
  * determinism, the SHA-256 inputs digest, input validation, and the
    JSON / markdown deliverables.

The two heavy studies are computed once at import to keep the suite fast; the
test ladder is small and uses a short-horizon product (the convergence
mechanics are horizon-independent).
"""
from __future__ import annotations

import json
import math
import unittest
import warnings

import numpy as np

from par_model_v2.projection.monthly_projection import ParEndowmentProduct
from par_model_v2.analysis.scenario_adequacy import (
    CBIRC_SCENARIO_FLOOR,
    CONVERGENCE_SCHEMA,
    DEFAULT_DETERMINISTIC_RATE,
    DEFAULT_LADDER,
    SEED_STRIDE,
    Z_95,
    ConvergenceStudyResult,
    run_convergence_study,
)

# Short-horizon representative product (term must be one of 5/10/20).
_PRODUCT = ParEndowmentProduct(
    term_years=5, issue_age=40, gender="M",
    sum_assured=50_000.0, annual_premium=6_000.0,
)
_LADDER = (200, 400, 800)
_REPL = 5
_SEED = 7


def _run(**kw) -> ConvergenceStudyResult:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return run_convergence_study(product=_PRODUCT, **kw)


# Heavy studies computed once.
RES_EMP = _run(ladder=_LADDER, replications=_REPL, seed_base=_SEED)
RES_IID = _run(ladder=_LADDER, replications=1, seed_base=_SEED)


class TestEmpiricalStudy(unittest.TestCase):
    def test_schema_and_shape(self):
        self.assertEqual(RES_EMP.schema, CONVERGENCE_SCHEMA)
        self.assertEqual(tuple(RES_EMP.ladder), _LADDER)
        self.assertEqual([p.n_scenarios for p in RES_EMP.points], list(_LADDER))
        self.assertEqual(RES_EMP.error_model, "empirical_antithetic")
        self.assertEqual(RES_EMP.deterministic_discount_rate,
                         DEFAULT_DETERMINISTIC_RATE)

    def test_seeds_distinct_and_offset(self):
        for p in RES_EMP.points:
            self.assertEqual(len(p.seeds), _REPL)
            self.assertEqual(p.seeds[0], _SEED)
            self.assertEqual(len(set(p.seeds)), _REPL)
            self.assertEqual(p.seeds[1], _SEED + SEED_STRIDE)

    def test_iid_se_identity(self):
        for p in RES_EMP.points:
            self.assertAlmostEqual(
                p.se_iid, p.pv_std / math.sqrt(p.n_scenarios), places=9
            )

    def test_empirical_error_model(self):
        for p in RES_EMP.points:
            self.assertIsNotNone(p.se_empirical)
            self.assertEqual(p.effective_se, p.se_empirical)
            self.assertGreater(p.se_empirical, 0.0)
            self.assertLess(p.se_empirical, p.se_iid)  # antithetic reduction
            self.assertAlmostEqual(
                p.variance_reduction_factor, p.se_iid / p.se_empirical, places=6
            )
        self.assertGreater(RES_EMP.variance_reduction_factor, 2.0)

    def test_ci_band_construction(self):
        for p in RES_EMP.points:
            half = Z_95 * p.effective_se
            self.assertAlmostEqual(p.ci95_half_width, half, places=9)
            self.assertAlmostEqual(p.ci95_low, p.tvog - half, places=9)
            self.assertAlmostEqual(p.ci95_high, p.tvog + half, places=9)
            self.assertAlmostEqual(p.rel_ci_half_width, half / abs(p.tvog), places=9)
            self.assertGreaterEqual(p.tvog, p.ci95_low)
            self.assertLessEqual(p.tvog, p.ci95_high)

    def test_ci_half_width_decreases_with_n(self):
        hw = [p.ci95_half_width for p in RES_EMP.points]
        self.assertTrue(all(b < a for a, b in zip(hw, hw[1:])),
                        "CI half-width should shrink as N grows: %s" % hw)

    def test_scaling_exponent_negative(self):
        self.assertLess(RES_EMP.mc_error_scaling_exponent, 0.0)

    def test_convergence_ratios(self):
        self.assertEqual(len(RES_EMP.convergence_ratios), len(_LADDER) - 1)
        for cr in RES_EMP.convergence_ratios:
            self.assertAlmostEqual(
                cr["theoretical_ratio"],
                math.sqrt(cr["from_n"] / cr["to_n"]), places=4,
            )

    def test_required_n_formula(self):
        c = RES_EMP.se_constant
        denom = abs(RES_EMP.tvog_reference)
        expected = int(math.ceil((Z_95 * c / (RES_EMP.rel_tol * denom)) ** 2))
        self.assertEqual(RES_EMP.required_n_for_rel_tol, expected)
        self.assertAlmostEqual(
            RES_EMP.se_constant,
            RES_EMP.se_reference * math.sqrt(RES_EMP.n_reference), places=6,
        )

    def test_empirical_needs_fewer_than_iid(self):
        self.assertLessEqual(RES_EMP.required_n_for_rel_tol, RES_EMP.required_n_iid)

    def test_recommendation_respects_floor(self):
        req_rounded = int(math.ceil(RES_EMP.required_n_for_rel_tol / 500.0) * 500)
        self.assertEqual(RES_EMP.recommended_n,
                         max(CBIRC_SCENARIO_FLOOR, req_rounded))
        self.assertGreaterEqual(RES_EMP.recommended_n, CBIRC_SCENARIO_FLOOR)
        self.assertTrue(RES_EMP.cbirc_floor_satisfied)

    def test_meets_cbirc_floor_flags(self):
        for p in RES_EMP.points:
            self.assertEqual(p.meets_cbirc_floor,
                             p.n_scenarios >= CBIRC_SCENARIO_FLOOR)

    def test_to_dict_json_serialisable(self):
        d = RES_EMP.to_dict()
        s = json.dumps(d)
        self.assertIn(CONVERGENCE_SCHEMA, s)
        self.assertEqual(len(d["points"]), len(_LADDER))
        self.assertIn("sizing", d)
        self.assertIn("diagnostics", d)

    def test_markdown_sections(self):
        md = RES_EMP.to_markdown()
        for token in (
            "Scenario-Adequacy Convergence Study",
            "Convergence report",
            "Runtime benchmark",
            "Recommendation memo",
            "Recommended production scenario count",
            "UNSIGNED",
        ):
            self.assertIn(token, md)

    def test_summary_keys(self):
        s = RES_EMP.summary()
        for k in ("recommended_n", "required_n_for_rel_tol",
                  "variance_reduction_factor", "inputs_digest"):
            self.assertIn(k, s)

    def test_unsigned_note(self):
        self.assertIn("UNSIGNED", RES_EMP.unsigned_note)
        self.assertIn("NOT the governed portfolio TVOG headline",
                      RES_EMP.unsigned_note)


class TestNaiveModel(unittest.TestCase):
    def test_naive_iid_fallback(self):
        self.assertEqual(RES_IID.error_model, "naive_iid")
        self.assertIsNone(RES_IID.variance_reduction_factor)
        for p in RES_IID.points:
            self.assertIsNone(p.se_empirical)
            self.assertAlmostEqual(p.effective_se, p.se_iid, places=12)

    def test_naive_scaling_exponent_near_minus_half(self):
        # iid SE = pv_std / sqrt(N); pv_std ~ const => slope ~ -0.5
        self.assertLess(RES_IID.mc_error_scaling_exponent, -0.4)
        self.assertGreater(RES_IID.mc_error_scaling_exponent, -0.6)


class TestDeterminismAndDigest(unittest.TestCase):
    def test_determinism(self):
        a = _run(ladder=(150, 300), replications=3, seed_base=_SEED)
        b = _run(ladder=(150, 300), replications=3, seed_base=_SEED)
        self.assertEqual([round(p.tvog, 9) for p in a.points],
                         [round(p.tvog, 9) for p in b.points])
        self.assertEqual([round(p.se_empirical, 9) for p in a.points],
                         [round(p.se_empirical, 9) for p in b.points])
        self.assertEqual(a.inputs_digest, b.inputs_digest)

    def test_digest_changes_with_inputs(self):
        base = _run(ladder=(150, 300), replications=2, seed_base=_SEED)
        variants = [
            dict(ladder=(150, 300), replications=2, seed_base=_SEED + 1),
            dict(ladder=(150, 600), replications=2, seed_base=_SEED),
            dict(ladder=(150, 300), replications=2, seed_base=_SEED, rel_tol=0.01),
            dict(ladder=(150, 300), replications=3, seed_base=_SEED),
        ]
        for v in variants:
            self.assertNotEqual(base.inputs_digest, _run(**v).inputs_digest,
                                "digest should change for %s" % v)

    def test_digest_is_sha256_hex(self):
        self.assertEqual(len(RES_IID.inputs_digest), 64)
        int(RES_IID.inputs_digest, 16)


class TestInjectedRunner(unittest.TestCase):
    """A deterministic stub runner is honoured (fast, no ESG generation)."""

    def test_injected_runner_used(self):
        calls = []

        def stub(product, hw, gbm, det_rate, n, seed):
            calls.append((n, seed))
            # deterministic in (n, seed); antithetic-like tiny spread across seeds
            tvog = 1000.0 + 0.001 * seed
            pv_mean = 90000.0
            pv_std = 12000.0
            return (tvog, pv_mean, pv_std, 0.0)

        res = run_convergence_study(
            product=_PRODUCT, ladder=(500, 1000, 2000), replications=4,
            seed_base=100, tvog_runner=stub,
        )
        # every (N, seed) evaluated exactly once
        self.assertEqual(len(calls), 3 * 4)
        # point estimate is the stub's primary-seed value
        self.assertAlmostEqual(res.points[0].tvog, 1000.0 + 0.001 * 100, places=9)
        # iid SE uses the stub pv_std
        self.assertAlmostEqual(
            res.points[0].se_iid, 12000.0 / math.sqrt(500), places=6
        )
        # empirical SE from the 4 stub seeds is tiny but positive
        self.assertGreater(res.points[0].se_empirical, 0.0)
        self.assertEqual(res.error_model, "empirical_antithetic")


class TestValidation(unittest.TestCase):
    def test_bad_inputs_raise(self):
        for bad in (
            dict(ladder=(500,)),
            dict(ladder=(500, 400)),
            dict(ladder=(500, 500)),
            dict(replications=0),
            dict(rel_tol=0.0),
            dict(rel_tol=1.0),
        ):
            with self.assertRaises(ValueError):
                _run(**bad)


class TestDefaults(unittest.TestCase):
    def test_default_constants(self):
        self.assertEqual(DEFAULT_LADDER, (500, 1_000, 2_000, 5_000))
        self.assertEqual(CBIRC_SCENARIO_FLOOR, 2_000)


if __name__ == "__main__":
    unittest.main(verbosity=2)
