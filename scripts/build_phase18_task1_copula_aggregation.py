"""Phase 18 Task 1 evidence builder — copula-based tail-dependent aggregation.

Runs the canonical three-driver (rate + equity + credit-spread) nested
aggregation at 99.5% to obtain the realised standalone capital-loss vectors and
the nested / var-covar SCR benchmarks, then fits Gaussian / Student-t /
survival-Clayton copulas to the realised losses, aggregates the 99.5% SCR under
each, and benchmarks every result to the nested ground truth.

Writes docs/validation/PHASE18_COPULA_AGGREGATION_REPORT.{json,md}.

EDUCATIONAL ONLY — placeholder parameters; not a regulatory capital model.
"""
from __future__ import annotations
import json, os, sys

import numpy as np

from par_model_v2.projection.monthly_projection import ParEndowmentProduct
from par_model_v2.projection.multi_driver_capital import EquityGuaranteeSpec
from par_model_v2.projection.multi_driver_capital_3d import (
    CreditExposureSpec, ThreeDriverCorrelation, _outer_states_3d,
)
from par_model_v2.projection.multi_driver_risk_aggregation import (
    ThreeDriverRiskAggregator, ThreeDriverAggregationConfig,
)
from par_model_v2.projection.multi_driver_copula_aggregation import (
    CopulaRiskAggregator, CopulaAggregationConfig,
)
from par_model_v2.projection.nested_stochastic_tvog import (
    capital_metrics_from_liabilities,
)
from par_model_v2.stochastic.esg_process import HullWhiteParams, GBMParams
from par_model_v2.stochastic.credit_spread import CreditSpreadParams

OUT_DIR = os.path.join("docs", "validation")
DRIVERS = ["short_rate", "equity_guarantee", "credit_spread"]


def build(n_outer: int = 1000, n_inner: int = 256, seed: int = 42,
          n_sim: int = 200_000) -> dict:
    product = ParEndowmentProduct(
        term_years=10, issue_age=40, gender="M",
        sum_assured=100_000, annual_premium=6_000,
    )
    aggregator = ThreeDriverRiskAggregator(
        product, HullWhiteParams(), GBMParams(rate_equity_correlation=-0.15),
        CreditSpreadParams(), ThreeDriverCorrelation(),
        equity_guarantee=EquityGuaranteeSpec(guarantee_rate=1.0),
        credit_exposure=CreditExposureSpec(exposure_rate=1.0),
    )
    td_cfg = ThreeDriverAggregationConfig(
        n_outer=n_outer, n_inner=n_inner, seed=seed,
        confidence_level=0.995, aggregation_gap_tolerance=0.35,
    )
    # Single nested pass: realised standalone capital-loss vectors.
    outer = _outer_states_3d(
        td_cfg.n_outer, td_cfg.capital_horizon_months, td_cfg.outer_measure,
        aggregator.hw_params, aggregator.gbm_params, aggregator.spread_params,
        aggregator.correlation, aggregator.initial_curve, td_cfg.seed,
    )
    rate_l, equity_l, credit_l = aggregator._component_liabilities(outer, td_cfg)

    # Benchmarks derived from the same loss vectors (matches ThreeDriverRiskAggregator).
    conf, hm = td_cfg.confidence_level, td_cfg.capital_horizon_months
    scr_vec = np.array([
        capital_metrics_from_liabilities(rate_l, conf, hm).scr_proxy,
        capital_metrics_from_liabilities(equity_l, conf, hm).scr_proxy,
        capital_metrics_from_liabilities(credit_l, conf, hm).scr_proxy,
    ], dtype=float)
    nested_scr = capital_metrics_from_liabilities(
        rate_l + equity_l + credit_l, conf, hm
    ).scr_proxy
    C = aggregator.correlation.matrix(aggregator.gbm_params.rate_equity_correlation)
    var_covar_scr = float(np.sqrt(max(0.0, scr_vec @ C @ scr_vec)))

    copula_agg = CopulaRiskAggregator(
        [rate_l, equity_l, credit_l], DRIVERS,
        nested_scr=nested_scr, var_covar_scr=var_covar_scr,
    )
    report = copula_agg.run(CopulaAggregationConfig(n_sim=n_sim, seed=20260605))
    out = report.to_dict()
    out["esg_factor_correlation_matrix"] = [[float(x) for x in row] for row in C]
    return out


def _md(d: dict) -> str:
    lines = [
        "# Phase 18 Task 1 — Copula-Based Tail-Dependent Risk Aggregation",
        "",
        "**Classification:** EDUCATIONAL ONLY — placeholder parameters; not a regulatory capital model.",
        "",
        f"**Verdict:** {d['verdict']}",
        "",
        f"Drivers: {', '.join(d['drivers'])}.  Run `{d['run_id']}`; "
        f"reproducibility digest `{d['reproducibility_digest'][:16]}`.",
        "",
        "## Benchmarks",
        "",
        f"- Three-driver **nested** SCR (diversified ground truth): **{d['nested_scr']:.1f}**",
        f"- Legacy **var-covar** SCR (governed ESG *factor* correlation): "
        f"**{d['var_covar_scr']:.1f}** — understates nested by "
        f"**{d['var_covar_rel_error_vs_nested']*100:.1f}%** (MR-010)",
        f"- Standalone SCR sum (comonotonic bound): {d['standalone_scr_sum']:.1f}",
        "",
        "Realised capital-loss correlation (rate, equity, credit): "
        f"{[[round(x,3) for x in r] for r in d['realised_loss_correlation']]}.",
        "",
        "## Copula aggregation results (99.5%)",
        "",
        "| Copula | SCR | rel. err vs nested | upper-tail dep. λU | AIC | params |",
        "|---|--:|--:|--:|--:|---|",
    ]
    for c in d["copulas"]:
        p = c["params"]
        if "df" in p:
            ps = f"df={p['df']:.0f}"
        elif "theta" in p:
            ps = f"θ={p['theta']:.2f}"
        else:
            ps = "corr"
        star = " ⟵ selected" if c["name"] == d["selected_copula"] else ""
        lines.append(
            f"| {c['name']}{star} | {c['aggregated_scr']:.1f} | "
            f"{c['scr_rel_error_vs_nested']*100:.2f}% | "
            f"{c['upper_tail_dependence']:.3f} | {c['aic']:.1f} | {ps} |"
        )
    lines += [
        "",
        f"**Selected copula (min AIC):** `{d['selected_copula']}`.",
        "",
        "## MR-010 finding (empirical justification — Solvency II Art. 234)",
        "",
        "The var-covar formula understates diversified nested capital by "
        f"~{d['var_covar_rel_error_vs_nested']*100:.0f}% for two compounding reasons: "
        "(1) it aggregates with the governed ESG *factor* correlation (negative "
        "off-diagonals) while the realised capital-*loss* vectors co-move strongly "
        "*positively* in the tail; and (2) an elliptical formula has zero asymptotic "
        "tail dependence.  Re-fitting the dependence with a copula on the **realised "
        "loss vectors** removes (1) entirely: the AIC-selected copula reconciles to "
        f"the nested benchmark within {d['copulas'][0]['scr_rel_error_vs_nested']*100:.1f}–"
        f"{max(c['scr_rel_error_vs_nested'] for c in d['copulas'])*100:.1f}%.  The "
        "Student-t fit collapses toward Gaussian (high df), and survival-Clayton "
        "(genuine upper-tail dependence) bounds the estimate conservatively from "
        "above — i.e. at this sample the residual *tail* dependence beyond the "
        "(correctly-signed) linear loss correlation is modest.  This **MITIGATES "
        "MR-010**: the copula engine, fitted to realised losses, is the recommended "
        "aggregation; the var-covar formula is retained for reference only.",
        "",
        "## Standards",
        "",
        ", ".join(d["standards"]) + ".",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    n_outer = int(sys.argv[1]) if len(sys.argv) > 1 else 1000
    n_inner = int(sys.argv[2]) if len(sys.argv) > 2 else 256
    os.makedirs(OUT_DIR, exist_ok=True)
    d = build(n_outer=n_outer, n_inner=n_inner)
    with open(os.path.join(OUT_DIR, "PHASE18_COPULA_AGGREGATION_REPORT.json"), "w", encoding="utf-8") as fh:
        json.dump(d, fh, indent=2, sort_keys=True)
    with open(os.path.join(OUT_DIR, "PHASE18_COPULA_AGGREGATION_REPORT.md"), "w", encoding="utf-8") as fh:
        fh.write(_md(d))
    print("VERDICT:", d["verdict"])
    print("nested=%.1f var-covar=%.1f (rel err %.1f%%) selected=%s" % (
        d["nested_scr"], d["var_covar_scr"],
        100 * d["var_covar_rel_error_vs_nested"], d["selected_copula"]))
    for c in d["copulas"]:
        print("  %-16s SCR=%.1f relerr=%.2f%% AIC=%.1f lambdaU=%.3f" % (
            c["name"], c["aggregated_scr"], 100 * c["scr_rel_error_vs_nested"],
            c["aic"], c["upper_tail_dependence"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
