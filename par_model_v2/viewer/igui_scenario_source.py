"""ES-3 - User economic-scenario ENGINE INTEGRATION (GUI/run layer).

Wires a validated user scenario set (ES-1 loader, ES-2 persist) into the
governed run pipeline as a FIRST-CLASS, measure-guarded, governance-recorded
run input:

* :func:`read_scenario_source` / :func:`read_run_intent` - the run-config
  selector ``scenario_source: model | user_file`` and the run measure intent
  ``valuation | p_diagnostic`` (both default to the governed behaviour);
* :func:`evaluate_measure_guard` / :func:`enforce_measure_guard` - the MEASURE
  GUARD: a valuation run demands a ``risk_neutral`` file, a P-measure
  diagnostic run demands a ``real_world`` file; a mismatch is an ERROR that
  carries a structured DEVIATION RECORD and REFUSES the run;
* :func:`attach_scenario_source_for_run` - best-effort, digest-cached: reload
  the persisted set, RE-VERIFY its file digest, derive the annual->monthly
  interpolation summary, and record the file digest + manifest + guard
  decision into the run governance trail (a ``scenario_source`` provenance
  block the caller stamps onto the run artifacts).

Discipline: STANDARD LIBRARY ONLY at import time - numpy, the ES-1 loader and
the ES-3 interpolation engine are imported LAZILY inside the builders (the
GUI-layer contract, mirrored on :mod:`igui_scenarios`).  Purely additive: the
default selector is ``model`` so a run that does not opt in is bit-identical,
and the governed headline (TVOG / aggregation report) is never touched.

User scenario files remain UNSIGNED pending Model Owner approval; every
consumed set carries its sha256 file digest.
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional

# ---- selector + intent vocabulary ---------------------------------------
SCENARIO_SOURCE_MODEL = "model"
SCENARIO_SOURCE_USER_FILE = "user_file"
VALID_SCENARIO_SOURCES = (SCENARIO_SOURCE_MODEL, SCENARIO_SOURCE_USER_FILE)

RUN_INTENT_VALUATION = "valuation"
RUN_INTENT_P_DIAGNOSTIC = "p_diagnostic"
VALID_RUN_INTENTS = (RUN_INTENT_VALUATION, RUN_INTENT_P_DIAGNOSTIC)

#: The measure each run intent REQUIRES of a user scenario file.
INTENT_REQUIRED_BASIS = {
    RUN_INTENT_VALUATION: "risk_neutral",     # Q measure for capital/TVOG
    RUN_INTENT_P_DIAGNOSTIC: "real_world",    # P measure for diagnostics
}

#: Where uploaded sets are persisted (under the run_output root, ES-2).
SCENARIO_STORE_DIRNAME = "user_scenarios"
#: Where the per-run scenario-source provenance is persisted (digest-keyed,
#: mirrors CF-2 ``cashflow_set_runs`` / GD-4 ``path_detail_runs``).
RUN_SCENARIO_SOURCE_DIRNAME = "scenario_source_runs"
PROVENANCE_NAME = "SCENARIO_SOURCE_PROVENANCE.json"

PROV_SCHEMA = "es3-scenario-source-prov-1.0"

UNSIGNED_BANNER = (
    "UNSIGNED - user economic scenario files are scenario INPUTS pending "
    "Model Owner approval of the generating source.")


class ScenarioSourceError(ValueError):
    """Invalid scenario-source / run-intent configuration."""


class ScenarioMeasureError(ScenarioSourceError):
    """The user file's measure basis does not match the run intent."""


# ---- selector + intent readers ------------------------------------------
def read_scenario_source(model_inputs: Dict[str, Any]) -> str:
    """The run's scenario source. Defaults to ``model`` (governed ESG).

    Raises :class:`ScenarioSourceError` on an unrecognised explicit value so a
    typo can never silently fall back to the built-in generator."""
    val = (model_inputs or {}).get("scenario_source", SCENARIO_SOURCE_MODEL)
    if val is None:
        return SCENARIO_SOURCE_MODEL
    val = str(val).strip()
    if val not in VALID_SCENARIO_SOURCES:
        raise ScenarioSourceError(
            "scenario_source must be one of %r; got %r"
            % (VALID_SCENARIO_SOURCES, val))
    return val


def read_run_intent(model_inputs: Dict[str, Any]) -> str:
    """The run's measure intent. Defaults to ``valuation`` (Q measure)."""
    val = (model_inputs or {}).get("run_intent", RUN_INTENT_VALUATION)
    if val is None:
        return RUN_INTENT_VALUATION
    val = str(val).strip()
    if val not in VALID_RUN_INTENTS:
        raise ScenarioSourceError(
            "run_intent must be one of %r; got %r" % (VALID_RUN_INTENTS, val))
    return val


def required_basis_for_intent(intent: str) -> str:
    """The scenario-file measure basis a given run intent requires."""
    try:
        return INTENT_REQUIRED_BASIS[intent]
    except KeyError as exc:
        raise ScenarioSourceError("unknown run_intent %r" % intent) from exc


def _deviation_record(*, reason: str, selector: str, intent: str,
                      required_basis: Optional[str], file_basis: Optional[str],
                      digest: Optional[str], now: str) -> Dict[str, Any]:
    """A structured model-risk deviation record for a guard failure."""
    return {
        "record_type": "SCENARIO_MEASURE_DEVIATION",
        "severity": "ERROR",
        "detected_at": now,
        "reason": reason,
        "scenario_source": selector,
        "run_intent": intent,
        "required_basis": required_basis,
        "file_basis": file_basis,
        "file_sha256": digest,
        "resolution": ("run REFUSED - upload a %s scenario file, or set "
                       "run_intent to match the file's measure basis"
                       % (required_basis if required_basis else "matching")),
        "reference": "docs/ECONOMIC_SCENARIO_FILE_FORMAT.md (ES-3 measure guard)",
    }


def _utcnow() -> str:
    import datetime as _dt
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def evaluate_measure_guard(model_inputs: Dict[str, Any]) -> Dict[str, Any]:
    """Decide whether the run may proceed under the measure guard.

    Returns a JSON-safe decision dict ``{ok, selector, ...}``.  For a
    ``model`` source the guard is not applicable (``ok=True``).  For a
    ``user_file`` source it requires a recorded ``user_scenarios`` block whose
    ``basis`` matches the run intent; a mismatch (or a missing / unknown-basis
    block) yields ``ok=False`` with a structured ``deviation_record``.  Never
    raises for an expected failure - see :func:`enforce_measure_guard` for the
    raising variant."""
    selector = read_scenario_source(model_inputs)
    intent = read_run_intent(model_inputs)
    now = _utcnow()
    if selector == SCENARIO_SOURCE_MODEL:
        return {"ok": True, "selector": selector, "run_intent": intent,
                "guard": "not_applicable",
                "note": "built-in HW1F+GBM ESG (governed); measure guard n/a"}

    required = required_basis_for_intent(intent)
    block = (model_inputs or {}).get("user_scenarios")
    if not isinstance(block, dict) or not block:
        return {"ok": False, "selector": selector, "run_intent": intent,
                "required_basis": required, "file_basis": None,
                "reason": "scenario_source=user_file but no scenario file is "
                          "recorded (upload one on /scenarios first)",
                "deviation_record": _deviation_record(
                    reason="no user scenario file recorded", selector=selector,
                    intent=intent, required_basis=required, file_basis=None,
                    digest=None, now=now)}

    file_basis = block.get("basis")
    digest = block.get("csv_sha256")
    if file_basis not in ("risk_neutral", "real_world"):
        return {"ok": False, "selector": selector, "run_intent": intent,
                "required_basis": required, "file_basis": file_basis,
                "csv_sha256": digest,
                "reason": "recorded scenario file has an unknown measure basis "
                          "%r" % (file_basis,),
                "deviation_record": _deviation_record(
                    reason="unknown file measure basis", selector=selector,
                    intent=intent, required_basis=required,
                    file_basis=file_basis, digest=digest, now=now)}

    if file_basis != required:
        return {"ok": False, "selector": selector, "run_intent": intent,
                "required_basis": required, "file_basis": file_basis,
                "csv_sha256": digest,
                "reason": ("measure mismatch - a %s run requires a %s scenario "
                           "file but the recorded file is %s"
                           % (intent, required, file_basis)),
                "deviation_record": _deviation_record(
                    reason="measure basis mismatch", selector=selector,
                    intent=intent, required_basis=required,
                    file_basis=file_basis, digest=digest, now=now)}

    return {"ok": True, "selector": selector, "run_intent": intent,
            "required_basis": required, "file_basis": file_basis,
            "csv_sha256": digest, "guard": "pass",
            "note": "measure guard PASS (%s matches %s intent)"
                    % (file_basis, intent)}


def enforce_measure_guard(model_inputs: Dict[str, Any]) -> Dict[str, Any]:
    """Raising variant of :func:`evaluate_measure_guard`: returns the decision
    on success, raises :class:`ScenarioMeasureError` on a guard failure (the
    exception message is the human reason; the decision, incl. the deviation
    record, is attached as ``.decision``)."""
    decision = evaluate_measure_guard(model_inputs)
    if not decision.get("ok"):
        err = ScenarioMeasureError(decision.get("reason", "measure guard failed"))
        err.decision = decision  # type: ignore[attr-defined]
        raise err
    return decision


# ---- provenance + monthly-mapping attachment ----------------------------
def build_scenario_source_provenance(
        model_inputs: Dict[str, Any], guard: Dict[str, Any],
        mapping_summary: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """The ``scenario_source`` provenance block recorded into the run
    governance trail: selector, measure-guard decision, file digest +
    manifest subset, and the annual->monthly interpolation summary."""
    selector = guard.get("selector")
    block = (model_inputs or {}).get("user_scenarios") or {}
    prov: Dict[str, Any] = {
        "record_type": "SCENARIO_SOURCE_PROVENANCE",
        "schema": PROV_SCHEMA,
        "stamped_at": _utcnow(),
        "scenario_source": selector,
        "run_intent": guard.get("run_intent"),
        "measure_guard": {
            "ok": bool(guard.get("ok")),
            "required_basis": guard.get("required_basis"),
            "file_basis": guard.get("file_basis"),
            "note": guard.get("note") or guard.get("reason"),
        },
        "unsigned": True,
        "unsigned_banner": UNSIGNED_BANNER,
    }
    if guard.get("deviation_record"):
        prov["deviation_record"] = guard["deviation_record"]
    if selector == SCENARIO_SOURCE_USER_FILE and block:
        prov["file"] = {
            "csv_sha256": block.get("csv_sha256"),
            "schema": block.get("schema"),
            "basis": block.get("basis"),
            "n_scenarios": block.get("n_scenarios"),
            "projection_years": block.get("projection_years"),
            "currency": block.get("currency"),
            "source": block.get("source"),
        }
    if mapping_summary is not None:
        prov["monthly_mapping"] = mapping_summary
    return prov


def _verify_persisted_digest(store_dir: str, digest: str) -> Optional[str]:
    """Re-hash the persisted CSV; return an error string if it is missing or
    no longer matches the recorded digest (never trust the store blindly)."""
    from par_model_v2.stochastic.user_scenarios import (  # lazy
        CSV_DEFAULT_NAME, compute_csv_sha256)
    csv_path = os.path.join(store_dir, CSV_DEFAULT_NAME)
    if not os.path.exists(csv_path):
        return "persisted scenario CSV not found at %s" % csv_path
    try:
        actual = compute_csv_sha256(csv_path)
    except OSError as exc:
        return "digest re-check unavailable: %s" % exc
    if actual != digest:
        return ("persisted scenario CSV digest %s no longer matches the "
                "recorded digest %s (file changed on disk)" % (actual, digest))
    return None


def attach_scenario_source_for_run(inputs_path: str,
                                   out_root: str) -> Dict[str, Any]:
    """Best-effort: record the run's scenario source into the governance trail
    and (for a user file) derive + persist the monthly-interpolation summary,
    digest-keyed like CF-2 / GD-4.  NEVER raises for an expected condition;
    returns a JSON-safe attachment block carrying the ``provenance`` the caller
    stamps onto the run artifacts.

    For ``scenario_source=model`` this is a light note (no store written, run
    stays bit-identical).  For ``user_file`` it RE-VERIFIES the persisted file
    digest, loads the set, computes the mapping summary and writes the
    provenance under ``<out_root>/scenario_source_runs/<digest12>/``."""
    try:
        with open(inputs_path, encoding="utf-8") as fh:
            mi = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        return {"ok": False, "errors": ["could not read model_inputs: %s" % exc]}

    try:
        selector = read_scenario_source(mi)
        guard = evaluate_measure_guard(mi)
    except ScenarioSourceError as exc:
        return {"ok": False, "errors": [str(exc)]}

    if selector == SCENARIO_SOURCE_MODEL:
        prov = build_scenario_source_provenance(mi, guard)
        return {"ok": True, "selector": selector, "guard_ok": True,
                "attached": False, "provenance": prov,
                "note": "built-in ESG (governed); no user file recorded"}

    block = mi.get("user_scenarios") or {}
    digest = block.get("csv_sha256")
    if not digest:
        return {"ok": False, "selector": selector,
                "errors": ["scenario_source=user_file but no recorded digest"]}

    store_dir = os.path.join(out_root, SCENARIO_STORE_DIRNAME, str(digest)[:12])
    digest_err = _verify_persisted_digest(store_dir, digest)
    if digest_err:
        # Still surface the guard provenance so the trail records the failure.
        prov = build_scenario_source_provenance(mi, guard)
        return {"ok": False, "selector": selector, "stale": True,
                "errors": [digest_err], "provenance": prov}

    # Load the set + derive the monthly-mapping summary (lazy numpy engine).
    try:
        from par_model_v2.stochastic.user_scenarios import (  # lazy
            CSV_DEFAULT_NAME, MANIFEST_DEFAULT_NAME, load_user_scenario_set)
        from par_model_v2.stochastic.scenario_source import (  # lazy
            monthly_mapping_summary)
        sset = load_user_scenario_set(
            os.path.join(store_dir, CSV_DEFAULT_NAME),
            os.path.join(store_dir, MANIFEST_DEFAULT_NAME))
        mapping_summary = monthly_mapping_summary(sset)
    except Exception as exc:  # loader/interp failure - never break the run
        prov = build_scenario_source_provenance(mi, guard)
        return {"ok": False, "selector": selector,
                "errors": ["scenario mapping unavailable: %s" % exc],
                "provenance": prov}

    prov = build_scenario_source_provenance(mi, guard, mapping_summary)

    # Persist the provenance digest-keyed (cache hit if identical file re-run).
    run_dir = os.path.join(out_root, RUN_SCENARIO_SOURCE_DIRNAME,
                           str(digest)[:12])
    prov_path = os.path.join(run_dir, PROVENANCE_NAME)
    cached = False
    try:
        if os.path.exists(prov_path):
            with open(prov_path, encoding="utf-8") as fh:
                existing = json.load(fh)
            if (existing.get("schema") == PROV_SCHEMA
                    and (existing.get("file") or {}).get("csv_sha256") == digest):
                cached = True
        if not cached:
            os.makedirs(run_dir, exist_ok=True)
            tmp = prov_path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(prov, fh, indent=1)
            with open(tmp, encoding="utf-8") as fh:
                json.load(fh)  # re-parse guard
            os.replace(tmp, prov_path)
    except OSError as exc:
        return {"ok": False, "selector": selector,
                "errors": ["could not persist provenance: %s" % exc],
                "provenance": prov}

    return {"ok": True, "selector": selector, "guard_ok": bool(guard.get("ok")),
            "attached": True, "cached": cached, "csv_sha256": digest,
            "dir": os.path.abspath(run_dir), "provenance": prov,
            "monthly_mapping": mapping_summary}
