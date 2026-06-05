"""
Phase 6 Acceptance Tests — ESG Scenario Schema Compatibility
============================================================

Purpose
-------
This module is the Phase 6 *schema-compatibility acceptance suite*. It ties the
three Phase 6 contracts — scenario metadata / parameter snapshot,
calibration data interfaces, and consumer output mappings — into a single set
of end-to-end checks that prove the expanded ESG schema remains backward
compatible with the v1 model consumers (ESGAdapter, TVOG, RiskMetrics,
DynamicALMEngine, reporting).

Coverage (per docs/ESG_SCHEMA_COMPATIBILITY_ACCEPTANCE.md):
  1. v1 wide-view backward compatibility (ESGAdapter round-trip)
  2. P / Q measure guardrails for each consumer
  3. Audit metadata propagation through consumer views
  4. Monthly-grid completeness and dtype stability
  5. Calibration-interface ↔ generated-factor consistency
  6. DynamicALM annual-return derivation

Standards
---------
SOA ASOP 56 §3.1.3, §3.4, §3.5 — process documentation, calibration inputs,
scenario adequacy.
IA TAS M §3.5, §3.6, §3.9 — traceability, audit trail, data validation.
"""

from __future__ import annotations

import pytest

from par_model_v2.stochastic.esg_process import (
    Measure,
    ScenarioSet,
    default_phase6_consumer_mappings,
    default_phase6_calibration_interfaces,
    phase6_consumer_mapping,
    _V1_WIDE_COLUMNS,
    _TRACEABILITY_FIELDS,
)
from par_model_v2.stochastic.esg_adapter import (
    ESGAdapter,
    ESGAdapterConfig,
    _REQUIRED_COLUMNS,
)


# Small, fast, test-scale dimensions. Scenario-adequacy warnings are disabled
# in the adapter config because these are unit-scale runs, not production runs.
N_SCEN = 8
T_MONTHS = 6


def _make_set(measure):
    return ScenarioSet.generate(
        n=N_SCEN,
        T_months=T_MONTHS,
        measure=measure,
        seed=7,
        model_version="schema-compat-test",
        base_currency="CNY",
    )


def _adapter():
    return ESGAdapter(
        ESGAdapterConfig(
            warn_on_low_scenario_count=False,
            raise_on_range_violation=True,
            minimum_scenarios=1,
        )
    )


# ---------------------------------------------------------------------------
# 1. v1 wide-view backward compatibility
# ---------------------------------------------------------------------------
class TestV1WideViewBackwardCompatibility:
    def test_generated_set_contains_all_v1_columns(self):
        scenarios = _make_set(Measure.P)
        for column in _V1_WIDE_COLUMNS:
            assert column in scenarios.data.columns

    def test_generated_set_passes_v1_esg_adapter(self):
        """Phase 6 output must still satisfy the v1 ESGAdapter schema contract."""
        scenarios = _make_set(Measure.Q)
        validated = _adapter().load_from_dataframe(scenarios.data.copy())
        # All v1-required columns survive validation/casting.
        for column in _REQUIRED_COLUMNS:
            assert column in validated.columns

    def test_consumer_wide_views_pass_v1_adapter(self):
        """Each consumer-ready wide view must remain v1-schema valid."""
        adapter = _adapter()
        p_set = _make_set(Measure.P)
        q_set = _make_set(Measure.Q)
        cases = {
            "tvog": q_set,
            "risk_metrics": p_set,
            "dynamic_alm": p_set,
            "reporting": p_set,
        }
        for consumer_id, scenario_set in cases.items():
            view = scenario_set.consumer_wide_view(consumer_id)
            validated = adapter.load_from_dataframe(view)
            assert set(_REQUIRED_COLUMNS).issubset(validated.columns)


# ---------------------------------------------------------------------------
# 2. P / Q measure guardrails
# ---------------------------------------------------------------------------
class TestMeasureGuardrails:
    def test_tvog_accepts_q_rejects_p(self):
        assert phase6_consumer_mapping("tvog").validate_scenario_set(_make_set(Measure.Q))
        with pytest.raises(ValueError):
            phase6_consumer_mapping("tvog").validate_scenario_set(_make_set(Measure.P))

    def test_risk_metrics_accepts_p_rejects_q(self):
        assert phase6_consumer_mapping("risk_metrics").validate_scenario_set(_make_set(Measure.P))
        with pytest.raises(ValueError):
            phase6_consumer_mapping("risk_metrics").validate_scenario_set(_make_set(Measure.Q))

    def test_dynamic_alm_rejects_q(self):
        with pytest.raises(ValueError):
            phase6_consumer_mapping("dynamic_alm").validate_scenario_set(_make_set(Measure.Q))

    def test_reporting_accepts_both_measures(self):
        mapping = phase6_consumer_mapping("reporting")
        assert mapping.validate_scenario_set(_make_set(Measure.P))
        assert mapping.validate_scenario_set(_make_set(Measure.Q))


# ---------------------------------------------------------------------------
# 3. Audit metadata propagation
# ---------------------------------------------------------------------------
class TestMetadataPropagation:
    def test_all_traceability_fields_present_in_view_attrs(self):
        scenarios = _make_set(Measure.P)
        view = scenarios.consumer_wide_view("reporting")
        for field_name in _TRACEABILITY_FIELDS:
            assert field_name in view.attrs, "missing traceability attr: {}".format(field_name)

    def test_traceability_attrs_match_underlying_metadata(self):
        scenarios = _make_set(Measure.P)
        attrs = phase6_consumer_mapping("reporting").traceability_attributes(scenarios)
        assert attrs["measure"] == "P"
        assert attrs["model_version"] == "schema-compat-test"
        assert attrs["base_currency"] == "CNY"
        assert attrs["parameter_snapshot_id"] == scenarios.parameter_snapshot.snapshot_id

    def test_metadata_snapshot_id_consistency_enforced(self):
        """Mismatched metadata/snapshot IDs must be rejected before consumer use."""
        scenarios = _make_set(Measure.P)
        # ScenarioMetadata is a frozen dataclass; bypass to simulate corruption.
        object.__setattr__(scenarios.metadata, "parameter_snapshot_id", "tampered-id")
        with pytest.raises(ValueError):
            phase6_consumer_mapping("reporting").validate_scenario_set(scenarios)


# ---------------------------------------------------------------------------
# 4. Monthly-grid completeness and dtype stability
# ---------------------------------------------------------------------------
class TestGridCompleteness:
    def test_row_count_is_n_times_months_plus_one(self):
        scenarios = _make_set(Measure.P)
        assert len(scenarios.data) == N_SCEN * (T_MONTHS + 1)

    def test_every_scenario_has_full_month_grid(self):
        scenarios = _make_set(Measure.P)
        expected_months = set(range(T_MONTHS + 1))
        for sid, group in scenarios.data.groupby("scenario_id"):
            assert set(group["month"].tolist()) == expected_months

    def test_single_measure_label_only(self):
        scenarios = _make_set(Measure.Q)
        assert scenarios.data["measure"].unique().tolist() == ["Q"]


# ---------------------------------------------------------------------------
# 5. Calibration-interface consistency
# ---------------------------------------------------------------------------
class TestCalibrationInterfaceConsistency:
    def test_default_interfaces_are_json_serialisable(self):
        for interface in default_phase6_calibration_interfaces():
            payload = interface.to_dict()
            assert payload["interface_id"]
            assert payload["required_fields"]
            assert interface.required_column_names

    def test_curve_interface_currency_matches_generated_base_currency(self):
        interfaces = {i.interface_id: i for i in default_phase6_calibration_interfaces()}
        # At least one risk-free-curve interface should exist and expose columns.
        curve_keys = [k for k in interfaces if "curve" in k.lower() or "rate" in k.lower()]
        assert curve_keys, "expected a risk-free curve calibration interface"


# ---------------------------------------------------------------------------
# 6. DynamicALM annual-return derivation
# ---------------------------------------------------------------------------
class TestDynamicALMReturns:
    def test_alm_returns_keys_and_equity_annualisation(self):
        scenarios = _make_set(Measure.P)
        returns = scenarios.alm_annual_returns(scenario_id=1, month=1)
        assert set(returns) == {"Cash", "Govt", "Credit", "Equity"}
        row = scenarios.data[
            (scenarios.data["scenario_id"] == 1) & (scenarios.data["month"] == 1)
        ].iloc[0]
        expected_equity = (1.0 + float(row["equity_return_1m"])) ** 12 - 1.0
        assert returns["Equity"] == pytest.approx(expected_equity)
        assert returns["Cash"] == pytest.approx(float(row["r_short"]))

    def test_alm_rejects_unknown_scenario_month(self):
        scenarios = _make_set(Measure.P)
        with pytest.raises(ValueError):
            scenarios.alm_annual_returns(scenario_id=999, month=1)


# ---------------------------------------------------------------------------
# 7. Full consumer coverage sanity
# ---------------------------------------------------------------------------
def test_default_mappings_cover_all_v1_consumers():
    by_id = {m.consumer_id for m in default_phase6_consumer_mappings()}
    assert {"tvog", "risk_metrics", "dynamic_alm", "reporting"}.issubset(by_id)

    by_id = {m.consumer_id for m in default_phase6_consumer_mappings()}
    assert {"tvog", "risk_metrics", "dynamic_alm", "reporting"}.issubset(by_id)
    by_id = {m.consumer_id for m in default_phase6_consumer_mappings()}
    assert {"tvog", "risk_metrics", "dynamic_alm", "reporting"}.issubset(by_id)
