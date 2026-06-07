"""Tests for par_model_v2/projection/tail_dependence.py (Phase 23 Task 1)."""
import numpy as np
import pytest
from scipy import stats

from par_model_v2.projection.tail_dependence import (
    DF_HI_DEFAULT,
    DF_LO_DEFAULT,
    TailDependenceMatch,
    empirical_upper_tail_dependence,
    implied_t_df_from_tail_dependence,
    match_t_df_to_losses,
    pairwise_upper_tail_dependence,
    t_copula_upper_tail_dependence,
)


def _t_copula_sample(n, rho, df, seed):
    """Bivariate t-copula pseudo-observations via the standard construction."""
    rng = np.random.default_rng(seed)
    z = rng.multivariate_normal([0, 0], [[1, rho], [rho, 1]], size=n)
    w = rng.chisquare(df, size=n) / df
    x = z / np.sqrt(w)[:, None]
    return stats.t.cdf(x, df)


class TestClosedForm:
    def test_known_value_demarta_mcneil(self):
        # nu=4, rho=0.5: arg=-sqrt(5*0.5/1.5)=-sqrt(5/3); lambda=2*t5.cdf(-1.29099)
        expected = 2.0 * stats.t.cdf(-np.sqrt(5.0 / 3.0), 5)
        assert t_copula_upper_tail_dependence(4.0, 0.5) == pytest.approx(expected, abs=1e-12)

    def test_gaussian_limit_zero(self):
        assert t_copula_upper_tail_dependence(1e6, 0.5) < 1e-6

    def test_rho_one_gives_one(self):
        assert t_copula_upper_tail_dependence(4.0, 1.0) == 1.0

    def test_monotone_decreasing_in_df(self):
        lams = [t_copula_upper_tail_dependence(df, 0.5) for df in (2, 4, 8, 30, 100)]
        assert all(a > b for a, b in zip(lams, lams[1:]))

    def test_monotone_increasing_in_rho(self):
        lams = [t_copula_upper_tail_dependence(4.0, r) for r in (-0.5, 0.0, 0.3, 0.7, 0.95)]
        assert all(a < b for a, b in zip(lams, lams[1:]))

    def test_negative_rho_still_positive_lambda(self):
        # t-copula has tail dependence even at negative rho (finite df)
        assert t_copula_upper_tail_dependence(4.0, -0.5) > 0.0

    def test_invalid_inputs_raise(self):
        with pytest.raises(ValueError):
            t_copula_upper_tail_dependence(0.0, 0.5)
        with pytest.raises(ValueError):
            t_copula_upper_tail_dependence(4.0, -1.0)


class TestInversion:
    def test_round_trip(self):
        for df_true in (2.0, 5.0, 12.0, 40.0):
            for rho in (-0.3, 0.0, 0.4, 0.8):
                lam = t_copula_upper_tail_dependence(df_true, rho)
                df_hat, capped = implied_t_df_from_tail_dependence(lam, rho)
                assert not capped
                assert df_hat == pytest.approx(df_true, rel=1e-5)

    def test_cap_high_df_disclosed(self):
        # zero tail dependence (Gaussian) -> df pinned at upper bound, flagged
        df_hat, capped = implied_t_df_from_tail_dependence(0.0, 0.3)
        assert capped and df_hat == DF_HI_DEFAULT

    def test_cap_low_df_disclosed(self):
        df_hat, capped = implied_t_df_from_tail_dependence(0.999999, 0.0)
        assert capped and df_hat == DF_LO_DEFAULT

    def test_invalid_lambda_raises(self):
        with pytest.raises(ValueError):
            implied_t_df_from_tail_dependence(1.5, 0.3)


class TestEmpiricalEstimator:
    def test_recovers_t_copula_lambda(self):
        df_true, rho = 4.0, 0.5
        U = _t_copula_sample(200_000, rho, df_true, seed=42)
        lam_hat = empirical_upper_tail_dependence(U[:, 0], U[:, 1], 0.98)
        lam_true = t_copula_upper_tail_dependence(df_true, rho)
        # finite-threshold estimator: generous but meaningful tolerance
        assert lam_hat == pytest.approx(lam_true, abs=0.08)
        assert lam_hat > 0.15

    def test_gaussian_sample_near_zero(self):
        rng = np.random.default_rng(7)
        z = rng.multivariate_normal([0, 0], [[1, 0.5], [0.5, 1]], size=200_000)
        U = stats.norm.cdf(z)
        lam_gauss = empirical_upper_tail_dependence(U[:, 0], U[:, 1], 0.99)
        lam_t = t_copula_upper_tail_dependence(4.0, 0.5)
        assert lam_gauss < 0.5 * lam_t  # clearly separated from t(4)

    def test_independence_near_zero(self):
        rng = np.random.default_rng(11)
        u, v = rng.uniform(size=100_000), rng.uniform(size=100_000)
        assert empirical_upper_tail_dependence(u, v, 0.95) < 0.12

    def test_validation(self):
        with pytest.raises(ValueError):
            empirical_upper_tail_dependence(np.ones(3), np.ones(4))
        with pytest.raises(ValueError):
            empirical_upper_tail_dependence(np.ones(3), np.ones(3), threshold=0.4)

    def test_pairwise_matrix_symmetric_unit_diag(self):
        U = _t_copula_sample(50_000, 0.4, 5.0, seed=3)
        lam = pairwise_upper_tail_dependence(U, 0.95)
        assert lam.shape == (2, 2)
        assert np.allclose(lam, lam.T)
        assert np.allclose(np.diag(lam), 1.0)


class TestDfMatching:
    def test_recovers_df_from_synthetic_losses(self):
        df_true, rho = 4.0, 0.6
        U = _t_copula_sample(150_000, rho, df_true, seed=42)
        # arbitrary monotone marginals (lognormal losses) — rank-invariant
        L = np.column_stack([stats.lognorm.ppf(U[:, 0], 0.8),
                             stats.lognorm.ppf(U[:, 1], 1.2)])
        m = match_t_df_to_losses(L, threshold=0.98)
        assert isinstance(m, TailDependenceMatch)
        assert m.pooled_df_capped_share == 0.0
        # tail-dependence matching at finite threshold: order-of-magnitude gate
        assert 2.0 <= m.pooled_df <= 12.0

    def test_gaussian_signature_df_increases_with_threshold(self):
        # KNOWN finite-threshold bias: a Gaussian sample has lambda_hat(q) > 0
        # at any finite q (slowly decaying to 0 as q -> 1), so the implied df
        # is finite but RISES as the threshold tightens. That monotone-rising
        # df is the documented Gaussian diagnostic; a genuinely heavy-tailed
        # t(4) sample keeps an (approximately) stable low df instead.
        rng = np.random.default_rng(5)
        z = rng.multivariate_normal([0, 0], [[1, 0.5], [0.5, 1]], size=150_000)
        dfs = [match_t_df_to_losses(np.exp(z), threshold=q).pooled_df
               for q in (0.99, 0.995, 0.999)]
        assert dfs[0] < dfs[1] < dfs[2]          # rising-df Gaussian signature
        U = _t_copula_sample(150_000, 0.5, 4.0, seed=5)
        df_t = match_t_df_to_losses(U, threshold=0.995).pooled_df
        assert df_t < dfs[1]                     # t(4) reads heavier-tailed

    def test_deterministic(self):
        U = _t_copula_sample(20_000, 0.5, 6.0, seed=9)
        m1 = match_t_df_to_losses(U.copy(), threshold=0.97)
        m2 = match_t_df_to_losses(U.copy(), threshold=0.97)
        assert m1.to_dict() == m2.to_dict()

    def test_to_dict_schema(self):
        U = _t_copula_sample(5_000, 0.5, 6.0, seed=1)
        d = match_t_df_to_losses(U, threshold=0.95).to_dict()
        for key in ("threshold", "n_obs", "lambda_matrix", "rho_matrix",
                    "pairwise_df", "pooled_df", "pooled_df_capped_share", "note"):
            assert key in d

    def test_input_validation(self):
        with pytest.raises(ValueError):
            match_t_df_to_losses(np.ones((10, 1)))
