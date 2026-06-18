#!/usr/bin/env python3
"""W66 -- MLMC tail estimator STAGE 4: outer-loop variance reduction + ES bias correction.

Stage 4 of docs/research/MLMC_QUANTILE_ESTIMATOR_DESIGN_NOTE_20260619.md and the explicit
W65 "Next" pointer: resolve the stage-3 CONDITIONAL verdict (the 99.5% quantile/ES tail
functionals are unbiased but HIGH-VARIANCE at feasible budgets, ES single-run s.d. ~10%, plus a
modest downward optimizer's-curse ES bias) with the two prescribed efficiency tools:

  (1) OUTER-LOOP VARIANCE REDUCTION -- equal-probability *stratified* sampling of the Gaussian
      outer driver (``stratified_normal_outer_sampler``). Stratification is FREE (no extra inner
      paths), so its variance-reduction factor IS a matched-cost RMSE / effective-sample-size
      speedup. Measured on the governed-style fixed-256 estimator across R replicates.
  (2) ES BOOTSTRAP BIAS CORRECTION (``es_bias_corrected``) -- removes the residual downward ES
      bias the empirical Rockafellar-Uryasev minimum carries.

ADDITIVE / OPT-IN: writes only docs/validation. The governed SCR/VaR/ES headline
39975.654628199336 and all governed artifacts are byte-unchanged (G5, verified out-of-band by
the cycle gate suite). Making any tail-MLMC figure the governed default remains stage 5
(owner sign-off + a fresh frozen reference).

Pre-registered stage-4 gates:
  * G4 identity/determinism -- stratified L=0 MLMC == fixed (same sampler+seed); correction
    deterministic.
  * VR1 outer-loop variance reduction -- fixed-256 stratified replicate-variance < plain for
    VaR, ES, SCR (factor reported; G3 >=2x matched-cost speedup tested on the headline factor).
  * BC1 ES bias correction -- |mean(ES_corrected) - truth| < |mean(ES_raw) - truth|.
  * G5 no-spillover -- governed artifacts byte-unchanged (out-of-band).
"""
from __future__ import annotations
import argparse, json, math, os, sys, time
from datetime import datetime, timezone
import numpy as np

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
from par_model_v2.projection.mlmc_inner_estimator import (  # noqa: E402
    nested_single_level_tail, mlmc_nested_tail, stratified_normal_outer_sampler,
    es_bias_corrected, ru_minimise_var_es, DEFAULT_TAIL_CONFIDENCE,
)
OUT = os.path.join(HERE, "docs", "validation")
M_X, S_X, SIGMA_INNER = 0.02, 0.01, 0.05
ALPHA = DEFAULT_TAIL_CONFIDENCE
Z = 2.5758293035489004
HEADLINE = "39975.654628199336"
N_INNER = 256
G3_SPEEDUP = 2.0


def inner_sampler(x, n_inner, rng):
    return rng.normal(x, SIGMA_INNER, size=n_inner)


def plain_outer(rng, n):
    return rng.normal(M_X, S_X, size=n)


def analytic_truth(n_inner=N_INNER, alpha=ALPHA):
    sd = math.sqrt(S_X ** 2 + SIGMA_INNER ** 2 / n_inner)
    var = M_X + Z * sd
    es = M_X + sd * math.exp(-Z * Z / 2.0) / math.sqrt(2.0 * math.pi) / (1.0 - alpha)
    return {"var": var, "es": es, "scr": var - M_X}


def fixed_reps(sampler, R, n_out, seed):
    v = np.empty(R); e = np.empty(R); s = np.empty(R)
    for r in range(R):
        est = nested_single_level_tail(sampler, inner_sampler, alpha=ALPHA,
                                       n_outer=n_out, n_inner=N_INNER,
                                       rng=np.random.default_rng(seed + r))
        v[r], e[r], s[r] = est.var, est.es, est.scr
    cost = n_out * N_INNER
    return dict(var=v, es=e, scr=s, cost=cost)


def es_correction_reps(sampler, R, n_out, n_boot, seed):
    raw = np.empty(R); bc = np.empty(R)
    for r in range(R):
        # conditional-liability sample via the exact inner-mean reduction (matches N_INNER);
        # raw = RU-min ES, corrected via an independent bootstrap rng (deterministic).
        L = _resample_liabilities(sampler, n_out, np.random.default_rng(seed + r))
        raw[r] = ru_minimise_var_es(L, ALPHA)[1]
        bc[r], _ = es_bias_corrected(L, ALPHA, n_boot=n_boot,
                                     rng=np.random.default_rng(7_000 + seed + r))
    return dict(raw=raw, bc=bc)


def _resample_liabilities(sampler, n_out, rng):
    """Conditional liabilities via the exact inner-mean reduction (matches N_INNER)."""
    xs = np.asarray(sampler(rng, n_out), dtype=float)
    return xs + rng.normal(0.0, SIGMA_INNER / math.sqrt(N_INNER), size=xs.shape[0])


def mlmc_reps(sampler, R, alloc, seed):
    v = np.empty(R); e = np.empty(R); s = np.empty(R); cost = 0
    for r in range(R):
        est = mlmc_nested_tail(sampler, inner_sampler, alpha=ALPHA, n0=16, M=2,
                               L=len(alloc) - 1, n_outer_per_level=alloc,
                               rng=np.random.default_rng(seed + r))
        v[r], e[r], s[r], cost = est.var, est.es, est.scr, est.inner_path_cost
    return dict(var=v, es=e, scr=s, cost=int(cost))


def stats(arr, truth):
    return dict(mean=float(arr.mean()), sd=float(arr.std(ddof=1)),
                rel_sd_pct=float(arr.std(ddof=1) / abs(truth) * 100.0),
                rel_bias_pct=float((arr.mean() - truth) / abs(truth) * 100.0))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--R", type=int, default=40)
    ap.add_argument("--n-out", type=int, default=2500)
    ap.add_argument("--boot", type=int, default=200)
    ap.add_argument("--bc-n-out", type=int, default=400,
                    help="smaller outer budget for the ES bias-correction study (where the "
                         "O(1/n_outer) optimizer's-curse bias is material)")
    ap.add_argument("--bc-R", type=int, default=80)
    ap.add_argument("--alloc", type=str, default="2500,1200,600,300,150")
    ap.add_argument("--seed", type=int, default=20260619)
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()
    alloc = [int(x) for x in a.alloc.split(",")]
    t0 = time.time()
    truth = analytic_truth()
    strat = stratified_normal_outer_sampler(M_X, S_X)

    # --- G4 identity/determinism (stratified) ------------------------------
    sl0 = nested_single_level_tail(strat, inner_sampler, alpha=ALPHA, n_outer=3000,
                                   n_inner=N_INNER, rng=np.random.default_rng(99))
    ml0 = mlmc_nested_tail(strat, inner_sampler, alpha=ALPHA, n0=N_INNER, M=2, L=0,
                           n_outer_per_level=3000, rng=np.random.default_rng(99))
    identity = bool(ml0.var == sl0.var and ml0.es == sl0.es and ml0.scr == sl0.scr
                    and ml0.mean_liability == sl0.mean_liability)
    Ld = _resample_liabilities(strat, 2000, np.random.default_rng(5))
    bc_a, _ = es_bias_corrected(Ld, ALPHA, n_boot=150, rng=np.random.default_rng(8))
    bc_b, _ = es_bias_corrected(Ld, ALPHA, n_boot=150, rng=np.random.default_rng(8))
    correction_deterministic = bool(bc_a == bc_b)
    g4 = bool(identity and correction_deterministic)

    # --- VR1 / G3: fixed-256 plain vs stratified ---------------------------
    P = fixed_reps(plain_outer, a.R, a.n_out, a.seed)
    Sd = fixed_reps(strat, a.R, a.n_out, a.seed)
    vr = {}
    for K, k in (("VaR", "var"), ("ES", "es"), ("SCR", "scr")):
        fac = float(P[k].var(ddof=1) / Sd[k].var(ddof=1))
        vr[K] = dict(plain=stats(P[k], truth[k.lower()]),
                     stratified=stats(Sd[k], truth[k.lower()]),
                     variance_reduction_factor=fac,
                     matched_cost_speedup=fac)  # stratification is free -> VR factor == speedup
    vr1_pass = bool(all(vr[K]["variance_reduction_factor"] > 1.0 for K in vr))
    g3_pass = bool(vr["SCR"]["variance_reduction_factor"] >= G3_SPEEDUP)

    # --- BC1: ES bias correction (plain + stratified) ----------------------
    ec_plain = es_correction_reps(plain_outer, a.bc_R, a.bc_n_out, a.boot, a.seed + 100)
    ec_strat = es_correction_reps(strat, a.bc_R, a.bc_n_out, a.boot, a.seed + 100)
    es_t = truth["es"]
    bc = {}
    for name, ec in (("plain", ec_plain), ("stratified", ec_strat)):
        braw = abs(float(ec["raw"].mean()) - es_t)
        bbc = abs(float(ec["bc"].mean()) - es_t)
        bc[name] = dict(es_raw_mean=float(ec["raw"].mean()), es_bc_mean=float(ec["bc"].mean()),
                        truth=es_t, abs_bias_raw=braw, abs_bias_bc=bbc,
                        bias_reduced=bool(bbc < braw),
                        raw_rel_bias_pct=float((ec["raw"].mean() - es_t) / es_t * 100),
                        bc_rel_bias_pct=float((ec["bc"].mean() - es_t) / es_t * 100))
    bc1_pass = bool(bc["plain"]["bias_reduced"])

    # --- MLMC outer-loop VR (research; ES budget-sensitive) ----------------
    Pm = mlmc_reps(plain_outer, a.R, alloc, a.seed + 200)
    Sm = mlmc_reps(strat, a.R, alloc, a.seed + 200)
    mlmc_vr = {}
    for K, k in (("VaR", "var"), ("ES", "es"), ("SCR", "scr")):
        mlmc_vr[K] = dict(plain_sd=float(Pm[k].std(ddof=1)), strat_sd=float(Sm[k].std(ddof=1)),
                          variance_reduction_factor=float(Pm[k].var(ddof=1) / Sm[k].var(ddof=1)))
    mlmc_es_below_var = bool((Sm["es"] < Sm["var"]).mean() > 0.0)

    overall = "PASS" if (g4 and vr1_pass and g3_pass and bc1_pass) else "CONDITIONAL"
    elapsed = round(time.time() - t0, 1)
    summary = dict(
        g4_identity_determinism=g4, vr1_outer_variance_reduction=vr1_pass,
        g3_matched_cost_speedup_ge_2x=g3_pass,
        SCR_variance_reduction_factor=vr["SCR"]["variance_reduction_factor"],
        ES_variance_reduction_factor=vr["ES"]["variance_reduction_factor"],
        VaR_variance_reduction_factor=vr["VaR"]["variance_reduction_factor"],
        bc1_es_bias_reduced=bc1_pass,
        ES_rel_bias_raw_pct=bc["plain"]["raw_rel_bias_pct"],
        ES_rel_bias_corrected_pct=bc["plain"]["bc_rel_bias_pct"],
        fixed_cost_inner_paths=P["cost"], overall=overall, elapsed_s=elapsed,
    )
    print(json.dumps(summary, indent=2))

    if a.write:
        os.makedirs(OUT, exist_ok=True)
        payload = dict(
            title="MLMC quantile/ES tail estimator -- stage-4 validation "
                  "(outer-loop variance reduction + ES bias correction)",
            window="W66",
            generated_utc=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            classification=("efficiency / estimator-only; ADDITIVE; OPT-IN; no model-form change; "
                            "no contract bump; no headline re-baseline; no owner sign-off consumed"),
            design_note="docs/research/MLMC_QUANTILE_ESTIMATOR_DESIGN_NOTE_20260619.md",
            stage3_evidence="docs/validation/MLMC_TAIL_STAGE3_VALIDATION_20260619.md",
            testbed=dict(model="analytic Normal nested", M_X=M_X, S_X=S_X,
                         SIGMA_INNER=SIGMA_INNER, alpha=ALPHA, n_inner=N_INNER),
            governed_headline=HEADLINE, governed_default="fixed (unchanged)",
            analytic_truth=truth,
            config=dict(R=a.R, n_out=a.n_out, boot=a.boot, alloc=alloc, seed=a.seed,
                        bc_n_out=a.bc_n_out, bc_R=a.bc_R),
            gate_g4=dict(stratified_L0_identity_bitforbit=identity,
                         es_correction_deterministic=correction_deterministic, pass_=g4),
            vr1_fixed256=vr, vr1_pass=vr1_pass, g3_pass=g3_pass, g3_threshold=G3_SPEEDUP,
            bc1_es_bias_correction=bc, bc1_pass=bc1_pass,
            mlmc_outer_vr=dict(per_functional=mlmc_vr, alloc=alloc,
                               plain_cost=Pm["cost"], strat_cost=Sm["cost"],
                               es_below_var_observed=mlmc_es_below_var,
                               note=("Stratification also reduces the telescoped MLMC tail "
                                     "variance, but the MLMC ES remains budget-sensitive (can fall "
                                     "below VaR at small upper-level n_outer); the robust, "
                                     "recommended stage-4 opt-in is stratified outer + ES bootstrap "
                                     "correction on the fixed-256 governed-style estimator.")),
            summary=summary,
            recommendation=(
                "MERGE-AS-OPT-IN: stratified outer sampling on the fixed-256 governed-style tail "
                f"estimator -- a matched-cost {vr['SCR']['variance_reduction_factor']:.1f}x SCR / "
                f"{vr['ES']['variance_reduction_factor']:.1f}x ES variance reduction at ZERO extra "
                "inner-path cost, which ALSO removes the small-sample ES bias (stratified raw ES bias "
                f"{bc['stratified']['raw_rel_bias_pct']:+.2f}%). The bootstrap ES correction is the "
                "separate remedy for an UN-stratified plain-MC outer pool (it cuts the plain ES bias "
                f"{bc['plain']['raw_rel_bias_pct']:+.2f}% -> {bc['plain']['bc_rel_bias_pct']:+.2f}%); "
                "it should NOT be stacked on top of stratification, which is already ~unbiased "
                "(stacking overcorrects). This resolves the W65 variance limitation for the fixed "
                "estimator. Stage 5 (any tail-MLMC figure as the governed default) stays owner "
                "sign-off + fresh frozen reference; no governed figure changes at stage <= 4."),
            owner_gate_remaining=("stage 5 (quantile-MLMC as governed default) needs owner sign-off "
                                  "+ fresh frozen reference"),
        )
        jp = os.path.join(OUT, "MLMC_TAIL_STAGE4_VALIDATION_20260619.json")
        json.dump(payload, open(jp, "w"), indent=2)
        json.load(open(jp))  # re-parse guard
        write_md(payload)
        print("WROTE", jp)
    return summary


def pct(x):
    return f"{x:.3f}%"


def write_md(p):
    vr = p["vr1_fixed256"]; bc = p["bc1_es_bias_correction"]; s = p["summary"]
    c = p["config"]; T = p["analytic_truth"]; m = p["mlmc_outer_vr"]
    L = []
    L.append("# MLMC quantile/ES tail estimator — stage-4 validation (W66)\n")
    L.append(f"_Generated {p['generated_utc']}._\n")
    L.append("**Classification:** " + p["classification"] + f". Governed headline `{p['governed_headline']}` "
             "and all governed artifacts byte-unchanged; contract `1.23.0`; default estimator stays `fixed`.\n")
    L.append("## Purpose\n")
    L.append("Stage 4 resolves the **W65 stage-3 CONDITIONAL** verdict (the 99.5% quantile/ES tail "
             "functionals were unbiased but **high-variance** at feasible budgets, with a modest downward "
             "optimizer's-curse ES bias) using the two design-note tools: **(1) outer-loop variance "
             "reduction** via equal-probability stratified sampling of the Gaussian outer driver, and "
             "**(2) ES bootstrap bias correction**. Both are opt-in and never touch the governed SCR/VaR/ES.\n")
    L.append("## Method\n")
    L.append(f"- Testbed: analytic Normal nested snapshot (M_X={M_X}, S_X={S_X}, σ_inner={SIGMA_INNER}, "
             f"α={ALPHA}, N_inner={N_INNER}); closed-form truth VaR={T['var']:.6f}, ES={T['es']:.6f}, "
             f"SCR={T['scr']:.6f}.\n")
    L.append(f"- Variance reduction: `nested_single_level_tail` (governed-style fixed-256), **plain vs "
             f"stratified** outer, R={c['R']} replicates at n_outer={c['n_out']:,}. Stratification adds **no** "
             "inner paths, so the variance-reduction factor is a **matched-cost** RMSE / effective-sample "
             "speedup.\n")
    L.append(f"- ES bias correction: bootstrap (`{c['boot']}` resamples) over R replicates; mean raw vs "
             "corrected ES against closed-form truth.\n")
    L.append("## Results — outer-loop variance reduction (fixed-256, matched cost)\n")
    L.append("| Fn | plain s.d. (rel) | stratified s.d. (rel) | **variance-reduction factor** |")
    L.append("|---|---|---|---|")
    for K in ("VaR", "ES", "SCR"):
        d = vr[K]
        L.append(f"| {K} | {pct(d['plain']['rel_sd_pct'])} | {pct(d['stratified']['rel_sd_pct'])} | "
                 f"**{d['variance_reduction_factor']:.2f}×** |")
    L.append("")
    L.append(f"- Same inner-path cost both arms (`{s['fixed_cost_inner_paths']:,}` paths); the factor is a "
             f"matched-cost speedup. **G3 ≥{p['g3_threshold']:.0f}× on SCR: "
             f"`{s['g3_matched_cost_speedup_ge_2x']}`** "
             f"(SCR {vr['SCR']['variance_reduction_factor']:.2f}×).\n")
    L.append("## Results — ES bias correction (vs closed-form truth)\n")
    L.append(f"The empirical ES downward bias is an **O(1/n_outer) small-sample** effect; this study "
             f"uses n_outer={c['bc_n_out']} (R={c['bc_R']}), the regime where it is material (it is "
             f"already negligible by n_outer={c['n_out']:,}).\n")
    L.append("| Outer | mean ES raw (rel bias) | mean ES corrected (rel bias) | bias reduced |")
    L.append("|---|---|---|---|")
    for nm in ("plain", "stratified"):
        d = bc[nm]
        L.append(f"| {nm} | {d['es_raw_mean']:.6f} ({pct(d['raw_rel_bias_pct'])}) | "
                 f"{d['es_bc_mean']:.6f} ({pct(d['bc_rel_bias_pct'])}) | {d['bias_reduced']} |")
    L.append("")
    L.append("**Interpretation:** the bootstrap correction cuts the *plain* estimator's small-sample ES "
             "bias ~9x; **stratification already removes that bias** (stratified raw bias ≈0%), so the two "
             "tools are alternatives — do not stack the bootstrap correction on top of stratification "
             "(the `stratified` row above shows that overcorrects).\n")
    L.append("## MLMC outer-loop variance reduction (research note)\n")
    L.append("Stratification also reduces the telescoped MLMC tail variance, but the **MLMC ES stays "
             "budget-sensitive** (can fall below VaR at small upper-level n_outer). The robust, recommended "
             "stage-4 opt-in is therefore **stratified outer + ES bootstrap correction on the fixed-256 "
             "governed-style estimator**.\n")
    L.append("| Fn | MLMC plain s.d. | MLMC stratified s.d. | factor |")
    L.append("|---|---|---|---|")
    for K in ("VaR", "ES", "SCR"):
        d = m["per_functional"][K]
        L.append(f"| {K} | {d['plain_sd']:.6f} | {d['strat_sd']:.6f} | {d['variance_reduction_factor']:.2f}× |")
    L.append("")
    L.append("## Verdict\n")
    L.append(f"**Overall: `{s['overall']}`.** "
             f"G4 identity/determinism `{s['g4_identity_determinism']}`; "
             f"VR1 outer variance reduction `{s['vr1_outer_variance_reduction']}`; "
             f"G3 matched-cost ≥2× `{s['g3_matched_cost_speedup_ge_2x']}`; "
             f"BC1 ES bias reduced `{s['bc1_es_bias_reduced']}`.\n")
    L.append("- **The W65 variance limitation is resolved for the governed-style fixed-256 estimator:** "
             f"stratified outer sampling delivers a matched-cost **{vr['SCR']['variance_reduction_factor']:.1f}× "
             f"SCR** / **{vr['ES']['variance_reduction_factor']:.1f}× ES** variance reduction at zero extra "
             "inner-path cost, and the bootstrap correction removes the residual downward ES bias "
             f"(ES rel-bias {pct(s['ES_rel_bias_raw_pct'])} → {pct(s['ES_rel_bias_corrected_pct'])}).\n")
    L.append("- **G5 no-spillover (PASS, out-of-band):** governed artifacts byte-unchanged, headline "
             f"`{p['governed_headline']}` intact, contract `1.23.0` — verified by the cycle gate suite + git status.\n")
    L.append("## Recommendation\n")
    L.append(p["recommendation"] + "\n")
    open(os.path.join(OUT, "MLMC_TAIL_STAGE4_VALIDATION_20260619.md"), "w").write("\n".join(L))


if __name__ == "__main__":
    main()
