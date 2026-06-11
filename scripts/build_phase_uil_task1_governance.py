#!/usr/bin/env python3
"""Phase UIL Task 1 (B1): governance ChangeRecord for the user-input loader.

Opens an idempotent code_change ChangeRecord at OWNER_REVIEW for
scripts/load_user_inputs.py + tests/test_user_inputs.py and logs the
matching governance AuditEntry. No model math, no capital figure changes.

Usage: python3 scripts/build_phase_uil_task1_governance.py
"""
import json
import sys

sys.path.insert(0, ".")
from par_model_v2.governance.audit_trail import AuditEntry, ChangeRecord, GovernanceStore  # noqa: E402

GOV_PATH = ".claude-dev/GOVERNANCE_STORE.json"
ACTOR = "AutomatedModelDev_PhaseUIL"
PHASE = "Phase UIL: User-Input Loader + Run Orchestrator"
TITLE = ("Phase UIL Task 1 - user-input loader scripts/load_user_inputs.py: "
         "template xlsx -> validated schema-versioned model_inputs.json (pure I/O, no model math)")
AFFECTED = [
    "scripts/load_user_inputs.py",
    "tests/test_user_inputs.py",
    "production_run/USER_MANUAL_run_and_inputs.md",
]
REFS = [
    "SOA ASOP 56 section 3.2 (model inputs) and 3.5 (reliance on data supplied by others)",
    "ASOP 23 Data Quality (review and validation of data used in the model)",
    "IA TAS M sections 3.2 (data) and 3.7 (change control)",
    "IMPLEMENTATION_PLAN_currency_and_inputs.md workstream B1 (owner-approved design note)",
]


def main() -> dict:
    store = GovernanceStore.from_json(open(GOV_PATH).read())
    if any(r.title == TITLE for r in store.change_records):
        out = {"added": False, "reason": "already applied (idempotent)"}
    else:
        rec = ChangeRecord.create(
            title=TITLE,
            description=(
                "New standalone loader reading production_run/MODEL_INPUTS_TEMPLATE.xlsx by tab "
                "name + header (openpyxl): validates currency block (ISO code, symbol, decimals, "
                "scale, separator, market label, valuation date), balance sheet (asset MVs >= 0, "
                "positive total, derived illiquid share, forced-sale fraction in (0,1], positive "
                "BEL and guarantee index), portfolio model points (allowed product set "
                "HKCD_PAR_2026/HKRB_PAR_2026/GMMB_EQ_2026, complete rows, age/term/SA/premium/"
                "count/bonus ranges), assumptions (confidence in (0,1); relief sigma > 0; alpha, "
                "benefit share in (0,1]), and run settings (positive integer n_sim/replicates/"
                "horizon, integer seed, non-empty label). Writes schema-versioned (1.0.0) "
                "model_inputs.json, re-parses it before exit, echoes currency/total MV/total SA/"
                "policy count. Fails loudly listing every issue as tab/row/field. Frozen copula "
                "parameters are read back for provenance only and are NOT user-settable. Pure "
                "I/O + validation; zero impact on any governed capital figure."
            ),
            change_type="code_change",
            affected_components=AFFECTED,
            standard_references=REFS,
            before_snapshot={
                "loader": "absent - user inputs hardcoded in fixtures/synthetic generator",
                "user_manual_section_4": "documented as 'once the loader is wired in' (not live)",
            },
            after_snapshot={
                "loader": "scripts/load_user_inputs.py LIVE (schema_version 1.0.0)",
                "tests": "tests/test_user_inputs.py 19 passed (happy path + 15 fail-loud cases)",
                "template_echo_check": {
                    "currency": "USD", "backing_asset_mv": 100000.0,
                    "total_sum_assured": 290000000.0, "policy_count": 2500,
                },
                "governed_frozen_user_settable": False,
            },
            impact_assessment=(
                "Additive tooling only: no model code path consumes model_inputs.json yet "
                "(that is Task 2/B2 with governed fallbacks). The governed frozen-t headline "
                "and all calibrated parameters are unchanged and remain frozen."
            ),
            author=ACTOR,
            phase=PHASE,
            quantitative_impact="None - pure I/O + validation; no capital figure touched.",
        )
        rec.submit_for_peer_review(actor=ACTOR, comments="Loader + 19 unit tests green; manual section 4 marked LIVE.")
        rec.submit_to_owner(actor=ACTOR, comments="Self-review (automated dev): pure I/O tooling, no capital impact; owner sign-off requested per plan B1.")
        store.add_change_record(rec)
        store.audit_trail.append(AuditEntry.governance(
            actor=ACTOR, phase=PHASE,
            event="ChangeRecord opened (OWNER_REVIEW) - Phase UIL Task 1 user-input loader (B1)",
            details={"record_id": rec.record_id, "change_type": "code_change",
                     "status": rec.status.value, "affected_components": AFFECTED},
        ))
        with open(GOV_PATH, "w", encoding="utf-8") as fh:
            fh.write(store.to_json())
        out = {"added": True, "record_id": rec.record_id, "status": rec.status.value}
    out["audit_entries"] = len(store.audit_trail.all())
    out["audit_integrity_ok"] = store.audit_trail.verify_all()
    out["change_records_total"] = len(store.change_records)
    # re-parse to confirm the store is not corrupted
    json.load(open(GOV_PATH))
    return out


if __name__ == "__main__":
    print(json.dumps(main(), indent=1, default=str))
