"""
Tests — Scenario Stress Testing Framework
==========================================

Validates par_model_v2.risk.stress_testing against:
  - SOA ASOP 7 §3.5 scenario requirements
  - CBIRC C-ROSS prescribed test coverage
  - ERM multi-factor scenario completeness
  - Numerical correctness of duration approximations
  - Governance: report structure and regulatory citation completeness
"""

from __future__ import annotations

import math
import warnings
from datetime import datetime, timezone

import numpy as np
import pytest

from par_model_v2.risk.stress_testing import (
    ALL_SCENARIOS,
    CBIRC_SCENARIOS,
    COMBINED_SCENARIOS,
    SOA_ASOP7_SCENARIOS,
    PortfolioSnapshot,
    ScenarioCategory,
    ShockSpec,
    ShockType,
    StressScenario,
    StressTestEngine,
    StressTestResult,
    run_regulatory_stress_test,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

VALUATION_DATE = datetime(2026, 3, 31, tzinfo=timezone.utc)


@pytest.fixture
def base_portfolio() -> PortfolioSnapshot:
    """Representative PAR fund balance sheet (CNY, stylised).

    Bond portfolio (government):   700,000
    Equity (CSI 300 proxy):        200,000
    Credit bonds (corporate):       50,000
    Other (cash / property):        50,000
    -----------------------------------------
    Total assets:                1,000,000
    Liability PV:                  950,000
    Free surplus:                   50,000
    Solvency ratio:               1.0526

    Duration / convexity assumptions:
      Bond:           8yr duration, 80yr² convexity
      Credit bond:    4yr duration
      Liability:     12yr duration, 200yr² convexity
    Sensitivities:
      Lapse:         −2,000 CNY per +1pp lapse
      Mortality:     +3,000 CNY per ×0.1 mortality multiplier
    """
    return PortfolioSnapshot(
        valuation_date=VALUATION_DATE,
        bond_mv=700_000.0,
        bond_duration=8.0,
        bond_convexity=80.0,
        equity_mv=200_000.0,
        credit_bond_mv=50_000.0,
        credit_bond_duration=4.0,
        other_assets=50_000.0,
        liability_pv=950_000.0,
        liability_duration=12.0,
        liability_convexity=200.0,
        discount_rate=0.035,
        lapse_sensitivity=-2_000.0,
        mortality_sensitivity=3_000.0,
    )


@pytest.fixture
def engine(base_portfolio: PortfolioSnapshot) -> StressTestEngine:
    return StressTestEngine(base_portfolio, warn_on_approximation=False)


# ---------------------------------------------------------------------------
# 1.  Portfolio snapshot basics
# ---------------------------------------------------------------------------

class TestPortfolioSnapshot:

    def test_total_assets(self, base_portfolio: PortfolioSnapshot) -> None:
        assert base_portfolio.total_assets == pytest.approx(1_000_000.0)

    def test_surplus(self, base_portfolio: PortfolioSnapshot) -> None:
        assert base_portfolio.surplus == pytest.approx(50_000.0)

    def test_solvency_ratio(self, base_portfolio: PortfolioSnapshot) -> None:
        expected = 1_000_000.0 / 950_000.0
        assert base_portfolio.solvency_ratio == pytest.approx(expected, rel=1e-6)

    def test_zero_liability_solvency(self) -> None:
        snap = PortfolioSnapshot(
            valuation_date=VALUATION_DATE,
            bond_mv=100_000.0, bond_duration=5.0, bond_convexity=25.0,
            equity_mv=0.0, credit_bond_mv=0.0, credit_bond_duration=0.0,
            other_assets=0.0, liability_pv=0.0,
            liability_duration=0.0, liability_convexity=0.0,
            discount_rate=0.03, lapse_sensitivity=0.0, mortality_sensitivity=0.0,
        )
        assert math.isinf(snap.solvency_ratio)


# ---------------------------------------------------------------------------
# 2.  Shock specification
# ---------------------------------------------------------------------------

class TestShockSpec:

    def test_valid_construction(self) -> None:
        s = ShockSpec(ShockType.RATE_PARALLEL, 200.0, "200bps up")
        assert s.shock_type == ShockType.RATE_PARALLEL
        assert s.magnitude == 200.0

    def test_invalid_shock_type(self) -> None:
        with pytest.raises(TypeError):
            ShockSpec("not_a_type", 100.0)  # type: ignore[arg-type]

    def test_immutability(self) -> None:
        s = ShockSpec(ShockType.EQUITY_PRICE, -0.30)
        with pytest.raises(Exception):  # frozen dataclass raises FrozenInstanceError
            s.magnitude = 0.0  # type: ignore[misc]


# ---------------------------------------------------------------------------
# 3.  Scenario library completeness (SOA / CBIRC coverage)
# ---------------------------------------------------------------------------

class TestScenarioLibrary:

    def test_cbirc_scenario_count(self) -> None:
        """CBIRC C-ROSS requires ≥6 prescribed stress tests (§5.2–5.3)."""
        assert len(CBIRC_SCENARIOS) >= 6

    def test_soa_asop7_scenario_count(self) -> None:
        """SOA ASOP 7 §3.5 — minimum 4 scenario types (rate, equity, lapse, mortality)."""
        assert len(SOA_ASOP7_SCENARIOS) >= 4

    def test_erm_combined_scenarios_present(self) -> None:
        assert len(COMBINED_SCENARIOS) >= 4

    def test_all_scenarios_contains_all_groups(self) -> None:
        names = {s.name for s in ALL_SCENARIOS}
        for scenario in CBIRC_SCENARIOS + SOA_ASOP7_SCENARIOS + COMBINED_SCENARIOS:
            assert scenario.name in names

    def test_cbirc_rate_up_200_present(self) -> None:
        names = [s.name for s in CBIRC_SCENARIOS]
        assert "CBIRC-IR-UP200" in names

    def test_cbirc_rate_down_200_present(self) -> None:
        names = [s.name for s in CBIRC_SCENARIOS]
        assert "CBIRC-IR-DOWN200" in names

    def test_cbirc_equity_down_40_present(self) -> None:
        names = [s.name for s in CBIRC_SCENARIOS]
        assert "CBIRC-EQ-DOWN40" in names

    def test_reverse_stress_in_erm(self) -> None:
        names = [s.name for s in COMBINED_SCENARIOS]
        assert "ERM-REVERSE-STRESS" in names

    def test_all_scenarios_have_regulatory_reference(self) -> None:
        """Every scenario must cite a governing standard for audit trail."""
        for s in ALL_SCENARIOS:
            assert s.regulatory_reference, (
                f"Scenario {s.name} is missing a regulatory_reference"
            )

    def test_all_scenarios_have_at_least_one_shock(self) -> None:
        for s in ALL_SCENARIOS:
            assert len(s.shocks) >= 1, f"{s.name} has no shocks"

    def test_severity_values_valid(self) -> None:
        valid = {"mild", "moderate", "severe", "extreme"}
        for s in ALL_SCENARIOS:
            assert s.severity in valid, f"{s.name} has invalid severity '{s.severity}'"

    def test_shock_by_type_found(self) -> None:
        scenario = next(s for s in CBIRC_SCENARIOS if s.name == "CBIRC-IR-UP200")
        shock = scenario.shock_by_type(ShockType.RATE_PARALLEL)
        assert shock is not None
        assert shock.magnitude == pytest.approx(200.0)

    def test_shock_by_type_not_found(self) -> None:
        scenario = next(s for s in CBIRC_SCENARIOS if s.name == "CBIRC-IR-UP200")
        assert scenario.shock_by_type(ShockType.EQUITY_PRICE) is None

    def test_unique_scenario_names(self) -> None:
        names = [s.name for s in ALL_SCENARIOS]
        assert len(names) == len(set(names)), "Duplicate scenario names found"


# ---------------------------------------------------------------------------
# 4.  Rate shock numerical correctness
# ---------------------------------------------------------------------------

class TestRateShockNumerics:

    def test_rate_up_200bps_bond_decreases(self, engine: StressTestEngine) -> None:
        """Bond MV falls when rates rise (positive duration)."""
        scenario = next(s for s in CBIRC_SCENARIOS if s.name == "CBIRC-IR-UP200")
        result = engine.apply_scenario(scenario)
        assert result.stressed_bond_mv < engine.portfolio.bond_mv

    def test_rate_down_200bps_bond_increases(self, engine: StressTestEngine) -> None:
        """Bond MV rises when rates fall."""
        scenario = next(s for s in CBIRC_SCENARIOS if s.name == "CBIRC-IR-DOWN200")
        result = engine.apply_scenario(scenario)
        assert result.stressed_bond_mv > engine.portfolio.bond_mv

    def test_rate_up_200bps_bond_change_approximate(
        self, engine: StressTestEngine
    ) -> None:
        """
        ΔBond ≈ −D × Δy + 0.5 × C × Δy² (duration + convexity).
        D=8, C=80, Δy=0.02, MV=700,000
        Expected: −8×0.02×700,000 + 0.5×80×0.02²×700,000
               = −112,000 + 11,200 = −100,800
        """
        scenario = next(s for s in CBIRC_SCENARIOS if s.name == "CBIRC-IR-UP200")
        result = engine.apply_scenario(scenario)
        expected_delta = -8.0 * 0.02 * 700_000 + 0.5 * 80.0 * 0.02 ** 2 * 700_000
        actual_delta = result.stressed_bond_mv - engine.portfolio.bond_mv
        assert actual_delta == pytest.approx(expected_delta, rel=1e-6)

    def test_rate_shock_liability_moves_opposite_direction(
        self, engine: StressTestEngine
    ) -> None:
        """
        For rate up 200bps: bond MV falls, liability PV also falls.

        Dollar-duration comparison:
          Asset DV01   ≈ (700k×8 + 50k×4) / 10,000 = 580
          Liab  DV01   ≈ 950k×12 / 10,000            = 1,140

        Since Liab DV01 > Asset DV01, a rate RISE reduces liabilities MORE
        than it reduces assets → net surplus INCREASES (rate-up is beneficial
        for this particular ALM mismatch configuration).

        Surplus change = base_surplus − stressed_surplus < 0 means improvement.
        """
        scenario = next(s for s in CBIRC_SCENARIOS if s.name == "CBIRC-IR-UP200")
        result = engine.apply_scenario(scenario)
        # Liability dollar-duration exceeds asset dollar-duration → rate up improves surplus
        assert result.surplus_change < 0  # surplus improved (liability fell more)

    def test_rate_down_net_effect_adverse(self, engine: StressTestEngine) -> None:
        """
        Rate down 200bps: bond MV rises, liability PV rises more (longer dur).
        Net surplus should fall (adverse) — confirms ALM duration mismatch.
        """
        scenario = next(s for s in CBIRC_SCENARIOS if s.name == "CBIRC-IR-DOWN200")
        result = engine.apply_scenario(scenario)
        assert result.surplus_change > 0  # adverse

    def test_zero_duration_no_repricing(self, base_portfolio: PortfolioSnapshot) -> None:
        """Portfolio with zero duration assets/liabilities should be immune to rate shocks."""
        snap = PortfolioSnapshot(
            valuation_date=VALUATION_DATE,
            bond_mv=500_000.0, bond_duration=0.0, bond_convexity=0.0,
            equity_mv=0.0, credit_bond_mv=0.0, credit_bond_duration=0.0,
            other_assets=100_000.0, liability_pv=550_000.0,
            liability_duration=0.0, liability_convexity=0.0,
            discount_rate=0.03, lapse_sensitivity=0.0, mortality_sensitivity=0.0,
        )
        eng = StressTestEngine(snap, warn_on_approximation=False)
        scenario = next(s for s in CBIRC_SCENARIOS if s.name == "CBIRC-IR-UP200")
        result = eng.apply_scenario(scenario)
        assert result.stressed_bond_mv == pytest.approx(500_000.0, rel=1e-9)
        assert result.stressed_liability_pv == pytest.approx(550_000.0, rel=1e-9)


# ---------------------------------------------------------------------------
# 5.  Equity shock
# ---------------------------------------------------------------------------

class TestEquityShock:

    def test_equity_down_40_reduces_equity_mv(self, engine: StressTestEngine) -> None:
        scenario = next(s for s in CBIRC_SCENARIOS if s.name == "CBIRC-EQ-DOWN40")
        result = engine.apply_scenario(scenario)
        expected = 200_000.0 * (1 - 0.40)
        assert result.stressed_equity_mv == pytest.approx(expected, rel=1e-9)

    def test_equity_negative_mv_floored_at_zero(self) -> None:
        """Equity MV cannot go below zero (limited liability)."""
        snap = PortfolioSnapshot(
            valuation_date=VALUATION_DATE,
            bond_mv=0.0, bond_duration=0.0, bond_convexity=0.0,
            equity_mv=100.0, credit_bond_mv=0.0, credit_bond_duration=0.0,
            other_assets=0.0, liability_pv=50.0,
            liability_duration=0.0, liability_convexity=0.0,
            discount_rate=0.03, lapse_sensitivity=0.0, mortality_sensitivity=0.0,
        )
        # Apply equity −110% shock (exceeds full value)
        extreme_shock = StressScenario(
            name="EXTREME-EQ",
            category=ScenarioCategory.SENSITIVITY,
            description="Extreme equity shock test (floor validation)",
            shocks=(ShockSpec(ShockType.EQUITY_PRICE, -1.50, "−150% shock"),),
            regulatory_reference="Test only",
        )
        eng = StressTestEngine(snap, scenarios=[extreme_shock], warn_on_approximation=False)
        result = eng.apply_scenario(extreme_shock)
        assert result.stressed_equity_mv == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# 6.  Lapse shock
# ---------------------------------------------------------------------------

class TestLapseShock:

    def test_positive_lapse_shock_reduces_liabilities(
        self, engine: StressTestEngine
    ) -> None:
        """Higher lapse reduces policy count, reducing liability PV (negative sensitivity)."""
        scenario = next(s for s in CBIRC_SCENARIOS if s.name == "CBIRC-LAPSE-SHOCK")
        result = engine.apply_scenario(scenario)
        # lapse_sensitivity = -2000 per +1pp, shock = +30pp → delta = -60,000
        expected_delta = -2_000.0 * 30.0   # +30pp × 100 = 3000 units? No: +0.30*100=30
        # delta = lapse_sensitivity × (0.30 * 100) = -2000 × 30 = -60,000
        # So liability should fall by 60,000
        base_liab = engine.portfolio.liability_pv   # 950,000
        # stressed liab ≈ 950,000 - 60,000 = 890,000 (ignoring rate shock, none here)
        assert result.stressed_liability_pv == pytest.approx(
            base_liab + expected_delta, rel=1e-6
        )

    def test_lapse_shock_detail_recorded(self, engine: StressTestEngine) -> None:
        scenario = next(s for s in CBIRC_SCENARIOS if s.name == "CBIRC-LAPSE-SHOCK")
        result = engine.apply_scenario(scenario)
        assert "liability_lapse_change" in result.shock_details


# ---------------------------------------------------------------------------
# 7.  Mortality shock
# ---------------------------------------------------------------------------

class TestMortalityShock:

    def test_mortality_increase_raises_liabilities(
        self, engine: StressTestEngine
    ) -> None:
        scenario = next(s for s in SOA_ASOP7_SCENARIOS if s.name == "SOA-MORTALITY-UP10")
        result = engine.apply_scenario(scenario)
        # mortality_sensitivity = 3000 per ×0.1 multiplier change; ×1.10 → +0.10 change
        # delta = 3000 × (0.10 / 0.10) = 3000
        expected_liab_increase = 3_000.0
        delta = result.stressed_liability_pv - engine.portfolio.liability_pv
        assert delta == pytest.approx(expected_liab_increase, rel=1e-6)

    def test_zero_mortality_sensitivity_no_change(
        self, base_portfolio: PortfolioSnapshot
    ) -> None:
        snap = PortfolioSnapshot(
            valuation_date=VALUATION_DATE,
            bond_mv=500_000.0, bond_duration=5.0, bond_convexity=25.0,
            equity_mv=100_000.0, credit_bond_mv=0.0, credit_bond_duration=0.0,
            other_assets=0.0, liability_pv=550_000.0,
            liability_duration=7.0, liability_convexity=50.0,
            discount_rate=0.03, lapse_sensitivity=0.0, mortality_sensitivity=0.0,
        )
        scenario = next(s for s in SOA_ASOP7_SCENARIOS if s.name == "SOA-MORTALITY-UP10")
        eng = StressTestEngine(snap, warn_on_approximation=False)
        result = eng.apply_scenario(scenario)
        # Mortality change should be 0
        assert result.shock_details["liability_mortality_change"] == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# 8.  Combined scenarios
# ---------------------------------------------------------------------------

class TestCombinedScenarios:

    def test_cbirc_combined_crisis_has_three_shocks(self) -> None:
        scenario = next(s for s in CBIRC_SCENARIOS if s.name == "CBIRC-COMBINED-CRISIS")
        assert len(scenario.shocks) == 3

    def test_deflation_trap_most_adverse_for_par_fund(
        self, engine: StressTestEngine
    ) -> None:
        """Deflation trap (rates −300bps, equity −50%) should be among the worst."""
        results = engine.run_all_scenarios()
        deflation = next(
            r for r in results if r.scenario.name == "ERM-DEFLATION-TRAP"
        )
        surplus_changes = [r.surplus_change for r in results]
        # Deflation trap should be in the top-3 worst
        sorted_changes = sorted(surplus_changes, reverse=True)
        rank = sorted_changes.index(deflation.surplus_change)
        assert rank <= 2, (
            f"ERM-DEFLATION-TRAP should be top-3 worst; got rank {rank}"
        )

    def test_reverse_stress_produces_insolvent_or_near_insolvent(
        self, engine: StressTestEngine
    ) -> None:
        """ERM-REVERSE-STRESS is calibrated to be the most adverse scenario."""
        scenario = next(s for s in COMBINED_SCENARIOS if s.name == "ERM-REVERSE-STRESS")
        result = engine.apply_scenario(scenario)
        # Surplus should drop significantly (>50%)
        assert result.surplus_change_pct > 50.0


# ---------------------------------------------------------------------------
# 9.  Vol and FX shocks emit warnings
# ---------------------------------------------------------------------------

class TestApproximationWarnings:

    def test_vol_shock_emits_warning(self, base_portfolio: PortfolioSnapshot) -> None:
        vol_scenario = StressScenario(
            name="TEST-VOL",
            category=ScenarioCategory.SENSITIVITY,
            description="Test vol shock warning",
            shocks=(ShockSpec(ShockType.EQUITY_VOL, 2.0, "Vol ×2"),),
            regulatory_reference="Test",
        )
        eng = StressTestEngine(
            base_portfolio, scenarios=[vol_scenario], warn_on_approximation=True
        )
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            eng.apply_scenario(vol_scenario)
        assert any("EQUITY_VOL" in str(w.message) for w in caught)

    def test_fx_shock_emits_warning(self, base_portfolio: PortfolioSnapshot) -> None:
        fx_scenario = StressScenario(
            name="TEST-FX",
            category=ScenarioCategory.SENSITIVITY,
            description="Test FX shock warning",
            shocks=(ShockSpec(ShockType.FX, -0.10, "FX −10%"),),
            regulatory_reference="Test",
        )
        eng = StressTestEngine(
            base_portfolio, scenarios=[fx_scenario], warn_on_approximation=True
        )
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            eng.apply_scenario(fx_scenario)
        assert any("FX" in str(w.message) for w in caught)


# ---------------------------------------------------------------------------
# 10.  Run all scenarios
# ---------------------------------------------------------------------------

class TestRunAllScenarios:

    def test_run_all_returns_correct_count(self, engine: StressTestEngine) -> None:
        results = engine.run_all_scenarios()
        assert len(results) == len(ALL_SCENARIOS)

    def test_all_results_have_scenario_name(self, engine: StressTestEngine) -> None:
        results = engine.run_all_scenarios()
        for r in results:
            assert r.scenario.name

    def test_run_subset_scenarios(self, engine: StressTestEngine) -> None:
        results = engine.run_all_scenarios(CBIRC_SCENARIOS)
        assert len(results) == len(CBIRC_SCENARIOS)

    def test_results_are_stress_test_result_instances(
        self, engine: StressTestEngine
    ) -> None:
        results = engine.run_all_scenarios()
        assert all(isinstance(r, StressTestResult) for r in results)


# ---------------------------------------------------------------------------
# 11.  Generate report (DataFrame)
# ---------------------------------------------------------------------------

class TestGenerateReport:

    def test_report_returns_dataframe(self, engine: StressTestEngine) -> None:
        import pandas as pd
        df = engine.generate_report()
        assert isinstance(df, pd.DataFrame)

    def test_report_has_correct_columns(self, engine: StressTestEngine) -> None:
        df = engine.generate_report()
        required_cols = {
            "scenario", "category", "severity", "regulatory_reference",
            "base_assets", "stressed_assets",
            "base_liabilities", "stressed_liabilities",
            "base_surplus", "stressed_surplus",
            "surplus_change", "surplus_change_pct",
            "base_solvency_ratio", "stressed_solvency_ratio",
            "solvency_ratio_change", "is_insolvent",
        }
        assert required_cols.issubset(set(df.columns))

    def test_report_sorted_worst_first(self, engine: StressTestEngine) -> None:
        df = engine.generate_report(sort_by="surplus_change", ascending=False)
        changes = df["surplus_change"].tolist()
        assert changes == sorted(changes, reverse=True)

    def test_report_row_count_matches_scenarios(self, engine: StressTestEngine) -> None:
        df = engine.generate_report()
        assert len(df) == len(ALL_SCENARIOS)

    def test_base_values_consistent(self, engine: StressTestEngine) -> None:
        """Base surplus and solvency ratio should be the same in every row."""
        df = engine.generate_report()
        assert df["base_surplus"].nunique() == 1
        assert df["base_solvency_ratio"].nunique() == 1


# ---------------------------------------------------------------------------
# 12.  Markdown report
# ---------------------------------------------------------------------------

class TestMarkdownReport:

    def test_markdown_contains_scenario_names(self, engine: StressTestEngine) -> None:
        md = engine.generate_markdown_report()
        for s in CBIRC_SCENARIOS:
            assert s.name in md, f"Scenario {s.name} missing from markdown report"

    def test_markdown_contains_regulatory_headers(
        self, engine: StressTestEngine
    ) -> None:
        md = engine.generate_markdown_report()
        assert "CBIRC C-ROSS" in md
        assert "SOA ASOP 7" in md
        assert "IA TAS M" in md

    def test_markdown_contains_base_portfolio_section(
        self, engine: StressTestEngine
    ) -> None:
        md = engine.generate_markdown_report()
        assert "Base Portfolio" in md

    def test_markdown_contains_solvency_ratio(self, engine: StressTestEngine) -> None:
        md = engine.generate_markdown_report()
        assert "Solvency Ratio" in md

    def test_markdown_contains_approximation_note(
        self, engine: StressTestEngine
    ) -> None:
        md = engine.generate_markdown_report()
        assert "Duration" in md or "approximation" in md.lower()


# ---------------------------------------------------------------------------
# 13.  Convenience function
# ---------------------------------------------------------------------------

class TestRunRegulatoryStressTest:

    def test_returns_dataframe(self, base_portfolio: PortfolioSnapshot) -> None:
        import pandas as pd
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            df = run_regulatory_stress_test(base_portfolio)
        assert isinstance(df, pd.DataFrame)

    def test_includes_cbirc_scenarios(self, base_portfolio: PortfolioSnapshot) -> None:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            df = run_regulatory_stress_test(base_portfolio)
        cbirc_names = {s.name for s in CBIRC_SCENARIOS}
        result_names = set(df["scenario"].tolist())
        assert cbirc_names.issubset(result_names)

    def test_exclude_erm_option(self, base_portfolio: PortfolioSnapshot) -> None:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            df = run_regulatory_stress_test(base_portfolio, include_erm=False)
        erm_names = {s.name for s in COMBINED_SCENARIOS}
        result_names = set(df["scenario"].tolist())
        assert erm_names.isdisjoint(result_names)


# ---------------------------------------------------------------------------
# 14.  StressTestResult properties
# ---------------------------------------------------------------------------

class TestStressTestResultProperties:

    def test_insolvent_flag_when_surplus_negative(
        self, engine: StressTestEngine
    ) -> None:
        scenario = next(s for s in COMBINED_SCENARIOS if s.name == "ERM-REVERSE-STRESS")
        result = engine.apply_scenario(scenario)
        # If stressed surplus < 0, is_insolvent must be True
        assert result.is_insolvent == (result.stressed_surplus < 0)

    def test_surplus_change_direction(self, engine: StressTestEngine) -> None:
        """surplus_change = base_surplus − stressed_surplus (positive = adverse)."""
        scenario = next(s for s in CBIRC_SCENARIOS if s.name == "CBIRC-EQ-DOWN40")
        result = engine.apply_scenario(scenario)
        expected = result.base_snapshot.surplus - result.stressed_surplus
        assert result.surplus_change == pytest.approx(expected, rel=1e-9)

    def test_to_dict_keys(self, engine: StressTestEngine) -> None:
        scenario = CBIRC_SCENARIOS[0]
        result = engine.apply_scenario(scenario)
        d = result.to_dict()
        assert "scenario" in d
        assert "is_insolvent" in d
        assert "surplus_change_pct" in d

    def test_surplus_change_pct_nan_when_base_zero(self) -> None:
        """Surplus change % should be nan when base surplus is zero."""
        snap = PortfolioSnapshot(
            valuation_date=VALUATION_DATE,
            bond_mv=500_000.0, bond_duration=5.0, bond_convexity=0.0,
            equity_mv=0.0, credit_bond_mv=0.0, credit_bond_duration=0.0,
            other_assets=0.0, liability_pv=500_000.0,  # surplus = 0
            liability_duration=5.0, liability_convexity=0.0,
            discount_rate=0.03, lapse_sensitivity=0.0, mortality_sensitivity=0.0,
        )
        eng = StressTestEngine(snap, warn_on_approximation=False)
        result = eng.apply_scenario(CBIRC_SCENARIOS[0])
        assert math.isnan(result.surplus_change_pct)


# ---------------------------------------------------------------------------
# 15.  Integration: full run produces internally consistent results
# ---------------------------------------------------------------------------

class TestIntegration:

    def test_base_surplus_unchanged_across_scenarios(
        self, engine: StressTestEngine
    ) -> None:
        results = engine.run_all_scenarios()
        base_surplus = engine.portfolio.surplus
        for r in results:
            assert r.base_snapshot.surplus == pytest.approx(base_surplus)

    def test_all_stressed_assets_non_negative(self, engine: StressTestEngine) -> None:
        results = engine.run_all_scenarios()
        for r in results:
            assert r.stressed_total_assets >= 0.0, (
                f"Negative total assets in scenario {r.scenario.name}"
            )

    def test_all_stressed_liabilities_non_negative(
        self, engine: StressTestEngine
    ) -> None:
        results = engine.run_all_scenarios()
        for r in results:
            assert r.stressed_liability_pv >= 0.0

    def test_solvency_ratio_change_sign_consistent(
        self, engine: StressTestEngine
    ) -> None:
        """If stressed surplus falls, solvency ratio should also fall (for given liab)."""
        results = engine.run_all_scenarios()
        for r in results:
            # solvency_ratio_change should be negative when stressed_surplus < base_surplus
            if r.stressed_surplus < r.base_snapshot.surplus:
                assert r.solvency_ratio_change <= 0.0 + 1e-9, (
                    f"Scenario {r.scenario.name}: surplus fell but solvency ratio rose"
                )
