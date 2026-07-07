"""GD-2 - Stepwise liability drill-down GUI page (owner directive 2026-07-07).

Serves the GD-2 drill-down set (roadmap 4.0e) in the GUI: pick a MODEL
POINT or a PRODUCT CLASS and inspect the month-by-month build-up -
in-force / death / surrender counts, premium and expense, every benefit
bucket with its guaranteed vs non-guaranteed split, net and cumulative net
cash flow - as an SVG chart plus a yearly table with per-year monthly
drill-down (the CF-3 interaction pattern).

Data flow: ``GET /drilldown-data`` reads the SAVED ``model_inputs.json``,
runs the GD-2 engine into ``<out_root>/drilldown_set/`` (JSON + 2 CSVs),
and returns compact ``{columns, rows}`` tables per selection.  CACHED by
the drill-down inputs digest (portfolio + product catalogue): unchanged
inputs never re-run the engine.

Discipline: STANDARD LIBRARY ONLY at import time (engine + pandas lazy);
ZERO external references in the page (inline JS/SVG only); diagnostic
overlay - governed headline figures untouched; declaration scales UNSIGNED
(banner shown).
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict

DD_GUI_SCHEMA_VERSION = "gd2-gui-1.0"
DD_SET_DIRNAME = "drilldown_set"


def _table(frame) -> Dict[str, Any]:
    """Compact JSON table: {"columns": [...], "rows": [[...], ...]}."""
    return {"columns": [str(c) for c in frame.columns],
            "rows": [[(round(float(v), 2) if isinstance(v, (int, float))
                       else v) for v in row]
                     for row in frame.itertuples(index=False, name=None)]}


def build_drilldown_response(inputs_path: str, out_root: str) -> Dict[str, Any]:
    """Compute (or serve cached) the drill-down set, shaped for the page."""
    if not os.path.exists(inputs_path):
        return {"ok": False, "errors": [
            "model_inputs.json not found - save your inputs first "
            "(Run Controls / Model Points pages)"]}
    try:
        with open(inputs_path, encoding="utf-8") as fh:
            mi = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        return {"ok": False,
                "errors": ["could not parse model_inputs.json: %s" % exc]}
    if not mi.get("portfolio"):
        return {"ok": False, "errors": [
            "no portfolio in the assembled inputs - add model points first"]}
    try:
        from par_model_v2.projection.liability_drilldown import (
            _inputs_digest, build_liability_drilldown, yearly_stepwise)
    except Exception as exc:  # pragma: no cover - engine deps missing
        return {"ok": False,
                "errors": ["drill-down engine unavailable: %s" % exc]}

    out_dir = os.path.join(out_root, DD_SET_DIRNAME)
    cache_path = os.path.join(out_dir, "DD_GUI_CACHE.json")
    digest = _inputs_digest(mi)
    if os.path.exists(cache_path):
        try:
            with open(cache_path, encoding="utf-8") as fh:
                cached = json.load(fh)
            if (cached.get("inputs_digest") == digest
                    and cached.get("schema") == DD_GUI_SCHEMA_VERSION):
                cached["cached"] = True
                return cached
        except (OSError, json.JSONDecodeError, ValueError):
            pass  # fall through to recompute

    try:
        res = build_liability_drilldown(mi, out_dir=out_dir)
    except Exception as exc:
        return {"ok": False, "errors": ["drill-down failed: %s" % exc]}

    tables: Dict[str, Any] = {}
    charts: Dict[str, Any] = {}
    for sel in res["selections"]:
        sid = sel["id"]
        monthly = res["frames"][sid]
        yearly = yearly_stepwise(monthly)
        tables[sid] = {"yearly": _table(yearly),
                       "monthly": _table(monthly)}
        charts[sid] = {
            "years": yearly["year"].astype(int).tolist(),
            "premium": yearly["premium"].round(2).tolist(),
            "expense": yearly["expense"].round(2).tolist(),
            "guaranteed": yearly["benefit_guaranteed"].round(2).tolist(),
            "non_guaranteed":
                yearly["benefit_non_guaranteed"].round(2).tolist(),
            "net": yearly["net_cashflow"].round(2).tolist(),
        }
    payload = {
        "ok": True,
        "schema": DD_GUI_SCHEMA_VERSION,
        "cached": False,
        "inputs_digest": digest,
        "basis": res["basis"],
        "unsigned_note": res["unsigned_note"],
        "horizon": res["horizon"],
        "selections": res["selections"],
        "totals": res["totals"],
        "tables": tables,
        "charts": charts,
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


def render_drilldown_html() -> str:
    """Self-contained stepwise drill-down page (selector + SVG + tables)."""
    return """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Liability drill-down - GD-2</title>
<style>
 body{font:14px/1.5 system-ui,Segoe UI,Arial,sans-serif;margin:0;background:#0f1115;color:#e8eaed}
 main{max-width:1180px;margin:0 auto;padding:24px}
 h1{font-size:20px;margin:0 0 4px} h2{font-size:15px;margin:18px 0 8px;color:#9fb4ff}
 .card{background:#171a21;border:1px solid #262b36;border-radius:10px;padding:16px;margin:12px 0}
 .muted{color:#9aa3b2} .mono{font-family:ui-monospace,Consolas,monospace}
 button,select{font:inherit;padding:6px 12px;border-radius:8px;border:1px solid #2b6cff;background:#2b6cff;color:#fff;cursor:pointer}
 select{background:#0b0d12;border-color:#394150;max-width:640px}
 button:disabled{background:#33384a;border-color:#33384a;cursor:not-allowed}
 .tblwrap{overflow:auto;max-height:460px;border:1px solid #20242e;border-radius:8px}
 table{border-collapse:collapse;width:100%;font-size:12.5px}
 th,td{border-bottom:1px solid #262b36;padding:4px 8px;text-align:right;white-space:nowrap}
 th{position:sticky;top:0;background:#171a21;color:#9fb4ff}
 th:first-child,td:first-child{text-align:left;position:sticky;left:0;background:#171a21}
 .unsigned{background:#3a2b12;border:1px solid #8a6d1a;color:#ffd166;border-radius:10px;padding:10px 14px;margin:10px 0;font-weight:600}
 .legend{display:flex;gap:14px;flex-wrap:wrap;margin:6px 0;font-size:12.5px}
 .legend span{display:inline-flex;align-items:center;gap:5px}
 .sw{width:12px;height:12px;border-radius:3px;display:inline-block}
 svg{width:100%;height:auto;background:#0b0d12;border:1px solid #20242e;border-radius:8px}
 .bad{color:#f87272} .ok{color:#36d399}
 .kpi{display:inline-block;margin:2px 14px 2px 0}
 .kpi b{color:#9fb4ff;font-weight:600}
</style></head><body><main>
 <h1>Stepwise liability drill-down</h1>
 <div class="muted">GD-2 - pick a model point or product class and inspect the month-by-month
  premium / expense / benefit build-up, incl. in-force &amp; decrement counts and the
  guaranteed vs non-guaranteed split. Same engine as the
  <a href="/cashflows" style="color:#9fb4ff">Cash flows</a> page (CF-1 projectors),
  so class totals reconcile exactly. Computed from your SAVED inputs and cached until they change.</div>
 <div class="unsigned" id="unsigned" style="display:none"></div>

 <div class="card">
  <button id="btn-load">Compute / refresh drill-down</button>
  <span class="muted" id="status">(not loaded yet)</span>
 </div>

 <div id="content" style="display:none">
  <div class="card">
   <label class="muted">Selection
    <select id="sel-pick"></select></label>
   <div id="kpis" style="margin-top:8px"></div>
  </div>
  <div class="card">
   <h2>Yearly build-up (selected model point / class)</h2>
   <div class="legend" id="leg-dd"></div>
   <svg id="chart-dd" viewBox="0 0 1080 300" preserveAspectRatio="none"></svg>
  </div>
  <div class="card">
   <h2>Stepwise table</h2>
   <div style="margin:6px 0">
    <label class="muted">Granularity
     <select id="gran"><option value="yearly">Yearly (1-100)</option>
      <option value="monthly">Monthly (drill into one year)</option></select></label>
    <label class="muted" id="yearpick-wrap" style="display:none">Year
     <select id="yearpick"></select></label>
   </div>
   <div class="tblwrap"><table id="tbl"><thead></thead><tbody></tbody></table></div>
   <p class="muted">CSV copies (monthly + yearly, all selections) are written to
    <span class="mono" id="csvdir"></span>.</p>
  </div>
 </div>

<script>
"use strict";
var $=function(id){return document.getElementById(id);};
var DATA=null;
var PALETTE=["#5b8def","#f0b429","#36d399","#f87272","#a78bfa","#4dd4e8"];
function fmt(x){return (x==null||x==="")?"":(typeof x==="number"?x.toLocaleString(undefined,{maximumFractionDigits:2}):x);}
function svgEl(name){return document.createElementNS("http://www.w3.org/2000/svg",name);}
function clearSvg(s){while(s.firstChild){s.removeChild(s.firstChild);}}
function niceMax(v){if(v<=0)return 1;var p=Math.pow(10,Math.floor(Math.log(v)/Math.LN10));var n=v/p;return (n<=1?1:n<=2?2:n<=5?5:10)*p;}
function drawAxes(svg,W,H,pad,y0,y1,nYears){
  var ax=svgEl("g");
  for(var i=0;i<=4;i++){
    var yv=y0+(y1-y0)*i/4, y=H-pad-(H-2*pad)*i/4;
    var ln=svgEl("line");ln.setAttribute("x1",pad);ln.setAttribute("x2",W-pad);
    ln.setAttribute("y1",y);ln.setAttribute("y2",y);
    ln.setAttribute("stroke","#20242e");ax.appendChild(ln);
    var t=svgEl("text");t.setAttribute("x",4);t.setAttribute("y",y+4);
    t.setAttribute("fill","#9aa3b2");t.setAttribute("font-size","10");
    t.textContent=Math.abs(yv)>=1e6?(yv/1e6).toFixed(1)+"M":yv.toFixed(0);
    ax.appendChild(t);}
  for(var x=0;x<=nYears;x+=Math.max(Math.round(nYears/5),1)){
    var xp=pad+(W-2*pad)*x/nYears;
    var tx=svgEl("text");tx.setAttribute("x",xp);tx.setAttribute("y",H-4);
    tx.setAttribute("fill","#9aa3b2");tx.setAttribute("font-size","10");
    tx.setAttribute("text-anchor","middle");tx.textContent="y"+x;ax.appendChild(tx);}
  svg.appendChild(ax);}
function lineChart(svgId,legId,years,seriesList){
  var svg=$(svgId);clearSvg(svg);
  var W=1080,H=300,pad=44;
  var lo=0,hi=0;
  seriesList.forEach(function(s){s.values.forEach(function(v){if(v<lo)lo=v;if(v>hi)hi=v;});});
  hi=niceMax(hi);lo=(lo<0)?-niceMax(-lo):0;
  drawAxes(svg,W,H,pad,lo,hi,years.length);
  if(lo<0){var zy=H-pad-(H-2*pad)*(0-lo)/(hi-lo);
    var z=svgEl("line");z.setAttribute("x1",pad);z.setAttribute("x2",W-pad);
    z.setAttribute("y1",zy);z.setAttribute("y2",zy);z.setAttribute("stroke","#394150");svg.appendChild(z);}
  var leg=$(legId);leg.innerHTML="";
  seriesList.forEach(function(s,si){
    var col=PALETTE[si%PALETTE.length];
    var pts=years.map(function(yr,i){
      var x=pad+(W-2*pad)*(yr-1)/Math.max(years.length-1,1);
      var y=H-pad-(H-2*pad)*(s.values[i]-lo)/(hi-lo);
      return x.toFixed(1)+","+y.toFixed(1);}).join(" ");
    var pl=svgEl("polyline");pl.setAttribute("points",pts);pl.setAttribute("fill","none");
    pl.setAttribute("stroke",col);pl.setAttribute("stroke-width","1.8");svg.appendChild(pl);
    leg.innerHTML+="<span><span class=sw style='background:"+col+"'></span>"+s.name+"</span>";});}
function curSel(){return $("sel-pick").value;}
function renderChart(){
  if(!DATA)return;
  var c=DATA.charts[curSel()];
  if(!c)return;
  lineChart("chart-dd","leg-dd",c.years,[
    {name:"Premium inflow",values:c.premium},
    {name:"Expenses",values:c.expense},
    {name:"Benefits - guaranteed",values:c.guaranteed},
    {name:"Benefits - non-guaranteed (incl. cash dividend)",values:c.non_guaranteed},
    {name:"Net cash flow",values:c.net}]);}
function renderKpis(){
  if(!DATA)return;
  var t=DATA.totals[curSel()];
  if(!t)return;
  $("kpis").innerHTML=
    "<span class=kpi><b>Premium</b> "+fmt(t.premium)+"</span>"+
    "<span class=kpi><b>Expense</b> "+fmt(t.expense)+"</span>"+
    "<span class=kpi><b>Gtd benefits</b> "+fmt(t.benefit_guaranteed)+"</span>"+
    "<span class=kpi><b>Non-gtd benefits</b> "+fmt(t.benefit_non_guaranteed)+"</span>"+
    "<span class=kpi><b>Lifetime net CF</b> "+fmt(t.net_cashflow)+"</span>";}
function renderTable(){
  if(!DATA)return;
  var gran=$("gran").value;
  var t=DATA.tables[curSel()];
  if(!t)return;
  var tab=(gran==="yearly")?t.yearly:t.monthly;
  var thead=$("tbl").querySelector("thead");var tbody=$("tbl").querySelector("tbody");
  thead.innerHTML="<tr>"+tab.columns.map(function(c){return "<th>"+c+"</th>";}).join("")+"</tr>";
  var rows=tab.rows;
  if(gran==="monthly"){
    var yr=parseInt($("yearpick").value||"1",10);
    rows=rows.filter(function(r){return r[0]>=(yr-1)*12+1&&r[0]<=yr*12;});}
  tbody.innerHTML=rows.map(function(r){
    return "<tr>"+r.map(function(v){return "<td>"+fmt(v)+"</td>";}).join("")+"</tr>";}).join("");}
function renderAll(){renderKpis();renderChart();renderTable();}
function boot(j){
  DATA=j;
  $("content").style.display="block";
  $("unsigned").style.display="block";
  $("unsigned").textContent="UNSIGNED - "+j.unsigned_note;
  $("csvdir").textContent=j.csv_dir;
  $("status").innerHTML="loaded <span class=ok>OK</span>"+(j.cached?" (cached)":"")+
    " - "+j.selections.length+" selections - inputs digest <span class=mono>"+
    String(j.inputs_digest).slice(0,23)+"</span>";
  var sp=$("sel-pick");sp.innerHTML="";
  j.selections.forEach(function(s){
    var o=document.createElement("option");o.value=s.id;
    o.textContent=(s.kind==="product_class"?"[CLASS] ":"")+s.label;
    sp.appendChild(o);});
  var yp=$("yearpick");yp.innerHTML="";
  for(var y=1;y<=100;y++){var o=document.createElement("option");o.value=y;o.textContent=y;yp.appendChild(o);}
  renderAll();}
$("sel-pick").addEventListener("change",renderAll);
$("gran").addEventListener("change",function(){
  $("yearpick-wrap").style.display=($("gran").value==="monthly")?"":"none";renderTable();});
$("yearpick").addEventListener("change",renderTable);
$("btn-load").addEventListener("click",function(){
  $("btn-load").disabled=true;$("status").textContent="computing (first run takes a few seconds)...";
  fetch("/drilldown-data").then(function(r){return r.json();}).then(function(j){
    $("btn-load").disabled=false;
    if(j&&j.ok){boot(j);}
    else{$("status").innerHTML="<span class=bad>"+((j&&j.errors)||["failed"]).join("; ")+"</span>";}
  }).catch(function(e){$("btn-load").disabled=false;
    $("status").innerHTML="<span class=bad>"+String(e)+"</span>";});});
</script></main></body></html>"""
