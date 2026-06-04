"""
par_model_v2.examples — Phase 12 Guided Educational Examples
=============================================================

This package provides runnable walkthroughs of the six core actuarial workflows
built across Phases 1–11 of the AI Actuarial 2026 model.

Available modules
-----------------
guided_examples
    Six example functions covering pricing, HK participating valuation, TVOG,
    ALM rebalancing, stress testing, and the full reporting-close workflow.

    Quick start::

        from par_model_v2.examples.guided_examples import run_all_examples
        results = run_all_examples()

    Single section::

        from par_model_v2.examples.guided_examples import example_tvog_computation
        tvog_results = example_tvog_computation()

MODEL-USE RESTRICTION
---------------------
All examples use PLACEHOLDER / ILLUSTRATIVE parameters.  They must not be used
for regulatory reporting, MCEV, dividend declarations, or any production actuarial
output.  See docs/PHASE12_MODEL_LIMITATION_CARDS.md for full limitation cards.
"""

from par_model_v2.examples.guided_examples import (
    example_alm_projection,
    example_fixed_income_pricing,
    example_hk_liability_valuation,
    example_reporting_close,
    example_stress_testing,
    example_tvog_computation,
    run_all_examples,
)

__all__ = [
    "run_all_examples",
    "example_fixed_income_pricing",
    "example_hk_liability_valuation",
    "example_tvog_computation",
    "example_alm_projection",
    "example_stress_testing",
    "example_reporting_close",
]
