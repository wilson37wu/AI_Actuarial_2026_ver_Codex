#!/usr/bin/env python3
"""Phase 36 Task 4 (gap E3) - single reproducibility evidence-pack export on the
zero-install offline UI.

Adds ONE in-browser action ("Reproducibility evidence pack") to ui_app.html that
serialises the EXACT embedded ``ui_data`` payload bytes - which already contain
``contract_manifest.section_digests`` + ``root_digest`` and the build/provenance
stamp (``meta.generated_utc`` / ``source_files`` / ``contract_manifest.generated_by``)
- to a single downloaded file via the existing ``downloadText``/``downloadBlob``
Blob plumbing. The exported bytes are byte-identical to the embedded payload, so a
reviewer receives independently digest-verifiable evidence of exactly what the UI
displayed: they can recompute the per-section SHA-256 digests and match the
manifest, or re-load the file in this same UI for the in-browser verifier to
confirm INTEGRITY VERIFIED.

DISPLAY LAYER ONLY. The export reuses the embedded snapshot and the existing
manifest; it recomputes NO model figure (governed headline 39975.654628199336 and
every governed read-out render bit-for-bit). NO contract change (the embedded
payload is byte-identical, so the Phase 35 Task 3 per-section SHA-256 digests still
verify and no new ui_data key is added). The export path makes NO network call and
uses NO storage API; it works under file://.

PURE HTML / JS; ADDITIVE-only; idempotent; anchor-asserted (each patch's anchor
must be unique). Mirrors the Phase 36 Task 2 (E1) standalone-patch pattern; it is
NOT a ui_data contract layer, so it is intentionally absent from
build_ui_pipeline.LAYERS.

Run:  python3 scripts/build_phase36_task4_e3_evidence_pack.py
"""
from __future__ import annotations

import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UI_APP = os.path.join(REPO, "ui_app.html")

_BTN_PRINTALL = (
    '<button type="button" class="tbtn" id="btnPrintAll" title="Print every '
    'governed surface (all tabs + sub-views) as a single sign-off pack">Print all '
    '(sign-off pack)</button>'
)
_BTN_E3 = (
    '<button type="button" class="tbtn" id="btnEvidencePack" title="Export the '
    'EXACT embedded ui_data payload (byte-identical; carries contract_manifest '
    'per-section + root SHA-256 digests and the build/provenance stamp) as one '
    'reproducibility evidence pack for independent offline verification">'
    'Reproducibility evidence pack</button>'
)

_DOWNLOADTEXT = (
    '  function downloadText(name,text,mime){ downloadBlob(name,new Blob([text],'
    '{type:(mime||"text/plain")+";charset=utf-8"})); }'
)
_E3_FUNCS = (
    "  // ===== Phase 36 Task 4 (gap E3): reproducibility evidence-pack export =====\n"
    "  // Serialises the EXACT embedded ui_data payload bytes (which already contain\n"
    "  // contract_manifest.section_digests + root_digest and the build/provenance\n"
    "  // stamp) to ONE downloaded file via the existing Blob plumbing. The exported\n"
    "  // bytes are byte-identical to the embedded payload, so a reviewer can\n"
    "  // independently recompute the per-section SHA-256 digests and match the\n"
    "  // manifest (or re-load the file here for the in-browser verifier to confirm\n"
    "  // INTEGRITY VERIFIED). No network, no storage API; file:// safe. DISPLAY\n"
    "  // LAYER ONLY: it recomputes NO model figure.\n"
    "  function getEmbeddedRaw(){\n"
    "    var el=document.getElementById(\"ui-data\");\n"
    "    if(!el) return null;\n"
    "    var raw=el.textContent||\"\";\n"
    "    return raw.replace(\"/*__UI_DATA__*/\",\"\").trim();\n"
    "  }\n"
    "  function exportEvidencePack(){\n"
    "    try{\n"
    "      var raw=getEmbeddedRaw();\n"
    "      if(!raw||raw===\"null\"){ try{ alert(\"No embedded data to export.\"); }catch(_e){} return; }\n"
    "      var ver=\"unknown\", root=\"\";\n"
    "      try{ var d=JSON.parse(raw); ver=(d&&d.contract_version)||\"unknown\";\n"
    "        root=(d&&d.contract_manifest&&d.contract_manifest.root_digest)||\"\"; }catch(_e){}\n"
    "      var tag=root?(\"_\"+String(root).slice(0,8)):\"\";\n"
    "      var name=\"reproducibility_evidence_pack_v\"+ver+tag+\".json\";\n"
    "      downloadText(name, raw, \"application/json\");\n"
    "      try{ if(typeof announce===\"function\") announce(\"Reproducibility evidence pack exported: \"+name); }catch(_e){}\n"
    "    }catch(_e){}\n"
    "  }"
)

_MAP_PRINTALL = (
    '      ["btnPrintAll",function(){ var de=document.documentElement; if(de) '
    'de.classList.add("printall"); try{ window.print(); }catch(e){} if(de) '
    'de.classList.remove("printall"); }]'
)
_MAP_E3 = (
    '      ["btnPrintAll",function(){ var de=document.documentElement; if(de) '
    'de.classList.add("printall"); try{ window.print(); }catch(e){} if(de) '
    'de.classList.remove("printall"); }],\n'
    '      ["btnEvidencePack",function(){ exportEvidencePack(); }]'
)

_VERIFIER_TAIL = "verifier runs entirely offline in the browser.</p>'"
_VERIFIER_TAIL_NEW = (
    "verifier runs entirely offline in the browser.</p>'+\n"
    "      '<p class=\"muted\" data-e3-note=\"1\">Reproducibility evidence pack: use the "
    "<b>Reproducibility evidence pack</b> toolbar button to download the exact embedded "
    "<span class=\"mono\">ui_data</span> payload (byte-identical; it carries these "
    "per-section and root SHA-256 digests plus the build/provenance stamp) for independent, "
    "offline re-verification. The export recomputes no model figure.</p>'"
)

# (marker that proves this patch is already applied, old unique anchor, new text)
PATCHES = [
    ('id="btnEvidencePack"', _BTN_PRINTALL, _BTN_PRINTALL + "\n    " + _BTN_E3),
    ("function exportEvidencePack(", _DOWNLOADTEXT, _DOWNLOADTEXT + "\n" + _E3_FUNCS),
    ('["btnEvidencePack",function', _MAP_PRINTALL, _MAP_E3),
    ('data-e3-note="1"', _VERIFIER_TAIL, _VERIFIER_TAIL_NEW),
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
    # invariants
    assert new_html.count('id="btnEvidencePack"') == 1, "exactly one evidence-pack button"
    assert "function exportEvidencePack(" in new_html and "function getEmbeddedRaw(" in new_html
    assert "localStorage" not in _E3_FUNCS and "sessionStorage" not in _E3_FUNCS, \
        "export path must use no storage API"
    print(
        "phase36_task4_e3: applied=%d skipped=%d ok=%s"
        % (len(applied), len(skipped), all(m in new_html for m, _o, _n in PATCHES))
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
