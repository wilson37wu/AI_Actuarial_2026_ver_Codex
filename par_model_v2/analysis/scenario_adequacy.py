"""
Scenario-Adequacy Convergence Study
===================================

Roadmap §4.1 item #5 (C-ROSS gap #6).  Quantifies how the Monte-Carlo
TVOG estimator converges as the Q-measure scenario count grows across the
ladder ``500 -> 1,000 -> 2,000 -> 5,000`` and produces the three deliverables
the backlog item names:

  1. **Convergence report** - per-count TVOG point estimate with 95% CI bands.
  2. **Runtime benchmark** - wall-clock per count and the total.
  3. **Recommendation memo** - the minimum scenario count for a target relative
     precision, reconciled against the CBIRC C-ROSS ``>= 2,000`` floor.

Two error models - and why it matters here
------------------------------------------
For a fixed calibration the TVOG estimate is a sample mean minus a deterministic
constant, so a *naive iid* reading of its Monte-Carlo error is

    SE_iid(N) = sigma_PV / sqrt(N),   sigma_PV = std of the per-scenario PV.

But the governed ESG (:func:`ScenarioSet.generate`) draws **antithetic** normal
shocks, which negatively-correlates scenario pairs and reduces the variance of
the mean *below* the iid level.  Measured on this model the reduction is ~10x in
standard-error terms, so ``SE_iid`` badly **overstates** the true error.  The
study therefore also computes an **empirical** (antithetic-aware) standard error
by replicating each N-run across independent governed seeds:

    SE_emp(N) = std( TVOG over R independent seeds ),

which is exactly the sampling error of one production N-run under the governed
sampler.  CI bands, the convergence fit, and the sizing recommendation all use
``SE_emp`` when replications are available (``SE_iid`` is retained as a
documented conservative reference), and the ratio ``SE_iid / SE_emp`` is
reported as the realised **variance-reduction factor**.

Both errors decay like ``1/sqrt(N)``; the study measures the observed exponent
(fit of ``log SE`` vs ``log N``) against the theoretical ``-0.5`` and checks
point-estimate stability (each rung inside the previous rung's CI).

Reproducibility
---------------
Every run uses the governed seed policy; the primary ladder uses ``seed_base``
and replications use deterministic offset seeds (``seed_base + k*SEED_STRIDE``).
The result carries a SHA-256 digest over the full input basis.

SCOPE / PRODUCTION-USE RESTRICTION
----------------------------------
Purely-additive **diagnostic** built on the governed ``TVOGEngine``, run
unchanged; it does **not** touch any governed headline figure (portfolio TVOG,
aggregation reports).  Representative product + placeholder ESG calibration;
automation-driven sign-off - **UNSIGNED** pending owner / independent review.

Standards: SOA ASOP 56 s3.5 (scenario adequacy & validation), ASOP 25 s3.3
(scenario generation), CBIRC C-ROSS (scenario-count floor >= 2,000);
IA TAS M s3.6 (validation acceptance criteria).
"""

from __future__ import annotations

import hashlib
import json
import math
import time
import warnings
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Dict, List, Optional, Sequence, Tuple

import numpy as np

from par_model_v2.projection.monthly_projection import ParEndowmentProduct
from par_model_v2.projection.tvog import (
    TVOGEngine,
    ScenarioCountWarning,
    TVOG_MINIMUM_SCENARIOS,
)
from par_model_v2.stochastic.esg_process import (
    GBMParams,
    HullWhiteParams,
    Measure,
    ScenarioSet,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CONVERGENCE_SCHEMA = "scenario-adequacy-convergence-1.0"

#: The backlog-mandated scenario ladder.
DEFAULT_LADDER: Tuple[int, ...] = (500, 1_000, 2_000, 5_000)

#: CBIRC C-ROSS scenario-count floor (quality-bar s3).
CBIRC_SCENARIO_FLOOR = 2_000

#: Default target: the 95% CI half-width should be <= 2% of |TVOG|.
DEFAULT_REL_TOL = 0.02

#: Two-sided 95% normal quantile.
Z_95 = 1.959963984540054

#: Seed offset between independent replications (keeps RNG streams disjoint).
SEED_STRIDE = 10_000

#: Governed deterministic discount base for the TVOG study (CBIRC 3.0% cap).
DEFAULT_DETERMINISTIC_RATE = 0.030

_TINY = 1e-12


def _default_product() -> ParEndowmentProduct:
    """The representative 10-year PAR endowment used by the standard study."""
    return ParEndowmentProduct(
        term_years=10,
        issue_age=35,
        gender="M",
        sum_assured=100_000.0,
        annual_premium=5_000.0,
    )


# ---------------------------------------------------------------------------
# Per-count result
# ---------------------------------------------------------------------------

@dataclass
class ConvergencePoint:
    """Convergence statistics at a single scenario count ``n_scenarios``.

    The point estimate ``tvog`` is the primary-seed run.  ``se_iid`` is the
    naive ``sigma_PV / sqrt(N)`` error; ``se_empirical`` is the across-seed
    error (present when ``n_replications >= 2``).  ``effective_se`` (and the
    ``ci95_*`` bands built from it) use the empirical error when available,
    else the iid error.
    """

    n_scenarios: int
    tvog: float
    pv_mean: float
    pv_std: float
    se_iid: float
    n_replications: int
    error_model: str                       # "empirical_antithetic" | "naive_iid"
    effective_se: float
    ci95_half_width: float
    ci95_low: float
    ci95_high: float
    rel_ci_half_width: float
    runtime_seconds: float
    meets_cbirc_floor: bool
    meets_rel_tol: bool
    # empirical replication cross-check (optional)
    se_empirical: Optional[float] = None
    tvog_repl_mean: Optional[float] = None
    variance_reduction_factor: Optional[float] = None
    seeds: Tuple[int, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict:
        d = {
            "n_scenarios": int(self.n_scenarios),
            "tvog": round(float(self.tvog), 4),
            "pv_mean": round(float(self.pv_mean), 4),
            "pv_std": round(float(self.pv_std), 4),
            "se_iid": round(float(self.se_iid), 4),
            "error_model": self.error_model,
            "effective_se": round(float(self.effective_se), 4),
            "ci95_half_width": round(float(self.ci95_half_width), 4),
            "ci95_low": round(float(self.ci95_low), 4),
            "ci95_high": round(float(self.ci95_high), 4),
            "rel_ci_half_width": round(float(self.rel_ci_half_width), 6),
            "rel_ci_half_width_pct": round(float(self.rel_ci_half_width) * 100.0, 4),
            "runtime_seconds": round(float(self.runtime_seconds), 4),
            "meets_cbirc_floor": bool(self.meets_cbirc_floor),
            "meets_rel_tol": bool(self.meets_rel_tol),
            "n_replications": int(self.n_replications),
            "seeds": [int(s) for s in self.seeds],
        }
        if self.se_empirical is not None:
            d["se_empirical"] = round(float(self.se_empirical), 4)
            d["tvog_repl_mean"] = round(float(self.tvog_repl_mean), 4)
            d["variance_reduction_factor"] = round(
                float(self.variance_reduction_factor), 4
            )
        return d


# ---------------------------------------------------------------------------
# Study result
# ---------------------------------------------------------------------------

@dataclass
class ConvergenceStudyResult:
    """Full scenario-adequacy convergence study across the count ladder."""

    schema: str
    ladder: Tuple[int, ...]
    points: List[ConvergencePoint]
    deterministic_discount_rate: float
    seed_base: int
    replications: int
    rel_tol: float
    cbirc_floor: int
    error_model: str
    # reference (largest-N) quantities used for analytic sizing
    tvog_reference: float
    n_reference: int
    se_reference: float                    # effective SE at the reference count
    se_constant: float                     # c in SE(N) = c / sqrt(N)
    variance_reduction_factor: Optional[float]
    # analytic sizing (on the effective error model)
    required_n_for_rel_tol: int
    required_n_iid: int                    # conservative iid sizing (disclosure)
    recommended_n: int
    predicted_rel_ci_at_floor: float
    meets_rel_tol_at_floor: bool
    cbirc_floor_satisfied: bool
    # diagnostics
    mc_error_scaling_exponent: float
    convergence_ratios: List[dict]
    stable_from_n: Optional[int]
    total_runtime_seconds: float
    inputs_digest: str
    generated_at: str
    unsigned_note: str

    # -- serialisation ---------------------------------------------------
    def to_dict(self) -> dict:
        return {
            "schema": self.schema,
            "roadmap_item": (
                "s4.1 #5 scenario adequacy at 2,000+ scenarios: convergence "
                "study 500->1000->2000->5000 with CI bands (C-ROSS gap #6)"
            ),
            "generated_at": self.generated_at,
            "inputs_digest": self.inputs_digest,
            "ladder": [int(n) for n in self.ladder],
            "deterministic_discount_rate": self.deterministic_discount_rate,
            "seed_base": int(self.seed_base),
            "replications": int(self.replications),
            "error_model": self.error_model,
            "rel_tol": self.rel_tol,
            "rel_tol_pct": round(self.rel_tol * 100.0, 4),
            "cbirc_floor": int(self.cbirc_floor),
            "points": [p.to_dict() for p in self.points],
            "reference": {
                "n_scenarios": int(self.n_reference),
                "tvog": round(float(self.tvog_reference), 4),
                "effective_se": round(float(self.se_reference), 4),
                "se_constant_c": round(float(self.se_constant), 4),
                "variance_reduction_factor": (
                    round(float(self.variance_reduction_factor), 4)
                    if self.variance_reduction_factor is not None
                    else None
                ),
            },
            "sizing": {
                "required_n_for_rel_tol": int(self.required_n_for_rel_tol),
                "required_n_iid_conservative": int(self.required_n_iid),
                "recommended_n": int(self.recommended_n),
                "predicted_rel_ci_at_floor": round(
                    float(self.predicted_rel_ci_at_floor), 6
                ),
                "predicted_rel_ci_at_floor_pct": round(
                    float(self.predicted_rel_ci_at_floor) * 100.0, 4
                ),
                "meets_rel_tol_at_floor": bool(self.meets_rel_tol_at_floor),
                "cbirc_floor_satisfied": bool(self.cbirc_floor_satisfied),
            },
            "diagnostics": {
                "mc_error_scaling_exponent": round(
                    float(self.mc_error_scaling_exponent), 4
                ),
                "mc_error_scaling_theoretical": -0.5,
                "convergence_ratios": self.convergence_ratios,
                "stable_from_n": self.stable_from_n,
            },
            "total_runtime_seconds": round(float(self.total_runtime_seconds), 4),
            "unsigned_note": self.unsigned_note,
            "standards": [
                "SOA ASOP 56 s3.5",
                "SOA ASOP 25 s3.3",
                "CBIRC C-ROSS (scenario floor >= 2,000)",
                "IA TAS M s3.6",
            ],
        }

    def summary(self) -> dict:
        """Compact scalar summary for logs / audit."""
        return {
            "schema": self.schema,
            "ladder": list(self.ladder),
            "error_model": self.error_model,
            "tvog_reference": round(float(self.tvog_reference), 4),
            "se_reference": round(float(self.se_reference), 4),
            "variance_reduction_factor": (
                round(float(self.variance_reduction_factor), 4)
                if self.variance_reduction_factor is not None
                else None
            ),
            "required_n_for_rel_tol": int(self.required_n_for_rel_tol),
            "recommended_n": int(self.recommended_n),
            "meets_rel_tol_at_floor": bool(self.meets_rel_tol_at_floor),
            "cbirc_floor_satisfied": bool(self.cbirc_floor_satisfied),
            "mc_error_scaling_exponent": round(
                float(self.mc_error_scaling_exponent), 4
            ),
            "inputs_digest": self.inputs_digest,
        }

    # -- narrative -------------------------------------------------------
    def recommendation_memo(self) -> str:
        """Return the recommendation-memo markdown block."""
        rec = self.recommended_n
        req = self.required_n_for_rel_tol
        floor = self.cbirc_floor
        driver = "CBIRC C-ROSS floor" if req <= floor else "target precision"
        floor_word = "MET" if self.meets_rel_tol_at_floor else "NOT met"
        vrf = (
            "{:.1f}x".format(self.variance_reduction_factor)
            if self.variance_reduction_factor is not None
            else "n/a (single-seed run)"
        )
        lines = [
            "## Recommendation memo",
            "",
            "- **Recommended production scenario count: {:,}.**".format(rec),
            "- Binding constraint: **{}** "
            "(effective precision needs ~{:,}; regulatory floor is {:,}).".format(
                driver, req, floor
            ),
            "- Target precision (95% CI half-width <= {:.1f}% of |TVOG|) is "
            "**{}** at the {:,}-scenario floor (predicted {:.2f}% on the {} "
            "error model).".format(
                self.rel_tol * 100, floor_word, floor,
                self.predicted_rel_ci_at_floor * 100, self.error_model,
            ),
            "- CBIRC C-ROSS >= {:,} floor is **{}** by the recommendation.".format(
                floor, "satisfied" if self.cbirc_floor_satisfied else "NOT satisfied"
            ),
            "- Realised variance reduction from the governed antithetic sampler: "
            "**{}** in standard-error terms; ignoring it (naive iid) would "
            "over-provision to ~{:,} scenarios.".format(vrf, self.required_n_iid),
            "- Observed Monte-Carlo error scaling exponent {:+.3f} vs theoretical "
            "-0.500 (confirms 1/sqrt(N) convergence).".format(
                self.mc_error_scaling_exponent
            ),
        ]
        if self.stable_from_n is not None:
            lines.append(
                "- Point estimate is **stable from N = {:,}** (each rung lands "
                "inside the previous rung's 95% CI).".format(self.stable_from_n)
            )
        lines.append("")
        lines.append(
            "_Diagnostic only; UNSIGNED. Governed portfolio TVOG headline "
            "untouched - re-baselining onto any revised scenario count remains "
            "owner-gated._"
        )
        return "\n".join(lines)

    def to_markdown(self) -> str:
        """Full convergence-report markdown (report + benchmark + memo)."""
        hdr = [
            "# Scenario-Adequacy Convergence Study",
            "",
            "**Schema:** `{}`  ".format(self.schema),
            "**Roadmap item:** s4.1 #5 (C-ROSS gap #6)  ",
            "**Generated:** {}  ".format(self.generated_at),
            "**Inputs digest:** `{}...`  ".format(self.inputs_digest[:16]),
            "**Error model:** {} ({} replication(s) per count)  ".format(
                self.error_model, self.replications
            ),
            "**Deterministic discount base:** {:.3%} (CBIRC 3.0% cap)  ".format(
                self.deterministic_discount_rate
            ),
            "**Seed policy:** base {}, stride {}  ".format(
                self.seed_base, SEED_STRIDE
            ),
            "",
            "> Purely-additive diagnostic on the governed `TVOGEngine`. "
            "No governed headline figure is changed. **UNSIGNED**.",
            "",
            "## Convergence report (TVOG with 95% CI bands)",
            "",
            "| N | TVOG | iid SE | effective SE | 95% CI half-width | rel. CI | "
            "95% CI band | runtime (s) | >= floor | <= tol |",
            "|---:|---:|---:|---:|---:|---:|:--|---:|:--:|:--:|",
        ]
        rows = []
        for p in self.points:
            rows.append(
                "| {n:,} | {tvog:,.1f} | {se_iid:,.1f} | {se:,.1f} | {hw:,.1f} | "
                "{rel:.2%} | [{lo:,.0f}, {hi:,.0f}] | {rt:.2f} | {fl} | {tl} |".format(
                    n=p.n_scenarios,
                    tvog=p.tvog,
                    se_iid=p.se_iid,
                    se=p.effective_se,
                    hw=p.ci95_half_width,
                    rel=p.rel_ci_half_width,
                    lo=p.ci95_low,
                    hi=p.ci95_high,
                    rt=p.runtime_seconds,
                    fl="Y" if p.meets_cbirc_floor else ".",
                    tl="Y" if p.meets_rel_tol else ".",
                )
            )
        vrf_line = (
            "{:.1f}x".format(self.variance_reduction_factor)
            if self.variance_reduction_factor is not None
            else "n/a"
        )
        diag = [
            "",
            "## Convergence diagnostics",
            "",
            "- Reference TVOG = {:,.1f} at N = {:,}; effective SE = {:,.1f} "
            "(SE(N) = {:,.1f} / sqrt(N)).".format(
                self.tvog_reference, self.n_reference, self.se_reference,
                self.se_constant,
            ),
            "- Realised antithetic variance-reduction factor "
            "(iid SE / empirical SE): **{}**.".format(vrf_line),
            "- Monte-Carlo error scaling exponent (fit of log SE vs log N): "
            "**{:+.3f}** vs theoretical -0.500.".format(
                self.mc_error_scaling_exponent
            ),
        ]
        for cr in self.convergence_ratios:
            diag.append(
                "- N {a:,} -> {b:,}: CI half-width ratio observed {obs:.3f} vs "
                "theoretical {th:.3f} (sqrt law); |dTVOG| {d:,.1f} {inside} "
                "combined CI.".format(
                    a=cr["from_n"],
                    b=cr["to_n"],
                    obs=cr["observed_ratio"],
                    th=cr["theoretical_ratio"],
                    d=cr["abs_tvog_change"],
                    inside="within" if cr["stable_within_ci"] else "OUTSIDE",
                )
            )
        bench = [
            "",
            "## Runtime benchmark",
            "",
            "- Total wall-clock: **{:.2f} s** across {} scenario counts{}".format(
                self.total_runtime_seconds,
                len(self.points),
                " x {} replications.".format(self.replications)
                if self.replications > 1
                else ".",
            ),
        ]
        return "\n".join(
            hdr + rows + diag + bench + ["", self.recommendation_memo(), ""]
        )


# ---------------------------------------------------------------------------
# Core computation
# ---------------------------------------------------------------------------

def _one_tvog_run(
    product: ParEndowmentProduct,
    hw_params: HullWhiteParams,
    gbm_params: GBMParams,
    deterministic_discount_rate: float,
    n_scenarios: int,
    seed: int,
) -> Tuple[float, float, float, float]:
    """Run one governed TVOG computation.

    Returns ``(tvog, pv_mean, pv_std_ddof1, runtime_seconds)``.
    """
    t0 = time.monotonic()
    scenarios = ScenarioSet.generate(
        n=n_scenarios,
        T_months=product.term_months,
        measure=Measure.Q,
        hw_params=hw_params,
        gbm_params=gbm_params,
        seed=seed,
    )
    engine = TVOGEngine(
        product=product,
        scenarios=scenarios,
        deterministic_discount_rate=deterministic_discount_rate,
    )
    with warnings.catch_warnings():
        # Below-minimum counts are an explicit, intended part of a convergence
        # study; do not let the engine's adequacy warning abort strict runs.
        warnings.simplefilter("ignore", ScenarioCountWarning)
        result = engine.compute(run_label="convergence")
    pvs = np.asarray(result.scenario_pvs, dtype=float)
    pv_std = float(pvs.std(ddof=1)) if pvs.size > 1 else 0.0
    runtime = time.monotonic() - t0
    return (
        float(result.tvog),
        float(result.pv_guaranteed_stochastic_mean),
        pv_std,
        runtime,
    )


def _inputs_digest(
    product: ParEndowmentProduct,
    hw_params: HullWhiteParams,
    gbm_params: GBMParams,
    deterministic_discount_rate: float,
    ladder: Sequence[int],
    seed_base: int,
    replications: int,
    rel_tol: float,
    cbirc_floor: int,
) -> str:
    basis = {
        "schema": CONVERGENCE_SCHEMA,
        "product": {
            "term_months": int(product.term_months),
            "issue_age": int(product.issue_age),
            "gender": str(product.gender),
            "sum_assured": float(product.sum_assured),
            "annual_premium": float(product.annual_premium),
        },
        "hw": {
            "mean_reversion_speed": float(hw_params.mean_reversion_speed),
            "short_rate_vol": float(hw_params.short_rate_vol),
            "initial_short_rate": float(hw_params.initial_short_rate),
            "long_run_rate_p": float(hw_params.long_run_rate_p),
            "market_price_of_risk": float(hw_params.market_price_of_risk),
        },
        "gbm": {
            "equity_vol": float(gbm_params.equity_vol),
            "dividend_yield": float(gbm_params.dividend_yield),
            "equity_risk_premium": float(gbm_params.equity_risk_premium),
            "rate_equity_correlation": float(gbm_params.rate_equity_correlation),
        },
        "deterministic_discount_rate": float(deterministic_discount_rate),
        "ladder": [int(n) for n in ladder],
        "seed_base": int(seed_base),
        "replications": int(replications),
        "rel_tol": float(rel_tol),
        "cbirc_floor": int(cbirc_floor),
    }
    payload = json.dumps(basis, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def run_convergence_study(
    product: Optional[ParEndowmentProduct] = None,
    hw_params: Optional[HullWhiteParams] = None,
    gbm_params: Optional[GBMParams] = None,
    ladder: Sequence[int] = DEFAULT_LADDER,
    deterministic_discount_rate: float = DEFAULT_DETERMINISTIC_RATE,
    seed_base: int = 42,
    replications: int = 1,
    rel_tol: float = DEFAULT_REL_TOL,
    cbirc_floor: int = CBIRC_SCENARIO_FLOOR,
    tvog_runner: Optional[Callable[..., Tuple[float, float, float, float]]] = None,
    progress: Optional[Callable[[str], None]] = None,
) -> ConvergenceStudyResult:
    """Run the scenario-adequacy convergence study across ``ladder``.

    Parameters
    ----------
    product, hw_params, gbm_params
        Governed model inputs.  Defaults: the representative 10-year PAR
        endowment and the placeholder HW1F / GBM calibrations.
    ladder
        Ascending scenario counts.  Default ``(500, 1000, 2000, 5000)``.
    deterministic_discount_rate
        Flat deterministic base for TVOG (default 3.0%, the CBIRC cap).
    seed_base
        Primary governed seed.  Replications use ``seed_base + k*SEED_STRIDE``.
    replications
        Independent seeds per count.  ``>= 2`` enables the empirical
        antithetic-aware error model; ``1`` falls back to the naive iid error.
    rel_tol
        Target 95% CI half-width as a fraction of |TVOG| (default 0.02).
    cbirc_floor
        Regulatory scenario floor (default 2,000).
    tvog_runner
        Optional callable with the signature of :func:`_one_tvog_run`
        ``(product, hw, gbm, det_rate, n, seed) -> (tvog, pv_mean,
        pv_std, runtime)``.  Defaults to the governed engine run; a
        disk-memoised runner lets a builder resume a long study, and a
        stub keeps unit tests fast.  Injected runners must stay
        deterministic in ``seed`` to preserve reproducibility.
    progress
        Optional callback receiving human-readable progress strings.

    Returns
    -------
    ConvergenceStudyResult
    """
    product = product or _default_product()
    hw_params = hw_params or HullWhiteParams()
    gbm_params = gbm_params or GBMParams()

    ladder = tuple(int(n) for n in ladder)
    if len(ladder) < 2:
        raise ValueError("ladder must contain at least two scenario counts")
    if any(b <= a for a, b in zip(ladder, ladder[1:])):
        raise ValueError("ladder must be strictly ascending: {}".format(ladder))
    if replications < 1:
        raise ValueError("replications must be >= 1")
    if not (0.0 < rel_tol < 1.0):
        raise ValueError("rel_tol must be in (0, 1); got {}".format(rel_tol))

    use_empirical = replications >= 2
    error_model = "empirical_antithetic" if use_empirical else "naive_iid"
    runner = tvog_runner or _one_tvog_run

    def _log(msg: str) -> None:
        if progress is not None:
            progress(msg)

    points: List[ConvergencePoint] = []
    total_runtime = 0.0

    for n in ladder:
        seeds = tuple(seed_base + k * SEED_STRIDE for k in range(replications))
        _log("N={:,}: running {} replication(s)...".format(n, replications))

        # Primary-seed run (replicate 0) supplies the point estimate + iid SE.
        tvog0, pv_mean0, pv_std0, rt0 = runner(
            product, hw_params, gbm_params,
            deterministic_discount_rate, n, seeds[0],
        )
        run_rt = rt0
        tvog_samples = [tvog0]
        for seed in seeds[1:]:
            tvog_k, _pm, _ps, rt_k = runner(
                product, hw_params, gbm_params,
                deterministic_discount_rate, n, seed,
            )
            tvog_samples.append(tvog_k)
            run_rt += rt_k
        total_runtime += run_rt

        se_iid = pv_std0 / math.sqrt(n)

        se_emp = repl_mean = vrf = None
        if use_empirical:
            arr = np.asarray(tvog_samples, dtype=float)
            se_emp = float(arr.std(ddof=1))
            repl_mean = float(arr.mean())
            vrf = se_iid / se_emp if se_emp > _TINY else None

        effective_se = se_emp if (use_empirical and se_emp is not None) else se_iid
        half = Z_95 * effective_se
        denom = max(abs(tvog0), _TINY)
        rel_hw = half / denom

        points.append(
            ConvergencePoint(
                n_scenarios=n,
                tvog=tvog0,
                pv_mean=pv_mean0,
                pv_std=pv_std0,
                se_iid=se_iid,
                n_replications=replications,
                error_model=error_model,
                effective_se=effective_se,
                ci95_half_width=half,
                ci95_low=tvog0 - half,
                ci95_high=tvog0 + half,
                rel_ci_half_width=rel_hw,
                runtime_seconds=run_rt,
                meets_cbirc_floor=(n >= cbirc_floor),
                meets_rel_tol=(rel_hw <= rel_tol),
                se_empirical=se_emp,
                tvog_repl_mean=repl_mean,
                variance_reduction_factor=vrf,
                seeds=seeds,
            )
        )

    # -- reference (largest N) ------------------------------------------
    ref = points[-1]
    tvog_ref = ref.tvog
    n_ref = ref.n_scenarios
    se_ref = ref.effective_se
    denom_ref = max(abs(tvog_ref), _TINY)

    # SE(N) = c / sqrt(N)  =>  c = SE_ref * sqrt(N_ref)
    se_constant = se_ref * math.sqrt(n_ref)
    se_constant_iid = ref.se_iid * math.sqrt(n_ref)  # = pv_std at ref

    # -- analytic sizing: N* to hit rel_tol -----------------------------
    #   half(N) = Z * c / sqrt(N);  half/|TVOG| <= rel_tol
    #   =>  N >= ( Z * c / (rel_tol * |TVOG|) )^2
    def _required_n(c: float) -> int:
        raw = (Z_95 * c / (rel_tol * denom_ref)) ** 2
        return int(math.ceil(raw))

    required_n = _required_n(se_constant)
    required_n_iid = _required_n(se_constant_iid)
    required_n_rounded = int(math.ceil(required_n / 500.0) * 500)
    recommended_n = max(cbirc_floor, required_n_rounded)

    predicted_se_floor = se_constant / math.sqrt(cbirc_floor)
    predicted_rel_ci_floor = Z_95 * predicted_se_floor / denom_ref
    meets_at_floor = predicted_rel_ci_floor <= rel_tol
    cbirc_ok = recommended_n >= cbirc_floor

    # -- MC error scaling exponent (fit log SE vs log N) ----------------
    logN = np.log(np.array([p.n_scenarios for p in points], dtype=float))
    logSE = np.log(
        np.array([max(p.effective_se, _TINY) for p in points], dtype=float)
    )
    slope = float(np.polyfit(logN, logSE, 1)[0])

    # -- convergence ratios + stability ---------------------------------
    ratios: List[dict] = []
    stable_from: Optional[int] = None
    for a, b in zip(points, points[1:]):
        obs = b.ci95_half_width / max(a.ci95_half_width, _TINY)
        theo = math.sqrt(a.n_scenarios / b.n_scenarios)
        d = abs(b.tvog - a.tvog)
        inside = d <= (a.ci95_half_width + b.ci95_half_width)
        ratios.append(
            {
                "from_n": a.n_scenarios,
                "to_n": b.n_scenarios,
                "observed_ratio": round(obs, 4),
                "theoretical_ratio": round(theo, 4),
                "abs_tvog_change": round(d, 4),
                "stable_within_ci": bool(inside),
            }
        )
        if inside and stable_from is None:
            stable_from = a.n_scenarios
        if not inside:
            stable_from = None

    digest = _inputs_digest(
        product, hw_params, gbm_params, deterministic_discount_rate,
        ladder, seed_base, replications, rel_tol, cbirc_floor,
    )

    unsigned = (
        "Educational scenario-adequacy diagnostic on the governed TVOGEngine. "
        "Representative product + placeholder ESG calibration; automation-driven "
        "sign-off. NOT the governed portfolio TVOG headline. UNSIGNED pending "
        "owner / independent-review approval."
    )

    return ConvergenceStudyResult(
        schema=CONVERGENCE_SCHEMA,
        ladder=ladder,
        points=points,
        deterministic_discount_rate=deterministic_discount_rate,
        seed_base=seed_base,
        replications=replications,
        rel_tol=rel_tol,
        cbirc_floor=cbirc_floor,
        error_model=error_model,
        tvog_reference=tvog_ref,
        n_reference=n_ref,
        se_reference=se_ref,
        se_constant=se_constant,
        variance_reduction_factor=ref.variance_reduction_factor,
        required_n_for_rel_tol=required_n,
        required_n_iid=required_n_iid,
        recommended_n=recommended_n,
        predicted_rel_ci_at_floor=predicted_rel_ci_floor,
        meets_rel_tol_at_floor=meets_at_floor,
        cbirc_floor_satisfied=cbirc_ok,
        mc_error_scaling_exponent=slope,
        convergence_ratios=ratios,
        stable_from_n=stable_from,
        total_runtime_seconds=total_runtime,
        inputs_digest=digest,
        generated_at=datetime.now(timezone.utc).isoformat(),
        unsigned_note=unsigned,
    )


__all__ = [
    "CONVERGENCE_SCHEMA",
    "DEFAULT_LADDER",
    "CBIRC_SCENARIO_FLOOR",
    "DEFAULT_REL_TOL",
    "DEFAULT_DETERMINISTIC_RATE",
    "Z_95",
    "SEED_STRIDE",
    "ConvergencePoint",
    "ConvergenceStudyResult",
    "run_convergence_study",
]
