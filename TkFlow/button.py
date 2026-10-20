"""TkFlow button classes and helpers."""
from __future__ import annotations

from typing import Any, TYPE_CHECKING
from tkinter import ttk
from .label import Label
from ._helpers import Callback, _command, _layout_options

if TYPE_CHECKING:
    from . import App, Window, Container, Widget, Section, Row, Column


class Button(Label):
    """A button; command takes no arguments. background=True runs it in a thread."""

    def __init__(self, parent: App | Window | Container, text: str = "",
                 command: Callback | None = None, *, background: bool = False,
                 on_result: Callback | None = None, on_error: Callback | None = None,
                 busy_text: str | None = None, disable_while_running: bool = True,
                 **options: Any) -> None:
        parent.app._check_thread()
        self._invoke = _command(parent.app, command, background, on_result, on_error)
        self.command = command
        state_binding = options.pop("bind", None)
        layout = _layout_options(options)
        self._attach(parent, ttk.Button(parent.widget, text=text, command=self._invoke, **options), **layout)

        if state_binding is not None:
            self.bind_state(state_binding)
        from .command import Command
        if isinstance(command, Command):
            saved_text, saved_disabled = text, False
            def busy_changed(busy):
                nonlocal saved_text, saved_disabled
                if busy:
                    saved_text = self.get()
                    saved_disabled = self.widget.instate(["disabled"])
                    if busy_text is not None:
                        self.set(busy_text)
                    if disable_while_running:
                        self.disable()
                else:
                    if busy_text is not None:
                        self.set(saved_text)
                    if disable_while_running and not saved_disabled:
                        self.enable()
            self.on_dispose(command.busy.subscribe(busy_changed, immediate=False))

    def invoke(self) -> Any:
        """Invoke unless disabled, returning the result or background Future."""
        self._check()
        if not self.widget.instate(["disabled"]):
            return self._invoke()
        return None
