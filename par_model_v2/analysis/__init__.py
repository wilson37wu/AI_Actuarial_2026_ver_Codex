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
scenario_adequacy
    Monte-Carlo scenario-adequacy convergence study (roadmap §4.1 #5 /
    C-ROSS gap #6): TVOG convergence with 95% CI bands across the
    500->1,000->2,000->5,000 ladder, runtime benchmark, and a scenario-count
    recommendation reconciled against the CBIRC C-ROSS >= 2,000 floor.
"""

from par_model_v2.analysis.sensitivity import (
    ParameterShock,
    SensitivityResult,
    SensitivityReport,
    SensitivityEngine,
    run_standard_sensitivity,
)
from par_model_v2.analysis.scenario_adequacy import (
    CONVERGENCE_SCHEMA,
    DEFAULT_LADDER,
    CBIRC_SCENARIO_FLOOR,
    ConvergencePoint,
    ConvergenceStudyResult,
    run_convergence_study,
)

__all__ = [
    "ParameterShock",
    "SensitivityResult",
    "SensitivityReport",
    "SensitivityEngine",
    "run_standard_sensitivity",
    "CONVERGENCE_SCHEMA",
    "DEFAULT_LADDER",
    "CBIRC_SCENARIO_FLOOR",
    "ConvergencePoint",
    "ConvergenceStudyResult",
    "run_convergence_study",
]
