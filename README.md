# TkFlow

TkFlow is a lightweight Python library for building Tkinter desktop applications with simple classes. Create an app, add menus and sections, and place controls inside them. TkFlow handles widget variables, layout, and delivery of background results to the GUI thread.

Version **0.1.0** provides the first usable foundation: application and additional windows, menus and submenus, nested rows and columns, labels, buttons, text inputs, checkboxes, dropdowns, dialogs, styling, and background commands. It uses only Tkinter and the Python standard library at runtime.

## Add TkFlow to a project

Requires Python **3.10+** with Tkinter installed. Copy the **entire `TkFlow/` folder** into your project. No pip installation, build step, or packaging configuration is needed. Each public class lives in its own module; `__init__.py` exposes them together.

For a project with a child directory:

```text
my_project/
    TkFlow/
        __init__.py
        app.py
        menu.py
        section.py
        button.py
        ...
    ui/
        __init__.py
        main.py
```

In `ui/main.py`, use `from TkFlow import App, Menu, Section, Button`, then run **from `my_project/`**:

```bash
python -m ui.main
```

Python then finds the sibling `TkFlow` folder on its normal import path. Running `python ui/main.py` directly uses the child directory as the import root; prefer the module command above. A `main.py` in the project root can simply run with `python main.py`.

You can also nest the folder under another package, such as `my_project/utils/TkFlow/`, and import with `from utils.TkFlow import App`. All internal imports are relative, so the folder can be renamed too. Individual class imports work as well: `from TkFlow.app import App`, `from TkFlow.menu import Menu`, or `from TkFlow.text_input import TextInput`.

Run `python -m tkinter` to check Tk on a desktop. Some Linux distributions ship it separately (for example, `python3-tk` on Debian/Ubuntu). A desktop display or virtual display is required to create windows.

## Your first application

```python
from TkFlow import App, Button, Label, Menu, TextInput

app = App(title="My application", height=300, width=480)
app.set_title("Greeting app")
app.set_size(height=320, width=500)

menu = Menu(app)
file = menu.dropdown("File")
file.add_command("Quit", app.close)
help_menu = menu.dropdown("Help")
help_menu.add_command("About", lambda: app.message("Built with TkFlow"))

section = app.section("Greeting")
Label(section, "Your name")
name = TextInput(section, value="World")
output = Label(section, "Ready")
Button(section, "Greet", command=lambda: output.set(f"Hello, {name.get()}!"))

app.run()
```

Only call `app.run()` once, after constructing the interface. Keep it inside `if __name__ == "__main__":` when your module will be imported elsewhere. See [the greeting example](examples/greeting.py) and [the form example](examples/form.py), which separate construction into a reusable `build_app()` function.

## Windows and application settings

`App(title="TkFlow", height=480, width=640, ...)` owns the root window. Dimensions use explicit `height` and `width` in pixels; `set_size(height, width)` follows that same order.

Optional settings: `min_height=100`, `min_width=100`, `resizable=True`, `padding=12`, `spacing=8`, and `theme=None`. `resizable` can also be `(horizontal, vertical)`, such as `(True, False)`. Choose a theme from `app.style.theme_names()`.

`set_title()`, `set_size()`, `set_min_size()`, and `set_resizable()` return the window, so calls can be chained. `app.close()` destroys its windows. `Window(app, title="Details", height=240, width=360)` creates an additional window with the same settings except `theme`; it shares the application event loop. Add widgets and menus directly to that window. `window.close()` closes just that window.

`app.message("Saved", title="Status", kind="info")` shows a dialog (`info`, `warning`, or `error`). `app.confirm("Continue?")` returns a boolean. These also work on `Window` and are parented to the corresponding window.

## Sections and automatic layout

```python
from TkFlow import Section, Row, Column, Label, TextInput

profile = Section(app, "Profile", padding=12, spacing=8)
row = Row(profile, padding=0)
Label(row, "Name")
name = TextInput(row, expand=True)
column = Column(profile)
Label(column, "Additional information")
```

An `App`, `Window`, `Column`, or default `Section` stacks children vertically. A `Row` lays them out horizontally. Containers can be nested freely. Each parent also offers `.section(title, ...)`, `.row(...)`, and `.column(...)` helpers. `Section` accepts `orientation="horizontal"` or `"vertical"`; `Container` is a plain frame with the same orientation option.

All widgets and containers accept these placement options:

| Option | Default | Effect |
| --- | --- | --- |
| `expand` | `False` | Give this child a share of extra space along its parent's layout direction |
| `fill` | `"x"` | Stretch within the allocated cell: `"none"`, `"x"`, `"y"`, or `"both"` |
| `padx`, `pady` | `0` | Extra outer spacing in pixels |

Containers also accept `padding=8` for inner spacing and `spacing=8` between children. Use `expand=True, fill="both"` on each enclosing container when a nested region should grow in both directions.

TkFlow uses `grid` inside its content containers. Avoid manually using `pack` or `place` for children of those same containers. The top-level content frame is managed separately.

## Controls and values

| Class | Construction | Value access | Callback |
| --- | --- | --- | --- |
| `Label` | `Label(parent, text="Hello")` | `.get()` / `.set(text)` | Native event bindings |
| `Button` | `Button(parent, text="Save", command=save)` | `.get()` / `.set(text)` for its label | `command()` |
| `TextInput` | `TextInput(parent, value="", on_change=changed)` | `.get()` / `.set(text)` | `on_change(value)` on edits **and** `.set()` |
| `Checkbox` | `Checkbox(parent, text="Enabled", value=False, command=changed)` | `.get()` / `.set(bool)` | `command(bool)` on activation; `.set()` does not call it |
| `Dropdown` | `Dropdown(parent, values=["A", "B"], on_change=changed)` | `.get()` / `.set(choice)` | `on_change(choice)` on selection; `.set()` does not call it |

Dropdowns select the first option by default, or accept `value="B"`. They are readonly unless `editable=True`. Invalid choices raise `ValueError` in readonly mode. An empty choice list has an empty initial value. In editable mode, manually typed changes can be observed using `.bind()`; `on_change` still represents list selection.

All controls offer `.configure(**native_options)`, `.enable()`, `.disable()`, `.hide()`, `.show()`, and `.destroy()`. Hiding preserves the widget and its layout position; destroying removes it. `.bind("<Return>", handler)` calls the handler with a native Tk event and adds to existing bindings by default. `Button.invoke()` runs its command unless disabled, returning the result or a background `Future`.

Extra keyword arguments are forwarded to the underlying ttk widget, for example `width=30`, `show="*"` on text inputs, `anchor="center"` on labels, and `style="Accent.TButton"` on buttons. Tkinter reports unsupported native options. TkFlow reserves layout arguments and the managed `textvariable`, `variable`, and `command` options where applicable.

## Menus

```python
menu = Menu(app)
file = menu.dropdown("File")
file.add_command("Open", open_file, accelerator="Ctrl+O")
file.separator()
recent = file.dropdown("Recent")
recent.add_command("Example", open_example)
file.add_command("Quit", app.close)
```

`Menu(app)` attaches a menu bar. Use one bar per window. `.dropdown(label)` returns a child menu, supporting arbitrarily nested submenus. `.add_command(label, command, ...)` returns the native entry index. It accepts native entry options such as `state="disabled"` or `accelerator="Ctrl+O"`. An accelerator is a displayed hint; bind the shortcut separately, e.g. `app.root.bind("<Control-o>", lambda event: open_file())`.

## Background commands and safe GUI updates

Create widgets and run the event loop on the **main thread**. Tk widgets and their variables must not be accessed from workers, including reading values. Use background threads for blocking I/O or other work that would freeze the interface:

```python
import time
from TkFlow import Button, Label

status = Label(app, "Ready")

def load_data():
    time.sleep(1)  # Replace with your blocking operation; no widget access here.
    return "Finished"

Button(app, "Load", command=load_data, background=True,
       on_result=status.set,
       on_error=lambda error: status.set(f"Failed: {error}"))
```

Buttons and menu commands accept `background=True`, `on_result(result)`, and `on_error(exception)`. Text input, checkbox, and dropdown callbacks support these options too; their value is captured on the GUI thread before the worker starts. Completion callbacks run on the main GUI thread. Without `background=True`, commands run synchronously; optional result/error handlers run there as well. Unhandled worker errors go through Tk's `report_callback_exception` hook.

For a form, read widget values **before** starting work:

```python
def submit():
    current_name = name.get()  # This handler runs on the GUI thread.
    app.run_in_thread(save_name, current_name,
                      on_result=status.set,
                      on_error=lambda error: status.set(str(error)))

Button(app, "Save", command=submit)
```

`app.run_in_thread(function, *args, on_result=None, on_error=None, **kwargs)` returns a `concurrent.futures.Future`. It tracks the worker result; GUI delivery happens later through the event loop. Do not wait with `.result()` on the GUI thread. `app.call_soon(function, *args)` safely queues progress updates from any thread. `app.after(milliseconds, function, *args)` schedules a GUI-thread callback and must itself be called on that thread.

Workers are daemon threads. Closing the app discards queued updates and suppresses later GUI delivery; running work is not forcibly cancelled and may end when the process exits. Use your own `threading.Event` for cooperative cancellation when needed, and do not rely on a daemon worker to finish critical writes after closing. If a result targets a secondary window or a widget you destroy while work is active, guard that callback or coordinate its lifetime. For heavy CPU work, use a separate process outside this first iteration's thread helper.

## Styling and native Tk access

```python
app.style.configure("Accent.TButton", padding=10)
Button(app, "Styled", command=lambda: None, style="Accent.TButton")
```

`app.root` / `window.root` expose Tk / Toplevel, `app.style` exposes `ttk.Style`, and `.widget` exposes each native widget. `app.widget` is the content frame. Value controls expose `.variable`. These escape hatches follow Tkinter's main-thread and lifecycle rules.

## Development and tests

From this repository's root (no installation needed):

```bash
python -m unittest discover -s tests -v
python -m examples.greeting
python -m examples.form
```

On headless Linux, run the tests or examples through `xvfb-run -a`. In the prepared Codex cloud environment:

```bash
export PATH="/workspace/.tkflow-env/root/usr/bin:$PATH"
xvfb-run -a python3 -m unittest discover -s tests -v
```

The tests exercise real widgets, nested layout and resizing, value changes, menu actions, background delivery, error handling, and cleanup. They also verify a copied folder can be imported from a child directory and from a nested, renamed package. Dialog routing is mocked to avoid interactive prompts. This iteration is validated on Linux; native Windows/macOS appearance and behavior still need platform testing.

## Direction and scope

The goal remains a beginner-friendly, consistent API with minimal boilerplate, reusable components, clear errors, and access to native Tkinter when needed. Future iterations can add multiline text, radio buttons, lists, sliders, progress bars, and richer layout helpers. This first release focuses on the README's original foundation rather than those additional controls.

Licensed under GPL-3.0-only; see [LICENSE](LICENSE).
