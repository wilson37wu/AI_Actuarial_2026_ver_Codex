"""
Phase 25 Task 1 - design-note helper: full path-wise bonus declaration dynamics.

Addresses the residual DOCUMENTED in the Phase 24 Task 3 report
(docs/validation/PHASE24_TASK3_INNER_PATH_ACTION_REPORT.json,
``residual_documented``): the governed bonus-cut decision is currently taken
ONCE at the outer node (horizon-level declared-rate response) and the
retained-bonus factor is CONSTANT across the inner paths of one outer node.
Phase 25 designs the refinement in which the declaration is re-evaluated at
EVERY inner time step on a path-wise coverage proxy (path-wise basis).

This module provides, for the Task 1 design note ONLY:

- a SYNTHETIC single-fund participating product with a reversionary bonus that
  attaches to the liability, so that NO real archived nested benchmark is
  consumed before the Task 2 gates;
- three declaration bases on common random numbers: ``without`` (full target
  bonus), ``horizon`` (decision frozen at t=0 from the outer-node coverage
  ratio - the Phase 24 Task 3 convention), ``pathwise`` (decision re-evaluated
  each step on the path-wise coverage ratio), plus a ``max_cut`` bound basis;
- the recognition-lag pre-study: at deeply stressed outer nodes the
  horizon-level basis freezes the maximum cut for the whole projection while
  the path-wise basis RESTORES the bonus on recovering paths, so the
  horizon-level basis UNDERSTATES the with-actions tail loss; on healthy
  nodes the horizon-level basis never cuts while the path-wise basis cuts on
  deteriorating paths (the two-sided recognition-lag effect);
- FIXED pre-registered acceptance gates for Phase 25 Tasks 2-4 (no
  gate-shopping; recorded BEFORE any real-data path-wise benchmark).

EDUCATIONAL MODEL: all parameters are educational placeholders pending
credentialled management-practice data and independent APS X2 review.
NOT for production capital decisions.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Dict

import numpy as np

from par_model_v2.projection.management_actions import ManagementActionRule

# ---------------------------------------------------------------------------
# Fixed pre-registered acceptance gates (Phase 25 Task 1 design note s5).
# ---------------------------------------------------------------------------
PATHWISE_OOS_R2_GATE = 0.95
PATHWISE_VAR_REL_ERROR_GATE = 0.10
# Disclosure trigger (NOT a pass/fail gate): if |pathwise - horizon| SCR delta
# exceeds this fraction of the horizon-basis SCR, MR-010/MR-014 must be
# refreshed with the path-wise figures and the delta surfaced in the UI.
PATHWISE_MATERIALITY_DISCLOSURE_THRESHOLD = 0.01
# Archived Phase 24 Task 3 inner-path horizon-level SCR (comparison baseline
# for Task 2 read-outs; motivation only, NOT consumed by any gate here).
HORIZON_BASIS_SCR_REFERENCE = 40_852.0541


@dataclass
class PathwiseBonusConfig:
    """Synthetic pre-study configuration (educational placeholders)."""

    n_outer: int = 4000
    n_inner: int = 100
    n_steps: int = 10
    mu: float = 0.05
    sigma: float = 0.15
    guaranteed_rate: float = 0.02
    bonus_target: float = 0.02
    rf: float = 0.02
    cr0_center: float = 1.12
    cr0_sigma: float = 0.15
    l0: float = 100.0
    seed: int = 42
    confidence: float = 0.995

    def __post_init__(self) -> None:
        if self.n_outer < 100:
            raise ValueError("n_outer must be >= 100")
        if self.n_inner < 10:
            raise ValueError("n_inner must be >= 10")
        if self.n_steps < 2:
            raise ValueError("n_steps must be >= 2 (path-wise needs a path)")
        if not (0.0 < self.confidence < 1.0):
            raise ValueError("confidence must be in (0, 1)")
        if self.sigma <= 0.0 or self.cr0_sigma <= 0.0:
            raise ValueError("sigma and cr0_sigma must be positive")
        if self.bonus_target < 0.0 or self.l0 <= 0.0 or self.cr0_center <= 0.0:
            raise ValueError("bonus_target >= 0 and l0, cr0_center > 0 required")

    def to_dict(self) -> Dict[str, float]:
        return {
            "n_outer": self.n_outer, "n_inner": self.n_inner,
            "n_steps": self.n_steps, "mu": self.mu, "sigma": self.sigma,
            "guaranteed_rate": self.guaranteed_rate,
            "bonus_target": self.bonus_target, "rf": self.rf,
            "cr0_center": self.cr0_center, "cr0_sigma": self.cr0_sigma,
            "l0": self.l0, "seed": self.seed, "confidence": self.confidence,
        }


def retained_bonus_rate(rule: ManagementActionRule, cr: np.ndarray) -> np.ndarray:
    """Retained share of the TARGET bonus rate at coverage ratio ``cr``.

    The PRE floor retains ``pre_floor`` of the participating bonus regardless
    of stress; ``rule.cut_factor`` is the retained share of the CUTTABLE part:

        retained = pre_floor + (1 - pre_floor) * cut_factor(cr)  in [pre_floor, 1]
    """
    return rule.pre_floor + (1.0 - rule.pre_floor) * rule.cut_factor(cr)


BASES = ("without", "horizon", "pathwise", "max_cut")


def simulate_bases(cfg: PathwiseBonusConfig, rule: ManagementActionRule) -> Dict[str, object]:
    """Simulate the four declaration bases on COMMON random numbers.

    Reversionary bonus attaches to the liability: L_{t+1} = L_t * (1 + g +
    b_target * retained_t); assets follow the same lognormal path for every
    basis (the bonus is not paid out within the horizon), so any difference
    between bases is the declaration dynamics ONLY.  The decision variable is
    the basis's own path-wise coverage ratio CR_t = A_t / L_t (pre-step).

    Returns per-outer-node conditional net losses E_inner[(L_T - A_T)] * disc
    for each basis, plus path-wise action/restoration diagnostics.
    """
    rng = np.random.default_rng(cfg.seed)
    cr0 = cfg.cr0_center * np.exp(
        cfg.cr0_sigma * rng.standard_normal(cfg.n_outer) - 0.5 * cfg.cr0_sigma ** 2
    )
    growth = np.exp(
        (cfg.mu - 0.5 * cfg.sigma ** 2)
        + cfg.sigma * rng.standard_normal((cfg.n_steps, cfg.n_outer, cfg.n_inner))
    )
    disc = (1.0 + cfg.rf) ** (-cfg.n_steps)
    ret_h0 = retained_bonus_rate(rule, cr0)
    out: Dict[str, object] = {"cr0": cr0, "config": cfg.to_dict(), "rule": rule.to_dict()}
    eps = 1e-12
    for basis in BASES:
        a = np.repeat((cr0 * cfg.l0)[:, None], cfg.n_inner, axis=1)
        liab = np.full((cfg.n_outer, cfg.n_inner), cfg.l0)
        prev_ret = None
        had_cut = np.zeros((cfg.n_outer, cfg.n_inner), dtype=bool)
        restored = np.zeros_like(had_cut)
        for t in range(cfg.n_steps):
            if basis == "without":
                ret = np.ones_like(liab)
            elif basis == "horizon":
                ret = np.repeat(ret_h0[:, None], cfg.n_inner, axis=1)
            elif basis == "max_cut":
                ret = np.full_like(liab, rule.pre_floor)
            else:  # pathwise: decision re-evaluated on the path-wise CR
                ret = retained_bonus_rate(rule, a / liab)
                if prev_ret is not None:
                    restored |= had_cut & (ret > prev_ret + eps)
                had_cut |= ret < 1.0 - eps
                prev_ret = ret
            liab = liab * (1.0 + cfg.guaranteed_rate + cfg.bonus_target * ret)
            a = a * growth[t]
        out[basis] = (liab - a).mean(axis=1) * disc
        if basis == "pathwise":
            out["pathwise_action_share"] = float(had_cut.mean())
            out["pathwise_restoration_share"] = float((had_cut & restored).mean())
    return out


def synthetic_recognition_lag_pre_study(
    seed: int = 42, n_outer: int = 4000, n_inner: int = 100, n_steps: int = 10
) -> Dict[str, object]:
    """Recognition-lag mechanism pre-study on the synthetic fund.

    Demonstrates (a) the SIGN of the horizon-level understatement at the
    99.5% tail, (b) that bonus restoration is a real dynamic (positive share
    of cut-then-restored inner paths), and (c) elementwise bound consistency
    (every with-actions basis lies between ``without`` and ``max_cut``).
    """
    cfg = PathwiseBonusConfig(n_outer=n_outer, n_inner=n_inner, n_steps=n_steps, seed=seed)
    rule = ManagementActionRule()
    sim = simulate_bases(cfg, rule)
    q = cfg.confidence
    var_ = {b: float(np.quantile(sim[b], q)) for b in BASES}
    mean_ = {b: float(np.mean(sim[b])) for b in BASES}
    scr_ = {b: var_[b] - mean_[b] for b in BASES}
    tol = 1e-9 * cfg.l0
    wo, pw, hz, mc = (np.asarray(sim[b]) for b in ("without", "pathwise", "horizon", "max_cut"))
    bounds_ok = bool(
        np.all(pw <= wo + tol) and np.all(pw >= mc - tol)
        and np.all(hz <= wo + tol) and np.all(hz >= mc - tol)
    )
    understatement_sign_ok = bool(var_["pathwise"] > var_["horizon"])
    relief_ordering_ok = bool(var_["without"] >= var_["pathwise"] > var_["horizon"] >= var_["max_cut"])
    horizon_understatement_rel = float(
        (var_["pathwise"] - var_["horizon"]) / abs(var_["pathwise"])
    )
    median_diff_pathwise_minus_horizon = float(np.median(pw - hz))
    payload = {
        "config": cfg.to_dict(), "rule": rule.to_dict(),
        "var995": {k: round(v, 6) for k, v in var_.items()},
        "scr": {k: round(v, 6) for k, v in scr_.items()},
    }
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    return {
        "seed": seed, "n_outer": n_outer, "n_inner": n_inner, "n_steps": n_steps,
        "config": cfg.to_dict(), "rule": rule.to_dict(),
        "var995": var_, "mean": mean_, "scr_proxy": scr_,
        "horizon_understatement_rel_at_var995": horizon_understatement_rel,
        "median_diff_pathwise_minus_horizon": median_diff_pathwise_minus_horizon,
        "pathwise_action_share": sim["pathwise_action_share"],
        "pathwise_restoration_share": sim["pathwise_restoration_share"],
        "understatement_sign_ok": understatement_sign_ok,
        "relief_ordering_ok": relief_ordering_ok,
        "bounds_ok": bounds_ok,
        "mechanism_demonstrated": bool(
            understatement_sign_ok and bounds_ok
            and sim["pathwise_restoration_share"] > 0.0
        ),
        "digest": digest,
    }


def pathwise_bonus_use_restrictions() -> Dict[str, object]:
    """Use restrictions for the path-wise declaration design (disclosed)."""
    return {
        "classification": "EDUCATIONAL",
        "production_use": False,
        "restrictions": [
            "Synthetic pre-study demonstrates the recognition-lag MECHANISM, not the magnitude, of the real-data effect.",
            "Reversionary-bonus attachment and single-fund dynamics are simplifications of the governed 7-driver nested model.",
            "Declaration parameters (trigger/floor/PRE/target bonus) are educational placeholders pending credentialled data + APS X2 review.",
            "No real archived nested benchmark is consumed before the Phase 25 Task 2 gates (no gate-shopping).",
        ],
        "gates": {
            "pathwise_oos_r2_gate": PATHWISE_OOS_R2_GATE,
            "pathwise_var_rel_error_gate": PATHWISE_VAR_REL_ERROR_GATE,
            "materiality_disclosure_threshold": PATHWISE_MATERIALITY_DISCLOSURE_THRESHOLD,
        },
    }
