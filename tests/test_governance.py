"""
Tests for par_model_v2.governance — Audit Trail and Governance Framework
=========================================================================

Test coverage:
  - AuditEntry factory methods and digest integrity
  - AuditTrail append, filter, integrity verification
  - ChangeRecord creation and sign-off workflow state machine
  - ModelRiskRegister CRUD, filtering, and summary
  - GovernanceStore composite serialisation roundtrip
  - seed_initial_risk_register content validation

Standards tested:
  IA TAS M §3.3, §3.5, §3.7
  SOA ASOP 56 §3.5
  IFoA Modelling Practice Note §4
"""

import json
import pytest

from par_model_v2.governance import (
    AuditEntry, AuditTrail,
    ChangeRecord, SignOffStatus,
    ModelRiskRegister, RiskEntry, RiskRating, MitigationStatus,
    GovernanceStore, EntryType,
    seed_initial_risk_register,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

PHASE = "Phase 2: Industry Standards Alignment"
ACTOR = "test-agent"


@pytest.fixture
def trail() -> AuditTrail:
    return AuditTrail()


@pytest.fixture
def store() -> GovernanceStore:
    return GovernanceStore()


@pytest.fixture
def basic_model_run_entry() -> AuditEntry:
    return AuditEntry.model_run(
        actor=ACTOR,
        phase=PHASE,
        run_id="cycle-test-01",
        scenario_count=1000,
        duration_seconds=180.0,
        outcome="PASS",
        files_changed=["par_model_v2/governance/audit_trail.py"],
        test_summary="107/107 passed",
    )


@pytest.fixture
def basic_change_record() -> ChangeRecord:
    return ChangeRecord.create(
        title="Reduce discount rate from 3.5% to 3.0%",
        description="Align with CBIRC regulatory cap per Reserve Valuation Guidance 2023.",
        change_type="assumption_change",
        affected_components=["par_model_v2/projection/monthly_projection.py"],
        standard_references=["SOA ASOP 25 §3.3", "CBIRC Reserve Valuation Guidance 2023"],
        before_snapshot={"discount_rate": 0.035},
        after_snapshot={"discount_rate": 0.030},
        impact_assessment="Increases liability PV; reduces solvency margin. Directionally correct for regulatory compliance.",
        author=ACTOR,
        phase=PHASE,
        quantitative_impact="Estimated +2–5% liability PV; TVOG directionally increases.",
        assumption_owner="Head of Actuarial",
        peer_reviewer="Senior Actuary",
    )


# ---------------------------------------------------------------------------
# AuditEntry — factory methods
# ---------------------------------------------------------------------------

class TestAuditEntryFactories:

    def test_model_run_fields(self, basic_model_run_entry):
        e = basic_model_run_entry
        assert e.entry_type == EntryType.MODEL_RUN
        assert e.actor == ACTOR
        assert e.details["run_id"] == "cycle-test-01"
        assert e.details["scenario_count"] == 1000
        assert e.details["outcome"] == "PASS"

    def test_param_change_fields(self):
        e = AuditEntry.param_change(
            actor=ACTOR,
            phase=PHASE,
            parameter_name="discount_rate",
            old_value=0.035,
            new_value=0.030,
            rationale="CBIRC regulatory cap compliance",
            standard_reference="SOA ASOP 25 §3.3",
            change_record_id="abc123",
        )
        assert e.entry_type == EntryType.PARAM_CHANGE
        assert e.details["parameter_name"] == "discount_rate"
        assert e.details["old_value"] == 0.035
        assert e.details["new_value"] == 0.030
        assert e.details["change_record_id"] == "abc123"

    def test_validation_entry(self):
        e = AuditEntry.validation(
            actor=ACTOR,
            phase=PHASE,
            test_suite="tests/test_governance.py",
            tests_run=25,
            tests_passed=25,
            tests_failed=0,
            outcome="PASS",
        )
        assert e.entry_type == EntryType.VALIDATION
        assert e.details["tests_run"] == 25
        assert e.details["failed_tests"] == []

    def test_sign_off_entry(self):
        e = AuditEntry.sign_off(
            actor="Head of Actuarial",
            phase=PHASE,
            change_record_id="cr-001",
            new_status=SignOffStatus.APPROVED,
            comments="Reviewed and approved.",
        )
        assert e.entry_type == EntryType.SIGN_OFF
        assert e.details["new_status"] == SignOffStatus.APPROVED.value

    def test_correction_entry(self):
        original = AuditEntry.model_run(
            actor=ACTOR, phase=PHASE, run_id="bad-run",
            scenario_count=100, duration_seconds=60.0,
            outcome="PASS", files_changed=[],
        )
        correction = AuditEntry.correction(
            actor=ACTOR,
            phase=PHASE,
            corrects_entry_id=original.entry_id,
            reason="Duration was wrong — should be 120.0 seconds",
            corrected_details={"duration_seconds": 120.0},
        )
        assert correction.entry_type == EntryType.CORRECTION
        assert correction.corrects_entry_id == original.entry_id

    def test_governance_entry(self):
        e = AuditEntry.governance(
            actor=ACTOR, phase=PHASE,
            event="Risk register seeded",
            details={"entries_created": 8},
        )
        assert e.entry_type == EntryType.GOVERNANCE


# ---------------------------------------------------------------------------
# AuditEntry — digest integrity
# ---------------------------------------------------------------------------

class TestAuditEntryIntegrity:

    def test_digest_valid_on_creation(self, basic_model_run_entry):
        assert basic_model_run_entry.verify_digest() is True

    def test_digest_unique_per_entry(self):
        e1 = AuditEntry.model_run(
            actor=ACTOR, phase=PHASE, run_id="r1",
            scenario_count=1, duration_seconds=1.0, outcome="PASS", files_changed=[],
        )
        e2 = AuditEntry.model_run(
            actor=ACTOR, phase=PHASE, run_id="r2",
            scenario_count=1, duration_seconds=1.0, outcome="PASS", files_changed=[],
        )
        assert e1.digest != e2.digest

    def test_serialisation_preserves_digest(self, basic_model_run_entry):
        d = basic_model_run_entry.to_dict()
        restored = AuditEntry.from_dict(d)
        assert restored.verify_digest() is True
        assert restored.digest == basic_model_run_entry.digest

    def test_json_roundtrip(self, basic_model_run_entry):
        d = basic_model_run_entry.to_dict()
        restored = AuditEntry.from_dict(d)
        assert restored.entry_id == basic_model_run_entry.entry_id
        assert restored.entry_type == basic_model_run_entry.entry_type


# ---------------------------------------------------------------------------
# AuditTrail
# ---------------------------------------------------------------------------

class TestAuditTrail:

    def test_append_and_count(self, trail, basic_model_run_entry):
        trail.append(basic_model_run_entry)
        assert len(trail.all()) == 1

    def test_append_multiple(self, trail):
        for i in range(5):
            e = AuditEntry.model_run(
                actor=ACTOR, phase=PHASE, run_id=f"run-{i}",
                scenario_count=0, duration_seconds=1.0, outcome="PASS", files_changed=[],
            )
            trail.append(e)
        assert len(trail.all()) == 5

    def test_verify_all_passes(self, trail, basic_model_run_entry):
        trail.append(basic_model_run_entry)
        assert trail.verify_all() is True

    def test_filter_by_type(self, trail):
        run_e = AuditEntry.model_run(
            actor=ACTOR, phase=PHASE, run_id="r1",
            scenario_count=0, duration_seconds=1.0, outcome="PASS", files_changed=[],
        )
        val_e = AuditEntry.validation(
            actor=ACTOR, phase=PHASE,
            test_suite="tests/", tests_run=10, tests_passed=10,
            tests_failed=0, outcome="PASS",
        )
        trail.append(run_e)
        trail.append(val_e)
        runs = trail.filter_by_type(EntryType.MODEL_RUN)
        vals = trail.filter_by_type(EntryType.VALIDATION)
        assert len(runs) == 1
        assert len(vals) == 1

    def test_filter_by_phase(self, trail):
        e1 = AuditEntry.model_run(
            actor=ACTOR, phase="Phase 1: Model Review",
            run_id="r1", scenario_count=0, duration_seconds=1.0, outcome="PASS", files_changed=[],
        )
        e2 = AuditEntry.model_run(
            actor=ACTOR, phase="Phase 2: Industry Standards Alignment",
            run_id="r2", scenario_count=0, duration_seconds=1.0, outcome="PASS", files_changed=[],
        )
        trail.append(e1)
        trail.append(e2)
        assert len(trail.filter_by_phase("Phase 1: Model Review")) == 1

    def test_latest(self, trail):
        for i in range(15):
            e = AuditEntry.model_run(
                actor=ACTOR, phase=PHASE, run_id=f"r-{i}",
                scenario_count=0, duration_seconds=1.0, outcome="PASS", files_changed=[],
            )
            trail.append(e)
        assert len(trail.latest(10)) == 10

    def test_integrity_report_structure(self, trail, basic_model_run_entry):
        trail.append(basic_model_run_entry)
        report = trail.integrity_report()
        assert report["total"] == 1
        assert report["all_valid"] is True
        assert basic_model_run_entry.entry_id in report["per_entry"]

    def test_json_roundtrip(self, trail, basic_model_run_entry):
        trail.append(basic_model_run_entry)
        blob = trail.to_json()
        trail2 = AuditTrail.from_json(blob)
        assert len(trail2.all()) == 1
        assert trail2.verify_all() is True


# ---------------------------------------------------------------------------
# ChangeRecord — creation and sign-off workflow
# ---------------------------------------------------------------------------

class TestChangeRecord:

    def test_create_defaults(self, basic_change_record):
        cr = basic_change_record
        assert cr.status == SignOffStatus.DRAFT
        assert cr.sign_off_history == []
        assert cr.record_id is not None
        assert cr.change_type == "assumption_change"

    def test_invalid_change_type_raises(self):
        with pytest.raises(ValueError, match="change_type must be one of"):
            ChangeRecord.create(
                title="Test", description="Test", change_type="invalid_type",
                affected_components=[], standard_references=[],
                before_snapshot={}, after_snapshot={},
                impact_assessment="none", author=ACTOR, phase=PHASE,
            )

    def test_workflow_draft_to_peer_review(self, basic_change_record):
        basic_change_record.submit_for_peer_review(actor="senior-actuary", comments="Ready for review")
        assert basic_change_record.status == SignOffStatus.PEER_REVIEW
        assert len(basic_change_record.sign_off_history) == 1
        assert basic_change_record.sign_off_history[0]["actor"] == "senior-actuary"

    def test_workflow_peer_review_to_owner(self, basic_change_record):
        basic_change_record.submit_for_peer_review(actor="senior-actuary")
        basic_change_record.submit_to_owner(actor="senior-actuary", comments="Peer review complete")
        assert basic_change_record.status == SignOffStatus.OWNER_REVIEW
        assert len(basic_change_record.sign_off_history) == 2

    def test_workflow_full_approval(self, basic_change_record):
        basic_change_record.submit_for_peer_review(actor="senior-actuary")
        basic_change_record.submit_to_owner(actor="senior-actuary")
        basic_change_record.approve(actor="Head of Actuarial", comments="Approved for production.")
        assert basic_change_record.status == SignOffStatus.APPROVED
        assert len(basic_change_record.sign_off_history) == 3

    def test_workflow_rejection(self, basic_change_record):
        basic_change_record.submit_for_peer_review(actor="senior-actuary")
        basic_change_record.reject(actor="senior-actuary", comments="Impact assessment incomplete.")
        assert basic_change_record.status == SignOffStatus.REJECTED

    def test_cannot_skip_peer_review(self, basic_change_record):
        with pytest.raises(ValueError, match="Must be in PEER_REVIEW"):
            basic_change_record.submit_to_owner(actor="senior-actuary")

    def test_cannot_approve_from_peer_review(self, basic_change_record):
        basic_change_record.submit_for_peer_review(actor="senior-actuary")
        with pytest.raises(ValueError, match="Must be in OWNER_REVIEW"):
            basic_change_record.approve(actor="Head of Actuarial")

    def test_cannot_reject_approved(self, basic_change_record):
        basic_change_record.submit_for_peer_review(actor="senior-actuary")
        basic_change_record.submit_to_owner(actor="senior-actuary")
        basic_change_record.approve(actor="Head of Actuarial")
        with pytest.raises(ValueError, match="Cannot reject"):
            basic_change_record.reject(actor="senior-actuary")

    def test_serialisation_roundtrip(self, basic_change_record):
        basic_change_record.submit_for_peer_review(actor="senior-actuary")
        d = basic_change_record.to_dict()
        cr2 = ChangeRecord.from_dict(d)
        assert cr2.status == SignOffStatus.PEER_REVIEW
        assert cr2.record_id == basic_change_record.record_id
        assert cr2.before_snapshot == {"discount_rate": 0.035}
        assert len(cr2.sign_off_history) == 1

    def test_summary_row(self, basic_change_record):
        row = basic_change_record.summary_row()
        assert "record_id" in row
        assert "status" in row
        assert row["status"] == SignOffStatus.DRAFT.value


# ---------------------------------------------------------------------------
# ModelRiskRegister
# ---------------------------------------------------------------------------

class TestModelRiskRegister:

    def test_add_and_retrieve(self):
        rr = ModelRiskRegister()
        rr.add(
            risk_id="MR-TEST-01",
            title="Test risk",
            description="A test risk entry.",
            category="model_error",
            likelihood=RiskRating.MEDIUM,
            impact=RiskRating.HIGH,
            owner="Model Developer",
            mitigation="Write tests.",
            related_standard="SOA ASOP 56 §3.5",
        )
        entry = rr.get("MR-TEST-01")
        assert entry.title == "Test risk"
        assert entry.overall_rating == RiskRating.HIGH   # max(MEDIUM, HIGH)

    def test_invalid_category_raises(self):
        rr = ModelRiskRegister()
        with pytest.raises(ValueError, match="category must be one of"):
            rr.add(
                risk_id="MR-BAD", title="Bad", description="Bad category",
                category="not_a_category",
                likelihood=RiskRating.LOW, impact=RiskRating.LOW,
                owner="nobody", mitigation="none", related_standard="none",
            )

    def test_overall_rating_max_logic(self):
        rr = ModelRiskRegister()
        rr.add(
            risk_id="MR-CRIT", title="Critical impact", description="",
            category="assumption_error",
            likelihood=RiskRating.LOW, impact=RiskRating.CRITICAL,
            owner="Owner", mitigation="TBD", related_standard="ASOP 25",
        )
        assert rr.get("MR-CRIT").overall_rating == RiskRating.CRITICAL

    def test_filter_by_category(self):
        rr = ModelRiskRegister()
        rr.add("MR-A", "A", "", "model_error", RiskRating.LOW, RiskRating.LOW, "O", "M", "S")
        rr.add("MR-B", "B", "", "data_quality", RiskRating.LOW, RiskRating.LOW, "O", "M", "S")
        model_errors = rr.filter(category="model_error")
        assert len(model_errors) == 1
        assert model_errors[0].risk_id == "MR-A"

    def test_filter_by_rating(self):
        rr = ModelRiskRegister()
        rr.add("MR-H", "High", "", "model_error", RiskRating.HIGH, RiskRating.HIGH, "O", "M", "S")
        rr.add("MR-L", "Low",  "", "model_error", RiskRating.LOW,  RiskRating.LOW,  "O", "M", "S")
        highs = rr.filter(rating=RiskRating.HIGH)
        assert len(highs) == 1

    def test_filter_by_mitigation_status(self):
        rr = ModelRiskRegister()
        rr.add("MR-O", "Open", "", "model_error", RiskRating.LOW, RiskRating.LOW, "O", "M", "S")
        rr.add("MR-M", "Mitigated", "", "model_error", RiskRating.LOW, RiskRating.LOW, "O", "M", "S",
               mitigation_status=MitigationStatus.MITIGATED)
        open_risks = rr.filter(mitigation_status=MitigationStatus.OPEN)
        assert len(open_risks) == 1

    def test_get_unknown_raises(self):
        rr = ModelRiskRegister()
        with pytest.raises(KeyError):
            rr.get("MR-NONEXISTENT")

    def test_update_mitigation(self):
        rr = ModelRiskRegister()
        rr.add("MR-U", "Update test", "", "model_error",
               RiskRating.MEDIUM, RiskRating.MEDIUM, "O", "M", "S")
        entry = rr.get("MR-U")
        entry.update_mitigation(MitigationStatus.MITIGATED, notes="Fixed in Phase 3.")
        assert rr.get("MR-U").mitigation_status == MitigationStatus.MITIGATED

    def test_summary_structure(self):
        rr = ModelRiskRegister()
        rr.add("MR-S", "Summary test", "", "governance_risk",
               RiskRating.HIGH, RiskRating.HIGH, "O", "M", "S")
        summary = rr.summary()
        assert summary["total"] == 1
        assert "by_rating" in summary
        assert "by_status" in summary

    def test_serialisation_roundtrip(self):
        rr = ModelRiskRegister()
        rr.add("MR-SER", "Serialise test", "Full description.",
               "model_error", RiskRating.HIGH, RiskRating.CRITICAL, "Owner",
               "Mitigate it.", "SOA ASOP 56")
        data = rr.to_list()
        rr2 = ModelRiskRegister.from_list(data)
        assert len(rr2.all()) == 1
        entry = rr2.get("MR-SER")
        assert entry.overall_rating == RiskRating.CRITICAL
        assert entry.likelihood == RiskRating.HIGH


# ---------------------------------------------------------------------------
# GovernanceStore
# ---------------------------------------------------------------------------

class TestGovernanceStore:

    def test_initial_state(self, store):
        assert len(store.audit_trail.all()) == 0
        assert len(store.change_records) == 0
        assert len(store.risk_register.all()) == 0

    def test_add_change_record(self, store, basic_change_record):
        store.add_change_record(basic_change_record)
        assert len(store.change_records) == 1
        assert store.get_change_record(basic_change_record.record_id) is basic_change_record

    def test_open_change_records(self, store, basic_change_record):
        store.add_change_record(basic_change_record)
        assert len(store.open_change_records()) == 1
        basic_change_record.submit_for_peer_review(ACTOR)
        basic_change_record.submit_to_owner(ACTOR)
        basic_change_record.approve("Head of Actuarial")
        assert len(store.open_change_records()) == 0

    def test_governance_summary(self, store):
        summary = store.governance_summary()
        assert summary["model_name"] == "PAR Fund Stochastic ALM & TVOG"
        assert "audit_entries" in summary
        assert "risk_register" in summary

    def test_json_roundtrip_empty(self, store):
        blob = store.to_json()
        store2 = GovernanceStore.from_json(blob)
        assert store2.model_name == store.model_name
        assert len(store2.audit_trail.all()) == 0

    def test_json_roundtrip_with_data(self, store, basic_model_run_entry, basic_change_record):
        store.audit_trail.append(basic_model_run_entry)
        store.add_change_record(basic_change_record)
        store.risk_register.add(
            "MR-RT", "Roundtrip", "desc", "model_error",
            RiskRating.LOW, RiskRating.MEDIUM, "O", "M", "S"
        )
        blob = store.to_json()
        store2 = GovernanceStore.from_json(blob)
        assert len(store2.audit_trail.all()) == 1
        assert store2.audit_trail.verify_all() is True
        assert len(store2.change_records) == 1
        assert len(store2.risk_register.all()) == 1

    def test_audit_integrity_after_roundtrip(self, store, basic_model_run_entry):
        store.audit_trail.append(basic_model_run_entry)
        store2 = GovernanceStore.from_json(store.to_json())
        assert store2.audit_trail.verify_all() is True


# ---------------------------------------------------------------------------
# seed_initial_risk_register
# ---------------------------------------------------------------------------

class TestSeedInitialRiskRegister:

    def test_seeded_count(self, store):
        seed_initial_risk_register(store)
        assert len(store.risk_register.all()) == 8

    def test_critical_risks_present(self, store):
        seed_initial_risk_register(store)
        critical = store.risk_register.filter(rating=RiskRating.CRITICAL)
        assert len(critical) >= 3   # MR-001, MR-003, MR-006, MR-008 are CRITICAL

    def test_audit_entry_created_on_seed(self, store):
        seed_initial_risk_register(store)
        gov_entries = store.audit_trail.filter_by_type(EntryType.GOVERNANCE)
        assert len(gov_entries) == 1

    def test_mr001_discount_rate_risk(self, store):
        seed_initial_risk_register(store)
        entry = store.risk_register.get("MR-001")
        assert entry.likelihood == RiskRating.HIGH
        assert entry.impact == RiskRating.CRITICAL
        assert entry.mitigation_status == MitigationStatus.IN_PROGRESS

    def test_mr005_executor_risk(self, store):
        seed_initial_risk_register(store)
        entry = store.risk_register.get("MR-005")
        assert entry.category == "process_risk"
        assert entry.mitigation_status == MitigationStatus.OPEN

    def test_mr007_change_control_risk(self, store):
        """MR-007 should be IN_PROGRESS because this module partially remediates it."""
        seed_initial_risk_register(store)
        entry = store.risk_register.get("MR-007")
        assert entry.mitigation_status == MitigationStatus.IN_PROGRESS

    def test_all_risk_ids_unique(self, store):
        seed_initial_risk_register(store)
        ids = [e.risk_id for e in store.risk_register.all()]
        assert len(ids) == len(set(ids))

    def test_serialisation_after_seed(self, store):
        seed_initial_risk_register(store)
        blob = store.to_json()
        store2 = GovernanceStore.from_json(blob)
        assert len(store2.risk_register.all()) == 8
        assert store2.audit_trail.verify_all() is True
