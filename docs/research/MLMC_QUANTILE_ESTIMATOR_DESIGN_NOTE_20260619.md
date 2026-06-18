# Design Note — Quantile / Expected-Shortfall MLMC estimator for the governed SCR (MLMC stage-5 prerequisite)

**Window:** W63 (claude, 2026-06-19, 18:00Z window). **Status:** DESIGN-NOTE-FIRST (no
implementation this cycle). **Classification:** efficiency / estimator-only — **NOT a
model-form change**, **NO contract bump**, **NO headline re-baseline**, **NO owner
sign-off consumed**. This note is the design-note-first prerequisite for **MLMC stage 5**
named explicitly in the W60 wiring card: *"making MLMC the default for a governed quantile
figure ... requires (a) OWNER SIGN-OFF and (b) building a quantile-MLMC estimator first (the
current estimator is unbiased for the mean liability only)."* This note specifies part (b)
so the owner (or a later cycle) can move straight to a gated prototype.

It continues the discipline that produced the W57 design note -> W58 prototype -> W60 wiring
sequence: additive only, gates stay green, governed artifacts byte-unchanged, headline
`39975.654628199336` bit-identical. It advances the only remaining named auto-admissible
MLMC step with forward research rather than a verification heartbeat (W61/W62 were
verification-only because the auto-admissible queue is otherwise empty).

---

## 1. Why the shipped MLMC estimator does not yet cover the governed SCR

The shipped estimator (`par_model_v2/projection/mlmc_inner_estimator.py`, W58 prototype /
W60 wiring) telescopes the inner-path resolution for a **linear** outer functional —
`identity_payoff`, i.e. the **mean** conditional liability `E_X[L(X)]`. For a linear
functional the inner Monte-Carlo error averages out and the nested estimator is unbiased:
`E[ L_hat(x) ] = L(x)`, so `E[ mean of L_hat ] = E[L]` for any inner count `N`.

The **governed** capital figure is not a mean. In
`nested_stochastic_tvog.capital_metrics_from_liabilities` (confidence
`DEFAULT_CONFIDENCE_LEVEL = 0.995`):

```
VaR_a   = quantile_a( L )                       # np.quantile(liabilities, 0.995)
ES_a    = E[ L | L >= VaR_a ]
SCR     = VaR_a( L ) - E[ L ]                    # governed headline 39975.654628199336
```

`VaR_a` and `ES_a` are **nonlinear** functionals of the conditional-liability distribution.
For a nonlinear `g`, finite inner sampling injects a **bias** that does not average out:
with `L_hat(x) = L(x) + eps(x)`, `eps(x) ~ N(0, sigma^2(x)/N)` approximately,

```
E[ g(L_hat(x)) ] = g(L(x)) + 0.5 * g''(L(x)) * sigma^2(x)/N + o(1/N)    (Gordy-Juneja 2010)
```

so the nested VaR/ES carries an `O(1/N_inner)` inner-sampling bias on top of the usual
`O(1/sqrt(n_outer))` statistical noise. The mean-MLMC estimator removes neither the quantile
bias nor the quantile variance — it estimates the wrong functional. **A quantile/ES-aware
MLMC construction is therefore a hard prerequisite before MLMC could ever be made the
default for the governed SCR (stage 5).** Until then, `inner_estimator='mlmc'` is correctly
restricted to the *mean-liability efficiency diagnostic* and never touches the headline.

## 2. Two bias sources the quantile estimator must control

1. **Inner-sampling bias** `O(1/N_inner)` from the nonlinearity of `quantile_a` / the tail
   indicator `1{L >= q}` (Gordy-Juneja). Controlled by anchoring the **finest** MLMC level
   at the governed benchmark `N_L = 256`, so the estimand at the top level is *identical* to
   the fixed-256 nested estimator — MLMC only re-organises how the inner expectation is
   accumulated, it does not lower the finest inner count below the governed value.
2. **Smoothing bias** `O(h)` if the discontinuous tail indicator is regularised (Section 3).
   Controlled by a level-indexed bandwidth schedule `h_l -> 0` as `l -> L`, chosen so the
   smoothing bias at the finest level is dominated by the fixed-256 estimator's own MC noise.

Both are made gate-checkable by **bias gate G0** (Section 5): the combined bias at `N_L=256`
must be <= a small fraction of the fixed-256 estimator's bootstrap standard error, i.e. the
quantile-MLMC estimator must be *statistically indistinguishable* from fixed-256.

## 3. Estimator construction (literature-grounded)

The governed SCR needs `VaR_a(L)` and `ES_a(L)`. Three composable building blocks, in
increasing robustness:

**(a) ES via the Rockafellar-Uryasev (RU) representation — preferred.**
```
ES_a(L)  = min_q  [ q + 1/(1-a) * E[(L - q)_+] ]
VaR_a(L) = argmin_q  of the same objective
```
The outer functional `(L - q)_+` is **Lipschitz** (not discontinuous), so the MLMC level
differences `P_l - P_{l-1}` of the nested RU objective have well-behaved, decaying variance
under the standard theory — far friendlier than a raw indicator. VaR is recovered as the
minimiser `q*`; SCR `= VaR_a - E[L]` reuses the existing (already-MLMC-able) mean term.
This is the construction used by Giles & Haji-Ali, *Multilevel nested simulation for
efficient risk estimation* (2019) and the CVaR-MLMC line (Bujok-Hambly-Reisinger).

**(b) Smoothed-indicator telescoping (for VaR/CDF directly).** Replace `1{L >= q}` by a
sigmoid `S_h(L - q) = 1/(1+exp(-(L-q)/h))` with bandwidth `h_l` shrinking up the ladder. The
nested CDF estimate `F_hat(q)` is telescoped over inner-path resolution; VaR is obtained by
inverting `F_hat` at `a`. The smoothing gives finite variance of the level differences; the
`h_l -> 0` schedule controls the `O(h)` bias (gate G0). Used as a cross-check on (a).

**(c) Antithetic fine/coarse inner coupling** — reuse the W58 mechanism
(`mlmc_nested`, geometric ladder `N_l = N_0*M^l`, antithetic coupling of the fine estimator
with its coarse half). Coupling the *same* tail functional evaluated at fine vs coarse inner
counts is what makes `Var(P_l - P_{l-1})` decay; this is the lever that turns the Lipschitz
RU objective into a `>=2x` cost cut.

**Recommended path:** implement **(a) RU-ES** as the primary estimator (Lipschitz objective,
cleanest MLMC variance decay, yields both VaR and ES), with **(b)** as an independent
validation oracle, and **(c)** as the variance-reduction coupling shared with the mean
prototype.

## 4. Integration points (no model-form change)

- Extend the opt-in path only: `mlmc_inner_estimator` gains a **tail functional** estimator
  (`mlmc_nested_tail(...)` returning `{VaR, ES, SCR}` plus per-level diagnostics) alongside
  the existing mean estimator. `nested_stochastic_tvog` keeps `inner_estimator="fixed"` as
  the **default**; the governed SCR/VaR/ES continue to come from the fixed single-level
  path and stay **byte-identical**.
- Seeds: reuse the slice-stable CRN protocol (`SeedSequence(seed).spawn(...)`), disjoint
  sub-streams per level, coarse-reuses-first-`N_{l-1}` antithetic coupling — same protocol
  proven bit-reproducible for the mean estimator (so staged == monolithic holds).
- The outer VR pool (Sobol-RQMC / stratified / RQMC+CV) is orthogonal and untouched.
- Pure `numpy` at import time (scipy only inside optionally-skipped tests), deterministic,
  no I/O, no global state — matching the existing module's discipline.

## 5. Pre-registered gates (defined BEFORE any implementation)

| Gate | Definition | Pass bar |
|---|---|---|
| **G0 bias (NEW)** | combined inner-sampling + smoothing bias of quantile-MLMC at `N_L=256` vs fixed-256 | <= **10%** of the fixed-256 bootstrap SE on each of VaR/ES/SCR (estimator statistically indistinguishable from fixed-256) |
| **G1 equivalence** | quantile-MLMC SCR vs fixed-256 SCR on the frozen snapshot; headline while default=`fixed` | within fixed-256 bootstrap 95% CI **AND** `39975.654628199336` **bit-identical** |
| **G2 tail accuracy** | 99.5% VaR, ES, SCR relative error vs fixed-256 benchmark | <= **1%** each |
| **G3 cost** | matched-RMSE inner-path cost vs fixed-256 at `N_L=256`; level variances `V_l` decay | net cost cut >= **2x** at equal-or-better SCR CI width, else **shelve** |
| **G4 reproducibility** | staged == monolithic, bit-identical under the seed protocol; `pytest`/`node` clean | exact |
| **G5 no-spillover** | governed artifacts (`ui_data.json`, `ui_app.html`, `combined_model_app.html`, `model_summary_card.html`, `model_result_viewer.html`, `offline_home.html`) byte-unchanged; contract `1.23.0` | exact |

Decision rule: fail **G0/G1/G2** -> reject outright (correctness — a biased quantile is worse
than a slow one). Pass G0-G2 but fail **G3** -> **shelve** (correct but not worth the
complexity; record, do not merge). G3 is the only gate whose failure is a "no value" shelve
rather than a correctness reject.

## 6. Staged plan (each stage = one future gated cycle)

1. **(this note)** Quantile/ES estimator design + pre-registered gates incl. the new bias
   gate G0. [DONE]
2. Prototype `mlmc_nested_tail` (RU-ES primary + smoothed-indicator oracle) behind the
   opt-in flag; unit-test the **telescoping identity** (top-level-only path == fixed-256
   VaR/ES bit-for-bit) and the RU minimiser recovering VaR. **[DONE — W64, 2026-06-19;
   evidence `docs/validation/MLMC_TAIL_STAGE2_PROTOTYPE_20260619.md`, 10+1s tail tests,
   identity bit-for-bit, RU recovery 0.64%/0.77% vs Normal truth.]**
3. Bias + equivalence + tail-accuracy validation (G0-G2) on the frozen snapshot; produce a
   validation card analogous to `MLMC_STAGE3_WIRING_VALIDATION_20260619.md`.
4. Cost / variance-decay study (G3) at `N_L=256`; decide merge-as-opt-in vs shelve.
5. **(owner sign-off ONLY)** consider making quantile-MLMC the default for the governed
   SCR — re-baseline + fresh frozen reference. Out of scope here.

## 7. Rollback / safety

Quantile-MLMC ships **opt-in with `"fixed"` as default**, so every stage up to 4 is a pure
no-op for the governed headline and all governed artifacts; rollback is "delete the optional
tail-functional branch." No model parameter, copula, correlation, or aggregation choice is
touched at any stage. No owner sign-off is consumed until stage 5, which stays out of scope.

## 8. Owner ask (one line)

If you want the inner-loop runtime headroom to eventually apply to the **governed SCR** (not
just the mean-liability diagnostic), approve proceeding to **stage 2** (prototype the
quantile/ES MLMC estimator behind the opt-in flag); otherwise this note de-risks stage 5 and
the next cycle returns to a single verification pass + the decision brief.

---

### Sources (consulted)
- M. B. Giles & A.-L. Haji-Ali, *Multilevel nested simulation for efficient risk estimation*,
  SIAM/ASA J. Uncertainty Quantification 7(2), 2019: https://epubs.siam.org/doi/10.1137/18M1173186
- K. Bujok, B. M. Hambly, C. Reisinger, *Multilevel simulation of functionals of Bernoulli
  random variables with application to basket credit derivatives*, Methodol. Comput. Appl.
  Probab., 2015.
- M. B. Gordy & S. Juneja, *Nested simulation in portfolio risk measurement*, Management
  Science 56(10), 2010 (the `O(1/N_inner)` inner-bias result): https://doi.org/10.1287/mnsc.1100.1213
- R. T. Rockafellar & S. Uryasev, *Optimization of Conditional Value-at-Risk*, J. of Risk
  2(3), 2000 (the ES = min_q [...] representation used in Section 3a).
- Optimized Multi-Level Monte Carlo Parametrization and Antithetic Sampling for Nested
  Simulations (arXiv 2510.18995, 2025): https://arxiv.org/pdf/2510.18995
- Repo precedent: mean-liability MLMC prototype `par_model_v2/projection/mlmc_inner_estimator.py`
  (W58) and its wiring `MLMC_STAGE3_WIRING_VALIDATION_20260619.md` (W60); governed nested
  estimator `par_model_v2/projection/nested_stochastic_tvog.py`
  (`capital_metrics_from_liabilities`, `DEFAULT_CONFIDENCE_LEVEL = 0.995`); prior MLMC design
  note `docs/research/MLMC_NESTED_LOOP_DESIGN_NOTE_20260618.md`.
