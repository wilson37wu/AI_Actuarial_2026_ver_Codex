# Cycle status — 2026-06-14 (Claude Cowork) — Phase 35 Task 3 (gap A2)

**Task:** per-section SHA-256 content digest + in-browser tamper-evident verifier.
**Verdict:** COMPLETE / PASS. ChangeRecord `60ee85ae8ebc4d09a09a01f0e75612b8`
(code_change, OWNER_REVIEW); records 94→95, audit 122→123, verify_all True.
**Lock:** held (owner=claude, cycle 2026-06-14T07:09Z-3ddf).

## What landed
- **`scripts/build_phase35_task3_a2_digests.py` (new):** computes a build-time
  SHA-256 over a canonical serialisation of every top-level section (all keys
  except `contract_manifest`) and a `root_digest` over the canonical sorted
  section-digest map, written **inside** `contract_manifest`
  (`digest_algo`/`section_digests`/`root_digest`/`digest_scope`/`digest_generated_by`).
  **ADDITIVE contract 1.19.0 → 1.20.0**; no new top-level key; every pre-existing
  `ui_data.json` key bit-identical. The build digests are produced by executing
  the **same** canonical+SHA-256 JS the page runs (in Node) → browser recompute
  matches by construction.
- **`ui_app.html`:** self-contained pure-JS SHA-256 + canonical serialiser +
  `renderIntegrityVerifierHtml()` — the Integrity (H1) panel recomputes the
  section digests **in the browser** (no network, no storage, `file://`-safe) and
  renders a verified/altered table + an INTEGRITY VERIFIED / CONTENT ALTERED badge.
  Recomputes a content digest, **not** a model figure.
- **`scripts/ui_app_self_test.cjs`:** +8 A2 checks (350 → 358); the contract-version
  check bumped to 1.20.0.

## Tests
- Pure-JS SHA-256 passes NIST `abc` + empty-string vectors.
- Build-time Node cross-check: embedded payload recomputes to identical digests
  (root `2d7b03f982a8980dbd5dc8355709d74bb795a273470b27a1ab9a4cfafb6ac117`).
- **ui_app self-test 358 checks ok:true 0/0** — jsdom executes the pure-JS SHA-256,
  so this proves the in-browser recompute matches the embedded digests (23 sections
  verified). **Tamper test:** mutating `summary` flips the badge to CONTENT ALTERED.
- **8/8 offline self-tests** green (ui_app 358, offline_viewer 11, combined_gui 27,
  userrun 9, distribution 9, integrity 10, search_deeplink 18, bundle_printall 21).
- **pytest** `tests/test_phase35_task3_a2_digests.py` 9/9 (incl. independent
  pure-Python `root_digest` re-derivation).
- 0 external refs; `model_result_viewer.html` / `combined_model_app.html` /
  `viewer_data.json` unchanged.

## Environment notes (for the next agent)
- The in-place file-tool editor truncated `scripts/ui_app_self_test.cjs` mid-write
  (the known virtiofs hazard). Recovered by restoring the pristine file from git
  and re-applying the edits **off-mount** in `/tmp`, then `cp`-ing back — never let
  the file tool be the last writer of a large mounted file; verify line counts.
- Running all 8 jsdom suites in one bash call exceeds the ~45 s tool budget — run
  them in batches of ≤2.

## Next
- **Phase 35 Task 4 = gap A3:** one-page printable ASOP-41-style model-card cover
  (presentation only; bit-for-bit from the embedded snapshot; owner-decision field
  BLANK; provenance-stamped). Then Task 5 = phase summary + consolidated re-audit +
  PHASE 35 COMPLETE.
