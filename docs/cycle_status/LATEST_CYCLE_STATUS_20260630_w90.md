# Cycle Status — W90 (Claude, AUTO) — 2026-06-30

**Conclusion:** PASS. Implemented the W89-registered auto-admissible improvement —
`tests/test_ui_data_contract_manifest_structure.py`, a pure-Python pytest gate that
pins the `ui_data.json` `contract_manifest` **structural completeness** (the manifest
is internally self-consistent and faithfully describes the real payload). 9 passed;
teeth re-verified in an isolated scratch copy (clone never mutated). No model-FORM,
governed-artifact, or contract change — `origin/main` delta is **+1 new test file**.
Phase 38 Task 3 (ui_app native-tab cutover) remains **OWNER-GATED**, left in_progress.

## Task executed
Authored `tests/test_ui_data_contract_manifest_structure.py` (stdlib `json`/`os`/`re`;
no node, no subprocess, no network, never SKIPs). 9 tests pinning, beyond the value
pins of W88 (offline-UI bytes/semver/headline) and W89 (manifest digest VALUES):

1. `contract_manifest` present, non-empty, well-typed (`required_top_level_keys` list,
   `section_digests` dict).
2. `key_count == 26` (governed literal).
3. `expected_contract_version == "1.23.0"` **and** `== ui_data.contract_version`
   (the manifest's declared expectation agrees with the live payload — a field W88
   does not cover).
4. Size agreement: `key_count == len(required_top_level_keys) == len(section_digests)
   == 26` (catches a `key_count` drift that leaves `section_digests`, and therefore
   `root_digest`, byte-identical → invisible to W89).
5. `set(required_top_level_keys) == set(section_digests)` — exact coverage, no orphan
   digest, no undigested required section.
6. `required_top_level_keys` has no duplicate entries (a JSON list can carry dups while
   set-equality still holds).
7. Every one of the 26 `section_digests` values is a well-formed 64-char lowercase-hex
   SHA-256 string (W89 only checked the two it pins by value).
8. The contract describes the REAL payload: `set(ui_data top-level) ==
   required_top_level_keys ∪ {contract_manifest}`, and `contract_manifest` is not
   itself a digested section (matches `digest_scope`).
9. TEETH (in-test): perturbed copies of the live manifest break the relevant
   invariants, proving the structural assertions are non-vacuous.

### Why this is a real gap (not a near-duplicate of W89)
`root_digest = sha256(canonical(section_digests))` (W89's teeth), so it only moves when
the section-digest **map** moves. A drift in `key_count` (a plain integer), in
`required_top_level_keys` (a sibling list), in `expected_contract_version`, or the
appearance of a new top-level ui_data section with no digest, leaves `section_digests`
— and thus `root_digest` — untouched: W88/W89 stay green while the manifest is silently
self-inconsistent or no longer describes the payload. W90 is the structural backstop.

## Teeth re-verification (isolated scratch, clone never mutated)
Copy-out of the live `ui_data.json` into `/tmp` scratch dirs, then perturb + run:
- `key_count` 26→27 → `test_key_count_pinned` + `test_count_fields_mutually_agree` RED.
- drop one `section_digest` → `test_count_fields_mutually_agree` +
  `test_required_keys_match_section_digest_keys` RED.
- add undigested top-level section → `test_required_keys_describe_real_payload` RED.
- malform a section digest (non-hex) → `test_all_section_digests_well_formed_hex` RED.
- duplicate a required key → `test_count_fields_mutually_agree` +
  `test_required_keys_have_no_duplicates` RED.
- `expected_contract_version` 1.23.0→9.9.9 → `test_expected_contract_version_agrees` RED.
Governed clone `ui_data.json` md5 `70b747a05c00d29bd6e286a7ee4cf42c` UNCHANGED throughout.

## Verification gates — GREEN
- **Gate C** — `launch_offline_gui.py --self-test`: `self_test_ok:true`,
  `engine_ready:true`. `run_model.py --n-outer 100 --n-inner 4 --no-tail --seed 42`
  smoke bit-match: **nested 49657.9 / gaussian 37499.0 / var-covar 30267.9**.
- **Gate D** — `actuarial_gui.spec` AST-parses; `release.workflow.yml` valid YAML;
  `offline_bootstrap.py --self-test` ok; `build_phase_pkg_task1_validate.py` 26 checks
  pass (incl. `ui_app_byte_unchanged` + `governed_headline_present`).
- **Integrity** — `build_offline_home_validate.py` 177/177 (failed:[]);
  `offline_home_loader_parity.cjs` (node) 10/10; `ui_app_selftest_nojsdom.cjs` 40/40;
  governed-UI pytest cluster 25 passed (`test_offline_home_validate` 4 + W88 5 + W89 7
  + W90 9); MLMC suite 53/53. Repo-wide `--collect-only` = **3749 tests, 0 collection
  errors**.
- **Governed bytes byte-UNCHANGED** — `offline_home.html` md5
  `03d6538d3cae9efb83062ecbfab096e9`; `ui_data.json` md5
  `70b747a05c00d29bd6e286a7ee4cf42c` / contract `1.23.0` / root_digest `456f7721…`;
  headline `39975.654628199336`.

## Engine lock
numpy 1.26.4 / scipy 1.13.1 / pandas 2.2.3 (`requirements-engine-lock.txt`) in
`/tmp/eng_venv_w90` (reused w89 venv); pytest 9.1.1.

## Coordination
Fresh throwaway clone (`/tmp/cc_20260630_040746`); mount `.git` untouched. Preflight
PROCEED (owner null); lock `2026-06-30T04:09Z-6b7d` acquired. Mount synced to
`origin/main` post-push; lock released.

## Researched next improvement (registered W91)
`tests/test_ui_data_section_digest_recompute_parity` — a **Node** (stdlib-only,
jsdom-free) gate that recomputes ALL 26 `section_digests` directly from the **standalone
`ui_data.json`** payload using the page's embedded `_ciCanon`/`_ciSha256` canonical
serialiser (the authoritative JS recipe — a pure-Python recompute is infeasible because
the recipe uses JS-native `String(Number)` formatting; this cycle empirically confirmed
19/26 sections diverge under Python `json.dumps`), asserting parity with
`contract_manifest.section_digests` + `root_digest`. Closes the gap that the existing
all-26 recompute (`ui_app_selftest_nojsdom.cjs`, 40/40) runs on `ui_app.html`'s
**embedded** payload, while no gate recomputes the 26 section payloads of the standalone
governed `ui_data.json` that `offline_home.html` consumes. **The next cycle must FIRST
confirm the gap is real** (no existing gate recomputes section payloads against
standalone `ui_data.json`); if already covered transitively (embedded==standalone proof
+ embedded recompute), redirect to a documentation refresh instead. stdlib/node only;
no governed bytes; no model-FORM change; distinct from W84–W90.
