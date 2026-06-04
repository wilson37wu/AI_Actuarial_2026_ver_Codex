"""
scripts/calibration — Calibration Scripts Package
==================================================

Standalone calibration scripts for each ESG and liability module.
Run individually or via run_all_calibrations.py.

Scripts
-------
calibrate_curves.py
    Hull-White 1F parameter calibration for USD, EUR, HKD, CNY, and JPY yield
    curves using synthetic ATM swaption quotes. Demonstrates the
    L-BFGS-B minimisation of weighted normal-vol errors.

calibrate_equity.py
    GBM parameter calibration for US, EU, HK/CN, JP, and Asia ex-JP equity
    factors. Blends realised historical volatility with option-implied vol
    and calculates bias-adjusted equity risk premia.

calibrate_credit.py
    Credit spread calibration for fixed-income and private-credit instruments.
    Fits spread-duration-adjusted OAS curves and illiquidity premia for private
    credit, PE, and infrastructure.

calibrate_liabilities.py
    Liability assumption calibration for Hong Kong PAR products. Covers
    mortality (HK insured life tables + improvement), voluntary lapse, and
    policyholder bonus expectations for cash-dividend and reversionary-bonus
    product lines.

run_all_calibrations.py
    Orchestrates all four scripts, aggregates results, and writes a combined
    parameter snapshot JSON and a Markdown calibration summary report.

Standards
---------
SOA ASOP 56 s3.4  -- calibration methodology documentation
SOA ASOP 25 s3.3  -- credibility and assumption hierarchy
IA TAS M s3.5     -- assumption appropriateness and sign-off
"""
