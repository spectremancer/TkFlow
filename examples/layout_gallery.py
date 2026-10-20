"""Tabs, split panes, grids and scrolling composition. Run: python -m examples.layout_gallery."""
from types import SimpleNamespace
from TkFlow import App, Button, Collapsible, Grid, Label, ListView, ScrollColumn, SplitPane, Tabs, Theme


def build_app():
    app = App("TkFlow - layout gallery", height=650, width=960, min_height=450, min_width=700)
    Theme().apply(app)
    Label(app, "Layout gallery", style="Title.TLabel")
    tabs = Tabs(app, expand=True, fill="both")
    grid_page = tabs.add("Grid", padding=8)
    grid = Grid(grid_page, columns=2, expand=True, fill="both")
    wide = grid.cell(0, 0, colspan=2, padding=8)
    Label(wide, "A wide section spans both columns", style="Heading.TLabel")
    Label(wide, "The cells below resize evenly as the window changes.", style="Muted.TLabel")
    for title in ("Project activity", "Team notes", "Upcoming releases", "Quick actions"):
        card = grid.column(expand=True, fill="both", padding=10, spacing=5)
        Label(card, title, style="Heading.TLabel")
        Label(card, "Reusable containers keep each section self-contained.", wraplength=280, justify="left")
        Button(card, "Inspect", lambda title=title: app.notify(title))
    split_page = tabs.add("Split panes")
    panes = SplitPane(split_page, expand=True, fill="both")
    left, right = panes.add("left"), panes.add("right")
    Label(left, "Drag the divider", style="Heading.TLabel")
    selection = Label(right, "Select a topic")
    ListView(left, ["Lifecycle", "State", "Workers", "Navigation"], height=6, expand=True, fill="both",
             on_select=lambda items: selection.set(" / ".join(items)))
    scroll_page = tabs.add("Scrollable content")
    scroll = ScrollColumn(scroll_page, expand=True, fill="both")
    for index in range(12):
        disclosure = Collapsible(scroll.content, f"Section {index + 1}", collapsed=index > 2)
        Label(disclosure.content, "Collapsible sections work inside scrollable containers.", wraplength=500)
    app.demo = SimpleNamespace(tabs=tabs, grid=grid, scroll=scroll)
    return app


if __name__ == "__main__":
    build_app().run()
