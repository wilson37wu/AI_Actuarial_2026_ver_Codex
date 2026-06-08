#!/usr/bin/env python3
"""Phase 26 Task 5 - offline-UI propagation of the full path-wise copula
re-aggregation; PHASE 26 COMPLETE.

This is NOT a model calculation. It verifies that the offline UI
(`scripts/build_ui_data.py` -> `ui_data.json` v1.8.0 ADDITIVE + `ui_app.html`)
surfaces the Phase 26 additions as a first-class **Full Re-Agg (P26)** panel:
  (a) Task 2 per-driver composition transform on the FROZEN t(2.9451) copula -
      component-basis t SCR 39,975.7 vs re-anchored 39,794.3 (+0.46%);
  (b) Task 3 frozen-copula margin bootstrap on the FULL component basis -
      component t SCR mean 39,595.1, 95% CI [36,676.2, 42,943.1], SE 4.07%,
      with the nested path-wise reference 46,638.9 OUTSIDE the CI -> the
      residual 14.29% gap decomposes 91.9% COPULA-FORM / 8.1% relief-surface;
  (c) Task 4 paired common-random-number delta matrix - composition correction
      +211.5 [+46.1, +381.8] statistically significant yet < 1% MR trigger
      (MR-010/MR-014 numeric refresh NOT required; MR-015 stays free).
It re-runs the jsdom self-test (0 network / 0 JS errors), opens an
OWNER_REVIEW ChangeRecord, appends one governance audit entry, verifies
audit-chain integrity, and writes the Task 5 evidence report.
PHASE 26 COMPLETE once this report is persisted.

Run:  PYTHONPATH=/var/tmp/pylibs:. python3 scripts/build_phase26_task5_ui_propagation.py
"""
from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from par_model_v2.governance.audit_trail import (
    AuditEntry,
    ChangeRecord,
    GovernanceStore,
)

PHASE = "Phase 26: Full Path-Wise Copula Re-Aggregation"
ACTOR = "AutomatedModelDev_Phase26"
GOV_PATH = Path(".claude-dev/GOVERNANCE_STORE.json")
UI_DATA = Path("ui_data.json")
UI_APP = Path("ui_app.html")
SELF_TEST = Path("scripts/ui_app_self_test.cjs")
OUT_DIR = Path("docs/validation")
JSON_PATH = OUT_DIR / "PHASE26_TASK5_UI_PROPAGATION_REPORT.json"
MD_PATH = OUT_DIR / "PHASE26_TASK5_UI_PROPAGATION_REPORT.md"
CARD_PATH = Path("docs/UI_PROPAGATION_CARD_P26.md")
CHANGE_TITLE = (
    "Phase 26 Task 5 - offline-UI propagation of the full path-wise copula "
    "re-aggregation view"
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
    "Solvency II Art. 234 (dependence justification - frozen-copula "
    "re-aggregation + rank-invariance displayed)",
    "Efron & Tibshirani (1993) paired bootstrap",
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
    p26 = data.get("phase26", {}) if isinstance(data.get("phase26"), dict) else {}
    co = p26.get("composition", {}) or {}
    ct = co.get("t_readout", {}) or {}
    bo = p26.get("bootstrap", {}) or {}
    ci = bo.get("component_t_scr_ci", {}) or {}
    gd = bo.get("residual_gap_decomposition", {}) or {}
    dm = p26.get("delta_matrix", {}) or {}
    pm = dm.get("point_matrix", {}) or {}
    pdl = dm.get("paired_deltas", {}) or {}
    cc = pdl.get("composition_correction_t", {}) or {}
    mr = pdl.get("management_relief_t", {}) or {}
    trg = dm.get("mr_trigger", {}) or {}
    ri = dm.get("rank_invariance", {}) or {}
    verdicts = data.get("verdicts", [])
    vnames = [str(v.get("name") or v.get("key", "")) for v in verdicts]

    def _v(name):
        return any(name in n for n in vnames)

    checks = {
        "contract_version": data.get("contract_version"),
        "contract_is_1_8_0": data.get("contract_version") == "1.8.0",
        "phase26_section_present": isinstance(p26, dict) and bool(p26),
        # ---- Task 2 composition transform ----
        "comp_scr_component_39976": _close(ct.get("scr_component"), 39975.7, 1.0),
        "comp_scr_level_39794": _close(ct.get("scr_level"), 39794.3, 1.0),
        "comp_scr_without_47269": _close(ct.get("scr_without"), 47269.1, 1.0),
        "comp_sign_gate_ref_39794": _close(
            co.get("sign_gate_reference"), 39794.3, 1.0),
        "comp_nested_ref_46639": _close(
            co.get("nested_pathwise_reference"), 46638.9, 1.0),
        "comp_vs_reanchored_0_46pct": _close(
            co.get("component_vs_reanchored_rel_t"), 0.004557, 5e-4),
        "comp_mr_trigger_1pct_not_met":
            co.get("mr_refresh_trigger_1pct") is False,
        "comp_gap_to_nested_14_29pct": _close(
            co.get("gap_to_nested_component_t_rel"), -0.142869, 5e-4),
        "comp_envelope_bounds_ok": co.get("envelope_bounds_ok") is True,
        "comp_df_frozen_2_9451": _close(co.get("df_rematched"), 2.9451, 1e-3),
        "comp_rho_frozen_lt_1e_12": (
            isinstance(co.get("rho_max_abs_diff"), (int, float))
            and float(co["rho_max_abs_diff"]) < 1e-12),
        "comp_gates_6_pass": (isinstance(co.get("gates"), dict)
                              and len(co["gates"]) == 6
                              and _gates_pass(co["gates"])),
        # ---- Task 3 frozen-copula bootstrap + gap decomposition ----
        "boot_mean_39595": _close(ci.get("mean"), 39595.1, 1.0),
        "boot_ci_lo_36676": _close(ci.get("ci_lo"), 36676.2, 1.0),
        "boot_ci_hi_42943": _close(ci.get("ci_hi"), 42943.1, 1.0),
        "boot_se_4_07pct_le_5pct": (
            _close(bo.get("se_frac_of_mean"), 0.040661, 5e-4)
            and float(bo.get("se_frac_of_mean") or 1.0) <= 0.05),
        "boot_se_gate_pass": bo.get("se_gate_pass") is True,
        "boot_nested_OUTSIDE_95ci":
            bo.get("headline_nested_inside_95ci") is False,
        "gap_copula_form_share_91_9pct": _close(
            gd.get("copula_form_share_of_gap"), 0.918501, 5e-4),
        "gap_relief_surface_share_8_1pct": _close(
            gd.get("relief_surface_share_of_gap"), 0.081499, 5e-4),
        "gap_copula_form_dominant": gd.get("copula_form_dominant") is True,
        "gap_residual_exceeds_t_g_sensitivity":
            gd.get("residual_exceeds_t_g_sensitivity") is True,
        "boot_gates_pass": _gates_pass(bo.get("gates")),
        # ---- Task 4 paired delta matrix + MR trigger ----
        "matrix_component_t_39976": _close(
            (pm.get("component") or {}).get("t"), 39975.7, 1.0),
        "matrix_level_t_39794": _close(
            (pm.get("level") or {}).get("t"), 39794.3, 1.0),
        "matrix_without_t_47269": _close(
            (pm.get("without") or {}).get("t"), 47269.1, 1.0),
        "paired_comp_correction_212": _close(cc.get("mean"), 211.5, 2.0),
        "paired_comp_correction_excludes_zero":
            cc.get("excludes_zero") is True,
        "paired_mgmt_relief_excludes_zero": mr.get("excludes_zero") is True,
        "mr_trigger_not_fired": trg.get("trigger_fired") is False,
        "mr_trigger_max_move_0_55pct": _close(
            trg.get("max_abs_rel"), 0.005510, 5e-4),
        "mr_trigger_significant_t":
            trg.get("statistically_significant_t") is True,
        "rank_invariant_reverified": ri.get("rank_invariant") is True,
        "delta_gates_pass": _gates_pass(dm.get("gates")),
        # ---- additive capital read-outs ----
        "capital_component_39976": _close(
            cap.get("t_copula_scr_pathwise_component"), 39975.7, 1.0),
        "capital_component_bootstrap_39595": _close(
            cap.get("t_copula_scr_pathwise_component_bootstrap_mean"),
            39595.1, 1.0),
        # ---- verdicts + narrative ----
        "comp_verdict_listed": _v("per-driver composition transform"),
        "boot_verdict_listed":
            _v("frozen-copula margin bootstrap + gap decomposition"),
        "delta_verdict_listed": _v("paired full-vs-reanchored delta matrix"),
        "narrative_present": bool(str(p26.get("narrative", "")).strip()),
    }
    checks["all_passed"] = all(v is True for k, v in checks.items()
                               if k not in ("contract_version",))
    checks["headline_readouts"] = {
        "scr_component_t": ct.get("scr_component"),
        "scr_level_t": ct.get("scr_level"),
        "component_vs_reanchored_rel": co.get("component_vs_reanchored_rel_t"),
        "bootstrap_mean": ci.get("mean"),
        "bootstrap_ci": [ci.get("ci_lo"), ci.get("ci_hi")],
        "bootstrap_se_frac": bo.get("se_frac_of_mean"),
        "nested_reference": co.get("nested_pathwise_reference"),
        "gap_to_nested_rel": co.get("gap_to_nested_component_t_rel"),
        "copula_form_share": gd.get("copula_form_share_of_gap"),
        "relief_surface_share": gd.get("relief_surface_share_of_gap"),
        "paired_comp_correction": [cc.get("mean"), cc.get("ci_lo"),
                                   cc.get("ci_hi")],
        "mr_trigger_fired": trg.get("trigger_fired"),
        "mr_trigger_max_abs_rel": trg.get("max_abs_rel"),
    }
    return checks


def run_self_test() -> dict:
    proc = subprocess.run(
        ["node", str(SELF_TEST), str(UI_APP)],
        capture_output=True, text=True, timeout=120,
    )
    out = json.loads(proc.stdout)
    return {
        "ok": bool(out.get("ok")),
        "network_calls": out.get("checks", {}).get("networkCalls"),
        "js_errors": out.get("checks", {}).get("jsErrors"),
        "n_checks": len(out.get("checks", {})),
        "failed_checks": [k for k, v in out.get("checks", {}).items()
                          if v is False],
        "phase26_checks": {
            k: out.get("checks", {}).get(k)
            for k in ("phase26TabPresent", "p26Cards", "p26GateCrits",
                      "p26MatrixRows", "p26DeltaRows", "p26GapRows",
                      "p26BarRects", "componentScrPresent",
                      "componentBootstrapCiPresent", "copulaFormGapPresent",
                      "gapToNestedPresent", "compositionImmaterialPresent",
                      "mr015FreePresent", "nestedOutsideComponentCiPresent",
                      "reaggCompositionVerdictPresent",
                      "reaggBootstrapVerdictPresent",
                      "reaggDeltaVerdictPresent")
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
                "Phase 26 Task 5 propagated the full path-wise copula "
                "re-aggregation results to the zero-install offline UI. "
                "scripts/build_ui_data.py (contract bumped ADDITIVELY to "
                "v1.8.0) now surfaces a first-class Full Re-Agg (P26) panel: "
                "(1) the Task 2 per-driver composition transform on the FROZEN "
                "t(2.9451) copula - component-basis t SCR 39,975.7 vs "
                "re-anchored (LEVEL) 39,794.3 = +0.46%, relief on the cuttable "
                "component only with the per-scenario envelope clip, governed "
                "sigma/alpha/benefit-share UNCHANGED, 6/6 gates; (2) the Task "
                "3 frozen-copula margin bootstrap (200x20k) on the FULL "
                "component basis - t SCR mean 39,595.1, 95% CI "
                "[36,676.2, 42,943.1], SE 4.07% <= 5%, with the nested "
                "path-wise reference 46,638.9 OUTSIDE the CI; the residual "
                "14.29% gap decomposes 91.9% COPULA-FORM (6,120.2 - the nested "
                "joint tail is heavier than the frozen t copula on standalone "
                "margins, exceeding the entire gaussian->t sensitivity 4,765.6) "
                "/ 8.1% relief-surface (543.0, bounded by the governed 1.16% "
                "OOS error); (3) the Task 4 paired common-random-number delta "
                "matrix - composition correction (full minus re-anchored, t) "
                "+211.5 [+46.1, +381.8], 95% CI EXCLUDES zero (statistically "
                "significant) yet max |move| 0.55% < 1% MR trigger -> "
                "MR-010/MR-014 numeric refresh NOT required, MR-015 stays "
                "free; rank invariance re-verified (df 2.9451 within 1e-4, rho "
                "max|diff| 7.2e-16). Three Phase 26 PASS verdicts and additive "
                "capital read-outs (t_copula_scr_pathwise_component, "
                "t_copula_scr_pathwise_component_bootstrap_mean) added. The UI "
                "performs no calculation; it consumes only already-produced "
                "model output JSONs. PHASE 26 COMPLETE (Tasks 1-5)."
            ),
            change_type="code_change",
            affected_components=AFFECTED_COMPONENTS,
            standard_references=STANDARD_REFERENCES,
            before_snapshot={
                "ui_contract": "1.7.0 (path-wise declaration / proxy basis / "
                               "tail-diagnostics panel; no full re-aggregation "
                               "basis matrix, component-basis bootstrap or "
                               "paired delta matrix)",
            },
            after_snapshot={
                "ui_contract": "1.8.0 (additive)",
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
                "working (Phase 25 Task 5 exact-version test pin relaxed to a "
                "version floor >= (1,7,0) - DISCLOSED forward-compat fix per "
                "repo convention). Completes the Phase 26 per-task offline-UI "
                "propagation requirement; PHASE 26 COMPLETE (Tasks 1-5)."
            ),
            quantitative_impact=(
                "UI now displays: component-basis t SCR {sc:.0f} vs re-anchored "
                "{sl:.0f} = +{cr:.2%} (composition correction); frozen-copula "
                "bootstrap mean {bm:.0f}, 95% CI [{lo:.0f}, {hi:.0f}], SE "
                "{se:.2%}; nested {nr:.0f} OUTSIDE the CI; gap {gp:.2%} "
                "decomposed {cf:.1%} copula-form / {rs:.1%} relief-surface; "
                "paired composition correction +{pc:.0f} [{pl:.0f}, {ph:.0f}] "
                "with max |move| {mm:.2%} < 1% MR trigger (not fired). jsdom "
                "self-test ok with {nc} network calls and {je} JS errors over "
                "{n} checks."
            ).format(
                sc=hr["scr_component_t"], sl=hr["scr_level_t"],
                cr=hr["component_vs_reanchored_rel"], bm=hr["bootstrap_mean"],
                lo=hr["bootstrap_ci"][0], hi=hr["bootstrap_ci"][1],
                se=hr["bootstrap_se_frac"], nr=hr["nested_reference"],
                gp=abs(hr["gap_to_nested_rel"]), cf=hr["copula_form_share"],
                rs=hr["relief_surface_share"],
                pc=hr["paired_comp_correction"][0],
                pl=hr["paired_comp_correction"][1],
                ph=hr["paired_comp_correction"][2],
                mm=hr["mr_trigger_max_abs_rel"],
                nc=st["network_calls"], je=st["js_errors"], n=st["n_checks"],
            ),
            author=ACTOR,
            phase=PHASE,
            peer_reviewer="APS_X2_Independent_Reviewer",
            assumption_owner="ChiefActuary",
        )
        rec.submit_for_peer_review(
            ACTOR,
            "UI propagation verified by the contract checks + jsdom self-test "
            "(0 network / 0 JS errors); display-layer change only. The "
            "economically-immaterial-but-statistically-significant composition "
            "correction, the copula-form-dominated residual gap, and the "
            "nested-OUTSIDE-CI disclosure are carried into the display "
            "verbatim; the copula is FROZEN per SII Art. 234.",
        )
        rec.submit_to_owner(
            ACTOR,
            "Owner review requested. PHASE 26 COMPLETE at the educational "
            "level; production sign-off remains withheld pending "
            "credentialled-data calibration and independent APS X2 review.",
        )
        store.add_change_record(rec)
        added = True
        record_id = rec.record_id
        record_status = rec.status.value
        store.audit_trail.append(
            AuditEntry.governance(
                actor=ACTOR,
                phase=PHASE,
                event=("ChangeRecord opened (OWNER_REVIEW) - Phase 26 Task 5 "
                       "offline-UI propagation; PHASE 26 COMPLETE"),
                details={
                    "record_id": rec.record_id,
                    "ui_contract": "1.8.0",
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
        "task": "Phase 26 Task 5 - offline-UI propagation",
        "phase": PHASE,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "verdict": "PASS",
        "phase26_status": "COMPLETE (Tasks 1-5)",
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
    md = """# Phase 26 Task 5 - Offline-UI Propagation Report

**Generated (UTC):** {now}
**Verdict:** PASS - **PHASE 26 COMPLETE (Tasks 1-5)**

## What the offline UI now surfaces (contract v1.8.0, additive)

A first-class **Full Re-Agg (P26)** panel:

- **Per-driver composition transform on the FROZEN copula (Task 2):**
  component-basis t SCR {sc:,.0f} vs re-anchored (LEVEL) {sl:,.0f} =
  **+{cr:.2%}**; relief on the cuttable component only with the per-scenario
  envelope clip; governed sigma 0.225 / alpha 0.7567 / benefit-share 0.8450
  UNCHANGED; copula FROZEN (df 2.9451, rho max|diff| 7.2e-16); 6/6 gates.
- **Frozen-copula margin bootstrap on the FULL component basis (Task 3):**
  t SCR mean {bm:,.0f}, 95% CI [{lo:,.0f}, {hi:,.0f}], SE **{se:.2%}** of mean
  (<= 5%); the nested path-wise reference {nr:,.0f} sits **OUTSIDE the CI** ->
  the residual **{gp:.2%}** gap decomposes **{cf:.1%} COPULA-FORM** (the
  nested joint tail is heavier than the frozen t copula on standalone margins,
  exceeding the entire gaussian->t dependence-form sensitivity) and only
  **{rs:.1%} relief-surface** (bounded by the governed 1.16% OOS error).
- **Paired common-random-number delta matrix (Task 4):** composition
  correction (full - re-anchored, t) **+{pc:,.0f} [{pl:,.0f}, {ph:,.0f}]**,
  95% CI EXCLUDES zero (statistically significant) yet max |move| **{mm:.2%}**
  < 1% MR trigger -> MR-010/MR-014 numeric refresh **NOT required**, **MR-015
  stays free**; rank invariance re-verified (df/rho frozen); management-action
  relief dominates the capital picture.
- Headline verdicts extended with the three Phase 26 PASS verdicts; additive
  capital read-outs `t_copula_scr_pathwise_component` and
  `t_copula_scr_pathwise_component_bootstrap_mean`.

**Conclusion.** The full and re-anchored bases are economically
interchangeable on the frozen copula; the material gap to the nested truth is
a copula-FORM limitation, NOT a basis-choice effect. Nested with-actions
(path-wise) remains the capital reference.

## Verification

- `ui_data.json` contract checks: ALL PASS ({nck} substantive checks).
- jsdom self-test: **ok:true**, {nc} network calls / {je} JS errors over
  {nst} checks (17 new Phase 26 checks incl. panel cards, basis matrix /
  paired-delta / gap-decomposition tables, gate grids, SCR bars).
- DISCLOSED forward-compat fix: the Phase 25 Task 5 exact-version test pin on
  "1.7.0" relaxed to a version floor >= (1,7,0) (additive bumps are the repo
  convention).

## Governance

- ChangeRecord `{crid}` ({crstatus}); audit entries {aud}; change records
  {chg}; audit-chain integrity verify_all = {integ}.
- Production sign-off remains withheld (educational classification): residual
  is credentialled-data calibration + independent APS X2 review - not a code
  gap.

**Standards:** SOA ASOP 41 s3.2; ASOP 56 s3.5; IA TAS M s3.6;
Solvency II Art. 234; Efron & Tibshirani (1993) paired bootstrap.
""".format(
        now=report["generated_utc"],
        sc=hr["scr_component_t"], sl=hr["scr_level_t"],
        cr=hr["component_vs_reanchored_rel"], bm=hr["bootstrap_mean"],
        lo=hr["bootstrap_ci"][0], hi=hr["bootstrap_ci"][1],
        se=hr["bootstrap_se_frac"], nr=hr["nested_reference"],
        gp=abs(hr["gap_to_nested_rel"]), cf=hr["copula_form_share"],
        rs=hr["relief_surface_share"],
        pc=hr["paired_comp_correction"][0], pl=hr["paired_comp_correction"][1],
        ph=hr["paired_comp_correction"][2], mm=hr["mr_trigger_max_abs_rel"],
        nck=nck, nc=st["network_calls"], je=st["js_errors"],
        nst=st["n_checks"], crid=gov["change_record_id"],
        crstatus=gov["change_record_status"],
        aud=report["governance"]["audit_entries"],
        chg=report["governance"]["change_records"], integ=integrity,
    )
    MD_PATH.write_text(md, encoding="utf-8")

    card = """# UI Propagation Card (Phase 26 Task 5) - PHASE 26 COMPLETE

- Offline UI contract bumped ADDITIVELY 1.7.0 -> 1.8.0; new Full Re-Agg (P26)
  tab consumes only model-output JSONs (zero install, 0 network, 0 JS errors).
- Task 2: full per-driver composition vs re-anchored (LEVEL) on the FROZEN
  copula - component t SCR {sc:,.0f} vs {sl:,.0f} (+{cr:.2%}); 6/6 gates.
- Task 3: frozen-copula bootstrap on the component basis - mean {bm:,.0f},
  95% CI [{lo:,.0f}, {hi:,.0f}], SE {se:.2%}; nested {nr:,.0f} OUTSIDE the CI;
  gap {gp:.2%} = {cf:.1%} copula-form / {rs:.1%} relief-surface.
- Task 4: paired composition correction +{pc:,.0f} [{pl:,.0f}, {ph:,.0f}],
  significant but < 1% MR trigger -> MR-015 stays free.
- Finding surfaced verbatim: full vs re-anchored are economically
  interchangeable on the frozen copula; the residual gap is COPULA-FORM, not
  basis-choice. Verdict: PASS - educational; production sign-off withheld.
""".format(
        sc=hr["scr_component_t"], sl=hr["scr_level_t"],
        cr=hr["component_vs_reanchored_rel"], bm=hr["bootstrap_mean"],
        lo=hr["bootstrap_ci"][0], hi=hr["bootstrap_ci"][1],
        se=hr["bootstrap_se_frac"], nr=hr["nested_reference"],
        gp=abs(hr["gap_to_nested_rel"]), cf=hr["copula_form_share"],
        rs=hr["relief_surface_share"],
        pc=hr["paired_comp_correction"][0], pl=hr["paired_comp_correction"][1],
        ph=hr["paired_comp_correction"][2],
    )
    CARD_PATH.write_text(card, encoding="utf-8")

    print(json.dumps({
        "verdict": "PASS", "phase26": "COMPLETE",
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
