#!/usr/bin/env python3
"""Build model_summary_card.html -- a printable one-page model summary card.

Standing owner directive (scheduled task): "build a user interface for offline use
... it should not depend on any pre installation ... the user interface uses ONLY
the model output to display the result." This page is a single, self-contained,
PRINT-OPTIMISED summary that reads a curated set of GOVERNED figures straight from
the model-output snapshot ``ui_data.json`` and lays them out as a one-page card a
user can read on screen or print / save-as-PDF (an embedded button calls
``window.print()`` -- no network, no install).

It is the NEXT-EXECUTION-POINTER option (b) follow-on to ``offline_home.html``:
decision-neutral, ADDITIVE, zero-network. It recomputes NOTHING (every number is
copied verbatim from the snapshot), alters no governed artifact (``ui_app.html``
untouched), and introduces no ``ui_data`` contract change (it is a separate file).
stdlib only.
"""
from __future__ import annotations
import json, html, datetime, hashlib, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
UI_DATA = ROOT / "ui_data.json"
OUT = ROOT / "model_summary_card.html"


def _fmt(x, dp=0):
    try:
        return f"{float(x):,.{dp}f}"
    except Exception:
        return html.escape(str(x))


def _rows(pairs):
    return "\n".join(
        f'      <tr><th>{html.escape(l)}</th><td>{v}</td></tr>' for l, v in pairs)


def build() -> str:
    d = json.loads(UI_DATA.read_text(encoding="utf-8"))
    meta = d.get("meta", {})
    cap = d.get("capital", {})
    s = d.get("summary", {})
    tail = d.get("tail", {})
    gov = d.get("governance", {})
    cur = (meta.get("currency", {}) or {}).get("symbol", "")
    hl = d["owner_decision_p31"]["evidence_pack"]["governed_headline"]
    headline = hl["value"]
    df = hl.get("rank_invariance_df")
    src_sha = hashlib.sha256(UI_DATA.read_bytes()).hexdigest()
    built = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # --- Capital basis (all verbatim from the snapshot) ---
    capital_rows = [
        ("Nested 99.5% SCR (capital reference)", f"{cur}{_fmt(cap.get('nested_scr'))}"),
        (f"Tail-matched t-copula SCR (df {_fmt(cap.get('t_copula_df'),4)})",
         f"{cur}{_fmt(cap.get('t_copula_scr'))}"),
        (f"Selected-copula SCR ({html.escape(str(cap.get('selected_copula','')))})",
         f"{cur}{_fmt(cap.get('correlated_scr'))}"),
        ("Var-covar SCR (closed-form)", f"{cur}{_fmt(cap.get('var_covar_scr'))}"),
        ("Standalone sum (pre-diversification)", f"{cur}{_fmt(cap.get('standalone_sum'))}"),
        ("Diversification benefit (nested)", f"{cur}{_fmt(cap.get('diversification_benefit_nested'))}"),
    ]

    # --- Seven standalone risk-driver SCRs (verbatim) ---
    driver_rows = [
        ("Interest rate (G2++)", f"{cur}{_fmt(cap.get('rate_scr'))}"),
        ("Equity", f"{cur}{_fmt(cap.get('equity_scr'))}"),
        ("Credit spread", f"{cur}{_fmt(cap.get('credit_scr'))}"),
        ("Lapse", f"{cur}{_fmt(cap.get('lapse_scr'))}"),
        ("Mortality", f"{cur}{_fmt(cap.get('mortality_scr'))}"),
        ("FX", f"{cur}{_fmt(cap.get('fx_scr'))}"),
        ("Liquidity (G-LIQX-calibrated)", f"{cur}{_fmt(cap.get('liquidity_scr'))}"),
    ]

    # --- Tail / convergence (verbatim) ---
    tail_rows = [
        ("Confidence level", f"{_fmt(float(cap.get('confidence_level',0))*100,1)}%"),
        ("Risk horizon", f"{cap.get('horizon_months')} months"),
        ("VaR (point)", f"{cur}{_fmt(tail.get('var_point'))}"),
        ("Expected Shortfall (point)", f"{cur}{_fmt(tail.get('es_point'))}"),
        ("Tail convergence", "CONVERGED" if tail.get("converged") else "NOT CONVERGED"),
        ("Recommended outer scenarios", _fmt(tail.get("recommended_n_outer"))),
    ]

    # --- Validation & governance scorecard (verbatim) ---
    verds = d.get("verdicts", []) or []
    n_pass = sum(1 for v in verds
                 if "PASS" in str(v.get("verdict", "")).upper())
    score_rows = [
        ("Deployment gates cleared", f"{s.get('gates_cleared')}/{s.get('gates_total')}"),
        ("Validation verdicts PASS", f"{n_pass}/{len(verds)}"),
        ("Tasks complete", f"{s.get('tasks_completed')}/{s.get('tasks_total')}"),
        ("Phases complete", _fmt(s.get("phases_completed"))),
        ("Calibrated risk drivers", _fmt(s.get("calibrated_drivers"))),
        ("Risks open / mitigated", f"{s.get('risks_open')} / {s.get('risks_mitigated')}"),
        ("Audit entries verified", f"{gov.get('audit_verified')}/{gov.get('audit_entries')}"
         + (" (integrity OK)" if gov.get("audit_integrity_ok") else " (INTEGRITY FAIL)")),
        ("Audit chain failures", _fmt(gov.get("audit_failed"))),
    ]

    # --- Curated key validated results (short, verbatim labels) ---
    def _verd(key):
        for v in verds:
            if v.get("key") == key:
                return v.get("label", key), v.get("verdict", "")
        return None
    key_results = []
    for k in ("proxy", "aggregation", "tail"):
        r = _verd(k)
        if r:
            key_results.append(r)
    # add the tail-matched t-copula structured verdict by name match
    for v in verds:
        nm = str(v.get("name", ""))
        if "Student-t copula aggregation" in nm:
            key_results.append((nm, v.get("evidence", v.get("verdict", ""))))
            break
    kr_html = "\n".join(
        f'      <li><b>{html.escape(str(lbl))}.</b> {html.escape(str(txt))}</li>'
        for lbl, txt in key_results)

    capital_html = _rows(capital_rows)
    driver_html = _rows(driver_rows)
    tail_html = _rows(tail_rows)
    score_html = _rows(score_rows)

    return f'''<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Model Summary Card -- {html.escape(meta.get("model_name","Actuarial Stochastic Model"))}</title>
<style>
  :root {{ --ink:#10202f; --mut:#5a6b7d; --acc:#1d4e89; --line:#d4dde6;
    --panel:#f4f7fa; --ok:#1c7a4a; --warn:#9a6a12; --headhl:#eaf1fb; }}
  * {{ box-sizing:border-box; }}
  html,body {{ background:#e9edf1; }}
  body {{ margin:0; color:var(--ink);
    font:13px/1.45 -apple-system,Segoe UI,Roboto,Arial,sans-serif; }}
  .sheet {{ max-width:820px; margin:18px auto; background:#fff; color:var(--ink);
    padding:26px 30px 22px; border-radius:6px; box-shadow:0 1px 8px rgba(0,0,0,.12); }}
  header {{ border-bottom:2px solid var(--acc); padding-bottom:12px; margin-bottom:6px; }}
  .ttl {{ display:flex; justify-content:space-between; align-items:flex-start; gap:14px; }}
  h1 {{ margin:0 0 3px; font-size:20px; color:var(--acc); }}
  .sub {{ color:var(--mut); font-size:12px; margin:1px 0; }}
  .class {{ display:inline-block; margin-top:7px; padding:3px 9px; border-radius:5px;
    background:#fdf3df; color:var(--warn); font-size:11px; font-weight:700;
    border:1px solid #ecd9a8; }}
  .prod {{ display:inline-block; margin:7px 0 0 8px; padding:3px 9px; border-radius:5px;
    background:#fbe9e9; color:#a32020; font-size:11px; font-weight:700;
    border:1px solid #e6c2c2; }}
  .headline {{ background:var(--headhl); border:1px solid #cfe0f7; border-radius:8px;
    padding:13px 16px; margin:14px 0; display:flex; justify-content:space-between;
    align-items:center; gap:16px; }}
  .headline .lbl {{ color:var(--mut); font-size:11.5px; text-transform:uppercase;
    letter-spacing:.05em; }}
  .headline .val {{ font-size:27px; font-weight:750; color:var(--acc);
    font-variant-numeric:tabular-nums; }}
  .headline .meta {{ text-align:right; color:var(--mut); font-size:11.5px; }}
  .grid {{ display:grid; grid-template-columns:1fr 1fr; gap:14px 22px; }}
  section {{ break-inside:avoid; }}
  h2 {{ font-size:11.5px; text-transform:uppercase; letter-spacing:.06em;
    color:var(--acc); margin:14px 0 6px; border-bottom:1px solid var(--line);
    padding-bottom:3px; }}
  table {{ width:100%; border-collapse:collapse; }}
  th, td {{ text-align:left; padding:3.5px 2px; font-size:12px;
    border-bottom:1px solid #eef2f6; vertical-align:top; }}
  th {{ font-weight:500; color:var(--mut); }}
  td {{ text-align:right; font-weight:650; font-variant-numeric:tabular-nums;
    white-space:nowrap; }}
  .kr {{ margin:4px 0 0; padding-left:17px; }}
  .kr li {{ font-size:11.5px; color:var(--ink); margin-bottom:4px; line-height:1.4; }}
  footer {{ margin-top:16px; padding-top:9px; border-top:1px solid var(--line);
    color:var(--mut); font-size:10.5px; line-height:1.45; }}
  code {{ background:var(--panel); padding:1px 4px; border-radius:3px; }}
  .bar {{ max-width:820px; margin:0 auto 0; display:flex; justify-content:flex-end;
    padding:6px 0 0; }}
  .btn {{ background:var(--acc); color:#fff; border:0; border-radius:6px;
    padding:8px 16px; font-size:13px; font-weight:600; cursor:pointer; }}
  .btn:hover {{ background:#163d6c; }}
  @media print {{
    html,body {{ background:#fff; }}
    .sheet {{ box-shadow:none; margin:0; max-width:none; border-radius:0;
      padding:0 6px; }}
    .bar {{ display:none; }}
    @page {{ size:A4 portrait; margin:14mm; }}
  }}
</style></head>
<body>
<div class="bar"><button class="btn" id="print" type="button">Print / Save as PDF</button></div>
<div class="sheet">
  <header>
    <div class="ttl">
      <div>
        <h1>{html.escape(meta.get("model_name","Actuarial Stochastic Model"))}</h1>
        <p class="sub">One-page model summary card &mdash; read on screen or print to PDF.
          Every figure is copied verbatim from the model-output snapshot; this page
          computes nothing.</p>
        <p class="sub">Model version <b>{html.escape(str(meta.get("model_version","")))}</b>
          &middot; data contract <b>{html.escape(str(d.get("contract_version","")))}</b>
          &middot; snapshot {html.escape(str(meta.get("generated_utc","")))}</p>
      </div>
    </div>
    <span class="class">{html.escape(meta.get("classification","EDUCATIONAL ONLY"))}</span>
    <span class="prod">{html.escape(str(s.get("production_status","")))}</span>
  </header>

  <div class="headline">
    <div>
      <div class="lbl">Governed headline SCR component (frozen single-df t)</div>
      <div class="val">{cur}{_fmt(headline,2)}</div>
    </div>
    <div class="meta">rank-invariance df {_fmt(df,4)}<br/>
      {html.escape(str(hl.get("status","")))}</div>
  </div>

  <div class="grid">
    <section>
      <h2>Capital basis</h2>
      <table>
{capital_html}
      </table>
    </section>
    <section>
      <h2>Standalone risk-driver SCR (7 drivers)</h2>
      <table>
{driver_html}
      </table>
    </section>
    <section>
      <h2>Tail &amp; convergence</h2>
      <table>
{tail_html}
      </table>
    </section>
    <section>
      <h2>Validation &amp; governance</h2>
      <table>
{score_html}
      </table>
    </section>
  </div>

  <h2>Key validated results</h2>
  <ul class="kr">
{kr_html}
  </ul>

  <footer>
    Built {built} from <code>ui_data.json</code> (sha256 <code>{src_sha[:16]}&hellip;</code>).
    Self-contained &amp; zero-install: open by double-click from a USB stick or an
    air-gapped machine; makes no network calls. The governed result template
    <code>ui_app.html</code> is never modified by this card. Figures are a curated
    READ-OUT of the snapshot &mdash; for the full interactive surface open
    <code>ui_app.html</code> (or <code>offline_home.html</code>).
  </footer>
</div>
<script>
// Offline-only: ZERO network calls. The button triggers the browser's own print/PDF.
(function(){{
  var PROVENANCE = {{ contract: {json.dumps(d.get("contract_version",""))},
    headline: {json.dumps(headline)}, source_sha256: {json.dumps(src_sha)} }};
  window.__MODEL_SUMMARY_CARD__ = PROVENANCE;
  document.addEventListener("DOMContentLoaded", function(){{
    var b = document.getElementById("print");
    if (b) b.addEventListener("click", function(){{ window.print(); }});
  }});
}})();
</script>
</body></html>'''


def main():
    out = build()
    OUT.write_text(out, encoding="utf-8")
    bad = [t for t in ("http://", "https://", "//cdn", "googleapis", "unpkg", "jsdelivr")
           if t in out]
    if bad:
        print(f"FAIL: external reference(s) emitted: {bad}", file=sys.stderr)
        return 2
    print(f"OK wrote {OUT} ({len(out):,} bytes); 0 external refs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
