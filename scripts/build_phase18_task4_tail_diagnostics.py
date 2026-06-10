#!/usr/bin/env python3
"""Build the Phase 18 Task 4 FOUR-driver tail-convergence/stability evidence.

Runs outer-count convergence, bootstrap CI/SE on 99.5% VaR/ES, and a
crude/antithetic/Sobol variance-reduction comparison on the four-driver LSMC
surface; writes docs/validation/PHASE18_TASK4_TAIL_DIAGNOSTICS_REPORT.{json,md}.

Run: PYTHONPATH=/var/tmp/pylibs:. python3 scripts/build_phase18_task4_tail_diagnostics.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from par_model_v2.projection.monthly_projection import ParEndowmentProduct
from par_model_v2.projection.multi_driver_tail_diagnostics import (
    FourDriverTailConfig,
    FourDriverTailDiagnostics,
)

OUT_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs", "validation"
)


def main() -> int:
    product = ParEndowmentProduct(
        issue_age=45, gender="M", sum_assured=100000.0,
        annual_premium=5000.0, term_years=20,
    )
    cfg = FourDriverTailConfig(
        n_fit=900, capital_horizon_months=12,
        outer_grid=(1_000, 2_000, 4_000, 8_000, 16_000),
        convergence_tol=0.02,
        n_bootstrap=1_200, bootstrap_n_outer=8_000,
        vr_replications=80, vr_n_outer=4_096, vr_pilot_n=6_000,
    )
    report = FourDriverTailDiagnostics(product).run(config=cfg)

    os.makedirs(OUT_DIR, exist_ok=True)
    json_path = os.path.join(OUT_DIR, "PHASE18_TASK4_TAIL_DIAGNOSTICS_REPORT.json")
    md_path = os.path.join(OUT_DIR, "PHASE18_TASK4_TAIL_DIAGNOSTICS_REPORT.md")
    with open(json_path, "w", encoding="utf-8") as f:
        f.write(report.to_json())
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(report.to_markdown())

    c = report.convergence
    b = report.bootstrap
    v = report.variance_reduction
    print("VERDICT:", report.verdict)
    print("VaR path:", ["{:.0f}".format(x) for x in c.var_path],
          "converged", c.converged, "recN", c.recommended_n_outer)
    print("bootstrap VaR {:.0f} CI [{:.0f},{:.0f}] SE {:.0f} relhw {:.4f}".format(
        b.var_point, b.var_ci_low, b.var_ci_high, b.var_standard_error,
        b.var_ci_rel_halfwidth))
    print("VR: anti {:.2f}x sobol {:.2f}x".format(
        v.antithetic_var_ratio, v.sobol_var_ratio))
    print("digest", report.reproducibility_digest[:12])
    print("written:", json_path, md_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
