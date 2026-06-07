"""Phase 22 Task 5 tests — offline-UI propagation of the calibrated 7D view.

Verifies (read-only over built artifacts):
- ui_data.json contract v1.4.0 surfaces the Phase 22 Task 1-4 results
  (remediated six-driver OOS PASS, seven-driver OOS PASS, G-LIQX calibrated
  exposure/coupling panel, calibrated aggregation + tail read-outs);
- ui_app.html embeds the same snapshot with zero external references;
- the Task 5 evidence report + governance ChangeRecord are persisted and the
  audit chain verifies.

Run:  PYTHONPATH=/var/tmp/pylibs:. python3 -m pytest tests/test_phase22_task5_ui_propagation.py -q
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
UI_DATA = REPO / "ui_data.json"
UI_APP = REPO / "ui_app.html"
REPORT = REPO / "docs/validation/PHASE22_TASK5_UI_PROPAGATION_REPORT.json"
GOV = REPO / ".claude-dev/GOVERNANCE_STORE.json"


@pytest.fixture(scope="module")
def ui():
    return json.loads(UI_DATA.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def report():
    return json.loads(REPORT.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def gov():
    return json.loads(GOV.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def html():
    return UI_APP.read_text(encoding="utf-8")


# ---- contract ---------------------------------------------------------------

def test_contract_version_bumped_additively(ui):
    assert ui["contract_version"] == "1.4.0"


def test_contract_sections_unchanged(ui):
    for key in ("meta", "summary", "inventory", "capital", "tail", "proxy",
                "loss", "calibrations", "governance", "verdicts"):
        assert key in ui, key


# ---- (a) Task 1: remediated six-driver OOS PASS replaces PARTIAL ------------

def test_six_driver_oos_remediated_pass_listed(ui):
    v = [x for x in ui["verdicts"]
         if "REMEDIATED, Phase 22 Task 1" in str(x.get("name", ""))]
    assert len(v) == 1
    assert v[0]["verdict"] == "PASS"
    assert "0.9985" in v[0]["evidence"]
    assert "PHASE22_TASK1" in v[0]["source"]


def test_no_stale_six_driver_partial_verdict(ui):
    assert not any("PARTIAL" in str(x.get("verdict", ""))
                   and "Six-driver" in str(x.get("name", ""))
                   for x in ui["verdicts"])


# ---- (b) Task 2: seven-driver OOS PASS --------------------------------------

def test_seven_driver_oos_pass_listed(ui):
    v = [x for x in ui["verdicts"]
         if "Seven-driver OOS proxy validation" in str(x.get("name", ""))]
    assert len(v) == 1
    assert v[0]["verdict"].startswith("PASS")
    assert "PHASE22_TASK2" in v[0]["source"]


# ---- (c) Task 3: G-LIQX calibrated exposure/coupling panel -------------------

def test_gliqx_calibration_panel_present_and_calibrated(ui):
    recs = [r for r in ui["calibrations"]
            if "G-LIQX" in str(r.get("gate_id", ""))]
    assert len(recs) == 1
    r = recs[0]
    assert r["gate_status"] == "PASS"
    assert r["is_placeholder"] is False
    assert abs(r["params"]["exposure_notional"] - 22000.0) < 1.0
    assert r["params"]["correlation7_psd"] is True


def test_gliqx_panel_has_coupling_bars_and_criteria(ui):
    r = [x for x in ui["calibrations"] if "G-LIQX" in str(x.get("gate_id", ""))][0]
    diag = r.get("diagnostics") or {}
    crit = diag.get("criteria") or []
    assert sum(1 for c in crit if c.get("ok")) == 6
    bars = (diag.get("fit_bars") or {}).get("items") or []
    assert len(bars) == 6  # six estimated couplings


def test_gliqx_verdict_listed(ui):
    assert any("G-LIQX" in str(x.get("name", "")) for x in ui["verdicts"])


# ---- (d) Task 4: calibrated aggregation + tail read-outs ---------------------

def test_capital_prefers_phase22_calibrated_aggregation(ui):
    cap = ui["capital"]
    assert "PHASE22_TASK4" in cap["aggregation_source"]
    assert cap["liquidity_inputs_calibrated"] is True
    assert abs(cap["liquidity_exposure_notional"] - 22000.0) < 1.0
    assert abs(cap["liquidity_scr"] - 45.0533) < 0.1
    assert abs(cap["var_covar_scr"] - 28990.9) < 1.0
    assert abs(cap["nested_scr"] - 48707.4) < 1.0
    assert abs(cap["copula_scr"] - 41604.3) < 1.0
    assert cap["n_drivers"] == 7


def test_calibrated_vs_placeholder_deltas_embedded(ui):
    comp = ui["capital"].get("calibrated_vs_placeholder")
    assert isinstance(comp, dict)
    assert abs(comp["standalone_scr_liquidity"]["placeholder"] - 63.32) < 0.1
    assert abs(comp["standalone_scr_liquidity"]["calibrated"] - 45.05) < 0.1


def test_tail_prefers_phase22_rerun_and_converged(ui):
    tail = ui["tail"]
    assert "PHASE22_TASK4" in tail["source"]
    assert tail["converged"] is True
    assert "G-LIQX-CALIBRATED" in tail["verdict"] or "seven-driver" in tail["verdict"]


def test_headline_keyed_verdicts_calibrated(ui):
    keyed = {x.get("key"): x for x in ui["verdicts"] if x.get("key")}
    assert "G-LIQX-CALIBRATED" in keyed["aggregation"]["verdict"]
    assert "G-LIQX-CALIBRATED" in keyed["tail"]["verdict"]
    assert "PHASE22_TASK4" in keyed["aggregation"]["source"]


# ---- offline html ------------------------------------------------------------

def test_html_embeds_same_contract_offline(html):
    assert "/*__UI_DATA__*/" in html
    assert '"contract_version": "1.4.0"' in html.replace('": "', '": "') or \
        '"contract_version":"1.4.0"' in html.replace(" ", "")
    assert "G-LIQX" in html


def test_html_no_external_references(html):
    assert not re.search(r'src\s*=\s*["\']https?://', html)
    assert not re.search(r'href\s*=\s*["\']https?://', html)
    assert "fetch(" not in html.replace("// fetch(", "")


# ---- evidence report + governance --------------------------------------------

def test_task5_report_pass_and_phase22_complete(report):
    assert report["verdict"] == "PASS"
    assert report["phase22_status"] == "COMPLETE (Tasks 1-5)"
    ck = report["ui_contract_checks"]
    assert ck["all_passed"] is True
    st = report["self_test"]
    assert st["ok"] is True and st["network_calls"] == 0 and st["js_errors"] == 0


def test_change_record_owner_review_and_audit_integrity(report, gov):
    g = report["governance"]
    assert g["change_record_status"] == "OWNER_REVIEW"
    assert g["audit_integrity_verify_all"] is True
    titles = [r.get("title") for r in gov.get("change_records", [])]
    assert ("Phase 22 Task 5 - offline-UI propagation of the calibrated "
            "seven-driver view") in titles
