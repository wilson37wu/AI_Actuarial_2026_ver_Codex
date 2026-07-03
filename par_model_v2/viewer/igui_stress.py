"""GUI-2 - Sensitivities & stress runs for the Input & Run GUI.

Roadmap 4.0 item GUI-2 (owner directive 2026-07-03).  Provides:

  * a CATALOGUE of predefined input-level stresses/sensitivities whose fields
    verifiably flow into ``scripts/run_model.py`` (portfolio economics,
    liquidity-exposure balance sheet, capital confidence, run horizon, seed);
  * ``apply_stress``  - deep-copy the gated base inputs, apply ONE stress,
    RE-VALIDATE and RE-GATE the stressed set (the Task-6 gate binds its
    reproducibility digest to the exact input bytes, so a stressed set gets
    its own freshly-cleared gate or the run is refused - the gate is never
    bypassed);
  * ``run_stress``    - execute the stressed set through the SAME governed
    ``execute_run`` pipeline into an isolated ``<out_root>/stress_<id>/``
    directory (the base run's artifacts and the /my-results user copy are
    never clobbered), then diff the stressed headline against the base run's
    ``RUN_MODEL_SUMMARY.json``;
  * ``compare_headlines`` - metric-by-metric base vs stress deltas;
  * ``asset_stress_report`` - the existing deterministic Phase 9 asset-class
    stress suite (rates/credit/private/infra), JSON-shaped for the GUI panel;
  * ``render_stress_html`` - the self-contained stress console page.

Excluded by design: assumption blocks that do NOT flow into the run_model
capital path (e.g. lapse/mortality tables feed the liability stage, not the
seven-driver aggregation) are not offered as stresses here - a zero-delta
toggle would be misleading.  They join in GUI-3+ when calibration/liability
runs are surfaced.

Discipline: STANDARD LIBRARY ONLY at import time for the GUI path (the asset
stress panel imports the engine lazily); no governed headline change; the
committed ui_app.html is untouched.  Stress results are DIAGNOSTIC overlays,
not governed capital figures.
"""
from __future__ import annotations

import copy
import html as _html
import json
import os
from typing import Any, Callable, Dict, List, Optional

from par_model_v2.viewer.igui_run_execution import (
    SUMMARY_NAME,
    execute_run,
    verify_run_gate,
)

STRESS_SCHEMA_VERSION = "gui2-stress-1.0"

#: metric keys diffed between base and stressed RUN_MODEL summaries
_HEADLINE_METRICS = ("nested_scr", "copula_scr", "var_covar_scr")


def _scale_portfolio(field: str, factor: float) -> Callable[[Dict[str, Any]], List[str]]:
    def _apply(mi: Dict[str, Any]) -> List[str]:
        rows = mi.get("portfolio") or []
        if not rows:
            raise ValueError("no portfolio rows to stress")
        for r in rows:
            r[field] = float(r[field]) * factor
        return ["portfolio[*].{} x{:g} ({} rows)".format(field, factor, len(rows))]
    return _apply


def _set_confidence(value: float) -> Callable[[Dict[str, Any]], List[str]]:
    def _apply(mi: Dict[str, Any]) -> List[str]:
        mi.setdefault("assumptions", {})["confidence"] = float(value)
        return ["assumptions.confidence -> {:g}".format(value)]
    return _apply


def _shift_seed(offset: int) -> Callable[[Dict[str, Any]], List[str]]:
    def _apply(mi: Dict[str, Any]) -> List[str]:
        rs = mi.setdefault("run_settings", {})
        old = int(rs.get("seed") or 0)
        rs["seed"] = old + int(offset)
        return ["run_settings.seed {} -> {}".format(old, rs["seed"])]
    return _apply


def _set_horizon(months: int) -> Callable[[Dict[str, Any]], List[str]]:
    def _apply(mi: Dict[str, Any]) -> List[str]:
        rs = mi.setdefault("run_settings", {})
        old = rs.get("horizon_months")
        rs["horizon_months"] = int(months)
        return ["run_settings.horizon_months {} -> {}".format(old, months)]
    return _apply


def _scale_balance_sheet(factor: float) -> Callable[[Dict[str, Any]], List[str]]:
    def _apply(mi: Dict[str, Any]) -> List[str]:
        bs = mi.get("balance_sheet") or {}
        if not bs.get("assets"):
            raise ValueError("no balance-sheet assets to stress")
        for a in bs["assets"]:
            a["market_value"] = float(a["market_value"]) * factor
        for key in ("backing_asset_mv", "illiquid_mv",
                    "stated_total_backing_asset_mv"):
            if bs.get(key) is not None:
                bs[key] = float(bs[key]) * factor
        totals = mi.get("totals") or {}
        if totals.get("backing_asset_mv") is not None:
            totals["backing_asset_mv"] = float(totals["backing_asset_mv"]) * factor
        return ["balance_sheet asset MVs (and derived totals) x{:g}".format(factor)]
    return _apply


#: The predefined GUI-2 catalogue.  ``requires`` names the model_inputs block
#: a stress needs; availability is reported per assembled input set.
STRESS_CATALOGUE: List[Dict[str, Any]] = [
    {"id": "SENS_CONF_99", "category": "sensitivity",
     "label": "Confidence 99.5% -> 99.0%",
     "description": "Capital confidence level lowered one notch; isolates tail-percentile sensitivity.",
     "requires": None, "transform": _set_confidence(0.99)},
    {"id": "SENS_CONF_999", "category": "sensitivity",
     "label": "Confidence 99.5% -> 99.9%",
     "description": "Capital confidence level raised; deeper tail percentile.",
     "requires": None, "transform": _set_confidence(0.999)},
    {"id": "STRESS_SA_UP20", "category": "stress",
     "label": "Sum assured +20%",
     "description": "Every portfolio row's sum assured scaled x1.2; guarantee burden up.",
     "requires": "portfolio", "transform": _scale_portfolio("sum_assured", 1.2)},
    {"id": "STRESS_PREM_DN20", "category": "stress",
     "label": "Annual premium -20%",
     "description": "Every portfolio row's annual premium scaled x0.8; asset build-up down.",
     "requires": "portfolio", "transform": _scale_portfolio("annual_premium", 0.8)},
    {"id": "STRESS_EXPO_UP50", "category": "stress",
     "label": "Backing assets +50% (liquidity exposure)",
     "description": "Balance-sheet asset market values (and derived totals) scaled x1.5; liquidity exposure notional rises.",
     "requires": "balance_sheet", "transform": _scale_balance_sheet(1.5)},
    {"id": "SENS_SEED_SHIFT", "category": "sensitivity",
     "label": "Seed +1000 (Monte-Carlo noise)",
     "description": "Same economics, different random seed; the delta IS the sampling error at the configured scenario budget.",
     "requires": None, "transform": _shift_seed(1000)},
    {"id": "SENS_HORIZON_24", "category": "sensitivity",
     "label": "Capital horizon 12 -> 24 months",
     "description": "Outer capital horizon doubled.",
     "requires": None, "transform": _set_horizon(24)},
]


def catalogue_for(model_inputs: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """JSON-safe catalogue with per-input availability flags."""
    out = []
    for item in STRESS_CATALOGUE:
        needs = item["requires"]
        available, reason = True, None
        if model_inputs is None:
            available, reason = False, "no assembled model_inputs.json yet"
        elif needs and not (model_inputs.get(needs)):
            available, reason = False, "requires {} in the assembled inputs".format(needs)
        out.append({"id": item["id"], "category": item["category"],
                    "label": item["label"], "description": item["description"],
                    "available": available, "unavailable_reason": reason})
    return out


def _find(stress_id: str) -> Dict[str, Any]:
    for item in STRESS_CATALOGUE:
        if item["id"] == stress_id:
            return item
    raise KeyError("unknown stress id: {}".format(stress_id))


def apply_stress(model_inputs: Dict[str, Any], stress_id: str,
                 loader_module=None) -> Dict[str, Any]:
    """Deep-copy + stress + RE-VALIDATE + RE-GATE.  Returns
    ``{"ok", "stressed_inputs", "changes", "gate"}``; refuses (ok=False) when
    the stressed set fails validation - the gate is never bypassed."""
    from par_model_v2.viewer.igui_validation_gating import (
        aggregate_validation, build_run_gate)
    if loader_module is None:
        import load_user_inputs as loader_module  # scripts/ on sys.path (run_gui)
    item = _find(stress_id)
    stressed = copy.deepcopy(model_inputs)
    stressed.pop("run_gate", None)
    changes = item["transform"](stressed)
    validation = aggregate_validation(stressed, loader_module)
    gate = build_run_gate(stressed, validation)
    stressed["run_gate"] = gate
    check = verify_run_gate(stressed)
    if not (gate.get("run_permitted") and check["ok"]):
        return {"ok": False, "stress_id": stress_id, "changes": changes,
                "errors": (gate.get("blocking_issues") or []) + check.get("reasons", []),
                "gate": {k: gate.get(k) for k in ("decision", "run_permitted")}}
    return {"ok": True, "stress_id": stress_id, "changes": changes,
            "stressed_inputs": stressed,
            "gate": {k: gate.get(k) for k in
                     ("decision", "run_permitted", "reproducibility_digest")}}


def compare_headlines(base: Optional[Dict[str, Any]],
                      stress: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Metric-by-metric base vs stress deltas (headline + per-driver standalone)."""
    if not base or not stress:
        return {"ok": False, "error": "base or stress headline missing",
                "rows": []}
    rows = []

    def add(metric, b, s):
        if b is None or s is None:
            return
        b, s = float(b), float(s)
        rows.append({"metric": metric, "base": b, "stress": s,
                     "delta": s - b,
                     "delta_pct": ((s - b) / abs(b) * 100.0) if b else None})

    for key in _HEADLINE_METRICS:
        add(key, base.get(key), stress.get(key))
    b_sa, s_sa = base.get("standalone_scr") or {}, stress.get("standalone_scr") or {}
    for driver in sorted(set(b_sa) | set(s_sa)):
        add("standalone." + driver, b_sa.get(driver), s_sa.get(driver))
    return {"ok": True, "rows": rows}


def read_base_headline(out_root: str) -> Optional[Dict[str, Any]]:
    """The base run's headline from ``<out_root>/RUN_MODEL_SUMMARY.json``."""
    path = os.path.join(out_root, SUMMARY_NAME)
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8") as fh:
            return (json.load(fh) or {}).get("headline")
    except (OSError, json.JSONDecodeError):
        return None


def run_stress(inputs_path: str, stress_id: str, out_root: str, *,
               smoke: bool = True, repo_root: Optional[str] = None,
               loader_module=None) -> Dict[str, Any]:
    """Stress -> re-gate -> run (isolated dir) -> diff vs base.  Never touches
    the base artifacts or the /my-results user copy."""
    if not os.path.exists(inputs_path):
        return {"ok": False, "stage": "inputs_missing",
                "errors": ["model_inputs.json not found: %s" % inputs_path],
                "progress": []}
    with open(inputs_path, encoding="utf-8") as fh:
        base_inputs = json.load(fh)
    applied = apply_stress(base_inputs, stress_id, loader_module=loader_module)
    if not applied["ok"]:
        applied.setdefault("stage", "stress_gate_refused")
        applied.setdefault("progress", ["stressed inputs failed validation/gating"])
        return applied
    stress_dir = os.path.join(out_root, "stress_{}".format(stress_id))
    os.makedirs(stress_dir, exist_ok=True)
    stressed_path = os.path.join(stress_dir, "model_inputs.json")
    with open(stressed_path, "w", encoding="utf-8") as fh:
        json.dump(applied["stressed_inputs"], fh, indent=1)
    with open(stressed_path, encoding="utf-8") as fh:
        json.load(fh)  # re-parse guard
    result = execute_run(stressed_path, stress_dir, smoke=smoke,
                         repo_root=repo_root)
    result["kind"] = "stress"
    result["stress_id"] = stress_id
    result["changes"] = applied["changes"]
    base_headline = read_base_headline(out_root)
    result["comparison"] = compare_headlines(base_headline, result.get("headline"))
    result["base_available"] = base_headline is not None
    if base_headline is None:
        result.setdefault("progress", []).append(
            "NOTE: no base RUN_MODEL_SUMMARY.json in %s - run a base run first "
            "for deltas" % out_root)
    result.setdefault("progress", []).append(
        "stress run isolated in %s (base artifacts untouched)" % stress_dir)
    return result


def asset_stress_report() -> Dict[str, Any]:
    """The existing deterministic Phase 9 asset-class stress suite, JSON-shaped.
    Engine imports are lazy so the GUI server stays importable without numpy."""
    try:
        from par_model_v2.projection.asset_stress import (
            default_phase9_asset_stress_scenarios, run_asset_class_stress_tests)
    except Exception as exc:  # pragma: no cover - engine deps missing
        return {"ok": False, "error": "asset stress engine unavailable: %s" % exc}
    report = run_asset_class_stress_tests()
    frame = report.stress_results
    by_class = (frame.groupby(["scenario_id", "asset_class"], as_index=False)
                     ["market_value_impact"].sum())
    scenarios = []
    for scen in default_phase9_asset_stress_scenarios():
        rows = by_class[by_class["scenario_id"] == scen.scenario_id]
        scenarios.append({
            "name": scen.scenario_id,
            "description": scen.description,
            "governance_note": scen.governance_note,
            "impacts_by_class": [
                {"asset_class": str(r["asset_class"]),
                 "market_value_impact": float(r["market_value_impact"])}
                for _, r in rows.iterrows()],
            "total_impact": float(rows["market_value_impact"].sum()),
        })
    return {"ok": True, "schema": STRESS_SCHEMA_VERSION, "scenarios": scenarios,
            "note": ("Deterministic Phase 9 educational asset stress attribution; "
                     "display-only, not calibrated market-risk capital.")}


def render_stress_html() -> str:
    """Self-contained stress console page (no external references)."""
    return """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Stress &amp; sensitivities - GUI-2</title>
<style>
 body{font:14px/1.5 system-ui,Segoe UI,Arial,sans-serif;margin:0;background:#0f1115;color:#e8eaed}
 main{max-width:920px;margin:0 auto;padding:24px}
 h1{font-size:20px;margin:0 0 4px} h2{font-size:15px;margin:20px 0 8px;color:#9fb4ff}
 .card{background:#171a21;border:1px solid #262b36;border-radius:10px;padding:16px;margin:12px 0}
 .muted{color:#9aa3b2} .mono{font-family:ui-monospace,Consolas,monospace}
 button{font:inherit;padding:7px 14px;border-radius:8px;border:1px solid #2b6cff;background:#2b6cff;color:#fff;cursor:pointer}
 button:disabled{background:#33384a;border-color:#33384a;color:#7b8499;cursor:not-allowed;opacity:.7}
 pre{background:#0b0d12;border:1px solid #20242e;border-radius:8px;padding:12px;white-space:pre-wrap;max-height:260px;overflow:auto}
 .ok{color:#36d399} .bad{color:#f87272}
 table{border-collapse:collapse;width:100%} td,th{border-bottom:1px solid #262b36;padding:6px 8px;text-align:left}
 td.num{text-align:right;font-family:ui-monospace,Consolas,monospace}
 .pos{color:#f87272} .neg{color:#36d399}
 .pill{display:inline-block;padding:2px 8px;border-radius:999px;font-size:12px;border:1px solid #394150}
</style></head><body><main>
 <h1>Stress &amp; sensitivities</h1>
 <div class="muted">GUI-2 - each stress deep-copies your gated inputs, applies ONE predefined change,
  re-validates + re-gates the stressed set, runs the SAME governed engine into an isolated directory,
  and diffs the headline against your base run. Diagnostic overlay - never a governed capital figure.
  <a href="/run-execution" style="color:#9fb4ff">Back to the run page</a></div>

 <div class="card">
  <h2>1 &middot; Base run</h2>
  <div class="muted">Deltas compare against your latest base run (<span class="mono">RUN_MODEL_SUMMARY.json</span>).
   No base run yet? <a href="/run-execution" style="color:#9fb4ff">Run the model first.</a></div>
  <p><span id="base-status" class="pill">base: checking...</span></p>
 </div>

 <div class="card">
  <h2>2 &middot; Predefined stresses &amp; sensitivities</h2>
  <label class="muted" style="display:flex;gap:8px;align-items:center;margin:6px 0">
   <input type="checkbox" id="smoke" checked> Fast smoke run (diagnostic scenario budget)</label>
  <table id="catalogue"><thead><tr><th>Stress</th><th>What changes</th><th></th></tr></thead><tbody></tbody></table>
  <h2>Progress</h2>
  <pre id="progress" class="mono">(idle)</pre>
 </div>

 <div class="card" id="delta-card" style="display:none">
  <h2>3 &middot; Base vs stress</h2>
  <div class="muted" id="delta-title"></div>
  <table id="deltas"><thead><tr><th>Metric</th><th>Base</th><th>Stress</th><th>Delta</th><th>Delta %</th></tr></thead><tbody></tbody></table>
 </div>

 <div class="card">
  <h2>Deterministic asset-class stress suite (Phase 9)</h2>
  <div class="muted">Existing governed educational suite; instant, display-only.</div>
  <table id="asset-stress"><thead><tr><th>Scenario</th><th>Asset class impacts</th><th>Total</th></tr></thead><tbody></tbody></table>
 </div>

<script>
"use strict";
var $=function(id){return document.getElementById(id);};
function post(path,body){return fetch(path,{method:"POST",headers:{"Content-Type":"application/json"},
  body:JSON.stringify(body||{})}).then(function(r){return r.json();});}
function fmt(x){return (x==null)?"--":Number(x).toLocaleString(undefined,{maximumFractionDigits:2});}
function loadCatalogue(){fetch("/stress-catalogue").then(function(r){return r.json();}).then(function(j){
  var st=$("base-status");
  st.textContent="base: "+(j.base_available?"available (deltas on)":"MISSING - run a base run first");
  st.className="pill "+(j.base_available?"ok":"bad");
  var tb=$("catalogue").querySelector("tbody");tb.innerHTML="";
  (j.catalogue||[]).forEach(function(c){
    var tr=document.createElement("tr");
    var btn="<button data-id="+c.id+(c.available?"":" disabled")+">Run</button>";
    tr.innerHTML="<td><b>"+c.label+"</b><br><span class=muted>"+c.id+" &middot; "+c.category+"</span></td>"+
      "<td class=muted>"+c.description+(c.available?"":"<br><span class=bad>"+(c.unavailable_reason||"")+"</span>")+"</td>"+
      "<td>"+btn+"</td>";
    tb.appendChild(tr);});
  tb.querySelectorAll("button[data-id]").forEach(function(b){
    b.addEventListener("click",function(){runStress(b.getAttribute("data-id"));});});
});}
function renderDeltas(j){var r=(j&&j.result)||{};var cmp=r.comparison||{};
  $("delta-card").style.display="block";
  $("delta-title").textContent=(r.stress_id||"")+" - "+((r.changes||[]).join("; "))+
    (r.base_available?"":"  [no base run - stress values only]");
  var tb=$("deltas").querySelector("tbody");tb.innerHTML="";
  (cmp.rows||[]).forEach(function(row){var tr=document.createElement("tr");
    var cls=(row.delta>0)?"pos":((row.delta<0)?"neg":"");
    tr.innerHTML="<td>"+row.metric+"</td><td class=num>"+fmt(row.base)+"</td>"+
      "<td class=num>"+fmt(row.stress)+"</td>"+
      "<td class='num "+cls+"'>"+fmt(row.delta)+"</td>"+
      "<td class='num "+cls+"'>"+(row.delta_pct==null?"--":fmt(row.delta_pct)+"%")+"</td>";
    tb.appendChild(tr);});
  if(!(cmp.rows||[]).length&&r.headline){var tr=document.createElement("tr");
    tr.innerHTML="<td>nested_scr (stress only)</td><td class=num>--</td><td class=num>"+
      fmt(r.headline.nested_scr)+"</td><td class=num>--</td><td class=num>--</td>";
    tb.appendChild(tr);}}
function poll(id){fetch("/jobs/"+id).then(function(r){return r.json();}).then(function(j){
  if(j&&j.progress){$("progress").textContent=j.progress.join("\\n");}
  if(j&&(j.state==="succeeded"||j.state==="failed")){
    if(j.state==="succeeded"){renderDeltas(j);}
    setButtons(false);}
  else{setTimeout(function(){poll(id);},2000);}
}).catch(function(){setTimeout(function(){poll(id);},4000);});}
function setButtons(disabled){document.querySelectorAll("#catalogue button[data-id]").forEach(function(b){
  if(!b.hasAttribute("data-unavailable")){b.disabled=disabled;}});}
function runStress(id){setButtons(true);$("progress").textContent="(submitting "+id+")";
  post("/run-stress",{stress_id:id,smoke:$("smoke").checked}).then(function(j){
    if(j&&j.ok&&j.job_id){poll(j.job_id);}
    else{$("progress").textContent=(j&&j.error)||"submit failed";setButtons(false);}
  }).catch(function(e){$("progress").textContent=String(e);setButtons(false);});}
function loadAssetStress(){fetch("/asset-stress").then(function(r){return r.json();}).then(function(j){
  var tb=$("asset-stress").querySelector("tbody");tb.innerHTML="";
  if(!(j&&j.ok)){tb.innerHTML="<tr><td colspan=3 class=muted>"+((j&&j.error)||"unavailable")+"</td></tr>";return;}
  (j.scenarios||[]).forEach(function(s){var tr=document.createElement("tr");
    var parts=(s.impacts_by_class||[]).map(function(i){return i.asset_class+": "+fmt(i.market_value_impact);});
    var cls=(s.total_impact<0)?"pos":"neg";
    tr.innerHTML="<td><b>"+s.name+"</b><br><span class=muted>"+s.description+"</span></td>"+
      "<td class=muted>"+parts.join("<br>")+"</td>"+
      "<td class='num "+cls+"'>"+fmt(s.total_impact)+"</td>";
    tb.appendChild(tr);});});}
loadCatalogue();loadAssetStress();
</script></main></body></html>"""
