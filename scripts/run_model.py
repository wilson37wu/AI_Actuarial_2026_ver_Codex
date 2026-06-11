#!/usr/bin/env python3
"""Phase UIL Task 3 (B3): run orchestrator -- the single user-facing entry point.

    python3 scripts/run_model.py --inputs model_inputs.json

Threads the validated user inputs (the schema-versioned output of
``scripts/load_user_inputs.py``) through the governed Phase 22 Task 4
seven-driver engine, in order:

  standalone driver losses -> 7x7 var-covar -> copula aggregation (AIC
  selection on the realised losses) -> nested benchmark -> bootstrap SCR
  confidence intervals -> tail diagnostics

and writes GUI-consumable result JSONs with the SAME ``aggregation`` shape as
``docs/validation/PHASE22_TASK4_AGGREGATION_REPORT.json`` (the snapshot
``scripts/build_ui_data.py`` already parses):

  <out>/RUN_MODEL_AGGREGATION_REPORT.json   full evidence (aggregation shape)
  <out>/RUN_MODEL_SUMMARY.json              one-screen headline summary

Run Settings honoured (CLI flags override the template values):
``n_sim``, ``seed``, ``bootstrap_replicates``, ``horizon_months``,
``output_label``; plus ``confidence`` from the Assumptions tab.

Backward-compatibility hard gate: with NO ``model_inputs.json`` present the
orchestrator builds exactly the governed pipeline -- synthetic representative
product (issue age 45 / M / SA 100,000 / premium 5,000 / 20y), archived
G-LIQX-calibrated liquidity exposure notional and frozen seven-driver
correlation -- parameter-identical to the governed Phase 22 Task 4 run at the
same config.  Frozen dependence parameters (copula df, couplings) are NEVER
user-settable here.

The engine prices ONE representative model point (the same semantics as every
governed capital run).  With a user portfolio the representative point is the
inforce-weighted mean of the PAR rows; the book totals and a DISCLOSED linear
scaling factor are reported alongside (approximation, not a governed result).
GMMB_EQ rows are split out and disclosed; they do not enter the PAR engine.

MODEL-USE RESTRICTION: parameters are educational placeholders pending
credentialled data and independent review (ASOP 56 s3.5 / TAS M s3.2).
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

PHASE = "Phase UIL: User-Input Loader + Run Orchestrator"
TASK = "Task 3 (B3): scripts/run_model.py orchestrator"
DEFAULT_OUT_DIR = REPO_ROOT / "docs" / "validation"
AGG_REPORT_NAME = "RUN_MODEL_AGGREGATION_REPORT.json"
SUMMARY_NAME = "RUN_MODEL_SUMMARY.json"

#: Governed Phase 21/22 aggregation defaults (kept in lock-step with
#: scripts/build_phase22_task4_aggregation.py so a no-input run is
#: parameter-identical to the governed evidence at the same config).
GOVERNED_DEFAULTS = {
    "n_outer": 160,
    "n_inner": 24,
    "seed": 42,
    "n_sim": 200_000,
    "bootstrap_replicates": 200,
    "horizon_months": 12,
    "output_label": "governed_default_run",
}


@dataclass
class RunPlan:
    """Fully-resolved run configuration with per-field provenance."""

    n_outer: int = GOVERNED_DEFAULTS["n_outer"]
    n_inner: int = GOVERNED_DEFAULTS["n_inner"]
    seed: int = GOVERNED_DEFAULTS["seed"]
    n_sim: int = GOVERNED_DEFAULTS["n_sim"]
    bootstrap_replicates: int = GOVERNED_DEFAULTS["bootstrap_replicates"]
    horizon_months: int = GOVERNED_DEFAULTS["horizon_months"]
    confidence: float = 0.995
    output_label: str = GOVERNED_DEFAULTS["output_label"]
    run_tail: bool = True
    inputs_source: Optional[str] = None
    provenance: Dict[str, str] = field(default_factory=dict)

    def validate(self) -> None:
        if self.n_sim < 1_000:
            raise ValueError("n_sim must be >= 1,000 (got %d)" % self.n_sim)
        if self.bootstrap_replicates < 50:
            raise ValueError("bootstrap_replicates must be >= 50 (got %d)"
                             % self.bootstrap_replicates)
        if self.horizon_months < 1:
            raise ValueError("horizon_months must be >= 1")
        if not (0.5 < self.confidence < 1.0):
            raise ValueError("confidence must be in (0.5, 1.0)")


def tail_sim_grid(n_sim: int) -> Tuple[int, ...]:
    """Ascending convergence grid ending at ``n_sim`` (>= 2 distinct entries)."""
    if n_sim >= 200_000:
        return (10_000, 25_000, 50_000, 100_000, n_sim)
    grid = sorted({max(1_000, n_sim // 8), max(1_000, n_sim // 4),
                   max(1_000, n_sim // 2), n_sim})
    if len(grid) < 2:
        grid = sorted({max(500, n_sim // 2), n_sim})
    return tuple(grid)


def resolve_plan(inputs: Optional[Dict[str, Any]],
                 args: Optional[argparse.Namespace] = None) -> RunPlan:
    """Merge governed defaults <- template Run Settings <- CLI overrides."""
    from par_model_v2.user_inputs import capital_params, run_settings

    plan = RunPlan()
    prov = {k: "governed_default" for k in (
        "n_outer", "n_inner", "seed", "n_sim", "bootstrap_replicates",
        "horizon_months", "confidence", "output_label")}

    rs = run_settings(inputs) or {}
    # n_outer / n_inner are not template fields, but a hand-tuned
    # model_inputs.json may carry them (power users / smoke profiles).
    mapping = {"n_outer": "n_outer", "n_inner": "n_inner",
               "n_sim": "n_sim", "seed": "seed",
               "bootstrap_replicates": "bootstrap_replicates",
               "horizon_months": "horizon_months",
               "output_label": "output_label"}
    for src_key, attr in mapping.items():
        if rs.get(src_key) is not None:
            val = rs[src_key]
            setattr(plan, attr, type(getattr(plan, attr))(val))
            prov[attr] = "run_settings"

    cp = capital_params(inputs)
    plan.confidence = float(cp["confidence"])
    prov["confidence"] = cp["source"]

    if args is not None:
        cli_map = {"n_outer": "n_outer", "n_inner": "n_inner", "seed": "seed",
                   "n_sim": "n_sim",
                   "bootstrap_replicates": "bootstrap_replicates",
                   "horizon_months": "horizon_months",
                   "confidence": "confidence", "label": "output_label"}
        for arg_name, attr in cli_map.items():
            val = getattr(args, arg_name, None)
            if val is not None:
                setattr(plan, attr, type(getattr(plan, attr))(val))
                prov[attr] = "cli"
        if getattr(args, "no_tail", False):
            plan.run_tail = False

    if inputs is not None:
        plan.inputs_source = str(inputs.get("_source_path"))
    plan.provenance = prov
    plan.validate()
    return plan


def resolve_product(inputs: Optional[Dict[str, Any]]) -> Tuple[object, Dict[str, Any]]:
    """Representative capital model point + provenance.

    No user inputs -> the governed synthetic representative product,
    bit-identical parameters to every governed capital run.  With a user
    portfolio -> the inforce-weighted mean of the PAR rows (model-point
    semantics preserved; book totals disclosed for scaling).
    """
    from par_model_v2.projection.monthly_projection import ParEndowmentProduct
    from par_model_v2.projection.portfolio_generator import (
        build_portfolio, split_model_points)
    from par_model_v2.user_inputs import user_model_points

    pts = user_model_points(inputs)
    if not pts:
        product = ParEndowmentProduct(issue_age=45, gender="M",
                                      sum_assured=100000.0,
                                      annual_premium=5000.0, term_years=20)
        return product, {
            "source": "governed_default",
            "representative_product": {
                "issue_age": 45, "gender": "M", "sum_assured": 100000.0,
                "annual_premium": 5000.0, "term_years": 20},
            "portfolio_summary": None, "gmmb_rows_disclosed": 0,
            "book_scaling": None,
        }

    par_pts, gmmb_pts = split_model_points(pts)
    result = build_portfolio(user_inputs=inputs)   # fail-loud row validation
    tbl = result.policies
    w = tbl["inforce_count"].to_numpy(dtype=float)
    if w.sum() <= 0:
        raise ValueError("user portfolio has zero total inforce_count")

    def wmean(col: str) -> float:
        return float((tbl[col].to_numpy(dtype=float) * w).sum() / w.sum())

    from par_model_v2.projection.monthly_projection import VALID_TERMS
    age = int(round(wmean("issue_age")))
    term_w = wmean("term_years")
    # The engine's product mechanics support fixed terms only; snap the
    # weighted-mean term to the nearest supported term (disclosed below).
    term = int(min(VALID_TERMS, key=lambda t: (abs(t - term_w), t)))
    sa = wmean("sum_assured")
    prem = wmean("annual_premium")
    gender = (tbl.assign(_w=w).groupby("gender")["_w"].sum().idxmax())

    from par_model_v2.projection.monthly_projection import ParEndowmentProduct
    product = ParEndowmentProduct(issue_age=age, gender=str(gender),
                                  sum_assured=sa, annual_premium=prem,
                                  term_years=term)
    total_sa = float((tbl["sum_assured"].to_numpy(dtype=float) * w).sum())
    prov = {
        "source": "user_portfolio_inforce_weighted_mean",
        "representative_product": {
            "issue_age": age, "gender": str(gender), "sum_assured": sa,
            "annual_premium": prem, "term_years": term,
            "term_years_weighted_mean": term_w,
            "term_snap_note": ("weighted-mean term %.2f snapped to nearest "
                               "supported product term %d (VALID_TERMS=%s)"
                               % (term_w, term, VALID_TERMS))},
        "portfolio_summary": result.summary,
        "portfolio_digest": result.digest,
        "gmmb_rows_disclosed": len(gmmb_pts),
        "book_scaling": {
            "policy_count_total": float(w.sum()),
            "sum_assured_total": total_sa,
            "representative_sum_assured": sa,
            "linear_scale_factor": (total_sa / sa) if sa > 0 else None,
            "note": ("DISCLOSED APPROXIMATION, not a governed result: the "
                     "engine prices one representative model point; "
                     "multiplying per-point capital by linear_scale_factor "
                     "assumes homogeneous-book linear scaling."),
        },
    }
    return product, prov


def resolve_exposure(inputs: Optional[Dict[str, Any]]) -> Tuple[float, Dict[str, Any]]:
    """Liquidity exposure notional: user balance sheet, else G-LIQX archive."""
    from par_model_v2.calibration.phase22_liquidity_exposure_calibration import (
        derive_exposure_notional, load_exposure_fixture, resolve_exposure_spec)
    from par_model_v2.projection.multi_driver_capital_7d_aggregation import (
        calibrated_liquidity_exposure_notional)

    if inputs is not None and (inputs.get("balance_sheet") or {}):
        spec, _lineage = load_exposure_fixture()
        resolved = resolve_exposure_spec(spec, inputs)
        derived = derive_exposure_notional(resolved)
        return float(derived["exposure_notional"]), {
            "source": resolved.get("exposure_source", "user_inputs"),
            "derivation": derived,
        }
    notional, is_placeholder = calibrated_liquidity_exposure_notional()
    if is_placeholder:
        raise RuntimeError(
            "G-LIQX calibrated exposure notional not found and no user "
            "balance sheet supplied; refusing to run on placeholders "
            "(run scripts/build_phase22_task3_liquidity_exposure.py or "
            "supply model_inputs.json).")
    return float(notional), {
        "source": "archived_g_liqx_calibration",
        "report": "docs/validation/PHASE22_TASK3_LIQUIDITY_EXPOSURE_REPORT.json",
    }


def build_aggregator(product: object, exposure_notional: float):
    """Seven-driver aggregator on the governed frozen correlation (fail loud)."""
    from par_model_v2.projection.multi_driver_capital_7d_aggregation import (
        LiquidityExposureSpec, SevenDriverLiquidityRiskAggregator,
        calibrated_seven_driver_correlation)

    corr7, is_placeholder = calibrated_seven_driver_correlation()
    if is_placeholder:
        raise RuntimeError(
            "calibrated seven-driver correlation not found; refusing to "
            "aggregate on placeholder couplings.")
    return SevenDriverLiquidityRiskAggregator(
        product,
        liquidity_exposure=LiquidityExposureSpec(
            exposure_notional=exposure_notional),
        correlation7=corr7,
    )


def assemble_report(aggregation: Dict[str, Any], plan: RunPlan,
                    product_prov: Dict[str, Any],
                    exposure_prov: Dict[str, Any],
                    currency: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Full evidence JSON -- same structural contract as the Phase 22 Task 4
    report (top-level ``aggregation`` dict), plus user-run provenance."""
    from par_model_v2.projection.multi_driver_capital_7d_aggregation import (
        seven_driver_use_restrictions)

    return {
        "run_timestamp": datetime.now(timezone.utc).isoformat(),
        "phase": PHASE,
        "task": TASK,
        "generator": "scripts/run_model.py",
        "output_label": plan.output_label,
        "currency": currency,
        "run_plan": {**asdict(plan)},
        "inputs_provenance": {
            "model_inputs": plan.inputs_source or "ABSENT (governed default run)",
            "representative_product": product_prov,
            "liquidity_exposure": exposure_prov,
            "frozen_dependence": "calibrated seven-driver correlation "
                                 "(governed, never user-settable)",
        },
        "aggregation": aggregation,
        "use_restrictions": seven_driver_use_restrictions(),
    }


def summarise(report: Dict[str, Any]) -> Dict[str, Any]:
    agg = report["aggregation"]
    tail = agg.get("tail_diagnostics") or {}
    sim_bs = (tail.get("simulated_bootstrap") or {}) if isinstance(tail, dict) else {}
    return {
        "run_timestamp": report["run_timestamp"],
        "output_label": report["output_label"],
        "currency": report.get("currency"),
        "inputs": report["inputs_provenance"]["model_inputs"],
        "headline": {
            "nested_scr": agg.get("nested_scr"),
            "copula_selected": agg.get("copula_selected"),
            "copula_scr": agg.get("copula_scr"),
            "var_covar_scr": agg.get("var_covar_scr"),
            "standalone_scr": agg.get("standalone_scr"),
            "esg_understatement_pct": agg.get("esg_understatement_pct"),
        },
        "bootstrap_ci": {
            "var_point": sim_bs.get("var_point"),
            "var_ci": sim_bs.get("var_ci"),
            "es_ci": sim_bs.get("es_ci"),
            "var_ci_rel_halfwidth": sim_bs.get("var_ci_rel_halfwidth"),
            "n_bootstrap": sim_bs.get("n_bootstrap"),
        },
        "verdict": agg.get("verdict"),
        "duration_seconds": agg.get("duration_seconds"),
        "evidence": AGG_REPORT_NAME,
    }


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=1, default=str), encoding="utf-8")
    json.loads(path.read_text(encoding="utf-8"))   # re-parse guard


def orchestrate(argv: Optional[list] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--inputs", type=Path, default=None,
                    help="model_inputs.json from scripts/load_user_inputs.py "
                         "(default: auto-discover; absent -> governed run)")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT_DIR,
                    help="output folder (default docs/validation)")
    ap.add_argument("--n-outer", dest="n_outer", type=int, default=None,
                    help="outer (real-world) nodes, >= 100 (governed 160)")
    ap.add_argument("--n-inner", dest="n_inner", type=int, default=None,
                    help="inner (risk-neutral) paths per node (governed 24)")
    ap.add_argument("--n-sim", dest="n_sim", type=int, default=None,
                    help="copula simulations (template Run Settings n_sim)")
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--bootstrap-replicates", dest="bootstrap_replicates",
                    type=int, default=None)
    ap.add_argument("--horizon-months", dest="horizon_months", type=int,
                    default=None)
    ap.add_argument("--confidence", type=float, default=None)
    ap.add_argument("--label", type=str, default=None)
    ap.add_argument("--no-tail", dest="no_tail", action="store_true",
                    help="skip tail diagnostics (fast smoke run)")
    args = ap.parse_args(argv)

    from par_model_v2.projection.multi_driver_capital_5d_aggregation import (
        FiveDriverAggregationConfig)
    from par_model_v2.projection.multi_driver_capital_7d_aggregation import (
        SevenDriverTailConfig)
    from par_model_v2.user_inputs import find_model_inputs

    t0 = time.monotonic()
    inputs = find_model_inputs(args.inputs)   # fail loud on broken file
    plan = resolve_plan(inputs, args)

    product, product_prov = resolve_product(inputs)
    term_months = int(product_prov["representative_product"]["term_years"]) * 12
    if plan.horizon_months >= term_months:
        raise ValueError(
            "horizon_months (%d) must be below the representative product "
            "term (%d months)" % (plan.horizon_months, term_months))

    exposure_notional, exposure_prov = resolve_exposure(inputs)
    agg = build_aggregator(product, exposure_notional)

    cfg = FiveDriverAggregationConfig(
        n_outer=plan.n_outer, n_inner=plan.n_inner, seed=plan.seed,
        confidence_level=plan.confidence,
        capital_horizon_months=plan.horizon_months,
        n_sim_copula=plan.n_sim,
    )
    tail_cfg = SevenDriverTailConfig(
        n_sim_grid=tail_sim_grid(plan.n_sim),
        n_bootstrap_sim=plan.bootstrap_replicates,
        n_bootstrap_nested=max(plan.bootstrap_replicates, 2_000),
        seed=plan.seed + 17,
    )

    print("run_model: inputs=%s label=%r" % (
        plan.inputs_source or "ABSENT (governed default)", plan.output_label))
    print("run_model: n_outer=%d n_inner=%d n_sim=%d seed=%d horizon=%dm "
          "confidence=%.4f bootstrap=%d tail=%s" % (
              plan.n_outer, plan.n_inner, plan.n_sim, plan.seed,
              plan.horizon_months, plan.confidence,
              plan.bootstrap_replicates, plan.run_tail))

    report7d = agg.run_7d(
        config=cfg,
        actor="RunModelOrchestrator",
        phase=PHASE,
        run_tail_diagnostics=plan.run_tail,
        tail_config=tail_cfg if plan.run_tail else None,
    )

    currency = (inputs or {}).get("currency")
    report = assemble_report(report7d.to_dict(), plan, product_prov,
                             exposure_prov, currency)
    out_dir = Path(args.out)
    _write_json(out_dir / AGG_REPORT_NAME, report)
    summary = summarise(report)
    summary["wall_clock_seconds"] = round(time.monotonic() - t0, 3)
    _write_json(out_dir / SUMMARY_NAME, summary)

    print("run_model: nested SCR %.1f | %s copula SCR %.1f | var-covar %.1f"
          % (report["aggregation"]["nested_scr"],
             report["aggregation"]["copula_selected"],
             report["aggregation"]["copula_scr"],
             report["aggregation"]["var_covar_scr"]))
    print("run_model: evidence -> %s" % (out_dir / AGG_REPORT_NAME))
    print("run_model: summary  -> %s" % (out_dir / SUMMARY_NAME))
    print("run_model: next: PYTHONPATH=. python3 scripts/build_ui_data.py")
    return 0


if __name__ == "__main__":
    sys.exit(orchestrate())
