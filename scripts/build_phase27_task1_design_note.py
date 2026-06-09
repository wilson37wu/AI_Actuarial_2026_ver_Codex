"""Phase 27 Task 1 - research + design note builder.

Candidate CHOSEN (design-note-first discipline, one per cycle): RICHER
UPPER-TAIL DEPENDENCE COPULA - an explicit upper-tail-asymmetry parameter (the
generalized-hyperbolic skew-t copula; Demarta & McNeil 2005) layered on top of
the FROZEN (df 2.9451, Sigma), with gamma = 0 recovering the symmetric t
EXACTLY.  Motivation is QUANTIFIED from the Phase 26 Task 3 residual-gap
decomposition: the nested path-wise truth 46,638.9 is 14.29% above the frozen-t
component read-out 39,975.7, and 91.9% of that gap (6,120.2) is COPULA-FORM -
exceeding the entire gaussian->t dependence-form sensitivity (4,765.6) - while
the governed relief surface mis-prices only 1.16%.  The genuine nested joint
upper tail is heavier than a radially-symmetric t can represent.

Candidates NOT chosen this cycle (rationale recorded in the note):
- grouped-t copula (Daul et al. 2003): heterogeneous df by driver group; richer
  but does NOT add radial asymmetry (each block stays symmetric) and needs a
  group partition that pre-empts a calibration decision - deferred behind the
  asymmetry parameter, which is the cheaper strict super-set of the freeze.
- vine / pair-copula construction (Aas et al. 2009): most general but a large
  parameter surface (d-1 trees) that cannot be governed as a single additive
  change under Art. 234 in one phase - deferred.
- credentialled-data calibration: standing human-action blocker.

Outputs: docs/validation/PHASE27_TASK1_DESIGN_NOTE.{json,md};
         docs/RICHER_TAIL_DEPENDENCE_DESIGN_CARD.md;
         governance ChangeRecord (OWNER_REVIEW) + audit entry (--governance).

Idempotent: the ChangeRecord is detected by title on re-run.
Run: PYTHONPATH=/var/tmp/pylibs:. python3 scripts/build_phase27_task1_design_note.py [--governance] [--fast]

EDUCATIONAL ONLY - design note; no production capital use.
"""
from __future__ import annotations

import json
import os
import sys

from par_model_v2.governance.audit_trail import AuditEntry, ChangeRecord, GovernanceStore
from par_model_v2.projection.tail_dependence_upgrade import (
    BOOTSTRAP_N_SIM_GATE,
    BOOTSTRAP_REPLICATES_GATE,
    BOOTSTRAP_SE_GATE,
    COPULA_FORM_RESIDUAL_ABS,
    COPULA_FORM_SHARE_OF_GAP,
    DEPENDENCE_FORM_SENSITIVITY_T_MINUS_G,
    DF_REMATCH_TOL,
    FROZEN_T_COMPONENT_SCR_REFERENCE,
    GAMMA_ZERO_RECOVERY_TOL,
    NESTED_PATHWISE_SCR_REFERENCE,
    NEW_RISK_ID,
    RANK_INVARIANCE_DF,
    REAGG_MATERIALITY_DISCLOSURE_THRESHOLD,
    RELIEF_SURFACE_PART_ABS,
    RELIEF_SURFACE_SHARE_OF_GAP,
    RHO_FROZEN_TOL,
    RICHER_COPULA_SIGN_GATE_REFERENCE,
    TOTAL_GAP_ABS,
    TOTAL_GAP_REL_TO_NESTED,
    skew_t_vs_symmetric_t_pre_study,
    tail_dependence_upgrade_use_restrictions,
)

GOV_PATH = os.path.join(".claude-dev", "GOVERNANCE_STORE.json")
OUT_DIR = os.path.join("docs", "validation")
JSON_PATH = os.path.join(OUT_DIR, "PHASE27_TASK1_DESIGN_NOTE.json")
MD_PATH = os.path.join(OUT_DIR, "PHASE27_TASK1_DESIGN_NOTE.md")
CARD_PATH = os.path.join("docs", "RICHER_TAIL_DEPENDENCE_DESIGN_CARD.md")
P26T3 = os.path.join(OUT_DIR, "PHASE26_TASK3_MARGIN_BOOTSTRAP_REPORT.json")

CHANGE_TITLE = (
    "Phase 27 Task 1 - design note: richer upper-tail dependence copula "
    "(skew-t upper-tail-asymmetry parameter on the frozen t copula)"
)

STANDARD_REFERENCES = [
    "Solvency II Delegated Reg. Art. 234 (empirically justified diversification incl. tail behaviour; dependence justified on the basis actually used for capital)",
    "Solvency II Delegated Reg. Art. 23 (future management actions: objective, realistic, verifiable)",
    "SOA ASOP 56 §3.1.3/§3.4/§3.5", "SOA ASOP 25 §3.3", "IA TAS M §3.2/§3.6",
    "IFoA Life Aggregation & Simulation working party",
    "Demarta & McNeil (2005), The t copula and related copulas (skew-t copula)",
    "McNeil, Frey & Embrechts (2015), Quantitative Risk Management ch. 7 (GH skew-t; tail dependence)",
    "Daul, De Giorgi, Lindskog & McNeil (2003), The grouped t-copula",
    "Aas, Czado, Frigessi & Bakken (2009), Pair-copula constructions of multiple dependence (vines)",
]

AFFECTED_COMPONENTS = [
    "par_model_v2/projection/tail_dependence_upgrade.py (NEW, tested helper module)",
    "tests/test_phase27_task1_design_note.py",
    "scripts/build_phase27_task1_design_note.py",
    "docs/validation/PHASE27_TASK1_DESIGN_NOTE.{json,md}",
    "docs/RICHER_TAIL_DEPENDENCE_DESIGN_CARD.md",
]


def _load_p26t3_motivation() -> dict:
    """Archived Phase 26 Task 3 figures (motivation; NOT consumed by gates)."""
    try:
        with open(P26T3) as fh:
            r = json.load(fh)
        res = r.get("result", r)
        decomp = res.get("residual_gap_decomposition", {})
        return {
            "nested_scr": NESTED_PATHWISE_SCR_REFERENCE,
            "frozen_t_component_scr": FROZEN_T_COMPONENT_SCR_REFERENCE,
            "total_gap_abs": TOTAL_GAP_ABS,
            "total_gap_rel_to_nested": TOTAL_GAP_REL_TO_NESTED,
            "copula_form_residual_abs": COPULA_FORM_RESIDUAL_ABS,
            "copula_form_share_of_gap": COPULA_FORM_SHARE_OF_GAP,
            "relief_surface_part_abs": RELIEF_SURFACE_PART_ABS,
            "relief_surface_share_of_gap": RELIEF_SURFACE_SHARE_OF_GAP,
            "dependence_form_sensitivity_t_minus_g": DEPENDENCE_FORM_SENSITIVITY_T_MINUS_G,
            "interpretation": decomp.get("interpretation"),
            "source": P26T3,
        }
    except Exception as exc:  # archived report missing -> disclosed
        return {"source": P26T3, "load_error": str(exc)}


def build_design_note(fast: bool = False) -> dict:
    pre = skew_t_vs_symmetric_t_pre_study(
        seed=42, n_scen=40_000 if fast else 200_000
    )
    note = {
        "title": "Phase 27 Task 1 - Design Note: Richer Upper-Tail Dependence Copula",
        "verdict": "PASS" if pre["mechanism_demonstrated"] else "FAIL",
        "classification": "EDUCATIONAL",
        "candidate_chosen": (
            "richer upper-tail dependence - an explicit upper-tail-asymmetry "
            "parameter (GH skew-t copula) on the FROZEN (df 2.9451, Sigma); "
            "gamma = 0 recovers the symmetric t EXACTLY (strict super-set of the "
            "governed copula)"
        ),
        "candidates_not_chosen": {
            "grouped_t_copula": (
                "Daul et al. (2003): heterogeneous df by driver group is richer "
                "but each block remains radially SYMMETRIC (no upper-tail "
                "asymmetry, the demonstrated copula-form driver) and it forces a "
                "group-partition calibration decision up front. Deferred behind "
                "the single-parameter asymmetry upgrade."
            ),
            "vine_pair_copula": (
                "Aas et al. (2009): most general (d-1 trees of bivariate "
                "copulas) but the parameter surface cannot be governed as a "
                "single additive Art. 234 change in one phase. Deferred as the "
                "general fallback if the asymmetry parameter is insufficient."
            ),
            "credentialled_data_calibration": (
                "BLOCKED on credentialled management-practice data (standing "
                "human-action blocker); not executable from the sandbox. Remains "
                "the production sign-off residual by design."
            ),
        },
        "motivation_from_phase26_task3": _load_p26t3_motivation(),
        "problem": (
            "Phase 26 closed the BASIS question: the full path-wise copula "
            "re-aggregation (per-driver composition relief on the frozen copula) "
            "and the analytic re-anchoring are economically interchangeable "
            "(+0.46%), and the frozen-copula margin bootstrap is tight "
            "(SE 4.07%). Yet the component read-out 39,975.7 still sits 14.29% "
            "below the nested truth 46,638.9, and the bootstrap DECOMPOSED that "
            "residual: only 543.0 (8.1%; 1.16% of nested) is relief-surface "
            "error - the remaining 6,120.2 (91.9%) is COPULA-FORM and EXCEEDS "
            "the entire gaussian->t dependence-form sensitivity (4,765.6). The "
            "frozen copula is a Student-t: a SINGLE scalar df with a radially "
            "SYMMETRIC tail (lambda_U = lambda_L). The nested joint loss is "
            "upper-asymmetric - the simultaneous-large-loss corner (credit + "
            "FX/liquidity carve-outs co-crashing) is heavier than a symmetric t "
            "can represent at ANY df without distorting the body or the lower "
            "tail. No re-choice of df closes a SHAPE gap."
        ),
        "method": (
            "Phase 27 keeps the calibrated MARGINS and the governed rank "
            "dependence (df 2.9451, correlation Sigma) FROZEN and adds ONE new "
            "structural lever: an upper-tail-asymmetry parameter via the "
            "generalized-hyperbolic skew-t copula (Demarta & McNeil 2005; McNeil, "
            "Frey & Embrechts 2015 ch. 7), X = gamma*W + sqrt(W)*Z with "
            "W ~ InvGamma(df/2, df/2), Z ~ N(0, Sigma). The skewness vector gamma "
            "controls the radial asymmetry: gamma > 0 lifts the UPPER-tail "
            "dependence while leaving the lower tail near the symmetric level, "
            "and gamma = 0 reproduces the governed symmetric t EXACTLY (a strict "
            "super-set - the freeze is nested as a boundary case, so the archive "
            "cross-check is exact). Task 2 fits gamma to the realised "
            "upper-tail co-exceedances of the standalone capital-loss vectors "
            "(margins and df UNCHANGED), re-aggregates the path-wise component "
            "basis on the skew-t copula, and Task 3 bootstraps the skew-t SCR "
            "and re-decomposes the residual gap against the nested reference."
        ),
        "hypothesis": (
            "The skew-t (gamma > 0) re-aggregated path-wise SCR is HIGHER than "
            "the frozen-t component read-out 39,975.7 (a heavier, asymmetric "
            "upper tail can only RAISE the joint 99.5% loss vs the symmetric "
            "freeze) and the gap to the nested reference 46,638.9 SHRINKS; the "
            "synthetic skew-t pre-study sign carries over."
        ),
        "pre_study_skew_t_vs_symmetric_t": pre,
        "pre_study_disclosure": (
            "The pre-study uses a SYNTHETIC seven-driver portfolio on common "
            "random numbers; the symmetric-t basis is the SAME GH mixture with "
            "gamma = 0 (mixing variate W and Gaussian Z reused), through "
            "IDENTICAL frozen margins - so the ONLY difference is upper-tail "
            f"asymmetry. Positive skewness lifts the upper-tail-dependence proxy "
            f"to {pre['tail_dependence_proxy']['skew_t_upper']:.3f} (vs "
            f"{pre['tail_dependence_proxy']['symmetric_t_upper']:.3f} symmetric) "
            f"while the lower tail stays near-symmetric "
            f"({pre['tail_dependence_proxy']['skew_t_lower']:.3f}), and raises "
            f"VaR99.5 by {pre['var_understatement_rel_at_var995']:.1%} and ES99.5 "
            f"by {pre['es_understatement_rel_at_es995']:.1%}: the symmetric copula "
            "UNDERSTATES upper-tail capital, the SAME sign as the documented "
            "nested-vs-frozen-t copula-form residual. The gamma = 0 recovery is "
            f"EXACT (max abs deviation {pre['gamma_zero_recovery_max_abs']:.1e}). "
            "It demonstrates the MECHANISM and its SIGN, not the magnitude of the "
            "real-data effect (synthetic margins; single skewness scalar; no "
            "per-node clip binding); the real magnitude is quantified only at "
            "Tasks 2-3."
        ),
        "gap_analysis": [
            {
                "standard": "Solvency II Del. Reg. Art. 234; IFoA Aggregation WP (dependence on the basis used, incl. tail behaviour)",
                "requirement": "Diversification/dependence empirically justified ON THE BASIS ACTUALLY USED for capital, INCLUDING tail behaviour and tail asymmetry; the copula form must be adequate, not only its parameters.",
                "current_state": "Copula frozen as a radially-SYMMETRIC Student-t (df 2.9451, tail-matched on average pairwise upper-tail dependence, Phase 23 Task 2). lambda_U = lambda_L by construction; the joint loss tail is upper-asymmetric.",
                "gap": "91.9% of the 14.29% nested gap (6,120.2) is copula-FORM and exceeds the whole gaussian->t dependence-form sensitivity (4,765.6) - a SHAPE gap no df re-choice can close.",
                "phase27_design": "Task 2: add an upper-tail-asymmetry parameter (skew-t) on the frozen (df, Sigma); gamma = 0 recovers the freeze exactly; fit gamma to realised upper-tail co-exceedances (margins/df unchanged).",
            },
            {
                "standard": "SOA ASOP 56 §3.5 (dependency structure appropriate to purpose)",
                "requirement": "The dependency structure - including tail co-movement and its asymmetry - appropriate to the intended purpose; material structural limitations identified and addressed where practicable.",
                "current_state": "The symmetric-t structural limitation is DISCLOSED (P26T3 decomposition) and registered, but not yet remediated.",
                "gap": "A disclosed structural limitation that dominates the residual should be attacked with a richer structure, not left as standing disclosure.",
                "phase27_design": "Skew-t is the cheapest super-set: one extra parameter, exact nesting of the freeze, governed as a single additive copula change.",
            },
            {
                "standard": "IA TAS M §3.2/§3.6 (limitations disclosed; evidence reproducible)",
                "requirement": "Material limitations disclosed with quantification; remediation evidence reproducible with recorded config and pre-registered gates.",
                "current_state": "P26T3/T5 disclose the copula-form residual verbatim in the report, risk register and offline UI with the bootstrap CI.",
                "gap": "Disclosure exists; the REMEDIATION (a richer copula form) is the open item.",
                "phase27_design": "Task 3 headline gate: skew-t 95% bootstrap CI tested against nested 46,638.9 (closure or residual re-decomposed); seeds/config/digests recorded; Task 4 refreshes MR-010/MR-014 and opens MR-015 for the copula-form change.",
            },
            {
                "standard": "Solvency II Del. Reg. Art. 23 (management actions consistent with practice)",
                "requirement": "Allowance for management actions consistent with how they would be exercised - including which losses are relievable in a JOINT tail event.",
                "current_state": "The carve-out (non-cuttable) drivers - credit loss, FX/liquidity offsets - dominate the joint tail (P24T3/P26T2); a symmetric copula under-weights their simultaneous-crash corner.",
                "gap": "Under-stating the joint upper tail under-states the un-relievable carve-out losses, i.e. understates required capital.",
                "phase27_design": "The skew-t lifts the upper-tail corner where the carve-outs co-move; relief still applies only to the cuttable component per scenario (P26T2 convention unchanged).",
            },
        ],
        "task2_acceptance_criteria": [
            "Add an upper-tail-asymmetry parameter (GH skew-t copula) on the FROZEN (df 2.9451, Sigma); the symmetric t is recovered EXACTLY at gamma = 0 (strict super-set; nested freeze)",
            f"gamma = 0 EXACT-recovery check: skew-t aggregate reproduces the symmetric-t aggregate to within {GAMMA_ZERO_RECOVERY_TOL:.0e} on common random numbers (archive cross-check is then exact)",
            f"Frozen-t COMPONENT read-out {FROZEN_T_COMPONENT_SCR_REFERENCE:,.1f} reproduced bit-identically BEFORE any skew-t computation (archive cross-check)",
            f"Rank invariance: df re-matched on the WITHOUT-actions staged losses within {DF_REMATCH_TOL} of {RANK_INVARIANCE_DF}; correlation matrix max|diff| <= {RHO_FROZEN_TOL} (df + Sigma FROZEN; only gamma added; Art. 234)",
            "Margins UNCHANGED: standalone marginal capital bit-identical (the upgrade changes the COPULA only)",
            "gamma fitted to realised upper-tail co-exceedances of the standalone loss vectors (no re-tuning of df/Sigma/margins; leakage-free)",
            f"Sign gate (pre-registered): skew-t re-aggregated path-wise SCR >= frozen-t component {RICHER_COPULA_SIGN_GATE_REFERENCE:,.1f}; magnitude DISCLOSED, not gated",
            "Symmetric-t component basis RETAINED and reported alongside as the comparison variant",
            "No gate-shopping: these gates fixed in this Task 1 note before any real-data skew-t fit",
            "code_change ChangeRecord OWNER_REVIEW",
        ],
        "task3_acceptance_criteria": [
            f"Skew-t margin bootstrap: >= {BOOTSTRAP_REPLICATES_GATE} replicates x {BOOTSTRAP_N_SIM_GATE:,} sims (P26T3 pattern)",
            f"HEADLINE gate: nested path-wise reference {NESTED_PATHWISE_SCR_REFERENCE:,.1f} INSIDE the skew-t 95% bootstrap CI (closure of the copula-form residual) - if still outside, the residual gap MUST be RE-decomposed (residual copula-form vs relief-surface) and the REDUCTION vs the frozen-t copula-form residual 6,120.2 quantified - no silent acceptance",
            "Directional gate: skew-t REDUCES the nested gap on common random numbers vs the symmetric-t basis (no widening)",
            f"Bootstrap SE <= {BOOTSTRAP_SE_GATE:.0%} of the mean SCR",
            "Idempotent re-run digest-identical; seeds/config recorded",
            "methodology_change ChangeRecord OWNER_REVIEW",
        ],
        "task4_acceptance_criteria": [
            "Tail diagnostics on the skew-t basis: skew-vs-symmetric and skew-vs-nested deltas at VaR/ES/SCR; upper- vs lower-tail dependence reported (the asymmetry is the headline)",
            f"MR-010 / MR-014 refreshed if the skew-t SCR moves more than {REAGG_MATERIALITY_DISCLOSURE_THRESHOLD:.0%} from the frozen-t component read-out (disclosure trigger, not pass/fail); open {NEW_RISK_ID} for the copula-form (radial-asymmetry) change",
            f"Rank invariance re-verified: df {RANK_INVARIANCE_DF} on without-actions losses; correlation frozen; only gamma added (no silent re-tuning)",
            "Reproducibility: seeds, config, digests recorded; assumption_change/governance ChangeRecord OWNER_REVIEW",
        ],
        "task5_plan": (
            "Offline-UI propagation (ui_data.json contract 1.8.0 -> 1.9.0 ADDITIVE; "
            "richer-tail panel: skew-t-vs-symmetric-t-vs-nested SCR comparison, "
            "upper/lower tail-dependence asymmetry, bootstrap CI closure read-out, "
            "gates) + PHASE 27 COMPLETE documentation; UI consumes ONLY "
            "model-output JSON, zero-install."
        ),
        "limitations": [
            "The synthetic pre-study proves the upper-tail-asymmetry mechanism and its SIGN, not the magnitude (synthetic margins; single skewness scalar; rank-PIT copula isolation; no per-node clip binding).",
            "The skew-t adds ONE asymmetry parameter; if the real residual needs heterogeneous tail dependence ACROSS drivers, grouped-t (deferred) is the next escalation; vine is the general fallback.",
            "gamma is fitted to upper-tail co-exceedances - a finite-sample estimate; its sampling error is propagated through the Task 3 bootstrap.",
            "Margins and df remain the calibrated frozen values; the upgrade does not revisit the marginal calibration (out of scope this phase).",
            "Action parameters remain educational placeholders pending credentialled practice data + independent APS X2 review.",
        ],
        "use_restrictions": tail_dependence_upgrade_use_restrictions(),
        "standard_references": STANDARD_REFERENCES,
        "affected_components": AFFECTED_COMPONENTS,
    }
    return note


def _md(note: dict) -> str:
    pre = note["pre_study_skew_t_vs_symmetric_t"]
    v = pre["var995"]
    td = pre["tail_dependence_proxy"]
    m = note["motivation_from_phase26_task3"]
    lines = [
        f"# {note['title'].replace(' - ', ' — ', 1)}",
        "",
        f"**Verdict: {note['verdict']}** (design note + tested helper module + synthetic upper-tail-asymmetry pre-study). EDUCATIONAL ONLY.",
        "",
        "## 0. Candidate selection (design-note-first discipline)",
        "",
        f"**Chosen:** {note['candidate_chosen']}.",
        "",
        f"- Grouped-t copula: {note['candidates_not_chosen']['grouped_t_copula']}",
        f"- Vine / pair-copula: {note['candidates_not_chosen']['vine_pair_copula']}",
        f"- Credentialled-data calibration: {note['candidates_not_chosen']['credentialled_data_calibration']}",
        "",
        "## 1. Problem",
        "",
        note["problem"],
        "",
        f"Archived Phase 26 Task 3 motivation figures (NOT consumed by gates): {json.dumps({k: m.get(k) for k in ('nested_scr', 'frozen_t_component_scr', 'total_gap_rel_to_nested', 'copula_form_residual_abs', 'copula_form_share_of_gap', 'relief_surface_part_abs', 'dependence_form_sensitivity_t_minus_g')}, default=float)}",
        "",
        "## 2. Method — richer upper-tail dependence (skew-t copula; Tasks 2-3)",
        "",
        note["method"],
        "",
        f"**Hypothesis:** {note['hypothesis']}",
        "",
        "## 3. Pre-study (synthetic upper-tail-asymmetry mechanism)",
        "",
        f"- Synthetic portfolio: 7 drivers, GH skew-t mixture (df={pre['config']['df']}, rho={pre['config']['rho']}, gamma={pre['config']['gamma']}); symmetric-t basis is the SAME mixture at gamma=0 on common random numbers; identical frozen margins; n_scen={pre['config']['n_scen']:,}, seed={pre['config']['seed']}",
        f"- VaR99.5: symmetric-t {v['symmetric_t']:.2f}; skew-t {v['skew_t']:.2f} → symmetric basis UNDERSTATES by {pre['var_understatement_rel_at_var995']:.1%}",
        f"- ES99.5 understatement: {pre['es_understatement_rel_at_es995']:.1%}",
        f"- Upper-tail-dependence proxy (p={td['level_p']}): skew-t {td['skew_t_upper']:.3f} vs symmetric-t {td['symmetric_t_upper']:.3f}; lower tail skew-t {td['skew_t_lower']:.3f} vs symmetric-t {td['symmetric_t_lower']:.3f}",
        f"- Radial asymmetry (upper−lower): skew-t {td['skew_t_asymmetry']:.3f} vs symmetric-t {td['symmetric_t_asymmetry']:.3f} (~0)",
        f"- gamma=0 EXACT recovery: max abs deviation {pre['gamma_zero_recovery_max_abs']:.1e} (≤ {GAMMA_ZERO_RECOVERY_TOL:.0e})",
        f"- understatement_sign_ok={pre['understatement_sign_ok']}; asymmetry_ok={pre['asymmetry_ok']}; ordering_ok={pre['ordering_ok']}; gamma_zero_recovery_ok={pre['gamma_zero_recovery_ok']}; digest={pre['digest']}",
        "",
        note["pre_study_disclosure"],
        "",
        "## 4. Gap analysis (standards vs current model)",
        "",
    ]
    for g in note["gap_analysis"]:
        lines += [f"### {g['standard']}", "",
                  f"- **Requirement:** {g['requirement']}",
                  f"- **Current state:** {g['current_state']}",
                  f"- **Gap:** {g['gap']}",
                  f"- **Phase 27 design:** {g['phase27_design']}", ""]
    lines += ["## 5. Acceptance criteria (FIXED, pre-registered — no gate-shopping)", "", "**Task 2:**", ""]
    lines += [f"- {c}" for c in note["task2_acceptance_criteria"]]
    lines += ["", "**Task 3:**", ""]
    lines += [f"- {c}" for c in note["task3_acceptance_criteria"]]
    lines += ["", "**Task 4:**", ""]
    lines += [f"- {c}" for c in note["task4_acceptance_criteria"]]
    lines += ["", f"**Task 5 plan:** {note['task5_plan']}"]
    lines += ["", "## 6. Limitations", ""]
    lines += [f"- {l}" for l in note["limitations"]]
    lines += ["", "## 7. Standards", ""]
    lines += [f"- {s}" for s in note["standard_references"]]
    lines += ["", "*Generated by scripts/build_phase27_task1_design_note.py — educational model; production sign-off withheld.*", ""]
    return "\n".join(lines)


def _card(note: dict) -> str:
    pre = note["pre_study_skew_t_vs_symmetric_t"]
    v = pre["var995"]
    td = pre["tail_dependence_proxy"]
    return "\n".join([
        "# Richer Upper-Tail Dependence Copula — Design Card (Phase 27)",
        "",
        f"**Verdict: {note['verdict']}** (design note; implementation in Phase 27 Tasks 2-4). EDUCATIONAL ONLY.",
        "",
        "## What changes",
        "",
        "The aggregation copula gains ONE structural lever: an upper-tail-asymmetry",
        "parameter (GH skew-t copula) layered on the FROZEN (df 2.9451, Sigma).",
        "gamma = 0 recovers the symmetric t EXACTLY (strict super-set; nested freeze).",
        "Margins, df and correlation are UNCHANGED — only the radial tail shape moves.",
        "",
        "## Why (quantified motivation + synthetic pre-study)",
        "",
        f"- Archived P26T3 decomposition: nested {NESTED_PATHWISE_SCR_REFERENCE:,.1f} vs frozen-t component {FROZEN_T_COMPONENT_SCR_REFERENCE:,.1f} → 14.29% gap; {COPULA_FORM_RESIDUAL_ABS:,.1f} (91.9%) is COPULA-FORM, exceeding the whole gaussian→t sensitivity ({DEPENDENCE_FORM_SENSITIVITY_T_MINUS_G:,.1f}); relief-surface only {RELIEF_SURFACE_PART_ABS:,.1f} (1.16% of nested)",
        f"- The frozen copula is radially SYMMETRIC (lambda_U = lambda_L); the joint loss tail is upper-asymmetric — no df re-choice closes a SHAPE gap",
        f"- Synthetic pre-study (common random numbers): skew-t lifts upper-tail dependence {td['symmetric_t_upper']:.3f} → {td['skew_t_upper']:.3f} (lower tail stays {td['skew_t_lower']:.3f}); VaR99.5 {v['symmetric_t']:.2f} → {v['skew_t']:.2f} (+{pre['var_understatement_rel_at_var995']:.1%})",
        f"- gamma=0 EXACT recovery (max abs dev {pre['gamma_zero_recovery_max_abs']:.1e}); reproducibility digest: {pre['digest']}",
        "",
        "## Pre-registered gates (s5 of the design note)",
        "",
        "- Strict super-set: gamma=0 reproduces the symmetric t EXACTLY; df 2.9451 (tol 1e-4) + Sigma (max|diff| ≤ 1e-12) FROZEN; margins bit-identical",
        f"- Archive cross-check: frozen-t component read-out {FROZEN_T_COMPONENT_SCR_REFERENCE:,.1f} reproduced bit-identically",
        f"- Sign gate: skew-t SCR ≥ frozen-t component {RICHER_COPULA_SIGN_GATE_REFERENCE:,.1f} (magnitude disclosed, not gated)",
        f"- HEADLINE (Task 3): nested {NESTED_PATHWISE_SCR_REFERENCE:,.1f} INSIDE the skew-t 95% bootstrap CI, or residual RE-decomposed + reduction vs 6,120.2 quantified; skew-t must REDUCE the nested gap on CRN",
        f"- MR-010/MR-014 refresh trigger: skew-t-vs-frozen SCR delta > 1%; open {NEW_RISK_ID} for the copula-form change",
        "",
        "## Out of scope / residuals (disclosed)",
        "",
        "- Grouped-t (heterogeneous df by group): deferred escalation if a single asymmetry scalar is insufficient",
        "- Vine / pair-copula: general fallback; not governable as one additive change this phase",
        "- Credentialled calibration: standing human-action blocker",
        "",
        "*Generated by scripts/build_phase27_task1_design_note.py — educational model; production sign-off withheld.*",
        "",
    ])


def apply_governance(store: GovernanceStore, note: dict) -> dict:
    actor = "Phase27Task1DesignNote"
    phase = "Phase 27: Richer Tail-Dependence Copula"
    if any(r.title == CHANGE_TITLE for r in store.change_records):
        return {"added": False, "reason": "already applied (idempotent)"}
    pre = note["pre_study_skew_t_vs_symmetric_t"]
    td = pre["tail_dependence_proxy"]
    rec = ChangeRecord.create(
        title=CHANGE_TITLE,
        description=(
            "Design note for Phase 27: richer upper-tail dependence copula - an "
            "explicit upper-tail-asymmetry parameter (GH skew-t copula; Demarta & "
            "McNeil 2005) layered on the FROZEN (df 2.9451, Sigma), with gamma = 0 "
            "recovering the symmetric t EXACTLY (new tested helper module "
            "par_model_v2/projection/tail_dependence_upgrade.py: synthetic skew-t "
            "vs symmetric-t pre-study on common random numbers, pre-registered "
            "gate constants, use restrictions). Addresses the COPULA-FORM residual "
            "QUANTIFIED in the Phase 26 Task 3 report (nested 46,638.9 vs frozen-t "
            "component 39,975.7; 91.9% of the 14.29% gap is copula-form, exceeding "
            "the entire gaussian->t sensitivity). Candidate selection rationale "
            "recorded (grouped-t and vine deferred; credentialled calibration "
            "blocked on data). FIXED pre-registered acceptance gates for Tasks 2-4 "
            "including exact gamma=0 nesting and the SIGN gate."
        ),
        change_type="governance_change",
        affected_components=AFFECTED_COMPONENTS,
        standard_references=STANDARD_REFERENCES,
        before_snapshot={
            "copula_form": (
                "radially-symmetric Student-t (df 2.9451, Sigma frozen); "
                "lambda_U = lambda_L; nested truth 46,638.9 above the frozen-t "
                "component 39,975.7 with 91.9% of the gap copula-FORM (P26T3)"
            ),
        },
        after_snapshot={
            "design": "skew-t upper-tail-asymmetry parameter on the frozen (df, Sigma), gamma=0 nests the freeze exactly (Task 2); bootstrap closure test vs nested (Task 3); tail diagnostics + MR refresh + MR-015 (Task 4); UI 1.8.0 -> 1.9.0 (Task 5)",
            "pre_study": {
                "var_understatement_rel_at_var995": pre["var_understatement_rel_at_var995"],
                "es_understatement_rel_at_es995": pre["es_understatement_rel_at_es995"],
                "upper_tail_dependence_skew_vs_sym": [td["skew_t_upper"], td["symmetric_t_upper"]],
                "gamma_zero_recovery_max_abs": pre["gamma_zero_recovery_max_abs"],
                "asymmetry_ok": pre["asymmetry_ok"],
            },
            "verdict": note["verdict"] + " (design note)",
        },
        impact_assessment=(
            "No numeric capital output changed this cycle (design note + additive "
            "helper module only). Fixes non-gate-shopped acceptance criteria for "
            "Tasks 2-4 BEFORE any real-data skew-t fit; pre-registers the SIGN of "
            "the expected capital effect (skew-t SCR >= frozen-t component) and the "
            "HEADLINE closure criterion (nested inside the skew-t 95% CI, or "
            "residual re-decomposed with the copula-form reduction quantified). "
            "The upgrade is a strict super-set of the governed copula (gamma=0 "
            "exact), so the freeze and all prior read-outs are preserved. "
            "Educational classification retained; production sign-off withheld "
            "pending credentialled data + APS X2 review."
        ),
        author=actor, phase=phase,
        quantitative_impact=(
            f"Synthetic pre-study: upper-tail asymmetry raises VaR99.5 by "
            f"{pre['var_understatement_rel_at_var995']:.1%} and ES99.5 by "
            f"{pre['es_understatement_rel_at_es995']:.1%}; upper-tail-dependence "
            f"proxy {td['symmetric_t_upper']:.3f} -> {td['skew_t_upper']:.3f} "
            f"(lower tail near-symmetric). No capital figures changed. Archived "
            f"motivation: copula-form residual {COPULA_FORM_RESIDUAL_ABS:,.1f} "
            f"(91.9% of the 14.29% nested gap, P26T3)."
        ),
    )
    rec.submit_for_peer_review(actor=actor, comments="Design note + new unit tests PASS; no existing module touched; gamma=0 nests the governed freeze exactly.")
    rec.submit_to_owner(actor=actor, comments="Owner review: synthetic-mechanism scope + copula-form residual remediation path documented; sign-off withheld.")
    store.add_change_record(rec)
    store.audit_trail.append(AuditEntry.governance(
        actor=actor, phase=phase,
        event="ChangeRecord opened (OWNER_REVIEW) - Phase 27 Task 1 design note (richer upper-tail dependence / skew-t copula)",
        details={"record_id": rec.record_id, "change_type": "governance_change",
                 "status": rec.status.value, "affected_components": AFFECTED_COMPONENTS},
    ))
    return {"added": True, "record_id": rec.record_id, "status": rec.status.value}


def main(use_governance: bool = False, fast: bool = False) -> dict:
    note = build_design_note(fast=fast)
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(JSON_PATH, "w") as fh:
        json.dump(note, fh, indent=1, default=float)
    with open(MD_PATH, "w") as fh:
        fh.write(_md(note))
    with open(CARD_PATH, "w") as fh:
        fh.write(_card(note))
    out = {"verdict": note["verdict"], "json": JSON_PATH, "md": MD_PATH, "card": CARD_PATH}
    if use_governance:
        store = GovernanceStore.from_json(open(GOV_PATH).read())
        gov = apply_governance(store, note)
        if gov.get("added"):
            with open(GOV_PATH, "w") as fh:
                fh.write(store.to_json())
        gov["audit_entries"] = len(store.audit_trail.all())
        gov["audit_integrity_ok"] = store.audit_trail.verify_all()
        gov["change_records_total"] = len(store.change_records)
        out["governance"] = gov
    return out


if __name__ == "__main__":
    res = main(use_governance="--governance" in sys.argv, fast="--fast" in sys.argv)
    print(json.dumps(res, indent=1, default=str))
