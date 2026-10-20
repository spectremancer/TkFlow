"""A disclosure header with a nested content column."""
from .container import Container
from .column import Column
from .button import Button
from .state import State


class Collapsible(Container):
    def __init__(self, parent, title="Details", *, collapsed=False, **options):
        super().__init__(parent, **options)
        self.title = title
        self.collapsed = State(collapsed)
        self.header = Button(self, title, lambda: self.collapsed.update(lambda value: not value))
        self.content = Column(self, padding=0)
        def render(value):
            self.header.set(("> " if value else "v ") + self.title)
            self.content.hide() if value else self.content.show()
        self.on_dispose(self.collapsed.subscribe(render))
