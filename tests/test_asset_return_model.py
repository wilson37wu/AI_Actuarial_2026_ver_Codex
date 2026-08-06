"""
Unit tests for AssetReturnModel (par_model_v2/projection/asset_return_model.py)

Phase A of the asset–ESG coupling design
(docs/DESIGN_ASSET_ESG_COUPLING.md §4.1–§4.2, §5 gates).

Coverage:
  - Analytic return definitions per class (Cash, Govt, Credit, Equity)
  - Flat-scenario invariant: constant inputs -> constant returns (design G-AC1 spirit)
  - Period-change / initial-reference handling (Δx[0] = 0 by default)
  - Vectorisation consistency: batched (N, T) equals stacked single-path (T,)
  - Portfolio earned return weighting and weight-sum validation
  - Construction / input validation and error messages

Run:
    PYTHONPATH=. pytest tests/test_asset_return_model.py -v
"""

from __future__ import annotations

import numpy as np
import pytest

from par_model_v2.projection.asset_return_model import (
    AssetClassParams,
    AssetReturnModel,
    portfolio_earned_return,
)


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

def _full_model() -> AssetReturnModel:
    return AssetReturnModel(
        {
            "Cash": AssetClassParams("Cash"),
            "Govt": AssetClassParams("Govt", effective_duration=7.0),
            "Credit": AssetClassParams(
                "Credit",
                effective_duration=5.0,
                spread_duration=4.0,
                base_spread=0.012,
                annual_default_loss=0.003,
            ),
            "Equity": AssetClassParams("Equity", dividend_yield=0.025),
        }
    )


# ---------------------------------------------------------------------------
# Analytic return definitions
# ---------------------------------------------------------------------------

class TestReturnDefinitions:
    def test_cash_is_short_rate_over_twelve(self):
        model = AssetReturnModel({"Cash": AssetClassParams("Cash")})
        sr = np.array([0.01, 0.02, 0.03, 0.025])
        out = model.monthly_total_returns(short_rate=sr)
        assert np.allclose(out["Cash"], sr / 12.0)

    def test_govt_carry_minus_duration_price_move(self):
        dur = 7.0
        model = AssetReturnModel({"Govt": AssetClassParams("Govt", effective_duration=dur)})
        sr = np.array([0.030, 0.034, 0.031])  # Δr = [0, +0.004, -0.003]
        out = model.monthly_total_returns(short_rate=sr)
        d_short = np.array([0.0, 0.004, -0.003])
        expected = sr / 12.0 - dur * d_short
        assert np.allclose(out["Govt"], expected)

    def test_credit_full_decomposition(self):
        p = AssetClassParams(
            "Credit",
            effective_duration=5.0,
            spread_duration=4.0,
            base_spread=0.012,
            annual_default_loss=0.003,
        )
        model = AssetReturnModel({"Credit": p})
        sr = np.array([0.030, 0.033])      # Δr = [0, +0.003]
        cs = np.array([0.012, 0.015])      # Δs = [0, +0.003]
        out = model.monthly_total_returns(short_rate=sr, credit_spread=cs)
        d_short = np.array([0.0, 0.003])
        d_spread = np.array([0.0, 0.003])
        expected = (
            sr / 12.0
            - p.effective_duration * d_short
            + p.base_spread / 12.0
            - p.spread_duration * d_spread
            - p.annual_default_loss / 12.0
        )
        assert np.allclose(out["Credit"], expected)

    def test_equity_is_passed_through(self):
        model = AssetReturnModel({"Equity": AssetClassParams("Equity")})
        sr = np.array([0.02, 0.02, 0.02])
        eq = np.array([0.01, -0.05, 0.03])
        out = model.monthly_total_returns(short_rate=sr, equity_return=eq)
        assert np.allclose(out["Equity"], eq)
        # Pass-through must not alias the input array.
        assert out["Equity"] is not eq


# ---------------------------------------------------------------------------
# Flat-scenario invariant (design gate G-AC1 spirit)
# ---------------------------------------------------------------------------

class TestFlatScenario:
    def test_constant_inputs_give_constant_returns(self):
        model = _full_model()
        T = 24
        sr = np.full(T, 0.03)
        cs = np.full(T, 0.012)
        eq = np.full(T, 0.004)
        out = model.monthly_total_returns(short_rate=sr, equity_return=eq, credit_spread=cs)
        for cls, arr in out.items():
            assert np.allclose(arr, arr[0]), f"{cls} not constant under a flat scenario"

    def test_flat_govt_equals_carry(self):
        model = AssetReturnModel({"Govt": AssetClassParams("Govt", effective_duration=9.0)})
        sr = np.full(12, 0.025)
        out = model.monthly_total_returns(short_rate=sr)
        # Δr = 0 everywhere -> no price term -> pure carry.
        assert np.allclose(out["Govt"], 0.025 / 12.0)


# ---------------------------------------------------------------------------
# Initial-reference / period-change handling
# ---------------------------------------------------------------------------

class TestInitialReference:
    def test_default_first_change_is_zero(self):
        model = AssetReturnModel({"Govt": AssetClassParams("Govt", effective_duration=7.0)})
        sr = np.array([0.05, 0.05])
        out = model.monthly_total_returns(short_rate=sr)
        # First element price move must be zero by default.
        assert out["Govt"][0] == pytest.approx(0.05 / 12.0)

    def test_explicit_initial_short_rate(self):
        dur = 7.0
        model = AssetReturnModel({"Govt": AssetClassParams("Govt", effective_duration=dur)})
        sr = np.array([0.034, 0.034])
        out = model.monthly_total_returns(short_rate=sr, initial_short_rate=0.030)
        # Δr[0] = 0.034 - 0.030 = 0.004 -> price term applies in first month.
        assert out["Govt"][0] == pytest.approx(0.034 / 12.0 - dur * 0.004)
        assert out["Govt"][1] == pytest.approx(0.034 / 12.0)  # Δr[1] = 0


# ---------------------------------------------------------------------------
# Vectorisation consistency
# ---------------------------------------------------------------------------

class TestVectorisation:
    def test_batched_equals_stacked_single_paths(self):
        model = _full_model()
        rng = np.random.default_rng(20260623)
        N, T = 5, 18
        sr = 0.03 + 0.01 * rng.standard_normal((N, T))
        cs = 0.012 + 0.002 * rng.standard_normal((N, T))
        eq = 0.004 * rng.standard_normal((N, T))

        batched = model.monthly_total_returns(short_rate=sr, equity_return=eq, credit_spread=cs)

        for n in range(N):
            single = model.monthly_total_returns(
                short_rate=sr[n], equity_return=eq[n], credit_spread=cs[n]
            )
            for cls in batched:
                assert np.allclose(batched[cls][n], single[cls]), f"{cls} row {n} mismatch"

    def test_output_shape_matches_input(self):
        model = _full_model()
        sr = np.zeros((3, 10)) + 0.02
        cs = np.zeros((3, 10)) + 0.01
        eq = np.zeros((3, 10))
        out = model.monthly_total_returns(short_rate=sr, equity_return=eq, credit_spread=cs)
        for arr in out.values():
            assert arr.shape == (3, 10)

    def test_per_scenario_initial_reference(self):
        model = AssetReturnModel({"Govt": AssetClassParams("Govt", effective_duration=4.0)})
        sr = np.array([[0.03, 0.03], [0.05, 0.05]])
        init = np.array([0.02, 0.06])  # per-scenario reference
        out = model.monthly_total_returns(short_rate=sr, initial_short_rate=init)
        assert out["Govt"][0, 0] == pytest.approx(0.03 / 12.0 - 4.0 * (0.03 - 0.02))
        assert out["Govt"][1, 0] == pytest.approx(0.05 / 12.0 - 4.0 * (0.05 - 0.06))


# ---------------------------------------------------------------------------
# Portfolio earned return
# ---------------------------------------------------------------------------

class TestPortfolioEarnedReturn:
    def test_weighted_sum(self):
        returns = {
            "Govt": np.array([0.01, 0.02]),
            "Equity": np.array([0.03, -0.04]),
        }
        weights = {"Govt": 0.6, "Equity": 0.4}
        earned = portfolio_earned_return(returns, weights)
        expected = 0.6 * returns["Govt"] + 0.4 * returns["Equity"]
        assert np.allclose(earned, expected)

    def test_full_portfolio_against_model(self):
        model = _full_model()
        sr = np.array([0.03, 0.031, 0.029])
        cs = np.array([0.012, 0.013, 0.012])
        eq = np.array([0.005, -0.02, 0.01])
        out = model.monthly_total_returns(short_rate=sr, equity_return=eq, credit_spread=cs)
        weights = {"Govt": 0.4, "Credit": 0.3, "Equity": 0.2, "Cash": 0.1}
        earned = portfolio_earned_return(out, weights)
        expected = sum(weights[c] * out[c] for c in weights)
        assert np.allclose(earned, expected)

    def test_weights_must_sum_to_one(self):
        returns = {"Govt": np.array([0.01]), "Cash": np.array([0.002])}
        with pytest.raises(ValueError, match="sum to 1"):
            portfolio_earned_return(returns, {"Govt": 0.5, "Cash": 0.4})

    def test_weights_unknown_class_rejected(self):
        returns = {"Govt": np.array([0.01])}
        with pytest.raises(ValueError, match="no returns"):
            portfolio_earned_return(returns, {"Equity": 1.0})

    def test_empty_weights_rejected(self):
        with pytest.raises(ValueError, match="non-empty"):
            portfolio_earned_return({"Govt": np.array([0.01])}, {})


# ---------------------------------------------------------------------------
# Construction and input validation
# ---------------------------------------------------------------------------

class TestValidation:
    def test_unknown_asset_class_in_params(self):
        with pytest.raises(ValueError, match="unknown asset class"):
            AssetReturnModel({"Bonds": AssetClassParams("Govt")})

    def test_key_must_match_asset_class(self):
        with pytest.raises(ValueError, match="key and asset_class must match"):
            AssetReturnModel({"Govt": AssetClassParams("Credit")})

    def test_empty_params_rejected(self):
        with pytest.raises(ValueError, match="at least one"):
            AssetReturnModel({})

    def test_bad_asset_class_param(self):
        with pytest.raises(ValueError, match="asset_class must be one of"):
            AssetClassParams("Property")

    def test_negative_duration_rejected(self):
        with pytest.raises(ValueError, match="effective_duration must be non-negative"):
            AssetClassParams("Govt", effective_duration=-1.0)

    def test_credit_requires_spread_path(self):
        model = AssetReturnModel({"Credit": AssetClassParams("Credit", effective_duration=5.0)})
        with pytest.raises(ValueError, match="credit_spread is required"):
            model.monthly_total_returns(short_rate=np.array([0.03, 0.03]))

    def test_equity_requires_return_path(self):
        model = AssetReturnModel({"Equity": AssetClassParams("Equity")})
        with pytest.raises(ValueError, match="equity_return is required"):
            model.monthly_total_returns(short_rate=np.array([0.03, 0.03]))

    def test_companion_shape_must_match(self):
        model = _full_model()
        with pytest.raises(ValueError, match="must match short_rate shape"):
            model.monthly_total_returns(
                short_rate=np.array([0.03, 0.03]),
                equity_return=np.array([0.01, 0.02, 0.03]),
                credit_spread=np.array([0.01, 0.01]),
            )

    def test_short_rate_rank_validation(self):
        model = AssetReturnModel({"Cash": AssetClassParams("Cash")})
        with pytest.raises(ValueError, match="1-D .* or 2-D"):
            model.monthly_total_returns(short_rate=np.zeros((2, 2, 2)))

    def test_empty_short_rate_rejected(self):
        model = AssetReturnModel({"Cash": AssetClassParams("Cash")})
        with pytest.raises(ValueError, match="at least one time step"):
            model.monthly_total_returns(short_rate=np.array([]))

    def test_asset_classes_in_canonical_order(self):
        model = AssetReturnModel(
            {
                "Equity": AssetClassParams("Equity"),
                "Cash": AssetClassParams("Cash"),
                "Govt": AssetClassParams("Govt"),
            }
        )
        # Canonical order is Govt, Credit, Equity, Cash (Credit absent here).
        assert model.asset_classes == ("Govt", "Equity", "Cash")
