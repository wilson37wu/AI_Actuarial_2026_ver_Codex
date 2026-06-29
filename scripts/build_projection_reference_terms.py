#!/usr/bin/env python3
"""build_projection_reference_terms.py — Phase 38 Task 2.

Generate the 5yr and 10yr PAR-endowment reference runs in the IDENTICAL schema as
the 20yr governed reference, by reusing build_projection_reference.write_reference
(same product/fund presets, same governed engine call run_full_projection — only
``term_years`` differs). Display-only; the 20yr governed file is NOT touched.

Outputs:
  docs/validation/PROJECTION_REFERENCE_RUN_5YR.json
  docs/validation/PROJECTION_REFERENCE_RUN_10YR.json

Run:  python3 scripts/build_projection_reference_terms.py
"""
from __future__ import annotations
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from build_projection_reference import write_reference  # noqa: E402

VALDIR = os.path.join(ROOT, "docs", "validation")
TERMS = {5: "PROJECTION_REFERENCE_RUN_5YR.json",
         10: "PROJECTION_REFERENCE_RUN_10YR.json"}


def main() -> int:
    rc = 0
    for term in sorted(TERMS):
        rc |= write_reference(term, os.path.join(VALDIR, TERMS[term]))
    return rc


if __name__ == "__main__":
    sys.exit(main())
