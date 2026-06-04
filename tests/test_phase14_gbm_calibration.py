"""
Tests for Phase 14 Task 2 — GBM equity calibration to educational-proxy CNY/HK data (G-03).

Covers:
  * deterministic educational-proxy synthesis (reproducibility, moment recovery);
  * EquityDataLoader validation guards;
  * GBMCalibrator recovery of sigma_S / ERP / rho inside G-03 plausibility bands;
  * the G-03 gate evaluation (all six criteria) — PASS and forced-FAIL;
  * the full run_phase14_gbm_calibration pipeline: ChangeRecord APPROVED, one
    PARAM_CHANGE audit entry per market, MR-002 -> MITIGATED, governance
    round-trip integrity, and report rendering.
"""

from __future__ import annotations

import json
import os
import tempfile

import numpy as np
import pytest

from par_model_v2.calibration.calibration_framework import GBMCalibrator
from par_model_v2.calibration.equity_market_data_source import (
    MIN_DAILY_OBS,
    RHO_MAX,
    RHO_MIN,
    SIGMA_S_MAX,
    SIGMA_S_MIN,
    EquityDataLoader,
    FileBasedEquitySource,
    build_equity_loader,
    check_equity_calibration,
    default_fixture_dir,
    evaluate_g03_gate,
    synthesize_equity_history,
)
from par_model_v2.calibration.phase14_gbm_calibration import (
    MARKETS,
    MR002_ID,
    Phase14GBMReport,
    build_g03_change_record,
    run_phase14_gbm_calibration,
)
from par_model_v2.governance.audit_trail import (
    GovernanceStore,
    MitigationStatus,
    SignOffStatus,
    seed_initial_risk_register,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def cny_spec():
    path = default_fixture_dir() / "cny_equity_history_20260101.json"
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture
def seeded_store():
    """A fresh GovernanceStore seeded with the canonical risk register (incl. MR-002)."""
    store = GovernanceStore()
    seed_initial_risk_register(store)
    return store


# ---------------------------------------------------------------------------
# Synthesis
# ---------------------------------------------------------------------------

def test_synthesis_is_deterministic(cny_spec):
    eq1, rf1, dv1, d1 = synthesize_equity_history(cny_spec)
    eq2, rf2, dv2, d2 = synthesize_equity_history(cny_spec)
    assert np.allclose(eq1.values, eq2.values)
    assert np.allclose(rf1.values, rf2.values)
    assert d1 == d2


def test_synthesis_shapes_and_minimum_history(cny_spec):
    eq, rf, dv, _ = synthesize_equity_history(cny_spec)
    assert len(eq) == len(rf)
    assert len(eq) >= MIN_DAILY_OBS
    assert len(eq) >= 1260  # >= 5y daily, no calibrator warning
    assert len(dv) >= 36


def test_synthesis_recovers_annual_returns(cny_spec):
    """Compounded calendar-year total return matches the documented value."""
    eq, _, _, _ = synthesize_equity_history(cny_spec)
    annual = {int(y): float(r) for y, r in cny_spec["annual_equity_returns"].items()}
    comp = np.expm1(eq.groupby(eq.index.year).sum())
    for y, target in annual.items():
        assert comp.loc[y] == pytest.approx(target, abs=1e-6)


# ---------------------------------------------------------------------------
# Loader validation
# ---------------------------------------------------------------------------

def test_loader_returns_inputs_and_lineage():
    loader = build_equity_loader("CNY")
    inputs, lineage = loader.load()
    assert lineage.market == "CNY"
    assert lineage.sha256_checksum and len(lineage.sha256_checksum) == 64
    assert len(inputs.equity_returns) == len(inputs.rf_returns)


def test_loader_rejects_too_little_history(tmp_path, cny_spec):
    spec = json.loads(json.dumps(cny_spec))
    spec["daily_synthesis"]["start_date"] = "2025-06-01"  # ~7 months only
    f = tmp_path / "tiny_equity_history_20260101.json"
    f.write_text(json.dumps(spec), encoding="utf-8")
    loader = EquityDataLoader(FileBasedEquitySource(f))
    with pytest.raises(ValueError, match="daily equity observations"):
        loader.load()


def test_missing_fixture_raises():
    with pytest.raises(FileNotFoundError):
        FileBasedEquitySource(default_fixture_dir() / "does_not_exist.json")


# ---------------------------------------------------------------------------
# Calibration recovery
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("market", list(MARKETS))
def test_calibration_lands_in_bands(market):
    loader = build_equity_loader(market)
    inputs, _ = loader.load()
    res = GBMCalibrator(inputs).calibrate()
    assert not res.is_placeholder
    assert SIGMA_S_MIN <= res.sigma_S <= SIGMA_S_MAX
    assert RHO_MIN <= res.rho <= RHO_MAX
    assert 0.0 < res.erp <= 0.05 + 1e-9
    assert res.dividend_yield > 0.0


def test_rho_is_negative_as_documented():
    """Rate-equity correlation recovers a negative figure for both markets."""
    for market in MARKETS:
        inputs, _ = build_equity_loader(market).load()
        res = GBMCalibrator(inputs).calibrate()
        assert res.rho < 0.0


# ---------------------------------------------------------------------------
# Gate evaluation
# ---------------------------------------------------------------------------

def test_g03_gate_passes_when_all_criteria_met():
    checks = []
    for market in MARKETS:
        inputs, _ = build_equity_loader(market).load()
        res = GBMCalibrator(inputs).calibrate()
        checks.append(
            check_equity_calibration(market, len(inputs.equity_returns), res, has_param_change_audit=True)
        )
    gate = evaluate_g03_gate(checks)
    assert gate.gate_id == "G-03"
    assert gate.status == "PASS"
    assert all(c.all_pass() for c in checks)


def test_g03_gate_fails_without_param_change_audit():
    inputs, _ = build_equity_loader("CNY").load()
    res = GBMCalibrator(inputs).calibrate()
    chk = check_equity_calibration("CNY", len(inputs.equity_returns), res, has_param_change_audit=False)
    gate = evaluate_g03_gate([chk])
    assert gate.status == "FAIL"
    assert "c6_param_change_audit" in gate.evidence


def test_g03_gate_fails_on_short_history():
    inputs, _ = build_equity_loader("CNY").load()
    res = GBMCalibrator(inputs).calibrate()
    chk = check_equity_calibration("CNY", 500, res, has_param_change_audit=True)  # < 750
    assert not chk.criteria["c1_min_daily_obs"]
    assert evaluate_g03_gate([chk]).status == "FAIL"


# ---------------------------------------------------------------------------
# ChangeRecord
# ---------------------------------------------------------------------------

def test_change_record_has_before_after_and_standards():
    inputs, _ = build_equity_loader("CNY").load()
    res = GBMCalibrator(inputs).calibrate()
    chk = check_equity_calibration("CNY", len(inputs.equity_returns), res, has_param_change_audit=True)
    from par_model_v2.calibration.phase14_gbm_calibration import MarketEquityCalibrationSummary
    summ = MarketEquityCalibrationSummary(
        market="CNY", calibration_date="2026-01-01", sigma_S=res.sigma_S, erp=res.erp,
        dividend_yield=res.dividend_yield, rho=res.rho, equity_vol_hist=res.equity_vol_hist,
        equity_vol_implied=res.equity_vol_implied, n_daily_obs=len(inputs.equity_returns),
        is_placeholder=res.is_placeholder, notes=res.notes,
        lineage=build_equity_loader("CNY")._source.build_lineage_record(), check=chk,
    )
    cr = build_g03_change_record([summ])
    assert cr.change_type == "assumption_change"
    assert cr.before_snapshot["erp"] == 0.045
    assert "CNY_sigma_S" in cr.after_snapshot
    refs = " ".join(cr.standard_references)
    assert "ASOP 56" in refs and "TAS M" in refs


# ---------------------------------------------------------------------------
# Full pipeline
# ---------------------------------------------------------------------------

def test_pipeline_passes_and_mitigates_mr002(seeded_store):
    rpt = run_phase14_gbm_calibration(governance_store=seeded_store)
    assert isinstance(rpt, Phase14GBMReport)
    assert rpt.gate_g03.status == "PASS"
    assert rpt.change_record_status == SignOffStatus.APPROVED.value
    assert rpt.mr002_status == MitigationStatus.MITIGATED.value
    assert len(rpt.audit_entry_ids) == len(MARKETS)
    # MR-002 actually moved in the store
    assert seeded_store.risk_register.get(MR002_ID).mitigation_status == MitigationStatus.MITIGATED


def test_pipeline_records_param_change_audit_per_market(seeded_store):
    run_phase14_gbm_calibration(governance_store=seeded_store)
    pc = [e for e in seeded_store.audit_trail.all() if e.entry_type.value == "PARAM_CHANGE"]
    markets = {e.details["parameter_name"] for e in pc}
    assert markets == {"GBM_equity_params[{}]".format(m) for m in MARKETS}
    assert seeded_store.audit_trail.verify_all()


def test_pipeline_persists_and_round_trips(seeded_store):
    with tempfile.TemporaryDirectory() as tmp:
        store_path = os.path.join(tmp, "GOV.json")
        seeded_store_json = seeded_store.to_json()
        with open(store_path, "w", encoding="utf-8") as fh:
            fh.write(seeded_store_json)
        rpt = run_phase14_gbm_calibration(
            store_path=store_path, write_report=True, docs_dir=tmp, persist_governance=True
        )
        assert rpt.gate_g03.status == "PASS"
        reloaded = GovernanceStore.from_json(open(store_path, encoding="utf-8").read())
        assert reloaded.risk_register.get(MR002_ID).mitigation_status == MitigationStatus.MITIGATED
        assert reloaded.audit_trail.verify_all()
        assert os.path.exists(os.path.join(tmp, "PHASE14_GBM_CALIBRATION_REPORT.md"))
        assert os.path.exists(os.path.join(tmp, "PHASE14_GBM_CALIBRATION_REPORT.json"))


def test_report_markdown_mentions_gate_and_restriction(seeded_store):
    rpt = run_phase14_gbm_calibration(governance_store=seeded_store)
    md = rpt.markdown
    assert "G-03" in md
    assert "PRODUCTION USE RESTRICTION" in md
    assert "MR-002" in md


# ---------------------------------------------------------------------------
# Governance store regression: the canonical on-disk store must still load
# ---------------------------------------------------------------------------

def test_canonical_governance_store_round_trips():
    """The committed .claude-dev/GOVERNANCE_STORE.json must load and round-trip.

    Guards against the prior-cycle defect where SignOffStatus 'IMPLEMENTED' and
    RiskRating 'VERY_LOW' could not be parsed.
    """
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    store_path = os.path.join(repo_root, ".claude-dev", "GOVERNANCE_STORE.json")
    if not os.path.exists(store_path):
        pytest.skip("governance store not present in this checkout")
    store = GovernanceStore.from_json(open(store_path, encoding="utf-8").read())
    assert store.audit_trail.verify_all()
    GovernanceStore.from_json(store.to_json())  # round-trip
    assert SignOffStatus("IMPLEMENTED").value == "IMPLEMENTED"
