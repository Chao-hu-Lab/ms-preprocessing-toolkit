"""Tests for GUI async task runner boundary."""

from __future__ import annotations

import threading

from ms_preprocessing.gui.async_task_runner import AsyncTaskRunner


class _Host:
    def __init__(self, *, schedulable: bool) -> None:
        self.schedulable = schedulable
        self.after_calls: list[tuple[int, object]] = []
        if schedulable:
            self.tk = object()
        self._pipeline_is_processing = False
        self._pipeline_worker_thread = None
        self._ui_thread_id = threading.get_ident()
        self.busy_states: list[bool] = []
        self.logs: list[str] = []

    def _can_schedule_ui_callbacks(self) -> bool:
        return self.schedulable

    def after(self, delay_ms: int, callback) -> str:
        self.after_calls.append((delay_ms, callback))
        return "after-id"

    def winfo_exists(self) -> bool:
        return True

    def _set_pipeline_busy_state(self, processing: bool) -> None:
        self._pipeline_is_processing = processing
        self.busy_states.append(processing)

    def _log(self, message: str) -> None:
        self.logs.append(message)


def test_schedules_worker_thread_when_ui_callback_scheduling_is_available() -> None:
    host = _Host(schedulable=True)
    ran = threading.Event()

    AsyncTaskRunner(host).start_task(lambda: ran.set(), name="unit-worker")

    assert host._pipeline_worker_thread is not None
    assert host._pipeline_worker_thread.name == "unit-worker"
    assert ran.wait(timeout=1.0)
    host._pipeline_worker_thread.join(timeout=1.0)
    assert len(host.after_calls) == 1
    assert host.after_calls[0][0] == 16
    assert callable(host.after_calls[0][1])


def test_supports_direct_execution_fallback() -> None:
    host = _Host(schedulable=False)
    calls: list[str] = []

    AsyncTaskRunner(host).start_task(lambda: calls.append("ran"), name="direct")

    assert calls == ["ran"]
    assert host._pipeline_worker_thread is None


def test_drains_ui_queue_on_ui_thread() -> None:
    host = _Host(schedulable=False)
    calls: list[tuple[str, int]] = []
    runner = AsyncTaskRunner(host)

    runner.dispatch(lambda value: calls.append(("callback", value)), 7)
    runner.drain_ui_queue()

    assert calls == [("callback", 7)]


def test_prevents_concurrent_tasks() -> None:
    host = _Host(schedulable=False)
    host._pipeline_is_processing = True
    calls: list[str] = []

    started = AsyncTaskRunner(host).start_task(lambda: calls.append("ran"), name="blocked")

    assert started is False
    assert calls == []


def test_clears_busy_state_after_failure() -> None:
    host = _Host(schedulable=False)

    def fail() -> None:
        raise RuntimeError("boom")

    AsyncTaskRunner(host).start_task(fail, name="failure")

    assert host.busy_states == [True, False]
    assert any("boom" in message for message in host.logs)


def test_threaded_failure_cleanup_runs_through_ui_queue() -> None:
    host = _Host(schedulable=True)

    def fail() -> None:
        raise RuntimeError("boom")

    runner = AsyncTaskRunner(host)
    runner.start_task(fail, name="failure-worker")

    assert host._pipeline_worker_thread is not None
    host._pipeline_worker_thread.join(timeout=1.0)
    assert host.logs == []
    assert host.busy_states == [True]

    runner.drain_ui_queue()

    assert host._pipeline_worker_thread is None
    assert host.busy_states == [True, False]
    assert any("boom" in message for message in host.logs)
