"""GD-1 - Scenario-path detail GUI page (owner directive 2026-07-07).

Serves the stepwise economic-scenario / asset-return path detail in the GUI:
percentile FANS (p5/p25/p50/p75/p95) and raw SAMPLE paths for the real-world
(Measure.P) short rate, the equity index, and per-asset-class returns /
cumulative total-return indices derived with the SAME class mechanics as the
CF-1 projection set. All charts are self-drawn inline SVG - zero external
references, matching every other console page.

Data flow: ``GET /path-data`` reads the SAVED ``model_inputs.json`` (seed +
horizon from Run Controls, asset classes from the balance sheet), runs the
GD-1 engine into ``<out_root>/path_detail/`` (JSON + 6 CSVs), and returns a
compact display payload. The result is CACHED by the GD-1 inputs digest:
while seed / horizon / balance sheet are unchanged the engine is not re-run.

Discipline: STANDARD LIBRARY ONLY at import time (engine / numpy / pandas
are imported lazily inside the data builder); diagnostic overlay - governed
headline figures untouched; parameters UNSIGNED (banner shown).
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict

PATH_GUI_SCHEMA_VERSION = "gd1-gui-1.0"
PATH_SET_DIRNAME = "path_detail"
PAGE_SAMPLE_PATHS = 10   # raw paths surfaced to the page (payload size guard)


def build_path_detail_response(inputs_path: str, out_root: str) -> Dict[str, Any]:
    """Compute (or serve cached) the path-detail set, shaped for the page."""
    mi: Dict[str, Any] = {}
    inputs_note = None
    if os.path.exists(inputs_path):
        try:
            with open(inputs_path, encoding="utf-8") as fh:
                mi = json.load(fh)
        except (OSError, json.JSONDecodeError) as exc:
            return {"ok": False, "errors": [
                "could not parse model_inputs.json: %s" % exc]}
    else:
        inputs_note = ("model_inputs.json not found - showing governed "
                       "defaults (seed 42); save Run Controls / Portfolio "
                       "to bind paths to your run inputs")

    try:
        from par_model_v2.projection.scenario_path_detail import (
            _inputs_digest, _resolve_horizon, build_scenario_path_detail,
            DEFAULT_N_PATHS)
    except Exception as exc:  # pragma: no cover - engine deps missing
        return {"ok": False, "errors": ["path-detail engine unavailable: %s" % exc]}

    out_dir = os.path.join(out_root, PATH_SET_DIRNAME)
    cache_path = os.path.join(out_dir, "PATH_GUI_CACHE.json")
    digest = _inputs_digest(mi, DEFAULT_N_PATHS, _resolve_horizon(mi, None))
    if os.path.exists(cache_path):
        try:
            with open(cache_path, encoding="utf-8") as fh:
                cached = json.load(fh)
            if (cached.get("inputs_digest") == digest
                    and cached.get("schema") == PATH_GUI_SCHEMA_VERSION):
                cached["cached"] = True
                return cached
        except (OSError, json.JSONDecodeError, ValueError):
            pass  # fall through to recompute

    try:
        res = build_scenario_path_detail(mi, out_dir=out_dir)
    except Exception as exc:
        return {"ok": False, "errors": ["path simulation failed: %s" % exc]}

    n_show = min(PAGE_SAMPLE_PATHS, int(res.get("n_display") or 0) or PAGE_SAMPLE_PATHS)
    payload: Dict[str, Any] = {
        "ok": True,
        "schema": PATH_GUI_SCHEMA_VERSION,
        "cached": False,
        "inputs_digest": digest,
        "unsigned_note": res["unsigned_note"],
        "inputs_note": inputs_note,
        "measure": res["measure"],
        "seed": res["seed"],
        "n_paths": res["n_paths"],
        "horizon_months": res["horizon_months"],
        "parameters": res["parameters"],
        "asset_classes": res["asset_classes"],
        "fans": res["fans"],
        "samples": {
            "months": res["samples"]["months"],
            "short_rate": res["samples"]["short_rate"][:n_show],
            "equity_index": res["samples"]["equity_index"][:n_show],
        },
        "csv_dir": out_dir,
    }
    try:
        os.makedirs(out_dir, exist_ok=True)
        tmp = cache_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, default=str)
        with open(tmp, encoding="utf-8") as fh:
            json.load(fh)  # re-parse guard
        os.replace(tmp, cache_path)
    except OSError:
        pass  # cache is best-effort
    return payload


def render_paths_html() -> str:
    """Self-contained scenario-path page (fan charts + sample overlays)."""
    return """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Scenario paths - GD-1</title>
<style>
 body{font:14px/1.5 system-ui,Segoe UI,Arial,sans-serif;margin:0;background:#0f1115;color:#e8eaed}
 main{max-width:1180px;margin:0 auto;padding:24px}
 h1{font-size:20px;margin:0 0 4px} h2{font-size:15px;margin:18px 0 8px;color:#9fb4ff}
 .card{background:#171a21;border:1px solid #262b36;border-radius:10px;padding:16px;margin:12px 0}
 .muted{color:#9aa3b2} .mono{font-family:ui-monospace,Consolas,monospace}
 button,select{font:inherit;padding:6px 12px;border-radius:8px;border:1px solid #2b6cff;background:#2b6cff;color:#fff;cursor:pointer}
 select{background:#0b0d12;border-color:#394150}
 button:disabled{background:#33384a;border-color:#33384a;cursor:not-allowed}
 label{margin-right:14px}
 .unsigned{background:#3a2b12;border:1px solid #8a6d1a;color:#ffd166;border-radius:10px;padding:10px 14px;margin:10px 0;font-weight:600}
 .note{background:#12233a;border:1px solid #2b6cff;color:#9fb4ff;border-radius:10px;padding:8px 12px;margin:10px 0}
 .legend{display:flex;gap:14px;flex-wrap:wrap;margin:6px 0;font-size:12.5px}
 .legend span{display:inline-flex;align-items:center;gap:5px}
 .sw{width:12px;height:12px;border-radius:3px;display:inline-block}
 svg{width:100%;height:auto;background:#0b0d12;border:1px solid #20242e;border-radius:8px}
 .kv{font-size:12.5px} .kv b{color:#9fb4ff;font-weight:600}
</style></head><body><main>
 <h1>Scenario paths &amp; asset returns</h1>
 <div class="muted">GD-1 - stepwise economic-scenario detail: real-world (P) short-rate and
  equity-index paths on the governed educational parameters with your SAVED run seed, and
  per-asset-class return / cumulative-index fans on the same class mechanics as the
  <a href="/cashflows" style="color:#9fb4ff">Cash flows</a> set.
  Percentile fan = p5/p25/p50/p75/p95 across all simulated paths; thin lines = raw sample paths.</div>
 <div class="unsigned" id="unsigned" style="display:none"></div>
 <div class="note" id="inputs-note" style="display:none"></div>

 <div class="card">
  <button id="btn-load">Simulate / refresh paths</button>
  <span class="muted" id="status">(not loaded yet)</span>
 </div>

 <div id="content" style="display:none">
  <div class="card kv" id="prov"></div>
  <div class="card">
   <h2>Series</h2>
   <div style="margin:6px 0">
    <label class="muted">Show
     <select id="series"></select></label>
    <label class="muted"><input type="checkbox" id="show-samples" checked>
     overlay sample paths (rate / equity only)</label>
   </div>
   <div class="legend" id="leg"></div>
   <svg id="chart" viewBox="0 0 1080 340" preserveAspectRatio="none"></svg>
  </div>
  <p class="muted">CSV copies (fans + sample paths) are written to
   <span class="mono" id="csvdir"></span>.</p>
 </div>

<script>
"use strict";
var $=function(id){return document.getElementById(id);};
var DATA=null;
var BAND_OUT="#1d2c4d", BAND_IN="#28406e", MEDIAN="#5b8def", SAMPLE="#9aa3b2";
function svgEl(name){return document.createElementNS("http://www.w3.org/2000/svg",name);}
function clearSvg(s){while(s.firstChild){s.removeChild(s.firstChild);}}
function fmtVal(v,pctMode){
  if(pctMode){return (100*v).toFixed(2)+"%";}
  return Math.abs(v)>=1e6?(v/1e6).toFixed(1)+"M":v.toFixed(v<10?3:1);}
function seriesCatalogue(d){
  var cat=[{id:"short_rate",label:"Short rate (P, %)",pct:true,months:d.samples.months,
            fan:d.fans.short_rate,samples:d.samples.short_rate},
           {id:"equity_index",label:"Equity index (P, level)",pct:false,months:d.samples.months,
            fan:d.fans.equity_index,samples:d.samples.equity_index}];
  d.asset_classes.forEach(function(c){
    cat.push({id:"cum_"+c,label:"Cumulative index - "+c+" (base 100)",pct:false,
              months:d.samples.months,fan:d.fans.asset_class_cumulative_index[c],samples:null});
    var mret=d.fans.asset_class_monthly_return[c];
    var m1=[];for(var i=1;i<d.samples.months.length;i++){m1.push(d.samples.months[i]);}
    cat.push({id:"ret_"+c,label:"Monthly return - "+c+" (%)",pct:true,
              months:m1,fan:mret,samples:null});});
  return cat;}
function bounds(fan,samples){
  var lo=Infinity,hi=-Infinity;
  ["p5","p95"].forEach(function(k){fan[k].forEach(function(v){
    if(v<lo)lo=v;if(v>hi)hi=v;});});
  if(samples){samples.forEach(function(p){p.forEach(function(v){
    if(v<lo)lo=v;if(v>hi)hi=v;});});}
  if(lo===hi){lo-=1;hi+=1;}
  var padc=(hi-lo)*0.06;return [lo-padc,hi+padc];}
function drawFan(spec,showSamples){
  var svg=$("chart");clearSvg(svg);
  var W=1080,H=340,pad=52;
  var months=spec.months,n=months.length;
  var bl=bounds(spec.fan,showSamples?spec.samples:null),lo=bl[0],hi=bl[1];
  var X=function(i){return pad+(W-2*pad)*i/(n-1);};
  var Y=function(v){return H-pad-(H-2*pad)*(v-lo)/(hi-lo);};
  var ax=svgEl("g");
  for(var g=0;g<=4;g++){
    var yv=lo+(hi-lo)*g/4,y=Y(yv);
    var ln=svgEl("line");ln.setAttribute("x1",pad);ln.setAttribute("x2",W-pad);
    ln.setAttribute("y1",y);ln.setAttribute("y2",y);ln.setAttribute("stroke","#20242e");ax.appendChild(ln);
    var t=svgEl("text");t.setAttribute("x",4);t.setAttribute("y",y+4);
    t.setAttribute("fill","#9aa3b2");t.setAttribute("font-size","10");
    t.textContent=fmtVal(yv,spec.pct);ax.appendChild(t);}
  for(var f=0;f<=5;f++){
    var mi=Math.round((n-1)*f/5);
    var tx=svgEl("text");tx.setAttribute("x",X(mi));tx.setAttribute("y",H-6);
    tx.setAttribute("fill","#9aa3b2");tx.setAttribute("font-size","10");
    tx.setAttribute("text-anchor","middle");
    tx.textContent="m"+months[mi];ax.appendChild(tx);}
  svg.appendChild(ax);
  function band(loKey,hiKey,fill){
    var pts=[];
    for(var i=0;i<n;i++){pts.push(X(i).toFixed(1)+","+Y(spec.fan[hiKey][i]).toFixed(1));}
    for(var j=n-1;j>=0;j--){pts.push(X(j).toFixed(1)+","+Y(spec.fan[loKey][j]).toFixed(1));}
    var pg=svgEl("polygon");pg.setAttribute("points",pts.join(" "));
    pg.setAttribute("fill",fill);pg.setAttribute("stroke","none");svg.appendChild(pg);}
  band("p5","p95",BAND_OUT);
  band("p25","p75",BAND_IN);
  if(showSamples&&spec.samples){
    spec.samples.forEach(function(p){
      var pts=p.map(function(v,i){return X(i).toFixed(1)+","+Y(v).toFixed(1);}).join(" ");
      var pl=svgEl("polyline");pl.setAttribute("points",pts);pl.setAttribute("fill","none");
      pl.setAttribute("stroke",SAMPLE);pl.setAttribute("stroke-width","0.7");
      pl.setAttribute("opacity","0.55");svg.appendChild(pl);});}
  var med=spec.fan.p50.map(function(v,i){return X(i).toFixed(1)+","+Y(v).toFixed(1);}).join(" ");
  var ml=svgEl("polyline");ml.setAttribute("points",med);ml.setAttribute("fill","none");
  ml.setAttribute("stroke",MEDIAN);ml.setAttribute("stroke-width","2");svg.appendChild(ml);
  var leg=$("leg");
  leg.innerHTML="<span><span class=sw style='background:"+BAND_OUT+"'></span>p5-p95</span>"
    +"<span><span class=sw style='background:"+BAND_IN+"'></span>p25-p75</span>"
    +"<span><span class=sw style='background:"+MEDIAN+"'></span>median</span>"
    +(showSamples&&spec.samples?"<span><span class=sw style='background:"+SAMPLE+"'></span>sample paths</span>":"");}
function currentSpec(){
  var cat=seriesCatalogue(DATA);
  var id=$("series").value||cat[0].id;
  for(var i=0;i<cat.length;i++){if(cat[i].id===id){return cat[i];}}
  return cat[0];}
function redraw(){if(DATA){drawFan(currentSpec(),$("show-samples").checked);}}
function render(d){
  DATA=d;
  if(d.unsigned_note){$("unsigned").style.display="block";$("unsigned").textContent=d.unsigned_note;}
  if(d.inputs_note){$("inputs-note").style.display="block";$("inputs-note").textContent=d.inputs_note;}
  var p=d.parameters;
  $("prov").innerHTML="<b>Provenance</b> &mdash; measure "+d.measure
    +" &middot; seed <span class=mono>"+d.seed+"</span>"
    +" &middot; paths "+d.n_paths
    +" &middot; horizon "+d.horizon_months+"m"
    +" &middot; HW1F(a="+p.mean_reversion_speed+", sigma="+p.short_rate_vol+")"
    +" &middot; GBM(vol="+p.equity_vol+", ERP="+p.equity_risk_premium
    +", rho="+p.rate_equity_correlation+")"
    +" &middot; digest <span class=mono>"+d.inputs_digest.slice(0,12)+"&hellip;</span>";
  var sel=$("series");sel.innerHTML="";
  seriesCatalogue(d).forEach(function(s){
    var o=document.createElement("option");o.value=s.id;o.textContent=s.label;
    sel.appendChild(o);});
  $("csvdir").textContent=d.csv_dir||"";
  $("content").style.display="block";
  redraw();}
function load(){
  $("btn-load").disabled=true;
  $("status").textContent="simulating… (cached when inputs unchanged)";
  fetch("/path-data").then(function(r){return r.json();}).then(function(d){
    $("btn-load").disabled=false;
    if(!d.ok){$("status").textContent="ERROR: "+(d.errors||["unknown"]).join("; ");return;}
    $("status").textContent=(d.cached?"served from cache":"freshly simulated")
      +" · digest "+d.inputs_digest.slice(0,12)+"…";
    render(d);
  }).catch(function(e){
    $("btn-load").disabled=false;
    $("status").textContent="ERROR: "+e;});}
$("btn-load").addEventListener("click",load);
$("series")&&$("series").addEventListener("change",redraw);
$("show-samples").addEventListener("change",redraw);
load();
</script>
</main></body></html>"""
