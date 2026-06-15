"""Unit tests for Post-Phase-IGUI Task 7 - MR-VR-2 OUTER-loop scrambled-Sobol RQMC +
control-variate variance reduction for the 99.5% SCR estimator (gates G1-G6)."""

from __future__ import annotations

import numpy as np

import par_model_v2.projection.outer_loop_variance_reduction as V
from par_model_v2.projection.outer_loop_variance_reduction import (
    FROZEN_T_COMPONENT_SCR_REFERENCE,
    analytic_expected_loss,
    analytic_scr,
    fit_control_beta,
    proxy_mean_closed_form,
    run_study,
    validate,
)

# A single shared study run (the study is deterministic / idempotent).
_P = run_study()
_G = validate(_P)


def test_numerics_norm_cdf_ppf_round_trip():
    ps = np.array([0.001, 0.01, 0.25, 0.5, 0.75, 0.99, 0.995, 0.999])
    z = V._norm_ppf(ps)
    back = V._norm_cdf(z)
    assert np.max(np.abs(back - ps)) < 1e-8


def test_closed_form_moments_match_mc():
    # analytic E[L] and E[P] recovered by large crude MC
    x = V.slice_stable_normals(np.random.SeedSequence(7), 600_000)
    assert abs(float(np.mean(V.loss(x))) - analytic_expected_loss()) / analytic_expected_loss() < 0.01
    assert abs(float(np.mean(V.proxy(x))) - proxy_mean_closed_form()) / proxy_mean_closed_form() < 0.01
    # analytic SCR recovered by large crude MC (loss is strictly increasing in X)
    L = V.loss(x)
    mc_scr = float(np.quantile(L, V.ALPHA) - np.mean(L))
    assert abs(mc_scr - analytic_scr()) / analytic_scr() < 0.02
    assert analytic_scr() > 0.0


def test_g1_governed_headline_bit_identical():
    inv = _P["governed_headline_invariance"]
    assert inv["bit_identical"] is True
    assert inv["max_abs_dev"] <= V.ESTIMATOR_INVARIANCE_TOL
    assert inv["after"]["frozen_t_component_scr"] == FROZEN_T_COMPONENT_SCR_REFERENCE
    assert inv["before"] == inv["after"]
    assert inv["additive_disclosed_not_a_swap"] is True


def test_g2_control_beta_out_of_sample():
    fit = fit_control_beta()
    # beta fit on a held-out pilot, with its own seed
    assert fit["pilot_n"] >= 10_000
    assert fit["pilot_seed"] == V.PILOT_SEED
    # control-target correlation is strong and the theoretical reduction is useful
    assert 0.0 < fit["rho"] < 1.0
    assert fit["one_over_1_minus_rho2"] >= V.MIN_VARIANCE_REDUCTION_RATIO


def test_g2_unbiasedness_mean_and_scr():
    rep = _P["replicate_study"]
    unb = rep["unbiasedness"]
    assert rep["n_replicates"] >= V.BOOTSTRAP_REPLICATES_GATE
    assert unb["control_variate_rel_vs_crude"] <= V.UNBIASEDNESS_TOL_REL
    assert unb["sobol_rel_vs_crude"] <= V.UNBIASEDNESS_TOL_REL
    assert unb["stratified_rel_vs_crude"] <= V.UNBIASEDNESS_TOL_REL
    assert unb["all_within_tol"] is True
    assert unb["crude_rel_vs_analytic"] < 0.01
    # the control-variate mean-leg ratio tracks the theoretical 1/(1-rho^2)
    cv_ratio = rep["variance_reduction_ratios"]["control_variate"]["ratio"]
    theo = rep["control_one_over_1_minus_rho2"]
    assert abs(cv_ratio - theo) / theo < 0.25
    # SCR target is unbiased
    sunb = _P["scr_tail_study"]["unbiasedness_scr"]
    assert sunb["crude_rel_vs_analytic"] <= V.UNBIASEDNESS_TOL_REL
    assert sunb["rqmc_plus_cv_rel_vs_crude"] <= V.UNBIASEDNESS_TOL_REL


def test_g3_scr_variance_reduction_ratios_with_ci_and_ess():
    scr = _P["scr_tail_study"]
    ratios = scr["variance_reduction_ratios"]
    for k in ("sobol_rqmc", "control_variate", "stratified", "rqmc_plus_cv"):
        v = ratios[k]
        for key in ("ratio", "ci95_lo", "ci95_hi"):
            assert key in v
    # at least one technique is useful (>= 1.5x) on the SCR target
    assert scr["any_useful_ge_1p5x"] is True
    # RQMC and stratification (the quantile-leg levers) are useful on the SCR target
    assert ratios["sobol_rqmc"]["ratio"] >= V.MIN_VARIANCE_REDUCTION_RATIO
    assert ratios["stratified"]["ratio"] >= V.MIN_VARIANCE_REDUCTION_RATIO
    # ESS present and positive
    assert set(scr["effective_sample_size"]) == set(ratios)
    assert all(x > 0 for x in scr["effective_sample_size"].values())
    # rho and 1/(1-rho^2) disclosed on the SCR study
    assert "control_rho" in scr and "control_one_over_1_minus_rho2" in scr


def test_g3_control_variate_alone_measured_on_quantile():
    # MEASURED, not assumed: the control variate ALONE acts on the cheap mean leg, so
    # its SCR-target ratio is sub-useful (the honest OUTER-loop analogue of MR-VR-1's
    # antithetic-ineffective-at-99.5% disclosure).
    scr = _P["scr_tail_study"]
    cv_ratio = scr["variance_reduction_ratios"]["control_variate"]["ratio"]
    assert cv_ratio < V.MIN_VARIANCE_REDUCTION_RATIO
    assert "disclosure" in scr and scr["disclosure"]
    # the combined RQMC+CV and the quantile-leg levers beat control-variate-alone
    assert scr["variance_reduction_ratios"]["rqmc_plus_cv"]["ratio"] > cv_ratio


def test_g4_slice_stable_reproducibility_and_idempotent_digest():
    a = V.slice_stable_normals(np.random.SeedSequence(99), 1234, n_slices=4)
    a2 = V.slice_stable_normals(np.random.SeedSequence(99), 1234, n_slices=4)
    assert np.array_equal(a, a2)
    assert a.shape == (1234,)
    # idempotent digest across full re-runs
    p2 = run_study()
    assert _P["digest"] == p2["digest"]
    assert len(_P["digest"]) == 64
    for k in ("n_outer", "n_outer_tail", "n_replicates", "sobol_dimension", "seeds"):
        assert k in _P["grid"]
    assert "sobol_scramble" in _P["grid"]["seeds"]


def test_g5_adoption_materiality_reported_not_applied():
    mat = _P["adoption_materiality"]
    assert mat["applied"] is False
    assert abs(mat["indicated_rel_dscr"]) <= mat["materiality_threshold_rel"]
    assert mat["is_material"] is False
    assert "open_model_risk" not in mat
    assert mat["scr_proxy_analytic"] > 0


def test_g5_material_branch_opens_model_risk(monkeypatch):
    # Exercise the material BRANCH without gate-shopping the pre-registered denominator:
    # tighten the materiality threshold so the (small, non-zero) indicated dSCR trips it
    # -> a new model-risk entry must be OPENED, still NOT applied.
    monkeypatch.setattr(V, "MATERIALITY_THRESHOLD_REL", 1e-15)
    fit = fit_control_beta()
    mat = V.adoption_materiality(fit)
    assert abs(mat["indicated_rel_dscr"]) > 1e-15
    assert mat["is_material"] is True
    assert mat["applied"] is False
    assert "open_model_risk" in mat
    assert mat["open_model_risk"]["status"] == "OPEN"


def test_g6_classification_and_techniques():
    assert _P["classification"] == "EFFICIENCY"
    assert len(_P["vr_techniques"]) == 4
    assert "crude_iid" in _P["vr_techniques"]
    assert "control_variate" in _P["vr_techniques"]
    assert "sobol_rqmc" in _P["vr_techniques"]


def test_full_gate_passes():
    assert _G["ok"] is True
    assert _G["n_checks"] == 20
    assert all(_G["checks"].values())


if __name__ == "__main__":
    import sys
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for fn in fns:
        try:
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
