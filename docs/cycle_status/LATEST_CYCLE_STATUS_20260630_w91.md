# Cycle Status — W91 (Claude, AUTO) — 2026-06-30

**Conclusion:** PASS. Implemented the W90-registered auto-admissible improvement **after confirming the gap is
real** — `scripts/ui_data_section_digest_recompute_parity.cjs`, a Node (stdlib-only `fs`/`path`/`crypto`/`vm`,
jsdom-free) gate that recomputes ALL 26 `section_digests` **+** `root_digest` **directly from the standalone
`ui_data.json`** (the file `offline_home.html` consumes) and asserts parity with that file's own `contract_manifest`
plus the governed `root_digest` pin — and `tests/test_ui_data_section_digest_recompute_parity.py`, the pytest wrapper.
**22/22 GREEN**; 6 pytest cases. No model-FORM / governed-artifact / contract change — `origin/main` delta is **+2 new
files**. Phase 38 Task 3 (ui_app native-tab cutover) remains **OWNER-GATED**, left in_progress.

## Confirm-gap-first (required by the W90 registration — done BEFORE building)
No existing gate recomputes the 26 section payloads of the **standalone** `ui_data.json`:
- `scripts/ui_app_selftest_nojsdom.cjs` (40/40) recomputes `_ciSectionDigests(DATA)` where `DATA` is the **embedded**
  payload parsed from `ui_app.html`'s `<script id="ui-data">` block — not the standalone file.
- W89 `test_ui_data_contract_manifest_digest.py` pins `root_digest` + the `contract_version` section digest **by
  value**; W90 `test_ui_data_contract_manifest_structure.py` pins manifest **structure** — neither recomputes a
  section payload→digest.
- The `test_embedded_payload_matches_standalone` tests (phase35-a2, postigui task5/task8) compare only the
  `contract_manifest` sub-object (`root_digest` + `section_digests` map), plus at most one individual section — never
  all 26 standalone section payloads.
- `scripts/build_offline_home_validate.py` "recomputes nothing" (renders governed figures verbatim);
  `scripts/offline_home_loader_parity.cjs` compares rendered **figures**, not digests.

⇒ a standalone `ui_data.json` whose section **payload** drifted while its manifest digests stayed byte-identical passed
every prior gate. Gap **real**, not transitively covered (no full embedded==standalone 26-section equality proof
exists). Built the gate.

## Task executed
`scripts/ui_data_section_digest_recompute_parity.cjs` recomputes the 26 digests from the standalone `ui_data.json`
**two independent ways**:
1. **AUTHORITATIVE** — extracts the page's OWN `_ciCanon`/`_ciSha256`/`_ciSectionDigests` from `ui_app.html` (recipe
   source only; the inert `<script id="ui-data">` block is stripped first so the embedded payload is never read) and
   runs `_ciSectionDigests(STANDALONE_DATA)`. 0 mismatch / 0 missing / 0 extra vs the standalone manifest; recomputed
   `root_digest` == manifest == governed `456f7721…`.
2. **INDEPENDENT** — `node:crypto` SHA-256 over a faithful re-implementation of the canonical serialiser; same parity
   + governed-root pin.

Plus exact `section_digests`-keys == standalone non-manifest top-level keys coverage, `key_count==26`
self-consistency, governed contract `1.23.0` pin, and NIST SHA-256 vectors for both the page hasher and `node:crypto`.
A pure-Python recompute is **infeasible** — the recipe uses JS-native `String(Number)` number formatting; 19/26
sections diverge under Python `json.dumps` — which is exactly why the authoritative path borrows the page JS.

`tests/test_ui_data_section_digest_recompute_parity.py` collects the Node gate into pytest (SKIP only when a `node`
binary is absent, mirroring `test_ui_app_selftest_nojsdom.py`), asserting `ok`, `failed==[]`, `passed==checks`, and a
`checks>=22` baseline (catches a silently weakened guard).

### Why this is a real gap (not a near-duplicate of W84–W90)
The all-26 recompute that already exists (`ui_app_selftest_nojsdom.cjs`) runs on `ui_app.html`'s **embedded** payload.
The standalone `ui_data.json` — the artifact `offline_home.html` actually loads (and into which the user can drag-drop
a different snapshot) — is checked elsewhere only for manifest **values**/**structure** and rendered **figures**. W91
is the first and only gate that takes the standalone payload's 26 section bodies and recomputes their digests under the
authoritative recipe. Distinct input (standalone, not embedded) and distinct assertion (payload→digest recompute, not
manifest-only comparison).

## Teeth re-verification (isolated `/tmp` scratch; clone never mutated)
Copy-out of the governed `ui_data.json` + real `ui_app.html` recipe into `/tmp/w91_teeth*`, then perturb + run:
- **T1** mutate a section payload (`a11y_audit`) with the manifest untouched → AUTH+INDEP `section_digests` **and**
  `root_digest` mismatch + governed-root mismatch RED — **the gap class**, invisible to W88/W89/W90.
- **T2** drop a section payload (keep its manifest digest) → AUTH missing + coverage + `key_count` RED.
- **T3** add an undigested top-level section → AUTH extra + INDEP mismatch + coverage + `key_count` RED.
- **T4** tamper a manifest `section_digest` value (payload untouched) → AUTH+INDEP mismatch RED.
- **T5** nested numeric mutation → RED.

Governed clone `ui_data.json` md5 `70b747a05c00d29bd6e286a7ee4cf42c` UNCHANGED throughout (copy-out only).

## Verification gates — GREEN
- **Gate C** — `launch_offline_gui.py --self-test`: `self_test_ok:true`, `engine_ready:true`. `run_model.py
  --n-outer 100 --n-inner 4 --no-tail --seed 42` smoke bit-match: **nested 49657.9 / gaussian 37499.0 / var-covar
  30267.9**.
- **Gate D** — `actuarial_gui.spec` AST-parses; `release.workflow.yml` valid YAML; `offline_bootstrap.py --self-test`
  ok (7/7); `build_phase_pkg_task1_validate.py` 26 checks pass (incl. `ui_app_byte_unchanged` +
  `governed_headline_present`).
- **Integrity** — `build_offline_home_validate.py` 177/177 (failed:[]); `offline_home_loader_parity.cjs` (node) 10/10;
  `ui_app_selftest_nojsdom.cjs` (node) 40/40; **new `ui_data_section_digest_recompute_parity.cjs` (node) 22/22**;
  governed-UI pytest cluster **+ W91 = 34 passed** (`test_offline_home_validate` 4 + W88 5 + W89 7 + W90 9 +
  nojsdom-wrapper 3 + **W91-wrapper 6**); MLMC suite 53/53. Repo-wide `--collect-only` = **3755 tests, 0 collection
  errors**.
- **Governed bytes byte-UNCHANGED** — `offline_home.html` md5 `03d6538d3cae9efb83062ecbfab096e9`; `ui_data.json` md5
  `70b747a05c00d29bd6e286a7ee4cf42c` / contract `1.23.0` / root_digest `456f7721…`; headline `39975.654628199336`.

## Engine lock
numpy 1.26.4 / scipy 1.13.1 / pandas 2.2.3 (`requirements-engine-lock.txt`) in `/tmp/eng_venv_w89` (reused); pytest
9.1.1.

## Coordination
Fresh throwaway clone (`/tmp/cc_20260630_050753`); mount `.git` untouched. Preflight PROCEED (owner null); lock
`2026-06-30T05:09Z-179f` acquired. Mount synced to `origin/main` post-push; lock released.

## Researched next improvement (registered W92, behind a hard near-duplicate guard)
**Governance-gate accretion is now SATURATED** — the offline-UI digest-integrity surface is fully pinned for BOTH the
embedded (`ui_app.html`) and standalone (`ui_data.json`) payloads by **value** (W88/W89), **structure** (W90), and
**recompute** (nojsdom embedded 40/40 + W91 standalone 22/22). Any further pure manifest/digest gate would be a
near-duplicate and is disallowed by the owner directive. The next cycle must do ONE of, in priority order: (1) a
genuinely **distinct** auto-admissible integrity gate *only if the gap is demonstrated first* (e.g. a full 26-section
embedded==standalone payload-equality proof — but confirm it is not already transitively implied by W91 + nojsdom +
manifest-equality before building, else skip); (2) a `MODEL_DEV_TASK_PROMPT.md`/docs documentation refresh
consolidating the W84–W91 integrity-gate map (no new gate); (3) opt-in estimator/efficiency work that leaves the
governed headline `39975.654628199336` byte-identical. **No further near-duplicate governance gate; no
model-FORM/contract/headline change** (those remain owner-gated, as does Phase 38 Task 3).
