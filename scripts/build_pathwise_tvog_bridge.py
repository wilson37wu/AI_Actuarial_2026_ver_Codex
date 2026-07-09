#!/usr/bin/env python3
"""
Builder — Path-wise vs current (horizon) TVOG bridge evidence artifact.

Roadmap §4.1 item #8 (Limitation #4 — stochastic bonus declaration).
Regenerates deterministically:
  * ``docs/validation/PATHWISE_TVOG_BRIDGE.json`` — the machine artifact
    (per-basis TVOG, the exact additive current→path-wise bridge for the hard
    guarantee and the declared-benefit measures, martingale + bounds gates,
    mechanism shares, stable content digest, UNSIGNED banner).

Purely additive DIAGNOSTIC; does NOT touch the governed portfolio TVOG /
aggregation headline. Re-baselining the governed headline onto a path-wise
declaration basis stays OWNER-GATED.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from par_model_v2.projection.pathwise_tvog_bridge import (  # noqa: E402
    build_pathwise_tvog_bridge,
    pathwise_tvog_use_restrictions,
)


def build(repo_root: Path) -> dict:
    res = build_pathwise_tvog_bridge()
    artifact = res.to_dict()
    artifact["roadmap_item"] = (
        "§4.1 #8 (Limitation #4) stochastic bonus declaration: path-wise "
        "RB/TB TVOG bridge vs current horizon-level convention"
    )
    artifact["content_digest"] = res.content_digest()
    artifact["use_restrictions"] = pathwise_tvog_use_restrictions()
    out = repo_root / "docs" / "validation" / "PATHWISE_TVOG_BRIDGE.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(artifact, indent=2), encoding="utf-8")
    return artifact


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    art = build(root)
    g = art["bridge_guarantee"]
    d = art["bridge_declared"]
    print("wrote docs/validation/PATHWISE_TVOG_BRIDGE.json")
    print("  content_digest:", art["content_digest"][:16])
    print("  martingale_ok:", art["martingale_ok"],
          "ratio", round(art["martingale_ratio"], 5),
          "| bounds_ok:", art["bounds_ok"])
    print("  guarantee bridge : horizon {:.4f} -> pathwise {:.4f}  ({:+.3%})".format(
        g["tvog_current_horizon"], g["tvog_pathwise"], g["delta_pct_of_current"]))
    print("  declared  bridge : horizon {:.4f} -> pathwise {:.4f}  ({:+.3%})".format(
        d["tvog_current_horizon"], d["tvog_pathwise"], d["delta_pct_of_current"]))
