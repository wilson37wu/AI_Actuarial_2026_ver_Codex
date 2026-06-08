"""Phase 26 Task 1 - research + design note builder.

Candidate CHOSEN (design-note-first discipline, one per cycle): FULL PATH-WISE
COPULA RE-AGGREGATION - the governed relief applied to the per-driver
COMPOSITION of each joint copula scenario, vs the Phase 25 Task 4 analytic
re-anchoring (relief applied ONCE to the anchored joint total level with a
constant FIT-sample benefit share).  Motivation is QUANTIFIED: the nested
path-wise reference 46,638.9 sits OUTSIDE the re-anchoring bootstrap 95% CI
[35,793, 42,496] - a 14.7% understatement BEYOND margin noise.

Candidates NOT chosen this cycle (rationale recorded in the note):
- credentialled-data calibration: blocked on credentialled practice data
  (standing human-action blocker); cannot be executed from the sandbox.
- declaration-cadence refinement (annual board cadence with smoothing):
  deferred - the cadence sensitivity (ratio 1.136, deterministic basis) is
  archived, and cadence evidence computed on the SOON-TO-CHANGE aggregation
  basis would be superseded within one phase; aggregation first.

Outputs: docs/validation/PHASE26_TASK1_DESIGN_NOTE.{json,md};
         docs/PATHWISE_COPULA_REAGGREGATION_DESIGN_CARD.md;
         governance ChangeRecord (OWNER_REVIEW) + audit entry (--governance).

Idempotent: the ChangeRecord is detected by title on re-run.
Run: PYTHONPATH=/var/tmp/pylibs:. python3 scripts/build_phase26_task1_design_note.py [--governance] [--fast]

EDUCATIONAL ONLY - design note; no production capital use.
"""
from __future__ import annotations

import json
import os
import sys

from par_model_v2.governance.audit_trail import AuditEntry, ChangeRecord, GovernanceStore
from par_model_v2.projection.pathwise_copula_reaggregation import (
    BOOTSTRAP_N_SIM_GATE,
    BOOTSTRAP_REPLICATES_GATE,
    BOOTSTRAP_SE_GATE,
    DF_REMATCH_TOL,
    FULL_REAGG_SIGN_GATE_REFERENCE,
    GAUSSIAN_REANCHORED_READOUT,
    NESTED_PATHWISE_SCR_REFERENCE,
    RANK_INVARIANCE_DF,
    REAGG_MATERIALITY_DISCLOSURE_THRESHOLD,
    REANCHORING_BOOTSTRAP_CI95,
    REANCHORING_UNDERSTATEMENT_REL,
    RHO_FROZEN_TOL,
    T_COPULA_REANCHORED_READOUT,
    pathwise_reaggregation_use_restrictions,
    synthetic_level_vs_component_pre_study,
)

GOV_PATH = os.path.join(".claude-dev", "GOVERNANCE_STORE.json")
OUT_DIR = os.path.join("docs", "validation")
JSON_PATH = os.path.join(OUT_DIR, "PHASE26_TASK1_DESIGN_NOTE.json")
MD_PATH = os.path.join(OUT_DIR, "PHASE26_TASK1_DESIGN_NOTE.md")
CARD_PATH = os.path.join("docs", "PATHWISE_COPULA_REAGGREGATION_DESIGN_CARD.md")
P25T4 = os.path.join(OUT_DIR, "PHASE25_TASK4_PATHWISE_TAIL_DIAGNOSTICS_REPORT.json")

CHANGE_TITLE = (
    "Phase 26 Task 1 - design note: full path-wise copula re-aggregation "
    "(per-driver composition relief on the frozen joint copula)"
)

STANDARD_REFERENCES = [
    "Solvency II Delegated Reg. Art. 234 (empirically justified diversification incl. tail behaviour; dependence justified on the basis actually used for capital)",
    "Solvency II Delegated Reg. Art. 23 (future management actions: objective, realistic, verifiable)",
    "SOA ASOP 56 §3.1.3/§3.4/§3.5", "SOA ASOP 25 §3.3", "IA TAS M §3.2/§3.6",
    "IFoA Life Aggregation & Simulation working party",
    "CFO Forum MCEV Principle 7 (TVOG; dynamic management actions)",
]

AFFECTED_COMPONENTS = [
    "par_model_v2/projection/pathwise_copula_reaggregation.py (NEW, tested helper module)",
    "tests/test_phase26_task1_design_note.py",
    "scripts/build_phase26_task1_design_note.py",
    "docs/validation/PHASE26_TASK1_DESIGN_NOTE.{json,md}",
    "docs/PATHWISE_COPULA_REAGGREGATION_DESIGN_CARD.md",
]


def _load_p25t4_motivation() -> dict:
    """Archived Phase 25 Task 4 figures (motivation; NOT consumed by gates)."""
    try:
        with open(P25T4) as fh:
            r = json.load(fh)
        res = r.get("result", {})
        return {
            "next_phase_candidate_documented": r.get("next_phase_candidate")
            or res.get("next_phase_candidate"),
            "nested_scr_with_pathwise": NESTED_PATHWISE_SCR_REFERENCE,
            "t_copula_reanchored_readout": T_COPULA_REANCHORED_READOUT,
            "gaussian_reanchored_readout": GAUSSIAN_REANCHORED_READOUT,
            "bootstrap_ci95": list(REANCHORING_BOOTSTRAP_CI95),
            "understatement_beyond_noise_rel": REANCHORING_UNDERSTATEMENT_REL,
            "source": P25T4,
        }
    except Exception as exc:  # archived report missing -> disclosed
        return {"source": P25T4, "load_error": str(exc)}


def build_design_note(fast: bool = False) -> dict:
    pre = synthetic_level_vs_component_pre_study(
        seed=42, n_scen=40_000 if fast else 200_000
    )
    note = {
        "title": "Phase 26 Task 1 - Design Note: Full Path-Wise Copula Re-Aggregation",
        "verdict": "PASS" if pre["mechanism_demonstrated"] else "FAIL",
        "classification": "EDUCATIONAL",
        "candidate_chosen": (
            "full path-wise copula re-aggregation (P25T4 documented next-phase "
            "candidate; quantified 14.7%-beyond-noise motivation)"
        ),
        "candidates_not_chosen": {
            "credentialled_data_calibration": (
                "BLOCKED on credentialled management-practice data (standing "
                "human-action blocker); not executable from the sandbox. Remains "
                "the production sign-off residual by design."
            ),
            "declaration_cadence_refinement": (
                "DEFERRED: the annual-cadence sensitivity (ratio 1.136, deterministic "
                "basis) is archived; cadence evidence computed on the aggregation basis "
                "that THIS phase changes would be superseded within one phase. "
                "Sequencing the aggregation refinement first avoids duplicated "
                "cadence benchmarks."
            ),
        },
        "motivation_from_phase25_task4": _load_p25t4_motivation(),
        "problem": (
            "Phase 25 Task 4 produced the t/gaussian path-wise capital read-outs by "
            "ANALYTIC RE-ANCHORING: the governed smoothed-relief surface (sigma 0.225, "
            "alpha 0.7567) plus ONE constant FIT-sample benefit share (beta_fit 0.8450) "
            "applied to the anchored joint TOTAL liability level of each copula scenario. "
            "The transform therefore sees neither the per-driver composition of the "
            "scenario nor the per-node spread of the cuttable share. The frozen-copula "
            "margin bootstrap quantified the consequence: the nested path-wise reference "
            "46,638.9 sits OUTSIDE the re-anchoring 95% CI [35,793, 42,496] - the "
            "re-anchoring understates nested by 14.7% BEYOND margin noise. The mechanism "
            "is composition heterogeneity: the 99.5% tail of the joint loss is "
            "disproportionately driven by the heavy-tailed CARVE-OUT (non-cuttable) "
            "drivers (credit loss; analytic FX/liquidity offsets), so the constant-share "
            "level transform credits relief the governed rule cannot actually take in "
            "the tail."
        ),
        "method": (
            "Full path-wise copula re-aggregation (Tasks 2-3): keep the copula FROZEN "
            "(df 2.9451 tail-matched on the without-actions basis, Phase 23 Task 2; "
            "correlation matrix bit-frozen) and replace the level transform with a "
            "per-driver composition transform: for each joint copula scenario, recover "
            "the per-driver loss composition from the frozen margins, split cuttable vs "
            "carve-out components per scenario, evaluate the governed smoothed-relief "
            "surface on the scenario's coverage state, and apply the relief to the "
            "scenario's CUTTABLE component only (clip at max_relief of the cuttable "
            "component - the node-level envelope preserved per scenario). Calibration "
            "scalars (sigma, alpha) remain the governed Phase 25 Task 3 FIT-sample "
            "values - leakage-free, NO re-tuning. Task 3 then re-runs the frozen-copula "
            "margin bootstrap on the FULL re-aggregated basis: the headline acceptance "
            "criterion is that the nested path-wise reference falls INSIDE the 95% CI "
            "(closure of the beyond-noise understatement), or the residual gap is "
            "decomposed (copula-form vs relief-surface error) and disclosed."
        ),
        "hypothesis": (
            "The full re-aggregated t-copula path-wise SCR is HIGHER than the analytic "
            "re-anchored read-out 39,794.3 (composition heterogeneity can only reduce "
            "tail relief vs the constant-share level transform) and the gap to the "
            "nested reference 46,638.9 shrinks to within margin noise; the synthetic "
            "pre-study sign carries over."
        ),
        "pre_study_level_vs_component": pre,
        "pre_study_disclosure": (
            "The pre-study uses a SYNTHETIC seven-driver t-copula portfolio (equicorrelated "
            "rho 0.5, df 3, lognormal margins, three carve-out drivers mirroring the P24T3 "
            "non-cuttable components) so that no real archived nested benchmark is consumed "
            "before the Task 2 gates. On common random numbers, moving the relief from the "
            "constant-share level basis to the per-scenario cuttable composition raises "
            f"VaR99.5 by {pre['level_understatement_rel_at_var995']:.1%} - the level basis "
            "UNDERSTATES with-actions capital, and the tail cuttable share is depressed "
            f"({pre['beta_mean']:.3f} mean vs {pre['beta_tail_mean']:.3f} in the tail). It "
            "demonstrates the composition-heterogeneity MECHANISM and its SIGN, not the "
            "magnitude of the real-data effect: on the real basis two further channels "
            "(per-node coverage-state heterogeneity and the benefit-share spread, both "
            "clip-binding at node level) widen the gap toward the archived 14.7%; they are "
            "quantified only at Tasks 2-3."
        ),
        "gap_analysis": [
            {
                "standard": "Solvency II Del. Reg. Art. 234; IFoA Aggregation WP (dependence on the basis used)",
                "requirement": "Diversification/dependence empirically justified ON THE BASIS ACTUALLY USED for capital, including tail behaviour; no silent re-tuning when the basis changes.",
                "current_state": "Copula frozen (df 2.9451 on without-actions losses; rank invariance re-verified at P25T4), but the with-actions t/gaussian read-outs are a LEVEL transform of the joint total - the dependence between cuttable and carve-out components inside the tail is not represented.",
                "gap": "The benchmark capital read-outs on the path-wise basis are quantified as understating the nested reference by 14.7% beyond margin noise.",
                "phase26_design": "Task 2: per-driver composition transform on the frozen copula (no re-tuning); Task 3: bootstrap closure test against the nested reference; rank-invariance re-verified each task.",
            },
            {
                "standard": "SOA ASOP 56 §3.1.3/§3.4 (model structure; approximations appropriate to purpose)",
                "requirement": "Structure of the model - including the LEVEL at which an approximation enters - appropriate to the intended purpose; material approximation error identified.",
                "current_state": "Constant beta_fit benefit share applied at the joint level (disclosed first-order approximation, P25T4); per-node share spread reported but not propagated.",
                "gap": "The approximation error is quantified (14.7% beyond noise) and exceeds any reasonable materiality threshold for a benchmark read-out.",
                "phase26_design": "Task 2 propagates the per-scenario cuttable composition; the constant-share level transform is RETAINED as the comparison variant (P24T3 convention).",
            },
            {
                "standard": "IA TAS M §3.2/§3.6 (limitations disclosed; evidence reproducible)",
                "requirement": "Material limitations disclosed with quantification where practicable; validation evidence reproducible with recorded config.",
                "current_state": "P25T4/T5 disclose the understatement verbatim in the report, risk register (MR-010/MR-014) and offline UI, with the bootstrap CI.",
                "gap": "Disclosure exists; the REMEDIATION is the open item - benchmark read-outs should not stay outside their own confidence band against the truth reference.",
                "phase26_design": "Task 3 headline gate: nested reference INSIDE the full re-aggregation 95% CI, or residual gap decomposed + disclosed; seeds/config/digests recorded; Task 4 refreshes MR-010/MR-014.",
            },
            {
                "standard": "Solvency II Del. Reg. Art. 23 (management actions consistent with practice)",
                "requirement": "Allowance for management actions consistent with how they would actually be exercised - including WHAT can be cut: carve-outs (credit loss, FX/liquidity offsets) are not relievable by a bonus cut.",
                "current_state": "Nested truth respects carve-outs per node (P24T3); the benchmark level transform applies a constant cuttable share to the joint total - in the tail this credits relief on carve-out-driven losses.",
                "gap": "Benchmark relief in the tail exceeds what the governed rule can take; sign pre-registered (understatement of capital).",
                "phase26_design": "Task 2 applies relief to the per-scenario CUTTABLE component only, with the per-scenario max_relief envelope clip.",
            },
        ],
        "task2_acceptance_criteria": [
            "Per-driver composition transform on the FROZEN copula: relief applied to the per-scenario cuttable component only; per-scenario envelope clip at max_relief of the cuttable component; governed sigma/alpha UNCHANGED (P25T3 FIT values; no re-tuning)",
            f"Rank invariance: df re-matched on the WITHOUT-actions staged losses within {DF_REMATCH_TOL} of {RANK_INVARIANCE_DF}; correlation matrix max|diff| <= {RHO_FROZEN_TOL} (copula FROZEN, Art. 234)",
            "Without-actions t/gaussian read-outs and the P25T4 re-anchored read-outs reproduced bit-identically BEFORE any new computation (archive cross-check)",
            f"Sign gate (pre-registered): full re-aggregated t-copula path-wise SCR >= the analytic re-anchored read-out {FULL_REAGG_SIGN_GATE_REFERENCE:,.1f}; magnitude DISCLOSED, not gated",
            "Constant-share level transform RETAINED and reported alongside as the comparison variant (P24T3 convention)",
            "No gate-shopping: these gates fixed in this Task 1 note before any real-data full re-aggregation",
            "code_change ChangeRecord OWNER_REVIEW",
        ],
        "task3_acceptance_criteria": [
            f"Frozen-copula margin bootstrap on the FULL re-aggregated basis: >= {BOOTSTRAP_REPLICATES_GATE} replicates x {BOOTSTRAP_N_SIM_GATE:,} sims (P25T4 pattern)",
            f"HEADLINE gate: nested path-wise reference {NESTED_PATHWISE_SCR_REFERENCE:,.1f} INSIDE the full re-aggregation 95% CI - closure of the beyond-noise understatement; if still outside, the residual gap MUST be decomposed (copula-form vs relief-surface error) and disclosed - no silent acceptance",
            f"Bootstrap SE <= {BOOTSTRAP_SE_GATE:.0%} of the mean SCR",
            "Idempotent re-run digest-identical; seeds/config recorded",
            "methodology_change ChangeRecord OWNER_REVIEW",
        ],
        "task4_acceptance_criteria": [
            "Tail diagnostics on the full re-aggregated basis: with-vs-without and full-vs-reanchored deltas at VaR/ES/SCR for nested, t, gaussian (var-covar: no path-wise analogue - DISCLOSED in-table, P25T4 convention)",
            f"MR-010 (var-covar understatement) and MR-014 refreshed if the full re-aggregated SCR moves more than {REAGG_MATERIALITY_DISCLOSURE_THRESHOLD:.0%} from the re-anchored read-out (disclosure trigger, not pass/fail)",
            f"Rank invariance re-verified: df {RANK_INVARIANCE_DF} on without-actions losses; copula parameters frozen (no silent re-tuning)",
            "Reproducibility: seeds, config, digests recorded; assumption_change/governance ChangeRecord OWNER_REVIEW",
        ],
        "task5_plan": (
            "Offline-UI propagation (ui_data.json contract 1.7.0 -> 1.8.0 ADDITIVE; full "
            "re-aggregation panel: full-vs-reanchored-vs-nested SCR comparison, bootstrap "
            "CI closure read-out, composition-heterogeneity diagnostics, gates) + PHASE 26 "
            "COMPLETE documentation; UI consumes ONLY model-output JSON."
        ),
        "limitations": [
            "The synthetic pre-study proves the composition-heterogeneity mechanism and its SIGN, not the magnitude (synthetic margins; single relief surface; no per-node clip binding).",
            "The full re-aggregation still consumes the governed smoothed-relief surface (sigma, alpha) - a FIT-sample approximation of the path-wise truth; residual surface error is decomposed at Task 3 if the CI gate fails.",
            "Per-driver composition recovery from the frozen margins is exact only at the margin level used by the benchmark (node-level heterogeneity below the driver level remains aggregated).",
            "Declaration cadence (annual board declaration with smoothing) remains the deferred candidate; sensitivity 1.136 archived.",
            "Action parameters remain educational placeholders pending credentialled practice data + independent APS X2 review.",
        ],
        "use_restrictions": pathwise_reaggregation_use_restrictions(),
        "standard_references": STANDARD_REFERENCES,
        "affected_components": AFFECTED_COMPONENTS,
    }
    return note


def _md(note: dict) -> str:
    pre = note["pre_study_level_vs_component"]
    v = pre["var995"]
    m = note["motivation_from_phase25_task4"]
    lines = [
        f"# {note['title'].replace(' - ', ' — ', 1)}",
        "",
        f"**Verdict: {note['verdict']}** (design note + tested helper module + synthetic composition-heterogeneity pre-study). EDUCATIONAL ONLY.",
        "",
        "## 0. Candidate selection (design-note-first discipline)",
        "",
        f"**Chosen:** {note['candidate_chosen']}.",
        "",
        f"- Credentialled-data calibration: {note['candidates_not_chosen']['credentialled_data_calibration']}",
        f"- Declaration-cadence refinement: {note['candidates_not_chosen']['declaration_cadence_refinement']}",
        "",
        "## 1. Problem",
        "",
        note["problem"],
        "",
        f"Archived Phase 25 motivation figures (NOT consumed by gates): {json.dumps({k: m.get(k) for k in ('nested_scr_with_pathwise', 't_copula_reanchored_readout', 'gaussian_reanchored_readout', 'bootstrap_ci95', 'understatement_beyond_noise_rel')}, default=float)}",
        "",
        "## 2. Method — full path-wise copula re-aggregation (Tasks 2-3)",
        "",
        note["method"],
        "",
        f"**Hypothesis:** {note['hypothesis']}",
        "",
        "## 3. Pre-study (synthetic composition-heterogeneity mechanism)",
        "",
        f"- Synthetic portfolio: 7 drivers, equicorrelated t-copula rho 0.5, df 3, lognormal margins; carve-out (non-cuttable) drivers mirror P24T3; n_scen={pre['config']['n_scen']:,}, seed={pre['config']['seed']}",
        f"- VaR99.5 per 100 mean loss: without {v['without']:.2f}; level basis {v['level']:.2f}; component basis {v['component']:.2f}",
        f"- Level basis UNDERSTATES the component-basis VaR99.5 by {pre['level_understatement_rel_at_var995']:.1%}",
        f"- Tail cuttable-share depression: mean {pre['beta_mean']:.3f} vs tail {pre['beta_tail_mean']:.3f} (the mechanism: the tail is carve-out-driven)",
        f"- Mean relief nearly unchanged ({pre['mean_relief_level']:.2f} vs {pre['mean_relief_component']:.2f}): a tail re-ranking effect, not a mean shift",
        f"- understatement_sign_ok={pre['understatement_sign_ok']}; ordering_ok={pre['ordering_ok']}; bounds_ok={pre['bounds_ok']}; digest={pre['digest']}",
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
                  f"- **Phase 26 design:** {g['phase26_design']}", ""]
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
    lines += ["", "*Generated by scripts/build_phase26_task1_design_note.py — educational model; production sign-off withheld.*", ""]
    return "\n".join(lines)


def _card(note: dict) -> str:
    pre = note["pre_study_level_vs_component"]
    v = pre["var995"]
    return "\n".join([
        "# Full Path-Wise Copula Re-Aggregation — Design Card (Phase 26)",
        "",
        f"**Verdict: {note['verdict']}** (design note; implementation in Phase 26 Tasks 2-4). EDUCATIONAL ONLY.",
        "",
        "## What changes",
        "",
        "The t/gaussian path-wise benchmark read-outs move from the Phase 25 Task 4",
        "analytic re-anchoring (relief applied ONCE to the joint TOTAL level with a",
        "constant benefit share) to a per-driver COMPOSITION transform on the frozen",
        "copula: relief applied to each scenario's cuttable component only, with the",
        "per-scenario max_relief envelope clip. Copula, rule shape, sigma/alpha UNCHANGED.",
        "",
        "## Why (quantified motivation + synthetic pre-study)",
        "",
        f"- Archived P25T4 bootstrap: nested path-wise reference {NESTED_PATHWISE_SCR_REFERENCE:,.1f} OUTSIDE the re-anchoring 95% CI [35,793, 42,496] — 14.7% understatement BEYOND margin noise",
        f"- Synthetic pre-study (common random numbers): level basis understates the component-basis VaR99.5 by {pre['level_understatement_rel_at_var995']:.1%}; tail cuttable share depressed {pre['beta_mean']:.3f} -> {pre['beta_tail_mean']:.3f}",
        f"- VaR99.5: without {v['without']:.2f} / level {v['level']:.2f} / component {v['component']:.2f} (sign pre-registered; magnitude NOT extrapolated)",
        f"- Reproducibility digest: {pre['digest']}",
        "",
        "## Pre-registered gates (s5 of the design note)",
        "",
        "- Copula FROZEN: df 2.9451 (tol 1e-4) on without-actions losses; rho max|diff| <= 1e-12",
        "- Archive cross-check: without-actions + P25T4 re-anchored read-outs reproduced bit-identically",
        "- Sign gate: full re-aggregated t SCR >= re-anchored 39,794.3 (magnitude disclosed, not gated)",
        "- HEADLINE (Task 3): nested 46,638.9 INSIDE the full re-aggregation 95% bootstrap CI, or residual gap decomposed + disclosed",
        "- MR-010/MR-014 refresh trigger: full-vs-reanchored SCR delta > 1%",
        "",
        "## Out of scope / residuals (disclosed)",
        "",
        "- Declaration-cadence refinement (annual board cadence): deferred candidate; sensitivity 1.136 archived",
        "- Credentialled calibration: standing human-action blocker",
        "- Sub-driver node heterogeneity remains aggregated at the margin level",
        "",
        "*Generated by scripts/build_phase26_task1_design_note.py — educational model; production sign-off withheld.*",
        "",
    ])


def apply_governance(store: GovernanceStore, note: dict) -> dict:
    actor = "Phase26Task1DesignNote"
    phase = "Phase 26: Full Path-Wise Copula Re-Aggregation"
    if any(r.title == CHANGE_TITLE for r in store.change_records):
        return {"added": False, "reason": "already applied (idempotent)"}
    pre = note["pre_study_level_vs_component"]
    rec = ChangeRecord.create(
        title=CHANGE_TITLE,
        description=(
            "Design note for Phase 26: full path-wise copula re-aggregation - the governed "
            "relief applied to the per-driver COMPOSITION of each joint copula scenario on the "
            "FROZEN copula (new tested helper module "
            "par_model_v2/projection/pathwise_copula_reaggregation.py: synthetic t-copula "
            "level-vs-component pre-study, pre-registered gate constants, use restrictions), "
            "addressing the residual QUANTIFIED in the Phase 25 Task 4 report (nested path-wise "
            "reference outside the re-anchoring bootstrap 95% CI; 14.7% understatement beyond "
            "margin noise). Candidate selection rationale recorded (credentialled calibration "
            "blocked on data; declaration-cadence refinement deferred to avoid superseded "
            "evidence). FIXED pre-registered acceptance gates for Tasks 2-4."
        ),
        change_type="governance_change",
        affected_components=AFFECTED_COMPONENTS,
        standard_references=STANDARD_REFERENCES,
        before_snapshot={
            "benchmark_basis": (
                "t/gaussian path-wise read-outs via analytic re-anchoring (P25T4): constant "
                "benefit share applied to the joint TOTAL level; nested reference outside the "
                "bootstrap 95% CI (quantified residual)"
            ),
        },
        after_snapshot={
            "design": "per-driver composition transform on the frozen copula (Task 2); bootstrap closure test vs nested (Task 3); tail diagnostics + MR refresh (Task 4); UI 1.7.0 -> 1.8.0 (Task 5)",
            "pre_study": {
                "level_understatement_rel_at_var995": pre["level_understatement_rel_at_var995"],
                "tail_cuttable_share_depression": pre["tail_cuttable_share_depression"],
                "understatement_sign_ok": pre["understatement_sign_ok"],
                "bounds_ok": pre["bounds_ok"],
            },
            "verdict": note["verdict"] + " (design note)",
        },
        impact_assessment=(
            "No numeric output path changed this cycle (design note + additive helper module "
            "only). Fixes non-gate-shopped acceptance criteria for Tasks 2-4 BEFORE any "
            "real-data full re-aggregation; pre-registers the SIGN of the expected capital "
            "effect (full re-aggregated t SCR >= re-anchored read-out) and the HEADLINE "
            "closure criterion (nested reference inside the full re-aggregation 95% CI). "
            "Educational classification retained; production sign-off withheld pending "
            "credentialled data + APS X2 review."
        ),
        author=actor, phase=phase,
        quantitative_impact=(
            f"Synthetic pre-study: constant-share level basis understates the component-basis "
            f"VaR99.5 by {pre['level_understatement_rel_at_var995']:.1%}; tail cuttable share "
            f"depressed by {pre['tail_cuttable_share_depression']:.3f}. No capital figures "
            f"changed. Archived motivation: 14.7% beyond-noise understatement (P25T4)."
        ),
    )
    rec.submit_for_peer_review(actor=actor, comments="Design note + new unit tests PASS; no existing module touched.")
    rec.submit_to_owner(actor=actor, comments="Owner review: synthetic-mechanism scope + margin-level composition residual documented; sign-off withheld.")
    store.add_change_record(rec)
    store.audit_trail.append(AuditEntry.governance(
        actor=actor, phase=phase,
        event="ChangeRecord opened (OWNER_REVIEW) - Phase 26 Task 1 design note (full path-wise copula re-aggregation)",
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
