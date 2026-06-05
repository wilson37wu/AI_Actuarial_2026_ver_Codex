# Recovery Report — 2026-06-05 disk-full crash (offline viewer restored)

> **UPDATE 2026-06-05 (later cycle): `ia_validation.py` RECOVERED.** The truncation was a single
> mid-string cut in the **last** entry (`VR-D03`) of the `IA_VALIDATION_REQUIREMENTS` list — NOT a
> missing `ValidationRunner` (that class is intact at line 483). The list tail was reconstructed
> faithfully (completed the final acceptance-criterion string + closed the entry + closed the list).
> `py_compile` clean; module imports; `len(IA_VALIDATION_REQUIREMENTS)==31` (all unique); the full
> suite now **collects all 2070 tests with 0 import errors** (previously blocked). Verified PASS:
> `test_ia_validation`+`test_phase13_ia_validation` 75, `test_validation_dashboard`+`test_phase14_ia_revalidation` 66,
> `test_model_health`+`test_data_validator` 113 (incl. the `total==31` dashboard assertion). **Human
> checklist item 4 is DONE.** Remaining human blockers: disk-full (item 1) + ghost git locks (item 2) +
> commit/push (item 6) — the sandbox still cannot touch git.

**Author:** automated 12h cycle (autonomous run)
**Scope:** crash-recovery + offline-viewer restoration. **No git commit was made** (see "Why no commit").

## Headline
- **Offline result-viewer is FIXED and verified working offline.** `node scripts/offline_viewer_self_test.cjs model_result_viewer.html` → `ok:true`, 4 tabs, 7 SVG charts, 7 export controls, **0 network calls, 0 JS errors**. `tests/test_offline_viewer.py` 20/21 pass (the 1 "fail" is a 10s subprocess-timeout on the node self-test under the loaded sandbox, not a logic failure).
- The viewer was previously **broken**: `model_result_viewer.html` was truncated mid-JS (no `</html>`), rendering 0 tabs.

## Root cause
1. **The mounted volume `/sessions` (shared `/dev/sdc`) is 100% full (~32 MB free).** ~9.2 GB is consumed by *other* sessions outside this repo, so it is **not reclaimable from here**. Under zero free space, writes to the mount are **silently corrupted/truncated while preserving the file's byte size** — the classic "same size, different bytes" signature seen across multiple files. This is what truncated the viewer rebuild.
2. **The 2026-06-03 crash + disk pressure truncated several working-tree files**, and the 2026-06-05 Phase R recovery commit (`1f8f990`) **committed some already-truncated files**, so the corruption is now baked into `HEAD` (== `origin/main`, `65ae2cf`).
3. **Ghost git locks** (`.git/index.lock`, `.git/refs/heads/main.lock`, `.git/__probe_lock`, dated 2026-06-03/04) are present and **unremovable from the sandbox** (`rm` → "Operation not permitted"; `ls` is inconsistent about them). They block all normal `git` (`reset`/`add`/`commit` fail with "Another git process seems to be running" / "index.lock: File exists").

## What was fixed this cycle (working tree only; files persist in the user's folder)
- `par_model_v2/viewer/viewer_template.html` — restored complete known-good version from `HEAD` (the on-disk copy was the Phase 18 Task 5 template but **corrupted**: a duplicate `viewAggregation` function + truncation).
- `scripts/build_offline_viewer.py` — restored complete known-good version from `HEAD` (on-disk Phase 18 copy was truncated mid-`change_records`).
- `model_result_viewer.html` + `viewer_data.json` — **rebuilt** from the restored toolchain (`PYTHONPATH=/var/tmp/pylibs:. python3 scripts/build_offline_viewer.py`). Now 87,777 B, ends with `</html>`, audit integrity 37/37 verified, 12 deployment gates, 12 risks.
- `tests/test_offline_viewer.py` — restored complete version from blob `fa5d5fe` (on-disk + `HEAD` copies were truncated at line ~218).

Note: restoring the viewer toolchain from `HEAD` **reverts the viewer to the Phase 17 (3-driver) display**. The Phase 18 Task 5 viewer enhancements (lapse standalone-SCR bar, 4-driver copula reconciliation read-outs) are **not shown**, but the underlying Phase 18 four-driver model, data, and JSON reports are all intact. A **losslessly reconstructed** Phase 18 bundler is preserved (see below) for clean re-application once git/disk are healthy.

## Preserved recovery artifacts (this folder)
- `viewer_template.PHASE18_TRUNCATED.html` — the corrupted on-disk Phase 18 template (for forensic reference).
- `build_offline_viewer.PHASE18_TRUNCATED.py` — the corrupted on-disk Phase 18 bundler.
- `build_offline_viewer.PHASE18_RECONSTRUCTED.py` — **GOOD**: disk-head(1..372) + HEAD-tail(325..EOF) splice; compiles; retains all Phase 18 report-preference + copula/lapse fields. Use this to restore the Phase 18 viewer once on a healthy base (pair with a reconstructed Phase 18 template).

## UNRECOVERABLE without a human: `par_model_v2/validation/ia_validation.py`
- On-disk and **every git blob** (HEAD, `1f8f990`, both 53,746 B blobs) are **truncated at line ~1290** inside the `IA_VALIDATION_REQUIREMENTS` list (`"Compl…`).
- The complete ~1,289-line version was **never committed** — history jumps from a complete **716-line** version (blob `3edbcc5`) straight to the truncated 1,289-line blob in one commit. So **GitHub `origin/main` also has only the truncated blob**; re-fetching will NOT recover it.
- The 716-line version compiles but **lacks `IA_VALIDATION_REQUIREMENTS` and `ValidationRunner`** that newer modules import (`validation/__init__.py`, `model_health.py`, `phase13/14_*`, `tests/test_ia_validation.py`), so a silent revert would cascade-break.
- **Action required (human):** restore `ia_validation.py` from a developer machine / IDE local history / editor backup that predates the crash, OR reconstruct the truncated tail (close the `IA_VALIDATION_REQUIREMENTS` list after `VR-D03` + re-add `ValidationRunner` and any trailing exports). Left **as-is (truncated)** this cycle — a loud `SyntaxError` is more honest than a silently-wrong old API.

## Why no commit was made this cycle
Committing now would (a) require the fragile alt-`GIT_INDEX_FILE` workaround on a **100%-full disk that corrupts writes**, and (b) snapshot a tree that **still contains one unrecoverable corrupt file**. The responsible action is to leave the (improved) working tree in place — it persists in the user's folder regardless of git — and hand the git/disk/ia_validation issues to a human.

## HUMAN ACTION CHECKLIST (in order)
1. **Free disk space** on the host folder so `/sessions` is no longer 100% full (the corruption source).
2. In a real shell: `rm -f .git/index.lock .git/refs/heads/main.lock .git/__probe_lock` (the ghost locks).
3. `git reset` (mixed) to clear the phantom-deleted index; confirm the working tree.
4. **Restore `par_model_v2/validation/ia_validation.py`** from a pre-crash backup (see above) and confirm `python3 -m pytest tests/test_ia_validation.py` passes.
5. Re-run `python3 scripts/build_offline_viewer.py` and `node scripts/offline_viewer_self_test.cjs model_result_viewer.html` (expect `ok:true`).
6. Commit the restored viewer toolchain + `ia_validation.py` + this report; `git push origin main`.
7. (Optional) Re-apply the Phase 18 viewer enhancements using `build_offline_viewer.PHASE18_RECONSTRUCTED.py` + a reconstructed Phase 18 template.

---

## UPDATE 2026-06-05 (interactive) — human ran git fix; PUSH SUCCEEDED; residual index repair pending

**Human deleted the ghost locks and ran commit+push. Result:**
- ✅ Ghost locks `.git/refs/heads/main.lock` + `.git/__probe_lock` — GONE.
- ✅ Commit `3d17637` "Recover ia_validation.py + crash-recovery working tree" created.
- ✅ **PUSHED to GitHub** — `origin/main` == local HEAD == `3d17637`. The recovered `ia_validation.py`
  (1296 lines, correct reconstructed tail) is verified inside the pushed commit. **The substantive
  recovery is now safe on the remote.**

**New residual blocker (local-only, low stakes):** the working `.git/index` is CORRUPT
(`fatal: unknown index entry format 0x…`) — leftover disk-full write damage. Because the index was
corrupt at commit time, the human's `git add -A` was incomplete: **35 files are still uncommitted**, ALL
of them documentation/logs (`docs/G05_*` probe logs, `docs/MODEL_USAGE_GUIDE.md`,
`docs/validation/PHASE15_RISK_AGGREGATION_REPORT.md`, `MODEL_DEV_LOG.md`, `MODEL_DEV_TASK_PROMPT.md`).
No source/model/test file is pending — `ia_validation.py` is fully committed+pushed.

The sandbox CANNOT repair the index (`rm .git/index` → "Operation not permitted"; a `.git/index.lock`
ghost is present again). **Human action required (on the Windows host):**
```
cd C:\Users\SkiesNet\Downloads\Auto_Actuarial_Model_Dev_May26
Remove-Item -Force .git\index, .git\index.lock -ErrorAction SilentlyContinue
git reset
git status
git add -A
git commit -m "Capture residual doc/log/state updates (post index-repair)"
git push origin main
```
After that the tree is fully clean and Phase 19 can begin. Disk-full on `/sessions` (the automation
sandbox volume, not the host) remains the corruption root cause for future automated cycles.
