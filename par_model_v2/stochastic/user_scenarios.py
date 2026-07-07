"""ES-1 - User-supplied economic scenario file: validating loader.

Owner directive (2026-07-08, KCW, interactive session): allow USER-INPUT
economic scenario FILES alongside the built-in HW1F + GBM scenario
generator.  Format spec: ``docs/ECONOMIC_SCENARIO_FILE_FORMAT.md``
(schema ``esg-user-scenarios-1.0``); templates in ``docs/templates/``.

This module implements the ES-1 half of the track: a FAIL-LOUD validating
loader that turns the two user files

* ``economic_scenarios.csv``            - scenario table (§2 of the spec)
* ``economic_scenarios_manifest.json``  - conventions + integrity digest (§3)

into an in-memory :class:`UserScenarioSet` (numpy arrays), enforcing every
§4 validation rule with the offending ROW and COLUMN reported so the ES-2
GUI can surface precise errors.  Nothing here touches the governed engine:
``scenario_source`` selection, the measure guard and the run governance
trail are ES-3 scope.

Governance: user scenario files are SCENARIO INPUTS and remain UNSIGNED
pending Model Owner approval of the generating source.  Every loaded set
carries the file digest (sha256) and the UNSIGNED banner; the loader also
echoes a summary card (p5/median/p95 of the 10Y rate and EQ_RETURN at
projection years 1/10/50/100) for eyeball verification per spec §4.6.
"""
from __future__ import annotations

import csv
import hashlib

import json
import math
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

SCHEMA_ID = "esg-user-scenarios-1.0"

TENOR_LABELS: Tuple[str, ...] = (
    "3M", "6M", "9M", "1Y", "2Y", "3Y", "5Y", "7Y", "10Y", "15Y", "20Y",
    "30Y")
TENOR_YEARS: Tuple[float, ...] = (
    0.25, 0.5, 0.75, 1.0, 2.0, 3.0, 5.0, 7.0, 10.0, 15.0, 20.0, 30.0)

EXPECTED_HEADER: Tuple[str, ...] = (
    ("scenario", "year") + TENOR_LABELS + ("EQ_RETURN",))

PROJECTION_YEARS = 100          # engine horizon - must be exact (spec §1)
MIN_SCENARIOS = 100             # loader floor (spec §1)
CROSS_SCENARIO_COUNT = 2000     # C-ROSS capital-run standard (spec §5)

RATE_MIN, RATE_MAX = -0.05, 0.30            # spec §4.4
EQ_RETURN_MIN, EQ_RETURN_MAX = -0.99, 3.00  # spec §4.4

VALID_BASES = ("risk_neutral", "real_world")

REQUIRED_RATE_CONVENTION = {
    "type": "zero_coupon_spot", "compounding": "annual", "units": "decimal"}
REQUIRED_EQUITY_CONVENTION = {
    "type": "annual_total_return", "units": "decimal"}

REQUIRED_MANIFEST_KEYS = (
    "schema", "n_scenarios", "projection_years", "basis", "rate_convention",
    "equity_convention", "currency", "source", "created_utc", "csv_sha256")

CSV_DEFAULT_NAME = "economic_scenarios.csv"
MANIFEST_DEFAULT_NAME = "economic_scenarios_manifest.json"

MAX_REPORTED_ERRORS = 50        # cap the error list; the count is still exact

UNSIGNED_BANNER = (
    "UNSIGNED - user-supplied economic scenario file; the generating source "
    "has NOT been approved by the Model Owner. Scenario input only, never a "
    "governed calibration; every run records the file digest.")

SUMMARY_CARD_YEARS = (1, 10, 50, 100)
SUMMARY_PERCENTILES = (5, 50, 95)


class UserScenarioValidationError(ValueError):
    """Raised when the scenario file/manifest fails §4 validation.

    ``errors`` is a list of dicts with keys ``where`` (file), ``row``
    (1-based CSV line number incl. header, or None), ``column`` (name or
    None) and ``message``.  ``n_errors`` is the TOTAL number of errors
    found, which may exceed ``len(errors)`` (reporting is capped at
    :data:`MAX_REPORTED_ERRORS`).
    """

    def __init__(self, errors: List[Dict[str, Any]], n_errors: int) -> None:
        self.errors = errors
        self.n_errors = n_errors
        lines = [
            f"user scenario validation FAILED ({n_errors} error(s); "
            f"showing {len(errors)}):"]
        for e in errors:
            loc = e["where"]
            if e.get("row") is not None:
                loc += f" row {e['row']}"
            if e.get("column"):
                loc += f" col {e['column']}"
            lines.append(f"  - [{loc}] {e['message']}")
        super().__init__("\n".join(lines))


def _err(where: str, message: str, row: Optional[int] = None,
         column: Optional[str] = None) -> Dict[str, Any]:
    return {"where": where, "row": row, "column": column, "message": message}


def compute_csv_sha256(csv_path: str) -> str:
    """SHA-256 hex digest of the CSV file bytes (manifest §3 convention)."""
    h = hashlib.sha256()
    with open(csv_path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


@dataclass
class UserScenarioSet:
    """Validated in-memory scenario set (spec ``esg-user-scenarios-1.0``)."""

    n_scenarios: int
    projection_years: int
    basis: str
    tenor_labels: Tuple[str, ...]
    tenor_years: Tuple[float, ...]
    # rates[s, y, t]: annually-compounded decimal spot zero, curve at END of
    # projection year y+1; eq_returns[s, y]: annual equity total return OVER
    # projection year y+1.
    rates: np.ndarray
    eq_returns: np.ndarray
    manifest: Dict[str, Any]
    csv_sha256: str
    csv_path: str
    manifest_path: str
    unsigned: bool = True
    unsigned_banner: str = UNSIGNED_BANNER
    warnings: List[str] = field(default_factory=list)

    def summary_card(self) -> Dict[str, Any]:
        """§4.6 eyeball-verification card: p5/p50/p95 of the 10Y spot rate
        and EQ_RETURN at projection years 1/10/50/100, plus provenance."""
        t10 = self.tenor_labels.index("10Y")
        per_year: Dict[str, Any] = {}
        for year in SUMMARY_CARD_YEARS:
            if year > self.projection_years:
                continue
            yi = year - 1
            r = self.rates[:, yi, t10]
            q = self.eq_returns[:, yi]
            per_year[str(year)] = {
                "rate_10y": {
                    f"p{p}": float(np.percentile(r, p))
                    for p in SUMMARY_PERCENTILES},
                "eq_return": {
                    f"p{p}": float(np.percentile(q, p))
                    for p in SUMMARY_PERCENTILES},
            }
        return {
            "schema": SCHEMA_ID,
            "n_scenarios": self.n_scenarios,
            "projection_years": self.projection_years,
            "basis": self.basis,
            "currency": self.manifest.get("currency"),
            "source": self.manifest.get("source"),
            "csv_sha256": self.csv_sha256,
            "unsigned": self.unsigned,
            "unsigned_banner": self.unsigned_banner,
            "warnings": list(self.warnings),
            "by_projection_year": per_year,
        }

    def render_summary_card_text(self) -> str:
        """Plain-text echo of :meth:`summary_card` (loader console echo)."""
        card = self.summary_card()
        lines = [
            "=== USER ECONOMIC SCENARIO SET (" + SCHEMA_ID + ") ===",
            self.unsigned_banner,
            (f"scenarios={self.n_scenarios}  years={self.projection_years}  "
             f"basis={self.basis}  currency={card['currency']}"),
            f"source: {card['source']}",
            f"csv sha256: {self.csv_sha256}",
        ]
        for warn in self.warnings:
            lines.append(f"WARNING: {warn}")
        lines.append("year   10Y-rate p5/p50/p95        EQ_RETURN p5/p50/p95")
        for year, stats in card["by_projection_year"].items():
            r, q = stats["rate_10y"], stats["eq_return"]
            lines.append(
                f"{year:>4}   "
                f"{r['p5']:.4f}/{r['p50']:.4f}/{r['p95']:.4f}   "
                f"{q['p5']:+.4f}/{q['p50']:+.4f}/{q['p95']:+.4f}")
        return "\n".join(lines)


def _validate_manifest(manifest_path: str,
                       errors: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    where = os.path.basename(manifest_path)
    if not os.path.isfile(manifest_path):
        errors.append(_err(where, "manifest file not found"))
        return None
    try:
        with open(manifest_path, "r", encoding="utf-8") as fh:
            manifest = json.load(fh)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        errors.append(_err(where, f"manifest is not parseable JSON: {exc}"))
        return None
    if not isinstance(manifest, dict):
        errors.append(_err(where, "manifest must be a JSON object"))
        return None

    for key in REQUIRED_MANIFEST_KEYS:
        if key not in manifest:
            errors.append(_err(where, f"missing required key '{key}'"))
    if errors:
        return manifest

    if manifest["schema"] != SCHEMA_ID:
        errors.append(_err(
            where, f"schema must be '{SCHEMA_ID}', got "
                   f"'{manifest['schema']}'", column="schema"))
    if not isinstance(manifest["n_scenarios"], int) \
            or isinstance(manifest["n_scenarios"], bool) \
            or manifest["n_scenarios"] < MIN_SCENARIOS:
        errors.append(_err(
            where, f"n_scenarios must be an integer >= {MIN_SCENARIOS}, got "
                   f"{manifest['n_scenarios']!r}", column="n_scenarios"))
    if manifest["projection_years"] != PROJECTION_YEARS:
        errors.append(_err(
            where, f"projection_years must be exactly {PROJECTION_YEARS} "
                   f"(engine horizon), got "
                   f"{manifest['projection_years']!r}",
            column="projection_years"))
    if manifest["basis"] not in VALID_BASES:
        errors.append(_err(
            where, f"basis must be one of {list(VALID_BASES)}, got "
                   f"{manifest['basis']!r}", column="basis"))

    rc = manifest.get("rate_convention")
    if not isinstance(rc, dict):
        errors.append(_err(where, "rate_convention must be an object",
                           column="rate_convention"))
    else:
        for k, v in REQUIRED_RATE_CONVENTION.items():
            if rc.get(k) != v:
                errors.append(_err(
                    where, f"rate_convention.{k} must be '{v}', got "
                           f"{rc.get(k)!r}", column="rate_convention"))
    ec = manifest.get("equity_convention")
    if not isinstance(ec, dict):
        errors.append(_err(where, "equity_convention must be an object",
                           column="equity_convention"))
    else:
        for k, v in REQUIRED_EQUITY_CONVENTION.items():
            if ec.get(k) != v:
                errors.append(_err(
                    where, f"equity_convention.{k} must be '{v}', got "
                           f"{ec.get(k)!r}", column="equity_convention"))

    for key in ("currency", "source", "created_utc", "csv_sha256"):
        if not isinstance(manifest.get(key), str) or not manifest[key].strip():
            errors.append(_err(
                where, f"'{key}' must be a non-empty string", column=key))
    return manifest


def _parse_float(token: str) -> float:
    """Strict finite-decimal parse: rejects blanks, NaN, inf, and any
    non-numeric text (raises ValueError)."""
    text = token.strip()
    if not text:
        raise ValueError("blank cell")
    value = float(text)     # raises ValueError on non-numeric text
    if math.isnan(value) or math.isinf(value):
        raise ValueError(f"non-finite value {text!r}")
    return value


def _parse_int(token: str) -> int:
    text = token.strip()
    if not text or not (text.isdigit()
                        or (text[0] in "+-" and text[1:].isdigit())):
        raise ValueError(f"not an integer: {token!r}")
    return int(text)


def load_user_scenario_set(
        csv_path: str,
        manifest_path: Optional[str] = None) -> UserScenarioSet:
    """Load + validate a user economic scenario file pair (spec §4).

    FAIL-LOUD: raises :class:`UserScenarioValidationError` listing every
    violation (row/column reported, capped at ``MAX_REPORTED_ERRORS``).
    On success returns the validated :class:`UserScenarioSet` with the
    UNSIGNED banner attached and any §5 advisory warnings (e.g. scenario
    count below the C-ROSS capital standard).
    """
    if manifest_path is None:
        manifest_path = os.path.join(
            os.path.dirname(os.path.abspath(csv_path)), MANIFEST_DEFAULT_NAME)

    errors: List[Dict[str, Any]] = []
    n_errors = 0

    def add(e: Dict[str, Any]) -> None:
        nonlocal n_errors
        n_errors += 1
        if len(errors) < MAX_REPORTED_ERRORS:
            errors.append(e)

    csv_where = os.path.basename(csv_path)

    manifest = _validate_manifest(manifest_path, errors)
    n_errors = len(errors)
    if manifest is None or errors:
        raise UserScenarioValidationError(errors, n_errors)

    if not os.path.isfile(csv_path):
        add(_err(csv_where, "scenario CSV file not found"))
        raise UserScenarioValidationError(errors, n_errors)

    # §4.5 integrity: manifest digest must match the file byte-for-byte.
    actual_sha = compute_csv_sha256(csv_path)
    declared_sha = str(manifest["csv_sha256"]).strip().lower()
    if actual_sha != declared_sha:
        add(_err(
            os.path.basename(manifest_path),
            f"csv_sha256 mismatch: manifest declares {declared_sha!r} but "
            f"file digest is '{actual_sha}'", column="csv_sha256"))
        raise UserScenarioValidationError(errors, n_errors)

    n_scenarios = int(manifest["n_scenarios"])
    expected_rows = n_scenarios * PROJECTION_YEARS

    rates = np.empty((n_scenarios, PROJECTION_YEARS, len(TENOR_LABELS)),
                     dtype=np.float64)
    eq_returns = np.empty((n_scenarios, PROJECTION_YEARS), dtype=np.float64)

    with open(csv_path, "r", encoding="utf-8", newline="") as fh:
        reader = csv.reader(fh)
        # §4.1 header: names, order, count - exact.
        try:
            header = next(reader)
        except StopIteration:
            add(_err(csv_where, "file is empty (no header row)", row=1))
            raise UserScenarioValidationError(errors, n_errors)
        if tuple(h.strip() for h in header) != EXPECTED_HEADER:
            add(_err(
                csv_where,
                "header must be exactly "
                f"'{','.join(EXPECTED_HEADER)}', got "
                f"'{','.join(h.strip() for h in header)}'", row=1))
            raise UserScenarioValidationError(errors, n_errors)

        # §4.2 structure: contiguous scenarios 1..N, complete years 1..100,
        # sorted, no duplicates.  Because the required ordering is total,
        # row i (0-based) MUST be (scenario=i//100+1, year=i%100+1); any
        # deviation is a structural error and parsing stops there (every
        # subsequent row would be misaligned).
        data_index = 0
        structural_stop = False
        for row in reader:
            line_no = data_index + 2      # 1-based file line (header = 1)
            if len(row) != len(EXPECTED_HEADER):
                add(_err(
                    csv_where,
                    f"expected {len(EXPECTED_HEADER)} columns, got "
                    f"{len(row)}", row=line_no))
                structural_stop = True
                break
            if data_index >= expected_rows:
                add(_err(
                    csv_where,
                    f"more data rows than manifest n_scenarios="
                    f"{n_scenarios} x {PROJECTION_YEARS} years = "
                    f"{expected_rows}", row=line_no))
                structural_stop = True
                break

            exp_scen = data_index // PROJECTION_YEARS + 1
            exp_year = data_index % PROJECTION_YEARS + 1
            try:
                scen = _parse_int(row[0])
            except ValueError as exc:
                add(_err(csv_where, str(exc), row=line_no, column="scenario"))
                structural_stop = True
                break
            try:
                year = _parse_int(row[1])
            except ValueError as exc:
                add(_err(csv_where, str(exc), row=line_no, column="year"))
                structural_stop = True
                break
            if scen != exp_scen or year != exp_year:
                add(_err(
                    csv_where,
                    f"row out of sequence: expected scenario {exp_scen} "
                    f"year {exp_year} (rows sorted by scenario then year, "
                    f"scenarios contiguous 1..{n_scenarios}, years complete "
                    f"1..{PROJECTION_YEARS}, no gaps or duplicates); got "
                    f"scenario {scen} year {year}", row=line_no))
                structural_stop = True
                break

            si, yi = scen - 1, year - 1
            # §4.3 numeric + §4.4 bounds, per cell with row/col reported.
            for ci, col in enumerate(TENOR_LABELS):
                token = row[2 + ci]
                try:
                    value = _parse_float(token)
                except ValueError as exc:
                    add(_err(csv_where, str(exc), row=line_no, column=col))
                    value = np.nan
                else:
                    if not (RATE_MIN <= value <= RATE_MAX):
                        add(_err(
                            csv_where,
                            f"rate {value} outside plausibility bounds "
                            f"[{RATE_MIN}, {RATE_MAX}]",
                            row=line_no, column=col))
                rates[si, yi, ci] = value
            token = row[2 + len(TENOR_LABELS)]
            try:
                value = _parse_float(token)
            except ValueError as exc:
                add(_err(csv_where, str(exc), row=line_no,
                         column="EQ_RETURN"))
                value = np.nan
            else:
                if not (EQ_RETURN_MIN <= value <= EQ_RETURN_MAX):
                    add(_err(
                        csv_where,
                        f"EQ_RETURN {value} outside plausibility bounds "
                        f"[{EQ_RETURN_MIN}, {EQ_RETURN_MAX}]",
                        row=line_no, column="EQ_RETURN"))
            eq_returns[si, yi] = value
            data_index += 1

        if not structural_stop and data_index != expected_rows:
            add(_err(
                csv_where,
                f"expected {expected_rows} data rows (n_scenarios="
                f"{n_scenarios} x {PROJECTION_YEARS} years), found "
                f"{data_index}", row=data_index + 1))

    if n_errors:
        raise UserScenarioValidationError(errors, n_errors)

    warnings: List[str] = []
    if n_scenarios < CROSS_SCENARIO_COUNT:
        warnings.append(
            f"scenario count {n_scenarios} is below the C-ROSS capital-run "
            f"standard of >= {CROSS_SCENARIO_COUNT}; acceptable for "
            "diagnostics, WARN if used for capital figures (spec §5)")

    return UserScenarioSet(
        n_scenarios=n_scenarios,
        projection_years=PROJECTION_YEARS,
        basis=str(manifest["basis"]),
        tenor_labels=TENOR_LABELS,
        tenor_years=TENOR_YEARS,
        rates=rates,
        eq_returns=eq_returns,
        manifest=manifest,
        csv_sha256=actual_sha,
        csv_path=os.path.abspath(csv_path),
        manifest_path=os.path.abspath(manifest_path),
        warnings=warnings,
    )


def collect_validation_errors(
        csv_path: str,
        manifest_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Non-raising wrapper for GUI callers (ES-2): returns the error list
    ([] when the file pair is valid)."""
    try:
        load_user_scenario_set(csv_path, manifest_path)
    except UserScenarioValidationError as exc:
        return exc.errors
    return []
