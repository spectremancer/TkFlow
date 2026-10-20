"""Reusable interface components with explicit show/hide lifecycle hooks."""
from .column import Column


class Component(Column):
    """Subclass build() to assemble a reusable view; register resources on_dispose."""
    def __init__(self, parent, **options):
        super().__init__(parent, **options)
        self.build()

    def build(self):
        pass

    def on_show(self):
        pass

    def on_hide(self):
        pass
