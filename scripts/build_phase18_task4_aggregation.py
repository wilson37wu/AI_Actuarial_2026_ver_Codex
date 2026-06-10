#!/usr/bin/env python3
"""Build the Phase 18 Task 4 FOUR-driver tail-dependent aggregation evidence.

Runs the genuine four-driver CRN standalone decomposition + 4x4 var-covar +
copula-on-realised-losses aggregation, benchmarks both to four-driver nested
capital, and writes docs/validation/PHASE18_TASK4_AGGREGATION_REPORT.{json,md}.

Run:  PYTHONPATH=/var/tmp/pylibs:. python3 scripts/build_phase18_task4_aggregation.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from par_model_v2.projection.monthly_projection import ParEndowmentProduct
from par_model_v2.projection.multi_driver_capital_4d_aggregation import (
    FourDriverAggregationConfig,
    FourDriverRiskAggregator,
)

OUT_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs", "validation"
)


def main() -> int:
    product = ParEndowmentProduct(
        issue_age=45, gender="M", sum_assured=100000.0,
        annual_premium=5000.0, term_years=20,
    )
    cfg = FourDriverAggregationConfig(
        n_outer=250, n_inner=64, seed=42, capital_horizon_months=12,
        n_sim_copula=150_000,
    )
    report = FourDriverRiskAggregator(product).run(config=cfg)

    os.makedirs(OUT_DIR, exist_ok=True)
    json_path = os.path.join(OUT_DIR, "PHASE18_TASK4_AGGREGATION_REPORT.json")
    md_path = os.path.join(OUT_DIR, "PHASE18_TASK4_AGGREGATION_REPORT.md")
    with open(json_path, "w", encoding="utf-8") as f:
        f.write(report.to_json())
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(report.to_markdown())

    sa = report.standalone
    vc = report.var_covar
    sel = report.copula.selected
    print("VERDICT:", report.verdict)
    print("standalone SCR: rate {:.0f} eq {:.0f} cr {:.0f} lapse {:.0f} sum {:.0f}".format(
        sa.rate_capital.scr_proxy, sa.equity_capital.scr_proxy,
        sa.credit_capital.scr_proxy, sa.lapse_capital.scr_proxy, sa.standalone_scr_sum))
    print("var-covar SCR {:.0f}  nested {:.0f}  rel_err {:.3f}  understatement {:.1%}".format(
        vc.correlated_scr, report.nested_scr, vc.formula_vs_nested_scr_rel_error,
        vc.esg_understatement_pct))
    print("copula {} SCR {:.0f} rel {:.3f}".format(
        report.copula.selected_copula, sel.aggregated_capital.scr_proxy,
        sel.scr_rel_error_vs_nested))
    print("CRN-sum SCR {:.0f}  interaction residual {:.0f} ({:.1%})".format(
        vc.crn_additive_capital.scr_proxy, vc.interaction_residual_scr,
        vc.interaction_residual_rel))
    print("digest", report.reproducibility_digest[:12])
    print("written:", json_path, md_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
