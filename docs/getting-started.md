# Getting started

## Copy the folder

```text
my_project/
    TkFlow/
        __init__.py
        app.py
        command.py
        form.py
        ...
    ui/
        __init__.py
        main.py
```

Keep the entire `TkFlow` folder together, including the modules beginning with `_`. `__init__.py` exposes the public classes; internal modules use relative imports. Nesting or renaming the folder is supported, for example `from utils.gui import App` after copying it to `utils/gui`.

In `ui/main.py`:

```python
from TkFlow import App, Button, Label, Menu, TextInput


def main():
    app = App("Greeting", height=320, width=520)
    file_menu = Menu(app).dropdown("File")
    file_menu.add_command("Quit", app.close)
    details = app.section("Your details")
    Label(details, "Name")
    name = TextInput(details, "World")
    result = Label(details, "Ready")
    Button(details, "Greet", lambda: result.set(f"Hello, {name.get()}!"))
    app.run()


if __name__ == "__main__":
    main()
```

Run `python -m ui.main` from `my_project/`. This makes the project root an import location. Running `python ui/main.py` directly puts `ui/` on the import path instead; use the module invocation rather than modifying `sys.path`. A root-level `main.py` can simply run with `python main.py`.

Run `python -m tkinter` on a desktop to check Tk. Debian/Ubuntu commonly provide a `python3-tk` system package. On Linux without a display, use `xvfb-run -a python -m ui.main`. A virtual display is useful for automated tests; it is not a desktop preview.

## Settings and additional windows

```python
from TkFlow import Window

app.set_title("Workspace").set_size(height=600, width=900)
app.set_min_size(height=300, width=500).set_resizable((True, True))
window = Window(app, "Details", height=240, width=400)
Label(window, "This shares the application's event loop.")
Button(window, "Close", window.close)
```

Dimensions are **height, width** in pixels. Resizability pairs are **horizontal, vertical** booleans. Create one `App` per application; additional windows use `Window`, not another event loop. `app.run()` is called once. `app.close()` closes all its windows; `window.close()` closes only that window.

## Automatic layout

`App`, `Window`, `Section`, and `Column` stack children from top to bottom. `Row` arranges children left to right. Every layout parent offers `.section(title, ...)`, `.row(...)`, and `.column(...)`. You can also construct the classes directly.

```python
from TkFlow import Section, Row, Dropdown

panel = Section(app, "Search", expand=True, fill="both")
row = Row(panel, padding=0)
query = TextInput(row, expand=True)
category = Dropdown(row, ["All", "Messages", "People"])
Button(row, "Search", lambda: None)
```

`expand=True` assigns a share of unused space along the parent's stacking direction. `fill="x"` (default), `"y"`, `"both"`, or `"none"` controls how the child occupies its assigned cell. Set `expand=True, fill="both"` on each enclosing container for a large growing transcript or editor. `padx` and `pady` add outer spacing. Containers accept `padding` (inner spacing, default 8) and `spacing` (between children, default 8). App's padding defaults to 12.

Hiding a widget preserves its slot and values. Showing restores it. Destroying removes it and its children. TkFlow handles the geometry of its children with `grid`; do not mix `pack` and `grid` in those same content frames. Form's scrollable body is managed by its canvas; add fields through Form rather than trying to reposition the body.

## Appearance and native access

Extra constructor options go to the relevant native control: `width=30`, `show="*"`, `anchor="center"`, or `style="Accent.TButton"`, for example. Unknown native options produce Tk errors. TkFlow owns the layout and managed `command`, `variable`, and `textvariable` options for controls that use them.

```python
app.style.configure("Accent.TButton", padding=10)
Button(app, "Action", lambda: None, style="Accent.TButton")
```

`app.style.theme_names()` lists installed themes; `theme="clam"` is an optional App constructor argument if available. Themes and fonts vary by platform.

Native handles:

- `app.root`, `window.root`: Tk and Toplevel.
- `app.widget`, `window.widget`: content frames.
- `control.widget`: underlying ttk control; TextArea/LogView expose an outer frame here.
- `text_area.text`: native `tk.Text` for tags, selections, and editor-specific behavior.
- `value_control.variable`: managed Tk variable.
- `app.style`: `ttk.Style`.

Native handles must follow the same GUI-thread and lifetime rules as the wrappers. TkFlow's thread guards cannot protect direct native access.

## Organizing larger applications

Use controller classes or `build_app()` functions to retain related controls and commands. The examples expose `app.demo` as an example-specific collection for automated interaction; it is not a TkFlow API requirement. Keep domain functions independent of widgets, pass captured values into workers, and let completion handlers render results. Start with [the runnable examples](examples.md).
