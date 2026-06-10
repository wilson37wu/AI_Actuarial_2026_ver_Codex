"""Phase 28 Task 1 - research + design note builder.

Candidate CHOSEN (design-note-first discipline, one per cycle): the GROUPED
t-copula (Daul, De Giorgi, Lindskog & McNeil 2003) - per-block degrees of
freedom (heterogeneous tail dependence across driver blocks) on the FROZEN
correlation Sigma, with the homogeneous boundary (all df_g = 2.9451, single
shared mixing variate) recovering the governed single-df t copula EXACTLY.

Motivation is the Phase 27 RECONFIRMATION: the skew-t upper-tail-asymmetry
scalar fitted leakage-free pinned at gamma_hat ~ 6.24e-05 (the realised
standalone margins show no radial asymmetry), so the copula-FORM residual fell
only 6,120.2 -> 6,114.9 (0.09%) and was RE-CONFIRMED as NOT a standalone-driver
asymmetry effect. The single Student-t imposes ONE tail-dependence level on
EVERY pair; the nested joint loss has HETEROGENEOUS tail co-movement (the
financial / carve-out block co-crashes far harder than it co-moves with the
non-financial block). The grouped-t is the indicated escalation: it adds
per-block tail dependence the single pooled df cannot represent.

Candidates NOT chosen this cycle (rationale recorded in the note):
- vine / pair-copula construction (Aas et al. 2009): the general fallback (d-1
  trees of bivariate copulas) but the parameter surface cannot be governed as a
  single additive Art. 234 change in one phase - deferred behind the grouped-t,
  which is the cheaper structured super-set of the freeze.
- heavier single pooled df / re-anchor: a uniform tail-heaviness move; it does
  NOT add the across-driver tail-dependence heterogeneity the residual points
  to (the single df already failed at Phase 26/27).
- credentialled-data calibration: standing human-action blocker.

KEY HONEST FINDING (disclosed up front): the grouped-t is a tail-dependence
HETEROGENEITY lever, NOT a uniform tail-heaviness lever. The single-df t shares
ONE mixing variate and is therefore the MAXIMAL-cross-block-dependence boundary;
the grouped-t's independent per-block mixing can only REDUCE cross-block tail
co-movement. So its effect on AGGREGATE SCR is genuinely TWO-SIDED (unlike the
sign-pinned skew-t asymmetry scalar): on the synthetic portfolio the cross-block
dilution dominates and aggregate VaR99.5 FALLS ~5%. Whether the grouped-t CLOSES
the upward nested residual therefore depends on whether the nested structure is
genuinely within-block-concentrated - resolved empirically at Tasks 2-3; a
WIDENING is itself informative (escalate to the vine).

Outputs: docs/validation/PHASE28_TASK1_DESIGN_NOTE.{json,md};
         docs/GROUPED_T_DESIGN_CARD.md;
         governance ChangeRecord (OWNER_REVIEW) + audit entry (--governance).

Idempotent: the ChangeRecord is detected by title on re-run.
Run: PYTHONPATH=/var/tmp/pylibs:. python3 scripts/build_phase28_task1_design_note.py [--governance] [--fast]

EDUCATIONAL ONLY - design note; no production capital use.
"""
from __future__ import annotations

import json
import os
import sys

from par_model_v2.governance.audit_trail import AuditEntry, ChangeRecord, GovernanceStore
from par_model_v2.projection.grouped_t_upgrade import (
    BOOTSTRAP_N_SIM_GATE,
    BOOTSTRAP_REPLICATES_GATE,
    BOOTSTRAP_SE_GATE,
    COPULA_FORM_RESIDUAL_ABS,
    COPULA_FORM_SHARE_OF_GAP,
    DEPENDENCE_FORM_SENSITIVITY_T_MINUS_G,
    DF_REMATCH_TOL,
    FIN_BLOCK,
    FROZEN_T_COMPONENT_SCR_REFERENCE,
    GROUPED_T_SIGN_GATE_REFERENCE,
    HOMOGENEOUS_RECOVERY_TOL,
    NESTED_PATHWISE_SCR_REFERENCE,
    NEW_RISK_ID,
    NONFIN_BLOCK,
    RANK_INVARIANCE_DF,
    REAGG_MATERIALITY_DISCLOSURE_THRESHOLD,
    RELIEF_SURFACE_PART_ABS,
    RHO_FROZEN_TOL,
    SKEWT_GAMMA_HAT,
    SKEWT_RECONFIRMED_COPULA_FORM_RESIDUAL_ABS,
    TOTAL_GAP_ABS,
    TOTAL_GAP_REL_TO_NESTED,
    grouped_t_upgrade_use_restrictions,
    grouped_t_vs_single_t_pre_study,
)

GOV_PATH = os.path.join(".claude-dev", "GOVERNANCE_STORE.json")
OUT_DIR = os.path.join("docs", "validation")
JSON_PATH = os.path.join(OUT_DIR, "PHASE28_TASK1_DESIGN_NOTE.json")
MD_PATH = os.path.join(OUT_DIR, "PHASE28_TASK1_DESIGN_NOTE.md")
CARD_PATH = os.path.join("docs", "GROUPED_T_DESIGN_CARD.md")
P27T3 = os.path.join(OUT_DIR, "PHASE27_TASK3_SKEW_T_BOOTSTRAP_REPORT.json")

CHANGE_TITLE = (
    "Phase 28 Task 1 - design note: grouped-t / heterogeneous tail-dependence "
    "copula (per-block degrees of freedom on the frozen correlation Sigma)"
)

STANDARD_REFERENCES = [
    "Solvency II Delegated Reg. Art. 234 (empirically justified diversification incl. tail behaviour; dependence justified on the basis actually used for capital)",
    "Solvency II Delegated Reg. Art. 23 (future management actions: objective, realistic, verifiable)",
    "SOA ASOP 56 3.1.3/3.4/3.5", "SOA ASOP 25 3.3", "IA TAS M 3.2/3.6",
    "IFoA Life Aggregation & Simulation working party",
    "Daul, De Giorgi, Lindskog & McNeil (2003), The grouped t-copula",
    "Demarta & McNeil (2005), The t copula and related copulas",
    "McNeil, Frey & Embrechts (2015), Quantitative Risk Management ch. 7 (grouped t; tail dependence)",
    "Aas, Czado, Frigessi & Bakken (2009), Pair-copula constructions of multiple dependence (vines)",
]

AFFECTED_COMPONENTS = [
    "par_model_v2/projection/grouped_t_upgrade.py (NEW, tested helper module)",
    "tests/test_phase28_task1_design_note.py",
    "scripts/build_phase28_task1_design_note.py",
    "docs/validation/PHASE28_TASK1_DESIGN_NOTE.{json,md}",
    "docs/GROUPED_T_DESIGN_CARD.md",
]


def _load_p27t3_motivation() -> dict:
    """Archived Phase 27 Task 3 figures (motivation; NOT consumed by gates)."""
    base = {
        "nested_scr": NESTED_PATHWISE_SCR_REFERENCE,
        "frozen_t_component_scr": FROZEN_T_COMPONENT_SCR_REFERENCE,
        "total_gap_abs": TOTAL_GAP_ABS,
        "total_gap_rel_to_nested": TOTAL_GAP_REL_TO_NESTED,
        "frozen_t_copula_form_residual_abs": COPULA_FORM_RESIDUAL_ABS,
        "copula_form_share_of_gap": COPULA_FORM_SHARE_OF_GAP,
        "relief_surface_part_abs": RELIEF_SURFACE_PART_ABS,
        "skewt_gamma_hat": SKEWT_GAMMA_HAT,
        "skewt_reconfirmed_copula_form_residual_abs": SKEWT_RECONFIRMED_COPULA_FORM_RESIDUAL_ABS,
        "dependence_form_sensitivity_t_minus_g": DEPENDENCE_FORM_SENSITIVITY_T_MINUS_G,
        "source": P27T3,
    }
    try:
        with open(P27T3) as fh:
            r = json.load(fh)
        res = r.get("result", r)
        base["p27t3_headline"] = res.get("headline") or res.get("conclusion")
    except Exception as exc:  # archived report missing -> disclosed
        base["load_error"] = str(exc)
    return base


def build_design_note(fast: bool = False) -> dict:
    pre = grouped_t_vs_single_t_pre_study(
        seed=42, n_scen=40_000 if fast else 200_000
    )
    td = pre["tail_dependence_proxy"]
    note = {
        "title": "Phase 28 Task 1 - Design Note: Grouped-t / Heterogeneous Tail-Dependence Copula",
        "verdict": "PASS" if pre["mechanism_demonstrated"] else "FAIL",
        "classification": "EDUCATIONAL",
        "candidate_chosen": (
            "grouped-t copula (Daul et al. 2003) - per-block degrees of freedom "
            "(heterogeneous tail dependence across driver blocks) on the FROZEN "
            "correlation Sigma; the homogeneous boundary (all df_g = 2.9451, "
            "single shared mixing variate) recovers the governed single-df t "
            "EXACTLY (strict super-set; nested freeze)"
        ),
        "candidates_not_chosen": {
            "vine_pair_copula": (
                "Aas et al. (2009): most general (d-1 trees of bivariate "
                "copulas) but the parameter surface cannot be governed as a "
                "single additive Art. 234 change in one phase. Retained as the "
                "general fallback if a block-homogeneous grouped-t still cannot "
                "represent the nested inner-path joint dynamics."
            ),
            "heavier_single_pooled_df": (
                "A uniform tail-heaviness move (lower the single df / re-anchor): "
                "does NOT add the ACROSS-driver tail-dependence heterogeneity the "
                "residual points to - a single df already failed at Phase 26/27 "
                "and forces lambda equal on every pair. Rejected."
            ),
            "credentialled_data_calibration": (
                "BLOCKED on credentialled management-practice data (standing "
                "human-action blocker); not executable from the sandbox. Remains "
                "the production sign-off residual by design."
            ),
        },
        "motivation_from_phase27": _load_p27t3_motivation(),
        "problem": (
            "Phase 27 closed the upper-tail-ASYMMETRY question NEGATIVELY: fitting "
            "the skew-t skewness scalar gamma leakage-free to the realised "
            "standalone upper-tail co-exceedances pinned it at gamma_hat ~ 6.2e-05 "
            "(the realised margins show no radial asymmetry), so the copula-FORM "
            "residual fell only 6,120.2 -> 6,114.9 (0.09%) and was RE-CONFIRMED as "
            "NOT a standalone-driver asymmetry effect (MR-015 OPEN). The frozen "
            "copula is a SINGLE-df Student-t: it imposes ONE tail-dependence level "
            "on EVERY pair (lambda_ij = lambda for all i,j at the common df). The "
            "nested joint loss is HETEROGENEOUS: the financial / carve-out block "
            "(credit loss + FX/liquidity offsets) co-crashes far harder WITHIN the "
            "block than it co-moves with the non-financial block. A single pooled "
            "df cannot represent within-block >> cross-block tail dependence - no "
            "re-choice of one df closes a heterogeneity gap."
        ),
        "method": (
            "Phase 28 keeps the calibrated MARGINS and the governed correlation "
            "Sigma FROZEN and adds ONE structured lever: per-block degrees of "
            "freedom via the grouped t-copula (Daul et al. 2003). Partition the d "
            "drivers into m blocks; each block g carries its own radial mixing "
            "variate W_g ~ InvGamma(df_g/2, df_g/2) on the SAME Gaussian draw "
            "Z ~ N(0, Sigma): X_k = sqrt(W_g(k)) * Z_k for driver k in block g. "
            "Within a block the pair tail dependence is the t-tail of df_g (shared "
            "mixing -> strong co-crash); across blocks the mixing is independent "
            "-> weaker cross-block tail dependence. The homogeneous boundary (all "
            "df_g = 2.9451 with a SINGLE shared mixing variate) reproduces the "
            "governed single-df t EXACTLY (a strict super-set; the freeze is the "
            "m=1 / fully-pooled boundary, so the archive cross-check is exact). "
            "Task 2 fits the per-block df_g to the realised within-block vs "
            "cross-block co-exceedances of the standalone capital-loss vectors "
            "(margins and Sigma UNCHANGED) on the PRE-REGISTERED partition, "
            "re-aggregates the path-wise component basis on the grouped-t, and "
            "Task 3 bootstraps the grouped-t SCR and re-decomposes the residual "
            "gap against the nested reference."
        ),
        "hypothesis": (
            "The grouped-t produces WITHIN-block >> CROSS-block upper-tail "
            "dependence that a single pooled df cannot (heterogeneity the residual "
            "points to). Its effect on AGGREGATE SCR is TWO-SIDED and resolved "
            "empirically: because the single-df t shares ONE mixing variate it is "
            "the MAXIMAL-cross-block-dependence boundary, so the grouped-t's "
            "independent per-block mixing can RAISE the within-carve-out corner "
            "while DILUTING cross-block co-movement. Whether the net closes the "
            "upward nested residual 46,638.9 depends on whether the nested "
            "structure is within-block-concentrated; a WIDENING is itself "
            "informative (escalate to the vine)."
        ),
        "pre_study_grouped_t_vs_single_t": pre,
        "pre_study_disclosure": (
            "The pre-study uses a SYNTHETIC seven-driver, two-block portfolio on "
            "common random numbers; the single-df t basis shares ONE mixing "
            "variate across all drivers (same Z, same base Gamma draw), through "
            "IDENTICAL frozen margins - so the ONLY difference is the per-block "
            "tail-dependence heterogeneity. The grouped-t lifts within-carve-out "
            f"upper-tail dependence to {td['grouped_within_fin']:.3f} (vs cross-block "
            f"{td['grouped_cross']:.3f}; heterogeneity {td['grouped_heterogeneity']:+.3f}) "
            f"while the single-df t stays near-uniform across blocks "
            f"(heterogeneity {td['single_heterogeneity']:+.3f}). The homogeneous "
            f"boundary recovery is EXACT (max abs deviation "
            f"{pre['homogeneous_recovery_max_abs']:.1e}). DISCLOSED two-sided sign: "
            f"on this portfolio the cross-block dilution "
            f"({pre['cross_block_dilution_rel']:.1%} vs the single-t cross level) "
            f"dominates, so aggregate VaR99.5 moves "
            f"{pre['var_understatement_rel_at_var995']:+.1%} "
            f"({pre['aggregate_var_direction'].upper()}) - the grouped-t is a "
            "tail-dependence HETEROGENEITY lever, not a uniform tail-heaviness "
            "lever, and its aggregate effect is NOT sign-pinned (unlike the "
            "skew-t). It demonstrates the MECHANISM, not the magnitude or the "
            "sign of the real-data effect; both are quantified only at Tasks 2-3."
        ),
        "gap_analysis": [
            {
                "standard": "Solvency II Del. Reg. Art. 234; IFoA Aggregation WP (dependence on the basis used, incl. tail behaviour)",
                "requirement": "Diversification/dependence empirically justified ON THE BASIS ACTUALLY USED for capital, INCLUDING heterogeneous tail co-movement across risk types; the copula form must be adequate, not only its parameters.",
                "current_state": "Copula frozen as a SINGLE-df Student-t (df 2.9451): lambda_ij identical for EVERY pair. The carve-out block co-crashes harder within-block than across blocks - a heterogeneity the single df cannot represent.",
                "gap": "After the skew-t reconfirmation (gamma_hat ~ 0) ~91.8% of the 14.29% nested gap (6,114.9) remains copula-FORM; a single df forces uniform pairwise tail dependence and cannot separate within- from cross-block.",
                "phase28_design": "Task 2: add per-block df_g (grouped-t) on the frozen Sigma; the homogeneous boundary recovers the freeze exactly; fit df_g to realised within/cross-block co-exceedances on the pre-registered partition.",
            },
            {
                "standard": "SOA ASOP 56 3.5 (dependency structure appropriate to purpose)",
                "requirement": "The dependency structure - including the heterogeneity of tail co-movement across risk types - appropriate to the intended purpose; material structural limitations addressed where practicable.",
                "current_state": "The single-df homogeneity limitation is DISCLOSED (P27 reconfirmation, MR-015) but not remediated; the skew-t scalar did not close it.",
                "gap": "A disclosed structural limitation that dominates the residual should be attacked with the structurally indicated richer form (heterogeneous tail dependence), not a uniform parameter re-choice.",
                "phase28_design": "Grouped-t is the cheapest structured super-set: m per-block df parameters, exact nesting of the freeze, governed as a single additive copula change on a pre-registered partition.",
            },
            {
                "standard": "IA TAS M 3.2/3.6 (limitations disclosed; evidence reproducible)",
                "requirement": "Material limitations disclosed with quantification; remediation evidence reproducible with recorded config and pre-registered gates.",
                "current_state": "P27 discloses the copula-form residual and MR-015 verbatim in the report, risk register and offline UI with the bootstrap CI.",
                "gap": "Disclosure exists; the REMEDIATION (heterogeneous tail dependence) is the open item.",
                "phase28_design": "Task 3 headline gate: grouped-t 95% bootstrap CI tested against nested 46,638.9 (closure or residual RE-decomposed with the reduction vs the skew-t-reconfirmed 6,114.9 quantified); seeds/config/digests recorded; Task 4 refreshes MR-010/MR-014 and opens MR-016 for the heterogeneous-tail change.",
            },
            {
                "standard": "Solvency II Del. Reg. Art. 23 (management actions consistent with practice)",
                "requirement": "Allowance for management actions consistent with how they would be exercised - including which losses are relievable in a JOINT tail event.",
                "current_state": "The carve-out (non-cuttable) drivers - credit loss, FX/liquidity offsets - dominate the joint tail (P24T3/P26T2); a single df treats their internal co-crash the same as their co-movement with cuttable drivers.",
                "gap": "Mis-stating the WITHIN-carve-out joint tail mis-states the un-relievable carve-out losses, i.e. mis-states required capital; the direction is empirical.",
                "phase28_design": "The grouped-t lets the carve-out block carry its own (heavier) tail while relief still applies only to the cuttable component per scenario (P26T2 convention unchanged).",
            },
        ],
        "task2_acceptance_criteria": [
            "Implement the grouped-t copula (per-block df_g) on the FROZEN correlation Sigma; the single-df t is recovered EXACTLY at the homogeneous boundary (all df_g = 2.9451, single shared mixing variate; strict super-set; nested freeze)",
            f"Homogeneous-boundary EXACT-recovery check: grouped-t aggregate reproduces the single-df t aggregate to within {HOMOGENEOUS_RECOVERY_TOL:.0e} on common random numbers (archive cross-check is then exact)",
            f"Frozen-t COMPONENT read-out {FROZEN_T_COMPONENT_SCR_REFERENCE:,.1f} reproduced bit-identically BEFORE any grouped-t computation (archive cross-check)",
            f"Rank invariance: correlation matrix max|diff| <= {RHO_FROZEN_TOL} (Sigma FROZEN); the homogeneous df stays at {RANK_INVARIANCE_DF} within {DF_REMATCH_TOL}; only per-block df_g added (Art. 234; no silent re-tuning of Sigma)",
            "Margins UNCHANGED: standalone marginal capital bit-identical (the upgrade changes the COPULA only)",
            f"Block partition PRE-REGISTERED in this note: FIN/carve-out = drivers {list(FIN_BLOCK)} (credit, FX, liquidity), NON-FIN = drivers {list(NONFIN_BLOCK)}; df_g fitted to realised within/cross-block co-exceedances (no re-tuning of Sigma/margins; leakage-free)",
            f"Directional gate (DISCLOSED, NOT one-sided): grouped-t re-aggregated path-wise SCR reported vs the frozen-t component {GROUPED_T_SIGN_GATE_REFERENCE:,.1f}; the grouped-t is two-sided (within-block concentration vs cross-block dilution), so the sign is resolved empirically and disclosed, not pre-gated upward",
            "Single-df t component basis RETAINED and reported alongside as the comparison variant",
            "No gate-shopping: these gates fixed in this Task 1 note before any real-data grouped-t fit",
            "code_change ChangeRecord OWNER_REVIEW",
        ],
        "task3_acceptance_criteria": [
            f"Grouped-t margin bootstrap: >= {BOOTSTRAP_REPLICATES_GATE} replicates x {BOOTSTRAP_N_SIM_GATE:,} sims (P26T3/P27T3 pattern)",
            f"HEADLINE gate: nested path-wise reference {NESTED_PATHWISE_SCR_REFERENCE:,.1f} INSIDE the grouped-t 95% bootstrap CI (closure of the copula-form residual) - if still outside, the residual gap MUST be RE-decomposed (residual copula-form vs relief-surface) and the CHANGE vs the skew-t-reconfirmed copula-form residual {SKEWT_RECONFIRMED_COPULA_FORM_RESIDUAL_ABS:,.1f} (and the frozen-t {COPULA_FORM_RESIDUAL_ABS:,.1f}) quantified - no silent acceptance",
            "Directional diagnostic (DISCLOSED, NOT a hard gate): the grouped-t-vs-single-t nested-gap change on common random numbers is reported with its sign; a WIDENING is informative (the residual is not within-block-concentrated -> vine escalation) and is documented, not gate-failed",
            f"Bootstrap SE <= {BOOTSTRAP_SE_GATE:.0%} of the mean SCR",
            "Idempotent re-run digest-identical; seeds/config recorded",
            "methodology_change ChangeRecord OWNER_REVIEW",
        ],
        "task4_acceptance_criteria": [
            "Tail diagnostics on the grouped-t basis: within-block vs cross-block upper/lower tail dependence (the heterogeneity is the headline); grouped-vs-single and grouped-vs-nested deltas at VaR/ES/SCR",
            f"MR-010 / MR-014 refreshed if the grouped-t SCR moves more than {REAGG_MATERIALITY_DISCLOSURE_THRESHOLD:.0%} from the frozen-t component read-out (disclosure trigger, not pass/fail); open {NEW_RISK_ID} for the heterogeneous-tail-dependence change",
            f"Rank invariance re-verified: Sigma frozen; homogeneous df {RANK_INVARIANCE_DF}; only per-block df_g added (no silent re-tuning)",
            "Reproducibility: seeds, config, digests recorded; assumption_change/governance ChangeRecord OWNER_REVIEW",
        ],
        "task5_plan": (
            "Offline-UI propagation (ui_data.json contract 1.9.0 -> 1.10.0 ADDITIVE; "
            "grouped-t panel: grouped-t-vs-single-t-vs-nested SCR comparison, "
            "within-block vs cross-block tail-dependence heterogeneity, bootstrap "
            "CI closure/re-decomposition read-out, MR-016, gates) + PHASE 28 "
            "documentation; UI consumes ONLY model-output JSON, zero-install."
        ),
        "limitations": [
            "The synthetic pre-study proves the heterogeneous-tail-dependence mechanism and the EXACT homogeneous-boundary nesting, not the magnitude or the SIGN of the real-data aggregate effect (synthetic margins; two-block partition; rank-PIT copula isolation; no per-node clip binding).",
            "The grouped-t is a HETEROGENEITY lever, not a tail-heaviness lever: because the single-df t is the maximal-cross-block-dependence boundary, the grouped-t can DILUTE cross-block co-movement and LOWER aggregate SCR - on the synthetic it does. Whether it closes the upward nested residual is an open empirical question for Tasks 2-3.",
            "If a block-homogeneous grouped-t still cannot represent the nested inner-path joint dynamics, the vine / pair-copula (Aas et al. 2009) is the general fallback (Phase 29).",
            "The block partition is a NEW modelling decision; it is pre-registered here (financial/carve-out vs non-financial) but a different partition would require its own governed note.",
            "Margins and Sigma remain the calibrated frozen values; the upgrade does not revisit the marginal calibration or the correlation (out of scope this phase).",
            "Action parameters remain educational placeholders pending credentialled practice data + independent APS X2 review.",
        ],
        "use_restrictions": grouped_t_upgrade_use_restrictions(),
        "standard_references": STANDARD_REFERENCES,
        "affected_components": AFFECTED_COMPONENTS,
    }
    return note


def _md(note: dict) -> str:
    pre = note["pre_study_grouped_t_vs_single_t"]
    v = pre["var995"]
    td = pre["tail_dependence_proxy"]
    m = note["motivation_from_phase27"]
    lines = [
        f"# {note['title'].replace(' - ', ' — ', 1)}",
        "",
        f"**Verdict: {note['verdict']}** (design note + tested helper module + synthetic heterogeneous-tail-dependence pre-study). EDUCATIONAL ONLY.",
        "",
        "## 0. Candidate selection (design-note-first discipline)",
        "",
        f"**Chosen:** {note['candidate_chosen']}.",
        "",
        f"- Vine / pair-copula: {note['candidates_not_chosen']['vine_pair_copula']}",
        f"- Heavier single pooled df: {note['candidates_not_chosen']['heavier_single_pooled_df']}",
        f"- Credentialled-data calibration: {note['candidates_not_chosen']['credentialled_data_calibration']}",
        "",
        "## 1. Problem",
        "",
        note["problem"],
        "",
        f"Archived Phase 27 motivation figures (NOT consumed by gates): {json.dumps({k: m.get(k) for k in ('nested_scr', 'frozen_t_component_scr', 'total_gap_rel_to_nested', 'skewt_gamma_hat', 'skewt_reconfirmed_copula_form_residual_abs', 'copula_form_share_of_gap', 'dependence_form_sensitivity_t_minus_g')}, default=float)}",
        "",
        "## 2. Method — grouped-t / heterogeneous tail dependence (Tasks 2-3)",
        "",
        note["method"],
        "",
        f"**Hypothesis:** {note['hypothesis']}",
        "",
        "## 3. Pre-study (synthetic heterogeneous-tail-dependence mechanism)",
        "",
        f"- Synthetic portfolio: 7 drivers, 2 blocks (FIN/carve-out {pre['config']['fin_block']} weight {pre['config']['fin_block_weight']:.2f}; NON-FIN {pre['config']['nonfin_block']}); grouped-t df_fin={pre['config']['df_fin']}, df_nonfin={pre['config']['df_nonfin']}; single-df t basis shares ONE mixing variate (df_pooled={pre['config']['df_pooled']}) on common random numbers; identical frozen margins; n_scen={pre['config']['n_scen']:,}, seed={pre['config']['seed']}",
        f"- Upper-tail dependence (p={td['level_p']}): grouped within-FIN {td['grouped_within_fin']:.3f} vs cross-block {td['grouped_cross']:.3f} (heterogeneity {td['grouped_heterogeneity']:+.3f}); single-df t within-FIN {td['single_within_fin']:.3f} vs cross {td['single_cross']:.3f} (heterogeneity {td['single_heterogeneity']:+.3f}, near-uniform)",
        f"- Cross-block dilution: grouped cross-block tail dependence is {pre['cross_block_dilution_rel']:.1%} of the single-t cross level — the single-df t is the MAXIMAL-cross-block boundary",
        f"- VaR99.5: single-t {v['single_t']:.2f}; grouped-t {v['grouped_t']:.2f} → aggregate moves {pre['var_understatement_rel_at_var995']:+.1%} ({pre['aggregate_var_direction'].upper()}) — DISCLOSED two-sided, the grouped-t is a heterogeneity lever not a tail-heaviness lever",
        f"- ES99.5 move: {pre['es_understatement_rel_at_es995']:+.1%}",
        f"- Homogeneous-boundary EXACT recovery: max abs deviation {pre['homogeneous_recovery_max_abs']:.1e} (≤ {HOMOGENEOUS_RECOVERY_TOL:.0e})",
        f"- heterogeneity_ok={pre['heterogeneity_ok']}; homogeneous_recovery_ok={pre['homogeneous_recovery_ok']}; (diagnostics) sign_ok={pre['understatement_sign_ok']}, ordering_ok={pre['ordering_ok']}; mechanism_demonstrated={pre['mechanism_demonstrated']}; digest={pre['digest']}",
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
                  f"- **Phase 28 design:** {g['phase28_design']}", ""]
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
    lines += ["", "*Generated by scripts/build_phase28_task1_design_note.py — educational model; production sign-off withheld.*", ""]
    return "\n".join(lines)


def _card(note: dict) -> str:
    pre = note["pre_study_grouped_t_vs_single_t"]
    v = pre["var995"]
    td = pre["tail_dependence_proxy"]
    return "\n".join([
        "# Grouped-t / Heterogeneous Tail-Dependence Copula — Design Card (Phase 28)",
        "",
        f"**Verdict: {note['verdict']}** (design note; implementation in Phase 28 Tasks 2-4). EDUCATIONAL ONLY.",
        "",
        "## What changes",
        "",
        "The aggregation copula gains per-block degrees of freedom (the grouped-t;",
        "Daul et al. 2003) on the FROZEN correlation Sigma. Each driver block carries",
        "its own radial mixing variate -> heterogeneous within- vs cross-block tail",
        "dependence. The homogeneous boundary (all df_g = 2.9451, single shared mixing)",
        "recovers the single-df t EXACTLY (strict super-set; nested freeze).",
        "Margins and Sigma are UNCHANGED — only the per-block tail dependence moves.",
        "",
        "## Why (quantified motivation + synthetic pre-study)",
        "",
        f"- Phase 27 RECONFIRMATION: the skew-t scalar pinned at gamma_hat ~ {SKEWT_GAMMA_HAT:.1e}; the copula-form residual fell only {COPULA_FORM_RESIDUAL_ABS:,.1f} → {SKEWT_RECONFIRMED_COPULA_FORM_RESIDUAL_ABS:,.1f} (0.09%) — NOT a radial-asymmetry effect (MR-015 OPEN)",
        f"- The single-df t imposes ONE tail-dependence level on EVERY pair; the nested joint loss has within-block >> cross-block tail co-movement — no single df can represent that",
        f"- Synthetic pre-study (common random numbers): grouped-t within-FIN upper-tail dependence {td['grouped_within_fin']:.3f} vs cross-block {td['grouped_cross']:.3f} (single-df t near-uniform {td['single_within_fin']:.3f}/{td['single_cross']:.3f})",
        f"- DISCLOSED two-sided sign: cross-block dilution dominates here, VaR99.5 {v['single_t']:.2f} → {v['grouped_t']:.2f} ({pre['var_understatement_rel_at_var995']:+.1%}); the grouped-t is a HETEROGENEITY lever, not a tail-heaviness lever",
        f"- Homogeneous-boundary EXACT recovery (max abs dev {pre['homogeneous_recovery_max_abs']:.1e}); reproducibility digest: {pre['digest']}",
        "",
        "## Pre-registered gates (s5 of the design note)",
        "",
        "- Strict super-set: homogeneous boundary reproduces the single-df t EXACTLY; Sigma (max|diff| ≤ 1e-12) FROZEN; homogeneous df 2.9451 (tol 1e-4); margins bit-identical",
        f"- Archive cross-check: frozen-t component read-out {FROZEN_T_COMPONENT_SCR_REFERENCE:,.1f} reproduced bit-identically",
        f"- Pre-registered partition: FIN/carve-out {list(FIN_BLOCK)} vs NON-FIN {list(NONFIN_BLOCK)}; df_g fitted leakage-free to within/cross-block co-exceedances",
        f"- Directional gate DISCLOSED (not one-sided): grouped-t SCR reported vs frozen-t component {GROUPED_T_SIGN_GATE_REFERENCE:,.1f}; two-sided, resolved empirically",
        f"- HEADLINE (Task 3): nested {NESTED_PATHWISE_SCR_REFERENCE:,.1f} INSIDE the grouped-t 95% bootstrap CI, or residual RE-decomposed + change vs {SKEWT_RECONFIRMED_COPULA_FORM_RESIDUAL_ABS:,.1f} quantified; a widening flags the vine escalation",
        f"- MR-010/MR-014 refresh trigger: grouped-t-vs-frozen SCR delta > 1%; open {NEW_RISK_ID} for the heterogeneous-tail change",
        "",
        "## Out of scope / residuals (disclosed)",
        "",
        "- Vine / pair-copula (Aas et al. 2009): general fallback if a block-homogeneous grouped-t is insufficient (Phase 29)",
        "- Block partition is a pre-registered modelling decision; alternatives need their own governed note",
        "- Credentialled calibration: standing human-action blocker",
        "",
        "*Generated by scripts/build_phase28_task1_design_note.py — educational model; production sign-off withheld.*",
        "",
    ])


def apply_governance(store: GovernanceStore, note: dict) -> dict:
    actor = "Phase28Task1DesignNote"
    phase = "Phase 28: Grouped-t / Heterogeneous Tail-Dependence"
    if any(r.title == CHANGE_TITLE for r in store.change_records):
        return {"added": False, "reason": "already applied (idempotent)"}
    pre = note["pre_study_grouped_t_vs_single_t"]
    td = pre["tail_dependence_proxy"]
    rec = ChangeRecord.create(
        title=CHANGE_TITLE,
        description=(
            "Design note for Phase 28: grouped-t / heterogeneous tail-dependence "
            "copula - per-block degrees of freedom (Daul et al. 2003) on the "
            "FROZEN correlation Sigma, with the homogeneous boundary (all df_g = "
            "2.9451, single shared mixing variate) recovering the governed "
            "single-df t EXACTLY (new tested helper module "
            "par_model_v2/projection/grouped_t_upgrade.py: synthetic grouped-t vs "
            "single-t pre-study on common random numbers, pre-registered gate "
            "constants and block partition, use restrictions). Carries forward the "
            "Phase 27 RECONFIRMATION (skew-t gamma_hat ~ 0; copula-form residual "
            "6,120.2 -> 6,114.9, 0.09%, NOT a radial-asymmetry effect; MR-015 "
            "OPEN). Demonstrates the heterogeneous within-block >> cross-block "
            "tail dependence a single pooled df cannot represent and EXACT "
            "homogeneous-boundary nesting; DISCLOSES the two-sided aggregate sign "
            "(cross-block dilution can lower aggregate SCR). Candidate selection "
            "rationale recorded (vine deferred as general fallback; heavier single "
            "df rejected; credentialled calibration blocked). FIXED pre-registered "
            "acceptance gates for Tasks 2-4 including exact homogeneous-boundary "
            "nesting and the pre-registered block partition."
        ),
        change_type="governance_change",
        affected_components=AFFECTED_COMPONENTS,
        standard_references=STANDARD_REFERENCES,
        before_snapshot={
            "copula_form": (
                "single-df Student-t (df 2.9451, Sigma frozen); lambda_ij identical "
                "for every pair; nested truth 46,638.9 above the frozen-t component "
                "39,975.7 with ~91.8% of the gap copula-FORM after the skew-t "
                "reconfirmation (6,114.9; gamma_hat ~ 0; MR-015 OPEN)"
            ),
        },
        after_snapshot={
            "design": "grouped-t per-block df on the frozen Sigma; homogeneous boundary nests the freeze exactly (Task 2); bootstrap closure/re-decomposition vs nested (Task 3); within/cross-block tail diagnostics + MR refresh + MR-016 (Task 4); UI 1.9.0 -> 1.10.0 (Task 5)",
            "pre_study": {
                "grouped_within_fin_vs_cross": [td["grouped_within_fin"], td["grouped_cross"]],
                "grouped_heterogeneity": td["grouped_heterogeneity"],
                "single_heterogeneity": td["single_heterogeneity"],
                "cross_block_dilution_rel": pre["cross_block_dilution_rel"],
                "var_understatement_rel_at_var995": pre["var_understatement_rel_at_var995"],
                "aggregate_var_direction": pre["aggregate_var_direction"],
                "homogeneous_recovery_max_abs": pre["homogeneous_recovery_max_abs"],
                "heterogeneity_ok": pre["heterogeneity_ok"],
            },
            "verdict": note["verdict"] + " (design note)",
        },
        impact_assessment=(
            "No numeric capital output changed this cycle (design note + additive "
            "helper module only). Fixes non-gate-shopped acceptance criteria for "
            "Tasks 2-4 BEFORE any real-data grouped-t fit; pre-registers the block "
            "partition and the HEADLINE closure/re-decomposition criterion (nested "
            "inside the grouped-t 95% CI, or residual re-decomposed with the change "
            "vs the skew-t-reconfirmed 6,114.9 quantified). DISCLOSES up front that "
            "the grouped-t is a tail-dependence HETEROGENEITY lever whose aggregate "
            "effect is two-sided (the synthetic shows cross-block dilution lowering "
            "aggregate SCR), so the directional question is resolved empirically and "
            "a widening flags the vine escalation. The upgrade is a strict super-set "
            "of the governed copula (homogeneous boundary exact), so the freeze and "
            "all prior read-outs are preserved. Educational classification retained; "
            "production sign-off withheld pending credentialled data + APS X2 review."
        ),
        author=actor, phase=phase,
        quantitative_impact=(
            f"Synthetic pre-study: grouped-t within-carve-out upper-tail dependence "
            f"{td['grouped_within_fin']:.3f} vs cross-block {td['grouped_cross']:.3f} "
            f"(single-df t near-uniform {td['single_within_fin']:.3f}/"
            f"{td['single_cross']:.3f}); cross-block dilution "
            f"{pre['cross_block_dilution_rel']:.1%}; aggregate VaR99.5 "
            f"{pre['var_understatement_rel_at_var995']:+.1%} "
            f"({pre['aggregate_var_direction']}); homogeneous-boundary recovery "
            f"max abs dev {pre['homogeneous_recovery_max_abs']:.1e}. No capital "
            f"figures changed. Archived motivation: copula-form residual "
            f"{SKEWT_RECONFIRMED_COPULA_FORM_RESIDUAL_ABS:,.1f} (~91.8% of the "
            f"14.29% nested gap, P27T3 reconfirmation)."
        ),
    )
    rec.submit_for_peer_review(actor=actor, comments="Design note + new unit tests PASS; no existing module touched; homogeneous boundary nests the governed freeze exactly; two-sided sign disclosed.")
    rec.submit_to_owner(actor=actor, comments="Owner review: synthetic-mechanism scope + heterogeneous-tail remediation path documented; two-sided aggregate sign disclosed; sign-off withheld.")
    store.add_change_record(rec)
    store.audit_trail.append(AuditEntry.governance(
        actor=actor, phase=phase,
        event="ChangeRecord opened (OWNER_REVIEW) - Phase 28 Task 1 design note (grouped-t / heterogeneous tail-dependence copula)",
        details={"record_id": rec.record_id, "change_type": "governance_change",
                 "status": rec.status.value, "affected_components": AFFECTED_COMPONENTS},
    ))
    return {"added": True, "record_id": rec.record_id, "status": rec.status.value}


def main(use_governance: bool = False, fast: bool = False) -> dict:
    note = build_design_note(fast=fast)
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(JSON_PATH, "w", encoding="utf-8") as fh:
        json.dump(note, fh, indent=1, default=float)
    with open(MD_PATH, "w", encoding="utf-8") as fh:
        fh.write(_md(note))
    with open(CARD_PATH, "w", encoding="utf-8") as fh:
        fh.write(_card(note))
    out = {"verdict": note["verdict"], "json": JSON_PATH, "md": MD_PATH, "card": CARD_PATH}
    if use_governance:
        store = GovernanceStore.from_json(open(GOV_PATH).read())
        gov = apply_governance(store, note)
        if gov.get("added"):
            with open(GOV_PATH, "w", encoding="utf-8") as fh:
                fh.write(store.to_json())
        gov["audit_entries"] = len(store.audit_trail.all())
        gov["audit_integrity_ok"] = store.audit_trail.verify_all()
        gov["change_records_total"] = len(store.change_records)
        out["governance"] = gov
    return out


if __name__ == "__main__":
    res = main(use_governance="--governance" in sys.argv, fast="--fast" in sys.argv)
    print(json.dumps(res, indent=1, default=str))
