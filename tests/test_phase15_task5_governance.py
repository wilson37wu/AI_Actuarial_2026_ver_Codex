"""Phase 15 Task 5 — multi-driver proxy governance refresh tests.

Validates the idempotent governance refresh applied by
scripts/build_phase15_task5_governance.py. Tests that exercise the *additive*
behaviour start from a reconstructed pre-refresh store (MR-011 + the Task 5
ChangeRecord + their audit entries stripped) so they are robust whether or not
the canonical committed store has already been refreshed.
"""
from __future__ import annotations

import os
import importlib.util

import pytest

from par_model_v2.governance.audit_trail import (
    GovernanceStore,
    ModelRiskRegister,
    AuditTrail,
    MitigationStatus,
    RiskRating,
    SignOffStatus,
)

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SCRIPT = os.path.join(_REPO, "scripts", "build_phase15_task5_governance.py")
_GOV = os.path.join(_REPO, ".claude-dev", "GOVERNANCE_STORE.json")
_CARD = os.path.join(_REPO, "docs", "MULTI_DRIVER_PROXY_LIMITATION_CARD.md")


def _load_module():
    spec = importlib.util.spec_from_file_location("phase15_task5_gov", _SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _fresh_store() -> GovernanceStore:
    return GovernanceStore.from_json(open(_GOV, encoding="utf-8").read())


def _pre_refresh_store(mod) -> GovernanceStore:
    """Reconstruct the store as it was BEFORE the Task 5 refresh."""
    store = _fresh_store()
    # strip MR-011
    store.risk_register = ModelRiskRegister(
        [e for e in store.risk_register.all() if e.risk_id != mod.MR_ID])
    # strip the Task 5 ChangeRecord
    store.change_records = [r for r in store.change_records if r.title != mod.CHANGE_TITLE]
    # strip the Task 5 governance audit entries
    store.audit_trail = AuditTrail(
        [e for e in store.audit_trail.all() if e.actor != "Phase15Task5GovernanceRefresh"])
    return store


@pytest.fixture(scope="module")
def mod():
    return _load_module()


def test_refresh_adds_mr011(mod):
    store = _pre_refresh_store(mod)
    assert "MR-011" not in [e.risk_id for e in store.risk_register.all()]
    mod.apply_phase15_task5_governance(store)
    mr = store.risk_register.get("MR-011")
    assert mr.overall_rating == RiskRating.HIGH
    assert mr.mitigation_status == MitigationStatus.IN_PROGRESS
    assert mr.category == "model_error"
    assert "educational" in mr.title.lower()


def test_refresh_adds_owner_review_change_record(mod):
    store = _pre_refresh_store(mod)
    mod.apply_phase15_task5_governance(store)
    rec = next(r for r in store.change_records if r.title == mod.CHANGE_TITLE)
    assert rec.status == SignOffStatus.OWNER_REVIEW
    assert rec.change_type == "governance_change"
    assert "docs/MULTI_DRIVER_PROXY_LIMITATION_CARD.md" in rec.affected_components


def test_refresh_is_idempotent(mod):
    store = _pre_refresh_store(mod)
    s1 = mod.apply_phase15_task5_governance(store)
    n_risks = len(store.risk_register.all())
    n_changes = len(store.change_records)
    n_audit = len(store.audit_trail.all())
    s2 = mod.apply_phase15_task5_governance(store)
    assert s1["added_risk_MR_011"] is True and s2["added_risk_MR_011"] is False
    assert s1["added_change_record"] is True and s2["added_change_record"] is False
    assert len(store.risk_register.all()) == n_risks
    assert len(store.change_records) == n_changes
    assert len(store.audit_trail.all()) == n_audit


def test_two_governance_audit_entries_added(mod):
    store = _pre_refresh_store(mod)
    before = len(store.audit_trail.all())
    mod.apply_phase15_task5_governance(store)
    assert len(store.audit_trail.all()) == before + 2


def test_audit_integrity_preserved(mod):
    store = _pre_refresh_store(mod)
    mod.apply_phase15_task5_governance(store)
    assert store.audit_trail.verify_all() is True
    rt = GovernanceStore.from_json(store.to_json())
    assert rt.audit_trail.verify_all() is True
    assert rt.risk_register.get("MR-011").overall_rating == RiskRating.HIGH


def test_summary_residual_documents_independent_review(mod):
    store = _pre_refresh_store(mod)
    summary = mod.apply_phase15_task5_governance(store)
    assert "APS X2" in summary["residual"]
    assert summary["change_record_status"] == "OWNER_REVIEW"
    assert summary["audit_integrity_ok"] is True


def test_canonical_store_already_refreshed_is_consistent():
    # the committed store should already contain MR-011 + the Task 5 record
    store = _fresh_store()
    mr = store.risk_register.get("MR-011")
    assert mr.overall_rating == RiskRating.HIGH
    assert any(r.title.startswith("Phase 15 Task 5") for r in store.change_records)
    assert store.audit_trail.verify_all() is True


def test_limitation_card_present_and_complete():
    assert os.path.exists(_CARD)
    text = open(_CARD, encoding="utf-8").read()
    for marker in [
        "EDUCATIONAL ONLY", "Model-use restrictions",
        "MR-011", "MR-010", "APS X2", "OWNER_REVIEW",
    ]:
        assert marker in text, marker
