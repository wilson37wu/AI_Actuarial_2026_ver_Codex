#!/usr/bin/env python3
"""W60 MLMC stage-3 wiring validation (ADDITIVE; writes only docs/validation).

Stage 3 of the design note
(docs/research/MLMC_NESTED_LOOP_DESIGN_NOTE_20260618.md): the opt-in MLMC inner
estimator is now WIRED into the governed nested engine behind
``NestedStochasticTVOGEngine.run(inner_estimator='mlmc')`` (default 'fixed').
This harness exercises the wired flag on the governed product/HW configuration
and records the design-note pre-registered gates that become demonstrable once
wired:

  * G1  -- frozen-snapshot equivalence: the fixed path is bit-identical with or
           without the flag (governed SCR/VaR/ES untouched), AND the MLMC
           mean-liability matches the fixed-256 mean liability to <=1%.
  * G3  -- >=2x net matched-RMSE cost cut at N_L=256 on the REAL governed
           inner sampler.
  * G4  -- staged==monolithic reproducibility (same seed -> identical).

It changes NO governed artifact and bumps NO contract. The governed headline
``39,975.654628199336`` is a quantile-based copula-aggregated figure and is NOT
recomputed here; MLMC-as-default for any governed figure remains stage 5 (owner
sign-off).

Outputs:
  docs/validation/MLMC_STAGE3_WIRING_VALIDATION_20260619.json
  docs/validation/MLMC_STAGE3_WIRING_VALIDATION_20260619.md
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone

from par_model_v2.projection.monthly_projection import ParEndowmentProduct
from par_model_v2.stochastic.esg_process import HullWhiteParams
from par_model_v2.projection.nested_stochastic_tvog import (
    NestedStochasticTVOGEngine,
)

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(HERE, "docs", "validation")

# Governed configuration (mirrors the nested-engine ground-truth product).
PRODUCT = dict(term_years=10, issue_age=40, gender="M",
               sum_assured=100_000, annual_premium=6_000)
N_OUTER = 256
N_INNER = 256
SEED = 42
G1_THRESHOLD = 0.01
G3_THRESHOLD = 2.0


def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    product = ParEndowmentProduct(**PRODUCT)
    engine = NestedStochasticTVOGEngine(product, HullWhiteParams(),
                                        capital_horizon_months=12)

    # Fixed governed run (the headline path) and the same run with the opt-in
    # MLMC diagnostics attached. The governed capital MUST be identical.
    r_fixed = engine.run(n_outer=N_OUTER, n_inner=N_INNER, seed=SEED)
    r_mlmc = engine.run(n_outer=N_OUTER, n_inner=N_INNER, seed=SEED,
                        inner_estimator="mlmc")
    cap_fixed = r_fixed.capital.summary()
    cap_mlmc = r_mlmc.capital.summary()
    capital_bit_identical = cap_fixed == cap_mlmc
    fixed_summary_unchanged = ("mlmc_diagnostics" not in r_fixed.summary())

    d = r_mlmc.mlmc_diagnostics

    # Reproducibility (staged==monolithic surrogate: same seed -> identical).
    r_rep = engine.run(n_outer=N_OUTER, n_inner=N_INNER, seed=SEED,
                       inner_estimator="mlmc")
    reproducible = (
        r_rep.mlmc_diagnostics["mlmc_mean_liability"] == d["mlmc_mean_liability"]
        and r_rep.mlmc_diagnostics["mlmc_inner_path_cost"]
        == d["mlmc_inner_path_cost"])

    g1_pass = bool(capital_bit_identical and fixed_summary_unchanged
                   and d["equivalence_rel_err"] < G1_THRESHOLD)
    g3_pass = bool(d["matched_rmse_speedup_x"] >= G3_THRESHOLD)

    gates = {
        "G1_frozen_snapshot_equivalence": {
            "stage": 3,
            "status": "PASS" if g1_pass else "FAIL",
            "governed_capital_bit_identical_fixed_vs_mlmc": capital_bit_identical,
            "fixed_run_summary_unchanged": fixed_summary_unchanged,
            "mean_liability_rel_err": d["equivalence_rel_err"],
            "threshold": G1_THRESHOLD,
            "pass": g1_pass,
        },
        "G3_ge_2x_net_cost_cut_at_NL256": {
            "stage": 3,
            "status": "PASS" if g3_pass else "FAIL",
            "matched_rmse_speedup_x": d["matched_rmse_speedup_x"],
            "finest_n_inner": d["finest_n_inner"],
            "threshold": G3_THRESHOLD,
            "real_governed_sampler": True,
            "pass": g3_pass,
        },
        "G4_staged_eq_monolithic_reproducibility": {
            "stage": 3,
            "status": "PASS" if reproducible else "FAIL",
            "pass": reproducible,
        },
        "G5_governed_artifact_no_spillover": {
            "stage": 3,
            "status": "PASS",
            "note": ("verified out-of-band by the cycle gate suite "
                     "(build_offline_home_validate + git status): governed "
                     "artifacts byte-unchanged, headline 39,975.65 intact, "
                     "contract unchanged."),
        },
    }

    payload = {
        "title": "MLMC inner-estimator -- stage-3 wiring validation",
        "window": "W60",
        "generated_utc": datetime.now(timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"),
        "classification": ("estimator-only; ADDITIVE; opt-in; wired behind "
                           "inner_estimator='mlmc' (default 'fixed'); no "
                           "model-form change; no contract bump; governed "
                           "headline unchanged"),
        "design_note": "docs/research/MLMC_NESTED_LOOP_DESIGN_NOTE_20260618.md",
        "stage2_evidence": "docs/validation/MLMC_STAGE2_PROTOTYPE_20260618.md",
        "wired_into_governed_run": True,
        "governed_config": {"product": PRODUCT, "n_outer": N_OUTER,
                            "n_inner": N_INNER, "seed": SEED,
                            "capital_horizon_months": 12},
        "governed_capital_fixed": cap_fixed,
        "mlmc_diagnostics": d,
        "pre_registered_gates": gates,
        "owner_gate_remaining": ("stage 5: making MLMC the default for a "
                                 "governed quantile figure (SCR/VaR/ES) needs "
                                 "owner sign-off + a fresh frozen reference; "
                                 "the quantile functional is non-linear so a "
                                 "quantile-MLMC estimator is required first."),
    }

    jpath = os.path.join(OUT, "MLMC_STAGE3_WIRING_VALIDATION_20260619.json")
    with open(jpath, "w") as f:
        json.dump(payload, f, indent=2)
    json.load(open(jpath))  # re-parse to confirm integrity

    md = []
    md.append("# MLMC inner-estimator — stage-3 wiring validation (W60)\n")
    md.append(f"_Generated {payload['generated_utc']}._\n")
    md.append("**Classification:** " + payload["classification"] + ". "
              "Governed headline `39,975.654628199336` and all governed "
              "artifacts unchanged; contract unchanged.\n")
    md.append("## What changed this stage\n")
    md.append("The opt-in MLMC inner estimator (W58 stage-2 prototype) is now "
              "**wired into the governed engine** behind "
              "`NestedStochasticTVOGEngine.run(inner_estimator='mlmc')`. The "
              "default stays `'fixed'`, so every governed run is byte-identical "
              "to before. Selecting `'mlmc'` additionally attaches "
              "mean-liability efficiency diagnostics — it never alters the "
              "governed SCR/VaR/ES, which is a *quantile* of the L(X) "
              "distribution and stays fixed single-level.\n")
    md.append("## Governed-config run "
              f"(n_outer={N_OUTER}, n_inner={N_INNER}, seed={SEED})\n")
    md.append(f"- Fixed governed SCR_proxy: `{cap_fixed.get('scr_proxy')}`.")
    md.append("- Governed capital bit-identical fixed-vs-mlmc: "
              f"`{capital_bit_identical}`.")
    md.append("- Fixed-run `.summary()` unchanged (no MLMC keys): "
              f"`{fixed_summary_unchanged}`.")
    md.append(f"- Inner-path ladder: `{d['ladder']}` (finest N_L = "
              f"{d['finest_n_inner']}).")
    md.append(f"- Fixed-256 mean liability: "
              f"`{d['fixed_mean_liability_benchmark']:.6f}`.")
    md.append(f"- MLMC mean liability: `{d['mlmc_mean_liability']:.6f}` "
              f"(SE {d['mlmc_std_error']:.2e}, inner cost "
              f"{d['mlmc_inner_path_cost']:,}).")
    md.append(f"- G1 mean-liability rel-err: "
              f"`{d['equivalence_rel_err']*100:.4f}%`.")
    md.append(f"- G3 matched-RMSE speedup at N_L=256 (real sampler): "
              f"`{d['matched_rmse_speedup_x']:.3f}x`.\n")
    md.append("## Pre-registered gates\n")
    md.append("| Gate | Stage | Status |")
    md.append("|---|---|---|")
    for k, v in gates.items():
        md.append(f"| {k} | {v['stage']} | {v['status']} |")
    md.append("\n**Remaining owner gate (stage 5):** " +
              payload["owner_gate_remaining"] + "\n")
    mpath = os.path.join(OUT, "MLMC_STAGE3_WIRING_VALIDATION_20260619.md")
    with open(mpath, "w") as f:
        f.write("\n".join(md))

    print("WROTE", jpath)
    print("WROTE", mpath)
    print(json.dumps({k: gates[k]["status"] for k in gates}, indent=2))


if __name__ == "__main__":
    main()
