#!/usr/bin/env python3
"""Phase 30 Task 5 - offline-UI propagation of the post-vine dependence
roadmap decision + binding stop-rule; PHASE 30 COMPLETE.

This is NOT a model calculation. It verifies that the offline UI
(`scripts/build_ui_data.py` -> `ui_data.json` v1.13.0 ADDITIVE +
`ui_app.html`) surfaces the Phase 30 additions as a first-class
**Stop-Rule (P30)** panel:
  (a) Task 1 roadmap decision (option A tree-3 vine deepening selected
      design-note-first; binding stop-rule option D embedded; option C =
      Phase 31 owner decision package regardless of outcome);
  (b) Task 2 tree-3 candidate on the FROZEN P29 2-tree fit - DUAL boundary
      recovery bit-identical (frozen-t 39,975.7 AND 2-tree vine 42,458.6,
      dev 0.0); all four pre-registered third-tree pairs zero-strength
      (joint-conditional fit support n_fit {3,3,3,1} of 112) so the
      candidate is BIT-IDENTICAL to the 2-tree vine;
  (c) Task 3 margin bootstrap (200x20k) - tree-3 SCR mean 41,751.9, 95% CI
      [38,593.7, 44,556.4], SE 3.81%; nested 46,638.9 OUTSIDE the CI;
      per-replicate tree-3 minus 2-tree vine EXACTLY ZERO;
  (d) Task 4 tail diagnostics + the BINDING STOP-RULE APPLIED: MR-016 and
      MR-017 KEEP OPEN, dependence-FORM escalation under MR-016 ENDS,
      Phase 31 = owner decision package; overfit gate PASS (ratio 0.049);
      governed headline move 0.0000% (MR-010/MR-014 no refresh).
It re-runs the jsdom self-test (0 network / 0 JS errors), opens an
OWNER_REVIEW ChangeRecord, appends one governance audit entry, verifies
audit-chain integrity, and writes the Task 5 evidence report.
PHASE 30 COMPLETE once this report is persisted.

Run:  PYTHONPATH=. python3 scripts/build_phase30_task5_ui_propagation.py
"""
from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from par_model_v2.governance.audit_trail import (
    AuditEntry,
    ChangeRecord,
    GovernanceStore,
)

PHASE = "Phase 30: Post-Vine Dependence Roadmap Decision"
ACTOR = "AutomatedModelDev_Phase30"
GOV_PATH = Path(".claude-dev/GOVERNANCE_STORE.json")
UI_DATA = Path("ui_data.json")
UI_APP = Path("ui_app.html")
SELF_TEST = Path("scripts/ui_app_self_test.cjs")
OUT_DIR = Path("docs/validation")
JSON_PATH = OUT_DIR / "PHASE30_TASK5_UI_PROPAGATION_REPORT.json"
MD_PATH = OUT_DIR / "PHASE30_TASK5_UI_PROPAGATION_REPORT.md"
CARD_PATH = Path("docs/UI_PROPAGATION_CARD_P30.md")
CHANGE_TITLE = (
    "Phase 30 Task 5 - offline-UI propagation of the tree-3 vine candidate "
    "and the binding stop-rule decision view"
)
AFFECTED_COMPONENTS = [
    "scripts/build_ui_data.py",
    "scripts/ui_app_self_test.cjs",
    "ui_data.json",
    "ui_app.html",
]
STANDARD_REFERENCES = [
    "SOA ASOP 41 s3.2 (communication of actuarial findings)",
    "SOA ASOP 56 s3.5 (model output validation & presentation)",
    "IA TAS M s3.6 (reproducibility and disclosure of model results)",
    "Solvency II Art. 234 (dependence justification - frozen copula/margins; "
    "tree-3 vine DISCLOSED, not adopted)",
    "Aas, Czado, Frigessi & Bakken (2009) pair-copula constructions",
    "IFoA Modelling Practice Note s4 (model risk register / stop-rule)",
]


def _close(x, target, tol=1.0):
    return isinstance(x, (int, float)) and abs(float(x) - target) <= tol


def _gates_pass(gates, ignore_suffixes=("_raw", "_required")):
    if not isinstance(gates, dict) or not gates:
        return False
    for k, v in gates.items():
        if any(k.endswith(s) for s in ignore_suffixes):
            continue
        if v is not True:
            return False
    return True


def check_ui_contract() -> dict:
    data = json.loads(UI_DATA.read_text(encoding="utf-8"))
    cap = data.get("capital", {})
    p30 = data.get("phase30", {}) if isinstance(data.get("phase30"), dict) \
        else {}
    rm = p30.get("roadmap", {}) or {}
    t3 = p30.get("tree3", {}) or {}
    bo = p30.get("bootstrap", {}) or {}
    sr = p30.get("stop_rule", {}) or {}
    td = p30.get("tail", {}) or {}
    ci = bo.get("tree3_component_scr_ci", {}) or {}
    gd = bo.get("residual_gap_redecomposition_point", {}) or {}
    oc = td.get("overfit_check", {}) or {}
    fc = t3.get("tree3_family_counts", {}) or {}
    levels = td.get("levels", {}) or {}
    rows90 = (levels.get("90") or {}).get("rows", []) or []
    n_first = sum(1 for r in rows90 if r.get("tree") == "first")
    n_second = sum(1 for r in rows90 if r.get("tree") == "second")
    n_third = sum(1 for r in rows90 if r.get("tree") == "third")
    n_holdout = sum(1 for r in rows90 if r.get("tree") == "holdout")

    checks = {
        "contract_version": data.get("contract_version"),
        "contract_is_1_13_0": data.get("contract_version") == "1.13.0",
        "phase30_section_present": isinstance(p30, dict) and bool(p30),
        # ---- Task 1 roadmap decision ----
        "roadmap_option_A_selected":
            rm.get("selected_option") == "A_tree3_vine_deepening",
        "roadmap_stop_rule_preregistered":
            "STOP-RULE" in str(rm.get("stop_rule", "")),
        "roadmap_phase31_committed": "owner decision package" in str(
            rm.get("post_phase30_commitment", "")).lower(),
        # ---- Task 2 tree-3 candidate ----
        "tree3_structure": t3.get("structure")
            == "truncated_c_vine_credit_root_tree3",
        "tree3_three_trees": t3.get("max_vine_trees") == 3,
        "tree3_point_42459": _close(
            t3.get("tree3_candidate_scr_component"), 42458.6, 1.0),
        "vine2_ref_42459": _close(
            t3.get("vine2_boundary_scr_component"), 42458.6, 1.0),
        "frozen_t_point_39976": _close(
            t3.get("frozen_t_reference_scr_component"), 39975.7, 1.0),
        "grouped_t_ref_35604": _close(
            t3.get("grouped_t_comparison_scr_component"), 35604.4, 1.0),
        "dual_boundary_recovery_exact": (
            t3.get("boundary_t_recovery_dev") == 0.0
            and t3.get("boundary_vine2_recovery_dev") == 0.0),
        "candidate_vs_vine2_exactly_zero":
            t3.get("candidate_vs_vine2_rel") == 0.0,
        "tree3_families_all_zero_strength_gaussian": (
            fc.get("gaussian") == 4
            and all(fc.get(k, 0) == 0 for k in
                    ("student_t", "survival_clayton", "survival_gumbel"))),
        "third_tree_edges_4": len(t3.get("third_tree_edges") or []) == 4,
        "df_frozen_2_9451": _close(t3.get("df_rematched"), 2.9451, 1e-3),
        "rho_frozen_lt_1e_12": (
            isinstance(t3.get("rho_max_abs_diff"), (int, float))
            and float(t3["rho_max_abs_diff"]) < 1e-12),
        "t2_gates_10_pass": (isinstance(t3.get("gates"), dict)
                             and len(t3["gates"]) == 10
                             and _gates_pass(t3["gates"])),
        # ---- Task 3 bootstrap ----
        "boot_mean_41752": _close(ci.get("mean"), 41751.9, 1.0),
        "boot_ci_lo_38594": _close(ci.get("ci_lo"), 38593.7, 1.0),
        "boot_ci_hi_44556": _close(ci.get("ci_hi"), 44556.4, 1.0),
        "boot_se_3_81pct_le_5pct": (
            _close(bo.get("se_frac_of_mean"), 0.038063, 5e-4)
            and float(bo.get("se_frac_of_mean") or 1.0) <= 0.05),
        "boot_se_gate_pass": bo.get("se_gate_pass") is True,
        "boot_nested_OUTSIDE_95ci":
            bo.get("headline_nested_inside_95ci") is False,
        "boot_nested_ref_46639": _close(
            bo.get("nested_pathwise_reference"), 46638.9, 1.0),
        "boot_tree3_minus_vine2_exactly_zero": (
            bo.get("tree3_minus_vine2_max_abs") == 0.0
            and bo.get("tree3_minus_vine2_all_exactly_zero") is True),
        "residual_tree3_3637": _close(
            gd.get("copula_form_residual_abs"), 3637.3, 1.0),
        "boot_gates_pass": _gates_pass(bo.get("gates")),
        # ---- Task 4 stop-rule + MR decision ----
        "stop_rule_trigger_met": sr.get("stop_rule_trigger_met") is True,
        "stop_rule_applied": sr.get("stop_rule_applied") is True,
        "dependence_form_escalation_ends":
            sr.get("dependence_form_escalation_ends") is True,
        "mr016_keep_open": sr.get("mr016_decision") == "KEEP_OPEN",
        "mr017_keep_open": sr.get("mr017_decision") == "KEEP_OPEN",
        "phase31_owner_package_directive": "OWNER DECISION PACKAGE" in str(
            sr.get("phase31_directive", "")).upper(),
        "governed_headline_move_0": (
            sr.get("governed_headline_relative_move") == 0.0
            and sr.get("mr010_mr014_refresh_required") is False),
        "governed_headline_39976": _close(
            sr.get("governed_headline_reference"), 39975.7, 1.0),
        "residual_refs_inherited": (
            _close(sr.get("residual_change_vs_grouped_t_rel"),
                   -0.653310, 5e-4)
            and _close(sr.get("residual_change_vs_skewt_rel"),
                       -0.405174, 5e-4)),
        # ---- Task 4 tail grid + overfit ----
        "tail_grid_4_levels": (len(levels) == 4
                               and sorted(levels.keys())
                               == ["80", "85", "90", "95"]),
        "tail_p90_rows_6_5_4_3":
            (n_first, n_second, n_third, n_holdout) == (6, 5, 4, 3),
        "overfit_ratio_0_049": _close(
            oc.get("holdout_to_fit_max_lift_ratio"), 0.048802, 5e-4),
        "overfit_gate_pass": oc.get("overfit_gate_pass") is True,
        "tree3_fit_all_zero_strength":
            oc.get("tree3_fit_all_zero_strength") is True,
        "t4_gates_6_pass": (isinstance(td.get("gates"), dict)
                            and len(td["gates"]) == 6
                            and _gates_pass(td["gates"])),
        # ---- additive capital read-outs ----
        "capital_tree3_point_42459": _close(
            cap.get("tree3_vine_scr_component_point"), 42458.6, 1.0),
        "capital_tree3_bootstrap_41752": _close(
            cap.get("tree3_vine_scr_component_bootstrap_mean"),
            41751.9, 1.0),
        # ---- narrative ----
        "narrative_present": bool(str(p30.get("narrative", "")).strip()),
        "narrative_discloses_not_adopted":
            "not adopted" in str(p30.get("narrative", "")).lower(),
        "narrative_states_stop_rule": "STOP-RULE IS APPLIED" in str(
            p30.get("narrative", "")),
    }
    checks["all_passed"] = all(v is True for k, v in checks.items()
                               if k not in ("contract_version",))
    checks["headline_readouts"] = {
        "tree3_point": t3.get("tree3_candidate_scr_component"),
        "tree3_bootstrap_mean": ci.get("mean"),
        "tree3_bootstrap_ci": [ci.get("ci_lo"), ci.get("ci_hi")],
        "tree3_se_frac": bo.get("se_frac_of_mean"),
        "vine2_point": t3.get("vine2_boundary_scr_component"),
        "frozen_point": t3.get("frozen_t_reference_scr_component"),
        "grouped_point": t3.get("grouped_t_comparison_scr_component"),
        "nested_reference": bo.get("nested_pathwise_reference"),
        "copula_form_residual": gd.get("copula_form_residual_abs"),
        "overfit_ratio": oc.get("holdout_to_fit_max_lift_ratio"),
        "stop_rule_applied": sr.get("stop_rule_applied"),
        "mr016_decision": sr.get("mr016_decision"),
        "mr017_decision": sr.get("mr017_decision"),
        "governed_headline_move":
            sr.get("governed_headline_relative_move"),
        "phase31_directive": sr.get("phase31_directive"),
    }
    return checks


def run_self_test() -> dict:
    env = dict(**os.environ)
    proc = subprocess.run(
        ["node", str(SELF_TEST), str(UI_APP)],
        capture_output=True, text=True, timeout=180, env=env,
    )
    out = json.loads(proc.stdout)
    return {
        "ok": bool(out.get("ok")),
        "network_calls": out.get("checks", {}).get("networkCalls"),
        "js_errors": out.get("checks", {}).get("jsErrors"),
        "n_checks": len(out.get("checks", {})),
        "failed_checks": [k for k, v in out.get("checks", {}).items()
                          if v is False],
        "phase30_checks": {
            k: out.get("checks", {}).get(k)
            for k in ("phase30TabPresent", "p30Cards", "p30GateCrits",
                      "p30PairRows", "p30EdgeRows", "p30GapRows",
                      "p30BarRects", "stopRuleTabTextPresent",
                      "p30StopRuleAppliedPresent", "p30Tree3ScrPresent",
                      "p30BootstrapCiPresent", "p30NestedOutsidePresent",
                      "p30ZeroStrengthPresent", "p30Mr016KeepOpenPresent",
                      "p30Mr017Present", "p30Phase31Present",
                      "p30GovernedHeadlinePresent",
                      "p30OverfitRatioPresent")
        },
    }


def apply_governance(store: GovernanceStore, ui: dict, st: dict) -> dict:
    added = False
    record_id = None
    record_status = None
    if not any(r.title == CHANGE_TITLE for r in store.change_records):
        hr = ui["headline_readouts"]
        rec = ChangeRecord.create(
            title=CHANGE_TITLE,
            description=(
                "Phase 30 Task 5 propagated the post-vine dependence "
                "roadmap decision and the BINDING STOP-RULE outcome to the "
                "zero-install offline UI. scripts/build_ui_data.py "
                "(contract bumped ADDITIVELY to v1.13.0) now surfaces a "
                "first-class Stop-Rule (P30) panel: (1) the Task 1 roadmap "
                "decision (option A tree-3 vine deepening selected "
                "design-note-first; binding stop-rule pre-registered; "
                "Phase 31 owner decision package committed regardless of "
                "outcome); (2) the Task 2 tree-3 candidate on the FROZEN "
                "P29 2-tree fit with DUAL boundary recovery bit-identical "
                "(frozen-t 39,975.7 AND 2-tree vine 42,458.6, dev 0.0) and "
                "the data-support DISCLOSURE that all four pre-registered "
                "third-tree pairs are zero-strength (joint-conditional fit "
                "support n_fit {3,3,3,1} of 112 rows) so the candidate is "
                "BIT-IDENTICAL to the 2-tree vine; (3) the Task 3 margin "
                "bootstrap (200x20k) - tree-3 SCR mean 41,751.9, 95% CI "
                "[38,593.7, 44,556.4], SE 3.81% <= 5%, nested 46,638.9 "
                "OUTSIDE the CI, per-replicate tree-3 minus 2-tree vine "
                "EXACTLY ZERO in all 200 replicates; (4) the Task 4 "
                "pair-level tail grid (6 first-tree + 5 second-tree + 4 "
                "third-tree + 3 holdout pairs with 95% CIs), the overfit "
                "gate (holdout/fit ratio 0.049 = P29 reference, PASS), and "
                "the BINDING STOP-RULE APPLIED: MR-016 and MR-017 KEEP "
                "OPEN, dependence-FORM escalation under MR-016 ENDS, "
                "Phase 31 = owner decision package (option C); governed "
                "headline (frozen single-df t 39,975.7) recovered "
                "bit-identically (move 0.0000% -> MR-010/MR-014 no "
                "refresh). Additive capital read-outs "
                "tree3_vine_scr_component_point and "
                "tree3_vine_scr_component_bootstrap_mean added. The UI "
                "performs no calculation; it consumes only already-produced "
                "model output JSONs. The tree-3 / vine candidates remain "
                "DISCLOSED, not adopted, pending owner sign-off. "
                "PHASE 30 COMPLETE (Tasks 1-5)."
            ),
            change_type="code_change",
            affected_components=AFFECTED_COMPONENTS,
            standard_references=STANDARD_REFERENCES,
            before_snapshot={
                "ui_contract": "1.12.0 (vine tail panel + currency "
                               "wire-through; no tree-3 / stop-rule panel, "
                               "roadmap decision or Phase 31 directive)",
            },
            after_snapshot={
                "ui_contract": "1.13.0 (additive)",
                "headline_readouts": hr,
                "self_test_ok": st["ok"],
                "network_calls": st["network_calls"],
                "js_errors": st["js_errors"],
                "n_checks": st["n_checks"],
            },
            impact_assessment=(
                "Display-layer only: the UI bundler reads validation-report "
                "JSONs and performs no model calculation, so no model "
                "output changes. Additive contract bump keeps existing "
                "consumers working. The governed headline remains the "
                "frozen single-df t component basis; the tree-3 / 2-tree "
                "vine candidates are surfaced as DISCLOSED alternative "
                "read-outs only, pending owner sign-off. Completes the "
                "Phase 30 per-task offline-UI propagation requirement; "
                "PHASE 30 COMPLETE (Tasks 1-5); next phase is the owner "
                "decision package (option C)."
            ),
            quantitative_impact=(
                "UI now displays: tree-3 candidate SCR {tp:.0f} point / "
                "{tm:.0f} bootstrap mean, 95% CI [{lo:.0f}, {hi:.0f}], SE "
                "{se:.2%}; 2-tree vine {vp:.0f} (tree-3 minus 2-tree "
                "EXACTLY ZERO); frozen-t {fp:.0f} (governed); grouped-t "
                "{gp:.0f}; nested {nr:.0f} OUTSIDE the CI; copula-form "
                "residual {cf:.0f} UNCHANGED; overfit ratio {ro:.3f}; "
                "STOP-RULE applied {sa}; MR-016 {m16} / MR-017 {m17}; "
                "governed headline move {gm:.4%}. jsdom self-test ok with "
                "{nc} network calls and {je} JS errors over {n} checks."
            ).format(
                tp=hr["tree3_point"], tm=hr["tree3_bootstrap_mean"],
                lo=hr["tree3_bootstrap_ci"][0],
                hi=hr["tree3_bootstrap_ci"][1],
                se=hr["tree3_se_frac"], vp=hr["vine2_point"],
                fp=hr["frozen_point"], gp=hr["grouped_point"],
                nr=hr["nested_reference"], cf=hr["copula_form_residual"],
                ro=hr["overfit_ratio"], sa=hr["stop_rule_applied"],
                m16=hr["mr016_decision"], m17=hr["mr017_decision"],
                gm=hr["governed_headline_move"],
                nc=st["network_calls"], je=st["js_errors"],
                n=st["n_checks"],
            ),
            author=ACTOR,
            phase=PHASE,
            peer_reviewer="APS_X2_Independent_Reviewer",
            assumption_owner="ChiefActuary",
        )
        rec.submit_for_peer_review(
            ACTOR,
            "UI propagation verified by the contract checks + jsdom "
            "self-test (0 network / 0 JS errors); display-layer change "
            "only. The zero-strength tree-3 finding, the nested-OUTSIDE-CI "
            "disclosure, the BINDING STOP-RULE decision (dependence-FORM "
            "escalation ENDS) and the Phase 31 owner-decision-package "
            "directive are carried into the display verbatim; copula and "
            "margins remain FROZEN per SII Art. 234 and neither vine "
            "candidate is adopted into the governed headline.",
        )
        rec.submit_to_owner(
            ACTOR,
            "Owner review requested. PHASE 30 COMPLETE at the educational "
            "level; production sign-off remains withheld pending "
            "credentialled-data calibration and independent APS X2 review. "
            "Phase 31 is the owner decision package: adopt the disclosed "
            "vine read-out vs accept the residual vs fund a second "
            "independent nested run (option B), per the pre-registered "
            "stop-rule.",
        )
        store.add_change_record(rec)
        added = True
        record_id = rec.record_id
        record_status = rec.status.value
        store.audit_trail.append(
            AuditEntry.governance(
                actor=ACTOR,
                phase=PHASE,
                event=("ChangeRecord opened (OWNER_REVIEW) - Phase 30 "
                       "Task 5 offline-UI propagation; PHASE 30 COMPLETE; "
                       "stop-rule applied, Phase 31 = owner decision "
                       "package"),
                details={
                    "record_id": rec.record_id,
                    "ui_contract": "1.13.0",
                    "self_test_ok": st["ok"],
                    "network_calls": st["network_calls"],
                    "js_errors": st["js_errors"],
                    "affected_components": AFFECTED_COMPONENTS,
                },
            )
        )
    else:
        for rec in store.change_records:
            if rec.title == CHANGE_TITLE:
                record_id = rec.record_id
                record_status = rec.status.value
    return {"added_change_record": added, "change_record_id": record_id,
            "change_record_status": record_status}


def main() -> int:
    ui = check_ui_contract()
    if not ui["all_passed"]:
        print("UI contract checks FAILED:",
              [k for k, v in ui.items()
               if v is False and k != "contract_version"])
        return 1
    st = run_self_test()
    if not (st["ok"] and st["network_calls"] == 0 and st["js_errors"] == 0):
        print("Self-test FAILED:", st)
        return 1

    store = GovernanceStore.from_json(GOV_PATH.read_text(encoding="utf-8"))
    n_audit_before = len(store.audit_trail.all())
    n_change_before = len(store.change_records)
    gov = apply_governance(store, ui, st)
    integrity = store.audit_trail.verify_all()
    if not integrity:
        print("AUDIT INTEGRITY FAILED - store NOT saved")
        return 1
    GOV_PATH.write_text(store.to_json(), encoding="utf-8")

    report = {
        "task": "Phase 30 Task 5 - offline-UI propagation",
        "phase": PHASE,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "verdict": "PASS",
        "phase30_status": "COMPLETE (Tasks 1-5)",
        "stop_rule": "APPLIED - dependence-FORM escalation under MR-016 "
                     "ENDS; Phase 31 = owner decision package (option C)",
        "ui_contract_checks": ui,
        "self_test": st,
        "governance": {
            **gov,
            "audit_entries":
                f"{n_audit_before}->{len(store.audit_trail.all())}",
            "change_records":
                f"{n_change_before}->{len(store.change_records)}",
            "audit_integrity_verify_all": integrity,
        },
    }
    JSON_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")

    hr = ui["headline_readouts"]
    nck = sum(1 for k, v in ui.items()
              if v is True and k not in ("all_passed",))
    md = """# Phase 30 Task 5 - Offline-UI Propagation Report

**Generated (UTC):** {now}
**Verdict:** PASS - **PHASE 30 COMPLETE (Tasks 1-5)**

## What the offline UI now surfaces (contract v1.13.0, additive)

A first-class **Stop-Rule (P30)** panel:

- **Roadmap decision (Task 1):** option A (tree-3 vine deepening) selected
  design-note-first; the binding stop-rule (option D) pre-registered; the
  Phase 31 owner decision package (option C) committed regardless of
  outcome; option B (nested-aware calibration) reserved as an
  owner-approved escalation.
- **Tree-3 candidate on the FROZEN P29 2-tree fit (Task 2):** DUAL boundary
  recovery bit-identical FIRST (frozen-t **{fp:,.0f}** AND 2-tree vine
  **{vp:,.0f}**, dev 0.0). Data-support DISCLOSURE: all four pre-registered
  joint-conditional third-tree pairs are **zero-strength** (n_fit
  {{3,3,3,1}} of 112 fit rows), so the candidate component SCR
  **{tp:,.0f}** is **BIT-IDENTICAL** to the 2-tree vine.
- **Margin bootstrap (Task 3):** tree-3 SCR mean **{tm:,.0f}**, 95% CI
  **[{lo:,.0f}, {hi:,.0f}]**, SE **{se:.2%}** (<= 5%); nested {nr:,.0f}
  remains **OUTSIDE the CI**; per-replicate tree-3 minus 2-tree vine
  EXACTLY ZERO in all 200 replicates; copula-form residual **{cf:,.0f}**
  UNCHANGED vs the 2-tree vine.
- **Binding stop-rule + MR decision (Task 4):** pair-level tail grid (6
  first-tree + 5 second-tree + 4 third-tree + 3 holdout pairs, 4 p-levels,
  95% CIs); overfit gate PASS (holdout/fit ratio **{ro:.3f}** = P29
  reference); **STOP-RULE APPLIED** - MR-016 and MR-017 **KEEP OPEN**,
  **dependence-FORM escalation under MR-016 ENDS**, **Phase 31 = owner
  decision package**; governed headline recovered bit-identically (move
  **{gm:.4%}** -> MR-010/MR-014 no refresh).
- Additive capital read-outs `tree3_vine_scr_component_point` and
  `tree3_vine_scr_component_bootstrap_mean`.

**Conclusion.** Phase 30 closes the dependence-FORM escalation arc that ran
P27 (skew-t) -> P28 (grouped-t) -> P29 (2-tree vine) -> P30 (tree-3): the
vine narrowed the copula-form residual by 65% but the data cannot support
deeper conditional structure (zero-strength tree 3), and the nested truth
stays outside the sampling band. Per the pre-registered stop-rule, no
further copula-structure candidates may be opened without owner sign-off;
the decision moves to the owner (adopt the disclosed read-out vs accept the
residual vs fund option B).

## Verification

- `ui_data.json` contract checks: ALL PASS ({nck} substantive checks).
- jsdom self-test: **ok:true**, {nc} network calls / {je} JS errors over
  {nst} checks (18 new Phase 30 checks incl. panel cards, third-tree edge
  table, pair-level tail table (18 rows = 6+5+4+3), residual table, gate
  grids, SCR + lift bar charts, stop-rule text assertions).

## Governance

- ChangeRecord `{crid}` ({crstatus}); audit entries {aud}; change records
  {chg}; audit-chain integrity verify_all = {integ}.
- Production sign-off remains withheld (educational classification).

**Standards:** SOA ASOP 41 s3.2; ASOP 56 s3.5; IA TAS M s3.6; Solvency II
Art. 234; Aas et al. (2009); IFoA MPN s4.
""".format(
        now=report["generated_utc"],
        tp=hr["tree3_point"], tm=hr["tree3_bootstrap_mean"],
        lo=hr["tree3_bootstrap_ci"][0], hi=hr["tree3_bootstrap_ci"][1],
        se=hr["tree3_se_frac"], vp=hr["vine2_point"],
        fp=hr["frozen_point"], nr=hr["nested_reference"],
        cf=hr["copula_form_residual"], ro=hr["overfit_ratio"],
        gm=hr["governed_headline_move"],
        nck=nck, nc=st["network_calls"], je=st["js_errors"],
        nst=st["n_checks"], crid=gov["change_record_id"],
        crstatus=gov["change_record_status"],
        aud=report["governance"]["audit_entries"],
        chg=report["governance"]["change_records"], integ=integrity,
    )
    MD_PATH.write_text(md, encoding="utf-8")

    card = """# UI Propagation Card (Phase 30 Task 5) - PHASE 30 COMPLETE

- Offline UI contract bumped ADDITIVELY 1.12.0 -> 1.13.0; new Stop-Rule
  (P30) tab consumes only model-output JSONs (zero install, 0 network,
  0 JS errors).
- Task 1: roadmap decision - option A (tree-3 deepening) design-note-first
  with the binding stop-rule pre-registered; Phase 31 owner package
  committed regardless of outcome.
- Task 2: tree-3 candidate {tp:,.0f} BIT-IDENTICAL to the 2-tree vine
  {vp:,.0f} (all four third-tree pairs zero-strength, n_fit {{3,3,3,1}} of
  112); DUAL boundary recovery dev 0.0 (frozen-t {fp:,.0f} governed).
- Task 3: bootstrap mean {tm:,.0f}, 95% CI [{lo:,.0f}, {hi:,.0f}], SE
  {se:.2%}; nested {nr:,.0f} OUTSIDE; tree-3 minus 2-tree EXACTLY ZERO in
  all 200 replicates; residual {cf:,.0f} UNCHANGED.
- Task 4: overfit gate PASS (ratio {ro:.3f}); STOP-RULE APPLIED - MR-016 /
  MR-017 KEEP OPEN, dependence-FORM escalation ENDS, Phase 31 = owner
  decision package; governed headline move {gm:.4%}.
- Finding surfaced verbatim: the tree-3 / vine candidates are DISCLOSED,
  not adopted - the governed headline remains the frozen single-df t.
  Verdict: PASS - educational; production sign-off withheld.
""".format(
        tp=hr["tree3_point"], tm=hr["tree3_bootstrap_mean"],
        lo=hr["tree3_bootstrap_ci"][0], hi=hr["tree3_bootstrap_ci"][1],
        se=hr["tree3_se_frac"], vp=hr["vine2_point"],
        fp=hr["frozen_point"], nr=hr["nested_reference"],
        cf=hr["copula_form_residual"], ro=hr["overfit_ratio"],
        gm=hr["governed_headline_move"],
    )
    CARD_PATH.write_text(card, encoding="utf-8")

    print(json.dumps({
        "verdict": "PASS", "phase30": "COMPLETE",
        "stop_rule": "APPLIED",
        "change_record_id": gov["change_record_id"],
        "change_record_status": gov["change_record_status"],
        "audit": report["governance"]["audit_entries"],
        "changes": report["governance"]["change_records"],
        "integrity": integrity,
        "self_test_ok": st["ok"], "n_self_test_checks": st["n_checks"],
        "reports": [str(JSON_PATH), str(MD_PATH), str(CARD_PATH)],
    }, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
