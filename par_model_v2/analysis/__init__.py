"""
par_model_v2.analysis
=====================

Analytical tools for model diagnostics and governance reporting.

Modules
-------
sensitivity
    Sensitivity analysis of TVOG and liability metrics to key model
    parameters.  Implements VR-SE01 through VR-SE04 from the IA
    validation registry.
"""

from par_model_v2.analysis.sensitivity import (
    ParameterShock,
    SensitivityResult,
    SensitivityReport,
    SensitivityEngine,
    run_standard_sensitivity,
)

__all__ = [
    "ParameterShock",
    "SensitivityResult",
    "SensitivityReport",
    "SensitivityEngine",
    "run_standard_sensitivity",
]
