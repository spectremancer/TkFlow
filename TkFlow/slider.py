"""Continuous numeric values bound to a themed scale."""
import math
import tkinter as tk
from tkinter import ttk
from ._value_widget import _ValueWidget
from ._helpers import _layout_options


class Slider(_ValueWidget):
    def __init__(self, parent, value=None, *, minimum=0, maximum=100, on_change=None, bind=None, **options):
        parent.app._check_thread()
        if minimum >= maximum:
            raise ValueError("minimum must be less than maximum")
        self.minimum, self.maximum = minimum, maximum
        layout = _layout_options(options)
        self.variable = tk.DoubleVar(master=parent.widget)
        self._attach(parent, ttk.Scale(parent.widget, from_=minimum, to=maximum, variable=self.variable,
                                      command=lambda v: on_change(float(v)) if on_change else None, **options), **layout)
        self.set(bind.get() if bind is not None else minimum if value is None else value)
        if bind is not None:
            self.bind_state(bind)

    def set(self, value):
        value = float(value)
        if not math.isfinite(value) or not self.minimum <= value <= self.maximum:
            raise ValueError("Value is outside slider range")
        return super().set(value)
