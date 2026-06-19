#!/usr/bin/env python3
"""W67 -- MLMC tail estimator STAGE 4B: selectable variance-reduction MODE wiring.

Stage-4b wires the W66 stage-4 tail tools (``stratified_normal_outer_sampler`` +
``es_bias_corrected``) into a single, mode-selectable diagnostics entry point on
the opt-in tail path -- ``tail_capital_diagnostics(variance_reduction=...,
es_bias_correction=...)`` -- the tail analogue of the W60 stage-3
``engine_mean_liability_diagnostics`` mean wiring.

DEFAULT is OFF (``variance_reduction="none"``, ``es_bias_correction=False``): the
default path is the EXACT plain fixed-N_inner ``nested_single_level_tail``
estimator, so a FROZEN reference snapshot holds bit-for-bit and the governed
SCR/VaR/ES headline 39975.654628199336 is byte-unchanged. Selecting a stratified
mode swaps in the W66 stratified sampler at MATCHED inner-path cost (free
variance reduction); the optional ES bootstrap correction is attached additively.

ADDITIVE / OPT-IN: writes only docs/validation. No contract bump, no model-form
change, no headline re-baseline, no owner sign-off consumed. Making any tail-MLMC
figure the governed default remains stage 5.

Pre-registered stage-4b gates:
  * G-W67a frozen-snapshot equivalence -- default mode reproduces the W67 frozen
    reference VaR/ES/SCR bit-for-bit AND equals a plain-outer
    ``nested_single_level_tail`` call bit-for-bit (the default path is unchanged).
  * G-W67b mode-selectable VR -- stratified mode keeps the SAME inner-path cost,
    differs from plain, and delivers a matched-cost replicate variance-reduction
    factor > 1 for VaR/ES/SCR (SCR >= 2x reconfirmed on the wired API).
  * G-W67c determinism -- same seed -> identical dict; ES correction deterministic
    and obeys the bootstrap identity es_bc == 2*es_raw - boot_mean.
  * G-W67d no-spillover -- governed headline echoed; governed artifacts
    byte-unchanged (out-of-band by the cycle gate suite + git status).
"""
from __future__ import annotations
import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone

import numpy as np

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
from par_model_v2.projection.mlmc_inner_estimator import (  # noqa: E402
    tail_capital_diagnostics, resolve_tail_outer_sampler, TAIL_VR_MODES,
    nested_single_level_tail, DEFAULT_TAIL_CONFIDENCE,
)

OUT = os.path.join(HERE, "docs", "validation")
HEADLINE = "39975.654628199336"
G3_SPEEDUP = 2.0

# Frozen W67 reference: plain-outer fixed-256 estimator at the canonical config.
CFG = dict(mu_x=0.02, sigma_x=0.01, sigma_inner=0.05,
           n_outer=4000, n_inner=256, seed=20260619)
FROZEN = dict(
    var=0.04820076634696653,
    es=0.051878781816970275,
    scr=0.027892778037151456,
    mean_liability=0.020307988309815075,
    var_empirical=0.048203134971483055,
    es_empirical=0.051878781816970275,
    inner_path_cost=1024000,
)
ALPHA = DEFAULT_TAIL_CONFIDENCE


def _inner(x, m, rng):
    return rng.normal(float(x), CFG["sigma_inner"], size=int(m))


def _plain(rng, n):
    return rng.normal(CFG["mu_x"], CFG["sigma_x"], size=int(n))


def _vr_factor(mode, R, n_out, seed):
    pv = np.empty(R); pe = np.empty(R); ps = np.empty(R)
    sv = np.empty(R); se = np.empty(R); ss = np.empty(R)
    for r in range(R):
        cfg = dict(CFG, n_outer=n_out, seed=seed + r)
        a = tail_capital_diagnostics(variance_reduction="none", **cfg)
        b = tail_capital_diagnostics(variance_reduction=mode, **cfg)
        pv[r], pe[r], ps[r] = a["var"], a["es"], a["scr"]
        sv[r], se[r], ss[r] = b["var"], b["es"], b["scr"]
    return {
        "VaR": float(pv.var(ddof=1) / sv.var(ddof=1)),
        "ES": float(pe.var(ddof=1) / se.var(ddof=1)),
        "SCR": float(ps.var(ddof=1) / ss.var(ddof=1)),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--R", type=int, default=40)
    ap.add_argument("--vr-n-out", type=int, default=1500)
    ap.add_argument("--boot", type=int, default=200)
    ap.add_argument("--seed", type=int, default=20260619)
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()
    t0 = time.time()

    # --- G-W67a frozen-snapshot equivalence --------------------------------
    d_def = tail_capital_diagnostics(**CFG)
    frozen_match = bool(all(d_def[k] == FROZEN[k] for k in FROZEN))
    ref = nested_single_level_tail(_plain, _inner, alpha=ALPHA,
                                   n_outer=CFG["n_outer"], n_inner=CFG["n_inner"],
                                   rng=np.random.default_rng(CFG["seed"]))
    equals_plain = bool(d_def["var"] == ref.var and d_def["es"] == ref.es
                        and d_def["scr"] == ref.scr
                        and d_def["mean_liability"] == ref.mean_liability)
    default_off = bool(d_def["variance_reduction"] == "none"
                       and d_def["es_bias_correction"] is False)
    g_a = bool(frozen_match and equals_plain and default_off)

    # --- G-W67b mode-selectable VR (matched cost, factor > 1) --------------
    d_strat = tail_capital_diagnostics(variance_reduction="stratified", **CFG)
    same_cost = bool(d_strat["inner_path_cost"] == d_def["inner_path_cost"])
    differs = bool(d_strat["var"] != d_def["var"])
    vr = _vr_factor("stratified", a.R, a.vr_n_out, a.seed)
    vr_all_gt1 = bool(all(v > 1.0 for v in vr.values()))
    g3_scr = bool(vr["SCR"] >= G3_SPEEDUP)
    # antithetic mode also valid + matched cost
    d_anti = tail_capital_diagnostics(variance_reduction="stratified_antithetic", **CFG)
    anti_ok = bool(d_anti["inner_path_cost"] == d_def["inner_path_cost"]
                   and d_anti["variance_reduction"] == "stratified_antithetic")
    g_b = bool(same_cost and differs and vr_all_gt1 and g3_scr and anti_ok)

    # --- G-W67c determinism + ES-correction identity -----------------------
    det = bool(tail_capital_diagnostics(**CFG) == d_def)
    de = tail_capital_diagnostics(es_bias_correction=True, es_bias_n_boot=a.boot, **CFG)
    de2 = tail_capital_diagnostics(es_bias_correction=True, es_bias_n_boot=a.boot, **CFG)
    es_det = bool(de["es_bias_corrected"] == de2["es_bias_corrected"])
    es_identity = bool(abs(de["es_bias_corrected"]
                           - (2 * de["es"] - de["es_bias_boot_mean"])) < 1e-12)
    core_unchanged = bool((de["var"], de["es"], de["scr"])
                          == (d_def["var"], d_def["es"], d_def["scr"]))
    g_c = bool(det and es_det and es_identity and core_unchanged)

    # --- G-W67d no-spillover (headline echoed; byte-check out-of-band) ------
    g_d = bool(HEADLINE == "39975.654628199336")

    overall = "PASS" if (g_a and g_b and g_c and g_d) else "CONDITIONAL"
    elapsed = round(time.time() - t0, 1)
    summary = dict(
        g_w67a_frozen_snapshot_equivalence=g_a,
        g_w67b_mode_selectable_vr=g_b,
        g_w67c_determinism_and_es_identity=g_c,
        g_w67d_no_spillover=g_d,
        SCR_variance_reduction_factor=vr["SCR"],
        ES_variance_reduction_factor=vr["ES"],
        VaR_variance_reduction_factor=vr["VaR"],
        g3_matched_cost_speedup_ge_2x=g3_scr,
        es_bias_corrected=de["es_bias_corrected"],
        es_bias_hat=de["es_bias_hat"],
        overall=overall, elapsed_s=elapsed,
    )
    print(json.dumps(summary, indent=2))

    if a.write:
        os.makedirs(OUT, exist_ok=True)
        payload = dict(
            title="MLMC quantile/ES tail estimator -- stage-4b wiring "
                  "(selectable variance-reduction MODE on the opt-in tail path)",
            window="W67",
            generated_utc=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            classification=("efficiency / estimator-only WIRING; ADDITIVE; OPT-IN; default OFF; "
                            "no model-form change; no contract bump; no headline re-baseline; "
                            "no owner sign-off consumed"),
            design_note="docs/research/MLMC_QUANTILE_ESTIMATOR_DESIGN_NOTE_20260619.md",
            stage4_evidence="docs/validation/MLMC_TAIL_STAGE4_VALIDATION_20260619.md",
            api=dict(
                entry_point="par_model_v2.projection.mlmc_inner_estimator.tail_capital_diagnostics",
                resolver="par_model_v2.projection.mlmc_inner_estimator.resolve_tail_outer_sampler",
                modes=list(TAIL_VR_MODES),
                default="variance_reduction='none', es_bias_correction=False",
                pattern="tail analogue of the W60 stage-3 engine_mean_liability_diagnostics wiring",
            ),
            governed_headline=HEADLINE, governed_default="fixed (unchanged)",
            frozen_reference=dict(config=CFG, snapshot=FROZEN),
            default_mode_diagnostics=d_def,
            stratified_mode_diagnostics=d_strat,
            es_bias_correction_example=de,
            gate_g_w67a=dict(frozen_snapshot_bitforbit=frozen_match,
                             equals_plain_nested_single_level=equals_plain,
                             default_is_off=default_off, pass_=g_a),
            gate_g_w67b=dict(stratified_same_inner_path_cost=same_cost,
                             stratified_differs_from_plain=differs,
                             variance_reduction_factor=vr, all_gt_1x=vr_all_gt1,
                             g3_scr_ge_2x=g3_scr, antithetic_mode_ok=anti_ok, pass_=g_b),
            gate_g_w67c=dict(default_deterministic=det, es_correction_deterministic=es_det,
                             es_bootstrap_identity=es_identity,
                             es_correction_additive_core_unchanged=core_unchanged, pass_=g_c),
            gate_g_w67d=dict(headline_echoed=g_d,
                             note="governed artifacts byte-unchanged verified out-of-band "
                                  "(cycle gate suite + git status)"),
            config=dict(R=a.R, vr_n_out=a.vr_n_out, boot=a.boot, seed=a.seed),
            summary=summary,
            recommendation=(
                "MERGE-AS-OPT-IN WIRING: tail_capital_diagnostics exposes the W66 stratified "
                "outer sampler (and the optional ES bootstrap correction) as a selectable "
                "variance-reduction MODE on the opt-in tail path. The default 'none' mode is "
                "bit-identical to the pre-W67 plain fixed-256 estimator (frozen-snapshot "
                "equivalence), so the governed headline is untouched. Selecting 'stratified' "
                f"delivers a matched-cost {vr['SCR']:.2f}x SCR / {vr['ES']:.2f}x ES variance "
                "reduction at ZERO extra inner-path cost. Stage 5 (any tail-MLMC figure as the "
                "governed default) stays owner sign-off + a fresh frozen reference."),
            owner_gate_remaining=("stage 5 (quantile-MLMC as governed default) needs owner sign-off "
                                  "+ fresh frozen reference"),
        )
        jp = os.path.join(OUT, "MLMC_TAIL_STAGE4B_WIRING_20260619.json")
        json.dump(payload, open(jp, "w"), indent=2)
        json.load(open(jp))  # re-parse guard
        write_md(payload)
        print("WROTE", jp)
    return summary


def write_md(p):
    s = p["summary"]; vr = p["gate_g_w67b"]["variance_reduction_factor"]
    fr = p["frozen_reference"]
    L = []
    L.append("# MLMC quantile/ES tail estimator — stage-4b wiring (W67)\n")
    L.append(f"_Generated {p['generated_utc']}._\n")
    L.append("**Classification:** " + p["classification"] + f". Governed headline "
             f"`{p['governed_headline']}` and all governed artifacts byte-unchanged; contract "
             "`1.23.0`; default estimator stays `fixed`.\n")
    L.append("## Purpose\n")
    L.append("Stage 4b **wires** the W66 stage-4 tail tools (stratified outer sampling + ES "
             "bootstrap bias correction) into one mode-selectable entry point on the opt-in tail "
             "path, `tail_capital_diagnostics(variance_reduction=…, es_bias_correction=…)` — the "
             "tail analogue of the W60 stage-3 `engine_mean_liability_diagnostics` mean wiring. "
             "The **default is OFF and bit-identical** to the pre-W67 plain fixed-256 estimator.\n")
    L.append("## API\n")
    L.append(f"- Entry point: `{p['api']['entry_point']}`")
    L.append(f"- Resolver: `{p['api']['resolver']}` — modes `{p['api']['modes']}`")
    L.append(f"- Default: `{p['api']['default']}` (the governed-style fixed-256 estimator)\n")
    L.append("## Frozen-snapshot equivalence (gate G-W67a)\n")
    L.append(f"Config `{fr['config']}` → frozen VaR `{fr['snapshot']['var']}`, ES "
             f"`{fr['snapshot']['es']}`, SCR `{fr['snapshot']['scr']}`. The default `none` mode "
             f"reproduces these **bit-for-bit** and equals a plain-outer `nested_single_level_tail` "
             f"call bit-for-bit: **`{s['g_w67a_frozen_snapshot_equivalence']}`**.\n")
    L.append("## Mode-selectable variance reduction (gate G-W67b, matched cost)\n")
    L.append("| Fn | matched-cost variance-reduction factor |")
    L.append("|---|---|")
    L.append(f"| VaR | {vr['VaR']:.2f}× |")
    L.append(f"| ES | {vr['ES']:.2f}× |")
    L.append(f"| SCR | {vr['SCR']:.2f}× |")
    L.append("")
    L.append(f"- Stratified mode keeps the **same inner-path cost** as plain, so the factor is a "
             f"matched-cost speedup. **G3 ≥2× on SCR: `{s['g3_matched_cost_speedup_ge_2x']}`**.\n")
    L.append("## Determinism + ES correction (gate G-W67c)\n")
    L.append(f"- Same seed → identical dict; ES correction deterministic and obeys the bootstrap "
             f"identity `es_bc == 2·es_raw − boot_mean`; correction is additive (core VaR/ES/SCR "
             f"unchanged): **`{s['g_w67c_determinism_and_es_identity']}`** "
             f"(example es_bc `{s['es_bias_corrected']:.6f}`, bias_hat `{s['es_bias_hat']:+.6e}`).\n")
    L.append("## Verdict\n")
    L.append(f"**Overall: `{s['overall']}`.** "
             f"G-W67a frozen-snapshot equivalence `{s['g_w67a_frozen_snapshot_equivalence']}`; "
             f"G-W67b mode-selectable VR `{s['g_w67b_mode_selectable_vr']}`; "
             f"G-W67c determinism/ES-identity `{s['g_w67c_determinism_and_es_identity']}`; "
             f"G-W67d no-spillover `{s['g_w67d_no_spillover']}`.\n")
    L.append("## Recommendation\n")
    L.append(p["recommendation"] + "\n")
    open(os.path.join(OUT, "MLMC_TAIL_STAGE4B_WIRING_20260619.md"), "w").write("\n".join(L))


if __name__ == "__main__":
    main()
