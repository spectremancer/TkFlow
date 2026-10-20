"""Named views with lifecycle-aware navigation and back history."""
from .container import Container
from .column import Column


class ScreenStack(Container):
    def __init__(self, parent, **options):
        super().__init__(parent, **options)
        self.screens, self.history = {}, []
        self.current = None

    def _place(self, child, **options):
        child._slot, child._weight = len(self._children), 1
        self._children.append(child)
        child.widget.grid(row=0, column=0, sticky="nsew")
        self.widget.rowconfigure(0, weight=1)
        self.widget.columnconfigure(0, weight=1)
        child.widget.grid_remove()

    def _set_weight(self, child, weight):
        pass

    def add(self, name, factory=Column, **options):
        self._check()
        if name in self.screens:
            raise ValueError(f"Screen {name!r} already exists")
        screen = factory(self, **options)
        self.screens[name] = screen
        if self.current is None:
            self.show_screen(name)
        return screen

    def show_screen(self, name, *, remember=True):
        self._check()
        screen = self.screens[name]
        if name == self.current:
            return screen
        if self.current is not None:
            previous = self.screens[self.current]
            if hasattr(previous, "on_hide"):
                previous.on_hide()
            previous.widget.grid_remove()
            if remember:
                self.history.append(self.current)
        self.current = name
        screen.widget.grid()
        screen.widget.tkraise()
        if hasattr(screen, "on_show"):
            screen.on_show()
        return screen

    def back(self):
        self._check()
        if self.history:
            return self.show_screen(self.history.pop(), remember=False)

    def remove(self, name):
        self._check()
        screen = self.screens.pop(name)
        if name == self.current:
            if hasattr(screen, "on_hide"):
                screen.on_hide()
            self.current = None
        self.history = [item for item in self.history if item != name]
        screen.destroy()
        if self.current is None and self.screens:
            self.show_screen(next(iter(self.screens)), remember=False)
