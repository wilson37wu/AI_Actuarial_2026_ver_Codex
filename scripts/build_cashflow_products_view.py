#!/usr/bin/env python3
"""Phase 38 Task 1+2 - Cash-Flow & Products offline view (no-calc bundler).

Reads ALREADY-PRODUCED governed model output (the PAR-endowment reference runs
under docs/validation/) plus the product catalogue, and emits a single
self-contained, zero-install, fully-offline ``cashflow_products.html`` (no
external refs, no network, no build step for the user). It performs NO model
calculation - it only re-shapes embedded output for display, exactly like
build_ui_data.py.

Task 2 (this revision): embeds the 5yr / 10yr / 20yr reference runs and adds a
product/term selector so the user can switch the charted term. The 20yr run is
the default and is byte-for-byte the prior reference; 5/10yr are governed term
variants (build_projection_reference_terms.py). Still display-only + traceable.

Run:  python3 scripts/build_cashflow_products_view.py
Out:  cashflow_products.html  (repo root)
"""
from __future__ import annotations
import json, os, re

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VALDIR = os.path.join(REPO, "docs", "validation")
OUT = os.path.join(REPO, "cashflow_products.html")

# (key, source filename, selector label) - 20yr is the governed default.
TERMS = [
    ("5",  "PROJECTION_REFERENCE_RUN_5YR.json",  "5-year"),
    ("10", "PROJECTION_REFERENCE_RUN_10YR.json", "10-year"),
    ("20", "PROJECTION_REFERENCE_RUN.json",      "20-year"),
]
DEFAULT_TERM = "20"


def _r(x, n=2):
    try:
        return round(float(x), n)
    except Exception:
        return 0.0


def build_one(src_path):
    """Re-shape ONE governed reference run into the per-term display payload."""
    d = json.load(open(src_path, encoding="utf-8"))
    L = d["L"]; A = d["A"]; S = d["S"]
    months = [int(r["month"]) for r in L]

    asset = {
        "govt":   [_r(r["gC"] + r["gM"]) for r in A],
        "credit": [_r(r["cC"] + r["cM"]) for r in A],
        "equity": [_r(r["eD"] + r["eG"]) for r in A],
        "cash":   [_r(r["ci"]) for r in A],
        "total":  [_r(r["ti"]) for r in A],
        "fmv":    [_r(r["fmv"]) for r in A],
    }
    liability = {
        "premium":   [_r(r["prem"]) for r in L],
        "expenses":  [_r(r["acq"] + r["ren"]) for r in L],
        "death_g":   [_r(r["dG"]) for r in L],
        "death_n":   [_r(r["dN"]) for r in L],
        "mat_g":     [_r(r["mG"]) for r in L],
        "mat_n":     [_r(r["mN"]) for r in L],
        "surrender": [_r(r["sv"]) for r in L],
        "net":       [_r(r["ncf"]) for r in L],
    }
    liability["benefits"] = [
        _r(liability["death_g"][i] + liability["death_n"][i] + liability["mat_g"][i]
           + liability["mat_n"][i] + liability["surrender"][i])
        for i in range(len(L))
    ]
    liability["guaranteed"] = [_r(liability["death_g"][i] + liability["mat_g"][i]) for i in range(len(L))]
    liability["nonguar"] = [_r(liability["death_n"][i] + liability["mat_n"][i]) for i in range(len(L))]

    # Net cash flow - BOTH views
    underwriting = liability["net"][:]                                  # prem - expenses - benefits
    alm = [_r(underwriting[i] + asset["total"][i]) for i in range(len(L))]  # + investment income
    def cum(xs):
        out = []; s = 0.0
        for v in xs:
            s += v; out.append(_r(s))
        return out
    net = {
        "underwriting": underwriting,
        "alm": alm,
        "cum_underwriting": cum(underwriting),
        "cum_alm": cum(alm),
    }

    pv = [
        ["PV premiums", d["pvP"], "in"],
        ["PV guaranteed benefits", d["pvG"], "out"],
        ["PV non-guaranteed benefits", d["pvN"], "out"],
        ["PV surrender benefits", d["pvSv"], "out"],
        ["PV expenses", d["pvE"], "out"],
        ["PV net liability (reserve basis)", d["pvNL"], "net"],
        ["PV asset investment income", d["pvAI"], "in"],
        ["Total shareholder transfer", d["totSh"], "net"],
        ["Total policyholder distribution", d["totPh"], "net"],
        ["Asset share at maturity", d["asAtMat"], "net"],
    ]
    pv = [[lbl, _r(val), kind] for lbl, val, kind in pv]

    params = d.get("params", {})
    meta = {
        "source": d.get("source"),
        "generated_utc": d.get("generated_utc"),
        "classification": d.get("classification"),
        "term_months": len(L),
        "src_file": os.path.basename(src_path),
        "params": params,
    }
    return {"meta": meta, "months": months, "asset": asset,
            "liability": liability, "net": net, "pv": pv}


def build_catalogue():
    # ---- Product catalogue (modelled + tested) -------------------------------
    products = [
        {
            "name": "PAR Endowment (5 / 10 / 20-year)",
            "type": "Participating endowment - reversionary bonus",
            "engine": "par_model_v2.projection.monthly_projection.ParEndowmentProduct",
            "terms": "5 / 10 / 20yr - all governed reference runs (selectable in Cash Flows)",
            "params": {
                "Issue age / gender": "40 / M",
                "Sum assured": "1,000,000",
                "Annual premium": "60,000",
                "Reversionary bonus rate": "3.0%",
                "Terminal bonus %": "50%",
                "Surrender value %": "90%",
                "PH share": "90%",
                "Reserving discount": "3.0%",
            },
            "mechanics": ("Death in term: sum assured (guar) + accumulated reversionary bonus (non-guar). "
                          "Survival to term: sum assured (guar) + terminal bonus (non-guar). "
                          "Surrender: surrender_value_pct x asset share. Asset share rolls monthly with 70/30 profit sharing. "
                          "The 5/10/20yr runs use identical product/fund presets; only the term (60/120/240 months) differs."),
            "tested": "tests/test_hk_participating_products.py; monthly-projection unit tests; three governed reference runs (PROJECTION_REFERENCE_RUN*.json).",
            "status": "Reference runs (5/10/20yr, charted)",
        },
        {
            "name": "HK Reversionary-Bonus PAR",
            "type": "Hong Kong participating - reversionary + terminal bonus",
            "engine": "par_model_v2.projection.hk_participating",
            "terms": "Per fixture book",
            "params": {"Bonus": "Reversionary (vesting) + terminal", "Fixtures": "hk_reversionary_bonus_policies.json"},
            "mechanics": ("Reversionary bonuses vest annually and are guaranteed once declared; terminal bonus paid at "
                          "maturity/death from the unvested surplus. Mechanics: docs/HK_REVERSIONARY_BONUS_PRODUCT_MECHANICS.md."),
            "tested": "tests/test_hk_participating_products.py; fixture book reconciliation.",
            "status": "Modelled & tested",
        },
        {
            "name": "HK Cash-Dividend PAR",
            "type": "Hong Kong participating - cash dividend",
            "engine": "par_model_v2.projection.hk_participating",
            "terms": "Per fixture book",
            "params": {"Distribution": "Annual cash dividend", "Fixtures": "hk_cash_dividend_policies.json"},
            "mechanics": ("Surplus distributed as an annual cash dividend (paid, accumulated at interest, or premium-offset) "
                          "rather than a sum-assured bonus. Mechanics: docs/HK_CASH_DIVIDEND_PRODUCT_MECHANICS.md."),
            "tested": "tests/test_hk_participating_products.py; fixture book reconciliation.",
            "status": "Modelled & tested",
        },
    ]
    model_point_schema = ["product_type", "issue_age", "gender", "term_years",
                          "sum_assured", "annual_premium", "policy_count", "vested_bonus"]
    return {"products": products, "model_point_schema": model_point_schema}


def build_payload():
    terms = {}
    order = []
    for key, fname, label in TERMS:
        one = build_one(os.path.join(VALDIR, fname))
        one["label"] = label
        terms[key] = one
        order.append(key)
    cat = build_catalogue()
    return {
        "default": DEFAULT_TERM,
        "order": order,
        "terms": terms,
        "products": cat["products"],
        "model_point_schema": cat["model_point_schema"],
    }


HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Cash Flows &amp; Products - Actuarial Stochastic Model (offline)</title>
<style>
  :root{--bg:#0f1822;--panel:#172433;--panel2:#1d2f42;--ink:#e8eef5;--muted:#9fb2c6;
    --line:#2a3f57;--accent:#3da5ff;--accent2:#2bd4a7;--warn:#e0bd72;--bad:#ff6b6b;
    --govt:#3da5ff;--credit:#2bd4a7;--equity:#caa14a;--cash:#9b8cff;}
  *{box-sizing:border-box}
  body{margin:0;background:linear-gradient(160deg,#0f1822,#13202e);color:var(--ink);
    font:15px/1.5 -apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;-webkit-font-smoothing:antialiased}
  .wrap{max-width:1060px;margin:0 auto;padding:30px 20px 70px}
  a{color:var(--accent)}
  .eyebrow{letter-spacing:.14em;text-transform:uppercase;font-size:11.5px;color:var(--accent2);font-weight:700}
  h1{font-size:25px;margin:.2em 0 .1em}
  .sub{color:var(--muted);max-width:74ch;font-size:14px}
  .offline{display:inline-flex;align-items:center;gap:7px;background:rgba(61,165,255,.1);
    border:1px solid rgba(61,165,255,.3);color:#9fcdfb;border-radius:999px;padding:4px 11px;font-size:12px;font-weight:600;margin-top:10px}
  .tabs{display:flex;gap:6px;margin:22px 0 0;border-bottom:1px solid var(--line);flex-wrap:wrap}
  .tab{padding:10px 16px;cursor:pointer;color:var(--muted);font-weight:600;border:1px solid transparent;border-bottom:none;border-radius:9px 9px 0 0}
  .tab[aria-selected=true]{color:var(--ink);background:var(--panel);border-color:var(--line)}
  .panel{display:none;background:var(--panel);border:1px solid var(--line);border-top:none;border-radius:0 0 12px 12px;padding:20px}
  .panel.on{display:block}
  .termsel{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin:0 0 16px;
    padding:11px 13px;background:var(--panel2);border:1px solid var(--line);border-radius:10px}
  .tslabel{font-size:12px;letter-spacing:.04em;text-transform:uppercase;color:var(--muted);font-weight:700}
  .tspills{display:flex;gap:6px;flex-wrap:wrap}
  .tpill{padding:6px 14px;cursor:pointer;font-size:13px;font-weight:600;color:var(--muted);
    background:var(--panel);border:1px solid var(--line);border-radius:999px}
  .tpill[aria-selected=true]{color:#06121d;background:var(--accent2);border-color:var(--accent2)}
  .tsnote{font-size:12px;color:var(--muted);margin-left:auto}
  .subtabs{display:flex;gap:6px;margin-bottom:14px;flex-wrap:wrap}
  .stab{padding:6px 13px;cursor:pointer;font-size:13px;font-weight:600;color:var(--muted);
    background:var(--panel2);border:1px solid var(--line);border-radius:999px}
  .stab[aria-selected=true]{color:#06121d;background:var(--accent);border-color:var(--accent)}
  .view{display:none}.view.on{display:block}
  h2{font-size:17px;margin:.2em 0 .5em}
  h3{font-size:13px;letter-spacing:.06em;text-transform:uppercase;color:var(--muted);margin:18px 0 8px}
  .muted{color:var(--muted)}.note{color:var(--muted);font-size:12.5px;margin-top:10px}
  .legend{display:flex;gap:14px;flex-wrap:wrap;margin:4px 0 8px;font-size:12.5px;color:var(--muted)}
  .legend span{display:inline-flex;align-items:center;gap:6px}
  .sw{width:11px;height:11px;border-radius:2px;display:inline-block}
  .chartbox{background:#0d1620;border:1px solid var(--line);border-radius:10px;padding:10px}
  svg{display:block;width:100%;height:auto}
  table{width:100%;border-collapse:collapse;margin-top:6px}
  th,td{text-align:left;padding:8px 11px;border-bottom:1px solid var(--line);font-size:13.5px}
  th{background:var(--panel2);color:var(--muted);font-weight:600}
  td.num{text-align:right;font-variant-numeric:tabular-nums}
  .in{color:var(--accent2)}.out{color:var(--warn)}.net{color:var(--accent)}
  .kpis{display:grid;grid-template-columns:repeat(2,1fr);gap:12px;margin:4px 0 6px}
  @media(min-width:720px){.kpis{grid-template-columns:repeat(4,1fr)}}
  .kpi{background:#0d1620;border:1px solid var(--line);border-radius:10px;padding:12px 14px}
  .kpi .k{font-size:11.5px;color:var(--muted)}.kpi .v{font-size:18px;font-weight:700;margin-top:3px;font-variant-numeric:tabular-nums}
  .cards{display:grid;grid-template-columns:1fr;gap:14px}
  @media(min-width:760px){.cards{grid-template-columns:1fr 1fr}}
  .card{background:#0d1620;border:1px solid var(--line);border-radius:12px;padding:16px 17px}
  .card h4{margin:0 0 2px;font-size:16px}
  .card .ty{color:var(--accent2);font-size:12px;font-weight:600}
  .card dl{display:grid;grid-template-columns:auto 1fr;gap:3px 12px;margin:10px 0 0;font-size:13px}
  .card dt{color:var(--muted)}.card dd{margin:0;text-align:right;font-variant-numeric:tabular-nums}
  .badge{display:inline-block;margin-top:10px;padding:3px 9px;border-radius:999px;font-size:11px;font-weight:700;
    background:rgba(43,212,167,.13);color:#5fe6c2;border:1px solid rgba(43,212,167,.33)}
  .badge.ref{background:rgba(61,165,255,.13);color:#9fcdfb;border-color:rgba(61,165,255,.33)}
  code{background:#0d1620;border:1px solid var(--line);border-radius:6px;padding:1px 6px;font-size:12.5px}
  footer{margin-top:26px;color:var(--muted);font-size:12px;border-top:1px solid var(--line);padding-top:14px}
</style>
</head>
<body>
<div class="wrap">
  <div class="eyebrow">Actuarial Stochastic Capital Model</div>
  <h1>Cash Flows &amp; Products</h1>
  <p class="sub">Asset, liability and net cash-flow projections plus the product catalogue, displayed
     directly from governed model output. Zero install, fully offline - nothing is recomputed here.
     <a href="index.html">&larr; back to start</a> · <a href="ui_app.html">SCR / capital report</a></p>
  <p><span class="offline">● Offline · embedded snapshot</span></p>

  <div class="tabs" role="tablist">
    <div class="tab" role="tab" data-tab="cf" aria-selected="true">Cash Flows</div>
    <div class="tab" role="tab" data-tab="pr" aria-selected="false">Products</div>
  </div>

  <div class="panel on" id="cf">
    <div class="termsel">
      <span class="tslabel">Product / term</span>
      <div class="tspills" id="tspills" role="tablist"></div>
      <span class="tsnote" id="tsnote"></span>
    </div>
    <div class="subtabs">
      <div class="stab" data-view="cf-asset" aria-selected="true">Asset</div>
      <div class="stab" data-view="cf-liab" aria-selected="false">Liability</div>
      <div class="stab" data-view="cf-net" aria-selected="false">Net</div>
    </div>
    <div class="view on" id="cf-asset"></div>
    <div class="view" id="cf-liab"></div>
    <div class="view" id="cf-net"></div>
    <p class="note" id="cfsrc"></p>
  </div>

  <div class="panel" id="pr"></div>

  <footer>
    Source: <code>docs/validation/PROJECTION_REFERENCE_RUN*.json</code> (5 / 10 / 20yr) ·
    <span id="cls"></span><br>
    Display-only over frozen model output (EDUCATIONAL). Built by
    <code>scripts/build_cashflow_products_view.py</code> - a no-calculation bundler. 0 external references.
  </footer>
</div>
<script id="cfp-data" type="application/json">__DATA__</script>
<script>
(function(){
  var DATA = JSON.parse(document.getElementById("cfp-data").textContent);
  var cur = DATA.default;
  function td(){return DATA.terms[cur];}
  function esc(s){return String(s==null?"":s).replace(/[&<>]/g,function(c){return{"&":"&amp;","<":"&lt;",">":"&gt;"}[c];});}
  function fmt(x){var n=Number(x); if(!isFinite(n))return "-";
    return n.toLocaleString(undefined,{maximumFractionDigits:0});}

  // ---- generic multi-series line chart (inline SVG, no libs) ----
  function chart(series, N, opts){
    opts=opts||{}; var W=980,H=300,pl=64,pr=16,pt=14,pb=26;
    var all=[]; series.forEach(function(s){all=all.concat(s.data);});
    var mn=Math.min.apply(null,all.concat(opts.zero?[0]:[]));
    var mx=Math.max.apply(null,all.concat(opts.zero?[0]:[]));
    if(mn===mx){mx=mn+1;}
    var sx=function(i){return pl+(W-pl-pr)*(N<=1?0:i/(N-1));};
    var sy=function(v){return pt+(H-pt-pb)*(1-(v-mn)/(mx-mn));};
    var g='<svg viewBox="0 0 '+W+' '+H+'" preserveAspectRatio="xMidYMid meet" role="img">';
    // zero line + axis labels
    var yz=sy(0);
    if(mn<0&&mx>0){g+='<line x1="'+pl+'" y1="'+yz.toFixed(1)+'" x2="'+(W-pr)+'" y2="'+yz.toFixed(1)+'" stroke="#3a567a" stroke-dasharray="3 3"/>';}
    g+='<line x1="'+pl+'" y1="'+pt+'" x2="'+pl+'" y2="'+(H-pb)+'" stroke="#2a3f57"/>';
    g+='<line x1="'+pl+'" y1="'+(H-pb)+'" x2="'+(W-pr)+'" y2="'+(H-pb)+'" stroke="#2a3f57"/>';
    [mx,(mx+mn)/2,mn].forEach(function(v){var y=sy(v);
      g+='<text x="'+(pl-7)+'" y="'+(y+3).toFixed(1)+'" fill="#7f93a8" font-size="11" text-anchor="end">'+fmt(v)+'</text>';});
    // x ticks (years)
    var yrs=Math.round(N/12);
    for(var yy=0;yy<=yrs;yy+=Math.max(1,Math.round(yrs/10))){var i=Math.min(N-1,yy*12-1); if(i<0)i=0;
      g+='<text x="'+sx(i).toFixed(1)+'" y="'+(H-9)+'" fill="#7f93a8" font-size="11" text-anchor="middle">'+yy+'y</text>';}
    series.forEach(function(s){
      var pts=s.data.map(function(v,i){return sx(i).toFixed(1)+","+sy(v).toFixed(1);}).join(" ");
      if(s.fill){g+='<polygon points="'+pl+','+yz.toFixed(1)+' '+pts+' '+(W-pr)+','+yz.toFixed(1)+'" fill="'+s.color+'" opacity="0.14"/>';}
      g+='<polyline points="'+pts+'" fill="none" stroke="'+s.color+'" stroke-width="'+(s.w||1.8)+'"/>';
    });
    g+='</svg>'; return g;
  }
  function legend(series){return '<div class="legend">'+series.map(function(s){
    return '<span><i class="sw" style="background:'+s.color+'"></i>'+esc(s.label)+'</span>';}).join("")+'</div>';}

  function kpis(items){return '<div class="kpis">'+items.map(function(it){
    return '<div class="kpi"><div class="k">'+esc(it[0])+'</div><div class="v '+(it[2]||"")+'">'+esc(it[1])+'</div></div>';}).join("")+'</div>';}

  // ---- Asset view ----
  function renderAsset(){
    var D=td(), a=D.asset, N=D.months.length;
    var series=[
      {label:"Govt (coupon+maturity)",data:a.govt,color:"#3da5ff"},
      {label:"Credit",data:a.credit,color:"#2bd4a7"},
      {label:"Equity (div+growth)",data:a.equity,color:"#caa14a"},
      {label:"Cash interest",data:a.cash,color:"#9b8cff"},
      {label:"Total income",data:a.total,color:"#e8eef5",w:2.4}
    ];
    var pvAI=D.pv.filter(function(r){return r[0].indexOf("asset")>-1;})[0];
    var html='<h2>Asset cash flows - monthly income by class</h2>'+
      kpis([["PV asset investment income",fmt(pvAI?pvAI[1]:0),"in"],
            ["Final fund value (FMV)",fmt(a.fmv[a.fmv.length-1]),""],
            ["Peak monthly income",fmt(Math.max.apply(null,a.total)),"in"],
            ["Months projected",N,""]])+
      legend(series)+'<div class="chartbox">'+chart(series,N)+'</div>'+
      '<p class="note">Govt/Credit show coupon + maturity proceeds; Equity shows dividends + capital growth; Cash is short-rate interest. '+
      'Fund market value rolls forward to '+fmt(a.fmv[a.fmv.length-1])+'.</p>';
    document.getElementById("cf-asset").innerHTML=html;
  }
  // ---- Liability view ----
  function renderLiab(){
    var D=td(), l=D.liability, N=D.months.length;
    var series=[
      {label:"Premium (in)",data:l.premium,color:"#2bd4a7",fill:true},
      {label:"Benefits (out)",data:l.benefits,color:"#ff6b6b"},
      {label:"Expenses (out)",data:l.expenses,color:"#e0bd72"},
      {label:"Net (ncf)",data:l.net,color:"#3da5ff",w:2.4}
    ];
    var gn=[
      {label:"Guaranteed benefits",data:l.guaranteed,color:"#3da5ff"},
      {label:"Non-guaranteed benefits",data:l.nonguar,color:"#caa14a"},
      {label:"Surrender value",data:l.surrender,color:"#9b8cff"}
    ];
    function pvrow(k){return D.pv.filter(function(r){return r[0].indexOf(k)>-1;})[0];}
    var html='<h2>Liability cash flows - premium, benefits, expenses</h2>'+
      kpis([["PV premiums",fmt(pvrow("premiums")[1]),"in"],
            ["PV guaranteed",fmt(pvrow("guaranteed")[1]),"out"],
            ["PV non-guaranteed",fmt(pvrow("non-guaranteed")[1]),"out"],
            ["PV net liability",fmt(pvrow("net liability")[1]),"net"]])+
      legend(series)+'<div class="chartbox">'+chart(series,N,{zero:true})+'</div>'+
      '<h3>Guaranteed vs non-guaranteed benefit split</h3>'+
      legend(gn)+'<div class="chartbox">'+chart(gn,N)+'</div>'+
      '<p class="note">Net (ncf) = premium &minus; expenses &minus; benefits. Guaranteed = death/maturity sum assured; '+
      'non-guaranteed = accumulated reversionary + terminal bonus.</p>';
    document.getElementById("cf-liab").innerHTML=html;
  }
  // ---- Net view (BOTH) ----
  function renderNet(){
    var D=td(), n=D.net, N=D.months.length;
    var flow=[
      {label:"Net underwriting (prem - exp - benefits)",data:n.underwriting,color:"#3da5ff",w:2},
      {label:"Net incl. investment income (ALM)",data:n.alm,color:"#2bd4a7",w:2}
    ];
    var cumv=[
      {label:"Cumulative underwriting",data:n.cum_underwriting,color:"#3da5ff",fill:true,w:2},
      {label:"Cumulative ALM (incl. income)",data:n.cum_alm,color:"#2bd4a7",w:2}
    ];
    var html='<h2>Net cash flow - two views</h2>'+
      kpis([["Final cum. underwriting",fmt(n.cum_underwriting[N-1]),"net"],
            ["Final cum. ALM",fmt(n.cum_alm[N-1]),"net"],
            ["Min monthly underwriting",fmt(Math.min.apply(null,n.underwriting)),"out"],
            ["Max monthly ALM",fmt(Math.max.apply(null,n.alm)),"in"]])+
      '<h3>Monthly net</h3>'+legend(flow)+'<div class="chartbox">'+chart(flow,N,{zero:true})+'</div>'+
      '<h3>Cumulative net</h3>'+legend(cumv)+'<div class="chartbox">'+chart(cumv,N,{zero:true})+'</div>'+
      '<p class="note"><b>Underwriting net</b> = premium &minus; expenses &minus; benefits (liability side). '+
      '<b>ALM net</b> = underwriting net + asset investment income, i.e. the net cash position once the asset book’s '+
      'income is included - the asset-vs-liability liquidity view you asked for.</p>';
    document.getElementById("cf-net").innerHTML=html;
  }
  // ---- Products ----
  function renderProducts(){
    var p0=td().meta.params;
    var html='<h2>Products modelled &amp; tested</h2>'+
      '<p class="muted">The stochastic engine projects participating (PAR) products. The PAR endowment is run at '+
      '5 / 10 / 20-year terms as governed reference runs - switch the charted term with the selector in the Cash Flows tab.</p><div class="cards">';
    DATA.products.forEach(function(p){
      var dl=Object.keys(p.params).map(function(k){
        return '<dt>'+esc(k)+'</dt><dd>'+esc(p.params[k])+'</dd>';}).join("");
      var bcl = p.status.indexOf("Reference")>-1 ? "badge ref" : "badge";
      html+='<div class="card"><h4>'+esc(p.name)+'</h4><div class="ty">'+esc(p.type)+'</div>'+
        '<dl>'+dl+'</dl>'+
        '<p class="note"><b>Mechanics.</b> '+esc(p.mechanics)+'</p>'+
        '<p class="note"><b>Tested.</b> '+esc(p.tested)+'</p>'+
        '<span class="'+bcl+'">'+esc(p.status)+'</span></div>';
    });
    html+='</div><h3>Model-point schema (input fields)</h3><p class="muted">'+
      DATA.model_point_schema.map(function(f){return '<code>'+esc(f)+'</code>';}).join(" ")+'</p>'+
      '<p class="note">Model points drive the in-force book; PAR + GMMB rows supported. '+
      'Currently charted reference run: age '+esc(p0.age)+', sum assured '+fmt(p0.sa)+
      ', annual premium '+fmt(p0.annPrem)+', '+esc(p0.termYrs)+'yr term.</p>';
    document.getElementById("pr").innerHTML=html;
  }

  function renderAll(){renderAsset();renderLiab();renderNet();renderProducts();
    var D=td();
    document.getElementById("cfsrc").textContent=
      "Reference run ("+esc(D.label)+") generated "+(D.meta.generated_utc||"")+" · "+D.months.length+
      " months · "+(D.meta.src_file||"")+" · "+(D.meta.source||"");
    document.getElementById("tsnote").textContent=
      D.months.length+" months · "+D.meta.src_file;
  }

  // ---- term selector ----
  function buildPills(){
    var box=document.getElementById("tspills");
    box.innerHTML=DATA.order.map(function(k){
      var lbl=DATA.terms[k].label+(k===DATA.default?" (reference)":"");
      return '<div class="tpill" role="tab" data-term="'+k+'" aria-selected="'+(k===cur)+'">'+esc(lbl)+'</div>';
    }).join("");
    [].slice.call(box.querySelectorAll(".tpill")).forEach(function(el){
      el.addEventListener("click",function(){
        cur=el.getAttribute("data-term");
        [].slice.call(box.querySelectorAll(".tpill")).forEach(function(n){
          n.setAttribute("aria-selected", n===el?"true":"false");});
        renderAll();
      });
    });
  }

  buildPills();
  renderAll();
  document.getElementById("cls").textContent=td().meta.classification||"";

  // tab + subtab wiring
  function sel(nodes,on){nodes.forEach(function(n){n.setAttribute("aria-selected", n===on?"true":"false");});}
  var tabs=[].slice.call(document.querySelectorAll(".tab"));
  tabs.forEach(function(t){t.addEventListener("click",function(){
    sel(tabs,t);
    document.querySelectorAll(".panel").forEach(function(p){p.classList.toggle("on",p.id===t.getAttribute("data-tab"));});
  });});
  var stabs=[].slice.call(document.querySelectorAll(".stab"));
  stabs.forEach(function(s){s.addEventListener("click",function(){
    sel(stabs,s);
    document.querySelectorAll(".view").forEach(function(v){v.classList.toggle("on",v.id===s.getAttribute("data-view"));});
  });});
})();
</script>
</body>
</html>
"""


def main():
    data = build_payload()
    blob = json.dumps(data, separators=(",", ":"), ensure_ascii=False)
    html = HTML.replace("__DATA__", blob)
    # offline guarantee: no external references
    bad = re.findall(r'https?://|<script\s+src|<link\b|@import', html)
    if bad:
        raise SystemExit("external refs present: %r" % bad[:5])
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write(html)
    nterms = len(data["terms"])
    print("wrote %s (%d bytes), 0 external refs, %d terms (%s)"
          % (OUT, len(html), nterms, ",".join(data["order"])))


if __name__ == "__main__":
    main()
