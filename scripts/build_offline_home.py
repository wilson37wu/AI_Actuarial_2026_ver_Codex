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
  var DEFAULT = { figsHTML:null, hv:"", hc:"", hs:"", bridgeHTML:null };
  var CB_MAXW = 430;  // mirrors CAPBRIDGE_MAXW in scripts/build_offline_home.py
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
  a.src {{ color:var(--acc); }}{LOADER_CSS}{CHOOSER_CSS}{A11Y_CSS}{CAPBRIDGE_CSS}
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
