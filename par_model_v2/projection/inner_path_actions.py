"""Inner-path management-action dynamics prototype (Phase 24 Task 3).

EDUCATIONAL ONLY -- not a production bonus-declaration or capital model.

Phase 23 Task 3 applied the governed ``ManagementActionRule`` as an
outer-node transform of the full conditional liability.  This module relaxes
that approximation one step: the same retained-bonus decision is applied to
the cuttable projected bonus-cashflow PV inside the conditional liability
decomposition, while guaranteed and non-cuttable liability components are
left unchanged.

The prototype is intentionally horizon-level, not a full monthly
declaration engine.  A response factor represents the share of future bonus
cashflow PV that can react inside the one-year inner projection; values below
1.0 disclose recognition lag / already-vested bonus inertia.  Setting the
factor to 1.0 recovers the Phase 23 outer-node transform exactly.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Dict

import numpy as np

from par_model_v2.projection.joint_action_aggregation import (
    INNER_PATH_OOS_R2_GATE,
    INNER_PATH_VAR_REL_ERROR_GATE,
)
from par_model_v2.projection.management_actions import ManagementActionRule
from par_model_v2.projection.nested_stochastic_tvog import (
    capital_metrics_from_liabilities,
)


@dataclass(frozen=True)
class InnerPathActionConfig:
    """Prototype parameters for horizon-level inner-path bonus response."""

    bonus_cashflow_response: float = 0.85

    def __post_init__(self) -> None:
        if not (0.0 < self.bonus_cashflow_response <= 1.0):
            raise ValueError("bonus_cashflow_response must be in (0, 1]")

    def to_dict(self) -> Dict[str, float]:
        return {"bonus_cashflow_response": float(self.bonus_cashflow_response)}


def apply_inner_path_bonus_action(
    liabilities: np.ndarray,
    rule: ManagementActionRule,
    reference_assets: float,
    config: InnerPathActionConfig | None = None,
) -> np.ndarray:
    """Apply the bonus cut to projected cuttable bonus cashflow PV.

    The decomposition is:

        L = guaranteed_and_noncuttable + cuttable_bonus_pv
        cuttable_bonus_pv = bonus_share * L
        relief = response * (1-pre_floor) * (1-cut_factor(CR)) * cuttable_bonus_pv

    where CR is still computed on the pre-action liability.  The same
    governance rule therefore drives the decision, but relief is recorded as
    a cashflow-component response rather than as an opaque transform of the
    whole liability.
    """
    cfg = config or InnerPathActionConfig()
    l_pre = np.asarray(liabilities, dtype=float)
    if np.any(l_pre <= 0.0):
        raise ValueError("pre-action liabilities must be positive")
    cr = rule.coverage_ratio(l_pre, reference_assets)
    retained = rule.cut_factor(cr)
    cuttable_bonus_pv = rule.bonus_share * l_pre
    relief = (
        cfg.bonus_cashflow_response
        * (1.0 - rule.pre_floor)
        * (1.0 - retained)
        * cuttable_bonus_pv
    )
    return l_pre - relief


def inner_path_use_restrictions() -> Dict[str, object]:
    return {
        "classification": "EDUCATIONAL_PROTOTYPE_ONLY",
        "approved_uses": [
            "Quantifying the first-order delta between outer-node and "
            "inner-path management-action treatment",
            "Regression testing that the proxy applies the same cashflow "
            "response basis as the nested ground truth",
        ],
        "prohibited_uses": [
            "Production bonus declarations",
            "Regulatory capital or solvency submissions",
            "Policyholder communication or pricing",
        ],
        "residuals": [
            "No monthly path-wise re-declaration loop; the action is evaluated "
            "once at the capital horizon.",
            "The bonus-cashflow share and response factor are educational "
            "placeholders pending credentialled management-practice data.",
            "Reference assets remain the fixed Phase 23 leakage-free proxy.",
        ],
    }


def _r2(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    ss_res = float(np.sum((y_true - y_pred) ** 2))
    ss_tot = float(np.sum((y_true - y_true.mean()) ** 2))
    return 1.0 - ss_res / ss_tot if ss_tot > 0.0 else float("nan")


def _rel(a: float, b: float) -> float:
    return abs(a - b) / (abs(b) if abs(b) > 1e-9 else 1.0)


def validate_inner_path_actions(
    rule: ManagementActionRule,
    fit_mean_liability: float,
    val_truth: np.ndarray,
    val_pred: np.ndarray,
    nested_l: np.ndarray,
    proxy_l: np.ndarray,
    confidence_level: float,
    capital_horizon_months: int,
    config: InnerPathActionConfig | None = None,
) -> Dict[str, object]:
    """OOS validation with the inner-path cashflow-response basis.

    The same deterministic cashflow-response basis is applied to the heavy
    nested truth and to the proxy prediction, matching the Phase 24 Task 1
    pre-registration for Task 3.
    """
    cfg = config or InnerPathActionConfig()
    a_ref = rule.reference_assets(fit_mean_liability)
    nested_l = np.asarray(nested_l, dtype=float)
    proxy_l = np.asarray(proxy_l, dtype=float)
    val_truth = np.asarray(val_truth, dtype=float)
    val_pred = np.asarray(val_pred, dtype=float)

    nested_inner = apply_inner_path_bonus_action(nested_l, rule, a_ref, cfg)
    proxy_inner = apply_inner_path_bonus_action(proxy_l, rule, a_ref, cfg)
    val_truth_inner = apply_inner_path_bonus_action(val_truth, rule, a_ref, cfg)
    val_pred_inner = apply_inner_path_bonus_action(val_pred, rule, a_ref, cfg)

    nested_outer = rule.apply_to_liabilities(nested_l, a_ref)
    proxy_outer = rule.apply_to_liabilities(proxy_l, a_ref)

    cap_args = dict(
        confidence_level=float(confidence_level),
        capital_horizon_months=int(capital_horizon_months),
    )
    nested_wo = capital_metrics_from_liabilities(nested_l, **cap_args)
    nested_i = capital_metrics_from_liabilities(nested_inner, **cap_args)
    proxy_i = capital_metrics_from_liabilities(proxy_inner, **cap_args)
    nested_o = capital_metrics_from_liabilities(nested_outer, **cap_args)
    proxy_o = capital_metrics_from_liabilities(proxy_outer, **cap_args)

    cr_nested = rule.coverage_ratio(nested_l, a_ref)
    oos_r2 = _r2(val_truth_inner, val_pred_inner)
    var_rel = _rel(proxy_i.var_liability, nested_i.var_liability)
    es_rel = _rel(proxy_i.es_liability, nested_i.es_liability)
    scr_rel = _rel(proxy_i.scr_proxy, nested_i.scr_proxy)

    grid = np.linspace(
        float(min(nested_l.min(), proxy_l.min(), val_truth.min())) * 0.5,
        float(max(nested_l.max(), proxy_l.max(), val_truth.max())) * 2.0,
        20001,
    )
    grid_out = apply_inner_path_bonus_action(grid, rule, a_ref, cfg)
    monotone = bool(np.all(np.diff(grid_out) >= -1e-9))

    gates = {
        "G1_inner_path_oos_r2_ge_0p95": bool(oos_r2 >= INNER_PATH_OOS_R2_GATE),
        "G2_inner_path_var_rel_error_le_0p10": bool(
            var_rel <= INNER_PATH_VAR_REL_ERROR_GATE
        ),
        "G3_inner_path_capital_le_without_actions": bool(
            nested_i.var_liability <= nested_wo.var_liability + 1e-9
            and nested_i.scr_proxy <= nested_wo.scr_proxy + 1e-9
        ),
        "G4_inner_path_monotone": monotone,
    }
    digest_src = json.dumps(
        {
            "rule": rule.to_dict(),
            "config": cfg.to_dict(),
            "fit_mean": float(fit_mean_liability),
            "nested_var": nested_i.var_liability,
            "proxy_var": proxy_i.var_liability,
            "oos_r2": oos_r2,
        },
        sort_keys=True,
    ).encode("utf-8")

    return {
        "rule": rule.to_dict(),
        "config": cfg.to_dict(),
        "reference_assets": float(a_ref),
        "fit_mean_liability": float(fit_mean_liability),
        "active_share_nested": float(np.mean(cr_nested < rule.cr_trigger)),
        "floor_share_nested": float(np.mean(cr_nested <= rule.cr_floor)),
        "oos_r2_inner_path": float(oos_r2),
        "nested_capital_without": nested_wo.summary(),
        "nested_capital_inner_path": nested_i.summary(),
        "proxy_capital_inner_path": proxy_i.summary(),
        "nested_capital_outer_node": nested_o.summary(),
        "proxy_capital_outer_node": proxy_o.summary(),
        "var_rel_error_inner_path": float(var_rel),
        "es_rel_error_inner_path": float(es_rel),
        "scr_rel_error_inner_path": float(scr_rel),
        "outer_node_vs_inner_path": {
            "nested_var_delta": float(nested_i.var_liability - nested_o.var_liability),
            "nested_scr_delta": float(nested_i.scr_proxy - nested_o.scr_proxy),
            "proxy_var_delta": float(proxy_i.var_liability - proxy_o.var_liability),
            "interpretation": (
                "positive means the cashflow-response basis gives less immediate "
                "relief than the Phase 23 outer-node transform"
            ),
        },
        "gates": gates,
        "verdict": "PASS" if all(gates.values()) else "FAIL",
        "reproducibility_digest": hashlib.sha256(digest_src).hexdigest(),
    }

