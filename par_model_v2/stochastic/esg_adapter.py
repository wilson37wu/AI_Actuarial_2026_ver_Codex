"""
ESGAdapter — Moody's CNY ESG File Loader & Schema Validator
============================================================

Reads Moody's Analytics CNY Economic Scenario Generator (ESG) output files,
validates them against an expected schema, enforces ASOP 56 §3.5 scenario
adequacy requirements, and returns a clean ``pd.DataFrame`` ready for use in
ALM projection and TVOG computation.

Phase 3 Deliverable
-------------------
Implements ``VR-U06`` (ESGAdapter unit tests) and ``VR-D01``
(ESG input data schema and range validation) from the IA TAS M validation
framework (``par_model_v2/validation/ia_validation.py``).

Moody's CNY ESG File Format (expected)
---------------------------------------
The adapter expects a CSV file with at least the following columns:

    scenario_id   : int   — 1-based scenario index
    month         : int   — projection month (0 = valuation date)
    r_short       : float — annualised short rate (decimal; e.g. 0.02 = 2%)
    zcb_1y        : float — 1-year zero-coupon bond price (0 < P ≤ 1)
    zcb_10y       : float — 10-year zero-coupon bond price (0 < P ≤ 1)
    equity_index  : float — equity index level (normalised; S(0) > 0)
    measure       : str   — "P" or "Q"

Additional vendor-specific columns are silently retained.  The adapter
only enforces the schema on the required columns listed above.

Validation Rules (VR-D01)
--------------------------
Column presence
    All required columns must exist; missing columns → ``ESGSchemaError``.

Data types
    ``scenario_id`` and ``month`` must be integer-compatible.
    ``r_short``, ``zcb_1y``, ``zcb_10y``, ``equity_index`` must be numeric.
    ``measure`` must be "P" or "Q" only.

Value ranges (CNY plausibility, SOA ASOP 56 §3.5)
    r_short      ∈ [−0.02, 0.15]   — negative rates allowed (NIRP), capped at 15%
    zcb_1y       ∈ (0, 1]          — bond prices positive and ≤ par
    zcb_10y      ∈ (0, 1]          — same as above
    equity_index > 0               — no negative index levels

Scenario adequacy (ASOP 56 §3.5)
    TVOG / MCEV  : minimum 500 scenarios  (warning below 1 000)
    VaR 99.5%    : minimum 2 000 scenarios (warning below 5 000)
    ESGAdapter raises ``ScenarioAdequacyWarning`` for count < 500.

Standards References
--------------------
SOA ASOP 56 §3.5  — scenario count adequacy
IA TAS M §3.6.2   — unit testing requirements
IA TAS M §3.9     — data validation obligations
ESG_PROCESS_DOCUMENTATION.md §6 — scenario format specification
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# 0. Public Exceptions & Warnings
# ---------------------------------------------------------------------------

class ESGSchemaError(ValueError):
    """Raised when the ESG file fails schema validation.

    The message always includes:
    - The field name that failed
    - The observed value or description of the problem
    - The expected constraint

    IA TAS M §3.9: Data loading must fail explicitly when schema is violated.
    """


class ESGRangeError(ValueError):
    """Raised when ESG column values fall outside plausible actuarial ranges.

    Includes field name, observed extreme value, and expected range.
    """


class ScenarioAdequacyWarning(UserWarning):
    """Warning issued when scenario count is below ASOP 56 §3.5 minimums.

    Not an error (the file may still be used for development / testing) but
    must not be suppressed in production runs.
    """


# ---------------------------------------------------------------------------
# 1. Schema Definition
# ---------------------------------------------------------------------------

# Required columns: name → (numpy kind codes for dtype check, description)
# kind codes: 'i' = signed int, 'u' = unsigned int, 'f' = floating-point
_REQUIRED_COLUMNS: Dict[str, Tuple[str, str]] = {
    "scenario_id":  ("iuf",  "integer scenario identifier"),
    "month":        ("iuf",  "integer projection month"),
    "r_short":      ("f",    "annualised short rate (decimal)"),
    "zcb_1y":       ("f",    "1-year ZCB price"),
    "zcb_10y":      ("f",    "10-year ZCB price"),
    "equity_index": ("f",    "equity index level"),
    "measure":      ("UOS",  "measure flag — 'P' or 'Q'"),
}

# Value range rules: column → (min_inclusive, max_inclusive, allow_equal_min, allow_equal_max)
# None = unbounded on that side
_RANGE_RULES: Dict[str, Tuple[Optional[float], Optional[float], bool, bool]] = {
    "r_short":      (-0.02, 0.15,  True,  True),   # [-0.02, 0.15]
    "zcb_1y":       (0.0,   1.0,   False, True),   # (0, 1]
    "zcb_10y":      (0.0,   1.0,   False, True),   # (0, 1]
    "equity_index": (0.0,   None,  False, True),   # > 0
}

# Minimum scenario counts per use case (ASOP 56 §3.5)
SCENARIO_MINIMUM_PRODUCTION: int = 500    # absolute minimum for any production use
SCENARIO_MINIMUM_TVOG: int = 500          # TVOG / MCEV minimum
SCENARIO_RECOMMENDED_TVOG: int = 1_000   # recommended
SCENARIO_MINIMUM_VAR: int = 2_000        # VaR 99.5% minimum
SCENARIO_RECOMMENDED_VAR: int = 5_000    # recommended


# ---------------------------------------------------------------------------
# 2. ESGAdapter
# ---------------------------------------------------------------------------

@dataclass
class ESGAdapterConfig:
    """Configuration for ESGAdapter load behaviour.

    Attributes
    ----------
    warn_on_low_scenario_count : bool
        Issue ``ScenarioAdequacyWarning`` when scenario count < 500.
        Default True.  Set False only in unit tests.
    raise_on_range_violation : bool
        Raise ``ESGRangeError`` on out-of-range values.
        Default True.  Set False to log-and-continue in exploration workflows.
    minimum_scenarios : int
        Override production minimum.  Default 500 (ASOP 56 §3.5 TVOG minimum).
    """
    warn_on_low_scenario_count: bool = True
    raise_on_range_violation: bool = True
    minimum_scenarios: int = SCENARIO_MINIMUM_PRODUCTION


class ESGAdapter:
    """Loader and validator for Moody's CNY ESG output files.

    Usage
    -----
    >>> adapter = ESGAdapter()
    >>> df = adapter.load("/path/to/moodys_cny_esg.csv")
    >>> df.shape
    (500000, 8)  # 1 000 scenarios × 500 months + 1

    The returned DataFrame has exactly the required columns plus any extra
    vendor columns present in the source file.  All required columns are
    cast to their canonical dtypes.

    Validation
    ----------
    1. File existence — ``FileNotFoundError`` if path not found.
    2. Column presence — ``ESGSchemaError`` listing all missing columns.
    3. Column dtypes — ``ESGSchemaError`` per incompatible column.
    4. Measure values — ``ESGSchemaError`` if any value ∉ {"P", "Q"}.
    5. Value ranges — ``ESGRangeError`` per out-of-range column.
    6. Scenario count — ``ScenarioAdequacyWarning`` if < minimum_scenarios.

    Parameters
    ----------
    config : ESGAdapterConfig, optional
        Loader configuration.  Defaults to production-safe settings.

    Standards References
    --------------------
    VR-U06: ESGAdapter unit tests — data loading and validation
    VR-D01: ESG input data schema and range validation on load
    IA TAS M §3.9: Data validation obligations
    SOA ASOP 56 §3.5: Scenario count adequacy
    """

    def __init__(self, config: Optional[ESGAdapterConfig] = None) -> None:
        self.config = config if config is not None else ESGAdapterConfig()

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def load(self, path: str | Path) -> pd.DataFrame:
        """Load and validate an ESG file from ``path``.

        Parameters
        ----------
        path : str or Path
            Path to the Moody's CNY ESG CSV file.

        Returns
        -------
        pd.DataFrame
            Validated scenario data.  Required columns are cast to canonical
            dtypes; additional vendor columns are retained as-is.

        Raises
        ------
        FileNotFoundError
            If ``path`` does not exist.  Message includes the resolved path.
        ESGSchemaError
            If required columns are missing or have incompatible dtypes,
            or if the ``measure`` column contains values other than "P"/"Q".
        ESGRangeError
            If numeric values fall outside plausible actuarial ranges
            (only when ``config.raise_on_range_violation`` is True).
        ScenarioAdequacyWarning
            If the number of unique scenarios is below
            ``config.minimum_scenarios`` (only when
            ``config.warn_on_low_scenario_count`` is True).
        """
        path = Path(path).resolve()
        self._check_file_exists(path)
        df = pd.read_csv(path)
        self._validate_schema(df, path)
        df = self._cast_dtypes(df)
        self._validate_ranges(df)
        self._check_scenario_count(df)
        return df

    def load_from_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """Validate an already-loaded DataFrame against the ESG schema.

        Useful when the raw DataFrame is constructed programmatically
        (e.g. from a synthetic fixture in unit tests) rather than read
        from disk.

        Parameters
        ----------
        df : pd.DataFrame
            DataFrame to validate.  Must satisfy the same schema rules as
            a file loaded via ``load()``.

        Returns
        -------
        pd.DataFrame
            The same DataFrame after validation and dtype casting.

        Raises
        ------
        ESGSchemaError, ESGRangeError, ScenarioAdequacyWarning
            As per ``load()``.
        """
        self._validate_schema(df, path=Path("<in-memory>"))
        df = self._cast_dtypes(df)
        self._validate_ranges(df)
        self._check_scenario_count(df)
        return df

    # ------------------------------------------------------------------
    # Validation helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _check_file_exists(path: Path) -> None:
        """Raise FileNotFoundError with the resolved path in the message."""
        if not path.exists():
            raise FileNotFoundError(
                f"ESGAdapter: ESG file not found at '{path}'.  "
                f"Check the path and ensure the Moody's export is complete."
            )

    @staticmethod
    def _validate_schema(df: pd.DataFrame, path: Path) -> None:
        """Check column presence, dtype compatibility, and measure values."""
        # 1. Column presence
        missing = [col for col in _REQUIRED_COLUMNS if col not in df.columns]
        if missing:
            raise ESGSchemaError(
                f"ESGAdapter: Required column(s) missing from '{path.name}': "
                f"{missing}.  "
                f"Expected columns: {list(_REQUIRED_COLUMNS.keys())}."
            )

        # 2. Dtype compatibility
        dtype_errors: List[str] = []
        for col, (kind_codes, description) in _REQUIRED_COLUMNS.items():
            if col == "measure":
                # Measure handled separately below
                continue
            col_kind = df[col].dtype.kind
            if col_kind not in kind_codes:
                dtype_errors.append(
                    f"  '{col}' ({description}): expected dtype kind in "
                    f"{list(kind_codes)}, got dtype={df[col].dtype} "
                    f"(kind='{col_kind}')"
                )
        if dtype_errors:
            raise ESGSchemaError(
                f"ESGAdapter: Column dtype errors in '{path.name}':\n"
                + "\n".join(dtype_errors)
            )

        # 3. Measure column — must be convertible to string and contain only P/Q
        try:
            measure_vals = df["measure"].astype(str).str.strip().unique()
        except Exception as exc:
            raise ESGSchemaError(
                f"ESGAdapter: Cannot read 'measure' column: {exc}"
            ) from exc

        invalid_measures = set(measure_vals) - {"P", "Q"}
        if invalid_measures:
            raise ESGSchemaError(
                f"ESGAdapter: 'measure' column contains invalid values "
                f"{sorted(invalid_measures)}.  "
                f"Only 'P' (real-world) and 'Q' (risk-neutral) are permitted.  "
                f"IA TAS M §3.9 — measure must be explicitly declared."
            )

    @staticmethod
    def _cast_dtypes(df: pd.DataFrame) -> pd.DataFrame:
        """Cast required columns to canonical dtypes (non-destructive copy)."""
        df = df.copy()
        for col in ("scenario_id", "month"):
            df[col] = df[col].astype(np.int64)
        for col in ("r_short", "zcb_1y", "zcb_10y", "equity_index"):
            df[col] = df[col].astype(np.float64)
        df["measure"] = df["measure"].astype(str).str.strip()
        return df

    def _validate_ranges(self, df: pd.DataFrame) -> None:
        """Check numeric columns against plausible actuarial ranges.

        Raises ``ESGRangeError`` (when configured) or logs a warning
        for each column that has out-of-range values.
        """
        range_errors: List[str] = []

        for col, (lo, hi, lo_inc, hi_inc) in _RANGE_RULES.items():
            series = df[col]

            # Build violation mask
            mask = pd.Series(False, index=series.index)
            if lo is not None:
                mask |= (series < lo) if lo_inc else (series <= lo)
            if hi is not None:
                mask |= (series > hi) if hi_inc else (series >= hi)

            n_violations = int(mask.sum())
            if n_violations > 0:
                observed_min = float(series.min())
                observed_max = float(series.max())
                lo_sym = "[" if lo_inc else "("
                hi_sym = "]" if hi_inc else ")"
                lo_str = f"{lo}" if lo is not None else "-∞"
                hi_str = f"{hi}" if hi is not None else "+∞"
                range_errors.append(
                    f"  '{col}': {n_violations} value(s) outside "
                    f"{lo_sym}{lo_str}, {hi_str}{hi_sym}.  "
                    f"Observed range: [{observed_min:.6g}, {observed_max:.6g}].  "
                    f"Field: {_REQUIRED_COLUMNS[col][1]}"
                )

        if range_errors:
            msg = (
                "ESGAdapter: Value range violations (SOA ASOP 56 / CBIRC plausibility):\n"
                + "\n".join(range_errors)
            )
            if self.config.raise_on_range_violation:
                raise ESGRangeError(msg)
            else:
                warnings.warn(msg, UserWarning, stacklevel=4)

    def _check_scenario_count(self, df: pd.DataFrame) -> None:
        """Issue ScenarioAdequacyWarning if scenario count is too low.

        SOA ASOP 56 §3.5: minimum 500 scenarios for any production use.
        ESGAdapter warns (does not block) to allow test fixtures with
        small scenario counts to proceed.
        """
        if not self.config.warn_on_low_scenario_count:
            return

        n_scenarios = df["scenario_id"].nunique()
        if n_scenarios < self.config.minimum_scenarios:
            warnings.warn(
                f"ESGAdapter: Scenario count ({n_scenarios}) is below the "
                f"ASOP 56 §3.5 minimum of {self.config.minimum_scenarios} "
                f"for production use.  "
                f"TVOG minimum: {SCENARIO_MINIMUM_TVOG} "
                f"(recommended {SCENARIO_RECOMMENDED_TVOG}).  "
                f"VaR 99.5% minimum: {SCENARIO_MINIMUM_VAR} "
                f"(recommended {SCENARIO_RECOMMENDED_VAR}).  "
                f"This file should only be used for development / testing.",
                ScenarioAdequacyWarning,
                stacklevel=3,
            )

    # ------------------------------------------------------------------
    # Introspection helpers
    # ------------------------------------------------------------------

    @staticmethod
    def required_columns() -> List[str]:
        """Return the list of required column names."""
        return list(_REQUIRED_COLUMNS.keys())

    @staticmethod
    def schema_description() -> Dict[str, str]:
        """Return {column: description} for all required columns."""
        return {col: desc for col, (_, desc) in _REQUIRED_COLUMNS.items()}
