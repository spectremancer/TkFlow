"""Integration checks for bounded jobs, commands, forms, output, and examples."""
import logging
from pathlib import Path
import runpy
import threading
import time
import unittest

from TkFlow import App, Button, Command, Form, FormValidationError, LogView, Menu, TextArea


class ExtendedTests(unittest.TestCase):
    def setUp(self):
        self.app = App(max_workers=2, max_pending=4)
        self.errors = []
        self.app.root.report_callback_exception = lambda kind, error, tb: self.errors.append(error)

    def tearDown(self):
        self.app.close()
        self.assertEqual(self.errors, [])

    def pump(self, condition, timeout=3):
        deadline = time.monotonic() + timeout
        while not condition() and time.monotonic() < deadline:
            self.app.root.update()
            time.sleep(0.005)
        self.assertTrue(condition(), "Timed out waiting for GUI result")

    def test_command_snapshots_on_main_thread_and_suppresses_duplicates(self):
        gate = threading.Event()
        self.addCleanup(gate.set)
        captured, results, done = [], [], []
        main = threading.get_ident()
        def prepare():
            captured.append(threading.get_ident())
            return ("snapshot",)
        def work(value):
            gate.wait(2)
            return value, threading.get_ident()
        action = Command(self.app, work, prepare=prepare, on_result=results.append,
                         on_done=lambda: done.append(threading.get_ident()))
        button = Button(self.app, "Run", action)
        menu = Menu(self.app).dropdown("Jobs")
        menu.add_command("Run", action)
        first = button.invoke()
        menu.widget.invoke(0)
        self.assertIs(action(), first)
        self.assertEqual(captured, [main])
        self.assertTrue(action.running)
        gate.set()
        self.pump(lambda: bool(done))
        self.assertEqual(results[0][0], "snapshot")
        self.assertNotEqual(results[0][1], main)
        self.assertEqual(done, [main])
        self.assertFalse(action.running)

    def test_command_prepare_errors_do_not_start_worker(self):
        calls, errors, done = [], [], []
        action = self.app.command(lambda: calls.append(True), prepare=lambda: "not a tuple",
                                  on_error=errors.append, on_done=lambda: done.append(True))
        self.assertIsNone(action())
        self.assertIsInstance(errors[0], TypeError)
        self.assertEqual(calls, [])
        self.assertFalse(action.running)
        self.assertEqual(done, [True])

    def test_command_worker_error_and_synchronous_mode(self):
        errors = []
        action = self.app.command(lambda: 1 / 0, on_error=errors.append)
        action()
        self.pump(lambda: bool(errors))
        self.assertIsInstance(errors[0], ZeroDivisionError)
        self.assertFalse(action.running)
        values = []
        sync = self.app.command(lambda: threading.get_ident(), background=False, on_result=values.append)
        self.assertEqual(sync(), threading.get_ident())
        self.assertEqual(values, [threading.get_ident()])

    def test_pool_bounds_concurrency_and_rejects_full_queue_without_waiting(self):
        gate = threading.Event()
        started = [threading.Event(), threading.Event()]
        self.addCleanup(gate.set)
        def wait(index):
            started[index].set()
            gate.wait(2)
        first = self.app.run_in_thread(wait, 0)
        second = self.app.run_in_thread(wait, 1)
        self.assertTrue(all(event.wait(1) for event in started))
        pending = [self.app.run_in_thread(lambda: "queued") for _ in range(4)]
        before = time.monotonic()
        with self.assertRaisesRegex(RuntimeError, "queue is full"):
            self.app.run_in_thread(lambda: None)
        self.assertLess(time.monotonic() - before, 0.2)
        self.assertLessEqual(len(self.app._workers._threads), 2)
        self.app.close()
        self.assertTrue(self.app.stop_event.is_set())
        self.assertTrue(all(future.cancelled() for future in pending))
        gate.set()
        first.result(timeout=2)
        second.result(timeout=2)

    def test_queued_command_cancel_resets_running(self):
        gate = threading.Event()
        started = [threading.Event(), threading.Event()]
        self.addCleanup(gate.set)
        def wait(index):
            started[index].set()
            gate.wait(2)
        for i in range(2):
            self.app.run_in_thread(wait, i)
        self.assertTrue(all(event.wait(1) for event in started))
        called = []
        action = self.app.command(lambda: called.append(True))
        action()
        self.assertTrue(action.cancel())
        self.pump(lambda: not action.running)
        self.assertEqual(called, [])

    def test_pool_reuses_daemon_workers(self):
        futures = [self.app.run_in_thread(threading.get_ident) for _ in range(2)]
        self.pump(lambda: all(future.done() for future in futures))
        threads = tuple(self.app._workers._threads)
        for _ in range(3):
            future = self.app.run_in_thread(threading.get_ident)
            self.pump(future.done)
        self.assertEqual(tuple(self.app._workers._threads), threads)
        self.assertTrue(all(thread.daemon for thread in threads))

    def test_text_area_readonly_tags_trimming_and_cleanup(self):
        area = TextArea(self.app, readonly=True, max_lines=3, expand=True, fill="both")
        area.text.tag_configure("notice", foreground="blue")
        area.append("one\ntwo\nthree\nfour\n", tag="notice")
        self.assertEqual(area.get(), "two\nthree\nfour\n")
        self.assertEqual(str(area.text.cget("state")), "disabled")
        self.assertTrue(area.text.tag_ranges("notice"))
        area.clear().set("replacement")
        self.assertEqual(area.get(), "replacement")
        area.hide().show()
        area.destroy()
        with self.assertRaisesRegex(RuntimeError, "destroyed"):
            area.get()

    def test_log_view_batches_worker_messages_and_detaches_handlers(self):
        output = LogView(self.app, poll_ms=5, max_lines=3)
        logger = logging.getLogger(f"test.{id(self)}")
        logger.setLevel(logging.INFO)
        logger.propagate = False
        handler = output.attach_logger(logger, format="%(levelname)s %(message)s")
        def worker():
            logger.info("hello")
            output.print("worker", 42)
        future = self.app.run_in_thread(worker)
        self.pump(lambda: "worker 42" in output.get())
        future.result(timeout=1)
        self.assertIn("INFO hello", output.get())
        output.destroy()
        self.assertNotIn(handler, logger.handlers)
        output.print("ignored after destroy")
        self.assertTrue(output._messages.empty())

    def test_log_queue_overflow_and_bounded_history(self):
        output = LogView(self.app, poll_ms=5, max_pending=2, batch_size=1, max_lines=2)
        for i in range(10):
            output.print(i)
        self.assertEqual(output.dropped_messages, 8)
        self.pump(lambda: "1\n" in output.get())
        output.print("new")
        self.pump(lambda: "new" in output.get())
        self.assertEqual(output.get(), "1\nnew\n")

    def test_log_clear_discards_pending_and_truncates_large_messages(self):
        output = LogView(self.app, poll_ms=5, max_message_chars=5)
        output.write("123456789")
        self.pump(lambda: "truncated" in output.get())
        self.assertIn("12345", output.get())
        self.assertNotIn("6789", output.get())
        output.print("pending")
        output.clear()
        self.assertTrue(output._messages.empty())
        self.assertEqual(output.get(), "")

    def test_concurrent_log_producers_have_exact_overflow_count(self):
        output = LogView(self.app, max_pending=10)
        def produce():
            for _ in range(100):
                output.print("line")
        futures = [self.app.run_in_thread(produce) for _ in range(2)]
        # Deliberately don't pump Tk until producers fill the test buffer.
        for future in futures:
            future.result(timeout=2)
        self.assertEqual(output._messages.qsize(), 10)
        self.assertEqual(output.dropped_messages, 190)

    def test_form_dynamic_fields_values_validation_and_reset(self):
        form = Form(self.app, "Settings", expand=True, fill="both")
        form.add_text("name", "Name", required=True)
        form.add_dropdown("role", "Role", ["A", "B"])
        form.add_checkbox("agreed", "Agree", required=True)
        form.add_text("email", "Email", validator=lambda v: None if "@" in v else "Missing @")
        self.assertEqual(set(form.validate()), {"name", "agreed", "email"})
        with self.assertRaises(FormValidationError):
            form.snapshot()
        form.set({"name": "Ada", "role": "B", "agreed": True, "email": "a@b"})
        self.assertEqual(form.validate(), {})
        self.assertEqual(form.snapshot()["name"], "Ada")
        form.reset()
        self.assertEqual(form.get(), {"name": "", "role": "A", "agreed": False, "email": ""})
        self.assertEqual(form.errors, {})
        form.remove("email")
        self.assertNotIn("email", form.get())
        with self.assertRaisesRegex(ValueError, "already exists"):
            form.add_text("name", "Duplicate")
        with self.assertRaises(KeyError):
            form.set({"unknown": "no"})

    def test_large_form_scrolls_and_actions_stay_outside_canvas(self):
        form = Form(self.app, "Many fields", expand=True, fill="both")
        for i in range(40):
            form.add_text(f"field_{i}", f"Field {i}")
        button = form.add_button("Reset", form.reset)
        self.app.root.update()
        self.assertEqual(len(form.get()), 40)
        self.assertEqual(form.body.widget.winfo_manager(), "canvas")
        self.assertGreater(form.canvas.bbox("all")[3], form.canvas.winfo_height())
        form.canvas.yview_moveto(1)
        self.app.root.update()
        self.assertGreater(form.canvas.yview()[0], 0)
        self.assertTrue(button.widget.winfo_ismapped())

    def test_non_scrolling_form_and_validator_contract(self):
        form = Form(self.app, scrollable=False)
        form.add_label("Instructions")
        form.add_text("name", "Name", validator=lambda value: True)
        self.assertFalse(hasattr(form, "canvas"))
        with self.assertRaisesRegex(TypeError, "Validators"):
            form.validate()
        with self.assertRaisesRegex(ValueError, "vertical"):
            Form(self.app, orientation="horizontal")

    def test_form_submit_captures_values_and_validates_before_worker(self):
        form = Form(self.app)
        form.add_text("name", "Name", required=True)
        gate = threading.Event()
        self.addCleanup(gate.set)
        calls, results, errors = [], [], []
        def work(values):
            calls.append((values, threading.get_ident()))
            gate.wait(2)
            return values["name"]
        button = form.add_submit("Save", work, on_result=results.append, on_error=errors.append)
        button.invoke()
        self.assertIsInstance(errors.pop(), FormValidationError)
        self.assertEqual(calls, [])
        form.set({"name": "Before"})
        button.invoke()
        form.set({"name": "After"})
        gate.set()
        self.pump(lambda: bool(results))
        self.assertEqual(results, ["Before"])
        self.assertNotEqual(calls[0][1], threading.get_ident())

    def test_form_destroy_suppresses_submission_delivery(self):
        gate = threading.Event()
        self.addCleanup(gate.set)
        form = Form(self.app)
        form.add_text("x", "X")
        called = []
        button = form.add_submit("Save", lambda values: gate.wait(2), on_result=called.append)
        future = button.invoke()
        form.destroy()
        gate.set()
        self.pump(lambda: not button.command.running)
        self.assertTrue(future.done())
        self.app.root.update()
        self.assertEqual(called, [])


class ExtendedExamples(unittest.TestCase):
    def build(self, name):
        module = runpy.run_path(str(Path(__file__).resolve().parents[1] / "examples" / name))
        app = module["build_app"]()
        self.addCleanup(app.close)
        return app

    def pump(self, app, condition):
        deadline = time.monotonic() + 3
        while not condition() and time.monotonic() < deadline:
            app.root.update()
            time.sleep(0.005)
        self.assertTrue(condition())

    def test_menu_workspace_analysis_and_new(self):
        app = self.build("menus.py")
        app.demo.editor.set("one two\nthree")
        app.demo.analyze()
        self.pump(app, lambda: "3 words" in app.demo.status.get())
        app.demo.new()
        self.assertEqual(app.demo.editor.get(), "")
        self.assertEqual(app.demo.menu.widget.index("end"), 4)

    def test_chat_sends_and_receives_without_blocking(self):
        app = self.build("chat.py")
        app.demo.message.set("Hello")
        app.demo.send.invoke()
        self.assertTrue(app.demo.action.running)
        self.assertIn("You: Hello", app.demo.transcript.get())
        self.pump(app, lambda: "You said: Hello" in app.demo.transcript.get())
        self.assertTrue(app.demo.send.widget.instate(["!disabled"]))

    def test_logging_job_and_cancellation(self):
        app = self.build("logging_gui.py")
        app.demo.start()
        self.pump(app, lambda: "Step 1/10" in app.demo.output.get())
        app.demo.cancel.set()
        self.pump(app, lambda: app.demo.status.get() == "Cancelled")
        self.pump(app, lambda: "Stopped after" in app.demo.output.get())

    def test_dynamic_form_validation_and_extra_fields(self):
        app = self.build("dynamic_form.py")
        form = app.demo.form
        app.demo.submit.invoke()
        self.assertIn("name", form.errors)
        form.set({"name": "Ada", "email": "ada@example.com"})
        app.demo.add_extra()
        self.assertIn("extra_1", form.get())
        app.demo.submit.invoke()
        self.pump(app, lambda: "Registered Ada" in app.demo.status.get())


if __name__ == "__main__":
    unittest.main()
