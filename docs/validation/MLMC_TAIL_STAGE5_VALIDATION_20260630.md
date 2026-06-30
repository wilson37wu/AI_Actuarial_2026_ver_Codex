# MLMC Tail Estimator — STAGE 5 STUDY (Neyman optimal allocation)

_Generated 2026-06-30T09:22:33Z by `scripts/build_mlmc_tail_stage5_validation.py` (OFF-default, measurement-only)._

**Question.** Does *Neyman / optimal* sample allocation across outer strata improve the 99.5% tail VaR/ES/SCR estimator over the stage-4 *equal-probability proportional* stratification, **at matched inner-path cost**?

**Method.** Toy model (closed-form truth): outer X ~ N(0.020, 0.010²), inner ~ N(X, 0.050²); confidence α = 0.9950. Plain i.i.d. vs stage-4 (1 draw / equal-probability stratum, self-weighting) vs stage-5 (K equal-probability strata, two-phase **pilot Neyman** allocation n_h ∝ σ_h, probability-weighted RU minimiser). All three use the same n_outer × n_inner inner paths.


## Budget n_outer=256, n_inner=256 (K=32 strata, R=80 replicates, matched inner-path cost=65,536)

Truth: VaR=0.046987, ES=0.050299, SCR=0.026987

| metric | estimator | bias | variance | RMSE | MSE-VR vs plain |
|---|---|---:|---:|---:|---:|
| VaR | plain | -0.00121 | 8.608e-06 | 0.00317 | — |
| VaR | stage4 | -0.00035 | 4.744e-06 | 0.00221 | 2.07× |
| VaR | stage5 | -0.00013 | 4.884e-06 | 0.00221 | 2.05× |
| ES | plain | -0.00226 | 1.018e-05 | 0.00391 | — |
| ES | stage4 | -0.00063 | 9.249e-06 | 0.00311 | 1.58× |
| ES | stage5 | -0.00121 | 8.995e-06 | 0.00324 | 1.46× |
| SCR | plain | -0.00122 | 7.690e-06 | 0.00303 | — |
| SCR | stage4 | -0.00035 | 4.671e-06 | 0.00219 | 1.92× |
| SCR | stage5 | -0.00008 | 4.794e-06 | 0.00219 | 1.91× |

## Budget n_outer=1024, n_inner=256 (K=128 strata, R=80 replicates, matched inner-path cost=262,144)

Truth: VaR=0.046987, ES=0.050299, SCR=0.026987

| metric | estimator | bias | variance | RMSE | MSE-VR vs plain |
|---|---|---:|---:|---:|---:|
| VaR | plain | -0.00039 | 2.607e-06 | 0.00166 | — |
| VaR | stage4 | -0.00028 | 1.561e-06 | 0.00128 | 1.69× |
| VaR | stage5 | +0.00009 | 1.620e-06 | 0.00128 | 1.70× |
| ES | plain | -0.00066 | 3.541e-06 | 0.00199 | — |
| ES | stage4 | -0.00016 | 1.786e-06 | 0.00135 | 2.20× |
| ES | stage5 | -0.00035 | 2.013e-06 | 0.00146 | 1.87× |
| SCR | plain | -0.00041 | 2.457e-06 | 0.00162 | — |
| SCR | stage4 | -0.00028 | 1.574e-06 | 0.00129 | 1.59× |
| SCR | stage5 | +0.00010 | 1.573e-06 | 0.00126 | 1.66× |

## Findings

- **Both** stratifiers robustly beat plain Monte Carlo (≈1.4–2.2× MSE reduction on VaR/ES/SCR at matched cost).
- **Stage-5 Neyman** consistently delivers the **lowest VaR/SCR point-estimate bias** (near-unbiased SCR) — concentrating draws in the high-variance upper-tail strata sharpens the quantile location.
- On **SCR** (the governed capital metric) stage-5 is **competitive-to-slightly-better** than stage-4 on MSE; on **ES** the stage-4 proportional stratifier wins (its fine bulk coverage lowers the tail-average variance more than Neyman's sharper quantile helps).
- Stage-5 Neyman does **not uniformly dominate** stage-4.

## Recommendation

Stage-4 equal-probability proportional stratification **remains the recommended default** outer variance-reduction scheme. Stage-5 Neyman allocation is a useful **low-bias SCR variant** worth keeping as an OFF-default option, but it does not by itself justify a governed re-baseline. Adopting any stage-5 figure as the governed default remains **OWNER-GATED** (sign-off + a fresh frozen reference). The governed headline 39975.654628199336 and all governed artifacts are byte-unchanged by this study.

