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


# ===========================================================================
# W64 (2026-06-19): Quantile / Expected-Shortfall tail-functional MLMC
# ---------------------------------------------------------------------------
# Stage-2 PROTOTYPE of the quantile/ES-aware MLMC estimator specified in
# ``docs/research/MLMC_QUANTILE_ESTIMATOR_DESIGN_NOTE_20260619.md``.
#
# The governed capital figure is NOT a mean: with confidence ``a`` (=0.995),
#     VaR_a = quantile_a(L),  ES_a = E[L | L >= VaR_a],  SCR = VaR_a - E[L].
# These are NONLINEAR functionals of the conditional-liability distribution, so
# finite inner sampling injects an O(1/N_inner) Gordy-Juneja bias the mean
# estimator (``identity_payoff``) cannot remove. This block adds a tail-aware
# estimator built on the Rockafellar-Uryasev (RU) representation
#     ES_a(L)  = min_q [ q + 1/(1-a) * E[(L - q)_+] ]
#     VaR_a(L) = argmin_q of the same objective
# whose outer functional ``(L-q)_+`` is Lipschitz (not discontinuous), giving a
# clean MLMC level-difference variance decay. A sigmoid-smoothed CDF inversion
# is provided as an INDEPENDENT validation oracle.
#
# DISCIPLINE (unchanged from the mean prototype): pure numpy, deterministic
# given a seed, no I/O, no global state, OPT-IN. Default everywhere stays
# ``"fixed"``; nothing here touches the governed SCR/VaR/ES headline
# ``39,975.654628199336`` -- that remains a fixed single-level figure until the
# owner-signed-off stage 5. ``L = 0`` (single base level at ``N_L``) is the
# EXACT single-level reduction: it routes through the same RU minimiser as
# :func:`nested_single_level_tail`, so the telescoping identity is bit-for-bit.
# ===========================================================================

DEFAULT_TAIL_CONFIDENCE = 0.995  # mirrors nested_stochastic_tvog.DEFAULT_CONFIDENCE_LEVEL


def _empirical_var_es(liabilities: np.ndarray, alpha: float) -> tuple:
    """Governed-style empirical VaR/ES (mirrors capital_metrics_from_liabilities).

    Upper-tail risk: ``VaR = np.quantile(L, alpha)``; ``ES = mean(L | L >= VaR)``.
    Returned as ``(var, es)``.
    """
    L = np.asarray(liabilities, dtype=float)
    var = float(np.quantile(L, alpha))
    tail = L[L >= var]
    es = float(tail.mean()) if tail.size else var
    return var, es


def ru_objective(liabilities: np.ndarray, q: float, alpha: float) -> float:
    """Rockafellar-Uryasev CVaR objective ``q + E[(L-q)_+]/(1-alpha)``.

    Convex and piecewise-linear in ``q``; its minimum value is ``ES_alpha`` and
    its minimiser is the ``alpha``-quantile (VaR). The outer integrand
    ``(L-q)_+`` is Lipschitz, which is what gives the MLMC level differences a
    well-behaved decaying variance (vs. a raw discontinuous indicator).
    """
    L = np.asarray(liabilities, dtype=float)
    return float(q + np.mean(np.maximum(L - q, 0.0)) / (1.0 - alpha))


def ru_minimise_var_es(liabilities: np.ndarray, alpha: float) -> tuple:
    """Exact empirical RU minimiser -> ``(VaR_ru, ES_ru)``.

    ``J(q) = q + E[(L-q)_+]/(1-alpha)`` is piecewise-linear convex with kinks at
    the order statistics, so its minimum is attained at one of the ``L_i``.
    Evaluates ``J`` at every breakpoint in ``O(n log n)`` via a suffix sum and
    returns the minimiser (VaR) and minimum (ES). Deterministic; ties resolve to
    the smallest minimising order statistic (np.argmin convention).
    """
    Ls = np.sort(np.asarray(liabilities, dtype=float))
    n = Ls.size
    if n == 0:
        raise ValueError("empty liability sample")
    # suffix[k] = sum_{i>=k} Ls[i]  (length n+1, suffix[n] = 0)
    suffix = np.zeros(n + 1, dtype=float)
    suffix[:n] = np.cumsum(Ls[::-1])[::-1]
    idx = np.arange(n)
    # mean((L-q)_+) at q = Ls[j] is (1/n) * sum_{i>j}(Ls[i]-Ls[j])
    tail_sum = suffix[1:] - Ls * (n - 1 - idx)        # sum_{i>j}(Ls[i]-Ls[j])
    J = Ls + (tail_sum / n) / (1.0 - alpha)
    k = int(np.argmin(J))
    return float(Ls[k]), float(J[k])


def smoothed_cdf_var(
    liabilities: np.ndarray,
    alpha: float,
    h: float,
    *,
    q_lo: float | None = None,
    q_hi: float | None = None,
    iters: int = 100,
) -> float:
    """Sigmoid-smoothed empirical-CDF inversion -> VaR oracle (design note 3b).

    ``F_h(q) = mean( sigmoid((q - L)/h) )`` is smooth and strictly increasing in
    ``q``; solving ``F_h(q) = alpha`` by bisection gives a VaR estimate whose
    ``O(h)`` smoothing bias -> 0 as ``h -> 0``. Independent of the RU path, so it
    serves as a cross-check oracle (it does not share RU's breakpoint logic).
    """
    L = np.asarray(liabilities, dtype=float)
    lo = float(L.min()) if q_lo is None else float(q_lo)
    hi = float(L.max()) if q_hi is None else float(q_hi)
    if h <= 0:
        raise ValueError("bandwidth h must be > 0")
    for _ in range(int(iters)):
        mid = 0.5 * (lo + hi)
        F = float(np.mean(1.0 / (1.0 + np.exp(-(mid - L) / h))))
        if F < alpha:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


@dataclass
class TailEstimate:
    """VaR / ES / SCR from a (single-level or MLMC) nested tail estimator."""
    var: float
    es: float
    scr: float
    mean_liability: float
    confidence_level: float
    n_outer: int
    n_inner: int            # finest inner count N_L
    method: str             # "fixed" | "mlmc"
    inner_path_cost: int
    var_empirical: float = float("nan")   # np.quantile-based (governed) VaR
    es_empirical: float = float("nan")    # tail-mean ES
    var_smoothed: float = float("nan")    # sigmoid-CDF oracle VaR
    ladder: List[int] = field(default_factory=list)
    levels: List[dict] = field(default_factory=list)

    def summary(self) -> dict:
        return {
            "method": self.method,
            "confidence_level": self.confidence_level,
            "var": self.var,
            "es": self.es,
            "scr": self.scr,
            "mean_liability": self.mean_liability,
            "var_empirical": self.var_empirical,
            "es_empirical": self.es_empirical,
            "var_smoothed": self.var_smoothed,
            "n_outer": self.n_outer,
            "n_inner": self.n_inner,
            "inner_path_cost": self.inner_path_cost,
            "ladder": list(self.ladder),
            "levels": list(self.levels),
        }


def _per_outer_mean_liabilities(
    outer_sampler: OuterSampler,
    inner_sampler: InnerSampler,
    n_outer: int,
    n_inner: int,
    rng: np.random.Generator,
) -> np.ndarray:
    """Conditional liabilities ``L_{n_inner}(x_i) = mean of n_inner inner draws``."""
    xs = np.asarray(outer_sampler(rng, n_outer), dtype=float)
    out = np.empty(xs.shape[0], dtype=float)
    for i, x in enumerate(xs):
        inner = np.asarray(inner_sampler(float(x), int(n_inner), rng), dtype=float)
        out[i] = float(inner.mean())
    return out


def nested_single_level_tail(
    outer_sampler: OuterSampler,
    inner_sampler: InnerSampler,
    *,
    alpha: float = DEFAULT_TAIL_CONFIDENCE,
    n_outer: int,
    n_inner: int,
    rng: np.random.Generator,
    smoothing_h: float | None = None,
) -> TailEstimate:
    """Fixed-``n_inner`` nested VaR/ES/SCR -- the governed-style benchmark.

    Computes conditional liabilities exactly as the governed engine, then
    reports BOTH the empirical (np.quantile / tail-mean) figures AND the RU
    minimiser figures. The RU figures are the canonical ``var``/``es`` so that
    the ``L=0`` MLMC reduction matches bit-for-bit; the empirical figures are
    retained for the governed-equivalence check (they agree to O(1/n_outer)).
    """
    L = _per_outer_mean_liabilities(outer_sampler, inner_sampler,
                                    int(n_outer), int(n_inner), rng)
    var_ru, es_ru = ru_minimise_var_es(L, alpha)
    var_emp, es_emp = _empirical_var_es(L, alpha)
    mean_l = float(L.mean())
    var_sm = (smoothed_cdf_var(L, alpha, smoothing_h)
              if smoothing_h is not None else float("nan"))
    return TailEstimate(
        var=var_ru, es=es_ru, scr=float(var_ru - mean_l), mean_liability=mean_l,
        confidence_level=float(alpha), n_outer=int(L.size), n_inner=int(n_inner),
        method="fixed", inner_path_cost=int(L.size) * int(n_inner),
        var_empirical=var_emp, es_empirical=es_emp, var_smoothed=var_sm,
        ladder=[int(n_inner)], levels=[],
    )


def mlmc_nested_tail(
    outer_sampler: OuterSampler,
    inner_sampler: InnerSampler,
    *,
    alpha: float = DEFAULT_TAIL_CONFIDENCE,
    n0: int = 16,
    M: int = 2,
    L: int = 4,
    n_outer_per_level: Sequence[int] | int = 4000,
    rng: np.random.Generator,
    antithetic: bool = True,
    n_grid: int = 2049,
    smoothing_h: float | None = None,
) -> TailEstimate:
    """Telescoping multilevel VaR / ES / SCR via the RU representation.

    Telescopes the Lipschitz RU objective expectation ``Phi(q) = E_X[(L(X)-q)_+]``
    AND the mean ``E_X[L(X)]`` over a geometric inner-path ladder
    ``N_l = n0*M**l`` (finest ``N_L``), then recovers
        VaR = argmin_q J(q),  ES = min_q J(q),  J(q) = q + Phi(q)/(1-alpha),
        SCR = VaR - E[L].
    Correction levels couple the fine estimator to its antithetic coarse half
    (the same mechanism as the mean prototype), which is what shrinks
    ``Var(P_l - P_{l-1})``.

    ``L == 0`` is the EXACT single-level reduction: it delegates to the same RU
    minimiser as :func:`nested_single_level_tail`, so with matched seeds the
    VaR/ES are bit-for-bit identical (the telescoping identity).
    """
    ladder = inner_path_ladder(n0, M, L)
    if isinstance(n_outer_per_level, int):
        n_outer_per_level = [n_outer_per_level] * (L + 1)
    if len(n_outer_per_level) != L + 1:
        raise ValueError("n_outer_per_level must have length L+1")

    # --- L == 0: exact single-level reduction (bit-for-bit identity) ---------
    if L == 0:
        sl = nested_single_level_tail(
            outer_sampler, inner_sampler, alpha=alpha,
            n_outer=int(n_outer_per_level[0]), n_inner=ladder[0], rng=rng,
            smoothing_h=smoothing_h,
        )
        sl.method = "mlmc"
        sl.ladder = list(ladder)
        sl.levels = [{
            "level": 0, "n_inner_fine": ladder[0], "n_inner_coarse": 0,
            "n_outer": int(n_outer_per_level[0]),
            "mean_diff": sl.mean_liability, "var_diff": 0.0,
            "inner_path_cost": sl.inner_path_cost,
        }]
        return sl

    # --- base level l = 0: plain estimate at N_0 -----------------------------
    n_out0 = int(n_outer_per_level[0])
    L0 = _per_outer_mean_liabilities(outer_sampler, inner_sampler,
                                     n_out0, ladder[0], rng)
    # q-grid bracketing the minimiser, derived from the base sample (fine, fixed).
    q_lo = float(np.quantile(L0, max(0.5, alpha - 0.10)))
    q_hi = float(L0.max())
    if not (q_hi > q_lo):
        q_hi = q_lo + max(abs(q_lo), 1.0) * 1e-6
    q_grid = np.linspace(q_lo, q_hi, int(n_grid))

    phi = np.maximum(L0[:, None] - q_grid[None, :], 0.0).mean(axis=0)  # Phi(q_grid)
    mean_est = float(L0.mean())
    total_cost = n_out0 * ladder[0]
    levels: List[dict] = [{
        "level": 0, "n_inner_fine": ladder[0], "n_inner_coarse": 0,
        "n_outer": n_out0, "mean_diff": mean_est,
        "var_diff": float(L0.var(ddof=1)) if L0.size > 1 else 0.0,
        "inner_path_cost": n_out0 * ladder[0],
    }]

    # --- correction levels l = 1..L : coupled fine/coarse differences --------
    for lvl in range(1, L + 1):
        n_fine = ladder[lvl]
        n_coarse = ladder[lvl - 1]
        n_out = int(n_outer_per_level[lvl])
        xs = np.asarray(outer_sampler(rng, n_out), dtype=float)
        phi_diff = np.zeros_like(q_grid)
        mean_diff_acc = 0.0
        sub = n_fine // M
        for x in xs:
            inner = np.asarray(inner_sampler(float(x), n_fine, rng), dtype=float)
            fine_mean = float(inner.mean())
            if antithetic:
                submeans = inner[: sub * M].reshape(M, sub).mean(axis=1)
            else:
                inner_c = np.asarray(
                    inner_sampler(float(x), n_coarse, rng), dtype=float)
                submeans = np.array([inner_c.mean()])
            coarse_mean = float(submeans.mean())
            obj_fine = np.maximum(fine_mean - q_grid, 0.0)
            obj_coarse = np.maximum(
                submeans[:, None] - q_grid[None, :], 0.0).mean(axis=0)
            phi_diff += (obj_fine - obj_coarse)
            mean_diff_acc += (fine_mean - coarse_mean)
        phi += phi_diff / max(n_out, 1)
        mean_est += mean_diff_acc / max(n_out, 1)
        cost = n_out * n_fine + (0 if antithetic else n_out * n_coarse)
        total_cost += cost
        levels.append({
            "level": lvl, "n_inner_fine": n_fine, "n_inner_coarse": n_coarse,
            "n_outer": n_out, "mean_diff": float(mean_diff_acc / max(n_out, 1)),
            "var_diff": float(np.nan), "inner_path_cost": int(cost),
        })

    # --- recover VaR/ES from the telescoped RU objective ---------------------
    J = q_grid + phi / (1.0 - alpha)
    k = int(np.argmin(J))
    var = float(q_grid[k])
    es = float(J[k])
    var_sm = (smoothed_cdf_var(L0, alpha, smoothing_h, q_lo=q_lo, q_hi=q_hi)
              if smoothing_h is not None else float("nan"))
    return TailEstimate(
        var=var, es=es, scr=float(var - mean_est), mean_liability=float(mean_est),
        confidence_level=float(alpha), n_outer=int(n_out0), n_inner=int(ladder[-1]),
        method="mlmc", inner_path_cost=int(total_cost),
        var_empirical=float("nan"), es_empirical=float("nan"), var_smoothed=var_sm,
        ladder=list(ladder), levels=levels,
    )
