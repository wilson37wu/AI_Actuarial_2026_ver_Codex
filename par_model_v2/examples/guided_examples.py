"""
Phase 12 Task 3 — Guided Examples: Pricing, Valuation, TVOG, ALM, Stress, Reporting Close
===========================================================================================

Runnable educational walkthroughs of the six core actuarial workflows implemented across
Phases 1–11 of this model.  Each example section is a self-contained function that can be
called individually or via ``run_all_examples()``.

Section layout
--------------
1. ``example_fixed_income_pricing()``     — bond/liability present-value pricing
2. ``example_hk_liability_valuation()``   — HK participating product valuation (cash
                                            dividend & reversionary bonus)
3. ``example_tvog_computation()``         — TVOG under Q-measure stochastic scenarios
4. ``example_alm_projection()``           — DynamicALMEngine SAA rebalancing over 12 months
5. ``example_stress_testing()``           — asset-class deterministic stress scenarios
6. ``example_reporting_close()``          — full reporting-cycle workflow (assumption lock →
                                            model run → validation → sign-off)

Industry standards alignment
----------------------------
SOA ASOP 56 §3.1  — stochastic model documentation and use disclosure
SOA ASOP 56 §3.3  — model limitations explicitly documented per component
SOA ASOP 25 §3.3  — scenario generation adequacy
IA TAS M §3.2     — market-consistent valuation methodology
IA TAS M §3.6     — assumption-to-output traceability
ERM framework     — VaR/ES tail risk, scenario stress, governance evidence

MODEL-USE RESTRICTION
---------------------
All parameters are EDUCATIONAL PLACEHOLDERS.  This module must NOT be used for
regulatory capital, MCEV reporting, dividend declarations, or any other decision
that requires calibrated actuarial inputs.  See docs/PHASE12_MODEL_LIMITATION_CARDS.md
for full component-level limitation cards.
"""

from __future__ import annotations

import json
import warnings
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Section 1 — Fixed Income Pricing
# ---------------------------------------------------------------------------

def example_fixed_income_pricing() -> Dict[str, Any]:
    """
    Demonstrate present-value pricing of a fixed-income bond and a liability cashflow
    stream using the Phase 7 RiskFreeCurve and Phase 9 FixedIncomeInstrument.

    Concepts covered
    ----------------
    - Constructing a risk-free discount curve from starter market parameters
    - Computing dirty price and duration of a sovereign bond
    - Pricing a simple liability annuity-certain against the same curve
    - Measuring convexity impact from a parallel rate shift (+100 bps)

    SOA ASOP 56 §3.1 — economic scenario generator must identify measure,
                        calibration date, and model equations.
    IA TAS M §3.2    — market-consistent valuation: discount at risk-free + illiquidity
                        premium where applicable.

    MODEL-USE RESTRICTION: Starter curve parameters are illustrative approximations
    of USD market conditions; do not use for regulatory or MCEV reporting.
    """
    from par_model_v2.stochastic import RiskFreeCurve, starter_risk_free_curve
    from par_model_v2.projection.fixed_income import (
        FixedIncomeInstrument,
        FixedIncomeProjectionResult,
        project_fixed_income_cashflows,
        fixed_income_market_value_after_shock,
        default_phase9_fixed_income_instruments,
    )

    print("\n" + "=" * 70)
    print("SECTION 1: Fixed Income Pricing")
    print("=" * 70)

    # --- 1a. Build a USD risk-free curve -----------------------------------
    # API NOTE (MR-009 migration): RiskFreeCurve now exposes valuation_date,
    # curve_id, source_id, and a discount_factor(tenor_years) method (no longer
    # a precomputed discount_factors list or calibration_date/model_label attrs).
    print("\n[1a] USD Risk-Free Curve (starter parameters, illustrative)")
    usd_curve = starter_risk_free_curve("USD")
    usd_curve_label = f"{usd_curve.curve_id} ({usd_curve.compounding} compounding)"
    print(f"     Currency: {usd_curve.currency}")
    print(f"     Valuation date: {usd_curve.valuation_date}")
    print(f"     Curve: {usd_curve_label}")
    # Sample discount factors at 1, 5, 10 years via the discount_factor() method
    for yr in (1, 5, 10):
        df = usd_curve.discount_factor(yr)
        rate_implied = -np.log(df) / yr if df > 0 else float("nan")
        print(f"       {yr:2d}Y  DF={df:.6f}  implied spot rate={rate_implied*100:.3f}%")

    # --- 1b. Price a government coupon bond --------------------------------
    # API NOTE (MR-009 migration): the Phase 9 FixedIncomeInstrument now carries
    # market_value / duration_years / spread_bps fields, and pricing is done via
    # fixed_income_market_value_after_shock(instrument, rate_shift_bps=...).
    print("\n[1b] Government Coupon Bond — Base Pricing")
    instruments = default_phase9_fixed_income_instruments()
    govt_bond = next((b for b in instruments if b.asset_class == "Government"), instruments[0])
    mv_base = fixed_income_market_value_after_shock(govt_bond, rate_shift_bps=0)
    modified_duration = float(govt_bond.duration_years)
    print(f"     Instrument: {govt_bond.instrument_id}")
    print(f"     Asset class: {govt_bond.asset_class}  Currency: {govt_bond.currency}")
    print(f"     Coupon: {govt_bond.coupon_rate*100:.2f}%  Maturity: {govt_bond.maturity_years:.1f}y"
          f"  Credit rating: {govt_bond.credit_rating}")
    print(f"     Market value (base): {mv_base:>12,.2f}")
    print(f"     Modified duration:   {modified_duration:>12.4f} years")
    print(f"     Spread (OAS):        {govt_bond.spread_bps:>12.0f} bps")

    # --- 1c. Rate shock: +100 bps parallel shift ----------------------------
    print("\n[1c] Rate Sensitivity: +100 bps Parallel Shift")
    mv_shocked = fixed_income_market_value_after_shock(govt_bond, rate_shift_bps=100)
    dollar_impact = mv_shocked - mv_base
    pct_impact = dollar_impact / mv_base * 100 if mv_base != 0 else 0.0
    print(f"     Market value (+100 bps): {mv_shocked:>12,.2f}")
    print(f"     Dollar impact:           {dollar_impact:>12,.2f}")
    print(f"     % impact:                {pct_impact:>12.3f}%")
    # Duration approximation cross-check
    approx_impact = -modified_duration * 0.01 * 100  # 100 bps = 1%
    print(f"     Duration approx %:       {approx_impact:>12.3f}%  (cross-check)")
    print("     → +100 bps lowers MV (positive duration); magnitude ≈ duration × shift")

    # --- 1d. Liability annuity-certain pricing -------------------------------
    print("\n[1d] Liability Annuity-Certain (10-year, monthly payments of 500)")
    monthly_payment = 500.0
    pv_liability = sum(
        monthly_payment * usd_curve.discount_factor(m / 12.0)
        for m in range(1, 121)
    )
    print(f"     PV of liability stream: {pv_liability:>12,.2f}")
    print("     (Annuity-certain at USD risk-free; add illiquidity premium for insurance liabilities)")

    print("\n[SOA/IA Notes]")
    print("  SOA ASOP 56 §3.1: Curve valuation date and curve_id documented above.")
    print("  IA TAS M §3.2: Risk-free discount; illiquidity premium adjustment omitted here — add for insurance liabilities.")
    print("  MODEL LIMITATION: Parameters are starter placeholders; recalibrate before any regulatory use.")

    return {
        "section": "fixed_income_pricing",
        "usd_curve_model": usd_curve_label,
        "govt_bond_id": govt_bond.instrument_id,
        "market_value_base": round(mv_base, 2),
        "modified_duration": round(modified_duration, 4),
        "market_value_shocked_100bps": round(mv_shocked, 2),
        "dollar_impact_100bps": round(dollar_impact, 2),
        "pv_liability_annuity_10yr": round(pv_liability, 2),
    }


# ---------------------------------------------------------------------------
# Section 2 — HK Participating Liability Valuation
# ---------------------------------------------------------------------------

def example_hk_liability_valuation() -> Dict[str, Any]:
    """
    Demonstrate Phase 10 HK participating product valuation for:
      (a) Cash Dividend product (HKCD_PAR_2026)
      (b) Reversionary Bonus product (HKRB_PAR_2026)

    Concepts covered
    ----------------
    - Loading sample policies for each product line
    - Building annual dividend / bonus schedules
    - Computing the guaranteed vs non-guaranteed cashflow split
    - Viewing the asset-share support status over the projection horizon
    - Reading the bonus supportability ratio

    SOA ASOP 56 §3.1 — model must document product mechanics and guarantee split
    IA TAS M §3.6    — traceability from product definition to cashflow output
    ERM             — bonus supportability is a key ALM risk metric

    MODEL-USE RESTRICTION: Declaration assumptions are illustrative dummies.
    Do not use for actual bonus declarations or reserve certifications.
    """
    from par_model_v2.projection.hk_participating import (
        default_hk_cash_dividend_mechanics,
        sample_hk_cash_dividend_policies,
        annual_cash_dividend_schedule,
        hk_cash_dividend_asset_share_support_test,
        default_hk_reversionary_bonus_mechanics,
        sample_hk_reversionary_bonus_policies,
        annual_reversionary_bonus_schedule,
        reversionary_bonus_guarantee_split,
        hk_reversionary_bonus_asset_share_support_test,
        default_hk_declaration_assumption,
    )
    from par_model_v2.projection.monthly_projection import (
        ParEndowmentProduct,
        run_full_projection,
        project_asset_share,
    )

    print("\n" + "=" * 70)
    print("SECTION 2: HK Participating Liability Valuation")
    print("=" * 70)

    decl = default_hk_declaration_assumption()

    # --- 2a. Cash Dividend product -----------------------------------------
    print("\n[2a] HK Cash Dividend Product (HKCD_PAR_2026)")
    cd_mechanics = default_hk_cash_dividend_mechanics()
    # API NOTE (MR-009 migration): sample_*_policies() no longer takes `n`; it
    # returns a default set of sample policies. Asset-share support tests now use
    # the `fund_positions=` kwarg and report `is_supported` / `final_support_ratio`
    # (the old overall_status / annual_view fields were removed).
    cd_policies = sample_hk_cash_dividend_policies()
    pol = cd_policies[0]
    print(f"     Policy ID: {pol.policy_id}")
    print(f"     Product:   {pol.product_code}  |  Term: {pol.term_years}yr  |  Issue age: {pol.issue_age}")
    print(f"     Sum Assured: {pol.sum_assured:,.0f}  |  Annual premium: {pol.annual_premium:,.0f}")
    print(f"     Dividend option: {pol.dividend_option}")

    sched = annual_cash_dividend_schedule(pol, cd_mechanics, decl)
    # Display first 5 rows (annual declaration view)
    display = sched.head(5)[["policy_year", "declared_cash_dividend_rate", "cash_dividend",
                              "guarantee_status"]].copy()
    print("\n     Cash Dividend Schedule (first 5 rows):")
    print(display.to_string(index=False))

    # Asset-share support test
    from par_model_v2.projection.hk_participating import default_hk_asset_share_fund_positions
    fund_positions = default_hk_asset_share_fund_positions(scale=0.01)
    cd_support = hk_cash_dividend_asset_share_support_test(pol, cd_mechanics, decl,
                                                            fund_positions=fund_positions)
    cd_status = "SUPPORTED" if cd_support.is_supported else "UNSUPPORTED"
    print(f"\n     Asset-share support — final year ratio: {cd_support.final_support_ratio:.4f}")
    print(f"     Overall support status: {cd_status}")

    # --- 2b. Reversionary Bonus product ------------------------------------
    print("\n[2b] HK Reversionary Bonus Product (HKRB_PAR_2026)")
    rb_mechanics = default_hk_reversionary_bonus_mechanics()
    rb_policies = sample_hk_reversionary_bonus_policies()
    rb_pol = rb_policies[0]
    print(f"     Policy ID: {rb_pol.policy_id}")
    print(f"     Product:   {rb_pol.product_code}  |  Term: {rb_pol.term_years}yr  |  Issue age: {rb_pol.issue_age}")
    print(f"     Sum Assured: {rb_pol.sum_assured:,.0f}  |  Bonus option: {rb_pol.bonus_option}")

    rb_sched = annual_reversionary_bonus_schedule(rb_pol, rb_mechanics, decl)
    rb_display = rb_sched.head(5)[["policy_year", "declared_reversionary_bonus_rate",
                                    "annual_vested_bonus_addition", "vested_bonus_balance"]].copy()
    print("\n     Annual Reversionary Bonus Schedule (first 5 rows):")
    print(rb_display.to_string(index=False))

    # API NOTE (MR-009 migration): reversionary_bonus_guarantee_split now returns a
    # dict with the guaranteed maturity benefit and a discretionary terminal-bonus
    # percentage (rather than guaranteed/non_guaranteed benefit columns). The
    # guaranteed fraction is derived as 1 / (1 + terminal_bonus_pct).
    guar_split = reversionary_bonus_guarantee_split(rb_pol, rb_mechanics, decl)
    total_guar = float(guar_split["total_guaranteed_maturity_benefit"])
    terminal_bonus_pct = float(guar_split["terminal_bonus_pct"])
    total_nonguar = total_guar * terminal_bonus_pct  # discretionary terminal bonus
    print(f"\n     Total guaranteed maturity benefit:              {total_guar:>12,.0f}")
    print(f"     Terminal (non-guaranteed) bonus component:      {total_nonguar:>12,.0f}")
    guar_pct = total_guar / (total_guar + total_nonguar) * 100 if (total_guar + total_nonguar) > 0 else 0
    print(f"     Guaranteed fraction: {guar_pct:.1f}%  (ERM: lower = more discretionary = more ALM risk)")

    rb_support = hk_reversionary_bonus_asset_share_support_test(rb_pol, rb_mechanics, decl,
                                                                  fund_positions=fund_positions)
    rb_status = "SUPPORTED" if rb_support.is_supported else "UNSUPPORTED"
    print(f"     RB asset-share support status: {rb_status}")

    print("\n[SOA/IA Notes]")
    print("  SOA ASOP 56 §3.1: Product mechanics (guarantee split, declaration rules) documented in hk_participating.py.")
    print("  IA TAS M §3.6: Policy ID → declaration assumption → cashflow schedule → support status chain is auditable.")
    print("  ERM: Asset-share support ratio < 1.0 signals dividend/bonus is unsupported — governance escalation required.")

    return {
        "section": "hk_liability_valuation",
        "cash_dividend": {
            "policy_id": pol.policy_id,
            "product_code": pol.product_code,
            "overall_support_status": cd_status,
        },
        "reversionary_bonus": {
            "policy_id": rb_pol.policy_id,
            "product_code": rb_pol.product_code,
            "guaranteed_pct": round(guar_pct, 2),
            "overall_support_status": rb_status,
        },
    }


# ---------------------------------------------------------------------------
# Section 3 — TVOG Computation
# ---------------------------------------------------------------------------

def example_tvog_computation() -> Dict[str, Any]:
    """
    Demonstrate Q-measure TVOG computation using the Phase 4 TVOGEngine.

    Concepts covered
    ----------------
    - Generating a Q-measure ScenarioSet (risk-neutral Hull-White + GBM paths)
    - Running TVOGEngine.compute() for a 10-year PAR endowment
    - Interpreting the TVOG as the cost of the embedded interest-rate guarantee
    - Sensitivity: TVOG change from a 50 bps lower deterministic discount rate

    SOA ASOP 25 §3.3  — scenario adequacy (minimum 500 scenarios for TVOG)
    SOA ASOP 56 §3.5  — stochastic result confidence and convergence
    IA TAS M §3.2     — market-consistent valuation under Q-measure
    IFoA MCEV §7      — TVOG = stochastic mean PV − deterministic best-estimate PV

    MODEL-USE RESTRICTION: ESG parameters are PLACEHOLDERS.  TVOG results are
    illustrative convergence evidence only and must not be used for MCEV or
    Pillar 2 capital reporting.
    """
    from par_model_v2.projection.monthly_projection import ParEndowmentProduct
    from par_model_v2.stochastic.esg_process import ScenarioSet, Measure
    from par_model_v2.projection.tvog import TVOGEngine

    print("\n" + "=" * 70)
    print("SECTION 3: TVOG Computation")
    print("=" * 70)

    # --- 3a. Define product ------------------------------------------------
    product = ParEndowmentProduct(
        term_years=10,
        issue_age=35,
        gender="M",
        sum_assured=100_000,
        annual_premium=5_000,
    )
    print(f"\n[3a] Product: {product.term_years}yr PAR endowment  |  SA={product.sum_assured:,.0f}"
          f"  |  Age {product.issue_age}{product.gender}")
    print(f"     Term months: {product.term_months}")

    # --- 3b. Generate Q-measure scenarios (1,000 scenarios for speed) -------
    print("\n[3b] Generating 1,000 Q-measure scenarios (seeded, reproducible)")
    print("     NOTE: ASOP 56 §3.5 minimum is 500; production TVOG typically uses 5,000+")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")  # suppress ASOP 56 scenario-count advisory for 1k
        scenarios_q = ScenarioSet.generate(
            n=1_000,
            T_months=product.term_months,
            measure=Measure.Q,
            seed=42,
        )
    print(f"     Scenarios generated: {scenarios_q.n_scenarios}")
    print(f"     Horizon: {scenarios_q.T_months} months  |  Measure: {scenarios_q.measure}")

    # Sample short-rate statistics across paths at month 60
    month60_rates = scenarios_q.data[scenarios_q.data["month"] == 60]["r_short"]
    print(f"     r_short at month 60: mean={month60_rates.mean()*100:.3f}%"
          f"  p5={month60_rates.quantile(0.05)*100:.3f}%"
          f"  p95={month60_rates.quantile(0.95)*100:.3f}%")

    # --- 3c. Compute TVOG at base discount rate (3.5%) ----------------------
    print("\n[3c] TVOG at base deterministic rate = 3.50%")
    engine_base = TVOGEngine(product, scenarios_q, deterministic_discount_rate=0.035)
    result_base = engine_base.compute(run_label="guided-example-base")
    # API NOTE (MR-009 migration): TVOGResult guarantee-PV fields are now
    # pv_guaranteed_stochastic_mean / pv_guaranteed_deterministic.
    print(f"     PV stochastic mean:  {result_base.pv_guaranteed_stochastic_mean:>12,.2f}")
    print(f"     PV deterministic:    {result_base.pv_guaranteed_deterministic:>12,.2f}")
    print(f"     TVOG:                {result_base.tvog:>12,.2f}")
    print(f"     TVOG / SA:           {result_base.tvog / product.sum_assured * 100:>11.3f}%")
    print(f"     PV p5 / p95:         {result_base.pv_p5:>12,.2f}  /  {result_base.pv_p95:>12,.2f}")
    if result_base.tvog < 0:
        print("     ⚠ Negative TVOG flagged — may indicate parameter mis-specification")

    # --- 3d. Sensitivity: lower discount rate by 50 bps ---------------------
    print("\n[3d] Sensitivity: deterministic rate = 3.00% (−50 bps)")
    engine_low = TVOGEngine(product, scenarios_q, deterministic_discount_rate=0.030)
    result_low = engine_low.compute(run_label="guided-example-low-rate")
    tvog_delta = result_low.tvog - result_base.tvog
    print(f"     TVOG at 3.00%:       {result_low.tvog:>12,.2f}")
    print(f"     TVOG change (Δ):     {tvog_delta:>12,.2f}")
    print(f"     Direction: {'TVOG increased (lower rate raises deterministic PV less than stochastic mean, widening gap)' if tvog_delta > 0 else 'TVOG decreased'}")

    # --- 3e. Convergence check: 500 vs 1,000 scenarios ----------------------
    print("\n[3e] Convergence check: 500 vs 1,000 scenarios")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        sc_500 = ScenarioSet.generate(n=500, T_months=product.term_months, measure=Measure.Q, seed=42)
    eng_500 = TVOGEngine(product, sc_500, deterministic_discount_rate=0.035)
    res_500 = eng_500.compute(run_label="guided-conv-500")
    print(f"     TVOG (500 scen):   {res_500.tvog:>12,.2f}")
    print(f"     TVOG (1000 scen):  {result_base.tvog:>12,.2f}")
    print(f"     Δ convergence:     {abs(result_base.tvog - res_500.tvog):>12,.2f}")
    print("     (Small Δ → TVOG is converging; production runs should use 5,000+ for tighter SE)")

    print("\n[SOA/IA Notes]")
    print("  ASOP 56 §3.5: n_scenarios=1,000 meets minimum; disclose SE in production reporting.")
    print("  IA TAS M §3.2: Q-measure enforced; P-measure TVOG is not market-consistent.")
    print("  IFoA MCEV §7: TVOG = stochastic mean PV − deterministic PV (option value convention).")

    return {
        "section": "tvog_computation",
        "product_term_years": product.term_years,
        "sum_assured": product.sum_assured,
        "n_scenarios": scenarios_q.n_scenarios,
        "pv_stochastic_mean": round(result_base.pv_guaranteed_stochastic_mean, 2),
        "pv_deterministic_3_5pct": round(result_base.pv_guaranteed_deterministic, 2),
        "tvog_base": round(result_base.tvog, 2),
        "tvog_low_rate_3pct": round(result_low.tvog, 2),
        "tvog_delta_minus50bps": round(tvog_delta, 2),
        "tvog_convergence_500_vs_1000": round(abs(result_base.tvog - res_500.tvog), 2),
    }


# ---------------------------------------------------------------------------
# Section 4 — ALM Projection
# ---------------------------------------------------------------------------

def example_alm_projection() -> Dict[str, Any]:
    """
    Demonstrate the Phase 3 DynamicALMEngine with a 12-month SAA rebalancing
    simulation.

    Concepts covered
    ----------------
    - Defining a Strategic Asset Allocation policy (Govt/Credit/Equity/Cash)
    - Starting from a 100% Cash portfolio (the Phase 3 bug-fix scenario)
    - Running 12 monthly ALM steps with constant assumed returns
    - Reading per-period SAA deviations and transaction costs
    - Viewing final portfolio composition vs target

    SOA ASOP 56 §3.1 — ALM model must document rebalancing assumptions and
                        transaction cost rates
    ERM              — SAA drift without rebalancing creates basis risk; model
                        governance requires regular rebalancing evidence
    IA TAS M         — asset-share projection must use realistic investment
                        return assumptions

    MODEL-USE RESTRICTION: Return assumptions are illustrative constants.
    Stochastic returns should be drawn from the Phase 7–8 ESG for production ALM.
    """
    from par_model_v2.projection.dynamic_alm import (
        DynamicALMEngine,
        SAAPolicy,
        PortfolioState,
        ASSET_CLASSES,
    )

    print("\n" + "=" * 70)
    print("SECTION 4: ALM Projection (12-Month SAA Rebalancing)")
    print("=" * 70)

    # --- 4a. Define SAA policy ----------------------------------------------
    saa = SAAPolicy(
        weights={
            "Govt":   0.40,   # 40% government bonds
            "Credit": 0.25,   # 25% investment-grade credit
            "Equity": 0.25,   # 25% equity (HK PAR illustrative)
            "Cash":   0.10,   # 10% cash / liquidity buffer
        },
        rebalancing_threshold=0.05,    # rebalance when any class drifts > 5%
        buy_cost_rate=0.002,           # 20 bps buy cost
        sell_cost_rate=0.001,          # 10 bps sell cost
    )
    print("\n[4a] SAA Policy")
    for cls, w in saa.weights.items():
        print(f"     {cls:<8} target: {w*100:.0f}%")
    print(f"     Rebalancing threshold: {saa.rebalancing_threshold*100:.0f}%  |  "
          f"Buy cost: {saa.buy_cost_rate*100:.1f} bps  |  Sell cost: {saa.sell_cost_rate*100:.1f} bps")

    # --- 4b. Start from 100% Cash (Phase 3 VR-U02 bug-fix scenario) --------
    initial_mv = 1_000_000.0
    initial_portfolio = PortfolioState(
        holdings={"Govt": 0.0, "Credit": 0.0, "Equity": 0.0, "Cash": initial_mv},
        period=0,
    )
    print(f"\n[4b] Initial Portfolio (100% Cash — VR-U02 bug-fix scenario)")
    print(f"     Total MV: {initial_portfolio.total_mv():>12,.0f}")
    for cls in ASSET_CLASSES:
        print(f"     {cls:<8}: {initial_portfolio.holdings.get(cls, 0.0):>12,.0f}")

    # --- 4c. Constant annual return assumptions (illustrative) -------------
    annual_returns = {
        "Govt":   0.035,   # 3.5%  government bond yield
        "Credit": 0.050,   # 5.0%  investment-grade credit return
        "Equity": 0.080,   # 8.0%  equity total return (HK market illustrative)
        "Cash":   0.020,   # 2.0%  money market / HIBOR-linked
    }
    print("\n[4c] Annual Return Assumptions (constant, illustrative)")
    for cls, r in annual_returns.items():
        print(f"     {cls:<8}: {r*100:.1f}%")
    print("     NOTE: Use Phase 7–8 ESG stochastic paths for production ALM.")

    # --- 4d. Run 12-month ALM simulation ------------------------------------
    print("\n[4d] 12-Month ALM Simulation")
    engine = DynamicALMEngine(saa)
    results = engine.run(initial_portfolio, n_periods=12, annual_returns=annual_returns)

    # Period-by-period summary
    summary_rows = []
    for r in results:
        pf = r.portfolio_after_rebalancing
        total = pf.total_mv()
        w = pf.weights()
        summary_rows.append({
            "period": r.period,
            "total_mv": round(total, 0),
            "Govt%": round(w.get("Govt", 0) * 100, 1),
            "Credit%": round(w.get("Credit", 0) * 100, 1),
            "Equity%": round(w.get("Equity", 0) * 100, 1),
            "Cash%": round(w.get("Cash", 0) * 100, 1),
            "rebalanced": "Y" if r.rebalancing_triggered else "N",
            "cost": round(r.total_transaction_cost, 0),
        })

    df_summary = pd.DataFrame(summary_rows)
    print(df_summary.to_string(index=False))

    # Final portfolio analysis
    final = results[-1].portfolio_after_rebalancing
    final_total = final.total_mv()
    final_weights = final.weights()
    print(f"\n     Final MV: {final_total:>12,.0f}  (growth: {(final_total/initial_mv - 1)*100:.3f}%)")
    total_cost = sum(r.total_transaction_cost for r in results)
    print(f"     Total transaction costs: {total_cost:>10,.0f}  ({total_cost/initial_mv*100:.3f}% of initial MV)")
    rebalanced_months = sum(1 for r in results if r.rebalancing_triggered)
    print(f"     Months with rebalancing: {rebalanced_months}/12")

    # SAA deviation at end
    final_dev = results[-1].saa_deviation_after
    print("\n     Final SAA Deviation (after rebalancing):")
    for cls in ASSET_CLASSES:
        dev = final_dev.get(cls, 0.0)
        print(f"       {cls:<8}: {dev*100:+.3f}%")

    print("\n[SOA/IA Notes]")
    print("  SOA ASOP 56 §3.1: SAA weights, threshold, and costs documented as model assumptions.")
    print("  ERM: 100%-cash start triggers BUY trades in period 1 (VR-U02 fix); verify rebalancing==Y above.")
    print("  Production: replace constant returns with scenario-path returns from Phase 7–8 ESG.")

    return {
        "section": "alm_projection",
        "saa_weights": saa.weights,
        "initial_mv": initial_mv,
        "final_mv": round(final_total, 2),
        "growth_pct": round((final_total / initial_mv - 1) * 100, 4),
        "total_transaction_cost": round(total_cost, 2),
        "months_rebalanced": rebalanced_months,
        "final_weights": {cls: round(final_weights.get(cls, 0) * 100, 2) for cls in ASSET_CLASSES},
    }


# ---------------------------------------------------------------------------
# Section 5 — Stress Testing
# ---------------------------------------------------------------------------

def example_stress_testing() -> Dict[str, Any]:
    """
    Demonstrate Phase 9 deterministic asset-class stress tests and the Phase 8
    correlation matrix / P-measure backtest scaffold.

    Concepts covered
    ----------------
    - Running the default Phase 9 asset stress scenarios (rate shock, credit
      spread widen, equity crash, combined)
    - Reading the stress-result DataFrame sorted by impact
    - Identifying the worst-case scenario and driver asset class
    - Correlation matrix PSD validation for the Phase 8 multi-market ESG

    ERM framework     — tail risk stress tests mandatory; scenario descriptions
                        must be documented per ERM governance
    SOA ASOP 46       — scenario documentation requirement for stress tests
    IA TAS M §3.6     — stress results must be traceable to input scenario def

    MODEL-USE RESTRICTION: Stress scenarios are illustrative.  Magnitudes must be
    calibrated to the insurer's specific risk profile and regulatory guidance.
    """
    from par_model_v2.projection.asset_stress import (
        run_asset_class_stress_tests,
        default_phase9_asset_stress_scenarios,
    )
    from par_model_v2.stochastic.esg_process import CorrelationMatrixValidator

    print("\n" + "=" * 70)
    print("SECTION 5: Stress Testing")
    print("=" * 70)

    # --- 5a. Asset class stress scenarios -----------------------------------
    print("\n[5a] Phase 9 Asset Class Stress Scenarios")
    scenarios = default_phase9_asset_stress_scenarios()
    print(f"     Stress scenarios defined: {len(scenarios)}")
    # API NOTE (MR-009 migration): AssetStressScenario field is now `description`
    # (was scenario_description). run_asset_class_stress_tests now returns an
    # AssetStressReport; the per-instrument detail is on `.stress_results`.
    for s in scenarios:
        print(f"       {s.scenario_id:<30}  {s.description}")

    # --- 5b. Run stress tests -----------------------------------------------
    print("\n[5b] Running Stress Tests")
    stress_report = run_asset_class_stress_tests(scenarios)
    stress_df = stress_report.stress_results
    total_rows = len(stress_df)
    print(f"     Stress result rows: {total_rows}")

    # Aggregate by scenario: sum market value impact
    agg = (
        stress_df
        .groupby(["scenario_id", "scenario_description"])
        .agg(
            n_instruments=("instrument_id", "count"),
            total_base_mv=("base_market_value", "sum"),
            total_stressed_mv=("stressed_market_value", "sum"),
            total_impact=("market_value_impact", "sum"),
        )
        .reset_index()
    )
    agg["impact_pct"] = agg["total_impact"] / agg["total_base_mv"] * 100
    agg = agg.sort_values("total_impact")  # worst first

    print("\n     Scenario Summary (sorted worst to best):")
    display_cols = ["scenario_id", "total_base_mv", "total_stressed_mv", "total_impact", "impact_pct"]
    print(agg[display_cols].to_string(index=False, float_format=lambda x: f"{x:,.1f}"))

    # Worst scenario details
    worst_row = agg.iloc[0]
    worst_id = worst_row["scenario_id"]
    print(f"\n     Worst scenario: {worst_id}")
    worst_detail = stress_df[stress_df["scenario_id"] == worst_id].sort_values("market_value_impact")
    print("     Top 5 impacted instruments:")
    top5 = worst_detail.head(5)[["instrument_id", "asset_class", "base_market_value",
                                  "market_value_impact", "impact_pct", "stress_driver"]]
    print(top5.to_string(index=False))

    # --- 5c. Correlation matrix PSD validation -----------------------------
    print("\n[5c] Phase 8 Correlation Matrix — PSD Validation")
    from par_model_v2.stochastic.esg_process import phase8_rate_equity_fx_correlation_matrix
    corr_matrix = phase8_rate_equity_fx_correlation_matrix()
    n = corr_matrix.shape[0]
    print(f"     Correlation matrix dimensions: {n}×{n}")

    # API NOTE (MR-009 migration): CorrelationMatrixValidator is now constructed
    # with tolerances and exposes validate_matrix(matrix, repair=...), returning a
    # CorrelationMatrixValidationReport whose .diagnostics dict holds min_eigenvalue
    # and whose .repaired flag indicates whether PSD repair was applied.
    validator = CorrelationMatrixValidator()
    report = validator.validate_matrix(corr_matrix, repair=True)
    min_eig = float(report.diagnostics["min_eigenvalue"])
    validation = {
        "is_psd": bool(min_eig >= -1e-9),
        "min_eigenvalue": min_eig,
        "psd_repair_applied": bool(report.repaired),
    }
    print(f"     Is positive semi-definite: {validation['is_psd']}")
    print(f"     Min eigenvalue: {validation['min_eigenvalue']:.6f}")
    if validation["psd_repair_applied"]:
        print("     ⚠ PSD repair applied (nearest-PSD method) — check repair magnitude")
    else:
        print("     ✓ No repair needed — matrix is valid for Cholesky decomposition")

    print("\n[SOA/IA Notes]")
    print("  SOA ASOP 46: Each stress scenario has documented description and driver.")
    print("  ERM: Worst-case scenario identified above; escalate to risk committee if impact_pct > threshold.")
    print("  IA TAS M §3.6: scenario_id links stress result to input definition (audit trail).")

    return {
        "section": "stress_testing",
        "n_scenarios": len(scenarios),
        "n_stress_rows": total_rows,
        "worst_scenario_id": worst_id,
        "worst_scenario_total_impact": round(float(worst_row["total_impact"]), 2),
        "worst_scenario_impact_pct": round(float(worst_row["impact_pct"]), 3),
        "correlation_matrix_is_psd": bool(validation["is_psd"]),
        "correlation_min_eigenvalue": round(float(validation["min_eigenvalue"]), 6),
    }


# ---------------------------------------------------------------------------
# Section 6 — Reporting Close
# ---------------------------------------------------------------------------

def example_reporting_close() -> Dict[str, Any]:
    """
    Demonstrate the Phase 11 reporting-cycle workflow: assumption lock → model
    run → validation suite → output review → sign-off pack.

    Concepts covered
    ----------------
    - Locking projection assumptions (mortality, lapse, bonus, discount, expense)
    - Creating a model run record from the locked assumptions
    - Running the Phase 11 validation suite (movement, reconciliation, TVOG,
      seed stability)
    - Building the output review with embedded validation status
    - Assembling the sign-off pack (JSON + Markdown) as governance evidence

    IA TAS M §3.6     — assumption-to-output traceability chain required
    SOA ASOP 56 §3.2  — governance: model outputs must be validated before use
    SOA ASOP 56 §3.3  — model limitations and restrictions must be documented
    ERM               — sign-off pack constitutes evidence for model governance

    MODEL-USE RESTRICTION: Assumption values are dummy placeholders.  Validation
    thresholds are illustrative.  The sign-off pack must not be used as actual
    actuarial sign-off evidence.
    """
    import tempfile
    from pathlib import Path
    from par_model_v2.projection.reporting_cycle import (
        default_projection_assumptions,
        ReportingCycleConfig,
        run_reporting_cycle,
    )
    from par_model_v2.projection.portfolio_generator import (
        generate_hk_par_portfolio,
        PortfolioGenerationConfig,
    )

    print("\n" + "=" * 70)
    print("SECTION 6: Reporting Close Workflow")
    print("=" * 70)

    # API NOTE (MR-009 migration): the reporting cycle is now driven by the
    # high-level orchestrator run_reporting_cycle(portfolio, assumptions, config),
    # which performs all five stages (lock → chunked run → validation → review →
    # sign-off pack) and returns a SignOffPack carrying the lock, run_record,
    # validation, and review sub-objects. The old hand-assembled ModelRunRecord /
    # run_validation_suite(run_record, lock) / SignOffPack.assemble() API was
    # removed; ProjectionAssumption no longer has category/unit fields.

    # --- 6a. Assumption snapshot -------------------------------------------
    print("\n[6a] Assumption Lock — Snapshot all projection assumptions")
    assumptions = default_projection_assumptions()
    print(f"     Assumptions defined: {len(assumptions)}")
    for a in assumptions[:5]:
        print(f"       {a.name:<22} = {a.value}   ({a.label})")
    if len(assumptions) > 5:
        print(f"       ... and {len(assumptions) - 5} more")

    # --- 6b. Build a small synthetic HK PAR portfolio ----------------------
    print("\n[6b] Synthetic HK PAR Portfolio (educational, small for speed)")
    portfolio_result = generate_hk_par_portfolio(
        PortfolioGenerationConfig(n_policies=200, seed=2026)
    )
    portfolio = portfolio_result.policies
    print(f"     Policies generated: {len(portfolio):,}")
    print(f"     Portfolio digest:   {portfolio_result.digest[:16]}...  (SHA-256, reproducible)")

    # --- 6c. Run the full reporting cycle ----------------------------------
    print("\n[6c] Run Reporting Cycle — lock → run → validation → review → sign-off")
    cycle_cfg = ReportingCycleConfig(
        output_dir=Path(tempfile.mkdtemp(prefix="guided_reporting_")),
        cycle_label="Guided Example Reporting Cycle",
        locked_by="guided-example-user",
        reviewer="guided-example-AA",
        chunk_size=50,
        auto_approve=True,
    )
    pack = run_reporting_cycle(portfolio, assumptions=assumptions, config=cycle_cfg)

    lock = pack.lock
    run_record = pack.run_record
    validation = pack.validation
    review = pack.review

    print(f"     Lock ID:        {lock.lock_id}")
    print(f"     Locked by:      {lock.locked_by}   at {lock.created_at}")
    print(f"     Digest:         {lock.digest[:16]}...  (SHA-256 of assumption snapshot)")
    print(f"     Run ID:         {run_record.run_id}  (refs lock {run_record.lock_id})")
    print(f"     Reconciliation: {'PASSED' if run_record.reconciliation_passed else 'FAILED'}"
          f"  ({run_record.n_chunks_done}/{run_record.n_chunks} chunks)")

    # --- 6d. Validation suite results --------------------------------------
    n_checks = len(validation.checks)
    overall_status = getattr(validation.overall_status, "value", str(validation.overall_status))
    print("\n[6d] Validation Suite — Post-run checks")
    print(f"     Checks run:   {n_checks}")
    print(f"     PASS:         {validation.n_pass}")
    print(f"     FAIL:         {validation.n_fail}")
    print(f"     WARN:         {validation.n_warn}")
    print(f"     SKIP:         {validation.n_skip}")
    print(f"     Overall status: {overall_status}")
    if validation.n_fail > 0:
        fails = [c for c in validation.checks
                 if getattr(c.status, "value", str(c.status)) == "FAIL"]
        for f in fails:
            print(f"     ⚠ FAIL: [{f.check_id}] {f.check_name} — {f.message}")
    else:
        print("     ✓ All checks PASSED, WARNED, or SKIPPED")

    # --- 6e. Output review + sign-off governance checklist -----------------
    print("\n[6e] Output Review & Sign-Off Pack — Governance evidence")
    print(f"     Review ID:      {review.review_id}  (reviewer: {review.reviewer})")
    print(f"     Approved:       {review.approved}")
    print(f"     Pack ID:        {pack.pack_id}")
    print(f"     Governance cleared: {pack.governance_cleared}  |  Blockers: {len(pack.blockers)}")

    # Derive a five-gate governance checklist from the cycle outcome.
    checklist = [
        ("G1 Assumptions locked",   bool(lock.lock_id)),
        ("G2 Reconciliation passed", bool(run_record.reconciliation_passed)),
        ("G3 Validation no failures", validation.n_fail == 0),
        ("G4 Output review approved", bool(review.approved)),
        ("G5 Sign-off governance cleared", bool(pack.governance_cleared)),
    ]
    n_total = len(checklist)
    n_complete = sum(1 for _, ok in checklist if ok)
    print(f"     Sign-off checklist: {n_complete}/{n_total} gates complete")
    for label, ok in checklist:
        print(f"       {'✓' if ok else '○'} {label}")

    print("\n[SOA/IA Notes]")
    print("  IA TAS M §3.6: Full chain: lock_id → run_id → validation → review_id → pack_id.")
    print("  SOA ASOP 56 §3.2: Validation suite must pass before results leave the model.")
    print("  ERM: Sign-off pack is governance evidence; store with version-controlled model outputs.")

    return {
        "section": "reporting_close",
        "lock_id": lock.lock_id,
        "run_id": run_record.run_id,
        "n_assumptions": len(assumptions),
        "validation_n_checks": n_checks,
        "validation_n_pass": validation.n_pass,
        "validation_n_fail": validation.n_fail,
        "validation_overall_status": overall_status,
        "sign_off_pack_id": pack.pack_id,
        "checklist_complete": n_complete,
        "checklist_total": n_total,
    }


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

def run_all_examples(sections: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    Run all six guided example sections and return a consolidated results dict.

    Parameters
    ----------
    sections : list of str, optional
        Subset of section keys to run.  Defaults to all six.
        Valid keys: "pricing", "valuation", "tvog", "alm", "stress", "reporting"

    Returns
    -------
    dict
        Keys are section names; values are per-section result dicts.

    Example
    -------
    >>> from par_model_v2.examples.guided_examples import run_all_examples
    >>> results = run_all_examples()
    >>> print(results["tvog"]["tvog_base"])

    MODEL-USE RESTRICTION: Educational only. See module docstring.
    """
    all_sections = {
        "pricing":   example_fixed_income_pricing,
        "valuation": example_hk_liability_valuation,
        "tvog":      example_tvog_computation,
        "alm":       example_alm_projection,
        "stress":    example_stress_testing,
        "reporting": example_reporting_close,
    }

    run_keys = sections if sections else list(all_sections.keys())

    print("\n" + "=" * 70)
    print("PHASE 12 — GUIDED EXAMPLES: Educational Actuarial Model Walkthroughs")
    print("=" * 70)
    print(f"Sections to run: {run_keys}")
    print(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")
    print(f"\nMODEL-USE RESTRICTION: EDUCATIONAL ONLY. NOT FOR REGULATORY OR")
    print(f"PRODUCTION REPORTING. See docs/PHASE12_MODEL_LIMITATION_CARDS.md.")

    results: Dict[str, Any] = {}
    errors: Dict[str, str] = {}

    for key in run_keys:
        fn = all_sections.get(key)
        if fn is None:
            print(f"\n[SKIP] Unknown section key: {key!r}")
            continue
        try:
            result = fn()
            results[key] = result
            print(f"\n[OK] Section '{key}' completed.")
        except Exception as exc:
            msg = f"{type(exc).__name__}: {exc}"
            errors[key] = msg
            print(f"\n[ERROR] Section '{key}' failed: {msg}")

    print("\n" + "=" * 70)
    print("GUIDED EXAMPLES COMPLETE")
    print("=" * 70)
    print(f"Sections completed: {len(results)}/{len(run_keys)}")
    if errors:
        print(f"Sections with errors: {list(errors.keys())}")
        results["_errors"] = errors

    return results


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser(
        description="Phase 12 guided examples for the educational actuarial model."
    )
    parser.add_argument(
        "--sections",
        nargs="*",
        choices=["pricing", "valuation", "tvog", "alm", "stress", "reporting"],
        default=None,
        help="Run only the listed sections (default: all).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Dump the results dict as JSON to stdout after the run.",
    )
    args = parser.parse_args()

    results = run_all_examples(sections=args.sections)

    if args.json:
        print("\n--- JSON RESULTS ---")
        print(json.dumps(results, indent=2, default=str))

    # Exit non-zero if any section errored
    if "_errors" in results:
        sys.exit(1)
