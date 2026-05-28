"""
Unit tests for HybridGrid — Boundary Conditions
================================================

Covers VR-U07: "HybridGrid (liability projection grid) must have unit tests
confirming correct boundary handling, grid shape, and interpolation."

Acceptance criteria (from ia_validation.py VR-U07):
  AC1  Grid shape matches expected (term × age × scenario) dimensions
  AC2  Boundary cells (age=0, final projection month) return correct values
  AC3  Interpolation between grid nodes is monotone where expected
  AC4  Zero premium / zero sum-assured inputs handled without NaN output

Test classes
------------
  TestHybridGridConstruction      — valid and invalid constructor args
  TestGridShape                   — AC1: shape property and data layout
  TestBoundaryCells               — AC2: t=0, t=T-1, age_node=0, age_node=-1
  TestBoundaryClamp               — AC2: out-of-range indices clamped to boundary
  TestInterpolation               — AC3: linear interp, monotonicity, NaN guard
  TestScenarioAggregation         — scenario_mean, scenario_percentile
  TestBestEstimate                — best_estimate_value: interp + scene mean
  TestDegenerateInputs            — AC4: zero premium, zero SA, factory method
  TestCoverageAndDiagnostics      — coverage_ratio, has_nan, boundary_values
  TestIABoundaryConditionsSuite   — combined AC2 acceptance-criteria walkthrough

Run:
    PYTHONPATH=. pytest tests/test_hybrid_grid.py -v
"""

from __future__ import annotations

import math
import numpy as np
import pytest

from par_model_v2.projection.hybrid_grid import (
    GridDimensionError,
    HybridGrid,
    HybridGridError,
)


# ===========================================================================
# Helpers / fixtures
# ===========================================================================

def _filled_grid(T: int = 12, ages=(25, 35, 45), N: int = 4) -> HybridGrid:
    """Return a grid with values = t * 100 + age_node_idx * 10 + scenario_idx."""
    g = HybridGrid(T, ages, N)
    A = len(ages)
    for t in range(T):
        for a in range(A):
            for s in range(N):
                g.set_value(t, a, s, t * 100 + a * 10 + s)
    return g


def _monotone_grid(T: int = 24, ages=(20, 30, 40, 50), N: int = 1) -> HybridGrid:
    """Reserve values strictly increasing with age; constant across t."""
    g = HybridGrid(T, ages, N)
    A = len(ages)
    for t in range(T):
        for a in range(A):
            # Reserve decreases as age increases (older → less remaining term)
            g.set_value(t, a, 0, float(1000 - a * 100))
    return g


# ===========================================================================
# 1. Constructor validation
# ===========================================================================

class TestHybridGridConstruction:

    def test_minimal_valid_construction(self):
        """Single-month, single-age, single-scenario grid is valid."""
        g = HybridGrid(projection_months=1, age_nodes=[30], n_scenarios=1)
        assert g.shape == (1, 1, 1)

    def test_standard_construction(self):
        """Standard PAR grid: 120 months, 4 ages, 1000 scenarios."""
        g = HybridGrid(120, [25, 35, 45, 55], 1000)
        assert g.shape == (120, 4, 1000)

    def test_zero_projection_months_raises(self):
        with pytest.raises(GridDimensionError, match="projection_months"):
            HybridGrid(0, [25, 35], 10)

    def test_negative_projection_months_raises(self):
        with pytest.raises(GridDimensionError):
            HybridGrid(-5, [25, 35], 10)

    def test_empty_age_nodes_raises(self):
        with pytest.raises(GridDimensionError, match="age_nodes"):
            HybridGrid(12, [], 10)

    def test_non_increasing_age_nodes_raises(self):
        with pytest.raises(GridDimensionError, match="strictly increasing"):
            HybridGrid(12, [30, 25, 40], 10)

    def test_equal_age_nodes_raises(self):
        with pytest.raises(GridDimensionError, match="strictly increasing"):
            HybridGrid(12, [25, 25, 35], 10)

    def test_zero_scenarios_raises(self):
        with pytest.raises(GridDimensionError, match="n_scenarios"):
            HybridGrid(12, [25, 35], 0)

    def test_default_n_scenarios_is_one(self):
        g = HybridGrid(12, [25, 35])
        assert g.n_scenarios == 1

    def test_single_age_node_valid(self):
        """One age node means no interpolation; grid still valid."""
        g = HybridGrid(60, [40], 100)
        assert g.n_age_nodes == 1

    def test_fractional_ages_accepted(self):
        """Age nodes can be fractional (e.g., 25.5, 35.5)."""
        g = HybridGrid(12, [25.5, 35.5, 45.5], 1)
        assert g.age_nodes == [25.5, 35.5, 45.5]


# ===========================================================================
# 2. Grid shape — AC1
# ===========================================================================

class TestGridShape:
    """AC1: Grid shape matches expected (term × age × scenario) dimensions."""

    def test_shape_property_matches_constructor(self):
        g = HybridGrid(60, [20, 30, 40, 50, 60], 500)
        T, A, N = g.shape
        assert T == 60
        assert A == 5
        assert N == 500

    def test_projection_months_property(self):
        g = HybridGrid(240, [25, 55], 10)
        assert g.projection_months == 240

    def test_age_nodes_property_returns_copy(self):
        nodes = [25.0, 35.0, 45.0]
        g = HybridGrid(12, nodes, 1)
        returned = g.age_nodes
        returned.append(99.0)   # mutate the returned list
        assert g.age_nodes == nodes   # original unchanged

    def test_n_age_nodes_property(self):
        g = HybridGrid(12, [20, 30, 40, 50], 1)
        assert g.n_age_nodes == 4

    def test_n_scenarios_property(self):
        g = HybridGrid(12, [25, 35], 250)
        assert g.n_scenarios == 250

    def test_unset_cells_are_nan(self):
        """Fresh grid cells read back as NaN before any set_value calls."""
        g = HybridGrid(6, [30, 40], 3)
        for t in range(6):
            for a in range(2):
                for s in range(3):
                    assert math.isnan(g.get_value(t, a, s))

    @pytest.mark.parametrize("T,ages,N", [
        (5 * 12,  [25, 35, 45],       1),    # 5Y term
        (10 * 12, [25, 35, 45, 55],   100),  # 10Y term, 4 age nodes
        (20 * 12, list(range(20, 70, 5)), 500),  # 20Y, 10 age nodes
    ])
    def test_parametrised_shapes(self, T, ages, N):
        g = HybridGrid(T, ages, N)
        assert g.shape == (T, len(ages), N)


# ===========================================================================
# 3. Boundary cells — AC2
# ===========================================================================

class TestBoundaryCells:
    """AC2: Boundary cells (age=0, final projection month) return correct
    values once populated."""

    def test_t0_all_age_nodes_readable(self):
        """t=0 is accessible for every age node and returns the stored value."""
        g = HybridGrid(60, [20, 30, 40], 1)
        for a in range(3):
            g.set_value(t=0, age_node_idx=a, scenario_idx=0, value=float(a * 1000))
        for a in range(3):
            assert g.get_value(0, a, 0) == pytest.approx(float(a * 1000))

    def test_tT_minus_1_all_age_nodes_readable(self):
        """t=T-1 (final month) is accessible and correct."""
        T = 120
        g = HybridGrid(T, [25, 35, 45, 55], 1)
        for a in range(4):
            g.set_value(T - 1, a, 0, float(a * 500 + 9999))
        for a in range(4):
            assert g.get_value(T - 1, a, 0) == pytest.approx(float(a * 500 + 9999))

    def test_youngest_age_node_idx0_correct(self):
        """age_node_idx=0 (youngest) stores and returns correctly."""
        g = HybridGrid(12, [20, 30, 40], 2)
        g.set_value(t=5, age_node_idx=0, scenario_idx=0, value=777.5)
        g.set_value(t=5, age_node_idx=0, scenario_idx=1, value=888.5)
        assert g.get_value(5, 0, 0) == pytest.approx(777.5)
        assert g.get_value(5, 0, 1) == pytest.approx(888.5)

    def test_oldest_age_node_idx_last_correct(self):
        """age_node_idx=A-1 (oldest) stores and returns correctly."""
        g = HybridGrid(12, [20, 30, 40, 50], 1)
        g.set_value(t=0, age_node_idx=3, scenario_idx=0, value=42.0)
        assert g.get_value(0, 3, 0) == pytest.approx(42.0)

    def test_is_boundary_t_flags_correctly(self):
        T = 24
        g = HybridGrid(T, [25, 35], 1)
        assert g.is_boundary_t(0)           # first month
        assert g.is_boundary_t(T - 1)       # last month
        assert not g.is_boundary_t(1)
        assert not g.is_boundary_t(T - 2)

    def test_is_boundary_age_flags_correctly(self):
        g = HybridGrid(12, [25, 35, 45, 55], 1)
        assert g.is_boundary_age(0)         # youngest
        assert g.is_boundary_age(3)         # oldest
        assert not g.is_boundary_age(1)
        assert not g.is_boundary_age(2)

    def test_full_boundary_values_dict_correct(self):
        """boundary_values() returns all edges of the grid."""
        T, ages, N = 4, [20, 30, 40], 1
        g = HybridGrid(T, ages, N)
        # Fill with a deterministic pattern: value = t * 10 + age_node_idx
        for t in range(T):
            for a in range(len(ages)):
                g.set_value(t, a, 0, float(t * 10 + a))
        bv = g.boundary_values(scenario_idx=0)

        # t=0 row
        assert bv["t0_by_age"] == pytest.approx([0.0, 1.0, 2.0])
        # t=T-1 row
        assert bv["tT_by_age"] == pytest.approx([30.0, 31.0, 32.0])
        # youngest age col (a=0): values = t*10 + 0 = 0, 10, 20, 30
        assert bv["youngest_by_t"] == pytest.approx([0.0, 10.0, 20.0, 30.0])
        # oldest age col (a=2): values = t*10 + 2 = 2, 12, 22, 32
        assert bv["oldest_by_t"] == pytest.approx([2.0, 12.0, 22.0, 32.0])


# ===========================================================================
# 4. Boundary clamp — AC2 (out-of-range indices clamped, not raised)
# ===========================================================================

class TestBoundaryClamp:
    """Out-of-range integer indices must be clamped to valid range (ASOP 56
    §3.2.3 — no extrapolation; boundary returned instead)."""

    @pytest.fixture
    def grid(self):
        return _filled_grid(T=12, ages=(25, 35, 45), N=4)

    def test_t_below_zero_clamped_to_t0(self, grid):
        """t=-1 should return the same as t=0."""
        for a in range(3):
            for s in range(4):
                assert grid.get_value(-1, a, s) == grid.get_value(0, a, s)

    def test_t_above_max_clamped_to_tT_minus_1(self, grid):
        """t=100 should return t=T-1=11."""
        T = grid.projection_months
        for a in range(3):
            for s in range(4):
                assert grid.get_value(100, a, s) == grid.get_value(T - 1, a, s)

    def test_age_node_below_zero_clamped_to_0(self, grid):
        """age_node_idx=-1 returns age_node_idx=0."""
        for t in range(12):
            for s in range(4):
                assert grid.get_value(t, -1, s) == grid.get_value(t, 0, s)

    def test_age_node_above_max_clamped_to_last(self, grid):
        """age_node_idx=99 returns the last age node."""
        A = grid.n_age_nodes
        for t in range(12):
            for s in range(4):
                assert grid.get_value(t, 99, s) == grid.get_value(t, A - 1, s)

    def test_scenario_below_zero_clamped(self, grid):
        for t in range(12):
            for a in range(3):
                assert grid.get_value(t, a, -1) == grid.get_value(t, a, 0)

    def test_scenario_above_max_clamped(self, grid):
        N = grid.n_scenarios
        for t in range(12):
            for a in range(3):
                assert grid.get_value(t, a, 999) == grid.get_value(t, a, N - 1)

    def test_set_value_out_of_range_t_clamped(self):
        """set_value with t=-1 writes to t=0 (no exception)."""
        g = HybridGrid(6, [25, 35], 1)
        g.set_value(-1, 0, 0, 99.9)
        assert g.get_value(0, 0, 0) == pytest.approx(99.9)

    def test_interpolate_age_below_min_returns_boundary(self):
        """interpolate_age(age=10) for nodes starting at 25 → returns age 25 cell."""
        g = HybridGrid(12, [25, 35, 45], 1)
        g.fill_uniform(100.0)
        assert g.interpolate_age(t=0, age=10.0, scenario_idx=0) == pytest.approx(100.0)

    def test_interpolate_age_above_max_returns_boundary(self):
        """interpolate_age(age=99) for nodes ending at 55 → returns age 55 cell."""
        g = HybridGrid(12, [25, 35, 45, 55], 1)
        g.set_value(0, 3, 0, 500.0)   # age_node 55 = index 3
        val = g.interpolate_age(t=0, age=99.0, scenario_idx=0)
        assert val == pytest.approx(500.0)


# ===========================================================================
# 5. Interpolation — AC3
# ===========================================================================

class TestInterpolation:
    """AC3: Interpolation between grid nodes is monotone where expected."""

    def test_linear_midpoint(self):
        """Midpoint between two ages should be the arithmetic mean."""
        g = HybridGrid(1, [20, 40], 1)
        g.set_value(0, 0, 0, 100.0)   # age 20 → 100
        g.set_value(0, 1, 0, 200.0)   # age 40 → 200
        # age 30 = midpoint → 150
        assert g.interpolate_age(0, 30.0, 0) == pytest.approx(150.0)

    def test_linear_quarter_point(self):
        """Quarter-point interpolation: (25 - 20) / (40 - 20) = 0.25."""
        g = HybridGrid(1, [20, 40], 1)
        g.set_value(0, 0, 0, 0.0)
        g.set_value(0, 1, 0, 100.0)
        assert g.interpolate_age(0, 25.0, 0) == pytest.approx(25.0)

    def test_exact_node_age_returns_exact_value(self):
        """Querying exactly at a node age returns the stored value (no error)."""
        g = HybridGrid(12, [25, 35, 45, 55], 1)
        for a, val in enumerate([1000, 900, 800, 700]):
            g.set_value(0, a, 0, float(val))
        for a, (age, expected) in enumerate(
            zip([25, 35, 45, 55], [1000, 900, 800, 700])
        ):
            # Exact age — should hit boundary or left node exactly
            result = g.interpolate_age(0, float(age), 0)
            assert result == pytest.approx(float(expected), abs=1e-9), (
                f"age={age}: expected {expected}, got {result}"
            )

    def test_interpolation_monotone_decreasing(self):
        """If values are strictly decreasing with age, interpolation must
        produce a monotone-decreasing curve at every intermediate age."""
        g = _monotone_grid(T=1, ages=(20, 30, 40, 50), N=1)
        # Expected: 1000, 900, 800, 700 at nodes
        ages_query = np.linspace(20, 50, 100)
        values = [g.interpolate_age(0, float(a), 0) for a in ages_query]
        for i in range(len(values) - 1):
            assert values[i] >= values[i + 1] - 1e-9, (
                f"Monotonicity violated at index {i}: "
                f"v[{i}]={values[i]:.4f} > v[{i+1}]={values[i+1]:.4f}"
            )

    def test_interpolation_monotone_increasing(self):
        """If values strictly increase with age (e.g., liability PV), interp
        must be monotone increasing."""
        g = HybridGrid(1, [20, 30, 40, 50], 1)
        for a, v in enumerate([100.0, 200.0, 300.0, 400.0]):
            g.set_value(0, a, 0, v)
        ages_query = np.linspace(20, 50, 100)
        values = [g.interpolate_age(0, float(a), 0) for a in ages_query]
        for i in range(len(values) - 1):
            assert values[i] <= values[i + 1] + 1e-9

    def test_interpolation_flat_is_constant(self):
        """Constant values across nodes → all interpolated values equal."""
        g = HybridGrid(1, [20, 30, 40, 50], 1)
        g.fill_uniform(42.0)
        for age in np.linspace(20, 50, 50):
            assert g.interpolate_age(0, float(age), 0) == pytest.approx(42.0)

    def test_interpolation_nan_when_node_unset(self):
        """If a bracketing node is NaN (unset), interpolation returns NaN."""
        g = HybridGrid(1, [20, 30, 40], 1)
        g.set_value(0, 0, 0, 100.0)   # age 20 set
        # age 30 (index 1) NOT set → NaN
        # Querying at age 25 (between 20 and 30) should propagate NaN
        assert math.isnan(g.interpolate_age(0, 25.0, 0))

    def test_interpolation_different_scenarios(self):
        """Interpolation is per-scenario and not averaged across scenarios."""
        g = HybridGrid(1, [20, 40], 3)
        # scenario 0: 0 → 100; scenario 1: 0 → 200; scenario 2: 0 → 300
        for s, hi in enumerate([100.0, 200.0, 300.0]):
            g.set_value(0, 0, s, 0.0)
            g.set_value(0, 1, s, hi)
        # age=30 = midpoint
        assert g.interpolate_age(0, 30.0, 0) == pytest.approx(50.0)
        assert g.interpolate_age(0, 30.0, 1) == pytest.approx(100.0)
        assert g.interpolate_age(0, 30.0, 2) == pytest.approx(150.0)

    def test_multi_node_interpolation_correct_bracket(self):
        """With 4 nodes, interpolation picks the correct bracketing pair."""
        g = HybridGrid(1, [20, 30, 40, 50], 1)
        values = [10.0, 20.0, 50.0, 80.0]  # non-uniform spacing in y
        for a, v in enumerate(values):
            g.set_value(0, a, 0, v)
        # age 25 → between nodes 0 (age 20, v=10) and 1 (age 30, v=20)
        # alpha = (25-20)/(30-20) = 0.5; interp = 10 + 0.5*10 = 15
        assert g.interpolate_age(0, 25.0, 0) == pytest.approx(15.0)
        # age 45 → between nodes 2 (age 40, v=50) and 3 (age 50, v=80)
        # alpha = (45-40)/(50-40) = 0.5; interp = 50 + 0.5*30 = 65
        assert g.interpolate_age(0, 45.0, 0) == pytest.approx(65.0)


# ===========================================================================
# 6. Scenario aggregation
# ===========================================================================

class TestScenarioAggregation:

    def test_scenario_mean_simple(self):
        g = HybridGrid(1, [25], 4)
        for s, v in enumerate([10.0, 20.0, 30.0, 40.0]):
            g.set_value(0, 0, s, v)
        assert g.scenario_mean(0, 0) == pytest.approx(25.0)

    def test_scenario_mean_single_scenario(self):
        g = HybridGrid(1, [30], 1)
        g.set_value(0, 0, 0, 999.0)
        assert g.scenario_mean(0, 0) == pytest.approx(999.0)

    def test_scenario_mean_ignores_nan_by_default(self):
        """ignore_unset=True (default): NaN cells excluded from mean."""
        g = HybridGrid(1, [25], 4)
        g.set_value(0, 0, 0, 100.0)
        g.set_value(0, 0, 1, 200.0)
        # scenarios 2 and 3 remain NaN
        assert g.scenario_mean(0, 0) == pytest.approx(150.0)

    def test_scenario_mean_all_nan_returns_nan(self):
        g = HybridGrid(1, [25], 3)
        assert math.isnan(g.scenario_mean(0, 0))

    def test_scenario_mean_ignore_unset_false(self):
        """ignore_unset=False includes NaN → result is NaN."""
        g = HybridGrid(1, [25], 3)
        g.set_value(0, 0, 0, 100.0)
        result = g.scenario_mean(0, 0, ignore_unset=False)
        assert math.isnan(result)

    def test_scenario_percentile_median(self):
        g = HybridGrid(1, [30], 5)
        for s, v in enumerate([1.0, 2.0, 3.0, 4.0, 5.0]):
            g.set_value(0, 0, s, v)
        assert g.scenario_percentile(0, 0, 50) == pytest.approx(3.0)

    def test_scenario_percentile_99th_var(self):
        """99th percentile from 1000 uniform[0,1] samples ≈ 0.99."""
        rng = np.random.default_rng(42)
        vals = rng.uniform(0, 1, 1000)
        g = HybridGrid(1, [30], 1000)
        g.fill_scenario(0, 0, vals)
        p99 = g.scenario_percentile(0, 0, 99)
        assert 0.985 < p99 < 0.999

    def test_scenario_percentile_all_nan_returns_nan(self):
        g = HybridGrid(1, [30], 5)
        assert math.isnan(g.scenario_percentile(0, 0, 95))

    def test_fill_scenario_wrong_length_raises(self):
        g = HybridGrid(1, [30], 5)
        with pytest.raises(HybridGridError, match="n_scenarios"):
            g.fill_scenario(0, 0, [1.0, 2.0, 3.0])   # len=3, N=5


# ===========================================================================
# 7. Best-estimate value
# ===========================================================================

class TestBestEstimate:

    def test_be_single_scenario_equals_value(self):
        """With 1 scenario, best_estimate_value equals the stored value."""
        g = HybridGrid(1, [20, 40], 1)
        g.set_value(0, 0, 0, 100.0)
        g.set_value(0, 1, 0, 200.0)
        assert g.best_estimate_value(0, 30.0) == pytest.approx(150.0)

    def test_be_averages_across_scenarios(self):
        """best_estimate_value averages scenarios then interpolates age."""
        g = HybridGrid(1, [20, 40], 2)
        # Node 0 (age 20): scenarios 0→100, 1→200; mean=150
        # Node 1 (age 40): scenarios 0→300, 1→400; mean=350
        g.set_value(0, 0, 0, 100.0); g.set_value(0, 0, 1, 200.0)
        g.set_value(0, 1, 0, 300.0); g.set_value(0, 1, 1, 400.0)
        # age 30 midpoint → (150 + 350) / 2 = 250
        assert g.best_estimate_value(0, 30.0) == pytest.approx(250.0)

    def test_be_boundary_below_returns_youngest_mean(self):
        g = HybridGrid(12, [25, 35], 2)
        g.set_value(5, 0, 0, 100.0); g.set_value(5, 0, 1, 200.0)
        # age=10 < 25 → boundary → mean of node 0 = 150
        assert g.best_estimate_value(5, 10.0) == pytest.approx(150.0)

    def test_be_boundary_above_returns_oldest_mean(self):
        g = HybridGrid(12, [25, 35], 2)
        g.set_value(0, 1, 0, 400.0); g.set_value(0, 1, 1, 600.0)
        assert g.best_estimate_value(0, 99.0) == pytest.approx(500.0)

    def test_be_nan_when_unset(self):
        g = HybridGrid(12, [25, 35, 45], 1)
        # Only node 0 is set; querying between nodes 0 and 1 → NaN (node 1 unset)
        g.set_value(0, 0, 0, 100.0)
        assert math.isnan(g.best_estimate_value(0, 30.0))


# ===========================================================================
# 8. Degenerate inputs — AC4
# ===========================================================================

class TestDegenerateInputs:
    """AC4: Zero premium / zero sum-assured inputs handled without NaN output."""

    def test_zero_sum_assured_no_nan_from_factory(self):
        """Factory method with sum_assured=0 fills grid with zeros (not NaN)."""
        g = HybridGrid.from_liability_projection(
            projection_months=120,
            age_nodes=[25, 35, 45],
            n_scenarios=10,
            sum_assured=0.0,
            annual_premium=1000.0,
        )
        assert not g.has_nan()
        assert g.get_value(0, 0, 0) == pytest.approx(0.0)
        assert g.get_value(119, 2, 9) == pytest.approx(0.0)

    def test_zero_premium_no_nan_from_factory(self):
        """Factory method with annual_premium=0 fills grid with zeros (not NaN)."""
        g = HybridGrid.from_liability_projection(
            projection_months=60,
            age_nodes=[30, 45, 60],
            n_scenarios=5,
            sum_assured=100_000.0,
            annual_premium=0.0,
        )
        assert not g.has_nan()
        for t in range(60):
            for a in range(3):
                for s in range(5):
                    assert g.get_value(t, a, s) == pytest.approx(0.0)

    def test_both_zero_no_nan(self):
        """sum_assured=0 AND premium=0 still produces all-zero grid."""
        g = HybridGrid.from_liability_projection(
            projection_months=12,
            age_nodes=[25, 55],
            n_scenarios=3,
            sum_assured=0.0,
            annual_premium=0.0,
        )
        assert not g.has_nan()

    def test_zero_premium_interpolation_no_nan(self):
        """Interpolation on a zero-filled grid returns 0.0, not NaN."""
        g = HybridGrid.from_liability_projection(
            projection_months=12,
            age_nodes=[20, 30, 40, 50],
            n_scenarios=1,
            sum_assured=100_000.0,
            annual_premium=0.0,
        )
        for age in [20.0, 25.5, 35.0, 49.9, 50.0]:
            v = g.interpolate_age(t=0, age=age, scenario_idx=0)
            assert v == pytest.approx(0.0), f"age={age}: expected 0.0, got {v}"

    def test_zero_premium_best_estimate_no_nan(self):
        """best_estimate_value on zero-filled grid returns 0.0."""
        g = HybridGrid.from_liability_projection(
            projection_months=60,
            age_nodes=[25, 45, 65],
            n_scenarios=10,
            sum_assured=50_000.0,
            annual_premium=0.0,
        )
        assert g.best_estimate_value(0, 35.0) == pytest.approx(0.0)
        assert g.best_estimate_value(59, 55.0) == pytest.approx(0.0)

    def test_factory_with_valid_reserve_array(self):
        """from_liability_projection correctly populates grid from ndarray."""
        T, ages, N = 12, [25, 35, 45], 2
        arr = np.ones((T, len(ages), N)) * 500.0
        g = HybridGrid.from_liability_projection(
            projection_months=T,
            age_nodes=ages,
            n_scenarios=N,
            sum_assured=100_000.0,
            annual_premium=2000.0,
            reserve_values=arr,
        )
        assert not g.has_nan()
        assert g.get_value(5, 1, 1) == pytest.approx(500.0)

    def test_factory_wrong_reserve_shape_raises(self):
        """from_liability_projection raises HybridGridError if array shape mismatch."""
        with pytest.raises(HybridGridError, match="shape"):
            HybridGrid.from_liability_projection(
                projection_months=12,
                age_nodes=[25, 35],
                n_scenarios=3,
                sum_assured=100_000.0,
                annual_premium=2000.0,
                reserve_values=np.zeros((12, 2, 5)),   # N=5 ≠ 3
            )

    def test_very_small_premium_no_nan(self):
        """Epsilon-small premium is not zero → grid uses reserve_values or zero-fill."""
        g = HybridGrid.from_liability_projection(
            projection_months=12,
            age_nodes=[30, 50],
            n_scenarios=1,
            sum_assured=100_000.0,
            annual_premium=1e-10,   # tiny but non-zero
        )
        assert not g.has_nan()

    def test_set_value_zero_no_nan(self):
        """Directly setting a cell to 0.0 is valid and not NaN."""
        g = HybridGrid(12, [25, 35], 1)
        g.set_value(0, 0, 0, 0.0)
        val = g.get_value(0, 0, 0)
        assert val == pytest.approx(0.0)
        assert not math.isnan(val)


# ===========================================================================
# 9. Coverage and diagnostics
# ===========================================================================

class TestCoverageAndDiagnostics:

    def test_coverage_zero_on_fresh_grid(self):
        g = HybridGrid(6, [25, 35], 3)
        assert g.coverage_ratio() == pytest.approx(0.0)

    def test_coverage_full_after_fill_uniform(self):
        g = HybridGrid(4, [20, 30, 40], 2)
        g.fill_uniform(1.0)
        assert g.coverage_ratio() == pytest.approx(1.0)

    def test_coverage_partial(self):
        """Set exactly half the cells; coverage should be 0.5."""
        T, A, N = 2, 2, 2   # total = 8 cells
        g = HybridGrid(T, [20, 30], N)
        # Set 4 of 8 cells
        g.set_value(0, 0, 0, 1.0)
        g.set_value(0, 0, 1, 2.0)
        g.set_value(0, 1, 0, 3.0)
        g.set_value(0, 1, 1, 4.0)
        assert g.coverage_ratio() == pytest.approx(0.5)

    def test_has_nan_fresh(self):
        g = HybridGrid(3, [30], 2)
        assert g.has_nan()

    def test_has_nan_after_full_fill(self):
        g = HybridGrid(3, [30, 40], 2)
        g.fill_uniform(0.0)
        assert not g.has_nan()

    def test_has_nan_partial_fill(self):
        g = HybridGrid(3, [30, 40], 2)
        g.set_value(0, 0, 0, 1.0)   # only one cell set
        assert g.has_nan()

    def test_repr_contains_shape_info(self):
        g = HybridGrid(60, [25, 35, 45], 100)
        r = repr(g)
        assert "60" in r
        assert "100" in r

    def test_fill_uniform_then_no_nan(self):
        g = HybridGrid(12, [20, 30, 40, 50], 50)
        g.fill_uniform(0.0)
        assert not g.has_nan()
        assert g.coverage_ratio() == pytest.approx(1.0)


# ===========================================================================
# 10. IA VR-U07 acceptance-criteria walkthrough (combined suite)
# ===========================================================================

class TestIABoundaryConditionsSuite:
    """Explicit mapping to the four VR-U07 acceptance criteria to document
    that all IA TAS M §3.6.2 requirements are met."""

    def test_ac1_shape_matches_term_age_scenario(self):
        """AC1: Grid shape matches expected (term × age × scenario) dimensions."""
        for term_years in (5, 10, 20):
            T = term_years * 12
            ages = [25, 30, 35, 40, 45, 50]
            N = 500
            g = HybridGrid(T, ages, N)
            assert g.shape == (T, len(ages), N), (
                f"term={term_years}Y: expected ({T},{len(ages)},{N}), "
                f"got {g.shape}"
            )

    def test_ac2_boundary_age0_final_month_correct(self):
        """AC2: Boundary cells (age=0 node, final projection month) return
        correct stored values."""
        T, ages, N = 120, [20, 35, 55], 10
        g = HybridGrid(T, ages, N)

        # Populate only the four extreme corners
        for s in range(N):
            g.set_value(0,     0,  s, 1000.0 + s)   # (t=0,    youngest)
            g.set_value(T - 1, 0,  s, 2000.0 + s)   # (t=T-1,  youngest)
            g.set_value(0,     2,  s, 3000.0 + s)   # (t=0,    oldest)
            g.set_value(T - 1, 2,  s, 4000.0 + s)   # (t=T-1,  oldest)

        for s in range(N):
            assert g.get_value(0,     0, s) == pytest.approx(1000.0 + s)
            assert g.get_value(T - 1, 0, s) == pytest.approx(2000.0 + s)
            assert g.get_value(0,     2, s) == pytest.approx(3000.0 + s)
            assert g.get_value(T - 1, 2, s) == pytest.approx(4000.0 + s)

    def test_ac3_interpolation_monotone(self):
        """AC3: Interpolation between grid nodes is monotone where expected."""
        # Reserves decrease monotonically from youngest to oldest age
        # (older lives have fewer future premiums → lower reserve)
        T = 1
        ages = [20, 25, 30, 35, 40, 45, 50, 55, 60]
        values = [5000, 4500, 4000, 3500, 3000, 2500, 2000, 1500, 1000]
        N = 1
        g = HybridGrid(T, ages, N)
        for a, v in enumerate(values):
            g.set_value(0, a, 0, float(v))

        query_ages = np.linspace(20, 60, 200)
        interp_vals = [g.interpolate_age(0, float(a), 0) for a in query_ages]

        # Strict monotone decreasing check
        violations = []
        for i in range(len(interp_vals) - 1):
            if interp_vals[i] < interp_vals[i + 1] - 1e-9:
                violations.append((query_ages[i], interp_vals[i], interp_vals[i+1]))
        assert not violations, (
            f"Monotonicity violated at {len(violations)} points; "
            f"first: age≈{violations[0][0]:.2f}, "
            f"v={violations[0][1]:.4f} < {violations[0][2]:.4f}"
        )

    def test_ac4_zero_premium_no_nan_end_to_end(self):
        """AC4: Zero premium / zero sum-assured inputs handled without NaN."""
        # Scenario A: zero sum assured
        g_zero_sa = HybridGrid.from_liability_projection(
            projection_months=120,
            age_nodes=[25, 35, 45, 55],
            n_scenarios=100,
            sum_assured=0.0,
            annual_premium=3600.0,
        )
        assert not g_zero_sa.has_nan(), "zero SA: grid contains NaN"
        # Interpolation
        for t in [0, 60, 119]:
            for age in [25.0, 35.0, 45.0, 50.0, 55.0]:
                v = g_zero_sa.interpolate_age(t, age, 0)
                assert not math.isnan(v), f"zero SA: NaN at t={t}, age={age}"

        # Scenario B: zero annual premium
        g_zero_prem = HybridGrid.from_liability_projection(
            projection_months=60,
            age_nodes=[30, 40, 50, 60],
            n_scenarios=50,
            sum_assured=500_000.0,
            annual_premium=0.0,
        )
        assert not g_zero_prem.has_nan(), "zero premium: grid contains NaN"
        be = g_zero_prem.best_estimate_value(0, 45.0)
        assert not math.isnan(be), "zero premium: best_estimate_value returned NaN"
        assert be == pytest.approx(0.0)
