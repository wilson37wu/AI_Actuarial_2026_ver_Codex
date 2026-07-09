"""Roadmap 4.1 #10 -- tests for the 100k-policy batch performance profile.

Stdlib + numpy/pandas only (scipy/pytest are unavailable in the network-
restricted sandbox); runnable via ``python3 -m unittest
tests.test_batch_perf_profile``.

The tests assert the *structure* and *governance invariants* of the finding --
NOT absolute milliseconds (which are environment-dependent):
  * the safe optimisation is byte-identical (governed digest value unchanged,
    regression-locked to a pinned hash);
  * the top hotspot is the reproducibility digest;
  * the owner-gated buffer-hash scheme genuinely differs from the governed
    digest (so it is correctly flagged as requiring sign-off);
  * report serialisation and the idempotent inputs digest.
"""

import json
import re
import unittest
from dataclasses import replace

from par_model_v2.projection.portfolio_generator import (
    PortfolioGenerationConfig,
    generate_hk_par_portfolio,
    portfolio_digest,
    _portfolio_digest_presorted,
)
from par_model_v2.projection import batch_perf_profile as B

# Pinned governed digests (regression-lock: the safe optimisation must NOT
# change these byte-for-byte values).
PIN_500 = "fa7e14963091fd04effd3a4c5c00b832bf34b3a06082b10eda4a5f2db9714366"
PIN_100K = "321f50d82e0c41bcfa5c0dde78a9cbb5c749466c038857df227b5eb80c570c1e"

_HEX64 = re.compile(r"^[0-9a-f]{64}$")


def _cfg(n):
    return replace(PortfolioGenerationConfig(), n_policies=n)


class TestGovernedDigestUnchanged(unittest.TestCase):
    def test_presorted_equals_public_and_pin_500(self):
        res = generate_hk_par_portfolio(_cfg(500))
        self.assertEqual(res.digest, PIN_500)
        self.assertEqual(_portfolio_digest_presorted(res.policies), res.digest)
        self.assertEqual(portfolio_digest(res.policies), res.digest)

    def test_default_100k_pin_and_invariance(self):
        res = generate_hk_par_portfolio(PortfolioGenerationConfig())
        self.assertEqual(res.digest, PIN_100K)
        # presorted shortcut is byte-identical to the public digest on the
        # already-canonical generated frame.
        self.assertEqual(_portfolio_digest_presorted(res.policies), res.digest)

    def test_public_digest_is_sort_invariant(self):
        res = generate_hk_par_portfolio(_cfg(700))
        shuffled = res.policies.sample(frac=1.0, random_state=13)
        self.assertEqual(portfolio_digest(shuffled), res.digest)


class TestDigestSchemeComparison(unittest.TestCase):
    def test_buffer_hash_is_a_different_value(self):
        res = generate_hk_par_portfolio(_cfg(1200))
        # The owner-gated buffer-hash scheme must NOT reproduce the governed
        # digest -- that is exactly why adopting it needs sign-off.
        self.assertNotEqual(B._buffer_hash_digest(res.policies), res.digest)

    def test_compare_reports_difference(self):
        res = generate_hk_par_portfolio(_cfg(1500))
        cmp = B.compare_digest_schemes(res.policies, reps=2)
        self.assertTrue(cmp.values_differ)
        self.assertGreater(cmp.to_csv_ms, 0.0)
        self.assertGreaterEqual(cmp.buffer_hash_ms, 0.0)
        self.assertIsInstance(cmp.speedup_pct, float)


class TestSafeOptimizationMeasurement(unittest.TestCase):
    def test_byte_identical_and_bounded(self):
        so = B.measure_safe_optimization(_cfg(1500), reps=2)
        self.assertTrue(so.digest_byte_identical)
        self.assertGreaterEqual(so.saving_ms, 0.0)
        self.assertGreater(so.generation_ms, 0.0)
        self.assertGreaterEqual(so.saving_pct_of_generation, 0.0)
        # Safe saving is a small fraction, never the whole generation.
        self.assertLess(so.saving_pct_of_generation, 100.0)


class TestGenerationDecomposition(unittest.TestCase):
    def test_digest_is_a_fraction_of_generation(self):
        g = B.decompose_generation(_cfg(2000), reps=2)
        self.assertGreater(g.total_ms, 0.0)
        self.assertGreaterEqual(g.digest_ms, 0.0)
        self.assertGreaterEqual(g.modelling_ms, 0.0)
        self.assertGreater(g.digest_fraction, 0.0)
        self.assertLessEqual(g.digest_fraction, 1.0)


class TestHotspots(unittest.TestCase):
    def test_top_hotspots_sorted_desc(self):
        hs = B.top_hotspots(lambda: generate_hk_par_portfolio(_cfg(1500)), reps=1, top_n=6)
        self.assertGreater(len(hs), 0)
        tots = [h.tottime_s for h in hs]
        self.assertEqual(tots, sorted(tots, reverse=True))
        for h in hs:
            self.assertTrue(h.function)
            self.assertGreaterEqual(h.ncalls, 0)


class TestTimeStage(unittest.TestCase):
    def test_time_stage_shape(self):
        st = B.time_stage("noop", lambda: sum(range(10)), reps=3, warmup=1)
        self.assertEqual(st.reps, 3)
        self.assertGreaterEqual(st.mean_ms, 0.0)
        self.assertGreaterEqual(st.min_ms, 0.0)


class TestReport(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rep = B.build_report(_cfg(2500), reps=2, hotspot_top_n=8)

    def test_core_fields(self):
        r = self.rep
        self.assertEqual(r.schema_version, "perf-profile-100k-1.0")
        self.assertEqual(r.n_policies, 2500)
        self.assertTrue(r.unsigned)
        self.assertTrue(_HEX64.match(r.inputs_digest))
        # documented-finding branch: safe cut below 20% target.
        self.assertFalse(r.meets_20pct_safely)
        self.assertGreaterEqual(r.safe_cut_pct, 0.0)
        # owner-gated opportunity is real and positive.
        self.assertGreater(r.owner_gated_cut_pct, 0.0)
        self.assertTrue(r.digest_scheme.values_differ)
        self.assertTrue(r.safe_optimization.digest_byte_identical)
        self.assertTrue(r.top_hotspot_function)

    def test_serialisation(self):
        r = self.rep
        parsed = json.loads(r.to_json())
        self.assertEqual(parsed["schema_version"], "perf-profile-100k-1.0")
        self.assertIn("finding", parsed)
        md = r.to_markdown()
        self.assertTrue(md.startswith("# 100k-Policy Batch Performance Profile"))
        self.assertIn("Finding", md)
        self.assertIn("Owner-gated", md)

    def test_finding_mentions_governance(self):
        f = self.rep.finding.lower()
        self.assertIn("owner", f)
        self.assertIn("digest", f)
        self.assertIn("20%", f)

    def test_inputs_digest_idempotent(self):
        a = B.build_report(_cfg(800), reps=2)
        b = B.build_report(_cfg(800), reps=2)
        self.assertEqual(a.inputs_digest, b.inputs_digest)
        # different scale -> different inputs digest
        c = B.build_report(_cfg(900), reps=2)
        self.assertNotEqual(a.inputs_digest, c.inputs_digest)


class TestHarnessDoesNotMutateGovernedDigest(unittest.TestCase):
    def test_digest_stable_after_full_harness(self):
        # Running the whole harness must not perturb the governed digest.
        B.build_report(_cfg(500), reps=2)
        res = generate_hk_par_portfolio(_cfg(500))
        self.assertEqual(res.digest, PIN_500)


if __name__ == "__main__":
    unittest.main(verbosity=2)
