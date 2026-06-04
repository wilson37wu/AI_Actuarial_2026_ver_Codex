"""Build Phase 15 Task 3 correlated-risk-aggregation evidence (JSON + Markdown).

Deterministic (seed=42).  Reproduces:
  docs/validation/PHASE15_RISK_AGGREGATION_REPORT.json
  docs/validation/PHASE15_RISK_AGGREGATION_REPORT.md

Run:  PYTHONPATH=. python3 scripts/build_phase15_task3_evidence.py
"""
from __future__ import annotations

import json
import os

from par_model_v2.projection.monthly_projection import ParEndowmentProduct
from par_model_v2.projection.multi_driver_capital import EquityGuaranteeSpec
from par_model_v2.projection.multi_driver_risk_aggregation import (
    MultiDriverRiskAggregator,
    RiskAggregationConfig,
    risk_aggregation_use_restrictions,
)
from par_model_v2.stochastic.esg_process import GBMParams, HullWhiteParams

OUT_DIR = os.path.join("docs", "validation")
JSON_PATH = os.path.join(OUT_DIR, "PHASE15_RISK_AGGREGATION_REPORT.json")
MD_PATH = os.path.join(OUT_DIR, "PHASE15_RISK_AGGREGATION_REPORT.md")


def build():
    product = ParEndowmentProduct(
        term_years=10, issue_age=40, gender="M",
        sum_assured=100_000, annual_premium=6_000,
    )
    aggregator = MultiDriverRiskAggregator(
        product, HullWhiteParams(),
        GBMParams(rate_equity_correlation=-0.15),
        equity_guarantee=EquityGuaranteeSpec(guarantee_rate=1.0),
    )
    cfg = RiskAggregationConfig(
        n_outer=1_000, n_inner=256, seed=42,
        confidence_level=0.995, aggregation_gap_tolerance=0.35,
    )
    report = aggregator.run(cfg)
    d = report.to_dict()

    os.makedirs(OUT_DIR, exist_ok=True)
    with open(JSON_PATH, "w") as fh:
        json.dump(d, fh, indent=2, sort_keys=True)

    s = d["standalone"]
    a = d["aggregation"]
    rc, ec, fc = s["rate_capital"], s["equity_capital"], a["full_nested_capital"]
    restr = risk_aggregation_use_restrictions()

    def money(x):
        return "{:,.2f}".format(x)

    md = []
    md.append("# Phase 15 Task 3 — Correlated Risk Aggregation Report")
    md.append("")
    md.append("**Verdict:** {}  ".format(d["verdict"]))
    md.append("**Run ID:** `{}`  ".format(d["run_id"]))
    md.append("**Reproducibility digest:** `{}`  ".format(d["reproducibility_digest"]))
    md.append("**Confidence level:** {:.1%} | **Horizon:** {} months | "
              "**Outer:** {:,} | **Inner:** {} | **Seed:** {}".format(
                  d["config"]["confidence_level"], d["config"]["capital_horizon_months"],
                  d["config"]["n_outer"], d["config"]["n_inner"], d["config"]["seed"]))
    md.append("")
    md.append("Classification: **{}**".format(restr["classification"]))
    md.append("")
    md.append("## 1. Standalone capital (SCR-proxy = VaR − mean liability)")
    md.append("")
    md.append("| Risk module | Mean liability | VaR (99.5%) | ES (99.5%) | SCR-proxy |")
    md.append("|---|--:|--:|--:|--:|")
    md.append("| Rate (guaranteed benefits, equity guarantee OFF) | {} | {} | {} | {} |".format(
        money(rc["mean_liability"]), money(rc["var_liability"]), money(rc["es_liability"]), money(rc["scr_proxy"])))
    md.append("| Equity guarantee (CRN-isolated leg) | {} | {} | {} | {} |".format(
        money(ec["mean_liability"]), money(ec["var_liability"]), money(ec["es_liability"]), money(ec["scr_proxy"])))
    md.append("| **Undiversified sum (SCR_r + SCR_e)** | | | | **{}** |".format(money(s["standalone_scr_sum"])))
    md.append("")
    md.append("Empirically measured **component loss correlation** (rate leg vs equity leg, "
              "across the outer P-distribution): **{:+.4f}**.".format(s["component_loss_correlation"]))
    md.append("")
    md.append("## 2. Correlated aggregation vs fully-diversified nested capital")
    md.append("")
    md.append("ESG rate/equity driver correlation ρ = **{:+.3f}** (governed `GBMParams.rate_equity_correlation`).  "
              "Validated ESG correlation matrix PASS = **{}**.".format(
                  a["esg_rate_equity_correlation"], a["correlation_matrix_passed"]))
    md.append("")
    md.append("| Quantity | SCR-proxy |")
    md.append("|---|--:|")
    md.append("| Undiversified sum | {} |".format(money(s["standalone_scr_sum"])))
    md.append("| Variance-covariance formula (ESG ρ) | {} |".format(money(a["correlated_scr"])))
    md.append("| **Fully-diversified two-driver nested (ground truth)** | **{}** |".format(money(fc["scr_proxy"])))
    md.append("")
    md.append("| Diversification metric | Value |")
    md.append("|---|--:|")
    md.append("| Benefit, formula (sum − formula) | {} |".format(money(a["diversification_benefit_formula"])))
    md.append("| Benefit, nested (sum − nested) | {} |".format(money(a["diversification_benefit_nested"])))
    md.append("| Formula − nested gap | {} |".format(money(a["formula_vs_nested_scr_gap"])))
    md.append("| Formula vs nested rel. error | {:.2%} |".format(a["formula_vs_nested_scr_rel_error"]))
    md.append("")
    md.append("## 3. Key model-risk finding")
    md.append("")
    md.append("The variance-covariance formula fed with the **raw ESG driver correlation "
              "(ρ = {:+.3f})** materially **understates** the true diversified tail capital "
              "({} vs nested {}, {:.1%} below). The economic reason: the equity maturity "
              "guarantee (a put) and the rate-driven guaranteed-benefit leg both lose value in "
              "the *same* direction under a joint down-rate / down-equity stress, so their "
              "**realised loss correlation is {:+.3f}** — strongly positive — not the {:+.3f} "
              "factor correlation. A production capital model must aggregate on the **capital-loss "
              "correlation**, not the raw ESG factor correlation; the fully-diversified nested "
              "run is the reference.".format(
                  a["esg_rate_equity_correlation"], money(a["correlated_scr"]), money(fc["scr_proxy"]),
                  a["formula_vs_nested_scr_rel_error"], s["component_loss_correlation"],
                  a["esg_rate_equity_correlation"]))
    md.append("")
    md.append("## 4. Notes")
    md.append("")
    for n in d["notes"]:
        md.append("- {}".format(n))
    md.append("")
    md.append("## 5. Model-use restrictions")
    md.append("")
    for lim in restr["limitations"]:
        md.append("- {}".format(lim))
    md.append("")
    md.append("**Standards:** " + ", ".join(d["standards"]))
    md.append("")

    with open(MD_PATH, "w") as fh:
        fh.write("\n".join(md))

    print("WROTE", JSON_PATH)
    print("WROTE", MD_PATH)
    print("VERDICT", d["verdict"])


if __name__ == "__main__":
    build()
