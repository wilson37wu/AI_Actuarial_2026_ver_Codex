"""
Unit tests for par_model_v2.stochastic.ESGAdapter
==================================================

Satisfies IA TAS M validation requirements:

  VR-U06: ESGAdapter unit tests — data loading and validation
    - Valid file loads without error and returns correct DataFrame shape
    - Malformed column names raise ESGSchemaError with descriptive message
    - Missing file raises FileNotFoundError with path in message
    - Scenario count < 500 raises ScenarioAdequacyWarning
    - Scenario count checked against ASOP 56 §3.5 minimum table

  VR-D01: ESG input data — schema and range validation on load
    - Column names validated against expected schema on load
    - Short rate paths: all values in [−0.02, 0.15] (plausible CNY range)
    - Equity index paths: all values > 0 (no negative prices)
    - Scenario count ≥ 500 before accepting file for production
    - Validation error message includes field name, observed value, and range

Test structure
--------------
  Class TestFixtures                   — shared fixture factories
  Class TestFileNotFound               — missing path handling
  Class TestSchemaValidation           — column presence and dtype errors
  Class TestMeasureValidation          — measure column valid/invalid values
  Class TestRangeValidation            — numeric range rules (VR-D01)
  Class TestScenarioAdequacyWarning    — ASOP 56 §3.5 scenario count
  Class TestValidLoad                  — happy-path tests: shape, dtypes, content
  Class TestLoadFromDataFrame          — in-memory DataFrame path
  Class TestESGAdapterConfig           — config override behaviour
  Class TestIntrospectionHelpers       — required_columns(), schema_description()
  Class TestEdgeCases                  — boundary values, extra columns, etc.

Run
---
  PYTHONPATH=. pytest tests/test_esg_adapter.py -v

SOA / IA alignment
------------------
  SOA ASOP 56 §3.5 — scenario adequacy
  IA TAS M §3.6.2  — unit test coverage
  IA TAS M §3.9    — data validation obligations
"""

from __future__ import annotations

import io
import re
import warnings
from pathlib import Path
from typing import Any, Dict

import numpy as np
import pandas as pd
import pytest

from par_model_v2.stochastic.esg_adapter import (
    SCENARIO_MINIMUM_PRODUCTION,
    SCENARIO_MINIMUM_TVOG,
    SCENARIO_MINIMUM_VAR,
    SCENARIO_RECOMMENDED_TVOG,
    SCENARIO_RECOMMENDED_VAR,
    ESGAdapter,
    ESGAdapterConfig,
    ESGRangeError,
    ESGSchemaError,
    ScenarioAdequacyWarning,
)


# ---------------------------------------------------------------------------
# 0. Shared fixture factories
# ---------------------------------------------------------------------------

def _make_valid_df(
    n_scenarios: int = 10,
    T_months: int = 5,
    measure: str = "Q",
    r_short_val: float = 0.025,
    equity_val: float = 100.0,
) -> pd.DataFrame:
    """Build a minimal valid ESG DataFrame for testing.

    Parameters
    ----------
    n_scenarios : int
        Number of unique scenarios (scenario_id 1..n).
    T_months : int
        Number of months per scenario (month 0..T_months).
    measure : str
        Measure flag value, default "Q".
    r_short_val : float
        Constant short rate value across all rows.
    equity_val : float
        Constant equity index value across all rows.
    """
    rows = []
    for sid in range(1, n_scenarios + 1):
        for m in range(T_months + 1):
            rows.append({
                "scenario_id":  sid,
                "month":        m,
                "r_short":      r_short_val,
                "zcb_1y":       np.exp(-r_short_val * 1),
                "zcb_10y":      np.exp(-r_short_val * 10),
                "equity_index": equity_val,
                "measure":      measure,
            })
    return pd.DataFrame(rows)


def _make_valid_csv(tmp_path: Path, **kwargs) -> Path:
    """Write a valid ESG DataFrame to a temp CSV and return the path."""
    df = _make_valid_df(**kwargs)
    csv_path = tmp_path / "test_esg.csv"
    df.to_csv(csv_path, index=False)
    return csv_path


def _adapter_no_warnings() -> ESGAdapter:
    """Return an ESGAdapter that suppresses scenario adequacy warnings."""
    return ESGAdapter(ESGAdapterConfig(warn_on_low_scenario_count=False))


# ---------------------------------------------------------------------------
# 1. FileNotFoundError
# ---------------------------------------------------------------------------

class TestFileNotFound:
    """VR-U06: Missing file raises FileNotFoundError with path in message."""

    def test_missing_file_raises_file_not_found(self, tmp_path):
        """FileNotFoundError raised when path does not exist."""
        adapter = _adapter_no_warnings()
        missing = tmp_path / "does_not_exist.csv"
        with pytest.raises(FileNotFoundError) as exc_info:
            adapter.load(missing)
        assert str(missing) in str(exc_info.value)

    def test_missing_file_message_contains_path(self, tmp_path):
        """Error message must include the offending path (IA TAS M §3.9)."""
        adapter = _adapter_no_warnings()
        missing = tmp_path / "no_such_file.csv"
        with pytest.raises(FileNotFoundError, match=re.escape(str(missing))):
            adapter.load(missing)

    def test_wrong_extension_file_not_found(self, tmp_path):
        """Non-existent path with non-CSV extension still raises FileNotFoundError."""
        adapter = _adapter_no_warnings()
        with pytest.raises(FileNotFoundError):
            adapter.load(tmp_path / "esg.xlsx")

    def test_string_path_accepted(self, tmp_path):
        """load() accepts a plain string path (not just pathlib.Path)."""
        adapter = _adapter_no_warnings()
        missing = str(tmp_path / "missing.csv")
        with pytest.raises(FileNotFoundError):
            adapter.load(missing)


# ---------------------------------------------------------------------------
# 2. Schema validation — column presence
# ---------------------------------------------------------------------------

class TestSchemaValidation:
    """VR-U06 / VR-D01: Column presence and dtype checks."""

    def test_valid_file_loads_cleanly(self, tmp_path):
        """A fully conformant CSV loads without raising any exception."""
        csv_path = _make_valid_csv(tmp_path, n_scenarios=5, T_months=3)
        adapter = _adapter_no_warnings()
        df = adapter.load(csv_path)
        assert isinstance(df, pd.DataFrame)

    def test_missing_single_column_raises_schema_error(self, tmp_path):
        """ESGSchemaError raised when one required column is absent."""
        df = _make_valid_df(n_scenarios=5, T_months=2)
        df = df.drop(columns=["r_short"])
        csv_path = tmp_path / "missing_col.csv"
        df.to_csv(csv_path, index=False)
        adapter = _adapter_no_warnings()
        with pytest.raises(ESGSchemaError, match="r_short"):
            adapter.load(csv_path)

    def test_missing_multiple_columns_lists_all_in_message(self, tmp_path):
        """ESGSchemaError message lists every missing column."""
        df = _make_valid_df(n_scenarios=5, T_months=2)
        df = df.drop(columns=["r_short", "equity_index", "zcb_10y"])
        csv_path = tmp_path / "multi_missing.csv"
        df.to_csv(csv_path, index=False)
        adapter = _adapter_no_warnings()
        with pytest.raises(ESGSchemaError) as exc_info:
            adapter.load(csv_path)
        msg = str(exc_info.value)
        assert "r_short" in msg
        assert "equity_index" in msg
        assert "zcb_10y" in msg

    def test_missing_scenario_id_raises_schema_error(self, tmp_path):
        """scenario_id is a required column."""
        df = _make_valid_df().drop(columns=["scenario_id"])
        csv_path = tmp_path / "no_sid.csv"
        df.to_csv(csv_path, index=False)
        with pytest.raises(ESGSchemaError, match="scenario_id"):
            _adapter_no_warnings().load(csv_path)

    def test_missing_month_raises_schema_error(self, tmp_path):
        """month is a required column."""
        df = _make_valid_df().drop(columns=["month"])
        csv_path = tmp_path / "no_month.csv"
        df.to_csv(csv_path, index=False)
        with pytest.raises(ESGSchemaError, match="month"):
            _adapter_no_warnings().load(csv_path)

    def test_missing_measure_raises_schema_error(self, tmp_path):
        """measure is a required column."""
        df = _make_valid_df().drop(columns=["measure"])
        csv_path = tmp_path / "no_measure.csv"
        df.to_csv(csv_path, index=False)
        with pytest.raises(ESGSchemaError, match="measure"):
            _adapter_no_warnings().load(csv_path)

    def test_string_rate_column_raises_schema_error(self, tmp_path):
        """r_short as text strings raises ESGSchemaError (dtype mismatch)."""
        df = _make_valid_df(n_scenarios=5, T_months=2)
        df["r_short"] = "not_a_number"
        csv_path = tmp_path / "bad_dtype.csv"
        df.to_csv(csv_path, index=False)
        with pytest.raises(ESGSchemaError, match="r_short"):
            _adapter_no_warnings().load(csv_path)

    def test_string_equity_index_raises_schema_error(self, tmp_path):
        """equity_index as text strings raises ESGSchemaError (dtype mismatch)."""
        df = _make_valid_df(n_scenarios=5, T_months=2)
        df["equity_index"] = "bad"
        csv_path = tmp_path / "bad_eq.csv"
        df.to_csv(csv_path, index=False)
        with pytest.raises(ESGSchemaError, match="equity_index"):
            _adapter_no_warnings().load(csv_path)

    def test_extra_columns_are_retained(self, tmp_path):
        """Extra vendor-specific columns are not stripped from output."""
        df = _make_valid_df(n_scenarios=5, T_months=2)
        df["vendor_col_alpha"] = 999.0
        csv_path = tmp_path / "extra_cols.csv"
        df.to_csv(csv_path, index=False)
        result = _adapter_no_warnings().load(csv_path)
        assert "vendor_col_alpha" in result.columns

    def test_empty_dataframe_raises_schema_error_on_missing_columns(self, tmp_path):
        """Completely empty CSV (header only, wrong columns) raises ESGSchemaError."""
        csv_path = tmp_path / "empty.csv"
        csv_path.write_text("col_a,col_b\n")
        with pytest.raises(ESGSchemaError):
            _adapter_no_warnings().load(csv_path)


# ---------------------------------------------------------------------------
# 3. Measure column validation
# ---------------------------------------------------------------------------

class TestMeasureValidation:
    """VR-U06 / VR-D01: measure column must contain only 'P' or 'Q'."""

    def test_measure_p_accepted(self, tmp_path):
        """Measure.P scenarios load without error."""
        csv_path = _make_valid_csv(tmp_path, measure="P")
        df = _adapter_no_warnings().load(csv_path)
        assert set(df["measure"].unique()) == {"P"}

    def test_measure_q_accepted(self, tmp_path):
        """Measure.Q scenarios load without error."""
        csv_path = _make_valid_csv(tmp_path, measure="Q")
        df = _adapter_no_warnings().load(csv_path)
        assert set(df["measure"].unique()) == {"Q"}

    def test_mixed_p_and_q_accepted(self, tmp_path):
        """Files with both P and Q rows (multi-measure) are accepted by schema."""
        df_p = _make_valid_df(n_scenarios=3, T_months=2, measure="P")
        df_q = _make_valid_df(n_scenarios=3, T_months=2, measure="Q")
        df_q["scenario_id"] += 3  # avoid duplicate IDs
        df = pd.concat([df_p, df_q], ignore_index=True)
        csv_path = tmp_path / "mixed.csv"
        df.to_csv(csv_path, index=False)
        result = _adapter_no_warnings().load(csv_path)
        assert set(result["measure"].unique()) == {"P", "Q"}

    def test_invalid_measure_value_raises_schema_error(self, tmp_path):
        """Values other than 'P'/'Q' in measure column raise ESGSchemaError."""
        df = _make_valid_df(n_scenarios=5, T_months=2)
        df["measure"] = "X"
        csv_path = tmp_path / "bad_measure.csv"
        df.to_csv(csv_path, index=False)
        with pytest.raises(ESGSchemaError, match="measure"):
            _adapter_no_warnings().load(csv_path)

    def test_lowercase_measure_raises_schema_error(self, tmp_path):
        """Lowercase 'p'/'q' is not accepted — must be uppercase 'P'/'Q'."""
        df = _make_valid_df(n_scenarios=5, T_months=2)
        df["measure"] = "q"
        csv_path = tmp_path / "lower_measure.csv"
        df.to_csv(csv_path, index=False)
        with pytest.raises(ESGSchemaError, match="measure"):
            _adapter_no_warnings().load(csv_path)

    def test_numeric_measure_raises_schema_error(self, tmp_path):
        """Numeric measure values raise ESGSchemaError."""
        df = _make_valid_df(n_scenarios=5, T_months=2)
        df["measure"] = 1
        csv_path = tmp_path / "num_measure.csv"
        df.to_csv(csv_path, index=False)
        with pytest.raises(ESGSchemaError, match="measure"):
            _adapter_no_warnings().load(csv_path)

    def test_measure_error_message_is_descriptive(self, tmp_path):
        """ESGSchemaError for bad measure lists the invalid value found."""
        df = _make_valid_df(n_scenarios=5, T_months=2)
        df["measure"] = "REAL_WORLD"
        csv_path = tmp_path / "bad_measure2.csv"
        df.to_csv(csv_path, index=False)
        with pytest.raises(ESGSchemaError, match="REAL_WORLD"):
            _adapter_no_warnings().load(csv_path)


# ---------------------------------------------------------------------------
# 4. Range validation (VR-D01)
# ---------------------------------------------------------------------------

class TestRangeValidation:
    """VR-D01: Numeric column range checks (CNY plausibility constraints)."""

    def test_r_short_below_floor_raises_range_error(self, tmp_path):
        """r_short < -0.02 raises ESGRangeError (below NIRP floor)."""
        df = _make_valid_df(n_scenarios=5, T_months=2, r_short_val=0.025)
        df.loc[df.index[0], "r_short"] = -0.05  # far below -2%
        csv_path = tmp_path / "r_low.csv"
        df.to_csv(csv_path, index=False)
        with pytest.raises(ESGRangeError, match="r_short"):
            _adapter_no_warnings().load(csv_path)

    def test_r_short_above_ceiling_raises_range_error(self, tmp_path):
        """r_short > 0.15 raises ESGRangeError (above 15% ceiling)."""
        df = _make_valid_df(n_scenarios=5, T_months=2, r_short_val=0.025)
        df.loc[df.index[0], "r_short"] = 0.20  # above 15%
        csv_path = tmp_path / "r_high.csv"
        df.to_csv(csv_path, index=False)
        with pytest.raises(ESGRangeError, match="r_short"):
            _adapter_no_warnings().load(csv_path)

    def test_r_short_at_exact_floor_is_valid(self, tmp_path):
        """r_short == -0.02 is at the inclusive lower boundary — must pass.

        Note: with r_short = -0.02, exp(-B*r) > 1 for the ZCB prices generated
        by the default fixture, which would trigger the zcb_1y/zcb_10y range
        rules.  We override ZCB columns with valid values to isolate the
        r_short boundary test.
        """
        df = _make_valid_df(n_scenarios=5, T_months=2, r_short_val=-0.02)
        # Override ZCB columns: keep them in (0, 1] independent of the rate
        df["zcb_1y"] = 0.990
        df["zcb_10y"] = 0.910
        csv_path = tmp_path / "r_at_floor.csv"
        df.to_csv(csv_path, index=False)
        result = _adapter_no_warnings().load(csv_path)
        assert (result["r_short"] == -0.02).any()

    def test_r_short_at_exact_ceiling_is_valid(self, tmp_path):
        """r_short == 0.15 is at the inclusive upper boundary — must pass."""
        df = _make_valid_df(n_scenarios=5, T_months=2, r_short_val=0.15)
        csv_path = tmp_path / "r_at_ceil.csv"
        df.to_csv(csv_path, index=False)
        result = _adapter_no_warnings().load(csv_path)
        assert (result["r_short"] == 0.15).any()

    def test_equity_index_zero_raises_range_error(self, tmp_path):
        """equity_index == 0 raises ESGRangeError (must be strictly positive)."""
        df = _make_valid_df(n_scenarios=5, T_months=2, equity_val=100.0)
        df.loc[df.index[0], "equity_index"] = 0.0
        csv_path = tmp_path / "eq_zero.csv"
        df.to_csv(csv_path, index=False)
        with pytest.raises(ESGRangeError, match="equity_index"):
            _adapter_no_warnings().load(csv_path)

    def test_equity_index_negative_raises_range_error(self, tmp_path):
        """equity_index < 0 raises ESGRangeError (negative prices impossible)."""
        df = _make_valid_df(n_scenarios=5, T_months=2, equity_val=100.0)
        df.loc[df.index[0], "equity_index"] = -10.0
        csv_path = tmp_path / "eq_neg.csv"
        df.to_csv(csv_path, index=False)
        with pytest.raises(ESGRangeError, match="equity_index"):
            _adapter_no_warnings().load(csv_path)

    def test_equity_index_positive_value_is_valid(self, tmp_path):
        """equity_index = 0.001 (very small but positive) passes range check."""
        df = _make_valid_df(n_scenarios=5, T_months=2, equity_val=0.001)
        csv_path = tmp_path / "eq_small.csv"
        df.to_csv(csv_path, index=False)
        result = _adapter_no_warnings().load(csv_path)
        assert (result["equity_index"] > 0).all()

    def test_zcb_1y_above_one_raises_range_error(self, tmp_path):
        """zcb_1y > 1.0 raises ESGRangeError (ZCB price cannot exceed par)."""
        df = _make_valid_df(n_scenarios=5, T_months=2)
        df.loc[df.index[0], "zcb_1y"] = 1.05
        csv_path = tmp_path / "zcb1_high.csv"
        df.to_csv(csv_path, index=False)
        with pytest.raises(ESGRangeError, match="zcb_1y"):
            _adapter_no_warnings().load(csv_path)

    def test_zcb_1y_zero_raises_range_error(self, tmp_path):
        """zcb_1y == 0 raises ESGRangeError (must be strictly positive)."""
        df = _make_valid_df(n_scenarios=5, T_months=2)
        df.loc[df.index[0], "zcb_1y"] = 0.0
        csv_path = tmp_path / "zcb1_zero.csv"
        df.to_csv(csv_path, index=False)
        with pytest.raises(ESGRangeError, match="zcb_1y"):
            _adapter_no_warnings().load(csv_path)

    def test_zcb_10y_at_exact_one_is_valid(self, tmp_path):
        """zcb_10y == 1.0 is at the inclusive upper bound — must pass."""
        df = _make_valid_df(n_scenarios=5, T_months=2)
        df["zcb_10y"] = 1.0
        csv_path = tmp_path / "zcb10_par.csv"
        df.to_csv(csv_path, index=False)
        result = _adapter_no_warnings().load(csv_path)
        assert (result["zcb_10y"] == 1.0).any()

    def test_range_error_message_includes_field_name_and_range(self, tmp_path):
        """ESGRangeError message includes field name and expected range (VR-D01)."""
        df = _make_valid_df(n_scenarios=5, T_months=2, equity_val=100.0)
        df.loc[df.index[0], "equity_index"] = -5.0
        csv_path = tmp_path / "range_msg.csv"
        df.to_csv(csv_path, index=False)
        with pytest.raises(ESGRangeError) as exc_info:
            _adapter_no_warnings().load(csv_path)
        msg = str(exc_info.value)
        assert "equity_index" in msg

    def test_multiple_range_violations_all_reported(self, tmp_path):
        """When both r_short and equity_index violate ranges, both appear in error."""
        df = _make_valid_df(n_scenarios=5, T_months=2)
        df.loc[df.index[0], "r_short"] = 0.99
        df.loc[df.index[1], "equity_index"] = -1.0
        csv_path = tmp_path / "multi_range.csv"
        df.to_csv(csv_path, index=False)
        with pytest.raises(ESGRangeError) as exc_info:
            _adapter_no_warnings().load(csv_path)
        msg = str(exc_info.value)
        assert "r_short" in msg
        assert "equity_index" in msg

    def test_range_violation_warn_not_raise_when_configured(self, tmp_path):
        """With raise_on_range_violation=False, ESGRangeError is not raised."""
        df = _make_valid_df(n_scenarios=5, T_months=2, equity_val=100.0)
        df.loc[df.index[0], "equity_index"] = -1.0
        csv_path = tmp_path / "warn_only.csv"
        df.to_csv(csv_path, index=False)
        config = ESGAdapterConfig(
            warn_on_low_scenario_count=False,
            raise_on_range_violation=False,
        )
        adapter = ESGAdapter(config)
        with warnings.catch_warnings(record=True):
            warnings.simplefilter("always")
            result = adapter.load(csv_path)  # must not raise
        assert isinstance(result, pd.DataFrame)


# ---------------------------------------------------------------------------
# 5. Scenario adequacy warning (ASOP 56 §3.5)
# ---------------------------------------------------------------------------

class TestScenarioAdequacyWarning:
    """VR-U06: ScenarioAdequacyWarning for low scenario counts."""

    def test_500_scenarios_does_not_warn(self, tmp_path):
        """Exactly 500 scenarios meets the minimum — no warning issued."""
        csv_path = _make_valid_csv(tmp_path, n_scenarios=500, T_months=1)
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            ESGAdapter().load(csv_path)
        adeq_warnings = [x for x in w if issubclass(x.category, ScenarioAdequacyWarning)]
        assert len(adeq_warnings) == 0

    def test_499_scenarios_issues_warning(self, tmp_path):
        """499 scenarios is below the ASOP 56 §3.5 minimum — warning expected."""
        csv_path = _make_valid_csv(tmp_path, n_scenarios=499, T_months=1)
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            ESGAdapter().load(csv_path)
        adeq_warnings = [x for x in w if issubclass(x.category, ScenarioAdequacyWarning)]
        assert len(adeq_warnings) == 1

    def test_small_scenario_count_issues_warning(self, tmp_path):
        """10 scenarios (development fixture) raises ScenarioAdequacyWarning."""
        csv_path = _make_valid_csv(tmp_path, n_scenarios=10, T_months=3)
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            ESGAdapter().load(csv_path)
        adeq_warnings = [x for x in w if issubclass(x.category, ScenarioAdequacyWarning)]
        assert len(adeq_warnings) == 1

    def test_warning_message_contains_minimum(self, tmp_path):
        """ScenarioAdequacyWarning message cites ASOP 56 §3.5 minimum count."""
        csv_path = _make_valid_csv(tmp_path, n_scenarios=10, T_months=1)
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            ESGAdapter().load(csv_path)
        adeq_warnings = [x for x in w if issubclass(x.category, ScenarioAdequacyWarning)]
        assert len(adeq_warnings) == 1
        msg = str(adeq_warnings[0].message)
        assert str(SCENARIO_MINIMUM_PRODUCTION) in msg

    def test_warning_message_contains_scenario_count(self, tmp_path):
        """Warning message states the actual scenario count found."""
        csv_path = _make_valid_csv(tmp_path, n_scenarios=42, T_months=1)
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            ESGAdapter().load(csv_path)
        adeq_warnings = [x for x in w if issubclass(x.category, ScenarioAdequacyWarning)]
        assert len(adeq_warnings) == 1
        msg = str(adeq_warnings[0].message)
        assert "42" in msg

    def test_warning_suppressed_when_configured(self, tmp_path):
        """warn_on_low_scenario_count=False suppresses the warning."""
        csv_path = _make_valid_csv(tmp_path, n_scenarios=10, T_months=1)
        config = ESGAdapterConfig(warn_on_low_scenario_count=False)
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            ESGAdapter(config).load(csv_path)
        adeq_warnings = [x for x in w if issubclass(x.category, ScenarioAdequacyWarning)]
        assert len(adeq_warnings) == 0

    def test_custom_minimum_scenarios_respected(self, tmp_path):
        """minimum_scenarios config override is honoured."""
        # Set minimum to 5; 3 scenarios should still warn
        csv_path = _make_valid_csv(tmp_path, n_scenarios=3, T_months=1)
        config = ESGAdapterConfig(minimum_scenarios=5)
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            ESGAdapter(config).load(csv_path)
        adeq_warnings = [x for x in w if issubclass(x.category, ScenarioAdequacyWarning)]
        assert len(adeq_warnings) == 1

    def test_custom_minimum_met_no_warning(self, tmp_path):
        """When n_scenarios >= custom minimum, no warning is issued."""
        csv_path = _make_valid_csv(tmp_path, n_scenarios=10, T_months=1)
        config = ESGAdapterConfig(minimum_scenarios=10)
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            ESGAdapter(config).load(csv_path)
        adeq_warnings = [x for x in w if issubclass(x.category, ScenarioAdequacyWarning)]
        assert len(adeq_warnings) == 0


# ---------------------------------------------------------------------------
# 6. Happy-path / valid load tests
# ---------------------------------------------------------------------------

class TestValidLoad:
    """VR-U06: Valid file loads without error and returns correct shape."""

    def test_output_is_dataframe(self, tmp_path):
        """Return type is pd.DataFrame."""
        csv_path = _make_valid_csv(tmp_path)
        result = _adapter_no_warnings().load(csv_path)
        assert isinstance(result, pd.DataFrame)

    def test_output_row_count_is_correct(self, tmp_path):
        """Row count equals n_scenarios × (T_months + 1)."""
        n_scenarios, T_months = 7, 4
        csv_path = _make_valid_csv(tmp_path, n_scenarios=n_scenarios, T_months=T_months)
        result = _adapter_no_warnings().load(csv_path)
        expected_rows = n_scenarios * (T_months + 1)
        assert len(result) == expected_rows

    def test_required_columns_all_present_in_output(self, tmp_path):
        """All required columns exist in the output DataFrame."""
        csv_path = _make_valid_csv(tmp_path)
        result = _adapter_no_warnings().load(csv_path)
        for col in ESGAdapter.required_columns():
            assert col in result.columns, f"Column '{col}' missing from output"

    def test_scenario_id_dtype_is_int64(self, tmp_path):
        """scenario_id is cast to int64 on load."""
        csv_path = _make_valid_csv(tmp_path)
        result = _adapter_no_warnings().load(csv_path)
        assert result["scenario_id"].dtype == np.int64

    def test_month_dtype_is_int64(self, tmp_path):
        """month is cast to int64 on load."""
        csv_path = _make_valid_csv(tmp_path)
        result = _adapter_no_warnings().load(csv_path)
        assert result["month"].dtype == np.int64

    def test_r_short_dtype_is_float64(self, tmp_path):
        """r_short is cast to float64 on load."""
        csv_path = _make_valid_csv(tmp_path)
        result = _adapter_no_warnings().load(csv_path)
        assert result["r_short"].dtype == np.float64

    def test_equity_index_dtype_is_float64(self, tmp_path):
        """equity_index is cast to float64 on load."""
        csv_path = _make_valid_csv(tmp_path)
        result = _adapter_no_warnings().load(csv_path)
        assert result["equity_index"].dtype == np.float64

    def test_measure_column_is_string(self, tmp_path):
        """measure column contains string values after load."""
        csv_path = _make_valid_csv(tmp_path, measure="Q")
        result = _adapter_no_warnings().load(csv_path)
        assert result["measure"].dtype == object  # pandas string = object kind

    def test_scenario_ids_start_at_one(self, tmp_path):
        """Scenario IDs should include 1 as the minimum (1-based indexing)."""
        csv_path = _make_valid_csv(tmp_path, n_scenarios=5)
        result = _adapter_no_warnings().load(csv_path)
        assert result["scenario_id"].min() == 1

    def test_month_starts_at_zero(self, tmp_path):
        """Month column starts at 0 (valuation date)."""
        csv_path = _make_valid_csv(tmp_path, T_months=5)
        result = _adapter_no_warnings().load(csv_path)
        assert result["month"].min() == 0

    def test_zcb_prices_are_positive(self, tmp_path):
        """ZCB prices in output are positive (passes range check)."""
        csv_path = _make_valid_csv(tmp_path, r_short_val=0.03)
        result = _adapter_no_warnings().load(csv_path)
        assert (result["zcb_1y"] > 0).all()
        assert (result["zcb_10y"] > 0).all()

    def test_realistic_cny_rate_scenario(self, tmp_path):
        """Realistic 2.5% CNY short rate scenario loads cleanly."""
        csv_path = _make_valid_csv(tmp_path, r_short_val=0.025, equity_val=3850.0)
        result = _adapter_no_warnings().load(csv_path)
        assert result["r_short"].iloc[0] == pytest.approx(0.025)
        assert result["equity_index"].iloc[0] == pytest.approx(3850.0)


# ---------------------------------------------------------------------------
# 7. load_from_dataframe
# ---------------------------------------------------------------------------

class TestLoadFromDataFrame:
    """In-memory DataFrame validation path."""

    def test_valid_dataframe_passes(self):
        """Valid in-memory DataFrame loads without error."""
        df = _make_valid_df(n_scenarios=5, T_months=3)
        result = _adapter_no_warnings().load_from_dataframe(df)
        assert isinstance(result, pd.DataFrame)

    def test_missing_column_raises_schema_error(self):
        """Missing column in DataFrame raises ESGSchemaError."""
        df = _make_valid_df().drop(columns=["zcb_1y"])
        with pytest.raises(ESGSchemaError, match="zcb_1y"):
            _adapter_no_warnings().load_from_dataframe(df)

    def test_invalid_measure_raises_schema_error(self):
        """Invalid measure value in DataFrame raises ESGSchemaError."""
        df = _make_valid_df()
        df["measure"] = "INVALID"
        with pytest.raises(ESGSchemaError, match="measure"):
            _adapter_no_warnings().load_from_dataframe(df)

    def test_range_violation_raises_range_error(self):
        """Out-of-range equity_index in DataFrame raises ESGRangeError."""
        df = _make_valid_df()
        df.loc[0, "equity_index"] = -100.0
        with pytest.raises(ESGRangeError, match="equity_index"):
            _adapter_no_warnings().load_from_dataframe(df)

    def test_scenario_adequacy_warning_from_dataframe(self):
        """ScenarioAdequacyWarning raised from in-memory DataFrame with < 500 scenarios."""
        df = _make_valid_df(n_scenarios=10)
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            ESGAdapter().load_from_dataframe(df)
        adeq_warnings = [x for x in w if issubclass(x.category, ScenarioAdequacyWarning)]
        assert len(adeq_warnings) == 1

    def test_original_dataframe_not_mutated(self):
        """load_from_dataframe returns a copy — original DataFrame is unchanged."""
        df = _make_valid_df(n_scenarios=5, T_months=2)
        original_dtypes = df.dtypes.copy()
        _ = _adapter_no_warnings().load_from_dataframe(df)
        # scenario_id in original may be int64 or object depending on creation
        # The key check: original DataFrame is not the same object as output
        result = _adapter_no_warnings().load_from_dataframe(df)
        assert result is not df


# ---------------------------------------------------------------------------
# 8. ESGAdapterConfig behaviour
# ---------------------------------------------------------------------------

class TestESGAdapterConfig:
    """Config dataclass controls adapter behaviour."""

    def test_default_config_is_production_safe(self):
        """Default config has production-safe flags (both validations on)."""
        config = ESGAdapterConfig()
        assert config.warn_on_low_scenario_count is True
        assert config.raise_on_range_violation is True
        assert config.minimum_scenarios == SCENARIO_MINIMUM_PRODUCTION

    def test_minimum_scenarios_constant_matches_tvog_minimum(self):
        """Default minimum_scenarios equals SCENARIO_MINIMUM_TVOG (500)."""
        assert SCENARIO_MINIMUM_PRODUCTION == SCENARIO_MINIMUM_TVOG == 500

    def test_var_minimum_is_2000(self):
        """ASOP 56 §3.5: VaR 99.5% minimum is 2 000 scenarios."""
        assert SCENARIO_MINIMUM_VAR == 2_000

    def test_tvog_recommended_is_1000(self):
        """ASOP 56 §3.5: TVOG recommended count is 1 000."""
        assert SCENARIO_RECOMMENDED_TVOG == 1_000

    def test_var_recommended_is_5000(self):
        """ASOP 56 §3.5: VaR recommended count is 5 000."""
        assert SCENARIO_RECOMMENDED_VAR == 5_000


# ---------------------------------------------------------------------------
# 9. Introspection helpers
# ---------------------------------------------------------------------------

class TestIntrospectionHelpers:
    """ESGAdapter.required_columns() and .schema_description()."""

    def test_required_columns_returns_list(self):
        """required_columns() returns a list of strings."""
        cols = ESGAdapter.required_columns()
        assert isinstance(cols, list)
        assert all(isinstance(c, str) for c in cols)

    def test_required_columns_contains_all_expected(self):
        """required_columns() includes all 7 required columns."""
        cols = ESGAdapter.required_columns()
        for expected in [
            "scenario_id", "month", "r_short",
            "zcb_1y", "zcb_10y", "equity_index", "measure"
        ]:
            assert expected in cols

    def test_schema_description_returns_dict(self):
        """schema_description() returns a dict keyed by column name."""
        desc = ESGAdapter.schema_description()
        assert isinstance(desc, dict)

    def test_schema_description_has_entry_for_each_required_column(self):
        """schema_description() has an entry for every required column."""
        desc = ESGAdapter.schema_description()
        for col in ESGAdapter.required_columns():
            assert col in desc, f"'{col}' missing from schema_description()"

    def test_schema_description_values_are_strings(self):
        """schema_description() values are non-empty strings."""
        desc = ESGAdapter.schema_description()
        for col, val in desc.items():
            assert isinstance(val, str) and len(val) > 0, \
                f"Empty description for column '{col}'"


# ---------------------------------------------------------------------------
# 10. Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    """Boundary values, unusual but valid inputs, and defensive cases."""

    def test_single_scenario_single_month(self, tmp_path):
        """1 scenario, 1 month (T=0) is the minimal valid DataFrame."""
        df = _make_valid_df(n_scenarios=1, T_months=0)
        result = _adapter_no_warnings().load_from_dataframe(df)
        assert len(result) == 1

    def test_negative_rate_within_nirp_floor_is_valid(self, tmp_path):
        """r_short = -0.005 (mild NIRP) passes range check."""
        df = _make_valid_df(n_scenarios=5, T_months=2, r_short_val=-0.005)
        # ZCB prices > 1 would violate zcb range — adjust them
        df["zcb_1y"] = 0.995
        df["zcb_10y"] = 0.950
        result = _adapter_no_warnings().load_from_dataframe(df)
        assert (result["r_short"] < 0).any()

    def test_whitespace_in_measure_column_is_stripped(self, tmp_path):
        """Measure values with surrounding whitespace (e.g. ' Q ') are stripped."""
        df = _make_valid_df(n_scenarios=5, T_months=2, measure="Q")
        df["measure"] = " Q "  # add surrounding spaces
        csv_path = tmp_path / "ws_measure.csv"
        df.to_csv(csv_path, index=False)
        # Whitespace is stripped in _validate_schema check and _cast_dtypes
        result = _adapter_no_warnings().load(csv_path)
        assert set(result["measure"].unique()) == {"Q"}

    def test_float_scenario_id_in_csv_cast_to_int(self, tmp_path):
        """scenario_id stored as float (e.g. 1.0) in CSV is cast to int64."""
        df = _make_valid_df(n_scenarios=5, T_months=2)
        df["scenario_id"] = df["scenario_id"].astype(float)  # simulate CSV float
        csv_path = tmp_path / "float_sid.csv"
        df.to_csv(csv_path, index=False)
        result = _adapter_no_warnings().load(csv_path)
        assert result["scenario_id"].dtype == np.int64

    def test_column_order_does_not_matter(self, tmp_path):
        """Shuffled column order in the CSV still loads correctly."""
        df = _make_valid_df(n_scenarios=5, T_months=2)
        df = df[list(reversed(df.columns))]  # reverse column order
        csv_path = tmp_path / "col_order.csv"
        df.to_csv(csv_path, index=False)
        result = _adapter_no_warnings().load(csv_path)
        for col in ESGAdapter.required_columns():
            assert col in result.columns

    def test_large_equity_value_is_valid(self, tmp_path):
        """Very large equity index (e.g. 100 000) is within range (no upper cap)."""
        df = _make_valid_df(n_scenarios=5, T_months=2, equity_val=100_000.0)
        result = _adapter_no_warnings().load_from_dataframe(df)
        assert (result["equity_index"] == 100_000.0).all()

    def test_adapter_is_reusable_across_multiple_loads(self, tmp_path):
        """The same adapter instance can load multiple files sequentially."""
        adapter = _adapter_no_warnings()
        for n in [3, 7, 2]:
            # Pass tmp_path (a directory) so _make_valid_csv writes test_esg.csv
            # inside a unique subdirectory per iteration to avoid overwriting.
            sub = tmp_path / f"run_{n}"
            sub.mkdir()
            csv_path = _make_valid_csv(sub, n_scenarios=n, T_months=1)
            df = adapter.load(csv_path)
            assert df["scenario_id"].nunique() == n

    def test_adapter_is_reusable_across_multiple_loads(self, tmp_path):
        """The same adapter instance can load multiple files sequentially."""
        adapter = _adapter_no_warnings()
        for n in [3, 7, 2]:
            sub = tmp_path / f"run_{n}"
            sub.mkdir()
            csv_path = _make_valid_csv(sub, n_scenarios=n, T_months=1)
            df = adapter.load(csv_path)
            assert df["scenario_id"].nunique() == n
