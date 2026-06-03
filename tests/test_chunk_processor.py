"""
Tests for Phase 11 Task 2: grouping, chunking, checkpoint restart, failed-chunk
audit, and reconciliation (par_model_v2/projection/chunk_processor.py).
"""

from __future__ import annotations

import json
import math
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from par_model_v2.projection.portfolio_generator import (
    PortfolioGenerationConfig,
    generate_hk_par_portfolio,
    portfolio_digest,
)
from par_model_v2.projection.chunk_processor import (
    AGE_BANDS,
    RECONCILE_COLS,
    ChunkStatus,
    ChunkedProcessor,
    ChunkedProcessorConfig,
    CheckpointStore,
    ControlTotalResult,
    FailedChunkAuditEntry,
    FailedChunkAuditReport,
    GroupKey,
    PolicyGroup,
    ReconciliationReport,
    build_policy_groups,
    build_run_metadata,
    group_summary_table,
    reconcile,
    _default_chunk_fn,
    _age_band_label,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SMALL_CFG = PortfolioGenerationConfig(n_policies=3_000, seed=42)


@pytest.fixture(scope="module")
def small_result():
    return generate_hk_par_portfolio(SMALL_CFG)


@pytest.fixture(scope="module")
def small_table(small_result):
    return small_result.policies


@pytest.fixture(scope="module")
def small_digest(small_table):
    return portfolio_digest(small_table)


# ---------------------------------------------------------------------------
# Age-band labelling
# ---------------------------------------------------------------------------

class TestAgeBandLabel:
    def test_young(self):
        assert _age_band_label(25) == "18-29"

    def test_boundary_30(self):
        assert _age_band_label(30) == "30-39"

    def test_boundary_40(self):
        assert _age_band_label(40) == "40-49"

    def test_boundary_60(self):
        assert _age_band_label(60) == "60+"

    def test_senior(self):
        assert _age_band_label(65) == "60+"


# ---------------------------------------------------------------------------
# GroupKey
# ---------------------------------------------------------------------------

class TestGroupKey:
    def test_label_format(self):
        key = GroupKey("CASH_DIVIDEND", "30-39", 10)
        assert key.to_label() == "CASH_DIVIDEND|30-39|T10"

    def test_to_dict_keys(self):
        key = GroupKey("REVERSIONARY_BONUS", "40-49", 20)
        d = key.to_dict()
        assert set(d.keys()) == {"product_line", "age_band", "term_years"}

    def test_frozen_immutability(self):
        key = GroupKey("CASH_DIVIDEND", "18-29", 5)
        with pytest.raises((TypeError, AttributeError)):
            key.product_line = "OTHER"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# PolicyGroup and build_policy_groups
# ---------------------------------------------------------------------------

class TestBuildPolicyGroups:
    def test_returns_dict_of_policy_groups(self, small_table):
        groups = build_policy_groups(small_table)
        assert isinstance(groups, dict)
        assert all(isinstance(v, PolicyGroup) for v in groups.values())

    def test_labels_are_sorted(self, small_table):
        groups = build_policy_groups(small_table)
        labels = list(groups.keys())
        assert labels == sorted(labels)

    def test_non_overlapping_exhaustive_coverage(self, small_table):
        groups = build_policy_groups(small_table)
        total = sum(g.n_policies for g in groups.values())
        assert total == len(small_table)

    def test_unique_policy_ids_across_groups(self, small_table):
        groups = build_policy_groups(small_table)
        all_ids = pd.concat(
            [g.policies["policy_id"] for g in groups.values()], ignore_index=True
        )
        assert not all_ids.duplicated().any()

    def test_group_summary_n_policies_consistent(self, small_table):
        groups = build_policy_groups(small_table)
        for label, g in groups.items():
            assert g.group_summary["n_policies"] == g.n_policies, label

    def test_control_totals_sum_to_portfolio(self, small_table):
        groups = build_policy_groups(small_table)
        for col in RECONCILE_COLS:
            group_total = sum(g.control_totals()[col] for g in groups.values())
            portfolio_total = float(small_table[col].sum())
            assert math.isclose(group_total, portfolio_total, rel_tol=1e-9), col

    def test_missing_column_raises(self, small_table):
        bad = small_table.drop(columns=["policy_id"])
        with pytest.raises(ValueError, match="missing required columns"):
            build_policy_groups(bad)

    def test_product_line_assignment(self, small_table):
        groups = build_policy_groups(small_table)
        for label, g in groups.items():
            unique_lines = g.policies["product_line"].unique()
            assert len(unique_lines) == 1, f"mixed product lines in group {label}"
            assert unique_lines[0] == g.key.product_line

    def test_age_band_assignment(self, small_table):
        groups = build_policy_groups(small_table)
        for label, g in groups.items():
            computed = g.policies["issue_age"].map(_age_band_label)
            assert (computed == g.key.age_band).all(), label

    def test_term_assignment(self, small_table):
        groups = build_policy_groups(small_table)
        for label, g in groups.items():
            assert (g.policies["term_years"] == g.key.term_years).all(), label


# ---------------------------------------------------------------------------
# group_summary_table
# ---------------------------------------------------------------------------

class TestGroupSummaryTable:
    def test_shape_and_columns(self, small_table):
        groups = build_policy_groups(small_table)
        df = group_summary_table(groups)
        assert isinstance(df, pd.DataFrame)
        assert "group_label" in df.columns
        assert "n_policies" in df.columns
        for col in RECONCILE_COLS:
            assert col in df.columns

    def test_row_count_equals_number_of_groups(self, small_table):
        groups = build_policy_groups(small_table)
        df = group_summary_table(groups)
        assert len(df) == len(groups)

    def test_total_n_policies_matches_portfolio(self, small_table):
        groups = build_policy_groups(small_table)
        df = group_summary_table(groups)
        assert df["n_policies"].sum() == len(small_table)


# ---------------------------------------------------------------------------
# CheckpointStore
# ---------------------------------------------------------------------------

class TestCheckpointStore:
    def test_initialise_creates_file(self, small_table, tmp_path):
        cp_path = tmp_path / "cp.json"
        store = CheckpointStore(cp_path, portfolio_digest="abc", chunk_size=500)
        records = store.initialise(small_table)
        assert cp_path.exists()
        assert len(records) == math.ceil(len(small_table) / 500)

    def test_all_records_pending_after_init(self, small_table, tmp_path):
        cp_path = tmp_path / "cp.json"
        store = CheckpointStore(cp_path, chunk_size=500)
        records = store.initialise(small_table)
        assert all(r.status == ChunkStatus.PENDING for r in records)

    def test_row_ranges_are_contiguous(self, small_table, tmp_path):
        cp_path = tmp_path / "cp.json"
        store = CheckpointStore(cp_path, chunk_size=500)
        records = store.initialise(small_table)
        for i, rec in enumerate(records):
            if i > 0:
                assert rec.start_row == records[i - 1].end_row

    def test_load_restores_records(self, small_table, tmp_path):
        cp_path = tmp_path / "cp.json"
        store = CheckpointStore(cp_path, chunk_size=500)
        records = store.initialise(small_table)
        records[0].status = ChunkStatus.DONE
        store.update_chunk(records, 0)

        store2 = CheckpointStore(cp_path, chunk_size=500)
        loaded, _meta = store2.load()
        assert loaded[0].status == ChunkStatus.DONE
        assert all(r.status == ChunkStatus.PENDING for r in loaded[1:])

    def test_load_raises_if_file_missing(self, tmp_path):
        store = CheckpointStore(tmp_path / "missing.json")
        with pytest.raises(FileNotFoundError):
            store.load()

    def test_digest_mismatch_raises(self, small_table, tmp_path):
        cp_path = tmp_path / "cp.json"
        store = CheckpointStore(cp_path, portfolio_digest="digest_A", chunk_size=500)
        store.initialise(small_table)

        store2 = CheckpointStore(cp_path, portfolio_digest="digest_B", chunk_size=500)
        with pytest.raises(ValueError, match="digest mismatch"):
            store2.load()

    def test_empty_digest_skips_check(self, small_table, tmp_path):
        cp_path = tmp_path / "cp.json"
        store = CheckpointStore(cp_path, portfolio_digest="digest_A", chunk_size=500)
        store.initialise(small_table)

        store2 = CheckpointStore(cp_path, portfolio_digest="", chunk_size=500)
        records, _ = store2.load()  # should not raise
        assert len(records) > 0

    def test_checkpoint_json_structure(self, small_table, tmp_path):
        cp_path = tmp_path / "cp.json"
        store = CheckpointStore(cp_path, portfolio_digest="d1", chunk_size=500)
        store.initialise(small_table)
        with cp_path.open() as fh:
            data = json.load(fh)
        assert "version" in data
        assert "run_id" in data
        assert "chunks" in data
        assert data["chunk_size"] == 500


# ---------------------------------------------------------------------------
# ChunkedProcessor with default stub fn
# ---------------------------------------------------------------------------

class TestChunkedProcessorHappyPath:
    def _cfg(self, tmp_path: Path) -> ChunkedProcessorConfig:
        return ChunkedProcessorConfig(
            chunk_size=500,
            checkpoint_path=tmp_path / "cp.json",
            audit_path=tmp_path / "audit.json",
            reconciliation_path=tmp_path / "recon.json",
        )

    def test_reconciliation_passes_on_clean_run(self, small_table, small_digest, tmp_path):
        cfg = self._cfg(tmp_path)
        processor = ChunkedProcessor(small_table, config=cfg, portfolio_digest=small_digest)
        recon = processor.run()
        assert recon.overall_passed

    def test_all_chunks_done_after_run(self, small_table, tmp_path):
        cfg = self._cfg(tmp_path)
        processor = ChunkedProcessor(small_table, config=cfg)
        processor.run()
        records, _ = processor._store.load()
        assert all(r.status == ChunkStatus.DONE for r in records)

    def test_reconciliation_file_written(self, small_table, tmp_path):
        cfg = self._cfg(tmp_path)
        processor = ChunkedProcessor(small_table, config=cfg)
        processor.run()
        assert cfg.reconciliation_path.exists()

    def test_no_audit_file_on_clean_run(self, small_table, tmp_path):
        cfg = self._cfg(tmp_path)
        processor = ChunkedProcessor(small_table, config=cfg)
        processor.run()
        assert not cfg.audit_path.exists()

    def test_n_chunks_equals_ceil_divide(self, small_table, tmp_path):
        cfg = self._cfg(tmp_path)
        processor = ChunkedProcessor(small_table, config=cfg)
        recon = processor.run()
        expected = math.ceil(len(small_table) / cfg.chunk_size)
        assert recon.n_chunks_total == expected

    def test_processed_n_policies_matches_source(self, small_table, tmp_path):
        cfg = self._cfg(tmp_path)
        processor = ChunkedProcessor(small_table, config=cfg)
        recon = processor.run()
        assert recon.processed_n_policies == len(small_table)

    def test_restart_skips_done_chunks(self, small_table, tmp_path):
        cfg = self._cfg(tmp_path)
        call_count = {"n": 0}

        def counting_fn(chunk: pd.DataFrame):
            call_count["n"] += 1
            return _default_chunk_fn(chunk)

        # First run: process all chunks.
        p1 = ChunkedProcessor(small_table, config=cfg)
        p1.run(chunk_fn=counting_fn)
        first_count = call_count["n"]

        # Second run: all chunks already DONE — fn should not be called.
        call_count["n"] = 0
        p2 = ChunkedProcessor(small_table, config=cfg)
        recon = p2.run(chunk_fn=counting_fn)
        assert call_count["n"] == 0
        assert recon.overall_passed


# ---------------------------------------------------------------------------
# ChunkedProcessor with injected failures
# ---------------------------------------------------------------------------

class TestChunkedProcessorWithFailures:
    def _cfg(self, tmp_path: Path) -> ChunkedProcessorConfig:
        return ChunkedProcessorConfig(
            chunk_size=500,
            checkpoint_path=tmp_path / "cp.json",
            audit_path=tmp_path / "audit.json",
            reconciliation_path=tmp_path / "recon.json",
            retry_failed=False,
        )

    def _failing_fn(self, fail_idx: int):
        """Return a chunk_fn that raises for chunk at position fail_idx."""
        call_count = {"n": 0}

        def fn(chunk: pd.DataFrame):
            idx = call_count["n"]
            call_count["n"] += 1
            if idx == fail_idx:
                raise RuntimeError(f"injected failure at chunk {fail_idx}")
            return _default_chunk_fn(chunk)

        return fn

    def test_failed_chunk_recorded_in_checkpoint(self, small_table, tmp_path):
        cfg = self._cfg(tmp_path)
        processor = ChunkedProcessor(small_table, config=cfg)
        processor.run(chunk_fn=self._failing_fn(0))
        records, _ = processor._store.load()
        assert any(r.status == ChunkStatus.FAILED for r in records)

    def test_audit_file_written_on_failure(self, small_table, tmp_path):
        cfg = self._cfg(tmp_path)
        processor = ChunkedProcessor(small_table, config=cfg)
        processor.run(chunk_fn=self._failing_fn(0))
        assert cfg.audit_path.exists()

    def test_audit_entry_contains_error_info(self, small_table, tmp_path):
        cfg = self._cfg(tmp_path)
        processor = ChunkedProcessor(small_table, config=cfg)
        processor.run(chunk_fn=self._failing_fn(0))
        with cfg.audit_path.open() as fh:
            data = json.load(fh)
        assert data["n_failed"] == 1
        entry = data["entries"][0]
        assert entry["error_class"] == "RuntimeError"
        assert "injected failure" in entry["error_message"]
        assert "Traceback" in entry["stack_trace"]

    def test_reconciliation_fails_when_chunks_failed(self, small_table, tmp_path):
        cfg = self._cfg(tmp_path)
        processor = ChunkedProcessor(small_table, config=cfg)
        recon = processor.run(chunk_fn=self._failing_fn(0))
        assert not recon.overall_passed
        assert recon.n_chunks_failed == 1

    def test_retry_failed_true_reruns_failed_chunk(self, small_table, tmp_path):
        # First run: fail chunk 0.
        cfg_fail = ChunkedProcessorConfig(
            chunk_size=500,
            checkpoint_path=tmp_path / "cp.json",
            audit_path=tmp_path / "audit.json",
            reconciliation_path=tmp_path / "recon.json",
            retry_failed=True,
        )
        p1 = ChunkedProcessor(small_table, config=cfg_fail)
        p1.run(chunk_fn=self._failing_fn(0))

        # Second run: retry_failed=True, fn succeeds this time.
        p2 = ChunkedProcessor(small_table, config=cfg_fail)
        recon = p2.run(chunk_fn=_default_chunk_fn)
        assert recon.overall_passed


# ---------------------------------------------------------------------------
# Reconciliation function directly
# ---------------------------------------------------------------------------

class TestReconcileFunction:
    def test_perfect_reconciliation(self, small_table):
        from par_model_v2.projection.chunk_processor import ChunkRecord
        import math

        chunk_size = 500
        chunks = list(
            small_table.sort_values(["product_line", "policy_id"], kind="mergesort")
            .reset_index(drop=True)
            .pipe(lambda df: (df.iloc[s:s + chunk_size] for s in range(0, len(df), chunk_size)))
        )
        records = []
        start = 0
        for i, chunk in enumerate(chunks):
            n = len(chunk)
            rec = ChunkRecord(
                chunk_index=i,
                start_row=start,
                end_row=start + n,
                n_rows=n,
                status=ChunkStatus.DONE,
                control_totals={col: float(chunk[col].sum()) for col in RECONCILE_COLS},
            )
            records.append(rec)
            start += n

        recon = reconcile(small_table, records, tolerance=0.01)
        assert recon.overall_passed
        assert recon.n_chunks_failed == 0
        assert recon.n_chunks_pending == 0

    def test_missing_policies_fails_reconciliation(self, small_table):
        from par_model_v2.projection.chunk_processor import ChunkRecord

        # Only one DONE chunk covering a fraction of policies.
        rec = ChunkRecord(
            chunk_index=0,
            start_row=0,
            end_row=500,
            n_rows=500,
            status=ChunkStatus.DONE,
            control_totals={col: float(small_table.iloc[:500][col].sum()) for col in RECONCILE_COLS},
        )
        recon = reconcile(small_table, [rec], tolerance=0.01)
        assert not recon.overall_passed
        exceptions_text = " ".join(recon.exceptions)
        assert "policy count mismatch" in exceptions_text

    def test_financial_mismatch_fails_reconciliation(self, small_table):
        from par_model_v2.projection.chunk_processor import ChunkRecord

        ordered = small_table.sort_values(
            ["product_line", "policy_id"], kind="mergesort"
        ).reset_index(drop=True)
        records = []
        start = 0
        chunk_size = 500
        for i, s in enumerate(range(0, len(ordered), chunk_size)):
            chunk = ordered.iloc[s:s + chunk_size]
            n = len(chunk)
            totals = {col: float(chunk[col].sum()) for col in RECONCILE_COLS}
            if i == 0:
                totals["sum_assured"] += 1_000_000.0  # inject mismatch
            records.append(
                ChunkRecord(
                    chunk_index=i,
                    start_row=start,
                    end_row=start + n,
                    n_rows=n,
                    status=ChunkStatus.DONE,
                    control_totals=totals,
                )
            )
            start += n

        recon = reconcile(small_table, records, tolerance=0.01)
        assert not recon.overall_passed
        failed_cols = [r.column for r in recon.control_total_results if not r.passed]
        assert "sum_assured" in failed_cols

    def test_pending_chunks_fail_reconciliation(self, small_table):
        from par_model_v2.projection.chunk_processor import ChunkRecord

        rec = ChunkRecord(
            chunk_index=0,
            start_row=0,
            end_row=500,
            n_rows=500,
            status=ChunkStatus.PENDING,
        )
        recon = reconcile(small_table, [rec], tolerance=0.01)
        assert not recon.overall_passed
        assert recon.n_chunks_pending == 1


# ---------------------------------------------------------------------------
# FailedChunkAuditReport serialisation
# ---------------------------------------------------------------------------

class TestFailedChunkAuditReport:
    def test_to_dict_structure(self):
        entry = FailedChunkAuditEntry(
            chunk_index=3,
            start_row=1500,
            end_row=2000,
            n_rows=500,
            run_id="test-run",
            attempted_at="2026-06-04T00:00:00Z",
            error_class="ValueError",
            error_message="test error",
            stack_trace="Traceback ...",
        )
        report = FailedChunkAuditReport(run_id="test-run", generated_at="2026-06-04T00:00:00Z", entries=[entry])
        d = report.to_dict()
        assert d["n_failed"] == 1
        assert d["entries"][0]["error_class"] == "ValueError"

    def test_write_creates_valid_json(self, tmp_path):
        report = FailedChunkAuditReport(run_id="r1", generated_at="2026-06-04T00:00:00Z")
        path = report.write(tmp_path / "audit.json")
        with path.open() as fh:
            data = json.load(fh)
        assert data["n_failed"] == 0


# ---------------------------------------------------------------------------
# ReconciliationReport serialisation
# ---------------------------------------------------------------------------

class TestReconciliationReport:
    def test_write_creates_valid_json(self, small_table, tmp_path):
        cfg = ChunkedProcessorConfig(
            chunk_size=500,
            checkpoint_path=tmp_path / "cp.json",
            audit_path=tmp_path / "audit.json",
            reconciliation_path=tmp_path / "recon.json",
        )
        processor = ChunkedProcessor(small_table, config=cfg)
        recon = processor.run()
        with cfg.reconciliation_path.open() as fh:
            data = json.load(fh)
        assert "overall_passed" in data
        assert "control_total_results" in data
        assert isinstance(data["control_total_results"], list)

    def test_reconciliation_passed_true_in_json(self, small_table, tmp_path):
        cfg = ChunkedProcessorConfig(
            chunk_size=500,
            checkpoint_path=tmp_path / "cp.json",
            audit_path=tmp_path / "audit.json",
            reconciliation_path=tmp_path / "recon.json",
        )
        processor = ChunkedProcessor(small_table, config=cfg)
        processor.run()
        with cfg.reconciliation_path.open() as fh:
            data = json.load(fh)
        assert data["overall_passed"] is True


# ---------------------------------------------------------------------------
# iter_chunks interface
# ---------------------------------------------------------------------------

class TestIterChunks:
    def test_iter_chunks_yields_all_pending(self, small_table, tmp_path):
        cfg = ChunkedProcessorConfig(
            chunk_size=500,
            checkpoint_path=tmp_path / "cp.json",
            audit_path=tmp_path / "audit.json",
            reconciliation_path=tmp_path / "recon.json",
        )
        processor = ChunkedProcessor(small_table, config=cfg)
        chunks = list(processor.iter_chunks())
        expected = math.ceil(len(small_table) / 500)
        assert len(chunks) == expected

    def test_iter_chunks_yields_correct_row_counts(self, small_table, tmp_path):
        cfg = ChunkedProcessorConfig(
            chunk_size=500,
            checkpoint_path=tmp_path / "cp.json",
            audit_path=tmp_path / "audit.json",
            reconciliation_path=tmp_path / "recon.json",
        )
        processor = ChunkedProcessor(small_table, config=cfg)
        total = sum(len(df) for _, df in processor.iter_chunks())
        assert total == len(small_table)


# ---------------------------------------------------------------------------
# build_run_metadata
# ---------------------------------------------------------------------------

class TestBuildRunMetadata:
    def test_metadata_fields_populated(self, small_table, tmp_path):
        cfg = ChunkedProcessorConfig(
            chunk_size=500,
            checkpoint_path=tmp_path / "cp.json",
            audit_path=tmp_path / "audit.json",
            reconciliation_path=tmp_path / "recon.json",
        )
        processor = ChunkedProcessor(small_table, config=cfg)
        recon = processor.run()
        meta = build_run_metadata(processor, recon, started_at="2026-06-04T00:00:00Z")
        assert meta.reconciliation_passed
        assert meta.n_done == recon.n_chunks_done
        d = meta.to_dict()
        assert "run_id" in d
        assert "processor_version" in d
