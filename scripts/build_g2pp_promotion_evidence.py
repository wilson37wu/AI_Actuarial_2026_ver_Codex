#!/usr/bin/env python3
"""Builder - G2++ two-factor rate-model production-promotion evidence.

Roadmap 4.1 #7 (MR-004). Assembles the evidence that the validated G2++
two-factor rate process has been promoted to a *selectable* production rate
model in the governed ESG path (``ScenarioSet.generate(rate_model="g2pp")``),
with HW1F retained as the byte-identical default fallback:

  * selectability          - the rate-model registry + fail-loud resolver;
  * HW1F fallback identity  - pinned digests of the governed default Q/P paths;
  * swaption fit            - G2++ calibrated to the ATM swaption surface
                              (RMSE in vol bps + the G-SWPN gate);
  * Q-measure martingale    - discounted-ZCB reconciliation on the promoted set;
  * curve-twist evidence    - short-vs-long decorrelation vs the one-factor
                              HW1F benchmark (the two-factor raison d'etre).

Writes docs/validation/G2PP_PRODUCTION_PROMOTION.json (schema
g2pp-production-promotion-1.0, stable inputs digest, UNSIGNED banner). Purely
additive diagnostic - no governed headline figure is touched; the G2++ path is
opt-in and re-baselining the headline onto it remains owner-gated.

Usage:  python3 scripts/build_g2pp_promotion_evidence.py [--n 2000] [--months 120]
"""
from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import sys
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import par_model_v2.stochastic.esg_process as esg  # noqa: E402

SCHEMA = "g2pp-production-promotion-1.0"

# Pinned digests of the governed default (HW1F) path (see tests/test_g2pp_promotion.py).
HW1F_Q_DIGEST = "1aa0b3f4cc460a2f85477d3548a998346a8e9fdaa18056dcadefd564677b8d1a"
HW1F_P_DIGEST = "bf7ede63cdbdb5e99be1cc8882caeaf11f98a75203f557d33adb5c0ed78ce37e"

_GOV_COLS = ["scenario_id", "month", "r_short", "zcb_1y", "zcb_10y",
             "equity_index", "equity_return_1m", "measure"]


def _digest(df):
    cols = [c for c in _GOV_COLS if c in df.columns]
    return hashlib.sha256(df[cols].round(12).to_csv(index=False).encode()).hexdigest()


def _cny_curve():
    return esg.RiskFreeCurve(
        tenors_years=(0.25, 1, 2, 3, 5, 7, 10, 20, 30),
        zero_rates=(0.018, 0.020, 0.022, 0.024, 0.026, 0.028, 0.030, 0.032, 0.033),
        currency="CNY", market="CNY",
    )


def build(n=2000, months=120, seed=42):
    curve = _cny_curve()

    # 1. swaption fit -----------------------------------------------------
    import par_model_v2.stochastic.g2pp_swaption as sw
    cal = sw.calibrate_g2pp_to_swaptions(curve=curve)
    gate = sw.evaluate_g_swpn_gate(calibration=cal, curve=curve)
    g2_params = cal.params

    # 2. generate promoted G2++ set + HW1F benchmark (Q-measure) ----------
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        g2 = esg.ScenarioSet.generate(n=n, T_months=months, measure=esg.Measure.Q,
                                      seed=seed, rate_model="g2pp",
                                      g2_params=g2_params, initial_curve=curve)
        hw = esg.ScenarioSet.generate(n=n, T_months=months, measure=esg.Measure.Q,
                                      seed=seed, rate_model="hw1f",
                                      initial_curve=curve)
        # governed default (no rate_model kwarg) - must match the pinned digest
        default_q = esg.ScenarioSet.generate(n=200, T_months=120,
                                             measure=esg.Measure.Q, seed=42)
        default_p = esg.ScenarioSet.generate(n=200, T_months=120,
                                             measure=esg.Measure.P, seed=42)

    # 3. martingale evidence on the promoted set --------------------------
    mart = esg.QMeasureMartingaleValidator().validate(curve, g2.data)

    # 4. curve-twist evidence vs the one-factor benchmark -----------------
    twist = esg.CurveTwistValidator().validate(
        g2.data, benchmark_data=hw.data, rate_model="g2pp")

    # inputs digest (config only - fully reproducible, timestamp excluded) -
    cfg = {
        "schema": SCHEMA, "n": n, "months": months, "seed": seed,
        "curve": {"tenors": list(curve.tenors_years), "zeros": list(curve.zero_rates)},
        "g2_params": cal.params_dict(),
    }
    inputs_digest = hashlib.sha256(
        json.dumps(cfg, sort_keys=True, default=str).encode()).hexdigest()

    artifact = {
        "schema": SCHEMA,
        "title": "G2++ Two-Factor Rate-Model Production Promotion - Evidence",
        "roadmap_item": "4.1 #7 (MR-004)",
        "generated_at": _dt.datetime.now(tz=_dt.timezone.utc).isoformat(),
        "inputs_digest": inputs_digest,
        "unsigned": True,
        "unsigned_banner": (
            "UNSIGNED - educational calibration to a synthetic proxy swaption "
            "surface; G2++ is a SELECTABLE production rate model but the governed "
            "headline stays on HW1F. Re-baselining the headline onto G2++ requires "
            "owner sign-off + independent review (IA TAS M §3.6)."
        ),
        "selectability": {
            "generate_kwarg": "ScenarioSet.generate(rate_model=..., g2_params=...)",
            "available_rate_models": list(esg.available_rate_models()),
            "default_rate_model": esg.DEFAULT_RATE_MODEL,
            "resolver_is_fail_loud": True,
            "diagnostic_columns_added": ["g2pp_x", "g2pp_y"],
        },
        "hw1f_fallback_identity": {
            "statement": ("The default path is byte-for-byte unchanged; the extra "
                          "G2++ RNG draw is taken only in the g2pp branch, after "
                          "the hw1f draws."),
            "default_q_digest": _digest(default_q.data),
            "default_p_digest": _digest(default_p.data),
            "pinned_q_digest": HW1F_Q_DIGEST,
            "pinned_p_digest": HW1F_P_DIGEST,
            "q_identical": _digest(default_q.data) == HW1F_Q_DIGEST,
            "p_identical": _digest(default_p.data) == HW1F_P_DIGEST,
        },
        "swaption_fit": {
            "converged": bool(cal.converged),
            "n_quotes": int(cal.n_quotes),
            "iterations": int(cal.iterations),
            "rmse_vol_bps": float(cal.rmse_vol_bps),
            "max_abs_vol_bps": float(cal.max_abs_vol_bps),
            "calibrated_params": cal.params_dict(),
            "gate_id": getattr(gate, "gate_id", None),
            "gate_passed": bool(getattr(gate, "passed", False)),
            "use_restriction": getattr(gate, "use_restriction", None),
        },
        "martingale_evidence": {
            "n_scenarios": n, "horizon_months": months,
            "passed": bool(mart.passed),
            "diagnostics": {k: float(v) for k, v in mart.diagnostics.items()},
            "failed_checks": [c.to_dict() for c in mart.failed_checks()],
        },
        "curve_twist_evidence": {
            "passed": bool(twist.passed),
            "report": twist.to_dict(),
            "interpretation": (
                "A one-factor model drives every tenor off one Brownian factor "
                "so short/long changes are near-perfectly correlated (parallel "
                "shifts only). The two-factor G2++ decorrelates them, evidencing "
                "genuine curve twists / steepening."
            ),
        },
    }
    return artifact


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=2000)
    ap.add_argument("--months", type=int, default=120)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()
    repo = Path(__file__).resolve().parents[1]
    out_dir = repo / "docs" / "validation"
    out_dir.mkdir(parents=True, exist_ok=True)
    artifact = build(n=args.n, months=args.months, seed=args.seed)
    out = out_dir / "G2PP_PRODUCTION_PROMOTION.json"
    out.write_text(json.dumps(artifact, indent=2), encoding="utf-8")
    print("wrote", out.relative_to(repo))
    print("  swaption RMSE vol bps :", round(artifact["swaption_fit"]["rmse_vol_bps"], 3),
          "| gate", "PASS" if artifact["swaption_fit"]["gate_passed"] else "FAIL")
    print("  martingale passed     :", artifact["martingale_evidence"]["passed"])
    print("  twist g2 vs hw1f corr :",
          round(artifact["curve_twist_evidence"]["report"]["diagnostics"]["short_long_change_correlation"], 4),
          "vs",
          round(artifact["curve_twist_evidence"]["report"]["diagnostics"]["benchmark_short_long_change_correlation"], 4))
    print("  hw1f fallback identity:", artifact["hw1f_fallback_identity"]["q_identical"]
          and artifact["hw1f_fallback_identity"]["p_identical"])
    print("  inputs_digest         :", artifact["inputs_digest"][:16], "...")


if __name__ == "__main__":
    main()
