"""ISO date entry with typed date access and explicit validation."""
from datetime import date
from .text_input import TextInput


class DateInput(TextInput):
    """Enter YYYY-MM-DD; get() returns datetime.date or raises ValueError."""
    def __init__(self, parent, value=None, **options):
        value = date.today() if value is None else value
        date.fromisoformat(str(value))
        super().__init__(parent, str(value), **options)

    def get(self):
        return date.fromisoformat(super().get())

    def set(self, value):
        return super().set(date.fromisoformat(str(value)).isoformat())
