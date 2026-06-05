"""
Correlated risk aggregation for the multi-driver capital proxy.

Phase 15 Task 3.  Aggregates standalone rate and equity-guarantee capital
using the governed ESG rate/equity correlation, then compares that formula
result with a fully diversified two-driver nested capital run.

The module is intentionally additive.  It reuses the Task 1 two-driver nested
valuation primitives and does not modify the LSMC or out-of-sample validation
engines from Tasks 1-2.
"""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

import numpy as np

from par_model_v2.projection.monthly_projection import ParEndowmentProduct
from par_model_v2.projection.nested_stochastic_tvog import (
    CapitalMetrics,
    DEFAULT_CAPITAL_HORIZON_MONTHS,
    DEFAULT_CONFIDENCE_LEVEL,
    capital_metrics_from_liabilities,
)
from par_model_v2.projection.multi_driver_capital import (
    EquityGuaranteeSpec,
    _inner_pathwise_pvs_2d,
    _outer_states_2d,
)
from par_model_v2.stochastic.esg_process import (
    CorrelationMatrixValidator,
    GBMParams,
    HullWhiteParams,
    Measure,
    RiskFreeCurve,
    phase8_rate_equity_fx_correlation_matrix,
)


DEFAULT_AGGREGATION_GAP_TOLERANCE = 0.35


def _metric_dict(metrics: CapitalMetrics) -> Dict[str, object]:
    return metrics.summary()


def _rel_error(value: float, reference: float) -> float:
    denom = abs(reference) if abs(reference) > 1e-9 else 1.0
    return abs(value - reference) / denom


@dataclass
class RiskAggregationConfig:
    """Configuration for the correlated aggregation evidence run."""

    n_outer: int = 1_000
    n_inner: int = 256
    seed: int = 42
    confidence_level: float = DEFAULT_CONFIDENCE_LEVEL
    capital_horizon_months: int = DEFAULT_CAPITAL_HORIZON_MONTHS
    outer_measure: Measure = Measure.P
    aggregation_gap_tolerance: float = DEFAULT_AGGREGATION_GAP_TOLERANCE

    def __post_init__(self) -> None:
        if self.n_outer < 20:
            raise ValueError("n_outer must be >= 20")
        if self.n_inner < 8:
            raise ValueError("n_inner must be >= 8")
        if not (0.5 < self.confidence_level < 1.0):
            raise ValueError("confidence_level must be in (0.5, 1.0)")
        if self.capital_horizon_months <= 0:
            raise ValueError("capital_horizon_months must be positive")
        if self.aggregation_gap_tolerance < 0:
            raise ValueError("aggregation_gap_tolerance must be non-negative")
        self.outer_measure = Measure(self.outer_measure)

    def to_dict(self) -> Dict[str, object]:
        return {
            "n_outer": self.n_outer,
            "n_inner": self.n_inner,
            "seed": self.seed,
            "confidence_level": self.confidence_level,
            "capital_horizon_months": self.capital_horizon_months,
            "outer_measure": self.outer_measure.value,
            "aggregation_gap_tolerance": self.aggregation_gap_tolerance,
        }


@dataclass
class StandaloneCapital:
    """Standalone rate and equity-guarantee capital metrics."""

    rate_capital: CapitalMetrics
    equity_capital: CapitalMetrics
    standalone_scr_sum: float
    component_loss_correlation: float

    def to_dict(self) -> Dict[str, object]:
        return {
            "rate_capital": _metric_dict(self.rate_capital),
            "equity_capital": _metric_dict(self.equity_capital),
            "standalone_scr_sum": round(self.standalone_scr_sum, 6),
            "component_loss_correlation": round(self.component_loss_correlation, 6),
        }


@dataclass
class CorrelatedAggregation:
    """Formula aggregation and reconciliation to full nested capital."""

    esg_rate_equity_correlation: float
    esg_correlation_matrix: Tuple[Tuple[float, ...], ...]
    correlation_matrix_passed: bool
    correlated_scr: float
    full_nested_capital: CapitalMetrics
    diversification_benefit_formula: float
    diversification_benefit_nested: float
    formula_vs_nested_scr_gap: float
    formula_vs_nested_scr_rel_error: float

    def to_dict(self) -> Dict[str, object]:
        return {
            "esg_rate_equity_correlation": round(self.esg_rate_equity_correlation, 6),
            "esg_correlation_matrix": [list(row) for row in self.esg_correlation_matrix],
            "correlation_matrix_passed": self.correlation_matrix_passed,
            "correlated_scr": round(self.correlated_scr, 6),
            "full_nested_capital": _metric_dict(self.full_nested_capital),
            "diversification_benefit_formula": round(self.diversification_benefit_formula, 6),
            "diversification_benefit_nested": round(self.diversification_benefit_nested, 6),
            "formula_vs_nested_scr_gap": round(self.formula_vs_nested_scr_gap, 6),
            "formula_vs_nested_scr_rel_error": round(self.formula_vs_nested_scr_rel_error, 6),
        }


@dataclass
class RiskAggregationReport:
    """Full structured Phase 15 Task 3 risk-aggregation report."""

    config: RiskAggregationConfig
    standalone: StandaloneCapital
    aggregation: CorrelatedAggregation
    run_id: str
    duration_seconds: float
    verdict: str
    reproducibility_digest: str
    notes: List[str] = field(default_factory=list)
    audit_entry_id: Optional[str] = None

    def to_dict(self) -> Dict[str, object]:
        return {
            "run_id": self.run_id,
            "verdict": self.verdict,
            "standalone": self.standalone.to_dict(),
            "aggregation": self.aggregation.to_dict(),
            "reproducibility_digest": self.reproducibility_digest,
            "duration_seconds": round(self.duration_seconds, 4),
            "config": self.config.to_dict(),
            "notes": list(self.notes),
            "audit_entry_id": self.audit_entry_id,
            "standards": [
                "SOA ASOP 56 §3.5",
                "SOA ASOP 56 §3.1.3",
                "SOA ASOP 25 §3.3",
                "IA TAS M §3.6",
                "IA TAS M §3.2",
                "IFoA proxy-model working party",
            ],
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True)


class MultiDriverRiskAggregator:
    """Run standalone risk capital, formula aggregation, and nested comparison."""

    def __init__(
        self,
        product: ParEndowmentProduct,
        hw_params: Optional[HullWhiteParams] = None,
        gbm_params: Optional[GBMParams] = None,
        initial_curve: Optional[RiskFreeCurve] = None,
        equity_guarantee: Optional[EquityGuaranteeSpec] = None,
        annual_qx_fn: Optional[Callable] = None,
    ) -> None:
        self.product = product
        self.hw_params = hw_params if hw_params is not None else HullWhiteParams()
        self.gbm_params = gbm_params if gbm_params is not None else GBMParams()
        self.initial_curve = initial_curve
        self.equity_guarantee = equity_guarantee or EquityGuaranteeSpec()
        self.annual_qx_fn = annual_qx_fn

    def run(
        self,
        config: Optional[RiskAggregationConfig] = None,
        governance_store: Optional["object"] = None,
        actor: str = "MultiDriverRiskAggregator",
        phase: str = "Phase 15: Multi-Risk Economic Capital and Proxy-Model Validation",
    ) -> RiskAggregationReport:
        cfg = config or RiskAggregationConfig()
        if cfg.capital_horizon_months >= self.product.term_months:
            raise ValueError("capital_horizon_months must be less than product term")

        t0 = time.monotonic()
        run_id = "md-riskagg-" + uuid.uuid4().hex[:8]
        rem = self.product.term_months - cfg.capital_horizon_months

        outer = _outer_states_2d(
            cfg.n_outer,
            cfg.capital_horizon_months,
            cfg.outer_measure,
            self.hw_params,
            self.gbm_params,
            self.initial_curve,
            cfg.seed,
        )

        full_l = np.empty(len(outer), dtype=float)
        rate_l = np.empty(len(outer), dtype=float)
        equity_l = np.empty(len(outer), dtype=float)
        rate_only = EquityGuaranteeSpec(
            guarantee_rate=0.0,
            initial_index_level=self.equity_guarantee.initial_index_level,
        )
        child = np.random.SeedSequence(cfg.seed).spawn(len(outer))
        for i, (r, s) in enumerate(outer):
            inner_seed = int(child[i].generate_state(1)[0])
            full_pv = _inner_pathwise_pvs_2d(
                float(r), float(s), cfg.n_inner, rem, self.product, self.hw_params,
                self.gbm_params, cfg.capital_horizon_months, inner_seed,
                self.equity_guarantee, self.annual_qx_fn,
            )
            rate_pv = _inner_pathwise_pvs_2d(
                float(r), float(s), cfg.n_inner, rem, self.product, self.hw_params,
                self.gbm_params, cfg.capital_horizon_months, inner_seed,
                rate_only, self.annual_qx_fn,
            )
            full_l[i] = float(full_pv.mean())
            rate_l[i] = float(rate_pv.mean())
            equity_l[i] = full_l[i] - rate_l[i]

        rate_cap = capital_metrics_from_liabilities(
            rate_l, cfg.confidence_level, cfg.capital_horizon_months
        )
        equity_cap = capital_metrics_from_liabilities(
            equity_l, cfg.confidence_level, cfg.capital_horizon_months
        )
        full_cap = capital_metrics_from_liabilities(
            full_l, cfg.confidence_level, cfg.capital_horizon_months
        )

        component_corr = float(np.corrcoef(rate_l, equity_l)[0, 1])
        if not np.isfinite(component_corr):
            component_corr = 0.0

        standalone_sum = float(rate_cap.scr_proxy + equity_cap.scr_proxy)
        rho = float(self.gbm_params.rate_equity_correlation)
        aggregated_variance = (
            rate_cap.scr_proxy ** 2
            + equity_cap.scr_proxy ** 2
            + 2.0 * rho * rate_cap.scr_proxy * equity_cap.scr_proxy
        )
        correlated_scr = float(np.sqrt(max(0.0, aggregated_variance)))

        matrix_raw = phase8_rate_equity_fx_correlation_matrix(self.gbm_params)
        # phase8_rate_equity_fx_correlation_matrix returns a pandas DataFrame;
        # iterating it directly yields column labels (strings), so coerce to a
        # numeric ndarray before building the immutable tuple-of-tuples.
        matrix_arr = np.asarray(matrix_raw, dtype=float)
        matrix = tuple(tuple(float(x) for x in row) for row in matrix_arr)
        corr_report = CorrelationMatrixValidator().validate_matrix(matrix, repair=False)

        aggregation = CorrelatedAggregation(
            esg_rate_equity_correlation=rho,
            esg_correlation_matrix=matrix,
            correlation_matrix_passed=bool(corr_report.passed),
            correlated_scr=correlated_scr,
            full_nested_capital=full_cap,
            diversification_benefit_formula=standalone_sum - correlated_scr,
            diversification_benefit_nested=standalone_sum - full_cap.scr_proxy,
            formula_vs_nested_scr_gap=correlated_scr - full_cap.scr_proxy,
            formula_vs_nested_scr_rel_error=_rel_error(correlated_scr, full_cap.scr_proxy),
        )
        standalone = StandaloneCapital(
            rate_capital=rate_cap,
            equity_capital=equity_cap,
            standalone_scr_sum=standalone_sum,
            component_loss_correlation=component_corr,
        )

        notes: List[str] = [
            "Standalone rate capital uses the guaranteed-benefit component with the equity guarantee switched off.",
            "Standalone equity capital uses the equity-guarantee component isolated by common-random-number subtraction.",
            "Formula aggregation uses the ESG rate_equity_correlation input, not a fitted capital-factor correlation.",
        ]
        verdict = self._verdict(cfg, standalone, aggregation, notes)

        digest = hashlib.sha256(
            np.round(
                np.concatenate([
                    full_l,
                    rate_l,
                    equity_l,
                    np.array([correlated_scr, rho, component_corr], dtype=float),
                ]),
                9,
            ).tobytes()
        ).hexdigest()

        duration = time.monotonic() - t0
        audit_entry_id = None
        if governance_store is not None:
            try:
                from par_model_v2.governance.audit_trail import AuditEntry

                entry = AuditEntry.model_run(
                    actor=actor,
                    phase=phase,
                    run_id=run_id,
                    scenario_count=cfg.n_outer * cfg.n_inner,
                    duration_seconds=round(duration, 4),
                    outcome=verdict.split()[0],
                    files_changed=[
                        "par_model_v2/projection/multi_driver_risk_aggregation.py"
                    ],
                    test_summary=(
                        "rate SCR={:.2f}; equity SCR={:.2f}; formula SCR={:.2f}; "
                        "full nested SCR={:.2f}; rho={:.3f}".format(
                            rate_cap.scr_proxy,
                            equity_cap.scr_proxy,
                            correlated_scr,
                            full_cap.scr_proxy,
                            rho,
                        )
                    ),
                )
                governance_store.audit_trail.append(entry)
                audit_entry_id = entry.entry_id
            except Exception as exc:  # pragma: no cover - governance is optional
                notes.append("Governance audit append skipped: {}".format(exc))

        return RiskAggregationReport(
            config=cfg,
            standalone=standalone,
            aggregation=aggregation,
            run_id=run_id,
            duration_seconds=duration,
            verdict=verdict,
            reproducibility_digest=digest,
            notes=notes,
            audit_entry_id=audit_entry_id,
        )

    @staticmethod
    def _verdict(
        cfg: RiskAggregationConfig,
        standalone: StandaloneCapital,
        aggregation: CorrelatedAggregation,
        notes: List[str],
    ) -> str:
        checks = [
            aggregation.correlation_matrix_passed,
            aggregation.correlated_scr <= standalone.standalone_scr_sum + 1e-9,
            aggregation.full_nested_capital.scr_proxy <= standalone.standalone_scr_sum + 1e-9,
            aggregation.formula_vs_nested_scr_rel_error <= cfg.aggregation_gap_tolerance,
        ]
        if aggregation.formula_vs_nested_scr_rel_error > cfg.aggregation_gap_tolerance:
            notes.append(
                "Formula-vs-nested SCR gap exceeds tolerance; review non-linear guarantee interactions."
            )
        if all(checks):
            return "PASS - correlated aggregation reconciles to nested diversified capital"
        return "PARTIAL - aggregation evidence generated with review items"


def risk_aggregation_use_restrictions() -> Dict[str, object]:
    return {
        "module": "par_model_v2/projection/multi_driver_risk_aggregation.py",
        "classification": "EDUCATIONAL ONLY - NOT a regulatory capital model",
        "risk_drivers": ["short rate", "equity guarantee"],
        "method": "Standalone SCRs aggregated with the ESG rate/equity correlation and benchmarked to full nested capital.",
        "limitations": [
            "Formula aggregation is a second-moment approximation and may miss non-linear guarantee interactions.",
            "The ESG factor correlation is not a calibrated capital-module correlation.",
            "Lapse, mortality trend, credit spread, FX, liquidity, and management-action risks remain outside this aggregation.",
            "Credentialled calibration data and independent APS X2 review are still required before production use.",
        ],
        "standards": [
            "SOA ASOP 56 §3.1.3",
            "SOA ASOP 56 §3.5",
            "SOA ASOP 25 §3.3",
            "IA TAS M §3.2",
            "IA TAS M §3.6",
        ],
    }


def risk_aggregation_use_restrictions_json() -> str:
    return json.dumps(risk_aggregation_use_restrictions(), indent=2, sort_keys=True)

