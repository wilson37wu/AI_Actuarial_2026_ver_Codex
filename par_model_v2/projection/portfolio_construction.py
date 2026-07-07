"""PC-1 - Flexible portfolio construction (owner directive 2026-07-03).

Owner requirement: freely construct the insurance portfolio's INPUTS -

  * ASSET side: choose asset classes by TYPE (bond / equity / cash), their
    MIX and the SAA (strategic asset allocation weights) that both derives
    the balance sheet and drives the liability-coupled fund's rebalancing
    target and per-class mechanics;
  * LIABILITY side: define PRODUCT TEMPLATES (e.g. short-term vs long-term
    participating products) in a product catalogue - parameterised over the
    governed mechanic FAMILIES already in the engine - and compose the
    model-point portfolio from them.

Design principle: ADDITIVE to the governed input contract.  The run gate's
loader (``scripts/load_user_inputs.py``) still sees exactly the fields it
validates today: portfolio rows carry a mechanic-family ``product_type`` and
the derived ``balance_sheet`` is a plain asset-row list.  The new
``product_catalogue`` and ``asset_strategy`` blocks refine HOW the CF
projection engine parameterises those rows; they never bypass or alter the
gate.  Catalogue rates are scenario inputs and remain UNSIGNED pending
Model Owner approval.

Mechanic families (the calculation bases products map onto):
  * ``HKCD_PAR_2026`` - cash-dividend par endowment (tunable: cash-dividend
    rate, surrender value %);
  * ``HKRB_PAR_2026`` - reversionary-bonus par endowment (tunable: RB rate,
    terminal bonus %, surrender value %);
  * ``GMMB_EQ_2026``  - equity account with guaranteed maturity floor
    (tunable: surrender value %);
  * ``WL_PAR_2026``   - PC-2: whole-life participating (RB mechanics,
    endowment-at-limit convention);
  * ``TERM_2026``     - PC-2: level term assurance (protection);
  * ``ANNUITY_2026``  - PC-2: deferred life annuity (guaranteed payout).

PC-2 additionally allows OPTIONAL per-product expense/decrement overrides
(``OVERRIDE_PARAMS``) on any catalogue product; absent keys fall back to
the governed engine defaults so legacy catalogues project bit-identically.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

PC_SCHEMA_VERSION = "portfolio-construction-1.0"

#: mechanic families and the catalogue parameters each accepts
PRODUCT_FAMILIES: Dict[str, Dict[str, Any]] = {
    "HKCD_PAR_2026": {
        "label": "Cash-dividend participating endowment",
        "params": {
            "cash_dividend_rate": {"default": 0.012, "min": 0.0, "max": 0.20},
            "surrender_value_pct": {"default": 0.90, "min": 0.0, "max": 1.0},
        },
    },
    "HKRB_PAR_2026": {
        "label": "Reversionary-bonus participating endowment",
        "params": {
            "rb_rate": {"default": 0.025, "min": 0.0, "max": 0.20},
            "terminal_bonus_pct": {"default": 0.35, "min": 0.0, "max": 1.0},
            "surrender_value_pct": {"default": 0.90, "min": 0.0, "max": 1.0},
        },
    },
    "GMMB_EQ_2026": {
        "label": "Equity account with guaranteed maturity benefit",
        "params": {
            "surrender_value_pct": {"default": 0.90, "min": 0.0, "max": 1.0},
        },
    },
    # ---- PC-2 mechanic families (owner directive 2026-07-03, track 4.0d) ----
    "WL_PAR_2026": {
        "label": "Whole-life participating (RB mechanics, endowment-at-limit)",
        "params": {
            "rb_rate": {"default": 0.02, "min": 0.0, "max": 0.20},
            "terminal_bonus_pct": {"default": 0.30, "min": 0.0, "max": 1.0},
            "surrender_value_pct": {"default": 0.85, "min": 0.0, "max": 1.0},
        },
    },
    "TERM_2026": {
        "label": "Level term assurance (protection)",
        "params": {
            "surrender_value_pct": {"default": 0.0, "min": 0.0, "max": 1.0},
        },
    },
    "ANNUITY_2026": {
        "label": "Deferred life annuity (guaranteed payout)",
        "params": {
            "deferral_years": {"default": 10.0, "min": 1.0, "max": 50.0},
            "annuity_rate": {"default": 0.05, "min": 0.005, "max": 0.25},
            "surrender_value_pct": {"default": 0.90, "min": 0.0, "max": 1.0},
        },
    },
}

#: PC-2 - OPTIONAL per-product expense/decrement overrides, valid on ANY
#: catalogue product.  Only validated/applied when PRESENT; absent keys use
#: the governed engine defaults (cashflow_projection_set constants / base
#: decrement tables), keeping legacy catalogues bit-identical.
OVERRIDE_PARAMS: Dict[str, Dict[str, float]] = {
    "acq_expense_pct": {"min": 0.0, "max": 0.50},
    "renewal_expense_pct": {"min": 0.0, "max": 0.50},
    "renewal_expense_fixed_monthly": {"min": 0.0, "max": 1000.0},
    "mortality_multiplier": {"min": 0.01, "max": 10.0},
    "lapse_multiplier": {"min": 0.0, "max": 10.0},
}

ASSET_KINDS: Dict[str, List[str]] = {
    "bond": ["annual_yield", "avg_maturity_years"],
    "equity": ["annual_dividend_yield", "annual_capital_growth"],
    "cash": ["annual_yield"],
}

_RATE_BOUNDS = {"annual_yield": (0.0, 0.5),
                "annual_dividend_yield": (0.0, 0.5),
                "annual_capital_growth": (-0.5, 0.5),
                "avg_maturity_years": (0.25, 100.0)}


def default_product_catalogue() -> List[Dict[str, Any]]:
    """Starter catalogue: short & long par (CD and RB) + GMMB (editable)."""
    return [
        {"product_id": "PAR_CD_SHORT", "family": "HKCD_PAR_2026",
         "label": "Short-term cash-dividend par (5-10y)",
         "term_years_min": 5, "term_years_max": 10,
         "cash_dividend_rate": 0.015, "surrender_value_pct": 0.92},
        {"product_id": "PAR_CD_LONG", "family": "HKCD_PAR_2026",
         "label": "Long-term cash-dividend par (15-30y)",
         "term_years_min": 15, "term_years_max": 30,
         "cash_dividend_rate": 0.012, "surrender_value_pct": 0.90},
        {"product_id": "PAR_RB_LONG", "family": "HKRB_PAR_2026",
         "label": "Long-term reversionary-bonus par (15-30y)",
         "term_years_min": 15, "term_years_max": 30,
         "rb_rate": 0.025, "terminal_bonus_pct": 0.35,
         "surrender_value_pct": 0.90},
        {"product_id": "GMMB_STD", "family": "GMMB_EQ_2026",
         "label": "Equity GMMB (10-20y)",
         "term_years_min": 10, "term_years_max": 20,
         "surrender_value_pct": 0.90},
        {"product_id": "WL_PAR_STD", "family": "WL_PAR_2026",
         "label": "Whole-life par (endowment-at-limit, 30-70y)",
         "term_years_min": 30, "term_years_max": 70,
         "rb_rate": 0.02, "terminal_bonus_pct": 0.30,
         "surrender_value_pct": 0.85},
        {"product_id": "TERM_STD", "family": "TERM_2026",
         "label": "Level term assurance (5-30y)",
         "term_years_min": 5, "term_years_max": 30,
         "surrender_value_pct": 0.0},
        {"product_id": "ANNUITY_DEF", "family": "ANNUITY_2026",
         "label": "Deferred annuity (10y deferral, 15-40y)",
         "term_years_min": 15, "term_years_max": 40,
         "deferral_years": 10, "annuity_rate": 0.05,
         "surrender_value_pct": 0.90},
    ]


def default_asset_strategy() -> Dict[str, Any]:
    """Starter SAA (editable): 75% bonds across three classes, 15% equity,
    10% cash on a 200m book."""
    return {
        "total_market_value": 200_000_000.0,
        "rebalancing": "constant_mix",
        "saa": [
            {"asset_class": "Government bonds", "kind": "bond",
             "weight": 0.40, "annual_yield": 0.032,
             "avg_maturity_years": 10.0, "illiquid": False},
            {"asset_class": "Corporate bonds", "kind": "bond",
             "weight": 0.25, "annual_yield": 0.042,
             "avg_maturity_years": 7.0, "illiquid": False},
            {"asset_class": "Private credit", "kind": "bond",
             "weight": 0.10, "annual_yield": 0.060,
             "avg_maturity_years": 5.0, "illiquid": True},
            {"asset_class": "Equity", "kind": "equity",
             "weight": 0.15, "annual_dividend_yield": 0.025,
             "annual_capital_growth": 0.045, "illiquid": False},
            {"asset_class": "Cash", "kind": "cash",
             "weight": 0.10, "annual_yield": 0.020, "illiquid": False},
        ],
    }


def _num(v) -> Optional[float]:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if f == f else None  # NaN guard


# ---------------------------------------------------------------------------
# Validators (fail-loud, GUI-facing message format)
# ---------------------------------------------------------------------------

#: the liquidity-exposure engine (user_inputs.exposure_overrides) requires
#: a strictly positive illiquid share - surfaced here as a validation rule
ILLIQUID_RULE = ("at least one SAA asset class with weight > 0 must be "
                 "marked illiquid (the liquidity-exposure engine requires "
                 "0 < illiquid_share <= 1)")


def validate_asset_strategy(strategy: Any) -> List[str]:
    errors: List[str] = []
    if not isinstance(strategy, dict):
        return ["asset_strategy must be a JSON object"]
    total = _num(strategy.get("total_market_value"))
    if total is None or total <= 0:
        errors.append("[Asset strategy] total market value must be positive, "
                      "got %r" % strategy.get("total_market_value"))
    saa = strategy.get("saa")
    if not isinstance(saa, list) or not saa:
        errors.append("[Asset strategy] saa must be a non-empty array of "
                      "asset-class rows")
        return errors
    weight_sum = 0.0
    seen = set()
    for i, row in enumerate(saa, 1):
        if not isinstance(row, dict):
            errors.append("[Asset strategy] row %d must be a JSON object" % i)
            continue
        label = str(row.get("asset_class") or "").strip()
        if not label:
            errors.append("[Asset strategy] row %d: asset class label is "
                          "required" % i)
        elif label.lower() in seen:
            errors.append("[Asset strategy] row %d: duplicate asset class "
                          "%r" % (i, label))
        else:
            seen.add(label.lower())
        kind = str(row.get("kind") or "").strip().lower()
        if kind not in ASSET_KINDS:
            errors.append("[Asset strategy] row %d (%s): kind must be one of "
                          "%s, got %r" % (i, label, sorted(ASSET_KINDS),
                                          row.get("kind")))
            continue
        w = _num(row.get("weight"))
        if w is None or w < 0 or w > 1:
            errors.append("[Asset strategy] row %d (%s): weight must be in "
                          "[0, 1], got %r" % (i, label, row.get("weight")))
        else:
            weight_sum += w
        for pname in ASSET_KINDS[kind]:
            v = _num(row.get(pname))
            lo, hi = _RATE_BOUNDS[pname]
            if v is None or not (lo <= v <= hi):
                errors.append("[Asset strategy] row %d (%s): %s must be in "
                              "[%g, %g], got %r"
                              % (i, label, pname, lo, hi, row.get(pname)))
    if abs(weight_sum - 1.0) > 1e-6:
        errors.append("[Asset strategy] SAA weights must sum to 1.0 "
                      "(got %.6f)" % weight_sum)
    if not errors and not any(
            bool(r.get("illiquid")) and (_num(r.get("weight")) or 0) > 0
            for r in saa if isinstance(r, dict)):
        errors.append("[Asset strategy] " + ILLIQUID_RULE)
    return errors


def validate_product_catalogue(catalogue: Any) -> List[str]:
    errors: List[str] = []
    if not isinstance(catalogue, list) or not catalogue:
        return ["product_catalogue must be a non-empty JSON array"]
    seen = set()
    for i, p in enumerate(catalogue, 1):
        if not isinstance(p, dict):
            errors.append("[Catalogue] row %d must be a JSON object" % i)
            continue
        pid = str(p.get("product_id") or "").strip()
        if not pid:
            errors.append("[Catalogue] row %d: product_id is required" % i)
        elif pid in seen:
            errors.append("[Catalogue] row %d: duplicate product_id %r"
                          % (i, pid))
        else:
            seen.add(pid)
        family = str(p.get("family") or "").strip()
        if family not in PRODUCT_FAMILIES:
            errors.append("[Catalogue] %s: family must be one of %s, got %r"
                          % (pid or i, sorted(PRODUCT_FAMILIES), p.get("family")))
            continue
        tmin = _num(p.get("term_years_min"))
        tmax = _num(p.get("term_years_max"))
        if tmin is None or tmax is None or tmin <= 0 or tmax < tmin \
                or tmax > 100:
            errors.append("[Catalogue] %s: term range must satisfy "
                          "0 < min <= max <= 100, got %r..%r"
                          % (pid or i, p.get("term_years_min"),
                             p.get("term_years_max")))
        for pname, spec in PRODUCT_FAMILIES[family]["params"].items():
            v = p.get(pname, spec["default"])
            f = _num(v)
            if f is None or not (spec["min"] <= f <= spec["max"]):
                errors.append("[Catalogue] %s: %s must be in [%g, %g], got %r"
                              % (pid or i, pname, spec["min"], spec["max"], v))
        for pname, spec in OVERRIDE_PARAMS.items():  # PC-2, only if present
            if pname in p:
                f = _num(p[pname])
                if f is None or not (spec["min"] <= f <= spec["max"]):
                    errors.append("[Catalogue] %s: override %s must be in "
                                  "[%g, %g], got %r"
                                  % (pid or i, pname, spec["min"],
                                     spec["max"], p[pname]))
    return errors


def validate_composed_portfolio(rows: Any,
                                catalogue: List[Dict[str, Any]]) -> List[str]:
    """Composer-level checks: rows must reference catalogue products and
    respect the product's term range; family rules (e.g. CD cannot carry a
    vested RB) are re-checked here AND again by the governed loader."""
    errors: List[str] = []
    if not isinstance(rows, list) or not rows:
        return ["portfolio must be a non-empty JSON array of model points"]
    by_id = {str(p.get("product_id")): p for p in (catalogue or [])
             if isinstance(p, dict)}
    for i, row in enumerate(rows, 1):
        if not isinstance(row, dict):
            errors.append("[Portfolio] row %d must be a JSON object" % i)
            continue
        pid = str(row.get("product_id") or "").strip()
        if not pid:
            errors.append("[Portfolio] row %d: product_id is required "
                          "(pick a catalogue product)" % i)
            continue
        prod = by_id.get(pid)
        if prod is None:
            errors.append("[Portfolio] row %d: unknown product_id %r"
                          % (i, pid))
            continue
        term = _num(row.get("term_years"))
        tmin, tmax = _num(prod.get("term_years_min")), _num(
            prod.get("term_years_max"))
        if term is None or (tmin is not None and term < tmin) or (
                tmax is not None and term > tmax):
            errors.append("[Portfolio] row %d (%s): term %r outside the "
                          "product's range %g..%g"
                          % (i, pid, row.get("term_years"), tmin, tmax))
        if prod.get("family") in ("HKCD_PAR_2026", "TERM_2026",
                                  "ANNUITY_2026") \
                and (_num(row.get("vested_bonus")) or 0.0) > 0:
            errors.append("[Portfolio] row %d (%s): cash-dividend / "
                          "protection / annuity products cannot carry a "
                          "vested reversionary bonus" % (i, pid))
        if prod.get("family") == "ANNUITY_2026" and term is not None:
            dy = _num(prod.get("deferral_years", 10.0)) or 10.0
            if term <= dy:
                errors.append("[Portfolio] row %d (%s): annuity term %g must "
                              "exceed the deferral period %g years"
                              % (i, pid, term, dy))
    return errors


# ---------------------------------------------------------------------------
# Derivations (strategy -> balance sheet; composed rows -> loader rows)
# ---------------------------------------------------------------------------

def derive_balance_sheet(strategy: Dict[str, Any],
                         existing_bs: Optional[Dict[str, Any]] = None
                         ) -> Dict[str, Any]:
    """Balance-sheet asset rows from the SAA (mv = weight x total); the
    loader's scalar fields are preserved from the existing block (or given
    safe defaults) so the governed gate contract is fully satisfied."""
    total = float(strategy["total_market_value"])
    assets = [{"asset_class": str(r["asset_class"]),
               "market_value": round(float(r["weight"]) * total, 2),
               "illiquid": bool(r.get("illiquid", False))}
              for r in strategy["saa"] if float(r.get("weight", 0)) > 0]
    bs = dict(existing_bs or {})
    bs["assets"] = assets
    total_mv = round(sum(a["market_value"] for a in assets), 2)
    illiquid_mv = round(sum(a["market_value"] for a in assets
                            if a["illiquid"]), 2)
    bs["stated_total_backing_asset_mv"] = total_mv
    # loader-derived fields the RUN ENGINE requires (user_inputs.
    # exposure_overrides): total backing MV + illiquid share
    bs["backing_asset_mv"] = total_mv
    bs["illiquid_mv"] = illiquid_mv
    bs["illiquid_share"] = (illiquid_mv / total_mv) if total_mv > 0 else 0.0
    bs.setdefault("forced_sale_fraction", 0.20)
    bs.setdefault("best_estimate_liability", round(0.75 * total, 2))
    bs.setdefault("equity_guarantee_initial_index", 100.0)
    return bs


def asset_mechanics_from_strategy(strategy: Dict[str, Any]
                                  ) -> Dict[str, Dict[str, Any]]:
    """Per-class CF-engine mechanics keyed by the exact class label."""
    mechs: Dict[str, Dict[str, Any]] = {}
    for r in strategy.get("saa") or []:
        kind = str(r.get("kind")).lower()
        mech: Dict[str, Any] = {"kind": kind}
        for pname in ASSET_KINDS.get(kind, []):
            mech[pname] = float(r[pname])
        if kind == "equity":
            mech.setdefault("annual_capital_growth", 0.0)
        mechs[str(r.get("asset_class"))] = mech
    return mechs


def resolve_portfolio(rows: List[Dict[str, Any]],
                      catalogue: Optional[List[Dict[str, Any]]]
                      ) -> List[Dict[str, Any]]:
    """Attach mechanic family + catalogue parameters to composed rows.

    Rows WITHOUT a ``product_id`` (legacy inputs) pass through untouched -
    the engine then uses its governed defaults.  Returned rows always carry
    a loader-valid ``product_type`` (the family)."""
    by_id = {str(p.get("product_id")): p for p in (catalogue or [])
             if isinstance(p, dict)}
    out: List[Dict[str, Any]] = []
    for row in rows or []:
        r = dict(row)
        pid = str(r.get("product_id") or "").strip()
        prod = by_id.get(pid)
        if prod is not None:
            family = str(prod["family"])
            r["product_type"] = family
            mech: Dict[str, Any] = {}
            for pname, spec in PRODUCT_FAMILIES[family]["params"].items():
                mech[pname] = float(prod.get(pname, spec["default"]))
            for pname in OVERRIDE_PARAMS:  # PC-2: only when explicitly set
                if pname in prod:
                    mech[pname] = float(prod[pname])
            r["mechanics"] = mech
        out.append(r)
    return out
