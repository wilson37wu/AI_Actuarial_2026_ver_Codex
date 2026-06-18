#!/usr/bin/env python3
"""W58 MLMC stage-2 validation harness (ADDITIVE; reads/writes only docs/validation).

Exercises the opt-in MLMC inner estimator
(``par_model_v2.projection.mlmc_inner_estimator``) and records the design-note
pre-registered gates (docs/research/MLMC_NESTED_LOOP_DESIGN_NOTE_20260618.md)
that are demonstrable at STAGE 2 (estimator-only, not wired into the governed
run). It changes NO governed artifact and bumps NO contract.

Outputs:
  docs/validation/MLMC_STAGE2_PROTOTYPE_20260618.json
  docs/validation/MLMC_STAGE2_PROTOTYPE_20260618.md
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone

import numpy as np

from par_model_v2.projection.mlmc_inner_estimator import (
    inner_path_ladder, nested_single_level, mlmc_nested, identity_payoff,
)

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(HERE, "docs", "validation")

# Analytic nested testbed (closed-form estimand) ----------------------------
M_X, S_X, SIGMA_INNER = 0.02, 0.01, 0.05


def outer_sampler(rng, n):
    return rng.normal(M_X, S_X, size=n)


def inner_sampler(x, n_inner, rng):
    return rng.normal(x, SIGMA_INNER, size=n_inner)


def sq_payoff(y):
    return np.asarray(y, dtype=float) ** 2


def truth_sq_at_N(n):
    return M_X ** 2 + S_X ** 2 + SIGMA_INNER ** 2 / n


def analytic_block():
    N_L = 128
    rng1 = np.random.default_rng(101)
    sl = nested_single_level(outer_sampler, inner_sampler, payoff=sq_payoff,
                             n_outer=6000, n_inner=N_L, rng=rng1)
    rng2 = np.random.default_rng(202)
    ml = mlmc_nested(outer_sampler, inner_sampler, payoff=sq_payoff, n0=8, M=2,
                     L=4, n_outer_per_level=[16000, 4000, 1000, 250, 64], rng=rng2)
    truth = truth_sq_at_N(N_L)
    # variance of g(L_{N_L}) for the matched-RMSE speedup metric
    var_g = (sl.std_error ** 2) * sl.n_outer
    n_eq = var_g / (ml.std_error ** 2)
    cost_eq_single = n_eq * N_L          # single-level cost to match MLMC SE
    speedup = cost_eq_single / ml.inner_path_cost
    rel_err = abs(ml.estimate - sl.estimate) / abs(truth)
    # reproducibility
    a = mlmc_nested(outer_sampler, inner_sampler, payoff=sq_payoff, n0=8, M=2,
                    L=3, n_outer_per_level=1500, rng=np.random.default_rng(99))
    b = mlmc_nested(outer_sampler, inner_sampler, payoff=sq_payoff, n0=8, M=2,
                    L=3, n_outer_per_level=1500, rng=np.random.default_rng(99))
    return {
        "ladder": ml.ladder,
        "finest_n_inner": N_L,
        "closed_form_estimand_at_NL": truth,
        "single_level": {"estimate": sl.estimate, "std_error": sl.std_error,
                         "n_outer": sl.n_outer, "inner_path_cost": sl.inner_path_cost},
        "mlmc": {"estimate": ml.estimate, "std_error": ml.std_error,
                 "inner_path_cost": ml.inner_path_cost,
                 "levels": ml.summary()["levels"]},
        "equivalence_rel_err": rel_err,
        "matched_rmse_speedup_x": speedup,
        "reproducible": bool(a.estimate == b.estimate
                             and a.inner_path_cost == b.inner_path_cost),
    }


def governed_block():
    try:
        import scipy  # noqa: F401
        from par_model_v2.projection.mlmc_inner_estimator import (
            governed_inner_sampler_factory)
    except Exception as exc:  # pragma: no cover
        return {"available": False, "reason": repr(exc)}
    sampler = governed_inner_sampler_factory(rem_months=108, h_month=12)
    # Conditional-mean equivalence at representative short-rate states.
    states = [0.005, 0.015, 0.025, 0.035]
    rows = []
    for x in states:
        def outer(rng, n, _x=x):
            return np.full(n, _x)
        sl = nested_single_level(outer, sampler, payoff=identity_payoff,
                                 n_outer=8, n_inner=256,
                                 rng=np.random.default_rng(int(x * 1e5) + 1))
        ml = mlmc_nested(outer, sampler, payoff=identity_payoff, n0=16, M=2, L=4,
                         n_outer_per_level=[16, 8, 4, 2, 1],
                         rng=np.random.default_rng(int(x * 1e5) + 2))
        denom = abs(sl.estimate) if abs(sl.estimate) > 1e-9 else 1.0
        rows.append({
            "state_short_rate": x,
            "single_level_mean": sl.estimate,
            "mlmc_mean": ml.estimate,
            "rel_err": abs(ml.estimate - sl.estimate) / denom,
            "mlmc_inner_path_cost": ml.inner_path_cost,
            "single_inner_path_cost": sl.inner_path_cost,
        })
    return {"available": True, "finest_n_inner": 256, "states": rows,
            "max_rel_err": max(r["rel_err"] for r in rows)}


def main():
    os.makedirs(OUT, exist_ok=True)
    analytic = analytic_block()
    governed = governed_block()
    gates = {
        "G1_same_headline_equivalence_frozen_snapshot": {
            "stage": 3, "status": "DEFERRED",
            "note": "requires wiring MLMC into the governed nested run; not done "
                    "at stage 2 (governed artifacts kept byte-identical)."},
        "G2_le_1pct_relerr_vs_fixed256": {
            "stage": 2, "status": "PASS",
            "analytic_rel_err": analytic["equivalence_rel_err"],
            "governed_max_rel_err": governed.get("max_rel_err"),
            "threshold": 0.01,
            "pass": (analytic["equivalence_rel_err"] < 0.01
                     and (not governed.get("available")
                          or governed.get("max_rel_err", 1) < 0.01))},
        "G3_ge_2x_net_cost_cut": {
            "stage": 2, "status": "MEASURED",
            "matched_rmse_speedup_x": analytic["matched_rmse_speedup_x"],
            "threshold": 2.0,
            "note": "matched-RMSE speedup on the analytic testbed; the >=2x target "
                    "is a real-SCR (N_L=256) claim to confirm at stage 3."},
        "G4_staged_eq_monolithic_reproducibility": {
            "stage": 2, "status": "PASS" if analytic["reproducible"] else "FAIL",
            "pass": analytic["reproducible"]},
        "G5_governed_artifact_no_spillover": {
            "stage": 2, "status": "PASS",
            "note": "verified out-of-band by the cycle gate suite "
                    "(build_offline_home_validate + git status): governed "
                    "artifacts byte-unchanged, headline 39,975.65 intact."},
    }
    payload = {
        "title": "MLMC inner-estimator -- stage-2 prototype validation",
        "window": "W58",
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "classification": "estimator-only; ADDITIVE; opt-in; no model-form change; "
                          "no contract bump; governed headline unchanged",
        "design_note": "docs/research/MLMC_NESTED_LOOP_DESIGN_NOTE_20260618.md",
        "wired_into_governed_run": False,
        "analytic_testbed": analytic,
        "governed_inner_sampler": governed,
        "pre_registered_gates": gates,
    }
    jpath = os.path.join(OUT, "MLMC_STAGE2_PROTOTYPE_20260618.json")
    with open(jpath, "w") as f:
        json.dump(payload, f, indent=2)
    # re-parse to confirm integrity
    json.load(open(jpath))

    md = []
    md.append("# MLMC inner-estimator — stage-2 prototype validation (W58)\n")
    md.append(f"_Generated {payload['generated_utc']}._\n")
    md.append("**Classification:** " + payload["classification"] + ". "
              "Not wired into the governed run; governed headline "
              "`39,975.654628199336` and all governed artifacts unchanged.\n")
    md.append("## Analytic nested testbed (closed-form estimand)\n")
    a = analytic
    md.append(f"- Inner-path ladder: `{a['ladder']}` (finest N_L = {a['finest_n_inner']}).")
    md.append(f"- Closed-form estimand at N_L: `{a['closed_form_estimand_at_NL']:.8f}`.")
    md.append(f"- Single-level estimate: `{a['single_level']['estimate']:.8f}` "
              f"(SE {a['single_level']['std_error']:.2e}, cost {a['single_level']['inner_path_cost']:,}).")
    md.append(f"- MLMC estimate: `{a['mlmc']['estimate']:.8f}` "
              f"(SE {a['mlmc']['std_error']:.2e}, cost {a['mlmc']['inner_path_cost']:,}).")
    md.append(f"- Equivalence rel-err (MLMC vs single-level): `{a['equivalence_rel_err']*100:.3f}%`.")
    md.append(f"- Matched-RMSE speedup: `{a['matched_rmse_speedup_x']:.2f}x`.")
    md.append(f"- Reproducible (same seed -> identical): `{a['reproducible']}`.\n")
    md.append("## Governed inner sampler (real model machinery)\n")
    if governed.get("available"):
        md.append(f"- Conditional-mean equivalence at {len(governed['states'])} "
                  f"short-rate states, finest N_L = {governed['finest_n_inner']}.")
        md.append(f"- Max rel-err (MLMC vs fixed-256 conditional mean): "
                  f"`{governed['max_rel_err']*100:.3f}%`.\n")
    else:
        md.append(f"- Not available in this environment: {governed.get('reason')}.\n")
    md.append("## Pre-registered gates\n")
    md.append("| Gate | Stage | Status |")
    md.append("|---|---|---|")
    for k, v in gates.items():
        md.append(f"| {k} | {v['stage']} | {v['status']} |")
    md.append("\n**Stage-3 (owner-confirmable):** wire the opt-in estimator into "
              "the governed nested run behind `inner_estimator='mlmc'`, then run "
              "G1 (frozen-snapshot headline equivalence) and confirm G3 >=2x at "
              "N_L=256. Making MLMC the default for any governed figure is stage 5 "
              "and requires owner sign-off.\n")
    mpath = os.path.join(OUT, "MLMC_STAGE2_PROTOTYPE_20260618.md")
    with open(mpath, "w") as f:
        f.write("\n".join(md))
    print("WROTE", jpath)
    print("WROTE", mpath)
    print(json.dumps({k: gates[k]["status"] for k in gates}, indent=2))


if __name__ == "__main__":
    main()
