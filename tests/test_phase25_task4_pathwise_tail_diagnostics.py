"""Tests for Phase 25 Task 4 -- path-wise tail diagnostics + delta matrix.

Covers the pathwise_tail_diagnostics module on small synthetic data plus
consistency checks of the published Task 4 report (if present).
EDUCATIONAL ONLY.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from par_model_v2.projection.inner_path_action_dynamics import (
    apply_pathwise_declaration_node,
)
from par_model_v2.projection.joint_action_aggregation import (
    JointActionAggregator,
)
from par_model_v2.projection.management_actions import ManagementActionRule
from par_model_v2.projection.nested_stochastic_tvog import (
    capital_metrics_from_liabilities,
)
from par_model_v2.projection.pathwise_proxy_basis import (
    smoothed_relief_response,
)
from par_model_v2.projection.pathwise_tail_diagnostics import (
    PATHWISE_DISCLOSURE_THRESHOLD,
    PW_BOOTSTRAP_N_SIM,
    PW_BOOTSTRAP_REPLICATES,
    PW_CONFIDENCE_SWEEP,
    PW_CONVERGENCE_PREFIXES,
    PW_SEED_STABILITY_SEEDS,
    build_pathwise_delta_matrix,
    pathwise_bootstrap_margin_ci,
    pathwise_confidence_sweep,
    pathwise_diagnostics_digest,
    pathwise_joint_readout,
    pathwise_joint_with_actions,
    pathwise_prefix_convergence,
    pathwise_seed_stability,
    pathwise_tail_use_restrictions,
)

REPORT = Path("docs/validation/PHASE25_TASK4_PATHWISE_TAIL_DIAGNOSTICS_REPORT.json")

SIGMA = 0.225
ALPHA = 0.7567
BETA = 0.845


@pytest.fixture(scope="module")
def rule():
    return ManagementActionRule()


@pytest.fixture(scope="module")
def agg(rule):
    rng = np.random.default_rng(7)
    n = 80
    l_fit = 100_000.0
    losses = {
        "d1": np.exp(rng.normal(np.log(15_000.0), 0.5, n)),
        "d2": np.exp(rng.normal(np.log(12_000.0), 0.6, n)),
    }
    R = np.array([[1.0, 0.5], [0.5, 1.0]])
    return JointActionAggregator(
        standalone_losses=losses, correlation=R, rule=rule, l_fit=l_fit)


class TestPathwiseJointWithActions:
    def test_relief_reduces_liability(self, rule, agg):
        V = np.linspace(80_000.0, 220_000.0, 512)
        out = pathwise_joint_with_actions(
            rule, V, agg.a_ref, SIGMA, ALPHA, BETA)
        W = out["W"]
        assert np.all(W <= V + 1e-9)
        assert np.all(W >= V * (1.0 - rule.max_relief) - 1e-9)

    def test_envelope_guard_identical_transform(self, rule, agg):
        V = np.linspace(80_000.0, 220_000.0, 256)
        b_hat = BETA * V
        cr = rule.coverage_ratio(V, agg.a_ref)
        relieved = ALPHA * smoothed_relief_response(rule, cr, SIGMA) \
            * np.clip(b_hat, 0.0, V)
        W_ref, _ = apply_pathwise_declaration_node(rule, V, b_hat, relieved)
        out = pathwise_joint_with_actions(
            rule, V, agg.a_ref, SIGMA, ALPHA, BETA)
        np.testing.assert_allclose(out["W"], W_ref, rtol=0, atol=1e-12)

    def test_relieved_nonnegative_and_active_share(self, rule, agg):
        V = np.linspace(80_000.0, 220_000.0, 256)
        out = pathwise_joint_with_actions(
            rule, V, agg.a_ref, SIGMA, ALPHA, BETA)
        assert np.all(np.asarray(out["relieved"]) >= -1e-12)
        assert 0.0 <= out["active_share"] <= 1.0

    def test_sigma_zero_recovers_raw_relief_on_benefit_base(self, rule, agg):
        V = np.linspace(80_000.0, 220_000.0, 128)
        out = pathwise_joint_with_actions(
            rule, V, agg.a_ref, 0.0, 1.0, BETA)
        cr = rule.coverage_ratio(V, agg.a_ref)
        expected = V - np.minimum(
            rule.relief_fraction(cr) * BETA * V,
            rule.max_relief * BETA * V)
        np.testing.assert_allclose(out["W"], expected, rtol=0, atol=1e-9)

    def test_monotone_in_liability(self, rule, agg):
        V = np.linspace(60_000.0, 260_000.0, 20_001)
        W = pathwise_joint_with_actions(
            rule, V, agg.a_ref, SIGMA, ALPHA, BETA)["W"]
        assert np.all(np.diff(W) >= -1e-9)

    def test_invalid_benefit_share_raises(self, rule, agg):
        V = np.array([100_000.0])
        for bad in (0.0, -0.1, 1.5):
            with pytest.raises(ValueError):
                pathwise_joint_with_actions(
                    rule, V, agg.a_ref, SIGMA, ALPHA, bad)

    def test_nonpositive_levels_raise(self, rule, agg):
        with pytest.raises(ValueError):
            pathwise_joint_with_actions(
                rule, np.array([-1.0, 100.0]), agg.a_ref, SIGMA, ALPHA, BETA)


class TestPathwiseJointReadout:
    def test_keys_and_finite(self, agg):
        r = pathwise_joint_readout(agg, 4000, 11, 3.0, SIGMA, ALPHA, BETA)
        for k in ("var_pathwise", "es_pathwise", "scr_pathwise",
                  "var_horizon", "scr_horizon", "var_without",
                  "scr_without", "digest"):
            assert k in r
        assert np.isfinite(r["scr_pathwise"])

    def test_pathwise_relieves_less_than_horizon_in_tail(self, agg):
        # alpha < 1 and smoothing cap mean the path-wise basis keeps more
        # liability in the deep tail than the saturated horizon rule.
        r = pathwise_joint_readout(agg, 8000, 11, 3.0, SIGMA, ALPHA, BETA)
        assert r["scr_pathwise"] >= r["scr_horizon"] - 1e-9
        assert r["var_pathwise"] >= r["var_horizon"] - 1e-9

    def test_with_actions_below_without(self, agg):
        r = pathwise_joint_readout(agg, 4000, 11, 3.0, SIGMA, ALPHA, BETA)
        assert r["var_pathwise"] <= r["var_without"] + 1e-9
        assert r["scr_pathwise"] <= r["scr_without"] + 1e-9

    def test_digest_deterministic_and_seed_sensitive(self, agg):
        r1 = pathwise_joint_readout(agg, 2000, 11, 3.0, SIGMA, ALPHA, BETA)
        r2 = pathwise_joint_readout(agg, 2000, 11, 3.0, SIGMA, ALPHA, BETA)
        r3 = pathwise_joint_readout(agg, 2000, 12, 3.0, SIGMA, ALPHA, BETA)
        assert r1["digest"] == r2["digest"]
        assert r1["digest"] != r3["digest"]
        assert r1["scr_pathwise"] == r2["scr_pathwise"]

    def test_gaussian_branch(self, agg):
        r = pathwise_joint_readout(agg, 2000, 11, None, SIGMA, ALPHA, BETA)
        assert r["config"]["copula"] == "gaussian"
        assert np.isfinite(r["scr_pathwise"])

    def test_crn_horizon_matches_aggregator_run(self, agg):
        from par_model_v2.projection.joint_action_aggregation import (
            JointActionConfig,
        )
        r = pathwise_joint_readout(agg, 4000, 11, 3.0, SIGMA, ALPHA, BETA)
        res = agg.run(JointActionConfig(n_sim=4000, seed=11, df=3.0))
        assert abs(r["scr_horizon"] - res.scr_joint_with) < 1e-9


class TestConfidenceSweep:
    @pytest.fixture(scope="class")
    def sweep(self, agg):
        return pathwise_confidence_sweep(
            agg, 8000, 11, 3.0, SIGMA, ALPHA, BETA,
            confidences=(0.90, 0.95, 0.99, 0.995))

    def test_row_count_and_keys(self, sweep):
        assert len(sweep) == 4
        for r in sweep:
            for k in ("confidence", "var_pathwise", "scr_pathwise",
                      "scr_horizon", "tail_active_share",
                      "tail_saturation_share",
                      "tail_mean_smoothed_relief_fraction",
                      "relief_at_var_pathwise",
                      "pathwise_minus_horizon_scr"):
                assert k in r

    def test_var_monotone_in_confidence(self, sweep):
        for a, b in zip(sweep, sweep[1:]):
            assert a["var_pathwise"] <= b["var_pathwise"] + 1e-9

    def test_shares_in_unit_interval(self, sweep):
        for r in sweep:
            assert 0.0 <= r["tail_saturation_share"] \
                <= r["tail_active_share"] <= 1.0

    def test_smoothed_fraction_below_max_relief(self, sweep, rule):
        for r in sweep:
            assert r["tail_mean_smoothed_relief_fraction"] \
                <= rule.max_relief + 1e-12

    def test_pathwise_scr_ge_horizon_scr(self, sweep):
        for r in sweep:
            assert r["scr_pathwise"] >= r["scr_horizon"] - 1e-9


class TestPrefixConvergenceAndSeeds:
    def test_prefix_rows_and_final_zero_delta(self, agg):
        rows = pathwise_prefix_convergence(
            agg, 11, 3.0, SIGMA, ALPHA, BETA, prefixes=(1000, 2000, 4000))
        assert [r["n_sim"] for r in rows] == [1000, 2000, 4000]
        assert rows[-1]["scr_rel_delta_vs_full"] < 1e-12
        for r in rows:
            assert r["var_rel_delta_vs_full"] >= 0.0

    def test_seed_stability_structure(self, agg):
        out = pathwise_seed_stability(
            agg, 3.0, 2000, SIGMA, ALPHA, BETA, seeds=(11, 12, 13))
        assert len(out["rows"]) == 3
        assert out["scr_max_rel_spread"] >= 0.0
        assert np.isfinite(out["scr_mean"])


class TestBootstrap:
    def test_bootstrap_structure_and_ci_order(self, agg, rule):
        losses = {k: v for k, v in agg.losses.items()}
        boot = pathwise_bootstrap_margin_ci(
            losses_without=losses, correlation=agg.correlation, rule=rule,
            l_fit=agg.l_fit, anchor_means=agg.anchor_means, df=3.0,
            sigma=SIGMA, alpha=ALPHA, benefit_share=BETA,
            n_replicates=8, n_sim=1500, seed=99)
        assert boot["n_replicates"] == 8
        assert boot["n_obs"] == 80
        for k in ("var_pathwise", "es_pathwise", "scr_pathwise"):
            ci = boot[k]
            assert ci["ci_lo_95"] <= ci["mean"] <= ci["ci_hi_95"]
            assert ci["se"] >= 0.0
        assert "frozen" in boot["resampling"]

    def test_bootstrap_deterministic_given_seed(self, agg, rule):
        losses = {k: v for k, v in agg.losses.items()}
        kw = dict(losses_without=losses, correlation=agg.correlation,
                  rule=rule, l_fit=agg.l_fit,
                  anchor_means=agg.anchor_means, df=3.0, sigma=SIGMA,
                  alpha=ALPHA, benefit_share=BETA, n_replicates=4,
                  n_sim=1500, seed=99)
        b1 = pathwise_bootstrap_margin_ci(**kw)
        b2 = pathwise_bootstrap_margin_ci(**kw)
        assert b1["scr_pathwise"]["mean"] == b2["scr_pathwise"]["mean"]


class TestDeltaMatrix:
    @pytest.fixture(scope="class")
    def matrix(self):
        without = {
            "nested": {"var": 170.0, "es": 175.0, "scr": 55.0},
            "t_copula": {"var": 160.0, "es": 165.0, "scr": 47.0},
            "gaussian": {"var": 150.0, "es": 155.0, "scr": 41.0},
            "var_covar": {"var": None, "es": None, "scr": 29.0},
        }
        hz = {
            "nested": {"var": 153.0, "es": 158.0, "scr": 41.0},
            "t_copula": {"var": 144.0, "es": 148.0, "scr": 31.0},
            "gaussian": {"var": 138.0, "es": 141.0, "scr": 26.0},
            "var_covar": {"var": None, "es": None, "scr": 14.0},
        }
        pw = {
            "nested": {"var": 159.0, "es": 163.0, "scr": 47.0},
            "t_copula": {"var": 152.0, "es": 157.0, "scr": 40.0},
            "gaussian": {"var": 147.0, "es": 152.0, "scr": 35.0},
            "var_covar": {"var": None, "es": None, "scr": None},
        }
        return build_pathwise_delta_matrix(without, hz, pw)

    def test_levels_complete(self, matrix):
        assert set(matrix) == {"nested", "t_copula", "gaussian", "var_covar"}

    def test_delta_arithmetic(self, matrix):
        row = matrix["t_copula"]
        d = row["with_pathwise_minus_without"]
        assert d["scr_delta"] == pytest.approx(40.0 - 47.0)
        d2 = row["pathwise_minus_horizon"]
        assert d2["scr_delta"] == pytest.approx(9.0)
        assert d2["scr_delta_pct"] == pytest.approx(9.0 / 31.0)

    def test_none_handling_var_covar(self, matrix):
        row = matrix["var_covar"]
        assert row["with_pathwise"]["scr"] is None
        assert "scr_delta" not in row.get("pathwise_minus_horizon", {})
        assert row["with_horizon_minus_without"]["scr_delta"] \
            == pytest.approx(14.0 - 29.0)

    def test_nested_pathwise_vs_horizon_positive(self, matrix):
        d = matrix["nested"]["pathwise_minus_horizon"]
        assert d["scr_delta"] > 0  # path-wise relieves less


class TestConstantsAndRestrictions:
    def test_diagnostic_constants_match_p24t4_conventions(self):
        assert PW_CONFIDENCE_SWEEP == (0.90, 0.95, 0.99, 0.995, 0.999)
        assert PW_CONVERGENCE_PREFIXES == (25_000, 50_000, 100_000, 200_000)
        assert PW_SEED_STABILITY_SEEDS[0] == 20260607
        assert PW_BOOTSTRAP_REPLICATES == 200
        assert PW_BOOTSTRAP_N_SIM == 20_000
        assert PATHWISE_DISCLOSURE_THRESHOLD == 0.01

    def test_use_restrictions(self):
        r = pathwise_tail_use_restrictions()
        assert r["classification"] == "EDUCATIONAL_DEMONSTRATION_ONLY"
        assert any("re-anchoring" in u for u in [r["rationale"]])
        assert len(r["prohibited_uses"]) >= 3

    def test_digest_deterministic(self):
        p = {"a": 1.0, "b": [1, 2, 3]}
        assert pathwise_diagnostics_digest(p) \
            == pathwise_diagnostics_digest(dict(p))
        assert pathwise_diagnostics_digest({"a": 2.0}) \
            != pathwise_diagnostics_digest({"a": 1.0})


@pytest.mark.skipif(not REPORT.exists(), reason="Task 4 report not built")
class TestPublishedReport:
    @pytest.fixture(scope="class")
    def rep(self):
        return json.loads(REPORT.read_text(encoding="utf-8"))

    def test_verdict_pass_and_gates(self, rep):
        assert rep["verdict"] == "PASS"
        assert all(rep["gates"].values())
        assert set(rep["gates"]) == {
            "G1_delta_matrix_complete_and_crosschecked",
            "G2_var_covar_understatement_refreshed_pathwise",
            "G3_df_rank_invariance_copula_frozen",
            "G4_reproducibility_recorded",
        }

    def test_rank_invariance_frozen(self, rep):
        assert abs(rep["df_rematched"] - 2.9451) <= 5e-5
        assert rep["rho_max_abs_diff_vs_archived"] < 1e-6

    def test_p24t2_reproduced_bit_identically(self, rep):
        repro = rep["reproduction_of_p24t2_horizon_basis"]
        assert repro["t_digest_match"] and repro["g_digest_match"]
        assert repro["t_scr_abs_diff"] < 1e-9
        assert repro["g_scr_abs_diff"] < 1e-9

    def test_nested_row_matches_p25t2_archive(self, rep):
        p25t2 = json.loads(Path(
            "docs/validation/PHASE25_TASK2_PATHWISE_DECLARATION_REPORT.json"
        ).read_text(encoding="utf-8"))["result"]
        nrow = rep["delta_matrix"]["nested"]
        assert nrow["with_pathwise"]["scr"] == pytest.approx(
            p25t2["nested_capital_with_pathwise"]["scr_proxy"], abs=1e-6)
        assert nrow["with_horizon"]["scr"] == pytest.approx(
            p25t2["nested_capital_with_horizon"]["scr_proxy"], abs=1e-6)
        assert nrow["without"]["scr"] == pytest.approx(
            p25t2["nested_capital_without"]["scr_proxy"], abs=1e-6)

    def test_mr_refresh_trigger_met(self, rep):
        t = rep["mr_refresh_trigger"]
        assert t["met"] is True
        assert t["nested_scr_delta_rel_to_horizon"] \
            == pytest.approx(0.14165, abs=5e-4)

    def test_pathwise_relieves_less_at_every_level(self, rep):
        m = rep["delta_matrix"]
        for lv in ("nested", "t_copula", "gaussian"):
            d = m[lv]["pathwise_minus_horizon"]
            assert d["scr_delta"] > 0.0

    def test_sigma_alpha_match_p25t3_archive(self, rep):
        p25t3 = json.loads(Path(
            "docs/validation/PHASE25_TASK3_PATHWISE_PROXY_BASIS_REPORT.json"
        ).read_text(encoding="utf-8"))["result"]
        surf = p25t3["surface_calibration_fit_only"]
        p = rep["pathwise_basis_params"]
        assert p["sigma"] == pytest.approx(surf["sigma"], abs=1e-12)
        assert p["alpha"] == pytest.approx(surf["alpha"], abs=1e-12)
        assert 0.0 < p["benefit_share_fit"] <= 1.0

    def test_var_covar_refresh_positive_and_wider_than_horizon(self, rep):
        vc = rep["var_covar_refresh"]
        assert vc["understatement_vs_nested_with_pathwise"] > 0
        assert vc["understatement_vs_t_pathwise_readout"] > 0
        assert vc["understatement_vs_nested_with_pathwise"] > \
            vc["understatement_vs_nested_with_horizon_basis_p24t4"]

    def test_saturation_and_smoothed_fraction(self, rep):
        f = rep["diagnostic_findings"]
        assert 0.0 <= f["tail_saturation_share_at_995"] <= 1.0
        assert f["tail_mean_smoothed_relief_fraction_at_995"] \
            <= rep["rule"]["max_relief"] + 1e-12
        assert f["pathwise_relieves_less_at_every_confidence"] is True

    def test_bootstrap_present_with_disclosure(self, rep):
        boot = rep["tail_diagnostics"].get("bootstrap")
        if boot is None:
            pytest.skip("boot stage not yet run")
        assert boot["n_obs"] == rep["n_obs"]
        f = rep["diagnostic_findings"]
        assert "nested_pathwise_inside_bootstrap_ci" in f
        assert f["bootstrap_scr_se_pct_of_mean"] > 0
