"""
Dynamic-Lapse TVOG Delta — Rate-Optionality Value of the Lapse Response
=======================================================================

Roadmap §4.1 item #4 (MR-003).  The Phase 13 dynamic-lapse model
(:mod:`par_model_v2.projection.dynamic_lapse`) makes the annual lapse rate a
function of the market-vs-credited rate differential.  This module *quantifies*
what that costs in **TVOG** (Time Value of Options and Guarantees) terms — the
number the roadmap item asks for ("TVOG delta quantified").

TVOG proxy
----------
For a representative PAR endowment, project the liability PV across a
distribution of market-rate outcomes ``R ~ N(credited, sigma^2)`` and take the
**convexity / optionality value**

    TVOG = E[ PV_netliab(R) ] - PV_netliab(credited)

i.e. the average scenario reserve minus the deterministic central reserve (the
classic "stochastic minus deterministic" definition of the time value of a
guarantee).  The expectation is evaluated by exact 5-node **Gauss-Hermite**
quadrature (no SciPy dependency; integrates any polynomial up to degree 9
exactly), so the result is deterministic and reproducible.

Why the *delta* isolates dynamic lapse
--------------------------------------
Under **static** lapse the projected PV does not depend on the market rate at
all (lapse is a duration-only table), so ``PV_netliab(R)`` is FLAT and
``TVOG_static == 0`` exactly.  Under **dynamic** lapse the PV bends with the
rate, giving a non-zero ``TVOG_dynamic``.  The reported

    delta = TVOG_dynamic - TVOG_static  ( = TVOG_dynamic )

is therefore precisely the TVOG contribution *introduced by* the dynamic-lapse
assumption — the FLAT-sensitivity gap that MR-003 flags for static lapse.

SCOPE / PRODUCTION USE RESTRICTION
----------------------------------
This is an **educational representative-policy diagnostic**, NOT the governed
portfolio TVOG headline (which is produced by the stochastic aggregation engine
and is left untouched).  The rate distribution ``sigma`` is an illustrative
assumption, the experience study behind the lapse parameters is synthetic, and
the sign-off is automation-driven.  UNSIGNED pending owner approval.

Standards: SOA ASOP 7 §3.3 (economic-responsive behaviour), ASOP 56 §3.1
(model documentation); IA TAS M §3.5/§3.6 (assumption traceability).
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

import numpy as np

from par_model_v2.projection.monthly_projection import (
    DEFAULT_RESERVING_DISCOUNT_RATE,
    ParEndowmentProduct,
    project_liability_cashflows,
)
from par_model_v2.projection.dynamic_lapse import (
    DynamicLapseAssumption,
    default_hk_par_dynamic_lapse,
)

TVOG_SCHEMA = "dynamic-lapse-tvog-1.0"

#: Illustrative annualised standard deviation of the market rate used for the
#: TVOG expectation (100 bps).  Documented assumption, not calibrated.
DEFAULT_RATE_SIGMA = 0.010

# ---------------------------------------------------------------------------
# 5-node Gauss-Hermite quadrature (physicists' convention)
#   \int e^{-x^2} f(x) dx  ~=  sum_i W_i f(x_i)
# Recentred to E[f(R)], R ~ N(mu, sigma^2):  R_i = mu + sigma*sqrt(2)*x_i,
# probability weight w_i = W_i / sqrt(pi)  (sum w_i = 1).
# Exact for polynomials up to degree 2*5-1 = 9.
# ---------------------------------------------------------------------------

_GH5_X: Tuple[float, ...] = (
    0.0,
    0.9585724646138185,
    -0.9585724646138185,
    2.0201828704560856,
    -2.0201828704560856,
)
_GH5_W: Tuple[float, ...] = (
    0.9453087204829419,
    0.3936193231522412,
    0.3936193231522412,
    0.019953242059045913,
    0.019953242059045913,
)


def gauss_hermite_normal_nodes(
    mu: float, sigma: float
) -> List[Tuple[float, float]]:
    """Return ``[(rate_i, prob_weight_i), ...]`` for ``R ~ N(mu, sigma^2)``.

    Probability weights sum to 1; the nodes integrate ``E[g(R)]`` exactly for
    any polynomial ``g`` up to degree 9.  ``sigma == 0`` collapses to the single
    central node (a degenerate, deterministic rate).
    """
    if sigma < 0:
        raise ValueError(f"sigma must be >= 0; got {sigma}")
    sqrt_pi = math.sqrt(math.pi)
    if sigma == 0.0:
        return [(mu, 1.0)]
    return [
        (mu + sigma * math.sqrt(2.0) * x, w / sqrt_pi)
        for x, w in zip(_GH5_X, _GH5_W)
    ]


# ---------------------------------------------------------------------------
# Representative product (matches the Phase 13 impact-study reference policy)
# ---------------------------------------------------------------------------

def representative_par_product() -> ParEndowmentProduct:
    """Representative 20y HK PAR endowment used for the TVOG diagnostic."""
    return ParEndowmentProduct(
        term_years=20,
        issue_age=40,
        gender="M",
        sum_assured=1_000_000.0,
        annual_premium=60_000.0,
        rb_rate_annual=0.030,
        terminal_bonus_pct=0.50,
        surrender_value_pct=0.90,
    )


# ---------------------------------------------------------------------------
# Result containers
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class TvogScenarioRow:
    """One Gauss-Hermite rate node and its projected PV net liability."""

    market_rate: float
    spread_bps: float
    prob_weight: float
    pv_net_liability: float

    def to_dict(self) -> Dict[str, object]:
        return {
            "market_rate": round(self.market_rate, 8),
            "spread_bps": round(self.spread_bps, 2),
            "prob_weight": round(self.prob_weight, 8),
            "pv_net_liability": round(self.pv_net_liability, 4),
        }


@dataclass(frozen=True)
class TvogProxyResult:
    """TVOG proxy under a single lapse basis (``static`` or ``dynamic``)."""

    basis: str                      # "static" | "dynamic"
    credited_rate: float
    rate_sigma: float
    discount_rate_annual: float
    pv_central: float               # PV_netliab at the central (credited) rate
    expected_pv: float              # E[PV_netliab(R)]
    tvog: float                     # expected_pv - pv_central
    scenarios: Tuple[TvogScenarioRow, ...]

    def to_dict(self) -> Dict[str, object]:
        return {
            "basis": self.basis,
            "credited_rate": self.credited_rate,
            "rate_sigma": self.rate_sigma,
            "discount_rate_annual": self.discount_rate_annual,
            "pv_central": round(self.pv_central, 4),
            "expected_pv": round(self.expected_pv, 4),
            "tvog": round(self.tvog, 4),
            "scenarios": [s.to_dict() for s in self.scenarios],
        }


@dataclass(frozen=True)
class DynamicLapseTvogDelta:
    """Static-vs-dynamic TVOG delta for the representative policy."""

    schema: str
    run_timestamp: str
    credited_rate: float
    rate_sigma: float
    discount_rate_annual: float
    static: TvogProxyResult
    dynamic: TvogProxyResult
    tvog_static: float
    tvog_dynamic: float
    tvog_delta: float
    tvog_delta_pct_of_central: float
    assumption: Dict[str, object]
    unsigned: bool = True
    unsigned_banner: str = (
        "UNSIGNED — educational representative-policy TVOG proxy; NOT the "
        "governed portfolio TVOG headline. Replace the synthetic experience "
        "study + illustrative rate sigma and obtain APS X2 review before use."
    )
    standard_references: Tuple[str, ...] = (
        "SOA ASOP 7 §3.3", "SOA ASOP 56 §3.1", "IA TAS M §3.5", "IA TAS M §3.6",
    )

    def to_dict(self) -> Dict[str, object]:
        d = {
            "schema": self.schema,
            "run_timestamp": self.run_timestamp,
            "credited_rate": self.credited_rate,
            "rate_sigma": self.rate_sigma,
            "discount_rate_annual": self.discount_rate_annual,
            "tvog_static": round(self.tvog_static, 4),
            "tvog_dynamic": round(self.tvog_dynamic, 4),
            "tvog_delta": round(self.tvog_delta, 4),
            "tvog_delta_pct_of_central": round(self.tvog_delta_pct_of_central, 6),
            "static": self.static.to_dict(),
            "dynamic": self.dynamic.to_dict(),
            "assumption": self.assumption,
            "unsigned": self.unsigned,
            "unsigned_banner": self.unsigned_banner,
            "standard_references": list(self.standard_references),
        }
        return d

    def content_digest(self) -> str:
        """Deterministic SHA-256 over the numeric content (ex-timestamp)."""
        payload = self.to_dict()
        payload.pop("run_timestamp", None)
        blob = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()

    def markdown(self) -> str:
        rows = []
        for s in self.dynamic.scenarios:
            st = next(
                (r for r in self.static.scenarios
                 if abs(r.market_rate - s.market_rate) < 1e-12),
                None,
            )
            rows.append(
                "| {:+.0f} | {:.4f} | {:.4f} | {:,.2f} | {:,.2f} |".format(
                    s.spread_bps, s.market_rate, s.prob_weight,
                    (st.pv_net_liability if st else float("nan")),
                    s.pv_net_liability,
                )
            )
        table = "\n".join(rows)
        return (
            "### TVOG delta — dynamic vs static lapse (representative 20y PAR)\n\n"
            f"**Rate distribution:** market rate ~ N(credited={self.credited_rate:.4f}, "
            f"sigma={self.rate_sigma:.4f}); 5-node Gauss-Hermite expectation. "
            f"Discount {self.discount_rate_annual:.3%} (<= CBIRC 3.0% cap).\n\n"
            "| Spread (bps) | Market rate | Prob wt | PV NL static | PV NL dynamic |\n"
            "|---:|---:|---:|---:|---:|\n"
            f"{table}\n\n"
            f"- **TVOG static** = E[PV] - PV(central) = **{self.tvog_static:,.4f}** "
            "(0 by construction — static lapse is rate-invariant / FLAT).\n"
            f"- **TVOG dynamic** = **{self.tvog_dynamic:,.4f}**.\n"
            f"- **TVOG delta (dynamic - static)** = **{self.tvog_delta:,.4f}** "
            f"= **{self.tvog_delta_pct_of_central:+.3%}** of the central reserve "
            f"|{self.static.pv_central:,.2f}|.\n\n"
            f"> {self.unsigned_banner}\n"
        )


# ---------------------------------------------------------------------------
# Computation
# ---------------------------------------------------------------------------

def tvog_proxy(
    assumption: Optional[DynamicLapseAssumption],
    product: Optional[ParEndowmentProduct] = None,
    credited_rate: float = 0.025,
    rate_sigma: float = DEFAULT_RATE_SIGMA,
    discount_rate_annual: float = DEFAULT_RESERVING_DISCOUNT_RATE,
) -> TvogProxyResult:
    """TVOG proxy under one lapse basis.

    ``assumption is None`` ⇒ **static** basis (the projection ignores the market
    rate, so every node shares the same PV and ``tvog == 0``).  Otherwise the
    **dynamic** basis feeds each Gauss-Hermite rate node through the dynamic
    lapse function.
    """
    if product is None:
        product = representative_par_product()
    basis = "static" if assumption is None else "dynamic"
    nodes = gauss_hermite_normal_nodes(credited_rate, rate_sigma)

    def pv_at(rate: float) -> float:
        if assumption is None:
            res = project_liability_cashflows(
                product, discount_rate_annual=discount_rate_annual
            )
        else:
            res = project_liability_cashflows(
                product,
                discount_rate_annual=discount_rate_annual,
                dynamic_lapse=assumption,
                market_rate=rate,
            )
        return float(res.pv_net_liability)

    pv_central = pv_at(credited_rate)
    scenarios: List[TvogScenarioRow] = []
    expected_pv = 0.0
    for rate, w in nodes:
        pv = pv_at(rate)
        expected_pv += w * pv
        scenarios.append(
            TvogScenarioRow(
                market_rate=rate,
                spread_bps=(rate - credited_rate) * 1e4,
                prob_weight=w,
                pv_net_liability=pv,
            )
        )
    return TvogProxyResult(
        basis=basis,
        credited_rate=credited_rate,
        rate_sigma=rate_sigma,
        discount_rate_annual=discount_rate_annual,
        pv_central=pv_central,
        expected_pv=expected_pv,
        tvog=expected_pv - pv_central,
        scenarios=tuple(scenarios),
    )


def dynamic_lapse_tvog_delta(
    assumption: Optional[DynamicLapseAssumption] = None,
    product: Optional[ParEndowmentProduct] = None,
    credited_rate: Optional[float] = None,
    rate_sigma: float = DEFAULT_RATE_SIGMA,
    discount_rate_annual: float = DEFAULT_RESERVING_DISCOUNT_RATE,
) -> DynamicLapseTvogDelta:
    """Quantify the TVOG delta introduced by the dynamic-lapse assumption.

    Runs the TVOG proxy under static and dynamic lapse and returns the signed
    delta (``= TVOG_dynamic`` since ``TVOG_static == 0``) plus full scenario
    provenance.  ``assumption`` defaults to the pre-calibrated HK PAR default.
    """
    if assumption is None:
        cr = 0.025 if credited_rate is None else credited_rate
        assumption = default_hk_par_dynamic_lapse(credited_rate=cr)
    cr = assumption.credited_rate if credited_rate is None else credited_rate

    static = tvog_proxy(None, product, cr, rate_sigma, discount_rate_annual)
    dynamic = tvog_proxy(assumption, product, cr, rate_sigma, discount_rate_annual)

    delta = dynamic.tvog - static.tvog
    denom = abs(static.pv_central)
    delta_pct = (delta / denom) if denom > 0 else float("nan")

    return DynamicLapseTvogDelta(
        schema=TVOG_SCHEMA,
        run_timestamp=datetime.now(timezone.utc).isoformat(),
        credited_rate=cr,
        rate_sigma=rate_sigma,
        discount_rate_annual=discount_rate_annual,
        static=static,
        dynamic=dynamic,
        tvog_static=static.tvog,
        tvog_dynamic=dynamic.tvog,
        tvog_delta=delta,
        tvog_delta_pct_of_central=delta_pct,
        assumption={
            "beta": assumption.beta,
            "kappa": assumption.kappa,
            "shock_max": assumption.shock_max,
            "tau": assumption.tau,
            "width": assumption.width,
            "credited_rate": assumption.credited_rate,
            "marginal_response_bound_year1": assumption.marginal_response_bound(),
        },
    )


def tvog_delta_vol_profile(
    sigmas: Tuple[float, ...] = (0.0025, 0.0050, 0.0100, 0.0150, 0.0200),
    assumption: Optional[DynamicLapseAssumption] = None,
    credited_rate: float = 0.025,
    discount_rate_annual: float = DEFAULT_RESERVING_DISCOUNT_RATE,
) -> List[Dict[str, float]]:
    """TVOG delta as a function of the assumed rate volatility (report table)."""
    if assumption is None:
        assumption = default_hk_par_dynamic_lapse(credited_rate=credited_rate)
    out: List[Dict[str, float]] = []
    for sig in sigmas:
        d = dynamic_lapse_tvog_delta(
            assumption=assumption,
            credited_rate=credited_rate,
            rate_sigma=sig,
            discount_rate_annual=discount_rate_annual,
        )
        out.append(
            {
                "rate_sigma": sig,
                "tvog_static": d.tvog_static,
                "tvog_dynamic": d.tvog_dynamic,
                "tvog_delta": d.tvog_delta,
                "tvog_delta_pct_of_central": d.tvog_delta_pct_of_central,
            }
        )
    return out


__all__ = [
    "TVOG_SCHEMA",
    "DEFAULT_RATE_SIGMA",
    "gauss_hermite_normal_nodes",
    "representative_par_product",
    "TvogScenarioRow",
    "TvogProxyResult",
    "DynamicLapseTvogDelta",
    "tvog_proxy",
    "dynamic_lapse_tvog_delta",
    "tvog_delta_vol_profile",
]
