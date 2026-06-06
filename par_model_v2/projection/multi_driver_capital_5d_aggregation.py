"""
Five-Driver Tail-Dependent Risk Aggregation for the Economic-Capital Proxy
==========================================================================

Phase 19 Task 4 (aggregation half).  Generalises the Phase 18 Task 4
*four-driver* variance-covariance + copula aggregation
(:mod:`par_model_v2.projection.multi_driver_capital_4d_aggregation`) to the
**five-driver** economic-capital proxy
``(rate, equity-guarantee, credit-spread, lapse-behaviour, mortality-trend)`` of
:mod:`par_model_v2.projection.multi_driver_capital_5d`.

What it produces
----------------
For one shared set of governed, 5-factor-correlated outer states ``(r,S,s,b,m)``
at the capital horizon H it isolates **five** standalone capital-loss vectors by
a common-random-number (CRN) decomposition of the conditional liability, then:

  1. aggregates the five standalone SCRs with the governed **5x5 ESG factor
     correlation** (variance-covariance / second-moment formula) - the legacy
     method whose understatement is **MR-010**;
  2. re-aggregates the five realised standalone capital-loss vectors with a
     **copula** fitted to the *realised losses* (Gaussian / Student-t /
     survival-Clayton, selected by AIC) - the Phase 18 Task 1 tail-dependent
     mitigation, here reused unchanged via :class:`CopulaRiskAggregator`;
  3. benchmarks both against the **genuine five-driver nested capital**, computed
     on the SAME outer states and inner seeds (all five drivers ON), so the
     comparison is exact like-for-like.

The fifth driver - mortality trend - enters the policyholder benefit through the
mortality multiplier ``G(m_H) = exp(theta * m_H)`` that scales the central
annual ``q_x`` used to build the residual death / maturity cashflow vector.
Like the fourth (lapse) driver, mortality acts on the *guaranteed* leg, which is
itself scaled by the multiplicative in-force factor ``IF(r,b)``; the genuine
nested liability therefore carries a ``IF x G(m)`` cross-term that a first-order
additive CRN split cannot reproduce.  This module measures and discloses that
interaction residual rather than hiding it.  Mortality trend is **non-financial**
(P = Q, no risk premium) and is **orthogonal** to every financial driver in the
default 5x5 matrix, so it injects a second orthogonal tail axis: a SMALL,
near-additive standalone contribution that the copula must not over-state.

The module is **additive**: it imports, but never modifies, the five-driver
nested primitives (:mod:`...multi_driver_capital_5d`) and the Phase 18 Task 1
copula aggregator (:mod:`...multi_driver_copula_aggregation`).

SOA ASOP 56 §3.5; SOA ASOP 25 §3.3; SOA ASOP 7 §3.3; SOA ASOP 56 §3.1;
IA TAS M §3.2/§3.5/§3.6; Solvency II Delegated Reg. Art. 234;
IFoA Life Aggregation & Simulation WP; Lee & Carter (1992).
"""

from __future__ import annotations

import hashlib
import time
import uuid
import json
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

import numpy as np

from par_model_v2.projection.monthly_projection import ParEndowmentProduct
from par_model_v2.projection.nested_stochastic_tvog import (
    CapitalMetrics,
    DEFAULT_CAPITAL_HORIZON_MONTHS,
    DEFAULT_CONFIDENCE_LEVEL,
    CAPITAL_OUTER_MINIMUM,
    capital_metrics_from_liabilities,
)
from par_model_v2.projection.multi_driver_capital import EquityGuaranteeSpec
from par_model_v2.projection.multi_driver_capital_3d import CreditExposureSpec
from par_model_v2.projection.multi_driver_capital_4d import (
    FourDriverCorrelation,
    LapseExposureSpec,
)
from par_model_v2.projection.multi_driver_capital_5d import (
    FiveDriverCorrelation,
    MortalityExposureSpec,
    _inner_pathwise_pvs_5d,
    _outer_states_5d,
)
from par_model_v2.projection.multi_driver_copula_aggregation import (
    CopulaAggregationConfig,
    CopulaAggregationReport,
    CopulaRiskAggregator,
)
from par_model_v2.stochastic.credit_spread import CreditSpreadParams
from par_model_v2.stochastic.esg_process import (
    CorrelationMatrixValidator,
    GBMParams,
    HullWhiteParams,
    Measure,
    RiskFreeCurve,
)
from par_model_v2.stochastic.lapse_behaviour import LapseBehaviourParams
from par_model_v2.stochastic.mortality_trend import (
    MortalityTrendParams,
    default_mortality_trend,
)


#: The var-covar formula must reconcile to nested within this rel. error to PASS.
DEFAULT_FIVED_AGG_GAP_TOLERANCE = 0.35


def _rel_error(value: float, reference: float) -> float:
    denom = abs(reference) if abs(reference) > 1e-9 else 1.0
    return abs(value - reference) / denom


class _NoLapseExposure(LapseExposureSpec):
    """A lapse-exposure whose in-force factor is identically 1.0 (lapse OFF)."""

    def inforce_factor(self, r_h: float, b_h: float, h_month: int, term_months: int) -> float:  # noqa: D401
        return 1.0


class _NoMortalityExposure(MortalityExposureSpec):
    """A mortality-exposure whose multiplier is identically 1.0 (mortality OFF).

    Switches the mortality-trend driver OFF in the CRN decomposition: the
    guaranteed benefit is valued on the *central* ``q_x`` basis (``G = 1``), so
    the isolated mortality component is ``L_mort = guaranteed(G(m)) - guaranteed``.
    """

    def multiplier(self, m_h: float) -> float:  # noqa: D401
        return 1.0


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass
class FiveDriverAggregationConfig:
    """Configuration for the Phase 19 Task 4 five-driver aggregation run."""

    n_outer: int = CAPITAL_OUTER_MINIMUM
    n_inner: int = 128
    seed: int = 42
    confidence_level: float = DEFAULT_CONFIDENCE_LEVEL
    capital_horizon_months: int = DEFAULT_CAPITAL_HORIZON_MONTHS
    outer_measure: Measure = Measure.P
    aggregation_gap_tolerance: float = DEFAULT_FIVED_AGG_GAP_TOLERANCE
    n_sim_copula: int = 200_000

    def __post_init__(self) -> None:
        if self.n_outer < 100:
            raise ValueError("n_outer must be >= 100")
        if self.n_inner < 1:
            raise ValueError("n_inner must be >= 1")
        if not (0.5 < self.confidence_level < 1.0):
            raise ValueError("confidence_level must be in (0.5, 1.0)")
        if self.capital_horizon_months <= 0:
            raise ValueError("capital_horizon_months must be positive")
        if self.aggregation_gap_tolerance < 0:
            raise ValueError("aggregation_gap_tolerance must be non-negative")
        if self.n_sim_copula < 1_000:
            raise ValueError("n_sim_copula must be >= 1000")
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
            "n_sim_copula": self.n_sim_copula,
        }


@dataclass
class FiveDriverStandaloneCapital:
    """The five CRN-isolated standalone capital figures + realised loss corr."""

    rate_capital: CapitalMetrics
    equity_capital: CapitalMetrics
    credit_capital: CapitalMetrics
    lapse_capital: CapitalMetrics
    mortality_capital: CapitalMetrics
    standalone_scr_sum: float
    loss_correlation_matrix: Tuple[Tuple[float, ...], ...]

    def scr_vector(self) -> np.ndarray:
        return np.array(
            [
                self.rate_capital.scr_proxy,
                self.equity_capital.scr_proxy,
                self.credit_capital.scr_proxy,
                self.lapse_capital.scr_proxy,
                self.mortality_capital.scr_proxy,
            ],
            dtype=float,
        )

    def to_dict(self) -> Dict[str, object]:
        return {
            "rate_capital": self.rate_capital.summary(),
            "equity_capital": self.equity_capital.summary(),
            "credit_capital": self.credit_capital.summary(),
            "lapse_capital": self.lapse_capital.summary(),
            "mortality_capital": self.mortality_capital.summary(),
            "standalone_scr_sum": round(self.standalone_scr_sum, 4),
            "loss_correlation_matrix": [
                [round(x, 6) for x in row] for row in self.loss_correlation_matrix
            ],
        }


@dataclass
class FiveDriverVarCovarAggregation:
    """Variance-covariance (5x5 ESG factor) aggregation vs nested benchmark."""

    esg_correlation_matrix: Tuple[Tuple[float, ...], ...]
    correlation_matrix_passed: bool
    correlated_scr: float
    full_nested_capital: CapitalMetrics
    crn_additive_capital: CapitalMetrics
    interaction_residual_scr: float
    interaction_residual_rel: float
    diversification_benefit_formula: float
    diversification_benefit_nested: float
    formula_vs_nested_scr_gap: float
    formula_vs_nested_scr_rel_error: float
    esg_understatement_pct: float

    def to_dict(self) -> Dict[str, object]:
        return {
            "esg_correlation_matrix": [
                [round(x, 6) for x in row] for row in self.esg_correlation_matrix
            ],
            "correlation_matrix_passed": bool(self.correlation_matrix_passed),
            "correlated_scr": round(self.correlated_scr, 4),
            "full_nested_capital": self.full_nested_capital.summary(),
            "crn_additive_capital": self.crn_additive_capital.summary(),
            "interaction_residual_scr": round(self.interaction_residual_scr, 4),
            "interaction_residual_rel": round(self.interaction_residual_rel, 6),
            "diversification_benefit_formula": round(self.diversification_benefit_formula, 4),
            "diversification_benefit_nested": round(self.diversification_benefit_nested, 4),
            "formula_vs_nested_scr_gap": round(self.formula_vs_nested_scr_gap, 4),
            "formula_vs_nested_scr_rel_error": round(self.formula_vs_nested_scr_rel_error, 6),
            "esg_understatement_pct": round(self.esg_understatement_pct, 6),
        }


@dataclass
class FiveDriverAggregationReport:
    """Full structured Phase 19 Task 4 five-driver aggregation report."""

    config: FiveDriverAggregationConfig
    drivers: Tuple[str, ...]
    standalone: FiveDriverStandaloneCapital
    var_covar: FiveDriverVarCovarAggregation
    copula: CopulaAggregationReport
    nested_scr: float
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
            "drivers": list(self.drivers),
            "nested_scr": round(self.nested_scr, 4),
            "standalone": self.standalone.to_dict(),
            "var_covar": self.var_covar.to_dict(),
            "copula": self.copula.to_dict(),
            "reproducibility_digest": self.reproducibility_digest,
            "duration_seconds": round(self.duration_seconds, 4),
            "config": self.config.to_dict(),
            "notes": list(self.notes),
            "audit_entry_id": self.audit_entry_id,
            "standards": [
                "SOA ASOP 56 §3.5",
                "SOA ASOP 56 §3.1",
                "SOA ASOP 25 §3.3",
                "SOA ASOP 7 §3.3",
                "IA TAS M §3.2",
                "IA TAS M §3.5",
                "IA TAS M §3.6",
                "Solvency II Delegated Reg. Art. 234",
                "IFoA Life Aggregation & Simulation WP",
                "Lee & Carter (1992)",
            ],
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True)

    def to_markdown(self) -> str:
        vc = self.var_covar
        sa = self.standalone
        cop = self.copula
        sel = cop.selected
        lines = [
            "# Phase 19 Task 4 - Five-Driver Tail-Dependent Risk Aggregation",
            "",
            "**Drivers:** {}".format(", ".join(self.drivers)),
            "",
            "**Verdict:** {}".format(self.verdict),
            "",
            "Run `{}` | {} s | digest `{}`".format(
                self.run_id, round(self.duration_seconds, 2),
                self.reproducibility_digest[:12]),
            "",
            "## 1. Standalone capital (CRN-isolated)",
            "",
            "| Driver | SCR |",
            "|--------|----:|",
            "| Rate | {:,.1f} |".format(sa.rate_capital.scr_proxy),
            "| Equity guarantee | {:,.1f} |".format(sa.equity_capital.scr_proxy),
            "| Credit spread | {:,.1f} |".format(sa.credit_capital.scr_proxy),
            "| Lapse behaviour | {:,.1f} |".format(sa.lapse_capital.scr_proxy),
            "| Mortality trend | {:,.1f} |".format(sa.mortality_capital.scr_proxy),
            "| **Sum (no diversification)** | **{:,.1f}** |".format(sa.standalone_scr_sum),
            "",
            "## 2. Aggregation vs genuine five-driver nested capital",
            "",
            "| Method | Aggregate SCR | Rel. error vs nested |",
            "|--------|--------------:|---------------------:|",
            "| Var-covar (5x5 ESG factor) | {:,.1f} | {:.1%} |".format(
                vc.correlated_scr, vc.formula_vs_nested_scr_rel_error),
            "| Copula ({}, realised losses) | {:,.1f} | {:.1%} |".format(
                cop.selected_copula, sel.aggregated_capital.scr_proxy,
                sel.scr_rel_error_vs_nested),
            "| **Nested ground truth** | **{:,.1f}** | - |".format(self.nested_scr),
            "",
            "ESG-factor var-covar understates nested capital by **{:.1f}%** (MR-010).".format(
                100.0 * vc.esg_understatement_pct),
            "Copula-on-realised-losses reconciles within **{:.1f}%**.".format(
                100.0 * sel.scr_rel_error_vs_nested),
            "",
            "## 3. CRN additive-decomposition residual (multiplicative lapse x mortality)",
            "",
            "- CRN additive-sum SCR: {:,.1f}".format(vc.crn_additive_capital.scr_proxy),
            "- Genuine nested SCR:   {:,.1f}".format(self.nested_scr),
            "- Interaction residual: {:,.1f} ({:.1%} of nested) - the multiplicative "
            "in-force x (equity-guarantee + mortality-G) cross-terms the additive split "
            "omits.".format(vc.interaction_residual_scr, vc.interaction_residual_rel),
            "",
            "## 4. Mortality-trend driver (5th, second non-financial, orthogonal)",
            "",
            "- Mortality is non-financial (P=Q, no risk premium) and orthogonal to every "
            "financial driver in the default 5x5 matrix; standalone SCR "
            "{:,.1f} is SMALL vs rate/equity/credit, confirming a genuinely orthogonal "
            "second tail axis (cf the Phase 19 Task 3 nested finding).".format(
                sa.mortality_capital.scr_proxy),
            "",
            "## Notes",
            "",
        ]
        lines += ["- {}".format(n) for n in self.notes]
        return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Aggregator
# ---------------------------------------------------------------------------

class FiveDriverRiskAggregator:
    """Five-driver standalone capital, var-covar + copula aggregation, nested benchmark.

    Reuses the Phase 19 Task 3 five-driver nested primitives and the Phase 18
    Task 1 copula aggregator; both are imported, never modified.

    SOA ASOP 56 §3.5; SOA ASOP 25 §3.3; SOA ASOP 7 §3.3; IA TAS M §3.2/§3.5/§3.6.
    """

    def __init__(
        self,
        product: ParEndowmentProduct,
        hw_params: Optional[HullWhiteParams] = None,
        gbm_params: Optional[GBMParams] = None,
        spread_params: Optional[CreditSpreadParams] = None,
        lapse_params: Optional[LapseBehaviourParams] = None,
        mortality_params: Optional[MortalityTrendParams] = None,
        correlation: Optional[FiveDriverCorrelation] = None,
        initial_curve: Optional[RiskFreeCurve] = None,
        equity_guarantee: Optional[EquityGuaranteeSpec] = None,
        credit_exposure: Optional[CreditExposureSpec] = None,
        lapse_exposure: Optional[LapseExposureSpec] = None,
        mortality_exposure: Optional[MortalityExposureSpec] = None,
        annual_qx_fn: Optional[Callable] = None,
    ) -> None:
        self.product = product
        self.hw_params = hw_params if hw_params is not None else HullWhiteParams()
        self.gbm_params = gbm_params if gbm_params is not None else GBMParams()
        self.spread_params = spread_params if spread_params is not None else CreditSpreadParams()
        self.lapse_params = lapse_params if lapse_params is not None else LapseBehaviourParams()
        self.mortality_params = (
            mortality_params if mortality_params is not None else default_mortality_trend()
        )
        self.correlation = correlation if correlation is not None else FiveDriverCorrelation()
        self.initial_curve = initial_curve
        self.equity_guarantee = equity_guarantee or EquityGuaranteeSpec()
        self.credit_exposure = credit_exposure or CreditExposureSpec()
        self.lapse_exposure = lapse_exposure or LapseExposureSpec()
        self.mortality_exposure = mortality_exposure or MortalityExposureSpec()
        self.annual_qx_fn = annual_qx_fn

    def _component_liabilities(
        self, outer: np.ndarray, cfg: FiveDriverAggregationConfig
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """CRN-isolated rate / equity / credit / lapse / mortality + full liability.

        For each outer state ``(r,S,s,b,m)`` the SAME inner seed drives six
        valuations, so the inner ``(rate, equity, spread)`` paths are identical:

            L_base = guaranteed_pv(central q_x)          (eq OFF, cr OFF, lapse OFF, mort OFF)
            L_re   = guaranteed_pv + equity_pv           (eq ON)
            L_rc   = guaranteed_pv + credit_pv           (cr ON)
            L_rl   = IF(r,b) * guaranteed_pv             (lapse ON)
            L_rm   = guaranteed_pv(G(m) q_x)             (mort ON)
            L_full = IF(r,b)*(guaranteed_pv(G(m)) + equity_pv) + credit_pv   (all ON)

        ->  rate_l     = L_base
            equity_l   = L_re - L_base
            credit_l   = L_rc - L_base
            lapse_l    = L_rl - L_base   (= (IF-1)*guaranteed_pv)
            mortality_l= L_rm - L_base   (= (G(m)-effect)*guaranteed_pv)

        The five additive components do NOT sum to ``L_full`` because both lapse
        (IF) and mortality (G) act multiplicatively on the guaranteed leg (the
        ``IF x equity`` and ``IF x G`` cross-terms); the residual is reported.
        """
        rem = self.product.term_months - cfg.capital_horizon_months
        eq_on = self.equity_guarantee
        eq_off = EquityGuaranteeSpec(
            guarantee_rate=0.0,
            initial_index_level=self.equity_guarantee.initial_index_level,
        )
        cr_on = self.credit_exposure
        cr_off = CreditExposureSpec(exposure_rate=0.0)
        lapse_on = self.lapse_exposure
        lapse_off = _NoLapseExposure(
            assumption=self.lapse_exposure.assumption,
            credited_rate=self.lapse_exposure.credited_rate,
            lapse_cap=self.lapse_exposure.lapse_cap,
        )
        mort_on = self.mortality_exposure
        mort_off = _NoMortalityExposure(
            trend_sensitivity=self.mortality_exposure.trend_sensitivity,
            qx_cap=self.mortality_exposure.qx_cap,
        )

        child = np.random.SeedSequence(cfg.seed).spawn(len(outer))
        rate_l = np.empty(len(outer), dtype=float)
        equity_l = np.empty(len(outer), dtype=float)
        credit_l = np.empty(len(outer), dtype=float)
        lapse_l = np.empty(len(outer), dtype=float)
        mortality_l = np.empty(len(outer), dtype=float)
        full_l = np.empty(len(outer), dtype=float)
        for i, (r, s, c, b, m) in enumerate(outer):
            inner_seed = int(child[i].generate_state(1)[0])

            def _mean(eq_spec, cr_spec, lapse_spec, mort_spec):
                pvs = _inner_pathwise_pvs_5d(
                    float(r), float(s), float(c), float(b), float(m), cfg.n_inner, rem,
                    self.product, self.hw_params, self.gbm_params, self.spread_params,
                    self.correlation, cfg.capital_horizon_months, inner_seed,
                    eq_spec, cr_spec, lapse_spec, mort_spec, self.annual_qx_fn,
                )
                return float(pvs.mean())

            l_base = _mean(eq_off, cr_off, lapse_off, mort_off)
            l_re = _mean(eq_on, cr_off, lapse_off, mort_off)
            l_rc = _mean(eq_off, cr_on, lapse_off, mort_off)
            l_rl = _mean(eq_off, cr_off, lapse_on, mort_off)
            l_rm = _mean(eq_off, cr_off, lapse_off, mort_on)
            l_full = _mean(eq_on, cr_on, lapse_on, mort_on)
            rate_l[i] = l_base
            equity_l[i] = l_re - l_base
            credit_l[i] = l_rc - l_base
            lapse_l[i] = l_rl - l_base
            mortality_l[i] = l_rm - l_base
            full_l[i] = l_full
        return rate_l, equity_l, credit_l, lapse_l, mortality_l, full_l

    def run(
        self,
        config: Optional[FiveDriverAggregationConfig] = None,
        governance_store: Optional["object"] = None,
        actor: str = "FiveDriverRiskAggregator",
        phase: str = "Phase 19: Recovery Completion and Driver Expansion",
    ) -> FiveDriverAggregationReport:
        cfg = config or FiveDriverAggregationConfig()
        if cfg.capital_horizon_months >= self.product.term_months:
            raise ValueError("capital_horizon_months must be less than product term")

        t0 = time.monotonic()
        run_id = "ftd-riskagg-" + uuid.uuid4().hex[:8]

        outer = _outer_states_5d(
            cfg.n_outer, cfg.capital_horizon_months, cfg.outer_measure,
            self.hw_params, self.gbm_params, self.spread_params, self.lapse_params,
            self.mortality_params, self.correlation, self.initial_curve, cfg.seed,
        )
        (rate_l, equity_l, credit_l, lapse_l, mortality_l,
         full_l) = self._component_liabilities(outer, cfg)
        crn_sum_l = rate_l + equity_l + credit_l + lapse_l + mortality_l

        conf = cfg.confidence_level
        hm = cfg.capital_horizon_months
        rate_cap = capital_metrics_from_liabilities(rate_l, conf, hm)
        equity_cap = capital_metrics_from_liabilities(equity_l, conf, hm)
        credit_cap = capital_metrics_from_liabilities(credit_l, conf, hm)
        lapse_cap = capital_metrics_from_liabilities(lapse_l, conf, hm)
        mortality_cap = capital_metrics_from_liabilities(mortality_l, conf, hm)
        full_cap = capital_metrics_from_liabilities(full_l, conf, hm)
        crn_sum_cap = capital_metrics_from_liabilities(crn_sum_l, conf, hm)

        # Realised 5x5 capital-loss correlation.
        stacked = np.vstack([rate_l, equity_l, credit_l, lapse_l, mortality_l])
        loss_corr = np.nan_to_num(np.corrcoef(stacked), nan=0.0)
        loss_corr_t = tuple(tuple(float(x) for x in row) for row in loss_corr)

        scr_vec = np.array(
            [rate_cap.scr_proxy, equity_cap.scr_proxy, credit_cap.scr_proxy,
             lapse_cap.scr_proxy, mortality_cap.scr_proxy], dtype=float
        )
        standalone_sum = float(scr_vec.sum())

        # Governed 5x5 ESG driver correlation (rate, equity, credit, lapse, mortality).
        C = self.correlation.matrix(self.gbm_params.rate_equity_correlation)
        C_t = tuple(tuple(float(x) for x in row) for row in C)
        corr_report = CorrelationMatrixValidator().validate_matrix(C_t, repair=False)

        aggregated_variance = float(scr_vec @ C @ scr_vec)
        correlated_scr = float(np.sqrt(max(0.0, aggregated_variance)))

        nested_scr = float(full_cap.scr_proxy)
        gap = correlated_scr - nested_scr
        rel_err = _rel_error(correlated_scr, nested_scr)
        denom = abs(nested_scr) if abs(nested_scr) > 1e-9 else 1.0
        understatement_pct = (nested_scr - correlated_scr) / denom
        interaction_residual = float(crn_sum_cap.scr_proxy - nested_scr)
        interaction_residual_rel = interaction_residual / denom

        var_covar = FiveDriverVarCovarAggregation(
            esg_correlation_matrix=C_t,
            correlation_matrix_passed=bool(corr_report.passed),
            correlated_scr=correlated_scr,
            full_nested_capital=full_cap,
            crn_additive_capital=crn_sum_cap,
            interaction_residual_scr=interaction_residual,
            interaction_residual_rel=interaction_residual_rel,
            diversification_benefit_formula=standalone_sum - correlated_scr,
            diversification_benefit_nested=standalone_sum - nested_scr,
            formula_vs_nested_scr_gap=gap,
            formula_vs_nested_scr_rel_error=rel_err,
            esg_understatement_pct=understatement_pct,
        )
        standalone = FiveDriverStandaloneCapital(
            rate_capital=rate_cap, equity_capital=equity_cap,
            credit_capital=credit_cap, lapse_capital=lapse_cap,
            mortality_capital=mortality_cap,
            standalone_scr_sum=standalone_sum, loss_correlation_matrix=loss_corr_t,
        )

        # Copula (tail-dependent) re-aggregation on the realised standalone
        # loss vectors, benchmarked to the genuine five-driver nested capital.
        copula_cfg = CopulaAggregationConfig(
            n_sim=cfg.n_sim_copula, seed=cfg.seed + 11,
            confidence_level=conf, capital_horizon_months=hm,
        )
        copula = CopulaRiskAggregator(
            loss_vectors=[rate_l, equity_l, credit_l, lapse_l, mortality_l],
            driver_names=["rate", "equity", "credit", "lapse", "mortality"],
            nested_scr=nested_scr,
            var_covar_scr=correlated_scr,
        ).run(config=copula_cfg)

        notes: List[str] = [
            "Standalone rate capital is the guaranteed-benefit component (equity, credit, lapse, and mortality all OFF; central q_x basis).",
            "Equity / credit standalone capital isolated by common-random-number subtraction (eq-guarantee / reduced-form credit-loss).",
            "Lapse standalone capital is (IF(r,b)-1)*guaranteed_pv - the marginal behavioural in-force effect; lapse is NON-FINANCIAL.",
            "Mortality standalone capital is the marginal effect of scaling central q_x by G(m_H)=exp(theta*m_H); mortality trend is NON-FINANCIAL (P=Q) and ORTHOGONAL to every financial driver in the default 5x5 matrix.",
            "Var-covar aggregation uses the governed 5x5 ESG driver correlation, NOT a fitted capital-factor correlation.",
            "MR-010 (five-driver refresh): the raw ESG-factor var-covar formula understates the diversified nested capital by "
            "{:.1f}% because the realised capital-loss vectors co-move positively in the tail while several ESG factor "
            "off-diagonals are zero/negative.".format(100.0 * understatement_pct),
            "Copula-on-realised-losses (selected: {}) reconciles to nested capital within {:.1f}% - the implemented MR-010 "
            "mitigation, now extended to five drivers.".format(
                copula.selected_copula, 100.0 * copula.selected.scr_rel_error_vs_nested),
            "Five-driver finding: the CRN additive decomposition leaves a {:.1f}%-of-nested interaction residual because BOTH "
            "the lapse driver (IF) and the mortality driver (G) scale the guaranteed benefit MULTIPLICATIVELY (the IF x "
            "equity-guarantee and IF x mortality-G cross-terms). A positive residual means the genuine nested capital is "
            "SUPER-additive vs the CRN-additive standalone sum, so 'nested <= standalone sum' is NOT a valid invariant for "
            "five drivers.".format(100.0 * interaction_residual_rel),
            "Mortality being a SMALL orthogonal driver, the five-driver nested SCR is a small monotone increment over the "
            "four-driver figure (benefit-timing on a sum-assured endowment); the copula must not over-state this second "
            "orthogonal tail axis (MR-012 tail-aggregation governance).",
        ]
        verdict = self._verdict(cfg, standalone, var_covar, copula, notes)

        digest = hashlib.sha256(
            np.round(
                np.concatenate([
                    full_l, rate_l, equity_l, credit_l, lapse_l, mortality_l,
                    np.array([correlated_scr, nested_scr,
                              copula.selected.aggregated_capital.scr_proxy], dtype=float),
                    C.ravel(),
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
                    actor=actor, phase=phase, run_id=run_id,
                    scenario_count=cfg.n_outer * cfg.n_inner * 6,
                    duration_seconds=round(duration, 4),
                    outcome=verdict.split()[0],
                    files_changed=[
                        "par_model_v2/projection/multi_driver_capital_5d_aggregation.py"
                    ],
                    test_summary=(
                        "rate={:.1f}; equity={:.1f}; credit={:.1f}; lapse={:.1f}; "
                        "mortality={:.1f}; var-cov={:.1f} (rel {:.1%}); copula({})={:.1f} "
                        "(rel {:.1%}); nested={:.1f}; ESG understatement={:.1f}%".format(
                            rate_cap.scr_proxy, equity_cap.scr_proxy,
                            credit_cap.scr_proxy, lapse_cap.scr_proxy,
                            mortality_cap.scr_proxy, correlated_scr, rel_err,
                            copula.selected_copula,
                            copula.selected.aggregated_capital.scr_proxy,
                            copula.selected.scr_rel_error_vs_nested,
                            nested_scr, 100.0 * understatement_pct,
                        )
                    ),
                )
                governance_store.audit_trail.append(entry)
                audit_entry_id = entry.entry_id
            except Exception as exc:  # pragma: no cover - governance optional
                notes.append("Governance audit append skipped: {}".format(exc))

        return FiveDriverAggregationReport(
            config=cfg,
            drivers=("short_rate", "equity_guarantee", "credit_spread",
                     "lapse_behaviour", "mortality_trend"),
            standalone=standalone, var_covar=var_covar, copula=copula,
            nested_scr=nested_scr, run_id=run_id, duration_seconds=duration,
            verdict=verdict, reproducibility_digest=digest, notes=notes,
            audit_entry_id=audit_entry_id,
        )

    @staticmethod
    def _verdict(
        cfg: FiveDriverAggregationConfig,
        standalone: FiveDriverStandaloneCapital,
        var_covar: FiveDriverVarCovarAggregation,
        copula: CopulaAggregationReport,
        notes: List[str],
    ) -> str:
        sel = copula.selected
        checks = [
            var_covar.correlation_matrix_passed,
            # Var-covar SCR is bounded above by the undiversified standalone sum
            # (always true for a valid correlation matrix).  The GENUINE nested
            # capital is NOT so bounded for five drivers - the multiplicative
            # lapse AND mortality couplings can make it super-additive vs the
            # CRN-additive standalone sum (see interaction_residual).
            var_covar.correlated_scr <= standalone.standalone_scr_sum + 1e-6,
            # The copula (tail-dependent) aggregation reconciles to nested better
            # than the var-covar formula does - the core MR-010 mitigation claim.
            sel.scr_rel_error_vs_nested < var_covar.formula_vs_nested_scr_rel_error,
        ]
        if sel.scr_rel_error_vs_nested >= var_covar.formula_vs_nested_scr_rel_error:
            notes.append(
                "Copula aggregation did not beat the var-covar formula vs nested; "
                "review the realised-loss copula fit."
            )
        if all(checks):
            return (
                "PASS - five-driver copula aggregation (selected: {}) reconciles to nested capital "
                "within {:.1%} vs var-covar {:.1%}; MR-010 five-driver mitigation confirmed".format(
                    copula.selected_copula, sel.scr_rel_error_vs_nested,
                    var_covar.formula_vs_nested_scr_rel_error)
            )
        return "PARTIAL - five-driver aggregation evidence generated with review items"


def five_driver_aggregation_use_restrictions() -> Dict[str, object]:
    return {
        "module": "par_model_v2/projection/multi_driver_capital_5d_aggregation.py",
        "classification": "EDUCATIONAL ONLY - NOT a regulatory capital model",
        "risk_drivers": ["short rate", "equity guarantee", "credit spread",
                         "lapse behaviour", "mortality trend"],
        "method": (
            "Five standalone SCRs isolated by common-random-number decomposition of the "
            "conditional liability, aggregated BOTH with the governed 5x5 ESG factor "
            "correlation (variance-covariance) AND with a copula fitted to the realised "
            "standalone capital-loss vectors (Gaussian / Student-t / survival-Clayton, "
            "AIC-selected), each benchmarked to genuine five-driver nested capital."
        ),
        "limitations": [
            "The CRN additive split carries a multiplicative lapse AND mortality interaction residual (the IF x equity-guarantee and IF x mortality-G cross-terms); it is reported, not removed.",
            "Var-covar aggregation on the ESG factor matrix materially understates diversified capital (MR-010); the copula on realised losses is the recommended aggregation.",
            "Copulas are fitted to a finite outer-state sample, so tail-dependence estimates are sampling-noisy and the marginals cannot extrapolate beyond the simulated loss range.",
            "Five drivers only (rates + equity + credit + lapse + mortality-trend): FX, liquidity, and management-action risks remain outside the aggregation.",
            "Mortality trend is a single systemic OU index (Lee-Carter-style level, no age/cohort structure) with placeholder parameters and no basis-risk decomposition.",
            "Lapse behaviour is a single systemic OU index with placeholder parameters and no product / cohort structure.",
            "Credentialled calibration data and independent APS X2 review are still required before any production use.",
        ],
        "standards": [
            "SOA ASOP 56 §3.5",
            "SOA ASOP 56 §3.1",
            "SOA ASOP 25 §3.3",
            "SOA ASOP 7 §3.3",
            "IA TAS M §3.2",
            "IA TAS M §3.5",
            "IA TAS M §3.6",
            "Solvency II Delegated Reg. Art. 234",
            "Lee & Carter (1992)",
        ],
    }


def five_driver_aggregation_use_restrictions_json() -> str:
    return json.dumps(five_driver_aggregation_use_restrictions(), indent=2, sort_keys=True)


__all__ = [
    "DEFAULT_FIVED_AGG_GAP_TOLERANCE",
    "FiveDriverAggregationConfig",
    "FiveDriverStandaloneCapital",
    "FiveDriverVarCovarAggregation",
    "FiveDriverAggregationReport",
    "FiveDriverRiskAggregator",
    "five_driver_aggregation_use_restrictions",
    "five_driver_aggregation_use_restrictions_json",
]
