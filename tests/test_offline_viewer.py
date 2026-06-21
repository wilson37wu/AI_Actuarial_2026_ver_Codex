"""Phase 16 — offline result-viewer bundler + schema + offline-safety tests.

Task 1 covered the base schema, governance, and offline-safety.
Task 2 adds the loss-distribution section (histogram + pre-computed
confidence/percentile/seed sweeps) and the interactive capital/tail dashboards,
plus the model-side loss-distribution emitter.
Task 3 adds the proxy overfit-gap chart and the diversification-benefit
waterfall (standalone -> var-cov -> nested) aggregation view.
Task 4 adds the governance panel.
Task 5 adds responsive polish, print, canvas-based PNG export for every SVG
chart, and an executable offline self-test.
"""
from __future__ import annotations

import json
import os
import re
import importlib.util
import shutil
import subprocess

import pytest

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SCRIPT = os.path.join(_REPO, "scripts", "build_offline_viewer.py")
_TEMPLATE = os.path.join(_REPO, "par_model_v2", "viewer", "viewer_template.html")
_LOSS_JSON = os.path.join(_REPO, "docs", "validation", "PHASE16_LOSS_DISTRIBUTION.json")
_SELF_TEST = os.path.join(_REPO, "scripts", "offline_viewer_self_test.cjs")


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
    tpl = open(_TEMPLATE, encoding="utf-8").read()
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
    tpl = open(_TEMPLATE, encoding="utf-8").read()
    for token in ["function histChart", "function ciBar", "function renderLossPanel",
                  'id="lossSeed"', 'id="lossCl"', 'id="lossPct"', 'id="lossChart"']:
        assert token in tpl, "missing Task 2 viewer element: " + token


# ---------------------------------------------------------------- Task 3 proxy + aggregation
def test_template_has_task3_views():
    tpl = open(_TEMPLATE, encoding="utf-8").read()
    for token in ["function waterfallChart", "function viewAggregation",
                  "Overfit gap", '["agg","Aggregation",viewAggregation]',
                  "Diversification-benefit waterfall"]:
        assert token in tpl, "missing Task 3 viewer element: " + token


def test_aggregation_data_supports_waterfall(data):
    c = data["capital"]
    for k in ("standalone_sum", "correlated_scr", "nested_scr",
              "diversification_benefit_formula", "esg_rate_equity_correlation",
              "component_loss_correlation"):
        assert isinstance(c.get(k), (int, float)), k
    # waterfall ordering: var-cov sits below the standalone sum (a diversification reduction)
    assert c["correlated_scr"] < c["standalone_sum"]


def test_loss_emitter_is_calculation_side_only():
    # The viewer template must not import or run the model; all numbers are pre-computed.
    tpl = open(_TEMPLATE, encoding="utf-8").read().lower()
    for forbidden in ["math.random", "numpy", "fetch(", "xmlhttprequest", "import("]:
        assert forbidden not in tpl, "viewer must not compute/fetch: " + forbidden


# ---------------------------------------------------------------- Task 4 governance panel
def test_governance_deployment_gates(data):
    gates = data["governance"]["deployment_gates"]
    assert len(gates) == 12, "expected 12 deployment gates"
    ids = {g["gate_id"] for g in gates}
    assert {"G-01", "G-10", "G-11", "G-12"} <= ids
    for g in gates:
        for k in ("gate_id", "description", "status", "level", "blocking", "cleared"):
            assert k in g, k
    assert sum(1 for g in gates if g["cleared"]) == 12, "all 12 gates cleared (educational)"


def test_governance_audit_integrity_is_computed(data):
    g = data["governance"]
    # the badge must be a *computed* digest-recomputation result, not a hard-coded flag
    assert g["audit_integrity_ok"] is True
    assert g["audit_verified"] == g["audit_entries"] >= 28
    assert g["audit_failed"] == 0


def test_governance_change_record_timeline_fields(data):
    crs = data["governance"]["change_records"]
    assert crs and all("created_at" in c for c in crs)
    for c in crs:
        assert isinstance(c.get("sign_off_history"), list)
    # at least one record carries a multi-step sign-off history (peer -> owner)
    assert any(len(c["sign_off_history"]) >= 2 for c in crs)


def test_governance_risk_register_enriched(data):
    rr = data["governance"]["risk_register"]
    assert rr
    for r in rr:
        for k in ("risk_id", "title", "overall_rating", "mitigation_status",
                  "category", "owner", "description", "mitigation"):
            assert k in r, k
    mr011 = next(r for r in rr if r["risk_id"] == "MR-011")
    assert mr011["description"] and mr011["mitigation"]


def test_template_has_task4_views():
    tpl = open(_TEMPLATE, encoding="utf-8").read()
    for token in ["Deployment-gate checklist", 'id="rrStatus"', 'id="rrRating"',
                  'class="timeline"', "digests verified", "function viewGov",
                  "Change-record timeline"]:
        assert token in tpl, "missing Task 4 viewer element: " + token


# ---------------------------------------------------------------- Task 5 polish + offline packaging
def test_template_has_task5_packaging_controls():
    tpl = open(_TEMPLATE, encoding="utf-8").read()
    for token in ["function exportSvgToPng", "createElement(\"canvas\")",
                  "function enhanceChartExports", "Export PNG",
                  'id="printView"', "@media(max-width:540px)", "@media print",
                  'id="file"', 'id="drop"']:
        assert token in tpl, "missing Task 5 packaging element: " + token


def test_offline_self_test_script_runs_on_rendered_html(tmp_path, data):
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not available")
    html_path = tmp_path / "viewer.html"
    html_path.write_text(_mod().render_html(data), encoding="utf-8")
    # Make the repo-root node_modules discoverable (jsdom lives there; node_modules
    # is gitignored, so it is present on dev hosts / the mount but absent in a fresh
    # clone or clean CI checkout). Mirrors tests/test_phase36_task4_e3_evidence_pack.py.
    env = dict(os.environ)
    _nm = os.path.join(_REPO, "node_modules")
    if os.path.isdir(_nm):
        env["NODE_PATH"] = _nm + os.pathsep + env.get("NODE_PATH", "")
    result = subprocess.run(
        [node, _SELF_TEST, str(html_path)],
        cwd=_REPO,
        text=True,
        capture_output=True,
        timeout=90,  # bumped from 10s: headless Node render self-test needs ~25s on slow CI/sandbox hosts (P19T1)
        check=False,
        env=env,
    )
    # The self-test requires the optional `jsdom` module. When it is not installed
    # (fresh clone / clean CI without node_modules), SKIP rather than hard-fail:
    # the stdlib mirror (build_offline_home_validate / offline_home_loader_parity)
    # provides rebuild-independent coverage, and this jsdom path still runs wherever
    # node_modules/jsdom is present. Canonical pattern: test_phase36_task4 line ~125.
    _out = (result.stderr or "") + (result.stdout or "")
    if result.returncode != 0 and (
        "Cannot find module 'jsdom'" in _out or "MODULE_NOT_FOUND" in _out
    ):
        pytest.skip("jsdom unavailable: " + _out.strip()[:200])
    assert result.returncode == 0, result.stdout + result.stderr
    checks = json.loads(result.stdout)["checks"]
    assert checks["networkCalls"] == 0
    assert checks["jsErrors"] == 0
    assert checks["exportButtons"] >= checks["svgCount"] >= 6
    assert checks["canvasExportSource"] is True
