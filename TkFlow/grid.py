"""Responsive grid layout with automatic cells and explicit spans."""
from .container import Container
from ._helpers import _positive


class Grid(Container):
    def __init__(self, parent, *, columns=2, **options):
        self.columns = _positive(columns, "columns")
        self._cells, self._pending = {}, None
        super().__init__(parent, **options)

    def _place(self, child, *, expand, fill, padx, pady):
        if fill not in ("none", "x", "y", "both"):
            child.widget.destroy()
            raise ValueError("Invalid fill")
        if self._pending is None:
            row, column = divmod(self._next_slot, self.columns)
            while (row, column) in self._cells:
                self._next_slot += 1
                row, column = divmod(self._next_slot, self.columns)
            rowspan = colspan = 1
            self._next_slot += 1
        else:
            row, column, rowspan, colspan = self._pending
        child._slot, child._weight = len(self._children), int(expand)
        child._gridrow, child._gridcolumn = row, column
        self._children.append(child)
        self._cells.update({(r, c): child for r in range(row, row + rowspan) for c in range(column, column + colspan)})
        child.widget.grid(row=row, column=column, rowspan=rowspan, columnspan=colspan,
                          sticky={"none":"w", "x":"ew", "y":"ns", "both":"nsew"}[fill],
                          padx=padx + self.spacing // 2, pady=pady + self.spacing // 2)
        for col in range(column, column + colspan):
            self.widget.columnconfigure(col, weight=1, uniform="columns")
        self.widget.rowconfigure(row, weight=int(expand))
        def release():
            self._cells = {position: item for position, item in self._cells.items() if item is not child}
        # _place runs during Widget._attach, after cleanup storage exists.
        child.on_dispose(release)

    def _set_weight(self, child, weight):
        others = [item._weight for item in self._children if item is not child and
                  item._gridrow == child._gridrow and not item._destroyed and item.widget.winfo_manager() == "grid"]
        self.widget.rowconfigure(child._gridrow, weight=max([weight, *others]))

    def cell(self, row, column, *, rowspan=1, colspan=1, **options):
        from .column import Column
        if any(isinstance(n, bool) or not isinstance(n, int) for n in (row, column, rowspan, colspan)):
            raise ValueError("Grid coordinates and spans must be integers")
        if min(row, column) < 0 or min(rowspan, colspan) < 1:
            raise ValueError("Grid indices must be nonnegative and spans positive")
        occupied = {(r, c) for r in range(row, row + rowspan) for c in range(column, column + colspan)}
        if occupied & self._cells.keys():
            raise ValueError("Grid cell overlaps another cell")
        self._pending = row, column, rowspan, colspan
        try:
            return Column(self, **options)
        finally:
            self._pending = None
