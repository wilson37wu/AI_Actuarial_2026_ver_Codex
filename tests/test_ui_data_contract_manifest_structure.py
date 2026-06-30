"""Governed ui_data.json contract-manifest STRUCTURAL-completeness gate (W90).

The ``contract_manifest`` in ``ui_data.json`` is internally self-consistent and
faithfully describes the real payload, so a metadata/structure drift is caught
even when every pinned digest *value* is left untouched.

Background / the gap this closes
--------------------------------
The offline-UI governance stack already pins the manifest's *values*:

* W88 (``test_governed_offline_ui_byte_anchors.py``) - md5(offline_home.html),
  the top-level ``contract_version`` semver, and the headline scalar.
* W89 (``test_ui_data_contract_manifest_digest.py``) - ``digest_algo``, the
  ``root_digest`` literal, and the ``section_digests.contract_version`` digest,
  each re-derived from the live payload (content-drift teeth).

What NOTHING pinned is the manifest's STRUCTURE. ``contract_manifest`` carries
three independent statements of its own size - ``key_count``,
``len(required_top_level_keys)``, and ``len(section_digests)`` - that must agree
at 26, the ``required_top_level_keys`` set must coincide exactly with the
``section_digests`` key set (every governed section has exactly one digest, with
no orphan or missing entry), and the contract must enumerate ui_data's REAL
top-level sections (everything except ``contract_manifest`` itself, per
``digest_scope``).

These are failure modes the value pins miss. ``root_digest`` is
``sha256(canonical(section_digests))`` (W89's teeth), so it only moves when the
section-digest MAP moves. A drift in ``key_count`` (a plain integer field), or in
``required_top_level_keys`` (a sibling list), or the appearance of a new
top-level ui_data section with no matching digest, leaves ``section_digests``
- and therefore ``root_digest`` - byte-identical: W88/W89 stay green while the
manifest is silently self-inconsistent or no longer describes the payload. This
module is the structural backstop.

What it pins / proves
---------------------
* ``key_count == 26`` (governed literal), and the three size statements agree:
  ``key_count == len(required_top_level_keys) == len(section_digests)``.
* ``set(required_top_level_keys) == set(section_digests)`` - exact coverage, no
  orphan digest, no undigested required section; and ``required_top_level_keys``
  has no duplicate entries.
* Every one of the 26 ``section_digests`` values is a well-formed 64-char
  lowercase-hex SHA-256 string (W89 only checked the two it pins by value).
* The contract describes the REAL payload: the set of ui_data top-level keys is
  exactly ``required_top_level_keys`` plus ``contract_manifest`` itself, and
  ``contract_manifest`` is NOT listed among the digested sections (matching
  ``digest_scope``: "... every top-level section except contract_manifest").
* TEETH - the structural assertions are non-vacuous: a copy of the manifest with
  one section_digest dropped breaks key-set equality and the count agreement, and
  a copy with ``key_count`` perturbed breaks the size agreement, so the gate is
  demonstrably discriminating rather than trivially true.

Auto-admissibility
------------------
Test-tooling only: Python standard library (``json``/``os``/``re``); no network,
no writes, no node, no subprocess, never SKIPs. It asserts the existing governed
structure and changes NO governed byte, model figure, or contract version. An
owner-approved ui_data contract change that alters the section set re-baselines
``GOVERNED_KEY_COUNT`` here in the same change-set, exactly as the digest gates
are. Distinct from W84/W85 (jsdom-free guard wrappers), W86 (guard-coverage),
W87 (gitignore hygiene), W88 (offline-UI byte anchors), and W89 (manifest digest
VALUES): this pins the manifest's STRUCTURAL completeness and payload fidelity.
"""
import json
import os
import re

import pytest

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
_UI_DATA = os.path.join(_REPO, "ui_data.json")

# Governed section count. Re-baselined ONLY by an owner-approved ui_data
# contract change that adds/removes a top-level section (with a contract bump),
# alongside W88's anchors and W89's digests.
GOVERNED_KEY_COUNT = 26
# Governed contract semver the manifest declares it expects. Re-baselined ONLY
# by an owner-approved contract bump, alongside W88's top-level semver anchor.
GOVERNED_CONTRACT_VERSION = "1.23.0"
# contract_manifest is the one top-level ui_data key that is NOT a digested
# section (per contract_manifest.digest_scope).
_MANIFEST_KEY = "contract_manifest"
_SHA256_HEX = re.compile(r"\A[0-9a-f]{64}\Z")


def _load_ui_data():
    with open(_UI_DATA, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _manifest():
    return _load_ui_data()[_MANIFEST_KEY]


def test_ui_data_present_and_has_manifest():
    # Never vacuously green: the artifact and the manifest must exist.
    assert os.path.isfile(_UI_DATA), "missing %s" % _UI_DATA
    assert os.path.getsize(_UI_DATA) > 0, "ui_data.json is empty"
    data = _load_ui_data()
    cm = data.get(_MANIFEST_KEY)
    assert isinstance(cm, dict), "ui_data.json has no contract_manifest object"
    assert isinstance(cm.get("required_top_level_keys"), list)
    assert isinstance(cm.get("section_digests"), dict)


def test_key_count_pinned():
    cm = _manifest()
    assert cm.get("key_count") == GOVERNED_KEY_COUNT, (
        "contract_manifest.key_count changed: expected %d, got %r. If this is an "
        "owner-approved ui_data section add/remove, re-baseline GOVERNED_KEY_COUNT "
        "here (and the digest gates), with a contract bump."
        % (GOVERNED_KEY_COUNT, cm.get("key_count"))
    )


def test_expected_contract_version_agrees():
    # The manifest's own stated expectation must equal the governed semver AND
    # the live top-level contract_version. Catches a manifest whose declared
    # expected_contract_version drifts from the payload it describes - a field
    # W88 does not cover (W88 pins the top-level semver, not the manifest's
    # expectation-of-it).
    data = _load_ui_data()
    cm = data[_MANIFEST_KEY]
    assert cm.get("expected_contract_version") == GOVERNED_CONTRACT_VERSION, (
        "contract_manifest.expected_contract_version changed: expected %r, got %r"
        % (GOVERNED_CONTRACT_VERSION, cm.get("expected_contract_version"))
    )
    assert cm.get("expected_contract_version") == data.get("contract_version"), (
        "manifest expected_contract_version (%r) != top-level contract_version (%r)"
        % (cm.get("expected_contract_version"), data.get("contract_version"))
    )


def test_count_fields_mutually_agree():
    # The manifest states its own size three ways; all three must agree, and with
    # the governed literal. Catches a key_count drift that leaves section_digests
    # (and thus root_digest) untouched.
    cm = _manifest()
    n_required = len(cm["required_top_level_keys"])
    n_digests = len(cm["section_digests"])
    assert cm["key_count"] == n_required == n_digests == GOVERNED_KEY_COUNT, (
        "manifest size statements disagree: key_count=%r, "
        "len(required_top_level_keys)=%d, len(section_digests)=%d, governed=%d"
        % (cm.get("key_count"), n_required, n_digests, GOVERNED_KEY_COUNT)
    )


def test_required_keys_match_section_digest_keys():
    # Exact coverage: every required section has exactly one digest and there is
    # no orphan digest. A missing/extra entry here does not necessarily move
    # root_digest in a way the value-pins notice, so pin the SET equality.
    cm = _manifest()
    required = set(cm["required_top_level_keys"])
    digested = set(cm["section_digests"].keys())
    assert required == digested, (
        "required_top_level_keys and section_digests disagree: "
        "required-only=%s, digest-only=%s"
        % (sorted(required - digested), sorted(digested - required))
    )


def test_required_keys_have_no_duplicates():
    # required_top_level_keys is a JSON list, so it CAN carry duplicates (unlike
    # the section_digests object keys). A dup would make the list len exceed the
    # true section count while set-equality still held - pin uniqueness.
    req = _manifest()["required_top_level_keys"]
    assert len(req) == len(set(req)), (
        "required_top_level_keys has duplicate entries: %s"
        % sorted({k for k in req if req.count(k) > 1})
    )


def test_all_section_digests_well_formed_hex():
    # All 26, not just the two W89 pins by value: every section digest is a
    # 64-char lowercase-hex sha256 string.
    sd = _manifest()["section_digests"]
    bad = {k: v for k, v in sd.items()
           if not (isinstance(v, str) and _SHA256_HEX.match(v))}
    assert not bad, "malformed section_digests (want 64-char lc hex): %r" % bad


def test_required_keys_describe_real_payload():
    # The contract enumerates the REAL ui_data top-level sections: the actual
    # top-level key set is exactly required_top_level_keys plus contract_manifest
    # itself, and contract_manifest is not itself listed as a digested section
    # (matching digest_scope's "every top-level section except contract_manifest").
    data = _load_ui_data()
    cm = data[_MANIFEST_KEY]
    actual_top = set(data.keys())
    required = set(cm["required_top_level_keys"])
    assert _MANIFEST_KEY not in required, (
        "contract_manifest must not list itself as a digested section"
    )
    assert actual_top == required | {_MANIFEST_KEY}, (
        "contract drifted from real payload: ui_data-only=%s, contract-only=%s"
        % (sorted(actual_top - (required | {_MANIFEST_KEY})),
           sorted((required | {_MANIFEST_KEY}) - actual_top))
    )


def test_structural_checks_are_discriminating():
    # TEETH: prove the structural assertions are non-vacuous by perturbing copies
    # of the live manifest and confirming each invariant then FAILS.
    cm = _manifest()
    # (a) drop one section_digest -> key-set equality and count agreement break.
    sd_missing = dict(cm["section_digests"])
    dropped = sorted(sd_missing)[0]
    del sd_missing[dropped]
    assert set(cm["required_top_level_keys"]) != set(sd_missing), (
        "set-equality teeth vacuous: dropping a digest did not break coverage"
    )
    assert not (len(cm["required_top_level_keys"]) == len(sd_missing)
                == GOVERNED_KEY_COUNT), (
        "count-agreement teeth vacuous: dropping a digest did not break the count"
    )
    # (b) perturb key_count -> size agreement breaks.
    assert not ((GOVERNED_KEY_COUNT + 1)
                == len(cm["required_top_level_keys"])
                == len(cm["section_digests"])), (
        "count-agreement teeth vacuous: a wrong key_count still agreed"
    )


if __name__ == "__main__":
    raise SystemExit(pytest.main([os.path.abspath(__file__), "-v"]))
