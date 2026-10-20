"""Database behavior, atomicity, parameterization, and worker compatibility."""
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import threading
import unittest

from SQLiteFlow import Database, Column, ForeignKey, Q, IntegrityError


class DatabaseTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.path = Path(self.temporary.name) / "app.sqlite3"
        self.db = Database(self.path)
        self.addCleanup(self.db.close)
        self.people = self.db.create_table("people", {
            "name": Column(str, nullable=False), "email":Column(str, unique=True),
            "age":int, "active":Column(bool, default=True), "notes":str,
        })

    def test_complete_crud_and_reopen(self):
        key = self.people.insert(name="Ada", email="ada@example.com", age=30)
        self.assertEqual(self.people.get(key)["active"], 1)
        self.assertEqual(self.people.update(key, {"name":"Grace"}), 1)
        self.assertEqual(self.people.first({"email":"ada@example.com"})["name"], "Grace")
        with Database(self.path) as reopened:
            self.assertEqual(reopened.table("people").get(key)["name"], "Grace")
        self.assertTrue(self.people.exists({"age":30}))
        self.assertEqual(self.people.delete(key), 1)
        self.assertIsNone(self.people.get(key))
        self.assertEqual(self.people.count(), 0)
        self.assertEqual(self.people.update(key, name="Missing"), 0)
        self.assertEqual(self.people.delete(key), 0)

    def test_defaults_empty_insert_dates_and_blobs(self):
        table = self.db.create_table("records", {"title":Column(str, default="O'Reilly"),
                                                 "payload":bytes, "created":str})
        first = table.insert()
        self.assertEqual(table.get(first)["title"], "O'Reilly")
        key = table.insert(payload=b"\x00\xff", created=date(2026, 10, 20))
        self.assertEqual(table.get(key)["payload"], b"\x00\xff")
        self.assertEqual(table.get(key)["created"], "2026-10-20")
        self.db.execute("UPDATE records SET created=:created WHERE id=:id",
                        {"created":datetime(2026, 10, 20, 12, 30),"id":key})
        self.assertEqual(table.get(key)["created"], "2026-10-20T12:30:00")

    def test_filters_ordering_projection_and_pagination(self):
        self.people.insert_many([{"name":"Ada","age":30}, {"name":"Grace","age":40}, {"name":"Alan","age":20}])
        rows = self.people.find(Q(age__gte=25) & (Q(name="Ada") | Q(name="Grace")), order_by="-age", columns=["name"])
        self.assertEqual(rows, [{"name":"Grace"}, {"name":"Ada"}])
        self.assertEqual(self.people.find({"age__in":[20,30]}, order_by="age", offset=1, limit=1)[0]["name"], "Ada")
        self.assertEqual(self.people.find(~Q(name="Ada"), order_by="name")[0]["name"], "Alan")
        self.assertEqual(len(self.people.find(order_by=["age","name"], offset=2)), 1)
        self.assertEqual(self.people.find(limit=0), [])

    def test_null_and_empty_set_predicates(self):
        self.people.insert(name="Ada")
        self.assertEqual(self.people.count({"email":None}), 1)
        self.assertEqual(self.people.count({"email__ne":None}), 0)
        self.assertEqual(self.people.count({"email__is_null":True}), 1)
        self.assertEqual(self.people.count({"name__in":[]}), 0)
        self.assertEqual(self.people.count({"name__not_in":[]}), 1)

    def test_text_predicates_escape_literal_wildcards(self):
        self.people.insert_many([{"name":"100%_done"}, {"name":"100x_done"}, {"name":"O'Reilly"}])
        self.assertEqual(self.people.count({"name__contains":"%_"}), 1)
        self.assertEqual(self.people.count({"name__startswith":"100%"}), 1)
        self.assertEqual(self.people.count({"name__endswith":"Reilly"}), 1)
        self.assertEqual(self.people.count({"name__like":"100%"}), 2)

    def test_values_are_bound_and_identifiers_are_validated(self):
        attack = "'); DROP TABLE people; --"
        key = self.people.insert(name=attack, notes="\x00 data")
        self.assertEqual(self.people.get(key)["name"], attack)
        self.assertEqual(self.people.find({"name":attack})[0]["id"], key)
        for function in (lambda: self.db.table('people; DROP TABLE people'),
                         lambda: self.people.find(order_by='name; DELETE FROM people'),
                         lambda: self.people.insert({"name) VALUES ('x');--":"bad"}),
                         lambda: self.people.find({"name__unknown":"bad"})):
            with self.assertRaises(ValueError):
                function()
        self.assertEqual(self.people.count(), 1)
        quoted = self.db.create_table("order", {"select":str})
        key = quoted.insert({"select":"reserved keyword"})
        self.assertEqual(quoted.get(key)["select"], "reserved keyword")

    def test_unfiltered_mutations_require_explicit_opt_in(self):
        self.people.insert(name="Ada")
        for condition in (None, {}, Q(), Q() | Q(name="Ada"), Q(name__not_in=[])):
            with self.assertRaisesRegex(ValueError, "unfiltered"):
                self.people.delete_where(where=condition)
            with self.assertRaisesRegex(ValueError, "unfiltered"):
                self.people.update_where({"active":False}, where=condition)
        self.assertEqual(self.people.delete_where(where=Q(name__in=[])), 0)
        self.assertEqual(self.people.update_where({"active":False}, allow_all=True), 1)
        self.assertEqual(self.people.delete_where(allow_all=True), 1)

    def test_bulk_insert_is_atomic(self):
        with self.assertRaises(IntegrityError):
            self.people.insert_many([{"name":"Ada","email":"same"}, {"name":"Grace","email":"same"}])
        self.assertEqual(self.people.count(), 0)
        keys = self.people.insert_many({"name":f"Person {i}"} for i in range(4))
        self.assertEqual(len(keys), 4)
        self.assertEqual(self.people.count(), 4)

    def test_transaction_commit_rollback_and_nested_savepoint(self):
        with self.db.transaction():
            self.people.insert(name="Outer")
            try:
                with self.db.transaction():
                    self.people.insert(name="Inner")
                    raise ValueError("undo inner")
            except ValueError:
                pass
            self.people.insert(name="After")
        self.assertEqual([row["name"] for row in self.people.find(order_by="id")], ["Outer","After"])
        with self.assertRaises(RuntimeError):
            with self.db.transaction():
                self.people.delete_where(allow_all=True)
                raise RuntimeError("undo outer")
        self.assertEqual(self.people.count(), 2)

    def test_transactional_schema_rollback(self):
        with self.assertRaises(RuntimeError):
            with self.db.transaction():
                self.db.create_table("temporary", {"value":str})
                raise RuntimeError()
        with self.assertRaises(ValueError):
            self.db.table("temporary")

    def test_foreign_keys_apply_on_every_connection(self):
        children = self.db.create_table("children", {"parent_id":Column(int, nullable=False,
                    references=ForeignKey("people", on_delete="CASCADE"))})
        with self.assertRaises(IntegrityError):
            children.insert(parent_id=999)
        key = self.people.insert(name="Parent")
        child = children.insert(parent_id=key)
        self.assertIsNotNone(children.get(child))
        self.people.delete(key)
        self.assertIsNone(children.get(child))
        with ThreadPoolExecutor(max_workers=1) as executor:
            with self.assertRaises(IntegrityError):
                executor.submit(children.insert, parent_id=999).result(timeout=3)

    def test_upsert_unique_indexes_and_conflict_options(self):
        key = self.people.insert(name="Before", email="same")
        self.assertEqual(self.people.upsert({"name":"After","email":"same"}, conflict="email"), 1)
        self.assertEqual(self.people.get(key)["name"], "After")
        self.assertEqual(self.people.upsert({"name":"Ignored","email":"same"}, conflict="email", update=[]), 0)
        self.assertEqual(self.people.get(key)["name"], "After")
        self.db.create_index("people", ["name","age"], unique=True)
        self.people.upsert({"name":"New","age":20}, conflict=["name","age"])
        self.people.upsert({"name":"New","age":20}, conflict=["name","age"])
        self.assertEqual(self.people.count({"name":"New"}), 1)

    def test_text_primary_key_and_no_primary_key(self):
        tags = self.db.create_table("tags", {"code":Column(str, primary_key=True), "label":str})
        self.assertEqual(tags.insert(code="alpha", label="A"), "alpha")
        self.assertEqual(self.db.table("tags").get("alpha")["label"], "A")
        rows = self.db.create_table("keyless", {"value":str}, add_id=False)
        rows.insert(value="text")
        with self.assertRaisesRegex(ValueError, "primary key"):
            rows.get(1)
        self.assertEqual(rows.first()["value"], "text")

    def test_concurrent_operations_and_immediate_transactions(self):
        counters = self.db.create_table("counters", {"value":int})
        identity = counters.insert(value=0)
        def increment(_):
            with self.db.transaction(immediate=True):
                current = counters.get(identity)["value"]
                counters.update(identity, value=current + 1)
        with ThreadPoolExecutor(max_workers=4) as executor:
            list(executor.map(increment, range(24)))
        self.assertEqual(counters.get(identity)["value"], 24)
        self.assertEqual(self.db.query("PRAGMA journal_mode")[0]["journal_mode"], "wal")

    def test_memory_database_is_shared_but_instances_are_isolated(self):
        with Database(":memory:") as first, Database(":memory:") as second:
            table = first.create_table("items", {"value":str})
            with ThreadPoolExecutor(max_workers=1) as executor:
                key = executor.submit(table.insert, value="worker").result(timeout=3)
            self.assertEqual(table.get(key)["value"], "worker")
            with self.assertRaises(ValueError):
                second.table("items")

    def test_close_allows_active_transaction_to_finish_and_rejects_new_work(self):
        entered, finish = threading.Event(), threading.Event()
        def work():
            with self.db.transaction():
                entered.set()
                finish.wait(2)
                self.people.insert(name="Committed")
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(work)
            self.assertTrue(entered.wait(1))
            self.db.close()
            with self.assertRaisesRegex(RuntimeError, "closed"):
                self.people.count()
            finish.set()
            future.result(timeout=3)
        with Database(self.path) as reopened:
            self.assertEqual(reopened.table("people").count(), 1)

    def test_invalid_arguments_fail_without_mutation(self):
        for call in (lambda: self.people.find(limit=-1), lambda: self.people.find(offset=True),
                     lambda: self.people.find(columns=[]), lambda: self.people.update(1, {}),
                     lambda: self.people.insert(name="A", age=float("nan")),
                     lambda: self.people.upsert({"name":"A"}, conflict=[])):
            with self.assertRaises((ValueError, TypeError)):
                call()
        with self.assertRaises(TypeError):
            bool(Q(name="Ada"))
        with self.assertRaises(TypeError):
            Q() & None
        self.assertEqual(self.people.count(), 0)

    def test_copy_folder_imports_without_tkinter_or_site_packages(self):
        import shutil
        project = Path(self.temporary.name) / "copy"
        shutil.copytree(Path(__file__).resolve().parents[1] / "SQLiteFlow", project / "utils" / "store")
        result = subprocess.run([sys.executable, "-E", "-S", "-c",
            "import sys; from utils.store import Database; db=Database(':memory:'); "
            "t=db.create_table('items', {'name':str}); k=t.insert(name='Ada'); "
            "assert t.get(k)['name']=='Ada'; assert 'tkinter' not in sys.modules; db.close()"],
            cwd=project, text=True, capture_output=True, timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
