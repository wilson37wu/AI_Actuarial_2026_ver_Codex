# Phase 11 Task 4: Performance Benchmarks and Memory Profiling

**Module:** `par_model_v2/projection/performance_benchmarks.py`  
**Tests:** `tests/test_performance_benchmarks.py`  
**Phase:** 11 — 100,000-Policy Processing and Reporting Cycle  
**Source ID:** PHASE11-T4-BENCH  
**Limitation ID:** PHASE11-T4-BENCH-LIMIT

---

## Overview

This module provides wall-clock timing, throughput measurement, and memory
profiling instrumentation for the Phase 11 educational actuarial processing
pipeline.  It benchmarks three pipeline stages:

1. **Portfolio generation** — synthetic 100k HK PAR policy table generation
   (Phase 11 Task 1).
2. **Chunked processing** — the `ChunkedProcessor` control-plane loop over
   policy chunks, with per-chunk timing instrumentation (Phase 11 Task 2).
3. **Governance overhead** — sign-off pack assembly simulation (Phase 11 Task 3).

An optional **scalability probe** runs the chunked processing at multiple
portfolio sizes to produce a throughput-vs-size curve for capacity planning.

---

## Components

### `BenchmarkTimer`

Context manager recording wall-clock elapsed seconds via `time.perf_counter`.
No external dependencies.  Typical use:

```python
with BenchmarkTimer() as t:
    do_work()
print(f"Elapsed: {t.elapsed_s:.3f} s")
```

### `MemoryTracer`

Context manager wrapping `tracemalloc` for peak Python heap allocation
measurement.  Reports both peak and current allocated memory in MiB.

```python
with MemoryTracer() as m:
    big_list = list(range(1_000_000))
print(f"Peak: {m.peak_mib:.2f} MiB")
```

### `ChunkTimingRecord`

Dataclass capturing timing for a single chunk: index, row count, elapsed
seconds, and throughput.

### `ChunkTimingStats`

Aggregate statistics over a vector of `ChunkTimingRecord` instances:
mean, median, P95, P99, min, max elapsed times and corresponding throughputs.
Constructed via `ChunkTimingStats.from_records(records)`.

### `StageBenchmarkResult`

Per-stage result collecting elapsed time, throughput, `tracemalloc` peak,
and POSIX peak RSS.  Serialisable to dict/JSON.

### `PerformanceBenchmarkReport`

Top-level report aggregating all stage results, per-chunk timing statistics,
overall throughput, and performance notes.  Supports:

- `write_json(path)` — serialise to JSON.
- `write_markdown(path)` — render a readable Markdown report.

### Benchmark functions

| Function | Description |
|----------|-------------|
| `benchmark_portfolio_generation(n_policies, seed)` | Time and profile portfolio generation. |
| `benchmark_chunked_processing(table, chunk_size, ...)` | Time chunked processing with per-chunk instrumentation. |
| `benchmark_governance_overhead(n_policies, n_chunks)` | Time sign-off pack assembly overhead. |
| `benchmark_scalability_probe(sizes, chunk_size, seed)` | Throughput curve at multiple portfolio sizes. |
| `run_phase11_benchmarks(n_policies, chunk_size, ...)` | Full benchmark suite orchestrator. |

---

## Educational Performance Targets

The following are *indicative* targets for the Python reference implementation
running with the stub chunk function (raw column sums).  Real projection
functions will be slower.

| Stage | Target throughput |
|-------|-------------------|
| Portfolio generation | ≥ 5,000 policies/s |
| Chunked processing (stub) | ≥ 20,000 policies/s |
| End-to-end (generation + processing) | ≥ 1,000 policies/s |

---

## Memory Measurement Notes

`tracemalloc_peak_mib` captures Python heap allocations only.  NumPy/Pandas
off-heap buffers (large array data) may not be fully captured.  For the most
comprehensive single-process memory metric on Linux/macOS, use
`peak_rss_mib` (from `resource.getrusage`); this field is `None` on Windows.

---

## Optimization Paths

1. **Vectorise portfolio generation** — use NumPy vectorised sampling and
   Pandas Categorical dtypes for product/age columns.
2. **Parallel chunk dispatch** — use `multiprocessing.Pool.map` or
   `concurrent.futures.ProcessPoolExecutor` to process chunks in parallel.
3. **SQLite checkpoint** — replace JSON checkpoint with SQLite for lower I/O
   overhead at high chunk counts.
4. **dtype downcasting** — use `float32` for financial columns where precision
   allows, halving the memory footprint of the policy DataFrame.
5. **Generator-based chunking** — process chunks as generators to avoid
   duplicating the full policy table in memory.

---

## Industry Standards Alignment

- **SOA ASOP 56 §3.6:** Model performance and scalability are model risk
  considerations; benchmark evidence informs model risk management decisions.
- **IA TAS M §3.5:** Model documentation should address computational
  performance limitations and their implications for reporting timelines.
- **ERM:** Performance benchmarks support operational risk controls: run-time
  estimates enable capacity planning, SLA setting, and escalation triggers for
  model run management.

---

## Limitations

- Benchmark timings are environment-dependent; cloud and CI sandboxes introduce
  scheduling jitter not present on dedicated workstations.
- `tracemalloc` does not capture off-heap allocations from NumPy/Pandas C extensions.
- The stub chunk function measures pipeline overhead only; real model projection
  functions must be benchmarked separately with representative inputs.
- All financial amounts are nominal and undiscounted; they are not suitable for
  valuation or reporting without further calculation.
- This module is for educational purposes and must not be used for production
  capacity planning without calibration to live workloads.

---

*Source ID: PHASE11-T4-BENCH | Limitation ID: PHASE11-T4-BENCH-LIMIT*
