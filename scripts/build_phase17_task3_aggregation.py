"""Phase 17 Task 3 evidence builder — three-driver correlated risk aggregation.

Runs the canonical aggregation evidence (rate + equity + credit-spread) at
99.5% and writes docs/validation/PHASE17_RISK_AGGREGATION_REPORT.{json,md}.

EDUCATIONAL ONLY — placeholder parameters; not a regulatory capital model.
"""
from __future__ import annotations
import json, os, sys

from par_model_v2.projection.monthly_projection import ParEndowmentProduct
from par_model_v2.projection.multi_driver_capital import EquityGuaranteeSpec
from par_model_v2.projection.multi_driver_capital_3d import (
    CreditExposureSpec, ThreeDriverCorrelation,
)
from par_model_v2.projection.multi_driver_risk_aggregation import (
    ThreeDriverRiskAggregator, ThreeDriverAggregationConfig,
)
from par_model_v2.stochastic.esg_process import HullWhiteParams, GBMParams
from par_model_v2.stochastic.credit_spread import CreditSpreadParams

OUT_DIR = os.path.join("docs", "validation")


def build(n_outer: int = 1000, n_inner: int = 256, seed: int = 42) -> dict:
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
    cfg = ThreeDriverAggregationConfig(
        n_outer=n_outer, n_inner=n_inner, seed=seed,
        confidence_level=0.995, aggregation_gap_tolerance=0.35,
    )
    report = aggregator.run(cfg)
    return report.to_dict()


def _md(d: dict) -> str:
    s = d["standalone"]; a = d["aggregation"]
    rc, ec, cc = s["rate_capital"], s["equity_capital"], s["credit_capital"]
    fn = a["full_nested_capital"]
    lines = [
        "# Phase 17 Task 3 — Three-Driver Correlated Risk Aggregation",
        "",
        "**Classification:** EDUCATIONAL ONLY — placeholder parameters; not a regulatory capital model.",
        "",
        f"**Verdict:** {d['verdict']}",
        "",
        f"Drivers: {', '.join(d['drivers'])}.  Run `{d['run_id']}`; "
        f"reproducibility digest `{d['reproducibility_digest'][:16]}`.",
        "",
        "## Standalone capital (99.5%, CRN-isolated)",
        "",
        "| Component | mean L | VaR | ES | SCR (VaR−mean) |",
        "|---|--:|--:|--:|--:|",
        f"| Rate (guaranteed benefit) | {rc['mean_liability']:.1f} | {rc['var_liability']:.1f} | {rc['es_liability']:.1f} | {rc['scr_proxy']:.1f} |",
        f"| Equity guarantee | {ec['mean_liability']:.1f} | {ec['var_liability']:.1f} | {ec['es_liability']:.1f} | {ec['scr_proxy']:.1f} |",
        f"| Credit loss | {cc['mean_liability']:.1f} | {cc['var_liability']:.1f} | {cc['es_liability']:.1f} | {cc['scr_proxy']:.1f} |",
        f"| **Standalone sum** | | | | **{s['standalone_scr_sum']:.1f}** |",
        "",
        "## Aggregation",
        "",
        f"- Var-covar SCR (governed 3×3 ESG correlation): **{a['correlated_scr']:.1f}**",
        f"- Full three-driver nested SCR (diversified benchmark): **{fn['scr_proxy']:.1f}**",
        f"- Diversification benefit — formula: {a['diversification_benefit_formula']:.1f}; nested: {a['diversification_benefit_nested']:.1f}",
        f"- Formula-vs-nested rel. error: {a['formula_vs_nested_scr_rel_error']*100:.1f}% (tol {d['config']['aggregation_gap_tolerance']*100:.0f}%)",
        "",
        "### MR-010 (three-driver refresh)",
        "",
        f"The raw ESG-factor formula understates the diversified nested capital by "
        f"**{a['esg_understatement_pct']*100:.1f}%**.  ESG driver correlation matrix "
        f"(rate, equity, credit): {a['esg_correlation_matrix']}.  Realised capital-loss "
        f"correlation: {s['loss_correlation_matrix']}.  Equity-guarantee and credit losses "
        f"co-move positively in stress even though the underlying equity/spread factor "
        f"correlation is negative — so the second-moment formula on factor correlations "
        f"is non-conservative for diversified capital.",
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
    with open(os.path.join(OUT_DIR, "PHASE17_RISK_AGGREGATION_REPORT.json"), "w") as fh:
        json.dump(d, fh, indent=2, sort_keys=True)
    with open(os.path.join(OUT_DIR, "PHASE17_RISK_AGGREGATION_REPORT.md"), "w") as fh:
        fh.write(_md(d))
    print("VERDICT:", d["verdict"])
    print("correlated_scr=%.1f nested_scr=%.1f understate=%.1f%%" % (
        d["aggregation"]["correlated_scr"],
        d["aggregation"]["full_nested_capital"]["scr_proxy"],
        100 * d["aggregation"]["esg_understatement_pct"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
