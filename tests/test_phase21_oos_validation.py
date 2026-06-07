"""Phase 21 Task 2 — six-driver out-of-sample proxy-validation tests.

Covers: hexavariate basis construction with capped interaction order, config
validation, surface fitting in both fx modes (learned hexavariate vs analytic
CIP-exact offset), slice-stable CRN staging bit-identity, the end-to-end
validate() workflow (report structure, leakage, FX-axis evidence,
reproducibility), and staged == monolithic equivalence via ``precomputed``.
"""

import numpy as np
import pytest

from par_model_v2.projection.monthly_projection import ParEndowmentProduct
from par_model_v2.projection.multi_driver_proxy_validation_6d import (
    DEFAULT_HEX_BASIS_GRID,
    HexProxyValidationConfig,
    SixDriverFXProxyValidator,
    _fit_hex_surface,
    _hex_poly_basis,
    _hex_poly_powers,
    _n_hex_basis_terms,
    hex_proxy_validation_use_restrictions,
)


@pytest.fixture(scope="module")
def product():
    return ParEndowmentProduct(
        issue_age=45, gender="M", sum_assured=100000.0,
        annual_premium=5000.0, term_years=20,
    )


@pytest.fixture(scope="module")
def validator(product):
    return SixDriverFXProxyValidator(product)


def _tiny_cfg(**kw):
    base = dict(
        n_fit=60, n_validation=8, n_insample_heavy=8, n_inner_heavy=8,
        n_eval=40, nested_n_inner=8, basis_grid=((1, 3), (2, 3)),
    )
    base.update(kw)
    return HexProxyValidationConfig(**base)


# ---------------------------------------------------------------------------
# Hexavariate basis
# ---------------------------------------------------------------------------

def test_hex_basis_term_counts():
    # Full simplex counts C(6+d, 6) when the cap does not bite.
    assert _n_hex_basis_terms(1, 3) == 7
    assert _n_hex_basis_terms(2, 3) == 28
    assert _n_hex_basis_terms(3, 3) == 84
    # Cap at 2 removes the 20 three-way (1,1,1) cubic terms: 84 - 20 = 64.
    assert _n_hex_basis_terms(3, 2) == 64
    # Cap at 3 removes the 75 quartic terms with >= 3 distinct drivers.
    assert _n_hex_basis_terms(4, 3) == 135


def test_hex_basis_cap_excludes_higher_interactions():
    for powers, max_int in ((_hex_poly_powers(4, 3), 3), (_hex_poly_powers(3, 2), 2)):
        for p in powers:
            nonzero = sum(1 for e in p if e >= 1)
            total = sum(p)
            assert not (nonzero >= 3 and total > max_int)


def test_hex_basis_design_matrix_shape_and_validation():
    X = np.random.default_rng(0).normal(size=(11, 6))
    B = _hex_poly_basis(X, 2, 3)
    assert B.shape == (11, 28)
    np.testing.assert_allclose(B[:, 0], np.ones(11))
    with pytest.raises(ValueError):
        _hex_poly_basis(X[:, :5], 2, 3)
    with pytest.raises(ValueError):
        _hex_poly_powers(-1, 3)


# ---------------------------------------------------------------------------
# Configuration validation
# ---------------------------------------------------------------------------

def test_config_validation():
    with pytest.raises(ValueError):
        HexProxyValidationConfig(fit_seed=7, validation_seed=7)
    with pytest.raises(ValueError):
        HexProxyValidationConfig(selection_metric="aic")
    with pytest.raises(ValueError):
        HexProxyValidationConfig(basis_grid=())
    with pytest.raises(ValueError):
        HexProxyValidationConfig(basis_grid=((0, 3),))
    with pytest.raises(ValueError):
        HexProxyValidationConfig(n_validation=4)
    with pytest.raises(ValueError):
        HexProxyValidationConfig(fx_modes=("bayesian",))
    with pytest.raises(ValueError):
        HexProxyValidationConfig(fx_modes=())
    cfg = HexProxyValidationConfig()
    d = cfg.to_dict()
    assert d["fx_modes"] == ["analytic", "learned"]
    assert d["eval_seed"] == cfg.fit_seed + 99
    assert d["nested_inner_seed"] == cfg.fit_seed + 100
    assert tuple(tuple(p) for p in d["basis_grid"]) == DEFAULT_HEX_BASIS_GRID


# ---------------------------------------------------------------------------
# Surface fitting (both fx modes)
# ---------------------------------------------------------------------------

def test_fit_hex_surface_learned_recovers_noiseless_polynomial():
    rng = np.random.default_rng(1)
    X6 = rng.normal(size=(400, 6))
    # Noiseless quadratic in all six drivers (incl. an FX term).
    y = (2.0 + 1.5 * X6[:, 0] - 0.7 * X6[:, 5]
         + 0.4 * X6[:, 1] * X6[:, 5] + 0.3 * X6[:, 2] ** 2)
    fx_zero = np.zeros(len(X6))
    surf = _fit_hex_surface(X6, y, fx_zero, 2, 3, fx_mode="learned")
    pred = surf.predict_poly(X6)
    np.testing.assert_allclose(pred, y, atol=1e-8)
    assert surf.in_sample_r2_noisy == pytest.approx(1.0)
    assert surf.n_basis_terms == 28


def test_fit_hex_surface_analytic_mode_spans_five_drivers_only():
    rng = np.random.default_rng(2)
    X6 = rng.normal(size=(300, 6))
    y5 = 1.0 + 0.5 * X6[:, 0] - 0.2 * X6[:, 3] ** 2
    fx_l = -3.0 * (X6[:, 5] - 1.0)
    surf = _fit_hex_surface(X6, y5, fx_l, 2, 3, fx_mode="analytic")
    # Quintivariate basis: C(5+2,5) = 21 terms; FX never enters the fit.
    assert surf.n_basis_terms == 21
    assert len(surf.beta) == 21
    np.testing.assert_allclose(surf.predict_poly(X6), y5, atol=1e-8)
    # Perturbing the X column must not change the analytic-mode polynomial.
    X6b = X6.copy()
    X6b[:, 5] += 10.0
    np.testing.assert_allclose(surf.predict_poly(X6b), surf.predict_poly(X6))
    with pytest.raises(ValueError):
        _fit_hex_surface(X6, y5, fx_l, 2, 3, fx_mode="other")


# ---------------------------------------------------------------------------
# Slice-stable CRN staging
# ---------------------------------------------------------------------------

def test_states_deterministic_and_shape(validator):
    s1 = validator.states(24, 123)
    s2 = validator.states(24, 123)
    np.testing.assert_allclose(s1, s2)
    assert s1.shape == (24, 6)
    assert np.all(s1[:, 5] > 0.0)  # lognormal FX spots positive


def test_single_path_payoffs_staged_bit_identical(validator):
    X = validator.states(16, 42)
    mono = validator.single_path_payoffs_sliced(X, 0, 16, 42)
    part = np.concatenate([
        validator.single_path_payoffs_sliced(X, 0, 7, 42),
        validator.single_path_payoffs_sliced(X, 7, 16, 42),
    ])
    np.testing.assert_array_equal(mono, part)


def test_heavy_targets_staged_bit_identical(validator):
    X = validator.states(10, 7)
    mono = validator.heavy_targets_sliced(X, 0, 10, 8, 99)
    part = np.concatenate([
        validator.heavy_targets_sliced(X, 0, 4, 8, 99),
        validator.heavy_targets_sliced(X, 4, 10, 8, 99),
    ])
    np.testing.assert_array_equal(mono, part)


def test_fx_term_cip_exact_mapping(validator):
    x0 = validator.agg.fx_exposure.initial_spot_rate
    notional = validator.agg.fx_exposure.exposure_notional
    states = np.zeros((3, 6))
    states[:, 5] = (x0, 0.9 * x0, 1.1 * x0)
    fx = validator.fx_term(states)
    assert fx[0] == pytest.approx(0.0)
    assert fx[1] == pytest.approx(0.1 * notional)
    assert fx[2] == pytest.approx(-0.1 * notional)


# ---------------------------------------------------------------------------
# End-to-end validate()
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def tiny_report(validator):
    return validator.validate(_tiny_cfg())


def test_validate_report_structure(tiny_report):
    d = tiny_report.to_dict()
    assert d["drivers"] == [
        "short_rate_g2pp_2f", "equity_level", "credit_spread",
        "lapse_behaviour", "mortality_trend", "fx_translation",
    ]
    assert d["selected_fx_mode"] in ("analytic", "learned")
    # Both modes x both bases swept.
    assert len(d["basis_rows"]) == 4
    modes = {r["fx_mode"] for r in d["basis_rows"]}
    assert modes == {"analytic", "learned"}
    sel = tiny_report.selected_row()
    assert sel.fx_mode == tiny_report.selected_fx_mode
    assert sel.degree == tiny_report.selected_degree
    assert d["verdict"].startswith(("PASS", "PARTIAL"))
    assert d["leakage"]["leakage_free"] is True
    assert d["leakage"]["n_exact_shared_states"] == 0
    assert "fx_axis_evidence" in d
    assert d["capital_comparison"]["nested_n_inner"] == 8
    assert len(d["reproducibility_digest"]) == 64
    json_str = tiny_report.to_json()
    assert "selected_fx_mode" in json_str


def test_validate_reproducible_digest(validator, tiny_report):
    rep2 = validator.validate(_tiny_cfg())
    assert rep2.reproducibility_digest == tiny_report.reproducibility_digest
    assert rep2.selected_fx_mode == tiny_report.selected_fx_mode
    assert rep2.verdict == tiny_report.verdict


def test_validate_precomputed_staged_equals_monolithic(validator, tiny_report):
    cfg = _tiny_cfg()
    fit_X = validator.states(cfg.n_fit, cfg.fit_seed)
    val_X = validator.states(cfg.n_validation, cfg.validation_seed)
    eval_X = validator.states(cfg.n_eval, cfg.eval_seed)
    pre = {
        "fit_y5": np.concatenate([
            validator.single_path_payoffs_sliced(fit_X, 0, 25, cfg.fit_seed),
            validator.single_path_payoffs_sliced(fit_X, 25, cfg.n_fit, cfg.fit_seed),
        ]),
        "val_truth5": validator.heavy_targets_sliced(
            val_X, 0, cfg.n_validation, cfg.n_inner_heavy, cfg.validation_seed),
        "insample_truth5": validator.heavy_targets_sliced(
            fit_X[:cfg.n_insample_heavy], 0, cfg.n_insample_heavy,
            cfg.n_inner_heavy, cfg.insample_heavy_seed),
        "nested_l5": np.concatenate([
            validator.heavy_targets_sliced(
                eval_X, 0, 13, cfg.nested_n_inner, cfg.nested_inner_seed),
            validator.heavy_targets_sliced(
                eval_X, 13, cfg.n_eval, cfg.nested_n_inner, cfg.nested_inner_seed),
        ]),
    }
    staged = validator.validate(cfg, precomputed=pre)
    assert staged.reproducibility_digest == tiny_report.reproducibility_digest
    for a, b in zip(staged.basis_rows, tiny_report.basis_rows):
        assert a.to_dict() == b.to_dict()
    assert staged.capital_comparison.to_dict() == tiny_report.capital_comparison.to_dict()


def test_validate_precomputed_length_mismatch_raises(validator):
    cfg = _tiny_cfg()
    with pytest.raises(ValueError):
        validator.validate(cfg, precomputed={"fit_y5": np.zeros(3)})


def test_analytic_mode_recovers_fx_axis_exactly(validator):
    cfg = _tiny_cfg(fx_modes=("analytic",))
    rep = validator.validate(cfg)
    assert rep.selected_fx_mode == "analytic"
    # The CIP-exact offset reproduces the theoretical slope by construction.
    assert rep.fx_axis_evidence["slope_rel_error"] < 1e-6


def test_validator_constructor_validation(product):
    with pytest.raises(ValueError):
        SixDriverFXProxyValidator(product, capital_horizon_months=0)
    with pytest.raises(ValueError):
        SixDriverFXProxyValidator(
            product, capital_horizon_months=product.term_months)


# ---------------------------------------------------------------------------
# Use restrictions
# ---------------------------------------------------------------------------

def test_use_restrictions_structure():
    r = hex_proxy_validation_use_restrictions()
    assert "SixDriverFXProxyValidator" in r["module"]
    assert "EDUCATIONAL" in r["classification"]
    assert any("Liquidity" in s or "liquidity" in s for s in [r["residual_risk"]])
    assert any("188" in s for s in r["standards"])
