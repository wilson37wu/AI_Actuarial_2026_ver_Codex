"""Tests for the MLMC stage-3 wiring into the governed nested engine (W60).

Guards the opt-in ``NestedStochasticTVOGEngine.run(inner_estimator='mlmc')``
path: the default 'fixed' run stays byte-identical (no governed figure moves),
the 'mlmc' run attaches mean-liability diagnostics whose estimand matches the
fixed-256 mean liability (gate G1) at >=2x matched-RMSE cost cut (gate G3), and
the diagnostics are reproducible (gate G4). MLMC never alters the governed
SCR/VaR/ES headline (a quantile; stage-5 owner gate).
"""
import numpy as np
import pytest

from par_model_v2.projection.monthly_projection import ParEndowmentProduct
from par_model_v2.stochastic.esg_process import HullWhiteParams
from par_model_v2.projection.nested_stochastic_tvog import (
    NestedStochasticTVOGEngine,
)
from par_model_v2.projection.mlmc_inner_estimator import (
    engine_mean_liability_diagnostics,
)


def _engine():
    product = ParEndowmentProduct(term_years=10, issue_age=40, gender="M",
                                  sum_assured=100_000, annual_premium=6_000)
    return NestedStochasticTVOGEngine(product, HullWhiteParams(),
                                      capital_horizon_months=12)


@pytest.fixture(scope="module")
def runs():
    eng = _engine()
    r_fixed = eng.run(n_outer=128, n_inner=256, seed=42)
    r_mlmc = eng.run(n_outer=128, n_inner=256, seed=42, inner_estimator="mlmc")
    return r_fixed, r_mlmc


def test_default_is_fixed_and_summary_byte_identical(runs):
    r_fixed, _ = runs
    assert r_fixed.inner_estimator == "fixed"
    assert r_fixed.mlmc_diagnostics is None
    # The fixed-run summary must carry NO MLMC keys (pre-stage-3 shape).
    s = r_fixed.summary()
    assert "mlmc_diagnostics" not in s
    assert "inner_estimator" not in s


def test_mlmc_does_not_move_governed_capital(runs):
    r_fixed, r_mlmc = runs
    # Selecting MLMC must leave every governed capital figure bit-identical.
    assert r_fixed.capital.summary() == r_mlmc.capital.summary()
    assert np.array_equal(r_fixed.conditional_liabilities,
                          r_mlmc.conditional_liabilities)


def test_mlmc_attaches_diagnostics(runs):
    _, r_mlmc = runs
    assert r_mlmc.inner_estimator == "mlmc"
    d = r_mlmc.mlmc_diagnostics
    assert d is not None
    assert d["estimand"].startswith("outer_mean_conditional_liability")
    assert d["finest_n_inner"] == 256
    assert d["ladder"][-1] == 256
    s = r_mlmc.summary()
    assert s["inner_estimator"] == "mlmc"
    assert "mlmc_diagnostics" in s


def test_G1_mean_liability_equivalence(runs):
    _, r_mlmc = runs
    d = r_mlmc.mlmc_diagnostics
    # MLMC mean liability matches the fixed-256 mean liability within 1%.
    assert d["equivalence_rel_err"] < 0.01


def test_G3_matched_rmse_speedup_at_NL256(runs):
    _, r_mlmc = runs
    d = r_mlmc.mlmc_diagnostics
    assert d["matched_rmse_speedup_x"] >= 2.0


def test_G4_reproducible_same_seed():
    eng = _engine()
    a = eng.run(n_outer=96, n_inner=256, seed=7, inner_estimator="mlmc")
    b = eng.run(n_outer=96, n_inner=256, seed=7, inner_estimator="mlmc")
    assert (a.mlmc_diagnostics["mlmc_mean_liability"]
            == b.mlmc_diagnostics["mlmc_mean_liability"])
    assert (a.mlmc_diagnostics["mlmc_inner_path_cost"]
            == b.mlmc_diagnostics["mlmc_inner_path_cost"])


def test_invalid_inner_estimator_rejected():
    eng = _engine()
    with pytest.raises(ValueError):
        eng.run(n_outer=16, n_inner=64, seed=1, inner_estimator="bogus")


def test_helper_function_directly():
    product = ParEndowmentProduct(term_years=10, issue_age=40, gender="M",
                                  sum_assured=100_000, annual_premium=6_000)
    d = engine_mean_liability_diagnostics(
        product=product, hw_params=HullWhiteParams(),
        capital_horizon_months=12, outer_measure="P",
        n_inner=128, seed=3, fixed_n_outer=64)
    assert d["finest_n_inner"] == 128
    assert d["ladder"][-1] == 128
    assert d["mlmc_inner_path_cost"] > 0
