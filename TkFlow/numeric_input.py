"""A numeric spinbox with explicit conversion and range validation."""
import math
import tkinter as tk
from tkinter import ttk
from ._value_widget import _ValueWidget
from ._helpers import _layout_options


class NumericInput(_ValueWidget):
    def __init__(self, parent, value=None, *, minimum=0, maximum=100, step=1, integer=False,
                 on_change=None, bind=None, **options):
        parent.app._check_thread()
        if minimum > maximum or step <= 0:
            raise ValueError("Invalid numeric range or step")
        self.minimum, self.maximum, self.integer = minimum, maximum, integer
        layout = _layout_options(options)
        self.variable = tk.StringVar(master=parent.widget)
        self._attach(parent, ttk.Spinbox(parent.widget, from_=minimum, to=maximum,
                                        increment=step, textvariable=self.variable, **options), **layout)
        self.set(bind.get() if bind is not None else minimum if value is None else value)
        if on_change is not None:
            def changed(*_):
                try:
                    value = self.get()
                except ValueError:
                    return
                on_change(value)
            self._trace_id = self.variable.trace_add("write", changed)
        if bind is not None:
            self.bind_state(bind)

    def get(self):
        self._check()
        try:
            value = float(self.variable.get())
        except ValueError:
            raise ValueError(f"Enter a number from {self.minimum} to {self.maximum}") from None
        if not math.isfinite(value) or not self.minimum <= value <= self.maximum:
            raise ValueError(f"Enter a number from {self.minimum} to {self.maximum}")
        if self.integer and not value.is_integer():
            raise ValueError("Enter a whole number")
        return int(value) if self.integer else value

    def set(self, value):
        self._check()
        previous = self.variable.get()
        self.variable.set(str(value))
        try:
            self.get()
        except (ValueError, TypeError):
            self.variable.set(previous)
            raise
        return self
