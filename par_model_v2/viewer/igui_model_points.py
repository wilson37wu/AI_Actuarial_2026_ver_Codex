"""Phase IGUI Task 3 - policy / model-point data + in-force ingest core logic.

Pure, **standard-library-only** model-point layer for the owner-directed
Actuarial Input & Run GUI (Phase IGUI). This is the ``D2_policy_model_points``
domain of the Task-1 coverage map and the second staged input domain after the
Task-2 run controls. It holds everything the local runner
(``scripts/run_gui.py``) needs that is worth unit-testing in isolation:

  * :data:`MODEL_POINT_FIELDS` - declarative spec of an editable model-point row
    (the eight ``Portfolio`` columns the loader/engine already use);
  * :data:`BALANCE_SHEET_ASSET_FIELDS` / :data:`BALANCE_SHEET_SCALAR_FIELDS` -
    the balance-sheet asset rows + the scalar reserve/forced-sale/index fields;
  * :func:`default_model_points` / :func:`default_balance_sheet` - clean, valid
    starting rows (PAR + GMMB) so the page opens ready-to-validate;
  * :func:`normalize_model_points` - a raw GUI payload (rows of strings, as an
    HTML table delivers) -> typed model-point rows + per-row/per-field errors;
  * :func:`normalize_balance_sheet` - raw balance-sheet payload -> typed dict;
  * :func:`ingest_inforce` - parse an uploaded CSV **or** JSON in-force file and
    map flexible column/key names onto the canonical ``Portfolio`` schema;
  * :func:`reconcile_balance_sheet` - sum the asset rows and reconcile against
    the user's stated total (the same tolerance rule the Excel parser applies);
  * :func:`book_scaling_disclosure` - the DISCLOSED, NON-GOVERNED book-scaling
    preview, computed exactly as ``scripts/run_model.resolve_product`` reports
    it (inforce-weighted representative point + linear scale factor), so the
    user sees up-front what the engine will do with a multi-row book;
  * :func:`portfolio_to_model_inputs` - typed rows + balance sheet -> the
    ``model_inputs.json`` ``{portfolio, balance_sheet, totals}`` sub-schema that
    the loader-side validator (``scripts/load_user_inputs.validate_portfolio_dict``)
    accepts, so a GUI payload round-trips through the REAL loader's validation,
    fail-loud, before a run is ever permitted;
  * :func:`render_model_points_html` - a SELF-CONTAINED page (zero external
    references, zero JS network beyond same-origin POSTs) with interactive
    add/edit/delete of rows, a file-ingest control, and a live reconciliation +
    book-scaling panel, served on 127.0.0.1;
  * :func:`validate_task3_gate` - a Task-3 acceptance gate (structural checks +
    LIVE repo cross-checks), parallel to the Task-2 ``validate_task2_gate``.

Binding discipline (unchanged): NO model parameter changes; the input+run GUI
adds NO third-party runtime dependency (stdlib only); it binds 127.0.0.1 and
makes NO outbound network call; the Phase 30 stop-rule stands and the
MR-016/MR-017 owner decision is not pre-empted; the zero-install RESULTS UI
(``ui_app.html``) stays byte-unchanged. The governed headline SCR is carried
bit-for-bit. Field rules and enumerations are duplicated from the loader and
guarded equal by the Task-3 gate / tests so the GUI never diverges from the
template path.
"""

from __future__ import annotations

import csv as _csv
import datetime as _dt
import hashlib
import html as _html
import io as _io
import json
import os
import re
from typing import Any, Dict, List, Tuple

DOC_ID = "PHASE_IGUI_TASK3_MODEL_POINTS"
DOC_VERSION = "1.0.0"

#: Governed headline SCR (frozen single-df t), carried bit-for-bit wherever displayed.
GOVERNED_HEADLINE = "39,975.654628199336"

#: model_inputs.json schema version (kept in lock-step with
#: scripts/load_user_inputs.SCHEMA_VERSION; the Task-3 gate asserts equality).
SCHEMA_VERSION = "1.0.0"

#: Frozen sha256 of the zero-install RESULTS UI; the gate asserts the live file
#: is byte-identical so Task 3 provably leaves ui_app.html unchanged.
UI_APP_SHA256 = "6dca35b3520297263dd06086a1ced18cf831efb3fab6a6e8a9cde744500d7e65"

#: Allowed enumerations - duplicated from the loader and guarded equal by a test.
ALLOWED_PRODUCT_TYPES = ("HKCD_PAR_2026", "HKRB_PAR_2026", "GMMB_EQ_2026", "WL_PAR_2026", "TERM_2026", "ANNUITY_2026")
ALLOWED_GENDERS = ("M", "F")
#: PC-2 - PAR rows for the book-scaling echo (mirror of USER_PRODUCT_LINE_MAP)
PAR_PRODUCT_TYPES = ("HKCD_PAR_2026", "HKRB_PAR_2026", "WL_PAR_2026")
#: PAR product lines (cash-dividend forbids a vested reversionary bonus) - mirror
#: of par_model_v2.projection.portfolio_generator.USER_PRODUCT_LINE_MAP.
CASH_DIVIDEND_PRODUCT = "HKCD_PAR_2026"
GMMB_PRODUCT = "GMMB_EQ_2026"

#: Third-party imports the GUI layer must NEVER pull in (stdlib-only contract).
FORBIDDEN_RUNTIME_IMPORTS = (
    "flask", "django", "fastapi", "aiohttp", "tornado", "bottle", "cherrypy",
    "requests", "httpx", "urllib3", "numpy", "pandas", "scipy", "openpyxl",
)

HTML_ARTIFACTS = ["ui_app.html", "model_result_viewer.html", "combined_model_app.html"]


# --------------------------------------------------------------------------
# (a) declarative model-point + balance-sheet specs (Task-1 domain D2)
# --------------------------------------------------------------------------
MODEL_POINT_FIELDS: List[Dict[str, Any]] = [
    {"id": "product_type", "label": "Product type", "kind": "choice",
     "choices": list(ALLOWED_PRODUCT_TYPES),
     "help": "PAR cash-dividend / PAR reversionary-bonus / GMMB equity guarantee / "
             "PC-2: whole-life par, term assurance, deferred annuity."},
    {"id": "issue_age", "label": "Issue age", "kind": "int", "min": 0, "max": 120,
     "help": "Integer age at issue, 0-120."},
    {"id": "gender", "label": "Gender", "kind": "choice", "choices": list(ALLOWED_GENDERS),
     "help": "M or F."},
    {"id": "term_years", "label": "Term (yrs)", "kind": "int", "min": 1,
     "help": "Positive policy term in years."},
    {"id": "sum_assured", "label": "Sum assured", "kind": "float", "min_excl": 0.0,
     "help": "Per-policy sum assured (> 0)."},
    {"id": "annual_premium", "label": "Annual premium", "kind": "float", "min": 0.0,
     "help": "Per-policy annual premium (>= 0)."},
    {"id": "policy_count", "label": "Policy count", "kind": "int", "min": 1,
     "help": "Number of in-force policies this model point represents (> 0)."},
    {"id": "vested_bonus", "label": "Vested bonus", "kind": "float", "min": 0.0,
     "help": "Vested reversionary bonus (>= 0; must be 0 for cash-dividend PAR)."},
]

#: Canonical Portfolio keys in template order (used for CSV ingest + ordering).
MODEL_POINT_KEYS = tuple(f["id"] for f in MODEL_POINT_FIELDS)

#: Flexible header/key aliases accepted when ingesting an in-force CSV/JSON file.
#: Keys are normalised (lower-cased, non-alphanumerics stripped) before lookup.
INFORCE_ALIASES: Dict[str, str] = {
    "producttype": "product_type", "product": "product_type", "plan": "product_type",
    "producttypecode": "product_type",
    "issueage": "issue_age", "age": "issue_age", "ageatissue": "issue_age",
    "gender": "gender", "sex": "gender",
    "termyrs": "term_years", "term": "term_years", "termyears": "term_years",
    "policyterm": "term_years",
    "sumassured": "sum_assured", "facevalue": "sum_assured", "facamount": "sum_assured",
    "sa": "sum_assured",
    "annualpremium": "annual_premium", "premium": "annual_premium",
    "modalpremium": "annual_premium", "ap": "annual_premium",
    "policycount": "policy_count", "count": "policy_count", "policies": "policy_count",
    "numpolicies": "policy_count", "inforcecount": "policy_count", "lives": "policy_count",
    "vestedbonus": "vested_bonus", "bonus": "vested_bonus",
    "reversionarybonus": "vested_bonus", "vb": "vested_bonus",
}

BALANCE_SHEET_ASSET_FIELDS: List[Dict[str, Any]] = [
    {"id": "asset_class", "label": "Asset class", "kind": "text"},
    {"id": "market_value", "label": "Market value", "kind": "float", "min": 0.0},
    {"id": "illiquid", "label": "Illiquid?", "kind": "bool"},
]

BALANCE_SHEET_SCALAR_FIELDS: List[Dict[str, Any]] = [
    {"id": "stated_total_backing_asset_mv", "label": "Total backing asset market value (stated)",
     "kind": "float", "min": 0.0, "optional": True,
     "help": "Optional stated total; reconciled against the sum of the asset rows."},
    {"id": "forced_sale_fraction", "label": "Forced-sale fraction (mass-lapse shock)",
     "kind": "float", "min_excl": 0.0, "max": 1.0,
     "help": "In (0, 1]."},
    {"id": "best_estimate_liability", "label": "Best-estimate liability (reserve)",
     "kind": "float", "min_excl": 0.0,
     "help": "Positive reserve."},
    {"id": "equity_guarantee_initial_index", "label": "Equity-guarantee initial index level",
     "kind": "float", "min_excl": 0.0,
     "help": "Positive index level."},
]


def default_model_points() -> List[Dict[str, str]]:
    """Three clean, valid default rows (two PAR + one GMMB), string-valued as a
    form table submits. These are an EXAMPLE book, not a model parameter."""
    return [
        {"product_type": "HKCD_PAR_2026", "issue_age": "45", "gender": "M",
         "term_years": "20", "sum_assured": "100000", "annual_premium": "5000",
         "policy_count": "1000", "vested_bonus": "0"},
        {"product_type": "HKRB_PAR_2026", "issue_age": "40", "gender": "F",
         "term_years": "25", "sum_assured": "250000", "annual_premium": "9000",
         "policy_count": "500", "vested_bonus": "1200"},
        {"product_type": "GMMB_EQ_2026", "issue_age": "50", "gender": "M",
         "term_years": "15", "sum_assured": "300000", "annual_premium": "12000",
         "policy_count": "250", "vested_bonus": "0"},
    ]


def default_balance_sheet() -> Dict[str, Any]:
    """A clean, valid default balance sheet (asset rows + scalar fields)."""
    return {
        "assets": [
            {"asset_class": "Government bonds", "market_value": "120000000", "illiquid": "no"},
            {"asset_class": "Corporate bonds", "market_value": "60000000", "illiquid": "no"},
            {"asset_class": "Private credit", "market_value": "20000000", "illiquid": "yes"},
        ],
        "stated_total_backing_asset_mv": "200000000",
        "forced_sale_fraction": "0.20",
        "best_estimate_liability": "150000000",
        "equity_guarantee_initial_index": "100.0",
    }


# --------------------------------------------------------------------------
# (b) coercion helpers
# --------------------------------------------------------------------------
def _as_str(v: Any) -> str:
    return str(v).strip() if v is not None else ""


def _to_int(v: Any):
    s = _as_str(v).replace(",", "")
    if s == "":
        return None
    try:
        f = float(s)
    except (TypeError, ValueError):
        return None
    if f != int(f):
        return None
    return int(f)


def _to_float(v: Any):
    s = _as_str(v).replace(",", "")
    if s == "":
        return None
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


def _is_blank(v: Any) -> bool:
    return v is None or (isinstance(v, str) and not v.strip())


# --------------------------------------------------------------------------
# (c) normalisation: raw row payload -> typed model-point rows
# --------------------------------------------------------------------------
def normalize_model_points(rows: Any) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Coerce a raw (string) GUI row list into typed model-point dicts.

    Returns ``(typed_rows, errors)``. Type-coercion problems are reported here
    in the fail-loud ``row <n>, field '<id>'`` format; deeper range/consistency
    validation is the loader's job (round-tripped via
    :func:`portfolio_to_model_inputs` then the loader gate). Blank rows (every
    field empty) are skipped so an editable table can carry empty scaffolding.
    """
    errors: List[str] = []
    typed: List[Dict[str, Any]] = []
    if not isinstance(rows, list):
        return [], ["portfolio rows must be a JSON array"]
    int_ids = {f["id"] for f in MODEL_POINT_FIELDS if f["kind"] == "int"}
    float_ids = {f["id"] for f in MODEL_POINT_FIELDS if f["kind"] == "float"}
    for k, raw in enumerate(rows, 1):
        if not isinstance(raw, dict):
            errors.append("row %d: must be a JSON object" % k)
            continue
        if all(_is_blank(raw.get(f["id"])) for f in MODEL_POINT_FIELDS):
            continue  # skip an entirely blank scaffold row
        rec: Dict[str, Any] = {}
        for f in MODEL_POINT_FIELDS:
            fid = f["id"]
            v = raw.get(fid)
            if fid in int_ids:
                iv = _to_int(v)
                if iv is None:
                    errors.append("row %d, field '%s': must be an integer, got %r" % (k, fid, v))
                else:
                    rec[fid] = iv
            elif fid in float_ids:
                fv = _to_float(v)
                if fv is None:
                    errors.append("row %d, field '%s': must be a number, got %r" % (k, fid, v))
                else:
                    rec[fid] = fv
            else:
                rec[fid] = _as_str(v)
        rec["source_row"] = k
        typed.append(rec)
    return typed, errors


def normalize_balance_sheet(payload: Any) -> Tuple[Dict[str, Any], List[str]]:
    """Coerce a raw balance-sheet payload into a typed dict (asset rows typed,
    scalar fields typed). Returns ``(typed, errors)``."""
    errors: List[str] = []
    if not isinstance(payload, dict):
        return {}, ["balance_sheet must be a JSON object"]
    out: Dict[str, Any] = {"assets": []}
    raw_assets = payload.get("assets")
    if not isinstance(raw_assets, list):
        errors.append("balance_sheet.assets must be a JSON array")
        raw_assets = []
    for k, row in enumerate(raw_assets, 1):
        if not isinstance(row, dict):
            errors.append("asset row %d: must be a JSON object" % k)
            continue
        if all(_is_blank(row.get(f["id"])) for f in BALANCE_SHEET_ASSET_FIELDS):
            continue
        label = _as_str(row.get("asset_class"))
        mv = _to_float(row.get("market_value"))
        illiq_raw = _as_str(row.get("illiquid")).lower()
        rec: Dict[str, Any] = {"asset_class": label}
        if mv is None:
            errors.append("asset row %d, field 'market_value': must be a number, got %r"
                          % (k, row.get("market_value")))
        else:
            rec["market_value"] = mv
        if illiq_raw in ("yes", "true", "1", "y"):
            rec["illiquid"] = True
        elif illiq_raw in ("no", "false", "0", "n", ""):
            rec["illiquid"] = False
        else:
            errors.append("asset row %d, field 'illiquid': must be Yes/No, got %r"
                          % (k, row.get("illiquid")))
        out["assets"].append(rec)
    for f in BALANCE_SHEET_SCALAR_FIELDS:
        fid = f["id"]
        v = payload.get(fid)
        if _is_blank(v):
            if f.get("optional"):
                continue
            errors.append("balance_sheet field '%s': must be a number, got %r" % (fid, v))
            continue
        fv = _to_float(v)
        if fv is None:
            errors.append("balance_sheet field '%s': must be a number, got %r" % (fid, v))
        else:
            out[fid] = fv
    return out, errors


# --------------------------------------------------------------------------
# (d) in-force file ingest (CSV or JSON) -> canonical Portfolio rows
# --------------------------------------------------------------------------
def _alias_key(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", _as_str(name).lower())


def _map_inforce_record(rec: Dict[str, Any]) -> Dict[str, str]:
    """Map one flexible in-force record onto the canonical schema (strings)."""
    out: Dict[str, str] = {}
    for k, v in rec.items():
        canon = INFORCE_ALIASES.get(_alias_key(k))
        if canon is None and _alias_key(k) in {_alias_key(c) for c in MODEL_POINT_KEYS}:
            # exact canonical key (already in schema)
            canon = next(c for c in MODEL_POINT_KEYS if _alias_key(c) == _alias_key(k))
        if canon is not None:
            out[canon] = _as_str(v)
    return out


def ingest_inforce(text: str, fmt: str = "auto") -> Tuple[List[Dict[str, str]], List[str]]:
    """Parse an uploaded in-force file (CSV or JSON) into canonical, string-valued
    ``Portfolio`` rows ready for :func:`normalize_model_points`.

    ``fmt`` is ``"csv"``, ``"json"`` or ``"auto"`` (sniff on the leading
    non-whitespace char). Column/key names are matched flexibly via
    :data:`INFORCE_ALIASES`; gender is upper-cased and obvious product aliases
    are normalised. Returns ``(rows, errors)`` - it does NOT validate ranges
    (that is the loader's job); it only confirms a usable shape and reports
    unmappable / empty files fail-loud.
    """
    errors: List[str] = []
    s = (text or "").strip()
    if not s:
        return [], ["in-force file is empty"]
    if fmt == "auto":
        fmt = "json" if s[0] in "[{" else "csv"

    raw_records: List[Dict[str, Any]] = []
    if fmt == "json":
        try:
            obj = json.loads(s)
        except json.JSONDecodeError as exc:
            return [], ["in-force JSON is not parseable: %s" % exc]
        if isinstance(obj, dict):
            obj = obj.get("portfolio") if isinstance(obj.get("portfolio"), list) else [obj]
        if not isinstance(obj, list):
            return [], ["in-force JSON must be a list of records (or {portfolio: [...]})"]
        for k, r in enumerate(obj, 1):
            if not isinstance(r, dict):
                errors.append("record %d: must be a JSON object" % k)
                continue
            raw_records.append(r)
    else:  # csv
        try:
            reader = _csv.DictReader(_io.StringIO(s))
            if not reader.fieldnames:
                return [], ["in-force CSV has no header row"]
            for r in reader:
                raw_records.append(dict(r))
        except (_csv.Error, ValueError) as exc:
            return [], ["in-force CSV is not parseable: %s" % exc]

    rows: List[Dict[str, str]] = []
    for k, rec in enumerate(raw_records, 1):
        mapped = _map_inforce_record(rec)
        if not mapped:
            errors.append("record %d: no recognisable Portfolio columns found" % k)
            continue
        if "gender" in mapped:
            mapped["gender"] = mapped["gender"].upper()[:1] if mapped["gender"] else ""
        if "product_type" in mapped:
            mapped["product_type"] = _normalize_product_alias(mapped["product_type"])
        # fill any missing canonical keys with blank so the editor shows them
        for key in MODEL_POINT_KEYS:
            mapped.setdefault(key, "")
        rows.append(mapped)
    if not rows and not errors:
        errors.append("in-force file produced no usable rows")
    return rows, errors


def _normalize_product_alias(val: str) -> str:
    v = _as_str(val)
    up = v.upper()
    if up in ALLOWED_PRODUCT_TYPES:
        return up
    al = _alias_key(v)
    if al in ("cash", "cashdividend", "hkcd", "par", "parcash"):
        return "HKCD_PAR_2026"
    if al in ("rb", "reversionary", "reversionarybonus", "hkrb", "parrb"):
        return "HKRB_PAR_2026"
    if al in ("gmmb", "equityguarantee", "gmmbeq", "eq"):
        return "GMMB_EQ_2026"
    if al in ("wl", "wholelife", "wholelifepar", "wlpar"):
        return "WL_PAR_2026"
    if al in ("term", "termassurance", "termlife", "protection"):
        return "TERM_2026"
    if al in ("annuity", "deferredannuity", "annuitydef", "ann"):
        return "ANNUITY_2026"
    return v  # leave as-is; loader reports the invalid product fail-loud


# --------------------------------------------------------------------------
# (e) reconciliation + book-scaling disclosure
# --------------------------------------------------------------------------
def reconcile_balance_sheet(typed_bs: Dict[str, Any]) -> Dict[str, Any]:
    """Sum the asset rows and reconcile against the user's stated total, with the
    SAME tolerance the Excel parser uses (max(1e-6 * total, 1e-9)). Also derive
    the illiquid market value + share. Pure echo for the page - no validation."""
    assets = typed_bs.get("assets") or []
    total = 0.0
    illiquid = 0.0
    for a in assets:
        mv = a.get("market_value")
        if isinstance(mv, (int, float)):
            total += float(mv)
            if a.get("illiquid"):
                illiquid += float(mv)
    stated = typed_bs.get("stated_total_backing_asset_mv")
    out: Dict[str, Any] = {
        "sum_of_asset_rows": total,
        "stated_total_backing_asset_mv": stated,
        "illiquid_mv": illiquid,
        "illiquid_share": (illiquid / total) if total > 0 else None,
        "n_asset_rows": len(assets),
    }
    if isinstance(stated, (int, float)) and total > 0:
        tol = max(1e-6 * total, 1e-9)
        out["reconciles"] = abs(float(stated) - total) <= tol
        out["difference"] = float(stated) - total
        out["tolerance"] = tol
    else:
        out["reconciles"] = None
        out["difference"] = None
        out["tolerance"] = None
    return out


def book_scaling_disclosure(typed_rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """The DISCLOSED, NON-GOVERNED book-scaling preview, computed exactly as
    ``scripts/run_model.resolve_product`` reports it: the engine prices ONE
    inforce-weighted representative PAR model point; book totals + a linear
    scale factor are disclosed alongside (an approximation, not a governed
    result). GMMB rows are routed separately and only their count is disclosed.

    Pure stdlib arithmetic (no numpy) - this only ECHOES what the orchestrator
    already does; it computes no governed figure and changes no parameter.
    """
    par = [r for r in typed_rows if r.get("product_type") in PAR_PRODUCT_TYPES]
    gmmb = [r for r in typed_rows if r.get("product_type") not in PAR_PRODUCT_TYPES]
    out: Dict[str, Any] = {
        "n_model_point_rows": len(typed_rows),
        "par_rows": len(par),
        "gmmb_rows_disclosed": len(gmmb),
        "note": ("DISCLOSED APPROXIMATION, not a governed result: the engine "
                 "prices one inforce-weighted representative PAR model point; "
                 "multiplying per-point capital by linear_scale_factor assumes "
                 "homogeneous-book linear scaling. GMMB rows are routed by the "
                 "orchestrator, not the PAR portfolio."),
    }
    # need numeric sum_assured + policy_count on every PAR row
    usable = [r for r in par
              if isinstance(r.get("sum_assured"), (int, float))
              and isinstance(r.get("policy_count"), (int, float))]
    if not usable:
        out["book_scaling"] = None
        return out
    w_total = float(sum(float(r["policy_count"]) for r in usable))
    sa_weighted_total = float(sum(float(r["sum_assured"]) * float(r["policy_count"])
                                  for r in usable))
    rep_sa = (sa_weighted_total / w_total) if w_total > 0 else None
    out["book_scaling"] = {
        "policy_count_total": w_total,
        "sum_assured_total": sa_weighted_total,
        "representative_sum_assured": rep_sa,
        "linear_scale_factor": (sa_weighted_total / rep_sa) if rep_sa else None,
    }
    return out


# --------------------------------------------------------------------------
# (f) typed rows + balance sheet -> model_inputs.json {portfolio, balance_sheet}
# --------------------------------------------------------------------------
def _balance_sheet_to_model_inputs(typed_bs: Dict[str, Any]) -> Dict[str, Any]:
    """Build the loader-compatible balance_sheet sub-schema (assets + derived
    backing_asset_mv / illiquid_share + scalar reserve fields)."""
    rec = reconcile_balance_sheet(typed_bs)
    bs: Dict[str, Any] = {
        "assets": list(typed_bs.get("assets") or []),
        "backing_asset_mv": rec["sum_of_asset_rows"],
        "illiquid_mv": rec["illiquid_mv"],
        "illiquid_share": rec["illiquid_share"],
    }
    for fid in ("forced_sale_fraction", "best_estimate_liability",
                "equity_guarantee_initial_index"):
        if fid in typed_bs:
            bs[fid] = typed_bs[fid]
    if "stated_total_backing_asset_mv" in typed_bs:
        bs["stated_total_backing_asset_mv"] = typed_bs["stated_total_backing_asset_mv"]
    return bs


def portfolio_to_model_inputs(typed_rows: List[Dict[str, Any]],
                              typed_bs: Dict[str, Any],
                              *, generated_at: str = None) -> Dict[str, Any]:
    """Build the ``model_inputs.json`` ``{portfolio, balance_sheet, totals}``
    sub-schema (loader-compatible) from typed model-point rows + a typed balance
    sheet. The portfolio rows carry exactly the eight Portfolio keys plus
    ``source_row`` (the same shape ``scripts/load_user_inputs.parse_portfolio``
    emits and ``par_model_v2.user_inputs.user_model_points`` consumes)."""
    portfolio = []
    for r in typed_rows:
        rec = {k: r.get(k) for k in MODEL_POINT_KEYS}
        rec["source_row"] = r.get("source_row")
        portfolio.append(rec)
    bs = _balance_sheet_to_model_inputs(typed_bs)
    total_sa = 0.0
    pc = 0
    for r in typed_rows:
        if isinstance(r.get("sum_assured"), (int, float)) and isinstance(r.get("policy_count"), (int, float)):
            total_sa += float(r["sum_assured"]) * float(r["policy_count"])
            pc += int(r["policy_count"])
    totals = {
        "backing_asset_mv": bs.get("backing_asset_mv"),
        "total_sum_assured": total_sa,
        "policy_count": pc,
        "model_point_rows": len(portfolio),
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at or _dt.datetime.now(_dt.timezone.utc).isoformat(),
        "source": "igui_run_gui (Phase IGUI Task 3 model points + in-force ingest)",
        "portfolio": portfolio,
        "balance_sheet": bs,
        "totals": totals,
    }


# --------------------------------------------------------------------------
# (g) self-contained page (interactive add/edit/delete + ingest + reconcile)
# --------------------------------------------------------------------------
def _js_const(name: str, obj: Any) -> str:
    return "const %s=%s;" % (name, json.dumps(obj))


def render_model_points_html(rows: List[Dict[str, str]] = None,
                             balance_sheet: Dict[str, Any] = None) -> str:
    """Render the SELF-CONTAINED model-point page. No external src/href; the only
    network is same-origin POSTs to the local runner. Interactive add / edit /
    delete of rows, an in-force file-ingest control (CSV/JSON parsed locally and
    POSTed to /ingest), and a live reconciliation + book-scaling panel."""
    rows = rows if rows is not None else default_model_points()
    bs = balance_sheet if balance_sheet is not None else default_balance_sheet()
    fields_js = _js_const("FIELDS", [{"id": f["id"], "label": f["label"],
                                      "kind": f["kind"],
                                      "choices": f.get("choices", [])}
                                     for f in MODEL_POINT_FIELDS])
    bs_scalar_js = _js_const("BS_SCALARS", [{"id": f["id"], "label": f["label"],
                                             "optional": bool(f.get("optional"))}
                                            for f in BALANCE_SHEET_SCALAR_FIELDS])
    rows_js = _js_const("INIT_ROWS", rows)
    bs_js = _js_const("INIT_BS", bs)
    headline = _html.escape(GOVERNED_HEADLINE)
    _tmpl = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Actuarial Input &amp; Run GUI - Model Points (Phase IGUI Task 3)</title>
<style>
 body{font-family:system-ui,Arial,sans-serif;margin:0;background:#0f1722;color:#e7eef7}
 header{padding:16px 22px;background:#16263a;border-bottom:1px solid #24405e}
 h1{font-size:18px;margin:0}
 h2{font-size:15px;color:#8fb6e6;margin:18px 0 8px}
 main{max-width:1080px;margin:0 auto;padding:22px}
 table{border-collapse:collapse;width:100%;font-size:13px}
 th,td{border:1px solid #24405e;padding:4px 6px;text-align:left}
 th{background:#16263a;color:#8fb6e6}
 input,select{background:#0b1320;color:#e7eef7;border:1px solid #2c4a6b;border-radius:5px;padding:4px 6px;width:100%;box-sizing:border-box}
 .num{text-align:right}
 .actions{display:flex;gap:12px;margin:14px 0;flex-wrap:wrap}
 button{background:#2563eb;color:#fff;border:0;border-radius:6px;padding:9px 14px;font-size:14px;cursor:pointer}
 button.secondary{background:#33445c}
 button.del{background:#7a2533;padding:3px 9px;font-size:12px}
 .help{color:#7f97b3;font-size:12px;margin:2px 0 10px}
 #out{white-space:pre-wrap;background:#0b1320;border:1px solid #24405e;border-radius:8px;padding:12px;margin-top:14px;font-family:ui-monospace,Menlo,monospace;font-size:12.5px}
 #recon{background:#0b1320;border:1px solid #24405e;border-radius:8px;padding:12px;margin-top:10px;font-size:13px}
 .ok{color:#36d399}.bad{color:#f87272}.warn{color:#fbbd23}
 fieldset{border:1px solid #24405e;border-radius:8px;margin:0 0 14px;padding:12px 14px}
 legend{padding:0 8px;color:#8fb6e6;font-weight:600}
 .bsrow{display:grid;grid-template-columns:340px 220px;gap:10px;align-items:center;margin:6px 0}
 footer{color:#6c8099;font-size:12px;padding:12px 22px;border-top:1px solid #24405e}
</style></head>
<body>
<header><h1>Actuarial Input &amp; Run GUI &mdash; Model Points &amp; In-force</h1></header>
<main>
 <h2>Policy / model-point rows (PAR + GMMB)</h2>
 <div class="help">Add, edit or delete rows. Upload an in-force CSV/JSON to append rows (columns matched flexibly). Validation runs through the real loader (fail-loud) before any write.</div>
 <table id="mptab"><thead><tr id="mphead"></tr></thead><tbody id="mpbody"></tbody></table>
 <div class="actions">
  <button type="button" id="btn-add" class="secondary">+ Add row</button>
  <label class="secondary" style="background:#33445c;border-radius:6px;padding:9px 14px;cursor:pointer">Upload in-force file<input type="file" id="file" accept=".csv,.json,text/csv,application/json" style="display:none"></label>
 </div>

 <fieldset><legend>Balance sheet &mdash; backing assets</legend>
  <table id="astab"><thead><tr><th>Asset class</th><th>Market value</th><th>Illiquid?</th><th></th></tr></thead><tbody id="asbody"></tbody></table>
  <div class="actions"><button type="button" id="btn-add-asset" class="secondary">+ Add asset</button></div>
  <div id="bsscalars"></div>
 </fieldset>

 <div id="recon">Reconciliation &amp; book-scaling preview appears here.</div>

 <div class="actions">
  <button type="button" id="btn-validate" class="secondary">Validate</button>
  <button type="button" id="btn-save">Validate &amp; write model_inputs.json</button>
 </div>
 <div id="out">Ready. Reconciliation + disclosed book-scaling update live; validation is fail-loud via the real loader.</div>
</main>
<footer>Phase IGUI Task 3 &mdash; stdlib local runner (127.0.0.1, offline). Governed headline SCR carried bit-for-bit: __HEADLINE__. The zero-install RESULTS UI (ui_app.html) is unchanged.</footer>
<script>
__FIELDS_JS__
__BS_SCALARS_JS__
__ROWS_JS__
__BS_JS__
let rows = JSON.parse(JSON.stringify(INIT_ROWS));
let bs = JSON.parse(JSON.stringify(INIT_BS));

function el(t,a,c){const e=document.createElement(t);if(a)for(const k in a)e.setAttribute(k,a[k]);if(c!=null)e.textContent=c;return e;}
function buildHead(){const tr=document.getElementById('mphead');tr.innerHTML='';FIELDS.forEach(f=>tr.appendChild(el('th',null,f.label)));tr.appendChild(el('th',null,''));}
function cellInput(f,val,ri){
  let inp;
  if(f.kind==='choice'){inp=el('select');f.choices.forEach(c=>{const o=el('option',{value:c},c);if(c===val)o.selected=true;inp.appendChild(o);});}
  else{inp=el('input',{type:(f.kind==='int'||f.kind==='float')?'number':'text',value:val==null?'':val});if(f.kind!=='choice')inp.className='num';}
  inp.oninput=inp.onchange=()=>{rows[ri][f.id]=inp.value;refresh();};
  return inp;
}
function renderRows(){
  const tb=document.getElementById('mpbody');tb.innerHTML='';
  rows.forEach((r,ri)=>{
    const tr=el('tr');
    FIELDS.forEach(f=>{const td=el('td');td.appendChild(cellInput(f,r[f.id],ri));tr.appendChild(td);});
    const td=el('td');const b=el('button',{type:'button'},'Delete');b.className='del';b.onclick=()=>{rows.splice(ri,1);renderRows();refresh();};td.appendChild(b);tr.appendChild(td);
    tb.appendChild(tr);
  });
}
function blankRow(){const r={};FIELDS.forEach(f=>r[f.id]='');return r;}
function renderAssets(){
  const tb=document.getElementById('asbody');tb.innerHTML='';
  (bs.assets||[]).forEach((a,ai)=>{
    const tr=el('tr');
    const c1=el('td');const i1=el('input',{type:'text',value:a.asset_class||''});i1.oninput=()=>{bs.assets[ai].asset_class=i1.value;refresh();};c1.appendChild(i1);tr.appendChild(c1);
    const c2=el('td');const i2=el('input',{type:'number',value:a.market_value||''});i2.className='num';i2.oninput=()=>{bs.assets[ai].market_value=i2.value;refresh();};c2.appendChild(i2);tr.appendChild(c2);
    const c3=el('td');const s3=el('select');['no','yes'].forEach(o=>{const op=el('option',{value:o},o);if((a.illiquid||'').toString().toLowerCase()===o)op.selected=true;s3.appendChild(op);});s3.onchange=()=>{bs.assets[ai].illiquid=s3.value;refresh();};c3.appendChild(s3);tr.appendChild(c3);
    const c4=el('td');const b=el('button',{type:'button'},'Delete');b.className='del';b.onclick=()=>{bs.assets.splice(ai,1);renderAssets();refresh();};c4.appendChild(b);tr.appendChild(c4);
    tb.appendChild(tr);
  });
}
function renderScalars(){
  const wrap=document.getElementById('bsscalars');wrap.innerHTML='';
  BS_SCALARS.forEach(f=>{
    const row=el('div');row.className='bsrow';
    row.appendChild(el('label',null,f.label+(f.optional?' (optional)':'')));
    const inp=el('input',{type:'number',value:bs[f.id]==null?'':bs[f.id]});
    inp.oninput=()=>{bs[f.id]=inp.value;refresh();};row.appendChild(inp);wrap.appendChild(row);
  });
}
async function refresh(){
  try{
    const r=await fetch('/reconcile',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({portfolio:rows,balance_sheet:bs})});
    const j=await r.json();const rec=j.reconcile||{};const bk=(j.book_scaling||{}).book_scaling;
    let h='<b>Reconciliation</b>\\n';
    h+='  asset rows: '+rec.n_asset_rows+'   sum of rows: '+fmt(rec.sum_of_asset_rows)+'\\n';
    h+='  stated total: '+(rec.stated_total_backing_asset_mv==null?'(none)':fmt(rec.stated_total_backing_asset_mv));
    if(rec.reconciles===true)h+='   <span class="ok">reconciles</span>';
    else if(rec.reconciles===false)h+='   <span class="bad">MISMATCH (diff '+fmt(rec.difference)+')</span>';
    h+='\\n  illiquid share: '+(rec.illiquid_share==null?'n/a':(100*rec.illiquid_share).toFixed(2)+'%')+'\\n\\n';
    h+='<b>Disclosed book-scaling preview</b> <span class="warn">(approximation, not governed)</span>\\n';
    h+='  PAR rows: '+(j.book_scaling||{}).par_rows+'   GMMB rows disclosed: '+(j.book_scaling||{}).gmmb_rows_disclosed+'\\n';
    if(bk){h+='  policy count total: '+fmt(bk.policy_count_total)+'\\n  representative sum assured: '+fmt(bk.representative_sum_assured)+'\\n  linear scale factor: '+fmt(bk.linear_scale_factor);}
    document.getElementById('recon').innerHTML=h;
  }catch(e){document.getElementById('recon').innerHTML='<span class="bad">reconcile error</span> '+e;}
}
function fmt(x){if(x==null)return 'n/a';return (typeof x==='number')?x.toLocaleString(undefined,{maximumFractionDigits:4}):x;}
function payload(){return {portfolio:rows,balance_sheet:bs};}
async function post(path){
  const out=document.getElementById('out');out.textContent='Working...';
  try{
    const r=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload())});
    const j=await r.json();
    if(j.ok){out.innerHTML='<span class="ok">OK</span>\\n'+JSON.stringify(j,null,1);}
    else{out.innerHTML='<span class="bad">INVALID ('+(j.errors||[]).length+' issue(s))</span>\\n'+(j.errors||[]).join('\\n');}
  }catch(e){out.innerHTML='<span class="bad">runner error</span>\\n'+e;}
}
document.getElementById('btn-add').onclick=()=>{rows.push(blankRow());renderRows();refresh();};
document.getElementById('btn-add-asset').onclick=()=>{(bs.assets=bs.assets||[]).push({asset_class:'',market_value:'',illiquid:'no'});renderAssets();refresh();};
document.getElementById('btn-validate').onclick=()=>post('/validate_portfolio');
document.getElementById('btn-save').onclick=()=>post('/save_portfolio');
document.getElementById('file').onchange=async(ev)=>{
  const f=ev.target.files[0];if(!f)return;const text=await f.text();const out=document.getElementById('out');out.textContent='Ingesting '+f.name+'...';
  try{
    const r=await fetch('/ingest',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text:text,format:'auto'})});
    const j=await r.json();
    if(j.ok){rows=rows.concat(j.rows);renderRows();refresh();out.innerHTML='<span class="ok">Ingested '+j.rows.length+' row(s) from '+f.name+'</span>';}
    else{out.innerHTML='<span class="bad">ingest failed ('+(j.errors||[]).length+')</span>\\n'+(j.errors||[]).join('\\n');}
  }catch(e){out.innerHTML='<span class="bad">ingest error</span>\\n'+e;}
  ev.target.value='';
};
buildHead();renderRows();renderAssets();renderScalars();refresh();
</script>
</body></html>"""
    return (_tmpl.replace("__HEADLINE__", headline)
                 .replace("__FIELDS_JS__", fields_js)
                 .replace("__BS_SCALARS_JS__", bs_scalar_js)
                 .replace("__ROWS_JS__", rows_js)
                 .replace("__BS_JS__", bs_js))


# --------------------------------------------------------------------------
# (h) Task-3 acceptance gate (structural + LIVE repo cross-checks)
# --------------------------------------------------------------------------
def _live_external_ref_count(repo_root: str) -> int:
    pat = re.compile(r'(?:src|href)="(?:https?:)?//')
    total = 0
    for name in HTML_ARTIFACTS:
        with open(os.path.join(repo_root, name), encoding="utf-8") as fh:
            total += len(pat.findall(fh.read()))
    return total


def _source_has_forbidden_import(path: str) -> bool:
    if not os.path.exists(path):
        return True
    with open(path, encoding="utf-8") as fh:
        src = fh.read()
    for mod in FORBIDDEN_RUNTIME_IMPORTS:
        if re.search(r'^\s*(?:import|from)\s+%s\b' % re.escape(mod), src, re.MULTILINE):
            return True
    return False


def validate_task3_gate(repo_root: str = ".") -> Dict[str, Any]:
    """Task-3 gate: pre-registered acceptance checks, structural + LIVE."""
    checks: Dict[str, bool] = {}
    run_gui = os.path.join(repo_root, "scripts", "run_gui.py")
    loader = os.path.join(repo_root, "scripts", "load_user_inputs.py")
    this_mod = os.path.join(repo_root, "par_model_v2", "viewer", "igui_model_points.py")
    pg = os.path.join(repo_root, "par_model_v2", "projection", "portfolio_generator.py")

    # --- plumbing present ---
    checks["model_points_module_present"] = os.path.exists(this_mod)
    checks["run_gui_present"] = os.path.exists(run_gui)
    checks["loader_present"] = os.path.exists(loader)

    # --- stdlib-only: this layer pulls in NO forbidden third-party runtime dep ---
    checks["model_points_module_stdlib_only"] = not _source_has_forbidden_import(this_mod)

    # --- run_gui serves the model-points page + the new endpoints ---
    try:
        with open(run_gui, encoding="utf-8") as fh:
            gui_src = fh.read()
        checks["run_gui_serves_model_points"] = ("/model-points" in gui_src
                                                 and "render_model_points_html" in gui_src)
        checks["run_gui_has_portfolio_endpoints"] = all(
            p in gui_src for p in ("/validate_portfolio", "/save_portfolio",
                                   "/ingest", "/reconcile"))
        checks["run_gui_still_localhost"] = ("127.0.0.1" in gui_src and "0.0.0.0" not in gui_src)
    except OSError:
        checks["run_gui_serves_model_points"] = False
        checks["run_gui_has_portfolio_endpoints"] = False
        checks["run_gui_still_localhost"] = False

    # --- loader exposes the portfolio dict validator the GUI round-trips through ---
    try:
        with open(loader, encoding="utf-8") as fh:
            loader_src = fh.read()
        checks["loader_has_portfolio_validator"] = "def validate_portfolio_dict" in loader_src
        m = re.search(r'SCHEMA_VERSION\s*=\s*"([^"]+)"', loader_src)
        checks["schema_version_lockstep"] = bool(m) and m.group(1) == SCHEMA_VERSION
        checks["loader_product_enum_lockstep"] = (
            'ALLOWED_PRODUCT_TYPES = ("HKCD_PAR_2026", "HKRB_PAR_2026", '
            '"GMMB_EQ_2026", "WL_PAR_2026", "TERM_2026", "ANNUITY_2026")'
            in loader_src)
        checks["loader_gender_enum_lockstep"] = (
            'ALLOWED_GENDERS = ("M", "F")' in loader_src)
    except OSError:
        checks["loader_has_portfolio_validator"] = False
        checks["schema_version_lockstep"] = False
        checks["loader_product_enum_lockstep"] = False
        checks["loader_gender_enum_lockstep"] = False

    # --- enum lock-step with the portfolio generator's product line map ---
    try:
        with open(pg, encoding="utf-8") as fh:
            pg_src = fh.read()
        checks["pg_product_line_map_present"] = "USER_PRODUCT_LINE_MAP" in pg_src
    except OSError:
        checks["pg_product_line_map_present"] = False

    # --- defaults normalise clean + build a loader-valid fragment ---
    typed_rows, row_errs = normalize_model_points(default_model_points())
    typed_bs, bs_errs = normalize_balance_sheet(default_balance_sheet())
    checks["defaults_normalise_clean"] = (row_errs == [] and bs_errs == [])
    checks["defaults_three_rows"] = (len(typed_rows) == 3)
    frag = portfolio_to_model_inputs(typed_rows, typed_bs,
                                     generated_at="1970-01-01T00:00:00+00:00")
    checks["fragment_has_portfolio_and_bs"] = (
        isinstance(frag.get("portfolio"), list) and len(frag["portfolio"]) == 3
        and isinstance(frag.get("balance_sheet"), dict)
        and "backing_asset_mv" in frag["balance_sheet"])

    # --- the fragment passes the loader's own validator ---
    try:
        import sys as _sys
        sp = os.path.join(repo_root, "scripts")
        if sp not in _sys.path:
            _sys.path.insert(0, sp)
        import load_user_inputs as _lui  # noqa: E402
        checks["fragment_passes_loader_validator"] = (_lui.validate_portfolio_dict(frag) == [])
    except Exception:
        checks["fragment_passes_loader_validator"] = False

    # --- reconciliation: defaults reconcile, mismatch is caught ---
    rec = reconcile_balance_sheet(typed_bs)
    checks["defaults_reconcile"] = (rec.get("reconciles") is True)
    bad_bs = dict(typed_bs)
    bad_bs = json.loads(json.dumps(typed_bs))
    bad_bs["stated_total_backing_asset_mv"] = rec["sum_of_asset_rows"] + 1_000_000.0
    checks["mismatch_detected"] = (reconcile_balance_sheet(bad_bs).get("reconciles") is False)

    # --- book scaling disclosure: PAR-only, GMMB disclosed by count ---
    bk = book_scaling_disclosure(typed_rows)
    checks["book_scaling_par_only"] = (bk["par_rows"] == 2 and bk["gmmb_rows_disclosed"] == 1)
    checks["book_scaling_has_factor"] = (
        bk["book_scaling"] is not None and bk["book_scaling"]["linear_scale_factor"] is not None)

    # --- in-force ingest: CSV + JSON both map to canonical rows ---
    csv_text = ("Product,Age,Sex,Term,FaceValue,Premium,Count,Bonus\n"
                "HKCD_PAR_2026,45,M,20,100000,5000,1000,0\n"
                "HKRB_PAR_2026,40,F,25,250000,9000,500,1200\n")
    csv_rows, csv_errs = ingest_inforce(csv_text, "auto")
    checks["csv_ingest_two_rows"] = (csv_errs == [] and len(csv_rows) == 2
                                     and csv_rows[0]["product_type"] == "HKCD_PAR_2026"
                                     and csv_rows[0]["sum_assured"] == "100000")
    json_text = json.dumps([{"product_type": "GMMB_EQ_2026", "issue_age": 50,
                             "gender": "m", "term_years": 15, "sum_assured": 300000,
                             "annual_premium": 12000, "policy_count": 250,
                             "vested_bonus": 0}])
    json_rows, json_errs = ingest_inforce(json_text, "auto")
    checks["json_ingest_one_row"] = (json_errs == [] and len(json_rows) == 1
                                     and json_rows[0]["gender"] == "M"
                                     and json_rows[0]["product_type"] == "GMMB_EQ_2026")
    checks["empty_ingest_fails_loud"] = (ingest_inforce("", "auto")[1] != [])

    # --- the self-contained page: governed headline + zero external refs ---
    page = render_model_points_html()
    checks["page_carries_headline"] = GOVERNED_HEADLINE in page
    checks["page_has_endpoints"] = all(p in page for p in
                                       ("/validate_portfolio", "/save_portfolio",
                                        "/ingest", "/reconcile"))
    checks["page_zero_external_refs"] = (
        len(re.findall(r'(?:src|href)="(?:https?:)?//', page)) == 0)

    # --- RESULTS UI byte-unchanged + zero external refs across artifacts ---
    try:
        with open(os.path.join(repo_root, "ui_app.html"), "rb") as fh:
            checks["ui_app_byte_unchanged"] = (
                hashlib.sha256(fh.read()).hexdigest() == UI_APP_SHA256)
    except OSError:
        checks["ui_app_byte_unchanged"] = False
    try:
        checks["live_zero_external_refs"] = (_live_external_ref_count(repo_root) == 0)
    except OSError:
        checks["live_zero_external_refs"] = False

    # --- governance store readable + risk register frozen at 17 ---
    try:
        with open(os.path.join(repo_root, ".claude-dev", "GOVERNANCE_STORE.json"),
                  encoding="utf-8") as fh:
            gov = json.load(fh)
        checks["governance_risk_register_frozen"] = len(gov.get("risk_register", [])) == 17
        checks["governance_change_records_floor"] = len(gov.get("change_records", [])) >= 102
    except (OSError, json.JSONDecodeError):
        checks["governance_risk_register_frozen"] = False
        checks["governance_change_records_floor"] = False

    return {"ok": all(checks.values()), "n_checks": len(checks), "checks": checks}
