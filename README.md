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

## A full application toolkit

The library now also provides observable State binding, automatic command busy states and progress, cancellation and debounce, grids/tabs/split panes/scrolling/disclosures, numeric/date/radio/slider/progress/file controls, sortable/filterable tables and lists, reusable Components and ScreenStack navigation, richer conditional forms, semantic themes, custom dialogs, notifications, keyboard shortcuts, and developer helpers.

```python
from TkFlow import State, TextInput, Label, Button

name = State("Developer")
TextInput(section, bind=name)
Label(section, bind=name)
job = app.command(lambda text: f"Hello, {text}",
                  prepare=lambda: (name.get(),), on_result=output.set,
                  owner=section)
Button(section, "Run", job, busy_text="Working...")
```

See the [expanded API guide](docs/toolkit.md) for complete signatures and the [architecture guide](docs/architecture.md) for how to organize a real project.

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

## SQLiteFlow: database CRUD

Copy the sibling **`SQLiteFlow/` folder** alongside TkFlow (or use it independently). It provides ordinary dictionary CRUD with parameterized filters, transactions, foreign keys, and per-operation worker-safe connections:

```python
from SQLiteFlow import Database, Column

with Database("data/app.sqlite3") as db:
    contacts = db.create_table("contacts", {"name":str, "email":Column(str, unique=True)})
    identity = contacts.insert(name="Ada", email="ada@example.com")
    contact = contacts.get(identity)
    contacts.update(identity, name="Ada Lovelace")
    rows = contacts.find({"name__contains":"Ada"}, order_by="name")
    contacts.delete(identity)
```

Pass form dictionaries into CRUD methods from a TkFlow background Command. See [the complete SQLiteFlow guide](docs/sqlite.md) and run `python -m examples.database_crud` for a persistent contacts application.

## Runnable examples

From the repository root:

```bash
python -m examples.database_crud
python -m examples.workbench
python -m examples.layout_gallery
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
- [Expanded toolkit reference](docs/toolkit.md)
- [SQLiteFlow CRUD and GUI integration](docs/sqlite.md)
- [Architecture and compatibility](docs/architecture.md)
- [Testing and inspected screenshots](docs/testing.md)
- [Example walkthroughs](docs/examples.md)

## Development

```bash
python -m unittest discover -s tests -v
```

A desktop display is required for Tk windows. On headless Linux use `xvfb-run -a python -m unittest discover -s tests -v`. In the prepared cloud environment, first add `/workspace/.tkflow-env/root/usr/bin` to PATH. Run `python -m tkinter` to check a desktop Tk installation; Debian/Ubuntu may require `python3-tk`.

The 96 tests cover real widget behavior and the examples. The screenshot gallery includes 28 inspected captures with default/compact layouts, dialogs, validation, and busy states. Linux is validated; native Windows/macOS behavior still needs platform testing. The toolkit remains a plain copyable folder with native Tk access. Screenshots cover the example screens at standard and compact Linux sizes; OS-specific fonts, high DPI, and assistive technology still require target-platform testing.

Licensed under GPL-3.0-only; see [LICENSE](LICENSE).
