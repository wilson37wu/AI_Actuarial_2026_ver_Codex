"""
Tests for Phase 11 Task 2: ChunkedPortfolioProcessor, build_chunk_plan,
reconcile_portfolio, and failed-chunk audit.

These tests run against a small synthetic portfolio (200 or 500 policies)
so they complete well within the 45-second sandbox limit.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Dict

import numpy as np
import pandas as pd
import pytest

from par_model_v2.projection.portfolio_generator import (
    PRODUCT_LINE_CASH,
    PRODUCT_LINE_RB,
    UNIFIED_COLUMNS,
    generate_hk_par_portfolio,
    PortfolioGenerationConfig,
)
from par_model_v2.projection.chunked_processor import (
    ChunkRecord,
    ChunkStatus,
    ChunkedPortfolioProcessor,
    CheckpointStore,
    ProcessingPlan,
    ReconciliationReport,
    REQUIRED_CHUNK_RESULT_KEYS,
    build_chunk_plan,
    default_chunk_fn,
    failed_chunk_audit_report,
    reconcile_portfolio,
    _chunk_id,
    _check_no_overlap,
    _rel_close,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def small_portfolio():
    """200-policy synthetic portfolio for fast tests."""
    result = generate_hk_par_portfolio(PortfolioGenerationConfig(n_policies=200, seed=42))
    return result.policies


@pytest.fixture(scope="module")
def medium_portfolio():
    """500-policy portfolio for grouping / chunking tests."""
    result = generate_hk_par_portfolio(PortfolioGenerationConfig(n_policies=500, seed=7))
    return result.policies


@pytest.fixture()
def tmp_checkpoint(tmp_path):
    return tmp_path / "checkpoint.json"


# ---------------------------------------------------------------------------
# ChunkRecord serialisation
# ---------------------------------------------------------------------------


class TestChunkRecord:
    def test_round_trip_pending(self):
        rec = ChunkRecord(
            chunk_id="chunk_00000",
            group_key=(("product_line", PRODUCT_LINE_CASH),),
            start_row=0,
            end_row=100,
            n_policies=100,
        )
        assert ChunkRecord.from_dict(rec.to_dict()) == rec

    def test_round_trip_completed(self):
        rec = ChunkRecord(
            chunk_id="chunk_00001",
            group_key=(),
            start_row=0,
            end_row=50,
            n_policies=50,
            status=ChunkStatus.COMPLETED,
            result={"n_policies": 50, "total_sum_assured": 1e6,
                    "n_cash_dividend": 25, "n_reversionary_bonus": 25},
            started_at="2026-06-04T10:00:00Z",
            completed_at="2026-06-04T10:00:05Z",
        )
        restored = ChunkRecord.from_dict(rec.to_dict())
        assert restored.status == ChunkStatus.COMPLETED
        assert restored.result["n_policies"] == 50

    def test_round_trip_failed(self):
        rec = ChunkRecord(
            chunk_id="chunk_00002",
            group_key=(),
            start_row=50,
            end_row=100,
            n_policies=50,
            status=ChunkStatus.FAILED,
            error={"type": "RuntimeError", "message": "boom", "traceback": "..."},
        )
        restored = ChunkRecord.from_dict(rec.to_dict())
        assert restored.status == ChunkStatus.FAILED
        assert restored.error["type"] == "RuntimeError"


# ---------------------------------------------------------------------------
# ProcessingPlan serialisation
# ---------------------------------------------------------------------------


class TestProcessingPlan:
    def test_round_trip(self):
        plan = ProcessingPlan(
            portfolio_digest="abc123",
            n_policies=1000,
            chunk_size=100,
            group_by=["product_line"],
            n_chunks=12,
            created_at="2026-06-04T00:00:00Z",
        )
        assert ProcessingPlan.from_dict(plan.to_dict()) == plan


# ---------------------------------------------------------------------------
# CheckpointStore
# ---------------------------------------------------------------------------


class TestCheckpointStore:
    def test_save_and_load(self, tmp_checkpoint):
        store = CheckpointStore(tmp_checkpoint)
        plan = ProcessingPlan(
            portfolio_digest="d1g3st",
            n_policies=100,
            chunk_size=50,
            group_by=None,
            n_chunks=2,
            created_at="2026-01-01T00:00:00Z",
        )
        records = [
            ChunkRecord(chunk_id="chunk_00000", group_key=(), start_row=0, end_row=50, n_policies=50),
            ChunkRecord(chunk_id="chunk_00001", group_key=(), start_row=50, end_row=100, n_policies=50),
        ]
        store.save(plan, records)
        assert store.exists()
        loaded_plan, loaded_records = store.load()
        assert loaded_plan.n_policies == 100
        assert len(loaded_records) == 2

    def test_checkpoint_version_mismatch(self, tmp_checkpoint):
        store = CheckpointStore(tmp_checkpoint)
        tmp_checkpoint.parent.mkdir(parents=True, exist_ok=True)
        payload = {"checkpoint_version": "99.0", "plan": {}, "chunks": []}
        with tmp_checkpoint.open("w") as fh:
            json.dump(payload, fh)
        with pytest.raises(ValueError, match="incompatible"):
            store.load()

    def test_reset(self, tmp_checkpoint):
        store = CheckpointStore(tmp_checkpoint)
        tmp_checkpoint.parent.mkdir(parents=True, exist_ok=True)
        tmp_checkpoint.write_text("{}")
        store.reset()
        assert not store.exists()

    def test_atomic_write_leaves_no_temp_files(self, tmp_checkpoint):
        store = CheckpointStore(tmp_checkpoint)
        plan = ProcessingPlan("d", 10, 10, None, 1, "2026-01-01T00:00:00Z")
        records = [ChunkRecord("chunk_00000", (), 0, 10, 10)]
        store.save(plan, records)
        leftovers = list(tmp_checkpoint.parent.glob(".chk_*.json.tmp"))
        assert leftovers == []


# ---------------------------------------------------------------------------
# build_chunk_plan
# ---------------------------------------------------------------------------


class TestBuildChunkPlan:
    def test_basic_no_grouping(self, small_portfolio):
        plan, records = build_chunk_plan(small_portfolio, chunk_size=50)
        assert plan.n_policies == len(small_portfolio)
        assert plan.n_chunks == 4  # 200 / 50
        assert all(r.status == ChunkStatus.PENDING for r in records)
        # Row bounds cover all rows without gaps or overlaps
        all_rows = sorted((r.start_row, r.end_row) for r in records)
        assert all_rows[0][0] == 0
        assert all_rows[-1][1] == len(small_portfolio)
        for i in range(len(all_rows) - 1):
            assert all_rows[i][1] == all_rows[i + 1][0]

    def test_chunk_ids_are_unique(self, small_portfolio):
        _, records = build_chunk_plan(small_portfolio, chunk_size=30)
        ids = [r.chunk_id for r in records]
        assert len(set(ids)) == len(ids)

    def test_grouped_by_product_line(self, small_portfolio):
        _, records = build_chunk_plan(small_portfolio, chunk_size=50, group_by=["product_line"])
        # Each chunk should contain only one product line
        for rec in records:
            assert len(rec.group_key) == 1
            assert rec.group_key[0][0] == "product_line"

    def test_total_policies_covered(self, medium_portfolio):
        _, records = build_chunk_plan(medium_portfolio, chunk_size=100)
        total = sum(r.n_policies for r in records)
        assert total == len(medium_portfolio)

    def test_chunk_size_one(self, tmp_path):
        """Degenerate case: every policy is its own chunk."""
        result = generate_hk_par_portfolio(PortfolioGenerationConfig(n_policies=10, seed=1))
        plan, records = build_chunk_plan(result.policies, chunk_size=1)
        assert plan.n_chunks == 10
        assert all(r.n_policies == 1 for r in records)

    def test_invalid_chunk_size(self, small_portfolio):
        with pytest.raises(ValueError, match="chunk_size"):
            build_chunk_plan(small_portfolio, chunk_size=0)

    def test_missing_columns(self):
        df = pd.DataFrame({"policy_id": [1, 2], "junk": [0, 0]})
        with pytest.raises(ValueError, match="missing columns"):
            build_chunk_plan(df)

    def test_determinism(self, small_portfolio):
        _, records_a = build_chunk_plan(small_portfolio, chunk_size=40)
        _, records_b = build_chunk_plan(small_portfolio, chunk_size=40)
        assert [r.start_row for r in records_a] == [r.start_row for r in records_b]


# ---------------------------------------------------------------------------
# default_chunk_fn
# ---------------------------------------------------------------------------


class TestDefaultChunkFn:
    def test_required_keys_present(self, small_portfolio):
        result = default_chunk_fn(small_portfolio, "chunk_00000")
        assert REQUIRED_CHUNK_RESULT_KEYS.issubset(result.keys())

    def test_policy_count_matches(self, small_portfolio):
        result = default_chunk_fn(small_portfolio, "chunk_00000")
        assert result["n_policies"] == len(small_portfolio)

    def test_product_line_counts_sum(self, small_portfolio):
        result = default_chunk_fn(small_portfolio, "chunk_00000")
        assert result["n_cash_dividend"] + result["n_reversionary_bonus"] == result["n_policies"]


# ---------------------------------------------------------------------------
# ChunkedPortfolioProcessor -- happy path
# ---------------------------------------------------------------------------


class TestChunkedPortfolioProcessorHappyPath:
    def test_full_run(self, small_portfolio, tmp_checkpoint):
        proc = ChunkedPortfolioProcessor(tmp_checkpoint, chunk_size=50)
        summary = proc.run(small_portfolio)
        assert summary["n_completed"] == 4
        assert summary["n_failed"] == 0
        assert summary["n_pending"] == 0

    def test_checkpoint_created(self, small_portfolio, tmp_checkpoint):
        proc = ChunkedPortfolioProcessor(tmp_checkpoint, chunk_size=50)
        proc.run(small_portfolio)
        assert tmp_checkpoint.exists()

    def test_idempotent_rerun(self, small_portfolio, tmp_checkpoint):
        proc = ChunkedPortfolioProcessor(tmp_checkpoint, chunk_size=50)
        proc.run(small_portfolio)
        summary2 = proc.run(small_portfolio)
        assert summary2["n_completed"] == 4  # none re-processed

    def test_on_chunk_complete_callback(self, small_portfolio, tmp_checkpoint):
        completed_ids = []
        def _cb(rec):
            completed_ids.append(rec.chunk_id)

        proc = ChunkedPortfolioProcessor(tmp_checkpoint, chunk_size=50)
        proc.run(small_portfolio, on_chunk_complete=_cb)
        assert len(completed_ids) == 4

    def test_grouped_run(self, small_portfolio, tmp_checkpoint):
        proc = ChunkedPortfolioProcessor(
            tmp_checkpoint, chunk_size=60, group_by=["product_line"]
        )
        summary = proc.run(small_portfolio)
        assert summary["n_failed"] == 0
        assert summary["n_completed"] > 0

    def test_resume_from_checkpoint(self, small_portfolio, tmp_checkpoint):
        """Simulate partial run by completing half the chunks manually, then restart."""
        proc = ChunkedPortfolioProcessor(tmp_checkpoint, chunk_size=50)
        # Build plan without running
        proc._load_or_build(small_portfolio)
        # Manually complete first two chunks
        for rec in proc._records[:2]:
            rec.status = ChunkStatus.COMPLETED
            rec.result = {
                "chunk_id": rec.chunk_id,
                "n_policies": rec.n_policies,
                "total_sum_assured": 1.0,
                "total_annual_premium": 0.5,
                "n_cash_dividend": 0,
                "n_reversionary_bonus": rec.n_policies,
                "mean_sum_assured": 1.0,
                "mean_issue_age": 35.0,
            }
        proc.store.save(proc._plan, proc._records)

        # Second processor picks up checkpoint and runs remaining 2
        proc2 = ChunkedPortfolioProcessor(tmp_checkpoint, chunk_size=50)
        summary = proc2.run(small_portfolio)
        assert summary["n_completed"] == 4

    def test_status_summary_after_run(self, small_portfolio, tmp_checkpoint):
        proc = ChunkedPortfolioProcessor(tmp_checkpoint, chunk_size=50)
        proc.run(small_portfolio)
        status = proc.status_summary()
        assert status["n_completed"] == 4

    def test_policy_count_mismatch_raises(self, small_portfolio, tmp_checkpoint):
        proc = ChunkedPortfolioProcessor(tmp_checkpoint, chunk_size=50)
        proc.run(small_portfolio)
        # Attempt to run with a different-sized portfolio
        wrong_portfolio = small_portfolio.head(100)
        proc2 = ChunkedPortfolioProcessor(tmp_checkpoint, chunk_size=50)
        with pytest.raises(ValueError, match="checkpoint built for"):
            proc2.run(wrong_portfolio)


# ---------------------------------------------------------------------------
# ChunkedPortfolioProcessor -- failure handling
# ---------------------------------------------------------------------------


class TestChunkedPortfolioProcessorFailures:
    def _failing_fn(self, chunk_df, chunk_id):
        """Always raises for chunk_00001."""
        if chunk_id == "chunk_00001":
            raise RuntimeError("injected failure for {}".format(chunk_id))
        return default_chunk_fn(chunk_df, chunk_id)

    def test_failed_chunk_recorded(self, small_portfolio, tmp_checkpoint):
        proc = ChunkedPortfolioProcessor(
            tmp_checkpoint, chunk_fn=self._failing_fn, chunk_size=50
        )
        summary = proc.run(small_portfolio)
        assert summary["n_failed"] == 1
        assert summary["n_completed"] == 3
        assert "chunk_00001" in summary["failed_chunk_ids"]

    def test_failed_record_has_error_info(self, small_portfolio, tmp_checkpoint):
        proc = ChunkedPortfolioProcessor(
            tmp_checkpoint, chunk_fn=self._failing_fn, chunk_size=50
        )
        proc.run(small_portfolio)
        failed = proc.failed_records()
        assert len(failed) == 1
        assert failed[0].error["type"] == "RuntimeError"
        assert "injected failure" in failed[0].error["message"]

    def test_retry_failed(self, small_portfolio, tmp_checkpoint):
        proc = ChunkedPortfolioProcessor(
            tmp_checkpoint, chunk_fn=self._failing_fn, chunk_size=50
        )
        proc.run(small_portfolio)
        # Now retry with a working function
        proc.chunk_fn = default_chunk_fn
        retry_summary = proc.retry_failed(small_portfolio)
        assert retry_summary["n_failed"] == 0
        assert retry_summary["n_completed"] == 4

    def test_failed_chunk_audit_report(self, small_portfolio, tmp_checkpoint):
        proc = ChunkedPortfolioProcessor(
            tmp_checkpoint, chunk_fn=self._failing_fn, chunk_size=50
        )
        proc.run(small_portfolio)
        audit = failed_chunk_audit_report(proc.records)
        assert audit["n_failed"] == 1
        assert audit["failed_chunks"][0]["chunk_id"] == "chunk_00001"
        assert audit["failed_chunks"][0]["error_type"] == "RuntimeError"

    def test_chunk_fn_returns_non_dict(self, small_portfolio, tmp_checkpoint):
        def bad_fn(chunk_df, chunk_id):
            return "not a dict"

        proc = ChunkedPortfolioProcessor(tmp_checkpoint, chunk_fn=bad_fn, chunk_size=50)
        summary = proc.run(small_portfolio)
        assert summary["n_failed"] == 4

    def test_chunk_fn_missing_required_key(self, small_portfolio, tmp_checkpoint):
        def incomplete_fn(chunk_df, chunk_id):
            return {"n_policies": len(chunk_df)}  # missing other required keys

        proc = ChunkedPortfolioProcessor(tmp_checkpoint, chunk_fn=incomplete_fn, chunk_size=50)
        summary = proc.run(small_portfolio)
        assert summary["n_failed"] == 4


# ---------------------------------------------------------------------------
# Reconciliation
# ---------------------------------------------------------------------------


class TestReconcilePortfolio:
    def test_reconcile_passes_after_clean_run(self, small_portfolio, tmp_checkpoint):
        proc = ChunkedPortfolioProcessor(tmp_checkpoint, chunk_size=50)
        proc.run(small_portfolio)
        report = proc.reconcile(small_portfolio)
        assert report.passed
        assert report.n_failed_chunks == 0

    def test_reconcile_fails_with_failed_chunks(self, small_portfolio, tmp_checkpoint):
        def failing_fn(chunk_df, chunk_id):
            if chunk_id == "chunk_00000":
                raise RuntimeError("boom")
            return default_chunk_fn(chunk_df, chunk_id)

        proc = ChunkedPortfolioProcessor(tmp_checkpoint, chunk_fn=failing_fn, chunk_size=50)
        proc.run(small_portfolio)
        report = proc.reconcile(small_portfolio)
        assert not report.passed
        assert report.n_failed_chunks == 1

    def test_reconcile_detects_count_mismatch(self, small_portfolio):
        """Fabricate records with wrong n_policies to trigger count check."""
        _, records = build_chunk_plan(small_portfolio, chunk_size=50)
        for rec in records:
            rec.status = ChunkStatus.COMPLETED
            rec.result = {
                "n_policies": rec.n_policies + 1,  # wrong
                "total_sum_assured": float(small_portfolio["sum_assured"].sum() / len(records)),
                "n_cash_dividend": 10,
                "n_reversionary_bonus": rec.n_policies - 9,
            }
        report = reconcile_portfolio(small_portfolio, records)
        check = next(c for c in report.checks if c.name == "policy_count")
        assert not check.passed

    def test_reconcile_detects_overlap(self, small_portfolio):
        """Fabricate overlapping row bounds."""
        _, records = build_chunk_plan(small_portfolio, chunk_size=50)
        for rec in records:
            rec.status = ChunkStatus.COMPLETED
            rec.result = {
                "n_policies": rec.n_policies,
                "total_sum_assured": 1.0,
                "n_cash_dividend": 0,
                "n_reversionary_bonus": rec.n_policies,
            }
        # Introduce overlap
        records[1].start_row = records[0].end_row - 1
        report = reconcile_portfolio(small_portfolio, records)
        check = next(c for c in report.checks if c.name == "no_row_overlap")
        assert not check.passed

    def test_summary_string(self, small_portfolio, tmp_checkpoint):
        proc = ChunkedPortfolioProcessor(tmp_checkpoint, chunk_size=50)
        proc.run(small_portfolio)
        report = proc.reconcile(small_portfolio)
        s = report.summary_string()
        assert "PASSED" in s

    def test_to_dict_serialisable(self, small_portfolio, tmp_checkpoint):
        proc = ChunkedPortfolioProcessor(tmp_checkpoint, chunk_size=50)
        proc.run(small_portfolio)
        report = proc.reconcile(small_portfolio)
        d = report.to_dict()
        json.dumps(d)  # must not raise


# ---------------------------------------------------------------------------
# ReconciliationReport accessors
# ---------------------------------------------------------------------------


class TestReconciliationReportAccessors:
    def test_failed_checks_on_passing_report(self, small_portfolio, tmp_checkpoint):
        proc = ChunkedPortfolioProcessor(tmp_checkpoint, chunk_size=50)
        proc.run(small_portfolio)
        report = proc.reconcile(small_portfolio)
        assert report.failed_checks() == []

    def test_completed_and_failed_records_accessors(self, small_portfolio, tmp_checkpoint):
        proc = ChunkedPortfolioProcessor(tmp_checkpoint, chunk_size=50)
        proc.run(small_portfolio)
        assert len(proc.completed_records()) == 4
        assert len(proc.failed_records()) == 0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class TestHelpers:
    def test_chunk_id_zero_padded(self):
        assert _chunk_id(0) == "chunk_00000"
        assert _chunk_id(99999) == "chunk_99999"
        assert len(_chunk_id(42)) == len(_chunk_id(0))

    def test_no_overlap_clean(self):
        assert _check_no_overlap([(0, 10), (10, 20), (20, 30)]) == ""

    def test_no_overlap_detects_overlap(self):
        msg = _check_no_overlap([(0, 15), (10, 20)])
        assert "overlap" in msg

    def test_rel_close(self):
        assert _rel_close(1.0, 1.0 + 1e-9, 1e-6)
        assert not _rel_close(1.0, 1.1, 1e-6)

    def test_chunk_id_uniqueness_for_large_plan(self):
        ids = [_chunk_id(i) for i in range(1000)]
        assert len(set(ids)) == 1000
