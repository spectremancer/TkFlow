"""TkFlow widget classes and helpers."""
from __future__ import annotations

from typing import Any, TYPE_CHECKING
import tkinter as tk
from ._helpers import Callback

if TYPE_CHECKING:
    from . import App, Window, Container, Widget, Section, Row, Column


class Widget:
    """Common wrapper operations; the native Tk widget is available as .widget."""

    def _attach(self, parent: App | Window | Container, widget: tk.Widget,
                *, expand: bool = False, fill: str = "x", padx: int = 0,
                pady: int = 0) -> None:
        self.app = parent.app
        self.parent = parent
        self.widget = widget
        self._destroyed = False
        self._cleanups = []
        self._timers = set()
        parent._place(self, expand=expand, fill=fill, padx=padx, pady=pady)

    def _layout_weight(self, weight: int) -> None:
        if hasattr(self.parent, "_set_weight"):
            self.parent._set_weight(self, weight)
            return
        if self.parent.orientation == "horizontal":
            self.parent.widget.columnconfigure(self._slot, weight=weight)
        else:
            self.parent.widget.rowconfigure(self._slot, weight=weight)

    def _check(self) -> None:
        self.app._check_thread()
        if self._destroyed:
            raise RuntimeError("This widget has been destroyed")

    def configure(self, **options: Any) -> Widget:
        """Forward native widget options, e.g. style, width, or padding."""
        self._check()
        self.widget.configure(**options)
        return self

    def enable(self) -> Widget:
        self._check()
        self.widget.state(["!disabled"])
        return self

    def disable(self) -> Widget:
        self._check()
        self.widget.state(["disabled"])
        return self

    def hide(self) -> Widget:
        self._check()
        if hasattr(self.parent, "_hide_child"):
            self.parent._hide_child(self)
        else:
            self.widget.grid_remove()
        self._layout_weight(0)
        return self

    def show(self) -> Widget:
        self._check()
        if hasattr(self.parent, "_show_child"):
            self.parent._show_child(self)
        else:
            self.widget.grid()
        self._layout_weight(self._weight)
        return self

    def destroy(self) -> None:
        self._check()
        self._dispose()
        self._layout_weight(0)
        self.widget.destroy()
        self.parent._children.remove(self)

    def on_dispose(self, callback):
        """Register cleanup; return the callback for convenience."""
        self._check()
        self._cleanups.append(callback)
        return callback

    def safe(self, callback):
        """Guard a result callback against use after this widget is destroyed."""
        def guarded(*args, **kwargs):
            self.app._check_thread()
            if not self._destroyed and not self.app._closed:
                return callback(*args, **kwargs)
        return guarded

    def after(self, milliseconds, callback, *args):
        self._check()
        def run():
            self._timers.discard(timer)
            self.safe(callback)(*args)
        timer = self.app.after(milliseconds, run)
        self._timers.add(timer)
        return timer

    def bind_state(self, state, *, two_way=True):
        """Bind get/set values, or Label text, with automatic unsubscription."""
        self._check()
        updating = False
        def render(value):
            nonlocal updating
            if self._destroyed:
                return
            updating = True
            try:
                self.set(value)
            finally:
                updating = False
        self.on_dispose(state.subscribe(render))
        if two_way and hasattr(self, "variable"):
            def changed(*_):
                if not updating:
                    try:
                        state.set(self.get())
                    except (ValueError, tk.TclError):
                        pass
            trace = self.variable.trace_add("write", changed)
            self.on_dispose(lambda: self.variable.trace_remove("write", trace))
        elif two_way and hasattr(self, "text"):
            def edited(event):
                if self.text.edit_modified():
                    self.text.edit_modified(False)
                    if not updating:
                        state.set(self.get())
            binding = self.text.bind("<<Modified>>", edited, add="+")
            self.on_dispose(lambda: self.text.unbind("<<Modified>>", binding))
        return self

    def bind_enabled(self, state):
        self.on_dispose(state.subscribe(lambda enabled: self.enable() if enabled else self.disable()))
        return self

    def _focus_target(self):
        if hasattr(self, "text"):
            return self.text
        if hasattr(self, "tree"):
            return self.tree
        if hasattr(self, "entry"):
            return self.entry.widget
        if hasattr(self, "buttons") and self.buttons:
            return self.buttons[0]
        return self.widget

    def focus(self):
        self._check()
        self._focus_target().focus_set()
        return self

    def _dispose(self) -> None:
        if self._destroyed:
            return
        self._destroyed = True
        for timer in self._timers:
            self.app.root.after_cancel(timer)
        self._timers.clear()
        cleanups, self._cleanups = self._cleanups, []
        for cleanup in reversed(cleanups):
            try:
                cleanup()
            except Exception as error:
                self.app._report_error(error)
        self._cleanups.clear()

    def bind(self, event: str, command: Callback, *, add: bool = True) -> str:
        """Bind a Tk event; command receives the native event object."""
        self._check()
        return self.widget.bind(event, command, add="+" if add else "")
