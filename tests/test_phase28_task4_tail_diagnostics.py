"""Phase 28 Task 4 -- grouped-t within/cross-block tail-dependence diagnostics
unit tests.

Verifies the pre-registered Task 4 gates: the within/cross-block upper/lower
tail-dependence grid re-draw (grouped-t vs single-df t on CRN), the per-metric
percentile-CI summary, the archive cross-check against the cached P28T3 records
(bit-identical at p=0.90), the MR-010/MR-014 no-refresh DECISION algebra (the
GOVERNED single-df t boundary move is 0; the disclosed grouped-t move is
documented), the dilution consistency (grouped cross-block upper <= single-df t
cross-block upper on CRN), the homogeneous-boundary within-NON-FIN exact match,
the order-independent digest, and the educational use-restrictions.
EDUCATIONAL model.
"""
from __future__ import annotations

import glob
import json
from pathlib import Path

import numpy as np
import pytest

from par_model_v2.projection.grouped_t_copula_aggregation import (
    BLOCKS, RANK_INVARIANCE_DF,
)
from par_model_v2.projection.grouped_t_tail_diagnostics import (
    MR_REFRESH_TRIGGER,
    P26T3_FROZEN_T_COMPONENT_MEAN,
    P28T3_GROUPED_T_COMPONENT_MEAN,
    P28T3_SINGLE_T_COMPONENT_MEAN,
    TAIL_LEVEL_GRID,
    block_tail_dependence_grid,
    crosscheck_against_p28t3,
    mr_refresh_decision,
    summarise_block_tail_diagnostics,
    summarise_metric,
    tail_diagnostics_digest,
    tail_diagnostics_use_restrictions,
)

BLOCK_DFS = [37.865628454397445, 8.506318281609548]
P28T2V = Path("/var/tmp/p28t2_build/verified.npz")
P28T3_PARTIALS = sorted(glob.glob("/var/tmp/p28t3_stage/partial_*.json"))
REPORT = Path("docs/validation/PHASE28_TASK4_TAIL_DIAGNOSTICS_REPORT.json")

_staged = P28T2V.exists() and len(P28T3_PARTIALS) > 0
needs_stage = pytest.mark.skipif(not _staged, reason="staged inputs absent")


def _corr(d=7, rho=0.4):
    R = np.full((d, d), rho)
    np.fill_diagonal(R, 1.0)
    return R


# --------------------------------------------------------------------------
# Self-contained gates (no staged inputs needed)
# --------------------------------------------------------------------------
def test_tail_grid_shape_and_keys():
    """One record per seed with within/cross upper/lower and heterogeneity for
    both grouped-t and single-df t legs at every p."""
    R = _corr(7, 0.35)
    seeds = [11, 22, 33]
    grid = block_tail_dependence_grid(R, BLOCK_DFS, seeds, n_sim=3000)
    assert grid["n_replicates"] == 3
    assert len(grid["records"]) == 3
    rec = grid["records"][0]
    for p in TAIL_LEVEL_GRID:
        k = f"{int(round(p * 100)):02d}"
        for leg in ("grp", "sng"):
            for bk in ("nonfin", "fin"):
                assert f"{leg}_within_upper_{bk}_{k}" in rec
                assert f"{leg}_within_lower_{bk}_{k}" in rec
            assert f"{leg}_cross_upper_{k}" in rec
            assert f"{leg}_cross_lower_{k}" in rec
            assert f"{leg}_heterogeneity_upper_{k}" in rec
        assert f"grp_minus_sng_cross_upper_{k}" in rec
        assert 0.0 <= rec[f"grp_within_upper_fin_{k}"] <= 1.0
        assert 0.0 <= rec[f"grp_cross_upper_{k}"] <= 1.0


def test_homogeneous_boundary_within_nonfin_exact():
    """With df_g = the frozen df, block 0 (NON-FIN) reuses the single-df t
    shared-mixing rng position, so within-NON-FIN upper/lower are BIT-identical
    across the grouped and single legs. The FIN block and the cross-block draw
    an INDEPENDENT mixing variate in the grouped leg, so those differ even at
    equal df - that independent per-block mixing IS the dilution lever."""
    R = _corr(7, 0.3)
    grid = block_tail_dependence_grid(
        R, [RANK_INVARIANCE_DF, RANK_INVARIANCE_DF], [7, 8], n_sim=4000)
    for rec in grid["records"]:
        for p in TAIL_LEVEL_GRID:
            k = f"{int(round(p * 100)):02d}"
            assert rec[f"grp_within_upper_nonfin_{k}"] == rec[f"sng_within_upper_nonfin_{k}"]
            assert rec[f"grp_within_lower_nonfin_{k}"] == rec[f"sng_within_lower_nonfin_{k}"]
            assert rec[f"grp_cross_upper_{k}"] <= rec[f"sng_cross_upper_{k}"] + 1e-9


def test_grid_reproducible_same_seeds():
    """Same seeds -> identical records (re-draw is deterministic)."""
    R = _corr(7, 0.3)
    g1 = block_tail_dependence_grid(R, BLOCK_DFS, [5, 6], n_sim=2500)
    g2 = block_tail_dependence_grid(R, BLOCK_DFS, [5, 6], n_sim=2500)
    k = "90"
    for a, b in zip(g1["records"], g2["records"]):
        assert a[f"grp_cross_upper_{k}"] == b[f"grp_cross_upper_{k}"]
        assert a[f"sng_within_lower_nonfin_{k}"] == b[f"sng_within_lower_nonfin_{k}"]


def test_summarise_metric_ci():
    s = summarise_metric(list(range(1, 201)), 0.95)
    assert s["n"] == 200
    assert abs(s["mean"] - 100.5) < 1e-9
    assert s["ci_lo"] < s["mean"] < s["ci_hi"]
    assert s["min"] == 1.0 and s["max"] == 200.0


def test_mr_refresh_decision_no_refresh():
    """The governed single-df t boundary == frozen-t basis -> governed move 0;
    the grouped-t DOWN move is disclosed, not actioned -> NO refresh."""
    d = mr_refresh_decision(
        scr_component_single_t=P28T3_SINGLE_T_COMPONENT_MEAN,
        scr_component_basis=P26T3_FROZEN_T_COMPONENT_MEAN,
        scr_component_grouped_t=P28T3_GROUPED_T_COMPONENT_MEAN)
    assert d["refresh_required"] is False
    assert abs(d["governed_headline_relative_move"]) <= MR_REFRESH_TRIGGER
    assert "NO refresh" in d["decision"]
    assert d["disclosed_grouped_vs_basis_move_point"] < -0.05


def test_mr_refresh_decision_triggers_on_big_governed_move():
    """A > 1% GOVERNED move (single-df t boundary not recovered) flips to REFRESH."""
    d = mr_refresh_decision(
        scr_component_single_t=45000.0, scr_component_basis=39595.0,
        scr_component_grouped_t=39595.0)
    assert d["refresh_required"] is True
    assert abs(d["governed_headline_relative_move"]) > MR_REFRESH_TRIGGER
    assert "REFRESH" in d["decision"]


def test_digest_order_independent():
    recs = []
    for i in range(8):
        r = {"replicate_index": i}
        for p in TAIL_LEVEL_GRID:
            k = f"{int(round(p * 100)):02d}"
            r[f"grp_within_upper_nonfin_{k}"] = 0.2 + 0.001 * i
            r[f"grp_within_upper_fin_{k}"] = 0.12 + 0.0005 * i
            r[f"grp_cross_upper_{k}"] = 0.17 + 0.001 * i
            r[f"sng_within_upper_nonfin_{k}"] = 0.21 + 0.001 * i
            r[f"sng_within_upper_fin_{k}"] = 0.18 + 0.0005 * i
            r[f"sng_cross_upper_{k}"] = 0.25 + 0.001 * i
        recs.append(r)
    import random
    shuffled = recs[:]
    random.Random(1).shuffle(shuffled)
    assert tail_diagnostics_digest(recs) == tail_diagnostics_digest(shuffled)


def test_use_restrictions_educational():
    r = tail_diagnostics_use_restrictions()
    assert r["classification"] == "EDUCATIONAL"
    assert any("FROZEN" in s for s in r["restrictions"])
    assert any("MR-016" in s for s in r["restrictions"])


# --------------------------------------------------------------------------
# Staged-input gates (cached P28T3 records)
# --------------------------------------------------------------------------
def _load_cached(n=None):
    recs = {}
    for p in P28T3_PARTIALS:
        for r in json.loads(Path(p).read_text(encoding="utf-8"))["records"]:
            recs[int(r["replicate_index"])] = r
    ordered = [recs[i] for i in range(len(recs))]
    return ordered if n is None else ordered[:n]


def _rho():
    return np.asarray(np.load(P28T2V)["rho"], float)


@needs_stage
def test_crosscheck_bit_identical_subset():
    """At p=0.90 the recomputed grouped-t within/cross upper + heterogeneity
    reproduce the cached P28T3 records BIT-identically (faithful re-read)."""
    cached = _load_cached(12)
    grid = block_tail_dependence_grid(
        _rho(), BLOCK_DFS, [int(c["cop_seed"]) for c in cached])
    cc = crosscheck_against_p28t3(grid, cached, tol=1e-12)
    assert cc["bit_identical"] is True
    assert cc["max_abs_dev"] == 0.0


@needs_stage
def test_grouped_dilutes_cross_block():
    """On CRN the grouped-t cross-block upper is <= the single-df t cross-block
    upper at every p (df_g > frozen -> dilution of the maximal-cross boundary)."""
    cached = _load_cached(20)
    grid = block_tail_dependence_grid(
        _rho(), BLOCK_DFS, [int(c["cop_seed"]) for c in cached])
    summ = summarise_block_tail_diagnostics(grid)
    for p in TAIL_LEVEL_GRID:
        k = f"p_{int(round(p * 100)):02d}"
        assert summ[k]["grp_cross_upper"]["mean"] <= summ[k]["sng_cross_upper"]["mean"] + 1e-9
        assert summ[k]["grp_minus_sng_cross_upper"]["mean"] <= 1e-9


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
