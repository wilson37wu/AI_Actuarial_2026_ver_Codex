"""
Backtesting Report Generator
============================

Generate governance-ready markdown reports from Phase 4 backtest results.
The primary deliverable is the annual file documented in
docs/PARAMETER_CALIBRATION_METHODOLOGY.md §9.4:

    docs/CALIBRATION_BACKTEST_REPORT_{YYYY}.md
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from par_model_v2.calibration.backtesting import (
    BACKTEST_MIN_COVERAGE,
    BACKTEST_VAR99_BREACH_LIMIT,
    BacktestDataset,
    BacktestResult,
)
from par_model_v2.calibration.calibration_framework import CalibrationResult


def _status_label(passed: bool) -> str:
    return "PASS" if passed else "FAIL"


@dataclass
class BacktestReport:
    """Markdown report builder for annual backtesting review."""

    calibration_result: CalibrationResult
    dataset: BacktestDataset
    backtest_result: BacktestResult
    report_year: int
    generated_at: datetime = field(default_factory=lambda: datetime.now(tz=timezone.utc))

    def output_path(self, docs_dir: str | Path = "docs") -> Path:
        return Path(docs_dir) / f"CALIBRATION_BACKTEST_REPORT_{self.report_year}.md"

    def tail_conclusion(self) -> str:
        tail = self.backtest_result.tail_summary()
        if self.backtest_result.var99_exception_rate > BACKTEST_VAR99_BREACH_LIMIT:
            return (
                "Tail risk is understated: VaR99 breaches exceed the 5% governance limit "
                "and recalibration is mandatory."
            )
        if tail["max_var99_excess"] > 0.0:
            return (
                "Tail losses show isolated VaR99 breaches, but the running breach rate "
                "remains inside tolerance."
            )
        if self.backtest_result.var95_exception_rate > 0.10:
            return (
                "No VaR99 breach occurred, but the 95th percentile tail is active and "
                "deserves monitoring."
            )
        return "Tail loss experience remains inside the model's current VaR/ES tolerance bands."

    def recommendation(self) -> str:
        if self.backtest_result.requires_recalibration:
            return (
                "Recalibration required before the next annual production cycle. "
                "Focus on widening the P-measure tail and reviewing rate/equity fit."
            )
        return (
            "No immediate recalibration trigger. Continue annual monitoring and replace "
            "the synthetic dataset with external realised CNY market history when available."
        )

    def to_markdown(self) -> str:
        summary = self.backtest_result.summary()
        tail = self.backtest_result.tail_summary()
        worst = self.backtest_result.worst_observation()
        martingale_ok = bool(self.backtest_result.martingale_results.attrs.get("all_pass", False))

        rate_ok = self.backtest_result.rate_coverage_pct >= BACKTEST_MIN_COVERAGE
        equity_ok = self.backtest_result.equity_coverage_pct >= BACKTEST_MIN_COVERAGE
        var99_ok = self.backtest_result.var99_exception_rate <= BACKTEST_VAR99_BREACH_LIMIT

        return f"""# Calibration Backtest Report {self.report_year}

**Generated:** {self.generated_at.isoformat()}  
**Calibration date:** {self.calibration_result.calibration_date.isoformat()}  
**Run ID:** {self.backtest_result.run_id}  
**Observations:** {self.dataset.n_observations} annual points  
**Dataset basis:** synthetic development scaffold (real market history not yet connected)

---

## 1. Executive Summary

- Rate 10th-90th coverage: {self.backtest_result.rate_coverage_pct:.1%} ({_status_label(rate_ok)}; minimum {BACKTEST_MIN_COVERAGE:.0%})
- Equity 10th-90th coverage: {self.backtest_result.equity_coverage_pct:.1%} ({_status_label(equity_ok)}; minimum {BACKTEST_MIN_COVERAGE:.0%})
- VaR95 breach rate: {self.backtest_result.var95_exception_rate:.1%}
- VaR99 breach rate: {self.backtest_result.var99_exception_rate:.1%} ({_status_label(var99_ok)}; maximum {BACKTEST_VAR99_BREACH_LIMIT:.0%})
- Kupiec POF p-values: 95%={self.backtest_result.kupiec_pvalue_95:.3f}, 99%={self.backtest_result.kupiec_pvalue_99:.3f}
- Q-measure martingale control: {_status_label(martingale_ok)}
- Governance trigger: {"RECALIBRATION REQUIRED" if self.backtest_result.requires_recalibration else "MONITOR"}

## 2. Tail Loss Analysis

- Mean VaR95 / ES95: {tail["mean_var95"]:,.0f} / {tail["mean_es95"]:,.0f}
- Mean VaR99 / ES99: {tail["mean_var99"]:,.0f} / {tail["mean_es99"]:,.0f}
- Mean realised excess above VaR95 / VaR99: {tail["mean_var95_excess"]:,.0f} / {tail["mean_var99_excess"]:,.0f}
- Maximum realised excess above VaR95 / VaR99: {tail["max_var95_excess"]:,.0f} / {tail["max_var99_excess"]:,.0f}
- Average realised loss in VaR95 / VaR99 breach years: {tail["avg_realised_loss_var95_breach"]:,.0f} / {tail["avg_realised_loss_var99_breach"]:,.0f}

**Tail conclusion:** {self.tail_conclusion()}

## 3. Worst Observation

- Observation date: {worst["observation_date"]}
- Realised loss: {worst["realised_loss"]:,.0f}
- VaR95 / ES95: {worst["var95"]:,.0f} / {worst["es95"]:,.0f}
- VaR99 / ES99: {worst["var99"]:,.0f} / {worst["es99"]:,.0f}
- VaR95 breach: {"Yes" if worst["var95_breach"] else "No"}
- VaR99 breach: {"Yes" if worst["var99_breach"] else "No"}

## 4. Governance Interpretation

- SOA ASOP 56 §3.5 scenario adequacy: annual rate/equity coverage and tail breach tracking implemented.
- IA TAS M §3.6 validation evidence: backtest detail, Kupiec statistics, and martingale control recorded in code output.
- ERM tail metric view: Expected Shortfall is reported alongside VaR so severe but low-frequency loss years are not hidden by percentile thresholds.

## 5. Recommendation

{self.recommendation()}

## 6. Machine Summary

```json
{json.dumps(summary, indent=2)}
```
"""

    def write(self, docs_dir: str | Path = "docs") -> Path:
        path = self.output_path(docs_dir)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.to_markdown(), encoding="utf-8")
        return path


def generate_backtest_report(
    calibration_result: CalibrationResult,
    dataset: BacktestDataset,
    backtest_result: BacktestResult,
    report_year: Optional[int] = None,
    docs_dir: str | Path = "docs",
) -> Path:
    """Write the annual markdown deliverable and return its path."""
    year = report_year or pd_timestamp_year(dataset)
    report = BacktestReport(
        calibration_result=calibration_result,
        dataset=dataset,
        backtest_result=backtest_result,
        report_year=year,
    )
    return report.write(docs_dir=docs_dir)


def pd_timestamp_year(dataset: BacktestDataset) -> int:
    """Infer the report year from the most recent observation."""
    latest = dataset.observations["observation_date"].max()
    return int(latest.year)


__all__ = [
    "BacktestReport",
    "generate_backtest_report",
]
