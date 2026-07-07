#!/usr/bin/env python3
"""Build the governed HW1F live-calibration parameter card (roadmap 4.1 #2).

Runs ``run_hw1f_live_calibration`` for CNY + HKD through the governed
three-tier provenance loader (no fetcher configured -> educational fixture
tier; results UNSIGNED by construction) and writes the evidence card to
``docs/validation/``.

Usage:
    python3 scripts/build_hw1f_live_calibration_card.py [--out-dir DIR]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", default=str(REPO_ROOT / "docs" / "validation"),
                        help="Directory for the parameter-card artifacts")
    parser.add_argument("--refresh", action="store_true",
                        help="Ignore the digest cache and recalibrate")
    args = parser.parse_args()

    from par_model_v2.calibration.hw1f_live_calibration import (
        run_hw1f_live_calibration)

    card = run_hw1f_live_calibration(out_dir=Path(args.out_dir),
                                     refresh=args.refresh)

    print("HW1F live-calibration parameter card")
    print("  schema        :", card["schema_version"])
    print("  inputs digest :", card["inputs_digest"][:16] + "...")
    print("  cached        :", card["cached"])
    print("  UNSIGNED      :", card["unsigned"])
    for blk in card["markets"]:
        d = blk["diagnostics"]
        print("  {market}: a={a:.4f} sigma_r={s:.4f} rmse={r:.2f}bps "
              "sse={sse:.3e} converged={c} at_bounds={ab} [{prov}]".format(
                  market=blk["market"], a=blk["parameters"]["a"],
                  s=blk["parameters"]["sigma_r"], r=d["rmse_bps"],
                  sse=d["sse_weighted_bps_sq"], c=d["converged"], ab=d["params_at_bounds"] or "none",
                  prov=blk["provenance"]))
    for g in card["gates"]:
        print("  gate {}: {}".format(g["gate_id"], g["status"]))
    print("  artifacts     :", str(Path(args.out_dir) /
                                   "HW1F_LIVE_CALIBRATION_PARAMETER_CARD.{json,md}"))
    ok = all(blk["diagnostics"]["converged"] for blk in card["markets"])
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
