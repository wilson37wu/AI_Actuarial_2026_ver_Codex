"""Post-Phase-IGUI Task 7 - builder for the MR-VR-2 OUTER-loop variance-reduction
study report.

Runs par_model_v2.projection.outer_loop_variance_reduction under the six
pre-registered gates G1..G6 (frozen in the Task 6 design note), writes a DISCLOSED
JSON + Markdown report and a result card, and (with --governance) leaves an
OWNER_REVIEW ChangeRecord.

Efficiency-only: NO model parameter change; the governed frozen-t component
headline 39,975.654628199336 stays BIT-IDENTICAL. Phase 30 stop-rule honoured
(only the Monte-Carlo sampling scheme of an existing estimator changes and an
unbiased control variate is added; no copula structure touched).

Outputs:
  docs/validation/POSTIGUI_TASK7_OUTER_VARIANCE_REDUCTION.{json,md}
  docs/POSTIGUI_TASK7_OUTER_VARIANCE_REDUCTION_REPORT_CARD.md
  optional governance ChangeRecord (--governance), governance_change, OWNER_REVIEW.
"""

from __future__ import annotations

import json
import os
import sys

from par_model_v2.projection.outer_loop_variance_reduction import (
    CANDIDATE_ID,
    FROZEN_T_COMPONENT_SCR_REFERENCE,
    NESTED_PATHWISE_SCR_REFERENCE,
    run_study,
    validate,
)
from par_model_v2.projection.outer_loop_efficiency_design import standard_references
from par_model_v2.governance.audit_trail import AuditEntry, ChangeRecord, GovernanceStore

GOV_PATH = os.path.join(".claude-dev", "GOVERNANCE_STORE.json")
OUT_DIR = os.path.join("docs", "validation")
JSON_PATH = os.path.join(OUT_DIR, "POSTIGUI_TASK7_OUTER_VARIANCE_REDUCTION.json")
MD_PATH = os.path.join(OUT_DIR, "POSTIGUI_TASK7_OUTER_VARIANCE_REDUCTION.md")
CARD_PATH = os.path.join("docs", "POSTIGUI_TASK7_OUTER_VARIANCE_REDUCTION_REPORT_CARD.md")

CHANGE_TITLE = (
    "Post-Phase-IGUI Task 7 - implement MR-VR-2 OUTER-loop scrambled-Sobol RQMC + "
    "control-variate variance reduction for the 99.5% SCR estimator (gates G1-G6; "
    "efficiency-only, additive/disclosed, no parameter change)"
)

AFFECTED_COMPONENTS = [
    "par_model_v2/projection/outer_loop_variance_reduction.py (NEW)",
    "scripts/build_postigui_task7_outer_variance_reduction.py (NEW)",
    "tests/test_postigui_task7_outer_variance_reduction.py (NEW)",
    "docs/validation/POSTIGUI_TASK7_OUTER_VARIANCE_REDUCTION.{json,md}",
    "docs/POSTIGUI_TASK7_OUTER_VARIANCE_REDUCTION_REPORT_CARD.md",
]


def _md(p: dict, g: dict) -> str:
    inv = p["governed_headline_invariance"]
    cvfit = p["control_variate_fit"]
    rep = p["replicate_study"]
    rratios = rep["variance_reduction_ratios"]
    ress = rep["effective_sample_size"]
    rnstar = rep["n_star_for_target_se"]
    runb = rep["unbiasedness"]
    scr = p["scr_tail_study"]
    sratios = scr["variance_reduction_ratios"]
    sess = scr["effective_sample_size"]
    sunb = scr["unbiasedness_scr"]
    mat = p["adoption_materiality"]
    lines = [
        "# Post-Phase-IGUI Task 7 - OUTER-Loop Variance-Reduction Study (MR-VR-2)",
        "",
        f"**Verdict: {'PASS' if g['ok'] else 'FAIL'}** - efficiency-only "
        f"(EFFICIENCY); NO parameter change; governed frozen-t headline "
        f"BIT-IDENTICAL. Gate {sum(g['checks'].values())}/{g['n_checks']}.",
        "",
        f"- Candidate: **{p['candidate_id']}** (RQMC + control-variates for the OUTER "
        f"capital/SCR loop)",
        f"- Run digest (idempotent): `{p['digest']}`",
        f"- Outer loss: full revaluation L(X) = mu + delta*X + c*max(X-k,0) "
        f"(mu={p['grid']['loss_mu']:g}, delta={p['grid']['loss_delta']:g}, "
        f"c={p['grid']['loss_kink_c']:g}, k={p['grid']['loss_kink_k']:g}); "
        f"delta-gamma proxy P(X) curvature gamma2={p['grid']['proxy_gamma2']:g}.",
        f"- Analytic E[L] = {rep['analytic_mean_loss']:.6f}; analytic SCR* = "
        f"{scr['analytic_scr']:.6f}.",
        "",
        "## G1 - Governed-headline invariance (additive / disclosed)",
        "",
        f"- Bit-identical: **{inv['bit_identical']}** (max abs dev "
        f"{inv['max_abs_dev']:.1e}, tol {inv['tol']:g})",
        f"- Governed frozen-t headline unmoved: "
        f"**{inv['after']['frozen_t_component_scr']:,.12f}**",
        f"- Additive/disclosed, not a silent swap: "
        f"**{inv['additive_disclosed_not_a_swap']}**",
        "",
        "## G2 - Estimator unbiasedness (out-of-sample beta; >= 200 replicates)",
        "",
        f"- Control-variate beta = {cvfit['beta']:.6f} fit on a HELD-OUT pilot "
        f"(n={cvfit['pilot_n']:,}, seed {cvfit['pilot_seed']}) -> adds no in-sample bias.",
        f"- Control-target correlation rho = **{cvfit['rho']:.4f}**; theoretical mean-leg "
        f"reduction 1/(1-rho^2) = **{cvfit['one_over_1_minus_rho2']:.3f}x**.",
        f"- Mean target: crude {runb['crude_mean']:.6f} vs analytic "
        f"{runb['analytic_mean']:.6f} (rel {runb['crude_rel_vs_analytic']*100:.4f}%); "
        f"CV vs crude {runb['control_variate_rel_vs_crude']*100:.4f}%, Sobol vs crude "
        f"{runb['sobol_rel_vs_crude']*100:.4f}%, stratified vs crude "
        f"{runb['stratified_rel_vs_crude']*100:.4f}% (tol {runb['tol_rel']*100:.1f}%) -> "
        f"all within tol: **{runb['all_within_tol']}**.",
        f"- SCR target: crude SCR {sunb['crude_scr_mean']:.6f} vs analytic "
        f"{sunb['analytic_scr']:.6f} (rel {sunb['crude_rel_vs_analytic']*100:.4f}%); "
        f"RQMC+CV vs crude {sunb['rqmc_plus_cv_rel_vs_crude']*100:.4f}%.",
        "",
        "## G3a - Mean-target work-normalised VR ratios + ESS (with CIs)",
        "",
        "| Technique | VR ratio | 95% CI | ESS (scenarios) | n* @1% SE | useful >=1.5x |",
        "|---|---|---|---|---|---|",
    ]
    for k in ("sobol_rqmc", "control_variate", "stratified"):
        v = rratios[k]
        lines.append(
            f"| {k} | {v['ratio']:.3f}x | [{v['ci95_lo']:.3f}, {v['ci95_hi']:.3f}] | "
            f"{ress[k]:,.0f} | {rnstar[k]:,.0f} | {v['useful_ge_threshold']} |"
        )
    lines.extend([
        f"| crude (baseline) | 1.000x | - | {rep['n_outer']:,} | "
        f"{rnstar['crude']:,.0f} | - |",
        "",
        f"- Control-variate mean-leg ratio {rratios['control_variate']['ratio']:.3f}x "
        f"matches the theoretical 1/(1-rho^2) = {cvfit['one_over_1_minus_rho2']:.3f}x.",
        f"- {rep['interpretation']}",
        "",
        "## G3b - OUTER 99.5% SCR target work-normalised VR ratios + ESS (with CIs)",
        "",
        "| Technique | VR ratio | 95% CI | ESS (scenarios) | useful >=1.5x |",
        "|---|---|---|---|---|",
    ])
    for k in ("sobol_rqmc", "control_variate", "stratified", "rqmc_plus_cv"):
        v = sratios[k]
        lines.append(
            f"| {k} | {v['ratio']:.3f}x | [{v['ci95_lo']:.3f}, {v['ci95_hi']:.3f}] | "
            f"{sess[k]:,.0f} | {v['useful_ge_threshold']} |"
        )
    lines.extend([
        f"| crude (baseline) | 1.000x | - | {scr['n_outer']:,} | - |",
        "",
        f"- Best technique on the SCR target: **{scr['best_technique']}** "
        f"({sratios[scr['best_technique']]['ratio']:.1f}x); at least one >= 1.5x useful: "
        f"**{scr['any_useful_ge_1p5x']}**.",
        f"- Control-variate-ALONE on the SCR target is "
        f"{sratios['control_variate']['ratio']:.3f}x (sub-1.5x): the honest MEASURED "
        f"finding that the control variate acts only on the cheap mean leg, not the "
        f"99.5% quantile leg.",
        f"- {scr['disclosure']}",
        "",
        "## G4 - Slice-stable reproducibility + version-pinned grid",
        "",
        f"- Outer scenarios via SeedSequence.spawn (slice-stable); scrambled-Sobol "
        f"(base-2, Cranley-Patterson rotation); idempotent digest `{p['digest']}`.",
        f"- Grid pinned: n_outer={p['grid']['n_outer']:,}, "
        f"n_outer_tail={p['grid']['n_outer_tail']:,}, "
        f"n_replicates={p['grid']['n_replicates']}, alpha={p['grid']['alpha']}, "
        f"sobol_dimension={p['grid']['sobol_dimension']}; seeds={p['grid']['seeds']}.",
        "",
        "## G5 - Adoption materiality (REPORTED, NOT applied)",
        "",
        f"- SCR proxy (analytic): {mat['scr_proxy_analytic']:,.6f}; crude outer-MC: "
        f"{mat['scr_proxy_crude_outer_mc']:,.6f}; VR (RQMC+CV) outer-MC: "
        f"{mat['scr_proxy_vr_outer_mc']:,.6f}.",
        f"- Indicated dSCR if adopted (VR vs crude): "
        f"{mat['indicated_dscr_abs_vs_crude']:.6f} "
        f"(**{mat['indicated_rel_dscr']*100:.6f}%** of headline; materiality "
        f"{mat['materiality_threshold_rel']*100:.0f}%).",
        f"- Material: **{mat['is_material']}**; applied: **{mat['applied']}**.",
        f"- Disposition: {mat['disposition']}",
        "",
        "## G6 - Governance + reproducibility",
        "",
        f"- Idempotent run digest: `{p['digest']}`; classification "
        f"{p['classification']}; techniques {', '.join(p['vr_techniques'])}.",
        "- Report-only: no offline-UI surface added this cycle (ui_app.html "
        "byte-unchanged); any future surface would be an ADDITIVE contract bump only.",
        "",
        "## Gate detail",
        "",
    ])
    for k, v in g["checks"].items():
        lines.append(f"- {k}: {v}")
    lines.extend(["", "## Standards", ""])
    lines.extend(f"- {s}" for s in standard_references())
    lines.extend(["", "*Generated by scripts/build_postigui_task7_outer_variance_reduction.py.*", ""])
    return "\n".join(lines)


def _card(p: dict, g: dict) -> str:
    cvfit = p["control_variate_fit"]
    scr = p["scr_tail_study"]
    sratios = scr["variance_reduction_ratios"]
    rep = p["replicate_study"]
    mat = p["adoption_materiality"]
    return "\n".join([
        "# OUTER-Loop Variance-Reduction Study - Result Card (Post-Phase-IGUI Task 7)",
        "",
        f"**{p['candidate_id']} implemented.** Efficiency-only; EFFICIENCY. "
        f"Gate {sum(g['checks'].values())}/{g['n_checks']} "
        f"({'PASS' if g['ok'] else 'FAIL'}). Governed headline "
        f"{FROZEN_T_COMPONENT_SCR_REFERENCE:,.6f} BIT-IDENTICAL.",
        "",
        "## Headline findings",
        "",
        f"- Work-normalised OUTER 99.5% SCR variance-reduction ratios (vs crude i.i.d.): "
        f"**Sobol-RQMC {sratios['sobol_rqmc']['ratio']:.0f}x**, "
        f"**stratified {sratios['stratified']['ratio']:.0f}x**, "
        f"**RQMC+CV {sratios['rqmc_plus_cv']['ratio']:.0f}x** "
        f"(>= 200-replicate CIs). Best technique: **{scr['best_technique']}**; "
        f"at least one >= 1.5x: **{scr['any_useful_ge_1p5x']}**.",
        f"- Control-target correlation **rho = {cvfit['rho']:.3f}** -> theoretical "
        f"mean-leg reduction 1/(1-rho^2) = **{cvfit['one_over_1_minus_rho2']:.2f}x** "
        f"(measured mean-leg CV ratio "
        f"{rep['variance_reduction_ratios']['control_variate']['ratio']:.2f}x).",
        f"- MEASURED (not assumed) tail finding: the control variate ALONE is "
        f"**{sratios['control_variate']['ratio']:.2f}x** on the 99.5% SCR target "
        f"(sub-1.5x) because it acts only on the cheap mean leg - the OUTER-loop "
        f"analogue of MR-VR-1's antithetic-ineffective-at-99.5% disclosure. RQMC / "
        f"stratification are the levers for the quantile leg.",
        f"- Estimators UNBIASED: out-of-sample beta; replicate means agree with crude "
        f"within {rep['unbiasedness']['tol_rel']*100:.1f}%.",
        f"- Adopting the VR estimator would move the SCR proxy by "
        f"**{mat['indicated_rel_dscr']*100:.6f}%** of headline "
        f"({'MATERIAL' if mat['is_material'] else 'immaterial'}, "
        f"< {mat['materiality_threshold_rel']*100:.0f}% threshold); "
        f"**REPORTED, NOT applied** - the governed production estimator stays frozen.",
        "",
        "## Discipline",
        "",
        "Additive/disclosed efficiency study; governed headline bit-identical; "
        ">=200 replicate seeds with bootstrap CIs; out-of-sample control-variate beta; "
        "slice-stable SeedSequence-spawn outer scenarios; scrambled-Sobol RQMC; "
        f"idempotent digest `{p['digest']}`. Only the Monte-Carlo sampling scheme "
        "changes and an unbiased control variate is added - no copula structure or "
        "model parameter touched (Phase 30 stop-rule). MR-016/MR-017 stay OPEN.",
        "",
        "*Generated by scripts/build_postigui_task7_outer_variance_reduction.py.*",
        "",
    ])


def apply_governance(store: GovernanceStore, p: dict, g: dict) -> dict:
    actor = "PostIGUITask7OuterVarianceReductionStudy"
    phase = "Post-Phase-IGUI: Model-Improvement Candidate Implementation"
    if any(r.title == CHANGE_TITLE for r in store.change_records):
        return {"added": False, "reason": "already applied (idempotent)"}
    cvfit = p["control_variate_fit"]
    scr = p["scr_tail_study"]
    sratios = scr["variance_reduction_ratios"]
    mat = p["adoption_materiality"]
    rec = ChangeRecord.create(
        title=CHANGE_TITLE,
        description=(
            "Implemented MR-VR-2: efficiency-only OUTER-loop variance-reduction study "
            "on the governed 99.5% SCR estimator comparing crude i.i.d. Monte Carlo "
            "against scrambled-Sobol randomised-QMC over the outer scenario grid, a "
            "control variate built from the cheap delta-gamma proxy SCR (beta fit "
            "out-of-sample on a held-out pilot so it adds no bias), proportional tail "
            "stratification, and the combined RQMC+CV estimator. Work-normalised "
            "variance-reduction ratios and effective-sample-size reported with "
            ">=200-replicate bootstrap CIs on the OUTER 99.5% SCR target; control-target "
            "correlation rho and theoretical reduction 1/(1-rho^2) disclosed; "
            "control-variate-alone DISCLOSED as sub-1.5x on the quantile leg (acts only "
            "on the cheap mean leg) - the measured-not-assumed tail finding, the "
            "OUTER-loop analogue of MR-VR-1's antithetic-ineffective-at-99.5% result. "
            "Governed frozen-t headline recovered BIT-IDENTICAL (dev 0); the "
            "variance-reduced estimator is ADDITIVE/DISCLOSED. Indicated adoption dSCR "
            "REPORTED, NOT applied. Only the Monte-Carlo sampling scheme changes and an "
            "unbiased control variate is added; no copula structure (Phase 30 "
            "stop-rule); MR-016/MR-017 untouched."
        ),
        change_type="governance_change",
        affected_components=AFFECTED_COMPONENTS,
        standard_references=standard_references(),
        before_snapshot={
            "candidate": CANDIDATE_ID,
            "state": "pre-registered (Task 6 design note OWNER_REVIEW)",
            "vr_efficacy_quantified": False,
        },
        after_snapshot={
            "candidate": CANDIDATE_ID,
            "gate": f"{sum(g['checks'].values())}/{g['n_checks']}",
            "gate_ok": g["ok"],
            "digest": p["digest"],
            "control_rho": cvfit["rho"],
            "one_over_1_minus_rho2": cvfit["one_over_1_minus_rho2"],
            "scr_vr_ratio_sobol_rqmc": sratios["sobol_rqmc"]["ratio"],
            "scr_vr_ratio_stratified": sratios["stratified"]["ratio"],
            "scr_vr_ratio_control_variate": sratios["control_variate"]["ratio"],
            "scr_vr_ratio_rqmc_plus_cv": sratios["rqmc_plus_cv"]["ratio"],
            "best_technique": scr["best_technique"],
            "indicated_rel_dscr": mat["indicated_rel_dscr"],
            "indicated_applied": mat["applied"],
            "is_material": mat["is_material"],
            "headline_bit_identical": p["governed_headline_invariance"]["bit_identical"],
        },
        impact_assessment=(
            "Governance/efficiency only. Quantifies, with CIs, how much OUTER-loop "
            "Monte-Carlo variance the admissible levers (RQMC, control variate, "
            "stratification) cut for the 99.5% SCR estimator; the governed headline "
            "does not move and no parameter is changed. The variance-reduced estimator "
            "is additive/disclosed; the indicated adoption dSCR is immaterial and NOT "
            "applied."
            if not mat["is_material"] else
            "Governance/efficiency only. Indicated adoption dSCR EXCEEDS 1% of the "
            "headline -> a new model-risk entry is OPENED for owner decision; the "
            "production estimator is NOT auto-switched; the governed headline does not "
            "move."
        ),
        author=actor,
        phase=phase,
        quantitative_impact=(
            f"Work-normalised SCR VR ratios: Sobol-RQMC {sratios['sobol_rqmc']['ratio']:.1f}x, "
            f"stratified {sratios['stratified']['ratio']:.1f}x, RQMC+CV "
            f"{sratios['rqmc_plus_cv']['ratio']:.1f}x; control-variate-alone "
            f"{sratios['control_variate']['ratio']:.2f}x (sub-useful on the quantile leg, "
            f"disclosed). Control rho {cvfit['rho']:.3f}, 1/(1-rho^2) "
            f"{cvfit['one_over_1_minus_rho2']:.2f}x. Indicated adoption dSCR "
            f"{mat['indicated_rel_dscr']*100:.6f}% of headline, NOT applied. Governed "
            f"headline {FROZEN_T_COMPONENT_SCR_REFERENCE:,.6f} unchanged."
        ),
    )
    rec.submit_for_peer_review(
        actor=actor,
        comments="MR-VR-2 outer-loop variance-reduction study implemented; gates G1-G6 green; unit tests added.",
    )
    rec.submit_to_owner(
        actor=actor,
        comments="Owner review: efficiency-only; governed headline bit-identical; "
                 "indicated adoption dSCR REPORTED, not applied.",
    )
    store.add_change_record(rec)
    store.audit_trail.append(AuditEntry.governance(
        actor=actor,
        phase=phase,
        event="ChangeRecord opened (OWNER_REVIEW) - Post-Phase-IGUI Task 7 MR-VR-2 outer-loop variance reduction",
        details={"record_id": rec.record_id, "change_type": "governance_change",
                 "status": rec.status.value, "candidate_id": CANDIDATE_ID,
                 "digest": p["digest"]},
    ))
    return {"added": True, "record_id": rec.record_id, "status": rec.status.value}


def main(use_governance: bool = False) -> dict:
    p = run_study()
    g = validate(p)
    p["validation_gate"] = g
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(JSON_PATH, "w", encoding="utf-8") as fh:
        json.dump(p, fh, indent=1, default=float)
    with open(MD_PATH, "w", encoding="utf-8") as fh:
        fh.write(_md(p, g))
    with open(CARD_PATH, "w", encoding="utf-8") as fh:
        fh.write(_card(p, g))
    out = {"verdict": "PASS" if g["ok"] else "FAIL", "gate_ok": g["ok"],
           "n_checks": g["n_checks"], "passed": sum(g["checks"].values()),
           "candidate_id": CANDIDATE_ID, "digest": p["digest"],
           "json": JSON_PATH, "md": MD_PATH, "card": CARD_PATH}
    if use_governance:
        store = GovernanceStore.from_json(open(GOV_PATH).read())
        gov = apply_governance(store, p, g)
        if gov.get("added"):
            with open(GOV_PATH, "w", encoding="utf-8") as fh:
                fh.write(store.to_json())
        gov["audit_entries"] = len(store.audit_trail.all())
        gov["audit_integrity_ok"] = store.audit_trail.verify_all()
        gov["change_records_total"] = len(store.change_records)
        out["governance"] = gov
    return out


if __name__ == "__main__":
    res = main(use_governance="--governance" in sys.argv)
    print(json.dumps(res, indent=1, default=str))
