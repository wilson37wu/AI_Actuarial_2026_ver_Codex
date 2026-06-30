# Tail-MLMC Efficiency Map — consolidated stage-1..5 reference (W96)

_Generated 2026-06-30 (claude, AUTO W96). **Classification:** documentation-only consolidation
— no new gate, no model-form change, no contract bump, no headline re-baseline, no owner
sign-off consumed. Governed headline `39975.654628199336` and all governed artifacts are
byte-unchanged. This card collates the per-stage validation cards already in the repo into one
efficiency map; it adds **no** code and **no** new governance gate._

## Purpose

The tail-functional MLMC programme was shipped over six dated validation cards (W63→W95). This
map is the single place to read **what each stage proved, the matched-cost efficiency it
delivered, and why the governed default has not moved**. It exists because the auto-admissible
backlog's registered lead (W96) was a *non-duplicate docs/runbook refresh consolidating the
stage-1..5 tail-MLMC efficiency map* — not a new estimator, study, or gate (the governance-gate
set is saturated and stage-5-as-default is owner-gated).

## Why a tail-specific ladder exists (the linear-vs-nonlinear split)

There are two MLMC tracks in `par_model_v2/projection/mlmc_inner_estimator.py`:

- **Mean-inner track** (precursor): telescopes inner-path resolution for the **linear** mean
  conditional liability `E_X[L(X)]`. For a linear functional the inner error averages out, so
  the nested estimator is unbiased for any inner count `N`. Wired behind
  `inner_estimator='mlmc'` (default `'fixed'`); it never touches the governed SCR.
- **Tail-functional track** (this map): the governed capital figure is **nonlinear** —
  `VaR_0.995(L)`, `ES`, `SCR = VaR − E[L]`. Finite inner sampling injects an `O(1/N_inner)`
  bias that does **not** average out (Gordy-Juneja 2010) on top of the `O(1/√n_outer)` noise,
  so a quantile/ES-aware construction (Rockafellar-Uryasev representation) is a hard
  prerequisite before any MLMC figure could ever be a governed default.

The mean track answers "cheaper mean liability"; only the tail track is relevant to the
governed SCR, so stages 1-5 below are the **tail** ladder.

## The ladder at a glance

| Stage | Window / date | What shipped | Headline result | Verdict |
|---|---|---|---|---|
| 1 — Design | W63 · 2026-06-19 | Design note (no code): RU representation `ES_a = min_q[q + E[(L−q)_+]/(1−a)]`, two bias sources, gate plan | Specifies the quantile/ES-MLMC construction; names stage 5 (governed default) as owner-gated | DESIGN |
| 2 — Prototype | W64 · 2026-06-19 | `mlmc_nested_tail`, `ru_minimise_var_es`, `smoothed_cdf_var`, `nested_single_level_tail` | Telescoping identity `L=0` ≡ fixed **bit-for-bit**; RU recovers VaR 0.64% / ES 0.77% vs closed form; RU VaR == `np.quantile` to 4.7e-6 | PASS (identity + determinism) |
| 3 — Validation | W65 · 2026-06-19 | G0/G1/G2 bias + equivalence + tail-accuracy on the frozen benchmark | **CONDITIONAL** — correct & unbiased but variance-limited at 99.5% (single-run s.d. VaR 4.31% / ES 10.21% / SCR 7.34%) | CONDITIONAL → motivates stage 4 |
| 4 — Variance reduction | W66 · 2026-06-19 | Equal-probability stratified outer + ES bootstrap bias correction | Matched-cost VR **SCR 2.39× / ES 4.04× / VaR 2.19×**; ES bias −2.163% → −0.244% (stratification alone removes it) | PASS → merge-as-opt-in |
| 4b — Wiring | W67 · 2026-06-19 | `tail_capital_diagnostics(variance_reduction=…, es_bias_correction=…)`, modes `none/stratified/stratified_antithetic`, default OFF | Default `none` bit-identical to plain fixed-256; selecting `stratified` gives matched-cost **SCR 2.46× / ES 2.86× / VaR 2.62×** | PASS |
| 5 — Neyman allocation | W95 · 2026-06-30 | OFF-default study: Neyman optimal `n_h ∝ σ_h` (probability-weighted RU minimiser) vs stage-4 proportional, matched inner cost | **Lowest VaR/SCR bias** (near-unbiased SCR); SCR competitive-to-slightly-better; **loses on ES**; does **not** uniformly dominate stage 4 | PASS (OFF-default) |
| 5 — Governed default | — | (not executed) | Making any tail-MLMC figure the governed SCR default | **OWNER-GATED** — sign-off + fresh frozen reference |

## Consolidated efficiency table (matched inner-path cost)

All factors below are **matched-cost** variance-reduction (RMSE / effective-sample) speedups —
stratification and Neyman add **zero** extra inner paths. "vs plain" = vs i.i.d. nested Monte
Carlo at the same inner-path budget.

| Source (window) | Testbed | VaR | ES | **SCR** | Notes |
|---|---|---:|---:|---:|---|
| Stage 4 (W66) fixed-256 | Normal nested, n_outer=2,500, R=40 | 2.19× | 4.04× | **2.39×** | stratified outer vs plain; G3 ≥2× SCR ✓ |
| Stage 4b (W67) wiring | Normal nested, n_outer=4,000 | 2.62× | 2.86× | **2.46×** | `stratified` mode vs `none`; default bit-identical |
| Stage 5 (W95) 256×256, K=32 | Normal nested, R=80 | 2.05× | 1.46× | **1.91×** | Neyman; stage-4 here: VaR 2.07× / ES 1.58× / SCR 1.92× |
| Stage 5 (W95) 1024×256, K=128 | Normal nested, R=80 | 1.70× | 1.87× | **1.66×** | Neyman; stage-4 here: VaR 1.69× / ES 2.20× / SCR 1.59× |

### Point-estimate bias — the stage-5 differentiator

| Budget | metric | stage-4 bias | stage-5 (Neyman) bias |
|---|---|---:|---:|
| 256×256 | SCR | −0.00035 | **−0.00008** |
| 1024×256 | SCR | −0.00028 | **+0.00010** |
| 256×256 | VaR | −0.00035 | **−0.00013** |
| 1024×256 | VaR | −0.00028 | **+0.00009** |

Neyman concentrates draws in the high-variance upper-tail strata, sharpening the quantile
location → **near-unbiased SCR**. The trade is ES: stage-4's finer bulk coverage lowers the
tail-average variance more than Neyman's sharper quantile helps, so stage-4 wins on ES MSE.

## Pre-registered gate rollup

| Gate | Meaning | Status across the ladder |
|---|---|---|
| G4 — telescoping identity | `mlmc_nested_tail(L=0)` ≡ fixed single-level, bit-for-bit | PASS at every stage (2,3,4b); stage-5 weighted-RU ≡ governed `ru_minimise_var_es` bit-for-bit |
| Determinism | same seed → identical output | PASS at every stage |
| G0/G1/G2 — bias / CI / ≤1% accuracy | tail accuracy on frozen benchmark | Stage 3 CONDITIONAL (variance-limited); resolved as a **variance** problem by stage-4 VR |
| G3 — matched-cost ≥2× on SCR | variance reduction pays for itself | PASS (stage 4 2.39×, stage 4b 2.46×) |
| BC1 — ES bias reduced | bootstrap correction or stratification | PASS (stage 4: −2.16% → −0.24%) |
| G5 — no governed spillover | governed artifacts byte-unchanged | PASS at every stage (`offline_home.html` md5 `03d6538d`, `ui_data.json` md5 `70b747a0` / contract `1.23.0`, headline `39975.654628199336`) |

## Operating recommendation (current)

1. **Default outer variance reduction = stage-4 equal-probability proportional stratification.**
   Robust across budgets, best ES, ~2.4× matched-cost SCR speedup, removes the small-sample ES
   bias for free. Exposed (OFF by default) via `tail_capital_diagnostics(variance_reduction='stratified')`.
2. **Stage-5 Neyman = OFF-default low-bias SCR variant.** Keep available for SCR-point-estimate
   work where near-unbiasedness matters more than ES variance; it does not uniformly dominate
   stage 4, so it does not justify a re-baseline on its own.
3. **ES bootstrap correction** is the remedy for an *un-stratified* plain-MC outer pool only —
   **do not stack** it on stratified sampling (already ~unbiased; stacking overcorrects).
4. **Governed default unchanged.** The governed SCR stays the fixed single-level estimator.
   Making any tail-MLMC figure (stratified, Neyman, or MLMC-telescoped) the governed default is
   **stage 5 = owner-gated**: requires owner sign-off **and** a fresh frozen reference.

## Provenance — source cards (authoritative; this map summarises, does not supersede)

- Stage 1: `docs/research/MLMC_QUANTILE_ESTIMATOR_DESIGN_NOTE_20260619.md` (+ `MLMC_NESTED_LOOP_DESIGN_NOTE_20260618.md`, `MLMC_TAIL_VR_MODE_CONSUMER_NOTE_20260619.md`)
- Stage 2: `docs/validation/MLMC_TAIL_STAGE2_PROTOTYPE_20260619.{md,json}`
- Stage 3: `docs/validation/MLMC_TAIL_STAGE3_VALIDATION_20260619.{md,json}`
- Stage 4: `docs/validation/MLMC_TAIL_STAGE4_VALIDATION_20260619.{md,json}`
- Stage 4b: `docs/validation/MLMC_TAIL_STAGE4B_WIRING_20260619.{md,json}`
- Stage 5: `docs/validation/MLMC_TAIL_STAGE5_VALIDATION_20260630.md`
- Mean-inner precursor: `docs/validation/MLMC_STAGE2_PROTOTYPE_20260618.md`, `docs/validation/MLMC_STAGE3_WIRING_VALIDATION_20260619.md`

### Reproduce
```
python scripts/build_mlmc_tail_stage5_validation.py        # stage-5 Neyman card (OFF-default)
python -m pytest tests/test_mlmc_tail_stage{3,4,4b,5}.py -q # tail-track suite
python -m pytest tests/test_mlmc_tail_estimator.py -q       # estimator unit gates
```

_No governance gate is added by this document. It is a reading aid over existing, separately
gated evidence._
