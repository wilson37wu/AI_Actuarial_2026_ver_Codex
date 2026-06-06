#!/usr/bin/env python3
"""
Phase 20 Task 2 build script: G2++ swaption-surface calibration + G-SWPN gate.

Calibrates the enhanced G2++ rate driver to an educational-proxy ATM swaption
volatility grid, evaluates the G-SWPN calibration-quality gate, writes validation
evidence (JSON + Markdown), refreshes the model card, and records an OWNER_REVIEW
governance ChangeRecord plus the MR-013 residual-risk update.  Idempotent on the
governance store (it will not append a duplicate Task-2 ChangeRecord).

Run:
    PYTHONPATH=. python scripts/build_phase20_task2_swaption.py
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from par_model_v2.governance.audit_trail import (
    AuditEntry,
    ChangeRecord,
    GovernanceStore,
    MitigationStatus,
)
from par_model_v2.stochastic.g2pp_swaption import (
    educational_proxy_curve,
    educational_proxy_vol_grid,
    evaluate_g_swpn_gate,
)

PHASE = "Phase 20: Market-Consistency and Multi-Factor Uplift"
ACTOR = "AutomatedModelDev_Phase20"
GOV_PATH = Path(".claude-dev/GOVERNANCE_STORE.json")
OUT_DIR = Path("docs/validation")
JSON_PATH = OUT_DIR / "PHASE20_TASK2_G2PP_SWAPTION_REPORT.json"
MD_PATH = OUT_DIR / "PHASE20_TASK2_G2PP_SWAPTION_REPORT.md"
CARD_PATH = Path("docs/MARKET_CONSISTENT_G2PP_SWAPTION_CARD.md")
CHANGE_TITLE = "Phase 20 Task 2 - G2++ swaption-surface calibration and G-SWPN gate"

AFFECTED_COMPONENTS = [
    "par_model_v2/stochastic/g2pp_swaption.py",
    "par_model_v2/stochastic/__init__.py",
    "tests/test_phase20_g2pp_swaption.py",
    "scripts/build_phase20_task2_swaption.py",
    "docs/MARKET_CONSISTENT_G2PP_SWAPTION_CARD.md",
    "docs/validation/PHASE20_TASK2_G2PP_SWAPTION_REPORT.{json,md}",
]

STANDARD_REFERENCES = [
    "SOA ASOP 56 section 3.1.3",
    "SOA ASOP 56 section 3.5",
    "SOA ASOP 56 section 4.1",
    "IA TAS M section 3.5",
    "IA TAS M section 3.6",
    "Solvency II Delegated Regulation Article 22",
    "Solvency II Delegated Regulation Article 77",
]


def _has_change_record(store: GovernanceStore) -> bool:
    return any(r.title == CHANGE_TITLE for r in store.change_records)


def _refresh_mr013(store: GovernanceStore, gate: Dict[str, Any]) -> str:
    try:
        risk = store.risk_register.get("MR-013")
        cal = gate["calibration"]
        risk.update_mitigation(
            MitigationStatus.IN_PROGRESS,
            notes=(
                "Phase 20 Task 2 calibrated the G2++ driver (a, b, sigma, eta, rho) to an "
                "educational-proxy ATM swaption surface via analytic Brigo-Mercurio pricing; "
                "G-SWPN gate {status} (vol RMSE {rmse:.1f} bps). Residual: market-consistency "
                "martingale gate (Task 3), capital propagation (Task 4), recalibration to a "
                "validated market surface, and independent review remain pending."
            ).format(status=gate["status"], rmse=cal["rmse_vol_bps"]),
        )
        return "refreshed"
    except KeyError:
        return "missing"


def _write_card(gate: Dict[str, Any]) -> None:
    cal = gate["calibration"]
    p = cal["params"]
    CARD_PATH.write_text(
        """# Market-Consistent G2++ Swaption Calibration Card

**Phase:** 20 - Market-Consistency and Multi-Factor Uplift (Task 2)

**Status:** Calibrated to an EDUCATIONAL PROXY swaption surface; pending martingale
validation (Task 3), capital propagation (Task 4), and independent review.

## Purpose

Task 2 makes the enhanced G2++ rate driver calibratable. It adds an analytic
European swaption pricer (Brigo-Mercurio one-dimensional Gaussian-quadrature
decomposition into an option on the fixed-leg coupon bond), Black (lognormal)
ATM pricing/implied-vol inversion for the targets, a derivative-free Nelder-Mead
calibration of (a, b, sigma, eta, rho), and the G-SWPN calibration-quality gate.

## Calibrated Parameters (educational proxy surface)

| Parameter | Symbol | Value |
| --- | --- | ---: |
| Mean reversion (factor 1) | a | {a:.5f} |
| Mean reversion (factor 2) | b | {b:.5f} |
| Volatility (factor 1) | sigma | {sigma:.5f} |
| Volatility (factor 2) | eta | {eta:.5f} |
| Factor correlation | rho | {rho:.4f} |

Fit: implied-vol RMSE {rmse:.1f} bps, worst-point {maxv:.1f} bps, relative-price
RMSE {relp:.4f} across {nq} ATM quotes. Gate **{status}**.

## Validation

- Analytic pricer cross-checked against Monte Carlo (within 4 standard errors).
- ATM payer/receiver swaption put-call (swap) parity holds to ~1e-16.
- Calibrated engine still reprices the input curve exactly (affine ZCB identity).

## Production Use Restriction

The swaption surface is a SYNTHETIC educational placeholder, not market data. Do
not use the calibrated parameters for production pricing, capital, or external
disclosure. Phase 20 Task 3 must add a market-consistency martingale validation
gate; Task 4 must propagate the driver through the capital stack; recalibration to
a validated market surface and independent reviewer sign-off remain required.
""".format(
            a=p["mean_reversion_x"],
            b=p["mean_reversion_y"],
            sigma=p["vol_x"],
            eta=p["vol_y"],
            rho=p["factor_correlation"],
            rmse=cal["rmse_vol_bps"],
            maxv=cal["max_abs_vol_bps"],
            relp=cal["rmse_relative_price"],
            nq=cal["n_quotes"],
            status=gate["status"],
        ),
        encoding="utf-8",
    )


def _markdown(report: Dict[str, Any]) -> str:
    gate = report["gate"]
    cal = gate["calibration"]
    p = cal["params"]
    checks = "\n".join(
        "- **{}**: {} (observed `{:.6g}`, threshold `{}`)".format(
            c["check_id"], "PASS" if c["passed"] else "FAIL", c["observed"], c["threshold"]
        )
        for c in gate["checks"]
    )
    rows = "\n".join(
        "| {:.0f}y x {:.0f}y | {:.4f} | {:.4f} | {:.4f} | {:+.1f} |".format(
            q["expiry"], q["tenor"], q["forward"], q["market_vol"], q["model_vol"], q["vol_error_bps"]
        )
        for q in cal["per_quote"]
    )
    return """# Phase 20 Task 2 - G2++ Swaption-Surface Calibration

**Run timestamp:** {ts}

**Gate:** `{gate_id}` - **{status}**

## Calibrated G2++ Parameters

| a | b | sigma | eta | rho |
| ---: | ---: | ---: | ---: | ---: |
| {a:.5f} | {b:.5f} | {sigma:.5f} | {eta:.5f} | {rho:.4f} |

Initial seed: a={ia:.4f}, b={ib:.4f}, sigma={isig:.4f}, eta={iet:.4f}, rho={irho:.3f}.

## Fit Quality

| Metric | Value |
| --- | ---: |
| ATM quotes | {nq} |
| Implied-vol RMSE | {rmse:.2f} bps |
| Worst-point vol error | {maxv:.2f} bps |
| Relative-price RMSE | {relp:.4f} |
| Objective (mean rel-price^2) | {obj:.6g} |
| Simplex iterations | {iters} |

## G-SWPN Checks

{checks}

## Per-Quote Fit (ATM, semi-annual)

| Expiry x Tenor | Forward | Market vol | Model vol | Error (bps) |
| --- | ---: | ---: | ---: | ---: |
{rows}

## Governance

- ChangeRecord: `{cr_id}` - **{cr_status}**
- MR-013: **{mr_status}** ({mr_action})
- Audit integrity: **{audit}**

## Production Restriction

{restriction}
""".format(
        ts=report["run_timestamp"],
        gate_id=gate["gate_id"],
        status=gate["status"],
        a=p["mean_reversion_x"], b=p["mean_reversion_y"], sigma=p["vol_x"], eta=p["vol_y"], rho=p["factor_correlation"],
        ia=cal["initial_params"]["mean_reversion_x"], ib=cal["initial_params"]["mean_reversion_y"],
        isig=cal["initial_params"]["vol_x"], iet=cal["initial_params"]["vol_y"], irho=cal["initial_params"]["factor_correlation"],
        nq=cal["n_quotes"], rmse=cal["rmse_vol_bps"], maxv=cal["max_abs_vol_bps"],
        relp=cal["rmse_relative_price"], obj=cal["objective_value"], iters=cal["iterations"],
        checks=checks, rows=rows,
        cr_id=report["change_record_id"], cr_status=report["change_record_status"],
        mr_status=report["mr013_status"], mr_action=report["mr013_action"],
        audit=report["audit_integrity_ok"], restriction=gate["use_restriction"],
    )


def apply_governance(store: GovernanceStore, gate: Dict[str, Any]) -> Dict[str, Any]:
    mr_action = _refresh_mr013(store, gate)
    added = False
    record_id = None
    record_status = None
    cal = gate["calibration"]

    if not _has_change_record(store):
        rec = ChangeRecord.create(
            title=CHANGE_TITLE,
            description=(
                "Phase 20 Task 2 calibrated the enhanced G2++ rate driver to an educational-proxy "
                "ATM swaption volatility grid. Added an analytic European swaption pricer "
                "(Brigo-Mercurio decomposition into an option on the fixed-leg coupon bond), Black "
                "ATM pricing/implied-vol inversion, a derivative-free Nelder-Mead calibration of "
                "(a, b, sigma, eta, rho), and a G-SWPN calibration-quality gate. Production sign-off "
                "withheld pending martingale validation, capital propagation, and recalibration to a "
                "validated market surface."
            ),
            change_type="methodology_change",
            affected_components=AFFECTED_COMPONENTS,
            standard_references=STANDARD_REFERENCES,
            before_snapshot={
                "g2pp_parameters": "educational defaults (Task 1); no swaption calibration",
                "swaption_pricer": "not available",
                "g_swpn_gate": "not available",
            },
            after_snapshot={
                "g2pp_parameters": cal["params"],
                "swaption_pricer": "analytic Brigo-Mercurio (Gauss-Hermite quadrature)",
                "g_swpn_status": gate["status"],
                "vol_rmse_bps": cal["rmse_vol_bps"],
                "checks_passed": sum(1 for c in gate["checks"] if c["passed"]),
                "checks_total": len(gate["checks"]),
            },
            impact_assessment=(
                "Makes the two-factor rate driver calibratable without changing existing HW1F, "
                "ScenarioSet, TVOG, or capital outputs. Calibrated parameters remain educational "
                "until Tasks 3-4 validate martingales and capital impact and an independent reviewer "
                "signs off a market-data calibration."
            ),
            quantitative_impact=(
                "G-SWPN {status}: implied-vol RMSE {rmse:.1f} bps, worst-point {maxv:.1f} bps, "
                "relative-price RMSE {relp:.4f} across {nq} ATM quotes; ATM put-call parity ~1e-16."
            ).format(
                status=gate["status"], rmse=cal["rmse_vol_bps"], maxv=cal["max_abs_vol_bps"],
                relp=cal["rmse_relative_price"], nq=cal["n_quotes"],
            ),
            author=ACTOR,
            phase=PHASE,
            peer_reviewer="APS_X2_Independent_Reviewer",
            assumption_owner="ChiefActuary",
        )
        rec.submit_for_peer_review(
            ACTOR,
            "Analytic swaption pricer (MC-cross-checked), calibration, and G-SWPN gate staged; "
            "market-surface recalibration required before approval.",
        )
        rec.submit_to_owner(
            ACTOR,
            "Owner review requested. Production sign-off withheld pending Phase 20 Tasks 3-4 and a "
            "validated market swaption surface.",
        )
        store.add_change_record(rec)
        added = True
        record_id = rec.record_id
        record_status = rec.status.value
        store.audit_trail.append(
            AuditEntry.governance(
                actor=ACTOR,
                phase=PHASE,
                event="ChangeRecord opened (OWNER_REVIEW) - G2++ swaption calibration and G-SWPN gate",
                details={
                    "record_id": rec.record_id,
                    "gate_id": gate["gate_id"],
                    "gate_status": gate["status"],
                    "vol_rmse_bps": cal["rmse_vol_bps"],
                    "affected_components": AFFECTED_COMPONENTS,
                    "mr013_action": mr_action,
                },
            )
        )
    else:
        for rec in store.change_records:
            if rec.title == CHANGE_TITLE:
                record_id = rec.record_id
                record_status = rec.status.value
                break

    return {
        "mr013_action": mr_action,
        "mr013_status": store.risk_register.get("MR-013").mitigation_status.value,
        "added_change_record": added,
        "change_record_id": record_id,
        "change_record_status": record_status,
    }


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    curve = educational_proxy_curve()
    gate = evaluate_g_swpn_gate(curve=curve).to_dict()
    store = GovernanceStore.from_json(GOV_PATH.read_text(encoding="utf-8")) if GOV_PATH.exists() else GovernanceStore()
    gov = apply_governance(store, gate)
    _write_card(gate)

    if GOV_PATH.exists():
        GOV_PATH.write_text(store.to_json() + "\n", encoding="utf-8")

    report = {
        "run_timestamp": datetime.now(timezone.utc).isoformat(),
        "phase": PHASE,
        "task": "Phase 20 Task 2 - G2++ swaption-surface calibration and G-SWPN gate",
        "gate": gate,
        "proxy_grid": educational_proxy_vol_grid(),
        "affected_components": AFFECTED_COMPONENTS,
        "standard_references": STANDARD_REFERENCES,
        "change_record_id": gov["change_record_id"],
        "change_record_status": gov["change_record_status"],
        "mr013_action": gov["mr013_action"],
        "mr013_status": gov["mr013_status"],
        "audit_integrity_ok": store.audit_trail.verify_all(),
        "change_records_total": len(store.change_records),
        "risk_register_summary": store.risk_register.summary(),
        "use_restriction": gate["use_restriction"],
    }
    report["markdown"] = _markdown(report)
    JSON_PATH.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    MD_PATH.write_text(report["markdown"], encoding="utf-8")

    print("=== Phase 20 Task 2 - G2++ Swaption Calibration ===")
    print("Gate G-SWPN       : {}".format(gate["status"]))
    print("Vol RMSE (bps)    : {:.2f}".format(gate["calibration"]["rmse_vol_bps"]))
    print("ChangeRecord      : {} ({})".format(gov["change_record_id"], gov["change_record_status"]))
    print("MR-013            : {} ({})".format(gov["mr013_status"], gov["mr013_action"]))
    print("Audit integrity   : {}".format(store.audit_trail.verify_all()))
    print("Report            : {}".format(JSON_PATH))
    return 0 if gate["status"] == "PASS" and store.audit_trail.verify_all() else 1


if __name__ == "__main__":
    sys.exit(main())
