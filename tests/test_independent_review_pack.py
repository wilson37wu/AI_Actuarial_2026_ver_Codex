"""
Unit tests — Independent-Review Readiness Pack (roadmap §4.1 #9).

Guarantees the pack's Definition of Done: a single ``docs/INDEPENDENT_REVIEW_PACK.md``
index in which **every link resolves**. Also asserts the pack retains the structural
content an APS X2 / TAS M §3.6.5 reviewer relies on (the five mandated scope areas,
the TAS M requirement map, and the #1–#8 post-review evidence ledger).

stdlib-only / unittest — scipy + pytest are unavailable in the network-restricted CI
sandbox; run directly with ``python3 -m unittest tests.test_independent_review_pack -v``.
"""
from __future__ import annotations

import os
import re
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(_HERE)
DOCS_DIR = os.path.join(REPO_ROOT, "docs")
PACK_PATH = os.path.join(DOCS_DIR, "INDEPENDENT_REVIEW_PACK.md")

# [text](target) — target captured up to the first ')'
_LINK_RE = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
_EXTERNAL_PREFIXES = ("http://", "https://", "mailto:")


def _load_pack() -> str:
    with open(PACK_PATH, encoding="utf-8") as fh:
        return fh.read()


def _link_targets(text: str):
    """All in-repo (non-external, non-anchor) link targets, anchors stripped."""
    out = []
    for raw in _LINK_RE.findall(text):
        target = raw.strip()
        if not target or target.startswith("#"):
            continue
        if target.lower().startswith(_EXTERNAL_PREFIXES):
            continue
        target = target.split("#", 1)[0].strip()  # drop any #fragment
        if target:
            out.append(target)
    return out


class PackExistsTests(unittest.TestCase):
    def test_pack_file_present(self):
        self.assertTrue(os.path.isfile(PACK_PATH), f"missing {PACK_PATH}")

    def test_pack_non_trivial(self):
        self.assertGreater(len(_load_pack()), 4000, "pack unexpectedly small")


class LinkResolutionTests(unittest.TestCase):
    """The core Definition of Done — every relative link resolves."""

    def test_links_present(self):
        # Guard against an accidentally gutted index.
        self.assertGreaterEqual(len(_link_targets(_load_pack())), 60)

    def test_every_link_resolves(self):
        text = _load_pack()
        missing = []
        for target in _link_targets(text):
            # Links render on GitHub relative to the pack's own directory (docs/).
            resolved = os.path.normpath(os.path.join(DOCS_DIR, target))
            if not os.path.exists(resolved):
                missing.append(target)
        self.assertEqual(missing, [], f"unresolved links: {missing}")

    def test_no_links_escape_repo(self):
        text = _load_pack()
        root_abs = os.path.abspath(REPO_ROOT)
        for target in _link_targets(text):
            resolved = os.path.abspath(os.path.join(DOCS_DIR, target))
            self.assertTrue(
                resolved.startswith(root_abs),
                f"link escapes repo root: {target}",
            )


class StructuralContentTests(unittest.TestCase):
    def setUp(self):
        self.text = _load_pack()

    def test_standards_named(self):
        self.assertIn("APS X2", self.text)
        self.assertIn("TAS M", self.text)

    def test_five_aps_x2_areas_present(self):
        for area in (
            "Model architecture & design",
            "Parameterisation & calibration",
            "Validation framework & results",
            "Governance, change control & risk register",
            "Documentation adequacy",
        ):
            self.assertIn(area, self.text, f"missing APS X2 area: {area}")

    def test_foundational_review_linked(self):
        self.assertIn(
            "validation/PHASE13_APS_X2_INDEPENDENT_REVIEW.md",
            self.text,
            "foundational APS X2 review not linked",
        )

    def test_all_eight_increment_status_links_present(self):
        for slug in (
            "LATEST_CYCLE_STATUS_2026_07_03_live_market_data_pipeline.md",
            "LATEST_CYCLE_STATUS_2026_07_08_hw1f_live_calibration.md",
            "LATEST_CYCLE_STATUS_2026_07_09_cbirc_discount_cap.md",
            "LATEST_CYCLE_STATUS_2026_07_09_dynamic_lapse_elasticity_tvog.md",
            "LATEST_CYCLE_STATUS_2026_07_09_scenario_adequacy.md",
            "LATEST_CYCLE_STATUS_2026_07_09_backtest_real_history.md",
            "LATEST_CYCLE_STATUS_2026_07_09_g2pp_promotion.md",
            "LATEST_CYCLE_STATUS_2026_07_09_pathwise_tvog_bridge.md",
        ):
            self.assertIn(slug, self.text, f"missing increment status link: {slug}")

    def test_open_residuals_disclosed(self):
        # Honesty gate: production residuals must be visible, not glossed.
        self.assertIn("OPEN production residual", self.text)
        self.assertIn("human APS X2 reviewer", self.text)

    def test_link_resolution_test_referenced(self):
        self.assertIn("tests/test_independent_review_pack.py", self.text)


if __name__ == "__main__":
    unittest.main()
