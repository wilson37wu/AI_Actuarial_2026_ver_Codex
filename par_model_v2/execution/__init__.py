"""
par_model_v2.execution — Distributed Batch Execution
=====================================================

Public API for the distributed/parallel execution layer.

Exports
-------
DistributedExecutor
    Pickle-safe batch executor for parallel scenario processing.
TaskSpec
    Immutable specification for a single executable task.
ExecutionResult
    Result wrapper produced by each completed task.
ExecutionBackend
    Enum of available execution backends (PROCESS, THREAD, SEQUENTIAL).
PicklingError
    Raised when a non-picklable callable is submitted to a process backend.
make_partial_task
    Helper: bind fixed kwargs to a module-level callable (returns picklable partial).

Usage Pattern (correct — no pickling bug)
------------------------------------------
>>> from functools import partial
>>> from par_model_v2.execution import DistributedExecutor
>>>
>>> # Define worker at MODULE LEVEL — not as lambda or local function
>>> # (Module-level callables are picklable; lambdas/locals are NOT)
>>>
>>> results = DistributedExecutor().run_batch(_project_single_scenario,
...                                           arg_list=[(mp, cfg) for mp in model_points],
...                                           n_workers=4)

See par_model_v2/execution/distributed_executor.py for full documentation.
"""

from .distributed_executor import (
    DistributedExecutor,
    ExecutionBackend,
    ExecutionResult,
    PicklingError,
    TaskSpec,
    make_partial_task,
)

__all__ = [
    "DistributedExecutor",
    "ExecutionBackend",
    "ExecutionResult",
    "PicklingError",
    "TaskSpec",
    "make_partial_task",
]
