"""Regression tests for the W204 cadence guard in scripts/agent_lock.py.

The guard exists because the scheduled task's cron was mis-set to hourly
(``0 * * * *``) instead of 12-hourly (``0 2,14 * * *``). Each spurious firing
rebuilt a venv, ran the whole verification battery and produced a near-duplicate
status document and email draft while making zero model progress -- 11 firings
on 2026-07-21 alone. ``preflight`` now yields when a completed cycle is more
recent than ``min_interval_minutes``.

The guard is a NOISE SUPPRESSOR, not a safety control. The tests below therefore
weight one property above all others: **it must fail open.** A wrongly-held lock
stalls one cycle; a wrongly-asserted cadence block would stall the project
indefinitely and silently, since every subsequent firing would re-evaluate the
same stale timestamp. Every malformed-input case is asserted to PROCEED.

Stdlib-only (no pytest required): run with
    python3 -m unittest tests.test_agent_lock_cadence -v
or directly:
    python3 tests/test_agent_lock_cadence.py
"""
import importlib.util
import json
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
LOCK_SCRIPT = REPO / "scripts" / "agent_lock.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("agent_lock_cadence_mod",
                                                  LOCK_SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


MOD = _load_module()


def _released(minutes_ago):
    """A released-lock dict whose cycle finished ``minutes_ago`` minutes back."""
    ts = MOD._iso(MOD._now() - timedelta(minutes=minutes_ago))
    return {"owner": None, "released_at": ts, "released_by": "claude",
            "ttl_minutes": 120}


class CadenceGuardTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / ".claude-dev").mkdir(parents=True, exist_ok=True)
        self.addCleanup(self._tmp.cleanup)

    def _policy(self, obj, raw=None):
        p = self.root / MOD.CADENCE_POLICY_FILE
        p.write_text(raw if raw is not None else json.dumps(obj),
                     encoding="utf-8")

    # ---- the guard firing as designed -------------------------------------

    def test_blocks_when_last_cycle_is_too_recent(self):
        self._policy({"enabled": True, "min_interval_minutes": 600})
        got = MOD._cadence_block(self.root, _released(45))
        self.assertIsNotNone(got)
        self.assertEqual(got["decision"], "YIELD")
        self.assertEqual(got["reason"], "cadence")
        self.assertEqual(got["min_interval_minutes"], 600)
        self.assertLess(got["minutes_since_last_cycle"], 600)
        self.assertEqual(got["override"], "--ignore-cadence")

    def test_allows_once_interval_has_elapsed(self):
        self._policy({"enabled": True, "min_interval_minutes": 600})
        self.assertIsNone(MOD._cadence_block(self.root, _released(601)))

    def test_boundary_is_inclusive_exactly_at_interval_proceeds(self):
        self._policy({"enabled": True, "min_interval_minutes": 600})
        self.assertIsNone(MOD._cadence_block(self.root, _released(600)))

    def test_twelve_hour_cadence_is_never_blocked_by_the_600_min_policy(self):
        """The shipped policy must be inert once the cron is corrected."""
        shipped = json.loads(
            (REPO / MOD.CADENCE_POLICY_FILE).read_text(encoding="utf-8"))
        self.assertLess(shipped["min_interval_minutes"], 12 * 60,
                        "policy interval must sit below the intended 12h "
                        "cadence or correct schedules would self-suppress")

    # ---- fail-open properties ---------------------------------------------

    def test_missing_policy_proceeds(self):
        self.assertIsNone(MOD._cadence_block(self.root, _released(1)))

    def test_malformed_policy_proceeds(self):
        self._policy(None, raw="{not json at all")
        self.assertIsNone(MOD._cadence_block(self.root, _released(1)))

    def test_policy_of_wrong_shape_proceeds(self):
        self._policy(None, raw='["a", "list", "not", "an", "object"]')
        self.assertIsNone(MOD._cadence_block(self.root, _released(1)))

    def test_disabled_policy_proceeds(self):
        self._policy({"enabled": False, "min_interval_minutes": 600})
        self.assertIsNone(MOD._cadence_block(self.root, _released(1)))

    def test_non_positive_and_non_numeric_intervals_proceed(self):
        for bad in (0, -30, "soon", None):
            with self.subTest(interval=bad):
                self._policy({"enabled": True, "min_interval_minutes": bad})
                self.assertIsNone(MOD._cadence_block(self.root, _released(1)))

    def test_absent_released_at_proceeds(self):
        """A cycle that CRASHED never writes released_at -> must not compound."""
        self._policy({"enabled": True, "min_interval_minutes": 600})
        self.assertIsNone(MOD._cadence_block(self.root, {"owner": None}))

    def test_unparseable_released_at_proceeds(self):
        self._policy({"enabled": True, "min_interval_minutes": 600})
        self.assertIsNone(MOD._cadence_block(
            self.root, {"owner": None, "released_at": "last Tuesday"}))

    def test_held_lock_is_not_the_cadence_guards_business(self):
        """_is_held owns that decision; the cadence guard must abstain."""
        self._policy({"enabled": True, "min_interval_minutes": 600})
        held = {"owner": "codex", "started_at": MOD._iso(MOD._now()),
                "ttl_minutes": 120, "released_at": MOD._iso(MOD._now())}
        self.assertIsNone(MOD._cadence_block(self.root, held))

    # ---- policy loader ----------------------------------------------------

    def test_loader_returns_empty_dict_on_every_bad_input(self):
        self.assertEqual(MOD._load_cadence_policy(self.root), {})
        self._policy(None, raw="}{")
        self.assertEqual(MOD._load_cadence_policy(self.root), {})
        self._policy(None, raw="42")
        self.assertEqual(MOD._load_cadence_policy(self.root), {})

    def test_shipped_policy_parses_and_is_self_documenting(self):
        pol = json.loads(
            (REPO / MOD.CADENCE_POLICY_FILE).read_text(encoding="utf-8"))
        self.assertIsInstance(pol, dict)
        for key in ("enabled", "min_interval_minutes", "rationale",
                    "disable_procedure", "fail_open"):
            self.assertIn(key, pol)


if __name__ == "__main__":
    unittest.main(verbosity=2)
