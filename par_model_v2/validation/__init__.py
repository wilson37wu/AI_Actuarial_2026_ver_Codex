"""
par_model_v2.validation -- IA TAS M paragraph 3.6 / 3.9 Validation Framework
"""

from .ia_validation import (
    IA_VALIDATION_REQUIREMENTS,
    ValidationCategory,
    ValidationReport,
    ValidationRequirement,
    ValidationResult,
    ValidationRunner,
    ValidationStatus,
)

IAValidationReport = ValidationReport

from .data_validator import (
    CheckSeverity,
    CheckResult,
    ValidationReport as DataValidationReport,
    ModelPointValidator,
    MortalityTableValidator,
    LapseTableValidator,
    DiscountRateValidator,
    FullDataValidationReport,
    validate_all,
)

__all__ = [
    "IA_VALIDATION_REQUIREMENTS",
    "IAValidationReport",
    "ValidationCategory",
    "ValidationReport",
    "ValidationRequirement",
    "ValidationResult",
    "ValidationRunner",
    "ValidationStatus",
    "CheckSeverity",
    "CheckResult",
    "DataValidationReport",
    "ModelPointValidator",
    "MortalityTableValidator",
    "LapseTableValidator",
    "DiscountRateValidator",
    "FullDataValidationReport",
    "validate_all",
]

from .model_health import (
    HealthStatus,
    HealthCheckResult,
    HealthReport,
    ModelHealthChecker,
    run_health_checks,
)

__all__ += [
    "HealthStatus",
    "HealthCheckResult",
    "HealthReport",
    "ModelHealthChecker",
    "run_health_checks",
]

# NOTE: the legacy `.validation_dashboard` module was retired in Phase 16 when the
# offline result-viewer (model_result_viewer.html) replaced the in-process
# dashboard. Its import block is intentionally omitted here.

# --- Phase 13 IA TAS M validation suite (re-wired after a prior cycle's
# truncated write; module + tests already on disk) ---
from .phase13_ia_tas_m import (
    Phase13IAValidationResult,
    build_phase13_validation_requirements,
    evaluate_g06_gate,
    run_phase13_ia_tas_m_validation,
)

__all__ += [
    "Phase13IAValidationResult",
    "build_phase13_validation_requirements",
    "evaluate_g06_gate",
    "run_phase13_ia_tas_m_validation",
]

# --- Phase 20 Task 3: market-consistency (martingale) validation gate (G-MART) ---
from .phase20_market_consistency import (
    GMartGateReport,
    MartingaleCheck,
    evaluate_g_mart_gate,
    simulate_hw1f_exact,
)

__all__ += [
    "GMartGateReport",
    "MartingaleCheck",
    "evaluate_g_mart_gate",
    "simulate_hw1f_exact",
]
