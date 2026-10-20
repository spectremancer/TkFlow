"""Resizable horizontal/vertical split panes."""
from tkinter import ttk
from .tabs import Tabs
from .widget import Widget
from ._helpers import _layout_options


class SplitPane(Tabs):
    def __init__(self, parent, *, orientation="horizontal", **options):
        if orientation not in ("horizontal", "vertical"):
            raise ValueError("orientation must be horizontal or vertical")
        parent.app._check_thread()
        layout = _layout_options(options)
        self._children, self.pages = [], {}
        self.orientation = orientation
        self._attach(parent, ttk.Panedwindow(parent.widget, orient=orientation, **options), **layout)

    def _place(self, child, **options):
        child._slot, child._weight = len(self._children), 1
        self._children.append(child)
        self.widget.add(child.widget, weight=1)

    def add(self, name, *, weight=1, **options):
        from .column import Column
        self._check()
        if name in self.pages:
            raise ValueError(f"Pane {name!r} already exists")
        page = Column(self, **options)
        self.widget.pane(page.widget, weight=weight)
        self.pages[name] = page
        return page

    def _hide_child(self, child):
        self.widget.forget(child.widget)

    def _show_child(self, child):
        self.widget.add(child.widget, weight=1)

    def select(self, name):
        raise TypeError("Split panes are all visible; use Tabs or ScreenStack for selection")
