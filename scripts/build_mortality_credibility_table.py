#!/usr/bin/env python3
"""
Builder — Credibility-Blended Mortality Table evidence (roadmap §4.1 #11, ASOP 25).

Runs the credibility-blending + improvement generator for both genders on the
built-in SYNTHETIC illustrative experience and (re)generates deterministically:

  * ``docs/validation/MORTALITY_CREDIBILITY_BLEND.json`` — machine artifact
    (both genders: credibility factors, blended A/E, blended base & projected
    qx tables, pinned digests, UNSIGNED banner).
  * ``docs/MORTALITY_CREDIBILITY_BLEND.md`` — human report (per-gender cards).

Purely additive diagnostic; does NOT touch any governed headline figure and
never mutates the governed ``_base_annual_qx``.  The default experience is
SYNTHETIC and the improvement scale illustrative, so the artifact is UNSIGNED
pending owner sign-off + independent APS X2 review.

Usage:
    python3 scripts/build_mortality_credibility_table.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from par_model_v2.projection.mortality_credibility import (  # noqa: E402
    SCHEMA,
    UNSIGNED_BANNER,
    STANDARD_REFERENCES,
    generate_blended_table,
)


def build(repo_root: Path, base_year: int = 2020, valuation_year: int = 2026) -> dict:
    tables = {}
    md_parts = [
        "# Credibility-Blended Mortality Tables (ASOP 25) — Evidence Report",
        "",
        f"**Schema:** `{SCHEMA}`  •  **Base→Valuation:** {base_year}→{valuation_year}  ",
        "**Roadmap:** §4.1 #11 mortality improvement + credibility blending (ASOP 25)  ",
        "",
        "> " + UNSIGNED_BANNER,
        "",
    ]
    for g in ("M", "F"):
        t = generate_blended_table(gender=g, base_year=base_year,
                                   valuation_year=valuation_year)
        tables[g] = t.to_dict()
        md_parts.append(t.to_markdown())
        md_parts.append("")

    artifact = {
        "schema": SCHEMA,
        "roadmap_item": "§4.1 #11 mortality improvement + credibility blending (ASOP 25)",
        "base_year": base_year,
        "valuation_year": valuation_year,
        "genders": tables,
        "unsigned": True,
        "unsigned_banner": UNSIGNED_BANNER,
        "standard_references": list(STANDARD_REFERENCES),
    }

    val = repo_root / "docs" / "validation"
    val.mkdir(parents=True, exist_ok=True)
    (val / "MORTALITY_CREDIBILITY_BLEND.json").write_text(
        json.dumps(artifact, indent=2), encoding="utf-8")
    (repo_root / "docs" / "MORTALITY_CREDIBILITY_BLEND.md").write_text(
        "\n".join(md_parts), encoding="utf-8")
    return artifact


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    art = build(root)
    for g, t in art["genders"].items():
        c = t["credibility"]
        print(f"[{g}] Z={c['Z']:.4f}  A/E_obs={c['observed_AE']:.4f}  "
              f"deaths={c['total_deaths']:.0f}/{c['full_credibility_deaths']:.1f}  "
              f"content_digest={t['content_digest'][:16]}…")
    print("wrote docs/validation/MORTALITY_CREDIBILITY_BLEND.json + docs/MORTALITY_CREDIBILITY_BLEND.md")
