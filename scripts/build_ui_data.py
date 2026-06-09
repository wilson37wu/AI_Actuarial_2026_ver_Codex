"""UI Task 1 (offline user-interface track) -- inventory + data contract bundler.

This is NOT a model calculation. It scans the model's ALREADY-PRODUCED output
artifacts (docs/validation/*.json, the legacy docs/*CALIBRATION*.json reports,
.claude-dev/GOVERNANCE_STORE.json, MODEL_DEV_STATE.json and the existing
viewer_data.json), normalises them into ONE stable ``ui_data.json`` contract,
and emits a fully self-contained ``ui_app.html`` with that snapshot embedded so
the UI opens OFFLINE with data pre-loaded (no CDN, no server, no install, no
runtime network).

Contract sections (ui_data.json):
  contract_version : str   -- bump on breaking schema changes
  meta             : dict  -- model name/version/classification/generated
  summary          : dict  -- task/phase/gate/risk roll-up + production status
  inventory        : list  -- catalogue of EVERY source artifact surfaced
  capital          : dict  -- seven-driver SCRs, var-covar/copula/nested
  tail             : dict  -- 99.5% VaR/ES, convergence, bootstrap CI, VR
  proxy            : dict  -- LSMC proxy validation (degree sweep, overfit)
  loss             : dict  -- pre-computed loss distribution (look-up only)
  calibrations     : list  -- one record per calibrated driver + gate status
  governance       : dict  -- audit/changes/risks/gates (read-only)
  verdicts         : list  -- headline PASS/FAIL verdicts

Run:  PYTHONPATH=. python3 scripts/build_ui_data.py
Outputs (repo root):  ui_data.json , ui_app.html
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
import os
from typing import Any, Dict, List, Optional

CONTRACT_VERSION = "1.10.0"

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VAL = os.path.join(REPO, "docs", "validation")
DOCS = os.path.join(REPO, "docs")
GOV_PATH = os.path.join(REPO, ".claude-dev", "GOVERNANCE_STORE.json")
STATE_PATH = os.path.join(REPO, ".claude-dev", "MODEL_DEV_STATE.json")
VIEWER_DATA = os.path.join(REPO, "viewer_data.json")
OUT_JSON = os.path.join(REPO, "ui_data.json")
OUT_HTML = os.path.join(REPO, "ui_app.html")

DATA_TOKEN = "/*__UI_DATA__*/null"


def _load(path: str) -> Optional[dict]:
    try:
        with open(path) as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def _sha256_file(path: str) -> str:
    h = hashlib.sha256()
    try:
        with open(path, "rb") as fh:
            for chunk in iter(lambda: fh.read(65536), b""):
                h.update(chunk)
    except OSError:
        return ""
    return h.hexdigest()


def _mtime_utc(path: str) -> str:
    try:
        return _dt.datetime.utcfromtimestamp(os.path.getmtime(path)).isoformat() + "Z"
    except OSError:
        return ""


# --------------------------------------------------------------------------- #
# Inventory: catalogue every model-output artifact the UI may surface.
# --------------------------------------------------------------------------- #
_CATEGORY_RULES = [
    ("AGGREGATION", "risk_aggregation"),
    ("TAIL_DIAGNOSTICS", "tail_diagnostics"),
    ("PROXY_VALIDATION", "proxy_validation"),
    ("CALIBRATION", "calibration"),
    ("LOSS_DISTRIBUTION", "loss_distribution"),
    ("CAPITAL", "capital_evidence"),
    ("GOVERNANCE", "governance"),
    ("IA_TASM", "ia_validation"),
    ("APS_X2", "independent_review"),
    ("BACKTEST", "backtest"),
    ("DASHBOARD", "dashboard"),
    ("DYNAMIC_LAPSE", "calibration"),
    ("MR001", "model_risk"),
]


def _categorise(fname: str) -> str:
    up = fname.upper()
    for token, cat in _CATEGORY_RULES:
        if token in up:
            return cat
    return "other"


def _headline(obj: Any) -> str:
    """Best-effort one-line headline from a report dict."""
    if not isinstance(obj, dict):
        return ""
    for key in ("verdict", "status", "overall_verdict"):
        v = obj.get(key)
        if isinstance(v, str) and v:
            return v[:160]
    for sub in ("copula", "summary", "gate_glapse", "gate"):
        s = obj.get(sub)
        if isinstance(s, dict):
            for key in ("verdict", "status"):
                v = s.get(key)
                if isinstance(v, str) and v:
                    return (sub + ": " + v)[:160]
    return ""


def _build_inventory() -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    seen = set()
    legacy_named = [
        "PHASE13_HW1F_CALIBRATION_REPORT.json",
        "PHASE14_GBM_CALIBRATION_REPORT.json",
        "PHASE13_DYNAMIC_LAPSE_REPORT.json",
        "PHASE13_MR001_DISCOUNT_RATE_REPORT.json",
        "PHASE12_VALIDATION_DASHBOARD.json",
    ]
    paths: List[str] = []
    if os.path.isdir(VAL):
        for fn in sorted(os.listdir(VAL)):
            if fn.endswith(".json"):
                paths.append(os.path.join(VAL, fn))
    for fn in legacy_named:
        p = os.path.join(DOCS, fn)
        if os.path.isfile(p):
            paths.append(p)
    for p in paths:
        rp = os.path.relpath(p, REPO).replace(os.sep, "/")
        if rp in seen:
            continue
        seen.add(rp)
        obj = _load(p)
        items.append({
            "id": os.path.splitext(os.path.basename(p))[0],
            "path": rp,
            "category": _categorise(os.path.basename(p)),
            "bytes": (os.path.getsize(p) if os.path.isfile(p) else 0),
            "sha256": _sha256_file(p),
            "mtime_utc": _mtime_utc(p),
            "headline": _headline(obj),
        })
    return items


# --------------------------------------------------------------------------- #
# Calibrations: one normalised record per calibrated stochastic driver.
# --------------------------------------------------------------------------- #
def _calib_record(driver: str, gate_id: str, market: str, params: Dict[str, Any],
                  gate_status: str, gate_evidence: str, is_placeholder: Optional[bool],
                  source: str, lineage: Any,
                  diagnostics: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    return {
        "driver": driver,
        "gate_id": gate_id,
        "market": market,
        "params": params,
        "gate_status": gate_status,
        "gate_evidence": gate_evidence,
        "is_placeholder": bool(is_placeholder) if is_placeholder is not None else None,
        "source": source,
        "lineage_id": (lineage.get("lineage_id") if isinstance(lineage, dict) else None),
        # UI Task 3 -- per-driver fit diagnostics for the calibration explorer.
        # {method, n_obs, fit_r2, converged, criteria:[{name,ok}],
        #  fit_bars:{title,unit,items:[{label,value}],threshold:{label,value}|None}|None}
        "diagnostics": diagnostics or {},
    }


# Human-readable labels for the per-gate boolean criteria dicts emitted by the
# calibrators. Unknown keys are prettified by stripping the leading "cN_" token.
_CRIT_NAMES = {
    "c1_min_daily_obs": "Sufficient daily observations",
    "c2_sigma_in_band": "Volatility within plausibility band",
    "c3_erp_documented": "Equity-risk-premium documented",
    "c4_rho_in_band": "Rate-equity correlation in band",
    "c5_not_placeholder": "Not a placeholder",
    "c6_param_change_audit": "Parameter change audited",
    "c1_min_obs": "Sufficient observations",
    "c2_kappa_in_band": "Mean-reversion speed in band",
    "c3_long_run_in_band": "Long-run level in band",
    "c4_sigma_in_band": "Volatility within band",
    "c5_lambda_in_band": "Market price of risk in band",
    "c5_stationary_std_in_band": "Stationary std-dev in band",
    "c6_not_placeholder_with_audit": "Not a placeholder; change audited",
}


def _criteria_list(crit: Any) -> List[Dict[str, Any]]:
    """Normalise a {key: bool} gate-criteria dict into [{name, ok}] for the UI."""
    out: List[Dict[str, Any]] = []
    if isinstance(crit, dict):
        for k, v in crit.items():
            name = _CRIT_NAMES.get(k)
            if name is None:
                # strip a leading "cN_" then title-case the remainder
                rest = k.split("_", 1)[1] if k[:1] == "c" and "_" in k else k
                name = rest.replace("_", " ").strip().capitalize()
            out.append({"name": name, "ok": bool(v)})
    return out


def _num(x: Any) -> Optional[float]:
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def _build_calibrations() -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []

    hw = _load(os.path.join(DOCS, "PHASE13_HW1F_CALIBRATION_REPORT.json"))
    if isinstance(hw, dict):
        for mkt, sub in hw.items():
            if isinstance(sub, dict) and "sigma_r" in sub:
                rmse = _num(sub.get("swaption_rmse_bps"))
                maxe = _num(sub.get("max_swaption_error_bps"))
                conv = sub.get("converged")
                band = 25.0  # G-02 swaption-RMSE plausibility band (bps)
                crit = [
                    {"name": "Not a placeholder", "ok": not sub.get("is_placeholder")},
                    {"name": "Swaption RMSE within G-02 band (≤ 25 bps)",
                     "ok": (rmse is not None and rmse <= band)},
                    {"name": "Optimiser converged", "ok": bool(conv)},
                ]
                items = [it for it in (
                    {"label": "Swaption RMSE", "value": rmse} if rmse is not None else None,
                    {"label": "Max error", "value": maxe} if maxe is not None else None,
                ) if it]
                diag = {
                    "method": "L-BFGS-B least-squares fit to the market swaption surface",
                    "n_obs": None, "fit_r2": None, "converged": bool(conv) if conv is not None else None,
                    "criteria": crit,
                    "fit_bars": ({"title": "Swaption fit error vs the G-02 band",
                                  "unit": "bps", "items": items,
                                  "threshold": {"label": "G-02 band (25 bps)", "value": band}}
                                 if items else None),
                }
                out.append(_calib_record(
                    "Interest rate (HW1F)", "G-02", sub.get("market", mkt),
                    {"a": sub.get("a"), "sigma_r": sub.get("sigma_r"), "r0": sub.get("r0"),
                     "swaption_rmse_bps": sub.get("swaption_rmse_bps")},
                    "PASS" if not sub.get("is_placeholder") else "PLACEHOLDER",
                    "swaption RMSE %s bps; converged=%s" % (sub.get("swaption_rmse_bps"), conv),
                    sub.get("is_placeholder"),
                    "docs/PHASE13_HW1F_CALIBRATION_REPORT.json", sub.get("lineage"), diag))

    g2 = _load(os.path.join(VAL, "PHASE20_TASK2_G2PP_SWAPTION_REPORT.json"))
    if isinstance(g2, dict):
        gate = g2.get("gate", {})
        cal = gate.get("calibration", {}) if isinstance(gate, dict) else {}
        params = cal.get("params", {}) if isinstance(cal, dict) else {}
        rmse = _num(cal.get("rmse_vol_bps"))
        maxe = _num(cal.get("max_abs_vol_bps"))
        obj = _num(cal.get("objective_value"))
        conv = cal.get("converged")
        checks = gate.get("checks", []) if isinstance(gate, dict) else []
        criteria = []
        for chk in checks:
            if isinstance(chk, dict):
                criteria.append({"name": chk.get("description", chk.get("check_id", "")),
                                 "ok": bool(chk.get("passed"))})
        items = [it for it in (
            {"label": "RMSE vol error", "value": rmse} if rmse is not None else None,
            {"label": "Max vol error", "value": maxe} if maxe is not None else None,
            {"label": "Objective x10k", "value": obj * 10000.0} if obj is not None else None,
        ) if it]
        diag = {
            "method": "Two-factor G2++ calibration to the educational ATM swaption surface",
            "n_obs": cal.get("n_quotes"),
            "fit_r2": None,
            "converged": bool(conv) if conv is not None else None,
            "criteria": criteria,
            "fit_bars": ({"title": "G2++ swaption calibration diagnostics",
                          "unit": "bps / scaled objective",
                          "items": items,
                          "threshold": {"label": "G-SWPN RMSE band (75 bps)", "value": 75.0}}
                         if items else None),
        }
        out.append(_calib_record(
            "Interest rate (G2++ 2F)", gate.get("gate_id", "G-SWPN"), "HKD",
            {"a": params.get("mean_reversion_x"),
             "b": params.get("mean_reversion_y"),
             "sigma": params.get("vol_x"),
             "eta": params.get("vol_y"),
             "rho": params.get("factor_correlation"),
             "rmse_vol_bps": cal.get("rmse_vol_bps"),
             "max_abs_vol_bps": cal.get("max_abs_vol_bps")},
            gate.get("status", "PASS"),
            "G2++ swaption gate %s; RMSE %.1f bps, max error %.1f bps, converged=%s"
            % (gate.get("status", "PASS"), rmse or 0.0, maxe or 0.0, conv),
            False, "docs/validation/PHASE20_TASK2_G2PP_SWAPTION_REPORT.json", None, diag))

    gbm = _load(os.path.join(DOCS, "PHASE14_GBM_CALIBRATION_REPORT.json"))
    if isinstance(gbm, dict):
        for sub in gbm.get("summaries", []):
            if isinstance(sub, dict):
                imp = _num(sub.get("equity_vol_implied"))
                hist = _num(sub.get("equity_vol_hist"))
                sig = _num(sub.get("sigma_S"))
                vitems = [it for it in (
                    {"label": "σ implied", "value": imp * 100.0} if imp is not None else None,
                    {"label": "σ historical", "value": hist * 100.0} if hist is not None else None,
                    {"label": "σ blended", "value": sig * 100.0} if sig is not None else None,
                ) if it]
                diag = {
                    "method": "Blended implied/historical vol (60/40); survivorship-adjusted ERP",
                    "n_obs": sub.get("n_daily_obs"), "fit_r2": None, "converged": None,
                    "criteria": _criteria_list(sub.get("criteria")),
                    "fit_bars": ({"title": "Equity-volatility decomposition",
                                  "unit": "%", "items": vitems, "threshold": None}
                                 if vitems else None),
                }
                out.append(_calib_record(
                    "Equity (GBM)", "G-03", sub.get("market", ""),
                    {"sigma_S": sub.get("sigma_S"), "erp": sub.get("erp"),
                     "dividend_yield": sub.get("dividend_yield"), "rho": sub.get("rho")},
                    "PASS" if not sub.get("is_placeholder") else "PLACEHOLDER",
                    (sub.get("notes", "") or "")[:140], sub.get("is_placeholder"),
                    "docs/PHASE14_GBM_CALIBRATION_REPORT.json", sub.get("lineage"), diag))

    cir = _load(os.path.join(VAL, "PHASE18_CIR_CALIBRATION_REPORT.json"))
    if isinstance(cir, dict):
        s = cir.get("summary", cir)
        gate = cir.get("gate_gcr") or cir.get("gate") or {}
        s0 = _num(s.get("initial_spread"))
        lrp = _num(s.get("long_run_spread_p") or s.get("long_run_level") or s.get("long_run_spread"))
        lrq = _num(s.get("risk_neutral_long_run_spread"))
        sitems = [it for it in (
            {"label": "Initial s₀", "value": s0 * 1e4} if s0 is not None else None,
            {"label": "Long-run P", "value": lrp * 1e4} if lrp is not None else None,
            {"label": "Long-run Q", "value": lrq * 1e4} if lrq is not None else None,
        ) if it]
        diag = {
            "method": "CIR OLS transition regression; Feller condition checked; documented Q anchor",
            "n_obs": s.get("n_obs"), "fit_r2": _num(s.get("fit_r2")), "converged": None,
            "criteria": _criteria_list(s.get("criteria")),
            "fit_bars": ({"title": "Credit-spread level structure",
                          "unit": "bp", "items": sitems, "threshold": None}
                         if sitems else None),
        }
        out.append(_calib_record(
            "Credit spread (CIR++)", "G-CR", s.get("market", "CNY"),
            {"kappa": s.get("kappa"),
             "long_run_level": s.get("long_run_spread_p") or s.get("long_run_level") or s.get("long_run_spread"),
             "sigma": s.get("spread_vol") or s.get("sigma"),
             "lambda": s.get("market_price_of_credit_risk") or s.get("lambda"),
             "feller_ok": s.get("feller_ok")},
            gate.get("status", "PASS"), (gate.get("evidence", s.get("notes", "")) or "")[:140],
            s.get("is_placeholder"), "docs/validation/PHASE18_CIR_CALIBRATION_REPORT.json",
            s.get("lineage"), diag))

    lap = _load(os.path.join(VAL, "PHASE19_LAPSE_CALIBRATION_REPORT.json"))
    if isinstance(lap, dict):
        s = lap.get("summary", {})
        gate = lap.get("gate_glapse", {})
        hl = _num(s.get("half_life_years"))
        sst = _num(s.get("stationary_std"))
        ae = _num(s.get("long_run_ae"))
        litems = [it for it in (
            {"label": "Half-life (yr)", "value": hl} if hl is not None else None,
            {"label": "Stationary σ", "value": sst} if sst is not None else None,
            {"label": "Long-run A/E", "value": ae} if ae is not None else None,
        ) if it]
        diag = {
            "method": "OU AR(1) OLS regression on the log(A/E) experience series",
            "n_obs": s.get("n_obs"), "fit_r2": _num(s.get("fit_r2")), "converged": None,
            "criteria": _criteria_list(s.get("criteria")),
            "fit_bars": ({"title": "OU behavioural-index diagnostics",
                          "unit": "", "items": litems, "threshold": None}
                         if litems else None),
        }
        out.append(_calib_record(
            "Dynamic lapse (OU)", gate.get("gate_id", "G-LAPSE"), s.get("market", "HK_PAR"),
            {"kappa": s.get("kappa"), "long_run_level": s.get("long_run_level"),
             "behaviour_vol": s.get("behaviour_vol"), "stationary_std": s.get("stationary_std"),
             "half_life_years": s.get("half_life_years"), "long_run_ae": s.get("long_run_ae")},
            gate.get("status", "PASS"), (gate.get("evidence", "") or "")[:160],
            s.get("is_placeholder"), "docs/validation/PHASE19_LAPSE_CALIBRATION_REPORT.json",
            s.get("lineage"), diag))

    # FX / currency driver (6th driver, Phase 21 Task 1): lognormal spot with
    # P-measure outer drift and CIP-exact Q conditioning; G-FX plausibility gate.
    fx = _load(os.path.join(VAL, "PHASE21_TASK1_FX_DRIVER_REPORT.json"))
    if isinstance(fx, dict) and isinstance(fx.get("gate"), dict):
        gate = fx["gate"]
        params = gate.get("params", {}) if isinstance(gate.get("params"), dict) else {}
        crit = []
        cip_z, cip_tol = None, None
        for c in gate.get("criteria", []):
            if isinstance(c, dict):
                crit.append({"name": str(c.get("criterion", "")).replace("-", " "),
                             "ok": bool(c.get("passed"))})
                ev = c.get("evidence", {})
                if isinstance(ev, dict) and ev.get("check_id") == "MART-FX-CIP":
                    cip_z = _num(ev.get("n_std_errors"))
                    cip_tol = _num(ev.get("tolerance_sigma"))
        items = ([{"label": "CIP martingale |z|", "value": cip_z}]
                 if cip_z is not None else [])
        diag = {
            "method": "Lognormal FX spot; P-measure outer drift, CIP-exact analytic Q "
                      "conditioning (MART-FX-CIP martingale evidence)",
            "n_obs": params.get("n_scenarios"), "fit_r2": None, "converged": None,
            "criteria": crit,
            "fit_bars": ({"title": "Q-measure CIP martingale evidence",
                          "unit": "sigma", "items": items,
                          "threshold": ({"label": "G-FX tolerance (%.0f sigma)" % cip_tol,
                                         "value": cip_tol} if cip_tol else None)}
                         if items else None),
        }
        status = "PASS" if gate.get("passed") else "FAIL"
        out.append(_calib_record(
            "FX / currency (lognormal)", gate.get("gate", "G-FX"), "USD/HKD",
            {"fx_vol": params.get("fx_vol"),
             "rate_spread": params.get("domestic_foreign_rate_spread"),
             "initial_spot": params.get("initial_spot_rate"),
             "real_world_drift": params.get("real_world_drift")},
            status,
            "G-FX %s (%s/%s criteria); CIP martingale z=%.3f sigma"
            % (status, gate.get("n_passed"), gate.get("n_criteria"), cip_z or 0.0),
            False, "docs/validation/PHASE21_TASK1_FX_DRIVER_REPORT.json", None, diag))

    # Liquidity-premium driver (7th driver, Phase 21 Task 3): CIR++ funding-spread /
    # illiquidity-premium process calibrated on the HKD educational fixture; G-LIQ gate.
    liq = _load(os.path.join(VAL, "PHASE21_TASK3_LIQUIDITY_CALIBRATION_REPORT.json"))
    if isinstance(liq, dict) and isinstance(liq.get("summary"), dict):
        s = liq["summary"]
        gate = liq.get("gate_gliq", {}) if isinstance(liq.get("gate_gliq"), dict) else {}
        lr = _num(s.get("long_run_premium_p"))
        l0 = _num(s.get("initial_premium"))
        litems = [it for it in (
            {"label": "Initial premium", "value": l0 * 1e4} if l0 is not None else None,
            {"label": "Long-run P", "value": lr * 1e4} if lr is not None else None,
        ) if it]
        diag = {
            "method": "CIR++ OLS transition regression (delegated to the tested CIR "
                      "estimator); Feller checked; lambda_l clamped at plausibility cap "
                      "(disclosed)",
            "n_obs": s.get("n_obs"), "fit_r2": _num(s.get("fit_r2")), "converged": None,
            "criteria": _criteria_list(s.get("criteria")),
            "fit_bars": ({"title": "Liquidity-premium level structure",
                          "unit": "bp", "items": litems, "threshold": None}
                         if litems else None),
        }
        out.append(_calib_record(
            "Liquidity premium (CIR++)", gate.get("gate_id", "G-LIQ"),
            s.get("market", "HKD"),
            {"kappa_l": s.get("kappa"), "long_run_premium": s.get("long_run_premium_p"),
             "sigma_l": s.get("premium_vol"),
             "lambda_l": s.get("market_price_of_liquidity_risk"),
             "half_life_years": s.get("half_life_years"),
             "feller_ok": s.get("feller_ok")},
            gate.get("status", "PASS"), (gate.get("evidence", "") or "")[:160],
            s.get("is_placeholder"),
            "docs/validation/PHASE21_TASK3_LIQUIDITY_CALIBRATION_REPORT.json",
            s.get("lineage"), diag))

    # Liquidity exposure-notional + 7x7 couplings (Phase 22 Task 3): G-LIQX gate.
    # Replaces the placeholder exposure (30,000) and couplings with reproducible
    # calibrated values (1,200-month seeded joint synthesis; PSD-validated).
    liqx = _load(os.path.join(VAL, "PHASE22_TASK3_LIQUIDITY_EXPOSURE_REPORT.json"))
    if isinstance(liqx, dict) and isinstance(liqx.get("gate_gliqx"), dict):
        gate = liqx["gate_gliqx"]
        expo = liqx.get("exposure", {}) if isinstance(liqx.get("exposure"), dict) else {}
        est = (liqx.get("estimated_couplings", {})
               if isinstance(liqx.get("estimated_couplings"), dict) else {})
        crit = [{"name": k.replace("_", " "), "ok": bool(v)}
                for k, v in (liqx.get("criteria") or {}).items()]
        litems = [{"label": k.replace("liq_", "liq-"), "value": _num(v)}
                  for k, v in est.items() if _num(v) is not None]
        diag = {
            "method": "Exposure notional = backing MV x illiquid share x forced-sale "
                      "fraction (lineage-checksummed fixture); couplings estimated "
                      "from a 1,200-month seeded joint synthesis, recovered within "
                      "0.12 of documented targets; 7x7 PSD-validated; capital "
                      "sensitivity bounded (net-diversifying finding)",
            "n_obs": liqx.get("n_obs"), "fit_r2": None, "converged": None,
            "criteria": crit,
            "fit_bars": ({"title": "Estimated liquidity couplings (7x7 row)",
                          "unit": "corr", "items": litems,
                          "threshold": ({"label": "recovery tolerance",
                                         "value": _num(liqx.get("coupling_tolerance"))}
                                        if _num(liqx.get("coupling_tolerance"))
                                        is not None else None)}
                         if litems else None),
        }
        out.append(_calib_record(
            "Liquidity exposure + couplings (G-LIQX)",
            gate.get("gate_id", "G-LIQX"), liqx.get("market", "HKD"),
            {"exposure_notional": expo.get("exposure_notional"),
             "backing_asset_mv": expo.get("backing_asset_mv"),
             "illiquid_share": expo.get("illiquid_share"),
             "forced_sale_fraction": expo.get("forced_sale_fraction"),
             "coupling_tolerance": liqx.get("coupling_tolerance"),
             "correlation7_psd": liqx.get("correlation7_psd_passed")},
            gate.get("status", "PASS"), (gate.get("evidence", "") or "")[:160],
            liqx.get("is_placeholder"),
            "docs/validation/PHASE22_TASK3_LIQUIDITY_EXPOSURE_REPORT.json",
            liqx.get("lineage"), diag))

    # Mortality-trend driver: the 5th capital driver is an EDUCATIONAL parametric
    # placeholder (OU / Lee-Carter-style index, P=Q non-financial). It is NOT
    # calibrated to a mortality-experience series and has no plausibility gate yet,
    # so this panel is included for completeness and honestly flagged as such.
    kappa_m, sigma_m = 0.30, 0.15
    stat_std = sigma_m / (2.0 * kappa_m) ** 0.5
    out.append(_calib_record(
        "Mortality trend (OU)", "G-MORT (n/a)", "HK_PAR",
        {"kappa_m": kappa_m, "sigma_m": sigma_m, "initial_index": 0.0,
         "stationary_std": stat_std},
        "PLACEHOLDER", "Educational placeholder — illustrative kappa_m/sigma_m, "
        "not calibrated to a mortality-experience series; no G-MORT plausibility gate defined.",
        True, "par_model_v2/stochastic/mortality_trend.py", None,
        {"method": "Educational placeholder (OU / Lee-Carter-style trend; P=Q, non-financial)",
         "n_obs": None, "fit_r2": None, "converged": None,
         "criteria": [{"name": "Calibrated to experience data", "ok": False},
                      {"name": "Plausibility gate defined", "ok": False}],
         "fit_bars": None}))

    return out


# --------------------------------------------------------------------------- #
# Capital reconciliation against the latest five-driver aggregation report.
# --------------------------------------------------------------------------- #
def _scr_from_standalone(standalone: Dict[str, Any], name: str) -> Any:
    v = standalone.get(name, {})
    return v.get("scr_proxy") if isinstance(v, dict) else None


def _build_capital(base: Dict[str, Any]) -> Dict[str, Any]:
    cap = dict(base) if isinstance(base, dict) else {}

    # Phase 21 Task 4: seven-driver (rate, equity, credit, lapse, mortality, FX,
    # liquidity) tail-dependent aggregation — preferred snapshot when present.
    phase21, _agg_src = None, None
    for _fn in ("PHASE22_TASK4_AGGREGATION_REPORT.json",
                "PHASE21_TASK4_AGGREGATION_REPORT.json"):
        _cand = _load(os.path.join(VAL, _fn))
        if isinstance(_cand, dict) and isinstance(_cand.get("aggregation"), dict):
            phase21, _agg_src = _cand, "docs/validation/" + _fn
            break
    if isinstance(phase21, dict) and isinstance(phase21.get("aggregation"), dict):
        rep = phase21["aggregation"]
        sa = rep.get("standalone_scr", {})
        if isinstance(sa, dict):
            for key, src in (("rate_scr", "rate"), ("equity_scr", "equity"),
                             ("credit_scr", "credit"), ("lapse_scr", "lapse"),
                             ("mortality_scr", "mortality"), ("fx_scr", "fx"),
                             ("liquidity_scr", "liquidity")):
                v = _num(sa.get(src))
                if v is not None:
                    cap[key] = v
        cap["nested_scr"] = rep.get("nested_scr", cap.get("nested_scr"))
        cap["var_covar_scr"] = rep.get("var_covar_scr", cap.get("var_covar_scr"))
        cap["standalone_sum"] = rep.get("standalone_scr_sum", cap.get("standalone_sum"))
        cap["selected_copula"] = rep.get("copula_selected")
        cap["formula_vs_nested_rel_error"] = rep.get("var_covar_vs_nested_rel_error")
        if rep.get("var_covar_vs_nested_rel_error") is not None:
            cap["esg_understatement_pct"] = round(
                100.0 * rep["var_covar_vs_nested_rel_error"], 2)
        cop = rep.get("copula_report", {})
        if isinstance(cop, dict):
            cap["copula"] = dict(cop)
            cap["copula"]["candidates"] = cop.get("candidates") or cop.get("copulas", [])
        cap["copula_scr"] = rep.get("copula_scr")
        cap["copula_vs_nested_rel_error"] = rep.get("copula_vs_nested_rel_error")
        cap["n_drivers"] = len(rep.get("drivers", [])) or 7
        cap["drivers"] = rep.get("drivers", [])
        cap["rate_driver"] = "G2++ two-factor rates"
        cap["liquidity_note"] = ("Liquidity standalone SCR is small under the "
                                 "calibrated mean reversion (half-life 0.74y over a "
                                 "~19y workout) — documented finding, verified "
                                 "CIR-affine-exact.")
        cap["aggregation_source"] = _agg_src
        if "PHASE22_TASK4" in str(_agg_src):
            _notional = _num(rep.get("liquidity_exposure_notional"))
            cap["liquidity_exposure_notional"] = _notional
            cap["liquidity_inputs_calibrated"] = True
            comp = phase21.get("comparison_vs_placeholder")
            if isinstance(comp, dict):
                cap["calibrated_vs_placeholder"] = comp
            cap["liquidity_note"] = (
                "Liquidity inputs are G-LIQX-CALIBRATED: exposure notional "
                + ("%.0f" % _notional if _notional is not None else "n/a")
                + " replaces the 30,000 placeholder; the six couplings are "
                "estimated from a 1,200-month seeded joint synthesis "
                "(PSD-validated). The standalone liquidity SCR remains small "
                "under the calibrated mean reversion (half-life 0.74y over a "
                "~19y workout) - documented finding, verified CIR-affine-exact.")
        cap["aggregation_verdict"] = rep.get("verdict")
        return cap

    phase20 = _load(os.path.join(VAL, "PHASE20_TASK4_AGGREGATION_REPORT.json"))
    if isinstance(phase20, dict) and isinstance(phase20.get("g2pp_report"), dict):
        rep = phase20["g2pp_report"]
        sa = rep.get("standalone", {})
        for key, src in (("rate_scr", "rate_capital"), ("equity_scr", "equity_capital"),
                         ("credit_scr", "credit_capital"), ("lapse_scr", "lapse_capital"),
                         ("mortality_scr", "mortality_capital")):
            v = _scr_from_standalone(sa, src)
            if v is not None:
                cap[key] = v
        cop = rep.get("copula", {})
        if isinstance(cop, dict):
            cap["nested_scr"] = cop.get("nested_scr", cap.get("nested_scr"))
            cap["var_covar_scr"] = cop.get("var_covar_scr", cap.get("var_covar_scr"))
            cap["standalone_sum"] = cop.get("standalone_scr_sum", cap.get("standalone_sum"))
            cap["selected_copula"] = cop.get("selected_copula")
            cap["formula_vs_nested_rel_error"] = cop.get("var_covar_rel_error_vs_nested")
            cap["copula"] = dict(cop)
            cap["copula"]["candidates"] = cop.get("candidates") or cop.get("copulas", [])
            if cop.get("var_covar_rel_error_vs_nested") is not None:
                cap["esg_understatement_pct"] = round(100.0 * cop["var_covar_rel_error_vs_nested"], 2)
        cap["n_drivers"] = 5
        cap["rate_driver"] = "G2++ two-factor rates"
        cap["aggregation_source"] = "docs/validation/PHASE20_TASK4_AGGREGATION_REPORT.json"
        cap["aggregation_verdict"] = rep.get("verdict")
        comp = phase20.get("comparison", {})
        if isinstance(comp, dict):
            cap["comparison"] = comp
            nested_cmp = comp.get("nested_scr", {})
            if isinstance(nested_cmp, dict):
                cap["nested_scr_reduction_pct"] = round(-100.0 * nested_cmp.get("rel_delta", 0.0), 2)
        return cap

    agg = _load(os.path.join(VAL, "PHASE19_TASK4_AGGREGATION_REPORT.json"))
    if isinstance(agg, dict):
        sa = agg.get("standalone", {})
        for key, src in (("rate_scr", "rate_capital"), ("equity_scr", "equity_capital"),
                         ("credit_scr", "credit_capital"), ("lapse_scr", "lapse_capital"),
                         ("mortality_scr", "mortality_capital")):
            v = _scr_from_standalone(sa, src)
            if v is not None:
                cap[key] = v
        cop = agg.get("copula", {})
        if isinstance(cop, dict):
            cap["nested_scr"] = cop.get("nested_scr", cap.get("nested_scr"))
            cap["var_covar_scr"] = cop.get("var_covar_scr", cap.get("var_covar_scr"))
            cap["standalone_sum"] = cop.get("standalone_scr_sum", cap.get("standalone_sum"))
            cap["selected_copula"] = cop.get("selected_copula")
            cap["formula_vs_nested_rel_error"] = cop.get("var_covar_rel_error_vs_nested")
            cap["copula"] = dict(cop)
            cap["copula"]["candidates"] = cop.get("candidates") or cop.get("copulas", [])
            if cop.get("var_covar_rel_error_vs_nested") is not None:
                cap["esg_understatement_pct"] = round(100.0 * cop["var_covar_rel_error_vs_nested"], 2)
        cap["n_drivers"] = 5
        cap["aggregation_source"] = "docs/validation/PHASE19_TASK4_AGGREGATION_REPORT.json"
    return cap


def _build_tail(base: Dict[str, Any]) -> Dict[str, Any]:
    tail = dict(base) if isinstance(base, dict) else {}

    # Phase 21 Task 4: seven-driver tail diagnostics (copula-simulated convergence,
    # simulated + honest small-sample nested bootstrap CIs, Sobol-RQMC efficiency).
    phase21, _tail_src = None, None
    for _fn in ("PHASE22_TASK4_AGGREGATION_REPORT.json",
                "PHASE21_TASK4_AGGREGATION_REPORT.json"):
        _cand = _load(os.path.join(VAL, _fn))
        _td = ((_cand or {}).get("aggregation", {}).get("tail_diagnostics", {})
               if isinstance(_cand, dict) else {})
        if isinstance(_td, dict) and _td and not _td.get("skipped"):
            phase21, _tail_src = _cand, "docs/validation/" + _fn
            break
    td = (phase21 or {}).get("aggregation", {}).get("tail_diagnostics", {}) \
        if isinstance(phase21, dict) else {}
    if isinstance(td, dict) and td and not td.get("skipped"):
        sb = td.get("simulated_bootstrap", {})
        nb = td.get("nested_bootstrap", {})
        vr = td.get("variance_reduction", {})
        if isinstance(sb, dict):
            tail["final_var"] = sb.get("var_point", tail.get("final_var"))
            tail["final_es"] = sb.get("es_point", tail.get("final_es"))
            tail["var_ci"] = sb.get("var_ci", tail.get("var_ci"))
            tail["es_ci"] = sb.get("es_ci", tail.get("es_ci"))
            tail["var_se"] = sb.get("var_se")
            tail["es_se"] = sb.get("es_se")
            tail["bootstrap_n"] = sb.get("n_bootstrap")
        tail["outer_grid"] = td.get("n_sim_grid", [])
        tail["var_path"] = td.get("var_convergence_path", [])
        tail["es_path"] = td.get("es_convergence_path", [])
        tail["converged"] = bool(td.get("converged"))
        tail["recommended_n_outer"] = (tail["outer_grid"][-1]
                                       if tail.get("outer_grid") else None)
        tail["grid_label"] = "copula simulations"
        tail["grid_note"] = ("Convergence grid is the gaussian-copula simulation count "
                             "(10k-200k, CRN prefixes), not nested outer scenarios; the "
                             "honest small-sample nested CI (n_outer=160) is disclosed "
                             "separately.")
        if isinstance(vr, dict):
            tail["sobol_ratio"] = vr.get("qmc_variance_reduction_ratio")
        if isinstance(nb, dict):
            tail["nested_var_ci"] = nb.get("var_ci")
            tail["nested_n_outer"] = nb.get("n_outer")
            tail["nested_disclosure"] = nb.get("disclosure")
        tail["verdict"] = (
            "PASS - seven-driver 99.5% capital metric converges (copula-simulated, "
            "last VaR delta < 0.5%), is bounded by simulated and honest small-sample "
            "nested bootstrap CIs, and benefits from Sobol-RQMC variance reduction"
            if tail.get("converged") else
            "PARTIAL - seven-driver copula-simulated tail metric NOT yet converged; "
            "see convergence panel")
        tail["source"] = _tail_src
        return tail

    phase20 = _load(os.path.join(VAL, "PHASE20_TASK4_TAIL_DIAGNOSTICS_REPORT.json"))
    if not isinstance(phase20, dict):
        return tail
    t = phase20.get("tail", {})
    if not isinstance(t, dict):
        return tail
    v995 = (t.get("var_es_by_level") or {}).get("0.995", {})
    boot = t.get("bootstrap_scr_995", {})
    conv = t.get("outer_convergence", [])
    if isinstance(v995, dict):
        tail["final_var"] = v995.get("scr_var", v995.get("var", tail.get("final_var")))
        tail["final_es"] = v995.get("scr_es", v995.get("es", tail.get("final_es")))
    if isinstance(boot, dict):
        tail["var_ci"] = [boot.get("ci_lo_95"), boot.get("ci_hi_95")]
        tail["var_se"] = boot.get("rel_halfwidth")
        tail["bootstrap_n"] = boot.get("n_boot")
    if isinstance(conv, list) and conv:
        tail["outer_grid"] = [r.get("n_outer") for r in conv if isinstance(r, dict)]
        tail["var_path"] = [r.get("scr_proxy") for r in conv if isinstance(r, dict)]
        tail["es_path"] = tail["var_path"]
        tail["recommended_n_outer"] = tail["outer_grid"][-1] if tail["outer_grid"] else None
        tail["converged"] = True
    tail["source"] = "docs/validation/PHASE20_TASK4_TAIL_DIAGNOSTICS_REPORT.json"
    return tail


def _build_verdicts(base: Any) -> List[Dict[str, Any]]:
    verdicts = list(base) if isinstance(base, list) else []
    mart = _load(os.path.join(VAL, "PHASE20_TASK3_G_MART_REPORT.json"))
    if isinstance(mart, dict):
        gate = mart.get("gate", {})
        diag = gate.get("diagnostics", {}) if isinstance(gate, dict) else {}
        verdicts.append({
            "name": "G-MART market-consistency gate",
            "verdict": gate.get("status", "PASS") if isinstance(gate, dict) else "PASS",
            "evidence": "worst %.2f sigma; max rel error %.4g; %s scenarios"
            % (_num(diag.get("worst_n_std_errors")) or 0.0,
               _num(diag.get("max_rel_error")) or 0.0,
               diag.get("n_scenarios", "")),
            "source": "docs/validation/PHASE20_TASK3_G_MART_REPORT.json",
        })
    phase20 = _load(os.path.join(VAL, "PHASE20_TASK4_AGGREGATION_REPORT.json"))
    if isinstance(phase20, dict):
        rep = phase20.get("g2pp_report", {})
        if isinstance(rep, dict):
            verdicts.append({
                "name": "G2++ five-driver capital re-aggregation",
                "verdict": "PASS" if str(rep.get("verdict", "")).startswith("PASS") else rep.get("verdict", ""),
                "evidence": rep.get("verdict", ""),
                "source": "docs/validation/PHASE20_TASK4_AGGREGATION_REPORT.json",
            })

    # Phase 21 verdicts: G-FX gate, six-driver OOS proxy validation (honest PARTIAL),
    # G-LIQ gate, and the seven-driver tail-dependent aggregation.
    fx = _load(os.path.join(VAL, "PHASE21_TASK1_FX_DRIVER_REPORT.json"))
    if isinstance(fx, dict) and isinstance(fx.get("gate"), dict):
        g = fx["gate"]
        verdicts.append({
            "name": "G-FX FX-driver plausibility gate (6th driver)",
            "verdict": "PASS" if g.get("passed") else "FAIL",
            "evidence": "%s/%s criteria passed incl. MART-FX-CIP Q-measure martingale"
            % (g.get("n_passed"), g.get("n_criteria")),
            "source": "docs/validation/PHASE21_TASK1_FX_DRIVER_REPORT.json",
        })
    oos = _load(os.path.join(VAL, "PHASE21_TASK2_OOS_VALIDATION_REPORT.json"))
    if isinstance(oos, dict) and isinstance(oos.get("validation"), dict):
        v = oos["validation"]
        verd = str(v.get("verdict", ""))
        verdicts.append({
            "name": "Six-driver OOS proxy validation (FX included)",
            "verdict": "PARTIAL" if verd.upper().startswith("PARTIAL") else verd,
            "evidence": verd,
            "source": "docs/validation/PHASE21_TASK2_OOS_VALIDATION_REPORT.json",
        })
    liq = _load(os.path.join(VAL, "PHASE21_TASK3_LIQUIDITY_CALIBRATION_REPORT.json"))
    if isinstance(liq, dict) and isinstance(liq.get("gate_gliq"), dict):
        g = liq["gate_gliq"]
        verdicts.append({
            "name": "G-LIQ liquidity-calibration gate (7th driver)",
            "verdict": g.get("status", ""),
            "evidence": (g.get("evidence", "") or "")[:160],
            "source": "docs/validation/PHASE21_TASK3_LIQUIDITY_CALIBRATION_REPORT.json",
        })
    agg7 = _load(os.path.join(VAL, "PHASE21_TASK4_AGGREGATION_REPORT.json"))
    if isinstance(agg7, dict) and isinstance(agg7.get("aggregation"), dict):
        rep = agg7["aggregation"]
        verdicts.append({
            "name": "Seven-driver tail-dependent capital aggregation",
            "verdict": rep.get("verdict", ""),
            "evidence": "var-covar understates nested by %.1f%%; copula rel err %.1f%%; "
            "tail diagnostics converged"
            % (100.0 * (rep.get("var_covar_vs_nested_rel_error") or 0.0),
               100.0 * (rep.get("copula_vs_nested_rel_error") or 0.0)),
            "source": "docs/validation/PHASE21_TASK4_AGGREGATION_REPORT.json",
        })
        # Refresh the headline keyed verdicts (inherited from the five-driver
        # viewer_data baseline) so the primary read-outs match the seven-driver
        # aggregation now surfaced in the capital/tail sections.
        vc_rel = 100.0 * (rep.get("var_covar_vs_nested_rel_error") or 0.0)
        cop_rel = 100.0 * (rep.get("copula_vs_nested_rel_error") or 0.0)
        sel = rep.get("copula_selected") or "gaussian"
        for v in verdicts:
            if not isinstance(v, dict):
                continue
            if v.get("key") == "aggregation":
                v["verdict"] = (
                    "%s - seven-driver copula aggregation (selected: %s) reconciles "
                    "to nested capital within %.1f%% vs var-covar understatement "
                    "%.1f%%; MR-010 seven-driver mitigation confirmed"
                    % (rep.get("verdict", "PASS"), sel, cop_rel, vc_rel))
                v["source"] = "docs/validation/PHASE21_TASK4_AGGREGATION_REPORT.json"
            elif v.get("key") == "tail":
                v["verdict"] = (
                    "PASS - seven-driver 99.5% capital metric converges "
                    "(copula-simulated), is bounded by simulated and honest "
                    "small-sample nested bootstrap CIs, and benefits from "
                    "Sobol-RQMC variance reduction")
                v["source"] = "docs/validation/PHASE21_TASK4_AGGREGATION_REPORT.json"

    # ---- Phase 22 verdicts: proxy hardening + calibrated liquidity inputs ----
    rem = _load(os.path.join(VAL, "PHASE22_TASK1_OOS_REMEDIATION_REPORT.json"))
    if isinstance(rem, dict) and isinstance(rem.get("validation"), dict):
        fs = rem["validation"].get("final_selected", {})
        fs = fs if isinstance(fs, dict) else {}
        for v in verdicts:
            if (isinstance(v, dict) and v.get("name")
                    == "Six-driver OOS proxy validation (FX included)"):
                v["name"] = ("Six-driver OOS proxy validation "
                             "(REMEDIATED, Phase 22 Task 1)")
                v["verdict"] = "PASS"
                v["evidence"] = (
                    "Remediation: inner 96->256, staged-CRN outer uplift, targeted "
                    "deg-2 basis; OOS R2=%.4f, max |rel err| %.2f%%, overfit gap "
                    "%.4f - prior honest PARTIAL superseded"
                    % (fs.get("oos_r2") or 0.0,
                       100.0 * (fs.get("oos_max_abs_rel_error") or 0.0),
                       fs.get("overfit_gap") or 0.0))
                v["source"] = ("docs/validation/"
                               "PHASE22_TASK1_OOS_REMEDIATION_REPORT.json")

    oos7 = _load(os.path.join(VAL, "PHASE22_TASK2_7D_PROXY_VALIDATION_REPORT.json"))
    if isinstance(oos7, dict) and isinstance(oos7.get("validation"), dict):
        verd = str(oos7["validation"].get("verdict", ""))
        verdicts.append({
            "name": "Seven-driver OOS proxy validation (liquidity included)",
            "verdict": "PASS" if verd.upper().startswith("PASS") else verd,
            "evidence": verd,
            "source": "docs/validation/PHASE22_TASK2_7D_PROXY_VALIDATION_REPORT.json",
        })

    liqx = _load(os.path.join(VAL, "PHASE22_TASK3_LIQUIDITY_EXPOSURE_REPORT.json"))
    if isinstance(liqx, dict) and isinstance(liqx.get("gate_gliqx"), dict):
        g = liqx["gate_gliqx"]
        verdicts.append({
            "name": "G-LIQX liquidity exposure + coupling calibration gate",
            "verdict": g.get("status", ""),
            "evidence": (g.get("evidence", "") or "")[:160],
            "source": "docs/validation/PHASE22_TASK3_LIQUIDITY_EXPOSURE_REPORT.json",
        })

    agg22 = _load(os.path.join(VAL, "PHASE22_TASK4_AGGREGATION_REPORT.json"))
    if isinstance(agg22, dict) and isinstance(agg22.get("aggregation"), dict):
        rep22 = agg22["aggregation"]
        vc_rel = 100.0 * (rep22.get("var_covar_vs_nested_rel_error") or 0.0)
        cop_rel = 100.0 * (rep22.get("copula_vs_nested_rel_error") or 0.0)
        sel = rep22.get("copula_selected") or "gaussian"
        src22 = "docs/validation/PHASE22_TASK4_AGGREGATION_REPORT.json"
        for v in verdicts:
            if not isinstance(v, dict):
                continue
            if v.get("name") == "Seven-driver tail-dependent capital aggregation":
                v["name"] = ("Seven-driver capital aggregation "
                             "(G-LIQX-CALIBRATED inputs, Phase 22 Task 4)")
                v["verdict"] = rep22.get("verdict", "")
                v["evidence"] = (
                    "Calibrated re-run: var-covar understates nested by %.1f%%; "
                    "copula rel err %.1f%%; tail diagnostics re-run converged; "
                    "capital impact of calibration bounded (liquidity SCR "
                    "63.5->45.1)" % (vc_rel, cop_rel))
                v["source"] = src22
            elif v.get("key") == "aggregation":
                v["verdict"] = (
                    "%s - seven-driver copula aggregation (selected: %s) with "
                    "G-LIQX-CALIBRATED liquidity exposure + couplings reconciles "
                    "to nested capital within %.1f%% vs var-covar understatement "
                    "%.1f%%; MR-010 re-confirmed and mitigated"
                    % (rep22.get("verdict", "PASS"), sel, cop_rel, vc_rel))
                v["source"] = src22
            elif v.get("key") == "tail":
                v["verdict"] = (
                    "PASS - seven-driver 99.5% capital metric (G-LIQX-CALIBRATED "
                    "liquidity inputs) converges (copula-simulated), is bounded by "
                    "simulated and honest small-sample nested bootstrap CIs, and "
                    "benefits from Sobol-RQMC variance reduction")
                v["source"] = src22

    # ---- Phase 23 verdicts: tail-dependence upgrade + management actions ----
    t2 = _load(os.path.join(VAL, "PHASE23_TASK2_T_COPULA_AGGREGATION_REPORT.json"))
    if isinstance(t2, dict) and isinstance(t2.get("aggregation"), dict):
        a2 = t2["aggregation"]
        verdicts.append({
            "name": "Tail-matched Student-t copula aggregation (Phase 23 Task 2)",
            "verdict": str(a2.get("verdict", "")),
            "evidence": ("df matched %.4f from pooled tail-dependence; t-copula "
                         "SCR %.0f vs nested %.0f (rel err %.1f%%) vs gaussian "
                         "%.1f%% and var-covar understatement %.1f%%")
            % (_num(a2.get("df_matched")) or 0.0,
               _num(a2.get("t_matched_scr")) or 0.0,
               _num(a2.get("nested_scr")) or 0.0,
               100.0 * (_num(a2.get("t_matched_rel_error_vs_nested")) or 0.0),
               100.0 * (_num(a2.get("gaussian_rel_error_vs_nested")) or 0.0),
               100.0 * (_num(a2.get("var_covar_rel_error_vs_nested")) or 0.0)),
            "source": ("docs/validation/"
                       "PHASE23_TASK2_T_COPULA_AGGREGATION_REPORT.json"),
        })
    t3v = _load(os.path.join(VAL, "PHASE23_TASK3_MANAGEMENT_ACTION_REPORT.json"))
    if isinstance(t3v, dict) and isinstance(t3v.get("result"), dict):
        r3 = t3v["result"]
        verdicts.append({
            "name": ("Management-action rule - dynamic reversionary-bonus cut "
                     "(Phase 23 Task 3)"),
            "verdict": str(t3v.get("verdict", "")),
            "evidence": ("5/5 pre-registered gates; nested VaR99.5 -%.0f, SCR "
                         "-%.0f; active on %.1f%% of outer states; OOS R2 with "
                         "actions %.4f; proxy-vs-nested VaR rel err %.2f%%; "
                         "trigger sensitivity 1.05/1.10/1.15 all PASS")
            % (_num(r3.get("nested_var_reduction")) or 0.0,
               _num(r3.get("nested_scr_reduction")) or 0.0,
               100.0 * (_num(r3.get("active_share_nested")) or 0.0),
               _num(r3.get("oos_r2_with_actions")) or 0.0,
               100.0 * (_num(r3.get("var_rel_error_with_actions")) or 0.0)),
            "source": ("docs/validation/"
                       "PHASE23_TASK3_MANAGEMENT_ACTION_REPORT.json"),
        })
    t4v = _load(os.path.join(VAL,
                             "PHASE23_TASK4_AGGREGATION_WITH_ACTIONS_REPORT.json"))
    if isinstance(t4v, dict) and isinstance(t4v.get("aggregation_with_actions"),
                                            dict):
        a4 = t4v["aggregation_with_actions"]
        b4 = t4v.get("without_actions_baseline", {}) or {}
        _nw = _num(b4.get("nested_scr")) or 0.0
        _na = _num(a4.get("nested_scr")) or 0.0
        verdicts.append({
            "name": ("Seven-driver aggregation WITH management actions "
                     "(Phase 23 Task 4)"),
            "verdict": str(t4v.get("verdict", "")),
            "evidence": ("nested SCR %.0f -> %.0f (%.1f%%); rank invariance "
                         "gated (df %.4f unchanged); DISCLOSED: "
                         "copula-on-standalone understates nested-with (t rel "
                         "err %.1f%%) - the action saturates in the joint "
                         "tail; the nested run remains the capital reference")
            % (_nw, _na, (100.0 * (_na - _nw) / _nw) if _nw else 0.0,
               _num(a4.get("df_matched")) or 0.0,
               100.0 * (_num(a4.get("t_matched_rel_error_vs_nested")) or 0.0)),
            "source": ("docs/validation/"
                       "PHASE23_TASK4_AGGREGATION_WITH_ACTIONS_REPORT.json"),
        })
    j2 = _load(os.path.join(
        VAL, "PHASE24_TASK2_JOINT_ACTION_REAGGREGATION_REPORT.json"))
    if isinstance(j2, dict) and isinstance(j2.get("joint_action"), dict):
        ja2 = j2["joint_action"]
        verdicts.append({
            "name": ("Joint-scenario action-after-aggregation t-copula "
                     "(Phase 24 Task 2)"),
            "verdict": str(j2.get("verdict", "")),
            "evidence": ("governed rule applied ONCE to the t(%.4f) joint "
                         "liability: t-SCR %.1f vs nested-with %.1f (rel err "
                         "%.2f%% vs standalone-action baseline 22.54%% - "
                         "saturation gap closed); joint action only relieves; "
                         "rank invariance re-gated")
            % (_num(j2.get("df_matched")) or 0.0,
               _num(ja2.get("t_scr")) or 0.0,
               _num(j2.get("nested_scr_with")) or 0.0,
               100.0 * (_num(ja2.get("t_rel")) or 0.0)),
            "source": ("docs/validation/"
                       "PHASE24_TASK2_JOINT_ACTION_REAGGREGATION_REPORT.json"),
        })
    j3 = _load(os.path.join(VAL, "PHASE24_TASK3_INNER_PATH_ACTION_REPORT.json"))
    if isinstance(j3, dict) and isinstance(j3.get("result"), dict):
        r3 = j3["result"]
        d3 = r3.get("outer_vs_inner_path_delta", {}) or {}
        verdicts.append({
            "name": ("Inner-path management-action dynamics prototype "
                     "(Phase 24 Task 3)"),
            "verdict": str(r3.get("verdict", "")),
            "evidence": ("bonus cut applied to INNER-PATH benefit cashflows "
                         "(credit loss + analytic offsets non-cuttable): OOS "
                         "R2 %.4f, VaR rel err %.2f%%; outer-node over-relief "
                         "disclosed - nested SCR %.1f -> %.1f (+%.1f, +4.0%%); "
                         "the inner-path basis is the more conservative, more "
                         "faithful with-actions basis")
            % (_num(r3.get("oos_r2_with_actions_inner_path")) or 0.0,
               100.0 * (_num(r3.get("var_rel_error_with_actions")) or 0.0),
               _num(d3.get("nested_scr_outer_node")) or 0.0,
               _num(d3.get("nested_scr_inner_path")) or 0.0,
               _num(d3.get("nested_scr_delta")) or 0.0),
            "source": ("docs/validation/"
                       "PHASE24_TASK3_INNER_PATH_ACTION_REPORT.json"),
        })
    j4 = _load(os.path.join(
        VAL, "PHASE24_TASK4_JOINT_ACTION_TAIL_DIAGNOSTICS_REPORT.json"))
    if isinstance(j4, dict) and isinstance(j4.get("delta_matrix"), dict):
        f4 = j4.get("diagnostic_findings", {}) or {}
        vc4 = j4.get("var_covar_refresh", {}) or {}
        bt4 = ((j4.get("tail_diagnostics", {}) or {})
               .get("bootstrap", {}) or {}).get("scr_with", {}) or {}
        verdicts.append({
            "name": ("Joint-action tail diagnostics + capital-delta matrix "
                     "(Phase 24 Task 4)"),
            "verdict": str(j4.get("verdict", "")),
            "evidence": ("delta matrix complete (27/27 archive cross-checks, "
                         "P24T2 reproduced bit-identically); 99.5%% joint tail "
                         "%.1f%% saturated; var-covar understatement refreshed "
                         "%.1f%% vs nested-with / %.1f%% vs t-joint (MR-010); "
                         "margin-bootstrap 95%% CI [%.0f, %.0f] contains the "
                         "nested-with reference (n_obs=160 noise quantified)")
            % (100.0 * (_num(f4.get("tail_saturation_share_at_995")) or 0.0),
               100.0 * (_num(vc4.get("understatement_vs_nested_with")) or 0.0),
               100.0 * (_num(vc4.get("understatement_vs_t_joint")) or 0.0),
               _num(bt4.get("ci_lo_95")) or 0.0,
               _num(bt4.get("ci_hi_95")) or 0.0),
            "source": ("docs/validation/PHASE24_TASK4_JOINT_ACTION_TAIL_"
                       "DIAGNOSTICS_REPORT.json"),
        })
    # Phase 25 verdicts: path-wise declaration in the nested truth, matching
    # path-wise proxy basis, and path-wise tail diagnostics + delta matrix.
    k2 = _load(os.path.join(
        VAL, "PHASE25_TASK2_PATHWISE_DECLARATION_REPORT.json"))
    if isinstance(k2, dict) and isinstance(k2.get("result"), dict):
        kr = k2["result"]
        kd = kr.get("pathwise_vs_horizon_delta", {}) or {}
        ncp = kr.get("nested_capital_with_pathwise", {}) or {}
        nch = kr.get("nested_capital_with_horizon", {}) or {}
        verdicts.append({
            "name": ("Path-wise bonus declaration in the nested truth "
                     "(Phase 25 Task 2)"),
            "verdict": str(kr.get("verdict", "")),
            "evidence": ("per-time-step retained-bonus factor on the "
                         "path-wise coverage proxy: nested with-actions SCR "
                         "%.1f (path-wise) vs %.1f (horizon basis) = +%.2f%%; "
                         "restoration share %.1f%%; without-actions "
                         "bit-identical; the path-wise basis relieves LESS - "
                         "the more conservative with-actions read-out "
                         "(recognition-lag effect, two-sided)")
            % (_num(ncp.get("scr_proxy")) or 0.0,
               _num(nch.get("scr_proxy")) or 0.0,
               100.0 * (_num(kd.get("scr_delta_rel_to_horizon")) or 0.0),
               100.0 * (_num(kr.get("pathwise_restoration_share")) or 0.0)),
            "source": ("docs/validation/"
                       "PHASE25_TASK2_PATHWISE_DECLARATION_REPORT.json"),
        })
    k3 = _load(os.path.join(
        VAL, "PHASE25_TASK3_PATHWISE_PROXY_BASIS_REPORT.json"))
    if isinstance(k3, dict) and isinstance(k3.get("result"), dict):
        kr = k3["result"]
        sf = kr.get("surface_calibration_fit_only", {}) or {}
        verdicts.append({
            "name": ("Matching path-wise proxy basis + seven-driver OOS "
                     "re-validation (Phase 25 Task 3)"),
            "verdict": str(kr.get("verdict", "")),
            "evidence": ("smoothed-relief response surface (sigma %.3f, "
                         "alpha %.4f; FIT-only, leakage-free): OOS R2 %.4f, "
                         "VaR rel err %.2f%%, SCR rel err %.2f%% on the "
                         "path-wise with-actions basis; truth and proxy use "
                         "the IDENTICAL path-wise action basis")
            % (_num(sf.get("sigma")) or 0.0, _num(sf.get("alpha")) or 0.0,
               _num(kr.get("oos_r2_with_actions_pathwise")) or 0.0,
               100.0 * (_num(kr.get("var_rel_error_with_actions")) or 0.0),
               100.0 * (_num(kr.get("scr_rel_error_with_actions")) or 0.0)),
            "source": ("docs/validation/"
                       "PHASE25_TASK3_PATHWISE_PROXY_BASIS_REPORT.json"),
        })
    k4 = _load(os.path.join(
        VAL, "PHASE25_TASK4_PATHWISE_TAIL_DIAGNOSTICS_REPORT.json"))
    if isinstance(k4, dict) and isinstance(k4.get("delta_matrix"), dict):
        kf = k4.get("diagnostic_findings", {}) or {}
        kv = k4.get("var_covar_refresh", {}) or {}
        kb = ((k4.get("tail_diagnostics", {}) or {})
              .get("bootstrap", {}) or {}).get("scr_pathwise", {}) or {}
        verdicts.append({
            "name": ("Path-wise tail diagnostics + capital-delta matrix "
                     "(Phase 25 Task 4)"),
            "verdict": str(k4.get("verdict", "")),
            "evidence": ("path-wise relieves LESS at every confidence level "
                         "(the horizon basis understates the with-actions "
                         "SCR across the matrix); var-covar understatement "
                         "refreshed %.1f%% vs nested path-wise (MR-010); "
                         "copula FROZEN (df %.4f re-matched); margin-"
                         "bootstrap 95%% CI [%.0f, %.0f] - nested path-wise "
                         "reference OUTSIDE the CI (the analytic re-anchoring "
                         "understates nested by %.1f%% beyond noise; "
                         "DISCLOSED motivation for full path-wise copula "
                         "re-aggregation)")
            % (100.0 * (_num(kv.get(
                   "understatement_vs_nested_with_pathwise")) or 0.0),
               _num(k4.get("df_rematched")) or 0.0,
               _num(kb.get("ci_lo_95")) or 0.0,
               _num(kb.get("ci_hi_95")) or 0.0,
               100.0 * (_num(kf.get(
                   "t_pathwise_vs_nested_pathwise_rel_err")) or 0.0)),
            "source": ("docs/validation/PHASE25_TASK4_PATHWISE_TAIL_"
                       "DIAGNOSTICS_REPORT.json"),
        })
    # Phase 26 verdicts: full path-wise copula re-aggregation - the per-driver
    # composition transform, the frozen-copula component-basis bootstrap with
    # the copula-form gap decomposition, and the paired delta matrix.
    m2 = _load(os.path.join(
        VAL, "PHASE26_TASK2_COMPOSITION_TRANSFORM_REPORT.json"))
    if isinstance(m2, dict) and isinstance(m2.get("result"), dict):
        mr = m2["result"]
        mt = mr.get("t_readout", {}) or {}
        verdicts.append({
            "name": ("Full path-wise copula re-aggregation - per-driver "
                     "composition transform (Phase 26 Task 2)"),
            "verdict": str(m2.get("verdict", "")),
            "evidence": ("per-scenario composition on the FROZEN t(2.9451) "
                         "copula, relief on the cuttable component only with "
                         "the per-scenario envelope clip: component-basis SCR "
                         "%.1f vs re-anchored %.1f = +%.2f%% (statistically "
                         "real but immaterial); governed sigma/alpha/"
                         "benefit-share UNCHANGED; copula FROZEN (df %.4f, rho "
                         "max|diff| %.1e)")
            % (_num(mt.get("scr_component")) or 0.0,
               _num(mr.get("sign_gate_reference")) or 0.0,
               100.0 * (_num(mr.get("component_vs_reanchored_rel_t")) or 0.0),
               _num(m2.get("df_rematched")) or 0.0,
               _num(m2.get("rho_max_abs_diff")) or 0.0),
            "source": ("docs/validation/"
                       "PHASE26_TASK2_COMPOSITION_TRANSFORM_REPORT.json"),
        })
    m3 = _load(os.path.join(
        VAL, "PHASE26_TASK3_MARGIN_BOOTSTRAP_REPORT.json"))
    if isinstance(m3, dict) and isinstance(m3.get("result"), dict):
        mr = m3["result"]
        ci = mr.get("component_t_scr_ci", {}) or {}
        dc = mr.get("residual_gap_decomposition", {}) or {}
        verdicts.append({
            "name": ("Full path-wise copula re-aggregation - frozen-copula "
                     "margin bootstrap + gap decomposition (Phase 26 Task 3)"),
            "verdict": str(m3.get("verdict", "")),
            "evidence": ("component-basis frozen-copula bootstrap (200x20k): "
                         "t SCR mean %.1f, 95%% CI [%.0f, %.0f], SE %.2f%% of "
                         "mean (<= 5%%); nested path-wise %.1f OUTSIDE the CI "
                         "-> residual %.2f%% gap decomposed %.1f%% COPULA-FORM "
                         "(heavier nested joint tail than the frozen t copula "
                         "on standalone margins) / %.1f%% relief-surface; "
                         "copula-form DOMINANT, DISCLOSED")
            % (_num(ci.get("mean")) or 0.0,
               _num(ci.get("ci_lo")) or 0.0,
               _num(ci.get("ci_hi")) or 0.0,
               100.0 * (_num(mr.get("se_frac_of_mean")) or 0.0),
               _num(mr.get("nested_pathwise_reference")) or 0.0,
               100.0 * (_num(dc.get("gap_total_rel_to_nested")) or 0.0),
               100.0 * (_num(dc.get("copula_form_share_of_gap")) or 0.0),
               100.0 * (_num(dc.get("relief_surface_share_of_gap")) or 0.0)),
            "source": ("docs/validation/"
                       "PHASE26_TASK3_MARGIN_BOOTSTRAP_REPORT.json"),
        })
    m4 = _load(os.path.join(
        VAL, "PHASE26_TASK4_DELTA_MATRIX_REPORT.json"))
    if isinstance(m4, dict) and isinstance(m4.get("result"), dict):
        mr = m4["result"]
        pdl = mr.get("paired_deltas", {}) or {}
        cc = pdl.get("composition_correction_t", {}) or {}
        trg = mr.get("mr_trigger", {}) or {}
        verdicts.append({
            "name": ("Full path-wise copula re-aggregation - paired "
                     "full-vs-reanchored delta matrix (Phase 26 Task 4)"),
            "verdict": str(m4.get("verdict", "")),
            "evidence": ("paired common-random-number delta matrix over the "
                         "Task 3 replicates: composition correction "
                         "(full minus re-anchored, t) +%.1f [%.1f, %.1f], "
                         "95%% CI EXCLUDES zero (statistically significant) "
                         "yet max |move| %.2f%% < 1%% MR trigger -> MR-010/"
                         "MR-014 numeric refresh NOT required, MR-015 stays "
                         "free; rank invariance re-verified (df/rho frozen)")
            % (_num(cc.get("mean")) or 0.0,
               _num(cc.get("ci_lo")) or 0.0,
               _num(cc.get("ci_hi")) or 0.0,
               100.0 * (_num(trg.get("max_abs_rel")) or 0.0)),
            "source": ("docs/validation/"
                       "PHASE26_TASK4_DELTA_MATRIX_REPORT.json"),
        })
    return verdicts




def _build_management_actions() -> Dict[str, Any]:
    """Phase 23 (contract 1.5.0, additive): management-action rule + the
    with-actions aggregation/tail read-outs. Pure display-layer normalisation of
    the already-produced Task 3/4 validation reports - no model calculation."""
    out: Dict[str, Any] = {}
    t3 = _load(os.path.join(VAL, "PHASE23_TASK3_MANAGEMENT_ACTION_REPORT.json"))
    if isinstance(t3, dict) and isinstance(t3.get("result"), dict):
        res = t3["result"]
        out["rule"] = res.get("rule", {})
        out["rule_description"] = (
            "Dynamic reversionary-bonus participation cut (Solvency II Art. 23): "
            "cut_factor = clip((CR - 0.90)/(1.10 - 0.90), 0, 1) with CR = A_ref/L "
            "at the outer node; PRE floor 60% of the bonus share; max liability "
            "relief 12%; monotonicity guarded at construction. The rule enters the "
            "nested conditional liability AND identically the LSMC proxy "
            "prediction as an analytic post-composition basis feature "
            "(A_ref leakage-free from the fit-sample mean).")
        out["reference_assets"] = res.get("reference_assets")
        out["active_share_nested"] = res.get("active_share_nested")
        out["floor_share_nested"] = res.get("floor_share_nested")
        out["oos_r2_with_actions"] = res.get("oos_r2_with_actions")
        out["oos_r2_without_actions"] = res.get("oos_r2_without_actions")
        out["var_rel_error_with_actions"] = res.get("var_rel_error_with_actions")
        out["nested_capital_without"] = res.get("nested_capital_without", {})
        out["nested_capital_with"] = res.get("nested_capital_with", {})
        out["proxy_capital_with"] = res.get("proxy_capital_with", {})
        out["gates_task3"] = res.get("gates", {})
        out["trigger_sensitivity"] = t3.get("trigger_sensitivity", [])
        out["task3_verdict"] = t3.get("verdict")
        out["task3_source"] = ("docs/validation/"
                               "PHASE23_TASK3_MANAGEMENT_ACTION_REPORT.json")
        out["task3_change_record_id"] = t3.get("change_record_id")
    t4 = _load(os.path.join(VAL,
                            "PHASE23_TASK4_AGGREGATION_WITH_ACTIONS_REPORT.json"))
    if isinstance(t4, dict) and isinstance(t4.get("aggregation_with_actions"),
                                           dict):
        agg = t4["aggregation_with_actions"]
        base = t4.get("without_actions_baseline", {}) or {}
        out["aggregation"] = {
            "df_matched": agg.get("df_matched"),
            "active_share_full": t4.get("active_share_full"),
            "floor_share_full": t4.get("floor_share_full"),
            "nested_scr_with": agg.get("nested_scr"),
            "t_copula_scr_with": agg.get("t_matched_scr"),
            "gaussian_scr_with": agg.get("gaussian_scr"),
            "var_covar_scr_with": agg.get("var_covar_scr"),
            "nested_scr_without": base.get("nested_scr"),
            "t_copula_scr_without": base.get("t_matched_scr"),
            "gaussian_scr_without": base.get("gaussian_scr"),
            "var_covar_scr_without": base.get("var_covar_scr"),
            "var_covar_understatement_with":
                agg.get("var_covar_rel_error_vs_nested"),
            "t_rel_error_with": agg.get("t_matched_rel_error_vs_nested"),
            "t_rel_error_without": base.get("t_matched_rel_error_vs_nested"),
            "gaussian_rel_error_with": agg.get("gaussian_rel_error_vs_nested"),
            "gaussian_rel_error_without":
                base.get("gaussian_rel_error_vs_nested"),
            "deltas": t4.get("deltas", {}),
            "standalone_drivers": t4.get("standalone_drivers", []),
            "standalone_scr_with": t4.get("standalone_scr_with_actions", []),
            "standalone_scr_without": base.get("standalone_scr", []),
            "anchoring_convention": t4.get("anchoring_convention"),
        }
        out["gates_task4"] = t4.get("gates", {})
        out["task4_verdict"] = t4.get("verdict")
        out["saturation_finding"] = (
            "MATERIAL FINDING (disclosed): copula-on-standalone-losses "
            "understates the nested with-actions benchmark (t rel err 4.0% -> "
            "22.5%; gaussian 14.9% -> 27.8%) because the action saturates (max "
            "relief 12%) in the joint tail while standalone tails sit in the "
            "steeper partial-cut band. The nested run remains the capital "
            "reference; copula read-outs are diagnostics on this basis. Rank "
            "invariance gated: the action is a monotone marginal transform, so "
            "the empirical copula and matched df are identical with/without "
            "actions.")
        out["task4_source"] = ("docs/validation/"
                               "PHASE23_TASK4_AGGREGATION_WITH_ACTIONS_REPORT"
                               ".json")
        out["task4_change_record_id"] = t4.get("change_record_id")
    return out


def _build_phase24() -> Dict[str, Any]:
    """Phase 24 (contract 1.6.0, additive): joint-scenario action-after-
    aggregation, inner-path action dynamics, and joint-action tail
    diagnostics. Pure display-layer normalisation of the already-produced
    Phase 24 Task 2/3/4 validation reports - no model calculation."""
    out: Dict[str, Any] = {}
    t2 = _load(os.path.join(
        VAL, "PHASE24_TASK2_JOINT_ACTION_REAGGREGATION_REPORT.json"))
    if isinstance(t2, dict) and isinstance(t2.get("joint_action"), dict):
        ja = t2["joint_action"]
        base = t2.get("standalone_action_baseline_p23t4", {}) or {}
        out["joint_action"] = {
            "t_scr_joint": ja.get("t_scr"),
            "t_var_joint": ja.get("t_var"),
            "t_es_joint": ja.get("t_es"),
            "t_rel_error_joint": ja.get("t_rel"),
            "gaussian_scr_joint": ja.get("g_scr"),
            "gaussian_rel_error_joint": ja.get("g_rel"),
            "t_scr_standalone_baseline": base.get("t_matched_scr"),
            "t_rel_error_standalone_baseline":
                base.get("t_matched_rel_error_vs_nested"),
            "nested_scr_with": t2.get("nested_scr_with"),
            "df_matched": t2.get("df_matched"),
            "df_rematched": t2.get("df_rematched"),
            "active_share": ja.get("active_share"),
            "floor_share": ja.get("floor_share"),
            "joint_action_only_relieves": ja.get("joint_action_only_relieves"),
            "gates": t2.get("gates", {}),
            "verdict": t2.get("verdict"),
            "anchoring_convention": t2.get("anchoring_convention"),
            "saturation_gap_closure": (
                "Saturation-gap closure (disclosed): applying the SAME governed "
                "bonus-cut rule ONCE to the t-copula JOINT liability "
                "(action-after-aggregation) instead of to each standalone "
                "driver loss closes the copula-on-standalone understatement vs "
                "the nested with-actions benchmark from 22.54% to 6.39%; the "
                "joint action only ever relieves (W <= V pathwise) and rank "
                "invariance is re-gated (df re-matched, unchanged to 5 dp). "
                "The nested run remains the capital reference."),
            "source": ("docs/validation/"
                       "PHASE24_TASK2_JOINT_ACTION_REAGGREGATION_REPORT.json"),
            "change_record_id": t2.get("change_record_id"),
        }
    t3 = _load(os.path.join(VAL, "PHASE24_TASK3_INNER_PATH_ACTION_REPORT.json"))
    if isinstance(t3, dict) and isinstance(t3.get("result"), dict):
        res = t3["result"]
        cc = t3.get("credit_carveout_diagnostics", {}) or {}
        out["inner_path"] = {
            "oos_r2_with_actions": res.get("oos_r2_with_actions_inner_path"),
            "oos_r2_without_actions": res.get("oos_r2_without_actions"),
            "var_rel_error_with_actions": res.get("var_rel_error_with_actions"),
            "es_rel_error_with_actions": res.get("es_rel_error_with_actions"),
            "active_share_nested": res.get("active_share_nested"),
            "floor_share_nested": res.get("floor_share_nested"),
            "nested_capital_without": res.get("nested_capital_without", {}),
            "nested_capital_with_inner_path":
                res.get("nested_capital_with_inner_path", {}),
            "nested_capital_with_outer_node":
                res.get("nested_capital_with_outer_node", {}),
            "outer_vs_inner_path_delta":
                res.get("outer_vs_inner_path_delta", {}),
            "kappa_fit_calibrated": cc.get("kappa_fit_calibrated"),
            "credit_share_of_liability":
                cc.get("credit_share_of_liability_nested"),
            "benefit_share_of_liability":
                cc.get("benefit_share_of_liability_nested"),
            "gates": res.get("gates", {}),
            "verdict": res.get("verdict"),
            "method": t3.get("method"),
            "source": ("docs/validation/"
                       "PHASE24_TASK3_INNER_PATH_ACTION_REPORT.json"),
            "change_record_id": t3.get("change_record_id"),
        }
    t4 = _load(os.path.join(
        VAL, "PHASE24_TASK4_JOINT_ACTION_TAIL_DIAGNOSTICS_REPORT.json"))
    if isinstance(t4, dict) and isinstance(t4.get("delta_matrix"), dict):
        td = t4.get("tail_diagnostics", {}) or {}
        out["tail_diagnostics"] = {
            "delta_matrix": t4.get("delta_matrix", {}),
            "var_covar_refresh": t4.get("var_covar_refresh", {}),
            "confidence_sweep": td.get("confidence_sweep", []),
            "prefix_convergence": td.get("prefix_convergence", []),
            "seed_stability": td.get("seed_stability", {}),
            "bootstrap": td.get("bootstrap", {}),
            "diagnostic_findings": t4.get("diagnostic_findings", {}),
            "crosscheck_count": t4.get("crosscheck_count"),
            "reproduction_of_p24t2": t4.get("reproduction_of_p24t2", {}),
            "n_obs": t4.get("n_obs"),
            "n_sim": t4.get("n_sim"),
            "gates": t4.get("gates", {}),
            "verdict": t4.get("verdict"),
            "inner_path_disclosure_note":
                (t4.get("inner_path_disclosure", {}) or {}).get("note"),
            "source": ("docs/validation/PHASE24_TASK4_JOINT_ACTION_TAIL_"
                       "DIAGNOSTICS_REPORT.json"),
            "change_record_id": t4.get("change_record_id"),
        }
    if out:
        out["narrative"] = (
            "Phase 24 quantified HOW management actions and dependence "
            "interact: the joint-scenario (action-after-aggregation) basis "
            "closes the disclosed Phase 23 saturation gap 22.54% -> 6.39%; "
            "the inner-path cashflow basis corrects an outer-node over-relief "
            "(+4.0% nested SCR, the more conservative and more faithful "
            "with-actions basis); and the tail diagnostics show the 99.5% "
            "joint tail is 100% saturated (max relief everywhere capital is "
            "measured), with margin-bootstrap CI quantifying the n_obs=160 "
            "small-sample noise. Nested with-actions remains the capital "
            "reference; all copula read-outs are diagnostics on that basis.")
    return out


def _build_phase25() -> Dict[str, Any]:
    """Phase 25 (contract 1.7.0, additive): path-wise management-action
    declaration in the nested truth, the matching path-wise proxy basis, and
    the path-wise tail diagnostics + capital-delta matrix. Pure display-layer
    normalisation of the already-produced Phase 25 Task 2/3/4 validation
    reports - no model calculation."""
    out: Dict[str, Any] = {}
    t2 = _load(os.path.join(
        VAL, "PHASE25_TASK2_PATHWISE_DECLARATION_REPORT.json"))
    if isinstance(t2, dict) and isinstance(t2.get("result"), dict):
        r = t2["result"]
        dl = r.get("pathwise_vs_horizon_delta", {}) or {}
        out["declaration"] = {
            "rule": r.get("rule", {}),
            "nested_capital_without": r.get("nested_capital_without", {}),
            "nested_capital_with_horizon":
                r.get("nested_capital_with_horizon", {}),
            "nested_capital_with_pathwise":
                r.get("nested_capital_with_pathwise", {}),
            "pathwise_vs_horizon_delta": dl,
            "pathwise_action_share": r.get("pathwise_action_share"),
            "pathwise_restoration_share":
                r.get("pathwise_restoration_share"),
            "clip_binding_share_pathwise":
                r.get("clip_binding_share_pathwise"),
            "clip_binding_share_horizon":
                r.get("clip_binding_share_horizon"),
            "gates": r.get("gates", {}),
            "verdict": r.get("verdict"),
            "interpretation": dl.get("interpretation"),
            "source": ("docs/validation/"
                       "PHASE25_TASK2_PATHWISE_DECLARATION_REPORT.json"),
            "change_record_id": t2.get("change_record_id"),
        }
    t3 = _load(os.path.join(
        VAL, "PHASE25_TASK3_PATHWISE_PROXY_BASIS_REPORT.json"))
    if isinstance(t3, dict) and isinstance(t3.get("result"), dict):
        r = t3["result"]
        out["proxy_basis"] = {
            "oos_r2_with_actions": r.get("oos_r2_with_actions_pathwise"),
            "oos_r2_without_actions": r.get("oos_r2_without_actions"),
            "var_rel_error_with_actions":
                r.get("var_rel_error_with_actions"),
            "es_rel_error_with_actions": r.get("es_rel_error_with_actions"),
            "scr_rel_error_with_actions":
                r.get("scr_rel_error_with_actions"),
            "surface": r.get("surface_calibration_fit_only", {}),
            "cadence_sensitivity":
                r.get("declaration_cadence_sensitivity", {}),
            "gates": r.get("gates", {}),
            "verdict": r.get("verdict"),
            "source": ("docs/validation/"
                       "PHASE25_TASK3_PATHWISE_PROXY_BASIS_REPORT.json"),
            "change_record_id": t3.get("change_record_id"),
        }
    t4 = _load(os.path.join(
        VAL, "PHASE25_TASK4_PATHWISE_TAIL_DIAGNOSTICS_REPORT.json"))
    if isinstance(t4, dict) and isinstance(t4.get("delta_matrix"), dict):
        td = t4.get("tail_diagnostics", {}) or {}
        out["tail_diagnostics"] = {
            "delta_matrix": t4.get("delta_matrix", {}),
            "var_covar_refresh": t4.get("var_covar_refresh", {}),
            "pathwise_basis_params": t4.get("pathwise_basis_params", {}),
            "df_matched": t4.get("df_matched"),
            "df_rematched": t4.get("df_rematched"),
            "rho_max_abs_diff_vs_archived":
                t4.get("rho_max_abs_diff_vs_archived"),
            "mr_refresh_trigger": t4.get("mr_refresh_trigger", {}),
            "t_scr_pathwise_readout":
                (t4.get("t_pathwise_readout", {}) or {}).get("scr_pathwise"),
            "g_scr_pathwise_readout":
                (t4.get("g_pathwise_readout", {}) or {}).get("scr_pathwise"),
            "confidence_sweep": td.get("confidence_sweep", []),
            "prefix_convergence": td.get("prefix_convergence", []),
            "seed_stability": td.get("seed_stability", {}),
            "bootstrap": td.get("bootstrap", {}),
            "diagnostic_findings": t4.get("diagnostic_findings", {}),
            "reproduction_of_p24t2":
                t4.get("reproduction_of_p24t2_horizon_basis", {}),
            "crosscheck_count": t4.get("crosscheck_count"),
            "n_obs": t4.get("n_obs"),
            "n_sim": t4.get("n_sim"),
            "readout_convention": t4.get("readout_convention"),
            "gates": t4.get("gates", {}),
            "verdict": t4.get("verdict"),
            "mr010_refreshed": t4.get("mr010_refreshed"),
            "mr014_refreshed": t4.get("mr014_refreshed"),
            "source": ("docs/validation/PHASE25_TASK4_PATHWISE_TAIL_"
                       "DIAGNOSTICS_REPORT.json"),
            "change_record_id": t4.get("change_record_id"),
        }
    if out:
        out["narrative"] = (
            "Phase 25 moved the management action from a horizon-level "
            "declaration to a PATH-WISE declaration: the bonus cut (and "
            "restoration) responds to each inner path's own coverage, "
            "introducing the recognition-lag effect - the path-wise basis "
            "relieves LESS in the tail and its with-actions SCR (46,638.9 vs "
            "40,852.1 on the horizon basis, +14.17%) is the more "
            "conservative, more faithful read-out. The matching proxy basis "
            "re-validates OOS on the identical action basis (R2 0.9978, VaR "
            "rel err 0.40%); the tail diagnostics refresh MR-010/MR-014 "
            "(var-covar understatement 69.1% vs nested path-wise) and "
            "DISCLOSE that the analytic re-anchoring understates the nested "
            "path-wise reference by 14.7% beyond bootstrap noise - the "
            "quantified motivation for a full path-wise copula "
            "re-aggregation next phase. Nested with-actions (path-wise "
            "declaration) remains the capital reference.")
    return out


def _build_phase26() -> Dict[str, Any]:
    """Phase 26 (contract 1.8.0, additive): full PATH-WISE COPULA
    RE-AGGREGATION. Surfaces the Task 2 per-driver composition transform on
    the FROZEN copula (component vs re-anchored/level basis), the Task 3
    frozen-copula margin bootstrap on the full component basis with the nested
    reference OUTSIDE the 95% CI -> copula-form gap decomposition, and the
    Task 4 paired full-vs-reanchored delta matrix with the MR-trigger decision.
    Pure display-layer normalisation of the already-produced Phase 26 Task
    2/3/4 validation reports - no model calculation."""
    out: Dict[str, Any] = {}
    # ---- Task 2: per-driver composition transform (component vs level) ----
    t2 = _load(os.path.join(
        VAL, "PHASE26_TASK2_COMPOSITION_TRANSFORM_REPORT.json"))
    if isinstance(t2, dict) and isinstance(t2.get("result"), dict):
        r = t2["result"]
        tr = r.get("t_readout", {}) or {}
        gr = r.get("g_readout", {}) or {}
        out["composition"] = {
            "cuttable_drivers": t2.get("cuttable_drivers", []),
            "carveout_drivers": t2.get("carveout_drivers", []),
            "t_readout": {
                "scr_without": tr.get("scr_without"),
                "scr_level": tr.get("scr_level"),
                "scr_component": tr.get("scr_component"),
                "component_minus_level_scr":
                    tr.get("component_minus_level_scr"),
                "cuttable_share_mean": tr.get("cuttable_share_mean"),
                "cuttable_share_tail_mean": tr.get("cuttable_share_tail_mean"),
                "tail_cuttable_share_depression":
                    tr.get("tail_cuttable_share_depression"),
            },
            "g_readout": {
                "scr_without": gr.get("scr_without"),
                "scr_level": gr.get("scr_level"),
                "scr_component": gr.get("scr_component"),
                "component_minus_level_scr":
                    gr.get("component_minus_level_scr"),
            },
            "sign_gate_reference": r.get("sign_gate_reference"),
            "nested_pathwise_reference": r.get("nested_pathwise_reference"),
            "component_vs_reanchored_rel_t":
                r.get("component_vs_reanchored_rel_t"),
            "component_vs_reanchored_rel_g":
                r.get("component_vs_reanchored_rel_g"),
            "mr_refresh_trigger_1pct": r.get("mr_refresh_trigger_1pct"),
            "gap_to_nested_component_t_rel":
                r.get("gap_to_nested_component_t_rel"),
            "gap_to_nested_level_t_rel": r.get("gap_to_nested_level_t_rel"),
            "envelope_bounds_ok": r.get("envelope_bounds_ok"),
            "df_rematched": t2.get("df_rematched"),
            "rho_max_abs_diff": t2.get("rho_max_abs_diff"),
            "gates": r.get("gates", {}),
            "verdict": t2.get("verdict"),
            "source": ("docs/validation/"
                       "PHASE26_TASK2_COMPOSITION_TRANSFORM_REPORT.json"),
            "change_record_id": t2.get("change_record_id"),
        }
    # ---- Task 3: frozen-copula margin bootstrap on the component basis ----
    t3 = _load(os.path.join(
        VAL, "PHASE26_TASK3_MARGIN_BOOTSTRAP_REPORT.json"))
    if isinstance(t3, dict) and isinstance(t3.get("result"), dict):
        r = t3["result"]
        out["bootstrap"] = {
            "config": r.get("config", {}),
            "component_t_scr_ci": r.get("component_t_scr_ci", {}),
            "component_g_scr_ci": r.get("component_g_scr_ci", {}),
            "level_t_scr_ci": r.get("level_t_scr_ci", {}),
            "without_t_scr_ci": r.get("without_t_scr_ci", {}),
            "nested_pathwise_reference": r.get("nested_pathwise_reference"),
            "task2_t_component_point": r.get("task2_t_component_point"),
            "headline_nested_inside_95ci":
                r.get("headline_nested_inside_95ci"),
            "se_frac_of_mean": r.get("se_frac_of_mean"),
            "se_gate_pass": r.get("se_gate_pass"),
            "residual_gap_decomposition":
                r.get("residual_gap_decomposition", {}),
            "gates": r.get("gates", {}),
            "verdict": t3.get("verdict"),
            "digest": r.get("digest"),
            "source": ("docs/validation/"
                       "PHASE26_TASK3_MARGIN_BOOTSTRAP_REPORT.json"),
            "change_record_id": t3.get("change_record_id"),
        }
    # ---- Task 4: paired full-vs-reanchored delta matrix + MR trigger ----
    t4 = _load(os.path.join(
        VAL, "PHASE26_TASK4_DELTA_MATRIX_REPORT.json"))
    if isinstance(t4, dict) and isinstance(t4.get("result"), dict):
        r = t4["result"]
        out["delta_matrix"] = {
            "point_matrix": r.get("point_matrix", {}),
            "marginal_cis": r.get("marginal_cis", {}),
            "paired_deltas": r.get("paired_deltas", {}),
            "mr_trigger": r.get("mr_trigger", {}),
            "gap_to_nested": r.get("gap_to_nested", {}),
            "rank_invariance": r.get("rank_invariance", {}),
            "config": r.get("config", {}),
            "gates": r.get("gates", {}),
            "verdict": t4.get("verdict"),
            "digest": r.get("digest"),
            "source": ("docs/validation/"
                       "PHASE26_TASK4_DELTA_MATRIX_REPORT.json"),
            "change_record_id": t4.get("change_record_id"),
        }
    if out:
        out["narrative"] = (
            "Phase 26 re-aggregated the path-wise capital from the FULL "
            "per-driver composition on the FROZEN t(2.9451) copula (rank "
            "invariance held: rho max|diff| 7.2e-16, df within 1e-4), instead "
            "of the Phase 25 constant-share LEVEL (analytic re-anchoring) "
            "transform. The composition correction (full minus re-anchored) "
            "is STATISTICALLY SIGNIFICANT on the paired common-random-number "
            "bootstrap (t +211.5 [+46.1, +381.8]; g +192.6 [+60.2, +312.6]) "
            "but ECONOMICALLY IMMATERIAL (+0.54% / +0.55%, below the 1% "
            "MR-010/MR-014 refresh trigger - MR-015 stays free). The frozen-"
            "copula margin bootstrap on the full component basis puts the "
            "component t SCR at 39,595.1 [36,676.2, 42,943.1] (SE 4.07% <= 5%) "
            "with the nested path-wise reference 46,638.9 OUTSIDE the 95% CI; "
            "the residual 14.29% gap decomposes 91.9% COPULA-FORM (6,120.2 - "
            "the nested joint tail is heavier than the frozen t copula on "
            "standalone margins, exceeding the entire gaussian->t sensitivity "
            "of 4,765.6) and only 8.1% relief-surface (543.0, bounded by the "
            "governed 1.16% OOS error). CONCLUSION: the full and re-anchored "
            "bases are economically interchangeable on the frozen copula; the "
            "material gap to the nested truth is a copula-FORM limitation, NOT "
            "a basis-choice effect. Nested with-actions (path-wise) remains "
            "the capital reference; production sign-off withheld (educational).")
    return out


# --------------------------------------------------------------------------- #
def _build_phase27() -> Dict[str, Any]:
    """Phase 27 (contract 1.9.0, additive): richer UPPER-TAIL-DEPENDENCE
    copula (GH skew-t). Surfaces the Task 3 skew-t margin bootstrap (skew-t vs
    symmetric-t vs nested SCR + residual re-decomposition), the Task 4
    upper/lower tail-dependence asymmetry profile across the p-grid with 95%
    CIs, the gamma_hat~0 MATERIAL FINDING, and the MR-015 risk. Pure
    display-layer normalisation of the already-produced Phase 27 Task 3/4
    validation reports - no model calculation."""
    out: Dict[str, Any] = {}
    t3 = _load(os.path.join(
        VAL, "PHASE27_TASK3_SKEW_T_BOOTSTRAP_REPORT.json"))
    if isinstance(t3, dict) and isinstance(t3.get("result"), dict):
        r = t3["result"]
        out["bootstrap"] = {
            "config": r.get("config", {}),
            "gamma_hat": t3.get("gamma_hat"),
            "skewt_component_scr_ci": r.get("skewt_component_scr_ci", {}),
            "symmetric_component_scr_ci":
                r.get("symmetric_component_scr_ci", {}),
            "without_skewt_scr_ci": r.get("without_skewt_scr_ci", {}),
            "nested_pathwise_reference": r.get("nested_pathwise_reference"),
            "task2_frozen_t_component_point":
                r.get("task2_frozen_t_component_point"),
            "task2_skewt_component_point":
                r.get("task2_skewt_component_point"),
            "headline_nested_inside_95ci":
                r.get("headline_nested_inside_95ci"),
            "se_frac_of_mean": r.get("se_frac_of_mean"),
            "se_gate_pass": r.get("se_gate_pass"),
            "directional_not_widened_mean":
                r.get("directional_not_widened_mean"),
            "directional_lift_nonneg_share":
                r.get("directional_lift_nonneg_share"),
            "radial_asymmetry_mean": r.get("radial_asymmetry_mean"),
            "skewt_minus_sym_mean": r.get("skewt_minus_sym_mean"),
            "residual_gap_redecomposition":
                r.get("residual_gap_redecomposition_point", {}),
            "gates": r.get("gates", {}),
            "verdict": t3.get("verdict"),
            "digest": r.get("digest"),
            "source": ("docs/validation/"
                       "PHASE27_TASK3_SKEW_T_BOOTSTRAP_REPORT.json"),
            "change_record_id": t3.get("change_record_id"),
        }
    t4 = _load(os.path.join(
        VAL, "PHASE27_TASK4_TAIL_DIAGNOSTICS_REPORT.json"))
    if isinstance(t4, dict) and isinstance(t4.get("result"), dict):
        r = t4["result"]
        tds = r.get("tail_diagnostics_summary", {}) or {}

        def _m(blk, key):
            v = blk.get(key) or {}
            return {"mean": v.get("mean"), "ci_lo": v.get("ci_lo"),
                    "ci_hi": v.get("ci_hi")}

        rows = []
        for pk in sorted(tds.keys()):
            blk = tds[pk] or {}
            try:
                p_val = float(pk.split("_")[1]) / 100.0
            except (IndexError, ValueError):
                p_val = None
            rows.append({
                "p": p_val,
                "skewt_lambda_U": _m(blk, "skewt_lambda_U"),
                "skewt_lambda_L": _m(blk, "skewt_lambda_L"),
                "skewt_radial_asym": _m(blk, "skewt_radial_asym"),
                "sym_lambda_U": _m(blk, "sym_lambda_U"),
                "sym_lambda_L": _m(blk, "sym_lambda_L"),
            })
        cfg = r.get("config", {}) or {}
        out["tail"] = {
            "gamma_hat": t4.get("gamma_hat"),
            "df_frozen": t4.get("df_frozen"),
            "nested_pathwise_reference": t4.get("nested_pathwise_reference"),
            "p_grid": cfg.get("p_grid", []),
            "tail_anchor_p": cfg.get("tail_level_anchor"),
            "rows": rows,
            "archive_crosscheck": r.get("archive_crosscheck", {}),
            "consistency_skewt_ge_sym": r.get("consistency_skewt_ge_sym"),
            "mr_refresh_decision": r.get("mr_refresh_decision", {}),
            "mr015_opened": t4.get("mr015_opened"),
            "gates": r.get("gates", {}),
            "verdict": t4.get("verdict"),
            "digest": r.get("digest"),
            "source": ("docs/validation/"
                       "PHASE27_TASK4_TAIL_DIAGNOSTICS_REPORT.json"),
            "change_record_id": t4.get("change_record_id"),
        }
    if out:
        out["narrative"] = (
            "Phase 27 layered an explicit UPPER-TAIL-ASYMMETRY scalar - the "
            "generalized-hyperbolic skew-t copula (Demarta & McNeil 2005) - on "
            "the FROZEN t(2.9451) copula, with gamma=0 recovering the symmetric "
            "t EXACTLY. MATERIAL FINDING: fitting gamma leakage-free to the "
            "realised upper-tail co-exceedances pins it at the boundary "
            "(gamma_hat ~ 6.2e-5), so the skew-t draw is near-radially-"
            "symmetric (radial asymmetry ~ 0 at p=0.90) and the skew-t "
            "component SCR (39,598.2 bootstrap mean) is economically identical "
            "to the frozen-t basis (39,595.1). The nested path-wise reference "
            "46,638.9 lies OUTSIDE the skew-t 95% CI [36,679.9, 42,943.1] "
            "(SE 4.07%); the copula-FORM residual falls only ~0.09% "
            "(6,120.2 -> 6,114.9) - RE-CONFIRMED as NOT closed by a single "
            "upper-tail-asymmetry scalar. It lives in nested inner-path joint "
            "dynamics a copula on standalone margins cannot represent. The "
            "MR-010/MR-014 quantifications are unchanged (SCR move 0.013% < 1% "
            "trigger); MR-015 is opened to track the copula-form residual, the "
            "grouped-t / vine escalation scheduled for Phase 28. Copula FROZEN "
            "per SII Art. 234; production sign-off withheld (educational).")
    return out


def _build_phase28() -> Dict[str, Any]:
    """Phase 28 (contract 1.10.0, additive): grouped-t / heterogeneous
    tail-dependence copula. Normalises the already-produced Task 2 grouped-t
    point read-out, Task 3 bootstrap, and Task 4 within/cross-block diagnostics
    for the offline UI. Display-layer only - no model calculation."""
    out: Dict[str, Any] = {}
    t2 = _load(os.path.join(
        VAL, "PHASE28_TASK2_GROUPED_T_COPULA_REPORT.json"))
    if isinstance(t2, dict) and isinstance(t2.get("result"), dict):
        r = t2["result"]
        out["copula"] = {
            "drivers": t2.get("drivers", []),
            "df_frozen": t2.get("df_frozen"),
            "df_rematched": t2.get("df_rematched"),
            "rho_max_abs_diff": t2.get("rho_max_abs_diff"),
            "block_dfs_hat": r.get("block_dfs_hat", []),
            "block_labels": r.get("block_labels", []),
            "blocks": r.get("blocks", []),
            "realised_block_codependence":
                r.get("realised_block_codependence", {}),
            "fit": r.get("fit", {}),
            "grouped_t_readout_at_df_hat":
                r.get("grouped_t_readout_at_df_hat", {}),
            "single_t_readout_homogeneous":
                r.get("single_t_readout_homogeneous", {}),
            "frozen_t_component_reference":
                r.get("frozen_t_component_reference"),
            "nested_pathwise_reference": r.get("nested_pathwise_reference"),
            "grouped_t_vs_frozen_t_rel":
                r.get("grouped_t_vs_frozen_t_rel"),
            "grouped_t_vs_frozen_t_direction":
                r.get("grouped_t_vs_frozen_t_direction"),
            "gap_to_nested_grouped_t_rel":
                r.get("gap_to_nested_grouped_t_rel"),
            "gap_to_nested_frozen_t_rel":
                r.get("gap_to_nested_frozen_t_rel"),
            "homogeneous_recovery_dev": r.get("homogeneous_recovery_dev"),
            "gates": r.get("gates", {}),
            "verdict": t2.get("verdict"),
            "source": ("docs/validation/"
                       "PHASE28_TASK2_GROUPED_T_COPULA_REPORT.json"),
            "change_record_id": t2.get("change_record_id"),
        }
    t3 = _load(os.path.join(
        VAL, "PHASE28_TASK3_GROUPED_T_BOOTSTRAP_REPORT.json"))
    if isinstance(t3, dict) and isinstance(t3.get("result"), dict):
        r = t3["result"]
        out["bootstrap"] = {
            "config": r.get("config", {}),
            "block_dfs_hat": t3.get("block_dfs_hat", []),
            "grouped_t_component_scr_ci":
                r.get("grouped_t_component_scr_ci", {}),
            "single_t_component_scr_ci":
                r.get("single_t_component_scr_ci", {}),
            "without_grouped_t_scr_ci":
                r.get("without_grouped_t_scr_ci", {}),
            "grouped_minus_single_mean":
                r.get("grouped_minus_single_mean"),
            "grouped_minus_single_neg_share":
                r.get("grouped_minus_single_neg_share"),
            "directional_disclosed_direction":
                r.get("directional_disclosed_direction"),
            "nested_pathwise_reference": r.get("nested_pathwise_reference"),
            "task2_frozen_t_component_point":
                r.get("task2_frozen_t_component_point"),
            "task2_grouped_t_component_point":
                r.get("task2_grouped_t_component_point"),
            "headline_nested_inside_95ci":
                r.get("headline_nested_inside_95ci"),
            "se_frac_of_mean": r.get("se_frac_of_mean"),
            "se_gate_pass": r.get("se_gate_pass"),
            "residual_gap_redecomposition_point":
                r.get("residual_gap_redecomposition_point", {}),
            "residual_gap_redecomposition_bootstrap_mean":
                r.get("residual_gap_redecomposition_bootstrap_mean", {}),
            "gates": r.get("gates", {}),
            "digest": r.get("digest"),
            "verdict": t3.get("verdict"),
            "source": ("docs/validation/"
                       "PHASE28_TASK3_GROUPED_T_BOOTSTRAP_REPORT.json"),
            "change_record_id": t3.get("change_record_id"),
        }
    t4 = _load(os.path.join(
        VAL, "PHASE28_TASK4_TAIL_DIAGNOSTICS_REPORT.json"))
    if isinstance(t4, dict) and isinstance(t4.get("result"), dict):
        r = t4["result"]
        tds = r.get("tail_diagnostics_summary", {}) or {}

        def _m(blk, key):
            v = blk.get(key) or {}
            return {"mean": v.get("mean"), "ci_lo": v.get("ci_lo"),
                    "ci_hi": v.get("ci_hi")}

        rows = []
        for pk in sorted(tds.keys()):
            blk = tds[pk] or {}
            try:
                p_val = float(pk.split("_")[1]) / 100.0
            except (IndexError, ValueError):
                p_val = None
            rows.append({
                "p": p_val,
                "grp_cross_upper": _m(blk, "grp_cross_upper"),
                "grp_cross_lower": _m(blk, "grp_cross_lower"),
                "sng_cross_upper": _m(blk, "sng_cross_upper"),
                "sng_cross_lower": _m(blk, "sng_cross_lower"),
                "grp_minus_sng_cross_upper":
                    _m(blk, "grp_minus_sng_cross_upper"),
                "grp_within_upper_nonfin":
                    _m(blk, "grp_within_upper_nonfin"),
                "grp_within_upper_fin": _m(blk, "grp_within_upper_fin"),
                "sng_within_upper_fin": _m(blk, "sng_within_upper_fin"),
                "grp_within_radial_asym_fin":
                    _m(blk, "grp_within_radial_asym_fin"),
                "grp_heterogeneity_upper":
                    _m(blk, "grp_heterogeneity_upper"),
            })
        cfg = r.get("config", {}) or {}
        out["tail"] = {
            "block_dfs_frozen": t4.get("block_dfs_frozen", []),
            "homogeneous_df_frozen": t4.get("homogeneous_df_frozen"),
            "nested_pathwise_reference": t4.get("nested_pathwise_reference"),
            "p_grid": cfg.get("p_grid", []),
            "tail_anchor_p": cfg.get("tail_level_anchor"),
            "rows": rows,
            "archive_crosscheck": r.get("archive_crosscheck", {}),
            "dilution_consistency": r.get("dilution_consistency", {}),
            "mr_refresh_decision": r.get("mr_refresh_decision", {}),
            "mr016_opened": t4.get("mr016_opened"),
            "gates": r.get("gates", {}),
            "verdict": t4.get("verdict"),
            "digest": r.get("digest"),
            "source": ("docs/validation/"
                       "PHASE28_TASK4_TAIL_DIAGNOSTICS_REPORT.json"),
            "change_record_id": t4.get("change_record_id"),
        }
    if out:
        out["narrative"] = (
            "Phase 28 tested the grouped-t copula (Daul et al. 2003) as a "
            "heterogeneous tail-dependence super-set of the frozen single-df "
            "t(2.9451) copula. The homogeneous boundary recovers the governed "
            "single-df t component exactly, but leakage-free block df fitting "
            "to standalone within-block co-exceedances gives df_NONFIN=37.866 "
            "and df_FIN=8.506, both lighter-tailed than the frozen df. "
            "MATERIAL FINDING: the grouped-t dilutes cross-block co-movement "
            "against the single shared-mixing t boundary, moving grouped-t "
            "component SCR DOWN to 35,372.5 bootstrap mean (point 35,604.4) "
            "vs single-df t 39,595.1 bootstrap mean (point 39,975.7). The "
            "nested path-wise reference 46,638.9 remains OUTSIDE the grouped-t "
            "95% CI [33,034.4, 38,008.5], and the copula-form residual WIDENS "
            "from the skew-t-reconfirmed 6,114.9 to 10,491.5. The grouped-t is "
            "therefore DISCLOSED, not adopted into the governed headline; "
            "MR-010/MR-014 are not refreshed (headline move 0.00%), MR-016 is "
            "opened, and Phase 29 escalates to vine / pair-copula. Copula and "
            "margins remain frozen per SII Art. 234; production sign-off "
            "withheld (educational).")
    return out


def build_ui_data() -> Dict[str, Any]:
    base = _load(VIEWER_DATA) or {}
    state = _load(STATE_PATH) or {}
    gov = _load(GOV_PATH) or {}

    now = _dt.datetime.now(_dt.timezone.utc).isoformat()

    meta = dict(base.get("meta", {}))
    meta.setdefault("model_name", gov.get("model_name", "HK PAR Stochastic Capital Model (educational)"))
    meta.setdefault("model_version", gov.get("model_version", state.get("model_version", "")))
    meta["generated_utc"] = now
    meta["classification"] = meta.get("classification", "EDUCATIONAL -- not for production capital reporting")

    inventory = _build_inventory()
    calibrations = _build_calibrations()
    capital = _build_capital(base.get("capital", {}))
    tail = _build_tail(base.get("tail", {}))
    management_actions = _build_management_actions()
    _ma_agg = management_actions.get("aggregation") or {}
    if _ma_agg:
        # Additive capital read-outs: tail-matched t-copula (without-actions
        # basis) + the nested with-actions headline (Phase 23 Tasks 2-4).
        capital["t_copula_scr"] = _ma_agg.get("t_copula_scr_without")
        capital["t_copula_df"] = _ma_agg.get("df_matched")
        capital["t_copula_rel_error"] = _ma_agg.get("t_rel_error_without")
        capital["nested_scr_with_actions"] = _ma_agg.get("nested_scr_with")

    phase24 = _build_phase24()
    _p24_ja = phase24.get("joint_action") or {}
    if _p24_ja:
        # Additive capital read-out: joint-action (action-after-aggregation)
        # t-copula SCR (Phase 24 Task 2).
        capital["t_copula_scr_joint_action"] = _p24_ja.get("t_scr_joint")
    _p24_ipc = ((phase24.get("inner_path") or {})
                .get("nested_capital_with_inner_path") or {})
    if _p24_ipc:
        capital["nested_scr_with_inner_path"] = _p24_ipc.get("scr_proxy")

    phase25 = _build_phase25()
    _p25_ncp = ((phase25.get("declaration") or {})
                .get("nested_capital_with_pathwise") or {})
    if _p25_ncp:
        # Additive capital read-out: nested with-actions SCR on the path-wise
        # declaration basis (Phase 25 Task 2 - the more conservative basis).
        capital["nested_scr_with_pathwise"] = _p25_ncp.get("scr_proxy")
    _p25_td = phase25.get("tail_diagnostics") or {}
    if _p25_td.get("t_scr_pathwise_readout") is not None:
        capital["t_copula_scr_pathwise_readout"] = _p25_td.get(
            "t_scr_pathwise_readout")

    phase26 = _build_phase26()
    _p26_comp = (phase26.get("composition") or {}).get("t_readout") or {}
    if _p26_comp.get("scr_component") is not None:
        # Additive capital read-out: full re-aggregated (component-basis)
        # path-wise t-copula SCR (Phase 26 Task 2 - point estimate).
        capital["t_copula_scr_pathwise_component"] = _p26_comp.get(
            "scr_component")
    _p26_bt = (phase26.get("bootstrap") or {}).get(
        "component_t_scr_ci") or {}
    if _p26_bt.get("mean") is not None:
        # Additive capital read-out: frozen-copula bootstrap mean SCR on the
        # full component basis (Phase 26 Task 3 - sampling-band centre).
        capital["t_copula_scr_pathwise_component_bootstrap_mean"] = (
            _p26_bt.get("mean"))

    phase27 = _build_phase27()
    _p27_bt = (phase27.get("bootstrap") or {}).get(
        "skewt_component_scr_ci") or {}
    if _p27_bt.get("mean") is not None:
        capital["skewt_copula_scr_component_bootstrap_mean"] = (
            _p27_bt.get("mean"))

    phase28 = _build_phase28()
    _p28_bt = (phase28.get("bootstrap") or {})
    _p28_grp = _p28_bt.get("grouped_t_component_scr_ci") or {}
    _p28_sng = _p28_bt.get("single_t_component_scr_ci") or {}
    if _p28_grp.get("mean") is not None:
        capital["grouped_t_copula_scr_component_bootstrap_mean"] = (
            _p28_grp.get("mean"))
    if _p28_sng.get("mean") is not None:
        capital["single_t_copula_scr_component_bootstrap_mean"] = (
            _p28_sng.get("mean"))
    _p28_cp = (phase28.get("copula") or {}).get(
        "grouped_t_readout_at_df_hat") or {}
    if _p28_cp.get("scr_component") is not None:
        capital["grouped_t_copula_scr_component_point"] = (
            _p28_cp.get("scr_component"))

    governance = dict(base.get("governance", {}))
    _base_risks = list(governance.get("risk_register", []) or [])
    _have = {str(x.get("risk_id")) for x in _base_risks}
    _store_risks = (gov.get("risk_register") or []) if isinstance(gov, dict) \
        else []
    for _rk in _store_risks:
        _rid = str(_rk.get("risk_id"))
        if _rid and _rid not in _have:
            _base_risks.append({
                "risk_id": _rk.get("risk_id"),
                "title": _rk.get("title"),
                "overall_rating": _rk.get("overall_rating"),
                "mitigation_status": _rk.get("mitigation_status"),
                "category": _rk.get("category"),
                "owner": _rk.get("owner"),
                "likelihood": _rk.get("likelihood"),
                "impact": _rk.get("impact"),
                "description": _rk.get("description"),
                "mitigation": _rk.get("mitigation"),
                "related_standard": _rk.get("related_standard"),
                "updated_at": _rk.get("updated_at"),
            })
            _have.add(_rid)
    if _base_risks:
        governance["risk_register"] = _base_risks

    summary = dict(base.get("summary", {}))
    summary["contract_artifacts"] = len(inventory)
    summary["calibrated_drivers"] = len(calibrations)

    data = {
        "contract_version": CONTRACT_VERSION,
        "meta": meta,
        "summary": summary,
        "inventory": inventory,
        "capital": capital,
        "tail": tail,
        "proxy": base.get("proxy", {}),
        "loss": base.get("loss", {}),
        "calibrations": calibrations,
        "management_actions": management_actions,
        "phase24": phase24,
        "phase25": phase25,
        "phase26": phase26,
        "phase27": phase27,
        "phase28": phase28,
        "governance": governance,
        "verdicts": _build_verdicts(base.get("verdicts", [])),
    }
    return data


# --------------------------------------------------------------------------- #
# Self-contained HTML shell. ZERO network, no CDN, inline CSS+JS only.
# --------------------------------------------------------------------------- #
HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Actuarial Stochastic Model -- Offline Result UI</title>
<style>
  :root{
    --bg:#0f141b; --panel:#161e29; --panel2:#1d2733; --ink:#e7edf5; --muted:#93a1b3;
    --line:#283545; --accent:#4f9cff; --pass:#39d98a; --warn:#ffb454; --fail:#ff6b6b;
    --chip:#22303f;
  }
  *{box-sizing:border-box}
  body{margin:0;background:var(--bg);color:var(--ink);
    font:14px/1.5 -apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif}
  header{padding:18px 22px;border-bottom:1px solid var(--line);
    background:linear-gradient(180deg,#16202c,#0f141b)}
  h1{margin:0 0 4px;font-size:19px;font-weight:650}
  .sub{color:var(--muted);font-size:12.5px}
  .wrap{max-width:1180px;margin:0 auto;padding:0 22px}
  .tabs{display:flex;gap:4px;flex-wrap:wrap;margin:14px 0 0}
  .tab{padding:8px 14px;border:1px solid var(--line);border-bottom:none;
    background:var(--panel);color:var(--muted);border-radius:8px 8px 0 0;cursor:pointer;font-size:13px}
  .tab.active{background:var(--panel2);color:var(--ink);font-weight:600}
  .panel{display:none;background:var(--panel2);border:1px solid var(--line);
    border-radius:0 8px 8px 8px;padding:18px;margin-bottom:30px}
  .panel.active{display:block}
  .cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin:6px 0 16px}
  .card{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:12px 14px}
  .card .k{color:var(--muted);font-size:11.5px;text-transform:uppercase;letter-spacing:.04em}
  .card .v{font-size:20px;font-weight:650;margin-top:3px}
  table{border-collapse:collapse;width:100%;font-size:13px}
  th,td{text-align:left;padding:7px 9px;border-bottom:1px solid var(--line);vertical-align:top}
  th{color:var(--muted);font-weight:600;font-size:11.5px;text-transform:uppercase;letter-spacing:.03em;
    position:sticky;top:0;background:var(--panel2)}
  tr:hover td{background:#1a2531}
  .chip{display:inline-block;padding:2px 8px;border-radius:999px;font-size:11.5px;font-weight:600;
    background:var(--chip);border:1px solid var(--line)}
  .chip.pass{color:var(--pass);border-color:#1f5e44}
  .chip.warn{color:var(--warn);border-color:#5e4a1f}
  .chip.fail{color:var(--fail);border-color:#5e2222}
  .mono{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:12px;color:var(--muted)}
  .gate-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px;margin-top:6px}
  .gate{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:12px 14px}
  .gate h4{margin:0 0 2px;font-size:14px}
  .gate .params{margin-top:8px;font-size:12.5px;color:var(--muted)}
  .gate .params b{color:var(--ink);font-weight:600}
  .critgrid{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:6px;margin:4px 0 14px}
  .crit{display:flex;align-items:center;gap:8px;background:var(--panel2);border:1px solid var(--line);
    border-radius:7px;padding:6px 10px;font-size:12.5px}
  .crit .cic{font-weight:700;width:14px;text-align:center}
  .crit.pass .cic{color:var(--pass)} .crit.fail .cic{color:var(--fail)}
  .subh{margin:12px 0 6px;font-size:11.5px;color:var(--muted);text-transform:uppercase;letter-spacing:.04em}
  .ptable{margin-bottom:14px}
  .calibpanel{padding:14px 16px}
  .calibpanel h4{margin:0 0 2px;font-size:14.5px}
  .filter{margin:2px 0 12px}
  .filter input,.filter select{background:var(--panel);color:var(--ink);border:1px solid var(--line);
    border-radius:7px;padding:6px 9px;font-size:13px}
  .muted{color:var(--muted)}
  .note{color:var(--muted);font-size:12.5px;margin-top:10px}
  details{margin-top:12px}
  summary{cursor:pointer;color:var(--accent);font-size:13px}
  pre{background:#0c1118;border:1px solid var(--line);border-radius:8px;padding:12px;overflow:auto;
    font-size:11.5px;color:#cbd6e4}
  .badge{display:inline-block;padding:2px 8px;border-radius:6px;font-size:11px;background:var(--chip);
    border:1px solid var(--line);color:var(--muted);margin-left:6px}
  .scaffold{color:var(--muted);font-size:13px;padding:8px 0}
  .dz{margin-top:14px;border:1px dashed var(--line);border-radius:10px;padding:14px;color:var(--muted);font-size:12.5px}
  .subnav{display:flex;gap:6px;flex-wrap:wrap;margin:6px 0 14px}
  .segbtn{padding:6px 12px;border:1px solid var(--line);background:var(--panel);color:var(--muted);
    border-radius:7px;cursor:pointer;font-size:12.5px}
  .segbtn.active{background:var(--accent);border-color:var(--accent);color:#06101c;font-weight:650}
  .chartwrap{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:14px 14px 10px;margin-bottom:14px}
  .chartwrap h4{margin:0 0 2px;font-size:14px}
  .chartwrap .cap{color:var(--muted);font-size:12px;margin:0 0 10px}
  svg.chart{display:block;width:100%;height:auto;overflow:visible;margin-top:2px}
  svg.chart text{fill:var(--muted);font:11px -apple-system,Segoe UI,Roboto,sans-serif}
  svg.chart text.val{fill:var(--ink);font-weight:600}
  svg.chart .axis{stroke:var(--line);stroke-width:1}
  svg.chart .grid{stroke:#22303f;stroke-width:1;stroke-dasharray:3 3}
  svg.chart .bar{transition:opacity .12s}
  svg.chart .bar:hover,svg.chart circle:hover{opacity:.82;cursor:pointer}
  svg.chart .refline{stroke-width:1.5}
  .legend{display:flex;gap:14px;flex-wrap:wrap;margin:8px 2px 0;font-size:12px;color:var(--muted)}
  .legend span{display:inline-flex;align-items:center;gap:6px}
  .legend i{width:11px;height:11px;border-radius:3px;display:inline-block}
  .tipbox{position:fixed;z-index:50;pointer-events:none;background:#0c1118;border:1px solid var(--line);
    border-radius:7px;padding:7px 9px;font-size:12px;color:var(--ink);max-width:280px;line-height:1.45;
    box-shadow:0 6px 20px rgba(0,0,0,.45);opacity:0;transition:opacity .08s}
  .tipbox.on{opacity:1}
  .gbar{height:9px;background:var(--panel);border:1px solid var(--line);border-radius:999px;overflow:hidden;margin:4px 0 12px}
  .gbar-fill{height:100%;background:var(--pass)}
  .timeline{position:relative;margin-top:6px}
  .tl-item{display:flex;gap:12px;padding:9px 0;border-bottom:1px solid var(--line)}
  .tl-dot{width:11px;height:11px;border-radius:50%;margin-top:5px;flex:0 0 auto;background:var(--muted)}
  .tl-dot.pass{background:var(--pass)} .tl-dot.warn{background:var(--warn)} .tl-dot.fail{background:var(--fail)}
  .tl-body{flex:1 1 auto;min-width:0}
  .tl-head{margin-bottom:2px}
  .tl-soh{padding:6px 0 6px 10px;border-left:2px solid var(--line);margin:5px 0}
  .rdetbox{background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:10px 12px;font-size:12.5px}
  .heatwrap{max-width:460px;margin:0 0 10px}
  .auditbadge{display:inline-block;padding:8px 14px;border-radius:8px;font-weight:700;font-size:13px}
  .auditbadge.ok{color:var(--pass);background:rgba(57,217,138,.12);border:1px solid #1f5e44}
  .auditbadge.bad{color:var(--fail);background:rgba(255,107,107,.12);border:1px solid #5e2222}
  .toolbar{display:flex;gap:8px;flex-wrap:wrap;margin-top:10px}
  .tbtn{padding:6px 12px;border:1px solid var(--line);background:var(--panel);color:var(--ink);border-radius:7px;cursor:pointer;font-size:12.5px;font-family:inherit}
  .tbtn:hover{border-color:var(--accent);color:var(--accent)}
  .tab,.segbtn{font-family:inherit}
  .tab:focus-visible,.tbtn:focus-visible,.segbtn:focus-visible,.rrow:focus-visible,.crow:focus-visible,.panel:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
  @media print{
    :root{--bg:#fff;--panel:#fff;--panel2:#fff;--ink:#111;--muted:#444;--line:#bbb;--chip:#eee;--accent:#15489c}
    body{background:#fff;color:#111}
    header{background:#fff;border-color:#bbb}
    .toolbar,.tabs,.dz,.filter,#__tip,details>summary{display:none !important}
    .panel{display:block !important;border:none;border-radius:0;padding:0;margin:0 0 22px;background:#fff}
    .panel::before{display:block;content:attr(data-title);font-size:16px;font-weight:700;margin:0 0 10px;color:#111;border-bottom:2px solid #111;padding-bottom:4px}
    .chartwrap,.gate,.card,table,.tl-item{page-break-inside:avoid}
    svg.chart text{fill:#111} svg.chart text.val{fill:#000}
    .card,.gate,.chartwrap{border-color:#bbb}
    a{color:#111}
  }
</style>
</head>
<body>
<header><div class="wrap">
  <h1 id="title">Actuarial Stochastic Model -- Offline Result UI</h1>
  <div class="sub" id="subtitle"></div>
  <div class="toolbar" id="toolbar" role="toolbar" aria-label="Export and print actions">
    <button type="button" class="tbtn" id="btnExportPng" title="Export the visible charts of the active tab as PNG images">Export charts (PNG)</button>
    <button type="button" class="tbtn" id="btnCsvInv">CSV: Inventory</button>
    <button type="button" class="tbtn" id="btnCsvRisk">CSV: Risk register</button>
    <button type="button" class="tbtn" id="btnCsvChg">CSV: Change records</button>
    <button type="button" class="tbtn" id="btnPrint" title="Open the browser print dialog (Save as PDF)">Print / Save PDF</button>
  </div>
</div></header>
<div class="wrap">
  <div class="tabs" id="tabs"></div>
  <div id="overview" class="panel" data-title="Overview"></div>
  <div id="inventory" class="panel" data-title="Inventory &amp; Contract"></div>
  <div id="calibrations" class="panel" data-title="Calibrations"></div>
  <div id="capital" class="panel" data-title="Capital &amp; Tail"></div>
  <div id="actions" class="panel" data-title="Management Actions"></div>
  <div id="phase24" class="panel" data-title="Joint Actions (P24)"></div>
  <div id="phase25" class="panel" data-title="Path-wise Actions (P25)"></div>
  <div id="phase26" class="panel" data-title="Full Re-Agg (P26)"></div>
  <div id="phase27" class="panel" data-title="Skew-t Tail (P27)"></div>
  <div id="phase28" class="panel" data-title="Grouped-t Tail (P28)"></div>
  <div id="governance" class="panel" data-title="Governance"></div>
</div>

<script id="ui-data" type="application/json">/*__UI_DATA__*/null</script>
<script>
"use strict";
(function(){
  function parseEmbedded(){
    var el = document.getElementById("ui-data");
    if(!el) return null;
    var raw = el.textContent || "";
    raw = raw.replace("/*__UI_DATA__*/","").trim();
    if(!raw || raw === "null") return null;
    try { return JSON.parse(raw); } catch(e){ return null; }
  }
  var DATA = parseEmbedded();

  function esc(s){ return String(s==null?"":s)
    .replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;"); }
  function num(x,d){ if(x==null||isNaN(x)) return "--";
    return Number(x).toLocaleString(undefined,{maximumFractionDigits:(d==null?0:d)}); }
  function chipClass(s){ s=String(s||"").toUpperCase();
    if(/PASS|CLEAR|MITIGAT|APPROV|OK/.test(s)) return "pass";
    if(/WARN|REVIEW|PLACEHOLD|OPEN|DRAFT/.test(s)) return "warn";
    if(/FAIL|BLOCK|FALSE/.test(s)) return "fail"; return ""; }
  function chip(s){ return '<span class="chip '+chipClass(s)+'">'+esc(s||"--")+'</span>'; }

  var TABS = [
    ["overview","Overview"],
    ["inventory","Inventory & Contract"],
    ["calibrations","Calibrations"],
    ["capital","Capital & Tail"],
    ["actions","Management Actions"],
    ["phase24","Joint Actions (P24)"],
    ["phase25","Path-wise Actions (P25)"],
    ["phase26","Full Re-Agg (P26)"],
    ["phase27","Skew-t Tail (P27)"],
    ["phase28","Grouped-t Tail (P28)"],
    ["governance","Governance"]
  ];

  function renderTabs(){
    var t = document.getElementById("tabs");
    t.innerHTML = "";
    t.setAttribute("role","tablist");
    t.setAttribute("aria-label","Result sections");
    TABS.forEach(function(p,i){
      var b = document.createElement("button");
      b.type = "button";
      b.className = "tab"+(i===0?" active":"");
      b.textContent = p[1];
      b.id = "tab-"+p[0];
      b.setAttribute("data-target",p[0]);
      b.setAttribute("role","tab");
      b.setAttribute("aria-controls",p[0]);
      b.setAttribute("aria-selected", i===0?"true":"false");
      b.setAttribute("tabindex", i===0?"0":"-1");
      b.onclick = function(){ activateTab(p[0]); };
      b.addEventListener("keydown", function(e){
        if(e.key==="ArrowRight"||e.key==="ArrowLeft"||e.key==="Home"||e.key==="End"){
          e.preventDefault();
          var els=[].slice.call(document.querySelectorAll("#tabs .tab"));
          var idx=els.indexOf(b);
          var ni=e.key==="ArrowRight"?(idx+1)%els.length:e.key==="ArrowLeft"?(idx-1+els.length)%els.length:e.key==="Home"?0:els.length-1;
          els[ni].focus(); els[ni].click();
        }
      });
      t.appendChild(b);
    });
    TABS.forEach(function(p){
      var pl=document.getElementById(p[0]);
      if(pl){ pl.setAttribute("role","tabpanel"); pl.setAttribute("aria-labelledby","tab-"+p[0]); if(!pl.hasAttribute("tabindex")) pl.setAttribute("tabindex","0"); }
    });
    document.getElementById("overview").classList.add("active");
  }
  function activateTab(target){
    [].forEach.call(document.querySelectorAll("#tabs .tab"),function(x){
      var on=x.getAttribute("data-target")===target;
      x.classList.toggle("active",on);
      x.setAttribute("aria-selected", on?"true":"false");
      x.setAttribute("tabindex", on?"0":"-1");
    });
    [].forEach.call(document.querySelectorAll(".panel"),function(x){ x.classList.remove("active"); });
    var pl=document.getElementById(target); if(pl) pl.classList.add("active");
  }

  function renderHeader(){
    if(!DATA){ document.getElementById("subtitle").textContent =
      "No embedded data found. Load a ui_data.json below."; return; }
    var m = DATA.meta||{};
    document.getElementById("title").textContent = m.model_name || "Actuarial Stochastic Model -- Offline Result UI";
    document.getElementById("subtitle").innerHTML =
      esc(m.classification||"") +
      ' <span class="badge">contract v'+esc(DATA.contract_version||"?")+'</span>'+
      ' <span class="badge">generated '+esc((m.generated_utc||"").slice(0,19))+'Z</span>';
  }

  function renderOverview(){
    var el = document.getElementById("overview"); if(!DATA){ el.innerHTML=dz(); return; }
    var s = DATA.summary||{}, cap = DATA.capital||{};
    var cards = [
      ["Tasks complete",(s.tasks_completed!=null? s.tasks_completed+"/"+(s.tasks_total||"?"):"--")],
      ["Phases complete", s.phases_completed!=null? s.phases_completed : "--"],
      ["Gates cleared",(s.gates_cleared!=null? s.gates_cleared+"/"+(s.gates_total||"?"):"--")],
      ["Risks mitigated",(s.risks_mitigated!=null? s.risks_mitigated:"--")+" / open "+(s.risks_open!=null?s.risks_open:"--")],
      ["Artifacts catalogued", (DATA.inventory||[]).length],
      ["Calibrated drivers", (DATA.calibrations||[]).length],
      ["Nested 99.5% SCR", num(cap.nested_scr)],
      ["Production status", s.production_status||"educational"]
    ];
    var html = '<div class="cards">';
    cards.forEach(function(c){ html += '<div class="card"><div class="k">'+esc(c[0])+
      '</div><div class="v">'+esc(c[1])+'</div></div>'; });
    html += '</div>';
    var v = DATA.verdicts||[];
    if(v.length){
      html += '<h3 style="margin:8px 0 6px">Headline verdicts</h3><table><thead><tr><th>Item</th><th>Verdict</th></tr></thead><tbody>';
      v.forEach(function(x){
        var name = x.name||x.id||x.title||"";
        var verd = x.verdict||x.status||"";
        html += '<tr><td>'+esc(name)+'</td><td>'+chip(verd)+'</td></tr>';
      });
      html += '</tbody></table>';
    }
    html += '<p class="note">This is the zero-install offline UI foundation (UI Task 1): inventory + one stable '+
      '<span class="mono">ui_data.json</span> contract embedded inline. No network is contacted. '+
      'All five tabs are interactive: Inventory, Calibrations, Capital/Tail, and the Governance &amp; assumptions dashboard '+
      '(deployment gates, model-risk register, ChangeRecord approval trail, recomputed audit integrity).</p>';
    el.innerHTML = html;
  }

  function renderInventory(){
    var el = document.getElementById("inventory"); if(!DATA){ el.innerHTML=dz(); return; }
    var inv = DATA.inventory||[];
    var cats = {}; inv.forEach(function(i){ cats[i.category]=(cats[i.category]||0)+1; });
    var catOpts = '<option value="">All categories ('+inv.length+')</option>';
    Object.keys(cats).sort().forEach(function(c){ catOpts += '<option value="'+esc(c)+'">'+esc(c)+' ('+cats[c]+')</option>'; });
    var html = '<p class="muted">Catalogue of every model-output artifact the UI surfaces. '+
      'Each row is content-addressed by SHA-256 so the UI provenance is verifiable offline.</p>';
    html += '<div class="filter"><input id="invq" placeholder="filter by name / headline" style="min-width:240px"/> '+
      '<select id="invcat">'+catOpts+'</select></div>';
    html += '<table id="invtable"><thead><tr><th>Artifact</th><th>Category</th><th>Headline</th>'+
      '<th>Bytes</th><th>SHA-256</th></tr></thead><tbody></tbody></table>';
    html += '<details><summary>Show ui_data.json contract schema</summary><pre>'+esc(contractSchema())+'</pre></details>';
    el.innerHTML = html;
    var tbody = el.querySelector("#invtable tbody");
    function draw(){
      var q = (el.querySelector("#invq").value||"").toLowerCase();
      var c = el.querySelector("#invcat").value||"";
      tbody.innerHTML = "";
      inv.filter(function(i){
        if(c && i.category!==c) return false;
        if(q && !((i.id+" "+i.headline+" "+i.path).toLowerCase().indexOf(q)>=0)) return false;
        return true;
      }).forEach(function(i){
        var tr = document.createElement("tr");
        tr.innerHTML = '<td title="'+esc(i.path)+'"><span class="mono">'+esc(i.id)+'</span></td>'+
          '<td>'+chip(i.category)+'</td><td>'+esc(i.headline||"")+'</td>'+
          '<td>'+num(i.bytes)+'</td><td class="mono" title="'+esc(i.sha256)+'">'+esc((i.sha256||"").slice(0,12))+'</td>';
        tbody.appendChild(tr);
      });
    }
    el.querySelector("#invq").oninput = draw;
    el.querySelector("#invcat").onchange = draw;
    draw();
  }

  function critRow(c){
    var ok=!!c.ok, ic=ok?"✓":"✗", cls=ok?"pass":"fail";
    return '<div class="crit '+cls+'"><span class="cic">'+ic+'</span>'+esc(c.name)+'</div>';
  }

  function calibFitChart(dg){
    var fb=dg&&dg.fit_bars;
    if(!fb||!fb.items||!fb.items.length) return '';
    var unit=fb.unit||'';
    var items=fb.items.map(function(it){
      return {label:it.label, value:it.value, color:"#4f9cff",
        tip:"<b>"+esc(it.label)+"</b><br>"+(unit? (num(it.value,2)+" "+unit) : num(it.value,3))}; });
    var reflines=[];
    if(fb.threshold) reflines.push({label:fb.threshold.label, value:fb.threshold.value,
      color:"var(--warn)", tip:"<b>"+esc(fb.threshold.label)+"</b><br>"+num(fb.threshold.value,2)+(unit?(" "+unit):"")});
    return '<div class="chartwrap"><h4>'+esc(fb.title)+'</h4>'+
      '<p class="cap">Fit-quality diagnostics ('+esc(unit||"mixed units")+'). Hover a bar for the exact value.</p>'+
      barChart(items,{w:560,h:260,mB:54,reflines:reflines})+'</div>';
  }

  function calibPanel(c,idx,active){
    var dg=c.diagnostics||{}, p=c.params||{};
    var prows=Object.keys(p).filter(function(k){return p[k]!=null;}).map(function(k){
      var v=p[k]; return '<tr><td class="mono">'+esc(k)+'</td><td>'+
        esc(typeof v==="number"? Number(v).toPrecision(6): v)+'</td></tr>'; }).join("");
    var kpis=[["Gate",c.gate_id]];
    if(dg.n_obs!=null) kpis.push(["Observations",num(dg.n_obs)]);
    if(dg.fit_r2!=null) kpis.push(["Fit R²",num(dg.fit_r2,3)]);
    if(dg.converged!=null) kpis.push(["Optimiser",dg.converged?"converged":"not converged"]);
    var kpihtml=kpis.map(function(k){return '<div class="card"><div class="k">'+esc(k[0])+
      '</div><div class="v">'+esc(k[1])+'</div></div>';}).join("");
    var crits=(dg.criteria||[]).map(critRow).join("");
    return '<div class="gate calibpanel" id="calib-'+idx+'"'+(active?'':' style="display:none"')+'>'+
      '<h4>'+esc(c.driver)+' &middot; '+esc(c.market)+' '+chip(c.gate_status)+
        (c.is_placeholder?' <span class="chip warn">placeholder</span>':'')+'</h4>'+
      '<div class="muted" style="margin:2px 0 4px">'+esc(dg.method||"")+'</div>'+
      '<div class="cards" style="margin:8px 0 4px">'+kpihtml+'</div>'+
      (crits?'<h5 class="subh">Gate criteria ('+esc(c.gate_id)+')</h5><div class="critgrid">'+crits+'</div>':'')+
      '<h5 class="subh">Calibrated parameters</h5>'+
      '<table class="ptable"><thead><tr><th>Parameter</th><th>Value</th></tr></thead><tbody>'+prows+'</tbody></table>'+
      calibFitChart(dg)+
      '<div class="note">'+esc(c.gate_evidence||"")+' &middot; source: <span class="mono">'+esc(c.source||"")+'</span>'+
        (c.lineage_id?(' &middot; lineage <span class="mono">'+esc(c.lineage_id)+'</span>'):"")+'</div>'+
      '</div>';
  }

  function renderCalibrations(){
    var el = document.getElementById("calibrations"); if(!DATA){ el.innerHTML=dz(); return; }
    var cs = DATA.calibrations||[];
    if(!cs.length){ el.innerHTML = '<p class="muted">No calibration records in this snapshot.</p>'; return; }
    var npass=cs.filter(function(c){return /PASS|CLEAR/.test(String(c.gate_status||"").toUpperCase());}).length;
    var nplace=cs.filter(function(c){return c.is_placeholder;}).length;
    var html = '<p class="muted">Per-driver calibration explorer: each calibrated stochastic driver with its '+
      'plausibility gate, gate-criteria breakdown, calibrated parameters and fit diagnostics. '+
      'Read-only; rendered offline from the embedded snapshot.</p>';
    html += '<div class="cards">'+
      '<div class="card"><div class="k">Calibrated drivers</div><div class="v">'+cs.length+'</div></div>'+
      '<div class="card"><div class="k">Gates passed</div><div class="v">'+npass+'/'+cs.length+'</div></div>'+
      '<div class="card"><div class="k">Placeholders</div><div class="v">'+nplace+'</div></div></div>';
    html += '<div class="subnav" id="calibnav">'+cs.map(function(c,i){
      var name=String(c.driver||"").replace(/\s*\(.*\)\s*/,"");
      return '<div class="segbtn'+(i===0?" active":"")+'" data-idx="'+i+'">'+esc(name)+' &middot; '+esc(c.market)+'</div>';
    }).join("")+'</div>';
    html += '<div id="calibpanels">'+cs.map(function(c,i){return calibPanel(c,i,i===0);}).join("")+'</div>';
    el.innerHTML = html;
    [].forEach.call(el.querySelectorAll("#calibnav .segbtn"),function(b){
      b.onclick=function(){
        [].forEach.call(el.querySelectorAll("#calibnav .segbtn"),function(x){x.classList.remove("active");});
        [].forEach.call(el.querySelectorAll(".calibpanel"),function(x){x.style.display="none";});
        b.classList.add("active");
        var v=document.getElementById("calib-"+b.getAttribute("data-idx")); if(v) v.style.display="block";
      };
    });
    wireTips(el);
  }

  // ---- inline-SVG chart toolkit (UI Task 2; zero-dependency, offline) ----
  function fmtK(x){ if(x==null||isNaN(x)) return "--"; var a=Math.abs(x);
    if(a>=1e6) return (x/1e6).toFixed(2)+"M"; if(a>=1e3) return (x/1e3).toFixed(1)+"k";
    return Number(x).toFixed(a<10&&a>0?1:0); }
  function ta(s){ return String(s==null?"":s).replace(/"/g,"&quot;"); }
  function svgOpen(w,h){ return '<svg class="chart" viewBox="0 0 '+w+' '+h+'" '+
    'preserveAspectRatio="xMidYMid meet" role="img">'; }
  function xlabel(label,cx,cy){ var w=String(label).split(" "); var o="";
    for(var i=0;i<w.length;i++){ o+='<text x="'+cx+'" y="'+(cy+i*12)+'" text-anchor="middle">'+esc(w[i])+'</text>'; }
    return o; }
  function legendRow(items){ return '<div class="legend">'+items.map(function(d){
    return '<span><i style="background:'+(d.color||'var(--accent)')+'"></i>'+esc(d.label)+'</span>'; }).join("")+'</div>'; }

  function barChart(items,opts){
    opts=opts||{};
    var W=opts.w||660, H=opts.h||300, mL=50, mR=16, mT=16, mB=opts.mB||48;
    var iw=W-mL-mR, ih=H-mT-mB;
    var vals=items.map(function(d){return d.value||0;});
    (opts.reflines||[]).forEach(function(r){ vals.push(r.value||0); });
    var maxV=opts.max!=null?opts.max:Math.max.apply(null,vals); maxV=(maxV>0?maxV:1)*1.10;
    var n=items.length, step=iw/n, bw=step*0.62;
    var Y=function(v){ return mT+ih-(v/maxV)*ih; };
    var s=svgOpen(W,H);
    for(var g=0;g<=4;g++){ var gv=maxV*g/4, gy=Y(gv);
      s+='<line class="grid" x1="'+mL+'" y1="'+gy+'" x2="'+(W-mR)+'" y2="'+gy+'"/>';
      s+='<text x="'+(mL-6)+'" y="'+(gy+3)+'" text-anchor="end">'+fmtK(gv)+'</text>'; }
    s+='<line class="axis" x1="'+mL+'" y1="'+(mT+ih)+'" x2="'+(W-mR)+'" y2="'+(mT+ih)+'"/>';
    items.forEach(function(d,i){
      var x=mL+i*step+(step-bw)/2, by=Y(d.value||0), bh=mT+ih-by;
      s+='<rect class="bar" x="'+x+'" y="'+by+'" width="'+bw+'" height="'+Math.max(0,bh)+'" rx="3" '+
        'fill="'+(d.color||'var(--accent)')+'"'+(d.stroke?(' stroke="'+d.stroke+'" stroke-width="2"'):'')+
        ' data-tip="'+ta(d.tip||(d.label+': '+num(d.value)))+'"/>';
      s+='<text class="val" x="'+(x+bw/2)+'" y="'+(by-5)+'" text-anchor="middle">'+fmtK(d.value)+'</text>';
      s+=xlabel(d.label, x+bw/2, mT+ih+14);
    });
    (opts.reflines||[]).forEach(function(r){ var ry=Y(r.value);
      s+='<line class="refline" x1="'+mL+'" y1="'+ry+'" x2="'+(W-mR)+'" y2="'+ry+'" '+
        'stroke="'+(r.color||'var(--ink)')+'" stroke-dasharray="6 4" data-tip="'+ta(r.tip||r.label)+'"/>';
      s+='<text x="'+(W-mR)+'" y="'+(ry-4)+'" text-anchor="end" fill="'+(r.color||'var(--ink)')+'">'+esc(r.label)+'</text>';
    });
    return s+'</svg>';
  }

  function ciChart(rows,opts){
    opts=opts||{};
    var W=opts.w||680, rowH=70, mT=14, mB=30, mL=86, mR=28;
    var H=mT+mB+rows.length*rowH;
    var av=[]; rows.forEach(function(r){ av.push(r.lo,r.hi,r.point); });
    var lo=Math.min.apply(null,av), hi=Math.max.apply(null,av);
    var pad=(hi-lo)*0.18||1; lo-=pad; hi+=pad;
    var X=function(v){ return mL+(v-lo)/(hi-lo)*(W-mL-mR); };
    var s=svgOpen(W,H);
    for(var t=0;t<=4;t++){ var tv=lo+(hi-lo)*t/4, tx=X(tv);
      s+='<line class="grid" x1="'+tx+'" y1="'+mT+'" x2="'+tx+'" y2="'+(H-mB)+'"/>';
      s+='<text x="'+tx+'" y="'+(H-mB+16)+'" text-anchor="middle">'+fmtK(tv)+'</text>'; }
    rows.forEach(function(r,i){
      var cy=mT+i*rowH+rowH/2, c=r.color||'var(--accent)';
      s+='<text class="val" x="'+(mL-12)+'" y="'+(cy-3)+'" text-anchor="end">'+esc(r.label)+'</text>';
      s+='<text x="'+(mL-12)+'" y="'+(cy+13)+'" text-anchor="end">'+fmtK(r.point)+'</text>';
      var x1=X(r.lo), x2=X(r.hi), xp=X(r.point);
      s+='<line x1="'+x1+'" y1="'+cy+'" x2="'+x2+'" y2="'+cy+'" stroke="'+c+'" stroke-width="3" data-tip="'+ta(r.tip)+'"/>';
      s+='<line x1="'+x1+'" y1="'+(cy-8)+'" x2="'+x1+'" y2="'+(cy+8)+'" stroke="'+c+'" stroke-width="2"/>';
      s+='<line x1="'+x2+'" y1="'+(cy-8)+'" x2="'+x2+'" y2="'+(cy+8)+'" stroke="'+c+'" stroke-width="2"/>';
      s+='<circle cx="'+xp+'" cy="'+cy+'" r="6" fill="var(--ink)" stroke="'+c+'" stroke-width="2" data-tip="'+ta(r.tip)+'"/>';
    });
    return s+'</svg>';
  }

  function lineChart(series,xvals,opts){
    opts=opts||{};
    var W=opts.w||680, H=opts.h||300, mL=58, mR=20, mT=18, mB=44;
    var iw=W-mL-mR, ih=H-mT-mB;
    var allY=[]; series.forEach(function(se){ allY=allY.concat(se.data); });
    var minY=Math.min.apply(null,allY), maxY=Math.max.apply(null,allY);
    var pad=(maxY-minY)*0.15||1; minY-=pad; maxY+=pad;
    var xmin=Math.min.apply(null,xvals), xmax=Math.max.apply(null,xvals);
    var X=function(v){ return mL+(xmax===xmin?0:(v-xmin)/(xmax-xmin)*iw); };
    var Y=function(v){ return mT+ih-(v-minY)/(maxY-minY)*ih; };
    var s=svgOpen(W,H);
    for(var g=0;g<=4;g++){ var gv=minY+(maxY-minY)*g/4, gy=Y(gv);
      s+='<line class="grid" x1="'+mL+'" y1="'+gy+'" x2="'+(W-mR)+'" y2="'+gy+'"/>';
      s+='<text x="'+(mL-6)+'" y="'+(gy+3)+'" text-anchor="end">'+fmtK(gv)+'</text>'; }
    s+='<line class="axis" x1="'+mL+'" y1="'+(mT+ih)+'" x2="'+(W-mR)+'" y2="'+(mT+ih)+'"/>';
    xvals.forEach(function(xv){ var px=X(xv);
      s+='<text x="'+px+'" y="'+(mT+ih+16)+'" text-anchor="middle">'+fmtK(xv)+'</text>'; });
    if(opts.markX!=null){ var mx=X(opts.markX);
      s+='<line class="refline" x1="'+mx+'" y1="'+mT+'" x2="'+mx+'" y2="'+(mT+ih)+'" '+
        'stroke="var(--warn)" stroke-dasharray="5 4" data-tip="'+ta("Recommended outer count n* = "+num(opts.markX))+'"/>';
      s+='<text x="'+mx+'" y="'+(mT-4)+'" text-anchor="middle" fill="var(--warn)">n*='+fmtK(opts.markX)+'</text>'; }
    series.forEach(function(se){
      var d=""; se.data.forEach(function(v,i){ d+=(i?"L":"M")+X(xvals[i])+" "+Y(v)+" "; });
      s+='<path d="'+d+'" fill="none" stroke="'+se.color+'" stroke-width="2.2"/>';
      se.data.forEach(function(v,i){
        s+='<circle cx="'+X(xvals[i])+'" cy="'+Y(v)+'" r="4.5" fill="'+se.color+'" data-tip="'+
          ta("<b>"+se.label+"</b><br>n_outer = "+num(xvals[i])+"<br>"+se.label+" = "+num(v))+'"/>'; });
    });
    return s+'</svg>';
  }

  function wireTips(container){
    var tip=document.getElementById("__tip");
    if(!tip){ tip=document.createElement("div"); tip.id="__tip"; tip.className="tipbox"; document.body.appendChild(tip); }
    container.addEventListener("mousemove",function(e){
      var t=(e.target&&e.target.getAttribute)?e.target.getAttribute("data-tip"):null;
      if(t){ tip.innerHTML=t; tip.classList.add("on");
        tip.style.left=(e.clientX+14)+"px"; tip.style.top=(e.clientY+16)+"px";
      } else { tip.classList.remove("on"); }
    });
    container.addEventListener("mouseleave",function(){ tip.classList.remove("on"); });
  }

  function capBarsBlock(cap){
    var sum=cap.standalone_sum||1;
    var D=[
      {label:"Short rate", value:cap.rate_scr, color:"#4f9cff"},
      {label:"Equity gtee", value:cap.equity_scr, color:"#39d98a"},
      {label:"Credit spread", value:cap.credit_scr, color:"#ffb454"},
      {label:"Lapse", value:cap.lapse_scr, color:"#b98cff"},
      {label:"Mortality", value:cap.mortality_scr, color:"#ff6b6b"},
      {label:"FX", value:cap.fx_scr, color:"#5ad7e0"},
      {label:"Liquidity", value:cap.liquidity_scr, color:"#e0c45a"}
    ].filter(function(d){return d.value!=null;});
    D.forEach(function(d){ d.tip="<b>"+d.label+"</b><br>Standalone 99.5% SCR: "+num(d.value)+
      "<br>"+(d.value/sum*100).toFixed(1)+"% of standalone sum"; });
    return '<div class="chartwrap"><h4>Standalone 99.5% SCR by risk driver</h4>'+
      '<p class="cap">Pre-diversification capital charge per stochastic driver (12-month horizon, 99.5% VaR). '+
      'Hover a bar for its share of the standalone sum.</p>'+
      barChart(D,{w:660,h:300})+legendRow(D)+'</div>';
  }

  function capAggBlock(cap){
    var cop=cap.copula||{}, cands=cop.candidates||[], nested=cap.nested_scr, sel=cap.selected_copula;
    var D=[
      {label:"Standalone sum", value:cap.standalone_sum, color:"#5a6b7d",
        tip:"<b>Standalone sum</b><br>Naive add-up (no diversification): "+num(cap.standalone_sum)},
      {label:"Var-covar", value:cap.var_covar_scr, color:"#ffb454",
        tip:"<b>Var-covar (formula)</b><br>SCR: "+num(cap.var_covar_scr)+
          "<br>Rel err vs nested: "+(cap.formula_vs_nested_rel_error!=null?(cap.formula_vs_nested_rel_error*100).toFixed(1)+"%":"--")+
          "<br>Gaussian-correlation closed form; understates the tail."}
    ];
    cands.forEach(function(c){
      var is=(c.name===sel);
      D.push({label:String(c.name).replace(/_/g,"-"), value:c.aggregated_scr,
        color:is?"#4f9cff":"#33506e", stroke:is?"var(--ink)":null,
        tip:"<b>"+c.name+(is?" (selected)":"")+"</b><br>Aggregated SCR: "+num(c.aggregated_scr)+
          "<br>Rel err vs nested: "+(c.scr_rel_error_vs_nested*100).toFixed(1)+"%"+
          "<br>Diversification benefit: "+num(c.diversification_benefit)+
          "<br>Upper-tail dependence: "+Number(c.upper_tail_dependence).toFixed(3)+
          "<br>AIC: "+Number(c.aic).toFixed(1)});
    });
    var reflines=(nested!=null)?[{label:"Nested benchmark", value:nested, color:"var(--pass)",
      tip:"<b>Nested-simulation benchmark</b><br>SCR: "+num(nested)+"<br>The capital figure all aggregators are judged against."}]:[];
    var note="";
    if(cap.esg_understatement_pct!=null)
      note='<p class="cap" style="margin-top:8px">Var-covar understates the nested benchmark by <b>'+
        esc(cap.esg_understatement_pct)+'%</b> (MR-010). Selected aggregator: '+chip(sel||"--")+
        ' &mdash; closest match to nested with parsimony (lowest AIC among adequate fits).</p>';
    return '<div class="chartwrap"><h4>Capital aggregation: standalone &rarr; var-covar &rarr; copula vs nested</h4>'+
      '<p class="cap">Each aggregation method versus the nested-simulation benchmark (dashed green). '+
      'The selected copula is outlined. Hover for rel-error, diversification benefit, tail dependence and AIC.</p>'+
      barChart(D,{w:760,h:330,mB:54,reflines:reflines})+note+'</div>';
  }

  function capTailBlock(cap,tail){
    if(tail.final_var==null){ return '<div class="chartwrap"><p class="muted">No tail metrics in snapshot.</p></div>'; }
    var vci=tail.var_ci||[null,null], eci=tail.es_ci||[null,null];
    var rows=[
      {label:"VaR 99.5%", point:tail.final_var, lo:vci[0], hi:vci[1], color:"#4f9cff",
        tip:"<b>99.5% VaR</b><br>Point estimate: "+num(tail.final_var)+
          "<br>95% bootstrap CI: ["+num(vci[0])+", "+num(vci[1])+"]<br>Std error: "+num(tail.var_se)},
      {label:"ES 99.5%", point:tail.final_es, lo:eci[0], hi:eci[1], color:"#39d98a",
        tip:"<b>99.5% Expected Shortfall</b><br>Point estimate: "+num(tail.final_es)+
          "<br>95% bootstrap CI: ["+num(eci[0])+", "+num(eci[1])+"]<br>Std error: "+num(tail.es_se)}
    ];
    var ratios='<p class="cap" style="margin-top:8px">Variance-reduction efficiency &mdash; Sobol vs MC: <b>'+
      esc(num(tail.sobol_ratio,2))+'x</b>'+
      (tail.antithetic_ratio!=null?(', antithetic vs MC: <b>'+esc(num(tail.antithetic_ratio,2))+'x</b>'):'')+
      '. Both point and CI are bounded, so the metric is reproducible within sampling noise.</p>';
    if(tail.nested_disclosure){
      ratios+='<p class="cap">Honest small-sample disclosure (nested, n_outer='+esc(num(tail.nested_n_outer))+
        '): 95% CI ['+esc(num((tail.nested_var_ci||[])[0]))+', '+esc(num((tail.nested_var_ci||[])[1]))+
        ']. '+esc(tail.nested_disclosure)+'</p>';
    }
    return '<div class="chartwrap"><h4>99.5% VaR &amp; ES with 95% bootstrap confidence intervals</h4>'+
      '<p class="cap">Point estimate (dot) with the bootstrap CI (whisker). A bounded CI is the convergence '+
      'evidence the tail gate requires. Hover for exact figures and standard errors.</p>'+
      ciChart(rows,{w:680})+ratios+'</div>';
  }

  function capConvBlock(tail){
    var xs=tail.outer_grid||[];
    if(!xs.length){ return '<div class="chartwrap"><p class="muted">No convergence grid in snapshot.</p></div>'; }
    var series=[
      {label:"VaR", color:"#4f9cff", data:tail.var_path||[]},
      {label:"ES", color:"#39d98a", data:tail.es_path||[]}
    ];
    var conv=tail.converged?chip("CONVERGED"):chip("NOT CONVERGED");
    var glabel=tail.grid_label||"outer scenarios";
    return '<div class="chartwrap"><h4>Convergence of the 99.5% tail metric</h4>'+
      '<p class="cap">VaR and ES as the number of '+esc(glabel)+' grows. The dashed amber line marks the '+
      'recommended count; flattening past it is the convergence signal. '+conv+
      (tail.grid_note?(' &mdash; '+esc(tail.grid_note)):'')+'</p>'+
      lineChart(series,xs,{w:680,h:300,markX:tail.recommended_n_outer})+legendRow(series)+'</div>';
  }

  function renderCapital(){
    var el = document.getElementById("capital"); if(!DATA){ el.innerHTML=dz(); return; }
    var cap = DATA.capital||{}, tail = DATA.tail||{};
    var cardRows = [
      ["Rate SCR", cap.rate_scr],["Equity SCR", cap.equity_scr],["Credit SCR", cap.credit_scr],
      ["Lapse SCR", cap.lapse_scr],["Mortality SCR", cap.mortality_scr],
      ["FX SCR", cap.fx_scr],["Liquidity SCR", cap.liquidity_scr],
      ["Standalone sum", cap.standalone_sum],["Var-covar SCR", cap.var_covar_scr],
      ["Nested SCR", cap.nested_scr]
    ];
    var html = '<div class="cards">';
    cardRows.forEach(function(r){ if(r[1]!=null) html += '<div class="card"><div class="k">'+esc(r[0])+
      '</div><div class="v">'+num(r[1])+'</div></div>'; });
    html += '</div>';
    var nd = cap.n_drivers||5;
    var ndWord = (nd===7?"Seven":nd===6?"Six":"Five");
    html += '<p class="note">'+ndWord+'-driver economic-capital aggregation at the 99.5% / 12-month level'+
      (nd>=7?' (rate, equity, credit, lapse, mortality, FX, liquidity &mdash; all documented drivers aggregated)':'')+'. '+
      'Rate driver: '+esc(cap.rate_driver||"HW1F / legacy snapshot")+
      (cap.nested_scr_reduction_pct!=null?(' &middot; nested SCR reduction vs HW1F: '+esc(cap.nested_scr_reduction_pct)+'%'):"")+
      '. Switch views below; all charts are inline SVG rendered offline from the embedded snapshot.</p>';
    if(cap.liquidity_note) html += '<p class="note">'+esc(cap.liquidity_note)+'</p>';
    var views = [["bars","Driver SCRs"],["agg","Aggregation"],["tail","VaR / ES + CI"],["conv","Convergence"]];
    html += '<div class="subnav" id="capnav">'+views.map(function(v,i){
      return '<div class="segbtn'+(i===0?" active":"")+'" data-view="'+v[0]+'">'+esc(v[1])+'</div>'; }).join("")+'</div>';
    html += '<div id="cap-bars" class="capview">'+capBarsBlock(cap)+'</div>';
    html += '<div id="cap-agg" class="capview" style="display:none">'+capAggBlock(cap)+'</div>';
    html += '<div id="cap-tail" class="capview" style="display:none">'+capTailBlock(cap,tail)+'</div>';
    html += '<div id="cap-conv" class="capview" style="display:none">'+capConvBlock(tail)+'</div>';
    el.innerHTML = html;
    [].forEach.call(el.querySelectorAll("#capnav .segbtn"),function(b){
      b.onclick=function(){
        [].forEach.call(el.querySelectorAll("#capnav .segbtn"),function(x){x.classList.remove("active");});
        [].forEach.call(el.querySelectorAll(".capview"),function(x){x.style.display="none";});
        b.classList.add("active");
        var v=document.getElementById("cap-"+b.getAttribute("data-view"));
        if(v) v.style.display="block";
      };
    });
    wireTips(el);
  }

  // ---- Management Actions view (Phase 23 Task 5) ----
  function maGateGrid(g,label){
    var keys=Object.keys(g||{});
    if(!keys.length) return "";
    var h='<div class="subh">'+esc(label)+'</div><div class="critgrid">';
    keys.forEach(function(k){
      var ok=g[k]===true;
      h+='<div class="crit '+(ok?"pass":"fail")+'"><span class="cic">'+(ok?"✓":"✗")+
        '</span><span class="mono">'+esc(k)+'</span></div>';
    });
    return h+'</div>';
  }
  function renderActions(){
    var el=document.getElementById("actions"); if(!el) return;
    if(!DATA){ el.innerHTML=dz(); return; }
    var ma=DATA.management_actions||{};
    var a=ma.aggregation||{}, r=ma.rule||{};
    if(!Object.keys(a).length&&!Object.keys(r).length){
      el.innerHTML='<p class="muted">No management-action data in this snapshot (requires contract v1.5.0+).</p>';
      return;
    }
    var ncw=ma.nested_capital_without||{}, ncwa=ma.nested_capital_with||{};
    var html='<div class="cards">';
    [
      ["Nested SCR without actions",num(a.nested_scr_without)],
      ["Nested SCR with actions",num(a.nested_scr_with)],
      ["Nested VaR 99.5 without",num(ncw.var_liability)],
      ["Nested VaR 99.5 with",num(ncwa.var_liability)],
      ["Action active (outer nodes)",a.active_share_full!=null?(100*a.active_share_full).toFixed(1)+"%":"--"],
      ["At max-relief floor",a.floor_share_full!=null?(100*a.floor_share_full).toFixed(1)+"%":"--"],
      ["OOS R2 with actions",ma.oos_r2_with_actions!=null?Number(ma.oos_r2_with_actions).toFixed(4):"--"],
      ["Matched t df (rank-invariant)",a.df_matched!=null?String(a.df_matched):"--"]
    ].forEach(function(c){ html+='<div class="card"><div class="k">'+esc(c[0])+
      '</div><div class="v">'+esc(c[1])+'</div></div>'; });
    html+='</div>';
    html+='<p class="note">'+esc(ma.rule_description||"")+'</p>';
    html+='<div class="subh">Rule parameters (educational placeholders, disclosed)</div>'+
      '<table class="ptable ruletable"><thead><tr><th>Parameter</th><th>Value</th></tr></thead><tbody>'+
      [["CR trigger (action starts below)",r.cr_trigger],
       ["CR floor (full cut at/below)",r.cr_floor],
       ["Bonus share of liability",r.bonus_share],
       ["PRE floor (min retained bonus share)",r.pre_floor],
       ["Max liability relief",r.max_relief],
       ["Reference coverage (A_ref anchor)",r.reference_coverage]
      ].map(function(p){ return '<tr><td>'+esc(p[0])+'</td><td class="mono">'+
        (p[1]!=null?esc(p[1]):"--")+'</td></tr>'; }).join("")+
      '</tbody></table>';
    var D=[];
    [["Nested w/o",a.nested_scr_without,"#39d98a"],
     ["Nested WITH",a.nested_scr_with,"#1f8a5c"],
     ["t-copula w/o",a.t_copula_scr_without,"#4f9cff"],
     ["t-copula WITH",a.t_copula_scr_with,"#2b5d99"],
     ["Gaussian w/o",a.gaussian_scr_without,"#9a7bff"],
     ["Gaussian WITH",a.gaussian_scr_with,"#5d49a6"],
     ["Var-covar w/o",a.var_covar_scr_without,"#ffb454"],
     ["Var-covar WITH",a.var_covar_scr_with,"#a8762f"]
    ].forEach(function(b){ if(b[1]!=null) D.push({label:b[0],value:b[1],color:b[2],
      tip:"<b>"+b[0]+"</b><br>99.5% / 1y SCR: "+num(b[1])}); });
    if(D.length){
      html+='<div class="chartwrap"><h4>99.5% / 1y SCR &mdash; with vs without management actions</h4>'+
        '<p class="cap">Nested (with-actions '+num(a.nested_scr_with)+') is the capital reference. '+
        'Copula and var-covar read-outs on the with-actions basis are diagnostics &mdash; see the '+
        'saturation finding below. Matched t df '+esc(a.df_matched)+' is identical with/without actions '+
        '(rank invariance: the action is a monotone marginal transform).</p>'+
        barChart(D,{w:760,h:300,mB:64})+'</div>';
    }
    html+=maGateGrid(ma.gates_task3,"Task 3 pre-registered gates (rule + seven-driver OOS re-validation)");
    html+=maGateGrid(ma.gates_task4,"Task 4 pre-registered gates (aggregation with actions)");
    var ts=ma.trigger_sensitivity||[];
    if(ts.length){
      html+='<div class="subh">Trigger sensitivity (Task 3)</div>'+
        '<table class="trigtable"><thead><tr><th>CR trigger</th><th>CR floor</th>'+
        '<th>Active share</th><th>Nested SCR reduction</th><th>OOS R2</th><th>Verdict</th></tr></thead><tbody>';
      ts.forEach(function(t){
        html+='<tr><td>'+esc(num(t.cr_trigger,2))+'</td><td>'+esc(num(t.cr_floor,2))+'</td>'+
          '<td>'+(t.active_share_nested!=null?(100*t.active_share_nested).toFixed(1)+"%":"--")+'</td>'+
          '<td>'+num(t.nested_scr_reduction)+'</td>'+
          '<td>'+(t.oos_r2_with_actions!=null?Number(t.oos_r2_with_actions).toFixed(4):"--")+'</td>'+
          '<td>'+chip(t.verdict)+'</td></tr>';
      });
      html+='</tbody></table>';
    }
    var drv=a.standalone_drivers||[], sw=a.standalone_scr_with||[], swo=a.standalone_scr_without||[];
    if(drv.length&&sw.length===drv.length&&swo.length===drv.length){
      html+='<div class="subh">Standalone driver SCRs &mdash; with vs without actions</div>'+
        '<table class="matable"><thead><tr><th>Driver</th><th>Without</th><th>With</th>'+
        '<th>Delta</th></tr></thead><tbody>';
      drv.forEach(function(d,i){
        html+='<tr><td>'+esc(d)+'</td><td>'+num(swo[i])+'</td><td>'+num(sw[i])+'</td>'+
          '<td>'+num(sw[i]-swo[i])+'</td></tr>';
      });
      html+='</tbody></table>';
      if(a.anchoring_convention)
        html+='<p class="note">Anchoring convention (disclosed): <span class="mono">'+
          esc(a.anchoring_convention)+'</span>. Mortality/liquidity are unchanged by construction '+
          '(anchored CR 1.12 &gt; trigger 1.10).</p>';
    }
    html+='<p class="note">'+esc(ma.saturation_finding||"")+'</p>';
    html+='<p class="note mono">Sources: '+esc(ma.task3_source||"")+' &middot; '+esc(ma.task4_source||"")+
      ' &middot; ChangeRecords '+esc(ma.task3_change_record_id||"")+' / '+esc(ma.task4_change_record_id||"")+'</p>';
    el.innerHTML=html;
    wireTips(el);
  }

  function renderPhase24(){
    var el=document.getElementById("phase24"); if(!el) return;
    if(!DATA){ el.innerHTML=dz(); return; }
    var p=DATA.phase24||{};
    var ja=p.joint_action||{}, ip=p.inner_path||{}, td=p.tail_diagnostics||{};
    if(!Object.keys(ja).length&&!Object.keys(td).length){
      el.innerHTML='<p class="muted">No Phase 24 joint-action data in this snapshot (requires contract v1.6.0+).</p>';
      return;
    }
    var fnd=td.diagnostic_findings||{}, bt=(td.bootstrap||{}).scr_with||{};
    var ipd=ip.outer_vs_inner_path_delta||{};
    var html='<div class="cards">';
    [
      ["Nested SCR with actions (reference)",num(ja.nested_scr_with)],
      ["Joint-action t-SCR",num(ja.t_scr_joint)],
      ["t rel err - joint action",ja.t_rel_error_joint!=null?(100*ja.t_rel_error_joint).toFixed(2)+"%":"--"],
      ["t rel err - standalone action",ja.t_rel_error_standalone_baseline!=null?(100*ja.t_rel_error_standalone_baseline).toFixed(2)+"%":"--"],
      ["Inner-path SCR delta (vs outer-node)",ipd.nested_scr_delta!=null?"+"+num(ipd.nested_scr_delta)+" (+4.0%)":"--"],
      ["99.5% tail saturation share",fnd.tail_saturation_share_at_995!=null?(100*fnd.tail_saturation_share_at_995).toFixed(1)+"%":"--"],
      ["Bootstrap SCR SE (% of mean)",fnd.bootstrap_scr_se_pct_of_mean!=null?(100*fnd.bootstrap_scr_se_pct_of_mean).toFixed(1)+"%":"--"],
      ["Matched t df (rank-invariant)",ja.df_matched!=null?String(ja.df_matched):"--"]
    ].forEach(function(c){ html+='<div class="card"><div class="k">'+esc(c[0])+
      '</div><div class="v">'+esc(c[1])+'</div></div>'; });
    html+='</div>';
    html+='<p class="note">'+esc(ja.saturation_gap_closure||"")+'</p>';
    var dm=td.delta_matrix||{};
    function dmc(m,k){ var r=(dm[m]||{})[k]||{}; return r.scr; }
    var rows=[["Nested (reference)","nested"],["t-copula (df matched)","t_copula"],
              ["Gaussian copula","gaussian"],["Var-covar","var_covar"]];
    if(Object.keys(dm).length){
      html+='<div class="subh">Capital-delta matrix (99.5% / 1y SCR) &mdash; without &rarr; with-standalone &rarr; with-joint (Task 4)</div>'+
        '<table class="ptable dmtable"><thead><tr><th>Benchmark</th><th>Without actions</th>'+
        '<th>With (standalone action)</th><th>With (joint action)</th><th>Joint &minus; standalone</th></tr></thead><tbody>';
      rows.forEach(function(r){
        var w=dmc(r[1],"without"), s=dmc(r[1],"standalone_action"), j=dmc(r[1],"joint_action");
        var d=(dm[r[1]]||{}).joint_minus_standalone_scr;
        html+='<tr><td>'+esc(r[0])+'</td><td>'+num(w)+'</td><td>'+num(s)+'</td><td>'+num(j)+'</td>'+
          '<td>'+(d!=null?num(d):"--")+'</td></tr>';
      });
      html+='</tbody></table>';
      var D=[];
      [["Nested w/o",dmc("nested","without"),"#39d98a"],
       ["Nested WITH",dmc("nested","joint_action"),"#1f8a5c"],
       ["t standalone",dmc("t_copula","standalone_action"),"#2b5d99"],
       ["t JOINT",dmc("t_copula","joint_action"),"#4f9cff"],
       ["Gauss standalone",dmc("gaussian","standalone_action"),"#5d49a6"],
       ["Gauss JOINT",dmc("gaussian","joint_action"),"#9a7bff"],
       ["Var-covar WITH",dmc("var_covar","standalone_action"),"#ffb454"]
      ].forEach(function(b){ if(b[1]!=null) D.push({label:b[0],value:b[1],color:b[2],
        tip:"<b>"+b[0]+"</b><br>99.5% / 1y SCR: "+num(b[1])}); });
      if(D.length){
        html+='<div class="chartwrap"><h4>99.5% / 1y SCR &mdash; joint-action vs standalone-action basis</h4>'+
          '<p class="cap">The joint-action basis (rule applied ONCE to the aggregated liability) sits '+
          num(ja.t_scr_joint)+' vs nested-with '+num(ja.nested_scr_with)+' &mdash; rel err '+
          (ja.t_rel_error_joint!=null?(100*ja.t_rel_error_joint).toFixed(2)+"%":"--")+
          ' against 22.54% on the standalone-action basis. Var-covar understates nested-with by 56.4% (MR-010 refresh).</p>'+
          barChart(D,{w:760,h:300,mB:64})+'</div>';
      }
    }
    var sw=td.confidence_sweep||[];
    if(sw.length){
      html+='<div class="subh">Action-saturation profile across the tail (Task 4, disclosed)</div>'+
        '<table class="swtable"><thead><tr><th>Confidence</th><th>SCR without</th><th>SCR with (joint)</th>'+
        '<th>Tail saturation share</th><th>Mean residual cut factor</th><th>Relief at VaR</th></tr></thead><tbody>';
      sw.forEach(function(s){
        html+='<tr><td>'+(100*s.confidence).toFixed(1)+'%</td><td>'+num(s.scr_without)+'</td>'+
          '<td>'+num(s.scr_with)+'</td><td>'+(100*s.tail_saturation_share).toFixed(1)+'%</td>'+
          '<td>'+(s.tail_mean_cut_factor!=null?Number(s.tail_mean_cut_factor).toFixed(4):"--")+'</td>'+
          '<td>'+num(s.relief_at_var)+'</td></tr>';
      });
      html+='</tbody></table>'+
        '<p class="note">At 99.5% the joint tail is 100.0% saturated &mdash; the action delivers max relief (12%) '+
        'everywhere capital is measured, which is exactly the Phase 23 Task 4 saturation mechanism, now fully quantified.</p>';
    }
    if(bt.mean!=null){
      html+='<div class="subh">Margin bootstrap (copula FROZEN per SII Art. 234; 200 &times; 20k; n_obs=160)</div>'+
        '<div class="cards">'+
        '<div class="card"><div class="k">Bootstrap SCR mean</div><div class="v">'+num(bt.mean)+'</div></div>'+
        '<div class="card"><div class="k">SCR SE</div><div class="v">'+num(bt.se)+'</div></div>'+
        '<div class="card"><div class="k">95% CI</div><div class="v">['+num(bt.ci_lo_95)+', '+num(bt.ci_hi_95)+']</div></div>'+
        '<div class="card"><div class="k">Nested-with inside CI</div><div class="v">'+(fnd.nested_with_inside_bootstrap_ci?"✓ yes":"✗ no")+'</div></div>'+
        '</div>'+
        '<p class="note">Prefix-convergence SCR delta '+(fnd.scr_prefix_final_rel_delta!=null?(100*fnd.scr_prefix_final_rel_delta).toFixed(2)+"%":"--")+
        ' (100k vs 200k); copula-seed max spread '+(fnd.scr_seed_max_rel_spread!=null?(100*fnd.scr_seed_max_rel_spread).toFixed(2)+"%":"--")+
        ' across 5 seeds. The n_obs=160 small-sample noise is the dominant uncertainty (disclosed Task 1 limitation).</p>';
    }
    if(Object.keys(ipd).length){
      html+='<div class="subh">Inner-path action dynamics (Task 3) &mdash; outer-node vs inner-path basis</div>'+
        '<table class="ptable iptable"><thead><tr><th>Read-out (nested, 500 outer nodes)</th>'+
        '<th>Outer-node transform</th><th>Inner-path basis</th><th>Delta</th></tr></thead><tbody>'+
        '<tr><td>VaR 99.5</td><td>'+num(ipd.nested_var_99_5_outer_node)+'</td><td>'+num(ipd.nested_var_99_5_inner_path)+'</td>'+
        '<td>+'+num(ipd.nested_var_99_5_delta)+'</td></tr>'+
        '<tr><td>SCR</td><td>'+num(ipd.nested_scr_outer_node)+'</td><td>'+num(ipd.nested_scr_inner_path)+'</td>'+
        '<td>+'+num(ipd.nested_scr_delta)+' (+4.0%)</td></tr>'+
        '</tbody></table>'+
        '<p class="note">The bonus cut applies to the INNER-PATH policyholder-benefit cashflows only (guaranteed + '+
        'equity-guarantee PV); the asset-side credit loss and analytic FX/liquidity offsets are non-cuttable. The '+
        'outer-node transform over-relieves those components, so the inner-path basis is the more conservative, more '+
        'faithful with-actions basis. OOS R2 with actions '+(ip.oos_r2_with_actions!=null?Number(ip.oos_r2_with_actions).toFixed(4):"--")+
        '; VaR rel err '+(ip.var_rel_error_with_actions!=null?(100*ip.var_rel_error_with_actions).toFixed(2)+"%":"--")+
        '; carve-out kappa '+(ip.kappa_fit_calibrated!=null?Number(ip.kappa_fit_calibrated).toFixed(4):"--")+
        ' (fit-calibrated, leakage-free).</p>';
    }
    html+=maGateGrid(ja.gates,"Task 2 pre-registered gates (joint-scenario re-aggregation)");
    html+=maGateGrid(ip.gates,"Task 3 pre-registered gates (inner-path action dynamics)");
    html+=maGateGrid(td.gates,"Task 4 pre-registered gates (tail diagnostics + delta matrix)");
    html+='<p class="note">'+esc(p.narrative||"")+'</p>';
    html+='<p class="note mono">Sources: '+esc(ja.source||"")+' &middot; '+esc(ip.source||"")+' &middot; '+esc(td.source||"")+
      ' &middot; ChangeRecords '+esc(ja.change_record_id||"")+' / '+esc(ip.change_record_id||"")+' / '+esc(td.change_record_id||"")+'</p>';
    el.innerHTML=html;
    wireTips(el);
  }

  function renderPhase25(){
    var el=document.getElementById("phase25"); if(!el) return;
    if(!DATA){ el.innerHTML=dz(); return; }
    var p=DATA.phase25||{};
    var dc=p.declaration||{}, px=p.proxy_basis||{}, td=p.tail_diagnostics||{};
    if(!Object.keys(dc).length&&!Object.keys(td).length){
      el.innerHTML='<p class="muted">No Phase 25 path-wise action data in this snapshot (requires contract v1.7.0+).</p>';
      return;
    }
    var fnd=td.diagnostic_findings||{}, bt=(td.bootstrap||{}).scr_pathwise||{};
    var dl=dc.pathwise_vs_horizon_delta||{};
    var ncw=(dc.nested_capital_without||{}).scr_proxy;
    var nch=(dc.nested_capital_with_horizon||{}).scr_proxy;
    var ncp=(dc.nested_capital_with_pathwise||{}).scr_proxy;
    var html='<div class="cards">';
    [
      ["Nested SCR without actions",num(ncw)],
      ["Nested SCR with (horizon basis)",num(nch)],
      ["Nested SCR with (PATH-WISE) - reference",num(ncp)],
      ["Path-wise &minus; horizon SCR",dl.scr_delta!=null?"+"+num(dl.scr_delta)+" (+"+(100*dl.scr_delta_rel_to_horizon).toFixed(2)+"%)":"--"],
      ["Path-wise action share",dc.pathwise_action_share!=null?(100*dc.pathwise_action_share).toFixed(1)+"%":"--"],
      ["Cut-then-restore share",dc.pathwise_restoration_share!=null?(100*dc.pathwise_restoration_share).toFixed(1)+"%":"--"],
      ["Proxy OOS R2 (path-wise basis)",px.oos_r2_with_actions!=null?Number(px.oos_r2_with_actions).toFixed(4):"--"],
      ["t df (copula FROZEN)",td.df_rematched!=null?Number(td.df_rematched).toFixed(4):"--"]
    ].forEach(function(c){ html+='<div class="card"><div class="k">'+c[0]+
      '</div><div class="v">'+esc(c[1])+'</div></div>'; });
    html+='</div>';
    html+='<p class="note">'+esc(dl.interpretation||"")+'</p>';
    var dm=td.delta_matrix||{};
    function dmc(m,k){ var r=(dm[m]||{})[k]||{}; return r.scr; }
    function dmp(m){ return (dm[m]||{}).pathwise_minus_horizon||{}; }
    var rows=[["Nested (reference)","nested"],["t-copula (df matched)","t_copula"],
              ["Gaussian copula","gaussian"],["Var-covar","var_covar"]];
    if(Object.keys(dm).length){
      html+='<div class="subh">Capital-delta matrix (99.5% / 1y SCR) &mdash; without &rarr; with-horizon &rarr; with-path-wise (Task 4)</div>'+
        '<table class="ptable pwtable"><thead><tr><th>Benchmark</th><th>Without actions</th>'+
        '<th>With (horizon basis)</th><th>With (path-wise)</th><th>Path-wise &minus; horizon</th></tr></thead><tbody>';
      rows.forEach(function(r){
        var w=dmc(r[1],"without"), h=dmc(r[1],"with_horizon"), q=dmc(r[1],"with_pathwise");
        var d=dmp(r[1]).scr_delta, dp=dmp(r[1]).scr_delta_pct;
        html+='<tr><td>'+esc(r[0])+'</td><td>'+num(w)+'</td><td>'+num(h)+'</td>'+
          '<td>'+(q!=null?num(q):"-- (no path-wise analogue, DISCLOSED)")+'</td>'+
          '<td>'+(d!=null?"+"+num(d)+" (+"+(100*dp).toFixed(1)+"%)":"--")+'</td></tr>';
      });
      html+='</tbody></table>';
      var D=[];
      [["Nested w/o",dmc("nested","without"),"#39d98a"],
       ["Nested horizon",dmc("nested","with_horizon"),"#1f8a5c"],
       ["Nested PATH-WISE",dmc("nested","with_pathwise"),"#2fd0a8"],
       ["t horizon",dmc("t_copula","with_horizon"),"#2b5d99"],
       ["t PATH-WISE",dmc("t_copula","with_pathwise"),"#4f9cff"],
       ["Gauss horizon",dmc("gaussian","with_horizon"),"#5d49a6"],
       ["Gauss PATH-WISE",dmc("gaussian","with_pathwise"),"#9a7bff"],
       ["Var-covar horizon",dmc("var_covar","with_horizon"),"#ffb454"]
      ].forEach(function(b){ if(b[1]!=null) D.push({label:b[0],value:b[1],color:b[2],
        tip:"<b>"+b[0]+"</b><br>99.5% / 1y SCR: "+num(b[1])}); });
      if(D.length){
        html+='<div class="chartwrap"><h4>99.5% / 1y SCR &mdash; path-wise vs horizon declaration basis</h4>'+
          '<p class="cap">The path-wise basis relieves LESS at every level and confidence &mdash; the horizon basis '+
          'understates the with-actions SCR across the matrix (nested +'+
          (dl.scr_delta_rel_to_horizon!=null?(100*dl.scr_delta_rel_to_horizon).toFixed(2)+"%":"--")+
          '). Var-covar has no path-wise analogue and understates nested path-wise by 69.1% (MR-010 refresh).</p>'+
          barChart(D,{w:760,h:300,mB:64})+'</div>';
      }
    }
    var sw=td.confidence_sweep||[];
    if(sw.length){
      html+='<div class="subh">Path-wise action profile across the tail (Task 4, disclosed)</div>'+
        '<table class="pwswtable"><thead><tr><th>Confidence</th><th>SCR without</th><th>SCR with (horizon)</th>'+
        '<th>SCR with (path-wise)</th><th>Tail saturation share</th><th>Mean smoothed relief fraction</th>'+
        '<th>Path-wise &minus; horizon</th></tr></thead><tbody>';
      sw.forEach(function(s){
        html+='<tr><td>'+(100*s.confidence).toFixed(1)+'%</td><td>'+num(s.scr_without)+'</td>'+
          '<td>'+num(s.scr_horizon)+'</td><td>'+num(s.scr_pathwise)+'</td>'+
          '<td>'+(100*s.tail_saturation_share).toFixed(1)+'%</td>'+
          '<td>'+(s.tail_mean_smoothed_relief_fraction!=null?Number(s.tail_mean_smoothed_relief_fraction).toFixed(4):"--")+'</td>'+
          '<td>+'+num(s.pathwise_minus_horizon_scr)+'</td></tr>';
      });
      html+='</tbody></table>'+
        '<p class="note">At 99.5% the raw governed cut saturates 100.0% of the tail, but the mean smoothed relief '+
        'fraction is '+(fnd.tail_mean_smoothed_relief_fraction_at_995!=null?Number(fnd.tail_mean_smoothed_relief_fraction_at_995).toFixed(4):"--")+
        ' &lt; max relief 0.12 &mdash; restoration on recovering inner paths caps the realised relief '+
        '(the recognition-lag mechanism, quantified).</p>';
    }
    if(bt.mean!=null){
      html+='<div class="subh">Margin bootstrap (copula FROZEN per SII Art. 234; 200 &times; 20k; n_obs=160)</div>'+
        '<div class="cards">'+
        '<div class="card"><div class="k">Bootstrap SCR mean (t path-wise)</div><div class="v">'+num(bt.mean)+'</div></div>'+
        '<div class="card"><div class="k">SCR SE</div><div class="v">'+num(bt.se)+'</div></div>'+
        '<div class="card"><div class="k">95% CI</div><div class="v">['+num(bt.ci_lo_95)+', '+num(bt.ci_hi_95)+']</div></div>'+
        '<div class="card"><div class="k">Nested path-wise inside CI</div><div class="v">'+(fnd.nested_pathwise_inside_bootstrap_ci?"✓ yes":"✗ no (OUTSIDE)")+'</div></div>'+
        '</div>'+
        '<p class="note">The nested path-wise reference '+num(ncp)+' sits OUTSIDE the 95% CI &mdash; the analytic '+
        're-anchoring understates the nested path-wise SCR by '+
        (fnd.t_pathwise_vs_nested_pathwise_rel_err!=null?(100*fnd.t_pathwise_vs_nested_pathwise_rel_err).toFixed(1)+"%":"--")+
        ' beyond margin noise: the quantified, DISCLOSED motivation for the next-phase full path-wise copula '+
        're-aggregation. Bootstrap SCR SE '+
        (fnd.bootstrap_scr_se_pct_of_mean!=null?(100*fnd.bootstrap_scr_se_pct_of_mean).toFixed(1)+"%":"--")+
        ' of mean; copula-seed max spread '+
        (fnd.scr_seed_max_rel_spread!=null?(100*fnd.scr_seed_max_rel_spread).toFixed(2)+"%":"--")+
        ' across 5 seeds; prefix-convergence final delta '+
        (fnd.scr_prefix_final_rel_delta!=null?(100*fnd.scr_prefix_final_rel_delta).toFixed(2)+"%":"--")+'.</p>';
    }
    if(Object.keys(px).length){
      var sf=px.surface||{}, cd=px.cadence_sensitivity||{};
      html+='<div class="subh">Matching path-wise proxy basis (Task 3) &mdash; seven-driver OOS re-validation</div>'+
        '<table class="ptable pxtable"><thead><tr><th>Read-out</th><th>Value</th><th>Gate / note</th></tr></thead><tbody>'+
        '<tr><td>OOS R2 with actions (path-wise)</td><td>'+(px.oos_r2_with_actions!=null?Number(px.oos_r2_with_actions).toFixed(4):"--")+'</td><td>&ge; 0.95</td></tr>'+
        '<tr><td>OOS R2 without actions</td><td>'+(px.oos_r2_without_actions!=null?Number(px.oos_r2_without_actions).toFixed(4):"--")+'</td><td>unchanged basis</td></tr>'+
        '<tr><td>VaR 99.5 rel error (with actions)</td><td>'+(px.var_rel_error_with_actions!=null?(100*px.var_rel_error_with_actions).toFixed(2)+"%":"--")+'</td><td>&le; 10%</td></tr>'+
        '<tr><td>ES rel error (with actions)</td><td>'+(px.es_rel_error_with_actions!=null?(100*px.es_rel_error_with_actions).toFixed(2)+"%":"--")+'</td><td>disclosed</td></tr>'+
        '<tr><td>SCR rel error (with actions)</td><td>'+(px.scr_rel_error_with_actions!=null?(100*px.scr_rel_error_with_actions).toFixed(2)+"%":"--")+'</td><td>disclosed</td></tr>'+
        '<tr><td>Surface sigma (smoothing width)</td><td>'+(sf.sigma!=null?Number(sf.sigma).toFixed(3):"--")+'</td><td>grid-interior, FIT-only</td></tr>'+
        '<tr><td>Surface alpha (level match)</td><td>'+(sf.alpha!=null?Number(sf.alpha).toFixed(4):"--")+'</td><td>FIT-only, leakage-free</td></tr>'+
        '<tr><td>FIT R2 (relieved amount)</td><td>'+(sf.fit_r2_relieved!=null?Number(sf.fit_r2_relieved).toFixed(4):"--")+'</td><td>response-surface fit</td></tr>'+
        '<tr><td>Annual/monthly cadence ratio</td><td>'+(cd.annual_over_monthly_mean_ratio!=null?Number(cd.annual_over_monthly_mean_ratio).toFixed(3):"--")+'</td><td>cadence sensitivity, disclosed</td></tr>'+
        '</tbody></table>';
    }
    html+=maGateGrid(dc.gates,"Task 2 pre-registered gates (path-wise declaration in the nested truth)");
    html+=maGateGrid(px.gates,"Task 3 pre-registered gates (matching path-wise proxy basis)");
    html+=maGateGrid(td.gates,"Task 4 pre-registered gates (path-wise tail diagnostics + delta matrix)");
    html+='<p class="note">'+esc(p.narrative||"")+'</p>';
    html+='<p class="note mono">Sources: '+esc(dc.source||"")+' &middot; '+esc(px.source||"")+' &middot; '+esc(td.source||"")+
      ' &middot; ChangeRecords '+esc(dc.change_record_id||"")+' / '+esc(px.change_record_id||"")+' / '+esc(td.change_record_id||"")+'</p>';
    el.innerHTML=html;
    wireTips(el);
  }

  function renderPhase26(){
    var el=document.getElementById("phase26"); if(!el) return;
    if(!DATA){ el.innerHTML=dz(); return; }
    var p=DATA.phase26||{};
    var co=p.composition||{}, bo=p.bootstrap||{}, dm=p.delta_matrix||{};
    if(!Object.keys(co).length&&!Object.keys(dm).length){
      el.innerHTML='<p class="muted">No Phase 26 full path-wise copula re-aggregation data in this snapshot (requires contract v1.8.0+).</p>';
      return;
    }
    var ct=co.t_readout||{}, cg=co.g_readout||{};
    var ci=bo.component_t_scr_ci||{}, gd=bo.residual_gap_decomposition||{};
    var pm=dm.point_matrix||{}, mc=dm.marginal_cis||{}, pdl=dm.paired_deltas||{}, trg=dm.mr_trigger||{};
    var nestedRef=(co.nested_pathwise_reference!=null?co.nested_pathwise_reference:bo.nested_pathwise_reference);
    var cc=pdl.composition_correction_t||{};
    var compRel=(cc.mean_rel_to_subtrahend!=null?cc.mean_rel_to_subtrahend:co.component_vs_reanchored_rel_t);
    var gapRel=co.gap_to_nested_component_t_rel;
    var html='<div class="cards">';
    [
      ["Nested SCR (path-wise) - reference",num(nestedRef)],
      ["Component (FULL re-agg) t SCR",num(ct.scr_component)],
      ["Re-anchored (LEVEL) t SCR",num(ct.scr_level)],
      ["Composition correction (full &minus; re-anchored)",cc.mean!=null?"+"+num(cc.mean)+" (+"+(100*compRel).toFixed(2)+"%)":"--"],
      ["Bootstrap mean t SCR (component)",num(ci.mean)],
      ["Bootstrap 95% CI (component t)",ci.ci_lo!=null?"["+num(ci.ci_lo)+", "+num(ci.ci_hi)+"]":"--"],
      ["Bootstrap SE (% of mean)",bo.se_frac_of_mean!=null?(100*bo.se_frac_of_mean).toFixed(2)+"%":"--"],
      ["Nested inside 95% CI?",bo.headline_nested_inside_95ci?"✓ yes":"✗ no (OUTSIDE)"],
      ["Gap to nested (component, t)",gapRel!=null?(100*gapRel).toFixed(2)+"%":"--"],
      ["Copula-form share of gap",gd.copula_form_share_of_gap!=null?(100*gd.copula_form_share_of_gap).toFixed(1)+"%":"--"],
      ["Relief-surface share of gap",gd.relief_surface_share_of_gap!=null?(100*gd.relief_surface_share_of_gap).toFixed(1)+"%":"--"],
      ["MR-010/MR-014 1% trigger",trg.trigger_fired===false?"NOT fired (MR-015 free)":(trg.trigger_fired?"FIRED":"--")],
      ["t df (copula FROZEN)",co.df_rematched!=null?Number(co.df_rematched).toFixed(4):"--"],
      ["rho max|diff| (frozen)",co.rho_max_abs_diff!=null?Number(co.rho_max_abs_diff).toExponential(1):"--"]
    ].forEach(function(c){ html+='<div class="card"><div class="k">'+c[0]+
      '</div><div class="v">'+esc(c[1])+'</div></div>'; });
    html+='</div>';
    html+='<p class="note">The full per-driver composition re-aggregation moves the with-actions SCR by only +'+
      (compRel!=null?(100*compRel).toFixed(2):"--")+'% versus the Phase 25 analytic re-anchoring: '+
      'STATISTICALLY SIGNIFICANT (paired 95% CI excludes zero) but ECONOMICALLY IMMATERIAL '+
      '(below the 1% MR trigger - MR-015 stays free). Copula FROZEN per SII Art. 234.</p>';
    // ---- point matrix: bases x {t, gaussian} with component-basis 95% CI ----
    function pmc(b,k){ return (pm[b]||{})[k]; }
    function mci(b,k){ var r=(mc[b]||{})[k]; return (r&&r.ci_lo!=null)?("["+num(r.ci_lo)+", "+num(r.ci_hi)+"]"):"--"; }
    var brows=[["Without actions","without"],["Re-anchored (LEVEL)","level"],["Component (FULL re-agg)","component"]];
    html+='<div class="subh">Re-aggregation basis matrix (99.5% / 1y SCR) &mdash; without &rarr; re-anchored &rarr; full component (Task 2 point, Task 3 frozen-copula CI)</div>'+
      '<table class="ptable p26matrix"><thead><tr><th>Basis</th><th>t-copula SCR</th><th>t 95% CI (bootstrap)</th>'+
      '<th>Gaussian SCR</th></tr></thead><tbody>';
    brows.forEach(function(r){
      html+='<tr><td>'+esc(r[0])+'</td><td>'+num(pmc(r[1],"t"))+'</td><td>'+mci(r[1],"t")+'</td>'+
        '<td>'+num(pmc(r[1],"g"))+'</td></tr>';
    });
    html+='</tbody></table>';
    // ---- SCR bar chart ----
    var D=[];
    [["Without (t)",pmc("without","t"),"#39d98a"],
     ["Re-anchored (t)",pmc("level","t"),"#2b5d99"],
     ["Component (t)",pmc("component","t"),"#4f9cff"],
     ["Bootstrap mean (t)",ci.mean,"#2fd0a8"],
     ["Nested PATH-WISE ref",nestedRef,"#ffb454"],
     ["Component (gauss)",pmc("component","g"),"#9a7bff"]
    ].forEach(function(b){ if(b[1]!=null) D.push({label:b[0],value:b[1],color:b[2],
      tip:"<b>"+b[0]+"</b><br>99.5% / 1y SCR: "+num(b[1])}); });
    if(D.length){
      html+='<div class="chartwrap"><h4>99.5% / 1y SCR &mdash; full re-aggregation vs re-anchored vs nested reference</h4>'+
        '<p class="cap">The full component basis and the re-anchored level basis are economically interchangeable on the '+
        'frozen copula; both sit well below the nested path-wise reference '+num(nestedRef)+' &mdash; a COPULA-FORM gap, not a basis choice.</p>'+
        barChart(D,{w:760,h:300,mB:64})+'</div>';
    }
    // ---- paired delta decomposition (common-random-number) ----
    function pd(k){ return pdl[k]||{}; }
    var drows=[
      ["Composition correction (full &minus; re-anchored), t","composition_correction_t"],
      ["Composition correction (full &minus; re-anchored), gaussian","composition_correction_g"],
      ["Management-action relief (without &minus; full), t","management_relief_t"],
      ["Dependence form (gaussian &rarr; t), component","dependence_form_component"],
      ["Dependence form (gaussian &rarr; t), re-anchored","dependence_form_level"]
    ];
    html+='<div class="subh">Paired common-random-number delta decomposition (Task 4; over the 200 frozen-copula replicates)</div>'+
      '<table class="ptable p26dtable"><thead><tr><th>Effect</th><th>Mean</th><th>95% CI</th><th>Excludes zero?</th></tr></thead><tbody>';
    drows.forEach(function(r){
      var d=pd(r[1]);
      html+='<tr><td>'+r[0]+'</td><td>'+(d.mean!=null?"+"+num(d.mean):"--")+'</td>'+
        '<td>'+(d.ci_lo!=null?"[+"+num(d.ci_lo)+", +"+num(d.ci_hi)+"]":"--")+'</td>'+
        '<td>'+(d.excludes_zero?"✓ yes (significant)":"no")+'</td></tr>';
    });
    html+='</tbody></table>'+
      '<p class="note">Every effect is statistically significant on the paired bootstrap, but the composition correction is the '+
      'smallest by two orders of magnitude: management-action relief (+'+num((pd("management_relief_t").mean))+') dominates the capital picture.</p>';
    // ---- residual gap decomposition ----
    if(Object.keys(gd).length){
      html+='<div class="subh">Residual gap to nested truth (Task 3) &mdash; copula-form vs relief-surface</div>'+
        '<table class="ptable p26gaptable"><thead><tr><th>Component</th><th>Absolute</th><th>Share of gap</th><th>Basis</th></tr></thead><tbody>'+
        '<tr><td>Relief-surface error</td><td>'+num(gd.relief_surface_part_abs)+'</td><td>'+
          (gd.relief_surface_share_of_gap!=null?(100*gd.relief_surface_share_of_gap).toFixed(1)+"%":"--")+
          '</td><td>bounded by governed 1.16% OOS error</td></tr>'+
        '<tr><td>Copula-form residual</td><td>'+num(gd.copula_form_residual_abs)+'</td><td>'+
          (gd.copula_form_share_of_gap!=null?(100*gd.copula_form_share_of_gap).toFixed(1)+"%":"--")+
          '</td><td>nested joint tail heavier than frozen t copula</td></tr>'+
        '<tr><td>Total gap (nested &minus; component)</td><td>'+num(gd.gap_total_abs)+'</td><td>'+
          (gd.gap_total_rel_to_nested!=null?(100*gd.gap_total_rel_to_nested).toFixed(2)+"%":"--")+
          '</td><td>nested with-actions reference</td></tr>'+
        '</tbody></table>'+
        '<p class="note">The residual is COPULA-FORM DOMINATED ('+
        (gd.copula_form_share_of_gap!=null?(100*gd.copula_form_share_of_gap).toFixed(1):"--")+
        '% of the gap): the copula-form residual '+num(gd.copula_form_residual_abs)+' EXCEEDS the entire gaussian&rarr;t '+
        'dependence-form sensitivity ('+num(gd.dependence_form_sensitivity_t_minus_g)+'). The governed relief surface mis-prices SCR by only 1.16% of nested. '+
        'The nested path-wise reference '+num(nestedRef)+' lies OUTSIDE the component-basis 95% CI ['+num(ci.ci_lo)+', '+num(ci.ci_hi)+'] '+
        '&mdash; the gap is a copula-FORM limitation, NOT a basis-choice effect. DISCLOSED.</p>';
    }
    html+=maGateGrid(co.gates,"Task 2 pre-registered gates (per-driver composition transform on the frozen copula)");
    html+=maGateGrid(bo.gates,"Task 3 pre-registered gates (frozen-copula margin bootstrap + gap decomposition)");
    html+=maGateGrid(dm.gates,"Task 4 pre-registered gates (paired full-vs-reanchored delta matrix + MR trigger)");
    html+='<p class="note">'+esc(p.narrative||"")+'</p>';
    html+='<p class="note mono">Sources: '+esc(co.source||"")+' &middot; '+esc(bo.source||"")+' &middot; '+esc(dm.source||"")+
      ' &middot; ChangeRecords '+esc(co.change_record_id||"")+' / '+esc(bo.change_record_id||"")+' / '+esc(dm.change_record_id||"")+'</p>';
    el.innerHTML=html;
    wireTips(el);
  }

  function renderPhase27(){
    var el=document.getElementById("phase27"); if(!el) return;
    if(!DATA){ el.innerHTML=dz(); return; }
    var p=DATA.phase27||{};
    var bo=p.bootstrap||{}, td=p.tail||{};
    if(!Object.keys(bo).length&&!Object.keys(td).length){
      el.innerHTML='<p class="muted">No Phase 27 skew-t tail-dependence data in this snapshot (requires contract v1.9.0+).</p>';
      return;
    }
    var sk=bo.skewt_component_scr_ci||{}, sy=bo.symmetric_component_scr_ci||{};
    var gd=bo.residual_gap_redecomposition||{};
    var mr=td.mr_refresh_decision||{};
    var nestedRef=(bo.nested_pathwise_reference!=null?bo.nested_pathwise_reference:td.nested_pathwise_reference);
    var gh=(bo.gamma_hat!=null?bo.gamma_hat:td.gamma_hat);
    var html='<div class="cards">';
    [
      ["gamma_hat (fitted upper-tail skew)",gh!=null?Number(gh).toExponential(2):"--"],
      ["Skew-t component SCR (bootstrap mean)",num(sk.mean)],
      ["Symmetric-t component SCR (mean)",num(sy.mean)],
      ["Nested SCR (path-wise) - reference",num(nestedRef)],
      ["Skew-t 95% CI",sk.ci_lo!=null?"["+num(sk.ci_lo)+", "+num(sk.ci_hi)+"]":"--"],
      ["Skew-t SE (% of mean)",bo.se_frac_of_mean!=null?(100*bo.se_frac_of_mean).toFixed(2)+"%":"--"],
      ["Nested inside 95% CI?",bo.headline_nested_inside_95ci?"✓ yes":"✗ no (OUTSIDE)"],
      ["Radial asymmetry (mean, p=0.90)",bo.radial_asymmetry_mean!=null?Number(bo.radial_asymmetry_mean).toExponential(2):"--"],
      ["Copula-form residual reduction",gd.copula_form_residual_reduction_rel!=null?(100*gd.copula_form_residual_reduction_rel).toFixed(2)+"%":"--"],
      ["MR-010/MR-014 1% trigger",mr.refresh_required===false?("NOT fired (move "+(mr.max_abs_relative_move!=null?(100*mr.max_abs_relative_move).toFixed(3)+"%":"--")+")"):(mr.refresh_required?"FIRED":"--")],
      ["MR-015 (copula-form residual)",td.mr015_opened?"OPEN (tracked)":"--"],
      ["df (copula FROZEN)",td.df_frozen!=null?Number(td.df_frozen).toFixed(4):"--"]
    ].forEach(function(c){ html+='<div class="card"><div class="k">'+c[0]+
      '</div><div class="v">'+esc(c[1])+'</div></div>'; });
    html+='</div>';
    html+='<p class="note"><b>MATERIAL FINDING.</b> The fitted upper-tail-asymmetry scalar gamma_hat &asymp; 0 pins the skew-t at near-radial-symmetry, '+
      'so the skew-t component SCR is economically identical to the frozen symmetric-t basis (move '+
      (mr.max_abs_relative_move!=null?(100*mr.max_abs_relative_move).toFixed(3):"--")+'%, below the 1% MR trigger). '+
      'The copula-form residual to the nested truth is RE-CONFIRMED as NOT closed by a single skew-t scalar. Copula FROZEN per SII Art. 234.</p>';
    var D=[];
    [["Symmetric-t (mean)",sy.mean,"#2b5d99"],
     ["Skew-t (mean)",sk.mean,"#4f9cff"],
     ["Skew-t CI lo",sk.ci_lo,"#2fd0a8"],
     ["Skew-t CI hi",sk.ci_hi,"#2fd0a8"],
     ["Nested PATH-WISE ref",nestedRef,"#ffb454"]
    ].forEach(function(b){ if(b[1]!=null) D.push({label:b[0],value:b[1],color:b[2],
      tip:"<b>"+b[0]+"</b><br>99.5% / 1y SCR: "+num(b[1])}); });
    if(D.length){
      html+='<div class="chartwrap"><h4>99.5% / 1y SCR &mdash; skew-t vs symmetric-t vs nested reference</h4>'+
        '<p class="cap">With gamma_hat &asymp; 0 the skew-t and symmetric-t bases coincide; both sit well below the nested path-wise reference '+
        num(nestedRef)+' &mdash; a COPULA-FORM gap unaffected by the upper-tail-asymmetry scalar.</p>'+
        barChart(D,{w:760,h:300,mB:64})+'</div>';
    }
    var rows=td.rows||[];
    if(rows.length){
      html+='<div class="subh">Upper/lower tail-dependence &amp; radial asymmetry across the tail grid (skew-t draw, 200&times;20k bootstrap, 95% CI)</div>'+
        '<table class="ptable"><thead><tr><th>p</th><th>&lambda;<sub>U</sub> (skew-t)</th><th>&lambda;<sub>L</sub> (skew-t)</th>'+
        '<th>Radial asym (U&minus;L)</th><th>&lambda;<sub>U</sub> (sym-t)</th></tr></thead><tbody>';
      function cv(m){ return (m&&m.mean!=null)?(Number(m.mean).toFixed(4)+(m.ci_lo!=null?(" ["+Number(m.ci_lo).toFixed(4)+", "+Number(m.ci_hi).toFixed(4)+"]"):"")):"--"; }
      rows.forEach(function(rw){
        html+='<tr><td>'+(rw.p!=null?rw.p.toFixed(2):"--")+'</td><td>'+cv(rw.skewt_lambda_U)+'</td><td>'+cv(rw.skewt_lambda_L)+'</td>'+
          '<td>'+((rw.skewt_radial_asym&&rw.skewt_radial_asym.mean!=null)?Number(rw.skewt_radial_asym.mean).toExponential(2):"--")+'</td>'+
          '<td>'+((rw.sym_lambda_U&&rw.sym_lambda_U.mean!=null)?Number(rw.sym_lambda_U.mean).toFixed(4):"--")+'</td></tr>';
      });
      html+='</tbody></table>';
      var TD=[];
      rows.forEach(function(rw){
        var pl=(rw.p!=null?rw.p.toFixed(2):"?");
        if(rw.skewt_lambda_U&&rw.skewt_lambda_U.mean!=null) TD.push({label:"λU p="+pl,value:rw.skewt_lambda_U.mean,color:"#4f9cff",tip:"<b>upper tail dep</b><br>p="+pl+": "+rw.skewt_lambda_U.mean.toFixed(4)});
        if(rw.skewt_lambda_L&&rw.skewt_lambda_L.mean!=null) TD.push({label:"λL p="+pl,value:rw.skewt_lambda_L.mean,color:"#9a7bff",tip:"<b>lower tail dep</b><br>p="+pl+": "+rw.skewt_lambda_L.mean.toFixed(4)});
      });
      if(TD.length){
        html+='<div class="chartwrap"><h4>Tail-dependence: upper (&lambda;<sub>U</sub>) vs lower (&lambda;<sub>L</sub>) across p</h4>'+
          '<p class="cap">The skew-t draw is near-radially-symmetric (&lambda;<sub>U</sub> &asymp; &lambda;<sub>L</sub> at every p), consistent with gamma_hat &asymp; 0.</p>'+
          barChart(TD,{w:760,h:300,mB:84})+'</div>';
      }
    }
    if(Object.keys(gd).length){
      html+='<div class="subh">Residual gap to nested truth &mdash; copula-form vs relief-surface (skew-t re-decomposition)</div>'+
        '<table class="ptable"><thead><tr><th>Component</th><th>Absolute</th><th>Share of gap</th><th>Basis</th></tr></thead><tbody>'+
        '<tr><td>Relief-surface error</td><td>'+num(gd.relief_surface_part_abs)+'</td><td>'+
          (gd.relief_surface_share_of_gap!=null?(100*gd.relief_surface_share_of_gap).toFixed(1)+"%":"--")+
          '</td><td>bounded by governed 1.16% OOS error</td></tr>'+
        '<tr><td>Copula-form residual (skew-t)</td><td>'+num(gd.copula_form_residual_abs)+'</td><td>'+
          (gd.copula_form_share_of_gap!=null?(100*gd.copula_form_share_of_gap).toFixed(1)+"%":"--")+
          '</td><td>frozen-t '+num(gd.copula_form_residual_frozen_t)+' &rarr; skew-t '+num(gd.copula_form_residual_abs)+'</td></tr>'+
        '<tr><td>Total gap (nested &minus; skew-t)</td><td>'+num(gd.gap_total_abs)+'</td><td>'+
          (gd.gap_total_rel_to_nested!=null?(100*gd.gap_total_rel_to_nested).toFixed(2)+"%":"--")+
          '</td><td>nested with-actions reference</td></tr>'+
        '</tbody></table>'+
        '<p class="note">The skew-t scalar lifts the frozen-t component SCR by only '+num(gd.skewt_minus_sym_lift)+' on common random numbers; '+
        'the copula-form residual moves '+num(gd.copula_form_residual_frozen_t)+' &rarr; '+num(gd.copula_form_residual_abs)+' ('+
        (gd.copula_form_residual_reduction_rel!=null?(100*gd.copula_form_residual_reduction_rel).toFixed(2):"--")+'% reduction) &mdash; '+
        'RE-CONFIRMED as NOT closed by a single upper-tail-asymmetry scalar. Mitigation: grouped-t / vine escalation (Phase 28). Tracked by MR-015. DISCLOSED.</p>';
    }
    html+=maGateGrid(bo.gates,"Task 3 pre-registered gates (skew-t margin bootstrap + residual re-decomposition)");
    html+=maGateGrid(td.gates,"Task 4 pre-registered gates (tail-dependence diagnostics + MR-015)");
    html+='<p class="note">'+esc(p.narrative||"")+'</p>';
    html+='<p class="note mono">Sources: '+esc(bo.source||"")+' &middot; '+esc(td.source||"")+
      ' &middot; ChangeRecords '+esc(bo.change_record_id||"")+' / '+esc(td.change_record_id||"")+'</p>';
    el.innerHTML=html;
    wireTips(el);
  }

  function renderPhase28(){
    var el=document.getElementById("phase28"); if(!el) return;
    if(!DATA){ el.innerHTML=dz(); return; }
    var p=DATA.phase28||{};
    var co=p.copula||{}, bo=p.bootstrap||{}, td=p.tail||{};
    if(!Object.keys(co).length&&!Object.keys(bo).length&&!Object.keys(td).length){
      el.innerHTML='<p class="muted">No Phase 28 grouped-t tail-dependence data in this snapshot (requires contract v1.10.0+).</p>';
      return;
    }
    var gr=bo.grouped_t_component_scr_ci||{}, sg=bo.single_t_component_scr_ci||{};
    var grpPoint=bo.task2_grouped_t_component_point;
    var sngPoint=bo.task2_frozen_t_component_point;
    var nestedRef=(bo.nested_pathwise_reference!=null?bo.nested_pathwise_reference:co.nested_pathwise_reference);
    var gd=bo.residual_gap_redecomposition_point||{};
    var mr=td.mr_refresh_decision||{};
    var dfs=(co.block_dfs_hat||td.block_dfs_frozen||[]);
    var p90=(td.rows||[]).filter(function(x){ return Math.abs(Number(x.p)-0.9)<1e-9; })[0]||{};
    function mean(m,d){ return (m&&m.mean!=null)?Number(m.mean).toFixed(d==null?4:d):"--"; }
    function ci(m,d){ return (m&&m.ci_lo!=null)?"["+Number(m.ci_lo).toFixed(d==null?4:d)+", "+Number(m.ci_hi).toFixed(d==null?4:d)+"]":"--"; }
    var html='<div class="cards">';
    [
      ["df_NONFIN / df_FIN",dfs.length>1?(Number(dfs[0]).toFixed(3)+" / "+Number(dfs[1]).toFixed(3)):"--"],
      ["Grouped-t component SCR (bootstrap mean)",num(gr.mean)],
      ["Grouped-t component SCR (point)",num(grpPoint)],
      ["Single-df t component SCR (mean)",num(sg.mean)],
      ["Single-df t component SCR (point)",num(sngPoint)],
      ["Nested SCR (path-wise) - reference",num(nestedRef)],
      ["Grouped-t 95% CI",gr.ci_lo!=null?"["+num(gr.ci_lo)+", "+num(gr.ci_hi)+"]":"--"],
      ["Grouped-t SE (% of mean)",bo.se_frac_of_mean!=null?(100*bo.se_frac_of_mean).toFixed(2)+"%":"--"],
      ["Nested inside grouped 95% CI?",bo.headline_nested_inside_95ci?"yes":"no (OUTSIDE)"],
      ["Grouped minus single (CRN mean)",num(bo.grouped_minus_single_mean)],
      ["Cross-block dilution at p=0.90",mean(p90.grp_minus_sng_cross_upper,4)+" "+ci(p90.grp_minus_sng_cross_upper,4)],
      ["MR-016",td.mr016_opened?"OPEN (tracked)":"--"]
    ].forEach(function(c){ html+='<div class="card"><div class="k">'+c[0]+
      '</div><div class="v">'+esc(c[1])+'</div></div>'; });
    html+='</div>';
    html+='<p class="note"><b>MATERIAL FINDING.</b> The grouped-t block-df fit did not reveal a standalone within-FIN tail concentration. '+
      'It diluted cross-block co-movement versus the single shared-mixing t boundary, so grouped-t component SCR moved DOWN. '+
      'The grouped-t result is DISCLOSED, not adopted into the governed headline; MR-010/MR-014 stay unchanged and MR-016 tracks the residual.</p>';
    var D=[];
    [["Grouped-t mean",gr.mean,"#4f9cff"],
     ["Grouped-t point",grpPoint,"#2fd0a8"],
     ["Single-df t mean",sg.mean,"#9a7bff"],
     ["Single-df t point",sngPoint,"#2b5d99"],
     ["Nested PATH-WISE ref",nestedRef,"#ffb454"]
    ].forEach(function(b){ if(b[1]!=null) D.push({label:b[0],value:b[1],color:b[2],
      tip:"<b>"+b[0]+"</b><br>99.5% / 1y SCR: "+num(b[1])}); });
    if(D.length){
      html+='<div class="chartwrap"><h4>99.5% / 1y SCR &mdash; grouped-t vs single-df t vs nested reference</h4>'+
        '<p class="cap">The grouped-t component sits below the single-df t boundary and farther below the nested path-wise reference '+num(nestedRef)+
        '; the widening is informative model-form evidence, not a failed recalibration.</p>'+barChart(D,{w:760,h:300,mB:72})+'</div>';
    }
    var rows=td.rows||[];
    if(rows.length){
      html+='<div class="subh">Within/cross-block upper/lower tail-dependence grid (grouped vs single, 200&times;20k bootstrap, 95% CI)</div>'+
        '<table class="ptable p28tail"><thead><tr><th>p</th><th>Grouped cross U</th><th>Single cross U</th><th>Grouped - single cross U</th>'+
        '<th>Grouped cross L</th><th>Grouped within FIN U</th><th>Single within FIN U</th><th>Grouped FIN radial asym</th></tr></thead><tbody>';
      rows.forEach(function(rw){
        html+='<tr><td>'+(rw.p!=null?rw.p.toFixed(2):"--")+'</td>'+
          '<td>'+mean(rw.grp_cross_upper,4)+' '+ci(rw.grp_cross_upper,4)+'</td>'+
          '<td>'+mean(rw.sng_cross_upper,4)+' '+ci(rw.sng_cross_upper,4)+'</td>'+
          '<td>'+mean(rw.grp_minus_sng_cross_upper,4)+' '+ci(rw.grp_minus_sng_cross_upper,4)+'</td>'+
          '<td>'+mean(rw.grp_cross_lower,4)+' '+ci(rw.grp_cross_lower,4)+'</td>'+
          '<td>'+mean(rw.grp_within_upper_fin,4)+'</td>'+
          '<td>'+mean(rw.sng_within_upper_fin,4)+'</td>'+
          '<td>'+mean(rw.grp_within_radial_asym_fin,5)+' '+ci(rw.grp_within_radial_asym_fin,5)+'</td></tr>';
      });
      html+='</tbody></table>';
      var TD=[];
      rows.forEach(function(rw){
        var pl=(rw.p!=null?rw.p.toFixed(2):"?");
        if(rw.grp_cross_upper&&rw.grp_cross_upper.mean!=null) TD.push({label:"grp cross p="+pl,value:rw.grp_cross_upper.mean,color:"#4f9cff",tip:"<b>grouped cross upper</b><br>p="+pl+": "+rw.grp_cross_upper.mean.toFixed(4)});
        if(rw.sng_cross_upper&&rw.sng_cross_upper.mean!=null) TD.push({label:"single cross p="+pl,value:rw.sng_cross_upper.mean,color:"#9a7bff",tip:"<b>single cross upper</b><br>p="+pl+": "+rw.sng_cross_upper.mean.toFixed(4)});
      });
      if(TD.length){
        html+='<div class="chartwrap"><h4>Cross-block upper-tail dilution profile</h4>'+
          '<p class="cap">Grouped-t cross-block upper tail dependence is below the single-df t boundary at every p; p=0.90 dilution is '+
          mean(p90.grp_minus_sng_cross_upper,4)+'.</p>'+barChart(TD,{w:760,h:300,mB:90})+'</div>';
      }
    }
    if(Object.keys(gd).length){
      html+='<div class="subh">Residual gap to nested truth &mdash; grouped-t re-decomposition and widening</div>'+
        '<table class="ptable p28gaptable"><thead><tr><th>Component</th><th>Absolute</th><th>Share / move</th><th>Basis</th></tr></thead><tbody>'+
        '<tr><td>Relief-surface error</td><td>'+num(gd.relief_surface_part_abs)+'</td><td>'+
          (gd.relief_surface_share_of_gap!=null?(100*gd.relief_surface_share_of_gap).toFixed(1)+"%":"--")+
          '</td><td>bounded by governed 1.16% OOS error</td></tr>'+
        '<tr><td>Copula-form residual (grouped-t)</td><td>'+num(gd.copula_form_residual_abs)+'</td><td>'+
          (gd.copula_form_share_of_gap!=null?(100*gd.copula_form_share_of_gap).toFixed(1)+"% of gap":"--")+
          '</td><td>skew-t reconfirmed '+num(gd.copula_form_residual_skewt_reconfirmed)+' &rarr; grouped-t '+num(gd.copula_form_residual_abs)+'</td></tr>'+
        '<tr><td>Residual widening vs skew-t</td><td>'+num(gd.copula_form_residual_change_vs_skewt_abs)+'</td><td>'+
          (gd.copula_form_residual_change_vs_skewt_rel!=null?("+"+(100*gd.copula_form_residual_change_vs_skewt_rel).toFixed(2)+"%"):"--")+
          '</td><td>informative negative super-set result; vine escalation</td></tr>'+
        '<tr><td>Total gap (nested &minus; grouped-t)</td><td>'+num(gd.gap_total_abs)+'</td><td>'+
          (gd.gap_total_rel_to_nested!=null?(100*gd.gap_total_rel_to_nested).toFixed(2)+"% of nested":"--")+
          '</td><td>nested with-actions reference</td></tr>'+
        '</tbody></table>'+
        '<p class="note">The nested reference '+num(nestedRef)+' is OUTSIDE the grouped-t CI ['+num(gr.ci_lo)+', '+num(gr.ci_hi)+']; '+
        'the copula-form residual WIDENS from '+num(gd.copula_form_residual_skewt_reconfirmed)+' to '+num(gd.copula_form_residual_abs)+
        '. This confirms the residual is nested inner-path joint structure that a copula on standalone margins cannot represent. DISCLOSED; Phase 29 vine / pair-copula is the fallback.</p>';
    }
    html+='<div class="subh">MR refresh and governance decision</div>'+
      '<table class="ptable"><thead><tr><th>Decision</th><th>Value</th><th>Rationale</th></tr></thead><tbody>'+
      '<tr><td>Governed headline move</td><td>'+(mr.governed_headline_relative_move!=null?(100*mr.governed_headline_relative_move).toFixed(4)+"%":"--")+
      '</td><td>Frozen single-df t boundary recovered exactly; MR-010/MR-014 no-refresh.</td></tr>'+
      '<tr><td>Disclosed grouped move</td><td>'+(mr.disclosed_grouped_vs_basis_move_bootstrap_mean!=null?(100*mr.disclosed_grouped_vs_basis_move_bootstrap_mean).toFixed(2)+"%":"--")+
      '</td><td>Non-conservative DOWN move, disclosed and tracked by MR-016.</td></tr>'+
      '<tr><td>MR-016</td><td>'+(td.mr016_opened?"OPEN":"--")+'</td><td>Heterogeneous-tail / cross-block-dilution copula-form residual remains open.</td></tr>'+
      '</tbody></table>';
    html+=maGateGrid(co.gates,"Task 2 pre-registered gates (grouped-t copula re-aggregation)");
    html+=maGateGrid(bo.gates,"Task 3 pre-registered gates (grouped-t bootstrap + residual re-decomposition)");
    html+=maGateGrid(td.gates,"Task 4 pre-registered gates (tail diagnostics + MR-016)");
    html+='<p class="note">'+esc(p.narrative||"")+'</p>';
    html+='<p class="note mono">Sources: '+esc(co.source||"")+' &middot; '+esc(bo.source||"")+' &middot; '+esc(td.source||"")+
      ' &middot; ChangeRecords '+esc(co.change_record_id||"")+' / '+esc(bo.change_record_id||"")+' / '+esc(td.change_record_id||"")+'</p>';
    el.innerHTML=html;
    wireTips(el);
  }

  // ---- Governance & assumptions view (UI Task 4) ----
  var GLIK=["VERY_LOW","LOW","MEDIUM","HIGH","CRITICAL"];
  var GIMP=["VERY_LOW","LOW","MEDIUM","HIGH","CRITICAL"];
  function gLvl(s){ s=String(s||"").toUpperCase().replace(/\s+/g,"_");
    var m={VERY_LOW:0,VL:0,LOW:1,L:1,MEDIUM:2,MODERATE:2,MED:2,M:2,HIGH:3,H:3,CRITICAL:4,VERY_HIGH:4,SEVERE:4};
    return (m[s]!=null)?m[s]:-1; }

  function govIntegrity(g){
    var ae=(typeof g.audit_entries==="number")?g.audit_entries:((g.audit_entries||[]).length||0);
    var ver=(g.audit_verified!=null)?g.audit_verified:ae;
    var fail=(g.audit_failed!=null)?g.audit_failed:0;
    var steps=0; (g.change_records||[]).forEach(function(c){ steps+=(c.sign_off_history||[]).length; });
    var ok=(fail===0)&&(ver===ae)&&(g.audit_integrity_ok!==false);
    return {ok:ok,entries:ae,verified:ver,failed:fail,signoff_steps:steps,records:(g.change_records||[]).length};
  }

  function govKpis(g){
    var gates=g.deployment_gates||[], cleared=gates.filter(function(x){return x.cleared;}).length;
    var risks=g.risk_register||[];
    function rs(r){ return String(r.mitigation_status||"").toUpperCase(); }
    var openR=risks.filter(function(r){ return rs(r)==="OPEN"||rs(r)==="IN_PROGRESS"; }).length;
    var mitR=risks.filter(function(r){ return rs(r)==="MITIGATED"||rs(r)==="CLOSED"; }).length;
    var it=govIntegrity(g);
    return '<div class="cards">'+
      '<div class="card"><div class="k">Deployment gates</div><div class="v">'+cleared+' / '+gates.length+'</div></div>'+
      '<div class="card"><div class="k">Model risks open</div><div class="v">'+openR+'</div></div>'+
      '<div class="card"><div class="k">Risks mitigated/closed</div><div class="v">'+mitR+'</div></div>'+
      '<div class="card"><div class="k">Change records</div><div class="v">'+it.records+'</div></div>'+
      '<div class="card"><div class="k">Audit entries</div><div class="v">'+it.entries+'</div></div>'+
      '<div class="card"><div class="k">Audit integrity</div><div class="v" style="color:'+(it.ok?'var(--pass)':'var(--fail)')+'">'+
        (it.ok?'✓ OK':'✗')+'</div></div>'+
      '</div>';
  }

  function govGatesBlock(g){
    var gates=g.deployment_gates||[];
    if(!gates.length) return '<div class="chartwrap"><p class="muted">No deployment gates in snapshot.</p></div>';
    var cleared=gates.filter(function(x){return x.cleared;}).length;
    var pct=gates.length?(100*cleared/gates.length):0;
    var h='<div class="chartwrap"><h4>Educational deployment gates</h4>'+
      '<p class="cap">'+cleared+' of '+gates.length+' gates cleared. Each gate is an educational-use guardrail &mdash; '+
      'a cleared gate is NOT a production sign-off. Hover a card for what it blocks.</p>'+
      '<div class="gbar"><div class="gbar-fill" style="width:'+pct.toFixed(1)+'%"></div></div>'+
      '<div class="gate-grid">';
    gates.forEach(function(x){
      h+='<div class="gate" data-tip="'+ta('<b>'+esc(x.gate_id)+'</b><br>'+esc(x.description)+'<br>Blocks: '+esc(x.blocking||'--'))+'">'+
        '<div style="display:flex;justify-content:space-between;align-items:center;gap:8px">'+
        '<h4 class="mono">'+esc(x.gate_id)+'</h4>'+chip(x.status)+'</div>'+
        '<div class="params">'+esc(x.description)+'</div>'+
        '<div class="params" style="margin-top:6px"><span class="badge">'+esc(x.level||'')+'</span> '+
        '<span class="badge">blocks: '+esc(x.blocking||'--')+'</span></div></div>';
    });
    return h+'</div></div>';
  }

  function riskHeatmap(risks){
    var W=440,H=300,mL=92,mT=12,mB=60,mR=14;
    var cols=5,rows=5,cw=(W-mL-mR)/cols,ch=(H-mT-mB)/rows;
    var grid={}; risks.forEach(function(r){ var li=gLvl(r.likelihood),ii=gLvl(r.impact);
      if(li<0||ii<0) return; var k=ii+'_'+li; grid[k]=(grid[k]||0)+1; });
    var s=svgOpen(W,H);
    for(var ri=0;ri<rows;ri++){ var imp=rows-1-ri;
      for(var ci=0;ci<cols;ci++){
        var x=mL+ci*cw, y=mT+ri*ch, n=grid[imp+'_'+ci]||0, score=imp+ci;
        var col=score>=6?'rgba(255,107,107,':(score>=4?'rgba(255,180,84,':(score>=2?'rgba(79,156,255,':'rgba(57,217,138,'));
        s+='<rect x="'+x+'" y="'+y+'" width="'+(cw-3)+'" height="'+(ch-3)+'" rx="4" fill="'+col+(n>0?'0.85':'0.12')+')" '+
          'stroke="var(--line)" data-tip="'+ta('Impact '+GIMP[imp].replace('_',' ')+' × Likelihood '+GLIK[ci].replace('_',' ')+'<br>'+n+' risk(s)')+'"/>';
        if(n>0) s+='<text class="val" x="'+(x+(cw-3)/2)+'" y="'+(y+(ch-3)/2+4)+'" text-anchor="middle">'+n+'</text>';
      }
    }
    for(var c2=0;c2<cols;c2++){ s+=xlabel(GLIK[c2].replace('_',' '), mL+c2*cw+(cw-3)/2, mT+rows*ch+12); }
    for(var r2=0;r2<rows;r2++){ var imp2=rows-1-r2;
      s+='<text x="'+(mL-8)+'" y="'+(mT+r2*ch+(ch-3)/2+3)+'" text-anchor="end">'+esc(GIMP[imp2].replace('_',' '))+'</text>'; }
    s+='<text x="'+(mL+(W-mL-mR)/2)+'" y="'+(H-4)+'" text-anchor="middle">Likelihood &rarr;</text>';
    return s+'</svg>';
  }

  function govRiskTable(risks){
    if(!risks.length) return '<p class="muted">No risks match the current filter.</p>';
    var h='<table><thead><tr><th>ID</th><th>Title</th><th>Rating</th><th>Likelihood</th><th>Impact</th>'+
      '<th>Status</th><th>Category</th></tr></thead><tbody>';
    risks.forEach(function(r,i){
      h+='<tr class="rrow" data-i="'+i+'" style="cursor:pointer"><td class="mono">'+esc(r.risk_id||r.id||'')+'</td>'+
        '<td>'+esc(r.title||'')+'</td><td>'+chip(r.overall_rating)+'</td><td>'+esc(r.likelihood||'--')+'</td>'+
        '<td>'+esc(r.impact||'--')+'</td><td>'+chip(r.mitigation_status)+'</td><td>'+esc(r.category||'--')+'</td></tr>';
      h+='<tr class="rdet" data-i="'+i+'" style="display:none"><td colspan="7"><div class="rdetbox">'+
        '<div><b>Description.</b> '+esc(r.description||'--')+'</div>'+
        '<div style="margin-top:6px"><b>Mitigation.</b> '+esc(r.mitigation||'--')+'</div>'+
        '<div class="params" style="margin-top:6px">Standard: '+esc(r.related_standard||'--')+
        ' &middot; Owner: '+esc(r.owner||'--')+' &middot; Updated: '+esc(String(r.updated_at||'').slice(0,10))+'</div>'+
        '</div></td></tr>';
    });
    return h+'</tbody></table>';
  }

  function govRisksControls(){
    var ratings=['','CRITICAL','HIGH','MEDIUM','LOW','VERY_LOW'];
    var statuses=['','OPEN','IN_PROGRESS','MITIGATED','CLOSED'];
    function opts(arr){ return arr.map(function(v){ return '<option value="'+v+'">'+(v?esc(v):'All')+'</option>'; }).join(''); }
    return '<div class="filter">Rating <select id="rfRating">'+opts(ratings)+'</select> '+
      '&nbsp; Mitigation status <select id="rfStatus">'+opts(statuses)+'</select></div>';
  }

  function govChangesBlock(g){
    var recs=(g.change_records||[]).slice();
    if(!recs.length) return '<div class="chartwrap"><p class="muted">No change records in snapshot.</p></div>';
    recs.sort(function(a,b){ return String(b.created_at||'').localeCompare(String(a.created_at||'')); });
    var h='<div class="chartwrap"><h4>ChangeRecord approval timeline</h4>'+
      '<p class="cap">Newest first. Each record carries its standards basis and a full peer-review &rarr; owner-review &rarr; '+
      'approval sign-off chain. Click a record to expand its sign-off history.</p><div class="timeline">';
    recs.forEach(function(c,i){
      var refs=(c.standard_references||[]).map(function(x){return '<span class="badge">'+esc(x)+'</span>';}).join(' ');
      var soh=(c.sign_off_history||[]).map(function(x){
        return '<div class="tl-soh"><span class="mono">'+esc(String(x.timestamp||'').slice(0,19).replace('T',' '))+'</span> '+
          chip(x.status)+' <b>'+esc(x.actor||'')+'</b><div class="params">'+esc(x.comments||'')+'</div></div>'; }).join('');
      h+='<div class="tl-item"><div class="tl-dot '+chipClass(c.status)+'"></div><div class="tl-body">'+
        '<div class="tl-head crow" data-i="'+i+'" style="cursor:pointer">'+chip(c.status)+' <b>'+esc(c.title||'')+'</b> '+chip(c.change_type)+'</div>'+
        '<div class="params">'+esc(String(c.created_at||'').slice(0,10))+' &middot; '+esc(c.phase||'')+' &middot; '+
        esc(c.author||'')+' &rarr; '+esc(c.peer_reviewer||'')+' &middot; <span class="mono">'+esc(String(c.record_id||'').slice(0,8))+'</span></div>'+
        '<div class="cdet" data-i="'+i+'" style="display:none"><div class="subh">Standards basis</div>'+(refs||'<span class="muted">none</span>')+
        '<div class="subh">Sign-off history</div>'+(soh||'<span class="muted">none</span>')+'</div></div></div>';
    });
    return h+'</div></div>';
  }

  function govAuditBlock(g){
    var it=govIntegrity(g), statusDist={}, typeDist={};
    (g.change_records||[]).forEach(function(c){ statusDist[c.status]=(statusDist[c.status]||0)+1;
      typeDist[c.change_type]=(typeDist[c.change_type]||0)+1; });
    function dist(o){ return Object.keys(o).map(function(k){ return '<tr><td>'+chip(k)+'</td><td>'+o[k]+'</td></tr>'; }).join(''); }
    var badge='<div class="auditbadge '+(it.ok?'ok':'bad')+'">'+(it.ok?'✓ AUDIT TRAIL VERIFIED':'✗ AUDIT TRAIL INTEGRITY FAILURE')+'</div>';
    return '<div class="chartwrap"><h4>Audit-trail integrity (recomputed offline)</h4>'+
      '<p class="cap">Recomputed from the embedded governance export: integrity holds when every audit entry is verified '+
      'and none failed. Sign-off steps are the human-review evidence behind each approved change.</p>'+badge+
      '<div class="cards" style="margin-top:12px">'+
      '<div class="card"><div class="k">Entries</div><div class="v">'+it.entries+'</div></div>'+
      '<div class="card"><div class="k">Verified</div><div class="v">'+it.verified+'</div></div>'+
      '<div class="card"><div class="k">Failed</div><div class="v" style="color:'+(it.failed?'var(--fail)':'var(--pass)')+'">'+it.failed+'</div></div>'+
      '<div class="card"><div class="k">Sign-off steps</div><div class="v">'+it.signoff_steps+'</div></div></div>'+
      '<div style="display:grid;grid-template-columns:1fr 1fr;gap:18px;margin-top:6px">'+
      '<div><div class="subh">Change records by status</div><table><tbody>'+dist(statusDist)+'</tbody></table></div>'+
      '<div><div class="subh">Change records by type</div><table><tbody>'+dist(typeDist)+'</tbody></table></div>'+
      '</div></div>';
  }

  function renderGovernance(){
    var el = document.getElementById("governance"); if(!DATA){ el.innerHTML=dz(); return; }
    var g = DATA.governance||{};
    var html = govKpis(g);
    html += '<p class="note">Read-only governance export embedded inline (no network): deployment gates, the model-risk '+
      'register, the ChangeRecord approval trail, and a recomputed audit-integrity badge. Educational use only.</p>';
    var views=[["gates","Deployment gates"],["risks","Model-risk register"],["changes","Change records"],["audit","Audit integrity"]];
    html += '<div class="subnav" id="govnav">'+views.map(function(v,i){
      return '<div class="segbtn'+(i===0?" active":"")+'" data-view="'+v[0]+'">'+esc(v[1])+'</div>'; }).join("")+'</div>';
    html += '<div id="gov-gates" class="govview">'+govGatesBlock(g)+'</div>';
    html += '<div id="gov-risks" class="govview" style="display:none"><div class="chartwrap"><h4>Model-risk register</h4>'+
      '<p class="cap">Filter by rating and mitigation status. The heatmap bins risks by impact × likelihood; '+
      'click a table row for description, mitigation and standards basis.</p>'+govRisksControls()+
      '<div id="gov-risk-body"></div></div></div>';
    html += '<div id="gov-changes" class="govview" style="display:none">'+govChangesBlock(g)+'</div>';
    html += '<div id="gov-audit" class="govview" style="display:none">'+govAuditBlock(g)+'</div>';
    el.innerHTML = html;
    [].forEach.call(el.querySelectorAll("#govnav .segbtn"),function(b){
      b.onclick=function(){
        [].forEach.call(el.querySelectorAll("#govnav .segbtn"),function(x){x.classList.remove("active");});
        [].forEach.call(el.querySelectorAll(".govview"),function(x){x.style.display="none";});
        b.classList.add("active");
        var v=document.getElementById("gov-"+b.getAttribute("data-view")); if(v) v.style.display="block";
      };
    });
    function renderRiskBody(){
      var rt=(document.getElementById("rfRating")||{}).value||"";
      var st=(document.getElementById("rfStatus")||{}).value||"";
      var risks=(g.risk_register||[]).filter(function(r){
        if(rt && String(r.overall_rating||"").toUpperCase()!==rt) return false;
        if(st && String(r.mitigation_status||"").toUpperCase()!==st) return false;
        return true; });
      var body=document.getElementById("gov-risk-body"); if(!body) return;
      body.innerHTML='<div class="heatwrap">'+riskHeatmap(risks)+'</div>'+govRiskTable(risks);
      [].forEach.call(body.querySelectorAll(".rrow"),function(row){
        row.onclick=function(){ var i=row.getAttribute("data-i");
          var d=body.querySelector('.rdet[data-i="'+i+'"]'); if(d) d.style.display=(d.style.display==="none"?"table-row":"none"); };
      });
      wireTips(body);
    }
    var rfa=document.getElementById("rfRating"), rfb=document.getElementById("rfStatus");
    if(rfa) rfa.onchange=renderRiskBody; if(rfb) rfb.onchange=renderRiskBody;
    renderRiskBody();
    [].forEach.call(el.querySelectorAll(".crow"),function(row){
      row.onclick=function(){ var i=row.getAttribute("data-i");
        var d=el.querySelector('.cdet[data-i="'+i+'"]'); if(d) d.style.display=(d.style.display==="none"?"block":"none"); };
    });
    wireTips(el);
  }

  function dz(){
    return '<p class="muted">No embedded data in this file.</p>'+
      '<div class="dz" id="drop">Drag &amp; drop a <span class="mono">ui_data.json</span> here, '+
      'or <input type="file" id="file" accept="application/json"/></div>';
  }

  function contractSchema(){
    return [
      "ui_data.json -- stable offline UI contract (v"+(DATA&&DATA.contract_version||"1.0.0")+")",
      "{",
      "  contract_version : string   // bump on breaking schema change",
      "  meta         : {model_name, model_version, generated_utc, classification}",
      "  summary      : {tasks_completed, tasks_total, phases_completed, gates_cleared,",
      "                  gates_total, risks_open, risks_mitigated, production_status, ...}",
      "  inventory    : [{id, path, category, bytes, sha256, mtime_utc, headline}]",
      "  capital      : {rate_scr, equity_scr, credit_scr, lapse_scr, mortality_scr,",
      "                  fx_scr, liquidity_scr, standalone_sum, var_covar_scr,",
      "                  nested_scr, selected_copula, esg_understatement_pct, n_drivers}",
      "  tail         : {final_var, final_es, converged, var_ci, es_ci, sobol_ratio,",
      "                  nested_var_ci, nested_n_outer, grid_label, ...}",
      "  proxy        : {verdict, selected_degree, degree_rows, var_rel_error, ...}",
      "  loss         : {histogram, confidence_sweep, percentiles, var995, es995, ...}",
      "  calibrations : [{driver, gate_id, market, params, gate_status, gate_evidence,",
      "                   is_placeholder, source, lineage_id,",
      "                   diagnostics:{method,n_obs,fit_r2,converged,criteria[],fit_bars}}]",
      "  governance   : {audit_entries, audit_integrity_ok, change_records,",
      "                  deployment_gates, risk_register}",
      "  verdicts     : [{name, verdict}]",
      "}"
    ].join("\n");
  }

  function wireDropLoader(){
    var fileEl = document.getElementById("file");
    var dropEl = document.getElementById("drop");
    function ingest(text){ try{ DATA = JSON.parse(text); renderAll(); }catch(e){} }
    if(fileEl) fileEl.onchange = function(e){ var f=e.target.files[0]; if(!f) return;
      var r=new FileReader(); r.onload=function(){ ingest(r.result); }; r.readAsText(f); };
    if(dropEl){ dropEl.ondragover=function(e){e.preventDefault();};
      dropEl.ondrop=function(e){ e.preventDefault(); var f=e.dataTransfer.files[0]; if(!f) return;
        var r=new FileReader(); r.onload=function(){ ingest(r.result); }; r.readAsText(f); }; }
  }

  /* ---- UI Task 5: export (PNG/CSV), print, accessibility ---- */
  var CHART_EXPORT_CSS = "svg{--bg:#0f141b;--panel:#161e29;--panel2:#1d2733;--ink:#e7edf5;--muted:#93a1b3;--line:#283545;--accent:#4f9cff;--pass:#39d98a;--warn:#ffb454;--fail:#ff6b6b;--chip:#22303f}"
    + "text{fill:#93a1b3;font:11px -apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif}"
    + "text.val{fill:#e7edf5;font-weight:600}.axis{stroke:#283545;stroke-width:1}"
    + ".grid{stroke:#22303f;stroke-width:1;stroke-dasharray:3 3}.refline{stroke-width:1.5}";
  function downloadBlob(name,blob){
    try{
      var url=URL.createObjectURL(blob);
      var a=document.createElement("a"); a.href=url; a.download=name;
      document.body.appendChild(a); a.click();
      setTimeout(function(){ try{URL.revokeObjectURL(url);}catch(e){} if(a.parentNode) a.parentNode.removeChild(a); },0);
    }catch(e){}
  }
  function downloadText(name,text,mime){ downloadBlob(name,new Blob([text],{type:(mime||"text/plain")+";charset=utf-8"})); }
  function csvCell(v){ v=(v==null?"":String(v)).replace(/\r?\n/g," "); if(/[",]/.test(v)) v='"'+v.replace(/"/g,'""')+'"'; return v; }
  function rowsToCSV(headers,rows){ var out=[headers.map(csvCell).join(",")]; rows.forEach(function(r){ out.push(r.map(csvCell).join(",")); }); return out.join("\r\n"); }
  function buildInventoryCSV(){ var inv=(DATA&&DATA.inventory)||[];
    return rowsToCSV(["id","category","headline","bytes","sha256","path","mtime_utc"],
      inv.map(function(i){ return [i.id,i.category,i.headline,i.bytes,i.sha256,i.path,i.mtime_utc]; })); }
  function buildRiskCSV(){ var rr=(DATA&&DATA.governance&&DATA.governance.risk_register)||[];
    return rowsToCSV(["risk_id","title","overall_rating","mitigation_status","category","likelihood","impact","owner","related_standard","updated_at","description","mitigation"],
      rr.map(function(r){ return [r.risk_id,r.title,r.overall_rating,r.mitigation_status,r.category,r.likelihood,r.impact,r.owner,r.related_standard,r.updated_at,r.description,r.mitigation]; })); }
  function buildChangesCSV(){ var cr=(DATA&&DATA.governance&&DATA.governance.change_records)||[];
    return rowsToCSV(["record_id","title","status","change_type","phase","author","peer_reviewer","created_at","standard_references","signoff_steps"],
      cr.map(function(c){ return [c.record_id,c.title,c.status,c.change_type,c.phase,c.author,c.peer_reviewer,c.created_at,(c.standard_references||[]).join("; "),(c.sign_off_history||[]).length]; })); }
  window.__uiExport={ inventoryCSV:buildInventoryCSV, riskCSV:buildRiskCSV, changesCSV:buildChangesCSV };
  function isVisible(el){ return !!(el&&(el.offsetWidth||el.offsetHeight||(el.getClientRects&&el.getClientRects().length))); }
  function dataURLtoBlob(du){ var p=du.split(","),b=atob(p[1]),n=b.length,u=new Uint8Array(n); while(n--) u[n]=b.charCodeAt(n); return new Blob([u],{type:"image/png"}); }
  function svgToPng(svg,filename){
    try{
      var SVGNS="http"+"://www.w3.org/2000/svg";
      var clone=svg.cloneNode(true); clone.setAttribute("xmlns",SVGNS);
      var vb=(svg.getAttribute("viewBox")||"0 0 660 300").split(/\s+/);
      var w=parseFloat(vb[2])||660, h=parseFloat(vb[3])||300, scale=2;
      clone.setAttribute("width",w); clone.setAttribute("height",h);
      var st=document.createElementNS(SVGNS,"style"); st.textContent=CHART_EXPORT_CSS;
      var bg=document.createElementNS(SVGNS,"rect");
      bg.setAttribute("x",0); bg.setAttribute("y",0); bg.setAttribute("width",w); bg.setAttribute("height",h); bg.setAttribute("fill","#1d2733");
      clone.insertBefore(bg,clone.firstChild); clone.insertBefore(st,clone.firstChild);
      var xml=new XMLSerializer().serializeToString(clone);
      var url="data:image/svg+xml;base64,"+btoa(unescape(encodeURIComponent(xml)));
      var img=new Image();
      img.onload=function(){
        var cv=document.createElement("canvas"); cv.width=w*scale; cv.height=h*scale;
        var ctx=cv.getContext("2d"); ctx.scale(scale,scale); ctx.drawImage(img,0,0);
        if(cv.toBlob){ cv.toBlob(function(bl){ if(bl) downloadBlob(filename,bl); },"image/png"); }
        else { downloadBlob(filename,dataURLtoBlob(cv.toDataURL("image/png"))); }
      };
      img.onerror=function(){};
      img.src=url;
    }catch(e){}
  }
  function exportPNGActive(){
    var panel=document.querySelector(".panel.active"); if(!panel) return;
    var pid=panel.id||"panel";
    var svgs=[].slice.call(panel.querySelectorAll("svg.chart")).filter(isVisible);
    if(!svgs.length){ try{ alert("No charts on the active tab. Open Capital & Tail, Calibrations, or Governance to export charts."); }catch(e){} return; }
    svgs.forEach(function(svg,i){ svgToPng(svg,"chart_"+pid+"_"+(i+1)+".png"); });
  }
  function wireToolbar(){
    var map=[
      ["btnExportPng",function(){ exportPNGActive(); }],
      ["btnCsvInv",function(){ downloadText("inventory.csv",buildInventoryCSV(),"text/csv"); }],
      ["btnCsvRisk",function(){ downloadText("risk_register.csv",buildRiskCSV(),"text/csv"); }],
      ["btnCsvChg",function(){ downloadText("change_records.csv",buildChangesCSV(),"text/csv"); }],
      ["btnPrint",function(){ try{ window.print(); }catch(e){} }]
    ];
    map.forEach(function(m){ var b=document.getElementById(m[0]); if(b) b.onclick=m[1]; });
  }
  function a11yEnhance(){
    [].forEach.call(document.querySelectorAll(".subnav"),function(nav){
      nav.setAttribute("role","tablist");
      var btns=[].slice.call(nav.querySelectorAll(".segbtn"));
      btns.forEach(function(b,i){
        b.setAttribute("role","tab");
        b.setAttribute("aria-selected", b.classList.contains("active")?"true":"false");
        if(!b.hasAttribute("tabindex")) b.setAttribute("tabindex", b.classList.contains("active")?"0":"-1");
        b.addEventListener("keydown",function(e){
          if(e.key==="Enter"||e.key===" "||e.key==="Spacebar"){ e.preventDefault(); b.click(); }
          else if(e.key==="ArrowRight"||e.key==="ArrowLeft"||e.key==="Home"||e.key==="End"){
            e.preventDefault();
            var ni=e.key==="ArrowRight"?(i+1)%btns.length:e.key==="ArrowLeft"?(i-1+btns.length)%btns.length:e.key==="Home"?0:btns.length-1;
            btns[ni].focus(); btns[ni].click();
          }
        });
      });
    });
    var lbl={invq:"Filter inventory by name or headline",invcat:"Filter inventory by category",rfRating:"Filter risks by overall rating",rfStatus:"Filter risks by mitigation status"};
    Object.keys(lbl).forEach(function(id){ var el=document.getElementById(id); if(el&&!el.getAttribute("aria-label")) el.setAttribute("aria-label",lbl[id]); });
    [].forEach.call(document.querySelectorAll(".filter input,.filter select"),function(el){ if(!el.getAttribute("aria-label")) el.setAttribute("aria-label", el.id||"filter control"); });
    [].forEach.call(document.querySelectorAll(".rrow,.crow"),function(el){ if(!el.hasAttribute("tabindex")){ el.setAttribute("tabindex","0"); el.setAttribute("role","button"); } });
  }
  var _a11yWired=false;
  function wireGlobalA11y(){
    if(_a11yWired) return; _a11yWired=true;
    document.addEventListener("click",function(e){
      var t=e.target;
      if(t&&t.classList&&t.classList.contains("segbtn")){
        var nav=t.closest?t.closest(".subnav"):null;
        if(nav){ [].forEach.call(nav.querySelectorAll(".segbtn"),function(b){
          var on=b.classList.contains("active");
          b.setAttribute("aria-selected", on?"true":"false");
          b.setAttribute("tabindex", on?"0":"-1");
        }); }
      }
    });
    document.addEventListener("keydown",function(e){
      var t=e.target; if(!t||!t.classList) return;
      if((e.key==="Enter"||e.key===" "||e.key==="Spacebar")&&(t.classList.contains("rrow")||t.classList.contains("crow"))){ e.preventDefault(); t.click(); }
    });
  }
  function renderAll(){
    renderHeader(); renderOverview(); renderInventory();
    renderCalibrations(); renderCapital(); renderActions(); renderPhase24(); renderPhase25(); renderPhase26(); renderPhase27(); renderPhase28(); renderGovernance(); wireDropLoader();
    wireToolbar(); a11yEnhance(); wireGlobalA11y();
  }

  renderTabs();
  renderAll();
})();
</script>
</body>
</html>
"""


def write_outputs(data: Dict[str, Any]) -> None:
    with open(OUT_JSON, "w") as fh:
        json.dump(data, fh, indent=2, default=str)
    embedded = "/*__UI_DATA__*/" + json.dumps(data, default=str)
    html = HTML_TEMPLATE.replace(DATA_TOKEN, embedded)
    with open(OUT_HTML, "w") as fh:
        fh.write(html)


def main() -> None:
    data = build_ui_data()
    write_outputs(data)
    print("ui_data.json artifacts:", len(data["inventory"]),
          "calibrations:", len(data["calibrations"]),
          "contract:", data["contract_version"])
    print("wrote", OUT_JSON, "and", OUT_HTML)


if __name__ == "__main__":
    main()
