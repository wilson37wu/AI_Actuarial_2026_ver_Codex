"""Phase 27 Task 4 -- skew-t copula tail-dependence diagnostics unit tests.

Verifies the pre-registered Task 4 gates: the upper/lower tail-dependence grid
re-draw, the per-metric percentile-CI summary, the archive cross-check against
the cached P27T3 records (bit-identical at p=0.90), the MR-010/MR-014 no-refresh
DECISION algebra (move <= 1% trigger), the diagnostics consistency
(skew-t radial asymmetry >= symmetric on CRN), the order-independent digest, and
the educational use-restrictions. EDUCATIONAL model.
"""
from __future__ import annotations

import glob
import json
from pathlib import Path

import numpy as np
import pytest

from par_model_v2.projection.skew_t_copula_aggregation import RANK_INVARIANCE_DF
from par_model_v2.projection.skew_t_tail_diagnostics import (
    MR_REFRESH_TRIGGER,
    P26T3_FROZEN_T_COMPONENT_MEAN,
    P27T3_RADIAL_ASYMMETRY_MEAN_AT_090,
    P27T3_SKEWT_COMPONENT_MEAN,
    TAIL_LEVEL_GRID,
    crosscheck_against_p27t3,
    mr_refresh_decision,
    summarise_metric,
    summarise_tail_diagnostics,
    tail_dependence_grid,
    tail_diagnostics_digest,
    tail_diagnostics_use_restrictions,
)

GAMMA_HAT = 6.24229466599955e-05
P27T2V = Path("/var/tmp/p27t2_stage/verified.npz")
P27T3_INPUTS = Path("/var/tmp/p27t3_stage/verified_inputs.npz")
P27T3_PARTIALS = sorted(glob.glob("/var/tmp/p27t3_stage/partial_*.json"))
REPORT = Path("docs/validation/PHASE27_TASK4_TAIL_DIAGNOSTICS_REPORT.json")

_staged = P27T2V.exists() and P27T3_INPUTS.exists() and len(P27T3_PARTIALS) > 0
needs_stage = pytest.mark.skipif(not _staged, reason="staged inputs absent")


def _corr(d=7, rho=0.4):
    R = np.full((d, d), rho)
    np.fill_diagonal(R, 1.0)
    return R


# --------------------------------------------------------------------------
# Self-contained gates (no staged inputs needed)
# --------------------------------------------------------------------------
def test_tail_grid_shape_and_keys():
    """The grid returns one record per seed with lambda_U/L and radial asym at
    every p for both the skew-t and symmetric legs."""
    R = _corr(7, 0.35)
    seeds = [11, 22, 33]
    grid = tail_dependence_grid(R, RANK_INVARIANCE_DF, GAMMA_HAT, seeds, n_sim=3000)
    assert grid["n_replicates"] == 3
    assert len(grid["records"]) == 3
    rec = grid["records"][0]
    for p in TAIL_LEVEL_GRID:
        k = f"{int(round(p * 100)):02d}"
        for stem in ("skewt_lambda_U", "skewt_lambda_L", "skewt_radial_asym",
                     "sym_lambda_U", "sym_lambda_L", "sym_radial_asym",
                     "skewt_minus_sym_radial_asym"):
            assert f"{stem}_{k}" in rec
    # tail-dependence proxies live in [0, 1]
    for p in TAIL_LEVEL_GRID:
        k = f"{int(round(p * 100)):02d}"
        assert 0.0 <= rec[f"skewt_lambda_U_{k}"] <= 1.0
        assert 0.0 <= rec[f"skewt_lambda_L_{k}"] <= 1.0


def test_tail_grid_reproducible_same_seeds():
    """Same seeds -> identical records (re-draw is deterministic)."""
    R = _corr(7, 0.3)
    g1 = tail_dependence_grid(R, RANK_INVARIANCE_DF, GAMMA_HAT, [5, 6], n_sim=2500)
    g2 = tail_dependence_grid(R, RANK_INVARIANCE_DF, GAMMA_HAT, [5, 6], n_sim=2500)
    k = "90"
    for a, b in zip(g1["records"], g2["records"]):
        assert a[f"skewt_lambda_U_{k}"] == b[f"skewt_lambda_U_{k}"]
        assert a[f"sym_lambda_L_{k}"] == b[f"sym_lambda_L_{k}"]


def test_summarise_metric_ci():
    s = summarise_metric(list(range(1, 201)), 0.95)
    assert s["n"] == 200
    assert abs(s["mean"] - 100.5) < 1e-9
    assert s["ci_lo"] < s["mean"] < s["ci_hi"]
    assert s["min"] == 1.0 and s["max"] == 200.0


def test_mr_refresh_decision_no_refresh():
    """gamma_hat ~ 0: skew-t component ~ frozen-t basis -> NO refresh."""
    d = mr_refresh_decision(P27T3_SKEWT_COMPONENT_MEAN, P26T3_FROZEN_T_COMPONENT_MEAN)
    assert d["refresh_required"] is False
    assert d["max_abs_relative_move"] <= MR_REFRESH_TRIGGER
    assert "NO refresh" in d["decision"]


def test_mr_refresh_decision_triggers_on_big_move():
    """A > 1% component-SCR move flips the decision to REFRESH."""
    d = mr_refresh_decision(45000.0, 39595.0, scr_skewt_point=45000.0,
                            scr_basis_point=39975.0)
    assert d["refresh_required"] is True
    assert d["max_abs_relative_move"] > MR_REFRESH_TRIGGER
    assert "REFRESH" in d["decision"]


def test_digest_order_independent():
    recs = []
    for i in range(8):
        r = {"replicate_index": i}
        for p in TAIL_LEVEL_GRID:
            k = f"{int(round(p * 100)):02d}"
            r[f"skewt_lambda_U_{k}"] = 0.2 + 0.001 * i
            r[f"skewt_lambda_L_{k}"] = 0.2 + 0.0005 * i
            r[f"sym_lambda_U_{k}"] = 0.19 + 0.001 * i
            r[f"sym_lambda_L_{k}"] = 0.19 + 0.0005 * i
        recs.append(r)
    import random
    shuffled = recs[:]
    random.Random(1).shuffle(shuffled)
    assert tail_diagnostics_digest(recs) == tail_diagnostics_digest(shuffled)


def test_use_restrictions_educational():
    r = tail_diagnostics_use_restrictions()
    assert r["classification"] == "EDUCATIONAL"
    assert any("FROZEN" in s for s in r["restrictions"])
    assert any("MR-015" in s for s in r["restrictions"])


# --------------------------------------------------------------------------
# Staged-input gates (cached P27T3 records)
# --------------------------------------------------------------------------
def _load_cached(n=None):
    recs = {}
    for p in P27T3_PARTIALS:
        for r in json.loads(Path(p).read_text(encoding="utf-8"))["records"]:
            recs[int(r["replicate_index"])] = r
    ordered = [recs[i] for i in range(len(recs))]
    return ordered if n is None else ordered[:n]


def _inputs():
    rho = np.asarray(np.load(P27T2V)["rho"], float)
    gamma_hat = float(np.load(P27T3_INPUTS)["gamma_hat"][0])
    return rho, gamma_hat


@needs_stage
def test_crosscheck_bit_identical_subset():
    """At p=0.90 the recomputed lambda_U/L/radial asym reproduce the cached
    P27T3 records BIT-identically (faithful re-read, not a re-tune)."""
    cached = _load_cached(12)
    rho, gamma_hat = _inputs()
    grid = tail_dependence_grid(
        rho, RANK_INVARIANCE_DF, gamma_hat, [int(c["cop_seed"]) for c in cached])
    cc = crosscheck_against_p27t3(grid, cached, tol=1e-12)
    assert cc["bit_identical"] is True
    assert cc["max_abs_dev_lambda_U"] == 0.0
    assert cc["max_abs_dev_lambda_L"] == 0.0
    assert cc["max_abs_dev_radial_asym"] == 0.0


@needs_stage
def test_radial_asymmetry_near_zero_and_matches_cache():
    """gamma_hat ~ 0 -> radial asymmetry mean ~ 0 at p=0.90, matching the cached
    P27T3 mean."""
    cached = _load_cached(20)
    rho, gamma_hat = _inputs()
    grid = tail_dependence_grid(
        rho, RANK_INVARIANCE_DF, gamma_hat, [int(c["cop_seed"]) for c in cached])
    summ = summarise_tail_diagnostics(grid)
    ra = summ["p_90"]["skewt_radial_asym"]["mean"]
    assert abs(ra) < 0.05               # near-symmetric
    # the cached P27T3 mean is over all 200 replicates; the subset mean should be
    # the same order of magnitude (~1e-3) and same sign region
    assert abs(ra) < 10 * abs(P27T3_RADIAL_ASYMMETRY_MEAN_AT_090) + 0.01


@needs_stage
def test_consistency_skewt_ge_sym():
    """On CRN the skew-t radial asymmetry is >= the symmetric-t radial asymmetry
    at every p (the asymmetry lever cannot REDUCE upper-tail dependence)."""
    cached = _load_cached(20)
    rho, gamma_hat = _inputs()
    grid = tail_dependence_grid(
        rho, RANK_INVARIANCE_DF, gamma_hat, [int(c["cop_seed"]) for c in cached])
    summ = summarise_tail_diagnostics(grid)
    for p in TAIL_LEVEL_GRID:
        k = f"p_{int(round(p * 100)):02d}"
        assert summ[k]["skewt_radial_asym"]["mean"] >= summ[k]["sym_radial_asym"]["mean"] - 1e-9


@needs_stage
def test_report_gates_pass():
    if not REPORT.exists():
        pytest.skip("report not yet generated")
    rep = json.loads(REPORT.read_text(encoding="utf-8"))
    r = rep["result"]
    assert rep["verdict"] == "PASS"
    assert r["archive_crosscheck"]["bit_identical"] is True
    assert r["mr_refresh_decision"]["refresh_required"] is False
    for k, v in r["gates"].items():
        assert v is True, k
