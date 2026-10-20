"""Named string choices presented as radio buttons."""
import tkinter as tk
from tkinter import ttk
from ._value_widget import _ValueWidget
from ._helpers import _layout_options


class RadioGroup(_ValueWidget):
    def __init__(self, parent, values, value=None, *, horizontal=False, on_change=None, bind=None, **options):
        parent.app._check_thread()
        self.values = tuple(values)
        if not self.values or isinstance(values, str) or len(set(self.values)) != len(self.values):
            raise ValueError("Provide distinct radio choices")
        if not all(isinstance(choice, str) for choice in self.values):
            raise TypeError("Radio choices must be strings")
        value = self.values[0] if value is None else value
        if value not in self.values:
            raise ValueError("Unknown radio choice")
        layout = _layout_options(options)
        frame = ttk.Frame(parent.widget, **options)
        self.variable = tk.StringVar(master=frame, value=value)
        self.buttons = []
        for index, text in enumerate(self.values):
            button = ttk.Radiobutton(frame, text=text, value=text, variable=self.variable,
                                     command=lambda: on_change(self.get()) if on_change else None)
            button.grid(row=0 if horizontal else index, column=index if horizontal else 0,
                        sticky="w", padx=(0, 12), pady=3)
            self.buttons.append(button)
        self._attach(parent, frame, **layout)
        if bind is not None:
            self.bind_state(bind)

    def set(self, value):
        if value not in self.values:
            raise ValueError("Unknown radio choice")
        return super().set(value)

    def enable(self):
        self._check()
        for button in self.buttons:
            button.state(["!disabled"])
        return self

    def disable(self):
        self._check()
        for button in self.buttons:
            button.state(["disabled"])
        return self
