# Latest Cycle Status — W95 (claude, AUTO)

**Timestamp:** 2026-06-30T09:26:00Z
**Cycle ID:** 2026-06-30T09:10Z-3bb3
**Owner:** claude (Cowork `auto_actuarial_stochastic_model`)
**Verdict:** ✅ PASS — `origin/main` delta = **3 ADDITIVE files** (stage-5 script + test + validation card) + state/log/this cycle-status record; no model-FORM, governed-artifact, contract, or headline change.

## One-line conclusion
Executed the long-registered W95 LEAD: shipped an **OFF-default MLMC stage-5 STUDY** (Neyman / optimal outer-stratum sample **allocation** vs the stage-4 **proportional** stratifier) as **three additive files**, measurement-only with the governed headline byte-identical, ran the **full verification battery (all GREEN, MLMC now 66/66)**, and did a **full tracked-file mount sync**. The study **closes** the stage-5 allocation question: stage-4 proportional stratification remains the recommended default; stage-5 Neyman is a useful OFF-default low-bias SCR variant that does not uniformly dominate it.

## What this cycle did (exactly one task)
The single `in_progress` item, **Phase 38 Task 3** (fold Cash Flows + Products + the Phase 37 Scenario Explorer into byte-pinned `ui_app.html` as native tabs), stays **OWNER-GATED** (sha256 re-baseline across the gate scripts + a `ui_data.json` contract bump) and is **not** executed here. W94 registered W95 with the LEAD = an OFF-default MLMC stage-5 efficiency study; this cycle worked it and shipped it:

- **`scripts/build_mlmc_tail_stage5_validation.py`** (OFF-default, `--self-test`) — adds three importable, well-tested primitives without touching `par_model_v2/projection/mlmc_inner_estimator.py`:
  - `weighted_ru_minimise_var_es(L, w, α)` — a **strict generalisation** of the governed `ru_minimise_var_es`; with uniform weights `1/n` it reproduces it **bit-for-bit** (max abs diff `0.0` / ≤ 4.4e-16 over random samples — the S5-ID anchor).
  - `neyman_allocation(σ, n_total, n_min)` — integer **budget-conserving** optimal allocation across equal-probability strata (`Σ n_h == n_total`, every `n_h ≥ n_min`).
  - `neyman_stratified_tail_estimate(...)` — two-phase **pilot** Neyman estimate at **matched inner-path cost** (`Σ n_h == n_outer`).
- **`tests/test_mlmc_tail_stage5.py`** — **13/13** seed-stable guards (identity, budget conservation, monotonicity, determinism, matched-cost, variance-reduction-vs-plain, near-unbiased SCR, self-test parity).
- **`docs/validation/MLMC_TAIL_STAGE5_VALIDATION_20260630.md`** — the generated 2-budget bias/variance/RMSE card.

## Finding (measurement-only; matched inner-path cost)
- Both stratifiers beat plain Monte Carlo by **≈1.4–2.2× MSE** on VaR/ES/SCR.
- **Stage-5 Neyman gives the lowest VaR/SCR point-estimate bias** (near-unbiased SCR: `+0.00010` at n_outer=1024 vs stage-4 `−0.00028`) — concentrating draws in the high-variance upper-tail strata sharpens the quantile location.
- On **SCR** (the governed capital metric) stage-5 is **competitive-to-slightly-better** than stage-4 on MSE (1.66× vs 1.59× at n_outer=1024); on **ES** stage-4 proportional wins.
- Stage-5 Neyman does **not uniformly dominate** stage-4 ⇒ **stage-4 proportional stratification remains the recommended default**; stage-5-as-default stays **OWNER-GATED**. Question **closed** with data.

## Verification gates — all GREEN
- **Gate C** — `launch_offline_gui.py --self-test`: `self_test_ok:true`, `engine_ready:true`. `run_model.py --n-outer 100 --n-inner 4 --no-tail --seed 42` bit-match: **nested 49657.9 / gaussian 37499.0 / var-covar 30267.9**.
- **Gate D** — `actuarial_gui.spec` AST-parses; `release.workflow.yml` valid YAML; `offline_bootstrap.py --self-test` **7/7** `ok`; `build_phase_pkg_task1_validate.py` **26/26** (incl. `ui_app_byte_unchanged`, `governed_headline_present`).
- **Integrity** — `build_offline_home_validate.py` **177/177** (failed:[]); pytest `test_offline_home_validate.py` **4 passed**; `offline_home_loader_parity.cjs` (node) **10/10**; `ui_app_selftest_nojsdom.cjs` (node) **40/40**; `ui_data_section_digest_recompute_parity.cjs` (node) **22/22**; **MLMC suite 66/66** (inner+wiring 16 · tail_estimator+stage3 15 · stage4+stage4b 22 · **+13 stage-5**).
- **Governed bytes byte-UNCHANGED** — `offline_home.html` md5 `03d6538d3cae9efb83062ecbfab096e9`; `ui_data.json` md5 `70b747a05c00d29bd6e286a7ee4cf42c` / contract `1.23.0` / `root_digest 456f7721…`; `ui_app.html` sha256 `d82c65ec…`; headline `39975.654628199336`. The Gate-C smoke re-wrote `docs/validation/RUN_MODEL_*.json` in the clone → **reverted** via `git checkout`, not committed.

## Engine lock
numpy 1.26.4 / scipy 1.13.1 / pandas 2.2.3 (`requirements-engine-lock.txt`) in a pre-existing pinned `/tmp` venv.

## Coordination
Fresh throwaway clone of `origin/main` (`/tmp/cc_20260630_090759`); mount `.git` untouched. Preflight **PROCEED** (owner null, prior release 08:20:14Z); lock `2026-06-30T09:10Z-3bb3` acquired. Mount synced to `origin/main` post-push; lock released.

## Researched next improvement (registered W96, behind the same hard near-duplicate guard)
With the stage-5 allocation question **closed** and the governance-gate surface **saturated**, W96 LEAD = a **non-duplicate docs/runbook refresh consolidating the stage-1..5 tail-MLMC efficiency map** (no new gate), ELSE the SKILL's sanctioned exhausted-backlog **verification + full mount-sync pass**. A "stage-6" estimator would be over-engineering and is **not** registered. No model-FORM/contract/headline change (owner-gated); Phase 38 Task 3 owner-gated; MLMC-default stage 5 owner-gated.
