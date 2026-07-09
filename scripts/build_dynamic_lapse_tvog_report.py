#!/usr/bin/env python3
"""
Builder — Dynamic-Lapse Bounded-Elasticity + TVOG-Delta evidence artifact.

Roadmap §4.1 #4 (MR-003).  Regenerates, deterministically:
  * ``docs/DYNAMIC_LAPSE_ELASTICITY_TVOG_DELTA.json`` — the machine artifact
    (elasticity bound + semi-elasticity profile + TVOG delta + vol profile).

The markdown sections appended to ``docs/PHASE13_DYNAMIC_LAPSE_REPORT.md`` are
produced from the same numbers (see ``markdown_sections``).

Purely additive diagnostic; does NOT touch the governed portfolio TVOG headline
or the existing PHASE13_DYNAMIC_LAPSE_REPORT.json gate evidence.
"""
from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import sys
from pathlib import Path as _Path
sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))


from par_model_v2.projection.dynamic_lapse import (
    base_annual_lapse,
    default_hk_par_dynamic_lapse,
)
from par_model_v2.projection.dynamic_lapse_tvog import (
    dynamic_lapse_tvog_delta,
    tvog_delta_vol_profile,
)

_KEY_SPREADS_BPS = (-200, -100, 0, 100, 200, 400)


def _elasticity_summary(credited_rate: float = 0.025) -> dict:
    a = default_hk_par_dynamic_lapse(credited_rate=credited_rate)
    base1 = base_annual_lapse(1)

    # empirical max slope vs analytic bound (bounded-elasticity evidence)
    h = 1e-7
    def lapse_pre(s, base):
        return base * a.efficiency_multiplier(s) + a.mass_lapse(s)
    grid = np.linspace(-0.15, 0.15, 3001)
    emp_max = max(
        (lapse_pre(s + h, base1) - lapse_pre(s - h, base1)) / (2 * h) for s in grid
    )
    bound = a.marginal_response_bound(base=base1)

    return {
        "credited_rate": credited_rate,
        "base_year1": base1,
        "marginal_response_bound_year1": bound,
        "empirical_max_slope_year1": float(emp_max),
        "bound_holds": bool(emp_max <= bound + 1e-9),
        "efficiency_slope_peak_at_zero": a.efficiency_multiplier_slope(0.0),
        "mass_lapse_slope_peak_at_tau": a.mass_lapse_slope(a.tau),
        "semi_elasticity_profile": [
            {
                "spread_bps": bp,
                "semi_elasticity_per_unit": a.semi_elasticity(bp / 1e4, policy_year=1),
                "semi_elasticity_per_bp": a.semi_elasticity(bp / 1e4, policy_year=1) * 1e-4,
                "marginal_response": a.marginal_response(bp / 1e4, base=base1),
            }
            for bp in _KEY_SPREADS_BPS
        ],
    }


def build(repo_root: Path) -> dict:
    delta = dynamic_lapse_tvog_delta(rate_sigma=0.010)
    artifact = {
        "schema": "dynamic-lapse-elasticity-tvog-1.0",
        "run_timestamp": datetime.now(timezone.utc).isoformat(),
        "roadmap_item": "§4.1 #4 (MR-003) dynamic lapse: rate-differential response, bounded elasticity, TVOG delta",
        "bounded_elasticity": _elasticity_summary(),
        "tvog_delta": delta.to_dict(),
        "tvog_delta_vol_profile": tvog_delta_vol_profile(),
        "production_use_restriction": (
            "Educational representative-policy diagnostic. Synthetic experience "
            "study; illustrative rate sigma; automation-driven sign-off. NOT the "
            "governed portfolio TVOG headline. UNSIGNED pending APS X2 review."
        ),
        "standards": ["SOA ASOP 7 §3.3", "SOA ASOP 56 §3.1", "IA TAS M §3.5", "IA TAS M §3.6"],
    }
    out = repo_root / "docs" / "DYNAMIC_LAPSE_ELASTICITY_TVOG_DELTA.json"
    out.write_text(json.dumps(artifact, indent=2), encoding="utf-8")
    return artifact


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    art = build(root)
    d = art["tvog_delta"]
    print("wrote docs/DYNAMIC_LAPSE_ELASTICITY_TVOG_DELTA.json")
    print("  bound_holds:", art["bounded_elasticity"]["bound_holds"],
          "bound=", round(art["bounded_elasticity"]["marginal_response_bound_year1"], 4))
    print("  TVOG delta (sigma=1.0%):", round(d["tvog_delta"], 4),
          "=", "{:+.3%}".format(d["tvog_delta_pct_of_central"]), "of central")
