#!/usr/bin/env python3
"""Phase UIL Task 2 (B2): governance ChangeRecord for de-hardcoded fixtures.

Opens an idempotent code_change ChangeRecord at OWNER_REVIEW for the optional
user-input plumbing (par_model_v2/user_inputs.py + additive hooks in the
phase22 exposure calibration and the portfolio generator) and logs the
matching governance AuditEntry.  With no model_inputs.json present every
governed read-out is bit-identical to the fixture pipeline (regression-gated
by tests/test_user_inputs_integration.py).

Usage: python3 scripts/build_phase_uil_task2_governance.py
"""
import json
import sys

sys.path.insert(0, ".")
from par_model_v2.governance.audit_trail import AuditEntry, ChangeRecord, GovernanceStore  # noqa: E402

GOV_PATH = ".claude-dev/GOVERNANCE_STORE.json"
ACTOR = "AutomatedModelDev_PhaseUIL"
PHASE = "Phase UIL: User-Input Loader + Run Orchestrator"
TITLE = ("Phase UIL Task 2 - de-hardcode fixtures (B2): optional model_inputs.json plumbing "
         "with governed bit-identical fallbacks (par_model_v2/user_inputs.py)")
AFFECTED = [
    "par_model_v2/user_inputs.py",
    "par_model_v2/calibration/phase22_liquidity_exposure_calibration.py",
    "par_model_v2/projection/portfolio_generator.py",
    "tests/test_user_inputs_integration.py",
]
REFS = [
    "SOA ASOP 56 sections 3.2 (model inputs) and 3.6 (model testing - regression gate)",
    "ASOP 23 Data Quality (validation of data supplied by others before use)",
    "IA TAS M sections 3.2 (data) and 3.7 (change control)",
    "IMPLEMENTATION_PLAN_currency_and_inputs.md workstream B2 (owner-approved design note)",
]


def main() -> dict:
    store = GovernanceStore.from_json(open(GOV_PATH).read())
    if any(r.title == TITLE for r in store.change_records):
        out = {"added": False, "reason": "already applied (idempotent)"}
    else:
        rec = ChangeRecord.create(
            title=TITLE,
            description=(
                "New single access point par_model_v2/user_inputs.py for the schema-versioned "
                "model_inputs.json (resolution: explicit path -> PAR_MODEL_INPUTS env var -> "
                "production_run/model_inputs.json -> repo root; absent file -> None / governed "
                "defaults; present-but-broken file -> UserInputsError, never silent fallback). "
                "Additive consumer hooks: (1) phase22 resolve_exposure_spec overlays user "
                "backing_asset_mv / illiquid_share / forced_sale_fraction on the fixture spec "
                "with provenance flag exposure_source, leaving derive_exposure_notional and its "
                "gate unchanged; (2) portfolio_generator portfolio_from_model_points builds the "
                "unified PAR table from user model points (one record per model point, "
                "inforce_count = policy_count, fail-loud row-level validation against Phase 10 "
                "mechanics, GMMB rows split out for the B3 orchestrator) and build_portfolio "
                "dispatches user book vs synthetic generator; (3) capital_params returns "
                "confidence/relief_sigma/relief_alpha/benefit_share with governed defaults "
                "0.995 / 0.225 / 0.7567 / 0.8450 for the B3 orchestrator to pass through. "
                "Frozen copula df / grouped-t dfs remain governed and are NOT user-settable."
            ),
            change_type="code_change",
            affected_components=AFFECTED,
            standard_references=REFS,
            before_snapshot={
                "exposure_inputs": "fixture-only (100000 / 0.55 / 0.40)",
                "portfolio": "synthetic generator only (PHASE11-HK-PAR-SYNTHETIC-100K)",
                "capital_params": "hardcoded at call sites (0.995 / 0.225 / 0.7567 / 0.8450)",
            },
            after_snapshot={
                "user_inputs_module": "par_model_v2/user_inputs.py LIVE (schema major 1)",
                "tests": "tests/test_user_inputs_integration.py 19 passed; "
                         "test_portfolio_generator + test_phase22_task3 35 passed unchanged",
                "regression_gate": "no model_inputs.json -> exposure inputs, portfolio digest "
                                   "and capital params bit-identical to governed pipeline",
                "governed_frozen_user_settable": False,
            },
            impact_assessment=(
                "Additive, backward-compatible plumbing with explicit regression gate: with no "
                "user inputs present every consumer returns exactly the fixture/governed values "
                "(exact-equality tests). No governed capital figure changes. The orchestrator "
                "(B3) is the first code path that will activate these hooks end-to-end."
            ),
            author=ACTOR,
            phase=PHASE,
            quantitative_impact=(
                "None with no inputs file (bit-identical gate). With user inputs, capital "
                "results reflect the user's balance sheet / book / assumptions by design."
            ),
        )
        rec.submit_for_peer_review(actor=ACTOR, comments="B2 hooks + 19 integration tests green; existing 35 phase22/portfolio tests unchanged.")
        rec.submit_to_owner(actor=ACTOR, comments="Self-review (automated dev): additive plumbing, bit-identical fallback gate; owner sign-off requested per plan B2.")
        store.add_change_record(rec)
        store.audit_trail.append(AuditEntry.governance(
            actor=ACTOR, phase=PHASE,
            event="ChangeRecord opened (OWNER_REVIEW) - Phase UIL Task 2 de-hardcoded fixtures (B2)",
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
