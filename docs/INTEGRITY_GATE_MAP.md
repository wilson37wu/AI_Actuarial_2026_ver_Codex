# Offline-UI Integrity-Gate Map (W84–W91)

**Status:** consolidating reference (W92, 2026-06-30, claude AUTO). Documentation only —
no new gate, no model-FORM/contract/headline change, governed bytes byte-unchanged.

## Purpose

Cycles W84–W91 added eight CI gates that together pin the **offline-UI integrity surface**:
the governed display artifacts (`offline_home.html`, `ui_data.json`, `ui_app.html`) and the
node guards that prove they are mutually consistent and untampered. The gates were added one
per cycle and their scopes are documented only in the per-cycle `docs/cycle_status/` files.
This map is the single place that states **what each gate pins, on which payload, and why it
is distinct from its neighbours** — so the next agent can tell at a glance whether a proposed
new gate is genuinely additive or a near-duplicate. (Governance-gate accretion is **saturated**;
see "Saturation & the transitive closure" below.)

## The two payloads

The integrity surface has **two** copies of the same 26-section model-output payload:

- **EMBEDDED** — the payload baked inside `ui_app.html` (the single-file app).
- **STANDALONE** — `ui_data.json`, the file `offline_home.html` loads at runtime (and into
  which a user may drag-drop a different snapshot).

Each payload carries a `contract_manifest` with a SHA-256 `section_digest` per top-level
section and a `root_digest` = sha256 over the canonical section-digest map. Both manifests are
pinned to the **same** governed `root_digest`
`456f772166a1198363e16c7ccc68f87175ab4e4fa289cc0e798a009f1b257d01`.

## Gate inventory

| Cycle | File | Kind | Payload / surface | Pins / asserts | Teeth |
|---|---|---|---|---|---|
| **W84** | `tests/test_ui_app_selftest_nojsdom.py` → `scripts/ui_app_selftest_nojsdom.cjs` | node guard + pytest wrapper (SKIP if no node) | EMBEDDED (`ui_app.html`) | Recomputes all 26 section digests + root from the embedded payload vs the embedded manifest; asserts `ok`, `failed==[]`, `passed==checks`, `checks>=40` | inject remote `<link href="https://…">` into a copy → 39/40, exit 1 |
| **W85** | `tests/test_offline_home_loader_parity.py` → `scripts/offline_home_loader_parity.cjs` | node guard + pytest wrapper (SKIP if no node) | `offline_home.html` ↔ `ui_data.json` | Loader-parity: the figures `offline_home.html` renders equal the values baked from `ui_data.json`; asserts `ok`, `failed==[]`, `checks>=10` | force `figure[0] JS!=baked` in a copy → 9/10, exit 1 |
| **W86** | `tests/test_nojsdom_guards_are_collected.py` | pure-Python meta-gate (no node, never SKIP) | `scripts/*.cjs` × `tests/` | Every jsdom-FREE `.cjs` guard basename is referenced by a pytest wrapper — no orphan guard can silently stop running | inject an uncollected jsdom-free guard into an isolated copy → fail |
| **W87** | `tests/test_gitignore_covers_junk_probes.py` | pure-Python meta-gate (`git check-ignore`, SKIP if no git) | `.gitignore` × `AGENT_COORDINATION.md` §6 | A representative path from **every** documented junk/probe family is git-ignored — enforces "junk never gets committed" in CI, not by convention | a family path that is not ignored → fail |
| **W88** | `tests/test_governed_offline_ui_byte_anchors.py` | pure-Python (`hashlib`, never SKIP) | governed raw bytes + scalars | Pins the 3 governed offline-UI **value** anchors: `offline_home.html` md5 `03d6538d…`, `contract_version` semver `1.23.0`, headline `39975.654628199336` | proves `md5(raw + b"\x00") != governed` (non-vacuous) |
| **W89** | `tests/test_ui_data_contract_manifest_digest.py` | pure-Python (`hashlib`, never SKIP) | STANDALONE manifest **values** | Pins `ui_data.json` machine digests: `root_digest == 456f7721…` (literal) and the `contract_version` section digest; **re-derives** both from the live payload (recipe) and proves `root == sha256(canonical(section_digests))` | perturb a section digest → recomputed root != governed |
| **W90** | `tests/test_ui_data_contract_manifest_structure.py` | pure-Python (no node, never SKIP) | STANDALONE manifest **structure** | Pins manifest **structural completeness**: every payload section has a digest, each is valid sha256 hex, manifest section set == payload section set — i.e. the manifest faithfully and completely describes the real payload | drop/add a section in a scratch copy → fail |
| **W91** | `tests/test_ui_data_section_digest_recompute_parity.py` → `scripts/ui_data_section_digest_recompute_parity.cjs` | node guard + pytest wrapper (SKIP if no node) | STANDALONE payload → digest | Recomputes all 26 section digests + root from the **standalone** `ui_data.json` **two ways** (the page's own authoritative serialiser + an independent `node:crypto` path) vs the manifest and the governed root; `checks>=22` | mutate a section payload with the manifest untouched → AUTH+INDEP section + root mismatch RED (the gap class W88/W89/W90 cannot see) |

## How the gates compose (coverage by axis)

| Axis | EMBEDDED (`ui_app.html`) | STANDALONE (`ui_data.json`) |
|---|---|---|
| payload → digest **recompute** | W84 (nojsdom, 40 checks) | W91 (22 checks, two independent recipes) |
| manifest digest **values** | W88 (governed root + byte anchors) | W89 (root + contract_version section, re-derived) |
| manifest **structure** | — (shares the recompute via W84) | W90 (completeness + faithfulness) |
| rendered-figure **parity** | — | W85 (`offline_home.html` ↔ `ui_data.json`) |
| raw-byte **anchor** | W88 (`offline_home.html` md5) | W89/W91 (root pin) |
| **meta** (gates keep running, junk excluded) | W86 (no orphan guards), W87 (junk git-ignored) | same |

## Saturation & the transitive closure (why no further pure digest/manifest gate is admissible)

Because the **same** authoritative serialiser+sha256 recipe is applied on both sides, and both
manifests are pinned to the **same** collision-resistant `root_digest`:

```
recipe(EMBEDDED payload)   == EMBEDDED manifest digests      (W84 nojsdom, all 26 + root)
recipe(STANDALONE payload) == STANDALONE manifest digests    (W91, all 26 + root, two ways)
EMBEDDED manifest.root == STANDALONE manifest.root == 456f7721…   (W88 + W89 governed pin)
```

`root_digest` is sha256 over the canonical map of all 26 section digests, so **equal roots ⟹
equal section-digest maps** (sha256 collision resistance). Combined with the two recompute
gates, `recipe(EMBEDDED section) == recipe(STANDALONE section)` for all 26 sections ⟹ their
canonical serialisations are equal (sha256 preimage resistance). **Therefore a "full 26-section
embedded == standalone payload-equality" gate is already transitively implied** by
W84 + W91 + the shared root pin, and would be a near-duplicate. This is the candidate the W91
hand-off registered for W92 with the instruction "confirm it is not already transitively
implied … else skip" — it is implied, so it was **skipped** (W92, this doc).

The offline-UI digest-integrity surface is **fully pinned** for both payloads by value
(W88/W89), structure (W90), and recompute (W84 embedded / W91 standalone). Any further pure
manifest/digest gate is disallowed by the owner directive against near-duplicate governance
gates.

## What is still open (and gated)

- **Phase 38 Task 3** — fold Cash Flows + Products + the Phase 37 Scenario Explorer into the
  byte-pinned `ui_app.html` as native tabs. **OWNER-GATED**: requires an owner sha256
  re-baseline across the gate scripts above + a `ui_data.json` contract bump. Left
  `in_progress`; not executed by the auto cycle.
- **Admissible next steps** (priority order, per the W91/W92 hand-off): a genuinely *distinct*
  integrity gate **only if a new gap is demonstrated first**; else a documentation refresh (this
  map); else opt-in estimator/efficiency work that leaves the headline `39975.654628199336`
  byte-identical. **No** further near-duplicate governance gate; **no** model-FORM / contract /
  headline change without owner sign-off.

## Governed anchors (for quick reference)

| Artifact | Anchor |
|---|---|
| `offline_home.html` | md5 `03d6538d3cae9efb83062ecbfab096e9` |
| `ui_data.json` | md5 `70b747a05c00d29bd6e286a7ee4cf42c` · contract `1.23.0` · root `456f772166a1198363e16c7ccc68f87175ab4e4fa289cc0e798a009f1b257d01` |
| `ui_app.html` | sha256 `d82c65ec…` (pinned by `build_phase_pkg_task1_validate`) |
| headline SCR | `39975.654628199336` |
| engine smoke (`run_model --n-outer 100 --n-inner 4 --no-tail --seed 42`) | nested `49657.9` / gaussian `37499.0` / var-covar `30267.9` |

*Maintenance: when an owner-approved change re-baselines any anchor above, update this table and
the affected gate row in the same cycle as the contract bump.*
