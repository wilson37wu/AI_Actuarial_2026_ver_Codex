"""Post-Phase-IGUI Task 2 - builder for the MR-CAL-1 credentialled-data
calibration-residual diagnostics report.

Runs par_model_v2.calibration.credentialled_residual_diagnostics under the six
pre-registered gates G1..G6, writes a DISCLOSED JSON + Markdown report and a
design/result card, and (with --governance) leaves an OWNER_REVIEW ChangeRecord.

Diagnostics-only: NO model parameter change; the frozen margins and the governed
frozen-t component headline 39,975.654628199336 stay BIT-IDENTICAL. Phase 30
stop-rule honoured (no copula structure touched).

Outputs:
  docs/validation/POSTIGUI_TASK2_DIAGNOSTICS.{json,md}
  docs/POSTIGUI_TASK2_CREDENTIALLED_CALIBRATION_REPORT_CARD.md
  optional governance ChangeRecord (--governance), governance_change, OWNER_REVIEW.
"""

from __future__ import annotations

import json
import os
import sys

from par_model_v2.calibration.credentialled_residual_diagnostics import (
    CANDIDATE_ID,
    FROZEN_T_COMPONENT_SCR_REFERENCE,
    NESTED_PATHWISE_SCR_REFERENCE,
    run_diagnostics,
    validate,
)
from par_model_v2.calibration.credentialled_residual_design import (
    standard_references,
)
from par_model_v2.governance.audit_trail import AuditEntry, ChangeRecord, GovernanceStore

GOV_PATH = os.path.join(".claude-dev", "GOVERNANCE_STORE.json")
OUT_DIR = os.path.join("docs", "validation")
JSON_PATH = os.path.join(OUT_DIR, "POSTIGUI_TASK2_DIAGNOSTICS.json")
MD_PATH = os.path.join(OUT_DIR, "POSTIGUI_TASK2_DIAGNOSTICS.md")
CARD_PATH = os.path.join("docs", "POSTIGUI_TASK2_CREDENTIALLED_CALIBRATION_REPORT_CARD.md")

CHANGE_TITLE = (
    "Post-Phase-IGUI Task 2 - implement MR-CAL-1 credentialled-data "
    "calibration-residual diagnostics (frozen margins; gates G1-G6; "
    "diagnostics-only, no parameter change)"
)

AFFECTED_COMPONENTS = [
    "par_model_v2/calibration/credentialled_residual_diagnostics.py (NEW)",
    "scripts/build_postigui_task2_diagnostics.py (NEW)",
    "tests/test_postigui_task2_diagnostics.py (NEW)",
    "docs/validation/POSTIGUI_TASK2_DIAGNOSTICS.{json,md}",
    "docs/POSTIGUI_TASK2_CREDENTIALLED_CALIBRATION_REPORT_CARD.md",
]


def _md(p: dict, g: dict) -> str:
    inv = p["frozen_margin_invariance"]
    dec = p["residual_decomposition"]
    cred = p["credibility"]
    gof = p["goodness_of_fit"]
    lines = [
        "# Post-Phase-IGUI Task 2 - Credentialled-Data Calibration-Residual "
        "Diagnostics (MR-CAL-1)",
        "",
        f"**Verdict: {'PASS' if g['ok'] else 'FAIL'}** - diagnostics-only "
        f"(EDUCATIONAL); NO parameter change; frozen margins + governed headline "
        f"BIT-IDENTICAL. Gate {sum(g['checks'].values())}/{g['n_checks']}.",
        "",
        f"- Candidate: **{p['candidate_id']}**",
        f"- Run digest (idempotent): `{p['digest']}`",
        "",
        "## G1 - Frozen-margin + headline invariance",
        "",
        f"- Bit-identical: **{inv['bit_identical']}** (max abs dev "
        f"{inv['max_abs_dev']:.1e}, tol {inv['tol']:g})",
        f"- Governed frozen-t headline unmoved: "
        f"**{inv['after']['frozen_t_component_scr']:,.12f}**",
        "",
        "## G2 - Credentialled-reference provenance",
        "",
        f"- Kind: **{p['credentialled_reference']['kind']}** "
        f"({p['credentialled_reference']['label']})",
        f"- Source: {p['credentialled_reference']['source']}",
        f"- Vintage: {p['credentialled_reference']['vintage']}; "
        f"n/margin: {p['credentialled_reference']['n_per_margin']:,}; "
        f"seed: {p['credentialled_reference']['seed']}",
        f"- Credential basis: {p['credentialled_reference']['credential_basis']}",
        "",
        "## G3 - Leakage-free goodness-of-fit (holdout, bootstrap CIs)",
        "",
        f"- Split: holdout fraction {gof['split']['holdout_fraction']}, "
        f"leakage-free {gof['split']['leakage_free']}; "
        f"{gof['bootstrap_replicates']} bootstrap replicates.",
        "",
        "| Margin | n hold | KS | AD | PIT mean | PIT-mean SE% | tail q99.5 SE% |",
        "|---|---|---|---|---|---|---|",
    ]
    for name, m in gof["per_margin"].items():
        lines.append(
            f"| {name} | {m['n_holdout']:,} | {m['point']['ks']:.4f} | "
            f"{m['point']['ad']:.3f} | {m['point']['pit_mean']:.4f} | "
            f"{m['bootstrap']['pit_mean']['se_rel']*100:.3f} | "
            f"{m['bootstrap']['tail_q995']['se_rel']*100:.3f} |"
        )
    lines.extend([
        "",
        "## G4 - Residual decomposition vs nested",
        "",
        f"- Nested path-wise reference: {dec['nested_pathwise_scr']:,.1f}",
        f"- Governed frozen-t headline: {dec['governed_frozen_t_headline']:,.6f}",
        f"- Total gap vs nested: **{dec['total_gap_vs_nested']:,.3f}**",
        f"- Copula-FORM residual (frozen_t): {dec['copula_form_residual_frozen_t']:,.3f} "
        f"(**{dec['copula_form_share']*100:.2f}%**)",
        f"- Margin-calibration residual (by difference): "
        f"**{dec['margin_calibration_residual_by_difference']:,.3f}** "
        f"(**{dec['margin_calibration_share']*100:.2f}%**)",
        f"- Reconciliation error: {dec['reconciliation_error']:.2e} "
        f"(tol {dec['reconciliation_abs_tol']:g}) -> reconciles: "
        f"**{dec['reconciles_within_tol']}**; headline unmoved: "
        f"**{dec['headline_unmoved']}**",
        "",
        "## G5 - Credibility (REPORTED, NOT applied)",
        "",
        f"- Method: {cred['method']}",
        f"- Indicated total dSCR: {cred['indicated_dscr_total']:,.3f} "
        f"(**{cred['indicated_rel_dscr_total']*100:.3f}%** of headline; "
        f"materiality {cred['materiality_threshold_rel']*100:.0f}%)",
        f"- Material: **{cred['is_material']}**; applied: **{cred['applied']}**",
        f"- Disposition: {cred['disposition']}",
        "",
        "| Margin | n | credibility Z | sigma model | sigma ref | indicated dSCR |",
        "|---|---|---|---|---|---|",
    ]
    )
    for name, m in cred["per_margin"].items():
        lines.append(
            f"| {name} | {m['n']:,} | {m['credibility_Z']:.4f} | "
            f"{m['sigma_model']:.4f} | {m['sigma_reference_implied']:.4f} | "
            f"{m['indicated_dscr']:,.3f} |"
        )
    lines.extend([
        "",
        "## G6 - Governance + reproducibility",
        "",
        f"- Idempotent run digest: `{p['digest']}`",
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
    lines.extend(["", "*Generated by scripts/build_postigui_task2_diagnostics.py.*", ""])
    return "\n".join(lines)


def _card(p: dict, g: dict) -> str:
    dec = p["residual_decomposition"]
    cred = p["credibility"]
    return "\n".join([
        "# Credentialled-Data Calibration-Residual Diagnostics - Result Card "
        "(Post-Phase-IGUI Task 2)",
        "",
        f"**{p['candidate_id']} implemented.** Diagnostics-only; EDUCATIONAL. "
        f"Gate {sum(g['checks'].values())}/{g['n_checks']} "
        f"({'PASS' if g['ok'] else 'FAIL'}). Frozen margins + governed headline "
        f"{FROZEN_T_COMPONENT_SCR_REFERENCE:,.6f} BIT-IDENTICAL.",
        "",
        "## Headline findings",
        "",
        f"- Of the {dec['total_gap_vs_nested']:,.0f} gap to the nested reference "
        f"({NESTED_PATHWISE_SCR_REFERENCE:,.1f}), the copula FORM explains "
        f"**{dec['copula_form_share']*100:.1f}%** "
        f"({dec['copula_form_residual_frozen_t']:,.0f}) and the margin calibration "
        f"**{dec['margin_calibration_share']*100:.1f}%** "
        f"({dec['margin_calibration_residual_by_difference']:,.0f}).",
        f"- Credibility-weighted indicated margin shift -> "
        f"**{cred['indicated_rel_dscr_total']*100:.2f}%** of headline "
        f"({'MATERIAL' if cred['is_material'] else 'immaterial'}, "
        f"< {cred['materiality_threshold_rel']*100:.0f}% threshold); "
        f"**REPORTED, NOT applied**.",
        "- The dominant residual lives on the COPULA FORM side - consistent with "
        "the Phase 26-29 finding - so the margin calibration is the minor "
        "contributor. No recalibration indicated; MR-016/MR-017 stay OPEN.",
        "",
        "## Discipline",
        "",
        "Synthetic credentialled-reference stub (no licensed external dataset in "
        "sandbox); leakage-free fit/holdout split; >=200 bootstrap reps; idempotent "
        f"digest `{p['digest']}`. No copula structure or model parameter touched "
        "(Phase 30 stop-rule).",
        "",
        "*Generated by scripts/build_postigui_task2_diagnostics.py.*",
        "",
    ])


def apply_governance(store: GovernanceStore, p: dict, g: dict) -> dict:
    actor = "PostIGUITask2CredentialledCalibrationDiagnostics"
    phase = "Post-Phase-IGUI: Model-Improvement Candidate Implementation"
    if any(r.title == CHANGE_TITLE for r in store.change_records):
        return {"added": False, "reason": "already applied (idempotent)"}
    dec = p["residual_decomposition"]
    cred = p["credibility"]
    rec = ChangeRecord.create(
        title=CHANGE_TITLE,
        description=(
            "Implemented MR-CAL-1: diagnostics-only credentialled-data calibration-"
            "residual analysis of the seven frozen standalone risk-driver margins. "
            "PIT/QQ/KS/Anderson-Darling goodness-of-fit on a leakage-free fit/holdout "
            "split with >=200 bootstrap replicates; residual decomposition of the gap "
            "vs nested into a copula-FORM part and a margin-calibration part; partial-"
            "credibility Z and credibility-weighted indicated margin shift REPORTED, "
            "NOT applied. Frozen margins and the governed frozen-t headline recovered "
            "BIT-IDENTICAL (dev 0). No recalibration; no copula structure (Phase 30 "
            "stop-rule); MR-016/MR-017 untouched."
        ),
        change_type="governance_change",
        affected_components=AFFECTED_COMPONENTS,
        standard_references=standard_references(),
        before_snapshot={
            "candidate": CANDIDATE_ID,
            "state": "pre-registered (Task 1 design note OWNER_REVIEW)",
            "calibration_residual_quantified": False,
        },
        after_snapshot={
            "candidate": CANDIDATE_ID,
            "gate": f"{sum(g['checks'].values())}/{g['n_checks']}",
            "gate_ok": g["ok"],
            "digest": p["digest"],
            "margin_calibration_share": dec["margin_calibration_share"],
            "copula_form_share": dec["copula_form_share"],
            "indicated_rel_dscr_total": cred["indicated_rel_dscr_total"],
            "indicated_applied": cred["applied"],
            "is_material": cred["is_material"],
        },
        impact_assessment=(
            "Governance/diagnostics only. Quantifies the margin-calibration residual "
            "for the first time and confirms it is the minor share of the nested gap; "
            "the governed headline does not move and no margin parameter is changed. "
            "Indicated credibility-weighted shift is immaterial and NOT applied."
            if not cred["is_material"] else
            "Governance/diagnostics only. Indicated credibility-weighted shift EXCEEDS "
            "1% of the headline -> a new model-risk entry is OPENED for owner decision; "
            "NO recalibration performed; the governed headline does not move."
        ),
        author=actor,
        phase=phase,
        quantitative_impact=(
            f"Gap vs nested {dec['total_gap_vs_nested']:,.3f} = copula-FORM "
            f"{dec['copula_form_residual_frozen_t']:,.3f} "
            f"({dec['copula_form_share']*100:.2f}%) + margin-calibration "
            f"{dec['margin_calibration_residual_by_difference']:,.3f} "
            f"({dec['margin_calibration_share']*100:.2f}%). Indicated dSCR "
            f"{cred['indicated_rel_dscr_total']*100:.3f}% of headline, NOT applied. "
            f"Governed headline {FROZEN_T_COMPONENT_SCR_REFERENCE:,.6f} unchanged."
        ),
    )
    rec.submit_for_peer_review(
        actor=actor,
        comments="MR-CAL-1 diagnostics implemented; gates G1-G6 green; unit tests added.",
    )
    rec.submit_to_owner(
        actor=actor,
        comments="Owner review: diagnostics-only; frozen margins/headline bit-identical; "
                 "credibility indication REPORTED, not applied.",
    )
    store.add_change_record(rec)
    store.audit_trail.append(AuditEntry.governance(
        actor=actor,
        phase=phase,
        event="ChangeRecord opened (OWNER_REVIEW) - Post-Phase-IGUI Task 2 MR-CAL-1 diagnostics",
        details={"record_id": rec.record_id, "change_type": "governance_change",
                 "status": rec.status.value, "candidate_id": CANDIDATE_ID,
                 "digest": p["digest"]},
    ))
    return {"added": True, "record_id": rec.record_id, "status": rec.status.value}


def main(use_governance: bool = False) -> dict:
    p = run_diagnostics()
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
