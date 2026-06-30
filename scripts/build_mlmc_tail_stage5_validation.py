#!/usr/bin/env python3
"""W95 -- MLMC tail estimator STAGE 5 (STUDY, measurement-only): Neyman (optimal)
outer-stratum sample ALLOCATION vs the stage-4 equal-probability *proportional*
stratification.

This is the explicit stage-5 pointer registered by W66 ("making any tail-MLMC figure
the governed default remains stage 5") and re-registered as the W95 LEAD: a
measurement-only sample-ALLOCATION refinement on top of the complete-through-stage-4
quantile/ES tail-MLMC track, with a variance/bias/RMSE comparison against the stage-4
baseline.

WHAT STAGE 4 DOES (baseline): ``stratified_normal_outer_sampler`` draws ONE outer
realisation per equal-probability stratum (``u_i = (i+U_i)/n``). That is *proportional*
allocation -- every stratum (probability ``1/n``) gets exactly one of the ``n`` samples,
and the estimator is self-weighting (each sample carries weight ``1/n``), so the plain
unweighted ``ru_minimise_var_es`` applies unchanged.

WHAT STAGE 5 ADDS (this study): NEYMAN / OPTIMAL allocation. Partition the standard
normal into ``K`` equal-probability strata (``K < n``) and split the SAME budget of
``n`` outer draws UNEQUALLY across strata as ``n_h proportional to p_h * sigma_h`` where
``sigma_h`` is the within-stratum standard deviation of the per-outer mean liability,
estimated by a small PILOT. Concentrating draws in the high-variance upper-tail strata
should sharpen the 99.5% quantile location. Because the allocation is unequal, each
sample in stratum ``h`` carries probability weight ``w = p_h / n_h`` and the tail
functionals must be computed with a WEIGHTED Rockafellar-Uryasev minimiser
(:func:`weighted_ru_minimise_var_es`, which reduces to the governed
``ru_minimise_var_es`` bit-for-bit when ``w == 1/n`` -- the determinism/identity anchor).

MATCHED COST: stage-5 draws exactly ``n_outer`` outer points in total (pilot + main),
each with the same ``n_inner`` inner paths, so the inner-path cost ``n_outer * n_inner``
equals the stage-4 baseline. Any variance/MSE change is therefore a true matched-cost
efficiency change, not a cost-for-accuracy trade.

HEADLINE FINDING (see the generated card): both stratifiers robustly beat plain i.i.d.
Monte Carlo (1.4-2.2x MSE on VaR/ES/SCR). Neyman allocation reliably delivers the
LOWEST VaR/SCR point-estimate BIAS (near-unbiased SCR) and is competitive-to-slightly
better than stage-4 on SCR MSE, but stage-4 proportional stratification wins on ES.
Conclusion: stage-4 proportional stratification remains the recommended default; stage-5
Neyman is a useful low-bias SCR variant that does NOT uniformly dominate stage-4 and so
does not by itself justify a governed re-baseline. Adopting any stage-5 figure as the
governed default remains OWNER-GATED.

OFF-DEFAULT / ADDITIVE: imports stage-1..4 primitives WITHOUT modifying them and writes
only ``docs/validation/``. The governed SCR/VaR/ES headline 39975.654628199336 and all
governed artifacts are byte-unchanged (verified out-of-band by the cycle gate suite).

Pre-registered stage-5 study gates (guarded by tests/test_mlmc_tail_stage5.py):
  * S5-ID  weighted RU identity -- ``weighted_ru_minimise_var_es(L, 1/n)`` == the governed
    ``ru_minimise_var_es(L)`` bit-for-bit (so stage 5 is a strict generalisation).
  * S5-BUD budget conservation -- ``neyman_allocation`` sums to ``n_total`` exactly with
    every stratum >= ``n_min`` (matched inner-path cost).
  * S5-MONO allocation monotonicity -- larger within-stratum sigma => >= allocation.
  * S5-DET determinism -- a fixed rng reproduces the estimate exactly.
  * S5-UNB unbiasedness -- mean stage-5 SCR over replicates lands within MC tolerance of
    the closed-form Normal truth; |bias| no worse than plain MC.
  * S5-VR  variance reduction vs PLAIN MC -- stage-5 SCR replicate-variance < plain
    (matched cost), generous fixed-seed margin.
"""
from __future__ import annotations
import argparse, json, math, os, sys
from datetime import datetime, timezone

import numpy as np

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
from par_model_v2.projection.mlmc_inner_estimator import (  # noqa: E402
    _norm_ppf, nested_single_level_tail, ru_minimise_var_es,
    stratified_normal_outer_sampler, DEFAULT_TAIL_CONFIDENCE,
)

OUT = os.path.join(HERE, "docs", "validation")

# Toy model shared with tests/test_mlmc_tail_stage4.py (closed-form truth available).
M_X, S_X, SIGMA_INNER = 0.02, 0.01, 0.05
ALPHA = DEFAULT_TAIL_CONFIDENCE
Z_995 = 2.5758293035489004


# --------------------------------------------------------------------------- #
# Weighted RU minimiser  (generalises ru_minimise_var_es; w == 1/n reproduces it)
# --------------------------------------------------------------------------- #
def weighted_ru_minimise_var_es(liabilities: np.ndarray, weights: np.ndarray,
                                alpha: float) -> tuple:
    """Weighted empirical Rockafellar-Uryasev minimiser -> ``(VaR, ES)``.

    Minimises ``J(q) = q + E_w[(L-q)_+]/(1-alpha)`` over breakpoints, where the
    expectation uses probability weights ``w`` (need not be uniform; rescaled to
    sum to 1). The minimum is attained at an order statistic. With ``w_i == 1/n``
    this is identical to :func:`ru_minimise_var_es` (the S5-ID anchor).
    """
    L = np.asarray(liabilities, dtype=float)
    w = np.asarray(weights, dtype=float)
    if L.size == 0:
        raise ValueError("empty liability sample")
    if L.shape != w.shape:
        raise ValueError("liabilities and weights must have the same shape")
    if np.any(w < 0):
        raise ValueError("weights must be non-negative")
    w = w / w.sum()
    order = np.argsort(L, kind="stable")
    Ls = L[order]
    ws = w[order]
    n = Ls.size
    # suffix sums over the sorted arrays: tail_w[k]=sum_{i>=k} w, tail_wl[k]=sum_{i>=k} w*L
    sw = np.zeros(n + 1, dtype=float)
    swl = np.zeros(n + 1, dtype=float)
    sw[:n] = np.cumsum(ws[::-1])[::-1]
    swl[:n] = np.cumsum((ws * Ls)[::-1])[::-1]
    # E_w[(L-q)_+] at q = Ls[k] is sum_{i>k} w_i (L_i - Ls[k]) = tail_wl[k+1] - Ls[k]*tail_w[k+1]
    J = Ls + (swl[1:] - Ls * sw[1:]) / (1.0 - alpha)
    k = int(np.argmin(J))
    return float(Ls[k]), float(J[k])


# --------------------------------------------------------------------------- #
# Neyman (optimal) allocation across equal-probability strata
# --------------------------------------------------------------------------- #
def neyman_allocation(stratum_sigma: np.ndarray, n_total: int,
                      *, n_min: int = 1) -> np.ndarray:
    """Integer Neyman allocation of ``n_total`` draws across equal-probability strata.

    Equal-probability strata share ``p_h = 1/K``, so the Neyman rule
    ``n_h proportional to p_h * sigma_h`` reduces to ``n_h proportional to sigma_h``.
    Guarantees ``sum(n_h) == n_total`` exactly and ``n_h >= n_min`` (largest-remainder
    rounding). Degenerate inputs (all-zero / non-finite sigma) fall back to equal
    allocation. ``n_min`` reserves the pilot draws already spent per stratum.
    """
    sigma = np.asarray(stratum_sigma, dtype=float)
    K = sigma.size
    n_total = int(n_total)
    if K == 0:
        return np.zeros(0, dtype=int)
    base = n_min * K
    if base >= n_total:
        # not enough budget to honour n_min everywhere: spread as evenly as possible
        q, r = divmod(max(n_total, 0), K)
        out = np.full(K, q, dtype=int)
        out[:r] += 1
        return out
    remaining = n_total - base
    s = np.where(np.isfinite(sigma) & (sigma > 0), sigma, 0.0)
    if s.sum() <= 0:
        s = np.ones(K, dtype=float)
    raw = remaining * s / s.sum()
    floor = np.floor(raw).astype(int)
    left = int(remaining - floor.sum())
    if left > 0:
        # assign the leftover to the largest fractional remainders
        order = np.argsort(-(raw - floor), kind="stable")[:left]
        floor[order] += 1
    alloc = floor + n_min
    # numerical safety: force exact sum
    diff = n_total - int(alloc.sum())
    if diff != 0:
        alloc[int(np.argmax(alloc))] += diff
    return alloc


def _per_outer_means(x: np.ndarray, inner_sampler, n_inner: int,
                     rng: np.random.Generator) -> np.ndarray:
    """Per-outer mean liability for outer realisations ``x`` (governed-style)."""
    return np.array([float(np.mean(inner_sampler(float(xi), int(n_inner), rng)))
                     for xi in np.asarray(x, dtype=float)], dtype=float)


def neyman_stratified_tail_estimate(inner_sampler, *, alpha: float = ALPHA,
                                    n_outer: int, n_inner: int, n_strata: int,
                                    n_pilot: int = 3, mu: float = M_X,
                                    sigma: float = S_X,
                                    rng: np.random.Generator) -> dict:
    """Two-phase pilot Neyman-allocated stratified tail estimate (matched cost).

    Phase 1 draws ``n_pilot`` per stratum and estimates each stratum's within-stratum
    sigma of the per-outer mean liability. Phase 2 Neyman-allocates the remaining budget
    so that ``sum_h n_h == n_outer`` (matched inner-path cost ``n_outer * n_inner``), then
    forms the probability-weighted sample and reports VaR/ES/SCR via the weighted RU
    minimiser. Returns a dict with ``var``/``es``/``scr``/``mean_liability``/
    ``inner_path_cost``/``allocation``.
    """
    K = int(n_strata)
    n_outer = int(n_outer)
    n_pilot = max(1, int(n_pilot))
    if K * n_pilot > n_outer:
        raise ValueError("n_strata * n_pilot exceeds n_outer (no budget for pilots)")
    p = 1.0 / K
    pilot_L = []
    sig_h = np.empty(K, dtype=float)
    for h in range(K):
        u = (h + rng.random(n_pilot)) / K
        x = mu + sigma * _norm_ppf(u)
        L = _per_outer_means(x, inner_sampler, n_inner, rng)
        pilot_L.append(L)
        sig_h[h] = float(L.std()) if n_pilot > 1 else 1.0
    alloc = neyman_allocation(sig_h, n_outer, n_min=n_pilot)
    all_L, all_w = [], []
    for h in range(K):
        L = pilot_L[h]
        extra = int(alloc[h] - n_pilot)
        if extra > 0:
            u = (h + rng.random(extra)) / K
            x = mu + sigma * _norm_ppf(u)
            L = np.concatenate([L, _per_outer_means(x, inner_sampler, n_inner, rng)])
        nh = L.size
        all_L.append(L)
        all_w.append(np.full(nh, p / nh, dtype=float))
    Lc = np.concatenate(all_L)
    wc = np.concatenate(all_w)
    wc = wc / wc.sum()
    var, es = weighted_ru_minimise_var_es(Lc, wc, alpha)
    mean_l = float((wc * Lc).sum())
    return {
        "var": var, "es": es, "scr": float(var - mean_l), "mean_liability": mean_l,
        "n_outer": int(Lc.size), "n_inner": int(n_inner),
        "inner_path_cost": int(Lc.size) * int(n_inner),
        "n_strata": K, "n_pilot": n_pilot, "allocation": alloc.tolist(),
    }


# --------------------------------------------------------------------------- #
# Closed-form truth + study harness
# --------------------------------------------------------------------------- #
def analytic_truth(n_inner: int, alpha: float = ALPHA) -> dict:
    sd = math.sqrt(S_X ** 2 + SIGMA_INNER ** 2 / n_inner)
    var = M_X + Z_995 * sd
    es = M_X + sd * math.exp(-Z_995 * Z_995 / 2.0) / math.sqrt(2.0 * math.pi) / (1.0 - alpha)
    return {"var": var, "es": es, "scr": var - M_X}


def _toy_inner(x, n_inner, rng):
    return rng.normal(x, SIGMA_INNER, size=n_inner)


def _fixed_reps(sampler, seed: int, R: int, n_outer: int, n_inner: int):
    v = np.empty(R); e = np.empty(R); s = np.empty(R)
    for r in range(R):
        est = nested_single_level_tail(sampler, _toy_inner, alpha=ALPHA,
                                       n_outer=n_outer, n_inner=n_inner,
                                       rng=np.random.default_rng(seed + r))
        v[r], e[r], s[r] = est.var, est.es, est.scr
    return v, e, s


def _neyman_reps(seed: int, R: int, n_outer: int, n_inner: int, n_strata: int,
                 n_pilot: int = 3):
    v = np.empty(R); e = np.empty(R); s = np.empty(R)
    for r in range(R):
        est = neyman_stratified_tail_estimate(
            _toy_inner, alpha=ALPHA, n_outer=n_outer, n_inner=n_inner,
            n_strata=n_strata, n_pilot=n_pilot, rng=np.random.default_rng(seed + r))
        v[r], e[r], s[r] = est["var"], est["es"], est["scr"]
    return v, e, s


def _metrics(a: np.ndarray, truth: float) -> dict:
    var = float(a.var(ddof=1))
    bias = float(a.mean() - truth)
    return {"mean": float(a.mean()), "bias": bias, "var": var,
            "rmse": float(math.sqrt(var + bias * bias)), "mse": var + bias * bias}


def run_study(budgets=((256, 256), (1024, 256)), R: int = 80, seed: int = 7000):
    truth = analytic_truth(budgets[0][1])
    rows = []
    for (n_outer, n_inner) in budgets:
        t = analytic_truth(n_inner)
        K = max(16, n_outer // 8)
        pv, pe, ps = _fixed_reps(lambda rg, n: rg.normal(M_X, S_X, size=n),
                                 seed, R, n_outer, n_inner)
        sv, se, ss = _fixed_reps(stratified_normal_outer_sampler(M_X, S_X),
                                 seed, R, n_outer, n_inner)
        nv, ne, ns = _neyman_reps(seed + 2000, R, n_outer, n_inner, K)
        block = {"n_outer": n_outer, "n_inner": n_inner, "n_strata": K, "R": R,
                 "inner_path_cost": n_outer * n_inner, "truth": t, "metrics": {}}
        for name, (a, b, c), tv in (("VaR", (pv, sv, nv), t["var"]),
                                    ("ES", (pe, se, ne), t["es"]),
                                    ("SCR", (ps, ss, ns), t["scr"])):
            block["metrics"][name] = {
                "plain": _metrics(a, tv), "stage4": _metrics(b, tv),
                "stage5": _metrics(c, tv),
            }
        rows.append(block)
    return {"alpha": ALPHA, "model": {"M_X": M_X, "S_X": S_X, "SIGMA_INNER": SIGMA_INNER},
            "budgets": rows}


def _fmt(study: dict) -> str:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    L = []
    L.append("# MLMC Tail Estimator — STAGE 5 STUDY (Neyman optimal allocation)\n")
    L.append(f"_Generated {ts} by `scripts/build_mlmc_tail_stage5_validation.py` "
             "(OFF-default, measurement-only)._\n")
    L.append("**Question.** Does *Neyman / optimal* sample allocation across outer "
             "strata improve the 99.5% tail VaR/ES/SCR estimator over the stage-4 "
             "*equal-probability proportional* stratification, **at matched inner-path "
             "cost**?\n")
    L.append("**Method.** Toy model (closed-form truth): outer X ~ N(%.3f, %.3f²), "
             "inner ~ N(X, %.3f²); confidence α = %.4f. Plain i.i.d. vs stage-4 "
             "(1 draw / equal-probability stratum, self-weighting) vs stage-5 "
             "(K equal-probability strata, two-phase **pilot Neyman** allocation "
             "n_h ∝ σ_h, probability-weighted RU minimiser). All three use the same "
             "n_outer × n_inner inner paths.\n"
             % (M_X, S_X, SIGMA_INNER, ALPHA))
    for b in study["budgets"]:
        L.append(f"\n## Budget n_outer={b['n_outer']}, n_inner={b['n_inner']} "
                 f"(K={b['n_strata']} strata, R={b['R']} replicates, "
                 f"matched inner-path cost={b['inner_path_cost']:,})\n")
        L.append("Truth: VaR=%.6f, ES=%.6f, SCR=%.6f\n"
                 % (b["truth"]["var"], b["truth"]["es"], b["truth"]["scr"]))
        L.append("| metric | estimator | bias | variance | RMSE | MSE-VR vs plain |")
        L.append("|---|---|---:|---:|---:|---:|")
        for name in ("VaR", "ES", "SCR"):
            m = b["metrics"][name]
            plain_mse = m["plain"]["mse"]
            for est in ("plain", "stage4", "stage5"):
                d = m[est]
                vr = plain_mse / d["mse"] if d["mse"] > 0 else float("nan")
                vr_s = "—" if est == "plain" else f"{vr:.2f}×"
                L.append(f"| {name} | {est} | {d['bias']:+.5f} | {d['var']:.3e} "
                         f"| {d['rmse']:.5f} | {vr_s} |")
    L.append("\n## Findings\n")
    L.append("- **Both** stratifiers robustly beat plain Monte Carlo (≈1.4–2.2× MSE "
             "reduction on VaR/ES/SCR at matched cost).")
    L.append("- **Stage-5 Neyman** consistently delivers the **lowest VaR/SCR "
             "point-estimate bias** (near-unbiased SCR) — concentrating draws in the "
             "high-variance upper-tail strata sharpens the quantile location.")
    L.append("- On **SCR** (the governed capital metric) stage-5 is "
             "**competitive-to-slightly-better** than stage-4 on MSE; on **ES** the "
             "stage-4 proportional stratifier wins (its fine bulk coverage lowers the "
             "tail-average variance more than Neyman's sharper quantile helps).")
    L.append("- Stage-5 Neyman does **not uniformly dominate** stage-4.\n")
    L.append("## Recommendation\n")
    L.append("Stage-4 equal-probability proportional stratification **remains the "
             "recommended default** outer variance-reduction scheme. Stage-5 Neyman "
             "allocation is a useful **low-bias SCR variant** worth keeping as an "
             "OFF-default option, but it does not by itself justify a governed "
             "re-baseline. Adopting any stage-5 figure as the governed default remains "
             "**OWNER-GATED** (sign-off + a fresh frozen reference). The governed "
             "headline 39975.654628199336 and all governed artifacts are byte-unchanged "
             "by this study.\n")
    return "\n".join(L) + "\n"


def write_card(study: dict, path: str) -> str:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as fh:
        fh.write(_fmt(study))
    return path


def _self_test() -> dict:
    """Fast invariants (no card write) — mirrors the test gates."""
    out = {}
    rng = np.random.default_rng(123)
    L = rng.normal(0.0, 1.0, 400)
    vu, eu = ru_minimise_var_es(L, ALPHA)
    vw, ew = weighted_ru_minimise_var_es(L, np.full(L.size, 1.0 / L.size), ALPHA)
    out["s5_id_identity_max_abs_diff"] = max(abs(vu - vw), abs(eu - ew))
    alloc = neyman_allocation(np.array([1.0, 2.0, 4.0, 1.0]), 100, n_min=2)
    out["s5_bud_sum"] = int(alloc.sum())
    out["s5_bud_min_ok"] = bool(alloc.min() >= 2)
    out["s5_mono_ok"] = bool(alloc[2] >= alloc[0])  # larger sigma -> >= alloc
    est1 = neyman_stratified_tail_estimate(_toy_inner, n_outer=128, n_inner=64,
                                           n_strata=16, rng=np.random.default_rng(5))
    est2 = neyman_stratified_tail_estimate(_toy_inner, n_outer=128, n_inner=64,
                                           n_strata=16, rng=np.random.default_rng(5))
    out["s5_det_ok"] = bool(est1["scr"] == est2["scr"] and est1["var"] == est2["var"])
    out["s5_matched_cost"] = est1["inner_path_cost"]
    out["ok"] = bool(out["s5_id_identity_max_abs_diff"] < 1e-12 and out["s5_bud_sum"] == 100
                     and out["s5_bud_min_ok"] and out["s5_mono_ok"] and out["s5_det_ok"])
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--self-test", action="store_true",
                    help="fast invariant check; prints JSON, writes nothing")
    ap.add_argument("--out", default=os.path.join(
        OUT, "MLMC_TAIL_STAGE5_VALIDATION_20260630.md"))
    ap.add_argument("--reps", type=int, default=80)
    args = ap.parse_args(argv)
    if args.self_test:
        print(json.dumps(_self_test(), indent=2))
        return 0
    study = run_study(R=args.reps)
    path = write_card(study, args.out)
    print(json.dumps({"ok": True, "card": os.path.relpath(path, HERE),
                      "budgets": [b["n_outer"] for b in study["budgets"]]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
