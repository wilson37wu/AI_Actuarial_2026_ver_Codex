"""
Phase 25 Task 3 - matching path-wise proxy basis feature + OOS re-validation.

Phase 25 Task 2 moved the governed bonus-cut decision INTO the inner paths of
the nested truth (path-wise declaration: the retained-bonus factor re-evaluated
at every inner month from CR_{i,t} = a_ref / RemPV0_{i,t}).  The LSMC proxy,
however, cannot run inner paths.  This module gives the proxy the MATCHING
analytic post-composition action basis (the G1 identical-basis convention),
selecting between the TWO candidates pre-registered in the Phase 25 Task 1
design note s5 / Task 2 report:

(a) zero-shock expected-path relieved amount with a single fit-calibrated
    level factor (the P24T3 ``kappa`` pattern) -
    :func:`deterministic_pathwise_relieved` +
    :func:`calibrate_pathwise_level_factor`; and

(b) a learned-feature-free analytic response surface on the node coverage
    state: the rule's relief curve smoothed over an effective lognormal
    dispersion of the path-wise coverage ratio (Gauss-Hermite quadrature),

        relieved_hat(x) = alpha * phi_sigma(CR_node(x)) * clip(B_hat, 0, L_hat),
        phi_sigma(c)    = E_Z[ relief_fraction(c * exp(sigma Z - sigma^2/2)) ],

    with exactly TWO scalars (sigma, alpha) calibrated on the FIT sample ONLY
    (leakage-free; no per-state learned coefficients) -
    :func:`smoothed_relief_response` + :func:`calibrate_pathwise_response_surface`.

Candidate selection is made on FIT-sample evidence only and both candidates'
diagnostics are DISCLOSED in the validation report (no gate-shopping: the
gates are the unchanged Phase 22 set, fixed in the design note before any
real-data benchmark).  Rationale recorded here: the zero-shock path misses
the diffusion-driven cuts at mid-coverage nodes (relief is a convex, locally
triggered function of the path-wise CR), so a single level factor is badly
state-dependent; the smoothed-relief surface models exactly that dispersion
effect and is exact in the deep tail where relief saturates.

Both sides then apply the IDENTICAL node-level transform
:func:`par_model_v2.projection.inner_path_action_dynamics.apply_pathwise_declaration_node`
(envelope guard relieved <= max_relief * clip(B, 0, L)):

    truth:  L_with     = L     - clip(relieved_pathwise_node, 0, max_relief * B)
    proxy:  L_hat_with = L_hat - clip(relieved_hat,            0, max_relief * B_hat)

Fixed pre-registered gates (Phase 25 Task 1 design note s5 - the UNCHANGED
Phase 22 gates; no gate-shopping):

  G1  identical path-wise action basis in truth and proxy (structural +
      numeric: same rule, same a_ref, same envelope transform; bases respect
      0 <= relieved and 0 <= clip(B, 0, L) <= L after the guard)
  G2  OOS R^2 (with actions, path-wise basis)  >= 0.95
  G3  proxy-vs-nested VaR99.5 rel err (with)   <= 0.10
  G4  action monotonicity re-verified on the path-wise basis (rule guard AND
      the smoothed-surface transform)
  G5  leakage-free calibration (sigma, alpha, kappa from the FIT sample only)
      + no action at/above the trigger coverage ratio

DISCLOSED residuals (design note; sensitivity read-outs where cheap):
declaration cadence (monthly truth vs annual sensitivity, quantified on the
deterministic expected-path basis); perfect-foresight discounting in the
coverage proxy (adapted valuation would need nested-nested simulation); the
node-level analytic FX/liquidity offset enters the proxy undecayed; the
effective dispersion sigma is constant across nodes (a (CR, vol)-state
surface is the documented refinement if per-node dispersion ever matters).

EDUCATIONAL MODEL: management-action parameters remain educational
placeholders pending credentialled management-practice data and independent
APS X2 review.  NOT for production capital decisions.
"""

from __future__ import annotations

from typing import Dict, Optional, Tuple

import numpy as np

from par_model_v2.projection.inner_path_action_dynamics import (
    apply_pathwise_declaration_node,
    inner_path_monotonicity_check,
    pathwise_declaration_components_5d,
)
from par_model_v2.projection.management_actions import ManagementActionRule
from par_model_v2.projection.nested_stochastic_tvog import (
    _inner_q_process,
    _residual_cashflow_vector,
    _vectorised_discount_factors,
    capital_metrics_from_liabilities,
)
from par_model_v2.projection.pathwise_bonus_dynamics import (
    PATHWISE_OOS_R2_GATE,
    PATHWISE_VAR_REL_ERROR_GATE,
)
from par_model_v2.stochastic.credit_spread import _inner_q_spread_process
from par_model_v2.stochastic.esg_process import (
    GBMEquityProcess,
    GBMParams,
    Measure,
)

__all__ = [
    "PATHWISE_OOS_R2_GATE",
    "PATHWISE_VAR_REL_ERROR_GATE",
    "pathwise_declaration_fit_sliced",
    "deterministic_pathwise_relieved",
    "calibrate_pathwise_level_factor",
    "smoothed_relief_response",
    "calibrate_pathwise_response_surface",
    "pathwise_surface_monotonicity_check",
    "validate_pathwise_proxy_basis",
    "pathwise_proxy_basis_use_restrictions",
]

# Gauss-Hermite order for the smoothed-relief quadrature (fixed, disclosed).
_GH_ORDER = 21
_GH_X, _GH_W = np.polynomial.hermite.hermgauss(_GH_ORDER)


def pathwise_declaration_fit_sliced(
    validator, states7_full: np.ndarray, i0: int, i1: int,
    seed: int, n_inner: int, rule: ManagementActionRule,
    reference_assets: float, node_offsets: np.ndarray,
    horizon_reliefs: np.ndarray,
) -> Dict[str, np.ndarray]:
    """Sliced per-node path-wise declaration run on the FIT states.

    Seeds mirror
    :func:`par_model_v2.projection.inner_path_action_dynamics.benefit_credit_fit_sliced`
    (and therefore the archived Phase 22 Task 2 fit stage) EXACTLY:
    ``SeedSequence(seed + 1)`` spawned once per outer node, consumed in the
    same order - so the without-actions (benefit, credit) components are
    BIT-IDENTICAL to the archived Phase 24 Task 3 fit decomposition and can
    be exact-equality checked at every build slice.
    """
    if n_inner < 1:
        raise ValueError("n_inner must be >= 1")
    child = np.random.SeedSequence(seed + 1).spawn(len(states7_full))[i0:i1]
    n = i1 - i0
    out = {k: np.empty(n) for k in (
        "total", "benefit", "credit", "relieved_pathwise",
        "relieved_horizon", "action_share", "restoration_share",
        "cr_path0_mean")}
    v = validator
    for j in range(n):
        row = states7_full[i0 + j]
        r, s, c, b, m = (float(x) for x in row[:5])
        inner_seed = int(child[j].generate_state(1)[0])
        res = pathwise_declaration_components_5d(
            r, s, c, b, m, n_inner, v._rem,
            v.product, v.agg.hw_params, v.agg.gbm_params,
            v.agg.spread_params, v.agg.correlation,
            v.capital_horizon_months, inner_seed,
            v.agg.equity_guarantee, v.agg.credit_exposure,
            v.agg.lapse_exposure, v.agg.mortality_exposure,
            rule, reference_assets,
            node_offset=float(node_offsets[i0 + j]),
            horizon_relief=float(horizon_reliefs[i0 + j]),
        )
        ben = np.asarray(res["benefit"])
        cre = np.asarray(res["credit"])
        out["total"][j] = float((ben + cre).mean())
        out["benefit"][j] = float(ben.mean())
        out["credit"][j] = float(cre.mean())
        out["relieved_pathwise"][j] = float(
            np.asarray(res["relieved_pathwise"]).mean())
        out["relieved_horizon"][j] = float(
            np.asarray(res["relieved_horizon"]).mean())
        out["action_share"][j] = res["action_share"]
        out["restoration_share"][j] = res["restoration_share"]
        out["cr_path0_mean"][j] = res["cr_path0_mean"]
    return out


def deterministic_pathwise_relieved(
    validator, states7: np.ndarray, rule: ManagementActionRule,
    reference_assets: float, node_offsets: np.ndarray,
    cadence_months: int = 1,
) -> np.ndarray:
    """Zero-shock expected-path path-wise relieved amount per outer node.

    Candidate (a) of the design note: mirrors the relieved-amount
    composition of :func:`pathwise_declaration_components_5d` on a SINGLE
    drift-only (certainty-equivalent) inner path: the same time-0-discounted
    benefit cashflows, the same remaining-liability proxy

        RemPV0_t = remaining in-force benefit
                   + remaining credit-loss component
                   + node_offset (analytic FX + liquidity, undecayed),

    the same pre-step declaration convention (the relief in force for the
    cashflow at month u is decided at the start of that month), and the same
    carve-outs (only in-force policyholder benefits cuttable).  Jensen /
    diffusion effects (cuts triggered by stressed inner paths from healthy
    nodes, restoration on recovering paths) are NOT captured; the candidate
    comparison in the validation report discloses the resulting
    state-dependent bias.  Also used for the declaration-cadence sensitivity
    (``cadence_months`` > 1 re-declares only every that-many months; 1 = the
    monthly truth convention).
    """
    if cadence_months < 1:
        raise ValueError("cadence_months must be >= 1")
    x = np.asarray(states7, dtype=float)
    if x.ndim == 1:
        x = x.reshape(1, -1)
    offs = np.asarray(node_offsets, dtype=float)
    if offs.shape[0] != x.shape[0]:
        raise ValueError("node_offsets must align with states7 rows")
    v = validator
    rem = v._rem
    product = v.product
    notional = v.agg.credit_exposure.notional(product.sum_assured)
    units = v.agg.equity_guarantee.units(product.sum_assured)
    floor = v.agg.equity_guarantee.floor(product.sum_assured)
    dt = 1.0 / 12.0
    z1 = np.zeros((1, rem))
    eps = 1e-9
    # declaration months: the relief in force at step t uses the latest
    # declaration at or before t (t = 0 .. rem-1; pre-step convention).
    decl_idx = (np.arange(rem) // int(cadence_months)) * int(cadence_months)
    out = np.empty(len(x))
    for i, row in enumerate(x):
        r, s, sp, b, m = (float(val) for val in row[:5])
        hw = _inner_q_process(r, v.agg.hw_params)
        rate_paths = hw._simulate_array(1, rem, Measure.Q, z1)
        inner_gbm_params = GBMParams(
            equity_vol=v.agg.gbm_params.equity_vol,
            dividend_yield=v.agg.gbm_params.dividend_yield,
            equity_risk_premium=v.agg.gbm_params.equity_risk_premium,
            rate_equity_correlation=v.agg.gbm_params.rate_equity_correlation,
            initial_index_level=s,
        )
        gbm = GBMEquityProcess(inner_gbm_params, rate_process=hw)
        equity_paths, _ret = gbm._simulate_array(
            1, rem, Measure.Q, rate_paths, z1)
        csp = _inner_q_spread_process(sp, v.agg.spread_params)
        spread_paths = csp._simulate_array(1, rem, Measure.Q, z1)
        disc = _vectorised_discount_factors(rate_paths)

        inforce = v.agg.lapse_exposure.inforce_factor(
            r, b, v.capital_horizon_months, product.term_months)
        scaled_qx = v.agg.mortality_exposure.scaled_qx_fn(m, None)
        cf = _residual_cashflow_vector(
            product, v.capital_horizon_months, scaled_qx)

        g_cf = disc * cf[None, :]                              # (1, rem+1)
        tail = np.flip(np.cumsum(np.flip(g_cf, axis=1), axis=1), axis=1)
        fund_T = units * equity_paths[:, rem]
        eq_payoff = np.maximum(floor - fund_T, 0.0)
        eq0 = disc[:, rem] * eq_payoff                         # (1,)

        rem_ben0 = inforce * (tail[:, 1:] + eq0[:, None])      # (1, rem)
        cum = np.cumsum(spread_paths[:, :rem] * dt, axis=1)
        cum_prev = np.concatenate([np.zeros((1, 1)), cum[:, :-1]], axis=1)
        rem_credit0 = (disc[:, rem] * notional)[:, None] * (
            1.0 - np.exp(-(cum[:, -1][:, None] - cum_prev)))

        rem_l0 = rem_ben0 + rem_credit0 + float(offs[i])
        cr_path = float(reference_assets) / np.maximum(rem_l0, eps)
        relief = rule.relief_fraction(cr_path)                 # (1, rem)
        relief = relief[:, decl_idx]
        relieved = inforce * (
            (relief * g_cf[:, 1:]).sum(axis=1)
            + relief[:, rem - 1] * eq0
        )
        out[i] = float(relieved[0])
    return out


def calibrate_pathwise_level_factor(
    relieved_truth_fit: np.ndarray,
    relieved_det_fit: np.ndarray,
    min_det_mean_rel: float = 1e-12,
) -> float:
    """Single level factor for candidate (a), FIT sample ONLY.

        lambda = mean(relieved_truth_fit) / mean(relieved_det_fit)

    Mirrors the Phase 24 Task 3 ``kappa`` pattern.  Raises if the
    deterministic basis carries no signal on the fit sample.
    """
    t = np.asarray(relieved_truth_fit, dtype=float)
    d = np.asarray(relieved_det_fit, dtype=float)
    if t.shape != d.shape or t.ndim != 1:
        raise ValueError("fit arrays must be 1-D and aligned")
    if np.any(d < -1e-9) or np.any(t < -1e-9):
        raise ValueError("relieved amounts must be non-negative")
    t_mean = float(t.mean())
    d_mean = float(d.mean())
    scale = max(abs(t_mean), 1.0)
    if d_mean <= min_det_mean_rel * scale:
        raise ValueError(
            "deterministic relieved basis has no signal on the fit sample "
            "(mean %.3g vs truth mean %.3g)" % (d_mean, t_mean))
    return t_mean / d_mean


def smoothed_relief_response(
    rule: ManagementActionRule, cr: np.ndarray, sigma: float,
) -> np.ndarray:
    """Relief curve smoothed over an effective lognormal CR dispersion.

        phi_sigma(c) = E_Z[ relief_fraction(c * exp(sigma Z - sigma^2/2)) ]

    evaluated with fixed Gauss-Hermite quadrature (order 21).  sigma is the
    effective dispersion of the path-wise coverage ratio around the node
    coverage ratio; sigma -> 0 recovers relief_fraction(c) (a unit test).
    phi is non-increasing in c (a mixture of non-increasing functions) and
    phi <= max_relief everywhere, so the node transform inherits the rule's
    monotonicity guard with margin (checked numerically in
    :func:`pathwise_surface_monotonicity_check`).
    """
    if not (sigma >= 0.0 and np.isfinite(sigma)):
        raise ValueError("sigma must be finite and >= 0")
    c = np.asarray(cr, dtype=float)
    scalar = c.ndim == 0
    c = np.atleast_1d(c)
    if sigma == 0.0:
        out = rule.relief_fraction(c)
    else:
        shocks = np.exp(
            sigma * np.sqrt(2.0) * _GH_X - 0.5 * sigma * sigma)
        cc = c[:, None] * shocks[None, :]
        out = (rule.relief_fraction(cc) * _GH_W[None, :]).sum(axis=1) \
            / np.sqrt(np.pi)
    return float(out[0]) if scalar else out


def calibrate_pathwise_response_surface(
    rule: ManagementActionRule,
    cr_fit: np.ndarray,
    benefit_fit: np.ndarray,
    relieved_truth_fit: np.ndarray,
    sigma_grid: Optional[np.ndarray] = None,
) -> Dict[str, float]:
    """Calibrate (sigma, alpha) of candidate (b) on the FIT sample ONLY.

    For each sigma on a fixed grid, alpha has the closed-form least-squares
    solution against the truth per-node relieved amounts; the (sigma, alpha)
    pair minimising the SSE is selected.  Exactly two scalars, leakage-free,
    no per-state learned coefficients.  Returns the calibration record
    (sigma, alpha, fit R^2 of the relieved amounts, truth/predicted means).
    """
    cr = np.asarray(cr_fit, dtype=float)
    ben = np.asarray(benefit_fit, dtype=float)
    t = np.asarray(relieved_truth_fit, dtype=float)
    if not (cr.shape == ben.shape == t.shape) or cr.ndim != 1:
        raise ValueError("fit arrays must be 1-D and aligned")
    if np.any(t < -1e-9):
        raise ValueError("relieved amounts must be non-negative")
    if sigma_grid is None:
        sigma_grid = np.round(np.arange(0.05, 0.805, 0.025), 4)
    best = None
    for sigma in np.asarray(sigma_grid, dtype=float):
        p = smoothed_relief_response(rule, cr, float(sigma)) * ben
        denom = float((p * p).sum())
        if denom <= 0.0:
            continue
        alpha = float((t * p).sum() / denom)
        if not (alpha > 0.0 and np.isfinite(alpha)):
            continue
        sse = float(((t - alpha * p) ** 2).sum())
        if best is None or sse < best[2]:
            best = (float(sigma), alpha, sse)
    if best is None:
        raise ValueError(
            "response-surface calibration failed: no sigma on the grid "
            "yields a positive-signal least-squares fit")
    sigma, alpha, sse = best
    ss_tot = float(((t - t.mean()) ** 2).sum())
    pred = alpha * smoothed_relief_response(rule, cr, sigma) * ben
    return {
        "sigma": sigma,
        "alpha": alpha,
        "fit_r2_relieved": 1.0 - sse / ss_tot if ss_tot > 0 else float("nan"),
        "fit_truth_mean": float(t.mean()),
        "fit_pred_mean": float(pred.mean()),
        "sigma_grid_lo": float(np.min(sigma_grid)),
        "sigma_grid_hi": float(np.max(sigma_grid)),
        "sigma_interior": bool(
            np.min(sigma_grid) < sigma < np.max(sigma_grid)),
        "gh_order": _GH_ORDER,
    }


def pathwise_surface_monotonicity_check(
    rule: ManagementActionRule,
    reference_assets: float,
    sigma: float,
    alpha: float,
    l_lo: float,
    l_hi: float,
    betas: Tuple[float, ...] = (0.0, 0.25, 0.5, 0.75, 1.0),
    n_grid: int = 20001,
) -> bool:
    """Verify L -> L - min(alpha * phi_sigma(A/L), max_relief) * beta * L is
    non-decreasing for every benefit share beta in [0, 1] (the proxy-side
    node transform spanning the guard envelope B <= L)."""
    if not (0.0 < l_lo < l_hi):
        raise ValueError("require 0 < l_lo < l_hi")
    grid = np.linspace(float(l_lo), float(l_hi), int(n_grid))
    frac = np.minimum(
        float(alpha) * smoothed_relief_response(
            rule, float(reference_assets) / grid, float(sigma)),
        rule.max_relief)
    for beta in betas:
        if not (0.0 <= beta <= 1.0):
            raise ValueError("betas must lie in [0, 1]")
        out = grid - frac * beta * grid
        if not bool(np.all(np.diff(out) >= -1e-9)):
            return False
    return True


def _r2(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    ss_res = float(np.sum((y_true - y_pred) ** 2))
    ss_tot = float(np.sum((y_true - y_true.mean()) ** 2))
    return 1.0 - ss_res / ss_tot if ss_tot > 0 else float("nan")


def _rel(a: float, b: float) -> float:
    return abs(a - b) / (abs(b) if abs(b) > 1e-9 else 1.0)


def _approx_diag(emp: np.ndarray, est: np.ndarray) -> Dict[str, float]:
    emp = np.asarray(emp, dtype=float)
    est = np.asarray(est, dtype=float)
    denom = np.maximum(np.abs(emp), 1e-9)
    rel = np.abs(est - emp) / denom
    active = emp > 1e-9
    corr = float(np.corrcoef(emp, est)[0, 1]) if (
        emp.std() > 0 and est.std() > 0) else float("nan")
    return {
        "mean_abs_error": float(np.abs(est - emp).mean()),
        "mean_abs_rel_error_active": float(rel[active].mean())
        if active.any() else 0.0,
        "active_share_truth": float(active.mean()),
        "active_share_estimate": float(np.mean(est > 1e-9)),
        "corr": corr,
    }


def validate_pathwise_proxy_basis(
    rule: ManagementActionRule,
    fit_mean_liability: float,
    surface: Dict[str, float],
    kappa_credit: float,
    val_truth: np.ndarray,
    val_pred: np.ndarray,
    nested_l: np.ndarray,
    proxy_l: np.ndarray,
    benefit_val: np.ndarray,
    benefit_nested: np.ndarray,
    benefit_proxy_val: np.ndarray,
    benefit_proxy_nested: np.ndarray,
    relieved_truth_val: np.ndarray,
    relieved_truth_nested: np.ndarray,
    confidence_level: float,
    capital_horizon_months: int,
    calibration_leakage_free: bool,
    candidate_comparison: Optional[Dict[str, object]] = None,
    cadence_sensitivity: Optional[Dict[str, float]] = None,
) -> Dict[str, object]:
    """Phase 25 Task 3 - seven-driver OOS re-validation on the path-wise
    with-actions basis with the matching proxy basis feature (candidate (b),
    the smoothed-relief response surface).

    Truth and proxy use the IDENTICAL transform
    :func:`apply_pathwise_declaration_node` (same rule, same envelope guard
    relieved <= max_relief * clip(B, 0, L)); the only difference is the
    relieved-amount estimate: empirical per-node inner-path mean (truth) vs
    alpha * phi_sigma(CR_node) * clip(B_hat, 0, L_hat) (proxy).  The proxy
    node coverage ratio uses the PROXY liability (CR_hat = a_ref / L_hat),
    the same convention as the Phase 23/24 with-actions proxy transforms.
    Gates are the FIXED pre-registered Phase 25 Task 1 design note s5 set.
    """
    a_ref = rule.reference_assets(fit_mean_liability)
    sigma = float(surface["sigma"])
    alpha = float(surface["alpha"])
    val_truth = np.asarray(val_truth, dtype=float)
    val_pred = np.asarray(val_pred, dtype=float)
    nested_l = np.asarray(nested_l, dtype=float)
    proxy_l = np.asarray(proxy_l, dtype=float)

    def _proxy_relieved(l_hat: np.ndarray, b_hat: np.ndarray) -> np.ndarray:
        l_a = np.asarray(l_hat, dtype=float)
        b_clip = np.clip(np.asarray(b_hat, dtype=float), 0.0, l_a)
        cr_hat = rule.coverage_ratio(l_a, a_ref)
        return alpha * smoothed_relief_response(rule, cr_hat, sigma) * b_clip

    relieved_proxy_val = _proxy_relieved(val_pred, benefit_proxy_val)
    relieved_proxy_nested = _proxy_relieved(proxy_l, benefit_proxy_nested)

    val_truth_with, _clip_tv = apply_pathwise_declaration_node(
        rule, val_truth, benefit_val, relieved_truth_val)
    val_pred_with, _clip_pv = apply_pathwise_declaration_node(
        rule, val_pred, benefit_proxy_val, relieved_proxy_val)
    nested_with, clip_truth_nested = apply_pathwise_declaration_node(
        rule, nested_l, benefit_nested, relieved_truth_nested)
    proxy_with, clip_proxy_nested = apply_pathwise_declaration_node(
        rule, proxy_l, benefit_proxy_nested, relieved_proxy_nested)

    cap = dict(
        confidence_level=float(confidence_level),
        capital_horizon_months=int(capital_horizon_months),
    )
    nested_cap_wo = capital_metrics_from_liabilities(nested_l, **cap)
    nested_cap_w = capital_metrics_from_liabilities(nested_with, **cap)
    proxy_cap_wo = capital_metrics_from_liabilities(proxy_l, **cap)
    proxy_cap_w = capital_metrics_from_liabilities(proxy_with, **cap)

    oos_r2_with = _r2(val_truth_with, val_pred_with)
    oos_r2_without = _r2(val_truth, val_pred)
    var_rel_with = _rel(proxy_cap_w.var_liability, nested_cap_w.var_liability)
    es_rel_with = _rel(proxy_cap_w.es_liability, nested_cap_w.es_liability)
    scr_rel_with = _rel(proxy_cap_w.scr_proxy, nested_cap_w.scr_proxy)

    lo = float(min(nested_l.min(), proxy_l.min(), val_truth.min())) * 0.5
    hi = float(max(nested_l.max(), proxy_l.max(), val_truth.max())) * 2.0
    monotone_rule = inner_path_monotonicity_check(rule, a_ref, lo, hi)
    monotone_surface = pathwise_surface_monotonicity_check(
        rule, a_ref, sigma, alpha, lo, hi)

    cr_probe = np.array([rule.cr_trigger, rule.cr_trigger + 1e-9, 10.0])
    no_action_above_trigger = bool(
        np.all(rule.relief_fraction(cr_probe) <= 1e-12))

    # G1 numeric: identical transform + envelope on both sides; relieved
    # estimates non-negative; benefit bases respect 0 <= clip(B, 0, L) <= L.
    bases_ok = bool(alpha > 0.0 and np.isfinite(alpha)
                    and sigma >= 0.0 and np.isfinite(sigma))
    for l_arr, b_arr, r_arr in (
        (val_truth, benefit_val, relieved_truth_val),
        (val_pred, benefit_proxy_val, relieved_proxy_val),
        (nested_l, benefit_nested, relieved_truth_nested),
        (proxy_l, benefit_proxy_nested, relieved_proxy_nested),
    ):
        l_a = np.asarray(l_arr, dtype=float)
        b_clip = np.clip(np.asarray(b_arr, dtype=float), 0.0, l_a)
        r_a = np.asarray(r_arr, dtype=float)
        if not (np.all(r_a >= -1e-9) and np.all(b_clip >= 0.0)
                and np.all(b_clip <= l_a + 1e-9)):
            bases_ok = False

    gates = {
        "G1_identical_pathwise_action_basis_truth_and_proxy": bool(bases_ok),
        "G2_oos_r2_with_actions_ge_0p95": bool(
            oos_r2_with >= PATHWISE_OOS_R2_GATE),
        "G3_var_rel_error_with_actions_le_0p10": bool(
            var_rel_with <= PATHWISE_VAR_REL_ERROR_GATE),
        "G4_monotone_on_pathwise_basis": bool(
            monotone_rule and monotone_surface),
        "G5_leakage_free_calibration_and_no_action_above_trigger": bool(
            calibration_leakage_free and no_action_above_trigger),
    }
    verdict = "PASS" if all(gates.values()) else "FAIL"

    out = {
        "rule": rule.to_dict(),
        "reference_assets": float(a_ref),
        "fit_mean_liability": float(fit_mean_liability),
        "surface_calibration_fit_only": dict(surface),
        "kappa_credit_fit_calibrated": float(kappa_credit),
        "oos_r2_with_actions_pathwise": float(oos_r2_with),
        "oos_r2_without_actions": float(oos_r2_without),
        "var_rel_error_with_actions": float(var_rel_with),
        "es_rel_error_with_actions": float(es_rel_with),
        "scr_rel_error_with_actions": float(scr_rel_with),
        "nested_capital_without": nested_cap_wo.summary(),
        "nested_capital_with_pathwise": nested_cap_w.summary(),
        "proxy_capital_without": proxy_cap_wo.summary(),
        "proxy_capital_with_pathwise": proxy_cap_w.summary(),
        "clip_binding_share_truth_nested": float(clip_truth_nested),
        "clip_binding_share_proxy_nested": float(clip_proxy_nested),
        "monotonicity": {
            "rule_guard": bool(monotone_rule),
            "surface_transform": bool(monotone_surface),
        },
        "relieved_approximation_diagnostics": {
            "val_nodes": _approx_diag(relieved_truth_val, relieved_proxy_val),
            "nested_nodes": _approx_diag(
                relieved_truth_nested, relieved_proxy_nested),
        },
        "gates": gates,
        "verdict": verdict,
    }
    if candidate_comparison is not None:
        out["candidate_comparison"] = dict(candidate_comparison)
    if cadence_sensitivity is not None:
        out["declaration_cadence_sensitivity"] = dict(cadence_sensitivity)
    return out


def pathwise_proxy_basis_use_restrictions() -> Dict[str, object]:
    """Governed use restrictions for the path-wise proxy basis feature."""
    return {
        "classification": "EDUCATIONAL_DEMONSTRATION_ONLY",
        "approved_uses": [
            "Methodology demonstration of a matching analytic "
            "post-composition action basis for an LSMC proxy (identical "
            "path-wise action basis in truth and proxy, Solvency II "
            "Art. 23 consistency)",
            "Quantification of the expected-path vs smoothed-response-"
            "surface approximation error of the per-node path-wise "
            "relieved amount",
        ],
        "prohibited_uses": [
            "Production capital or solvency decisions",
            "Policyholder bonus declarations",
            "Regulatory submissions",
        ],
        "rationale": (
            "Management-action parameters are educational placeholders; "
            "the proxy relieved amount is an analytic smoothed-relief "
            "response surface with two fit-calibrated scalars (sigma, "
            "alpha) - per-node approximation error disclosed; the truth "
            "coverage proxy uses realised-path (perfect-foresight) "
            "discounting; the node-level FX/liquidity offset enters "
            "undecayed; the effective dispersion sigma is constant across "
            "nodes; production sign-off withheld pending credentialled "
            "data and independent APS X2 review."
        ),
    }
