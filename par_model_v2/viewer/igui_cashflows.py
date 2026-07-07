"""CF-3 - Cash-flow projection GUI page (owner request 2026-07-03).

Serves the CF-track projection set (roadmap 4.0c) in the GUI as TABLES and
CHARTS: yearly liability cash flows by product class x bucket, yearly asset
cash flows and balances by asset class, per-year MONTHLY drill-down, and
self-drawn SVG charts (net-cashflow components; stacked asset balances).
All pages in this GUI are ZERO-EXTERNAL-REFERENCE, so charts are rendered
by inline JS into SVG - no CDN, no chart library.

Data flow: ``GET /cashflow-data`` reads the SAVED ``model_inputs.json``
(portfolio + balance sheet - the same file the input pages write), runs the
CF-1 engine into ``<out_root>/cashflow_set/`` (also refreshing the six wide
CSVs + JSON artifact), and returns compact ``{columns, rows}`` tables.  The
result is CACHED by the CF inputs digest: while portfolio and balance sheet
are unchanged the engine is not re-run.

Discipline: STANDARD LIBRARY ONLY at import time (the engine and pandas are
imported lazily inside the data builder); diagnostic overlay - governed
headline figures untouched; declaration scales UNSIGNED (banner shown).
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

CF_GUI_SCHEMA_VERSION = "cf3-gui-1.1"
CF_SET_DIRNAME = "cashflow_set"


def _table(frame) -> Dict[str, Any]:
    """Compact JSON table: {"columns": [...], "rows": [[...], ...]}."""
    return {"columns": [str(c) for c in frame.columns],
            "rows": [[(round(float(v), 2) if isinstance(v, (int, float))
                       else v) for v in row]
                     for row in frame.itertuples(index=False, name=None)]}


def build_cashflow_response(inputs_path: str, out_root: str) -> Dict[str, Any]:
    """Compute (or serve cached) the projection set, shaped for the page."""
    if not os.path.exists(inputs_path):
        return {"ok": False, "errors": [
            "model_inputs.json not found - save your inputs first "
            "(Run Controls / Model Points pages)"]}
    try:
        with open(inputs_path, encoding="utf-8") as fh:
            mi = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        return {"ok": False, "errors": ["could not parse model_inputs.json: %s" % exc]}
    if not mi.get("portfolio"):
        return {"ok": False, "errors": [
            "no portfolio in the assembled inputs - add model points first"]}
    if not (mi.get("balance_sheet") or {}).get("assets"):
        return {"ok": False, "errors": [
            "no balance-sheet assets in the assembled inputs"]}
    try:
        from par_model_v2.projection.cashflow_projection_set import (
            LIABILITY_BUCKETS, build_cashflow_projection_set, to_wide,
            _inputs_digest)
    except Exception as exc:  # pragma: no cover - engine deps missing
        return {"ok": False, "errors": ["cash-flow engine unavailable: %s" % exc]}

    out_dir = os.path.join(out_root, CF_SET_DIRNAME)
    cache_path = os.path.join(out_dir, "CF_GUI_CACHE.json")
    digest = _inputs_digest(mi)
    if os.path.exists(cache_path):
        try:
            with open(cache_path, encoding="utf-8") as fh:
                cached = json.load(fh)
            if (cached.get("inputs_digest") == digest
                    and cached.get("schema") == CF_GUI_SCHEMA_VERSION):
                cached["cached"] = True
                return cached
        except (OSError, json.JSONDecodeError, ValueError):
            pass  # fall through to recompute

    try:
        res = build_cashflow_projection_set(mi, out_dir=out_dir)
    except Exception as exc:
        return {"ok": False, "errors": ["projection failed: %s" % exc]}
    f = res["frames"]

    # chart series (yearly totals across classes)
    liab_y = f["liability_yearly"]
    benefit_cols = [b for b in LIABILITY_BUCKETS
                    if b not in ("premium", "expense")]
    tot = liab_y.groupby("year", as_index=False).sum(numeric_only=True)
    liab_chart = {
        "years": tot["year"].astype(int).tolist(),
        "premium": tot["premium"].round(2).tolist(),
        "expense": tot["expense"].round(2).tolist(),
        "benefits": tot[benefit_cols].sum(axis=1).round(2).tolist(),
        # GD-1 (owner directive 2026-07-07): guaranteed vs non-guaranteed
        # benefit split surfaced directly in the chart payload. Cash
        # dividends are non-guaranteed by construction (declared scale).
        "guaranteed": tot[[b for b in benefit_cols
                           if b.endswith("_guaranteed")
                           and not b.endswith("_non_guaranteed")]]
        .sum(axis=1).round(2).tolist(),
        "non_guaranteed": tot[[b for b in benefit_cols
                               if b.endswith("_non_guaranteed")
                               or b == "cash_dividend"]]
        .sum(axis=1).round(2).tolist(),
        "net": tot["net_cashflow"].round(2).tolist(),
    }
    bal_y = f["asset_balance_yearly"]
    classes = sorted(bal_y["asset_class"].unique().tolist())
    bal_chart = {
        "years": sorted(bal_y["year"].astype(int).unique().tolist()),
        "classes": classes,
        "series": {c: bal_y[bal_y["asset_class"] == c]
                   .sort_values("year")["market_value"].round(2).tolist()
                   for c in classes},
    }

    payload = {
        "ok": True,
        "schema": CF_GUI_SCHEMA_VERSION,
        "cached": False,
        "inputs_digest": digest,
        "basis": res["basis"],
        "unsigned_note": res["unsigned_note"],
        "horizon": res["horizon"],
        "book_runoff_month": res["totals"].get("book_runoff_month"),
        "asset_shortfall": res["totals"].get("asset_shortfall", 0.0),
        "tables": {
            "liability_yearly": _table(to_wide(liab_y, "product_class", "year")),
            "asset_cf_yearly": _table(to_wide(f["asset_cf_yearly"],
                                              "asset_class", "year")),
            "asset_balance_yearly": _table(to_wide(f["asset_balance_yearly"],
                                                   "asset_class", "year")),
            "liability_monthly": _table(to_wide(f["liability_monthly"],
                                                "product_class", "month")),
            "asset_cf_monthly": _table(to_wide(f["asset_cf_monthly"],
                                               "asset_class", "month")),
            "asset_balance_monthly": _table(to_wide(f["asset_balance_monthly"],
                                                    "asset_class", "month")),
        },
        "charts": {"liability": liab_chart, "balances": bal_chart},
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


def render_cashflows_html() -> str:
    """Self-contained cash-flow projection page (tables + SVG charts)."""
    return """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Cash-flow projections - CF-3</title>
<style>
 body{font:14px/1.5 system-ui,Segoe UI,Arial,sans-serif;margin:0;background:#0f1115;color:#e8eaed}
 main{max-width:1180px;margin:0 auto;padding:24px}
 h1{font-size:20px;margin:0 0 4px} h2{font-size:15px;margin:18px 0 8px;color:#9fb4ff}
 .card{background:#171a21;border:1px solid #262b36;border-radius:10px;padding:16px;margin:12px 0}
 .muted{color:#9aa3b2} .mono{font-family:ui-monospace,Consolas,monospace}
 button,select{font:inherit;padding:6px 12px;border-radius:8px;border:1px solid #2b6cff;background:#2b6cff;color:#fff;cursor:pointer}
 select{background:#0b0d12;border-color:#394150}
 button:disabled{background:#33384a;border-color:#33384a;cursor:not-allowed}
 .tabbar{display:flex;gap:8px;flex-wrap:wrap;margin:8px 0}
 .tabbar button{background:#20242e;border-color:#394150}
 .tabbar button.on{background:#2b6cff;border-color:#2b6cff}
 .tblwrap{overflow:auto;max-height:420px;border:1px solid #20242e;border-radius:8px}
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
</style></head><body><main>
 <h1>Cash-flow projections</h1>
 <div class="muted">CF-3 - liability cash flows by product class &amp; bucket, asset cash flows and
  balances by asset class; deterministic central basis; monthly + yearly to 100 years.
  Computed from your SAVED inputs (<span class="mono">model_inputs.json</span>) and cached until they change.
  <a href="/run-execution" style="color:#9fb4ff">Run page</a> &middot;
  <a href="/history" style="color:#9fb4ff">Run history</a></div>
 <div class="unsigned" id="unsigned" style="display:none"></div>

 <div class="card">
  <button id="btn-load">Compute / refresh projections</button>
  <span class="muted" id="status">(not loaded yet)</span>
 </div>

 <div id="content" style="display:none">
  <div class="card">
   <h2>Liability net cash flow by year (all product classes)</h2>
   <div class="legend" id="leg-liab"></div>
   <svg id="chart-liab" viewBox="0 0 1080 300" preserveAspectRatio="none"></svg>
  </div>
  <div class="card">
   <h2>Asset balances by year (stacked by asset class)</h2>
   <div class="legend" id="leg-bal"></div>
   <svg id="chart-bal" viewBox="0 0 1080 300" preserveAspectRatio="none"></svg>
  </div>
  <div class="card">
   <h2>Tables</h2>
   <div class="tabbar" id="tabs"></div>
   <div style="margin:6px 0">
    <label class="muted">Granularity
     <select id="gran"><option value="yearly">Yearly (1-100)</option>
      <option value="monthly">Monthly (drill into one year)</option></select></label>
    <label class="muted" id="yearpick-wrap" style="display:none">Year
     <select id="yearpick"></select></label>
   </div>
   <div class="tblwrap"><table id="tbl"><thead></thead><tbody></tbody></table></div>
   <p class="muted">CSV copies of every table (monthly + yearly) are written to
    <span class="mono" id="csvdir"></span>.</p>
  </div>
 </div>

<script>
"use strict";
var $=function(id){return document.getElementById(id);};
var DATA=null;
var PALETTE=["#5b8def","#36d399","#f0b429","#f87272","#a78bfa","#4dd4e8","#f472b6","#9ca3af"];
var TABS=[["liability","Liability CFs"],["asset_cf","Asset CFs"],["asset_balance","Asset balances"]];
var curTab="liability";
function fmt(x){return (x==null||x==="")?"":(typeof x==="number"?x.toLocaleString(undefined,{maximumFractionDigits:2}):x);}
function svgEl(name){return document.createElementNS("http://www.w3.org/2000/svg",name);}
function clearSvg(s){while(s.firstChild){s.removeChild(s.firstChild);}}
function niceMax(v){if(v<=0)return 1;var p=Math.pow(10,Math.floor(Math.log(v)/Math.LN10));var n=v/p;return (n<=1?1:n<=2?2:n<=5?5:10)*p;}
function drawAxes(svg,W,H,pad,y0,y1,xlab){
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
  for(var x=0;x<=100;x+=20){
    var xp=pad+(W-2*pad)*x/100;
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
  drawAxes(svg,W,H,pad,lo,hi,"year");
  if(lo<0){var zy=H-pad-(H-2*pad)*(0-lo)/(hi-lo);
    var z=svgEl("line");z.setAttribute("x1",pad);z.setAttribute("x2",W-pad);
    z.setAttribute("y1",zy);z.setAttribute("y2",zy);z.setAttribute("stroke","#394150");svg.appendChild(z);}
  var leg=$(legId);leg.innerHTML="";
  seriesList.forEach(function(s,si){
    var col=PALETTE[si%PALETTE.length];
    var pts=years.map(function(yr,i){
      var x=pad+(W-2*pad)*(yr-1)/(years.length-1);
      var y=H-pad-(H-2*pad)*(s.values[i]-lo)/(hi-lo);
      return x.toFixed(1)+","+y.toFixed(1);}).join(" ");
    var pl=svgEl("polyline");pl.setAttribute("points",pts);pl.setAttribute("fill","none");
    pl.setAttribute("stroke",col);pl.setAttribute("stroke-width","1.8");svg.appendChild(pl);
    leg.innerHTML+="<span><span class=sw style='background:"+col+"'></span>"+s.name+"</span>";});}
function stackedBars(svgId,legId,years,classes,series){
  var svg=$(svgId);clearSvg(svg);
  var W=1080,H=300,pad=44;
  var hi=0;
  years.forEach(function(yr,i){var t=0;classes.forEach(function(c){t+=series[c][i];});if(t>hi)hi=t;});
  hi=niceMax(hi);
  drawAxes(svg,W,H,pad,0,hi,"year");
  var leg=$(legId);leg.innerHTML="";
  classes.forEach(function(c,ci){
    leg.innerHTML+="<span><span class=sw style='background:"+PALETTE[ci%PALETTE.length]+"'></span>"+c+"</span>";});
  var bw=(W-2*pad)/years.length;
  years.forEach(function(yr,i){
    var y=H-pad;
    classes.forEach(function(c,ci){
      var v=series[c][i];var h=(H-2*pad)*v/hi;
      var r=svgEl("rect");r.setAttribute("x",pad+i*bw);r.setAttribute("width",Math.max(bw-0.5,0.5));
      r.setAttribute("y",y-h);r.setAttribute("height",h);
      r.setAttribute("fill",PALETTE[ci%PALETTE.length]);svg.appendChild(r);
      y-=h;});});}
function renderTable(){
  if(!DATA)return;
  var gran=$("gran").value;
  var key=curTab+(gran==="yearly"?"_yearly":"_monthly");
  var t=DATA.tables[key];
  var thead=$("tbl").querySelector("thead");var tbody=$("tbl").querySelector("tbody");
  thead.innerHTML="<tr>"+t.columns.map(function(c){return "<th>"+c+"</th>";}).join("")+"</tr>";
  var rows=t.rows;
  if(gran==="monthly"){
    var yr=parseInt($("yearpick").value||"1",10);
    rows=rows.filter(function(r){return r[0]>=(yr-1)*12+1&&r[0]<=yr*12;});}
  tbody.innerHTML=rows.map(function(r){
    return "<tr>"+r.map(function(v,i){return "<td>"+fmt(v)+"</td>";}).join("")+"</tr>";}).join("");}
function setTab(id){curTab=id;
  $("tabs").querySelectorAll("button").forEach(function(b){
    b.className=(b.getAttribute("data-tab")===id)?"on":"";});
  renderTable();}
function boot(j){
  DATA=j;
  $("content").style.display="block";
  $("unsigned").style.display="block";
  $("unsigned").textContent="UNSIGNED - "+j.unsigned_note;
  $("csvdir").textContent=j.csv_dir;
  $("status").innerHTML="loaded <span class=ok>OK</span>"+(j.cached?" (cached)":"")+
    " - inputs digest <span class=mono>"+String(j.inputs_digest).slice(0,23)+"</span>"+
    (j.book_runoff_month?" - book runs off at month "+j.book_runoff_month+
      " (later balances are surplus compounding)":"")+
    (j.asset_shortfall>0?" - <span class=bad>FUND SHORTFALL "+fmt(j.asset_shortfall)+"</span>":"");
  var lc=j.charts.liability;
  lineChart("chart-liab","leg-liab",lc.years,[
    {name:"Premium inflow",values:lc.premium},
    {name:"Expenses",values:lc.expense},
    {name:"Benefit outgo",values:lc.benefits},
    {name:"Benefits - guaranteed",values:lc.guaranteed||[]},
    {name:"Benefits - non-guaranteed (incl. cash dividend)",values:lc.non_guaranteed||[]},
    {name:"Net cash flow",values:lc.net}]);
  var bc=j.charts.balances;
  stackedBars("chart-bal","leg-bal",bc.years,bc.classes,bc.series);
  var tabs=$("tabs");tabs.innerHTML="";
  TABS.forEach(function(t){
    var b=document.createElement("button");b.textContent=t[1];
    b.setAttribute("data-tab",t[0]);
    b.addEventListener("click",function(){setTab(t[0]);});
    tabs.appendChild(b);});
  var yp=$("yearpick");yp.innerHTML="";
  for(var y=1;y<=100;y++){var o=document.createElement("option");o.value=y;o.textContent=y;yp.appendChild(o);}
  setTab("liability");}
$("gran").addEventListener("change",function(){
  $("yearpick-wrap").style.display=($("gran").value==="monthly")?"":"none";renderTable();});
$("yearpick").addEventListener("change",renderTable);
$("btn-load").addEventListener("click",function(){
  $("btn-load").disabled=true;$("status").textContent="computing (first run takes a few seconds)...";
  fetch("/cashflow-data").then(function(r){return r.json();}).then(function(j){
    $("btn-load").disabled=false;
    if(j&&j.ok){boot(j);}
    else{$("status").innerHTML="<span class=bad>"+((j&&j.errors)||["failed"]).join("; ")+"</span>";}
  }).catch(function(e){$("btn-load").disabled=false;
    $("status").innerHTML="<span class=bad>"+String(e)+"</span>";});});
</script></main></body></html>"""
