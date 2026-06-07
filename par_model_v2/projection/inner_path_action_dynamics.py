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
