"""Phase 17 Task 5 — three-driver (rate+equity+credit) proxy governance refresh tests.

Validates the idempotent governance refresh applied by
scripts/build_phase17_task5_governance.py, plus the three-driver extension of the
offline-viewer schema. Tests that exercise the *additive* governance behaviour
start from a reconstructed pre-refresh store (MR-012 + the Task 5 ChangeRecord +
their audit entries stripped) so they are robust whether or not the canonical
committed store has already been refreshed.
"""
from __future__ import annotations

import importlib.util
import os

import pytest

from par_model_v2.governance.audit_trail import (
    AuditTrail,
    GovernanceStore,
    MitigationStatus,
    ModelRiskRegister,
    RiskRating,
    SignOffStatus,
)

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SCRIPT = os.path.join(_REPO, "scripts", "build_phase17_task5_governance.py")
_BUNDLER = os.path.join(_REPO, "scripts", "build_offline_viewer.py")
_GOV = os.path.join(_REPO, ".claude-dev", "GOVERNANCE_STORE.json")
_CARD = os.path.join(_REPO, "docs", "MULTI_DRIVER_3D_PROXY_LIMITATION_CARD.md")
_ACTOR = "Phase17Task5GovernanceRefresh"


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _fresh_store() -> GovernanceStore:
    return GovernanceStore.from_json(open(_GOV, encoding="utf-8").read())


def _pre_refresh_store(mod) -> GovernanceStore:
    store = _fresh_store()
    store.risk_register = ModelRiskRegister(
        [e for e in store.risk_register.all() if e.risk_id != mod.MR_ID])
    store.change_records = [r for r in store.change_records if r.title != mod.CHANGE_TITLE]
    store.audit_trail = AuditTrail(
        [e for e in store.audit_trail.all() if e.actor != _ACTOR])
    return store


@pytest.fixture(scope="module")
def mod():
    return _load(_SCRIPT, "phase17_task5_gov")


def test_refresh_adds_mr012(mod):
    store = _pre_refresh_store(mod)
    assert mod.MR_ID == "MR-012"
    assert "MR-012" not in [e.risk_id for e in store.risk_register.all()]
    mod.apply_phase17_task5_governance(store)
    mr = store.risk_register.get("MR-012")
    assert mr.overall_rating == RiskRating.HIGH
    assert mr.mitigation_status == MitigationStatus.IN_PROGRESS
    assert mr.category == "model_error"
    assert "credit" in mr.title.lower()


def test_refresh_adds_owner_review_change_record(mod):
    store = _pre_refresh_store(mod)
    mod.apply_phase17_task5_governance(store)
    rec = next(r for r in store.change_records if r.title == mod.CHANGE_TITLE)
    assert rec.status == SignOffStatus.OWNER_REVIEW
    assert rec.change_type == "governance_change"
    assert "par_model_v2/stochastic/credit_spread.py" in rec.affected_components
    assert "docs/MULTI_DRIVER_3D_PROXY_LIMITATION_CARD.md" in rec.affected_components


def test_refresh_is_idempotent(mod):
    store = _pre_refresh_store(mod)
    s1 = mod.apply_phase17_task5_governance(store)
    n_risks = len(store.risk_register.all())
    n_changes = len(store.change_records)
    n_audit = len(store.audit_trail.all())
    s2 = mod.apply_phase17_task5_governance(store)
    assert s1["added_risk_MR_012"] is True and s2["added_risk_MR_012"] is False
    assert s1["added_change_record"] is True and s2["added_change_record"] is False
    assert len(store.risk_register.all()) == n_risks
    assert len(store.change_records) == n_changes
    assert len(store.audit_trail.all()) == n_audit


def test_two_governance_audit_entries_added(mod):
    store = _pre_refresh_store(mod)
    before = len(store.audit_trail.all())
    mod.apply_phase17_task5_governance(store)
    assert len(store.audit_trail.all()) == before + 2


def test_audit_integrity_preserved(mod):
    store = _pre_refresh_store(mod)
    mod.apply_phase17_task5_governance(store)
    assert store.audit_trail.verify_all() is True
    rt = GovernanceStore.from_json(store.to_json())
    assert rt.audit_trail.verify_all() is True
    assert rt.risk_register.get("MR-012").overall_rating == RiskRating.HIGH


def test_summary_documents_three_drivers_and_residual(mod):
    store = _pre_refresh_store(mod)
    summary = mod.apply_phase17_task5_governance(store)
    assert summary["drivers"] == ["short_rate", "equity", "credit_spread"]
    assert "APS X2" in summary["residual"]
    assert summary["change_record_status"] == "OWNER_REVIEW"
    assert summary["audit_integrity_ok"] is True


def test_canonical_store_already_refreshed_is_consistent():
    store = _fresh_store()
    mr = store.risk_register.get("MR-012")
    assert mr.overall_rating == RiskRating.HIGH
    assert any(r.title.startswith("Phase 17 Task 5") for r in store.change_records)
    assert store.audit_trail.verify_all() is True


def test_limitation_card_present_and_complete():
    assert os.path.exists(_CARD)
    text = open(_CARD, encoding="utf-8").read()
    for marker in [
        "EDUCATIONAL ONLY", "Model-use restrictions",
        "MR-012", "MR-010", "MR-011", "APS X2", "OWNER_REVIEW",
        "credit_spread", "CIR++", "three", "38.7",
    ]:
        assert marker in text, marker


def test_viewer_schema_carries_three_drivers():
    """The bundler must surface the credit driver in the capital schema when the
    Phase 17 three-driver reports are present."""
    bundler = _load(_BUNDLER, "offline_viewer_bundler")
    data = bundler.build_viewer_data()
    cap = data.get("capital", {})
    assert cap.get("credit_scr") is not None, "credit_scr must be populated from Phase 17 report"
    assert "credit_spread" in (cap.get("drivers") or [])
    assert cap.get("esg_understatement_pct") is not None
    # proxy view must still have rows (Phase 17 basis_rows normalised to degree_rows)
    assert data.get("proxy", {}).get("degree_rows"), "proxy degree_rows must be non-empty"
