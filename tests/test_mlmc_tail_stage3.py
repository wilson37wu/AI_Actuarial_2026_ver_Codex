"""Stage-3 (W65) regression guards for the quantile/ES tail-functional MLMC estimator.

Fast, **seed-stable** assertions only. The precise statistical gates (G0/G1/G2, the
benchmark bootstrap CIs and the estimator-variance characterisation) live in
``scripts/build_mlmc_tail_stage3_validation.py`` -> ``docs/validation/
MLMC_TAIL_STAGE3_VALIDATION_20260619.md``; the W65 finding is that the tail
functionals are *unbiased but high-variance* at feasible budgets, so accuracy is
Monte-Carlo-resolution-limited and is deliberately NOT asserted at a tight tolerance
here (that would flake). These tests guard the robust facts the card relies on:

* **G4 telescoping identity** -- ``mlmc_nested_tail(L=0)`` bit-for-bit == fixed at N_L=256;
* **determinism** -- same seed -> identical;
* **structural invariants** -- ES >= VaR (CVaR dominates VaR), SCR == VaR - E[L],
  ladder / finest-inner / inner-path-cost accounting;
* **consistency** -- the replicate-mean VaR/ES/SCR sit within a GENEROUS Monte-Carlo
  band of the fixed-256 benchmark (guards gross regressions without flaking);
* **mean liability** (the linear, low-variance term) recovers the benchmark tightly.

The estimator is opt-in; nothing here touches the governed SCR/VaR/ES headline.
"""
import numpy as np
import pytest

from par_model_v2.projection.mlmc_inner_estimator import (
    mlmc_nested_tail,
    nested_single_level_tail,
    DEFAULT_TAIL_CONFIDENCE,
)

M_X, S_X, SIGMA_INNER = 0.02, 0.01, 0.05
ALPHA = DEFAULT_TAIL_CONFIDENCE


def outer_sampler(rng, n):
    return rng.normal(M_X, S_X, size=n)


def inner_sampler(x, n_inner, rng):
    return rng.normal(x, SIGMA_INNER, size=n_inner)


def _mean_reps(R, n0, alloc, seed):
    v = np.empty(R); e = np.empty(R); s = np.empty(R); ml = np.empty(R)
    for r in range(R):
        est = mlmc_nested_tail(
            outer_sampler, inner_sampler, alpha=ALPHA, n0=n0, M=2,
            L=len(alloc) - 1, n_outer_per_level=alloc,
            rng=np.random.default_rng(seed + r))
        v[r], e[r], s[r], ml[r] = est.var, est.es, est.scr, est.mean_liability
    return v.mean(), e.mean(), s.mean(), ml.mean()


def test_identity_L0_bit_for_bit_at_256():
    sl = nested_single_level_tail(
        outer_sampler, inner_sampler, alpha=ALPHA, n_outer=3000,
        n_inner=256, rng=np.random.default_rng(99))
    ml = mlmc_nested_tail(
        outer_sampler, inner_sampler, alpha=ALPHA, n0=256, M=2, L=0,
        n_outer_per_level=3000, rng=np.random.default_rng(99))
    assert ml.var == sl.var and ml.es == sl.es and ml.scr == sl.scr
    assert ml.n_inner == 256 and ml.ladder == [256]


def test_determinism_same_seed_identical():
    kw = dict(alpha=ALPHA, n0=16, M=2, L=4,
              n_outer_per_level=[3000, 1500, 800, 400, 200])
    a = mlmc_nested_tail(outer_sampler, inner_sampler,
                         rng=np.random.default_rng(13), **kw)
    b = mlmc_nested_tail(outer_sampler, inner_sampler,
                         rng=np.random.default_rng(13), **kw)
    assert a.var == b.var and a.es == b.es and a.scr == b.scr
    assert a.mean_liability == b.mean_liability


def test_structural_invariants():
    est = mlmc_nested_tail(
        outer_sampler, inner_sampler, alpha=ALPHA, n0=16, M=2, L=4,
        n_outer_per_level=[4000, 2000, 1000, 500, 250],
        rng=np.random.default_rng(321))
    assert est.es >= est.var               # CVaR dominates VaR
    assert est.var > 0 and est.es > 0
    assert est.scr == pytest.approx(est.var - est.mean_liability)
    assert est.ladder == [16, 32, 64, 128, 256] and est.n_inner == 256
    # antithetic cost accounting: sum_l n_outer_l * N_fine_l
    assert est.inner_path_cost == 4000*16 + 2000*32 + 1000*64 + 500*128 + 250*256


def test_consistency_generous_band_vs_fixed256():
    # Fixed-256 governed-style benchmark; generous band (high-variance tail -> NOT tight).
    bench = nested_single_level_tail(
        outer_sampler, inner_sampler, alpha=ALPHA, n_outer=15000,
        n_inner=256, rng=np.random.default_rng(2024))
    v, e, s, ml = _mean_reps(R=8, n0=16, alloc=[6000, 2600, 1300, 650, 320], seed=4000)
    # Generous 15% band guards gross regressions without flaking on MC noise.
    assert abs(v - bench.var) / bench.var < 0.15
    assert abs(e - bench.es) / bench.es < 0.15
    assert abs(s - bench.scr) / bench.scr < 0.15
    # The LINEAR mean-liability term is low-variance and recovers the benchmark tightly.
    assert abs(ml - bench.mean_liability) / abs(bench.mean_liability) < 0.03
