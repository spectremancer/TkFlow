# Building forms

`Form` is a Section with a scrolling field body and a separate action row. There is no fixed field count; add fields in a loop or after the interface starts. A scrollbar keeps large forms usable without forcing the window to grow. Action buttons remain outside the scrolling region.

```python
from TkFlow import App, Form, Label

app = App("Account", height=560, width=640)
form = Form(app, "Create account", expand=True, fill="both")
form.add_label("Tell us about yourself.")
form.add_text("name", "Full name", required=True)
form.add_text("email", "Email", required=True,
              validator=lambda text: None if "@" in text else "Include an @")
form.add_dropdown("role", "Role", ["Developer", "Designer", "Other"])
form.add_checkbox("updates", "Receive updates", value=True)
status = Label(app, "Ready")


def save(values):
    # Worker receives plain data; no widget access here.
    return f"Saved {values['name']} ({values['role']})"


form.add_submit("Save", save, on_result=status.set,
                on_error=lambda error: status.set(str(error)))
form.add_button("Reset", form.reset)
app.run()
```

## Fields and layout

`Form(parent, title="", scrollable=True, **section_options)` accepts Section's title, padding, spacing, styling, and placement options. The Form itself uses a vertical layout; the field body and action row occupy fixed rows. For a small form that should use its full natural height, set `scrollable=False`. For larger forms, use `expand=True, fill="both"` and set an appropriate app size.

The field methods return the actual control, so native options and bindings are available:

```python
password = form.add_text("password", "Password", show="*", width=30)
password.bind("<Return>", lambda event: submit.invoke())
```

Supported field creation:

- `add_text(name, label, value="", required=False, validator=None, **text_input_options)`
- `add_dropdown(name, label, values, value=None, required=False, validator=None, **dropdown_options)`
- `add_checkbox(name, label, value=False, required=False, validator=None, **checkbox_options)`
- `add_label(text, **label_options)` adds explanatory text; it has no value in the snapshot.

Names must be nonempty strings and unique within a form. Names are dictionary keys; labels are presentation text. A dropdown's default is its initial selected choice, including the automatic first choice. Removing and adding fields does not change other names.

```python
for key, caption in [("team", "Team"), ("office", "Office"), ("city", "City")]:
    form.add_text(key, caption)

form.remove("office")
form.add_text("office", "Office", value="Remote")
```

`form.fields[name]` is a `FormField` containing `control`, `label`, `row`, `error_label`, `default`, `required`, and `validator`. For conditional fields, use `form.fields[name].row.hide()` / `.show()`. **Hidden fields still participate in get, reset, and validation.** Update requirements/validators yourself, or remove the field if it should not be part of submitted data.

`form.body` is the field container. Additional decorative controls may be added there, but only named field methods register values. `form.actions` is the button row. In a scrollable form, leave the canvas-managed body's geometry alone. Use the scrollbar to navigate; this iteration does not install global mouse-wheel or automatic focus-scrolling hooks.

## Getting and setting values

- `get()` returns a new `dict` with all current values, without validation.
- `set({name: value, ...})` updates specified fields and leaves others alone. Unknown names raise `KeyError`. Values follow each control's normal rules. Updates are sequential, not transactional; validate a bulk payload yourself if you need all-or-nothing behavior.
- `reset()` restores initial defaults and clears error messages.
- `remove(name)` destroys that field's row and removes its value/error entry.

Text values are strings, checkbox values are bools, and dropdown values are strings. Each snapshot dictionary is independent; current built-in field values are immutable primitives, so subsequent edits cannot alter the captured data.

## Validation

`validate()` returns a new `dict[name, message]`, updates `form.errors`, and shows an inline error below each invalid field. An empty dictionary means valid.

A required text field rejects empty/whitespace-only strings. A required checkbox must be checked. A required dropdown must have a nonempty value. Validators receive the current value and return `None` (or an empty string) for valid input, or an error string. A required-field failure takes precedence over a custom validator. A validator that returns a non-string/non-None value raises `TypeError`; exceptions in validators propagate as application errors.

Keep validators fast: they run on the GUI thread. Network validation belongs in the worker after local validation.

`snapshot()` validates and returns the current value dictionary, or raises `FormValidationError`. The exception exposes `.errors` with a copy of field messages. `get()` intentionally does not raise validation errors.

## Submission and custom buttons

`add_submit(text, command, background=True, on_result=None, on_error=None, **button_options)` creates a Button backed by Command:

1. Capture and validate values on the GUI thread.
2. Call `command(values)` in the worker pool by default.
3. Deliver the result or error to the GUI thread.

Invalid data never reaches the worker. Inline messages are always updated. If `on_error` is provided it also receives validation errors; otherwise validation errors remain inline and unexpected worker errors go to Tk's error reporting. Result/error handlers are suppressed after the Form is destroyed.

The returned Button exposes `.command`, the reusable Command instance. Repeated submissions of the same button while it is busy share the current Future. Fields remain editable during work, and callbacks see the original captured values. `.command.running` and `.command.cancel()` allow inspection and cancellation of queued work. To show a busy state, manage the button in your own prepare/result/error handlers using an explicit Command, or display progress in a Label/LogView. The helper suppresses duplicate work without automatically disabling fields.

`add_button(text, command, **button_options)` adds an ordinary action to the action row. Its callback takes no arguments and is synchronous unless you pass a Command or `background=True`. Use it for reset, adding more fields, or opening a help window. Each separately created submit button has its own Command; share an explicit Command if different actions must share one busy policy.
