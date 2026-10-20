"""Real TkFlow forms/tables running SQLite CRUD in bounded background commands."""
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest
from unittest.mock import patch

from SQLiteFlow import Database
from TkFlow.devtools import capture_errors, pump_until
from examples.database_crud import build_app


class DatabaseGuiTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.path = Path(self.temporary.name) / "contacts.sqlite3"
        self.app = build_app(self.path)
        self.addCleanup(self.app.close)
        self.errors = []
        self.app.root.report_callback_exception = lambda kind, error, tb: self.errors.append(error)
        pump_until(self.app, lambda: self.app.demo.ready.get() and not self.app.demo.action.running)

    def tearDown(self):
        self.app.close()
        self.assertEqual(self.errors, [])

    def run_operation(self, operation):
        self.app.demo.request(operation)
        pump_until(self.app, lambda: not self.app.demo.action.running)

    def test_create_read_update_search_delete_and_persistence(self):
        demo = self.app.demo
        self.assertEqual(len(demo.table.rows()), 3)
        calls = []
        connect = demo.db._connect
        def recorded_connect():
            calls.append(threading.get_ident())
            return connect()
        with patch.object(demo.db, "_connect", side_effect=recorded_connect):
            demo.form.set({"name":"New contact", "email":"new@example.com", "role":"Designer", "active":True})
            self.run_operation("create")
            pump_until(self.app, lambda: demo.selected.get() is not None)
            identity = demo.selected.get()
            self.assertEqual(len(demo.table.rows()), 4)
            self.assertEqual(demo.form.get()["name"], "New contact")
            demo.form.set({"name":"Updated contact", "active":False})
            self.run_operation("update")
            pump_until(self.app, lambda: demo.form.get()["name"] == "Updated contact")
            self.assertFalse(demo.form.get()["active"])
            demo.search.set("Updated")
            self.run_operation("refresh")
            self.assertEqual(len(demo.table.rows()), 1)
            demo.table.select(identity)
            pump_until(self.app, lambda: demo.selected.get() == identity)
            self.run_operation("delete")
            self.assertEqual(len(demo.table.rows()), 3)
        self.assertTrue(calls)
        self.assertTrue(all(identity != threading.get_ident() for identity in calls))
        self.app.close()
        with Database(self.path) as reopened:
            self.assertEqual(reopened.table("contacts").count(), 3)
            self.assertFalse(reopened.table("contacts").exists({"email":"new@example.com"}))

    def test_validation_and_unique_errors_preserve_data(self):
        demo = self.app.demo
        self.run_operation("create")
        self.assertIn("name", demo.form.errors)
        self.assertEqual(len(demo.table.rows()), 3)
        demo.form.set({"name":"Duplicate", "email":"ada@example.com"})
        self.run_operation("create")
        self.assertIn("UNIQUE", demo.status.get())
        self.assertEqual(len(demo.table.rows()), 3)
        self.assertEqual(demo.form.get()["name"], "Duplicate")
        self.assertTrue(demo.buttons["create"].widget.instate(["!disabled"]))

    def test_waiting_for_database_lock_does_not_block_gui(self):
        demo = self.app.demo
        blocker = sqlite3.connect(self.path)
        try:
            blocker.execute("BEGIN IMMEDIATE")
            demo.form.set({"name":"Waited safely", "email":"waited@example.com"})
            demo.request("create")
            ticks = []
            self.app.after(10, lambda: ticks.append(True))
            pump_until(self.app, lambda: bool(ticks))
            self.assertTrue(demo.action.running)
        finally:
            blocker.rollback()
            blocker.close()
        pump_until(self.app, lambda: not demo.action.running)
        self.assertTrue(any(row["name"] == "Waited safely" for row in demo.table.rows()))

    def test_existing_empty_database_is_not_reseeded(self):
        self.app.close()
        with Database(self.path) as db:
            db.table("contacts").delete_where(allow_all=True)
        app = build_app(self.path)
        self.addCleanup(app.close)
        with capture_errors(app) as errors:
            pump_until(app, lambda: app.demo.ready.get() and not app.demo.action.running)
            self.assertEqual(app.demo.table.rows(), [])
            self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
