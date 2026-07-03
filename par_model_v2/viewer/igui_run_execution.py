"""Phase IGUI Task 7 - end-to-end run + results handoff (Phase IGUI MVP).

This is the LAST input+run-GUI domain. Tasks 2-5 collect every input domain into
the loader's ``model_inputs.json`` schema; Task 6 (``igui_validation_gating``)
SURFACES validation and records a governance RUN GATE (CLEARED only when every
domain is present AND clean) plus a deterministic run-level reproducibility
digest. Task 7 is the piece that finally RUNS THE MODEL end-to-end and hands the
result to the existing zero-install RESULTS UI:

    gated model_inputs.json  (run_gate CLEARED, Task 6)
        -> scripts/run_model.py  (the governed seven-driver orchestrator)
            -> docs/validation/RUN_MODEL_AGGREGATION_REPORT.json + RUN_MODEL_SUMMARY.json
                -> the offline RESULTS UI (ui_app.html) user_run contract
                   (consumed by scripts/build_ui_data._build_user_run, VERBATIM)

Design / discipline (unchanged from Tasks 2-6):
  * This module is STANDARD-LIBRARY ONLY (``subprocess``/``json``/``hashlib`` ...).
    It NEVER imports numpy/scipy/pandas; it DRIVES ``scripts/run_model.py`` as a
    child process, so the GUI/runner layer keeps zero third-party runtime deps
    while the model engine (which legitimately needs numpy/scipy) runs out of
    process. The runner stays localhost-only and makes no outbound network call.
  * A run is REFUSED unless the assembled ``model_inputs.json`` carries a Task-6
    ``run_gate`` with ``decision == CLEARED`` / ``run_permitted == True`` AND the
    gate's reproducibility digest re-verifies against the live inputs. A BLOCKED
    or missing or tampered gate NEVER spawns the model.
  * The Task-6 run-gate reproducibility digest is CARRIED INTO THE OUTPUT
    PROVENANCE (a ``run_gate_provenance`` block stamped onto the captured
    RUN_MODEL artifacts), so every produced result is traceable back to the exact
    gated input set that authorised it.
  * The zero-install RESULTS UI (``ui_app.html``) is BYTE-UNCHANGED: this module
    only writes RUN_MODEL_*.json into the caller-chosen output dir and shapes the
    user_run handoff that the UI already consumes; it never edits ui_app.html and
    changes NO model parameter. The governed headline SCR is echoed bit-for-bit;
    the frozen copula structure (Phase 30 stop-rule) is echoed read-only; the
    MR-016/MR-017 owner decision is not pre-empted.
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import html as _html
import json
import os
import subprocess
import sys
import tempfile
from typing import Any, Dict, List, Optional, Tuple

from par_model_v2.viewer.igui_validation_gating import (
    DOMAINS,
    FROZEN_COPULA_STRUCTURE,
    GOVERNED_HEADLINE,
    SCHEMA_VERSION,
    UI_APP_SHA256,
    run_reproducibility_digest,
)

DOC_ID = "PHASE_IGUI_TASK7_RUN_EXECUTION"
DOC_VERSION = "1.0.0"

#: The two artifacts the governed orchestrator writes and the offline RESULTS UI
#: (build_ui_data._build_user_run) consumes VERBATIM.
AGG_REPORT_NAME = "RUN_MODEL_AGGREGATION_REPORT.json"
SUMMARY_NAME = "RUN_MODEL_SUMMARY.json"

#: A small, FAST smoke configuration (used by self-tests + the Task-7 gate). It is
#: deliberately far below the governed config; a smoke run is DISCLOSED as a
#: smoke run in the output provenance and is never a governed capital result.
SMOKE_OVERRIDES = {
    "n_outer": 100,      # orchestrator floor is 100
    "n_inner": 2,
    "n_sim": 2000,
    "bootstrap_replicates": 50,  # orchestrator floor is 50
    "no_tail": True,
}

#: Forbidden third-party runtime imports (this layer must stay stdlib-only; the
#: model engine deps live behind the run_model.py subprocess boundary).
FORBIDDEN_RUNTIME_IMPORTS = ("numpy", "scipy", "pandas", "openpyxl")

#: Resolve the repo root from this file (…/par_model_v2/viewer/igui_run_execution.py).
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# --------------------------------------------------------------------------
# (a) gate verification -- a run is REFUSED unless Task-6 cleared it
# --------------------------------------------------------------------------
def verify_run_gate(model_inputs: Dict[str, Any]) -> Dict[str, Any]:
    """Verify the assembled inputs carry a Task-6 run gate that PERMITS a run.

    Returns ``{"ok": bool, "reasons": [...], "reproducibility_digest": str|None,
    "decision": str|None}``. ``ok`` is True only when the gate exists, its
    decision is CLEARED, ``run_permitted`` is True, its schema_version matches and
    its reproducibility digest re-verifies against the live inputs (so a gate
    cannot be lifted off a different/altered input set). NEVER raises; a caller
    refuses to spawn the model whenever ``ok`` is False.
    """
    reasons: List[str] = []
    if not isinstance(model_inputs, dict):
        return {"ok": False, "reasons": ["model_inputs is not a JSON object"],
                "reproducibility_digest": None, "decision": None}
    gate = model_inputs.get("run_gate")
    if not isinstance(gate, dict):
        return {"ok": False,
                "reasons": ["no run_gate present - run validation/gating (Task 6) first"],
                "reproducibility_digest": None, "decision": None}
    decision = gate.get("decision")
    if decision != "CLEARED":
        reasons.append("run_gate.decision is %r (need CLEARED)" % decision)
    if gate.get("run_permitted") is not True:
        reasons.append("run_gate.run_permitted is not True")
    if gate.get("schema_version") != SCHEMA_VERSION:
        reasons.append("run_gate.schema_version %r != loader %r"
                       % (gate.get("schema_version"), SCHEMA_VERSION))
    stored = gate.get("reproducibility_digest")
    live = run_reproducibility_digest(model_inputs)
    if not (isinstance(stored, str) and stored == live):
        reasons.append("run_gate.reproducibility_digest does not match the live "
                       "inputs (gate was recorded for a different/altered input set)")
    # every domain must still be present + clean in the recorded gate summary
    gate_domains = gate.get("domains") or {}
    for d in DOMAINS:
        info = gate_domains.get(d) or {}
        if not (info.get("present") and info.get("ok")):
            reasons.append("run_gate domain %r is not present+clean" % d)
    return {"ok": not reasons, "reasons": reasons,
            "reproducibility_digest": live, "decision": decision}


# --------------------------------------------------------------------------
# (b) build the run_model.py command from the gated inputs
# --------------------------------------------------------------------------
def build_run_command(inputs_path: str, out_dir: str, *,
                      smoke: bool = False,
                      python_exe: Optional[str] = None,
                      repo_root: Optional[str] = None) -> List[str]:
    """Assemble the argv that drives ``scripts/run_model.py`` against the gated
    ``inputs_path`` writing into ``out_dir``. run_model itself reads the Run
    Settings (n_outer/n_inner/n_sim/seed/...) out of model_inputs.json, so the
    base command passes only ``--inputs``/``--out``; ``smoke=True`` overlays the
    small SMOKE_OVERRIDES for tests / the Task-7 gate. No model parameter is set
    here - every figure still comes from the governed engine."""
    root = repo_root or _REPO_ROOT
    runner = os.path.join(root, "scripts", "run_model.py")
    cmd = [python_exe or sys.executable, runner,
           "--inputs", inputs_path, "--out", out_dir]
    if smoke:
        cmd += ["--n-outer", str(SMOKE_OVERRIDES["n_outer"]),
                "--n-inner", str(SMOKE_OVERRIDES["n_inner"]),
                "--n-sim", str(SMOKE_OVERRIDES["n_sim"]),
                "--bootstrap-replicates", str(SMOKE_OVERRIDES["bootstrap_replicates"])]
        if SMOKE_OVERRIDES.get("no_tail"):
            cmd += ["--no-tail"]
    return cmd


# --------------------------------------------------------------------------
# (c) carry the Task-6 digest into the captured output provenance
# --------------------------------------------------------------------------
def _run_gate_provenance(model_inputs: Dict[str, Any], gate_check: Dict[str, Any],
                         *, smoke: bool, now: Optional[str] = None) -> Dict[str, Any]:
    """The provenance block stamped onto every captured run artifact: it carries
    the Task-6 run-gate reproducibility digest + decision so a produced result is
    traceable to the exact gated input set that authorised it."""
    gate = model_inputs.get("run_gate") or {}
    return {
        "record_type": "RUN_GATE_PROVENANCE",
        "doc_id": DOC_ID,
        "doc_version": DOC_VERSION,
        "stamped_at": now or _dt.datetime.now(_dt.timezone.utc).isoformat(),
        "gate_decision": gate.get("decision"),
        "run_permitted": gate.get("run_permitted"),
        "reproducibility_digest": gate_check.get("reproducibility_digest"),
        "schema_version": SCHEMA_VERSION,
        "governed_headline": GOVERNED_HEADLINE,
        "frozen_copula_structure": FROZEN_COPULA_STRUCTURE,
        "smoke_run": bool(smoke),
        "ui_app_sha256": UI_APP_SHA256,
        "note": ("Result produced by Phase IGUI Task 7 end-to-end run; carried "
                 "VERBATIM into the offline RESULTS UI user_run contract. A "
                 "smoke_run=true result is a fast diagnostic, NOT a governed "
                 "capital figure."),
    }


def _stamp_provenance(path: str, provenance: Dict[str, Any]) -> None:
    """Augment a captured RUN_MODEL artifact in-place with the run-gate provenance
    (additive top-level ``run_gate_provenance`` key), with a re-parse guard so a
    corrupt file is never handed downstream."""
    with open(path, encoding="utf-8") as fh:
        obj = json.load(fh)
    obj["run_gate_provenance"] = provenance
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=1, default=str)
    with open(path, encoding="utf-8") as fh:
        json.load(fh)  # re-parse guard


# --------------------------------------------------------------------------
# (d) the end-to-end driver
# --------------------------------------------------------------------------
def execute_run(inputs_path: str, out_dir: str, *,
                smoke: bool = False,
                python_exe: Optional[str] = None,
                repo_root: Optional[str] = None,
                env: Optional[Dict[str, str]] = None,
                timeout: Optional[float] = 1800.0) -> Dict[str, Any]:
    """Drive the governed model end-to-end from a GATED ``model_inputs.json``.

    Steps: (1) read+parse the inputs (fail loud); (2) verify the Task-6 run gate
    PERMITS a run - if not, REFUSE and spawn nothing; (3) run scripts/run_model.py
    as a child process capturing stdout/stderr as progress; (4) read back the two
    RUN_MODEL artifacts and stamp the run-gate provenance (digest) onto each;
    (5) shape the user_run handoff the offline RESULTS UI consumes. Returns a
    structured result with a ``stage`` that says exactly where it stopped. NEVER
    raises for an expected failure (blocked gate, child error, missing artifact);
    it returns ``ok: False`` with progress + reasons so the GUI can surface it."""
    root = repo_root or _REPO_ROOT
    progress: List[str] = []

    # (1) read + parse
    if not os.path.exists(inputs_path):
        return {"ok": False, "stage": "inputs_missing",
                "errors": ["model_inputs.json not found: %s" % inputs_path],
                "progress": progress}
    try:
        with open(inputs_path, encoding="utf-8") as fh:
            model_inputs = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        return {"ok": False, "stage": "inputs_unreadable",
                "errors": ["could not parse model_inputs.json: %s" % exc],
                "progress": progress}
    progress.append("loaded gated inputs: %s" % os.path.abspath(inputs_path))

    # (2) GATE: refuse unless Task-6 cleared this exact input set
    gate_check = verify_run_gate(model_inputs)
    if not gate_check["ok"]:
        progress.append("RUN REFUSED - run gate does not permit a run")
        return {"ok": False, "stage": "run_gate_not_cleared",
                "errors": gate_check["reasons"], "gate": gate_check,
                "progress": progress}
    progress.append("run gate CLEARED (digest %s) - authorising run"
                    % (gate_check["reproducibility_digest"] or "")[:23])

    # (3) drive run_model.py out of process
    os.makedirs(out_dir, exist_ok=True)
    cmd = build_run_command(inputs_path, out_dir, smoke=smoke,
                            python_exe=python_exe, repo_root=root)
    run_env = dict(os.environ if env is None else env)
    # ensure the child can import the package (repo root on PYTHONPATH)
    existing = run_env.get("PYTHONPATH", "")
    run_env["PYTHONPATH"] = root + (os.pathsep + existing if existing else "")
    progress.append("executing: %s" % " ".join(
        os.path.basename(c) if c.endswith(".py") else c for c in cmd))
    try:
        proc = subprocess.run(cmd, cwd=root, env=run_env, timeout=timeout,
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                              universal_newlines=True)
    except subprocess.TimeoutExpired:
        return {"ok": False, "stage": "run_timeout",
                "errors": ["run_model.py exceeded %ss" % timeout],
                "progress": progress}
    except OSError as exc:
        return {"ok": False, "stage": "run_spawn_error",
                "errors": ["could not start run_model.py: %s" % exc],
                "progress": progress}
    for line in (proc.stdout or "").splitlines():
        if line.strip():
            progress.append(line.rstrip())
    if proc.returncode != 0:
        return {"ok": False, "stage": "run_failed",
                "errors": ["run_model.py exited %d (see progress)" % proc.returncode],
                "returncode": proc.returncode, "progress": progress}
    progress.append("run_model.py completed (exit 0)")

    # (4) capture artifacts + stamp run-gate provenance (carry the digest)
    summary_path = os.path.join(out_dir, SUMMARY_NAME)
    report_path = os.path.join(out_dir, AGG_REPORT_NAME)
    for p in (summary_path, report_path):
        if not os.path.exists(p):
            return {"ok": False, "stage": "artifact_missing",
                    "errors": ["expected run artifact not found: %s" % p],
                    "progress": progress}
    provenance = _run_gate_provenance(model_inputs, gate_check, smoke=smoke)
    _stamp_provenance(summary_path, provenance)
    _stamp_provenance(report_path, provenance)
    progress.append("stamped run-gate provenance (digest carried into output)")

    # (5) shape the offline RESULTS-UI handoff
    handoff = build_results_handoff(out_dir, provenance)
    progress.append("results handoff ready for offline RESULTS UI (user_run contract)")
    return {"ok": True, "stage": "run_complete", "smoke": bool(smoke),
            "out_dir": os.path.abspath(out_dir),
            "summary_path": os.path.abspath(summary_path),
            "report_path": os.path.abspath(report_path),
            "reproducibility_digest": gate_check["reproducibility_digest"],
            "headline": handoff.get("headline"), "verdict": handoff.get("verdict"),
            "handoff": handoff, "progress": progress}


# --------------------------------------------------------------------------
# (e) the offline RESULTS-UI handoff (user_run contract)
# --------------------------------------------------------------------------
def build_results_handoff(out_dir: str, provenance: Dict[str, Any]) -> Dict[str, Any]:
    """Shape the run result into the SAME ``user_run`` contract the offline
    RESULTS UI already consumes (``scripts/build_ui_data._build_user_run`` reads
    RUN_MODEL_SUMMARY.json + RUN_MODEL_AGGREGATION_REPORT.json VERBATIM). This is
    the hand-off object: it carries the headline / bootstrap CI / run plan / input
    provenance bit-for-bit from the captured artifacts PLUS the run-gate
    reproducibility digest, and points at the two on-disk artifacts the UI reads.
    It does NOT modify ui_app.html (the UI stays byte-unchanged); a real user
    refreshes their offline UI by pointing build_ui_data at these artifacts."""
    summary_path = os.path.join(out_dir, SUMMARY_NAME)
    report_path = os.path.join(out_dir, AGG_REPORT_NAME)
    summ: Dict[str, Any] = {}
    rep: Dict[str, Any] = {}
    try:
        with open(summary_path, encoding="utf-8") as fh:
            summ = json.load(fh)
    except (OSError, json.JSONDecodeError):
        summ = {}
    try:
        with open(report_path, encoding="utf-8") as fh:
            rep = json.load(fh)
    except (OSError, json.JSONDecodeError):
        rep = {}
    user_run: Dict[str, Any] = {}
    for key in ("run_timestamp", "output_label", "currency", "inputs", "headline",
                "bootstrap_ci", "verdict", "duration_seconds", "evidence",
                "wall_clock_seconds"):
        if key in summ:
            user_run[key] = summ[key]
    for key in ("run_plan", "inputs_provenance", "use_restrictions"):
        if isinstance(rep.get(key), dict):
            user_run[key] = rep[key]
    user_run["run_gate_provenance"] = provenance
    user_run["reproducibility_digest"] = provenance.get("reproducibility_digest")
    user_run["source"] = "docs/validation/RUN_MODEL_SUMMARY.json"
    user_run["evidence_source"] = "docs/validation/RUN_MODEL_AGGREGATION_REPORT.json"
    return {
        "ok": bool(user_run.get("headline")),
        "user_run": user_run,
        "headline": user_run.get("headline"),
        "verdict": user_run.get("verdict"),
        "artifacts": {
            "summary": os.path.abspath(summary_path),
            "aggregation_report": os.path.abspath(report_path),
        },
        "consumes": ("scripts/build_ui_data._build_user_run -> ui_data.json.user_run "
                     "-> ui_app.html (offline RESULTS UI, byte-unchanged)"),
        "reproducibility_digest": provenance.get("reproducibility_digest"),
    }


# --------------------------------------------------------------------------
# (f) the self-contained run page (GET /run-execution)
# --------------------------------------------------------------------------
def render_run_html() -> str:
    """A self-contained (zero external reference) end-to-end RUN page for the
    input+run GUI. It explains the gate-then-run flow, exposes a Run button that
    is DISABLED until the gate clears, surfaces live progress + errors from
    ``POST /execute``, and renders the headline read-outs after a run. The
    governed headline + frozen copula structure are shown read-only. No CDN, no
    inline remote ``src``; pure localhost."""
    gov = _html.escape(GOVERNED_HEADLINE)
    frozen = _html.escape(FROZEN_COPULA_STRUCTURE)
    return """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Run model end-to-end - Phase IGUI Task 7</title>
<style>
 body{font:14px/1.5 system-ui,Segoe UI,Arial,sans-serif;margin:0;background:#0f1115;color:#e8eaed}
 main{max-width:880px;margin:0 auto;padding:24px}
 h1{font-size:20px;margin:0 0 4px} h2{font-size:15px;margin:20px 0 8px;color:#9fb4ff}
 .card{background:#171a21;border:1px solid #262b36;border-radius:10px;padding:16px;margin:12px 0}
 .muted{color:#9aa3b2} .mono{font-family:ui-monospace,Consolas,monospace}
 button{font:inherit;padding:9px 16px;border-radius:8px;border:1px solid #2b6cff;background:#2b6cff;color:#fff;cursor:pointer}
 button:disabled{background:#33384a;border-color:#33384a;color:#7b8499;cursor:not-allowed;opacity:.7}
 button.secondary{background:transparent;color:#9fb4ff}
 pre{background:#0b0d12;border:1px solid #20242e;border-radius:8px;padding:12px;white-space:pre-wrap;max-height:320px;overflow:auto}
 .ok{color:#36d399} .bad{color:#f87272} .pill{display:inline-block;padding:2px 8px;border-radius:999px;font-size:12px;border:1px solid #394150}
 table{border-collapse:collapse;width:100%} td,th{border-bottom:1px solid #262b36;padding:6px 8px;text-align:left}
 label.cb{display:flex;gap:8px;align-items:center;margin:8px 0}
</style></head><body><main>
 <h1>Run the model end-to-end</h1>
 <div class="muted">Phase IGUI Task 7 - the input+run GUI MVP. Inputs &rarr; <span class="mono">model_inputs.json</span>
  &rarr; <span class="mono">scripts/run_model.py</span> &rarr; offline RESULTS UI (<span class="mono">ui_app.html</span>, byte-unchanged).</div>

 <div class="card">
  <h2>1 &middot; Validation &amp; run gate</h2>
  <div class="muted">A run is <b>blocked</b> until the assembled inputs are clean across every domain
   (run controls, model points, assumptions, ESG) and the Task-6 gate is <b>CLEARED</b>.</div>
  <p><button id="btn-preflight" class="secondary" type="button">Re-check gate</button>
     <span id="gate-status" class="pill">gate: unknown</span></p>
 </div>

 <div class="card">
  <h2>2 &middot; Execute</h2>
  <label class="cb"><input type="checkbox" id="smoke" checked> Fast smoke run (diagnostic; not a governed capital figure)</label>
  <p><button id="btn-run" type="button" disabled>Run model end-to-end</button>
     <span id="run-status" class="muted"></span></p>
  <h2>Progress</h2>
  <pre id="progress" class="mono">(idle)</pre>
 </div>

 <div class="card" id="result-card" style="display:none">
  <h2>3 &middot; Result &rarr; offline RESULTS UI</h2>
  <div class="muted">Headline read-outs (carried bit-for-bit from <span class="mono">RUN_MODEL_SUMMARY.json</span>).
   The result flows into the offline RESULTS UI via its existing <span class="mono">user_run</span> contract.</div>
  <table id="headline"></table>
  <p class="muted">Reproducibility digest: <span id="digest" class="mono">--</span></p>
 </div>

 <div class="card">
  <div class="muted">Governed headline SCR (read-only, bit-for-bit): <span class="mono">""" + gov + """</span></div>
  <div class="muted">Frozen dependence structure (Phase 30 stop-rule, read-only): <span class="mono">""" + frozen + """</span></div>
 </div>

<script>
"use strict";
var $=function(id){return document.getElementById(id);};
function post(path,body){return fetch(path,{method:"POST",headers:{"Content-Type":"application/json"},
  body:JSON.stringify(body||{})}).then(function(r){return r.json();});}
function setGate(ok,txt){var g=$("gate-status");g.textContent="gate: "+txt;
  g.className="pill "+(ok?"ok":"bad");$("btn-run").disabled=!ok;}
function preflight(){return post("/preflight",{}).then(function(j){
  var ok=!!(j&&j.ok);setGate(ok,ok?"CLEARED":"BLOCKED");return ok;
}).catch(function(){setGate(false,"error");return false;});}
function renderHeadline(h,digest){var t=$("headline");t.innerHTML="";
  if(h){var rows=[["Nested SCR",h.nested_scr],["Selected copula",h.copula_selected],
    ["Copula SCR",h.copula_scr],["Var-covar SCR",h.var_covar_scr]];
    rows.forEach(function(r){var tr=document.createElement("tr");
      tr.innerHTML="<th>"+r[0]+"</th><td class='mono'>"+(r[1]==null?"--":r[1])+"</td>";t.appendChild(tr);});}
  $("digest").textContent=digest||"--";$("result-card").style.display="block";}
function finish(j){var r=(j&&j.result)||{};
  $("progress").textContent=((j&&j.progress)||[]).join("\\n")||"(no output)";
  if(j&&j.state==="succeeded"&&r.ok){$("run-status").innerHTML="<span class='ok'>complete</span>";
    renderHeadline(r.headline,r.reproducibility_digest);}
  else{$("run-status").innerHTML="<span class='bad'>"+((j&&j.error)||(r&&r.stage)||"failed")+"</span>";}
  return preflight();}
function poll(id){fetch("/jobs/"+id).then(function(r){return r.json();}).then(function(j){
  if(j&&j.progress){$("progress").textContent=j.progress.join("\\n");}
  if(j&&(j.state==="succeeded"||j.state==="failed")){finish(j);}
  else{setTimeout(function(){poll(id);},2000);}
}).catch(function(){setTimeout(function(){poll(id);},4000);});}
function run(){$("btn-run").disabled=true;$("run-status").textContent="submitting...";
  $("progress").textContent="(starting)";
  post("/execute-async",{smoke:$("smoke").checked}).then(function(j){
    if(j&&j.ok&&j.job_id){$("run-status").textContent="job "+j.job_id+" running (page stays live; progress refreshes every 2s)";
      poll(j.job_id);}
    else{$("run-status").innerHTML="<span class='bad'>"+((j&&j.error)||"submit failed")+"</span>";
      $("btn-run").disabled=false;}
  }).catch(function(e){$("run-status").innerHTML="<span class='bad'>error</span>";
    $("progress").textContent=String(e);$("btn-run").disabled=false;});}
$("btn-preflight").addEventListener("click",preflight);
$("btn-run").addEventListener("click",run);
preflight();
</script>
</main></body></html>"""


# --------------------------------------------------------------------------
# (g) static-source guard + pre-registered Task-7 gate (mirrors Task 6)
# --------------------------------------------------------------------------
def _source_has_forbidden_import(path: str) -> bool:
    import re
    if not os.path.exists(path):
        return True
    with open(path, encoding="utf-8") as fh:
        src = fh.read()
    for mod in FORBIDDEN_RUNTIME_IMPORTS:
        if re.search(r'^\s*(?:import|from)\s+%s\b' % re.escape(mod), src, re.MULTILINE):
            return True
    return False


def _clean_gated_inputs() -> Dict[str, Any]:
    """A fully-populated, valid, GATED assembled inputs dict (every domain clean +
    a CLEARED Task-6 run_gate), used by the gate + tests to drive a real run."""
    from par_model_v2.viewer.igui_validation_gating import (
        _clean_assembled_inputs, aggregate_validation, build_run_gate)
    import sys as _sys
    for p in (_REPO_ROOT, os.path.join(_REPO_ROOT, "scripts")):
        if p not in _sys.path:
            _sys.path.insert(0, p)
    import load_user_inputs as _lui  # noqa: E402
    mi = _clean_assembled_inputs()
    v = aggregate_validation(mi, _lui)
    mi["run_gate"] = build_run_gate(mi, v)
    return mi


def validate_task7_gate(repo_root: str = ".", *, run_live: bool = True) -> Dict[str, Any]:
    """Pre-registered Task-7 acceptance checks: structural plumbing + (when
    ``run_live``) a real end-to-end SMOKE run that proves the gate-then-run-then-
    handoff chain, with the reproducibility digest carried into the output and the
    offline RESULTS UI byte-unchanged."""
    checks: Dict[str, bool] = {}
    this_mod = os.path.join(repo_root, "par_model_v2", "viewer", "igui_run_execution.py")
    run_gui = os.path.join(repo_root, "scripts", "run_gui.py")
    run_model = os.path.join(repo_root, "scripts", "run_model.py")
    ui_app = os.path.join(repo_root, "ui_app.html")

    checks["execution_module_present"] = os.path.exists(this_mod)
    checks["run_model_present"] = os.path.exists(run_model)
    checks["execution_module_stdlib_only"] = not _source_has_forbidden_import(this_mod)

    try:
        with open(run_gui, encoding="utf-8") as fh:
            gui_src = fh.read()
        checks["run_gui_serves_run_execution"] = (
            "/run-execution" in gui_src and "render_run_html" in gui_src)
        checks["run_gui_has_execute_endpoint"] = "/execute" in gui_src
        checks["run_gui_still_localhost"] = ("127.0.0.1" in gui_src and "0.0.0.0" not in gui_src)
        checks["run_gui_prior_pages_intact"] = all(
            p in gui_src for p in ("/run-gate", "render_gate_html", "/esg",
                                   "render_esg_html", "/assumptions", "/model-points"))
    except OSError:
        for k in ("run_gui_serves_run_execution", "run_gui_has_execute_endpoint",
                  "run_gui_still_localhost", "run_gui_prior_pages_intact"):
            checks[k] = False

    # ui_app.html byte-unchanged (zero-install RESULTS UI frozen)
    try:
        with open(ui_app, "rb") as fh:
            checks["ui_app_byte_unchanged"] = (
                hashlib.sha256(fh.read()).hexdigest() == UI_APP_SHA256)
    except OSError:
        checks["ui_app_byte_unchanged"] = False

    # self-contained run page
    page = render_run_html()
    checks["run_page_self_contained"] = ("http://" not in page and "https://" not in page
                                         and "src=" not in page)
    checks["run_page_carries_headline"] = (GOVERNED_HEADLINE in page)
    checks["run_page_blocks_run_by_default"] = ('id="btn-run" type="button" disabled' in page)

    # gate verification logic: a BLOCKED / missing gate is refused
    no_gate = {"schema_version": SCHEMA_VERSION}
    checks["missing_gate_refused"] = (verify_run_gate(no_gate)["ok"] is False)
    try:
        gated = _clean_gated_inputs()
        checks["cleared_gate_accepted"] = (verify_run_gate(gated)["ok"] is True)
        tampered = json.loads(json.dumps(gated))
        tampered["run_settings"]["seed"] = int(tampered["run_settings"].get("seed", 0)) + 1
        checks["tampered_inputs_refused"] = (verify_run_gate(tampered)["ok"] is False)
    except Exception:
        checks["cleared_gate_accepted"] = False
        checks["tampered_inputs_refused"] = False

    if run_live:
        try:
            tmp = tempfile.mkdtemp(prefix="igui_task7_")
            inp = os.path.join(tmp, "model_inputs.json")
            with open(inp, "w", encoding="utf-8") as fh:
                json.dump(_clean_gated_inputs(), fh, indent=1)
            out = os.path.join(tmp, "out")
            res = execute_run(inp, out, smoke=True, repo_root=repo_root)
            checks["live_run_ok"] = bool(res.get("ok")) and res.get("stage") == "run_complete"
            checks["live_run_headline"] = bool(
                res.get("headline") and res["headline"].get("nested_scr"))
            # digest carried into the captured artifacts
            sp = os.path.join(out, SUMMARY_NAME)
            with open(sp, encoding="utf-8") as fh:
                summ = json.load(fh)
            prov = summ.get("run_gate_provenance") or {}
            checks["digest_carried_into_output"] = (
                prov.get("reproducibility_digest") == res.get("reproducibility_digest")
                and isinstance(prov.get("reproducibility_digest"), str)
                and prov["reproducibility_digest"].startswith("sha256:"))
            checks["handoff_user_run_shaped"] = bool(
                res.get("handoff", {}).get("user_run", {}).get("headline"))
            # a BLOCKED gate spawns nothing
            blocked_inp = os.path.join(tmp, "blocked.json")
            with open(blocked_inp, "w", encoding="utf-8") as fh:
                json.dump({"schema_version": SCHEMA_VERSION}, fh)
            blocked_out = os.path.join(tmp, "blocked_out")
            bres = execute_run(blocked_inp, blocked_out, smoke=True, repo_root=repo_root)
            checks["blocked_gate_runs_nothing"] = (
                bres.get("ok") is False
                and bres.get("stage") == "run_gate_not_cleared"
                and not os.path.exists(os.path.join(blocked_out, SUMMARY_NAME)))
        except Exception:
            for k in ("live_run_ok", "live_run_headline", "digest_carried_into_output",
                      "handoff_user_run_shaped", "blocked_gate_runs_nothing"):
                checks.setdefault(k, False)

    n_pass = sum(1 for v in checks.values() if v)
    return {"ok": all(checks.values()), "n_checks": len(checks),
            "n_pass": n_pass, "checks": checks}
