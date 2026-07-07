"""ES-1 - user economic scenario file validating loader tests.

Covers every §4 rule of docs/ECONOMIC_SCENARIO_FILE_FORMAT.md
(esg-user-scenarios-1.0): header, structure (contiguity / completeness /
ordering / duplicates), numeric cells, plausibility bounds, manifest
conventions + sha256 integrity, summary card echo and UNSIGNED banner.
"""
from __future__ import annotations

import csv
import hashlib
import json
import os

import numpy as np
import pytest

from par_model_v2.stochastic.user_scenarios import (
    CROSS_SCENARIO_COUNT, EXPECTED_HEADER, MANIFEST_DEFAULT_NAME, MIN_SCENARIOS,
    PROJECTION_YEARS, SCHEMA_ID, TENOR_LABELS, UNSIGNED_BANNER,
    UserScenarioValidationError, collect_validation_errors,
    compute_csv_sha256, load_user_scenario_set)

N_SCEN = MIN_SCENARIOS  # 100 scenarios x 100 years = 10,000 rows - fast


def _rates_for(scen: int, year: int):
    base = 0.02 + 0.00005 * (scen % 7) + 0.00002 * (year % 11)
    return [round(base + 0.001 * i, 6) for i in range(len(TENOR_LABELS))]


def _eq_for(scen: int, year: int) -> float:
    return round(0.06 + 0.01 * ((scen + year) % 5) - 0.02 * (scen % 3), 6)


def _write_csv(path, n_scen=N_SCEN, mutate=None):
    """Write a valid CSV; ``mutate(rows)`` may edit the row list in place."""
    rows = []
    for s in range(1, n_scen + 1):
        for y in range(1, PROJECTION_YEARS + 1):
            rows.append([s, y] + _rates_for(s, y) + [_eq_for(s, y)])
    if mutate is not None:
        mutate(rows)
    with open(path, "w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(EXPECTED_HEADER)
        writer.writerows(rows)


def _write_manifest(path, csv_path, n_scen=N_SCEN, override=None):
    manifest = {
        "schema": SCHEMA_ID,
        "n_scenarios": n_scen,
        "projection_years": PROJECTION_YEARS,
        "basis": "risk_neutral",
        "rate_convention": {"type": "zero_coupon_spot",
                            "compounding": "annual", "units": "decimal",
                            "day_count": "ACT/365F"},
        "equity_convention": {"type": "annual_total_return",
                              "units": "decimal"},
        "currency": "CNY",
        "source": "pytest synthetic ESG v1 (2026-07-08)",
        "created_utc": "2026-07-08T00:00:00Z",
        "csv_sha256": compute_csv_sha256(csv_path),
    }
    if override:
        manifest.update(override)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh)
    return manifest


@pytest.fixture()
def valid_pair(tmp_path):
    csv_path = tmp_path / "economic_scenarios.csv"
    man_path = tmp_path / MANIFEST_DEFAULT_NAME
    _write_csv(csv_path)
    _write_manifest(man_path, csv_path)
    return str(csv_path), str(man_path)


def _errors_for(csv_path, man_path):
    with pytest.raises(UserScenarioValidationError) as exc_info:
        load_user_scenario_set(csv_path, man_path)
    return exc_info.value.errors


# ---------------------------------------------------------------- happy path

def test_valid_pair_loads(valid_pair):
    csv_path, man_path = valid_pair
    ss = load_user_scenario_set(csv_path, man_path)
    assert ss.n_scenarios == N_SCEN
    assert ss.projection_years == PROJECTION_YEARS
    assert ss.basis == "risk_neutral"
    assert ss.rates.shape == (N_SCEN, PROJECTION_YEARS, len(TENOR_LABELS))
    assert ss.eq_returns.shape == (N_SCEN, PROJECTION_YEARS)
    assert np.isfinite(ss.rates).all() and np.isfinite(ss.eq_returns).all()
    # spot-check a known cell against the generator
    assert ss.rates[4, 9, 0] == pytest.approx(_rates_for(5, 10)[0])
    assert ss.eq_returns[2, 0] == pytest.approx(_eq_for(3, 1))


def test_manifest_path_defaults_to_csv_dir(valid_pair):
    csv_path, _ = valid_pair
    ss = load_user_scenario_set(csv_path)   # manifest_path omitted
    assert ss.n_scenarios == N_SCEN


def test_digest_recorded_and_matches(valid_pair):
    csv_path, man_path = valid_pair
    ss = load_user_scenario_set(csv_path, man_path)
    with open(csv_path, "rb") as fh:
        assert ss.csv_sha256 == hashlib.sha256(fh.read()).hexdigest()
    assert ss.manifest["csv_sha256"] == ss.csv_sha256


def test_unsigned_banner_and_flag(valid_pair):
    ss = load_user_scenario_set(*valid_pair)
    assert ss.unsigned is True
    assert "UNSIGNED" in ss.unsigned_banner
    card = ss.summary_card()
    assert card["unsigned"] is True
    assert card["unsigned_banner"] == UNSIGNED_BANNER
    assert "UNSIGNED" in ss.render_summary_card_text()


def test_summary_card_percentiles(valid_pair):
    ss = load_user_scenario_set(*valid_pair)
    card = ss.summary_card()
    by_year = card["by_projection_year"]
    assert set(by_year) == {"1", "10", "50", "100"}
    t10 = TENOR_LABELS.index("10Y")
    for year_key, stats in by_year.items():
        yi = int(year_key) - 1
        r = ss.rates[:, yi, t10]
        assert stats["rate_10y"]["p50"] == pytest.approx(
            float(np.percentile(r, 50)))
        assert stats["rate_10y"]["p5"] <= stats["rate_10y"]["p95"]
        q = ss.eq_returns[:, yi]
        assert stats["eq_return"]["p95"] == pytest.approx(
            float(np.percentile(q, 95)))
    text = ss.render_summary_card_text()
    assert SCHEMA_ID in text and str(ss.csv_sha256) in text


def test_cross_scenario_count_warning(valid_pair):
    ss = load_user_scenario_set(*valid_pair)
    assert any(str(CROSS_SCENARIO_COUNT) in w for w in ss.warnings)


def test_collect_validation_errors_empty_when_valid(valid_pair):
    assert collect_validation_errors(*valid_pair) == []


# ------------------------------------------------------------------ manifest

def test_missing_manifest(tmp_path):
    csv_path = tmp_path / "economic_scenarios.csv"
    _write_csv(csv_path)
    errors = _errors_for(str(csv_path), str(tmp_path / "nope.json"))
    assert any("not found" in e["message"] for e in errors)


def test_unparseable_manifest(tmp_path, valid_pair):
    csv_path, man_path = valid_pair
    with open(man_path, "w", encoding="utf-8") as fh:
        fh.write("{not json")
    errors = _errors_for(csv_path, man_path)
    assert any("parseable" in e["message"] for e in errors)


def test_missing_manifest_key(valid_pair):
    csv_path, man_path = valid_pair
    manifest = json.load(open(man_path, encoding="utf-8"))
    del manifest["basis"]
    json.dump(manifest, open(man_path, "w", encoding="utf-8"))
    errors = _errors_for(csv_path, man_path)
    assert any("'basis'" in e["message"] for e in errors)


@pytest.mark.parametrize("override,column", [
    ({"schema": "esg-user-scenarios-0.9"}, "schema"),
    ({"n_scenarios": MIN_SCENARIOS - 1}, "n_scenarios"),
    ({"n_scenarios": "1000"}, "n_scenarios"),
    ({"projection_years": 50}, "projection_years"),
    ({"basis": "realistic"}, "basis"),
    ({"rate_convention": {"type": "par_yield", "compounding": "annual",
                          "units": "decimal"}}, "rate_convention"),
    ({"rate_convention": {"type": "zero_coupon_spot",
                          "compounding": "continuous",
                          "units": "decimal"}}, "rate_convention"),
    ({"equity_convention": {"type": "price_return",
                            "units": "decimal"}}, "equity_convention"),
    ({"currency": ""}, "currency"),
    ({"csv_sha256": ""}, "csv_sha256"),
])
def test_manifest_convention_violations(tmp_path, override, column):
    csv_path = tmp_path / "economic_scenarios.csv"
    man_path = tmp_path / MANIFEST_DEFAULT_NAME
    _write_csv(csv_path)
    _write_manifest(man_path, csv_path, override=override)
    errors = _errors_for(str(csv_path), str(man_path))
    assert any(e["column"] == column for e in errors), errors


def test_sha256_mismatch(valid_pair):
    csv_path, man_path = valid_pair
    _write_manifest(man_path, csv_path, override={"csv_sha256": "0" * 64})
    errors = _errors_for(csv_path, man_path)
    assert any(e["column"] == "csv_sha256"
               and "mismatch" in e["message"] for e in errors)


# ----------------------------------------------------------------------- CSV

def test_missing_csv(tmp_path, valid_pair):
    csv_path, man_path = valid_pair
    os.remove(csv_path)
    errors = _errors_for(csv_path, man_path)
    assert any("not found" in e["message"] for e in errors)


def test_wrong_header_order(tmp_path):
    csv_path = tmp_path / "economic_scenarios.csv"
    man_path = tmp_path / MANIFEST_DEFAULT_NAME
    _write_csv(csv_path)
    text = open(csv_path, encoding="utf-8").read()
    bad = text.replace("scenario,year", "year,scenario", 1)
    open(csv_path, "w", encoding="utf-8", newline="").write(bad)
    _write_manifest(man_path, csv_path)   # digest of the mutated file
    errors = _errors_for(str(csv_path), str(man_path))
    assert any(e["row"] == 1 and "header" in e["message"] for e in errors)


def _mutated_pair(tmp_path, mutate):
    csv_path = tmp_path / "economic_scenarios.csv"
    man_path = tmp_path / MANIFEST_DEFAULT_NAME
    _write_csv(csv_path, mutate=mutate)
    _write_manifest(man_path, csv_path)
    return str(csv_path), str(man_path)


def test_non_numeric_cell_reports_row_and_column(tmp_path):
    def mutate(rows):
        rows[104][4] = "abc"        # scenario 2, year 5, tenor col '9M'
    errors = _errors_for(*_mutated_pair(tmp_path, mutate))
    assert any(e["row"] == 106 and e["column"] == "9M" for e in errors)


def test_blank_cell_rejected(tmp_path):
    def mutate(rows):
        rows[0][14] = ""            # EQ_RETURN, first data row
    errors = _errors_for(*_mutated_pair(tmp_path, mutate))
    assert any(e["row"] == 2 and e["column"] == "EQ_RETURN"
               and "blank" in e["message"] for e in errors)


@pytest.mark.parametrize("token", ["nan", "inf", "-inf"])
def test_non_finite_rejected(tmp_path, token):
    def mutate(rows):
        rows[3][2] = token
    errors = _errors_for(*_mutated_pair(tmp_path, mutate))
    assert any(e["row"] == 5 and e["column"] == "3M" for e in errors)


def test_rate_bounds(tmp_path):
    def mutate(rows):
        rows[10][2] = "0.31"        # > 0.30
        rows[11][3] = "-0.06"       # < -0.05
    errors = _errors_for(*_mutated_pair(tmp_path, mutate))
    assert any(e["row"] == 12 and e["column"] == "3M" for e in errors)
    assert any(e["row"] == 13 and e["column"] == "6M" for e in errors)


def test_eq_return_bounds(tmp_path):
    def mutate(rows):
        rows[20][14] = "3.5"
    errors = _errors_for(*_mutated_pair(tmp_path, mutate))
    assert any(e["row"] == 22 and e["column"] == "EQ_RETURN"
               and "bounds" in e["message"] for e in errors)


def test_boundary_values_accepted(tmp_path):
    def mutate(rows):
        rows[0][2] = "-0.05"
        rows[0][3] = "0.30"
        rows[0][14] = "-0.99"
        rows[1][14] = "3.00"
    csv_path, man_path = _mutated_pair(tmp_path, mutate)
    ss = load_user_scenario_set(csv_path, man_path)
    assert ss.rates[0, 0, 0] == pytest.approx(-0.05)
    assert ss.eq_returns[0, 1] == pytest.approx(3.00)


def test_duplicate_row_rejected(tmp_path):
    def mutate(rows):
        rows[50] = list(rows[49])   # duplicate (scenario 1, year 50)
    errors = _errors_for(*_mutated_pair(tmp_path, mutate))
    assert any("out of sequence" in e["message"] for e in errors)


def test_missing_year_rejected(tmp_path):
    def mutate(rows):
        del rows[30]                # scenario 1 loses year 31
    errors = _errors_for(*_mutated_pair(tmp_path, mutate))
    assert any("out of sequence" in e["message"] or "expected" in e["message"]
               for e in errors)


def test_unsorted_rows_rejected(tmp_path):
    def mutate(rows):
        rows[0], rows[1] = rows[1], rows[0]
    errors = _errors_for(*_mutated_pair(tmp_path, mutate))
    assert any("out of sequence" in e["message"] for e in errors)


def test_non_contiguous_scenarios_rejected(tmp_path):
    def mutate(rows):
        for r in rows:
            if r[0] == N_SCEN:
                r[0] = N_SCEN + 1   # gap: ...,99,101
    errors = _errors_for(*_mutated_pair(tmp_path, mutate))
    assert any("out of sequence" in e["message"] for e in errors)


def test_row_count_mismatch_vs_manifest(tmp_path):
    csv_path = tmp_path / "economic_scenarios.csv"
    man_path = tmp_path / MANIFEST_DEFAULT_NAME
    _write_csv(csv_path, n_scen=N_SCEN)
    _write_manifest(man_path, csv_path, n_scen=N_SCEN + 1)  # declares more
    errors = _errors_for(str(csv_path), str(man_path))
    assert any("out of sequence" in e["message"] or "data rows" in e["message"]
               for e in errors)


def test_extra_rows_rejected(tmp_path):
    def mutate(rows):
        rows.append([N_SCEN + 1, 1] + _rates_for(1, 1) + [0.05])
    errors = _errors_for(*_mutated_pair(tmp_path, mutate))
    assert any("more data rows" in e["message"]
               or "out of sequence" in e["message"] for e in errors)


def test_error_report_capped_but_counted(tmp_path):
    def mutate(rows):
        for r in rows[:80]:         # 80 bad EQ cells > 50-error cap
            r[14] = "9.99"
    with pytest.raises(UserScenarioValidationError) as exc_info:
        load_user_scenario_set(*_mutated_pair(tmp_path, mutate))
    exc = exc_info.value
    assert exc.n_errors == 80
    assert len(exc.errors) == 50


def test_collect_validation_errors_nonempty_when_invalid(tmp_path):
    def mutate(rows):
        rows[0][2] = "bad"
    csv_path, man_path = _mutated_pair(tmp_path, mutate)
    errors = collect_validation_errors(csv_path, man_path)
    assert errors and errors[0]["column"] == "3M"


# ------------------------------------------------------------------ template

def test_committed_template_header_matches_spec():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    template = os.path.join(root, "docs", "templates",
                            "economic_scenarios_TEMPLATE.csv")
    with open(template, encoding="utf-8") as fh:
        header = next(csv.reader(fh))
    assert tuple(h.strip() for h in header) == EXPECTED_HEADER


def test_committed_manifest_template_conventions():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    template = os.path.join(root, "docs", "templates",
                            "economic_scenarios_manifest_TEMPLATE.json")
    manifest = json.load(open(template, encoding="utf-8"))
    assert manifest["schema"] == SCHEMA_ID
    assert manifest["projection_years"] == PROJECTION_YEARS
    assert manifest["rate_convention"]["type"] == "zero_coupon_spot"
    assert manifest["rate_convention"]["compounding"] == "annual"
    assert manifest["rate_convention"]["units"] == "decimal"
    assert manifest["equity_convention"]["type"] == "annual_total_return"
    assert manifest["basis"] in ("risk_neutral", "real_world")
