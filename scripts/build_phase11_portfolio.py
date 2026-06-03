"""Materialise the Phase 11 synthetic 100,000-policy HK PAR portfolio.

Usage:
    python scripts/build_phase11_portfolio.py [--n N] [--seed S] [--out DIR]

Writes:
    <out>/phase11_hk_par_portfolio.csv      -- full policy table
    <out>/phase11_hk_par_portfolio_meta.json -- summary + digest (no rows)

The CSV is intentionally not committed to git; it is a regenerable artifact
for the Phase 11 reporting cycle.  The metadata JSON is small and serves as
reproducibility evidence (digest + summary).
"""

from __future__ import annotations

import argparse
from pathlib import Path

from par_model_v2.projection import (
    PortfolioGenerationConfig,
    generate_hk_par_portfolio,
    validate_portfolio,
    write_metadata,
    write_portfolio,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build Phase 11 HK PAR portfolio")
    parser.add_argument("--n", type=int, default=100_000, help="number of policies")
    parser.add_argument("--seed", type=int, default=20_260_604, help="rng seed")
    parser.add_argument("--out", type=str, default="outputs", help="output directory")
    parser.add_argument("--validate-full", action="store_true", help="validate every record")
    args = parser.parse_args()

    config = PortfolioGenerationConfig(n_policies=args.n, seed=args.seed)
    result = generate_hk_par_portfolio(config)
    validate_portfolio(result.policies, sample_size=None if args.validate_full else 2_000)

    out = Path(args.out)
    csv_path = write_portfolio(result.policies, out / "phase11_hk_par_portfolio.csv")
    meta_path = write_metadata(result, out / "phase11_hk_par_portfolio_meta.json")

    print(f"policies      : {len(result.policies):,}")
    print(f"digest_sha256 : {result.digest}")
    print(f"csv           : {csv_path}")
    print(f"metadata      : {meta_path}")
    print(f"cash / rb     : {result.summary['n_cash_dividend']:,} / "
          f"{result.summary['n_reversionary_bonus']:,}")
    print(f"total SA (HKD): {result.summary['total_sum_assured']:,.0f}")


if __name__ == "__main__":
    main()
