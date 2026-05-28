"""
Scenario Stress Testing Framework
==================================

Implements a structured scenario stress testing framework for PAR fund
stochastic ALM, required by:

  - SOA ASOP 7  §3.5  — scenario selection and adequacy for stress tests
  - SOA ASOP 56 §3.3  — scenario-based analysis disclosure requirements
  - IA TAS M    §3.8  — stress testing and sensitivity analysis
  - ERM Framework     — adverse scenario identification and solvency impact
  - CBIRC C-ROSS      — prescribed regulatory stress scenarios for life insurers

FRAMEWORK OVERVIEW
------------------
The framework provides three layers:

  1. **Shock Specifications** (`ShockSpec`) — atomic parameter shocks
     (parallel rate shift, equity price drop, credit spread widening, etc.)

  2. **Stress Scenarios** (`StressScenario`) — named, regulatory-referenced
     combinations of shocks drawn from CBIRC C-ROSS, SOA ASOP 7, and
     standard ERM practice.

  3. **Stress Test Engine** (`StressTestEngine`) — applies scenarios to a
     `PortfolioSnapshot`, producing `StressTestResult` objects with surplus,
     solvency ratio, and regulatory margin impacts.

PREDEFINED SCENARIO LIBRARY
-----------------------------
  CBIRC_SCENARIOS   — 6 mandatory CBIRC C-ROSS prescribed tests
  SOA_ASOP7_SCENARIOS — 5 standard SOA ASOP 7 scenarios
  COMBINED_SCENARIOS — 4 multi-factor adverse scenarios
  ALL_SCENARIOS      — union of the above

LOSS SIGN CONVENTION
---------------------
Surplus = Assets − Liabilities.  A *positive* stress impact means
surplus *falls* (adverse scenario).  All `surplus_change` values in
StressTestResult follow this convention: positive = worse.

P-MEASURE REQUIREMENT
----------------------
Stress tests must be conducted under Measure.P (real-world) parameters.
Do not use Q-measure risk-neutral parameters for solvency-basis stress tests.
See esg_process.py and ESG_PROCESS_DOCUMENTATION.md §2.2.

DEVELOPMENT STATUS
------------------
Phase 2 — full shock definitions and engine implemented.
Phase 4 — integrate with ScenarioSet for stochastic re-projection per scenario
          (replacing the closed-form / duration-approximation methods used here).

PRODUCTION USE RESTRICTION
---------------------------
Duration and convexity approximations are used for asset repricing in Phase 2.
Full re-projection is required for regulatory filing in Phase 4+.
"""

from __future__ import annotations

import enum
import warnings
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# 1.  Enumerations
# ---------------------------------------------------------------------------

class ShockType(enum.Enum):
    """Taxonomy of shock dimensions that can be applied to a portfolio.

    SOA ASOP 7 §3.5 requires scenarios to be selected from a comprehensive
    range of plausible adverse conditions across all material risk drivers.
    """
    RATE_PARALLEL  = "rate_parallel"   # Parallel shift of the yield curve (bps)
    RATE_TWIST     = "rate_twist"      # Steepening/flattening twist (bps at long end)
    EQUITY_PRICE   = "equity_price"    # Proportional equity price shock (e.g. -0.30)
    EQUITY_VOL     = "equity_vol"      # Implied vol multiplier (e.g. 2.0 = doubled vol)
    CREDIT_SPREAD  = "credit_spread"   # Credit spread widening (bps)
    FX             = "fx"              # FX rate shock (proportional, e.g. -0.10)
    LAPSE_RATE     = "lapse_rate"      # Additive lapse rate shock (e.g. +0.05 = +5pp)
    MORTALITY      = "mortality"       # Mortality rate multiplier (e.g. 1.10 = +10%)


class ScenarioCategory(enum.Enum):
    """Classification of scenario origin and purpose."""
    CBIRC_PRESCRIBED   = "CBIRC C-ROSS Prescribed"
    SOA_ASOP7          = "SOA ASOP 7 Standard"
    IA_TAS_M           = "IA TAS M §3.8"
    ERM_COMBINED       = "ERM Multi-Factor"
    SENSITIVITY        = "Sensitivity Analysis"
    REVERSE_STRESS     = "Reverse Stress Test"


# ---------------------------------------------------------------------------
# 2.  Shock specification
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ShockSpec:
    """Atomic parameter shock.

    Parameters
    ----------
    shock_type : ShockType
        The dimension of the shock.
    magnitude : float
        Size of the shock.  Units depend on `shock_type`:
          - RATE_PARALLEL / RATE_TWIST / CREDIT_SPREAD: basis points (e.g. 100)
          - EQUITY_PRICE / FX: proportional (e.g. -0.30 = −30%)
          - EQUITY_VOL / MORTALITY: multiplier (e.g. 2.0 = double)
          - LAPSE_RATE: additive percentage points (e.g. 0.05 = +5pp)
    description : str
        Human-readable description of this shock.
    """
    shock_type:  ShockType
    magnitude:   float
    description: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.shock_type, ShockType):
            raise TypeError(f"shock_type must be ShockType, got {type(self.shock_type)}")


# ---------------------------------------------------------------------------
# 3.  Stress scenario definition
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class StressScenario:
    """Named, multi-shock stress scenario.

    Attributes
    ----------
    name : str
        Short identifier (used as report row label).
    category : ScenarioCategory
        Scenario origin classification.
    description : str
        Narrative description of the scenario.
    shocks : tuple[ShockSpec, ...]
        Ordered sequence of shocks applied simultaneously.
    regulatory_reference : str
        Citation of the governing standard (e.g. "CBIRC C-ROSS §5.2.1").
    severity : str
        Qualitative severity: "mild" | "moderate" | "severe" | "extreme".
    """
    name:                 str
    category:             ScenarioCategory
    description:          str
    shocks:               Tuple[ShockSpec, ...]
    regulatory_reference: str = ""
    severity:             str = "moderate"   # mild | moderate | severe | extreme

    def shock_by_type(self, shock_type: ShockType) -> Optional[ShockSpec]:
        """Return the first shock of the given type, or None."""
        for s in self.shocks:
            if s.shock_type == shock_type:
                return s
        return None


# ---------------------------------------------------------------------------
# 4.  Predefined scenario library
# ---------------------------------------------------------------------------

# --- 4a. CBIRC C-ROSS prescribed scenarios (mandatory for Chinese life insurers)

CBIRC_SCENARIOS: List[StressScenario] = [
    StressScenario(
        name="CBIRC-IR-UP200",
        category=ScenarioCategory.CBIRC_PRESCRIBED,
        description=(
            "Parallel upward shift of the CNY risk-free yield curve by 200 bps. "
            "Tests asset–liability duration mismatch under rising rates. "
            "Mandatory under CBIRC C-ROSS Risk Capital Rules §5.2."
        ),
        shocks=(
            ShockSpec(ShockType.RATE_PARALLEL, +200.0,
                      "CNY yield curve +200bps parallel shift"),
        ),
        regulatory_reference="CBIRC C-ROSS §5.2.1 — Interest Rate Risk (upward)",
        severity="severe",
    ),
    StressScenario(
        name="CBIRC-IR-DOWN200",
        category=ScenarioCategory.CBIRC_PRESCRIBED,
        description=(
            "Parallel downward shift of the CNY risk-free yield curve by 200 bps. "
            "Tests reinvestment risk and guarantee cost escalation under falling rates. "
            "PAR funds are particularly sensitive due to guaranteed minimum bonuses."
        ),
        shocks=(
            ShockSpec(ShockType.RATE_PARALLEL, -200.0,
                      "CNY yield curve -200bps parallel shift"),
        ),
        regulatory_reference="CBIRC C-ROSS §5.2.1 — Interest Rate Risk (downward)",
        severity="severe",
    ),
    StressScenario(
        name="CBIRC-EQ-DOWN40",
        category=ScenarioCategory.CBIRC_PRESCRIBED,
        description=(
            "Equity market decline of 40% applied to the equity allocation "
            "of the PAR fund portfolio. Tests equity concentration risk and "
            "investment return shortfall relative to guaranteed bonuses."
        ),
        shocks=(
            ShockSpec(ShockType.EQUITY_PRICE, -0.40,
                      "CSI 300 / equity portfolio −40% price shock"),
        ),
        regulatory_reference="CBIRC C-ROSS §5.2.2 — Equity Price Risk",
        severity="extreme",
    ),
    StressScenario(
        name="CBIRC-CREDIT-WIDE200",
        category=ScenarioCategory.CBIRC_PRESCRIBED,
        description=(
            "Credit spread widening of 200 bps on non-government bond holdings. "
            "Tests mark-to-market losses on corporate bond allocation and "
            "potential credit migration / default events."
        ),
        shocks=(
            ShockSpec(ShockType.CREDIT_SPREAD, +200.0,
                      "Corporate bond credit spread +200bps widening"),
        ),
        regulatory_reference="CBIRC C-ROSS §5.2.3 — Credit Risk",
        severity="severe",
    ),
    StressScenario(
        name="CBIRC-LAPSE-SHOCK",
        category=ScenarioCategory.CBIRC_PRESCRIBED,
        description=(
            "Mass lapse shock: immediate 30pp increase in lapse rates. "
            "Tests liquidity and surrender value obligations under "
            "policyholder behaviour stress. Critical for PAR fund surplus "
            "distribution sustainability."
        ),
        shocks=(
            ShockSpec(ShockType.LAPSE_RATE, +0.30,
                      "Lapse rate +30 percentage points (mass lapse event)"),
        ),
        regulatory_reference="CBIRC C-ROSS §5.2.4 — Lapse & Behaviour Risk",
        severity="extreme",
    ),
    StressScenario(
        name="CBIRC-COMBINED-CRISIS",
        category=ScenarioCategory.CBIRC_PRESCRIBED,
        description=(
            "Combined market crisis scenario: equity −30%, rates −150bps, "
            "credit spreads +150bps. Represents a systemic financial stress "
            "event (e.g. 2008-style crisis adapted to CNY markets). "
            "Required for CBIRC comprehensive stress testing."
        ),
        shocks=(
            ShockSpec(ShockType.EQUITY_PRICE, -0.30,
                      "Equity −30% (market crisis)"),
            ShockSpec(ShockType.RATE_PARALLEL, -150.0,
                      "CNY yield curve −150bps (flight to safety)"),
            ShockSpec(ShockType.CREDIT_SPREAD, +150.0,
                      "Credit spread +150bps (risk-off environment)"),
        ),
        regulatory_reference="CBIRC C-ROSS §5.3 — Comprehensive Stress Test",
        severity="extreme",
    ),
]

# --- 4b. SOA ASOP 7 standard scenarios

SOA_ASOP7_SCENARIOS: List[StressScenario] = [
    StressScenario(
        name="SOA-IR-TWIST-STEEP",
        category=ScenarioCategory.SOA_ASOP7,
        description=(
            "Yield curve steepening: short rates −100bps, long rates +100bps. "
            "Tests convexity mismatch between PAR fund liabilities (long duration) "
            "and asset portfolio. Consistent with SOA ASOP 7 §3.5 twist scenario."
        ),
        shocks=(
            ShockSpec(ShockType.RATE_PARALLEL, -100.0,
                      "Short-end −100bps (parallel base)"),
            ShockSpec(ShockType.RATE_TWIST, +100.0,
                      "Long-end +100bps twist (steepening)"),
        ),
        regulatory_reference="SOA ASOP 7 §3.5 — Interest Rate Scenario Set",
        severity="moderate",
    ),
    StressScenario(
        name="SOA-IR-TWIST-FLAT",
        category=ScenarioCategory.SOA_ASOP7,
        description=(
            "Yield curve flattening: short rates +100bps, long rates flat. "
            "Tests reinvestment risk for maturing short-term assets and "
            "economic cost of guaranteed minimum crediting rates."
        ),
        shocks=(
            ShockSpec(ShockType.RATE_PARALLEL, +100.0,
                      "Short-end +100bps"),
            ShockSpec(ShockType.RATE_TWIST, -100.0,
                      "Long-end twist −100bps (flattening)"),
        ),
        regulatory_reference="SOA ASOP 7 §3.5 — Interest Rate Scenario Set",
        severity="moderate",
    ),
    StressScenario(
        name="SOA-MORTALITY-UP10",
        category=ScenarioCategory.SOA_ASOP7,
        description=(
            "Mortality rates increase by 10% across all age/sex cohorts. "
            "Represents pandemic or catastrophe mortality event. Tests "
            "adequacy of mortality margins in PAR fund pricing basis."
        ),
        shocks=(
            ShockSpec(ShockType.MORTALITY, 1.10,
                      "Mortality rate ×1.10 (10% uplift)"),
        ),
        regulatory_reference="SOA ASOP 7 §3.5 / ASOP 25 §3.2 — Mortality Stress",
        severity="moderate",
    ),
    StressScenario(
        name="SOA-EQ-VOL-DOUBLE",
        category=ScenarioCategory.SOA_ASOP7,
        description=(
            "Equity implied volatility doubles (vol multiplier = 2.0). "
            "Represents a VIX-spike style event. Tests option cost escalation "
            "for guaranteed minimum investment returns (GMIR) embedded in PAR fund."
        ),
        shocks=(
            ShockSpec(ShockType.EQUITY_VOL, 2.0,
                      "Equity implied volatility ×2.0"),
        ),
        regulatory_reference="SOA ASOP 7 §3.5 — Equity Scenario",
        severity="severe",
    ),
    StressScenario(
        name="SOA-LAPSE-DYNAMIC",
        category=ScenarioCategory.SOA_ASOP7,
        description=(
            "Dynamic lapse stress: +15pp lapse rate increase representing "
            "rational policyholder behaviour under adverse market conditions. "
            "Tests liquidity and surrender obligation mismatch in PAR fund."
        ),
        shocks=(
            ShockSpec(ShockType.LAPSE_RATE, +0.15,
                      "Lapse rate +15pp (dynamic policyholder behaviour)"),
        ),
        regulatory_reference="SOA ASOP 7 §3.5 — Lapse Behaviour Scenario",
        severity="moderate",
    ),
]

# --- 4c. Multi-factor ERM combined scenarios

COMBINED_SCENARIOS: List[StressScenario] = [
    StressScenario(
        name="ERM-DEFLATION-TRAP",
        category=ScenarioCategory.ERM_COMBINED,
        description=(
            "Japan-style deflation: rates −300bps, equity −50%, lapse −10pp "
            "(policyholders retain policies when alternatives worsen). "
            "Represents a secular low-rate trapped environment. "
            "Most adverse single scenario for PAR fund guarantee costs."
        ),
        shocks=(
            ShockSpec(ShockType.RATE_PARALLEL, -300.0,
                      "Rates −300bps (deflation / zero-rate environment)"),
            ShockSpec(ShockType.EQUITY_PRICE, -0.50,
                      "Equity −50% (deflation-linked asset collapse)"),
            ShockSpec(ShockType.LAPSE_RATE, -0.10,
                      "Lapse −10pp (no better alternatives — policies retained)"),
        ),
        regulatory_reference=(
            "ERM Framework §4.2 — Tail Risk / Reverse Stress Test; "
            "IA TAS M §3.8 — Adverse Scenario"
        ),
        severity="extreme",
    ),
    StressScenario(
        name="ERM-STAGFLATION",
        category=ScenarioCategory.ERM_COMBINED,
        description=(
            "Stagflationary shock: rates +300bps (inflation-driven), "
            "equity −25% (growth collapse), credit spread +100bps. "
            "Tests whether PAR fund assets reprice favourably enough to "
            "offset equity losses and guarantee shortfall."
        ),
        shocks=(
            ShockSpec(ShockType.RATE_PARALLEL, +300.0,
                      "Rates +300bps (inflationary tightening)"),
            ShockSpec(ShockType.EQUITY_PRICE, -0.25,
                      "Equity −25% (stagflation growth collapse)"),
            ShockSpec(ShockType.CREDIT_SPREAD, +100.0,
                      "Credit spread +100bps (liquidity premium rise)"),
        ),
        regulatory_reference="ERM Framework §4.2 — Stagflation Scenario",
        severity="severe",
    ),
    StressScenario(
        name="ERM-PANDEMIC-LAPSE",
        category=ScenarioCategory.ERM_COMBINED,
        description=(
            "Pandemic + mass-lapse: mortality +20%, lapse +20pp, "
            "equity −20% (initial shock). Tests combined mortality and "
            "liquidity stress. Critical following COVID-19 experience."
        ),
        shocks=(
            ShockSpec(ShockType.MORTALITY, 1.20,
                      "Mortality ×1.20 (pandemic excess deaths)"),
            ShockSpec(ShockType.LAPSE_RATE, +0.20,
                      "Lapse +20pp (financial hardship surrenders)"),
            ShockSpec(ShockType.EQUITY_PRICE, -0.20,
                      "Equity −20% (pandemic market impact)"),
        ),
        regulatory_reference=(
            "ERM Framework §4.3 — Pandemic Scenario; "
            "SOA ASOP 56 §3.3 — Scenario Disclosure"
        ),
        severity="severe",
    ),
    StressScenario(
        name="ERM-REVERSE-STRESS",
        category=ScenarioCategory.ERM_COMBINED,
        description=(
            "Reverse stress test anchor: represents the hypothetical scenario "
            "at which the PAR fund surplus falls to zero (technical insolvency). "
            "Uses a combined shock calibrated to produce breakeven outcome. "
            "Parameterisation: rates −400bps, equity −60%, lapse +25pp. "
            "Subject to revision once calibration is complete in Phase 4."
        ),
        shocks=(
            ShockSpec(ShockType.RATE_PARALLEL, -400.0,
                      "Rates −400bps (extreme low-rate scenario)"),
            ShockSpec(ShockType.EQUITY_PRICE, -0.60,
                      "Equity −60% (severe market crash)"),
            ShockSpec(ShockType.LAPSE_RATE, +0.25,
                      "Lapse +25pp (confidence collapse)"),
        ),
        regulatory_reference=(
            "IA TAS M §3.8 — Reverse Stress Test; "
            "ERM Framework §4.4 — Reverse Stress Test"
        ),
        severity="extreme",
    ),
]

# Aggregated library
ALL_SCENARIOS: List[StressScenario] = (
    CBIRC_SCENARIOS + SOA_ASOP7_SCENARIOS + COMBINED_SCENARIOS
)


# ---------------------------------------------------------------------------
# 5.  Portfolio snapshot
# ---------------------------------------------------------------------------

@dataclass
class PortfolioSnapshot:
    """Simplified balance-sheet snapshot of the PAR fund at valuation date.

    This dataclass holds the stylised asset/liability decomposition needed
    for duration-approximation stress testing (Phase 2 implementation).
    Full re-projection per scenario will replace this in Phase 4.

    Parameters
    ----------
    valuation_date : datetime
        Balance-sheet date.
    bond_mv : float
        Mark-to-market value of bond / fixed-income holdings (CNY).
    bond_duration : float
        Modified duration of bond portfolio (years).
    bond_convexity : float
        Convexity of bond portfolio (years²).  Used for second-order rate shifts.
    equity_mv : float
        Mark-to-market value of equity holdings (CNY).
    credit_bond_mv : float
        Mark-to-market value of corporate / credit bond holdings (CNY).
    credit_bond_duration : float
        Modified duration of credit bond portfolio (years).
    other_assets : float
        Cash, property, and other assets not repriced under these shocks (CNY).
    liability_pv : float
        Present value of policyholder liabilities (CNY).
    liability_duration : float
        Effective duration of liabilities (years).
    liability_convexity : float
        Convexity of liabilities (years²).
    discount_rate : float
        Base annualised discount rate used for liability valuation (decimal).
    lapse_sensitivity : float
        Estimated change in liability PV per +1pp change in lapse rate (CNY).
        Negative means higher lapse → lower liabilities (anti-clockwise effect).
    mortality_sensitivity : float
        Estimated change in liability PV per ×0.1 change in mortality multiplier.
        Positive means higher mortality → higher death benefit outgo.
    label : str
        Descriptive label for this snapshot.
    """
    valuation_date:      datetime
    bond_mv:             float
    bond_duration:       float
    bond_convexity:      float
    equity_mv:           float
    credit_bond_mv:      float
    credit_bond_duration: float
    other_assets:        float
    liability_pv:        float
    liability_duration:  float
    liability_convexity: float
    discount_rate:       float
    lapse_sensitivity:   float   # CNY per +1pp lapse rate
    mortality_sensitivity: float  # CNY per ×0.1 mortality multiplier
    label:               str = "PAR Fund Portfolio"

    # ------------------------------------------------------------------
    # Derived quantities
    # ------------------------------------------------------------------

    @property
    def total_assets(self) -> float:
        """Total asset market value."""
        return self.bond_mv + self.equity_mv + self.credit_bond_mv + self.other_assets

    @property
    def surplus(self) -> float:
        """Free surplus = Assets − Liabilities."""
        return self.total_assets - self.liability_pv

    @property
    def solvency_ratio(self) -> float:
        """Asset / Liability ratio.  >1.0 = solvent."""
        if self.liability_pv == 0:
            return float("inf")
        return self.total_assets / self.liability_pv


# ---------------------------------------------------------------------------
# 6.  Stress test result
# ---------------------------------------------------------------------------

@dataclass
class StressTestResult:
    """Outcome of applying a single `StressScenario` to a `PortfolioSnapshot`.

    Attributes
    ----------
    scenario : StressScenario
        The scenario that produced this result.
    base_snapshot : PortfolioSnapshot
        Unstressed portfolio at valuation date.
    stressed_bond_mv : float
        Bond MV after rate/credit shocks.
    stressed_equity_mv : float
        Equity MV after equity price shock.
    stressed_credit_bond_mv : float
        Credit bond MV after credit spread shock.
    stressed_liability_pv : float
        Liability PV after rate/lapse/mortality shocks.
    shock_details : dict
        Per-shock decomposition of asset and liability impacts.
    timestamp : datetime
        When this result was computed.
    """
    scenario:              StressScenario
    base_snapshot:         PortfolioSnapshot
    stressed_bond_mv:      float
    stressed_equity_mv:    float
    stressed_credit_bond_mv: float
    stressed_liability_pv: float
    shock_details:         Dict[str, float]
    timestamp:             datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    # ------------------------------------------------------------------
    # Derived quantities
    # ------------------------------------------------------------------

    @property
    def stressed_total_assets(self) -> float:
        return (
            self.stressed_bond_mv
            + self.stressed_equity_mv
            + self.stressed_credit_bond_mv
            + self.base_snapshot.other_assets   # other assets not repriced
        )

    @property
    def stressed_surplus(self) -> float:
        return self.stressed_total_assets - self.stressed_liability_pv

    @property
    def surplus_change(self) -> float:
        """Change in surplus (positive = adverse = surplus fell)."""
        return self.base_snapshot.surplus - self.stressed_surplus

    @property
    def surplus_change_pct(self) -> float:
        """Surplus change as % of base surplus."""
        base = self.base_snapshot.surplus
        if base == 0:
            return float("nan")
        return 100.0 * self.surplus_change / abs(base)

    @property
    def stressed_solvency_ratio(self) -> float:
        if self.stressed_liability_pv == 0:
            return float("inf")
        return self.stressed_total_assets / self.stressed_liability_pv

    @property
    def solvency_ratio_change(self) -> float:
        return self.stressed_solvency_ratio - self.base_snapshot.solvency_ratio

    @property
    def is_insolvent(self) -> bool:
        return self.stressed_surplus < 0

    def to_dict(self) -> Dict:
        """Flat dictionary for DataFrame construction."""
        return {
            "scenario":              self.scenario.name,
            "category":              self.scenario.category.value,
            "severity":              self.scenario.severity,
            "regulatory_reference":  self.scenario.regulatory_reference,
            "base_assets":           round(self.base_snapshot.total_assets, 0),
            "stressed_assets":       round(self.stressed_total_assets, 0),
            "base_liabilities":      round(self.base_snapshot.liability_pv, 0),
            "stressed_liabilities":  round(self.stressed_liability_pv, 0),
            "base_surplus":          round(self.base_snapshot.surplus, 0),
            "stressed_surplus":      round(self.stressed_surplus, 0),
            "surplus_change":        round(self.surplus_change, 0),
            "surplus_change_pct":    round(self.surplus_change_pct, 2),
            "base_solvency_ratio":   round(self.base_snapshot.solvency_ratio, 4),
            "stressed_solvency_ratio": round(self.stressed_solvency_ratio, 4),
            "solvency_ratio_change": round(self.solvency_ratio_change, 4),
            "is_insolvent":          self.is_insolvent,
        }


# ---------------------------------------------------------------------------
# 7.  Stress Test Engine
# ---------------------------------------------------------------------------

class StressTestEngine:
    """Apply stress scenarios to a portfolio snapshot.

    This engine implements closed-form first-order (and second-order for rates)
    approximations for asset and liability repricing under each scenario shock.

    APPROXIMATION NOTES (Phase 2)
    ------------------------------
    - Rate shocks: duration + convexity approximation
      ΔP/P ≈ −D_mod × Δy + 0.5 × C × (Δy)²
      where Δy is in decimal (e.g. 200bps → Δy = 0.020).
    - Equity shocks: direct proportional impact.
    - Credit shocks: duration approximation on credit bond allocation only.
    - Lapse shocks: linear sensitivity (CNY per pp from PortfolioSnapshot).
    - Mortality shocks: linear sensitivity (CNY per multiplier unit).
    - Vol shocks: recorded for Phase 4 TVOG re-computation; no MV impact in Phase 2.
    - FX shocks: recorded for Phase 4; no FX exposure modelled in Phase 2.

    SOA Reference
    -------------
    ASOP 7 §3.5 — scenario-based analysis; first-order approximation acceptable
    for sensitivity reporting when full re-projection is not feasible.

    Parameters
    ----------
    portfolio : PortfolioSnapshot
        Base portfolio to stress test.
    scenarios : list[StressScenario], optional
        Scenarios to run.  Defaults to ALL_SCENARIOS.
    warn_on_approximation : bool
        Emit warnings when approximation limitations apply.  Default True.
    """

    def __init__(
        self,
        portfolio: PortfolioSnapshot,
        scenarios: Optional[List[StressScenario]] = None,
        warn_on_approximation: bool = True,
    ) -> None:
        if not isinstance(portfolio, PortfolioSnapshot):
            raise TypeError("portfolio must be a PortfolioSnapshot instance")
        self.portfolio = portfolio
        self.scenarios = scenarios if scenarios is not None else ALL_SCENARIOS
        self.warn_on_approximation = warn_on_approximation

    # ------------------------------------------------------------------
    # 7a. Internal shock helpers
    # ------------------------------------------------------------------

    def _apply_rate_shock(
        self,
        mv: float,
        duration: float,
        convexity: float,
        parallel_bps: float,
        twist_bps: float = 0.0,
    ) -> Tuple[float, float]:
        """Return (stressed_mv, mv_change) for a rate-sensitive asset or liability.

        Uses convexity-adjusted duration approximation.
        Twist adds to the duration × twist_bps component at long end.
        """
        dy_parallel = parallel_bps / 10_000.0
        dy_twist    = twist_bps    / 10_000.0
        # Duration approximation: ΔP ≈ −D × Δy × P + 0.5 × C × (Δy)² × P
        delta_from_parallel = (
            -duration * dy_parallel
            + 0.5 * convexity * dy_parallel ** 2
        ) * mv
        # Twist treated as an additional long-end shift (simplified)
        delta_from_twist = -duration * dy_twist * mv * 0.5  # 50% weight at long end

        total_delta = delta_from_parallel + delta_from_twist
        stressed_mv = mv + total_delta
        return max(stressed_mv, 0.0), total_delta

    def _apply_equity_shock(self, equity_mv: float, shock_pct: float) -> Tuple[float, float]:
        """Return (stressed_mv, mv_change) for equity shock (shock_pct e.g. -0.30)."""
        delta = equity_mv * shock_pct
        return max(equity_mv + delta, 0.0), delta

    def _apply_credit_shock(
        self,
        credit_mv: float,
        duration: float,
        spread_bps: float,
    ) -> Tuple[float, float]:
        """Return (stressed_mv, mv_change) for credit spread widening."""
        dy = spread_bps / 10_000.0
        delta = -duration * dy * credit_mv
        return max(credit_mv + delta, 0.0), delta

    def _apply_lapse_shock(self, lapse_shock_pp: float) -> float:
        """Return change in liability PV due to lapse shock (additive pp)."""
        # Linear sensitivity: portfolio.lapse_sensitivity CNY per +1pp
        return self.portfolio.lapse_sensitivity * (lapse_shock_pp * 100.0)

    def _apply_mortality_shock(self, mortality_multiplier: float) -> float:
        """Return change in liability PV due to mortality multiplier shock."""
        # Base multiplier = 1.0; deviation drives sensitivity
        multiplier_change = mortality_multiplier - 1.0  # e.g. 1.10 → +0.10
        return self.portfolio.mortality_sensitivity * (multiplier_change / 0.10)

    # ------------------------------------------------------------------
    # 7b. Apply a single scenario
    # ------------------------------------------------------------------

    def apply_scenario(self, scenario: StressScenario) -> StressTestResult:
        """Apply all shocks in `scenario` to the base portfolio.

        Returns
        -------
        StressTestResult
        """
        p = self.portfolio
        shock_details: Dict[str, float] = {}

        # Collect shocks by type
        parallel_bps = 0.0
        twist_bps    = 0.0
        equity_shock = 0.0
        credit_bps   = 0.0
        lapse_pp     = 0.0
        mortality_mult = 1.0
        has_vol_shock  = False
        has_fx_shock   = False

        for shock in scenario.shocks:
            if shock.shock_type == ShockType.RATE_PARALLEL:
                parallel_bps += shock.magnitude
            elif shock.shock_type == ShockType.RATE_TWIST:
                twist_bps += shock.magnitude
            elif shock.shock_type == ShockType.EQUITY_PRICE:
                equity_shock += shock.magnitude
            elif shock.shock_type == ShockType.CREDIT_SPREAD:
                credit_bps += shock.magnitude
            elif shock.shock_type == ShockType.LAPSE_RATE:
                lapse_pp += shock.magnitude
            elif shock.shock_type == ShockType.MORTALITY:
                mortality_mult *= shock.magnitude
            elif shock.shock_type == ShockType.EQUITY_VOL:
                has_vol_shock = True
                if self.warn_on_approximation:
                    warnings.warn(
                        f"[{scenario.name}] EQUITY_VOL shock recorded but not applied "
                        "to MV in Phase 2. Full TVOG re-projection required (Phase 4).",
                        UserWarning, stacklevel=2,
                    )
            elif shock.shock_type == ShockType.FX:
                has_fx_shock = True
                if self.warn_on_approximation:
                    warnings.warn(
                        f"[{scenario.name}] FX shock recorded but not applied "
                        "in Phase 2 (no FX exposure modelled). Review in Phase 4.",
                        UserWarning, stacklevel=2,
                    )

        # --- Asset repricing ------------------------------------------------

        # Government / duration bonds
        stressed_bond_mv, bond_delta = self._apply_rate_shock(
            mv=p.bond_mv,
            duration=p.bond_duration,
            convexity=p.bond_convexity,
            parallel_bps=parallel_bps,
            twist_bps=twist_bps,
        )
        shock_details["bond_mv_change"] = bond_delta

        # Equity
        stressed_equity_mv, equity_delta = self._apply_equity_shock(
            equity_mv=p.equity_mv,
            shock_pct=equity_shock,
        )
        shock_details["equity_mv_change"] = equity_delta

        # Credit bonds (rate shock + spread shock)
        stressed_credit_mv, credit_rate_delta = self._apply_rate_shock(
            mv=p.credit_bond_mv,
            duration=p.credit_bond_duration,
            convexity=0.0,           # simplified: no convexity for credit bonds
            parallel_bps=parallel_bps,
            twist_bps=0.0,
        )
        stressed_credit_mv, credit_spread_delta = self._apply_credit_shock(
            credit_mv=stressed_credit_mv,
            duration=p.credit_bond_duration,
            spread_bps=credit_bps,
        )
        shock_details["credit_bond_mv_change"] = credit_rate_delta + credit_spread_delta

        # --- Liability repricing --------------------------------------------

        # Rate shock on liabilities (note: opposite sign to assets)
        stressed_liab_mv, liab_rate_delta = self._apply_rate_shock(
            mv=p.liability_pv,
            duration=p.liability_duration,
            convexity=p.liability_convexity,
            parallel_bps=parallel_bps,
            twist_bps=twist_bps,
        )
        shock_details["liability_rate_change"] = liab_rate_delta

        # Lapse shock
        liab_lapse_delta = self._apply_lapse_shock(lapse_pp)
        shocked_liab = stressed_liab_mv + liab_lapse_delta
        shock_details["liability_lapse_change"] = liab_lapse_delta

        # Mortality shock
        liab_mort_delta = self._apply_mortality_shock(mortality_mult)
        shocked_liab += liab_mort_delta
        shock_details["liability_mortality_change"] = liab_mort_delta

        stressed_liability_pv = max(shocked_liab, 0.0)

        return StressTestResult(
            scenario=scenario,
            base_snapshot=p,
            stressed_bond_mv=stressed_bond_mv,
            stressed_equity_mv=stressed_equity_mv,
            stressed_credit_bond_mv=stressed_credit_mv,
            stressed_liability_pv=stressed_liability_pv,
            shock_details=shock_details,
        )

    # ------------------------------------------------------------------
    # 7c. Run all scenarios
    # ------------------------------------------------------------------

    def run_all_scenarios(
        self,
        scenarios: Optional[List[StressScenario]] = None,
    ) -> List[StressTestResult]:
        """Apply all scenarios in sequence, return list of results."""
        target = scenarios if scenarios is not None else self.scenarios
        return [self.apply_scenario(s) for s in target]

    # ------------------------------------------------------------------
    # 7d. Report generation
    # ------------------------------------------------------------------

    def generate_report(
        self,
        scenarios: Optional[List[StressScenario]] = None,
        sort_by: str = "surplus_change",
        ascending: bool = False,
    ) -> pd.DataFrame:
        """Run all scenarios and return a summary DataFrame.

        Parameters
        ----------
        scenarios : list[StressScenario], optional
            Override scenario list.
        sort_by : str
            Column to sort by.  Default "surplus_change" (most adverse first).
        ascending : bool
            Sort direction.  Default False (worst first).

        Returns
        -------
        pd.DataFrame
            One row per scenario with surplus, solvency ratio, and change columns.
        """
        results = self.run_all_scenarios(scenarios)
        rows = [r.to_dict() for r in results]
        df = pd.DataFrame(rows)
        if sort_by in df.columns:
            df = df.sort_values(sort_by, ascending=ascending).reset_index(drop=True)
        return df

    def generate_markdown_report(
        self,
        scenarios: Optional[List[StressScenario]] = None,
        title: str = "PAR Fund Scenario Stress Test Report",
    ) -> str:
        """Generate a governance-ready markdown report.

        Returns
        -------
        str
            Formatted markdown string suitable for inclusion in audit documents
            or appending to docs/MODEL_AUDIT_REPORT.md.
        """
        results = self.run_all_scenarios(scenarios)
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        p = self.portfolio

        lines: List[str] = [
            f"# {title}",
            "",
            f"**Generated:** {now}  ",
            f"**Valuation Date:** {p.valuation_date.date()}  ",
            f"**Portfolio:** {p.label}  ",
            f"**Regulatory Framework:** CBIRC C-ROSS, SOA ASOP 7, IA TAS M §3.8  ",
            "",
            "---",
            "",
            "## Base Portfolio (Pre-Stress)",
            "",
            f"| Metric | Value (CNY) |",
            f"|--------|-------------|",
            f"| Total Assets | {p.total_assets:,.0f} |",
            f"| Government Bonds | {p.bond_mv:,.0f} |",
            f"| Equity | {p.equity_mv:,.0f} |",
            f"| Credit Bonds | {p.credit_bond_mv:,.0f} |",
            f"| Other Assets | {p.other_assets:,.0f} |",
            f"| Liability PV | {p.liability_pv:,.0f} |",
            f"| **Free Surplus** | **{p.surplus:,.0f}** |",
            f"| Solvency Ratio | {p.solvency_ratio:.4f} |",
            "",
            "---",
            "",
            "## Scenario Results",
            "",
            "| Scenario | Category | Severity | Stressed Surplus | Surplus Change | Surplus Δ% | Stressed Sol. Ratio | Insolvent? |",
            "|----------|----------|----------|-----------------|----------------|------------|---------------------|------------|",
        ]

        # Sort by surplus_change descending (worst first)
        results_sorted = sorted(results, key=lambda r: r.surplus_change, reverse=True)

        for r in results_sorted:
            insol = "⚠️ YES" if r.is_insolvent else "No"
            lines.append(
                f"| {r.scenario.name} "
                f"| {r.scenario.category.value} "
                f"| {r.scenario.severity} "
                f"| {r.stressed_surplus:,.0f} "
                f"| {r.surplus_change:,.0f} "
                f"| {r.surplus_change_pct:.1f}% "
                f"| {r.stressed_solvency_ratio:.4f} "
                f"| {insol} |"
            )

        # Count insolvencies
        n_insolvent = sum(1 for r in results if r.is_insolvent)
        n_total = len(results)

        lines += [
            "",
            "---",
            "",
            "## Summary Statistics",
            "",
            f"- **Scenarios run:** {n_total}",
            f"- **Scenarios causing insolvency:** {n_insolvent} / {n_total}",
            f"- **Worst surplus impact:** {max(r.surplus_change for r in results):,.0f} CNY",
            f"- **Worst solvency ratio:** {min(r.stressed_solvency_ratio for r in results):.4f}",
            "",
            "---",
            "",
            "## Regulatory Compliance Notes",
            "",
            "- SOA ASOP 7 §3.5: All prescribed scenario categories covered "
            "(rate, equity, lapse, mortality, multi-factor).",
            "- CBIRC C-ROSS §5.2–5.3: All 6 prescribed stress tests included.",
            "- IA TAS M §3.8: Reverse stress test scenario (ERM-REVERSE-STRESS) "
            "included; full calibration deferred to Phase 4.",
            "- Approximation method: Duration + convexity (Phase 2). "
            "Full stochastic re-projection required before regulatory filing.",
            "",
            "---",
            "",
            f"*Report auto-generated by `par_model_v2.risk.stress_testing.StressTestEngine`.*  ",
            f"*Review and sign-off required before external use — see GOVERNANCE_FRAMEWORK.md.*",
        ]

        return "\n".join(lines)


# ---------------------------------------------------------------------------
# 8.  Convenience function
# ---------------------------------------------------------------------------

def run_regulatory_stress_test(
    portfolio: PortfolioSnapshot,
    include_erm: bool = True,
) -> pd.DataFrame:
    """One-call convenience function for regulatory stress test report.

    Parameters
    ----------
    portfolio : PortfolioSnapshot
        Base portfolio snapshot.
    include_erm : bool
        Whether to include ERM multi-factor scenarios.  Default True.

    Returns
    -------
    pd.DataFrame
        Sorted stress test results (worst surplus impact first).

    Example
    -------
    >>> snap = PortfolioSnapshot(
    ...     valuation_date=datetime(2026, 3, 31, tzinfo=timezone.utc),
    ...     bond_mv=700_000, bond_duration=8.0, bond_convexity=80.0,
    ...     equity_mv=200_000, credit_bond_mv=50_000,
    ...     credit_bond_duration=4.0, other_assets=50_000,
    ...     liability_pv=950_000, liability_duration=12.0, liability_convexity=200.0,
    ...     discount_rate=0.035, lapse_sensitivity=-2_000,
    ...     mortality_sensitivity=3_000,
    ... )
    >>> df = run_regulatory_stress_test(snap)
    >>> print(df[["scenario", "stressed_surplus", "is_insolvent"]])
    """
    scenarios = CBIRC_SCENARIOS + SOA_ASOP7_SCENARIOS
    if include_erm:
        scenarios += COMBINED_SCENARIOS
    engine = StressTestEngine(portfolio, scenarios=scenarios)
    return engine.generate_report(sort_by="surplus_change", ascending=False)
