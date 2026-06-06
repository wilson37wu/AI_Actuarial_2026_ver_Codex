#!/usr/bin/env python3
"""Phase 20 Task 3 build + governance -- market-consistency (martingale) gate G-MART.

Runs the G-MART gate (deflated-asset / forward martingale checks under Q across the
HW1F + G2++ rate drivers, the GBM equity driver and FX), writes the validation
report (JSON + Markdown) and a model card, opens an OWNER_REVIEW ChangeRecord,
refreshes risk MR-013, and verifies audit-chain integrity.

Run:  PYTHONPATH=/var/tmp/pylibs:. python3 scripts/build_phase20_task3_market_consistency.py
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
from par_model_v2.validation.phase20_market_consistency import evaluate_g_mart_gate

PHASE = "Phase 20: Market-Consistency and Multi-Factor Uplift"
ACTOR = "AutomatedModelDev_Phase20"
GOV_PATH = Path(".claude-dev/GOVERNANCE_STORE.json")
OUT_DIR = Path("docs/validation")
JSON_PATH = OUT_DIR / "PHASE20_TASK3_G_MART_REPORT.json"
MD_PATH = OUT_DIR / "PHASE20_TASK3_G_MART_REPORT.md"
CARD_PATH = Path("docs/MARKET_CONSISTENCY_G_MART_CARD.md")
CHANGE_TITLE = "Phase 20 Task 3 - market-consistency martingale validation gate (G-MART)"

AFFECTED_COMPONENTS = [
    "par_model_v2/validation/phase20_market_consistency.py",
    "par_model_v2/validation/__init__.py",
    "tests/test_phase20_market_consistency.py",
    "scripts/build_phase20_task3_market_consistency.py",
    "docs/MARKET_CONSISTENCY_G_MART_CARD.md",
    "docs/validation/PHASE20_TASK3_G_MART_REPORT.{json,md}",
]

STANDARD_REFERENCES = [
    "SOA ASOP 56 section 3.1.3",
    "SOA ASOP 56 section 3.5",
    "IA TAS M section 3.6",
    "Solvency II Delegated Regulation Article 22",
    "Solvency II Delegated Regulation Article 234",
    "Brigo-Mercurio 2006",
]


def _has_change_record(store: GovernanceStore) -> bool:
    return any(r.title == CHANGE_TITLE for r in store.change_records)


def _refresh_mr013(store: GovernanceStore, gate: Dict[str, Any]) -> str:
    try:
        risk = store.risk_register.get("MR-013")
        diag = gate["diagnostics"]
        risk.update_mitigation(
            MitigationStatus.IN_PROGRESS,
            notes=(
                "Phase 20 Task 3 added the G-MART market-consistency gate: the deflated-asset / "
                "forward martingale identities hold under Q within Monte-Carlo tolerance for the "
                "HW1F (exact dynamics) and G2++ rate drivers, GBM equity, and FX (covered interest "
                "parity). G-MART {status} (worst {nsig:.2f} sigma; max rel err {rel:.2e} over {n} paths). "
                "A documented diagnostic shows the EDUCATIONAL monthly-Euler HW1F simulate() carries a "
                "~7% martingale bias vs the exact dynamics (use exact simulation for market-consistent "
                "work). Residual: capital re-aggregation with the 2F driver (Task 4), UI surfacing "
                "(Task 5), recalibration to a validated market surface, and independent review remain pending."
            ).format(
                status=gate["status"], nsig=diag["worst_n_std_errors"],
                rel=diag["max_rel_error"], n=diag["n_scenarios"],
            ),
        )
        return "refreshed"
    except KeyError:
        return "missing"


def _check_rows(gate: Dict[str, Any]) -> str:
    rows = []
    for c in gate["checks"]:
        rows.append(
            "| {id} | {sev} | {passed} | {est:.6f} | {tgt:.6f} | {rel:.2e} | {nsig:.2f} |".format(
                id=c["check_id"], sev=c["severity"], passed="PASS" if c["passed"] else "FAIL",
                est=c["estimate"], tgt=c["target"], rel=c["rel_error"], nsig=c["n_std_errors"],
            )
        )
    return "\n".join(rows)


def _write_card(gate: Dict[str, Any]) -> None:
    diag = gate["diagnostics"]
    CARD_PATH.write_text(
        """# Market-Consistency (Martingale) Gate Card -- G-MART

**Phase:** 20 - Market-Consistency and Multi-Factor Uplift (Task 3)

**Status:** Martingale evidence at EDUCATIONAL calibration; gate {status}. Production
sign-off withheld pending capital re-aggregation (Task 4), UI surfacing (Task 5),
recalibration to a validated market surface, and independent (APS X2) review.

## Purpose

G-MART is an output-only, additive validation gate that verifies the economic-scenario
generators are arbitrage-free under the risk-neutral measure Q. With the money-market
account B(t) = exp(int_0^t r ds) as numeraire, every traded asset deflated by B(t) must
be a Q-martingale. The gate tests these identities by Monte-Carlo within a k-standard-error
band, so each PASS is a statistical hypothesis test, not an arbitrary point comparison.

## Identities tested

| Driver | Identity |
| --- | --- |
| HW1F rates (exact) | E^Q[ D(t) P_HW(t,T) ] = P(0,T) |
| G2++ / 2F rates | E^Q[ D(t) P_G2(t,T) ] = P(0,T) |
| GBM equity | E^Q[ D(t) S(t) exp(q_S t) ] = S(0) |
| FX (covered interest parity) | E^Q_d[ D_d(t) X(t) exp(r_f t) ] = X(0) |

The deflator for the analytic-bond checks uses the trapezoidal integral of the simulated
short rate (O(dt^2)); the equity/FX checks use the left-point integral that matches the
GBM/FX Euler drift exactly, so the discrete discounted-asset identity is exact there.

## Result (educational proxy; seed {seed})

- Gate **{status}**: worst error {nsig:.2f} sigma, max relative error {rel:.2e} over {n} paths,
  horizon t = {t:.2f}y.
- Drivers covered: {drivers}.

## Honest diagnostics (informational, non-gating)

- **MART-HW1F-EULER-BIAS:** the EDUCATIONAL monthly-Euler `HullWhiteRateProcess.simulate`
  (mean-reversion-to-forward, no convexity term, r0 = params.initial_short_rate) carries a
  ~7% martingale bias vs the exact dynamics. Use the exact HW1F simulation for any
  market-consistent valuation; the educational Euler path generator is for illustration only.
- **MART-PQ-MEASURE:** under the real-world measure P the discounted equity is NOT a
  martingale -- it drifts up by exp(ERP*t). This confirms the martingale property is
  genuinely Q-specific (P/Q separation, G-05 / MR-004).

## Model-use restriction

{restriction}
""".format(
            status=gate["status"], seed=20260606, nsig=diag["worst_n_std_errors"],
            rel=diag["max_rel_error"], n=diag["n_scenarios"], t=diag["test_time_years"],
            drivers=", ".join(diag["drivers"]), restriction=gate["use_restriction"],
        ),
        encoding="utf-8",
    )


def _markdown(report: Dict[str, Any]) -> str:
    gate = report["gate"]
    diag = gate["diagnostics"]
    return """# Phase 20 Task 3 -- Market-Consistency (Martingale) Gate G-MART

**Run:** {ts}

**Gate G-MART:** {status} ({npass}/{nerr} ERROR checks pass; {ntot} checks incl. diagnostics)

## Numeraire and method

Money-market account B(t) = exp(int_0^t r ds). Each deflated-asset martingale identity is
tested by Monte-Carlo against its analytic target within a {k:.0f}-standard-error band
(n = {n} paths; horizon t = {t:.2f}y).

## Checks

| Check | Severity | Result | MC estimate | Target | Rel err | n-sigma |
| --- | --- | --- | ---: | ---: | ---: | ---: |
{rows}

## Summary

- Worst ERROR-check deviation: {nsig:.2f} sigma (band {k:.0f} sigma).
- Max ERROR relative error: {rel:.2e}.
- Drivers covered: {drivers}.

## Diagnostics (non-gating)

- The educational monthly-Euler HW1F simulator shows a documented ~7% martingale bias vs the
  exact dynamics (MART-HW1F-EULER-BIAS) -- exact simulation is used for the gate.
- Under P the discounted equity drifts up by exp(ERP*t) (MART-PQ-MEASURE), confirming the
  martingale property is Q-specific.

## Governance

- ChangeRecord: {rec} ({recst}).
- MR-013: {mr} ({mract}).
- Audit integrity: {audit}.

## Production restriction

{restriction}
""".format(
        ts=report["run_timestamp"], status=gate["status"], npass=gate["n_passed"],
        nerr=gate["n_error_checks"], ntot=gate["n_checks"], k=diag["k_sigma"],
        n=diag["n_scenarios"], t=diag["test_time_years"], rows=_check_rows(gate),
        nsig=diag["worst_n_std_errors"], rel=diag["max_rel_error"],
        drivers=", ".join(diag["drivers"]), rec=report["change_record_id"],
        recst=report["change_record_status"], mr=report["mr013_status"],
        mract=report["mr013_action"], audit=report["audit_integrity_ok"],
        restriction=gate["use_restriction"],
    )


def apply_governance(store: GovernanceStore, gate: Dict[str, Any]) -> Dict[str, Any]:
    mr_action = _refresh_mr013(store, gate)
    added = False
    record_id = None
    record_status = None
    diag = gate["diagnostics"]

    if not _has_change_record(store):
        rec = ChangeRecord.create(
            title=CHANGE_TITLE,
            description=(
                "Phase 20 Task 3 added an output-only market-consistency (martingale) validation gate "
                "(G-MART). With the money-market numeraire, it verifies by Monte-Carlo that deflated "
                "fixed-maturity ZCBs are Q-martingales for the HW1F (exact dynamics) and G2++ rate "
                "drivers, that the ex-dividend discounted GBM equity index is a Q-martingale, and that "
                "the FX covered-interest-parity martingale holds, each within a 4-standard-error band. "
                "An honest diagnostic quantifies the ~7% martingale bias of the educational monthly-Euler "
                "HW1F path generator vs the exact dynamics, and a P/Q diagnostic confirms the property is "
                "measure-specific. Production sign-off withheld pending capital re-aggregation, UI "
                "surfacing, and recalibration to a validated market surface."
            ),
            change_type="methodology_change",
            affected_components=AFFECTED_COMPONENTS,
            standard_references=STANDARD_REFERENCES,
            before_snapshot={
                "market_consistency_gate": "not available",
                "exact_hw1f_simulator": "not available (only educational Euler path generator)",
            },
            after_snapshot={
                "market_consistency_gate": "G-MART",
                "g_mart_status": gate["status"],
                "error_checks_passed": "{}/{}".format(gate["n_passed"], gate["n_checks"]),
                "worst_n_std_errors": diag["worst_n_std_errors"],
                "max_rel_error": diag["max_rel_error"],
                "drivers": diag["drivers"],
            },
            impact_assessment=(
                "Adds arbitrage-free evidence across the rate/equity/FX drivers without changing any "
                "existing simulation output (additive validation module). Surfaces the educational "
                "Euler HW1F bias as a documented limitation so downstream market-consistent work uses "
                "the exact dynamics."
            ),
            quantitative_impact=(
                "G-MART {status}: all {nerr} ERROR martingale checks pass within {k:.0f} sigma "
                "(worst {nsig:.2f} sigma; max rel err {rel:.2e}) over {n} paths at t={t:.2f}y. "
                "Educational-Euler HW1F bias ~7% (documented, non-gating)."
            ).format(
                status=gate["status"], nerr=gate["n_error_checks"], k=diag["k_sigma"],
                nsig=diag["worst_n_std_errors"], rel=diag["max_rel_error"],
                n=diag["n_scenarios"], t=diag["test_time_years"],
            ),
            author=ACTOR,
            phase=PHASE,
            peer_reviewer="APS_X2_Independent_Reviewer",
            assumption_owner="ChiefActuary",
        )
        rec.submit_for_peer_review(
            ACTOR,
            "Martingale gate (exact HW1F + G2++ + GBM + FX) staged with MC tolerance; "
            "market-surface recalibration required before approval.",
        )
        rec.submit_to_owner(
            ACTOR,
            "Owner review requested. Production sign-off withheld pending Phase 20 Tasks 4-5 and a "
            "validated market surface.",
        )
        store.add_change_record(rec)
        added = True
        record_id = rec.record_id
        record_status = rec.status.value
        store.audit_trail.append(
            AuditEntry.governance(
                actor=ACTOR,
                phase=PHASE,
                event="ChangeRecord opened (OWNER_REVIEW) - G-MART market-consistency gate",
                details={
                    "record_id": rec.record_id,
                    "gate_id": gate["gate_id"],
                    "gate_status": gate["status"],
                    "worst_n_std_errors": diag["worst_n_std_errors"],
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
    gate = evaluate_g_mart_gate().to_dict()
    store = GovernanceStore.from_json(GOV_PATH.read_text(encoding="utf-8")) if GOV_PATH.exists() else GovernanceStore()
    gov = apply_governance(store, gate)
    _write_card(gate)

    if GOV_PATH.exists():
        GOV_PATH.write_text(store.to_json() + "\n", encoding="utf-8")

    report = {
        "run_timestamp": datetime.now(timezone.utc).isoformat(),
        "phase": PHASE,
        "task": "Phase 20 Task 3 - market-consistency martingale validation gate (G-MART)",
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

    print("=== Phase 20 Task 3 - G-MART Market-Consistency Gate ===")
    print("Gate G-MART       : {}".format(gate["status"]))
    print("Worst n-sigma     : {:.3f}".format(gate["diagnostics"]["worst_n_std_errors"]))
    print("Max rel error     : {:.2e}".format(gate["diagnostics"]["max_rel_error"]))
    print("ChangeRecord      : {} ({})".format(gov["change_record_id"], gov["change_record_status"]))
    print("MR-013            : {} ({})".format(gov["mr013_status"], gov["mr013_action"]))
    print("Audit integrity   : {}".format(store.audit_trail.verify_all()))
    print("Report            : {}".format(JSON_PATH))
    return 0 if gate["status"] == "PASS" and store.audit_trail.verify_all() else 1


if __name__ == "__main__":
    sys.exit(main())
