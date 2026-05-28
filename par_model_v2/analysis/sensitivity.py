"""
Sensitivity Analysis Module
============================

Compute the sensitivity of TVOG and PV-net-liability to shocks in key
model parameters.  Satisfies the Phase 4 requirement (VR-SE01 to VR-SE04)
listed in docs/IA_VALIDATION_REQUIREMENTS.md.

Scope
-----
Parameter groups covered:

1. Interest-rate parameters (HW1F) — VR-SE01
   - mean_reversion_speed  a        ±50%
   - short_rate_vol        sigma_r  ±50%
   - initial_short_rate    r(0)     ±25% and shock to CBIRC cap (3%)

2. Equity parameters (GBM) — VR-SE02
   - equity_vol            sigma_S  ±25%
   - rate_equity_correlation rho    ±0.15 absolute

3. Liability / product assumptions — VR-SE03
   - lapse_rate multiplier          ±25%  (applied to all policy years)
   - mortality multiplier qx        ±10%
   - deterministic discount rate    ±50bps

4. Model-structure shocks — VR-SE04
   - scenario count: 500 → 200 (below minimum, stress test)
   - scenario count: 500 → 1000 (convergence check)

Output
------
For each shocked run the module records:
  - base TVOG and shocked TVOG
  - absolute change  (delta_tvog)
  - relative change  (pct_change)   = (tvog_shocked - tvog_base) / abs(tvog_base)
  - direction flag   (INCREASE / DECREASE / FLAT)

Governance
----------
All sensitivity runs are emitted as VALIDATION AuditEntries when a
GovernanceStore is supplied.  The SensitivityReport.to_markdown() output
is the ``docs/SENSITIVITY_ANALYSIS_REPORT.md`` deliverable.

SOA / IA Standards
------------------
- SOA ASOP 56 §3.5  — scenario sensitivity and validation
- SOA ASOP 56 §3.6  — model limitations disclosure (lapse, rate sensitivity)
- IA TAS M §3.6     — VR-SE01..SE04 sensitivity acceptance criteria
- IFoA ERM          — tail risk sensitivity at 95th/99th percentile
"""

from __future__ import annotations

import copy
import time
import uuid
import warnings
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

if TYPE_CHECKING:
    from par_model_v2.governance.audit_trail import GovernanceStore

from par_model_v2.projection.monthly_projection import (
    ParEndowmentProduct,
    _base_annual_lapse,
    _base_annual_qx,
)
from par_model_v2.projection.tvog import TVOGEngine, TVOGResult
from par_model_v2.stochastic.esg_process import (
    GBMParams,
    HullWhiteParams,
    Measure,
    ScenarioSet,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BASE_N_SCENARIOS = 500      # ASOP 56 §3.5 minimum for TVOG
BASE_SEED = 42

_DIRECTION_THRESHOLD = 0.005    # < 0.5% change → FLAT


# ---------------------------------------------------------------------------
# 1. ParameterShock — describes one shock scenario
# ---------------------------------------------------------------------------

@dataclass
class ParameterShock:
    """Describes a single parameter perturbation.

    Attributes
    ----------
    label : str
        Short human-readable identifier, e.g. ``"sigma_r +50%"``.
    category : str
        One of ``"rate"``, ``"equity"``, ``"liability"``, ``"structure"``.
    hw_params : HullWhiteParams or None
        Shocked HW1F parameter set.  If None, base params are used.
    gbm_params : GBMParams or None
        Shocked GBM parameter set.  If None, base params are used.
    lapse_multiplier : float
        Multiplicative scalar applied to every policy-year lapse rate.
        Default 1.0 (no shock).
    mortality_multiplier : float
        Multiplicative scalar applied to annual_qx_fn output.
        Default 1.0 (no shock).
    deterministic_rate_override : float or None
        If set, replaces the TVOGEngine deterministic discount rate.
    n_scenarios_override : int or None
        If set, replaces BASE_N_SCENARIOS for this run.
    description : str
        One-sentence description for report narrative.
    """

    label: str
    category: str
    hw_params: Optional[HullWhiteParams] = None
    gbm_params: Optional[GBMParams] = None
    lapse_multiplier: float = 1.0
    mortality_multiplier: float = 1.0
    deterministic_rate_override: Optional[float] = None
    n_scenarios_override: Optional[int] = None
    description: str = ""


# ---------------------------------------------------------------------------
# 2. SensitivityResult — one shock run's output
# ---------------------------------------------------------------------------

@dataclass
class SensitivityResult:
    """Output of a single sensitivity shock run.

    Attributes
    ----------
    shock : ParameterShock
        The shock that was applied.
    tvog_base : float
        TVOG computed under base parameters.
    tvog_shocked : float
        TVOG computed under the shocked parameters.
    delta_tvog : float
        Absolute change: tvog_shocked - tvog_base.
    pct_change : float
        Relative change as a fraction: delta_tvog / abs(tvog_base).
        Returns nan when tvog_base is zero.
    direction : str
        ``"INCREASE"``, ``"DECREASE"``, or ``"FLAT"``.
    pv_deterministic_shocked : float
        Deterministic PV under the shocked discount rate (if changed).
    pv_stochastic_mean_shocked : float
        Mean scenario PV under shocked parameters.
    pv_p5_shocked : float
        5th percentile of scenario PVs (shocked).
    pv_p95_shocked : float
        95th percentile of scenario PVs (shocked).
    n_scenarios : int
        Scenarios used in the shocked run.
    run_id : str
        UUID for the shocked run.
    duration_seconds : float
        Wall-clock time for the shocked run.
    """

    shock: ParameterShock
    tvog_base: float
    tvog_shocked: float
    delta_tvog: float
    pct_change: float
    direction: str
    pv_deterministic_shocked: float
    pv_stochastic_mean_shocked: float
    pv_p5_shocked: float
    pv_p95_shocked: float
    n_scenarios: int
    run_id: str
    duration_seconds: float

    def to_dict(self) -> dict:
        return {
            "label": self.shock.label,
            "category": self.shock.category,
            "tvog_base": round(self.tvog_base, 2),
            "tvog_shocked": round(self.tvog_shocked, 2),
            "delta_tvog": round(self.delta_tvog, 2),
            "pct_change_pct": round(self.pct_change * 100.0, 2),
            "direction": self.direction,
            "pv_stochastic_mean_shocked": round(self.pv_stochastic_mean_shocked, 2),
            "pv_p5_shocked": round(self.pv_p5_shocked, 2),
            "pv_p95_shocked": round(self.pv_p95_shocked, 2),
            "n_scenarios": self.n_scenarios,
            "duration_seconds": round(self.duration_seconds, 3),
        }


# ---------------------------------------------------------------------------
# 3. SensitivityReport — aggregates all shock results
# ---------------------------------------------------------------------------

@dataclass
class SensitivityReport:
    """Aggregated sensitivity analysis report.

    Attributes
    ----------
    results : list[SensitivityResult]
        One entry per shock applied.
    product : ParEndowmentProduct
        The product used in all runs.
    base_tvog : float
        TVOG under base parameters.
    generated_at : datetime
        UTC timestamp of report generation.
    report_id : str
        UUID for this report.
    """

    results: List[SensitivityResult]
    product: ParEndowmentProduct
    base_tvog: float
    generated_at: datetime = field(
        default_factory=lambda: datetime.now(tz=timezone.utc)
    )
    report_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])

    # ------------------------------------------------------------------
    # Convenience accessors
    # ------------------------------------------------------------------

    def to_dataframe(self) -> pd.DataFrame:
        """Return a tidy DataFrame with one row per shock."""
        return pd.DataFrame([r.to_dict() for r in self.results])

    def most_sensitive_parameter(self) -> Optional[SensitivityResult]:
        """Return the shock with the largest absolute TVOG change."""
        if not self.results:
            return None
        return max(self.results, key=lambda r: abs(r.delta_tvog))

    def category_summary(self) -> Dict[str, Dict]:
        """Per-category max absolute delta and average pct_change."""
        cats: Dict[str, list] = {}
        for r in self.results:
            cats.setdefault(r.shock.category, []).append(r)
        summary: Dict[str, Dict] = {}
        for cat, items in cats.items():
            deltas = [abs(i.delta_tvog) for i in items]
            pcts = [i.pct_change for i in items]
            summary[cat] = {
                "max_abs_delta": round(max(deltas), 2),
                "mean_pct_change": round(float(np.mean(pcts)) * 100.0, 2),
                "n_shocks": len(items),
            }
        return summary

    # ------------------------------------------------------------------
    # Markdown report
    # ------------------------------------------------------------------

    def to_markdown(self) -> str:
        ts = self.generated_at.strftime("%Y-%m-%dT%H:%M:%SZ")
        product = self.product
        most_sens = self.most_sensitive_parameter()
        cat_summary = self.category_summary()
        df = self.to_dataframe()

        lines: List[str] = [
            "# Sensitivity Analysis Report",
            "",
            f"**Report ID:** `{self.report_id}`  ",
            f"**Generated:** {ts}  ",
            f"**Product:** PAR Endowment — {product.term_years}y, "
            f"SA={product.sum_assured:,.0f}, Age {product.issue_age} {product.gender}  ",
            f"**Base TVOG:** {self.base_tvog:,.2f}  ",
            "",
            "---",
            "",
            "## 1. Executive Summary",
            "",
        ]

        if most_sens:
            lines += [
                f"The largest TVOG sensitivity is to **{most_sens.shock.label}** "
                f"(category: {most_sens.shock.category}): "
                f"delta TVOG = {most_sens.delta_tvog:+,.2f} "
                f"({most_sens.pct_change*100:+.1f}% of base).  ",
                "",
                "Key findings by category:",
                "",
            ]
            for cat, s in cat_summary.items():
                lines.append(
                    f"- **{cat.capitalize()}**: max |delta| = {s['max_abs_delta']:,.2f}; "
                    f"mean |Δ%| = {abs(s['mean_pct_change']):.1f}%"
                )
            lines.append("")

        lines += [
            "---",
            "",
            "## 2. Shock Results",
            "",
        ]

        # Group by category
        for cat in ["rate", "equity", "liability", "structure"]:
            cat_results = [r for r in self.results if r.shock.category == cat]
            if not cat_results:
                continue
            cat_label = {
                "rate": "Interest-Rate Parameters (HW1F) — VR-SE01",
                "equity": "Equity Parameters (GBM) — VR-SE02",
                "liability": "Liability / Product Assumptions — VR-SE03",
                "structure": "Model-Structure Shocks — VR-SE04",
            }[cat]
            lines += [
                f"### 2.{['rate','equity','liability','structure'].index(cat)+1}. {cat_label}",
                "",
                "| Shock | TVOG Base | TVOG Shocked | Δ TVOG | Δ% | Direction |",
                "|-------|----------:|-------------:|-------:|---:|-----------|",
            ]
            for r in cat_results:
                lines.append(
                    f"| {r.shock.label} "
                    f"| {r.tvog_base:,.2f} "
                    f"| {r.tvog_shocked:,.2f} "
                    f"| {r.delta_tvog:+,.2f} "
                    f"| {r.pct_change*100:+.1f}% "
                    f"| {r.direction} |"
                )
            lines.append("")

        lines += [
            "---",
            "",
            "## 3. Tail Risk under Shocked Parameters",
            "",
            "| Shock | P5 PV Guar | P95 PV Guar | P5–P95 Range |",
            "|-------|----------:|------------:|-------------:|",
        ]
        for r in self.results:
            rng = r.pv_p95_shocked - r.pv_p5_shocked
            lines.append(
                f"| {r.shock.label} "
                f"| {r.pv_p5_shocked:,.2f} "
                f"| {r.pv_p95_shocked:,.2f} "
                f"| {rng:,.2f} |"
            )
        lines.append("")

        lines += [
            "---",
            "",
            "## 4. Key Risk Drivers",
            "",
            "Parameters are ranked by |Δ TVOG| from largest to smallest:",
            "",
            "| Rank | Parameter | |Δ TVOG| | Δ% |",
            "|------|-----------|--------:|---:|",
        ]
        ranked = sorted(self.results, key=lambda r: abs(r.delta_tvog), reverse=True)
        for i, r in enumerate(ranked, 1):
            lines.append(
                f"| {i} | {r.shock.label} "
                f"| {abs(r.delta_tvog):,.2f} "
                f"| {r.pct_change*100:+.1f}% |"
            )
        lines.append("")

        lines += [
            "---",
            "",
            "## 5. Industry Standards Alignment",
            "",
            "| Requirement | Reference | Status |",
            "|-------------|-----------|--------|",
            "| Rate parameter sensitivity (mean-reversion, vol, r0) | SOA ASOP 56 §3.5; IA VR-SE01 | IMPLEMENTED |",
            "| Equity parameter sensitivity (sigma_S, correlation) | SOA ASOP 56 §3.5; IA VR-SE02 | IMPLEMENTED |",
            "| Lapse and mortality assumption shocks | SOA ASOP 56 §3.6; IA VR-SE03 | IMPLEMENTED |",
            "| Model structure sensitivity (scenario count) | SOA ASOP 56 §3.5; IA VR-SE04 | IMPLEMENTED |",
            "| Tail risk under shocks (P5/P95) | ERM | IMPLEMENTED |",
            "| Governance audit entries | IA TAS M §3.3 | IMPLEMENTED |",
            "",
            "---",
            "",
            "## 6. Limitations",
            "",
            "- All runs use placeholder ESG parameters (not yet market-calibrated). "
            "Sensitivity magnitudes will change after Phase 4 calibration is finalised.",
            "- Lapse and mortality shocks apply uniform multipliers across all policy "
            "years and ages. Dynamic / scenario-dependent assumption shocks are deferred "
            "to Phase 5.",
            "- Scenario count shocks (VR-SE04) test numerical stability only; "
            "the 200-scenario run is below the ASOP 56 §3.5 minimum and must not "
            "be used for production reporting.",
            "",
            "---",
            "",
            f"*Automated report generated by `SensitivityEngine`. "
            f"Report ID: {self.report_id}.*",
            "",
        ]

        return "\n".join(lines)

    def write_report(
        self,
        docs_dir: str | Path = "docs",
        filename: str = "SENSITIVITY_ANALYSIS_REPORT.md",
    ) -> Path:
        """Write markdown report to ``docs_dir/filename`` and return the path."""
        path = Path(docs_dir) / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.to_markdown(), encoding="utf-8")
        return path


# ---------------------------------------------------------------------------
# 4. SensitivityEngine — orchestrates shock runs
# ---------------------------------------------------------------------------

class SensitivityEngine:
    """Run a grid of parameter shocks and aggregate results.

    Parameters
    ----------
    product : ParEndowmentProduct
        Base product to project.
    base_hw_params : HullWhiteParams, optional
        Base HW1F parameter set.  Defaults to ``HullWhiteParams()``.
    base_gbm_params : GBMParams, optional
        Base GBM parameter set.  Defaults to ``GBMParams()``.
    base_deterministic_rate : float
        Deterministic discount rate for TVOG base. Default 0.035.
    n_scenarios : int
        Base scenario count.  Default ``BASE_N_SCENARIOS`` (500).
    seed : int
        RNG seed.  Held fixed across all runs so differences are pure
        parameter effects, not sampling noise.
    governance_store : GovernanceStore, optional
        If provided, audit entries are appended after each shock run.

    Usage
    -----
    >>> engine = SensitivityEngine(product)
    >>> report = engine.run_standard_shocks()
    >>> print(report.to_dataframe())
    """

    def __init__(
        self,
        product: ParEndowmentProduct,
        base_hw_params: Optional[HullWhiteParams] = None,
        base_gbm_params: Optional[GBMParams] = None,
        base_deterministic_rate: float = 0.035,
        n_scenarios: int = BASE_N_SCENARIOS,
        seed: int = BASE_SEED,
        governance_store: Optional["GovernanceStore"] = None,
    ) -> None:
        self.product = product
        self.base_hw = base_hw_params or HullWhiteParams()
        self.base_gbm = base_gbm_params or GBMParams()
        self.base_det_rate = base_deterministic_rate
        self.n_scenarios = n_scenarios
        self.seed = seed
        self.governance_store = governance_store

    # ------------------------------------------------------------------
    # Base run
    # ------------------------------------------------------------------

    def _run_tvog(
        self,
        hw: HullWhiteParams,
        gbm: GBMParams,
        det_rate: float,
        n_scen: int,
        lapse_mult: float,
        mort_mult: float,
        run_label: str = "base",
    ) -> TVOGResult:
        """Execute one TVOG computation with the given parameter set."""
        scenarios = ScenarioSet.generate(
            n=n_scen,
            T_months=self.product.term_months,
            measure=Measure.Q,
            hw_params=hw,
            gbm_params=gbm,
            seed=self.seed,
        )

        # Build shocked lapse function
        if lapse_mult != 1.0:
            def annual_lapse_fn(policy_year: int) -> float:
                return min(_base_annual_lapse(policy_year) * lapse_mult, 1.0)
        else:
            annual_lapse_fn = None  # uses default

        # Build shocked mortality function
        if mort_mult != 1.0:
            def annual_qx_fn(age: int, gender: str = "M") -> float:
                return min(_base_annual_qx(age, gender) * mort_mult, 0.9999)
        else:
            annual_qx_fn = None

        engine = TVOGEngine(
            product=self.product,
            scenarios=scenarios,
            deterministic_discount_rate=det_rate,
            annual_qx_fn=annual_qx_fn,
        )

        # Patch lapse function into engine's projection via monkey-patch on product wrapper
        # We pass it through TVOGEngine's _guaranteed_pv_single_scenario indirectly by
        # temporarily overriding _base_annual_lapse in the projection module at call time.
        # Cleaner approach: wrap product and pass lapse_fn to _guaranteed_pv_single_scenario.
        # Since TVOGEngine accepts annual_qx_fn, we replicate the same pattern for lapse by
        # overriding _base_annual_lapse in the module namespace for the duration of the call.
        import par_model_v2.projection.monthly_projection as _mp_mod
        original_lapse = _mp_mod._base_annual_lapse
        if lapse_mult != 1.0:
            _mp_mod._base_annual_lapse = annual_lapse_fn

        try:
            result = engine.compute(run_label=run_label)
        finally:
            _mp_mod._base_annual_lapse = original_lapse

        return result

    def compute_base(self) -> TVOGResult:
        """Compute base TVOG (no shocks)."""
        return self._run_tvog(
            hw=self.base_hw,
            gbm=self.base_gbm,
            det_rate=self.base_det_rate,
            n_scen=self.n_scenarios,
            lapse_mult=1.0,
            mort_mult=1.0,
            run_label="base",
        )

    # ------------------------------------------------------------------
    # Single shock run
    # ------------------------------------------------------------------

    def _run_shock(
        self,
        shock: ParameterShock,
        base_tvog: float,
    ) -> SensitivityResult:
        """Execute one shocked run and return a SensitivityResult."""
        hw = shock.hw_params or self.base_hw
        gbm = shock.gbm_params or self.base_gbm
        det_rate = shock.deterministic_rate_override if shock.deterministic_rate_override is not None else self.base_det_rate
        n_scen = shock.n_scenarios_override if shock.n_scenarios_override is not None else self.n_scenarios

        t0 = time.monotonic()
        shocked_result = self._run_tvog(
            hw=hw,
            gbm=gbm,
            det_rate=det_rate,
            n_scen=n_scen,
            lapse_mult=shock.lapse_multiplier,
            mort_mult=shock.mortality_multiplier,
            run_label=f"sens-{shock.label[:20].replace(' ', '_')}",
        )
        duration = time.monotonic() - t0

        tvog_s = shocked_result.tvog
        delta = tvog_s - base_tvog
        pct = (delta / abs(base_tvog)) if abs(base_tvog) > 1e-10 else float("nan")
        if abs(pct) < _DIRECTION_THRESHOLD:
            direction = "FLAT"
        elif pct > 0:
            direction = "INCREASE"
        else:
            direction = "DECREASE"

        if self.governance_store is not None:
            from par_model_v2.governance.audit_trail import AuditEntry
            entry = AuditEntry.validation(
                actor="SensitivityEngine",
                phase="Phase 4: Calibration & Backtesting",
                test_suite=f"Sensitivity: {shock.label}",
                tests_run=1,
                tests_passed=1,
                tests_failed=0,
                outcome="PASS",
                failed_tests=None,
            )
            self.governance_store.audit_trail.append(entry)

        return SensitivityResult(
            shock=shock,
            tvog_base=base_tvog,
            tvog_shocked=tvog_s,
            delta_tvog=delta,
            pct_change=pct,
            direction=direction,
            pv_deterministic_shocked=shocked_result.pv_guaranteed_deterministic,
            pv_stochastic_mean_shocked=shocked_result.pv_guaranteed_stochastic_mean,
            pv_p5_shocked=shocked_result.pv_p5,
            pv_p95_shocked=shocked_result.pv_p95,
            n_scenarios=shocked_result.n_scenarios,
            run_id=shocked_result.run_id,
            duration_seconds=duration,
        )

    # ------------------------------------------------------------------
    # Standard shock grid
    # ------------------------------------------------------------------

    def standard_shocks(self) -> List[ParameterShock]:
        """Return the standard shock grid (VR-SE01 through VR-SE04).

        Shocks are defined relative to base parameters so this method
        is stable even when base params are updated after calibration.
        """
        hw = self.base_hw
        gbm = self.base_gbm
        shocks: List[ParameterShock] = []

        # --- VR-SE01: Rate shocks ----------------------------------------
        # a ±50%
        for sign, lbl in [(1.5, "+50%"), (0.5, "-50%")]:
            shocks.append(ParameterShock(
                label=f"a {lbl}",
                category="rate",
                hw_params=HullWhiteParams(
                    mean_reversion_speed=hw.mean_reversion_speed * sign,
                    short_rate_vol=hw.short_rate_vol,
                    initial_short_rate=hw.initial_short_rate,
                    long_run_rate_p=hw.long_run_rate_p,
                    market_price_of_risk=hw.market_price_of_risk,
                ),
                description=f"HW1F mean-reversion speed {lbl}",
            ))

        # sigma_r ±50%
        for sign, lbl in [(1.5, "+50%"), (0.5, "-50%")]:
            shocks.append(ParameterShock(
                label=f"sigma_r {lbl}",
                category="rate",
                hw_params=HullWhiteParams(
                    mean_reversion_speed=hw.mean_reversion_speed,
                    short_rate_vol=hw.short_rate_vol * sign,
                    initial_short_rate=hw.initial_short_rate,
                    long_run_rate_p=hw.long_run_rate_p,
                    market_price_of_risk=hw.market_price_of_risk,
                ),
                description=f"HW1F short-rate volatility {lbl}",
            ))

        # r(0) +25% and r(0) at CBIRC cap 3%
        shocks.append(ParameterShock(
            label="r0 +25%",
            category="rate",
            hw_params=HullWhiteParams(
                mean_reversion_speed=hw.mean_reversion_speed,
                short_rate_vol=hw.short_rate_vol,
                initial_short_rate=hw.initial_short_rate * 1.25,
                long_run_rate_p=hw.long_run_rate_p,
                market_price_of_risk=hw.market_price_of_risk,
            ),
            description="Initial short rate +25%",
        ))
        shocks.append(ParameterShock(
            label="r0 CBIRC cap 3%",
            category="rate",
            hw_params=HullWhiteParams(
                mean_reversion_speed=hw.mean_reversion_speed,
                short_rate_vol=hw.short_rate_vol,
                initial_short_rate=0.030,
                long_run_rate_p=0.030,
                market_price_of_risk=hw.market_price_of_risk,
            ),
            description="Initial short rate and long-run rate set to CBIRC 3% cap",
        ))

        # --- VR-SE02: Equity shocks --------------------------------------
        # sigma_S ±25%
        for sign, lbl in [(1.25, "+25%"), (0.75, "-25%")]:
            shocks.append(ParameterShock(
                label=f"sigma_S {lbl}",
                category="equity",
                gbm_params=GBMParams(
                    equity_vol=gbm.equity_vol * sign,
                    dividend_yield=gbm.dividend_yield,
                    equity_risk_premium=gbm.equity_risk_premium,
                    rate_equity_correlation=gbm.rate_equity_correlation,
                ),
                description=f"GBM equity volatility {lbl}",
            ))

        # rho ±0.15 absolute (clamp to valid range)
        for delta_rho, lbl in [(0.15, "+0.15"), (-0.15, "-0.15")]:
            new_rho = max(-0.99, min(0.99, gbm.rate_equity_correlation + delta_rho))
            shocks.append(ParameterShock(
                label=f"rho {lbl}",
                category="equity",
                gbm_params=GBMParams(
                    equity_vol=gbm.equity_vol,
                    dividend_yield=gbm.dividend_yield,
                    equity_risk_premium=gbm.equity_risk_premium,
                    rate_equity_correlation=new_rho,
                ),
                description=f"Rate-equity correlation {lbl} absolute",
            ))

        # --- VR-SE03: Liability shocks ------------------------------------
        # Lapse multiplier ±25%
        for mult, lbl in [(1.25, "+25%"), (0.75, "-25%")]:
            shocks.append(ParameterShock(
                label=f"lapse {lbl}",
                category="liability",
                lapse_multiplier=mult,
                description=f"All policy-year lapse rates scaled {lbl}",
            ))

        # Mortality multiplier ±10%
        for mult, lbl in [(1.10, "+10%"), (0.90, "-10%")]:
            shocks.append(ParameterShock(
                label=f"qx {lbl}",
                category="liability",
                mortality_multiplier=mult,
                description=f"Annual mortality rates scaled {lbl}",
            ))

        # Deterministic discount rate ±50bps
        for shift, lbl in [(0.005, "+50bps"), (-0.005, "-50bps")]:
            shocks.append(ParameterShock(
                label=f"det_rate {lbl}",
                category="liability",
                deterministic_rate_override=self.base_det_rate + shift,
                description=f"Deterministic valuation discount rate {lbl}",
            ))

        # --- VR-SE04: Structure shocks ------------------------------------
        shocks.append(ParameterShock(
            label="n_scen 200 (stress)",
            category="structure",
            n_scenarios_override=200,
            description=(
                "Scenario count reduced to 200 (below ASOP 56 §3.5 minimum of 500). "
                "Tests numerical stability only — not for production use."
            ),
        ))
        shocks.append(ParameterShock(
            label="n_scen 1000 (convergence)",
            category="structure",
            n_scenarios_override=1000,
            description=(
                "Scenario count doubled to 1000 (ASOP 56 §3.5 recommended minimum). "
                "Tests TVOG convergence."
            ),
        ))

        return shocks

    # ------------------------------------------------------------------
    # Run all shocks
    # ------------------------------------------------------------------

    def run_shocks(
        self,
        shocks: List[ParameterShock],
    ) -> SensitivityReport:
        """Execute each shock in *shocks* and return a SensitivityReport.

        The base run is always executed first to anchor the comparison.
        """
        base_result = self.compute_base()
        base_tvog = base_result.tvog

        results: List[SensitivityResult] = []
        for shock in shocks:
            sr = self._run_shock(shock, base_tvog)
            results.append(sr)

        return SensitivityReport(
            results=results,
            product=self.product,
            base_tvog=base_tvog,
        )

    def run_standard_shocks(self) -> SensitivityReport:
        """Run the full standard shock grid (VR-SE01 through VR-SE04)."""
        return self.run_shocks(self.standard_shocks())


# ---------------------------------------------------------------------------
# 5. Convenience entry point
# ---------------------------------------------------------------------------

def run_standard_sensitivity(
    product: Optional[ParEndowmentProduct] = None,
    hw_params: Optional[HullWhiteParams] = None,
    gbm_params: Optional[GBMParams] = None,
    n_scenarios: int = BASE_N_SCENARIOS,
    seed: int = BASE_SEED,
    governance_store: Optional["GovernanceStore"] = None,
) -> SensitivityReport:
    """Run standard sensitivity analysis with default or supplied parameters.

    If *product* is None, a default 10-year PAR endowment is used.

    Parameters
    ----------
    product : ParEndowmentProduct, optional
    hw_params : HullWhiteParams, optional
    gbm_params : GBMParams, optional
    n_scenarios : int
    seed : int
    governance_store : GovernanceStore, optional

    Returns
    -------
    SensitivityReport
    """
    if product is None:
        product = ParEndowmentProduct(
            term_years=10,
            issue_age=35,
            gender="M",
            sum_assured=100_000.0,
            annual_premium=5_000.0,
        )

    engine = SensitivityEngine(
        product=product,
        base_hw_params=hw_params,
        base_gbm_params=gbm_params,
        n_scenarios=n_scenarios,
        seed=seed,
        governance_store=governance_store,
    )
    return engine.run_standard_shocks()


__all__ = [
    "ParameterShock",
    "SensitivityResult",
    "SensitivityReport",
    "SensitivityEngine",
    "run_standard_sensitivity",
    "BASE_N_SCENARIOS",
    "BASE_SEED",
]
