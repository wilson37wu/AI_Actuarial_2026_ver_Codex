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
    ("launchers/README.md", "Input &amp; Run GUI",
     "Enter your own actuarial inputs and run the stochastic model end-to-end on "
     "localhost. Needs Python 3.8+ (relaxes zero-install for THIS input+run step "
     "only); your run renders into a separate copy and never edits the governed "
     "template.", False),
]

def _fmt(x, dp=0):
    try:
        return f"{float(x):,.{dp}f}"
    except Exception:
        return html.escape(str(x))

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
  a.src {{ color:var(--acc); }}
</style></head>
<body><div class="wrap">
  <header>
    <h1>{html.escape(meta.get("model_name","Actuarial Stochastic Model"))}</h1>
    <p class="sub">Offline home &mdash; one place to open every result view. No internet,
      no install, no server required.</p>
    <p class="sub">Model version <b>{html.escape(str(meta.get("model_version","")))}</b>
      &middot; data contract <b>{html.escape(str(d.get("contract_version","")))}</b>
      &middot; snapshot {html.escape(str(meta.get("generated_utc","")))}</p>
    <span class="class">{html.escape(meta.get("classification","EDUCATIONAL ONLY"))}</span>
  </header>

  <h2>Headline governed figures</h2>
  <div class="figs" id="figs">
{figrows}
  </div>
  <p class="sub" style="margin-top:10px; font-size:12.5px;">Figures are read verbatim
    from the model-output snapshot &mdash; this page computes nothing.</p>

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
</div>
<script>
// Offline-only guard: this page makes ZERO network calls. Provenance is embedded.
(function(){{
  var PROVENANCE = {{ contract: {json.dumps(d.get("contract_version",""))},
    headline: {json.dumps(headline)}, source_sha256: {json.dumps(src_sha)} }};
  window.__OFFLINE_HOME__ = PROVENANCE;
}})();
</script>
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
