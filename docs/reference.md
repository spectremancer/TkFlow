# Class reference

All classes below are exported by `TkFlow/__init__.py`. They also live in individual modules, for example `TkFlow.app`, `TkFlow.menu`, `TkFlow.command`, and `TkFlow.form`. Public methods that access GUI objects must run on the GUI thread, except the specifically documented queue methods.

## App and Window

```python
App(title="TkFlow", height=480, width=640, *, min_height=100, min_width=100,
    resizable=True, padding=12, spacing=8, theme=None,
    max_workers=4, max_pending=64)
Window(parent, title="TkFlow", height=320, width=480, *, min_height=100,
       min_width=100, resizable=True, padding=12, spacing=8)
```

`Window` shares the parent's App, worker pool, theme, and event loop. App owns `root`, `widget`, `style`, and the thread-safe `stop_event`. Window owns its own `root` and content `widget`, and exposes `.app`.

Both provide:

| Method | Behavior |
| --- | --- |
| `set_title(title)` | Set title; return window |
| `set_size(height, width)` | Positive integer pixel dimensions; return window |
| `set_min_size(height, width)` | Positive minimum dimensions; return window |
| `set_resizable(value)` | bool or `(horizontal, vertical)` bool pair; return window |
| `section(title="", **options)` | Create a Section |
| `row(**options)` / `column(**options)` | Create a Row/Column |
| `message(text, title="Message", kind="info")` | Parented info/warning/error dialog |
| `confirm(text, title="Confirm")` | Parented yes/no dialog, returning bool |
| `close()` | Destroy this window; App also shuts down workers and other windows |

App additionally provides `run()`, `after(milliseconds, callback, *args)`, `call_soon(callback, *args)`, `run_in_thread(...)`, and `command(function, **options)`. See [execution policies](commands.md) for signatures, error routing, queue limits, and shutdown.

## Containers and common widget operations

```python
Container(parent, *, orientation="vertical", spacing=8, padding=8, title=None,
          expand=False, fill="x", padx=0, pady=0, **native_options)
Section(parent, title="", **options)
Row(parent, **options)
Column(parent, **options)
```

A titled Section uses a ttk LabelFrame; an empty title uses a plain Frame. Rows force horizontal orientation; Columns force vertical orientation. Do not pass `orientation` to Row/Column. Parents may be App, Window, or another container.

Widget is the shared base. Controls and containers expose `.widget`, `.app`, and `.parent`, plus:

- `configure(**options)`: native configuration, returning self.
- `enable()` / `disable()`: set native widget state. Disabling a container does **not** recursively disable its children.
- `hide()` / `show()`: remove/restore its grid slot, returning self.
- `destroy()`: destroy this control/subtree and unregister its layout item.
- `bind(event, callback, add=True)`: callback receives the native Tk event. Returns a binding ID. Use native `.unbind(event, id)` for removal.

Placement options `expand`, `fill`, `padx`, and `pady` are accepted by each control. Container padding/spacing are separate from those placement options. TextArea/LogView override enable/disable/configure/bind to act on their inner Text control.

## Basic controls

```python
Label(parent, text="", **options)
Button(parent, text="", command=None, *, background=False,
       on_result=None, on_error=None, **options)
TextInput(parent, value="", *, on_change=None, background=False,
          on_result=None, on_error=None, **options)
Checkbox(parent, text="", value=False, *, command=None, background=False,
         on_result=None, on_error=None, **options)
Dropdown(parent, values, value=None, *, editable=False, on_change=None,
         background=False, on_result=None, on_error=None, **options)
```

| Control | `get()` / `set(value)` | Callback arguments and timing |
| --- | --- | --- |
| Label | Display text | Native bindings only |
| Button | Button caption | `command()`, on activation |
| TextInput | String | `on_change(value)`, edits **and** `.set()` |
| Checkbox | bool; `.set()` requires bool | `command(bool)`, activation only |
| Dropdown | Choice string | `on_change(choice)`, list selection only |

Value `set()` methods return the control. TextInput, Checkbox, and Dropdown expose `.variable`. `Button.invoke()` honors disabled state and returns the ordinary callback result or background Future. A Command-backed button returns its Command's result/Future.

Dropdown selects the first option unless `value` is supplied. Readonly dropdowns reject invalid choices; `editable=True` permits arbitrary text. Empty choices initialize with an empty string. Editing typed dropdown text does not trigger `on_change`; use native event/variable bindings if needed. Re-enabling a readonly dropdown preserves its readonly state.

Existing `background=True` callbacks are distinct submissions; use a shared Command when duplicate suppression or a prepare phase is needed. TextInput/Checkbox/Dropdown snapshot their value on the GUI thread before dispatching background callbacks. Such callbacks must still avoid widget access.

## Menu

```python
Menu(parent, *, tearoff=False, **native_options)
```

Parent is App, Window, or a Menu. Construct one bar per window. `dropdown(label, **native_menu_options)` creates and attaches a submenu and returns it. `separator()` appends a separator and returns the menu.

`add_command(label, command, background=False, on_result=None, on_error=None, **entry_options)` adds a zero-argument callback and returns the native index. Extra options include `state="disabled"` and `accelerator="Ctrl+O"`. Accelerator text does not install a keyboard binding. Use `app.root.bind("<Control-o>", ...)` separately.

Use closures/default arguments to capture loop variables:

```python
for theme in app.style.theme_names():
    view.add_command(theme, lambda theme=theme: app.style.theme_use(theme))
```

Use `.widget.entryconfigure(index, state="disabled")` for dynamic entry state and `.widget.invoke(index)` for programmatic activation on the GUI thread. Native checkbutton/radiobutton menu entries can be added through `.widget` using Tk variables; keep those variables alive yourself.

## TextArea

```python
TextArea(parent, value="", *, readonly=False, max_lines=None,
         autoscroll=True, **text_options)
```

A vertically scrollable multiline text editor or output area. `.widget` is an outer frame, `.text` is the inner `tk.Text`. Extra options configure Text (default `wrap="word"`, `height=10`, `width=40`). It accepts the standard placement options.

- `get()` returns content without Tk's mandatory trailing newline.
- `set(text)` replaces content; `clear()` empties it.
- `append(text, tag=None)` appends without adding its own newline.
- `readonly=True` prevents user edits; programmatic set/append still work.
- `max_lines` trims oldest logical lines on programmatic edits. It is not a byte limit and does not police user typing in editable mode.
- `autoscroll=True` scrolls to the end on programmatic edits. Disable to retain the viewport.
- Configure colors/fonts/wrapping with `.configure(...)`, and tags/selections with `.text`.

TextArea methods are GUI-only. From a worker, use `app.call_soon(area.append, text)` for modest output or use LogView for sustained output. Tagged append is useful for chat roles:

```python
transcript.text.tag_configure("sender", foreground="#175cd3")
transcript.append("You: Hello\n\n", tag="sender")
```

## LogView and GuiLogHandler

```python
LogView(parent, *, max_lines=2000, max_pending=1000, poll_ms=40,
        batch_size=100, max_message_chars=16000, **text_area_options)
```

LogView is a readonly TextArea with a separate bounded queue. Worker-safe methods:

- `write(text)`: enqueue one text chunk without blocking; does not append a newline.
- `print(*values, sep=" ", end="\n")`: print-like convenience, writing to this view only.

Each chunk is truncated beyond `max_message_chars` characters with a marker. When the queue is full, newest chunks are dropped; `.dropped_messages` reports overflow count. Oldest rendered lines are trimmed at `max_lines`. By default a GUI timer joins up to 100 queued chunks into one insertion every 40 ms. None of these limits can make rendering an arbitrarily large retained document free; tune them for your workload.

`get()`, `clear()`, other text operations, and `attach_logger()` remain GUI-only. `clear()` empties pending output and rendered text; concurrently produced new output can appear afterward. Output written after disposal/App shutdown is ignored.

```python
import logging
logger = logging.getLogger("myapp.jobs")
logger.setLevel(logging.INFO)
handler = output.attach_logger(logger, level=logging.INFO,
                               format="%(levelname)s %(message)s")
```

`attach_logger` returns a `GuiLogHandler` and does not change logger level or propagation. Configure those deliberately. It accepts the standard logging Formatter format (default `%(asctime)s %(levelname)s %(message)s`). Handlers attached this way are detached and closed when the view is disposed. If constructing `GuiLogHandler(view)` manually, add/remove/close it through the standard logging API yourself. Formatting happens on the emitting thread, and insertion happens on the GUI thread.

Global stdout/stderr are not redirected. This avoids capturing unrelated libraries or creating recursive logging loops. For existing print-heavy functions, pass `output.print` as a writer callback. Standard logging is usually better for levels, timestamps, and structured routing.

## Form and Command

[Form guide](forms.md) describes `Form`, `FormField`, `FormValidationError`, field methods, and submission. [Command guide](commands.md) describes `Command(app, function, prepare=None, background=True, on_result=None, on_error=None, on_done=None)`, its Future/busy policy, and pool behavior.
