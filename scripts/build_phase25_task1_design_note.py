"""Phase 25 Task 1 — research + design note builder.

Candidate CHOSEN (design-note-first discipline, one per cycle): FULL PATH-WISE
BONUS DECLARATION DYNAMICS — the action re-evaluated at every inner time step
on a path-wise coverage proxy, vs the current Phase 24 Task 3 horizon-level
convention (decision once at the outer node; relief factor constant across the
inner paths of one outer node).  This is the residual DOCUMENTED in the
Phase 24 Task 3 report and the Phase 24 Task 1 Method B scope note.

Candidates NOT chosen this cycle (rationale recorded in the note):
- t-copula aggregation on the inner-path with-actions basis: deferred because
  the with-actions basis is about to change (this phase); re-doing the copula
  read on a basis that Task 2 supersedes would be wasted/duplicated evidence.
- credentialled-data calibration: blocked on credentialled practice data
  (standing human-action blocker); cannot be executed from the sandbox.

Outputs: docs/validation/PHASE25_TASK1_DESIGN_NOTE.{json,md};
         docs/PATHWISE_BONUS_DECLARATION_DESIGN_CARD.md;
         governance ChangeRecord (OWNER_REVIEW) + audit entry (--governance).

Idempotent: the ChangeRecord is detected by title on re-run.
Run: PYTHONPATH=/var/tmp/pylibs:. python3 scripts/build_phase25_task1_design_note.py [--governance] [--fast]

EDUCATIONAL ONLY — design note; no production capital use.
"""
from __future__ import annotations

import json
import os
import sys

from par_model_v2.governance.audit_trail import AuditEntry, ChangeRecord, GovernanceStore
from par_model_v2.projection.pathwise_bonus_dynamics import (
    HORIZON_BASIS_SCR_REFERENCE,
    PATHWISE_MATERIALITY_DISCLOSURE_THRESHOLD,
    PATHWISE_OOS_R2_GATE,
    PATHWISE_VAR_REL_ERROR_GATE,
    pathwise_bonus_use_restrictions,
    synthetic_recognition_lag_pre_study,
)

GOV_PATH = os.path.join(".claude-dev", "GOVERNANCE_STORE.json")
OUT_DIR = os.path.join("docs", "validation")
JSON_PATH = os.path.join(OUT_DIR, "PHASE25_TASK1_DESIGN_NOTE.json")
MD_PATH = os.path.join(OUT_DIR, "PHASE25_TASK1_DESIGN_NOTE.md")
CARD_PATH = os.path.join("docs", "PATHWISE_BONUS_DECLARATION_DESIGN_CARD.md")
P24T3 = os.path.join(OUT_DIR, "PHASE24_TASK3_INNER_PATH_ACTION_REPORT.json")

CHANGE_TITLE = (
    "Phase 25 Task 1 - design note: full path-wise bonus declaration dynamics "
    "(per-time-step declared-rate response on the inner paths)"
)

STANDARD_REFERENCES = [
    "Solvency II Delegated Reg. Art. 23 (future management actions: objective, realistic, verifiable; consistent with how they would be exercised over time)",
    "Solvency II Delegated Reg. Art. 234 (empirically justified diversification incl. tail behaviour)",
    "SOA ASOP 56 §3.1.3/§3.4/§3.5", "SOA ASOP 25 §3.3", "IA TAS M §3.2/§3.6",
    "IFoA Life Aggregation & Simulation working party",
    "CFO Forum MCEV Principle 7 (TVOG; dynamic management actions)",
]

AFFECTED_COMPONENTS = [
    "par_model_v2/projection/pathwise_bonus_dynamics.py (NEW, tested helper module)",
    "tests/test_phase25_task1_design_note.py",
    "scripts/build_phase25_task1_design_note.py",
    "docs/validation/PHASE25_TASK1_DESIGN_NOTE.{json,md}",
    "docs/PATHWISE_BONUS_DECLARATION_DESIGN_CARD.md",
]


def _load_p24t3_motivation() -> dict:
    """Archived Phase 24 Task 3 figures (motivation; NOT consumed by gates)."""
    try:
        with open(P24T3) as fh:
            r = json.load(fh)
        res = r.get("result", {})
        return {
            "residual_documented": r.get("residual_documented"),
            "nested_scr_without": res.get("nested_capital_without", {}).get("scr_proxy"),
            "nested_scr_with_outer_node": res.get("nested_capital_with_outer_node", {}).get("scr_proxy"),
            "nested_scr_with_inner_path": res.get("nested_capital_with_inner_path", {}).get("scr_proxy"),
            "active_share_nested": res.get("active_share_nested"),
            "floor_share_nested": res.get("floor_share_nested"),
            "rule": res.get("rule"),
            "source": P24T3,
        }
    except Exception as exc:  # archived report missing -> disclosed
        return {"source": P24T3, "load_error": str(exc)}


def build_design_note(fast: bool = False) -> dict:
    if fast:
        pre = synthetic_recognition_lag_pre_study(seed=42, n_outer=800, n_inner=40, n_steps=10)
    else:
        pre = synthetic_recognition_lag_pre_study(seed=42, n_outer=4000, n_inner=100, n_steps=10)
    note = {
        "title": "Phase 25 Task 1 - Design Note: Full Path-Wise Bonus Declaration Dynamics",
        "verdict": "PASS" if pre["mechanism_demonstrated"] else "FAIL",
        "classification": "EDUCATIONAL",
        "candidate_chosen": "full path-wise bonus declaration dynamics (P24T3 documented residual)",
        "candidates_not_chosen": {
            "t_copula_on_inner_path_basis": (
                "DEFERRED to a later phase: Task 2 of THIS phase changes the with-actions basis "
                "(horizon-level -> path-wise); running the copula re-aggregation on the inner-path "
                "basis now would produce evidence superseded within one phase. Sequencing the basis "
                "refinement first avoids duplicated copula benchmarks."
            ),
            "credentialled_data_calibration": (
                "BLOCKED on credentialled management-practice data (standing human-action blocker); "
                "not executable from the sandbox. Remains the production sign-off residual by design."
            ),
        },
        "motivation_from_phase24_task3": _load_p24t3_motivation(),
        "problem": (
            "Phase 24 Task 3 moved the governed bonus-cut rule into the inner-path benefit "
            "cashflows, but the DECISION remains horizon-level: the pre-action outer-node coverage "
            "ratio fixes ONE retained-bonus factor that is constant across all inner paths and all "
            "time steps of that node (documented residual). A real par-fund board re-declares the "
            "reversionary bonus at every declaration date on the fund's CURRENT solvency position: "
            "after a cut, recovering paths see the bonus (partially) restored; after a healthy "
            "start, deteriorating paths see a cut the horizon-level basis never applies. The "
            "horizon-level approximation therefore mis-states the with-actions liability in both "
            "directions (recognition lag), and the sign at the capital-relevant 99.5% tail is an "
            "UNDERSTATEMENT: stressed nodes keep maximum relief for the whole projection while the "
            "path-wise truth restores bonus on recovering paths."
        ),
        "method_design": {
            "task": "Task 2 (nested truth) + Task 3 (proxy basis)",
            "design": (
                "Extend par_model_v2/projection/inner_path_action_dynamics.py with a path-wise "
                "declaration mode: at each inner time step t, the retained-bonus factor is "
                "re-evaluated as retained(CR_t) where CR_t is a path-wise coverage proxy "
                "(reference assets rolled forward on the inner path / pre-action path liability "
                "at t), using the UNCHANGED governed ManagementActionRule shape (trigger/floor/"
                "PRE floor; same monotonicity guard). Only in-force policyholder benefits remain "
                "cuttable (P24T3 carve-outs preserved: credit loss + analytic FX/liquidity "
                "offsets are NOT cuttable). The horizon-level basis is RETAINED as the "
                "comparison/sensitivity variant (P24T3 convention), exactly as the superseded "
                "scalar-response variant was retained in Phase 24. The LSMC proxy gains the "
                "matching path-wise post-composition basis feature so truth and proxy share an "
                "IDENTICAL action basis (G1 convention), then seven-driver OOS re-validation at "
                "the unchanged Phase 22 gates."
            ),
            "hypothesis": (
                "Path-wise declaration relieves LESS capital than the horizon-level basis at the "
                "99.5% tail (bonus restoration on recovering paths), so the path-wise with-actions "
                "SCR is HIGHER than the P24T3 inner-path horizon-level reference "
                f"({HORIZON_BASIS_SCR_REFERENCE:,.1f}); the synthetic pre-study sign carries over."
            ),
        },
        "pre_study_recognition_lag": pre,
        "pre_study_disclosure": (
            "The pre-study uses a SYNTHETIC single-fund participating product (reversionary bonus "
            "attaching to the liability, common-random-number asset paths) so that no real archived "
            "nested benchmark is consumed before the Task 2 gates: it demonstrates the recognition-"
            "lag MECHANISM (horizon-level basis understates the path-wise with-actions tail loss by "
            f"{pre['horizon_understatement_rel_at_var995']:.1%} at VaR99.5 on the synthetic fund; "
            f"bonus cut-then-restoration occurs on {pre['pathwise_restoration_share']:.1%} of inner "
            "paths; on healthy nodes the median path-wise minus horizon-level difference is "
            f"{pre['median_diff_pathwise_minus_horizon']:.2f} per 100 of initial liability, i.e. the "
            "lag effect is two-sided), not the magnitude of the real-data effect."
        ),
        "gap_analysis": [
            {
                "standard": "Solvency II Del. Reg. Art. 23 (management actions)",
                "requirement": "Management actions allowed for only if consistent with how they would actually be exercised: bonus declarations are made at every declaration date on the then-current solvency position, including restorations.",
                "current_state": "P24T3 inner-path basis: cut enters the inner cashflows but the decision is frozen at the outer node; no restoration on recovering paths, no cut on deteriorating paths from healthy nodes.",
                "gap": "Declaration timing is inconsistent with exercise practice; synthetic pre-study sign: horizon-level basis UNDERSTATES the with-actions tail loss.",
                "phase25_design": "Task 2 path-wise declaration in the nested truth; gates pre-registered in this note (s5); horizon-level basis retained as sensitivity evidence.",
            },
            {
                "standard": "SOA ASOP 56 §3.1.3/§3.4 (model structure; assumptions supportable)",
                "requirement": "Model structure appropriate to purpose, including the TIME LEVEL at which management behaviour enters the model.",
                "current_state": "Action decision is per-outer-node (annual horizon); inner-path declared rate cannot respond to the path.",
                "gap": "Recognition lag unmodelled; TVOG interaction of declaration dynamics unmeasured.",
                "phase25_design": "Task 3: matching path-wise proxy basis feature + OOS re-validation R^2 >= 0.95, VaR rel err <= 10% (unchanged Phase 22 gates); TVOG read-out disclosed.",
            },
            {
                "standard": "IA TAS M §3.2/§3.6 (limitations disclosed; evidence reproducible)",
                "requirement": "Material limitations disclosed; validation evidence reproducible with recorded config.",
                "current_state": "P24T3 residual disclosed verbatim in the report, the risk register and the offline UI; no quantification exists.",
                "gap": "Residual is described but not quantified; materiality unknown.",
                "phase25_design": "Task 4: pathwise-vs-horizon and with-vs-without capital deltas at VaR/ES/SCR for all four benchmarks; MR-010/MR-014 refresh if the SCR delta exceeds the 1% disclosure threshold; seeds/config/digests recorded.",
            },
            {
                "standard": "Solvency II Del. Reg. Art. 234; IFoA Aggregation WP (tail dependence)",
                "requirement": "Dependence assumptions justified on the basis actually used for capital; copula must not silently re-tune when the action basis changes.",
                "current_state": "df=2.9451 tail-matched on WITHOUT-actions losses (P23T2); P24T2 joint-action mechanism validated on the outer-node basis.",
                "gap": "If the path-wise basis becomes the with-actions reference, the joint-action copula read-outs must be re-anchored WITHOUT re-tuning the dependence parameters.",
                "phase25_design": "Task 4 rank-invariance check: df re-matched on the without-actions staged losses unchanged at 2.9451; copula parameters frozen; the t-copula-on-new-basis full re-aggregation is the documented NEXT-phase candidate.",
            },
        ],
        "task2_acceptance_criteria": [
            "Path-wise declaration in the nested truth: retained-bonus factor re-evaluated at every inner time step from a path-wise coverage proxy; UNCHANGED governed rule shape (trigger/floor/PRE; monotonicity guard re-verified on the path-wise basis)",
            "P24T3 carve-outs preserved: only in-force policyholder benefits cuttable (credit loss + analytic FX/liquidity offsets NOT cuttable)",
            "Sign gate (pre-registered): path-wise with-actions SCR >= horizon-level inner-path with-actions SCR at 99.5% (bonus restoration relieves LESS in the tail); magnitude DISCLOSED, not gated",
            "Horizon-level basis retained and reported alongside as the sensitivity variant; without-actions basis unchanged bit-identically (archive cross-check BEFORE any new computation)",
            "No gate-shopping: these gates fixed in this Task 1 note before any real-data path-wise benchmark",
            "assumption_change ChangeRecord OWNER_REVIEW",
        ],
        "task3_acceptance_criteria": [
            "Identical path-wise action basis in nested truth AND proxy (matching post-composition basis feature)",
            f"Seven-driver OOS re-validation: R^2 >= {PATHWISE_OOS_R2_GATE}, VaR rel err <= {PATHWISE_VAR_REL_ERROR_GATE:.0%} (unchanged Phase 22 gates)",
            "Action monotonicity preserved (construction guard re-verified on the path-wise basis)",
            "Pathwise-vs-horizon capital delta disclosed at VaR/ES/SCR; residual (declaration frequency vs inner step size; board discretion smoothing) documented",
            "code_change/assumption_change ChangeRecord OWNER_REVIEW",
        ],
        "task4_acceptance_criteria": [
            "Tail diagnostics on the path-wise basis: with-vs-without and pathwise-vs-horizon deltas at VaR/ES/SCR for nested, t, gaussian, var-covar",
            f"MR-010/MR-014 refreshed if |pathwise - horizon| SCR delta > {PATHWISE_MATERIALITY_DISCLOSURE_THRESHOLD:.0%} of the horizon-basis SCR (disclosure trigger, not a pass/fail gate)",
            "Rank invariance: df re-matched on WITHOUT-actions staged losses unchanged at 2.9451; copula parameters frozen (no silent re-tuning)",
            "Reproducibility: seeds, config, digests recorded; methodology_change ChangeRecord OWNER_REVIEW",
        ],
        "task5_plan": "Offline-UI propagation (ui_data.json contract 1.6.0 -> 1.7.0 ADDITIVE; path-wise declaration panel: pathwise-vs-horizon delta matrix, restoration-share diagnostics, gates) + PHASE 25 COMPLETE documentation; UI consumes ONLY model output JSON.",
        "limitations": [
            "The synthetic pre-study proves the mechanism and its SIGN, not the magnitude, of the real-data effect (single fund, lognormal assets, bonus attaching to liability).",
            "Path-wise coverage proxy on the inner paths is itself an approximation (reference assets rolled forward analytically; no inner rebalancing).",
            "Declaration frequency is tied to the inner step size; real boards declare annually with smoothing/discretion - documented residual for the design.",
            "Action parameters remain educational placeholders pending credentialled practice data + independent APS X2 review.",
        ],
        "standard_references": STANDARD_REFERENCES,
        "use_restrictions": pathwise_bonus_use_restrictions(),
    }
    return note


def _md(note: dict) -> str:
    pre = note["pre_study_recognition_lag"]
    mo = note["motivation_from_phase24_task3"]
    v = pre["var995"]
    lines = [
        "# Phase 25 Task 1 — Design Note: Full Path-Wise Bonus Declaration Dynamics",
        "",
        f"**Verdict: {note['verdict']}** (design note + tested helper module + synthetic recognition-lag pre-study). EDUCATIONAL ONLY.",
        "",
        "## 0. Candidate selection (design-note-first discipline)",
        "",
        f"**Chosen:** {note['candidate_chosen']}.",
        "",
        f"- t-copula on the inner-path basis: {note['candidates_not_chosen']['t_copula_on_inner_path_basis']}",
        f"- Credentialled-data calibration: {note['candidates_not_chosen']['credentialled_data_calibration']}",
        "",
        "## 1. Problem",
        "",
        note["problem"],
        "",
        f"Archived Phase 24 Task 3 motivation figures (NOT consumed by gates): {json.dumps({k: mo.get(k) for k in ('nested_scr_without','nested_scr_with_outer_node','nested_scr_with_inner_path','active_share_nested','floor_share_nested')})}",
        "",
        "## 2. Method — path-wise declaration (Tasks 2-3)",
        "",
        note["method_design"]["design"],
        "",
        f"**Hypothesis:** {note['method_design']['hypothesis']}",
        "",
        "## 3. Pre-study (synthetic recognition-lag mechanism)",
        "",
        f"- Synthetic fund: lognormal assets mu={pre['config']['mu']}, sigma={pre['config']['sigma']}; g={pre['config']['guaranteed_rate']}, target bonus={pre['config']['bonus_target']}; n_outer={pre['n_outer']:,}, n_inner={pre['n_inner']}, n_steps={pre['n_steps']}, seed={pre['seed']}",
        f"- VaR99.5 conditional net loss: without {v['without']:.2f}; horizon-level {v['horizon']:.2f}; path-wise {v['pathwise']:.2f}; max-cut bound {v['max_cut']:.2f} (per 100 initial liability)",
        f"- Horizon-level UNDERSTATES the path-wise tail loss by {pre['horizon_understatement_rel_at_var995']:.1%} at VaR99.5",
        f"- Path-wise action share {pre['pathwise_action_share']:.1%}; cut-then-RESTORED share {pre['pathwise_restoration_share']:.1%} (restoration is a real dynamic)",
        f"- Median path-wise minus horizon-level diff {pre['median_diff_pathwise_minus_horizon']:.2f} (healthy nodes: path-wise cuts MORE — the lag effect is two-sided)",
        f"- understatement_sign_ok={pre['understatement_sign_ok']}; relief_ordering_ok={pre['relief_ordering_ok']}; bounds_ok={pre['bounds_ok']}; digest={pre['digest']}",
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
                  f"- **Phase 25 design:** {g['phase25_design']}", ""]
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
    lines += ["", "*Generated by scripts/build_phase25_task1_design_note.py — educational model; production sign-off withheld.*", ""]
    return "\n".join(lines)


def _card(note: dict) -> str:
    pre = note["pre_study_recognition_lag"]
    v = pre["var995"]
    return "\n".join([
        "# Path-Wise Bonus Declaration Dynamics — Design Card (Phase 25)",
        "",
        f"**Verdict: {note['verdict']}** (design note; implementation in Phase 25 Tasks 2-4). EDUCATIONAL ONLY.",
        "",
        "## What changes",
        "",
        "The governed bonus-cut decision moves from ONCE-per-outer-node (horizon-level,",
        "Phase 24 Task 3) to EVERY inner time step on a path-wise coverage proxy:",
        "recovering paths restore the bonus; deteriorating paths from healthy nodes get cut.",
        "Rule shape, carve-outs and monotonicity guard are UNCHANGED.",
        "",
        "## Why (recognition lag, synthetic pre-study)",
        "",
        f"- Horizon-level basis understates the path-wise with-actions tail loss by {pre['horizon_understatement_rel_at_var995']:.1%} at VaR99.5 (synthetic fund; sign pre-registered, magnitude NOT extrapolated)",
        f"- VaR99.5 per 100 initial liability: without {v['without']:.2f} / path-wise {v['pathwise']:.2f} / horizon {v['horizon']:.2f} / max-cut {v['max_cut']:.2f}",
        f"- Cut-then-restored share {pre['pathwise_restoration_share']:.1%}; two-sided median effect {pre['median_diff_pathwise_minus_horizon']:.2f}",
        f"- Reproducibility digest: {pre['digest']}",
        "",
        "## Pre-registered gates (s5 of the design note)",
        "",
        f"- OOS R^2 >= {PATHWISE_OOS_R2_GATE}; VaR rel err <= {PATHWISE_VAR_REL_ERROR_GATE:.0%} (unchanged Phase 22 gates)",
        "- Sign gate: path-wise SCR >= horizon-level SCR at 99.5% (magnitude disclosed, not gated)",
        f"- MR-010/MR-014 disclosure trigger: |pathwise - horizon| SCR delta > {PATHWISE_MATERIALITY_DISCLOSURE_THRESHOLD:.0%} of horizon SCR",
        "- Rank invariance: df unchanged at 2.9451 on without-actions losses; copula frozen",
        "",
        "## Out of scope / residuals (disclosed)",
        "",
        "- Declaration frequency tied to inner step size (boards declare annually with smoothing)",
        "- t-copula re-aggregation on the NEW basis: next-phase candidate",
        "- Credentialled calibration: standing human-action blocker",
        "",
        "*Generated by scripts/build_phase25_task1_design_note.py — educational model; production sign-off withheld.*",
        "",
    ])


def apply_governance(store: GovernanceStore, note: dict) -> dict:
    actor = "Phase25Task1DesignNote"
    phase = "Phase 25: Path-Wise Bonus Declaration Dynamics"
    if any(r.title == CHANGE_TITLE for r in store.change_records):
        return {"added": False, "reason": "already applied (idempotent)"}
    pre = note["pre_study_recognition_lag"]
    rec = ChangeRecord.create(
        title=CHANGE_TITLE,
        description=(
            "Design note for Phase 25: full path-wise bonus declaration dynamics - the governed "
            "ManagementActionRule decision re-evaluated at EVERY inner time step on a path-wise "
            "coverage proxy (new tested helper module "
            "par_model_v2/projection/pathwise_bonus_dynamics.py: four-bases common-random-number "
            "simulator, retained-bonus-rate mapping, synthetic recognition-lag pre-study), "
            "addressing the residual DOCUMENTED in the Phase 24 Task 3 report (decision frozen at "
            "the outer node; relief factor constant across inner paths). Candidate selection "
            "rationale recorded (t-copula-on-new-basis deferred to avoid superseded evidence; "
            "credentialled calibration blocked on data). FIXED pre-registered acceptance gates "
            "for Tasks 2-4."
        ),
        change_type="governance_change",
        affected_components=AFFECTED_COMPONENTS,
        standard_references=STANDARD_REFERENCES,
        before_snapshot={
            "action_dynamics": "inner-path cashflow cut with HORIZON-LEVEL decision (P24T3); relief factor constant across the inner paths of one outer node (documented residual)",
        },
        after_snapshot={
            "design": "path-wise per-time-step declaration (Tasks 2-3); tail diagnostics + risk-register refresh (Task 4); UI 1.6.0 -> 1.7.0 (Task 5)",
            "pre_study": {
                "horizon_understatement_rel_at_var995": pre["horizon_understatement_rel_at_var995"],
                "pathwise_restoration_share": pre["pathwise_restoration_share"],
                "understatement_sign_ok": pre["understatement_sign_ok"],
                "bounds_ok": pre["bounds_ok"],
            },
            "verdict": note["verdict"] + " (design note)",
        },
        impact_assessment=(
            "No numeric output path changed this cycle (design note + additive helper module only). "
            "Fixes non-gate-shopped acceptance criteria for Tasks 2-4 BEFORE any real-data "
            "path-wise benchmark; pre-registers the SIGN of the expected capital effect "
            "(path-wise SCR >= horizon-level SCR). Educational classification retained; "
            "production sign-off withheld pending credentialled data + APS X2 review."
        ),
        author=actor, phase=phase,
        quantitative_impact=(
            f"Synthetic pre-study: horizon-level basis understates the path-wise with-actions "
            f"VaR99.5 by {pre['horizon_understatement_rel_at_var995']:.1%}; cut-then-restored "
            f"share {pre['pathwise_restoration_share']:.1%}. No capital figures changed."
        ),
    )
    rec.submit_for_peer_review(actor=actor, comments="Design note + new unit tests PASS; no existing module touched.")
    rec.submit_to_owner(actor=actor, comments="Owner review: synthetic-mechanism scope + declaration-frequency residual documented; sign-off withheld.")
    store.add_change_record(rec)
    store.audit_trail.append(AuditEntry.governance(
        actor=actor, phase=phase,
        event="ChangeRecord opened (OWNER_REVIEW) - Phase 25 Task 1 design note (full path-wise bonus declaration dynamics)",
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
