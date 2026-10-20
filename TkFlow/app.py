"""TkFlow app classes and helpers."""
from __future__ import annotations

from typing import Any, TYPE_CHECKING
from concurrent.futures import Future
import queue
import threading
import tkinter as tk
import time
from ._workers import WorkerPool
from . import _resources
from tkinter import messagebox, ttk
from ._layout import _Layout
from ._helpers import Callback, _callback, _positive

if TYPE_CHECKING:
    from . import App, Window, Container, Widget, Section, Row, Column
    from .command import Command


class _Window(_Layout):
    def _setup_window(self, title: str, height: int, width: int,
                      min_height: int, min_width: int,
                      resizable: bool | tuple[bool, bool], padding: Any,
                      spacing: int) -> None:
        self._init_layout("vertical", spacing)
        self._closed = False
        self._cleanups = []
        self.set_title(title)
        self.set_size(height=height, width=width)
        self.set_min_size(height=min_height, width=min_width)
        self.set_resizable(resizable)
        self.widget = ttk.Frame(self.root, padding=padding)
        self.widget.pack(fill="both", expand=True)
        self.root.protocol("WM_DELETE_WINDOW", self.close)

    def on_dispose(self, callback):
        self.app._check_thread()
        self._cleanups.append(callback)
        return callback

    def _run_cleanups(self):
        callbacks, self._cleanups = self._cleanups, []
        for callback in reversed(callbacks):
            try:
                callback()
            except Exception as error:
                self.app._report_error(error)
        self._cleanups.clear()

    def safe(self, callback):
        def guarded(*args, **kwargs):
            self.app._check_thread()
            if not self._closed and not self.app._closed:
                return callback(*args, **kwargs)
        return guarded

    def _button_key(self, sequence, button):
        active = True
        def trigger(event):
            if not button._destroyed and not (sequence == "<Return>" and isinstance(event.widget, tk.Text)):
                button.invoke()
                return "break"
        binding = self.root.bind(sequence, trigger, add="+")
        def remove():
            nonlocal active
            if active:
                self.root.unbind(sequence, binding)
                active = False
        self.on_dispose(remove)
        button.on_dispose(remove)
        return remove

    def set_default_button(self, button):
        """Activate a button with Enter, leaving multiline Text editing intact."""
        self.app._check_thread()
        return self._button_key("<Return>", button)

    def set_cancel_button(self, button):
        self.app._check_thread()
        return self._button_key("<Escape>", button)

    def focus_order(self, *controls):
        """Install explicit Tab/Shift-Tab order, skipping hidden/disabled controls."""
        self.app._check_thread()
        bindings = []
        def move(index, direction):
            for offset in range(1, len(controls) + 1):
                candidate = controls[(index + direction * offset) % len(controls)]
                target = candidate._focus_target()
                if not candidate._destroyed and target.winfo_viewable() and not (
                        hasattr(target, "instate") and target.instate(["disabled"])):
                    candidate.focus()
                    break
            return "break"
        for index, control in enumerate(controls):
            target = control._focus_target()
            for sequence, direction in (("<Tab>", 1), ("<Shift-Tab>", -1), ("<ISO_Left_Tab>", -1)):
                binding = target.bind(sequence, lambda event, i=index, d=direction: move(i, d), add="+")
                bindings.append((target, sequence, binding))
        active = True
        def remove():
            nonlocal active
            if active:
                for target, sequence, binding in bindings:
                    if target.winfo_exists():
                        target.unbind(sequence, binding)
                bindings.clear()
                if remove in self._cleanups:
                    self._cleanups.remove(remove)
                active = False
        self.on_dispose(remove)
        for control in controls:
            control.on_dispose(remove)
        return remove

    def set_title(self, title: str) -> _Window:
        self.app._check_thread()
        self.root.title(title)
        return self

    def set_size(self, height: int, width: int) -> _Window:
        """Set dimensions in pixels (height, width); Tk geometry is width x height."""
        self.app._check_thread()
        self.root.geometry(f"{_positive(width, 'width')}x{_positive(height, 'height')}")
        return self

    def set_min_size(self, height: int, width: int) -> _Window:
        self.app._check_thread()
        self.root.minsize(_positive(width, "min_width"), _positive(height, "min_height"))
        return self

    def set_resizable(self, value: bool | tuple[bool, bool]) -> _Window:
        """A bool or a (horizontal, vertical) bool pair."""
        self.app._check_thread()
        if isinstance(value, bool):
            value = (value, value)
        if not isinstance(value, tuple) or len(value) != 2 or not all(isinstance(v, bool) for v in value):
            raise ValueError("resizable must be a bool or a (horizontal, vertical) bool pair")
        self.root.resizable(*value)
        return self

    def message(self, text: str, *, title: str = "Message", kind: str = "info") -> str:
        self.app._check_thread()
        functions = {"info": messagebox.showinfo, "warning": messagebox.showwarning,
                     "error": messagebox.showerror}
        if kind not in functions:
            raise ValueError("kind must be 'info', 'warning', or 'error'")
        return functions[kind](title, text, parent=self.root)

    def confirm(self, text: str, *, title: str = "Confirm") -> bool:
        self.app._check_thread()
        return messagebox.askyesno(title, text, parent=self.root)

    def close(self) -> None:
        self.app._check_thread()
        if not self._closed:
            self._closed = True
            self._run_cleanups()
            for child in self._children:
                child._dispose()
            self.root.destroy()
            if self in self.app._windows:
                self.app._windows.remove(self)


class App(_Window):
    """Own the root window and event loop. Construct and run on the main thread."""

    def __init__(self, title: str = "TkFlow", height: int = 480, width: int = 640,
                 *, min_height: int = 100, min_width: int = 100,
                 resizable: bool | tuple[bool, bool] = True, padding: Any = 12,
                 spacing: int = 8, theme: str | None = None,
                 max_workers: int = 4, max_pending: int = 64) -> None:
        if threading.current_thread() is not threading.main_thread():
            raise RuntimeError("Create App on the main thread")
        for name, value in (("height", height), ("width", width),
                            ("min_height", min_height), ("min_width", min_width)):
            _positive(value, name)
        _positive(max_workers, "max_workers")
        _positive(max_pending, "max_pending")
        self._workers = WorkerPool(max_workers, max_pending)
        self.stop_event = threading.Event()
        self.app = self
        self._thread_id = threading.get_ident()
        self._queue: queue.Queue[tuple[Callback, tuple[Any, ...]]] = queue.Queue()
        self._delivery_lock = threading.Lock()
        self._closed = False
        self._windows: list[Window] = []
        _resources.drain()
        self.root = tk.Tk()
        _resources.retain(self)
        try:
            self.style = ttk.Style(self.root)
            if theme is not None:
                if theme not in self.style.theme_names():
                    raise ValueError(f"Unknown theme {theme!r}; choose from {self.style.theme_names()}")
                self.style.theme_use(theme)
            self._setup_window(title, height, width, min_height, min_width,
                               resizable, padding, spacing)
            self._poll_id = self.root.after(10, self._drain)
        except Exception:
            self.root.destroy()
            raise

    def _check_thread(self) -> None:
        if threading.get_ident() != self._thread_id:
            raise RuntimeError("GUI operations must run on the main thread; use app.call_soon() or on_result")

    def call_soon(self, command: Callback, *args: Any) -> None:
        """Thread-safe: queue command(*args) for the GUI thread; ignore after close."""
        _callback(command, "command")
        if command is None:
            raise TypeError("command must be callable")
        with self._delivery_lock:
            if not self._closed:
                self._queue.put((command, args))

    def _drain(self) -> None:
        _resources.drain()
        # A bounded batch prevents a busy producer from starving the Tk event loop.
        deadline = time.monotonic() + 0.005
        for _ in range(100):
            if time.monotonic() >= deadline:
                break
            if self._closed:
                return
            try:
                command, args = self._queue.get_nowait()
            except queue.Empty:
                break
            try:
                command(*args)
            except Exception as error:
                self.root.report_callback_exception(type(error), error, error.__traceback__)
        if not self._closed:
            self._poll_id = self.root.after(10, self._drain)

    def _report_error(self, error: Exception) -> None:
        self.root.report_callback_exception(type(error), error, error.__traceback__)

    def run_in_thread(self, command: Callback, *args: Any,
                      on_result: Callback | None = None,
                      on_error: Callback | None = None, **kwargs: Any) -> Future:
        """Run work in the bounded daemon pool; completion callbacks run on the GUI thread.

        Workers must not access Tk. The Future represents the worker's result,
        not completion of the queued GUI callbacks. Running work cannot be killed.
        """
        _callback(command, "command")
        if command is None:
            raise TypeError("command must be callable")
        _callback(on_result, "on_result")
        _callback(on_error, "on_error")
        with self._delivery_lock:
            if self._closed:
                raise RuntimeError("Cannot start work after the app has closed")
        future = self._workers.submit(command, *args, **kwargs)

        def completed(result: Future) -> None:
            if result.cancelled():
                return
            error = result.exception()
            if error is not None:
                self.call_soon(on_error or self._report_error, error)
            elif on_result is not None:
                self.call_soon(on_result, result.result())

        future.add_done_callback(completed)
        return future

    def command(self, function: Callback, **options: Any) -> Command:
        """Create a reusable Command (background by default)."""
        from .command import Command
        return Command(self, function, **options)

    def shortcut(self, sequence, command, *, owner=None):
        """Install a keyboard shortcut; return an explicit unsubscriber."""
        self._check_thread()
        active = True
        def trigger(event):
            if active and (owner is None or not getattr(owner, "_destroyed", False)
                           and not getattr(owner, "_closed", False)):
                command()
                return "break"
        binding = self.root.bind(sequence, trigger, add="+")
        def remove():
            nonlocal active
            if active:
                self.root.unbind(sequence, binding)
                active = False
        (owner or self).on_dispose(remove)
        return remove

    def notify(self, text, *, kind="info", duration=4000):
        from .notification import Notification
        return Notification(self, text, kind=kind, duration=duration)

    def after(self, milliseconds: int, command: Callback, *args: Any) -> str:
        """Schedule on the GUI thread; returns an ID for root.after_cancel()."""
        self._check_thread()
        return self.root.after(milliseconds, command, *args)

    def run(self) -> None:
        self._check_thread()
        self.root.mainloop()

    def close(self) -> None:
        self._check_thread()
        if self._closed:
            return
        with self._delivery_lock:
            self._closed = True
        self._run_cleanups()
        self.stop_event.set()
        self._workers.shutdown()
        self.root.after_cancel(self._poll_id)
        for window in self._windows:
            if not window._closed:
                window._run_cleanups()
                for child in window._children:
                    child._dispose()
                window._closed = True
        for child in self._children:
            child._dispose()
        self.root.destroy()
        while not self._queue.empty():
            self._queue.get_nowait()
