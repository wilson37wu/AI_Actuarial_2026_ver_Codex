#!/usr/bin/env python3
"""Phase 36 Task 2 (gap E1) - live-region status announcements on the
zero-install offline UI (WCAG 2.1 AA SC 4.1.3 Status Messages).

Adds ONE visually-hidden polite sr-only live region (#srlive,
role="status" aria-live="polite") to ui_app.html and routes four dynamic state
changes through it so screen-reader users perceive them: (i) tab activation
announces the active tab (and, on the Integrity tab, the verify outcome); (ii)
global search announces the result count; (iii) the distribution slider announces
its read-out; (iv) the integrity verifier announces verified / content-altered.

DISPLAY LAYER ONLY. Announcements DESCRIBE already-on-screen state; the announce
path recomputes NO model figure (governed headline 39975.654628199336 and every
governed read-out render bit-for-bit). The region is polite (never assertive, no
interruption); focus is never stolen; it is sr-only and never visible. The inline
read-out #dx-readout loses its own aria-live so #srlive is the one announcer for
the slider. The contract-mismatch #integritybanner (separate visible status
banner, H1 fallback view only) is unchanged.

PURE HTML / ARIA / JS: NO contract change (embedded payload byte-identical, so the
Phase 35 Task 3 per-section SHA-256 digests still verify). ADDITIVE-only;
idempotent; file:// safe (no network, no storage API).

Run:  python3 scripts/build_phase36_task2_e1_live_regions.py
"""
from __future__ import annotations

import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UI_APP = os.path.join(REPO, "ui_app.html")

PATCHES = [
    (
        'id="srlive"',
        '<div id="integritybanner" class="integritybanner" role="status" aria-live="polite" aria-hidden="true" style="display:none"></div>',
        '<div id="integritybanner" class="integritybanner" role="status" aria-live="polite" aria-hidden="true" style="display:none"></div>\n'
        '  <div id="srlive" class="sr-only" role="status" aria-live="polite" aria-atomic="true"></div>',
    ),
    (
        "function announce(msg){",
        "  function activateTab(target, fromHash){",
        "  // ===== Phase 36 Task 2 (gap E1): single polite live region announcer =====\n"
        "  // DISPLAY LAYER ONLY (WCAG 2.1 AA SC 4.1.3 Status Messages). Routes dynamic\n"
        "  // state changes to ONE visually-hidden polite sr-only region. Announcements\n"
        "  // DESCRIBE already-on-screen state only; the path recomputes NO model figure.\n"
        "  // Polite (never assertive, no interruption); focus never stolen; file:// safe.\n"
        "  var _lastIntegrityVerified=null;\n"
        "  function announce(msg){\n"
        "    try{\n"
        "      var el=document.getElementById(\"srlive\");\n"
        "      if(!el) return;\n"
        "      el.textContent=String(msg==null?\"\":msg);\n"
        "    }catch(_e){}\n"
        "  }\n"
        "  function activateTab(target, fromHash){",
    ),
    (
        'var _msg="Showing tab: "',
        '    var pl=document.getElementById(target); if(pl) pl.classList.add("active");',
        '    var pl=document.getElementById(target); if(pl) pl.classList.add("active");\n'
        '    try{ var _at=document.querySelector("#tabs .tab.active"); var _msg="Showing tab: "+(((_at&&_at.textContent)||target||"").trim()); '
        'if(target==="integrity" && _lastIntegrityVerified!==null){ _msg+=". Content integrity "+(_lastIntegrityVerified?"verified":"check: content altered"); } '
        'announce(_msg); }catch(_e){}',
    ),
    (
        'announce(results.length+',
        "      results=out; cur=results.length?0:-1; render();",
        "      results=out; cur=results.length?0:-1; render();\n"
        '      announce(results.length+(results.length===1?" result":" results")+" for "+(q||""));',
    ),
    (
        '<p id="dx-readout" class="note">',
        "'<p id=\"dx-readout\" class=\"note\" aria-live=\"polite\">'",
        "'<p id=\"dx-readout\" class=\"note\">'",
    ),
    (
        'announce("Distribution read-out: "',
        'if(slider&&ro){ slider.addEventListener("input",function(){ ro.innerHTML=dxReadoutAt(dx,Number(slider.value)); }); }',
        'if(slider&&ro){ slider.addEventListener("input",function(){ var _dt=dxReadoutAt(dx,Number(slider.value)); ro.innerHTML=_dt; '
        'announce("Distribution read-out: "+String(_dt).replace(/<[^>]*>/g," ").replace(/\\s+/g," ").trim()); }); }',
    ),
    (
        "_lastIntegrityVerified=allOk;",
        "var allOk=(nAlt===0 && nMiss===0 && nExtra===0 && rootMatch);",
        "var allOk=(nAlt===0 && nMiss===0 && nExtra===0 && rootMatch);\n    _lastIntegrityVerified=allOk;",
    ),
    (
        'announce(_lastIntegrityVerified===null',
        "    html += renderA11yAuditHtml();\n    html += renderIntegrityVerifierHtml();\n    el.innerHTML=html;\n  }",
        "    html += renderA11yAuditHtml();\n    html += renderIntegrityVerifierHtml();\n    el.innerHTML=html;\n"
        '    try{ announce(_lastIntegrityVerified===null ? "Integrity panel updated" : ("Content integrity "+(_lastIntegrityVerified ? "verified" : "check: content altered"))); }catch(_e){}\n  }',
    ),
]


def apply(html: str):
    applied, skipped = [], []
    for marker, old, new in PATCHES:
        if marker in html:
            skipped.append(marker)
            continue
        n = html.count(old)
        if n != 1:
            raise SystemExit(
                "anchor not unique for marker %r: found %d occurrences" % (marker, n)
            )
        html = html.replace(old, new, 1)
        applied.append(marker)
    return html, applied, skipped


def main() -> int:
    with open(UI_APP, encoding="utf-8") as fh:
        html = fh.read()
    new_html, applied, skipped = apply(html)
    if applied:
        with open(UI_APP, "w", encoding="utf-8") as fh:
            fh.write(new_html)
    for marker, _old, _new in PATCHES:
        assert marker in new_html, "post-condition failed: marker %r absent" % marker
    assert 'aria-live="assertive"' not in new_html, "no assertive live region allowed"
    assert new_html.count('id="srlive"') == 1, "exactly one #srlive region"
    print(
        "phase36_task2_e1: applied=%d skipped=%d ok=%s"
        % (len(applied), len(skipped), all(m in new_html for m, _o, _n in PATCHES))
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
