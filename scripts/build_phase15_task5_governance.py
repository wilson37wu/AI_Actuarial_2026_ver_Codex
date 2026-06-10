"""Build Phase 15 Task 5 governance refresh for the multi-driver economic-capital proxy.

Phase 15 Task 5 — "Refresh governance: model-limitation card, ChangeRecord, MR
register update for the multi-driver proxy; document model-use restrictions and
the remaining credentialled-data / independent-review residual."

This consolidates the governance of the four Phase 15 multi-driver capital
modules built in Tasks 1-4:

    par_model_v2/projection/multi_driver_capital.py            (Task 1)
    par_model_v2/projection/multi_driver_proxy_validation.py   (Task 2)
    par_model_v2/projection/multi_driver_risk_aggregation.py   (Task 3)
    par_model_v2/projection/multi_driver_tail_diagnostics.py   (Task 4)

It is idempotent: re-running detects the already-applied MR entry and
ChangeRecord by their stable keys and does not duplicate them.

Run:  PYTHONPATH=. python3 scripts/build_phase15_task5_governance.py [--governance]

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
    SignOffStatus,
)

GOV_PATH = os.path.join(".claude-dev", "GOVERNANCE_STORE.json")
OUT_DIR = os.path.join("docs", "validation")
JSON_PATH = os.path.join(OUT_DIR, "PHASE15_TASK5_GOVERNANCE_REFRESH.json")

MR_ID = "MR-011"
CHANGE_TITLE = (
    "Phase 15 Task 5 - multi-driver economic-capital proxy governance refresh"
)

AFFECTED_COMPONENTS = [
    "par_model_v2/projection/multi_driver_capital.py",
    "par_model_v2/projection/multi_driver_proxy_validation.py",
    "par_model_v2/projection/multi_driver_risk_aggregation.py",
    "par_model_v2/projection/multi_driver_tail_diagnostics.py",
    "docs/MULTI_DRIVER_PROXY_LIMITATION_CARD.md",
    "docs/validation/PHASE15_TASK5_GOVERNANCE_REFRESH.{json,md}",
]

STANDARD_REFERENCES = [
    "IA TAS M §3.6", "IA TAS M §3.7", "APS X2 §3",
    "SOA ASOP 56 §3.5", "SOA ASOP 25 §3.3",
    "IFoA Modelling Practice Note §4",
]


def _has_change_record(store: GovernanceStore, title: str) -> bool:
    return any(r.title == title for r in store.change_records)


def _has_risk(store: GovernanceStore, risk_id: str) -> bool:
    try:
        store.risk_register.get(risk_id)
        return True
    except KeyError:
        return False


def apply_phase15_task5_governance(store: GovernanceStore) -> dict:
    """Apply the Task 5 governance refresh to ``store`` in place (idempotent).

    Returns a summary dict suitable for JSON evidence.
    """
    actor = "Phase15Task5GovernanceRefresh"
    phase = "Phase 15: Multi-Risk Economic Capital and Proxy-Model Validation"
    added_risk = False
    added_change = False

    # --- 1. MR-011: formalise the multi-driver proxy production residual ----
    if not _has_risk(store, MR_ID):
        store.risk_register.add(
            risk_id=MR_ID,
            title="Multi-driver economic-capital proxy is educational, not production capital",
            description=(
                "The Phase 15 multi-driver (short-rate + equity) nested/LSMC economic-capital "
                "proxy (Tasks 1-4) is fitted on PLACEHOLDER HW1F / GBM parameters, omits material "
                "risk drivers (lapse, mortality/longevity trend, credit spread, FX, liquidity, "
                "management action), uses an educational single-guarantee liability, and has NOT "
                "been independently reviewed (APS X2). The 99.5% VaR/ES and SCR-proxy figures it "
                "produces are illustrative only and must not be used for regulatory or internal "
                "economic-capital reporting until parameters are calibrated to credentialled market "
                "data, the omitted drivers are brought into the tail, and an independent reviewer "
                "signs off."
            ),
            category="model_error",
            likelihood=RiskRating.MEDIUM,
            impact=RiskRating.HIGH,
            owner="Model Owner",
            mitigation=(
                "Classify all multi-driver capital output as EDUCATIONAL ONLY in the limitation "
                "card and at the API boundary; bound proxy error by the Task 2 out-of-sample "
                "validation (OOS R^2=0.9704, VaR rel err 3.21%) and outer-sampling error by the "
                "Task 4 bootstrap CI (SE ~1.66%); benchmark every aggregated figure to the Task 3 "
                "nested ground truth. Residual closure requires credentialled-data calibration + "
                "independent APS X2 review (tracked jointly with MR-006 / MR-008)."
            ),
            related_standard="IA TAS M §3.6; APS X2 §3; SOA ASOP 56 §3.5",
            mitigation_status=MitigationStatus.IN_PROGRESS,
            notes=(
                "Opened by Phase 15 Task 5 governance refresh. Linked residual: MR-006 (validation "
                "readiness), MR-008 (HW1F calibration), MR-010 (aggregation diversification gap)."
            ),
        )
        added_risk = True
        store.audit_trail.append(AuditEntry.governance(
            actor=actor, phase=phase,
            event="risk register update - opened MR-011 (multi-driver capital proxy is educational)",
            details={
                "risk_id": MR_ID,
                "category": "model_error",
                "overall_rating": "HIGH",
                "mitigation_status": "IN_PROGRESS",
                "linked_residual": ["MR-006", "MR-008", "MR-010"],
            },
        ))

    # --- 2. consolidated ChangeRecord (governance_change, OWNER_REVIEW) -----
    if not _has_change_record(store, CHANGE_TITLE):
        rr = store.risk_register
        rec = ChangeRecord.create(
            title=CHANGE_TITLE,
            description=(
                "Consolidated governance refresh for the Phase 15 multi-driver economic-capital "
                "proxy (Tasks 1-4): published a single multi-driver-proxy model-limitation card, "
                "opened MR-011 to formalise the educational-only classification and the "
                "credentialled-data + independent-review residual, and restated the model-use "
                "restrictions spanning the two-driver LSMC surface (Task 1), the out-of-sample "
                "proxy validation (Task 2), the correlated risk aggregation (Task 3), and the "
                "tail-convergence / stability diagnostics (Task 4)."
            ),
            change_type="governance_change",
            affected_components=AFFECTED_COMPONENTS,
            standard_references=STANDARD_REFERENCES,
            before_snapshot={
                "multi_driver_proxy_governance": (
                    "Per-task limitation cards (CAPITAL/RISK_AGGREGATION/TAIL_DIAGNOSTICS) and "
                    "OWNER_REVIEW ChangeRecords existed, but there was no consolidated multi-driver "
                    "proxy limitation card and no single MR entry classifying the proxy as educational."
                ),
                "open_risks_for_multi_driver_proxy": ["MR-010 (diversification gap)"],
            },
            after_snapshot={
                "consolidated_limitation_card": "docs/MULTI_DRIVER_PROXY_LIMITATION_CARD.md",
                "new_risk": "MR-011 (multi-driver capital proxy is educational, not production)",
                "mr_010_status": rr.get("MR-010").mitigation_status.value,
                "risk_register_total": len(rr.all()),
            },
            impact_assessment=(
                "No numeric model output changes (governance-only). Establishes a single point of "
                "reference for the multi-driver capital proxy's scope, validated error bounds "
                "(proxy OOS R^2=0.9704; outer-sampling SE ~1.66%; aggregation benchmarked to nested), "
                "and the explicit production residual: placeholder calibration, omitted risk drivers, "
                "and no independent APS X2 review. Educational classification retained; production "
                "sign-off withheld."
            ),
            author=actor,
            phase=phase,
            quantitative_impact="None (governance-only). Residual: credentialled data + APS X2 review.",
        )
        rec.submit_for_peer_review(
            actor=actor,
            comments="Governance-only consolidation; underlying Task 1-4 modules unchanged; "
                     "1650+ regression tests PASS; compileall clean.")
        rec.submit_to_owner(
            actor=actor,
            comments="Owner review: educational placeholder params; omitted risk drivers; "
                     "independent APS X2 review pending. Production sign-off withheld.")
        store.add_change_record(rec)
        added_change = True
        store.audit_trail.append(AuditEntry.governance(
            actor=actor, phase=phase,
            event="ChangeRecord opened (OWNER_REVIEW) - multi-driver proxy governance refresh",
            details={
                "record_id": rec.record_id,
                "change_type": "governance_change",
                "status": rec.status.value,
                "affected_components": AFFECTED_COMPONENTS,
            },
        ))

    # --- summary -------------------------------------------------------------
    rr = store.risk_register
    summary = {
        "task": "Phase 15 Task 5 - multi-driver economic-capital proxy governance refresh",
        "added_risk_MR_011": added_risk,
        "added_change_record": added_change,
        "change_record_status": next(
            (r.status.value for r in store.change_records if r.title == CHANGE_TITLE), None),
        "audit_entries": len(store.audit_trail.all()),
        "audit_integrity_ok": store.audit_trail.verify_all(),
        "change_records_total": len(store.change_records),
        "risk_register_summary": rr.summary(),
        "mr_011": rr.get(MR_ID).to_dict() if _has_risk(store, MR_ID) else None,
        "limitation_card": "docs/MULTI_DRIVER_PROXY_LIMITATION_CARD.md",
        "residual": (
            "Credentialled-data calibration + independent APS X2 review pending; "
            "omitted risk drivers (lapse/mortality/credit/FX/liquidity/management action) "
            "outside the tail. Educational classification retained."
        ),
        "standard_references": STANDARD_REFERENCES,
    }
    return summary


def main(use_governance: bool = False) -> dict:
    blob = open(GOV_PATH).read()
    store = GovernanceStore.from_json(blob)
    summary = apply_phase15_task5_governance(store)

    os.makedirs(OUT_DIR, exist_ok=True)
    with open(JSON_PATH, "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2)

    if use_governance:
        with open(GOV_PATH, "w", encoding="utf-8") as fh:
            fh.write(store.to_json())
        print("governance: store written ->", GOV_PATH)

    print("MR-011 added:", summary["added_risk_MR_011"],
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
