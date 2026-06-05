#!/usr/bin/env python3
"""
build_combined_gui.py — assemble ONE offline, self-contained HTML application
that combines the two existing GUIs into a single file with two modes:

    [ Projection ]  the interactive input -> run -> illustrate tool
                    (par_projection_gui.html), with its CDN Chart.js removed and
                    replaced by an inline SVG chart shim so it works fully offline.

    [ Results ]     the offline result-viewer dashboard
                    (model_result_viewer.html) — Capital / Aggregation / Proxy /
                    Governance — unchanged (already offline, hand-rendered SVG).

Isolation: each original app is embedded verbatim inside its own <iframe srcdoc>,
so the two apps' CSS and global JS never collide. The shell only adds a mode
switch and ONE unified data loader.

Data contract: a single enriched output file `combined_app_data.json`:
    { schema, meta, results:{...viewer_data.json...}, projection:{...seed...} }
The shell embeds this snapshot AND accepts a freshly dropped unified file; it
routes `results` -> the Results iframe (its render()) and `projection` -> the
Projection iframe (loadCurve/loadPreset/inputs/auto-run) via postMessage.

No CDN, no npm, no build step at runtime: double-click the HTML and it works.
"""
from __future__ import annotations
import base64
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

PROJ_SRC = os.path.join(ROOT, "par_projection_gui.html")
VIEW_SRC = os.path.join(ROOT, "model_result_viewer.html")
SHIM_SRC = os.path.join(ROOT, "par_model_v2", "viewer", "svg_chart_shim.js")
VIEWER_DATA = os.path.join(ROOT, "viewer_data.json")

OUT_HTML = os.path.join(ROOT, "combined_model_app.html")
OUT_DATA = os.path.join(ROOT, "combined_app_data.json")


def _read(p: str) -> str:
    with open(p, "r", encoding="utf-8") as f:
        return f.read()


# --------------------------------------------------------------------------- #
# Projection-mode transforms: make it offline + message-driven                #
# --------------------------------------------------------------------------- #
PROJ_SEED_LISTENER = """
<script>
/* COMBINED-APP BRIDGE (projection mode): apply a saved projection scenario */
(function(){
  function applySeed(p){
    if(!p) return;
    try{
      if(p.curve && typeof loadCurve==='function') loadCurve(p.curve);
      if(p.preset && typeof loadPreset==='function'){ loadPreset(p.preset);
        if(typeof renderRows==='function') renderRows();
        if(typeof updateAllocChart==='function') updateAllocChart();
        if(typeof updatePortMetrics==='function') updatePortMetrics();
      }
      if(p.inputs){ for(var id in p.inputs){ var el=document.getElementById(id);
        if(el){ el.value=p.inputs[id]; el.dispatchEvent(new Event('input',{bubbles:true})); } } }
      if(p.reference_run && typeof setReferenceRun==='function'){
        setReferenceRun(p.reference_run);
        if(typeof runModel==='function'){ try{ runModel(); }catch(_){} }
      } else if(p.auto_run && typeof runAll==='function'){ runAll(); }
    }catch(e){ try{console.error('projection seed failed',e);}catch(_){} }
  }
  window.addEventListener('message',function(ev){
    var m=ev.data||{};
    if(m && m.type==='seed-projection') applySeed(m.payload);
  });
  // announce readiness so the shell can (re)send a seed
  try{ if(window.parent && window.parent!==window) window.parent.postMessage({type:'projection-ready'},'*'); }catch(_){}
})();
</script>
"""

VIEW_RESULTS_LISTENER = """
<script>
/* COMBINED-APP BRIDGE (results mode): re-render the dashboard from a payload */
(function(){
  window.addEventListener('message',function(ev){
    var m=ev.data||{};
    if(m && m.type==='set-results' && m.payload && typeof render==='function'){
      try{ render(m.payload);
        var d=document.getElementById('drop'); if(d) d.innerHTML='Loaded from unified data file.';
      }catch(e){ try{console.error('set-results failed',e);}catch(_){} }
    }
  });
  try{ if(window.parent && window.parent!==window) window.parent.postMessage({type:'results-ready'},'*'); }catch(_){}
})();
</script>
"""


def build_projection_html() -> str:
    html = _read(PROJ_SRC)
    shim = _read(SHIM_SRC)

    # 1) remove the CDN Chart.js dependency (the ONLY external/network ref)
    html, n = re.subn(
        r'<script[^>]+src="https?://[^"]*[Cc]hart[^"]*"[^>]*>\s*</script>\s*',
        "", html)
    if n == 0:
        # fall back: strip any remaining external <script src="http...">
        html = re.sub(r'<script[^>]+src="https?://[^"]+"[^>]*>\s*</script>\s*', "", html)

    shim_block = "<script>\n/* === inlined svg_chart_shim.js (offline) === */\n" + shim + "\n</script>\n"
    inject = shim_block + PROJ_SEED_LISTENER
    # inject right before </body> so it runs after the page's own script (overrides mkChart)
    if "</body>" in html:
        html = html.replace("</body>", inject + "</body>", 1)
    else:
        html = html + inject
    # safety: assert no external network refs remain
    leftovers = re.findall(r'(?:src|href)="https?://[^"]+"', html)
    if leftovers:
        raise SystemExit("projection still has external refs: %r" % leftovers[:5])
    return html


def build_viewer_html() -> str:
    html = _read(VIEW_SRC)
    inject = VIEW_RESULTS_LISTENER
    if "</body>" in html:
        html = html.replace("</body>", inject + "</body>", 1)
    else:
        html = html + inject
    leftovers = re.findall(r'(?:src|href)="https?://[^"]+"', html)
    if leftovers:
        raise SystemExit("viewer has external refs: %r" % leftovers[:5])
    return html


# --------------------------------------------------------------------------- #
# Enriched unified data contract                                              #
# --------------------------------------------------------------------------- #
def build_unified_data() -> dict:
    results = json.loads(_read(VIEWER_DATA))
    meta = dict(results.get("meta", {}))
    projection = {
        "description": "Saved projection scenario that seeds the interactive Projection mode. "
                       "The Projection engine still computes live in-browser; these fields set "
                       "the starting yield curve, asset preset, and key inputs.",
        "scenario_name": "CNY balanced participating endowment (educational default)",
        "curve": "cny2024",
        "preset": "balanced",
        "auto_run": False,
        "inputs": {},  # optional {elementId: value}; applied only if the id exists
        "assumptions_snapshot": {
            "discount_rate": 0.03,
            "ph_share": 0.90,
            "mortality_basis": "CL(2013) proxy, blended",
            "lapse_schedule_pct": [12.0, 9.0, 7.0, 5.0, 3.0, 1.5],
            "lapse_multiplier": 1.0,
            "note": "Mirrors the Projection GUI's built-in defaults; edit & re-run interactively.",
        },
        "available_curves": ["cny2024", "eur2024", "hkd2024", "flat35", "flat45"],
        "available_presets": ["conservative", "balanced", "aggressive", "sample"],
    }
    ref_path = os.path.join(ROOT, "docs", "validation", "PROJECTION_REFERENCE_RUN.json")
    if os.path.exists(ref_path):
        projection["reference_run"] = json.loads(_read(ref_path))
    return {
        "schema": "par-combined-app/v1",
        "meta": meta,
        "results": results,
        "projection": projection,
    }


# --------------------------------------------------------------------------- #
# Shell                                                                       #
# --------------------------------------------------------------------------- #
SHELL_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>PAR Stochastic Model — Combined GUI (offline)</title>
<style>
  :root{ --bg:#0c0f1d; --panel:#11142a; --line:#23284a; --ink:#e8ecff; --muted:#8f96b0;
         --accent:#5b8df7; --accent2:#27c9a0; }
  *{box-sizing:border-box}
  html,body{margin:0;height:100%}
  body{background:var(--bg);color:var(--ink);font-family:system-ui,-apple-system,'Segoe UI',Roboto,sans-serif;
       display:flex;flex-direction:column}
  header{display:flex;align-items:center;gap:14px;flex-wrap:wrap;padding:10px 16px;
         background:linear-gradient(180deg,#12162e,#0c0f1d);border-bottom:1px solid var(--line)}
  .brand{font-weight:700;font-size:15px;letter-spacing:.2px}
  .brand small{display:block;font-weight:400;font-size:11px;color:var(--muted)}
  .modes{display:flex;gap:6px;margin-left:6px}
  .mode{background:#161a34;color:var(--muted);border:1px solid var(--line);border-radius:8px;
        padding:7px 16px;font-size:13px;font-weight:600;cursor:pointer}
  .mode.active{background:var(--accent);color:#fff;border-color:var(--accent)}
  .spacer{flex:1}
  .ctl{display:flex;align-items:center;gap:8px}
  .ctl button,.ctl label{background:#161a34;color:var(--ink);border:1px solid var(--line);border-radius:8px;
        padding:6px 12px;font-size:12px;cursor:pointer}
  .ctl button:hover,.ctl label:hover{border-color:var(--accent)}
  #pill{font-size:11px;color:var(--muted)}
  #drop{font-size:11px;color:var(--muted);border:1px dashed var(--line);border-radius:8px;padding:5px 10px}
  #drop.over{border-color:var(--accent2);color:var(--ink)}
  main{flex:1;position:relative;min-height:0}
  iframe{position:absolute;inset:0;width:100%;height:100%;border:0;background:var(--bg);display:none}
  iframe.active{display:block}
  input[type=file]{display:none}
  .badge{font-size:10px;color:#0c0f1d;background:var(--accent2);border-radius:10px;padding:2px 8px;font-weight:700}
</style>
</head>
<body>
<header>
  <div class="brand">PAR Stochastic Model — Combined GUI
    <small id="metaLine">offline · no network · double-click to run</small></div>
  <div class="modes">
    <button class="mode active" id="modeProjection" onclick="switchMode('projection')">📈 Projection</button>
    <button class="mode" id="modeResults" onclick="switchMode('results')">📊 Results</button>
  </div>
  <span class="badge" id="classBadge">EDUCATIONAL</span>
  <div class="spacer"></div>
  <div class="ctl">
    <span id="drop">Drop a <code>combined_app_data.json</code> here</span>
    <label for="dataFile">📂 Load data file</label>
    <input type="file" id="dataFile" accept="application/json,.json">
    <button onclick="reseed()">↻ Re-seed</button>
    <span id="pill"></span>
  </div>
</header>
<main>
  <iframe id="frameProjection" class="active" title="Projection"></iframe>
  <iframe id="frameResults" title="Results"></iframe>
</main>

<script id="appData" type="application/json">__APP_DATA__</script>
<script>
/* ===== embedded sub-apps (base64 of UTF-8) — fully offline ================ */
var PROJ_B64 = "__PROJ_B64__";
var VIEW_B64 = "__VIEW_B64__";

function b64ToUtf8(b64){
  var bin = atob(b64), bytes = new Uint8Array(bin.length);
  for (var i=0;i<bin.length;i++) bytes[i]=bin.charCodeAt(i);
  return new TextDecoder('utf-8').decode(bytes);
}

var APP_DATA = JSON.parse(document.getElementById('appData').textContent);
var fProj = document.getElementById('frameProjection');
var fView = document.getElementById('frameResults');
var ready = {projection:false, results:false};

// classification + meta line
try{
  var cls = (APP_DATA.meta && APP_DATA.meta.classification) || 'EDUCATIONAL';
  document.getElementById('classBadge').textContent = (''+cls).split('--')[0].trim().slice(0,22) || 'EDUCATIONAL';
  var mn = (APP_DATA.meta && APP_DATA.meta.model_name) || 'PAR Fund';
  var mv = (APP_DATA.meta && APP_DATA.meta.model_version) || '';
  document.getElementById('metaLine').textContent = mn + (mv?(' v'+mv):'') + ' · offline · no network';
}catch(e){}

// receive readiness, then push the matching data slice
window.addEventListener('message', function(ev){
  var m = ev.data||{};
  if (m.type==='projection-ready'){ ready.projection=true; pushProjection(); }
  if (m.type==='results-ready'){ ready.results=true; pushResults(); }
});
function pushProjection(){ if(ready.projection && APP_DATA.projection)
  fProj.contentWindow.postMessage({type:'seed-projection', payload:APP_DATA.projection}, '*'); }
function pushResults(){ if(ready.results && APP_DATA.results)
  fView.contentWindow.postMessage({type:'set-results', payload:APP_DATA.results}, '*'); }

// build the iframes from the embedded sub-apps
fProj.srcdoc = b64ToUtf8(PROJ_B64);
fView.srcdoc = b64ToUtf8(VIEW_B64);

function switchMode(mode){
  var p = mode==='projection';
  fProj.classList.toggle('active', p);
  fView.classList.toggle('active', !p);
  document.getElementById('modeProjection').classList.toggle('active', p);
  document.getElementById('modeResults').classList.toggle('active', !p);
}
function reseed(){ pushProjection(); pushResults();
  document.getElementById('pill').textContent='re-seeded'; setTimeout(function(){document.getElementById('pill').textContent='';},1500); }

// ---- unified data-file loading (offline; routes to both modes) ----------
function ingest(obj){
  // accept either the unified {results,projection} or a bare viewer_data.json
  if (obj && (obj.results || obj.projection)){ APP_DATA = obj; }
  else { APP_DATA = {schema:'par-combined-app/v1', meta:obj.meta||{}, results:obj, projection:APP_DATA.projection}; }
  pushResults(); pushProjection();
  document.getElementById('drop').innerHTML = 'Loaded unified data file.';
}
function loadFile(file){
  var r = new FileReader();
  r.onload = function(){ try{ ingest(JSON.parse(r.result)); }
    catch(e){ alert('Invalid JSON: '+e.message); } };
  r.readAsText(file);
}
document.getElementById('dataFile').addEventListener('change', function(e){
  if(e.target.files[0]) loadFile(e.target.files[0]); });
var drop = document.getElementById('drop');
['dragover','dragenter'].forEach(function(ev){ drop.addEventListener(ev,function(e){e.preventDefault();drop.classList.add('over');}); });
['dragleave','dragend'].forEach(function(ev){ drop.addEventListener(ev,function(e){e.preventDefault();drop.classList.remove('over');}); });
drop.addEventListener('drop', function(e){ e.preventDefault(); drop.classList.remove('over');
  if(e.dataTransfer.files[0]) loadFile(e.dataTransfer.files[0]); });
// also accept drops anywhere on the window
window.addEventListener('dragover', function(e){e.preventDefault();});
window.addEventListener('drop', function(e){ e.preventDefault();
  if(e.dataTransfer && e.dataTransfer.files[0]) loadFile(e.dataTransfer.files[0]); });
</script>
</body>
</html>
"""


def build_shell(proj_html: str, view_html: str, data: dict) -> str:
    proj_b64 = base64.b64encode(proj_html.encode("utf-8")).decode("ascii")
    view_b64 = base64.b64encode(view_html.encode("utf-8")).decode("ascii")
    data_json = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    # guard: the JSON must not break the <script> block
    data_json = data_json.replace("</script>", "<\\/script>")
    html = SHELL_TEMPLATE
    html = html.replace("__PROJ_B64__", proj_b64)
    html = html.replace("__VIEW_B64__", view_b64)
    html = html.replace("__APP_DATA__", data_json)
    return html


def main() -> int:
    proj = build_projection_html()
    view = build_viewer_html()
    data = build_unified_data()
    shell = build_shell(proj, view, data)

    with open(OUT_DATA, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    with open(OUT_HTML, "w", encoding="utf-8") as f:
        f.write(shell)

    # report
    ext = re.findall(r'(?:src|href)="https?://[^"]+"', shell)
    print("combined_model_app.html :", len(shell), "bytes")
    print("combined_app_data.json  :", os.path.getsize(OUT_DATA), "bytes")
    print("external network refs in shell text:", len(ext), "(base64 blobs scanned separately by self-test)")
    print("projection charts -> inline SVG shim; viewer -> existing SVG; modes: projection|results")
    return 0


if __name__ == "__main__":
    sys.exit(main())
