"""GD-3 - Stepwise run-result decomposition set (owner directive 2026-07-07).

Owner requirement (roadmap 4.0e, GD-3): surface the per-driver standalone
SCR build-up from the RUN ARTIFACTS in the results GUI as a calculation
WATERFALL - how the seven standalone driver SCRs aggregate through the
var-covar credit, the copula tail-dependence uplift, and the nested
interaction residual into the headline nested SCR.

READ-ONLY over the run artifact: every number is lifted bit-for-bit from
``run_output/RUN_MODEL_AGGREGATION_REPORT.json`` (the evidence file
``scripts/run_model.py`` writes with the SAME structural contract as the
governed Phase 22 Task 4 aggregation report). This module NEVER re-runs
the engine and NEVER touches governed headline figures - it is a
diagnostic decomposition overlay, exactly like GD-1/GD-2.

Waterfall identities (asserted, fail-loud):

    sum(standalone_scr[d])            == standalone_scr_sum
    standalone_scr_sum + div_credit   == var_covar_scr
    var_covar_scr + copula_uplift     == copula_scr
    copula_scr + nested_residual      == nested_scr   (the headline)

Scope note: the executed-run artifact set carries the SCR aggregation
evidence only; the governed TVOG headline is produced by a separate,
owner-gated pipeline and is NOT decomposed here (kept untouched per the
standing constraint).

Artifacts (when ``out_dir`` is given): ``RUN_DECOMPOSITION_SET.json`` plus
four tidy CSVs (waterfall steps, per-driver standalone SCRs, copula
candidates, tail-convergence path), all stamped with a digest of the
source artifact bytes for cache invalidation.
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
from typing import Any, Dict, List, Optional

SCHEMA_VERSION = "run-decomposition-1.0"
JSON_NAME = "RUN_DECOMPOSITION_SET.json"
CSV_NAMES = ["decomposition_waterfall.csv",
             "decomposition_drivers.csv",
             "decomposition_copulas.csv",
             "decomposition_convergence.csv"]

#: The evidence file scripts/run_model.py writes into run_output/ (kept in
#: lock-step with scripts.run_model.AGG_REPORT_NAME - regression-tested).
AGG_REPORT_NAME = "RUN_MODEL_AGGREGATION_REPORT.json"

UNSIGNED_NOTE = ("Diagnostic decomposition of the run's SCR aggregation "
                 "evidence. Values are read bit-for-bit from the run "
                 "artifact; the view itself is UNSIGNED and is not a "
                 "governed report.")

#: Reconciliation tolerance (relative) for the waterfall identities.
_REL_TOL = 1e-9


def artifact_digest(path: str) -> str:
    """sha256 over the raw artifact bytes (cache key / provenance stamp)."""
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return "sha256:" + h.hexdigest()


def _close(a: float, b: float) -> bool:
    scale = max(abs(a), abs(b), 1.0)
    return abs(a - b) <= _REL_TOL * scale


def build_waterfall(agg: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Ordered waterfall steps from the ``aggregation`` dict.

    kinds: ``build`` (additive standalone driver bar), ``subtotal``
    (running anchor), ``delta`` (signed aggregation adjustment), ``final``
    (the headline nested SCR). Each step carries the running cumulative,
    so the GUI can draw floating bars without re-deriving arithmetic."""
    standalone = agg.get("standalone_scr") or {}
    drivers = agg.get("drivers") or sorted(standalone)
    ssum = float(agg["standalone_scr_sum"])
    vc = float(agg["var_covar_scr"])
    cop = float(agg["copula_scr"])
    nested = float(agg["nested_scr"])

    got_sum = sum(float(standalone[d]) for d in drivers)
    if not _close(got_sum, ssum):
        raise ValueError("standalone SCRs do not sum to standalone_scr_sum "
                         "(%r vs %r) - artifact inconsistent" % (got_sum, ssum))

    steps: List[Dict[str, Any]] = []
    cum = 0.0
    for d in drivers:
        v = float(standalone[d])
        cum += v
        steps.append({"id": "standalone_%s" % d, "kind": "build",
                      "label": "%s standalone SCR" % d,
                      "value": v, "cumulative": cum})
    steps.append({"id": "standalone_sum", "kind": "subtotal",
                  "label": "Sum of standalone SCRs",
                  "value": ssum, "cumulative": ssum})
    steps.append({"id": "diversification", "kind": "delta",
                  "label": "Diversification credit (var-covar)",
                  "value": vc - ssum, "cumulative": vc})
    steps.append({"id": "var_covar", "kind": "subtotal",
                  "label": "Var-covar SCR", "value": vc, "cumulative": vc})
    steps.append({"id": "copula_uplift", "kind": "delta",
                  "label": "Copula tail-dependence adjustment (%s)"
                           % agg.get("copula_selected"),
                  "value": cop - vc, "cumulative": cop})
    steps.append({"id": "copula", "kind": "subtotal",
                  "label": "Copula SCR (%s)" % agg.get("copula_selected"),
                  "value": cop, "cumulative": cop})
    steps.append({"id": "nested_residual", "kind": "delta",
                  "label": "Nested interaction residual",
                  "value": nested - cop, "cumulative": nested})
    steps.append({"id": "nested", "kind": "final",
                  "label": "Nested SCR (headline)",
                  "value": nested, "cumulative": nested})

    # fail-loud identity re-check on the finished ladder
    if not (_close(steps[-1]["cumulative"], nested)
            and _close(steps[len(drivers)]["cumulative"], ssum)):
        raise ValueError("waterfall does not reconcile - refusing to emit")
    return steps


def _driver_rows(agg: Dict[str, Any]) -> List[Dict[str, Any]]:
    standalone = agg.get("standalone_scr") or {}
    drivers = agg.get("drivers") or sorted(standalone)
    ssum = float(agg["standalone_scr_sum"]) or 1.0
    return [{"driver": d, "standalone_scr": float(standalone[d]),
             "share_of_sum_pct": 100.0 * float(standalone[d]) / ssum}
            for d in drivers]


def _copula_rows(agg: Dict[str, Any]) -> List[Dict[str, Any]]:
    sel = agg.get("copula_selected")
    rows = []
    for c in ((agg.get("copula_report") or {}).get("copulas") or []):
        rows.append({"name": c.get("name"),
                     "n_params": c.get("n_params"),
                     "loglik": c.get("loglik"),
                     "aic": c.get("aic"),
                     "upper_tail_dependence": c.get("upper_tail_dependence"),
                     "selected": c.get("name") == sel})
    return rows


def _convergence(agg: Dict[str, Any]) -> Dict[str, Any]:
    td = agg.get("tail_diagnostics") or {}
    if td.get("skipped"):
        return {"skipped": True}
    return {"skipped": False,
            "n_sim_grid": td.get("n_sim_grid") or [],
            "var_path": td.get("var_convergence_path") or [],
            "es_path": td.get("es_convergence_path") or [],
            "successive_var_rel_deltas":
                td.get("successive_var_rel_deltas") or [],
            "converged": td.get("converged"),
            "convergence_tolerance": td.get("convergence_tolerance"),
            "confidence_level": td.get("confidence_level")}


def _bootstrap(agg: Dict[str, Any]) -> Dict[str, Any]:
    td = agg.get("tail_diagnostics") or {}
    bs = td.get("simulated_bootstrap") or {}
    return {k: bs.get(k) for k in ("var_point", "var_ci", "es_point",
                                   "es_ci", "var_ci_rel_halfwidth",
                                   "n_bootstrap")}


def decompose_report(report: Dict[str, Any]) -> Dict[str, Any]:
    """Aggregation-report dict -> decomposition dict (no I/O)."""
    agg = report.get("aggregation")
    if not isinstance(agg, dict):
        raise ValueError("artifact has no 'aggregation' section - not a "
                         "run_model aggregation report")
    return {
        "ok": True,
        "schema": SCHEMA_VERSION,
        "unsigned_note": UNSIGNED_NOTE,
        "provenance": {
            "run_timestamp": report.get("run_timestamp"),
            "output_label": report.get("output_label"),
            "generator": report.get("generator"),
            "inputs": (report.get("inputs_provenance") or {}).get(
                "model_inputs"),
            "verdict": agg.get("verdict"),
            "confidence_level": (agg.get("config") or {}).get(
                "confidence_level"),
            "seed": (agg.get("config") or {}).get("seed"),
        },
        "headline": {
            "nested_scr": agg.get("nested_scr"),
            "copula_scr": agg.get("copula_scr"),
            "copula_selected": agg.get("copula_selected"),
            "var_covar_scr": agg.get("var_covar_scr"),
            "standalone_scr_sum": agg.get("standalone_scr_sum"),
            "esg_understatement_pct": agg.get("esg_understatement_pct"),
            "interaction_residual_rel": agg.get("interaction_residual_rel"),
        },
        "waterfall": build_waterfall(agg),
        "drivers": _driver_rows(agg),
        "copulas": _copula_rows(agg),
        "convergence": _convergence(agg),
        "bootstrap_ci": _bootstrap(agg),
    }


def _write_csv(path: str, columns: List[str],
               rows: List[List[Any]]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(columns)
        w.writerows(rows)


def build_run_decomposition(report_path: str,
                            out_dir: Optional[str] = None) -> Dict[str, Any]:
    """Read the run artifact, decompose it, optionally write artifacts.

    Returns the decomposition dict plus ``source_digest`` (sha256 of the
    artifact bytes) and, when ``out_dir`` is given, ``json_path`` /
    ``csv_paths``."""
    if not os.path.exists(report_path):
        raise FileNotFoundError(report_path)
    with open(report_path, encoding="utf-8") as fh:
        report = json.load(fh)
    result = decompose_report(report)
    result["source_artifact"] = os.path.abspath(report_path)
    result["source_digest"] = artifact_digest(report_path)

    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
        paths: Dict[str, str] = {}
        wf = result["waterfall"]
        _write_csv(os.path.join(out_dir, CSV_NAMES[0]),
                   ["order", "id", "kind", "label", "value", "cumulative"],
                   [[i + 1, s["id"], s["kind"], s["label"],
                     s["value"], s["cumulative"]] for i, s in enumerate(wf)])
        _write_csv(os.path.join(out_dir, CSV_NAMES[1]),
                   ["driver", "standalone_scr", "share_of_sum_pct"],
                   [[r["driver"], r["standalone_scr"],
                     r["share_of_sum_pct"]] for r in result["drivers"]])
        _write_csv(os.path.join(out_dir, CSV_NAMES[2]),
                   ["name", "n_params", "loglik", "aic",
                    "upper_tail_dependence", "selected"],
                   [[r["name"], r["n_params"], r["loglik"], r["aic"],
                     r["upper_tail_dependence"], r["selected"]]
                    for r in result["copulas"]])
        conv = result["convergence"]
        grid = conv.get("n_sim_grid") or []
        vpath = conv.get("var_path") or []
        epath = conv.get("es_path") or []
        _write_csv(os.path.join(out_dir, CSV_NAMES[3]),
                   ["n_sim", "var", "es"],
                   [[grid[i],
                     vpath[i] if i < len(vpath) else None,
                     epath[i] if i < len(epath) else None]
                    for i in range(len(grid))])
        for name in CSV_NAMES:
            paths[name] = os.path.abspath(os.path.join(out_dir, name))
        result["csv_paths"] = paths
        json_path = os.path.join(out_dir, JSON_NAME)
        with open(json_path, "w", encoding="utf-8") as fh:
            json.dump(result, fh, indent=1, default=str)
        with open(json_path, encoding="utf-8") as fh:
            json.load(fh)  # re-parse guard
        result["json_path"] = os.path.abspath(json_path)
    return result
