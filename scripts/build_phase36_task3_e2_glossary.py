#!/usr/bin/env python3
"""Phase 36 Task 3 (gap E2) - consolidated global glossary & methodology
explainer surface on the zero-install offline UI.

Promotes the sign-off-pack-scoped glossary (``owner_decision_p31.glossary``) to a
GLOBAL, build-time-assembled glossary / data-dictionary covering every governed
read-out across the 18 result tabs. Each entry carries a term, a plain-language
definition, the method/assumption basis, and the limitation provenance. All
limitation text and the nine base definitions are carried VERBATIM (copied
programmatically from the embedded payload at build time) - nothing is
re-derived or re-labelled. The surface is a new read-only "Methodology &
Glossary" tab/panel. DISPLAY-ONLY: it recomputes NO model figure (it contains no
model number at all).

ADDITIVE contract bump 1.20.0 -> 1.21.0: ONE new top-level key ``explainer`` is
added; every pre-existing ``ui_data`` key renders bit-identically. The Phase 35
Task 3 per-section SHA-256 digests are recomputed (the new ``explainer`` section
gets a digest; ``contract_version`` changes; the root digest recomputes) using
the EXACT embedded JS canonical+SHA-256 (imported from the A2 builder) so the
in-browser verifier still agrees byte-for-byte.

NO model parameter changes; the binding Phase 30 stop-rule stands; the
MR-016/MR-017 owner decision is not pre-empted.

Run (operates IN PLACE on REPO's ui_data.json + ui_app.html):
    python3 scripts/build_phase36_task3_e2_glossary.py [--check]
REPO is the parent of this script's dir unless overridden by env E2_REPO.
"""
from __future__ import annotations

import collections
import copy
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.environ.get("E2_REPO") or os.path.dirname(HERE)
UI_DATA = os.path.join(REPO, "ui_data.json")
UI_APP = os.path.join(REPO, "ui_app.html")

# reuse the EXACT canonical+SHA-256 digest computation from the A2 builder so
# the digests this layer writes are produced by the identical code the browser
# runs (no float-formatting divergence possible).
sys.path.insert(0, HERE)
import build_phase35_task3_a2_digests as a2  # noqa: E402

PRIOR_CONTRACT = "1.20.0"
NEW_CONTRACT = "1.21.0"
GENERATOR = "scripts/build_phase36_task3_e2_glossary.py (Phase 36 Task 3, gap E2)"
EXPLAINER_KEY = "explainer"
EXPLAINER_VERSION = "1.0.0"

# The 18 result tabs (id, label) in render order - mirrors TABS in ui_app.html.
TAB_ORDER = [
    ("overview", "Overview"),
    ("inventory", "Inventory & Contract"),
    ("calibrations", "Calibrations"),
    ("capital", "Capital & Tail"),
    ("actions", "Management Actions"),
    ("phase24", "Joint Actions (P24)"),
    ("phase25", "Path-wise Actions (P25)"),
    ("phase26", "Full Re-Agg (P26)"),
    ("phase27", "Skew-t Tail (P27)"),
    ("phase28", "Grouped-t Tail (P28)"),
    ("phase29", "Vine Tail (P29)"),
    ("phase30", "Stop-Rule (P30)"),
    ("comparator", "SCR Comparator (P33)"),
    ("distexplorer", "Distribution Explorer (P33)"),
    ("ownerdecision", "Owner Decision (P31)"),
    ("userrun", "User Run (UIL)"),
    ("governance", "Governance"),
    ("integrity", "Integrity (H1)"),
]

# Authored plain-language methodology terms (NO model figures). The nine base
# terms are NOT here - their definitions are carried verbatim from the embedded
# owner_decision_p31.glossary at assembly time.
AUTHORED_TERMS = {
    "Solvency Capital Requirement (SCR)":
        "the capital a regulator expects an insurer to hold so it can absorb a 1-in-200-year "
        "(99.5th percentile) adverse outcome over one year; the model produces a component SCR "
        "for the modelled risk aggregation.",
    "model-point inventory & data contract":
        "the set of representative policy rows (model points) and the build-time data-contract "
        "manifest the offline UI validates the embedded snapshot against before rendering.",
    "calibration basis":
        "the market/experience data and fitting procedure that fix each risk driver's parameters; "
        "the calibration explorer shows the per-driver inputs and fit on a fixed, frozen basis.",
    "management-action rule":
        "the governed, pre-specified rule (e.g. bonus crediting / de-risking) the projection applies "
        "deterministically inside each scenario; it is never user-settable in the offline surface.",
    "joint management actions":
        "the with-actions aggregation that applies the governed management-action rule jointly across "
        "risk drivers, so diversification reflects the actions actually taken in each joint scenario.",
    "path-wise bonus declaration":
        "bonus / crediting declared scenario-by-scenario along each projection path, rather than from a "
        "single deterministic assumption, so the with-actions basis is consistent path by path.",
    "full re-aggregation & delta matrix":
        "a complete re-aggregation of the with-actions basis whose delta matrix isolates how each "
        "modelling change moves the component SCR relative to the prior basis.",
    "skew-t copula":
        "a tail-dependence copula that allows asymmetric (skewed) joint extremes; assessed as a "
        "candidate dependence FORM on a fixed margin/calibration basis.",
    "grouped-t copula":
        "a t-copula variant that lets blocks of risk drivers carry their own degrees-of-freedom (tail "
        "weight); assessed as a candidate dependence FORM on a fixed margin/calibration basis.",
    "loss distribution & percentile (VaR/ES)":
        "the simulated distribution of one-year loss; Value-at-Risk reads a percentile and Expected "
        "Shortfall averages losses beyond it. The explorer is display-only over the frozen snapshot.",
    "owner decision package":
        "the Phase 31 pack that gives the model owner everything needed to dispose of the quantified "
        "dependence-form residual; options appear in registry order with no default and no steering.",
    "user run (UIL) & model_inputs":
        "the worked end-to-end example: user inputs are written to model_inputs.json and consumed by the "
        "par_model_v2 loader / run_model; the offline UI surfaces the resulting run, recomputing nothing.",
    "governance ChangeRecord":
        "an append-only governance ledger entry recording each model/UI change, its classification and "
        "owner-review status, for auditability.",
    "data-contract integrity & section digest":
        "a build-time SHA-256 digest of every data section that the page RECOMPUTES in your browser from "
        "the embedded snapshot to prove the content was not altered; it digests content, not a model figure.",
}

# Authored method/assumption basis per term id (NO model figures).
METHOD_BASIS = {
    "component SCR": "99.5th-percentile one-year loss of the modelled risk aggregation, before diversification with other balance-sheet components.",
    "governed headline": "the frozen single-df t-copula component-SCR read-out currently approved for use; re-affirmed bit-for-bit each phase, moved through no escalation P27->P30.",
    "copula-form residual": "absolute gap between a candidate copula's component SCR and the nested path-wise reference, holding margins and calibration fixed, so it isolates the dependence FORM effect.",
    "nested path-wise reference": "a full nested stochastic re-simulation applying the governed management-action rule inside every joint scenario.",
    "bootstrap CI95": "resampling the joint scenario set to obtain a 95% confidence interval for a candidate's component SCR.",
    "C-vine copula": "a cascade of bivariate copulas around root nodes; a truncated 2-tree carries fitted dependence only in the first two trees.",
    "binding stop-rule": "the pre-registered Phase 30 rule that ends dependence-form escalation once an added vine tree fits zero strength while the nested reference stays outside the candidate's 95% CI.",
    "MR-016": "model-risk register item: quantified copula-form (dependence form) residual - open and disclosed.",
    "MR-017": "model-risk register item: vine-form limitations (truncation; nested outside 95% CI) - open and disclosed.",
    "Solvency Capital Requirement (SCR)": "regulatory 99.5%/one-year capital standard; the model reports a component SCR for the modelled aggregation.",
    "model-point inventory & data contract": "load-time validation of the embedded snapshot against a build-time manifest (expected contract version + required sections).",
    "calibration basis": "per-driver parameters fixed from market/experience data on a frozen basis; surfaced read-only.",
    "management-action rule": "governed, pre-specified, deterministic application inside each scenario; not user-settable.",
    "joint management actions": "with-actions aggregation applying the governed rule jointly across drivers.",
    "path-wise bonus declaration": "scenario-by-scenario declaration along each path for a path-consistent with-actions basis.",
    "full re-aggregation & delta matrix": "complete re-aggregation with a delta matrix attributing each change's SCR effect.",
    "skew-t copula": "asymmetric tail-dependence copula assessed as a candidate dependence FORM on a fixed margin/calibration basis.",
    "grouped-t copula": "block-wise degrees-of-freedom t-copula assessed as a candidate dependence FORM on a fixed margin/calibration basis.",
    "loss distribution & percentile (VaR/ES)": "VaR reads a percentile of the simulated one-year loss; ES averages the tail beyond it; display-only over the frozen snapshot.",
    "owner decision package": "neutral assembly of pre-registered options in registry order; decision record blank until the owner completes the workflow.",
    "user run (UIL) & model_inputs": "inputs -> model_inputs.json -> par_model_v2 loader / run_model -> offline UI; the display layer recomputes nothing.",
    "governance ChangeRecord": "append-only ledger entry per change with classification and owner-review status.",
    "data-contract integrity & section digest": "in-browser pure-JS SHA-256 recompute of per-section digests from the embedded snapshot; digests content, not a model figure.",
}

# term -> indices into owner_decision_p31.limitations whose VERBATIM text is the
# limitation provenance for that term.
LIMITATION_REFS = {
    "component SCR": [2],
    "governed headline": [2],
    "copula-form residual": [2],
    "nested path-wise reference": [0],
    "bootstrap CI95": [0],
    "C-vine copula": [2],
    "binding stop-rule": [1],
    "MR-016": [2],
    "MR-017": [0, 2],
    "Solvency Capital Requirement (SCR)": [2],
    "model-point inventory & data contract": [1],
    "calibration basis": [2],
    "management-action rule": [1],
    "joint management actions": [2],
    "path-wise bonus declaration": [2],
    "full re-aggregation & delta matrix": [2],
    "skew-t copula": [2],
    "grouped-t copula": [2],
    "loss distribution & percentile (VaR/ES)": [0],
    "owner decision package": [1],
    "user run (UIL) & model_inputs": [1],
    "governance ChangeRecord": [1],
    "data-contract integrity & section digest": [1],
}

# tab id -> (primary read-out label, [term names covering it]) ; base names match
# either the verbatim glossary keys or the AUTHORED_TERMS keys.
TAB_COVERAGE = collections.OrderedDict([
    ("overview", ("Governed component SCR headline", ["governed headline", "component SCR", "Solvency Capital Requirement (SCR)"])),
    ("inventory", ("Model-point & contract inventory; data contract", ["model-point inventory & data contract"])),
    ("calibrations", ("Per-driver calibration explorer", ["calibration basis"])),
    ("capital", ("Component SCR dashboard & tail metrics", ["component SCR", "Solvency Capital Requirement (SCR)", "loss distribution & percentile (VaR/ES)"])),
    ("actions", ("Governed management-action rule", ["management-action rule"])),
    ("phase24", ("Joint-action with-actions aggregation", ["joint management actions", "management-action rule"])),
    ("phase25", ("Path-wise bonus-declaration dynamics", ["path-wise bonus declaration"])),
    ("phase26", ("Full re-aggregation & delta matrix", ["full re-aggregation & delta matrix"])),
    ("phase27", ("Skew-t tail diagnostics", ["skew-t copula", "copula-form residual"])),
    ("phase28", ("Grouped-t tail diagnostics", ["grouped-t copula", "copula-form residual"])),
    ("phase29", ("Vine tail diagnostics", ["C-vine copula", "copula-form residual"])),
    ("phase30", ("Dependence-form stop-rule", ["binding stop-rule", "MR-016", "MR-017"])),
    ("comparator", ("SCR comparator (copula-form residual ladder)", ["copula-form residual", "nested path-wise reference", "bootstrap CI95"])),
    ("distexplorer", ("Loss distribution explorer", ["loss distribution & percentile (VaR/ES)"])),
    ("ownerdecision", ("Owner decision package (P31)", ["owner decision package", "copula-form residual", "MR-016", "MR-017"])),
    ("userrun", ("User run (UIL) end-to-end example", ["user run (UIL) & model_inputs"])),
    ("governance", ("Governance ChangeRecord ledger", ["governance ChangeRecord"])),
    ("integrity", ("Data-contract integrity & per-section digests", ["data-contract integrity & section digest"])),
])


def _slug(name):
    out = []
    for ch in name.lower():
        out.append(ch if ch.isalnum() else "_")
    s = "".join(out)
    while "__" in s:
        s = s.replace("__", "_")
    return "t_" + s.strip("_")


def build_explainer(data):
    """Assemble the global glossary/explainer ENTIRELY from the embedded payload.

    All limitation text and the nine base definitions are COPIED programmatically
    (deepcopy) from owner_decision_p31 so they are carried bit-for-bit verbatim.
    """
    od = data["owner_decision_p31"]
    base_glossary = od["glossary"]              # 9 terms (verbatim defs)
    limitations = od["limitations"]            # verbatim list
    standard_references = od["standard_references"]
    figure_provenance = od["figure_provenance"]
    how_to_read = od["how_to_read"]

    # ordered union of term names: base 9 (in their existing order) then authored.
    term_names = list(base_glossary.keys())
    for name in AUTHORED_TERMS:
        if name not in term_names:
            term_names.append(name)

    # which tabs reference each term
    term_tabs = {n: [] for n in term_names}
    for tab_id, (_label, names) in TAB_COVERAGE.items():
        for n in names:
            term_tabs.setdefault(n, [])
            term_tabs[n].append(tab_id)

    terms = []
    for name in term_names:
        is_base = name in base_glossary
        definition = base_glossary[name] if is_base else AUTHORED_TERMS[name]
        if is_base:
            # carried verbatim from the embedded payload
            definition = copy.deepcopy(base_glossary[name])
        refs = LIMITATION_REFS.get(name, [])
        lim_text = [copy.deepcopy(limitations[i]) for i in refs]  # verbatim copy
        terms.append(collections.OrderedDict([
            ("id", _slug(name)),
            ("term", name),
            ("definition", definition),
            ("definition_source", "owner_decision_p31.glossary (verbatim)" if is_base
             else "explainer (plain-language; no model figure)"),
            ("method_basis", METHOD_BASIS.get(name, "")),
            ("limitation_provenance", collections.OrderedDict([
                ("carried_from", "owner_decision_p31.limitations"),
                ("refs", refs),
                ("text", lim_text),
            ])),
            ("tabs", term_tabs.get(name, [])),
        ]))

    tab_coverage = []
    for tab_id, label in TAB_ORDER:
        primary, names = TAB_COVERAGE[tab_id]
        tab_coverage.append(collections.OrderedDict([
            ("tab_id", tab_id),
            ("tab_label", label),
            ("primary_readout", primary),
            ("term_ids", [_slug(n) for n in names]),
        ]))

    explainer = collections.OrderedDict([
        ("doc", "consolidated methodology & glossary (global data dictionary)"),
        ("version", EXPLAINER_VERSION),
        ("generated_by", GENERATOR),
        ("title", "Methodology & Glossary"),
        ("display_only", True),
        ("note",
         "Build-time-assembled, display-only global glossary & data dictionary covering every "
         "governed read-out across the 18 result tabs. The nine base definitions and ALL limitation "
         "text are carried VERBATIM from owner_decision_p31; nothing is re-derived or re-labelled. "
         "This surface contains no model figure and recomputes no model quantity."),
        ("terms", terms),
        ("tab_coverage", tab_coverage),
        # verbatim carried blocks (provenance / data dictionary roots)
        ("limitations", copy.deepcopy(limitations)),
        ("standard_references", copy.deepcopy(standard_references)),
        ("provenance", collections.OrderedDict([
            ("glossary_source_key", "owner_decision_p31.glossary"),
            ("glossary_verbatim", copy.deepcopy(base_glossary)),
            ("limitations_source_key", "owner_decision_p31.limitations"),
            ("limitations_verbatim", copy.deepcopy(limitations)),
            ("figure_provenance_source_key", "owner_decision_p31.figure_provenance"),
            ("figure_provenance_verbatim", copy.deepcopy(figure_provenance)),
            ("standard_references_source_key", "owner_decision_p31.standard_references"),
            ("how_to_read_source_key", "owner_decision_p31.how_to_read"),
            ("how_to_read_verbatim", copy.deepcopy(how_to_read)),
            ("assembled_at", "build time only; no model quantity recomputed"),
        ])),
    ])
    return explainer


# --- ui_app.html render JS for the read-only Methodology & Glossary panel. ---
GLOSSARY_RENDER_JS = r"""
  // Phase 36 Task 3 (gap E2): read-only consolidated Methodology & Glossary.
  // DISPLAY-ONLY. Renders the build-time-assembled DATA.explainer global glossary
  // and per-tab coverage. It recomputes NO model figure and contains none; all
  // limitation text and the nine base definitions are carried verbatim from the
  // owner decision pack at build time. file:// safe (no network, no storage).
  function renderGlossary(){
    var el=document.getElementById("glossary"); if(!el) return;
    var ex=DATA&&DATA.explainer;
    if(!ex){ el.innerHTML='<p class="note">No glossary in this snapshot.</p>'; return; }
    var html='<h2>'+esc(ex.title||"Methodology & Glossary")+'</h2>';
    html+='<p class="note">'+esc(ex.note||"")+'</p>';
    var terms=ex.terms||[], i, j;
    // per-tab coverage table
    var tc=ex.tab_coverage||[];
    html+='<h3 style="margin:14px 0 6px">Per-tab coverage ('+tc.length+' result tabs)</h3>';
    html+='<table class="a11ytbl glosscov"><thead><tr><th>Tab</th><th>Primary read-out</th><th>Glossary terms</th></tr></thead><tbody>';
    var byId={}; for(i=0;i<terms.length;i++) byId[terms[i].id]=terms[i];
    for(i=0;i<tc.length;i++){
      var row=tc[i], tnames=[];
      for(j=0;j<(row.term_ids||[]).length;j++){ var t=byId[row.term_ids[j]]; if(t) tnames.push(esc(t.term)); }
      html+='<tr><td>'+esc(row.tab_label)+'</td><td>'+esc(row.primary_readout)+'</td><td>'+tnames.join("; ")+'</td></tr>';
    }
    html+='</tbody></table>';
    // global glossary / data dictionary
    html+='<h3 style="margin:18px 0 6px">Global glossary &amp; data dictionary ('+terms.length+' terms)</h3>';
    html+='<table class="a11ytbl glossterms"><thead><tr><th>Term</th><th>Definition</th><th>Method / assumption basis</th><th>Limitation provenance</th></tr></thead><tbody>';
    for(i=0;i<terms.length;i++){
      var tm=terms[i];
      var lim=(tm.limitation_provenance&&tm.limitation_provenance.text)||[];
      var limhtml="";
      for(j=0;j<lim.length;j++) limhtml+='<div class="glosslim">&bull; '+esc(lim[j])+'</div>';
      var vb=(tm.definition_source&&tm.definition_source.indexOf("verbatim")>=0)
        ? ' <span class="chip pass" title="carried verbatim from the owner decision pack">verbatim</span>' : '';
      html+='<tr data-glossterm="'+esc(tm.id)+'"><td class="mono">'+esc(tm.term)+vb+'</td>'+
        '<td>'+esc(tm.definition)+'</td>'+
        '<td>'+esc(tm.method_basis||"")+'</td>'+
        '<td>'+(limhtml||'<span class="muted">&mdash;</span>')+'</td></tr>';
    }
    html+='</tbody></table>';
    // verbatim limitation roots (carried bit-for-bit)
    var L=ex.limitations||[];
    html+='<h3 style="margin:18px 0 6px">Model limitations (carried verbatim)</h3><ul class="glossroot">';
    for(i=0;i<L.length;i++) html+='<li>'+esc(L[i])+'</li>';
    html+='</ul>';
    var R=ex.standard_references||[];
    if(R.length){ html+='<h3 style="margin:14px 0 6px">Standard references</h3><ul class="glossroot">';
      for(i=0;i<R.length;i++) html+='<li>'+esc(R[i])+'</li>'; html+='</ul>'; }
    html+='<p class="muted">Assembled at build time from the embedded snapshot ('+
      esc((ex.provenance&&ex.provenance.glossary_source_key)||"owner_decision_p31.glossary")+
      '). Display-only: no model figure is shown or recomputed.</p>';
    el.innerHTML=html;
  }
"""


def _patch_html(html, new_json):
    # 1. embedded payload byte-sync (reuse the A2 token swap).
    html = a2._embed_token_swap(html, new_json)

    # 2. TABS: add the Methodology & Glossary tab after Integrity.
    tabs_anchor = '["integrity","Integrity (H1)"]\n  ];'
    assert html.count(tabs_anchor) == 1, "TABS integrity anchor not unique/found"
    html = html.replace(
        tabs_anchor,
        '["integrity","Integrity (H1)"],\n'
        '    ["glossary","Methodology & Glossary"]\n  ];',
    )

    # 3. add the panel container div after the Integrity panel.
    panel_anchor = '<div id="integrity" class="panel" data-title="Integrity (H1)"></div>'
    assert html.count(panel_anchor) == 1, "integrity panel anchor not unique/found"
    html = html.replace(
        panel_anchor,
        panel_anchor +
        '\n  <div id="glossary" class="panel" data-title="Methodology &amp; Glossary"></div>',
    )

    # 4. inject renderGlossary() just before renderAll().
    renderall_anchor = "\n  function renderAll(){\n    renderHeader();"
    assert html.count(renderall_anchor) == 1, "renderAll anchor not unique/found"
    html = html.replace(renderall_anchor, "\n" + GLOSSARY_RENDER_JS + renderall_anchor)

    # 5. call renderGlossary() inside renderAll (after renderIntegrity()).
    call_anchor = "renderIntegrity(); renderIntegrityBanner();"
    assert html.count(call_anchor) == 1, "renderAll call anchor not unique/found"
    html = html.replace(call_anchor, "renderIntegrity(); renderGlossary(); renderIntegrityBanner();")
    return html


def main(check_only=False):
    with open(UI_DATA, encoding="utf-8") as fh:
        data = json.load(fh, object_pairs_hook=collections.OrderedDict)

    assert data.get("contract_version") == PRIOR_CONTRACT, (
        "unexpected prior contract %r (expected %r)"
        % (data.get("contract_version"), PRIOR_CONTRACT))
    assert EXPLAINER_KEY not in data, "explainer key already present"
    man = data.get("contract_manifest")
    assert isinstance(man, dict), "contract_manifest missing"
    assert "section_digests" in man, "expected A2 section_digests present"

    explainer = build_explainer(data)

    # integrity self-asserts: verbatim carry-through (built from the live payload).
    od = data["owner_decision_p31"]
    assert explainer["provenance"]["glossary_verbatim"] == od["glossary"]
    assert explainer["limitations"] == od["limitations"]
    assert explainer["provenance"]["limitations_verbatim"] == od["limitations"]
    for t in explainer["terms"]:
        if t["definition_source"].startswith("owner_decision_p31"):
            assert t["definition"] == od["glossary"][t["term"]], (
                "base def not verbatim: %r" % t["term"])
    covered = {tc["tab_id"] for tc in explainer["tab_coverage"]}
    assert covered == {tid for tid, _ in TAB_ORDER}, "tab coverage incomplete"
    # NO model figure introduced by AUTHORED content (authored definitions,
    # method bases, tab labels/read-outs). Verbatim-carried glossary definitions
    # and the provenance blocks may legitimately quote already-governed figures;
    # carrying them bit-for-bit is display, not recomputation, so they are exempt.
    authored_blob = json.dumps(AUTHORED_TERMS, default=str) + json.dumps(METHOD_BASIS, default=str)
    for tc in explainer["tab_coverage"]:
        authored_blob += tc["primary_readout"] + tc["tab_label"]
    for forbidden in ("39975.654628199336", "39,975", "46,638", "46638.9", "3,637"):
        assert forbidden not in authored_blob, "authored explainer text must contain no model figure: %r" % forbidden

    # --- build the new payload (explainer inserted before contract_manifest) ---
    new_data = collections.OrderedDict()
    for k, v in data.items():
        if k == "contract_manifest":
            new_data[EXPLAINER_KEY] = explainer
        new_data[k] = v
    if EXPLAINER_KEY not in new_data:  # manifest somehow last/missing
        new_data[EXPLAINER_KEY] = explainer

    new_data["contract_version"] = NEW_CONTRACT
    nman = new_data["contract_manifest"]
    nman["expected_contract_version"] = NEW_CONTRACT
    req = list(nman["required_top_level_keys"])
    if EXPLAINER_KEY not in req:
        req.append(EXPLAINER_KEY)
    nman["required_top_level_keys"] = req
    nman["key_count"] = len(req)
    base_note = nman.get("note", "")
    add_note = (" Global methodology & glossary (explainer) added additively in 1.21.0 (gap E2): "
                "display-only, no model figure, base definitions/limitations carried verbatim.")
    if "1.21.0" not in base_note:
        nman["note"] = (base_note + add_note).strip()

    # recompute per-section digests over the NEW payload (24 sections) using the
    # EXACT embedded JS, then write them into the manifest.
    res = a2.compute_digests_via_node(new_data)
    section_digests = res["section_digests"]
    root_digest = res["root_digest"]
    expected_top = sorted(k for k in new_data.keys() if k != "contract_manifest")
    assert res["keys"] == expected_top, "digest key set mismatch"
    assert EXPLAINER_KEY in section_digests, "explainer not digested"
    nman["section_digests"] = section_digests
    nman["root_digest"] = root_digest
    nman["digest_generated_by"] = (
        a2.GENERATOR + " + " + GENERATOR)

    new_json = json.dumps(new_data, default=str)
    json.loads(new_json)  # re-parse guard

    if check_only:
        print(json.dumps({
            "mode": "check", "contract": "%s -> %s" % (PRIOR_CONTRACT, NEW_CONTRACT),
            "terms": len(explainer["terms"]),
            "tab_coverage": len(explainer["tab_coverage"]),
            "sections_digested": len(section_digests),
            "root_digest": root_digest,
        }, indent=1))
        return 0

    with open(UI_APP, encoding="utf-8") as fh:
        html = fh.read()
    html = _patch_html(html, new_json)

    with open(UI_DATA, "w", encoding="utf-8") as fh:
        fh.write(new_json)
    with open(UI_APP, "w", encoding="utf-8") as fh:
        fh.write(html)

    # --- re-parse + integrity guards on disk ---
    with open(UI_DATA, encoding="utf-8") as fh:
        chk = json.load(fh)
    assert chk["contract_version"] == NEW_CONTRACT
    assert EXPLAINER_KEY in chk
    cman = chk["contract_manifest"]
    assert cman["root_digest"] == root_digest
    assert cman["key_count"] == len(expected_top)
    assert EXPLAINER_KEY in cman["required_top_level_keys"]

    h2 = open(UI_APP, encoding="utf-8").read()
    a = h2.find("/*__UI_DATA__*/") + len("/*__UI_DATA__*/")
    b = h2.find("</script>", a)
    emb = json.loads(h2[a:b])
    assert emb["contract_version"] == NEW_CONTRACT
    assert "explainer" in emb
    assert 'id="glossary"' in h2 and "function renderGlossary(" in h2
    assert '["glossary","Methodology & Glossary"]' in h2

    # confirm embedded payload recomputes to the SAME digests via Node.
    recheck = a2.compute_digests_via_node(emb)
    assert recheck["root_digest"] == root_digest, "embedded recompute root mismatch"
    assert recheck["section_digests"] == section_digests, "embedded recompute mismatch"

    print(json.dumps({
        "verdict": "PASS",
        "contract": "%s -> %s" % (PRIOR_CONTRACT, NEW_CONTRACT),
        "terms": len(explainer["terms"]),
        "tab_coverage": len(explainer["tab_coverage"]),
        "sections_digested": len(section_digests),
        "root_digest": root_digest,
        "embedded_recompute_matches": True,
        "ui_data_bytes": len(new_json.encode("utf-8")),
        "ui_app_bytes": len(h2.encode("utf-8")),
    }, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(check_only="--check" in sys.argv))
