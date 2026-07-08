"""ES-3 - user economic-scenario ENGINE INTEGRATION (roadmap 4.0f, owner
directive 2026-07-08).

Covers the engine/run-layer wiring that turns a validated user scenario set
(ES-1 loader, ES-2 persist) into a governed run input:

* the ``scenario_source: model | user_file`` selector + ``run_intent`` reader
  (defaults + fail-loud on bad values);
* the MEASURE GUARD (valuation->risk_neutral, p_diagnostic->real_world) incl.
  the structured deviation record on a mismatch / missing / unknown-basis file
  and the raising ``enforce_measure_guard`` variant;
* the annual->monthly PIECEWISE-ANNUAL interpolation mapping (shapes, the
  year-end curve held across the year, the exact geometric equity split);
* ``attach_scenario_source_for_run`` (digest-keyed persistence + cache reuse,
  never-raise contract, digest re-verification / stale guard, the model-source
  light note) reusing the real ES-2 save path;
* the ``execute_run`` refusal branch when the measure guard fails (no run
  spawned), with the run gate patched clear so the guard is what stops it.
"""
from __future__ import annotations

import csv as _csv
import io
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

import numpy as np  # noqa: E402

from par_model_v2.stochastic.user_scenarios import (  # noqa: E402
    CSV_DEFAULT_NAME, EXPECTED_HEADER, MANIFEST_DEFAULT_NAME, MIN_SCENARIOS,
    PROJECTION_YEARS, SCHEMA_ID, TENOR_LABELS, TENOR_YEARS, UserScenarioSet,
    compute_csv_sha256, load_user_scenario_set)
from par_model_v2.stochastic.scenario_source import (  # noqa: E402
    MAPPING_SCHEMA_ID, MONTHS_PER_YEAR, SHORT_RATE_PROXY_TENOR,
    ScenarioInterpolationError, interpolate_monthly_paths,
    monthly_mapping_summary)
from par_model_v2.viewer.igui_scenario_source import (  # noqa: E402
    PROV_SCHEMA, RUN_SCENARIO_SOURCE_DIRNAME, SCENARIO_SOURCE_MODEL,
    SCENARIO_SOURCE_USER_FILE, ScenarioMeasureError, ScenarioSourceError,
    attach_scenario_source_for_run, build_scenario_source_provenance,
    enforce_measure_guard, evaluate_measure_guard, read_run_intent,
    read_scenario_source, required_basis_for_intent)
from par_model_v2.viewer.igui_scenarios import (  # noqa: E402
    build_scenario_save_response)

N_SCEN = MIN_SCENARIOS  # 100 x 100


# --------------------------------------------------------------- fixtures
def _rates_for(scen, year):
    base = 0.02 + 0.00005 * (scen % 7) + 0.00002 * (year % 11)
    return [round(base + 0.001 * i, 6) for i in range(len(TENOR_LABELS))]


def _eq_for(scen, year):
    return round(0.06 + 0.01 * ((scen + year) % 5) - 0.02 * (scen % 3), 6)


def _csv_text(n_scen=N_SCEN):
    rows = []
    for s in range(1, n_scen + 1):
        for y in range(1, PROJECTION_YEARS + 1):
            rows.append([s, y] + _rates_for(s, y) + [_eq_for(s, y)])
    buf = io.StringIO()
    w = _csv.writer(buf, lineterminator="\n")
    w.writerow(EXPECTED_HEADER)
    w.writerows(rows)
    return buf.getvalue()


def _manifest_text(csv_text, basis="risk_neutral", n_scen=N_SCEN):
    with tempfile.NamedTemporaryFile("wb", suffix=".csv", delete=False) as fh:
        fh.write(csv_text.encode("utf-8"))
        tmp = fh.name
    try:
        sha = compute_csv_sha256(tmp)
    finally:
        os.unlink(tmp)
    manifest = {
        "schema": SCHEMA_ID, "n_scenarios": n_scen,
        "projection_years": PROJECTION_YEARS, "basis": basis,
        "rate_convention": {"type": "zero_coupon_spot", "compounding": "annual",
                            "units": "decimal", "day_count": "ACT/365F"},
        "equity_convention": {"type": "annual_total_return", "units": "decimal"},
        "currency": "CNY", "source": "es3 unit synthetic (2026-07-08)",
        "created_utc": "2026-07-08T00:00:00Z", "csv_sha256": sha,
    }
    return json.dumps(manifest)


def _payload(basis="risk_neutral"):
    c = _csv_text()
    return {"csv_text": c, "manifest_text": _manifest_text(c, basis=basis)}


def _synthetic_set(n_scn=3, n_years=4, basis="risk_neutral"):
    """A small in-memory UserScenarioSet bypassing the loader's 100x100 floor
    (the interpolation only reads rates/eq_returns/tenor_labels)."""
    rng = np.random.default_rng(7)
    rates = 0.01 + 0.02 * rng.random((n_scn, n_years, len(TENOR_LABELS)))
    eq = -0.1 + 0.3 * rng.random((n_scn, n_years))
    return UserScenarioSet(
        n_scenarios=n_scn, projection_years=n_years, basis=basis,
        tenor_labels=TENOR_LABELS, tenor_years=TENOR_YEARS,
        rates=rates, eq_returns=eq, manifest={"currency": "CNY"},
        csv_sha256="0" * 64, csv_path="x.csv", manifest_path="x.json")


def _user_block(basis="risk_neutral", digest="ab" * 32):
    return {"schema": SCHEMA_ID, "csv_sha256": digest, "basis": basis,
            "n_scenarios": N_SCEN, "projection_years": PROJECTION_YEARS,
            "currency": "CNY", "source": "es3 unit"}


# --------------------------------------------------------------- selectors
class TestSelectors(unittest.TestCase):
    def test_source_defaults_to_model(self):
        self.assertEqual(read_scenario_source({}), SCENARIO_SOURCE_MODEL)
        self.assertEqual(read_scenario_source({"scenario_source": None}),
                         SCENARIO_SOURCE_MODEL)

    def test_source_explicit(self):
        self.assertEqual(read_scenario_source({"scenario_source": "user_file"}),
                         SCENARIO_SOURCE_USER_FILE)

    def test_source_bad_value_fails_loud(self):
        with self.assertRaises(ScenarioSourceError):
            read_scenario_source({"scenario_source": "made_up"})

    def test_intent_default_and_bad(self):
        self.assertEqual(read_run_intent({}), "valuation")
        with self.assertRaises(ScenarioSourceError):
            read_run_intent({"run_intent": "nope"})

    def test_required_basis_map(self):
        self.assertEqual(required_basis_for_intent("valuation"), "risk_neutral")
        self.assertEqual(required_basis_for_intent("p_diagnostic"), "real_world")


# ------------------------------------------------------------ measure guard
class TestMeasureGuard(unittest.TestCase):
    def test_model_source_guard_not_applicable(self):
        d = evaluate_measure_guard({"scenario_source": "model"})
        self.assertTrue(d["ok"])
        self.assertEqual(d["selector"], SCENARIO_SOURCE_MODEL)
        self.assertEqual(d["guard"], "not_applicable")

    def test_valuation_matches_risk_neutral(self):
        mi = {"scenario_source": "user_file", "run_intent": "valuation",
              "user_scenarios": _user_block("risk_neutral")}
        d = evaluate_measure_guard(mi)
        self.assertTrue(d["ok"])
        self.assertEqual(d["required_basis"], "risk_neutral")
        self.assertEqual(d["file_basis"], "risk_neutral")

    def test_p_diagnostic_matches_real_world(self):
        mi = {"scenario_source": "user_file", "run_intent": "p_diagnostic",
              "user_scenarios": _user_block("real_world")}
        self.assertTrue(evaluate_measure_guard(mi)["ok"])

    def test_measure_mismatch_is_error_with_deviation(self):
        mi = {"scenario_source": "user_file", "run_intent": "valuation",
              "user_scenarios": _user_block("real_world")}
        d = evaluate_measure_guard(mi)
        self.assertFalse(d["ok"])
        self.assertIn("mismatch", d["reason"])
        dev = d["deviation_record"]
        self.assertEqual(dev["record_type"], "SCENARIO_MEASURE_DEVIATION")
        self.assertEqual(dev["severity"], "ERROR")
        self.assertEqual(dev["required_basis"], "risk_neutral")
        self.assertEqual(dev["file_basis"], "real_world")

    def test_user_file_without_block_refused(self):
        d = evaluate_measure_guard({"scenario_source": "user_file"})
        self.assertFalse(d["ok"])
        self.assertIn("no scenario file", d["reason"])
        self.assertEqual(d["deviation_record"]["severity"], "ERROR")

    def test_unknown_basis_refused(self):
        mi = {"scenario_source": "user_file",
              "user_scenarios": _user_block("bogus")}
        d = evaluate_measure_guard(mi)
        self.assertFalse(d["ok"])
        self.assertIn("unknown", d["reason"])

    def test_enforce_raises_on_mismatch(self):
        mi = {"scenario_source": "user_file", "run_intent": "valuation",
              "user_scenarios": _user_block("real_world")}
        with self.assertRaises(ScenarioMeasureError) as ctx:
            enforce_measure_guard(mi)
        self.assertTrue(hasattr(ctx.exception, "decision"))
        self.assertFalse(ctx.exception.decision["ok"])

    def test_enforce_returns_decision_on_pass(self):
        mi = {"scenario_source": "model"}
        self.assertTrue(enforce_measure_guard(mi)["ok"])


# -------------------------------------------------------- monthly mapping
class TestMonthlyMapping(unittest.TestCase):
    def setUp(self):
        self.set = _synthetic_set(n_scn=3, n_years=4)

    def test_shapes_and_year_index(self):
        p = interpolate_monthly_paths(self.set)
        n_m = 4 * MONTHS_PER_YEAR
        self.assertEqual(p["schema"], MAPPING_SCHEMA_ID)
        self.assertEqual(p["short_rate"].shape, (3, n_m))
        self.assertEqual(p["equity_return"].shape, (3, n_m))
        self.assertEqual(p["rate_cube"].shape, (3, n_m, len(TENOR_LABELS)))
        # year index: 1 repeated 12x, then 2, ...
        self.assertEqual(list(p["year_index"][:12]), [1] * 12)
        self.assertEqual(list(p["year_index"][12:24]), [2] * 12)

    def test_piecewise_annual_short_rate(self):
        p = interpolate_monthly_paths(self.set)
        ti = list(TENOR_LABELS).index(SHORT_RATE_PROXY_TENOR)
        for y in range(4):
            yr_3m = self.set.rates[:, y, ti]                 # (3,)
            for m in range(y * 12, (y + 1) * 12):
                np.testing.assert_allclose(p["short_rate"][:, m], yr_3m)

    def test_geometric_equity_split_recompounds_exactly(self):
        p = interpolate_monthly_paths(self.set)
        for y in range(4):
            months = p["equity_return"][:, y * 12:(y + 1) * 12]
            recompound = np.prod(1.0 + months, axis=1) - 1.0
            np.testing.assert_allclose(
                recompound, self.set.eq_returns[:, y], atol=1e-12)

    def test_extreme_equity_bound_is_finite(self):
        s = _synthetic_set(n_scn=2, n_years=1)
        s.eq_returns[:] = -0.99            # spec lower bound
        p = interpolate_monthly_paths(s)
        self.assertTrue(np.all(np.isfinite(p["equity_return"])))

    def test_summary_card_checks(self):
        card = monthly_mapping_summary(self.set)
        self.assertEqual(card["schema"], MAPPING_SCHEMA_ID)
        self.assertEqual(card["short_rate_proxy_tenor"], SHORT_RATE_PROXY_TENOR)
        self.assertLess(card["checks"]["year1_recompound_max_abs_error"], 1e-9)

    def test_missing_proxy_tenor_fails_loud(self):
        s = _synthetic_set(n_scn=2, n_years=2)
        s.tenor_labels = tuple("Z%d" % i for i in range(len(TENOR_LABELS)))
        with self.assertRaises(ScenarioInterpolationError):
            interpolate_monthly_paths(s)

    def test_end_to_end_with_real_loader(self):
        """A real 100x100 file through the ES-1 loader interpolates cleanly."""
        tmp = tempfile.mkdtemp(prefix="es3_load_")
        c = _csv_text()
        cp = os.path.join(tmp, CSV_DEFAULT_NAME)
        mp = os.path.join(tmp, MANIFEST_DEFAULT_NAME)
        with open(cp, "w", encoding="utf-8") as fh:
            fh.write(c)
        with open(mp, "w", encoding="utf-8") as fh:
            fh.write(_manifest_text(c))
        sset = load_user_scenario_set(cp, mp)
        p = interpolate_monthly_paths(sset)
        self.assertEqual(p["n_months"], PROJECTION_YEARS * MONTHS_PER_YEAR)
        self.assertEqual(p["short_rate"].shape, (N_SCEN, p["n_months"]))


# ------------------------------------------------------------- provenance
class TestProvenanceBlock(unittest.TestCase):
    def test_user_file_provenance_carries_digest_and_mapping(self):
        mi = {"scenario_source": "user_file", "run_intent": "valuation",
              "user_scenarios": _user_block("risk_neutral", digest="cd" * 32)}
        guard = evaluate_measure_guard(mi)
        summ = monthly_mapping_summary(_synthetic_set())
        prov = build_scenario_source_provenance(mi, guard, summ)
        self.assertEqual(prov["schema"], PROV_SCHEMA)
        self.assertEqual(prov["scenario_source"], "user_file")
        self.assertTrue(prov["measure_guard"]["ok"])
        self.assertEqual(prov["file"]["csv_sha256"], "cd" * 32)
        self.assertEqual(prov["monthly_mapping"]["schema"], MAPPING_SCHEMA_ID)
        self.assertTrue(prov["unsigned"])

    def test_failed_guard_provenance_records_deviation(self):
        mi = {"scenario_source": "user_file", "run_intent": "valuation",
              "user_scenarios": _user_block("real_world")}
        guard = evaluate_measure_guard(mi)
        prov = build_scenario_source_provenance(mi, guard)
        self.assertFalse(prov["measure_guard"]["ok"])
        self.assertEqual(prov["deviation_record"]["severity"], "ERROR")


# ------------------------------------------------- attach_for_run (persist)
class TestAttachForRun(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="es3_attach_")
        self.out_path = os.path.join(self.tmp, "model_inputs.json")
        self.run_output = self.tmp                       # store root == run_output
        self.store_root = os.path.join(self.run_output, "user_scenarios")

    def _save(self, basis="risk_neutral"):
        res = build_scenario_save_response(
            _payload(basis=basis), self.out_path, self.store_root)
        self.assertTrue(res["ok"], res)
        return res

    def test_model_source_is_light_note_no_store(self):
        with open(self.out_path, "w", encoding="utf-8") as fh:
            json.dump({"scenario_source": "model"}, fh)
        att = attach_scenario_source_for_run(self.out_path, self.run_output)
        self.assertTrue(att["ok"])
        self.assertEqual(att["selector"], SCENARIO_SOURCE_MODEL)
        self.assertFalse(att["attached"])
        self.assertFalse(os.path.exists(
            os.path.join(self.run_output, RUN_SCENARIO_SOURCE_DIRNAME)))

    def test_user_file_attach_persists_and_caches(self):
        save = self._save("risk_neutral")
        digest = save["csv_sha256"]
        att = attach_scenario_source_for_run(self.out_path, self.run_output)
        self.assertTrue(att["ok"], att)
        self.assertEqual(att["selector"], SCENARIO_SOURCE_USER_FILE)
        self.assertTrue(att["attached"])
        self.assertTrue(att["guard_ok"])
        self.assertFalse(att["cached"])
        self.assertEqual(att["csv_sha256"], digest)
        prov_dir = os.path.join(self.run_output, RUN_SCENARIO_SOURCE_DIRNAME,
                                digest[:12])
        self.assertTrue(os.path.isfile(
            os.path.join(prov_dir, "SCENARIO_SOURCE_PROVENANCE.json")))
        self.assertEqual(att["provenance"]["monthly_mapping"]["n_months"],
                         PROJECTION_YEARS * MONTHS_PER_YEAR)
        # second attach on the same digest -> cache hit
        att2 = attach_scenario_source_for_run(self.out_path, self.run_output)
        self.assertTrue(att2["cached"])

    def test_tampered_persisted_file_is_stale(self):
        save = self._save("risk_neutral")
        csv_path = os.path.join(self.store_root, save["csv_sha256"][:12],
                                CSV_DEFAULT_NAME)
        with open(csv_path, "a", encoding="utf-8") as fh:
            fh.write("tampered\n")
        att = attach_scenario_source_for_run(self.out_path, self.run_output)
        self.assertFalse(att["ok"])
        self.assertTrue(att["stale"])
        self.assertTrue(any("no longer matches" in e for e in att["errors"]))

    def test_save_sets_selector_and_matched_intent(self):
        self._save("real_world")
        with open(self.out_path, encoding="utf-8") as fh:
            mi = json.load(fh)
        self.assertEqual(mi["scenario_source"], "user_file")
        self.assertEqual(mi["run_intent"], "p_diagnostic")  # real_world -> P
        # guard passes by construction
        self.assertTrue(evaluate_measure_guard(mi)["ok"])

    def test_attach_never_raises_on_garbage_inputs(self):
        with open(self.out_path, "w", encoding="utf-8") as fh:
            fh.write("{ not json")
        att = attach_scenario_source_for_run(self.out_path, self.run_output)
        self.assertFalse(att["ok"])


# --------------------------------------------- execute_run refusal wiring
class TestExecuteRunGuardRefusal(unittest.TestCase):
    def test_execute_run_refuses_on_measure_mismatch(self):
        from par_model_v2.viewer import igui_run_execution as ex
        tmp = tempfile.mkdtemp(prefix="es3_exec_")
        out_path = os.path.join(tmp, "model_inputs.json")
        mi = {"scenario_source": "user_file", "run_intent": "valuation",
              "user_scenarios": _user_block("real_world"),
              "run_gate": {"decision": "CLEARED"}}
        with open(out_path, "w", encoding="utf-8") as fh:
            json.dump(mi, fh)
        # Patch the run gate clear so the MEASURE GUARD is what stops the run.
        clear = {"ok": True, "reasons": [], "decision": "CLEARED",
                 "reproducibility_digest": "sha256:test"}
        with mock.patch.object(ex, "verify_run_gate", return_value=clear):
            res = ex.execute_run(out_path, os.path.join(tmp, "run_output"))
        self.assertFalse(res["ok"])
        self.assertEqual(res["stage"], "scenario_measure_guard")
        self.assertIn("mismatch", " ".join(res["errors"]))
        self.assertFalse(res["scenario_source_guard"]["ok"])
        # a model-source (or matched) run must NOT be refused by the guard:
        # prove the guard is the sole cause by flipping to a matching file.
        mi["user_scenarios"] = _user_block("risk_neutral")
        with open(out_path, "w", encoding="utf-8") as fh:
            json.dump(mi, fh)
        with mock.patch.object(ex, "verify_run_gate", return_value=clear):
            res2 = ex.execute_run(out_path, os.path.join(tmp, "run_output2"),
                                  python_exe="/bin/false")
        # guard passed -> it proceeds past the guard (fails later at spawn/run,
        # NOT at the scenario guard)
        self.assertNotEqual(res2.get("stage"), "scenario_measure_guard")


# ------------------------------------------------------- import discipline
class TestImportDiscipline(unittest.TestCase):
    def test_gui_layer_module_is_stdlib_only_at_import(self):
        """igui_scenario_source must import numpy / the ES-1 loader / the ES-3
        interpolation engine only LAZILY (the GUI-layer contract)."""
        import re
        path = os.path.join(REPO, "par_model_v2", "viewer",
                            "igui_scenario_source.py")
        with open(path, encoding="utf-8") as fh:
            s = fh.read()
        for mod in ("numpy", "pandas", "scipy"):
            self.assertIsNone(
                re.search(r"^(?:import|from)\s+%s\b" % mod, s, re.MULTILINE),
                "%s imported at module level" % mod)
        self.assertIsNone(
            re.search(r"^(?:import|from)\s+par_model_v2\.stochastic", s,
                      re.MULTILINE),
            "numpy-side engine imported at module level")


if __name__ == "__main__":
    unittest.main()
