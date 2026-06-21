"""Post-Phase-35 Finding (2): builder/patch contract reconciliation guard.

These tests lock in the invariant that the offline-UI build pipeline reproduces
the PUBLISHED data-contract from a clean rebuild, so the layered build can never
again silently regress (build_ui_data.py alone emitted 1.18.0 while the live
artifacts were 1.20.0). They are fast/static: they import the pipeline and patch
modules and inspect version constants + the live ui_data.json -- no rebuild,
no heavy I/O.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
SCRIPTS = os.path.join(REPO, "scripts")
for p in (REPO, SCRIPTS):
    if p not in sys.path:
        sys.path.insert(0, p)

import build_ui_pipeline as pipe  # noqa: E402


def _live_contract():
    with open(os.path.join(REPO, "ui_data.json"), encoding="utf-8") as fh:
        return json.load(fh)["contract_version"]


def test_layer_chain_is_contiguous():
    """base -> ... -> published version constants form a gap-free chain.

    The expected "to" sequence is DERIVED from the pipeline's own
    ``LAYERS`` (base contract followed by each ADDITIVE patch layer's NEW
    contract) so this guard stays correct as new layers are appended. It was
    previously pinned to a literal 5-element list and went stale at each
    contract bump (the 1.22.0 MR-VR-1 step was missing after the 1.23.0
    MR-VR-2 panel shipped, turning this gate RED). Both endpoints remain
    explicitly pinned below, and ``validate_chain`` independently asserts
    contiguity and that the chain terminates at PUBLISHED_CONTRACT."""
    chain = pipe.validate_chain()  # raises on any gap
    tos = [s["to"] for s in chain["steps"]]
    expected = [pipe.BASE_CONTRACT] + [new for _script, _prior, new in pipe.LAYERS]
    assert tos == expected
    assert tos[0] == pipe.BASE_CONTRACT
    assert tos[-1] == pipe.PUBLISHED_CONTRACT


def test_base_contract_is_starting_point():
    """build_ui_data alone declares the base contract the first layer expects."""
    assert pipe.BASE_CONTRACT == pipe.LAYERS[0][1], (
        "build_ui_data.CONTRACT_VERSION must equal the first patch's PRIOR")


def test_published_contract_matches_live_artifact():
    """The pipeline's published target equals what is actually committed."""
    assert pipe.PUBLISHED_CONTRACT == _live_contract()


def test_check_mode_passes_on_live_tree():
    """--check validates the on-disk artifact without mutating it."""
    assert pipe.main(check_only=True) == 0


def test_no_version_gap_between_layers():
    """Each layer's PRIOR equals the previous layer's NEW."""
    cursor = pipe.BASE_CONTRACT
    for _script, prior, new in pipe.LAYERS:
        assert prior == cursor, "gap before %s" % _script
        cursor = new
    assert cursor == pipe.PUBLISHED_CONTRACT
