"""Phase 30 Task 2 - tree-3 vine deepening tests."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from par_model_v2.projection.t_copula_tail_matched_aggregation import (
    simulate_t_copula_uniforms,
)
from par_model_v2.projection.vine_copula_pair_aggregation import (
    FIT_FRACTION,
    FIT_SEED,
    TAIL_LEVEL_P,
    fit_vine_pair_families,
    simulate_vine_pair_copula_uniforms,
)
from par_model_v2.projection.vine_copula_upgrade import (
    DRIVER_NAMES,
    FIRST_TREE_EDGES,
    PAIR_FAMILY_CANDIDATES,
    RANK_INVARIANCE_DF,
    SECOND_TREE_EDGES,
    VINE_ROOT_DRIVER,
)
from par_model_v2.projection.vine_tree3_aggregation import (
    MAX_VINE_TREES_P30,
    THIRD_TREE_EDGES,
    VINE2_COMPONENT_SCR_REFERENCE,
    Tree3VineFit,
    fit_tree3_pairs,
    simulate_tree3_vine_uniforms,
    tree3_vine_fit_from_dict,
    tree3_vine_use_restrictions,
    validate_tree3_design_envelope,
)


DRIVERS = tuple(DRIVER_NAMES)
REPORT = Path("docs/validation/PHASE30_TASK2_TREE3_VINE_REPORT.json")


def _corr7(rho=0.35):
    R = np.full((7, 7), rho)
    np.fill_diagonal(R, 1.0)
    return R


def _synthetic_losses(n=6000, seed=30):
    rng = np.random.default_rng(seed)
    z = rng.standard_normal((n, 7)) @ np.linalg.cholesky(_corr7(0.25)).T
    credit_tail = np.maximum(z[:, 2] - np.quantile(z[:, 2], 0.85), 0.0)
    liq_tail = np.maximum(z[:, 6] - np.quantile(z[:, 6], 0.85), 0.0)
    z[:, 6] += 1.25 * credit_tail
    z[:, 5] += 0.90 * credit_tail
    # joint-conditional corner so tree-3 has something real to select
    z[:, 0] += 0.80 * np.minimum(credit_tail, liq_tail)
    z[:, 3] += 0.60 * np.minimum(credit_tail, liq_tail)
    return {name: z[:, i] for i, name in enumerate(DRIVERS)}


def _fits():
    losses = _synthetic_losses()
    fit2 = fit_vine_pair_families(losses, DRIVERS)
    fit3 = fit_tree3_pairs(losses, DRIVERS, fit2)
    return losses, fit2, fit3


# ---------------------------------------------------------------- envelope


def test_envelope_is_valid_and_capped():
    checks = validate_tree3_design_envelope()
    assert checks["envelope_ok"] is True
    assert checks["third_tree_edge_count"] == 4
    assert MAX_VINE_TREES_P30 == 3


def test_third_tree_edges_match_design_note():
    named = [
        "{}-{} | {},{}".format(
            DRIVERS[a], DRIVERS[b], DRIVERS[c[0]], DRIVERS[c[1]]
        )
        for a, b, c in THIRD_TREE_EDGES
    ]
    assert named == [
        "fx-rate | credit,liquidity",
        "rate-lapse | credit,liquidity",
        "lapse-mortality | credit,liquidity",
        "equity-liquidity | credit,fx",
    ]


def test_third_tree_pairs_disjoint_from_tree12():
    pairs12 = {tuple(sorted(e)) for e in FIRST_TREE_EDGES}
    pairs12.update(tuple(sorted((a, b))) for a, b, _ in SECOND_TREE_EDGES)
    for a, b, _ in THIRD_TREE_EDGES:
        assert tuple(sorted((a, b))) not in pairs12


def test_all_conditioner_sets_include_credit_root():
    for _, _, cond in THIRD_TREE_EDGES:
        assert VINE_ROOT_DRIVER in cond
        assert len(set(cond)) == 2


# ---------------------------------------------------------------- fit


def test_fit_is_deterministic_and_leakage_split_matches_phase29():
    losses, fit2, fit3 = _fits()
    fit3b = fit_tree3_pairs(losses, DRIVERS, fit2)
    assert fit3.to_dict() == fit3b.to_dict()
    # same split seed/fraction as Phase 29 => same digests as the 2-tree fit
    assert fit3.fit_indices_digest == fit2.fit_indices_digest
    assert fit3.holdout_indices_digest == fit2.holdout_indices_digest
    assert fit3.fit_indices_digest != fit3.holdout_indices_digest


def test_fit_selections_only_pre_registered_pairs_and_families():
    _, _, fit3 = _fits()
    assert len(fit3.tree3_selections) == 4
    for sel, (a, b, cond) in zip(fit3.tree3_selections, THIRD_TREE_EDGES):
        assert sel.edge == (a, b)
        assert sel.condition_on == cond
        assert sel.family in PAIR_FAMILY_CANDIDATES
        assert 0.0 <= sel.strength <= 0.75


def test_fit_roundtrip_through_dict():
    _, _, fit3 = _fits()
    d = fit3.to_dict()
    fit3r = tree3_vine_fit_from_dict(d)
    assert fit3r.to_dict() == d


# ---------------------------------------------------------------- simulator


def test_frozen_t_boundary_is_base_sampler_bit_identical():
    _, _, fit3 = _fits()
    R = _corr7()
    a = simulate_tree3_vine_uniforms(
        np.random.default_rng(7), 4000, R, RANK_INVARIANCE_DF, fit3,
        mode="frozen_t_boundary",
    )
    b = simulate_t_copula_uniforms(
        np.random.default_rng(7), 4000, R, RANK_INVARIANCE_DF
    )
    assert np.array_equal(a, b)


def test_vine2_boundary_bit_identical_to_phase29_candidate():
    _, fit2, fit3 = _fits()
    R = _corr7()
    a = simulate_tree3_vine_uniforms(
        np.random.default_rng(11), 4000, R, RANK_INVARIANCE_DF, fit3,
        mode="vine2_boundary",
    )
    b = simulate_vine_pair_copula_uniforms(
        np.random.default_rng(11), 4000, R, RANK_INVARIANCE_DF, fit2,
        mode="candidate",
    )
    assert np.array_equal(a, b)


def test_zero_tree3_strength_recovers_vine2_exactly():
    _, fit2, fit3 = _fits()
    zeroed = Tree3VineFit(
        frozen_fit=fit3.frozen_fit,
        tree3_selections=tuple(
            replace(s, strength=0.0) for s in fit3.tree3_selections
        ),
        fit_indices_digest=fit3.fit_indices_digest,
        holdout_indices_digest=fit3.holdout_indices_digest,
        tail_level_p=fit3.tail_level_p,
    )
    R = _corr7()
    a = simulate_tree3_vine_uniforms(
        np.random.default_rng(13), 4000, R, RANK_INVARIANCE_DF, zeroed,
        mode="candidate",
    )
    b = simulate_tree3_vine_uniforms(
        np.random.default_rng(13), 4000, R, RANK_INVARIANCE_DF, zeroed,
        mode="vine2_boundary",
    )
    assert np.array_equal(a, b)


def test_candidate_preserves_marginal_ranks():
    _, _, fit3 = _fits()
    U = simulate_tree3_vine_uniforms(
        np.random.default_rng(17), 4000, _corr7(), RANK_INVARIANCE_DF, fit3,
        mode="candidate",
    )
    for j in range(U.shape[1]):
        assert np.all(U[:, j] > 0.0) and np.all(U[:, j] < 1.0)
        # re-ranked empirical uniforms: sorted column is the uniform grid
        grid = (np.arange(U.shape[0]) + 0.5) / U.shape[0]
        assert np.allclose(np.sort(U[:, j]), grid)


def test_invalid_mode_raises():
    _, _, fit3 = _fits()
    with pytest.raises(ValueError):
        simulate_tree3_vine_uniforms(
            np.random.default_rng(1), 100, _corr7(), RANK_INVARIANCE_DF, fit3,
            mode="bogus",
        )


# ---------------------------------------------------------------- governance


def test_use_restrictions_are_educational_with_stop_rule():
    ur = tree3_vine_use_restrictions()
    assert ur["classification"] == "EDUCATIONAL"
    assert any("stop-rule" in s or "stop_rule" in s for s in ur["restrictions"]) or \
        "stop_rule" in ur["references"]
    assert ur["references"]["vine2_component_reference"] == (
        VINE2_COMPONENT_SCR_REFERENCE
    )


# ---------------------------------------------------------------- report gates


needs_report = pytest.mark.skipif(not REPORT.exists(), reason="report absent")


@needs_report
def test_report_verdict_pass_and_gates():
    rep = json.loads(REPORT.read_text(encoding="utf-8"))
    assert rep["verdict"] == "PASS"
    gates = rep["result"]["gates"]
    assert all(gates.values())
    assert rep["result"]["boundary_t_recovery_dev"] <= 1e-9
    assert rep["result"]["boundary_vine2_recovery_dev"] <= 1e-9


@needs_report
def test_report_dual_boundary_matches_archives():
    rep = json.loads(REPORT.read_text(encoding="utf-8"))
    r = rep["result"]
    assert r["frozen_t_component_reference_readout"]["scr_component"] == (
        39_975.654628199336
    )
    assert r["vine2_boundary_readout"]["scr_component"] == (
        VINE2_COMPONENT_SCR_REFERENCE
    )
