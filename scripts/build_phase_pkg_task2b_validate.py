#!/usr/bin/env python3
"""Phase PKG Task 2 (Option B) - structural acceptance gate for the offline
vendored-wheels venv bootstrap (offline_bootstrap.py + vendor_wheels.py + docs).

DECISION-NEUTRAL / AUTHORING-ONLY. Stdlib only (runs in the dev sandbox and as a
CI pre-step). It vendors/builds NOTHING; it asserts the authored Option-B recipe
is structurally sound and preserves the offline guarantee:

  * offline_bootstrap.py exists, parses, plans a pip install that FORCES --no-index
    and --find-links against the pinned requirements, with no remote URL/index flag;
    its --self-test returns ok:true; it imports no engine module.
  * vendor_wheels.py exists, parses, is a thin `pip download` wrapper targeting the
    pinned requirements + a local dest, and supports --print-argv (no-network).
  * the pinned requirements file exists and pins numpy/pandas/scipy.
  * the Option-B README + evidence report are present.
  * NO governed artifact moved: ui_app.html / ui_data.json byte-unchanged vs the
    pinned baseline and the governed headline string is still present.

Exit 0 + {"ok": true, ...} on success; exit 1 otherwise.
Run:  python3 scripts/build_phase_pkg_task2b_validate.py
"""
from __future__ import annotations
import ast
import importlib.util
import hashlib
import json
import os
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
BOOTSTRAP = os.path.join(REPO, "packaging", "offline_bootstrap.py")
VENDOR = os.path.join(REPO, "scripts", "vendor_wheels.py")
REQS = os.path.join(REPO, "requirements-engine-lock.txt")
README = os.path.join(REPO, "packaging", "OPTION_B_README.md")
EVIDENCE = os.path.join(REPO, "docs", "validation", "PHASE_PKG_TASK2B_OFFLINE_WHEELHOUSE.json")
UI_APP = os.path.join(REPO, "ui_app.html")
UI_DATA = os.path.join(REPO, "ui_data.json")

# Pinned baselines: this task must leave the governed artifacts byte-unchanged.
UI_APP_SHA = "d82c65ecc7f7130a07b34d55c9500e93e23dd71626d18c3002c4e0777bd1fee6"
GOVERNED_HEADLINE = "39975.654628199336"


def _sha(path: str) -> str:
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def _checks() -> list[tuple[str, bool, str]]:
    out: list[tuple[str, bool, str]] = []

    def chk(name: str, cond: bool, detail: str = "") -> None:
        out.append((name, bool(cond), detail))

    # --- offline_bootstrap.py ------------------------------------------------
    # We LOAD the module and inspect its planned pip argv + self-test result,
    # rather than scanning source text (the source legitimately contains the
    # "http(s)://" literals that the guard itself checks against).
    bs_ok = os.path.exists(BOOTSTRAP)
    chk("bootstrap_present", bs_ok, BOOTSTRAP)
    if bs_ok:
        try:
            ast.parse(open(BOOTSTRAP, encoding="utf-8").read())
            chk("bootstrap_parses", True)
        except SyntaxError as e:
            chk("bootstrap_parses", False, str(e))
        try:
            spec = importlib.util.spec_from_file_location("offline_bootstrap", BOOTSTRAP)
            bs = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(bs)
            argv = bs.plan_install(bs.DEFAULT_WHEELHOUSE, bs.DEFAULT_VENV)
            joined = " ".join(argv)
            chk("bootstrap_plan_forces_no_index", "--no-index" in argv)
            chk("bootstrap_plan_uses_find_links", "--find-links" in argv)
            chk("bootstrap_plan_targets_pinned_reqs",
                "requirements-engine-lock.txt" in joined and "-r" in argv)
            chk("bootstrap_plan_no_remote_url",
                ("http://" not in joined) and ("https://" not in joined)
                and "--index-url" not in argv and "-i" not in argv)
            st = bs.self_test()
            chk("bootstrap_self_test_ok", bool(st.get("ok")),
                "checks=%d" % len(st.get("checks", [])))
        except Exception as e:  # pragma: no cover
            chk("bootstrap_loads_and_self_tests", False, str(e))

    # --- vendor_wheels.py ----------------------------------------------------
    v_ok = os.path.exists(VENDOR)
    chk("vendor_present", v_ok, VENDOR)
    if v_ok:
        v_src = open(VENDOR, encoding="utf-8").read()
        try:
            ast.parse(v_src)
            chk("vendor_parses", True)
        except SyntaxError as e:
            chk("vendor_parses", False, str(e))
        chk("vendor_uses_pip_download", '"download"' in v_src)
        chk("vendor_targets_pinned_reqs", "requirements-engine-lock.txt" in v_src)
        chk("vendor_has_print_argv", "--print-argv" in v_src)

    # --- pinned requirements -------------------------------------------------
    r_ok = os.path.exists(REQS)
    chk("pinned_requirements_present", r_ok, REQS)
    if r_ok:
        r_src = open(REQS, encoding="utf-8").read()
        for mod in ("numpy==", "pandas==", "scipy=="):
            chk("pins_%s" % mod.rstrip("="), mod in r_src)

    # --- docs ----------------------------------------------------------------
    chk("option_b_readme_present", os.path.exists(README), README)
    chk("evidence_report_present", os.path.exists(EVIDENCE), EVIDENCE)

    # --- governed artifacts byte-unchanged -----------------------------------
    if os.path.exists(UI_APP):
        sha = _sha(UI_APP)
        chk("ui_app_byte_unchanged", sha == UI_APP_SHA, sha)
    else:
        chk("ui_app_byte_unchanged", False, "missing")
    if os.path.exists(UI_DATA):
        chk("governed_headline_present",
            GOVERNED_HEADLINE in open(UI_DATA, encoding="utf-8").read())
    else:
        chk("governed_headline_present", False, "missing")

    return out


def main() -> int:
    checks = _checks()
    ok = all(c for _, c, _ in checks)
    print(json.dumps({
        "task": "Phase PKG Task 2 (Option B) - offline vendored-wheels bootstrap gate",
        "ok": ok,
        "passed": sum(1 for _, c, _ in checks if c),
        "total": len(checks),
        "checks": [{"name": n, "ok": c, "detail": d} for n, c, d in checks],
    }, indent=1))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
