"""Tests for the Phase 23 Task 2 tail-matched t-copula aggregation."""
import json
from pathlib import Path

import numpy as np
import pytest
from scipy import stats

from par_model_v2.projection.nested_stochastic_tvog import (
    capital_metrics_from_liabilities,
)
from par_model_v2.projection.t_copula_tail_matched_aggregation import (
    DEFAULT_REL_ERROR_TOLERANCE,
    DEFAULT_THRESHOLDS,
    TailMatchedTCopulaAggregator,
    TCopulaAggregationConfig,
    simulate_t_copula_uniforms,
    t_copula_aggregation_use_restrictions,
)
from par_model_v2.projection.tail_dependence import t_copula_upper_tail_dependence

REPORT = Path("docs/validation/PHASE23_TASK2_T_COPULA_AGGREGATION_REPORT.json")


def _synthetic(df, n, seed=7, d=3, rho=0.55):
    rng = np.random.default_rng(seed)
    R = np.full((d, d), rho); np.fill_diagonal(R, 1.0)
    if np.isinf(df):
        Z = rng.standard_normal((n, d)) @ np.linalg.cholesky(R).T
        U = stats.norm.cdf(Z)
    else:
        U = simulate_t_copula_uniforms(rng, n, R, df)
    L = stats.lognorm.ppf(U, 0.7) * 1000.0
    return L


def _agg_for(L, **cfg_kw):
    nested = capital_metrics_from_liabilities(L.sum(axis=1), 0.995, 12).scr_proxy
    agg = TailMatchedTCopulaAggregator(
        [L[:, j] for j in range(L.shape[1])],
        [f"d{j}" for j in range(L.shape[1])],
        nested_scr=nested, var_covar_scr=0.6 * nested,
    )
    return agg, TCopulaAggregationConfig(n_sim=8000, **cfg_kw)


# ---------------------------------------------------------------- sampler ---

class TestTCopulaSampler:
    def test_shape_and_range(self):
        rng = np.random.default_rng(0)
        R = np.eye(2)
        U = simulate_t_copula_uniforms(rng, 500, R, 4.0)
        assert U.shape == (500, 2)
        assert np.all((U > 0) & (U < 1))

    def test_margins_uniform(self):
        rng = np.random.default_rng(1)
        R = np.array([[1.0, 0.5], [0.5, 1.0]])
        U = simulate_t_copula_uniforms(rng, 20000, R, 5.0)
        for j in range(2):
            p = stats.kstest(U[:, j], "uniform").pvalue
            assert p > 0.01

    def test_dependence_sign(self):
        rng = np.random.default_rng(2)
        R = np.array([[1.0, 0.7], [0.7, 1.0]])
        U = simulate_t_copula_uniforms(rng, 5000, R, 4.0)
        tau = stats.kendalltau(U[:, 0], U[:, 1]).statistic
        # tau = 2/pi * arcsin(rho) ~ 0.494 for rho=0.7
        assert abs(tau - 2.0 / np.pi * np.arcsin(0.7)) < 0.05

    def test_invalid_df_raises(self):
        with pytest.raises(ValueError):
            simulate_t_copula_uniforms(np.random.default_rng(0), 10, np.eye(2), 0.0)


# ----------------------------------------------------------------- config ---

class TestConfigValidation:
    def test_defaults_valid(self):
        cfg = TCopulaAggregationConfig()
        assert cfg.thresholds == DEFAULT_THRESHOLDS
        assert cfg.rel_error_tolerance == DEFAULT_REL_ERROR_TOLERANCE

    @pytest.mark.parametrize("kw", [
        {"thresholds": (0.8, 0.9)},                 # < 3 thresholds
        {"thresholds": (0.4, 0.8, 0.9)},            # out of range
        {"thresholds": (0.8, 0.8, 0.9)},            # duplicates
        {"n_sim": 10},
        {"confidence_level": 1.5},
        {"capital_horizon_months": 0},
        {"rel_error_tolerance": -0.1},
        {"df_lo": 5.0, "df_hi": 2.0},
    ])
    def test_invalid_configs_raise(self, kw):
        with pytest.raises(ValueError):
            TCopulaAggregationConfig(**kw)

    def test_to_dict_round_trip(self):
        d = TCopulaAggregationConfig().to_dict()
        assert json.loads(json.dumps(d)) == d


# ------------------------------------------------------------- aggregator ---

class TestAggregatorValidation:
    def test_needs_two_vectors(self):
        with pytest.raises(ValueError):
            TailMatchedTCopulaAggregator([np.ones(10)], ["a"], 1.0, 1.0)

    def test_driver_name_mismatch(self):
        with pytest.raises(ValueError):
            TailMatchedTCopulaAggregator(
                [np.ones(10), np.ones(10)], ["a"], 1.0, 1.0)


class TestSyntheticRecovery:
    def test_heavy_tail_t_beats_or_matches_gaussian(self):
        L = _synthetic(df=3.0, n=2000, seed=11)
        agg, cfg = _agg_for(L, seed=101)
        rep = agg.run(cfg)
        assert rep.verdict == "PASS"
        assert (rep.t_matched_rel_error_vs_nested
                <= rep.gaussian_rel_error_vs_nested + 1e-12) or (
                rep.t_matched_rel_error_vs_nested <= cfg.rel_error_tolerance)
        # matched df should be finite-tail (well below the cap)
        assert rep.df_matched < 50.0

    def test_gaussian_losses_show_rising_df_signature(self):
        # Design-note diagnostic: for Gaussian dependence (zero asymptotic
        # tail dependence) the finite-threshold matched df RISES as the
        # threshold tightens, and sits at or above the matched df of a
        # genuinely heavy-tailed t(3) sample with the same margins/seed.
        Lg = _synthetic(df=np.inf, n=2000, seed=12)
        agg_g, cfg = _agg_for(Lg, seed=102)
        rep_g = agg_g.run(cfg)
        dfs_g = [r.pooled_df for r in rep_g.sensitivity]
        assert dfs_g == sorted(dfs_g)  # rising-df signature
        Lt = _synthetic(df=3.0, n=2000, seed=12)
        agg_t, cfg_t = _agg_for(Lt, seed=102)
        rep_t = agg_t.run(cfg_t)
        assert rep_g.df_matched >= rep_t.df_matched  # ordering vs heavy tail

    def test_sensitivity_table_complete(self):
        L = _synthetic(df=4.0, n=800, seed=13)
        agg, cfg = _agg_for(L, seed=103)
        rep = agg.run(cfg)
        assert len(rep.sensitivity) == len(cfg.thresholds)
        for row in rep.sensitivity:
            assert 0.0 <= row.capped_share <= 1.0
            assert row.pooled_df > 0
            assert row.expected_tail_obs == pytest.approx(
                800 * (1 - row.threshold))

    def test_small_tail_obs_disclosure(self):
        L = _synthetic(df=4.0, n=50, seed=14)
        agg, cfg = _agg_for(L, seed=104)
        rep = agg.run(cfg)
        assert any("DISCLOSURE" in n and "joint-tail" in n for n in rep.notes)

    def test_verdict_consistent_with_fixed_gate(self):
        L = _synthetic(df=4.0, n=800, seed=15)
        agg, cfg = _agg_for(L, seed=105)
        rep = agg.run(cfg)
        expect_pass = (
            rep.t_matched_rel_error_vs_nested
            <= rep.gaussian_rel_error_vs_nested + 1e-12
        ) or (rep.t_matched_rel_error_vs_nested <= cfg.rel_error_tolerance)
        assert rep.verdict == ("PASS" if expect_pass else "PARTIAL")
        assert "25%" in rep.gate

    def test_reproducible_same_seed(self):
        L = _synthetic(df=4.0, n=400, seed=16)
        agg, cfg = _agg_for(L, seed=106)
        r1, r2 = agg.run(cfg), agg.run(cfg)
        assert r1.t_matched_scr == r2.t_matched_scr
        assert r1.gaussian_scr == r2.gaussian_scr
        assert r1.reproducibility_digest == r2.reproducibility_digest

    def test_digest_changes_with_seed(self):
        L = _synthetic(df=4.0, n=400, seed=17)
        agg, _ = _agg_for(L)
        r1 = agg.run(TCopulaAggregationConfig(n_sim=8000, seed=1))
        r2 = agg.run(TCopulaAggregationConfig(n_sim=8000, seed=2))
        assert r1.reproducibility_digest != r2.reproducibility_digest

    def test_implied_lambda_matrix_properties(self):
        L = _synthetic(df=4.0, n=800, seed=18)
        agg, cfg = _agg_for(L, seed=107)
        rep = agg.run(cfg)
        M = np.asarray(rep.implied_lambda_matrix)
        assert np.allclose(M, M.T)
        assert np.allclose(np.diag(M), 1.0)
        off = M[~np.eye(M.shape[0], dtype=bool)]
        assert np.all((off >= 0.0) & (off <= 1.0))
        # closed-form consistency at one pair
        rho = np.asarray(rep.rho_matrix)
        assert M[0, 1] == pytest.approx(
            t_copula_upper_tail_dependence(
                rep.df_matched, float(np.clip(rho[0, 1], -0.999, 0.999))),
            abs=1e-5)  # report matrix is rounded to 6 dp

    def test_report_json_serialisable(self):
        L = _synthetic(df=4.0, n=400, seed=19)
        agg, cfg = _agg_for(L, seed=108)
        rep = agg.run(cfg)
        blob = rep.to_json()
        d = json.loads(blob)
        assert d["verdict"] in ("PASS", "PARTIAL")
        assert len(d["threshold_sensitivity"]) == 3
        assert d["n_obs"] == 400


# ---------------------------------------------------------- use restricts ---

def test_use_restrictions_block():
    r = t_copula_aggregation_use_restrictions()
    assert r["classification"] == "EDUCATIONAL"
    assert any("Regulatory" in p for p in r["prohibited_uses"])
    assert len(r["key_limitations"]) >= 3


# ------------------------------------------------------- evidence report ---

@pytest.mark.skipif(not REPORT.exists(), reason="evidence report not built")
class TestEvidenceReport:
    def test_real_run_verdict_and_disclosures(self):
        rep = json.loads(REPORT.read_text(encoding="utf-8"))
        d = rep["aggregation"]
        assert d["verdict"] == "PASS"
        assert len(d["threshold_sensitivity"]) >= 3
        assert d["drivers"] == ["rate", "equity", "credit", "lapse",
                                "mortality", "fx", "liquidity"]
        assert d["n_obs"] == 160
        # fixed gate honoured
        ok = (d["t_matched_rel_error_vs_nested"]
              <= d["gaussian_rel_error_vs_nested"] + 1e-12) or (
              d["t_matched_rel_error_vs_nested"]
              <= d["config"]["rel_error_tolerance"])
        assert ok
        # tail-matched t must carry MORE upper-tail dependence than gaussian (0)
        M = np.asarray(d["implied_lambda_matrix"])
        assert M[~np.eye(M.shape[0], dtype=bool)].max() > 0.0

    def test_real_run_benchmarks_consistent(self):
        rep = json.loads(REPORT.read_text(encoding="utf-8"))
        d = rep["aggregation"]
        # nested/var-covar must match the Phase 22 Task 4 archived run
        arch = json.loads(Path(
            "docs/validation/PHASE22_TASK4_AGGREGATION_REPORT.json"
        ).read_text(encoding="utf-8"))["aggregation"]
        assert d["nested_scr"] == pytest.approx(arch["nested_scr"], abs=1e-3)
        assert d["var_covar_scr"] == pytest.approx(arch["var_covar_scr"], abs=1e-3)  # 4-dp rounding
        # capped share disclosed
        assert 0.0 <= d["df_matched_capped_share"] <= 1.0
