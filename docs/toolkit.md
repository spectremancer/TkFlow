# Application toolkit: API and practical patterns

This guide covers the expanded API. All classes below are exported by `TkFlow/__init__.py` and use only the Python standard library. Start with [getting started](getting-started.md) for folder imports and the existing controls, then run `python -m examples.workbench` while reading this guide. See [the architecture guide](architecture.md) for project organization and lifecycle rules.

## 1. Observable state and bindings

```python
from TkFlow import State, TextInput, Label, Checkbox, Button

name = State("Ada")
TextInput(panel, bind=name)
Label(panel, bind=name)
name.set("Grace")                  # Updates both controls.
name.update(lambda text: text.upper())

enabled = State(True)
Checkbox(panel, "Allow saving", bind=enabled)
Button(panel, "Save", save).bind_enabled(enabled)
```

`State(value)` belongs to its creating thread. `get()`, `set(value)`, and `update(function)` operate on that thread. `set` only notifies when equality changes. `subscribe(callback, immediate=True)` calls `callback(value)` and returns an unsubscribe function. Callback exceptions propagate; application subscribers should be short and predictable.

`bind=state` is available on Label, Button captions, TextInput, Checkbox, Dropdown, NumericInput, Slider, ProgressBar, RadioGroup, DateInput, FilePicker, and TextArea. Values flow from the model immediately. Value controls update the model through variable traces; TextArea uses the native modified event. Labels and button captions are one-way displays. Read the same value from multiple controls by binding them to one State.

Controls must agree on types and constraints. A readonly dropdown cannot display a value outside its choices. NumericInput/Slider use numbers, Checkbox uses bool, DateInput returns `datetime.date`, and TextArea/TextInput use strings. Invalid intermediate numeric/date text is allowed while typing but does not replace a valid bound State; `.get()` raises until corrected. An invalid programmatic State update can raise from a bound control; validate your model values before committing them. State does not provide transactional rollback.

`control.bind_state(state, two_way=True)` binds an existing control. `control.bind_enabled(state)` maps bool values to enabled/disabled state. Destroying a control removes its subscriptions and traces. State itself has no Tk dependency, but mutations still belong on its owning thread. A worker should use `app.call_soon(state.set, new_value)`.

## 2. Commands: busy state, progress, cancellation, debounce

```python
from TkFlow import ProgressBar, Button

progress = ProgressBar(panel)


def analyze(context, path):
    for index in range(20):
        if context.cancelled:
            return "Cancelled"
        process_batch(path, index)  # Put timeouts on external operations.
        context.report((index + 1) * 5)
    return "Completed"


job = app.command(analyze, context=True, owner=panel,
                  prepare=lambda: (path_input.get(),),
                  on_progress=progress.set,
                  on_result=status.set,
                  on_error=lambda error: status.set(str(error)))
Button(panel, "Analyze", job, busy_text="Analyzing...", style="Primary.TButton")
Button(panel, "Cancel", job.cancel)
```

Command options add `context=False`, `owner=None`, `on_progress=None`, and `debounce_ms=0` to the [existing prepare/work/result API](commands.md).

- `context=True` passes a `CommandContext` **before** the prepared arguments. Its `cancelled` property checks both invocation cancellation and App shutdown. Its `cancel_event` is a `threading.Event` suitable for interruptible waits.
- `context.report(value)` is worker-safe. Progress is coalesced: intermediate updates can be skipped and at most one progress delivery is pending per invocation. Use it for current progress, not an audit trail.
- `command.progress` is a State initialized to `None`; it receives delivered progress values. Use `on_progress` to update controls when `None` is not valid for them.
- `command.busy` is a bool State; `running` and `future` remain available. Completion resets busy state even after result-handler failures.
- `command.cancel()` sets the cancellation Event, cancels pending debounce, and attempts Future cancellation. Its bool return describes **Future cancellation**, not whether a running worker acknowledged the Event.
- `owner=panel` cancels when the owner is disposed and suppresses its late result/error/progress/done handlers. `dispose()` explicitly releases this command's App registration. A hidden screen is still alive; use a component's `on_hide()` to cancel if navigation should stop work.
- `debounce_ms=150` waits for a quiet interval and uses only the most recent arguments. It returns `None` until actual execution starts. Invocations arriving while the previous worker is busy are suppressed when their debounce fires; this is not an automatic latest-result search engine.

A Button given a Command automatically disables while busy and re-enables afterward, preserving a pre-existing disabled state. `busy_text="Saving..."` temporarily changes its caption. `disable_while_running=False` opts out. Share one Command between buttons and menus for shared overlap protection. Pass the Command directly; do not also set `background=True` on the control.

Quick GUI-only debounced search:

```python
search = app.command(table.filter, background=False, debounce_ms=150, owner=table)
TextInput(panel, on_change=search)
```

State-based enable rules and busy restoration are independent. If multiple policies control the same button, combine the policies in your application instead of relying on subscriber order. Long work must not run in `prepare`, GUI callbacks, validators, or synchronous commands.

## 3. Layout containers

All layout wrappers support the existing outer placement options (`expand`, `fill`, `padx`, `pady`). Set `expand=True, fill="both"` through the container chain for resizing regions. Run `python -m examples.layout_gallery` for live examples.

### Grid

```python
from TkFlow import Grid, Label

grid = Grid(panel, columns=2, expand=True, fill="both")
wide = grid.cell(0, 0, colspan=2)
Label(wide, "Spans both columns")
Label(grid, "Automatic next free cell")
Label(grid, "Another automatic cell")
```

`Grid(parent, columns=2, **container_options)` assigns new direct children to the next unoccupied cell. `cell(row, column, rowspan=1, colspan=1, **column_options)` returns a Column in an explicit region. Coordinates are zero-based. Explicit overlaps raise ValueError, and destroying a child releases occupied cells. Columns share width; expanding cells give their row growth weight. `cell` coordinates and spans must be integers.

A grid does not automatically rearrange column count when the window narrows. Choose a minimum window size that fits your content, use wrapping labels, or explicitly change your layout at application breakpoints. More space does not imply an infinitely shrinkable widget.

### Tabs and split panes

```python
from TkFlow import Tabs, SplitPane

tabs = Tabs(panel, expand=True, fill="both")
editor_page = tabs.add("editor", title="Editor")
settings_page = tabs.add("settings", title="Settings")
tabs.select("settings")

panes = SplitPane(editor_page, orientation="horizontal", expand=True, fill="both")
left = panes.add("navigation", weight=0)
right = panes.add("detail", weight=1)
```

`Tabs.add(name, title=None, **column_options)` returns a Column. `select(name)` selects it; `remove(name)` destroys it. `pages` exposes the named columns. Page `.hide()`/`.show()` use the notebook's native tab visibility, and cleanup still applies.

`SplitPane` supports horizontal or vertical orientation. `add(name, weight=1, **column_options)` returns a Column. Drag the sash to resize. It inherits `pages` and `remove`; all panes are visible, so `select` is intentionally unsupported. Hiding/showing a pane removes/re-adds it; a re-added pane uses the default weight and moves to the end. Reapply native pane configuration if your layout requires a specific order/weight after hiding.

### Scrolling and disclosure

```python
from TkFlow import ScrollColumn, Collapsible

scroll = ScrollColumn(panel, height=240, expand=True, fill="both")
for title in section_titles:
    disclosure = Collapsible(scroll.content, title, collapsed=True)
    Label(disclosure.content, "Details", wraplength=450)
```

Add controls to `scroll.content`, not directly to ScrollColumn. `canvas` exposes scrolling (`yview_moveto`, etc.). The canvas resizes the content width and updates its scroll region. Canvas-local mouse wheel bindings and a scrollbar are supplied; wheel events over a nested native control may be handled by that control. No global `bind_all` hook is installed.

`Collapsible` exposes `header`, `content`, and `collapsed` (State[bool]). Hiding a disclosure's content does not destroy its controls or remove values from forms. Its header uses ASCII disclosure markers for portability across core X11 fonts.

## 4. Additional controls

| Class | Important constructor options | Value API |
| --- | --- | --- |
| `NumericInput` | `value=None, minimum=0, maximum=100, step=1, integer=False, on_change=None, bind=None` | `get()` returns int/float; `set()` validates range and finite values |
| `RadioGroup` | `values, value=None, horizontal=False, on_change=None, bind=None` | String choice; options must be distinct |
| `Slider` | `value=None, minimum=0, maximum=100, on_change=None, bind=None` | Float in range |
| `ProgressBar` | `value=0, maximum=100, mode="determinate", bind=None` | Numeric progress; `start(interval=50)` / `stop()` for animation |
| `DateInput` | `value=None` (today), plus TextInput options | `get()` returns `datetime.date`; `set(date_or_iso_string)` validates |
| `FilePicker` | `value="", mode="open", title="Choose a path", filetypes=None, on_change=None, bind=None` | Path string; `browse()` invokes a parented native dialog |

NumericInput defaults to its minimum if neither value nor binding is supplied. Slider does the same. `integer=True` rejects fractional values. Temporary invalid entry text is surfaced by `get`; forms convert it to inline errors. Numeric `on_change` ignores invalid intermediate edits. Slider's native command and radio callbacks run on the GUI thread.

DateInput uses editable **YYYY-MM-DD text**, not a popup calendar. Impossible dates raise ValueError. FilePicker modes are `open`, `save`, and `directory`; cancellation leaves the existing value unchanged. The wrapper provides selection, not file existence checks or file I/O. Use background work to process selected paths.

For multiline input use TextArea; for a readonly transcript use `readonly=True`, and for sustained thread-safe output use LogView. These APIs are described in the [base reference](reference.md).

## 5. Tables and lists

```python
from TkFlow import Table

table = Table(panel, {"name": "Name", "count": "Count"},
              rows=[{"id": "a", "name": "Ada", "count": 10},
                    {"id": "b", "name": "Grace", "count": 2}],
              key="id", on_select=lambda rows: show_details(rows),
              expand=True, fill="both", height=8)
table.sort("count")
table.filter("ada")
table.filter(None)
table.update_row("a", count=11)
table.select("a")
```

`columns` is an ordered caption mapping or a sequence of field names. `rows` are dictionaries. `key="id"` gives stable IDs; without a key, IDs are zero-based string indices in each replacement dataset. IDs are normalized to strings and must be nonempty/unique. Missing column values display as empty strings. Model rows are shallow-copied on input/output; nested objects remain application-owned.

- `set_rows(rows)` validates replacement identities before replacing the model.
- `rows()` returns the currently visible, sorted rows as copies.
- `selected()` returns selected row copies; `select(*ids)` selects native visible IDs.
- `sort(column, reverse=False, key=None)` sorts visible results. Heading clicks toggle sort. Default sorting treats numeric values numerically, strings case-insensitively, and None separately. Supply e.g. `key=float` for numeric strings.
- `filter(text)` searches all row values, or pass `filter(predicate)` with a row dictionary. `None` clears filtering. Filtering does not delete the underlying model; selection of filtered-out rows is cleared.
- `update_row(id, **values)` updates a known row without changing its identity.
- `.tree` exposes the native Treeview for advanced columns, events, and selection options. `.widget` is the scrollbar frame.

Both axes scroll. Row selection callbacks run on the GUI thread. Data processing and callbacks must stay short; this is an in-memory Treeview wrapper, not a virtualized million-row data grid. Pre-filter/aggregate large datasets in a worker, then supply a reasonably sized result.

`ListView(parent, items=(), on_select=None, **table_options)` supplies a one-column string list. `set_items(items)` replaces items; `get()` returns selected strings, and its selection callback receives those strings. IDs are zero-based indices; duplicate display strings are permitted.

## 6. Components and navigation

```python
from TkFlow import Component, ScreenStack, Label


class Details(Component):
    def build(self):
        Label(self, "Details")

    def on_show(self):
        pass  # Refresh short-lived GUI state.

    def on_hide(self):
        pass  # Optionally cancel page-specific work.


screens = ScreenStack(panel, expand=True, fill="both")
screens.add("details", Details)
screens.add("settings")  # Default Column.
screens.show_screen("settings")
screens.back()
```

Component is a Column that calls `build()` during construction. Store constructor dependencies before `super().__init__` in subclasses. Register resources through `on_dispose(callback)` and own Commands explicitly.

ScreenStack has `screens`, `current`, and `history`. `add(name, factory=Column, **options)` constructs a view with the stack as parent and shows the first view. `show_screen(name, remember=True)` hides the old view, calls `on_hide`, shows the new view, and calls `on_show`. `back()` consumes navigation history. `remove(name)` destroys a view, clears its history entries, and selects another remaining view if necessary. Hidden screens retain their values and background operations; destruction releases their resources.

## 7. Rich forms

Form now supports `fields=[schema_dicts]`, `live_validation=False`, and `validators=()` in addition to its original options.

```python
form = Form(panel, "Account", live_validation=True, fields=[
    {"name":"name", "label":"Name", "type":"text", "required":True},
    {"name":"workers", "label":"Workers", "type":"number", "value":4,
     "minimum":1, "maximum":16, "integer":True},
])
form.group("contact", "Contact information")
form.add_checkbox("contact_enabled", "Enable contact")
form.add_text("email", "Email", group="contact", required=True,
              visible_when=lambda values: values.get("contact_enabled"))
form.add_text("count", "Count", value="10", converter=int)
```

`group(name, title)` creates a named Section; field methods accept `group=name`. In addition to existing methods, use `add_number`, `add_date`, `add_multiline`, `add_radio`, and `add_file`, forwarding each control's constructor options. `add_from_schema(spec)` is equivalent to the schema list; supported types are text, dropdown, checkbox, number, date, multiline, radio, and file.

`add_field(name, label, factory, value=None, **field_options)` registers a custom control. `factory(row)` must return a wrapper with get/set; the supplied `value` is the reset default. Built-in richer controls derive their default from the control's initial value. For automatic dirty tracking, custom controls should expose a Tk `variable` or native `text` modified event, or call `form._changed()` from their own change bridge (an internal extension hook, subject to change).

`converter(value)` runs during validation/snapshot after required checks; conversion ValueErrors become inline errors. Empty optional strings are not converted. `get()` returns current raw control values; `snapshot()` returns converted values for active fields. NumericInput and DateInput are already typed controls. Validators should return None/empty string for valid input or an error string.

`visible_when(raw_values)` controls a field row's visibility. A conditionally inactive field retains its raw value but is skipped by validation and omitted from snapshots. Its value remains in `get()`. This differs from manually hiding a row: manual hiding alone does not exclude validation.

`validators` is an iterable of form-level callables receiving a copy of converted active values after field validation passes. Each returns None or a `{field_name: message}` dictionary. Use `"__form__"` for a general summary error. Field errors are shown inline. Keep all local validation short; service checks belong in workers.

`dirty` is a State[bool]. Edits compare raw values with the clean baseline, including inactive fields. `mark_clean()` accepts current values as clean; `reset()` restores initial defaults, clears errors, and marks clean. Adding a field adds its initial value to the baseline. Submitting does not automatically mark clean: a user may edit while the saved snapshot is in flight. Decide explicitly which successful save should reset your baseline.

Submit buttons now use the shared busy lifecycle and default busy caption `Working...`; customize `busy_text`. Owner-aware submission cancels on disposal and suppresses late user callbacks. The [form guide](forms.md) covers the original methods and error contract.

## 8. Appearance, dialogs, notifications, and keyboard access

`Theme(accent="#2156bd", background="#f4f6fa", surface="#ffffff", text="#172b4d", muted="#526581", danger="#b42318", font_size=10, spacing=8).apply(app)` installs consistent ttk styles using an available native font. Apply before building controls. Semantic styles include `Primary.TButton`, `Danger.TButton`, `Muted.TLabel`, `Title.TLabel`, `Heading.TLabel`, and `Error.TLabel`. Theme selects clam when available; native font metrics and widgets still vary by OS. Built-in UI captions use ASCII fallbacks for core X11 fonts.

```python
from TkFlow import InputDialog

InputDialog(app, "Workspace name?", value="Explorer").then(
    lambda value: name.set(value) if value is not None else None)
app.notify("Saved", kind="success", duration=4000)
```

`Dialog(parent, title="Dialog", modal=True, **window_options)` is a customizable Window with a Future. Add controls directly to it; call `resolve(value)` to settle and close. `close()` settles None. `then(callback)` queues GUI delivery. App shutdown settles open dialogs and suppresses later GUI callbacks. `modal=True` grabs input without starting a nested wait loop; ordinary App processing remains active. Use the native message/confirmation methods when their blocking modal behavior is acceptable. Do not block on a dialog Future in a GUI callback.

`InputDialog(parent, prompt, value="", title="Input", **options)` includes an entry, OK/Cancel, Enter submission, Escape cancellation, and initial focus. `Notification(parent, text, kind="info", duration=4000)` is a dismissible inline Row; kinds are info/success/warning/error. `app.notify` constructs it. Duration 0 disables auto-dismiss. Notifications consume layout space rather than cover controls; plan space for them in very small windows.

`app.shortcut("<Control-s>", command, owner=panel)` registers a root shortcut and returns an explicit remover. Owner disposal removes its binding. `.focus()` moves focus to a control (including the inner entry/tree of composites). `app.focus_order(first, second, save)` installs Tab/Shift-Tab order and skips hidden/disabled controls. `set_default_button(button)` and `set_cancel_button(button)` register Enter/Escape activation and return removers; default activation leaves multiline Text Enter editing intact. These methods are also available on Window. Native ttk controls retain Tab/Shift-Tab navigation; hidden screens are removed from the layout. Keep labels clear, expose keyboard alternatives, and test your OS's focus and assistive-technology behavior. This supplies useful keyboard primitives, not a claim of universal screen-reader compatibility.

## 9. Ownership and developer helpers

Each Widget exposes:

- `on_dispose(cleanup)` for subscriptions, handles, and external resource teardown.
- `safe(callback)` for a GUI-thread callback suppressed after owner disposal/App shutdown.
- `after(milliseconds, callback, *args)` for owner-scoped timers that cancel on disposal.
- `focus()`, plus the original bind/show/hide/destroy/state methods.

Commands with an owner handle cancellation and delivery automatically. Without an owner, use `widget.safe(result_handler)` when targeting disposable UI. These guards do not make native Tk operations thread-safe.

`TkFlow.devtools` provides `inspect_tree(owner)` (JSON-serializable wrapper names, paths, mapped status, and dimensions), `capture_errors(app)` (a context manager collecting callback errors), `invoke(control)`, and `pump_until(app, predicate, timeout=3)` for tests. They are small building blocks; see [testing and visual review](testing.md).
