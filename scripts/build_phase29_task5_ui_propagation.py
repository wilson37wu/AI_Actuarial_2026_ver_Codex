#!/usr/bin/env python3
"""Phase 29 Task 5 - offline-UI propagation of the vine / pair-copula
dependence upgrade; PHASE 29 COMPLETE.

This is NOT a model calculation. It verifies that the offline UI
(`scripts/build_ui_data.py` -> `ui_data.json` v1.11.0 ADDITIVE +
`ui_app.html`) surfaces the Phase 29 additions as a first-class
**Vine Tail (P29)** panel:
  (a) Task 2 truncated credit-root C-vine prototype on FROZEN margins -
      vine candidate component SCR 42,458.6 (+6.21% vs frozen-t 39,975.7,
      +19.25% vs grouped-t 35,604.4; gap to nested 46,638.9 narrowed to
      -8.96% - FIRST candidate to move TOWARD the nested read-out);
  (b) Task 3 vine margin bootstrap (200x20k, frozen fit) - vine SCR mean
      41,917.6, 95% CI [38,654.7, 45,284.3], SE 4.04%, nested OUTSIDE the
      CI; copula-form residual NARROWS to 3,637.3 (-65.33% vs grouped-t,
      -40.52% vs skew-t);
  (c) Task 4 pair-level tail diagnostics (p-grid 0.80-0.95, candidate vs
      frozen, fitted first/second tree + never-fitted holdout, 95% CIs;
      largest lift rate-liquidity|credit +0.8514 at p=0.90), the
      fit-vs-holdout overfit gate (holdout/fit max-lift ratio 0.049, PASS),
      and the MR-016 KEEP-OPEN / MR-017 OPENED remediation decision with the
      governed headline recovered bit-identically (move 0.0000%).
It re-runs the jsdom self-test (0 network / 0 JS errors), opens an
OWNER_REVIEW ChangeRecord, appends one governance audit entry, verifies
audit-chain integrity, and writes the Task 5 evidence report.
PHASE 29 COMPLETE once this report is persisted.

Run:  PYTHONPATH=. python3 scripts/build_phase29_task5_ui_propagation.py
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

PHASE = "Phase 29: Vine / Pair-Copula Dependence Upgrade"
ACTOR = "AutomatedModelDev_Phase29"
GOV_PATH = Path(".claude-dev/GOVERNANCE_STORE.json")
UI_DATA = Path("ui_data.json")
UI_APP = Path("ui_app.html")
SELF_TEST = Path("scripts/ui_app_self_test.cjs")
OUT_DIR = Path("docs/validation")
JSON_PATH = OUT_DIR / "PHASE29_TASK5_UI_PROPAGATION_REPORT.json"
MD_PATH = OUT_DIR / "PHASE29_TASK5_UI_PROPAGATION_REPORT.md"
CARD_PATH = Path("docs/UI_PROPAGATION_CARD_P29.md")
CHANGE_TITLE = (
    "Phase 29 Task 5 - offline-UI propagation of the vine / pair-copula "
    "dependence upgrade view"
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
    "Solvency II Art. 234 (dependence justification - frozen copula/margins "
    "+ rank-invariance displayed; vine DISCLOSED, not adopted)",
    "Aas, Czado, Frigessi & Bakken (2009) pair-copula constructions",
    "Efron & Tibshirani (1993) bootstrap",
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
    p29 = data.get("phase29", {}) if isinstance(data.get("phase29"), dict) \
        else {}
    co = p29.get("copula", {}) or {}
    bo = p29.get("bootstrap", {}) or {}
    td = p29.get("tail", {}) or {}
    ci = bo.get("vine_component_scr_ci", {}) or {}
    fci = bo.get("frozen_t_component_scr_ci", {}) or {}
    gd = bo.get("residual_gap_redecomposition_point", {}) or {}
    mr = td.get("mr_remediation_decision", {}) or {}
    oc = td.get("overfit_check", {}) or {}
    levels = td.get("levels", {}) or {}
    rows90 = (levels.get("90") or {}).get("rows", []) or []
    n_first = sum(1 for r in rows90 if r.get("tree") == "first")
    n_second = sum(1 for r in rows90 if r.get("tree") == "second")
    n_holdout = sum(1 for r in rows90 if r.get("tree") == "holdout")
    rate_liq = [r for r in rows90
                if r.get("pair_label") == "lapse-liquidity"
                or r.get("pair_label") == "rate-liquidity"]
    rl = next((r for r in rows90 if r.get("pair_label") == "rate-liquidity"
               and r.get("tree") == "second"), {})
    rl_lift = ((rl.get("lift_upper") or {}).get("mean"))

    checks = {
        "contract_version": data.get("contract_version"),
        "contract_is_1_11_0": data.get("contract_version") == "1.11.0",
        "phase29_section_present": isinstance(p29, dict) and bool(p29),
        # ---- Task 2 vine prototype ----
        "vine_structure_credit_root":
            co.get("structure") == "truncated_c_vine_credit_root",
        "vine_two_trees": co.get("max_vine_trees") == 2,
        "vine_root_credit": co.get("root_driver_name") == "credit",
        "vine_point_42459": _close(
            (co.get("vine_candidate_readout") or {}).get("scr_component"),
            42458.6, 1.0),
        "frozen_t_point_39976": _close(
            co.get("frozen_t_reference_scr_component"), 39975.7, 1.0),
        "boundary_recovery_exact": co.get("boundary_recovery_dev") == 0.0,
        "grouped_t_ref_35604": _close(
            co.get("grouped_t_comparison_scr_component"), 35604.4, 1.0),
        "vine_vs_frozen_plus_6_21pct": _close(
            co.get("candidate_vs_frozen_t_rel"), 0.062110, 5e-4),
        "gap_to_nested_minus_8_96pct": _close(
            co.get("candidate_gap_to_nested_rel"), -0.089632, 5e-4),
        "df_frozen_2_9451": _close(co.get("df_rematched"), 2.9451, 1e-3),
        "rho_frozen_lt_1e_12": (
            isinstance(co.get("rho_max_abs_diff"), (int, float))
            and float(co["rho_max_abs_diff"]) < 1e-12),
        "family_counts_present": bool(co.get("family_counts")),
        "t2_gates_8_pass": (isinstance(co.get("gates"), dict)
                            and len(co["gates"]) == 8
                            and _gates_pass(co["gates"])),
        # ---- Task 3 vine bootstrap ----
        "boot_mean_41918": _close(ci.get("mean"), 41917.6, 1.0),
        "boot_ci_lo_38655": _close(ci.get("ci_lo"), 38654.7, 1.0),
        "boot_ci_hi_45284": _close(ci.get("ci_hi"), 45284.3, 1.0),
        "boot_frozen_mean_39603": _close(fci.get("mean"), 39603.2, 1.0),
        "boot_se_4_04pct_le_5pct": (
            _close(bo.get("se_frac_of_mean"), 0.040418, 5e-4)
            and float(bo.get("se_frac_of_mean") or 1.0) <= 0.05),
        "boot_se_gate_pass": bo.get("se_gate_pass") is True,
        "boot_nested_OUTSIDE_95ci":
            bo.get("headline_nested_inside_95ci") is False,
        "boot_nested_ref_46639": _close(
            bo.get("nested_pathwise_reference"), 46638.9, 1.0),
        "boot_vine_up_pos_share_1": (
            bo.get("vine_minus_frozen_pos_share") == 1.0
            and bo.get("directional_disclosed_direction") == "up"),
        "residual_vine_3637": _close(
            gd.get("copula_form_residual_abs"), 3637.3, 1.0),
        "residual_refs_grouped_skewt": (
            _close(bo.get("grouped_t_copula_form_residual_ref"),
                   10491.5, 1.0)
            and _close(bo.get("skewt_reconfirmed_copula_form_residual_ref"),
                       6114.9, 1.0)),
        "boot_gates_pass": _gates_pass(bo.get("gates")),
        # ---- Task 4 pair tail diagnostics + overfit + MR decision ----
        "tail_grid_4_levels": (len(levels) == 4
                               and sorted(levels.keys())
                               == ["80", "85", "90", "95"]),
        "tail_p90_rows_6_5_3": (n_first, n_second, n_holdout) == (6, 5, 3),
        "rate_liq_lift_0_8514": _close(rl_lift, 0.8514, 5e-4),
        "overfit_ratio_0_049": _close(
            oc.get("holdout_to_fit_max_lift_ratio"), 0.048588, 5e-4),
        "overfit_gate_pass": oc.get("overfit_gate_pass") is True,
        "holdout_disclosure_complete":
            oc.get("holdout_disclosure_complete") is True,
        "mr016_keep_open": mr.get("mr016_decision") == "KEEP_OPEN",
        "mr017_opened": mr.get("open_mr017") is True,
        "residual_narrowing_minus_65_33pct": _close(
            mr.get("residual_change_vs_grouped_t_rel"), -0.653310, 5e-4),
        "residual_narrowing_minus_40_52pct": _close(
            mr.get("residual_change_vs_skewt_rel"), -0.405174, 5e-4),
        "governed_headline_move_0": (
            mr.get("governed_headline_relative_move") == 0.0
            and mr.get("mr010_mr014_refresh_required") is False),
        "governed_headline_39976": _close(
            mr.get("governed_headline_reference"), 39975.7, 1.0),
        "t4_gates_6_pass": (isinstance(td.get("gates"), dict)
                            and len(td["gates"]) == 6
                            and _gates_pass(td["gates"])),
        # ---- additive capital read-outs ----
        "capital_vine_point_42459": _close(
            cap.get("vine_copula_scr_component_point"), 42458.6, 1.0),
        "capital_vine_bootstrap_41918": _close(
            cap.get("vine_copula_scr_component_bootstrap_mean"),
            41917.6, 1.0),
        # ---- narrative ----
        "narrative_present": bool(str(p29.get("narrative", "")).strip()),
        "narrative_discloses_not_adopted":
            "not adopted" in str(p29.get("narrative", "")).lower(),
    }
    checks["all_passed"] = all(v is True for k, v in checks.items()
                               if k not in ("contract_version",))
    checks["headline_readouts"] = {
        "vine_point": (co.get("vine_candidate_readout")
                       or {}).get("scr_component"),
        "vine_bootstrap_mean": ci.get("mean"),
        "vine_bootstrap_ci": [ci.get("ci_lo"), ci.get("ci_hi")],
        "vine_se_frac": bo.get("se_frac_of_mean"),
        "frozen_point": co.get("frozen_t_reference_scr_component"),
        "grouped_point": co.get("grouped_t_comparison_scr_component"),
        "nested_reference": bo.get("nested_pathwise_reference"),
        "gap_to_nested_rel": co.get("candidate_gap_to_nested_rel"),
        "copula_form_residual": gd.get("copula_form_residual_abs"),
        "residual_change_vs_grouped_t_rel":
            mr.get("residual_change_vs_grouped_t_rel"),
        "residual_change_vs_skewt_rel":
            mr.get("residual_change_vs_skewt_rel"),
        "max_fit_lift": oc.get("max_fit_pair_abs_mean_lift"),
        "max_holdout_lift": oc.get("max_holdout_pair_abs_mean_lift"),
        "overfit_ratio": oc.get("holdout_to_fit_max_lift_ratio"),
        "mr016_decision": mr.get("mr016_decision"),
        "mr017_opened": mr.get("open_mr017"),
        "governed_headline_move":
            mr.get("governed_headline_relative_move"),
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
        "phase29_checks": {
            k: out.get("checks", {}).get(k)
            for k in ("phase29TabPresent", "p29Cards", "p29GateCrits",
                      "p29PairRows", "p29GapRows", "p29BarRects",
                      "vineTailTabTextPresent", "vineScrPresent",
                      "vineBootstrapCiPresent", "vineNestedOutsidePresent",
                      "vineResidualNarrowingPresent",
                      "vineRateLiquidityLiftPresent",
                      "vineOverfitRatioPresent",
                      "vineFrozenHeadlinePresent", "mr017Present",
                      "vineNotAdoptedPresent")
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
                "Phase 29 Task 5 propagated the vine / pair-copula "
                "dependence-upgrade results to the zero-install offline UI. "
                "scripts/build_ui_data.py (contract bumped ADDITIVELY to "
                "v1.11.0) now surfaces a first-class Vine Tail (P29) panel: "
                "(1) the Task 2 truncated credit-root C-vine prototype on "
                "FROZEN standalone margins / Sigma / df 2.9451 with EXACT "
                "frozen-t boundary recovery (dev 0.0) - vine candidate "
                "component SCR 42,458.6 = +6.21% vs frozen-t 39,975.7 and "
                "+19.25% vs grouped-t 35,604.4, narrowing the gap to the "
                "nested path-wise reference 46,638.9 to -8.96% (FIRST "
                "candidate to move TOWARD nested; disclosed, not gated; "
                "leakage-free family selection surfaced); (2) the Task 3 "
                "vine margin bootstrap (200x20k on the frozen fit) - vine "
                "SCR mean 41,917.6, 95% CI [38,654.7, 45,284.3], SE 4.04% "
                "<= 5%, nested OUTSIDE the CI; the copula-form residual "
                "NARROWS to 3,637.3 (-65.33% vs grouped-t 10,491.5, -40.52% "
                "vs skew-t 6,114.9) - the first candidate to NARROW below "
                "BOTH baselines; (3) the Task 4 pair-level tail-dependence "
                "grid (p in {0.80,0.85,0.90,0.95}, candidate vs frozen, "
                "fitted first/second tree + never-fitted holdout pairs, 95% "
                "CIs; largest lift rate-liquidity|credit +0.8514 at p=0.90), "
                "the fit-vs-holdout overfit gate (holdout/fit max-lift ratio "
                "0.049, PASS, holdout disclosure complete), and the MR-016 "
                "KEEP-OPEN / MR-017 OPENED remediation decision with the "
                "governed headline (frozen single-df t 39,975.7) recovered "
                "bit-identically (move 0.0000% -> MR-010/MR-014 no refresh). "
                "Additive capital read-outs vine_copula_scr_component_point "
                "and vine_copula_scr_component_bootstrap_mean added. The UI "
                "performs no calculation; it consumes only already-produced "
                "model output JSONs. The vine remains DISCLOSED, not adopted, "
                "pending owner sign-off. PHASE 29 COMPLETE (Tasks 1-5)."
            ),
            change_type="code_change",
            affected_components=AFFECTED_COMPONENTS,
            standard_references=STANDARD_REFERENCES,
            before_snapshot={
                "ui_contract": "1.10.0 (grouped-t tail panel; no vine / "
                               "pair-copula panel, pair-level tail grid, "
                               "overfit read-out or MR-016/MR-017 status)",
            },
            after_snapshot={
                "ui_contract": "1.11.0 (additive)",
                "headline_readouts": hr,
                "self_test_ok": st["ok"],
                "network_calls": st["network_calls"],
                "js_errors": st["js_errors"],
                "n_checks": st["n_checks"],
            },
            impact_assessment=(
                "Display-layer only: the UI bundler reads validation-report "
                "JSONs and performs no model calculation, so no model output "
                "changes. Additive contract bump keeps existing consumers "
                "working. The governed headline remains the frozen single-df "
                "t component basis; the vine candidate is surfaced as a "
                "DISCLOSED alternative read-out only, pending owner "
                "sign-off. Completes the Phase 29 per-task offline-UI "
                "propagation requirement; PHASE 29 COMPLETE (Tasks 1-5)."
            ),
            quantitative_impact=(
                "UI now displays: vine candidate SCR {vp:.0f} point / "
                "{vm:.0f} bootstrap mean, 95% CI [{lo:.0f}, {hi:.0f}], SE "
                "{se:.2%}; frozen-t {fp:.0f}; grouped-t {gp:.0f}; nested "
                "{nr:.0f} OUTSIDE the CI; copula-form residual {cf:.0f} "
                "({rg:+.2%} vs grouped-t, {rs:+.2%} vs skew-t); max fitted "
                "lift {mf:+.4f} vs max holdout lift {mh:.4f} (ratio "
                "{ro:.3f}); MR-016 {m16}, MR-017 opened {m17}; governed "
                "headline move {gm:.4%}. jsdom self-test ok with {nc} "
                "network calls and {je} JS errors over {n} checks."
            ).format(
                vp=hr["vine_point"], vm=hr["vine_bootstrap_mean"],
                lo=hr["vine_bootstrap_ci"][0], hi=hr["vine_bootstrap_ci"][1],
                se=hr["vine_se_frac"], fp=hr["frozen_point"],
                gp=hr["grouped_point"], nr=hr["nested_reference"],
                cf=hr["copula_form_residual"],
                rg=hr["residual_change_vs_grouped_t_rel"],
                rs=hr["residual_change_vs_skewt_rel"],
                mf=hr["max_fit_lift"], mh=hr["max_holdout_lift"],
                ro=hr["overfit_ratio"], m16=hr["mr016_decision"],
                m17=hr["mr017_opened"], gm=hr["governed_headline_move"],
                nc=st["network_calls"], je=st["js_errors"], n=st["n_checks"],
            ),
            author=ACTOR,
            phase=PHASE,
            peer_reviewer="APS_X2_Independent_Reviewer",
            assumption_owner="ChiefActuary",
        )
        rec.submit_for_peer_review(
            ACTOR,
            "UI propagation verified by the contract checks + jsdom "
            "self-test (0 network / 0 JS errors); display-layer change only. "
            "The first-to-narrow residual finding, the nested-OUTSIDE-CI "
            "disclosure, the fit-vs-holdout overfit evidence and the MR-016 "
            "KEEP-OPEN / MR-017 OPENED decision are carried into the display "
            "verbatim; copula and margins remain FROZEN per SII Art. 234 and "
            "the vine is NOT adopted into the governed headline.",
        )
        rec.submit_to_owner(
            ACTOR,
            "Owner review requested. PHASE 29 COMPLETE at the educational "
            "level; production sign-off remains withheld pending "
            "credentialled-data calibration and independent APS X2 review. "
            "Owner adoption decision for the vine candidate as a disclosed "
            "alternative read-out is tracked under MR-017 / next-phase "
            "re-assessment.",
        )
        store.add_change_record(rec)
        added = True
        record_id = rec.record_id
        record_status = rec.status.value
        store.audit_trail.append(
            AuditEntry.governance(
                actor=ACTOR,
                phase=PHASE,
                event=("ChangeRecord opened (OWNER_REVIEW) - Phase 29 Task 5 "
                       "offline-UI propagation; PHASE 29 COMPLETE"),
                details={
                    "record_id": rec.record_id,
                    "ui_contract": "1.11.0",
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
        "task": "Phase 29 Task 5 - offline-UI propagation",
        "phase": PHASE,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "verdict": "PASS",
        "phase29_status": "COMPLETE (Tasks 1-5)",
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
    md = """# Phase 29 Task 5 - Offline-UI Propagation Report

**Generated (UTC):** {now}
**Verdict:** PASS - **PHASE 29 COMPLETE (Tasks 1-5)**

## What the offline UI now surfaces (contract v1.11.0, additive)

A first-class **Vine Tail (P29)** panel:

- **Truncated credit-root C-vine prototype on FROZEN margins (Task 2):**
  vine candidate component SCR **{vp:,.0f}** (+6.21% vs frozen-t {fp:,.0f},
  +19.25% vs grouped-t {gp:,.0f}); gap to the nested path-wise reference
  {nr:,.0f} narrowed to **-8.96%** - the FIRST dependence candidate to move
  TOWARD the nested read-out (disclosed, not gated); EXACT frozen-t boundary
  recovery (dev 0.0); leakage-free family selection surfaced; copula and
  margins FROZEN (df 2.9451, rho max|diff| < 1e-12).
- **Vine margin bootstrap on the frozen fit (Task 3):** vine SCR mean
  **{vm:,.0f}**, 95% CI **[{lo:,.0f}, {hi:,.0f}]**, SE **{se:.2%}** of mean
  (<= 5%); nested {nr:,.0f} remains **OUTSIDE the CI**; the copula-form
  residual NARROWS to **{cf:,.0f}** ({rg:+.2%} vs grouped-t, {rs:+.2%} vs
  skew-t) - the first candidate to NARROW below BOTH baselines.
- **Pair-level tail diagnostics + overfit check + MR decision (Task 4):**
  candidate-vs-frozen upper/lower tail-dependence grid over p in
  {{0.80, 0.85, 0.90, 0.95}} for all 11 fitted links (first/second tree)
  PLUS 3 never-fitted holdout pairs with 95% CIs; largest lift
  rate-liquidity|credit **+0.8514** at p=0.90; fit-vs-holdout overfit gate
  PASS (max holdout lift {mh:.4f} vs max fitted lift {mf:.4f}, ratio
  **{ro:.3f}**); **MR-016 KEEP OPEN** (nested outside CI - close criteria
  not met; narrowing DISCLOSED) and **MR-017 OPENED** (residual vine-FORM
  limitations); governed headline recovered bit-identically (move
  **{gm:.4%}** -> MR-010/MR-014 no refresh).
- Additive capital read-outs `vine_copula_scr_component_point` and
  `vine_copula_scr_component_bootstrap_mean`.

**Conclusion.** The vine is the most informative dependence candidate to
date: it tilts the upper tail in the right direction on every fitted link
and materially narrows the copula-form residual, but the nested truth stays
outside its sampling band, so it remains a DISCLOSED alternative read-out -
NOT adopted into the governed headline without owner sign-off. The residual
lives in nested inner-path joint dynamics tracked by MR-017.

## Verification

- `ui_data.json` contract checks: ALL PASS ({nck} substantive checks).
- jsdom self-test: **ok:true**, {nc} network calls / {je} JS errors over
  {nst} checks (16 new Phase 29 checks incl. panel cards, pair-level tail
  table (14 rows = 6 first-tree + 5 second-tree + 3 holdout), gap
  re-decomposition table, gate grids, SCR + lift bar charts).

## Governance

- ChangeRecord `{crid}` ({crstatus}); audit entries {aud}; change records
  {chg}; audit-chain integrity verify_all = {integ}.
- Production sign-off remains withheld (educational classification):
  residual is credentialled-data calibration + independent APS X2 review -
  not a code gap.

**Standards:** SOA ASOP 41 s3.2; ASOP 56 s3.5; IA TAS M s3.6; Solvency II
Art. 234; Aas et al. (2009); Efron & Tibshirani (1993).
""".format(
        now=report["generated_utc"],
        vp=hr["vine_point"], vm=hr["vine_bootstrap_mean"],
        lo=hr["vine_bootstrap_ci"][0], hi=hr["vine_bootstrap_ci"][1],
        se=hr["vine_se_frac"], fp=hr["frozen_point"],
        gp=hr["grouped_point"], nr=hr["nested_reference"],
        cf=hr["copula_form_residual"],
        rg=hr["residual_change_vs_grouped_t_rel"],
        rs=hr["residual_change_vs_skewt_rel"],
        mf=hr["max_fit_lift"], mh=hr["max_holdout_lift"],
        ro=hr["overfit_ratio"], gm=hr["governed_headline_move"],
        nck=nck, nc=st["network_calls"], je=st["js_errors"],
        nst=st["n_checks"], crid=gov["change_record_id"],
        crstatus=gov["change_record_status"],
        aud=report["governance"]["audit_entries"],
        chg=report["governance"]["change_records"], integ=integrity,
    )
    MD_PATH.write_text(md, encoding="utf-8")

    card = """# UI Propagation Card (Phase 29 Task 5) - PHASE 29 COMPLETE

- Offline UI contract bumped ADDITIVELY 1.10.0 -> 1.11.0; new Vine Tail
  (P29) tab consumes only model-output JSONs (zero install, 0 network,
  0 JS errors).
- Task 2: truncated credit-root C-vine on FROZEN margins - candidate SCR
  {vp:,.0f} (+6.21% vs frozen-t {fp:,.0f}, +19.25% vs grouped-t {gp:,.0f});
  gap to nested {nr:,.0f} narrowed to -8.96% (first candidate to move
  TOWARD nested); boundary recovery dev 0.0.
- Task 3: vine bootstrap mean {vm:,.0f}, 95% CI [{lo:,.0f}, {hi:,.0f}], SE
  {se:.2%}; nested OUTSIDE the CI; copula-form residual {cf:,.0f}
  ({rg:+.2%} vs grouped-t, {rs:+.2%} vs skew-t) - first to NARROW below
  both baselines.
- Task 4: pair-level tail grid (11 fitted + 3 holdout pairs, 4 p-levels,
  95% CIs); largest lift rate-liquidity|credit +0.8514 at p=0.90; overfit
  gate PASS (holdout/fit ratio {ro:.3f}); MR-016 KEEP OPEN, MR-017 OPENED;
  governed headline move {gm:.4%} (no MR-010/MR-014 refresh).
- Finding surfaced verbatim: the vine is DISCLOSED, not adopted - the
  governed headline remains the frozen single-df t. Verdict: PASS -
  educational; production sign-off withheld.
""".format(
        vp=hr["vine_point"], vm=hr["vine_bootstrap_mean"],
        lo=hr["vine_bootstrap_ci"][0], hi=hr["vine_bootstrap_ci"][1],
        se=hr["vine_se_frac"], fp=hr["frozen_point"],
        gp=hr["grouped_point"], nr=hr["nested_reference"],
        cf=hr["copula_form_residual"],
        rg=hr["residual_change_vs_grouped_t_rel"],
        rs=hr["residual_change_vs_skewt_rel"],
        ro=hr["overfit_ratio"], gm=hr["governed_headline_move"],
    )
    CARD_PATH.write_text(card, encoding="utf-8")

    print(json.dumps({
        "verdict": "PASS", "phase29": "COMPLETE",
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
