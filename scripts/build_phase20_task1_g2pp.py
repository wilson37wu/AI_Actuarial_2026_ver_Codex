#!/usr/bin/env python3
"""
Phase 20 Task 1 build script: enhanced G2++ rate driver + G-RATE2 gate.

The script evaluates the additive G2++ analytic/gate module, writes validation
evidence, and records an OWNER_REVIEW governance ChangeRecord.  It is
idempotent: if the canonical GovernanceStore already contains the Phase 20 Task
1 ChangeRecord title, it rewrites the validation report but does not append
duplicate governance entries.

Run:
    PYTHONPATH=. python scripts/build_phase20_task1_g2pp.py
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from par_model_v2.governance.audit_trail import (
    AuditEntry,
    ChangeRecord,
    GovernanceStore,
    MitigationStatus,
    RiskRating,
)
from par_model_v2.stochastic.g2pp_rate import EnhancedG2PlusRateProcess, evaluate_g_rate2_gate


PHASE = "Phase 20: Market-Consistency and Multi-Factor Uplift"
ACTOR = "AutomatedModelDev_Phase20"
GOV_PATH = Path(".claude-dev/GOVERNANCE_STORE.json")
OUT_DIR = Path("docs/validation")
JSON_PATH = OUT_DIR / "PHASE20_TASK1_G2PP_RATE_REPORT.json"
MD_PATH = OUT_DIR / "PHASE20_TASK1_G2PP_RATE_REPORT.md"
CARD_PATH = Path("docs/MARKET_CONSISTENT_G2PP_RATE_CARD.md")
CHANGE_TITLE = "Phase 20 Task 1 - enhanced G2++ rates driver and G-RATE2 gate"

AFFECTED_COMPONENTS = [
    "par_model_v2/stochastic/g2pp_rate.py",
    "par_model_v2/stochastic/__init__.py",
    "tests/test_phase20_g2pp_rate.py",
    "scripts/build_phase20_task1_g2pp.py",
    "docs/MARKET_CONSISTENT_G2PP_RATE_CARD.md",
    "docs/validation/PHASE20_TASK1_G2PP_RATE_REPORT.{json,md}",
]

STANDARD_REFERENCES = [
    "SOA ASOP 56 section 3.1.3",
    "SOA ASOP 56 section 3.5",
    "SOA ASOP 25 section 3.3",
    "IA TAS M section 3.5",
    "IA TAS M section 3.6",
    "Solvency II Delegated Regulation Article 77",
    "Solvency II Delegated Regulation Article 234",
]


def _has_change_record(store: GovernanceStore) -> bool:
    return any(r.title == CHANGE_TITLE for r in store.change_records)


def _ensure_mr013(store: GovernanceStore) -> str:
    try:
        risk = store.risk_register.get("MR-013")
        risk.update_mitigation(
            MitigationStatus.IN_PROGRESS,
            notes=(
                "Phase 20 Task 1 added analytic G2++ ZCB/bond-option formulas and a G-RATE2 "
                "plausibility gate. Residual: swaption-surface calibration, martingale gate, "
                "capital propagation, and independent review remain pending."
            ),
        )
        return "refreshed"
    except KeyError:
        store.risk_register.add(
            risk_id="MR-013",
            title="Two-factor rates market consistency not fully calibrated",
            description=(
                "The G2++ rates driver now has analytic zero-coupon and bond-option formulas, "
                "but parameters are educational until calibrated to a swaption volatility surface "
                "and validated through martingale and capital-impact gates."
            ),
            category="model_error",
            likelihood=RiskRating.MEDIUM,
            impact=RiskRating.HIGH,
            owner="Assumption Owner",
            mitigation=(
                "Complete Phase 20 Tasks 2-4: swaption-surface calibration, market-consistency "
                "martingale gate, and capital re-aggregation/tail diagnostics with independent review."
            ),
            related_standard="SOA ASOP 56 section 3.5; IA TAS M section 3.6",
            mitigation_status=MitigationStatus.IN_PROGRESS,
            notes="Opened by Phase 20 Task 1 as an explicit residual risk tracker.",
        )
        return "added"


def _write_card() -> None:
    CARD_PATH.write_text(
        """# Market-Consistent G2++ Rate Driver Card

**Phase:** 20 - Market-Consistency and Multi-Factor Uplift

**Status:** Implementation staged; educational parameters pending swaption-surface calibration.

## Purpose

The enhanced G2++ module adds a two-factor Gaussian interest-rate driver with
exact OU factor simulation, analytic zero-coupon bond prices fitted to the
initial curve, analytic European options on zero-coupon bonds, and a G-RATE2
plausibility gate.

## What Changed

- `EnhancedG2PlusRateProcess` in `par_model_v2/stochastic/g2pp_rate.py`
- `zcb_price(x_t, y_t, t, T)` includes the G2++ affine convexity adjustment.
- `bond_option_price(T, S, K, call/put)` uses the closed-form Gaussian bond
  option formula and put-call parity.
- `evaluate_g_rate2_gate()` checks curve fit, option variance, parity, bounds,
  simulated factor correlation, and negative-rate support.

## Production Use Restriction

Do not use the Phase 20 Task 1 parameters for production pricing, capital, or
external disclosure. Phase 20 Task 2 must calibrate the G2++ parameters to an
observed swaption surface; Phase 20 Task 3 must add a martingale validation gate;
Phase 20 Task 4 must propagate the driver through the capital stack; independent
review remains required.
""",
        encoding="utf-8",
    )


def _markdown(report: Dict[str, Any]) -> str:
    gate = report["gate"]
    checks = "\n".join(
        "- **{}**: {} (observed `{}`, threshold `{}`)".format(
            c["check_id"],
            "PASS" if c["passed"] else "FAIL",
            c["observed"],
            c["threshold"],
        )
        for c in gate["checks"]
    )
    diag = gate["diagnostics"]
    return """# Phase 20 Task 1 - Enhanced G2++ Rates Driver

**Run timestamp:** {ts}

**Gate:** `{gate_id}` - **{status}**

## Diagnostics

| Metric | Value |
| --- | ---: |
| Initial-curve fit max abs error | {curve_fit:.12g} |
| Bond-option variance | {variance:.12g} |
| Call price | {call:.12g} |
| Put price | {put:.12g} |
| Put-call parity error | {parity:.12g} |
| Empirical factor correlation | {corr:.12g} |
| Negative-rate one-year discount factor | {neg_df:.12g} |

## G-RATE2 Checks

{checks}

## Governance

- ChangeRecord: `{change_record_id}` - **{change_record_status}**
- MR-013: **{mr013_status}** ({mr013_action})
- Audit integrity: **{audit_integrity_ok}**

## Production Restriction

Educational only until Phase 20 Tasks 2-4 calibrate and validate the G2++ driver
against a swaption surface, market-consistency martingale checks, and the
five-driver capital stack.
""".format(
        ts=report["run_timestamp"],
        gate_id=gate["gate_id"],
        status=gate["status"],
        curve_fit=diag["curve_fit_max_abs_error"],
        variance=diag["bond_option_variance"],
        call=diag["call_price"],
        put=diag["put_price"],
        parity=diag["put_call_parity_error"],
        corr=diag["empirical_factor_correlation"],
        neg_df=diag["negative_rate_discount_factor"],
        checks=checks,
        change_record_id=report["change_record_id"],
        change_record_status=report["change_record_status"],
        mr013_status=report["mr013_status"],
        mr013_action=report["mr013_action"],
        audit_integrity_ok=report["audit_integrity_ok"],
    )


def apply_governance(store: GovernanceStore, gate: Dict[str, Any]) -> Dict[str, Any]:
    mr013_action = _ensure_mr013(store)
    added_change = False
    record_id = None
    record_status = None

    if not _has_change_record(store):
        rec = ChangeRecord.create(
            title=CHANGE_TITLE,
            description=(
                "Phase 20 Task 1 added an enhanced G2++ rates driver with exact OU factor "
                "simulation, analytic initial-curve-fitted zero-coupon bond pricing, analytic "
                "European zero-coupon bond option pricing, and a G-RATE2 plausibility gate. "
                "This is the first step of the market-consistency/multi-factor uplift; "
                "production sign-off is withheld pending swaption-surface calibration, "
                "martingale validation, and capital re-aggregation."
            ),
            change_type="methodology_change",
            affected_components=AFFECTED_COMPONENTS,
            standard_references=STANDARD_REFERENCES,
            before_snapshot={
                "rates_driver": "HW1F default; legacy G2++ prototype omitted convexity adjustment and bond-option formula",
                "g_rate2_gate": "not available",
            },
            after_snapshot={
                "rates_driver": "EnhancedG2PlusRateProcess",
                "analytic_zcb": True,
                "analytic_bond_option": True,
                "g_rate2_status": gate["status"],
                "checks_passed": sum(1 for c in gate["checks"] if c["passed"]),
                "checks_total": len(gate["checks"]),
            },
            impact_assessment=(
                "Adds market-consistency infrastructure for a two-factor rates driver without "
                "changing existing HW1F, ScenarioSet, TVOG, or capital outputs. Future tasks will "
                "calibrate, validate martingales, and propagate the driver into capital aggregation."
            ),
            quantitative_impact=(
                "G-RATE2 {}: curve-fit max abs error {:.3e}; option variance {:.3e}; "
                "put-call parity error {:.3e}; empirical factor correlation {:.3f}."
            ).format(
                gate["status"],
                gate["diagnostics"]["curve_fit_max_abs_error"],
                gate["diagnostics"]["bond_option_variance"],
                gate["diagnostics"]["put_call_parity_error"],
                gate["diagnostics"]["empirical_factor_correlation"],
            ),
            author=ACTOR,
            phase=PHASE,
            peer_reviewer="APS_X2_Independent_Reviewer",
            assumption_owner="ChiefActuary",
        )
        rec.submit_for_peer_review(
            ACTOR,
            "Additive G2++ engine and G-RATE2 gate staged; tests and calibration evidence required before approval.",
        )
        rec.submit_to_owner(
            ACTOR,
            "Owner review requested. Production sign-off withheld pending Phase 20 Tasks 2-4.",
        )
        store.add_change_record(rec)
        added_change = True
        record_id = rec.record_id
        record_status = rec.status.value
        store.audit_trail.append(
            AuditEntry.governance(
                actor=ACTOR,
                phase=PHASE,
                event="ChangeRecord opened (OWNER_REVIEW) - enhanced G2++ rates driver and G-RATE2 gate",
                details={
                    "record_id": rec.record_id,
                    "gate_id": gate["gate_id"],
                    "gate_status": gate["status"],
                    "affected_components": AFFECTED_COMPONENTS,
                    "mr013_action": mr013_action,
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
        "mr013_action": mr013_action,
        "mr013_status": store.risk_register.get("MR-013").mitigation_status.value,
        "added_change_record": added_change,
        "change_record_id": record_id,
        "change_record_status": record_status,
    }


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    gate = evaluate_g_rate2_gate(EnhancedG2PlusRateProcess()).to_dict()
    store = GovernanceStore.from_json(GOV_PATH.read_text(encoding="utf-8")) if GOV_PATH.exists() else GovernanceStore()
    gov = apply_governance(store, gate)
    _write_card()

    if GOV_PATH.exists():
        GOV_PATH.write_text(store.to_json() + "\n", encoding="utf-8")

    report = {
        "run_timestamp": datetime.now(timezone.utc).isoformat(),
        "phase": PHASE,
        "task": "Phase 20 Task 1 - enhanced G2++ rates driver and G-RATE2 gate",
        "gate": gate,
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

    print("=== Phase 20 Task 1 - Enhanced G2++ Rates Driver ===")
    print("Gate G-RATE2      : {}".format(gate["status"]))
    print("ChangeRecord      : {} ({})".format(gov["change_record_id"], gov["change_record_status"]))
    print("MR-013            : {} ({})".format(gov["mr013_status"], gov["mr013_action"]))
    print("Audit integrity   : {}".format(store.audit_trail.verify_all()))
    print("Report            : {}".format(JSON_PATH))
    return 0 if gate["status"] == "PASS" and store.audit_trail.verify_all() else 1


if __name__ == "__main__":
    sys.exit(main())
