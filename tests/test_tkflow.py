"""Integration tests exercise real Tk widgets; run under Xvfb on headless Linux."""
import threading
import time
import unittest
import runpy
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

from TkFlow import App, Button, Checkbox, Column, Dropdown, Label, Menu, Row, Section, TextInput, Window


class TkFlowTests(unittest.TestCase):
    def setUp(self):
        self.app = App("Test", height=300, width=500)
        self.errors = []
        self.app.root.report_callback_exception = lambda kind, error, tb: self.errors.append(error)

    def tearDown(self):
        self.app.close()
        self.assertEqual(self.errors, [], "Unexpected Tk callback errors")

    def pump_until(self, predicate, timeout=2):
        deadline = time.monotonic() + timeout
        while not predicate() and time.monotonic() < deadline:
            self.app.root.update()
            time.sleep(0.005)
        self.assertTrue(predicate(), "Timed out waiting for GUI delivery")

    def test_window_settings(self):
        self.app.set_title("Updated").set_size(height=240, width=420)
        self.app.set_min_size(height=120, width=180).set_resizable((True, False))
        self.app.root.update()
        self.assertEqual(self.app.root.title(), "Updated")
        self.assertEqual((self.app.root.winfo_height(), self.app.root.winfo_width()), (240, 420))
        self.assertEqual(self.app.root.minsize(), (180, 120))
        self.assertEqual(self.app.root.resizable(), (1, 0))

    def test_nested_layout_and_resize(self):
        section = Section(self.app, "Details", expand=True, fill="both")
        row = Row(section, expand=True, fill="both")
        first = Label(row, "Left")
        column = Column(row, expand=True, fill="both")
        second = Label(column, "Right")
        third = Label(column, "Below")
        self.app.root.update()
        self.assertEqual(first.widget.grid_info()["column"], 0)
        self.assertEqual(column.widget.grid_info()["column"], 1)
        self.assertEqual(third.widget.grid_info()["row"], 1)
        self.assertGreater(third.widget.winfo_y(), second.widget.winfo_y())
        before = section.widget.winfo_width()
        self.app.set_size(height=400, width=700)
        self.app.root.update()
        self.assertGreater(section.widget.winfo_width(), before)

    def test_hide_show_destroy(self):
        section = self.app.section("Content")
        first = TextInput(section, on_change=lambda value: None)
        second = Label(section, "Keep")
        first.hide()
        self.assertEqual(first.widget.winfo_manager(), "")
        first.show()
        self.assertEqual(first.widget.grid_info()["row"], 0)
        first.destroy()
        self.assertIsNone(first.variable._tk)
        replacement = Label(section, "New")
        self.assertNotEqual(replacement.widget.grid_info()["row"], second.widget.grid_info()["row"])
        section.destroy()
        with self.assertRaisesRegex(RuntimeError, "destroyed"):
            second.set("No")

    def test_values_and_customization(self):
        changed = []
        entry = TextInput(self.app, "Initial", on_change=changed.append, width=25, show="*")
        entry.set("Changed")
        self.assertEqual(entry.get(), "Changed")
        self.assertEqual(changed, ["Changed"])
        checkbox = Checkbox(self.app, "Enabled", value=True)
        self.assertIs(checkbox.get(), True)
        checkbox.set(False)
        self.assertIs(checkbox.get(), False)
        dropdown = Dropdown(self.app, ["A", "B"])
        self.assertEqual(dropdown.get(), "A")
        dropdown.set("B")
        self.assertEqual(dropdown.get(), "B")
        dropdown.disable().enable()
        self.assertTrue(dropdown.widget.instate(["readonly", "!disabled"]))
        label = Label(self.app, "Old", anchor="center")
        label.set("New")
        self.assertEqual(label.get(), "New")
        self.assertEqual(str(label.widget.cget("anchor")), "center")

    def test_hidden_and_destroyed_widgets_release_expansion(self):
        section = Section(self.app, expand=True, fill="both")
        label = Label(section, "Expanding", expand=True, fill="both")
        slot = label.widget.grid_info()["row"]
        self.assertEqual(section.widget.rowconfigure(slot)["weight"], 1)
        label.hide()
        self.assertEqual(section.widget.rowconfigure(slot)["weight"], 0)
        label.show()
        self.assertEqual(section.widget.rowconfigure(slot)["weight"], 1)
        label.destroy()
        self.assertEqual(section.widget.rowconfigure(slot)["weight"], 0)

    def test_button_and_disabled_state(self):
        calls, results = [], []
        button = Button(self.app, "Run", command=lambda: calls.append("called") or 42, on_result=results.append)
        button.disable()
        self.assertIsNone(button.invoke())
        button.widget.invoke()
        self.assertEqual(calls, [])
        button.enable()
        self.assertEqual(button.invoke(), 42)
        self.assertEqual((calls, results), (["called"], [42]))

    def test_checkbox_and_dropdown_user_callbacks(self):
        changes = []
        check = Checkbox(self.app, command=changes.append)
        check.widget.invoke()
        self.assertEqual(changes, [True])
        check.set(False)
        self.assertEqual(changes, [True])
        dropdown = Dropdown(self.app, ["A", "B"], on_change=changes.append)
        self.app.root.update()
        dropdown.set("B")
        dropdown.widget.event_generate("<<ComboboxSelected>>")
        self.app.root.update()
        self.assertEqual(changes, [True, "B"])

    def test_menu_structure_and_commands(self):
        calls = []
        menu = Menu(self.app)
        file = menu.dropdown("File")
        index = file.add_command("Open", lambda: calls.append("opened"), accelerator="Ctrl+O")
        file.separator()
        sub = file.dropdown("More")
        sub.add_command("Nested", lambda: calls.append("nested"))
        file.widget.invoke(index)
        sub.widget.invoke(0)
        self.assertEqual(calls, ["opened", "nested"])
        self.assertEqual(menu.widget.entrycget(0, "label"), "File")
        self.assertEqual(file.widget.type(1), "separator")

    def test_background_keeps_event_loop_live_and_delivers_on_main_thread(self):
        gate = threading.Event()
        delivered, ticks = [], []
        main_id = threading.get_ident()
        button = Button(self.app, "Work", background=True,
                        command=lambda: (gate.wait(2), threading.get_ident())[1],
                        on_result=lambda worker_id: delivered.append((worker_id, threading.get_ident())))
        try:
            future = button.invoke()
            self.app.after(0, lambda: ticks.append(True))
            self.pump_until(lambda: bool(ticks))
            self.assertFalse(future.done())
            gate.set()
            self.pump_until(lambda: bool(delivered))
            self.assertNotEqual(delivered[0][0], main_id)
            self.assertEqual(delivered[0][1], main_id)
        finally:
            gate.set()

    def test_background_errors(self):
        errors = []
        def fail():
            raise ValueError("worker failed")
        future = self.app.run_in_thread(fail, on_error=lambda error: errors.append((error, threading.get_ident())))
        self.pump_until(lambda: bool(errors))
        with self.assertRaisesRegex(ValueError, "worker failed"):
            future.result()
        self.assertEqual(errors[0][1], threading.get_ident())

    def test_unhandled_worker_error_uses_tk_reporting(self):
        self.app.run_in_thread(lambda: 1 / 0)
        self.pump_until(lambda: bool(self.errors))
        self.assertIsInstance(self.errors.pop(), ZeroDivisionError)

    def test_menu_background_command(self):
        delivered = []
        file = Menu(self.app).dropdown("Tasks")
        file.add_command("Run", lambda: 7, background=True, on_result=delivered.append)
        file.widget.invoke(0)
        self.pump_until(lambda: bool(delivered))
        self.assertEqual(delivered, [7])

    def test_gui_thread_guard_and_call_soon(self):
        label = Label(self.app, "Before")
        errors = []
        def work():
            try:
                label.set("Unsafe")
            except RuntimeError as error:
                errors.append(error)
            self.app.call_soon(label.set, "Safe")
        future = self.app.run_in_thread(work)
        self.pump_until(lambda: label.get() == "Safe")
        future.result(timeout=1)
        self.assertEqual(len(errors), 1)

    def test_queue_survives_callback_error(self):
        delivered = []
        self.app.call_soon(lambda: 1 / 0)
        self.app.call_soon(delivered.append, "ok")
        self.pump_until(lambda: bool(delivered))
        self.assertIsInstance(self.errors.pop(), ZeroDivisionError)

    def test_closing_suppresses_pending_worker_delivery(self):
        gate = threading.Event()
        delivered = []
        future = self.app.run_in_thread(lambda: gate.wait(2), on_result=delivered.append)
        self.app.close()
        gate.set()
        future.result(timeout=2)
        self.app.call_soon(delivered.append, "late")
        self.assertEqual(delivered, [])
        with self.assertRaisesRegex(RuntimeError, "closed"):
            self.app.run_in_thread(lambda: None)

    def test_additional_window(self):
        window = Window(self.app, "Details", height=200, width=300)
        label = Label(window, "Child")
        self.assertIs(window.app, self.app)
        Menu(window).dropdown("File").add_command("Close", window.close)
        window.close()
        self.assertTrue(window._closed)
        with self.assertRaisesRegex(RuntimeError, "destroyed"):
            label.get()
        self.assertTrue(self.app.root.winfo_exists())

    def test_app_close_disposes_window_children(self):
        window = Window(self.app)
        entry = TextInput(window, on_change=lambda value: None)
        self.app.close()
        self.assertTrue(window._closed)
        self.assertIsNone(entry.variable._tk)

    def test_dialogs_have_parent(self):
        with patch("TkFlow.app.messagebox.showinfo", return_value="ok") as show:
            self.assertEqual(self.app.message("Hello", title="Greeting"), "ok")
            show.assert_called_once_with("Greeting", "Hello", parent=self.app.root)
        with patch("TkFlow.app.messagebox.askyesno", return_value=True) as ask:
            self.assertIs(self.app.confirm("Proceed?"), True)
            ask.assert_called_once_with("Confirm", "Proceed?", parent=self.app.root)

    def test_validation(self):
        with self.assertRaisesRegex(ValueError, "positive integer"):
            self.app.set_size(height=0, width=100)
        with self.assertRaisesRegex(ValueError, "orientation"):
            Section(self.app, orientation="diagonal")
        with self.assertRaisesRegex(ValueError, "spacing"):
            Row(self.app, spacing=-1)
        with self.assertRaisesRegex(ValueError, "fill"):
            Label(self.app, fill="bad")
        with self.assertRaisesRegex(TypeError, "callable"):
            Button(self.app, command="bad")
        with self.assertRaisesRegex(ValueError, "Choose"):
            Dropdown(self.app, ["A"], value="B")
        with self.assertRaisesRegex(TypeError, "sequence"):
            Dropdown(self.app, "ABC")
        with self.assertRaisesRegex(ValueError, "resizable"):
            self.app.set_resizable("yes")

    def test_individual_class_import(self):
        from TkFlow.app import App as ModuleApp
        self.assertIs(ModuleApp, App)

    def test_run_and_after(self):
        called = []
        self.app.after(0, lambda: called.append(True))
        self.app.after(20, self.app.root.quit)
        self.app.run()
        self.assertEqual(called, [True])


class FolderImportTests(unittest.TestCase):
    def check_project(self, folder, import_name):
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            shutil.copytree(Path(__file__).resolve().parents[1] / "TkFlow",
                            project / folder, ignore=shutil.ignore_patterns("__pycache__"))
            child = project / "ui"
            child.mkdir()
            (child / "__init__.py").write_text("")
            (child / "main.py").write_text(
                f"from {import_name} import App, Menu, Button, Label\n"
                f"from {import_name}.app import App as ModuleApp\n"
                "assert ModuleApp is App\n"
                "app = App('Copied folder')\n"
                "try:\n"
                "    section = app.section('Content')\n"
                "    status = Label(section, 'Before')\n"
                "    Button(section, 'Update', lambda: status.set('After')).invoke()\n"
                "    Menu(app).dropdown('File').add_command('Close', app.close)\n"
                "    app.root.update()\n"
                "    assert status.get() == 'After'\n"
                "finally:\n"
                "    app.close()\n"
                "print('Copied folder works')\n"
            )
            # -E ignores PYTHONPATH; -S excludes installed packages. Only the
            # copied project and Python's standard library provide these imports.
            result = subprocess.run([sys.executable, "-E", "-S", "-m", "ui.main"],
                                    cwd=project, capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip(), "Copied folder works")

    def test_child_directory_can_import_copied_folder(self):
        self.check_project("TkFlow", "TkFlow")

    def test_nested_renamed_folder_uses_relative_imports(self):
        self.check_project("utils/gui", "utils.gui")


class ExampleTests(unittest.TestCase):
    def build(self, name):
        module = runpy.run_path(str(Path(__file__).resolve().parents[1] / "examples" / name))
        app = module["build_app"]()
        self.addCleanup(app.close)
        return app

    def test_greeting_example(self):
        app = self.build("greeting.py")
        section = app._children[0]
        name = next(child for child in section._children if isinstance(child, TextInput))
        button = next(child for child in section._children if isinstance(child, Button))
        name.set("Ada")
        button.invoke()
        self.assertTrue(any(isinstance(child, Label) and child.get() == "Hello, Ada!"
                            for child in section._children))

    def test_form_example(self):
        app = self.build("form.py")
        section, status, save = app._children
        name = next(child for child in section._children if isinstance(child, TextInput))
        name.set("Ada")
        save.invoke()
        self.assertTrue(save.widget.instate(["disabled"]))
        self.assertEqual(status.get(), "Saving...")
        deadline = time.monotonic() + 3
        while status.get() == "Saving..." and time.monotonic() < deadline:
            app.root.update()
            time.sleep(0.005)
        self.assertEqual(status.get(), "Saved Ada (Developer), notifications: on")
        self.assertTrue(save.widget.instate(["!disabled"]))


if __name__ == "__main__":
    unittest.main()
