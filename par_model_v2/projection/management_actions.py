"""
Phase 23 Task 3 - Management actions: dynamic reversionary-bonus participation cut.

Implements Method B of the Phase 23 Task 1 design note
(docs/validation/PHASE23_TASK1_DESIGN_NOTE.md): an objective, verifiable,
MONOTONE management-action rule per Solvency II Delegated Regulation Art. 23.

    cut_factor(CR) = clip((CR - cr_floor) / (cr_trigger - cr_floor), 0, 1)

CR is an asset/liability coverage-ratio proxy at the outer node,
CR = reference_assets / L_pre_action.  ``cut_factor`` is the RETAINED share of
the cuttable participating bonus: 1 at/above the trigger (NO action), 0
at/below the floor (maximum cut).  A policyholder-reasonable-expectation (PRE)
floor retains at least ``pre_floor`` of the participating bonus regardless of
stress, so the maximum liability relief is bonus_share * (1 - pre_floor).

With-actions conditional liability (deterministic outer-node transform of the
pre-action conditional liability; the cut DECISION uses the pre-action CR):

    L_with = L * (1 - bonus_share * (1 - pre_floor) * (1 - cut_factor(CR(L))))

Monotonicity of L -> L_with is enforced at construction via the sufficient
condition  max_relief * cr_trigger / (cr_trigger - cr_floor) < 1 - max_relief,
which bounds sup_L L * d(relief)/dL on the active band.

EDUCATIONAL MODEL: trigger / floor / bonus-share / PRE / reference-coverage
parameters are educational placeholders pending credentialled
management-practice data and independent APS X2 review.  NOT for production
capital decisions.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

import numpy as np

from par_model_v2.projection.nested_stochastic_tvog import (
    capital_metrics_from_liabilities,
)


# Fixed pre-registered acceptance gates (Phase 23 Task 1 design note s5).
OOS_R2_GATE = 0.95
VAR_REL_ERROR_GATE = 0.10


@dataclass(frozen=True)
class ManagementActionRule:
    """Dynamic reversionary-bonus participation cut under solvency stress.

    Parameters (educational placeholders, disclosed)
    ------------------------------------------------
    cr_trigger : float
        Coverage ratio at/above which NO action is taken (full bonus).
    cr_floor : float
        Coverage ratio at/below which the maximum cut applies.
    bonus_share : float
        Share of the conditional liability attributable to cuttable
        participating bonus (educational placeholder).
    pre_floor : float
        Policyholder-reasonable-expectation floor: minimum retained share of
        the participating bonus under maximum stress.
    reference_coverage : float
        Baseline coverage ratio used to set reference assets from a baseline
        (fit-sample mean) liability: A_ref = reference_coverage * L_baseline.
    """

    cr_trigger: float = 1.10
    cr_floor: float = 0.90
    bonus_share: float = 0.30
    pre_floor: float = 0.60
    reference_coverage: float = 1.12

    def __post_init__(self) -> None:
        if not (self.cr_floor > 0.0):
            raise ValueError("cr_floor must be positive")
        if not (self.cr_trigger > self.cr_floor):
            raise ValueError("cr_trigger must exceed cr_floor")
        if not (0.0 <= self.bonus_share < 1.0):
            raise ValueError("bonus_share must be in [0, 1)")
        if not (0.0 <= self.pre_floor <= 1.0):
            raise ValueError("pre_floor must be in [0, 1]")
        if not (self.reference_coverage > 0.0):
            raise ValueError("reference_coverage must be positive")
        band = self.cr_trigger - self.cr_floor
        k = self.max_relief
        if k > 0.0 and k * self.cr_trigger / band >= 1.0 - k:
            raise ValueError(
                "monotonicity guard violated: max_relief * cr_trigger / "
                "(cr_trigger - cr_floor) must be < 1 - max_relief; widen the "
                "trigger-floor band or reduce the cut depth"
            )

    @property
    def max_relief(self) -> float:
        """Maximum fraction of the conditional liability that can be relieved."""
        return self.bonus_share * (1.0 - self.pre_floor)

    def cut_factor(self, cr: np.ndarray) -> np.ndarray:
        """Retained-bonus factor: clip((CR-floor)/(trigger-floor), 0, 1)."""
        cr = np.asarray(cr, dtype=float)
        band = self.cr_trigger - self.cr_floor
        return np.clip((cr - self.cr_floor) / band, 0.0, 1.0)

    def reference_assets(self, baseline_liability: float) -> float:
        """A_ref = reference_coverage * baseline (fit-sample mean) liability."""
        baseline = float(baseline_liability)
        if not (baseline > 0.0):
            raise ValueError("baseline_liability must be positive")
        return self.reference_coverage * baseline

    def coverage_ratio(
        self, liabilities: np.ndarray, reference_assets: float
    ) -> np.ndarray:
        """Outer-node coverage-ratio proxy CR = A_ref / L_pre_action."""
        l = np.asarray(liabilities, dtype=float)
        if np.any(l <= 0.0):
            raise ValueError("pre-action liabilities must be positive")
        a_ref = float(reference_assets)
        if not (a_ref > 0.0):
            raise ValueError("reference_assets must be positive")
        return a_ref / l

    def relief_fraction(self, cr: np.ndarray) -> np.ndarray:
        """Fraction of the conditional liability relieved by the bonus cut."""
        return self.max_relief * (1.0 - self.cut_factor(cr))

    def apply_to_liabilities(
        self, liabilities: np.ndarray, reference_assets: float
    ) -> np.ndarray:
        """With-actions conditional liabilities (deterministic transform)."""
        l = np.asarray(liabilities, dtype=float)
        cr = self.coverage_ratio(l, reference_assets)
        return l * (1.0 - self.relief_fraction(cr))

    def is_monotone(
        self,
        reference_assets: float,
        l_lo: float,
        l_hi: float,
        n_grid: int = 20001,
    ) -> bool:
        """Numerically verify L -> L_with is non-decreasing on [l_lo, l_hi]."""
        if not (0.0 < l_lo < l_hi):
            raise ValueError("require 0 < l_lo < l_hi")
        grid = np.linspace(float(l_lo), float(l_hi), int(n_grid))
        out = self.apply_to_liabilities(grid, reference_assets)
        return bool(np.all(np.diff(out) >= -1e-9))

    def to_dict(self) -> Dict[str, float]:
        return {
            "cr_trigger": self.cr_trigger,
            "cr_floor": self.cr_floor,
            "bonus_share": self.bonus_share,
            "pre_floor": self.pre_floor,
            "reference_coverage": self.reference_coverage,
            "max_relief": self.max_relief,
        }


def _r2(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    ss_res = float(np.sum((y_true - y_pred) ** 2))
    ss_tot = float(np.sum((y_true - y_true.mean()) ** 2))
    return 1.0 - ss_res / ss_tot if ss_tot > 0 else float("nan")


def _rel(a: float, b: float) -> float:
    return abs(a - b) / (abs(b) if abs(b) > 1e-9 else 1.0)


def validate_with_actions(
    rule: ManagementActionRule,
    fit_mean_liability: float,
    val_truth: np.ndarray,
    val_pred: np.ndarray,
    nested_l: np.ndarray,
    proxy_l: np.ndarray,
    confidence_level: float,
    capital_horizon_months: int,
) -> Dict[str, object]:
    """Seven-driver OOS re-validation with the management-action rule applied.

    The rule is a deterministic outer-node transform, so it is applied to the
    nested conditional liability (ground truth) AND to the proxy prediction
    (analytic post-composition basis feature).  Reference assets are calibrated
    on the FIT-sample mean liability only (leakage-free).

    Fixed pre-registered gates (Task 1 design note s5):
      G1  OOS R^2 (with actions)            >= 0.95
      G2  VaR rel err proxy-vs-nested (with) <= 0.10
      G3  nested with-actions VaR and SCR    <= without-actions (sanity)
      G4  rule monotone on the realised liability range
      G5  no action at/above the trigger coverage ratio
    """
    a_ref = rule.reference_assets(fit_mean_liability)

    nested_l = np.asarray(nested_l, dtype=float)
    proxy_l = np.asarray(proxy_l, dtype=float)
    val_truth = np.asarray(val_truth, dtype=float)
    val_pred = np.asarray(val_pred, dtype=float)

    nested_with = rule.apply_to_liabilities(nested_l, a_ref)
    proxy_with = rule.apply_to_liabilities(proxy_l, a_ref)
    val_truth_with = rule.apply_to_liabilities(val_truth, a_ref)
    val_pred_with = rule.apply_to_liabilities(val_pred, a_ref)

    cr_nested = rule.coverage_ratio(nested_l, a_ref)
    active_share = float(np.mean(cr_nested < rule.cr_trigger))
    floor_share = float(np.mean(cr_nested <= rule.cr_floor))

    cap = dict(
        confidence_level=float(confidence_level),
        capital_horizon_months=int(capital_horizon_months),
    )
    nested_cap_wo = capital_metrics_from_liabilities(nested_l, **cap)
    nested_cap_w = capital_metrics_from_liabilities(nested_with, **cap)
    proxy_cap_wo = capital_metrics_from_liabilities(proxy_l, **cap)
    proxy_cap_w = capital_metrics_from_liabilities(proxy_with, **cap)

    lo = float(min(nested_l.min(), proxy_l.min(), val_truth.min())) * 0.5
    hi = float(max(nested_l.max(), proxy_l.max(), val_truth.max())) * 2.0
    monotone = rule.is_monotone(a_ref, lo, hi)

    cr_probe = np.array([rule.cr_trigger, rule.cr_trigger + 1e-9, 10.0])
    no_action_above_trigger = bool(
        np.all(rule.relief_fraction(cr_probe) <= 1e-12)
    )

    oos_r2_with = _r2(val_truth_with, val_pred_with)
    oos_r2_without = _r2(val_truth, val_pred)
    var_rel_with = _rel(proxy_cap_w.var_liability, nested_cap_w.var_liability)
    es_rel_with = _rel(proxy_cap_w.es_liability, nested_cap_w.es_liability)
    scr_rel_with = _rel(proxy_cap_w.scr_proxy, nested_cap_w.scr_proxy)

    gates = {
        "G1_oos_r2_with_actions_ge_0p95": bool(oos_r2_with >= OOS_R2_GATE),
        "G2_var_rel_error_with_actions_le_0p10": bool(
            var_rel_with <= VAR_REL_ERROR_GATE
        ),
        "G3_with_actions_capital_le_without": bool(
            nested_cap_w.var_liability <= nested_cap_wo.var_liability + 1e-9
            and nested_cap_w.scr_proxy <= nested_cap_wo.scr_proxy + 1e-9
        ),
        "G4_rule_monotone": bool(monotone),
        "G5_no_action_above_trigger": no_action_above_trigger,
    }
    verdict = "PASS" if all(gates.values()) else "FAIL"

    return {
        "rule": rule.to_dict(),
        "reference_assets": float(a_ref),
        "fit_mean_liability": float(fit_mean_liability),
        "active_share_nested": active_share,
        "floor_share_nested": floor_share,
        "oos_r2_with_actions": float(oos_r2_with),
        "oos_r2_without_actions": float(oos_r2_without),
        "nested_capital_without": nested_cap_wo.summary(),
        "nested_capital_with": nested_cap_w.summary(),
        "proxy_capital_without": proxy_cap_wo.summary(),
        "proxy_capital_with": proxy_cap_w.summary(),
        "var_rel_error_with_actions": float(var_rel_with),
        "es_rel_error_with_actions": float(es_rel_with),
        "scr_rel_error_with_actions": float(scr_rel_with),
        "nested_var_reduction": float(
            nested_cap_wo.var_liability - nested_cap_w.var_liability
        ),
        "nested_scr_reduction": float(
            nested_cap_wo.scr_proxy - nested_cap_w.scr_proxy
        ),
        "gates": gates,
        "verdict": verdict,
    }


def management_action_use_restrictions() -> Dict[str, object]:
    """Governed use restrictions for the management-action rule."""
    return {
        "classification": "EDUCATIONAL_DEMONSTRATION_ONLY",
        "approved_uses": [
            "Methodology demonstration of Solvency II Art. 23 management "
            "actions in a nested-stochastic / LSMC-proxy framework",
            "Training material on dynamic bonus-participation rules",
        ],
        "prohibited_uses": [
            "Production capital or solvency decisions",
            "Policyholder bonus declarations",
            "Regulatory submissions",
        ],
        "rationale": (
            "Trigger, floor, bonus-share, PRE and reference-coverage "
            "parameters are educational placeholders; no credentialled "
            "management-practice data; production sign-off withheld pending "
            "independent APS X2 review."
        ),
    }
