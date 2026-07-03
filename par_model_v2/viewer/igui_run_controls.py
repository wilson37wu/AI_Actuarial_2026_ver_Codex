"""Phase IGUI Task 2 - run controls + stdlib local-runner core logic.

Pure, **standard-library-only** run-controls layer for the owner-directed
Actuarial Input & Run GUI (Phase IGUI). This module holds everything the local
runner (``scripts/run_gui.py``) needs that is worth unit-testing in isolation:

  * :data:`RUN_CONTROL_FIELDS` - declarative spec of the Task-2 run controls
    (the ``D1_run_controls`` domain of the Task-1 coverage map);
  * :func:`default_run_controls` - defaults aligned with the run orchestrator's
    governed defaults (``scripts/run_model.py``), read-only echo - NOT a model
    parameter change;
  * :func:`normalize_run_controls` - a raw GUI payload (all strings, as an HTML
    form delivers) -> a typed run-controls dict;
  * :func:`run_controls_to_model_inputs` - typed run controls -> the
    ``model_inputs.json`` ``{currency, run_settings}`` sub-schema that
    ``scripts/load_user_inputs.validate_run_controls_dict`` accepts (so a GUI
    payload round-trips through the REAL loader's validation, fail-loud, before
    a run is ever permitted);
  * :func:`reproducibility_digest` - a deterministic sha256 over the canonical
    run controls, surfaced per run (closes the Task-1 "per-run reproducibility
    digest" gap);
  * :func:`render_form_html` - a SELF-CONTAINED input page (zero external
    references, zero JS network) the runner serves on 127.0.0.1;
  * :func:`validate_task2_gate` - a Task-2 acceptance gate (structural checks +
    LIVE repo cross-checks), parallel to the Task-1 ``validate_design_note``.

Binding discipline (unchanged from the design note): NO model parameter
changes; the input+run GUI adds NO third-party runtime dependency (its
server/UI layer is Python standard library only); it binds 127.0.0.1 and makes
NO outbound network call; the Phase 30 stop-rule stands and the MR-016/MR-017
owner decision is not pre-empted; the zero-install RESULTS UI (``ui_app.html``)
stays byte-unchanged. The governed headline SCR is carried bit-for-bit.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import html as _html
import json
import os
import re
from typing import Any, Dict, List, Tuple

DOC_ID = "PHASE_IGUI_TASK2_RUN_CONTROLS"
DOC_VERSION = "1.0.0"

#: Governed headline SCR (frozen single-df t), carried bit-for-bit wherever displayed.
GOVERNED_HEADLINE = "39,975.654628199336"

#: model_inputs.json schema version (kept in lock-step with
#: scripts/load_user_inputs.SCHEMA_VERSION; the Task-2 gate asserts equality).
SCHEMA_VERSION = "1.0.0"

#: Frozen sha256 of the zero-install RESULTS UI; the gate asserts the live file
#: is byte-identical so Task 2 provably leaves ui_app.html unchanged.
UI_APP_SHA256 = "6dca35b3520297263dd06086a1ced18cf831efb3fab6a6e8a9cde744500d7e65"

#: Allowed enumerations - duplicated from the loader and guarded equal by a test.
ALLOWED_SCALES = ("units", "thousands", "millions")
ALLOWED_THOUSANDS = ("comma", "space", "period", "none")

#: Third-party imports the GUI layer must NEVER pull in (stdlib-only contract).
FORBIDDEN_RUNTIME_IMPORTS = (
    "flask", "django", "fastapi", "aiohttp", "tornado", "bottle", "cherrypy",
    "requests", "httpx", "urllib3", "numpy", "pandas", "scipy", "openpyxl",
)

HTML_ARTIFACTS = ["ui_app.html", "model_result_viewer.html", "combined_model_app.html"]


# --------------------------------------------------------------------------
# (a) declarative run-control spec  (Task-1 domain D1_run_controls)
# --------------------------------------------------------------------------
RUN_CONTROL_FIELDS: List[Dict[str, Any]] = [
    {"id": "valuation_date", "label": "Valuation date", "group": "currency",
     "kind": "date", "help": "Reporting / valuation date (YYYY-MM-DD)."},
    {"id": "currency_code", "label": "Reporting currency code", "group": "currency",
     "kind": "text", "help": "3-letter ISO 4217 code, e.g. HKD."},
    {"id": "currency_symbol", "label": "Reporting currency symbol", "group": "currency",
     "kind": "text", "help": "Display symbol, e.g. HK$."},
    {"id": "scale", "label": "Amount scale", "group": "currency",
     "kind": "choice", "choices": list(ALLOWED_SCALES),
     "help": "Units in which monetary inputs/outputs are expressed."},
    {"id": "thousands", "label": "Thousands separator", "group": "currency",
     "kind": "choice", "choices": list(ALLOWED_THOUSANDS),
     "help": "Display grouping separator."},
    {"id": "market_label", "label": "Calibration market label", "group": "currency",
     "kind": "text", "help": "Free-text label for the calibration market/data set."},
    {"id": "n_outer", "label": "Outer (real-world) scenarios", "group": "run_settings",
     "kind": "int", "min": 1,
     "help": "Number of outer / real-world scenarios (explicit; was implicit before)."},
    {"id": "n_inner", "label": "Inner (risk-neutral) paths", "group": "run_settings",
     "kind": "int", "min": 1,
     "help": "Number of inner / risk-neutral valuation paths per outer node."},
    {"id": "n_sim", "label": "Tail simulations (n_sim)", "group": "run_settings",
     "kind": "int", "min": 1,
     "help": "Monte-Carlo draws for the tail/SCR distribution."},
    {"id": "bootstrap_replicates", "label": "Bootstrap replicates", "group": "run_settings",
     "kind": "int", "min": 1, "help": "Bootstrap replicates for tail CIs."},
    {"id": "horizon_months", "label": "Projection horizon (months)", "group": "run_settings",
     "kind": "int", "min": 1, "help": "Total projection horizon in months."},
    {"id": "step_months", "label": "Projection step (months)", "group": "run_settings",
     "kind": "int", "min": 1,
     "help": "Projection time step in months (explicit; must divide the horizon)."},
    {"id": "seed", "label": "Random seed", "group": "run_settings",
     "kind": "int", "help": "Integer seed for reproducibility."},
    {"id": "output_label", "label": "Output label / scenario name", "group": "run_settings",
     "kind": "text", "help": "Label stamped on the run outputs."},
]

#: Defaults aligned with scripts/run_model.GOVERNED_DEFAULTS (echo only).
_GOVERNED_DEFAULTS = {
    "n_outer": 160, "n_inner": 24, "seed": 42, "n_sim": 200_000,
    "bootstrap_replicates": 1_000, "horizon_months": 12,
}


def default_run_controls() -> Dict[str, Any]:
    """Return a clean, valid default run-controls payload (string-valued, as a
    form would submit). Defaults echo the orchestrator's governed defaults; they
    are NOT a model-parameter change - the user may override any run control."""
    return {
        "valuation_date": _dt.date(2026, 6, 30).isoformat(),
        "currency_code": "HKD",
        "currency_symbol": "HK$",
        "scale": "units",
        "thousands": "comma",
        "market_label": "HK_2026_baseline",
        "n_outer": str(_GOVERNED_DEFAULTS["n_outer"]),
        "n_inner": str(_GOVERNED_DEFAULTS["n_inner"]),
        "n_sim": str(_GOVERNED_DEFAULTS["n_sim"]),
        "bootstrap_replicates": str(_GOVERNED_DEFAULTS["bootstrap_replicates"]),
        "horizon_months": str(_GOVERNED_DEFAULTS["horizon_months"]),
        "step_months": "1",
        "seed": str(_GOVERNED_DEFAULTS["seed"]),
        "output_label": "igui_run",
    }


# --------------------------------------------------------------------------
# (b) normalisation  (raw form payload -> typed run controls)
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


def normalize_run_controls(payload: Dict[str, Any]) -> Tuple[Dict[str, Any], List[str]]:
    """Coerce a raw (string) GUI payload into a typed run-controls dict.

    Returns ``(typed, errors)``. Type-coercion problems are reported here in the
    fail-loud message format; deeper range/consistency validation is the
    loader's job (:func:`run_controls_to_model_inputs` then the loader gate).
    """
    errors: List[str] = []
    typed: Dict[str, Any] = {}
    int_ids = {f["id"] for f in RUN_CONTROL_FIELDS if f["kind"] == "int"}
    for f in RUN_CONTROL_FIELDS:
        fid = f["id"]
        raw = payload.get(fid)
        if fid in int_ids:
            iv = _to_int(raw)
            if iv is None:
                errors.append("Field '%s': must be an integer, got %r" % (fid, raw))
            else:
                typed[fid] = iv
        else:
            typed[fid] = _as_str(raw)
    return typed, errors


# --------------------------------------------------------------------------
# (c) typed run controls -> model_inputs.json {currency, run_settings} subset
# --------------------------------------------------------------------------
def _canonical_for_digest(currency: Dict[str, Any], run_settings: Dict[str, Any]) -> str:
    rs = {k: v for k, v in run_settings.items() if k != "reproducibility_digest"}
    return json.dumps({"currency": currency, "run_settings": rs},
                      sort_keys=True, separators=(",", ":"))


def reproducibility_digest(currency: Dict[str, Any], run_settings: Dict[str, Any]) -> str:
    """Deterministic per-run digest over the canonical run controls."""
    payload = _canonical_for_digest(currency, run_settings).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def run_controls_to_model_inputs(typed: Dict[str, Any], *, generated_at: str = None) -> Dict[str, Any]:
    """Build the ``model_inputs.json`` ``{currency, run_settings}`` sub-schema
    (loader-compatible) from a typed run-controls dict, stamping the per-run
    reproducibility digest. Additive run-settings keys (``step_months``,
    ``n_outer``, ``n_inner``, ``reproducibility_digest``) are accepted by the
    run orchestrator and ignored by consumers that do not need them."""
    currency = {
        "code": _as_str(typed.get("currency_code")).upper(),
        "symbol": _as_str(typed.get("currency_symbol")),
        "scale": _as_str(typed.get("scale")),
        "thousands": _as_str(typed.get("thousands")),
        "market_label": _as_str(typed.get("market_label")),
        "valuation_date": _as_str(typed.get("valuation_date")),
    }
    run_settings = {
        "n_outer": typed.get("n_outer"),
        "n_inner": typed.get("n_inner"),
        "n_sim": typed.get("n_sim"),
        "bootstrap_replicates": typed.get("bootstrap_replicates"),
        "horizon_months": typed.get("horizon_months"),
        "step_months": typed.get("step_months"),
        "seed": typed.get("seed"),
        "output_label": _as_str(typed.get("output_label")),
    }
    run_settings["reproducibility_digest"] = reproducibility_digest(currency, run_settings)
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at or _dt.datetime.now(_dt.timezone.utc).isoformat(),
        "source": "igui_run_gui (Phase IGUI Task 2 run controls)",
        "currency": currency,
        "run_settings": run_settings,
    }


# --------------------------------------------------------------------------
# (d) self-contained input page  (zero external refs, zero JS network)
# --------------------------------------------------------------------------
def _field_input_html(f: Dict[str, Any], value: str) -> str:
    fid = _html.escape(f["id"])
    val = _html.escape(str(value))
    if f["kind"] == "choice":
        opts = "".join(
            '<option value="%s"%s>%s</option>' % (
                _html.escape(c), " selected" if c == value else "", _html.escape(c))
            for c in f["choices"])
        return '<select id="%s" name="%s">%s</select>' % (fid, fid, opts)
    typ = {"date": "date", "int": "number", "text": "text"}.get(f["kind"], "text")
    extra = ' min="%d"' % f["min"] if f.get("min") is not None else ""
    return '<input id="%s" name="%s" type="%s" value="%s"%s>' % (fid, fid, typ, val, extra)


def render_form_html(values: Dict[str, Any] = None) -> str:
    """Render the SELF-CONTAINED run-controls input page. No external src/href,
    no JS network call other than same-origin POSTs to the local runner."""
    values = values or default_run_controls()
    groups = [("currency", "Run controls - currency &amp; valuation"),
              ("run_settings", "Run controls - simulation settings")]
    sections = []
    for gid, gtitle in groups:
        rows = []
        for f in RUN_CONTROL_FIELDS:
            if f["group"] != gid:
                continue
            rows.append(
                '<div class="row"><label for="%s">%s</label>%s'
                '<span class="help">%s</span></div>' % (
                    _html.escape(f["id"]), _html.escape(f["label"]),
                    _field_input_html(f, values.get(f["id"], "")),
                    _html.escape(f["help"])))
        sections.append('<fieldset><legend>%s</legend>%s</fieldset>' % (gtitle, "".join(rows)))
    body = "".join(sections)
    # NOTE: all script/style inline; no external references; POSTs are same-origin.
    return """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Actuarial Input &amp; Run GUI - Run Controls (Phase IGUI Task 2)</title>
<style>
 body{font-family:system-ui,Arial,sans-serif;margin:0;background:#0f1722;color:#e7eef7}
 header{padding:16px 22px;background:#16263a;border-bottom:1px solid #24405e}
 h1{font-size:18px;margin:0}
 main{max-width:780px;margin:0 auto;padding:22px}
 fieldset{border:1px solid #24405e;border-radius:8px;margin:0 0 18px;padding:14px 16px}
 legend{padding:0 8px;color:#8fb6e6;font-weight:600}
 .row{display:grid;grid-template-columns:230px 200px 1fr;gap:10px;align-items:center;margin:8px 0}
 label{color:#cfe0f4}
 input,select{background:#0b1320;color:#e7eef7;border:1px solid #2c4a6b;border-radius:6px;padding:6px 8px}
 .help{color:#7f97b3;font-size:12px}
 .actions{display:flex;gap:12px;margin-top:8px}
 button{background:#2563eb;color:#fff;border:0;border-radius:6px;padding:9px 16px;font-size:14px;cursor:pointer}
 button.secondary{background:#33445c}
 button.run{background:#059669}
 button:disabled{background:#33445c;opacity:.6;cursor:not-allowed}
 #out{white-space:pre-wrap;background:#0b1320;border:1px solid #24405e;border-radius:8px;padding:12px;margin-top:14px;font-family:ui-monospace,Menlo,monospace;font-size:12.5px}
 .ok{color:#36d399}.bad{color:#f87272}
 footer{color:#6c8099;font-size:12px;padding:12px 22px;border-top:1px solid #24405e}
</style></head>
<body>
<header><h1>Actuarial Input &amp; Run GUI &mdash; Run Controls</h1></header>
""" + __import__("par_model_v2.viewer.igui_portfolio_builder",
                 fromlist=["nav_html"]).nav_html("/") + """
<main>
 <form id="rc">%s
  <div class="actions">
   <button type="button" id="btn-validate" class="secondary">Validate</button>
   <button type="button" id="btn-save" class="secondary">Validate &amp; write model_inputs.json</button>
   <button type="button" id="btn-run" class="run">Save &amp; RUN model</button>
  </div>
  <div class="actions" style="margin-top:6px">
   <label class="help" style="display:flex;gap:6px;align-items:center">
    <input type="checkbox" id="run-smoke" checked> Fast smoke run (diagnostic scenario budget)</label>
   <label class="help" style="display:flex;gap:6px;align-items:center">
    <input type="checkbox" id="run-autofill" checked> Auto-fill missing sections (model points / assumptions / ESG) with governed defaults</label>
  </div>
 </form>
 <div id="out">Ready. Validation runs through the real loader (fail-loud) before any write.</div>
</main>
<footer>Phase IGUI Task 2 &mdash; stdlib local runner (127.0.0.1, offline). Governed headline SCR carried bit-for-bit: %s. The zero-install RESULTS UI (ui_app.html) is unchanged.</footer>
<script>
const out=document.getElementById('out');
function payload(){const d={};new FormData(document.getElementById('rc')).forEach((v,k)=>d[k]=v);return d;}
async function post(path){
  out.textContent='Working...';
  try{
    const r=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload())});
    const j=await r.json();
    if(j.ok){out.innerHTML='<span class="ok">OK</span>\\n'+JSON.stringify(j,null,1);}
    else{out.innerHTML='<span class="bad">INVALID ('+(j.errors||[]).length+' issue(s))</span>\\n'+(j.errors||[]).join('\\n');}
  }catch(e){out.innerHTML='<span class="bad">runner error</span>\\n'+e;}
}
document.getElementById('btn-validate').onclick=()=>post('/validate');
document.getElementById('btn-save').onclick=()=>post('/save');
/* GUI-5 (owner request): one-click save -> auto-fill -> gate -> async run */
const btnRun=document.getElementById('btn-run');
function setRunning(b){btnRun.disabled=b;
  document.getElementById('btn-validate').disabled=b;
  document.getElementById('btn-save').disabled=b;}
function pollJob(id){
  fetch('/jobs/'+id).then(r=>r.json()).then(j=>{
    if(j&&j.progress){out.textContent='RUNNING (job '+id+')\\n'+j.progress.join('\\n');}
    if(j&&(j.state==='succeeded'||j.state==='failed')){
      setRunning(false);
      if(j.state==='succeeded'){
        const h=(j.result&&j.result.headline)||{};
        out.innerHTML='<span class="ok">RUN COMPLETE</span>\\n'
          +'nested_scr: '+(h.nested_scr==null?'--':Number(h.nested_scr).toLocaleString())+'\\n'
          +'copula_scr: '+(h.copula_scr==null?'--':Number(h.copula_scr).toLocaleString())+'\\n'
          +'var_covar_scr: '+(h.var_covar_scr==null?'--':Number(h.var_covar_scr).toLocaleString())+'\\n\\n'
          +'<a href="/my-results" style="color:#8fb6e6">Open YOUR results &rarr;</a>   '
          +'<a href="/history" style="color:#8fb6e6">Run history &amp; compare &rarr;</a>';
      }else{
        out.innerHTML='<span class="bad">RUN FAILED</span>\\n'
          +((j.result&&(j.result.errors||[]).join('\\n'))||j.error||'')+'\\n'
          +((j.progress||[]).join('\\n'));
      }
    }else{setTimeout(()=>pollJob(id),2000);}
  }).catch(()=>setTimeout(()=>pollJob(id),4000));}
btnRun.onclick=async()=>{
  setRunning(true);out.textContent='Saving inputs, checking the run gate...';
  try{
    const body=payload();
    body.smoke=document.getElementById('run-smoke').checked;
    body.autofill=document.getElementById('run-autofill').checked;
    const r=await fetch('/save-run',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    const j=await r.json();
    if(j.ok&&j.job_id){
      out.textContent='Run submitted (job '+j.job_id+')'
        +(j.autofilled&&j.autofilled.length?'\\nauto-filled with governed defaults: '+j.autofilled.join(', '):'')
        +'\\ninputs digest: '+((j.gate&&j.gate.reproducibility_digest)||'');
      pollJob(j.job_id);
    }else if(j.stage==='run_gate_blocked'){
      setRunning(false);
      out.innerHTML='<span class="bad">RUN GATE BLOCKED ('+(j.blocking_issues||[]).length+' issue(s))</span>\\n'
        +(j.blocking_issues||[]).join('\\n')+'\\n\\n'+(j.hint||'')+'\\n'
        +'<a href="/model-points" style="color:#8fb6e6">Model Points</a>  '
        +'<a href="/assumptions" style="color:#8fb6e6">Assumptions</a>  '
        +'<a href="/esg" style="color:#8fb6e6">ESG</a>  '
        +'<a href="/run-gate" style="color:#8fb6e6">Run Gate</a>';
    }else{
      setRunning(false);
      out.innerHTML='<span class="bad">'+(j.stage||'refused')+'</span>\\n'+((j.errors||[]).join('\\n'));
    }
  }catch(e){setRunning(false);out.innerHTML='<span class="bad">runner error</span>\\n'+e;}
};
</script>
</body></html>""" % (body, _html.escape(GOVERNED_HEADLINE))


# --------------------------------------------------------------------------
# (e) Task-2 acceptance gate  (structural + LIVE repo cross-checks)
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
        return True  # missing source counts as a failure for the gate
    with open(path, encoding="utf-8") as fh:
        src = fh.read()
    for mod in FORBIDDEN_RUNTIME_IMPORTS:
        if re.search(r'^\s*(?:import|from)\s+%s\b' % re.escape(mod), src, re.MULTILINE):
            return True
    return False


def validate_task2_gate(repo_root: str = ".") -> Dict[str, Any]:
    """Task-2 gate: pre-registered acceptance checks, structural + LIVE."""
    checks: Dict[str, bool] = {}
    run_gui = os.path.join(repo_root, "scripts", "run_gui.py")
    loader = os.path.join(repo_root, "scripts", "load_user_inputs.py")
    orch = os.path.join(repo_root, "scripts", "run_model.py")
    this_mod = os.path.join(repo_root, "par_model_v2", "viewer", "igui_run_controls.py")

    # --- plumbing present ---
    checks["run_gui_present"] = os.path.exists(run_gui)
    checks["core_module_present"] = os.path.exists(this_mod)
    checks["loader_present"] = os.path.exists(loader)
    checks["orchestrator_present"] = os.path.exists(orch)

    # --- stdlib-only: GUI layer pulls in NO forbidden third-party runtime dep ---
    checks["run_gui_stdlib_only"] = not _source_has_forbidden_import(run_gui)
    checks["core_module_stdlib_only"] = not _source_has_forbidden_import(this_mod)

    # --- localhost-bound, no outbound network (source contract) ---
    try:
        with open(run_gui, encoding="utf-8") as fh:
            gui_src = fh.read()
        checks["run_gui_binds_localhost"] = ("127.0.0.1" in gui_src and "0.0.0.0" not in gui_src)
    except OSError:
        checks["run_gui_binds_localhost"] = False

    # --- loader exposes the dict validator the GUI round-trips through ---
    try:
        with open(loader, encoding="utf-8") as fh:
            loader_src = fh.read()
        checks["loader_has_dict_validator"] = "def validate_run_controls_dict" in loader_src
        m = re.search(r'SCHEMA_VERSION\s*=\s*"([^"]+)"', loader_src)
        checks["schema_version_lockstep"] = bool(m) and m.group(1) == SCHEMA_VERSION
        checks["loader_scale_enum_lockstep"] = (
            'ALLOWED_SCALES = ("units", "thousands", "millions")' in loader_src)
        checks["loader_thousands_enum_lockstep"] = (
            'ALLOWED_THOUSANDS = ("comma", "space", "period", "none")' in loader_src)
    except OSError:
        checks["loader_has_dict_validator"] = False
        checks["schema_version_lockstep"] = False
        checks["loader_scale_enum_lockstep"] = False
        checks["loader_thousands_enum_lockstep"] = False

    # --- run controls round-trip: defaults normalise, build, digest twice equal ---
    typed, norm_errs = normalize_run_controls(default_run_controls())
    checks["defaults_normalise_clean"] = (norm_errs == [])
    mi = run_controls_to_model_inputs(typed, generated_at="1970-01-01T00:00:00+00:00")
    d1 = reproducibility_digest(mi["currency"], mi["run_settings"])
    d2 = reproducibility_digest(mi["currency"], mi["run_settings"])
    checks["digest_deterministic"] = (d1 == d2 and d1.startswith("sha256:") and len(d1) == 71)
    checks["model_inputs_has_run_settings"] = (
        "run_settings" in mi and "currency" in mi
        and "step_months" in mi["run_settings"]
        and "n_outer" in mi["run_settings"] and "n_inner" in mi["run_settings"])

    # --- the self-contained form: governed headline + zero external refs ---
    form = render_form_html()
    checks["form_carries_headline"] = GOVERNED_HEADLINE in form
    checks["form_has_all_fields"] = all(('name="%s"' % f["id"]) in form for f in RUN_CONTROL_FIELDS)
    checks["form_zero_external_refs"] = (
        len(re.findall(r'(?:src|href)="(?:https?:)?//', form)) == 0)

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
        checks["governance_change_records_floor"] = len(gov.get("change_records", [])) >= 100
    except (OSError, json.JSONDecodeError):
        checks["governance_risk_register_frozen"] = False
        checks["governance_change_records_floor"] = False

    return {"ok": all(checks.values()), "n_checks": len(checks), "checks": checks}
