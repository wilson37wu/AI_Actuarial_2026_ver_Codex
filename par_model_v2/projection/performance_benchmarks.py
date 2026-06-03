"""
Phase 11 Task 4: performance benchmarks and memory profiling for the
100,000-policy HK PAR educational portfolio processing pipeline.

This module provides timing, throughput, and memory instrumentation for the
key components of the Phase 11 educational actuarial processing cycle:

* **Wall-clock timing** – per-stage and per-chunk latency using
  :func:`time.perf_counter`.
* **Memory profiling** – peak allocated memory via :mod:`tracemalloc`
  (Python stdlib; zero extra dependencies).
* **Throughput metrics** – policies processed per second for each stage.
* **Per-chunk statistics** – mean, median, P95, and P99 chunk processing times
  derived from the recorded per-chunk latency vector.
* **Benchmark report** – structured :class:`PerformanceBenchmarkReport`
  serialisable to JSON and Markdown for model governance evidence.

Design notes
------------
The benchmark module uses only Python stdlib and NumPy (already a core
dependency).  ``tracemalloc`` is enabled for the duration of each benchmark
and disabled afterwards to avoid long-running overhead.  ``resource.getrusage``
is used on POSIX systems (Linux / macOS) for peak resident set size (RSS);
a graceful fallback is provided for Windows and sandboxed environments.

Performance targets (educational)
-----------------------------------
The following are indicative targets for the Python-reference implementation
and are not production commitments.  An optimised NumPy/Pandas implementation
on a modern workstation should achieve:

- Portfolio generation (100k policies): < 10 seconds.
- Chunked processing (10k-policy chunks, stub fn): < 1 s per chunk.
- Full 100k-policy stub run: < 60 seconds end-to-end.
- Reporting-cycle governance overhead: < 5 seconds.

Limitations
-----------
This is an educational reference.  Memory measurements capture Python heap
allocations recorded by ``tracemalloc``; they exclude C-extension off-heap
allocations (e.g. NumPy buffer pools, Pandas Categoricals) unless those arrays
are created through the Python allocator.  Peak RSS is the most comprehensive
memory metric on POSIX systems.  Benchmarks performed in a cloud or CI sandbox
may show higher variability than a dedicated workstation.

SOA / IA / ERM standards references
--------------------------------------
- SOA ASOP 56 §3.6: Model performance and scalability are model risk
  considerations; benchmark evidence supports model risk management.
- IA TAS M §3.5: Model documentation should include limitations related to
  computational performance and scalability.
- ERM: Performance benchmarks inform capacity planning and operational risk
  controls for model run management.
"""

from __future__ import annotations

import json
import time
import tracemalloc
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from par_model_v2.projection.chunk_processor import (
    RECONCILE_COLS,
    ChunkedProcessor,
    ChunkedProcessorConfig,
    ReconciliationReport,
)
from par_model_v2.projection.portfolio_generator import (
    PortfolioGenerationConfig,
    generate_hk_par_portfolio,
    portfolio_summary,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_BENCHMARK_VERSION = "1.0.0"

# Indicative throughput targets (policies/second) for educational reference.
# Below these values the benchmark report flags a NOTE (not a FAIL).
_TARGET_PORTFOLIO_GEN_POLICIES_PER_SEC = 5_000
_TARGET_CHUNK_POLICIES_PER_SEC = 20_000
_TARGET_FULL_RUN_POLICIES_PER_SEC = 1_000


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _peak_rss_mib() -> Optional[float]:
    """Return peak resident set size in MiB on POSIX; ``None`` on Windows."""
    try:
        import resource  # type: ignore[import]
        usage = resource.getrusage(resource.RUSAGE_SELF)
        # Linux reports in kilobytes; macOS in bytes.
        import sys
        if sys.platform == "darwin":
            return usage.ru_maxrss / (1024 * 1024)
        return usage.ru_maxrss / 1024
    except (ImportError, AttributeError):
        return None


# ---------------------------------------------------------------------------
# Timer context manager
# ---------------------------------------------------------------------------

class BenchmarkTimer:
    """Context manager that records elapsed wall-clock time in seconds.

    Usage::

        with BenchmarkTimer() as t:
            do_work()
        print(t.elapsed_s)  # seconds as float

    Attributes
    ----------
    elapsed_s:
        Wall-clock seconds elapsed inside the ``with`` block.  Set to ``None``
        before the block exits.
    """

    def __init__(self) -> None:
        self.elapsed_s: Optional[float] = None
        self._start: float = 0.0

    def __enter__(self) -> "BenchmarkTimer":
        self._start = time.perf_counter()
        return self

    def __exit__(self, *_: Any) -> None:
        self.elapsed_s = time.perf_counter() - self._start


# ---------------------------------------------------------------------------
# Memory tracer
# ---------------------------------------------------------------------------

class MemoryTracer:
    """Context manager wrapping :mod:`tracemalloc` for peak-memory measurement.

    Attributes
    ----------
    peak_mib:
        Peak Python heap allocation inside the block in MiB; ``None`` before
        the block exits.
    current_mib:
        Current Python heap allocation at block exit in MiB.
    """

    def __init__(self) -> None:
        self.peak_mib: Optional[float] = None
        self.current_mib: Optional[float] = None

    def __enter__(self) -> "MemoryTracer":
        tracemalloc.start()
        return self

    def __exit__(self, *_: Any) -> None:
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        self.current_mib = current / (1024 * 1024)
        self.peak_mib = peak / (1024 * 1024)


# ---------------------------------------------------------------------------
# Per-chunk timing record
# ---------------------------------------------------------------------------

@dataclass
class ChunkTimingRecord:
    """Wall-clock timing for a single chunk.

    Attributes
    ----------
    chunk_index:
        Zero-based chunk ordinal.
    n_rows:
        Number of policies in the chunk.
    elapsed_s:
        Wall-clock seconds for this chunk.
    policies_per_sec:
        Derived throughput metric (``n_rows / elapsed_s``; ``None`` if
        ``elapsed_s`` is zero or not measured).
    """

    chunk_index: int
    n_rows: int
    elapsed_s: float
    policies_per_sec: Optional[float]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ChunkTimingStats:
    """Aggregate statistics over a vector of :class:`ChunkTimingRecord`.

    Attributes
    ----------
    n_chunks:
        Number of chunks timed.
    total_policies:
        Sum of ``n_rows`` across all chunks.
    total_elapsed_s:
        Sum of chunk elapsed times (≠ wall time if parallel, but used here
        in a sequential reference implementation).
    mean_elapsed_s:
        Mean per-chunk elapsed time.
    median_elapsed_s:
        Median per-chunk elapsed time.
    p95_elapsed_s:
        95th-percentile per-chunk elapsed time.
    p99_elapsed_s:
        99th-percentile per-chunk elapsed time.
    max_elapsed_s:
        Maximum per-chunk elapsed time.
    min_elapsed_s:
        Minimum per-chunk elapsed time.
    mean_policies_per_sec:
        Mean throughput across chunks.
    overall_policies_per_sec:
        ``total_policies / total_elapsed_s`` (harmonic-mean-like aggregate).
    """

    n_chunks: int
    total_policies: int
    total_elapsed_s: float
    mean_elapsed_s: float
    median_elapsed_s: float
    p95_elapsed_s: float
    p99_elapsed_s: float
    max_elapsed_s: float
    min_elapsed_s: float
    mean_policies_per_sec: float
    overall_policies_per_sec: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_records(cls, records: List[ChunkTimingRecord]) -> "ChunkTimingStats":
        """Compute aggregate statistics from a list of :class:`ChunkTimingRecord`."""
        if not records:
            return cls(
                n_chunks=0, total_policies=0, total_elapsed_s=0.0,
                mean_elapsed_s=0.0, median_elapsed_s=0.0,
                p95_elapsed_s=0.0, p99_elapsed_s=0.0,
                max_elapsed_s=0.0, min_elapsed_s=0.0,
                mean_policies_per_sec=0.0, overall_policies_per_sec=0.0,
            )
        elapsed = np.array([r.elapsed_s for r in records], dtype=float)
        pps = np.array(
            [r.policies_per_sec if r.policies_per_sec is not None else 0.0 for r in records],
            dtype=float,
        )
        total_policies = sum(r.n_rows for r in records)
        total_elapsed = float(elapsed.sum())
        return cls(
            n_chunks=len(records),
            total_policies=total_policies,
            total_elapsed_s=round(total_elapsed, 4),
            mean_elapsed_s=round(float(elapsed.mean()), 4),
            median_elapsed_s=round(float(np.median(elapsed)), 4),
            p95_elapsed_s=round(float(np.percentile(elapsed, 95)), 4),
            p99_elapsed_s=round(float(np.percentile(elapsed, 99)), 4),
            max_elapsed_s=round(float(elapsed.max()), 4),
            min_elapsed_s=round(float(elapsed.min()), 4),
            mean_policies_per_sec=round(float(pps.mean()), 1),
            overall_policies_per_sec=round(
                total_policies / total_elapsed if total_elapsed > 0 else 0.0, 1
            ),
        )


# ---------------------------------------------------------------------------
# Stage benchmark result
# ---------------------------------------------------------------------------

@dataclass
class StageBenchmarkResult:
    """Timing and memory result for a single named pipeline stage.

    Attributes
    ----------
    stage_name:
        Human-readable stage identifier (e.g. ``"portfolio_generation"``).
    n_policies:
        Number of policies processed in this stage.
    elapsed_s:
        Wall-clock seconds for the stage.
    policies_per_sec:
        Throughput metric.
    tracemalloc_peak_mib:
        Peak Python heap memory during the stage in MiB.
    tracemalloc_current_mib:
        Python heap at stage exit in MiB.
    peak_rss_mib:
        Peak RSS at stage exit in MiB (POSIX only; ``None`` on Windows).
    notes:
        Free-text list of educational notes or performance flags.
    """

    stage_name: str
    n_policies: int
    elapsed_s: float
    policies_per_sec: float
    tracemalloc_peak_mib: Optional[float]
    tracemalloc_current_mib: Optional[float]
    peak_rss_mib: Optional[float]
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# Full benchmark report
# ---------------------------------------------------------------------------

@dataclass
class PerformanceBenchmarkReport:
    """Top-level performance benchmark report for the Phase 11 pipeline.

    Attributes
    ----------
    benchmark_id:
        UUID identifying this benchmark run.
    generated_at:
        ISO-8601 UTC timestamp.
    benchmark_version:
        Module version string.
    n_policies_total:
        Portfolio size benchmarked.
    chunk_size:
        Chunk size used for processing benchmarks.
    stages:
        Per-stage benchmark results.
    chunk_timing_stats:
        Aggregate per-chunk timing statistics.
    chunk_timing_records:
        Individual chunk timing records (one per chunk).
    overall_elapsed_s:
        Total wall-clock time for the complete benchmark run.
    overall_policies_per_sec:
        Overall end-to-end throughput.
    performance_targets_met:
        ``True`` if all stage throughputs meet educational reference targets.
    performance_notes:
        Aggregate performance notes and improvement suggestions.
    source_id:
        Traceability tag for audit reconstruction.
    limitation_id:
        Model limitation disclosure tag.
    """

    benchmark_id: str
    generated_at: str
    benchmark_version: str
    n_policies_total: int
    chunk_size: int
    stages: List[StageBenchmarkResult]
    chunk_timing_stats: ChunkTimingStats
    chunk_timing_records: List[ChunkTimingRecord]
    overall_elapsed_s: float
    overall_policies_per_sec: float
    performance_targets_met: bool
    performance_notes: List[str]
    source_id: str = "PHASE11-T4-BENCH"
    limitation_id: str = "PHASE11-T4-BENCH-LIMIT"

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["chunk_timing_stats"] = self.chunk_timing_stats.to_dict()
        d["chunk_timing_records"] = [r.to_dict() for r in self.chunk_timing_records]
        d["stages"] = [s.to_dict() for s in self.stages]
        return d

    def write_json(self, path: Path | str) -> Path:
        """Persist the report to a JSON file and return the path."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as fh:
            json.dump(self.to_dict(), fh, indent=2, sort_keys=True)
        return path

    def write_markdown(self, path: Path | str) -> Path:
        """Render the report as a Markdown document and return the path."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self._render_markdown(), encoding="utf-8")
        return path

    def _render_markdown(self) -> str:
        lines: List[str] = [
            "# Phase 11 Performance Benchmark Report",
            "",
            f"**Benchmark ID:** `{self.benchmark_id}`  ",
            f"**Generated:** {self.generated_at}  ",
            f"**Portfolio size:** {self.n_policies_total:,} policies  ",
            f"**Chunk size:** {self.chunk_size:,} policies  ",
            f"**Overall elapsed:** {self.overall_elapsed_s:.2f} s  ",
            f"**Overall throughput:** {self.overall_policies_per_sec:,.0f} policies/s  ",
            f"**Performance targets met:** {'✅ Yes' if self.performance_targets_met else '⚠️ No'}  ",
            "",
            "---",
            "",
            "## Stage Results",
            "",
            "| Stage | Policies | Elapsed (s) | Throughput (p/s) | Peak mem (MiB) | Peak RSS (MiB) |",
            "|-------|----------|-------------|-----------------|----------------|----------------|",
        ]
        for s in self.stages:
            rss = f"{s.peak_rss_mib:.1f}" if s.peak_rss_mib is not None else "N/A"
            mem = f"{s.tracemalloc_peak_mib:.1f}" if s.tracemalloc_peak_mib is not None else "N/A"
            lines.append(
                f"| {s.stage_name} | {s.n_policies:,} | {s.elapsed_s:.3f} | "
                f"{s.policies_per_sec:,.0f} | {mem} | {rss} |"
            )

        lines += [
            "",
            "## Per-Chunk Timing Statistics",
            "",
            f"- **Chunks:** {self.chunk_timing_stats.n_chunks}",
            f"- **Mean chunk time:** {self.chunk_timing_stats.mean_elapsed_s:.4f} s",
            f"- **Median chunk time:** {self.chunk_timing_stats.median_elapsed_s:.4f} s",
            f"- **P95 chunk time:** {self.chunk_timing_stats.p95_elapsed_s:.4f} s",
            f"- **P99 chunk time:** {self.chunk_timing_stats.p99_elapsed_s:.4f} s",
            f"- **Max chunk time:** {self.chunk_timing_stats.max_elapsed_s:.4f} s",
            f"- **Min chunk time:** {self.chunk_timing_stats.min_elapsed_s:.4f} s",
            f"- **Mean throughput:** {self.chunk_timing_stats.mean_policies_per_sec:,.0f} p/s",
            f"- **Overall throughput:** {self.chunk_timing_stats.overall_policies_per_sec:,.0f} p/s",
            "",
            "## Performance Notes",
            "",
        ]
        for note in self.performance_notes:
            lines.append(f"- {note}")

        lines += [
            "",
            "## Limitations",
            "",
            "- `tracemalloc` peak captures Python heap allocations only; NumPy/Pandas",
            "  off-heap buffers are not included in `tracemalloc_peak_mib`.",
            "- `peak_rss_mib` is the most comprehensive single-process memory metric on",
            "  POSIX systems (Linux/macOS).  It is unavailable on Windows sandboxes.",
            "- Benchmark results are sensitive to sandbox scheduling jitter; re-run in a",
            "  dedicated environment for capacity-planning decisions.",
            "- All benchmarks use the stub chunk function (raw column sums); real model",
            "  projection functions will have higher per-chunk latency.",
            "- This module is for educational purposes and must not be used for production",
            "  capacity planning without calibration to live workloads.",
            "",
            f"*Source ID: {self.source_id} | Limitation ID: {self.limitation_id}*",
        ]
        return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Portfolio generation benchmark
# ---------------------------------------------------------------------------

def benchmark_portfolio_generation(
    n_policies: int = 100_000,
    seed: int = 42,
) -> StageBenchmarkResult:
    """Benchmark synthetic portfolio generation for ``n_policies`` policies.

    Parameters
    ----------
    n_policies:
        Number of policies to generate.
    seed:
        Random seed for reproducibility.

    Returns
    -------
    StageBenchmarkResult
        Timing and memory statistics for this stage.
    """
    cfg = PortfolioGenerationConfig(n_policies=n_policies, seed=seed)
    notes: List[str] = []

    with MemoryTracer() as mem:
        with BenchmarkTimer() as t:
            result = generate_hk_par_portfolio(cfg)

    elapsed = t.elapsed_s or 0.0
    pps = n_policies / elapsed if elapsed > 0 else 0.0
    rss = _peak_rss_mib()

    if pps < _TARGET_PORTFOLIO_GEN_POLICIES_PER_SEC:
        notes.append(
            f"NOTE: portfolio generation throughput {pps:,.0f} p/s is below the "
            f"educational target {_TARGET_PORTFOLIO_GEN_POLICIES_PER_SEC:,} p/s.  "
            "Consider using Pandas categoricals and vectorised sampling."
        )
    else:
        notes.append(
            f"Portfolio generation throughput {pps:,.0f} p/s meets the "
            f"educational target {_TARGET_PORTFOLIO_GEN_POLICIES_PER_SEC:,} p/s."
        )

    return StageBenchmarkResult(
        stage_name="portfolio_generation",
        n_policies=n_policies,
        elapsed_s=round(elapsed, 4),
        policies_per_sec=round(pps, 1),
        tracemalloc_peak_mib=round(mem.peak_mib, 2) if mem.peak_mib is not None else None,
        tracemalloc_current_mib=round(mem.current_mib, 2) if mem.current_mib is not None else None,
        peak_rss_mib=round(rss, 1) if rss is not None else None,
        notes=notes,
    )


# ---------------------------------------------------------------------------
# Chunked processing benchmark
# ---------------------------------------------------------------------------

def benchmark_chunked_processing(
    table: pd.DataFrame,
    chunk_size: int = 10_000,
    checkpoint_path: Optional[Path] = None,
    chunk_fn: Optional[Callable[[pd.DataFrame], Dict[str, float]]] = None,
) -> Tuple[StageBenchmarkResult, List[ChunkTimingRecord], ReconciliationReport]:
    """Benchmark the chunked portfolio processor over an existing policy table.

    Each chunk is timed individually so that P95/P99 latency can be computed.
    Memory is profiled for the full chunked processing run.

    Parameters
    ----------
    table:
        Policy DataFrame (e.g. output of :func:`generate_hk_par_portfolio`).
    chunk_size:
        Policies per processing chunk.
    checkpoint_path:
        Optional path for checkpoint JSON.  Defaults to a temporary path
        ``/tmp/bench_checkpoint_{uuid}.json``.
    chunk_fn:
        Callable receiving a chunk ``DataFrame`` and returning a
        ``{column: total}`` dict.  Defaults to the stub (raw column sums).

    Returns
    -------
    tuple
        ``(StageBenchmarkResult, List[ChunkTimingRecord], ReconciliationReport)``
    """
    import tempfile

    if checkpoint_path is None:
        tmp = tempfile.mktemp(suffix=".json", prefix="bench_cp_")
        checkpoint_path = Path(tmp)

    audit_path = checkpoint_path.parent / (checkpoint_path.stem + "_audit.json")
    recon_path = checkpoint_path.parent / (checkpoint_path.stem + "_recon.json")

    cfg = ChunkedProcessorConfig(
        chunk_size=chunk_size,
        checkpoint_path=checkpoint_path,
        audit_path=audit_path,
        reconciliation_path=recon_path,
    )

    # Instrument the chunk function to record per-chunk timing.
    chunk_timing_records: List[ChunkTimingRecord] = []
    _idx_counter = [0]

    def _timed_chunk_fn(chunk: pd.DataFrame) -> Dict[str, float]:
        idx = _idx_counter[0]
        _idx_counter[0] += 1
        with BenchmarkTimer() as t:
            result = (chunk_fn or _stub_chunk_fn)(chunk)
        elapsed = t.elapsed_s or 0.0
        n = len(chunk)
        chunk_timing_records.append(
            ChunkTimingRecord(
                chunk_index=idx,
                n_rows=n,
                elapsed_s=round(elapsed, 6),
                policies_per_sec=round(n / elapsed, 1) if elapsed > 0 else None,
            )
        )
        return result

    n_policies = len(table)
    notes: List[str] = []

    with MemoryTracer() as mem:
        with BenchmarkTimer() as t:
            processor = ChunkedProcessor(table, config=cfg)
            recon = processor.run(chunk_fn=_timed_chunk_fn)

    elapsed = t.elapsed_s or 0.0
    pps = n_policies / elapsed if elapsed > 0 else 0.0
    rss = _peak_rss_mib()

    if pps < _TARGET_CHUNK_POLICIES_PER_SEC:
        notes.append(
            f"NOTE: chunked processing throughput {pps:,.0f} p/s is below the "
            f"educational target {_TARGET_CHUNK_POLICIES_PER_SEC:,} p/s for the stub "
            "function.  A real projection function will be slower; benchmark separately."
        )
    else:
        notes.append(
            f"Chunked processing throughput {pps:,.0f} p/s meets the educational "
            f"target {_TARGET_CHUNK_POLICIES_PER_SEC:,} p/s (stub function)."
        )

    if not recon.overall_passed:
        notes.append(
            f"WARNING: reconciliation did not pass ({len(recon.exceptions)} exception(s)); "
            "performance numbers may not reflect a clean full-portfolio run."
        )
    else:
        notes.append("Reconciliation passed: all control totals match within tolerance.")

    stage = StageBenchmarkResult(
        stage_name="chunked_processing",
        n_policies=n_policies,
        elapsed_s=round(elapsed, 4),
        policies_per_sec=round(pps, 1),
        tracemalloc_peak_mib=round(mem.peak_mib, 2) if mem.peak_mib is not None else None,
        tracemalloc_current_mib=round(mem.current_mib, 2) if mem.current_mib is not None else None,
        peak_rss_mib=round(rss, 1) if rss is not None else None,
        notes=notes,
    )
    return stage, chunk_timing_records, recon


# ---------------------------------------------------------------------------
# Stub chunk function (identical to chunk_processor default)
# ---------------------------------------------------------------------------

def _stub_chunk_fn(chunk: pd.DataFrame) -> Dict[str, float]:
    """Stub processor: return financial control totals without any modelling."""
    return {col: float(chunk[col].sum()) for col in RECONCILE_COLS}


# ---------------------------------------------------------------------------
# Reporting governance overhead benchmark
# ---------------------------------------------------------------------------

def benchmark_governance_overhead(
    n_policies: int,
    n_chunks: int,
) -> StageBenchmarkResult:
    """Estimate governance-overhead timing by simulating sign-off pack assembly.

    This benchmark does not invoke the full reporting cycle (which requires a
    complete portfolio run) but instead measures the structural overhead of
    building and serialising the sign-off pack artefacts from pre-computed data.

    Parameters
    ----------
    n_policies:
        Portfolio size for labelling purposes.
    n_chunks:
        Number of chunks in the run (for metadata realism).

    Returns
    -------
    StageBenchmarkResult
        Timing and memory for governance pack assembly.
    """
    notes: List[str] = []

    def _simulate_governance() -> None:
        # Simulate assumption lock creation
        assumption_data = {
            "mortality_table": "IA_HK_2010",
            "lapse_rate": 0.05,
            "discount_rate": 0.04,
            "expense_loading": 0.01,
            "declaration": {"cash_dividend_rate": 0.03, "bonus_rate": 0.02},
        }
        lock_payload = json.dumps(assumption_data, sort_keys=True)
        import hashlib
        lock_digest = hashlib.sha256(lock_payload.encode()).hexdigest()

        # Simulate run metadata assembly
        run_meta = {
            "run_id": str(uuid.uuid4()),
            "lock_id": f"LOCK-{lock_digest[:8].upper()}",
            "n_policies": n_policies,
            "n_chunks": n_chunks,
            "reconciliation_passed": True,
            "generated_at": _now_utc(),
        }

        # Simulate validation suite (8 checks)
        checks = []
        check_ids = [
            "REC-001", "FAIL-001", "POL-001", "SA-001",
            "MIX-001", "AGE-001", "PREM-001", "TVOG-001",
        ]
        for cid in check_ids:
            checks.append({"check_id": cid, "status": "PASS", "observed": 0.0, "threshold": 0.05})

        # Simulate sign-off pack serialisation
        pack = {
            "governance_cleared": True,
            "assumption_lock": assumption_data,
            "run_metadata": run_meta,
            "validation_checks": checks,
            "blockers": [],
        }
        _ = json.dumps(pack, sort_keys=True)  # serialisation cost

    with MemoryTracer() as mem:
        with BenchmarkTimer() as t:
            _simulate_governance()

    elapsed = t.elapsed_s or 0.0
    rss = _peak_rss_mib()

    notes.append(
        f"Governance pack assembly elapsed {elapsed * 1000:.2f} ms for "
        f"{n_policies:,} policies / {n_chunks} chunks."
    )
    notes.append(
        "Governance overhead is dominated by JSON serialisation of the sign-off "
        "pack; for large assumption sets consider binary serialisation (MessagePack, "
        "Avro) in production."
    )

    return StageBenchmarkResult(
        stage_name="governance_overhead",
        n_policies=n_policies,
        elapsed_s=round(elapsed, 6),
        policies_per_sec=0.0,  # not a throughput-driven stage
        tracemalloc_peak_mib=round(mem.peak_mib, 2) if mem.peak_mib is not None else None,
        tracemalloc_current_mib=round(mem.current_mib, 2) if mem.current_mib is not None else None,
        peak_rss_mib=round(rss, 1) if rss is not None else None,
        notes=notes,
    )


# ---------------------------------------------------------------------------
# Scalability probe
# ---------------------------------------------------------------------------

def benchmark_scalability_probe(
    sizes: Tuple[int, ...] = (1_000, 5_000, 10_000),
    chunk_size: int = 1_000,
    seed: int = 99,
) -> List[StageBenchmarkResult]:
    """Run chunked processing benchmarks at multiple portfolio sizes.

    Produces a throughput curve (policies/s vs. portfolio size) to assess
    whether the pipeline scales linearly or sub-linearly.

    Parameters
    ----------
    sizes:
        Tuple of portfolio sizes to benchmark (policies).
    chunk_size:
        Chunk size for all scalability runs.
    seed:
        RNG seed for reproducibility.

    Returns
    -------
    list
        One :class:`StageBenchmarkResult` per portfolio size, stage name
        ``"scalability_N"`` where ``N`` is the portfolio size.
    """
    results: List[StageBenchmarkResult] = []
    for n in sizes:
        cfg = PortfolioGenerationConfig(n_policies=n, seed=seed)
        gen_result = generate_hk_par_portfolio(cfg)
        table = gen_result.policies

        stage, _, _ = benchmark_chunked_processing(
            table, chunk_size=min(chunk_size, n)
        )
        stage.stage_name = f"scalability_{n}"
        results.append(stage)

    # Annotate with scaling analysis note.
    if len(results) >= 2:
        pps_values = [s.policies_per_sec for s in results]
        if pps_values[-1] > 0 and pps_values[0] > 0:
            scaling_ratio = pps_values[-1] / pps_values[0]
            note = (
                f"Scalability: throughput ratio (largest/smallest) = {scaling_ratio:.2f}. "
                "Values near 1.0 indicate linear scaling; values < 0.5 suggest growing "
                "overhead (e.g. DataFrame concatenation, checkpoint I/O) at larger sizes."
            )
            for s in results:
                s.notes.append(note)

    return results


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

def run_phase11_benchmarks(
    n_policies: int = 100_000,
    chunk_size: int = 10_000,
    seed: int = 42,
    run_scalability_probe: bool = False,
    scalability_sizes: Tuple[int, ...] = (1_000, 5_000, 10_000),
    output_dir: Optional[Path] = None,
) -> PerformanceBenchmarkReport:
    """Run the full Phase 11 performance benchmark suite.

    Stages executed:
    1. Portfolio generation (``n_policies`` synthetic HK PAR policies).
    2. Chunked processing (stub function; measures pipeline overhead).
    3. Governance overhead (sign-off pack assembly simulation).
    4. Scalability probe (optional; smaller sizes for throughput curve).

    Parameters
    ----------
    n_policies:
        Target portfolio size.
    chunk_size:
        Policies per chunk for the processing benchmark.
    seed:
        RNG seed for portfolio generation.
    run_scalability_probe:
        If ``True``, also run the scalability probe at ``scalability_sizes``.
    scalability_sizes:
        Portfolio sizes for the scalability probe (used only if
        ``run_scalability_probe`` is True).
    output_dir:
        Directory to write JSON and Markdown reports.  If ``None``, reports
        are not written automatically (caller can call ``write_json`` /
        ``write_markdown`` on the returned report).

    Returns
    -------
    PerformanceBenchmarkReport
        Full benchmark report with all stage results and aggregate statistics.
    """
    benchmark_id = str(uuid.uuid4())
    generated_at = _now_utc()
    stages: List[StageBenchmarkResult] = []
    all_notes: List[str] = []

    # -- Stage 1: portfolio generation
    gen_stage = benchmark_portfolio_generation(n_policies=n_policies, seed=seed)
    stages.append(gen_stage)
    all_notes.extend(gen_stage.notes)

    # Use generated table for processing benchmark
    cfg = PortfolioGenerationConfig(n_policies=n_policies, seed=seed)
    gen_result = generate_hk_par_portfolio(cfg)
    table = gen_result.policies

    # -- Stage 2: chunked processing
    proc_stage, chunk_records, recon = benchmark_chunked_processing(
        table, chunk_size=chunk_size
    )
    stages.append(proc_stage)
    all_notes.extend(proc_stage.notes)

    # -- Stage 3: governance overhead
    n_chunks = max(1, n_policies // chunk_size + (1 if n_policies % chunk_size else 0))
    gov_stage = benchmark_governance_overhead(n_policies=n_policies, n_chunks=n_chunks)
    stages.append(gov_stage)
    all_notes.extend(gov_stage.notes)

    # -- Stage 4: scalability probe (optional)
    if run_scalability_probe:
        scale_stages = benchmark_scalability_probe(
            sizes=scalability_sizes, chunk_size=min(1_000, min(scalability_sizes)),
            seed=seed,
        )
        stages.extend(scale_stages)
        for s in scale_stages:
            all_notes.extend(s.notes)

    # -- Aggregate statistics
    chunk_stats = ChunkTimingStats.from_records(chunk_records)
    timed_stages = [s for s in stages if s.stage_name in ("portfolio_generation", "chunked_processing")]
    overall_elapsed = sum(s.elapsed_s for s in timed_stages)
    overall_pps = n_policies / overall_elapsed if overall_elapsed > 0 else 0.0

    # -- Performance targets check
    targets_met = (
        gen_stage.policies_per_sec >= _TARGET_PORTFOLIO_GEN_POLICIES_PER_SEC
        and proc_stage.policies_per_sec >= _TARGET_CHUNK_POLICIES_PER_SEC
        and overall_pps >= _TARGET_FULL_RUN_POLICIES_PER_SEC
    )

    # -- Additional aggregate notes
    all_notes.append(
        f"Overall two-stage elapsed (generation + processing): {overall_elapsed:.2f} s "
        f"for {n_policies:,} policies ({overall_pps:,.0f} p/s combined)."
    )
    all_notes.append(
        "Optimization paths: (1) vectorise portfolio generation with NumPy arrays; "
        "(2) use multiprocessing.Pool for parallel chunk dispatch; "
        "(3) replace JSON checkpoint with SQLite for lower I/O overhead; "
        "(4) pre-sort and cache the ordered policy table to avoid repeated sort calls."
    )
    all_notes.append(
        "Memory optimization: process chunks as generators rather than slicing the "
        "full DataFrame to avoid duplicate copies; use dtype downcasting (float32 for "
        "financial columns where precision allows) to halve memory footprint."
    )

    report = PerformanceBenchmarkReport(
        benchmark_id=benchmark_id,
        generated_at=generated_at,
        benchmark_version=_BENCHMARK_VERSION,
        n_policies_total=n_policies,
        chunk_size=chunk_size,
        stages=stages,
        chunk_timing_stats=chunk_stats,
        chunk_timing_records=chunk_records,
        overall_elapsed_s=round(overall_elapsed, 4),
        overall_policies_per_sec=round(overall_pps, 1),
        performance_targets_met=targets_met,
        performance_notes=all_notes,
    )

    # -- Write outputs if requested
    if output_dir is not None:
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        json_path = out / f"phase11_benchmark_{benchmark_id[:8]}.json"
        md_path = out / f"phase11_benchmark_{benchmark_id[:8]}.md"
        report.write_json(json_path)
        report.write_markdown(md_path)

    return report
