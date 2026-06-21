"""Stage-4 (W66) regression guards for the tail-MLMC variance-reduction +
Expected-Shortfall bias-correction tools.

Fast, **seed-stable** assertions only. The precise statistical results (the
variance-reduction factors, the ES bias-reduction vs the closed-form Normal truth,
and the cost/variance-decay study) live in
``scripts/build_mlmc_tail_stage4_validation.py`` ->
``docs/validation/MLMC_TAIL_STAGE4_VALIDATION_20260619.md``. These tests guard the
robust facts the card relies on:

* ``_norm_ppf`` matches known standard-normal quantiles (numpy-only inverse CDF);
* ``stratified_normal_outer_sampler`` is deterministic, right-sized, unbiased in
  mean, and **reduces** the Monte-Carlo variance of the 99.5% tail VaR/ES/SCR
  estimators vs plain i.i.d. outer sampling (generous fixed-seed margin);
* ``es_bias_corrected`` is deterministic, obeys the bootstrap identity
  ``es_bc == 2*es_raw - boot_mean``, and lifts the downward-biased ES on average;
* both tools compose with ``nested_single_level_tail`` and ``mlmc_nested_tail``.

Everything here is opt-in; nothing touches the governed SCR/VaR/ES headline.
"""
import math

import numpy as np
import pytest

from par_model_v2.projection.mlmc_inner_estimator import (
    _norm_ppf,
    stratified_normal_outer_sampler,
    es_bias_corrected,
    nested_single_level_tail,
    mlmc_nested_tail,
    ru_minimise_var_es,
    DEFAULT_TAIL_CONFIDENCE,
)

M_X, S_X, SIGMA_INNER = 0.02, 0.01, 0.05
ALPHA = DEFAULT_TAIL_CONFIDENCE
Z_995 = 2.5758293035489004


def inner_sampler(x, n_inner, rng):
    return rng.normal(x, SIGMA_INNER, size=n_inner)


def plain_outer(rng, n):
    return rng.normal(M_X, S_X, size=n)


def analytic_truth(n_inner, alpha=ALPHA):
    sd = math.sqrt(S_X ** 2 + SIGMA_INNER ** 2 / n_inner)
    var = M_X + Z_995 * sd
    es = M_X + sd * math.exp(-Z_995 * Z_995 / 2.0) / math.sqrt(2.0 * math.pi) / (1.0 - alpha)
    return {"var": var, "es": es, "scr": var - M_X}


# --- _norm_ppf -------------------------------------------------------------
def test_norm_ppf_known_quantiles():
    pts = {0.5: 0.0, 0.975: 1.959963985, 0.995: 2.575829304,
           0.005: -2.575829304, 0.84134474606854: 1.0, 0.1586552539: -1.0}
    for p, expected in pts.items():
        got = float(_norm_ppf(np.array([p]))[0])
        assert abs(got - expected) < 5e-7, (p, got, expected)


def test_norm_ppf_monotone_and_symmetric():
    p = np.linspace(0.001, 0.999, 99)
    z = _norm_ppf(p)
    assert np.all(np.diff(z) > 0)                      # strictly increasing
    assert abs(float(_norm_ppf(np.array([0.3]))[0])
               + float(_norm_ppf(np.array([0.7]))[0])) < 1e-9   # antisymmetry


def test_norm_ppf_matches_scipy():
    st = pytest.importorskip("scipy.stats")
    p = np.array([0.01, 0.1, 0.5, 0.9, 0.975, 0.995, 0.999])
    assert np.allclose(_norm_ppf(p), st.norm.ppf(p), atol=1e-7)


# --- stratified outer sampler ----------------------------------------------
def test_stratified_sampler_deterministic_and_sized():
    s = stratified_normal_outer_sampler(M_X, S_X)
    a = s(np.random.default_rng(4), 2000)
    b = s(np.random.default_rng(4), 2000)
    assert a.shape == (2000,) and np.array_equal(a, b)


def test_stratified_sampler_unbiased_mean():
    s = stratified_normal_outer_sampler(M_X, S_X)
    x = s(np.random.default_rng(11), 20000)
    assert abs(float(x.mean()) - M_X) < 5e-4
    assert abs(float(x.std()) - S_X) < 5e-4


def test_stratified_antithetic_symmetric_mean():
    s = stratified_normal_outer_sampler(M_X, S_X, antithetic=True)
    x = s(np.random.default_rng(2), 4000)          # even n -> exact reflection
    assert abs(float(x.mean()) - M_X) < 1e-12


def test_stratified_reduces_tail_variance():
    """Stratified outer sampling cuts the 99.5% tail estimator variance."""
    strat = stratified_normal_outer_sampler(M_X, S_X)
    R, n_out = 40, 2000

    def reps(sampler, seed):
        v = np.empty(R); e = np.empty(R); s = np.empty(R)
        for r in range(R):
            est = nested_single_level_tail(
                sampler, inner_sampler, alpha=ALPHA, n_outer=n_out,
                n_inner=256, rng=np.random.default_rng(seed + r))
            v[r], e[r], s[r] = est.var, est.es, est.scr
        return v, e, s

    pv, pe, ps = reps(plain_outer, 5000)
    sv, se, ss = reps(strat, 5000)
    # observed >=2.1x across seeds at this budget; assert a safe >1.5 (won't flake)
    assert pv.var(ddof=1) / sv.var(ddof=1) > 1.5      # VaR
    assert pe.var(ddof=1) / se.var(ddof=1) > 1.5      # ES
    assert ps.var(ddof=1) / ss.var(ddof=1) > 1.5      # SCR


# --- ES bootstrap bias correction ------------------------------------------
def test_es_bias_correction_identity_and_determinism():
    L = np.random.default_rng(7).normal(M_X, S_X, 3000)
    es_bc, d = es_bias_corrected(L, ALPHA, n_boot=200, rng=np.random.default_rng(1))
    # bootstrap bias-corrected identity: es_bc == 2*es_raw - boot_mean
    assert abs(es_bc - (2 * d["es_raw"] - d["boot_mean"])) < 1e-12
    es_bc2, _ = es_bias_corrected(L, ALPHA, n_boot=200, rng=np.random.default_rng(1))
    assert es_bc == es_bc2                              # deterministic given seed
    # raw ES equals the canonical RU ES of the same sample
    assert abs(d["es_raw"] - ru_minimise_var_es(L, ALPHA)[1]) < 1e-12


def test_es_bias_correction_lifts_downward_bias_on_average():
    """Averaged over seeds the correction raises the downward-biased ES toward truth."""
    truth = analytic_truth(256)["es"]
    seeds = range(12)
    raw = np.empty(len(seeds)); bc = np.empty(len(seeds))
    for i, sd in enumerate(seeds):
        x = plain_outer(np.random.default_rng(900 + sd), 1000)
        L = x + np.random.default_rng(5000 + sd).normal(0.0, SIGMA_INNER / math.sqrt(256), 1000)
        bc[i], d = es_bias_corrected(L, ALPHA, n_boot=120, rng=np.random.default_rng(40 + sd))
        raw[i] = d["es_raw"]
    # empirical ES is biased low; correction lifts it and lands closer to truth
    assert raw.mean() < truth
    assert bc.mean() >= raw.mean()
    assert abs(bc.mean() - truth) <= abs(raw.mean() - truth) + 1e-9


# --- composition with the estimators ---------------------------------------
def test_stratified_composes_with_estimators():
    strat = stratified_normal_outer_sampler(M_X, S_X)
    sl = nested_single_level_tail(strat, inner_sampler, alpha=ALPHA,
                                  n_outer=2000, n_inner=256,
                                  rng=np.random.default_rng(3))
    assert sl.es >= sl.var and sl.n_inner == 256
    # MLMC tail estimator: stratification composes; the telescoped ES can fall
    # below VaR at small budgets (the documented W65 high-variance artifact), so
    # only finiteness + ladder accounting are asserted here (not ES>=VaR).
    ml = mlmc_nested_tail(strat, inner_sampler, alpha=ALPHA, n0=16, M=2, L=4,
                          n_outer_per_level=[2000, 1000, 500, 250, 125],
                          rng=np.random.default_rng(3))
    assert math.isfinite(ml.var) and math.isfinite(ml.es) and math.isfinite(ml.scr)
    assert ml.ladder == [16, 32, 64, 128, 256] and ml.n_inner == 256
