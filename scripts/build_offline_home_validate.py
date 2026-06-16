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
    failed = [n for n, c in checks if not c]
    print(json.dumps({"ok": not failed, "checks": len(checks),
                      "passed": len(checks) - len(failed), "failed": failed}, indent=2))
    return 1 if failed else 0

if __name__ == "__main__":
    raise SystemExit(main())
