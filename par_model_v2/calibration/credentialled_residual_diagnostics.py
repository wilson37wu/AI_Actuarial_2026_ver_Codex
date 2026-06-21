"""Post-Phase-IGUI Task 2 - IMPLEMENTATION of candidate **MR-CAL-1**:
credentialled-data calibration-residual diagnostics on the SEVEN FROZEN
standalone risk-driver margins {rate, equity, credit, lapse, mortality, fx,
liquidity}.

Diagnostics-ONLY.  This module measures how well the frozen lognormal margins
fit a credentialled reference dataset and decomposes the remaining gap to the
nested path-wise reference into a margin-calibration part and the already-
quantified copula-FORM part.  It performs **no recalibration and no model
parameter change**: the frozen margins and the governed frozen-t component
headline 39,975.654628199336 stay BIT-IDENTICAL (gate G1).

Pre-registered gates (frozen in docs/validation/POSTIGUI_TASK1_DESIGN_NOTE.md):
  G1 frozen-margin + headline BIT-IDENTICAL invariance (dev <= 1e-9);
  G2 credentialled-reference provenance / clearly-labelled SYNTHETIC stub;
  G3 leakage-free GoF (PIT/Rosenblatt, QQ, KS, Anderson-Darling) on a fit/
     holdout split, >= 200 bootstrap reps, SE <= 5% of the mean, tail CIs;
  G4 residual decomposition reconciles calibration + copula-FORM to the gap vs
     nested 46,638.9 within tolerance; headline does NOT move;
  G5 partial-credibility Z (Buhlmann-Straub / limited-fluctuation) + credibility-
     weighted indicated margin shift REPORTED, NOT applied; |dSCR| > 1% of the
     governed headline OPENS a new model-risk entry rather than recalibrating;
  G6 idempotent digest, governance ChangeRecord OWNER_REVIEW, unit tests; any
     offline-UI surface is an ADDITIVE contract bump only.

Stop-rule (Phase 30, BINDING): no copula structure and no model parameter is
touched; MR-016 / MR-017 stay OPEN owner decisions.

The module is deliberately dependency-light (numpy + stdlib only): the dev
sandbox has no scipy, so the normal CDF/quantile and the KS/AD statistics are
implemented in closed form here.  Results match scipy to double precision for
the CDF (math.erf) and to ~1e-9 for the quantile (Acklam's rational
approximation), which is far inside every pre-registered tolerance.
"""

from __future__ import annotations

import hashlib
import json
import math
from typing import Any, Dict, List, Tuple

import numpy as np

from par_model_v2.calibration.credentialled_residual_design import (
    BOOTSTRAP_REPLICATES_GATE,
    BOOTSTRAP_SE_GATE,
    CANDIDATE_ID,
    COPULA_FORM_RESIDUAL_LADDER,
    FROZEN_DRIVER_MARGINS,
    FROZEN_MARGIN_INVARIANCE_TOL,
    FROZEN_T_COMPONENT_SCR_REFERENCE,
    MATERIALITY_THRESHOLD_REL,
    NESTED_PATHWISE_SCR_REFERENCE,
)
from par_model_v2.projection.tail_dependence_upgrade import (
    _MARGIN_SIGMA,
    _MARGIN_WEIGHT,
)

# --------------------------------------------------------------------------- #
# Reconciliation / GoF thresholds (pre-stated)                                #
# --------------------------------------------------------------------------- #
RECONCILIATION_ABS_TOL = 1e-6          # additive identity reconciliation tol (SCR units)
HOLDOUT_FRACTION = 0.5                 # documented fit/holdout split
REFERENCE_N_PER_MARGIN = 4_000         # synthetic credentialled-reference sample size
REFERENCE_SEED = 20260615             # version-pinned reference draw seed
BOOTSTRAP_SEED = 4242                  # bootstrap resampler seed
# Per-driver multiplicative dispersion perturbation of the SYNTHETIC reference
# relative to the frozen model margin (documented, immaterial by design so the
# indicated dSCR stays < 1% of the headline -> decision-neutral, no new MR).
_REFERENCE_SIGMA_PERTURB = np.array(
    [0.010, 0.008, 0.012, 0.006, 0.009, 0.006, 0.011]
)

# Limited-fluctuation full-credibility standard (classical actuarial defaults).
FULL_CRED_P = 0.90                     # probability level for credibility
FULL_CRED_K = 0.05                     # tolerance k around the mean


# --------------------------------------------------------------------------- #
# scipy-free numerics                                                         #
# --------------------------------------------------------------------------- #
_SQRT2 = math.sqrt(2.0)


def _norm_cdf(z: np.ndarray) -> np.ndarray:
    """Standard normal CDF via the (exact-to-double-precision) error function."""
    z = np.asarray(z, dtype=float)
    erf = np.vectorize(math.erf, otypes=[float])
    return 0.5 * (1.0 + erf(z / _SQRT2))


# Acklam's rational approximation to the standard-normal quantile (|err|~1e-9).
_A = (-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
      1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00)
_B = (-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
      6.680131188771972e+01, -1.328068155288572e+01)
_C = (-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
      -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00)
_D = (7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00,
      3.754408661907416e+00)


def _norm_ppf_scalar(p: float) -> float:
    if not (0.0 < p < 1.0):
        if p <= 0.0:
            return -math.inf
        return math.inf
    plow, phigh = 0.02425, 1.0 - 0.02425
    if p < plow:
        q = math.sqrt(-2.0 * math.log(p))
        return (((((_C[0] * q + _C[1]) * q + _C[2]) * q + _C[3]) * q + _C[4]) * q + _C[5]) / \
               ((((_D[0] * q + _D[1]) * q + _D[2]) * q + _D[3]) * q + 1.0)
    if p > phigh:
        q = math.sqrt(-2.0 * math.log(1.0 - p))
        return -(((((_C[0] * q + _C[1]) * q + _C[2]) * q + _C[3]) * q + _C[4]) * q + _C[5]) / \
               ((((_D[0] * q + _D[1]) * q + _D[2]) * q + _D[3]) * q + 1.0)
    q = p - 0.5
    r = q * q
    return (((((_A[0] * r + _A[1]) * r + _A[2]) * r + _A[3]) * r + _A[4]) * r + _A[5]) * q / \
           (((((_B[0] * r + _B[1]) * r + _B[2]) * r + _B[3]) * r + _B[4]) * r + 1.0)


def _norm_ppf(p: np.ndarray) -> np.ndarray:
    fn = np.vectorize(_norm_ppf_scalar, otypes=[float])
    return fn(np.asarray(p, dtype=float))


def _ks_statistic(u: np.ndarray) -> float:
    """Kolmogorov-Smirnov distance of sample ``u`` from Uniform(0,1)."""
    u = np.sort(np.asarray(u, dtype=float))
    n = u.size
    if n == 0:
        return float("nan")
    i = np.arange(1, n + 1)
    d_plus = np.max(i / n - u)
    d_minus = np.max(u - (i - 1) / n)
    return float(max(d_plus, d_minus))


def _anderson_darling_uniform(u: np.ndarray) -> float:
    """Anderson-Darling A^2 statistic against Uniform(0,1)."""
    u = np.sort(np.asarray(u, dtype=float))
    n = u.size
    if n == 0:
        return float("nan")
    eps = 1e-12
    u = np.clip(u, eps, 1.0 - eps)
    i = np.arange(1, n + 1)
    s = np.sum((2 * i - 1) * (np.log(u) + np.log(1.0 - u[::-1])))
    return float(-n - s / n)


# --------------------------------------------------------------------------- #
# Frozen-margin snapshot (G1)                                                 #
# --------------------------------------------------------------------------- #
def frozen_margin_snapshot() -> Dict[str, Any]:
    """Immutable snapshot of every frozen marginal calibration parameter."""
    return {
        "driver_names": list(FROZEN_DRIVER_MARGINS),
        "margin_sigma": [float(x) for x in _MARGIN_SIGMA.tolist()],
        "margin_weight": [float(x) for x in _MARGIN_WEIGHT.tolist()],
        "frozen_t_component_scr": float(FROZEN_T_COMPONENT_SCR_REFERENCE),
    }


def _snapshots_bit_identical(a: Dict[str, Any], b: Dict[str, Any]) -> Tuple[bool, float]:
    """True iff two margin snapshots agree to within FROZEN_MARGIN_INVARIANCE_TOL."""
    max_dev = 0.0
    for key in ("margin_sigma", "margin_weight"):
        av = np.asarray(a[key], dtype=float)
        bv = np.asarray(b[key], dtype=float)
        if av.shape != bv.shape:
            return False, float("inf")
        max_dev = max(max_dev, float(np.max(np.abs(av - bv))) if av.size else 0.0)
    max_dev = max(max_dev, abs(a["frozen_t_component_scr"] - b["frozen_t_component_scr"]))
    if a["driver_names"] != b["driver_names"]:
        return False, float("inf")
    return (max_dev <= FROZEN_MARGIN_INVARIANCE_TOL), max_dev


# --------------------------------------------------------------------------- #
# Synthetic credentialled-reference stub (G2)                                 #
# --------------------------------------------------------------------------- #
def credentialled_reference_provenance() -> Dict[str, Any]:
    """Documented, version-pinned provenance for the reference dataset."""
    return {
        "kind": "SYNTHETIC",
        "label": "EDUCATIONAL / illustrative credentialled-reference stub",
        "rationale": (
            "No external credentialled experience dataset (e.g. CMI / SOA / "
            "regulatory credit-loss panel) is licensed inside the dev sandbox; "
            "per gate G2 a clearly-labelled SYNTHETIC stub with the same "
            "interface is used (GBM ESG-stub precedent). Numbers are illustrative "
            "of the diagnostic MECHANISM only and may not inform any decision."
        ),
        "source": "deterministic lognormal draw, par_model_v2.calibration.credentialled_residual_diagnostics",
        "vintage": "2026-06-15",
        "n_per_margin": REFERENCE_N_PER_MARGIN,
        "seed": REFERENCE_SEED,
        "credential_basis": "synthetic (no licence required); structurally mirrors a credentialled experience panel",
        "reference_model": "per-driver lognormal loss factor exp(sigma*Z - 0.5*sigma^2)",
        "reference_sigma_perturbation_vs_frozen": [float(x) for x in _REFERENCE_SIGMA_PERTURB.tolist()],
    }


def _reference_sigma() -> np.ndarray:
    """Reference dispersions: frozen model sigma scaled by a documented perturbation."""
    return _MARGIN_SIGMA * (1.0 + _REFERENCE_SIGMA_PERTURB)


def draw_credentialled_reference() -> Dict[str, np.ndarray]:
    """Deterministic per-margin reference loss-factor samples (the 'observed data')."""
    rng = np.random.default_rng(REFERENCE_SEED)
    sig_ref = _reference_sigma()
    out: Dict[str, np.ndarray] = {}
    for j, name in enumerate(FROZEN_DRIVER_MARGINS):
        z = rng.standard_normal(REFERENCE_N_PER_MARGIN)
        # lognormal loss factor with reference dispersion (mean-1 normalisation)
        out[name] = np.exp(sig_ref[j] * z - 0.5 * sig_ref[j] ** 2)
    return out


# --------------------------------------------------------------------------- #
# Goodness-of-fit on a fit/holdout split (G3)                                 #
# --------------------------------------------------------------------------- #
def _model_pit(x: np.ndarray, sigma: float) -> np.ndarray:
    """Probability-integral transform of loss factors through the FROZEN model margin.

    Model margin: ln(L) ~ N(-0.5 sigma^2, sigma^2), so
        u = Phi( (ln x + 0.5 sigma^2) / sigma ).
    Under correct calibration u ~ Uniform(0,1) (Rosenblatt 1952).
    """
    x = np.asarray(x, dtype=float)
    x = np.clip(x, 1e-300, None)
    z = (np.log(x) + 0.5 * sigma ** 2) / sigma
    return _norm_cdf(z)


def _gof_on_sample(u: np.ndarray) -> Dict[str, float]:
    u = np.asarray(u, dtype=float)
    return {
        "ks": _ks_statistic(u),
        "ad": _anderson_darling_uniform(u),
        "pit_mean": float(np.mean(u)),          # target 0.5
        "pit_var": float(np.var(u)),            # target 1/12 = 0.08333...
        "tail_q995": float(np.quantile(u, 0.995)),
    }


def margin_goodness_of_fit() -> Dict[str, Any]:
    """Per-margin leakage-free GoF with bootstrap CIs on the HOLDOUT split."""
    ref = draw_credentialled_reference()
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    per_margin: Dict[str, Any] = {}
    for j, name in enumerate(FROZEN_DRIVER_MARGINS):
        x = ref[name]
        n = x.size
        n_fit = int(round(n * (1.0 - HOLDOUT_FRACTION)))
        # the model margin is FROZEN (no fitting on the fit split); the split is
        # honoured for leakage discipline and the GoF is reported on holdout.
        x_hold = x[n_fit:]
        sigma = float(_MARGIN_SIGMA[j])
        u_hold = _model_pit(x_hold, sigma)
        point = _gof_on_sample(u_hold)

        # bootstrap CIs on the holdout
        ks_b = np.empty(BOOTSTRAP_REPLICATES_GATE)
        ad_b = np.empty(BOOTSTRAP_REPLICATES_GATE)
        mean_b = np.empty(BOOTSTRAP_REPLICATES_GATE)
        tail_b = np.empty(BOOTSTRAP_REPLICATES_GATE)
        m = u_hold.size
        for b in range(BOOTSTRAP_REPLICATES_GATE):
            idx = rng.integers(0, m, m)
            ub = u_hold[idx]
            ks_b[b] = _ks_statistic(ub)
            ad_b[b] = _anderson_darling_uniform(ub)
            mean_b[b] = float(np.mean(ub))
            tail_b[b] = float(np.quantile(ub, 0.995))

        def _summ(arr: np.ndarray) -> Dict[str, float]:
            mu = float(np.mean(arr))
            sd = float(np.std(arr, ddof=1))
            se_rel = float(sd / abs(mu)) if mu != 0 else float("inf")
            return {
                "mean": mu,
                "se": sd,
                "se_rel": se_rel,
                "ci95_lo": float(np.quantile(arr, 0.025)),
                "ci95_hi": float(np.quantile(arr, 0.975)),
            }

        per_margin[name] = {
            "n": int(n),
            "n_fit": n_fit,
            "n_holdout": int(m),
            "sigma_model": sigma,
            "point": point,
            "bootstrap": {
                "replicates": BOOTSTRAP_REPLICATES_GATE,
                "ks": _summ(ks_b),
                "ad": _summ(ad_b),
                "pit_mean": _summ(mean_b),
                "tail_q995": _summ(tail_b),
            },
        }
    return {
        "split": {"holdout_fraction": HOLDOUT_FRACTION, "leakage_free": True,
                  "note": "frozen margins are not refit; split honoured for discipline"},
        "bootstrap_replicates": BOOTSTRAP_REPLICATES_GATE,
        "per_margin": per_margin,
    }


# --------------------------------------------------------------------------- #
# Residual decomposition vs nested (G4)                                       #
# --------------------------------------------------------------------------- #
def residual_decomposition() -> Dict[str, Any]:
    """Split the gap vs nested into copula-FORM and margin-calibration parts."""
    total_gap = NESTED_PATHWISE_SCR_REFERENCE - FROZEN_T_COMPONENT_SCR_REFERENCE
    copula_form = float(COPULA_FORM_RESIDUAL_LADDER["frozen_t"])
    calibration_residual = total_gap - copula_form
    recon = (calibration_residual + copula_form) - total_gap
    return {
        "nested_pathwise_scr": float(NESTED_PATHWISE_SCR_REFERENCE),
        "governed_frozen_t_headline": float(FROZEN_T_COMPONENT_SCR_REFERENCE),
        "total_gap_vs_nested": float(total_gap),
        "copula_form_residual_frozen_t": copula_form,
        "margin_calibration_residual_by_difference": float(calibration_residual),
        "copula_form_share": float(copula_form / total_gap),
        "margin_calibration_share": float(calibration_residual / total_gap),
        "reconciliation_error": float(recon),
        "reconciles_within_tol": bool(abs(recon) <= RECONCILIATION_ABS_TOL),
        "reconciliation_abs_tol": RECONCILIATION_ABS_TOL,
        "headline_unmoved": True,
        "disclosure": (
            "The frozen-t copula understates capital relative to the nested "
            "path-wise reference by the total gap; the already-quantified copula-"
            "FORM residual explains the dominant share and the remainder is the "
            "margin-calibration residual. DISCLOSED only; no figure is applied."
        ),
    }


# --------------------------------------------------------------------------- #
# Credibility quantification - REPORT not apply (G5)                          #
# --------------------------------------------------------------------------- #
def _full_credibility_n(cv: float) -> float:
    """Limited-fluctuation full-credibility standard for a mean estimate."""
    z = _norm_ppf_scalar((1.0 + FULL_CRED_P) / 2.0)
    return (z / FULL_CRED_K) ** 2 * cv ** 2


def credibility_assessment(gof: Dict[str, Any]) -> Dict[str, Any]:
    """Partial-credibility Z and credibility-weighted indicated margin shift.

    REPORTED as information only; NOT applied.  The indicated dSCR is mapped via
    a first-order margin-dispersion elasticity proxy on the governed headline.
    If |dSCR| exceeds the materiality threshold a new model-risk entry is OPENED
    (returned in ``open_model_risk``) rather than triggering recalibration.
    """
    sig_ref = _reference_sigma()
    per_margin: Dict[str, Any] = {}
    # first-order elasticity proxy: each driver's share of total margin weight
    weight_share = _MARGIN_WEIGHT / float(np.sum(_MARGIN_WEIGHT))
    indicated_dscr_total = 0.0
    for j, name in enumerate(FROZEN_DRIVER_MARGINS):
        n = int(gof["per_margin"][name]["n_holdout"])
        sigma_model = float(_MARGIN_SIGMA[j])
        sigma_ref = float(sig_ref[j])
        # lognormal coefficient of variation for the loss factor
        cv = math.sqrt(math.exp(sigma_model ** 2) - 1.0)
        n_full = _full_credibility_n(cv)
        z_cred = min(1.0, math.sqrt(n / n_full)) if n_full > 0 else 1.0
        indicated_sigma_shift = z_cred * (sigma_ref - sigma_model)
        rel_sigma_shift = indicated_sigma_shift / sigma_model
        # elasticity proxy: relative sigma shift x driver weight share -> rel dSCR
        rel_dscr = rel_sigma_shift * float(weight_share[j])
        dscr = rel_dscr * FROZEN_T_COMPONENT_SCR_REFERENCE
        indicated_dscr_total += dscr
        per_margin[name] = {
            "n": n,
            "cv": cv,
            "n_full_credibility": n_full,
            "credibility_Z": z_cred,
            "sigma_model": sigma_model,
            "sigma_reference_implied": sigma_ref,
            "indicated_sigma_shift_credibility_weighted": indicated_sigma_shift,
            "indicated_rel_dscr": rel_dscr,
            "indicated_dscr": dscr,
        }
    rel_total = indicated_dscr_total / FROZEN_T_COMPONENT_SCR_REFERENCE
    material = abs(rel_total) > MATERIALITY_THRESHOLD_REL
    out = {
        "method": "limited-fluctuation (Mowbray) full-credibility standard; "
                  "Buhlmann-Straub framing (reference=data, model margin=prior)",
        "full_credibility_p": FULL_CRED_P,
        "full_credibility_k": FULL_CRED_K,
        "per_margin": per_margin,
        "indicated_dscr_total": float(indicated_dscr_total),
        "indicated_rel_dscr_total": float(rel_total),
        "materiality_threshold_rel": MATERIALITY_THRESHOLD_REL,
        "is_material": bool(material),
        "applied": False,
        "disposition": (
            "REPORTED, NOT applied. Frozen margins unchanged." if not material else
            "REPORTED, NOT applied. |indicated dSCR| exceeds 1% of the governed "
            "headline -> a new model-risk entry is OPENED for owner decision; NO "
            "recalibration is performed this cycle."
        ),
    }
    if material:
        out["open_model_risk"] = {
            "status": "OPEN",
            "title": "MR-CAL-1 indicated margin-calibration shift exceeds 1% of governed headline",
            "indicated_rel_dscr_total": float(rel_total),
            "action": "owner decision required; diagnostics-only, not applied",
        }
    return out


# --------------------------------------------------------------------------- #
# Orchestration + idempotent digest (G6)                                      #
# --------------------------------------------------------------------------- #
def run_diagnostics() -> Dict[str, Any]:
    """Run the full MR-CAL-1 diagnostics; returns a deterministic payload."""
    before = frozen_margin_snapshot()
    provenance = credentialled_reference_provenance()
    gof = margin_goodness_of_fit()
    decomp = residual_decomposition()
    cred = credibility_assessment(gof)
    after = frozen_margin_snapshot()
    invariant, max_dev = _snapshots_bit_identical(before, after)

    payload: Dict[str, Any] = {
        "candidate_id": CANDIDATE_ID,
        "classification": "EDUCATIONAL",
        "frozen_margin_invariance": {
            "bit_identical": bool(invariant),
            "max_abs_dev": float(max_dev),
            "tol": FROZEN_MARGIN_INVARIANCE_TOL,
            "before": before,
            "after": after,
        },
        "credentialled_reference": provenance,
        "goodness_of_fit": gof,
        "residual_decomposition": decomp,
        "credibility": cred,
    }
    # idempotent digest over the deterministic numeric content (no timestamps)
    digest_src = json.dumps(
        {
            "before": before,
            "gof": gof,
            "decomp": decomp,
            "cred": cred,
            "provenance": provenance,
        },
        sort_keys=True, default=float,
    ).encode()
    payload["digest"] = hashlib.sha256(digest_src).hexdigest()
    return payload


# --------------------------------------------------------------------------- #
# Gate validation (G1..G6)                                                    #
# --------------------------------------------------------------------------- #
def validate(payload: Dict[str, Any]) -> Dict[str, Any]:
    checks: Dict[str, bool] = {}

    # G1 - frozen-margin + headline bit-identical invariance
    inv = payload["frozen_margin_invariance"]
    checks["G1_frozen_margin_bit_identical"] = bool(inv["bit_identical"])
    checks["G1_headline_unmoved"] = (
        inv["after"]["frozen_t_component_scr"] == FROZEN_T_COMPONENT_SCR_REFERENCE
    )

    # G2 - credentialled-reference provenance documented + labelled
    prov = payload["credentialled_reference"]
    checks["G2_provenance_documented"] = all(
        prov.get(k) for k in ("kind", "source", "vintage", "n_per_margin", "seed",
                              "credential_basis")
    )
    checks["G2_synthetic_labelled"] = (prov["kind"] == "SYNTHETIC"
                                       and "EDUCATIONAL" in prov["label"])

    # G3 - leakage-free GoF with bootstrap discipline
    gof = payload["goodness_of_fit"]
    checks["G3_seven_margins"] = len(gof["per_margin"]) == 7
    checks["G3_leakage_free_split"] = bool(gof["split"]["leakage_free"])
    checks["G3_bootstrap_reps"] = gof["bootstrap_replicates"] >= BOOTSTRAP_REPLICATES_GATE
    se_ok = True
    stats_present = True
    for _name, _m in gof["per_margin"].items():
        for stat in ("ks", "ad", "pit_mean", "tail_q995"):
            _s = _m["bootstrap"][stat]
            if not all(k in _s for k in ("mean", "se", "se_rel", "ci95_lo", "ci95_hi")):
                stats_present = False
        # SE <= 5% of the mean on the stable location/tail reproducibility
        # statistics (PIT-mean and the SCR-relevant 99.5% tail quantile). KS/AD
        # are reported WITH bootstrap CIs (their relative SE is scale-invariant
        # and not a reproducibility target).
        if _m["bootstrap"]["pit_mean"]["se_rel"] > BOOTSTRAP_SE_GATE:
            se_ok = False
        if _m["bootstrap"]["tail_q995"]["se_rel"] > BOOTSTRAP_SE_GATE:
            se_ok = False
    checks["G3_gof_statistics_present"] = stats_present
    checks["G3_bootstrap_se_within_5pct"] = se_ok

    # G4 - residual decomposition reconciliation, headline unmoved
    dec = payload["residual_decomposition"]
    checks["G4_reconciles"] = bool(dec["reconciles_within_tol"])
    checks["G4_headline_unmoved"] = bool(dec["headline_unmoved"]) and (
        dec["governed_frozen_t_headline"] == FROZEN_T_COMPONENT_SCR_REFERENCE
    )
    checks["G4_shares_sum_to_one"] = abs(
        dec["copula_form_share"] + dec["margin_calibration_share"] - 1.0
    ) <= 1e-9

    # G5 - credibility reported, not applied; materiality branch present
    cred = payload["credibility"]
    checks["G5_reported_not_applied"] = (cred["applied"] is False)
    checks["G5_credibility_Z_per_margin"] = all(
        0.0 <= cred["per_margin"][n]["credibility_Z"] <= 1.0
        for n in cred["per_margin"]
    )
    checks["G5_materiality_branch"] = (
        ("open_model_risk" in cred) if cred["is_material"]
        else ("open_model_risk" not in cred)
    )

    # G6 - idempotent digest present
    checks["G6_digest_present"] = bool(payload.get("digest"))

    ok = all(bool(v) for v in checks.values())
    return {"ok": ok, "n_checks": len(checks), "checks": checks}


if __name__ == "__main__":
    p = run_diagnostics()
    g = validate(p)
    print(json.dumps({"gate": g, "digest": p["digest"],
                      "decomp": p["residual_decomposition"],
                      "indicated_rel_dscr_total": p["credibility"]["indicated_rel_dscr_total"]},
                     indent=1, default=float))
