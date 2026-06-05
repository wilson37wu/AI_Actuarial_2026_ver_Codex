"""Build the Phase 12 educational calibration assumption pack.

Example:
    python scripts/build_phase12_calibration_pack.py --output-dir outputs/phase12_calibration
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from par_model_v2.calibration import build_phase12_calibration_pack


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--calibration-date",
        default="2026-06-04",
        help="ISO calibration date used for pack metadata and starter fixtures.",
    )
    parser.add_argument(
        "--output-dir",
        default="outputs/phase12_calibration",
        help="Directory where JSON and Markdown outputs are written.",
    )
    parser.add_argument(
        "--category",
        action="append",
        choices=("curve", "equity", "credit", "liability"),
        help="Optional category filter. Repeat for multiple categories.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    pack = build_phase12_calibration_pack(
        calibration_date=args.calibration_date,
        categories=args.category,
    )
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = pack.write_json(out_dir / "phase12_calibration_pack.json")
    md_path = pack.write_markdown(out_dir / "phase12_calibration_pack.md")
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")
    print(f"Completeness status: {pack.completeness_status}")


if __name__ == "__main__":
    main()
