"""
Phase 22 Task 1 — Six-Driver OOS Proxy-Validation Remediation (hardening)
=========================================================================

Remediated re-run of the Phase 21 Task 2 six-driver (G2++ rate, equity,
credit, lapse, mortality-trend, FX-translation) out-of-sample LSMC proxy
validation, applying ALL THREE remediation options recorded in
MODEL_DEV_LOG.md (2026-06-07 cycle 2) after the honest PARTIAL verdict
(OOS R² 0.9498 vs the 0.95 gate):

1. **De-noised regression targets** — the fitting target for each training
   state is the mean of ``fit_n_inner`` (default 8, was 1) inner Q-paths of
   the five-driver conditional liability, plus the CIP-exact FX leg.  The
   per-state seed protocol is ``SeedSequence(fit_seed + 1).spawn(n_fit)`` —
   IDENTICAL to the governed Phase 21 kernel, so ``fit_n_inner=1`` reproduces
   the Phase 21 fitting targets bit-for-bit (regression-tested).
2. **More training states** — ``n_fit`` 500 → 2,000 via the same staged
   slice-stable CRN protocol (staged == monolithic, bit-identical).
3. **Targeted deg-2 basis on rate/equity only** — a 9-term quintivariate
   surface: deg-1 in all five stochastic-valuation drivers PLUS {r², S², r·S}
   (rate/equity curvature only), in the analytic CIP-exact-FX-offset mode that
   dominated the Phase 21 sweep.  This adds curvature exactly where the
   liability is known to be convex (guarantee optionality in rates/equity)
   without the full deg-2 term count that overfitted in Phase 21 (deg-2
   hexavariate OOS R² 0.794).  The targeted surface competes against the FULL
   governed (degree, max_interaction_order) × fx_mode sweep on the SAME
   fitting data and the SAME disjoint-seed hold-out; selection stays by OOS
   RMSE — no gate-shopping.

The eval nested benchmark is also de-noised: ``nested_n_inner`` 96 → 256.

Phase 22 gate (stricter than Phase 21): OOS R² ≥ 0.95 AND VaR, ES **and SCR**
rel err ≤ 10% AND leakage-free AND overfit gap ≤ 0.05 AND FX-axis slope rel
err ≤ 10%.

EDUCATIONAL MODEL: placeholder parameters; not for production capital.

SOA ASOP 7 §3.3; ASOP 25 §3.3; ASOP 56 §3.1.3/§3.5; IA TAS M §3.2/§3.6;
IFoA proxy-modelling working party; Longstaff & Schwartz (2001);
Solvency II Delegated Reg. Art. 188/234.
"""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np

from par_model_v2.projection.multi_driver_capital_5d import _quint_poly_basis
from par_model_v2.projection.multi_driver_proxy_validation import (
    CapitalComparison,
    _r2,
)
from par_model_v2.projection.nested_stochastic_tvog import (
    capital_metrics_from_liabilities,
)
from par_model_v2.projection.multi_driver_proxy_validation_6d import (
    HexBasisDiagnostics,
    HexProxyValidationConfig,
    HexProxyValidationReport,
    SixDriverFXProxyValidator,
)

#: Remediated sizing (Phase 22 Task 1). All other protocol constants are
#: inherited from the governed Phase 21 config.
REMEDIATED_N_FIT = 2000
REMEDIATED_FIT_N_INNER = 8
REMEDIATED_NESTED_N_INNER = 256

#: Targeted extra exponent tuples over the standardised quint state
#: (r, S, s, b, m): rate^2, equity^2, rate*equity.
TARGETED_EXTRA_POWERS: Tuple[Tuple[int, int, int, int, int], ...] = (
    (2, 0, 0, 0, 0), (0, 2, 0, 0, 0), (1, 1, 0, 0, 0),
)


def remediated_config(**overrides) -> HexProxyValidationConfig:
    """The Phase 22 Task 1 remediated configuration (governed defaults
    otherwise — same seeds, same hold-out, same heavy budgets)."""
    kw = dict(
        n_fit=REMEDIATED_N_FIT,
        nested_n_inner=REMEDIATED_NESTED_N_INNER,
    )
    kw.update(overrides)
    return HexProxyValidationConfig(**kw)


def _targeted_design(X5s: np.ndarray) -> np.ndarray:
    """Design matrix: deg-1 quint basis (6 terms) + {r², S², r·S} (9 total)."""
    X5s = np.asarray(X5s, dtype=float)
    if X5s.ndim != 2 or X5s.shape[1] != 5:
        raise ValueError("X5s must have shape (n, 5); got {}".format(X5s.shape))
    base = _quint_poly_basis(X5s, 1, 1)
    extra = np.column_stack([
        X5s[:, 0] ** 2, X5s[:, 1] ** 2, X5s[:, 0] * X5s[:, 1],
    ])
    return np.hstack([base, extra])


def n_targeted_terms() -> int:
    return _targeted_design(np.zeros((1, 5))).shape[1]


@dataclass
class TargetedQuintSurface:
    """Targeted rate/equity-curvature surface, analytic-FX-offset mode."""

    beta: np.ndarray
    centers: np.ndarray
    scales: np.ndarray
    in_sample_r2_noisy: float

    @property
    def n_basis_terms(self) -> int:
        return int(len(self.beta))

    def predict_poly(self, X6: np.ndarray) -> np.ndarray:
        X6 = np.asarray(X6, dtype=float)
        if X6.ndim == 1:
            X6 = X6.reshape(1, -1)
        Xs = (X6[:, :5] - self.centers) / self.scales
        return _targeted_design(Xs) @ self.beta


def fit_targeted_surface(
    fit_X6: np.ndarray, fit_y5: np.ndarray
) -> TargetedQuintSurface:
    """Least-squares fit of the targeted surface on the five-driver target
    (FX handled as the CIP-exact analytic offset; same centring / scaling /
    ``lstsq`` protocol as the governed engines)."""
    fit_X6 = np.asarray(fit_X6, dtype=float)
    if fit_X6.ndim != 2 or fit_X6.shape[1] != 6:
        raise ValueError("fit_X6 must have shape (n, 6)")
    X = fit_X6[:, :5]
    y = np.asarray(fit_y5, dtype=float)
    centers = X.mean(axis=0)
    scales = X.std(axis=0, ddof=0)
    scales = np.where(scales > 0, scales, 1.0)
    Xs = (X - centers) / scales
    design = _targeted_design(Xs)
    beta, _r, _rk, _sv = np.linalg.lstsq(design, y, rcond=None)
    y_hat = design @ beta
    ss_res = float(np.sum((y - y_hat) ** 2))
    ss_tot = float(np.sum((y - y.mean()) ** 2)) or 1.0
    return TargetedQuintSurface(
        beta=beta, centers=centers, scales=scales,
        in_sample_r2_noisy=1.0 - ss_res / ss_tot,
    )


class RemediatedHexProxyValidator(SixDriverFXProxyValidator):
    """Phase 22 Task 1 validator: de-noised fit targets + targeted basis.

    Inherits the ENTIRE governed Phase 21 protocol (outer states, inner
    kernels, slice-stable CRN, basis sweep, leakage, capital comparison,
    FX-axis recovery, verdict) and adds (a) a de-noised fitting kernel and
    (b) a targeted rate/equity-curvature candidate surface that competes in
    the same OOS selection.
    """

    # -- remediation 1: de-noised fitting targets ------------------------- #
    def denoised_fit_payoffs_sliced(
        self, states6_full: np.ndarray, i0: int, i1: int, seed: int,
        n_inner: int = REMEDIATED_FIT_N_INNER,
    ) -> np.ndarray:
        """Mean of ``n_inner`` inner Q-paths of L5 per fit state, rows
        [i0, i1) of the FULL state array.  Seed protocol identical to the
        governed ``single_path_payoffs_sliced`` (``SeedSequence(seed + 1)``),
        so ``n_inner=1`` is bit-identical to Phase 21 and any staging is
        bit-identical to a monolithic run."""
        if n_inner < 1:
            raise ValueError("n_inner must be >= 1")
        child = np.random.SeedSequence(seed + 1).spawn(len(states6_full))[i0:i1]
        y = np.empty(i1 - i0, dtype=float)
        for j in range(i1 - i0):
            inner_seed = int(child[j].generate_state(1)[0])
            y[j] = float(
                self._pvs_5d(states6_full[i0 + j], n_inner, inner_seed).mean()
            )
        return y

    # -- remediation 3: targeted-candidate OOS diagnostics ----------------- #
    def targeted_diagnostics(
        self,
        surf: TargetedQuintSurface,
        val_X: np.ndarray,
        val_truth: np.ndarray,
        insample_X: np.ndarray,
        insample_truth: np.ndarray,
    ) -> HexBasisDiagnostics:
        """OOS / in-sample skill of the targeted surface on the SAME hold-out
        used by the governed sweep (analytic FX offset added exactly)."""
        val_pred = surf.predict_poly(val_X) + self.fx_term(val_X)
        in_pred = surf.predict_poly(insample_X) + self.fx_term(insample_X)
        resid = val_pred - val_truth
        denom = np.where(np.abs(val_truth) > 1e-9, np.abs(val_truth), 1.0)
        in_r2_heavy = _r2(insample_truth, in_pred)
        oos_r2 = _r2(val_truth, val_pred)
        return HexBasisDiagnostics(
            fx_mode="analytic_targeted", degree=2, max_interaction_order=2,
            n_basis_terms=surf.n_basis_terms,
            in_sample_r2_noisy=surf.in_sample_r2_noisy,
            in_sample_r2_heavy=in_r2_heavy,
            oos_rmse=float(np.sqrt(np.mean(resid ** 2))),
            oos_r2=oos_r2,
            oos_mae=float(np.mean(np.abs(resid))),
            oos_max_abs_rel_error=float(np.max(np.abs(resid) / denom)),
            overfit_gap=in_r2_heavy - oos_r2,
        )


def run_remediated_validation(
    validator: RemediatedHexProxyValidator,
    config: Optional[HexProxyValidationConfig] = None,
    precomputed: Optional[Dict[str, np.ndarray]] = None,
    fit_n_inner: int = REMEDIATED_FIT_N_INNER,
    governance_store=None,
    actor: str = "AutomatedModelDev_Phase22",
    phase: str = "Phase 22: Proxy Hardening + Seven-Driver OOS Validation",
) -> Dict[str, object]:
    """Full Phase 22 Task 1 workflow.

    1. Runs the governed Phase 21 engine (`validate`) under the remediated
       config with de-noised fitting targets (supplied via ``precomputed`` or
       computed here) — full (degree, max_int) × fx_mode sweep, leakage,
       capital comparison, FX-axis recovery.
    2. Fits the targeted rate/equity-curvature surface on the SAME data and
       scores it on the SAME hold-out; the FINAL surface is whichever wins by
       the configured OOS selection metric (no gate-shopping).
    3. Applies the stricter Phase 22 gate: OOS R² ≥ 0.95; VaR, ES AND SCR rel
       err ≤ 10%; leakage-free; overfit gap ≤ 0.05; FX-axis slope ≤ 10%.

    Returns a JSON-serialisable report dict embedding the governed engine
    report plus the targeted-candidate evidence and the final verdict.
    """
    cfg = config or remediated_config()
    pre = dict(precomputed or {})
    t0 = time.monotonic()

    if "fit_y5" not in pre:
        fit_X_full = validator.states(cfg.n_fit, cfg.fit_seed)
        pre["fit_y5"] = validator.denoised_fit_payoffs_sliced(
            fit_X_full, 0, cfg.n_fit, cfg.fit_seed, n_inner=fit_n_inner
        )

    base_report: HexProxyValidationReport = validator.validate(
        config=cfg, precomputed=pre,
        governance_store=governance_store, actor=actor, phase=phase,
    )

    # Reconstruct the deterministic state sets + truths (cheap; CRN-stable).
    fit_X = validator.states(cfg.n_fit, cfg.fit_seed)
    val_X = validator.states(cfg.n_validation, cfg.validation_seed)
    eval_X = validator.states(cfg.n_eval, cfg.eval_seed)
    n_in = min(cfg.n_insample_heavy, len(fit_X))
    insample_X = fit_X[:n_in]
    val_truth = np.asarray(pre["val_truth5"], dtype=float) + validator.fx_term(val_X)
    insample_truth = (
        np.asarray(pre["insample_truth5"], dtype=float)
        + validator.fx_term(insample_X)
    )

    targeted = fit_targeted_surface(fit_X, np.asarray(pre["fit_y5"], dtype=float))
    targeted_row = validator.targeted_diagnostics(
        targeted, val_X, val_truth, insample_X, insample_truth
    )

    engine_sel = base_report.selected_row()
    if cfg.selection_metric == "oos_r2":
        targeted_wins = targeted_row.oos_r2 > engine_sel.oos_r2
    else:
        targeted_wins = targeted_row.oos_rmse < engine_sel.oos_rmse
    final_row = targeted_row if targeted_wins else engine_sel

    # Final capital comparison + FX-axis evidence for the FINAL surface.
    nested_l = (
        np.asarray(pre["nested_l5"], dtype=float) + validator.fx_term(eval_X)
    )
    nested_capital = capital_metrics_from_liabilities(
        nested_l, cfg.confidence_level, cfg.capital_horizon_months
    )
    if targeted_wins:
        proxy_l = targeted.predict_poly(eval_X) + validator.fx_term(eval_X)
        proxy_capital = capital_metrics_from_liabilities(
            proxy_l, cfg.confidence_level, cfg.capital_horizon_months
        )

        def _rel(a: float, b: float) -> float:
            return abs(a - b) / (abs(b) if abs(b) > 1e-9 else 1.0)

        capital_cmp = CapitalComparison(
            proxy_capital=proxy_capital, nested_capital=nested_capital,
            var_rel_error=_rel(proxy_capital.var_liability, nested_capital.var_liability),
            es_rel_error=_rel(proxy_capital.es_liability, nested_capital.es_liability),
            scr_rel_error=_rel(proxy_capital.scr_proxy, nested_capital.scr_proxy),
            nested_n_outer=cfg.n_eval, nested_n_inner=cfg.nested_n_inner,
        )
        # Analytic-offset mode: the surface's FX response IS the CIP-exact
        # leg, so the partial-FX slope is exact by construction; verify
        # numerically anyway (mirrors the governed engine's projection).
        x0 = float(validator.agg.fx_exposure.initial_spot_rate)
        notional = float(validator.agg.fx_exposure.exposure_notional)
        theoretical = -notional / x0
        base_X = val_X.copy()
        base_X[:, 5] = x0
        partial_fx = (
            (targeted.predict_poly(val_X) + validator.fx_term(val_X))
            - (targeted.predict_poly(base_X) + validator.fx_term(base_X))
        )
        slope_fit = float(np.polyfit(val_X[:, 5] - x0, partial_fx, 1)[0])
        fx_axis_evidence = {
            "theoretical_fx_slope": theoretical,
            "recovered_fx_slope": slope_fit,
            "slope_rel_error": abs(slope_fit - theoretical) / max(abs(theoretical), 1e-9),
        }
    else:
        capital_cmp = base_report.capital_comparison
        fx_axis_evidence = {
            k: float(v) for k, v in base_report.fx_axis_evidence.items()
        }

    # --- Phase 22 gate (stricter: ES + SCR join the VaR criterion) -------- #
    reasons: List[str] = []
    if final_row.oos_r2 < 0.95:
        reasons.append("OOS R^2 {:.4f} < 0.95".format(final_row.oos_r2))
    if capital_cmp.var_rel_error > 0.10:
        reasons.append("VaR rel error {:.2%} > 10%".format(capital_cmp.var_rel_error))
    if capital_cmp.es_rel_error > 0.10:
        reasons.append("ES rel error {:.2%} > 10%".format(capital_cmp.es_rel_error))
    if capital_cmp.scr_rel_error > 0.10:
        reasons.append("SCR rel error {:.2%} > 10%".format(capital_cmp.scr_rel_error))
    if not base_report.leakage.leakage_free:
        reasons.append("hold-out not leakage-free")
    if final_row.overfit_gap > 0.05:
        reasons.append("overfit gap {:.4f} > 0.05".format(final_row.overfit_gap))
    if fx_axis_evidence["slope_rel_error"] > 0.10:
        reasons.append("FX-axis slope rel error {:.2%} > 10%".format(
            fx_axis_evidence["slope_rel_error"]))
    if reasons:
        verdict = "PARTIAL — " + "; ".join(reasons)
    else:
        verdict = (
            "PASS — remediated six-driver surface ({}, {} terms) validated OOS "
            "(R^2={:.4f}, VaR/ES/SCR rel err {:.2%}/{:.2%}/{:.2%}, leakage-free, "
            "overfit gap={:.4f}, FX axis within {:.2%})".format(
                final_row.fx_mode, final_row.n_basis_terms, final_row.oos_r2,
                capital_cmp.var_rel_error, capital_cmp.es_rel_error,
                capital_cmp.scr_rel_error, final_row.overfit_gap,
                fx_axis_evidence["slope_rel_error"])
        )

    digest = hashlib.sha256(
        np.round(np.concatenate([
            val_truth, targeted.beta,
            np.array([
                1.0 if targeted_wins else 0.0,
                final_row.oos_r2, capital_cmp.var_rel_error,
                capital_cmp.es_rel_error, capital_cmp.scr_rel_error,
            ], dtype=float),
        ]), 9).tobytes()
    ).hexdigest()

    return {
        "run_id": "p22t1-remed-" + uuid.uuid4().hex[:8],
        "verdict": verdict,
        "remediation_applied": {
            "fit_n_inner": int(fit_n_inner),
            "n_fit": int(cfg.n_fit),
            "nested_n_inner": int(cfg.nested_n_inner),
            "targeted_basis": "deg-1 all drivers + {r^2, S^2, r*S} (9 terms, analytic FX offset)",
            "baseline_phase21": {
                "fit_n_inner": 1, "n_fit": 500, "nested_n_inner": 96,
                "oos_r2": 0.949837, "verdict": "PARTIAL",
            },
        },
        "final_selected": final_row.to_dict(),
        "targeted_candidate": targeted_row.to_dict(),
        "engine_selected": engine_sel.to_dict(),
        "targeted_wins": bool(targeted_wins),
        "capital_comparison": capital_cmp.to_dict(),
        "fx_axis_evidence": {
            k: round(float(v), 6) for k, v in fx_axis_evidence.items()
        },
        "governed_engine_report": base_report.to_dict(),
        "reproducibility_digest": digest,
        "duration_seconds": round(time.monotonic() - t0, 4),
        "standards": [
            "SOA ASOP 7 §3.3", "SOA ASOP 25 §3.3",
            "SOA ASOP 56 §3.1.3/§3.5", "IA TAS M §3.2/§3.6",
            "IFoA proxy-modelling working party",
            "Longstaff & Schwartz (2001)",
            "Solvency II Delegated Reg. Art. 188/234",
        ],
    }


def remediation_use_restrictions() -> Dict[str, object]:
    """IA TAS M §3.5 use-restriction disclosure for the remediated validation."""
    from par_model_v2.projection.multi_driver_proxy_validation_6d import (
        hex_proxy_validation_use_restrictions,
    )
    base = hex_proxy_validation_use_restrictions()
    base.update({
        "module": (
            "par_model_v2/projection/multi_driver_proxy_validation_6d_remediation.py"
            "::RemediatedHexProxyValidator"
        ),
        "remediation_scope": (
            "Hardening of the Phase 21 Task 2 PARTIAL: de-noised fitting targets "
            "(8 inner Q-paths/state), 4x training states (2,000), de-noised eval "
            "benchmark (256 inner), and a targeted rate/equity-curvature candidate "
            "basis competing in the same OOS selection. Same disjoint-seed "
            "hold-out; same no-gate-shopping selection discipline."
        ),
    })
    return base


__all__ = [
    "REMEDIATED_N_FIT",
    "REMEDIATED_FIT_N_INNER",
    "REMEDIATED_NESTED_N_INNER",
    "TARGETED_EXTRA_POWERS",
    "TargetedQuintSurface",
    "RemediatedHexProxyValidator",
    "fit_targeted_surface",
    "n_targeted_terms",
    "remediated_config",
    "run_remediated_validation",
    "remediation_use_restrictions",
]
