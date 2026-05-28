"""
Risk Metrics — Value at Risk (VaR) and Expected Shortfall (ES)
==============================================================

Implements tail risk metrics required by:
  - SOA ASOP 7  §3.3  — scenario-based tail risk measurement
  - SOA ASOP 56 §3.5  — scenario adequacy for tail-sensitive metrics
  - ERM Framework     — VaR and ES at 99.5% for solvency margin estimation

Supports two estimation methods:
  1. Empirical (non-parametric) — direct order-statistics from scenario output
  2. Parametric (Normal)        — closed-form; suitable only when loss ≈ Normal

Confidence levels supported:
  - 95.0%  (VaR_95 / ES_95)  — standard risk monitoring
  - 99.0%  (VaR_99 / ES_99)  — internal capital / ERM reporting
  - 99.5%  (VaR_995 / ES_995) — regulatory solvency (Solvency II, CBIRC C-ROSS)

LOSS SIGN CONVENTION
---------------------
All methods expect a **loss** array where POSITIVE values represent losses
(cash outflows to the insurer, or PV of liabilities exceeding assets).
If your model outputs profit, negate before passing in.

P / Q MEASURE NOTE
-------------------
  - VaR / ES should be computed on Measure.P (real-world) scenarios for ERM,
    capital, and solvency purposes.
  - Do NOT mix Q-measure (risk-neutral) paths with VaR/ES — this is a critical
    actuarial error.  See esg_process.py and ESG_PROCESS_DOCUMENTATION.md §2.2.

SCENARIO COUNT REQUIREMENTS (ASOP 56 §3.5)
-------------------------------------------
  - VaR 95.0%  : minimum 500  recommended 1,000
  - VaR 99.0%  : minimum 1,000 recommended 5,000
  - VaR 99.5%  : minimum 2,000 recommended 10,000
  Fewer scenarios produce unreliable tail estimates — flag in report.

DEVELOPMENT STATUS
------------------
Phase 2: Module implemented; integration with ScenarioSet deferred to Phase 4
         when ESG simulation (esg_process.py) is fully implemented.
         Deterministic stress-shifted inputs are supported now for testing.

PRODUCTION USE RESTRICTION
---------------------------
Placeholder ESG parameters in Phase 2/3 will produce unreliable tail estimates.
Do not use for regulatory reporting until Phase 4 calibration is complete.
"""

from __future__ import annotations

import enum
import warnings
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
from scipy import stats as scipy_stats


# ---------------------------------------------------------------------------
# 0. Confidence Level Enum
# ---------------------------------------------------------------------------

class ConfidenceLevel(float, enum.Enum):
    """Standard actuarial confidence levels for VaR / ES.

    Attributes
    ----------
    CL_95 : float
        95.0% — standard risk monitoring and internal reporting.
    CL_99 : float
        99.0% — internal capital / ERM reporting (common UK / EU standard).
    CL_995 : float
        99.5% — regulatory solvency (Solvency II, CBIRC C-ROSS equivalent).
    """

    CL_95 = 0.95
    CL_99 = 0.99
    CL_995 = 0.995

    @property
    def label(self) -> str:
        """Human-readable label, e.g. '99.5%'."""
        return f"{self.value * 100:.1f}%"

    @property
    def min_scenarios(self) -> int:
        """Minimum recommended scenario count (ASOP 56 §3.5)."""
        if self.value >= 0.995:
            return 2000
        elif self.value >= 0.99:
            return 1000
        else:
            return 500

    @property
    def recommended_scenarios(self) -> int:
        """Recommended scenario count (ASOP 56 §3.5)."""
        if self.value >= 0.995:
            return 10000
        elif self.value >= 0.99:
            return 5000
        else:
            return 1000


ALL_CONFIDENCE_LEVELS = [
    ConfidenceLevel.CL_95,
    ConfidenceLevel.CL_99,
    ConfidenceLevel.CL_995,
]


# ---------------------------------------------------------------------------
# 1. Result Dataclasses
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class VaRResult:
    """Value at Risk at a given confidence level.

    Attributes
    ----------
    confidence_level : ConfidenceLevel
        Confidence level α (e.g. 99.5%).
    var_value : float
        VaR(α) — the loss that is not exceeded in α% of scenarios.
        Positive = loss; negative = gain in the α-th worst case.
    method : str
        'empirical' or 'parametric'.
    scenario_count : int
        Number of scenarios used.
    is_reliable : bool
        False if scenario_count < confidence_level.min_scenarios.
        Unreliable estimates should not be used for regulatory purposes.
    reliability_warning : str
        Human-readable warning if is_reliable is False.

    SOA Reference
    -------------
    ASOP 7 §3.3 — scenario-based tail risk measurement.
    ASOP 56 §3.5 — scenario count adequacy.
    """

    confidence_level: ConfidenceLevel
    var_value: float
    method: str
    scenario_count: int

    @property
    def is_reliable(self) -> bool:
        return self.scenario_count >= self.confidence_level.min_scenarios

    @property
    def reliability_warning(self) -> str:
        if self.is_reliable:
            return ""
        return (
            f"VaR {self.confidence_level.label}: only {self.scenario_count} scenarios — "
            f"minimum {self.confidence_level.min_scenarios} required (ASOP 56 §3.5). "
            f"Estimate is unreliable for regulatory use."
        )

    def as_dict(self) -> dict:
        return {
            "metric": "VaR",
            "confidence_level": self.confidence_level.label,
            "value": self.var_value,
            "method": self.method,
            "n_scenarios": self.scenario_count,
            "is_reliable": self.is_reliable,
            "reliability_warning": self.reliability_warning,
        }


@dataclass(frozen=True)
class ESResult:
    """Expected Shortfall (Conditional VaR / Tail-VaR) at a given confidence level.

    ES(α) = E[Loss | Loss > VaR(α)]
    Average of losses exceeding the VaR threshold.
    ES is always >= VaR(α) and is a coherent risk measure (Artzner et al.).

    Attributes
    ----------
    confidence_level : ConfidenceLevel
        Confidence level α.
    es_value : float
        ES(α) — expected loss conditional on exceeding VaR(α).
    var_value : float
        The VaR(α) used as the threshold.
    tail_count : int
        Number of tail scenarios contributing to the ES average.
    method : str
        'empirical' or 'parametric'.
    scenario_count : int
        Total number of scenarios.
    is_reliable : bool
        False if tail_count < 30 (insufficient for stable tail average).

    SOA Reference
    -------------
    ASOP 7 §3.3 — coherent tail risk measurement.
    ERM Framework — ES as preferred metric over VaR for capital purposes.
    """

    confidence_level: ConfidenceLevel
    es_value: float
    var_value: float
    tail_count: int
    method: str
    scenario_count: int

    @property
    def is_reliable(self) -> bool:
        # Require at least 30 tail scenarios for stable average (CLT basis)
        return self.tail_count >= 30 and self.scenario_count >= self.confidence_level.min_scenarios

    @property
    def reliability_warning(self) -> str:
        warnings_list = []
        if self.scenario_count < self.confidence_level.min_scenarios:
            warnings_list.append(
                f"total scenarios {self.scenario_count} < minimum "
                f"{self.confidence_level.min_scenarios} (ASOP 56 §3.5)"
            )
        if self.tail_count < 30:
            warnings_list.append(
                f"tail scenarios {self.tail_count} < 30 — ES average is unstable"
            )
        if warnings_list:
            return (
                f"ES {self.confidence_level.label}: " + "; ".join(warnings_list) +
                ". Not suitable for regulatory use."
            )
        return ""

    def as_dict(self) -> dict:
        return {
            "metric": "ES",
            "confidence_level": self.confidence_level.label,
            "value": self.es_value,
            "var_threshold": self.var_value,
            "tail_scenarios": self.tail_count,
            "method": self.method,
            "n_scenarios": self.scenario_count,
            "is_reliable": self.is_reliable,
            "reliability_warning": self.reliability_warning,
        }


@dataclass
class RiskReport:
    """Consolidated VaR and ES report across all confidence levels.

    Attributes
    ----------
    var_results : dict[ConfidenceLevel, VaRResult]
    es_results  : dict[ConfidenceLevel, ESResult]
    loss_summary : pd.Series
        Descriptive statistics of the loss distribution.
    generated_at : str
        ISO 8601 UTC timestamp.
    measure_note : str
        Reminder of the measure used (must be Measure.P for ERM purposes).

    Methods
    -------
    to_dataframe() → pd.DataFrame
        Tabular view of all VaR and ES results.
    print_summary()
        Console-formatted summary for quick review.
    """

    var_results: Dict[ConfidenceLevel, VaRResult]
    es_results: Dict[ConfidenceLevel, ESResult]
    loss_summary: pd.Series
    generated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    measure_note: str = (
        "IMPORTANT: ERM VaR/ES must use Measure.P (real-world) scenarios. "
        "Q-measure (risk-neutral) paths produce economically incorrect tail metrics."
    )

    def to_dataframe(self) -> pd.DataFrame:
        """Return all results as a tidy DataFrame."""
        rows = []
        for cl in ALL_CONFIDENCE_LEVELS:
            if cl in self.var_results:
                rows.append(self.var_results[cl].as_dict())
            if cl in self.es_results:
                rows.append(self.es_results[cl].as_dict())
        return pd.DataFrame(rows)

    def print_summary(self) -> None:
        """Print a formatted summary to stdout."""
        print("=" * 65)
        print("RISK METRICS REPORT — VAR / ES")
        print(f"Generated: {self.generated_at}")
        print("-" * 65)
        print("LOSS DISTRIBUTION SUMMARY")
        print(self.loss_summary.to_string())
        print("-" * 65)
        print(f"{'Metric':<8} {'CL':>6}  {'Value':>12}  {'Reliable':<10}  Note")
        print("-" * 65)
        for cl in ALL_CONFIDENCE_LEVELS:
            if cl in self.var_results:
                r = self.var_results[cl]
                flag = "✓" if r.is_reliable else "⚠ UNRELIABLE"
                print(f"{'VaR':<8} {cl.label:>6}  {r.var_value:>12,.2f}  {flag:<10}  {r.reliability_warning[:40]}")
            if cl in self.es_results:
                r = self.es_results[cl]
                flag = "✓" if r.is_reliable else "⚠ UNRELIABLE"
                print(f"{'ES':<8} {cl.label:>6}  {r.es_value:>12,.2f}  {flag:<10}  {r.reliability_warning[:40]}")
        print("-" * 65)
        print(f"NOTE: {self.measure_note}")
        print("=" * 65)


# ---------------------------------------------------------------------------
# 2. LossDistribution — input container
# ---------------------------------------------------------------------------

@dataclass
class LossDistribution:
    """Container for a loss distribution derived from scenario simulation.

    Attributes
    ----------
    losses : np.ndarray
        1-D array of per-scenario losses (positive = loss, negative = profit).
        Shape: (n_scenarios,)
    label : str
        Human-readable description, e.g. 'Net PV loss — 20Y PAR endowment'.
    measure : str
        'P' (real-world) or 'Q' (risk-neutral). RiskMetrics will reject any
        non-'P' distribution at runtime to prevent invalid VaR/ES runs.
    currency : str
        Currency code, e.g. 'CNY'.
    unit : str
        Unit of loss values, e.g. 'per policy', 'CNY millions'.

    Class Methods
    -------------
    from_scenario_pv(scenario_results, asset_pv_col, liability_pv_col) :
        Construct from scenario DataFrames of PV (asset and liability).
    from_array(losses, label, measure) :
        Construct directly from a loss array (e.g. stress-shifted results).
    from_deterministic_stress(base_pv, shocked_pvs, shock_labels) :
        Construct from a set of deterministic stress scenarios (development
        phase utility — replace with stochastic simulation in Phase 4).
    """

    losses: np.ndarray
    label: str
    measure: str = "P"
    currency: str = "CNY"
    unit: str = "per policy"

    def __post_init__(self) -> None:
        self.losses = np.asarray(self.losses, dtype=float)
        if self.losses.ndim != 1:
            raise ValueError(
                f"losses must be a 1-D array; got shape {self.losses.shape}"
            )
        if self.measure not in ("P", "Q"):
            raise ValueError(f"measure must be 'P' or 'Q'; got '{self.measure}'")
        if self.measure == "Q":
            warnings.warn(
                "LossDistribution created with measure='Q'. "
                "RiskMetrics will reject this distribution because VaR/ES "
                "computed on Q-measure paths are economically incorrect for ERM. "
                "Use Measure.P for all risk capital and solvency computations. "
                "See esg_process.py and ESG_PROCESS_DOCUMENTATION.md §2.2.",
                UserWarning,
                stacklevel=2,
            )

    @property
    def n_scenarios(self) -> int:
        return len(self.losses)

    @property
    def summary_stats(self) -> pd.Series:
        """Descriptive statistics of the loss distribution."""
        return pd.Series({
            "n_scenarios": self.n_scenarios,
            "mean_loss":   float(np.mean(self.losses)),
            "std_loss":    float(np.std(self.losses, ddof=1)),
            "min_loss":    float(np.min(self.losses)),
            "p5_loss":     float(np.percentile(self.losses, 5)),
            "p25_loss":    float(np.percentile(self.losses, 25)),
            "p50_loss":    float(np.percentile(self.losses, 50)),
            "p75_loss":    float(np.percentile(self.losses, 75)),
            "p95_loss":    float(np.percentile(self.losses, 95)),
            "p99_loss":    float(np.percentile(self.losses, 99)),
            "p995_loss":   float(np.percentile(self.losses, 99.5)),
            "max_loss":    float(np.max(self.losses)),
            "skewness":    float(scipy_stats.skew(self.losses)),
            "kurtosis":    float(scipy_stats.kurtosis(self.losses)),
        }, name=self.label)

    @classmethod
    def from_array(
        cls,
        losses: Sequence[float],
        label: str = "Loss distribution",
        measure: str = "P",
        currency: str = "CNY",
        unit: str = "per policy",
    ) -> "LossDistribution":
        """Construct directly from a loss array.

        Parameters
        ----------
        losses : Sequence[float]
            Per-scenario loss values (positive = loss).
        label : str
            Human-readable description.
        measure : str
            'P' (real-world) or 'Q' (risk-neutral).
        """
        return cls(
            losses=np.asarray(losses, dtype=float),
            label=label,
            measure=measure,
            currency=currency,
            unit=unit,
        )

    @classmethod
    def from_scenario_pv(
        cls,
        scenario_df: pd.DataFrame,
        asset_pv_col: str = "asset_pv",
        liability_pv_col: str = "liability_pv",
        label: str = "Net PV loss (asset − liability PV shortfall)",
        measure: str = "P",
        currency: str = "CNY",
        unit: str = "per policy",
    ) -> "LossDistribution":
        """Construct from a DataFrame of per-scenario PV results.

        Loss is defined as:  loss = liability_pv − asset_pv
        Positive loss ↔ liabilities exceed assets (shortfall / underfunding).

        Parameters
        ----------
        scenario_df : pd.DataFrame
            One row per scenario.  Must contain asset_pv_col and liability_pv_col.
        asset_pv_col : str
            Column name for present value of assets.
        liability_pv_col : str
            Column name for present value of liabilities.
        label : str
            Description for reporting.
        measure : str
            Must be 'P' for ERM / solvency use.

        Returns
        -------
        LossDistribution

        Raises
        ------
        KeyError
            If required columns are absent.

        Notes
        -----
        This method is ready for Phase 4 integration once ScenarioSet.generate()
        is implemented and the projection engine accepts stochastic rate / equity
        paths as inputs.
        """
        missing = [c for c in [asset_pv_col, liability_pv_col]
                   if c not in scenario_df.columns]
        if missing:
            raise KeyError(
                f"Required columns not found in scenario_df: {missing}. "
                f"Available columns: {list(scenario_df.columns)}"
            )
        losses = (
            scenario_df[liability_pv_col].to_numpy(dtype=float)
            - scenario_df[asset_pv_col].to_numpy(dtype=float)
        )
        return cls(losses=losses, label=label, measure=measure,
                   currency=currency, unit=unit)

    @classmethod
    def from_deterministic_stress(
        cls,
        base_pv: float,
        shocked_pvs: Sequence[float],
        shock_labels: Optional[Sequence[str]] = None,
        label: str = "Deterministic stress loss distribution",
        currency: str = "CNY",
        unit: str = "per policy",
    ) -> "LossDistribution":
        """Construct from a set of deterministic stress scenario net PV values.

        This is a development-phase utility for testing the VaR/ES computation
        before stochastic simulation is available.  Losses are:
            loss_i = base_pv − shocked_pv_i   (positive if shocked < base)

        IMPORTANT: With a small number of deterministic scenarios, VaR/ES
        estimates will be marked as unreliable (below ASOP 56 §3.5 thresholds).
        Replace with stochastic paths in Phase 4.

        Parameters
        ----------
        base_pv : float
            Net asset-minus-liability PV under best-estimate assumptions.
        shocked_pvs : Sequence[float]
            Net asset-minus-liability PV under each stress scenario.
        shock_labels : Sequence[str], optional
            Descriptive labels for each shock scenario.
        label : str
            Description.
        """
        losses = np.array([base_pv - pv for pv in shocked_pvs], dtype=float)
        return cls(
            losses=losses,
            label=label,
            measure="P",  # Stress tests are always real-world
            currency=currency,
            unit=unit,
        )


# ---------------------------------------------------------------------------
# 3. Core VaR / ES Computations
# ---------------------------------------------------------------------------

def _empirical_var(losses: np.ndarray, alpha: float) -> float:
    """Empirical VaR(α) via the α-th order statistic.

    Uses numpy.percentile with linear interpolation (consistent with
    standard actuarial practice and Basel / Solvency II conventions).

    Parameters
    ----------
    losses : np.ndarray
        Sorted or unsorted 1-D loss array.
    alpha : float
        Confidence level (e.g. 0.995 for 99.5%).

    Returns
    -------
    float
        VaR estimate at confidence level α.
    """
    return float(np.percentile(losses, alpha * 100))


def _empirical_es(losses: np.ndarray, alpha: float) -> Tuple[float, float, int]:
    """Empirical ES(α) = mean of losses exceeding VaR(α).

    Parameters
    ----------
    losses : np.ndarray
        1-D loss array.
    alpha : float
        Confidence level.

    Returns
    -------
    Tuple[float, float, int]
        (es_value, var_value, tail_count)
    """
    var = _empirical_var(losses, alpha)
    tail = losses[losses > var]
    if len(tail) == 0:
        # Edge case: all scenarios produce identical losses (degenerate)
        return float(var), float(var), 0
    es = float(np.mean(tail))
    return es, float(var), len(tail)


def _parametric_var(mean: float, std: float, alpha: float) -> float:
    """Parametric (Normal) VaR(α) = μ + z_α · σ.

    WARNING: Normal VaR understates tail risk if the loss distribution is
    skewed or fat-tailed (lognormal returns, jump risk).  Validate against
    empirical VaR before use.  See ESG_PROCESS_DOCUMENTATION.md §4.4.

    Parameters
    ----------
    mean : float
        Mean of the loss distribution.
    std : float
        Standard deviation of the loss distribution.
    alpha : float
        Confidence level.

    Returns
    -------
    float
        Normal VaR(α).
    """
    z_alpha = scipy_stats.norm.ppf(alpha)
    return float(mean + z_alpha * std)


def _parametric_es(mean: float, std: float, alpha: float) -> Tuple[float, float]:
    """Parametric (Normal) ES(α) = μ + σ · φ(z_α) / (1 − α).

    Parameters
    ----------
    mean : float
        Mean of the loss distribution.
    std : float
        Standard deviation.
    alpha : float
        Confidence level.

    Returns
    -------
    Tuple[float, float]
        (es_value, var_value)

    Notes
    -----
    Derived from the closed-form tail expectation of the Normal distribution:
        E[X | X > VaR(α)] = μ + σ · φ(Φ⁻¹(α)) / (1 − α)
    where φ is the standard Normal PDF, Φ⁻¹ is the inverse Normal CDF.
    """
    z_alpha = scipy_stats.norm.ppf(alpha)
    phi_z = scipy_stats.norm.pdf(z_alpha)
    var = float(mean + z_alpha * std)
    es = float(mean + std * phi_z / (1.0 - alpha))
    return es, var


# ---------------------------------------------------------------------------
# 4. RiskMetrics — main interface
# ---------------------------------------------------------------------------

class RiskMetrics:
    """Compute VaR and ES across all standard confidence levels.

    Parameters
    ----------
    loss_distribution : LossDistribution
        Pre-constructed loss distribution.
    confidence_levels : list[ConfidenceLevel], optional
        Confidence levels to compute.  Defaults to all three standard levels.

    Methods
    -------
    empirical_var(alpha) → VaRResult
    empirical_es(alpha) → ESResult
    parametric_var(alpha) → VaRResult
    parametric_es(alpha) → ESResult
    full_report(method='empirical') → RiskReport
    stress_test_report(shocked_results, label) → pd.DataFrame

    SOA / ERM Reference
    -------------------
    ASOP 7 §3.3, ASOP 56 §3.5, ERM Framework (VaR 99.5% for solvency).

    Example
    -------
    >>> import numpy as np
    >>> from par_model_v2.risk import RiskMetrics, LossDistribution
    >>> rng = np.random.default_rng(42)
    >>> losses = rng.normal(loc=50_000, scale=25_000, size=5000)
    >>> ldf = LossDistribution.from_array(losses, label="Test loss", measure="P")
    >>> rm = RiskMetrics(ldf)
    >>> report = rm.full_report()
    >>> report.print_summary()
    """

    def __init__(
        self,
        loss_distribution: LossDistribution,
        confidence_levels: Optional[List[ConfidenceLevel]] = None,
    ) -> None:
        if loss_distribution.measure != "P":
            raise ValueError(
                "RiskMetrics requires measure='P' (real-world) loss distributions. "
                f"Got measure={loss_distribution.measure!r}. "
                "Q-measure losses are not valid inputs for VaR/ES."
            )
        self.ldf = loss_distribution
        self.cls = confidence_levels if confidence_levels is not None else ALL_CONFIDENCE_LEVELS
        # Pre-sort for efficiency (order statistics computed once)
        self._sorted_losses = np.sort(self.ldf.losses)
        self._mean = float(np.mean(self.ldf.losses))
        self._std = float(np.std(self.ldf.losses, ddof=1))

    # ------------------------------------------------------------------
    # 4a. Empirical methods
    # ------------------------------------------------------------------

    def empirical_var(self, alpha: ConfidenceLevel) -> VaRResult:
        """Compute empirical VaR at confidence level alpha.

        Uses linear interpolation between order statistics (numpy default).
        Appropriate for non-Normal distributions — no distributional assumption.

        Parameters
        ----------
        alpha : ConfidenceLevel
            Target confidence level.

        Returns
        -------
        VaRResult

        SOA Reference
        -------------
        ASOP 7 §3.3 — scenario-based approach; ASOP 56 §3.5 — adequacy check.
        """
        var_val = _empirical_var(self._sorted_losses, alpha.value)
        return VaRResult(
            confidence_level=alpha,
            var_value=var_val,
            method="empirical",
            scenario_count=self.ldf.n_scenarios,
        )

    def empirical_es(self, alpha: ConfidenceLevel) -> ESResult:
        """Compute empirical ES (Expected Shortfall / CVaR) at confidence level alpha.

        ES = E[Loss | Loss > VaR(α)] — average of tail losses.
        ES is a coherent risk measure (sub-additive, monotone, translation-invariant).

        Parameters
        ----------
        alpha : ConfidenceLevel
            Target confidence level.

        Returns
        -------
        ESResult

        Notes
        -----
        Preferred over VaR for capital purposes (ERM Framework, Basel III).
        Sensitive to tail scenario count — will flag as unreliable if n < 30.

        SOA Reference
        -------------
        ASOP 7 §3.3 — coherent tail risk measurement.
        ERM Framework — ES as primary solvency metric.
        """
        es_val, var_val, tail_count = _empirical_es(self._sorted_losses, alpha.value)
        return ESResult(
            confidence_level=alpha,
            es_value=es_val,
            var_value=var_val,
            tail_count=tail_count,
            method="empirical",
            scenario_count=self.ldf.n_scenarios,
        )

    # ------------------------------------------------------------------
    # 4b. Parametric (Normal) methods
    # ------------------------------------------------------------------

    def parametric_var(self, alpha: ConfidenceLevel) -> VaRResult:
        """Compute parametric (Normal) VaR at confidence level alpha.

        Assumes loss distribution is approximately Normal:
            VaR(α) = μ + Φ⁻¹(α) · σ

        WARNING: Normal assumption likely violated for actuarial loss distributions
        (skew from mortality concentration, fat tails from equity crashes).
        Always compare against empirical_var() — large divergence indicates
        material model error. See ESG_PROCESS_DOCUMENTATION.md §4.4.

        Parameters
        ----------
        alpha : ConfidenceLevel
            Target confidence level.

        Returns
        -------
        VaRResult
        """
        var_val = _parametric_var(self._mean, self._std, alpha.value)
        return VaRResult(
            confidence_level=alpha,
            var_value=var_val,
            method="parametric_normal",
            scenario_count=self.ldf.n_scenarios,
        )

    def parametric_es(self, alpha: ConfidenceLevel) -> ESResult:
        """Compute parametric (Normal) ES at confidence level alpha.

        Assumes loss ~ Normal:
            ES(α) = μ + σ · φ(Φ⁻¹(α)) / (1 − α)

        Parameters
        ----------
        alpha : ConfidenceLevel
            Target confidence level.

        Returns
        -------
        ESResult
        """
        es_val, var_val = _parametric_es(self._mean, self._std, alpha.value)
        # Parametric tail count is theoretical: (1-alpha) * n
        theoretical_tail = int(np.ceil((1 - alpha.value) * self.ldf.n_scenarios))
        return ESResult(
            confidence_level=alpha,
            es_value=es_val,
            var_value=var_val,
            tail_count=theoretical_tail,
            method="parametric_normal",
            scenario_count=self.ldf.n_scenarios,
        )

    # ------------------------------------------------------------------
    # 4c. Full report
    # ------------------------------------------------------------------

    def full_report(self, method: str = "empirical") -> RiskReport:
        """Generate a full risk report across all configured confidence levels.

        Parameters
        ----------
        method : str
            'empirical' (default) or 'parametric_normal'.
            For actuarial use, prefer 'empirical' unless n is very small.

        Returns
        -------
        RiskReport
            Contains VaR and ES at all configured confidence levels.

        Raises
        ------
        ValueError
            If method is not 'empirical' or 'parametric_normal'.
        """
        if method not in ("empirical", "parametric_normal"):
            raise ValueError(
                f"method must be 'empirical' or 'parametric_normal'; got '{method}'"
            )

        var_results: Dict[ConfidenceLevel, VaRResult] = {}
        es_results: Dict[ConfidenceLevel, ESResult] = {}

        for cl in self.cls:
            if method == "empirical":
                var_results[cl] = self.empirical_var(cl)
                es_results[cl] = self.empirical_es(cl)
            else:
                var_results[cl] = self.parametric_var(cl)
                es_results[cl] = self.parametric_es(cl)

        return RiskReport(
            var_results=var_results,
            es_results=es_results,
            loss_summary=self.ldf.summary_stats,
        )

    def both_methods_comparison(self) -> pd.DataFrame:
        """Compare empirical and parametric VaR/ES at all confidence levels.

        Useful for assessing the impact of the Normal approximation.
        Large divergence (> 20%) indicates fat tails or significant skew —
        in which case parametric estimates are not suitable.

        Returns
        -------
        pd.DataFrame
            Columns: confidence_level, metric, empirical, parametric, divergence_pct
        """
        rows = []
        for cl in self.cls:
            emp_var = self.empirical_var(cl)
            par_var = self.parametric_var(cl)
            emp_es = self.empirical_es(cl)
            par_es = self.parametric_es(cl)

            for metric, emp_val, par_val in [
                ("VaR", emp_var.var_value, par_var.var_value),
                ("ES",  emp_es.es_value,  par_es.es_value),
            ]:
                if par_val != 0:
                    div_pct = 100.0 * (emp_val - par_val) / abs(par_val)
                else:
                    div_pct = float("nan")
                rows.append({
                    "confidence_level": cl.label,
                    "metric": metric,
                    "empirical": round(emp_val, 4),
                    "parametric_normal": round(par_val, 4),
                    "divergence_pct": round(div_pct, 2),
                    "normal_adequate": abs(div_pct) < 20 if not np.isnan(div_pct) else False,
                })
        return pd.DataFrame(rows)

    # ------------------------------------------------------------------
    # 4d. Stress test report
    # ------------------------------------------------------------------

    def stress_test_report(
        self,
        stress_shifts: Dict[str, float],
        base_var_cl: ConfidenceLevel = ConfidenceLevel.CL_995,
    ) -> pd.DataFrame:
        """Assess VaR sensitivity to additive shifts in the loss distribution.

        Simulates simple stress scenarios by shifting every loss value up by
        `shock_amount`.  This approximates first-order sensitivity of VaR/ES
        to changes in expected loss (e.g. from parameter shocks).

        Parameters
        ----------
        stress_shifts : dict[str, float]
            Mapping of {stress_label: additive_shift_to_losses}.
            Positive shift = adverse scenario (losses worsen).
            Example: {"IR +100bps": 5000, "Equity -30%": 15000, ...}
        base_var_cl : ConfidenceLevel
            Confidence level for the stress VaR comparison.

        Returns
        -------
        pd.DataFrame
            Columns: scenario, var_995, es_995, var_change, es_change,
                     var_pct_change, es_pct_change.

        Notes
        -----
        This is a simplified additive shift — not a full re-projection.
        Replace with full re-projection in Phase 4 when the ESG stochastic
        paths are available per each stress scenario.

        SOA Reference
        -------------
        ASOP 7 §3.5 — scenario selection and stress testing.
        ERM Framework — scenario stress testing for solvency assessment.
        """
        cl = base_var_cl
        base_var = self.empirical_var(cl).var_value
        base_es = self.empirical_es(cl).es_value

        rows = [
            {
                "scenario": "Base (no stress)",
                f"var_{cl.label}": base_var,
                f"es_{cl.label}": base_es,
                "var_change": 0.0,
                "es_change": 0.0,
                "var_pct_change": 0.0,
                "es_pct_change": 0.0,
            }
        ]

        for label, shift in stress_shifts.items():
            stressed_losses = self.ldf.losses + shift
            stressed_ldf = LossDistribution.from_array(
                stressed_losses, label=label, measure=self.ldf.measure
            )
            stressed_rm = RiskMetrics(stressed_ldf, confidence_levels=[cl])
            stressed_var = stressed_rm.empirical_var(cl).var_value
            stressed_es = stressed_rm.empirical_es(cl).es_value
            rows.append({
                "scenario": label,
                f"var_{cl.label}": stressed_var,
                f"es_{cl.label}": stressed_es,
                "var_change": stressed_var - base_var,
                "es_change": stressed_es - base_es,
                "var_pct_change": 100.0 * (stressed_var - base_var) / abs(base_var) if base_var != 0 else float("nan"),
                "es_pct_change": 100.0 * (stressed_es - base_es) / abs(base_es) if base_es != 0 else float("nan"),
            })

        return pd.DataFrame(rows)
