"""
Tests — Mortality Credibility Blending & Improvement (roadmap §4.1 #11, ASOP 25).

unittest + numpy only (scipy/pytest unavailable in the network-restricted
sandbox); runnable directly:  python3 -m unittest tests.test_mortality_credibility
"""
from __future__ import annotations

import math
import unittest

import numpy as np

from par_model_v2.projection import mortality_credibility as mc
from par_model_v2.projection.monthly_projection import _base_annual_qx


# Pinned regression digests of the default generated tables (locks generator output).
_PINNED = {
    "M": {
        "inputs": "34132fd779c6a9d416c88001ee9c2eb1981161a86f1431da1b9256720392f6a0",
        "content": "df49af04deb0636922e6fe639c55be467ba290e8898897e27e84460ac6b1756b",
    },
    "F": {
        "inputs": "dd0517ba41c79a9f19a3672218e44020503eea5d361df9302edb309973f933a0",
        "content": "e02398fb097b6d86f8d79aef94b4638503b96d883641aa72b26c3ddeb536088e",
    },
}


class TestNormPPF(unittest.TestCase):
    def test_known_quantiles(self):
        self.assertAlmostEqual(mc.norm_ppf(0.5), 0.0, places=9)
        self.assertAlmostEqual(mc.norm_ppf(0.95), 1.6448536269514722, places=6)
        self.assertAlmostEqual(mc.norm_ppf(0.975), 1.959963984540054, places=6)
        self.assertAlmostEqual(mc.norm_ppf(0.025), -1.959963984540054, places=6)

    def test_symmetry(self):
        for p in (0.1, 0.3, 0.6, 0.8, 0.99):
            self.assertAlmostEqual(mc.norm_ppf(p), -mc.norm_ppf(1 - p), places=8)

    def test_domain_errors(self):
        for bad in (0.0, 1.0, -0.1, 1.5):
            with self.assertRaises(ValueError):
                mc.norm_ppf(bad)


class TestLimitedFluctuation(unittest.TestCase):
    def test_full_credibility_standard_formula(self):
        # lambda_F = (z_{(1+p)/2}/k)^2 ; p=.90,k=.05 -> ~1082.22
        lam = mc.full_credibility_deaths(0.90, 0.05)
        z = mc.norm_ppf(0.95)
        self.assertAlmostEqual(lam, (z / 0.05) ** 2, places=6)
        self.assertAlmostEqual(lam, 1082.217, places=2)

    def test_tighter_tolerance_needs_more_deaths(self):
        self.assertGreater(mc.full_credibility_deaths(0.95, 0.02),
                           mc.full_credibility_deaths(0.90, 0.05))

    def test_square_root_rule_and_cap(self):
        lam = mc.full_credibility_deaths()
        self.assertAlmostEqual(mc.limited_fluctuation_z(lam / 4.0, lam), 0.5, places=9)
        self.assertEqual(mc.limited_fluctuation_z(lam, lam), 1.0)
        self.assertEqual(mc.limited_fluctuation_z(10 * lam, lam), 1.0)  # capped
        self.assertEqual(mc.limited_fluctuation_z(0.0, lam), 0.0)

    def test_errors(self):
        with self.assertRaises(ValueError):
            mc.limited_fluctuation_z(10, 0)
        with self.assertRaises(ValueError):
            mc.full_credibility_deaths(1.0, 0.05)
        with self.assertRaises(ValueError):
            mc.full_credibility_deaths(0.9, 0.0)


class TestBuhlmann(unittest.TestCase):
    def test_k_from_classes(self):
        # EPV=0.02; VHM = weighted var of means -> K = EPV/VHM
        K = mc.buhlmann_k_from_classes([0.9, 1.0, 1.15], [0.02, 0.02, 0.02], [3, 4, 3])
        w = np.array([3, 4, 3.0]); w = w / w.sum()
        m = np.array([0.9, 1.0, 1.15]); mbar = float((w * m).sum())
        vhm = float((w * (m - mbar) ** 2).sum())
        self.assertAlmostEqual(K, 0.02 / vhm, places=9)

    def test_z_monotone_in_n(self):
        self.assertLess(mc.buhlmann_z(100, 5.0), mc.buhlmann_z(10000, 5.0))
        self.assertAlmostEqual(mc.buhlmann_z(0, 5.0), 0.0, places=12)
        self.assertGreater(mc.buhlmann_z(1e9, 5.0), 0.999)

    def test_errors(self):
        with self.assertRaises(ValueError):
            mc.buhlmann_k_from_classes([1.0], [0.02])              # <2 classes
        with self.assertRaises(ValueError):
            mc.buhlmann_k_from_classes([1.0, 1.0], [0.02, 0.02])   # VHM=0


class TestStandardTableReadsGoverned(unittest.TestCase):
    def test_matches_base_annual_qx(self):
        for g in ("M", "F"):
            std = mc.StandardMortalityTable(gender=g)
            for a in (20, 35, 50, 65, 80):
                self.assertEqual(std.qx(a), _base_annual_qx(a, g))

    def test_governed_base_not_mutated(self):
        before = [_base_annual_qx(a, "M") for a in range(18, 86)]
        _ = mc.generate_blended_table(gender="M")
        after = [_base_annual_qx(a, "M") for a in range(18, 86)]
        self.assertEqual(before, after)


class TestExperience(unittest.TestCase):
    def test_ae_and_expected(self):
        std = mc.StandardMortalityTable("M")
        exp = mc.MortalityExperience((40, 50), (1000.0, 800.0), (2.0, 5.0))
        e = 1000 * std.qx(40) + 800 * std.qx(50)
        self.assertAlmostEqual(exp.expected_deaths(std), e, places=9)
        self.assertAlmostEqual(exp.observed_ae(std), 7.0 / e, places=9)

    def test_digest_deterministic_and_sensitive(self):
        a = mc.MortalityExperience((40,), (1000.0,), (2.0,))
        b = mc.MortalityExperience((40,), (1000.0,), (2.0,))
        c = mc.MortalityExperience((40,), (1000.0,), (3.0,))
        self.assertEqual(a.digest(), b.digest())
        self.assertNotEqual(a.digest(), c.digest())

    def test_validation_errors(self):
        with self.assertRaises(ValueError):
            mc.MortalityExperience((40, 41), (1000.0,), (2.0,))     # length mismatch
        with self.assertRaises(ValueError):
            mc.MortalityExperience((40,), (-1.0,), (2.0,))          # neg exposure
        with self.assertRaises(ValueError):
            mc.MortalityExperience((), (), ())                      # empty


class TestImprovementScale(unittest.TestCase):
    def test_shape(self):
        imp = mc.ImprovementScale(base_rate=0.01, taper_start_age=60, taper_end_age=95)
        self.assertEqual(imp.rate(40), 0.01)
        self.assertEqual(imp.rate(60), 0.01)
        self.assertAlmostEqual(imp.rate(77), 0.01 * (95 - 77) / (95 - 60), places=9)
        self.assertEqual(imp.rate(95), 0.0)
        self.assertEqual(imp.rate(100), 0.0)

    def test_errors(self):
        with self.assertRaises(ValueError):
            mc.ImprovementScale(base_rate=1.5)
        with self.assertRaises(ValueError):
            mc.ImprovementScale(taper_start_age=95, taper_end_age=90)


class TestGenerateBlendedTable(unittest.TestCase):
    def test_blending_identity_aggregate(self):
        t = mc.generate_blended_table(gender="M")
        expected = t.credibility_z * t.observed_ae + (1 - t.credibility_z) * 1.0
        for ae in t.blended_ae:
            self.assertAlmostEqual(ae, expected, places=12)

    def test_favourable_experience_blended_between_obs_and_one(self):
        t = mc.generate_blended_table(gender="M")
        self.assertLess(t.observed_ae, 1.0)                 # favourable synthetic set
        self.assertTrue(t.observed_ae <= t.blended_ae[0] <= 1.0)

    def test_monotone_nondecreasing_and_bounds(self):
        for g in ("M", "F"):
            t = mc.generate_blended_table(gender=g)
            pq = np.array(t.projected_qx)
            self.assertTrue(np.all(np.diff(pq) >= -1e-15))
            self.assertGreaterEqual(pq.min(), 1e-6)
            self.assertLessEqual(pq.max(), 0.50)

    def test_improvement_reduces_qx(self):
        t = mc.generate_blended_table(gender="M")
        pq = np.array(t.projected_qx); bq = np.array(t.blended_base_qx)
        self.assertTrue(np.all(pq <= bq + 1e-15))
        # strictly below where improvement is positive (young/mid ages)
        idx = t.ages.index(40)
        self.assertLess(pq[idx], bq[idx])

    def test_zero_improvement_identity(self):
        t = mc.generate_blended_table(gender="M", improvement=mc.ImprovementScale(base_rate=0.0))
        for a, b in zip(t.projected_qx, t.blended_base_qx):
            self.assertAlmostEqual(a, b, places=15)

    def test_full_credibility_recovers_observed(self):
        # enormous experience -> Z=1 -> blended A/E == observed A/E
        std = mc.StandardMortalityTable("M")
        ages = list(range(30, 71))
        exposure = [50000.0] * len(ages)
        deaths = [e * 0.85 * std.qx(a) for a, e in zip(ages, exposure)]
        big = mc.MortalityExperience(tuple(ages), tuple(exposure), tuple(deaths),
                                     label="BIG", is_synthetic=True)
        t = mc.generate_blended_table(gender="M", experience=big)
        self.assertEqual(t.credibility_z, 1.0)
        self.assertAlmostEqual(t.blended_ae[0], t.observed_ae, places=9)
        self.assertAlmostEqual(t.observed_ae, 0.85, places=6)

    def test_determinism_pinned_digests(self):
        for g in ("M", "F"):
            t = mc.generate_blended_table(gender=g)
            self.assertEqual(t.inputs_digest, _PINNED[g]["inputs"])
            self.assertEqual(t.content_digest, _PINNED[g]["content"])
            # regenerate -> identical
            self.assertEqual(mc.generate_blended_table(gender=g).content_digest,
                             t.content_digest)

    def test_valuation_before_base_rejected(self):
        with self.assertRaises(ValueError):
            mc.generate_blended_table(base_year=2026, valuation_year=2020)

    def test_by_age_granularity_runs(self):
        cfg = mc.CredibilityConfig(method="limited_fluctuation", granularity="by_age")
        t = mc.generate_blended_table(gender="M", credibility=cfg)
        self.assertIsNotNone(t.per_age_z)
        self.assertEqual(len(t.per_age_z), len(t.ages))
        self.assertTrue(all(0.0 <= z <= 1.0 for z in t.per_age_z))

    def test_buhlmann_config_requires_k(self):
        with self.assertRaises(ValueError):
            mc.CredibilityConfig(method="buhlmann")

    def test_buhlmann_path(self):
        K = mc.buhlmann_k_from_classes([0.9, 1.0, 1.15], [0.02, 0.02, 0.02], [3, 4, 3])
        cfg = mc.CredibilityConfig(method="buhlmann", buhlmann_k=K)
        t = mc.generate_blended_table(gender="M", credibility=cfg)
        self.assertEqual(t.credibility_method, "buhlmann")
        self.assertTrue(0.0 <= t.credibility_z <= 1.0)


class TestSerializationAndValidator(unittest.TestCase):
    def test_to_dict_roundtrip_keys(self):
        d = mc.generate_blended_table(gender="M").to_dict()
        for key in ("schema", "credibility", "improvement", "experience", "table",
                    "unsigned", "unsigned_banner", "inputs_digest", "content_digest"):
            self.assertIn(key, d)
        self.assertTrue(d["unsigned"])
        self.assertEqual(d["schema"], mc.SCHEMA)

    def test_to_markdown_has_banner(self):
        md = mc.generate_blended_table(gender="M").to_markdown()
        self.assertIn("UNSIGNED", md)
        self.assertIn("Credibility", md)

    def test_output_passes_mortality_validator(self):
        from par_model_v2.validation.data_validator import MortalityTableValidator
        t = mc.generate_blended_table(gender="M")
        rep = MortalityTableValidator().validate(t.to_dataframe())
        self.assertTrue(rep.passed)


if __name__ == "__main__":
    unittest.main(verbosity=2)
