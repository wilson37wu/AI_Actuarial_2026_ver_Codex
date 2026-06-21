"""Build Phase 17 Task 5 governance refresh for the THREE-driver economic-capital proxy.

Phase 17 Task 5 — "Governance refresh: open the credit-driver model-risk entry, a
consolidated three-driver limitation card, an OWNER_REVIEW ChangeRecord, and an
audit-chain append."

This consolidates the governance of the four Phase 17 three-driver capital modules
(adding the credit-spread driver to the Phase 15 two-driver baseline):

    par_model_v2/stochastic/credit_spread.py                   (Task 1 — CIR++ credit driver)
    par_model_v2/projection/multi_driver_capital_3d.py         (Task 1 — trivariate nested + LSMC)
    par_model_v2/projection/multi_driver_proxy_validation.py   (Task 2 — ThreeDriverProxyValidator)
    par_model_v2/projection/multi_driver_risk_aggregation.py   (Task 3 — ThreeDriverRiskAggregator)
    par_model_v2/projection/multi_driver_tail_diagnostics.py   (Task 4 — ThreeDriverTailDiagnostics)

It is idempotent: re-running detects the already-applied MR entry and ChangeRecord
by their stable keys and does not duplicate them.

Run:  PYTHONPATH=. python3 scripts/build_phase17_task5_governance.py [--governance]

With --governance the canonical store .claude-dev/GOVERNANCE_STORE.json is loaded,
the refresh applied, and the store + the JSON evidence re-written.  Without it the
refresh is applied to an in-memory copy and only the JSON evidence is written
(no canonical-store mutation) so the script is safe to dry-run.
"""
from __future__ import annotations

import json
import os
import sys

from par_model_v2.governance.audit_trail import (
    AuditEntry,
    ChangeRecord,
    GovernanceStore,
    MitigationStatus,
    RiskRating,
)

GOV_PATH = os.path.join(".claude-dev", "GOVERNANCE_STORE.json")
OUT_DIR = os.path.join("docs", "validation")
JSON_PATH = os.path.join(OUT_DIR, "PHASE17_TASK5_GOVERNANCE_REFRESH.json")
MD_PATH = os.path.join(OUT_DIR, "PHASE17_TASK5_GOVERNANCE_REFRESH.md")
CARD_PATH = os.path.join("docs", "MULTI_DRIVER_3D_PROXY_LIMITATION_CARD.md")

MR_ID = "MR-012"
CHANGE_TITLE = (
    "Phase 17 Task 5 - three-driver (rate+equity+credit) economic-capital proxy governance refresh"
)

AFFECTED_COMPONENTS = [
    "par_model_v2/stochastic/credit_spread.py",
    "par_model_v2/projection/multi_driver_capital_3d.py",
    "par_model_v2/projection/multi_driver_proxy_validation.py",
    "par_model_v2/projection/multi_driver_risk_aggregation.py",
    "par_model_v2/projection/multi_driver_tail_diagnostics.py",
    "docs/MULTI_DRIVER_3D_PROXY_LIMITATION_CARD.md",
    "docs/validation/PHASE17_TASK5_GOVERNANCE_REFRESH.{json,md}",
    "par_model_v2/viewer/viewer_template.html",
    "scripts/build_offline_viewer.py",
]

STANDARD_REFERENCES = [
    "IA TAS M §3.6", "IA TAS M §3.7", "APS X2 §3",
    "SOA ASOP 56 §3.5", "SOA ASOP 25 §3.3",
    "IFoA proxy-modelling working party",
]


def _has_change_record(store: GovernanceStore, title: str) -> bool:
    return any(r.title == title for r in store.change_records)


def _has_risk(store: GovernanceStore, risk_id: str) -> bool:
    try:
        store.risk_register.get(risk_id)
        return True
    except KeyError:
        return False


def apply_phase17_task5_governance(store: GovernanceStore) -> dict:
    """Apply the Task 5 governance refresh to ``store`` in place (idempotent)."""
    actor = "Phase17Task5GovernanceRefresh"
    phase = "Phase 17: Third Risk Driver (Credit Spread) in the Economic-Capital Proxy"
    added_risk = False
    added_change = False

    # --- 1. MR-012: formalise the credit-driver / three-driver proxy residual ---
    if not _has_risk(store, MR_ID):
        store.risk_register.add(
            risk_id=MR_ID,
            title="Credit-spread driver and three-driver economic-capital proxy are educational, not production capital",
            description=(
                "Phase 17 adds a CIR++ mean-reverting credit-spread driver "
                "(par_model_v2/stochastic/credit_spread.py) as the third risk factor in the "
                "nested/LSMC economic-capital proxy (rate + equity + credit-spread), with a "
                "reduced-form hazard x LGD credit-loss component on spread-sensitive backing "
                "assets. The CIR++ parameters (mean-reversion, long-run spread, vol, risk "
                "premium) and the hazard/LGD assumptions are PLACEHOLDER educational defaults, "
                "NOT calibrated to credentialled credit-market data; the trivariate LSMC surface "
                "still omits material drivers (lapse, mortality/longevity trend, FX, liquidity, "
                "management action) and has NOT been independently reviewed (APS X2). The three-"
                "driver 99.5% VaR/ES and SCR-proxy figures are illustrative only and must not be "
                "used for regulatory or internal economic-capital reporting until the credit "
                "parameters are calibrated, the omitted drivers are brought into the tail, and an "
                "independent reviewer signs off."
            ),
            category="model_error",
            likelihood=RiskRating.MEDIUM,
            impact=RiskRating.HIGH,
            owner="Model Owner",
            mitigation=(
                "Classify all three-driver capital output as EDUCATIONAL ONLY in the consolidated "
                "limitation card and at the API boundary; bound proxy error by the Task 2 trivariate "
                "out-of-sample validation (OOS R^2=0.9751; selected basis deg1/max-int3; leakage-free) "
                "and outer-sampling error by the Task 4 three-driver bootstrap CI (VaR 150,859 with 95% "
                "CI [149,634, 152,369], SE 692 / +-0.91%); benchmark every aggregated figure to the Task "
                "3 three-driver nested ground truth. Residual closure requires credentialled credit-data "
                "calibration + independent APS X2 review (tracked jointly with MR-006 / MR-008 / MR-011)."
            ),
            related_standard="IA TAS M §3.6; APS X2 §3; SOA ASOP 56 §3.5; ASOP 25 §3.3",
            mitigation_status=MitigationStatus.IN_PROGRESS,
            notes=(
                "Opened by Phase 17 Task 5 governance refresh. Linked residual: MR-006 (validation "
                "readiness), MR-008 (HW1F calibration), MR-010 (factor-correlation diversification "
                "understatement, now ~38.7% with three drivers), MR-011 (multi-driver proxy educational)."
            ),
        )
        added_risk = True
        store.audit_trail.append(AuditEntry.governance(
            actor=actor, phase=phase,
            event="risk register update - opened MR-012 (credit-spread driver / three-driver capital proxy is educational)",
            details={
                "risk_id": MR_ID,
                "category": "model_error",
                "overall_rating": "HIGH",
                "mitigation_status": "IN_PROGRESS",
                "linked_residual": ["MR-006", "MR-008", "MR-010", "MR-011"],
                "new_driver": "credit_spread (CIR++)",
            },
        ))

    # --- 2. consolidated ChangeRecord (governance_change, OWNER_REVIEW) -----
    if not _has_change_record(store, CHANGE_TITLE):
        rr = store.risk_register
        rec = ChangeRecord.create(
            title=CHANGE_TITLE,
            description=(
                "Consolidated governance refresh for the Phase 17 three-driver economic-capital "
                "proxy (Tasks 1-4): added the CIR++ credit-spread driver and the trivariate "
                "(rate+equity+credit) nested ground truth + LSMC surface (Task 1), formal "
                "disjoint-seed out-of-sample trivariate proxy validation (Task 2, OOS R^2=0.9751), "
                "three-driver correlated risk aggregation (Task 3, honest PARTIAL), and three-driver "
                "tail-convergence / stability diagnostics (Task 4, PASS). Published a single "
                "consolidated three-driver model-limitation card, opened MR-012 to formalise the "
                "credit-driver educational-only classification and the credentialled-data + "
                "independent-review residual, and extended the offline result-viewer schema and "
                "Capital/Aggregation tabs to the three-driver proxy."
            ),
            change_type="governance_change",
            affected_components=AFFECTED_COMPONENTS,
            standard_references=STANDARD_REFERENCES,
            before_snapshot={
                "economic_capital_proxy_drivers": "two (short rate + equity)",
                "consolidated_limitation_card": "docs/MULTI_DRIVER_PROXY_LIMITATION_CARD.md (two-driver)",
                "open_risks_for_proxy": ["MR-010 (factor-correlation gap)", "MR-011 (multi-driver proxy educational)"],
                "offline_viewer": "Capital/Aggregation tabs render two drivers (rate + equity)",
            },
            after_snapshot={
                "economic_capital_proxy_drivers": "three (short rate + equity + credit spread)",
                "consolidated_limitation_card": "docs/MULTI_DRIVER_3D_PROXY_LIMITATION_CARD.md (three-driver)",
                "new_risk": "MR-012 (credit-spread driver / three-driver capital proxy is educational)",
                "mr_010_status": rr.get("MR-010").mitigation_status.value,
                "mr_011_status": rr.get("MR-011").mitigation_status.value if _has_risk(store, "MR-011") else None,
                "risk_register_total": len(rr.all()),
                "offline_viewer": "Capital/Aggregation tabs render three drivers (rate + equity + credit)",
            },
            impact_assessment=(
                "No numeric model output changes (governance + viewer-presentation only). Establishes "
                "a single point of reference for the three-driver capital proxy's scope, validated "
                "error bounds (trivariate OOS R^2=0.9751; three-driver outer-sampling SE +-0.91%; "
                "aggregation benchmarked to nested) and the explicit production residual: placeholder "
                "credit calibration, omitted risk drivers, factor-correlation diversification "
                "understatement (~38.7%, MR-010), and no independent APS X2 review. Educational "
                "classification retained; production sign-off withheld."
            ),
            author=actor,
            phase=phase,
            quantitative_impact="None (governance + viewer-presentation only). Residual: credentialled credit data + APS X2 review.",
        )
        rec.submit_for_peer_review(
            actor=actor,
            comments="Governance-only consolidation; underlying Task 1-4 modules unchanged; "
                     "regression PASS in batches; compileall + offline self-test clean.")
        rec.submit_to_owner(
            actor=actor,
            comments="Owner review: educational placeholder credit params; omitted risk drivers; "
                     "MR-010 factor-correlation understatement ~38.7%; independent APS X2 review "
                     "pending. Production sign-off withheld.")
        store.add_change_record(rec)
        added_change = True
        store.audit_trail.append(AuditEntry.governance(
            actor=actor, phase=phase,
            event="ChangeRecord opened (OWNER_REVIEW) - three-driver economic-capital proxy governance refresh",
            details={
                "record_id": rec.record_id,
                "change_type": "governance_change",
                "status": rec.status.value,
                "affected_components": AFFECTED_COMPONENTS,
                "drivers": ["short_rate", "equity", "credit_spread"],
            },
        ))

    # --- summary -------------------------------------------------------------
    rr = store.risk_register
    summary = {
        "task": "Phase 17 Task 5 - three-driver economic-capital proxy governance refresh",
        "phase_complete": "Phase 17 COMPLETE",
        "drivers": ["short_rate", "equity", "credit_spread"],
        "added_risk_MR_012": added_risk,
        "added_change_record": added_change,
        "change_record_status": next(
            (r.status.value for r in store.change_records if r.title == CHANGE_TITLE), None),
        "audit_entries": len(store.audit_trail.all()),
        "audit_integrity_ok": store.audit_trail.verify_all(),
        "change_records_total": len(store.change_records),
        "risk_register_summary": rr.summary(),
        "mr_012": rr.get(MR_ID).to_dict() if _has_risk(store, MR_ID) else None,
        "limitation_card": CARD_PATH,
        "residual": (
            "Credentialled credit-data calibration + independent APS X2 review pending; "
            "omitted risk drivers (lapse/mortality/FX/liquidity/management action) outside the "
            "tail; factor-correlation diversification understatement ~38.7% (MR-010). "
            "Educational classification retained."
        ),
        "standard_references": STANDARD_REFERENCES,
    }
    return summary


def _md(summary: dict) -> str:
    rr = summary["risk_register_summary"]
    lines = [
        "# Phase 17 Task 5 — Three-Driver Economic-Capital Proxy Governance Refresh",
        "",
        "**Classification:** EDUCATIONAL ONLY — placeholder parameters; not a regulatory capital model.",
        "",
        f"**Task:** {summary['task']}",
        f"**Status:** {summary['phase_complete']}",
        f"**Drivers:** {', '.join(summary['drivers'])}.",
        "",
        "## Governance actions",
        "",
        f"- **MR-012** opened: {summary['added_risk_MR_012']} "
        "(credit-spread driver / three-driver capital proxy is educational, HIGH, IN_PROGRESS).",
        f"- **ChangeRecord** added: {summary['added_change_record']} — "
        f"status **{summary['change_record_status']}** (production sign-off withheld).",
        f"- **Audit chain:** {summary['audit_entries']} entries; integrity verified: "
        f"{summary['audit_integrity_ok']}.",
        f"- **Risk register:** {rr['total']} total "
        f"({rr['by_status']}).",
        f"- **Consolidated limitation card:** `{summary['limitation_card']}`.",
        "",
        "## Residual (production sign-off blocker)",
        "",
        summary["residual"],
        "",
        "## Standards",
        "",
        ", ".join(summary["standard_references"]) + ".",
        "",
    ]
    return "\n".join(lines)


def main(use_governance: bool = False) -> dict:
    blob = open(GOV_PATH, encoding="utf-8").read()
    store = GovernanceStore.from_json(blob)
    summary = apply_phase17_task5_governance(store)

    os.makedirs(OUT_DIR, exist_ok=True)
    with open(JSON_PATH, "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2)
    with open(MD_PATH, "w", encoding="utf-8") as fh:
        fh.write(_md(summary))

    if use_governance:
        with open(GOV_PATH, "w", encoding="utf-8") as fh:
            fh.write(store.to_json())
        print("governance: store written ->", GOV_PATH)

    print("MR-012 added:", summary["added_risk_MR_012"],
          "| ChangeRecord added:", summary["added_change_record"],
          "| status:", summary["change_record_status"])
    print("audit entries:", summary["audit_entries"],
          "| integrity:", summary["audit_integrity_ok"],
          "| change records:", summary["change_records_total"])
    print("risk register:", summary["risk_register_summary"])
    print("evidence ->", JSON_PATH)
    return summary


if __name__ == "__main__":
    main(use_governance="--governance" in sys.argv)
