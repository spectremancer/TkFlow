"""A complete multi-screen desktop workbench. Run: python -m examples.workbench."""
from datetime import date
from types import SimpleNamespace
from TkFlow import (App, Button, Checkbox, Collapsible, Component, DateInput, FilePicker,
                    Form, Grid, InputDialog, Label, ListView, LogView, Menu, NumericInput,
                    ProgressBar, RadioGroup, ScreenStack, Slider, SplitPane, State,
                    Table, TextInput, Theme)


class WelcomeCard(Component):
    """Reusable component; a real application can move this into ui/components.py."""
    def build(self):
        Label(self, "Build less plumbing.", style="Heading.TLabel")
        Label(self, "Shared state, safe commands and composable screens.\nExplore the pages on the left.",
              style="Muted.TLabel", wraplength=480, justify="left")


def build_app():
    app = App("TkFlow Workbench", height=780, width=1120, min_height=560, min_width=780)
    Theme().apply(app)
    heading = app.row(padding=(4, 4, 4, 10))
    Label(heading, "TkFlow", style="Title.TLabel")
    Label(heading, "DEVELOPER WORKBENCH", style="Muted.TLabel", expand=True)
    status = State("Ready")
    Label(heading, bind=status, style="Muted.TLabel")
    split = SplitPane(app, expand=True, fill="both")
    sidebar = split.add("navigation", weight=0, padding=8)
    Label(sidebar, "EXPLORE", style="Muted.TLabel")
    stack = ScreenStack(split.add("workspace", weight=1, padding=4), padding=0, expand=True, fill="both")
    pages = {name: stack.add(name, padding=12) for name in ("Overview", "Data", "Forms", "Tasks", "Controls")}
    for name in pages:
        Button(sidebar, name, lambda name=name: stack.show_screen(name), width=15)
    Label(sidebar, "All examples run locally.\nNo service credentials needed.", wraplength=145,
          style="Muted.TLabel", justify="left")

    overview = pages["Overview"]
    Label(overview, "A toolkit that grows with your app", style="Heading.TLabel")
    WelcomeCard(overview, padding=(0, 8))
    metrics = Grid(overview, columns=3, padding=0)
    for number, caption in (("12", "Capability areas"), ("4", "Bounded workers"), ("0", "Runtime dependencies")):
        card = metrics.column(padding=12)
        Label(card, number, style="Title.TLabel")
        Label(card, caption, style="Muted.TLabel", wraplength=150)
    section = overview.section("Start with an example")
    Label(section, "- Browse and filter a table\n- Edit a validated form\n- Run and cancel background work\n- Try additional controls",
          justify="left", wraplength=520)
    Button(section, "Explore the data screen", lambda: stack.show_screen("Data"), style="Primary.TButton")
    details = Collapsible(overview, "How the parts fit together", collapsed=True)
    Label(details.content, "State owns values. Components own widgets. Commands own work.\nEach owner releases callbacks and subscriptions when destroyed.",
          wraplength=550, justify="left")

    data = pages["Data"]
    Label(data, "People directory", style="Heading.TLabel")
    Label(data, "Click a heading to sort. Type to filter. Select a row to inspect it.", style="Muted.TLabel", wraplength=600)
    search = TextInput(data, width=30, on_change=lambda text: filter_command(text))
    selected = State("No person selected")
    table = Table(data, {"name": "Name", "team": "Team", "tickets": "Open tickets"},
                  [{"id": 1, "name": "Ada Lovelace", "team": "Platform", "tickets": 3},
                   {"id": 2, "name": "Grace Hopper", "team": "Tools", "tickets": 12},
                   {"id": 3, "name": "Margaret Hamilton", "team": "Platform", "tickets": 2},
                   {"id": 4, "name": "Katherine Johnson", "team": "Research", "tickets": 8}],
                  key="id", height=8, expand=True, fill="both",
                  on_select=lambda rows: selected.set(rows[0]["name"] if rows else "No person selected"))
    filter_command = app.command(table.filter, background=False, debounce_ms=150, owner=table)
    Label(data, bind=selected, style="Muted.TLabel")
    Button(data, "Notify selection", lambda: app.notify(selected.get(), kind="success"))

    form_page = pages["Forms"]
    Label(form_page, "Project settings", style="Heading.TLabel")
    form = Form(form_page, "Configuration", expand=True, fill="both", live_validation=True)
    form.group("identity", "Project identity")
    form.add_text("name", "Project name", value="Explorer", required=True, group="identity")
    form.add_number("workers", "Worker count", value=4, minimum=1, maximum=16, integer=True)
    form.add_date("release", "Release date", value=date(2026, 11, 1))
    form.add_checkbox("contact", "Send release updates", value=True)
    form.add_text("email", "Contact email", value="team@example.com",
                  visible_when=lambda values: values.get("contact"),
                  validator=lambda value: None if "@" in value else "Include an @")
    form.add_multiline("notes", "Release notes", value="A practical desktop toolkit.", height=3)
    form.add_submit("Save settings", lambda values: f"Saved {values['name']}", on_result=status.set)
    form.add_button("Reset", form.reset)
    dirty_status = Label(form_page, "No unsaved changes", style="Muted.TLabel")
    dirty_status.on_dispose(form.dirty.subscribe(lambda dirty: dirty_status.set("Unsaved changes" if dirty else "No unsaved changes")))

    tasks = pages["Tasks"]
    Label(tasks, "Background job monitor", style="Heading.TLabel")
    Label(tasks, "The interface stays interactive while work runs. Progress is coalesced.", style="Muted.TLabel", wraplength=600)
    progress = ProgressBar(tasks)
    output = LogView(tasks, height=10, expand=True, fill="both")
    def work(context):
        for step in range(1, 21):
            if context.cancel_event.wait(0.04) or context.cancelled:
                output.print("Cancellation acknowledged")
                return "Cancelled"
            context.report(step * 5)
            output.print(f"Processed batch {step:02d}/20")
        return "All batches completed"
    task = app.command(work, context=True, owner=tasks, on_progress=progress.set,
                       on_result=status.set, on_error=lambda error: status.set(str(error)))
    actions = tasks.row(padding=0)
    Button(actions, "Run analysis", task, busy_text="Analyzing...", style="Primary.TButton")
    Button(actions, "Cancel", task.cancel)
    Button(actions, "Clear log", output.clear)

    controls = pages["Controls"]
    Label(controls, "Controls and shared state", style="Heading.TLabel")
    name = State("Developer")
    TextInput(controls, bind=name)
    Label(controls, bind=name, style="Heading.TLabel")
    choices = controls.section("Options")
    RadioGroup(choices, ["Local", "Preview", "Production"], horizontal=True)
    volume = State(40.0)
    Slider(choices, bind=volume)
    NumericInput(choices, bind=volume)
    DateInput(choices, value=date(2026, 11, 1))
    FilePicker(controls, mode="directory", title="Choose a workspace", padding=0)
    Button(controls, "Ask for a name", lambda: InputDialog(app, "What should we call this workspace?", value=name.get()).then(
        lambda result: name.set(result) if result is not None else None))
    enabled = State(True)
    Checkbox(controls, "Enable the action below", bind=enabled)
    Button(controls, "Enabled by state", lambda: app.notify("State-bound controls are ready")).bind_enabled(enabled)

    menu = Menu(app)
    navigate = menu.dropdown("Navigate")
    for name in pages:
        navigate.add_command(name, lambda name=name: stack.show_screen(name))
    navigate.add_command("Back", stack.back)
    navigate.separator()
    navigate.add_command("Quit", app.close)
    app.shortcut("<Control-1>", lambda: stack.show_screen("Overview"))
    app.shortcut("<Control-2>", lambda: stack.show_screen("Data"))
    app.shortcut("<Escape>", task.cancel)
    app.demo = SimpleNamespace(stack=stack, pages=pages, table=table, search=search, form=form,
                               task=task, output=output, progress=progress, status=status, name=name)
    return app


if __name__ == "__main__":
    build_app().run()
