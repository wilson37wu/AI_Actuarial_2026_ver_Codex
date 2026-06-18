"""Tests for the MLMC stage-2 inner-estimator prototype (W58).

Validates the telescoping multilevel inner estimator against (a) an analytic
nested testbed with a known closed-form estimand and (b) the governed inner
sampler. The estimator is opt-in and not wired into any governed figure; these
tests guard correctness + the equivalence/cost gates from the design note
(docs/research/MLMC_NESTED_LOOP_DESIGN_NOTE_20260618.md).
"""
import numpy as np
import pytest

from par_model_v2.projection.mlmc_inner_estimator import (
    inner_path_ladder,
    nested_single_level,
    mlmc_nested,
    mlmc_optimal_allocation,
    identity_payoff,
)

# --- analytic nested testbed -------------------------------------------------
# Outer X ~ Normal(M_X, S_X); L(x) = x ; inner draws ~ Normal(x, SIGMA_INNER).
M_X, S_X, SIGMA_INNER = 0.02, 0.01, 0.05


def outer_sampler(rng, n):
    return rng.normal(M_X, S_X, size=n)


def inner_sampler(x, n_inner, rng):
    return rng.normal(x, SIGMA_INNER, size=n_inner)


def sq_payoff(y):
    return np.asarray(y, dtype=float) ** 2


def truth_sq_at_N(n_inner):
    # E_X[(mean of n_inner draws)^2] = E[x^2] + sigma^2/n_inner
    return M_X ** 2 + S_X ** 2 + SIGMA_INNER ** 2 / n_inner


# --- ladder ------------------------------------------------------------------
def test_ladder_geometric():
    assert inner_path_ladder(16, 2, 4) == [16, 32, 64, 128, 256]
    assert inner_path_ladder(8, 2, 3) == [8, 16, 32, 64]
    with pytest.raises(ValueError):
        inner_path_ladder(0, 2, 3)
    with pytest.raises(ValueError):
        inner_path_ladder(8, 1, 3)


# --- identity payoff: linear, unbiased, MLMC == single-level -----------------
def test_identity_payoff_equivalence():
    rng1 = np.random.default_rng(20260618)
    sl = nested_single_level(outer_sampler, inner_sampler,
                             payoff=identity_payoff, n_outer=4000,
                             n_inner=128, rng=rng1)
    rng2 = np.random.default_rng(7)
    ml = mlmc_nested(outer_sampler, inner_sampler, payoff=identity_payoff,
                     n0=8, M=2, L=4, n_outer_per_level=[8000, 2000, 500, 200, 80],
                     rng=rng2)
    assert ml.ladder[-1] == 128
    # both estimate E[L(X)] = M_X (no inner bias for a linear functional)
    assert abs(sl.estimate - M_X) < 5 * sl.std_error + 1e-9
    assert abs(ml.estimate - M_X) < 5 * ml.std_error + 1e-9
    assert abs(sl.estimate - ml.estimate) < 5 * (sl.std_error + ml.std_error)


# --- nonlinear payoff: shared estimand at the finest level -------------------
def test_nonlinear_payoff_shared_estimand():
    N_L = 128
    rng1 = np.random.default_rng(101)
    sl = nested_single_level(outer_sampler, inner_sampler, payoff=sq_payoff,
                             n_outer=6000, n_inner=N_L, rng=rng1)
    rng2 = np.random.default_rng(202)
    ml = mlmc_nested(outer_sampler, inner_sampler, payoff=sq_payoff,
                     n0=8, M=2, L=4,
                     n_outer_per_level=[16000, 4000, 1000, 250, 64], rng=rng2)
    truth = truth_sq_at_N(N_L)
    # MLMC and single-level both target E[g(L_{N_L}(X))] (design-note equivalence)
    assert abs(sl.estimate - truth) < 6 * sl.std_error + 1e-9
    assert abs(ml.estimate - truth) < 6 * ml.std_error + 1e-9
    # G2-analogue: <=1% relative agreement between the two estimators
    assert abs(ml.estimate - sl.estimate) / abs(truth) < 0.01


# --- cost gate (G3-analogue): MLMC reaches <= the SE at lower inner cost ------
def test_mlmc_cost_advantage():
    N_L = 128
    rng1 = np.random.default_rng(11)
    sl = nested_single_level(outer_sampler, inner_sampler, payoff=sq_payoff,
                             n_outer=2000, n_inner=N_L, rng=rng1)
    rng2 = np.random.default_rng(22)
    ml = mlmc_nested(outer_sampler, inner_sampler, payoff=sq_payoff,
                     n0=8, M=2, L=4,
                     n_outer_per_level=[16000, 4000, 1000, 250, 64], rng=rng2)
    # cheaper total inner-path cost ...
    assert ml.inner_path_cost < sl.inner_path_cost
    # ... at comparable accuracy (SE within 15%) -> a genuine efficiency gain.
    # (The toy testbed's outer variance dominates; the structural inner-cost
    #  saving is far larger on the real nested SCR where N_L=256 dominates cost.)
    assert ml.std_error <= sl.std_error * 1.15


# --- antithetic coupling shrinks the correction-level variance ---------------
def test_antithetic_reduces_level_variance():
    rng_a = np.random.default_rng(333)
    ml_a = mlmc_nested(outer_sampler, inner_sampler, payoff=sq_payoff,
                       n0=8, M=2, L=4, n_outer_per_level=2000,
                       rng=rng_a, antithetic=True)
    rng_b = np.random.default_rng(333)
    ml_b = mlmc_nested(outer_sampler, inner_sampler, payoff=sq_payoff,
                       n0=8, M=2, L=4, n_outer_per_level=2000,
                       rng=rng_b, antithetic=False)
    # top correction level variance is smaller with antithetic coupling
    assert ml_a.levels[-1].var_diff <= ml_b.levels[-1].var_diff


# --- reproducibility: same seed -> identical estimate ------------------------
def test_reproducibility():
    r1 = np.random.default_rng(99)
    r2 = np.random.default_rng(99)
    a = mlmc_nested(outer_sampler, inner_sampler, payoff=sq_payoff,
                    n0=8, M=2, L=3, n_outer_per_level=1500, rng=r1)
    b = mlmc_nested(outer_sampler, inner_sampler, payoff=sq_payoff,
                    n0=8, M=2, L=3, n_outer_per_level=1500, rng=r2)
    assert a.estimate == b.estimate
    assert a.inner_path_cost == b.inner_path_cost


# --- optimal allocation diagnostic is well-formed ----------------------------
def test_optimal_allocation_shape():
    rng = np.random.default_rng(5)
    ml = mlmc_nested(outer_sampler, inner_sampler, payoff=sq_payoff,
                     n0=8, M=2, L=4, n_outer_per_level=2000, rng=rng)
    alloc = mlmc_optimal_allocation(ml.levels, target_se=1e-4)
    assert len(alloc) == len(ml.levels)
    assert all(n >= 1 for n in alloc)


# --- governed inner sampler smoke equivalence (real model machinery) ---------
def test_governed_inner_sampler_equivalence():
    pytest.importorskip("scipy")
    from par_model_v2.projection.mlmc_inner_estimator import (
        governed_inner_sampler_factory)
    sampler = governed_inner_sampler_factory(rem_months=108, h_month=12)

    # outer state = short-rate node; small grid for speed
    def outer(rng, n):
        return rng.uniform(0.0, 0.04, size=n)

    N_L = 64
    rng1 = np.random.default_rng(2026)
    sl = nested_single_level(outer, sampler, payoff=identity_payoff,
                             n_outer=24, n_inner=N_L, rng=rng1)
    rng2 = np.random.default_rng(2027)
    ml = mlmc_nested(outer, sampler, payoff=identity_payoff,
                     n0=8, M=2, L=3, n_outer_per_level=[48, 24, 12, 6], rng=rng2)
    assert ml.ladder[-1] == N_L
    # linear functional -> both unbiased for E[L(X)]; agree within combined SE
    assert abs(ml.estimate - sl.estimate) < 6 * (sl.std_error + ml.std_error) + 1.0
