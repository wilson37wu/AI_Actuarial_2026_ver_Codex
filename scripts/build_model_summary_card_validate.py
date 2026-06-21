#!/usr/bin/env python3
"""Env-independent (stdlib) structural gate for model_summary_card.html.

Needs no jsdom/node, so it runs in constrained CI/sandboxes. Asserts the printable
summary card is self-contained (zero external refs), renders the GOVERNED figures
verbatim from ui_data.json (recomputes nothing), and carries the print affordance.
"""
from __future__ import annotations
import json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HTML = ROOT / "model_summary_card.html"
UI_DATA = ROOT / "ui_data.json"


def main() -> int:
    html = HTML.read_text(encoding="utf-8")
    d = json.loads(UI_DATA.read_text(encoding="utf-8"))
    cap = d["capital"]
    s = d["summary"]
    tail = d["tail"]
    checks = []
    def ok(n, c): checks.append((n, bool(c)))

    ok("title present", "Model Summary Card" in html)
    ok("classification banner", "EDUCATIONAL ONLY" in html)
    ok("production status banner", str(s["production_status"]) in html)
    # governed headline verbatim
    hl = d["owner_decision_p31"]["evidence_pack"]["governed_headline"]["value"]
    ok("governed headline verbatim", hl == 39975.654628199336 and f"{hl:,.2f}" in html)
    # capital basis verbatim
    ok("nested_scr verbatim", f"{cap['nested_scr']:,.0f}" in html)
    ok("t_copula_scr verbatim", f"{cap['t_copula_scr']:,.0f}" in html)
    ok("standalone_sum verbatim", f"{cap['standalone_sum']:,.0f}" in html)
    ok("var_covar_scr verbatim", f"{cap['var_covar_scr']:,.0f}" in html)
    # all seven standalone drivers verbatim
    for k in ("rate_scr", "equity_scr", "credit_scr", "lapse_scr",
              "mortality_scr", "fx_scr", "liquidity_scr"):
        ok(f"{k} verbatim", f"{cap[k]:,.0f}" in html)
    # tail figures verbatim
    ok("var_point verbatim", f"{tail['var_point']:,.0f}" in html)
    ok("es_point verbatim", f"{tail['es_point']:,.0f}" in html)
    ok("confidence level", "99.5%" in html)
    # scorecard verbatim
    ok("gates verbatim", f"{s['gates_cleared']}/{s['gates_total']}" in html)
    ok("tasks verbatim", f"{s['tasks_completed']}/{s['tasks_total']}" in html)
    # print affordance + offline guarantees
    ok("print button", 'id="print"' in html and "window.print()" in html)
    ok("zero external refs", not re.search(r"https?://|//cdn|googleapis|unpkg|jsdelivr", html))
    ok("self-contained (no <link>/<script src)", "<link" not in html and "script src" not in html)
    ok("print media query", "@media print" in html and "@page" in html)
    ok("recomputes nothing note", "computes nothing" in html)

    failed = [n for n, c in checks if not c]
    print(json.dumps({"ok": not failed, "checks": len(checks),
                      "passed": len(checks) - len(failed), "failed": failed}, indent=2))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
