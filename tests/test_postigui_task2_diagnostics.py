"""Unit tests for Post-Phase-IGUI Task 2 - MR-CAL-1 credentialled-data
calibration-residual diagnostics (gates G1-G6)."""

from __future__ import annotations

import math

import numpy as np

from par_model_v2.calibration import credentialled_residual_diagnostics as D
from par_model_v2.calibration.credentialled_residual_diagnostics import (
    FROZEN_T_COMPONENT_SCR_REFERENCE,
    NESTED_PATHWISE_SCR_REFERENCE,
    run_diagnostics,
    validate,
)


def test_numerics_norm_cdf_ppf_round_trip():
    ps = np.array([0.001, 0.01, 0.25, 0.5, 0.75, 0.99, 0.999])
    z = D._norm_ppf(ps)
    back = D._norm_cdf(z)
    assert np.max(np.abs(back - ps)) < 1e-8


def test_norm_cdf_known_values():
    assert abs(float(D._norm_cdf(np.array([0.0]))[0]) - 0.5) < 1e-12
    assert abs(float(D._norm_cdf(np.array([1.959963984540054]))[0]) - 0.975) < 1e-6


def test_ks_and_ad_on_uniform_small():
    rng = np.random.default_rng(0)
    u = rng.random(5000)
    assert D._ks_statistic(u) < 0.05
    assert D._anderson_darling_uniform(u) < 5.0


def test_g1_frozen_margin_bit_identical():
    p = run_diagnostics()
    inv = p["frozen_margin_invariance"]
    assert inv["bit_identical"] is True
    assert inv["max_abs_dev"] <= D.FROZEN_MARGIN_INVARIANCE_TOL
    assert inv["after"]["frozen_t_component_scr"] == FROZEN_T_COMPONENT_SCR_REFERENCE
    # before == after exactly
    assert inv["before"]["margin_sigma"] == inv["after"]["margin_sigma"]
    assert inv["before"]["margin_weight"] == inv["after"]["margin_weight"]


def test_g2_provenance_synthetic_labelled():
    p = run_diagnostics()
    prov = p["credentialled_reference"]
    assert prov["kind"] == "SYNTHETIC"
    assert "EDUCATIONAL" in prov["label"]
    for k in ("source", "vintage", "n_per_margin", "seed", "credential_basis"):
        assert prov[k]


def test_g3_seven_margins_and_bootstrap():
    p = run_diagnostics()
    gof = p["goodness_of_fit"]
    assert len(gof["per_margin"]) == 7
    assert gof["split"]["leakage_free"] is True
    assert gof["bootstrap_replicates"] >= D.BOOTSTRAP_REPLICATES_GATE
    for name, m in gof["per_margin"].items():
        # PIT-mean and tail quantile reproducible within 5%
        assert m["bootstrap"]["pit_mean"]["se_rel"] <= D.BOOTSTRAP_SE_GATE
        assert m["bootstrap"]["tail_q995"]["se_rel"] <= D.BOOTSTRAP_SE_GATE
        # KS/AD reported with CIs
        for stat in ("ks", "ad", "pit_mean", "tail_q995"):
            for key in ("mean", "se", "ci95_lo", "ci95_hi"):
                assert key in m["bootstrap"][stat]


def test_g4_residual_decomposition_reconciles():
    p = run_diagnostics()
    dec = p["residual_decomposition"]
    total = NESTED_PATHWISE_SCR_REFERENCE - FROZEN_T_COMPONENT_SCR_REFERENCE
    assert abs(dec["total_gap_vs_nested"] - total) < 1e-9
    recon = dec["copula_form_residual_frozen_t"] + dec["margin_calibration_residual_by_difference"]
    assert abs(recon - dec["total_gap_vs_nested"]) <= dec["reconciliation_abs_tol"]
    assert dec["reconciles_within_tol"] is True
    assert dec["headline_unmoved"] is True
    assert abs(dec["copula_form_share"] + dec["margin_calibration_share"] - 1.0) <= 1e-9
    # copula form is the dominant share (Phase 26-29 finding)
    assert dec["copula_form_share"] > dec["margin_calibration_share"]


def test_g5_credibility_reported_not_applied_and_immaterial():
    p = run_diagnostics()
    cred = p["credibility"]
    assert cred["applied"] is False
    assert abs(cred["indicated_rel_dscr_total"]) <= cred["materiality_threshold_rel"]
    assert cred["is_material"] is False
    assert "open_model_risk" not in cred
    for name, m in cred["per_margin"].items():
        assert 0.0 <= m["credibility_Z"] <= 1.0
        assert m["n_full_credibility"] > 0


def test_g5_material_branch_opens_model_risk(monkeypatch):
    # inject a large reference perturbation -> indicated dSCR must exceed 1%
    big = np.array([0.20, 0.18, 0.22, 0.15, 0.19, 0.16, 0.21])
    monkeypatch.setattr(D, "_REFERENCE_SIGMA_PERTURB", big)
    p = run_diagnostics()
    cred = p["credibility"]
    assert cred["is_material"] is True
    assert cred["applied"] is False          # still NOT applied
    assert "open_model_risk" in cred
    assert cred["open_model_risk"]["status"] == "OPEN"


def test_g6_idempotent_digest():
    p1 = run_diagnostics()
    p2 = run_diagnostics()
    assert p1["digest"] == p2["digest"]
    assert len(p1["digest"]) == 64


def test_full_gate_passes():
    p = run_diagnostics()
    g = validate(p)
    assert g["ok"] is True
    assert g["n_checks"] == 16
    assert all(g["checks"].values())


if __name__ == "__main__":
    import sys
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for fn in fns:
        try:
            # crude monkeypatch shim for the standalone harness
            if "monkeypatch" in fn.__code__.co_varnames:
                class _MP:
                    def __init__(self): self._saved = []
                    def setattr(self, obj, name, val):
                        self._saved.append((obj, name, getattr(obj, name)))
                        setattr(obj, name, val)
                    def undo(self):
                        for o, n, v in reversed(self._saved): setattr(o, n, v)
                mp = _MP()
                try:
                    fn(mp)
                finally:
                    mp.undo()
            else:
                fn()
            print(f"PASS {fn.__name__}")
        except Exception as e:  # noqa
            failed += 1
            print(f"FAIL {fn.__name__}: {e}")
    print(f"\n{len(fns)-failed}/{len(fns)} passed")
    sys.exit(1 if failed else 0)
