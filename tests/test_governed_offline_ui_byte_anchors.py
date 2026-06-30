"""Governed offline-UI byte-anchor CI meta-gate (W88) - the three governed
offline-UI anchors stay byte-stable, enforced in pytest rather than by a manual
per-cycle eyeball.

Background
----------
The owner offline-UI directive (MODEL_DEV_TASK_PROMPT.md / the
`auto_actuarial_stochastic_model` skill) states: *"Keep governed UI artifacts
byte-stable unless the task is an approved UI change with a contract bump."* The
governance store and every cycle-status doc re-assert three concrete anchors:

  * ``md5(offline_home.html) == 03d6538d3cae9efb83062ecbfab096e9``
  * ``ui_data.json`` top-level ``contract_version == "1.23.0"``
  * the governed headline ``39975.654628199336`` (the t-copula pathwise SCR
    component at ``capital.t_copula_scr_pathwise_component``) present in
    ``ui_data.json``.

Until now those anchors were verified only by hand each cycle. `build_phase_pkg`
pins ``ui_app.html`` - a DIFFERENT file - and no pytest pinned
``offline_home.html``'s exact md5 (verified: ``grep -rl 03d6538d tests/ scripts/``
returns nothing). So a silent edit to ``offline_home.html`` or a stray
``contract_version`` / headline change would pass CI and only be caught by a human
remembering to look. This module closes that gap: it converts the manual
byte-stability check into an automatic guard.

It complements - and does not duplicate - the existing offline-UI gates:
``build_offline_home_validate`` (177 structural assertions about
``offline_home.html`` *content*) and ``offline_home_loader_parity.cjs`` (loader
behaviour). Neither pins the *exact bytes* of the artifact nor the
``ui_data.json`` contract/headline scalars; this gate does, and only that.

Why pin md5 of the raw bytes
----------------------------
An md5 over the file's raw bytes is the strictest possible byte-stability check:
any one-byte change flips it. The test also proves the hash discriminates
(perturbed bytes yield a different digest) so it cannot pass vacuously via a
degenerate constant-returning hash.

Auto-admissibility
------------------
Test-tooling only: Python standard library (``hashlib``/``json``/``os``); no
network, no writes, no node, no subprocess. It ships nothing the model/UI
computes and changes NO governed byte, model figure, or contract version - it
merely *asserts* the existing governed values. If an owner-approved UI change
re-baselines these anchors (with a contract bump), the four constants below are
updated in the same change-set, exactly as the gate scripts are. Distinct from
W84/W85 (jsdom-free guard wrappers), W86 (guard-coverage), and W87 (gitignore
hygiene): this pins the governed offline-UI bytes/scalars.
"""
import hashlib
import json
import os

import pytest

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
_OFFLINE_HOME = os.path.join(_REPO, "offline_home.html")
_UI_DATA = os.path.join(_REPO, "ui_data.json")

# --- The governed anchors (re-baselined ONLY by an owner-approved UI change). ---
GOVERNED_OFFLINE_HOME_MD5 = "03d6538d3cae9efb83062ecbfab096e9"
GOVERNED_UI_DATA_CONTRACT = "1.23.0"
GOVERNED_HEADLINE = 39975.654628199336
GOVERNED_HEADLINE_LITERAL = "39975.654628199336"
# Canonical home of the governed headline in ui_data.json.
_HEADLINE_PATH = ("capital", "t_copula_scr_pathwise_component")


def _read_bytes(path):
    with open(path, "rb") as fh:
        return fh.read()


def _load_ui_data():
    with open(_UI_DATA, "r", encoding="utf-8") as fh:
        return json.load(fh)


def test_governed_artifacts_present():
    # Anchor: never vacuously green because an artifact vanished or is empty.
    assert os.path.isfile(_OFFLINE_HOME), "missing %s" % _OFFLINE_HOME
    assert os.path.isfile(_UI_DATA), "missing %s" % _UI_DATA
    assert os.path.getsize(_OFFLINE_HOME) > 0, "offline_home.html is empty"
    assert os.path.getsize(_UI_DATA) > 0, "ui_data.json is empty"


def test_offline_home_md5_pinned():
    # THE invariant: offline_home.html is byte-for-byte the governed artifact.
    actual = hashlib.md5(_read_bytes(_OFFLINE_HOME)).hexdigest()
    assert actual == GOVERNED_OFFLINE_HOME_MD5, (
        "offline_home.html md5 changed: expected %s, got %s. If this is an "
        "owner-approved UI change, re-baseline GOVERNED_OFFLINE_HOME_MD5 here "
        "AND in the gate scripts, with a ui_data contract bump." % (
            GOVERNED_OFFLINE_HOME_MD5, actual)
    )


def test_ui_data_contract_version_pinned():
    # Pin the TOP-LEVEL contract_version string (not the contract_manifest
    # sha256, which is a different field).
    data = _load_ui_data()
    actual = data.get("contract_version")
    assert actual == GOVERNED_UI_DATA_CONTRACT, (
        "ui_data.json top-level contract_version changed: expected %r, got %r. "
        "A contract bump is an owner-gated change." % (
            GOVERNED_UI_DATA_CONTRACT, actual)
    )


def test_ui_data_headline_pinned():
    # Pin the governed headline at its canonical path AND as a raw literal in the
    # file, so neither a moved key nor a reformatted value can slip past.
    data = _load_ui_data()
    node = data
    for key in _HEADLINE_PATH:
        assert isinstance(node, dict) and key in node, (
            "governed headline path %s broke at %r" % (
                ".".join(_HEADLINE_PATH), key)
        )
        node = node[key]
    assert node == GOVERNED_HEADLINE, (
        "governed headline at %s changed: expected %r, got %r (owner-gated "
        "re-baseline)" % (".".join(_HEADLINE_PATH), GOVERNED_HEADLINE, node)
    )
    # repr round-trips to the exact literal -> guards against precision drift.
    assert repr(node) == GOVERNED_HEADLINE_LITERAL, (
        "governed headline lost exactness: repr=%r expected %r" % (
            repr(node), GOVERNED_HEADLINE_LITERAL)
    )
    with open(_UI_DATA, "r", encoding="utf-8") as fh:
        assert GOVERNED_HEADLINE_LITERAL in fh.read(), (
            "governed headline literal %s no longer present verbatim in "
            "ui_data.json" % GOVERNED_HEADLINE_LITERAL
        )


def test_md5_anchor_has_teeth():
    # Teeth: prove the digest discriminates, so the md5 pin is not vacuous. The
    # real bytes hash to the governed value; a single appended byte does not.
    raw = _read_bytes(_OFFLINE_HOME)
    assert hashlib.md5(raw).hexdigest() == GOVERNED_OFFLINE_HOME_MD5
    assert hashlib.md5(raw + b"\x00").hexdigest() != GOVERNED_OFFLINE_HOME_MD5, (
        "md5 failed to discriminate a one-byte change - hash is degenerate"
    )
    # And the governed constant is a well-formed 32-char lowercase hex digest.
    assert len(GOVERNED_OFFLINE_HOME_MD5) == 32
    assert all(c in "0123456789abcdef" for c in GOVERNED_OFFLINE_HOME_MD5)


if __name__ == "__main__":
    raise SystemExit(pytest.main([os.path.abspath(__file__), "-v"]))
