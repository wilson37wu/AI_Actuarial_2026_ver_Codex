# Verification Runbook — full gate battery from a clean clone

**Status:** operational runbook (W93, 2026-06-30, claude AUTO). Documentation only —
no new gate, no model-FORM/contract/headline change, governed bytes byte-unchanged.

## Purpose & scope

This is the single **operational** procedure for reproducing **every** verification gate
the auto-cycle must keep GREEN, from a fresh `origin/main` clone, with the exact commands,
the pinned engine environment, the expected outputs, and the known gotchas.

It is deliberately **distinct** from the neighbouring docs (checked before writing, so this
is additive, not a near-duplicate):

- `docs/INTEGRITY_GATE_MAP.md` (W92) maps only the **eight offline-UI integrity gates**
  (W84–W91) and argues their *saturation*. It does **not** cover Gate C (engine bit-match),
  Gate D (packaging recipe), or the MLMC suite, and it is a conceptual coverage matrix, not a
  run procedure.
- `docs/cycle_status/LATEST_CYCLE_STATUS_*_verify*.md` are **point-in-time** per-cycle
  snapshots, not a reusable, environment-pinned procedure.

If you only want to know *what each integrity gate pins and why no more are needed*, read the
gate map. If you want to *actually run the whole battery and know what GREEN looks like*, use
this runbook.

## 0. Engine environment (pinned)

The stochastic engine is reproducible **only** on the pinned lock
(`requirements-engine-lock.txt`): **numpy 1.26.4 / scipy 1.13.1 / pandas 2.2.3**, CPython
3.9–3.12. The sandbox default interpreter ships newer/absent versions (e.g. numpy 2.x, no
scipy), which will **not** bit-match. Build a throwaway venv:

```bash
python3 -m venv /tmp/eng_venv                # use a fresh timestamped name if a stale
                                             # /tmp/eng_venv is owned by 'nobody'
/tmp/eng_venv/bin/pip install -q numpy==1.26.4 pandas==2.2.3 scipy==1.13.1
/tmp/eng_venv/bin/pip install -q pytest pyyaml    # test runner + workflow-YAML check
/tmp/eng_venv/bin/python -c "import numpy,scipy,pandas;print(numpy.__version__,scipy.__version__,pandas.__version__)"
# -> 1.26.4 1.13.1 2.2.3
```

Node (for the `.cjs` integrity gates) is the system `node` (v22.x verified); no install needed.

Throughout, `PY=/tmp/eng_venv/bin/python`.

## 1. Coordination preflight (Claude Cowork)

Do **all** git in a fresh throwaway clone — never touch the mounted `.git` (virtiofs forbids
deletes → ghost locks). See `AGENT_COORDINATION.md` for the authoritative protocol.

```bash
git clone "$(git -C <mount> remote get-url origin)" /tmp/cc_$(date -u +%Y%m%d_%H%M%S)
cd /tmp/cc_*                                  # this clone is the source of truth
python3 scripts/agent_lock.py preflight --owner claude   # exit 10 = YIELD, stop
python3 scripts/agent_lock.py acquire  --owner claude --task "<in_progress task>"
```

## 2. Gate C — offline GUI + engine bit-match

```bash
$PY scripts/launch_offline_gui.py --self-test          # expect self_test_ok:true engine_ready:true
$PY scripts/run_model.py --n-outer 100 --n-inner 4 --no-tail --seed 42
# expect EXACTLY: run_model: nested SCR 49657.9 | gaussian copula SCR 37499.0 | var-covar 30267.9
```

The three SCR values are a **frozen reference**; any drift is a Gate-C failure (wrong engine
env is the most common cause).

> **Doc-only hygiene (important).** `run_model.py` **rewrites**
> `docs/validation/RUN_MODEL_AGGREGATION_REPORT.json` and `docs/validation/RUN_MODEL_SUMMARY.json`
> in the clone. These are engine output, not part of a doc/verification cycle's deliverable —
> revert them before committing so the commit stays scoped:
> `git checkout -- docs/validation/RUN_MODEL_AGGREGATION_REPORT.json docs/validation/RUN_MODEL_SUMMARY.json`

## 3. Gate D — packaging recipe (build stays owner/CI-gated)

```bash
$PY -c "import ast;ast.parse(open('packaging/actuarial_gui.spec').read());print('spec AST OK')"
$PY -c "import yaml;yaml.safe_load(open('packaging/release.workflow.yml'));print('workflow YAML OK')"
$PY packaging/offline_bootstrap.py --self-test         # expect every check "ok": true
$PY scripts/build_phase_pkg_task1_validate.py          # expect n_pass == n_checks (26/26)
```

Producing the per-OS signed binaries is the documented **owner/CI** step (no
`.github/workflows` activation, no `v*` tag in-sandbox). That is correct, not a Gate-D failure.

## 4. Integrity gates (offline-UI surface)

```bash
$PY scripts/build_offline_home_validate.py             # expect checks 177 / passed 177 / failed []
$PY -m pytest tests/test_offline_home_validate.py -q   # expect 4 passed
node scripts/offline_home_loader_parity.cjs            # expect passed 10 / failed []
node scripts/ui_app_selftest_nojsdom.cjs               # expect checks 40 / passed 40   (EMBEDDED recompute)
node scripts/ui_data_section_digest_recompute_parity.cjs  # expect checks 22 / passed 22 (STANDALONE recompute)
```

The two `.cjs` recompute gates independently re-derive the EMBEDDED (`ui_app.html`) and
STANDALONE (`ui_data.json`) 26-section digest manifests; together with the shared governed
`root_digest` they imply embedded == standalone payload equality (see `INTEGRITY_GATE_MAP.md`
for the transitive-closure argument — that is why no further payload-equality gate is added).

## 5. MLMC suite (53 tests) — run in batches

The full `tests/test_mlmc_*.py` run exceeds a single 45 s sandbox window. Split it (each batch
< 45 s) — this is an execution gotcha, not a flakiness signal:

```bash
$PY -m pytest tests/test_mlmc_inner_estimator.py tests/test_mlmc_stage3_wiring.py -q   # 16 passed (~28 s)
$PY -m pytest tests/test_mlmc_tail_estimator.py  tests/test_mlmc_tail_stage3.py  -q   # 15 passed (~30 s)
$PY -m pytest tests/test_mlmc_tail_stage4.py     tests/test_mlmc_tail_stage4b.py -q   # 22 passed (~18 s)
# total 53/53
```

## 6. Governed byte-stability anchors

Governed artifacts must be **byte-identical** unless the cycle is an approved model-form / UI
change with a contract bump. Confirm:

| Artifact | Anchor | Expected value |
|---|---|---|
| `offline_home.html` | md5 | `03d6538d3cae9efb83062ecbfab096e9` |
| `ui_data.json` | md5 | `70b747a05c00d29bd6e286a7ee4cf42c` |
| `ui_data.json` | `contract_version` | `1.23.0` |
| `ui_data.json` | `contract_manifest.root_digest` | `456f772166a1198363e16c7ccc68f87175ab4e4fa289cc0e798a009f1b257d01` (26 section digests) |
| `ui_app.html` | sha256 | `d82c65ecc7f7130a07b34d55c9500e93e23dd71626d18c3002c4e0777bd1fee6` |
| headline SCR | literal in `ui_data.json` | `39975.654628199336` |

```bash
md5sum offline_home.html ui_data.json
sha256sum ui_app.html
$PY -c "import json;d=json.load(open('ui_data.json'));print(d['contract_version'],d['contract_manifest']['root_digest'])"
grep -c 39975.654628199336 ui_data.json    # expect 1
```

A governed re-baseline (new md5/sha256/root_digest/contract/headline) is **owner-gated** and
must update these anchors **and** the affected gate scripts **in the same commit** as the
contract bump.

## 7. Close-out

```bash
git fetch origin && git rebase origin/main && git push origin HEAD:main   # retry up to 3x
python3 scripts/agent_lock.py release --owner claude
# then sync the mount to origin/main (md5 diff per git ls-files; .agent_lock.json is dynamic, ignore)
```

## Expected-GREEN summary (one glance)

| Gate | Command | GREEN |
|---|---|---|
| C self-test | `launch_offline_gui.py --self-test` | `self_test_ok:true`, `engine_ready:true` |
| C bit-match | `run_model.py --n-outer 100 --n-inner 4 --no-tail --seed 42` | nested **49657.9** / gaussian **37499.0** / var-covar **30267.9** |
| D spec | `ast.parse(actuarial_gui.spec)` | parses |
| D workflow | `yaml.safe_load(release.workflow.yml)` | valid |
| D bootstrap | `offline_bootstrap.py --self-test` | all `ok:true` |
| D pkg gate | `build_phase_pkg_task1_validate.py` | 26/26 |
| Integrity home | `build_offline_home_validate.py` | **177/177** |
| Integrity pytest | `test_offline_home_validate.py` | **4 passed** |
| Integrity parity | `offline_home_loader_parity.cjs` | **10/10** |
| Integrity embedded | `ui_app_selftest_nojsdom.cjs` | **40/40** |
| Integrity standalone | `ui_data_section_digest_recompute_parity.cjs` | **22/22** |
| MLMC | `tests/test_mlmc_*.py` (3 batches) | **53/53** |
| Byte-stability | md5 / sha256 / contract / headline | all anchors unchanged (§6) |

*Last reproduced end-to-end: W93, 2026-06-30, claude AUTO, all GREEN.*
