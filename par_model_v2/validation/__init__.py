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
