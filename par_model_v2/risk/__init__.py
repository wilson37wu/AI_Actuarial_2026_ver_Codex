"""
PAR Fund Stochastic Model — Risk Metrics Package
=================================================

Implements tail risk metrics per ERM and SOA ASOP 7 / ASOP 56 requirements.

Modules
-------
risk_metrics :
    Empirical and parametric VaR and Expected Shortfall (ES/CVaR) at
    standard actuarial confidence levels (95%, 99%, 99.5%).
    Works directly with loss distributions derived from scenario sets
    or from deterministic projection results (stress-shifted).
stress_testing :
    Scenario stress testing framework with 15 predefined scenarios across
    CBIRC C-ROSS, SOA ASOP 7, and ERM multi-factor categories. Includes
    StressTestEngine for duration-approximation asset/liability repricing
    and governance-ready markdown report generation.

SOA / ERM Standards Addressed
------------------------------
- ASOP 7  §3.3 : Scenario-based tail risk measurement
- ASOP 7  §3.5 : Scenario selection and stress testing
- ASOP 56 §3.3 : Scenario-based analysis disclosure
- ASOP 56 §3.5 : Scenario adequacy for tail metrics
- ERM Framework : VaR/ES at 99.5% + scenario stress testing for solvency
- CBIRC C-ROSS  : 6 prescribed stress tests (§5.2–5.3)
- IA TAS M §3.8 : Stress testing and sensitivity analysis

Usage
-----
>>> from par_model_v2.risk import StressTestEngine, PortfolioSnapshot
>>> from datetime import datetime, timezone
>>> snap = PortfolioSnapshot(
...     valuation_date=datetime(2026, 3, 31, tzinfo=timezone.utc),
...     bond_mv=700_000, bond_duration=8.0, bond_convexity=80.0,
...     equity_mv=200_000, credit_bond_mv=50_000,
...     credit_bond_duration=4.0, other_assets=50_000,
...     liability_pv=950_000, liability_duration=12.0, liability_convexity=200.0,
...     discount_rate=0.035, lapse_sensitivity=-2_000, mortality_sensitivity=3_000,
... )
>>> engine = StressTestEngine(snap)
>>> df = engine.generate_report()
>>> md = engine.generate_markdown_report()
"""

from par_model_v2.risk.risk_metrics import (
    LossDistribution,
    RiskMetrics,
    RiskReport,
    ConfidenceLevel,
    VaRResult,
    ESResult,
)
from par_model_v2.risk.stress_testing import (
    ShockType,
    ShockSpec,
    ScenarioCategory,
    StressScenario,
    PortfolioSnapshot,
    StressTestResult,
    StressTestEngine,
    CBIRC_SCENARIOS,
    SOA_ASOP7_SCENARIOS,
    COMBINED_SCENARIOS,
    ALL_SCENARIOS,
    run_regulatory_stress_test,
)

__all__ = [
    # risk_metrics
    "LossDistribution",
    "RiskMetrics",
    "RiskReport",
    "ConfidenceLevel",
    "VaRResult",
    "ESResult",
    # stress_testing
    "ShockType",
    "ShockSpec",
    "ScenarioCategory",
    "StressScenario",
    "PortfolioSnapshot",
    "StressTestResult",
    "StressTestEngine",
    "CBIRC_SCENARIOS",
    "SOA_ASOP7_SCENARIOS",
    "COMBINED_SCENARIOS",
    "ALL_SCENARIOS",
    "run_regulatory_stress_test",
]
