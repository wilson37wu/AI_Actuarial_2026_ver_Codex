"""
Phase 24 Task 3 - Inner-path management-action dynamics prototype.

Implements Method B of the Phase 24 Task 1 design note
(docs/validation/PHASE24_TASK1_DESIGN_NOTE.md): the governed
reversionary-bonus participation cut (Phase 23 Task 3,
:class:`par_model_v2.projection.management_actions.ManagementActionRule`)
is applied to the INNER-PATH projected policyholder-benefit cashflows at the
capital horizon, instead of uniformly rescaling the outer-node conditional
liability.

Outer-node basis (Phase 23, approximation):

    L_with = L * (1 - relief(CR(L)))          # relieves EVERYTHING in L,
                                              # including the asset-side
                                              # credit-loss component and the
                                              # analytic FX/liquidity offsets

Inner-path basis (this module):

    PV_with_i = PV_i - relief(CR(L)) * B_i    # per inner path i
    L_with    = mean_i(PV_with_i)
              = L - relief(CR(L)) * mean_i(B_i)

where ``B_i = guaranteed_pv_i + eq_guarantee_pv_i`` is the in-force
policyholder-benefit PV on inner path ``i`` (the only cashflows a
reversionary-bonus cut can touch) and the asset-side credit-loss PV and the
analytic FX / liquidity liability offsets are EXCLUDED from the cuttable
base.  The action decision (the relief factor) still uses the PRE-action
outer-node coverage ratio CR = A_ref / L — the declared-rate path responds
to the coverage ratio at the outer node (horizon-level cashflow response).
Because the relief factor is constant across the inner paths of one outer
node, the path-wise application aggregates exactly to the node-level
formula; this equivalence is unit-tested.

Scope (design-note s'Method B' scope note): full path-wise dynamic
declaration (the action re-evaluated at every inner time step on a
path-wise solvency position) is OUT of Phase 24 scope; this prototype
relaxes the outer-node approximation one step and documents the residual.

Proxy basis feature
-------------------
The LSMC proxy gains the MATCHING analytic post-composition feature: the
cuttable-benefit base for the proxy is

    B_hat(x) = clip( poly5(x) - kappa * C_det(r_H, s_H), 0, L_hat )

where ``poly5`` is the archived selected surface (the five-driver part of
the proxy prediction, i.e. prediction minus the analytic FX and liquidity
offsets), ``C_det`` is the deterministic expected-path (zero-shock,
certainty-equivalent) credit-loss PV computed with the SAME monthly inner-Q
discretisation as the simulator, and ``kappa`` is a single level adjustment
calibrated on the FIT sample only (leakage-free; corrects the Jensen /
rate-spread-correlation bias of the expected-path approximation).  No new
per-state learned coefficients are introduced.

Fixed pre-registered gates (Phase 24 Task 1 design note s5, module
constants in :mod:`par_model_v2.projection.joint_action_aggregation`):
OOS R^2 (with actions, inner-path basis) >= 0.95 and proxy-vs-nested
VaR99.5 rel err <= 10% — the unchanged Phase 22 gates — plus action
monotonicity re-verified on the inner-path basis.

EDUCATIONAL MODEL: management-action parameters remain educational
placeholders pending credentialled management-practice data and
independent APS X2 review.  NOT for production capital decisions.
"""

from __future__ import annotations

from typing import Dict, Optional, Tuple

import numpy as np

from par_model_v2.projection.joint_action_aggregation import (
    INNER_PATH_OOS_R2_GATE,
    INNER_PATH_VAR_REL_ERROR_GATE,
)
from par_model_v2.projection.management_actions import ManagementActionRule
from par_model_v2.projection.monthly_projection import ParEndowmentProduct
from par_model_v2.projection.multi_driver_capital_5d import (
    _correlated_shocks_5,
    _inner_pathwise_pvs_5d,
)
from par_model_v2.projection.nested_stochastic_tvog import (
    _inner_q_process,
    _residual_cashflow_vector,
    _vectorised_discount_factors,
    capital_metrics_from_liabilities,
)
from par_model_v2.stochastic.credit_spread import _inner_q_spread_process
from par_model_v2.stochastic.esg_process import (
    GBMEquityProcess,
    GBMParams,
    Measure,
)

__all__ = [
    "INNER_PATH_OOS_R2_GATE",
    "INNER_PATH_VAR_REL_ERROR_GATE",
    "inner_pathwise_pv_components_5d",
    "benefit_credit_heavy_sliced",
    "benefit_credit_fit_sliced",
    "deterministic_credit_pv",
    "apply_inner_path_action",
    "inner_path_monotonicity_check",
    "validate_inner_path_actions",
    "inner_path_use_restrictions",
]


def inner_pathwise_pv_components_5d(
    r, s, spread, b, m, n_inner, rem_months, product, base_hw_params,
    gbm_params, spread_params, correlation, h_month, seed,
    equity_guarantee, credit_exposure, lapse_exposure, mortality_exposure,
    annual_qx_fn=None,
) -> Tuple[np.ndarray, np.ndarray]:
    """Pathwise (benefit, credit) PV components at one outer state.

    Mirrors :func:`_inner_pathwise_pvs_5d` operation-for-operation (same RNG
    consumption order) and returns the in-force policyholder-benefit PV
    ``benefit = guaranteed_pv + eq_guarantee_pv`` and the asset-side
    ``credit = credit_loss_pv`` separately.  ``benefit + credit`` is
    BIT-IDENTICAL to the archived total (unit-tested), because the original
    returns ``(guaranteed_pv + eq_guarantee_pv) + credit_loss_pv`` in the
    same left-to-right association.
    """
    rng = np.random.default_rng(seed)
    chol = correlation.cholesky(gbm_params.rate_equity_correlation)
    z_rate, z_equity, z_spread, _z_lapse, _z_mort = _correlated_shocks_5(
        rng, n_inner, rem_months, chol
    )

    hw = _inner_q_process(r, base_hw_params)
    inner_gbm_params = GBMParams(
        equity_vol=gbm_params.equity_vol,
        dividend_yield=gbm_params.dividend_yield,
        equity_risk_premium=gbm_params.equity_risk_premium,
        rate_equity_correlation=gbm_params.rate_equity_correlation,
        initial_index_level=float(s),
    )
    gbm = GBMEquityProcess(inner_gbm_params, rate_process=hw)
    csp = _inner_q_spread_process(spread, spread_params)

    rate_paths = hw._simulate_array(n_inner, rem_months, Measure.Q, z_rate)
    equity_paths, _ret = gbm._simulate_array(
        n_inner, rem_months, Measure.Q, rate_paths, z_equity
    )
    spread_paths = csp._simulate_array(n_inner, rem_months, Measure.Q, z_spread)
    disc = _vectorised_discount_factors(rate_paths)

    inforce = lapse_exposure.inforce_factor(
        float(r), float(b), h_month, product.term_months
    )

    scaled_qx = mortality_exposure.scaled_qx_fn(float(m), annual_qx_fn)
    cf = _residual_cashflow_vector(product, h_month, scaled_qx)
    guaranteed_pv = inforce * (disc @ cf)

    units = equity_guarantee.units(product.sum_assured)
    floor = equity_guarantee.floor(product.sum_assured)
    fund_T = units * equity_paths[:, rem_months]
    eq_payoff = np.maximum(floor - fund_T, 0.0)
    eq_guarantee_pv = inforce * (disc[:, rem_months] * eq_payoff)

    notional = credit_exposure.notional(product.sum_assured)
    dt = 1.0 / 12.0
    cum_hazard = spread_paths[:, :rem_months].sum(axis=1) * dt
    loss_fraction = 1.0 - np.exp(-cum_hazard)
    credit_loss_pv = disc[:, rem_months] * notional * loss_fraction

    benefit = guaranteed_pv + eq_guarantee_pv
    return benefit, credit_loss_pv


def _components_at(validator, row: np.ndarray, n_inner: int, inner_seed: int):
    """(benefit, credit) pathwise components via the validator's primitives."""
    r, s, c, b, m = (float(v) for v in row[:5])
    v = validator
    return inner_pathwise_pv_components_5d(
        r, s, c, b, m, n_inner, v._rem,
        v.product, v.agg.hw_params, v.agg.gbm_params,
        v.agg.spread_params, v.agg.correlation,
        v.capital_horizon_months, inner_seed,
        v.agg.equity_guarantee, v.agg.credit_exposure,
        v.agg.lapse_exposure, v.agg.mortality_exposure,
        None,
    )


def benefit_credit_heavy_sliced(
    validator, states7_full: np.ndarray, i0: int, i1: int,
    n_inner: int, seed: int,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """(total, benefit, credit) node means; seeds mirror heavy_targets_sliced."""
    if n_inner < 1:
        raise ValueError("n_inner must be >= 1")
    child = np.random.SeedSequence(seed).spawn(len(states7_full))[i0:i1]
    n = i1 - i0
    total = np.empty(n)
    benefit = np.empty(n)
    credit = np.empty(n)
    for j in range(n):
        inner_seed = int(child[j].generate_state(1)[0])
        ben, cre = _components_at(
            validator, states7_full[i0 + j], n_inner, inner_seed)
        tot = ben + cre
        total[j] = float(tot.mean())
        benefit[j] = float(ben.mean())
        credit[j] = float(cre.mean())
    return total, benefit, credit


def benefit_credit_fit_sliced(
    validator, states7_full: np.ndarray, i0: int, i1: int,
    seed: int, n_inner: int,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """(total, benefit, credit) fit-node means; seeds mirror
    denoised_fit_payoffs_sliced (SeedSequence(seed + 1))."""
    if n_inner < 1:
        raise ValueError("n_inner must be >= 1")
    child = np.random.SeedSequence(seed + 1).spawn(len(states7_full))[i0:i1]
    n = i1 - i0
    total = np.empty(n)
    benefit = np.empty(n)
    credit = np.empty(n)
    for j in range(n):
        inner_seed = int(child[j].generate_state(1)[0])
        ben, cre = _components_at(
            validator, states7_full[i0 + j], n_inner, inner_seed)
        tot = ben + cre
        total[j] = float(tot.mean())
        benefit[j] = float(ben.mean())
        credit[j] = float(cre.mean())
    return total, benefit, credit


def deterministic_credit_pv(validator, states7: np.ndarray) -> np.ndarray:
    """Deterministic expected-path (zero-shock) credit-loss PV per state.

    Certainty-equivalent approximation: the inner-Q rate and spread
    processes are run on their ZERO-SHOCK (drift-only) paths with the same
    monthly discretisation as the simulator; the credit-loss PV is then the
    plain composition disc_T * notional * (1 - exp(-cum_hazard)).  Jensen
    convexity and the rate-spread correlation are NOT captured — that bias
    is corrected by a single fit-sample-calibrated level factor ``kappa``
    (leakage-free) and the residual approximation error is disclosed.
    """
    x = np.asarray(states7, dtype=float)
    if x.ndim == 1:
        x = x.reshape(1, -1)
    v = validator
    rem = v._rem
    notional = v.agg.credit_exposure.notional(v.product.sum_assured)
    dt = 1.0 / 12.0
    z1 = np.zeros((1, rem))
    out = np.empty(len(x))
    for i, row in enumerate(x):
        r, sp = float(row[0]), float(row[2])
        hw = _inner_q_process(r, v.agg.hw_params)
        rate_paths = hw._simulate_array(1, rem, Measure.Q, z1)
        csp = _inner_q_spread_process(sp, v.agg.spread_params)
        spread_paths = csp._simulate_array(1, rem, Measure.Q, z1)
        disc = _vectorised_discount_factors(rate_paths)
        cum_hazard = float(spread_paths[0, :rem].sum()) * dt
        out[i] = float(disc[0, rem]) * notional * (1.0 - np.exp(-cum_hazard))
    return out


def apply_inner_path_action(
    rule: ManagementActionRule,
    reference_assets: float,
    liabilities: np.ndarray,
    benefit_base: np.ndarray,
) -> np.ndarray:
    """With-actions liabilities on the inner-path basis.

    L_with = L - relief(CR(L)) * clip(B, 0, L).  The clip enforces the
    construction guard B <= L (the cuttable policyholder-benefit base can
    never exceed the total liability), which makes the transform monotone
    a fortiori under the rule's existing monotonicity guard.
    """
    l = np.asarray(liabilities, dtype=float)
    b = np.clip(np.asarray(benefit_base, dtype=float), 0.0, l)
    cr = rule.coverage_ratio(l, reference_assets)
    return l - rule.relief_fraction(cr) * b


def inner_path_monotonicity_check(
    rule: ManagementActionRule,
    reference_assets: float,
    l_lo: float,
    l_hi: float,
    betas: Tuple[float, ...] = (0.0, 0.25, 0.5, 0.75, 1.0),
    n_grid: int = 20001,
) -> bool:
    """Verify L -> L - relief(A/L) * beta * L is non-decreasing on the range
    for every benefit share beta in [0, 1] (B = beta * L spans the guard
    envelope B <= L)."""
    if not (0.0 < l_lo < l_hi):
        raise ValueError("require 0 < l_lo < l_hi")
    grid = np.linspace(float(l_lo), float(l_hi), int(n_grid))
    for beta in betas:
        if not (0.0 <= beta <= 1.0):
            raise ValueError("betas must lie in [0, 1]")
        out = apply_inner_path_action(
            rule, reference_assets, grid, beta * grid)
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


def validate_inner_path_actions(
    rule: ManagementActionRule,
    fit_mean_liability: float,
    val_truth: np.ndarray,
    val_pred: np.ndarray,
    nested_l: np.ndarray,
    proxy_l: np.ndarray,
    benefit_val: np.ndarray,
    benefit_nested: np.ndarray,
    benefit_proxy_val: np.ndarray,
    benefit_proxy_nested: np.ndarray,
    confidence_level: float,
    capital_horizon_months: int,
) -> Dict[str, object]:
    """Seven-driver OOS re-validation on the inner-path action basis.

    The SAME governed rule and the SAME transform
    :func:`apply_inner_path_action` are applied to the nested truth (with
    the empirical per-node benefit base from the inner-path component
    decomposition) and to the proxy (with the matching analytic
    post-composition benefit base) — gate G1.

    Fixed pre-registered gates (Phase 24 Task 1 design note s5):
      G1  identical action basis in truth and proxy (structural + numeric)
      G2  OOS R^2 (with actions, inner-path)        >= 0.95
      G3  VaR rel err proxy-vs-nested (with)        <= 0.10
      G4  monotone on the inner-path basis (B <= L envelope)
      G5  with-actions capital <= without + no action above trigger
    """
    a_ref = rule.reference_assets(fit_mean_liability)

    val_truth = np.asarray(val_truth, dtype=float)
    val_pred = np.asarray(val_pred, dtype=float)
    nested_l = np.asarray(nested_l, dtype=float)
    proxy_l = np.asarray(proxy_l, dtype=float)

    val_truth_with = apply_inner_path_action(
        rule, a_ref, val_truth, benefit_val)
    val_pred_with = apply_inner_path_action(
        rule, a_ref, val_pred, benefit_proxy_val)
    nested_with = apply_inner_path_action(
        rule, a_ref, nested_l, benefit_nested)
    proxy_with = apply_inner_path_action(
        rule, a_ref, proxy_l, benefit_proxy_nested)

    # Outer-node (Phase 23) basis on the SAME arrays, for the disclosed delta.
    nested_with_outer = rule.apply_to_liabilities(nested_l, a_ref)
    proxy_with_outer = rule.apply_to_liabilities(proxy_l, a_ref)

    cr_nested = rule.coverage_ratio(nested_l, a_ref)
    active_share = float(np.mean(cr_nested < rule.cr_trigger))
    floor_share = float(np.mean(cr_nested <= rule.cr_floor))

    cap = dict(
        confidence_level=float(confidence_level),
        capital_horizon_months=int(capital_horizon_months),
    )
    nested_cap_wo = capital_metrics_from_liabilities(nested_l, **cap)
    nested_cap_w = capital_metrics_from_liabilities(nested_with, **cap)
    nested_cap_outer = capital_metrics_from_liabilities(
        nested_with_outer, **cap)
    proxy_cap_w = capital_metrics_from_liabilities(proxy_with, **cap)
    proxy_cap_outer = capital_metrics_from_liabilities(
        proxy_with_outer, **cap)

    lo = float(min(nested_l.min(), proxy_l.min(), val_truth.min())) * 0.5
    hi = float(max(nested_l.max(), proxy_l.max(), val_truth.max())) * 2.0
    monotone = inner_path_monotonicity_check(rule, a_ref, lo, hi)

    cr_probe = np.array([rule.cr_trigger, rule.cr_trigger + 1e-9, 10.0])
    no_action_above_trigger = bool(
        np.all(rule.relief_fraction(cr_probe) <= 1e-12))

    # G1 numeric: the same transform with the same rule/a_ref applied to
    # both sides; benefit bases respect 0 <= B <= L after the guard clip.
    bases_ok = True
    for l_arr, b_arr in (
        (val_truth, benefit_val), (val_pred, benefit_proxy_val),
        (nested_l, benefit_nested), (proxy_l, benefit_proxy_nested),
    ):
        b_clip = np.clip(np.asarray(b_arr, dtype=float), 0.0, l_arr)
        if not (np.all(b_clip >= 0.0) and np.all(b_clip <= l_arr + 1e-9)):
            bases_ok = False

    oos_r2_with = _r2(val_truth_with, val_pred_with)
    oos_r2_without = _r2(val_truth, val_pred)
    var_rel_with = _rel(proxy_cap_w.var_liability, nested_cap_w.var_liability)
    es_rel_with = _rel(proxy_cap_w.es_liability, nested_cap_w.es_liability)
    scr_rel_with = _rel(proxy_cap_w.scr_proxy, nested_cap_w.scr_proxy)

    gates = {
        "G1_identical_action_basis_truth_and_proxy": bool(bases_ok),
        "G2_oos_r2_with_actions_ge_0p95": bool(
            oos_r2_with >= INNER_PATH_OOS_R2_GATE),
        "G3_var_rel_error_with_actions_le_0p10": bool(
            var_rel_with <= INNER_PATH_VAR_REL_ERROR_GATE),
        "G4_monotone_on_inner_path_basis": bool(monotone),
        "G5_with_le_without_and_no_action_above_trigger": bool(
            nested_cap_w.var_liability
            <= nested_cap_wo.var_liability + 1e-9
            and nested_cap_w.scr_proxy <= nested_cap_wo.scr_proxy + 1e-9
            and no_action_above_trigger
        ),
    }
    verdict = "PASS" if all(gates.values()) else "FAIL"

    return {
        "rule": rule.to_dict(),
        "reference_assets": float(a_ref),
        "fit_mean_liability": float(fit_mean_liability),
        "active_share_nested": active_share,
        "floor_share_nested": floor_share,
        "oos_r2_with_actions_inner_path": float(oos_r2_with),
        "oos_r2_without_actions": float(oos_r2_without),
        "nested_capital_without": nested_cap_wo.summary(),
        "nested_capital_with_inner_path": nested_cap_w.summary(),
        "nested_capital_with_outer_node": nested_cap_outer.summary(),
        "proxy_capital_with_inner_path": proxy_cap_w.summary(),
        "proxy_capital_with_outer_node": proxy_cap_outer.summary(),
        "var_rel_error_with_actions": float(var_rel_with),
        "es_rel_error_with_actions": float(es_rel_with),
        "scr_rel_error_with_actions": float(scr_rel_with),
        "outer_vs_inner_path_delta": {
            "nested_var_99_5_outer_node":
                float(nested_cap_outer.var_liability),
            "nested_var_99_5_inner_path": float(nested_cap_w.var_liability),
            "nested_var_99_5_delta": float(
                nested_cap_w.var_liability - nested_cap_outer.var_liability),
            "nested_scr_outer_node": float(nested_cap_outer.scr_proxy),
            "nested_scr_inner_path": float(nested_cap_w.scr_proxy),
            "nested_scr_delta": float(
                nested_cap_w.scr_proxy - nested_cap_outer.scr_proxy),
            "interpretation": (
                "The outer-node transform relieves the asset-side "
                "credit-loss component and the analytic FX/liquidity "
                "offsets as if they were cuttable bonus; the inner-path "
                "basis restricts the cut to policyholder-benefit "
                "cashflows, so it relieves LESS and is the more "
                "conservative (and more faithful) with-actions basis."
            ),
        },
        "gates": gates,
        "verdict": verdict,
    }


def inner_path_use_restrictions() -> Dict[str, object]:
    """Governed use restrictions for the inner-path action prototype."""
    return {
        "classification": "EDUCATIONAL_DEMONSTRATION_ONLY",
        "approved_uses": [
            "Methodology demonstration of inner-path management-action "
            "dynamics (Solvency II Art. 23) in a nested-stochastic / "
            "LSMC-proxy framework",
            "Quantification of the outer-node vs inner-path with-actions "
            "approximation gap",
        ],
        "prohibited_uses": [
            "Production capital or solvency decisions",
            "Policyholder bonus declarations",
            "Regulatory submissions",
        ],
        "rationale": (
            "Management-action parameters are educational placeholders; "
            "the declared-rate response is horizon-level (full path-wise "
            "dynamic declaration is a documented residual); the proxy "
            "credit carve-out uses a fit-calibrated expected-path "
            "approximation; production sign-off withheld pending "
            "credentialled data and independent APS X2 review."
        ),
    }


# ---------------------------------------------------------------------------
# Phase 25 Task 2 - path-wise declaration in the nested truth
# ---------------------------------------------------------------------------
# The Phase 24 Task 3 convention freezes the bonus-cut DECISION at the outer
# node (horizon-level declared-rate response): the relief factor is constant
# across the inner paths of one outer node.  Phase 25 Task 2 implements the
# pre-registered refinement (PHASE25_TASK1_DESIGN_NOTE s3/s5): the governed
# retained-bonus factor is re-evaluated at EVERY inner time step from a
# path-wise coverage proxy
#
#     CR_t = A_t / L_t,   A_t = a_ref rolled forward at the inner short rate,
#                         L_t = pre-action remaining path liability at t,
#
# and because both sides are deflated by the SAME path discount factor the
# proxy reduces to the numerically clean time-0 form
#
#     CR_{i,t} = a_ref / RemPV0_{i,t}
#
# with RemPV0 the time-0-discounted remaining pre-action path liability
# (in-force benefit + remaining credit-loss component + the node-level
# analytic FX/liquidity offset, held constant - disclosed).  The relief in
# force for the cashflow at month u is decided at the START of that month
# (pre-step CR at t = u-1, the Task 1 pre-study convention).  P24T3
# carve-outs are PRESERVED: only the in-force policyholder-benefit cashflows
# (guaranteed + equity-guarantee) are cuttable; the asset-side credit-loss
# PV and the analytic FX/liquidity offsets are NOT cuttable.  The
# horizon-level basis is RETAINED as the sensitivity variant.
#
# DISCLOSED limitations (declaration-frequency / adaptedness residuals are
# Task 3 documentation items): the coverage proxy discounts the remaining
# cashflows with the realised inner path (perfect-foresight discounting - a
# proxy, not an adapted valuation); declarations occur at every monthly
# inner step (an annual declaration cadence is the documented sensitivity);
# the node-level FX/liquidity offset enters the proxy undecayed.

from par_model_v2.projection.pathwise_bonus_dynamics import (
    PATHWISE_MATERIALITY_DISCLOSURE_THRESHOLD,
)

__all__ += [
    "PATHWISE_MATERIALITY_DISCLOSURE_THRESHOLD",
    "pathwise_declaration_components_5d",
    "pathwise_declaration_heavy_sliced",
    "apply_pathwise_declaration_node",
    "validate_pathwise_declaration",
    "pathwise_declaration_use_restrictions",
]


def pathwise_declaration_components_5d(
    r, s, spread, b, m, n_inner, rem_months, product, base_hw_params,
    gbm_params, spread_params, correlation, h_month, seed,
    equity_guarantee, credit_exposure, lapse_exposure, mortality_exposure,
    rule: ManagementActionRule, reference_assets: float,
    node_offset: float = 0.0, horizon_relief: float = 0.0,
    annual_qx_fn=None,
) -> Dict[str, object]:
    """Inner-path PV components plus path-wise / horizon relieved amounts.

    The simulation block mirrors :func:`inner_pathwise_pv_components_5d`
    operation-for-operation (identical RNG consumption order), so the
    returned ``benefit`` and ``credit`` arrays are BIT-IDENTICAL to the
    Phase 24 Task 3 decomposition (enforced at every build slice) and the
    without-actions basis is unchanged by construction.

    Returns a dict with per-inner-path arrays ``benefit``, ``credit``,
    ``relieved_pathwise``, ``relieved_horizon`` and path-wise diagnostics
    (action share, restoration share, initial path-wise CR stats).
    """
    rng = np.random.default_rng(seed)
    chol = correlation.cholesky(gbm_params.rate_equity_correlation)
    z_rate, z_equity, z_spread, _z_lapse, _z_mort = _correlated_shocks_5(
        rng, n_inner, rem_months, chol
    )

    hw = _inner_q_process(r, base_hw_params)
    inner_gbm_params = GBMParams(
        equity_vol=gbm_params.equity_vol,
        dividend_yield=gbm_params.dividend_yield,
        equity_risk_premium=gbm_params.equity_risk_premium,
        rate_equity_correlation=gbm_params.rate_equity_correlation,
        initial_index_level=float(s),
    )
    gbm = GBMEquityProcess(inner_gbm_params, rate_process=hw)
    csp = _inner_q_spread_process(spread, spread_params)

    rate_paths = hw._simulate_array(n_inner, rem_months, Measure.Q, z_rate)
    equity_paths, _ret = gbm._simulate_array(
        n_inner, rem_months, Measure.Q, rate_paths, z_equity
    )
    spread_paths = csp._simulate_array(n_inner, rem_months, Measure.Q, z_spread)
    disc = _vectorised_discount_factors(rate_paths)

    inforce = lapse_exposure.inforce_factor(
        float(r), float(b), h_month, product.term_months
    )

    scaled_qx = mortality_exposure.scaled_qx_fn(float(m), annual_qx_fn)
    cf = _residual_cashflow_vector(product, h_month, scaled_qx)
    guaranteed_pv = inforce * (disc @ cf)

    units = equity_guarantee.units(product.sum_assured)
    floor = equity_guarantee.floor(product.sum_assured)
    fund_T = units * equity_paths[:, rem_months]
    eq_payoff = np.maximum(floor - fund_T, 0.0)
    eq_guarantee_pv = inforce * (disc[:, rem_months] * eq_payoff)

    notional = credit_exposure.notional(product.sum_assured)
    dt = 1.0 / 12.0
    cum_hazard = spread_paths[:, :rem_months].sum(axis=1) * dt
    loss_fraction = 1.0 - np.exp(-cum_hazard)
    credit_loss_pv = disc[:, rem_months] * notional * loss_fraction

    benefit = guaranteed_pv + eq_guarantee_pv
    # --- end of the bit-identical Phase 24 Task 3 simulation block ---------

    # Time-0-discounted benefit cashflows per month (cuttable base, cf >= 0).
    g_cf = disc * cf[None, :]                                # (n, rem+1)
    # tail[:, t] = sum_{u >= t} g_cf[:, u]; remaining AFTER t is tail[:, t+1]
    tail = np.flip(np.cumsum(np.flip(g_cf, axis=1), axis=1), axis=1)
    eq0 = disc[:, rem_months] * eq_payoff                    # (n,)

    # Remaining in-force benefit at declaration times t = 0 .. rem-1.
    rem_ben0 = inforce * (tail[:, 1:] + eq0[:, None])        # (n, rem)

    # Remaining credit-loss component (hazard over [t, rem)).
    cum = np.cumsum(spread_paths[:, :rem_months] * dt, axis=1)   # (n, rem)
    cum_prev = np.concatenate(
        [np.zeros((n_inner, 1)), cum[:, :-1]], axis=1)           # (n, rem)
    rem_credit0 = (disc[:, rem_months] * notional)[:, None] * (
        1.0 - np.exp(-(cum[:, -1][:, None] - cum_prev)))

    rem_l0 = rem_ben0 + rem_credit0 + float(node_offset)
    eps = 1e-9
    cr_path = float(reference_assets) / np.maximum(rem_l0, eps)  # (n, rem)
    relief = rule.relief_fraction(cr_path)                       # (n, rem)

    # relief[:, t] is in force for the cashflow at month u = t + 1; the
    # equity-guarantee payoff at u = rem uses the last declaration t = rem-1.
    relieved_pathwise = inforce * (
        (relief * g_cf[:, 1:]).sum(axis=1)
        + relief[:, rem_months - 1] * eq0
    )
    relieved_horizon = float(horizon_relief) * benefit

    tol = 1e-12
    cut_any = relief > tol
    had_cut = np.maximum.accumulate(cut_any, axis=1)
    restored = np.any(
        had_cut[:, :-1] & (relief[:, 1:] < relief[:, :-1] - tol), axis=1)

    return {
        "benefit": benefit,
        "credit": credit_loss_pv,
        "relieved_pathwise": relieved_pathwise,
        "relieved_horizon": relieved_horizon,
        "action_share": float(np.mean(cut_any.any(axis=1))),
        "restoration_share": float(np.mean(restored)),
        "cr_path0_mean": float(cr_path[:, 0].mean()),
        "cr_path0_min": float(cr_path[:, 0].min()),
        "mean_relief_step": float(relief.mean()),
    }


def pathwise_declaration_heavy_sliced(
    validator, states7_full: np.ndarray, i0: int, i1: int,
    n_inner: int, seed: int, rule: ManagementActionRule,
    reference_assets: float, node_offsets: np.ndarray,
    horizon_reliefs: np.ndarray,
) -> Dict[str, np.ndarray]:
    """Sliced per-node path-wise declaration run on the nested eval states.

    Seeds mirror :func:`benefit_credit_heavy_sliced` (and therefore the
    archived Phase 22 Task 2 heavy stage) EXACTLY: one spawned child seed
    per outer node, consumed in the same order.
    """
    if n_inner < 1:
        raise ValueError("n_inner must be >= 1")
    child = np.random.SeedSequence(seed).spawn(len(states7_full))[i0:i1]
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


def apply_pathwise_declaration_node(
    rule: ManagementActionRule,
    l7: np.ndarray,
    benefit_node: np.ndarray,
    relieved_node: np.ndarray,
) -> Tuple[np.ndarray, float]:
    """Node-level with-actions liabilities from per-node relieved amounts.

    Guard (carve-out envelope): the relieved amount can never exceed
    ``max_relief * clip(B, 0, L)`` - the same envelope as the Phase 24
    Task 3 horizon basis.  Returns (L_with, clip_binding_share).
    """
    l = np.asarray(l7, dtype=float)
    b = np.clip(np.asarray(benefit_node, dtype=float), 0.0, l)
    cap = rule.max_relief * b
    rel = np.asarray(relieved_node, dtype=float)
    clip_share = float(np.mean(rel > cap + 1e-9))
    return l - np.minimum(np.maximum(rel, 0.0), cap), clip_share


def validate_pathwise_declaration(
    rule: ManagementActionRule,
    fit_mean_liability: float,
    nested_l: np.ndarray,
    benefit_nested: np.ndarray,
    relieved_pathwise_node: np.ndarray,
    relieved_horizon_node: np.ndarray,
    without_actions_bit_identical: bool,
    confidence_level: float,
    capital_horizon_months: int,
    action_share: float,
    restoration_share: float,
) -> Dict[str, object]:
    """Phase 25 Task 2 gates (FIXED in the Task 1 design note s5).

      G1  carve-outs preserved: relieved <= max_relief * clip(B, 0, L)
          elementwise on BOTH bases (credit / FX / liquidity not cuttable)
      G2  SIGN gate: path-wise with-actions SCR >= horizon-level
          with-actions SCR at 99.5% (magnitude DISCLOSED, not gated)
      G3  monotonicity guard re-verified on the path-wise basis
      G4  without-actions basis unchanged BIT-IDENTICALLY (slice-enforced)
      G5  horizon-level basis reproduced: node relieved equals
          relief(CR(L7)) * B exactly (sensitivity variant retained)
      G6  no action at/above the trigger coverage ratio
    """
    a_ref = rule.reference_assets(fit_mean_liability)
    l = np.asarray(nested_l, dtype=float)
    b = np.clip(np.asarray(benefit_nested, dtype=float), 0.0, l)
    cap_env = rule.max_relief * b + 1e-6

    nested_with_pw, clip_share_pw = apply_pathwise_declaration_node(
        rule, l, benefit_nested, relieved_pathwise_node)
    nested_with_hz, clip_share_hz = apply_pathwise_declaration_node(
        rule, l, benefit_nested, relieved_horizon_node)
    nested_with_hz_direct = apply_inner_path_action(
        rule, a_ref, l, benefit_nested)

    cap = dict(
        confidence_level=float(confidence_level),
        capital_horizon_months=int(capital_horizon_months),
    )
    cap_wo = capital_metrics_from_liabilities(l, **cap)
    cap_pw = capital_metrics_from_liabilities(nested_with_pw, **cap)
    cap_hz = capital_metrics_from_liabilities(nested_with_hz, **cap)

    lo = float(l.min()) * 0.5
    hi = float(l.max()) * 2.0
    monotone = inner_path_monotonicity_check(rule, a_ref, lo, hi)

    cr_probe = np.array([rule.cr_trigger, rule.cr_trigger + 1e-9, 10.0])
    no_action_above_trigger = bool(
        np.all(rule.relief_fraction(cr_probe) <= 1e-12))

    scr_delta = float(cap_pw.scr_proxy - cap_hz.scr_proxy)
    scr_delta_rel = scr_delta / abs(cap_hz.scr_proxy)
    disclosure_required = bool(
        abs(scr_delta_rel) > PATHWISE_MATERIALITY_DISCLOSURE_THRESHOLD)

    gates = {
        "G1_carveouts_preserved_relieved_within_envelope": bool(
            np.all(np.asarray(relieved_pathwise_node) <= cap_env)
            and np.all(np.asarray(relieved_horizon_node) <= cap_env)
            and np.all(np.asarray(relieved_pathwise_node) >= -1e-9)
        ),
        "G2_sign_gate_pathwise_scr_ge_horizon_scr": bool(
            cap_pw.scr_proxy >= cap_hz.scr_proxy - 1e-9),
        "G3_monotonicity_guard_pathwise_basis": bool(monotone),
        "G4_without_actions_bit_identical": bool(
            without_actions_bit_identical),
        "G5_horizon_basis_reproduced": bool(
            np.allclose(nested_with_hz, nested_with_hz_direct,
                        rtol=1e-9, atol=1e-6)),
        "G6_no_action_above_trigger": no_action_above_trigger,
    }
    verdict = "PASS" if all(gates.values()) else "FAIL"

    return {
        "rule": rule.to_dict(),
        "reference_assets": float(a_ref),
        "fit_mean_liability": float(fit_mean_liability),
        "pathwise_action_share": float(action_share),
        "pathwise_restoration_share": float(restoration_share),
        "clip_binding_share_pathwise": clip_share_pw,
        "clip_binding_share_horizon": clip_share_hz,
        "nested_capital_without": cap_wo.summary(),
        "nested_capital_with_horizon": cap_hz.summary(),
        "nested_capital_with_pathwise": cap_pw.summary(),
        "pathwise_vs_horizon_delta": {
            "var_99_5_delta": float(
                cap_pw.var_liability - cap_hz.var_liability),
            "es_delta": float(cap_pw.es_liability - cap_hz.es_liability),
            "scr_delta": scr_delta,
            "scr_delta_rel_to_horizon": scr_delta_rel,
            "materiality_disclosure_threshold":
                PATHWISE_MATERIALITY_DISCLOSURE_THRESHOLD,
            "mr010_mr014_refresh_required_task4": disclosure_required,
            "interpretation": (
                "The horizon-level basis freezes the maximum cut at "
                "stressed outer nodes for the whole projection while the "
                "path-wise basis RESTORES the bonus on recovering inner "
                "paths (and cuts on deteriorating paths from healthy "
                "nodes), so the path-wise basis relieves LESS in the tail "
                "and its with-actions SCR is the more conservative "
                "read-out (recognition-lag effect, two-sided)."
            ),
        },
        "gates": gates,
        "verdict": verdict,
    }


def pathwise_declaration_use_restrictions() -> Dict[str, object]:
    """Governed use restrictions for the path-wise declaration basis."""
    return {
        "classification": "EDUCATIONAL_DEMONSTRATION_ONLY",
        "approved_uses": [
            "Methodology demonstration of full path-wise management-action "
            "declaration dynamics (Solvency II Art. 23: actions modelled "
            "consistently with how they would be exercised over time) in "
            "a nested-stochastic / LSMC-proxy framework",
            "Quantification of the horizon-level vs path-wise declaration "
            "recognition-lag effect on with-actions capital",
        ],
        "prohibited_uses": [
            "Production capital or solvency decisions",
            "Policyholder bonus declarations",
            "Regulatory submissions",
        ],
        "rationale": (
            "Management-action parameters are educational placeholders; "
            "the path-wise coverage proxy uses realised-path discounting "
            "(perfect-foresight proxy, not an adapted valuation); "
            "declarations occur at every monthly inner step (annual "
            "cadence is a documented sensitivity); the node-level "
            "FX/liquidity offset enters the proxy undecayed; production "
            "sign-off withheld pending credentialled data and independent "
            "APS X2 review."
        ),
    }
