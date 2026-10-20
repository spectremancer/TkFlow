"""Reusable command execution, progress, cancellation and debounce policies."""
from __future__ import annotations
from concurrent.futures import Future
import threading
from ._helpers import _callback
from .state import State


class CommandContext:
    """Worker-safe cooperative cancellation and progress delivery."""
    def __init__(self, command, generation):
        self._command = command
        self._generation = generation
        self.cancel_event = command._cancel_event

    @property
    def cancelled(self):
        return self.cancel_event.is_set() or self._command.app.stop_event.is_set()

    def report(self, value):
        command = self._command
        # Coalesce progress: at most one pending delivery per command invocation.
        with command._progress_lock:
            command._progress_value = value
            if command._progress_queued:
                return
            command._progress_queued = True
        command.app.call_soon(command._deliver_progress, self._generation)


class Command:
    """Capture on the GUI thread, run bounded work, deliver lifetime-safe results.

    context=True passes a CommandContext before prepared arguments. debounce_ms
    schedules only the most recent invocation; owner guards callbacks and cleanup.
    """
    def __init__(self, app, function, *, prepare=None, background=True,
                 on_result=None, on_error=None, on_done=None, on_progress=None,
                 context=False, owner=None, debounce_ms=0):
        for name, callback in (("function", function), ("prepare", prepare), ("on_result", on_result),
                               ("on_error", on_error), ("on_done", on_done), ("on_progress", on_progress)):
            _callback(callback, name)
        if function is None:
            raise TypeError("function must be callable")
        if isinstance(debounce_ms, bool) or not isinstance(debounce_ms, int) or debounce_ms < 0:
            raise ValueError("debounce_ms must be a nonnegative integer")
        self.app, self.function, self.prepare = app, function, prepare
        self.background, self.owner, self.context = background, owner, context
        self.on_result, self.on_error, self.on_done = on_result, on_error, on_done
        self.on_progress = on_progress
        self.debounce_ms = debounce_ms
        self.future: Future | None = None
        self.running = False
        self._disposed = False
        self.busy = State(False)
        self.progress = State(None)
        self._cancel_event = threading.Event()
        self._timer = None
        self._generation = 0
        self._progress_lock = threading.Lock()
        self._progress_queued = False
        self._progress_value = None
        if owner is not None:
            owner.on_dispose(self.dispose)
        app.on_dispose(self.cancel)

    def _alive(self):
        return not self._disposed and not self.app._closed and (self.owner is None or not getattr(self.owner, "_destroyed", False)
                                         and not getattr(self.owner, "_closed", False))

    def __call__(self, *args):
        self.app._check_thread()
        if not self._alive():
            return None
        if self.debounce_ms:
            if self._timer is not None:
                self.app.root.after_cancel(self._timer)
            self._timer = self.app.after(self.debounce_ms, self._start, args)
            return None
        return self._start(args)

    def _start(self, args):
        self._timer = None
        if not self._alive():
            return None
        if self.running:
            return self.future
        self.running = True
        self._generation += 1
        self._cancel_event = threading.Event()
        self._progress_queued = False
        self.busy.set(True)
        self.progress.set(None)
        try:
            if self.prepare is not None:
                args = self.prepare(*args)
                if not isinstance(args, tuple):
                    raise TypeError("prepare must return a tuple of worker arguments")
            if self.context:
                args = (CommandContext(self, self._generation), *args)
            if self.background:
                self.future = self.app.run_in_thread(self.function, *args,
                                                    on_result=self._success, on_error=self._failure)
                self.future.add_done_callback(self._cancelled)
                return self.future
            result = self.function(*args)
        except Exception as error:
            self._failure(error)
            return None
        self._success(result)
        return result

    def _deliver_progress(self, generation):
        with self._progress_lock:
            value = self._progress_value
            self._progress_queued = False
        if generation == self._generation and self._alive():
            self.progress.set(value)
            if self.on_progress is not None:
                self.on_progress(value)

    def _finish(self):
        self.running = False
        self._disposed = False
        self.busy.set(False)
        if self._alive() and self.on_done is not None:
            self.on_done()

    def _success(self, result):
        try:
            if self._alive() and self.on_result is not None:
                self.on_result(result)
        finally:
            self._finish()

    def _failure(self, error):
        try:
            if self._alive():
                if self.on_error is not None:
                    self.on_error(error)
                else:
                    self.app._report_error(error)
        finally:
            self._finish()

    def _cancelled(self, future):
        if future.cancelled():
            self.app.call_soon(self._finish)

    def dispose(self):
        """Cancel and release the application registration when the owner dies."""
        self.cancel()
        self._disposed = True
        if self.cancel in self.app._cleanups:
            self.app._cleanups.remove(self.cancel)

    def cancel(self):
        """Request running cancellation, cancel queued work and pending debounce."""
        self.app._check_thread()
        self._cancel_event.set()
        if self._timer is not None:
            self.app.root.after_cancel(self._timer)
            self._timer = None
        return self.future.cancel() if self.future is not None else False
