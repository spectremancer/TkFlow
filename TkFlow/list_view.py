"""Simple string-list selection using the same table model."""
from .table import Table


class ListView(Table):
    def __init__(self, parent, items=(), *, on_select=None, **options):
        callback = (lambda rows: on_select([row["value"] for row in rows])) if on_select else None
        super().__init__(parent, {"value": "Items"}, on_select=callback, **options)
        self.set_items(items)

    def set_items(self, items):
        return self.set_rows({"value": str(value)} for value in items)

    def get(self):
        return [row["value"] for row in self.selected()]
