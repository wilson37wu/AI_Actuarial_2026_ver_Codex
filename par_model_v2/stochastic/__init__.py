"""
par_model_v2.stochastic
=======================

Stochastic process classes for the PAR Fund ESG (Economic Scenario Generator).

Modules
-------
esg_process
    HullWhiteRateProcess  — 1-factor Hull-White interest rate model (stub)
    GBMEquityProcess      — Geometric Brownian Motion equity model (stub)
    ScenarioSet           — Container for simulated scenario paths

Standards compliance
--------------------
SOA ASOP 56 §3.1.3 — stochastic process documentation (Phase 2, Task 1)
SOA ASOP 56 §3.4   — parameter calibration methodology (Phase 4)
SOA ASOP 7          — cash flow analysis under scenarios (Phase 4 integration)
IA TAS M §3.5       — assumption documentation (docs/ESG_PROCESS_DOCUMENTATION.md)

Development status
------------------
Phase 2 (current): Documented stubs — class structure, docstrings, parameter
                   dataclasses, and P/Q measure distinction in place.
                   simulate() methods raise NotImplementedError.

Phase 3: Fix DistributedExecutor pickling bug — unblocks batch simulation.
Phase 4: Implement simulate() bodies; calibrate parameters to market data;
         integrate with MonthlyProjectionEngine for TVOG computation.

Production use restriction
--------------------------
Do NOT use for regulatory reporting, pricing, or external disclosure until
Phase 4 calibration is complete and signed off by the Assumption Owner.
See docs/ESG_PROCESS_DOCUMENTATION.md §9 (Limitations and Disclosures).
"""

from par_model_v2.stochastic.esg_process import (
    HullWhiteParams,
    GBMParams,
    HullWhiteRateProcess,
    GBMEquityProcess,
    CalibrationSource,
    ParameterSnapshot,
    ScenarioSet,
    ScenarioMetadata,
    Measure,
)
from par_model_v2.stochastic.esg_adapter import (
    ESGAdapter,
    ESGAdapterConfig,
    ESGSchemaError,
    ESGRangeError,
    ScenarioAdequacyWarning,
    SCENARIO_MINIMUM_PRODUCTION,
    SCENARIO_MINIMUM_TVOG,
    SCENARIO_RECOMMENDED_TVOG,
    SCENARIO_MINIMUM_VAR,
    SCENARIO_RECOMMENDED_VAR,
)

__all__ = [
    # esg_process
    "HullWhiteParams",
    "GBMParams",
    "HullWhiteRateProcess",
    "GBMEquityProcess",
    "CalibrationSource",
    "ParameterSnapshot",
    "ScenarioSet",
    "ScenarioMetadata",
    "Measure",
    # esg_adapter
    "ESGAdapter",
    "ESGAdapterConfig",
    "ESGSchemaError",
    "ESGRangeError",
    "ScenarioAdequacyWarning",
    "SCENARIO_MINIMUM_PRODUCTION",
    "SCENARIO_MINIMUM_TVOG",
    "SCENARIO_RECOMMENDED_TVOG",
    "SCENARIO_MINIMUM_VAR",
    "SCENARIO_RECOMMENDED_VAR",
]
