"""Phase 17 Task 4 evidence builder — three-driver tail-convergence diagnostics.

Runs the canonical three-driver (rate + equity + credit-spread) tail-stability
evidence at 99.5% on the Phase 17 Task 1 trivariate LSMC surface and writes
docs/validation/PHASE17_TAIL_DIAGNOSTICS_REPORT.{json,md}.

EDUCATIONAL ONLY — placeholder parameters; not a regulatory capital model.
Usage:  PYTHONPATH=/var/tmp/pylibs:.  python3 scripts/build_phase17_task4_tail_diagnostics.py
"""
from __future__ import annotations

import json
import os

from par_model_v2.projection.monthly_projection import ParEndowmentProduct
from par_model_v2.projection.multi_driver_capital import EquityGuaranteeSpec
from par_model_v2.projection.multi_driver_capital_3d import (
    CreditExposureSpec, ThreeDriverCorrelation,
)
from par_model_v2.projection.multi_driver_tail_diagnostics import (
    ThreeDriverTailConfig, ThreeDriverTailDiagnostics,
)
from par_model_v2.stochastic.credit_spread import CreditSpreadParams
from par_model_v2.stochastic.esg_process import GBMParams, HullWhiteParams

OUT_DIR = os.path.join("docs", "validation")


def build(n_fit: int = 400, seed: int = 42) -> dict:
    product = ParEndowmentProduct(
        term_years=10, issue_age=40, gender="M",
        sum_assured=100_000, annual_premium=6_000,
    )
    engine = ThreeDriverTailDiagnostics(
        product, HullWhiteParams(), GBMParams(rate_equity_correlation=-0.15),
        CreditSpreadParams(), ThreeDriverCorrelation(),
        equity_guarantee=EquityGuaranteeSpec(guarantee_rate=1.0),
        credit_exposure=CreditExposureSpec(exposure_rate=1.0),
    )
    cfg = ThreeDriverTailConfig(
        n_fit=n_fit,
        outer_grid=(500, 1_000, 2_000, 3_000),
        convergence_tol=0.02,
        n_bootstrap=1_200, bootstrap_n_outer=3_000,
        vr_replications=80, vr_n_outer=2_048, vr_pilot_n=3_000,
        seed=seed,
    )
    report = engine.run(cfg)
    return report.to_dict(), report.to_markdown()


def main() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
    d, md = build()
    with open(os.path.join(OUT_DIR, "PHASE17_TAIL_DIAGNOSTICS_REPORT.json"), "w",
              encoding="utf-8") as fh:
        json.dump(d, fh, indent=2, sort_keys=True)
    with open(os.path.join(OUT_DIR, "PHASE17_TAIL_DIAGNOSTICS_REPORT.md"), "w",
              encoding="utf-8") as fh:
        fh.write(md)
    c = d["convergence"]; b = d["bootstrap"]; v = d["variance_reduction"]
    print("VERDICT:", d["verdict"])
    print("converged=%s rec_N>=%s final_VaR=%.1f final_ES=%.1f" % (
        c["converged"], c["recommended_n_outer"], c["final_var"], c["final_es"]))
    print("bootstrap VaR=%.1f CI=[%.1f,%.1f] SE=%.1f" % (
        b["var_point"], b["var_ci_low"], b["var_ci_high"], b["var_standard_error"]))
    print("antithetic_ratio=%.2f sobol_ratio=%.2f" % (
        v["antithetic_var_ratio"], v["sobol_var_ratio"]))
    print("digest:", d["reproducibility_digest"][:16])


if __name__ == "__main__":
    main()
