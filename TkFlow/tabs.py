"""Notebook pages with automatic container cleanup."""
from tkinter import ttk
from .widget import Widget
from ._helpers import _layout_options


class Tabs(Widget):
    def __init__(self, parent, **options):
        parent.app._check_thread()
        layout = _layout_options(options)
        self._children = []
        self.pages = {}
        self.orientation = "vertical"
        self._attach(parent, ttk.Notebook(parent.widget, **options), **layout)

    def _place(self, child, **options):
        child._slot, child._weight = len(self._children), 1
        self._children.append(child)
        self.widget.add(child.widget)

    def _set_weight(self, child, weight):
        pass

    def _hide_child(self, child):
        self.widget.hide(child.widget)

    def _show_child(self, child):
        self.widget.add(child.widget)

    def add(self, name, *, title=None, **options):
        from .column import Column
        self._check()
        if name in self.pages:
            raise ValueError(f"Page {name!r} already exists")
        page = Column(self, **options)
        self.widget.tab(page.widget, text=title or name)
        self.pages[name] = page
        return page

    def select(self, name):
        self._check()
        self.widget.select(self.pages[name].widget)
        return self.pages[name]

    def remove(self, name):
        self._check()
        self.pages.pop(name).destroy()

    def _dispose(self):
        for child in list(self._children):
            child._dispose()
        super()._dispose()
