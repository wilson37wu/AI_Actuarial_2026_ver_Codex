"""Phase 22 Task 1 — six-driver OOS proxy-validation remediation tests.

Covers: targeted-basis construction + exact synthetic recovery; the de-noised
fitting kernel's bit-identity to the governed Phase 21 kernel at n_inner=1;
slice-stable CRN staging; the remediated configuration; targeted diagnostics;
and the saved evidence report (verdict + stricter Phase 22 gate).
"""

import json
from pathlib import Path

import numpy as np
import pytest

from par_model_v2.projection.monthly_projection import ParEndowmentProduct
from par_model_v2.projection.multi_driver_proxy_validation_6d import (
    HexProxyValidationConfig,
)
from par_model_v2.projection.multi_driver_proxy_validation_6d_remediation import (
    REMEDIATED_FIT_N_INNER,
    REMEDIATED_N_FIT,
    REMEDIATED_NESTED_N_INNER,
    TARGETED_EXTRA_POWERS,
    RemediatedHexProxyValidator,
    _targeted_design,
    fit_targeted_surface,
    n_targeted_terms,
    remediated_config,
    remediation_use_restrictions,
)

REPORT = Path("docs/validation/PHASE22_TASK1_OOS_REMEDIATION_REPORT.json")


@pytest.fixture(scope="module")
def validator():
    product = ParEndowmentProduct(
        issue_age=45, gender="M", sum_assured=100000.0,
        annual_premium=5000.0, term_years=20,
    )
    return RemediatedHexProxyValidator(product)


@pytest.fixture(scope="module")
def small_states(validator):
    return validator.states(12, 42)


# ---------------------------------------------------------------------------
# Targeted basis
# ---------------------------------------------------------------------------

class TestTargetedBasis:
    def test_n_terms_is_nine(self):
        assert n_targeted_terms() == 9

    def test_extra_powers_are_rate_equity_only(self):
        for p in TARGETED_EXTRA_POWERS:
            assert len(p) == 5
            assert sum(p) == 2
            assert all(e == 0 for e in p[2:]), "curvature must be rate/equity only"

    def test_design_shape_and_columns(self):
        X = np.random.default_rng(1).normal(size=(20, 5))
        D = _targeted_design(X)
        assert D.shape == (20, 9)
        np.testing.assert_allclose(D[:, 0], 1.0)        # intercept
        np.testing.assert_allclose(D[:, -3], X[:, 0] ** 2)
        np.testing.assert_allclose(D[:, -2], X[:, 1] ** 2)
        np.testing.assert_allclose(D[:, -1], X[:, 0] * X[:, 1])

    def test_design_rejects_wrong_width(self):
        with pytest.raises(ValueError):
            _targeted_design(np.zeros((5, 6)))

    def test_exact_recovery_of_targeted_quadratic(self):
        rng = np.random.default_rng(7)
        X6 = rng.normal(size=(400, 6))
        y = (
            1.5 - 0.8 * X6[:, 0] + 2.0 * X6[:, 1] + 0.3 * X6[:, 3]
            + 0.9 * X6[:, 0] ** 2 - 0.5 * X6[:, 1] ** 2 + 0.25 * X6[:, 0] * X6[:, 1]
        )
        surf = fit_targeted_surface(X6, y)
        pred = surf.predict_poly(X6)
        ss = 1.0 - np.sum((y - pred) ** 2) / np.sum((y - y.mean()) ** 2)
        assert ss > 1.0 - 1e-10
        assert surf.n_basis_terms == 9

    def test_fit_rejects_wrong_width(self):
        with pytest.raises(ValueError):
            fit_targeted_surface(np.zeros((10, 5)), np.zeros(10))


# ---------------------------------------------------------------------------
# De-noised fitting kernel (remediation 1)
# ---------------------------------------------------------------------------

class TestDenoisedKernel:
    def test_bit_identity_to_phase21_at_n_inner_1(self, validator, small_states):
        legacy = validator.single_path_payoffs_sliced(small_states, 0, 12, 42)
        denoised = validator.denoised_fit_payoffs_sliced(
            small_states, 0, 12, 42, n_inner=1)
        assert np.array_equal(legacy, denoised)

    def test_staged_equals_monolithic(self, validator, small_states):
        mono = validator.denoised_fit_payoffs_sliced(small_states, 0, 12, 42, 4)
        staged = np.concatenate([
            validator.denoised_fit_payoffs_sliced(small_states, 0, 5, 42, 4),
            validator.denoised_fit_payoffs_sliced(small_states, 5, 12, 42, 4),
        ])
        assert np.array_equal(mono, staged)

    def test_denoising_changes_targets(self, validator, small_states):
        a = validator.denoised_fit_payoffs_sliced(small_states, 0, 12, 42, 1)
        b = validator.denoised_fit_payoffs_sliced(small_states, 0, 12, 42, 8)
        assert not np.array_equal(a, b)
        assert np.all(np.isfinite(b))

    def test_rejects_zero_inner(self, validator, small_states):
        with pytest.raises(ValueError):
            validator.denoised_fit_payoffs_sliced(small_states, 0, 4, 42, 0)


# ---------------------------------------------------------------------------
# Remediated configuration (remediations 1-3 sizing)
# ---------------------------------------------------------------------------

class TestRemediatedConfig:
    def test_sizing(self):
        cfg = remediated_config()
        assert cfg.n_fit == REMEDIATED_N_FIT == 2000
        assert cfg.nested_n_inner == REMEDIATED_NESTED_N_INNER == 256
        assert REMEDIATED_FIT_N_INNER == 8

    def test_inherits_governed_protocol(self):
        cfg = remediated_config()
        base = HexProxyValidationConfig()
        # Hold-out protocol unchanged: same seeds, same heavy budgets.
        assert cfg.fit_seed == base.fit_seed
        assert cfg.validation_seed == base.validation_seed
        assert cfg.n_validation == base.n_validation
        assert cfg.n_inner_heavy == base.n_inner_heavy
        assert cfg.n_eval == base.n_eval
        assert cfg.basis_grid == base.basis_grid

    def test_overrides(self):
        cfg = remediated_config(n_fit=64)
        assert cfg.n_fit == 64
        assert cfg.nested_n_inner == 256


# ---------------------------------------------------------------------------
# Targeted diagnostics row
# ---------------------------------------------------------------------------

class TestTargetedDiagnostics:
    def test_row_fields(self, validator, small_states):
        y = validator.denoised_fit_payoffs_sliced(small_states, 0, 12, 42, 1)
        surf = fit_targeted_surface(small_states, y)
        truth = y + validator.fx_term(small_states)
        row = validator.targeted_diagnostics(
            surf, small_states, truth, small_states, truth)
        assert row.fx_mode == "analytic_targeted"
        assert row.n_basis_terms == 9
        assert np.isfinite(row.oos_rmse) and np.isfinite(row.oos_r2)


# ---------------------------------------------------------------------------
# Saved evidence report (the actual Phase 22 Task 1 run)
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not REPORT.exists(), reason="evidence report not built")
class TestSavedReport:
    @pytest.fixture(scope="class")
    def rep(self):
        return json.loads(REPORT.read_text())["validation"]

    def test_verdict_pass(self, rep):
        assert rep["verdict"].startswith("PASS")

    def test_remediation_applied(self, rep):
        rem = rep["remediation_applied"]
        assert rem["fit_n_inner"] >= 8
        assert rem["n_fit"] >= 2000
        assert rem["nested_n_inner"] >= 256
        assert rem["baseline_phase21"]["oos_r2"] < 0.95

    def test_phase22_gate_met(self, rep):
        assert rep["final_selected"]["oos_r2"] >= 0.95
        cap = rep["capital_comparison"]
        assert cap["var_rel_error"] <= 0.10
        assert cap["es_rel_error"] <= 0.10
        assert cap["scr_rel_error"] <= 0.10
        assert rep["final_selected"]["overfit_gap"] <= 0.05
        assert rep["fx_axis_evidence"]["slope_rel_error"] <= 0.10
        assert rep["governed_engine_report"]["leakage"]["leakage_free"]

    def test_improvement_over_baseline(self, rep):
        assert rep["final_selected"]["oos_r2"] > rep["remediation_applied"][
            "baseline_phase21"]["oos_r2"]

    def test_targeted_candidate_documented(self, rep):
        t = rep["targeted_candidate"]
        assert t["fx_mode"] == "analytic_targeted"
        assert t["n_basis_terms"] == 9
        # Honest documentation: targeted competes but result recorded either way.
        assert isinstance(rep["targeted_wins"], bool)

    def test_selection_not_gate_shopped(self, rep):
        # Final surface must be the OOS-RMSE winner across ALL candidates.
        rows = rep["governed_engine_report"]["basis_rows"] + [rep["targeted_candidate"]]
        best = min(rows, key=lambda r: r["oos_rmse"])
        assert rep["final_selected"]["oos_rmse"] == best["oos_rmse"]


def test_use_restrictions_disclose_remediation():
    r = remediation_use_restrictions()
    assert "remediation_scope" in r
    assert "EDUCATIONAL" in r["classification"]
