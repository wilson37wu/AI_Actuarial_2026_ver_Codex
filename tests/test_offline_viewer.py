"""Phase 16 Task 1 — offline result-viewer bundler + schema + offline-safety tests."""
from __future__ import annotations

import json
import os
import re
import importlib.util

import pytest

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SCRIPT = os.path.join(_REPO, "scripts", "build_offline_viewer.py")
_TEMPLATE = os.path.join(_REPO, "par_model_v2", "viewer", "viewer_template.html")


def _mod():
    spec = importlib.util.spec_from_file_location("build_offline_viewer", _SCRIPT)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


@pytest.fixture(scope="module")
def data():
    return _mod().build_viewer_data()


def test_schema_sections_present(data):
    for k in ["meta", "verdicts", "summary", "capital", "tail", "proxy", "governance"]:
        assert k in data, k
    assert data["meta"]["model_name"]
    assert "EDUCATIONAL" in data["meta"]["classification"]
    assert data["meta"]["source_files"], "no source files discovered"


def test_capital_fields_populated(data):
    c = data["capital"]
    for k in ["rate_scr", "equity_scr", "standalone_sum", "correlated_scr", "nested_scr"]:
        assert isinstance(c.get(k), (int, float)), k
    # var-cov should sit below the nested diversified benchmark (diversification)
    assert c["correlated_scr"] < c["standalone_sum"]
    assert 0 <= c["formula_vs_nested_rel_error"] < 1


def test_tail_and_proxy_present(data):
    t = data["tail"]
    assert t.get("var_path") and len(t["var_path"]) >= 2
    assert t.get("var_ci") and t["var_ci"][0] is not None
    rows = data["proxy"]["degree_rows"]
    assert rows and all("degree" in r and "oos_r2" in r for r in rows)
    assert data["proxy"]["selected_degree"] is not None


def test_governance_includes_mr011(data):
    ids = [r["risk_id"] for r in data["governance"]["risk_register"]]
    assert "MR-011" in ids
    assert data["governance"]["audit_entries"] >= 28
    assert any(c["title"].startswith("Phase 15 Task 5") for c in data["governance"]["change_records"])


def test_render_embeds_parseable_json(data):
    html = _mod().render_html(data)
    assert "/*__VIEWER_DATA__*/null" not in html, "token not replaced"
    m = re.search(r"const EMBEDDED = (\{.*?\});\n", html, re.S)
    assert m, "embedded payload not found"
    parsed = json.loads(m.group(1))
    assert parsed["meta"]["model_name"] == data["meta"]["model_name"]
    assert parsed["governance"]["risk_register"]


def test_html_is_offline_safe(data):
    html = _mod().render_html(data).lower()
    # no external network dependencies of any kind
    for bad in ["http://", "https://", "cdn", "<script src", "<link", "@import", "fonts.google"]:
        assert bad not in html, "external reference found: " + bad


def test_template_has_token():
    tpl = open(_TEMPLATE).read()
    assert "/*__VIEWER_DATA__*/null" in tpl
    assert "<!DOCTYPE html>" in tpl
