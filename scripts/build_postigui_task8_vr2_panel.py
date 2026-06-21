#!/usr/bin/env python3
"""Post-Phase-IGUI Task 8 - ADDITIVE offline-UI efficiency panel for the
MR-VR-2 OUTER-loop variance-reduction study.

WHAT THIS LAYER DOES
--------------------
It is the fifth ADDITIVE patch layer on top of the published offline-UI
contract (after A1 a11y_audit -> 1.19.0, A2 section_digests -> 1.20.0, E2
explainer -> 1.21.0, MR-VR-1 postigui_vr -> 1.22.0). It adds ONE new
top-level ``ui_data`` key ``postigui_vr2`` (additive contract bump
1.22.0 -> 1.23.0) and a new read-only "Outer-Loop Variance Reduction
(MR-VR-2)" result tab/panel that surfaces, FROM MODEL OUTPUT ONLY, the
governed MR-VR-2 study (the outer capital / 99.5% SCR estimator):

  * work-normalised variance-reduction ratios + 95% CIs on BOTH the OUTER
    mean-loss target (sobol_rqmc / control_variate / stratified) and the
    99.5% SCR tail target (sobol_rqmc / control_variate / stratified /
    rqmc_plus_cv), with the >=1.5x "useful" disposition per technique;
  * the control-variate fit (beta, control-target correlation rho, and the
    theoretical mean-leg reduction 1/(1-rho^2));
  * effective-sample-size per technique on both targets;
  * the inner/outer-path count n* (for SE_rel = 1%) on the mean target;
  * the unbiasedness panels (mean and SCR estimators within tolerance of the
    analytic / crude reference; control-variate beta fit OUT-OF-SAMPLE);
  * the MEASURED-NOT-ASSUMED disclosure that control-variate-ALONE is
    INEFFECTIVE on the 99.5% SCR quantile leg (work-normalised ratio 0.93x,
    below the 1.5x bar) - the OUTER-loop analogue of MR-VR-1's antithetic-
    ineffective-at-99.5% finding - while RQMC / stratification / RQMC+CV are
    the levers for the quantile leg (best technique: stratified);
  * the governed-headline invariance (39,975.654628199336 BIT-IDENTICAL) and
    the adoption-materiality verdict (indicated dSCR immaterial -> REPORTED,
    NOT applied).

DISPLAY-ONLY. Every figure is carried bit-for-bit from
``docs/validation/POSTIGUI_TASK7_OUTER_VARIANCE_REDUCTION.json`` (the governed
Task-7 model-output report); NOTHING is recomputed in this layer or in the
browser. Every pre-existing ``ui_data`` key renders bit-identically; the A2
per-section SHA-256 digests are recomputed with the EXACT embedded JS (new
``postigui_vr2`` section digested, root recomputed) so the in-browser verifier
still agrees. Zero-install preserved (0 external refs, single self-contained
file:// HTML, no storage API). NO model parameter change; the binding Phase 30
stop-rule stands; the MR-016/MR-017 dependence decision is NOT pre-empted.
Idempotent.

Run (operates IN PLACE on REPO's ui_data.json + ui_app.html):
    PYTHONPATH=. python3 scripts/build_postigui_task8_vr2_panel.py
    PYTHONPATH=. python3 scripts/build_postigui_task8_vr2_panel.py --check
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
                         "POSTIGUI_TASK7_OUTER_VARIANCE_REDUCTION.json")

sys.path.insert(0, HERE)
import build_phase35_task3_a2_digests as a2  # noqa: E402

PRIOR_CONTRACT = "1.22.0"
NEW_CONTRACT = "1.23.0"
VR2_KEY = "postigui_vr2"
VR2_VERSION = "1.0.0"
GENERATOR = ("scripts/build_postigui_task8_vr2_panel.py "
             "(Post-Phase-IGUI Task 8, MR-VR-2 outer-loop efficiency panel)")
GOVERNED_HEADLINE = 39975.654628199336


def build_vr2_section() -> "collections.OrderedDict":
    with open(VR_REPORT, encoding="utf-8") as fh:
        rep = json.load(fh, object_pairs_hook=collections.OrderedDict)

    rs = rep["replicate_study"]
    ts = rep["scr_tail_study"]
    section = collections.OrderedDict([
        ("title", "Outer-Loop Variance Reduction (MR-VR-2)"),
        ("version", VR2_VERSION),
        ("candidate_id", rep["candidate_id"]),
        ("classification", rep["classification"]),
        ("note",
         "Display-only efficiency panel. Every figure is carried bit-for-bit "
         "from the governed MR-VR-2 model-output report "
         "(docs/validation/POSTIGUI_TASK7_OUTER_VARIANCE_REDUCTION.json); "
         "nothing is recomputed here or in the browser. Variance reduction is a "
         "NUMERICAL efficiency change on the OUTER capital / 99.5% SCR estimator "
         "(admissible under the Phase 30 stop-rule); the governed production "
         "estimator and headline stay frozen."),
        ("techniques", rep["vr_techniques"]),
        ("grid", rep["grid"]),
        ("control_variate_fit", rep["control_variate_fit"]),
        ("headline_invariance", rep["governed_headline_invariance"]),
        # OUTER mean-loss target
        ("analytic_mean_loss", rs["analytic_mean_loss"]),
        ("n_replicates", rs["n_replicates"]),
        ("n_outer", rs["n_outer"]),
        ("mean_estimator_summaries", rs["estimator_summaries"]),
        ("mean_variance_reduction_ratios", rs["variance_reduction_ratios"]),
        ("mean_effective_sample_size", rs["effective_sample_size"]),
        ("n_star_for_target_se", rs["n_star_for_target_se"]),
        ("target_se_rel", rs["target_se_rel"]),
        ("mean_unbiasedness", rs["unbiasedness"]),
        ("mean_interpretation", rs["interpretation"]),
        # 99.5% SCR tail target
        ("scr_tail_study", ts),
        ("best_tail_technique", ts["best_technique"]),
        ("control_rho", ts["control_rho"]),
        ("control_one_over_1_minus_rho2", ts["control_one_over_1_minus_rho2"]),
        ("adoption_materiality", rep["adoption_materiality"]),
        ("digest", rep["digest"]),
        ("validation_gate", rep["validation_gate"]),
        ("provenance", collections.OrderedDict([
            ("source_report",
             "docs/validation/POSTIGUI_TASK7_OUTER_VARIANCE_REDUCTION.json"),
            ("source_digest", rep["digest"]),
            ("display_only", True),
            ("recomputes_model_quantity", False),
            ("assembled_by", GENERATOR),
        ])),
    ])
    return section


# --- ui_app.html render JS for the read-only MR-VR-2 efficiency panel. --------
VR2_RENDER_JS = r"""
  // Post-Phase-IGUI Task 8 (MR-VR-2): read-only OUTER-loop variance-reduction
  // efficiency panel. DISPLAY-ONLY. Renders DATA.postigui_vr2 - the governed
  // Task-7 model-output study carried bit-for-bit. It recomputes NO model
  // figure. file:// safe (no network, no storage).
  function renderVr2Panel(){
    var el=document.getElementById("vr2panel"); if(!el) return;
    var v=DATA&&DATA.postigui_vr2;
    if(!v){ el.innerHTML='<p class="note">No outer-loop variance-reduction study in this snapshot.</p>'; return; }
    function num(x,d){ if(x==null||isNaN(x)) return "&mdash;";
      var n=Number(x); d=(d==null)?4:d;
      if(Math.abs(n)>=1e6) return n.toExponential(3);
      return n.toLocaleString(undefined,{minimumFractionDigits:0,maximumFractionDigits:d}); }
    function pct(x,d){ if(x==null||isNaN(x)) return "&mdash;"; d=(d==null)?3:d;
      return (Number(x)*100).toFixed(d)+"%"; }
    function chip(ok,t,f){ return ok?('<span class="chip pass">'+esc(t||"yes")+'</span>')
      :('<span class="chip warn">'+esc(f||"no")+'</span>'); }
    function ratioRows(rr,order){ var h='';
      for(var i=0;i<order.length;i++){ var rk=order[i][0], r=rr[rk]; if(!r) continue;
        h+='<tr data-vr2-tech="'+esc(rk)+'"><td>'+esc(order[i][1])+'</td>'
          +'<td class="mono">'+num(r.ratio,(r.ratio>=100?1:3))+'&times;</td>'
          +'<td class="mono">['+num(r.ci95_lo,(r.ci95_lo>=100?1:3))+', '+num(r.ci95_hi,(r.ci95_hi>=100?1:3))+']</td>'
          +'<td>'+chip(r.useful_ge_threshold,"useful","sub-useful")+'</td></tr>'; }
      return h; }
    var html='<h2>'+esc(v.title||"Outer-Loop Variance Reduction")+'</h2>';
    html+='<p class="note">Candidate <span class="mono">'+esc(v.candidate_id||"")+'</span> &middot; classification '
      +'<span class="chip pass">'+esc(v.classification||"")+'</span> &middot; '+esc(v.note||"")+'</p>';

    // Governed-headline invariance card.
    var hi=v.headline_invariance||{}, hb=hi.before||{}, ha=hi.after||{};
    html+='<div class="cards" data-vr2="invariance"><div class="card"><div class="k">Governed headline invariance</div>'
      +'<div class="val">'+chip(hi.bit_identical,"BIT-IDENTICAL","moved")+'</div>'
      +'<div class="sub">frozen-t component SCR '+num(hb.frozen_t_component_scr,6)+' &rarr; '+num(ha.frozen_t_component_scr,6)
      +' &middot; max|dev| '+num(hi.max_abs_dev,9)+' (tol '+num(hi.tol,9)+')'
      +' &middot; '+chip(hi.additive_disclosed_not_a_swap,"additive / disclosed, not a swap","swap")+'</div></div></div>';

    // Control-variate fit card.
    var cv=v.control_variate_fit||{};
    html+='<div class="cards" data-vr2="cvfit"><div class="card"><div class="k">Control-variate fit (out-of-sample beta)</div>'
      +'<div class="val">&rho; = '+num(cv.rho,4)+'</div>'
      +'<div class="sub">beta '+num(cv.beta,4)+' &middot; theoretical mean-leg reduction 1/(1&minus;&rho;&sup2;) = '
      +num(cv.one_over_1_minus_rho2,3)+'&times; &middot; pilot n '+num(cv.pilot_n,0)+' (held-out)</div></div></div>';

    // 99.5% SCR tail variance-reduction ratios (the headline efficiency target).
    var ts=v.scr_tail_study||{}, tr=ts.variance_reduction_ratios||{};
    html+='<h3 style="margin:16px 0 6px">Work-normalised VR ratios on the 99.5% SCR tail target (95% CI)</h3>';
    html+='<table class="a11ytbl vr2ratios"><caption class="sr-only">MR-VR-2 work-normalised variance-reduction ratios on the 99.5% SCR tail target with 95% CIs and the &ge;1.5&times; useful bar</caption>'
      +'<thead><tr><th>Technique</th><th>VR ratio</th><th>95% CI</th><th>Useful (&ge;1.5&times;)</th></tr></thead><tbody>';
    html+=ratioRows(tr,[["sobol_rqmc","Sobol-RQMC"],["control_variate","Control variate (alone)"],
      ["stratified","Stratified"],["rqmc_plus_cv","RQMC + control variate"]]);
    html+='</tbody></table>';
    html+='<p class="note">Best technique on the SCR tail: <span class="chip pass">'+esc(v.best_tail_technique||"")+'</span>'
      +' &middot; analytic SCR proxy '+num(ts.analytic_scr,4)+' &middot; '+num(ts.n_replicates,0)+' replicates &times; '
      +num(ts.n_outer,0)+' outer paths.</p>';

    // Measured-not-assumed control-variate disclosure.
    html+='<h3 style="margin:16px 0 6px">Control variate at the 99.5% SCR quantile &mdash; INEFFECTIVE alone (disclosed)</h3>';
    var cvr=tr.control_variate||{};
    html+='<div class="cards" data-vr2="tail"><div class="card"><div class="k">Control-variate-alone 99.5% SCR work-normalised ratio</div>'
      +'<div class="val">'+num(cvr.ratio,3)+'&times; '+chip(!!cvr.useful_ge_threshold,"useful","sub-useful (ineffective)")+'</div>'
      +'<div class="sub">95% CI ['+num(cvr.ci95_lo,3)+', '+num(cvr.ci95_hi,3)+'] &middot; below the 1.5&times; bar &middot; '
      +'control rho '+num(v.control_rho,4)+', 1/(1&minus;rho&sup2;) '+num(v.control_one_over_1_minus_rho2,3)+'&times; acts on the mean leg only</div></div></div>';
    html+='<p class="note">'+esc(ts.disclosure||"")+'</p>';

    // OUTER mean-loss variance-reduction ratios.
    var mr=v.mean_variance_reduction_ratios||{};
    html+='<h3 style="margin:16px 0 6px">Work-normalised VR ratios on the OUTER mean-loss target (95% CI)</h3>';
    html+='<table class="a11ytbl vr2mean"><caption class="sr-only">MR-VR-2 work-normalised variance-reduction ratios on the outer mean-loss target with 95% CIs</caption>'
      +'<thead><tr><th>Technique</th><th>VR ratio</th><th>95% CI</th><th>Useful (&ge;1.5&times;)</th></tr></thead><tbody>';
    html+=ratioRows(mr,[["sobol_rqmc","Sobol-RQMC"],["control_variate","Control variate"],["stratified","Stratified"]]);
    html+='</tbody></table>';

    // Effective sample size (SCR tail) + n* (mean target).
    var ess=ts.effective_sample_size||{}, ns=v.n_star_for_target_se||{};
    html+='<h3 style="margin:16px 0 6px">Effective sample size (99.5% SCR) &amp; outer-path n* for target SE_rel = '
      +pct(v.target_se_rel,2)+' (mean)</h3>';
    html+='<table class="a11ytbl vr2ess"><caption class="sr-only">Effective sample size per technique on the SCR tail target and the outer-path count n* needed to reach the target relative SE on the mean target</caption>'
      +'<thead><tr><th>Technique</th><th>SCR effective sample size</th><th>n* for target SE (mean)</th></tr></thead><tbody>';
    var eorder=[["crude","Crude i.i.d."],["sobol_rqmc","Sobol-RQMC"],["control_variate","Control variate"],
      ["stratified","Stratified"],["rqmc_plus_cv","RQMC + CV"]];
    for(var j=0;j<eorder.length;j++){ var ek=eorder[j][0];
      html+='<tr data-vr2-ess="'+esc(ek)+'"><td>'+esc(eorder[j][1])+'</td>'
        +'<td class="mono">'+(ess[ek]!=null?num(ess[ek],0):'<span class="muted">&mdash;</span>')+'</td>'
        +'<td class="mono">'+(ns[ek]!=null?num(ns[ek],(ns[ek]<100?2:0)):'<span class="muted">&mdash;</span>')+'</td></tr>';
    }
    html+='</tbody></table>';

    // Unbiasedness (mean + SCR).
    var ub=v.mean_unbiasedness||{}, us=ts.unbiasedness_scr||{};
    html+='<h3 style="margin:16px 0 6px">Unbiasedness vs the analytic / crude reference</h3>';
    html+='<p class="note">Mean target: analytic '+num(ub.analytic_mean,6)+' &middot; all estimators within tol '+pct(ub.tol_rel,2)
      +': '+chip(ub.all_within_tol,"yes","NO")+'. SCR target: analytic '+num(us.analytic_scr,6)+' &middot; crude '+num(us.crude_scr_mean,6)
      +' (rel '+pct(us.crude_rel_vs_analytic,4)+'), tol '+pct(us.tol_rel,2)+'.</p>';

    // Adoption materiality verdict.
    var am=v.adoption_materiality||{};
    html+='<h3 style="margin:16px 0 6px">Adoption materiality &mdash; REPORTED, NOT applied</h3>';
    html+='<div class="cards" data-vr2="adoption"><div class="card"><div class="k">Indicated dSCR (variance-reduced vs crude outer MC)</div>'
      +'<div class="val">'+pct(am.indicated_rel_dscr,4)+' '+chip(!am.is_material,"immaterial","MATERIAL")+'</div>'
      +'<div class="sub">threshold '+pct(am.materiality_threshold_rel,2)+' &middot; applied: '+chip(!am.applied,"NO (frozen)","yes")
      +' &middot; '+esc(am.disposition||"")+'</div></div></div>';

    html+='<p class="note">'+esc(v.mean_interpretation||"")+'</p>';
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

    # 2. TABS: add the Outer-Loop VR tab after the MR-VR-1 tab.
    tabs_anchor = '["vrpanel","Variance Reduction (MR-VR-1)"]\n  ];'
    assert html.count(tabs_anchor) == 1, "TABS vrpanel anchor not unique/found"
    html = html.replace(
        tabs_anchor,
        '["vrpanel","Variance Reduction (MR-VR-1)"],\n'
        '    ["vr2panel","Outer-Loop Variance Reduction (MR-VR-2)"]\n  ];',
    )

    # 3. add the panel container div after the MR-VR-1 panel.
    panel_anchor = ('<div id="vrpanel" class="panel" '
                    'data-title="Variance Reduction (MR-VR-1)"></div>')
    assert html.count(panel_anchor) == 1, "vrpanel panel anchor not unique/found"
    html = html.replace(
        panel_anchor,
        panel_anchor +
        '\n  <div id="vr2panel" class="panel" '
        'data-title="Outer-Loop Variance Reduction (MR-VR-2)"></div>',
    )

    # 4. inject renderVr2Panel() just before renderAll().
    renderall_anchor = "\n  function renderAll(){\n    renderHeader();"
    assert html.count(renderall_anchor) == 1, "renderAll anchor not unique/found"
    html = html.replace(renderall_anchor, "\n" + VR2_RENDER_JS + renderall_anchor)

    # 5. call renderVr2Panel() inside renderAll (after renderVrPanel()).
    call_anchor = "renderGlossary(); renderVrPanel(); renderIntegrityBanner();"
    assert html.count(call_anchor) == 1, "renderAll call anchor not unique/found"
    html = html.replace(
        call_anchor,
        "renderGlossary(); renderVrPanel(); renderVr2Panel(); renderIntegrityBanner();")
    return html


def main(check_only: bool = False) -> int:
    with open(UI_DATA, encoding="utf-8") as fh:
        data = json.load(fh, object_pairs_hook=collections.OrderedDict)

    assert data.get("contract_version") == PRIOR_CONTRACT, (
        "unexpected prior contract %r (expected %r)"
        % (data.get("contract_version"), PRIOR_CONTRACT))
    assert VR2_KEY not in data, "postigui_vr2 key already present"
    man = data.get("contract_manifest")
    assert isinstance(man, dict), "contract_manifest missing"
    assert "section_digests" in man, "expected A2 section_digests present"
    assert "postigui_vr" in data, "expected MR-VR-1 postigui_vr present (1.22.0)"

    vr2 = build_vr2_section()

    # Integrity self-asserts: figures carried bit-for-bit from the source report.
    with open(VR_REPORT, encoding="utf-8") as fh:
        src = json.load(fh)
    assert vr2["headline_invariance"] == src["governed_headline_invariance"]
    assert vr2["control_variate_fit"] == src["control_variate_fit"]
    assert vr2["mean_variance_reduction_ratios"] == src["replicate_study"]["variance_reduction_ratios"]
    assert vr2["mean_effective_sample_size"] == src["replicate_study"]["effective_sample_size"]
    assert vr2["n_star_for_target_se"] == src["replicate_study"]["n_star_for_target_se"]
    assert vr2["mean_unbiasedness"] == src["replicate_study"]["unbiasedness"]
    assert vr2["scr_tail_study"] == src["scr_tail_study"]
    assert vr2["adoption_materiality"] == src["adoption_materiality"]
    assert vr2["digest"] == src["digest"]
    # Governed headline carried exactly; not relabelled.
    assert vr2["headline_invariance"]["before"]["frozen_t_component_scr"] == GOVERNED_HEADLINE
    assert vr2["headline_invariance"]["after"]["frozen_t_component_scr"] == GOVERNED_HEADLINE
    assert vr2["headline_invariance"]["bit_identical"] is True
    # Control-variate-alone INEFFECTIVE on the 99.5% SCR tail (the required disclosure).
    cvr = vr2["scr_tail_study"]["variance_reduction_ratios"]["control_variate"]
    assert cvr["useful_ge_threshold"] is False
    assert cvr["ratio"] < 1.5
    # RQMC / stratification ARE useful on the tail; stratified is best.
    assert vr2["scr_tail_study"]["variance_reduction_ratios"]["sobol_rqmc"]["useful_ge_threshold"] is True
    assert vr2["scr_tail_study"]["variance_reduction_ratios"]["stratified"]["useful_ge_threshold"] is True
    assert vr2["scr_tail_study"]["variance_reduction_ratios"]["rqmc_plus_cv"]["useful_ge_threshold"] is True
    assert vr2["best_tail_technique"] == "stratified"
    # Adoption immaterial, reported not applied.
    assert vr2["adoption_materiality"]["is_material"] is False
    assert vr2["adoption_materiality"]["applied"] is False
    # Gate: 20 checks, all pass.
    assert vr2["validation_gate"]["ok"] is True
    assert vr2["validation_gate"]["n_checks"] == 20

    # --- build the new payload (postigui_vr2 inserted before contract_manifest) ---
    new_data = collections.OrderedDict()
    for k, val in data.items():
        if k == "contract_manifest":
            new_data[VR2_KEY] = vr2
        new_data[k] = val
    if VR2_KEY not in new_data:  # manifest somehow last/missing
        new_data[VR2_KEY] = vr2

    new_data["contract_version"] = NEW_CONTRACT
    nman = new_data["contract_manifest"]
    nman["expected_contract_version"] = NEW_CONTRACT
    req = list(nman["required_top_level_keys"])
    if VR2_KEY not in req:
        req.append(VR2_KEY)
    nman["required_top_level_keys"] = req
    nman["key_count"] = len(req)
    base_note = nman.get("note", "")
    add_note = (" MR-VR-2 outer-loop variance-reduction efficiency panel "
                "(postigui_vr2) added additively in 1.23.0 (Post-Phase-IGUI "
                "Task 8): display-only, no model figure recomputed, figures "
                "carried bit-for-bit from the governed Task-7 report.")
    if "1.23.0" not in base_note:
        nman["note"] = (base_note + add_note).strip()

    # recompute per-section digests over the NEW payload using the EXACT embedded
    # JS, then write them into the manifest.
    res = a2.compute_digests_via_node(new_data)
    section_digests = res["section_digests"]
    root_digest = res["root_digest"]
    expected_top = sorted(k for k in new_data.keys() if k != "contract_manifest")
    assert res["keys"] == expected_top, "digest key set mismatch"
    assert VR2_KEY in section_digests, "postigui_vr2 not digested"
    nman["section_digests"] = section_digests
    nman["root_digest"] = root_digest
    nman["digest_generated_by"] = (
        man.get("digest_generated_by", a2.GENERATOR) + " + " + GENERATOR)

    new_json = json.dumps(new_data, default=str)
    json.loads(new_json)  # re-parse guard

    if check_only:
        print(json.dumps({
            "mode": "check", "contract": "%s -> %s" % (PRIOR_CONTRACT, NEW_CONTRACT),
            "vr2_techniques": len(vr2["techniques"]),
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
    assert VR2_KEY in chk
    assert "postigui_vr" in chk  # MR-VR-1 still present (additive)
    cman = chk["contract_manifest"]
    assert cman["root_digest"] == root_digest
    assert cman["key_count"] == len(expected_top)
    assert VR2_KEY in cman["required_top_level_keys"]

    h2 = open(UI_APP, encoding="utf-8").read()
    a = h2.find("/*__UI_DATA__*/") + len("/*__UI_DATA__*/")
    b = h2.find("</script>", a)
    emb = json.loads(h2[a:b])
    assert emb["contract_version"] == NEW_CONTRACT
    assert VR2_KEY in emb
    assert 'id="vr2panel"' in h2 and "function renderVr2Panel(" in h2
    assert '["vr2panel","Outer-Loop Variance Reduction (MR-VR-2)"]' in h2

    # confirm embedded payload recomputes to the SAME digests via Node.
    recheck = a2.compute_digests_via_node(emb)
    assert recheck["root_digest"] == root_digest, "embedded recompute root mismatch"
    assert recheck["section_digests"] == section_digests, "embedded recompute mismatch"

    print(json.dumps({
        "verdict": "PASS",
        "contract": "%s -> %s" % (PRIOR_CONTRACT, NEW_CONTRACT),
        "vr2_techniques": len(vr2["techniques"]),
        "sections_digested": len(section_digests),
        "root_digest": root_digest,
        "embedded_recompute_matches": True,
        "ui_data_bytes": len(new_json.encode("utf-8")),
        "ui_app_bytes": len(h2.encode("utf-8")),
    }, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(check_only="--check" in sys.argv))
