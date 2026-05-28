"""
Calibration Backtesting Framework
=================================

Implements the Phase 4 backtesting dataset and historical replay framework
referenced in docs/PARAMETER_CALIBRATION_METHODOLOGY.md §9.4.

Scope
-----
1. Development-safe synthetic backtesting dataset generation
2. Historical replay of 1-year P-measure rate/equity distributions
3. Coverage-band checks for realised rate and equity outcomes
4. VaR breach tracking with Kupiec proportion-of-failures p-values
5. Q-measure martingale validation hook for governance traceability

This module does NOT claim production-ready historical calibration because the
workspace currently lacks external CNY yield-curve and CSI 300 files. The
synthetic dataset generator is an explicit development scaffold until real
market histories are connected in a later cycle.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Dict, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
from scipy import stats as scipy_stats

from par_model_v2.calibration.calibration_framework import CalibrationResult, martingale_test
from par_model_v2.governance.audit_trail import AuditEntry, GovernanceStore
from par_model_v2.risk.risk_metrics import ConfidenceLevel, LossDistribution, RiskMetrics
from par_model_v2.stochastic.esg_process import GBMParams, HullWhiteParams, Measure, ScenarioSet


BACKTEST_HORIZON_MONTHS = 12
BACKTEST_RATE_BAND = (0.10, 0.90)
BACKTEST_MIN_COVERAGE = 0.70
BACKTEST_VAR99_BREACH_LIMIT = 0.05
BACKTEST_DEFAULT_GUARANTEE_NOTIONAL = 1_000_000.0
BACKTEST_DEFAULT_EQUITY_WEIGHT = 0.35
BACKTEST_DEFAULT_DURATION_YEARS = 5.0


def _loss_from_market_outcome(
    realised_rate: np.ndarray | float,
    realised_equity_return: np.ndarray | float,
    deterministic_discount_rate: float,
    guarantee_notional: float,
    equity_weight: float,
    duration_years: float,
) -> np.ndarray | float:
    """Translate rate/equity outcomes into a simple annual loss proxy."""
    rate_shortfall = np.maximum(0.0, deterministic_discount_rate - realised_rate)
    rate_loss = guarantee_notional * duration_years * rate_shortfall

    equity_shortfall = np.maximum(0.0, -realised_equity_return)
    equity_loss = guarantee_notional * equity_weight * equity_shortfall

    diversification_credit = 0.10 * np.minimum(rate_loss, equity_loss)
    return rate_loss + equity_loss - diversification_credit


def _kupiec_pof_pvalue(
    n_exceptions: int,
    n_observations: int,
    confidence_level: ConfidenceLevel,
) -> float:
    """Return Kupiec POF p-value for a VaR exception count."""
    if n_observations <= 0:
        raise ValueError("n_observations must be positive")
    if not (0 <= n_exceptions <= n_observations):
        raise ValueError("n_exceptions must be between 0 and n_observations")

    tail_prob = 1.0 - float(confidence_level.value)
    observed_prob = n_exceptions / n_observations

    log_l_null = 0.0
    if n_observations > n_exceptions:
        log_l_null += (n_observations - n_exceptions) * np.log(1.0 - tail_prob)
    if n_exceptions > 0:
        log_l_null += n_exceptions * np.log(tail_prob)

    log_l_alt = 0.0
    if n_observations > n_exceptions and observed_prob < 1.0:
        log_l_alt += (n_observations - n_exceptions) * np.log(1.0 - observed_prob)
    if n_exceptions > 0 and observed_prob > 0.0:
        log_l_alt += n_exceptions * np.log(observed_prob)

    lr_stat = max(0.0, -2.0 * (log_l_null - log_l_alt))
    return float(scipy_stats.chi2.sf(lr_stat, df=1))


@dataclass
class BacktestDataset:
    """Container for annual realised observations used by the backtest engine."""

    observations: pd.DataFrame
    horizon_months: int = BACKTEST_HORIZON_MONTHS

    REQUIRED_COLUMNS = (
        "observation_date",
        "initial_short_rate",
        "initial_equity_index",
        "realised_rate_1y",
        "realised_equity_return_1y",
        "realised_loss",
    )

    def __post_init__(self) -> None:
        missing = [col for col in self.REQUIRED_COLUMNS if col not in self.observations.columns]
        if missing:
            raise ValueError(f"BacktestDataset missing required columns: {missing}")
        if self.horizon_months <= 0:
            raise ValueError("horizon_months must be positive")

        obs = self.observations.copy()
        obs["observation_date"] = pd.to_datetime(obs["observation_date"])
        obs = obs.sort_values("observation_date").reset_index(drop=True)

        numeric_cols = [col for col in self.REQUIRED_COLUMNS if col != "observation_date"]
        obs[numeric_cols] = obs[numeric_cols].astype(float)
        self.observations = obs

    @property
    def n_observations(self) -> int:
        return len(self.observations)

    @classmethod
    def synthetic(
        cls,
        calibration_result: CalibrationResult,
        n_observations: int = 10,
        seed: int = 42,
        start_date: Optional[date] = None,
        deterministic_discount_rate: float = 0.035,
        guarantee_notional: float = BACKTEST_DEFAULT_GUARANTEE_NOTIONAL,
        equity_weight: float = BACKTEST_DEFAULT_EQUITY_WEIGHT,
        duration_years: float = BACKTEST_DEFAULT_DURATION_YEARS,
    ) -> "BacktestDataset":
        """Build a rolling annual synthetic history from the calibrated ESG."""
        if n_observations <= 0:
            raise ValueError("n_observations must be positive")

        start_date = start_date or calibration_result.calibration_date
        current_short_rate = calibration_result.r0
        current_equity_index = 100.0

        records = []
        for idx in range(n_observations):
            observation_date = pd.Timestamp(start_date) + pd.DateOffset(years=idx + 1)

            hw_params = HullWhiteParams(
                mean_reversion_speed=calibration_result.a,
                short_rate_vol=calibration_result.sigma_r,
                initial_short_rate=current_short_rate,
                long_run_rate_p=current_short_rate + calibration_result.lambda_r,
                market_price_of_risk=calibration_result.lambda_r,
            )
            gbm_params = GBMParams(
                equity_vol=calibration_result.sigma_S,
                dividend_yield=calibration_result.dividend_yield,
                equity_risk_premium=calibration_result.erp,
                rate_equity_correlation=calibration_result.rho,
                initial_index_level=current_equity_index,
            )
            scenario_set = ScenarioSet.generate(
                n=1,
                T_months=BACKTEST_HORIZON_MONTHS,
                measure=Measure.P,
                hw_params=hw_params,
                gbm_params=gbm_params,
                seed=seed + idx,
            )
            path = scenario_set.path(1)
            terminal = path[path["month"] == BACKTEST_HORIZON_MONTHS].iloc[0]

            realised_rate = float(terminal["r_short"])
            realised_equity_index = float(terminal["equity_index"])
            realised_equity_return = realised_equity_index / current_equity_index - 1.0
            realised_loss = float(
                _loss_from_market_outcome(
                    realised_rate=realised_rate,
                    realised_equity_return=realised_equity_return,
                    deterministic_discount_rate=deterministic_discount_rate,
                    guarantee_notional=guarantee_notional,
                    equity_weight=equity_weight,
                    duration_years=duration_years,
                )
            )

            records.append(
                {
                    "observation_date": observation_date,
                    "initial_short_rate": current_short_rate,
                    "initial_equity_index": current_equity_index,
                    "realised_rate_1y": realised_rate,
                    "realised_equity_return_1y": realised_equity_return,
                    "realised_loss": realised_loss,
                }
            )

            current_short_rate = realised_rate
            current_equity_index = realised_equity_index

        return cls(pd.DataFrame.from_records(records), horizon_months=BACKTEST_HORIZON_MONTHS)


@dataclass
class BacktestResult:
    """Summary of a historical replay backtest run."""

    detail: pd.DataFrame
    rate_coverage_pct: float
    equity_coverage_pct: float
    var95_exception_rate: float
    var99_exception_rate: float
    es95_mean: float
    es99_mean: float
    kupiec_pvalue_95: float
    kupiec_pvalue_99: float
    martingale_results: pd.DataFrame
    requires_recalibration: bool
    run_id: str
    audit_entry_id: Optional[str] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(tz=timezone.utc))

    def summary(self) -> Dict[str, float | bool | str]:
        return {
            "run_id": self.run_id,
            "rate_coverage_pct": self.rate_coverage_pct,
            "equity_coverage_pct": self.equity_coverage_pct,
            "var95_exception_rate": self.var95_exception_rate,
            "var99_exception_rate": self.var99_exception_rate,
            "es95_mean": self.es95_mean,
            "es99_mean": self.es99_mean,
            "kupiec_pvalue_95": self.kupiec_pvalue_95,
            "kupiec_pvalue_99": self.kupiec_pvalue_99,
            "martingale_all_pass": bool(self.martingale_results.attrs.get("all_pass", False)),
            "requires_recalibration": self.requires_recalibration,
            "audit_entry_id": self.audit_entry_id,
            "created_at": self.created_at.isoformat(),
        }

    def worst_observation(self) -> Dict[str, float | str | bool]:
        """Return the observation with the largest realised loss."""
        if self.detail.empty:
            raise ValueError("BacktestResult.detail must not be empty")

        row = self.detail.sort_values("realised_loss", ascending=False).iloc[0]
        return {
            "observation_date": pd.Timestamp(row["observation_date"]).date().isoformat(),
            "realised_loss": float(row["realised_loss"]),
            "var95": float(row["var95"]),
            "es95": float(row["es95"]),
            "var99": float(row["var99"]),
            "es99": float(row["es99"]),
            "var95_breach": bool(row["var95_breach"]),
            "var99_breach": bool(row["var99_breach"]),
        }

    def tail_summary(self) -> Dict[str, float]:
        """Aggregate tail-loss diagnostics used by the reporting layer."""
        if self.detail.empty:
            raise ValueError("BacktestResult.detail must not be empty")

        var95_excess = np.maximum(0.0, self.detail["realised_loss"] - self.detail["var95"])
        var99_excess = np.maximum(0.0, self.detail["realised_loss"] - self.detail["var99"])
        avg_var95_breach = float(
            self.detail.loc[self.detail["var95_breach"], "realised_loss"].mean()
        ) if bool(self.detail["var95_breach"].any()) else 0.0
        avg_var99_breach = float(
            self.detail.loc[self.detail["var99_breach"], "realised_loss"].mean()
        ) if bool(self.detail["var99_breach"].any()) else 0.0

        return {
            "mean_var95": float(self.detail["var95"].mean()),
            "mean_es95": float(self.detail["es95"].mean()),
            "mean_var99": float(self.detail["var99"].mean()),
            "mean_es99": float(self.detail["es99"].mean()),
            "mean_var95_excess": float(var95_excess.mean()),
            "mean_var99_excess": float(var99_excess.mean()),
            "max_var95_excess": float(var95_excess.max()),
            "max_var99_excess": float(var99_excess.max()),
            "avg_realised_loss_var95_breach": avg_var95_breach,
            "avg_realised_loss_var99_breach": avg_var99_breach,
        }


class BacktestEngine:
    """Run 1-year historical replay backtests from annual realised observations."""

    def __init__(
        self,
        calibration_result: CalibrationResult,
        governance_store: Optional[GovernanceStore] = None,
        actor: str = "Claude Actuarial Agent",
        deterministic_discount_rate: float = 0.035,
        guarantee_notional: float = BACKTEST_DEFAULT_GUARANTEE_NOTIONAL,
        equity_weight: float = BACKTEST_DEFAULT_EQUITY_WEIGHT,
        duration_years: float = BACKTEST_DEFAULT_DURATION_YEARS,
    ) -> None:
        self.calibration_result = calibration_result
        self.governance_store = governance_store
        self.actor = actor
        self.deterministic_discount_rate = deterministic_discount_rate
        self.guarantee_notional = guarantee_notional
        self.equity_weight = equity_weight
        self.duration_years = duration_years

    def _hw_params(self, initial_short_rate: float) -> HullWhiteParams:
        return HullWhiteParams(
            mean_reversion_speed=self.calibration_result.a,
            short_rate_vol=self.calibration_result.sigma_r,
            initial_short_rate=initial_short_rate,
            long_run_rate_p=initial_short_rate + self.calibration_result.lambda_r,
            market_price_of_risk=self.calibration_result.lambda_r,
        )

    def _gbm_params(self, initial_equity_index: float) -> GBMParams:
        return GBMParams(
            equity_vol=self.calibration_result.sigma_S,
            dividend_yield=self.calibration_result.dividend_yield,
            equity_risk_premium=self.calibration_result.erp,
            rate_equity_correlation=self.calibration_result.rho,
            initial_index_level=initial_equity_index,
        )

    def _scenario_losses(self, terminal_rates: np.ndarray, annual_returns: np.ndarray) -> np.ndarray:
        return np.asarray(
            _loss_from_market_outcome(
                realised_rate=terminal_rates,
                realised_equity_return=annual_returns,
                deterministic_discount_rate=self.deterministic_discount_rate,
                guarantee_notional=self.guarantee_notional,
                equity_weight=self.equity_weight,
                duration_years=self.duration_years,
            ),
            dtype=float,
        )

    def run(
        self,
        dataset: BacktestDataset,
        n_scenarios: int = 1000,
        rate_band: Tuple[float, float] = BACKTEST_RATE_BAND,
        seed: int = 42,
    ) -> BacktestResult:
        if dataset.horizon_months != BACKTEST_HORIZON_MONTHS:
            raise ValueError(
                f"BacktestEngine requires a {BACKTEST_HORIZON_MONTHS}-month horizon; "
                f"got {dataset.horizon_months}"
            )
        if n_scenarios < 100:
            raise ValueError("n_scenarios must be at least 100 for stable backtesting")

        lower_q, upper_q = rate_band
        if not (0.0 < lower_q < upper_q < 1.0):
            raise ValueError("rate_band must satisfy 0 < lower < upper < 1")

        run_id = f"backtest-{uuid.uuid4().hex[:12]}"
        detail_rows = []

        for idx, observation in dataset.observations.iterrows():
            scenario_set = ScenarioSet.generate(
                n=n_scenarios,
                T_months=dataset.horizon_months,
                measure=Measure.P,
                hw_params=self._hw_params(float(observation["initial_short_rate"])),
                gbm_params=self._gbm_params(float(observation["initial_equity_index"])),
                seed=seed + idx,
            )
            terminal = scenario_set.data[scenario_set.data["month"] == dataset.horizon_months].copy()
            terminal_rates = terminal["r_short"].to_numpy(dtype=float)
            terminal_equity = terminal["equity_index"].to_numpy(dtype=float)
            annual_returns = terminal_equity / float(observation["initial_equity_index"]) - 1.0

            rate_p10, rate_p90 = np.quantile(terminal_rates, [lower_q, upper_q])
            equity_p10, equity_p90 = np.quantile(annual_returns, [lower_q, upper_q])

            scenario_losses = self._scenario_losses(terminal_rates, annual_returns)
            risk = RiskMetrics(
                LossDistribution.from_array(
                    scenario_losses,
                    label="Backtest annual loss distribution",
                    measure="P",
                    unit="CNY",
                )
            )
            var95 = risk.empirical_var(ConfidenceLevel.CL_95).var_value
            var99 = risk.empirical_var(ConfidenceLevel.CL_99).var_value
            es95 = risk.empirical_es(ConfidenceLevel.CL_95).es_value
            es99 = risk.empirical_es(ConfidenceLevel.CL_99).es_value

            realised_rate = float(observation["realised_rate_1y"])
            realised_equity_return = float(observation["realised_equity_return_1y"])
            realised_loss = float(observation["realised_loss"])

            detail_rows.append(
                {
                    "observation_date": observation["observation_date"],
                    "realised_rate_1y": realised_rate,
                    "rate_p10": float(rate_p10),
                    "rate_p90": float(rate_p90),
                    "rate_in_band": bool(rate_p10 <= realised_rate <= rate_p90),
                    "realised_equity_return_1y": realised_equity_return,
                    "equity_return_p10": float(equity_p10),
                    "equity_return_p90": float(equity_p90),
                    "equity_in_band": bool(equity_p10 <= realised_equity_return <= equity_p90),
                    "realised_loss": realised_loss,
                    "var95": float(var95),
                    "var99": float(var99),
                    "es95": float(es95),
                    "es99": float(es99),
                    "var95_breach": bool(realised_loss > var95),
                    "var99_breach": bool(realised_loss > var99),
                    "var95_excess": float(max(0.0, realised_loss - var95)),
                    "var99_excess": float(max(0.0, realised_loss - var99)),
                }
            )

        detail = pd.DataFrame(detail_rows)

        rate_coverage_pct = float(detail["rate_in_band"].mean())
        equity_coverage_pct = float(detail["equity_in_band"].mean())
        var95_exception_rate = float(detail["var95_breach"].mean())
        var99_exception_rate = float(detail["var99_breach"].mean())
        es95_mean = float(detail["es95"].mean())
        es99_mean = float(detail["es99"].mean())

        kupiec_pvalue_95 = _kupiec_pof_pvalue(
            int(detail["var95_breach"].sum()),
            len(detail),
            ConfidenceLevel.CL_95,
        )
        kupiec_pvalue_99 = _kupiec_pof_pvalue(
            int(detail["var99_breach"].sum()),
            len(detail),
            ConfidenceLevel.CL_99,
        )

        martingale_scenarios = ScenarioSet.generate(
            n=max(500, min(2000, n_scenarios)),
            T_months=12,
            measure=Measure.Q,
            hw_params=self._hw_params(self.calibration_result.r0),
            gbm_params=self._gbm_params(100.0),
            seed=seed + 50_000,
        )
        martingale_results = martingale_test(
            martingale_scenarios,
            horizons_years=(1.0,),
            tolerance=0.005,
            initial_equity_price=100.0,
            dividend_yield=self.calibration_result.dividend_yield,
        )

        requires_recalibration = bool(
            rate_coverage_pct < BACKTEST_MIN_COVERAGE
            or equity_coverage_pct < BACKTEST_MIN_COVERAGE
            or var99_exception_rate > BACKTEST_VAR99_BREACH_LIMIT
            or not bool(martingale_results.attrs.get("all_pass", False))
        )

        audit_entry_id = None
        if self.governance_store is not None:
            model_run_entry = AuditEntry.model_run(
                actor=self.actor,
                phase="Phase 4: Calibration & Backtesting",
                run_id=run_id,
                scenario_count=len(detail) * n_scenarios,
                duration_seconds=0.0,
                outcome="PASS" if not requires_recalibration else "REVIEW_REQUIRED",
                files_changed=["par_model_v2/calibration/backtesting.py"],
                test_summary=(
                    f"rate_cov={rate_coverage_pct:.1%}, equity_cov={equity_coverage_pct:.1%}, "
                    f"var99_breach={var99_exception_rate:.1%}"
                ),
            )
            validation_entry = AuditEntry.validation(
                actor=self.actor,
                phase="Phase 4: Calibration & Backtesting",
                test_suite="HistoricalBacktest",
                tests_run=5,
                tests_passed=sum(
                    [
                        rate_coverage_pct >= BACKTEST_MIN_COVERAGE,
                        equity_coverage_pct >= BACKTEST_MIN_COVERAGE,
                        var95_exception_rate <= 0.10,
                        var99_exception_rate <= BACKTEST_VAR99_BREACH_LIMIT,
                        bool(martingale_results.attrs.get("all_pass", False)),
                    ]
                ),
                tests_failed=sum(
                    [
                        rate_coverage_pct < BACKTEST_MIN_COVERAGE,
                        equity_coverage_pct < BACKTEST_MIN_COVERAGE,
                        var95_exception_rate > 0.10,
                        var99_exception_rate > BACKTEST_VAR99_BREACH_LIMIT,
                        not bool(martingale_results.attrs.get("all_pass", False)),
                    ]
                ),
                outcome="PASS" if not requires_recalibration else "REVIEW_REQUIRED",
                failed_tests=[
                    label
                    for label, failed in (
                        ("rate_band_coverage", rate_coverage_pct < BACKTEST_MIN_COVERAGE),
                        ("equity_band_coverage", equity_coverage_pct < BACKTEST_MIN_COVERAGE),
                        ("var95_exception_rate", var95_exception_rate > 0.10),
                        ("var99_exception_rate", var99_exception_rate > BACKTEST_VAR99_BREACH_LIMIT),
                        ("martingale_test", not bool(martingale_results.attrs.get("all_pass", False))),
                    )
                    if failed
                ],
            )
            self.governance_store.audit_trail.append(model_run_entry)
            self.governance_store.audit_trail.append(validation_entry)
            audit_entry_id = validation_entry.entry_id

        return BacktestResult(
            detail=detail,
            rate_coverage_pct=rate_coverage_pct,
            equity_coverage_pct=equity_coverage_pct,
            var95_exception_rate=var95_exception_rate,
            var99_exception_rate=var99_exception_rate,
            es95_mean=es95_mean,
            es99_mean=es99_mean,
            kupiec_pvalue_95=kupiec_pvalue_95,
            kupiec_pvalue_99=kupiec_pvalue_99,
            martingale_results=martingale_results,
            requires_recalibration=requires_recalibration,
            run_id=run_id,
            audit_entry_id=audit_entry_id,
        )


__all__ = [
    "BACKTEST_DEFAULT_DURATION_YEARS",
    "BACKTEST_DEFAULT_EQUITY_WEIGHT",
    "BACKTEST_DEFAULT_GUARANTEE_NOTIONAL",
    "BACKTEST_HORIZON_MONTHS",
    "BACKTEST_MIN_COVERAGE",
    "BACKTEST_RATE_BAND",
    "BACKTEST_VAR99_BREACH_LIMIT",
    "BacktestDataset",
    "BacktestEngine",
    "BacktestResult",
    "_kupiec_pof_pvalue",
    "_loss_from_market_outcome",
]
