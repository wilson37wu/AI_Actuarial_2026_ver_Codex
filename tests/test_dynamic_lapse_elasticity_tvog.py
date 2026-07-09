"""
Tests — Roadmap §4.1 #4 (MR-003): bounded-elasticity lapse response + TVOG delta
=================================================================================

Pure-stdlib ``unittest`` (numpy only) so the suite runs without SciPy/pytest.

Covers the increment added on top of the Phase 13 dynamic-lapse model:
  * analytic marginal response (``d lapse / d spread``) vs finite differences,
  * the closed-form Lipschitz **bounded-elasticity** guarantee,
  * the Gauss-Hermite TVOG proxy and the static-vs-dynamic **TVOG delta**.
"""
from __future__ import annotations

import math
import unittest

import numpy as np

from par_model_v2.projection.dynamic_lapse import (
    base_annual_lapse,
    default_hk_par_dynamic_lapse,
    DynamicLapseAssumption,
)
from par_model_v2.projection.dynamic_lapse_tvog import (
    DEFAULT_RATE_SIGMA,
    TVOG_SCHEMA,
    dynamic_lapse_tvog_delta,
    gauss_hermite_normal_nodes,
    representative_par_product,
    tvog_delta_vol_profile,
    tvog_proxy,
)


# ---------------------------------------------------------------------------
# Bounded-elasticity marginal response (model)
# ---------------------------------------------------------------------------
class TestMarginalResponse(unittest.TestCase):
    def setUp(self) -> None:
        self.a = default_hk_par_dynamic_lapse(credited_rate=0.025)
        self.base = base_annual_lapse(1)  # 0.12, the largest base

    def _lapse_pre(self, s: float, base: float) -> float:
        return base * self.a.efficiency_multiplier(s) + self.a.mass_lapse(s)

    def test_analytic_matches_finite_difference(self):
        h = 1e-7
        for s in np.linspace(-0.10, 0.10, 801):
            fd = (self._lapse_pre(s + h, self.base) - self._lapse_pre(s - h, self.base)) / (2 * h)
            an = self.a.marginal_response(s, base=self.base)
            self.assertAlmostEqual(fd, an, delta=1e-5)

    def test_marginal_response_non_negative(self):
        for s in np.linspace(-0.20, 0.20, 401):
            self.assertGreaterEqual(self.a.marginal_response(s, base=self.base), -1e-12)

    def test_bound_dominates_empirical_max_slope(self):
        bound = self.a.marginal_response_bound(base=self.base)
        self.assertTrue(math.isfinite(bound) and bound > 0)
        h = 1e-7
        emp_max = 0.0
        for s in np.linspace(-0.15, 0.15, 3001):
            fd = (self._lapse_pre(s + h, self.base) - self._lapse_pre(s - h, self.base)) / (2 * h)
            emp_max = max(emp_max, fd)
        # analytic bound must dominate the observed maximum slope
        self.assertLessEqual(emp_max, bound + 1e-9)

    def test_component_slope_peaks_are_analytic(self):
        self.assertAlmostEqual(
            self.a.efficiency_multiplier_slope(0.0),
            self.a.beta * 2.0 / math.pi / self.a.kappa,
            places=10,
        )
        self.assertAlmostEqual(
            self.a.mass_lapse_slope(self.a.tau),
            self.a.shock_max / (4.0 * self.a.width),
            places=10,
        )
        # peaks are indeed maxima of their components
        self.assertGreaterEqual(
            self.a.efficiency_multiplier_slope(0.0),
            self.a.efficiency_multiplier_slope(0.05),
        )
        self.assertGreaterEqual(
            self.a.mass_lapse_slope(self.a.tau),
            self.a.mass_lapse_slope(self.a.tau + 0.05),
        )

    def test_slopes_vanish_at_extremes(self):
        self.assertAlmostEqual(self.a.marginal_response(+1e6, base=self.base), 0.0, places=9)
        self.assertAlmostEqual(self.a.marginal_response(-1e6, base=self.base), 0.0, places=9)
        self.assertEqual(self.a.mass_lapse_slope(1e6), 0.0)
        self.assertEqual(self.a.mass_lapse_slope(-1e6), 0.0)

    def test_semi_elasticity_positive_and_finite(self):
        for s in (-0.02, 0.0, 0.02, 0.04):
            e = self.a.semi_elasticity(s, policy_year=1)
            self.assertTrue(math.isfinite(e))
            self.assertGreater(e, 0.0)

    def test_bound_monotone_in_parameters(self):
        # larger beta / shock_max ⇒ larger bound; larger kappa / width ⇒ smaller
        b0 = DynamicLapseAssumption(beta=0.4, kappa=0.02, shock_max=0.1, tau=0.03, width=0.01)
        self.assertGreater(
            DynamicLapseAssumption(beta=0.6, kappa=0.02, shock_max=0.1, tau=0.03, width=0.01).marginal_response_bound(base=0.12),
            b0.marginal_response_bound(base=0.12),
        )
        self.assertLess(
            DynamicLapseAssumption(beta=0.4, kappa=0.04, shock_max=0.1, tau=0.03, width=0.01).marginal_response_bound(base=0.12),
            b0.marginal_response_bound(base=0.12),
        )
        self.assertGreater(
            DynamicLapseAssumption(beta=0.4, kappa=0.02, shock_max=0.2, tau=0.03, width=0.01).marginal_response_bound(base=0.12),
            b0.marginal_response_bound(base=0.12),
        )

    def test_default_base_is_year1_global(self):
        # with base=None the bound uses year-1 base (largest), so it dominates
        # the bound computed at any later (smaller-base) duration
        self.assertAlmostEqual(
            self.a.marginal_response_bound(),
            self.a.marginal_response_bound(base=base_annual_lapse(1)),
            places=12,
        )
        self.assertGreaterEqual(
            self.a.marginal_response_bound(),
            self.a.marginal_response_bound(base=base_annual_lapse(20)),
        )


# ---------------------------------------------------------------------------
# Gauss-Hermite quadrature
# ---------------------------------------------------------------------------
class TestGaussHermite(unittest.TestCase):
    def test_weights_sum_to_one_and_moments_exact(self):
        mu, sig = 0.025, 0.010
        nodes = gauss_hermite_normal_nodes(mu, sig)
        w = sum(p for _, p in nodes)
        e_r = sum(r * p for r, p in nodes)
        e_r2 = sum(r * r * p for r, p in nodes)
        self.assertAlmostEqual(w, 1.0, places=12)
        self.assertAlmostEqual(e_r, mu, places=12)
        self.assertAlmostEqual(e_r2, mu * mu + sig * sig, places=12)

    def test_sigma_zero_single_node(self):
        nodes = gauss_hermite_normal_nodes(0.03, 0.0)
        self.assertEqual(len(nodes), 1)
        self.assertEqual(nodes[0], (0.03, 1.0))

    def test_negative_sigma_raises(self):
        with self.assertRaises(ValueError):
            gauss_hermite_normal_nodes(0.03, -0.01)


# ---------------------------------------------------------------------------
# TVOG delta
# ---------------------------------------------------------------------------
class TestTvogDelta(unittest.TestCase):
    def test_static_tvog_is_flat_zero(self):
        stat = tvog_proxy(None, credited_rate=0.025, rate_sigma=0.01)
        self.assertEqual(stat.basis, "static")
        self.assertAlmostEqual(stat.tvog, 0.0, places=9)
        self.assertAlmostEqual(stat.expected_pv, stat.pv_central, places=9)
        pvs = {round(s.pv_net_liability, 6) for s in stat.scenarios}
        self.assertEqual(len(pvs), 1)  # rate-invariant

    def test_delta_equals_dynamic_and_nonzero(self):
        d = dynamic_lapse_tvog_delta(rate_sigma=0.01)
        self.assertAlmostEqual(d.tvog_static, 0.0, places=9)
        self.assertNotAlmostEqual(d.tvog_dynamic, 0.0, places=3)
        self.assertAlmostEqual(d.tvog_delta, d.tvog_dynamic - d.tvog_static, places=9)
        self.assertEqual(d.schema, TVOG_SCHEMA)

    def test_zero_sigma_gives_zero_tvog(self):
        d = dynamic_lapse_tvog_delta(rate_sigma=0.0)
        self.assertAlmostEqual(d.tvog_static, 0.0, places=9)
        self.assertAlmostEqual(d.tvog_dynamic, 0.0, places=9)
        self.assertAlmostEqual(d.tvog_delta, 0.0, places=9)

    def test_delta_grows_with_small_sigma(self):
        mags = [
            abs(dynamic_lapse_tvog_delta(rate_sigma=s).tvog_delta)
            for s in (0.0025, 0.0050, 0.0100)
        ]
        self.assertLess(mags[0], mags[1])
        self.assertLess(mags[1], mags[2])

    def test_deterministic_digest(self):
        d1 = dynamic_lapse_tvog_delta(rate_sigma=0.01)
        d2 = dynamic_lapse_tvog_delta(rate_sigma=0.01)
        self.assertEqual(d1.content_digest(), d2.content_digest())

    def test_to_dict_and_markdown_complete(self):
        d = dynamic_lapse_tvog_delta(rate_sigma=0.01)
        dd = d.to_dict()
        for k in ("schema", "tvog_static", "tvog_dynamic", "tvog_delta",
                  "tvog_delta_pct_of_central", "static", "dynamic",
                  "assumption", "unsigned_banner"):
            self.assertIn(k, dd)
        self.assertTrue(dd["unsigned"])
        self.assertIn("marginal_response_bound_year1", dd["assumption"])
        md = d.markdown()
        self.assertIn("TVOG", md)
        self.assertIn("UNSIGNED", md)

    def test_discount_within_cbirc_cap(self):
        d = dynamic_lapse_tvog_delta(rate_sigma=0.01)
        self.assertLessEqual(d.discount_rate_annual, 0.030 + 1e-12)

    def test_vol_profile_shape(self):
        prof = tvog_delta_vol_profile()
        self.assertGreaterEqual(len(prof), 3)
        for row in prof:
            for k in ("rate_sigma", "tvog_static", "tvog_dynamic",
                      "tvog_delta", "tvog_delta_pct_of_central"):
                self.assertIn(k, row)
            self.assertAlmostEqual(row["tvog_static"], 0.0, places=9)

    def test_representative_product_is_20y(self):
        p = representative_par_product()
        self.assertEqual(p.term_years, 20)
        self.assertEqual(p.sum_assured, 1_000_000.0)

    def test_default_sigma_constant(self):
        self.assertEqual(DEFAULT_RATE_SIGMA, 0.010)


if __name__ == "__main__":
    unittest.main()
