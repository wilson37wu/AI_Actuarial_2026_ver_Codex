"""ES-2 - User economic-scenario file UPLOAD page (owner directive 2026-07-08).

The /scenarios console page lets the user upload the ES-1 file pair
(``economic_scenarios.csv`` + ``economic_scenarios_manifest.json``,
spec ``docs/ECONOMIC_SCENARIO_FILE_FORMAT.md``, schema
``esg-user-scenarios-1.0``) entirely from the GUI - zero .py editing:

* **Validate** - the posted texts are routed through the REAL ES-1 loader
  (``par_model_v2.stochastic.user_scenarios.load_user_scenario_set``);
  every violation is surfaced with the offending ROW and COLUMN exactly as
  the loader reports it (capped list, exact total count preserved).
* **Preview** - on a clean pair the page renders the spec par.4.6 summary
  card plus percentile FAN CHARTS (p5/p25/p50/p75/p95 by projection year)
  for every rate tenor, the equity annual return and the cumulative equity
  index - self-drawn inline SVG, zero external references.
* **Persist** - the byte-exact uploaded files are stored under
  ``<run_output>/user_scenarios/<digest12>/`` keyed by the file sha256
  (identical uploads share one copy; a later upload never overwrites a
  different set), and a ``user_scenarios`` provenance block (digest, basis,
  scenario count, source, UNSIGNED state) is merged into
  ``model_inputs.json``.
* **Gate integration** - saving a scenario set POPS any previously recorded
  ``run_gate`` (inputs changed -> the Task-6 gate must be re-cleared), and
  the persisted block is thereby bound into the run-gate reproducibility
  digest.  ``/scenario-status`` re-verifies the stored file digest on every
  read, so a tampered / moved file is reported STALE instead of silently
  trusted.

Scope note: engine consumption (``scenario_source: model|user_file``, the
measure guard and the run governance trail) is ES-3 - this page makes the
file pair uploadable, validated, previewable and persisted with its digest.

Discipline: STANDARD LIBRARY ONLY at import time (the ES-1 loader and its
numpy dependency are imported lazily inside the builders); user scenario
files are UNSIGNED scenario inputs; governed headline figures untouched.
"""
from __future__ import annotations

import datetime as _dt
import json
import os
import tempfile
from typing import Any, Dict, List, Optional, Tuple

SCN_GUI_SCHEMA_VERSION = "es2-gui-1.0"

#: Where uploaded sets are persisted (under the run_output root, keyed by
#: the first 12 hex chars of the CSV sha256 - like the GD-4/CF-2 stores).
SCENARIO_STORE_DIRNAME = "user_scenarios"

#: Preview payload persisted next to the stored file pair so /scenario-status
#: never has to re-parse the (up to ~13 MB) CSV on page load.
PREVIEW_CACHE_NAME = "SCENARIO_GUI_PREVIEW.json"

FAN_PERCENTILES = (5, 25, 50, 75, 95)

#: Upload guard: the designed file is ~13 MB (1,000 x 100 rows); anything an
#: order of magnitude beyond that is refused before parsing.
MAX_UPLOAD_BYTES = 128 * 1024 * 1024

_ES3_NOTE = ("persisted as a validated scenario INPUT; engine selection "
             "(scenario_source: model|user_file), the risk-neutral/real-world "
             "measure guard and the run governance trail land with ES-3")


def _structured(where: str, message: str) -> Dict[str, Any]:
    """Shape a page-level error like the loader's structured errors."""
    return {"where": where, "row": None, "column": None, "message": message}


def _texts_from_payload(payload: Any) -> Tuple[Optional[str], Optional[str],
                                               List[Dict[str, Any]]]:
    """Extract + guard the two uploaded texts from the POSTed JSON."""
    errors: List[Dict[str, Any]] = []
    if not isinstance(payload, dict):
        return None, None, [_structured("upload", "payload must be a JSON object")]
    csv_text = payload.get("csv_text")
    manifest_text = payload.get("manifest_text")
    if not isinstance(csv_text, str) or not csv_text.strip():
        errors.append(_structured(
            "upload", "scenario CSV missing - choose the "
            "economic_scenarios.csv file"))
    elif len(csv_text) > MAX_UPLOAD_BYTES:
        errors.append(_structured(
            "upload", "scenario CSV exceeds the %d MB upload guard"
            % (MAX_UPLOAD_BYTES // (1024 * 1024))))
    if not isinstance(manifest_text, str) or not manifest_text.strip():
        errors.append(_structured(
            "upload", "manifest missing - choose the "
            "economic_scenarios_manifest.json file"))
    elif len(manifest_text) > MAX_UPLOAD_BYTES:
        errors.append(_structured(
            "upload", "manifest exceeds the %d MB upload guard"
            % (MAX_UPLOAD_BYTES // (1024 * 1024))))
    if errors:
        return None, None, errors
    return csv_text, manifest_text, []


def _load_pair_from_texts(csv_text: str, manifest_text: str):
    """Write the posted texts byte-exact to a temp dir and run the REAL ES-1
    loader over them.  Returns ``(scenario_set, errors, n_errors)`` - on
    success errors is [] and the set is the validated UserScenarioSet."""
    from par_model_v2.stochastic import user_scenarios as us  # lazy: numpy
    with tempfile.TemporaryDirectory(prefix="es2_upload_") as tmp:
        csv_path = os.path.join(tmp, us.CSV_DEFAULT_NAME)
        man_path = os.path.join(tmp, us.MANIFEST_DEFAULT_NAME)
        # binary writes: the sha256 in the manifest is over the EXACT bytes
        # the user's tool wrote - no newline translation may intervene.
        with open(csv_path, "wb") as fh:
            fh.write(csv_text.encode("utf-8"))
        with open(man_path, "wb") as fh:
            fh.write(manifest_text.encode("utf-8"))
        try:
            sset = us.load_user_scenario_set(csv_path, man_path)
        except us.UserScenarioValidationError as exc:
            return None, exc.errors, exc.n_errors
        return sset, [], 0


def _fan(values, axis0_is_scenarios=True) -> Dict[str, List[float]]:
    """p5/p25/p50/p75/p95 across scenarios for each projection year."""
    import numpy as np  # lazy
    return {
        "p%d" % p: [round(float(v), 6)
                    for v in np.percentile(values, p, axis=0)]
        for p in FAN_PERCENTILES}


def _preview_payload(sset) -> Dict[str, Any]:
    """Shape the page preview: summary card + percentile fans by year for
    every tenor, the equity annual return and the cumulative equity index."""
    import numpy as np  # lazy
    fans: Dict[str, Any] = {}
    series: List[Dict[str, Any]] = []
    for ti, label in enumerate(sset.tenor_labels):
        key = "rate_%s" % label
        fans[key] = _fan(sset.rates[:, :, ti])
        series.append({"id": key, "label": "Spot zero rate %s (%%)" % label,
                       "pct": True})
    fans["eq_return"] = _fan(sset.eq_returns)
    series.append({"id": "eq_return",
                   "label": "Equity annual total return (%)", "pct": True})
    cum = np.cumprod(1.0 + sset.eq_returns, axis=1) * 100.0
    fans["eq_cumulative_index"] = _fan(cum)
    series.append({"id": "eq_cumulative_index",
                   "label": "Equity cumulative index (base 100)",
                   "pct": False})
    return {
        "schema": SCN_GUI_SCHEMA_VERSION,
        "years": list(range(1, sset.projection_years + 1)),
        "percentiles": list(FAN_PERCENTILES),
        "series": series,
        "fans": fans,
        "summary_card": sset.summary_card(),
        "summary_text": sset.render_summary_card_text(),
        "n_scenarios": sset.n_scenarios,
        "projection_years": sset.projection_years,
        "basis": sset.basis,
        "currency": sset.manifest.get("currency"),
        "source": sset.manifest.get("source"),
        "csv_sha256": sset.csv_sha256,
        "unsigned": True,
        "unsigned_banner": sset.unsigned_banner,
        "warnings": list(sset.warnings),
    }


def build_scenario_validate_response(payload: Any) -> Dict[str, Any]:
    """POST /validate-scenarios - validate the uploaded pair, no write."""
    csv_text, manifest_text, errors = _texts_from_payload(payload)
    if errors:
        return {"ok": False, "stage": "upload", "errors": errors,
                "n_errors": len(errors)}
    try:
        sset, verrors, n_errors = _load_pair_from_texts(csv_text, manifest_text)
    except Exception as exc:  # loader/numpy unavailable etc.
        return {"ok": False, "stage": "loader",
                "errors": [_structured("loader",
                                       "scenario loader unavailable: %s" % exc)],
                "n_errors": 1}
    if sset is None:
        return {"ok": False, "stage": "validation", "errors": verrors,
                "n_errors": n_errors}
    res = {"ok": True, "stage": "validated"}
    res.update(_preview_payload(sset))
    return res


def _read_model_inputs(out_path: str) -> Dict[str, Any]:
    if out_path and os.path.exists(out_path):
        try:
            with open(out_path, encoding="utf-8") as fh:
                return json.load(fh)
        except (OSError, json.JSONDecodeError):
            return {}
    return {}


def build_scenario_save_response(payload: Any, out_path: str,
                                 store_root: str) -> Dict[str, Any]:
    """POST /save-scenarios - validate, persist byte-exact under the digest
    key, merge the ``user_scenarios`` provenance block into
    ``model_inputs.json`` and RESET the run gate."""
    csv_text, manifest_text, errors = _texts_from_payload(payload)
    if errors:
        return {"ok": False, "stage": "upload", "errors": errors,
                "n_errors": len(errors)}
    try:
        sset, verrors, n_errors = _load_pair_from_texts(csv_text, manifest_text)
    except Exception as exc:
        return {"ok": False, "stage": "loader",
                "errors": [_structured("loader",
                                       "scenario loader unavailable: %s" % exc)],
                "n_errors": 1}
    if sset is None:
        return {"ok": False, "stage": "validation", "errors": verrors,
                "n_errors": n_errors}

    from par_model_v2.stochastic import user_scenarios as us  # lazy
    digest = sset.csv_sha256
    store_dir = os.path.join(store_root, digest[:12])
    csv_path = os.path.join(store_dir, us.CSV_DEFAULT_NAME)
    man_path = os.path.join(store_dir, us.MANIFEST_DEFAULT_NAME)
    try:
        os.makedirs(store_dir, exist_ok=True)
        with open(csv_path, "wb") as fh:
            fh.write(csv_text.encode("utf-8"))
        with open(man_path, "wb") as fh:
            fh.write(manifest_text.encode("utf-8"))
        # write-integrity guard: the persisted bytes MUST reproduce the
        # digest the manifest declares (fail loud, never trust the write).
        persisted = us.compute_csv_sha256(csv_path)
        if persisted != digest:
            return {"ok": False, "stage": "persist",
                    "errors": [_structured(
                        "store", "persisted CSV digest %s does not match the "
                        "validated digest %s - store write corrupted"
                        % (persisted, digest))],
                    "n_errors": 1}
    except OSError as exc:
        return {"ok": False, "stage": "persist",
                "errors": [_structured("store",
                                       "could not persist the set: %s" % exc)],
                "n_errors": 1}

    preview = _preview_payload(sset)
    block = {
        "schema": us.SCHEMA_ID,
        "gui_schema": SCN_GUI_SCHEMA_VERSION,
        "csv_path": os.path.abspath(csv_path),
        "manifest_path": os.path.abspath(man_path),
        "csv_sha256": digest,
        "basis": sset.basis,
        "n_scenarios": sset.n_scenarios,
        "projection_years": sset.projection_years,
        "currency": sset.manifest.get("currency"),
        "source": sset.manifest.get("source"),
        "created_utc": sset.manifest.get("created_utc"),
        "uploaded_utc": _dt.datetime.now(
            _dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "unsigned": True,
        "unsigned_banner": sset.unsigned_banner,
        "warnings": list(sset.warnings),
        "es3_note": _ES3_NOTE,
    }

    # preview cache (best-effort, re-parse guarded) so /scenario-status is fast
    try:
        cache_path = os.path.join(store_dir, PREVIEW_CACHE_NAME)
        tmp = cache_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(preview, fh)
        with open(tmp, encoding="utf-8") as fh:
            json.load(fh)  # re-parse guard
        os.replace(tmp, cache_path)
    except OSError:
        pass

    # merge into model_inputs.json + GATE RESET (inputs changed)
    mi = _read_model_inputs(out_path)
    mi["user_scenarios"] = block
    # ES-3: saving a validated set SELECTS it as the run scenario source and
    # derives the run measure intent from the file's OWN basis (so the ES-3
    # measure guard is satisfied by construction: risk_neutral->valuation,
    # real_world->p_diagnostic).  A run can revert to the governed ESG by
    # setting scenario_source back to "model".
    mi["scenario_source"] = "user_file"
    run_intent = ("valuation" if sset.basis == "risk_neutral"
                  else "p_diagnostic")
    mi["run_intent"] = run_intent
    gate_reset = mi.pop("run_gate", None) is not None
    try:
        with open(out_path, "w", encoding="utf-8") as fh:
            json.dump(mi, fh, indent=1)
        with open(out_path, encoding="utf-8") as fh:
            json.load(fh)  # re-parse guard: never hand a corrupt file on
    except OSError as exc:
        return {"ok": False, "stage": "persist",
                "errors": [_structured(
                    "model_inputs", "could not record the scenario block: %s"
                    % exc)],
                "n_errors": 1}

    res = {"ok": True, "stage": "saved",
           "written": os.path.abspath(out_path),
           "store_dir": os.path.abspath(store_dir),
           "user_scenarios": block,
           "scenario_source": "user_file",
           "run_intent": run_intent,
           "gate_reset": gate_reset,
           "gate_note": ("run gate reset - inputs changed, re-clear it on the "
                         "Run Gate page" if gate_reset else
                         "no cleared run gate was recorded; clear it on the "
                         "Run Gate page when the input set is complete"),
           "es3_note": _ES3_NOTE}
    res.update(preview)
    return res


def build_scenario_status_response(out_path: str) -> Dict[str, Any]:
    """GET /scenario-status - the currently persisted set, digest re-verified.

    Never trusts the stored block blindly: the persisted CSV is re-hashed on
    every read and a missing / tampered file is reported STALE (fail-loud)
    instead of silently served."""
    mi = _read_model_inputs(out_path)
    block = mi.get("user_scenarios")
    if not isinstance(block, dict):
        return {"ok": True, "present": False,
                "note": ("no user scenario set saved yet - upload + validate "
                         "+ save a file pair below")}
    csv_path = block.get("csv_path") or ""
    declared = str(block.get("csv_sha256") or "")
    if not os.path.isfile(csv_path):
        return {"ok": False, "present": True, "stale": True, "block": block,
                "errors": [_structured(
                    "store", "persisted scenario CSV not found at %s - "
                    "re-upload the set" % csv_path)]}
    try:
        from par_model_v2.stochastic.user_scenarios import compute_csv_sha256
        actual = compute_csv_sha256(csv_path)
    except Exception as exc:
        return {"ok": False, "present": True, "stale": True, "block": block,
                "errors": [_structured("loader",
                                       "digest re-check unavailable: %s" % exc)]}
    if actual != declared:
        return {"ok": False, "present": True, "stale": True, "block": block,
                "errors": [_structured(
                    "store", "persisted scenario CSV digest %s no longer "
                    "matches the recorded digest %s - the file changed on "
                    "disk; re-upload and re-save" % (actual, declared))]}

    res: Dict[str, Any] = {"ok": True, "present": True, "stale": False,
                           "block": block, "cached": False}
    cache_path = os.path.join(os.path.dirname(csv_path), PREVIEW_CACHE_NAME)
    if os.path.isfile(cache_path):
        try:
            with open(cache_path, encoding="utf-8") as fh:
                preview = json.load(fh)
            if (preview.get("schema") == SCN_GUI_SCHEMA_VERSION
                    and preview.get("csv_sha256") == declared):
                res["cached"] = True
                res.update(preview)
                return res
        except (OSError, json.JSONDecodeError, ValueError):
            pass  # fall through to a fresh parse
    # cache miss: re-load the persisted pair through the real loader
    try:
        from par_model_v2.stochastic import user_scenarios as us
        sset = us.load_user_scenario_set(
            csv_path, block.get("manifest_path") or None)
    except Exception as exc:
        return {"ok": False, "present": True, "stale": True, "block": block,
                "errors": [_structured(
                    "store", "persisted set no longer validates: %s" % exc)]}
    res.update(_preview_payload(sset))
    return res


def render_scenarios_html() -> str:
    """Self-contained /scenarios upload page (zero external references)."""
    return """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>User scenarios - ES-2</title>
<style>
 body{font:14px/1.5 system-ui,Segoe UI,Arial,sans-serif;margin:0;background:#0f1115;color:#e8eaed}
 main{max-width:1180px;margin:0 auto;padding:24px}
 h1{font-size:20px;margin:0 0 4px} h2{font-size:15px;margin:18px 0 8px;color:#9fb4ff}
 .card{background:#171a21;border:1px solid #262b36;border-radius:10px;padding:16px;margin:12px 0}
 .muted{color:#9aa3b2} .mono{font-family:ui-monospace,Consolas,monospace}
 button,select{font:inherit;padding:6px 12px;border-radius:8px;border:1px solid #2b6cff;background:#2b6cff;color:#fff;cursor:pointer}
 button.sec{background:#20242e;border-color:#394150}
 button:disabled{background:#33384a;border-color:#33384a;cursor:not-allowed}
 select{background:#0b0d12;border-color:#394150}
 input[type=file]{color:#9aa3b2}
 .unsigned{background:#3a2b12;border:1px solid #8a6d1a;color:#ffd166;border-radius:10px;padding:10px 14px;margin:10px 0;font-weight:600}
 .note{background:#12233a;border:1px solid #2b6cff;color:#9fb4ff;border-radius:10px;padding:8px 12px;margin:10px 0}
 .err{background:#2d1620;border:1px solid #7a3a4d;color:#ff9fb0;border-radius:10px;padding:8px 12px;margin:10px 0}
 .okmsg{background:#12301f;border:1px solid #2f7a4d;color:#9fe0b0;border-radius:10px;padding:8px 12px;margin:10px 0}
 table{border-collapse:collapse;width:100%;font-size:12.5px}
 th,td{border:1px solid #262b36;padding:4px 8px;text-align:left}
 th{background:#12151c;color:#9fb4ff}
 td.num{text-align:right;font-family:ui-monospace,Consolas,monospace}
 svg{width:100%;height:auto;background:#0b0d12;border:1px solid #20242e;border-radius:8px}
 .legend{display:flex;gap:14px;flex-wrap:wrap;margin:6px 0;font-size:12.5px}
 .legend span{display:inline-flex;align-items:center;gap:5px}
 .sw{width:12px;height:12px;border-radius:3px;display:inline-block}
 .kv{font-size:12.5px} .kv b{color:#9fb4ff;font-weight:600}
 label{margin-right:14px}
</style></head><body><main>
 <h1>User economic scenarios</h1>
 <div class="muted">ES-2 - upload a user-generated economic scenario file pair
  (<span class="mono">economic_scenarios.csv</span> +
  <span class="mono">economic_scenarios_manifest.json</span>, schema
  <span class="mono">esg-user-scenarios-1.0</span> - see
  <span class="mono">docs/ECONOMIC_SCENARIO_FILE_FORMAT.md</span> and the templates in
  <span class="mono">docs/templates/</span>). The pair is validated by the governed ES-1
  loader; every violation is listed with its row and column. A clean set can be saved:
  it is persisted under its sha256 digest and recorded in
  <span class="mono">model_inputs.json</span>, and the run gate is reset.</div>
 <div class="unsigned">UNSIGNED - user scenario files are scenario inputs; the generating
  source is NOT owner-approved. Every run records the file digest.</div>
 <div class="note">Engine selection (scenario_source: model | user_file), the
  risk-neutral / real-world measure guard and the run governance trail are ES-3 scope -
  this page validates, previews and persists the file pair with its digest.</div>

 <div class="card" id="current-card">
  <h2>Currently saved set</h2>
  <div class="muted" id="current-status">checking&hellip;</div>
  <div class="kv" id="current-detail" style="display:none"></div>
 </div>

 <div class="card">
  <h2>Upload</h2>
  <div style="margin:6px 0">
   <label>Scenario CSV <input type="file" id="file-csv" accept=".csv,text/csv"></label>
  </div>
  <div style="margin:6px 0">
   <label>Manifest JSON <input type="file" id="file-manifest" accept=".json,application/json"></label>
  </div>
  <div style="margin:10px 0">
   <button id="btn-validate" class="sec">Validate</button>
   <button id="btn-save">Validate &amp; save</button>
   <span class="muted" id="status"></span>
  </div>
 </div>

 <div class="err" id="errors-box" style="display:none">
  <div id="errors-head" style="font-weight:600;margin-bottom:6px"></div>
  <table id="errors-table"><thead><tr>
   <th>File</th><th>Row</th><th>Column</th><th>Problem</th>
  </tr></thead><tbody></tbody></table>
 </div>

 <div class="okmsg" id="saved-box" style="display:none"></div>

 <div id="preview" style="display:none">
  <div class="card kv" id="prov"></div>
  <div class="card">
   <h2>Summary card (spec &sect;4.6)</h2>
   <table id="summary-table"><thead><tr>
    <th>Projection year</th><th>10Y rate p5</th><th>p50</th><th>p95</th>
    <th>EQ_RETURN p5</th><th>p50</th><th>p95</th>
   </tr></thead><tbody></tbody></table>
   <div class="note" id="warn-box" style="display:none"></div>
  </div>
  <div class="card">
   <h2>Percentile fan preview</h2>
   <div style="margin:6px 0">
    <label class="muted">Series <select id="series"></select></label>
   </div>
   <div class="legend" id="leg"></div>
   <svg id="chart" viewBox="0 0 1080 340" preserveAspectRatio="none"></svg>
  </div>
 </div>

<script>
"use strict";
var $=function(id){return document.getElementById(id);};
var DATA=null;
var BAND_OUT="#1d2c4d", BAND_IN="#28406e", MEDIAN="#5b8def";
function svgEl(name){return document.createElementNS("http://www.w3.org/2000/svg",name);}
function clearSvg(s){while(s.firstChild){s.removeChild(s.firstChild);}}
function fmtVal(v,pctMode){
  if(pctMode){return (100*v).toFixed(2)+"%";}
  return Math.abs(v)>=1e6?(v/1e6).toFixed(1)+"M":v.toFixed(v<10?3:1);}
function readFileText(input){
  return new Promise(function(resolve,reject){
    if(!input.files||!input.files.length){resolve(null);return;}
    var r=new FileReader();
    r.onload=function(){resolve(String(r.result));};
    r.onerror=function(){reject(new Error("could not read "+input.files[0].name));};
    r.readAsText(input.files[0]);});}
function showErrors(res){
  var box=$("errors-box"),tb=$("errors-table").getElementsByTagName("tbody")[0];
  tb.innerHTML="";
  var errs=res.errors||[];
  $("errors-head").textContent="Validation FAILED - "+(res.n_errors||errs.length)
    +" error(s)"+(res.n_errors>errs.length?(" (showing first "+errs.length+")"):"");
  errs.forEach(function(e){
    var tr=document.createElement("tr");
    [e.where||"-",(e.row===null||e.row===undefined)?"-":e.row,
     e.column||"-",e.message||""].forEach(function(cell){
      var td=document.createElement("td");td.textContent=String(cell);
      tr.appendChild(td);});
    tb.appendChild(tr);});
  box.style.display="block";}
function hideErrors(){$("errors-box").style.display="none";}
function drawFan(fanKey){
  var svg=$("chart");clearSvg(svg);
  var fan=DATA.fans[fanKey];if(!fan){return;}
  var spec=null;
  DATA.series.forEach(function(s){if(s.id===fanKey){spec=s;}});
  var pct=spec?spec.pct:false;
  var years=DATA.years,n=years.length;
  var lo=Infinity,hi=-Infinity;
  ["p5","p95"].forEach(function(k){fan[k].forEach(function(v){
    if(v<lo)lo=v;if(v>hi)hi=v;});});
  if(lo===hi){lo-=1;hi+=1;}
  var padc=(hi-lo)*0.06;lo-=padc;hi+=padc;
  var W=1080,H=340,pad=52;
  var X=function(i){return pad+(W-2*pad)*i/(n-1);};
  var Y=function(v){return H-pad-(H-2*pad)*(v-lo)/(hi-lo);};
  var ax=svgEl("g");
  for(var g=0;g<=4;g++){
    var yv=lo+(hi-lo)*g/4,y=Y(yv);
    var ln=svgEl("line");ln.setAttribute("x1",pad);ln.setAttribute("x2",W-pad);
    ln.setAttribute("y1",y);ln.setAttribute("y2",y);ln.setAttribute("stroke","#20242e");ax.appendChild(ln);
    var t=svgEl("text");t.setAttribute("x",4);t.setAttribute("y",y+4);
    t.setAttribute("fill","#9aa3b2");t.setAttribute("font-size","10");
    t.textContent=fmtVal(yv,pct);ax.appendChild(t);}
  for(var f=0;f<=5;f++){
    var yi=Math.round((n-1)*f/5);
    var tx=svgEl("text");tx.setAttribute("x",X(yi));tx.setAttribute("y",H-6);
    tx.setAttribute("fill","#9aa3b2");tx.setAttribute("font-size","10");
    tx.setAttribute("text-anchor","middle");
    tx.textContent="y"+years[yi];ax.appendChild(tx);}
  svg.appendChild(ax);
  function band(loKey,hiKey,fill){
    var pts=[];
    for(var i=0;i<n;i++){pts.push(X(i).toFixed(1)+","+Y(fan[hiKey][i]).toFixed(1));}
    for(var j=n-1;j>=0;j--){pts.push(X(j).toFixed(1)+","+Y(fan[loKey][j]).toFixed(1));}
    var pg=svgEl("polygon");pg.setAttribute("points",pts.join(" "));
    pg.setAttribute("fill",fill);pg.setAttribute("stroke","none");svg.appendChild(pg);}
  band("p5","p95",BAND_OUT);
  band("p25","p75",BAND_IN);
  var med=fan.p50.map(function(v,i){return X(i).toFixed(1)+","+Y(v).toFixed(1);}).join(" ");
  var ml=svgEl("polyline");ml.setAttribute("points",med);ml.setAttribute("fill","none");
  ml.setAttribute("stroke",MEDIAN);ml.setAttribute("stroke-width","2");svg.appendChild(ml);
  $("leg").innerHTML="<span><span class=sw style='background:"+BAND_OUT+"'></span>p5-p95</span>"
    +"<span><span class=sw style='background:"+BAND_IN+"'></span>p25-p75</span>"
    +"<span><span class=sw style='background:"+MEDIAN+"'></span>median</span>";}
function renderPreview(d){
  DATA=d;
  $("prov").innerHTML="<b>Provenance</b> &mdash; scenarios "+d.n_scenarios
    +" &middot; years "+d.projection_years
    +" &middot; basis <span class=mono>"+d.basis+"</span>"
    +" &middot; currency "+(d.currency||"-")
    +" &middot; source "+String(d.source||"-").replace(/</g,"&lt;")
    +" &middot; sha256 <span class=mono>"+String(d.csv_sha256).slice(0,12)+"&hellip;</span>";
  var tb=$("summary-table").getElementsByTagName("tbody")[0];
  tb.innerHTML="";
  var by=(d.summary_card&&d.summary_card.by_projection_year)||{};
  Object.keys(by).forEach(function(y){
    var r=by[y].rate_10y,q=by[y].eq_return;
    var tr=document.createElement("tr");
    [y,(100*r.p5).toFixed(2)+"%",(100*r.p50).toFixed(2)+"%",(100*r.p95).toFixed(2)+"%",
     (100*q.p5).toFixed(2)+"%",(100*q.p50).toFixed(2)+"%",(100*q.p95).toFixed(2)+"%"]
      .forEach(function(cell,i){
        var td=document.createElement("td");
        if(i>0){td.className="num";}
        td.textContent=String(cell);tr.appendChild(td);});
    tb.appendChild(tr);});
  var wb=$("warn-box");
  if(d.warnings&&d.warnings.length){
    wb.style.display="block";wb.textContent="WARNING: "+d.warnings.join(" | ");
  }else{wb.style.display="none";}
  var sel=$("series");sel.innerHTML="";
  d.series.forEach(function(s){
    var o=document.createElement("option");o.value=s.id;o.textContent=s.label;
    sel.appendChild(o);});
  sel.value="rate_10Y";
  $("preview").style.display="block";
  drawFan(sel.value);}
function post(url){
  return Promise.all([readFileText($("file-csv")),readFileText($("file-manifest"))])
    .then(function(texts){
      return fetch(url,{method:"POST",
        headers:{"Content-Type":"application/json"},
        body:JSON.stringify({csv_text:texts[0],manifest_text:texts[1]})});})
    .then(function(r){return r.json();});}
function run(url,saving){
  hideErrors();$("saved-box").style.display="none";
  $("btn-validate").disabled=true;$("btn-save").disabled=true;
  $("status").textContent=saving?"validating + saving…":"validating…";
  post(url).then(function(res){
    $("btn-validate").disabled=false;$("btn-save").disabled=false;
    if(!res.ok){
      $("status").textContent="validation failed";
      showErrors(res);$("preview").style.display="none";return;}
    $("status").textContent=saving?"saved":"valid";
    renderPreview(res);
    if(saving){
      var sb=$("saved-box");sb.style.display="block";
      sb.textContent="Saved. Set "+String(res.csv_sha256).slice(0,12)
        +"… recorded in model_inputs.json ("
        +(res.gate_reset?"run gate RESET - re-clear it before running":"run gate: "+res.gate_note)
        +"). "+res.es3_note;
      loadStatus();}
  }).catch(function(e){
    $("btn-validate").disabled=false;$("btn-save").disabled=false;
    $("status").textContent="ERROR: "+e;});}
function loadStatus(){
  fetch("/scenario-status").then(function(r){return r.json();}).then(function(d){
    var st=$("current-status"),det=$("current-detail");
    if(!d.present){st.textContent=d.note||"no set saved yet";det.style.display="none";return;}
    if(!d.ok){
      st.textContent="STALE: "+((d.errors||[]).map(function(e){return e.message;}).join("; ")||"unknown");
      det.style.display="none";return;}
    var b=d.block||{};
    st.textContent=d.cached?"verified (digest re-checked; preview from cache)":"verified (digest re-checked)";
    det.style.display="block";
    det.innerHTML="<b>sha256</b> <span class=mono>"+String(b.csv_sha256).slice(0,12)+"&hellip;</span>"
      +" &middot; <b>basis</b> "+b.basis
      +" &middot; <b>scenarios</b> "+b.n_scenarios
      +" &middot; <b>currency</b> "+(b.currency||"-")
      +" &middot; <b>uploaded</b> "+(b.uploaded_utc||"-")
      +" &middot; <b>source</b> "+String(b.source||"-").replace(/</g,"&lt;");
    if(d.fans){renderPreview(d);}
  }).catch(function(e){
    $("current-status").textContent="status unavailable: "+e;});}
$("btn-validate").addEventListener("click",function(){run("/validate-scenarios",false);});
$("btn-save").addEventListener("click",function(){run("/save-scenarios",true);});
$("series").addEventListener("change",function(){if(DATA){drawFan($("series").value);}});
loadStatus();
</script>
</main></body></html>"""
