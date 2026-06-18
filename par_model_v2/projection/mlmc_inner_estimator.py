"""Multilevel Monte Carlo (MLMC) estimator for the nested SCR inner loop.

STATUS: stage-2 PROTOTYPE (W58, 2026-06-18). Estimator-only, ADDITIVE, OPT-IN.

This module is the implementation of the design-note-first plan in
``docs/research/MLMC_NESTED_LOOP_DESIGN_NOTE_20260618.md`` (Option 3 of the
model-improvement matrix). It is **not wired into the governed run path**: the
governed SCR continues to use the fixed single-level nested estimator
(``nested_stochastic_tvog.NestedStochasticTVOGEngine`` with ``n_inner=256``).
Selecting MLMC is an OPT-IN choice (``InnerEstimator``) that defaults to
``"fixed"``; making MLMC the default for any governed figure is a later,
owner-signed-off stage (stage 5 in the design note). Nothing here changes the
model form, the loss-distribution definition, the copula/aggregation, or the
governed headline ``39,975.654628199336``.

What it provides
----------------
* A faithful **nested** estimator of ``theta = E_X[ g(L(X)) ]`` where ``X`` is
  an outer (real-world) state, ``L(x) = E^Q[ inner PV | x ]`` is the conditional
  liability, and ``g`` is an arbitrary outer functional (default identity; the
  governed SCR uses a nonlinear tail functional). Two interchangeable estimators:

  - :func:`nested_single_level` -- the current fixed-``n_inner`` estimator.
  - :func:`mlmc_nested` -- the telescoping multilevel estimator over a geometric
    inner-path ladder ``N_l = N0 * M**l`` with **antithetic** fine/coarse inner
    coupling, which leaves the estimand at the finest level identical to the
    single-level estimator at ``n_inner = N_L`` but reaches the same RMSE at
    lower inner-path cost.

* :func:`mlmc_optimal_allocation` -- the standard MLMC cost/variance optimal
  per-level path budget, returned as a diagnostic (the prototype runs a fixed,
  reproducible allocation; the diagnostic shows what an adaptive run would pick).

Design discipline: pure ``numpy`` (no scipy at import time), deterministic given
a seed, no I/O, no global state.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, List, Sequence

import numpy as np

InnerSampler = Callable[[float, int, np.random.Generator], np.ndarray]
OuterSampler = Callable[[np.random.Generator, int], np.ndarray]
Payoff = Callable[[np.ndarray], np.ndarray]

# "fixed" -> governed single-level nested estimator (default).
# "mlmc"  -> opt-in telescoping multilevel inner estimator (this module).
InnerEstimator = str  # Literal["fixed", "mlmc"]


def identity_payoff(y: np.ndarray) -> np.ndarray:
    """Linear outer functional -- no inner-sampling bias (mean liability)."""
    return np.asarray(y, dtype=float)


# ---------------------------------------------------------------------------
# Level ladder
# ---------------------------------------------------------------------------
def inner_path_ladder(n0: int, M: int, L: int) -> List[int]:
    """Geometric ladder ``N_l = n0 * M**l`` for ``l = 0..L`` (finest = N_L)."""
    if n0 < 1 or M < 2 or L < 0:
        raise ValueError("require n0>=1, M>=2, L>=0")
    return [int(n0 * M ** lvl) for lvl in range(L + 1)]


# ---------------------------------------------------------------------------
# Single-level (current governed-style) nested estimator
# ---------------------------------------------------------------------------
@dataclass
class NestedEstimate:
    estimate: float
    std_error: float
    n_outer: int
    n_inner: int
    inner_path_cost: int  # total inner valuations = n_outer * n_inner


def nested_single_level(
    outer_sampler: OuterSampler,
    inner_sampler: InnerSampler,
    *,
    payoff: Payoff = identity_payoff,
    n_outer: int,
    n_inner: int,
    rng: np.random.Generator,
) -> NestedEstimate:
    """Fixed-``n_inner`` nested estimator of ``E_X[g(L_{n_inner}(X))]``.

    Mirrors the governed estimator: each outer state ``x_i`` is re-valued with
    ``n_inner`` inner paths; ``L_{n_inner}(x_i)`` is their sample mean; the outer
    estimate is the sample mean of ``g(L_{n_inner}(x_i))``.
    """
    xs = np.asarray(outer_sampler(rng, n_outer), dtype=float)
    g_vals = np.empty(xs.shape[0], dtype=float)
    for i, x in enumerate(xs):
        inner = np.asarray(inner_sampler(float(x), int(n_inner), rng), dtype=float)
        g_vals[i] = float(payoff(np.array([inner.mean()]))[0])
    est = float(g_vals.mean())
    se = float(g_vals.std(ddof=1) / np.sqrt(len(g_vals))) if len(g_vals) > 1 else 0.0
    return NestedEstimate(est, se, int(len(xs)), int(n_inner),
                          int(len(xs)) * int(n_inner))


# ---------------------------------------------------------------------------
# MLMC telescoping nested estimator
# ---------------------------------------------------------------------------
@dataclass
class MLMCLevelStat:
    level: int
    n_inner_fine: int
    n_inner_coarse: int
    n_outer: int
    mean_diff: float        # E[ g(L_fine) - g(L_coarse) ] estimate at this level
    var_diff: float         # variance of the per-outer difference
    inner_path_cost: int    # inner valuations spent at this level


@dataclass
class MLMCEstimate:
    estimate: float
    std_error: float
    ladder: List[int]
    levels: List[MLMCLevelStat] = field(default_factory=list)
    inner_path_cost: int = 0

    def summary(self) -> dict:
        return {
            "estimate": self.estimate,
            "std_error": self.std_error,
            "ladder": list(self.ladder),
            "inner_path_cost": self.inner_path_cost,
            "levels": [
                {
                    "level": s.level,
                    "n_inner_fine": s.n_inner_fine,
                    "n_inner_coarse": s.n_inner_coarse,
                    "n_outer": s.n_outer,
                    "mean_diff": s.mean_diff,
                    "var_diff": s.var_diff,
                    "inner_path_cost": s.inner_path_cost,
                }
                for s in self.levels
            ],
        }


def _antithetic_coarse(inner: np.ndarray, M: int, payoff: Payoff) -> float:
    """Antithetic coarse estimate from the SAME fine draws.

    Splits the ``N_fine`` inner draws into ``M`` disjoint sub-samples of size
    ``N_fine/M`` and averages ``g`` of each sub-mean. Coupling the coarse level
    to the fine draws is what shrinks ``Var[g(L_fine) - g(L_coarse)]`` for smooth
    ``g`` (Giles/antithetic nested MLMC).
    """
    n_fine = inner.shape[0]
    sub = n_fine // M
    parts = inner[: sub * M].reshape(M, sub)
    sub_means = parts.mean(axis=1)
    return float(payoff(sub_means).mean())


def mlmc_nested(
    outer_sampler: OuterSampler,
    inner_sampler: InnerSampler,
    *,
    payoff: Payoff = identity_payoff,
    n0: int = 16,
    M: int = 2,
    L: int = 4,
    n_outer_per_level: Sequence[int] | int = 4000,
    rng: np.random.Generator,
    antithetic: bool = True,
) -> MLMCEstimate:
    """Telescoping multilevel estimator of ``E_X[g(L_{N_L}(X))]``.

    ``E[g(L_{N_L})] = E[g(L_{N_0})] + sum_{l=1}^{L} E[g(L_{N_l}) - g(L_{N_{l-1}})]``

    The base level (l=0) is a single-level estimate at ``N_0``; each correction
    level ``l`` draws fresh outer states, evaluates ``N_l`` inner paths once, and
    forms the coupled difference ``g(L_{N_l}) - g(L_{N_{l-1}})`` where the coarse
    term reuses the fine draws antithetically. The finest level ``N_L`` equals the
    single-level benchmark's ``n_inner``, so the two estimators share an estimand.
    """
    ladder = inner_path_ladder(n0, M, L)
    if isinstance(n_outer_per_level, int):
        n_outer_per_level = [n_outer_per_level] * (L + 1)
    if len(n_outer_per_level) != L + 1:
        raise ValueError("n_outer_per_level must have length L+1")

    levels: List[MLMCLevelStat] = []
    total_estimate = 0.0
    total_var_of_mean = 0.0
    total_cost = 0

    # Base level l=0 : plain single-level estimate at N_0.
    n_out0 = int(n_outer_per_level[0])
    xs0 = np.asarray(outer_sampler(rng, n_out0), dtype=float)
    g0 = np.empty(xs0.shape[0])
    for i, x in enumerate(xs0):
        inner = np.asarray(inner_sampler(float(x), ladder[0], rng), dtype=float)
        g0[i] = float(payoff(np.array([inner.mean()]))[0])
    mean0 = float(g0.mean())
    var0 = float(g0.var(ddof=1)) if len(g0) > 1 else 0.0
    cost0 = n_out0 * ladder[0]
    total_estimate += mean0
    total_var_of_mean += var0 / max(len(g0), 1)
    total_cost += cost0
    levels.append(MLMCLevelStat(0, ladder[0], 0, n_out0, mean0, var0, cost0))

    # Correction levels l=1..L : coupled fine/coarse differences.
    for lvl in range(1, L + 1):
        n_fine = ladder[lvl]
        n_coarse = ladder[lvl - 1]
        n_out = int(n_outer_per_level[lvl])
        xs = np.asarray(outer_sampler(rng, n_out), dtype=float)
        diffs = np.empty(xs.shape[0])
        for i, x in enumerate(xs):
            inner = np.asarray(inner_sampler(float(x), n_fine, rng), dtype=float)
            g_fine = float(payoff(np.array([inner.mean()]))[0])
            if antithetic:
                g_coarse = _antithetic_coarse(inner, M, payoff)
            else:
                inner_c = np.asarray(
                    inner_sampler(float(x), n_coarse, rng), dtype=float)
                g_coarse = float(payoff(np.array([inner_c.mean()]))[0])
            diffs[i] = g_fine - g_coarse
        mean_d = float(diffs.mean())
        var_d = float(diffs.var(ddof=1)) if len(diffs) > 1 else 0.0
        cost = n_out * n_fine  # coarse reuses fine draws (antithetic)
        if not antithetic:
            cost += n_out * n_coarse
        total_estimate += mean_d
        total_var_of_mean += var_d / max(len(diffs), 1)
        total_cost += cost
        levels.append(
            MLMCLevelStat(lvl, n_fine, n_coarse, n_out, mean_d, var_d, cost))

    return MLMCEstimate(
        estimate=total_estimate,
        std_error=float(np.sqrt(total_var_of_mean)),
        ladder=ladder,
        levels=levels,
        inner_path_cost=int(total_cost),
    )


def mlmc_optimal_allocation(
    levels: Sequence[MLMCLevelStat], target_se: float
) -> List[int]:
    """Cost/variance-optimal outer counts per level for a target std-error.

    Standard MLMC allocation ``n_l proportional to sqrt(V_l / C_l)`` with the
    multiplier set so total variance of the mean meets ``target_se**2``. Returned
    as a diagnostic only (the prototype runs a fixed reproducible allocation).
    """
    if target_se <= 0:
        raise ValueError("target_se must be > 0")
    per_path_cost = []
    sqrt_vc = []
    for s in levels:
        c_l = s.inner_path_cost / max(s.n_outer, 1)   # cost per outer at level l
        v_l = max(s.var_diff, 0.0)
        per_path_cost.append(c_l)
        sqrt_vc.append(np.sqrt(v_l * c_l))
    s_sum = float(np.sum([np.sqrt(max(s.var_diff, 0.0) / max(c, 1e-12))
                          for s, c in zip(levels, per_path_cost)]))
    alloc = []
    for s, c in zip(levels, per_path_cost):
        v_l = max(s.var_diff, 0.0)
        n_l = (1.0 / target_se ** 2) * np.sqrt(v_l / max(c, 1e-12)) * s_sum
        alloc.append(int(np.ceil(max(n_l, 1.0))))
    return alloc


# ---------------------------------------------------------------------------
# Faithful adapter to the governed inner sampler (lazy import; heavy deps)
# ---------------------------------------------------------------------------
def governed_inner_sampler_factory(rem_months: int, h_month: int):
    """Build an :data:`InnerSampler` wrapping the governed inner valuation.

    Wraps ``nested_stochastic_tvog._inner_pathwise_pvs`` (the exact inner PV
    draw used by the governed estimator) so MLMC can be validated against the
    real model. Imported lazily because it pulls in the full HW/ESG stack.
    """
    from par_model_v2.projection.monthly_projection import ParEndowmentProduct
    from par_model_v2.stochastic.esg_process import HullWhiteParams
    from par_model_v2.projection.nested_stochastic_tvog import _inner_pathwise_pvs

    product = ParEndowmentProduct(
        term_years=10, issue_age=40, gender="M",
        sum_assured=100_000, annual_premium=6_000,
    )
    hw = HullWhiteParams()

    def sampler(x: float, n_inner: int, rng: np.random.Generator) -> np.ndarray:
        seed = int(rng.integers(0, 2 ** 31 - 1))
        return _inner_pathwise_pvs(
            float(x), int(n_inner), int(rem_months), product, hw,
            int(h_month), seed=seed)

    return sampler


# ---------------------------------------------------------------------------
# Stage-3 wiring helper: opt-in MLMC mean-liability diagnostics for the
# governed nested engine (ADDITIVE; never touches the governed SCR headline).
# ---------------------------------------------------------------------------
def engine_mean_liability_diagnostics(
    *,
    product,
    hw_params,
    capital_horizon_months: int,
    outer_measure,
    initial_curve=None,
    annual_qx_fn=None,
    n_inner: int = 256,
    seed: int = 42,
    fixed_mean_liability: float | None = None,
    fixed_n_outer: int | None = None,
    n0: int = 16,
    M: int = 2,
    L: int = 4,
    n_outer_per_level: Sequence[int] | None = None,
) -> dict:
    """Opt-in MLMC diagnostics for the governed nested engine (stage 3).

    Estimates the OUTER mean conditional liability ``theta = E_X[L(X)]`` -- the
    SINGLE estimand for which nested MLMC is unbiased (``L`` enters linearly, so
    the identity outer functional carries no inner-sampling bias). This is the
    governed run's ``conditional_liabilities.mean()``; the MLMC estimate of the
    SAME population quantity is returned alongside a matched-RMSE cost ratio.

    IMPORTANT: this is a DIAGNOSTIC sidecar. The governed SCR/VaR/ES headline is
    a *quantile* of the L(X) distribution, NOT its mean, so it is deliberately
    NOT computed here -- a quantile-MLMC headline is owner-signed-off stage 5.
    The governed engine continues to derive every capital figure from the fixed
    single-level estimator; selecting ``inner_estimator='mlmc'`` only attaches
    these mean-liability efficiency diagnostics.

    Returns a JSON-serialisable dict with the MLMC mean estimate, the fixed
    benchmark, the equivalence relative error (gate G1), the matched-RMSE
    speedup at ``N_L = n_inner`` (gate G3), the level ladder, and per-level
    stats. Deterministic given ``seed``.
    """
    # Lazy import to avoid a circular import at module load and to keep the
    # heavy HW/ESG stack out of pure-numpy import paths.
    from par_model_v2.projection.nested_stochastic_tvog import (
        _outer_states, _inner_pathwise_pvs,
    )

    rem = int(product.term_months) - int(capital_horizon_months)
    H = int(capital_horizon_months)

    def outer_sampler(rng: np.random.Generator, n: int) -> np.ndarray:
        child = int(rng.integers(0, 2 ** 31 - 1))
        return _outer_states(int(n), H, outer_measure, hw_params,
                             initial_curve, child)

    def inner_sampler(x: float, m: int, rng: np.random.Generator) -> np.ndarray:
        child = int(rng.integers(0, 2 ** 31 - 1))
        return _inner_pathwise_pvs(
            float(x), int(m), rem, product, hw_params, H, child, annual_qx_fn)

    if n_outer_per_level is None:
        # Geometric outer taper: more outer states at coarse (cheap) levels.
        base = max(int(fixed_n_outer or 256), 64)
        n_outer_per_level = [max(int(base // (M ** lvl)), 8) for lvl in range(L + 1)]

    ladder = inner_path_ladder(n0, M, L)
    if ladder[-1] != int(n_inner):
        # Keep the finest level aligned with the governed n_inner so the two
        # estimators share an estimand exactly.
        L_adj = 0
        nlad = [n0]
        while nlad[-1] < int(n_inner):
            nlad.append(nlad[-1] * M)
            L_adj += 1
        if nlad[-1] == int(n_inner):
            ladder = nlad
            L = L_adj
            if len(n_outer_per_level) != L + 1:
                base = max(int(fixed_n_outer or 256), 64)
                n_outer_per_level = [max(int(base // (M ** lvl)), 8)
                                     for lvl in range(L + 1)]

    rng_ml = np.random.default_rng(int(seed) ^ 0x5151)
    ml = mlmc_nested(outer_sampler, inner_sampler, payoff=identity_payoff,
                     n0=n0, M=M, L=L, n_outer_per_level=list(n_outer_per_level),
                     rng=rng_ml, antithetic=True)

    # Matched-RMSE single-level benchmark at the finest level (cost to reach the
    # MLMC std-error with a plain fixed-N_L nested run).
    rng_sl = np.random.default_rng(int(seed) ^ 0x2727)
    n_out_bench = max(int(fixed_n_outer or 256), 128)
    sl = nested_single_level(outer_sampler, inner_sampler,
                             payoff=identity_payoff, n_outer=n_out_bench,
                             n_inner=int(ladder[-1]), rng=rng_sl)
    var_g = (sl.std_error ** 2) * sl.n_outer  # per-outer variance of g(L_{N_L})
    if ml.std_error > 0:
        n_eq = var_g / (ml.std_error ** 2)            # outer count to match SE
        cost_eq_single = n_eq * ladder[-1]            # single-level inner cost
        speedup = float(cost_eq_single / max(ml.inner_path_cost, 1))
    else:
        speedup = float("inf")

    bench_mean = (float(fixed_mean_liability) if fixed_mean_liability is not None
                  else float(sl.estimate))
    denom = abs(bench_mean) if abs(bench_mean) > 1e-9 else 1.0
    rel_err = abs(ml.estimate - bench_mean) / denom

    return {
        "estimand": "outer_mean_conditional_liability_E_X[L(X)]",
        "finest_n_inner": int(ladder[-1]),
        "ladder": [int(v) for v in ladder],
        "n_outer_per_level": [int(v) for v in n_outer_per_level],
        "mlmc_mean_liability": float(ml.estimate),
        "mlmc_std_error": float(ml.std_error),
        "mlmc_inner_path_cost": int(ml.inner_path_cost),
        "fixed_mean_liability_benchmark": bench_mean,
        "single_level_benchmark_mean": float(sl.estimate),
        "single_level_benchmark_se": float(sl.std_error),
        "single_level_benchmark_n_outer": int(sl.n_outer),
        "equivalence_rel_err": float(rel_err),          # gate G1 (mean estimand)
        "matched_rmse_speedup_x": float(speedup),       # gate G3
        "levels": ml.summary()["levels"],
        "note": ("Diagnostic sidecar only; the governed SCR/VaR/ES headline is "
                 "a quantile and stays fixed single-level (stage-5 owner gate)."),
    }
