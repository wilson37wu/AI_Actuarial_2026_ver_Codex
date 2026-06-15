"""Phase IGUI Task 6 - validation surfacing + governance gating BEFORE a run.

The owner-directed Phase IGUI input+run GUI now collects every input domain
(Task 2 run controls, Task 3 model points, Task 4 assumptions, Task 5 ESG) and
writes them into the loader's ``model_inputs.json`` schema. This module is the
D5_validation_gating layer: it AGGREGATES the loader's fail-loud validation
across ALL domains, SURFACES every issue in the GUI, and BLOCKS the Run action
until the assembled ``model_inputs.json`` is clean across every domain. When the
gate clears it records a governance gate (a ChangeRecord-style provenance object)
plus a deterministic run-level reproducibility digest, so a run can never start
from an incomplete / inconsistent / un-provenanced input set.

Discipline (unchanged): standard-library only (no third-party runtime dep); the
governed headline SCR is carried bit-for-bit; the Phase 30 stop-rule stands (the
frozen copula structure is echoed read-only, never altered); the MR-016/MR-017
owner decision is not pre-empted; the zero-install RESULTS UI (``ui_app.html``)
is byte-unchanged; NO model parameter change. This layer SURFACES validation and
records the gate - it does NOT execute the model (end-to-end run + results
handoff is Task 7).
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import html as _html
import json
import os
import re
from typing import Any, Dict, List

DOC_ID = "PHASE_IGUI_TASK6_VALIDATION_GATING"
DOC_VERSION = "1.0.0"

#: Governed headline SCR (frozen single-df t), carried bit-for-bit wherever shown.
GOVERNED_HEADLINE = "39,975.654628199336"

#: model_inputs.json schema version (kept in lock-step with
#: scripts/load_user_inputs.SCHEMA_VERSION; the Task-6 gate asserts equality).
SCHEMA_VERSION = "1.0.0"

#: Frozen sha256 of the zero-install RESULTS UI; the gate asserts the live file
#: is byte-identical so Task 6 provably leaves ui_app.html unchanged.
UI_APP_SHA256 = "6dca35b3520297263dd06086a1ced18cf831efb3fab6a6e8a9cde744500d7e65"

#: The pinned, FROZEN dependence structure (Phase 30 stop-rule). Echoed read-only
#: in the gate provenance; never altered here.
FROZEN_COPULA_STRUCTURE = "single_t_grouped_FROZEN"

#: The GUI input domains, in collection order. Every one must be present AND clean
#: before the run gate clears.
DOMAINS = ("run_controls", "model_points", "assumptions", "esg")

#: Human-readable labels for the gate page + records.
DOMAIN_LABELS = {
    "run_controls": "Run controls (Task 2)",
    "model_points": "Model points / in-force (Task 3)",
    "assumptions": "Assumptions (Task 4)",
    "esg": "Economic scenarios / ESG (Task 5)",
}

#: Third-party imports the GUI layer must NEVER pull in (stdlib-only contract).
FORBIDDEN_RUNTIME_IMPORTS = (
    "flask", "django", "fastapi", "aiohttp", "tornado", "bottle", "cherrypy",
    "requests", "httpx", "urllib3", "numpy", "pandas", "scipy", "openpyxl",
)


# --------------------------------------------------------------------------
# (a) deterministic run-level reproducibility digest
# --------------------------------------------------------------------------
def _canonical_inputs(model_inputs: Dict[str, Any]) -> Dict[str, Any]:
    """A copy of the assembled inputs with VOLATILE / derived keys removed so the
    digest pins only the substantive, run-determining content. Stripping the
    wall-clock ``generated_at`` and any previously-recorded ``run_gate`` makes the
    digest reproducible for identical inputs."""
    clean = json.loads(json.dumps(model_inputs)) if isinstance(model_inputs, dict) else {}
    for volatile in ("generated_at", "run_gate"):
        clean.pop(volatile, None)
    return clean


def run_reproducibility_digest(model_inputs: Dict[str, Any]) -> str:
    """Deterministic ``sha256:<64 hex>`` digest over the canonical assembled inputs
    (volatile keys stripped). Same shape the loader validates for run-settings
    digests, so it can be surfaced and re-validated identically."""
    canonical = json.dumps(_canonical_inputs(model_inputs), sort_keys=True,
                           separators=(",", ":"))
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# --------------------------------------------------------------------------
# (b) aggregate validation across ALL domains (routes through the REAL loader)
# --------------------------------------------------------------------------
def aggregate_validation(model_inputs: Dict[str, Any],
                         loader_module: Any = None) -> Dict[str, Any]:
    """Run the loader's per-domain validators over the WHOLE assembled inputs dict
    and return a per-domain summary plus an overall verdict. Delegates to
    ``load_user_inputs.validate_assembled_inputs`` (the single fail-loud source of
    truth) so the GUI surfaces EXACTLY what the loader would reject. ``loader_module``
    may be injected for testing; otherwise it is imported lazily."""
    if loader_module is None:
        import load_user_inputs as loader_module  # scripts/ on sys.path
    return loader_module.validate_assembled_inputs(model_inputs)


# --------------------------------------------------------------------------
# (c) the governance run-gate (ChangeRecord-style provenance + digest)
# --------------------------------------------------------------------------
def build_run_gate(model_inputs: Dict[str, Any], validation: Dict[str, Any],
                   *, now: str = None) -> Dict[str, Any]:
    """Assemble the run-gate provenance record. ``validation`` is the output of
    :func:`aggregate_validation`. The record captures the gate DECISION
    (``CLEARED`` only when every domain is present AND clean, else ``BLOCKED``),
    a per-domain summary, the flat list of blocking issues, the run-level
    reproducibility digest, the governed headline and the read-only frozen copula
    structure. It is recorded BEFORE a run is permitted; it does NOT execute the
    model (that is Task 7)."""
    domains = validation.get("domains", {})
    cleared = bool(validation.get("ok"))
    blocking: List[str] = []
    domain_summary: Dict[str, Any] = {}
    for d in DOMAINS:
        info = domains.get(d, {"present": False, "ok": False,
                               "errors": ["domain not evaluated"]})
        domain_summary[d] = {
            "label": DOMAIN_LABELS[d],
            "present": bool(info.get("present")),
            "ok": bool(info.get("ok")),
            "n_errors": len(info.get("errors", [])),
        }
        if not info.get("ok"):
            for e in info.get("errors", []):
                blocking.append("[%s] %s" % (d, e))
    return {
        "record_type": "RUN_GATE",
        "doc_id": DOC_ID,
        "doc_version": DOC_VERSION,
        "generated_at": now or _dt.datetime.now(_dt.timezone.utc).isoformat(),
        "decision": "CLEARED" if cleared else "BLOCKED",
        "run_permitted": cleared,
        "schema_version": SCHEMA_VERSION,
        "reproducibility_digest": run_reproducibility_digest(model_inputs),
        "governed_headline": GOVERNED_HEADLINE,
        "frozen_copula_structure": FROZEN_COPULA_STRUCTURE,
        "domains": domain_summary,
        "n_blocking_issues": len(blocking),
        "blocking_issues": blocking,
        "provenance": {
            "source": "igui_run_gui (Phase IGUI Task 6 validation gating)",
            "ui_app_sha256": UI_APP_SHA256,
            "note": ("Run gate records readiness + reproducibility provenance only; "
                     "model execution and results handoff are Task 7."),
        },
    }


# --------------------------------------------------------------------------
# (d) self-contained validation / run-gate page
# --------------------------------------------------------------------------
def _js_const(name: str, obj: Any) -> str:
    return "const %s=%s;" % (name, json.dumps(obj))


def render_gate_html() -> str:
    """Render the SELF-CONTAINED validation / run-gate page. No external src/href;
    the only network is same-origin POSTs to the local runner. On load it POSTs
    ``/preflight`` (read-only aggregate validation of the assembled
    model_inputs.json) and renders per-domain PASS/FAIL with every loader issue.
    The Run button is DISABLED until ALL domains are present and clean; pressing it
    POSTs ``/run`` which records the governance gate + reproducibility digest."""
    domains_js = _js_const("DOMAINS", [{"id": d, "label": DOMAIN_LABELS[d]} for d in DOMAINS])
    headline = _html.escape(GOVERNED_HEADLINE)
    struct = _html.escape(FROZEN_COPULA_STRUCTURE)
    _tmpl = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Actuarial Input &amp; Run GUI - Validation &amp; Run Gate (Phase IGUI Task 6)</title>
<style>
 body{font-family:system-ui,Arial,sans-serif;margin:0;background:#0f1722;color:#e7eef7}
 header{padding:16px 22px;background:#16263a;border-bottom:1px solid #24405e}
 h1{font-size:18px;margin:0}
 h2{font-size:15px;color:#8fb6e6;margin:0}
 main{max-width:1040px;margin:0 auto;padding:22px}
 .domain{border:1px solid #24405e;border-radius:8px;margin:0 0 12px;padding:10px 14px;background:#13202f}
 .domain h3{margin:0 0 4px;font-size:14.5px}
 .pill{display:inline-block;border-radius:10px;padding:1px 9px;font-size:12px;font-weight:600;margin-left:8px}
 .pill.ok{background:#10391f;color:#36d399}
 .pill.bad{background:#3a1414;color:#f87272}
 .pill.missing{background:#3a3014;color:#fbbd23}
 ul.issues{margin:6px 0 0;padding-left:18px}
 ul.issues li{color:#f3b1b1;font-size:12.5px;margin:2px 0;font-family:ui-monospace,Menlo,monospace}
 .gate{border:2px solid #24405e;border-radius:10px;padding:14px;margin:16px 0;background:#16263a}
 .gate.cleared{border-color:#1f7a44}
 .gate.blocked{border-color:#7a2b2b}
 .actions{display:flex;gap:12px;margin:12px 0;flex-wrap:wrap}
 button{background:#2563eb;color:#fff;border:0;border-radius:6px;padding:9px 14px;font-size:14px;cursor:pointer}
 button.secondary{background:#33445c}
 button:disabled{background:#33384a;color:#8090a5;cursor:not-allowed}
 #out{white-space:pre-wrap;background:#0b1320;border:1px solid #24405e;border-radius:8px;padding:12px;margin-top:14px;font-family:ui-monospace,Menlo,monospace;font-size:12.5px}
 .ok{color:#36d399}.bad{color:#f87272}.warn{color:#fbbd23}
 footer{color:#6c8099;font-size:12px;padding:12px 22px;border-top:1px solid #24405e}
 .stop{color:#fbbd23;font-size:12px;margin:4px 0 10px}
</style></head>
<body>
<header><h1>Actuarial Input &amp; Run GUI &mdash; Validation &amp; Run Gate</h1>
<h2>The Run action is BLOCKED until every input domain is present and clean.</h2></header>
<main>
 <div class="stop">Phase 30 stop-rule: the dependence structure stays pinned to <b>__STRUCT__</b> (read-only echo). The gate records provenance + a reproducibility digest before a run; it does not execute the model (that is Task 7). MR-016/MR-017 remains with the owner.</div>
 <div id="domains"></div>
 <div id="gate" class="gate blocked">
   <b>Run gate:</b> <span id="gate-state" class="warn">checking&hellip;</span>
   <div id="gate-digest" class="help"></div>
 </div>
 <div class="actions">
  <button type="button" id="btn-refresh" class="secondary">Re-validate all domains</button>
  <button type="button" id="btn-run" disabled>Record run gate &amp; clear for run</button>
 </div>
 <div id="out">Validating the assembled model_inputs.json across all domains&hellip;</div>
</main>
<footer>Phase IGUI Task 6 &mdash; validation surfacing + governance gating before run (stdlib local runner, 127.0.0.1, offline). Governed headline SCR carried bit-for-bit: __HEADLINE__. The zero-install RESULTS UI (ui_app.html) is unchanged.</footer>
<script>
__DOMAINS_JS__
function el(t,a,c){const e=document.createElement(t);if(a)for(const k in a)e.setAttribute(k,a[k]);if(c!=null)e.textContent=c;return e;}
function renderDomains(v){
  const wrap=document.getElementById('domains');wrap.innerHTML='';
  const dmap=(v&&v.domains)||{};
  DOMAINS.forEach(d=>{
    const info=dmap[d.id]||{present:false,ok:false,errors:['not evaluated']};
    const box=el('div',{class:'domain'});
    const h=el('h3',null,d.label);
    let cls='ok',txt='PASS';
    if(!info.present){cls='missing';txt='MISSING';}
    else if(!info.ok){cls='bad';txt='FAIL ('+(info.errors||[]).length+')';}
    h.appendChild(el('span',{class:'pill '+cls},txt));
    box.appendChild(h);
    if(info.errors&&info.errors.length){
      const ul=el('ul',{class:'issues'});
      info.errors.forEach(e=>ul.appendChild(el('li',null,e)));
      box.appendChild(ul);
    }
    wrap.appendChild(box);
  });
}
function setGate(v){
  const g=document.getElementById('gate');const st=document.getElementById('gate-state');
  const run=document.getElementById('btn-run');const dg=document.getElementById('gate-digest');
  const ok=!!(v&&v.ok);
  g.className='gate '+(ok?'cleared':'blocked');
  st.className=ok?'ok':'bad';
  st.textContent=ok?'CLEARED - all domains present and clean':('BLOCKED - '+((v&&v.n_errors)||0)+' issue(s) across domains');
  run.disabled=!ok;
  dg.textContent='';
}
async function preflight(){
  const out=document.getElementById('out');out.textContent='Validating all domains...';
  try{
    const r=await fetch('/preflight',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});
    const j=await r.json();renderDomains(j);setGate(j);
    out.innerHTML=(j.ok?'<span class="ok">All domains valid. Run is cleared once you record the gate.</span>':'<span class="bad">Run blocked. Resolve the issues above (edit the domain pages and re-save), then re-validate.</span>')+'\\n'+JSON.stringify(j,null,1);
  }catch(e){out.innerHTML='<span class="bad">runner error</span>\\n'+e;}
}
async function recordRun(){
  const out=document.getElementById('out');out.textContent='Recording run gate...';
  try{
    const r=await fetch('/run',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});
    const j=await r.json();
    if(j.ok&&j.run_gate){
      const dg=document.getElementById('gate-digest');dg.textContent='digest '+j.run_gate.reproducibility_digest;
      out.innerHTML='<span class="ok">RUN GATE RECORDED ('+j.run_gate.decision+')</span>\\n'+JSON.stringify(j,null,1);
    }else{
      renderDomains(j.validation||j);setGate(j.validation||j);
      out.innerHTML='<span class="bad">Run gate BLOCKED</span>\\n'+JSON.stringify(j,null,1);
    }
  }catch(e){out.innerHTML='<span class="bad">runner error</span>\\n'+e;}
}
document.getElementById('btn-refresh').onclick=preflight;
document.getElementById('btn-run').onclick=recordRun;
preflight();
</script>
</body></html>"""
    return (_tmpl.replace("__HEADLINE__", headline)
                 .replace("__STRUCT__", struct)
                 .replace("__DOMAINS_JS__", domains_js))


# --------------------------------------------------------------------------
# (e) Task-6 acceptance gate (structural + LIVE repo cross-checks)
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


def _clean_assembled_inputs() -> Dict[str, Any]:
    """A fully-populated, valid assembled model_inputs dict built from each domain's
    own defaults (used by the gate + tests to assert a clean set CLEARS)."""
    import sys as _sys
    from par_model_v2.viewer.igui_run_controls import (
        default_run_controls, normalize_run_controls, run_controls_to_model_inputs)
    from par_model_v2.viewer.igui_model_points import (
        default_balance_sheet, default_model_points, normalize_balance_sheet,
        normalize_model_points, portfolio_to_model_inputs)
    from par_model_v2.viewer.igui_assumptions import (
        default_assumptions, normalize_assumptions, assumptions_to_model_inputs)
    from par_model_v2.viewer.igui_esg import (
        default_esg, normalize_esg, esg_to_model_inputs)
    rc_typed, _ = normalize_run_controls(default_run_controls())
    rc = run_controls_to_model_inputs(rc_typed)
    rows, _ = normalize_model_points(default_model_points())
    bs, _ = normalize_balance_sheet(default_balance_sheet())
    pf = portfolio_to_model_inputs(rows, bs)
    a_typed, _ = normalize_assumptions(default_assumptions())
    asm = assumptions_to_model_inputs(a_typed)
    e_typed, _ = normalize_esg(default_esg())
    esg = esg_to_model_inputs(e_typed)
    merged: Dict[str, Any] = {"schema_version": SCHEMA_VERSION}
    merged.update({"currency": rc["currency"], "run_settings": rc["run_settings"]})
    merged.update({"portfolio": pf["portfolio"], "balance_sheet": pf["balance_sheet"],
                   "totals": pf["totals"]})
    merged["assumptions"] = asm["assumptions"]
    merged["esg"] = esg["esg"]
    return merged


def validate_task6_gate(repo_root: str = ".") -> Dict[str, Any]:
    """Task-6 gate: pre-registered acceptance checks, structural + LIVE."""
    checks: Dict[str, bool] = {}
    run_gui = os.path.join(repo_root, "scripts", "run_gui.py")
    loader = os.path.join(repo_root, "scripts", "load_user_inputs.py")
    this_mod = os.path.join(repo_root, "par_model_v2", "viewer", "igui_validation_gating.py")
    ui_app = os.path.join(repo_root, "ui_app.html")

    # --- plumbing present ---
    checks["gating_module_present"] = os.path.exists(this_mod)
    checks["run_gui_present"] = os.path.exists(run_gui)
    checks["loader_present"] = os.path.exists(loader)

    # --- stdlib-only: this layer pulls in NO forbidden third-party runtime dep ---
    checks["gating_module_stdlib_only"] = not _source_has_forbidden_import(this_mod)

    # --- run_gui serves the gate page + the new endpoints; prior pages survive ---
    try:
        with open(run_gui, encoding="utf-8") as fh:
            gui_src = fh.read()
        checks["run_gui_serves_run_gate"] = ("/run-gate" in gui_src and "render_gate_html" in gui_src)
        checks["run_gui_has_gate_endpoints"] = all(p in gui_src for p in ("/preflight", "/run"))
        checks["run_gui_still_localhost"] = ("127.0.0.1" in gui_src and "0.0.0.0" not in gui_src)
        checks["run_gui_prior_pages_intact"] = all(
            p in gui_src for p in ("/model-points", "render_model_points_html",
                                   "/assumptions", "render_assumptions_html",
                                   "/esg", "render_esg_html", "render_form_html"))
    except OSError:
        checks["run_gui_serves_run_gate"] = False
        checks["run_gui_has_gate_endpoints"] = False
        checks["run_gui_still_localhost"] = False
        checks["run_gui_prior_pages_intact"] = False

    # --- loader exposes the aggregate validator the gate routes through ---
    try:
        with open(loader, encoding="utf-8") as fh:
            loader_src = fh.read()
        checks["loader_has_aggregate_validator"] = "def validate_assembled_inputs" in loader_src
        m = re.search(r'SCHEMA_VERSION\s*=\s*"([^"]+)"', loader_src)
        checks["schema_version_lockstep"] = bool(m) and m.group(1) == SCHEMA_VERSION
    except OSError:
        checks["loader_has_aggregate_validator"] = False
        checks["schema_version_lockstep"] = False

    # --- ui_app.html byte-unchanged (zero-install RESULTS UI frozen) ---
    try:
        with open(ui_app, "rb") as fh:
            checks["ui_app_byte_unchanged"] = (
                hashlib.sha256(fh.read()).hexdigest() == UI_APP_SHA256)
    except OSError:
        checks["ui_app_byte_unchanged"] = False

    # --- LIVE behaviour: a fully-populated valid input set CLEARS ---
    loader_errs_present = True
    try:
        import sys as _sys
        for p in (repo_root, os.path.join(repo_root, "scripts")):
            if p not in _sys.path:
                _sys.path.insert(0, p)
        import load_user_inputs as _lui  # noqa: E402
        loader_errs_present = hasattr(_lui, "validate_assembled_inputs")
        clean = _clean_assembled_inputs()
        v_clean = aggregate_validation(clean, _lui)
        checks["clean_inputs_clear"] = bool(v_clean.get("ok"))
        gate_clean = build_run_gate(clean, v_clean, now="1970-01-01T00:00:00+00:00")
        checks["clean_gate_decision_cleared"] = (gate_clean["decision"] == "CLEARED"
                                                 and gate_clean["run_permitted"] is True)
        checks["gate_has_digest"] = (
            isinstance(gate_clean.get("reproducibility_digest"), str)
            and gate_clean["reproducibility_digest"].startswith("sha256:")
            and len(gate_clean["reproducibility_digest"]) == 71)
        checks["gate_echoes_frozen_structure"] = (
            gate_clean["frozen_copula_structure"] == FROZEN_COPULA_STRUCTURE)
        checks["gate_carries_headline"] = (gate_clean["governed_headline"] == GOVERNED_HEADLINE)

        # --- LIVE behaviour: an INCOMPLETE set is BLOCKED (a missing domain blocks) ---
        incomplete = json.loads(json.dumps(clean))
        incomplete.pop("esg", None)
        v_bad = aggregate_validation(incomplete, _lui)
        checks["incomplete_inputs_blocked"] = (v_bad.get("ok") is False)
        gate_bad = build_run_gate(incomplete, v_bad)
        checks["incomplete_gate_decision_blocked"] = (
            gate_bad["decision"] == "BLOCKED" and gate_bad["run_permitted"] is False
            and gate_bad["n_blocking_issues"] >= 1)

        # --- LIVE behaviour: an INVALID field is surfaced + blocks ---
        invalid = json.loads(json.dumps(clean))
        invalid["run_settings"]["n_outer"] = 0  # violates >= 1
        v_inv = aggregate_validation(invalid, _lui)
        checks["invalid_field_blocked"] = (
            v_inv.get("ok") is False
            and v_inv["domains"]["run_controls"]["ok"] is False)

        # --- digest determinism ---
        checks["digest_deterministic"] = (
            run_reproducibility_digest(clean) == run_reproducibility_digest(clean))
        # --- a content change moves the digest ---
        moved = json.loads(json.dumps(clean))
        moved["run_settings"]["seed"] = int(moved["run_settings"].get("seed", 0)) + 1
        checks["digest_sensitive_to_inputs"] = (
            run_reproducibility_digest(moved) != run_reproducibility_digest(clean))
        # --- the volatile generated_at does NOT move the digest ---
        tstamped = json.loads(json.dumps(clean))
        tstamped["generated_at"] = "2099-01-01T00:00:00+00:00"
        checks["digest_ignores_timestamp"] = (
            run_reproducibility_digest(tstamped) == run_reproducibility_digest(clean))
    except Exception:
        for k in ("clean_inputs_clear", "clean_gate_decision_cleared", "gate_has_digest",
                  "gate_echoes_frozen_structure", "gate_carries_headline",
                  "incomplete_inputs_blocked", "incomplete_gate_decision_blocked",
                  "invalid_field_blocked", "digest_deterministic",
                  "digest_sensitive_to_inputs", "digest_ignores_timestamp"):
            checks.setdefault(k, False)
    checks["loader_validate_assembled_present"] = loader_errs_present

    # --- self-contained page (no external refs; headline + struct present) ---
    page = render_gate_html()
    checks["page_self_contained"] = ("http://" not in page and "https://" not in page
                                     and "src=" not in page)
    checks["page_carries_headline"] = (GOVERNED_HEADLINE in page)
    checks["page_shows_frozen_structure"] = (FROZEN_COPULA_STRUCTURE in page)
    checks["page_blocks_run_by_default"] = ('id="btn-run" disabled' in page)

    n_pass = sum(1 for v in checks.values() if v)
    return {"ok": all(checks.values()), "n_checks": len(checks),
            "n_pass": n_pass, "checks": checks}
