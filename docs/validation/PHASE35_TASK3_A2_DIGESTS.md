# Phase 35 Task 3 (gap A2) — per-section SHA-256 content digest + in-browser verifier

**Verdict:** PASS · **Contract:** 1.19.0 → 1.20.0 (ADDITIVE, manifest-schema only) ·
**Agent:** Claude Cowork (06:00/18:00 UTC window) · **Date:** 2026-06-14

## What gap A2 closes
Phase 34 Task 2 (gap H1) proved the required data **sections are present** and the
contract version matches, but it could not detect whether a section's **content**
had been altered. A2 adds tamper-evidence: a build-time SHA-256 of every section
plus an in-browser recompute that verifies the embedded content is unaltered.

## Design (frozen)
- `canonical(value)` = recursive JSON, object keys sorted lexicographically,
  compact separators, JS-native number formatting (`String(Number)`).
- `section_digests[k] = sha256(canonical(DATA[k]))` for every top-level key
  **except** `contract_manifest` (the digests live inside it; excluding it
  avoids self-reference).
- `root_digest = sha256(canonical(section_digests))`.
- Added **inside** `contract_manifest`: `digest_algo` ("sha256"),
  `section_digests`, `root_digest`, `digest_scope`, `digest_generated_by`.
  **No new top-level key** — every pre-existing `ui_data.json` key is bit-identical.

## Why build and browser agree by construction
The build-time digests are produced by **executing the exact canonical + SHA-256
JavaScript that is embedded in the page** (run once in Node at build time). The
browser runs the identical source, so the recompute agrees byte-for-byte — there
is no opportunity for a Python/JS float-formatting divergence.

## In-browser verifier (Integrity / H1 panel)
- Self-contained **pure-JS SHA-256** + canonical serialiser embedded in
  `ui_app.html`; **no network, no storage API**, works under `file://`.
- On load, `renderIntegrityVerifierHtml()` recomputes the section digests from
  the embedded payload and renders a verified/altered table plus an overall
  **INTEGRITY VERIFIED / CONTENT ALTERED** badge and a root-digest read-out.
- It recomputes a content **digest**, not a model figure.

## Verification
- Pure-JS SHA-256 passes the NIST **'abc'** and **empty-string** vectors.
- Build-time Node cross-check: the embedded payload recomputes to identical
  `section_digests` + `root_digest` (`2d7b03f982a8980dbd5dc8355709d74bb795a273470b27a1ab9a4cfafb6ac117`).
- **ui_app self-test 350 → 358 checks**, ok:true, 0 network / 0 JS errors. Because
  jsdom executes the pure-JS SHA-256, the suite proves the **in-browser recompute
  genuinely matches** the embedded digests (all 23 sections verified).
- **Tamper test:** mutating the `summary` section flips the badge to **CONTENT
  ALTERED** with exactly one altered row.
- **8/8 offline self-tests** green: ui_app 358, offline_viewer 11, combined_gui 27,
  userrun 9, distribution 9, integrity 10, search_deeplink 18, bundle_printall 21.
- **pytest** `tests/test_phase35_task3_a2_digests.py` 9/9 — including an
  **independent pure-Python re-derivation** of `root_digest`.
- **0 external refs**; `model_result_viewer.html`, `combined_model_app.html`,
  `viewer_data.json` unchanged.

## Governance
ChangeRecord `60ee85ae8ebc4d09a09a01f0e75612b8` (code_change, **OWNER_REVIEW**);
records 94 → 95, audit 122 → 123, `verify_all` True.

## Constraints honoured
NO model parameter changes; Phase 30 binding stop-rule stands; MR-016/MR-017 owner
decision not pre-empted; governed frozen-t headline 39975.654628199336 untouched.
Zero-install / no-storage-API / `file://` invariants preserved.
