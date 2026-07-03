"""PC-1 GUI - Portfolio construction page (owner directive 2026-07-03).

``/portfolio`` lets the user CONSTRUCT the insurance portfolio inputs:

  * ASSET STRATEGY - asset classes with a TYPE (bond / equity / cash),
    per-class parameters, and SAA weights (must sum to 100%); the balance
    sheet is DERIVED from the SAA and the total book value;
  * PRODUCT CATALOGUE - product templates over the governed mechanic
    families (e.g. short-term vs long-term par products with different
    dividend / bonus scales and term ranges);
  * PORTFOLIO COMPOSER - model-point rows that reference catalogue
    products.

Saving validates all three blocks (fail-loud), derives the balance sheet,
re-validates the derived ``{portfolio, balance_sheet}`` through the SAME
governed loader validator the run gate uses, and merge-writes
``model_inputs.json``.  The gate is then re-established on the Run Gate
page (digest binds to the new bytes) - the construction layer is ADDITIVE
and never bypasses governance.  Catalogue rates are UNSIGNED scenario
inputs pending Model Owner approval.

STANDARD LIBRARY ONLY at import time.
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

from par_model_v2.projection.portfolio_construction import (
    ASSET_KINDS,
    PC_SCHEMA_VERSION,
    PRODUCT_FAMILIES,
    default_asset_strategy,
    default_product_catalogue,
    derive_balance_sheet,
    resolve_portfolio,
    validate_asset_strategy,
    validate_composed_portfolio,
    validate_product_catalogue,
)


def _read_model_inputs(out_path: str) -> Dict[str, Any]:
    if out_path and os.path.exists(out_path):
        try:
            with open(out_path, encoding="utf-8") as fh:
                return json.load(fh) or {}
        except (OSError, json.JSONDecodeError):
            return {}
    return {}


def default_composed_portfolio() -> List[Dict[str, Any]]:
    """Example composed book (editable): short CD + long CD + long RB + GMMB."""
    return [
        {"product_id": "PAR_CD_SHORT", "issue_age": 40, "gender": "M",
         "term_years": 10, "sum_assured": 80000, "annual_premium": 6000,
         "policy_count": 800, "vested_bonus": 0},
        {"product_id": "PAR_CD_LONG", "issue_age": 45, "gender": "M",
         "term_years": 20, "sum_assured": 100000, "annual_premium": 5000,
         "policy_count": 1000, "vested_bonus": 0},
        {"product_id": "PAR_RB_LONG", "issue_age": 40, "gender": "F",
         "term_years": 25, "sum_assured": 250000, "annual_premium": 9000,
         "policy_count": 500, "vested_bonus": 1200},
        {"product_id": "GMMB_STD", "issue_age": 50, "gender": "M",
         "term_years": 15, "sum_assured": 300000, "annual_premium": 12000,
         "policy_count": 250, "vested_bonus": 0},
    ]


def build_construction_defaults(out_path: str) -> Dict[str, Any]:
    """Saved blocks when present, else the editable starter defaults."""
    mi = _read_model_inputs(out_path)
    return {
        "ok": True,
        "schema": PC_SCHEMA_VERSION,
        "asset_strategy": (mi.get("asset_strategy")
                           or default_asset_strategy()),
        "product_catalogue": (mi.get("product_catalogue")
                              or default_product_catalogue()),
        "portfolio": ([r for r in (mi.get("portfolio") or [])
                       if r.get("product_id")]
                      or default_composed_portfolio()),
        "families": {k: {"label": v["label"],
                         "params": {p: sp["default"]
                                    for p, sp in v["params"].items()}}
                     for k, v in PRODUCT_FAMILIES.items()},
        "asset_kinds": ASSET_KINDS,
    }


def build_construction_response(payload: Dict[str, Any], out_path: str,
                                do_write: bool = False) -> Dict[str, Any]:
    """Validate (and optionally save) the full construction payload."""
    payload = payload or {}
    strategy = payload.get("asset_strategy")
    catalogue = payload.get("product_catalogue")
    rows = payload.get("portfolio")
    errors = (validate_asset_strategy(strategy)
              + validate_product_catalogue(catalogue)
              + (validate_composed_portfolio(rows, catalogue)
                 if not isinstance(catalogue, list) or catalogue else []))
    if isinstance(catalogue, list) and catalogue:
        errors += []
    if errors:
        return {"ok": False, "errors": errors}

    mi = _read_model_inputs(out_path)
    derived_bs = derive_balance_sheet(strategy, mi.get("balance_sheet"))
    resolved = resolve_portfolio(rows, catalogue)
    loader_rows = []
    for r in resolved:
        lr = {k: v for k, v in r.items() if k != "mechanics"}
        loader_rows.append(lr)

    # governed-loader re-validation: the derived blocks must satisfy the
    # SAME rules the run gate enforces
    try:
        import load_user_inputs as loader  # scripts/ on sys.path (run_gui)
        loader_errors = loader.validate_portfolio_dict(
            {"portfolio": loader_rows, "balance_sheet": derived_bs})
    except Exception as exc:  # pragma: no cover
        loader_errors = ["loader unavailable for re-validation: %s" % exc]
    if loader_errors:
        return {"ok": False,
                "errors": ["derived inputs failed the governed loader:"]
                + loader_errors}

    result = {
        "ok": True,
        "schema": PC_SCHEMA_VERSION,
        "unsigned_note": ("Catalogue rates and SAA parameters are scenario "
                          "inputs - UNSIGNED pending Model Owner approval."),
        "derived_balance_sheet": derived_bs,
        "n_portfolio_rows": len(loader_rows),
        "product_classes": sorted({str(r.get("product_id")
                                       or r.get("product_type"))
                                   for r in loader_rows}),
    }
    if do_write:
        mi["asset_strategy"] = strategy
        mi["product_catalogue"] = catalogue
        mi["portfolio"] = loader_rows
        mi["balance_sheet"] = derived_bs
        mi.pop("run_gate", None)  # inputs changed -> gate must be re-cleared
        tmp = out_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(mi, fh, indent=1)
        with open(tmp, encoding="utf-8") as fh:
            json.load(fh)  # re-parse guard
        os.replace(tmp, out_path)
        result["written"] = os.path.abspath(out_path)
        result["note"] = ("saved - re-clear the run gate (Run Gate page or "
                          "Save & RUN) before the next run")
    return result


NAV_LINKS = [
    ("/", "Run Controls"), ("/portfolio", "Portfolio construction"),
    ("/model-points", "Model Points"), ("/assumptions", "Assumptions"),
    ("/esg", "ESG"), ("/run-gate", "Run Gate"),
    ("/run-execution", "Run"), ("/cashflows", "Cash flows"),
    ("/stress", "Stress"), ("/calibration", "Calibration"),
    ("/history", "History"), ("/my-results", "My results"),
]


def nav_html(active: str) -> str:
    """Shared top navigation bar (inline styles; zero external refs)."""
    links = []
    for href, label in NAV_LINKS:
        style = ("background:#2b6cff;color:#fff"
                 if href == active else "color:#9fb4ff")
        links.append('<a href="%s" style="text-decoration:none;padding:5px '
                     '11px;border-radius:7px;font-size:13px;%s">%s</a>'
                     % (href, style, label))
    return ('<nav style="display:flex;gap:4px;flex-wrap:wrap;padding:10px '
            '18px;background:#12151c;border-bottom:1px solid #262b36">'
            + "".join(links) + "</nav>")


def render_portfolio_html() -> str:
    """Self-contained portfolio construction page."""
    return """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Portfolio construction - PC-1</title>
<style>
 body{font:14px/1.5 system-ui,Segoe UI,Arial,sans-serif;margin:0;background:#0f1115;color:#e8eaed}
 main{max-width:1180px;margin:0 auto;padding:24px}
 h1{font-size:20px;margin:0 0 4px} h2{font-size:15px;margin:18px 0 8px;color:#9fb4ff}
 .card{background:#171a21;border:1px solid #262b36;border-radius:10px;padding:16px;margin:12px 0}
 .muted{color:#9aa3b2} .mono{font-family:ui-monospace,Consolas,monospace}
 button,select,input{font:inherit;border-radius:7px}
 button{padding:7px 14px;border:1px solid #2b6cff;background:#2b6cff;color:#fff;cursor:pointer}
 button.sec{background:#20242e;border-color:#394150}
 button.del{background:#472430;border-color:#7a3a4d;padding:3px 9px}
 button:disabled{background:#33384a;border-color:#33384a;cursor:not-allowed}
 input,select{background:#0b0d12;color:#e8eaed;border:1px solid #2c3444;padding:5px 7px}
 input{width:110px} input.small{width:70px}
 table{border-collapse:collapse;width:100%;font-size:13px}
 th,td{border-bottom:1px solid #262b36;padding:5px 6px;text-align:left;white-space:nowrap}
 th{color:#9fb4ff}
 .ok{color:#36d399} .bad{color:#f87272}
 pre{background:#0b0d12;border:1px solid #20242e;border-radius:8px;padding:12px;white-space:pre-wrap;max-height:240px;overflow:auto}
 .pill{display:inline-block;padding:2px 10px;border-radius:999px;font-size:12px;border:1px solid #394150}
 .unsigned{background:#3a2b12;border:1px solid #8a6d1a;color:#ffd166;border-radius:10px;padding:10px 14px;margin:10px 0;font-weight:600}
 .tabbar button.on{background:#2b6cff;border-color:#2b6cff}
</style></head><body>""" + nav_html("/portfolio") + """<main>
 <h1>Portfolio construction</h1>
 <div class="muted">PC-1 - construct the inputs freely: asset classes + SAA (derives the balance sheet
  and drives the fund mechanics), a product catalogue (e.g. short vs long term par products), and the
  composed model-point portfolio. Saving re-validates everything through the governed loader.
  <a href="/run-execution" style="color:#9fb4ff">Run page</a> &middot;
  <a href="/cashflows" style="color:#9fb4ff">Cash-flow projections</a></div>
 <div class="unsigned">UNSIGNED &mdash; catalogue rates and SAA parameters are scenario inputs pending Model Owner approval.</div>

 <div class="tabbar" style="display:flex;gap:8px;margin:10px 0">
  <button class="sec on" data-sect="sect-saa">1 &middot; Asset strategy (SAA)</button>
  <button class="sec" data-sect="sect-cat">2 &middot; Product catalogue</button>
  <button class="sec" data-sect="sect-pf">3 &middot; Portfolio composer</button>
 </div>

 <div class="card sect" id="sect-saa">
  <h2>Asset strategy (SAA) <span class="pill" id="wsum">weights: &hellip;</span></h2>
  <label class="muted">Total book market value
   <input id="total-mv" value="200000000"></label>
  <table id="saa"><thead><tr><th>Asset class</th><th>Type</th><th>Weight %</th>
   <th>Yield %</th><th>Avg maturity (y)</th><th>Div yield %</th><th>Growth %</th>
   <th>Illiquid</th><th></th></tr></thead><tbody></tbody></table>
  <button class="sec" id="add-saa">+ add asset class</button>
 </div>

 <div class="card sect" id="sect-cat" style="display:none">
  <h2>Product catalogue</h2>
  <table id="cat"><thead><tr><th>Product id</th><th>Family</th><th>Label</th>
   <th>Term min</th><th>Term max</th><th>CD rate %</th><th>RB rate %</th>
   <th>TB %</th><th>SV %</th><th></th></tr></thead><tbody></tbody></table>
  <button class="sec" id="add-cat">+ add product</button>
 </div>

 <div class="card sect" id="sect-pf" style="display:none">
  <h2>Portfolio composer</h2>
  <table id="pf"><thead><tr><th>Product</th><th>Issue age</th><th>Gender</th>
   <th>Term (y)</th><th>Sum assured</th><th>Annual premium</th><th>Policies</th>
   <th>Vested bonus</th><th></th></tr></thead><tbody></tbody></table>
  <button class="sec" id="add-pf">+ add model point</button>
 </div>

 <div class="card">
  <button id="btn-validate" class="sec">Validate</button>
  <button id="btn-save">Validate &amp; save construction</button>
  <pre id="out" class="mono">Loading saved construction&hellip;</pre>
 </div>

<script>
"use strict";
var $=function(id){return document.getElementById(id);};
var FAMILIES={};
function el(tag,attrs,text){var e=document.createElement(tag);
  Object.keys(attrs||{}).forEach(function(k){e.setAttribute(k,attrs[k]);});
  if(text!=null){e.textContent=text;}return e;}
function inp(val,cls){var e=el("input",{class:cls||""});e.value=(val==null?"":val);return e;}
function delBtn(tr){var b=el("button",{class:"del"},"x");
  b.addEventListener("click",function(){tr.remove();updateWsum();});return b;}
function sel(options,val){var s=el("select",{});
  options.forEach(function(o){var op=el("option",{value:o},o);s.appendChild(op);});
  s.value=val||options[0];return s;}
function addSaaRow(r){r=r||{};var tr=el("tr",{});
  var tds=[inp(r.asset_class||"","label"),sel(["bond","equity","cash"],r.kind),
    inp(r.weight!=null?(100*r.weight).toFixed(2):"","small w"),
    inp(r.annual_yield!=null?(100*r.annual_yield).toFixed(2):"","small"),
    inp(r.avg_maturity_years!=null?r.avg_maturity_years:"","small"),
    inp(r.annual_dividend_yield!=null?(100*r.annual_dividend_yield).toFixed(2):"","small"),
    inp(r.annual_capital_growth!=null?(100*r.annual_capital_growth).toFixed(2):"","small")];
  tds.forEach(function(c){var td=el("td",{});td.appendChild(c);tr.appendChild(td);});
  var cb=el("input",{type:"checkbox"});cb.checked=!!r.illiquid;
  var td=el("td",{});td.appendChild(cb);tr.appendChild(td);
  td=el("td",{});td.appendChild(delBtn(tr));tr.appendChild(td);
  tr.querySelector("input.w").addEventListener("input",updateWsum);
  $("saa").querySelector("tbody").appendChild(tr);updateWsum();}
function addCatRow(r){r=r||{};var tr=el("tr",{});
  var cells=[inp(r.product_id||"","label"),
    sel(Object.keys(FAMILIES),r.family),
    inp(r.label||"","label"),
    inp(r.term_years_min!=null?r.term_years_min:"","small"),
    inp(r.term_years_max!=null?r.term_years_max:"","small"),
    inp(r.cash_dividend_rate!=null?(100*r.cash_dividend_rate).toFixed(2):"","small"),
    inp(r.rb_rate!=null?(100*r.rb_rate).toFixed(2):"","small"),
    inp(r.terminal_bonus_pct!=null?(100*r.terminal_bonus_pct).toFixed(1):"","small"),
    inp(r.surrender_value_pct!=null?(100*r.surrender_value_pct).toFixed(1):"","small")];
  cells.forEach(function(c){var td=el("td",{});td.appendChild(c);tr.appendChild(td);});
  var td=el("td",{});td.appendChild(delBtn(tr));tr.appendChild(td);
  $("cat").querySelector("tbody").appendChild(tr);}
function addPfRow(r){r=r||{};var tr=el("tr",{});
  var ids=currentCatalogueIds();
  var cells=[sel(ids.length?ids:["-"],r.product_id),
    inp(r.issue_age!=null?r.issue_age:"","small"),
    sel(["M","F"],r.gender),
    inp(r.term_years!=null?r.term_years:"","small"),
    inp(r.sum_assured!=null?r.sum_assured:""),
    inp(r.annual_premium!=null?r.annual_premium:""),
    inp(r.policy_count!=null?r.policy_count:"","small"),
    inp(r.vested_bonus!=null?r.vested_bonus:"","small")];
  cells.forEach(function(c){var td=el("td",{});td.appendChild(c);tr.appendChild(td);});
  var td=el("td",{});td.appendChild(delBtn(tr));tr.appendChild(td);
  $("pf").querySelector("tbody").appendChild(tr);}
function currentCatalogueIds(){var ids=[];
  $("cat").querySelectorAll("tbody tr").forEach(function(tr){
    var v=tr.cells[0].firstChild.value.trim();if(v){ids.push(v);}});
  return ids;}
function updateWsum(){var t=0;
  $("saa").querySelectorAll("input.w").forEach(function(i){t+=parseFloat(i.value)||0;});
  var w=$("wsum");w.textContent="weights: "+t.toFixed(2)+"%";
  w.className="pill "+(Math.abs(t-100)<0.01?"ok":"bad");}
function pct(v){var f=parseFloat(v);return isNaN(f)?null:f/100.0;}
function num(v){var f=parseFloat(v);return isNaN(f)?null:f;}
function collect(){
  var saa=[];
  $("saa").querySelectorAll("tbody tr").forEach(function(tr){
    var c=tr.cells;var kind=c[1].firstChild.value;
    var row={asset_class:c[0].firstChild.value.trim(),kind:kind,
      weight:pct(c[2].firstChild.value),illiquid:c[7].firstChild.checked};
    if(kind==="bond"){row.annual_yield=pct(c[3].firstChild.value);
      row.avg_maturity_years=num(c[4].firstChild.value);}
    if(kind==="cash"){row.annual_yield=pct(c[3].firstChild.value);}
    if(kind==="equity"){row.annual_dividend_yield=pct(c[5].firstChild.value);
      row.annual_capital_growth=pct(c[6].firstChild.value);}
    saa.push(row);});
  var cat=[];
  $("cat").querySelectorAll("tbody tr").forEach(function(tr){
    var c=tr.cells;var fam=c[1].firstChild.value;
    var row={product_id:c[0].firstChild.value.trim(),family:fam,
      label:c[2].firstChild.value.trim(),
      term_years_min:num(c[3].firstChild.value),
      term_years_max:num(c[4].firstChild.value)};
    if(fam==="HKCD_PAR_2026"){row.cash_dividend_rate=pct(c[5].firstChild.value);}
    if(fam==="HKRB_PAR_2026"){row.rb_rate=pct(c[6].firstChild.value);
      row.terminal_bonus_pct=pct(c[7].firstChild.value);}
    var sv=pct(c[8].firstChild.value);if(sv!=null){row.surrender_value_pct=sv;}
    cat.push(row);});
  var pf=[];
  $("pf").querySelectorAll("tbody tr").forEach(function(tr){
    var c=tr.cells;
    pf.push({product_id:c[0].firstChild.value,
      issue_age:num(c[1].firstChild.value),gender:c[2].firstChild.value,
      term_years:num(c[3].firstChild.value),
      sum_assured:num(c[4].firstChild.value),
      annual_premium:num(c[5].firstChild.value),
      policy_count:num(c[6].firstChild.value),
      vested_bonus:num(c[7].firstChild.value)||0});});
  return {asset_strategy:{total_market_value:num($("total-mv").value),
      rebalancing:"constant_mix",saa:saa},
    product_catalogue:cat,portfolio:pf};}
function post(path){
  $("out").textContent="Working...";
  return fetch(path,{method:"POST",headers:{"Content-Type":"application/json"},
    body:JSON.stringify(collect())}).then(function(r){return r.json();})
  .then(function(j){
    if(j.ok){$("out").innerHTML="<span class=ok>OK</span> "+
      (j.written?"saved to model_inputs.json - "+(j.note||""):"valid")+
      " | product classes: "+(j.product_classes||[]).join(", ")+
      " | derived balance sheet total: "+
      Number(j.derived_balance_sheet.stated_total_backing_asset_mv).toLocaleString();}
    else{$("out").innerHTML="<span class=bad>INVALID ("+(j.errors||[]).length+
      " issue(s))</span>"+String.fromCharCode(10)+(j.errors||[]).join(String.fromCharCode(10));}
  }).catch(function(e){$("out").innerHTML="<span class=bad>error</span> "+e;});}
document.querySelectorAll(".tabbar button[data-sect]").forEach(function(b){
  b.addEventListener("click",function(){
    document.querySelectorAll(".sect").forEach(function(c){c.style.display="none";});
    document.querySelectorAll(".tabbar button[data-sect]").forEach(function(x){x.className="sec";});
    $(b.getAttribute("data-sect")).style.display="block";
    b.className="sec on";});});
$("btn-validate").addEventListener("click",function(){post("/validate_construction");});
$("btn-save").addEventListener("click",function(){post("/save_construction");});
$("add-saa").addEventListener("click",function(){addSaaRow();});
$("add-cat").addEventListener("click",function(){addCatRow();});
$("add-pf").addEventListener("click",function(){addPfRow();});
fetch("/portfolio-defaults").then(function(r){return r.json();}).then(function(j){
  FAMILIES=j.families||{};
  $("total-mv").value=j.asset_strategy.total_market_value;
  (j.asset_strategy.saa||[]).forEach(addSaaRow);
  (j.product_catalogue||[]).forEach(addCatRow);
  (j.portfolio||[]).forEach(addPfRow);
  $("out").textContent="Loaded. Edit the three blocks, then Validate & save. "+
    "After saving, re-clear the run gate (Save & RUN re-clears it automatically).";
}).catch(function(e){$("out").textContent="load failed: "+e;});
</script></main></body></html>"""
