"""Determinate or indeterminate progress with shared-state binding."""
import tkinter as tk
from tkinter import ttk
from ._value_widget import _ValueWidget
from ._helpers import _layout_options, _positive


class ProgressBar(_ValueWidget):
    def __init__(self, parent, value=0, *, maximum=100, mode="determinate", bind=None, **options):
        parent.app._check_thread()
        if maximum <= 0:
            raise ValueError("maximum must be positive")
        if mode not in ("determinate", "indeterminate"):
            raise ValueError("Invalid progress mode")
        layout = _layout_options(options)
        self.variable = tk.DoubleVar(master=parent.widget, value=value)
        self._attach(parent, ttk.Progressbar(parent.widget, maximum=maximum, mode=mode,
                                             variable=self.variable, **options), **layout)
        self.on_dispose(self.widget.stop)
        if bind is not None:
            self.bind_state(bind)

    def start(self, interval=50):
        self._check()
        self.widget.start(_positive(interval, "interval"))
        return self

    def stop(self):
        self._check()
        self.widget.stop()
        return self
