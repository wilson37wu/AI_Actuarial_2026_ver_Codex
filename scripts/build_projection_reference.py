#!/usr/bin/env python3
"""
build_projection_reference.py — run the GOVERNED Python projection model
(par_model_v2.projection.monthly_projection) and emit a `reference_run` JSON in
the exact schema the Projection-mode GUI consumes, so the GUI can display the
governed model's numbers instead of (or alongside) its in-browser engine.

Output: docs/validation/PROJECTION_REFERENCE_RUN.json  (20yr governed reference)

The schema mirrors the GUI's runEngine() result:
  { params:{...}, L:[{month,py,inF,qm,lm,prem,acq,ren,dG,dN,mG,mN,sv,ncf,df,pvNcf,rb,asp}],
    A:[{month,gC,gM,cC,cM,eD,eG,ci,ti,fmv,df,pv}],
    S:[{month,py,asBom,p,ac,re,inv,ir,dg,dn,sv,dist,sh,ph,asEom}],
    pvP,pvG,pvN,pvSv,pvE,pvNL,pvAI,totSh,totPh,asAtMat }

Phase 38 Task 2: the per-run assembly is now factored into
``assemble_reference_run(term_years)`` / ``write_reference(term_years, out_path)``
so term variants (5yr / 10yr) can be produced in the IDENTICAL schema by
``build_projection_reference_terms.py``. The default ``main()`` is byte-equivalent
to the prior behaviour (20yr -> docs/validation/PROJECTION_REFERENCE_RUN.json),
modulo the ``generated_utc`` timestamp.
"""
from __future__ import annotations
import json
import os
import sys
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from par_model_v2.projection.monthly_projection import (  # noqa: E402
    ParEndowmentProduct, AssetPosition, run_full_projection,
)

OUT = os.path.join(ROOT, "docs", "validation", "PROJECTION_REFERENCE_RUN.json")


# --- scenario: mirrors the GUI's default CNY balanced participating endowment -
def build_product(term_years: int = 20) -> ParEndowmentProduct:
    return ParEndowmentProduct(
        term_years=term_years,
        issue_age=40,
        gender="M",
        sum_assured=1_000_000.0,
        annual_premium=60_000.0,
        rb_rate_annual=0.030,
        terminal_bonus_pct=0.50,
        surrender_value_pct=0.90,
        initial_rb_accum=0.0,
    )


def build_fund() -> list:
    # "balanced" preset, scaled to a single-policy fund (~ first-year premium base)
    return [
        AssetPosition("Govt",   market_value=420_000.0, book_value=420_000.0,
                      annual_yield=0.0285, average_maturity_years=8.5, duration_years=7.4),
        AssetPosition("Credit_A", market_value=300_000.0, book_value=300_000.0,
                      annual_yield=0.0380, average_maturity_years=6.2, duration_years=5.1,
                      credit_rating="A"),
        AssetPosition("Equity", market_value=210_000.0, book_value=210_000.0,
                      annual_yield=0.0250, annual_capital_growth=0.060),
        AssetPosition("Cash",   market_value=70_000.0,  book_value=70_000.0,
                      annual_yield=0.0200),
    ]


def _rows(df, mapping):
    cols = {dst: src for dst, src in mapping.items()}
    recs = df.to_dict("records")
    out = []
    for r in recs:
        out.append({dst: round(float(r[src]), 4) if isinstance(r[src], (int, float))
                    else r[src] for dst, src in cols.items()})
    return out


def assemble_reference_run(term_years: int = 20, disc: float = 0.03) -> dict:
    """Run the governed projection for ``term_years`` and return the reference_run dict.

    The 20yr call reproduces the governed PROJECTION_REFERENCE_RUN.json exactly
    (modulo ``generated_utc``). Term variants reuse the identical product/fund
    presets, engine call and output schema — only ``term_years`` differs.
    """
    product = build_product(term_years)
    fund = build_fund()
    res = run_full_projection(
        product, fund,
        discount_rate_annual=disc,
        acquisition_expense_pct=0.08,
        renewal_expense_pct=0.04,
        renewal_expense_fixed_monthly=12.50,
        policyholder_share=0.90,
        shareholder_share=0.10,
        run_label=("combined-gui-reference" if term_years == 20
                   else "combined-gui-reference-%dyr" % term_years),
    )
    lib, ass, ash = res.liability, res.assets, res.asset_share

    L = _rows(lib.cashflows, {
        "month": "month", "py": "policy_year", "inF": "in_force_prob",
        "qm": "monthly_qx", "lm": "monthly_lapse", "prem": "premium",
        "acq": "acq_expense", "ren": "renewal_expense",
        "dG": "death_benefit_guar", "dN": "death_benefit_ng",
        "mG": "maturity_benefit_guar", "mN": "maturity_benefit_ng",
        "sv": "surrender_benefit", "ncf": "net_cashflow",
        "df": "discount_factor", "pvNcf": "pv_net_cashflow",
        "rb": "rb_accum", "asp": "asset_share_proxy",
    })
    A = _rows(ass.cashflows, {
        "month": "month", "gC": "Govt_coupon", "gM": "Govt_maturity",
        "cC": "Credit_coupon", "cM": "Credit_maturity",
        "eD": "Equity_dividend", "eG": "Equity_capital_gain",
        "ci": "Cash_interest", "ti": "total_income",
        "fmv": "running_fund_mv", "df": "discount_factor", "pv": "pv_cashflow",
    })
    S = _rows(ash.projection, {
        "month": "month", "py": "policy_year", "asBom": "asset_share_bom",
        "p": "premium", "ac": "acq_expense", "re": "renewal_expense",
        "inv": "investment_return", "ir": "inv_return_rate",
        "dg": "death_outgo_guar", "dn": "death_outgo_ng", "sv": "surrender_outgo",
        "dist": "distributable_surplus", "sh": "shareholder_dist",
        "ph": "policyholder_dist", "asEom": "asset_share_eom",
    })

    reference_run = {
        "source": "par_model_v2.projection.monthly_projection.run_full_projection",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "governed": True,
        "classification": "EDUCATIONAL ONLY -- governed model output, not regulatory capital",
        "params": {
            "termYrs": product.term_years,
            "age": product.issue_age,
            "gender": product.gender,
            "sa": product.sum_assured,
            "annPrem": product.annual_premium,
            "disc": disc,
            "phShare": 0.90,
            "rbRate": product.rb_rate_annual,
            "tbPct": product.terminal_bonus_pct,
            "svPct": product.surrender_value_pct,
            # DOM inputs to mirror so the GUI's direct $() reads stay consistent
            "inputs": {
                "p-age": product.issue_age,
                "p-sa": product.sum_assured,
                "p-prem": product.annual_premium,
                "p-ph": 0.90,
                "p-rb": product.rb_rate_annual,
                "p-tb": product.terminal_bonus_pct,
                "p-sv": product.surrender_value_pct,
            },
        },
        "L": L, "A": A, "S": S,
        "pvP": round(lib.pv_premiums, 4),
        "pvG": round(lib.pv_guaranteed_benefits, 4),
        "pvN": round(lib.pv_non_guaranteed_benefits, 4),
        "pvSv": round(lib.pv_surrender_benefits, 4),
        "pvE": round(lib.pv_expenses, 4),
        "pvNL": round(lib.pv_net_liability, 4),
        "pvAI": round(ass.pv_total_income, 4),
        "totSh": round(ash.total_shareholder_dist, 4),
        "totPh": round(ash.total_policyholder_dist, 4),
        "asAtMat": round(ash.asset_share_at_maturity, 4),
    }
    return reference_run


def write_reference(term_years: int, out_path: str, disc: float = 0.03) -> int:
    reference_run = assemble_reference_run(term_years, disc)
    L, A, S = reference_run["L"], reference_run["A"], reference_run["S"]
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(reference_run, f, ensure_ascii=False, indent=2)

    print("%s written:" % os.path.basename(out_path), os.path.getsize(out_path), "bytes")
    print("  term:", term_years, "yr | months L/A/S:", len(L), len(A), len(S))
    print("  PV prem %.0f | PV guar %.0f | PV ng %.0f | net liab %.0f | AS@mat %.0f"
          % (reference_run["pvP"], reference_run["pvG"],
             reference_run["pvN"], reference_run["pvNL"],
             reference_run["asAtMat"]))
    return 0


def main() -> int:
    return write_reference(20, OUT)


if __name__ == "__main__":
    sys.exit(main())
