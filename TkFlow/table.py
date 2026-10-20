"""A data-backed table with stable IDs, sorting, filtering, and selection."""
from tkinter import ttk
from .widget import Widget
from ._helpers import _layout_options


class Table(Widget):
    def __init__(self, parent, columns, rows=(), *, key=None, on_select=None, **options):
        parent.app._check_thread()
        self.columns = dict(columns) if isinstance(columns, dict) else {name: name for name in columns}
        if not self.columns:
            raise ValueError("At least one column is required")
        self.key, self.on_select = key, on_select
        self._rows, self._predicate = {}, None
        self._sort, self._reverse, self._sort_key = None, False, None
        layout = _layout_options(options)
        frame = ttk.Frame(parent.widget)
        self.tree = ttk.Treeview(frame, columns=tuple(self.columns), show="headings", **options)
        vertical = ttk.Scrollbar(frame, command=self.tree.yview)
        horizontal = ttk.Scrollbar(frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal.grid(row=1, column=0, sticky="ew")
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)
        for column, caption in self.columns.items():
            self.tree.heading(column, text=caption, command=lambda c=column: self.sort(c, reverse=not self._reverse if self._sort == c else False))
            self.tree.column(column, width=140, minwidth=60)
        self._attach(parent, frame, **layout)
        self.tree.bind("<<TreeviewSelect>>", lambda event: self.on_select(self.selected()) if self.on_select and not self._destroyed else None)
        self.set_rows(rows)

    def set_rows(self, rows):
        self._check()
        replacement = {}
        for index, row in enumerate(rows):
            row = dict(row)
            identity = str(row[self.key]) if self.key is not None else str(index)
            if not identity or identity in replacement:
                raise ValueError("Table row IDs must be distinct and nonempty")
            replacement[identity] = row
        self._rows = replacement
        self._render()
        return self

    def _render(self):
        selected = set(self.tree.selection())
        entries = [(identity, row) for identity, row in self._rows.items()
                   if self._predicate is None or self._predicate(dict(row))]
        if self._sort is not None:
            def sort_value(item):
                value = item[1].get(self._sort)
                if self._sort_key:
                    return self._sort_key(value)
                if value is None:
                    return (0, "")
                return (1, value) if isinstance(value, (int, float)) else (2, str(value).casefold())
            entries.sort(key=sort_value, reverse=self._reverse)
        children = self.tree.get_children()
        if children:
            self.tree.delete(*children)
        for identity, row in entries:
            self.tree.insert("", "end", iid=identity, values=[row.get(column, "") for column in self.columns])
        self.tree.selection_set([identity for identity, row in entries if identity in selected])

    def rows(self):
        self._check()
        return [dict(self._rows[identity]) for identity in self.tree.get_children()]

    def selected(self):
        self._check()
        return [dict(self._rows[identity]) for identity in self.tree.selection() if identity in self._rows]

    def select(self, *identities):
        self._check()
        self.tree.selection_set([str(identity) for identity in identities])
        return self

    def sort(self, column, *, reverse=False, key=None):
        self._check()
        if column not in self.columns:
            raise KeyError(column)
        self._sort, self._reverse, self._sort_key = column, reverse, key
        self._render()
        return self

    def filter(self, predicate=None):
        self._check()
        if isinstance(predicate, str):
            query = predicate.casefold()
            predicate = lambda row: any(query in str(value).casefold() for value in row.values())
        if predicate is not None and not callable(predicate):
            raise TypeError("filter expects text, a predicate, or None")
        self._predicate = predicate
        self._render()
        return self

    def update_row(self, identity, **values):
        self._check()
        identity = str(identity)
        if self.key in values and str(values[self.key]) != identity:
            raise ValueError("Row identity cannot change during update")
        self._rows[identity].update(values)
        self._render()
        return self

    def enable(self):
        self._check()
        self.tree.state(["!disabled"])
        return self

    def disable(self):
        self._check()
        self.tree.state(["disabled"])
        return self
