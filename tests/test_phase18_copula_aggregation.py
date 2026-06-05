"""
Tests for Phase 18 Task 1 — copula-based, tail-dependent risk aggregation
(``par_model_v2.projection.multi_driver_copula_aggregation``).

The aggregator consumes realised standalone capital-loss vectors plus the
nested-truth and var-covar SCR benchmarks, so the tests use fast SYNTHETIC loss
vectors with a known positive dependence structure (mirroring the realised
rate/equity/credit co-movement) — no nested model run is required.
"""

import json

import numpy as np
import pytest

from par_model_v2.projection.multi_driver_copula_aggregation import (
    CopulaAggregationConfig,
    CopulaAggregationReport,
    CopulaFit,
    CopulaRiskAggregator,
    DEFAULT_COPULA_REL_ERROR_TOLERANCE,
    _EmpiricalMargin,
    _nearest_correlation,
    _pseudo_obs,
    copula_aggregation_use_restrictions,
    copula_aggregation_use_restrictions_json,
)
from par_model_v2.projection.nested_stochastic_tvog import (
    capital_metrics_from_liabilities,
)


CONF = 0.995
HM = 12


def _synthetic_losses(n=2000, seed=7):
    """Three positively-dependent, positively-skewed loss vectors."""
    rng = np.random.default_rng(seed)
    R = np.array([[1.0, 0.6, 0.78], [0.6, 1.0, 0.65], [0.78, 0.65, 1.0]])
    chol = np.linalg.cholesky(R)
    z = rng.standard_normal((n, 3)) @ chol.T
    # Map to positively-skewed losses (lognormal-style) with distinct scales.
    rate = 80_000 + 9_000 * np.exp(0.4 * z[:, 0])
    equity = 20_000 + 12_000 * np.exp(0.5 * z[:, 1])
    credit = 9_000 + 3_000 * np.exp(0.45 * z[:, 2])
    return rate, equity, credit


def _benchmarks(rate, equity, credit, factor_corr):
    def scr(x):
        return float(np.quantile(x, CONF) - x.mean())

    sv = np.array([scr(rate), scr(equity), scr(credit)])
    nested = scr(rate + equity + credit)
    var_covar = float(np.sqrt(sv @ factor_corr @ sv))
    return nested, var_covar


@pytest.fixture(scope="module")
def losses():
    return _synthetic_losses()


@pytest.fixture(scope="module")
def report(losses):
    rate, equity, credit = losses
    # Deliberately NEGATIVE factor correlation -> reproduces the MR-010 gap.
    factor = np.array([[1.0, -0.15, -0.20], [-0.15, 1.0, -0.30], [-0.20, -0.30, 1.0]])
    nested, var_covar = _benchmarks(rate, equity, credit, factor)
    agg = CopulaRiskAggregator(
        [rate, equity, credit],
        ["short_rate", "equity_guarantee", "credit_spread"],
        nested_scr=nested,
        var_covar_scr=var_covar,
    )
    return agg.run(CopulaAggregationConfig(n_sim=60_000, seed=20260605))


# --------------------------------------------------------------------------- #
# Config + helper functions
# --------------------------------------------------------------------------- #

def test_config_validation():
    with pytest.raises(ValueError):
        CopulaAggregationConfig(n_sim=10)
    with pytest.raises(ValueError):
        CopulaAggregationConfig(confidence_level=1.5)
    with pytest.raises(ValueError):
        CopulaAggregationConfig(capital_horizon_months=0)
    with pytest.raises(ValueError):
        CopulaAggregationConfig(rel_error_tolerance=-0.1)
    with pytest.raises(ValueError):
        CopulaAggregationConfig(t_df_grid=())


def test_config_to_dict_roundtrip():
    cfg = CopulaAggregationConfig(n_sim=5000, seed=1)
    d = cfg.to_dict()
    assert d["n_sim"] == 5000 and d["seed"] == 1
    assert isinstance(d["t_df_grid"], list) and len(d["t_df_grid"]) > 0


def test_pseudo_obs_range_and_shape():
    L = _synthetic_losses(n=500, seed=3)
    M = np.column_stack(L)
    U = _pseudo_obs(M)
    assert U.shape == M.shape
    assert U.min() > 0.0 and U.max() < 1.0
    # rank-monotone within a column
    order_in = np.argsort(M[:, 0])
    assert np.all(np.diff(U[order_in, 0]) >= 0)


def test_empirical_margin_monotone_and_bounded():
    x = np.array([3.0, 1.0, 2.0, 5.0, 4.0])
    m = _EmpiricalMargin(x)
    grid = np.linspace(0, 1, 11)
    q = m.ppf(grid)
    assert np.all(np.diff(q) >= -1e-9)        # non-decreasing
    assert q[0] == pytest.approx(1.0)         # min order stat
    assert q[-1] == pytest.approx(5.0)        # max order stat


def test_nearest_correlation_is_valid():
    bad = np.array([[1.0, 0.9, -0.9], [0.9, 1.0, 0.9], [-0.9, 0.9, 1.0]])
    R = _nearest_correlation(bad)
    assert np.allclose(np.diag(R), 1.0)
    assert np.all(np.linalg.eigvalsh(R) > -1e-10)   # PSD
    assert np.allclose(R, R.T)


# --------------------------------------------------------------------------- #
# Core aggregation behaviour
# --------------------------------------------------------------------------- #

def test_input_validation():
    v = np.arange(50.0)
    with pytest.raises(ValueError):
        CopulaRiskAggregator([v], ["only"], 1.0, 1.0)          # need >= 2
    with pytest.raises(ValueError):
        CopulaRiskAggregator([v, v], ["a"], 1.0, 1.0)          # name mismatch


def test_report_is_pass(report):
    assert report.verdict.startswith("PASS")


def test_all_copulas_beat_var_covar(report):
    assert report.var_covar_rel_error_vs_nested > 0.30          # MR-010 gap reproduced
    for c in report.copulas:
        assert c.scr_rel_error_vs_nested < report.var_covar_rel_error_vs_nested


def test_selected_copula_within_tolerance(report):
    sel = report.selected
    assert sel.scr_rel_error_vs_nested <= report.config.rel_error_tolerance
    assert sel.name == report.selected_copula


def test_selected_by_aic(report):
    # The reported selection is the minimum-AIC copula.
    best = min(report.copulas, key=lambda c: c.aic)
    assert report.selected_copula == best.name


def test_three_copula_families_present(report):
    names = {c.name for c in report.copulas}
    assert names == {"gaussian", "student_t", "survival_clayton"}


def test_tail_dependence_orientation(report):
    fits = {c.name: c for c in report.copulas}
    assert fits["gaussian"].upper_tail_dependence == 0.0           # elliptical, no TD
    assert fits["survival_clayton"].upper_tail_dependence > 0.0    # upper-tail dependent
    assert fits["student_t"].upper_tail_dependence >= 0.0


def test_diversification_and_positive_scr(report):
    for c in report.copulas:
        assert c.aggregated_capital.scr_proxy > 0.0
        # diversified capital must not exceed the standalone sum
        assert c.aggregated_capital.scr_proxy <= report.standalone_scr_sum + 1e-6
        assert c.diversification_benefit == pytest.approx(
            report.standalone_scr_sum - c.aggregated_capital.scr_proxy, rel=1e-9
        )


def test_realised_loss_correlation_positive(report):
    M = np.array(report.realised_loss_correlation)
    assert M.shape == (3, 3)
    assert np.allclose(np.diag(M), 1.0)
    # off-diagonals all strongly positive (the MR-010 phenomenon)
    assert M[0, 1] > 0.4 and M[0, 2] > 0.4 and M[1, 2] > 0.4


def test_reproducibility(losses):
    rate, equity, credit = losses
    factor = np.array([[1.0, -0.15, -0.20], [-0.15, 1.0, -0.30], [-0.20, -0.30, 1.0]])
    nested, var_covar = _benchmarks(rate, equity, credit, factor)
    agg = CopulaRiskAggregator([rate, equity, credit],
                               ["r", "e", "c"], nested, var_covar)
    cfg = CopulaAggregationConfig(n_sim=40_000, seed=99)
    r1 = agg.run(cfg)
    r2 = agg.run(cfg)
    assert r1.reproducibility_digest == r2.reproducibility_digest
    assert r1.selected_copula == r2.selected_copula
    for a, b in zip(r1.copulas, r2.copulas):
        assert a.aggregated_capital.scr_proxy == pytest.approx(
            b.aggregated_capital.scr_proxy, rel=1e-12
        )


def test_digest_depends_on_inputs_not_sim_seed(losses):
    rate, equity, credit = losses
    factor = np.eye(3)
    nested, var_covar = _benchmarks(rate, equity, credit, factor)
    agg = CopulaRiskAggregator([rate, equity, credit], ["r", "e", "c"], nested, var_covar)
    d1 = agg.run(CopulaAggregationConfig(n_sim=20_000, seed=1)).reproducibility_digest
    d2 = agg.run(CopulaAggregationConfig(n_sim=20_000, seed=2)).reproducibility_digest
    assert d1 == d2   # digest is over the loss data + benchmarks, not the sim seed


def test_independent_components_diversify(losses):
    # Independent components -> aggregate SCR well below comonotonic sum.
    rng = np.random.default_rng(11)
    n = 3000
    a = 50_000 + 6_000 * np.exp(0.4 * rng.standard_normal(n))
    b = 30_000 + 5_000 * np.exp(0.4 * rng.standard_normal(n))
    c = 10_000 + 2_000 * np.exp(0.4 * rng.standard_normal(n))

    def scr(x):
        return float(np.quantile(x, CONF) - x.mean())

    nested = scr(a + b + c)
    var_covar = scr(a) + scr(b) + scr(c)  # comonotonic upper bound
    agg = CopulaRiskAggregator([a, b, c], ["a", "b", "c"], nested, var_covar)
    rep = agg.run(CopulaAggregationConfig(n_sim=60_000, seed=5))
    sel = rep.selected
    assert sel.aggregated_capital.scr_proxy < var_covar
    assert sel.scr_rel_error_vs_nested < 0.10


def test_to_dict_json_serialisable(report):
    d = report.to_dict()
    assert d["verdict"].startswith("PASS")
    assert len(d["copulas"]) == 3
    assert "selected_copula" in d
    s = report.to_json()
    parsed = json.loads(s)
    assert parsed["nested_scr"] == d["nested_scr"]
    assert "standards" in parsed


def test_copula_fit_to_dict(report):
    c = report.copulas[0]
    cd = c.to_dict()
    for key in ("name", "aic", "loglik", "aggregated_scr",
                "scr_rel_error_vs_nested", "upper_tail_dependence"):
        assert key in cd


def test_use_restrictions():
    r = copula_aggregation_use_restrictions()
    assert r["classification"].startswith("EDUCATIONAL")
    assert "limitations" in r and len(r["limitations"]) >= 3
    parsed = json.loads(copula_aggregation_use_restrictions_json())
    assert parsed["module"].endswith("multi_driver_copula_aggregation.py")


def test_default_tolerance_constant():
    assert 0.0 < DEFAULT_COPULA_REL_ERROR_TOLERANCE < 0.35


def test_governance_audit_optional(losses):
    """A minimal duck-typed governance store receives one audit entry."""
    rate, equity, credit = losses
    factor = np.eye(3)
    nested, var_covar = _benchmarks(rate, equity, credit, factor)

    class _Trail:
        def __init__(self):
            self.entries = []

        def append(self, e):
            self.entries.append(e)

    class _Store:
        def __init__(self):
            self.audit_trail = _Trail()

    store = _Store()
    agg = CopulaRiskAggregator([rate, equity, credit], ["r", "e", "c"], nested, var_covar)
    rep = agg.run(CopulaAggregationConfig(n_sim=20_000, seed=3), governance_store=store)
    # Either an entry was appended (real AuditEntry available) or a skip note logged.
    assert len(store.audit_trail.entries) == 1 or any(
        "audit append skipped" in n for n in rep.notes
    )
