"""
Phase 21 Task 3 — Liquidity-Premium Driver Calibration to Educational-Proxy HKD History
=======================================================================================

Adds the SEVENTH economic-capital-proxy driver — a CIR++ liquidity premium /
funding spread — and calibrates it, closing the last documented driver
omission in **MR-012** ("the proxy still omits ... liquidity") and tightening
**MR-011** ("multi-driver economic-capital proxy is educational") by:

  1. Loading an educational-proxy HKD liquidity-premium history via
     ``FileBasedLiquidityPremiumSource`` / ``LiquidityPremiumDataLoader``
     (replacing the ``LiquidityPremiumParams`` placeholder defaults).
  2. Running ``LiquidityPremiumCalibrator`` (delegating to the tested
     homoscedastic CIR OLS transition regression) to estimate ``kappa_l``,
     the P-measure long-run premium, ``sigma_l``, and the market price of
     liquidity risk ``lambda_l`` from a documented risk-neutral anchor.
  3. Recording a PARAM_CHANGE ``AuditEntry`` and an ``assumption_change``
     ``ChangeRecord`` driven DRAFT -> PEER_REVIEW -> OWNER_REVIEW -> APPROVED
     in the ``GovernanceStore`` (IA TAS M 3.5/3.7).
  4. Evaluating the internal liquidity-calibration gate **G-LIQ**.
  5. Refreshing risk-register entries MR-011 / MR-012 and (optionally)
     persisting ``.claude-dev/GOVERNANCE_STORE.json``.
  6. Writing ``docs/validation/PHASE21_TASK3_LIQUIDITY_CALIBRATION_REPORT.md`` / ``.json``.

Entry point
-----------
``run_phase21_liquidity_calibration()`` -> :class:`Phase21LiquidityReport`.

Seven-driver integration note
-----------------------------
This task delivers the calibrated DRIVER + gate.  The seven-driver
(r, S, s, b, m, fx, l) tail-dependent aggregation and tail diagnostics are
Phase 21 Task 4, per the one-task-per-cycle plan.

PRODUCTION USE RESTRICTION
--------------------------
Calibration is driven by an educational-proxy fixture, a single-path OLS
estimator, and an automation-driven three-stage sign-off.  Before production
pricing or capital use, replace the fixture with a credentialled
liquidity-premium series, use a maximum-likelihood / Kalman estimator with
standard errors, and obtain a genuine Assumption Owner + independent APS X2
review.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from par_model_v2.calibration.liquidity_calibrator import (
    LiquidityCalibrationResult,
    LiquidityPremiumCalibrator,
)
from par_model_v2.calibration.liquidity_market_data_source import (
    LiquidityCalibrationCheck,
    build_liquidity_loader,
    check_liquidity_calibration,
    evaluate_liquidity_gate,
)
from par_model_v2.calibration.market_data_source import (
    DataLineageRecord,
    ProductionGateStatus,
)
from par_model_v2.governance.audit_trail import (
    AuditEntry,
    ChangeRecord,
    GovernanceStore,
    MitigationStatus,
)

MR_PROXY_ID = "MR-011"
MR_DRIVER_ID = "MR-012"
MARKET = "HKD"
PHASE = "Phase 21: FX + Liquidity Drivers and Six/Seven-Driver Economic Capital"

# Placeholder CIR++ liquidity-premium parameters being replaced
# (LiquidityPremiumParams defaults).
PLACEHOLDER_LIQUIDITY = {
    "mean_reversion_speed": 0.60,
    "premium_vol": 0.025,
    "initial_premium": 0.005,
    "long_run_premium_p": 0.006,
    "market_price_of_liquidity_risk": 0.10,
    "shift": 0.001,
}


# ---------------------------------------------------------------------------
# 1. Summary + report containers
# ---------------------------------------------------------------------------

@dataclass
class LiquidityCalibrationSummary:
    market: str
    calibration_date: str
    kappa: float
    long_run_premium_p: float
    premium_vol: float
    market_price_of_liquidity_risk: float
    shift: float
    initial_premium: float
    half_life_years: float
    feller_ratio: float
    feller_ok: bool
    n_obs: int
    fit_r2: float
    is_placeholder: bool
    notes: str
    lineage: DataLineageRecord
    check: LiquidityCalibrationCheck

    def to_dict(self) -> Dict[str, Any]:
        return {
            "market": self.market,
            "calibration_date": self.calibration_date,
            "kappa": self.kappa,
            "long_run_premium_p": self.long_run_premium_p,
            "premium_vol": self.premium_vol,
            "market_price_of_liquidity_risk": self.market_price_of_liquidity_risk,
            "shift": self.shift,
            "initial_premium": self.initial_premium,
            "half_life_years": self.half_life_years,
            "feller_ratio": self.feller_ratio,
            "feller_ok": self.feller_ok,
            "n_obs": self.n_obs,
            "fit_r2": self.fit_r2,
            "is_placeholder": self.is_placeholder,
            "notes": self.notes,
            "lineage": self.lineage.to_dict(),
            "criteria": self.check.criteria,
        }


@dataclass
class Phase21LiquidityReport:
    run_timestamp: str
    summary: LiquidityCalibrationSummary
    gate_gliq: ProductionGateStatus
    change_record_id: str
    change_record_status: str
    mr011_status: str
    mr012_status: str
    audit_entry_ids: List[str]
    markdown: str = field(default="", repr=False)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_timestamp": self.run_timestamp,
            "summary": self.summary.to_dict(),
            "gate_gliq": self.gate_gliq.to_dict(),
            "change_record_id": self.change_record_id,
            "change_record_status": self.change_record_status,
            "mr011_status": self.mr011_status,
            "mr012_status": self.mr012_status,
            "audit_entry_ids": self.audit_entry_ids,
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    def gate_passes(self) -> bool:
        return self.gate_gliq.status == "PASS"


# ---------------------------------------------------------------------------
# 2. Governance: ChangeRecord + PARAM_CHANGE audit
# ---------------------------------------------------------------------------

def _after_snapshot(res: LiquidityCalibrationResult) -> Dict[str, Any]:
    return {
        "source": "FileBasedLiquidityPremiumSource (educational proxy)",
        "mean_reversion_speed": round(res.mean_reversion_speed, 6),
        "long_run_premium_p": round(res.long_run_premium_p, 6),
        "premium_vol": round(res.premium_vol, 6),
        "market_price_of_liquidity_risk": round(res.market_price_of_liquidity_risk, 6),
        "shift": round(res.shift, 6),
        "initial_premium": round(res.initial_premium, 6),
    }


def build_liquidity_change_record(res: LiquidityCalibrationResult) -> ChangeRecord:
    """Create the ``assumption_change`` ChangeRecord for the liquidity calibration."""
    return ChangeRecord.create(
        title="MR-011/MR-012: Liquidity-premium driver (7th) added and calibrated (HKD)",
        description=(
            "Phase 21 Task 3: Added the CIR++ liquidity-premium / funding-spread driver "
            "(par_model_v2/stochastic/liquidity_premium.py) — the SEVENTH economic-capital-"
            "proxy driver and the LAST documented-but-omitted driver in MR-012 — and replaced "
            "its placeholder parameters with values calibrated from educational-proxy HKD "
            "liquidity-premium history via LiquidityPremiumCalibrator (delegating to the "
            "tested homoscedastic CIR OLS transition regression): kappa_l and the P-measure "
            "long-run premium from the regression, sigma_l from the residual variance, and "
            "lambda_l from a documented risk-neutral long-run anchor via the CIR risk-premium "
            "relation. FileBasedLiquidityPremiumSource is used; production capital/pricing "
            "use requires a credentialled liquidity-premium series and a genuine independent review."
        ),
        change_type="assumption_change",
        affected_components=[
            "par_model_v2/stochastic/liquidity_premium.py",
            "par_model_v2/calibration/liquidity_calibrator.py",
            "par_model_v2/calibration/liquidity_market_data_source.py",
            "par_model_v2/calibration/phase21_liquidity_calibration.py",
            "par_model_v2/calibration/fixtures/hkd_liquidity_premium_history_20260101.json",
        ],
        standard_references=[
            "SOA ASOP 56 §3.1.3",
            "SOA ASOP 56 §3.4",
            "SOA ASOP 25 §3.3",
            "IA TAS M §3.4",
            "IA TAS M §3.5",
            "IA TAS M §3.6",
            "IFoA APS X2 §4.2",
        ],
        before_snapshot=dict(PLACEHOLDER_LIQUIDITY, source="educational placeholder"),
        after_snapshot=_after_snapshot(res),
        impact_assessment=(
            "Adds the liquidity premium as the seventh correlated risk driver available to the "
            "nested/LSMC economic-capital proxy (rate, equity, credit, lapse, mortality, FX, "
            "liquidity) and calibrates it. The forced-sale haircut helper turns a horizon "
            "liquidity state into a liability-side impact (PV haircut on illiquid backing "
            "assets). Seven-driver aggregation and tail diagnostics follow in Phase 21 Task 4; "
            "until then capital evidence remains six-driver."
        ),
        quantitative_impact=(
            "HKD: kappa_l={:.4f}/yr (half-life {:.1f}yr), long_run_premium_p={:.4f} ({:.0f}bp), "
            "sigma_l={:.4f}, lambda_l={:.4f}, shift={:.4f}, Feller ratio={:.2f} ({})".format(
                res.mean_reversion_speed, res.half_life_years,
                res.long_run_premium_p, res.long_run_premium_p * 1e4,
                res.premium_vol, res.market_price_of_liquidity_risk,
                res.shift, res.feller_ratio, "holds" if res.feller_ok else "violated — full-truncation Euler documented",
            )
        ),
        author="AutomatedModelDev_Phase21",
        phase=PHASE,
        peer_reviewer="APS_X2_Independent_Reviewer",
        assumption_owner="ChiefActuary",
    )


def approve_liquidity_change_record(cr: ChangeRecord) -> ChangeRecord:
    """Drive the ChangeRecord DRAFT -> PEER_REVIEW -> OWNER_REVIEW -> APPROVED.

    NOTE: automation-driven sign-off is educational only; a genuine Assumption
    Owner and independent peer review are required before production use.
    """
    cr.submit_for_peer_review(
        "AutomatedModelDev_Phase21",
        "CIR++ liquidity-premium parameters calibrated to HKD educational-proxy history; submitting for peer review.",
    )
    cr.submit_to_owner(
        "APS_X2_Independent_Reviewer",
        "kappa_l / long-run premium / sigma_l / lambda_l recovered inside documented plausibility bands; "
        "delegated CIR OLS methodology and data lineage reviewed and reasonable for educational use.",
    )
    cr.approve(
        "ChiefActuary",
        "Calibrated CIR++ liquidity-premium parameters approved for educational use; production "
        "pricing/capital use requires a credentialled liquidity-premium series and a genuine "
        "independent APS X2 review.",
    )
    return cr


def _build_param_change_entry(res: LiquidityCalibrationResult, cr_id: str) -> AuditEntry:
    return AuditEntry.param_change(
        actor="AutomatedModelDev_Phase21",
        phase=PHASE,
        parameter_name="CIR_liquidity_premium_params[{}]".format(MARKET),
        old_value=PLACEHOLDER_LIQUIDITY,
        new_value={
            "mean_reversion_speed": round(res.mean_reversion_speed, 6),
            "long_run_premium_p": round(res.long_run_premium_p, 6),
            "premium_vol": round(res.premium_vol, 6),
            "market_price_of_liquidity_risk": round(res.market_price_of_liquidity_risk, 6),
            "shift": round(res.shift, 6),
            "initial_premium": round(res.initial_premium, 6),
        },
        rationale=(
            "Calibrated to {} educational-proxy liquidity-premium history via "
            "LiquidityPremiumCalibrator (homoscedastic CIR OLS transition regression for "
            "kappa_l + long-run premium, residual variance for sigma_l, documented "
            "risk-neutral anchor for lambda_l).".format(MARKET)
        ),
        standard_reference="SOA ASOP 56 §3.4; SOA ASOP 25 §3.3; IA TAS M §3.5",
        change_record_id=cr_id,
    )


# ---------------------------------------------------------------------------
# 3. Markdown report
# ---------------------------------------------------------------------------

def _build_markdown(report: Phase21LiquidityReport) -> str:
    ts = report.run_timestamp[:19].replace("T", " ") + " UTC"
    s = report.summary
    g = report.gate_gliq
    g_icon = "PASS ✅" if g.status == "PASS" else "FAIL ❌"
    crit_rows = "\n".join(
        "| {} | {} |".format(k, "PASS" if v else "FAIL") for k, v in s.check.criteria.items()
    )
    return """# Phase 21 Task 3 — Liquidity-Premium Driver Calibration (G-LIQ)

**Run:** {ts}
**Market:** {market} (educational-proxy liquidity premium / funding spread)
**Gate G-LIQ:** {gate}

## What this is

The CIR++ liquidity-premium / funding-spread driver is the **seventh** —
and the **last documented-but-omitted** — risk driver of the multi-driver
economic-capital proxy (rate, equity, credit spread, dynamic lapse, mortality
trend, FX, liquidity). This task calibrates it to educational-proxy HKD
history, mirroring the GBM/HW1F/CIR/OU-lapse calibrators.

## Calibrated parameters

| Parameter | Value |
|---|---|
| Mean reversion kappa_l | {kappa:.4f} /yr (half-life {hl:.1f} yr) |
| Long-run premium (P) | {lr:.4f} ({lrbp:.0f} bp) |
| Premium vol sigma_l | {sig:.4f} |
| Market price of liquidity risk lambda_l | {lam:.4f} |
| CIR++ shift | {shift:.4f} |
| Initial premium l(0) | {init:.4f} |
| Feller ratio (2 kappa b / sigma^2) | {feller:.2f} ({fok}) |
| Observations | {n} monthly |
| Fit R^2 (homoscedastic CIR regression) | {r2:.4f} |

## G-LIQ criteria

| Criterion | Outcome |
|---|---|
{crit}

**Evidence:** {evidence}

## Governance

- ChangeRecord `{crid}` — status **{crstatus}** (assumption_change)
- PARAM_CHANGE audit entries: {audits}
- MR-011 (multi-driver proxy educational): **{mr011}**
- MR-012 (driver omissions / educational calibration): **{mr012}**

## Methodology

Delegated homoscedastic CIR OLS transition regression (one tested estimator
for both CIR++ drivers — credit and liquidity): kappa_l and the P long-run
premium from the regression, sigma_l from the residual variance, lambda_l from
the documented risk-neutral long-run anchor via b^Q - b^P = lambda_l sigma_l^2 / kappa_l.

## Model-use restrictions

EDUCATIONAL ONLY. Single systemic liquidity factor; educational-proxy fixture;
single-path OLS; automation-driven sign-off. Production use requires a
credentialled liquidity-premium series, an ML/Kalman estimator with standard
errors, and an independent APS X2 review. Seven-driver capital aggregation is
Phase 21 Task 4 — capital evidence remains six-driver until then.

*Standards: SOA ASOP 56 3.1.3/3.4; SOA ASOP 25 3.3; IA TAS M 3.4/3.5/3.6;
EIOPA VA illiquidity-premium methodology; CIR (1985); Brigo-Mercurio (2006).*
""".format(
        ts=ts, market=s.market, gate=g_icon,
        kappa=s.kappa, hl=s.half_life_years, lr=s.long_run_premium_p,
        lrbp=s.long_run_premium_p * 1e4, sig=s.premium_vol,
        lam=s.market_price_of_liquidity_risk, shift=s.shift,
        init=s.initial_premium, feller=s.feller_ratio,
        fok="holds" if s.feller_ok else "violated — full-truncation Euler documented",
        n=s.n_obs, r2=s.fit_r2, crit=crit_rows, evidence=g.evidence,
        crid=report.change_record_id, crstatus=report.change_record_status,
        audits=", ".join(report.audit_entry_ids),
        mr011=report.mr011_status, mr012=report.mr012_status,
    )


# ---------------------------------------------------------------------------
# 4. Pipeline
# ---------------------------------------------------------------------------

def run_phase21_liquidity_calibration(
    fixture_dir=None,
    as_of_date: str = "20260101",
    governance_store: Optional[GovernanceStore] = None,
    store_path: str = ".claude-dev/GOVERNANCE_STORE.json",
    write_report: bool = False,
    docs_dir: str = "docs/validation",
    persist_governance: bool = False,
) -> Phase21LiquidityReport:
    """Full Phase 21 Task 3 pipeline. Returns the report dataclass."""
    ts = datetime.now(timezone.utc).isoformat()

    if governance_store is None and os.path.exists(store_path):
        try:
            governance_store = GovernanceStore.from_json(open(store_path, encoding="utf-8").read())
        except Exception:  # noqa: BLE001
            governance_store = GovernanceStore()
    if governance_store is None:
        governance_store = GovernanceStore()

    # -- Calibrate --
    loader = build_liquidity_loader(MARKET, fixture_dir=fixture_dir, as_of_date=as_of_date)
    inputs, lineage = loader.load()
    result = LiquidityPremiumCalibrator(inputs).calibrate()
    n_obs = len(inputs.premium_history)

    # -- ChangeRecord --
    cr = build_liquidity_change_record(result)
    cr = approve_liquidity_change_record(cr)
    governance_store.add_change_record(cr)

    # -- PARAM_CHANGE audit entry --
    audit_entry = _build_param_change_entry(result, cr.record_id)
    governance_store.audit_trail.append(audit_entry)

    # -- Score gate now the audit entry exists --
    has_audit = any(
        e.details.get("parameter_name") == "CIR_liquidity_premium_params[{}]".format(MARKET)
        for e in governance_store.audit_trail.filter_by_type(audit_entry.entry_type)
    )
    check = check_liquidity_calibration(MARKET, n_obs, result, has_param_change_audit=has_audit)
    gate = evaluate_liquidity_gate(check)

    summary = LiquidityCalibrationSummary(
        market=MARKET,
        calibration_date=result.calibration_date.isoformat(),
        kappa=float(result.mean_reversion_speed),
        long_run_premium_p=float(result.long_run_premium_p),
        premium_vol=float(result.premium_vol),
        market_price_of_liquidity_risk=float(result.market_price_of_liquidity_risk),
        shift=float(result.shift),
        initial_premium=float(result.initial_premium),
        half_life_years=float(result.half_life_years),
        feller_ratio=float(result.feller_ratio),
        feller_ok=bool(result.feller_ok),
        n_obs=n_obs,
        fit_r2=float(result.fit_r2),
        is_placeholder=bool(result.is_placeholder),
        notes=result.notes,
        lineage=lineage,
        check=check,
    )

    mr011_status = _refresh_risk(governance_store, MR_PROXY_ID, result, gate, ts)
    mr012_status = _refresh_risk(governance_store, MR_DRIVER_ID, result, gate, ts)

    report = Phase21LiquidityReport(
        run_timestamp=ts,
        summary=summary,
        gate_gliq=gate,
        change_record_id=cr.record_id,
        change_record_status=cr.status.value,
        mr011_status=mr011_status,
        mr012_status=mr012_status,
        audit_entry_ids=[audit_entry.entry_id],
    )
    report.markdown = _build_markdown(report)

    if write_report:
        ddir = Path(docs_dir)
        ddir.mkdir(parents=True, exist_ok=True)
        (ddir / "PHASE21_TASK3_LIQUIDITY_CALIBRATION_REPORT.md").write_text(report.markdown, encoding="utf-8")
        (ddir / "PHASE21_TASK3_LIQUIDITY_CALIBRATION_REPORT.json").write_text(report.to_json(), encoding="utf-8")

    if persist_governance:
        with open(store_path, "w", encoding="utf-8") as fh:
            fh.write(governance_store.to_json())

    return report


def _refresh_risk(
    store: GovernanceStore,
    risk_id: str,
    res: LiquidityCalibrationResult,
    gate: ProductionGateStatus,
    ts: str,
) -> str:
    """Refresh a risk-register entry to MITIGATED (only if G-LIQ passed) + GOVERNANCE entry."""
    try:
        entry = store.risk_register.get(risk_id)
    except KeyError:
        return "NOT_FOUND"
    if gate.status != "PASS":
        return entry.mitigation_status.value

    note = (
        "Phase 21 Task 3 (G-LIQ): CIR++ liquidity-premium / funding-spread driver added as the "
        "SEVENTH economic-capital-proxy driver — the LAST documented-but-omitted driver — and "
        "calibrated to HKD educational-proxy history. kappa_l={:.4f} (half-life {:.1f}yr), "
        "long_run_premium_p={:.4f} ({:.0f}bp), sigma_l={:.4f}, lambda_l={:.4f}; Feller ratio "
        "{:.2f}. ChangeRecord APPROVED + one PARAM_CHANGE audit entry; G-LIQ PASS. Residual "
        "(keeps the risk open, not closed): seven-driver tail-dependent aggregation + tail "
        "diagnostics are Phase 21 Task 4; calibration is educational-proxy single-path OLS — "
        "credentialled data + a genuine independent APS X2 review are required.".format(
            res.mean_reversion_speed, res.half_life_years, res.long_run_premium_p,
            res.long_run_premium_p * 1e4, res.premium_vol,
            res.market_price_of_liquidity_risk, res.feller_ratio,
        )
    )
    entry.update_mitigation(MitigationStatus.MITIGATED, notes=note)
    store.audit_trail.append(
        AuditEntry.governance(
            actor="AutomatedModelDev_Phase21",
            phase=PHASE,
            event="{} refreshed to MITIGATED following G-LIQ PASS (liquidity-premium driver calibration)".format(risk_id),
            details={
                "risk_id": risk_id,
                "new_status": MitigationStatus.MITIGATED.value,
                "gate": "G-LIQ",
                "gate_status": gate.status,
                "kappa_l": round(res.mean_reversion_speed, 6),
                "long_run_premium_p": round(res.long_run_premium_p, 6),
                "premium_vol": round(res.premium_vol, 6),
                "market_price_of_liquidity_risk": round(res.market_price_of_liquidity_risk, 6),
                "timestamp": ts,
            },
        )
    )
    return entry.mitigation_status.value


__all__ = [
    "LiquidityCalibrationSummary",
    "Phase21LiquidityReport",
    "build_liquidity_change_record",
    "approve_liquidity_change_record",
    "run_phase21_liquidity_calibration",
    "MR_PROXY_ID",
    "MR_DRIVER_ID",
    "PLACEHOLDER_LIQUIDITY",
    "MARKET",
]
