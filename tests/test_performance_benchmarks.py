"""
Tests for Phase 11 Task 4: performance benchmarks and memory profiling.

Tests focus on the structural correctness of benchmark report construction,
per-chunk timing instrumentation, and scalability probe analysis.  Actual
timing values are not asserted (environment-dependent), but throughput fields
must be non-negative and report fields must serialise to valid JSON.

No third-party packages beyond numpy and pandas are required.
"""

from __future__ import annotations

import json
import math
import time
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from par_model_v2.projection.performance_benchmarks import (
    BenchmarkTimer,
    ChunkTimingRecord,
    ChunkTimingStats,
    MemoryTracer,
    PerformanceBenchmarkReport,
    StageBenchmarkResult,
    _stub_chunk_fn,
    benchmark_chunked_processing,
    benchmark_governance_overhead,
    benchmark_portfolio_generation,
    benchmark_scalability_probe,
    run_phase11_benchmarks,
)
from par_model_v2.projection.portfolio_generator import (
    PortfolioGenerationConfig,
    generate_hk_par_portfolio,
)


# ---------------------------------------------------------------------------
# BenchmarkTimer
# ---------------------------------------------------------------------------

class TestBenchmarkTimer:
    def test_elapsed_is_none_before_context(self):
        t = BenchmarkTimer()
        assert t.elapsed_s is None

    def test_elapsed_measured_after_context(self):
        with BenchmarkTimer() as t:
            time.sleep(0.01)
        assert t.elapsed_s is not None
        assert t.elapsed_s >= 0.009  # at least ~10 ms

    def test_elapsed_is_float(self):
        with BenchmarkTimer() as t:
            pass
        assert isinstance(t.elapsed_s, float)

    def test_zero_work_elapsed_non_negative(self):
        with BenchmarkTimer() as t:
            x = 1 + 1  # noqa: F841
        assert t.elapsed_s >= 0.0


# ---------------------------------------------------------------------------
# MemoryTracer
# ---------------------------------------------------------------------------

class TestMemoryTracer:
    def test_peak_mib_set_after_context(self):
        with MemoryTracer() as m:
            _ = [0] * 1000
        assert m.peak_mib is not None
        assert m.peak_mib >= 0.0

    def test_current_mib_set_after_context(self):
        with MemoryTracer() as m:
            pass
        assert m.current_mib is not None

    def test_peak_gte_current(self):
        with MemoryTracer() as m:
            big = list(range(100_000))
        # peak should be >= current (list was allocated inside)
        assert m.peak_mib >= m.current_mib - 0.001  # small float tolerance

    def test_nested_tracer_does_not_crash(self):
        """tracemalloc.start() is idempotent; nested usage should not raise."""
        with MemoryTracer() as outer:
            with MemoryTracer() as inner:
                _ = [None] * 100
        assert outer.peak_mib is not None
        assert inner.peak_mib is not None


# ---------------------------------------------------------------------------
# ChunkTimingRecord
# ---------------------------------------------------------------------------

class TestChunkTimingRecord:
    def test_to_dict_roundtrip(self):
        rec = ChunkTimingRecord(
            chunk_index=0, n_rows=1000, elapsed_s=0.5, policies_per_sec=2000.0
        )
        d = rec.to_dict()
        assert d["chunk_index"] == 0
        assert d["n_rows"] == 1000
        assert d["elapsed_s"] == pytest.approx(0.5)
        assert d["policies_per_sec"] == pytest.approx(2000.0)

    def test_none_policies_per_sec_serialisable(self):
        rec = ChunkTimingRecord(chunk_index=1, n_rows=500, elapsed_s=0.0, policies_per_sec=None)
        d = rec.to_dict()
        assert d["policies_per_sec"] is None
        # Must be JSON-serialisable
        _ = json.dumps(d)


# ---------------------------------------------------------------------------
# ChunkTimingStats
# ---------------------------------------------------------------------------

class TestChunkTimingStats:
    def _make_records(self, n: int = 10) -> list:
        rng = np.random.default_rng(0)
        elapsed = rng.uniform(0.1, 1.0, size=n)
        return [
            ChunkTimingRecord(
                chunk_index=i,
                n_rows=1000,
                elapsed_s=float(e),
                policies_per_sec=round(1000 / float(e), 1),
            )
            for i, e in enumerate(elapsed)
        ]

    def test_empty_records_returns_zeros(self):
        stats = ChunkTimingStats.from_records([])
        assert stats.n_chunks == 0
        assert stats.total_elapsed_s == 0.0

    def test_single_record(self):
        rec = ChunkTimingRecord(chunk_index=0, n_rows=500, elapsed_s=0.25, policies_per_sec=2000.0)
        stats = ChunkTimingStats.from_records([rec])
        assert stats.n_chunks == 1
        assert stats.total_policies == 500
        assert stats.mean_elapsed_s == pytest.approx(0.25, abs=1e-4)
        assert stats.p95_elapsed_s == pytest.approx(0.25, abs=1e-4)

    def test_stats_correctness(self):
        records = self._make_records(n=10)
        stats = ChunkTimingStats.from_records(records)
        assert stats.n_chunks == 10
        assert stats.total_policies == 10_000
        assert stats.min_elapsed_s <= stats.mean_elapsed_s <= stats.max_elapsed_s
        assert stats.p95_elapsed_s >= stats.median_elapsed_s

    def test_overall_pps_consistent(self):
        records = self._make_records(n=5)
        stats = ChunkTimingStats.from_records(records)
        expected_pps = stats.total_policies / stats.total_elapsed_s
        assert stats.overall_policies_per_sec == pytest.approx(expected_pps, rel=0.01)

    def test_to_dict_serialisable(self):
        stats = ChunkTimingStats.from_records(self._make_records())
        d = stats.to_dict()
        _ = json.dumps(d)  # must not raise


# ---------------------------------------------------------------------------
# StageBenchmarkResult
# ---------------------------------------------------------------------------

class TestStageBenchmarkResult:
    def test_to_dict_fields(self):
        stage = StageBenchmarkResult(
            stage_name="test_stage",
            n_policies=1000,
            elapsed_s=1.23,
            policies_per_sec=813.0,
            tracemalloc_peak_mib=5.0,
            tracemalloc_current_mib=2.0,
            peak_rss_mib=None,
            notes=["note1"],
        )
        d = stage.to_dict()
        assert d["stage_name"] == "test_stage"
        assert d["n_policies"] == 1000
        assert d["peak_rss_mib"] is None
        _ = json.dumps(d)


# ---------------------------------------------------------------------------
# Stub chunk function
# ---------------------------------------------------------------------------

class TestStubChunkFn:
    def test_returns_all_reconcile_cols(self):
        from par_model_v2.projection.chunk_processor import RECONCILE_COLS
        df = pd.DataFrame({
            "sum_assured": [100.0, 200.0],
            "annual_premium": [10.0, 20.0],
            "initial_vested_bonus": [0.0, 5.0],
        })
        result = _stub_chunk_fn(df)
        for col in RECONCILE_COLS:
            assert col in result

    def test_totals_match_sum(self):
        df = pd.DataFrame({
            "sum_assured": [100.0, 200.0, 300.0],
            "annual_premium": [10.0, 20.0, 30.0],
            "initial_vested_bonus": [1.0, 2.0, 3.0],
        })
        result = _stub_chunk_fn(df)
        assert result["sum_assured"] == pytest.approx(600.0)
        assert result["annual_premium"] == pytest.approx(60.0)
        assert result["initial_vested_bonus"] == pytest.approx(6.0)


# ---------------------------------------------------------------------------
# Portfolio generation benchmark
# ---------------------------------------------------------------------------

class TestBenchmarkPortfolioGeneration:
    def test_returns_stage_result(self):
        stage = benchmark_portfolio_generation(n_policies=500, seed=1)
        assert isinstance(stage, StageBenchmarkResult)

    def test_stage_name(self):
        stage = benchmark_portfolio_generation(n_policies=500, seed=1)
        assert stage.stage_name == "portfolio_generation"

    def test_n_policies_matches(self):
        stage = benchmark_portfolio_generation(n_policies=200, seed=2)
        assert stage.n_policies == 200

    def test_elapsed_non_negative(self):
        stage = benchmark_portfolio_generation(n_policies=100, seed=3)
        assert stage.elapsed_s >= 0.0

    def test_policies_per_sec_positive(self):
        stage = benchmark_portfolio_generation(n_policies=100, seed=4)
        assert stage.policies_per_sec > 0.0

    def test_tracemalloc_peak_set(self):
        stage = benchmark_portfolio_generation(n_policies=100, seed=5)
        assert stage.tracemalloc_peak_mib is not None
        assert stage.tracemalloc_peak_mib >= 0.0

    def test_notes_non_empty(self):
        stage = benchmark_portfolio_generation(n_policies=100, seed=6)
        assert len(stage.notes) > 0

    def test_serialisable(self):
        stage = benchmark_portfolio_generation(n_policies=100, seed=7)
        _ = json.dumps(stage.to_dict())


# ---------------------------------------------------------------------------
# Chunked processing benchmark
# ---------------------------------------------------------------------------

class TestBenchmarkChunkedProcessing:
    @pytest.fixture
    def small_table(self):
        cfg = PortfolioGenerationConfig(n_policies=500, seed=10)
        result = generate_hk_par_portfolio(cfg)
        return result.portfolio

    def test_returns_tuple_of_three(self, small_table):
        result = benchmark_chunked_processing(small_table, chunk_size=100)
        assert len(result) == 3

    def test_stage_result_type(self, small_table):
        stage, records, recon = benchmark_chunked_processing(small_table, chunk_size=100)
        assert isinstance(stage, StageBenchmarkResult)

    def test_stage_name(self, small_table):
        stage, _, _ = benchmark_chunked_processing(small_table, chunk_size=100)
        assert stage.stage_name == "chunked_processing"

    def test_chunk_records_count(self, small_table):
        """Number of chunk records should equal ceil(n_policies / chunk_size)."""
        chunk_size = 100
        _, records, _ = benchmark_chunked_processing(small_table, chunk_size=chunk_size)
        expected_chunks = math.ceil(len(small_table) / chunk_size)
        assert len(records) == expected_chunks

    def test_chunk_records_type(self, small_table):
        _, records, _ = benchmark_chunked_processing(small_table, chunk_size=250)
        assert all(isinstance(r, ChunkTimingRecord) for r in records)

    def test_all_chunk_elapsed_non_negative(self, small_table):
        _, records, _ = benchmark_chunked_processing(small_table, chunk_size=100)
        assert all(r.elapsed_s >= 0.0 for r in records)

    def test_all_chunk_row_counts_positive(self, small_table):
        _, records, _ = benchmark_chunked_processing(small_table, chunk_size=100)
        assert all(r.n_rows > 0 for r in records)

    def test_chunk_row_totals_match_portfolio(self, small_table):
        _, records, _ = benchmark_chunked_processing(small_table, chunk_size=100)
        total_rows = sum(r.n_rows for r in records)
        assert total_rows == len(small_table)

    def test_reconciliation_passed(self, small_table):
        _, _, recon = benchmark_chunked_processing(small_table, chunk_size=100)
        assert recon.overall_passed

    def test_throughput_positive(self, small_table):
        stage, _, _ = benchmark_chunked_processing(small_table, chunk_size=100)
        assert stage.policies_per_sec > 0.0

    def test_custom_chunk_fn(self, small_table):
        """Custom chunk fn should be invoked and timing recorded."""
        call_log = []

        def my_fn(chunk: pd.DataFrame):
            call_log.append(len(chunk))
            from par_model_v2.projection.chunk_processor import RECONCILE_COLS
            return {col: float(chunk[col].sum()) for col in RECONCILE_COLS}

        _, records, _ = benchmark_chunked_processing(
            small_table, chunk_size=250, chunk_fn=my_fn
        )
        assert len(call_log) == len(records)


# ---------------------------------------------------------------------------
# Governance overhead benchmark
# ---------------------------------------------------------------------------

class TestBenchmarkGovernanceOverhead:
    def test_returns_stage_result(self):
        stage = benchmark_governance_overhead(n_policies=1000, n_chunks=10)
        assert isinstance(stage, StageBenchmarkResult)

    def test_stage_name(self):
        stage = benchmark_governance_overhead(n_policies=1000, n_chunks=10)
        assert stage.stage_name == "governance_overhead"

    def test_elapsed_non_negative(self):
        stage = benchmark_governance_overhead(n_policies=500, n_chunks=5)
        assert stage.elapsed_s >= 0.0

    def test_notes_populated(self):
        stage = benchmark_governance_overhead(n_policies=1000, n_chunks=10)
        assert len(stage.notes) > 0

    def test_serialisable(self):
        stage = benchmark_governance_overhead(n_policies=1000, n_chunks=10)
        _ = json.dumps(stage.to_dict())


# ---------------------------------------------------------------------------
# Scalability probe
# ---------------------------------------------------------------------------

class TestBenchmarkScalabilityProbe:
    def test_returns_list_of_stage_results(self):
        stages = benchmark_scalability_probe(sizes=(200, 500), chunk_size=100, seed=0)
        assert isinstance(stages, list)
        assert len(stages) == 2

    def test_stage_names_include_size(self):
        stages = benchmark_scalability_probe(sizes=(100, 300), chunk_size=50, seed=1)
        names = [s.stage_name for s in stages]
        assert "scalability_100" in names
        assert "scalability_300" in names

    def test_throughput_positive(self):
        stages = benchmark_scalability_probe(sizes=(200,), chunk_size=100, seed=2)
        assert stages[0].policies_per_sec > 0.0

    def test_scaling_note_added(self):
        stages = benchmark_scalability_probe(sizes=(100, 500), chunk_size=50, seed=3)
        # At least one stage should have a scaling note
        all_notes = [n for s in stages for n in s.notes]
        assert any("Scalability" in n for n in all_notes)


# ---------------------------------------------------------------------------
# Full benchmark report
# ---------------------------------------------------------------------------

class TestPerformanceBenchmarkReport:
    @pytest.fixture(scope="class")
    def report(self):
        return run_phase11_benchmarks(
            n_policies=500,
            chunk_size=100,
            seed=42,
            run_scalability_probe=False,
        )

    def test_returns_report_type(self, report):
        assert isinstance(report, PerformanceBenchmarkReport)

    def test_benchmark_id_is_uuid(self, report):
        import re
        assert re.fullmatch(r"[0-9a-f\-]{36}", report.benchmark_id)

    def test_generated_at_is_iso(self, report):
        import re
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", report.generated_at)

    def test_stages_present(self, report):
        assert len(report.stages) >= 3  # generation, processing, governance

    def test_chunk_timing_stats_populated(self, report):
        assert report.chunk_timing_stats.n_chunks > 0

    def test_chunk_timing_records_populated(self, report):
        assert len(report.chunk_timing_records) > 0

    def test_overall_elapsed_positive(self, report):
        assert report.overall_elapsed_s > 0.0

    def test_overall_pps_positive(self, report):
        assert report.overall_policies_per_sec > 0.0

    def test_performance_notes_non_empty(self, report):
        assert len(report.performance_notes) > 0

    def test_json_serialisable(self, report):
        d = report.to_dict()
        payload = json.dumps(d)
        assert len(payload) > 100

    def test_write_json(self, report, tmp_path):
        out = tmp_path / "bench.json"
        path = report.write_json(out)
        assert path.exists()
        with path.open() as fh:
            loaded = json.load(fh)
        assert loaded["benchmark_id"] == report.benchmark_id

    def test_write_markdown(self, report, tmp_path):
        out = tmp_path / "bench.md"
        path = report.write_markdown(out)
        assert path.exists()
        content = path.read_text()
        assert "Performance Benchmark" in content
        assert report.benchmark_id in content

    def test_markdown_contains_stage_table(self, report, tmp_path):
        out = tmp_path / "bench2.md"
        report.write_markdown(out)
        content = out.read_text()
        assert "portfolio_generation" in content
        assert "chunked_processing" in content


# ---------------------------------------------------------------------------
# Full orchestrator with scalability probe
# ---------------------------------------------------------------------------

class TestRunPhase11BenchmarksScalability:
    def test_with_scalability_probe(self):
        report = run_phase11_benchmarks(
            n_policies=200,
            chunk_size=50,
            seed=1,
            run_scalability_probe=True,
            scalability_sizes=(50, 100),
        )
        stage_names = [s.stage_name for s in report.stages]
        assert "scalability_50" in stage_names
        assert "scalability_100" in stage_names

    def test_output_dir_writes_files(self, tmp_path):
        report = run_phase11_benchmarks(
            n_policies=100,
            chunk_size=50,
            seed=2,
            output_dir=tmp_path,
        )
        json_files = list(tmp_path.glob("*.json"))
        md_files = list(tmp_path.glob("*.md"))
        assert len(json_files) == 1
        assert len(md_files) == 1


# ---------------------------------------------------------------------------
# Integration: chunk timing records are consistent with stats
# ---------------------------------------------------------------------------

class TestChunkTimingConsistency:
    def test_stats_match_records(self):
        cfg = PortfolioGenerationConfig(n_policies=300, seed=99)
        table = generate_hk_par_portfolio(cfg).portfolio
        _, records, _ = benchmark_chunked_processing(table, chunk_size=100)
        stats = ChunkTimingStats.from_records(records)
        total_from_records = sum(r.n_rows for r in records)
        assert stats.total_policies == total_from_records
        assert stats.n_chunks == len(records)

    def test_min_max_consistent(self):
        cfg = PortfolioGenerationConfig(n_policies=300, seed=100)
        table = generate_hk_par_portfolio(cfg).portfolio
        _, records, _ = benchmark_chunked_processing(table, chunk_size=100)
        stats = ChunkTimingStats.from_records(records)
        elapsed = [r.elapsed_s for r in records]
        assert stats.min_elapsed_s == pytest.approx(min(elapsed), abs=1e-6)
        assert stats.max_elapsed_s == pytest.approx(max(elapsed), abs=1e-6)
