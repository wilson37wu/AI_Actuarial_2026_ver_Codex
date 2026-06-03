# Phase 11 Task 2 — Chunked Portfolio Processor

## Purpose

`par_model_v2/projection/chunked_processor.py` provides a reusable framework
for processing large policy portfolios in deterministic, resumable chunks.  It
was built to support the Phase 11 educational reporting cycle over the
100,000-policy synthetic Hong Kong PAR portfolio generated in Task 1.

---

## Key Components

| Class / Function | Role |
|---|---|
| `ChunkedPortfolioProcessor` | Top-level orchestrator — run, restart, retry, reconcile |
| `build_chunk_plan` | Partition a portfolio into deterministic `ChunkRecord` objects |
| `CheckpointStore` | Atomic JSON persistence of plan + chunk statuses |
| `ProcessingPlan` | Immutable description of chunking strategy |
| `ChunkRecord` | Per-chunk metadata, status, result, and error |
| `ChunkStatus` | `PENDING → IN_PROGRESS → COMPLETED / FAILED` |
| `default_chunk_fn` | Built-in aggregation function (returns portfolio statistics per chunk) |
| `reconcile_portfolio` | Cross-checks aggregated chunk results against source portfolio |
| `ReconciliationReport` | Structured reconciliation outcome with per-check results |
| `failed_chunk_audit_report` | Structured summary of all failed chunks for operator triage |

---

## Workflow

### First run

```python
from par_model_v2.projection import ChunkedPortfolioProcessor

processor = ChunkedPortfolioProcessor(
    "outputs/phase11_checkpoint.json",
    chunk_size=10_000,
    group_by=["product_line"],   # optional: keep product lines in separate chunks
)
summary = processor.run(portfolio)
# summary: {n_chunks, n_completed, n_failed, n_pending, elapsed_seconds}
```

### Restart after interruption

Re-run the same code.  The processor reads the checkpoint, skips `COMPLETED`
chunks, and continues from where it left off.

### Retry failed chunks

```python
processor.chunk_fn = my_fixed_fn   # swap in corrected logic if needed
retry_summary = processor.retry_failed(portfolio)
```

### Reconciliation

```python
report = processor.reconcile(portfolio)
print(report.summary_string())
# "Reconciliation PASSED: 7/7 checks passed, 10 chunks OK, 0 chunks failed"
assert report.passed
```

### Failed-chunk audit

```python
from par_model_v2.projection import failed_chunk_audit_report
audit = failed_chunk_audit_report(processor.records)
# audit["failed_chunks"] contains chunk_id, error_type, error_message, row bounds
```

---

## Reconciliation Checks

| Check | Description |
|---|---|
| `all_chunks_completed` | No chunks remain FAILED or PENDING |
| `policy_count` | Sum of chunk `n_policies` equals source portfolio row count |
| `no_row_overlap` | No chunk row range overlaps another |
| `total_sum_assured` | Aggregate sum assured matches source (relative tolerance 1e-6) |
| `cash_dividend_count` | Chunk cash-dividend counts sum to source total |
| `reversionary_bonus_count` | Chunk reversionary-bonus counts sum to source total |
| `chunk_id_uniqueness` | All chunk IDs are distinct |

---

## Custom `chunk_fn`

Supply any callable `(chunk_df: pd.DataFrame, chunk_id: str) -> dict` that
returns at least these keys:

```
n_policies, total_sum_assured, n_cash_dividend, n_reversionary_bonus
```

Extra keys are preserved in the checkpoint and available for downstream
reporting.  Example — compute a reserve proxy per chunk:

```python
def reserve_chunk_fn(chunk_df, chunk_id):
    from par_model_v2.projection import default_chunk_fn
    base = default_chunk_fn(chunk_df, chunk_id)
    base["proxy_reserve"] = float(chunk_df["sum_assured"].sum() * 0.05)
    return base

processor = ChunkedPortfolioProcessor(
    "outputs/phase11_reserve_checkpoint.json",
    chunk_fn=reserve_chunk_fn,
    chunk_size=10_000,
)
```

---

## Checkpoint File Format

```json
{
  "checkpoint_version": "1.0",
  "saved_at": "2026-06-04T10:00:00Z",
  "plan": {
    "portfolio_digest": "abc123def456",
    "n_policies": 100000,
    "chunk_size": 10000,
    "group_by": ["product_line"],
    "n_chunks": 12,
    "created_at": "2026-06-04T10:00:00Z"
  },
  "chunks": [
    {
      "chunk_id": "chunk_00000",
      "group_key": [["product_line", "CASH_DIVIDEND"]],
      "start_row": 0,
      "end_row": 10000,
      "n_policies": 10000,
      "status": "COMPLETED",
      "result": { "n_policies": 10000, "total_sum_assured": 5000000.0, ... },
      "error": null,
      "started_at": "2026-06-04T10:00:01Z",
      "completed_at": "2026-06-04T10:00:03Z"
    }
  ]
}
```

To force a full rerun, delete the checkpoint file or call `processor.store.reset()`.

---

## Industry Standards Alignment

**SOA ASOP 56 (Actuarial Models):**
- Reproducibility: plan is deterministic; same portfolio always produces the
  same chunk boundaries.
- Auditability: every chunk outcome (success or failure) is persisted with
  timestamps and full error details.
- Model-use restriction: this module is for educational / research use only.

**IA TAS M / TAS 100:**
- Traceability: checkpoint JSON links each chunk to its row bounds, group key,
  start/end timestamps, and aggregated results.
- Error governance: failed chunks are preserved in the audit trail rather than
  silently skipped; explicit retry path enables controlled remediation.

---

## Limitations

- **Single-process only.**  The atomic rename is safe for one process.  For
  parallel workers an external lock or database-backed store is required.
- **Synchronous execution.**  `chunk_fn` runs in the calling process.  For
  distributed workloads wrap with `multiprocessing` or `concurrent.futures`;
  the checkpoint and reconciliation layer here remains reusable.
- **Plan immutability.**  Changing `chunk_size` or `group_by` after a plan is
  saved requires deleting the checkpoint.  Row bounds in the plan are not
  sensitive to portfolio column changes (only to row count).
