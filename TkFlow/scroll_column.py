"""A scrollable container with a separately exposed content column."""
import tkinter as tk
from tkinter import ttk
from .container import Container
from .column import Column


class ScrollColumn(Container):
    def __init__(self, parent, *, height=240, **options):
        super().__init__(parent, **options)
        self.canvas = tk.Canvas(self.widget, height=height, width=280, highlightthickness=0,
                                background=self.app.root.cget("background"))
        self.content = Column(self, padding=0, expand=True, fill="both", _master=self.canvas)
        scrollbar = ttk.Scrollbar(self.widget, command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=scrollbar.set)
        self.content.widget.grid_forget()
        self._item = self.canvas.create_window(0, 0, window=self.content.widget, anchor="nw")
        self.canvas.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.content.widget.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(self._item, width=e.width))
        self.canvas.bind("<MouseWheel>", lambda e: self.canvas.yview_scroll(-1 if e.delta > 0 else 1, "units"))
        self.canvas.bind("<Button-4>", lambda e: self.canvas.yview_scroll(-1, "units"))
        self.canvas.bind("<Button-5>", lambda e: self.canvas.yview_scroll(1, "units"))
