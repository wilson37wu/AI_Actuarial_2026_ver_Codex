"""Tests for the W64 quantile / Expected-Shortfall tail-functional MLMC prototype.

Validates the stage-2 quantile-MLMC estimator specified in
``docs/research/MLMC_QUANTILE_ESTIMATOR_DESIGN_NOTE_20260619.md``:

* the **telescoping identity** -- a single-base-level (``L=0``) MLMC tail estimate
  is bit-for-bit identical to the fixed single-level estimator;
* the **RU minimiser recovers VaR/ES** -- the Rockafellar-Uryasev argmin equals
  the empirical quantile / tail-mean and the analytic Normal truth;
* MLMC ``L>0`` is a consistent estimator of the finest-level VaR/ES/SCR;
* determinism under a fixed seed; and the smoothed-CDF VaR oracle cross-check.

The estimator is OPT-IN and not wired into any governed figure (the governed
SCR/VaR/ES stays fixed single-level); these tests guard correctness + the
telescoping-identity gate (G4) ahead of the stage-3 bias/accuracy validation.
"""
import numpy as np
import pytest

from par_model_v2.projection.mlmc_inner_estimator import (
    DEFAULT_TAIL_CONFIDENCE,
    TailEstimate,
    _empirical_var_es,
    ru_objective,
    ru_minimise_var_es,
    smoothed_cdf_var,
    nested_single_level_tail,
    mlmc_nested_tail,
)

# --- analytic nested testbed (same shape as the mean-prototype tests) --------
# Outer X ~ Normal(M_X, S_X); L(x) = x; inner draws ~ Normal(x, SIGMA_INNER).
# Conditional liability L_N(x) ~ Normal(x, SIGMA_INNER^2/N), so the population
# of L_N(X) is Normal(M_X, S_X^2 + SIGMA_INNER^2/N) with closed-form VaR/ES.
M_X, S_X, SIGMA_INNER = 0.02, 0.01, 0.05
ALPHA = 0.995
Z_995 = 2.5758293035489004  # standard-normal 99.5% quantile


def outer_sampler(rng, n):
    return rng.normal(M_X, S_X, size=n)


def inner_sampler(x, n_inner, rng):
    return rng.normal(x, SIGMA_INNER, size=n_inner)


def analytic_var_es(n_inner, alpha=ALPHA):
    from math import sqrt, exp, pi
    sd = sqrt(S_X ** 2 + SIGMA_INNER ** 2 / n_inner)
    z = Z_995
    var = M_X + z * sd
    es = M_X + sd * exp(-z * z / 2.0) / sqrt(2.0 * pi) / (1.0 - alpha)
    return var, es


# --- defaults ----------------------------------------------------------------
def test_default_confidence():
    assert DEFAULT_TAIL_CONFIDENCE == 0.995


# --- RU objective + minimiser ------------------------------------------------
def test_ru_objective_value_matches_definition():
    L = np.array([1.0, 2.0, 3.0, 10.0])
    q, a = 2.0, 0.5
    # q + mean((L-q)_+)/(1-a) = 2 + mean([0,0,1,8])/0.5 = 2 + (9/4)/0.5 = 2 + 4.5
    assert ru_objective(L, q, a) == pytest.approx(6.5)


def test_ru_minimiser_recovers_empirical_var_es():
    rng = np.random.default_rng(11)
    L = rng.normal(0.02, 0.012, size=60000)
    var_ru, es_ru = ru_minimise_var_es(L, ALPHA)
    var_emp, es_emp = _empirical_var_es(L, ALPHA)
    # RU argmin (an order statistic) matches the empirical np.quantile VaR to O(1/n)
    assert abs(var_ru - var_emp) < 5e-4
    # ES (the RU minimum) matches the tail-mean ES closely
    assert abs(es_ru - es_emp) < 5e-4
    assert es_ru >= var_ru  # ES of the upper tail is at or beyond VaR


def test_ru_minimiser_recovers_analytic_truth():
    # Large nested single-level sample at N=256: RU VaR/ES match the Normal truth.
    sl = nested_single_level_tail(
        outer_sampler, inner_sampler, alpha=ALPHA,
        n_outer=60000, n_inner=256, rng=np.random.default_rng(123))
    var_t, es_t = analytic_var_es(256)
    assert abs(sl.var - var_t) / var_t < 0.02
    assert abs(sl.es - es_t) / es_t < 0.02
    assert sl.scr == pytest.approx(sl.var - sl.mean_liability)


# --- telescoping identity: L=0 == fixed single-level, BIT-FOR-BIT ------------
def test_telescoping_identity_L0_bit_for_bit():
    sl = nested_single_level_tail(
        outer_sampler, inner_sampler, alpha=ALPHA,
        n_outer=4000, n_inner=128, rng=np.random.default_rng(777))
    ml0 = mlmc_nested_tail(
        outer_sampler, inner_sampler, alpha=ALPHA,
        n0=128, M=2, L=0, n_outer_per_level=4000,
        rng=np.random.default_rng(777))
    # Exact equality (not approx): the L=0 MLMC path is the single-level reduction.
    assert ml0.var == sl.var
    assert ml0.es == sl.es
    assert ml0.scr == sl.scr
    assert ml0.mean_liability == sl.mean_liability
    assert ml0.method == "mlmc" and sl.method == "fixed"
    assert ml0.ladder == [128]


# --- MLMC L>0 is a consistent estimator of the finest-level figures ----------
def test_mlmc_tail_consistency_with_single_level():
    NL = 128
    sl = nested_single_level_tail(
        outer_sampler, inner_sampler, alpha=ALPHA,
        n_outer=8000, n_inner=NL, rng=np.random.default_rng(4040))
    ml = mlmc_nested_tail(
        outer_sampler, inner_sampler, alpha=ALPHA,
        n0=16, M=2, L=3, n_outer_per_level=[6000, 3000, 1500, 800],
        rng=np.random.default_rng(2026))
    assert ml.ladder == [16, 32, 64, 128]
    assert ml.n_inner == NL
    # VaR / ES / SCR agree with the fixed-NL benchmark within a MC tolerance band.
    assert abs(ml.var - sl.var) / sl.var < 0.06
    assert abs(ml.es - sl.es) / sl.es < 0.06
    assert ml.scr == pytest.approx(ml.var - ml.mean_liability)
    # The mean liability (linear, unbiased) agrees tightly.
    assert abs(ml.mean_liability - sl.mean_liability) / abs(sl.mean_liability) < 0.02


def test_mlmc_tail_levels_and_cost_accounting():
    ml = mlmc_nested_tail(
        outer_sampler, inner_sampler, alpha=ALPHA,
        n0=16, M=2, L=3, n_outer_per_level=[2000, 1000, 500, 300],
        rng=np.random.default_rng(9))
    assert [lv["level"] for lv in ml.levels] == [0, 1, 2, 3]
    # Antithetic coupling: cost = sum_l n_outer_l * N_fine_l (coarse reuses fine).
    expected = 2000 * 16 + 1000 * 32 + 500 * 64 + 300 * 128
    assert ml.inner_path_cost == expected
    assert ml.summary()["method"] == "mlmc"


# --- determinism (seed protocol: staged == monolithic) -----------------------
def test_determinism_fixed_seed():
    kw = dict(alpha=ALPHA, n0=16, M=2, L=3, n_outer_per_level=2000)
    a = mlmc_nested_tail(outer_sampler, inner_sampler,
                         rng=np.random.default_rng(5), **kw)
    b = mlmc_nested_tail(outer_sampler, inner_sampler,
                         rng=np.random.default_rng(5), **kw)
    assert a.var == b.var and a.es == b.es and a.scr == b.scr
    assert a.mean_liability == b.mean_liability


# --- smoothed-CDF VaR oracle (independent of the RU path) --------------------
def test_smoothed_cdf_var_oracle_brackets_and_agrees():
    rng = np.random.default_rng(31)
    L = rng.normal(0.02, 0.012, size=40000)
    var_emp, _ = _empirical_var_es(L, ALPHA)
    # Decreasing bandwidth -> shrinking O(h) smoothing bias toward the empirical VaR.
    v_coarse = smoothed_cdf_var(L, ALPHA, h=0.01)
    v_fine = smoothed_cdf_var(L, ALPHA, h=0.0005)
    assert abs(v_fine - var_emp) < abs(v_coarse - var_emp) + 1e-9
    assert abs(v_fine - var_emp) < 2e-3


def test_smoothed_cdf_var_requires_positive_bandwidth():
    with pytest.raises(ValueError):
        smoothed_cdf_var(np.arange(10.0), ALPHA, h=0.0)


# --- scipy cross-check (optional; skipped if scipy absent) -------------------
def test_ru_es_matches_scipy_normal_truth():
    scipy_stats = pytest.importorskip("scipy.stats")
    # Direct CVaR of a Normal sample vs the RU minimum.
    mu, sd = 0.02, 0.013
    rng = np.random.default_rng(77)
    L = rng.normal(mu, sd, size=200000)
    _, es_ru = ru_minimise_var_es(L, ALPHA)
    z = scipy_stats.norm.ppf(ALPHA)
    es_truth = mu + sd * scipy_stats.norm.pdf(z) / (1.0 - ALPHA)
    assert abs(es_ru - es_truth) / es_truth < 0.02
