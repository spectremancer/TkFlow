"""Nonmodal inline notifications with automatic timer cleanup."""
from .row import Row
from .label import Label
from .button import Button


class Notification(Row):
    def __init__(self, parent, text, *, kind="info", duration=4000):
        if kind not in ("info", "success", "warning", "error"):
            raise ValueError("Unknown notification kind")
        if duration < 0:
            raise ValueError("duration must be nonnegative")
        super().__init__(parent, padding=8)
        Label(self, f"{kind.upper()}  {text}", expand=True, wraplength=600,
              style="Error.TLabel" if kind == "error" else "TLabel")
        Button(self, "Dismiss", self.destroy)
        if duration:
            self.after(duration, self.destroy)
