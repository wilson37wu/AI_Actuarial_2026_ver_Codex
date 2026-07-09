# Cycle Status — 2026-07-10 — #10: 100k-policy batch performance profile

**Agent:** claude (scheduled task `actuarial-model-daily-improvement`)
**Item:** roadmap §4.1 #10 (Expansion-plan §2.6) — highest-priority OPEN general-backlog item; completes §4.1 #1–#10
**Lock:** acquired/released per `AGENT_COORDINATION.md` (cycle 2026-07-09T17:07Z-f16d)

## Outcome

DoD: "**≥20% runtime cut on benchmark or documented finding that none is
available**." This cycle delivers the **documented finding** branch with a
reproducible benchmark, PLUS the safe sub-20% optimisation that *is* available.

**Finding.** The single largest cost in the 100,000-policy deterministic batch
is the SHA-256 **reproducibility digest** of the generated portfolio, computed
via pandas `DataFrame.to_csv` — the top-`tottime` function in a cProfile of the
batch is pandas' `io.formats.csvs._save_chunk`, at **~70%** of the 100k
generation runtime (digest 366 ms of 526 ms). The batch is *digest-bound*, not
model-compute-bound. That digest's byte output **defines** the governed
reproducibility value recorded on every run, so it **cannot be reduced by
output-identical means**.

## What was built

- `par_model_v2/projection/batch_perf_profile.py` (numpy/pandas + stdlib only;
  no scipy, no new dependency) — the reproducible profiling harness:
  - `time_stage` / `top_hotspots` (cProfile) / `decompose_generation`
    (digest vs modelling compute) / `compare_digest_schemes` /
    `measure_safe_optimization` (with a byte-identity gate) and a
    `PerfProfileReport` (`to_dict`/`to_json`/`to_markdown`).
  - `inputs_digest` hashes the run inputs (config + schema), NOT the
    environment-dependent timings, so re-run identity is idempotent.
- `par_model_v2/projection/portfolio_generator.py` — **safe, byte-identical
  optimisation applied**: NEW internal `_portfolio_digest_presorted(table)`;
  `generate_hk_par_portfolio` now digests the already-canonical frame it just
  built (skips a redundant re-sort + column re-subset that `portfolio_digest`
  performs defensively). The public `portfolio_digest` API is unchanged. Saves
  ~11.5% of generation (~630→~530 ms); **below** the 20% bar.
- `scripts/build_perf_profile_100k.py` — evidence builder →
  `docs/validation/PERF_PROFILE_100K.json` (schema `perf-profile-100k-1.0`,
  `inputs_digest 2f5db6d1…`, UNSIGNED) + `docs/PERF_PROFILE_100K_CARD.md`.
- `docs/MODEL_STABILITY_AND_LIMITATIONS.md` §3.10 pointer.

## Governance

Purely additive. The governed TVOG/aggregation headline is UNTOUCHED, and the
portfolio **reproducibility digest VALUE is unchanged** and regression-locked
(n=500 `fa7e1496…`, default-100k `321f50d8…`). A ≥20% cut IS achievable — a
column-buffer-hash digest runs **~78% faster** (391 ms → 87 ms) — but it CHANGES
the governed digest value (`values_differ=True`); it is surfaced as an
**OWNER-GATED re-baseline** of the reproducibility-digest scheme and is NOT
self-approved.

## Tests

- NEW `tests/test_batch_perf_profile.py` — **14/14 GREEN** (unittest,
  numpy/pandas): digest byte-identity + pinned governed hashes; top-hotspot is
  the digest; the owner-gated buffer-hash scheme genuinely differs; report
  serialisation; idempotent inputs digest; the harness does not perturb the
  governed digest. No flaky absolute-ms assertions.
- Regression via a minimal pytest shim (scipy/pytest unavailable in the
  network-restricted sandbox): test_portfolio_generator 25, test_chunk_processor
  52, test_chunked_processor 46, test_performance_benchmarks 63,
  test_educational_reporting_pack 50, test_user_inputs_integration 19,
  test_pc2_mechanic_families 23 — **292 GREEN** across the affected surface.
  scipy-transitive suites (e.g. test_phase24_task1) remain pre-existingly
  collection-blocked, unrelated to this change.

## Next

§4.1 #11 — mortality improvement + credibility blending (ASOP 25) for qx tables.
Owner action available: sign off the digest-scheme re-baseline to unlock the
≥20% batch speed-up (`docs/PERF_PROFILE_100K_CARD.md`).
