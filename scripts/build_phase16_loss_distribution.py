"""Phase 16 Task 2 — loss-distribution evidence emitter (model-side; NOT the UI).

The offline result viewer must perform NO actuarial calculation — it only
*displays* model output. This script is the model-side producer of the loss
distribution that the viewer's capital & tail dashboards consume: it fits the
Phase 15 (rate + equity) LSMC capital surface **once** and then evaluates the
governed outer-state liability distribution ``L_hat`` so it can emit, as a plain
JSON artifact:

  * a histogram (bin edges + counts) of the 1-year outer liability distribution,
  * a confidence sweep (VaR / ES / SCR-proxy at 90 / 95 / 99 / 99.5 / 99.9%),
  * a percentile table, and
  * the same, recomputed under a handful of independent outer-sampling seeds,

so the viewer's seed / percentile / confidence selectors are driven *purely* by
pre-computed model output (the browser does zero numerics beyond a table
look-up). The surface is fitted once and only the *outer* sampling seed varies,
so the per-seed sweeps are cheap polynomial evaluations of one fitted surface.

Deterministic. Reproduces:
  docs/validation/PHASE16_LOSS_DISTRIBUTION.json

Run:  PYTHONPATH=. python3 scripts/build_phase16_loss_distribution.py
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
import os
from typing import Dict, List

import numpy as np

from par_model_v2.projection.monthly_projection import ParEndowmentProduct
from par_model_v2.projection.multi_driver_capital import EquityGuaranteeSpec
from par_model_v2.projection.multi_driver_tail_diagnostics import (
    MultiDriverTailDiagnostics,
    TailDiagnosticsConfig,
    _var_es,
)
from par_model_v2.stochastic.esg_process import GBMParams, HullWhiteParams

OUT_DIR = os.path.join("docs", "validation")
JSON_PATH = os.path.join(OUT_DIR, "PHASE16_LOSS_DISTRIBUTION.json")

#: Confidence levels offered by the viewer's interactive selector.
CONFIDENCE_LEVELS = (0.90, 0.95, 0.99, 0.995, 0.999)
#: Percentiles offered by the viewer's interactive selector.
PERCENTILES = (0.50, 0.75, 0.90, 0.95, 0.975, 0.99, 0.995, 0.999)
#: Independent outer-sampling seeds offered by the viewer's seed selector.
SEEDS = (42, 101, 202, 303)
#: Histogram resolution.
N_BINS = 40
CLASSIFICATION = "EDUCATIONAL ONLY — NOT a regulatory capital model"


def _histogram(liab: np.ndarray, n_bins: int) -> Dict[str, object]:
    counts, edges = np.histogram(liab, bins=n_bins)
    return {
        "bin_edges": [round(float(e), 4) for e in edges],
        "counts": [int(c) for c in counts],
        "n_bins": int(n_bins),
        "n_outer": int(liab.size),
        "min": round(float(liab.min()), 4),
        "max": round(float(liab.max()), 4),
    }


def _confidence_sweep(liab: np.ndarray, mean_liab: float) -> List[Dict[str, float]]:
    rows: List[Dict[str, float]] = []
    for cl in CONFIDENCE_LEVELS:
        var, es = _var_es(liab, cl)
        rows.append({
            "cl": cl,
            "var": round(var, 4),
            "es": round(es, 4),
            "scr": round(var - mean_liab, 4),
        })
    return rows


def _percentiles(liab: np.ndarray) -> List[Dict[str, float]]:
    return [{"p": p, "loss": round(float(np.quantile(liab, p)), 4)} for p in PERCENTILES]


def _seed_block(eng, surface, cfg, n_outer: int, seed: int) -> Dict[str, object]:
    liab = eng._outer_liabilities(surface, n_outer, cfg, seed=seed)
    mean_liab = float(liab.mean())
    var995, es995 = _var_es(liab, 0.995)
    return {
        "seed": int(seed),
        "mean_liability": round(mean_liab, 4),
        "var995": round(var995, 4),
        "es995": round(es995, 4),
        "scr995": round(var995 - mean_liab, 4),
        "histogram": _histogram(liab, N_BINS),
        "confidence_sweep": _confidence_sweep(liab, mean_liab),
        "percentiles": _percentiles(liab),
    }


def build(n_fit: int = 500, n_outer: int = 5_000) -> Dict[str, object]:
    product = ParEndowmentProduct(
        term_years=10, issue_age=40, gender="M",
        sum_assured=100_000, annual_premium=6_000,
    )
    eng = MultiDriverTailDiagnostics(
        product, HullWhiteParams(),
        GBMParams(rate_equity_correlation=-0.15),
        equity_guarantee=EquityGuaranteeSpec(guarantee_rate=1.0),
    )
    # outer_grid / bootstrap / vr params are unused here (we call _fit_surface +
    # _outer_liabilities directly) but the config validates them, so keep valid.
    cfg = TailDiagnosticsConfig(
        n_fit=n_fit, outer_grid=(1_000, 2_000), seed=42,
    )

    surface = eng._fit_surface(cfg)  # fitted ONCE; only the outer seed varies below

    seed_blocks = [_seed_block(eng, surface, cfg, n_outer, s) for s in SEEDS]
    base = seed_blocks[0]  # seed 42 is the canonical default view

    payload: Dict[str, object] = {
        "meta": {
            "phase": "Phase 16 Task 2 — offline-viewer loss-distribution evidence",
            "module": "par_model_v2/projection/multi_driver_tail_diagnostics.py",
            "generated_utc": _dt.datetime.now(_dt.timezone.utc).isoformat(),
            "seed_base": 42,
            "n_fit": int(n_fit),
            "n_outer": int(n_outer),
            "n_bins": int(N_BINS),
            "confidence_level": 0.995,
            "horizon_months": cfg.capital_horizon_months,
            "measure": cfg.outer_measure.value,
            "drivers": ["short_rate r_H", "equity_level S_H"],
            "lsmc_degree": cfg.lsmc_degree,
            "fit_r2": round(float(surface.fit_r2), 6),
            "classification": CLASSIFICATION,
            "note": (
                "The viewer performs NO calculation: VaR/ES/SCR at every confidence "
                "level and percentile are pre-computed here from the fitted LSMC "
                "surface. The surface is fitted once; only the outer-sampling seed "
                "varies across the 'seeds' blocks, so the selector is a pure look-up."
            ),
        },
        # default (seed 42) convenience fields the viewer reads first:
        "mean_liability": base["mean_liability"],
        "histogram": base["histogram"],
        "confidence_sweep": base["confidence_sweep"],
        "percentiles": base["percentiles"],
        "var995": base["var995"],
        "es995": base["es995"],
        "scr995": base["scr995"],
        "seeds": seed_blocks,
    }
    digest = hashlib.sha256(
        json.dumps(payload["seeds"], sort_keys=True).encode("utf-8")
    ).hexdigest()
    payload["meta"]["reproducibility_digest"] = digest

    os.makedirs(OUT_DIR, exist_ok=True)
    with open(JSON_PATH, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=1, ensure_ascii=False)

    print("fit_r2:", round(float(surface.fit_r2), 4),
          "| seeds:", [b["seed"] for b in seed_blocks])
    print("seed 42  VaR99.5 {:.0f}  ES99.5 {:.0f}  SCR {:.0f}".format(
        base["var995"], base["es995"], base["scr995"]))
    print("digest:", digest[:16])
    print("artifact:", JSON_PATH)
    return payload


if __name__ == "__main__":
    build()
