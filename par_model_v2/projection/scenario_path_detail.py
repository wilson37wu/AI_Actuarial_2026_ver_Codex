"""GD-1 - Stepwise scenario-path detail set (owner directive 2026-07-07).

Owner directive (2026-07-07, interactive): "allow for more detailed stepwise
calculation to be output and displayed in general, like economic scenario
paths, asset returns path, asset cash flow by asset class, liability cash
flow by guarantee and non-guarantee".

This module produces the ECONOMIC-SCENARIO / ASSET-RETURN half of that
directive as a governed DIAGNOSTIC OVERLAY:

* real-world (Measure.P) Hull-White 1F short-rate paths and correlated GBM
  equity-index paths, simulated with the SAVED run seed
  (``run_settings.seed``) on the governed educational parameters;
* per-asset-class monthly return paths derived from those drivers with the
  SAME class mechanics as the CF-1 projection set (bond carry + duration
  mark-to-market proxy, equity total return, cash carry);
* percentile FANS (p5/p25/p50/p75/p95 per month) for every series plus a
  small set of raw SAMPLE paths for stepwise display;
* JSON + CSV artifacts under ``<out_dir>/`` with an inputs digest so GUI
  callers can cache until seed / horizon / balance sheet change.

Governance: this is display-only evidence - NO governed headline figure
(TVOG, aggregation report) is touched; parameters are the governed
educational placeholders and every artifact carries an UNSIGNED note.
Asset cash flow by class and the guaranteed / non-guaranteed liability
split are served by the CF-1 projection set (``cashflow_projection_set``);
this module completes the picture with the stochastic path layer.
"""
from __future__ import annotations

import hashlib
import json
import os
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from par_model_v2.projection.cashflow_projection_set import (
    ASSET_CLASS_MECHANICS, _DEFAULT_ASSET_MECHANICS, _mechanics_for)
from par_model_v2.stochastic.esg_process import (
    GBMEquityProcess, HullWhiteRateProcess, Measure, _antithetic_normals)

SCHEMA_VERSION = "gd1-path-detail-1.0"
PERCENTILES = (5, 25, 50, 75, 95)
DEFAULT_N_PATHS = 200
DEFAULT_HORIZON_MONTHS = 480          # 40y display default
MAX_HORIZON_MONTHS = 1200             # CF-set horizon cap
MIN_HORIZON_MONTHS = 12
DEFAULT_N_DISPLAY = 20                # raw sample paths surfaced to the GUI

UNSIGNED_NOTE = (
    "UNSIGNED - diagnostic scenario-path overlay on governed educational "
    "(placeholder-calibrated) HW1F/GBM parameters; display evidence only, "
    "no governed headline figure is produced or altered.")

JSON_NAME = "path_detail.json"
CSV_NAMES = {
    "short_rate_fan": "short_rate_fan.csv",
    "equity_index_fan": "equity_index_fan.csv",
    "asset_class_monthly_return_fan": "asset_class_monthly_return_fan.csv",
    "asset_class_cumulative_fan": "asset_class_cumulative_fan.csv",
    "sample_paths_short_rate": "sample_paths_short_rate.csv",
    "sample_paths_equity_index": "sample_paths_equity_index.csv",
}


# ---------------------------------------------------------------------------
# inputs digest (cache key for GUI callers)
# ---------------------------------------------------------------------------
def _inputs_digest(model_inputs: Dict[str, Any], n_paths: int,
                   horizon_months: int) -> str:
    rs = (model_inputs or {}).get("run_settings") or {}
    basis = {
        "schema": SCHEMA_VERSION,
        "seed": rs.get("seed"),
        "n_paths": int(n_paths),
        "horizon_months": int(horizon_months),
        "balance_sheet": (model_inputs or {}).get("balance_sheet"),
    }
    return hashlib.sha256(
        json.dumps(basis, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()


def _resolve_horizon(model_inputs: Dict[str, Any],
                     horizon_months: Optional[int]) -> int:
    if horizon_months is None:
        rs = (model_inputs or {}).get("run_settings") or {}
        try:
            horizon_months = int(rs.get("horizon_months") or DEFAULT_HORIZON_MONTHS)
        except (TypeError, ValueError):
            horizon_months = DEFAULT_HORIZON_MONTHS
    return int(min(max(int(horizon_months), MIN_HORIZON_MONTHS),
                   MAX_HORIZON_MONTHS))


def _resolve_seed(model_inputs: Dict[str, Any]) -> int:
    rs = (model_inputs or {}).get("run_settings") or {}
    try:
        return int(rs.get("seed")) if rs.get("seed") is not None else 42
    except (TypeError, ValueError):
        return 42


# ---------------------------------------------------------------------------
# driver simulation (correlated HW1F + GBM, Measure.P)
# ---------------------------------------------------------------------------
def _simulate_drivers(n_paths: int, T: int, seed: int):
    """Correlated short-rate and equity paths, shape (n_paths, T+1) each.

    The plain ``simulate()`` DataFrame APIs draw INDEPENDENT shocks per
    driver; for a coherent stepwise display we correlate the equity shocks
    with the rate shocks at the governed ``rate_equity_correlation`` via the
    standard Gaussian construction z_e = rho*z_r + sqrt(1-rho^2)*z_iid.
    """
    rate_proc = HullWhiteRateProcess()
    eq_proc = GBMEquityProcess(rate_process=rate_proc)
    rho = float(eq_proc.params.rate_equity_correlation)

    rng_r = np.random.default_rng(seed)
    rng_e = np.random.default_rng(seed + 1)
    z_r = _antithetic_normals(rng_r, n_paths, T)
    z_i = _antithetic_normals(rng_e, n_paths, T)
    z_e = rho * z_r + np.sqrt(max(0.0, 1.0 - rho * rho)) * z_i

    rates = rate_proc._simulate_array(n_paths, T, Measure.P, z_r)
    equity, eq_returns = eq_proc._simulate_array(
        n_paths, T, Measure.P, rates, z_e)
    return rates, equity, eq_returns, rate_proc, eq_proc


# ---------------------------------------------------------------------------
# per-asset-class stochastic monthly returns (documented proxies)
# ---------------------------------------------------------------------------
def _par_bond_duration(annual_yield: float, maturity_years: float) -> float:
    """Modified-duration proxy of a par bond: (1-(1+y)^-M)/y (annual comp)."""
    y = max(float(annual_yield), 1e-6)
    return (1.0 - (1.0 + y) ** (-float(maturity_years))) / y


def _class_return_paths(label: str, rates: np.ndarray,
                        eq_returns: np.ndarray) -> np.ndarray:
    """Monthly return paths (n_paths, T) for one asset class.

    bond  : carry + duration mark-to-market proxy  y/12 - D * (r_m - r_{m-1})
    equity: GBM monthly total return (dividends are part of the CF set)
    cash  : short-rate carry r_{m-1}/12
    """
    mech = _mechanics_for(label)
    kind = mech.get("kind", "bond")
    dr = rates[:, 1:] - rates[:, :-1]
    if kind == "equity":
        return eq_returns[:, 1:]
    if kind == "cash":
        return rates[:, :-1] / 12.0
    y = float(mech.get("annual_yield",
                       _DEFAULT_ASSET_MECHANICS["annual_yield"]))
    mat = float(mech.get("avg_maturity_years",
                         _DEFAULT_ASSET_MECHANICS["avg_maturity_years"]))
    dur = _par_bond_duration(y, mat)
    return y / 12.0 - dur * dr


# ---------------------------------------------------------------------------
# fans + samples
# ---------------------------------------------------------------------------
def _fan(arr: np.ndarray) -> Dict[str, List[float]]:
    """Percentile fan per column of (n_paths, T[+1]) -> {p5: [...], ...}."""
    pct = np.percentile(arr, PERCENTILES, axis=0)
    return {"p%d" % p: np.round(pct[i], 8).tolist()
            for i, p in enumerate(PERCENTILES)}


def _fan_frame(fan: Dict[str, List[float]], months: np.ndarray,
               **extra_cols: str) -> pd.DataFrame:
    data: Dict[str, Any] = {"month": months}
    data.update({k: fan[k] for k in sorted(fan)})
    frame = pd.DataFrame(data)
    for name, val in extra_cols.items():
        frame.insert(0, name, val)
    return frame


def build_scenario_path_detail(model_inputs: Dict[str, Any],
                               out_dir: Optional[str] = None,
                               *,
                               n_paths: int = DEFAULT_N_PATHS,
                               horizon_months: Optional[int] = None,
                               n_display: int = DEFAULT_N_DISPLAY
                               ) -> Dict[str, Any]:
    """Build the stepwise scenario-path detail set; optionally write artifacts."""
    n_paths = int(min(max(int(n_paths), 10), 2000))
    T = _resolve_horizon(model_inputs, horizon_months)
    seed = _resolve_seed(model_inputs)
    n_show = int(min(max(int(n_display), 1), n_paths))

    rates, equity, eq_returns, rate_proc, eq_proc = _simulate_drivers(
        n_paths, T, seed)
    months_lvl = np.arange(0, T + 1)
    months_ret = np.arange(1, T + 1)

    # asset classes from the SAVED balance sheet (graceful when absent)
    assets = ((model_inputs or {}).get("balance_sheet") or {}).get("assets") or []
    labels = [str(a.get("asset_class")) for a in assets
              if a.get("asset_class")]
    seen, classes = set(), []
    for lbl in labels:
        if lbl not in seen:
            seen.add(lbl)
            classes.append(lbl)

    class_fans: Dict[str, Any] = {}
    cum_fans: Dict[str, Any] = {}
    ret_rows, cum_rows = [], []
    for lbl in classes:
        ret = _class_return_paths(lbl, rates, eq_returns)
        cum = 100.0 * np.cumprod(1.0 + ret, axis=1)
        cum = np.concatenate(
            [np.full((cum.shape[0], 1), 100.0), cum], axis=1)
        class_fans[lbl] = _fan(ret)
        cum_fans[lbl] = _fan(cum)
        ret_rows.append(_fan_frame(class_fans[lbl], months_ret,
                                   asset_class=lbl))
        cum_rows.append(_fan_frame(cum_fans[lbl], months_lvl,
                                   asset_class=lbl))

    digest = _inputs_digest(model_inputs, n_paths, T)
    payload: Dict[str, Any] = {
        "ok": True,
        "schema": SCHEMA_VERSION,
        "inputs_digest": digest,
        "unsigned_note": UNSIGNED_NOTE,
        "measure": "P",
        "seed": seed,
        "n_paths": n_paths,
        "n_display": n_show,
        "horizon_months": T,
        "parameters": {
            "rate_model": "Hull-White 1F (governed educational)",
            "mean_reversion_speed": rate_proc.params.mean_reversion_speed,
            "short_rate_vol": rate_proc.params.short_rate_vol,
            "initial_short_rate": rate_proc.params.initial_short_rate,
            "long_run_rate_p": rate_proc.params.long_run_rate_p,
            "equity_model": "GBM (governed educational)",
            "equity_vol": eq_proc.params.equity_vol,
            "dividend_yield": eq_proc.params.dividend_yield,
            "equity_risk_premium": eq_proc.params.equity_risk_premium,
            "rate_equity_correlation": eq_proc.params.rate_equity_correlation,
        },
        "asset_classes": classes,
        "asset_class_mechanics": {
            lbl: _mechanics_for(lbl) for lbl in classes},
        "fans": {
            "short_rate": _fan(rates),
            "equity_index": _fan(equity),
            "asset_class_monthly_return": class_fans,
            "asset_class_cumulative_index": cum_fans,
        },
        "samples": {
            "months": months_lvl.tolist(),
            "short_rate": np.round(rates[:n_show], 8).tolist(),
            "equity_index": np.round(equity[:n_show], 6).tolist(),
        },
    }

    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
        frames = {
            "short_rate_fan": _fan_frame(payload["fans"]["short_rate"],
                                         months_lvl),
            "equity_index_fan": _fan_frame(payload["fans"]["equity_index"],
                                           months_lvl),
            "asset_class_monthly_return_fan": (
                pd.concat(ret_rows, ignore_index=True) if ret_rows
                else pd.DataFrame()),
            "asset_class_cumulative_fan": (
                pd.concat(cum_rows, ignore_index=True) if cum_rows
                else pd.DataFrame()),
            "sample_paths_short_rate": pd.DataFrame(
                np.asarray(payload["samples"]["short_rate"]).T,
                columns=["path_%d" % i for i in range(n_show)]
            ).assign(month=months_lvl).set_index("month").reset_index(),
            "sample_paths_equity_index": pd.DataFrame(
                np.asarray(payload["samples"]["equity_index"]).T,
                columns=["path_%d" % i for i in range(n_show)]
            ).assign(month=months_lvl).set_index("month").reset_index(),
        }
        files = {}
        for key, name in CSV_NAMES.items():
            path = os.path.join(out_dir, name)
            frames[key].to_csv(path, index=False)
            files[key] = path
        json_path = os.path.join(out_dir, JSON_NAME)
        tmp = json_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, default=str)
        with open(tmp, encoding="utf-8") as fh:
            json.load(fh)  # re-parse guard (mid-write corruption seen before)
        os.replace(tmp, json_path)
        payload["files"] = files
        payload["json_path"] = json_path

    return payload
