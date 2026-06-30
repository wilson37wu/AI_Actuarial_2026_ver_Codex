"""Offline-UI CI-coverage meta-gate (W86) - every jsdom-FREE scripts/*.cjs guard
is collected by a pytest wrapper under tests/.

Background
----------
W84 and W85 added thin pytest wrappers that shell the two jsdom-FREE node guards
(scripts/ui_app_selftest_nojsdom.cjs, scripts/offline_home_loader_parity.cjs) so
they are re-checked on every test run. "jsdom-FREE" matters because those guards
use only the node standard library (no node_modules), so they actually execute
in the offline auto-cycle sandbox; the jsdom-DEPENDENT guards
(scripts/ui_app_self_test.cjs, scripts/offline_home_self_test.cjs, ...) require a
third-party module that is absent there and so stay owner/CI-gated.

This module is a pure-Python *meta-gate*: it enumerates scripts/*.cjs, statically
classifies each as jsdom-FREE vs jsdom-DEPENDENT, and asserts that every
jsdom-FREE guard is referenced by some pytest wrapper under tests/. It is a
backstop against CI-coverage drift - the failure mode where a future jsdom-FREE
guard is added (runnable in the sandbox) but nobody wires it into pytest, so it
silently never runs in the auto-cycle lane.

Why static, not a naive grep
----------------------------
The jsdom-FREE companion guards intentionally MENTION require('jsdom') in their
header comments (to explain why they avoid it). A naive substring/grep classifier
misclassifies them as dependent. The classifier here therefore strips // line and
/* block */ comments before looking for an executable require('jsdom') call, and
the suite ships unit "teeth" (test_classifier_distinguishes_comment_from_code)
proving that distinction.

Auto-admissibility
------------------
Test-tooling only: pure Python standard library (os/re/glob), no node, no
subprocess, no network. It reads source files and asserts a coverage invariant;
it ships nothing the model/UI computes and changes NO governed byte, model figure,
or contract version. Runs in every lane (it never SKIPs). Distinct target from
W84/W85 (a coverage meta-invariant, not a third guard wrapper).
"""
import glob
import os
import re

import pytest

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
_SCRIPTS_DIR = os.path.join(_REPO, "scripts")
_TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
_SELF = os.path.abspath(__file__)

# Executable `require('jsdom')` / require("jsdom") call (single or double quotes,
# optional inner whitespace). Applied AFTER comments are stripped.
_REQUIRE_JSDOM = re.compile(r"""require\(\s*['"]jsdom['"]\s*\)""")
_BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.S)
_LINE_COMMENT = re.compile(r"//[^\n]*")

# jsdom-FREE scripts/*.cjs that are deliberately NOT guards needing a wrapper
# (e.g. a future pure helper/library). Empty today: every current scripts/*.cjs
# is a self-test/parity guard. A future cycle that adds a non-guard jsdom-free
# .cjs adds it here in the same change, keeping the invariant honest.
_NON_GUARD_ALLOWLIST = frozenset()


def _strip_comments(src):
    return _LINE_COMMENT.sub("", _BLOCK_COMMENT.sub("", src))


def _read(path):
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        return fh.read()


def _is_jsdom_dependent(path):
    return bool(_REQUIRE_JSDOM.search(_strip_comments(_read(path))))


def _all_cjs():
    return sorted(glob.glob(os.path.join(_SCRIPTS_DIR, "*.cjs")))


def _jsdom_free_guards():
    return [
        p
        for p in _all_cjs()
        if not _is_jsdom_dependent(p)
        and os.path.basename(p) not in _NON_GUARD_ALLOWLIST
    ]


def _wrapper_corpus():
    """Concatenated text of every tests/*.py EXCEPT this meta-gate itself, so a
    guard basename appearing only in THIS file does not count as 'collected'."""
    parts = []
    for p in sorted(glob.glob(os.path.join(_TESTS_DIR, "*.py"))):
        if os.path.abspath(p) == _SELF:
            continue
        parts.append(_read(p))
    return "\n".join(parts)


def test_scripts_dir_has_cjs_guards():
    # Anchor: the enumeration is non-empty, so the gate is never vacuously green
    # because it scanned an empty/relocated directory.
    assert os.path.isdir(_SCRIPTS_DIR), "missing %s" % _SCRIPTS_DIR
    assert _all_cjs(), "no scripts/*.cjs found - enumeration is empty"


def test_every_jsdom_free_guard_has_a_pytest_wrapper():
    # THE invariant: any jsdom-FREE scripts/*.cjs guard (therefore runnable in
    # the offline auto-cycle sandbox) must be referenced by a pytest wrapper
    # under tests/, so it is re-checked automatically. Catches the drift where a
    # new jsdom-free guard is added but left uncollected.
    corpus = _wrapper_corpus()
    free = [os.path.basename(p) for p in _jsdom_free_guards()]
    uncollected = sorted(b for b in free if b not in corpus)
    assert not uncollected, (
        "jsdom-FREE guard(s) not referenced by any tests/*.py wrapper: %s. Add a "
        "thin pytest wrapper (model it on tests/test_ui_app_selftest_nojsdom.py "
        "or tests/test_offline_home_loader_parity.py)." % uncollected
    )


def test_classifier_distinguishes_comment_from_code(tmp_path):
    # Teeth: prove the classifier is not a naive substring match. A file that
    # only MENTIONS require('jsdom') in // and /* */ comments is jsdom-FREE; a
    # file that actually calls it is jsdom-DEPENDENT.
    mentions_only = tmp_path / "mentions_only.cjs"
    mentions_only.write_text(
        "// this guard avoids require('jsdom') on purpose\n"
        "/* require('jsdom') would pull a heavy third-party dep */\n"
        "const fs = require('fs');\n",
        encoding="utf-8",
    )
    real_dep = tmp_path / "real_dep.cjs"
    real_dep.write_text(
        'const { JSDOM, VirtualConsole } = require("jsdom");\n',
        encoding="utf-8",
    )
    assert _is_jsdom_dependent(str(real_dep)) is True
    assert _is_jsdom_dependent(str(mentions_only)) is False


def test_known_free_guards_classified_free():
    # Regression anchor: the two proven jsdom-FREE companion guards (W83/W85)
    # still classify FREE, so this meta-gate keeps real teeth even if the
    # classifier is later edited. (Deliberate removal updates this anchor in the
    # same cycle.)
    free = {os.path.basename(p) for p in _jsdom_free_guards()}
    for known in ("ui_app_selftest_nojsdom.cjs", "offline_home_loader_parity.cjs"):
        assert os.path.isfile(os.path.join(_SCRIPTS_DIR, known)), (
            "expected guard missing: %s" % known
        )
        assert known in free, "%s should classify jsdom-FREE" % known


def test_known_dependent_guard_classified_dependent():
    # Counter-anchor: a genuine jsdom consumer classifies DEPENDENT, so a broken
    # classifier that marks everything FREE (which would noisily demand wrappers
    # for owner/CI-gated guards) is caught.
    dep = os.path.join(_SCRIPTS_DIR, "ui_app_self_test.cjs")
    if not os.path.isfile(dep):
        pytest.skip("reference jsdom-dependent guard not present")
    assert _is_jsdom_dependent(dep) is True


if __name__ == "__main__":
    raise SystemExit(pytest.main([os.path.abspath(__file__), "-v"]))
