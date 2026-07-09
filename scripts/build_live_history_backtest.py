#!/usr/bin/env python3
"""Build the roadmap item-#6 live-history backtest evidence artifact.

Runs the >= 10-year CNY/CSI-300 backtest through the item-#1 live pipeline and
writes docs/validation/LIVE_HISTORY_BACKTEST.json (UNSIGNED, purely diagnostic;
no governed headline is touched).

Usage:
    python3 scripts/build_live_history_backtest.py [--scenarios N] [--seed S]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from par_model_v2.calibration.live_history_backtest import (
    DEFAULT_ARTIFACT_PATH,
    run_live_history_backtest,
)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenarios", type=int, default=2000)
    ap.add_argument("--seed", type=int, default=20260709)
    ap.add_argument("--out", default=str(DEFAULT_ARTIFACT_PATH))
    args = ap.parse_args()

    report = run_live_history_backtest(
        n_scenarios=args.scenarios,
        seed=args.seed,
        artifact_path=Path(args.out),
        write_artifact=True,
    )
    d = report.to_dict()
    fr = d["full_result"]
    rc = d["recalibration"]
    print("Live-history backtest (item #6) — provenance={} n_full={}".format(
        d["provenance"], d["n_full"]))
    print("  rate_cov={:.1%}  equity_cov={:.1%}  kupiec95={:.3f}  kupiec99={:.3f}  var99_breach={:.1%}".format(
        fr["rate_coverage_pct"], fr["equity_coverage_pct"], fr["kupiec_pvalue_95"],
        fr["kupiec_pvalue_99"], fr["var99_exception_rate"]))
    print("  G-09 gate: {}".format(d["gate_g09"]["status"]))
    print("  recalibration: {} (n_breached={}, breached={})".format(
        rc["recommendation"], rc["n_breached"],
        [t["name"] for t in rc["triggers"] if t["breached"]]))
    print("  inputs_digest={}".format(d["inputs_digest"][:16]))
    print("  written -> {}".format(args.out))


if __name__ == "__main__":
    main()
