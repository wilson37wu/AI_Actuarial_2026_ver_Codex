"""Canonical offline-UI rebuild pipeline (contract reconciliation).

WHY THIS FILE EXISTS
--------------------
``scripts/build_ui_data.py`` is the *base* bundler: run alone it emits
``ui_data.json`` / ``ui_app.html`` at the BASE contract ``1.18.0``. The
PUBLISHED artifacts in the repo are at a HIGHER contract (currently ``1.20.0``)
because two ADDITIVE patch layers are applied on top of the base build:

    build_ui_data.py               -> contract 1.18.0  (base bundle)
    build_phase35_task2_a1_wcag    -> contract 1.19.0  (+ a11y_audit, WCAG focus)
    build_phase35_task3_a2_digests -> contract 1.20.0  (+ per-section SHA-256
                                                         section_digests)

Historically this meant a "clean rebuild" (running only ``build_ui_data.py``)
would silently REGRESS the published contract from 1.20.0 back to 1.18.0 --
the post-Phase-35 Finding (2). This module is the reconciliation: ONE canonical
command that runs the base bundler and then re-applies the additive layers in
order, reproducing the published contract from clean. It self-validates that the
layer version constants form a contiguous chain that terminates at the published
contract.

The two ``*_governance`` patch scripts (a1_governance / a2_governance) are NOT
re-run here: they are one-time governance-ledger events already recorded in
GOVERNANCE_STORE.json. Re-running them would double-count ChangeRecords. This
pipeline reconciles the *artifact* contract only; the governance ledger is
append-only and authoritative as committed.

USAGE
-----
    PYTHONPATH=. python3 scripts/build_ui_pipeline.py            # clean rebuild
    PYTHONPATH=. python3 scripts/build_ui_pipeline.py --check    # validate only
                                                                 # (no rebuild)

``--check`` does not modify any artifact: it asserts the on-disk ui_data.json is
at the published contract and the layer chain is contiguous. The default mode
performs the full rebuild in place and asserts the result reaches the published
contract.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(REPO, "scripts")
UI_DATA = os.path.join(REPO, "ui_data.json")

# Import the layer modules so the chain is derived from the SAME constants the
# patches actually apply -- no duplicated version strings to drift out of sync.
sys.path.insert(0, SCRIPTS)
import build_ui_data as _base  # noqa: E402
import build_phase35_task2_a1_wcag as _a1  # noqa: E402
import build_phase35_task3_a2_digests as _a2  # noqa: E402

BASE_CONTRACT = _base.CONTRACT_VERSION            # "1.18.0"
PUBLISHED_CONTRACT = _a2.NEW_CONTRACT             # "1.20.0"

# Ordered (script, expected-prior, expected-new) chain. Priors/news come from
# the patch modules themselves so this list cannot silently disagree with them.
LAYERS = [
    ("build_phase35_task2_a1_wcag.py", _a1.PRIOR_CONTRACT, _a1.NEW_CONTRACT),
    ("build_phase35_task3_a2_digests.py", _a2.PRIOR_CONTRACT, _a2.NEW_CONTRACT),
]


def _live_contract() -> str:
    with open(UI_DATA, encoding="utf-8") as fh:
        return json.load(fh)["contract_version"]


def validate_chain() -> dict:
    """Assert the layer chain is contiguous: base -> ... -> published.

    Raises AssertionError on any gap. Returns a summary dict.
    """
    cursor = BASE_CONTRACT
    steps = [{"script": "build_ui_data.py", "from": None, "to": BASE_CONTRACT}]
    for script, prior, new in LAYERS:
        assert prior == cursor, (
            "contract chain gap before %s: this layer expects prior %r but the "
            "running cursor is %r" % (script, prior, cursor)
        )
        steps.append({"script": script, "from": prior, "to": new})
        cursor = new
    assert cursor == PUBLISHED_CONTRACT, (
        "chain terminates at %r, expected published contract %r"
        % (cursor, PUBLISHED_CONTRACT)
    )
    return {"base": BASE_CONTRACT, "published": PUBLISHED_CONTRACT, "steps": steps}


def _run(script: str) -> None:
    env = dict(os.environ, PYTHONPATH=REPO)
    res = subprocess.run(
        [sys.executable, os.path.join(SCRIPTS, script)],
        cwd=REPO, env=env, capture_output=True, text=True,
    )
    if res.returncode != 0:
        sys.stderr.write(res.stdout + res.stderr)
        raise SystemExit("step failed: %s (exit %d)" % (script, res.returncode))


def rebuild() -> str:
    """Run base bundler + additive layers in order; return final contract."""
    _run("build_ui_data.py")
    assert _live_contract() == BASE_CONTRACT, (
        "base build produced %r, expected %r" % (_live_contract(), BASE_CONTRACT)
    )
    for script, _prior, new in LAYERS:
        _run(script)
        assert _live_contract() == new, (
            "after %s contract is %r, expected %r" % (script, _live_contract(), new)
        )
    return _live_contract()


def main(check_only: bool = False) -> int:
    chain = validate_chain()
    if check_only:
        live = _live_contract()
        assert live == PUBLISHED_CONTRACT, (
            "on-disk ui_data.json contract %r != published %r"
            % (live, PUBLISHED_CONTRACT)
        )
        print(json.dumps({"mode": "check", "ok": True,
                          "live_contract": live, "chain": chain}, indent=2))
        return 0
    final = rebuild()
    assert final == PUBLISHED_CONTRACT, (
        "pipeline final contract %r != published %r" % (final, PUBLISHED_CONTRACT)
    )
    print(json.dumps({"mode": "rebuild", "ok": True,
                      "final_contract": final, "chain": chain}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(check_only="--check" in sys.argv))
