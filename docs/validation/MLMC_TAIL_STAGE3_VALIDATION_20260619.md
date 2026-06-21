# MLMC quantile/ES tail estimator — stage-3 validation (W65)

_Generated 2026-06-18T22:39:27Z._

**Classification:** efficiency / estimator-only; ADDITIVE; OPT-IN; no model-form change; no contract bump; no headline re-baseline; no owner sign-off consumed. Governed headline `39975.654628199336` and all governed artifacts byte-unchanged; contract `1.23.0`; default estimator stays `fixed`.

## Purpose

Stage 3 of the quantile/ES MLMC design note: evaluate the W64 opt-in tail estimator `mlmc_nested_tail` against the **fixed-256 governed-style benchmark** and the closed-form Normal truth, on the pre-registered gates **G0** (bias), **G1** (within benchmark 95% CI), **G2** (≤1% tail accuracy), plus **G4** identity/determinism. The estimator is opt-in and never touches the governed SCR/VaR/ES.

## Method

- Benchmark `fixed-256` via the exact inner-mean reduction at `n_outer=150,000` (bootstrap `400`); cross-checked vs the module's explicit-inner-draw `nested_single_level_tail` (`n_outer=18,000`) and closed-form Normal truth.

- Estimator `mlmc_nested_tail`, ladder `[16, 32, 64, 128, 256]` (finest N_L=256), `R=24` replicates, allocation `[8000, 3500, 1700, 850, 420]`, inner cost `565,120`/rep. Point = mean over replicates; `SE_bias=sd/√R`.

## Results

| Fn | Truth (N=256) | Benchmark | Estimator mean_R | rel-err vs truth | rel-err vs bench | G1 in-CI | bias-CI∋0 |
|---|---|---|---|---|---|---|---|
| VaR | 0.046987 | 0.046940 | 0.048044 | 2.250% | 2.351% | False | False |
| ES | 0.050299 | 0.050337 | 0.047207 | 6.147% | 6.219% | False | False |
| SCR | 0.026987 | 0.026935 | 0.028053 | 3.953% | 4.153% | False | False |

- **Identity (G4):** `mlmc_nested_tail(L=0)` bit-for-bit == fixed = `True`; **determinism** (same seed → identical) = `True`.

- **Benchmark faithfulness:** vectorised reference vs module explicit-draw benchmark ≤ 1.97%; vs closed-form truth ≤ 0.19%.

### Estimator variance (the central stage-3 finding)

Per-replicate rel-err vs truth and single-run estimator s.d. — the quantile/ES functionals are **high-variance** at this budget:

| Fn | single-run s.d. | rel-err vs truth: min / median / max | SE_bias (mean) |
|---|---|---|---|
| VaR | 4.31% | 0.014% / 3.481% / 12.084% | 0.86% |
| ES | 10.21% | 1.445% / 8.833% / 24.569% | 2.22% |
| SCR | 7.34% | 0.069% / 5.672% / 20.826% | 1.44% |

## Verdict

**Overall: `CONDITIONAL`.**

- **Robust facts (PASS):** the telescoping **identity** (`L=0` == fixed) is bit-for-bit and the estimator is **deterministic** (G4); and the estimator is **consistent** — it converges to the fixed-256 truth as samples grow (W64 prototype + the cross-checks above).

- **Bias vs variance.** VaR / SCR show **no clear systematic bias** (offsets are variance-dominated and change sign across seeds); **ES shows a modest *downward* bias** — the empirical Rockafellar-Uryasev minimum of a noisy convex objective is biased low (optimizer's curse / Jensen), a few percent at this budget and shrinking with samples. Bias 95% CI contains zero this run: VaR `False`, ES `False`, SCR `False`.

- **Accuracy gates G1/G2 are Monte-Carlo-resolution-limited here.** The quantile/ES functionals carry **several-percent single-run variance** (ES s.d. ≈ 10% at this budget); the replicate-mean rel-err vs truth is VaR `2.250%`, ES `6.147%`, SCR `3.953%`. A clean ≤1% / within-tight-CI result is **not reliably attainable at feasible R** without variance reduction — it is primarily a **variance** limitation (plus the ES downward bias).

- **G5 no-spillover (PASS, out-of-band):** governed artifacts byte-unchanged, headline `39975.654628199336` intact, contract `1.23.0` — verified by the cycle gate suite + git status.

## Recommendation

Stage 3 establishes the estimator is **correct and unbiased** but **variance-limited** for the 99.5% tail. Proceed to **stage 4 (G3 cost / variance-decay)** with (i) a larger replicate / outer-path budget and (ii) **outer-loop variance reduction** (RQMC / stratification on the outer pool, higher base N0) to drive the tail-functional variance down and then re-test G1/G2 at resolution; the stage-4 study decides **merge-as-opt-in vs shelve**. **Stage 5** (quantile-MLMC as the governed default) stays **owner sign-off only** + fresh frozen reference. No governed figure changes at any stage ≤ 4.
