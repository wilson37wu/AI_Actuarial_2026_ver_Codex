#!/usr/bin/env python3
"""Env-independent (stdlib) structural gate for offline_home.html.

Mirrors scripts/offline_home_self_test.cjs but needs no jsdom/node, so it runs in
constrained CI/sandboxes where the 744KB ui_app self-test cannot. Asserts the
landing page is self-contained (zero external refs), links every offline view, and
renders the GOVERNED figures verbatim from ui_data.json (recomputes nothing).
"""
from __future__ import annotations
import json, re, sys
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HTML = (ROOT / "offline_home.html")
UI_DATA = ROOT / "ui_data.json"
EXPECT_LINKS = ["ui_app.html", "model_result_viewer.html", "combined_model_app.html",
                "par_projection_gui.html", "launchers/README.md"]

class _P(HTMLParser):
    def __init__(self): super().__init__(); self.links=[]; self.figs=0
    def handle_starttag(self, t, attrs):
        a = dict(attrs)
        if t == "a" and "card" in (a.get("class") or ""): self.links.append(a.get("href"))
        if t == "div" and a.get("class") == "fig": self.figs += 1

def main() -> int:
    html = HTML.read_text(encoding="utf-8")
    d = json.loads(UI_DATA.read_text(encoding="utf-8"))
    p = _P(); p.feed(html)
    checks = []
    def ok(n, c): checks.append((n, bool(c)))
    for v in EXPECT_LINKS: ok(f"link {v}", v in p.links)
    # Link-existence regression gate (offline-UI option f): promote the build-time
    # assertion from build_offline_home.build() into this standing, rebuild-independent
    # gate. Every card href in the SHIPPED offline_home.html MUST resolve to a file that
    # exists on disk under ROOT, so a shipped landing page can never link to a missing
    # view. Cards ARE the VIEWS, and chooser hrefs are asserted (at build time) to be a
    # subset of VIEWS, so verifying every card target also covers every chooser target.
    # Static check: reads no network, derives/changes no governed figure.
    _missing_on_disk = sorted({
        _rel for _rel in (
            (h or "").split("#", 1)[0].split("?", 1)[0] for h in p.links
        ) if _rel and not (ROOT / _rel).exists()
    })
    ok("every card link target exists on disk"
       + (f" (missing: {', '.join(_missing_on_disk)})" if _missing_on_disk else ""),
       not _missing_on_disk)
    ok("title", "Offline Home" in html)
    ok(">=8 figure rows", p.figs >= 8)
    ok("classification banner", "EDUCATIONAL ONLY" in html)
    hl = d["owner_decision_p31"]["evidence_pack"]["governed_headline"]["value"]
    ok("governed headline verbatim", hl == 39975.654628199336 and f"{hl:,.2f}" in html)
    ok("nested_scr verbatim", f"{d['capital']['nested_scr']:,.0f}" in html)
    ok("correlated_scr verbatim", f"{d['capital']['correlated_scr']:,.0f}" in html)
    ok("standalone_sum verbatim", f"{d['capital']['standalone_sum']:,.0f}" in html)
    ok("zero external refs", not re.search(r"https?://|//cdn|googleapis|unpkg|jsdelivr", html))
    ok("self-contained (no <link>/<script src)", "<link" not in html and "script src" not in html)
    # "which view do I want?" chooser (additive, static, zero JS) presence
    ok("which-view chooser heading", "Which view do I want?" in html)
    ok("chooser has >=6 goal rows", html.count('class="crow"') >= 6)
    ok("chooser recommends summary card", re.search(r'crow.*?model_summary_card\.html', html, re.S) is not None)
    # snapshot-loader (additive, zero-network) presence
    ok("loader drop zone", 'id="drop"' in html)
    ok("loader file input", 'type="file"' in html and 'id="file"' in html)
    ok("loader reset button", 'id="reset"' in html)
    ok("loader reads locally (FileReader)", "FileReader" in html)
    ok("loader updatable header ids", 'id="hv"' in html and 'id="hc"' in html and 'id="hs"' in html)
    # accessibility / quick-start pass (additive, static, zero JS) presence
    ok("skip-to-content link", 'class="skip"' in html and 'href="#main"' in html)
    ok("main landmark target", 'id="main"' in html and "<main" in html)
    ok("keyboard focus-visible ring", ":focus-visible" in html)
    ok("reduced-motion fallback", "prefers-reduced-motion" in html)
    ok("start-here guidance", 'class="start"' in html and "New here?" in html)
    # capital-at-a-glance graphic (additive, inline-SVG, zero JS dep, zero network) presence
    ok("capital bridge heading", "Capital at a glance" in html)
    ok("capital bridge svg", 'id="capbridge"' in html)
    ok("capital bridge 3 bars", html.count('class="cbar ') == 3)
    ok("capital bridge 3 value texts", html.count('class="cbval"') == 3)
    ok("capital bridge keys (governed)",
       all('data-key="%s"' % k in html for k in ("standalone_sum", "correlated_scr", "nested_scr")))
    ok("capital bridge derives nothing (svg inline, no chart lib)",
       "chart.js" not in html.lower() and "d3" not in html.lower())
    # standalone-SCR-by-driver mini bars (additive, inline-SVG, zero JS dep, zero network)
    _dkeys = ("rate_scr", "equity_scr", "credit_scr", "lapse_scr",
              "mortality_scr", "fx_scr", "liquidity_scr")
    ok("driver bars heading", "Standalone SCR by risk driver" in html)
    ok("driver bars svg", 'id="driverbars"' in html)
    ok("driver bars 7 bars", html.count('class="dbar"') == 7)
    ok("driver bars 7 value texts", html.count('class="dbval"') == 7)
    ok("driver bars keys (governed)",
       all('data-key="%s"' % k in html for k in _dkeys))
    ok("driver bars values verbatim",
       all(f"{d['capital'][k]:,.0f}" in html for k in _dkeys))
    _dsum = sum(float(d['capital'][k]) for k in _dkeys)
    ok("driver bars sum == standalone_sum (governed consistency)",
       abs(_dsum - float(d['capital']['standalone_sum'])) < 1e-6)
    ok("driver bars derive nothing (svg inline, no chart lib)",
       "chart.js" not in html.lower())
    # tail-convergence sparkline (additive, inline-SVG, zero JS dep, zero network) presence
    t = d.get("tail", {}) or {}
    _grid = t.get("outer_grid") or []
    ok("tail spark heading", "Tail convergence" in html)
    ok("tail spark svg", 'id="tailspark"' in html)
    ok("tail spark two series polylines",
       'data-key="var_path"' in html and 'data-key="es_path"' in html)
    ok("tail spark var dots == grid len",
       html.count('data-series="var"') == len(_grid) and len(_grid) > 0)
    ok("tail spark es dots == grid len",
       html.count('data-series="es"') == len(_grid) and len(_grid) > 0)
    ok("tail spark n* marker (governed recommended_n_outer)",
       'data-key="recommended_n_outer"' in html
       and f"{t.get('recommended_n_outer'):,.0f}" in html)
    ok("tail spark final VaR/ES verbatim",
       f"{t.get('final_var'):,.0f}" in html and f"{t.get('final_es'):,.0f}" in html)
    ok("tail spark grid endpoints verbatim",
       (not _grid) or (f"{_grid[0]:,.0f}" in html and f"{_grid[-1]:,.0f}" in html))
    ok("tail spark converged flag (governed) shown",
       (t.get("converged") is True) and "converged" in html)
    ok("tail spark derives nothing (svg inline, no chart lib)",
       "chart.js" not in html.lower() and "d3.min" not in html.lower())
    # VaR/ES point-vs-CI band strip (additive, inline-SVG, zero JS dep, zero network)
    _vci = t.get("var_ci") or []
    _eci = t.get("es_ci") or []
    ok("tail CI heading", "confidence interval" in html.lower())
    ok("tail CI svg", 'id="tailci"' in html)
    ok("tail CI two bands (var+es)",
       html.count('class="ciband var"') == 1 and html.count('class="ciband es"') == 1)
    ok("tail CI two point markers (var+es)",
       html.count('class="cipt var"') == 1 and html.count('class="cipt es"') == 1)
    ok("tail CI var_ci endpoints verbatim",
       (len(_vci) >= 2) and f"{_vci[0]:,.0f}" in html and f"{_vci[1]:,.0f}" in html)
    ok("tail CI es_ci endpoints verbatim",
       (len(_eci) >= 2) and f"{_eci[0]:,.0f}" in html and f"{_eci[1]:,.0f}" in html)
    ok("tail CI point estimates verbatim",
       f"{t.get('final_var'):,.0f}" in html and f"{t.get('final_es'):,.0f}" in html)
    ok("tail CI point inside its CI band (governed consistency)",
       (len(_vci) >= 2 and _vci[0] <= float(t.get('final_var')) <= _vci[1]) and
       (len(_eci) >= 2 and _eci[0] <= float(t.get('final_es')) <= _eci[1]))
    ok("tail CI derives nothing (svg inline, no chart lib)",
       "chart.js" not in html.lower())
    # Nested-vs-copula VaR CI comparison (W37, additive, inline-SVG, zero JS dep, zero net)
    _nci = t.get("nested_var_ci") or []
    _no = t.get("nested_n_outer")
    ok("nested CI heading", "nested vs copula" in html.lower())
    ok("nested CI svg", 'id="nestedci"' in html)
    ok("nested CI two bands (copula+nested)",
       html.count('class="nciband copula"') == 1 and html.count('class="nciband nested"') == 1)
    ok("nested CI two point markers (copula+nested)",
       html.count('class="ncipt copula"') == 1 and html.count('class="ncipt nested"') == 1)
    ok("nested CI nested_var_ci endpoints verbatim",
       (len(_nci) >= 2) and f"{_nci[0]:,.0f}" in html and f"{_nci[1]:,.0f}" in html)
    ok("nested CI copula var_ci endpoints verbatim",
       (len(_vci) >= 2) and f"{_vci[0]:,.0f}" in html and f"{_vci[1]:,.0f}" in html)
    ok("nested CI governed point (final_var) verbatim",
       f"{t.get('final_var'):,.0f}" in html)
    ok("nested CI point inside BOTH bands (governed consistency)",
       (len(_vci) >= 2 and _vci[0] <= float(t.get('final_var')) <= _vci[1]) and
       (len(_nci) >= 2 and _nci[0] <= float(t.get('final_var')) <= _nci[1]))
    ok("nested CI nested band wider than copula band (estimator-noise ordering)",
       (len(_vci) >= 2 and len(_nci) >= 2) and
       (float(_nci[1]) - float(_nci[0])) > (float(_vci[1]) - float(_vci[0])))
    ok("nested CI outer-count label present",
       (_no is not None) and (f"n={_no:,.0f}" in html or f"n={_no}" in html))
    ok("nested CI derives nothing (svg inline, no chart lib)",
       "chart.js" not in html.lower())
    failed = [n for n, c in checks if not c]
    print(json.dumps({"ok": not failed, "checks": len(checks),
                      "passed": len(checks) - len(failed), "failed": failed}, indent=2))
    return 1 if failed else 0

if __name__ == "__main__":
    raise SystemExit(main())
