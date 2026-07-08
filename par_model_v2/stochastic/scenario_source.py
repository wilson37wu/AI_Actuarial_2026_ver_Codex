"""ES-3 - User economic-scenario ENGINE INTEGRATION: source selection,
measure guard, and the annual->monthly interpolation mapping.

Owner directive (2026-07-08, KCW, interactive session): allow USER-INPUT
economic scenario FILES alongside the built-in HW1F + GBM scenario
generator.  ES-1 delivered the validating loader
(:mod:`par_model_v2.stochastic.user_scenarios`, schema
``esg-user-scenarios-1.0``); ES-2 delivered the GUI upload/persist page.
ES-3 (this module + :mod:`par_model_v2.viewer.igui_scenario_source`) wires
the validated set into the run pipeline:

* ``scenario_source: model | user_file`` run-config selector,
* the MEASURE GUARD (risk_neutral for a valuation run, real_world for a
  P-measure diagnostic run; a mismatch is an ERROR carrying a structured
  deviation record - the run is refused, never silently mis-measured),
* the annual->monthly INTERPOLATION MAPPING that turns the user file's
  year-end spot-zero curves + annual equity total returns into the monthly
  economic path shape the engine consumes, and
* the file digest + manifest recorded into the run governance trail.

Scope / governance boundary: this module is PURELY ADDITIVE.  The default
selector is ``model`` (the governed HW1F+GBM ESG), so a run that does not
opt in is bit-identical.  Actually RE-BASELINING the governed headline
(TVOG / aggregation report) onto user scenarios moves a governed figure and
is therefore owner-gated - it is NOT part of ES-3.  ES-3 makes user
scenarios a first-class, measure-guarded, governance-recorded run input and
derives the monthly economic-path artifact from them; feeding that artifact
into the headline valuation is the gated follow-on (roadmap note).

User scenario files remain UNSIGNED pending Model Owner approval of the
generating source; every consumed set carries its sha256 file digest.

Monthly interpolation convention (schema ``es3-scenario-source-1.0``,
"piecewise-annual"):
  Let the file give, per scenario ``s`` and projection year ``y`` in 1..Y:
  a spot-zero curve at 12 tenors EFFECTIVE AT THE END of year ``y``, and
  ``EQ_RETURN`` the annual equity total return realised OVER year ``y``.
  The engine consumes months ``m = 1..12*Y``.  We map:
    * projection year of month m:  ``y(m) = ceil(m / 12)``  (months 1..12 ->
      year 1, 13..24 -> year 2, ...);
    * the rate curve applied during month m is the year-``y(m)`` YEAR-END
      curve, held constant across that year (piecewise-annual).  No
      cross-year linear interpolation is imposed: the user file only anchors
      year-END points, and the pre-year-1 curve is a governed run input we
      deliberately do NOT overwrite;
    * the monthly SHORT-RATE PROXY ``r_m`` is the shortest-tenor (3M) spot of
      the applied curve, held over the month;
    * the monthly EQUITY RETURN ``e_m`` is the GEOMETRIC split of the annual
      figure, ``(1 + EQ_RETURN[y(m)]) ** (1/12) - 1``, so the twelve monthly
      returns compound back to the annual total return EXACTLY.
"""
from __future__ import annotations

from typing import Any, Dict

import numpy as np

#: Schema id of the monthly-mapping artifact this module derives.
MAPPING_SCHEMA_ID = "es3-scenario-source-1.0"

#: Tenor used as the monthly short-rate proxy (the shortest curve point).
SHORT_RATE_PROXY_TENOR = "3M"

#: Months per projection year in the engine grid.
MONTHS_PER_YEAR = 12

#: Human-readable statement of the interpolation convention (recorded in the
#: run governance trail so a reviewer sees exactly how annual became monthly).
MONTHLY_MAPPING_DOC = (
    "piecewise-annual: month m maps to projection year y=ceil(m/12); the "
    "year-end spot-zero curve of year y is held constant across that year; "
    "the monthly short-rate proxy is the 3M spot of that curve; the monthly "
    "equity return is the geometric split (1+annual)**(1/12)-1 so twelve "
    "months compound back to the annual EQ_RETURN exactly. No cross-year "
    "linear interpolation and no overwrite of the governed pre-year-1 curve."
)


class ScenarioInterpolationError(ValueError):
    """Raised when a validated :class:`UserScenarioSet` cannot be mapped to
    the monthly engine grid (e.g. the 3M proxy tenor is absent)."""


def _short_rate_tenor_index(user_set: Any) -> int:
    """Index of the short-rate proxy tenor in the set's tenor labels."""
    try:
        return list(user_set.tenor_labels).index(SHORT_RATE_PROXY_TENOR)
    except ValueError as exc:  # pragma: no cover - loader guarantees the tenor
        raise ScenarioInterpolationError(
            "short-rate proxy tenor %r absent from the scenario set tenors %r"
            % (SHORT_RATE_PROXY_TENOR, tuple(user_set.tenor_labels))) from exc


def interpolate_monthly_paths(user_set: Any) -> Dict[str, Any]:
    """Map a validated :class:`UserScenarioSet` onto the monthly engine grid.

    Returns numpy arrays following the documented piecewise-annual convention:

    * ``short_rate`` - ``(n_scenarios, n_months)`` monthly short-rate proxy
      (the 3M spot of the applied year-end curve, held over the year);
    * ``equity_return`` - ``(n_scenarios, n_months)`` monthly equity total
      return, the geometric split of the annual EQ_RETURN;
    * ``rate_cube`` - ``(n_scenarios, n_months, n_tenors)`` the full monthly
      curve cube (each year's year-end curve broadcast over its 12 months);
    * ``year_index`` - ``(n_months,)`` the 1-based projection year of each
      month (audit trail for the mapping).

    Purely deterministic; no randomness, no governed-figure dependency.
    """
    rates = np.asarray(user_set.rates, dtype=float)          # (S, Y, T)
    eq = np.asarray(user_set.eq_returns, dtype=float)         # (S, Y)
    n_scn, n_years, n_ten = rates.shape
    n_months = n_years * MONTHS_PER_YEAR

    # month m (0-based) -> projection year index (0-based): m // 12
    year_of_month = np.arange(n_months) // MONTHS_PER_YEAR    # (M,)

    # Broadcast each year's curve/return across its 12 months (piecewise-annual).
    rate_cube = rates[:, year_of_month, :]                    # (S, M, T)
    ti = _short_rate_tenor_index(user_set)
    short_rate = rate_cube[:, :, ti]                          # (S, M)

    annual_eq = eq[:, year_of_month]                          # (S, M)
    # Geometric monthly split; clip the (1+r) base at a tiny positive floor so
    # the fractional power is finite even at the spec's EQ_RETURN=-0.99 bound.
    base = np.maximum(1.0 + annual_eq, 1e-9)
    monthly_eq = base ** (1.0 / MONTHS_PER_YEAR) - 1.0        # (S, M)

    return {
        "schema": MAPPING_SCHEMA_ID,
        "n_scenarios": int(n_scn),
        "projection_years": int(n_years),
        "n_months": int(n_months),
        "months_per_year": MONTHS_PER_YEAR,
        "short_rate_proxy_tenor": SHORT_RATE_PROXY_TENOR,
        "convention": MONTHLY_MAPPING_DOC,
        "year_index": (year_of_month + 1).astype(int),        # 1-based
        "short_rate": short_rate,
        "equity_return": monthly_eq,
        "rate_cube": rate_cube,
    }


def monthly_mapping_summary(user_set: Any) -> Dict[str, Any]:
    """A small, JSON-safe eyeball card for the run governance trail: the
    mapping conventions plus cross-year-boundary check statistics that a
    reviewer can verify by hand (year-1 monthly equity compounds to the
    annual figure; the month-12 short rate equals the year-1 3M spot)."""
    paths = interpolate_monthly_paths(user_set)
    short = paths["short_rate"]
    meq = paths["equity_return"]
    n_scn = paths["n_scenarios"]
    # Year-1 recompounding check (all scenarios), proving the geometric split.
    y1 = meq[:, :MONTHS_PER_YEAR]
    recompounded_y1 = np.prod(1.0 + y1, axis=1) - 1.0
    annual_y1 = np.asarray(user_set.eq_returns, dtype=float)[:, 0]
    max_recompound_err = float(np.max(np.abs(recompounded_y1 - annual_y1)))
    return {
        "schema": MAPPING_SCHEMA_ID,
        "n_scenarios": n_scn,
        "projection_years": paths["projection_years"],
        "n_months": paths["n_months"],
        "months_per_year": MONTHS_PER_YEAR,
        "short_rate_proxy_tenor": SHORT_RATE_PROXY_TENOR,
        "convention": MONTHLY_MAPPING_DOC,
        "checks": {
            # month 12 (index 11) short rate == year-1 3M spot (piecewise-annual)
            "short_rate_month12_p50": float(np.percentile(short[:, 11], 50)),
            "equity_return_month1_p50": float(np.percentile(meq[:, 0], 50)),
            "year1_recompound_max_abs_error": max_recompound_err,
        },
    }
