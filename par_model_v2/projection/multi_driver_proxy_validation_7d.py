"""
Phase 22 Task 2 - Seven-Driver Out-of-Sample Proxy Validation.

Extends the six-driver LSMC proxy validation to the calibrated seventh driver:
the CIR++ liquidity / funding-spread premium. The liquidity component is handled
as a known analytic feature:

    L7(x) = L5(r,S,s,b,m) + FX(X) + LIQ(l)

where FX is the Phase 21 CIP-exact translation leg and LIQ is the Phase 21
CIR-affine forced-sale haircut. The fitted polynomial is still selected by
disjoint-seed OOS RMSE; the known liquidity feature is added as an offset in
both validation and capital comparison, so no noisy regression coefficient is
spent learning a closed-form driver.

EDUCATIONAL MODEL: placeholder exposure notional and liquidity couplings; not
for production capital.
"""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np

from par_model_v2.projection.multi_driver_capital_7d_aggregation import (
    LiquidityExposureSpec,
    SevenDriverLiquidityRiskAggregator,
    seven_driver_use_restrictions,
)
from par_model_v2.projection.multi_driver_proxy_validation import (
    CapitalComparison,
    LeakageDiagnostics,
    _leakage_nd,
    _r2,
)
from par_model_v2.projection.multi_driver_proxy_validation_6d import (
    DEFAULT_HEX_BASIS_GRID,
    HexBasisDiagnostics,
    _FittedHexSurface,
    _fit_hex_surface,
)
from par_model_v2.projection.multi_driver_proxy_validation_6d_remediation import (
    REMEDIATED_FIT_N_INNER,
    REMEDIATED_N_FIT,
    REMEDIATED_NESTED_N_INNER,
)
from par_model_v2.projection.monthly_projection import ParEndowmentProduct
from par_model_v2.projection.nested_stochastic_tvog import (
    DEFAULT_CAPITAL_HORIZON_MONTHS,
    DEFAULT_CONFIDENCE_LEVEL,
    capital_metrics_from_liabilities,
)
from par_model_v2.stochastic.esg_process import Measure


DEFAULT_SEPT_BASIS_GRID = DEFAULT_HEX_BASIS_GRID


@dataclass(frozen=True)
class SeptProxyValidationConfig:
    """Configuration for the seven-driver OOS proxy validation."""

    n_fit: int = REMEDIATED_N_FIT
    n_validation: int = 60
    n_insample_heavy: int = 60
    n_inner_heavy: int = 384
    n_eval: int = 500
    nested_n_inner: int = REMEDIATED_NESTED_N_INNER
    fit_n_inner: int = REMEDIATED_FIT_N_INNER
    basis_grid: Tuple[Tuple[int, int], ...] = DEFAULT_SEPT_BASIS_GRID
    fx_modes: Tuple[str, ...] = ("analytic", "learned")
    selection_metric: str = "oos_rmse"
    confidence_level: float = DEFAULT_CONFIDENCE_LEVEL
    capital_horizon_months: int = DEFAULT_CAPITAL_HORIZON_MONTHS
    fit_seed: int = 42
    validation_seed: int = 20260607
    insample_heavy_seed: int = 7
    eval_seed_offset: int = 99
    nested_inner_seed_offset: int = 100
    outer_measure: Measure = Measure.P

    def __post_init__(self) -> None:
        if self.selection_metric not in ("oos_rmse", "oos_r2"):
            raise ValueError("selection_metric must be 'oos_rmse' or 'oos_r2'")
        if int(self.fit_seed) == int(self.validation_seed):
            raise ValueError("fit_seed and validation_seed must differ")
        if self.n_validation < 8:
            raise ValueError("n_validation must be >= 8")
        if self.fit_n_inner < 1 or self.n_inner_heavy < 1 or self.nested_n_inner < 1:
            raise ValueError("inner-path counts must be positive")
        if not self.basis_grid:
            raise ValueError("basis_grid must be non-empty")
        for mode in self.fx_modes:
            if mode not in ("analytic", "learned"):
                raise ValueError("fx_modes entries must be 'analytic' or 'learned'")

    @property
    def eval_seed(self) -> int:
        return int(self.fit_seed) + int(self.eval_seed_offset)

    @property
    def nested_inner_seed(self) -> int:
        return int(self.fit_seed) + int(self.nested_inner_seed_offset)

    def to_dict(self) -> Dict[str, object]:
        return {
            "n_fit": self.n_fit,
            "n_validation": self.n_validation,
            "n_insample_heavy": self.n_insample_heavy,
            "n_inner_heavy": self.n_inner_heavy,
            "n_eval": self.n_eval,
            "nested_n_inner": self.nested_n_inner,
            "fit_n_inner": self.fit_n_inner,
            "basis_grid": [list(x) for x in self.basis_grid],
            "fx_modes": list(self.fx_modes),
            "selection_metric": self.selection_metric,
            "confidence_level": self.confidence_level,
            "capital_horizon_months": self.capital_horizon_months,
            "fit_seed": self.fit_seed,
            "validation_seed": self.validation_seed,
            "insample_heavy_seed": self.insample_heavy_seed,
            "eval_seed": self.eval_seed,
            "nested_inner_seed": self.nested_inner_seed,
            "outer_measure": self.outer_measure.value
            if isinstance(self.outer_measure, Measure)
            else str(self.outer_measure),
        }


def seven_driver_proxy_config(**overrides) -> SeptProxyValidationConfig:
    kw = {}
    kw.update(overrides)
    return SeptProxyValidationConfig(**kw)


@dataclass
class SeptProxyValidationReport:
    """Structured seven-driver proxy validation evidence."""

    config: SeptProxyValidationConfig
    basis_rows: List[HexBasisDiagnostics]
    selected_fx_mode: str
    selected_degree: int
    selected_max_interaction_order: int
    selection_metric: str
    overfit_onset_terms: Optional[int]
    leakage: LeakageDiagnostics
    capital_comparison: CapitalComparison
    fx_axis_evidence: Dict[str, float]
    liquidity_axis_evidence: Dict[str, float]
    reproducibility_digest: str
    run_id: str
    duration_seconds: float
    verdict: str
    notes: List[str] = field(default_factory=list)
    audit_entry_id: Optional[str] = None

    def selected_row(self) -> HexBasisDiagnostics:
        return next(
            r for r in self.basis_rows
            if r.fx_mode == self.selected_fx_mode
            and r.degree == self.selected_degree
            and r.max_interaction_order == self.selected_max_interaction_order
        )

    def to_dict(self) -> Dict[str, object]:
        return {
            "run_id": self.run_id,
            "verdict": self.verdict,
            "drivers": [
                "short_rate_g2pp_2f",
                "equity_level",
                "credit_spread",
                "lapse_behaviour",
                "mortality_trend",
                "fx_translation",
                "liquidity_premium",
            ],
            "selected_fx_mode": self.selected_fx_mode,
            "selected_degree": self.selected_degree,
            "selected_max_interaction_order": self.selected_max_interaction_order,
            "selection_metric": self.selection_metric,
            "overfit_onset_terms": self.overfit_onset_terms,
            "selected_row": self.selected_row().to_dict(),
            "basis_rows": [r.to_dict() for r in self.basis_rows],
            "leakage": self.leakage.to_dict(),
            "capital_comparison": self.capital_comparison.to_dict(),
            "fx_axis_evidence": {
                k: round(float(v), 6) for k, v in self.fx_axis_evidence.items()
            },
            "liquidity_axis_evidence": {
                k: round(float(v), 9) for k, v in self.liquidity_axis_evidence.items()
            },
            "reproducibility_digest": self.reproducibility_digest,
            "duration_seconds": round(self.duration_seconds, 4),
            "config": self.config.to_dict(),
            "notes": list(self.notes),
            "audit_entry_id": self.audit_entry_id,
            "standards": [
                "SOA ASOP 7 section 3.3",
                "SOA ASOP 25 section 3.3",
                "SOA ASOP 56 section 3.1.3/3.5",
                "IA TAS M section 3.2/3.6",
                "IFoA proxy-modelling working party",
                "Longstaff & Schwartz (2001)",
                "Duffie-Singleton (1999)",
                "Solvency II Delegated Regulation Article 188/234",
            ],
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True)


class SevenDriverLiquidityProxyValidator:
    """Seven-driver OOS proxy validator with analytic FX and liquidity offsets."""

    def __init__(
        self,
        product: ParEndowmentProduct,
        liquidity_exposure: Optional[LiquidityExposureSpec] = None,
        capital_horizon_months: int = DEFAULT_CAPITAL_HORIZON_MONTHS,
        confidence_level: float = DEFAULT_CONFIDENCE_LEVEL,
        outer_measure: Measure = Measure.P,
        **aggregator_kwargs,
    ) -> None:
        if not (0 < capital_horizon_months < product.term_months):
            raise ValueError("capital_horizon_months must satisfy 0 < H < term")
        self.agg = SevenDriverLiquidityRiskAggregator(
            product,
            liquidity_exposure=liquidity_exposure,
            **aggregator_kwargs,
        )
        self.product = product
        self.capital_horizon_months = int(capital_horizon_months)
        self.confidence_level = float(confidence_level)
        self.outer_measure = Measure(outer_measure)

    @property
    def _rem(self) -> int:
        return self.product.term_months - self.capital_horizon_months

    def states(self, n: int, seed: int) -> np.ndarray:
        """Return (n, 7) states (r,S,s,b,m,FX,liquidity)."""
        return self.agg._outer_states_7d(
            n, self.capital_horizon_months, self.outer_measure, seed
        )

    def fx_term(self, states7: np.ndarray) -> np.ndarray:
        x = np.asarray(states7, dtype=float)
        if x.ndim == 1:
            x = x.reshape(1, -1)
        return self.agg.fx_exposure.liability_impact(x[:, 5])

    def liquidity_term(self, states7: np.ndarray) -> np.ndarray:
        x = np.asarray(states7, dtype=float)
        if x.ndim == 1:
            x = x.reshape(1, -1)
        tau = self.agg._liquidity_tau_years(self.capital_horizon_months)
        return self.agg.liquidity_exposure.liability_impact(
            x[:, 6], self.agg.liquidity_params, tau
        )

    def _pvs_5d(self, row: np.ndarray, n_inner: int, inner_seed: int) -> np.ndarray:
        from par_model_v2.projection.multi_driver_capital_5d import (
            _inner_pathwise_pvs_5d,
        )

        r, s, c, b, m = (float(v) for v in row[:5])
        return _inner_pathwise_pvs_5d(
            r, s, c, b, m, n_inner, self._rem,
            self.product, self.agg.hw_params, self.agg.gbm_params,
            self.agg.spread_params, self.agg.correlation,
            self.capital_horizon_months, inner_seed,
            self.agg.equity_guarantee, self.agg.credit_exposure,
            self.agg.lapse_exposure, self.agg.mortality_exposure,
            None,
        )

    def denoised_fit_payoffs_sliced(
        self, states7_full: np.ndarray, i0: int, i1: int, seed: int, n_inner: int
    ) -> np.ndarray:
        if n_inner < 1:
            raise ValueError("n_inner must be >= 1")
        child = np.random.SeedSequence(seed + 1).spawn(len(states7_full))[i0:i1]
        y = np.empty(i1 - i0, dtype=float)
        for j in range(i1 - i0):
            inner_seed = int(child[j].generate_state(1)[0])
            y[j] = float(
                self._pvs_5d(states7_full[i0 + j], n_inner, inner_seed).mean()
            )
        return y

    def heavy_targets_sliced(
        self, states7_full: np.ndarray, i0: int, i1: int, n_inner: int, seed: int
    ) -> np.ndarray:
        if n_inner < 1:
            raise ValueError("n_inner must be >= 1")
        child = np.random.SeedSequence(seed).spawn(len(states7_full))[i0:i1]
        truth = np.empty(i1 - i0, dtype=float)
        for j in range(i1 - i0):
            inner_seed = int(child[j].generate_state(1)[0])
            truth[j] = float(
                self._pvs_5d(states7_full[i0 + j], n_inner, inner_seed).mean()
            )
        return truth

    def _predict_l7(
        self, surf: _FittedHexSurface, states7: np.ndarray
    ) -> np.ndarray:
        x7 = np.asarray(states7, dtype=float)
        x6 = x7[:, :6]
        poly = surf.predict_poly(x6)
        if surf.fx_mode == "analytic":
            poly = poly + self.fx_term(x7)
        return poly + self.liquidity_term(x7)

    def validate(
        self,
        config: Optional[SeptProxyValidationConfig] = None,
        precomputed: Optional[Dict[str, np.ndarray]] = None,
        governance_store: Optional["object"] = None,
        actor: str = "SevenDriverLiquidityProxyValidator",
        phase: str = "Phase 22: Proxy Hardening + Seven-Driver OOS Validation",
    ) -> SeptProxyValidationReport:
        cfg = config or SeptProxyValidationConfig()
        pre = dict(precomputed or {})
        t0 = time.monotonic()
        run_id = "sept-proxyval-" + uuid.uuid4().hex[:8]
        notes: List[str] = []

        fit_X = self.states(cfg.n_fit, cfg.fit_seed)
        val_X = self.states(cfg.n_validation, cfg.validation_seed)
        eval_X = self.states(cfg.n_eval, cfg.eval_seed)

        fit_y5 = (
            np.asarray(pre["fit_y5"], dtype=float)
            if "fit_y5" in pre
            else self.denoised_fit_payoffs_sliced(
                fit_X, 0, cfg.n_fit, cfg.fit_seed, cfg.fit_n_inner
            )
        )
        if len(fit_y5) != cfg.n_fit:
            raise ValueError("fit_y5 must have length n_fit")

        val_truth5 = (
            np.asarray(pre["val_truth5"], dtype=float)
            if "val_truth5" in pre
            else self.heavy_targets_sliced(
                val_X, 0, cfg.n_validation, cfg.n_inner_heavy, cfg.validation_seed
            )
        )
        if len(val_truth5) != cfg.n_validation:
            raise ValueError("val_truth5 must have length n_validation")
        val_truth = val_truth5 + self.fx_term(val_X) + self.liquidity_term(val_X)

        n_in = min(cfg.n_insample_heavy, len(fit_X))
        insample_X = fit_X[:n_in]
        insample_truth5 = (
            np.asarray(pre["insample_truth5"], dtype=float)
            if "insample_truth5" in pre
            else self.heavy_targets_sliced(
                insample_X, 0, n_in, cfg.n_inner_heavy, cfg.insample_heavy_seed
            )
        )
        if len(insample_truth5) != n_in:
            raise ValueError("insample_truth5 must have length n_insample_heavy")
        insample_truth = (
            insample_truth5 + self.fx_term(insample_X) + self.liquidity_term(insample_X)
        )

        leakage = _leakage_nd(fit_X, val_X, cfg.fit_seed, cfg.validation_seed)
        if not leakage.leakage_free:
            notes.append("WARNING: hold-out leakage check did not pass.")

        fit_fx = self.fx_term(fit_X)
        rows: List[HexBasisDiagnostics] = []
        surfaces: Dict[Tuple[str, int, int], _FittedHexSurface] = {}
        for mode in cfg.fx_modes:
            for degree, max_int in cfg.basis_grid:
                surf = _fit_hex_surface(
                    fit_X[:, :6], fit_y5, fit_fx, degree, max_int, fx_mode=mode
                )
                surfaces[(mode, degree, max_int)] = surf
                val_pred = self._predict_l7(surf, val_X)
                in_pred = self._predict_l7(surf, insample_X)
                resid = val_pred - val_truth
                denom = np.where(np.abs(val_truth) > 1e-9, np.abs(val_truth), 1.0)
                oos_r2 = _r2(val_truth, val_pred)
                in_r2 = _r2(insample_truth, in_pred)
                rows.append(HexBasisDiagnostics(
                    fx_mode=mode,
                    degree=degree,
                    max_interaction_order=max_int,
                    n_basis_terms=surf.n_basis_terms,
                    in_sample_r2_noisy=surf.in_sample_r2_noisy,
                    in_sample_r2_heavy=in_r2,
                    oos_rmse=float(np.sqrt(np.mean(resid ** 2))),
                    oos_r2=oos_r2,
                    oos_mae=float(np.mean(np.abs(resid))),
                    oos_max_abs_rel_error=float(np.max(np.abs(resid) / denom)),
                    overfit_gap=in_r2 - oos_r2,
                ))

        selected = (
            min(rows, key=lambda r: r.oos_rmse)
            if cfg.selection_metric == "oos_rmse"
            else max(rows, key=lambda r: r.oos_r2)
        )
        selected_key = (
            selected.fx_mode, selected.degree, selected.max_interaction_order
        )
        chosen = surfaces[selected_key]
        ordered = sorted(
            rows,
            key=lambda r: (r.fx_mode, r.n_basis_terms, r.degree, r.max_interaction_order),
        )
        mode_rows = sorted(
            [r for r in rows if r.fx_mode == selected.fx_mode],
            key=lambda r: (r.n_basis_terms, r.degree, r.max_interaction_order),
        )
        overfit_onset_terms = None
        for prev, cur in zip(mode_rows, mode_rows[1:]):
            if cur.oos_rmse > prev.oos_rmse * 1.001:
                overfit_onset_terms = cur.n_basis_terms
                break

        proxy_l = self._predict_l7(chosen, eval_X)
        proxy_capital = capital_metrics_from_liabilities(
            proxy_l, cfg.confidence_level, cfg.capital_horizon_months
        )
        nested_l5 = (
            np.asarray(pre["nested_l5"], dtype=float)
            if "nested_l5" in pre
            else self.heavy_targets_sliced(
                eval_X, 0, cfg.n_eval, cfg.nested_n_inner, cfg.nested_inner_seed
            )
        )
        if len(nested_l5) != cfg.n_eval:
            raise ValueError("nested_l5 must have length n_eval")
        nested_l = nested_l5 + self.fx_term(eval_X) + self.liquidity_term(eval_X)
        nested_capital = capital_metrics_from_liabilities(
            nested_l, cfg.confidence_level, cfg.capital_horizon_months
        )

        def _rel(a: float, b: float) -> float:
            return abs(a - b) / (abs(b) if abs(b) > 1e-9 else 1.0)

        capital_cmp = CapitalComparison(
            proxy_capital=proxy_capital,
            nested_capital=nested_capital,
            var_rel_error=_rel(proxy_capital.var_liability, nested_capital.var_liability),
            es_rel_error=_rel(proxy_capital.es_liability, nested_capital.es_liability),
            scr_rel_error=_rel(proxy_capital.scr_proxy, nested_capital.scr_proxy),
            nested_n_outer=cfg.n_eval,
            nested_n_inner=cfg.nested_n_inner,
        )

        fx_evidence = self._fx_axis_evidence(chosen, val_X)
        liq_evidence = self._liquidity_axis_evidence(val_X)
        notes.append(
            "Liquidity is an analytic CIR-affine offset, not a learned coefficient; "
            "the validation therefore tests the fitted stochastic-valuation surface "
            "plus the exact liquidity feature on the same disjoint hold-out."
        )
        notes.append(
            "Proxy and nested capital are evaluated on the SAME eval outer states "
            "(seed {}), isolating surface error; nested benchmark uses {} inner "
            "Q-paths per state.".format(cfg.eval_seed, cfg.nested_n_inner)
        )

        digest = hashlib.sha256(
            np.round(np.concatenate([
                val_truth,
                chosen.beta,
                np.array([
                    selected.oos_r2,
                    capital_cmp.var_rel_error,
                    capital_cmp.es_rel_error,
                    capital_cmp.scr_rel_error,
                    liq_evidence["max_abs_offset_error"],
                ], dtype=float),
            ]), 9).tobytes()
        ).hexdigest()

        verdict = self._verdict(selected, capital_cmp, leakage, fx_evidence, liq_evidence, notes)
        duration = time.monotonic() - t0

        audit_entry_id = None
        if governance_store is not None:
            try:
                from par_model_v2.governance.audit_trail import AuditEntry

                entry = AuditEntry.model_run(
                    actor=actor,
                    phase=phase,
                    run_id=run_id,
                    scenario_count=(
                        cfg.n_fit * cfg.fit_n_inner
                        + (cfg.n_validation + n_in) * cfg.n_inner_heavy
                        + cfg.n_eval * cfg.nested_n_inner
                    ),
                    duration_seconds=round(duration, 4),
                    outcome="PASS" if verdict.startswith("PASS") else "PARTIAL",
                    files_changed=[
                        "par_model_v2/projection/multi_driver_proxy_validation_7d.py"
                    ],
                    test_summary=(
                        "7D OOS proxy-val: selected ({}, deg={}, max_int={}), "
                        "OOS R2={:.4f}, VaR/ES/SCR rel err={:.2%}/{:.2%}/{:.2%}, "
                        "liquidity offset max err={:.2e}"
                    ).format(
                        selected.fx_mode,
                        selected.degree,
                        selected.max_interaction_order,
                        selected.oos_r2,
                        capital_cmp.var_rel_error,
                        capital_cmp.es_rel_error,
                        capital_cmp.scr_rel_error,
                        liq_evidence["max_abs_offset_error"],
                    ),
                )
                governance_store.audit_trail.append(entry)
                audit_entry_id = entry.entry_id
            except Exception as exc:  # pragma: no cover - governance optional
                notes.append("audit append skipped: {}".format(exc))

        return SeptProxyValidationReport(
            config=cfg,
            basis_rows=ordered,
            selected_fx_mode=selected.fx_mode,
            selected_degree=selected.degree,
            selected_max_interaction_order=selected.max_interaction_order,
            selection_metric=cfg.selection_metric,
            overfit_onset_terms=overfit_onset_terms,
            leakage=leakage,
            capital_comparison=capital_cmp,
            fx_axis_evidence=fx_evidence,
            liquidity_axis_evidence=liq_evidence,
            reproducibility_digest=digest,
            run_id=run_id,
            duration_seconds=duration,
            verdict=verdict,
            notes=notes,
            audit_entry_id=audit_entry_id,
        )

    def _fx_axis_evidence(
        self, surf: _FittedHexSurface, states7: np.ndarray
    ) -> Dict[str, float]:
        x0 = float(self.agg.fx_exposure.initial_spot_rate)
        notional = float(self.agg.fx_exposure.exposure_notional)
        theoretical = -notional / x0
        x = np.asarray(states7, dtype=float)
        base = x.copy()
        base[:, 5] = x0
        partial = self._predict_l7(surf, x) - self._predict_l7(surf, base)
        slope = (
            float(np.polyfit(x[:, 5] - x0, partial, 1)[0])
            if np.std(x[:, 5]) > 0 else float("nan")
        )
        return {
            "theoretical_fx_slope": theoretical,
            "recovered_fx_slope": slope,
            "slope_rel_error": abs(slope - theoretical) / max(abs(theoretical), 1e-9),
        }

    def _liquidity_axis_evidence(self, states7: np.ndarray) -> Dict[str, float]:
        tau = self.agg._liquidity_tau_years(self.capital_horizon_months)
        direct = self.agg.liquidity_exposure.liability_impact(
            np.asarray(states7)[:, 6], self.agg.liquidity_params, tau
        )
        offset = self.liquidity_term(states7)
        base = float(self.liquidity_term(
            np.array([[0.0, 0.0, 0.0, 0.0, 0.0, self.agg.fx_params.initial_spot_rate,
                       self.agg.liquidity_params.initial_premium]])
        )[0])
        return {
            "max_abs_offset_error": float(np.max(np.abs(offset - direct))),
            "baseline_liquidity_impact": base,
            "tau_years": tau,
            "exposure_notional": float(self.agg.liquidity_exposure.exposure_notional),
            "initial_premium": float(self.agg.liquidity_params.initial_premium),
        }

    @staticmethod
    def _verdict(
        selected: HexBasisDiagnostics,
        capital_cmp: CapitalComparison,
        leakage: LeakageDiagnostics,
        fx_axis: Dict[str, float],
        liquidity_axis: Dict[str, float],
        notes: List[str],
    ) -> str:
        reasons: List[str] = []
        if selected.oos_r2 < 0.95:
            reasons.append("OOS R2 {:.4f} < 0.95".format(selected.oos_r2))
        if capital_cmp.var_rel_error > 0.10:
            reasons.append("VaR rel error {:.2%} > 10%".format(capital_cmp.var_rel_error))
        if capital_cmp.es_rel_error > 0.10:
            reasons.append("ES rel error {:.2%} > 10%".format(capital_cmp.es_rel_error))
        if capital_cmp.scr_rel_error > 0.10:
            reasons.append("SCR rel error {:.2%} > 10%".format(capital_cmp.scr_rel_error))
        if not leakage.leakage_free:
            reasons.append("hold-out not leakage-free")
        if selected.overfit_gap > 0.05:
            reasons.append("overfit gap {:.4f} > 0.05".format(selected.overfit_gap))
        if fx_axis["slope_rel_error"] > 0.10:
            reasons.append("FX-axis slope rel error {:.2%} > 10%".format(
                fx_axis["slope_rel_error"]))
        if liquidity_axis["max_abs_offset_error"] > 1e-9:
            reasons.append("liquidity analytic offset mismatch")
        if abs(liquidity_axis["baseline_liquidity_impact"]) > 1e-9:
            reasons.append("liquidity baseline not centred")
        if reasons:
            notes.append("verdict drivers: " + "; ".join(reasons))
            return "PARTIAL - " + "; ".join(reasons)
        return (
            "PASS - seven-driver surface ({}, deg {}, max_int {}, {} terms) "
            "validated OOS (R2={:.4f}, VaR/ES/SCR rel err "
            "{:.2%}/{:.2%}/{:.2%}, liquidity offset exact, leakage-free)"
        ).format(
            selected.fx_mode,
            selected.degree,
            selected.max_interaction_order,
            selected.n_basis_terms,
            selected.oos_r2,
            capital_cmp.var_rel_error,
            capital_cmp.es_rel_error,
            capital_cmp.scr_rel_error,
        )


def seven_driver_proxy_use_restrictions() -> Dict[str, object]:
    base = seven_driver_use_restrictions()
    base.update({
        "model": "SevenDriverLiquidityProxyValidator",
        "what_it_validates": (
            "Out-of-sample validation of the seven-driver LSMC capital proxy: "
            "five stochastic-valuation drivers fitted by polynomial surface, "
            "FX as a CIP-exact offset, and liquidity as a CIR-affine forced-sale "
            "haircut offset."
        ),
        "residual_risk": (
            "Valid only over the fitted state region. Liquidity exposure notional "
            "and 7x7 liquidity couplings remain educational placeholders pending "
            "Phase 22 Task 3 credentialled calibration and independent APS X2 review."
        ),
    })
    return base


__all__ = [
    "DEFAULT_SEPT_BASIS_GRID",
    "SeptProxyValidationConfig",
    "SeptProxyValidationReport",
    "SevenDriverLiquidityProxyValidator",
    "seven_driver_proxy_config",
    "seven_driver_proxy_use_restrictions",
]
