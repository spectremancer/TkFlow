"""Entry plus a parented native file/folder chooser."""
from tkinter import filedialog
from .row import Row
from .text_input import TextInput
from .button import Button


class FilePicker(Row):
    def __init__(self, parent, value="", *, mode="open", title="Choose a path", filetypes=None,
                 on_change=None, bind=None, **options):
        if mode not in ("open", "save", "directory"):
            raise ValueError("mode must be open, save, or directory")
        super().__init__(parent, **options)
        self.mode, self.title, self.filetypes = mode, title, filetypes
        self.entry = TextInput(self, value, expand=True, on_change=on_change, bind=bind)
        self.button = Button(self, "Browse...", self.browse)
        self.variable = self.entry.variable

    def browse(self):
        self._check()
        arguments = {"parent": self.app.root, "title": self.title}
        if self.mode != "directory" and self.filetypes is not None:
            arguments["filetypes"] = self.filetypes
        function = {"open": filedialog.askopenfilename, "save": filedialog.asksaveasfilename,
                    "directory": filedialog.askdirectory}[self.mode]
        value = function(**arguments)
        if value:
            self.set(value)
        return value

    def get(self):
        return self.entry.get()

    def set(self, value):
        self.entry.set(value)
        return self

    def enable(self):
        self.entry.enable()
        self.button.enable()
        return self

    def disable(self):
        self.entry.disable()
        self.button.disable()
        return self
