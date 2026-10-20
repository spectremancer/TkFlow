"""Composable, dynamically sized forms built out of Sections and controls."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Callable
import tkinter as tk
from tkinter import ttk
from .section import Section
from .label import Label
from .text_input import TextInput
from .dropdown import Dropdown
from .checkbox import Checkbox
from .button import Button
from .command import Command
from ._helpers import _callback
from .state import State


@dataclass
class FormField:
    """Public handles for a field's control, label, row, and validation message."""
    control: Any
    label: Label
    row: Section
    error_label: Label
    default: Any
    required: bool = False
    validator: Callable | None = None
    converter: Callable | None = None
    visible_when: Callable | None = None
    active: bool = True


class FormValidationError(ValueError):
    def __init__(self, errors: dict[str, str]):
        self.errors = errors
        super().__init__("; ".join(f"{key}: {message}" for key, message in errors.items()))


class Form(Section):
    """Add named fields, collect values, validate, reset, and submit a snapshot.

    Validators return None for valid values, or a human-readable error string.
    There is no fixed field count. Field rows can be hidden, shown, or removed.
    """

    def __init__(self, parent, title="", *, scrollable=True, fields=None, live_validation=False,
                 validators=(), **options):
        if options.pop("orientation", "vertical") != "vertical":
            raise ValueError("Form uses a vertical layout; use rows inside its body for custom content")
        super().__init__(parent, title=title, **options)
        self.fields: dict[str, FormField] = {}
        self.errors: dict[str, str] = {}
        self.groups = {}
        self.dirty = State(False)
        self._baseline = {}
        self.live_validation = live_validation
        self.validators = tuple(validators)
        if scrollable:
            self.canvas = tk.Canvas(self.widget, highlightthickness=0, height=240, width=300,
                                    background=self.app.root.cget("background"))
        self.body = self.column(padding=0, expand=True, fill="both",
                                _master=self.canvas if scrollable else None)
        if scrollable:
            scrollbar = ttk.Scrollbar(self.widget, orient="vertical", command=self.canvas.yview)
            self.canvas.configure(yscrollcommand=scrollbar.set)
            self.body.widget.grid_forget()
            item = self.canvas.create_window(0, 0, window=self.body.widget, anchor="nw")
            self.canvas.grid(row=0, column=0, sticky="nsew")
            scrollbar.grid(row=0, column=1, sticky="ns")
            self.body.widget.bind("<Configure>", lambda event: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
            self.canvas.bind("<Configure>", lambda event: self.canvas.itemconfigure(item, width=event.width))
        self.actions = self.row(padding=0)
        self.summary = Label(self, "", style="Error.TLabel", wraplength=550)
        self.summary.hide()
        for specification in fields or ():
            self.add_from_schema(specification)

    def _add(self, name, label, factory, default, *, required=False, validator=None,
             converter=None, visible_when=None, group=None):
        self._check()
        if not isinstance(name, str) or not name:
            raise ValueError("Field name must be a nonempty string")
        if name in self.fields:
            raise ValueError(f"Field {name!r} already exists")
        _callback(validator, "validator")
        row = Section(self.groups[group] if group else self.body, padding=0, spacing=3)
        label_widget = Label(row, label)
        try:
            control = factory(row)
        except Exception:
            row.destroy()
            raise
        error = Label(row, "", foreground="#b42318")
        error.hide()
        field = FormField(control, label_widget, row, error, default, required, validator, converter, visible_when)
        self.fields[name] = field
        self._baseline[name] = control.get()
        def changed(*args):
            self._changed()
        if hasattr(control, "variable"):
            trace = control.variable.trace_add("write", changed)
            control.on_dispose(lambda: control.variable.trace_remove("write", trace))
        elif hasattr(control, "text"):
            def edited(event):
                if control.text.edit_modified():
                    control.text.edit_modified(False)
                changed()
            control.bind("<<Modified>>", edited)
        self._refresh_visibility()
        return control

    def add_label(self, text: str, **options: Any) -> Label:
        """Add explanatory text without adding a value to the form snapshot."""
        self._check()
        return Label(self.body, text, **options)

    def add_text(self, name: str, label: str, value: str = "", *, required: bool = False,
                 validator: Callable | None = None, **options: Any) -> TextInput:
        field_options = self._field_options(options)
        return self._add(name, label, lambda row: TextInput(row, value, **options), value,
                         required=required, validator=validator, **field_options)

    def add_dropdown(self, name: str, label: str, values, value: str | None = None, *,
                     required: bool = False, validator: Callable | None = None, **options: Any) -> Dropdown:
        field_options = self._field_options(options)
        choices = tuple(values) if not isinstance(values, str) else values
        default = value if value is not None else (choices[0] if choices else "")
        return self._add(name, label, lambda row: Dropdown(row, choices, value, **options), default,
                         required=required, validator=validator, **field_options)

    def add_checkbox(self, name: str, label: str, value: bool = False, *, required: bool = False,
                     validator: Callable | None = None, **options: Any) -> Checkbox:
        field_options = self._field_options(options)
        return self._add(name, label, lambda row: Checkbox(row, value=value, **options), value,
                         required=required, validator=validator, **field_options)

    def get(self) -> dict[str, Any]:
        self._check()
        return {name: field.control.get() for name, field in self.fields.items()}

    def set(self, values: dict[str, Any]) -> Form:
        self._check()
        unknown = values.keys() - self.fields.keys()
        if unknown:
            raise KeyError(f"Unknown form fields: {sorted(unknown)}")
        for name, value in values.items():
            self.fields[name].control.set(value)
        return self

    @staticmethod
    def _field_options(options):
        return {name: options.pop(name) for name in ("converter", "visible_when", "group") if name in options}

    def group(self, name, title):
        self._check()
        if name in self.groups:
            raise ValueError("Group already exists")
        self.groups[name] = Section(self.body, title)
        return self.groups[name]

    def add_field(self, name, label, factory, *, value=None, **options):
        return self._add(name, label, factory, value, **options)

    def add_from_schema(self, specification):
        specification = dict(specification)
        kind = specification.pop("type", "text")
        methods = {"text": self.add_text, "dropdown": self.add_dropdown, "checkbox": self.add_checkbox,
                   "number": self.add_number, "date": self.add_date, "multiline": self.add_multiline,
                   "radio": self.add_radio, "file": self.add_file}
        if kind not in methods:
            raise ValueError(f"Unknown field type {kind!r}")
        return methods[kind](**specification)

    def _special(self, name, label, factory, options):
        field_options = self._field_options(options)
        for key in ("required", "validator"):
            if key in options:
                field_options[key] = options.pop(key)
        control = self._add(name, label, lambda row: factory(row, **options), None, **field_options)
        self.fields[name].default = control.get()
        return control

    def add_number(self, name, label, **options):
        from .numeric_input import NumericInput
        return self._special(name, label, NumericInput, options)

    def add_date(self, name, label, **options):
        from .date_input import DateInput
        return self._special(name, label, DateInput, options)

    def add_multiline(self, name, label, **options):
        from .text_area import TextArea
        return self._special(name, label, TextArea, options)

    def add_radio(self, name, label, **options):
        from .radio_group import RadioGroup
        return self._special(name, label, RadioGroup, options)

    def add_file(self, name, label, **options):
        from .file_picker import FilePicker
        return self._special(name, label, FilePicker, options)

    def _raw(self):
        values = {}
        for name, field in self.fields.items():
            try:
                values[name] = field.control.get()
            except (ValueError, TypeError, tk.TclError):
                values[name] = None
        return values

    def _refresh_visibility(self):
        values = self._raw()
        for field in self.fields.values():
            field.active = bool(field.visible_when(values)) if field.visible_when else True
            field.row.show() if field.active else field.row.hide()

    def _changed(self):
        if self._destroyed:
            return
        self._refresh_visibility()
        self.dirty.set(self._raw() != self._baseline)
        if self.live_validation:
            self.validate()

    def mark_clean(self):
        self._check()
        self._baseline = self._raw()
        self.dirty.set(False)
        return self

    def validate(self) -> dict[str, str]:
        self._check()
        self._refresh_visibility()
        errors, values = {}, {}
        for name, field in self.fields.items():
            message = None
            if field.active:
                try:
                    value = field.control.get()
                    if field.required and (value is False or value is None or isinstance(value, str) and not value.strip()):
                        message = "This field is required"
                    else:
                        if field.converter is not None and value != "" and value is not None:
                            value = field.converter(value)
                        if field.validator is not None:
                            message = field.validator(value)
                            if message is not None and not isinstance(message, str):
                                raise TypeError("Validators must return None or an error string")
                    values[name] = value
                except ValueError as error:
                    message = str(error) or "Invalid value"
            if message:
                errors[name] = message
                field.error_label.set(message).show()
            else:
                field.error_label.set("").hide()
        if not errors:
            for validator in self.validators:
                messages = validator(dict(values))
                if messages is not None:
                    if not isinstance(messages, dict):
                        raise TypeError("Form validators return a dictionary of messages or None")
                    errors.update(messages)
        for name, message in errors.items():
            if name in self.fields:
                self.fields[name].error_label.set(message).show()
        general = errors.get("__form__", "")
        self.summary.set(general)
        self.summary.show() if general else self.summary.hide()
        self.errors, self._validated_values = errors, values
        return dict(errors)

    def snapshot(self) -> dict[str, Any]:
        if self.validate():
            raise FormValidationError(dict(self.errors))
        return dict(self._validated_values)

    def reset(self) -> Form:
        self.set({name: field.default for name, field in self.fields.items()})
        self.errors = {}
        for field in self.fields.values():
            field.error_label.set("").hide()
        self.summary.hide()
        self.mark_clean()
        return self

    def remove(self, name: str) -> None:
        self._check()
        field = self.fields.pop(name)
        field.row.destroy()
        self.errors.pop(name, None)
        self._baseline.pop(name, None)
        self._changed()

    def add_button(self, text: str, command: Callable, **options: Any) -> Button:
        self._check()
        return Button(self.actions, text, command, **options)

    def add_submit(self, text: str, command: Callable, *, background: bool = True,
                   on_result: Callable | None = None, on_error: Callable | None = None,
                   **options: Any) -> Button:
        """Validate/capture on GUI thread; command(values) uses the pool by default."""
        def result(value):
            if not self._destroyed and on_result is not None:
                on_result(value)

        def error(exception):
            if self._destroyed:
                return
            if on_error is not None:
                on_error(exception)
            elif not isinstance(exception, FormValidationError):
                self.app._report_error(exception)

        action = Command(self.app, command, prepare=lambda: (self.snapshot(),),
                         background=background, on_result=result, on_error=error, owner=self)
        options.setdefault("busy_text", "Working...")
        button = self.add_button(text, action, **options)
        button.command = action
        return button
