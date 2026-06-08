"""Phase 26 Task 4 -- full-vs-reanchored delta matrix on the FROZEN copula.

Pure assembly/statistics layer over the already-staged Phase 26 evidence:

  * Task 2 point read-outs  (reagg_result.json): without / level (re-anchored)
    / component (full) SCR proxies under the t- and gaussian-copula.
  * Task 3 frozen-copula bootstrap (200x20k partials): per-replicate
    common-random-number SCR vectors for every basis, on which we build
    PAIRED bootstrap delta CIs (paired = same resampled rows + same copula
    draws per replicate, so the basis-choice delta is isolated from sampling
    noise -- far sharper than differencing two marginal CIs that overlap).

The delta matrix answers Phase 26 Task 4's question directly: does the FULL
path-wise re-aggregation (per-driver composition, COMPONENT basis) move SCR
materially versus the P25T4 analytic RE-ANCHORING (constant-share, LEVEL
basis), and is that move (a) statistically distinguishable from frozen-copula
sampling noise and (b) above the 1% MR-010/MR-014 disclosure trigger?

Copula df/rho and the governed relief scalars (sigma/alpha/beta_fit) stay
FROZEN throughout (Solvency II Art. 234 -- the governed dependence basis is
NOT re-tuned); this module performs NO simulation and changes NO governed
parameter. It only reduces staged evidence.

EDUCATIONAL MODEL: educational placeholders pending credentialled data and
independent APS X2 review. NOT for production capital decisions.
"""
from __future__ import annotations

import hashlib
import json
from typing import Dict, List, Sequence

import numpy as np

# Pre-registered Task 4 design (cycle-29 status; design note s5 lineage).
MR_REFRESH_TRIGGER_FRACTION = 0.01   # 1% move => MR-010/MR-014 numeric refresh
DELTA_CI_LEVEL = 0.95

# Bases in display order (low -> high capital), and the copulas carried on CRN.
BASES = ("without", "level", "component")
BASIS_LABELS = {
    "without": "without-actions",
    "level": "level (re-anchored, P25T4 analytic)",
    "component": "component (full path-wise re-aggregation)",
}
COPULAS = ("t", "g")
COPULA_LABELS = {"t": "t(2.9451)", "g": "gaussian"}

# Pre-registered paired contrasts (name -> (minuend_key, subtrahend_key)).
# Keys are the per-replicate record fields produced by Phase 26 Task 3.
PAIRED_CONTRASTS = {
    # full minus re-anchored: the composition correction (the Phase 26 thesis).
    "composition_correction_t": ("scr_component_t", "scr_level_t"),
    "composition_correction_g": ("scr_component_g", "scr_level_g"),
    # without minus full: the management-action relief embedded in the basis.
    "management_relief_t": ("scr_without_t", "scr_component_t"),
    # gaussian -> t dependence-form sensitivity at each basis.
    "dependence_form_component": ("scr_component_t", "scr_component_g"),
    "dependence_form_level": ("scr_level_t", "scr_level_g"),
}


def paired_delta_ci(records: Sequence[Dict[str, float]],
                    key_minuend: str,
                    key_subtrahend: str,
                    ci_level: float = DELTA_CI_LEVEL) -> Dict[str, object]:
    """Paired percentile-bootstrap CI for (minuend - subtrahend).

    Pairing is across the SAME replicate (common resampled rows + common
    random numbers), so the basis/copula contrast is isolated from the shared
    sampling noise that dominates each marginal CI. ``excludes_zero`` is the
    significance verdict (the contrast is distinguishable from zero at the
    stated CI level).
    """
    a = np.asarray([float(r[key_minuend]) for r in records], dtype=float)
    b = np.asarray([float(r[key_subtrahend]) for r in records], dtype=float)
    d = a - b
    lo_q = (1.0 - float(ci_level)) / 2.0
    hi_q = 1.0 - lo_q
    lo = float(np.quantile(d, lo_q))
    hi = float(np.quantile(d, hi_q))
    base_mean = float(np.mean(b))
    return {
        "n": int(d.size),
        "mean": float(np.mean(d)),
        "se": float(np.std(d, ddof=1)),
        "ci_level": float(ci_level),
        "ci_lo": lo,
        "ci_hi": hi,
        "excludes_zero": bool(lo > 0.0 or hi < 0.0),
        "mean_rel_to_subtrahend": float(np.mean(d) / base_mean) if base_mean else None,
    }


def _point_cell(reagg: Dict[str, object], basis: str, copula: str) -> float:
    ro = reagg["t_readout"] if copula == "t" else reagg["g_readout"]
    return float(ro["scr_" + basis])


def build_point_matrix(reagg: Dict[str, object]) -> Dict[str, Dict[str, float]]:
    """basis -> copula -> point SCR (from the Task 2 re-aggregation)."""
    return {b: {c: _point_cell(reagg, b, c) for c in COPULAS} for b in BASES}


def attach_marginal_cis(bootstrap: Dict[str, object]) -> Dict[str, Dict[str, object]]:
    """basis -> copula -> marginal frozen-copula bootstrap CI (where staged).

    Task 3 staged marginal CIs for component(t,g), level(t), without(t). Cells
    not staged are returned as ``None`` (the paired contrasts below carry the
    significance load, so a full marginal grid is not required).
    """
    out: Dict[str, Dict[str, object]] = {b: {c: None for c in COPULAS} for b in BASES}
    mapping = {
        ("component", "t"): "component_t_scr_ci",
        ("component", "g"): "component_g_scr_ci",
        ("level", "t"): "level_t_scr_ci",
        ("without", "t"): "without_t_scr_ci",
    }
    for (b, c), key in mapping.items():
        if key in bootstrap:
            out[b][c] = bootstrap[key]
    return out


def build_paired_deltas(records: Sequence[Dict[str, float]],
                        ci_level: float = DELTA_CI_LEVEL) -> Dict[str, Dict[str, object]]:
    return {name: paired_delta_ci(records, a, b, ci_level)
            for name, (a, b) in PAIRED_CONTRASTS.items()}


def mr_refresh_trigger(paired: Dict[str, Dict[str, object]],
                       threshold: float = MR_REFRESH_TRIGGER_FRACTION
                       ) -> Dict[str, object]:
    """1% MR-010/MR-014 disclosure trigger on the composition correction.

    The trigger watches the FULL-vs-RE-ANCHORED move (the only basis change
    introduced by Phase 26); the management-relief and dependence-form
    contrasts are pre-existing governed effects, not this phase's change. The
    trigger fires iff |composition correction| / re-anchored base exceeds the
    threshold under EITHER copula.
    """
    t = paired["composition_correction_t"]
    g = paired["composition_correction_g"]
    rel_t = abs(float(t["mean_rel_to_subtrahend"]))
    rel_g = abs(float(g["mean_rel_to_subtrahend"]))
    fired = bool(rel_t > threshold or rel_g > threshold)
    return {
        "threshold": float(threshold),
        "composition_correction_rel_t": float(t["mean_rel_to_subtrahend"]),
        "composition_correction_rel_g": float(g["mean_rel_to_subtrahend"]),
        "max_abs_rel": float(max(rel_t, rel_g)),
        "trigger_fired": fired,
        "statistically_significant_t": bool(t["excludes_zero"]),
        "statistically_significant_g": bool(g["excludes_zero"]),
        "interpretation": (
            "Composition correction (full minus re-anchored) is statistically "
            "{} (paired 95% CI {} zero) but economically {} (max |move| {:.2%} "
            "vs the 1% MR trigger) -> MR-010/MR-014 numeric refresh {}.".format(
                "significant" if (t["excludes_zero"] or g["excludes_zero"]) else "insignificant",
                "excludes" if (t["excludes_zero"] or g["excludes_zero"]) else "includes",
                "immaterial" if not fired else "material",
                max(rel_t, rel_g),
                "NOT required" if not fired else "REQUIRED")),
    }


def delta_matrix_digest(point: Dict[str, Dict[str, float]],
                        paired: Dict[str, Dict[str, object]]) -> str:
    """Stable digest over the point matrix + paired delta means/CIs."""
    payload = {
        "point": {b: {c: round(point[b][c], 6) for c in COPULAS} for b in BASES},
        "paired": {k: [round(v["mean"], 6), round(v["ci_lo"], 6),
                       round(v["ci_hi"], 6)] for k, v in sorted(paired.items())},
    }
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:12]


def rank_invariance_ok(df_rematched: float, rho_max_abs_diff: float,
                       df_target: float, df_tol: float, rho_tol: float
                       ) -> Dict[str, object]:
    """Re-verify the copula is FROZEN (df re-matched within tol; rho frozen)."""
    df_ok = bool(abs(float(df_rematched) - float(df_target)) <= float(df_tol))
    rho_ok = bool(float(rho_max_abs_diff) <= float(rho_tol))
    return {
        "df_rematched": float(df_rematched),
        "df_target": float(df_target),
        "df_within_tol": df_ok,
        "rho_max_abs_diff": float(rho_max_abs_diff),
        "rho_frozen": rho_ok,
        "rank_invariant": bool(df_ok and rho_ok),
    }


def delta_matrix_use_restrictions() -> Dict[str, object]:
    return {
        "classification": "EDUCATIONAL",
        "production_use": "PROHIBITED pending credentialled data + independent APS X2 review",
        "frozen": [
            "copula df = 2.9451 (rank invariance; SII Art. 234)",
            "rho correlation matrix (max|diff| <= 1e-12)",
            "governed sigma/alpha/beta_fit (P25T3 FIT values; no re-tuning)",
        ],
        "scope": [
            "Delta matrix REDUCES already-staged Task 2/Task 3 evidence; it runs "
            "NO new simulation and changes NO governed parameter.",
            "Paired deltas use common-random-number replicate pairing; the CIs are "
            "frozen-copula sampling bands, NOT calibration uncertainty.",
            "The material gap to the nested truth (Task 3: copula-form dominated) is "
            "NOT a basis-choice effect and is unchanged by this task.",
        ],
        "standards": [
            "Solvency II Delegated Regulation Article 234",
            "SOA ASOP 56 section 3.5; ASOP 25 section 3.3",
            "IA TAS M section 3.6",
            "Efron & Tibshirani (1993) paired bootstrap",
        ],
    }
