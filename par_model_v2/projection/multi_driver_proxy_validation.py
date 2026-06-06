"""
Out-of-Sample Proxy-Model Validation for the Multi-Driver LSMC Capital Surface
==============================================================================

Phase 15 Task 2.  Provides a *formal out-of-sample (OOS) validation* of the
bivariate (short-rate + equity) Longstaff-Schwartz capital proxy built in
Phase 15 Task 1 (:mod:`par_model_v2.projection.multi_driver_capital`).

Why a dedicated OOS validation
------------------------------
The Task 1 proxy is fitted by least-squares on ``N_fit`` *single-inner-path*
liability samples.  Its in-sample ``fit_r2`` is computed against those **noisy**
single-path payoffs, so it is intrinsically low (the regression deliberately
averages out single-path Monte-Carlo noise) and is therefore **not** a measure
of how well the surface reproduces the *true* conditional expectation
``L(r,S) = E^Q[ residual PV | r_H, S_H ]``.

A defensible proxy validation (IFoA proxy-model working-party guidance; SOA
ASOP 56 §3.5; IA TAS M §3.6) instead requires:

1. **A genuine hold-out.**  Fit on one set of outer states; validate on an
   *independent* set generated from a **disjoint seed** so no validation point
   can leak into the fit.
2. **"Heavy" (high-accuracy) validation targets.**  At each validation state
   compute a high-inner-count nested estimate of the *true* conditional
   expectation ``L(r,S)`` and measure proxy error against it — not against the
   irreducible single-path noise.
3. **Basis-complexity selection by OOS skill.**  Sweep the polynomial degree
   and pick the degree that minimises OOS error.  In-sample error always falls
   with degree; OOS error turns up once the surface starts fitting noise — that
   turning point is the overfit onset.
4. **Leakage / overfit diagnostics.**  Confirm fit and validation states are
   disjoint, and report the in-sample-heavy vs OOS skill gap per degree.

Public API
----------
* :class:`ProxyValidationConfig`     — run configuration (sizes, degrees, seeds).
* :class:`DegreeDiagnostics`         — per-degree in/out-of-sample skill row.
* :class:`LeakageDiagnostics`        — fit/validation disjointness evidence.
* :class:`ProxyValidationReport`     — full structured report + ``to_dict``/``to_json``.
* :class:`MultiDriverProxyValidator` — orchestrates fit / hold-out / selection.

Everything here is **additive** — the Task 1 module is imported, never modified,
and the existing single-factor Task 6 module is untouched.

ASOP / IA standards
-------------------
- SOA ASOP 56 §3.5   — scenario adequacy, convergence, proxy-model validation
- SOA ASOP 56 §3.1.3 — stochastic model documentation & output governance
- SOA ASOP 25 §3.3   — correlated-driver scenario adequacy
- IA TAS M §3.6      — model validation, out-of-sample testing, reproducibility
- IA TAS M §3.2      — market-consistent valuation
- IFoA proxy-model working party — fit/validate split, heavy validation points
- Longstaff & Schwartz (2001) — least-squares Monte-Carlo
"""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Sequence, Tuple

import numpy as np

from par_model_v2.projection.monthly_projection import ParEndowmentProduct
from par_model_v2.projection.nested_stochastic_tvog import (
    CapitalMetrics,
    capital_metrics_from_liabilities,
    DEFAULT_CAPITAL_HORIZON_MONTHS,
    DEFAULT_CONFIDENCE_LEVEL,
)
from par_model_v2.projection.multi_driver_capital import (
    EquityGuaranteeSpec,
    MultiDriverNestedEngine,
    _inner_pathwise_pvs_2d,
    _multi_poly_basis,
    _multi_poly_powers,
    _n_basis_terms,
    _outer_states_2d,
)
from par_model_v2.stochastic.esg_process import (
    GBMParams,
    HullWhiteParams,
    Measure,
    RiskFreeCurve,
)

#: Default polynomial degrees swept during OOS model selection.
DEFAULT_DEGREE_GRID: Tuple[int, ...] = (1, 2, 3, 4)

#: Default inner-path count for the *heavy* (high-accuracy) validation targets.
DEFAULT_HEAVY_INNER = 2_048


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ProxyValidationConfig:
    """Configuration for an out-of-sample proxy-validation run.

    Parameters
    ----------
    n_fit:
        Number of correlated outer fitting states (one inner path each), exactly
        as the Task 1 LSMC engine uses.
    n_validation:
        Number of *heavy* out-of-sample validation states (each valued with
        ``n_inner_heavy`` inner paths to approximate the true ``L(r,S)``).
    n_insample_heavy:
        Size of the held-in heavy subset (drawn from the fit seed) used only to
        measure the in-sample-vs-OOS skill gap.  Small to bound cost.
    n_inner_heavy:
        Inner-path count for every heavy nested target.  Larger -> truer target.
    degrees:
        Polynomial total-degrees to sweep for model selection.
    selection_metric:
        ``"oos_rmse"`` (minimise) or ``"oos_r2"`` (maximise).
    confidence_level, capital_horizon_months:
        Capital metric configuration (defaults match the Task 1 engine).
    fit_seed, validation_seed, insample_heavy_seed:
        Disjoint seeds.  ``fit_seed != validation_seed`` is enforced so the
        hold-out cannot leak.
    """

    n_fit: int = 2_000
    n_validation: int = 200
    n_insample_heavy: int = 80
    n_inner_heavy: int = DEFAULT_HEAVY_INNER
    degrees: Tuple[int, ...] = DEFAULT_DEGREE_GRID
    selection_metric: str = "oos_rmse"
    confidence_level: float = DEFAULT_CONFIDENCE_LEVEL
    capital_horizon_months: int = DEFAULT_CAPITAL_HORIZON_MONTHS
    fit_seed: int = 42
    validation_seed: int = 20260605
    insample_heavy_seed: int = 7
    outer_measure: Measure = Measure.P

    def __post_init__(self) -> None:
        if self.selection_metric not in ("oos_rmse", "oos_r2"):
            raise ValueError("selection_metric must be 'oos_rmse' or 'oos_r2'")
        if int(self.fit_seed) == int(self.validation_seed):
            raise ValueError(
                "fit_seed and validation_seed must differ to prevent hold-out leakage"
            )
        if not self.degrees:
            raise ValueError("degrees must be non-empty")
        if min(self.degrees) < 1:
            raise ValueError("all degrees must be >= 1")
        if self.n_validation < 8:
            raise ValueError("n_validation must be >= 8 for a meaningful OOS metric")

    def to_dict(self) -> Dict[str, object]:
        return {
            "n_fit": self.n_fit,
            "n_validation": self.n_validation,
            "n_insample_heavy": self.n_insample_heavy,
            "n_inner_heavy": self.n_inner_heavy,
            "degrees": list(self.degrees),
            "selection_metric": self.selection_metric,
            "confidence_level": self.confidence_level,
            "capital_horizon_months": self.capital_horizon_months,
            "fit_seed": self.fit_seed,
            "validation_seed": self.validation_seed,
            "insample_heavy_seed": self.insample_heavy_seed,
            "outer_measure": self.outer_measure.value
            if isinstance(self.outer_measure, Measure)
            else str(self.outer_measure),
        }


# ---------------------------------------------------------------------------
# Result dataclasses
# ---------------------------------------------------------------------------

@dataclass
class DegreeDiagnostics:
    """In-sample and out-of-sample skill for a single polynomial degree.

    Attributes
    ----------
    in_sample_r2_noisy:
        R^2 of the proxy against the *noisy single-path* fit payoffs (the Task 1
        ``fit_r2``).  Always rises with degree; **not** a validation metric.
    in_sample_r2_heavy:
        R^2 of the proxy against *heavy* nested truth on the held-in subset.
    oos_rmse, oos_r2, oos_mae, oos_max_abs_rel_error:
        Proxy error against heavy nested truth on the **independent** validation
        states.  These are the validation metrics.
    overfit_gap:
        ``in_sample_r2_heavy - oos_r2``.  A large positive gap signals the
        surface is fitting features that do not generalise (overfitting).
    """

    degree: int
    n_basis_terms: int
    in_sample_r2_noisy: float
    in_sample_r2_heavy: float
    oos_rmse: float
    oos_r2: float
    oos_mae: float
    oos_max_abs_rel_error: float
    overfit_gap: float

    def to_dict(self) -> Dict[str, object]:
        return {
            "degree": self.degree,
            "n_basis_terms": self.n_basis_terms,
            "in_sample_r2_noisy": round(self.in_sample_r2_noisy, 6),
            "in_sample_r2_heavy": round(self.in_sample_r2_heavy, 6),
            "oos_rmse": round(self.oos_rmse, 6),
            "oos_r2": round(self.oos_r2, 6),
            "oos_mae": round(self.oos_mae, 6),
            "oos_max_abs_rel_error": round(self.oos_max_abs_rel_error, 6),
            "overfit_gap": round(self.overfit_gap, 6),
        }


@dataclass
class LeakageDiagnostics:
    """Evidence that the fit and validation hold-out sets are disjoint."""

    fit_seed: int
    validation_seed: int
    seeds_disjoint: bool
    n_exact_shared_states: int
    min_pairwise_distance: float
    leakage_free: bool

    def to_dict(self) -> Dict[str, object]:
        return {
            "fit_seed": self.fit_seed,
            "validation_seed": self.validation_seed,
            "seeds_disjoint": self.seeds_disjoint,
            "n_exact_shared_states": self.n_exact_shared_states,
            "min_pairwise_distance": round(self.min_pairwise_distance, 9),
            "leakage_free": self.leakage_free,
        }


@dataclass
class CapitalComparison:
    """Selected-degree proxy capital vs independent multi-driver nested capital."""

    proxy_capital: CapitalMetrics
    nested_capital: CapitalMetrics
    var_rel_error: float
    es_rel_error: float
    scr_rel_error: float
    nested_n_outer: int
    nested_n_inner: int

    def to_dict(self) -> Dict[str, object]:
        return {
            "proxy_capital": self.proxy_capital.summary(),
            "nested_capital": self.nested_capital.summary(),
            "var_rel_error": round(self.var_rel_error, 6),
            "es_rel_error": round(self.es_rel_error, 6),
            "scr_rel_error": round(self.scr_rel_error, 6),
            "nested_n_outer": self.nested_n_outer,
            "nested_n_inner": self.nested_n_inner,
        }


@dataclass
class ProxyValidationReport:
    """Full structured out-of-sample proxy-validation report."""

    config: ProxyValidationConfig
    degree_rows: List[DegreeDiagnostics]
    selected_degree: int
    selection_metric: str
    overfit_onset_degree: Optional[int]
    leakage: LeakageDiagnostics
    capital_comparison: CapitalComparison
    reproducibility_digest: str
    run_id: str
    duration_seconds: float
    verdict: str
    notes: List[str] = field(default_factory=list)
    audit_entry_id: Optional[str] = None

    def selected_row(self) -> DegreeDiagnostics:
        return next(r for r in self.degree_rows if r.degree == self.selected_degree)

    def to_dict(self) -> Dict[str, object]:
        return {
            "run_id": self.run_id,
            "verdict": self.verdict,
            "selected_degree": self.selected_degree,
            "selection_metric": self.selection_metric,
            "overfit_onset_degree": self.overfit_onset_degree,
            "selected_row": self.selected_row().to_dict(),
            "degree_rows": [r.to_dict() for r in self.degree_rows],
            "leakage": self.leakage.to_dict(),
            "capital_comparison": self.capital_comparison.to_dict(),
            "reproducibility_digest": self.reproducibility_digest,
            "duration_seconds": round(self.duration_seconds, 4),
            "config": self.config.to_dict(),
            "notes": list(self.notes),
            "audit_entry_id": self.audit_entry_id,
            "standards": [
                "SOA ASOP 56 §3.5",
                "SOA ASOP 56 §3.1.3",
                "SOA ASOP 25 §3.3",
                "IA TAS M §3.6",
                "IA TAS M §3.2",
                "IFoA proxy-model working party",
                "Longstaff & Schwartz (2001)",
            ],
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True)


# ---------------------------------------------------------------------------
# Surface fitting / prediction (identical maths to the Task 1 engine, refit
# per degree on a SINGLE shared fitting data set so degrees are comparable)
# ---------------------------------------------------------------------------

@dataclass
class _FittedSurface:
    beta: np.ndarray
    centers: np.ndarray
    scales: np.ndarray
    degree: int
    in_sample_r2_noisy: float

    def predict(self, X: np.ndarray) -> np.ndarray:
        X = np.asarray(X, dtype=float)
        if X.ndim == 1:
            X = X.reshape(1, -1)
        Xs = (X - self.centers) / self.scales
        return _multi_poly_basis(Xs, self.degree) @ self.beta


def _fit_surface(fit_X: np.ndarray, fit_y: np.ndarray, degree: int) -> _FittedSurface:
    """Least-squares fit of the bivariate degree-``d`` surface on shared data.

    Mirrors :meth:`MultiDriverLSMCProxyEngine.fit_and_run` exactly (same
    centring/scaling and ``np.linalg.lstsq``) but takes the fitting data as
    arguments so every degree is fitted on the *same* states + payoffs.
    """
    centers = fit_X.mean(axis=0)
    scales = fit_X.std(axis=0, ddof=0)
    scales = np.where(scales > 0, scales, 1.0)
    Xs = (fit_X - centers) / scales
    design = _multi_poly_basis(Xs, degree)
    beta, _resid, _rank, _sv = np.linalg.lstsq(design, fit_y, rcond=None)
    y_hat = design @ beta
    ss_res = float(np.sum((fit_y - y_hat) ** 2))
    ss_tot = float(np.sum((fit_y - fit_y.mean()) ** 2)) or 1.0
    return _FittedSurface(
        beta=beta, centers=centers, scales=scales, degree=int(degree),
        in_sample_r2_noisy=1.0 - ss_res / ss_tot,
    )


def _r2(actual: np.ndarray, predicted: np.ndarray) -> float:
    ss_res = float(np.sum((actual - predicted) ** 2))
    ss_tot = float(np.sum((actual - actual.mean()) ** 2)) or 1.0
    return 1.0 - ss_res / ss_tot


# ---------------------------------------------------------------------------
# Validator
# ---------------------------------------------------------------------------

class MultiDriverProxyValidator:
    """Orchestrate fit / hold-out / degree-selection for the 2-driver proxy.

    The validator owns the product and economic assumptions; a single
    :meth:`validate` call runs the whole hold-out workflow and returns a
    :class:`ProxyValidationReport`.

    SOA ASOP 56 §3.5; IA TAS M §3.6; IFoA proxy-model working party.
    """

    def __init__(
        self,
        product: ParEndowmentProduct,
        hw_params: Optional[HullWhiteParams] = None,
        gbm_params: Optional[GBMParams] = None,
        initial_curve: Optional[RiskFreeCurve] = None,
        equity_guarantee: Optional[EquityGuaranteeSpec] = None,
        capital_horizon_months: int = DEFAULT_CAPITAL_HORIZON_MONTHS,
        confidence_level: float = DEFAULT_CONFIDENCE_LEVEL,
        outer_measure: Measure = Measure.P,
        annual_qx_fn: Optional[Callable] = None,
    ) -> None:
        if not (0 < capital_horizon_months < product.term_months):
            raise ValueError("capital_horizon_months must satisfy 0 < H < term_months")
        self.product = product
        self.hw_params = hw_params if hw_params is not None else HullWhiteParams()
        self.gbm_params = gbm_params if gbm_params is not None else GBMParams()
        self.initial_curve = initial_curve
        self.equity_guarantee = equity_guarantee or EquityGuaranteeSpec()
        self.capital_horizon_months = int(capital_horizon_months)
        self.confidence_level = float(confidence_level)
        self.outer_measure = Measure(outer_measure)
        self.annual_qx_fn = annual_qx_fn

    # -- low-level helpers ---------------------------------------------------

    @property
    def _rem(self) -> int:
        return self.product.term_months - self.capital_horizon_months

    def _states(self, n: int, seed: int) -> np.ndarray:
        return _outer_states_2d(
            n, self.capital_horizon_months, self.outer_measure,
            self.hw_params, self.gbm_params, self.initial_curve, seed,
        )

    def _single_path_payoffs(self, states: np.ndarray, seed: int) -> np.ndarray:
        """One inner path per state -> noisy fit target (matches Task 1 engine)."""
        child = np.random.SeedSequence(seed + 1).spawn(len(states))
        y = np.empty(len(states), dtype=float)
        for i, (r, s) in enumerate(states):
            inner_seed = int(child[i].generate_state(1)[0])
            pvs = _inner_pathwise_pvs_2d(
                float(r), float(s), 1, self._rem, self.product, self.hw_params,
                self.gbm_params, self.capital_horizon_months, inner_seed,
                self.equity_guarantee, self.annual_qx_fn,
            )
            y[i] = float(pvs[0])
        return y

    def _heavy_targets(self, states: np.ndarray, n_inner: int, seed: int) -> np.ndarray:
        """High-accuracy nested E^Q[L | r,S] at each state (the OOS truth)."""
        child = np.random.SeedSequence(seed).spawn(len(states))
        truth = np.empty(len(states), dtype=float)
        for i, (r, s) in enumerate(states):
            inner_seed = int(child[i].generate_state(1)[0])
            pvs = _inner_pathwise_pvs_2d(
                float(r), float(s), n_inner, self._rem, self.product, self.hw_params,
                self.gbm_params, self.capital_horizon_months, inner_seed,
                self.equity_guarantee, self.annual_qx_fn,
            )
            truth[i] = float(pvs.mean())
        return truth

    @staticmethod
    def _leakage(fit_X: np.ndarray, val_X: np.ndarray, fit_seed: int, val_seed: int) -> LeakageDiagnostics:
        # exact shared rows (defensive — disjoint seeds make this ~impossible)
        fit_rows = {tuple(np.round(row, 12)) for row in fit_X}
        n_shared = sum(1 for row in val_X if tuple(np.round(row, 12)) in fit_rows)
        # min distance from each validation point to the nearest fit point
        # (scaled per-dimension so rates & equity contribute comparably)
        scale = fit_X.std(axis=0, ddof=0)
        scale = np.where(scale > 0, scale, 1.0)
        f = fit_X / scale
        v = val_X / scale
        min_d = np.inf
        for vp in v:
            d = np.sqrt(np.min(np.sum((f - vp) ** 2, axis=1)))
            min_d = min(min_d, float(d))
        seeds_disjoint = int(fit_seed) != int(val_seed)
        leakage_free = seeds_disjoint and n_shared == 0
        return LeakageDiagnostics(
            fit_seed=int(fit_seed), validation_seed=int(val_seed),
            seeds_disjoint=seeds_disjoint, n_exact_shared_states=int(n_shared),
            min_pairwise_distance=float(min_d), leakage_free=leakage_free,
        )

    # -- main entry point ----------------------------------------------------

    def validate(
        self,
        config: Optional[ProxyValidationConfig] = None,
        nested_n_outer: int = 1_500,
        nested_n_inner: int = 128,
        governance_store: Optional["object"] = None,
        actor: str = "MultiDriverProxyValidator",
        phase: str = "Phase 15: Multi-Risk Economic Capital and Proxy-Model Validation",
    ) -> ProxyValidationReport:
        cfg = config or ProxyValidationConfig()
        t0 = time.monotonic()
        run_id = "md-proxyval-" + uuid.uuid4().hex[:8]
        notes: List[str] = []

        # --- 1. fitting data (one inner path each), seen ONLY by the fit -----
        fit_X = self._states(cfg.n_fit, cfg.fit_seed)
        fit_y = self._single_path_payoffs(fit_X, cfg.fit_seed)

        # --- 2. independent heavy hold-out (disjoint seed) ------------------
        val_X = self._states(cfg.n_validation, cfg.validation_seed)
        val_truth = self._heavy_targets(val_X, cfg.n_inner_heavy, cfg.validation_seed)

        # --- 3. held-in heavy subset (for the in/out skill gap) -------------
        n_in_heavy = min(cfg.n_insample_heavy, len(fit_X))
        insample_heavy_X = fit_X[:n_in_heavy]
        insample_heavy_truth = self._heavy_targets(
            insample_heavy_X, cfg.n_inner_heavy, cfg.insample_heavy_seed
        )

        # --- 4. leakage diagnostics -----------------------------------------
        leakage = self._leakage(fit_X, val_X, cfg.fit_seed, cfg.validation_seed)
        if not leakage.leakage_free:
            notes.append("WARNING: hold-out leakage check did not pass — review seeds.")

        # --- 5. degree sweep on shared fitting data -------------------------
        rows: List[DegreeDiagnostics] = []
        surfaces: Dict[int, _FittedSurface] = {}
        for d in cfg.degrees:
            surf = _fit_surface(fit_X, fit_y, d)
            surfaces[d] = surf
            val_pred = surf.predict(val_X)
            in_pred = surf.predict(insample_heavy_X)
            resid = val_pred - val_truth
            denom = np.where(np.abs(val_truth) > 1e-9, np.abs(val_truth), 1.0)
            oos_rmse = float(np.sqrt(np.mean(resid ** 2)))
            oos_mae = float(np.mean(np.abs(resid)))
            oos_max_rel = float(np.max(np.abs(resid) / denom))
            oos_r2 = _r2(val_truth, val_pred)
            in_r2_heavy = _r2(insample_heavy_truth, in_pred)
            rows.append(DegreeDiagnostics(
                degree=d, n_basis_terms=_n_basis_terms(d),
                in_sample_r2_noisy=surf.in_sample_r2_noisy,
                in_sample_r2_heavy=in_r2_heavy,
                oos_rmse=oos_rmse, oos_r2=oos_r2, oos_mae=oos_mae,
                oos_max_abs_rel_error=oos_max_rel,
                overfit_gap=in_r2_heavy - oos_r2,
            ))

        # --- 6. model selection by OOS skill --------------------------------
        if cfg.selection_metric == "oos_rmse":
            selected = min(rows, key=lambda r: r.oos_rmse)
        else:
            selected = max(rows, key=lambda r: r.oos_r2)
        selected_degree = selected.degree

        # overfit onset: first degree (in sweep order) whose OOS RMSE exceeds
        # the previous degree's by more than a small tolerance.
        ordered = sorted(rows, key=lambda r: r.degree)
        overfit_onset: Optional[int] = None
        for prev, cur in zip(ordered, ordered[1:]):
            if cur.oos_rmse > prev.oos_rmse * 1.001:
                overfit_onset = cur.degree
                break

        # --- 7. capital comparison at the selected degree -------------------
        chosen = surfaces[selected_degree]
        eval_X = self._states(cfg.n_fit, cfg.fit_seed + 99)  # large cheap outer set
        proxy_l = chosen.predict(eval_X)
        proxy_capital = capital_metrics_from_liabilities(
            proxy_l, cfg.confidence_level, cfg.capital_horizon_months
        )
        nested_res = MultiDriverNestedEngine(
            self.product, self.hw_params, self.gbm_params, self.initial_curve,
            self.equity_guarantee, self.capital_horizon_months,
            cfg.confidence_level, self.outer_measure, self.annual_qx_fn,
        ).run(n_outer=nested_n_outer, n_inner=nested_n_inner, seed=cfg.fit_seed + 99)
        nested_capital = nested_res.capital

        def _rel(a: float, b: float) -> float:
            return abs(a - b) / (abs(b) if abs(b) > 1e-9 else 1.0)

        capital_cmp = CapitalComparison(
            proxy_capital=proxy_capital, nested_capital=nested_capital,
            var_rel_error=_rel(proxy_capital.var_liability, nested_capital.var_liability),
            es_rel_error=_rel(proxy_capital.es_liability, nested_capital.es_liability),
            scr_rel_error=_rel(proxy_capital.scr_proxy, nested_capital.scr_proxy),
            nested_n_outer=nested_n_outer, nested_n_inner=nested_n_inner,
        )

        # --- 8. reproducibility digest --------------------------------------
        digest = hashlib.sha256(
            np.round(np.concatenate([
                val_truth, chosen.beta,
                np.array([selected_degree, proxy_capital.var_liability,
                          proxy_capital.es_liability], dtype=float),
            ]), 9).tobytes()
        ).hexdigest()

        # --- 9. verdict -----------------------------------------------------
        verdict = self._verdict(selected, capital_cmp, leakage, notes)

        duration = time.monotonic() - t0

        audit_entry_id = None
        if governance_store is not None:
            try:
                from par_model_v2.governance.audit_trail import AuditEntry

                entry = AuditEntry.model_run(
                    actor=actor, phase=phase, run_id=run_id,
                    scenario_count=cfg.n_fit + cfg.n_validation * cfg.n_inner_heavy,
                    duration_seconds=round(duration, 4),
                    outcome="PASS" if verdict.startswith("PASS") else "PARTIAL",
                    files_changed=[
                        "par_model_v2/projection/multi_driver_proxy_validation.py"
                    ],
                    test_summary=(
                        "OOS proxy-val: selected deg={}, OOS R2={:.4f}, OOS RMSE={:.2f}, "
                        "overfit_onset={}, VaR rel err={:.2%}, leakage_free={}".format(
                            selected_degree, selected.oos_r2, selected.oos_rmse,
                            overfit_onset, capital_cmp.var_rel_error, leakage.leakage_free)
                    ),
                )
                governance_store.audit_trail.append(entry)
                audit_entry_id = entry.entry_id
            except Exception as exc:  # pragma: no cover - governance optional
                notes.append("audit append skipped: {}".format(exc))

        return ProxyValidationReport(
            config=cfg, degree_rows=ordered, selected_degree=selected_degree,
            selection_metric=cfg.selection_metric, overfit_onset_degree=overfit_onset,
            leakage=leakage, capital_comparison=capital_cmp,
            reproducibility_digest=digest, run_id=run_id, duration_seconds=duration,
            verdict=verdict, notes=notes, audit_entry_id=audit_entry_id,
        )

    @staticmethod
    def _verdict(
        selected: DegreeDiagnostics,
        capital_cmp: CapitalComparison,
        leakage: LeakageDiagnostics,
        notes: List[str],
    ) -> str:
        """Honest PASS / PARTIAL verdict against documented thresholds.

        Thresholds (educational): OOS R^2 >= 0.95, selected-degree VaR rel error
        <= 10%, hold-out leakage-free, and a non-negligible but bounded overfit
        gap (<= 0.05).
        """
        reasons: List[str] = []
        if selected.oos_r2 < 0.95:
            reasons.append("OOS R^2 {:.4f} < 0.95".format(selected.oos_r2))
        if capital_cmp.var_rel_error > 0.10:
            reasons.append("VaR rel error {:.2%} > 10%".format(capital_cmp.var_rel_error))
        if not leakage.leakage_free:
            reasons.append("hold-out not leakage-free")
        if selected.overfit_gap > 0.05:
            reasons.append("overfit gap {:.4f} > 0.05".format(selected.overfit_gap))
        if reasons:
            notes.append("verdict drivers: " + "; ".join(reasons))
            return "PARTIAL — " + "; ".join(reasons)
        return (
            "PASS — selected degree {} validated OOS (R^2={:.4f}, VaR rel err={:.2%}, "
            "leakage-free, overfit gap={:.4f})".format(
                selected.degree, selected.oos_r2, capital_cmp.var_rel_error,
                selected.overfit_gap)
        )


# ---------------------------------------------------------------------------
# Model-use restrictions (governance disclosure)
# ---------------------------------------------------------------------------

def proxy_validation_use_restrictions() -> Dict[str, object]:
    """Structured model-use restrictions for the OOS proxy validation."""
    return {
        "module": "par_model_v2/projection/multi_driver_proxy_validation.py",
        "classification": "EDUCATIONAL ONLY — proxy-model validation evidence, not a regulatory sign-off",
        "what_it_validates": (
            "Out-of-sample skill of the Phase 15 Task 1 bivariate LSMC capital "
            "surface against high-accuracy nested truth on an independent, "
            "disjoint-seed hold-out, with basis-degree selected by OOS error."
        ),
        "heavy_target_caveat": (
            "Validation targets are nested Monte-Carlo estimates with "
            "n_inner_heavy paths; they are accurate but not exact. OOS R^2/RMSE "
            "carry residual inner Monte-Carlo error ~1/sqrt(n_inner_heavy)."
        ),
        "selection_caveat": (
            "Degree selection minimises OOS error over the swept grid only; the "
            "true optimum may lie outside the grid. Selection is over the fitted "
            "interquartile state region — extrapolation is unsupported."
        ),
        "residual_risk": (
            "Lapse, credit-spread, mortality-trend, and FX risks remain outside "
            "the proxy. Parameters are illustrative placeholders; capital "
            "magnitudes are NOT calibrated."
        ),
        "governance": (
            "Independent APS X2 review pending; production sign-off withheld. "
            "Use only for education, methodology demonstration, and testing."
        ),
        "standards": [
            "SOA ASOP 56 §3.5", "SOA ASOP 56 §3.1.3", "SOA ASOP 25 §3.3",
            "IA TAS M §3.6", "IA TAS M §3.2", "IFoA proxy-model working party",
            "Longstaff & Schwartz (2001)",
        ],
    }


def proxy_validation_use_restrictions_json() -> str:
    return json.dumps(proxy_validation_use_restrictions(), indent=2, sort_keys=True)


# ===========================================================================
# Phase 17 Task 2 — Out-of-sample TRIVARIATE proxy validation
# ===========================================================================
#
# Extends the bivariate OOS validation above to the Phase 17 Task 1 THREE-driver
# (short-rate + equity + credit-spread) LSMC capital surface
# (:mod:`par_model_v2.projection.multi_driver_capital_3d`).
#
# The methodology is identical in spirit (genuine disjoint-seed hold-out; heavy
# nested validation targets; basis-complexity selection by OOS skill; leakage /
# overfit diagnostics; honest verdict) but the model-selection grid now sweeps
# BOTH the polynomial total-degree AND the capped three-way interaction order,
# because with three drivers the interaction structure — not just the degree —
# is a real complexity lever (IFoA proxy-modelling working-party basis
# discipline; SOA ASOP 56 §3.5; IA TAS M §3.6).
#
# Everything here is additive — the two-driver validator above and the Task 1
# three-driver engines are imported, never modified.

from par_model_v2.projection.multi_driver_capital_3d import (  # noqa: E402
    CreditExposureSpec,
    ThreeDriverCorrelation,
    ThreeDriverNestedEngine,
    _inner_pathwise_pvs_3d,
    _n_tri_basis_terms,
    _outer_states_3d,
    _tri_poly_basis,
)
from par_model_v2.stochastic.credit_spread import CreditSpreadParams  # noqa: E402

#: Default (total-degree, max-three-way-interaction-order) grid swept for the
#: trivariate proxy.  Spans degree 1->4 and both interaction caps at degree 3
#: (no genuine r*S*s term vs the single r*S*s term).  The 3-way cap only bites at
#: total degree >= 3, so degrees 1/2 are interaction-cap invariant.
DEFAULT_TRI_BASIS_GRID: Tuple[Tuple[int, int], ...] = (
    (1, 3), (2, 3), (3, 2), (3, 3), (4, 3),
)


# ---------------------------------------------------------------------------
# Generic n-D leakage helper (shared maths; 2-D static above is left untouched)
# ---------------------------------------------------------------------------

def _leakage_nd(
    fit_X: np.ndarray, val_X: np.ndarray, fit_seed: int, val_seed: int
) -> LeakageDiagnostics:
    """Disjointness evidence for fit vs hold-out states in any dimension.

    Identical logic to :meth:`MultiDriverProxyValidator._leakage` but dimension
    agnostic, so it serves the 3-D (r, S, s) hold-out.
    """
    fit_rows = {tuple(np.round(row, 12)) for row in fit_X}
    n_shared = sum(1 for row in val_X if tuple(np.round(row, 12)) in fit_rows)
    scale = fit_X.std(axis=0, ddof=0)
    scale = np.where(scale > 0, scale, 1.0)
    f = fit_X / scale
    v = val_X / scale
    min_d = np.inf
    for vp in v:
        d = np.sqrt(np.min(np.sum((f - vp) ** 2, axis=1)))
        min_d = min(min_d, float(d))
    seeds_disjoint = int(fit_seed) != int(val_seed)
    leakage_free = seeds_disjoint and n_shared == 0
    return LeakageDiagnostics(
        fit_seed=int(fit_seed), validation_seed=int(val_seed),
        seeds_disjoint=seeds_disjoint, n_exact_shared_states=int(n_shared),
        min_pairwise_distance=float(min_d), leakage_free=leakage_free,
    )


# ---------------------------------------------------------------------------
# Trivariate configuration
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class TriProxyValidationConfig:
    """Configuration for an out-of-sample TRIVARIATE proxy-validation run.

    Mirrors :class:`ProxyValidationConfig` but the model-selection grid is a
    tuple of ``(degree, max_interaction_order)`` pairs (``basis_grid``) rather
    than a tuple of degrees, because the three-way interaction cap is an
    independent complexity lever for three drivers.
    """

    n_fit: int = 1_000
    n_validation: int = 80
    n_insample_heavy: int = 60
    n_inner_heavy: int = 512
    basis_grid: Tuple[Tuple[int, int], ...] = DEFAULT_TRI_BASIS_GRID
    selection_metric: str = "oos_rmse"
    confidence_level: float = DEFAULT_CONFIDENCE_LEVEL
    capital_horizon_months: int = DEFAULT_CAPITAL_HORIZON_MONTHS
    fit_seed: int = 42
    validation_seed: int = 20260605
    insample_heavy_seed: int = 7
    outer_measure: Measure = Measure.P

    def __post_init__(self) -> None:
        if self.selection_metric not in ("oos_rmse", "oos_r2"):
            raise ValueError("selection_metric must be 'oos_rmse' or 'oos_r2'")
        if int(self.fit_seed) == int(self.validation_seed):
            raise ValueError(
                "fit_seed and validation_seed must differ to prevent hold-out leakage"
            )
        if not self.basis_grid:
            raise ValueError("basis_grid must be non-empty")
        for (d, m) in self.basis_grid:
            if d < 1:
                raise ValueError("all basis degrees must be >= 1")
            if m < 0:
                raise ValueError("all max_interaction_order values must be >= 0")
        if self.n_validation < 8:
            raise ValueError("n_validation must be >= 8 for a meaningful OOS metric")

    def to_dict(self) -> Dict[str, object]:
        return {
            "n_fit": self.n_fit,
            "n_validation": self.n_validation,
            "n_insample_heavy": self.n_insample_heavy,
            "n_inner_heavy": self.n_inner_heavy,
            "basis_grid": [list(p) for p in self.basis_grid],
            "selection_metric": self.selection_metric,
            "confidence_level": self.confidence_level,
            "capital_horizon_months": self.capital_horizon_months,
            "fit_seed": self.fit_seed,
            "validation_seed": self.validation_seed,
            "insample_heavy_seed": self.insample_heavy_seed,
            "outer_measure": self.outer_measure.value
            if isinstance(self.outer_measure, Measure)
            else str(self.outer_measure),
        }


# ---------------------------------------------------------------------------
# Trivariate per-basis diagnostics row
# ---------------------------------------------------------------------------

@dataclass
class TriBasisDiagnostics:
    """In/out-of-sample skill for a single ``(degree, max_interaction_order)``.

    Same metric set as :class:`DegreeDiagnostics`, with the extra
    ``max_interaction_order`` so the interaction-cap effect is visible.
    """

    degree: int
    max_interaction_order: int
    n_basis_terms: int
    in_sample_r2_noisy: float
    in_sample_r2_heavy: float
    oos_rmse: float
    oos_r2: float
    oos_mae: float
    oos_max_abs_rel_error: float
    overfit_gap: float

    def to_dict(self) -> Dict[str, object]:
        return {
            "degree": self.degree,
            "max_interaction_order": self.max_interaction_order,
            "n_basis_terms": self.n_basis_terms,
            "in_sample_r2_noisy": round(self.in_sample_r2_noisy, 6),
            "in_sample_r2_heavy": round(self.in_sample_r2_heavy, 6),
            "oos_rmse": round(self.oos_rmse, 6),
            "oos_r2": round(self.oos_r2, 6),
            "oos_mae": round(self.oos_mae, 6),
            "oos_max_abs_rel_error": round(self.oos_max_abs_rel_error, 6),
            "overfit_gap": round(self.overfit_gap, 6),
        }


@dataclass
class TriProxyValidationReport:
    """Full structured out-of-sample TRIVARIATE proxy-validation report."""

    config: TriProxyValidationConfig
    basis_rows: List[TriBasisDiagnostics]
    selected_degree: int
    selected_max_interaction_order: int
    selection_metric: str
    overfit_onset_terms: Optional[int]
    leakage: LeakageDiagnostics
    capital_comparison: CapitalComparison
    reproducibility_digest: str
    run_id: str
    duration_seconds: float
    verdict: str
    notes: List[str] = field(default_factory=list)
    audit_entry_id: Optional[str] = None

    def selected_row(self) -> TriBasisDiagnostics:
        return next(
            r for r in self.basis_rows
            if r.degree == self.selected_degree
            and r.max_interaction_order == self.selected_max_interaction_order
        )

    def to_dict(self) -> Dict[str, object]:
        return {
            "run_id": self.run_id,
            "verdict": self.verdict,
            "drivers": ["short_rate", "equity_level", "credit_spread"],
            "selected_degree": self.selected_degree,
            "selected_max_interaction_order": self.selected_max_interaction_order,
            "selection_metric": self.selection_metric,
            "overfit_onset_terms": self.overfit_onset_terms,
            "selected_row": self.selected_row().to_dict(),
            "basis_rows": [r.to_dict() for r in self.basis_rows],
            "leakage": self.leakage.to_dict(),
            "capital_comparison": self.capital_comparison.to_dict(),
            "reproducibility_digest": self.reproducibility_digest,
            "duration_seconds": round(self.duration_seconds, 4),
            "config": self.config.to_dict(),
            "notes": list(self.notes),
            "audit_entry_id": self.audit_entry_id,
            "standards": [
                "SOA ASOP 56 §3.5",
                "SOA ASOP 56 §3.1.3",
                "SOA ASOP 25 §3.3",
                "IA TAS M §3.6",
                "IA TAS M §3.2",
                "IFoA proxy-model working party",
                "Longstaff & Schwartz (2001)",
                "Duffie & Singleton (1999)",
                "Cox-Ingersoll-Ross (1985)",
            ],
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True)


# ---------------------------------------------------------------------------
# Trivariate surface fitting / prediction (shared-data refit per basis)
# ---------------------------------------------------------------------------

@dataclass
class _FittedTriSurface:
    beta: np.ndarray
    centers: np.ndarray
    scales: np.ndarray
    degree: int
    max_interaction_order: int
    in_sample_r2_noisy: float

    def predict(self, X: np.ndarray) -> np.ndarray:
        X = np.asarray(X, dtype=float)
        if X.ndim == 1:
            X = X.reshape(1, -1)
        Xs = (X - self.centers) / self.scales
        return _tri_poly_basis(Xs, self.degree, self.max_interaction_order) @ self.beta


def _fit_tri_surface(
    fit_X: np.ndarray, fit_y: np.ndarray, degree: int, max_interaction_order: int
) -> _FittedTriSurface:
    """Least-squares fit of the trivariate ``(degree, max_int)`` surface.

    Mirrors :meth:`ThreeDriverLSMCProxyEngine.fit_and_run` exactly (same
    centring/scaling and ``np.linalg.lstsq``) but takes the fitting data as
    arguments so every basis is fitted on the *same* states + payoffs.
    """
    centers = fit_X.mean(axis=0)
    scales = fit_X.std(axis=0, ddof=0)
    scales = np.where(scales > 0, scales, 1.0)
    Xs = (fit_X - centers) / scales
    design = _tri_poly_basis(Xs, degree, max_interaction_order)
    beta, _resid, _rank, _sv = np.linalg.lstsq(design, fit_y, rcond=None)
    y_hat = design @ beta
    ss_res = float(np.sum((fit_y - y_hat) ** 2))
    ss_tot = float(np.sum((fit_y - fit_y.mean()) ** 2)) or 1.0
    return _FittedTriSurface(
        beta=beta, centers=centers, scales=scales, degree=int(degree),
        max_interaction_order=int(max_interaction_order),
        in_sample_r2_noisy=1.0 - ss_res / ss_tot,
    )


# ---------------------------------------------------------------------------
# Trivariate validator
# ---------------------------------------------------------------------------

class ThreeDriverProxyValidator:
    """Orchestrate fit / hold-out / basis-selection for the 3-driver proxy.

    Owns the product and the HW1F / GBM / CIR++ / correlation / exposure
    assumptions; a single :meth:`validate` call runs the whole disjoint-seed
    hold-out workflow over the ``(degree, max_interaction_order)`` grid and
    returns a :class:`TriProxyValidationReport`.

    SOA ASOP 56 §3.5; IA TAS M §3.6; ASOP 25 §3.3; IFoA proxy-model WP.
    """

    def __init__(
        self,
        product: ParEndowmentProduct,
        hw_params: Optional[HullWhiteParams] = None,
        gbm_params: Optional[GBMParams] = None,
        spread_params: Optional[CreditSpreadParams] = None,
        correlation: Optional[ThreeDriverCorrelation] = None,
        initial_curve: Optional[RiskFreeCurve] = None,
        equity_guarantee: Optional[EquityGuaranteeSpec] = None,
        credit_exposure: Optional[CreditExposureSpec] = None,
        capital_horizon_months: int = DEFAULT_CAPITAL_HORIZON_MONTHS,
        confidence_level: float = DEFAULT_CONFIDENCE_LEVEL,
        outer_measure: Measure = Measure.P,
        annual_qx_fn: Optional[Callable] = None,
    ) -> None:
        if not (0 < capital_horizon_months < product.term_months):
            raise ValueError("capital_horizon_months must satisfy 0 < H < term_months")
        self.product = product
        self.hw_params = hw_params if hw_params is not None else HullWhiteParams()
        self.gbm_params = gbm_params if gbm_params is not None else GBMParams()
        self.spread_params = spread_params if spread_params is not None else CreditSpreadParams()
        self.correlation = correlation if correlation is not None else ThreeDriverCorrelation()
        self.initial_curve = initial_curve
        self.equity_guarantee = equity_guarantee or EquityGuaranteeSpec()
        self.credit_exposure = credit_exposure or CreditExposureSpec()
        self.capital_horizon_months = int(capital_horizon_months)
        self.confidence_level = float(confidence_level)
        self.outer_measure = Measure(outer_measure)
        self.annual_qx_fn = annual_qx_fn

    @property
    def _rem(self) -> int:
        return self.product.term_months - self.capital_horizon_months

    def _states(self, n: int, seed: int) -> np.ndarray:
        return _outer_states_3d(
            n, self.capital_horizon_months, self.outer_measure,
            self.hw_params, self.gbm_params, self.spread_params,
            self.correlation, self.initial_curve, seed,
        )

    def _single_path_payoffs(self, states: np.ndarray, seed: int) -> np.ndarray:
        """One inner path per state -> noisy fit target (matches Task 1 engine)."""
        child = np.random.SeedSequence(seed + 1).spawn(len(states))
        y = np.empty(len(states), dtype=float)
        for i, (r, s, c) in enumerate(states):
            inner_seed = int(child[i].generate_state(1)[0])
            pvs = _inner_pathwise_pvs_3d(
                float(r), float(s), float(c), 1, self._rem, self.product,
                self.hw_params, self.gbm_params, self.spread_params,
                self.correlation, self.capital_horizon_months, inner_seed,
                self.equity_guarantee, self.credit_exposure, self.annual_qx_fn,
            )
            y[i] = float(pvs[0])
        return y

    def _heavy_targets(self, states: np.ndarray, n_inner: int, seed: int) -> np.ndarray:
        """High-accuracy nested E^Q[L | r,S,s] at each state (the OOS truth)."""
        child = np.random.SeedSequence(seed).spawn(len(states))
        truth = np.empty(len(states), dtype=float)
        for i, (r, s, c) in enumerate(states):
            inner_seed = int(child[i].generate_state(1)[0])
            pvs = _inner_pathwise_pvs_3d(
                float(r), float(s), float(c), n_inner, self._rem, self.product,
                self.hw_params, self.gbm_params, self.spread_params,
                self.correlation, self.capital_horizon_months, inner_seed,
                self.equity_guarantee, self.credit_exposure, self.annual_qx_fn,
            )
            truth[i] = float(pvs.mean())
        return truth

    def validate(
        self,
        config: Optional[TriProxyValidationConfig] = None,
        nested_n_outer: int = 1_000,
        nested_n_inner: int = 128,
        governance_store: Optional["object"] = None,
        actor: str = "ThreeDriverProxyValidator",
        phase: str = "Phase 17: Third Risk Driver (Credit Spread) in the Economic-Capital Proxy",
    ) -> TriProxyValidationReport:
        cfg = config or TriProxyValidationConfig()
        t0 = time.monotonic()
        run_id = "td-proxyval-" + uuid.uuid4().hex[:8]
        notes: List[str] = []

        # --- 1. fitting data (one inner path each), seen ONLY by the fit -----
        fit_X = self._states(cfg.n_fit, cfg.fit_seed)
        fit_y = self._single_path_payoffs(fit_X, cfg.fit_seed)

        # --- 2. independent heavy hold-out (disjoint seed) ------------------
        val_X = self._states(cfg.n_validation, cfg.validation_seed)
        val_truth = self._heavy_targets(val_X, cfg.n_inner_heavy, cfg.validation_seed)

        # --- 3. held-in heavy subset (for the in/out skill gap) -------------
        n_in_heavy = min(cfg.n_insample_heavy, len(fit_X))
        insample_heavy_X = fit_X[:n_in_heavy]
        insample_heavy_truth = self._heavy_targets(
            insample_heavy_X, cfg.n_inner_heavy, cfg.insample_heavy_seed
        )

        # --- 4. leakage diagnostics -----------------------------------------
        leakage = _leakage_nd(fit_X, val_X, cfg.fit_seed, cfg.validation_seed)
        if not leakage.leakage_free:
            notes.append("WARNING: hold-out leakage check did not pass — review seeds.")

        # --- 5. basis sweep on shared fitting data --------------------------
        rows: List[TriBasisDiagnostics] = []
        surfaces: Dict[Tuple[int, int], _FittedTriSurface] = {}
        for (d, m) in cfg.basis_grid:
            surf = _fit_tri_surface(fit_X, fit_y, d, m)
            surfaces[(d, m)] = surf
            val_pred = surf.predict(val_X)
            in_pred = surf.predict(insample_heavy_X)
            resid = val_pred - val_truth
            denom = np.where(np.abs(val_truth) > 1e-9, np.abs(val_truth), 1.0)
            oos_rmse = float(np.sqrt(np.mean(resid ** 2)))
            oos_mae = float(np.mean(np.abs(resid)))
            oos_max_rel = float(np.max(np.abs(resid) / denom))
            oos_r2 = _r2(val_truth, val_pred)
            in_r2_heavy = _r2(insample_heavy_truth, in_pred)
            rows.append(TriBasisDiagnostics(
                degree=d, max_interaction_order=m,
                n_basis_terms=_n_tri_basis_terms(d, m),
                in_sample_r2_noisy=surf.in_sample_r2_noisy,
                in_sample_r2_heavy=in_r2_heavy,
                oos_rmse=oos_rmse, oos_r2=oos_r2, oos_mae=oos_mae,
                oos_max_abs_rel_error=oos_max_rel,
                overfit_gap=in_r2_heavy - oos_r2,
            ))

        # --- 6. model selection by OOS skill --------------------------------
        if cfg.selection_metric == "oos_rmse":
            selected = min(rows, key=lambda r: r.oos_rmse)
        else:
            selected = max(rows, key=lambda r: r.oos_r2)
        selected_key = (selected.degree, selected.max_interaction_order)

        # overfit onset: order bases by complexity (#terms) and find the first
        # whose OOS RMSE rises above the previous (less complex) basis.
        ordered = sorted(rows, key=lambda r: (r.n_basis_terms, r.degree, r.max_interaction_order))
        overfit_onset_terms: Optional[int] = None
        for prev, cur in zip(ordered, ordered[1:]):
            if cur.oos_rmse > prev.oos_rmse * 1.001:
                overfit_onset_terms = cur.n_basis_terms
                break

        # --- 7. capital comparison at the selected basis -------------------
        chosen = surfaces[selected_key]
        eval_X = self._states(cfg.n_fit, cfg.fit_seed + 99)  # large cheap outer set
        proxy_l = chosen.predict(eval_X)
        proxy_capital = capital_metrics_from_liabilities(
            proxy_l, cfg.confidence_level, cfg.capital_horizon_months
        )
        nested_res = ThreeDriverNestedEngine(
            self.product, self.hw_params, self.gbm_params, self.spread_params,
            self.correlation, self.initial_curve, self.equity_guarantee,
            self.credit_exposure, self.capital_horizon_months,
            cfg.confidence_level, self.outer_measure, self.annual_qx_fn,
        ).run(n_outer=nested_n_outer, n_inner=nested_n_inner, seed=cfg.fit_seed + 99)
        nested_capital = nested_res.capital

        def _rel(a: float, b: float) -> float:
            return abs(a - b) / (abs(b) if abs(b) > 1e-9 else 1.0)

        capital_cmp = CapitalComparison(
            proxy_capital=proxy_capital, nested_capital=nested_capital,
            var_rel_error=_rel(proxy_capital.var_liability, nested_capital.var_liability),
            es_rel_error=_rel(proxy_capital.es_liability, nested_capital.es_liability),
            scr_rel_error=_rel(proxy_capital.scr_proxy, nested_capital.scr_proxy),
            nested_n_outer=nested_n_outer, nested_n_inner=nested_n_inner,
        )

        # --- 8. reproducibility digest --------------------------------------
        digest = hashlib.sha256(
            np.round(np.concatenate([
                val_truth, chosen.beta,
                np.array([selected.degree, selected.max_interaction_order,
                          proxy_capital.var_liability, proxy_capital.es_liability],
                         dtype=float),
            ]), 9).tobytes()
        ).hexdigest()

        # --- 9. verdict -----------------------------------------------------
        verdict = self._verdict(selected, capital_cmp, leakage, notes)

        duration = time.monotonic() - t0

        audit_entry_id = None
        if governance_store is not None:
            try:
                from par_model_v2.governance.audit_trail import AuditEntry

                entry = AuditEntry.model_run(
                    actor=actor, phase=phase, run_id=run_id,
                    scenario_count=cfg.n_fit + cfg.n_validation * cfg.n_inner_heavy,
                    duration_seconds=round(duration, 4),
                    outcome="PASS" if verdict.startswith("PASS") else "PARTIAL",
                    files_changed=[
                        "par_model_v2/projection/multi_driver_proxy_validation.py"
                    ],
                    test_summary=(
                        "3D OOS proxy-val: selected (deg={}, max_int={}), OOS R2={:.4f}, "
                        "OOS RMSE={:.2f}, VaR rel err={:.2%}, leakage_free={}".format(
                            selected.degree, selected.max_interaction_order,
                            selected.oos_r2, selected.oos_rmse,
                            capital_cmp.var_rel_error, leakage.leakage_free)
                    ),
                )
                governance_store.audit_trail.append(entry)
                audit_entry_id = entry.entry_id
            except Exception as exc:  # pragma: no cover - governance optional
                notes.append("audit append skipped: {}".format(exc))

        return TriProxyValidationReport(
            config=cfg, basis_rows=ordered,
            selected_degree=selected.degree,
            selected_max_interaction_order=selected.max_interaction_order,
            selection_metric=cfg.selection_metric,
            overfit_onset_terms=overfit_onset_terms,
            leakage=leakage, capital_comparison=capital_cmp,
            reproducibility_digest=digest, run_id=run_id, duration_seconds=duration,
            verdict=verdict, notes=notes, audit_entry_id=audit_entry_id,
        )

    @staticmethod
    def _verdict(
        selected: TriBasisDiagnostics,
        capital_cmp: CapitalComparison,
        leakage: LeakageDiagnostics,
        notes: List[str],
    ) -> str:
        """Honest PASS / PARTIAL verdict against documented thresholds.

        Thresholds (educational): OOS R^2 >= 0.95, selected-basis VaR rel error
        <= 10%, hold-out leakage-free, and a bounded overfit gap (<= 0.05).
        """
        reasons: List[str] = []
        if selected.oos_r2 < 0.95:
            reasons.append("OOS R^2 {:.4f} < 0.95".format(selected.oos_r2))
        if capital_cmp.var_rel_error > 0.10:
            reasons.append("VaR rel error {:.2%} > 10%".format(capital_cmp.var_rel_error))
        if not leakage.leakage_free:
            reasons.append("hold-out not leakage-free")
        if selected.overfit_gap > 0.05:
            reasons.append("overfit gap {:.4f} > 0.05".format(selected.overfit_gap))
        if reasons:
            notes.append("verdict drivers: " + "; ".join(reasons))
            return "PARTIAL — " + "; ".join(reasons)
        return (
            "PASS — selected basis (deg {}, max_int {}) validated OOS "
            "(R^2={:.4f}, VaR rel err={:.2%}, leakage-free, overfit gap={:.4f})".format(
                selected.degree, selected.max_interaction_order, selected.oos_r2,
                capital_cmp.var_rel_error, selected.overfit_gap)
        )


def tri_proxy_validation_use_restrictions() -> Dict[str, object]:
    """Structured model-use restrictions for the TRIVARIATE OOS proxy validation."""
    base = proxy_validation_use_restrictions()
    base.update({
        "module": "par_model_v2/projection/multi_driver_proxy_validation.py::ThreeDriverProxyValidator",
        "classification": "EDUCATIONAL ONLY — three-driver proxy-model validation evidence, not a regulatory sign-off",
        "what_it_validates": (
            "Out-of-sample skill of the Phase 17 Task 1 TRIVARIATE (rate + equity "
            "+ credit-spread) LSMC capital surface against high-accuracy nested "
            "truth on an independent, disjoint-seed hold-out, with the basis "
            "(polynomial degree AND capped three-way interaction order) selected "
            "by OOS error."
        ),
        "selection_caveat": (
            "Basis selection minimises OOS error over the swept (degree, "
            "max_interaction_order) grid only; the true optimum may lie outside "
            "the grid. Valid only over the fitted 3-D interquartile state region "
            "— extrapolation is unsupported."
        ),
        "residual_risk": (
            "Lapse, mortality-trend, and FX risks remain outside the proxy; "
            "credit is a single systemic CIR++ spread (no rating migration / "
            "default jump). Parameters are illustrative placeholders; capital "
            "magnitudes are NOT calibrated."
        ),
        "standards": [
            "SOA ASOP 56 §3.5", "SOA ASOP 56 §3.1.3", "SOA ASOP 25 §3.3",
            "IA TAS M §3.6", "IA TAS M §3.2", "IFoA proxy-model working party",
            "Longstaff & Schwartz (2001)", "Duffie & Singleton (1999)",
            "Cox-Ingersoll-Ross (1985)",
        ],
    })
    return base


def tri_proxy_validation_use_restrictions_json() -> str:
    return json.dumps(tri_proxy_validation_use_restrictions(), indent=2, sort_keys=True)


__all__ = [
    "DEFAULT_DEGREE_GRID",
    "DEFAULT_HEAVY_INNER",
    "ProxyValidationConfig",
    "DegreeDiagnostics",
    "LeakageDiagnostics",
    "CapitalComparison",
    "ProxyValidationReport",
    "MultiDriverProxyValidator",
    "proxy_validation_use_restrictions",
    "proxy_validation_use_restrictions_json",
    "_fit_surface",
    "_r2",
    # --- Phase 17 Task 2: trivariate OOS proxy validation ---
    "DEFAULT_TRI_BASIS_GRID",
    "TriProxyValidationConfig",
    "TriBasisDiagnostics",
    "TriProxyValidationReport",
    "ThreeDriverProxyValidator",
    "tri_proxy_validation_use_restrictions",
    "tri_proxy_validation_use_restrictions_json",
    "_fit_tri_surface",
    "_leakage_nd",
]


# ===========================================================================
# Phase 18 Task 3: FOUR-DRIVER out-of-sample proxy validation
# ===========================================================================
#
# Everything here is additive — the two- and three-driver validators above and
# the Phase 18 Task 3 four-driver engines are imported, never modified.

from par_model_v2.projection.multi_driver_capital_4d import (  # noqa: E402
    FourDriverCorrelation,
    FourDriverNestedEngine,
    LapseExposureSpec,
    _inner_pathwise_pvs_4d,
    _n_quad_basis_terms,
    _outer_states_4d,
    _quad_poly_basis,
)
from par_model_v2.stochastic.lapse_behaviour import LapseBehaviourParams  # noqa: E402


#: Default (degree, max_interaction_order) grid swept for the four-driver basis.
#: Interaction order is a genuine complexity lever once there are four drivers
#: (the in-force factor multiplies the equity put, an r·b·S interaction).
DEFAULT_QUAD_BASIS_GRID: Tuple[Tuple[int, int], ...] = (
    (1, 3), (2, 3), (3, 2), (3, 3), (4, 3),
)


@dataclass(frozen=True)
class QuadProxyValidationConfig:
    """Configuration for an out-of-sample FOUR-DRIVER proxy-validation run.

    Mirrors :class:`TriProxyValidationConfig`; the model-selection grid is a
    tuple of ``(degree, max_interaction_order)`` pairs (``basis_grid``).
    """

    n_fit: int = 1_000
    n_validation: int = 80
    n_insample_heavy: int = 60
    n_inner_heavy: int = 512
    basis_grid: Tuple[Tuple[int, int], ...] = DEFAULT_QUAD_BASIS_GRID
    selection_metric: str = "oos_rmse"
    confidence_level: float = DEFAULT_CONFIDENCE_LEVEL
    capital_horizon_months: int = DEFAULT_CAPITAL_HORIZON_MONTHS
    fit_seed: int = 42
    validation_seed: int = 20260605
    insample_heavy_seed: int = 7
    outer_measure: Measure = Measure.P

    def __post_init__(self) -> None:
        if self.selection_metric not in ("oos_rmse", "oos_r2"):
            raise ValueError("selection_metric must be 'oos_rmse' or 'oos_r2'")
        if int(self.fit_seed) == int(self.validation_seed):
            raise ValueError(
                "fit_seed and validation_seed must differ to prevent hold-out leakage"
            )
        if not self.basis_grid:
            raise ValueError("basis_grid must be non-empty")
        for (d, m) in self.basis_grid:
            if d < 1:
                raise ValueError("all basis degrees must be >= 1")
            if m < 0:
                raise ValueError("all max_interaction_order values must be >= 0")
        if self.n_validation < 8:
            raise ValueError("n_validation must be >= 8 for a meaningful OOS metric")

    def to_dict(self) -> Dict[str, object]:
        return {
            "n_fit": self.n_fit,
            "n_validation": self.n_validation,
            "n_insample_heavy": self.n_insample_heavy,
            "n_inner_heavy": self.n_inner_heavy,
            "basis_grid": [list(p) for p in self.basis_grid],
            "selection_metric": self.selection_metric,
            "confidence_level": self.confidence_level,
            "capital_horizon_months": self.capital_horizon_months,
            "fit_seed": self.fit_seed,
            "validation_seed": self.validation_seed,
            "insample_heavy_seed": self.insample_heavy_seed,
            "outer_measure": self.outer_measure.value
            if isinstance(self.outer_measure, Measure)
            else str(self.outer_measure),
        }


@dataclass
class QuadBasisDiagnostics:
    """In/out-of-sample skill for a single ``(degree, max_interaction_order)``."""

    degree: int
    max_interaction_order: int
    n_basis_terms: int
    in_sample_r2_noisy: float
    in_sample_r2_heavy: float
    oos_rmse: float
    oos_r2: float
    oos_mae: float
    oos_max_abs_rel_error: float
    overfit_gap: float

    def to_dict(self) -> Dict[str, object]:
        return {
            "degree": self.degree,
            "max_interaction_order": self.max_interaction_order,
            "n_basis_terms": self.n_basis_terms,
            "in_sample_r2_noisy": round(self.in_sample_r2_noisy, 6),
            "in_sample_r2_heavy": round(self.in_sample_r2_heavy, 6),
            "oos_rmse": round(self.oos_rmse, 6),
            "oos_r2": round(self.oos_r2, 6),
            "oos_mae": round(self.oos_mae, 6),
            "oos_max_abs_rel_error": round(self.oos_max_abs_rel_error, 6),
            "overfit_gap": round(self.overfit_gap, 6),
        }


@dataclass
class QuadProxyValidationReport:
    """Full structured out-of-sample FOUR-DRIVER proxy-validation report."""

    config: QuadProxyValidationConfig
    basis_rows: List[QuadBasisDiagnostics]
    selected_degree: int
    selected_max_interaction_order: int
    selection_metric: str
    overfit_onset_terms: Optional[int]
    leakage: LeakageDiagnostics
    capital_comparison: CapitalComparison
    reproducibility_digest: str
    run_id: str
    duration_seconds: float
    verdict: str
    notes: List[str] = field(default_factory=list)
    audit_entry_id: Optional[str] = None

    def selected_row(self) -> QuadBasisDiagnostics:
        return next(
            r for r in self.basis_rows
            if r.degree == self.selected_degree
            and r.max_interaction_order == self.selected_max_interaction_order
        )

    def to_dict(self) -> Dict[str, object]:
        return {
            "run_id": self.run_id,
            "verdict": self.verdict,
            "drivers": ["short_rate", "equity_level", "credit_spread", "lapse_behaviour"],
            "selected_degree": self.selected_degree,
            "selected_max_interaction_order": self.selected_max_interaction_order,
            "selection_metric": self.selection_metric,
            "overfit_onset_terms": self.overfit_onset_terms,
            "selected_row": self.selected_row().to_dict(),
            "basis_rows": [r.to_dict() for r in self.basis_rows],
            "leakage": self.leakage.to_dict(),
            "capital_comparison": self.capital_comparison.to_dict(),
            "reproducibility_digest": self.reproducibility_digest,
            "duration_seconds": round(self.duration_seconds, 4),
            "config": self.config.to_dict(),
            "notes": list(self.notes),
            "audit_entry_id": self.audit_entry_id,
            "standards": [
                "SOA ASOP 7 §3.3",
                "SOA ASOP 56 §3.5",
                "SOA ASOP 56 §3.1.3",
                "SOA ASOP 25 §3.3",
                "IA TAS M §3.6",
                "IA TAS M §3.2",
                "IFoA proxy-modelling working party",
                "Longstaff & Schwartz (2001)",
                "Duffie & Singleton (1999)",
                "Cox-Ingersoll-Ross (1985)",
            ],
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True)


@dataclass
class _FittedQuadSurface:
    beta: np.ndarray
    centers: np.ndarray
    scales: np.ndarray
    degree: int
    max_interaction_order: int
    in_sample_r2_noisy: float

    def predict(self, X: np.ndarray) -> np.ndarray:
        X = np.asarray(X, dtype=float)
        if X.ndim == 1:
            X = X.reshape(1, -1)
        Xs = (X - self.centers) / self.scales
        return _quad_poly_basis(Xs, self.degree, self.max_interaction_order) @ self.beta


def _fit_quad_surface(
    fit_X: np.ndarray, fit_y: np.ndarray, degree: int, max_interaction_order: int
) -> _FittedQuadSurface:
    """Least-squares fit of the quadrivariate ``(degree, max_int)`` surface.

    Mirrors :meth:`FourDriverLSMCProxyEngine.fit_and_run` exactly (same
    centring/scaling and ``np.linalg.lstsq``) but takes the fitting data as
    arguments so every basis is fitted on the *same* states + payoffs.
    """
    centers = fit_X.mean(axis=0)
    scales = fit_X.std(axis=0, ddof=0)
    scales = np.where(scales > 0, scales, 1.0)
    Xs = (fit_X - centers) / scales
    design = _quad_poly_basis(Xs, degree, max_interaction_order)
    beta, _resid, _rank, _sv = np.linalg.lstsq(design, fit_y, rcond=None)
    y_hat = design @ beta
    ss_res = float(np.sum((fit_y - y_hat) ** 2))
    ss_tot = float(np.sum((fit_y - fit_y.mean()) ** 2)) or 1.0
    return _FittedQuadSurface(
        beta=beta, centers=centers, scales=scales, degree=int(degree),
        max_interaction_order=int(max_interaction_order),
        in_sample_r2_noisy=1.0 - ss_res / ss_tot,
    )


class FourDriverProxyValidator:
    """Orchestrate fit / hold-out / basis-selection for the 4-driver proxy.

    Owns the product and the HW1F / GBM / CIR++ / OU-lapse / correlation /
    exposure assumptions; a single :meth:`validate` call runs the whole
    disjoint-seed hold-out workflow over the ``(degree, max_interaction_order)``
    grid and returns a :class:`QuadProxyValidationReport`.

    SOA ASOP 7 §3.3; ASOP 56 §3.5; IA TAS M §3.6; ASOP 25 §3.3; IFoA WP.
    """

    def __init__(
        self,
        product: ParEndowmentProduct,
        hw_params: Optional[HullWhiteParams] = None,
        gbm_params: Optional[GBMParams] = None,
        spread_params: Optional[CreditSpreadParams] = None,
        lapse_params: Optional[LapseBehaviourParams] = None,
        correlation: Optional[FourDriverCorrelation] = None,
        initial_curve: Optional[RiskFreeCurve] = None,
        equity_guarantee: Optional[EquityGuaranteeSpec] = None,
        credit_exposure: Optional[CreditExposureSpec] = None,
        lapse_exposure: Optional[LapseExposureSpec] = None,
        capital_horizon_months: int = DEFAULT_CAPITAL_HORIZON_MONTHS,
        confidence_level: float = DEFAULT_CONFIDENCE_LEVEL,
        outer_measure: Measure = Measure.P,
        annual_qx_fn: Optional[Callable] = None,
    ) -> None:
        if not (0 < capital_horizon_months < product.term_months):
            raise ValueError("capital_horizon_months must satisfy 0 < H < term_months")
        self.product = product
        self.hw_params = hw_params if hw_params is not None else HullWhiteParams()
        self.gbm_params = gbm_params if gbm_params is not None else GBMParams()
        self.spread_params = spread_params if spread_params is not None else CreditSpreadParams()
        self.lapse_params = lapse_params if lapse_params is not None else LapseBehaviourParams()
        self.correlation = correlation if correlation is not None else FourDriverCorrelation()
        self.initial_curve = initial_curve
        self.equity_guarantee = equity_guarantee or EquityGuaranteeSpec()
        self.credit_exposure = credit_exposure or CreditExposureSpec()
        self.lapse_exposure = lapse_exposure or LapseExposureSpec()
        self.capital_horizon_months = int(capital_horizon_months)
        self.confidence_level = float(confidence_level)
        self.outer_measure = Measure(outer_measure)
        self.annual_qx_fn = annual_qx_fn

    @property
    def _rem(self) -> int:
        return self.product.term_months - self.capital_horizon_months

    def _states(self, n: int, seed: int) -> np.ndarray:
        return _outer_states_4d(
            n, self.capital_horizon_months, self.outer_measure,
            self.hw_params, self.gbm_params, self.spread_params, self.lapse_params,
            self.correlation, self.initial_curve, seed,
        )

    def _single_path_payoffs(self, states: np.ndarray, seed: int) -> np.ndarray:
        """One inner path per state -> noisy fit target (matches Task 3 engine)."""
        child = np.random.SeedSequence(seed + 1).spawn(len(states))
        y = np.empty(len(states), dtype=float)
        for i, (r, s, c, b) in enumerate(states):
            inner_seed = int(child[i].generate_state(1)[0])
            pvs = _inner_pathwise_pvs_4d(
                float(r), float(s), float(c), float(b), 1, self._rem, self.product,
                self.hw_params, self.gbm_params, self.spread_params,
                self.correlation, self.capital_horizon_months, inner_seed,
                self.equity_guarantee, self.credit_exposure, self.lapse_exposure,
                self.annual_qx_fn,
            )
            y[i] = float(pvs[0])
        return y

    def _heavy_targets(self, states: np.ndarray, n_inner: int, seed: int) -> np.ndarray:
        """High-accuracy nested E^Q[L | r,S,s,b] at each state (the OOS truth)."""
        child = np.random.SeedSequence(seed).spawn(len(states))
        truth = np.empty(len(states), dtype=float)
        for i, (r, s, c, b) in enumerate(states):
            inner_seed = int(child[i].generate_state(1)[0])
            pvs = _inner_pathwise_pvs_4d(
                float(r), float(s), float(c), float(b), n_inner, self._rem, self.product,
                self.hw_params, self.gbm_params, self.spread_params,
                self.correlation, self.capital_horizon_months, inner_seed,
                self.equity_guarantee, self.credit_exposure, self.lapse_exposure,
                self.annual_qx_fn,
            )
            truth[i] = float(pvs.mean())
        return truth

    def validate(
        self,
        config: Optional[QuadProxyValidationConfig] = None,
        nested_n_outer: int = 1_000,
        nested_n_inner: int = 128,
        governance_store: Optional["object"] = None,
        actor: str = "FourDriverProxyValidator",
        phase: str = "Phase 18: Tail-Dependent Risk Aggregation and Driver/Calibration Sophistication",
    ) -> QuadProxyValidationReport:
        cfg = config or QuadProxyValidationConfig()
        t0 = time.monotonic()
        run_id = "fd-proxyval-" + uuid.uuid4().hex[:8]
        notes: List[str] = []

        # --- 1. fitting data (one inner path each), seen ONLY by the fit -----
        fit_X = self._states(cfg.n_fit, cfg.fit_seed)
        fit_y = self._single_path_payoffs(fit_X, cfg.fit_seed)

        # --- 2. independent heavy hold-out (disjoint seed) ------------------
        val_X = self._states(cfg.n_validation, cfg.validation_seed)
        val_truth = self._heavy_targets(val_X, cfg.n_inner_heavy, cfg.validation_seed)

        # --- 3. held-in heavy subset (for the in/out skill gap) -------------
        n_in_heavy = min(cfg.n_insample_heavy, len(fit_X))
        insample_heavy_X = fit_X[:n_in_heavy]
        insample_heavy_truth = self._heavy_targets(
            insample_heavy_X, cfg.n_inner_heavy, cfg.insample_heavy_seed
        )

        # --- 4. leakage diagnostics -----------------------------------------
        leakage = _leakage_nd(fit_X, val_X, cfg.fit_seed, cfg.validation_seed)
        if not leakage.leakage_free:
            notes.append("WARNING: hold-out leakage check did not pass — review seeds.")

        # --- 5. basis sweep on shared fitting data --------------------------
        rows: List[QuadBasisDiagnostics] = []
        surfaces: Dict[Tuple[int, int], _FittedQuadSurface] = {}
        for (d, m) in cfg.basis_grid:
            surf = _fit_quad_surface(fit_X, fit_y, d, m)
            surfaces[(d, m)] = surf
            val_pred = surf.predict(val_X)
            in_pred = surf.predict(insample_heavy_X)
            resid = val_pred - val_truth
            denom = np.where(np.abs(val_truth) > 1e-9, np.abs(val_truth), 1.0)
            oos_rmse = float(np.sqrt(np.mean(resid ** 2)))
            oos_mae = float(np.mean(np.abs(resid)))
            oos_max_rel = float(np.max(np.abs(resid) / denom))
            oos_r2 = _r2(val_truth, val_pred)
            in_r2_heavy = _r2(insample_heavy_truth, in_pred)
            rows.append(QuadBasisDiagnostics(
                degree=d, max_interaction_order=m,
                n_basis_terms=_n_quad_basis_terms(d, m),
                in_sample_r2_noisy=surf.in_sample_r2_noisy,
                in_sample_r2_heavy=in_r2_heavy,
                oos_rmse=oos_rmse, oos_r2=oos_r2, oos_mae=oos_mae,
                oos_max_abs_rel_error=oos_max_rel,
                overfit_gap=in_r2_heavy - oos_r2,
            ))

        # --- 6. model selection by OOS skill --------------------------------
        if cfg.selection_metric == "oos_rmse":
            selected = min(rows, key=lambda r: r.oos_rmse)
        else:
            selected = max(rows, key=lambda r: r.oos_r2)
        selected_key = (selected.degree, selected.max_interaction_order)

        # overfit onset: order bases by complexity (#terms) and find the first
        # whose OOS RMSE rises above the previous (less complex) basis.
        ordered = sorted(rows, key=lambda r: (r.n_basis_terms, r.degree, r.max_interaction_order))
        overfit_onset_terms: Optional[int] = None
        for prev, cur in zip(ordered, ordered[1:]):
            if cur.oos_rmse > prev.oos_rmse * 1.001:
                overfit_onset_terms = cur.n_basis_terms
                break

        # --- 7. capital comparison at the selected basis -------------------
        chosen = surfaces[selected_key]
        eval_X = self._states(cfg.n_fit, cfg.fit_seed + 99)  # large cheap outer set
        proxy_l = chosen.predict(eval_X)
        proxy_capital = capital_metrics_from_liabilities(
            proxy_l, cfg.confidence_level, cfg.capital_horizon_months
        )
        nested_res = FourDriverNestedEngine(
            self.product, self.hw_params, self.gbm_params, self.spread_params,
            self.lapse_params, self.correlation, self.initial_curve,
            self.equity_guarantee, self.credit_exposure, self.lapse_exposure,
            self.capital_horizon_months, cfg.confidence_level, self.outer_measure,
            self.annual_qx_fn,
        ).run(n_outer=nested_n_outer, n_inner=nested_n_inner, seed=cfg.fit_seed + 99)
        nested_capital = nested_res.capital

        def _rel(a: float, b: float) -> float:
            return abs(a - b) / (abs(b) if abs(b) > 1e-9 else 1.0)

        capital_cmp = CapitalComparison(
            proxy_capital=proxy_capital, nested_capital=nested_capital,
            var_rel_error=_rel(proxy_capital.var_liability, nested_capital.var_liability),
            es_rel_error=_rel(proxy_capital.es_liability, nested_capital.es_liability),
            scr_rel_error=_rel(proxy_capital.scr_proxy, nested_capital.scr_proxy),
            nested_n_outer=nested_n_outer, nested_n_inner=nested_n_inner,
        )

        # --- 8. reproducibility digest --------------------------------------
        digest = hashlib.sha256(
            np.round(np.concatenate([
                val_truth, chosen.beta,
                np.array([selected.degree, selected.max_interaction_order,
                          proxy_capital.var_liability, proxy_capital.es_liability],
                         dtype=float),
            ]), 9).tobytes()
        ).hexdigest()

        # --- 9. verdict -----------------------------------------------------
        verdict = self._verdict(selected, capital_cmp, leakage, notes)

        duration = time.monotonic() - t0

        audit_entry_id = None
        if governance_store is not None:
            try:
                from par_model_v2.governance.audit_trail import AuditEntry

                entry = AuditEntry.model_run(
                    actor=actor, phase=phase, run_id=run_id,
                    scenario_count=cfg.n_fit + cfg.n_validation * cfg.n_inner_heavy,
                    duration_seconds=round(duration, 4),
                    outcome="PASS" if verdict.startswith("PASS") else "PARTIAL",
                    files_changed=[
                        "par_model_v2/projection/multi_driver_proxy_validation.py"
                    ],
                    test_summary=(
                        "4D OOS proxy-val: selected (deg={}, max_int={}), OOS R2={:.4f}, "
                        "OOS RMSE={:.2f}, VaR rel err={:.2%}, leakage_free={}".format(
                            selected.degree, selected.max_interaction_order,
                            selected.oos_r2, selected.oos_rmse,
                            capital_cmp.var_rel_error, leakage.leakage_free)
                    ),
                )
                governance_store.audit_trail.append(entry)
                audit_entry_id = entry.entry_id
            except Exception as exc:  # pragma: no cover - governance optional
                notes.append("audit append skipped: {}".format(exc))

        return QuadProxyValidationReport(
            config=cfg, basis_rows=ordered,
            selected_degree=selected.degree,
            selected_max_interaction_order=selected.max_interaction_order,
            selection_metric=cfg.selection_metric,
            overfit_onset_terms=overfit_onset_terms,
            leakage=leakage, capital_comparison=capital_cmp,
            reproducibility_digest=digest, run_id=run_id, duration_seconds=duration,
            verdict=verdict, notes=notes, audit_entry_id=audit_entry_id,
        )

    @staticmethod
    def _verdict(
        selected: QuadBasisDiagnostics,
        capital_cmp: CapitalComparison,
        leakage: LeakageDiagnostics,
        notes: List[str],
    ) -> str:
        """Honest PASS / PARTIAL verdict against documented thresholds.

        Thresholds (educational): OOS R^2 >= 0.95, selected-basis VaR rel error
        <= 10%, hold-out leakage-free, and a bounded overfit gap (<= 0.05).
        """
        reasons: List[str] = []
        if selected.oos_r2 < 0.95:
            reasons.append("OOS R^2 {:.4f} < 0.95".format(selected.oos_r2))
        if capital_cmp.var_rel_error > 0.10:
            reasons.append("VaR rel error {:.2%} > 10%".format(capital_cmp.var_rel_error))
        if not leakage.leakage_free:
            reasons.append("hold-out not leakage-free")
        if selected.overfit_gap > 0.05:
            reasons.append("overfit gap {:.4f} > 0.05".format(selected.overfit_gap))
        if reasons:
            notes.append("verdict drivers: " + "; ".join(reasons))
            return "PARTIAL — " + "; ".join(reasons)
        return (
            "PASS — selected basis (deg {}, max_int {}) validated OOS "
            "(R^2={:.4f}, VaR rel err={:.2%}, leakage-free, overfit gap={:.4f})".format(
                selected.degree, selected.max_interaction_order, selected.oos_r2,
                capital_cmp.var_rel_error, selected.overfit_gap)
        )


def quad_proxy_validation_use_restrictions() -> Dict[str, object]:
    """Structured model-use restrictions for the FOUR-DRIVER OOS proxy validation."""
    base = proxy_validation_use_restrictions()
    base.update({
        "module": "par_model_v2/projection/multi_driver_proxy_validation.py::FourDriverProxyValidator",
        "classification": "EDUCATIONAL ONLY — four-driver proxy-model validation evidence, not a regulatory sign-off",
        "what_it_validates": (
            "Out-of-sample skill of the Phase 18 Task 3 QUADRIVARIATE (rate + "
            "equity + credit-spread + lapse-behaviour) LSMC capital surface "
            "against high-accuracy nested truth on an independent, disjoint-seed "
            "hold-out, with the basis (polynomial degree AND capped higher-order "
            "interaction order) selected by OOS error."
        ),
        "selection_caveat": (
            "Basis selection minimises OOS error over the swept (degree, "
            "max_interaction_order) grid only; the true optimum may lie outside "
            "the grid. Valid only over the fitted 4-D interquartile state region "
            "— extrapolation is unsupported."
        ),
        "residual_risk": (
            "Mortality-trend and FX risks remain outside the proxy; lapse is a "
            "single systemic OU behavioural index (no product / cohort "
            "structure); credit is a single systemic CIR++ spread. Parameters "
            "are illustrative placeholders; capital magnitudes are NOT calibrated."
        ),
        "standards": [
            "SOA ASOP 7 §3.3", "SOA ASOP 56 §3.5", "SOA ASOP 56 §3.1.3",
            "SOA ASOP 25 §3.3", "IA TAS M §3.6", "IA TAS M §3.2",
            "IFoA proxy-modelling working party", "Longstaff & Schwartz (2001)",
            "Duffie & Singleton (1999)", "Cox-Ingersoll-Ross (1985)",
        ],
    })
    return base


def quad_proxy_validation_use_restrictions_json() -> str:
    return json.dumps(quad_proxy_validation_use_restrictions(), indent=2, sort_keys=True)


__all__ += [
    # --- Phase 18 Task 3: four-driver OOS proxy validation ---
    "DEFAULT_QUAD_BASIS_GRID",
    "QuadProxyValidationConfig",
    "QuadBasisDiagnostics",
    "QuadProxyValidationReport",
    "FourDriverProxyValidator",
    "quad_proxy_validation_use_restrictions",
    "quad_proxy_validation_use_restrictions_json",
    "_fit_quad_surface",
]


# ===========================================================================
# Phase 19 Task 3: FIVE-DRIVER out-of-sample proxy validation
# ===========================================================================
#
# Everything here is additive — the two-, three- and four-driver validators
# above and the Phase 19 Task 3 five-driver engines are imported, never modified.

from par_model_v2.projection.multi_driver_capital_5d import (  # noqa: E402
    FiveDriverCorrelation,
    FiveDriverNestedEngine,
    MortalityExposureSpec,
    _inner_pathwise_pvs_5d,
    _n_quint_basis_terms,
    _outer_states_5d,
    _quint_poly_basis,
)
from par_model_v2.stochastic.mortality_trend import MortalityTrendParams  # noqa: E402


#: Default (degree, max_interaction_order) grid swept for the five-driver basis.
#: Interaction order is a genuine complexity lever once there are five drivers
#: (the in-force factor multiplies the equity put while the mortality multiplier
#: scales the guaranteed leg — an r·b·m·S interaction).
DEFAULT_QUINT_BASIS_GRID: Tuple[Tuple[int, int], ...] = (
    (1, 3), (2, 3), (3, 2), (3, 3), (4, 3),
)


@dataclass(frozen=True)
class QuintProxyValidationConfig:
    """Configuration for an out-of-sample FIVE-DRIVER proxy-validation run.

    Mirrors :class:`QuadProxyValidationConfig`; the model-selection grid is a
    tuple of ``(degree, max_interaction_order)`` pairs (``basis_grid``).
    """

    n_fit: int = 1_000
    n_validation: int = 80
    n_insample_heavy: int = 60
    n_inner_heavy: int = 512
    basis_grid: Tuple[Tuple[int, int], ...] = DEFAULT_QUINT_BASIS_GRID
    selection_metric: str = "oos_rmse"
    confidence_level: float = DEFAULT_CONFIDENCE_LEVEL
    capital_horizon_months: int = DEFAULT_CAPITAL_HORIZON_MONTHS
    fit_seed: int = 42
    validation_seed: int = 20260606
    insample_heavy_seed: int = 7
    outer_measure: Measure = Measure.P

    def __post_init__(self) -> None:
        if self.selection_metric not in ("oos_rmse", "oos_r2"):
            raise ValueError("selection_metric must be 'oos_rmse' or 'oos_r2'")
        if int(self.fit_seed) == int(self.validation_seed):
            raise ValueError(
                "fit_seed and validation_seed must differ to prevent hold-out leakage"
            )
        if not self.basis_grid:
            raise ValueError("basis_grid must be non-empty")
        for (d, m) in self.basis_grid:
            if d < 1:
                raise ValueError("all basis degrees must be >= 1")
            if m < 0:
                raise ValueError("all max_interaction_order values must be >= 0")
        if self.n_validation < 8:
            raise ValueError("n_validation must be >= 8 for a meaningful OOS metric")

    def to_dict(self) -> Dict[str, object]:
        return {
            "n_fit": self.n_fit,
            "n_validation": self.n_validation,
            "n_insample_heavy": self.n_insample_heavy,
            "n_inner_heavy": self.n_inner_heavy,
            "basis_grid": [list(p) for p in self.basis_grid],
            "selection_metric": self.selection_metric,
            "confidence_level": self.confidence_level,
            "capital_horizon_months": self.capital_horizon_months,
            "fit_seed": self.fit_seed,
            "validation_seed": self.validation_seed,
            "insample_heavy_seed": self.insample_heavy_seed,
            "outer_measure": self.outer_measure.value
            if isinstance(self.outer_measure, Measure)
            else str(self.outer_measure),
        }


@dataclass
class QuintBasisDiagnostics:
    """In/out-of-sample skill for a single ``(degree, max_interaction_order)``."""

    degree: int
    max_interaction_order: int
    n_basis_terms: int
    in_sample_r2_noisy: float
    in_sample_r2_heavy: float
    oos_rmse: float
    oos_r2: float
    oos_mae: float
    oos_max_abs_rel_error: float
    overfit_gap: float

    def to_dict(self) -> Dict[str, object]:
        return {
            "degree": self.degree,
            "max_interaction_order": self.max_interaction_order,
            "n_basis_terms": self.n_basis_terms,
            "in_sample_r2_noisy": round(self.in_sample_r2_noisy, 6),
            "in_sample_r2_heavy": round(self.in_sample_r2_heavy, 6),
            "oos_rmse": round(self.oos_rmse, 6),
            "oos_r2": round(self.oos_r2, 6),
            "oos_mae": round(self.oos_mae, 6),
            "oos_max_abs_rel_error": round(self.oos_max_abs_rel_error, 6),
            "overfit_gap": round(self.overfit_gap, 6),
        }


@dataclass
class QuintProxyValidationReport:
    """Full structured out-of-sample FIVE-DRIVER proxy-validation report."""

    config: QuintProxyValidationConfig
    basis_rows: List[QuintBasisDiagnostics]
    selected_degree: int
    selected_max_interaction_order: int
    selection_metric: str
    overfit_onset_terms: Optional[int]
    leakage: LeakageDiagnostics
    capital_comparison: CapitalComparison
    reproducibility_digest: str
    run_id: str
    duration_seconds: float
    verdict: str
    notes: List[str] = field(default_factory=list)
    audit_entry_id: Optional[str] = None

    def selected_row(self) -> QuintBasisDiagnostics:
        return next(
            r for r in self.basis_rows
            if r.degree == self.selected_degree
            and r.max_interaction_order == self.selected_max_interaction_order
        )

    def to_dict(self) -> Dict[str, object]:
        return {
            "run_id": self.run_id,
            "verdict": self.verdict,
            "drivers": [
                "short_rate", "equity_level", "credit_spread",
                "lapse_behaviour", "mortality_trend",
            ],
            "selected_degree": self.selected_degree,
            "selected_max_interaction_order": self.selected_max_interaction_order,
            "selection_metric": self.selection_metric,
            "overfit_onset_terms": self.overfit_onset_terms,
            "selected_row": self.selected_row().to_dict(),
            "basis_rows": [r.to_dict() for r in self.basis_rows],
            "leakage": self.leakage.to_dict(),
            "capital_comparison": self.capital_comparison.to_dict(),
            "reproducibility_digest": self.reproducibility_digest,
            "duration_seconds": round(self.duration_seconds, 4),
            "config": self.config.to_dict(),
            "notes": list(self.notes),
            "audit_entry_id": self.audit_entry_id,
            "standards": [
                "SOA ASOP 7 §3.3",
                "SOA ASOP 25 §3.3",
                "SOA ASOP 56 §3.5",
                "SOA ASOP 56 §3.1.3",
                "IA TAS M §3.6",
                "IA TAS M §3.2",
                "IFoA proxy-modelling working party",
                "Lee & Carter (1992)",
                "Longstaff & Schwartz (2001)",
                "Duffie & Singleton (1999)",
                "Cox-Ingersoll-Ross (1985)",
            ],
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True)


@dataclass
class _FittedQuintSurface:
    beta: np.ndarray
    centers: np.ndarray
    scales: np.ndarray
    degree: int
    max_interaction_order: int
    in_sample_r2_noisy: float

    def predict(self, X: np.ndarray) -> np.ndarray:
        X = np.asarray(X, dtype=float)
        if X.ndim == 1:
            X = X.reshape(1, -1)
        Xs = (X - self.centers) / self.scales
        return _quint_poly_basis(Xs, self.degree, self.max_interaction_order) @ self.beta


def _fit_quint_surface(
    fit_X: np.ndarray, fit_y: np.ndarray, degree: int, max_interaction_order: int
) -> _FittedQuintSurface:
    """Least-squares fit of the quintivariate ``(degree, max_int)`` surface.

    Mirrors :meth:`FiveDriverLSMCProxyEngine.fit_and_run` exactly (same
    centring/scaling and ``np.linalg.lstsq``) but takes the fitting data as
    arguments so every basis is fitted on the *same* states + payoffs.
    """
    centers = fit_X.mean(axis=0)
    scales = fit_X.std(axis=0, ddof=0)
    scales = np.where(scales > 0, scales, 1.0)
    Xs = (fit_X - centers) / scales
    design = _quint_poly_basis(Xs, degree, max_interaction_order)
    beta, _resid, _rank, _sv = np.linalg.lstsq(design, fit_y, rcond=None)
    y_hat = design @ beta
    ss_res = float(np.sum((fit_y - y_hat) ** 2))
    ss_tot = float(np.sum((fit_y - fit_y.mean()) ** 2)) or 1.0
    return _FittedQuintSurface(
        beta=beta, centers=centers, scales=scales, degree=int(degree),
        max_interaction_order=int(max_interaction_order),
        in_sample_r2_noisy=1.0 - ss_res / ss_tot,
    )


class FiveDriverProxyValidator:
    """Orchestrate fit / hold-out / basis-selection for the 5-driver proxy.

    Owns the product and the HW1F / GBM / CIR++ / OU-lapse / OU-mortality /
    correlation / exposure assumptions; a single :meth:`validate` call runs the
    whole disjoint-seed hold-out workflow over the ``(degree,
    max_interaction_order)`` grid and returns a :class:`QuintProxyValidationReport`.

    SOA ASOP 7 §3.3; ASOP 25 §3.3; ASOP 56 §3.5; IA TAS M §3.6; IFoA WP.
    """

    def __init__(
        self,
        product: ParEndowmentProduct,
        hw_params: Optional[HullWhiteParams] = None,
        gbm_params: Optional[GBMParams] = None,
        spread_params: Optional["object"] = None,
        lapse_params: Optional[LapseBehaviourParams] = None,
        mortality_params: Optional[MortalityTrendParams] = None,
        correlation: Optional[FiveDriverCorrelation] = None,
        initial_curve: Optional[RiskFreeCurve] = None,
        equity_guarantee: Optional[EquityGuaranteeSpec] = None,
        credit_exposure: Optional["object"] = None,
        lapse_exposure: Optional[LapseExposureSpec] = None,
        mortality_exposure: Optional[MortalityExposureSpec] = None,
        capital_horizon_months: int = DEFAULT_CAPITAL_HORIZON_MONTHS,
        confidence_level: float = DEFAULT_CONFIDENCE_LEVEL,
        outer_measure: Measure = Measure.P,
        annual_qx_fn: Optional[Callable] = None,
    ) -> None:
        if not (0 < capital_horizon_months < product.term_months):
            raise ValueError("capital_horizon_months must satisfy 0 < H < term_months")
        from par_model_v2.stochastic.credit_spread import CreditSpreadParams
        from par_model_v2.projection.multi_driver_capital_3d import CreditExposureSpec
        self.product = product
        self.hw_params = hw_params if hw_params is not None else HullWhiteParams()
        self.gbm_params = gbm_params if gbm_params is not None else GBMParams()
        self.spread_params = spread_params if spread_params is not None else CreditSpreadParams()
        self.lapse_params = lapse_params if lapse_params is not None else LapseBehaviourParams()
        self.mortality_params = (
            mortality_params if mortality_params is not None else MortalityTrendParams()
        )
        self.correlation = correlation if correlation is not None else FiveDriverCorrelation()
        self.initial_curve = initial_curve
        self.equity_guarantee = equity_guarantee or EquityGuaranteeSpec()
        self.credit_exposure = credit_exposure or CreditExposureSpec()
        self.lapse_exposure = lapse_exposure or LapseExposureSpec()
        self.mortality_exposure = mortality_exposure or MortalityExposureSpec()
        self.capital_horizon_months = int(capital_horizon_months)
        self.confidence_level = float(confidence_level)
        self.outer_measure = Measure(outer_measure)
        self.annual_qx_fn = annual_qx_fn

    @property
    def _rem(self) -> int:
        return self.product.term_months - self.capital_horizon_months

    def _states(self, n: int, seed: int) -> np.ndarray:
        return _outer_states_5d(
            n, self.capital_horizon_months, self.outer_measure,
            self.hw_params, self.gbm_params, self.spread_params, self.lapse_params,
            self.mortality_params, self.correlation, self.initial_curve, seed,
        )

    def _single_path_payoffs(self, states: np.ndarray, seed: int) -> np.ndarray:
        """One inner path per state -> noisy fit target (matches Task 3 engine)."""
        child = np.random.SeedSequence(seed + 1).spawn(len(states))
        y = np.empty(len(states), dtype=float)
        for i, (r, s, c, b, m) in enumerate(states):
            inner_seed = int(child[i].generate_state(1)[0])
            pvs = _inner_pathwise_pvs_5d(
                float(r), float(s), float(c), float(b), float(m), 1, self._rem,
                self.product, self.hw_params, self.gbm_params, self.spread_params,
                self.correlation, self.capital_horizon_months, inner_seed,
                self.equity_guarantee, self.credit_exposure, self.lapse_exposure,
                self.mortality_exposure, self.annual_qx_fn,
            )
            y[i] = float(pvs[0])
        return y

    def _heavy_targets(self, states: np.ndarray, n_inner: int, seed: int) -> np.ndarray:
        """High-accuracy nested E^Q[L | r,S,s,b,m] at each state (the OOS truth)."""
        child = np.random.SeedSequence(seed).spawn(len(states))
        truth = np.empty(len(states), dtype=float)
        for i, (r, s, c, b, m) in enumerate(states):
            inner_seed = int(child[i].generate_state(1)[0])
            pvs = _inner_pathwise_pvs_5d(
                float(r), float(s), float(c), float(b), float(m), n_inner, self._rem,
                self.product, self.hw_params, self.gbm_params, self.spread_params,
                self.correlation, self.capital_horizon_months, inner_seed,
                self.equity_guarantee, self.credit_exposure, self.lapse_exposure,
                self.mortality_exposure, self.annual_qx_fn,
            )
            truth[i] = float(pvs.mean())
        return truth

    def validate(
        self,
        config: Optional[QuintProxyValidationConfig] = None,
        nested_n_outer: int = 1_000,
        nested_n_inner: int = 128,
        governance_store: Optional["object"] = None,
        actor: str = "FiveDriverProxyValidator",
        phase: str = "Phase 19: Recovery Completion and Driver Expansion",
    ) -> QuintProxyValidationReport:
        cfg = config or QuintProxyValidationConfig()
        t0 = time.monotonic()
        run_id = "fv-proxyval-" + uuid.uuid4().hex[:8]
        notes: List[str] = []

        # --- 1. fitting data (one inner path each), seen ONLY by the fit -----
        fit_X = self._states(cfg.n_fit, cfg.fit_seed)
        fit_y = self._single_path_payoffs(fit_X, cfg.fit_seed)

        # --- 2. independent heavy hold-out (disjoint seed) ------------------
        val_X = self._states(cfg.n_validation, cfg.validation_seed)
        val_truth = self._heavy_targets(val_X, cfg.n_inner_heavy, cfg.validation_seed)

        # --- 3. held-in heavy subset (for the in/out skill gap) -------------
        n_in_heavy = min(cfg.n_insample_heavy, len(fit_X))
        insample_heavy_X = fit_X[:n_in_heavy]
        insample_heavy_truth = self._heavy_targets(
            insample_heavy_X, cfg.n_inner_heavy, cfg.insample_heavy_seed
        )

        # --- 4. leakage diagnostics -----------------------------------------
        leakage = _leakage_nd(fit_X, val_X, cfg.fit_seed, cfg.validation_seed)
        if not leakage.leakage_free:
            notes.append("WARNING: hold-out leakage check did not pass — review seeds.")

        # --- 5. basis sweep on shared fitting data --------------------------
        rows: List[QuintBasisDiagnostics] = []
        surfaces: Dict[Tuple[int, int], _FittedQuintSurface] = {}
        for (d, m) in cfg.basis_grid:
            surf = _fit_quint_surface(fit_X, fit_y, d, m)
            surfaces[(d, m)] = surf
            val_pred = surf.predict(val_X)
            in_pred = surf.predict(insample_heavy_X)
            resid = val_pred - val_truth
            denom = np.where(np.abs(val_truth) > 1e-9, np.abs(val_truth), 1.0)
            oos_rmse = float(np.sqrt(np.mean(resid ** 2)))
            oos_mae = float(np.mean(np.abs(resid)))
            oos_max_rel = float(np.max(np.abs(resid) / denom))
            oos_r2 = _r2(val_truth, val_pred)
            in_r2_heavy = _r2(insample_heavy_truth, in_pred)
            rows.append(QuintBasisDiagnostics(
                degree=d, max_interaction_order=m,
                n_basis_terms=_n_quint_basis_terms(d, m),
                in_sample_r2_noisy=surf.in_sample_r2_noisy,
                in_sample_r2_heavy=in_r2_heavy,
                oos_rmse=oos_rmse, oos_r2=oos_r2, oos_mae=oos_mae,
                oos_max_abs_rel_error=oos_max_rel,
                overfit_gap=in_r2_heavy - oos_r2,
            ))

        # --- 6. model selection by OOS skill --------------------------------
        if cfg.selection_metric == "oos_rmse":
            selected = min(rows, key=lambda r: r.oos_rmse)
        else:
            selected = max(rows, key=lambda r: r.oos_r2)
        selected_key = (selected.degree, selected.max_interaction_order)

        # overfit onset: order bases by complexity (#terms) and find the first
        # whose OOS RMSE rises above the previous (less complex) basis.
        ordered = sorted(rows, key=lambda r: (r.n_basis_terms, r.degree, r.max_interaction_order))
        overfit_onset_terms: Optional[int] = None
        for prev, cur in zip(ordered, ordered[1:]):
            if cur.oos_rmse > prev.oos_rmse * 1.001:
                overfit_onset_terms = cur.n_basis_terms
                break

        # --- 7. capital comparison at the selected basis -------------------
        chosen = surfaces[selected_key]
        eval_X = self._states(cfg.n_fit, cfg.fit_seed + 99)  # large cheap outer set
        proxy_l = chosen.predict(eval_X)
        proxy_capital = capital_metrics_from_liabilities(
            proxy_l, cfg.confidence_level, cfg.capital_horizon_months
        )
        nested_res = FiveDriverNestedEngine(
            self.product, self.hw_params, self.gbm_params, self.spread_params,
            self.lapse_params, self.mortality_params, self.correlation,
            self.initial_curve, self.equity_guarantee, self.credit_exposure,
            self.lapse_exposure, self.mortality_exposure,
            self.capital_horizon_months, cfg.confidence_level, self.outer_measure,
            self.annual_qx_fn,
        ).run(n_outer=nested_n_outer, n_inner=nested_n_inner, seed=cfg.fit_seed + 99)
        nested_capital = nested_res.capital

        def _rel(a: float, b: float) -> float:
            return abs(a - b) / (abs(b) if abs(b) > 1e-9 else 1.0)

        capital_cmp = CapitalComparison(
            proxy_capital=proxy_capital, nested_capital=nested_capital,
            var_rel_error=_rel(proxy_capital.var_liability, nested_capital.var_liability),
            es_rel_error=_rel(proxy_capital.es_liability, nested_capital.es_liability),
            scr_rel_error=_rel(proxy_capital.scr_proxy, nested_capital.scr_proxy),
            nested_n_outer=nested_n_outer, nested_n_inner=nested_n_inner,
        )

        # --- 8. reproducibility digest --------------------------------------
        digest = hashlib.sha256(
            np.round(np.concatenate([
                val_truth, chosen.beta,
                np.array([selected.degree, selected.max_interaction_order,
                          proxy_capital.var_liability, proxy_capital.es_liability],
                         dtype=float),
            ]), 9).tobytes()
        ).hexdigest()

        # --- 9. verdict -----------------------------------------------------
        verdict = self._verdict(selected, capital_cmp, leakage, notes)

        duration = time.monotonic() - t0

        audit_entry_id = None
        if governance_store is not None:
            try:
                from par_model_v2.governance.audit_trail import AuditEntry

                entry = AuditEntry.model_run(
                    actor=actor, phase=phase, run_id=run_id,
                    scenario_count=cfg.n_fit + cfg.n_validation * cfg.n_inner_heavy,
                    duration_seconds=round(duration, 4),
                    outcome="PASS" if verdict.startswith("PASS") else "PARTIAL",
                    files_changed=[
                        "par_model_v2/projection/multi_driver_proxy_validation.py"
                    ],
                    test_summary=(
                        "5D OOS proxy-val: selected (deg={}, max_int={}), OOS R2={:.4f}, "
                        "OOS RMSE={:.2f}, VaR rel err={:.2%}, leakage_free={}".format(
                            selected.degree, selected.max_interaction_order,
                            selected.oos_r2, selected.oos_rmse,
                            capital_cmp.var_rel_error, leakage.leakage_free)
                    ),
                )
                governance_store.audit_trail.append(entry)
                audit_entry_id = entry.entry_id
            except Exception as exc:  # pragma: no cover - governance optional
                notes.append("audit append skipped: {}".format(exc))

        return QuintProxyValidationReport(
            config=cfg, basis_rows=ordered,
            selected_degree=selected.degree,
            selected_max_interaction_order=selected.max_interaction_order,
            selection_metric=cfg.selection_metric,
            overfit_onset_terms=overfit_onset_terms,
            leakage=leakage, capital_comparison=capital_cmp,
            reproducibility_digest=digest, run_id=run_id, duration_seconds=duration,
            verdict=verdict, notes=notes, audit_entry_id=audit_entry_id,
        )

    @staticmethod
    def _verdict(
        selected: QuintBasisDiagnostics,
        capital_cmp: CapitalComparison,
        leakage: LeakageDiagnostics,
        notes: List[str],
    ) -> str:
        """Honest PASS / PARTIAL verdict against documented thresholds.

        Thresholds (educational): OOS R^2 >= 0.95, selected-basis VaR rel error
        <= 10%, hold-out leakage-free, and a bounded overfit gap (<= 0.05).
        """
        reasons: List[str] = []
        if selected.oos_r2 < 0.95:
            reasons.append("OOS R^2 {:.4f} < 0.95".format(selected.oos_r2))
        if capital_cmp.var_rel_error > 0.10:
            reasons.append("VaR rel error {:.2%} > 10%".format(capital_cmp.var_rel_error))
        if not leakage.leakage_free:
            reasons.append("hold-out not leakage-free")
        if selected.overfit_gap > 0.05:
            reasons.append("overfit gap {:.4f} > 0.05".format(selected.overfit_gap))
        if reasons:
            notes.append("verdict drivers: " + "; ".join(reasons))
            return "PARTIAL — " + "; ".join(reasons)
        return (
            "PASS — selected basis (deg {}, max_int {}) validated OOS "
            "(R^2={:.4f}, VaR rel err={:.2%}, leakage-free, overfit gap={:.4f})".format(
                selected.degree, selected.max_interaction_order, selected.oos_r2,
                capital_cmp.var_rel_error, selected.overfit_gap)
        )


def quint_proxy_validation_use_restrictions() -> Dict[str, object]:
    """Structured model-use restrictions for the FIVE-DRIVER OOS proxy validation."""
    base = proxy_validation_use_restrictions()
    base.update({
        "module": "par_model_v2/projection/multi_driver_proxy_validation.py::FiveDriverProxyValidator",
        "classification": "EDUCATIONAL ONLY — five-driver proxy-model validation evidence, not a regulatory sign-off",
        "what_it_validates": (
            "Out-of-sample skill of the Phase 19 Task 3 QUINTIVARIATE (rate + "
            "equity + credit-spread + lapse-behaviour + mortality-trend) LSMC "
            "capital surface against high-accuracy nested truth on an independent, "
            "disjoint-seed hold-out, with the basis (polynomial degree AND capped "
            "higher-order interaction order) selected by OOS error."
        ),
        "selection_caveat": (
            "Basis selection minimises OOS error over the swept (degree, "
            "max_interaction_order) grid only; the true optimum may lie outside "
            "the grid. Valid only over the fitted 5-D interquartile state region "
            "— extrapolation is unsupported."
        ),
        "residual_risk": (
            "FX and liquidity risks remain outside the proxy; lapse and mortality "
            "are each a single systemic OU index (no product / cohort / age "
            "structure); credit is a single systemic CIR++ spread. Parameters are "
            "illustrative placeholders; capital magnitudes are NOT calibrated."
        ),
        "standards": [
            "SOA ASOP 7 §3.3", "SOA ASOP 25 §3.3", "SOA ASOP 56 §3.5",
            "SOA ASOP 56 §3.1.3", "IA TAS M §3.6", "IA TAS M §3.2",
            "IFoA proxy-modelling working party", "Lee & Carter (1992)",
            "Longstaff & Schwartz (2001)", "Duffie & Singleton (1999)",
            "Cox-Ingersoll-Ross (1985)",
        ],
    })
    return base


def quint_proxy_validation_use_restrictions_json() -> str:
    return json.dumps(quint_proxy_validation_use_restrictions(), indent=2, sort_keys=True)


__all__ += [
    # --- Phase 19 Task 3: five-driver OOS proxy validation ---
    "DEFAULT_QUINT_BASIS_GRID",
    "QuintProxyValidationConfig",
    "QuintBasisDiagnostics",
    "QuintProxyValidationReport",
    "FiveDriverProxyValidator",
    "quint_proxy_validation_use_restrictions",
    "quint_proxy_validation_use_restrictions_json",
    "_fit_quint_surface",
]
