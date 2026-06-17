#!/usr/bin/env python3
"""Build offline_home.html -- a zero-install landing page for the offline UI.

Standing owner directive (scheduled task): "build a user interface for offline
use ... it should not depend on any pre installation ... the user interface uses
ONLY the model output to display the result." This page is a single, self-
contained HTML landing surface that (a) reads a small curated set of GOVERNED
figures straight from the model-output snapshot ``ui_data.json`` and (b) links the
existing offline views so a non-technical user has one obvious place to start.

It recomputes NOTHING. It alters no governed artifact (ui_app.html untouched) and
introduces no ui_data contract change (it is a separate file). stdlib only.

Offline snapshot-loader (added 2026-06-16, claude window): an ADDITIVE, zero-network
drag/click loader lets a user point the page at a DIFFERENT ui_data.json and see the
headline figures refresh. The file is read locally via the FileReader API (no upload,
no network); the JS extraction MIRRORS the Python ``figures`` mapping below so the
loaded snapshot renders by the same rules. The built-in governed snapshot remains the
default and is restored by a Reset button -- graceful fallback on any parse/shape error.
"""
from __future__ import annotations
import json, html, datetime, hashlib, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
UI_DATA = ROOT / "ui_data.json"
OUT = ROOT / "offline_home.html"

# Offline views to surface. zero_install=True means double-click, no runtime.
VIEWS = [
    ("ui_app.html", "Full Results Explorer",
     "The complete governed result UI: Overview, Inventory &amp; Contract, "
     "Calibrations, Capital &amp; Tail, Governance, plus phase deep-dives, "
     "chart/CSV export and print-to-PDF.", True),
    ("model_result_viewer.html", "Result Viewer (light)",
     "A lighter, faster read-only viewer of the same model-output snapshot.", True),
    ("combined_model_app.html", "Combined Model App",
     "Combined offline GUI bringing the result surfaces together in one file.", True),
    ("par_projection_gui.html", "PAR Projection GUI",
     "Interactive PAR-endowment projection explorer (deterministic walk-through).", True),
    ("model_summary_card.html", "Model Summary Card (print)",
     "A printable one-page summary of the governed headline, capital basis, "
     "seven driver SCRs, tail metrics and validation scorecard &mdash; read on "
     "screen or print / save-as-PDF. Computes nothing.", True),
    ("launchers/README.md", "Input &amp; Run GUI",
     "Enter your own actuarial inputs and run the stochastic model end-to-end on "
     "localhost. Needs Python 3.8+ (relaxes zero-install for THIS input+run step "
     "only); your run renders into a separate copy and never edits the governed "
     "template.", False),
]

# "Which view do I want?" chooser -- consolidates the result-view descriptions into
# goal-oriented one-liners. Every href MUST also be a VIEWS entry (asserted in build()),
# so the chooser and the cards stay single-sourced and never drift.
CHOOSER = [
    ("See the headline capital numbers and the validation scorecard at a glance "
     "&mdash; on screen or print / save-as-PDF",
     "model_summary_card.html", "Model Summary Card", True),
    ("Explore the full governed results in depth: capital, tail, calibrations, "
     "governance and phase deep-dives, with chart &amp; CSV export",
     "ui_app.html", "Full Results Explorer", True),
    ("Read the same model-output snapshot in a lighter, faster viewer",
     "model_result_viewer.html", "Result Viewer (light)", True),
    ("Open every result surface bundled together in one single file",
     "combined_model_app.html", "Combined Model App", True),
    ("Walk through the PAR-endowment projection interactively",
     "par_projection_gui.html", "PAR Projection GUI", True),
    ("Enter your own actuarial inputs and run the stochastic model end-to-end",
     "launchers/README.md", "Input &amp; Run GUI", False),
]

# --- Snapshot loader assets (kept OUT of the f-string so JS braces need no escaping) ---
LOADER_CSS = """
  .loader { background:var(--panel); border:1px solid var(--line); border-radius:11px;
    padding:15px 16px; margin-top:8px; }
  .drop { border:1.5px dashed #2f4660; border-radius:9px; padding:16px; text-align:center;
    color:var(--mut); font-size:13.5px; cursor:pointer;
    transition:border-color .15s, background .15s; }
  .drop:hover, .drop.hover { border-color:var(--acc); background:#0c141d; }
  .drop b { color:var(--ink); }
  .lbtns { display:flex; gap:10px; margin-top:10px; flex-wrap:wrap; }
  .btn { background:#0c141d; color:var(--ink); border:1px solid var(--line);
    border-radius:7px; padding:7px 13px; font-size:13px; cursor:pointer; }
  .btn:hover { border-color:var(--acc); }
  .lbanner { margin-top:10px; font-size:12.5px; padding:8px 11px; border-radius:7px;
    display:none; }
  .lbanner.ok { display:block; background:#11321f; color:var(--ok);
    border:1px solid #1c5436; }
  .lbanner.err { display:block; background:#3a1414; color:#ff8f8f;
    border:1px solid #5a1f1f; }
  .fig.changed { outline:1px solid var(--acc); outline-offset:-1px; }"""

CHOOSER_CSS = """
  .chooser { display:flex; flex-direction:column; gap:8px; }
  .crow { display:grid; grid-template-columns:1fr auto; gap:6px 14px; align-items:center;
    background:var(--panel); border:1px solid var(--line); border-radius:9px;
    padding:11px 14px; }
  .cgoal { color:var(--ink); font-size:13.5px; }
  .cpick { display:flex; align-items:center; gap:8px; white-space:nowrap; }
  .cpick a { color:var(--acc); text-decoration:none; font-weight:600; font-size:13.5px; }
  .cpick a:hover { text-decoration:underline; }
  .cpick .badge { margin-left:2px; }
  @media (max-width:560px){ .crow { grid-template-columns:1fr; }
    .cpick { white-space:normal; } }"""

# Accessibility / quick-start pass (added 2026-06-16, claude window) -- static CSS only,
# NO new JS, so the zero-JS-error guarantee is preserved. Provides: a skip-to-content link
# (visible only on keyboard focus), a visible keyboard focus ring on every interactive
# element, a reduced-motion fallback, and styling for the one-line "Start here" guidance.
A11Y_CSS = """
  .skip { position:absolute; left:-9999px; top:0; z-index:200; background:var(--acc);
    color:#06121f; padding:9px 15px; border-radius:0 0 8px 0; font-weight:700;
    text-decoration:none; }
  .skip:focus { left:0; }
  .start { margin:12px 0 0; padding:9px 13px; background:#0c1f33; border:1px solid #1d4060;
    border-radius:8px; color:var(--ink); font-size:13px; }
  .start b { color:var(--acc); }
  a:focus-visible, button:focus-visible, .drop:focus-visible, [tabindex]:focus-visible {
    outline:2px solid var(--acc); outline-offset:2px; border-radius:6px; }
  main:focus { outline:none; }
  @media (prefers-reduced-motion: reduce){
    * { transition:none !important; }
    .card:hover { transform:none; } }"""

# Capital-at-a-glance graphic (added 2026-06-17, claude window) -- an ADDITIVE, inline-SVG
# horizontal bar chart that DISPLAYS the already-governed capital figures graphically. It
# recomputes nothing: each bar's length is just a value/max scaling of three governed
# numbers (standalone sum, var-covar/correlated SCR, nested 99.5% SCR) read verbatim from
# ui_data.json. No JS library, no network, no external ref -- the SVG is baked at build time
# and (for snapshot-loader parity) redrawn by the same in-page JS that refreshes the figures.
CAPBRIDGE_MAXW = 430.0  # px: max bar width inside the 560-wide viewBox (leaves a value gutter)
CAPBRIDGE_CSS = """
  .cbridge { background:var(--panel); border:1px solid var(--line); border-radius:11px;
    padding:14px 16px 10px; }
  .cbridge svg { width:100%; height:auto; display:block; }
  .cbar-label { fill:var(--mut); font-size:12.5px; }
  .cbval { fill:var(--ink); font-size:12.5px; font-weight:650; }
  .cbar.s0 { fill:#3a4a5e; }
  .cbar.s1 { fill:#2f6db0; }
  .cbar.s2 { fill:#4ea1ff; }
  .cbcap { color:var(--mut); font-size:12.5px; margin:9px 2px 0; }"""

# Standalone-SCR-by-driver graphic (added 2026-06-17, claude window) -- an ADDITIVE,
# inline-SVG horizontal mini bar set that DISPLAYS the seven already-governed standalone
# (pre-diversification) per-driver capital charges graphically. Recomputes nothing: each
# bar's length is value/max scaling of a governed number read verbatim from ui_data.json
# (rate/equity/credit/lapse/mortality/fx/liquidity _scr). The seven sum to the governed
# standalone_sum shown above (consistency asserted in the stdlib gate). No JS library, no
# network, no external ref -- the SVG is baked at build time and (for snapshot-loader
# parity) redrawn by the same in-page JS that refreshes the figures.
DRIVERBARS_MAXW = 430.0  # px: same value gutter as CAPBRIDGE_MAXW, inside the 560 viewBox
_DRIVER_ROWS = [
    ("rate_scr", "Interest rate"),
    ("equity_scr", "Equity"),
    ("credit_scr", "Credit"),
    ("lapse_scr", "Lapse"),
    ("mortality_scr", "Mortality"),
    ("fx_scr", "FX"),
    ("liquidity_scr", "Liquidity"),
]
DRIVERBARS_CSS = """
  .dbridge { background:var(--panel); border:1px solid var(--line); border-radius:11px;
    padding:14px 16px 10px; }
  .dbridge svg { width:100%; height:auto; display:block; }
  .dbar-label { fill:var(--mut); font-size:12px; }
  .dbval { fill:var(--ink); font-size:12px; font-weight:650; }
  .dbar { fill:#2f6db0; }
  .dbcap { color:var(--mut); font-size:12.5px; margin:9px 2px 0; }"""

# Tail-convergence sparkline (added 2026-06-17, claude window W35) -- an ADDITIVE, inline-SVG
# line chart that DISPLAYS the already-governed tail-convergence diagnostic graphically: the
# 99.5% VaR and ES liability estimates plotted against the outer-scenario count grid, with a
# marker at the GOVERNED recommended outer count n* (the point at which the model declares the
# tail estimate converged). Recomputes nothing: every plotted coordinate is just a value/range
# scaling of governed numbers read verbatim from ui_data.json's ``tail`` block (outer_grid,
# var_path, es_path, recommended_n_outer, final_var, final_es, converged). No JS library, no
# network, no external ref -- the SVG is baked at build time and (for snapshot-loader parity)
# redrawn by the same in-page JS that refreshes the figures.
TAILSPARK_GEO = {"x0": 10.0, "x1": 498.0, "y0": 14.0, "y1": 118.0}  # px inside the 560 viewBox
TAILSPARK_CSS = """
  .tspark { background:var(--panel); border:1px solid var(--line); border-radius:11px;
    padding:14px 16px 10px; }
  .tspark svg { width:100%; height:auto; display:block; }
  .tbase { stroke:var(--line); stroke-width:1; }
  .tvar { fill:none; stroke:#4ea1ff; stroke-width:2; }
  .tes  { fill:none; stroke:#e8b23a; stroke-width:2; }
  .tdot.var { fill:#4ea1ff; }
  .tdot.es  { fill:#e8b23a; }
  .tval { font-size:11.5px; font-weight:650; }
  .tval.var { fill:#4ea1ff; }
  .tval.es  { fill:#e8b23a; }
  .tnstar { stroke:#2ec27e; stroke-width:1.2; stroke-dasharray:4 3; }
  .tnlab  { fill:var(--ok); font-size:11px; font-weight:650; text-anchor:end; }
  .taxis  { fill:var(--mut); font-size:10.5px; }
  .tcap   { color:var(--mut); font-size:12.5px; margin:9px 2px 0; }
  .tkey   { display:inline-block; width:11px; height:3px; border-radius:2px;
    vertical-align:middle; margin:0 4px 0 10px; }"""

# VaR/ES point-vs-CI band strip (added 2026-06-17, claude window W36) -- an ADDITIVE,
# inline-SVG strip that DISPLAYS the already-governed 99.5% VaR and ES tail estimates each
# as a Monte-Carlo confidence-interval BAND with the governed point estimate marked on it.
# Recomputes nothing: every coordinate is a value/range scaling of governed numbers read
# verbatim from ui_data.json's ``tail`` block (var_ci / es_ci band ends, final_var / final_es
# point markers) on a single shared scale. Complements the W35 convergence sparkline (VaR/ES
# vs the outer-scenario count) by showing the SAMPLING UNCERTAINTY around the converged
# estimates. No JS library, no network, no external ref -- baked at build time and (for
# snapshot-loader parity) redrawn by the same in-page JS that refreshes the figures.
TAILCI_GEO = {"x0": 86.0, "x1": 470.0, "vy": 40.0, "ey": 92.0, "bh": 16.0}  # px in 560 viewBox
TAILCI_CSS = """
  .ciband-wrap { background:var(--panel); border:1px solid var(--line); border-radius:11px;
    padding:14px 16px 10px; }
  .ciband-wrap svg { width:100%; height:auto; display:block; }
  .citrack { stroke:var(--line); stroke-width:1; }
  .ciband { opacity:0.30; }
  .ciband.var { fill:#4ea1ff; }
  .ciband.es  { fill:#e8b23a; }
  .cipt { stroke-width:2; }
  .cipt.var { stroke:#4ea1ff; }
  .cipt.es  { stroke:#e8b23a; }
  .cilab { fill:var(--mut); font-size:12px; }
  .civ { font-size:11.5px; font-weight:650; }
  .civ.var { fill:#4ea1ff; }
  .civ.es  { fill:#e8b23a; }
  .cirange { fill:var(--mut); font-size:10.5px; text-anchor:middle; }
  .cicap { color:var(--mut); font-size:12.5px; margin:9px 2px 0; }"""

# --- Nested-vs-copula VaR confidence-interval comparison (offline-UI W37) ---
# Decision-neutral, additive, zero-network. Shows the governed 99.5% VaR estimate's
# Monte-Carlo confidence band from TWO governed estimators on ONE shared scale: the
# copula-simulated band (``var_ci``, tight -- the converged estimator) vs the NESTED
# estimator's band (``nested_var_ci``) computed at only ``nested_n_outer`` outer scenarios
# (wide -- more sampling noise). Both rows mark the SAME governed point (``final_var``),
# which lies inside both bands. Every x-coordinate is a value/range scaling of a governed
# number -- no number is derived. Complements the W36 VaR/ES CI strip by isolating the
# ESTIMATOR-CHOICE uncertainty for VaR. Redrawn by the snapshot-loader JS (redrawNestedCI).
NESTEDCI_GEO = {"x0": 116.0, "x1": 466.0, "vy": 40.0, "ey": 92.0, "bh": 16.0}  # px in 560 viewBox
NESTEDCI_CSS = """
  .ncici-wrap { background:var(--panel); border:1px solid var(--line); border-radius:11px;
    padding:14px 16px 10px; }
  .ncici-wrap svg { width:100%; height:auto; display:block; }
  .ncitrack { stroke:var(--line); stroke-width:1; }
  .nciband { opacity:0.30; }
  .nciband.copula { fill:#2ec27e; }
  .nciband.nested { fill:#e8b23a; }
  .ncipt { stroke-width:2; }
  .ncipt.copula { stroke:#2ec27e; }
  .ncipt.nested { stroke:#e8b23a; }
  .ncilab { fill:var(--mut); font-size:11px; }
  .nciv { font-size:11.5px; font-weight:650; fill:var(--ink); }
  .ncirange { fill:var(--mut); font-size:10.5px; text-anchor:middle; }
  .ncicap { color:var(--mut); font-size:12.5px; margin:9px 2px 0; }"""

LOADER_PANEL = """  <h2>Load a different snapshot (optional)</h2>
  <div class="loader" id="loader">
    <div class="drop" id="drop" tabindex="0" role="button"
      aria-label="Load a different ui_data.json snapshot from this computer">
      Drag a <b>ui_data.json</b> here, or <b>click to choose a file</b>, to refresh the
      figures above from a different model-output snapshot.<br/>
      <span style="font-size:12px">Stays fully offline &mdash; the file is read locally in
      your browser; nothing leaves this computer.</span>
      <input type="file" id="file" accept=".json,application/json" style="display:none"/>
    </div>
    <div class="lbtns">
      <button class="btn" id="reset" type="button">Reset to built-in snapshot</button>
    </div>
    <div class="lbanner" id="lbanner" role="status" aria-live="polite"></div>
  </div>
  <p class="sub" style="margin-top:8px; font-size:12.5px;">Loading a snapshot only
    re-renders the figures on this page from that file. It changes no governed artifact
    and uploads nothing; Reset restores the built-in governed snapshot.</p>
"""

LOADER_JS = """
<script>
// Additive offline snapshot-loader. ZERO network: the chosen file is read locally via
// FileReader. Mirrors the Python figure mapping so a loaded ui_data.json renders by the
// same rules. Built-in governed snapshot stays the default (Reset restores it).
(function(){
  var DEFAULT = { figsHTML:null, hv:"", hc:"", hs:"", bridgeHTML:null, driversHTML:null,
    tailHTML:null, tailciHTML:null, nestedciHTML:null };
  var CB_MAXW = 430;  // mirrors CAPBRIDGE_MAXW in scripts/build_offline_home.py
  var TS = { x0:10, x1:498, y0:14, y1:118 };  // mirrors TAILSPARK_GEO in the Python builder
  var TCI = { x0:86, x1:470, vy:40, ey:92, bh:16 };  // mirrors TAILCI_GEO in the Python builder
  var NCI = { x0:116, x1:466, vy:40, ey:92, bh:16 };  // mirrors NESTEDCI_GEO in the Python builder
  function fmt(x, dp){
    if (x === null || x === undefined) return "None";
    var n = Number(x);
    if (isFinite(n)) return n.toLocaleString("en-US",
      { minimumFractionDigits:dp, maximumFractionDigits:dp });
    return String(x);
  }
  function extract(d){
    var meta = d.meta || {}, cap = d.capital || {}, s = d.summary || {};
    var cur = ((meta.currency || {}).symbol) || "";
    var hl = null;
    try { hl = d.owner_decision_p31.evidence_pack.governed_headline.value; } catch(e){}
    return {
      figs: [
        ["Governed headline SCR component (frozen-t)", cur + fmt(hl, 2)],
        ["Nested 99.5% SCR", cur + fmt(cap.nested_scr, 0)],
        ["Var-covar / correlated SCR", cur + fmt(cap.correlated_scr, 0)],
        ["Standalone sum (pre-diversification)", cur + fmt(cap.standalone_sum, 0)],
        ["Diversification benefit (nested)", cur + fmt(cap.div_benefit_nested, 0)],
        ["Risk drivers (calibrated)", fmt(s.calibrated_drivers, 0)],
        ["Deployment gates cleared", String(s.gates_cleared) + "/" + String(s.gates_total)],
        ["Tasks complete", String(s.tasks_completed) + "/" + String(s.tasks_total)]
      ],
      mv: (meta.model_version != null ? String(meta.model_version) : ""),
      cv: (d.contract_version != null ? String(d.contract_version) : ""),
      snap: (meta.generated_utc != null ? String(meta.generated_utc) : "")
    };
  }
  function esc(s){ var e = document.createElement("div"); e.textContent = String(s); return e.innerHTML; }
  function setText(id, v){ var el = document.getElementById(id); if (el) el.textContent = v; }
  // Redraw the capital-at-a-glance bars from a (possibly loaded) snapshot. Pure display:
  // bar width = value/max scaled to CB_MAXW, mirroring _capbridge_svg in the Python builder.
  function redrawBridge(cap, cur){
    var svg = document.getElementById("capbridge");
    if (!svg) return;
    var keys = ["standalone_sum", "correlated_scr", "nested_scr"];
    var vals = keys.map(function(k){ return Number(cap[k]); });
    var present = vals.filter(function(v){ return isFinite(v); });
    var mx = present.length ? Math.max.apply(null, present) : 0;
    if (!(mx > 0)) return;
    keys.forEach(function(k, i){
      var v = vals[i];
      var rect = svg.querySelector('rect.cbar[data-key="' + k + '"]');
      var txt = svg.querySelector('text.cbval[data-key="' + k + '"]');
      var w = (isFinite(v) ? v / mx : 0) * CB_MAXW;
      if (rect) rect.setAttribute("width", w.toFixed(1));
      if (txt){ txt.setAttribute("x", (w + 8).toFixed(1));
        txt.textContent = (isFinite(v) ? cur + fmt(v, 0) : "n/a"); }
    });
  }
  // Redraw the per-driver standalone-SCR bars from a (possibly loaded) snapshot. Pure
  // display: width = value/max scaled to CB_MAXW, mirroring _driverbars_svg in the builder.
  function redrawDrivers(cap, cur){
    var svg = document.getElementById("driverbars");
    if (!svg) return;
    var keys = ["rate_scr","equity_scr","credit_scr","lapse_scr","mortality_scr","fx_scr","liquidity_scr"];
    var vals = keys.map(function(k){ return Number(cap[k]); });
    var present = vals.filter(function(v){ return isFinite(v); });
    var mx = present.length ? Math.max.apply(null, present) : 0;
    if (!(mx > 0)) return;
    keys.forEach(function(k, i){
      var v = vals[i];
      var rect = svg.querySelector('rect.dbar[data-key="' + k + '"]');
      var txt = svg.querySelector('text.dbval[data-key="' + k + '"]');
      var w = (isFinite(v) ? v / mx : 0) * CB_MAXW;
      if (rect) rect.setAttribute("width", w.toFixed(1));
      if (txt){ txt.setAttribute("x", (w + 8).toFixed(1));
        txt.textContent = (isFinite(v) ? cur + fmt(v, 0) : "n/a"); }
    });
  }
  // Redraw the tail-convergence sparkline from a (possibly loaded) snapshot. Pure display:
  // coordinates = value/range scaling, mirroring _tailspark_svg in the Python builder.
  function redrawTail(tail, cur){
    var svg = document.getElementById("tailspark");
    if (!svg || !tail) return;
    var grid = tail.outer_grid || [], vp = tail.var_path || [], ep = tail.es_path || [];
    var n = Math.min(grid.length, vp.length, ep.length);
    if (n < 1) return;
    var all = vp.slice(0, n).concat(ep.slice(0, n)).map(Number).filter(isFinite);
    if (!all.length) return;
    var vmin = Math.min.apply(null, all), vmax = Math.max.apply(null, all);
    var span = (vmax - vmin) || 1;
    function X(i){ return TS.x0 + (n > 1 ? i / (n - 1) : 0) * (TS.x1 - TS.x0); }
    function Y(v){ return TS.y1 - (Number(v) - vmin) / span * (TS.y1 - TS.y0); }
    function poly(key, arr){
      var el = svg.querySelector('polyline[data-key="' + key + '"]');
      if (!el) return;
      var p = [];
      for (var i = 0; i < n; i++) p.push(X(i).toFixed(1) + "," + Y(arr[i]).toFixed(1));
      el.setAttribute("points", p.join(" "));
    }
    poly("var_path", vp); poly("es_path", ep);
    function dots(series, arr){
      var ds = svg.querySelectorAll('circle[data-series="' + series + '"]');
      for (var i = 0; i < ds.length; i++){
        var idx = Number(ds[i].getAttribute("data-i"));
        if (idx < n && isFinite(Number(arr[idx]))){
          ds[i].setAttribute("cx", X(idx).toFixed(1));
          ds[i].setAttribute("cy", Y(arr[idx]).toFixed(1));
        }
      }
    }
    dots("var", vp); dots("es", ep);
    function endlab(key, arr){
      var t = svg.querySelector('text[data-key="' + key + '"]');
      if (t){ t.setAttribute("y", (Y(arr[n - 1]) + 3).toFixed(1));
        t.textContent = cur + fmt(arr[n - 1], 0); }
    }
    endlab("final_var", vp); endlab("final_es", ep);
    var rec = Number(tail.recommended_n_outer), mi = n - 1;
    for (var i = 0; i < n; i++){ if (Number(grid[i]) === rec){ mi = i; break; } }
    var mxp = X(mi);
    var line = svg.querySelector('line[data-key="recommended_n_outer"]');
    if (line){ line.setAttribute("x1", mxp.toFixed(1)); line.setAttribute("x2", mxp.toFixed(1)); }
    var nlab = svg.querySelector('text.tnlab[data-key="recommended_n_outer"]');
    if (nlab){ nlab.setAttribute("x", mxp.toFixed(1));
      nlab.textContent = "n* = " + fmt(rec, 0); }
    var gf = svg.querySelector('text[data-key="grid_first"]');
    if (gf){ gf.setAttribute("x", X(0).toFixed(1)); gf.textContent = fmt(grid[0], 0); }
    var gl = svg.querySelector('text[data-key="grid_last"]');
    if (gl){ gl.setAttribute("x", X(n - 1).toFixed(1)); gl.textContent = fmt(grid[n - 1], 0); }
  }
  // Redraw the VaR/ES point-vs-CI band strip from a (possibly loaded) snapshot. Pure display:
  // coordinates = value/range scaling on a shared scale, mirroring _tailci_svg in the builder.
  function redrawTailCI(tail, cur){
    var svg = document.getElementById("tailci");
    if (!svg || !tail) return;
    var vci = tail.var_ci || [], eci = tail.es_ci || [];
    var rows = [
      { s:"civar", lo:Number(vci[0]), hi:Number(vci[1]), pt:Number(tail.final_var), y:TCI.vy },
      { s:"cies",  lo:Number(eci[0]), hi:Number(eci[1]), pt:Number(tail.final_es), y:TCI.ey }
    ];
    var all = [];
    rows.forEach(function(r){ [r.lo, r.hi].forEach(function(v){ if (isFinite(v)) all.push(v); }); });
    if (all.length < 2) return;
    var vmin = Math.min.apply(null, all), vmax = Math.max.apply(null, all);
    var span = (vmax - vmin) || 1;
    function X(v){ return TCI.x0 + (Number(v) - vmin) / span * (TCI.x1 - TCI.x0); }
    rows.forEach(function(r){
      var band = svg.querySelector('rect.ciband[data-series="' + r.s + '"]');
      if (band && isFinite(r.lo) && isFinite(r.hi)){
        band.setAttribute("x", X(r.lo).toFixed(1));
        band.setAttribute("width", Math.max(0, X(r.hi) - X(r.lo)).toFixed(1));
      }
      var tick = svg.querySelector('line.cipt[data-series="' + r.s + '"]');
      if (tick && isFinite(r.pt)){
        tick.setAttribute("x1", X(r.pt).toFixed(1));
        tick.setAttribute("x2", X(r.pt).toFixed(1));
      }
      var pv = svg.querySelector('text.civ[data-series="' + r.s + '"]');
      if (pv && isFinite(r.pt)) pv.textContent = cur + fmt(r.pt, 0);
      var rg = svg.querySelector('text.cirange[data-series="' + r.s + '"]');
      if (rg && isFinite(r.lo) && isFinite(r.hi)){
        rg.setAttribute("x", ((X(r.lo) + X(r.hi)) / 2).toFixed(1));
        rg.textContent = fmt(r.lo, 0) + " to " + fmt(r.hi, 0);
      }
    });
  }
  // coordinates = value/range scaling on a shared scale, mirroring _nestedci_svg in builder.
  function redrawNestedCI(tail, cur){
    var svg = document.getElementById("nestedci");
    if (!svg || !tail) return;
    var vci = tail.var_ci || [], nci = tail.nested_var_ci || [], pt = Number(tail.final_var);
    var rows = [
      { s:"ncicopula", lo:Number(vci[0]), hi:Number(vci[1]), pt:pt, y:NCI.vy },
      { s:"ncinested", lo:Number(nci[0]), hi:Number(nci[1]), pt:pt, y:NCI.ey }
    ];
    var all = [];
    rows.forEach(function(r){ [r.lo, r.hi].forEach(function(v){ if (isFinite(v)) all.push(v); }); });
    if (all.length < 2) return;
    var vmin = Math.min.apply(null, all), vmax = Math.max.apply(null, all);
    var span = (vmax - vmin) || 1;
    function X(v){ return NCI.x0 + (Number(v) - vmin) / span * (NCI.x1 - NCI.x0); }
    rows.forEach(function(r){
      var band = svg.querySelector('rect.nciband[data-series="' + r.s + '"]');
      if (band && isFinite(r.lo) && isFinite(r.hi)){
        band.setAttribute("x", X(r.lo).toFixed(1));
        band.setAttribute("width", Math.max(0, X(r.hi) - X(r.lo)).toFixed(1));
      }
      var tick = svg.querySelector('line.ncipt[data-series="' + r.s + '"]');
      if (tick && isFinite(r.pt)){
        tick.setAttribute("x1", X(r.pt).toFixed(1));
        tick.setAttribute("x2", X(r.pt).toFixed(1));
      }
      var pv = svg.querySelector('text.nciv[data-series="' + r.s + '"]');
      if (pv && isFinite(r.pt)) pv.textContent = cur + fmt(r.pt, 0);
      var rg = svg.querySelector('text.ncirange[data-series="' + r.s + '"]');
      if (rg && isFinite(r.lo) && isFinite(r.hi)){
        rg.setAttribute("x", ((X(r.lo) + X(r.hi)) / 2).toFixed(1));
        rg.textContent = fmt(r.lo, 0) + " to " + fmt(r.hi, 0);
      }
    });
  }
  function render(ex, fromLoad){
    var figs = document.getElementById("figs");
    var prev = [].map.call(figs.querySelectorAll(".fv"), function(n){ return n.textContent; });
    figs.innerHTML = ex.figs.map(function(p, i){
      var changed = fromLoad && prev[i] !== undefined && prev[i] !== p[1];
      return '<div class="fig' + (changed ? ' changed' : '') + '"><span class="fl">' +
        esc(p[0]) + '</span><span class="fv">' + esc(p[1]) + '</span></div>';
    }).join("");
    setText("hv", ex.mv); setText("hc", ex.cv); setText("hs", ex.snap);
  }
  function banner(kind, msg){
    var b = document.getElementById("lbanner");
    if (b){ b.className = "lbanner " + kind; b.textContent = msg; }
  }
  function looksLikeSnapshot(d){
    return d && typeof d === "object" &&
      (d.summary || d.capital || d.owner_decision_p31 || d.contract_version);
  }
  function loadText(text, name){
    var d;
    try { d = JSON.parse(text); }
    catch(e){ banner("err", "Could not parse " + name + ": not valid JSON (" + e.message +
      "). Figures unchanged."); return; }
    if (!looksLikeSnapshot(d)){ banner("err", name + " does not look like a ui_data.json " +
      "snapshot (no summary / capital / contract_version). Figures unchanged."); return; }
    try {
      render(extract(d), true);
      try { var _cur = (((d.meta || {}).currency || {}).symbol) || "";
        redrawBridge(d.capital || {}, _cur); } catch(e){}
      try { var _cur2 = (((d.meta || {}).currency || {}).symbol) || "";
        redrawDrivers(d.capital || {}, _cur2); } catch(e){}
      try { var _cur3 = (((d.meta || {}).currency || {}).symbol) || "";
        redrawTail(d.tail || {}, _cur3); } catch(e){}
      try { var _cur4 = (((d.meta || {}).currency || {}).symbol) || "";
        redrawTailCI(d.tail || {}, _cur4); } catch(e){}
      try { var _cur5 = (((d.meta || {}).currency || {}).symbol) || "";
        redrawNestedCI(d.tail || {}, _cur5); } catch(e){}
      var c = d.contract_version ? (" \\u00b7 contract " + d.contract_version) : "";
      banner("ok", "Loaded " + name + c + " \\u00b7 read locally, no network. Built-in " +
        "governed snapshot unchanged \\u2014 click Reset to restore.");
    } catch(e){ banner("err", "Failed to render " + name + ": " + e.message +
      ". Figures unchanged."); }
  }
  document.addEventListener("DOMContentLoaded", function(){
    var figs = document.getElementById("figs");
    if (!figs) return;
    DEFAULT.figsHTML = figs.innerHTML;
    DEFAULT.hv = (document.getElementById("hv") || {}).textContent || "";
    DEFAULT.hc = (document.getElementById("hc") || {}).textContent || "";
    DEFAULT.hs = (document.getElementById("hs") || {}).textContent || "";
    var _b0 = document.getElementById("capbridge");
    DEFAULT.bridgeHTML = _b0 ? _b0.innerHTML : null;
    var _d0 = document.getElementById("driverbars");
    DEFAULT.driversHTML = _d0 ? _d0.innerHTML : null;
    var _t0 = document.getElementById("tailspark");
    DEFAULT.tailHTML = _t0 ? _t0.innerHTML : null;
    var _tc0 = document.getElementById("tailci");
    DEFAULT.tailciHTML = _tc0 ? _tc0.innerHTML : null;
    var _nc0 = document.getElementById("nestedci");
    DEFAULT.nestedciHTML = _nc0 ? _nc0.innerHTML : null;
    var drop = document.getElementById("drop"), file = document.getElementById("file");
    if (!drop || !file) return;
    function readFile(f){
      if (!f) return;
      var r = new FileReader();
      r.onload = function(){ loadText(String(r.result), f.name); };
      r.onerror = function(){ banner("err", "Could not read the file. Figures unchanged."); };
      r.readAsText(f);
    }
    drop.addEventListener("click", function(){ file.click(); });
    drop.addEventListener("keydown", function(e){
      if (e.key === "Enter" || e.key === " "){ e.preventDefault(); file.click(); }
    });
    file.addEventListener("change", function(){ readFile(file.files && file.files[0]); });
    ["dragenter","dragover"].forEach(function(ev){
      drop.addEventListener(ev, function(e){ e.preventDefault(); e.stopPropagation();
        drop.classList.add("hover"); });
    });
    ["dragleave","drop"].forEach(function(ev){
      drop.addEventListener(ev, function(e){ e.preventDefault(); e.stopPropagation();
        drop.classList.remove("hover"); });
    });
    drop.addEventListener("drop", function(e){
      var dt = e.dataTransfer;
      if (dt && dt.files && dt.files.length) readFile(dt.files[0]);
    });
    var rb = document.getElementById("reset");
    if (rb) rb.addEventListener("click", function(){
      figs.innerHTML = DEFAULT.figsHTML;
      setText("hv", DEFAULT.hv); setText("hc", DEFAULT.hc); setText("hs", DEFAULT.hs);
      var _bsvg = document.getElementById("capbridge");
      if (_bsvg && DEFAULT.bridgeHTML != null) _bsvg.innerHTML = DEFAULT.bridgeHTML;
      var _dsvg = document.getElementById("driverbars");
      if (_dsvg && DEFAULT.driversHTML != null) _dsvg.innerHTML = DEFAULT.driversHTML;
      var _tsvg = document.getElementById("tailspark");
      if (_tsvg && DEFAULT.tailHTML != null) _tsvg.innerHTML = DEFAULT.tailHTML;
      var _tcsvg = document.getElementById("tailci");
      if (_tcsvg && DEFAULT.tailciHTML != null) _tcsvg.innerHTML = DEFAULT.tailciHTML;
      var _ncsvg = document.getElementById("nestedci");
      if (_ncsvg && DEFAULT.nestedciHTML != null) _ncsvg.innerHTML = DEFAULT.nestedciHTML;
      banner("ok", "Restored the built-in governed snapshot.");
    });
  });
})();
</script>"""

def _fmt(x, dp=0):
    try:
        return f"{float(x):,.{dp}f}"
    except Exception:
        return html.escape(str(x))

def _capbridge_svg(cap, cur):
    """Build an inline-SVG horizontal bar chart of three GOVERNED capital figures.

    Pure display: bar length = value / max(value) scaled to CAPBRIDGE_MAXW px. Derives no
    new number; the visible gap from the standalone sum down to the nested SCR is the
    diversification effect, shown implicitly (not computed). Each <rect>/<text> carries a
    ``data-key`` so the snapshot-loader JS can redraw it from a freshly loaded snapshot.
    """
    rows = [
        ("standalone_sum", "Standalone sum (pre-diversification)", "s0"),
        ("correlated_scr", "Var-covar / correlated SCR", "s1"),
        ("nested_scr", "Nested 99.5% SCR", "s2"),
    ]
    vals = []
    for k, _label, _cls in rows:
        try:
            vals.append(float(cap.get(k)))
        except (TypeError, ValueError):
            vals.append(None)
    present = [v for v in vals if v is not None]
    mx = max(present) if present else 0.0
    top, row_h, bar_h = 8, 46, 18
    parts = []
    for i, (k, label, cls) in enumerate(rows):
        v = vals[i]
        label_y = top + i * row_h + 12
        bar_y = top + i * row_h + 18
        w = (v / mx * CAPBRIDGE_MAXW) if (v is not None and mx > 0) else 0.0
        vtxt = f"{cur}{_fmt(v, 0)}" if v is not None else "n/a"
        parts.append(
            f'<text class="cbar-label" x="2" y="{label_y}">{html.escape(label)}</text>'
            f'<rect class="cbar {cls}" data-key="{k}" x="2" y="{bar_y}" rx="4" '
            f'width="{w:.1f}" height="{bar_h}"></rect>'
            f'<text class="cbval" data-key="{k}" x="{w + 8:.1f}" '
            f'y="{bar_y + bar_h - 4}">{html.escape(vtxt)}</text>')
    height = top + len(rows) * row_h + 4
    return (
        f'<svg id="capbridge" viewBox="0 0 560 {height}" role="img" '
        f'aria-label="Capital comparison bar chart: standalone sum, var-covar SCR and '
        f'nested 99.5% SCR, read verbatim from the model-output snapshot.">\n    '
        + "\n    ".join(parts) + "\n  </svg>")

def _driverbars_svg(cap, cur):
    """Inline-SVG horizontal mini bar set of the seven GOVERNED standalone per-driver SCRs.

    Pure display: bar length = value / max(value) scaled to DRIVERBARS_MAXW px. Derives no
    new number; the seven charges sum to the governed standalone_sum (shown above and gate-
    asserted). Rows are baked sorted by magnitude for readability; each <rect>/<text> carries
    a ``data-key`` so the snapshot-loader JS can redraw each row from a freshly loaded
    snapshot (re-sorting is unnecessary -- only widths/values change).
    """
    rows = []
    for k, label in _DRIVER_ROWS:
        try:
            v = float(cap.get(k))
        except (TypeError, ValueError):
            v = None
        rows.append((k, label, v))
    rows.sort(key=lambda r: (r[2] is not None, r[2] if r[2] is not None else 0.0),
              reverse=True)
    present = [r[2] for r in rows if r[2] is not None]
    mx = max(present) if present else 0.0
    top, row_h, bar_h = 6, 34, 15
    parts = []
    for i, (k, label, v) in enumerate(rows):
        label_y = top + i * row_h + 11
        bar_y = top + i * row_h + 16
        w = (v / mx * DRIVERBARS_MAXW) if (v is not None and mx > 0) else 0.0
        vtxt = f"{cur}{_fmt(v, 0)}" if v is not None else "n/a"
        parts.append(
            f'<text class="dbar-label" x="2" y="{label_y}">{html.escape(label)}</text>'
            f'<rect class="dbar" data-key="{k}" x="2" y="{bar_y}" rx="3" '
            f'width="{w:.1f}" height="{bar_h}"></rect>'
            f'<text class="dbval" data-key="{k}" x="{w + 8:.1f}" '
            f'y="{bar_y + bar_h - 3}">{html.escape(vtxt)}</text>')
    height = top + len(rows) * row_h + 4
    return (
        f'<svg id="driverbars" viewBox="0 0 560 {height}" role="img" '
        f'aria-label="Standalone SCR by risk driver bar chart: seven per-driver standalone '
        f'capital charges, read verbatim from the model-output snapshot.">\n    '
        + "\n    ".join(parts) + "\n  </svg>")

def _tailspark_svg(tail, cur):
    """Inline-SVG convergence sparkline of the GOVERNED tail diagnostic.

    Pure display: the 99.5% VaR and ES liability estimates (``var_path`` / ``es_path``) are
    plotted against the outer-scenario grid (``outer_grid``); each coordinate is a value/range
    scaling of a governed number -- no number is derived. A dashed marker sits at the governed
    recommended outer count ``recommended_n_outer`` (= n*, where the model declares the tail
    estimate converged). Each element carries a ``data-key``/``data-series`` so the snapshot-
    loader JS can redraw it from a freshly loaded snapshot (mirrors ``redrawTail`` in LOADER_JS).
    """
    grid = list(tail.get("outer_grid") or [])
    vp = list(tail.get("var_path") or [])
    ep = list(tail.get("es_path") or [])
    n = min(len(grid), len(vp), len(ep))
    g = TAILSPARK_GEO
    x0, x1, y0, y1 = g["x0"], g["x1"], g["y0"], g["y1"]
    nums = []
    for v in (vp[:n] + ep[:n]):
        try:
            nums.append(float(v))
        except (TypeError, ValueError):
            pass
    vmin = min(nums) if nums else 0.0
    vmax = max(nums) if nums else 1.0
    span = (vmax - vmin) or 1.0

    def X(i):
        return x0 + (i / (n - 1) if n > 1 else 0.0) * (x1 - x0)

    def Y(v):
        return y1 - (float(v) - vmin) / span * (y1 - y0)

    def _poly(key, cls, arr):
        pts = " ".join(f"{X(i):.1f},{Y(arr[i]):.1f}" for i in range(n))
        return f'<polyline class="{cls}" data-key="{key}" points="{pts}"></polyline>'

    def _dots(series, cls, arr):
        return "\n    ".join(
            f'<circle class="tdot {cls}" data-series="{series}" data-i="{i}" '
            f'cx="{X(i):.1f}" cy="{Y(arr[i]):.1f}" r="3"></circle>' for i in range(n))

    # n* marker: governed recommended outer count (index in the grid; default rightmost).
    rec = tail.get("recommended_n_outer")
    mi = n - 1 if n else 0
    for i in range(n):
        try:
            if float(grid[i]) == float(rec):
                mi = i
                break
        except (TypeError, ValueError):
            pass
    mx = X(mi) if n else x1
    rec_txt = _fmt(rec, 0) if rec is not None else "n/a"

    parts = []
    # baseline
    parts.append(f'<line class="tbase" x1="{x0:.1f}" y1="{y1:.1f}" '
                 f'x2="{x1:.1f}" y2="{y1:.1f}"></line>')
    # n* marker line + label (drawn first so the series lines sit on top)
    parts.append(f'<line class="tnstar" data-key="recommended_n_outer" x1="{mx:.1f}" '
                 f'y1="{y0:.1f}" x2="{mx:.1f}" y2="{y1:.1f}"></line>')
    parts.append(f'<text class="tnlab" data-key="recommended_n_outer" x="{mx:.1f}" '
                 f'y="{y0 - 3:.1f}">n* = {html.escape(rec_txt)}</text>')
    # series polylines + dots
    if n:
        parts.append(_poly("var_path", "tvar", vp))
        parts.append(_poly("es_path", "tes", ep))
        parts.append(_dots("var", "var", vp))
        parts.append(_dots("es", "es", ep))
        # end value labels (governed final VaR / ES, verbatim)
        fv = tail.get("final_var", vp[n - 1] if n else None)
        fe = tail.get("final_es", ep[n - 1] if n else None)
        parts.append(
            f'<text class="tval var" data-key="final_var" x="{x1 + 4:.1f}" '
            f'y="{Y(vp[n - 1]) + 3:.1f}">{html.escape(cur + _fmt(fv, 0))}</text>')
        parts.append(
            f'<text class="tval es" data-key="final_es" x="{x1 + 4:.1f}" '
            f'y="{Y(ep[n - 1]) + 3:.1f}">{html.escape(cur + _fmt(fe, 0))}</text>')
        # x-axis endpoint labels (governed grid first/last, verbatim)
        parts.append(f'<text class="taxis" data-key="grid_first" text-anchor="start" '
                     f'x="{X(0):.1f}" y="{y1 + 14:.1f}">{html.escape(_fmt(grid[0], 0))}</text>')
        parts.append(f'<text class="taxis" data-key="grid_last" text-anchor="end" '
                     f'x="{X(n - 1):.1f}" y="{y1 + 14:.1f}">'
                     f'{html.escape(_fmt(grid[n - 1], 0))}</text>')
    parts.append(f'<text class="taxis" text-anchor="middle" x="{(x0 + x1) / 2:.1f}" '
                 f'y="{y1 + 14:.1f}">outer scenarios &rarr;</text>')
    height = int(y1 + 22)
    return (
        f'<svg id="tailspark" viewBox="0 0 560 {height}" role="img" '
        f'aria-label="Tail-convergence sparkline: 99.5% VaR and ES liability estimates '
        f'plotted against the outer-scenario count, with a marker at the governed '
        f'recommended count n*. Read verbatim from the model-output snapshot.">\n    '
        + "\n    ".join(parts) + "\n  </svg>")

def _tailci_svg(tail, cur):
    """Inline-SVG strip of the GOVERNED 99.5% VaR / ES estimates with their CI bands.

    Pure display: each row draws the governed Monte-Carlo confidence interval (``var_ci`` /
    ``es_ci``) as a band and marks the governed point estimate (``final_var`` / ``final_es``)
    on it. Every x-coordinate is a value/range scaling of a governed number on a single shared
    scale spanning the four CI endpoints -- no number is derived. Each element carries a
    ``data-series`` so the snapshot-loader JS can redraw it (mirrors ``redrawTailCI``).
    """
    g = TAILCI_GEO
    x0, x1 = g["x0"], g["x1"]
    rows = [
        ("var", "99.5% VaR", tail.get("var_ci") or [], tail.get("final_var"), g["vy"]),
        ("es", "99.5% ES", tail.get("es_ci") or [], tail.get("final_es"), g["ey"]),
    ]
    ends = []
    for _s, _l, ci, _pt, _y in rows:
        if len(ci) >= 2:
            try:
                ends.append(float(ci[0])); ends.append(float(ci[1]))
            except (TypeError, ValueError):
                pass
    vmin = min(ends) if ends else 0.0
    vmax = max(ends) if ends else 1.0
    span = (vmax - vmin) or 1.0

    def X(v):
        return x0 + (float(v) - vmin) / span * (x1 - x0)

    bh = g["bh"]
    parts = []
    for s, label, ci, pt, y in rows:
        parts.append(f'<line class="citrack" x1="{x0:.1f}" y1="{y:.1f}" '
                     f'x2="{x1:.1f}" y2="{y:.1f}"></line>')
        parts.append(f'<text class="cilab" x="2" y="{y + 4:.1f}">{html.escape(label)}</text>')
        if len(ci) >= 2:
            lo, hi = float(ci[0]), float(ci[1])
            bx, bw = X(lo), max(0.0, X(hi) - X(lo))
            parts.append(f'<rect class="ciband {s}" data-series="ci{s}" x="{bx:.1f}" '
                         f'y="{y - bh / 2:.1f}" width="{bw:.1f}" height="{bh:.1f}" rx="3"></rect>')
            cx = (X(lo) + X(hi)) / 2
            parts.append(f'<text class="cirange" data-series="ci{s}" x="{cx:.1f}" '
                         f'y="{y + bh / 2 + 12:.1f}">{html.escape(_fmt(lo, 0))} to '
                         f'{html.escape(_fmt(hi, 0))}</text>')
        if pt is not None:
            px = X(pt)
            parts.append(f'<line class="cipt {s}" data-series="ci{s}" x1="{px:.1f}" '
                         f'y1="{y - bh / 2 - 3:.1f}" x2="{px:.1f}" '
                         f'y2="{y + bh / 2 + 3:.1f}"></line>')
            parts.append(f'<text class="civ {s}" data-series="ci{s}" text-anchor="start" '
                         f'x="{x1 + 6:.1f}" y="{y + 4:.1f}">'
                         f'{html.escape(cur + _fmt(pt, 0))}</text>')
    height = int(g["ey"] + bh / 2 + 18)
    return (
        f'<svg id="tailci" viewBox="0 0 560 {height}" role="img" '
        f'aria-label="VaR/ES confidence-interval strip: the governed 99.5% VaR and ES '
        f'estimates each shown as a Monte-Carlo confidence band with the point estimate '
        f'marked. Read verbatim from the model-output snapshot.">\n    '
        + "\n    ".join(parts) + "\n  </svg>")

def _nestedci_svg(tail, cur):
    """Inline-SVG comparison of the GOVERNED 99.5% VaR estimate's confidence band from two
    estimators on one shared scale: the copula-simulated band (``var_ci``) vs the nested
    estimator's band (``nested_var_ci`` at ``nested_n_outer`` outer scenarios). Both rows mark
    the same governed point (``final_var``). Every x-coordinate is a value/range scaling of a
    governed number -- no number is derived. Mirrors ``redrawNestedCI`` in LOADER_JS.
    """
    g = NESTEDCI_GEO
    x0, x1 = g["x0"], g["x1"]
    n_outer = tail.get("nested_n_outer")
    nlbl = ("Nested VaR (n=%s)" % _fmt(n_outer, 0)) if n_outer is not None else "Nested VaR"
    pt = tail.get("final_var")
    rows = [
        ("copula", "Copula VaR", tail.get("var_ci") or [], pt, g["vy"]),
        ("nested", nlbl, tail.get("nested_var_ci") or [], pt, g["ey"]),
    ]
    ends = []
    for _s, _l, ci, _pt, _y in rows:
        if len(ci) >= 2:
            try:
                ends.append(float(ci[0])); ends.append(float(ci[1]))
            except (TypeError, ValueError):
                pass
    vmin = min(ends) if ends else 0.0
    vmax = max(ends) if ends else 1.0
    span = (vmax - vmin) or 1.0

    def X(v):
        return x0 + (float(v) - vmin) / span * (x1 - x0)

    bh = g["bh"]
    parts = []
    for s, label, ci, pt_, y in rows:
        parts.append(f'<line class="ncitrack" x1="{x0:.1f}" y1="{y:.1f}" '
                     f'x2="{x1:.1f}" y2="{y:.1f}"></line>')
        parts.append(f'<text class="ncilab" x="2" y="{y + 4:.1f}">{html.escape(label)}</text>')
        if len(ci) >= 2:
            lo, hi = float(ci[0]), float(ci[1])
            bx, bw = X(lo), max(0.0, X(hi) - X(lo))
            parts.append(f'<rect class="nciband {s}" data-series="nci{s}" x="{bx:.1f}" '
                         f'y="{y - bh / 2:.1f}" width="{bw:.1f}" height="{bh:.1f}" rx="3"></rect>')
            cx = (X(lo) + X(hi)) / 2
            parts.append(f'<text class="ncirange" data-series="nci{s}" x="{cx:.1f}" '
                         f'y="{y + bh / 2 + 12:.1f}">{html.escape(_fmt(lo, 0))} to '
                         f'{html.escape(_fmt(hi, 0))}</text>')
        if pt_ is not None:
            px = X(pt_)
            parts.append(f'<line class="ncipt {s}" data-series="nci{s}" x1="{px:.1f}" '
                         f'y1="{y - bh / 2 - 3:.1f}" x2="{px:.1f}" '
                         f'y2="{y + bh / 2 + 3:.1f}"></line>')
            parts.append(f'<text class="nciv {s}" data-series="nci{s}" text-anchor="start" '
                         f'x="{x1 + 6:.1f}" y="{y + 4:.1f}">'
                         f'{html.escape(cur + _fmt(pt_, 0))}</text>')
    height = int(g["ey"] + bh / 2 + 18)
    return (
        f'<svg id="nestedci" viewBox="0 0 560 {height}" role="img" '
        f'aria-label="Nested vs copula-simulated VaR confidence-interval comparison: the '
        f'governed 99.5% VaR shown as the copula-simulated band and the wider nested-estimator '
        f'band on a shared scale, with the governed point marked. Read verbatim from the '
        f'model-output snapshot.">\n    '
        + "\n    ".join(parts) + "\n  </svg>")

def build() -> str:
    d = json.loads(UI_DATA.read_text(encoding="utf-8"))
    meta = d.get("meta", {})
    cap = d.get("capital", {})
    s = d.get("summary", {})
    cur = (meta.get("currency", {}) or {}).get("symbol", "")
    headline = d["owner_decision_p31"]["evidence_pack"]["governed_headline"]["value"]
    src_sha = hashlib.sha256(UI_DATA.read_bytes()).hexdigest()
    built = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # Curated, governed figures -- copied verbatim from model output, nothing derived.
    figures = [
        ("Governed headline SCR component (frozen-t)", f"{cur}{_fmt(headline,2)}"),
        ("Nested 99.5% SCR", f"{cur}{_fmt(cap.get('nested_scr'))}"),
        ("Var-covar / correlated SCR", f"{cur}{_fmt(cap.get('correlated_scr'))}"),
        ("Standalone sum (pre-diversification)", f"{cur}{_fmt(cap.get('standalone_sum'))}"),
        ("Diversification benefit (nested)", f"{cur}{_fmt(cap.get('div_benefit_nested'))}"),
        ("Risk drivers (calibrated)", _fmt(s.get("calibrated_drivers"))),
        ("Deployment gates cleared", f"{s.get('gates_cleared')}/{s.get('gates_total')}"),
        ("Tasks complete", f"{s.get('tasks_completed')}/{s.get('tasks_total')}"),
    ]

    cards = []
    for href, title, desc, zero in VIEWS:
        badge = ('<span class="badge zi">Zero-install</span>' if zero
                 else '<span class="badge py">Needs Python</span>')
        cards.append(f'''      <a class="card" href="{html.escape(href)}" data-view="{html.escape(href)}">
        <div class="card-h"><span class="card-t">{title}</span>{badge}</div>
        <p class="card-d">{desc}</p>
        <span class="open">Open &rarr;</span>
      </a>''')

    figrows = "\n".join(
        f'      <div class="fig"><span class="fl">{html.escape(l)}</span>'
        f'<span class="fv">{v}</span></div>' for l, v in figures)
    cardhtml = "\n".join(cards)
    capbridge = _capbridge_svg(cap, cur)
    driverbars = _driverbars_svg(cap, cur)
    _tail = d.get("tail", {}) or {}
    tailspark = _tailspark_svg(_tail, cur)
    tailci = _tailci_svg(_tail, cur)
    nestedci = _nestedci_svg(_tail, cur)
    _tgrid = list(_tail.get("outer_grid") or [])
    _t_lo = _fmt(_tgrid[0], 0) if _tgrid else "n/a"
    _t_hi = _fmt(_tgrid[-1], 0) if _tgrid else "n/a"
    _t_nstar = _fmt(_tail.get("recommended_n_outer"), 0)
    _t_converged = "converged" if _tail.get("converged") else "not yet converged"
    _nci_nouter = _fmt(_tail.get("nested_n_outer"), 0)

    # Build-time link-existence assertion (offline-UI option e): every VIEWS href
    # -- and, by the chooser-drift check below, every CHOOSER href, which must be a
    # VIEWS entry -- MUST resolve to a file that actually exists on disk at build
    # time, so the landing page can never ship a link to a missing view. Static
    # check; reads nothing from the network, derives/changes no governed figure.
    _missing = []
    for _v in VIEWS:
        _href = _v[0]
        # hrefs are plain relative paths; defend against any future anchor/query.
        _rel = _href.split("#", 1)[0].split("?", 1)[0]
        if not (ROOT / _rel).exists():
            _missing.append(_href)
    if _missing:
        raise SystemExit(
            "FAIL: offline_home would link to missing view target(s): "
            + ", ".join(sorted(_missing))
            + " (every VIEWS href must exist on disk at build time)")

    # Build the "which view do I want?" chooser; assert it never drifts from VIEWS.
    _view_hrefs = {v[0] for v in VIEWS}
    crows = []
    for goal, chref, clabel, czero in CHOOSER:
        assert chref in _view_hrefs, f"chooser href not in VIEWS: {chref}"
        cbadge = ('<span class="badge zi">Zero-install</span>' if czero
                  else '<span class="badge py">Needs Python</span>')
        crows.append(
            f'      <div class="crow">\n'
            f'        <span class="cgoal">{goal}</span>\n'
            f'        <span class="cpick"><a href="{html.escape(chref)}">{clabel} '
            f'&rarr;</a>{cbadge}</span>\n'
            f'      </div>')
    chooserhtml = "\n".join(crows)

    return f'''<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Actuarial Stochastic Model -- Offline Home</title>
<style>
  :root {{ --bg:#0f1722; --panel:#16212e; --ink:#e8eef5; --mut:#9fb0c3;
    --acc:#4ea1ff; --line:#26384b; --ok:#2ec27e; --warn:#e8b23a; }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; font:15px/1.5 -apple-system,Segoe UI,Roboto,Arial,sans-serif;
    background:var(--bg); color:var(--ink); }}
  .wrap {{ max-width:1040px; margin:0 auto; padding:28px 20px 56px; }}
  header h1 {{ margin:0 0 4px; font-size:24px; }}
  .sub {{ color:var(--mut); margin:0 0 2px; }}
  .class {{ display:inline-block; margin-top:10px; padding:4px 10px; border-radius:6px;
    background:#3a2c12; color:var(--warn); font-size:12.5px; font-weight:600;
    border:1px solid #5a4519; }}
  h2 {{ font-size:15px; text-transform:uppercase; letter-spacing:.06em;
    color:var(--mut); margin:30px 0 12px; }}
  .figs {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(230px,1fr));
    gap:10px; }}
  .fig {{ background:var(--panel); border:1px solid var(--line); border-radius:9px;
    padding:12px 14px; display:flex; flex-direction:column; gap:4px; }}
  .fl {{ color:var(--mut); font-size:12.5px; }}
  .fv {{ font-size:19px; font-weight:650; font-variant-numeric:tabular-nums; }}
  .cards {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(300px,1fr));
    gap:14px; }}
  .card {{ background:var(--panel); border:1px solid var(--line); border-radius:11px;
    padding:16px 17px; text-decoration:none; color:var(--ink); display:flex;
    flex-direction:column; gap:8px; transition:border-color .15s, transform .15s; }}
  .card:hover {{ border-color:var(--acc); transform:translateY(-2px); }}
  .card-h {{ display:flex; align-items:center; justify-content:space-between; gap:8px; }}
  .card-t {{ font-size:16px; font-weight:650; }}
  .card-d {{ margin:0; color:var(--mut); font-size:13.5px; flex:1; }}
  .badge {{ font-size:11px; font-weight:700; padding:2px 8px; border-radius:20px;
    white-space:nowrap; }}
  .badge.zi {{ background:#11321f; color:var(--ok); border:1px solid #1c5436; }}
  .badge.py {{ background:#2a2030; color:#d49bff; border:1px solid #4a325a; }}
  .open {{ color:var(--acc); font-weight:600; font-size:13.5px; }}
  footer {{ margin-top:34px; padding-top:16px; border-top:1px solid var(--line);
    color:var(--mut); font-size:12px; }}
  code {{ background:#0c141d; padding:1px 5px; border-radius:4px; }}
  a.src {{ color:var(--acc); }}{LOADER_CSS}{CHOOSER_CSS}{A11Y_CSS}{CAPBRIDGE_CSS}{DRIVERBARS_CSS}{TAILSPARK_CSS}{TAILCI_CSS}{NESTEDCI_CSS}
</style></head>
<body>
  <a class="skip" href="#main">Skip to main content</a>
  <main id="main" class="wrap" tabindex="-1">
  <header>
    <h1>{html.escape(meta.get("model_name","Actuarial Stochastic Model"))}</h1>
    <p class="sub">Offline home &mdash; one place to open every result view. No internet,
      no install, no server required.</p>
    <p class="sub">Model version <b id="hv">{html.escape(str(meta.get("model_version","")))}</b>
      &middot; data contract <b id="hc">{html.escape(str(d.get("contract_version","")))}</b>
      &middot; snapshot <span id="hs">{html.escape(str(meta.get("generated_utc","")))}</span></p>
    <p class="start">New here? <b>Start with the Full Results Explorer</b> below for the
      complete read-only results, or use the &ldquo;Which view do I want?&rdquo; chooser to
      pick by goal. Every view is read-only and changes no governed figure.</p>
    <span class="class">{html.escape(meta.get("classification","EDUCATIONAL ONLY"))}</span>
  </header>

  <h2>Headline governed figures</h2>
  <div class="figs" id="figs">
{figrows}
  </div>
  <p class="sub" style="margin-top:10px; font-size:12.5px;">Figures are read verbatim
    from the model-output snapshot &mdash; this page computes nothing.</p>

  <h2>Capital at a glance</h2>
  <div class="cbridge">
  {capbridge}
  </div>
  <p class="cbcap">Bars are scaled to the largest value (the standalone sum). The visible gap
    from the standalone sum down to the nested 99.5% SCR is the diversification effect. Every
    value is read verbatim from the model-output snapshot &mdash; this chart computes nothing.</p>

  <h2>Standalone SCR by risk driver</h2>
  <div class="dbridge">
  {driverbars}
  </div>
  <p class="dbcap">Each bar is one of the seven standalone (pre-diversification) risk-driver
    capital charges, scaled to the largest driver charge. Together the seven sum to the
    standalone total shown above. Every value is read verbatim from the model-output snapshot
    &mdash; this chart computes nothing.</p>

  <h2>Tail convergence</h2>
  <div class="tspark">
  {tailspark}
  </div>
  <p class="tcap"><span class="tkey" style="background:#4ea1ff"></span>99.5% VaR
    <span class="tkey" style="background:#e8b23a"></span>99.5% ES &mdash; the governed tail
    estimates as the outer-scenario count rises from {_t_lo} to {_t_hi}. The dashed green marker
    is the recommended count <b>n* = {_t_nstar}</b>, where the model declares the tail estimate
    <b>{_t_converged}</b>. Every coordinate is read verbatim from the model-output snapshot
    &mdash; this chart computes nothing.</p>

  <h2>VaR &amp; ES with confidence intervals</h2>
  <div class="ciband-wrap">
  {tailci}
  </div>
  <p class="cicap"><span class="tkey" style="background:#4ea1ff"></span>99.5% VaR
    <span class="tkey" style="background:#e8b23a"></span>99.5% ES &mdash; each governed tail
    estimate (the vertical marker) shown with its Monte-Carlo confidence band (lighter) on a
    single shared scale, so the sampling uncertainty around the converged figures is visible.
    Every value is read verbatim from the model-output snapshot &mdash; this chart computes
    nothing.</p>

  <h2>Nested vs copula-simulated VaR &mdash; confidence intervals</h2>
  <div class="ncici-wrap">
  {nestedci}
  </div>
  <p class="ncicap"><span class="tkey" style="background:#2ec27e"></span>Copula-simulated
    <span class="tkey" style="background:#e8b23a"></span>Nested (n={_nci_nouter}) &mdash; the
    same governed 99.5% VaR point (the vertical marker) shown inside two confidence bands on
    one shared scale: the copula-simulated band (the converged estimator) is tight, while the
    nested estimator's band &mdash; computed at only {_nci_nouter} outer scenarios &mdash; is
    much wider, so the extra sampling noise of the nested route is visible. The point sits
    inside both bands. Every value is read verbatim from the model-output snapshot &mdash;
    this chart computes nothing.</p>

{LOADER_PANEL}
  <h2>Which view do I want?</h2>
  <p class="sub" style="margin-top:-4px; font-size:12.5px;">Pick by what you want to do
    &mdash; each links straight to the matching view below. Every view is read-only and
    changes no governed artifact.</p>
  <div class="chooser">
{chooserhtml}
  </div>

  <h2>Open a view</h2>
  <div class="cards">
{cardhtml}
  </div>

  <footer>
    Built {built} from <a class="src" href="ui_data.json">ui_data.json</a>
    (sha256 <code>{src_sha[:16]}&hellip;</code>). Zero-install pages are fully
    self-contained: open by double-click from a USB stick or an air-gapped machine.
    The governed result template <code>ui_app.html</code> is never modified by this page.
  </footer>
  </main>
<script>
// Offline-only guard: this page makes ZERO network calls. Provenance is embedded.
(function(){{
  var PROVENANCE = {{ contract: {json.dumps(d.get("contract_version",""))},
    headline: {json.dumps(headline)}, source_sha256: {json.dumps(src_sha)} }};
  window.__OFFLINE_HOME__ = PROVENANCE;
}})();
</script>{LOADER_JS}
</body></html>'''

def main():
    out = build()
    OUT.write_text(out, encoding="utf-8")
    # zero-install assertion: no external references may be emitted.
    bad = [t for t in ("http://", "https://", "//cdn", "googleapis", "unpkg", "jsdelivr")
           if t in out]
    if bad:
        print(f"FAIL: external reference(s) emitted: {bad}", file=sys.stderr)
        return 2
    print(f"OK wrote {OUT} ({len(out):,} bytes); 0 external refs")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
