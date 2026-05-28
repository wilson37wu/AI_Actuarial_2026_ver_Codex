# Model Governance and Audit Trail Framework
## PAR Fund Stochastic ALM & TVOG Model

**Document Type:** Governance Framework Specification  
**Prepared by:** Claude Actuarial Agent (Automated Cycle 11)  
**Date:** 2026-05-18  
**Phase:** 2 — Industry Standards Alignment  
**Task:** Implement governance and audit trail framework (Task 4 of 6)  
**Module:** `par_model_v2/governance/audit_trail.py`  
**Version:** 1.0  
**Status:** DRAFT — Pending Assumption Owner sign-off  

---

## 1. Executive Summary

This document specifies the governance and audit trail framework implemented for the PAR Fund Stochastic ALM & TVOG Model. The framework closes the material governance gap identified in Phase 1 (MR-007: No assumption change control process) and remediates the following IA TAS M requirements previously rated non-compliant:

| Requirement | Prior Status | Post-Implementation Status |
|-------------|-------------|---------------------------|
| IA TAS M §3.3 — Model governance and ownership | 🔴 Non-compliant | 🟠 Framework in place; adoption required |
| IA TAS M §3.5 — Assumption sign-off workflow | 🔴 Non-compliant | 🟠 Workflow implemented; requires process adoption |
| IA TAS M §3.7 — Model change control | 🔴 Non-compliant | 🟠 ChangeRecord format implemented; requires usage |
| SOA ASOP 56 §3.5 — Validation governance | 🟠 Partial | 🟠 AuditTrail captures validation events; stochastic validation Phase 3 |
| IFoA Practice Note §4 — Model risk register | 🔴 Non-compliant | 🟠 8 risks seeded from Phase 1; live updates required |

**Key limitation:** The framework provides the technical infrastructure. Full compliance requires organisational adoption — actors must use ChangeRecord and AuditTrail in every model run and assumption change. Until that discipline is in place, the governance register will diverge from reality.

---

## 2. Standards Reference

### IA TAS M (Technical Actuarial Standard: Models, 2016/2021)

**§3.3 Governance and Ownership**  
Requires a nominated Model Owner responsible for fitness-for-purpose, model governance, and sign-off on material outputs. Implemented via `GovernanceStore.model_name` and `ChangeRecord.assumption_owner`.

**§3.5 Assumptions**  
All material assumptions must be documented, appropriately set, and signed off by the Assumption Owner. Implemented via `ChangeRecord` and `SignOffWorkflow` (three-stage: DRAFT → PEER_REVIEW → OWNER_REVIEW → APPROVED).

**§3.7 Change Control**  
Every material model or assumption change must be recorded with: description, before/after snapshots, impact assessment, author, reviewer, and approval status. Implemented via `ChangeRecord` with enforced `sign_off_history`.

### SOA ASOP 56 (Modeling, 2019)

**§3.5 Model Validation**  
Validation events must be recorded, including test suite results, failure counts, and outcome. Implemented via `AuditEntry.validation()`.

### IFoA Actuarial Modelling Practice Note (2015)

**§4 Model Risk Management**  
Requires a model risk register with risk descriptions, ratings, owners, and mitigation status. Implemented via `ModelRiskRegister` with 8 seeded entries from Phase 1.

---

## 3. Framework Architecture

### 3.1 Component Overview

```
par_model_v2/governance/
├── __init__.py              — clean public API
└── audit_trail.py           — all classes (400+ lines)
    ├── EntryType             — enum: MODEL_RUN, PARAM_CHANGE, VALIDATION, SIGN_OFF, CORRECTION, GOVERNANCE
    ├── SignOffStatus         — enum: DRAFT, PEER_REVIEW, OWNER_REVIEW, APPROVED, REJECTED, SUPERSEDED
    ├── RiskRating            — enum: LOW, MEDIUM, HIGH, CRITICAL
    ├── MitigationStatus      — enum: OPEN, IN_PROGRESS, MITIGATED, ACCEPTED
    ├── AuditEntry            — immutable, SHA-256 digested, frozen dataclass
    ├── AuditTrail            — append-only list; integrity verification
    ├── ChangeRecord          — IA TAS M §3.7 compliant; full sign-off workflow
    ├── RiskEntry             — single model risk register entry
    ├── ModelRiskRegister     — IFoA §4 register with CRUD and filtering
    ├── GovernanceStore       — composite store; JSON serialisable
    └── seed_initial_risk_register() — seeder from Phase 1 findings
```

### 3.2 Design Principles

**Append-only audit trail.** `AuditEntry` is a frozen dataclass — no field can be modified after creation. Corrections are handled by creating a new `CORRECTION` entry that references the original. This prevents retrospective manipulation of the audit log.

**SHA-256 digest integrity.** Every `AuditEntry` contains a digest of its key fields. `AuditTrail.verify_all()` and `integrity_report()` detect any post-creation tampering.

**Strict sign-off state machine.** `ChangeRecord` enforces IA TAS M §3.5 stage ordering. Skipping stages raises `ValueError`. Approving a record that hasn't been owner-reviewed is impossible by design.

**Fully serialisable.** `GovernanceStore.to_json()` / `from_json()` enables persistence to `.claude-dev/GOVERNANCE_STORE.json`. The automated cycle appends to the store each run.

---

## 4. Sign-Off Workflow (IA TAS M §3.5)

Every material assumption or methodology change must follow this three-stage workflow:

```
Author creates ChangeRecord (status: DRAFT)
    │
    ▼
Author submits for peer review → status: PEER_REVIEW
    │  (Peer reviewer: Senior Actuary / APS X2 reviewer)
    │  [review, comments, possibly REJECTED → back to DRAFT]
    ▼
Peer reviewer submits to owner → status: OWNER_REVIEW
    │  (Assumption Owner: Head of Actuarial / signing actuary)
    │  [review, comments, possibly REJECTED → back to DRAFT]
    ▼
Assumption Owner approves → status: APPROVED
    │
    ▼
ChangeRecord locked; AuditEntry.sign_off() recorded
```

**When is a ChangeRecord required?**

| Change Type | ChangeRecord Required? | Notes |
|-------------|----------------------|-------|
| ESG parameter change (a, σ_r, σ_S, ERP) | ✅ Yes | Material calibration change |
| Discount rate change | ✅ Yes | Regulatory impact |
| Lapse / mortality assumption change | ✅ Yes | TVOG-sensitive |
| Code refactor (no behavioural change) | 🟠 Optional | Document in commit message |
| Test addition / documentation update | ❌ No | Low governance risk |
| Phase boundary transition | ✅ Yes | Record phase completion |

---

## 5. Model Risk Register (IFoA §4)

The register is seeded with 8 entries from Phase 1 findings. Current summary:

| Risk ID | Title | Rating | Status |
|---------|-------|--------|--------|
| MR-001 | Discount rate exceeds CBIRC cap | CRITICAL | IN_PROGRESS |
| MR-002 | Investment returns overstated vs CNY market | HIGH | IN_PROGRESS |
| MR-003 | Dynamic lapse assumption absent | CRITICAL | OPEN |
| MR-004 | P/Q measure not enforced at runtime | CRITICAL | IN_PROGRESS |
| MR-005 | Distributed executor pickling failure | HIGH | OPEN |
| MR-006 | Model validation readiness below threshold | CRITICAL | IN_PROGRESS |
| MR-007 | No assumption change control process | HIGH | IN_PROGRESS |
| MR-008 | HW1F calibration not yet executed | CRITICAL | OPEN |

**Open CRITICAL risks:** MR-003 (dynamic lapse), MR-008 (HW1F calibration uncalibrated). Both require Phase 4 remediation.

**Risk register maintenance:** Each automated cycle should call `RiskEntry.update_mitigation()` when a risk's status changes and append a `GOVERNANCE` audit entry documenting the update.

---

## 6. Audit Trail Entry Types

### MODEL_RUN
Recorded at the start and end of each automated 12-hour cycle. Fields:
- `run_id` — cycle identifier
- `scenario_count` — number of stochastic paths (0 until Phase 4)
- `duration_seconds`
- `outcome` — PASS / FAIL / PARTIAL
- `files_changed` — list of modified files
- `test_summary` — e.g. "161/161 passed"

### PARAM_CHANGE
Recorded when any model parameter is modified. Fields:
- `parameter_name` — dotted path (e.g. `hw1f.mean_reversion_speed`)
- `old_value` / `new_value`
- `rationale` — human-readable justification
- `standard_reference` — governing ASOP / TAS M section
- `change_record_id` — links to associated ChangeRecord

### VALIDATION
Recorded after any test suite execution. Fields:
- `test_suite` — path or name
- `tests_run` / `tests_passed` / `tests_failed`
- `outcome` — PASS / FAIL
- `failed_tests` — list of failing test names

### SIGN_OFF
Recorded when a ChangeRecord transitions state. Links to the record by `change_record_id`.

### CORRECTION
Used to correct a prior entry without deleting it. References the corrected entry by `corrects_entry_id`.

### GOVERNANCE
General governance events: risk register updates, policy changes, phase transitions.

---

## 7. Integration with Automated Cycles

Each 12-hour cycle should follow this governance integration pattern:

```python
from par_model_v2.governance import GovernanceStore, AuditEntry, seed_initial_risk_register
import json
from pathlib import Path

GOVERNANCE_FILE = Path(".claude-dev/GOVERNANCE_STORE.json")

# 1. Load or initialise store
if GOVERNANCE_FILE.exists():
    store = GovernanceStore.from_json(GOVERNANCE_FILE.read_text())
else:
    store = GovernanceStore()
    seed_initial_risk_register(store)

# 2. Log model run start
run_entry = AuditEntry.model_run(
    actor="Claude-Actuarial-Agent",
    phase="Phase 2: Industry Standards Alignment",
    run_id="cycle-11",
    scenario_count=0,
    duration_seconds=3600.0,
    outcome="PASS",
    files_changed=[
        "par_model_v2/governance/audit_trail.py",
        "par_model_v2/governance/__init__.py",
        "tests/test_governance.py",
        "docs/GOVERNANCE_FRAMEWORK.md",
    ],
    test_summary="161/161 passed",
)
store.audit_trail.append(run_entry)

# 3. Log validation
val_entry = AuditEntry.validation(
    actor="Claude-Actuarial-Agent",
    phase="Phase 2: Industry Standards Alignment",
    test_suite="tests/",
    tests_run=161,
    tests_passed=161,
    tests_failed=0,
    outcome="PASS",
)
store.audit_trail.append(val_entry)

# 4. Verify integrity
assert store.audit_trail.verify_all()

# 5. Persist
GOVERNANCE_FILE.write_text(store.to_json())
```

---

## 8. Limitations and Known Issues

1. **No database backend.** The JSON file approach will not scale beyond ~10,000 entries. For production use, migrate to a database or event log service.

2. **No cryptographic signing.** SHA-256 digests detect accidental corruption but not deliberate falsification by a party with file access. Production deployment should use HMAC or asymmetric signatures.

3. **No email/notification integration.** Sign-off notifications are not automated — actors must poll the register. Phase 5 should wire ChangeRecord transitions to email alerts.

4. **Process adoption gap.** The framework only works if every human and automated actor consistently uses `ChangeRecord` and `AuditEntry`. Ungoverned changes remain undetectable. Enforce via CI/CD gate in Phase 5.

5. **Concurrent write risk.** JSON file writes are not atomic. Concurrent automated cycles (unlikely given 12-hour cadence but possible) could corrupt the file. Use file locking or a database in production.

---

## 9. Compliance Traceability

| IA TAS M Section | Requirement | Implementation |
|-----------------|-------------|----------------|
| §3.3 | Model governance and ownership | `GovernanceStore.model_name`, `ChangeRecord.assumption_owner` |
| §3.5 | Assumption sign-off | `ChangeRecord.SignOffStatus`, `submit_for_peer_review()`, `approve()` |
| §3.7 | Change control log | `ChangeRecord` with `before_snapshot`, `after_snapshot`, `impact_assessment` |
| §3.6 | Testing and validation | `AuditEntry.validation()`, `AuditTrail.filter_by_type()` |
| §3.8 | Limitations disclosure | Section 8 of this document; `RiskEntry.description` in register |

| SOA ASOP Section | Requirement | Implementation |
|-----------------|-------------|----------------|
| ASOP 56 §3.5 | Model validation | `AuditEntry.validation()`, `AuditTrail.verify_all()` |
| ASOP 25 §3.3 | Assumption documentation | `ChangeRecord.standard_references` field |

| IFoA Practice Note | Requirement | Implementation |
|-------------------|-------------|----------------|
| §4 | Model risk register | `ModelRiskRegister`, `RiskEntry`, 8 seeded entries |
| §4 | Risk ratings | `RiskRating` enum: LOW / MEDIUM / HIGH / CRITICAL |
| §4 | Mitigation tracking | `MitigationStatus` enum; `update_mitigation()` method |

---

*This document is part of the automated Phase 2 governance deliverables. Supersedes: none (first governance framework document).*
