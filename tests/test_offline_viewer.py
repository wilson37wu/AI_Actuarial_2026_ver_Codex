"""Phase 16 — offline result-viewer bundler + schema + offline-safety tests.

Task 1 covered the base schema, governance, and offline-safety.
Task 2 adds the loss-distribution section (histogram + pre-computed
confidence/percentile/seed sweeps) and the interactive capital/tail dashboards,
plus the model-side loss-distribution emitter.
"""
from __future__ import annotations

import json
import os
import re
import importlib.util

import pytest

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SCRIPT = os.path.join(_REPO, "scripts", "build_offline_viewer.py")
_TEMPLATE = os.path.join(_REPO, "par_model_v2", "viewer", "viewer_template.html")
_LOSS_JSON = os.path.join(_REPO, "docs", "validation", "PHASE16_LOSS_DISTRIBUTION.json")


def _mod():
    spec = importlib.util.spec_from_file_location("build_offline_viewer", _SCRIPT)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


@pytest.fixture(scope="module")
def data():
    return _mod().build_viewer_data()


# ---------------------------------------------------------------- Task 1 schema
def test_schema_sections_present(data):
    for k in ["meta", "verdicts", "summary", "capital", "tail", "proxy", "loss", "governance"]:
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


# ---------------------------------------------------------------- Task 2 loss
@pytest.mark.skipif(not os.path.exists(_LOSS_JSON),
                    reason="loss-distribution artifact not yet produced by the model")
def test_loss_section_present(data):
    L = data["loss"]
    assert L, "loss section empty (run scripts/build_phase16_loss_distribution.py)"
    h = L["histogram"]
    # histogram is self-consistent: edges = counts + 1, counts sum to n_outer
    assert len(h["bin_edges"]) == len(h["counts"]) + 1
    assert sum(h["counts"]) == h["n_outer"] == L["n_outer"]
    assert h["min"] <= h["max"]


@pytest.mark.skipif(not os.path.exists(_LOSS_JSON),
                    reason="loss-distribution artifact not yet produced by the model")
def test_loss_confidence_sweep_monotonic(data):
    sweep = data["loss"]["confidence_sweep"]
    assert len(sweep) >= 3
    cls = [r["cl"] for r in sweep]
    vars_ = [r["var"] for r in sweep]
    # VaR is non-decreasing in the confidence level; ES >= VaR; SCR == VaR - mean
    assert cls == sorted(cls)
    assert vars_ == sorted(vars_)
    mean = data["loss"]["mean_liability"]
    for r in sweep:
        assert r["es"] >= r["var"] - 1e-6
        assert abs(r["scr"] - (r["var"] - mean)) < 1.0


@pytest.mark.skipif(not os.path.exists(_LOSS_JSON),
                    reason="loss-distribution artifact not yet produced by the model")
def test_loss_percentiles_and_seeds(data):
    L = data["loss"]
    pcts = L["percentiles"]
    losses = [r["loss"] for r in pcts]
    assert losses == sorted(losses), "percentile losses must be non-decreasing"
    seeds = L["seeds"]
    assert len(seeds) >= 2, "need multiple seeds for the interactive seed selector"
    assert len({s["seed"] for s in seeds}) == len(seeds), "seeds must be distinct"
    for s in seeds:
        assert s["histogram"]["bin_edges"] and s["confidence_sweep"] and s["percentiles"]
        assert abs(s["scr995"] - (s["var995"] - s["mean_liability"])) < 1.0


def test_template_has_task2_charts():
    tpl = open(_TEMPLATE).read()
    for token in ["function histChart", "function ciBar", "function renderLossPanel",
                  'id="lossSeed"', 'id="lossCl"', 'id="lossPct"', 'id="lossChart"']:
        assert token in tpl, "missing Task 2 viewer element: " + token


def test_loss_emitter_is_calculation_side_only():
    # The viewer template must not import or run the model; all numbers are pre-computed.
    tpl = open(_TEMPLATE).read().lower()
    for forbidden in ["math.random", "numpy", "fetch(", "xmlhttprequest", "import("]:
        assert forbidden not in tpl, "viewer must not compute/fetch: " + forbidden
