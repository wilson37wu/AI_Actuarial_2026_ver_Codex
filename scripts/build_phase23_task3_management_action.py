#!/usr/bin/env python3
"""Phase 23 Task 3 build + governance - management-action rule (dynamic bonus cut).

The rule is the deterministic outer-node transform designed in Task 1: it is
applied to the NESTED conditional liability (ground truth) and, identically, to
the LSMC proxy prediction as an analytic post-composition basis feature (the
same pattern as the FX / liquidity analytic offsets).  All heavy inner-path
arrays are reused BIT-IDENTICALLY from the archived Phase 22 Task 2 stage
(.phase22_task2_stage), cross-checked against the archived report before use.

Run staged (each stage < 45 s):
  PYTHONPATH=/var/tmp/pylibs:. python3 scripts/build_phase23_task3_management_action.py --stage validate
  PYTHONPATH=/var/tmp/pylibs:. python3 scripts/build_phase23_task3_management_action.py --stage actions
  PYTHONPATH=/var/tmp/pylibs:. python3 scripts/build_phase23_task3_management_action.py --stage governance
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

import numpy as np

from par_model_v2.governance.audit_trail import (
    AuditEntry,
    ChangeRecord,
    GovernanceStore,
    MitigationStatus,
    RiskRating,
)
from par_model_v2.projection.management_actions import (
    ManagementActionRule,
    management_action_use_restrictions,
    validate_with_actions,
)
from par_model_v2.projection.monthly_projection import ParEndowmentProduct
from par_model_v2.projection.multi_driver_proxy_validation_6d import (
    _fit_hex_surface,
)
from par_model_v2.projection.multi_driver_proxy_validation_7d import (
    SevenDriverLiquidityProxyValidator,
    seven_driver_proxy_config,
)

PHASE = "Phase 23: Tail-Dependence Upgrade + Management Actions"
ACTOR = "AutomatedModelDev_Phase23"
GOV_PATH = Path(".claude-dev/GOVERNANCE_STORE.json")
OUT_DIR = Path("docs/validation")
JSON_PATH = OUT_DIR / "PHASE23_TASK3_MANAGEMENT_ACTION_REPORT.json"
MD_PATH = OUT_DIR / "PHASE23_TASK3_MANAGEMENT_ACTION_REPORT.md"
CARD_PATH = Path("docs/MANAGEMENT_ACTION_RULE_CARD.md")
P22T2_STAGE = Path(".phase22_task2_stage")
P22T2_REPORT = OUT_DIR / "PHASE22_TASK2_7D_PROXY_VALIDATION_REPORT.json"
STAGE_DIR = Path("/var/tmp/p23t3_stage")
ARRAYS_PATH = STAGE_DIR / "arrays.npz"
CROSSCHECK_PATH = STAGE_DIR / "crosscheck.json"

CHANGE_TITLE = (
    "Phase 23 Task 3 - management-action rule (dynamic reversionary-bonus "
    "participation cut) in nested ground truth + proxy basis"
)

AFFECTED_COMPONENTS = [
    "par_model_v2/projection/management_actions.py",
    "tests/test_phase23_task3_management_actions.py",
    "scripts/build_phase23_task3_management_action.py",
    "docs/MANAGEMENT_ACTION_RULE_CARD.md",
    "docs/validation/PHASE23_TASK3_MANAGEMENT_ACTION_REPORT.{json,md}",
]

STANDARD_REFERENCES = [
    "Solvency II Delegated Regulation Article 23 (future management actions)",
    "SOA ASOP 56 section 3.1.3/3.4/3.5",
    "SOA ASOP 25 section 3.3",
    "IA TAS M section 3.2/3.6",
    "IFoA with-profits / management-actions practice notes",
]

SENSITIVITY_TRIGGERS = (1.05, 1.10, 1.15)
TRIGGER_FLOOR_BAND = 0.20


def _product() -> ParEndowmentProduct:
    return ParEndowmentProduct(
        issue_age=45,
        gender="M",
        sum_assured=100000.0,
        annual_premium=5000.0,
        term_years=20,
    )


def _assemble_precomputed(cfg) -> Dict[str, np.ndarray]:
    sizes = {"fit": cfg.n_fit, "val": cfg.n_validation,
             "inheavy": cfg.n_insample_heavy, "nested": cfg.n_eval}
    keys = {"fit": "fit_y5", "val": "val_truth5",
            "inheavy": "insample_truth5", "nested": "nested_l5"}
    pre = {}
    for part, n in sizes.items():
        full = np.full(n, np.nan)
        for f in sorted(P22T2_STAGE.glob(part + "_*.npz")):
            i0, i1 = (int(x) for x in f.stem.split("_")[-2:])
            full[i0:i1] = np.load(f)["arr"]
        if np.isnan(full).any():
            raise RuntimeError(
                "staged slices for {} do not cover [0, {})".format(part, n))
        pre[keys[part]] = full
    return pre


def stage_validate() -> int:
    """Re-run the without-actions validation from archived primitives and
    cross-check bit-level consistency with the archived Phase 22 Task 2 report;
    persist the arrays the action stage needs."""
    t0 = time.monotonic()
    STAGE_DIR.mkdir(parents=True, exist_ok=True)
    cfg = seven_driver_proxy_config()
    v = SevenDriverLiquidityProxyValidator(_product())
    pre = _assemble_precomputed(cfg)

    rep = v.validate(config=cfg, precomputed=pre)
    archived = json.loads(P22T2_REPORT.read_text(encoding="utf-8"))
    arc_val = archived["validation"]
    arc_row = arc_val["selected_row"]
    sel = rep.selected_row()
    arc_cap = arc_val["capital_comparison"]
    cap = rep.capital_comparison

    def _close(a, b, tol=1e-9):
        return abs(float(a) - float(b)) <= tol * max(1.0, abs(float(b)))

    checks = {
        "selected_surface_match": (
            sel.fx_mode == arc_row["fx_mode"]
            and sel.degree == arc_row["degree"]
            and sel.max_interaction_order == arc_row["max_interaction_order"]
        ),
        "oos_r2_match": _close(sel.oos_r2, arc_row["oos_r2"], tol=1e-5),
        "proxy_var_match": _close(
            cap.proxy_capital.var_liability,
            arc_cap["proxy_capital"]["var_liability"]),
        "nested_var_match": _close(
            cap.nested_capital.var_liability,
            arc_cap["nested_capital"]["var_liability"]),
        "verdict_pass_without_actions": rep.verdict.startswith("PASS"),
    }
    if not all(checks.values()):
        raise RuntimeError("cross-check vs archived report failed: " +
                           json.dumps(checks))

    # rebuild arrays for the action stage (deterministic refit of the
    # archived-selected surface; same seeds, same staged inner targets)
    fit_X = v.states(cfg.n_fit, cfg.fit_seed)
    val_X = v.states(cfg.n_validation, cfg.validation_seed)
    eval_X = v.states(cfg.n_eval, cfg.eval_seed)
    fit_y5 = pre["fit_y5"]
    surf = _fit_hex_surface(
        fit_X[:, :6], fit_y5, v.fx_term(fit_X),
        sel.degree, sel.max_interaction_order, fx_mode=sel.fx_mode)
    val_truth = pre["val_truth5"] + v.fx_term(val_X) + v.liquidity_term(val_X)
    val_pred = v._predict_l7(surf, val_X)
    nested_l = pre["nested_l5"] + v.fx_term(eval_X) + v.liquidity_term(eval_X)
    proxy_l = v._predict_l7(surf, eval_X)
    fit_l7 = fit_y5 + v.fx_term(fit_X) + v.liquidity_term(fit_X)
    fit_mean = float(fit_l7.mean())

    checks["refit_var_match"] = _close(
        float(np.quantile(proxy_l, cfg.confidence_level)),
        arc_cap["proxy_capital"]["var_liability"])
    if not checks["refit_var_match"]:
        raise RuntimeError("refit surface does not reproduce archived VaR")

    np.savez(ARRAYS_PATH, val_truth=val_truth, val_pred=val_pred,
             nested_l=nested_l, proxy_l=proxy_l,
             fit_mean=np.array([fit_mean]))
    CROSSCHECK_PATH.write_text(json.dumps({
        "checks": checks,
        "archived_report": str(P22T2_REPORT),
        "selected_surface": {
            "fx_mode": sel.fx_mode, "degree": sel.degree,
            "max_interaction_order": sel.max_interaction_order,
            "n_basis_terms": sel.n_basis_terms,
            "oos_r2_without_actions": sel.oos_r2,
        },
        "fit_mean_liability": fit_mean,
        "config": cfg.to_dict(),
        "duration_seconds": time.monotonic() - t0,
    }, indent=2) + "\n", encoding="utf-8")
    print("validate stage OK; checks:", json.dumps(checks))
    return 0


def _digest(arrs: Dict[str, np.ndarray], rule: ManagementActionRule) -> str:
    h = hashlib.sha256()
    for k in sorted(arrs):
        h.update(k.encode())
        h.update(np.ascontiguousarray(arrs[k]).tobytes())
    h.update(json.dumps(rule.to_dict(), sort_keys=True).encode())
    return h.hexdigest()


def stage_actions() -> int:
    t0 = time.monotonic()
    data = np.load(ARRAYS_PATH)
    crosscheck = json.loads(CROSSCHECK_PATH.read_text(encoding="utf-8"))
    cfg = seven_driver_proxy_config()
    fit_mean = float(data["fit_mean"][0])
    arrs = {k: data[k] for k in
            ("val_truth", "val_pred", "nested_l", "proxy_l")}

    rule = ManagementActionRule()
    res = validate_with_actions(
        rule, fit_mean, arrs["val_truth"], arrs["val_pred"],
        arrs["nested_l"], arrs["proxy_l"],
        cfg.confidence_level, cfg.capital_horizon_months)

    sensitivity = []
    for trig in SENSITIVITY_TRIGGERS:
        r_s = ManagementActionRule(
            cr_trigger=trig, cr_floor=trig - TRIGGER_FLOOR_BAND)
        s = validate_with_actions(
            r_s, fit_mean, arrs["val_truth"], arrs["val_pred"],
            arrs["nested_l"], arrs["proxy_l"],
            cfg.confidence_level, cfg.capital_horizon_months)
        sensitivity.append({
            "cr_trigger": trig,
            "cr_floor": trig - TRIGGER_FLOOR_BAND,
            "active_share_nested": s["active_share_nested"],
            "nested_var_with": s["nested_capital_with"]["var_liability"],
            "nested_var_reduction": s["nested_var_reduction"],
            "nested_scr_reduction": s["nested_scr_reduction"],
            "oos_r2_with_actions": s["oos_r2_with_actions"],
            "var_rel_error_with_actions": s["var_rel_error_with_actions"],
            "verdict": s["verdict"],
        })

    report = {
        "task": "Phase 23 Task 3 - management-action rule "
                "(dynamic reversionary-bonus participation cut)",
        "phase": PHASE,
        "run_timestamp": datetime.now(timezone.utc).isoformat(),
        "run_id": "p23t3-" + _digest(arrs, rule)[:8],
        "verdict": res["verdict"],
        "result": res,
        "trigger_sensitivity": sensitivity,
        "without_actions_crosscheck": crosscheck,
        "primitives_provenance": (
            "All inner-path arrays reused bit-identically from "
            ".phase22_task2_stage (Phase 22 Task 2, seeds 42/20260607/7, "
            "nested 500x256); cross-checked against the archived report "
            "before use; the selected surface (analytic, deg 3, max_int 2) "
            "was refit deterministically from the same staged fit targets."
        ),
        "method": (
            "The management action is a deterministic outer-node transform "
            "L_with = L*(1 - bonus_share*(1-pre_floor)*(1-cut_factor(CR))) "
            "with CR = A_ref/L and cut_factor = "
            "clip((CR-CR_floor)/(CR_trigger-CR_floor),0,1); the cut decision "
            "uses the PRE-action coverage ratio. It enters the nested ground "
            "truth and, identically, the proxy prediction as an analytic "
            "post-composition basis feature (no new learned coefficients). "
            "A_ref is calibrated on the FIT-sample mean liability only "
            "(leakage-free)."
        ),
        "limitations": [
            "Trigger/floor/bonus-share/PRE/reference-coverage are educational "
            "placeholders pending credentialled management-practice data and "
            "APS X2 review.",
            "The action is applied at the outer node as a transform of the "
            "conditional liability; a full inner-path bonus mechanism "
            "(per-path declared-bonus dynamics) is a documented future "
            "refinement.",
            "Coverage ratio uses a fixed reference-asset proxy, not a "
            "projected asset portfolio at the horizon.",
        ],
        "use_restrictions": management_action_use_restrictions(),
        "reproducibility_digest": _digest(arrs, rule),
        "duration_seconds": time.monotonic() - t0,
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    JSON_PATH.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    MD_PATH.write_text(_markdown(report), encoding="utf-8")
    CARD_PATH.write_text(_card(report), encoding="utf-8")
    json.loads(JSON_PATH.read_text(encoding="utf-8"))
    print("actions stage OK; verdict:", res["verdict"],
          "; gates:", json.dumps(res["gates"]))
    return 0


def _markdown(rep: Dict[str, Any]) -> str:
    r = rep["result"]
    g = r["gates"]
    nw, nwo = r["nested_capital_with"], r["nested_capital_without"]
    pw = r["proxy_capital_with"]
    sens = "\n".join(
        "| {cr_trigger:.2f} | {cr_floor:.2f} | {active_share_nested:.1%} | "
        "{nested_var_with:.1f} | {nested_var_reduction:.1f} | "
        "{nested_scr_reduction:.1f} | {oos_r2_with_actions:.4f} | "
        "{var_rel_error_with_actions:.2%} | {verdict} |".format(**s)
        for s in rep["trigger_sensitivity"])
    gates = "\n".join("* {}: {}".format(k, "PASS" if v else "FAIL")
                      for k, v in g.items())
    lims = "\n".join("* " + x for x in rep["limitations"])
    return """# Phase 23 Task 3 - Management-Action Rule (Dynamic Bonus Cut)

Run: {ts}

## Verdict: {verdict}

Rule: `cut_factor = clip((CR - {fl:.2f}) / ({tr:.2f} - {fl:.2f}), 0, 1)`;
retained bonus = pre_floor + (1 - pre_floor) * cut_factor; max liability
relief = bonus_share * (1 - pre_floor) = {mr:.1%}.
CR = A_ref / L with A_ref = {rc:.2f} x fit-sample mean liability
({fm:.1f}) = {ar:.1f} (leakage-free).

## Gates (fixed pre-registered, Task 1 design note s5)

{gates}

## Capital impact (nested ground truth, n_outer=500, n_inner=256)

| metric | without actions | with actions | reduction |
| --- | --- | --- | --- |
| mean liability | {nwo_mean:.1f} | {nw_mean:.1f} | {dmean:.1f} |
| VaR 99.5 | {nwo_var:.1f} | {nw_var:.1f} | {dvar:.1f} |
| ES | {nwo_es:.1f} | {nw_es:.1f} | {des:.1f} |
| SCR proxy | {nwo_scr:.1f} | {nw_scr:.1f} | {dscr:.1f} |

Action active on {act:.1%} of nested outer states (at/below trigger);
{flo:.1%} at/below the floor (maximum cut).

## Proxy OOS re-validation (with actions)

* OOS R2: {r2w:.4f} (without actions: {r2wo:.4f}; gate >= 0.95)
* Proxy VaR99.5 (with actions): {pvar:.1f} vs nested {nvar:.1f} (rel err {vrel:.2%}; gate <= 10%)
* ES rel err: {esrel:.2%}; SCR rel err: {scrrel:.2%}

## Trigger sensitivity (floor = trigger - {band:.2f})

| trigger | floor | active share | nested VaR with | VaR reduction | SCR reduction | OOS R2 | VaR rel err | verdict |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
{sens}

## Provenance

{prov}

## Limitations

{lims}

## Reproducibility

* Digest: `{digest}`

*EDUCATIONAL MODEL - management-action parameters are placeholders;
production sign-off withheld pending credentialled data + APS X2 review.*
""".format(
        ts=rep["run_timestamp"], verdict=rep["verdict"],
        fl=r["rule"]["cr_floor"], tr=r["rule"]["cr_trigger"],
        mr=r["rule"]["max_relief"], rc=r["rule"]["reference_coverage"],
        fm=r["fit_mean_liability"], ar=r["reference_assets"],
        gates=gates,
        nwo_mean=nwo["mean_liability"], nw_mean=nw["mean_liability"],
        dmean=nwo["mean_liability"] - nw["mean_liability"],
        nwo_var=nwo["var_liability"], nw_var=nw["var_liability"],
        dvar=r["nested_var_reduction"],
        nwo_es=nwo["es_liability"], nw_es=nw["es_liability"],
        des=nwo["es_liability"] - nw["es_liability"],
        nwo_scr=nwo["scr_proxy"], nw_scr=nw["scr_proxy"],
        dscr=r["nested_scr_reduction"],
        act=r["active_share_nested"], flo=r["floor_share_nested"],
        r2w=r["oos_r2_with_actions"], r2wo=r["oos_r2_without_actions"],
        pvar=pw["var_liability"], nvar=nw["var_liability"],
        vrel=r["var_rel_error_with_actions"],
        esrel=r["es_rel_error_with_actions"],
        scrrel=r["scr_rel_error_with_actions"],
        band=TRIGGER_FLOOR_BAND, sens=sens,
        prov=rep["primitives_provenance"], lims=lims,
        digest=rep["reproducibility_digest"])


def _card(rep: Dict[str, Any]) -> str:
    r = rep["result"]
    return """# Management-Action Rule Card (Phase 23 Task 3)

**Rule:** dynamic reversionary-bonus participation cut under solvency stress
(Solvency II Art. 23: objective, realistic, verifiable, monotone).

* cut_factor = clip((CR - {fl:.2f}) / ({tr:.2f} - {fl:.2f}), 0, 1) (retained-bonus factor)
* CR = A_ref / L_pre_action at the outer node; A_ref = {rc:.2f} x fit-sample mean
* PRE floor: at least {pf:.0%} of participating bonus always retained
* Max liability relief: {mr:.1%}

**Verdict: {verdict}** - nested VaR99.5 reduced {dvar:.1f} ({dvarp:.2%}),
SCR proxy reduced {dscr:.1f}; OOS R2 with actions {r2:.4f}; VaR rel err {vrel:.2%}.

**Where it enters:** nested conditional liability (ground truth) AND the LSMC
proxy prediction as an analytic post-composition feature - no new learned
coefficients, no change to any governed upstream module.

**Use restrictions:** EDUCATIONAL_DEMONSTRATION_ONLY - parameters are
placeholders pending credentialled management-practice data + APS X2 review.

Evidence: docs/validation/PHASE23_TASK3_MANAGEMENT_ACTION_REPORT.{{json,md}}
""".format(
        fl=r["rule"]["cr_floor"], tr=r["rule"]["cr_trigger"],
        rc=r["rule"]["reference_coverage"], pf=r["rule"]["pre_floor"],
        mr=r["rule"]["max_relief"], verdict=rep["verdict"],
        dvar=r["nested_var_reduction"],
        dvarp=r["nested_var_reduction"]
        / r["nested_capital_without"]["var_liability"],
        dscr=r["nested_scr_reduction"], r2=r["oos_r2_with_actions"],
        vrel=r["var_rel_error_with_actions"])


def _has_change_record(store: GovernanceStore) -> bool:
    return any(r.title == CHANGE_TITLE for r in store.change_records)


def stage_governance() -> int:
    rep = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    r = rep["result"]
    store = GovernanceStore.from_json(GOV_PATH.read_text(encoding="utf-8"))

    if _has_change_record(store):
        rec = next(x for x in store.change_records if x.title == CHANGE_TITLE)
        print("already applied:", rec.record_id)
        print("audit integrity:", store.audit_trail.verify_all())
        return 0

    # MR-014: management-action omission -- open, then MITIGATED on PASS.
    mr014_action = "exists"
    try:
        store.risk_register.get("MR-014")
    except KeyError:
        store.risk_register.add(
            risk_id="MR-014",
            title="Management-action omission in liability / capital model",
            description=(
                "Policyholder options (dynamic lapse) are modelled but "
                "insurer management actions are not: reversionary-bonus "
                "participation is static, so TVOG and tail capital are "
                "biased upward relative to a realistic with-management-"
                "action basis (ASOP 56 3.1.3 asymmetry; Solvency II Art. 23)."
            ),
            category="assumption_error",
            likelihood=RiskRating.HIGH,
            impact=RiskRating.MEDIUM,
            owner="ChiefActuary",
            mitigation=(
                "Phase 23 Task 3: governed dynamic reversionary-bonus "
                "participation cut entering the nested ground truth and the "
                "proxy basis, validated OOS at fixed pre-registered gates."
            ),
            related_standard="ASOP 56 3.1.3/3.4; TAS M 3.2; SII Art. 23",
            mitigation_status=MitigationStatus.OPEN,
        )
        mr014_action = "opened"
    if rep["verdict"] == "PASS":
        store.risk_register.get("MR-014").update_mitigation(
            MitigationStatus.MITIGATED,
            notes=(
                "Phase 23 Task 3 PASS: monotone Art.-23 bonus-cut rule "
                "(trigger {tr:.2f}, floor {fl:.2f}, PRE floor {pf:.0%}, max "
                "relief {mr:.1%}) applied to nested truth + proxy; nested "
                "VaR99.5 {nwo:.0f} -> {nw:.0f}, SCR reduction {dscr:.0f}; "
                "OOS R2 with actions {r2:.4f}; VaR rel err {vrel:.2%}; all "
                "5 pre-registered gates PASS. Parameters remain educational "
                "placeholders (residual risk: parameter realism, outer-node "
                "approximation)."
            ).format(
                tr=r["rule"]["cr_trigger"], fl=r["rule"]["cr_floor"],
                pf=r["rule"]["pre_floor"], mr=r["rule"]["max_relief"],
                nwo=r["nested_capital_without"]["var_liability"],
                nw=r["nested_capital_with"]["var_liability"],
                dscr=r["nested_scr_reduction"],
                r2=r["oos_r2_with_actions"],
                vrel=r["var_rel_error_with_actions"]),
        )
        mr014_action += "+mitigated"

    rec = ChangeRecord.create(
        title=CHANGE_TITLE,
        description=(
            "Implemented Method B of the Phase 23 Task 1 design note: a "
            "dynamic reversionary-bonus participation cut under solvency "
            "stress (cut_factor = clip((CR-CR_floor)/(CR_trigger-CR_floor),"
            "0,1), PRE floor retained). The rule is a deterministic, "
            "monotone outer-node transform entering the NESTED conditional "
            "liability and, identically, the LSMC proxy prediction as an "
            "analytic post-composition basis feature. Seven-driver OOS "
            "re-validation re-ran on bit-identical Phase 22 Task 2 staged "
            "primitives after cross-checking the archived report."
        ),
        change_type="assumption_change",
        affected_components=AFFECTED_COMPONENTS,
        standard_references=STANDARD_REFERENCES,
        before_snapshot={
            "management_actions": "none (static bonus participation)",
            "nested_var_99_5": r["nested_capital_without"]["var_liability"],
            "nested_scr_proxy": r["nested_capital_without"]["scr_proxy"],
            "risk_register": "no management-action entry",
        },
        after_snapshot={
            "rule": r["rule"],
            "nested_var_99_5_with_actions":
                r["nested_capital_with"]["var_liability"],
            "nested_scr_proxy_with_actions":
                r["nested_capital_with"]["scr_proxy"],
            "oos_r2_with_actions": r["oos_r2_with_actions"],
            "var_rel_error_with_actions": r["var_rel_error_with_actions"],
            "gates": r["gates"],
            "verdict": rep["verdict"],
            "reproducibility_digest": rep["reproducibility_digest"],
        },
        impact_assessment=(
            "Additive assumption change: closes the ASOP 56 3.1.3 asymmetry "
            "(policyholder options modelled, insurer options not). No change "
            "to any governed upstream module; without-actions results remain "
            "the archived Phase 22 Task 2 evidence. Parameters are "
            "educational placeholders (disclosed)."
        ),
        quantitative_impact=(
            "Nested VaR99.5 {nwo:.1f} -> {nw:.1f} (-{dvar:.1f}); SCR proxy "
            "{swo:.1f} -> {sw:.1f} (-{dscr:.1f}); action active on {act:.1%} "
            "of outer states; OOS R2 with actions {r2:.4f}; proxy-vs-nested "
            "VaR rel err {vrel:.2%}."
        ).format(
            nwo=r["nested_capital_without"]["var_liability"],
            nw=r["nested_capital_with"]["var_liability"],
            dvar=r["nested_var_reduction"],
            swo=r["nested_capital_without"]["scr_proxy"],
            sw=r["nested_capital_with"]["scr_proxy"],
            dscr=r["nested_scr_reduction"],
            act=r["active_share_nested"], r2=r["oos_r2_with_actions"],
            vrel=r["var_rel_error_with_actions"]),
        author=ACTOR,
        phase=PHASE,
        peer_reviewer="APS_X2_Independent_Reviewer",
        assumption_owner="ChiefActuary",
    )
    rec.submit_for_peer_review(
        ACTOR,
        "Monotone Art.-23 bonus-cut rule with PRE floor; fixed pre-registered "
        "gates; bit-identical primitive reuse cross-checked; trigger "
        "sensitivity and placeholder parameters disclosed.",
    )
    rec.submit_to_owner(
        ACTOR,
        "Owner review requested. Production sign-off withheld pending "
        "credentialled management-practice data, inner-path bonus dynamics, "
        "and independent APS X2 review.",
    )
    store.add_change_record(rec)

    entry = AuditEntry.model_run(
        actor=ACTOR,
        phase=PHASE,
        run_id=rep["run_id"],
        scenario_count=500,
        duration_seconds=rep["duration_seconds"],
        outcome=rep["verdict"],
        files_changed=AFFECTED_COMPONENTS,
        test_summary=(
            "with-actions nested VaR {nw:.1f} (was {nwo:.1f}); OOS R2 "
            "{r2:.4f}; VaR rel err {vrel:.2%}; gates {ng}/5 PASS".format(
                nw=r["nested_capital_with"]["var_liability"],
                nwo=r["nested_capital_without"]["var_liability"],
                r2=r["oos_r2_with_actions"],
                vrel=r["var_rel_error_with_actions"],
                ng=sum(r["gates"].values()))
        ),
    )
    store.audit_trail.append(entry)

    ok = store.audit_trail.verify_all()
    GOV_PATH.write_text(store.to_json() + "\n", encoding="utf-8")

    rep["change_record_id"] = rec.record_id
    rep["change_record_status"] = (
        rec.status.value if hasattr(rec.status, "value") else str(rec.status))
    rep["mr014_action"] = mr014_action
    rep["audit_integrity_ok"] = ok
    rep["change_records_total"] = len(store.change_records)
    JSON_PATH.write_text(json.dumps(rep, indent=2) + "\n", encoding="utf-8")

    print("ChangeRecord {} ({}); MR-014 {}; audit entries {}; verify_all {}".format(
        rec.record_id, rep["change_record_status"], mr014_action,
        len(store.audit_trail.entries), ok))
    return 0 if ok else 1


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", choices=["validate", "actions", "governance"],
                    required=True)
    a = ap.parse_args()
    sys.exit({"validate": stage_validate, "actions": stage_actions,
              "governance": stage_governance}[a.stage]())
