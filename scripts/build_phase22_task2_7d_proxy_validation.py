#!/usr/bin/env python3
"""Phase 22 Task 2 build + governance - seven-driver proxy OOS validation.

Run staged:
  PYTHONPATH=. python3 scripts/build_phase22_task2_7d_proxy_validation.py --stage part --part fit --i0 0 --i1 2000
  PYTHONPATH=. python3 scripts/build_phase22_task2_7d_proxy_validation.py --stage part --part val --i0 0 --i1 60
  PYTHONPATH=. python3 scripts/build_phase22_task2_7d_proxy_validation.py --stage part --part inheavy --i0 0 --i1 60
  PYTHONPATH=. python3 scripts/build_phase22_task2_7d_proxy_validation.py --stage part --part nested --i0 0 --i1 250
  PYTHONPATH=. python3 scripts/build_phase22_task2_7d_proxy_validation.py --stage part --part nested --i0 250 --i1 500
  PYTHONPATH=. python3 scripts/build_phase22_task2_7d_proxy_validation.py --stage finalise
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from par_model_v2.projection.monthly_projection import ParEndowmentProduct
from par_model_v2.projection.multi_driver_proxy_validation_7d import (
    SevenDriverLiquidityProxyValidator,
    seven_driver_proxy_config,
    seven_driver_proxy_use_restrictions,
)


PHASE = "Phase 22: Proxy Hardening + Seven-Driver OOS Validation"
ACTOR = "AutomatedModelDev_Phase22"
GOV_PATH = Path(".claude-dev/GOVERNANCE_STORE.json")
OUT_DIR = Path("docs/validation")
JSON_PATH = OUT_DIR / "PHASE22_TASK2_7D_PROXY_VALIDATION_REPORT.json"
MD_PATH = OUT_DIR / "PHASE22_TASK2_7D_PROXY_VALIDATION_REPORT.md"
CARD_PATH = Path("docs/SEVEN_DRIVER_PROXY_VALIDATION_CARD.md")
STAGE_DIR = Path(".phase22_task2_stage")
CHANGE_TITLE = "Phase 22 Task 2 - seven-driver LSMC proxy extension + OOS validation"

AFFECTED_COMPONENTS = [
    "par_model_v2/projection/multi_driver_proxy_validation_7d.py",
    "tests/test_phase22_task2_seven_driver_proxy.py",
    "scripts/build_phase22_task2_7d_proxy_validation.py",
    "docs/SEVEN_DRIVER_PROXY_VALIDATION_CARD.md",
    "docs/validation/PHASE22_TASK2_7D_PROXY_VALIDATION_REPORT.{json,md}",
]

STANDARD_REFERENCES = [
    "SOA ASOP 7 section 3.3",
    "SOA ASOP 25 section 3.3",
    "SOA ASOP 56 section 3.1.3/3.5",
    "IA TAS M section 3.2/3.6",
    "IFoA proxy-modelling working party",
    "Longstaff & Schwartz (2001)",
    "Duffie-Singleton (1999)",
    "Solvency II Delegated Regulation Article 188/234",
]


def _product() -> ParEndowmentProduct:
    return ParEndowmentProduct(
        issue_age=45,
        gender="M",
        sum_assured=100000.0,
        annual_premium=5000.0,
        term_years=20,
    )


def _validator() -> SevenDriverLiquidityProxyValidator:
    return SevenDriverLiquidityProxyValidator(_product())


def _part_states(v: SevenDriverLiquidityProxyValidator, cfg, part: str):
    if part == "fit":
        return v.states(cfg.n_fit, cfg.fit_seed)
    if part == "val":
        return v.states(cfg.n_validation, cfg.validation_seed)
    if part == "inheavy":
        return v.states(cfg.n_fit, cfg.fit_seed)[: cfg.n_insample_heavy]
    if part == "nested":
        return v.states(cfg.n_eval, cfg.eval_seed)
    raise ValueError("unknown part: {}".format(part))


def stage_part(part: str, i0: int, i1: int) -> int:
    import numpy as np

    STAGE_DIR.mkdir(parents=True, exist_ok=True)
    cfg = seven_driver_proxy_config()
    v = _validator()
    X = _part_states(v, cfg, part)
    if part == "fit":
        arr = v.denoised_fit_payoffs_sliced(
            X, i0, i1, cfg.fit_seed, cfg.fit_n_inner)
    elif part == "val":
        arr = v.heavy_targets_sliced(
            X, i0, i1, cfg.n_inner_heavy, cfg.validation_seed)
    elif part == "inheavy":
        arr = v.heavy_targets_sliced(
            X, i0, i1, cfg.n_inner_heavy, cfg.insample_heavy_seed)
    elif part == "nested":
        arr = v.heavy_targets_sliced(
            X, i0, i1, cfg.nested_n_inner, cfg.nested_inner_seed)
    else:
        raise ValueError("unknown part: {}".format(part))
    np.savez(STAGE_DIR / "{}_{:05d}_{:05d}.npz".format(part, i0, i1), arr=arr)
    print("stage {} [{}, {}) done".format(part, i0, i1))
    return 0


def _assemble_precomputed():
    import numpy as np

    cfg = seven_driver_proxy_config()
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
    pre = {}
    for part, n in sizes.items():
        full = np.full(n, np.nan)
        for f in sorted(STAGE_DIR.glob(part + "_*.npz")):
            i0, i1 = (int(x) for x in f.stem.split("_")[-2:])
            full[i0:i1] = np.load(f)["arr"]
        if np.isnan(full).any():
            raise RuntimeError("staged slices for {} do not cover [0, {})".format(part, n))
        pre[keys[part]] = full
    return pre


def _markdown(report: Dict[str, Any]) -> str:
    rep = report["validation"]
    row = rep["selected_row"]
    cap = rep["capital_comparison"]
    liq = rep["liquidity_axis_evidence"]
    rows = "\n".join(
        "| {} | ({}, {}) | {} | {:.4f} | {:.1f} | {:.4f} |".format(
            r["fx_mode"], r["degree"], r["max_interaction_order"],
            r["n_basis_terms"], r["oos_r2"], r["oos_rmse"], r["overfit_gap"]
        )
        for r in rep["basis_rows"]
    )
    return """# Phase 22 Task 2 - Seven-Driver Proxy OOS Validation

Run: {ts}

## Verdict: {verdict}

Selected surface: **{mode}**, degree {deg}, max interaction {mi}, {terms} terms.
Liquidity enters as an analytic CIR-affine forced-sale haircut offset; FX enters
as the CIP-exact translation offset.

| fx_mode | (deg, max_int) | terms | OOS R2 | OOS RMSE | overfit gap |
| --- | --- | --- | --- | --- | --- |
{rows}

## Capital comparison

* Proxy VaR99.5: {pvar:.1f} vs nested {nvar:.1f} (rel err {var:.2%})
* Proxy ES: {pes:.1f} vs nested {nes:.1f} (rel err {es:.2%})
* SCR rel err: {scr:.2%}
* Nested benchmark: n_outer={no}, nested_n_inner={ni}

## Liquidity analytic feature

* Offset max abs error: {liqerr:.3e}
* Baseline liquidity impact: {base:.3e}
* Exposure notional: {notional:.0f}; tau={tau:.1f} years; initial premium={prem:.4%}

## Leakage / reproducibility

* Leakage-free: {leak}
* Reproducibility digest: `{digest}`

## Governance

* ChangeRecord: {crid} ({crstatus})
* MR-011: {mr11}; MR-012: {mr12}
* Audit integrity: {audit}

## Notes

{notes}
""".format(
        ts=report["run_timestamp"],
        verdict=rep["verdict"],
        mode=row["fx_mode"],
        deg=row["degree"],
        mi=row["max_interaction_order"],
        terms=row["n_basis_terms"],
        rows=rows,
        pvar=cap["proxy_capital"]["var_liability"],
        nvar=cap["nested_capital"]["var_liability"],
        var=cap["var_rel_error"],
        pes=cap["proxy_capital"]["es_liability"],
        nes=cap["nested_capital"]["es_liability"],
        es=cap["es_rel_error"],
        scr=cap["scr_rel_error"],
        no=cap["nested_n_outer"],
        ni=cap["nested_n_inner"],
        liqerr=liq["max_abs_offset_error"],
        base=liq["baseline_liquidity_impact"],
        notional=liq["exposure_notional"],
        tau=liq["tau_years"],
        prem=liq["initial_premium"],
        leak=rep["leakage"]["leakage_free"],
        digest=rep["reproducibility_digest"],
        crid=report["change_record_id"],
        crstatus=report["change_record_status"],
        mr11=report["risk_actions"].get("MR-011", "n/a"),
        mr12=report["risk_actions"].get("MR-012", "n/a"),
        audit=report["audit_integrity_ok"],
        notes="\n".join("* " + n for n in rep["notes"]),
    )


def _write_card(rep: Dict[str, Any]) -> None:
    row = rep["validation"]["selected_row"]
    cap = rep["validation"]["capital_comparison"]
    liq = rep["validation"]["liquidity_axis_evidence"]
    CARD_PATH.write_text(
        """# Seven-Driver Proxy Validation Card

**Phase:** 22 Task 2 - Proxy hardening + seven-driver OOS validation

**Status:** EDUCATIONAL. ChangeRecord at OWNER_REVIEW; production sign-off
withheld pending credentialled calibration and independent APS X2 review.

## Result

Seven-driver proxy validation verdict: **{verdict}**. Selected surface:
{mode}, degree {deg}, max interaction {mi}, {terms} terms.

| Metric | Value |
|---|---:|
| OOS R2 | {r2:.4f} |
| OOS RMSE | {rmse:.1f} |
| VaR rel error | {var:.2%} |
| ES rel error | {es:.2%} |
| SCR rel error | {scr:.2%} |
| Liquidity offset max error | {liqerr:.3e} |

## Design

The seventh driver is the calibrated CIR++ liquidity premium. It enters as an
analytic CIR-affine forced-sale haircut feature rather than a learned noisy
coefficient. FX remains a CIP-exact analytic offset. The polynomial surface is
selected on a disjoint-seed hold-out by OOS RMSE.

## Limitations

Educational only. Liquidity exposure notional and 7x7 liquidity couplings remain
placeholder assumptions until Phase 22 Task 3. The surface is valid only over
the fitted state region; no production capital use before credentialled data and
independent APS X2 review.
""".format(
            verdict=rep["validation"]["verdict"],
            mode=row["fx_mode"],
            deg=row["degree"],
            mi=row["max_interaction_order"],
            terms=row["n_basis_terms"],
            r2=row["oos_r2"],
            rmse=row["oos_rmse"],
            var=cap["var_rel_error"],
            es=cap["es_rel_error"],
            scr=cap["scr_rel_error"],
            liqerr=liq["max_abs_offset_error"],
        ),
        encoding="utf-8",
    )


def finalise() -> int:
    from par_model_v2.governance.audit_trail import (
        AuditEntry,
        ChangeRecord,
        GovernanceStore,
        MitigationStatus,
    )

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    cfg = seven_driver_proxy_config()
    store = (
        GovernanceStore.from_json(GOV_PATH.read_text(encoding="utf-8"))
        if GOV_PATH.exists() else GovernanceStore()
    )
    val = _validator().validate(
        cfg,
        precomputed=_assemble_precomputed(),
        governance_store=store,
        actor=ACTOR,
        phase=PHASE,
    )
    rep = val.to_dict()
    row = rep["selected_row"]
    cap = rep["capital_comparison"]
    passed = rep["verdict"].startswith("PASS")

    note = (
        "Phase 22 Task 2 extended the proxy validation to all seven documented "
        "drivers with liquidity as an analytic CIR-affine haircut feature: "
        "selected {mode} deg {deg}/max_int {mi}, OOS R2 {r2:.4f}, VaR/ES/SCR "
        "rel err {var:.2%}/{es:.2%}/{scr:.2%}, liquidity offset exact; verdict {verdict}."
    ).format(
        mode=row["fx_mode"],
        deg=row["degree"],
        mi=row["max_interaction_order"],
        r2=row["oos_r2"],
        var=cap["var_rel_error"],
        es=cap["es_rel_error"],
        scr=cap["scr_rel_error"],
        verdict="PASS" if passed else "PARTIAL",
    )
    risk_actions = {}
    for rid in ("MR-011", "MR-012"):
        try:
            store.risk_register.get(rid).update_mitigation(
                MitigationStatus.MITIGATED if passed else MitigationStatus.IN_PROGRESS,
                notes=note,
            )
            risk_actions[rid] = "refreshed"
        except KeyError:
            risk_actions[rid] = "missing"

    existing = [r for r in store.change_records if r.title == CHANGE_TITLE]
    if existing:
        record_id = existing[0].record_id
        record_status = existing[0].status.value
    else:
        rec = ChangeRecord.create(
            title=CHANGE_TITLE,
            description=(
                "Extend the LSMC proxy validation to the seventh driver "
                "(calibrated CIR++ liquidity premium). The liquidity term is "
                "entered as an analytic CIR-affine forced-sale haircut offset; "
                "FX remains a CIP-exact offset; the stochastic valuation surface "
                "is selected by disjoint-seed OOS RMSE."
            ),
            change_type="methodology_change",
            affected_components=AFFECTED_COMPONENTS,
            standard_references=STANDARD_REFERENCES,
            before_snapshot={
                "proxy_validation": "six-driver remediated OOS PASS; liquidity outside proxy validation",
            },
            after_snapshot={
                "proxy_validation": "seven-driver OOS {}".format("PASS" if passed else "PARTIAL"),
                "selected_surface": row,
                "capital_comparison": cap,
                "liquidity_axis_evidence": rep["liquidity_axis_evidence"],
            },
            impact_assessment=(
                "Validation-evidence change. Extends proxy OOS validation coverage "
                "to all documented drivers without changing the Phase 21 aggregation "
                "or production outputs."
            ),
            quantitative_impact=(
                "OOS R2 {r2:.4f}; OOS RMSE {rmse:.1f}; VaR/ES/SCR rel err "
                "{var:.2%}/{es:.2%}/{scr:.2%}; liquidity offset error {liq:.2e}; "
                "n_fit={nf}, fit_n_inner={fni}, n_eval={ne}, nested_n_inner={ni}."
            ).format(
                r2=row["oos_r2"],
                rmse=row["oos_rmse"],
                var=cap["var_rel_error"],
                es=cap["es_rel_error"],
                scr=cap["scr_rel_error"],
                liq=rep["liquidity_axis_evidence"]["max_abs_offset_error"],
                nf=cfg.n_fit,
                fni=cfg.fit_n_inner,
                ne=cfg.n_eval,
                ni=cfg.nested_n_inner,
            ),
            author=ACTOR,
            phase=PHASE,
            peer_reviewer="APS_X2_Independent_Reviewer",
            assumption_owner="ChiefActuary",
        )
        rec.submit_for_peer_review(
            ACTOR,
            "Seven-driver proxy OOS validation staged with exact liquidity offset; "
            "credentialled liquidity exposure/coupling calibration remains pending.",
        )
        rec.submit_to_owner(
            ACTOR,
            "Owner review requested. Production sign-off withheld pending Phase 22 "
            "Tasks 3-5 and independent APS X2 review.",
        )
        store.add_change_record(rec)
        record_id = rec.record_id
        record_status = rec.status.value
        store.audit_trail.append(
            AuditEntry.governance(
                actor=ACTOR,
                phase=PHASE,
                event="ChangeRecord opened (OWNER_REVIEW) - seven-driver proxy validation",
                details={
                    "record_id": rec.record_id,
                    "verdict": rep["verdict"][:160],
                    "selected_surface": row,
                    "risk_actions": risk_actions,
                    "affected_components": AFFECTED_COMPONENTS,
                },
            )
        )

    audit_ok = store.audit_trail.verify_all()
    if GOV_PATH.exists():
        GOV_PATH.write_text(store.to_json() + "\n", encoding="utf-8")

    report = {
        "run_timestamp": datetime.now(timezone.utc).isoformat(),
        "phase": PHASE,
        "task": "Task 2 - Seven-driver LSMC proxy extension + OOS validation",
        "validation": rep,
        "affected_components": AFFECTED_COMPONENTS,
        "standard_references": STANDARD_REFERENCES,
        "change_record_id": record_id,
        "change_record_status": record_status,
        "risk_actions": risk_actions,
        "audit_integrity_ok": bool(audit_ok),
        "change_records_total": len(store.change_records),
        "use_restrictions": seven_driver_proxy_use_restrictions(),
    }
    report["markdown"] = _markdown(report)
    _write_card(report)
    JSON_PATH.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    MD_PATH.write_text(report["markdown"], encoding="utf-8")

    print("verdict:", rep["verdict"])
    print("selected:", row["fx_mode"], row["degree"], row["max_interaction_order"], row["n_basis_terms"])
    print("capital rel err VaR/ES/SCR: {:.4f}/{:.4f}/{:.4f}".format(
        cap["var_rel_error"], cap["es_rel_error"], cap["scr_rel_error"]))
    print("change record:", record_id, record_status)
    print("audit integrity:", audit_ok)
    return 0 if (passed and audit_ok) else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", choices=["part", "finalise"], required=True)
    ap.add_argument("--part", choices=["fit", "val", "inheavy", "nested"])
    ap.add_argument("--i0", type=int, default=0)
    ap.add_argument("--i1", type=int, default=0)
    args = ap.parse_args()
    if args.stage == "part":
        if not args.part:
            ap.error("--part required with --stage part")
        return stage_part(args.part, args.i0, args.i1)
    return finalise()


if __name__ == "__main__":
    sys.exit(main())
