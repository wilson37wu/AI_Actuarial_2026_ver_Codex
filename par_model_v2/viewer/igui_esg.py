"""Phase IGUI Task 5 - economic-scenario / ESG input domain (STOP-RULE-BOUNDED, owner-gated).

Pure, **standard-library-only** ESG / calibration layer for the owner-directed
Actuarial Input & Run GUI (Phase IGUI). This is the ``D4_esg_economic`` domain of
the Task-1 coverage map and the fourth staged input domain after Task-2 run
controls, Task-3 model points and Task-4 assumptions. It surfaces the economic
scenario generator's calibration so a user can SEE the governed basis and record
the market-data / calibration-target PROVENANCE around it, while never being able
to change the frozen stochastic engine.

STOP-RULE discipline (the binding constraint of Task 5): the Phase 30 dependence
stop-rule stands - **NO new copula-structure candidates** - and the pending
MR-016/MR-017 owner decision is **not pre-empted**. Therefore:

  * the governed ESG calibration (G2++/HW short-rate, equity GBM, credit-spread
    and liquidity-premium mean-reverting processes, and the FROZEN dependence
    structure: single-df t-copula df 2.9451 + grouped-t block dfs 37.866 / 8.506)
    is a **READ-ONLY provenance echo** - displayed for transparency, NEVER
    settable; the loader REJECTS any payload that tries to override it;
  * the copula STRUCTURE itself is pinned to ``single_t_grouped_FROZEN`` - the
    loader REJECTS any payload that names a different structure (the stop-rule
    guard), so the GUI can never introduce a new dependence-structure candidate;
  * the only user-SETTABLE ESG inputs are **bounded, owner-gated, non-structural
    PROVENANCE/metadata**: market-data valuation date & source, the
    scenario-set label, and the calibration TARGETS (e.g. the market 10y rate /
    equity vol the governed calibration was aimed at). These are additive
    documentation written to ``model_inputs.json``; they do NOT feed the engine,
    which keeps running on its frozen governed parameters bit-for-bit.

The zero-install RESULTS UI (``ui_app.html``) stays byte-unchanged.

Contents:
  * :data:`ESG_FIELDS` - declarative spec of every SETTABLE provenance field;
  * :data:`GOVERNED_ESG_FROZEN` - the governed calibration echo (NEVER settable);
  * :data:`FROZEN_COPULA_STRUCTURE` - the pinned dependence structure label;
  * :func:`default_esg` - a clean, valid starting set so the page opens ready;
  * :func:`normalize_esg` - raw GUI payload -> typed provenance + per-field errors;
  * :func:`esg_to_model_inputs` - typed provenance -> the ``model_inputs.json``
    ``{esg}`` sub-schema, with the governed-frozen echo + structure pin attached
    read-only;
  * :func:`render_esg_html` - a SELF-CONTAINED page (zero external references,
    same-origin POSTs only) with the governed basis shown read-only;
  * :func:`validate_task5_gate` - the Task-5 acceptance gate (structural + LIVE
    repo cross-checks), parallel to the Task-2 / Task-3 / Task-4 gates.

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

DOC_ID = "PHASE_IGUI_TASK5_ESG"
DOC_VERSION = "1.0.0"

#: Governed headline SCR (frozen single-df t), carried bit-for-bit wherever displayed.
GOVERNED_HEADLINE = "39,975.654628199336"

#: model_inputs.json schema version (kept in lock-step with
#: scripts/load_user_inputs.SCHEMA_VERSION; the Task-5 gate asserts equality).
SCHEMA_VERSION = "1.0.0"

#: Frozen sha256 of the zero-install RESULTS UI; the gate asserts the live file
#: is byte-identical so Task 5 provably leaves ui_app.html unchanged.
UI_APP_SHA256 = "6dca35b3520297263dd06086a1ced18cf831efb3fab6a6e8a9cde744500d7e65"

#: The pinned, FROZEN dependence structure (Phase 30 stop-rule). Any other value
#: in a payload is REJECTED by the loader - the GUI can never name a new
#: copula-structure candidate.
FROZEN_COPULA_STRUCTURE = "single_t_grouped_FROZEN"

#: Governed / frozen ESG calibration - READ-ONLY provenance echo. These mirror the
#: governed marginal-process and dependence parameters and are NEVER user-settable;
#: the validator rejects any payload that tries to override them. Values are the
#: governed educational calibration (par_model_v2/stochastic/esg_process.py and the
#: frozen single-df t-copula df 2.9451 / grouped-t block dfs).
GOVERNED_ESG_FROZEN: Dict[str, Any] = {
    "rate_model": "G2++ two-factor / HW one-factor (educational governed)",
    "rate.mean_reversion_x": 0.10,
    "rate.mean_reversion_y": 0.35,
    "rate.vol_x": 0.010,
    "rate.vol_y": 0.006,
    "rate.long_run_rate_p": 0.025,
    "equity.equity_vol": 0.22,
    "equity.dividend_yield": 0.025,
    "equity.equity_risk_premium": 0.045,
    "equity.rate_equity_correlation": -0.15,
    "credit.mean_reversion_speed": 0.30,
    "credit.long_run_spread_p": 0.015,
    "liquidity.mean_reversion_speed": 0.60,
    "liquidity.long_run_premium_p": 0.006,
    "dependence.copula_structure": FROZEN_COPULA_STRUCTURE,
    "dependence.copula_df_single_t": 2.9451,
    "dependence.grouped_t_df_nonfin": 37.866,
    "dependence.grouped_t_df_fin": 8.506,
}

#: Third-party imports the GUI layer must NEVER pull in (stdlib-only contract).
FORBIDDEN_RUNTIME_IMPORTS = (
    "flask", "django", "fastapi", "aiohttp", "tornado", "bottle", "cherrypy",
    "requests", "httpx", "urllib3", "numpy", "pandas", "scipy", "openpyxl",
)

HTML_ARTIFACTS = ["ui_app.html", "model_result_viewer.html", "combined_model_app.html"]


# --------------------------------------------------------------------------
# (a) declarative SETTABLE provenance spec (Task-1 domain D4) -- bounded, owner-gated
# --------------------------------------------------------------------------
# Only PROVENANCE / calibration-target metadata is settable. None of these feed the
# frozen engine; they document the market data + targets the governed calibration was
# aimed at. Each field: id, group, label, kind (float|int|choice|bool|text), bounds, default.
ESG_FIELDS: List[Dict[str, Any]] = [
    # --- Market data provenance ---
    {"id": "market_data.valuation_date", "group": "Market Data", "label": "Market-data valuation date",
     "kind": "date", "default": "2026-05-31",
     "help": "ISO date (YYYY-MM-DD) of the market data the governed calibration is anchored to (provenance only)."},
    {"id": "market_data.curve_source", "group": "Market Data", "label": "Yield-curve source",
     "kind": "text", "default": "HKMA EFBN / govt curve (educational)",
     "help": "Free-text source of the risk-free curve used as a calibration target (provenance only)."},
    {"id": "market_data.equity_index", "group": "Market Data", "label": "Equity index reference",
     "kind": "text", "default": "HSI total-return (educational)",
     "help": "Reference equity index for the equity-vol calibration target (provenance only)."},

    # --- Scenario set provenance ---
    {"id": "scenario.set_label", "group": "Scenario Set", "label": "Scenario-set label",
     "kind": "text", "default": "governed-base-2026",
     "help": "A label recorded with the run for traceability (provenance only)."},
    {"id": "scenario.documented_paths", "group": "Scenario Set", "label": "Documented scenario count",
     "kind": "int", "lo": 1, "hi": 1000000, "lo_open": False, "hi_open": False, "default": 20000,
     "help": "The scenario count the calibration provenance documents, in [1, 1,000,000]. "
             "Provenance only - the engine uses its governed outer/inner split."},

    # --- Calibration targets (market figures the governed calibration was aimed at) ---
    {"id": "calibration.target_10y_rate", "group": "Calibration Targets", "label": "Target 10y risk-free rate",
     "kind": "float", "lo": -0.1, "hi": 0.5, "lo_open": True, "hi_open": True, "default": 0.033,
     "help": "Market 10y rate the governed rate calibration targets, in (-0.10, 0.50). Provenance only."},
    {"id": "calibration.target_equity_vol", "group": "Calibration Targets", "label": "Target equity volatility",
     "kind": "float", "lo": 0.0, "hi": 2.0, "lo_open": True, "hi_open": False, "default": 0.22,
     "help": "Market equity vol the governed equity calibration targets, in (0, 2]. Provenance only."},
    {"id": "calibration.target_credit_spread", "group": "Calibration Targets", "label": "Target credit spread",
     "kind": "float", "lo": 0.0, "hi": 1.0, "lo_open": False, "hi_open": False, "default": 0.015,
     "help": "Market credit spread the governed credit calibration targets, in [0, 1]. Provenance only."},
    {"id": "calibration.basis_note", "group": "Calibration Targets", "label": "Calibration basis note",
     "kind": "text", "default": "Governed educational calibration; not a credentialled market-consistent basis.",
     "help": "Free-text note on the calibration basis (provenance only)."},
]

#: Field ids in declared order.
ESG_KEYS = tuple(f["id"] for f in ESG_FIELDS)

#: Stable group order for rendering.
GROUP_ORDER = ("Market Data", "Scenario Set", "Calibration Targets")


# --------------------------------------------------------------------------
# (b) coercion helpers
# --------------------------------------------------------------------------
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


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


def default_esg() -> Dict[str, Any]:
    """A clean, valid default ESG-provenance set, NESTED as the model_inputs block.

    These are EXAMPLE educational provenance values, not governed model parameters."""
    flat: Dict[str, Any] = {}
    for f in ESG_FIELDS:
        flat[f["id"]] = f["default"]
    return _nest(flat)


# --------------------------------------------------------------------------
# (c) normalisation: raw GUI payload -> typed provenance + errors
# --------------------------------------------------------------------------
def normalize_esg(payload: Any) -> Tuple[Dict[str, Any], List[str]]:
    """Coerce a raw (string) GUI ESG payload into a typed, NESTED dict.

    Returns ``(typed, errors)``. Type-coercion problems are reported here in the
    fail-loud ``field '<id>'`` format; deeper range / stop-rule checks are the
    loader's job (round-tripped via :func:`esg_to_model_inputs` then
    ``validate_esg_dict``). The governed-frozen echo + structure pin are NOT taken
    from the payload - they are always attached from :data:`GOVERNED_ESG_FROZEN`.
    """
    errors: List[str] = []
    flat: Dict[str, Any] = {}
    if not isinstance(payload, dict):
        return {}, ["esg payload must be a JSON object"]
    for f in ESG_FIELDS:
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
        elif kind == "date":
            sv = _as_str(v)
            if not _DATE_RE.match(sv):
                errors.append("field '%s': must be an ISO date YYYY-MM-DD, got %r" % (fid, v))
            else:
                flat[fid] = sv
        else:  # text
            flat[fid] = _as_str(v)
    typed = _nest(flat)
    return typed, errors


# --------------------------------------------------------------------------
# (d) typed provenance -> model_inputs.json {esg} sub-schema
# --------------------------------------------------------------------------
def esg_to_model_inputs(typed: Dict[str, Any], *, generated_at: str = None) -> Dict[str, Any]:
    """Build the ``model_inputs.json`` ``{esg}`` sub-schema (loader-compatible) from
    typed provenance. The governed-frozen ESG echo (incl. the pinned copula
    structure) is attached READ-ONLY from :data:`GOVERNED_ESG_FROZEN` (never from
    the user payload), so a round-trip can never smuggle a governed-parameter
    override or a new copula-structure candidate past the loader-side validator."""
    esg = json.loads(json.dumps(typed))  # deep copy
    esg["governed_esg_readback"] = dict(GOVERNED_ESG_FROZEN)
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at or _dt.datetime.now(_dt.timezone.utc).isoformat(),
        "source": "igui_run_gui (Phase IGUI Task 5 ESG, stop-rule-bounded, owner-gated)",
        "esg": esg,
    }


# --------------------------------------------------------------------------
# (e) self-contained page
# --------------------------------------------------------------------------
def _js_const(name: str, obj: Any) -> str:
    return "const %s=%s;" % (name, json.dumps(obj))


def render_esg_html(values: Dict[str, Any] = None) -> str:
    """Render the SELF-CONTAINED ESG page. No external src/href; the only network
    is same-origin POSTs to the local runner. Settable inputs are grouped; the
    governed-frozen ESG calibration + pinned copula structure are shown READ-ONLY."""
    vals = values if values is not None else default_esg()
    fields_js = _js_const("FIELDS", [
        {"id": f["id"], "group": f["group"], "label": f["label"], "kind": f["kind"],
         "choices": f.get("choices", []), "help": f.get("help", "")}
        for f in ESG_FIELDS])
    groups_js = _js_const("GROUPS", list(GROUP_ORDER))
    vals_js = _js_const("INIT_VALS", vals)
    frozen_js = _js_const("FROZEN", GOVERNED_ESG_FROZEN)
    headline = _html.escape(GOVERNED_HEADLINE)
    _tmpl = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Actuarial Input &amp; Run GUI - Economic Scenarios / ESG (Phase IGUI Task 5)</title>
<style>
 body{font-family:system-ui,Arial,sans-serif;margin:0;background:#0f1722;color:#e7eef7}
 header{padding:16px 22px;background:#16263a;border-bottom:1px solid #24405e}
 h1{font-size:18px;margin:0}
 h2{font-size:15px;color:#8fb6e6;margin:0}
 main{max-width:1040px;margin:0 auto;padding:22px}
 fieldset{border:1px solid #24405e;border-radius:8px;margin:0 0 14px;padding:12px 14px}
 legend{padding:0 8px;color:#8fb6e6;font-weight:600}
 .frow{display:grid;grid-template-columns:320px 240px;gap:10px;align-items:center;margin:6px 0}
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
 .stop{color:#fbbd23;font-size:12px;margin:4px 0 10px}
</style></head>
<body>
<header><h1>Actuarial Input &amp; Run GUI &mdash; Economic Scenarios / ESG</h1>
<h2>Stop-rule-bounded &amp; owner-gated: the governed ESG calibration is a read-only echo.</h2></header>
<main>
 <div class="stop">Phase 30 stop-rule: NO new copula-structure candidates. The dependence structure is pinned to <b>__STRUCT__</b>; the loader rejects any other value. MR-016/MR-017 remains with the owner.</div>
 <div id="groups"></div>

 <fieldset class="frozen"><legend>Governed / frozen ESG calibration (READ-ONLY)</legend>
  <div class="help">These are the governed economic-scenario parameters and the FROZEN dependence structure. Shown for provenance only; they can never be set here and the loader rejects any override.</div>
  <div id="frozen"></div>
 </fieldset>

 <div class="actions">
  <button type="button" id="btn-validate" class="secondary">Validate</button>
  <button type="button" id="btn-save">Validate &amp; write model_inputs.json</button>
 </div>
 <div id="out">Ready. ESG provenance validates fail-loud through the real loader; the governed calibration and copula structure are never changed.</div>
</main>
<footer>Phase IGUI Task 5 &mdash; economic scenarios / ESG (stop-rule-bounded, owner-gated), stdlib local runner (127.0.0.1, offline). Governed headline SCR carried bit-for-bit: __HEADLINE__. The zero-install RESULTS UI (ui_app.html) is unchanged.</footer>
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
  else{let ty='text';if(f.kind==='float'||f.kind==='int')ty='number';else if(f.kind==='date')ty='date';inp=el('input',{type:ty,value:val==null?'':val});inp.oninput=()=>setv(f.id,inp.value);}
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
    const r=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({esg:vals})});
    const j=await r.json();
    if(j.ok){out.innerHTML='<span class="ok">OK</span>\\n'+JSON.stringify(j,null,1);}
    else{out.innerHTML='<span class="bad">INVALID ('+(j.errors||[]).length+' issue(s))</span>\\n'+(j.errors||[]).join('\\n');}
  }catch(e){out.innerHTML='<span class="bad">runner error</span>\\n'+e;}
}
document.getElementById('btn-validate').onclick=()=>post('/validate_esg');
document.getElementById('btn-save').onclick=()=>post('/save_esg');
renderGroups();renderFrozen();
</script>
</body></html>"""
    return (_tmpl.replace("__HEADLINE__", headline)
                 .replace("__STRUCT__", _html.escape(FROZEN_COPULA_STRUCTURE))
                 .replace("__FIELDS_JS__", fields_js)
                 .replace("__GROUPS_JS__", groups_js)
                 .replace("__VALS_JS__", vals_js)
                 .replace("__FROZEN_JS__", frozen_js))


# --------------------------------------------------------------------------
# (f) Task-5 acceptance gate (structural + LIVE repo cross-checks)
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


def validate_task5_gate(repo_root: str = ".") -> Dict[str, Any]:
    """Task-5 gate: pre-registered acceptance checks, structural + LIVE."""
    checks: Dict[str, bool] = {}
    run_gui = os.path.join(repo_root, "scripts", "run_gui.py")
    loader = os.path.join(repo_root, "scripts", "load_user_inputs.py")
    this_mod = os.path.join(repo_root, "par_model_v2", "viewer", "igui_esg.py")

    # --- plumbing present ---
    checks["esg_module_present"] = os.path.exists(this_mod)
    checks["run_gui_present"] = os.path.exists(run_gui)
    checks["loader_present"] = os.path.exists(loader)

    # --- stdlib-only: this layer pulls in NO forbidden third-party runtime dep ---
    checks["esg_module_stdlib_only"] = not _source_has_forbidden_import(this_mod)

    # --- run_gui serves the esg page + the new endpoints ---
    try:
        with open(run_gui, encoding="utf-8") as fh:
            gui_src = fh.read()
        checks["run_gui_serves_esg"] = ("/esg" in gui_src and "render_esg_html" in gui_src)
        checks["run_gui_has_esg_endpoints"] = all(
            p in gui_src for p in ("/validate_esg", "/save_esg"))
        checks["run_gui_still_localhost"] = ("127.0.0.1" in gui_src and "0.0.0.0" not in gui_src)
        # the prior task pages/endpoints survive unchanged
        checks["run_gui_prior_pages_intact"] = all(
            p in gui_src for p in ("/model-points", "render_model_points_html",
                                   "/assumptions", "render_assumptions_html",
                                   "/validate_assumptions", "render_form_html"))
    except OSError:
        checks["run_gui_serves_esg"] = False
        checks["run_gui_has_esg_endpoints"] = False
        checks["run_gui_still_localhost"] = False
        checks["run_gui_prior_pages_intact"] = False

    # --- loader exposes the esg dict validator the GUI round-trips through ---
    try:
        with open(loader, encoding="utf-8") as fh:
            loader_src = fh.read()
        checks["loader_has_esg_validator"] = "def validate_esg_dict" in loader_src
        m = re.search(r'SCHEMA_VERSION\s*=\s*"([^"]+)"', loader_src)
        checks["schema_version_lockstep"] = bool(m) and m.group(1) == SCHEMA_VERSION
    except OSError:
        checks["loader_has_esg_validator"] = False
        checks["schema_version_lockstep"] = False

    # --- defaults normalise clean + build a loader-valid fragment ---
    typed, errs = normalize_esg(default_esg())
    checks["defaults_normalise_clean"] = (errs == [])
    frag = esg_to_model_inputs(typed, generated_at="1970-01-01T00:00:00+00:00")
    checks["fragment_has_esg"] = (
        isinstance(frag.get("esg"), dict)
        and "market_data" in frag["esg"]
        and "governed_esg_readback" in frag["esg"])

    # --- the fragment passes the loader's own validator ---
    loader_errs = ["<not-run>"]
    _lui = None
    try:
        import sys as _sys
        sp = os.path.join(repo_root, "scripts")
        if sp not in _sys.path:
            _sys.path.insert(0, sp)
        import load_user_inputs as _lui  # noqa: E402
        loader_errs = _lui.validate_esg_dict(frag)
        checks["fragment_passes_loader_validator"] = (loader_errs == [])
    except Exception:
        checks["fragment_passes_loader_validator"] = False

    # --- loader frozen-echo lockstep with this module ---
    try:
        checks["loader_frozen_lockstep"] = (
            _lui is not None and _lui.GOVERNED_ESG_FROZEN == GOVERNED_ESG_FROZEN)
    except Exception:
        checks["loader_frozen_lockstep"] = False

    # --- OWNER-GATING: governed-frozen echo is always the governed values ---
    checks["frozen_echo_is_governed"] = (
        frag["esg"]["governed_esg_readback"] == GOVERNED_ESG_FROZEN)

    # --- OWNER-GATING: a payload that tries to OVERRIDE a frozen calibration is REJECTED ---
    try:
        tampered = json.loads(json.dumps(frag))
        tampered["esg"]["governed_esg_readback"]["equity.equity_vol"] = 9.999
        rej = _lui.validate_esg_dict(tampered)
        checks["frozen_override_rejected"] = (len(rej) > 0)
    except Exception:
        checks["frozen_override_rejected"] = False

    # --- STOP-RULE: a payload that names a NEW copula structure is REJECTED ---
    try:
        newstruct = json.loads(json.dumps(frag))
        newstruct["esg"]["governed_esg_readback"]["dependence.copula_structure"] = "vine_tree3_candidate"
        rej2 = _lui.validate_esg_dict(newstruct)
        checks["new_copula_structure_rejected"] = (len(rej2) > 0)
        # also rejected when smuggled as a top-level esg field
        smuggle = json.loads(json.dumps(frag))
        smuggle["esg"]["copula_structure"] = "skew_t_candidate"
        rej3 = _lui.validate_esg_dict(smuggle)
        checks["stop_rule_guard_blocks_smuggled_structure"] = (len(rej3) > 0)
    except Exception:
        checks["new_copula_structure_rejected"] = False
        checks["stop_rule_guard_blocks_smuggled_structure"] = False

    # --- range validation: an out-of-bounds settable target is caught ---
    try:
        bad = json.loads(json.dumps(default_esg()))
        bad["calibration"]["target_equity_vol"] = 9.0  # > 2
        bt, _ = normalize_esg(bad)
        bfrag = esg_to_model_inputs(bt)
        checks["out_of_bounds_caught"] = (len(_lui.validate_esg_dict(bfrag)) > 0)
    except Exception:
        checks["out_of_bounds_caught"] = False

    # --- date validation: a bad valuation date is rejected at normalisation ---
    bad2 = json.loads(json.dumps(default_esg()))
    bad2["market_data"]["valuation_date"] = "31/05/2026"
    _, e2 = normalize_esg(bad2)
    checks["bad_date_rejected"] = (len(e2) > 0)

    # --- self-contained page: zero external refs; carries headline; shows frozen + stop-rule ---
    page = render_esg_html()
    checks["page_self_contained"] = ('src="http' not in page and 'href="http' not in page
                                     and "//cdn" not in page)
    checks["page_carries_headline"] = (GOVERNED_HEADLINE in page)
    checks["page_shows_frozen_readonly"] = ("readonly" in page and "copula_df_single_t" in page)
    checks["page_shows_stop_rule"] = ("stop-rule" in page and FROZEN_COPULA_STRUCTURE in page)
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
