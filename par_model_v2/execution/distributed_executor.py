"""
Distributed Batch Executor — Pickle-Safe Parallel Scenario Runner
==================================================================

Motivation & Bug Fix
---------------------
The original DistributedExecutor in the v1 codebase failed with:

    ``AttributeError: Can't pickle local object '<locals>.<lambda>'``
    ``_pickle.PicklingError: Can't pickle <function <lambda>>``

Root cause: worker functions were passed as locally-scoped lambdas to
``multiprocessing.Pool.map()``.  Python's pickle protocol cannot serialise
lambdas or closures defined inside another function — only top-level
(module-level) callables are picklable.

This module fixes the bug by:
  1. Accepting only module-level callables (validated with pickle.dumps before dispatch).
  2. Providing ``make_partial_task()`` — a ``functools.partial`` wrapper for
     binding fixed kwargs to a module-level callable while preserving picklability.
  3. Using ``concurrent.futures.ProcessPoolExecutor`` (cleaner error propagation
     than raw ``multiprocessing.Pool``).
  4. Supporting a ``SEQUENTIAL`` fallback for environments where multiprocessing
     is unavailable (e.g. nested parallelism, debuggers, CI with resource limits).

Correct Usage Pattern
---------------------
Step 1 — define worker at MODULE LEVEL (not inside a function/class body):

    # In par_model_v2/projection/batch_runner.py   (module-level, picklable ✓)
    def _run_scenario(scenario_id: int, config: ProjectionConfig) -> float:
        \"\"\"Single-scenario projection worker — must be module-level.\"\"\"
        engine = MonthlyProjectionEngine(config)
        return engine.run(scenario_id).tvog

Step 2 — bind fixed args with functools.partial before passing to executor:

    from functools import partial
    from par_model_v2.execution import DistributedExecutor, make_partial_task

    worker = make_partial_task(_run_scenario, config=my_config)   # picklable ✓
    executor = DistributedExecutor(n_workers=8)
    results = executor.map(worker, scenario_ids)

Anti-patterns that WILL FAIL
-----------------------------
    # ✗ Lambda — not picklable
    executor.map(lambda sid: _run_scenario(sid, cfg), scenario_ids)

    # ✗ Local function — not picklable
    def _worker(sid):
        return _run_scenario(sid, cfg)   # closure captures 'cfg' — not picklable
    executor.map(_worker, scenario_ids)

    # ✗ Bound method of non-picklable object — not picklable
    executor.map(self._run, scenario_ids)   # only works if self is picklable

SOA / ERM Context
-----------------
This executor is the runtime backbone for:
  - Batch TVOG computation across 1,000–10,000 Q-measure scenarios (Phase 4)
  - VaR/ES Monte Carlo across 2,000–5,000 P-measure scenarios (Phase 4)
  - Stress scenario batch runs (Phase 2/3)
  - Parameter calibration grid search (Phase 4)

IA Validation Requirements Unblocked
-------------------------------------
Fixing this executor satisfies Phase 3 prerequisites for:
  VR-I01 — End-to-end integration test (deterministic ESG stub)
  VR-I02 — Multi-model-point batch run
  VR-I04 — Parallel vs sequential result consistency
  VR-G01 — Governance store audit of batch runs
  VR-G02 — Audit trail for scenario batches
  VR-G04 — Risk register update on batch completion
  + integration test harness wiring

Industry Standards
------------------
SOA ASOP 56 §3.5  — Scenario generation and validation.
IA TAS M §3.6     — Testing and validation framework.
ERM               — VaR/ES scenario batch runs at 99.5% confidence.
"""

from __future__ import annotations

import enum
import functools
import io
import logging
import pickle
import time
from concurrent.futures import Future, ProcessPoolExecutor, ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Iterator, List, Optional, Tuple, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class PicklingError(TypeError):
    """Raised when a callable submitted to a PROCESS backend is not picklable.

    This is the canonical error that manifested in the v1 DistributedExecutor
    when lambdas or locally-scoped functions were passed to multiprocessing.

    To fix: replace the lambda/local with a module-level callable, or use
    ``make_partial_task(module_level_func, **fixed_kwargs)`` to bind args.
    """


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class ExecutionBackend(str, enum.Enum):
    """Available execution backends.

    Attributes
    ----------
    PROCESS : str
        ``concurrent.futures.ProcessPoolExecutor``.  Full parallelism; workers
        run in separate OS processes — bypasses Python GIL.  Requires all
        callables and arguments to be picklable.  USE THIS for CPU-bound work
        (scenario projection, Monte Carlo).

    THREAD : str
        ``concurrent.futures.ThreadPoolExecutor``.  Workers are OS threads
        sharing the same process memory — no pickle requirement.  Suitable
        for I/O-bound work (data loading, file writing).  NOT suitable for
        CPU-bound projection due to GIL.

    SEQUENTIAL : str
        No parallelism — tasks execute one at a time in the calling thread.
        Useful for debugging, profiling, and environments where multiprocessing
        is unavailable (e.g. nested workers, certain CI environments).
        Results are identical to PROCESS/THREAD backends.
    """

    PROCESS = "process"
    THREAD = "thread"
    SEQUENTIAL = "sequential"


# ---------------------------------------------------------------------------
# Data containers
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class TaskSpec:
    """Immutable specification for a single executable task.

    Encapsulates a callable and its arguments in a picklable container.
    Validated for picklability at construction time when ``validate`` is True.

    Attributes
    ----------
    func : Callable
        Module-level callable to invoke.  Must be picklable (no lambdas,
        no locally-scoped functions, no closures over non-picklable objects).
    args : tuple
        Positional arguments for ``func``.  Must all be picklable.
    kwargs : dict
        Keyword arguments for ``func``.  Must all be picklable.
    task_id : str
        Optional human-readable identifier for logging and result correlation.

    Raises
    ------
    PicklingError
        If ``func``, ``args``, or ``kwargs`` are not picklable and
        ``validate=True`` (the default).
    """

    func: Callable
    args: tuple = field(default_factory=tuple)
    kwargs: dict = field(default_factory=dict)
    task_id: str = ""

    def __post_init__(self) -> None:
        # Validate picklability eagerly at construction so failures surface
        # at call-site rather than deep inside a worker process.
        _validate_picklable(self.func, context="TaskSpec.func")
        _validate_picklable(self.args, context="TaskSpec.args")
        _validate_picklable(self.kwargs, context="TaskSpec.kwargs")

    def invoke(self) -> Any:
        """Execute the task in the current process (used by SEQUENTIAL backend)."""
        return self.func(*self.args, **self.kwargs)


@dataclass
class ExecutionResult:
    """Result wrapper produced by each completed task.

    Attributes
    ----------
    task_id : str
        Echoes ``TaskSpec.task_id`` for correlation.
    value : Any
        Return value of the task callable on success.  None if ``error`` is set.
    error : Exception or None
        Exception raised by the task, or None on success.
    duration_seconds : float
        Wall-clock time for this task (excludes queue wait time).
    worker_index : int
        Ordinal index of the task in the submitted batch (0-based).

    Properties
    ----------
    ok : bool
        True if the task succeeded (no error).
    """

    task_id: str
    value: Any
    error: Optional[Exception]
    duration_seconds: float
    worker_index: int

    @property
    def ok(self) -> bool:
        """True if the task completed without error."""
        return self.error is None

    def unwrap(self) -> Any:
        """Return ``value``, or raise ``error`` if the task failed.

        Convenience method for callers that want to re-raise worker errors
        in the main process.
        """
        if self.error is not None:
            raise self.error
        return self.value


# ---------------------------------------------------------------------------
# Module-level worker shim
# (CRITICAL: must be at module level to be picklable)
# ---------------------------------------------------------------------------

def _execute_task_spec(task_spec: TaskSpec) -> Tuple[Any, float]:
    """Module-level shim invoked by each worker process.

    Accepts a ``TaskSpec`` (picklable), invokes it, and returns
    (result_value, duration_seconds).  Exceptions propagate to the
    ``Future`` in the main process via concurrent.futures machinery.

    This function MUST remain at module level — moving it inside a class
    or function body re-introduces the pickling bug.
    """
    t0 = time.perf_counter()
    value = task_spec.func(*task_spec.args, **task_spec.kwargs)
    return value, time.perf_counter() - t0


# ---------------------------------------------------------------------------
# Picklability validator
# ---------------------------------------------------------------------------

def _validate_picklable(obj: Any, context: str = "") -> None:
    """Attempt to pickle ``obj``; raise ``PicklingError`` with a helpful message if it fails.

    Parameters
    ----------
    obj : Any
        Object to validate.
    context : str
        Human-readable label for the object (used in error message).

    Raises
    ------
    PicklingError
        If ``obj`` cannot be serialised with the default pickle protocol.
    """
    try:
        pickle.dumps(obj, protocol=pickle.HIGHEST_PROTOCOL)
    except (pickle.PicklingError, AttributeError, TypeError) as exc:
        obj_repr = repr(obj)[:120]
        hint = (
            "\n\nFix: Replace lambda/local functions with module-level callables, "
            "or use make_partial_task(module_level_func, **fixed_kwargs) to bind "
            "configuration arguments."
        )
        raise PicklingError(
            f"[DistributedExecutor] Cannot pickle {context}: {obj_repr}"
            f"\nOriginal error: {exc}{hint}"
        ) from exc


# ---------------------------------------------------------------------------
# Public helper
# ---------------------------------------------------------------------------

def make_partial_task(func: Callable, *bound_args: Any, **bound_kwargs: Any) -> functools.partial:
    """Create a picklable ``functools.partial`` from a module-level callable.

    This is the recommended pattern for binding fixed configuration arguments
    (e.g. a ``ProjectionConfig`` object) to a scenario worker function without
    resorting to lambdas or closures.

    Parameters
    ----------
    func : Callable
        Module-level callable.  Must be picklable (no lambdas, no locals).
    *bound_args : Any
        Positional arguments to pre-bind.
    **bound_kwargs : Any
        Keyword arguments to pre-bind.

    Returns
    -------
    functools.partial
        A partial object that is picklable as long as ``func`` and all bound
        arguments are themselves picklable.

    Raises
    ------
    PicklingError
        If ``func`` or any bound argument is not picklable.

    Examples
    --------
    >>> # Module-level worker (picklable ✓)
    >>> def _project(scenario_id: int, config: dict) -> float:
    ...     return config["rate"] * scenario_id
    >>>
    >>> worker = make_partial_task(_project, config={"rate": 0.05})
    >>> worker(42)   # → 2.1
    2.1
    """
    partial_obj = functools.partial(func, *bound_args, **bound_kwargs)
    # Validate the whole partial is picklable
    _validate_picklable(partial_obj, context=f"make_partial_task({func.__name__!r})")
    return partial_obj


# ---------------------------------------------------------------------------
# Main executor class
# ---------------------------------------------------------------------------

class DistributedExecutor:
    """Pickle-safe parallel batch executor for actuarial scenario runs.

    Wraps ``concurrent.futures.ProcessPoolExecutor`` (or ThreadPoolExecutor /
    sequential fallback) with:
      - Up-front picklability validation (surfaces errors at call-site)
      - ``functools.partial`` support via ``make_partial_task``
      - Automatic fallback to SEQUENTIAL if multiprocessing is unavailable
      - Structured ``ExecutionResult`` output with timing and error capture

    Parameters
    ----------
    n_workers : int, optional
        Number of parallel workers.  Default: 4.  For SEQUENTIAL backend,
        this parameter is ignored.
    backend : ExecutionBackend, optional
        Execution backend.  Default: ``ExecutionBackend.PROCESS``.
        Use ``ExecutionBackend.SEQUENTIAL`` for debugging or single-core runs.
    fallback_to_sequential : bool, optional
        If True (default), fall back to SEQUENTIAL if the PROCESS backend
        fails to initialise (e.g. in forking-restricted environments).
    timeout_seconds : float, optional
        Per-task timeout.  None (default) means no timeout.

    Examples
    --------
    >>> # ── Correct: module-level callable ──────────────────────────────────
    >>> def _compute(x: float, scale: float) -> float:
    ...     return x * scale
    >>>
    >>> worker = make_partial_task(_compute, scale=2.5)
    >>> with DistributedExecutor(n_workers=4) as ex:
    ...     results = ex.map(worker, [1.0, 2.0, 3.0])
    >>> [r.value for r in results]
    [2.5, 5.0, 7.5]

    >>> # ── Incorrect: lambda — raises PicklingError ─────────────────────────
    >>> with DistributedExecutor() as ex:
    ...     results = ex.map(lambda x: x * 2.5, [1.0, 2.0])   # PicklingError ✗
    """

    def __init__(
        self,
        n_workers: int = 4,
        backend: ExecutionBackend = ExecutionBackend.PROCESS,
        fallback_to_sequential: bool = True,
        timeout_seconds: Optional[float] = None,
    ) -> None:
        self.n_workers = n_workers
        self.backend = backend
        self.fallback_to_sequential = fallback_to_sequential
        self.timeout_seconds = timeout_seconds
        self._executor = None  # lazy init

    # ------------------------------------------------------------------
    # Context manager protocol
    # ------------------------------------------------------------------

    def __enter__(self) -> "DistributedExecutor":
        self._start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self._stop()

    def _start(self) -> None:
        if self.backend == ExecutionBackend.SEQUENTIAL:
            return
        try:
            if self.backend == ExecutionBackend.PROCESS:
                self._executor = ProcessPoolExecutor(max_workers=self.n_workers)
            elif self.backend == ExecutionBackend.THREAD:
                self._executor = ThreadPoolExecutor(max_workers=self.n_workers)
        except Exception as exc:  # noqa: BLE001
            if self.fallback_to_sequential:
                logger.warning(
                    "DistributedExecutor: failed to start %s backend (%s). "
                    "Falling back to SEQUENTIAL.",
                    self.backend.value,
                    exc,
                )
                self.backend = ExecutionBackend.SEQUENTIAL
            else:
                raise

    def _stop(self) -> None:
        if self._executor is not None:
            self._executor.shutdown(wait=True)
            self._executor = None

    # ------------------------------------------------------------------
    # Core map interface
    # ------------------------------------------------------------------

    def map(
        self,
        func: Callable[[Any], T],
        iterable: Iterable[Any],
        task_id_prefix: str = "task",
    ) -> List[ExecutionResult]:
        """Apply ``func`` to each element in ``iterable`` in parallel.

        Parameters
        ----------
        func : Callable
            Module-level callable.  Must be picklable when using PROCESS backend.
            Use ``make_partial_task`` to bind fixed configuration arguments.
        iterable : Iterable[Any]
            Arguments passed to ``func`` one-by-one.
        task_id_prefix : str
            Prefix for auto-generated ``task_id`` labels (used for logging).

        Returns
        -------
        List[ExecutionResult]
            Results in the same order as ``iterable``.  Check ``result.ok``
            before accessing ``result.value``.

        Raises
        ------
        PicklingError
            If ``func`` is not picklable (PROCESS backend only).
        """
        items = list(iterable)
        if self.backend == ExecutionBackend.PROCESS:
            _validate_picklable(func, context="DistributedExecutor.map(func)")

        task_specs = [
            TaskSpec(
                func=func,
                args=(item,),
                task_id=f"{task_id_prefix}_{i}",
            )
            for i, item in enumerate(items)
        ]
        return self._dispatch(task_specs)

    def run_batch(
        self,
        func: Callable,
        arg_list: List[Tuple[Any, ...]],
        fixed_kwargs: Optional[dict] = None,
        task_id_prefix: str = "batch",
    ) -> List[ExecutionResult]:
        """Run a batch of tasks with per-task positional args and shared fixed kwargs.

        This is the recommended entry point for actuarial batch scenario runs.

        Parameters
        ----------
        func : Callable
            Module-level callable.  Signature: ``func(*per_task_args, **fixed_kwargs)``.
        arg_list : List[Tuple]
            Each tuple contains positional args for one task invocation.
            E.g. ``[(scenario_id_1,), (scenario_id_2,), ...]``
        fixed_kwargs : dict, optional
            Keyword arguments shared across all tasks.  Typically the projection
            configuration (model points, parameters, etc.).  Must be picklable.
        task_id_prefix : str
            Prefix for auto-generated task IDs.

        Returns
        -------
        List[ExecutionResult]
            Results in the same order as ``arg_list``.

        Examples
        --------
        >>> from par_model_v2.execution import DistributedExecutor
        >>>
        >>> # Module-level worker (must be at top of module)
        >>> def _project_scenario(scenario_id: int, config: dict) -> float:
        ...     return config["rate"] * scenario_id
        >>>
        >>> executor = DistributedExecutor(n_workers=4)
        >>> results = executor.run_batch(
        ...     _project_scenario,
        ...     arg_list=[(i,) for i in range(100)],
        ...     fixed_kwargs={"config": {"rate": 0.05}},
        ... )
        >>> values = [r.unwrap() for r in results]
        """
        fixed_kwargs = fixed_kwargs or {}
        if fixed_kwargs:
            worker = make_partial_task(func, **fixed_kwargs)
        else:
            if self.backend == ExecutionBackend.PROCESS:
                _validate_picklable(func, context="DistributedExecutor.run_batch(func)")
            worker = func

        task_specs = [
            TaskSpec(
                func=worker,
                args=args,
                task_id=f"{task_id_prefix}_{i}",
            )
            for i, args in enumerate(arg_list)
        ]
        return self._dispatch(task_specs)

    def submit_task(self, task_spec: TaskSpec) -> ExecutionResult:
        """Submit a single pre-built ``TaskSpec`` and return its result.

        Convenience method for one-off tasks.  For batches, prefer ``map``
        or ``run_batch``.
        """
        results = self._dispatch([task_spec])
        return results[0]

    # ------------------------------------------------------------------
    # Internal dispatch
    # ------------------------------------------------------------------

    def _dispatch(self, task_specs: List[TaskSpec]) -> List[ExecutionResult]:
        """Dispatch task_specs to the configured backend and collect results."""
        if not task_specs:
            return []

        started_here = self._executor is None and self.backend != ExecutionBackend.SEQUENTIAL
        if started_here:
            self._start()

        try:
            if self.backend == ExecutionBackend.SEQUENTIAL:
                return self._dispatch_sequential(task_specs)
            elif self._executor is not None:
                return self._dispatch_concurrent(task_specs)
            else:
                # fallback triggered during _start()
                return self._dispatch_sequential(task_specs)
        finally:
            if started_here:
                self._stop()

    def _dispatch_sequential(self, task_specs: List[TaskSpec]) -> List[ExecutionResult]:
        """Sequential (single-threaded) execution."""
        results: List[ExecutionResult] = []
        for i, spec in enumerate(task_specs):
            t0 = time.perf_counter()
            error: Optional[Exception] = None
            value: Any = None
            try:
                value = spec.func(*spec.args, **spec.kwargs)
                duration = time.perf_counter() - t0
            except Exception as exc:  # noqa: BLE001
                duration = time.perf_counter() - t0
                error = exc
                logger.warning(
                    "Task %s failed (sequential): %s", spec.task_id, exc
                )
            results.append(
                ExecutionResult(
                    task_id=spec.task_id,
                    value=value,
                    error=error,
                    duration_seconds=duration,
                    worker_index=i,
                )
            )
        return results

    def _dispatch_concurrent(self, task_specs: List[TaskSpec]) -> List[ExecutionResult]:
        """Concurrent execution via ProcessPoolExecutor or ThreadPoolExecutor."""
        futures: List[Tuple[int, Future]] = []
        for i, spec in enumerate(task_specs):
            future = self._executor.submit(_execute_task_spec, spec)
            futures.append((i, future))

        results: List[ExecutionResult] = [None] * len(task_specs)  # type: ignore[list-item]
        for i, future in futures:
            spec = task_specs[i]
            error: Optional[Exception] = None
            value: Any = None
            duration = 0.0
            try:
                value, duration = future.result(timeout=self.timeout_seconds)
            except Exception as exc:  # noqa: BLE001
                error = exc
                logger.warning(
                    "Task %s failed (%s backend): %s",
                    spec.task_id,
                    self.backend.value,
                    exc,
                )
            results[i] = ExecutionResult(
                task_id=spec.task_id,
                value=value,
                error=error,
                duration_seconds=duration,
                worker_index=i,
            )
        return results

    # ------------------------------------------------------------------
    # Diagnostics
    # ------------------------------------------------------------------

    def validate_callable(self, func: Callable) -> bool:
        """Return True if ``func`` is safe to submit to the PROCESS backend.

        Does not raise — catches the PicklingError and returns False.

        Parameters
        ----------
        func : Callable
            Any callable to test.

        Returns
        -------
        bool
            True if picklable; False otherwise.
        """
        try:
            _validate_picklable(func, context="validate_callable")
            return True
        except PicklingError:
            return False

    def __repr__(self) -> str:
        return (
            f"DistributedExecutor("
            f"backend={self.backend.value!r}, "
            f"n_workers={self.n_workers}, "
            f"fallback={self.fallback_to_sequential})"
        )
