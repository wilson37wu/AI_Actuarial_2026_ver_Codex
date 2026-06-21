"""Phase UIL Task 1 (B1): tests for scripts/load_user_inputs.py.

Covers: happy path on the shipped template, normalised JSON schema/totals,
and fail-loud validation (tab/row/field in every message) for each rule
class: range violations, allowed-set violations, incomplete rows, missing
tabs, and stale derived totals.
"""
import copy
import json
import os
import sys

import pytest

openpyxl = pytest.importorskip("openpyxl")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from load_user_inputs import (  # noqa: E402
    ALLOWED_PRODUCT_TYPES,
    SCHEMA_VERSION,
    InputValidationError,
    load_user_inputs,
    main,
)

TEMPLATE = os.path.join(os.path.dirname(__file__), "..", "production_run", "MODEL_INPUTS_TEMPLATE.xlsx")


# ----------------------------------------------------------------- fixtures
def _edit(tmp_path, mutate, name="edited.xlsx"):
    """Copy the shipped template, apply ``mutate(workbook)``, save, return path."""
    wb = openpyxl.load_workbook(TEMPLATE)
    mutate(wb)
    p = tmp_path / name
    wb.save(p)
    return str(p)


def _find_row(ws, prefix, col=1):
    for i, row in enumerate(ws.iter_rows(values_only=True), 1):
        v = row[col - 1] if row and len(row) >= col else None
        if v is not None and str(v).startswith(prefix):
            return i
    raise AssertionError("label %r not found in tab %r" % (prefix, ws.title))


# ----------------------------------------------------------------- happy path
class TestHappyPath:
    def test_shipped_template_loads(self):
        inputs = load_user_inputs(TEMPLATE)
        assert inputs["schema_version"] == SCHEMA_VERSION
        assert inputs["currency"]["code"] == "USD"
        assert inputs["currency"]["symbol"] == "$"
        assert inputs["balance_sheet"]["backing_asset_mv"] == pytest.approx(100000.0)
        assert inputs["balance_sheet"]["illiquid_share"] == pytest.approx(0.45)
        assert inputs["balance_sheet"]["forced_sale_fraction"] == pytest.approx(0.40)
        assert len(inputs["portfolio"]) == 3
        assert inputs["totals"]["policy_count"] == 2500
        assert inputs["totals"]["total_sum_assured"] == pytest.approx(
            100000 * 1200 + 150000 * 800 + 100000 * 500)
        assert inputs["assumptions"]["confidence"] == pytest.approx(0.995)
        assert inputs["run_settings"]["n_sim"] == 20000
        assert inputs["run_settings"]["output_label"] == "MyRun_2026Q1"

    def test_governed_frozen_readback_present(self):
        inputs = load_user_inputs(TEMPLATE)
        frozen = inputs["assumptions"]["governed_frozen_readback"]
        assert frozen["copula_df_single_t"] == pytest.approx(2.9451)

    def test_every_product_type_allowed(self):
        inputs = load_user_inputs(TEMPLATE)
        for p in inputs["portfolio"]:
            assert p["product_type"] in ALLOWED_PRODUCT_TYPES

    def test_cli_writes_valid_json(self, tmp_path, capsys):
        out = tmp_path / "model_inputs.json"
        rc = main(["--template", TEMPLATE, "--out", str(out)])
        assert rc == 0
        blob = json.loads(out.read_text())
        assert blob["schema_version"] == SCHEMA_VERSION
        echo = capsys.readouterr().out
        assert "USD" in echo and "100,000" in echo and "2,500" in echo


# ----------------------------------------------------------------- failures
class TestValidationFailures:
    def _expect_error(self, path, *needles):
        with pytest.raises(InputValidationError) as exc:
            load_user_inputs(path)
        msg = str(exc.value)
        for n in needles:
            assert n in msg, "expected %r in:\n%s" % (n, msg)
        return msg

    def test_missing_tab_fails(self, tmp_path):
        p = _edit(tmp_path, lambda wb: wb.remove(wb["Portfolio"]))
        self._expect_error(p, "Tab 'Portfolio'", "required tab missing")

    def test_bad_product_type(self, tmp_path):
        def mutate(wb):
            ws = wb["Portfolio"]
            ws.cell(row=5, column=1, value="NOT_A_PRODUCT")
        p = _edit(tmp_path, mutate)
        self._expect_error(p, "Tab 'Portfolio', row 5", "Product type", "NOT_A_PRODUCT")

    def test_incomplete_portfolio_row(self, tmp_path):
        def mutate(wb):
            wb["Portfolio"].cell(row=6, column=5).value = None  # blank Sum assured
        p = _edit(tmp_path, mutate)
        self._expect_error(p, "Tab 'Portfolio', row 6", "Sum assured", "incomplete")

    def test_negative_market_value(self, tmp_path):
        def mutate(wb):
            ws = wb["Balance Sheet"]
            r = _find_row(ws, "Listed equity")
            ws.cell(row=r, column=2, value=-5)
        p = _edit(tmp_path, mutate)
        self._expect_error(p, "Tab 'Balance Sheet'", "Market value", ">= 0")

    def test_forced_sale_fraction_out_of_range(self, tmp_path):
        def mutate(wb):
            ws = wb["Balance Sheet"]
            r = _find_row(ws, "Forced-sale fraction")
            ws.cell(row=r, column=2, value=1.5)
        p = _edit(tmp_path, mutate)
        self._expect_error(p, "Forced-sale fraction", "(0, 1]")

    def test_confidence_must_be_open_interval(self, tmp_path):
        def mutate(wb):
            ws = wb["Assumptions"]
            r = _find_row(ws, "Confidence level (SCR)")
            ws.cell(row=r, column=2, value=1.0)
        p = _edit(tmp_path, mutate)
        self._expect_error(p, "Tab 'Assumptions'", "Confidence level (SCR)")

    def test_benefit_share_zero_rejected(self, tmp_path):
        def mutate(wb):
            ws = wb["Assumptions"]
            r = _find_row(ws, "Benefit share (beta_fit)")
            ws.cell(row=r, column=2, value=0)
        p = _edit(tmp_path, mutate)
        self._expect_error(p, "Benefit share (beta_fit)")

    def test_bad_currency_code(self, tmp_path):
        def mutate(wb):
            ws = wb["Currency"]
            r = _find_row(ws, "Reporting currency code")
            ws.cell(row=r, column=2, value="DOLLARS")
        p = _edit(tmp_path, mutate)
        self._expect_error(p, "Tab 'Currency'", "ISO 4217")

    def test_bad_valuation_date(self, tmp_path):
        def mutate(wb):
            ws = wb["Currency"]
            r = _find_row(ws, "Valuation date")
            ws.cell(row=r, column=2, value="06/11/2026")
        p = _edit(tmp_path, mutate)
        self._expect_error(p, "Valuation date", "YYYY-MM-DD")

    def test_zero_policy_count(self, tmp_path):
        def mutate(wb):
            wb["Portfolio"].cell(row=7, column=7, value=0)
        p = _edit(tmp_path, mutate)
        self._expect_error(p, "Tab 'Portfolio', row 7", "Policy count", "positive integer")

    def test_bad_n_sim(self, tmp_path):
        def mutate(wb):
            ws = wb["Run Settings"]
            r = _find_row(ws, "Number of simulations")
            ws.cell(row=r, column=2, value="lots")
        p = _edit(tmp_path, mutate)
        self._expect_error(p, "Tab 'Run Settings'", "Number of simulations")

    def test_stale_stated_total_fails(self, tmp_path):
        def mutate(wb):
            ws = wb["Balance Sheet"]
            r = _find_row(ws, "Total backing asset market value")
            ws.cell(row=r, column=2, value=999999)
        p = _edit(tmp_path, mutate)
        self._expect_error(p, "Total backing asset market value", "does not match")

    def test_multiple_errors_reported_together(self, tmp_path):
        def mutate(wb):
            wb["Portfolio"].cell(row=5, column=1, value="BOGUS")
            ws = wb["Assumptions"]
            r = _find_row(ws, "Confidence level (SCR)")
            ws.cell(row=r, column=2, value=2)
        p = _edit(tmp_path, mutate)
        msg = self._expect_error(p, "BOGUS", "Confidence level (SCR)")
        assert msg.count("\n  - ") >= 2

    def test_missing_file(self):
        with pytest.raises(InputValidationError) as exc:
            load_user_inputs("/nonexistent/template.xlsx")
        assert "not found" in str(exc.value)

    def test_cli_exit_code_on_failure(self, tmp_path, capsys):
        def mutate(wb):
            wb["Portfolio"].cell(row=5, column=1, value="BOGUS")
        p = _edit(tmp_path, mutate)
        rc = main(["--template", p, "--out", str(tmp_path / "x.json")])
        assert rc == 1
        assert "BOGUS" in capsys.readouterr().err
        assert not (tmp_path / "x.json").exists()
