#!/usr/bin/env python3
"""Phase 24 Task 3 -- inner-path management-action dynamics prototype.

Staged build:
  PYTHONPATH=/var/tmp/pylibs:. python3 scripts/build_phase24_task3_inner_path_actions.py --stage validate
  PYTHONPATH=/var/tmp/pylibs:. python3 scripts/build_phase24_task3_inner_path_actions.py --stage actions
  PYTHONPATH=/var/tmp/pylibs:. python3 scripts/build_phase24_task3_inner_path_actions.py --stage governance

The prototype applies the governed Phase 23 Task 3 bonus-cut decision to the
projected cuttable bonus-cashflow PV inside the conditional liability, rather
than only applying an outer-node transform to the full liability.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
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
)
from par_model_v2.projection.inner_path_actions import (
    InnerPathActionConfig,
    inner_path_use_restrictions,
    validate_inner_path_actions,
)
from par_model_v2.projection.management_actions import ManagementActionRule
from par_model_v2.projection.monthly_projection import ParEndowmentProduct
from par_model_v2.projection.multi_driver_proxy_validation_6d import _fit_hex_surface
from par_model_v2.projection.multi_driver_proxy_validation_7d import (
    SevenDriverLiquidityProxyValidator,
    seven_driver_proxy_config,
)

PHASE = "Phase 24: With-Actions Aggregation Consistency + Inner-Path Action Dynamics"
ACTOR = "AutomatedModelDev_Phase24"
GOV_PATH = Path(".claude-dev/GOVERNANCE_STORE.json")
OUT_DIR = Path("docs/validation")
JSON_PATH = OUT_DIR / "PHASE24_TASK3_INNER_PATH_SCALAR_RESPONSE_VARIANT_REPORT.json"
MD_PATH = OUT_DIR / "PHASE24_TASK3_INNER_PATH_SCALAR_RESPONSE_VARIANT_REPORT.md"
CARD_PATH = Path("docs/INNER_PATH_ACTION_DYNAMICS_CARD.md")
P22T2_STAGE = Path(".phase22_task2_stage")
P22T2_REPORT = OUT_DIR / "PHASE22_TASK2_7D_PROXY_VALIDATION_REPORT.json"
P23T3_REPORT = OUT_DIR / "PHASE23_TASK3_MANAGEMENT_ACTION_REPORT.json"
P24T1_REPORT = OUT_DIR / "PHASE24_TASK1_DESIGN_NOTE.json"
TMP_ROOT = Path(os.environ.get("PHASE24_STAGE_ROOT", r"C:\tmp"))
STAGE_DIR = TMP_ROOT / "p24t3_stage"
ARRAYS_PATH = STAGE_DIR / "arrays.npz"
CROSSCHECK_PATH = STAGE_DIR / "crosscheck.json"

CHANGE_TITLE = (
    "Phase 24 Task 3 - inner-path management-action dynamics prototype "
    "(bonus cashflow response)"
)

AFFECTED_COMPONENTS = [
    "par_model_v2/projection/inner_path_actions.py",
    "scripts/build_phase24_task3_inner_path_actions.py",
    "tests/test_phase24_task3_inner_path_actions.py",
    "docs/INNER_PATH_ACTION_DYNAMICS_CARD.md",
    "docs/validation/PHASE24_TASK3_INNER_PATH_SCALAR_RESPONSE_VARIANT_REPORT.{json,md}",
]

STANDARD_REFERENCES = [
    "Solvency II Delegated Regulation Article 23 (future management actions)",
    "SOA ASOP 56 section 3.1.3/3.4/3.5",
    "SOA ASOP 25 section 3.3",
    "IA TAS M section 3.2/3.6",
    "IFoA with-profits / management-actions practice notes",
]


def _product() -> ParEndowmentProduct:
    return ParEndowmentProduct(
        issue_age=45,
        gender="M",
        sum_assured=100000.0,
        annual_premium=5000.0,
        term_years=20,
    )


def _assemble_precomputed(cfg) -> Dict[str, np.ndarray]:
    sizes = {
        "fit": cfg.n_fit,
        "val": cfg.n_validation,
        "inheavy": cfg.n_insample_heavy,
        "nested": cfg.n_eval,
    }
    keys = {
        "fit": "fit_y5",
        "val": "val_truth5",
        "inheavy": "insample_truth5",
        "nested": "nested_l5",
    }
    pre: Dict[str, np.ndarray] = {}
    for part, n in sizes.items():
        full = np.full(n, np.nan)
        for f in sorted(P22T2_STAGE.glob(part + "_*.npz")):
            i0, i1 = (int(x) for x in f.stem.split("_")[-2:])
            full[i0:i1] = np.load(f)["arr"]
        if np.isnan(full).any():
            raise RuntimeError("staged slices for {} do not cover [0,{})".format(part, n))
        pre[keys[part]] = full
    return pre


def stage_validate() -> int:
    t0 = time.monotonic()
    STAGE_DIR.mkdir(parents=True, exist_ok=True)
    cfg = seven_driver_proxy_config()
    validator = SevenDriverLiquidityProxyValidator(_product())
    pre = _assemble_precomputed(cfg)
    rep = validator.validate(config=cfg, precomputed=pre)
    archived = json.loads(P22T2_REPORT.read_text(encoding="utf-8"))
    arc = archived["validation"]
    arc_row = arc["selected_row"]
    arc_cap = arc["capital_comparison"]
    sel = rep.selected_row()

    def _close(a: float, b: float, tol: float = 1e-9) -> bool:
        return abs(float(a) - float(b)) <= tol * max(1.0, abs(float(b)))

    checks = {
        "selected_surface_match": (
            sel.fx_mode == arc_row["fx_mode"]
            and sel.degree == arc_row["degree"]
            and sel.max_interaction_order == arc_row["max_interaction_order"]
        ),
        "oos_r2_match": _close(sel.oos_r2, arc_row["oos_r2"], 1e-5),
        "nested_var_match": _close(
            rep.capital_comparison.nested_capital.var_liability,
            arc_cap["nested_capital"]["var_liability"],
        ),
        "proxy_var_match": _close(
            rep.capital_comparison.proxy_capital.var_liability,
            arc_cap["proxy_capital"]["var_liability"],
        ),
        "verdict_pass_without_actions": rep.verdict.startswith("PASS"),
    }
    if not all(checks.values()):
        raise RuntimeError("archive cross-check failed: " + json.dumps(checks))

    fit_X = validator.states(cfg.n_fit, cfg.fit_seed)
    val_X = validator.states(cfg.n_validation, cfg.validation_seed)
    eval_X = validator.states(cfg.n_eval, cfg.eval_seed)
    fit_y5 = pre["fit_y5"]
    surf = _fit_hex_surface(
        fit_X[:, :6],
        fit_y5,
        validator.fx_term(fit_X),
        sel.degree,
        sel.max_interaction_order,
        fx_mode=sel.fx_mode,
    )
    val_truth = pre["val_truth5"] + validator.fx_term(val_X) + validator.liquidity_term(val_X)
    val_pred = validator._predict_l7(surf, val_X)
    nested_l = pre["nested_l5"] + validator.fx_term(eval_X) + validator.liquidity_term(eval_X)
    proxy_l = validator._predict_l7(surf, eval_X)
    fit_l7 = fit_y5 + validator.fx_term(fit_X) + validator.liquidity_term(fit_X)
    fit_mean = float(fit_l7.mean())
    checks["refit_proxy_var_match"] = _close(
        float(np.quantile(proxy_l, cfg.confidence_level)),
        arc_cap["proxy_capital"]["var_liability"],
    )
    if not checks["refit_proxy_var_match"]:
        raise RuntimeError("refit proxy surface did not reproduce archived VaR")

    np.savez(
        ARRAYS_PATH,
        val_truth=val_truth,
        val_pred=val_pred,
        nested_l=nested_l,
        proxy_l=proxy_l,
        fit_mean=np.array([fit_mean]),
    )
    CROSSCHECK_PATH.write_text(
        json.dumps(
            {
                "checks": checks,
                "selected_surface": {
                    "fx_mode": sel.fx_mode,
                    "degree": sel.degree,
                    "max_interaction_order": sel.max_interaction_order,
                    "n_basis_terms": sel.n_basis_terms,
                    "oos_r2_without_actions": sel.oos_r2,
                },
                "fit_mean_liability": fit_mean,
                "archived_report": str(P22T2_REPORT),
                "config": cfg.to_dict(),
                "duration_seconds": time.monotonic() - t0,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print("validate stage OK:", json.dumps(checks))
    return 0


def _digest(arrs: Dict[str, np.ndarray], cfg: InnerPathActionConfig) -> str:
    h = hashlib.sha256()
    for k in sorted(arrs):
        h.update(k.encode("utf-8"))
        h.update(np.ascontiguousarray(arrs[k]).tobytes())
    h.update(json.dumps(cfg.to_dict(), sort_keys=True).encode("utf-8"))
    return h.hexdigest()


def stage_actions() -> int:
    t0 = time.monotonic()
    data = np.load(ARRAYS_PATH)
    cross = json.loads(CROSSCHECK_PATH.read_text(encoding="utf-8"))
    cfg = seven_driver_proxy_config()
    rule = ManagementActionRule()
    ip_cfg = InnerPathActionConfig()
    arrs = {k: data[k] for k in ("val_truth", "val_pred", "nested_l", "proxy_l")}
    fit_mean = float(data["fit_mean"][0])
    result = validate_inner_path_actions(
        rule,
        fit_mean,
        arrs["val_truth"],
        arrs["val_pred"],
        arrs["nested_l"],
        arrs["proxy_l"],
        cfg.confidence_level,
        cfg.capital_horizon_months,
        ip_cfg,
    )
    p23 = json.loads(P23T3_REPORT.read_text(encoding="utf-8"))["result"]
    design = json.loads(P24T1_REPORT.read_text(encoding="utf-8"))
    result["task1_acceptance_criteria"] = design["task3_acceptance_criteria"]
    result["phase23_outer_node_reference"] = {
        "nested_var_with": p23["nested_capital_with"]["var_liability"],
        "nested_scr_with": p23["nested_capital_with"]["scr_proxy"],
        "oos_r2_with_actions": p23["oos_r2_with_actions"],
        "var_rel_error_with_actions": p23["var_rel_error_with_actions"],
    }
    out = {
        "task": CHANGE_TITLE,
        "phase": PHASE,
        "run_timestamp": datetime.now(timezone.utc).isoformat(),
        "run_id": "p24t3-" + _digest(arrs, ip_cfg)[:8],
        "verdict": result["verdict"],
        "result": result,
        "without_actions_crosscheck": cross,
        "method": (
            "Prototype decomposes L into guaranteed/non-cuttable PV plus "
            "cuttable bonus-cashflow PV = bonus_share * L. The governed "
            "retained-bonus factor is evaluated on the pre-action coverage "
            "ratio, then applied to that bonus-cashflow PV with a one-year "
            "response factor. The same basis is applied to nested truth and "
            "proxy prediction."
        ),
        "limitations": [
            "Horizon-level prototype only; no monthly path-wise bonus "
            "declaration loop.",
            "Bonus cashflow response factor 0.85 is an educational placeholder "
            "for recognition lag / already-vested bonus inertia.",
            "Reference assets remain the fixed leakage-free Phase 23 proxy.",
        ],
        "use_restrictions": inner_path_use_restrictions(),
        "affected_components": AFFECTED_COMPONENTS,
        "standard_references": STANDARD_REFERENCES,
        "reproducibility_digest": _digest(arrs, ip_cfg),
        "duration_seconds": time.monotonic() - t0,
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    JSON_PATH.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    MD_PATH.write_text(_markdown(out), encoding="utf-8")
    CARD_PATH.write_text(_card(out), encoding="utf-8")
    json.loads(JSON_PATH.read_text(encoding="utf-8"))
    print("actions stage OK; verdict {} gates {}".format(result["verdict"], result["gates"]))
    return 0 if result["verdict"] == "PASS" else 1


def _markdown(rep: Dict[str, Any]) -> str:
    r = rep["result"]
    g = r["gates"]
    nw = r["nested_capital_without"]
    ni = r["nested_capital_inner_path"]
    pi = r["proxy_capital_inner_path"]
    no = r["nested_capital_outer_node"]
    gates = "\n".join("* {}: {}".format(k, "PASS" if v else "FAIL") for k, v in g.items())
    lims = "\n".join("* " + x for x in rep["limitations"])
    return """# Phase 24 Task 3 - Inner-Path Management-Action Dynamics Prototype

Run: {ts}

## Verdict: {verdict}

The governed bonus-cut decision is applied to the projected cuttable bonus
cashflow PV, not only as an outer-node transform of the full liability.
Response factor: {resp:.0%}; max cashflow relief at floor:
bonus_share {bs:.0%} x (1-PRE {pf:.0%}) x response {resp:.0%} = {eff:.1%}.

## Fixed Task 1 gates

{gates}

## Capital impact (nested ground truth)

| basis | mean | VaR99.5 | ES | SCR |
| --- | --- | --- | --- | --- |
| without actions | {wo_mean:.1f} | {wo_var:.1f} | {wo_es:.1f} | {wo_scr:.1f} |
| outer-node Phase 23 basis | {o_mean:.1f} | {o_var:.1f} | {o_es:.1f} | {o_scr:.1f} |
| **inner-path cashflow basis** | **{i_mean:.1f}** | **{i_var:.1f}** | **{i_es:.1f}** | **{i_scr:.1f}** |

Outer-node vs inner-path delta: VaR {dvar:.1f}, SCR {dscr:.1f};
positive means the cashflow basis gives less immediate relief than the
Phase 23 outer-node transform.

## Proxy OOS re-validation

* OOS R2: {r2:.4f}
* Proxy VaR99.5: {pvar:.1f} vs nested {nvar:.1f}; rel err {vrel:.2%}
* ES rel err {esrel:.2%}; SCR rel err {scrrel:.2%}
* Active share {act:.1%}; floor share {flo:.1%}

## Provenance

The same Phase 22 Task 2 staged primitives and selected seven-driver proxy
surface were cross-checked before use. Cross-checks: {cross}.

## Limitations

{lims}

Digest `{digest}`.
""".format(
        ts=rep["run_timestamp"],
        verdict=rep["verdict"],
        resp=r["config"]["bonus_cashflow_response"],
        bs=r["rule"]["bonus_share"],
        pf=r["rule"]["pre_floor"],
        eff=r["rule"]["max_relief"] * r["config"]["bonus_cashflow_response"],
        gates=gates,
        wo_mean=nw["mean_liability"],
        wo_var=nw["var_liability"],
        wo_es=nw["es_liability"],
        wo_scr=nw["scr_proxy"],
        o_mean=no["mean_liability"],
        o_var=no["var_liability"],
        o_es=no["es_liability"],
        o_scr=no["scr_proxy"],
        i_mean=ni["mean_liability"],
        i_var=ni["var_liability"],
        i_es=ni["es_liability"],
        i_scr=ni["scr_proxy"],
        dvar=r["outer_node_vs_inner_path"]["nested_var_delta"],
        dscr=r["outer_node_vs_inner_path"]["nested_scr_delta"],
        r2=r["oos_r2_inner_path"],
        pvar=pi["var_liability"],
        nvar=ni["var_liability"],
        vrel=r["var_rel_error_inner_path"],
        esrel=r["es_rel_error_inner_path"],
        scrrel=r["scr_rel_error_inner_path"],
        act=r["active_share_nested"],
        flo=r["floor_share_nested"],
        cross=sum(rep["without_actions_crosscheck"]["checks"].values()),
        lims=lims,
        digest=rep["reproducibility_digest"],
    )


def _card(rep: Dict[str, Any]) -> str:
    r = rep["result"]
    ni = r["nested_capital_inner_path"]
    no = r["nested_capital_outer_node"]
    return """# Inner-Path Action Dynamics Card (Phase 24 Task 3)

**{verdict}.** The governed management-action rule now enters a horizon-level
inner-path cashflow basis: cuttable bonus PV = bonus_share x liability, with
the retained-bonus factor applied to that cashflow component.

Response factor {resp:.0%}; inner-path nested SCR {iscr:.0f} vs outer-node
{oscr:.0f}; OOS R2 {r2:.4f}; VaR rel err {vrel:.2%}.

Residual: no monthly path-wise declaration loop; parameters remain
educational placeholders pending credentialled practice data and APS X2
review.

Evidence: docs/validation/PHASE24_TASK3_INNER_PATH_SCALAR_RESPONSE_VARIANT_REPORT.{{json,md}}
""".format(
        verdict=rep["verdict"],
        resp=r["config"]["bonus_cashflow_response"],
        iscr=ni["scr_proxy"],
        oscr=no["scr_proxy"],
        r2=r["oos_r2_inner_path"],
        vrel=r["var_rel_error_inner_path"],
    )


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

    build_dir = TMP_ROOT / "p24t3_build"
    build_dir.mkdir(parents=True, exist_ok=True)
    (build_dir / "GOV_BACKUP_pre_p24t3.json").write_text(
        store.to_json() + "\n", encoding="utf-8"
    )

    store.risk_register.get("MR-014").update_mitigation(
        MitigationStatus.MITIGATED,
        notes=(
            "Phase 24 Task 3 refresh: inner-path management-action prototype "
            "applies the bonus cut to projected cuttable bonus-cashflow PV "
            "(response {resp:.0%}) instead of only as an outer-node full-liability "
            "transform. OOS R2 {r2:.4f}; VaR rel err {vrel:.2%}; nested SCR "
            "inner-path {iscr:.0f} vs outer-node {oscr:.0f}; gates {ng}/4 PASS. "
            "Residual remains full monthly path-wise declaration and "
            "credentialled management-practice parameters."
        ).format(
            resp=r["config"]["bonus_cashflow_response"],
            r2=r["oos_r2_inner_path"],
            vrel=r["var_rel_error_inner_path"],
            iscr=r["nested_capital_inner_path"]["scr_proxy"],
            oscr=r["nested_capital_outer_node"]["scr_proxy"],
            ng=sum(r["gates"].values()),
        ),
    )

    rec = ChangeRecord.create(
        title=CHANGE_TITLE,
        description=(
            "Implemented the Phase 24 Task 3 horizon-level inner-path "
            "management-action prototype: the governed bonus-cut decision is "
            "applied to cuttable projected bonus-cashflow PV inside the "
            "conditional liability decomposition, with the same analytic "
            "basis applied to nested truth and proxy prediction."
        ),
        change_type="assumption_change",
        affected_components=AFFECTED_COMPONENTS,
        standard_references=STANDARD_REFERENCES,
        before_snapshot={
            "basis": "Phase 23 outer-node full-liability transform",
            "nested_scr_outer_node": r["nested_capital_outer_node"]["scr_proxy"],
            "oos_r2_outer_node": r["phase23_outer_node_reference"]["oos_r2_with_actions"],
        },
        after_snapshot={
            "basis": "Phase 24 inner-path cuttable bonus-cashflow response",
            "response_factor": r["config"]["bonus_cashflow_response"],
            "nested_scr_inner_path": r["nested_capital_inner_path"]["scr_proxy"],
            "oos_r2_inner_path": r["oos_r2_inner_path"],
            "var_rel_error_inner_path": r["var_rel_error_inner_path"],
            "gates": r["gates"],
            "verdict": rep["verdict"],
            "reproducibility_digest": rep["reproducibility_digest"],
        },
        impact_assessment=(
            "Additive assumption-method prototype. It relaxes the immediate "
            "outer-node action approximation while preserving the archived "
            "without-actions and Phase 23 with-actions evidence. Production "
            "use remains prohibited."
        ),
        quantitative_impact=(
            "Nested SCR inner-path {iscr:.1f} vs outer-node {oscr:.1f}; "
            "VaR rel err {vrel:.2%}; OOS R2 {r2:.4f}; active share {act:.1%}."
        ).format(
            iscr=r["nested_capital_inner_path"]["scr_proxy"],
            oscr=r["nested_capital_outer_node"]["scr_proxy"],
            vrel=r["var_rel_error_inner_path"],
            r2=r["oos_r2_inner_path"],
            act=r["active_share_nested"],
        ),
        author=ACTOR,
        phase=PHASE,
        peer_reviewer="APS_X2_Independent_Reviewer",
        assumption_owner="ChiefActuary",
    )
    rec.submit_for_peer_review(
        ACTOR,
        "Task 1 pre-registered inner-path OOS gates pass; outer-node vs "
        "inner-path delta disclosed; residual monthly declaration loop noted.",
    )
    rec.submit_to_owner(
        ACTOR,
        "Owner review requested. Production sign-off withheld pending "
        "credentialled management-practice data and APS X2 review.",
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
            "inner-path action: OOS R2 {r2:.4f}; VaR rel err {vrel:.2%}; "
            "nested SCR {iscr:.1f}; gates {ng}/4 PASS"
        ).format(
            r2=r["oos_r2_inner_path"],
            vrel=r["var_rel_error_inner_path"],
            iscr=r["nested_capital_inner_path"]["scr_proxy"],
            ng=sum(r["gates"].values()),
        ),
    )
    store.audit_trail.append(entry)
    ok = store.audit_trail.verify_all()
    GOV_PATH.write_text(store.to_json() + "\n", encoding="utf-8")

    rep["change_record_id"] = rec.record_id
    rep["change_record_status"] = rec.status.value if hasattr(rec.status, "value") else str(rec.status)
    rep["mr014_refreshed"] = True
    rep["audit_integrity_ok"] = ok
    rep["change_records_total"] = len(store.change_records)
    JSON_PATH.write_text(json.dumps(rep, indent=2) + "\n", encoding="utf-8")
    MD_PATH.write_text(_markdown(rep), encoding="utf-8")
    print("ChangeRecord {} ({}); MR-014 refreshed; verify_all {}".format(
        rec.record_id, rep["change_record_status"], ok
    ))
    return 0 if ok else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", choices=["validate", "actions", "governance"], required=True)
    args = parser.parse_args()
    sys.exit(
        {"validate": stage_validate, "actions": stage_actions, "governance": stage_governance}[
            args.stage
        ]()
    )
