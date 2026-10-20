"""Custom dialogs with Future results and no nested blocking event loop."""
from concurrent.futures import Future
from .window import Window
from .label import Label
from .text_input import TextInput
from .button import Button


class Dialog(Window):
    def __init__(self, parent, title="Dialog", *, modal=True, **options):
        super().__init__(parent, title, **options)
        self.future = Future()
        self.root.transient(parent.root)
        self.app.on_dispose(self._cancel_result)
        if modal:
            self.root.grab_set()
        self.root.bind("<Escape>", lambda event: self.close())

    def _cancel_result(self):
        if not self.future.done():
            self.future.set_result(None)

    def resolve(self, value):
        if not self.future.done():
            self.future.set_result(value)
        self.close()

    def then(self, callback):
        """Run a result handler on the GUI thread, suppressed after app close."""
        self.future.add_done_callback(lambda future: self.app.call_soon(callback, future.result()) if not future.cancelled() else None)
        return self

    def close(self):
        self.app._check_thread()
        self._cancel_result()
        if not self._closed:
            if self._cancel_result in self.app._cleanups:
                self.app._cleanups.remove(self._cancel_result)
            # Do not release another dialog's grab when closing an older window.
            if self.root.grab_current() == self.root:
                self.root.grab_release()
            super().close()


class InputDialog(Dialog):
    def __init__(self, parent, prompt, *, value="", title="Input", **options):
        options.setdefault("height", 190)
        options.setdefault("width", 440)
        super().__init__(parent, title, **options)
        Label(self, prompt, wraplength=390)
        self.entry = TextInput(self, value)
        actions = self.row(padding=0)
        self.submit = Button(actions, "OK", lambda: self.resolve(self.entry.get()), style="Primary.TButton")
        Button(actions, "Cancel", self.close)
        self.root.bind("<Return>", lambda event: self.submit.invoke())
        self.entry.focus()
