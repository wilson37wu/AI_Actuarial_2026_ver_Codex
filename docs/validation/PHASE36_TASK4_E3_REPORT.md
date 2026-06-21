# Reproducibility Evidence-Pack Export — Validation Report (Phase 36 Task 4, gap E3)

**Doc** `PHASE36_TASK4_E3_REPORT` v1.0.0 | Phase 36: Offline UI Accessibility Completion & Educational Reproducibility | classification educational | model parameter changes: **NONE** | contract **1.21.0 (UNCHANGED)** | result: **PASS**

## Summary

Closed gap **E3** of the Phase 36 design note. Added one in-browser action — the **"Reproducibility evidence pack"** toolbar button — that serialises the **exact embedded `ui_data` payload bytes** to a single downloaded file via the existing `downloadText`/`downloadBlob` Blob plumbing. The exported bytes are **byte-identical** to the embedded payload (and to `ui_data.json`), which already carries `contract_manifest.section_digests` (24) + `root_digest` and the build/provenance stamp, so a reviewer receives **independently digest-verifiable** evidence of exactly what the UI displayed. Display/JS only: **no contract change**, no new `ui_data` key, every governed read-out renders bit-for-bit.

## What changed

1. **`ui_app.html` — one new toolbar action.** A `btnEvidencePack` button ("Reproducibility evidence pack") plus two JS helpers: `getEmbeddedRaw()` (re-reads the `#ui-data` script element, strips `/*__UI_DATA__*/`, trims — yielding the exact embedded payload bytes) and `exportEvidencePack()` (downloads those bytes as `reproducibility_evidence_pack_v<contract>_<root8>.json`). Wired into the existing `wireToolbar` map.
2. **Provenance stamp in the filename.** The download name carries the contract version and the first 8 hex of `contract_manifest.root_digest`, so a reviewer sees the provenance without opening the file; the full manifest + `meta.generated_utc` / `source_files` / `generated_by` are inside the byte-identical payload.
3. **Integrity-tab note.** A read-only note (`data-e3-note`) on the content-integrity panel points reviewers to the export and states it recomputes no model figure.
4. **No contract change.** The export reuses the embedded snapshot and existing manifest; `ui_data.json` and the embedded payload are **byte-identical**, so the Phase 35 Task 3 (gap A2) per-section SHA-256 digests still verify in-browser by construction. No new top-level key.
5. **Offline-safe.** The export path makes **no network call** and uses **no storage API** (Blob + `<a download>` only); it works under `file://`.

## Acceptance criteria (pre-registered in the Phase 36 design note) — all met

- the exported payload bytes equal the embedded `ui_data` bytes; the exported `section_digests`/`root_digest` recompute and match (verified by the existing in-browser verifier and a dedicated fallback test) — **met**
- the export performs no network call and uses no storage API; works under `file://` — **met**
- a hash is not a model figure: the governed headline and all governed read-outs render bit-identically; the export recomputes no model quantity — **met**
- new self-test checks cover the export control presence and byte/digest equality via a jsdom fallback test; suite stays ok:true 0/0 — **met** (+12 checks; new `ui_app_evidence_pack_fallback_test.cjs`)
- `ui_app_self_test.cjs` ok:true, 0 network, 0 JS errors; zero-install preserved — **met** (405 checks; 0 external refs)
- NO model parameter changes; stop-rule honoured; owner decision not pre-empted — **met**

## Evidence

The new jsdom fallback test (`ui_app_evidence_pack_fallback_test.cjs`) captures the bytes the button hands to the download plumbing and asserts: **byteIdentical** to the embedded payload; **filenameStamped** (`reproducibility_evidence_pack_v1.21.0_85a4f7c2.json`); **noStorageUsed**; and digest-verifiability by **re-embedding the exported bytes into a fresh UI instance** — the existing in-browser content-integrity verifier reports **INTEGRITY VERIFIED**, root digest match, 0 altered rows — with 0 network / 0 JS errors.

| Self-test | ok | checks |
|---|---|---|
| ui_app_self_test | true | 405 (+12) |
| ui_app_evidence_pack_fallback_test (new) | true | 12 |
| ui_app_integrity_fallback_test | true | 10 |
| ui_app_distribution_fallback_test | true | 9 |
| ui_app_userrun_fallback_test | true | 9 |
| ui_app_search_deeplink_test | true | 18 |
| ui_app_bundle_printall_test | true | 21 |
| offline_viewer_self_test | true | 11 |
| combined_gui_self_test | true | 27 |
| **total** | **9/9 ok** | **522** |

Pytests: `tests/test_phase36_task4_e3_evidence_pack.py` — **14 passed** (13 Python-level + 1 jsdom fallback gate). Contract/digest/pipeline regression (`test_phase34_task2_h1`, `test_phase35_task3_a2_digests`, `test_ui_contract_pipeline_reconcile`) — **21 passed**. External refs 0; network 0; JS errors 0.

## Governance

ChangeRecord `d9cab0e655c246c0b696361ec901ecc6` (`code_change`, **OWNER_REVIEW**); audit integrity verified True. Change records 98 → 99; audit entries 126 → 127; risk register 17 (unchanged — MR-016/MR-017 remain OPEN, owner decision not pre-empted).

## Invariants honoured

NO model parameter changes · Phase 30 binding stop-rule honoured · MR-016/MR-017 owner decision not pre-empted · zero-install / single self-contained `file://`-safe HTML preserved · NO contract change (display/JS only; embedded payload byte-identical) · the export surfaces the embedded snapshot bit-for-bit and recomputes nothing.

## Note on build architecture

Like the Phase 36 Task 2 (E1) live-region patch, E3 is a standalone, idempotent, anchor-asserted post-build HTML patch (`scripts/build_phase36_task4_e3_evidence_pack.py`) applied to the committed `ui_app.html`; it is **not** a `ui_data` contract layer, so it is intentionally absent from `build_ui_pipeline.LAYERS` (which governs only the `ui_data.json` contract reconcile). Re-running the patch is a no-op (`applied=0`).
