#!/usr/bin/env python3
"""Roadmap 4.1 #10 evidence builder -- profile the 100k-policy batch and emit
``docs/validation/PERF_PROFILE_100K.json`` + ``docs/PERF_PROFILE_100K_CARD.md``.

Reproducible: the ``inputs_digest`` hashes the run inputs (config + schema), not
the environment-dependent timings, so re-runs are idempotent in identity.  The
governed reproducibility digest of the generated portfolio is UNCHANGED by the
safe optimisation (regression-locked in tests/test_batch_perf_profile.py).

Usage:  python3 scripts/build_perf_profile_100k.py [--reps N] [--n POLICIES]
"""
from __future__ import annotations

import argparse
import sys
from dataclasses import replace
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from par_model_v2.projection.portfolio_generator import PortfolioGenerationConfig  # noqa: E402
from par_model_v2.projection import batch_perf_profile as B  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--reps", type=int, default=5)
    ap.add_argument("--n", type=int, default=None, help="policy count (default: config default 100k)")
    ap.add_argument("--top", type=int, default=12, help="hotspot rows")
    args = ap.parse_args(argv)

    cfg = PortfolioGenerationConfig()
    if args.n is not None:
        cfg = replace(cfg, n_policies=int(args.n))

    report = B.build_report(cfg, reps=args.reps, hotspot_top_n=args.top)

    val_dir = REPO / "docs" / "validation"
    val_dir.mkdir(parents=True, exist_ok=True)
    json_path = val_dir / "PERF_PROFILE_100K.json"
    card_path = REPO / "docs" / "PERF_PROFILE_100K_CARD.md"

    json_path.write_text(report.to_json() + "\n", encoding="utf-8")
    card_path.write_text(report.to_markdown(), encoding="utf-8")

    print(f"wrote {json_path.relative_to(REPO)}")
    print(f"wrote {card_path.relative_to(REPO)}")
    print(f"  n_policies            = {report.n_policies:,}")
    print(f"  top_hotspot_function  = {report.top_hotspot_function}")
    print(f"  digest_fraction       = {report.generation.digest_fraction:.3f}")
    print(f"  safe_cut_pct          = {report.safe_cut_pct:.2f}%  (meets 20% safely: {report.meets_20pct_safely})")
    print(f"  owner_gated_cut_pct   = {report.owner_gated_cut_pct:.1f}%")
    print(f"  digest_byte_identical = {report.safe_optimization.digest_byte_identical}")
    print(f"  inputs_digest         = {report.inputs_digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
