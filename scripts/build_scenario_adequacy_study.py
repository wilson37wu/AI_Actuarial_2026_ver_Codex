#!/usr/bin/env python3
"""
Builder - Scenario-Adequacy Convergence Study evidence artifacts.

Roadmap §4.1 #5 (C-ROSS gap #6).  Runs the governed TVOG estimator across the
500 -> 1,000 -> 2,000 -> 5,000 scenario ladder with independent-seed
replications and (re)generates, deterministically up to the run timestamp:

  * ``docs/SCENARIO_ADEQUACY_CONVERGENCE_STUDY.json`` - the machine artifact
    (per-count TVOG + 95% CI bands, runtime benchmark, sizing / recommendation).
  * ``docs/SCENARIO_ADEQUACY_CONVERGENCE_STUDY.md``   - the human report
    (convergence report + benchmark + recommendation memo).

Purely-additive diagnostic; does NOT touch any governed headline figure.  The
representative product + placeholder ESG calibration and automation-driven
sign-off make the numbers UNSIGNED pending owner / independent review.

Usage:
    python3 scripts/build_scenario_adequacy_study.py [--replications N] [--quick]
"""
from __future__ import annotations

import argparse
import json
import sys
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from par_model_v2.analysis.scenario_adequacy import (  # noqa: E402
    DEFAULT_LADDER,
    run_convergence_study,
)


def build(repo_root: Path, replications: int = 8, ladder=DEFAULT_LADDER,
          seed_base: int = 42) -> dict:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        res = run_convergence_study(
            ladder=ladder,
            replications=replications,
            seed_base=seed_base,
            progress=lambda m: print("  ..", m, flush=True),
        )
    docs = repo_root / "docs"
    (docs / "SCENARIO_ADEQUACY_CONVERGENCE_STUDY.json").write_text(
        json.dumps(res.to_dict(), indent=2), encoding="utf-8"
    )
    (docs / "SCENARIO_ADEQUACY_CONVERGENCE_STUDY.md").write_text(
        res.to_markdown(), encoding="utf-8"
    )
    return res.to_dict()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--replications", type=int, default=8)
    ap.add_argument("--seed-base", type=int, default=42)
    ap.add_argument("--quick", action="store_true",
                    help="tiny ladder for a fast self-check")
    args = ap.parse_args()

    root = Path(__file__).resolve().parents[1]
    ladder = (200, 400, 800) if args.quick else DEFAULT_LADDER
    d = build(root, replications=args.replications, ladder=ladder,
              seed_base=args.seed_base)
    print("wrote docs/SCENARIO_ADEQUACY_CONVERGENCE_STUDY.{json,md}")
    print("  error_model:", d["error_model"],
          "| ladder:", d["ladder"],
          "| replications:", d["replications"])
    print("  reference TVOG:", d["reference"]["tvog"],
          "| effective SE:", d["reference"]["effective_se"],
          "| VRF:", d["reference"]["variance_reduction_factor"])
    s = d["sizing"]
    print("  recommended_n:", s["recommended_n"],
          "| required(eff):", s["required_n_for_rel_tol"],
          "| required(iid):", s["required_n_iid_conservative"],
          "| meets_tol_at_floor:", s["meets_rel_tol_at_floor"])
    print("  total_runtime_s:", d["total_runtime_seconds"])
