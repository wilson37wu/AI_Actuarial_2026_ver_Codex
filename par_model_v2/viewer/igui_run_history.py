"""GUI-4 - Run history & compare for the Input & Run GUI.

Roadmap 4.0 item GUI-4 (owner directive 2026-07-03) - the last phase of the
owner-directed run-console track.  Provides:

  * ``load_registry``      - the PERSISTED RUN REGISTRY, built from the GUI-1
    ``JobManager`` job records (``<jobs_dir>/job_<id>.json``): run id,
    timestamps, kind (run / stress / calibration), state, smoke flag, the
    Task-6 INPUTS reproducibility digest, the SEED + run plan, and the
    HEADLINE outputs (nested / copula / var-covar SCR + per-driver
    standalone) - the reproducibility tuple the roadmap item names;
  * durable enrichment     - the shared ``run_output/`` artifacts are
    overwritten by later runs, so on first sight of a finished job the
    registry extracts the run plan (seed, n_outer, n_inner, n_sim, horizon)
    from the run's aggregation report WHILE IT STILL EXISTS and persists it
    back into the job record (additive ``registry`` block, atomic rewrite,
    re-parse guard) - after that the registry entry no longer depends on the
    artifacts;
  * ``get_run``            - open one past run (full persisted record);
  * ``compare_runs``       - side-by-side diff of TWO runs: metadata
    (kind, state, smoke, seed, digest, timestamps) plus metric-by-metric
    headline deltas (same delta shape as the GUI-2 stress console);
  * ``render_history_html``- the self-contained run-history console page
    (registry table, per-run detail, pick-two compare).

Read-only by design: the registry only ever ANNOTATES job records (additive
key, best-effort); it never deletes or rewrites engine artifacts, never
touches the governance store, and never changes a governed headline figure.
STANDARD LIBRARY ONLY (the whole GUI server path stays importable without
numpy/pandas/scipy).
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

from par_model_v2.viewer.igui_stress import compare_headlines

REGISTRY_SCHEMA_VERSION = "gui4-history-1.0"

#: run-plan keys copied from the aggregation report (reproducibility tuple)
_PLAN_KEYS = ("seed", "n_outer", "n_inner", "n_sim", "horizon_months",
              "bootstrap_replicates", "output_label")

#: metadata rows shown side-by-side in a compare (order preserved)
_META_KEYS = ("kind", "state", "smoke", "seed", "reproducibility_digest",
              "submitted_at", "finished_at", "elapsed_seconds")


def _read_json(path: str) -> Optional[Dict[str, Any]]:
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError, ValueError):
        return None


def _extract_plan(report_path: Optional[str]) -> Optional[Dict[str, Any]]:
    """The run plan (seed & scenario budget) from an aggregation report, if
    the artifact still exists (later runs overwrite the shared run_output)."""
    if not report_path or not os.path.exists(report_path):
        return None
    rep = _read_json(report_path)
    if not isinstance(rep, dict):
        return None
    plan = rep.get("run_plan")
    if not isinstance(plan, dict):
        return None
    return {k: plan.get(k) for k in _PLAN_KEYS}


def _persist_registry_block(job_path: str, record: Dict[str, Any],
                            block: Dict[str, Any]) -> None:
    """Best-effort durable annotation: write the extracted registry block back
    into the job record (additive key, atomic replace, re-parse guard)."""
    try:
        record["registry"] = block
        tmp = job_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(record, fh, indent=1, default=str)
        with open(tmp, encoding="utf-8") as fh:
            json.load(fh)  # never ship corrupt JSON (in-place precedent)
        os.replace(tmp, job_path)
    except OSError:
        pass  # annotation is best-effort; the in-memory entry still serves


def _entry_from_record(record: Dict[str, Any],
                       job_path: Optional[str] = None) -> Dict[str, Any]:
    """Shape one persisted job record into a JSON-safe registry entry,
    extracting + durably persisting the run plan when possible."""
    result = record.get("result") or {}
    meta = record.get("meta") or {}
    kind = meta.get("kind") or "run"
    registry = record.get("registry") if isinstance(
        record.get("registry"), dict) else None
    if registry is None:
        plan = _extract_plan(result.get("report_path"))
        registry = {"schema": REGISTRY_SCHEMA_VERSION, "run_plan": plan}
        if job_path and record.get("state") in ("succeeded", "failed"):
            _persist_registry_block(job_path, record, registry)
    plan = registry.get("run_plan") or {}
    out_dir = result.get("out_dir") or result.get("output_dir")
    att = result.get("path_detail") if isinstance(
        result.get("path_detail"), dict) else None
    return {
        "run_id": record.get("job_id"),
        "kind": kind,
        "label": (meta.get("stress_id") or meta.get("calibration_id")
                  or plan.get("output_label") or kind),
        "state": record.get("state"),
        "smoke": record.get("smoke"),
        "submitted_at": record.get("submitted_at"),
        "finished_at": record.get("finished_at"),
        "elapsed_seconds": record.get("elapsed_seconds"),
        "reproducibility_digest": result.get("reproducibility_digest"),
        "seed": plan.get("seed"),
        "run_plan": {k: plan.get(k) for k in _PLAN_KEYS} if plan else None,
        "plan_available": bool(plan),
        "headline": result.get("headline"),
        "unsigned": bool(result.get("unsigned")),
        "output_dir": out_dir,
        "path_detail": {
            "available": bool(att and att.get("ok") and att.get("dir")),
            "inputs_digest": (att or {}).get("inputs_digest"),
            "dir": (att or {}).get("dir"),
        },
        "error": record.get("error"),
    }


def load_registry(jobs_dir: str) -> Dict[str, Any]:
    """Scan the persisted job records into the run registry (newest first).
    Corrupt / unreadable records are reported, never fatal."""
    runs: List[Dict[str, Any]] = []
    skipped: List[str] = []
    if os.path.isdir(jobs_dir):
        for name in sorted(os.listdir(jobs_dir), reverse=True):
            if not (name.startswith("job_") and name.endswith(".json")):
                continue
            path = os.path.join(jobs_dir, name)
            record = _read_json(path)
            if not isinstance(record, dict) or not record.get("job_id"):
                skipped.append(name)
                continue
            runs.append(_entry_from_record(record, job_path=path))
    runs.sort(key=lambda r: r.get("submitted_at") or "", reverse=True)
    return {"ok": True, "schema": REGISTRY_SCHEMA_VERSION,
            "jobs_dir": os.path.abspath(jobs_dir) if jobs_dir else None,
            "count": len(runs), "skipped": skipped, "runs": runs}


def get_run(jobs_dir: str, run_id: str) -> Dict[str, Any]:
    """Open one past run: registry entry + the full persisted record."""
    safe = os.path.basename(str(run_id))  # no path traversal via run_id
    path = os.path.join(jobs_dir, "job_{}.json".format(safe))
    record = _read_json(path)
    if not isinstance(record, dict) or not record.get("job_id"):
        return {"ok": False, "error": "unknown run_id: {}".format(safe)}
    return {"ok": True, "entry": _entry_from_record(record, job_path=path),
            "record": record}


def compare_runs(jobs_dir: str, run_id_a: str, run_id_b: str) -> Dict[str, Any]:
    """Side-by-side diff of two past runs: metadata rows + headline deltas.
    Base/left = A, comparison/right = B (delta = B - A, GUI-2 shape)."""
    a = get_run(jobs_dir, run_id_a)
    if not a["ok"]:
        return {"ok": False, "error": a["error"]}
    b = get_run(jobs_dir, run_id_b)
    if not b["ok"]:
        return {"ok": False, "error": b["error"]}
    ea, eb = a["entry"], b["entry"]
    meta_rows = [{"field": k, "a": ea.get(k), "b": eb.get(k),
                  "same": ea.get(k) == eb.get(k)} for k in _META_KEYS]
    comparison = compare_headlines(ea.get("headline"), eb.get("headline"))
    notes = []
    if ea.get("kind") != eb.get("kind"):
        notes.append("different run kinds ({} vs {}) - deltas may not be "
                     "meaningful".format(ea.get("kind"), eb.get("kind")))
    if ea.get("smoke") or eb.get("smoke"):
        notes.append("at least one side is a SMOKE run (diagnostic scenario "
                     "budget) - not a governed capital figure")
    if ea.get("reproducibility_digest") and (
            ea.get("reproducibility_digest") == eb.get("reproducibility_digest")):
        notes.append("identical inputs digest - differences are sampling-only "
                     "(seed / scenario budget)")
    pa = ea.get("path_detail") or {}
    pb = eb.get("path_detail") or {}
    if pa.get("available") and pb.get("available"):
        if pa.get("inputs_digest") == pb.get("inputs_digest"):
            notes.append("both runs carry the SAME persisted scenario-path "
                         "set (identical path digest)")
        else:
            notes.append("persisted scenario-path sets DIFFER - open each "
                         "run's Paths view from the registry table")
    elif bool(pa.get("available")) != bool(pb.get("available")):
        notes.append("only one side carries a persisted scenario-path set "
                     "(runs executed before GD-4 have none)")
    return {"ok": True, "schema": REGISTRY_SCHEMA_VERSION,
            "a": ea, "b": eb, "meta_rows": meta_rows,
            "comparison": comparison, "notes": notes}


# --------------------------------------------------------------------------
# Console page
# --------------------------------------------------------------------------

def render_history_html() -> str:
    """Self-contained run-history console page (no external references)."""
    return """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Run history &amp; compare - GUI-4</title>
<style>
 body{font:14px/1.5 system-ui,Segoe UI,Arial,sans-serif;margin:0;background:#0f1115;color:#e8eaed}
 main{max-width:980px;margin:0 auto;padding:24px}
 h1{font-size:20px;margin:0 0 4px} h2{font-size:15px;margin:20px 0 8px;color:#9fb4ff}
 .card{background:#171a21;border:1px solid #262b36;border-radius:10px;padding:16px;margin:12px 0}
 .muted{color:#9aa3b2} .mono{font-family:ui-monospace,Consolas,monospace}
 button{font:inherit;padding:5px 12px;border-radius:8px;border:1px solid #2b6cff;background:#2b6cff;color:#fff;cursor:pointer}
 button:disabled{background:#33384a;border-color:#33384a;color:#7b8499;cursor:not-allowed;opacity:.7}
 pre{background:#0b0d12;border:1px solid #20242e;border-radius:8px;padding:12px;white-space:pre-wrap;max-height:300px;overflow:auto}
 .ok{color:#36d399} .bad{color:#f87272}
 table{border-collapse:collapse;width:100%} td,th{border-bottom:1px solid #262b36;padding:6px 8px;text-align:left;vertical-align:top}
 td.num{text-align:right;font-family:ui-monospace,Consolas,monospace}
 .pos{color:#f87272} .neg{color:#36d399}
 .pill{display:inline-block;padding:1px 8px;border-radius:999px;font-size:12px;border:1px solid #394150}
 .diff{background:#2a1d1d}
</style></head><body><main>
 <h1>Run history &amp; compare</h1>
 <div class="muted">GUI-4 - every GUI-triggered run (model / stress / calibration) is registered with its
  inputs digest, seed and headline so past results stay reproducible and comparable.
  <a href="/run-execution" style="color:#9fb4ff">Back to the run page</a></div>

 <div class="card">
  <h2>1 &middot; Registered runs <span id="count" class="pill">loading&hellip;</span></h2>
  <table id="runs"><thead><tr><th>A/B</th><th>Run</th><th>Kind</th><th>State</th>
   <th>Seed</th><th>Inputs digest</th><th>Headline SCR</th><th></th></tr></thead><tbody></tbody></table>
  <div style="margin-top:10px"><button id="btn-compare" disabled>Compare A vs B</button>
   <span class="muted" id="pick-hint">pick exactly two runs</span></div>
 </div>

 <div class="card" id="detail-card" style="display:none">
  <h2>2 &middot; Run detail <span id="detail-id" class="mono"></span></h2>
  <pre id="detail" class="mono"></pre>
 </div>

 <div class="card" id="compare-card" style="display:none">
  <h2>3 &middot; Side-by-side compare</h2>
  <div class="muted" id="cmp-notes"></div>
  <h2>Metadata</h2>
  <table id="cmp-meta"><thead><tr><th>Field</th><th>A</th><th>B</th></tr></thead><tbody></tbody></table>
  <h2>Headline deltas (B &minus; A)</h2>
  <table id="cmp-rows"><thead><tr><th>Metric</th><th>A</th><th>B</th><th>Delta</th><th>Delta %</th></tr></thead><tbody></tbody></table>
 </div>

<script>
"use strict";
var $=function(id){return document.getElementById(id);};
var picked=[];
function fmt(x){return (x==null)?"--":Number(x).toLocaleString(undefined,{maximumFractionDigits:2});}
function esc(s){var d=document.createElement("span");d.textContent=(s==null?"--":String(s));return d.innerHTML;}
function headlineOf(r){return (r.headline&&r.headline.nested_scr!=null)?fmt(r.headline.nested_scr):"--";}
function loadRuns(){fetch("/runs").then(function(r){return r.json();}).then(function(j){
  $("count").textContent=(j.count||0)+" run(s)";
  var tb=$("runs").querySelector("tbody");tb.innerHTML="";
  (j.runs||[]).forEach(function(r){var tr=document.createElement("tr");
    tr.innerHTML="<td><input type=checkbox data-id='"+esc(r.run_id)+"'></td>"+
      "<td class=mono>"+esc(r.run_id)+"<br><span class=muted>"+esc(r.submitted_at)+"</span></td>"+
      "<td>"+esc(r.kind)+"<br><span class=muted>"+esc(r.label)+"</span>"+
        (r.smoke?"<br><span class=pill>smoke</span>":"")+
        (r.unsigned?"<br><span class='pill bad'>UNSIGNED</span>":"")+"</td>"+
      "<td class="+(r.state==="succeeded"?"ok":"bad")+">"+esc(r.state)+"</td>"+
      "<td class=num>"+esc(r.seed==null?"--":r.seed)+"</td>"+
      "<td class=mono>"+esc((r.reproducibility_digest||"--").slice(0,18))+"</td>"+
      "<td class=num>"+headlineOf(r)+"</td>"+
      "<td><button data-open='"+esc(r.run_id)+"'>Open</button>"+
        ((r.path_detail&&r.path_detail.available)?" <button data-paths='"+esc(r.run_id)+"'>Paths</button>":"")+"</td>";
    tb.appendChild(tr);});
  tb.querySelectorAll("button[data-open]").forEach(function(b){
    b.addEventListener("click",function(){openRun(b.getAttribute("data-open"));});});
  tb.querySelectorAll("button[data-paths]").forEach(function(b){
    b.addEventListener("click",function(){
      location.href="/paths?run="+encodeURIComponent(b.getAttribute("data-paths"));});});
  tb.querySelectorAll("input[type=checkbox]").forEach(function(c){
    c.addEventListener("change",function(){
      var id=c.getAttribute("data-id");
      if(c.checked){picked.push(id);}else{picked=picked.filter(function(x){return x!==id;});}
      $("btn-compare").disabled=(picked.length!==2);
      $("pick-hint").textContent=picked.length+" picked (need 2)";});});
});}
function openRun(id){fetch("/runs/"+encodeURIComponent(id)).then(function(r){return r.json();}).then(function(j){
  $("detail-card").style.display="block";
  $("detail-id").textContent=id;
  $("detail").textContent=JSON.stringify(j.ok?j.entry:j,null,1);});}
function compare(){var a=picked[0],b=picked[1];
  fetch("/compare-runs?a="+encodeURIComponent(a)+"&b="+encodeURIComponent(b))
  .then(function(r){return r.json();}).then(function(j){
    if(!j.ok){alert(j.error||"compare failed");return;}
    $("compare-card").style.display="block";
    $("cmp-notes").textContent=(j.notes||[]).join("  |  ");
    var tb=$("cmp-meta").querySelector("tbody");tb.innerHTML="";
    (j.meta_rows||[]).forEach(function(m){var tr=document.createElement("tr");
      if(!m.same){tr.className="diff";}
      tr.innerHTML="<td>"+esc(m.field)+"</td><td class=mono>"+esc(m.a)+"</td><td class=mono>"+esc(m.b)+"</td>";
      tb.appendChild(tr);});
    tb=$("cmp-rows").querySelector("tbody");tb.innerHTML="";
    var rows=(j.comparison&&j.comparison.rows)||[];
    if(!rows.length){tb.innerHTML="<tr><td colspan=5 class=muted>"+
      esc((j.comparison&&j.comparison.error)||"no comparable headline metrics")+"</td></tr>";}
    rows.forEach(function(row){var tr=document.createElement("tr");
      var cls=(row.delta>0)?"pos":((row.delta<0)?"neg":"");
      tr.innerHTML="<td>"+esc(row.metric)+"</td><td class=num>"+fmt(row.base)+"</td>"+
        "<td class=num>"+fmt(row.stress)+"</td>"+
        "<td class='num "+cls+"'>"+fmt(row.delta)+"</td>"+
        "<td class='num "+cls+"'>"+(row.delta_pct==null?"--":fmt(row.delta_pct)+"%")+"</td>";
      tb.appendChild(tr);});});}
$("btn-compare").addEventListener("click",compare);
loadRuns();
</script></main></body></html>"""
