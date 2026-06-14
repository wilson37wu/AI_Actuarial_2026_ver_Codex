#!/usr/bin/env python3
"""Phase 35 Task 4 (gap A3) - one-page printable model-card cover for the
zero-install offline UI.

Presentation / print only. NO contract change: ui_data.json and the embedded
payload are left BYTE-IDENTICAL, so the Phase 35 Task 3 (gap A2) per-section
SHA-256 digests still verify in the browser by construction. Only ui_app.html
markup/CSS/JS and the offline self-test are patched.

What this adds (the established direct-artifact patch pattern):
  1. ui_app.html (CSS)  : screen-hide rule + a compact one-page @media print
                          block for a new .modelcardcover surface; the cover is
                          also revealed by the existing html.printall toggle.
  2. ui_app.html (body) : a <div id="modelcardcover"> next to the G3 sign-off
                          cover.
  3. ui_app.html (JS)   : renderModelCardCover() - assembles, BIT-FOR-BIT from
                          the embedded snapshot, an ASOP-41-style one-page model
                          card: model identity, scope, governed headline (carried
                          EXACTLY and never re-labelled), top limitations, Phase
                          30 stop-rule status, a BLANK owner-decision field
                          (MR-016/MR-017 not pre-empted) and a provenance stamp
                          (contract version + build stamp). Nothing is recomputed.
  4. scripts/ui_app_self_test.cjs : new checks for cover presence, the bit-for-bit
                          headline, the blank decision field and the one-page
                          print CSS.

NO model parameter changes. The binding Phase 30 stop-rule stands and the
MR-016/MR-017 owner decision is not pre-empted.

Run:  python3 scripts/build_phase35_task4_a3_modelcard.py [--check]
"""
from __future__ import annotations

import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UI_DATA = os.path.join(REPO, "ui_data.json")
UI_APP = os.path.join(REPO, "ui_app.html")
SELF_TEST = os.path.join(REPO, "scripts", "ui_app_self_test.cjs")

CONTRACT = "1.20.0"  # unchanged - presentation/print only

# --- 1. CSS: screen-hide (single anchor, mirrors .signoffcover) ---
SCREEN_ANCHOR = "\n  .signoffcover{display:none}\n"
SCREEN_REPLACE = "\n  .signoffcover{display:none}\n  .modelcardcover{display:none}\n"

# --- 1b. CSS: one-page print block, inserted before the H3 print-all comment ---
PRINT_ANCHOR = (
    "    /* H3 print-all: reveal every governed surface (all tab panels + "
    "collapsed sub-views) for one sign-off print */")
PRINT_BLOCK = (
    "    /* Phase 35 Task 4 (gap A3): one-page printable model-card cover */\n"
    "    .modelcardcover{display:block !important;page-break-after:always;"
    "page-break-inside:avoid;margin:0;font-size:11px;line-height:1.32;color:#111}\n"
    "    .modelcardcover h2{font-size:17px;margin:0 0 6px;color:#111;"
    "border-bottom:2px solid #111;padding-bottom:3px}\n"
    "    .modelcardcover .mcmeta{font-size:11px;color:#111;margin:3px 0}\n"
    "    .modelcardcover .mchead{font-size:12px;margin:6px 0;color:#111}\n"
    "    .modelcardcover .mcval{font-weight:700}\n"
    "    .modelcardcover ol.mclims{margin:3px 0 6px 18px;padding:0;font-size:10.5px}\n"
    "    .modelcardcover ol.mclims li{margin:1px 0}\n"
    "    .modelcardcover .mcneutral{margin:8px 0;padding:6px;border:1px solid #888;"
    "font-size:10px;color:#111}\n"
    "    .modelcardcover .mcrow{display:flex;gap:18px;margin-top:10px}\n"
    "    .modelcardcover .mcbox{flex:1;border-top:1px solid #111;padding-top:3px;"
    "font-size:10px;color:#111}\n"
    "    .modelcardcover .mcprov{margin-top:10px;font-size:9.5px;color:#333;"
    "border-top:1px solid #bbb;padding-top:4px}\n")

# --- 1c. CSS: also reveal the cover under the html.printall print-all toggle ---
PRINTALL_ANCHOR = "    html.printall .signoffcover{display:block !important}"
PRINTALL_REPLACE = (
    "    html.printall .signoffcover{display:block !important}\n"
    "    html.printall .modelcardcover{display:block !important}")

# --- 2. body div, mirrors the G3 sign-off cover container ---
BODY_ANCHOR = '<div id="signoffcover" class="signoffcover" aria-hidden="true"></div>'
BODY_REPLACE = (
    '<div id="signoffcover" class="signoffcover" aria-hidden="true"></div>\n'
    '  <div id="modelcardcover" class="modelcardcover" aria-hidden="true"></div>')

# --- 3. JS: renderModelCardCover(), injected just before renderSignoffCover() ---
RENDER_JS = r'''  // Phase 35 Task 4 (gap A3): one-page printable model-card cover. Assembled
  // BIT-FOR-BIT from the embedded snapshot (no recompute). ASOP-41 style: model
  // identity, scope, governed headline (carried exactly + never re-labelled),
  // top limitations, Phase 30 stop-rule status, a BLANK owner-decision field
  // (MR-016/MR-017 not pre-empted) and a provenance stamp. Print-only surface.
  function renderModelCardCover(){
    var el=document.getElementById("modelcardcover"); if(!el) return;
    if(!DATA){ el.innerHTML=""; return; }
    var m=DATA.meta||{};
    var od=DATA.owner_decision_p31||{};
    var ev=od.evidence_pack||{};
    var gh=ev.governed_headline||{};
    var sr=((DATA.phase30||{}).stop_rule)||{};
    var gen=String(m.generated_utc||"").slice(0,19);
    // exact, bit-for-bit headline carried from the embedded snapshot (NOT money-
    // formatted; never re-labelled - the governed label is carried verbatim).
    var ghExact=(gh.value!=null)?String(gh.value):"--";
    var lims=(od.limitations||[]).slice(0,3);
    var limHtml=lims.map(function(s){return '<li>'+esc(s)+'</li>';}).join("");
    var srLine;
    if(sr.stop_rule_applied===true){
      srLine='Phase 30 binding stop-rule APPLIED (pre-registered trigger met: '
        +(sr.stop_rule_trigger_met===true?'yes':'no')
        +') &mdash; dependence-FORM escalation under MR-016 has ENDED; '
        +'MR-016='+esc(String(sr.mr016_decision||'--'))
        +', MR-017='+esc(String(sr.mr017_decision||'--'))+'.';
    } else {
      srLine='Phase 30 stop-rule status not present in this snapshot.';
    }
    el.innerHTML=''
      +'<h2>Model card &mdash; '+esc(m.model_name||"Actuarial Stochastic Model")+'</h2>'
      +'<div class="mcmeta"><b>Model identity:</b> '+esc(m.model_name||"--")
        +' v'+esc(String(m.model_version||"--"))+' &middot; '+esc(m.classification||"--")+'</div>'
      +'<div class="mcmeta"><b>Scope:</b> '+esc(od.purpose||"--")+'</div>'
      +'<div class="mchead"><b>'+esc(gh.label||"governed component SCR headline (frozen single-df t)")
        +':</b> <span class="mcval" data-headline-exact="'+esc(ghExact)+'">'+esc(ghExact)+'</span>'
        +(gh.status?(' &middot; '+esc(gh.status)):'')+'</div>'
      +'<div class="mcmeta"><b>Top limitations:</b></div>'
      +'<ol class="mclims">'+limHtml+'</ol>'
      +'<div class="mcmeta"><b>Phase 30 stop-rule status:</b> '+srLine+'</div>'
      +'<div class="mcneutral">This one-page model card is assembled bit-for-bit '
        +'from the embedded snapshot; nothing is recomputed. The MR-016 / MR-017 '
        +'owner decision is NOT pre-empted: the decision field below is '
        +'intentionally BLANK until the model owner decides.</div>'
      +'<div class="mcrow">'
      +'<div class="mcbox">Owner decision (option id): _______________________</div>'
      +'<div class="mcbox">Signature: _______________________</div>'
      +'<div class="mcbox">Date: ________________</div>'
      +'</div>'
      +'<div class="mcprov">Provenance: contract v'+esc(String(DATA.contract_version||"?"))
        +' &middot; build stamp '+esc(gen)+'Z &middot; '+esc(m.model_name||"")+'</div>';
  }
'''
RENDER_ANCHOR = "  function renderSignoffCover(){"

# --- 3b. renderAll() call (unique 2-call anchor) ---
RENDERALL_ANCHOR = "renderSignoffCover(); wireDropLoader();"
RENDERALL_REPLACE = "renderSignoffCover(); renderModelCardCover(); wireDropLoader();"

# --- 4. self-test additions ---
ST_VARS_ANCHOR = (
    '  const printCoverCssPresent = /\\.signoffcover\\{display:block !important/.test(html)\n'
    '    && /\\.signoffcover\\{display:none\\}/.test(html);')
ST_VARS_ADD = '''
  // Phase 35 Task 4 (gap A3): one-page printable model-card cover.
  const modelCardEl = document.getElementById("modelcardcover");
  const modelCardText = (modelCardEl && modelCardEl.textContent) || "";
  const modelCardLimItems = modelCardEl ? modelCardEl.querySelectorAll("ol.mclims li").length : 0;
  const modelCardHeadlineExact = (function(){
    try { return String(uiDataObj.owner_decision_p31.evidence_pack.governed_headline.value); }
    catch(e){ return null; }
  })();
  const a3PrintCssPresent =
    /\\.modelcardcover\\{display:block !important;page-break-after:always/.test(html)
    && /\\.modelcardcover\\{display:none\\}/.test(html)
    && /html\\.printall \\.modelcardcover\\{display:block !important\\}/.test(html);'''

ST_CHECKS_ANCHOR = (
    "    // Phase 35 Task 3 (gap A2): content-integrity digests + in-browser verifier\n"
    "    a2DigestsPresent,")
ST_CHECKS_ADD = (
    "    // Phase 35 Task 4 (gap A3): one-page printable model-card cover\n"
    "    a3ModelCardPresent: !!modelCardEl,\n"
    "    a3ModelCardIdentity: /Model card/.test(modelCardText) &&\n"
    "      (uiDataObj ? modelCardText.indexOf(uiDataObj.meta.model_name) >= 0 : false) &&\n"
    "      /v0\\.2\\.0/.test(modelCardText) && /EDUCATIONAL ONLY/.test(modelCardText),\n"
    "    a3ModelCardScope: /Scope:/.test(modelCardText) && modelCardText.length > 200,\n"
    "    a3ModelCardHeadlineBitForBit: !!modelCardHeadlineExact &&\n"
    "      modelCardText.indexOf(modelCardHeadlineExact) >= 0 &&\n"
    "      /39975\\.654628199336/.test(modelCardText),\n"
    "    a3ModelCardHeadlineNotRelabelled:\n"
    "      /governed component SCR headline \\(frozen single-df t\\)/.test(modelCardText),\n"
    "    a3ModelCardLimitations: modelCardLimItems === 3,\n"
    "    a3ModelCardStopRule: /Phase 30/.test(modelCardText) &&\n"
    "      /stop-rule/i.test(modelCardText) && /MR-016/.test(modelCardText),\n"
    "    a3ModelCardDecisionBlank: /intentionally BLANK/.test(modelCardText) &&\n"
    "      /Owner decision \\(option id\\): _{6,}/.test(modelCardText),\n"
    "    a3ModelCardProvenance: /Provenance:/.test(modelCardText) &&\n"
    "      /contract v1\\.20\\.0/.test(modelCardText) && /build stamp/.test(modelCardText),\n"
    "    a3PrintCssPresent: a3PrintCssPresent,\n"
    "    // Phase 35 Task 3 (gap A2): content-integrity digests + in-browser verifier\n"
    "    a2DigestsPresent,")

ST_OK_ANCHOR = "    checks.a2DigestsPresent &&"
ST_OK_ADD = (
    "    checks.a3ModelCardPresent &&\n"
    "    checks.a3ModelCardIdentity &&\n"
    "    checks.a3ModelCardScope &&\n"
    "    checks.a3ModelCardHeadlineBitForBit &&\n"
    "    checks.a3ModelCardHeadlineNotRelabelled &&\n"
    "    checks.a3ModelCardLimitations &&\n"
    "    checks.a3ModelCardStopRule &&\n"
    "    checks.a3ModelCardDecisionBlank &&\n"
    "    checks.a3ModelCardProvenance &&\n"
    "    checks.a3PrintCssPresent &&\n"
    "    checks.a2DigestsPresent &&")


def _replace_once(s: str, old: str, new: str, label: str, idempotent_marker: str | None = None) -> str:
    if idempotent_marker is not None and idempotent_marker in s:
        return s  # already applied
    n = s.count(old)
    assert n == 1, "anchor %r found %d times (expected 1)" % (label, n)
    return s.replace(old, new, 1)


def patch_html(html: str) -> str:
    # payload must remain byte-identical -> capture and verify later
    html = _replace_once(html, SCREEN_ANCHOR, SCREEN_REPLACE, "screen-hide css",
                         idempotent_marker=".modelcardcover{display:none}")
    html = _replace_once(html, PRINT_ANCHOR, PRINT_BLOCK + PRINT_ANCHOR, "print css block",
                         idempotent_marker="gap A3): one-page printable model-card cover")
    html = _replace_once(html, PRINTALL_ANCHOR, PRINTALL_REPLACE, "printall css",
                         idempotent_marker="html.printall .modelcardcover")
    html = _replace_once(html, BODY_ANCHOR, BODY_REPLACE, "body div",
                         idempotent_marker='id="modelcardcover"')
    html = _replace_once(html, RENDER_ANCHOR, RENDER_JS + "\n" + RENDER_ANCHOR, "render js",
                         idempotent_marker="function renderModelCardCover(")
    html = _replace_once(html, RENDERALL_ANCHOR, RENDERALL_REPLACE, "renderAll call",
                         idempotent_marker="renderModelCardCover(); wireDropLoader();")
    return html


def patch_selftest(src: str) -> str:
    src = _replace_once(src, ST_VARS_ANCHOR, ST_VARS_ANCHOR + ST_VARS_ADD, "selftest vars",
                        idempotent_marker="modelCardHeadlineExact")
    src = _replace_once(src, ST_CHECKS_ANCHOR, ST_CHECKS_ADD, "selftest checks",
                        idempotent_marker="a3ModelCardPresent:")
    src = _replace_once(src, ST_OK_ANCHOR, ST_OK_ADD, "selftest ok formula",
                        idempotent_marker="checks.a3ModelCardPresent")
    return src


def _payload_bytes(html: str) -> bytes:
    tok = "/*__UI_DATA__*/"
    a = html.find(tok) + len(tok)
    b = html.find("</script>", a)
    return html[a:b].encode("utf-8")


def main(check_only: bool = False) -> int:
    with open(UI_APP, encoding="utf-8") as fh:
        html0 = fh.read()
    with open(SELF_TEST, encoding="utf-8") as fh:
        st0 = fh.read()

    # contract precondition (unchanged)
    with open(UI_DATA, encoding="utf-8") as fh:
        data = json.load(fh)
    assert data.get("contract_version") == CONTRACT, (
        "unexpected contract %r (expected %r)" % (data.get("contract_version"), CONTRACT))

    payload_before = _payload_bytes(html0)
    html1 = patch_html(html0)
    payload_after = _payload_bytes(html1)
    assert payload_before == payload_after, "embedded payload changed (must be byte-identical)"

    st1 = patch_selftest(st0)

    if check_only:
        print(json.dumps({
            "contract": CONTRACT + " (unchanged)",
            "html_changed": html1 != html0,
            "selftest_changed": st1 != st0,
            "payload_byte_identical": payload_before == payload_after,
        }, indent=1))
        return 0

    with open(UI_APP, "w", encoding="utf-8") as fh:
        fh.write(html1)
    with open(SELF_TEST, "w", encoding="utf-8") as fh:
        fh.write(st1)

    # on-disk guards
    h2 = open(UI_APP, encoding="utf-8").read()
    assert "function renderModelCardCover(" in h2
    assert 'id="modelcardcover"' in h2
    assert ".modelcardcover{display:block !important;page-break-after:always" in h2
    assert _payload_bytes(h2) == payload_before, "payload mutated on write"
    # re-parse the embedded payload to confirm it is still valid JSON
    json.loads(_payload_bytes(h2).decode("utf-8"))

    print(json.dumps({
        "verdict": "PASS",
        "contract": CONTRACT + " (unchanged - presentation/print only)",
        "payload_byte_identical": True,
        "ui_app_bytes": len(h2.encode("utf-8")),
        "selftest_bytes": len(st1.encode("utf-8")),
    }, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(check_only="--check" in sys.argv))
