"""Phase 30 Task 3 - tree-3 vine margin bootstrap tests.

Small-n fast checks of the bootstrap mechanics, CRN contract, stop-rule
recording and digests; the full 200 x 20,000 distribution lives in the
archived report.
"""

import json
from pathlib import Path

import numpy as np
import pytest

from par_model_v2.projection.management_actions import ManagementActionRule
from par_model_v2.projection.vine_tree3_aggregation import (
    THIRD_TREE_EDGES,
    tree3_vine_fit_from_dict,
)
from par_model_v2.projection.vine_tree3_bootstrap import (
    P29T3_VINE2_BOOTSTRAP_CI_REFERENCE,
    TREE3_BOOTSTRAP_MASTER_SEED,
    TREE3_BOOTSTRAP_N_SIM,
    TREE3_BOOTSTRAP_REPLICATES,
    TREE3_CANDIDATE_COMPONENT_SCR_POINT,
    tree3_bootstrap_digest,
    tree3_bootstrap_use_restrictions,
    tree3_fit_digest,
    tree3_margin_bootstrap,
    tree3_stop_rule_assessment,
)

P30T2_REFIT = Path("/var/tmp/p30t2_stage/part_refit.json")
P30T2_VERIFY = Path("/var/tmp/p30t2_stage/verified_inputs.npz")
P23T2_LOSSES = Path("/var/tmp/p23t2_stage/losses.npz")
P23T4_WITH = Path("/var/tmp/p23t4_stage/losses_with_actions.npz")

DRIVERS = ("rate", "equity", "credit", "lapse", "mortality", "fx",
           "liquidity")

needs_stage = pytest.mark.skipif(
    not (P30T2_REFIT.exists() and P30T2_VERIFY.exists()
         and P23T2_LOSSES.exists() and P23T4_WITH.exists()),
    reason="P30T2/P23 stage artefacts not present in this environment",
)


def _small_bootstrap(n_replicates=3, n_sim=2_000):
    z = np.load(P23T2_LOSSES)
    w = np.load(P23T4_WITH)
    s = np.load(P30T2_VERIFY)
    fit3 = tree3_vine_fit_from_dict(
        json.loads(P30T2_REFIT.read_text(encoding="utf-8"))["fit3"])
    losses = {k: np.asarray(z[k], dtype=float) for k in DRIVERS}
    anchors = {k: float(w[k + "_anchor_mean"][0]) for k in DRIVERS}
    return tree3_margin_bootstrap(
        losses_without=losses,
        correlation=np.asarray(s["rho"], float),
        rule=ManagementActionRule(),
        l_fit=float(w["l_fit"][0]),
        anchor_means=anchors,
        fit3=fit3,
        sigma=float(s["sigma"][0]),
        alpha=float(s["alpha"][0]),
        benefit_share=float(s["beta_fit"][0]),
        n_replicates=n_replicates,
        n_sim=n_sim,
        master_seed=TREE3_BOOTSTRAP_MASTER_SEED,
    )


def test_design_constants():
    assert TREE3_BOOTSTRAP_REPLICATES >= 200
    assert TREE3_BOOTSTRAP_N_SIM >= 20_000
    assert TREE3_CANDIDATE_COMPONENT_SCR_POINT == 42_458.5527095696
    lo, hi = P29T3_VINE2_BOOTSTRAP_CI_REFERENCE
    assert lo < hi


def test_stop_rule_outside_ci_triggers():
    sr = tree3_stop_rule_assessment(38_000.0, 44_000.0, 46_638.9)
    assert sr["nested_inside_tree3_95ci"] is False
    assert sr["stop_rule_trigger_met"] is True
    assert "Task 4" in sr["stop_rule_decision_stage"]
    assert "OUTSIDE" in sr["interpretation"]


def test_stop_rule_inside_ci_does_not_trigger():
    sr = tree3_stop_rule_assessment(38_000.0, 47_000.0, 46_638.9)
    assert sr["nested_inside_tree3_95ci"] is True
    assert sr["stop_rule_trigger_met"] is False
    assert "INSIDE" in sr["interpretation"]


def test_digest_order_independent():
    recs = [
        {"replicate_index": 1, "scr_component_tree3": 2.0,
         "scr_component_vine2": 2.0, "scr_component_frozen_t": 1.5,
         "scr_without_tree3": 3.0},
        {"replicate_index": 0, "scr_component_tree3": 1.0,
         "scr_component_vine2": 1.0, "scr_component_frozen_t": 0.5,
         "scr_without_tree3": 2.0},
    ]
    assert tree3_bootstrap_digest(recs) == tree3_bootstrap_digest(recs[::-1])


def test_fit_digest_canonical():
    d1 = {"a": 1, "b": [1, 2]}
    d2 = {"b": [1, 2], "a": 1}
    assert tree3_fit_digest(d1) == tree3_fit_digest(d2)


def test_use_restrictions_shape():
    u = tree3_bootstrap_use_restrictions()
    assert u["classification"] == "EDUCATIONAL"
    assert len(u["restrictions"]) >= 4
    assert any("zero" in r for r in u["restrictions"])


def test_third_tree_edges_pre_registered():
    assert len(THIRD_TREE_EDGES) == 4


@needs_stage
def test_small_bootstrap_crn_identity_and_chunking():
    res = _small_bootstrap(n_replicates=3, n_sim=2_000)
    recs = res["records"]
    assert len(recs) == 3
    for r in recs:
        # zero-strength tree-3 layer: tree-3 == 2-tree vine EXACTLY
        assert r["tree3_minus_vine2"] == 0.0
        assert r["scr_component_tree3"] == r["scr_component_vine2"]
        assert r["scr_component_tree3"] > 0.0
        assert r["scr_component_frozen_t"] > 0.0
    # chunk-independence: replicate 1 alone == replicate 1 of the full run
    z = np.load(P23T2_LOSSES)
    w = np.load(P23T4_WITH)
    s = np.load(P30T2_VERIFY)
    fit3 = tree3_vine_fit_from_dict(
        json.loads(P30T2_REFIT.read_text(encoding="utf-8"))["fit3"])
    losses = {k: np.asarray(z[k], dtype=float) for k in DRIVERS}
    anchors = {k: float(w[k + "_anchor_mean"][0]) for k in DRIVERS}
    solo = tree3_margin_bootstrap(
        losses_without=losses, correlation=np.asarray(s["rho"], float),
        rule=ManagementActionRule(), l_fit=float(w["l_fit"][0]),
        anchor_means=anchors, fit3=fit3, sigma=float(s["sigma"][0]),
        alpha=float(s["alpha"][0]), benefit_share=float(s["beta_fit"][0]),
        n_replicates=3, n_sim=2_000,
        master_seed=TREE3_BOOTSTRAP_MASTER_SEED,
        replicate_start=1, replicate_stop=2)
    assert solo["records"][0]["scr_component_tree3"] == \
        recs[1]["scr_component_tree3"]
    assert solo["records"][0]["cop_seed"] == recs[1]["cop_seed"]


@needs_stage
def test_small_bootstrap_idempotent_digest():
    a = _small_bootstrap(n_replicates=2, n_sim=1_000)
    b = _small_bootstrap(n_replicates=2, n_sim=1_000)
    assert tree3_bootstrap_digest(a["records"]) == \
        tree3_bootstrap_digest(b["records"])


@needs_stage
def test_archived_report_consistency():
    rep_path = Path("docs/validation/"
                    "PHASE30_TASK3_TREE3_MARGIN_BOOTSTRAP_REPORT.json")
    if not rep_path.exists():
        pytest.skip("archived report not present")
    rep = json.loads(rep_path.read_text(encoding="utf-8"))
    r = rep["result"]
    assert rep["verdict"] == "PASS"
    assert r["config"]["n_replicates"] >= 200
    assert r["se_gate_pass"] is True
    assert r["tree3_minus_vine2_all_exactly_zero"] is True
    sr = r["stop_rule_assessment"]
    assert sr["stop_rule_trigger_met"] == \
        (not r["headline_nested_inside_95ci"])
    ct = r["tree3_component_scr_ci"]
    assert ct["ci_lo"] < ct["mean"] < ct["ci_hi"]
