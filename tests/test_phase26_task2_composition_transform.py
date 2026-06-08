"""Phase 26 Task 2 -- per-driver composition transform unit tests."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from par_model_v2.projection.joint_action_aggregation import (
    JointActionAggregator,
)
from par_model_v2.projection.management_actions import ManagementActionRule
from par_model_v2.projection.pathwise_composition_transform import (
    CARVEOUT_DRIVERS,
    CUTTABLE_DRIVERS,
    composition_joint_readout,
    composition_transform_use_restrictions,
    composition_with_actions,
    split_joint_composition,
)
from par_model_v2.projection.pathwise_copula_reaggregation import (
    DF_REMATCH_TOL,
    FULL_REAGG_SIGN_GATE_REFERENCE,
    RANK_INVARIANCE_DF,
    RHO_FROZEN_TOL,
)
from par_model_v2.projection.pathwise_tail_diagnostics import (
    pathwise_joint_with_actions,
)

REPORT = Path("docs/validation/PHASE26_TASK2_COMPOSITION_TRANSFORM_REPORT.json")
P25T4_REPORT = Path(
    "docs/validation/PHASE25_TASK4_PATHWISE_TAIL_DIAGNOSTICS_REPORT.json")
DRIVERS = ("rate", "equity", "credit", "lapse", "mortality", "fx", "liquidity")


@pytest.fixture(scope="module")
def agg() -> JointActionAggregator:
    rng = np.random.default_rng(7)
    losses = {k: 100.0 * np.exp(0.3 * rng.standard_normal(160))
              for k in DRIVERS}
    rho = np.full((7, 7), 0.4)
    np.fill_diagonal(rho, 1.0)
    return JointActionAggregator(
        standalone_losses=losses, correlation=rho,
        rule=ManagementActionRule(), l_fit=10_000.0)


@pytest.fixture(scope="module")
def readout(agg) -> dict:
    return composition_joint_readout(
        agg, 4000, 11, 3.0, 0.225, 0.757, 0.845)


def test_carveout_partition_complete_and_disjoint():
    assert sorted(CUTTABLE_DRIVERS + CARVEOUT_DRIVERS) == sorted(DRIVERS)
    assert not set(CUTTABLE_DRIVERS) & set(CARVEOUT_DRIVERS)
    assert set(CARVEOUT_DRIVERS) == {"credit", "fx", "liquidity"}


def test_split_reconstruction_identity(agg):
    rng = np.random.default_rng(3)
    U = rng.uniform(0.001, 0.999, size=(500, 7))
    comp = split_joint_composition(agg, U)
    assert comp["reconstruction_max_abs_err"] < 1e-8
    assert comp["V"].shape == comp["V_cut"].shape == (500,)


def test_split_rejects_unknown_driver():
    rng = np.random.default_rng(5)
    losses = {k: 100.0 * np.exp(0.2 * rng.standard_normal(60))
              for k in DRIVERS + ("inflation",)}
    rho = np.eye(8)
    bad = JointActionAggregator(
        standalone_losses=losses, correlation=rho,
        rule=ManagementActionRule(), l_fit=10_000.0)
    with pytest.raises(ValueError, match="carve-out classification"):
        split_joint_composition(bad, np.full((10, 8), 0.5))


def test_component_envelope_bounds(agg):
    rng = np.random.default_rng(9)
    U = rng.uniform(0.001, 0.999, size=(2000, 7))
    comp = split_joint_composition(agg, U)
    rule = agg.rule
    pw = composition_with_actions(
        rule, comp["V"], comp["V_cut"], agg.a_ref, 0.225, 0.757, 0.845)
    b = np.asarray(pw["benefit_base"])
    relief = comp["V"] - np.asarray(pw["W"])
    assert np.all(b >= -1e-12) and np.all(b <= comp["V"] + 1e-9)
    assert np.all(relief >= -1e-9)
    assert np.all(relief <= rule.max_relief * b + 1e-9)


def test_component_relieves_no_more_than_level_when_carveout_positive(agg):
    rng = np.random.default_rng(13)
    U = rng.uniform(0.001, 0.999, size=(2000, 7))
    comp = split_joint_composition(agg, U)
    pw_c = composition_with_actions(
        agg.rule, comp["V"], comp["V_cut"], agg.a_ref, 0.225, 0.757, 0.845)
    pw_l = pathwise_joint_with_actions(
        agg.rule, comp["V"], agg.a_ref, 0.225, 0.757, 0.845)
    pos = np.asarray(comp["dev_carve"]) >= 0.0
    assert pos.any() and (~pos).any()
    w_c = np.asarray(pw_c["W"])[pos]
    w_l = np.asarray(pw_l["W"])[pos]
    assert np.all(w_c >= w_l - 1e-9)


def test_invalid_inputs_raise(agg):
    v = np.array([100.0, 200.0])
    with pytest.raises(ValueError, match="benefit_share"):
        composition_with_actions(agg.rule, v, v, agg.a_ref, 0.2, 0.7, 0.0)
    with pytest.raises(ValueError, match="misaligned"):
        composition_with_actions(
            agg.rule, v, np.array([1.0]), agg.a_ref, 0.2, 0.7, 0.8)
    with pytest.raises(ValueError, match="positive"):
        composition_with_actions(
            agg.rule, np.array([-1.0, 2.0]), v, agg.a_ref, 0.2, 0.7, 0.8)


def test_readout_structure_and_crn_level_consistency(agg, readout):
    ro = readout
    for k in ("scr_without", "scr_level", "scr_component", "digest",
              "cuttable_share_mean", "cuttable_share_tail_mean",
              "component_minus_level_scr"):
        assert k in ro
    # with-actions never exceeds without-actions; component >= level relief
    # restriction shows up as scr ordering within the with-actions pair
    assert ro["scr_level"] <= ro["scr_without"] + 1e-9
    assert ro["scr_component"] <= ro["scr_without"] + 1e-9
    assert 0.0 < ro["cuttable_share_mean"] <= 1.0
    assert ro["composition_reconstruction_max_abs_err"] < 1e-8
    assert ro["config"]["cuttable_drivers"] == list(CUTTABLE_DRIVERS)


def test_readout_idempotent_same_seed(agg, readout):
    ro2 = composition_joint_readout(
        agg, 4000, 11, 3.0, 0.225, 0.757, 0.845)
    assert ro2["digest"] == readout["digest"]
    assert ro2["scr_component"] == readout["scr_component"]
    assert ro2["scr_level"] == readout["scr_level"]


def test_gaussian_branch(agg):
    ro = composition_joint_readout(
        agg, 2000, 17, None, 0.225, 0.757, 0.845)
    assert ro["config"]["copula"] == "gaussian"
    assert ro["scr_component"] <= ro["scr_without"] + 1e-9


def test_use_restrictions_classification():
    ur = composition_transform_use_restrictions()
    assert ur["classification"] == "EDUCATIONAL"
    assert any("FROZEN" in r for r in ur["restrictions"])


@pytest.mark.skipif(not REPORT.exists(), reason="report not built yet")
class TestArchivedReport:
    @pytest.fixture(scope="class")
    def rep(self) -> dict:
        return json.loads(REPORT.read_text(encoding="utf-8"))

    def test_verdict_and_gates(self, rep):
        assert rep["verdict"] == "PASS"
        assert all(rep["result"]["gates"].values())

    def test_rank_invariance_frozen(self, rep):
        assert abs(rep["df_rematched"] - RANK_INVARIANCE_DF) <= DF_REMATCH_TOL
        assert rep["rho_max_abs_diff"] <= RHO_FROZEN_TOL

    def test_sign_gate_inequality(self, rep):
        t = rep["result"]["t_readout"]
        assert t["scr_component"] >= FULL_REAGG_SIGN_GATE_REFERENCE - 1e-9

    def test_level_variant_bit_identical_to_p25t4(self, rep):
        a = json.loads(P25T4_REPORT.read_text(encoding="utf-8"))
        t = rep["result"]["t_readout"]
        g = rep["result"]["g_readout"]
        assert t["scr_level"] == a["t_pathwise_readout"]["scr_pathwise"]
        assert g["scr_level"] == a["g_pathwise_readout"]["scr_pathwise"]
        assert t["scr_without"] == a["t_pathwise_readout"]["scr_without"]
        assert g["scr_without"] == a["g_pathwise_readout"]["scr_without"]

    def test_governed_scalars_unchanged(self, rep):
        a = json.loads(P25T4_REPORT.read_text(encoding="utf-8"))
        p = rep["pathwise_basis_params"]
        ap = a["pathwise_basis_params"]
        assert p["sigma"] == ap["sigma"]
        assert p["alpha"] == ap["alpha"]
        assert p["benefit_share_fit"] == ap["benefit_share_fit"]

    def test_partition_recorded(self, rep):
        assert rep["cuttable_drivers"] == list(CUTTABLE_DRIVERS)
        assert rep["carveout_drivers"] == list(CARVEOUT_DRIVERS)

    def test_governance_integrity_if_applied(self, rep):
        if "change_record_id" in rep:
            assert rep["change_record_status"] == "OWNER_REVIEW"
            assert rep["audit_integrity_ok"] is True
