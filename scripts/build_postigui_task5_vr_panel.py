#!/usr/bin/env python3
"""Post-Phase-IGUI Task 5 - ADDITIVE offline-UI efficiency panel for the
MR-VR-1 inner-path variance-reduction study.

WHAT THIS LAYER DOES
--------------------
It is the fourth ADDITIVE patch layer on top of the published offline-UI
contract (after A1 a11y_audit -> 1.19.0, A2 section_digests -> 1.20.0, E2
explainer -> 1.21.0). It adds ONE new top-level ``ui_data`` key
``postigui_vr`` (additive contract bump 1.21.0 -> 1.22.0) and a new read-only
"Variance Reduction (MR-VR-1)" result tab/panel that surfaces, FROM MODEL
OUTPUT ONLY, the governed MR-VR-1 study:

  * work-normalised variance-reduction ratios + 95% CIs (antithetic / Sobol-RQMC
    / CRN) and the >=1.5x "useful" disposition;
  * effective-sample-size per technique;
  * target-SE inner-path counts n* (for SE_rel = 1%);
  * the unbiasedness panel (all estimators within tolerance of the analytic /
    crude reference);
  * the antithetic-at-99.5% INEFFECTIVE disclosure (work-normalised ratio below
    the 1.5x bar, the same qualitative finding as the recorded outer-basis
    precedents);
  * the governed-headline invariance (39,975.654628199336 BIT-IDENTICAL) and the
    adoption-materiality verdict (indicated dSCR immaterial -> REPORTED, NOT
    applied).

DISPLAY-ONLY. Every figure is carried bit-for-bit from
``docs/validation/POSTIGUI_TASK4_VARIANCE_REDUCTION.json`` (the governed Task 4
model-output report); NOTHING is recomputed in this layer or in the browser.
Every pre-existing ``ui_data`` key renders bit-identically; the A2 per-section
SHA-256 digests are recomputed with the EXACT embedded JS (new ``postigui_vr``
section digested, root recomputed) so the in-browser verifier still agrees.
Zero-install preserved (0 external refs, single self-contained file:// HTML, no
storage API). NO model parameter change; the binding Phase 30 stop-rule stands;
the MR-016/MR-017 dependence decision is NOT pre-empted. Idempotent.

Run (operates IN PLACE on REPO's ui_data.json + ui_app.html):
    PYTHONPATH=. python3 scripts/build_postigui_task5_vr_panel.py
    PYTHONPATH=. python3 scripts/build_postigui_task5_vr_panel.py --check
"""
from __future__ import annotations

import collections
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HERE = os.path.join(REPO, "scripts")
UI_DATA = os.path.join(REPO, "ui_data.json")
UI_APP = os.path.join(REPO, "ui_app.html")
VR_REPORT = os.path.join(REPO, "docs", "validation",
                         "POSTIGUI_TASK4_VARIANCE_REDUCTION.json")

sys.path.insert(0, HERE)
import build_phase35_task3_a2_digests as a2  # noqa: E402

PRIOR_CONTRACT = "1.21.0"
NEW_CONTRACT = "1.22.0"
VR_KEY = "postigui_vr"
VR_VERSION = "1.0.0"
GENERATOR = ("scripts/build_postigui_task5_vr_panel.py "
             "(Post-Phase-IGUI Task 5, MR-VR-1 efficiency panel)")

# The governed Task-4 report fields carried bit-for-bit into the display layer.
# Nothing here is recomputed: the section is a display-normalised projection of
# the source report, which is the authoritative model output.


def build_vr_section() -> "collections.OrderedDict":
    with open(VR_REPORT, encoding="utf-8") as fh:
        rep = json.load(fh, object_pairs_hook=collections.OrderedDict)

    rs = rep["replicate_study"]
    section = collections.OrderedDict([
        ("title", "Inner-Path Variance Reduction (MR-VR-1)"),
        ("version", VR_VERSION),
        ("candidate_id", rep["candidate_id"]),
        ("classification", rep["classification"]),
        ("note",
         "Display-only efficiency panel. Every figure is carried bit-for-bit "
         "from the governed MR-VR-1 model-output report "
         "(docs/validation/POSTIGUI_TASK4_VARIANCE_REDUCTION.json); nothing is "
         "recomputed here or in the browser. Variance reduction is a NUMERICAL "
         "efficiency change (admissible under the Phase 30 stop-rule); the "
         "governed production estimator and headline stay frozen."),
        ("techniques", rep["vr_techniques"]),
        ("grid", rep["grid"]),
        ("headline_invariance", rep["governed_headline_invariance"]),
        ("analytic_inner_value", rs["analytic_inner_value"]),
        ("n_replicates", rs["n_replicates"]),
        ("n_inner", rs["n_inner"]),
        ("estimator_summaries", rs["estimator_summaries"]),
        ("variance_reduction_ratios", rs["variance_reduction_ratios"]),
        ("effective_sample_size", rs["effective_sample_size"]),
        ("n_star_for_target_se", rs["n_star_for_target_se"]),
        ("target_se_rel", rs["target_se_rel"]),
        ("unbiasedness", rs["unbiasedness"]),
        ("any_useful_ge_1p5x", rs["any_useful_ge_1p5x"]),
        ("interpretation", rs["interpretation"]),
        ("tail_study", rep["tail_study"]),
        ("adoption_materiality", rep["adoption_materiality"]),
        ("digest", rep["digest"]),
        ("validation_gate", rep["validation_gate"]),
        ("provenance", collections.OrderedDict([
            ("source_report",
             "docs/validation/POSTIGUI_TASK4_VARIANCE_REDUCTION.json"),
            ("source_digest", rep["digest"]),
            ("display_only", True),
            ("recomputes_model_quantity", False),
            ("assembled_by", GENERATOR),
        ])),
    ])
    return section


# --- ui_app.html render JS for the read-only VR efficiency panel. ------------
VR_RENDER_JS = r"""
  // Post-Phase-IGUI Task 5 (MR-VR-1): read-only inner-path variance-reduction
  // efficiency panel. DISPLAY-ONLY. Renders DATA.postigui_vr - the governed
  // Task-4 model-output study carried bit-for-bit. It recomputes NO model
  // figure. file:// safe (no network, no storage).
  function renderVrPanel(){
    var el=document.getElementById("vrpanel"); if(!el) return;
    var v=DATA&&DATA.postigui_vr;
    if(!v){ el.innerHTML='<p class="note">No variance-reduction study in this snapshot.</p>'; return; }
    function num(x,d){ if(x==null||isNaN(x)) return "&mdash;";
      var n=Number(x); d=(d==null)?4:d;
      if(Math.abs(n)>=1e6) return n.toExponential(3);
      return n.toLocaleString(undefined,{minimumFractionDigits:0,maximumFractionDigits:d}); }
    function pct(x,d){ if(x==null||isNaN(x)) return "&mdash;"; d=(d==null)?3:d;
      return (Number(x)*100).toFixed(d)+"%"; }
    function chip(ok,t,f){ return ok?('<span class="chip pass">'+esc(t||"yes")+'</span>')
      :('<span class="chip warn">'+esc(f||"no")+'</span>'); }
    var html='<h2>'+esc(v.title||"Inner-Path Variance Reduction")+'</h2>';
    html+='<p class="note">Candidate <span class="mono">'+esc(v.candidate_id||"")+'</span> &middot; classification '
      +'<span class="chip pass">'+esc(v.classification||"")+'</span> &middot; '+esc(v.note||"")+'</p>';

    // Governed-headline invariance card.
    var hi=v.headline_invariance||{}, hb=hi.before||{}, ha=hi.after||{};
    html+='<div class="cards" data-vr="invariance"><div class="card"><div class="k">Governed headline invariance</div>'
      +'<div class="val">'+chip(hi.bit_identical,"BIT-IDENTICAL","moved")+'</div>'
      +'<div class="sub">frozen-t component SCR '+num(hb.frozen_t_component_scr,6)+' &rarr; '+num(ha.frozen_t_component_scr,6)
      +' &middot; max|dev| '+num(hi.max_abs_dev,9)+' (tol '+num(hi.tol,9)+')'
      +' &middot; '+chip(hi.additive_disclosed_not_a_swap,"additive / disclosed, not a swap","swap")+'</div></div></div>';

    // Variance-reduction ratios (work-normalised) + 95% CI.
    var rr=v.variance_reduction_ratios||{};
    html+='<h3 style="margin:16px 0 6px">Work-normalised variance-reduction ratios (95% CI)</h3>';
    html+='<table class="a11ytbl vrratios"><caption class="sr-only">MR-VR-1 work-normalised VR ratios with 95% CIs and the &ge;1.5&times; useful bar</caption>'
      +'<thead><tr><th>Technique</th><th>VR ratio</th><th>95% CI</th><th>Useful (&ge;1.5&times;)</th></tr></thead><tbody>';
    var rorder=[["antithetic","Antithetic"],["crn","CRN (guarantee on/off)"],["sobol_qmc","Sobol-RQMC"]];
    for(var i=0;i<rorder.length;i++){ var rk=rorder[i][0], r=rr[rk]; if(!r) continue;
      html+='<tr data-vr-tech="'+esc(rk)+'"><td>'+esc(rorder[i][1])+'</td>'
        +'<td class="mono">'+num(r.ratio,(r.ratio>=100?1:3))+'&times;</td>'
        +'<td class="mono">['+num(r.ci95_lo,(r.ci95_lo>=100?1:3))+', '+num(r.ci95_hi,(r.ci95_hi>=100?1:3))+']</td>'
        +'<td>'+chip(r.useful_ge_threshold,"useful","sub-useful")+'</td></tr>';
    }
    html+='</tbody></table>';

    // Effective sample size + n* for target SE.
    var ess=v.effective_sample_size||{}, ns=v.n_star_for_target_se||{};
    html+='<h3 style="margin:16px 0 6px">Effective sample size &amp; inner-path count n* for target SE_rel = '
      +pct(v.target_se_rel,2)+'</h3>';
    html+='<table class="a11ytbl vress"><caption class="sr-only">Effective sample size per technique and the inner-path count n* needed to reach the target relative SE</caption>'
      +'<thead><tr><th>Technique</th><th>Effective sample size</th><th>n* for target SE</th></tr></thead><tbody>';
    var eorder=[["crude","Crude i.i.d."],["antithetic","Antithetic"],["crn","CRN"],["sobol_qmc","Sobol-RQMC"]];
    for(var j=0;j<eorder.length;j++){ var ek=eorder[j][0];
      html+='<tr data-vr-ess="'+esc(ek)+'"><td>'+esc(eorder[j][1])+'</td>'
        +'<td class="mono">'+(ess[ek]!=null?num(ess[ek],0):'<span class="muted">&mdash;</span>')+'</td>'
        +'<td class="mono">'+(ns[ek]!=null?num(ns[ek],(ns[ek]<100?2:0)):'<span class="muted">&mdash;</span>')+'</td></tr>';
    }
    html+='</tbody></table>';

    // Unbiasedness panel.
    var ub=v.unbiasedness||{};
    html+='<h3 style="margin:16px 0 6px">Unbiasedness vs the analytic / crude reference</h3>';
    html+='<p class="note">Analytic inner value <span class="mono">'+num(ub.analytic_value,6)+'</span> &middot; '
      +'all estimators within tolerance '+pct(ub.tol_rel,2)+': '+chip(ub.all_within_tol,"yes","NO")+'</p>';
    html+='<table class="a11ytbl vrunbias"><caption class="sr-only">Per-estimator relative deviation from the analytic and crude references (unbiasedness)</caption>'
      +'<thead><tr><th>Estimator</th><th>Mean</th><th>Rel. vs analytic</th></tr></thead><tbody>';
    var es=v.estimator_summaries||{};
    var uorder=[["crude","Crude","crude_rel_vs_analytic"],["antithetic","Antithetic","antithetic_rel_vs_analytic"],
      ["sobol_qmc","Sobol-RQMC","sobol_rel_vs_analytic"],["crn_difference","CRN difference","crn_rel_vs_analytic"]];
    for(var u=0;u<uorder.length;u++){ var us=es[uorder[u][0]]||{};
      html+='<tr><td>'+esc(uorder[u][1])+'</td><td class="mono">'+num(us.mean,4)+'</td>'
        +'<td class="mono">'+(ub[uorder[u][2]]!=null?pct(ub[uorder[u][2]],4):'<span class="muted">&mdash;</span>')+'</td></tr>';
    }
    html+='</tbody></table>';

    // Antithetic-at-99.5% INEFFECTIVE disclosure.
    var ts=v.tail_study||{}, tr=ts.antithetic_work_normalised_ratio||{}, pre=ts.precedent_outer_basis||{};
    html+='<h3 style="margin:16px 0 6px">Antithetic at the 99.5% capital quantile &mdash; INEFFECTIVE (disclosed)</h3>';
    html+='<div class="cards" data-vr="tail"><div class="card"><div class="k">Antithetic 99.5% work-normalised ratio</div>'
      +'<div class="val">'+num(tr.ratio,3)+'&times; '+chip(!ts.antithetic_ineffective_at_995,"useful","sub-useful (ineffective)")+'</div>'
      +'<div class="sub">95% CI ['+num(tr.ci95_lo,3)+', '+num(tr.ci95_hi,3)+'] &middot; below the 1.5&times; bar &middot; '
      +'outer-basis precedents '+num(pre.antithetic_p19_4d,2)+'&times; / '+num(pre.antithetic_p21,2)+'&times; (also sub-useful)</div></div></div>';
    html+='<p class="note">'+esc(ts.disclosure||"")+'</p>';

    // Adoption materiality verdict.
    var am=v.adoption_materiality||{};
    html+='<h3 style="margin:16px 0 6px">Adoption materiality &mdash; REPORTED, NOT applied</h3>';
    html+='<div class="cards" data-vr="adoption"><div class="card"><div class="k">Indicated dSCR (variance-reduced vs crude)</div>'
      +'<div class="val">'+pct(am.indicated_rel_dscr,4)+' '+chip(!am.is_material,"immaterial","MATERIAL")+'</div>'
      +'<div class="sub">threshold '+pct(am.materiality_threshold_rel,2)+' &middot; applied: '+chip(!am.applied,"NO (frozen)","yes")
      +' &middot; '+esc(am.disposition||"")+'</div></div></div>';

    html+='<p class="note">'+esc(v.interpretation||"")+'</p>';
    var g=v.validation_gate||{};
    html+='<p class="muted">Validation gate: '+chip(g.ok,"ok:true","ok:false")+' &middot; '+num(g.n_checks,0)
      +' checks &middot; study digest <span class="mono">'+esc((v.digest||"").slice(0,12))+'&hellip;</span> &middot; '
      +'carried bit-for-bit from '+esc((v.provenance&&v.provenance.source_report)||"")+'. Display-only: no model figure recomputed.</p>';
    el.innerHTML=html;
  }
"""


def _patch_html(html: str, new_json: str) -> str:
    # 1. embedded payload byte-sync (reuse the A2 token swap).
    html = a2._embed_token_swap(html, new_json)

    # 2. TABS: add the Variance Reduction tab after the Methodology & Glossary tab.
    tabs_anchor = '["glossary","Methodology & Glossary"]\n  ];'
    assert html.count(tabs_anchor) == 1, "TABS glossary anchor not unique/found"
    html = html.replace(
        tabs_anchor,
        '["glossary","Methodology & Glossary"],\n'
        '    ["vrpanel","Variance Reduction (MR-VR-1)"]\n  ];',
    )

    # 3. add the panel container div after the Glossary panel.
    panel_anchor = ('<div id="glossary" class="panel" '
                    'data-title="Methodology &amp; Glossary"></div>')
    assert html.count(panel_anchor) == 1, "glossary panel anchor not unique/found"
    html = html.replace(
        panel_anchor,
        panel_anchor +
        '\n  <div id="vrpanel" class="panel" '
        'data-title="Variance Reduction (MR-VR-1)"></div>',
    )

    # 4. inject renderVrPanel() just before renderAll().
    renderall_anchor = "\n  function renderAll(){\n    renderHeader();"
    assert html.count(renderall_anchor) == 1, "renderAll anchor not unique/found"
    html = html.replace(renderall_anchor, "\n" + VR_RENDER_JS + renderall_anchor)

    # 5. call renderVrPanel() inside renderAll (after renderGlossary()).
    call_anchor = "renderGlossary(); renderIntegrityBanner();"
    assert html.count(call_anchor) == 1, "renderAll call anchor not unique/found"
    html = html.replace(
        call_anchor, "renderGlossary(); renderVrPanel(); renderIntegrityBanner();")
    return html


def main(check_only: bool = False) -> int:
    with open(UI_DATA, encoding="utf-8") as fh:
        data = json.load(fh, object_pairs_hook=collections.OrderedDict)

    assert data.get("contract_version") == PRIOR_CONTRACT, (
        "unexpected prior contract %r (expected %r)"
        % (data.get("contract_version"), PRIOR_CONTRACT))
    assert VR_KEY not in data, "postigui_vr key already present"
    man = data.get("contract_manifest")
    assert isinstance(man, dict), "contract_manifest missing"
    assert "section_digests" in man, "expected A2 section_digests present"
    assert "explainer" in data, "expected E2 explainer present"

    vr = build_vr_section()

    # Integrity self-asserts: figures carried bit-for-bit from the source report.
    with open(VR_REPORT, encoding="utf-8") as fh:
        src = json.load(fh)
    assert vr["headline_invariance"] == src["governed_headline_invariance"]
    assert vr["variance_reduction_ratios"] == src["replicate_study"]["variance_reduction_ratios"]
    assert vr["effective_sample_size"] == src["replicate_study"]["effective_sample_size"]
    assert vr["n_star_for_target_se"] == src["replicate_study"]["n_star_for_target_se"]
    assert vr["tail_study"] == src["tail_study"]
    assert vr["adoption_materiality"] == src["adoption_materiality"]
    assert vr["digest"] == src["digest"]
    # Governed headline carried exactly; not relabelled.
    assert vr["headline_invariance"]["before"]["frozen_t_component_scr"] == 39975.654628199336
    assert vr["headline_invariance"]["bit_identical"] is True
    # Antithetic-99.5% disclosed ineffective (the required disclosure).
    assert vr["tail_study"]["antithetic_ineffective_at_995"] is True
    assert vr["tail_study"]["antithetic_work_normalised_ratio"]["useful_ge_threshold"] is False
    # Adoption immaterial, reported not applied.
    assert vr["adoption_materiality"]["is_material"] is False
    assert vr["adoption_materiality"]["applied"] is False

    # --- build the new payload (postigui_vr inserted before contract_manifest) ---
    new_data = collections.OrderedDict()
    for k, val in data.items():
        if k == "contract_manifest":
            new_data[VR_KEY] = vr
        new_data[k] = val
    if VR_KEY not in new_data:  # manifest somehow last/missing
        new_data[VR_KEY] = vr

    new_data["contract_version"] = NEW_CONTRACT
    nman = new_data["contract_manifest"]
    nman["expected_contract_version"] = NEW_CONTRACT
    req = list(nman["required_top_level_keys"])
    if VR_KEY not in req:
        req.append(VR_KEY)
    nman["required_top_level_keys"] = req
    nman["key_count"] = len(req)
    base_note = nman.get("note", "")
    add_note = (" MR-VR-1 inner-path variance-reduction efficiency panel "
                "(postigui_vr) added additively in 1.22.0 (Post-Phase-IGUI "
                "Task 5): display-only, no model figure recomputed, figures "
                "carried bit-for-bit from the governed Task-4 report.")
    if "1.22.0" not in base_note:
        nman["note"] = (base_note + add_note).strip()

    # recompute per-section digests over the NEW payload using the EXACT embedded
    # JS, then write them into the manifest.
    res = a2.compute_digests_via_node(new_data)
    section_digests = res["section_digests"]
    root_digest = res["root_digest"]
    expected_top = sorted(k for k in new_data.keys() if k != "contract_manifest")
    assert res["keys"] == expected_top, "digest key set mismatch"
    assert VR_KEY in section_digests, "postigui_vr not digested"
    nman["section_digests"] = section_digests
    nman["root_digest"] = root_digest
    nman["digest_generated_by"] = (
        man.get("digest_generated_by", a2.GENERATOR) + " + " + GENERATOR)

    new_json = json.dumps(new_data, default=str)
    json.loads(new_json)  # re-parse guard

    if check_only:
        print(json.dumps({
            "mode": "check", "contract": "%s -> %s" % (PRIOR_CONTRACT, NEW_CONTRACT),
            "vr_techniques": len(vr["techniques"]),
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
    assert VR_KEY in chk
    cman = chk["contract_manifest"]
    assert cman["root_digest"] == root_digest
    assert cman["key_count"] == len(expected_top)
    assert VR_KEY in cman["required_top_level_keys"]

    h2 = open(UI_APP, encoding="utf-8").read()
    a = h2.find("/*__UI_DATA__*/") + len("/*__UI_DATA__*/")
    b = h2.find("</script>", a)
    emb = json.loads(h2[a:b])
    assert emb["contract_version"] == NEW_CONTRACT
    assert VR_KEY in emb
    assert 'id="vrpanel"' in h2 and "function renderVrPanel(" in h2
    assert '["vrpanel","Variance Reduction (MR-VR-1)"]' in h2

    # confirm embedded payload recomputes to the SAME digests via Node.
    recheck = a2.compute_digests_via_node(emb)
    assert recheck["root_digest"] == root_digest, "embedded recompute root mismatch"
    assert recheck["section_digests"] == section_digests, "embedded recompute mismatch"

    print(json.dumps({
        "verdict": "PASS",
        "contract": "%s -> %s" % (PRIOR_CONTRACT, NEW_CONTRACT),
        "vr_techniques": len(vr["techniques"]),
        "sections_digested": len(section_digests),
        "root_digest": root_digest,
        "embedded_recompute_matches": True,
        "ui_data_bytes": len(new_json.encode("utf-8")),
        "ui_app_bytes": len(h2.encode("utf-8")),
    }, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(check_only="--check" in sys.argv))
