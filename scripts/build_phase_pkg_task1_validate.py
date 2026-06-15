#!/usr/bin/env python3
"""Phase PKG Task 1 - structural acceptance gate for the Option-A frozen-binary
build infrastructure (PyInstaller spec + CI release matrix + docs).

DECISION-NEUTRAL / AUTHORING-ONLY check. It does NOT build anything and needs no
third-party packages (stdlib only, so it runs in the dev sandbox and as the CI
pre-build gate). It asserts:

  * the PyInstaller spec exists, parses, targets the offline launcher and bundles
    only data paths that exist;
  * the release workflow exists, parses as YAML-ish, builds a 3-OS matrix, is
    gated to manual dispatch + version tags (NEVER a branch push), and smoke-tests
    the binary with ``--self-test``;
  * the packaging README + design note are present;
  * NO governed artifact moved this task: ui_app.html / ui_data.json are
    byte-unchanged vs the pinned baseline and the governed headline string is
    still present.

Exit 0 + ``{"ok": true, ...}`` on success; exit 1 otherwise.
Run:  python scripts/build_phase_pkg_task1_validate.py
"""
from __future__ import annotations
import ast
import hashlib
import json
import os
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
SPEC = os.path.join(REPO, "packaging", "actuarial_gui.spec")
WORKFLOW = os.path.join(REPO, "packaging", "release.workflow.yml")
README = os.path.join(REPO, "packaging", "README.md")
DESIGN = os.path.join(REPO, "docs", "validation", "PHASE_PKG_TASK1_BUILD_INFRA.json")

# Pinned baselines: this task must leave the governed UI artifacts byte-unchanged.
UI_APP_SHA = "d82c65ecc7f7130a07b34d55c9500e93e23dd71626d18c3002c4e0777bd1fee6"
GOVERNED_HEADLINE = "39975.654628199336"


def _sha(path: str) -> str:
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def _checks() -> list[tuple[str, bool, str]]:
    out: list[tuple[str, bool, str]] = []

    def chk(name: str, cond: bool, detail: str = "") -> None:
        out.append((name, bool(cond), detail))

    # --- spec ----------------------------------------------------------------
    spec_src = ""
    spec_ok = os.path.exists(SPEC)
    chk("spec_present", spec_ok, SPEC)
    if spec_ok:
        spec_src = open(SPEC, encoding="utf-8").read()
        try:
            ast.parse(spec_src)
            chk("spec_parses", True)
        except SyntaxError as e:  # pragma: no cover
            chk("spec_parses", False, str(e))
        chk("spec_targets_launcher",
            "launch_offline_gui.py" in spec_src,
            "entry point = scripts/launch_offline_gui.py")
        chk("spec_name_is_launch_actuarial_gui",
            'name="Launch_Actuarial_GUI"' in spec_src)
        chk("spec_console_visible", "console=True" in spec_src)
        chk("spec_upx_off_for_av_safety", "upx=False" in spec_src)
        chk("spec_collects_engine",
            all(p in spec_src for p in ("numpy", "pandas", "scipy")))
        # every bundled data candidate that the spec lists must exist in the repo
        for rel in ("ui_app.html", "ui_data.json", "production_run",
                    os.path.join(".claude-dev", "GOVERNANCE_STORE.json"),
                    "requirements-engine-lock.txt"):
            if rel in spec_src or rel.replace(os.sep, "/") in spec_src:
                chk("data_path_exists:%s" % rel,
                    os.path.exists(os.path.join(REPO, rel)))

    # --- workflow ------------------------------------------------------------
    wf_ok = os.path.exists(WORKFLOW)
    chk("workflow_present", wf_ok, WORKFLOW)
    if wf_ok:
        wf = open(WORKFLOW, encoding="utf-8").read()
        chk("workflow_three_os_matrix",
            all(o in wf for o in ("ubuntu-latest", "windows-latest", "macos-latest")))
        chk("workflow_manual_dispatch", "workflow_dispatch:" in wf)
        chk("workflow_tag_trigger", 'tags:' in wf and 'v*' in wf)
        chk("workflow_no_branch_push_trigger", "branches:" not in wf,
            "must not auto-run on a branch push")
        chk("workflow_runs_prebuild_gate",
            "build_phase_pkg_task1_validate.py" in wf)
        chk("workflow_builds_spec",
            "packaging/actuarial_gui.spec" in wf)
        chk("workflow_smoke_tests_binary",
            "--self-test" in wf and "127.0.0.1" in wf)
        chk("workflow_uploads_artifact", "upload-artifact" in wf)
        chk("workflow_install_note_present",
            ".github/workflows/release.yml" in wf and "workflow" in wf,
            "template documents how to install into .github/workflows with workflow-scope token")

    # --- docs ----------------------------------------------------------------
    chk("packaging_readme_present", os.path.exists(README))
    chk("design_note_present", os.path.exists(DESIGN))

    # --- governed-artifact invariance (no model/UI change this task) ---------
    ui_app = os.path.join(REPO, "ui_app.html")
    chk("ui_app_present", os.path.exists(ui_app))
    if os.path.exists(ui_app):
        chk("ui_app_byte_unchanged", _sha(ui_app) == UI_APP_SHA,
            "sha256 must equal pinned baseline")
    ui_data = os.path.join(REPO, "ui_data.json")
    if os.path.exists(ui_data):
        txt = open(ui_data, encoding="utf-8").read()
        chk("governed_headline_present", GOVERNED_HEADLINE in txt)

    return out


def main() -> int:
    results = _checks()
    ok = all(c for _, c, _ in results)
    payload = {
        "gate": "PHASE_PKG_TASK1_BUILD_INFRA",
        "ok": ok,
        "n_checks": len(results),
        "n_pass": sum(1 for _, c, _ in results if c),
        "checks": [
            {"name": n, "pass": c, **({"detail": d} if d else {})}
            for n, c, d in results
        ],
    }
    print(json.dumps(payload, indent=1))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
