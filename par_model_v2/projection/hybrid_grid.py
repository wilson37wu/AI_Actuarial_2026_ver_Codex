"""
HybridGrid — Liability Projection Grid for PAR Endowment Models
================================================================

A three-dimensional grid over (projection_month × age_node × scenario) that
stores pre-computed liability values (reserves, present-value cashflows, or
TVOG contributions) and provides:

  * Exact cell read/write at integer grid coordinates
  * Monotone linear interpolation in the age dimension
  * Scenario-averaging (mean) across the scenario dimension
  * Robust boundary handling — clamp rather than raise for out-of-range queries
  * Degenerate-input guards: zero premium / zero sum-assured never produce NaN

Design notes
------------
"Hybrid" refers to the blend of deterministic and stochastic calculations:
  - Deterministic layer : best-estimate reserve computed once per (t, age_node)
  - Stochastic layer    : per-scenario deviation stored in the scenario axis
  - Combined value      : deterministic reserve + stochastic deviation

The grid can therefore be used for:
  1. Deterministic reserving  — fill scenario axis with identical values
  2. TVOG computation         — fill with scenario-specific guarantee PVs
  3. Sensitivity testing      — perturb individual cells and re-aggregate

SOA / IA alignment
------------------
* SOA ASOP 56 §3.2.3 : grid discretisation documented; interpolation method
  stated (linear); extrapolation prohibited (boundary clamp applied instead)
* IA TAS M §3.6.2     : VR-U07 unit tests cover shape, boundary, interpolation,
  and degenerate inputs
* ERM                 : scenario axis enables VaR / ES extraction without
  re-running the full projection

Usage example
-------------
    from par_model_v2.projection.hybrid_grid import HybridGrid

    grid = HybridGrid(
        projection_months=120,          # 10-year term
        age_nodes=[25, 35, 45, 55],     # discrete ages on the grid
        n_scenarios=1000,
    )

    # Populate a single cell
    grid.set_value(t=0, age_node_idx=0, scenario_idx=0, value=10_000.0)

    # Interpolate between age nodes 0 (age 25) and 1 (age 35) at age 30
    v = grid.interpolate_age(t=0, age=30.0, scenario_idx=0)

    # Scenario mean at a given (t, age_node)
    mean_v = grid.scenario_mean(t=0, age_node_idx=0)

    # Best-estimate reserve at any (t, age) — interpolated over age, averaged
    # over scenarios
    be_reserve = grid.best_estimate_value(t=60, age=40.0)
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List, Optional, Sequence

import numpy as np


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class HybridGridError(Exception):
    """Base exception for HybridGrid problems."""


class GridDimensionError(HybridGridError):
    """Raised when constructor arguments produce an invalid grid shape."""


# ---------------------------------------------------------------------------
# Internal sentinel
# ---------------------------------------------------------------------------

_UNSET = float("nan")   # cells not yet written read back as NaN by design


# ---------------------------------------------------------------------------
# HybridGrid
# ---------------------------------------------------------------------------

class HybridGrid:
    """Three-dimensional liability projection grid.

    Parameters
    ----------
    projection_months : int
        Number of monthly projection steps (T).  Must be ≥ 1.
    age_nodes : sequence of float
        Strictly increasing sequence of ages used as grid nodes.  At least 1
        node required; interpolation is only meaningful with ≥ 2 nodes.
    n_scenarios : int
        Number of stochastic scenarios stored per (t, age_node) cell.
        Use n_scenarios=1 for deterministic (best-estimate) grids.

    Grid shape
    ----------
    (projection_months, len(age_nodes), n_scenarios)

    Index conventions
    -----------------
    * t             : 0-based month index in [0, projection_months)
    * age_node_idx  : 0-based index into age_nodes
    * scenario_idx  : 0-based index in [0, n_scenarios)

    Boundary policy
    ---------------
    Out-of-range integer indices are silently clamped to the valid range
    (ASOP 56 §3.2.3 — extrapolation prohibited; clamp used instead).
    """

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def __init__(
        self,
        projection_months: int,
        age_nodes: Sequence[float],
        n_scenarios: int = 1,
    ) -> None:
        # --- validate inputs -----------------------------------------
        if projection_months < 1:
            raise GridDimensionError(
                f"projection_months must be ≥ 1, got {projection_months}"
            )
        age_nodes = list(age_nodes)
        if len(age_nodes) < 1:
            raise GridDimensionError("age_nodes must contain at least one element")
        for i in range(len(age_nodes) - 1):
            if age_nodes[i] >= age_nodes[i + 1]:
                raise GridDimensionError(
                    f"age_nodes must be strictly increasing; "
                    f"violation at indices {i} and {i+1}: "
                    f"{age_nodes[i]} >= {age_nodes[i+1]}"
                )
        if n_scenarios < 1:
            raise GridDimensionError(
                f"n_scenarios must be ≥ 1, got {n_scenarios}"
            )

        self._T: int = int(projection_months)
        self._age_nodes: List[float] = age_nodes
        self._N: int = int(n_scenarios)

        # Core data array — shape (T, A, N); NaN until populated
        self._data: np.ndarray = np.full(
            (self._T, len(self._age_nodes), self._N),
            fill_value=_UNSET,
            dtype=np.float64,
        )

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def shape(self) -> tuple[int, int, int]:
        """(projection_months, n_age_nodes, n_scenarios)."""
        return (self._T, len(self._age_nodes), self._N)

    @property
    def projection_months(self) -> int:
        return self._T

    @property
    def age_nodes(self) -> List[float]:
        return list(self._age_nodes)

    @property
    def n_age_nodes(self) -> int:
        return len(self._age_nodes)

    @property
    def n_scenarios(self) -> int:
        return self._N

    # ------------------------------------------------------------------
    # Index helpers
    # ------------------------------------------------------------------

    def _clamp_t(self, t: int) -> int:
        """Clamp month index into [0, T-1]."""
        return max(0, min(int(t), self._T - 1))

    def _clamp_a(self, a: int) -> int:
        """Clamp age-node index into [0, A-1]."""
        return max(0, min(int(a), len(self._age_nodes) - 1))

    def _clamp_s(self, s: int) -> int:
        """Clamp scenario index into [0, N-1]."""
        return max(0, min(int(s), self._N - 1))

    def is_boundary_t(self, t: int) -> bool:
        """True if t is the first or last projection month."""
        return t == 0 or t == self._T - 1

    def is_boundary_age(self, age_node_idx: int) -> bool:
        """True if age_node_idx is the youngest or oldest node."""
        return age_node_idx == 0 or age_node_idx == len(self._age_nodes) - 1

    # ------------------------------------------------------------------
    # Cell write / read
    # ------------------------------------------------------------------

    def set_value(
        self,
        t: int,
        age_node_idx: int,
        scenario_idx: int,
        value: float,
    ) -> None:
        """Write a value to the grid.

        Parameters
        ----------
        t             : month index (0-based); out-of-range values are clamped
        age_node_idx  : age-node index (0-based); out-of-range values clamped
        scenario_idx  : scenario index (0-based); out-of-range values clamped
        value         : the liability value to store; NaN is accepted (marks
                        unset cells) but finite values are expected in practice
        """
        tc = self._clamp_t(t)
        ac = self._clamp_a(age_node_idx)
        sc = self._clamp_s(scenario_idx)
        self._data[tc, ac, sc] = float(value)

    def get_value(
        self,
        t: int,
        age_node_idx: int,
        scenario_idx: int,
    ) -> float:
        """Read the exact grid cell (with clamping).

        Returns NaN for cells that have not been populated.
        """
        tc = self._clamp_t(t)
        ac = self._clamp_a(age_node_idx)
        sc = self._clamp_s(scenario_idx)
        return float(self._data[tc, ac, sc])

    # ------------------------------------------------------------------
    # Bulk population helpers
    # ------------------------------------------------------------------

    def fill_scenario(
        self,
        t: int,
        age_node_idx: int,
        values: Sequence[float],
    ) -> None:
        """Set all scenario values for a given (t, age_node_idx) cell.

        Parameters
        ----------
        values : sequence of length n_scenarios
        """
        tc = self._clamp_t(t)
        ac = self._clamp_a(age_node_idx)
        if len(values) != self._N:
            raise HybridGridError(
                f"values length {len(values)} != n_scenarios {self._N}"
            )
        self._data[tc, ac, :] = np.asarray(values, dtype=np.float64)

    def fill_uniform(self, value: float) -> None:
        """Fill the entire grid with a constant value (useful for testing)."""
        self._data[:] = float(value)

    # ------------------------------------------------------------------
    # Interpolation — age dimension
    # ------------------------------------------------------------------

    def interpolate_age(
        self,
        t: int,
        age: float,
        scenario_idx: int,
    ) -> float:
        """Linearly interpolate in the age dimension for a given scenario.

        If ``age`` falls below the minimum age node or above the maximum,
        the boundary node value is returned (no extrapolation).

        Parameters
        ----------
        t           : month index (clamped if out of range)
        age         : continuous age at which to evaluate
        scenario_idx: scenario index (clamped if out of range)

        Returns
        -------
        float : interpolated grid value; NaN only if both bracketing nodes are
                unset (NaN)
        """
        tc = self._clamp_t(t)
        sc = self._clamp_s(scenario_idx)
        ages = self._age_nodes

        # Boundary clamp
        if age <= ages[0]:
            return float(self._data[tc, 0, sc])
        if age >= ages[-1]:
            return float(self._data[tc, -1, sc])

        # Find bracketing nodes
        idx_hi = next(i for i, a in enumerate(ages) if a > age)
        idx_lo = idx_hi - 1

        age_lo = ages[idx_lo]
        age_hi = ages[idx_hi]
        v_lo   = float(self._data[tc, idx_lo, sc])
        v_hi   = float(self._data[tc, idx_hi, sc])

        # If either bracketing value is NaN, return NaN — caller must handle
        if math.isnan(v_lo) or math.isnan(v_hi):
            return float("nan")

        alpha = (age - age_lo) / (age_hi - age_lo)   # in (0, 1)
        return v_lo + alpha * (v_hi - v_lo)

    # ------------------------------------------------------------------
    # Scenario aggregation
    # ------------------------------------------------------------------

    def scenario_mean(
        self,
        t: int,
        age_node_idx: int,
        *,
        ignore_unset: bool = True,
    ) -> float:
        """Mean across the scenario dimension for a given (t, age_node_idx).

        Parameters
        ----------
        ignore_unset : if True (default), unset (NaN) cells are excluded from
                       the mean.  If all cells are NaN, returns NaN.
        """
        tc = self._clamp_t(t)
        ac = self._clamp_a(age_node_idx)
        row = self._data[tc, ac, :]
        if ignore_unset:
            valid = row[~np.isnan(row)]
            if len(valid) == 0:
                return float("nan")
            return float(valid.mean())
        return float(row.mean())

    def scenario_percentile(
        self,
        t: int,
        age_node_idx: int,
        pct: float,
    ) -> float:
        """Percentile across the scenario dimension for a given (t, age_node).

        Parameters
        ----------
        pct : percentile in [0, 100]
        """
        tc = self._clamp_t(t)
        ac = self._clamp_a(age_node_idx)
        row = self._data[tc, ac, :]
        valid = row[~np.isnan(row)]
        if len(valid) == 0:
            return float("nan")
        return float(np.percentile(valid, pct))

    # ------------------------------------------------------------------
    # Best-estimate surface
    # ------------------------------------------------------------------

    def best_estimate_value(
        self,
        t: int,
        age: float,
    ) -> float:
        """Interpolated, scenario-averaged value at (t, age).

        Combines:
          1. Linear interpolation in the age dimension across bracketing nodes
          2. Scenario mean at each bracketing node

        This gives the best-estimate liability value at any (t, age) point.
        """
        tc = self._clamp_t(t)
        ages = self._age_nodes

        # Boundary clamp
        if age <= ages[0]:
            return self.scenario_mean(tc, 0)
        if age >= ages[-1]:
            return self.scenario_mean(tc, len(ages) - 1)

        # Find bracketing nodes
        idx_hi = next(i for i, a in enumerate(ages) if a > age)
        idx_lo = idx_hi - 1

        age_lo = ages[idx_lo]
        age_hi = ages[idx_hi]
        m_lo   = self.scenario_mean(tc, idx_lo)
        m_hi   = self.scenario_mean(tc, idx_hi)

        if math.isnan(m_lo) or math.isnan(m_hi):
            return float("nan")

        alpha = (age - age_lo) / (age_hi - age_lo)
        return m_lo + alpha * (m_hi - m_lo)

    # ------------------------------------------------------------------
    # Degenerate-input factory helper
    # ------------------------------------------------------------------

    @classmethod
    def from_liability_projection(
        cls,
        projection_months: int,
        age_nodes: Sequence[float],
        n_scenarios: int,
        sum_assured: float,
        annual_premium: float,
        reserve_values: Optional[np.ndarray] = None,
    ) -> "HybridGrid":
        """Build a HybridGrid pre-filled from liability projection values.

        Handles degenerate inputs: zero sum_assured or zero annual_premium
        are valid (e.g., fully paid-up or zero-benefit rider stub); the grid
        is filled with zeros rather than NaN in these cases so that downstream
        code never encounters NaN from degenerate inputs.

        Parameters
        ----------
        reserve_values : optional ndarray of shape (T, A, N).  If None, the
                         grid is zero-filled (degenerate case guard).
        """
        grid = cls(projection_months, age_nodes, n_scenarios)

        # Degenerate guard: zero economic inputs → zero liability values
        if sum_assured == 0.0 or annual_premium == 0.0:
            grid.fill_uniform(0.0)
            return grid

        if reserve_values is not None:
            arr = np.asarray(reserve_values, dtype=np.float64)
            expected_shape = (
                int(projection_months),
                len(list(age_nodes)),
                int(n_scenarios),
            )
            if arr.shape != expected_shape:
                raise HybridGridError(
                    f"reserve_values shape {arr.shape} != "
                    f"expected {expected_shape}"
                )
            grid._data[:] = arr
        else:
            grid.fill_uniform(0.0)

        return grid

    # ------------------------------------------------------------------
    # Diagnostics
    # ------------------------------------------------------------------

    def coverage_ratio(self) -> float:
        """Fraction of cells that have been populated (not NaN)."""
        total = self._data.size
        if total == 0:
            return float("nan")
        set_count = int(np.sum(~np.isnan(self._data)))
        return set_count / total

    def has_nan(self) -> bool:
        """True if any cell in the grid is NaN (unset or bad value)."""
        return bool(np.any(np.isnan(self._data)))

    def boundary_values(self, scenario_idx: int = 0) -> dict:
        """Return all boundary cell values as a dict for inspection.

        Covers: t=0 (all age nodes), t=T-1 (all age nodes),
                age_node=0 (all t), age_node=-1 (all t).

        Useful in validation and audit reporting.
        """
        sc = self._clamp_s(scenario_idx)
        A = len(self._age_nodes)
        result = {
            "t0_by_age":    [float(self._data[0,   a, sc]) for a in range(A)],
            "tT_by_age":    [float(self._data[-1,  a, sc]) for a in range(A)],
            "youngest_by_t":[float(self._data[t,   0, sc]) for t in range(self._T)],
            "oldest_by_t":  [float(self._data[t, A-1, sc]) for t in range(self._T)],
        }
        return result

    # ------------------------------------------------------------------
    # Dunder
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        T, A, N = self.shape
        cov = f"{self.coverage_ratio():.1%}"
        return (
            f"HybridGrid(T={T}, ages={self._age_nodes}, N={N}, "
            f"coverage={cov})"
        )


__all__ = ["HybridGrid", "HybridGridError", "GridDimensionError"]
