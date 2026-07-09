"""
Unit tests — Path-wise vs current (horizon) TVOG bridge (roadmap §4.1 #8).

numpy-only / unittest (scipy + pytest are unavailable in the network-restricted
CI sandbox); runnable directly with ``python3 -m unittest``.
"""
from __future__ import annotations

import json
import math
import unittest

import numpy as np

from par_model_v2.projection.management_actions import ManagementActionRule
from par_model_v2.projection.pathwise_tvog_bridge import (
    BASES,
    SCHEMA,
    PathwiseTVOGConfig,
    PathwiseTVOGBridgeResult,
    build_pathwise_tvog_bridge,
    pathwise_tvog_use_restrictions,
    simulate_tvog_bases,
)


class ConfigValidationTests(unittest.TestCase):
    def test_defaults_construct(self):
        cfg = PathwiseTVOGConfig()
        self.assertEqual(cfg.n_steps, 10)
        self.assertGreater(cfg.n_outer, 100)

    def test_rejects_bad_params(self):
        with self.assertRaises(ValueError):
            PathwiseTVOGConfig(n_outer=50)
        with self.assertRaises(ValueError):
            PathwiseTVOGConfig(n_inner=1)
        with self.assertRaises(ValueError):
            PathwiseTVOGConfig(n_steps=1)
        with self.assertRaises(ValueError):
            PathwiseTVOGConfig(sigma=0.0)
        with self.assertRaises(ValueError):
            PathwiseTVOGConfig(rf=-0.01)
        with self.assertRaises(ValueError):
            PathwiseTVOGConfig(rb_target=-0.01)
        with self.assertRaises(ValueError):
            PathwiseTVOGConfig(l0=0.0)

    def test_to_dict_roundtrips_json(self):
        d = PathwiseTVOGConfig().to_dict()
        self.assertEqual(json.loads(json.dumps(d))["n_steps"], 10)


class SimulationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cfg = PathwiseTVOGConfig(n_outer=1500, n_inner=60, seed=7)
        cls.rule = ManagementActionRule()
        cls.sim = simulate_tvog_bases(cls.cfg, cls.rule)

    def test_all_bases_present(self):
        for b in BASES:
            self.assertIn(b, self.sim)
            for k in ("tvog_guarantee_node", "tvog_declared_node", "net_liability_node"):
                self.assertEqual(np.asarray(self.sim[b][k]).shape, (self.cfg.n_outer,))

    def test_martingale_property(self):
        # E^Q[disc * A_T] / A_0 == 1 to Monte-Carlo error (risk-neutral drift).
        self.assertLess(abs(self.sim["martingale_ratio"] - 1.0), 0.02)

    def test_disc_matches_riskfree(self):
        self.assertAlmostEqual(
            self.sim["disc"], math.exp(-self.cfg.rf * self.cfg.n_steps), places=12
        )

    def test_common_random_numbers_bounds(self):
        # max_cut <= {horizon, pathwise} <= without, elementwise, both measures.
        tol = 1e-9 * self.cfg.l0
        for key in ("tvog_guarantee_node", "tvog_declared_node"):
            wo = np.asarray(self.sim["without"][key])
            mc = np.asarray(self.sim["max_cut"][key])
            for basis in ("horizon", "pathwise"):
                v = np.asarray(self.sim[basis][key])
                self.assertTrue(np.all(v <= wo + tol), f"{basis} {key} <= without")
                self.assertTrue(np.all(v >= mc - tol), f"{basis} {key} >= max_cut")

    def test_declared_dominates_guarantee(self):
        # Declared benefit (incl. TB) is never cheaper than the hard guarantee.
        for b in BASES:
            g = np.asarray(self.sim[b]["tvog_guarantee_node"])
            d = np.asarray(self.sim[b]["tvog_declared_node"])
            self.assertTrue(np.all(d >= g - 1e-9))

    def test_mechanism_shares(self):
        self.assertGreater(self.sim["pathwise_action_share"], 0.0)
        self.assertLessEqual(self.sim["pathwise_action_share"], 1.0)
        self.assertGreaterEqual(self.sim["pathwise_restoration_share"], 0.0)
        self.assertLessEqual(
            self.sim["pathwise_restoration_share"],
            self.sim["pathwise_action_share"] + 1e-12,
        )


class BridgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.res = build_pathwise_tvog_bridge()

    def test_schema_and_type(self):
        self.assertIsInstance(self.res, PathwiseTVOGBridgeResult)
        self.assertEqual(self.res.schema, SCHEMA)

    def test_bridge_identity_exact_guarantee(self):
        g = self.res.bridge_guarantee
        self.assertAlmostEqual(
            g.delta_total, g.delta_healthy_nodes + g.delta_stressed_nodes, places=9
        )
        self.assertLess(abs(g.identity_residual), 1e-9)

    def test_bridge_identity_exact_declared(self):
        d = self.res.bridge_declared
        self.assertAlmostEqual(
            d.delta_total, d.delta_healthy_nodes + d.delta_stressed_nodes, places=9
        )
        self.assertLess(abs(d.identity_residual), 1e-9)

    def test_bridge_reconciles_current_to_pathwise(self):
        for leg in (self.res.bridge_guarantee, self.res.bridge_declared):
            self.assertAlmostEqual(
                leg.tvog_pathwise,
                leg.tvog_current_horizon + leg.delta_total,
                places=9,
            )

    def test_basis_mean_ordering(self):
        rows = {b.basis: b for b in self.res.bases}
        for attr in ("tvog_guarantee", "tvog_declared", "mean_net_liability"):
            wo = getattr(rows["without"], attr)
            mc = getattr(rows["max_cut"], attr)
            hz = getattr(rows["horizon"], attr)
            pw = getattr(rows["pathwise"], attr)
            self.assertGreaterEqual(wo + 1e-9, hz)
            self.assertGreaterEqual(wo + 1e-9, pw)
            self.assertGreaterEqual(hz, mc - 1e-9)
            self.assertGreaterEqual(pw, mc - 1e-9)

    def test_martingale_and_bounds_gates(self):
        self.assertTrue(self.res.martingale_ok)
        self.assertTrue(self.res.bounds_ok)

    def test_default_finding_pathwise_reduces_tvog(self):
        # Regression lock on the documented finding: on the default fund the
        # path-wise basis reduces BOTH TVOG measures vs the horizon basis.
        self.assertLess(self.res.bridge_guarantee.delta_total, 0.0)
        self.assertLess(self.res.bridge_declared.delta_total, 0.0)

    def test_tb_extension_adds_responsiveness(self):
        # Extending RB -> RB+TB: the declared-benefit bridge is strictly larger
        # in magnitude than the guarantee-only bridge (TB declaration bites).
        self.assertGreater(
            abs(self.res.bridge_declared.delta_total),
            abs(self.res.bridge_guarantee.delta_total),
        )

    def test_healthy_share_in_unit_interval(self):
        self.assertGreater(self.res.healthy_node_share, 0.0)
        self.assertLess(self.res.healthy_node_share, 1.0)

    def test_healthy_reference_defaults_to_trigger(self):
        self.assertAlmostEqual(
            self.res.healthy_cr_reference, ManagementActionRule().cr_trigger, places=12
        )


class DeterminismAndSerialisationTests(unittest.TestCase):
    def test_same_seed_same_digest(self):
        a = build_pathwise_tvog_bridge()
        b = build_pathwise_tvog_bridge()
        self.assertEqual(a.content_digest(), b.content_digest())

    def test_different_seed_changes_result(self):
        a = build_pathwise_tvog_bridge(PathwiseTVOGConfig(seed=1))
        b = build_pathwise_tvog_bridge(PathwiseTVOGConfig(seed=2))
        self.assertNotEqual(a.content_digest(), b.content_digest())

    def test_to_dict_is_json_serialisable(self):
        d = build_pathwise_tvog_bridge().to_dict()
        blob = json.dumps(d)
        self.assertIn("pathwise-tvog-bridge-1.0", blob)
        self.assertEqual(json.loads(blob)["schema"], SCHEMA)

    def test_markdown_renders(self):
        md = build_pathwise_tvog_bridge().markdown()
        self.assertIn("TVOG bridge", md)
        self.assertIn("horizon", md)
        self.assertIn("UNSIGNED", md)

    def test_digest_excludes_timestamp(self):
        # content_digest must ignore run_timestamp (else it is not stable).
        r = build_pathwise_tvog_bridge()
        d = r.to_dict()
        d["run_timestamp"] = "1999-01-01T00:00:00+00:00"
        self.assertIn("run_timestamp", d)  # present in to_dict
        # digest recomputed on the object is timestamp-independent
        self.assertEqual(r.content_digest(), build_pathwise_tvog_bridge().content_digest())


class UseRestrictionTests(unittest.TestCase):
    def test_use_restrictions_disclose_educational(self):
        u = pathwise_tvog_use_restrictions()
        self.assertEqual(u["classification"], "EDUCATIONAL")
        self.assertFalse(u["production_use"])
        self.assertFalse(u["governed_headline_touched"])
        self.assertIn("owner_gated_followon", u)
        self.assertIn("GOVERNED", u["owner_gated_followon"].upper())
        self.assertGreaterEqual(len(u["restrictions"]), 3)

    def test_banner_and_standards(self):
        r = build_pathwise_tvog_bridge()
        self.assertIn("UNSIGNED", r.unsigned_banner)
        self.assertTrue(any("MCEV" in s or "TAS M" in s for s in r.standard_references))


if __name__ == "__main__":
    unittest.main(verbosity=2)
