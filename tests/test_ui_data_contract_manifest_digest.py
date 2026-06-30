"""Governed ui_data.json content-integrity digest gate (W89) - the machine
content digests in ``ui_data.json``'s ``contract_manifest`` stay pinned, so
silent payload drift is caught even when the human-readable ``contract_version``
semver string is left unchanged.

Background
----------
W88 (``tests/test_governed_offline_ui_byte_anchors.py``) pins the *human-readable*
governed offline-UI anchors: ``md5(offline_home.html)``, the top-level
``contract_version`` semver ``"1.23.0"``, and the headline scalar. Those guard the
rendered artifact and the version label - but NOT the machine content digests the
offline UI recomputes in-browser to prove the embedded payload is untampered.

``ui_data.json``'s ``contract_manifest`` (gap A2, contract 1.20.0+) carries a
SHA-256 per top-level section plus a ``root_digest`` over the section-digest map.
``contract_manifest.digest_scope`` documents the recipe verbatim:

    "sha256 over canonical(JSON) of every top-level section except
     contract_manifest; root_digest = sha256 over canonical(section_digests)."

No test pinned these (verified: ``grep -rl 456f7721 tests/ scripts/`` and
``grep -rl dd89545194911b5b tests/ scripts/`` both return nothing). So the payload
could drift - a section silently re-serialized - while the semver string stayed
``"1.23.0"`` and W88 stayed green. This module closes that gap with the MACHINE
content digest.

What it pins / proves
---------------------
* ``contract_manifest.digest_algo == "sha256"``.
* ``contract_manifest.root_digest`` == the governed value (literal pin).
* ``contract_manifest.section_digests.contract_version`` == the governed value
  (literal pin).
* TEETH - the pins are not vacuous string constants: the test RE-DERIVES both
  from the live payload using the documented canonical recipe and asserts they
  match, so any content drift in the section-digest map (root) or in the
  ``contract_version`` payload itself flips a digest and turns this RED.
* Both governed digests are well-formed 64-char lowercase-hex SHA-256 strings,
  and the recompute discriminates (a one-entry perturbation of the digest map
  yields a different root), so the teeth cannot pass vacuously.

Auto-admissibility
------------------
Test-tooling only: Python standard library (``hashlib``/``json``/``os``); no
network, no writes, no node, no subprocess, never SKIPs. It asserts existing
governed values and changes NO governed byte, model figure, or contract version.
If an owner-approved UI change re-baselines the contract (with a contract bump),
the two constants below are updated in the same change-set, exactly as the gate
scripts are. Distinct from W84/W85 (jsdom-free guard wrappers), W86
(guard-coverage), W87 (gitignore hygiene), and W88 (offline-UI byte anchors):
this pins the ui_data MACHINE content-integrity digests.
"""
import hashlib
import json
import os

import pytest

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
_UI_DATA = os.path.join(_REPO, "ui_data.json")

# --- Governed content-integrity digests (re-baselined ONLY by an owner-approved
# --- ui_data contract change, alongside the gate scripts and W88's anchors). ---
GOVERNED_DIGEST_ALGO = "sha256"
GOVERNED_ROOT_DIGEST = (
    "456f772166a1198363e16c7ccc68f87175ab4e4fa289cc0e798a009f1b257d01"
)
GOVERNED_CONTRACT_VERSION_SECTION_DIGEST = (
    "dd89545194911b5b0e3ddbc7285adf096b7196163c2fbf42e2a382cab8fc6c23"
)
_SHA256_HEX_LEN = 64


def _load_ui_data():
    with open(_UI_DATA, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _canonical(obj):
    # The recipe documented in contract_manifest.digest_scope and used by the
    # build_* digest scripts: compact, key-sorted JSON. Verified to reproduce
    # both root_digest and the contract_version section digest.
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def _sha256(obj):
    return hashlib.sha256(_canonical(obj).encode("utf-8")).hexdigest()


def _is_sha256_hex(s):
    return (
        isinstance(s, str)
        and len(s) == _SHA256_HEX_LEN
        and all(c in "0123456789abcdef" for c in s)
    )


def test_ui_data_present_and_has_manifest():
    # Never vacuously green: the artifact and the manifest must exist.
    assert os.path.isfile(_UI_DATA), "missing %s" % _UI_DATA
    assert os.path.getsize(_UI_DATA) > 0, "ui_data.json is empty"
    data = _load_ui_data()
    assert isinstance(data.get("contract_manifest"), dict), (
        "ui_data.json has no contract_manifest object"
    )


def test_digest_algo_pinned():
    cm = _load_ui_data()["contract_manifest"]
    assert cm.get("digest_algo") == GOVERNED_DIGEST_ALGO, (
        "contract_manifest.digest_algo changed: expected %r, got %r" % (
            GOVERNED_DIGEST_ALGO, cm.get("digest_algo"))
    )


def test_root_digest_pinned():
    cm = _load_ui_data()["contract_manifest"]
    assert cm.get("root_digest") == GOVERNED_ROOT_DIGEST, (
        "contract_manifest.root_digest changed: expected %s, got %s. If this is "
        "an owner-approved ui_data content change, re-baseline "
        "GOVERNED_ROOT_DIGEST here AND in the gate scripts, with a contract "
        "bump." % (GOVERNED_ROOT_DIGEST, cm.get("root_digest"))
    )


def test_contract_version_section_digest_pinned():
    sd = _load_ui_data()["contract_manifest"].get("section_digests", {})
    actual = sd.get("contract_version")
    assert actual == GOVERNED_CONTRACT_VERSION_SECTION_DIGEST, (
        "section_digests.contract_version changed: expected %s, got %s "
        "(owner-gated re-baseline)" % (
            GOVERNED_CONTRACT_VERSION_SECTION_DIGEST, actual)
    )


def test_root_digest_matches_section_map():
    # TEETH: root_digest is the genuine sha256 over canonical(section_digests),
    # per contract_manifest.digest_scope. This binds every section-digest entry:
    # tamper with any one and the recomputed root diverges from the pinned value.
    cm = _load_ui_data()["contract_manifest"]
    recomputed = _sha256(cm["section_digests"])
    assert recomputed == GOVERNED_ROOT_DIGEST, (
        "recomputed root over section_digests (%s) != governed root (%s): the "
        "section-digest map drifted from the pinned content" % (
            recomputed, GOVERNED_ROOT_DIGEST)
    )


def test_contract_version_section_digest_matches_payload():
    # TEETH: the contract_version section digest is the genuine sha256 over the
    # live contract_version payload, per the documented recipe. So a drift in the
    # contract_version content turns this RED even if the digest string were left
    # stale.
    data = _load_ui_data()
    recomputed = _sha256(data["contract_version"])
    assert recomputed == GOVERNED_CONTRACT_VERSION_SECTION_DIGEST, (
        "recomputed contract_version section digest (%s) != governed (%s)" % (
            recomputed, GOVERNED_CONTRACT_VERSION_SECTION_DIGEST)
    )


def test_governed_digests_well_formed_and_discriminating():
    # The pinned constants are real 64-char lowercase-hex sha256 digests ...
    assert _is_sha256_hex(GOVERNED_ROOT_DIGEST)
    assert _is_sha256_hex(GOVERNED_CONTRACT_VERSION_SECTION_DIGEST)
    # ... and the recompute discriminates, so the teeth are non-vacuous: a
    # perturbed section-digest map must NOT hash to the governed root.
    cm = _load_ui_data()["contract_manifest"]
    perturbed = dict(cm["section_digests"])
    perturbed["__tamper__"] = "0" * _SHA256_HEX_LEN
    assert _sha256(perturbed) != GOVERNED_ROOT_DIGEST, (
        "sha256 failed to discriminate a perturbed section-digest map"
    )


if __name__ == "__main__":
    raise SystemExit(pytest.main([os.path.abspath(__file__), "-v"]))
