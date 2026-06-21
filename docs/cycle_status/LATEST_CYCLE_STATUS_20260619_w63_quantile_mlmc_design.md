# Cycle Status — W63 (claude, 2026-06-19, 18:00Z)

**Type:** Forward-research, design-note-first (NOT a verification-only heartbeat).
**Task:** MLMC stage-5 prerequisite (b) — quantile/ES-aware MLMC estimator design.
**Classification:** efficiency / estimator-only; design-only; **no** model-form change, **no**
contract bump, **no** headline re-baseline, **no** owner sign-off consumed.

## What shipped
`docs/research/MLMC_QUANTILE_ESTIMATOR_DESIGN_NOTE_20260619.md` — specifies the estimator
the W60 wiring card named as the remaining gap before MLMC could be made the governed
default:
- The shipped MLMC estimator (`identity_payoff`) is unbiased only for the **mean** liability
  `E[L]`. The governed SCR is `VaR_0.995(L) - E[L]` (with `ES = E[L|L>=VaR]`), a **nonlinear**
  tail functional carrying an `O(1/N_inner)` Gordy-Juneja inner-sampling bias the mean
  estimator cannot remove.
- Prescribes the **Rockafellar-Uryasev ES representation** (Lipschitz `(L-q)_+` objective,
  clean MLMC variance decay, recovers both VaR and ES) as the primary estimator; a
  **smoothed-indicator CDF telescoping** as an independent oracle; **antithetic fine/coarse
  coupling** reused from the W58 mean prototype.
- Pre-registers a **new bias gate G0** (combined inner+smoothing bias at `N_L=256` <= 10% of
  the fixed-256 bootstrap SE) on top of G1 equivalence / G2 <=1% tail / G3 >=2x cost /
  G4 reproducibility / G5 no-spillover.

## Verification (green + byte-stable)
- `build_offline_home_validate` **177/177** ok:true
- `offline_home_loader_parity` **10/10**
- `tests/test_offline_home_validate` **4/4** (stdlib unittest)
- `tests/test_mlmc_inner_estimator` + `tests/test_mlmc_stage3_wiring` **15 passed + 1 scipy-skip**
- `offline_home.html` md5 `03d6538d3cae9efb83062ecbfab096e9` (byte-identical W52-W63)
- governed artifacts byte-unchanged; headline **39,975.65** (1 occ); contract **1.23.0**

## Git / ops
- All git in a fresh `/tmp` ext4 clone of `origin/main`; mount `.git` untouched.
- The `/sessions` mount is **100% full + delete-forbidden** -> the Windows Downloads mirror
  is stale at W59; **origin/main is the source of truth**.
- Lock acquired + released this cycle.

## Next
**W64 = MLMC stage-2 QUANTILE prototype** (`mlmc_nested_tail` behind the opt-in flag;
auto-runnable, no headline re-baseline) — unit-test the telescoping identity (top-level ==
fixed-256 VaR/ES bit-for-bit) and the RU minimiser recovering VaR. OR owner pivot: A MR-LONGEV-1
[sign-off] / B LSMC [sign-off] / C Phase IGUI [auto] / D Packaging [auto] / E FREEZE.
