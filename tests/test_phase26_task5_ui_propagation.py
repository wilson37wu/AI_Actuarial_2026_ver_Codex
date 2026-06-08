"""Phase 26 Task 5 tests - offline-UI propagation of the full path-wise
copula re-aggregation view; PHASE 26 COMPLETE.

Verifies (read-only over built artifacts):
- ui_data.json contract v1.8.0 (ADDITIVE) surfaces the Phase 26 Task 2-4
  results (per-driver composition transform on the frozen copula: component
  t SCR 39,975.7 vs re-anchored 39,794.3 = +0.46%; frozen-copula margin
  bootstrap on the component basis: mean 39,595.1, 95% CI [36,676.2,
  42,943.1], SE 4.07%, nested 46,638.9 OUTSIDE the CI -> 14.29% gap = 91.9%
  copula-form / 8.1% relief-surface; paired delta matrix: composition
  correction +211.5 [+46.1, +381.8] significant but < 1% MR trigger);
- ui_app.html embeds the same snapshot with zero external references and a
  Full Re-Agg (P26) panel;
- the Task 5 evidence report + governance ChangeRecord are persisted and the
  audit chain verifies.

Run:  PYTHONPATH=/var/tmp/pylibs:. python3 -m pytest tests/test_phase26_task5_ui_propagation.py -q
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
UI_DATA = REPO / "ui_data.json"
UI_APP = REPO / "ui_app.html"
REPORT = REPO / "docs/validation/PHASE26_TASK5_UI_PROPAGATION_REPORT.json"
CARD = REPO / "docs/UI_PROPAGATION_CARD_P26.md"
T2_REPORT = (REPO / "docs/validation/"
             "PHASE26_TASK2_COMPOSITION_TRANSFORM_REPORT.json")
T3_REPORT = (REPO / "docs/validation/"
             "PHASE26_TASK3_MARGIN_BOOTSTRAP_REPORT.json")
T4_REPORT = (REPO / "docs/validation/PHASE26_TASK4_DELTA_MATRIX_REPORT.json")
GOV = REPO / ".claude-dev/GOVERNANCE_STORE.json"


@pytest.fixture(scope="module")
def ui():
    return json.loads(UI_DATA.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def p26(ui):
    return ui.get("phase26", {})


@pytest.fixture(scope="module")
def report():
    return json.loads(REPORT.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def html():
    return UI_APP.read_text(encoding="utf-8")


class TestContract:
    def test_contract_version_at_least_1_8_0(self, ui):
        version = tuple(int(p) for p in ui["contract_version"].split("."))
        assert version >= (1, 8, 0)

    def test_phase26_section_present(self, p26):
        assert isinstance(p26, dict) and p26
        for k in ("composition", "bootstrap", "delta_matrix", "narrative"):
            assert k in p26

    def test_additive_predecessor_sections_retained(self, ui):
        # Additive bump must not drop any prior-phase section.
        for k in ("phase24", "phase25", "capital", "governance", "verdicts"):
            assert k in ui


class TestCompositionTransform:
    def test_component_vs_level_scr(self, p26):
        ct = p26["composition"]["t_readout"]
        assert ct["scr_component"] == pytest.approx(39975.7, abs=1.0)
        assert ct["scr_level"] == pytest.approx(39794.3, abs=1.0)
        # The full component basis is >= the re-anchored read-out (sign gate).
        assert ct["scr_component"] >= ct["scr_level"]

    def test_composition_correction_immaterial(self, p26):
        co = p26["composition"]
        assert co["component_vs_reanchored_rel_t"] == pytest.approx(
            0.004557, abs=5e-4)
        assert co["mr_refresh_trigger_1pct"] is False

    def test_copula_frozen(self, p26):
        co = p26["composition"]
        assert co["df_rematched"] == pytest.approx(2.9451, abs=1e-3)
        assert abs(float(co["rho_max_abs_diff"])) < 1e-12

    def test_composition_gates_pass(self, p26):
        gates = p26["composition"]["gates"]
        assert isinstance(gates, dict) and len(gates) == 6
        assert all(v is True for v in gates.values())

    def test_ui_matches_task2_report(self, p26):
        rep = json.loads(T2_REPORT.read_text(encoding="utf-8"))["result"]
        assert p26["composition"]["t_readout"]["scr_component"] == \
            pytest.approx(rep["t_readout"]["scr_component"], abs=1e-6)


class TestBootstrap:
    def test_component_ci(self, p26):
        ci = p26["bootstrap"]["component_t_scr_ci"]
        assert ci["mean"] == pytest.approx(39595.1, abs=1.0)
        assert ci["ci_lo"] == pytest.approx(36676.2, abs=1.0)
        assert ci["ci_hi"] == pytest.approx(42943.1, abs=1.0)

    def test_se_gate(self, p26):
        bo = p26["bootstrap"]
        assert bo["se_frac_of_mean"] == pytest.approx(0.040661, abs=5e-4)
        assert float(bo["se_frac_of_mean"]) <= 0.05
        assert bo["se_gate_pass"] is True

    def test_nested_outside_ci(self, p26):
        assert p26["bootstrap"]["headline_nested_inside_95ci"] is False

    def test_gap_decomposition_copula_form_dominant(self, p26):
        gd = p26["bootstrap"]["residual_gap_decomposition"]
        assert gd["copula_form_share_of_gap"] == pytest.approx(
            0.918501, abs=5e-4)
        assert gd["relief_surface_share_of_gap"] == pytest.approx(
            0.081499, abs=5e-4)
        assert gd["copula_form_dominant"] is True
        assert gd["residual_exceeds_t_g_sensitivity"] is True

    def test_ui_matches_task3_report(self, p26):
        rep = json.loads(T3_REPORT.read_text(encoding="utf-8"))["result"]
        assert p26["bootstrap"]["component_t_scr_ci"]["mean"] == \
            pytest.approx(rep["component_t_scr_ci"]["mean"], abs=1e-6)


class TestDeltaMatrix:
    def test_point_matrix(self, p26):
        pm = p26["delta_matrix"]["point_matrix"]
        assert pm["component"]["t"] == pytest.approx(39975.7, abs=1.0)
        assert pm["level"]["t"] == pytest.approx(39794.3, abs=1.0)
        assert pm["without"]["t"] == pytest.approx(47269.1, abs=1.0)

    def test_paired_composition_correction_significant(self, p26):
        cc = p26["delta_matrix"]["paired_deltas"]["composition_correction_t"]
        assert cc["mean"] == pytest.approx(211.5, abs=2.0)
        assert cc["excludes_zero"] is True

    def test_mr_trigger_not_fired(self, p26):
        trg = p26["delta_matrix"]["mr_trigger"]
        assert trg["trigger_fired"] is False
        assert trg["max_abs_rel"] == pytest.approx(0.005510, abs=5e-4)
        assert trg["statistically_significant_t"] is True

    def test_rank_invariance_reverified(self, p26):
        ri = p26["delta_matrix"]["rank_invariance"]
        assert ri["rank_invariant"] is True
        assert ri["df_within_tol"] is True
        assert ri["rho_frozen"] is True

    def test_ui_matches_task4_report(self, p26):
        rep = json.loads(T4_REPORT.read_text(encoding="utf-8"))["result"]
        ui_cc = p26["delta_matrix"]["paired_deltas"][
            "composition_correction_t"]["mean"]
        assert ui_cc == pytest.approx(
            rep["paired_deltas"]["composition_correction_t"]["mean"], abs=1e-6)


class TestCapitalReadouts:
    def test_additive_capital_readouts(self, ui):
        cap = ui["capital"]
        assert cap["t_copula_scr_pathwise_component"] == pytest.approx(
            39975.7, abs=1.0)
        assert cap["t_copula_scr_pathwise_component_bootstrap_mean"] == \
            pytest.approx(39595.1, abs=1.0)


class TestVerdicts:
    def test_three_phase26_verdicts(self, ui):
        names = [str(v.get("name") or v.get("key", ""))
                 for v in ui["verdicts"]]
        for needle in ("per-driver composition transform",
                       "frozen-copula margin bootstrap + gap decomposition",
                       "paired full-vs-reanchored delta matrix"):
            assert any(needle in n for n in names), needle
        for v in ui["verdicts"]:
            if "Phase 26" in str(v.get("name", "")):
                assert "PASS" in str(v.get("verdict", ""))


class TestOfflineHtml:
    def test_zero_external_references(self, html):
        # No remote scripts/styles/links: the UI is fully offline.
        assert not re.search(r'src\s*=\s*["\']https?://', html)
        assert not re.search(r'href\s*=\s*["\']https?://', html)
        assert "cdn" not in html.lower().split("/*__ui_data__*/")[0]

    def test_embedded_snapshot_matches_contract(self, html):
        marker = "/*__UI_DATA__*/"
        start = html.index(marker) + len(marker)
        end = html.index("</script>", start)
        data = json.loads(html[start:end])
        assert tuple(int(p) for p in
                     data["contract_version"].split(".")) >= (1, 8, 0)
        assert data["phase26"]["composition"]["t_readout"][
            "scr_component"] == pytest.approx(39975.65, abs=1.0)

    def test_full_reagg_panel_present(self, html):
        assert 'id="phase26"' in html
        assert "Full Re-Agg (P26)" in html


class TestReportAndGovernance:
    def test_report_pass_and_complete(self, report):
        assert report["verdict"] == "PASS"
        assert report["phase26_status"] == "COMPLETE (Tasks 1-5)"
        assert report["ui_contract_checks"]["all_passed"] is True

    def test_self_test_clean(self, report):
        st = report["self_test"]
        assert st["ok"] is True
        assert st["network_calls"] == 0
        assert st["js_errors"] == 0

    def test_change_record_owner_review(self, report):
        gov = report["governance"]
        assert gov["change_record_status"] == "OWNER_REVIEW"
        assert gov["audit_integrity_verify_all"] is True

    def test_change_record_in_store(self, report):
        store = json.loads(GOV.read_text(encoding="utf-8"))
        rid = report["governance"]["change_record_id"]
        assert any(r.get("record_id") == rid
                   for r in store["change_records"])

    def test_card_persisted(self):
        assert CARD.exists()
        assert "PHASE 26 COMPLETE" in CARD.read_text(encoding="utf-8")
