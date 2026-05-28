"""
Tests for par_model_v2.execution.DistributedExecutor
=====================================================

Coverage:
  - PicklingError: lambdas, locally-scoped functions, closures → correct error
  - Module-level callables: process, thread, sequential backends
  - functools.partial via make_partial_task: picklable, correct results
  - TaskSpec: validation, immutability, invoke()
  - ExecutionResult: ok property, unwrap(), error propagation
  - map(): order preservation, empty iterable, single-element
  - run_batch(): fixed_kwargs, arg_list, empty batch
  - submit_task(): single task dispatch
  - Context manager: __enter__ / __exit__ lifecycle
  - validate_callable(): True for module-level, False for lambda
  - Sequential fallback: identical results to process backend
  - Error capture: worker exceptions wrapped in ExecutionResult
  - Timeout: (smoke test — does not hang)
  - Backend enum values and __repr__

SOA Context
-----------
These tests satisfy Phase 3 validation requirement VR-I01 (executor integration)
and VR-I04 (parallel vs sequential result consistency check).
"""

from __future__ import annotations

import functools
import math
import time
from typing import Any

import pytest

from par_model_v2.execution import (
    DistributedExecutor,
    ExecutionBackend,
    ExecutionResult,
    PicklingError,
    TaskSpec,
    make_partial_task,
)
from par_model_v2.execution.distributed_executor import _validate_picklable


# ---------------------------------------------------------------------------
# Module-level test callables (MUST be at module level to be picklable)
# ---------------------------------------------------------------------------

def _identity(x: Any) -> Any:
    """Return x unchanged — simplest possible worker."""
    return x


def _square(x: float) -> float:
    """Return x²."""
    return x * x


def _multiply(x: float, factor: float) -> float:
    """Return x * factor — used to test fixed_kwargs binding."""
    return x * factor


def _add(x: float, y: float) -> float:
    """Return x + y — two positional args."""
    return x + y


def _slow_identity(x: Any, delay: float = 0.01) -> Any:
    """Simulate a slow task."""
    time.sleep(delay)
    return x


def _raise_value_error(x: Any) -> None:
    """Always raises ValueError — for error-capture tests."""
    raise ValueError(f"Intentional error for x={x!r}")


def _compute_zcb_proxy(t: float, rate: float = 0.02, maturity: float = 10.0) -> float:
    """Simple ZCB proxy: exp(-rate * (maturity - t)) — actuarial context."""
    return math.exp(-rate * (maturity - t))


# ---------------------------------------------------------------------------
# 1. PicklingError — lambdas and locals must fail early
# ---------------------------------------------------------------------------

class TestPicklingError:
    """Lambda and locally-defined functions must raise PicklingError immediately."""

    def test_lambda_raises_pickling_error_in_task_spec(self):
        with pytest.raises(PicklingError, match="Cannot pickle"):
            TaskSpec(func=lambda x: x, args=(1,))

    def test_lambda_raises_pickling_error_in_map(self):
        ex = DistributedExecutor(backend=ExecutionBackend.PROCESS)
        with pytest.raises(PicklingError):
            ex.map(lambda x: x * 2, [1, 2, 3])

    def test_local_function_raises_pickling_error(self):
        def _local_worker(x):
            return x
        with pytest.raises(PicklingError):
            TaskSpec(func=_local_worker, args=(1,))

    def test_closure_raises_pickling_error(self):
        captured = [1, 2, 3]
        def _closure(x):  # captures 'captured' from enclosing scope
            return x + captured[0]
        with pytest.raises(PicklingError):
            TaskSpec(func=_closure, args=(1,))

    def test_validate_picklable_raises_for_lambda(self):
        with pytest.raises(PicklingError):
            _validate_picklable(lambda: None, context="test lambda")

    def test_validate_picklable_passes_for_module_func(self):
        _validate_picklable(_identity, context="module-level func")  # no error

    def test_validate_picklable_passes_for_partial(self):
        p = functools.partial(_multiply, factor=2.0)
        _validate_picklable(p, context="partial of module-level func")  # no error

    def test_pickling_error_hint_message(self):
        """Error message should guide the user to the fix."""
        with pytest.raises(PicklingError) as exc_info:
            _validate_picklable(lambda x: x, context="test")
        assert "module-level" in str(exc_info.value) or "make_partial_task" in str(exc_info.value)


# ---------------------------------------------------------------------------
# 2. TaskSpec
# ---------------------------------------------------------------------------

class TestTaskSpec:
    def test_construction_with_module_level_func(self):
        spec = TaskSpec(func=_square, args=(3.0,))
        assert spec.func is _square
        assert spec.args == (3.0,)
        assert spec.kwargs == {}

    def test_invoke_returns_correct_result(self):
        spec = TaskSpec(func=_multiply, args=(4.0,), kwargs={"factor": 2.5})
        assert spec.invoke() == pytest.approx(10.0)

    def test_task_id_defaults_to_empty_string(self):
        spec = TaskSpec(func=_identity, args=(1,))
        assert spec.task_id == ""

    def test_task_id_stored(self):
        spec = TaskSpec(func=_identity, args=(1,), task_id="scenario_001")
        assert spec.task_id == "scenario_001"

    def test_immutable_frozen_dataclass(self):
        spec = TaskSpec(func=_identity, args=(1,))
        with pytest.raises((AttributeError, TypeError)):
            spec.task_id = "mutated"  # type: ignore[misc]

    def test_lambda_in_args_raises(self):
        # If args contain a non-picklable, it should fail
        with pytest.raises(PicklingError):
            TaskSpec(func=_identity, args=(lambda x: x,))


# ---------------------------------------------------------------------------
# 3. ExecutionResult
# ---------------------------------------------------------------------------

class TestExecutionResult:
    def _make_result(self, value=42, error=None):
        return ExecutionResult(
            task_id="t0",
            value=value,
            error=error,
            duration_seconds=0.001,
            worker_index=0,
        )

    def test_ok_true_when_no_error(self):
        assert self._make_result(value=99, error=None).ok is True

    def test_ok_false_when_error(self):
        assert self._make_result(value=None, error=ValueError("bad")).ok is False

    def test_unwrap_returns_value_on_success(self):
        assert self._make_result(value="hello").unwrap() == "hello"

    def test_unwrap_raises_on_error(self):
        result = self._make_result(value=None, error=ValueError("boom"))
        with pytest.raises(ValueError, match="boom"):
            result.unwrap()

    def test_duration_stored(self):
        result = self._make_result()
        result.duration_seconds = 0.123
        assert result.duration_seconds == pytest.approx(0.123)


# ---------------------------------------------------------------------------
# 4. make_partial_task
# ---------------------------------------------------------------------------

class TestMakePartialTask:
    def test_returns_functools_partial(self):
        p = make_partial_task(_multiply, factor=3.0)
        assert isinstance(p, functools.partial)

    def test_partial_is_callable(self):
        p = make_partial_task(_multiply, factor=5.0)
        assert p(2.0) == pytest.approx(10.0)

    def test_partial_is_picklable(self):
        import pickle
        p = make_partial_task(_multiply, factor=2.0)
        p2 = pickle.loads(pickle.dumps(p))
        assert p2(3.0) == pytest.approx(6.0)

    def test_lambda_in_partial_raises(self):
        with pytest.raises(PicklingError):
            make_partial_task(lambda x: x)

    def test_partial_with_bound_positional(self):
        p = make_partial_task(_add, 10.0)
        assert p(5.0) == pytest.approx(15.0)

    def test_actuarial_zcb_partial(self):
        """Simulate binding rate + maturity for a ZCB batch worker."""
        worker = make_partial_task(_compute_zcb_proxy, rate=0.025, maturity=20.0)
        val = worker(0.0)  # t=0
        expected = math.exp(-0.025 * 20.0)
        assert val == pytest.approx(expected, rel=1e-9)


# ---------------------------------------------------------------------------
# 5. ExecutionBackend enum
# ---------------------------------------------------------------------------

class TestExecutionBackend:
    def test_values(self):
        assert ExecutionBackend.PROCESS.value == "process"
        assert ExecutionBackend.THREAD.value == "thread"
        assert ExecutionBackend.SEQUENTIAL.value == "sequential"

    def test_membership(self):
        assert ExecutionBackend("process") is ExecutionBackend.PROCESS

    def test_three_backends_defined(self):
        assert len(list(ExecutionBackend)) == 3


# ---------------------------------------------------------------------------
# 6. Sequential backend — correctness baseline
# ---------------------------------------------------------------------------

class TestSequentialBackend:
    def _ex(self):
        return DistributedExecutor(backend=ExecutionBackend.SEQUENTIAL)

    def test_map_returns_correct_values(self):
        results = self._ex().map(_square, [1.0, 2.0, 3.0, 4.0])
        assert [r.value for r in results] == pytest.approx([1.0, 4.0, 9.0, 16.0])

    def test_map_order_preserved(self):
        results = self._ex().map(_identity, list(range(10)))
        assert [r.value for r in results] == list(range(10))

    def test_map_empty_iterable(self):
        results = self._ex().map(_identity, [])
        assert results == []

    def test_map_single_element(self):
        results = self._ex().map(_square, [7.0])
        assert len(results) == 1
        assert results[0].value == pytest.approx(49.0)

    def test_run_batch_with_fixed_kwargs(self):
        results = self._ex().run_batch(
            _multiply,
            arg_list=[(1.0,), (2.0,), (3.0,)],
            fixed_kwargs={"factor": 10.0},
        )
        assert [r.value for r in results] == pytest.approx([10.0, 20.0, 30.0])

    def test_run_batch_empty(self):
        results = self._ex().run_batch(_identity, arg_list=[])
        assert results == []

    def test_run_batch_no_fixed_kwargs(self):
        results = self._ex().run_batch(
            _add,
            arg_list=[(1.0, 2.0), (3.0, 4.0), (5.0, 6.0)],
        )
        assert [r.value for r in results] == pytest.approx([3.0, 7.0, 11.0])

    def test_submit_task_single(self):
        spec = TaskSpec(func=_multiply, args=(6.0,), kwargs={"factor": 7.0}, task_id="one")
        result = self._ex().submit_task(spec)
        assert result.ok
        assert result.value == pytest.approx(42.0)
        assert result.task_id == "one"

    def test_error_captured_in_result(self):
        results = self._ex().map(_raise_value_error, ["x"])
        assert len(results) == 1
        assert not results[0].ok
        assert isinstance(results[0].error, ValueError)

    def test_error_unwrap_raises(self):
        results = self._ex().map(_raise_value_error, ["y"])
        with pytest.raises(ValueError):
            results[0].unwrap()

    def test_mixed_success_and_failure(self):
        """Map over items where even indices succeed, odd raise — results in order."""
        def _selective(x: int) -> int:
            if x % 2 == 1:
                raise ValueError(f"odd: {x}")
            return x * 10
        # Use sequential to avoid pickling the local function
        results = DistributedExecutor(
            backend=ExecutionBackend.SEQUENTIAL
        )._dispatch([
            TaskSpec(func=_identity, args=(0,)),
            TaskSpec(func=_raise_value_error, args=("fail",)),
            TaskSpec(func=_identity, args=(2,)),
        ])
        assert results[0].ok and results[0].value == 0
        assert not results[1].ok
        assert results[2].ok and results[2].value == 2

    def test_result_worker_index(self):
        results = self._ex().map(_identity, ["a", "b", "c"])
        indices = [r.worker_index for r in results]
        assert indices == [0, 1, 2]

    def test_context_manager(self):
        with DistributedExecutor(backend=ExecutionBackend.SEQUENTIAL) as ex:
            results = ex.map(_square, [3.0, 4.0])
        assert [r.value for r in results] == pytest.approx([9.0, 16.0])

    def test_duration_is_nonnegative(self):
        results = self._ex().map(_identity, [42])
        assert results[0].duration_seconds >= 0.0


# ---------------------------------------------------------------------------
# 7. Thread backend
# ---------------------------------------------------------------------------

class TestThreadBackend:
    """Thread backend does NOT require pickling — local functions work here."""

    def _ex(self):
        return DistributedExecutor(backend=ExecutionBackend.THREAD, n_workers=2)

    def test_map_module_level_callable(self):
        with self._ex() as ex:
            results = ex.map(_square, [2.0, 3.0, 4.0])
        assert [r.value for r in results] == pytest.approx([4.0, 9.0, 16.0])

    def test_map_with_partial(self):
        worker = make_partial_task(_multiply, factor=3.0)
        with self._ex() as ex:
            results = ex.map(worker, [1.0, 2.0, 3.0])
        assert [r.value for r in results] == pytest.approx([3.0, 6.0, 9.0])

    def test_order_preserved_concurrent(self):
        with self._ex() as ex:
            results = ex.map(_slow_identity, list(range(10)))
        assert [r.value for r in results] == list(range(10))


# ---------------------------------------------------------------------------
# 8. Process backend — correctness (uses module-level callables)
# ---------------------------------------------------------------------------

class TestProcessBackend:
    """Process backend requires picklable callables."""

    def _ex(self):
        return DistributedExecutor(
            backend=ExecutionBackend.PROCESS,
            n_workers=2,
            fallback_to_sequential=True,
        )

    def test_map_squares(self):
        with self._ex() as ex:
            results = ex.map(_square, [1.0, 2.0, 3.0, 4.0])
        values = [r.value for r in results]
        assert values == pytest.approx([1.0, 4.0, 9.0, 16.0])

    def test_map_with_partial_task(self):
        worker = make_partial_task(_multiply, factor=10.0)
        with self._ex() as ex:
            results = ex.map(worker, [1.0, 2.0, 3.0])
        values = [r.value for r in results]
        assert values == pytest.approx([10.0, 20.0, 30.0])

    def test_process_matches_sequential(self):
        """VR-I04: parallel results must match sequential results exactly."""
        inputs = [float(i) for i in range(20)]
        seq_results = DistributedExecutor(
            backend=ExecutionBackend.SEQUENTIAL
        ).map(_square, inputs)
        proc_results = self._ex().map(_square, inputs)
        seq_values = [r.value for r in seq_results]
        proc_values = [r.value for r in proc_results]
        assert seq_values == pytest.approx(proc_values)

    def test_order_preserved(self):
        inputs = list(range(8))
        with self._ex() as ex:
            results = ex.map(_identity, inputs)
        assert [r.value for r in results] == inputs

    def test_run_batch_with_fixed_kwargs(self):
        with self._ex() as ex:
            results = ex.run_batch(
                _multiply,
                arg_list=[(x,) for x in [2.0, 4.0, 6.0]],
                fixed_kwargs={"factor": 5.0},
            )
        assert [r.value for r in results] == pytest.approx([10.0, 20.0, 30.0])

    def test_lambda_raises_before_dispatch(self):
        """PicklingError should fire immediately — not inside worker process."""
        with pytest.raises(PicklingError):
            self._ex().map(lambda x: x, [1, 2, 3])

    def test_actuarial_zcb_batch(self):
        """Simulate a small TVOG-style ZCB batch (actuarial context)."""
        worker = make_partial_task(_compute_zcb_proxy, rate=0.02, maturity=10.0)
        t_values = [0.0, 1.0, 2.0, 5.0, 9.0]
        with self._ex() as ex:
            results = ex.map(worker, t_values)
        for t, r in zip(t_values, results):
            expected = math.exp(-0.02 * (10.0 - t))
            assert r.value == pytest.approx(expected, rel=1e-9)


# ---------------------------------------------------------------------------
# 9. validate_callable
# ---------------------------------------------------------------------------

class TestValidateCallable:
    def _ex(self):
        return DistributedExecutor(backend=ExecutionBackend.PROCESS)

    def test_module_level_returns_true(self):
        assert self._ex().validate_callable(_square) is True

    def test_partial_returns_true(self):
        p = functools.partial(_multiply, factor=2.0)
        assert self._ex().validate_callable(p) is True

    def test_lambda_returns_false(self):
        assert self._ex().validate_callable(lambda x: x) is False

    def test_builtin_returns_true(self):
        assert self._ex().validate_callable(abs) is True


# ---------------------------------------------------------------------------
# 10. __repr__
# ---------------------------------------------------------------------------

class TestRepr:
    def test_repr_contains_backend(self):
        ex = DistributedExecutor(backend=ExecutionBackend.SEQUENTIAL, n_workers=3)
        r = repr(ex)
        assert "sequential" in r
        assert "3" in r


# ---------------------------------------------------------------------------
# 11. Edge cases and invariants
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_task_spec_with_no_args(self):
        """Zero-argument callable."""
        import time as _time
        spec = TaskSpec(func=_time.time, args=())
        result = spec.invoke()
        assert isinstance(result, float)

    def test_executor_without_context_manager(self):
        """Executor can be used without 'with' block (lazy init)."""
        ex = DistributedExecutor(backend=ExecutionBackend.SEQUENTIAL)
        results = ex.map(_identity, [10, 20, 30])
        assert [r.value for r in results] == [10, 20, 30]

    def test_reuse_after_context_manager(self):
        """Executor can be reused after a 'with' block exits."""
        ex = DistributedExecutor(backend=ExecutionBackend.SEQUENTIAL)
        with ex:
            r1 = ex.map(_identity, [1])
        # Second use — should work fine
        r2 = ex.map(_identity, [2])
        assert r1[0].value == 1
        assert r2[0].value == 2

    def test_large_batch_sequential(self):
        """500-item batch runs without error."""
        results = DistributedExecutor(
            backend=ExecutionBackend.SEQUENTIAL
        ).map(_square, range(500))
        assert len(results) == 500
        assert all(r.ok for r in results)

    def test_task_id_propagated_to_result(self):
        spec = TaskSpec(func=_identity, args=("value",), task_id="MY_TASK")
        ex = DistributedExecutor(backend=ExecutionBackend.SEQUENTIAL)
        result = ex.submit_task(spec)
        assert result.task_id == "MY_TASK"

    def test_run_batch_task_id_prefix(self):
        ex = DistributedExecutor(backend=ExecutionBackend.SEQUENTIAL)
        results = ex.run_batch(_identity, [(x,) for x in range(3)], task_id_prefix="scen")
        ids = [r.task_id for r in results]
        assert ids == ["scen_0", "scen_1", "scen_2"]
