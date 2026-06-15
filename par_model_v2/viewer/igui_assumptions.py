"""Phase IGUI Task 4 - actuarial assumptions input core logic (OWNER-GATED).

Pure, **standard-library-only** assumptions layer for the owner-directed
Actuarial Input & Run GUI (Phase IGUI). This is the ``D3_assumptions`` domain of
the Task-1 coverage map and the third staged input domain after Task-2 run
controls and Task-3 model points. It surfaces the full set of valuation
assumptions a user would expect to enter and round-trips every payload through
the REAL loader-side validator (``scripts/load_user_inputs.validate_assumptions_dict``)
fail-loud before a run is ever permitted.

OWNER-GATED discipline (this is the binding constraint of Task 4): surfacing an
assumption input here NEVER changes a governed / frozen model parameter. The
copula degrees of freedom, the grouped-t block dfs and the dependence Sigma are
**read-only provenance echoes** - they are displayed (so the user sees the
governed basis) but can NEVER be set, and the validator REJECTS any payload that
tries to override them. The collected assumptions are written to
``model_inputs.json`` as an additive ``assumptions`` block; the stochastic
engine continues to run on its frozen, governed parameters bit-for-bit. The
zero-install RESULTS UI (``ui_app.html``) stays byte-unchanged.

Contents:
  * :data:`ASSUMPTION_FIELDS` - declarative spec of every editable assumption,
    grouped (mortality / lapse & surrender / expenses / premiums / discount /
    bonus & crediting / management action / reinsurance / risk);
  * :data:`GOVERNED_FROZEN` - the governed df echo (NEVER user-settable);
  * :func:`default_assumptions` - a clean, valid starting set so the page opens
    ready-to-validate;
  * :func:`normalize_assumptions` - a raw GUI payload (strings, as a form
    delivers) -> typed assumptions + per-field errors;
  * :func:`assumptions_to_model_inputs` - typed assumptions -> the
    ``model_inputs.json`` ``{assumptions}`` sub-schema the loader validator
    accepts, with the governed-frozen echo attached read-only;
  * :func:`render_assumptions_html` - a SELF-CONTAINED page (zero external
    references, same-origin POSTs only) grouped by assumption family, with the
    governed-frozen basis shown read-only;
  * :func:`validate_task4_gate` - a Task-4 acceptance gate (structural + LIVE
    repo cross-checks), parallel to the Task-2 / Task-3 gates.

Binding discipline (unchanged): NO model parameter changes; the input+run GUI
adds NO third-party runtime dependency (stdlib only); it binds 127.0.0.1 and
makes NO outbound network call; the Phase 30 stop-rule stands and the
MR-016/MR-017 owner decision is not pre-empted; the zero-install RESULTS UI
stays byte-unchanged. The governed headline SCR is carried bit-for-bit.
"""

from __future__ import annotations

import datetime as _dt
import html as _html
import json
import os
import re
from typing import Any, Dict, List, Tuple

DOC_ID = "PHASE_IGUI_TASK4_ASSUMPTIONS"
DOC_VERSION = "1.0.0"

#: Governed headline SCR (frozen single-df t), carried bit-for-bit wherever displayed.
GOVERNED_HEADLINE = "39,975.654628199336"

#: model_inputs.json schema version (kept in lock-step with
#: scripts/load_user_inputs.SCHEMA_VERSION; the Task-4 gate asserts equality).
SCHEMA_VERSION = "1.0.0"

#: Frozen sha256 of the zero-install RESULTS UI; the gate asserts the live file
#: is byte-identical so Task 4 provably leaves ui_app.html unchanged.
UI_APP_SHA256 = "6dca35b3520297263dd06086a1ced18cf831efb3fab6a6e8a9cde744500d7e65"

#: Governed / frozen dependence parameters - READ-ONLY provenance echo. These are
#: NEVER user-settable; the validator rejects any payload that tries to override
#: them (the owner-gating contract of Task 4). Values mirror the frozen single-df
#: t-copula df 2.9451 and the grouped-t block dfs.
GOVERNED_FROZEN: Dict[str, float] = {
    "copula_df_single_t": 2.9451,
    "grouped_t_df_nonfin": 37.866,
    "grouped_t_df_fin": 8.506,
}

#: Third-party imports the GUI layer must NEVER pull in (stdlib-only contract).
FORBIDDEN_RUNTIME_IMPORTS = (
    "flask", "django", "fastapi", "aiohttp", "tornado", "bottle", "cherrypy",
    "requests", "httpx", "urllib3", "numpy", "pandas", "scipy", "openpyxl",
)

HTML_ARTIFACTS = ["ui_app.html", "model_result_viewer.html", "combined_model_app.html"]

#: Choice enumerations (duplicated into the loader validator + guarded equal by the gate).
PREMIUM_FREQUENCIES = ("annual", "semiannual", "quarterly", "monthly", "single")
DISCOUNT_MODES = ("flat", "curve")
BONUS_STRATEGIES = ("asset_share", "smoothed_bonus", "contribution_method", "fixed")
REINSURANCE_TYPES = ("none", "quota_share", "surplus", "yrt")


# --------------------------------------------------------------------------
# (a) declarative assumption spec (Task-1 domain D3) -- grouped
# --------------------------------------------------------------------------
# Each field: id, group, label, kind (float|int|choice|bool), bounds, default, help.
# Bounds use lo/hi with lo_open/hi_open flags (mirrors loader 'bounded' semantics).
ASSUMPTION_FIELDS: List[Dict[str, Any]] = [
    # --- Mortality (base + improvement) ---
    {"id": "mortality.base_table", "group": "Mortality", "label": "Base mortality table",
     "kind": "text", "default": "HK_ASSURED_2021",
     "help": "Identifier of the base mortality table (educational placeholder)."},
    {"id": "mortality.base_multiplier", "group": "Mortality", "label": "Base table multiplier",
     "kind": "float", "lo": 0.0, "hi": 5.0, "lo_open": True, "hi_open": False, "default": 1.0,
     "help": "Multiplicative loading on the base table, in (0, 5]."},
    {"id": "mortality.improvement_rate", "group": "Mortality", "label": "Annual improvement rate",
     "kind": "float", "lo": 0.0, "hi": 0.1, "lo_open": False, "hi_open": False, "default": 0.01,
     "help": "Annual mortality improvement, in [0, 0.10]."},
    {"id": "mortality.improvement_floor", "group": "Mortality", "label": "Improvement floor",
     "kind": "float", "lo": 0.0, "hi": 1.0, "lo_open": False, "hi_open": False, "default": 0.0,
     "help": "Lower floor applied to improved rates, in [0, 1]."},

    # --- Lapse / surrender incl. dynamic policyholder behaviour ---
    {"id": "lapse.base_lapse_rate", "group": "Lapse & Surrender", "label": "Base annual lapse rate",
     "kind": "float", "lo": 0.0, "hi": 1.0, "lo_open": False, "hi_open": True, "default": 0.05,
     "help": "Base annual lapse rate, in [0, 1)."},
    {"id": "lapse.base_surrender_rate", "group": "Lapse & Surrender", "label": "Base annual surrender rate",
     "kind": "float", "lo": 0.0, "hi": 1.0, "lo_open": False, "hi_open": True, "default": 0.03,
     "help": "Base annual surrender rate, in [0, 1)."},
    {"id": "lapse.dynamic_lapse_beta", "group": "Lapse & Surrender", "label": "Dynamic-lapse sensitivity (beta)",
     "kind": "float", "lo": 0.0, "hi": 10.0, "lo_open": False, "hi_open": False, "default": 1.5,
     "help": "Policyholder-behaviour sensitivity of lapse to in-the-moneyness, in [0, 10]."},
    {"id": "lapse.dynamic_lapse_itm_threshold", "group": "Lapse & Surrender", "label": "Dynamic-lapse ITM threshold",
     "kind": "float", "lo": 0.0, "hi": 5.0, "lo_open": True, "hi_open": False, "default": 1.0,
     "help": "In-the-moneyness ratio above which dynamic behaviour activates, in (0, 5]."},

    # --- Expenses (per-policy / %-premium / inflation) ---
    {"id": "expenses.per_policy", "group": "Expenses", "label": "Per-policy expense (annual)",
     "kind": "float", "lo": 0.0, "hi": 1e9, "lo_open": False, "hi_open": False, "default": 50.0,
     "help": "Per-policy annual maintenance expense, >= 0."},
    {"id": "expenses.pct_premium", "group": "Expenses", "label": "Expense as % of premium",
     "kind": "float", "lo": 0.0, "hi": 1.0, "lo_open": False, "hi_open": False, "default": 0.05,
     "help": "Premium-related expense fraction, in [0, 1]."},
    {"id": "expenses.inflation_rate", "group": "Expenses", "label": "Expense inflation rate",
     "kind": "float", "lo": -0.1, "hi": 0.2, "lo_open": False, "hi_open": False, "default": 0.02,
     "help": "Annual expense inflation, in [-0.10, 0.20]."},

    # --- Premiums / contributions ---
    {"id": "premiums.frequency", "group": "Premiums", "label": "Premium frequency",
     "kind": "choice", "choices": list(PREMIUM_FREQUENCIES), "default": "annual",
     "help": "Premium payment frequency."},
    {"id": "premiums.indexation_rate", "group": "Premiums", "label": "Premium indexation rate",
     "kind": "float", "lo": -0.1, "hi": 0.5, "lo_open": False, "hi_open": False, "default": 0.0,
     "help": "Annual premium indexation, in [-0.10, 0.50]."},

    # --- Discount rate / yield curve ---
    {"id": "discount.mode", "group": "Discount / Yield", "label": "Discount mode",
     "kind": "choice", "choices": list(DISCOUNT_MODES), "default": "flat",
     "help": "'flat' uses the flat rate; 'curve' uses the tenor/rate yield curve."},
    {"id": "discount.flat_rate", "group": "Discount / Yield", "label": "Flat discount rate",
     "kind": "float", "lo": -0.1, "hi": 0.5, "lo_open": True, "hi_open": True, "default": 0.03,
     "help": "Flat annual discount rate, in (-0.10, 0.50). Used when mode = flat."},

    # --- Bonus / crediting & bonus-declaration strategy ---
    {"id": "bonus.declaration_strategy", "group": "Bonus & Crediting", "label": "Bonus declaration strategy",
     "kind": "choice", "choices": list(BONUS_STRATEGIES), "default": "asset_share",
     "help": "Approach used to declare reversionary/terminal bonus."},
    {"id": "bonus.reversionary_rate", "group": "Bonus & Crediting", "label": "Reversionary bonus rate",
     "kind": "float", "lo": 0.0, "hi": 0.5, "lo_open": False, "hi_open": False, "default": 0.02,
     "help": "Annual reversionary bonus rate, in [0, 0.50]."},
    {"id": "bonus.terminal_rate", "group": "Bonus & Crediting", "label": "Terminal bonus rate",
     "kind": "float", "lo": 0.0, "hi": 2.0, "lo_open": False, "hi_open": False, "default": 0.1,
     "help": "Terminal bonus rate at maturity, in [0, 2]."},
    {"id": "bonus.smoothing_factor", "group": "Bonus & Crediting", "label": "Smoothing factor",
     "kind": "float", "lo": 0.0, "hi": 1.0, "lo_open": False, "hi_open": False, "default": 0.3,
     "help": "Asset-share smoothing weight, in [0, 1]."},

    # --- Management-action rules (relief scalars + dynamic toggle) ---
    {"id": "management_action.relief_sigma", "group": "Management Action", "label": "Relief: sigma",
     "kind": "float", "lo": 0.0, "hi": 10.0, "lo_open": True, "hi_open": False, "default": 1.0,
     "help": "Management-action relief sigma, in (0, 10]. (Loader 'relief_sigma'.)"},
    {"id": "management_action.relief_alpha", "group": "Management Action", "label": "Relief: alpha",
     "kind": "float", "lo": 0.0, "hi": 1.0, "lo_open": True, "hi_open": False, "default": 0.5,
     "help": "Management-action relief alpha, in (0, 1]. (Loader 'relief_alpha'.)"},
    {"id": "management_action.dynamic_rule_enabled", "group": "Management Action", "label": "Dynamic action rule enabled",
     "kind": "bool", "default": True,
     "help": "Whether the dynamic management-action rule is active."},

    # --- Reinsurance ---
    {"id": "reinsurance.type", "group": "Reinsurance", "label": "Reinsurance type",
     "kind": "choice", "choices": list(REINSURANCE_TYPES), "default": "none",
     "help": "Reinsurance arrangement type."},
    {"id": "reinsurance.quota_share", "group": "Reinsurance", "label": "Quota share ceded",
     "kind": "float", "lo": 0.0, "hi": 1.0, "lo_open": False, "hi_open": False, "default": 0.0,
     "help": "Fraction of risk ceded, in [0, 1]."},
    {"id": "reinsurance.retention_limit", "group": "Reinsurance", "label": "Retention limit",
     "kind": "float", "lo": 0.0, "hi": 1e12, "lo_open": False, "hi_open": False, "default": 0.0,
     "help": "Per-life retention limit, >= 0 (0 = not applicable)."},

    # --- Risk / SCR-level assumptions (existing loader fields) ---
    {"id": "risk.confidence", "group": "Risk", "label": "Confidence level (SCR)",
     "kind": "float", "lo": 0.0, "hi": 1.0, "lo_open": True, "hi_open": True, "default": 0.995,
     "help": "SCR confidence level, in (0, 1). (Loader 'confidence'.)"},
    {"id": "risk.benefit_share", "group": "Risk", "label": "Benefit share (beta_fit)",
     "kind": "float", "lo": 0.0, "hi": 1.0, "lo_open": True, "hi_open": False, "default": 0.9,
     "help": "Policyholder benefit share, in (0, 1]. (Loader 'benefit_share'.)"},
]

#: Field ids in declared order.
ASSUMPTION_KEYS = tuple(f["id"] for f in ASSUMPTION_FIELDS)

#: Stable group order for rendering.
GROUP_ORDER = ("Mortality", "Lapse & Surrender", "Expenses", "Premiums",
               "Discount / Yield", "Bonus & Crediting", "Management Action",
               "Reinsurance", "Risk")

#: Default educational discount curve (used when discount.mode == 'curve').
DEFAULT_DISCOUNT_CURVE: List[Dict[str, float]] = [
    {"tenor": 1, "rate": 0.025}, {"tenor": 5, "rate": 0.030},
    {"tenor": 10, "rate": 0.033}, {"tenor": 20, "rate": 0.035},
    {"tenor": 30, "rate": 0.036},
]


# --------------------------------------------------------------------------
# (b) coercion helpers
# --------------------------------------------------------------------------
def _as_str(v: Any) -> str:
    return str(v).strip() if v is not None else ""


def _to_float(v: Any):
    s = _as_str(v).replace(",", "")
    if s == "":
        return None
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


def _to_bool(v: Any):
    if isinstance(v, bool):
        return v
    s = _as_str(v).lower()
    if s in ("true", "yes", "1", "on"):
        return True
    if s in ("false", "no", "0", "off", ""):
        return False
    return None


def _is_blank(v: Any) -> bool:
    return v is None or (isinstance(v, str) and not v.strip())


def _flat_get(payload: Dict[str, Any], dotted: str) -> Any:
    """Read a possibly-nested key, accepting BOTH a flat 'a.b' key and a nested
    {'a': {'b': ...}} payload (a form may deliver either)."""
    if not isinstance(payload, dict):
        return None
    if dotted in payload:
        return payload[dotted]
    cur: Any = payload
    for part in dotted.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return None
    return cur


def _nest(flat: Dict[str, Any]) -> Dict[str, Any]:
    """Turn {'a.b': 1} into {'a': {'b': 1}}."""
    out: Dict[str, Any] = {}
    for k, v in flat.items():
        parts = k.split(".")
        cur = out
        for p in parts[:-1]:
            cur = cur.setdefault(p, {})
        cur[parts[-1]] = v
    return out


def default_assumptions() -> Dict[str, Any]:
    """A clean, valid default assumption set, NESTED as the model_inputs block.

    These are EXAMPLE educational assumptions, not governed model parameters."""
    flat: Dict[str, Any] = {}
    for f in ASSUMPTION_FIELDS:
        flat[f["id"]] = f["default"]
    nested = _nest(flat)
    nested["discount"]["curve"] = [dict(p) for p in DEFAULT_DISCOUNT_CURVE]
    return nested


# --------------------------------------------------------------------------
# (c) normalisation: raw GUI payload -> typed assumptions + errors
# --------------------------------------------------------------------------
def normalize_assumptions(payload: Any) -> Tuple[Dict[str, Any], List[str]]:
    """Coerce a raw (string) GUI assumptions payload into a typed, NESTED dict.

    Returns ``(typed, errors)``. Type-coercion problems are reported here in the
    fail-loud ``field '<id>'`` format; deeper range checks are the loader's job
    (round-tripped via :func:`assumptions_to_model_inputs` then
    ``validate_assumptions_dict``). The governed-frozen echo is NOT taken from
    the payload - it is always attached from :data:`GOVERNED_FROZEN`.
    """
    errors: List[str] = []
    flat: Dict[str, Any] = {}
    if not isinstance(payload, dict):
        return {}, ["assumptions payload must be a JSON object"]
    for f in ASSUMPTION_FIELDS:
        fid = f["id"]
        v = _flat_get(payload, fid)
        kind = f["kind"]
        if kind == "float":
            fv = _to_float(v)
            if fv is None:
                errors.append("field '%s': must be a number, got %r" % (fid, v))
            else:
                flat[fid] = fv
        elif kind == "int":
            fv = _to_float(v)
            if fv is None or fv != int(fv):
                errors.append("field '%s': must be an integer, got %r" % (fid, v))
            else:
                flat[fid] = int(fv)
        elif kind == "bool":
            bv = _to_bool(v)
            if bv is None:
                errors.append("field '%s': must be true/false, got %r" % (fid, v))
            else:
                flat[fid] = bv
        elif kind == "choice":
            sv = _as_str(v)
            if sv not in f["choices"]:
                errors.append("field '%s': must be one of %s, got %r"
                              % (fid, list(f["choices"]), v))
            else:
                flat[fid] = sv
        else:  # text
            flat[fid] = _as_str(v)
    typed = _nest(flat)

    # discount curve (only meaningful when mode == curve; always normalised if present)
    curve_in = _flat_get(payload, "discount.curve")
    if curve_in is None:
        curve_in = DEFAULT_DISCOUNT_CURVE
    norm_curve, curve_errs = _normalize_curve(curve_in)
    errors.extend(curve_errs)
    typed.setdefault("discount", {})["curve"] = norm_curve
    return typed, errors


def _normalize_curve(curve: Any) -> Tuple[List[Dict[str, float]], List[str]]:
    errors: List[str] = []
    out: List[Dict[str, float]] = []
    if not isinstance(curve, list):
        return [], ["field 'discount.curve': must be a JSON array of {tenor, rate}"]
    for i, pt in enumerate(curve, 1):
        if not isinstance(pt, dict):
            errors.append("discount.curve[%d]: must be an object {tenor, rate}" % i)
            continue
        if all(_is_blank(pt.get(k)) for k in ("tenor", "rate")):
            continue
        t = _to_float(pt.get("tenor"))
        r = _to_float(pt.get("rate"))
        if t is None or t <= 0:
            errors.append("discount.curve[%d].tenor: must be a positive number, got %r" % (i, pt.get("tenor")))
            continue
        if r is None:
            errors.append("discount.curve[%d].rate: must be a number, got %r" % (i, pt.get("rate")))
            continue
        out.append({"tenor": t, "rate": r})
    return out, errors


# --------------------------------------------------------------------------
# (d) typed assumptions -> model_inputs.json {assumptions} sub-schema
# --------------------------------------------------------------------------
def assumptions_to_model_inputs(typed: Dict[str, Any], *, generated_at: str = None) -> Dict[str, Any]:
    """Build the ``model_inputs.json`` ``{assumptions}`` sub-schema (loader
    -compatible) from typed assumptions. The governed-frozen df echo is attached
    READ-ONLY from :data:`GOVERNED_FROZEN` (never from the user payload), so a
    round-trip can never smuggle a governed-parameter override past the
    loader-side validator."""
    assumptions = json.loads(json.dumps(typed))  # deep copy
    assumptions["governed_frozen_readback"] = dict(GOVERNED_FROZEN)
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at or _dt.datetime.now(_dt.timezone.utc).isoformat(),
        "source": "igui_run_gui (Phase IGUI Task 4 assumptions, owner-gated)",
        "assumptions": assumptions,
    }


# --------------------------------------------------------------------------
# (e) self-contained page
# --------------------------------------------------------------------------
def _js_const(name: str, obj: Any) -> str:
    return "const %s=%s;" % (name, json.dumps(obj))


def render_assumptions_html(values: Dict[str, Any] = None) -> str:
    """Render the SELF-CONTAINED assumptions page. No external src/href; the only
    network is same-origin POSTs to the local runner. Inputs are grouped by
    assumption family; the governed-frozen dependence basis is shown READ-ONLY."""
    vals = values if values is not None else default_assumptions()
    fields_js = _js_const("FIELDS", [
        {"id": f["id"], "group": f["group"], "label": f["label"], "kind": f["kind"],
         "choices": f.get("choices", []), "help": f.get("help", "")}
        for f in ASSUMPTION_FIELDS])
    groups_js = _js_const("GROUPS", list(GROUP_ORDER))
    vals_js = _js_const("INIT_VALS", vals)
    frozen_js = _js_const("FROZEN", GOVERNED_FROZEN)
    headline = _html.escape(GOVERNED_HEADLINE)
    _tmpl = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Actuarial Input &amp; Run GUI - Assumptions (Phase IGUI Task 4)</title>
<style>
 body{font-family:system-ui,Arial,sans-serif;margin:0;background:#0f1722;color:#e7eef7}
 header{padding:16px 22px;background:#16263a;border-bottom:1px solid #24405e}
 h1{font-size:18px;margin:0}
 h2{font-size:15px;color:#8fb6e6;margin:0}
 main{max-width:1040px;margin:0 auto;padding:22px}
 fieldset{border:1px solid #24405e;border-radius:8px;margin:0 0 14px;padding:12px 14px}
 legend{padding:0 8px;color:#8fb6e6;font-weight:600}
 .frow{display:grid;grid-template-columns:320px 200px;gap:10px;align-items:center;margin:6px 0}
 .help{color:#7f97b3;font-size:11.5px;grid-column:1 / span 2;margin:-2px 0 4px}
 input,select{background:#0b1320;color:#e7eef7;border:1px solid #2c4a6b;border-radius:5px;padding:5px 7px;width:100%;box-sizing:border-box}
 input[readonly]{background:#1a2334;color:#9fb3cc;border-style:dashed}
 .actions{display:flex;gap:12px;margin:14px 0;flex-wrap:wrap}
 button{background:#2563eb;color:#fff;border:0;border-radius:6px;padding:9px 14px;font-size:14px;cursor:pointer}
 button.secondary{background:#33445c}
 #out{white-space:pre-wrap;background:#0b1320;border:1px solid #24405e;border-radius:8px;padding:12px;margin-top:14px;font-family:ui-monospace,Menlo,monospace;font-size:12.5px}
 .ok{color:#36d399}.bad{color:#f87272}.warn{color:#fbbd23}
 footer{color:#6c8099;font-size:12px;padding:12px 22px;border-top:1px solid #24405e}
 .frozen{background:#13202f}
</style></head>
<body>
<header><h1>Actuarial Input &amp; Run GUI &mdash; Assumptions</h1>
<h2>Owner-gated: governed/frozen dependence parameters are read-only echoes.</h2></header>
<main>
 <div id="groups"></div>

 <fieldset class="frozen"><legend>Governed / frozen dependence basis (READ-ONLY)</legend>
  <div class="help">These are the governed model parameters. They are shown for provenance only and can never be set here; the loader rejects any override.</div>
  <div id="frozen"></div>
 </fieldset>

 <div class="actions">
  <button type="button" id="btn-validate" class="secondary">Validate</button>
  <button type="button" id="btn-save">Validate &amp; write model_inputs.json</button>
 </div>
 <div id="out">Ready. Assumptions validate fail-loud through the real loader; the governed basis is never changed.</div>
</main>
<footer>Phase IGUI Task 4 &mdash; assumptions (owner-gated), stdlib local runner (127.0.0.1, offline). Governed headline SCR carried bit-for-bit: __HEADLINE__. The zero-install RESULTS UI (ui_app.html) is unchanged.</footer>
<script>
__FIELDS_JS__
__GROUPS_JS__
__VALS_JS__
__FROZEN_JS__
let vals = JSON.parse(JSON.stringify(INIT_VALS));
function getv(id){let cur=vals;for(const p of id.split('.')){if(cur==null)return '';cur=cur[p];}return cur==null?'':cur;}
function setv(id,v){let cur=vals;const ps=id.split('.');for(let i=0;i<ps.length-1;i++){if(cur[ps[i]]==null)cur[ps[i]]={};cur=cur[ps[i]];}cur[ps[ps.length-1]]=v;}
function el(t,a,c){const e=document.createElement(t);if(a)for(const k in a)e.setAttribute(k,a[k]);if(c!=null)e.textContent=c;return e;}
function inputFor(f){
  let inp;const val=getv(f.id);
  if(f.kind==='choice'){inp=el('select');f.choices.forEach(c=>{const o=el('option',{value:c},c);if(c===val)o.selected=true;inp.appendChild(o);});inp.onchange=()=>setv(f.id,inp.value);}
  else if(f.kind==='bool'){inp=el('select');['true','false'].forEach(c=>{const o=el('option',{value:c},c);if(String(val)===c)o.selected=true;inp.appendChild(o);});inp.onchange=()=>setv(f.id,inp.value==='true');}
  else{inp=el('input',{type:(f.kind==='float'||f.kind==='int')?'number':'text',value:val==null?'':val});inp.oninput=()=>setv(f.id,inp.value);}
  return inp;
}
function renderGroups(){
  const wrap=document.getElementById('groups');wrap.innerHTML='';
  GROUPS.forEach(g=>{
    const fs=el('fieldset');fs.appendChild(el('legend',null,g));
    FIELDS.filter(f=>f.group===g).forEach(f=>{
      const row=el('div',{class:'frow'});row.appendChild(el('label',null,f.label));row.appendChild(inputFor(f));
      if(f.help)row.appendChild(el('div',{class:'help'},f.help));
      fs.appendChild(row);
    });
    wrap.appendChild(fs);
  });
}
function renderFrozen(){
  const wrap=document.getElementById('frozen');wrap.innerHTML='';
  Object.keys(FROZEN).forEach(k=>{
    const row=el('div',{class:'frow'});row.appendChild(el('label',null,k));
    const inp=el('input',{type:'text',value:FROZEN[k],readonly:'readonly'});row.appendChild(inp);wrap.appendChild(row);
  });
}
async function post(path){
  const out=document.getElementById('out');out.textContent='Working...';
  try{
    const r=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({assumptions:vals})});
    const j=await r.json();
    if(j.ok){out.innerHTML='<span class="ok">OK</span>\\n'+JSON.stringify(j,null,1);}
    else{out.innerHTML='<span class="bad">INVALID ('+(j.errors||[]).length+' issue(s))</span>\\n'+(j.errors||[]).join('\\n');}
  }catch(e){out.innerHTML='<span class="bad">runner error</span>\\n'+e;}
}
document.getElementById('btn-validate').onclick=()=>post('/validate_assumptions');
document.getElementById('btn-save').onclick=()=>post('/save_assumptions');
renderGroups();renderFrozen();
</script>
</body></html>"""
    return (_tmpl.replace("__HEADLINE__", headline)
                 .replace("__FIELDS_JS__", fields_js)
                 .replace("__GROUPS_JS__", groups_js)
                 .replace("__VALS_JS__", vals_js)
                 .replace("__FROZEN_JS__", frozen_js))


# --------------------------------------------------------------------------
# (f) Task-4 acceptance gate (structural + LIVE repo cross-checks)
# --------------------------------------------------------------------------
def _source_has_forbidden_import(path: str) -> bool:
    if not os.path.exists(path):
        return True
    with open(path, encoding="utf-8") as fh:
        src = fh.read()
    for mod in FORBIDDEN_RUNTIME_IMPORTS:
        if re.search(r'^\s*(?:import|from)\s+%s\b' % re.escape(mod), src, re.MULTILINE):
            return True
    return False


def validate_task4_gate(repo_root: str = ".") -> Dict[str, Any]:
    """Task-4 gate: pre-registered acceptance checks, structural + LIVE."""
    checks: Dict[str, bool] = {}
    run_gui = os.path.join(repo_root, "scripts", "run_gui.py")
    loader = os.path.join(repo_root, "scripts", "load_user_inputs.py")
    this_mod = os.path.join(repo_root, "par_model_v2", "viewer", "igui_assumptions.py")

    # --- plumbing present ---
    checks["assumptions_module_present"] = os.path.exists(this_mod)
    checks["run_gui_present"] = os.path.exists(run_gui)
    checks["loader_present"] = os.path.exists(loader)

    # --- stdlib-only: this layer pulls in NO forbidden third-party runtime dep ---
    checks["assumptions_module_stdlib_only"] = not _source_has_forbidden_import(this_mod)

    # --- run_gui serves the assumptions page + the new endpoints ---
    try:
        with open(run_gui, encoding="utf-8") as fh:
            gui_src = fh.read()
        checks["run_gui_serves_assumptions"] = ("/assumptions" in gui_src
                                                and "render_assumptions_html" in gui_src)
        checks["run_gui_has_assumption_endpoints"] = all(
            p in gui_src for p in ("/validate_assumptions", "/save_assumptions"))
        checks["run_gui_still_localhost"] = ("127.0.0.1" in gui_src and "0.0.0.0" not in gui_src)
        # the prior task pages/endpoints survive unchanged
        checks["run_gui_prior_pages_intact"] = all(
            p in gui_src for p in ("/model-points", "render_model_points_html",
                                   "/validate_portfolio", "render_form_html"))
    except OSError:
        checks["run_gui_serves_assumptions"] = False
        checks["run_gui_has_assumption_endpoints"] = False
        checks["run_gui_still_localhost"] = False
        checks["run_gui_prior_pages_intact"] = False

    # --- loader exposes the assumptions dict validator the GUI round-trips through ---
    try:
        with open(loader, encoding="utf-8") as fh:
            loader_src = fh.read()
        checks["loader_has_assumptions_validator"] = "def validate_assumptions_dict" in loader_src
        m = re.search(r'SCHEMA_VERSION\s*=\s*"([^"]+)"', loader_src)
        checks["schema_version_lockstep"] = bool(m) and m.group(1) == SCHEMA_VERSION
    except OSError:
        checks["loader_has_assumptions_validator"] = False
        checks["schema_version_lockstep"] = False

    # --- defaults normalise clean + build a loader-valid fragment ---
    typed, errs = normalize_assumptions(default_assumptions())
    checks["defaults_normalise_clean"] = (errs == [])
    frag = assumptions_to_model_inputs(typed, generated_at="1970-01-01T00:00:00+00:00")
    checks["fragment_has_assumptions"] = (
        isinstance(frag.get("assumptions"), dict)
        and "mortality" in frag["assumptions"]
        and "governed_frozen_readback" in frag["assumptions"])

    # --- the fragment passes the loader's own validator ---
    loader_errs = ["<not-run>"]
    try:
        import sys as _sys
        sp = os.path.join(repo_root, "scripts")
        if sp not in _sys.path:
            _sys.path.insert(0, sp)
        import load_user_inputs as _lui  # noqa: E402
        loader_errs = _lui.validate_assumptions_dict(frag)
        checks["fragment_passes_loader_validator"] = (loader_errs == [])
    except Exception:
        checks["fragment_passes_loader_validator"] = False

    # --- OWNER-GATING: governed-frozen echo is always the governed values ---
    checks["frozen_echo_is_governed"] = (
        frag["assumptions"]["governed_frozen_readback"] == GOVERNED_FROZEN)

    # --- OWNER-GATING: a payload that tries to OVERRIDE a frozen df is REJECTED ---
    try:
        tampered = json.loads(json.dumps(frag))
        tampered["assumptions"]["governed_frozen_readback"]["copula_df_single_t"] = 9.999
        rej = _lui.validate_assumptions_dict(tampered)
        checks["frozen_override_rejected"] = (len(rej) > 0)
    except Exception:
        checks["frozen_override_rejected"] = False

    # --- range validation: an out-of-bounds assumption is caught ---
    try:
        bad = json.loads(json.dumps(default_assumptions()))
        bad["mortality"]["base_multiplier"] = 99.0  # > 5
        bt, _ = normalize_assumptions(bad)
        bfrag = assumptions_to_model_inputs(bt)
        checks["out_of_bounds_caught"] = (len(_lui.validate_assumptions_dict(bfrag)) > 0)
    except Exception:
        checks["out_of_bounds_caught"] = False

    # --- choice validation: an unknown enum is rejected at normalisation ---
    bad2 = json.loads(json.dumps(default_assumptions()))
    bad2["reinsurance"]["type"] = "not_a_type"
    _, e2 = normalize_assumptions(bad2)
    checks["bad_choice_rejected"] = (len(e2) > 0)

    # --- discount curve normalises + rejects a non-positive tenor ---
    _, ce = _normalize_curve([{"tenor": -1, "rate": 0.03}])
    checks["bad_curve_tenor_rejected"] = (len(ce) > 0)
    okc, oce = _normalize_curve(DEFAULT_DISCOUNT_CURVE)
    checks["default_curve_ok"] = (oce == [] and len(okc) == 5)

    # --- self-contained page: zero external refs; carries headline; shows frozen ---
    page = render_assumptions_html()
    checks["page_self_contained"] = ('src="http' not in page and 'href="http' not in page
                                     and "//cdn" not in page)
    checks["page_carries_headline"] = (GOVERNED_HEADLINE in page)
    checks["page_shows_frozen_readonly"] = ("readonly" in page and "copula_df_single_t" in page)
    checks["page_groups_present"] = all(g in page for g in GROUP_ORDER)

    # --- RESULTS UI byte-unchanged (frozen sha256) ---
    try:
        import hashlib
        with open(os.path.join(repo_root, "ui_app.html"), "rb") as fh:
            checks["ui_app_byte_unchanged"] = (
                hashlib.sha256(fh.read()).hexdigest() == UI_APP_SHA256)
    except OSError:
        checks["ui_app_byte_unchanged"] = False

    # --- no new external references in the three frozen HTML artifacts ---
    try:
        pat = re.compile(r'(?:src|href)="(?:https?:)?//')
        total = 0
        for name in HTML_ARTIFACTS:
            with open(os.path.join(repo_root, name), encoding="utf-8") as fh:
                total += len(pat.findall(fh.read()))
        checks["no_external_refs_in_results_ui"] = (total == 0)
    except OSError:
        checks["no_external_refs_in_results_ui"] = False

    n_pass = sum(1 for v in checks.values() if v)
    return {"ok": all(checks.values()), "n_checks": len(checks),
            "n_pass": n_pass, "checks": checks,
            "loader_validation_of_defaults": loader_errs}
