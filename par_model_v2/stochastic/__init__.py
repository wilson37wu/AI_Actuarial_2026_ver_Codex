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
    G2PlusParams,
    RiskFreeCurve,
    MartingaleEvidenceCheck,
    MartingaleEvidenceReport,
    QMeasureMartingaleValidator,
    YieldCurveValidationCheck,
    YieldCurveValidationReport,
    YieldCurveValidator,
    GBMParams,
    RegionalEquityFactor,
    available_starter_equity_markets,
    starter_equity_factor,
    default_phase8_equity_factors,
    FXParams,
    FXReturnFactor,
    available_starter_fx_pairs,
    starter_fx_factor,
    fx_factor_for_translation,
    default_phase8_fx_factors,
    phase8_rate_equity_fx_correlation_matrix,
    CorrelationMatrixValidationCheck,
    CorrelationMatrixValidationReport,
    CorrelationMatrixValidator,
    PMeasureBacktestCheck,
    PMeasureBacktestReport,
    PMeasureBacktestValidator,
    HullWhiteRateProcess,
    G2PlusRateProcess,
    GBMEquityProcess,
    JumpDiffusionParams,
    JumpDiffusionEquityProcess,
    build_equity_process,
    resolve_equity_model,
    available_equity_models,
    EQUITY_PROCESS_REGISTRY,
    DEFAULT_EQUITY_MODEL,
    EquityForwardMartingaleValidator,
    FXSpotProcess,
    CalibrationSource,
    CalibrationFieldSpec,
    CalibrationDataInterface,
    default_phase6_calibration_interfaces,
    ParameterSnapshot,
    ScenarioSet,
    ScenarioMetadata,
    ConsumerOutputMapping,
    default_phase6_consumer_mappings,
    phase6_consumer_mapping,
    available_starter_curve_currencies,
    starter_risk_free_curve,
    default_phase7_starter_curves,
    Measure,
)
from par_model_v2.stochastic.g2pp_rate import (
    EnhancedG2PlusRateProcess,
    G2PlusAnalyticDiagnostics,
    GRate2Check,
    GRate2GateReport,
    evaluate_g_rate2_gate,
)
from par_model_v2.stochastic.g2pp_swaption import (
    swap_schedule,
    par_swap_rate,
    black_swaption_price,
    black_implied_vol,
    g2pp_swaption_price,
    educational_proxy_curve,
    educational_proxy_vol_grid,
    calibrate_g2pp_to_swaptions,
    SwaptionCalibrationResult,
    GSwpnCheck,
    GSwpnGateReport,
    evaluate_g_swpn_gate,
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
    "G2PlusParams",
    "RiskFreeCurve",
    "MartingaleEvidenceCheck",
    "MartingaleEvidenceReport",
    "QMeasureMartingaleValidator",
    "YieldCurveValidationCheck",
    "YieldCurveValidationReport",
    "YieldCurveValidator",
    "GBMParams",
    "RegionalEquityFactor",
    "available_starter_equity_markets",
    "starter_equity_factor",
    "default_phase8_equity_factors",
    "FXParams",
    "FXReturnFactor",
    "available_starter_fx_pairs",
    "starter_fx_factor",
    "fx_factor_for_translation",
    "default_phase8_fx_factors",
    "phase8_rate_equity_fx_correlation_matrix",
    "CorrelationMatrixValidationCheck",
    "CorrelationMatrixValidationReport",
    "CorrelationMatrixValidator",
    "PMeasureBacktestCheck",
    "PMeasureBacktestReport",
    "PMeasureBacktestValidator",
    "HullWhiteRateProcess",
    "G2PlusRateProcess",
    "GBMEquityProcess",
    "JumpDiffusionParams",
    "JumpDiffusionEquityProcess",
    "build_equity_process",
    "resolve_equity_model",
    "available_equity_models",
    "EQUITY_PROCESS_REGISTRY",
    "DEFAULT_EQUITY_MODEL",
    "EquityForwardMartingaleValidator",
    "FXSpotProcess",
    "CalibrationSource",
    "CalibrationFieldSpec",
    "CalibrationDataInterface",
    "default_phase6_calibration_interfaces",
    "ParameterSnapshot",
    "ScenarioSet",
    "ScenarioMetadata",
    "ConsumerOutputMapping",
    "default_phase6_consumer_mappings",
    "phase6_consumer_mapping",
    "available_starter_curve_currencies",
    "starter_risk_free_curve",
    "default_phase7_starter_curves",
    "Measure",
    "EnhancedG2PlusRateProcess",
    "G2PlusAnalyticDiagnostics",
    "GRate2Check",
    "GRate2GateReport",
    "evaluate_g_rate2_gate",
    "swap_schedule",
    "par_swap_rate",
    "black_swaption_price",
    "black_implied_vol",
    "g2pp_swaption_price",
    "educational_proxy_curve",
    "educational_proxy_vol_grid",
    "calibrate_g2pp_to_swaptions",
    "SwaptionCalibrationResult",
    "GSwpnCheck",
    "GSwpnGateReport",
    "evaluate_g_swpn_gate",
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
