"""
Automated Model Health Checks — PAR Actuarial Model v2
=======================================================

Implements VR-H01 through VR-H12: lightweight component-level health checks
that run automatically at the start of every scheduled cycle to detect
regressions before any development work is performed.

Design principles
-----------------
1. FAST  — each check completes in <1 second; total suite <10 seconds.
2. NON-DESTRUCTIVE — no writes to production data; uses in-memory fixtures.
3. INDEPENDENT — each check catches its own exceptions; one failure does not
   block other checks.
4. TRACEABLE — results are emitted to GovernanceStore as a VALIDATION
   AuditEntry; fully round-trippable to JSON.

Health check IDs
----------------
VR-H01 : Module import health
VR-H02 : HybridGrid functional smoke test
VR-H03 : DynamicALMEngine smoke test (including 100%-cash regression)
VR-H04 : DistributedExecutor sequential backend
VR-H05 : DataValidator pipeline smoke test
VR-H06 : VaR/ES computation on synthetic loss distribution
VR-H07 : GovernanceStore JSON round-trip integrity
VR-H08 : IA validation requirements registry completeness
VR-H09 : Monthly projection smoke test with AuditTrail wiring
VR-H10 : ESGAdapter schema validation smoke test
VR-H11 : Two-factor (G2++) rate-calibration drift vs pinned reference
VR-H12 : ESG scenario-file column-schema hash vs pinned fingerprint

Industry standards
------------------
SOA ASOP 56 §3.5 — model health monitoring as part of ongoing validation
IA TAS M §3.3    — model governance traceability (health check in audit trail)
ERM              — automated regression detection for tail-risk components

DEVELOPMENT STATUS
------------------
Phase 3, Task 8: Fully implemented. 10 health checks, all green on delivery.
Roadmap 4.1 #12 (2026-07-10): added VR-H11 (calibration drift) and VR-H12
(scenario-file schema hash) governance monitors -- 12 health checks, all green.
"""

from __future__ import annotations

import enum
import hashlib
import json
import time
import traceback
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Module-level callable for VR-H04 (must be at module scope to be picklable)
# ---------------------------------------------------------------------------

def _square_int(x: int) -> int:
    """Module-level worker for VR-H04 pickling smoke test."""
    return x * x


# ---------------------------------------------------------------------------
# 0. Result primitives
# ---------------------------------------------------------------------------

class HealthStatus(str, enum.Enum):
    """Outcome of a single health check."""
    PASS  = "PASS"
    WARN  = "WARN"
    FAIL  = "FAIL"
    SKIP  = "SKIP"
    ERROR = "ERROR"


@dataclass
class HealthCheckResult:
    """Result of a single VR-H0x check."""
    check_id: str
    name: str
    status: HealthStatus
    duration_ms: float
    message: str
    details: Dict[str, Any] = field(default_factory=dict)
    error_trace: Optional[str] = None

    @property
    def ok(self) -> bool:
        return self.status in (HealthStatus.PASS, HealthStatus.WARN)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "check_id": self.check_id,
            "name": self.name,
            "status": self.status.value,
            "duration_ms": round(self.duration_ms, 2),
            "message": self.message,
            "details": self.details,
            "error_trace": self.error_trace,
        }


@dataclass
class HealthReport:
    """Aggregated results from all health checks."""
    report_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    generated_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    model_version: str = "par_model_v2"
    results: List[HealthCheckResult] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.results)

    @property
    def passed(self) -> int:
        return sum(1 for r in self.results if r.status == HealthStatus.PASS)

    @property
    def warned(self) -> int:
        return sum(1 for r in self.results if r.status == HealthStatus.WARN)

    @property
    def failed(self) -> int:
        return sum(1 for r in self.results
                   if r.status in (HealthStatus.FAIL, HealthStatus.ERROR))

    @property
    def skipped(self) -> int:
        return sum(1 for r in self.results if r.status == HealthStatus.SKIP)

    @property
    def overall_status(self) -> HealthStatus:
        if self.failed > 0:
            return HealthStatus.FAIL
        if self.warned > 0:
            return HealthStatus.WARN
        if self.skipped == self.total:
            return HealthStatus.SKIP
        return HealthStatus.PASS

    @property
    def total_duration_ms(self) -> float:
        return sum(r.duration_ms for r in self.results)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "generated_at": self.generated_at.isoformat(),
            "model_version": self.model_version,
            "overall_status": self.overall_status.value,
            "summary": {
                "total": self.total,
                "passed": self.passed,
                "warned": self.warned,
                "failed": self.failed,
                "skipped": self.skipped,
                "total_duration_ms": round(self.total_duration_ms, 2),
            },
            "results": [r.to_dict() for r in self.results],
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    def to_markdown(self) -> str:
        """Produce a compact markdown summary for MODEL_DEV_LOG.md."""
        icon = {
            HealthStatus.PASS: "OK", HealthStatus.WARN: "WARN",
            HealthStatus.FAIL: "FAIL", HealthStatus.SKIP: "SKIP",
            HealthStatus.ERROR: "ERROR",
        }
        lines = [
            f"### Model Health Report — {self.generated_at.strftime('%Y-%m-%dT%H:%M:%SZ')}",
            f"**Overall:** {icon[self.overall_status]} {self.overall_status.value}  ",
            (f"**Checks:** {self.passed}/{self.total} PASS | {self.warned} WARN | "
             f"{self.failed} FAIL | {self.skipped} SKIP  "),
            f"**Duration:** {self.total_duration_ms:.0f} ms",
            "",
            "| ID | Check | Status | ms | Message |",
            "|---|---|---|---|---|",
        ]
        for r in self.results:
            lines.append(
                f"| {r.check_id} | {r.name} | {icon.get(r.status,'?')} {r.status.value}"
                f" | {r.duration_ms:.0f} | {r.message} |"
            )
        if self.failed > 0:
            lines += ["", "**Failed checks:**"]
            for r in self.results:
                if not r.ok and r.error_trace:
                    lines.append(f"- **{r.check_id}**: `{r.error_trace[:200]}`")
        return "\n".join(lines)

    def emit_to_governance_store(self, store: Any) -> None:
        """Append a VALIDATION AuditEntry to a GovernanceStore."""
        from par_model_v2.governance.audit_trail import AuditEntry
        entry = AuditEntry.validation(
            actor="automated-health-check",
            phase="Phase 3",
            test_suite=f"ModelHealthSuite/{self.total}",
            tests_run=self.total,
            tests_passed=self.passed + self.warned,
            tests_failed=self.failed,
            outcome=self.overall_status.value,
            failed_tests=[r.check_id for r in self.results if not r.ok],
        )
        store.audit_trail.append(entry)


# ---------------------------------------------------------------------------
# 1. Check runner helper
# ---------------------------------------------------------------------------

def _run_check(
    check_id: str,
    name: str,
    fn: Callable[[], Tuple[HealthStatus, str, Dict[str, Any]]],
) -> HealthCheckResult:
    t0 = time.perf_counter()
    try:
        status, message, details = fn()
        error_trace = None
    except Exception:
        status = HealthStatus.ERROR
        message = "Unexpected exception during health check"
        details = {}
        error_trace = traceback.format_exc()
    duration_ms = (time.perf_counter() - t0) * 1000.0
    return HealthCheckResult(
        check_id=check_id, name=name, status=status,
        duration_ms=duration_ms, message=message,
        details=details, error_trace=error_trace,
    )


# ---------------------------------------------------------------------------
# 2. Individual health checks (VR-H01 through VR-H12)
# ---------------------------------------------------------------------------

def _check_module_imports() -> Tuple[HealthStatus, str, Dict]:
    """VR-H01: All par_model_v2 subpackages importable."""
    import importlib
    modules = [
        "par_model_v2.projection.hybrid_grid",
        "par_model_v2.projection.dynamic_alm",
        "par_model_v2.projection.monthly_projection",
        "par_model_v2.stochastic.esg_process",
        "par_model_v2.stochastic.esg_adapter",
        "par_model_v2.risk.risk_metrics",
        "par_model_v2.risk.stress_testing",
        "par_model_v2.governance.audit_trail",
        "par_model_v2.execution.distributed_executor",
        "par_model_v2.validation.ia_validation",
        "par_model_v2.validation.data_validator",
        "par_model_v2.calibration.calibration_framework",
    ]
    failed = []
    for mod in modules:
        try:
            importlib.import_module(mod)
        except Exception as e:
            failed.append(f"{mod}: {e}")
    if failed:
        return (
            HealthStatus.FAIL,
            f"{len(failed)}/{len(modules)} modules failed to import",
            {"failures": failed},
        )
    return (
        HealthStatus.PASS,
        f"All {len(modules)} submodules import cleanly",
        {"checked_count": len(modules)},
    )


def _check_hybrid_grid() -> Tuple[HealthStatus, str, Dict]:
    """VR-H02: HybridGrid construction, read/write, interpolation, boundary clamp."""
    from par_model_v2.projection.hybrid_grid import HybridGrid

    grid = HybridGrid(projection_months=60, age_nodes=[30, 40, 50], n_scenarios=10)
    assert grid.shape == (60, 3, 10), f"Shape mismatch: {grid.shape}"

    grid.set_value(t=0, age_node_idx=0, scenario_idx=0, value=1000.0)
    assert abs(grid.get_value(t=0, age_node_idx=0, scenario_idx=0) - 1000.0) < 1e-9

    for s in range(10):
        grid.set_value(t=0, age_node_idx=1, scenario_idx=s, value=float(s + 1))
    mean_val = grid.scenario_mean(t=0, age_node_idx=1)
    assert abs(mean_val - 5.5) < 1e-9, f"scenario_mean wrong: {mean_val}"

    # Boundary clamp
    grid.set_value(t=0, age_node_idx=0, scenario_idx=0, value=500.0)
    grid.set_value(t=0, age_node_idx=2, scenario_idx=0, value=1500.0)
    assert grid.interpolate_age(t=0, age=5.0,  scenario_idx=0) == 500.0
    assert grid.interpolate_age(t=0, age=99.0, scenario_idx=0) == 1500.0

    # Degenerate input — zero SA must not produce NaN
    degen = HybridGrid.from_liability_projection(
        projection_months=12, age_nodes=[35], n_scenarios=5,
        sum_assured=0.0, annual_premium=1000.0,
    )
    assert not degen.has_nan(), "Degenerate grid contains NaN"

    return (
        HealthStatus.PASS,
        "HybridGrid: shape, read/write, interp, boundary-clamp, degenerate-input all OK",
        {"shape": list(grid.shape), "scenario_mean": round(mean_val, 2)},
    )


def _check_dynamic_alm() -> Tuple[HealthStatus, str, Dict]:
    """VR-H03: DynamicALMEngine — normal run and 100%-cash regression."""
    from par_model_v2.projection.dynamic_alm import (
        DynamicALMEngine, SAAPolicy, PortfolioState,
    )

    saa = SAAPolicy(
        weights={"Govt": 0.40, "Credit": 0.30, "Equity": 0.20, "Cash": 0.10},
        rebalancing_threshold=0.05,
    )

    # Standard run
    portfolio = PortfolioState(
        holdings={"Govt": 400.0, "Credit": 300.0, "Equity": 200.0, "Cash": 100.0},
    )
    results = DynamicALMEngine(saa=saa).run(
        portfolio=portfolio, n_periods=3,
        annual_returns={"Govt": 0.03, "Credit": 0.04, "Equity": 0.08, "Cash": 0.02},
    )
    assert len(results) == 3, f"Expected 3 periods, got {len(results)}"
    # net_portfolio_mv is a method — call it
    final_mv = sum(results[-1].portfolio_after_rebalancing.holdings.values())
    assert final_mv > 0, f"Final MV non-positive: {final_mv}"

    # 100%-cash regression (VR-U02)
    portfolio_cash = PortfolioState(
        holdings={"Govt": 0.0, "Credit": 0.0, "Equity": 0.0, "Cash": 1000.0},
    )
    results_cash = DynamicALMEngine(saa=saa).run(
        portfolio=portfolio_cash, n_periods=2,
        annual_returns={"Govt": 0.03, "Credit": 0.04, "Equity": 0.08, "Cash": 0.02},
    )
    assert len(results_cash) == 2

    return (
        HealthStatus.PASS,
        f"DynamicALMEngine: 3-period run (final MV={final_mv:.0f}) and 100%-cash regression OK",
        {"final_mv": round(final_mv, 2)},
    )


def _check_distributed_executor() -> Tuple[HealthStatus, str, Dict]:
    """VR-H04: DistributedExecutor sequential backend correctness.

    Uses module-level _square_int (not a local function) so pickling succeeds.
    """
    from par_model_v2.execution.distributed_executor import (
        DistributedExecutor, ExecutionBackend, make_partial_task,
    )

    executor = DistributedExecutor(
        n_workers=2,
        backend=ExecutionBackend.SEQUENTIAL,
        fallback_to_sequential=True,
    )
    with executor:
        map_results = executor.map(_square_int, list(range(5)))

    values = [r.unwrap() for r in map_results]
    assert values == [0, 1, 4, 9, 16], f"Sequential map wrong: {values}"

    partial = make_partial_task(_square_int)
    assert partial(7) == 49, "Partial task call failed"

    return (
        HealthStatus.PASS,
        "DistributedExecutor: sequential map [0..4]^2=[0,1,4,9,16] correct",
        {"results": values},
    )


def _check_data_validators() -> Tuple[HealthStatus, str, Dict]:
    """VR-H05: All four DataValidators run on minimal valid inputs."""
    import pandas as pd
    from par_model_v2.validation.data_validator import (
        ModelPointValidator, MortalityTableValidator,
        LapseTableValidator, DiscountRateValidator,
    )

    issues = []

    # ModelPointValidator — required columns: age, gender, term_years, sum_assured, premium
    mp_df = pd.DataFrame({
        "policy_id": ["P001"],
        "age":       [35],
        "gender":    ["M"],
        "term_years":[10],
        "sum_assured":[100_000.0],
        "premium":   [5_000.0],
    })
    mp_report = ModelPointValidator().validate(mp_df)
    if mp_report.error_count > 0:
        issues.append(f"ModelPointValidator: {mp_report.error_count} errors — "
                      f"{mp_report.failed_checks()}")

    # MortalityTableValidator
    ages   = list(range(18, 66))
    qx_val = [0.0004 * (1.08 ** (a - 18)) for a in ages]
    mort_df = pd.DataFrame({"age": ages, "qx": qx_val, "gender": ["M"] * len(ages)})
    mort_report = MortalityTableValidator().validate(mort_df)
    if mort_report.error_count > 0:
        issues.append(f"MortalityTableValidator: {mort_report.error_count} errors")

    # LapseTableValidator
    lapse_df = pd.DataFrame({
        "policy_year": list(range(1, 21)),
        "lapse_rate":  [max(0.01, 0.15 - 0.006 * i) for i in range(20)],
    })
    lapse_report = LapseTableValidator().validate(lapse_df)
    if lapse_report.error_count > 0:
        issues.append(f"LapseTableValidator: {lapse_report.error_count} errors")

    # DiscountRateValidator (scalar)
    dr_report = DiscountRateValidator().validate(0.025)
    if dr_report.error_count > 0:
        issues.append(f"DiscountRateValidator: {dr_report.error_count} errors")

    if issues:
        return (
            HealthStatus.FAIL,
            f"DataValidator errors: {'; '.join(issues)}",
            {"issues": issues},
        )
    return (
        HealthStatus.PASS,
        "All 4 DataValidators pass on minimal valid inputs",
        {"validators_checked": 4},
    )


def _check_var_es() -> Tuple[HealthStatus, str, Dict]:
    """VR-H06: VaR and ES on a synthetic N(100, 20) loss distribution."""
    import numpy as np
    from par_model_v2.risk.risk_metrics import (
        RiskMetrics, LossDistribution, ConfidenceLevel,
    )

    rng    = np.random.default_rng(42)
    losses = rng.normal(loc=100.0, scale=20.0, size=5000)
    ld     = LossDistribution(losses=losses, label="health-check-synthetic")
    rm     = RiskMetrics(loss_distribution=ld)

    r95 = rm.empirical_var(ConfidenceLevel.CL_95)
    e95 = rm.empirical_es(ConfidenceLevel.CL_95)
    r99 = rm.empirical_var(ConfidenceLevel.CL_99)
    e99 = rm.empirical_es(ConfidenceLevel.CL_99)

    # N(100, 20): VaR_95 ≈ 132.9 — allow ±5 for n=5000 sampling noise
    assert 120 < r95.var_value < 145, f"VaR_95 out of range: {r95.var_value}"
    assert e95.es_value > r95.var_value, "ES_95 must exceed VaR_95"
    assert r99.var_value > r95.var_value, "VaR_99 must exceed VaR_95"
    assert e99.es_value  > r99.var_value, "ES_99 must exceed VaR_99"

    return (
        HealthStatus.PASS,
        (f"VaR/ES: VaR_95={r95.var_value:.1f}, ES_95={e95.es_value:.1f}, "
         f"VaR_99={r99.var_value:.1f}, ES_99={e99.es_value:.1f}"),
        {
            "var_95": round(r95.var_value, 2),
            "es_95":  round(e95.es_value,  2),
            "var_99": round(r99.var_value, 2),
            "es_99":  round(e99.es_value,  2),
        },
    )


def _check_governance_json_roundtrip() -> Tuple[HealthStatus, str, Dict]:
    """VR-H07: GovernanceStore JSON round-trip and SHA-256 integrity."""
    from par_model_v2.governance.audit_trail import GovernanceStore, AuditEntry

    store = GovernanceStore()
    store.audit_trail.append(
        AuditEntry.validation(
            actor="health-check",
            phase="Phase 3",
            test_suite="vr-h07-roundtrip",
            tests_run=1,
            tests_passed=1,
            tests_failed=0,
            outcome="PASS",
        )
    )

    json_str = store.to_json()
    store2   = GovernanceStore.from_json(json_str)
    entries  = store2.audit_trail.all()
    assert len(entries) == 1, f"Entry count mismatch: {len(entries)}"

    ok = store2.audit_trail.verify_all()
    assert ok, "Integrity check failed after round-trip"

    return (
        HealthStatus.PASS,
        "GovernanceStore: 1 AuditEntry survives JSON round-trip with SHA-256 integrity intact",
        {"entries": 1, "integrity_ok": True},
    )


def _check_ia_validation_registry() -> Tuple[HealthStatus, str, Dict]:
    """VR-H08: IA_VALIDATION_REQUIREMENTS registry completeness."""
    from par_model_v2.validation.ia_validation import (
        IA_VALIDATION_REQUIREMENTS, ValidationCategory,
    )

    reqs = IA_VALIDATION_REQUIREMENTS
    assert len(reqs) >= 20, f"Registry too small: {len(reqs)}"
    bad = [r.req_id for r in reqs if not r.req_id or not r.name]
    assert not bad, f"Requirements with missing id/name: {bad}"

    covered  = {r.category for r in reqs}
    all_cats = set(ValidationCategory)
    missing  = all_cats - covered
    if missing:
        return (
            HealthStatus.WARN,
            f"Registry: {len(reqs)} requirements; {len(missing)} categories uncovered",
            {"req_count": len(reqs), "missing_categories": [c.value for c in missing]},
        )
    return (
        HealthStatus.PASS,
        f"IA registry: {len(reqs)} requirements, all {len(all_cats)} categories covered",
        {"req_count": len(reqs), "categories_covered": len(covered)},
    )


def _check_monthly_projection() -> Tuple[HealthStatus, str, Dict]:
    """VR-H09: Monthly projection smoke test with AuditTrail wiring."""
    from par_model_v2.projection.monthly_projection import (
        run_full_projection, ParEndowmentProduct, AssetPosition,
    )
    from par_model_v2.governance.audit_trail import GovernanceStore

    product = ParEndowmentProduct(
        term_years=5, issue_age=35, gender="M",
        sum_assured=100_000.0, annual_premium=5_000.0,
    )
    positions = [
        AssetPosition("Govt",   50_000.0, 48_000.0, annual_yield=0.03),
        AssetPosition("Credit", 30_000.0, 29_000.0, annual_yield=0.04),
        AssetPosition("Cash",   20_000.0, 20_000.0, annual_yield=0.015),
    ]
    store  = GovernanceStore()
    result = run_full_projection(
        product=product,
        fund_positions=positions,
        discount_rate_annual=0.03,
        governance_store=store,
        run_label="health-check-smoke",
    )

    assert result is not None
    assert result.run_id is not None, "run_id not populated"

    # MODEL_RUN + VALIDATION = 2 audit entries
    n_entries = len(store.audit_trail.all())
    assert n_entries == 2, f"Expected 2 audit entries, got {n_entries}"
    assert store.audit_trail.verify_all(), "Audit trail integrity check failed"

    # result.summary is a method — call it to get the dict
    summary = result.summary()
    pv = summary.get("pv_net_liability", 0)

    return (
        HealthStatus.PASS,
        f"Monthly projection: 5y term, pv_net_liability={pv:,.0f}, {n_entries} audit entries",
        {
            "run_id":        result.run_id,
            "audit_entries": n_entries,
            "pv_net_liability": round(float(pv), 2),
        },
    )


def _check_esg_adapter() -> Tuple[HealthStatus, str, Dict]:
    """VR-H10: ESGAdapter schema validation on in-memory synthetic data.

    Uses a minimal 2-scenario × 3-month fixture (6 rows).  ScenarioAdequacyWarning
    is suppressed — this is a development/test fixture, not a production ESG set.
    """
    import warnings
    import pandas as pd
    from par_model_v2.stochastic.esg_adapter import ESGAdapter, ScenarioAdequacyWarning

    # Minimal valid fixture: 2 scenarios × 3 months = 6 rows
    rows = []
    for scen in range(1, 501):
        for month in range(3):
            rows.append({
                "scenario_id":  scen,
                "month":        month,
                "r_short":      0.025 + 0.001 * month,
                "zcb_1y":       0.975 - 0.001 * month,
                "zcb_10y":      0.780 - 0.002 * month,
                "equity_index": 1000.0 * (1.005 ** month),
                "measure":      "P",
            })
    df = pd.DataFrame(rows)

    adapter = ESGAdapter()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", ScenarioAdequacyWarning)
        loaded_df = adapter.load_from_dataframe(df)

    n_rows      = len(loaded_df)
    n_scenarios = loaded_df["scenario_id"].nunique()
    assert n_rows      == 1500, f"Expected 6 rows, got {n_rows}"
    assert n_scenarios == 500,  f"Expected 2 scenarios, got {n_scenarios}"
    assert set(["scenario_id", "month", "r_short"]).issubset(loaded_df.columns)

    return (
        HealthStatus.PASS,
        f"ESGAdapter: loaded {n_rows} rows, {n_scenarios} scenarios, schema valid",
        {"rows": n_rows, "scenarios": n_scenarios},
    )


# ---------------------------------------------------------------------------
# 2b. Governance monitors backing VR-H11 / VR-H12 (roadmap 4.1 #12)
# ---------------------------------------------------------------------------

# VR-H11 -- pinned governed reference calibration snapshot: the
# EnhancedG2PlusRateProcess / G2PlusParams defaults
# (par_model_v2/stochastic/esg_process.py). The digest regression-locks the governed
# two-factor rate calibration; any change to the live defaults surfaces here as drift.
# Re-baseline is OWNER-GATED (a legitimate recalibration must be signed off first).
_REFERENCE_CALIBRATION: Dict[str, Any] = {
    "model": "G2++/EnhancedG2PlusRateProcess",
    "mean_reversion_x": 0.10,
    "mean_reversion_y": 0.35,
    "vol_x": 0.010,
    "vol_y": 0.006,
    "factor_correlation": -0.70,
    "long_run_rate_p": 0.025,
    "market_price_of_risk_x": -0.10,
    "market_price_of_risk_y": -0.05,
}
_REFERENCE_CALIBRATION_DIGEST: str = (
    "e0c55f3c5001a8282dcf6d2b0d5ae060569f5c821d9f3878ef36cf712f7d43bc"
)
# Relative-drift tolerances (fraction of the reference magnitude).
_CALIBRATION_WARN_TOL: float = 0.02   # >2%  -> WARN (investigate)
_CALIBRATION_FAIL_TOL: float = 0.05   # >5%  -> FAIL (unreviewed calibration drift)

# VR-H12 -- pinned SHA-256 of the ESG scenario-file column schema
# (par_model_v2.stochastic.esg_adapter._REQUIRED_COLUMNS: name -> dtype-kind codes).
# Re-baseline is OWNER-GATED: an approved scenario-schema/contract change must be
# signed off before this pin moves.
_EXPECTED_SCENARIO_SCHEMA_HASH: str = (
    "9b2c4bec8d2a535fb10a249dd1845194f592861dbdcaa0a3843067da9e243938"
)


def _calibration_snapshot_digest(snapshot: Dict[str, Any]) -> str:
    """Canonical SHA-256 of a calibration snapshot (sorted keys, floats rounded 1e-10)."""
    canonical = json.dumps(
        {k: (round(v, 10) if isinstance(v, (int, float)) else v)
         for k, v in sorted(snapshot.items())},
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def compute_calibration_drift(
    reference: Dict[str, Any],
    candidate: Dict[str, Any],
    warn_tol: float = _CALIBRATION_WARN_TOL,
    fail_tol: float = _CALIBRATION_FAIL_TOL,
    abs_floor: float = 1e-6,
) -> Dict[str, Any]:
    """Per-parameter relative drift of a candidate calibration vs a governed reference.

    Relative drift for a numeric parameter is |cand - ref| / max(|ref|, abs_floor).
    A missing/extra key, or a changed non-numeric value, is STRUCTURAL drift and fails
    outright. Returns a JSON-safe dict
    {status, max_drift, per_param, missing, extra, mismatched} where status is
    "PASS" (no structural drift and max_drift <= warn_tol), "WARN"
    (warn_tol < max_drift <= fail_tol) or "FAIL" (structural, or max_drift > fail_tol).
    """
    ref_keys, cand_keys = set(reference), set(candidate)
    missing = sorted(ref_keys - cand_keys)
    extra = sorted(cand_keys - ref_keys)
    per_param: Dict[str, float] = {}
    mismatched: List[str] = []
    max_drift = 0.0
    for k in sorted(ref_keys & cand_keys):
        rv, cv = reference[k], candidate[k]
        numeric = (isinstance(rv, (int, float)) and isinstance(cv, (int, float))
                   and not isinstance(rv, bool) and not isinstance(cv, bool))
        if numeric:
            drift = abs(float(cv) - float(rv)) / max(abs(float(rv)), abs_floor)
            per_param[k] = drift
            if drift > max_drift:
                max_drift = drift
        elif rv != cv:
            mismatched.append(k)
    structural = bool(missing or extra or mismatched)
    if structural or max_drift > fail_tol:
        status = "FAIL"
    elif max_drift > warn_tol:
        status = "WARN"
    else:
        status = "PASS"
    return {
        "status": status,
        "max_drift": max_drift,
        "per_param": per_param,
        "missing": missing,
        "extra": extra,
        "mismatched": mismatched,
    }


def _scenario_schema_fingerprint(required_columns: Dict[str, Tuple[str, str]]) -> str:
    """Canonical SHA-256 over the ESG scenario-file column schema (name + dtype kinds)."""
    canonical = json.dumps(
        [[name, kinds] for name, (kinds, _desc) in required_columns.items()],
        separators=(",", ":"), ensure_ascii=True,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _check_calibration_drift() -> Tuple[HealthStatus, str, Dict]:
    """VR-H11: two-factor (G2++) rate-calibration drift vs a pinned governed reference.

    Monitors the LIVE governed default calibration (G2PlusParams in esg_process.py)
    against the pinned _REFERENCE_CALIBRATION and self-tests that the drift detector
    catches an injected out-of-tolerance perturbation (so a broken monitor cannot pass
    silently). PASS when the live calibration matches the reference within tolerance;
    WARN/FAIL surfaces drift for owner review (re-baseline is owner-gated).
    """
    ref_digest = _calibration_snapshot_digest(_REFERENCE_CALIBRATION)
    assert ref_digest == _REFERENCE_CALIBRATION_DIGEST, (
        f"Reference calibration digest moved: {ref_digest} "
        f"!= pinned {_REFERENCE_CALIBRATION_DIGEST}"
    )
    probe_ref = {"a": 0.10, "b": 0.006, "rho": -0.70}
    injected = compute_calibration_drift(probe_ref, dict(probe_ref, a=0.11))
    assert injected["status"] == "FAIL", "drift detector missed an injected +10% move"
    assert compute_calibration_drift(probe_ref, dict(probe_ref))["status"] == "PASS", \
        "drift detector false-positive on identical snapshot"

    from par_model_v2.stochastic.esg_process import G2PlusParams
    p = G2PlusParams()
    live = {
        "model": "G2++/EnhancedG2PlusRateProcess",
        "mean_reversion_x": p.mean_reversion_x,
        "mean_reversion_y": p.mean_reversion_y,
        "vol_x": p.vol_x,
        "vol_y": p.vol_y,
        "factor_correlation": p.factor_correlation,
        "long_run_rate_p": p.long_run_rate_p,
        "market_price_of_risk_x": p.market_price_of_risk_x,
        "market_price_of_risk_y": p.market_price_of_risk_y,
    }
    drift = compute_calibration_drift(_REFERENCE_CALIBRATION, live)
    live_digest = _calibration_snapshot_digest(live)
    status_map = {
        "PASS": HealthStatus.PASS,
        "WARN": HealthStatus.WARN,
        "FAIL": HealthStatus.FAIL,
    }
    status = status_map[drift["status"]]
    if status is HealthStatus.PASS:
        msg = (f"Calibration drift: G2++ live defaults match pinned reference "
               f"(max_drift={drift['max_drift']:.4f}); injected-drift self-test caught")
    else:
        worst = (max(drift["per_param"], key=drift["per_param"].get)
                 if drift["per_param"] else None)
        msg = (f"Calibration DRIFT {drift['status']}: max_drift={drift['max_drift']:.4f}"
               + (f" (worst: {worst})" if worst else "")
               + (f"; missing={drift['missing']}" if drift["missing"] else "")
               + (f"; extra={drift['extra']}" if drift["extra"] else ""))
    return (
        status,
        msg,
        {
            "reference_digest": _REFERENCE_CALIBRATION_DIGEST,
            "live_digest": live_digest,
            "max_drift": round(drift["max_drift"], 6),
            "drift_status": drift["status"],
            "warn_tol": _CALIBRATION_WARN_TOL,
            "fail_tol": _CALIBRATION_FAIL_TOL,
            "n_params": len(_REFERENCE_CALIBRATION),
            "injected_drift_detected": True,
        },
    )


def _check_scenario_schema_hash() -> Tuple[HealthStatus, str, Dict]:
    """VR-H12: ESG scenario-file schema hash vs a pinned governed fingerprint.

    Computes a canonical SHA-256 over the live scenario-file column schema
    (esg_adapter._REQUIRED_COLUMNS: column name -> dtype-kind codes) and compares it to
    the pinned _EXPECTED_SCENARIO_SCHEMA_HASH. Any add/remove/rename of a required
    column, or a dtype-kind change, moves the hash and FAILs the check -- a governance
    tripwire for unreviewed scenario-file contract changes. Re-baseline is owner-gated.
    """
    from par_model_v2.stochastic.esg_adapter import _REQUIRED_COLUMNS
    observed = _scenario_schema_fingerprint(_REQUIRED_COLUMNS)
    n_cols = len(_REQUIRED_COLUMNS)
    if observed != _EXPECTED_SCENARIO_SCHEMA_HASH:
        return (
            HealthStatus.FAIL,
            (f"Scenario schema hash MISMATCH: observed {observed[:12]}... "
             f"!= pinned {_EXPECTED_SCENARIO_SCHEMA_HASH[:12]}... "
             f"({n_cols} required columns) -- owner re-baseline required"),
            {
                "observed_hash": observed,
                "expected_hash": _EXPECTED_SCENARIO_SCHEMA_HASH,
                "n_required_columns": n_cols,
                "columns": list(_REQUIRED_COLUMNS.keys()),
            },
        )
    return (
        HealthStatus.PASS,
        (f"Scenario schema hash matches pinned fingerprint "
         f"({n_cols} required columns, sha256 {observed[:12]}...)"),
        {
            "schema_hash": observed,
            "n_required_columns": n_cols,
            "columns": list(_REQUIRED_COLUMNS.keys()),
        },
    )


# ---------------------------------------------------------------------------
# 3. Check registry
# ---------------------------------------------------------------------------

_CHECKS: List[Tuple[str, str, Callable]] = [
    ("VR-H01", "Module imports",                _check_module_imports),
    ("VR-H02", "HybridGrid smoke test",          _check_hybrid_grid),
    ("VR-H03", "DynamicALMEngine smoke test",    _check_dynamic_alm),
    ("VR-H04", "DistributedExecutor sequential", _check_distributed_executor),
    ("VR-H05", "DataValidator pipeline",         _check_data_validators),
    ("VR-H06", "VaR/ES computation",             _check_var_es),
    ("VR-H07", "GovernanceStore round-trip",     _check_governance_json_roundtrip),
    ("VR-H08", "IA validation registry",         _check_ia_validation_registry),
    ("VR-H09", "Monthly projection wiring",      _check_monthly_projection),
    ("VR-H10", "ESGAdapter schema validation",   _check_esg_adapter),
    ("VR-H11", "Calibration drift monitor",      _check_calibration_drift),
    ("VR-H12", "Scenario schema hash",           _check_scenario_schema_hash),
]


# ---------------------------------------------------------------------------
# 4. Public API
# ---------------------------------------------------------------------------

class ModelHealthChecker:
    """Entry point for automated health check runs.

    Parameters
    ----------
    skip_ids : list[str] | None
        Check IDs to skip (e.g. ["VR-H10"]).
    governance_store : GovernanceStore | None
        If provided, a VALIDATION AuditEntry is appended after the run.
    model_version : str
        Label embedded in the report.
    """

    def __init__(
        self,
        skip_ids: Optional[List[str]] = None,
        governance_store: Any = None,
        model_version: str = "par_model_v2",
    ) -> None:
        self._skip_ids         = set(skip_ids or [])
        self._governance_store = governance_store
        self._model_version    = model_version

    def run(self) -> HealthReport:
        """Execute all checks and return the aggregated HealthReport."""
        report = HealthReport(model_version=self._model_version)
        for check_id, name, fn in _CHECKS:
            if check_id in self._skip_ids:
                report.results.append(HealthCheckResult(
                    check_id=check_id, name=name,
                    status=HealthStatus.SKIP, duration_ms=0.0,
                    message="Skipped by caller",
                ))
            else:
                report.results.append(_run_check(check_id, name, fn))
        if self._governance_store is not None:
            try:
                report.emit_to_governance_store(self._governance_store)
            except Exception:
                pass
        return report


def run_health_checks(
    skip_ids: Optional[List[str]] = None,
    governance_store: Any = None,
    model_version: str = "par_model_v2",
) -> HealthReport:
    """Canonical entry point for scheduled task integration."""
    return ModelHealthChecker(
        skip_ids=skip_ids,
        governance_store=governance_store,
        model_version=model_version,
    ).run()


__all__ = [
    "HealthStatus",
    "HealthCheckResult",
    "HealthReport",
    "ModelHealthChecker",
    "run_health_checks",
]
