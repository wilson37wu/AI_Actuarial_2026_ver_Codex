"""Tests for roadmap 4.1 #2 - HW1F swaption calibration on a live/proxy quote set.

Covers: payload schema validation, the three provenance tiers (live_fetch /
cached_snapshot / file_fixture), snapshot tamper detection, live-tier
validation fail-loud behaviour, end-to-end calibrate() execution with fit
diagnostics, parameter-card artifacts, UNSIGNED flagging, and inputs-digest
idempotency.
"""
from __future__ import annotations

import copy
import json
import unittest
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory

try:
    import numpy  # noqa: F401
    import pandas  # noqa: F401
    import scipy  # noqa: F401
    _ENGINE = True
except Exception:  # pragma: no cover
    _ENGINE = False

if _ENGINE:
    from par_model_v2.calibration.hw1f_live_calibration import (
        DictSwaptionSource,
        MarketDataFetchError,
        SnapshotCache,
        SnapshotIntegrityError,
        SwaptionSurfaceLoader,
        render_parameter_card_md,
        run_hw1f_live_calibration,
        validate_swaption_surface_payload,
    )
    from par_model_v2.calibration.market_data_source import default_fixture_dir

FIXTURE_AS_OF = "20260101"


def _proxy_payload(currency: str = "CNY", as_of: str = "2026-07-01") -> dict:
    """A small but valid live/proxy swaption quote set (10 active quotes)."""
    grid = []
    for expiry in (1.0, 2.0, 5.0, 7.0, 10.0):
        for tenor in (2.0, 5.0):
            grid.append({
                "expiry_years": expiry,
                "swap_tenor_years": tenor,
                "normal_vol_bps": 60.0 - 2.0 * expiry - 0.5 * tenor,
                "weight": 1.0,
            })
    return {
        "currency": currency,
        "as_of_date": as_of,
        "swaption_grid": grid,
        "spot_curve": {
            "tenors_years": [0.25, 1.0, 2.0, 5.0, 10.0, 20.0, 30.0],
            "rates_decimal": [0.017, 0.019, 0.021, 0.024, 0.027, 0.029, 0.030],
        },
        "initial_short_rate": 0.018,
        "regulatory_rate_cap": 0.05,
    }


@unittest.skipUnless(_ENGINE, "numpy/pandas/scipy unavailable")
class TestPayloadValidation(unittest.TestCase):
    def test_valid_payload_has_no_errors(self):
        self.assertEqual(validate_swaption_surface_payload(_proxy_payload()), [])

    def test_missing_grid_rejected(self):
        p = _proxy_payload()
        del p["swaption_grid"]
        errs = validate_swaption_surface_payload(p)
        self.assertTrue(any("swaption_grid" in e for e in errs))

    def test_non_positive_vol_rejected(self):
        p = _proxy_payload()
        p["swaption_grid"][0]["normal_vol_bps"] = 0.0
        errs = validate_swaption_surface_payload(p)
        self.assertTrue(any("normal_vol_bps" in e for e in errs))

    def test_curve_length_mismatch_rejected(self):
        p = _proxy_payload()
        p["spot_curve"]["rates_decimal"] = p["spot_curve"]["rates_decimal"][:-1]
        errs = validate_swaption_surface_payload(p)
        self.assertTrue(any("differ in length" in e for e in errs))

    def test_bad_r0_rejected(self):
        p = _proxy_payload()
        p["initial_short_rate"] = 0.5
        errs = validate_swaption_surface_payload(p)
        self.assertTrue(any("initial_short_rate" in e for e in errs))

    def test_unsupported_currency_rejected(self):
        p = _proxy_payload(currency="USD")
        errs = validate_swaption_surface_payload(p)
        self.assertTrue(any("currency" in e for e in errs))


@unittest.skipUnless(_ENGINE, "numpy/pandas/scipy unavailable")
class TestProvenanceTiers(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.cache = SnapshotCache(Path(self._tmp.name) / "cache")

    def tearDown(self):
        self._tmp.cleanup()

    def test_fixture_tier(self):
        loader = SwaptionSurfaceLoader("CNY", self.cache,
                                       fixture_as_of=FIXTURE_AS_OF)
        res = loader.load()
        self.assertEqual(res.provenance, "file_fixture")
        self.assertEqual(res.market, "CNY")
        self.assertEqual(len(res.sha256), 64)
        self.assertEqual(res.lineage.market, "CNY")

    def test_live_tier_seals_snapshot_and_flags_unsigned(self):
        def fetcher(as_of):
            return _proxy_payload(as_of=as_of.isoformat())
        loader = SwaptionSurfaceLoader("CNY", self.cache, fetcher=fetcher)
        res = loader.load(as_of=date(2026, 7, 1), refresh=True)
        self.assertEqual(res.provenance, "live_fetch")
        self.assertTrue(Path(res.snapshot_path).exists())
        self.assertEqual(res.lineage.approved_by, "UNSIGNED_pending_owner_approval")

    def test_cached_tier_after_live(self):
        def fetcher(as_of):
            return _proxy_payload(as_of=as_of.isoformat())
        SwaptionSurfaceLoader("CNY", self.cache, fetcher=fetcher).load(
            as_of=date(2026, 7, 1), refresh=True)
        # New loader WITHOUT a fetcher must resolve the sealed snapshot.
        res = SwaptionSurfaceLoader("CNY", self.cache).load(as_of=date(2026, 7, 1))
        self.assertEqual(res.provenance, "cached_snapshot")
        self.assertEqual(res.payload["as_of_date"], "2026-07-01")

    def test_tampered_snapshot_detected(self):
        def fetcher(as_of):
            return _proxy_payload(as_of=as_of.isoformat())
        res = SwaptionSurfaceLoader("CNY", self.cache, fetcher=fetcher).load(
            as_of=date(2026, 7, 1), refresh=True)
        path = Path(res.snapshot_path)
        snap = json.loads(path.read_text(encoding="utf-8"))
        snap["records"][0]["initial_short_rate"] = 0.055
        path.write_text(json.dumps(snap), encoding="utf-8")
        with self.assertRaises(SnapshotIntegrityError):
            SwaptionSurfaceLoader("CNY", self.cache).load(as_of=date(2026, 7, 1))

    def test_invalid_live_payload_fails_loud_never_falls_back(self):
        def bad_fetcher(as_of):
            p = _proxy_payload(as_of=as_of.isoformat())
            p["swaption_grid"] = p["swaption_grid"][:2]  # keeps schema OK
            p["initial_short_rate"] = 0.9  # schema violation
            return p
        loader = SwaptionSurfaceLoader("CNY", self.cache, fetcher=bad_fetcher)
        with self.assertRaises(MarketDataFetchError):
            loader.load(as_of=date(2026, 7, 1), refresh=True)
        # Nothing cached from the bad fetch.
        self.assertEqual(self.cache.list_snapshots("swaption_surface_cny"), [])

    def test_market_currency_mismatch_rejected(self):
        def fetcher(as_of):
            return _proxy_payload(currency="HKD", as_of=as_of.isoformat())
        loader = SwaptionSurfaceLoader("CNY", self.cache, fetcher=fetcher)
        with self.assertRaises(MarketDataFetchError):
            loader.load(as_of=date(2026, 7, 1), refresh=True)


@unittest.skipUnless(_ENGINE, "numpy/pandas/scipy unavailable")
class TestEndToEndCalibration(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_fixture_calibration_end_to_end(self):
        card = run_hw1f_live_calibration(
            markets=("CNY", "HKD"),
            cache_dir=self.tmp / "cache",
            out_dir=self.tmp / "out",
        )
        self.assertEqual(card["schema_version"], "hw1f-live-cal-1.0")
        self.assertTrue(card["unsigned"])
        self.assertFalse(card["cached"])
        self.assertEqual(len(card["markets"]), 2)
        for blk in card["markets"]:
            p, d = blk["parameters"], blk["diagnostics"]
            self.assertFalse(blk["is_placeholder"])
            self.assertTrue(0.001 <= p["a"] <= 3.0)
            self.assertTrue(0.001 <= p["sigma_r"] <= 0.20)
            self.assertTrue(d["converged"], msg=blk["market"])
            self.assertGreater(d["sse_weighted_bps_sq"], 0.0)
            self.assertLessEqual(d["rmse_bps"], 25.0, msg=blk["market"])
            self.assertGreaterEqual(d["n_quotes_active"], 8)
            self.assertIsInstance(d["params_at_bounds"], list)
            self.assertEqual(len(blk["fit_table"]), d["n_quotes_total"])
        gate_ids = [g["gate_id"] for g in card["gates"]]
        self.assertIn("G-02", gate_ids)
        self.assertIn("G-12", gate_ids)

    def test_artifacts_written_and_digest_idempotent(self):
        out = self.tmp / "out"
        card1 = run_hw1f_live_calibration(
            markets=("CNY", "HKD"), cache_dir=self.tmp / "c", out_dir=out)
        jpath = out / "HW1F_LIVE_CALIBRATION_PARAMETER_CARD.json"
        mpath = out / "HW1F_LIVE_CALIBRATION_PARAMETER_CARD.md"
        self.assertTrue(jpath.exists() and mpath.exists())
        md = mpath.read_text(encoding="utf-8")
        self.assertIn("UNSIGNED", md)
        self.assertIn("RMSE (bps)", md)
        # Second run, same inputs -> digest-cache hit.
        card2 = run_hw1f_live_calibration(
            markets=("CNY", "HKD"), cache_dir=self.tmp / "c", out_dir=out)
        self.assertTrue(card2["cached"])
        self.assertEqual(card1["inputs_digest"], card2["inputs_digest"])
        self.assertEqual(
            card1["markets"][0]["parameters"], card2["markets"][0]["parameters"])

    def test_live_proxy_quote_set_calibrates(self):
        """The roadmap-#2 headline path: calibrate() on a LIVE/PROXY quote set."""
        def fetcher(as_of):
            return _proxy_payload(as_of=as_of.isoformat())
        card = run_hw1f_live_calibration(
            markets=("CNY",),
            fetchers={"CNY": fetcher},
            cache_dir=self.tmp / "cache",
            out_dir=self.tmp / "out",
            as_of=date(2026, 7, 1),
            refresh=True,
        )
        blk = card["markets"][0]
        self.assertEqual(blk["provenance"], "live_fetch")
        self.assertTrue(blk["diagnostics"]["converged"])
        self.assertLessEqual(blk["diagnostics"]["rmse_bps"], 25.0)
        self.assertTrue(card["unsigned"])
        self.assertIn("live_fetch", card["unsigned_reason"])
        self.assertEqual(
            blk["lineage"]["approved_by"], "UNSIGNED_pending_owner_approval")
        # Single-market run: cross-market gates are intentionally absent.
        self.assertEqual(card["gates"], [])

    def test_changed_live_quotes_change_digest(self):
        def fetcher_a(as_of):
            return _proxy_payload(as_of=as_of.isoformat())

        def fetcher_b(as_of):
            p = _proxy_payload(as_of=as_of.isoformat())
            for row in p["swaption_grid"]:
                row["normal_vol_bps"] += 5.0
            return p
        common = dict(markets=("CNY",), cache_dir=self.tmp / "c",
                      out_dir=self.tmp / "o", as_of=date(2026, 7, 1))
        card_a = run_hw1f_live_calibration(fetchers={"CNY": fetcher_a},
                                           refresh=True, **common)
        card_b = run_hw1f_live_calibration(fetchers={"CNY": fetcher_b},
                                           refresh=True, **common)
        self.assertNotEqual(card_a["inputs_digest"], card_b["inputs_digest"])
        self.assertNotEqual(card_a["markets"][0]["parameters"]["sigma_r"],
                            card_b["markets"][0]["parameters"]["sigma_r"])

    def test_dict_source_round_trips_fixture_source_conventions(self):
        cache = SnapshotCache(self.tmp / "cache")
        res = SwaptionSurfaceLoader("CNY", cache,
                                    fixture_as_of=FIXTURE_AS_OF).load()
        src = DictSwaptionSource(res)
        fixture = json.loads(
            (default_fixture_dir() / "cny_swaption_surface_20260101.json")
            .read_text(encoding="utf-8"))
        self.assertEqual(len(src.fetch_swaption_quotes()),
                         len(fixture["swaption_grid"]))
        self.assertEqual(src.fetch_initial_short_rate(),
                         fixture["initial_short_rate"])
        self.assertEqual(src.fetch_calibration_date().isoformat(),
                         fixture["as_of_date"])

    def test_markdown_renderer_complete(self):
        card = run_hw1f_live_calibration(
            markets=("CNY", "HKD"), cache_dir=self.tmp / "c")
        md = render_parameter_card_md(card)
        for token in ("UNSIGNED", "## CNY", "## HKD", "a (mean reversion)",
                      "Weighted SSE", "Converged", "G-02", "G-12",
                      card["inputs_digest"]):
            self.assertIn(str(token), md)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
