"""Phase UIL Task 2 (B2) tests: optional user inputs with governed fallbacks.

Regression gate: with NO user inputs every consumer must behave bit-identically
to the fixture-driven pipeline (same exposure inputs, same portfolio digest,
same capital-path parameters).
"""

from __future__ import annotations

import json

import pytest

import par_model_v2.user_inputs as ui
from par_model_v2.user_inputs import (
    GOVERNED_CAPITAL_PARAMS,
    UserInputsError,
    capital_params,
    exposure_overrides,
    find_model_inputs,
    user_model_points,
)
from par_model_v2.calibration.phase22_liquidity_exposure_calibration import (
    derive_exposure_notional,
    load_exposure_fixture,
    resolve_exposure_spec,
)
from par_model_v2.projection.portfolio_generator import (
    UNIFIED_COLUMNS,
    PortfolioGenerationConfig,
    build_portfolio,
    generate_hk_par_portfolio,
    portfolio_from_model_points,
    split_model_points,
)


SAMPLE_INPUTS = {
    "schema_version": "1.0.0",
    "currency": {"code": "HKD"},
    "balance_sheet": {
        "assets": [
            {"asset_class": "Govt bonds", "market_value": 150000.0, "illiquid": False},
            {"asset_class": "Corp credit", "market_value": 100000.0, "illiquid": True},
        ],
        "backing_asset_mv": 250000.0,
        "illiquid_mv": 100000.0,
        "illiquid_share": 0.40,
        "forced_sale_fraction": 0.35,
        "best_estimate_liability": 90000.0,
        "equity_guarantee_initial_index": 100.0,
    },
    "portfolio": [
        {"product_type": "HKCD_PAR_2026", "issue_age": 35, "gender": "F",
         "term_years": 10, "sum_assured": 500000.0, "annual_premium": 42000.0,
         "policy_count": 1200, "vested_bonus": 0.0, "source_row": 9},
        {"product_type": "HKRB_PAR_2026", "issue_age": 45, "gender": "M",
         "term_years": 20, "sum_assured": 800000.0, "annual_premium": 36000.0,
         "policy_count": 800, "vested_bonus": 12000.0, "source_row": 10},
        {"product_type": "GMMB_EQ_2026", "issue_age": 50, "gender": "M",
         "term_years": 10, "sum_assured": 100000.0, "annual_premium": 0.0,
         "policy_count": 500, "vested_bonus": 0.0, "source_row": 11},
    ],
    "assumptions": {"confidence": 0.99, "relief_sigma": 0.30,
                    "relief_alpha": 0.70, "benefit_share": 0.80},
    "run_settings": {"n_sim": 1000, "seed": 123, "output_label": "test"},
}


# ---------------------------------------------------------------------------
# find_model_inputs
# ---------------------------------------------------------------------------

def test_find_returns_none_when_no_file(tmp_path, monkeypatch):
    monkeypatch.delenv("PAR_MODEL_INPUTS", raising=False)
    monkeypatch.setattr(ui, "_REPO_ROOT", tmp_path)
    assert find_model_inputs() is None


def test_find_explicit_missing_path_fails_loud(tmp_path):
    with pytest.raises(UserInputsError, match="not found"):
        find_model_inputs(tmp_path / "nope.json")


def test_find_corrupt_json_fails_loud(tmp_path):
    p = tmp_path / "model_inputs.json"
    p.write_text("{not json", encoding="utf-8")
    with pytest.raises(UserInputsError, match="cannot read"):
        find_model_inputs(p)


def test_find_wrong_schema_major_fails_loud(tmp_path):
    p = tmp_path / "model_inputs.json"
    p.write_text(json.dumps({"schema_version": "2.0.0"}), encoding="utf-8")
    with pytest.raises(UserInputsError, match="unsupported schema_version"):
        find_model_inputs(p)


def test_find_valid_file_roundtrip(tmp_path):
    p = tmp_path / "model_inputs.json"
    p.write_text(json.dumps(SAMPLE_INPUTS), encoding="utf-8")
    got = find_model_inputs(p)
    assert got["currency"]["code"] == "HKD"
    assert got["_source_path"] == str(p)


def test_find_env_var_resolution(tmp_path, monkeypatch):
    p = tmp_path / "via_env.json"
    p.write_text(json.dumps(SAMPLE_INPUTS), encoding="utf-8")
    monkeypatch.setenv("PAR_MODEL_INPUTS", str(p))
    assert find_model_inputs()["currency"]["code"] == "HKD"


# ---------------------------------------------------------------------------
# capital params — governed fallback is bit-identical
# ---------------------------------------------------------------------------

def test_capital_params_governed_defaults():
    got = capital_params(None)
    assert got["source"] == "governed_defaults"
    for k, v in GOVERNED_CAPITAL_PARAMS.items():
        assert got[k] == v  # exact equality: bit-identical gate


def test_capital_params_user_override():
    got = capital_params(SAMPLE_INPUTS)
    assert got["source"] == "user_inputs"
    assert got["confidence"] == 0.99
    assert got["relief_sigma"] == 0.30
    assert got["relief_alpha"] == 0.70
    assert got["benefit_share"] == 0.80


def test_capital_params_rejects_out_of_range():
    bad = {"schema_version": "1.0.0", "assumptions": {"confidence": 1.5}}
    with pytest.raises(UserInputsError):
        capital_params(bad)


# ---------------------------------------------------------------------------
# phase22 exposure — fixture path unchanged, user path overlaid
# ---------------------------------------------------------------------------

def test_exposure_overrides_none_without_inputs():
    assert exposure_overrides(None) is None


def test_resolve_exposure_spec_fixture_identical():
    spec, _lineage = load_exposure_fixture()
    resolved = resolve_exposure_spec(spec, None)
    assert resolved["exposure_source"] == "fixture"
    assert resolved["exposure_inputs"]["backing_asset_mv"] == 100000.0
    assert resolved["exposure_inputs"]["illiquid_share"] == 0.55
    assert resolved["exposure_inputs"]["forced_sale_fraction"] == 0.40
    exp = derive_exposure_notional(resolved)
    assert exp["exposure_notional"] == pytest.approx(22000.0, abs=1e-9)


def test_resolve_exposure_spec_user_overlay():
    spec, _lineage = load_exposure_fixture()
    resolved = resolve_exposure_spec(spec, SAMPLE_INPUTS)
    assert resolved["exposure_source"] == "user_inputs"
    exp = derive_exposure_notional(resolved)
    assert exp["backing_asset_mv"] == 250000.0
    assert exp["exposure_notional"] == pytest.approx(250000.0 * 0.40 * 0.35)
    # original fixture spec must not be mutated
    assert spec["exposure_inputs"]["backing_asset_mv"] == 100000.0


def test_exposure_overrides_incomplete_fails_loud():
    with pytest.raises(UserInputsError, match="balance_sheet"):
        exposure_overrides({"schema_version": "1.0.0", "balance_sheet": {}})


# ---------------------------------------------------------------------------
# portfolio — user model points vs synthetic fallback
# ---------------------------------------------------------------------------

def test_split_model_points():
    par, gmmb = split_model_points(SAMPLE_INPUTS["portfolio"])
    assert len(par) == 2 and len(gmmb) == 1
    assert gmmb[0]["product_type"] == "GMMB_EQ_2026"


def test_portfolio_from_model_points_builds_unified_table():
    par, _ = split_model_points(SAMPLE_INPUTS["portfolio"])
    res = portfolio_from_model_points(par)
    t = res.policies
    assert list(t.columns) == list(UNIFIED_COLUMNS)
    assert len(t) == 2
    assert float(t["inforce_count"].sum()) == 2000.0
    cash = t[t["product_line"] == "CASH_DIVIDEND"].iloc[0]
    rb = t[t["product_line"] == "REVERSIONARY_BONUS"].iloc[0]
    assert cash["initial_vested_bonus"] == 0.0
    assert rb["initial_vested_bonus"] == 12000.0
    assert res.config.source_id == "USER_INPUTS"
    assert res.digest == portfolio_from_model_points(par).digest  # stable


def test_portfolio_from_model_points_fails_loud_with_all_rows():
    bad = [
        {"product_type": "HKCD_PAR_2026", "issue_age": 35, "gender": "F",
         "term_years": 10, "sum_assured": 500000.0, "annual_premium": 1000.0,
         "policy_count": 10, "vested_bonus": 5000.0, "source_row": 9},   # cash w/ VB
        {"product_type": "HKRB_PAR_2026", "issue_age": 200, "gender": "X",
         "term_years": 20, "sum_assured": 800000.0, "annual_premium": 1000.0,
         "policy_count": 10, "vested_bonus": 0.0, "source_row": 10},     # age+gender
    ]
    with pytest.raises(ValueError) as exc:
        portfolio_from_model_points(bad)
    msg = str(exc.value)
    assert "row 9" in msg and "row 10" in msg
    assert "vested" in msg and "issue_age" in msg


def test_build_portfolio_without_inputs_bit_identical():
    cfg = PortfolioGenerationConfig(n_policies=2000)
    direct = generate_hk_par_portfolio(cfg)
    via_b2 = build_portfolio(cfg, user_inputs=None)
    assert via_b2.digest == direct.digest  # regression gate


def test_build_portfolio_with_inputs_uses_user_book():
    res = build_portfolio(user_inputs=SAMPLE_INPUTS)
    assert res.config.source_id == "USER_INPUTS"
    assert len(res.policies) == 2


def test_user_model_points_accessor():
    assert user_model_points(None) is None
    assert user_model_points({"schema_version": "1.0.0"}) is None
    assert len(user_model_points(SAMPLE_INPUTS)) == 3
