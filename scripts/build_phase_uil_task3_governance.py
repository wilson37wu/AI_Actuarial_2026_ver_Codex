#!/usr/bin/env python3
"""Phase UIL Task 3 (B3): governance ChangeRecord for the run orchestrator.

Opens an idempotent code_change ChangeRecord at OWNER_REVIEW for
scripts/run_model.py (single user-facing entry point threading
model_inputs.json through the governed Phase 22 Task 4 seven-driver engine)
plus the production_run/run_production_model.py capital-stage wire-through,
and logs the matching governance AuditEntry.  With no model_inputs.json the
orchestrator resolves the EXACT governed Phase 22 Task 4 parameters
(regression-gated by tests/test_run_model.py).

Usage: python3 scripts/build_phase_uil_task3_governance.py
"""
import json
import sys

sys.path.insert(0, ".")
from par_model_v2.governance.audit_trail import AuditEntry, ChangeRecord, GovernanceStore  # noqa: E402

GOV_PATH = ".claude-dev/GOVERNANCE_STORE.json"
ACTOR = "AutomatedModelDev_PhaseUIL"
PHASE = "Phase UIL: User-Input Loader + Run Orchestrator"
TITLE = ("Phase UIL Task 3 - run orchestrator (B3): scripts/run_model.py single entry point "
         "threading model_inputs.json through the governed seven-driver engine")
AFFECTED = [
    "scripts/run_model.py",
    "production_run/run_production_model.py",
    "production_run/USER_MANUAL_run_and_inputs.md",
    "tests/test_run_model.py",
    "docs/validation/RUN_MODEL_AGGREGATION_REPORT.json",
    "docs/validation/RUN_MODEL_SUMMARY.json",
]
REFS = [
    "SOA ASOP 56 sections 3.2 (model inputs), 3.5 (model-use restriction) and 3.6 (testing)",
    "IA TAS M sections 3.2 (data) and 3.7 (change control)",
    "Solvency II Delegated Regulation Article 234 (aggregation basis unchanged)",
    "IMPLEMENTATION_PLAN_currency_and_inputs.md workstream B3 (owner-approved design note)",
]


def main() -> dict:
    store = GovernanceStore.from_json(open(GOV_PATH).read())
    if any(r.title == TITLE for r in store.change_records):
        out = {"added": False, "reason": "already applied (idempotent)"}
    else:
        rec = ChangeRecord.create(
            title=TITLE,
            description=(
                "New scripts/run_model.py: single user-facing entry point (python3 "
                "scripts/run_model.py --inputs model_inputs.json) threading validated user "
                "inputs through the UNCHANGED governed Phase 22 Task 4 seven-driver engine: "
                "standalone losses -> 7x7 var-covar -> copula aggregation (AIC on realised "
                "losses) -> nested benchmark -> bootstrap SCR CIs -> tail diagnostics. "
                "Honours Run Settings n_sim / seed / bootstrap_replicates / horizon_months / "
                "output_label and Assumptions confidence (CLI flags override; per-field "
                "provenance recorded). Representative capital model point: governed synthetic "
                "45/M/100,000/5,000/20y with no inputs (bit-identical parameters), else the "
                "inforce-weighted mean of the user PAR rows with the term snapped to the "
                "nearest supported product term and the book totals + linear scale factor "
                "DISCLOSED as approximation (not a governed result); GMMB rows split out and "
                "disclosed. Liquidity exposure notional: user balance sheet via the B2 "
                "resolve_exposure_spec overlay, else the archived G-LIQX calibration "
                "(fail-loud on placeholders). Frozen seven-driver correlation always governed, "
                "never user-settable. Writes docs/validation/RUN_MODEL_AGGREGATION_REPORT.json "
                "(same structural 'aggregation' contract as PHASE22_TASK4_AGGREGATION_REPORT."
                "json, the snapshot build_ui_data.py parses) + RUN_MODEL_SUMMARY.json, both "
                "re-parse-guarded; governed evidence files are never overwritten. "
                "production_run/run_production_model.py gains a 'capital' stage that calls the "
                "orchestrator automatically under --stage all when model_inputs.json exists "
                "(skipped with a pointer message otherwise; explicit --stage capital runs the "
                "governed-default profile; no seed pass-through so the template seed wins)."
            ),
            change_type="code_change",
            affected_components=AFFECTED,
            standard_references=REFS,
            before_snapshot={
                "entry_point": "developer build scripts only (per-phase, not user-facing)",
                "user_run_path": "template -> load_user_inputs.py -> model_inputs.json -> (manual)",
                "production_run_stages": "esg / assets / liabilities / interaction",
            },
            after_snapshot={
                "entry_point": "scripts/run_model.py LIVE (B3); manual section 4 step 3 LIVE",
                "production_run_stages": "esg / assets / liabilities / interaction / capital",
                "tests": "tests/test_run_model.py 23 passed (plan resolution, parameter-"
                         "identity vs archived P22T4 config/exposure, weighted-mean "
                         "representative product, GUI structural contract, fail-loud gates)",
                "regression_gate": "no model_inputs.json -> resolved plan + product + exposure "
                                   "notional parameter-identical to archived Phase 22 Task 4 "
                                   "evidence (asserted against the committed report)",
                "worked_example": "template demo book (3 model points, 2,500 policies, USD) "
                                  "run end-to-end; evidence docs/validation/RUN_MODEL_*.json",
            },
            impact_assessment=(
                "Additive orchestration layer over governed primitives; no engine, calibration "
                "or dependence-structure change, so no governed capital read-out moves. User "
                "runs write to NEW RUN_MODEL_* evidence files; governed PHASE*_REPORT.json "
                "files are read-only inputs. Model-use restriction propagated into every "
                "output. Risk: users may misread the disclosed linear book-scaling "
                "approximation as a governed result - mitigated by explicit notes in the "
                "report, summary and manual."
            ),
            author=ACTOR,
            phase=PHASE,
            quantitative_impact=(
                "None to governed evidence (orchestrator is read-only over governed "
                "parameters and writes separate RUN_MODEL_* files). User runs reflect the "
                "user's book / balance sheet / run settings by design; worked example "
                "(template demo book, n_sim 20,000, seed 20260608) committed as evidence."
            ),
        )
        rec.submit_for_peer_review(actor=ACTOR, comments="B3 orchestrator + 23 tests green; parameter-identity gate vs archived P22T4 asserted in tests.")
        rec.submit_to_owner(actor=ACTOR, comments="Self-review (automated dev): additive entry point over unchanged governed engine; owner sign-off requested per plan B3.")
        store.add_change_record(rec)
        store.audit_trail.append(AuditEntry.governance(
            actor=ACTOR, phase=PHASE,
            event="ChangeRecord opened (OWNER_REVIEW) - Phase UIL Task 3 run orchestrator (B3)",
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
