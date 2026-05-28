"""
PAR Fund Stochastic Model — Calibration Package
================================================

Provides calibration classes and utilities for ESG parameters:

  HullWhiteCalibrator  — Calibrates HW1F (a, sigma_r) to swaption implied vols
  GBMCalibrator        — Calibrates GBM (sigma_S, ERP, rho) to historical data
  CalibrationResult    — Dataclass holding calibrated parameters + fit stats
  martingale_test      — Validates Q-measure scenarios (Phase 3+)

Standards Reference
-------------------
SOA ASOP 56 s3.4 — Parameter calibration methodology documentation
SOA ASOP 25 s3.3 — Credibility of assumption bases
IA TAS M s3.5    — Assumption appropriateness and sign-off
docs/PARAMETER_CALIBRATION_METHODOLOGY.md — Full specification
"""

from par_model_v2.calibration.calibration_framework import (
    CalibrationResult,
    GBMCalibrationInputs,
    GBMCalibrator,
    HullWhiteCalibrationInputs,
    HullWhiteCalibrator,
    SwaptionQuote,
    martingale_test,
)
from par_model_v2.calibration.backtesting import (
    BACKTEST_HORIZON_MONTHS,
    BacktestDataset,
    BacktestEngine,
    BacktestResult,
)
from par_model_v2.calibration.backtest_reporting import (
    BacktestReport,
    generate_backtest_report,
)

__all__ = [
    "CalibrationResult",
    "GBMCalibrationInputs",
    "GBMCalibrator",
    "HullWhiteCalibrationInputs",
    "HullWhiteCalibrator",
    "SwaptionQuote",
    "martingale_test",
    "BACKTEST_HORIZON_MONTHS",
    "BacktestDataset",
    "BacktestEngine",
    "BacktestResult",
    "BacktestReport",
    "generate_backtest_report",
]
