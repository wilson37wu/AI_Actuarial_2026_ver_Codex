"""GUI-3 - Calibration console for the Input & Run GUI.

Roadmap 4.0 item GUI-3 (owner directive 2026-07-03).  Provides:

  * ``CALIBRATION_CATALOGUE``   - the two production calibration pipelines the
    GUI can trigger: HW1F swaption calibration (Phase 13, CNY + HKD) and GBM
    equity calibration (Phase 14, CNY + HKD);
  * ``market_data_status``      - the roadmap-#1 live market-data pipeline
    (CNY sovereign zero curve + CSI 300 index history) resolved through its
    governed provenance tiers (live_fetch / cached_snapshot / file_fixture),
    reporting per-dataset as-of date, row count, SHA-256, lineage approver and
    an explicit UNSIGNED flag - the GUI surfaces provenance, it never hides it;
  * ``run_calibration``         - execute ONE catalogue item end-to-end into an
    isolated ``<out_root>/calibration_<id>/`` directory: fit diagnostics
    (RMSE / SSE-proxy, max error, optimizer convergence, production gates),
    a per-market PARAMETER CARD, data lineage, and the pipeline's own
    markdown report - all persisted next to a JSON diagnostics file;
  * ``render_calibration_html`` - the self-contained calibration console page
    (market-data panel, run buttons, progress via the GUI-1 job endpoints,
    parameter card + diagnostics tables, UNSIGNED banner).

GOVERNANCE - UNSIGNED BY CONSTRUCTION
-------------------------------------
Roadmap #2 requires calibrated parameters to be "flagged UNSIGNED pending
owner approval", and the roadmap-#1 pipeline ships only educational fixture
data until the Model Owner approves a live vendor source.  Therefore every
result produced here carries ``"unsigned": true`` with the reason, and the
run uses a FRESH in-memory ``GovernanceStore`` - the repository governance
store (``.claude-dev/GOVERNANCE_STORE.json``) is NEVER loaded, mutated, or
persisted by a GUI calibration run.  Calibration output is a DIAGNOSTIC
overlay; no governed headline figure and no production ESG parameter is
touched.  Sign-off remains a human action outside this console.

Discipline (matches the Phase IGUI stack): STANDARD LIBRARY ONLY at import
time - the calibration engines (numpy / pandas / scipy) are imported lazily
inside the runner so the GUI server stays importable without them; the
committed ui_app.html is untouched.
"""
from __future__ import annotations

import html as _html
import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

CALIBRATION_SCHEMA_VERSION = "gui3-calibration-1.0"

#: Why every GUI calibration result is UNSIGNED (surfaced verbatim in the GUI).
UNSIGNED_REASON = (
    "Parameters UNSIGNED pending Model Owner approval (roadmap #2); market "
    "data resolved from the governed pipeline's educational fixture/cache "
    "tier - no owner-approved live vendor source is configured (roadmap #1)."
)

CALIBRATION_CATALOGUE: List[Dict[str, Any]] = [
    {
        "id": "CAL_HW1F_SWAPTION",
        "label": "HW1F swaption calibration (CNY + HKD)",
        "engine": "phase13_hw1f_calibration.run_phase13_hw1f_calibration",
        "model": "Hull-White 1F short rate",
        "description": (
            "L-BFGS-B fit of (a, sigma_r) to the ATM swaption normal-vol grid "
            "per market; reports RMSE / max error in bps, optimizer "
            "convergence, and production gates G-02 / G-12."),
    },
    {
        "id": "CAL_GBM_EQUITY",
        "label": "GBM equity calibration (CNY + HKD)",
        "engine": "phase14_gbm_calibration.run_phase14_gbm_calibration",
        "model": "Geometric Brownian motion equity",
        "description": (
            "Historical-window fit of (sigma_S, ERP, dividend yield, rho) per "
            "market from daily index returns; reports observation counts and "
            "the per-market calibration check."),
    },
]


def _engine_available() -> "tuple[bool, Optional[str]]":
    try:  # the three engine deps the calibrators need
        import numpy  # noqa: F401
        import pandas  # noqa: F401
        import scipy  # noqa: F401
        return True, None
    except Exception as exc:  # pragma: no cover - dep-less environments
        return False, "calibration engine unavailable: {}".format(exc)


def calibration_catalogue() -> List[Dict[str, Any]]:
    """JSON-safe catalogue with an availability flag per item."""
    ok, reason = _engine_available()
    out = []
    for item in CALIBRATION_CATALOGUE:
        out.append({
            "id": item["id"], "label": item["label"], "model": item["model"],
            "description": item["description"], "available": ok,
            "unavailable_reason": None if ok else reason,
            "unsigned": True,
        })
    return out


def _find(cal_id: str) -> Dict[str, Any]:
    for item in CALIBRATION_CATALOGUE:
        if item["id"] == cal_id:
            return item
    raise KeyError("unknown calibration id: {}".format(cal_id))


# ---------------------------------------------------------------------------
# Market-data pipeline status (roadmap #1 surface)
# ---------------------------------------------------------------------------

def market_data_status(cache_dir: Optional[str] = None) -> Dict[str, Any]:
    """Resolve both roadmap-#1 datasets through the governed pipeline and
    report provenance evidence.  Engine imports are lazy; failures degrade to
    a per-dataset error entry, never an exception to the HTTP layer."""
    ok, reason = _engine_available()
    if not ok:
        return {"ok": False, "error": reason, "datasets": []}
    import tempfile

    from par_model_v2.calibration.live_market_data_pipeline import (
        PROVENANCE_LIVE, CNYYieldCurveLoader, CSI300IndexLoader, SnapshotCache)
    cache = SnapshotCache(cache_dir or os.path.join(
        tempfile.gettempdir(), "igui_market_data_cache"))
    datasets = []
    for loader_cls in (CNYYieldCurveLoader, CSI300IndexLoader):
        loader = loader_cls(cache)  # no fetcher configured -> cache/fixture
        try:
            res = loader.load()
            lin = res.lineage
            datasets.append({
                "dataset": res.dataset,
                "ok": True,
                "as_of_date": res.as_of_date,
                "provenance": res.provenance,
                "rows": int(len(res.frame)),
                "sha256": res.sha256,
                "approved_by": lin.approved_by,
                "unsigned": (res.provenance == PROVENANCE_LIVE
                             or "UNSIGNED" in str(lin.approved_by).upper()
                             or res.provenance == "file_fixture"),
                "source_detail": lin.source_detail,
            })
        except Exception as exc:
            datasets.append({"dataset": loader_cls.dataset, "ok": False,
                             "error": str(exc)})
    return {"ok": all(d.get("ok") for d in datasets),
            "schema": CALIBRATION_SCHEMA_VERSION,
            "live_source_configured": False,
            "note": ("No owner-approved live vendor adapter is configured; "
                     "data resolves to the sealed snapshot/fixture tier and "
                     "any future live fetch is UNSIGNED pending owner "
                     "approval."),
            "datasets": datasets}


# ---------------------------------------------------------------------------
# Calibration runners (one isolated directory per run; UNSIGNED always)
# ---------------------------------------------------------------------------

def _fit_row(market: str, params: Dict[str, Any],
             diagnostics: Dict[str, Any]) -> Dict[str, Any]:
    return {"market": market, "parameters": params, "diagnostics": diagnostics}


def _run_hw1f() -> Dict[str, Any]:
    from par_model_v2.calibration.phase13_hw1f_calibration import (
        run_phase13_hw1f_calibration)
    from par_model_v2.governance.audit_trail import GovernanceStore
    report = run_phase13_hw1f_calibration(governance_store=GovernanceStore())
    rows = []
    for s in (report.cny, report.hkd):
        rmse = s.swaption_rmse_bps
        rows.append(_fit_row(s.market, {
            "a": s.a, "sigma_r": s.sigma_r, "r0": s.r0,
            "calibration_date": s.calibration_date,
        }, {
            "rmse_bps": rmse,
            "sse_proxy_bps2": (None if rmse is None else float(rmse) ** 2),
            "max_abs_error_bps": s.max_swaption_error_bps,
            "converged": bool(s.converged),
            "is_placeholder": bool(s.is_placeholder),
            "notes": s.notes,
            "lineage": s.lineage.to_dict(),
        }))
    gates = {"G-02": report.gate_g02.to_dict(), "G-12": report.gate_g12.to_dict()}
    return {"markets": rows, "gates": gates,
            "gates_all_pass": bool(report.gates_all_pass()),
            "markdown_report": report.markdown_report,
            "run_timestamp": report.run_timestamp}


def _run_gbm() -> Dict[str, Any]:
    from par_model_v2.calibration.phase14_gbm_calibration import (
        run_phase14_gbm_calibration)
    from par_model_v2.governance.audit_trail import GovernanceStore
    # Fresh in-memory store + persist_governance=False: the repository
    # governance store is never read or written by a GUI calibration run.
    report = run_phase14_gbm_calibration(governance_store=GovernanceStore(),
                                         persist_governance=False,
                                         write_report=False)
    rows = []
    for s in report.summaries:
        d = s.to_dict()
        rows.append(_fit_row(s.market, {
            "sigma_S": s.sigma_S, "erp": s.erp,
            "dividend_yield": s.dividend_yield, "rho": s.rho,
            "calibration_date": s.calibration_date,
        }, {
            "equity_vol_hist": s.equity_vol_hist,
            "equity_vol_implied": s.equity_vol_implied,
            "n_daily_obs": int(s.n_daily_obs),
            "is_placeholder": bool(s.is_placeholder),
            "notes": s.notes,
            "check": d.get("check"),
            "lineage": d.get("lineage"),
        }))
    return {"markets": rows,
            "gates": {"G-03": report.gate_g03.to_dict(),
                      "mr002_status": report.mr002_status,
                      "change_record_status": report.change_record_status},
            "gates_all_pass": bool(report.gate_passes()),
            "markdown_report": report.markdown or "",
            "run_timestamp": report.run_timestamp}


_RUNNERS = {"CAL_HW1F_SWAPTION": _run_hw1f, "CAL_GBM_EQUITY": _run_gbm}


def run_calibration(cal_id: str, out_root: str, *,
                    cache_dir: Optional[str] = None) -> Dict[str, Any]:
    """Execute ONE catalogue calibration into ``<out_root>/calibration_<id>/``.

    Returns the JSON-safe diagnostics dict (also persisted to disk).  Always
    UNSIGNED; never touches the repo governance store or run_output base
    artifacts."""
    item = _find(cal_id)  # KeyError on unknown id (HTTP layer maps to error)
    ok, reason = _engine_available()
    progress = ["calibration {} submitted".format(cal_id)]
    if not ok:
        return {"ok": False, "kind": "calibration", "calibration_id": cal_id,
                "errors": [reason], "progress": progress}
    cal_dir = os.path.join(out_root, "calibration_{}".format(cal_id))
    os.makedirs(cal_dir, exist_ok=True)
    progress.append("isolated output directory: {}".format(cal_dir))
    md_status = market_data_status(cache_dir=cache_dir)
    progress.append("market-data pipeline resolved ({} datasets, live_source_configured={})".format(
        len(md_status.get("datasets", [])), md_status.get("live_source_configured")))
    try:
        core = _RUNNERS[cal_id]()
    except Exception as exc:
        return {"ok": False, "kind": "calibration", "calibration_id": cal_id,
                "errors": ["calibration failed: {}".format(exc)],
                "progress": progress + ["FAILED"]}
    progress.append("fit complete: {} market(s), gates_all_pass={}".format(
        len(core["markets"]), core["gates_all_pass"]))
    result = {
        "ok": True,
        "kind": "calibration",
        "schema": CALIBRATION_SCHEMA_VERSION,
        "calibration_id": cal_id,
        "label": item["label"],
        "model": item["model"],
        "unsigned": True,
        "unsigned_reason": UNSIGNED_REASON,
        "governance": {
            "repo_store_touched": False,
            "note": ("Diagnostic run against a fresh in-memory governance "
                     "store; adopting these parameters requires the Model "
                     "Owner's signed ChangeRecord outside this console."),
        },
        "market_data": md_status,
        "markets": core["markets"],
        "gates": core["gates"],
        "gates_all_pass": core["gates_all_pass"],
        "run_timestamp": core.get("run_timestamp") or datetime.now(
            timezone.utc).isoformat(),
        "output_dir": cal_dir,
        "progress": progress,
    }
    diag_path = os.path.join(cal_dir, "CALIBRATION_DIAGNOSTICS.json")
    with open(diag_path, "w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=1, default=str)
    with open(diag_path, encoding="utf-8") as fh:
        json.load(fh)  # re-parse guard (in-place-corruption precedent)
    md = core.get("markdown_report") or ""
    if md:
        with open(os.path.join(cal_dir, "CALIBRATION_REPORT.md"), "w",
                  encoding="utf-8") as fh:
            fh.write(md)
    result["diagnostics_path"] = diag_path
    result["progress"].append("diagnostics persisted: {}".format(diag_path))
    return result


# ---------------------------------------------------------------------------
# Console page
# ---------------------------------------------------------------------------

def render_calibration_html() -> str:
    """Self-contained calibration console page (no external references)."""
    unsigned = _html.escape(UNSIGNED_REASON)
    return """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Calibration console - GUI-3</title>
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
 .pill{display:inline-block;padding:2px 8px;border-radius:999px;font-size:12px;border:1px solid #394150}
 .unsigned{background:#3a2b12;border:1px solid #8a6d1a;color:#ffd166;border-radius:10px;padding:12px 16px;margin:12px 0;font-weight:600}
</style></head><body><main>
 <h1>Calibration console</h1>
 <div class="muted">GUI-3 - trigger the governed HW1F / GBM calibration pipelines against the
  roadmap-#1 market-data pipeline and inspect fit diagnostics. Diagnostic overlay - production
  ESG parameters and governed headline figures are NEVER changed from this page.
  <a href="/run-execution" style="color:#9fb4ff">Back to the run page</a></div>

 <div class="unsigned">UNSIGNED &mdash; """ + unsigned + """</div>

 <div class="card">
  <h2>1 &middot; Market-data pipeline (roadmap #1)</h2>
  <div class="muted">CNY sovereign zero curve + CSI 300 daily history, resolved through the
   governed provenance tiers with SHA-256-sealed snapshots.</div>
  <table id="md"><thead><tr><th>Dataset</th><th>As-of</th><th>Tier</th><th>Rows</th><th>SHA-256</th><th>Signed?</th></tr></thead><tbody></tbody></table>
 </div>

 <div class="card">
  <h2>2 &middot; Calibration pipelines</h2>
  <table id="catalogue"><thead><tr><th>Calibration</th><th>What it fits</th><th></th></tr></thead><tbody></tbody></table>
  <h2>Progress</h2>
  <pre id="progress" class="mono">(idle)</pre>
 </div>

 <div class="card" id="result-card" style="display:none">
  <h2>3 &middot; Parameter card &amp; fit diagnostics <span id="res-unsigned" class="pill bad">UNSIGNED</span></h2>
  <div class="muted" id="res-title"></div>
  <table id="params"><thead><tr><th>Market</th><th>Parameters</th><th>Fit diagnostics</th></tr></thead><tbody></tbody></table>
  <h2>Production gates</h2>
  <pre id="gates" class="mono"></pre>
 </div>

<script>
"use strict";
var $=function(id){return document.getElementById(id);};
function post(path,body){return fetch(path,{method:"POST",headers:{"Content-Type":"application/json"},
  body:JSON.stringify(body||{})}).then(function(r){return r.json();});}
function fmt(x){if(x==null)return "--";var n=Number(x);
  return Math.abs(n)<0.01&&n!==0?n.toExponential(3):n.toLocaleString(undefined,{maximumFractionDigits:6});}
function loadMarketData(){fetch("/market-data-status").then(function(r){return r.json();}).then(function(j){
  var tb=$("md").querySelector("tbody");tb.innerHTML="";
  (j.datasets||[]).forEach(function(d){var tr=document.createElement("tr");
    if(!d.ok){tr.innerHTML="<td>"+d.dataset+"</td><td colspan=5 class=bad>"+(d.error||"error")+"</td>";}
    else{tr.innerHTML="<td class=mono>"+d.dataset+"</td><td>"+d.as_of_date+"</td>"+
      "<td>"+d.provenance+"</td><td class=num>"+d.rows+"</td>"+
      "<td class=mono>"+String(d.sha256).slice(0,12)+"&hellip;</td>"+
      "<td class="+(d.unsigned?"bad":"ok")+">"+(d.unsigned?"UNSIGNED":"signed")+"</td>";}
    tb.appendChild(tr);});
}).catch(function(e){$("md").querySelector("tbody").innerHTML=
  "<tr><td colspan=6 class=bad>"+String(e)+"</td></tr>";});}
function loadCatalogue(){fetch("/calibration-catalogue").then(function(r){return r.json();}).then(function(j){
  var tb=$("catalogue").querySelector("tbody");tb.innerHTML="";
  (j.catalogue||[]).forEach(function(c){var tr=document.createElement("tr");
    var btn="<button data-id="+c.id+(c.available?"":" disabled")+">Calibrate</button>";
    tr.innerHTML="<td><b>"+c.label+"</b><br><span class=muted>"+c.id+" &middot; "+c.model+"</span></td>"+
      "<td class=muted>"+c.description+(c.available?"":"<br><span class=bad>"+(c.unavailable_reason||"")+"</span>")+"</td>"+
      "<td>"+btn+"</td>";
    tb.appendChild(tr);});
  tb.querySelectorAll("button[data-id]").forEach(function(b){
    b.addEventListener("click",function(){runCal(b.getAttribute("data-id"));});});
});}
function kv(o){return Object.keys(o||{}).filter(function(k){return typeof o[k]!=="object"||o[k]==null;})
  .map(function(k){return k+" = <b>"+fmt(o[k])+"</b>";}).join("<br>");}
function renderResult(j){var r=(j&&j.result)||{};
  $("result-card").style.display="block";
  $("res-title").textContent=(r.label||"")+"  -  "+(r.run_timestamp||"")+
    "  -  gates "+(r.gates_all_pass?"PASS":"REVIEW");
  var tb=$("params").querySelector("tbody");tb.innerHTML="";
  (r.markets||[]).forEach(function(m){var tr=document.createElement("tr");
    var diag=m.diagnostics||{};
    var dparts=[];
    ["rmse_bps","sse_proxy_bps2","max_abs_error_bps","equity_vol_hist","equity_vol_implied","n_daily_obs"]
      .forEach(function(k){if(diag[k]!=null){dparts.push(k+" = <b>"+fmt(diag[k])+"</b>");}});
    dparts.push("converged = <b class="+(diag.converged===false?"bad":"ok")+">"+
      (diag.converged==null?"n/a":diag.converged)+"</b>");
    if(diag.is_placeholder){dparts.push("<span class=bad>PLACEHOLDER RESULT</span>");}
    tr.innerHTML="<td><b>"+m.market+"</b></td><td class=mono>"+kv(m.parameters)+"</td>"+
      "<td class=mono>"+dparts.join("<br>")+"</td>";
    tb.appendChild(tr);});
  $("gates").textContent=JSON.stringify(r.gates||{},null,1);}
function poll(id){fetch("/jobs/"+id).then(function(r){return r.json();}).then(function(j){
  if(j&&j.progress){$("progress").textContent=j.progress.join("\\n");}
  if(j&&(j.state==="succeeded"||j.state==="failed")){
    if(j.state==="succeeded"){renderResult(j);}
    else{$("progress").textContent+="\\nFAILED: "+((j.result&&(j.result.errors||[]).join("; "))||j.error||"");}
    setButtons(false);}
  else{setTimeout(function(){poll(id);},2000);}
}).catch(function(){setTimeout(function(){poll(id);},4000);});}
function setButtons(disabled){document.querySelectorAll("#catalogue button[data-id]").forEach(function(b){
  b.disabled=disabled;});}
function runCal(id){setButtons(true);$("progress").textContent="(submitting "+id+")";
  post("/run-calibration",{calibration_id:id}).then(function(j){
    if(j&&j.ok&&j.job_id){poll(j.job_id);}
    else{$("progress").textContent=(j&&(j.error||(j.errors||[]).join("; ")))||"submit failed";setButtons(false);}
  }).catch(function(e){$("progress").textContent=String(e);setButtons(false);});}
loadMarketData();loadCatalogue();
</script></main></body></html>"""
