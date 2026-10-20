"""TkFlow text input classes and helpers."""
from __future__ import annotations

from typing import Any, TYPE_CHECKING
import tkinter as tk
from tkinter import ttk
from ._value_widget import _ValueWidget
from ._helpers import Callback, _command, _layout_options

if TYPE_CHECKING:
    from . import App, Window, Container, Widget, Section, Row, Column


class TextInput(_ValueWidget):
    """Single-line text input; on_change(value) fires on edits and set()."""

    def __init__(self, parent: App | Window | Container, value: str = "", *,
                 on_change: Callback | None = None, background: bool = False,
                 on_result: Callback | None = None, on_error: Callback | None = None,
                 **options: Any) -> None:
        parent.app._check_thread()
        changed = _command(parent.app, on_change, background, on_result, on_error)
        state_binding = options.pop("bind", None)
        layout = _layout_options(options)
        self.variable = tk.StringVar(master=parent.widget, value=value)
        self._attach(parent, ttk.Entry(parent.widget, textvariable=self.variable, **options), **layout)
        def notify(*_):
            try:
                value = self.get()
            except ValueError:
                # Typed subclasses such as DateInput permit incomplete editing.
                return
            changed(value)
        self._trace_id = self.variable.trace_add("write", notify) if on_change else None
        if state_binding is not None:
            self.bind_state(state_binding)
