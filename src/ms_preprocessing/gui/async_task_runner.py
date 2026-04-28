"""Async worker and UI queue coordination for GUI controllers."""

from __future__ import annotations

import queue
import threading
from collections.abc import Callable
from typing import Any


class AsyncTaskRunner:
    """Coordinate background work and UI-thread callback delivery."""

    def __init__(self, host: Any) -> None:
        self._host = host
        self.ensure_state()

    def ensure_state(self) -> None:
        host = self._host
        if "_ui_thread_id" not in host.__dict__:
            host._ui_thread_id = threading.get_ident()
        if "_ui_queue" not in host.__dict__:
            host._ui_queue = queue.SimpleQueue()
        if "_ui_queue_after_id" not in host.__dict__:
            host._ui_queue_after_id = None
        if "_pipeline_worker_thread" not in host.__dict__:
            host._pipeline_worker_thread = None
        if "_pipeline_is_processing" not in host.__dict__:
            host._pipeline_is_processing = False
        if "_step_output_save_threads" not in host.__dict__:
            host._step_output_save_threads = []

    def can_schedule_ui_callbacks(self) -> bool:
        host = self._host
        after = getattr(host, "after", None)
        winfo_exists = getattr(host, "winfo_exists", None)
        return "tk" in host.__dict__ and callable(after) and callable(winfo_exists)

    def dispatch(self, callback: Callable[..., Any], *args: Any) -> None:
        self.ensure_state()
        if threading.get_ident() == self._host._ui_thread_id or not self._can_schedule_callbacks():
            callback(*args)
            return
        self._host._ui_queue.put((callback, args))

    def schedule_ui_queue_drain(self) -> None:
        self.ensure_state()
        host = self._host
        if not self._can_schedule_callbacks():
            return
        if host._ui_queue_after_id is not None:
            return
        try:
            if not host.winfo_exists():
                return
        except Exception:
            return
        host._ui_queue_after_id = host.after(16, self.drain_ui_queue)

    def drain_ui_queue(self) -> None:
        host = self._host
        host._ui_queue_after_id = None
        if self._can_schedule_callbacks():
            try:
                if not host.winfo_exists():
                    return
            except Exception:
                return

        while True:
            try:
                callback, args = host._ui_queue.get_nowait()
            except queue.Empty:
                break
            callback(*args)

        save_threads = [thread for thread in host._step_output_save_threads if thread.is_alive()]
        host._step_output_save_threads = save_threads
        worker_alive = (
            host._pipeline_worker_thread is not None and host._pipeline_worker_thread.is_alive()
        ) or bool(save_threads)
        if worker_alive or not host._ui_queue.empty():
            self.schedule_ui_queue_drain()

    def start_task(self, worker: Callable[[], Any], *, name: str) -> bool:
        self.ensure_state()
        host = self._host
        if host._pipeline_is_processing:
            return False

        host._set_pipeline_busy_state(True)
        if self._can_schedule_callbacks():
            self.schedule_ui_queue_drain()
            thread = threading.Thread(
                target=self._run_worker,
                args=(worker,),
                daemon=True,
                name=name,
            )
            host._pipeline_worker_thread = thread
            thread.start()
            return True

        self._run_worker(worker)
        return True

    def _run_worker(self, worker: Callable[[], Any]) -> None:
        try:
            worker()
        except Exception as exc:
            self.dispatch(self._finish_worker_failure, exc)

    def _finish_worker_failure(self, exc: Exception) -> None:
        self._host._pipeline_worker_thread = None
        self._host._log(f"Async task error: {exc}")
        self._host._set_pipeline_busy_state(False)

    def _can_schedule_callbacks(self) -> bool:
        override = getattr(self._host, "_can_schedule_ui_callbacks", None)
        if callable(override):
            return bool(override())
        return self.can_schedule_ui_callbacks()
