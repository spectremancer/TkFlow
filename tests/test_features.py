"""Behavioral tests for the full development toolkit, using real Tk widgets."""
from datetime import date
import threading
import subprocess
import sys
from pathlib import Path
import time
import unittest
from unittest.mock import patch

from TkFlow import (App, Button, Checkbox, Collapsible, Component, DateInput, Dialog, Dropdown,
                    FilePicker, Form, Grid, InputDialog, Label, ListView, NumericInput,
                    ProgressBar, RadioGroup, ScreenStack, ScrollColumn, Slider, SplitPane,
                    State, Table, Tabs, TextArea, TextInput, Theme)
from TkFlow.devtools import capture_errors, inspect_tree, invoke, pump_until


class FeatureTests(unittest.TestCase):
    def setUp(self):
        self.app = App(height=600, width=900)
        self.errors = []
        self.app.root.report_callback_exception = lambda kind, error, tb: self.errors.append(error)

    def tearDown(self):
        self.app.close()
        self.assertEqual(self.errors, [], "Unexpected GUI callback errors")

    def pump(self, predicate):
        pump_until(self.app, predicate)

    def test_state_subscriptions_equality_update_and_thread_guard(self):
        state = State(1)
        calls = []
        unsubscribe = state.subscribe(calls.append)
        state.set(1).update(lambda value: value + 2)
        unsubscribe()
        state.set(4)
        self.assertEqual(calls, [1, 3])
        future = self.app.run_in_thread(lambda: state.set(5), on_error=lambda error: None)
        self.pump(future.done)
        self.assertIsInstance(future.exception(), RuntimeError)
        self.app.call_soon(state.set, 6)
        self.pump(lambda: state.get() == 6)

    def test_state_two_way_controls_and_disposal(self):
        value = State("Ada")
        input = TextInput(self.app, bind=value)
        label = Label(self.app, bind=value)
        self.assertEqual(input.get(), "Ada")
        input.widget.delete(0, "end")
        input.widget.insert(0, "Grace")
        self.assertEqual(value.get(), "Grace")
        self.assertEqual(label.get(), "Grace")
        value.set("Margaret")
        self.assertEqual(input.get(), "Margaret")
        input.destroy()
        label.destroy()
        self.assertEqual(len(value._subscribers), 0)
        value.set("Safe after disposal")

    def test_checkbox_dropdown_and_enabled_state(self):
        checked = State(False)
        check = Checkbox(self.app, "Enable", bind=checked)
        button = Button(self.app, "Action").bind_enabled(checked)
        self.assertTrue(button.widget.instate(["disabled"]))
        check.widget.invoke()
        self.assertTrue(checked.get())
        self.assertTrue(button.widget.instate(["!disabled"]))
        choice = State("B")
        dropdown = Dropdown(self.app, ["A", "B"], bind=choice)
        self.assertEqual(dropdown.get(), "B")
        dropdown.set("A")
        self.assertEqual(choice.get(), "A")

    def test_multiline_state_binding_and_form_dirty_tracking(self):
        value = State("initial")
        form = Form(self.app)
        area = form.add_multiline("notes", "Notes", bind=value, height=3)
        self.app.root.update()
        form.mark_clean()
        area.text.insert("end", " edited")
        self.pump(lambda: value.get() == "initial edited" and form.dirty.get())
        value.set("from model")
        self.assertEqual(area.get(), "from model")
        form.destroy()
        self.assertEqual(len(value._subscribers), 0)

    def test_owner_timers_callbacks_and_cleanup(self):
        panel = self.app.section()
        calls = []
        safe = panel.safe(calls.append)
        panel.after(1, calls.append, "timer")
        panel.on_dispose(lambda: calls.append("disposed"))
        panel.destroy()
        safe("late")
        self.app.root.update()
        self.assertEqual(calls, ["disposed"])

    def test_command_busy_buttons_and_progress(self):
        entered, gate = threading.Event(), threading.Event()
        self.addCleanup(gate.set)
        reports, results = [], []
        def work(context):
            for value in range(100):
                context.report(value)
            entered.set()
            gate.wait(2)
            return "done"
        action = self.app.command(work, context=True, on_progress=reports.append, on_result=results.append)
        first = Button(self.app, "Run", action, busy_text="Running…")
        second = Button(self.app, "Shared", action)
        first.invoke()
        self.assertTrue(entered.wait(1))
        self.assertEqual(first.get(), "Running…")
        self.assertTrue(second.widget.instate(["disabled"]))
        self.pump(lambda: bool(reports))
        self.assertEqual(reports, [99])
        self.assertEqual(action.progress.get(), 99)
        gate.set()
        self.pump(lambda: not action.running)
        self.assertEqual(first.get(), "Run")
        self.assertTrue(second.widget.instate(["!disabled"]))
        self.assertEqual(results, ["done"])

    def test_context_cancellation_and_owner_lifetime(self):
        panel = self.app.section()
        entered = threading.Event()
        delivered = []
        def work(context):
            entered.set()
            context.cancel_event.wait(2)
            return context.cancelled
        action = self.app.command(work, context=True, owner=panel, on_result=delivered.append)
        future = action()
        self.assertTrue(entered.wait(1))
        panel.destroy()
        self.pump(future.done)
        self.assertTrue(future.result())
        self.assertEqual(delivered, [])
        self.assertNotIn(action.cancel, self.app._cleanups)

    def test_command_debounce_uses_latest_arguments_and_cancels(self):
        calls = []
        action = self.app.command(calls.append, background=False, debounce_ms=20)
        action("a")
        action("ab")
        action("abc")
        self.pump(lambda: bool(calls))
        self.assertEqual(calls, ["abc"])
        action("cancelled")
        action.cancel()
        self.app.root.update()
        self.assertEqual(calls, ["abc"])

    def test_grid_spans_automatic_positions_and_released_cells(self):
        grid = Grid(self.app, columns=2)
        wide = grid.cell(0, 0, colspan=2)
        first = Label(grid, "First", expand=True)
        second = Label(grid, "Second", expand=True)
        self.assertEqual(first.widget.grid_info()["row"], 1)
        self.assertEqual(second.widget.grid_info()["column"], 1)
        first.hide()
        self.assertEqual(grid.widget.rowconfigure(1)["weight"], 1)
        with self.assertRaisesRegex(ValueError, "overlaps"):
            grid.cell(0, 1)
        wide.destroy()
        replacement = grid.cell(0, 0, colspan=2)
        self.assertEqual(replacement.widget.grid_info()["columnspan"], 2)

    def test_tabs_and_split_panes(self):
        tabs = Tabs(self.app)
        first, second = tabs.add("one"), tabs.add("two")
        Label(first, "First")
        tabs.select("two")
        self.assertEqual(tabs.widget.select(), str(second.widget))
        second.hide().show()
        tabs.remove("two")
        self.assertTrue(second._destroyed)
        split = SplitPane(self.app)
        left, right = split.add("left"), split.add("right")
        self.assertEqual(len(split.widget.panes()), 2)
        right.hide()
        self.assertEqual(len(split.widget.panes()), 1)
        right.show()
        self.assertEqual(len(split.widget.panes()), 2)

    def test_scroll_and_collapsible(self):
        scroll = ScrollColumn(self.app, expand=True, fill="both", height=100)
        for index in range(20):
            Label(scroll.content, f"Line {index}", padding=12)
        self.app.root.update()
        self.assertGreater(scroll.canvas.bbox("all")[3], scroll.canvas.winfo_height())
        group = Collapsible(scroll.content, "Details", collapsed=True)
        Label(group.content, "Text")
        self.assertEqual(group.content.widget.winfo_manager(), "")
        group.header.invoke()
        self.assertEqual(group.content.widget.winfo_manager(), "grid")

    def test_numeric_and_date_validation(self):
        value = State(3)
        number = NumericInput(self.app, minimum=1, maximum=10, integer=True, bind=value)
        number.set(5)
        self.assertEqual(value.get(), 5)
        for invalid in (0, 11, 2.2, float("nan")):
            with self.assertRaises(ValueError):
                number.set(invalid)
            self.assertEqual(number.get(), 5)
        number.widget.delete(0, "end")
        with self.assertRaises(ValueError):
            number.get()
        self.assertEqual(value.get(), 5)
        dates = []
        date_input = DateInput(self.app, value="2026-10-20", on_change=dates.append)
        self.assertEqual(date_input.get(), date(2026, 10, 20))
        with self.assertRaises(ValueError):
            date_input.set("2026-02-30")
        date_input.widget.delete(0, "end")
        self.assertEqual(dates, [])
        date_input.widget.insert(0, "2026-10-21")
        self.assertEqual(dates, [date(2026, 10, 21)])

    def test_radio_slider_progress_and_picker(self):
        radio = RadioGroup(self.app, ["A", "B"])
        radio.set("B").disable().enable()
        self.assertEqual(radio.get(), "B")
        with self.assertRaises(ValueError):
            radio.set("C")
        amount = State(30.0)
        slider = Slider(self.app, bind=amount)
        slider.set(60)
        self.assertEqual(amount.get(), 60)
        progress = ProgressBar(self.app, bind=amount)
        self.assertEqual(progress.get(), 60)
        progress.start().stop()
        picker = FilePicker(self.app, mode="directory")
        with patch("TkFlow.file_picker.filedialog.askdirectory", return_value="/tmp/project") as choose:
            picker.browse()
            self.assertEqual(picker.get(), "/tmp/project")
            choose.assert_called_once_with(parent=self.app.root, title="Choose a path")
        with patch("TkFlow.file_picker.filedialog.askdirectory", return_value=""):
            picker.browse()
            self.assertEqual(picker.get(), "/tmp/project")

    def test_table_sort_filter_selection_and_update(self):
        table = Table(self.app, {"name":"Name", "count":"Count"},
                      [{"id":1,"name":"Ada","count":10}, {"id":2,"name":"Grace","count":2}], key="id")
        table.select(1).sort("count")
        self.assertEqual([row["id"] for row in table.rows()], [2, 1])
        self.assertEqual(table.selected()[0]["name"], "Ada")
        table.filter("grace")
        self.assertEqual([row["id"] for row in table.rows()], [2])
        table.filter(None).update_row(1, count=1)
        self.assertEqual(table.rows()[0]["id"], 1)
        with self.assertRaises(ValueError):
            table.set_rows([{"id":1}, {"id":1}])
        self.assertEqual(len(table.rows()), 2)
        with self.assertRaises(ValueError):
            table.update_row(1, id=99)

    def test_list_selection_and_model_copies(self):
        items = ListView(self.app, ["Alpha", "Beta"])
        items.select(1)
        self.assertEqual(items.get(), ["Beta"])
        table = Table(self.app, ["name"], [{"name":"Original"}])
        rows = table.rows()
        rows[0]["name"] = "Changed"
        self.assertEqual(table.rows()[0]["name"], "Original")

    def test_components_and_navigation_hooks(self):
        events = []
        class Page(Component):
            def build(self):
                Label(self, "Reusable page")
            def on_show(self):
                events.append("show")
            def on_hide(self):
                events.append("hide")
        stack = ScreenStack(self.app)
        first = stack.add("first", Page)
        second = stack.add("second", Page)
        stack.show_screen("second")
        self.assertEqual(events, ["show", "hide", "show"])
        self.assertEqual(first.widget.winfo_manager(), "")
        stack.back()
        self.assertEqual(stack.current, "first")
        stack.remove("first")
        self.assertTrue(first._destroyed)
        self.assertEqual(stack.current, "second")

    def test_form_schema_groups_conversion_conditions_and_cross_validation(self):
        form = Form(self.app, fields=[{"name":"contact", "label":"Contact", "type":"checkbox"}])
        form.group("account", "Account")
        form.add_text("count", "Count", value="4", converter=int, group="account")
        form.add_text("email", "Email", required=True, visible_when=lambda values: values["contact"])
        form.add_number("minimum", "Minimum", value=1)
        form.add_number("maximum", "Maximum", value=5)
        form.validators = (lambda values: {"maximum":"Must exceed minimum"} if values["maximum"] < values["minimum"] else None,)
        snapshot = form.snapshot()
        self.assertEqual(snapshot["count"], 4)
        self.assertNotIn("email", snapshot)
        form.set({"contact":True})
        self.assertIn("email", form.validate())
        form.set({"contact":False,"minimum":6})
        self.assertIn("maximum", form.validate())
        self.assertTrue(form.dirty.get())
        form.reset()
        self.assertFalse(form.dirty.get())

    def test_form_live_validation_typed_fields_and_clean_baseline(self):
        form = Form(self.app, live_validation=True)
        field = form.add_text("name", "Name", required=True)
        form.add_date("date", "Date", value=date(2026, 10, 20))
        form.add_radio("role", "Role", values=["A", "B"])
        form.add_file("path", "Path")
        field.set("Ada")
        self.assertTrue(form.dirty.get())
        form.mark_clean()
        self.assertFalse(form.dirty.get())
        field.set("")
        self.assertIn("name", form.errors)
        self.assertEqual(form.fields["date"].control.get(), date(2026, 10, 20))

    def test_dialog_resolve_cancel_and_notification_expiry(self):
        dialog = InputDialog(self.app, "Name?", value="Ada", modal=False)
        results = []
        dialog.then(results.append)
        dialog.submit.invoke()
        self.pump(lambda: bool(results))
        self.assertEqual(results, ["Ada"])
        cancelled = Dialog(self.app, modal=False)
        cancelled.close()
        self.assertIsNone(cancelled.future.result())
        notification = self.app.notify("Saved", duration=10)
        self.pump(lambda: notification._destroyed)

    def test_app_shutdown_resolves_open_dialog(self):
        dialog = Dialog(self.app, modal=False)
        self.app.close()
        self.assertIsNone(dialog.future.result(timeout=1))

    def test_shortcut_removal_focus_and_developer_tools(self):
        panel = self.app.section()
        button = Button(panel, "Go", lambda: calls.append(True))
        calls = []
        remove = self.app.shortcut("<Control-k>", button.invoke, owner=panel)
        self.app.root.update()
        self.app.root.focus_force()
        button.focus()
        self.app.root.event_generate("<Control-k>")
        self.app.root.update()
        self.assertEqual(calls, [True])
        remove()
        self.app.root.event_generate("<Control-k>")
        self.app.root.update()
        self.assertEqual(calls, [True])
        self.assertEqual(inspect_tree(self.app)["children"][0]["type"], "Section")
        invoke(button)
        self.assertEqual(len(calls), 2)
        with capture_errors(self.app) as errors:
            self.app.call_soon(lambda: 1/0)
            self.pump(lambda: bool(errors))
        self.assertIsInstance(errors[0], ZeroDivisionError)

    def test_explicit_focus_order_default_and_cancel_buttons(self):
        calls = []
        first = TextInput(self.app)
        second = TextInput(self.app)
        default = Button(self.app, "Accept", lambda: calls.append("accept"))
        cancel = Button(self.app, "Cancel", lambda: calls.append("cancel"))
        self.app.focus_order(first, second, default)
        self.app.set_default_button(default)
        self.app.set_cancel_button(cancel)
        self.app.root.update()
        self.app.root.focus_force()
        first.focus()
        first.widget.event_generate("<Tab>")
        self.app.root.update()
        self.assertEqual(self.app.root.focus_get(), second.widget)
        second.widget.event_generate("<Return>")
        second.widget.event_generate("<Escape>")
        self.app.root.update()
        self.assertEqual(calls, ["accept", "cancel"])
        first.destroy()
        self.assertFalse(second.widget.bind("<Tab>"))

    def test_theme_semantic_styles(self):
        theme = Theme(font_size=11)
        theme.apply(self.app)
        button = Button(self.app, "Save", style="Primary.TButton")
        self.assertEqual(button.widget.cget("style"), "Primary.TButton")
        self.assertEqual(self.app.style.lookup("Primary.TButton", "background"), theme.accent)


class ShowcaseTests(unittest.TestCase):
    def test_workbench_pages_and_tasks(self):
        from examples.workbench import build_app
        app = build_app()
        self.addCleanup(app.close)
        with capture_errors(app) as errors:
            for name in app.demo.pages:
                app.demo.stack.show_screen(name)
                app.root.update()
            self.assertEqual(app.demo.stack.current, "Controls")
            self.assertEqual(len(app.demo.table.rows()), 4)
            app.demo.search.set("Grace")
            pump_until(app, lambda: len(app.demo.table.rows()) == 1 and app.demo.table.rows()[0]["name"] == "Grace Hopper")
            app.demo.search.set("")
            pump_until(app, lambda: len(app.demo.table.rows()) == 4)
            app.demo.table.filter("Ada")
            self.assertEqual(len(app.demo.table.rows()), 1)
            self.assertEqual(app.demo.form.snapshot()["workers"], 4)
            app.demo.task()
            pump_until(app, lambda: not app.demo.task.running)
            self.assertEqual(app.demo.progress.get(), 100)
            pump_until(app, lambda: "20/20" in app.demo.output.get())
            self.assertEqual(errors, [])

    def test_form_inputs_are_not_obscured_by_canvas(self):
        from examples.workbench import build_app
        app = build_app()
        self.addCleanup(app.close)
        app.demo.stack.show_screen("Forms")
        app.root.update()
        entry = app.demo.form.fields["name"].control.widget
        topmost = app.root.winfo_containing(entry.winfo_rootx() + 8, entry.winfo_rooty() + 8)
        self.assertEqual(topmost, entry)

    def test_scroll_content_is_parented_to_its_clipping_canvas(self):
        from examples.workbench import build_app
        app = build_app()
        self.addCleanup(app.close)
        app.demo.stack.show_screen("Forms")
        app.set_size(height=620, width=820)
        form = app.demo.form
        form.set({"name":"", "email":"invalid"})
        form.validate()
        app.root.update()
        self.assertEqual(form.body.widget.master, form.canvas)
        self.assertGreater(form.canvas.bbox("all")[3], form.canvas.winfo_height())
        submit = form.actions._children[0].widget
        topmost = app.root.winfo_containing(submit.winfo_rootx() + 8, submit.winfo_rooty() + 8)
        self.assertEqual(topmost, submit)

    def test_compact_grid_buttons_fit_inside_cards(self):
        from examples.layout_gallery import build_app
        app = build_app()
        self.addCleanup(app.close)
        app.set_size(height=500, width=720)
        app.root.update()
        for card in app.demo.grid._children:
            for child in card._children:
                if isinstance(child, Button):
                    self.assertLessEqual(child.widget.winfo_rooty() + child.widget.winfo_height(),
                                         card.widget.winfo_rooty() + card.widget.winfo_height())

    def test_worker_gc_cannot_finalize_tcl_on_wrong_thread(self):
        script = """
import gc
import threading
from TkFlow import App, TextInput, FilePicker, Form
for index in range(12):
    app = App()
    TextInput(app, 'temporary')
    form = Form(app)
    form.add_file('path', 'Path')
    app.close()
    del form, app
    worker = threading.Thread(target=gc.collect)
    worker.start()
    worker.join(timeout=2)
app = App()
app.close()
print('GUI finalization stayed safe')
"""
        result = subprocess.run([sys.executable, "-E", "-S", "-c", script],
                                cwd=Path(__file__).resolve().parents[1], text=True,
                                capture_output=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")
        self.assertIn("GUI finalization stayed safe", result.stdout)

    def test_gallery_pages(self):
        from examples.layout_gallery import build_app
        app = build_app()
        self.addCleanup(app.close)
        with capture_errors(app) as errors:
            for name in app.demo.tabs.pages:
                app.demo.tabs.select(name)
                app.root.update()
            self.assertGreater(app.demo.scroll.canvas.bbox("all")[3], app.demo.scroll.canvas.winfo_height())
            self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
