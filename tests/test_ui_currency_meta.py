"""Phase UIL Task 4 (B4+A1): tests for the GUI currency wire-through.

Covers scripts/build_ui_data.py::_resolve_currency_meta source priority
(model_inputs.json -> RUN_MODEL_SUMMARY.json -> neutral default), soft
degradation on a broken inputs file (display metadata must never crash the
bundler), the meta stamping in build_ui_data(), and the presence of the
fmtMoney formatter + meta schema lines in the embedded HTML template.

The neutral default is the backward-compatibility gate: with no user inputs
and no run evidence the currency block must format money exactly like the
pre-1.12.0 bare-number display (no symbol, comma thousands, 0 decimals).
"""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import build_ui_data as bud  # noqa: E402

CUR_USD = {
    "code": "USD", "symbol": "$", "decimals": 0,
    "scale": "units", "thousands": "comma",
}
CUR_EUR = {
    "code": "EUR", "symbol": "E", "decimals": 2,
    "scale": "units", "thousands": "space",
}


@pytest.fixture(autouse=True)
def _no_ambient_inputs(monkeypatch, tmp_path):
    """Isolate every test from repo-level model_inputs.json and env vars.

    find_model_inputs is wrapped so the repo-root / production_run candidate
    files can never leak into a test; the PAR_MODEL_INPUTS env-var path stays
    fully functional for the tests that set it explicitly.
    """
    monkeypatch.delenv("PAR_MODEL_INPUTS", raising=False)
    import par_model_v2.user_inputs as pui
    real_find = pui.find_model_inputs

    def _isolated(path=None):
        if path is None and not os.environ.get("PAR_MODEL_INPUTS"):
            return None  # ignore ambient repo-level model_inputs.json
        return real_find(path)

    monkeypatch.setattr(pui, "find_model_inputs", _isolated)
    # Point the run-summary path somewhere empty unless a test overrides it.
    monkeypatch.setattr(bud, "RUN_SUMMARY_PATH",
                        str(tmp_path / "ABSENT_RUN_MODEL_SUMMARY.json"))
    yield


def _write(path, obj):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh)
    return str(path)


# ------------------------------------------------------------- resolution
def test_neutral_default_when_no_sources():
    out = bud._resolve_currency_meta()
    assert out["currency"]["code"] is None
    assert out["currency"]["symbol"] == ""
    assert out["currency"]["decimals"] == 0
    assert out["currency"]["thousands"] == "comma"
    assert "NEUTRAL_DEFAULT" in out["currency_source"]
    assert out["output_label"] is None


def test_run_summary_is_second_priority(monkeypatch, tmp_path):
    rs = _write(tmp_path / "RUN_MODEL_SUMMARY.json",
                {"output_label": "RunX", "currency": dict(CUR_USD)})
    monkeypatch.setattr(bud, "RUN_SUMMARY_PATH", rs)
    out = bud._resolve_currency_meta()
    assert out["currency"]["code"] == "USD"
    assert out["currency"]["symbol"] == "$"
    assert "RUN_MODEL_SUMMARY" in out["currency_source"]
    assert out["output_label"] == "RunX"


def test_model_inputs_wins_over_run_summary(monkeypatch, tmp_path):
    rs = _write(tmp_path / "RUN_MODEL_SUMMARY.json",
                {"output_label": "RunFromEvidence",
                 "currency": dict(CUR_USD)})
    mi = _write(tmp_path / "model_inputs.json",
                {"schema_version": "1.0.0", "currency": dict(CUR_EUR),
                 "run_settings": {"output_label": "LabelFromInputs"}})
    monkeypatch.setattr(bud, "RUN_SUMMARY_PATH", rs)
    monkeypatch.setenv("PAR_MODEL_INPUTS", mi)
    out = bud._resolve_currency_meta()
    assert out["currency"]["code"] == "EUR"
    assert out["currency"]["thousands"] == "space"
    assert "model_inputs.json" in out["currency_source"]
    # run evidence label wins (it describes the artefacts actually bundled)
    assert out["output_label"] == "RunFromEvidence"


def test_output_label_falls_back_to_run_settings(monkeypatch, tmp_path):
    mi = _write(tmp_path / "model_inputs.json",
                {"schema_version": "1.0.0", "currency": dict(CUR_EUR),
                 "run_settings": {"output_label": "LabelFromInputs"}})
    monkeypatch.setenv("PAR_MODEL_INPUTS", mi)
    out = bud._resolve_currency_meta()
    assert out["output_label"] == "LabelFromInputs"


def test_broken_inputs_degrades_softly(monkeypatch, tmp_path):
    bad = tmp_path / "model_inputs.json"
    bad.write_text("{not json", encoding="utf-8")
    rs = _write(tmp_path / "RUN_MODEL_SUMMARY.json",
                {"output_label": "RunX", "currency": dict(CUR_USD)})
    monkeypatch.setattr(bud, "RUN_SUMMARY_PATH", rs)
    monkeypatch.setenv("PAR_MODEL_INPUTS", str(bad))
    out = bud._resolve_currency_meta()  # must NOT raise (display-only path)
    assert out["currency"]["code"] == "USD"
    assert "RUN_MODEL_SUMMARY" in out["currency_source"]


def test_partial_currency_block_gets_defaults(monkeypatch, tmp_path):
    rs = _write(tmp_path / "RUN_MODEL_SUMMARY.json",
                {"currency": {"code": "JPY", "symbol": "Y"}})
    monkeypatch.setattr(bud, "RUN_SUMMARY_PATH", rs)
    out = bud._resolve_currency_meta()
    cur = out["currency"]
    assert cur["code"] == "JPY"
    assert cur["decimals"] == 0 and cur["scale"] == "units"
    assert cur["thousands"] == "comma"


# ------------------------------------------------------------- meta stamping
def test_build_ui_data_stamps_meta(monkeypatch, tmp_path):
    rs = _write(tmp_path / "RUN_MODEL_SUMMARY.json",
                {"output_label": "RunX", "currency": dict(CUR_USD)})
    monkeypatch.setattr(bud, "RUN_SUMMARY_PATH", rs)
    data = bud.build_ui_data()
    meta = data["meta"]
    assert meta["currency"]["code"] == "USD"
    assert "currency_source" in meta and "output_label" in meta
    assert data["contract_version"] == bud.CONTRACT_VERSION


def test_contract_version_bumped_additively():
    major, minor, _patch = (int(x) for x in bud.CONTRACT_VERSION.split("."))
    assert major == 1, "contract major bump would be BREAKING, not allowed here"
    assert minor >= 12


# ------------------------------------------------------------- HTML template
def test_html_template_has_fmtmoney_and_schema_doc():
    t = bud.HTML_TEMPLATE
    assert "function fmtMoney(" in t
    assert "function curMeta()" in t
    assert "currency:{code,symbol,decimals,scale,thousands}" in t
    # money renders are routed: the headline SCR card uses fmtMoney
    assert "fmtMoney(cap.nested_scr)" in t
    # the generic numeric formatter is still available for counts/ratios
    assert "function num(" in t
