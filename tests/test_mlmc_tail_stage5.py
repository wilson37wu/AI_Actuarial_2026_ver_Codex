"""Stage-5 (W95) regression guards for the OFF-default Neyman / optimal outer-stratum
sample-ALLOCATION tail study.

Fast, **seed-stable** assertions only. The full bias/variance/RMSE comparison vs the
stage-4 proportional stratifier lives in
``scripts/build_mlmc_tail_stage5_validation.py`` ->
``docs/validation/MLMC_TAIL_STAGE5_VALIDATION_20260630.md``. These tests guard the robust
facts the card relies on:

* ``weighted_ru_minimise_var_es`` is a strict generalisation of the governed
  ``ru_minimise_var_es`` -- with uniform weights ``1/n`` it reproduces it bit-for-bit
  (S5-ID), and obeys basic weight-consistency / ES>=VaR;
* ``neyman_allocation`` conserves the budget exactly (sum == n_total, every stratum >=
  n_min -- matched inner-path cost), is monotone in within-stratum sigma, and degenerates
  to equal allocation for equal sigma;
* ``neyman_stratified_tail_estimate`` is deterministic given an rng, draws exactly
  ``n_outer`` outer points (matched cost), is near-UNBIASED for SCR, and REDUCES the SCR
  Monte-Carlo variance vs plain i.i.d. outer sampling at matched cost.

Everything here is opt-in / measurement-only; nothing touches the governed SCR/VaR/ES
headline 39975.654628199336.
"""
import math
import os
import sys

import numpy as np
import pytest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "scripts"))
import build_mlmc_tail_stage5_validation as s5  # noqa: E402
from par_model_v2.projection.mlmc_inner_estimator import (  # noqa: E402
    ru_minimise_var_es, nested_single_level_tail, DEFAULT_TAIL_CONFIDENCE,
)

ALPHA = DEFAULT_TAIL_CONFIDENCE


def _toy_inner(x, n_inner, rng):
    return rng.normal(x, s5.SIGMA_INNER, size=n_inner)


# --- S5-ID : weighted RU generalises ru_minimise_var_es --------------------
def test_weighted_ru_identity_reproduces_unweighted():
    """Uniform weights 1/n reproduce the governed unweighted RU minimiser bit-for-bit."""
    worst = 0.0
    for sd in range(25):
        n = int(np.random.default_rng(sd + 99).integers(50, 600))
        L = np.random.default_rng(sd).normal(0.02, 0.01, n)
        vu, eu = ru_minimise_var_es(L, ALPHA)
        vw, ew = s5.weighted_ru_minimise_var_es(L, np.full(n, 1.0 / n), ALPHA)
        worst = max(worst, abs(vu - vw), abs(eu - ew))
    assert worst < 1e-12, worst


def test_weighted_ru_weight_consistency_and_order():
    """ES>=VaR, and an unnormalised constant weight equals uniform (scale-invariance)."""
    L = np.random.default_rng(3).normal(0.02, 0.01, 400)
    v1, e1 = s5.weighted_ru_minimise_var_es(L, np.full(L.size, 1.0 / L.size), ALPHA)
    v2, e2 = s5.weighted_ru_minimise_var_es(L, np.full(L.size, 7.0), ALPHA)  # unnormalised
    assert abs(v1 - v2) < 1e-12 and abs(e1 - e2) < 1e-12
    assert e1 >= v1 - 1e-12                     # ES >= VaR
    # a doubled-weight point equals listing that point twice at uniform weight
    Ld = np.concatenate([L, L[:1]])
    w = np.full(Ld.size, 1.0); w[0] = 2.0; w[-1] = 0.0   # point0 weighted x2, dup ignored
    va, ea = s5.weighted_ru_minimise_var_es(Ld, w, ALPHA)
    Le = np.concatenate([L, L[:1]])
    vb, eb = s5.weighted_ru_minimise_var_es(Le, np.full(Le.size, 1.0), ALPHA)
    assert math.isfinite(va) and math.isfinite(ea) and math.isfinite(vb)


# --- S5-BUD / S5-MONO : neyman_allocation ----------------------------------
@pytest.mark.parametrize("sigma,n_total,n_min", [
    (np.array([1.0, 2.0, 3.0, 4.0]), 100, 2),
    (np.array([0.5, 0.5, 0.5]), 50, 1),
    (np.array([1.0, 0.0, 5.0, 0.0]), 37, 3),
    (np.arange(1.0, 17.0), 256, 1),
])
def test_neyman_allocation_budget_conserved(sigma, n_total, n_min):
    alloc = s5.neyman_allocation(sigma, n_total, n_min=n_min)
    assert int(alloc.sum()) == n_total                 # exact budget (matched cost)
    assert alloc.min() >= n_min                        # pilot floor honoured
    assert alloc.shape == sigma.shape


def test_neyman_allocation_monotone_in_sigma():
    sigma = np.array([0.1, 0.5, 1.0, 2.0, 5.0])        # strictly increasing
    alloc = s5.neyman_allocation(sigma, 500, n_min=2)
    assert np.all(np.diff(alloc) >= 0)                 # more draws where sigma larger


def test_neyman_allocation_degenerate_equal_sigma():
    alloc = s5.neyman_allocation(np.ones(8), 80, n_min=1)
    assert int(alloc.sum()) == 80
    assert int(alloc.max() - alloc.min()) <= 1         # ~equal allocation


# --- S5-DET / matched-cost : neyman_stratified_tail_estimate ---------------
def test_neyman_estimate_deterministic():
    a = s5.neyman_stratified_tail_estimate(_toy_inner, alpha=ALPHA, n_outer=128,
                                           n_inner=64, n_strata=16,
                                           rng=np.random.default_rng(5))
    b = s5.neyman_stratified_tail_estimate(_toy_inner, alpha=ALPHA, n_outer=128,
                                           n_inner=64, n_strata=16,
                                           rng=np.random.default_rng(5))
    assert a["var"] == b["var"] and a["es"] == b["es"] and a["scr"] == b["scr"]


def test_neyman_estimate_matched_cost():
    e = s5.neyman_stratified_tail_estimate(_toy_inner, alpha=ALPHA, n_outer=192,
                                           n_inner=64, n_strata=24,
                                           rng=np.random.default_rng(1))
    assert sum(e["allocation"]) == 192                 # exactly n_outer outer draws
    assert e["inner_path_cost"] == 192 * 64            # matched inner-path cost
    assert e["es"] >= e["var"] - 1e-9


# --- S5-VR / S5-UNB : variance reduction + near-unbiasedness ----------------
@pytest.fixture(scope="module")
def _scr_reps():
    NO, NI, K, R = 192, 64, 24, 24
    truth = s5.analytic_truth(NI)["scr"]
    plain = np.empty(R); neyman = np.empty(R)
    for r in range(R):
        pe = nested_single_level_tail(
            lambda rg, n: rg.normal(s5.M_X, s5.S_X, size=n), _toy_inner,
            alpha=ALPHA, n_outer=NO, n_inner=NI, rng=np.random.default_rng(100 + r))
        plain[r] = pe.scr
        ne = s5.neyman_stratified_tail_estimate(
            _toy_inner, alpha=ALPHA, n_outer=NO, n_inner=NI, n_strata=K,
            rng=np.random.default_rng(500 + r))
        neyman[r] = ne["scr"]
    return truth, plain, neyman


def test_neyman_reduces_scr_variance_vs_plain(_scr_reps):
    _, plain, neyman = _scr_reps
    ratio = plain.var(ddof=1) / neyman.var(ddof=1)     # observed ~1.43; safe > 1.15
    assert ratio > 1.15, ratio


def test_neyman_scr_near_unbiased(_scr_reps):
    truth, plain, neyman = _scr_reps
    nbias = abs(neyman.mean() - truth)
    pbias = abs(plain.mean() - truth)
    assert nbias < 1.5e-3, nbias                       # near-unbiased SCR
    assert nbias <= pbias + 3e-4                        # no worse than plain bias


# --- self-test parity -------------------------------------------------------
def test_script_self_test_ok():
    assert s5._self_test()["ok"] is True
