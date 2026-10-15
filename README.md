# TkFlow

TkFlow is a copyable folder of Python classes for building Tkinter desktop applications with little setup. It handles menus, sections, nested layouts, common controls, forms, multiline text, GUI logs, and safe delivery of background work to the GUI thread. It uses Python 3.10+ and the standard library, including Tkinter.

## Use it in any project

Copy the entire **`TkFlow/` folder** into your project. No pip installation or build step is needed. Import its classes through `__init__.py`:

```python
from TkFlow import App, Button, Label, Menu, TextInput

app = App("My application", height=320, width=500)
Menu(app).dropdown("File").add_command("Quit", app.close)
section = app.section("Greeting")
name = TextInput(section, "World")
output = Label(section, "Ready")
Button(section, "Greet", lambda: output.set(f"Hello, {name.get()}!"))
app.run()
```

If your entry point is `ui/main.py`, run `python -m ui.main` **from the project root** so it can import the sibling TkFlow folder. A root-level `main.py` can run with `python main.py`. Relative internal imports also support a nested/renamed copy, such as `from utils.gui import App`.

## Forms and background commands

```python
from TkFlow import Form

form = Form(app, "Profile", expand=True, fill="both")
form.add_text("name", "Name", required=True)
form.add_dropdown("role", "Role", ["Developer", "Designer"])
form.add_checkbox("updates", "Receive updates", value=True)
form.add_submit("Save", lambda values: f"Saved {values['name']}",
                on_result=output.set)
form.add_button("Reset", form.reset)
```

Construct controls **before** `app.run()`. Form supports dynamic fields, scrolling, inline validation, reset, and background submission of captured values. For ordinary controls, share an `app.command(function, prepare=..., on_result=..., on_error=...)` between buttons and menus. Command defaults to background execution with duplicate suppression; preparation and completion callbacks run on the GUI thread. Quick callbacks that access widgets remain synchronous.

App's worker pool defaults to four daemon threads and 64 queued tasks. Queue saturation fails immediately instead of blocking the GUI. LogView provides a separate bounded message queue with batched insertion and retained-line limits. Arbitrary slow GUI callbacks can still freeze Tk; use the command pattern for blocking work and timeouts for external I/O.

## Runnable examples

From the repository root:

```bash
python -m examples.greeting
python -m examples.form
python -m examples.menus
python -m examples.chat
python -m examples.logging_gui
python -m examples.dynamic_form
```

All examples are self-contained: chat replies, document analysis, and saves are simulated. No API key or external service is needed.

## Detailed documentation

- [Documentation index](docs/README.md)
- [Getting started, imports, layout, and styling](docs/getting-started.md)
- [Class reference](docs/reference.md)
- [Commands, worker queues, errors, and shutdown](docs/commands.md)
- [Form fields, validation, and submission](docs/forms.md)
- [Example walkthroughs](docs/examples.md)

## Development

```bash
python -m unittest discover -s tests -v
```

A desktop display is required for Tk windows. On headless Linux use `xvfb-run -a python -m unittest discover -s tests -v`. In the prepared cloud environment, first add `/workspace/.tkflow-env/root/usr/bin` to PATH. Run `python -m tkinter` to check a desktop Tk installation; Debian/Ubuntu may require `python3-tk`.

Tests cover real widget behavior and the examples. Linux is validated; native Windows/macOS behavior still needs platform testing. Additional controls such as radio buttons, tables, sliders, and progress bars can be added in future iterations while preserving the simple class API and native Tk access.

Licensed under GPL-3.0-only; see [LICENSE](LICENSE).
