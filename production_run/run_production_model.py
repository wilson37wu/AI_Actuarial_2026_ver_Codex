#!/usr/bin/env python3
"""User-facing production run entry point.

Runs the four pillars of the model from one command, using ONLY the governed
library code in ``par_model_v2`` (no developer scripts needed):

  esg          Economic Scenario Generator - Q-measure rate / equity / FX
               paths with martingale and dimension validation.
  assets       Asset cash-flow / fixed-income pricing run.
  liabilities  Liability cash-flow valuation run (HK participating endowment).
  interaction  Stochastic asset-liability interaction: TVOG (cost of the
               embedded guarantee across stochastic scenarios) + dynamic ALM
               projection (assets and liabilities projected together).
  capital      Seven-driver capital aggregation via scripts/run_model.py
               (Phase UIL B3). Under --stage all it runs AUTOMATICALLY when a
               model_inputs.json is present (the user's template inputs are
               threaded through the engine); skipped otherwise.
  all          All of the above, plus a consolidated run summary.

Usage (from the repository root or from production_run/):

  python3 production_run/run_production_model.py --stage all
  python3 production_run/run_production_model.py --stage esg --scenarios 2000 --seed 42
  python3 production_run/run_production_model.py --stage interaction --out my_results

Outputs land in ``production_run/output/`` as machine-readable JSON. To view
results graphically, rebuild the offline GUI afterwards:

  python3 production_run/build_gui.py

MODEL-USE RESTRICTION: parameters are educational placeholders pending
credentialled data and independent review (ASOP 56 s3.5 / TAS M s3.2). The
word "production" refers to the run workflow, not to regulatory sign-off.
"""

from __future__ import annotations

import argparse
import json
import sys
import warnings
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

DEFAULT_OUT = HERE / "output"


def _write(out_dir: Path, name: str, payload: dict) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    p = out_dir / name
    p.write_text(json.dumps(payload, indent=1, default=str), encoding="utf-8")
    json.loads(p.read_text(encoding="utf-8"))   # re-parse: never ship corrupt JSON
    return p


def stage_esg(out_dir: Path, n_scenarios: int, seed: int) -> dict:
    """Economic Scenario Generator run with validation evidence."""
    from par_model_v2.stochastic.esg_process import Measure, ScenarioSet

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        scen = ScenarioSet.generate(n=n_scenarios, T_months=120,
                                    measure=Measure.Q, seed=seed)
    df = scen.data
    months = [12, 60, 120]
    rate_summary = {}
    for m in months:
        r = df[df["month"] == m]["r_short"]
        if len(r):
            rate_summary[f"month_{m}"] = {
                "mean": float(r.mean()),
                "p05": float(r.quantile(0.05)),
                "p50": float(r.quantile(0.50)),
                "p95": float(r.quantile(0.95)),
            }
    result = {
        "stage": "esg",
        "measure": str(scen.measure),
        "n_scenarios": int(scen.n_scenarios),
        "horizon_months": int(scen.T_months),
        "seed": seed,
        "columns": [str(c) for c in df.columns],
        "short_rate_summary": rate_summary,
        "note": ("Q-measure scenario set generated and dimension-validated; "
                 "martingale enforcement is built into ScenarioSet/Measure "
                 "(see par_model_v2/stochastic/esg_process.py)."),
    }
    _write(out_dir, "esg_result.json", result)
    return result


def stage_assets(out_dir: Path) -> dict:
    """Asset cash-flow / fixed-income pricing run."""
    from par_model_v2.examples.guided_examples import example_fixed_income_pricing
    result = {"stage": "assets",
              "result": example_fixed_income_pricing()}
    _write(out_dir, "assets_result.json", result)
    return result


def stage_liabilities(out_dir: Path) -> dict:
    """Liability cash-flow valuation run (HK participating)."""
    from par_model_v2.examples.guided_examples import example_hk_liability_valuation
    result = {"stage": "liabilities",
              "result": example_hk_liability_valuation()}
    _write(out_dir, "liabilities_result.json", result)
    return result


def stage_interaction(out_dir: Path) -> dict:
    """Stochastic asset-liability interaction: TVOG + dynamic ALM."""
    from par_model_v2.examples.guided_examples import (
        example_alm_projection,
        example_tvog_computation,
    )
    result = {
        "stage": "interaction",
        "tvog": example_tvog_computation(),
        "alm": example_alm_projection(),
        "note": ("TVOG quantifies the guarantee cost across stochastic "
                 "scenarios (liability reacting to the economic paths); the "
                 "ALM projection runs assets and liabilities together so "
                 "asset returns, crediting and liability cash flows "
                 "interact path by path."),
    }
    _write(out_dir, "interaction_result.json", result)
    return result


def stage_capital(out_dir: Path) -> dict:
    """Seven-driver capital aggregation via the B3 orchestrator.

    Called automatically under --stage all when a model_inputs.json exists
    (production_run/model_inputs.json, repo root, or $PAR_MODEL_INPUTS); an
    explicit --stage capital runs the governed-default profile even without
    user inputs. Results land in docs/validation/RUN_MODEL_*.json (the shape
    build_ui_data.py consumes) and a pointer is echoed into out_dir.
    """
    import subprocess

    from par_model_v2.user_inputs import find_model_inputs

    inputs = find_model_inputs()
    # NOTE: no --seed pass-through -- the orchestrator resolves the seed from
    # the template Run Settings (or its governed default); this script's
    # --seed only governs the ESG stage.
    cmd = [sys.executable, str(REPO_ROOT / "scripts" / "run_model.py")]
    if inputs is not None:
        cmd += ["--inputs", str(inputs["_source_path"])]
    proc = subprocess.run(cmd, cwd=str(REPO_ROOT))
    if proc.returncode != 0:
        raise RuntimeError("scripts/run_model.py exited %d" % proc.returncode)
    summary_path = REPO_ROOT / "docs" / "validation" / "RUN_MODEL_SUMMARY.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    result = {"stage": "capital",
              "orchestrator": "scripts/run_model.py",
              "model_inputs": (inputs or {}).get("_source_path",
                                                 "ABSENT (governed default)"),
              "summary": summary}
    _write(out_dir, "capital_result.json", result)
    return result


STAGES = {
    "esg": "Economic Scenario Generator",
    "assets": "Asset cash-flow / pricing",
    "liabilities": "Liability cash-flow valuation",
    "interaction": "Stochastic asset-liability interaction (TVOG + ALM)",
    "capital": "Seven-driver capital aggregation (scripts/run_model.py)",
}


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Production run entry point (see module docstring).")
    ap.add_argument("--stage", default="all",
                    choices=list(STAGES) + ["all"])
    ap.add_argument("--scenarios", type=int, default=1_000,
                    help="ESG scenario count (default 1,000; ASOP 56 "
                         "minimum 500; production typically 5,000+)")
    ap.add_argument("--seed", type=int, default=42,
                    help="Random seed (default 42; same seed => same run)")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT,
                    help="Output folder (default production_run/output)")
    args = ap.parse_args()

    out_dir = Path(args.out)
    run = {"run_timestamp": datetime.now(timezone.utc).isoformat(),
           "requested_stage": args.stage,
           "scenarios": args.scenarios, "seed": args.seed,
           "stages_completed": [], "stages_failed": {}}

    todo = list(STAGES) if args.stage == "all" else [args.stage]
    if args.stage == "all":
        from par_model_v2.user_inputs import find_model_inputs
        try:
            has_inputs = find_model_inputs() is not None
        except Exception:
            has_inputs = True   # present-but-broken: let the stage fail loud
        if not has_inputs:
            todo.remove("capital")
            print("\n(capital stage skipped: no model_inputs.json found; "
                  "run scripts/load_user_inputs.py first or use "
                  "--stage capital for the governed-default profile)")
    for st in todo:
        print("\n=== {} : {} ===".format(st, STAGES[st]))
        try:
            if st == "esg":
                stage_esg(out_dir, args.scenarios, args.seed)
            elif st == "assets":
                stage_assets(out_dir)
            elif st == "liabilities":
                stage_liabilities(out_dir)
            elif st == "interaction":
                stage_interaction(out_dir)
            elif st == "capital":
                stage_capital(out_dir)
            run["stages_completed"].append(st)
            print("[OK] {} -> {}/{}_result.json".format(st, out_dir, st))
        except Exception as exc:                     # noqa: BLE001
            run["stages_failed"][st] = "{}: {}".format(type(exc).__name__, exc)
            print("[ERROR] {} failed: {}".format(st, run["stages_failed"][st]))

    _write(out_dir, "run_summary.json", run)
    print("\nRun summary -> {}".format(out_dir / "run_summary.json"))
    print("To refresh the offline GUI: python3 production_run/build_gui.py")
    return 0 if not run["stages_failed"] else 1


if __name__ == "__main__":
    sys.exit(main())
