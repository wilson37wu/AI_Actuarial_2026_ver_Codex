"""CF-1 - Liability & Asset Cash-Flow Projection Set (owner directive 2026-07-03).

Owner requirement (interactive session): a NEW OUTPUT SET containing
liability and asset cash-flow projections -

  * LIABILITY, by product class x cash-flow type: premium inflow, expense
    cash flow, and benefit cash flow SPLIT guaranteed vs non-guaranteed
    ACROSS the surrender / death / maturity buckets (plus the cash-dividend
    outflow for cash-dividend products - at least 6 populated buckets for a
    CD product);
  * ASSET, by asset class: cash flows AND balance (market-value) projection;
  * both on MONTHLY and YEARLY grids up to 100 years (1,200 months).

BASIS (owner-selected 2026-07-03): deterministic CENTRAL projection -
best-estimate decrements (the governed base mortality / lapse tables from
``monthly_projection``), the governed reserving discount cap, and the
educational Phase 10 HK declaration mechanics.  This is a CASH-FLOW view,
not a capital figure: governed headline results (TVOG / SCR aggregation)
are untouched.  Declaration scales are the Phase 10 educational
placeholders and remain UNSIGNED pending owner approval.

GUARANTEED vs NON-GUARANTEED convention (documented, ASOP 56 3.4):
benefits funded by SUM ASSURED + bonuses ALREADY VESTED at the valuation
date count as guaranteed; benefits funded by FUTURE declarations (future
reversionary bonus accrual, terminal bonus, cash dividends, equity account
excess over guarantee) count as non-guaranteed.  Surrender values are split
in proportion to the guaranteed / non-guaranteed share of the projected
benefit at the surrender month.

Product mechanics (all reuse in-repo conventions):
  * HKRB_PAR_2026 - Phase 10 RB mechanics: annual RB vesting at the
    educational declaration rate, terminal bonus % of vested RB at maturity
    (non-guaranteed), surrender at ``surrender_value_pct`` x asset-share
    proxy;
  * HKCD_PAR_2026 - Phase 10 CD mechanics: annual cash dividend at the
    anniversary (non-guaranteed, does NOT vest into death/maturity),
    guaranteed SA death/maturity, surrender guaranteed;
  * GMMB_EQ_2026  - central-growth account proxy with guaranteed maturity
    floor: guarantee = SA, account excess = non-guaranteed; surrender pays
    the account (non-guaranteed).

Decrements, premium timing and expense loadings mirror
``monthly_projection.project_liability_cashflows`` exactly (regression-
tested), so this set is CONSISTENT with the existing per-product engine.
"""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from par_model_v2.projection.hk_participating import (
    default_hk_cash_dividend_mechanics,
    default_hk_declaration_assumption,
    default_hk_reversionary_bonus_mechanics,
)
from par_model_v2.projection.monthly_projection import (
    DEFAULT_RESERVING_DISCOUNT_RATE,
    _base_annual_lapse,
    _base_annual_qx,
    monthly_mortality_qx,
)

SCHEMA_VERSION = "cf-projection-set-1.0"
HORIZON_YEARS = 100
HORIZON_MONTHS = HORIZON_YEARS * 12

#: expense loadings - identical to project_liability_cashflows defaults
ACQ_EXPENSE_PCT = 0.08
RENEWAL_EXPENSE_PCT = 0.04
RENEWAL_EXPENSE_FIXED_MONTHLY = 12.50

#: liability bucket columns (the owner's cash-flow types)
LIABILITY_BUCKETS = [
    "premium",
    "expense",
    "death_guaranteed",
    "death_non_guaranteed",
    "maturity_guaranteed",
    "maturity_non_guaranteed",
    "surrender_guaranteed",
    "surrender_non_guaranteed",
    "cash_dividend",
    "annuity_guaranteed",
]

UNSIGNED_NOTE = (
    "Deterministic central cash-flow projection on educational Phase 10 "
    "declaration scales (RB 2.5%, TB 35%, CD 1.2% of SA) - UNSIGNED pending "
    "Model Owner approval; not a governed capital result."
)

#: asset-class mechanics keyed by loader label prefix (documented defaults;
#: bonds amortise and reinvest in-class so the book stays level, equity
#: compounds, cash rolls at the short rate)
ASSET_CLASS_MECHANICS = {
    "government": {"kind": "bond", "annual_yield": 0.032, "avg_maturity_years": 10.0},
    "corporate": {"kind": "bond", "annual_yield": 0.042, "avg_maturity_years": 7.0},
    "private": {"kind": "bond", "annual_yield": 0.060, "avg_maturity_years": 5.0},
    "infrastructure": {"kind": "bond", "annual_yield": 0.055, "avg_maturity_years": 12.0},
    "equity": {"kind": "equity", "annual_dividend_yield": 0.025,
               "annual_capital_growth": 0.045},
    "cash": {"kind": "cash", "annual_yield": 0.020},
}
_DEFAULT_ASSET_MECHANICS = {"kind": "bond", "annual_yield": 0.040,
                            "avg_maturity_years": 7.0}


# ---------------------------------------------------------------------------
# Liability projection - one model-point row
# ---------------------------------------------------------------------------

@dataclass
class _RowBuckets:
    """Monthly bucket arrays (length HORIZON_MONTHS) for one portfolio row."""
    arrays: Dict[str, np.ndarray] = field(default_factory=lambda: {
        b: np.zeros(HORIZON_MONTHS) for b in LIABILITY_BUCKETS})


def _decrements(issue_age: int, gender: str, term_months: int,
                qx_mult: float = 1.0, lapse_mult: float = 1.0,
                lapse_stop_month: Optional[int] = None):
    """Monthly qx / lapse / in-force arrays - IDENTICAL conventions to
    ``project_liability_cashflows`` (UDD monthly qx, annual lapse / 12,
    BOM in-force recursion), regression-tested against it.

    PC-2: optional per-product decrement overrides - ``qx_mult`` /
    ``lapse_mult`` scale the base tables (capped at 1.0 monthly);
    ``lapse_stop_month`` zeroes lapse from that month on (annuity
    post-vesting lock-in).  Defaults reproduce the base tables EXACTLY."""
    T = term_months
    q = np.zeros(T)
    l = np.zeros(T)
    in_force = np.zeros(T + 1)
    in_force[0] = 1.0
    for m in range(T):
        age = issue_age + m / 12.0
        policy_year = (m // 12) + 1
        q[m] = min(1.0, qx_mult * monthly_mortality_qx(
            _base_annual_qx(int(age), gender)))
        if lapse_stop_month is not None and m >= lapse_stop_month:
            l[m] = 0.0
        else:
            l[m] = min(1.0, lapse_mult * _base_annual_lapse(policy_year) / 12.0)
        in_force[m + 1] = in_force[m] * (1.0 - q[m]) * (1.0 - l[m])
    return q, l, in_force


def _premium_expense(prem_monthly: float, prem_annual: float, count: float,
                     in_force: np.ndarray, term_months: int,
                     out: _RowBuckets,
                     acq_pct: float = ACQ_EXPENSE_PCT,
                     ren_pct: float = RENEWAL_EXPENSE_PCT,
                     ren_fixed: float = RENEWAL_EXPENSE_FIXED_MONTHLY) -> None:
    """Premium + expense columns - IDENTICAL loadings to the legacy engine:
    acquisition 8% x ANNUAL premium at month 0 only; renewal (4% x monthly
    premium + fixed per policy) per in-force from month 1.  ``prem_*`` are
    PER-POLICY amounts; ``count`` scales to the model-point row.

    PC-2: the three loadings are per-product overridable (catalogue
    ``acq_expense_pct`` / ``renewal_expense_pct`` /
    ``renewal_expense_fixed_monthly``); defaults = the governed constants."""
    for m in range(term_months):
        prob_bom = in_force[m]
        out.arrays["premium"][m] += count * prem_monthly * prob_bom
        if m == 0:
            out.arrays["expense"][m] += (
                count * acq_pct * prem_annual * prob_bom)
        else:
            out.arrays["expense"][m] += count * (
                ren_pct * prem_monthly + ren_fixed) * prob_bom


def _asset_share_proxy(prem_monthly: float, prem_annual: float,
                       term_months: int, r_annual: float,
                       acq_pct: float = ACQ_EXPENSE_PCT,
                       ren_pct: float = RENEWAL_EXPENSE_PCT,
                       ren_fixed: float = RENEWAL_EXPENSE_FIXED_MONTHLY
                       ) -> np.ndarray:
    """Surrender-value basis proxy per policy - IDENTICAL recursion to the
    legacy engine: NET premium (after the same expense loadings) accumulated
    monthly at the reserving rate.  PC-2: expense loadings overridable in
    lock-step with ``_premium_expense`` so the surrender basis stays
    consistent with the booked expenses."""
    acc = np.zeros(term_months + 1)
    r_m = r_annual / 12.0
    for m in range(term_months):
        if m == 0:
            net = prem_monthly - acq_pct * prem_annual
        else:
            net = prem_monthly - (ren_pct * prem_monthly + ren_fixed)
        acc[m + 1] = (acc[m] + net) * (1.0 + r_m)
    return acc


def _row_overrides(ov: Dict[str, Any]) -> Dict[str, float]:
    """PC-2 - per-product expense/decrement overrides from the catalogue
    (``portfolio_construction.OVERRIDE_PARAMS``); absent keys fall back to
    the governed defaults so legacy rows project bit-identically."""
    return {
        "acq_pct": float(ov.get("acq_expense_pct", ACQ_EXPENSE_PCT)),
        "ren_pct": float(ov.get("renewal_expense_pct", RENEWAL_EXPENSE_PCT)),
        "ren_fixed": float(ov.get("renewal_expense_fixed_monthly",
                                  RENEWAL_EXPENSE_FIXED_MONTHLY)),
        "qx_mult": float(ov.get("mortality_multiplier", 1.0)),
        "lapse_mult": float(ov.get("lapse_multiplier", 1.0)),
    }


def _project_rb_row(row: Dict[str, Any], out: _RowBuckets) -> None:
    mech = default_hk_reversionary_bonus_mechanics()
    decl = default_hk_declaration_assumption()
    ov = row.get("mechanics") or {}  # PC-1 catalogue overrides
    sa = float(row["sum_assured"])
    initial_vb = float(row.get("vested_bonus") or 0.0)
    T = min(int(row["term_years"]) * 12, HORIZON_MONTHS)
    count = float(row["policy_count"])
    prem_a = float(row["annual_premium"])
    prem_m = prem_a / 12.0
    ex = _row_overrides(ov)
    q, l, in_force = _decrements(int(row["issue_age"]), row["gender"], T,
                                 qx_mult=ex["qx_mult"],
                                 lapse_mult=ex["lapse_mult"])
    _premium_expense(prem_m, prem_a, count, in_force, T, out,
                     acq_pct=ex["acq_pct"], ren_pct=ex["ren_pct"],
                     ren_fixed=ex["ren_fixed"])
    acc = _asset_share_proxy(prem_m, prem_a, T,
                             DEFAULT_RESERVING_DISCOUNT_RATE,
                             acq_pct=ex["acq_pct"], ren_pct=ex["ren_pct"],
                             ren_fixed=ex["ren_fixed"])
    rb_rate = float(ov.get("rb_rate",
                            decl.declared_reversionary_bonus_rate(mech)))
    tb_pct = float(ov.get("terminal_bonus_pct", mech.terminal_bonus_pct))
    svp = float(ov.get("surrender_value_pct", mech.surrender_value_pct))
    future_rb = 0.0
    for m in range(T):
        if m > 0 and m % 12 == 0:  # anniversary vesting of FUTURE declarations
            future_rb += rb_rate * sa
        prob_bom = in_force[m]
        deaths = prob_bom * q[m]
        lapses = prob_bom * (1.0 - q[m]) * l[m]
        guar_ben = sa + initial_vb
        nong_ben = future_rb + tb_pct * future_rb * (m / max(T - 1, 1))
        out.arrays["death_guaranteed"][m] += count * guar_ben * deaths
        out.arrays["death_non_guaranteed"][m] += count * future_rb * deaths
        sv = svp * acc[m + 1] * lapses
        g_w = guar_ben / max(guar_ben + nong_ben, 1e-12)
        out.arrays["surrender_guaranteed"][m] += count * sv * g_w
        out.arrays["surrender_non_guaranteed"][m] += count * sv * (1.0 - g_w)
    survivors = in_force[T]
    final_future_rb = future_rb + (rb_rate * sa if T % 12 == 0 and T > 0 else 0.0)
    out.arrays["maturity_guaranteed"][T - 1] += count * survivors * (sa + initial_vb)
    out.arrays["maturity_non_guaranteed"][T - 1] += count * survivors * (
        final_future_rb + tb_pct * (initial_vb + final_future_rb))


def _project_cd_row(row: Dict[str, Any], out: _RowBuckets) -> None:
    mech = default_hk_cash_dividend_mechanics()
    decl = default_hk_declaration_assumption()
    sa = float(row["sum_assured"])
    T = min(int(row["term_years"]) * 12, HORIZON_MONTHS)
    count = float(row["policy_count"])
    prem_a = float(row["annual_premium"])
    prem_m = prem_a / 12.0
    ov = row.get("mechanics") or {}  # PC-1/PC-2 catalogue overrides
    ex = _row_overrides(ov)
    q, l, in_force = _decrements(int(row["issue_age"]), row["gender"], T,
                                 qx_mult=ex["qx_mult"],
                                 lapse_mult=ex["lapse_mult"])
    _premium_expense(prem_m, prem_a, count, in_force, T, out,
                     acq_pct=ex["acq_pct"], ren_pct=ex["ren_pct"],
                     ren_fixed=ex["ren_fixed"])
    acc = _asset_share_proxy(prem_m, prem_a, T,
                             DEFAULT_RESERVING_DISCOUNT_RATE,
                             acq_pct=ex["acq_pct"], ren_pct=ex["ren_pct"],
                             ren_fixed=ex["ren_fixed"])
    div_rate = float(ov.get("cash_dividend_rate",
                            decl.declared_cash_dividend_rate(mech)))
    svp = float(ov.get("surrender_value_pct", mech.surrender_value_pct))
    for m in range(T):
        prob_bom = in_force[m]
        deaths = prob_bom * q[m]
        lapses = prob_bom * (1.0 - q[m]) * l[m]
        out.arrays["death_guaranteed"][m] += (
            count * sa * mech.death_benefit_multiple * deaths)
        # cash dividends do NOT vest: surrender value is guaranteed CV only
        out.arrays["surrender_guaranteed"][m] += count * svp * acc[m + 1] * lapses
        if m > 0 and m % 12 == 0:  # anniversary cash dividend to in-force
            out.arrays["cash_dividend"][m] += count * div_rate * sa * prob_bom
    out.arrays["maturity_guaranteed"][T - 1] += (
        count * in_force[T] * sa * mech.guaranteed_maturity_multiple)


def _project_gmmb_row(row: Dict[str, Any], out: _RowBuckets) -> None:
    sa = float(row["sum_assured"])  # the maturity guarantee
    T = min(int(row["term_years"]) * 12, HORIZON_MONTHS)
    count = float(row["policy_count"])
    prem_a = float(row["annual_premium"])
    prem_m = prem_a / 12.0
    ov = row.get("mechanics") or {}  # PC-1/PC-2 catalogue overrides
    ex = _row_overrides(ov)
    q, l, in_force = _decrements(int(row["issue_age"]), row["gender"], T,
                                 qx_mult=ex["qx_mult"],
                                 lapse_mult=ex["lapse_mult"])
    _premium_expense(prem_m, prem_a, count, in_force, T, out,
                     acq_pct=ex["acq_pct"], ren_pct=ex["ren_pct"],
                     ren_fixed=ex["ren_fixed"])
    # central-growth account proxy (growth = reserving rate; documented)
    acct = _asset_share_proxy(prem_m, prem_a, T,
                              DEFAULT_RESERVING_DISCOUNT_RATE,
                              acq_pct=ex["acq_pct"], ren_pct=ex["ren_pct"],
                              ren_fixed=ex["ren_fixed"])
    for m in range(T):
        prob_bom = in_force[m]
        deaths = prob_bom * q[m]
        lapses = prob_bom * (1.0 - q[m]) * l[m]
        a = acct[m + 1]
        # guarantee floor = SA; account excess over SA is non-guaranteed
        out.arrays["death_guaranteed"][m] += count * sa * deaths
        out.arrays["death_non_guaranteed"][m] += count * max(a - sa, 0.0) * deaths
        out.arrays["surrender_non_guaranteed"][m] += (
            count * float(ov.get("surrender_value_pct", 0.90)) * a * lapses)
    a_T = acct[T]
    out.arrays["maturity_guaranteed"][T - 1] += count * in_force[T] * sa
    out.arrays["maturity_non_guaranteed"][T - 1] += (
        count * in_force[T] * max(a_T - sa, 0.0))


def _project_wl_row(row: Dict[str, Any], out: _RowBuckets) -> None:
    """PC-2 WL_PAR_2026 - whole-life participating: identical RB par
    mechanics with the ENDOWMENT-AT-LIMIT convention (the composed
    ``term_years`` runs the cover to the product's age limit; survivors at
    the projection boundary receive SA + vested RB + terminal bonus exactly
    like an endowment maturing at the limit - standard whole-life
    tabulation).  Catalogue tunables mirror HKRB (rb_rate /
    terminal_bonus_pct / surrender_value_pct) + the PC-2 overrides."""
    _project_rb_row(row, out)


def _project_term_row(row: Dict[str, Any], out: _RowBuckets) -> None:
    """PC-2 TERM_2026 - level term assurance (protection): guaranteed SA on
    death only; NO maturity benefit; surrender value optional at
    ``surrender_value_pct`` x asset-share proxy (default 0.0 - standard for
    protection business, so lapses generate no cash flow)."""
    ov = row.get("mechanics") or {}
    ex = _row_overrides(ov)
    sa = float(row["sum_assured"])
    T = min(int(row["term_years"]) * 12, HORIZON_MONTHS)
    count = float(row["policy_count"])
    prem_a = float(row["annual_premium"])
    prem_m = prem_a / 12.0
    q, l, in_force = _decrements(int(row["issue_age"]), row["gender"], T,
                                 qx_mult=ex["qx_mult"],
                                 lapse_mult=ex["lapse_mult"])
    _premium_expense(prem_m, prem_a, count, in_force, T, out,
                     acq_pct=ex["acq_pct"], ren_pct=ex["ren_pct"],
                     ren_fixed=ex["ren_fixed"])
    svp = float(ov.get("surrender_value_pct", 0.0))
    acc = (_asset_share_proxy(prem_m, prem_a, T,
                              DEFAULT_RESERVING_DISCOUNT_RATE,
                              acq_pct=ex["acq_pct"], ren_pct=ex["ren_pct"],
                              ren_fixed=ex["ren_fixed"])
           if svp > 0.0 else None)
    for m in range(T):
        prob_bom = in_force[m]
        deaths = prob_bom * q[m]
        out.arrays["death_guaranteed"][m] += count * sa * deaths
        if acc is not None:
            lapses = prob_bom * (1.0 - q[m]) * l[m]
            out.arrays["surrender_guaranteed"][m] += (
                count * svp * max(acc[m + 1], 0.0) * lapses)


def _project_annuity_row(row: Dict[str, Any], out: _RowBuckets) -> None:
    """PC-2 ANNUITY_2026 - deferred life annuity (``sum_assured`` = annuity
    NOTIONAL): premiums during the ``deferral_years`` period accumulate the
    asset-share proxy; from vesting each survivor receives a GUARANTEED
    monthly annuity of ``annuity_rate`` x notional / 12 (bucket
    ``annuity_guaranteed``).  Death in deferral returns the asset-share
    proxy (guaranteed); surrender is deferral-only at
    ``surrender_value_pct``; post-vesting the annuity is LOCKED IN (lapse
    zeroed via ``lapse_stop_month``, no death benefit - payments cease on
    death).  The per-policy fixed renewal expense continues through the
    payout phase (payment admin)."""
    ov = row.get("mechanics") or {}
    ex = _row_overrides(ov)
    sa = float(row["sum_assured"])
    T = min(int(row["term_years"]) * 12, HORIZON_MONTHS)
    count = float(row["policy_count"])
    prem_a = float(row["annual_premium"])
    prem_m = prem_a / 12.0
    D = min(max(int(round(float(ov.get("deferral_years", 10.0)) * 12)), 0), T)
    pay_m = float(ov.get("annuity_rate", 0.05)) * sa / 12.0
    svp = float(ov.get("surrender_value_pct", 0.90))
    q, l, in_force = _decrements(int(row["issue_age"]), row["gender"], T,
                                 qx_mult=ex["qx_mult"],
                                 lapse_mult=ex["lapse_mult"],
                                 lapse_stop_month=D)
    # premiums + acquisition/renewal expenses run during the deferral only
    _premium_expense(prem_m, prem_a, count, in_force, D, out,
                     acq_pct=ex["acq_pct"], ren_pct=ex["ren_pct"],
                     ren_fixed=ex["ren_fixed"])
    acc = _asset_share_proxy(prem_m, prem_a, D,
                             DEFAULT_RESERVING_DISCOUNT_RATE,
                             acq_pct=ex["acq_pct"], ren_pct=ex["ren_pct"],
                             ren_fixed=ex["ren_fixed"]) if D > 0 else None
    for m in range(T):
        prob_bom = in_force[m]
        deaths = prob_bom * q[m]
        if m < D:
            basis = max(acc[m + 1], 0.0)
            lapses = prob_bom * (1.0 - q[m]) * l[m]
            out.arrays["death_guaranteed"][m] += count * basis * deaths
            out.arrays["surrender_guaranteed"][m] += (
                count * svp * basis * lapses)
        else:
            out.arrays["annuity_guaranteed"][m] += count * pay_m * prob_bom
            out.arrays["expense"][m] += count * ex["ren_fixed"] * prob_bom
    # no maturity benefit: the annuity runs off with survivorship


_PRODUCT_PROJECTORS = {
    "HKRB_PAR_2026": _project_rb_row,
    "HKCD_PAR_2026": _project_cd_row,
    "GMMB_EQ_2026": _project_gmmb_row,
    # PC-2 mechanic families (owner directive 2026-07-03, track 4.0d)
    "WL_PAR_2026": _project_wl_row,
    "TERM_2026": _project_term_row,
    "ANNUITY_2026": _project_annuity_row,
}


def project_liability_set(portfolio: List[Dict[str, Any]]) -> pd.DataFrame:
    """Monthly liability cash flows by product class, months 1..1200.

    Returns a tidy frame: columns = [month, product_class, <buckets...>,
    total_benefit, net_cashflow]."""
    if not portfolio:
        raise ValueError("portfolio is empty - nothing to project")
    frames = []
    by_class: Dict[str, _RowBuckets] = {}
    for row in portfolio:
        ptype = str(row.get("product_type"))
        if ptype not in _PRODUCT_PROJECTORS:
            raise ValueError("unknown product_type: %r" % ptype)
        # PC-1: report per catalogue product when composed (short/long par
        # split out); legacy rows keep the family as their class
        class_key = str(row.get("product_id") or ptype)
        out = by_class.setdefault(class_key, _RowBuckets())
        _PRODUCT_PROJECTORS[ptype](row, out)
    months = np.arange(1, HORIZON_MONTHS + 1)
    for ptype, out in sorted(by_class.items()):
        df = pd.DataFrame({"month": months, "product_class": ptype})
        for b in LIABILITY_BUCKETS:
            df[b] = out.arrays[b]
        benefit_cols = [b for b in LIABILITY_BUCKETS
                        if b not in ("premium", "expense")]
        df["total_benefit"] = df[benefit_cols].sum(axis=1)
        df["net_cashflow"] = df["premium"] - df["expense"] - df["total_benefit"]
        frames.append(df)
    return pd.concat(frames, ignore_index=True)


# ---------------------------------------------------------------------------
# Asset projection - by asset class, cash flows + balances
# ---------------------------------------------------------------------------

def _mechanics_for(label: str,
                   overrides: Optional[Dict[str, Dict[str, Any]]] = None
                   ) -> Dict[str, Any]:
    if overrides and str(label) in overrides:
        return overrides[str(label)]
    key = str(label).strip().lower()
    for prefix, mech in ASSET_CLASS_MECHANICS.items():
        if key.startswith(prefix):
            return mech
    return _DEFAULT_ASSET_MECHANICS


def project_asset_set(balance_sheet: Dict[str, Any],
                      net_liability_cf: Optional[np.ndarray] = None,
                      mechanics: Optional[Dict[str, Dict[str, Any]]] = None):
    """Monthly asset cash flows AND balances by asset class, months 1..1200,
    COUPLED to the liability book (owner correction 2026-07-03: balances must
    grow with premium accumulation and run off with the liabilities, not sit
    level).

    Fund recursion (documented ALM policy):
      * investment income (bond coupons / equity dividends / cash interest)
        is RETAINED and reinvested in the fund;
      * equity balances additionally compound at the capital-growth rate;
      * the liability NET cash flow of the month (premiums - expenses -
        benefits, from the liability set) is INVESTED when positive and
        FUNDED BY SELLING assets when negative;
      * the fund is rebalanced monthly to the OPENING balance-sheet class
        weights (constant-mix; bond principal roll is internal and has no
        balance effect under constant mix);
      * if outflows exhaust the fund, balances floor at zero and the
        unfunded amount is reported in the ``shortfall`` column.

    Per class cash-flow columns: ``investment_income``, ``capital_growth``,
    ``net_investment`` (purchase + / sale -), and per class balance column
    ``market_value``.  Accounting identity, tested:
    MV_c[m] = MV_c[m-1] + income_c + growth_c + net_investment_c.

    ``net_liability_cf`` is the length-1200 monthly net liability cash flow;
    omitted (None) means a standalone asset view with zero liability flows.
    """
    assets = (balance_sheet or {}).get("assets") or []
    if not assets:
        raise ValueError("balance_sheet.assets is empty - nothing to project")
    if net_liability_cf is None:
        net = np.zeros(HORIZON_MONTHS)
    else:
        net = np.asarray(net_liability_cf, dtype=float)
        if net.shape != (HORIZON_MONTHS,):
            raise ValueError("net_liability_cf must have length %d"
                             % HORIZON_MONTHS)

    labels = [str(a.get("asset_class")) for a in assets]
    mv0 = np.array([float(a.get("market_value")) for a in assets])
    if mv0.sum() <= 0:
        raise ValueError("total backing asset market value must be positive")
    weights = mv0 / mv0.sum()
    mechs = [_mechanics_for(lbl, mechanics) for lbl in labels]
    inc_rate = np.array([
        (m.get("annual_yield") if m["kind"] != "equity"
         else m["annual_dividend_yield"]) / 12.0 for m in mechs])
    grw_rate = np.array([
        ((1.0 + m["annual_capital_growth"]) ** (1.0 / 12.0) - 1.0)
        if m["kind"] == "equity" else 0.0 for m in mechs])

    n = len(labels)
    income = np.zeros((HORIZON_MONTHS, n))
    growth = np.zeros((HORIZON_MONTHS, n))
    net_inv = np.zeros((HORIZON_MONTHS, n))
    mv = np.zeros((HORIZON_MONTHS, n))
    shortfall = np.zeros(HORIZON_MONTHS)

    bal = mv0.copy()
    for i in range(HORIZON_MONTHS):
        income[i] = inc_rate * bal
        growth[i] = grw_rate * bal
        total_new = bal.sum() + income[i].sum() + growth[i].sum() + net[i]
        if total_new < 0.0:
            shortfall[i] = -total_new
            total_new = 0.0
        new_bal = weights * total_new  # constant-mix rebalancing
        net_inv[i] = new_bal - bal - income[i] - growth[i]
        bal = new_bal
        mv[i] = bal

    months = np.arange(1, HORIZON_MONTHS + 1)
    cf_frames, bal_frames = [], []
    for j, label in enumerate(labels):
        cf_frames.append(pd.DataFrame({
            "month": months, "asset_class": label,
            "investment_income": income[:, j],
            "capital_growth": growth[:, j],
            "net_investment": net_inv[:, j],
            "net_cashflow": income[:, j] + growth[:, j] + net_inv[:, j]}))
        bal_frames.append(pd.DataFrame({
            "month": months, "asset_class": label,
            "market_value": mv[:, j]}))
    cf = pd.concat(cf_frames, ignore_index=True)
    balf = pd.concat(bal_frames, ignore_index=True)
    cf.attrs["shortfall_total"] = float(shortfall.sum())
    balf.attrs["shortfall_total"] = float(shortfall.sum())
    return cf, balf


# ---------------------------------------------------------------------------
# Yearly rollups
# ---------------------------------------------------------------------------

def yearly_rollup(monthly: pd.DataFrame, group_col: str,
                  balance: bool = False) -> pd.DataFrame:
    """Yearly grid 1..100.  Cash flows SUM over the year; balances take the
    YEAR-END (month 12k) snapshot."""
    df = monthly.copy()
    df["year"] = ((df["month"] - 1) // 12) + 1
    value_cols = [c for c in df.columns
                  if c not in ("month", "year", group_col)]
    if balance:
        out = (df[df["month"] % 12 == 0]
               .drop(columns=["month"])
               .rename(columns={c: c for c in value_cols}))
        out = out[["year", group_col] + value_cols].reset_index(drop=True)
    else:
        out = (df.groupby(["year", group_col], as_index=False)[value_cols]
               .sum())
    return out


def to_wide(frame: pd.DataFrame, group_col: str, time_col: str) -> pd.DataFrame:
    """Owner-requested output shape (2026-07-03): ONLY the time dimension in
    rows; classes spread horizontally as column headers.

    Value columns are pivoted per class and flattened to
    ``<class>__<measure>`` (single-measure frames like balances keep just
    ``<class>``).  Row order = time ascending; column order = class then
    measure, classes sorted."""
    value_cols = [c for c in frame.columns
                  if c not in (time_col, group_col)]
    wide = frame.pivot(index=time_col, columns=group_col,
                       values=value_cols)
    if len(value_cols) == 1:
        wide.columns = [str(cls) for _, cls in wide.columns]
    else:
        wide = wide.swaplevel(axis=1)
        wide.columns = ["{}__{}".format(cls, measure)
                        for cls, measure in wide.columns]
    wide = wide[sorted(wide.columns)]
    return wide.reset_index()


# ---------------------------------------------------------------------------
# The output set (JSON + CSV artifacts)
# ---------------------------------------------------------------------------

def _inputs_digest(model_inputs: Dict[str, Any]) -> str:
    blob = json.dumps({"portfolio": model_inputs.get("portfolio"),
                       "balance_sheet": model_inputs.get("balance_sheet")},
                      sort_keys=True, default=str).encode("utf-8")
    return "sha256:" + hashlib.sha256(blob).hexdigest()


def build_cashflow_projection_set(model_inputs: Dict[str, Any],
                                  out_dir: Optional[str] = None) -> Dict[str, Any]:
    """Build the full owner-directed cash-flow projection set.

    Coerces the (string-valued) portfolio/balance-sheet rows, projects both
    sides, rolls up yearly, and (when ``out_dir`` is given) writes
    ``CASHFLOW_PROJECTION_SET.json`` + six CSVs.  Returns a JSON-safe
    summary carrying totals, paths and provenance."""
    portfolio = []
    for r in (model_inputs.get("portfolio") or []):
        portfolio.append({
            "product_type": str(r.get("product_type")),
            "issue_age": int(float(r.get("issue_age"))),
            "gender": str(r.get("gender") or "M"),
            "term_years": int(float(r.get("term_years"))),
            "sum_assured": float(r.get("sum_assured")),
            "annual_premium": float(r.get("annual_premium")),
            "policy_count": float(r.get("policy_count")),
            "vested_bonus": float(r.get("vested_bonus") or 0.0),
            **({"product_id": str(r["product_id"])} if r.get("product_id") else {}),
            **({"mechanics": r["mechanics"]}
               if isinstance(r.get("mechanics"), dict) else {}),
        })
    from par_model_v2.projection.portfolio_construction import (
        asset_mechanics_from_strategy, resolve_portfolio)
    catalogue = model_inputs.get("product_catalogue")
    resolved = resolve_portfolio(portfolio, catalogue)
    strategy = model_inputs.get("asset_strategy")
    asset_mech = (asset_mechanics_from_strategy(strategy)
                  if isinstance(strategy, dict) and strategy.get("saa")
                  else None)
    liab_m = project_liability_set(resolved)
    net_liab = (liab_m.groupby("month")["net_cashflow"].sum()
                .reindex(range(1, HORIZON_MONTHS + 1), fill_value=0.0)
                .to_numpy())
    asset_cf_m, asset_bal_m = project_asset_set(
        model_inputs.get("balance_sheet") or {}, net_liability_cf=net_liab,
        mechanics=asset_mech)
    liab_y = yearly_rollup(liab_m, "product_class")
    asset_cf_y = yearly_rollup(asset_cf_m, "asset_class")
    asset_bal_y = yearly_rollup(asset_bal_m, "asset_class", balance=True)

    result: Dict[str, Any] = {
        "ok": True,
        "schema": SCHEMA_VERSION,
        "csv_orientation": "rows=time only; classes horizontal (<class>__<measure>)",
        "basis": "deterministic_central",
        "horizon": {"months": HORIZON_MONTHS, "years": HORIZON_YEARS},
        "unsigned_note": UNSIGNED_NOTE,
        "inputs_digest": _inputs_digest(model_inputs),
        "liability_buckets": LIABILITY_BUCKETS,
        "product_classes": sorted(liab_m["product_class"].unique().tolist()),
        "asset_classes": sorted(asset_cf_m["asset_class"].unique().tolist()),
        "totals": {
            "liability": {b: float(liab_m[b].sum()) for b in LIABILITY_BUCKETS},
            "asset_income": float(asset_cf_m["investment_income"].sum()),
            "asset_shortfall": float(asset_cf_m.attrs.get("shortfall_total", 0.0)),
            "book_runoff_month": int(np.max(np.nonzero(net_liab)[0]) + 1
                                     if np.any(net_liab) else 0),
            "asset_final_mv": float(
                asset_bal_m[asset_bal_m["month"] == HORIZON_MONTHS]
                ["market_value"].sum()),
        },
    }
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
        tables = {
            "liability_cashflows_monthly.csv":
                to_wide(liab_m, "product_class", "month"),
            "liability_cashflows_yearly.csv":
                to_wide(liab_y, "product_class", "year"),
            "asset_cashflows_monthly.csv":
                to_wide(asset_cf_m, "asset_class", "month"),
            "asset_cashflows_yearly.csv":
                to_wide(asset_cf_y, "asset_class", "year"),
            "asset_balances_monthly.csv":
                to_wide(asset_bal_m, "asset_class", "month"),
            "asset_balances_yearly.csv":
                to_wide(asset_bal_y, "asset_class", "year"),
        }
        paths = {}
        for name, df in tables.items():
            path = os.path.join(out_dir, name)
            df.to_csv(path, index=False)
            paths[name] = os.path.abspath(path)
        result["csv_paths"] = paths
        json_path = os.path.join(out_dir, "CASHFLOW_PROJECTION_SET.json")
        payload = dict(result)
        wide_liab_y = to_wide(liab_y, "product_class", "year")
        wide_acf_y = to_wide(asset_cf_y, "asset_class", "year")
        wide_abal_y = to_wide(asset_bal_y, "asset_class", "year")
        payload["yearly_preview"] = {
            "orientation": "rows=time, columns=<class>__<measure>",
            "liability": wide_liab_y[wide_liab_y["year"] <= 5]
                .to_dict(orient="records"),
            "asset_cashflows": wide_acf_y[wide_acf_y["year"] <= 5]
                .to_dict(orient="records"),
            "asset_balances": wide_abal_y[wide_abal_y["year"] <= 5]
                .to_dict(orient="records"),
        }
        with open(json_path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=1, default=str)
        with open(json_path, encoding="utf-8") as fh:
            json.load(fh)  # re-parse guard
        result["json_path"] = os.path.abspath(json_path)
    result["frames"] = {
        "liability_monthly": liab_m, "liability_yearly": liab_y,
        "asset_cf_monthly": asset_cf_m, "asset_cf_yearly": asset_cf_y,
        "asset_balance_monthly": asset_bal_m, "asset_balance_yearly": asset_bal_y,
    }
    return result
