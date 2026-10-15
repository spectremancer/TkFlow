"""A desktop-style menu bar. Run: python -m examples.menus."""
from types import SimpleNamespace
from TkFlow import App, Button, Label, Menu, TextArea, Window


def build_app() -> App:
    app = App("TkFlow • menu workspace", height=540, width=820)
    workspace = app.section("Workspace", expand=True, fill="both")
    editor = TextArea(workspace, "Try the File, Edit, View, Tools, and Help menus.\n",
                      expand=True, fill="both", undo=True)
    status = Label(app, "Ready")
    menu = Menu(app)
    file = menu.dropdown("File")
    new = app.command(lambda: editor.set(""), background=False)
    file.add_command("New document", new, accelerator="Ctrl+N")
    recent = file.dropdown("Open sample")
    for name in ("Welcome", "Notes", "Checklist", "Meeting"):
        recent.add_command(name, lambda name=name: editor.set(f"{name}\n\nStart writing here.\n"))
    file.separator()
    file.add_command("Document summary", lambda: status.set(f"{len(editor.get())} characters"))
    file.add_command("Close", app.close)
    app.root.bind("<Control-n>", lambda event: new())

    edit = menu.dropdown("Edit")
    for name, event in (("Cut", "<<Cut>>"), ("Copy", "<<Copy>>"), ("Paste", "<<Paste>>")):
        edit.add_command(name, lambda event=event: editor.text.event_generate(event))
    edit.separator()
    edit.add_command("Select all", lambda: editor.text.tag_add("sel", "1.0", "end-1c"))
    edit.add_command("Clear document", lambda: editor.clear())

    view = menu.dropdown("View")
    themes = view.dropdown("Theme")
    for theme in sorted(app.style.theme_names()):
        themes.add_command(theme, lambda theme=theme: app.style.theme_use(theme))
    size = view.dropdown("Window size")
    for label, height, width in (("Compact", 400, 600), ("Comfortable", 540, 820), ("Large", 700, 1000)):
        size.add_command(label, lambda h=height, w=width: app.set_size(height=h, width=w))
    view.add_command("Hide status", status.hide)
    view.add_command("Show status", status.show)

    def analyze(text):
        # Simulated blocking analysis; a real implementation could read files.
        if app.stop_event.wait(0.2):
            return "Analysis cancelled"
        return f"Analysis: {len(text.split())} words, {len(text.splitlines())} lines"

    analyze_command = app.command(analyze, prepare=lambda: (editor.get(),), on_result=status.set,
                                  on_error=lambda error: status.set(str(error)))
    tools = menu.dropdown("Tools")
    tools.add_command("Analyze document in background", analyze_command)
    transformations = tools.dropdown("Transform")
    transformations.add_command("Uppercase", lambda: editor.set(editor.get().upper()))
    transformations.add_command("Lowercase", lambda: editor.set(editor.get().lower()))
    transformations.add_command("Trim whitespace", lambda: editor.set(editor.get().strip()))
    tools.add_command("Coming soon", lambda: None, state="disabled")

    def show_help():
        window = Window(app, "Quick help", height=220, width=480)
        Label(window, "Menus can share Command instances with buttons.")
        Label(window, "Long work uses the pool; GUI-only actions stay on this thread.")
        Button(window, "Close help", window.close)

    help_menu = menu.dropdown("Help")
    help_menu.add_command("Quick help", show_help)
    help_menu.add_command("About", lambda: app.message("TkFlow • copyable GUI classes"))
    Button(app, "Analyze (same command as Tools menu)", analyze_command)
    app.demo = SimpleNamespace(editor=editor, status=status, menu=menu, analyze=analyze_command, new=new)
    return app


if __name__ == "__main__":
    build_app().run()
