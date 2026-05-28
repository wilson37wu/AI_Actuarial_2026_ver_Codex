"""
Tests for AuditTrail wiring into the projection run loop.

Phase 3, Task 5 — VR-G01: Wire AuditTrail into projection run loop.

Covers:
  - run_full_projection without governance_store (backward-compat / legacy callers)
  - run_full_projection with governance_store emits MODEL_RUN + VALIDATION entries
  - run_id is set on FullProjectionResult when store provided
  - audit_entry_id cross-references the MODEL_RUN AuditEntry
  - VALIDATION entry passes for a well-formed projection
  - VALIDATION entry FAIL branch when pv_net_liability would be forced negative
  - AuditTrail digest integrity intact after wiring
  - Custom actor / phase / run_label propagate to audit entries
  - Backward compat: FullProjectionResult.run_id is None when no store given
"""

from __future__ import annotations

import pytest

from par_model_v2.governance.audit_trail import (
    AuditEntry,
    EntryType,
    GovernanceStore,
)
from par_model_v2.projection.monthly_projection import (
    AssetPosition,
    FullProjectionResult,
    ParEndowmentProduct,
    run_full_projection,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _prod(term: int = 5) -> ParEndowmentProduct:
    """Small 5-year policy — fast to project."""
    return ParEndowmentProduct(
        term_years=term,
        issue_age=35,
        gender="M",
        sum_assured=100_000.0,
        annual_premium=5_000.0,
        rb_rate_annual=0.03,
        terminal_bonus_pct=0.5,
        surrender_value_pct=0.9,
        initial_rb_accum=0.0,
    )


def _positions(scale: float = 0.01) -> list:
    return [
        AssetPosition("Govt",     900_000 * scale, 880_000 * scale, 8.5, 0.032, 0.0,  8.5, ""),
        AssetPosition("Credit_A", 575_000 * scale, 570_000 * scale, 6.2, 0.038, 0.0,  6.2, "A"),
        AssetPosition("Equity",   700_000 * scale, 700_000 * scale, 0.0, 0.025, 0.06, 0.0, ""),
        AssetPosition("Cash",     125_000 * scale, 125_000 * scale, 0.0, 0.020, 0.0,  0.0, ""),
    ]


def _run(store=None, **kwargs) -> FullProjectionResult:
    """Helper: run a 5-year projection, optionally with a governance_store."""
    return run_full_projection(
        product=_prod(),
        fund_positions=_positions(),
        governance_store=store,
        **kwargs,
    )


# ---------------------------------------------------------------------------
# 1. Backward-compatibility: no governance_store
# ---------------------------------------------------------------------------

class TestBackwardCompatibility:
    """Callers that do NOT pass governance_store must be unaffected."""

    def test_returns_full_projection_result(self):
        result = _run()
        assert isinstance(result, FullProjectionResult)

    def test_run_id_is_none_without_store(self):
        result = _run()
        assert result.run_id is None

    def test_audit_entry_id_is_none_without_store(self):
        result = _run()
        assert result.audit_entry_id is None

    def test_summary_fields_present(self):
        result = _run()
        summ = result.summary()
        expected_keys = {
            "term_years", "pv_premiums", "pv_guaranteed_benefits",
            "pv_non_guaranteed_benefits", "pv_expenses", "pv_net_liability",
            "asset_share_at_maturity",
        }
        assert expected_keys <= set(summ.keys())


# ---------------------------------------------------------------------------
# 2. Governance wiring: audit trail entries emitted
# ---------------------------------------------------------------------------

class TestAuditTrailEmission:
    """run_full_projection emits exactly MODEL_RUN + VALIDATION entries."""

    def setup_method(self):
        self.store = GovernanceStore()
        self.result = _run(store=self.store)

    def test_exactly_two_entries_emitted(self):
        assert len(self.store.audit_trail.all()) == 2

    def test_model_run_entry_emitted(self):
        model_runs = self.store.audit_trail.filter_by_type(EntryType.MODEL_RUN)
        assert len(model_runs) == 1

    def test_validation_entry_emitted(self):
        validations = self.store.audit_trail.filter_by_type(EntryType.VALIDATION)
        assert len(validations) == 1

    def test_model_run_outcome_pass(self):
        entry = self.store.audit_trail.filter_by_type(EntryType.MODEL_RUN)[0]
        assert entry.details["outcome"] == "PASS"

    def test_validation_outcome_pass(self):
        entry = self.store.audit_trail.filter_by_type(EntryType.VALIDATION)[0]
        assert entry.details["outcome"] == "PASS"
        assert entry.details["tests_run"] == 2
        assert entry.details["tests_passed"] == 2
        assert entry.details["tests_failed"] == 0

    def test_digest_integrity_after_wiring(self):
        assert self.store.audit_trail.verify_all()


# ---------------------------------------------------------------------------
# 3. run_id / audit_entry_id cross-references
# ---------------------------------------------------------------------------

class TestIdentifierPropagation:
    """FullProjectionResult.run_id and audit_entry_id must match the store."""

    def setup_method(self):
        self.store = GovernanceStore()
        self.result = _run(store=self.store, run_label="cycle-18")

    def test_run_id_is_set_on_result(self):
        assert self.result.run_id is not None
        assert self.result.run_id.startswith("cycle-18-")

    def test_audit_entry_id_is_set(self):
        assert self.result.audit_entry_id is not None

    def test_audit_entry_id_matches_model_run_entry(self):
        model_run = self.store.audit_trail.filter_by_type(EntryType.MODEL_RUN)[0]
        assert self.result.audit_entry_id == model_run.entry_id

    def test_run_id_in_model_run_details(self):
        model_run = self.store.audit_trail.filter_by_type(EntryType.MODEL_RUN)[0]
        assert model_run.details["run_id"] == self.result.run_id

    def test_duration_recorded_and_positive(self):
        model_run = self.store.audit_trail.filter_by_type(EntryType.MODEL_RUN)[0]
        assert model_run.details["duration_seconds"] >= 0.0


# ---------------------------------------------------------------------------
# 4. Custom actor / phase labels
# ---------------------------------------------------------------------------

class TestCustomLabels:
    """actor, phase, and run_label must propagate to audit entries."""

    def setup_method(self):
        self.store = GovernanceStore()
        self.result = run_full_projection(
            product=_prod(),
            fund_positions=_positions(),
            governance_store=self.store,
            actor="test-harness",
            phase="Phase 3: Model Validation & Testing",
            run_label="unit-test",
        )

    def test_actor_in_model_run_entry(self):
        model_run = self.store.audit_trail.filter_by_type(EntryType.MODEL_RUN)[0]
        assert model_run.actor == "test-harness"

    def test_actor_in_validation_entry(self):
        val = self.store.audit_trail.filter_by_type(EntryType.VALIDATION)[0]
        assert val.actor == "test-harness"

    def test_phase_in_model_run_entry(self):
        model_run = self.store.audit_trail.filter_by_type(EntryType.MODEL_RUN)[0]
        assert model_run.phase == "Phase 3: Model Validation & Testing"

    def test_run_label_prefix_in_run_id(self):
        assert self.result.run_id.startswith("unit-test-")


# ---------------------------------------------------------------------------
# 5. Validation FAIL branch — force negative pv_net_liability via monkeypatching
# ---------------------------------------------------------------------------

class TestValidationFailBranch:
    """If pv_net_liability is negative the VALIDATION entry must record FAIL."""

    def test_validation_fail_on_negative_pv_net_liability(self, monkeypatch):
        """
        Monkeypatch LiabilityProjectionResult.pv_net_liability to be negative
        after projection so the internal consistency check fires.
        """
        from par_model_v2.projection import monthly_projection as mp

        original_project = mp.project_liability_cashflows

        def patched_project(*args, **kwargs):
            result = original_project(*args, **kwargs)
            # Force pv_net_liability negative to trigger FAIL validation
            object.__setattr__(result, "pv_net_liability", -1.0) if hasattr(result, "__dataclass_fields__") else None
            # LiabilityProjectionResult is a dataclass (not frozen) — can assign
            result.pv_net_liability = -1.0
            return result

        monkeypatch.setattr(mp, "project_liability_cashflows", patched_project)

        store = GovernanceStore()
        _run(store=store)

        val = store.audit_trail.filter_by_type(EntryType.VALIDATION)[0]
        assert val.details["outcome"] == "FAIL"
        assert val.details["tests_failed"] == 1
        assert val.details["tests_passed"] == 1
        assert len(val.details["failed_tests"]) == 1
        assert "pv_net_liability" in val.details["failed_tests"][0]


# ---------------------------------------------------------------------------
# 6. Multiple runs accumulate entries in the same store
# ---------------------------------------------------------------------------

class TestAccumulation:
    """Multiple calls with the same store accumulate all entries."""

    def test_two_runs_yield_four_entries(self):
        store = GovernanceStore()
        _run(store=store, run_label="run-A")
        _run(store=store, run_label="run-B")
        assert len(store.audit_trail.all()) == 4

    def test_two_runs_have_distinct_run_ids(self):
        store = GovernanceStore()
        r1 = _run(store=store, run_label="run-A")
        r2 = _run(store=store, run_label="run-B")
        assert r1.run_id != r2.run_id

    def test_digest_integrity_after_two_runs(self):
        store = GovernanceStore()
        _run(store=store)
        _run(store=store)
        assert store.audit_trail.verify_all()


# ---------------------------------------------------------------------------
# 7. Scenario count hard-coded to 1 for deterministic runs
# ---------------------------------------------------------------------------

class TestScenarioCount:
    def test_scenario_count_is_one(self):
        store = GovernanceStore()
        _run(store=store)
        model_run = store.audit_trail.filter_by_type(EntryType.MODEL_RUN)[0]
        assert model_run.details["scenario_count"] == 1


# ---------------------------------------------------------------------------
# 8. GovernanceStore serialisation round-trip after wiring
# ---------------------------------------------------------------------------

class TestSerialisation:
    """Audit entries survive a to_json / from_json round-trip."""

    def test_round_trip_preserves_entries(self):
        store = GovernanceStore()
        result = _run(store=store, run_label="rt-test")

        blob   = store.to_json()
        store2 = GovernanceStore.from_json(blob)

        assert len(store2.audit_trail.all()) == 2
        assert store2.audit_trail.verify_all()

        model_run = store2.audit_trail.filter_by_type(EntryType.MODEL_RUN)[0]
        assert model_run.entry_id == result.audit_entry_id
        assert model_run.details["run_id"] == result.run_id
