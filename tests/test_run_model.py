"""Phase UIL Task 3 (B3): tests for the scripts/run_model.py orchestrator.

Fast tests only -- no nested runs.  The heavy integration path is exercised
by the committed worked-example evidence (docs/validation/RUN_MODEL_*.json).

Hard regression gate: with NO user inputs the resolved plan, representative
product and liquidity exposure notional are parameter-identical to the
archived governed Phase 22 Task 4 evidence.
"""

import argparse
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import run_model as rm  # noqa: E402

P22T4 = REPO_ROOT / "docs" / "validation" / "PHASE22_TASK4_AGGREGATION_REPORT.json"


def _args(**kw):
    ns = argparse.Namespace(n_outer=None, n_inner=None, seed=None, n_sim=None,
                            bootstrap_replicates=None, horizon_months=None,
                            confidence=None, label=None, no_tail=False)
    for k, v in kw.items():
        setattr(ns, k, v)
    return ns


def _user_inputs(**over):
    base = {
        "schema_version": "1.0.0",
        "_source_path": "<test>",
        "currency": {"code": "USD", "symbol": "$", "scale": "units"},
        "balance_sheet": {"backing_asset_mv": 250000.0,
                          "illiquid_share": 0.5,
                          "forced_sale_fraction": 0.4},
        "portfolio": [
            {"product_type": "HKCD_PAR_2026", "issue_age": 40, "gender": "M",
             "term_years": 20, "sum_assured": 100000.0,
             "annual_premium": 5000.0, "policy_count": 100,
             "vested_bonus": 0.0, "source_row": 2},
            {"product_type": "HKRB_PAR_2026", "issue_age": 50, "gender": "F",
             "term_years": 20, "sum_assured": 200000.0,
             "annual_premium": 8000.0, "policy_count": 300,
             "vested_bonus": 1000.0, "source_row": 3},
        ],
        "assumptions": {},
        "run_settings": {"n_sim": 20000, "seed": 7, "bootstrap_replicates": 100,
                         "horizon_months": 12, "output_label": "T"},
    }
    base.update(over)
    return base


# --------------------------------------------------------------------------
# RunPlan resolution
# --------------------------------------------------------------------------

class TestResolvePlan:
    def test_no_inputs_is_governed_default(self):
        plan = rm.resolve_plan(None, None)
        assert plan.n_outer == 160 and plan.n_inner == 24
        assert plan.seed == 42 and plan.n_sim == 200_000
        assert plan.bootstrap_replicates == 200
        assert plan.horizon_months == 12 and plan.confidence == 0.995
        assert plan.inputs_source is None
        assert all(v in ("governed_default", "governed_defaults")
                   for v in plan.provenance.values())

    def test_governed_default_matches_archived_p22t4_config(self):
        plan = rm.resolve_plan(None, None)
        cfg = json.loads(P22T4.read_text())["aggregation"]["config"]
        assert plan.n_outer == cfg["n_outer"]
        assert plan.n_inner == cfg["n_inner"]
        assert plan.seed == cfg["seed"]
        assert plan.n_sim == cfg["n_sim_copula"]
        assert plan.horizon_months == cfg["capital_horizon_months"]
        assert plan.confidence == pytest.approx(cfg["confidence_level"], abs=0)

    def test_run_settings_honoured(self):
        plan = rm.resolve_plan(_user_inputs(), None)
        assert plan.n_sim == 20000 and plan.seed == 7
        assert plan.bootstrap_replicates == 100
        assert plan.output_label == "T"
        assert plan.provenance["n_sim"] == "run_settings"

    def test_cli_overrides_run_settings(self):
        plan = rm.resolve_plan(_user_inputs(), _args(seed=99, label="X",
                                                     n_sim=50000))
        assert plan.seed == 99 and plan.output_label == "X"
        assert plan.n_sim == 50000
        assert plan.provenance["seed"] == "cli"

    def test_user_confidence_from_assumptions(self):
        ui = _user_inputs(assumptions={"confidence": 0.99})
        plan = rm.resolve_plan(ui, None)
        assert plan.confidence == pytest.approx(0.99)
        assert plan.provenance["confidence"] == "user_inputs"

    def test_invalid_plan_fails_loud(self):
        with pytest.raises(ValueError):
            rm.resolve_plan(None, _args(n_sim=10))           # n_sim too small
        with pytest.raises(ValueError):
            rm.resolve_plan(None, _args(bootstrap_replicates=5))
        with pytest.raises(ValueError):
            rm.resolve_plan(None, _args(confidence=1.5))


# --------------------------------------------------------------------------
# Tail grid
# --------------------------------------------------------------------------

class TestTailGrid:
    def test_canonical_200k_grid_preserved(self):
        assert rm.tail_sim_grid(200_000) == (10_000, 25_000, 50_000,
                                             100_000, 200_000)

    def test_small_grid_ascending_ends_at_n_sim(self):
        for n in (2_000, 5_000, 20_000, 100_000):
            g = rm.tail_sim_grid(n)
            assert list(g) == sorted(g) and len(g) >= 2 and g[-1] == n

    def test_grid_valid_for_tail_config(self):
        from par_model_v2.projection.multi_driver_capital_7d_aggregation import (
            SevenDriverTailConfig)
        cfg = SevenDriverTailConfig(n_sim_grid=rm.tail_sim_grid(20_000),
                                    n_bootstrap_sim=50)
        assert cfg.n_sim_grid[-1] == 20_000


# --------------------------------------------------------------------------
# Representative product
# --------------------------------------------------------------------------

class TestResolveProduct:
    def test_no_inputs_governed_product_bit_identical(self):
        product, prov = rm.resolve_product(None)
        assert prov["source"] == "governed_default"
        rp = prov["representative_product"]
        assert (rp["issue_age"], rp["gender"], rp["sum_assured"],
                rp["annual_premium"], rp["term_years"]) == (45, "M", 100000.0,
                                                            5000.0, 20)
        assert prov["book_scaling"] is None

    def test_user_portfolio_weighted_mean(self):
        product, prov = rm.resolve_product(_user_inputs())
        rp = prov["representative_product"]
        # weights 100 vs 300 -> age (40*100+50*300)/400 = 47.5 -> 48 (round)
        assert rp["issue_age"] == 48
        assert rp["sum_assured"] == pytest.approx(175000.0)   # (100k*100+200k*300)/400
        assert rp["annual_premium"] == pytest.approx(7250.0)
        assert rp["gender"] == "F"                            # majority by inforce
        assert rp["term_years"] == 20
        bs = prov["book_scaling"]
        assert bs["policy_count_total"] == pytest.approx(400.0)
        assert bs["sum_assured_total"] == pytest.approx(100000.0 * 100 + 200000.0 * 300)
        assert bs["linear_scale_factor"] == pytest.approx(
            bs["sum_assured_total"] / rp["sum_assured"])

    def test_term_snapped_to_supported_terms(self):
        ui = _user_inputs()
        for p in ui["portfolio"]:
            p["term_years"] = 25
        _, prov = rm.resolve_product(ui)
        assert prov["representative_product"]["term_years"] == 20
        assert "snapped" in prov["representative_product"]["term_snap_note"]

    def test_gmmb_rows_split_and_disclosed(self):
        ui = _user_inputs()
        ui["portfolio"].append({"product_type": "GMMB_EQ_2026",
                                "issue_age": 45, "gender": "M",
                                "term_years": 10, "sum_assured": 50000.0,
                                "annual_premium": 0.0, "policy_count": 10,
                                "vested_bonus": 0.0, "source_row": 4})
        _, prov = rm.resolve_product(ui)
        assert prov["gmmb_rows_disclosed"] == 1

    def test_bad_row_fails_loud(self):
        ui = _user_inputs()
        ui["portfolio"][0]["policy_count"] = -1
        with pytest.raises(ValueError):
            rm.resolve_product(ui)


# --------------------------------------------------------------------------
# Liquidity exposure
# --------------------------------------------------------------------------

class TestResolveExposure:
    def test_no_inputs_matches_archived_calibration(self):
        notional, prov = rm.resolve_exposure(None)
        assert prov["source"] == "archived_g_liqx_calibration"
        cal = json.loads(P22T4.read_text())["calibration_inputs"]
        assert notional == pytest.approx(cal["exposure_notional"], rel=0,
                                         abs=1e-9)

    def test_user_balance_sheet_derivation(self):
        notional, prov = rm.resolve_exposure(_user_inputs())
        assert prov["source"] == "user_inputs"
        assert notional == pytest.approx(250000.0 * 0.5 * 0.4)

    def test_incomplete_balance_sheet_fails_loud(self):
        from par_model_v2.user_inputs import UserInputsError
        ui = _user_inputs(balance_sheet={"backing_asset_mv": 1000.0})
        with pytest.raises(UserInputsError):
            rm.resolve_exposure(ui)


# --------------------------------------------------------------------------
# Report assembly (GUI structural contract)
# --------------------------------------------------------------------------

class TestAssembleReport:
    def _report(self):
        plan = rm.resolve_plan(None, None)
        stub_agg = {"nested_scr": 1.0, "copula_selected": "t",
                    "copula_scr": 2.0, "var_covar_scr": 3.0,
                    "standalone_scr": {"rate": 1.0}, "verdict": "PASS",
                    "duration_seconds": 0.1,
                    "tail_diagnostics": {"simulated_bootstrap": {
                        "var_point": 9.0, "var_ci": [8.0, 10.0],
                        "es_ci": [9.0, 11.0], "n_bootstrap": 200,
                        "var_ci_rel_halfwidth": 0.1}}}
        _, pprov = rm.resolve_product(None)
        return rm.assemble_report(stub_agg, plan, pprov,
                                  {"source": "archived_g_liqx_calibration"},
                                  {"code": "USD", "symbol": "$"})

    def test_same_structural_contract_as_p22t4(self):
        rep = self._report()
        # build_ui_data.py's aggregation-source predicate:
        assert isinstance(rep.get("aggregation"), dict)
        for key in ("run_timestamp", "phase", "task", "aggregation",
                    "use_restrictions"):
            assert key in rep
        agg_keys = set(json.loads(P22T4.read_text())["aggregation"])
        # the live engine emits the full shape; the stub carries the headline
        # subset the GUI reads:
        assert {"nested_scr", "copula_selected", "copula_scr",
                "var_covar_scr", "standalone_scr"} <= agg_keys

    def test_summary_headline_and_ci(self):
        s = rm.summarise(self._report())
        assert s["headline"]["nested_scr"] == 1.0
        assert s["bootstrap_ci"]["var_ci"] == [8.0, 10.0]
        assert s["verdict"] == "PASS"
        assert s["currency"]["code"] == "USD"

    def test_json_serialisable_and_reparses(self, tmp_path):
        rep = self._report()
        p = tmp_path / "r.json"
        rm._write_json(p, rep)
        assert json.loads(p.read_text())["phase"] == rm.PHASE


# --------------------------------------------------------------------------
# CLI / wiring
# --------------------------------------------------------------------------

class TestCLI:
    def test_explicit_missing_inputs_fails_loud(self):
        from par_model_v2.user_inputs import UserInputsError
        with pytest.raises(UserInputsError):
            rm.orchestrate(["--inputs", "/nonexistent/model_inputs.json"])

    def test_horizon_must_be_below_term(self):
        with pytest.raises(ValueError, match="horizon_months"):
            rm.orchestrate(["--horizon-months", "240", "--no-tail"])

    def test_production_run_capital_stage_wired(self):
        src = (REPO_ROOT / "production_run" /
               "run_production_model.py").read_text()
        assert "stage_capital" in src and '"capital"' in src
        assert "run_model.py" in src
