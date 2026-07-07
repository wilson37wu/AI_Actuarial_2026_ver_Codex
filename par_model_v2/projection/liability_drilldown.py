"""GD-2 - Stepwise liability drill-down set (owner directive 2026-07-07).

Owner requirement (roadmap 4.0e, GD-2): a per-model-point / per-product-
class BUCKET-LEVEL cash-flow inspector - pick a policy (portfolio row) or a
product class and see the month-by-month premium / expense / benefit
build-up including the guaranteed vs non-guaranteed split.

CONSISTENCY GUARANTEE: every number here is produced by the SAME row
projectors the CF-1 set aggregates (``_PRODUCT_PROJECTORS`` in
``cashflow_projection_set``), on the SAME resolved portfolio
(``resolve_portfolio`` applies PC-1 catalogue mechanics first).  Summing
the per-model-point drill-down over rows therefore reproduces the CF-1
class totals EXACTLY - regression-tested in
``tests/test_gd2_liability_drilldown.py``.

Added stepwise columns beyond the CF-1 buckets: beginning-of-month
in-force policy count and the month's expected death / surrender counts
(the decrement build-up that drives the cash flows), cumulative net cash
flow, and the guaranteed / non-guaranteed benefit subtotals.

Artifacts (when ``out_dir`` is given): ``LIABILITY_DRILLDOWN_SET.json``
plus two tidy CSVs (monthly + yearly, one block per selection), all
stamped with the inputs digest for cache invalidation.  Diagnostic overlay
only - governed headline figures untouched; declaration scales UNSIGNED.
"""
from __future__ import annotations

import hashlib
import json
import os
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from par_model_v2.projection.cashflow_projection_set import (
    HORIZON_MONTHS,
    LIABILITY_BUCKETS,
    UNSIGNED_NOTE,
    _PRODUCT_PROJECTORS,
    _RowBuckets,
    _decrements,
)

SCHEMA_VERSION = "liability-drilldown-1.0"
JSON_NAME = "LIABILITY_DRILLDOWN_SET.json"
CSV_NAMES = ["liability_drilldown_monthly.csv",
             "liability_drilldown_yearly.csv"]

GUARANTEED_BUCKETS = [b for b in LIABILITY_BUCKETS
                      if b.endswith("_guaranteed")
                      and not b.endswith("_non_guaranteed")]
NON_GUARANTEED_BUCKETS = [b for b in LIABILITY_BUCKETS
                          if b.endswith("_non_guaranteed")] + ["cash_dividend"]

#: stepwise columns, in output order
STEP_COLUMNS = (["month", "in_force_bom", "death_count", "surrender_count",
                 "premium", "expense"]
                + [b for b in LIABILITY_BUCKETS
                   if b not in ("premium", "expense")]
                + ["benefit_guaranteed", "benefit_non_guaranteed",
                   "total_benefit", "net_cashflow", "cumulative_net"])


def _inputs_digest(model_inputs: Dict[str, Any]) -> str:
    """Digest over the inputs the drill-down depends on (portfolio +
    catalogue only - balance sheet does not enter the liability view)."""
    blob = json.dumps(
        {"portfolio": model_inputs.get("portfolio"),
         "product_catalogue": model_inputs.get("product_catalogue")},
        sort_keys=True, default=str).encode("utf-8")
    return "sha256:" + hashlib.sha256(blob).hexdigest()


def _coerce_portfolio(model_inputs: Dict[str, Any]) -> List[Dict[str, Any]]:
    """IDENTICAL coercion to ``build_cashflow_projection_set`` (CF-1)."""
    portfolio = []
    for r in (model_inputs.get("portfolio") or []):
        portfolio.append({
            "product_type": str(r.get("product_type")),
            "issue_age": int(float(r.get("issue_age"))),
            "gender": str(r.get("gender") or "M"),
            "term_years": int(float(r.get("term_years"))),
            "sum_assured": float(r.get("sum_assured")),
            "annual_premium": float(r.get("annual_premium")),
            "policy_count": float(r.get("policy_count")),
            "vested_bonus": float(r.get("vested_bonus") or 0.0),
            **({"product_id": str(r["product_id"])} if r.get("product_id") else {}),
            **({"mechanics": r["mechanics"]}
               if isinstance(r.get("mechanics"), dict) else {}),
        })
    return portfolio


def _row_stepwise(row: Dict[str, Any]) -> Dict[str, np.ndarray]:
    """One resolved portfolio row -> stepwise monthly arrays (len 1200).

    Buckets come from the CF-1 projector for the row's product type;
    decrement counts re-run the SAME ``_decrements`` the projector used."""
    out = _RowBuckets()
    ptype = str(row.get("product_type"))
    if ptype not in _PRODUCT_PROJECTORS:
        raise ValueError("unknown product_type: %r" % ptype)
    _PRODUCT_PROJECTORS[ptype](row, out)
    T = min(int(row["term_years"]) * 12, HORIZON_MONTHS)
    count = float(row["policy_count"])
    q, l, in_force = _decrements(int(row["issue_age"]), row["gender"], T)
    arrays: Dict[str, np.ndarray] = {b: out.arrays[b] for b in LIABILITY_BUCKETS}
    ifb = np.zeros(HORIZON_MONTHS)
    dth = np.zeros(HORIZON_MONTHS)
    srr = np.zeros(HORIZON_MONTHS)
    ifb[:T] = count * in_force[:T]
    dth[:T] = count * in_force[:T] * q
    srr[:T] = count * in_force[:T] * (1.0 - q) * l
    arrays["in_force_bom"] = ifb
    arrays["death_count"] = dth
    arrays["surrender_count"] = srr
    return arrays


def _selection_frame(arrays: Dict[str, np.ndarray]) -> pd.DataFrame:
    """Stepwise monthly frame (months 1..1200) from bucket + count arrays."""
    df = pd.DataFrame({"month": np.arange(1, HORIZON_MONTHS + 1)})
    for c in ("in_force_bom", "death_count", "surrender_count"):
        df[c] = arrays[c]
    for b in LIABILITY_BUCKETS:
        df[b] = arrays[b]
    df["benefit_guaranteed"] = sum(df[b] for b in GUARANTEED_BUCKETS)
    df["benefit_non_guaranteed"] = sum(df[b] for b in NON_GUARANTEED_BUCKETS)
    df["total_benefit"] = df["benefit_guaranteed"] + df["benefit_non_guaranteed"]
    df["net_cashflow"] = df["premium"] - df["expense"] - df["total_benefit"]
    df["cumulative_net"] = df["net_cashflow"].cumsum()
    return df[STEP_COLUMNS]


def yearly_stepwise(monthly: pd.DataFrame) -> pd.DataFrame:
    """Yearly grid 1..100: cash flows SUM; in-force takes the year-START
    (BOM of month 12k-11) count; decrement counts SUM; cumulative_net takes
    the year-END value."""
    df = monthly.copy()
    df["year"] = ((df["month"] - 1) // 12) + 1
    flow_cols = [c for c in STEP_COLUMNS
                 if c not in ("month", "in_force_bom", "cumulative_net")]
    out = df.groupby("year", as_index=False)[flow_cols].sum()
    bom = df[df["month"] % 12 == 1][["year", "in_force_bom"]]
    eoy = df[df["month"] % 12 == 0][["year", "cumulative_net"]]
    out = out.merge(bom, on="year").merge(eoy, on="year",
                                          suffixes=("_sum", ""))
    # groupby summed cumulative_net too - drop it in favour of the year-end
    out = out.drop(columns=["cumulative_net_sum"], errors="ignore")
    cols = ["year"] + [c for c in STEP_COLUMNS if c != "month"]
    return out[cols]


def build_liability_drilldown(model_inputs: Dict[str, Any],
                              out_dir: Optional[str] = None) -> Dict[str, Any]:
    """Build the GD-2 stepwise drill-down set.

    Selections = every portfolio row (model point) + every product class
    (aggregate of its rows).  Returns metadata + per-selection monthly /
    yearly frames; writes JSON + 2 CSV artifacts when ``out_dir`` given."""
    portfolio = _coerce_portfolio(model_inputs)
    if not portfolio:
        raise ValueError("portfolio is empty - nothing to drill into")
    from par_model_v2.projection.portfolio_construction import resolve_portfolio
    resolved = resolve_portfolio(portfolio, model_inputs.get("product_catalogue"))

    selections: List[Dict[str, Any]] = []
    frames: Dict[str, pd.DataFrame] = {}
    class_arrays: Dict[str, Dict[str, np.ndarray]] = {}
    for i, row in enumerate(resolved):
        arrays = _row_stepwise(row)
        cls = str(row.get("product_id") or row.get("product_type"))
        sel_id = "mp-%d" % (i + 1)
        label = ("MP-%d %s | age %d %s | term %dy | SA %s | %s policies"
                 % (i + 1, cls, int(row["issue_age"]), row["gender"],
                    int(row["term_years"]),
                    format(int(row["sum_assured"]), ","),
                    format(int(row["policy_count"]), ",")))
        selections.append({"id": sel_id, "kind": "model_point",
                           "label": label, "product_class": cls,
                           "term_months": min(int(row["term_years"]) * 12,
                                              HORIZON_MONTHS)})
        frames[sel_id] = _selection_frame(arrays)
        agg = class_arrays.setdefault(cls, {})
        for k, v in arrays.items():
            agg[k] = agg.get(k, 0) + v
    for cls in sorted(class_arrays):
        sel_id = "class-%s" % cls
        selections.append({"id": sel_id, "kind": "product_class",
                           "label": "CLASS %s (all model points)" % cls,
                           "product_class": cls,
                           "term_months": HORIZON_MONTHS})
        frames[sel_id] = _selection_frame(class_arrays[cls])

    digest = _inputs_digest(model_inputs)
    result: Dict[str, Any] = {
        "ok": True,
        "schema": SCHEMA_VERSION,
        "basis": "deterministic_central",
        "unsigned_note": UNSIGNED_NOTE,
        "inputs_digest": digest,
        "horizon": {"months": HORIZON_MONTHS, "years": HORIZON_MONTHS // 12},
        "step_columns": STEP_COLUMNS,
        "selections": selections,
        "totals": {s["id"]: {
            "premium": float(frames[s["id"]]["premium"].sum()),
            "expense": float(frames[s["id"]]["expense"].sum()),
            "benefit_guaranteed":
                float(frames[s["id"]]["benefit_guaranteed"].sum()),
            "benefit_non_guaranteed":
                float(frames[s["id"]]["benefit_non_guaranteed"].sum()),
            "net_cashflow": float(frames[s["id"]]["net_cashflow"].sum()),
        } for s in selections},
    }
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
        monthly_blocks, yearly_blocks = [], []
        for s in selections:
            m = frames[s["id"]].copy()
            y = yearly_stepwise(frames[s["id"]])
            m.insert(0, "selection", s["id"])
            y.insert(0, "selection", s["id"])
            monthly_blocks.append(m)
            yearly_blocks.append(y)
        paths = {}
        for name, df in ((CSV_NAMES[0], pd.concat(monthly_blocks,
                                                  ignore_index=True)),
                         (CSV_NAMES[1], pd.concat(yearly_blocks,
                                                  ignore_index=True))):
            path = os.path.join(out_dir, name)
            df.to_csv(path, index=False)
            paths[name] = os.path.abspath(path)
        result["csv_paths"] = paths
        json_path = os.path.join(out_dir, JSON_NAME)
        payload = dict(result)
        payload["yearly_preview"] = {
            s["id"]: yearly_stepwise(frames[s["id"]]).head(5)
            .round(2).to_dict(orient="records") for s in selections}
        with open(json_path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=1, default=str)
        with open(json_path, encoding="utf-8") as fh:
            json.load(fh)  # re-parse guard
        result["json_path"] = os.path.abspath(json_path)
    result["frames"] = frames
    return result
