"""GD-3 - Stepwise run-result decomposition GUI page (owner directive
2026-07-07).

Serves the GD-3 decomposition set (roadmap 4.0e) in the GUI: a calculation
WATERFALL of the executed run's headline build-up - the seven standalone
driver SCRs stacking to their sum, the var-covar diversification credit,
the copula tail-dependence adjustment, and the nested interaction residual
landing on the headline nested SCR - plus the per-driver table, the copula
candidate comparison (AIC selection evidence), and the tail-convergence
path.

Data flow: ``GET /decomposition-data`` reads the run artifact
``<out_root>/RUN_MODEL_AGGREGATION_REPORT.json`` (written by every GUI
run), runs the GD-3 engine into ``<out_root>/decomposition_set/`` (JSON +
4 CSVs), and returns the decomposition. CACHED by the sha256 of the
artifact bytes: an unchanged run never re-derives the set.

Discipline: STANDARD LIBRARY ONLY (the GD-3 engine itself is stdlib-only);
ZERO external references in the page (inline JS/SVG only); READ-ONLY
diagnostic overlay - the run artifact and governed headline figures are
never modified.
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict

DECOMP_GUI_SCHEMA_VERSION = "gd3-gui-1.0"
DECOMP_SET_DIRNAME = "decomposition_set"


def build_decomposition_response(out_root: str) -> Dict[str, Any]:
    """Compute (or serve cached) the decomposition set for the GUI."""
    from par_model_v2.projection.run_result_decomposition import (
        AGG_REPORT_NAME, artifact_digest, build_run_decomposition)

    report_path = os.path.join(out_root, AGG_REPORT_NAME)
    if not os.path.exists(report_path):
        return {"ok": False, "errors": [
            "no run artifact found (%s) - execute a run first "
            "(Run Controls: Save & RUN, or the Run page)" % AGG_REPORT_NAME]}

    out_dir = os.path.join(out_root, DECOMP_SET_DIRNAME)
    cache_path = os.path.join(out_dir, "DECOMP_GUI_CACHE.json")
    try:
        digest = artifact_digest(report_path)
    except OSError as exc:
        return {"ok": False, "errors": ["cannot read run artifact: %s" % exc]}
    if os.path.exists(cache_path):
        try:
            with open(cache_path, encoding="utf-8") as fh:
                cached = json.load(fh)
            if (cached.get("source_digest") == digest
                    and cached.get("gui_schema") == DECOMP_GUI_SCHEMA_VERSION):
                cached["cached"] = True
                return cached
        except (OSError, json.JSONDecodeError, ValueError):
            pass  # fall through to recompute

    try:
        res = build_run_decomposition(report_path, out_dir=out_dir)
    except Exception as exc:
        return {"ok": False, "errors": ["decomposition failed: %s" % exc]}

    payload = dict(res)
    payload["gui_schema"] = DECOMP_GUI_SCHEMA_VERSION
    payload["cached"] = False
    payload["csv_dir"] = out_dir
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


def render_decomposition_html() -> str:
    """Self-contained run-result decomposition page (waterfall + tables)."""
    return """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Run decomposition - GD-3</title>
<style>
 body{font:14px/1.5 system-ui,Segoe UI,Arial,sans-serif;margin:0;background:#0f1115;color:#e8eaed}
 main{max-width:1180px;margin:0 auto;padding:24px}
 h1{font-size:20px;margin:0 0 4px} h2{font-size:15px;margin:18px 0 8px;color:#9fb4ff}
 .card{background:#171a21;border:1px solid #262b36;border-radius:10px;padding:16px;margin:12px 0}
 .muted{color:#9aa3b2} .mono{font-family:ui-monospace,Consolas,monospace}
 button{font:inherit;padding:6px 12px;border-radius:8px;border:1px solid #2b6cff;background:#2b6cff;color:#fff;cursor:pointer}
 button:disabled{background:#33384a;border-color:#33384a;cursor:not-allowed}
 .tblwrap{overflow:auto;max-height:420px;border:1px solid #20242e;border-radius:8px}
 table{border-collapse:collapse;width:100%;font-size:12.5px}
 th,td{border-bottom:1px solid #262b36;padding:4px 8px;text-align:right;white-space:nowrap}
 th{position:sticky;top:0;background:#171a21;color:#9fb4ff}
 th:first-child,td:first-child{text-align:left}
 .unsigned{background:#3a2b12;border:1px solid #8a6d1a;color:#ffd166;border-radius:10px;padding:10px 14px;margin:10px 0;font-weight:600}
 .legend{display:flex;gap:14px;flex-wrap:wrap;margin:6px 0;font-size:12.5px}
 .legend span{display:inline-flex;align-items:center;gap:5px}
 .sw{width:12px;height:12px;border-radius:3px;display:inline-block}
 svg{width:100%;height:auto;background:#0b0d12;border:1px solid #20242e;border-radius:8px}
 .bad{color:#f87272} .ok{color:#36d399}
 .kpi{display:inline-block;margin:2px 14px 2px 0}
 .kpi b{color:#9fb4ff;font-weight:600}
 .selrow{background:#12203a}
</style></head><body><main>
 <h1>Stepwise run-result decomposition</h1>
 <div class="muted">GD-3 - the calculation waterfall behind your run's headline: seven standalone
  driver SCRs &rarr; sum &rarr; var-covar diversification credit &rarr; copula tail-dependence
  adjustment &rarr; nested interaction residual &rarr; headline nested SCR. Every figure is read
  bit-for-bit from the run artifact (<span class="mono">RUN_MODEL_AGGREGATION_REPORT.json</span>);
  nothing is recomputed. Cached until you execute a new run.</div>
 <div class="unsigned" id="unsigned" style="display:none"></div>

 <div class="card">
  <button id="btn-load">Load / refresh decomposition</button>
  <span class="muted" id="status">(not loaded yet)</span>
 </div>

 <div id="content" style="display:none">
  <div class="card">
   <h2>Run provenance</h2>
   <div id="prov" class="muted"></div>
   <div id="kpis" style="margin-top:8px"></div>
  </div>
  <div class="card">
   <h2>SCR build-up waterfall</h2>
   <div class="legend" id="leg-wf"></div>
   <svg id="chart-wf" viewBox="0 0 1080 360" preserveAspectRatio="none"></svg>
   <div class="tblwrap" style="margin-top:10px"><table id="tbl-wf"><thead></thead><tbody></tbody></table></div>
  </div>
  <div class="card">
   <h2>Standalone driver SCRs</h2>
   <div class="tblwrap"><table id="tbl-drv"><thead></thead><tbody></tbody></table></div>
  </div>
  <div class="card">
   <h2>Copula candidates (AIC selection evidence)</h2>
   <div class="tblwrap"><table id="tbl-cop"><thead></thead><tbody></tbody></table></div>
  </div>
  <div class="card">
   <h2>Tail convergence (copula simulation VaR / ES by n_sim)</h2>
   <div class="legend" id="leg-cv"></div>
   <svg id="chart-cv" viewBox="0 0 1080 260" preserveAspectRatio="none"></svg>
   <div class="muted" id="cv-note"></div>
  </div>
  <p class="muted">CSV copies (waterfall, drivers, copulas, convergence) are written to
   <span class="mono" id="csvdir"></span>.</p>
 </div>

<script>
"use strict";
var $=function(id){return document.getElementById(id);};
var DATA=null;
var COL={build:"#5b8def",subtotal:"#9aa3b2",deltaneg:"#36d399",deltapos:"#f0b429",final:"#a78bfa"};
function fmt(x){return (x==null||x==="")?"":(typeof x==="number"?x.toLocaleString(undefined,{maximumFractionDigits:1}):String(x));}
function pct(x){return (x==null)?"":(100*x).toFixed(2)+"%";}
function svgEl(name){return document.createElementNS("http://www.w3.org/2000/svg",name);}
function clearSvg(s){while(s.firstChild){s.removeChild(s.firstChild);}}
function niceMax(v){if(v<=0)return 1;var p=Math.pow(10,Math.floor(Math.log(v)/Math.LN10));var n=v/p;return (n<=1?1:n<=2?2:n<=5?5:10)*p;}
function gridLines(svg,W,H,pad,hi){
  for(var i=0;i<=4;i++){
    var yv=hi*i/4, y=H-pad-(H-2*pad)*i/4;
    var ln=svgEl("line");ln.setAttribute("x1",pad);ln.setAttribute("x2",W-pad);
    ln.setAttribute("y1",y);ln.setAttribute("y2",y);
    ln.setAttribute("stroke","#20242e");svg.appendChild(ln);
    var t=svgEl("text");t.setAttribute("x",4);t.setAttribute("y",y+4);
    t.setAttribute("fill","#9aa3b2");t.setAttribute("font-size","10");
    t.textContent=Math.abs(yv)>=1e6?(yv/1e6).toFixed(1)+"M":yv.toFixed(0);
    svg.appendChild(t);}}
function waterfall(){
  var svg=$("chart-wf");clearSvg(svg);
  var steps=DATA.waterfall;
  var W=1080,H=360,pad=46;
  var hi=0;
  steps.forEach(function(s){var top=Math.max(s.cumulative,s.cumulative-s.value);if(top>hi)hi=top;});
  hi=niceMax(hi);
  gridLines(svg,W,H,pad,hi);
  var n=steps.length, slot=(W-2*pad)/n, bw=Math.min(slot*0.62,70);
  steps.forEach(function(s,i){
    var y0,y1,color;
    if(s.kind==="build"){y0=s.cumulative-s.value;y1=s.cumulative;color=COL.build;}
    else if(s.kind==="delta"){y0=Math.min(s.cumulative,s.cumulative-s.value);
      y1=Math.max(s.cumulative,s.cumulative-s.value);
      color=(s.value<0)?COL.deltaneg:COL.deltapos;}
    else{y0=0;y1=s.cumulative;color=(s.kind==="final")?COL.final:COL.subtotal;}
    var x=pad+slot*i+(slot-bw)/2;
    var yTop=H-pad-(H-2*pad)*y1/hi;
    var hpx=Math.max((H-2*pad)*(y1-y0)/hi,1.5);
    var r=svgEl("rect");
    r.setAttribute("x",x);r.setAttribute("y",yTop);
    r.setAttribute("width",bw);r.setAttribute("height",hpx);
    r.setAttribute("fill",color);
    r.setAttribute("fill-opacity",(s.kind==="subtotal")?"0.45":"0.9");
    var tt=svgEl("title");
    tt.textContent=s.label+": "+fmt(s.value)+" (cumulative "+fmt(s.cumulative)+")";
    r.appendChild(tt);svg.appendChild(r);
    if(s.kind!=="subtotal"&&i+1<n){
      var cn=svgEl("line");var yc=H-pad-(H-2*pad)*s.cumulative/hi;
      cn.setAttribute("x1",x+bw);cn.setAttribute("x2",pad+slot*(i+1)+(slot-bw)/2);
      cn.setAttribute("y1",yc);cn.setAttribute("y2",yc);
      cn.setAttribute("stroke","#394150");cn.setAttribute("stroke-dasharray","3,3");
      svg.appendChild(cn);}
    var lbl=svgEl("text");
    lbl.setAttribute("x",x+bw/2);lbl.setAttribute("y",H-6);
    lbl.setAttribute("fill","#9aa3b2");lbl.setAttribute("font-size","9");
    lbl.setAttribute("text-anchor","end");
    lbl.setAttribute("transform","rotate(-28 "+(x+bw/2)+" "+(H-6)+")");
    lbl.textContent=s.label.length>26?s.label.slice(0,25)+"…":s.label;
    svg.appendChild(lbl);});
  $("leg-wf").innerHTML=
    "<span><span class=sw style='background:"+COL.build+"'></span>Standalone driver SCR</span>"+
    "<span><span class=sw style='background:"+COL.deltaneg+"'></span>Diversification credit</span>"+
    "<span><span class=sw style='background:"+COL.deltapos+"'></span>Aggregation uplift</span>"+
    "<span><span class=sw style='background:"+COL.subtotal+"'></span>Subtotal</span>"+
    "<span><span class=sw style='background:"+COL.final+"'></span>Headline nested SCR</span>";}
function convChart(){
  var svg=$("chart-cv");clearSvg(svg);
  var cv=DATA.convergence||{};
  if(cv.skipped||!(cv.n_sim_grid||[]).length){
    $("cv-note").textContent="Tail diagnostics were skipped for this run (smoke mode).";return;}
  var W=1080,H=260,pad=46;
  var series=[{name:"VaR",values:cv.var_path,col:"#5b8def"},
              {name:"ES",values:cv.es_path,col:"#f0b429"}];
  var hi=0;series.forEach(function(s){(s.values||[]).forEach(function(v){if(v>hi)hi=v;});});
  hi=niceMax(hi);gridLines(svg,W,H,pad,hi);
  var grid=cv.n_sim_grid,leg=$("leg-cv");leg.innerHTML="";
  series.forEach(function(s){
    if(!(s.values||[]).length)return;
    var pts=s.values.map(function(v,i){
      var x=pad+(W-2*pad)*i/Math.max(grid.length-1,1);
      var y=H-pad-(H-2*pad)*v/hi;return x.toFixed(1)+","+y.toFixed(1);}).join(" ");
    var pl=svgEl("polyline");pl.setAttribute("points",pts);pl.setAttribute("fill","none");
    pl.setAttribute("stroke",s.col);pl.setAttribute("stroke-width","1.8");svg.appendChild(pl);
    leg.innerHTML+="<span><span class=sw style='background:"+s.col+"'></span>"+s.name+"</span>";});
  grid.forEach(function(g,i){
    var x=pad+(W-2*pad)*i/Math.max(grid.length-1,1);
    var t=svgEl("text");t.setAttribute("x",x);t.setAttribute("y",H-4);
    t.setAttribute("fill","#9aa3b2");t.setAttribute("font-size","10");
    t.setAttribute("text-anchor","middle");t.textContent=g.toLocaleString();
    svg.appendChild(t);});
  var note="converged: "+String(cv.converged)+" (tolerance "+String(cv.convergence_tolerance)+")";
  var bs=DATA.bootstrap_ci||{};
  if(bs.var_ci){note+=" - bootstrap VaR CI ["+fmt(bs.var_ci[0])+", "+fmt(bs.var_ci[1])+"] over "+String(bs.n_bootstrap)+" resamples";}
  $("cv-note").textContent=note;}
function fillTable(id,cols,rows,selIdx){
  var thead=$(id).querySelector("thead"),tbody=$(id).querySelector("tbody");
  thead.innerHTML="<tr>"+cols.map(function(c){return "<th>"+c+"</th>";}).join("")+"</tr>";
  tbody.innerHTML=rows.map(function(r){
    var cls=(selIdx!=null&&r[selIdx]===true)?" class=selrow":"";
    return "<tr"+cls+">"+r.map(function(v){
      return "<td>"+(v===true?"SELECTED":(v===false?"":fmt(v)))+"</td>";}).join("")+"</tr>";}).join("");}
function boot(j){
  DATA=j;
  $("content").style.display="block";
  $("unsigned").style.display="block";
  $("unsigned").textContent="UNSIGNED - "+j.unsigned_note;
  $("csvdir").textContent=j.csv_dir||"";
  $("status").innerHTML="loaded <span class=ok>OK</span>"+(j.cached?" (cached)":"")+
    " - artifact digest <span class=mono>"+String(j.source_digest).slice(0,23)+"</span>";
  var p=j.provenance||{};
  $("prov").innerHTML="run <span class=mono>"+fmt(p.run_timestamp)+"</span>"+
    " - label <span class=mono>"+fmt(p.output_label)+"</span>"+
    " - inputs "+fmt(p.inputs)+" - seed "+fmt(p.seed)+
    " - confidence "+fmt(p.confidence_level)+" - verdict <b>"+fmt(p.verdict)+"</b>";
  var h=j.headline||{};
  $("kpis").innerHTML=
    "<span class=kpi><b>Nested SCR</b> "+fmt(h.nested_scr)+"</span>"+
    "<span class=kpi><b>Copula SCR ("+fmt(h.copula_selected)+")</b> "+fmt(h.copula_scr)+"</span>"+
    "<span class=kpi><b>Var-covar SCR</b> "+fmt(h.var_covar_scr)+"</span>"+
    "<span class=kpi><b>Standalone sum</b> "+fmt(h.standalone_scr_sum)+"</span>"+
    "<span class=kpi><b>ESG understatement</b> "+pct(h.esg_understatement_pct)+"</span>";
  waterfall();
  fillTable("tbl-wf",["step","kind","label","value","cumulative"],
    j.waterfall.map(function(s,i){return [i+1,s.kind,s.label,s.value,s.cumulative];}));
  fillTable("tbl-drv",["driver","standalone SCR","share of sum"],
    (j.drivers||[]).map(function(d){return [d.driver,d.standalone_scr,d.share_of_sum_pct.toFixed(2)+"%"];}));
  fillTable("tbl-cop",["copula","n_params","loglik","AIC","upper tail dep","selected"],
    (j.copulas||[]).map(function(c){return [c.name,c.n_params,c.loglik,c.aic,c.upper_tail_dependence,c.selected];}),5);
  convChart();}
$("btn-load").addEventListener("click",function(){
  $("btn-load").disabled=true;$("status").textContent="loading...";
  fetch("/decomposition-data").then(function(r){return r.json();}).then(function(j){
    $("btn-load").disabled=false;
    if(j&&j.ok){boot(j);}
    else{$("status").innerHTML="<span class=bad>"+((j&&j.errors)||["failed"]).join("; ")+"</span>";}
  }).catch(function(e){$("btn-load").disabled=false;
    $("status").innerHTML="<span class=bad>"+String(e)+"</span>";});});
</script></main></body></html>"""
