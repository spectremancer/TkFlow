# SQLiteFlow: simple database CRUD for Python and TkFlow

SQLiteFlow lives in the sibling **`SQLiteFlow/` folder**. Copy it into any Python project, independently or alongside TkFlow. It uses the standard-library `sqlite3` module and does not import Tkinter, require package installation, generate models, or maintain a shared worker connection.

Requires Python 3.10+. Upsert requires SQLite 3.24+ (included in current supported Python distributions; inspect `sqlite3.sqlite_version` if using a custom build).

## Start with five operations

```python
from SQLiteFlow import Database, Column

with Database("data/app.sqlite3") as db:
    contacts = db.create_table("contacts", {
        "name": Column(str, nullable=False),
        "email": Column(str, nullable=False, unique=True),
        "role": Column(str, default="Other"),
        "active": Column(bool, default=True),
    })

    identity = contacts.insert(name="Ada", email="ada@example.com")
    contact = contacts.get(identity)
    contacts.update(identity, role="Developer")
    rows = contacts.find({"active":True}, order_by="name")
    contacts.delete(identity)
```

An integer primary key called `id` is added unless the schema already supplies a primary key or a column named `id`, or you set `add_id=False`. Integer keys follow SQLite rowid rules; deleted IDs can be reused. Treat them as opaque identities, not an event sequence.

`create_table` returns a Table handle. For an existing database use `db.table("contacts")`, which discovers its primary key. Reuse that lightweight handle for many calls. Methods return plain dictionaries, lists, identities, or affected-row counts—no model inheritance or implicit object persistence.

Schemas can use bare Python types for concise nullable columns:

```python
notes = db.create_table("notes", {"title":str, "body":str, "rating":float})
```

`with Database(...) as db` closes the database handle on exit; it does **not** group all enclosed work into one transaction. Each ordinary operation commits on success and rolls back on failure. Use `with db.transaction():` for a multi-operation atomic unit.

## Import and project layout

```text
project/
    TkFlow/
    SQLiteFlow/
    app/
        __init__.py
        main.py
        repository.py
```

In `app/repository.py`: `from SQLiteFlow import Database, Column, Q`. Run `python -m app.main` from the project root. SQLiteFlow's internal relative imports also allow a nested/renamed copy, e.g. `from utils.storage import Database`. SQLiteFlow.Table is a database handle; TkFlow.Table is a GUI widget. Use module-qualified names or import aliases when both are needed explicitly.

## Database lifecycle and connections

```python
Database(path, timeout=5.0, wal=True, create_parent=True)
```

- A relative file path is resolved at construction, so later working-directory changes do not redirect it. Parent directories are created by default; use `create_parent=False` to require them to exist.
- SQL work opens a connection **on the calling thread**, finishes the operation, and closes it there. There is no shared query connection and no cursor escapes the API.
- File databases enable WAL on first connection. If WAL cannot be enabled, the operation raises; explicitly use `wal=False` when you need another journal mode. Foreign keys are enabled on every connection.
- `timeout` is SQLite's busy-lock timeout in seconds, a finite nonnegative number. It is not a maximum query runtime. A blocked operation waits in its worker when used through Command.
- `close()` is idempotent. It prevents new operations; admitted operations and active transactions can finish. An active transaction keeps using its existing connection even if another thread closes the handle.
- `Database(":memory:")` gives an isolated shared in-memory database. Its internal anchor keeps it alive between operations; different Database instances remain isolated. The anchor is never used for CRUD. Close the handle when finished. SQLite's shared-memory locking differs from file WAL locking and can raise lock errors immediately for conflicting operations; file databases are the better example of concurrent writers.

The handle is shareable across worker threads. Your application decides transaction scope and operation ordering. A transaction belongs to its calling thread; work submitted to another thread does not join it automatically.

## Schema definitions

```python
Column(type=str, nullable=True, default=..., unique=False,
       primary_key=False, references=None)
ForeignKey(table, column="id", on_delete="RESTRICT", on_update="RESTRICT")
```

Omitting `default` means no SQL default. `default=None` explicitly means SQL NULL. Python types map to SQLite: str→TEXT, int/bool→INTEGER, float→REAL, bytes→BLOB. The strings TEXT, INTEGER, REAL, BLOB, and NUMERIC are also accepted. SQLite's affinity and constraints apply; this is not a runtime Python type-enforcement system.

Default values are quoted/encoded literals, never SQL expressions. A string such as `"CURRENT_TIMESTAMP"` is a literal string; use trusted SQL DDL if an expression default is needed. Foreign-key actions are restricted to RESTRICT, CASCADE, SET NULL, SET DEFAULT, and NO ACTION.

```python
projects = db.create_table("projects", {"name":Column(str, nullable=False)})
tasks = db.create_table("tasks", {
    "project_id": Column(int, nullable=False,
                         references=ForeignKey("projects", on_delete="CASCADE")),
    "title": Column(str, nullable=False),
})
db.create_index("tasks", "project_id")
db.create_index("tasks", ["project_id", "title"], unique=True)
```

`create_table(name, columns, add_id=True, if_not_exists=True)` supports one primary-key column in this schema builder. To declare your own `id`, use `Column(int, primary_key=True)`. Text keys work too. For composite keys or specialized constraints, create the table with trusted SQL and use where-based CRUD.

`create_index(table, columns, name=None, unique=False)` accepts a string or sequence of column names. The default name is `idx_TABLE_COLUMNS`. Table/index creation with IF NOT EXISTS does not validate or migrate an existing schema. Keep real migrations explicit and versioned; use transactions for compatible migration steps.

Identifiers use ASCII letters/numbers/underscores, starting with a letter or underscore. They are quoted, so reserved SQL words can still be valid names. Arbitrary SQL expressions, dotted names, and punctuation are not accepted as identifiers. Predicate suffixes reserve `__`; prefer ordinary snake_case column names.

## CRUD reference

| Method | Returns | Notes |
| --- | --- | --- |
| `table.insert(data=None, **fields)` | Primary-key value or generated rowid | Mapping or keyword data; an empty insert uses defaults |
| `table.insert_many(rows)` | List of keys/rowids | Atomic, preserving input order; accepts a generator |
| `table.get(identity)` | dict or None | Requires a single primary key |
| `table.find(where=None, order_by=None, limit=None, offset=0, columns=None)` | list[dict] | Filters, projection, sorting and pagination |
| `table.first(where=None, order_by=None, columns=None)` | dict or None | First matching result |
| `table.count(where=None)` | int | Matching row count |
| `table.exists(where=None)` | bool | Stops after the first match |
| `table.update(identity, data=None, **fields)` | int | Matched/affected rows, including unchanged matched values |
| `table.update_where(data, where=None, allow_all=False)` | int | Bulk update with explicit filter policy |
| `table.delete(identity)` | int | Zero for a missing row |
| `table.delete_where(where=None, allow_all=False)` | int | Bulk deletion with explicit filter policy |
| `table.upsert(data, conflict=..., update=None)` | int | Insert/update row count; zero on DO NOTHING |

Options after `where` are keyword-only where shown in the source signatures. Use `contacts.insert(form_values)` or `contacts.update(identity, form_values)` for form dictionaries. Duplicate keys between a mapping and keyword data raise. If a column name conflicts with a method parameter (such as `data`), use the mapping form.

Selected columns must be names, not SQL expressions. `order_by="name"` sorts ascending; `order_by="-created"` sorts descending; a sequence adds tie breakers. Pagination takes nonnegative integers. Without explicit ordering, SQLite does not promise a stable order. `offset` without a limit is supported.

Values support None, strings, integers, bools, finite floats, bytes/bytearray/memoryview, and date/datetime (stored as ISO strings). Returned bool columns are ordinary SQLite 0/1 integers; returned dates are strings. Convert explicitly when populating typed form fields. Use JSON strings for structured data if needed; unsupported objects raise TypeError. SQL NULL remains None.

Empty mappings, None, Q(), and predicates recognized as constant true are rejected for unfiltered bulk mutations:

```python
contacts.update_where({"active":False}, where={"role":"Former"})
contacts.delete_where(where={"active":False})
contacts.delete_where(allow_all=True)  # Explicitly delete every row.
```

This checks for missing/literal-true filters, not a mathematical proof that a predicate cannot match every row. A supplied broad predicate is your application's policy. Missing identity updates/deletes return zero. Integrity constraints raise sqlite3.IntegrityError and preserve atomicity.

## Filters and Q predicates

A mapping combines conditions with AND:

```python
rows = contacts.find({"active":True, "name__contains":"Ada"})
```

Supported suffixes:

| Suffix | Meaning |
| --- | --- |
| none / `__eq` | Equality; None becomes IS NULL |
| `__ne` | Inequality; None becomes IS NOT NULL |
| `__gt`, `__gte`, `__lt`, `__lte` | Comparisons |
| `__in`, `__not_in` | Iterable membership; strings/bytes/mappings are rejected as the iterable |
| `__is_null` | True for IS NULL, False for IS NOT NULL |
| `__contains`, `__startswith`, `__endswith` | Literal text matching, with `%`, `_`, and backslash escaped |
| `__like` | SQLite LIKE pattern matching with wildcards |

```python
from SQLiteFlow import Q

where = (Q(name__contains="Ada") | Q(email__endswith="@example.com")) & ~Q(active=False)
rows = contacts.find(where, order_by=["name", "id"], limit=25, offset=0)
```

Use `&`, `|`, and `~`, with parentheses. Python `and/or/not` cannot compose predicates and raise through Q's truth-value check. Empty `__in` is false; empty `__not_in` is true. SQL's normal NULL semantics still apply within membership/comparison lists. LIKE's case and Unicode behavior follows SQLite's configured collation, not Python's casefold behavior.

All predicate data is bound separately from SQL. Column/table/index/order identifiers are validated and quoted. Raw SQL escape hatches intentionally accept trusted SQL; they are not a security sandbox.

## Upserts

```python
contacts.upsert({"name":"Ada", "email":"ada@example.com", "active":True},
                conflict="email")
```

The conflict target must match a real UNIQUE constraint/index or primary key. Default updates include supplied columns except conflict columns and the configured primary key. `update=["name"]` restricts updates; `update=[]` uses DO NOTHING. Conflict and update columns must appear in supplied data. Omitted columns retain existing values on update or use schema defaults on insert. The return is affected-row count; use `first({"email":...})` when you need the resulting record.

## Transactions and nested rollback

```python
with db.transaction(immediate=True):
    project_id = projects.insert(name="Explorer")
    tasks.insert_many([
        {"project_id":project_id, "title":"Prototype"},
        {"project_id":project_id, "title":"Test"},
    ])
```

Root blocks BEGIN/COMMIT on success and ROLLBACK on exceptions, including BaseException. `immediate=True` acquires the writer reservation at entry; it is useful for read-modify-write logic with concurrent workers. SQLite still allows only one writer at a time. Keep transactions short and do not hold them open while waiting for GUI input.

Nested blocks use savepoints. Catch an inner exception outside its nested block to roll back just that block and continue the outer transaction. An uncaught exception rolls back the outer unit. `insert_many` opens a transaction itself and therefore becomes a nested savepoint inside an existing transaction.

```python
from SQLiteFlow import IntegrityError

with db.transaction():
    contacts.insert(name="First", email="first@example.com")
    try:
        with db.transaction():
            contacts.insert(name="Duplicate", email="first@example.com")
    except IntegrityError:
        pass
    contacts.insert(name="Second", email="second@example.com")
```

SQLite lock/constraint/database errors propagate unchanged. Import `IntegrityError`, `OperationalError`, or `DatabaseError` from SQLiteFlow or sqlite3. Handle these in your GUI error callback; do not silently retry an operation whose transaction scope is unclear.

## Trusted SQL escape hatches

```python
rows = db.query("SELECT role, COUNT(*) AS total FROM contacts GROUP BY role")
result = db.execute("UPDATE contacts SET active=? WHERE id=?", (False, identity))
print(result.rowcount, result.lastrowid)
```

`query` returns dictionaries. `execute` returns an immutable WriteResult with rowcount and lastrowid. SQLite may report rowcount=-1 for DDL; lastrowid is meaningful only for appropriate inserts. Use `query` for statements returning rows. Both accept positional parameter sequences or named parameter dictionaries, reuse active transactions, and close their cursors.

Only use trusted SQL structure here; bind all external values. Do not issue BEGIN, COMMIT, ROLLBACK, savepoint control, or executescript-style transaction management through these methods—use `transaction()`. Native connection/cursor objects are deliberately not exposed, so they cannot accidentally cross GUI worker threads.

## TkFlow integration

The folders remain independent. Use a background Command to run database methods, and pass captured plain values:

```python
from TkFlow import App, Form, Label
from SQLiteFlow import Database

app = App("Contacts")
db = Database("data/app.sqlite3")
app.on_dispose(db.close)
form = Form(app, "New contact", expand=True, fill="both")
form.add_text("name", "Name", required=True)
status = Label(app, "Ready")


def save(values):
    # Schema setup and SQL run on this worker's connection.
    contacts = db.create_table("contacts", {"name":str})
    return contacts.insert(values)


form.add_submit("Save", save, on_result=lambda identity: status.set(f"Saved #{identity}"),
                on_error=lambda error: status.set(str(error)))
app.run()
```

Form validates and captures values on the GUI thread. SQLiteFlow works on a worker-owned connection. Completion updates the GUI through Command. Database.close does not abort in-flight work; TkFlow's daemon workers still require application-level shutdown coordination for critical writes. Never block the GUI on Future.result(), and do not start worker tasks inside a GUI-thread transaction expecting them to share that transaction.

The [complete CRUD example](../examples/database_crud.py) demonstrates schema initialization, seeding only a new database, form-to-row conversion, table selection, create/update/delete/search, constraint-error reporting, and shared-command overlap protection. It waits for initialization asynchronously and disables conflicting actions while busy. A test deliberately holds a SQLite write lock and verifies a GUI timer still executes while the worker waits.

## Run, test and inspect

```bash
python -m examples.database_crud
python -m unittest discover -s tests -p test_sqliteflow.py -v
xvfb-run -a python -m unittest discover -s tests -v
```

The example stores its database under `examples/data/contacts.sqlite3` (ignored by Git). Data survives restarting; existing empty databases are not reseeded. Use `build_app(path)` to choose another path or an isolated test file. The optional Pillow-based screenshot tool uses a temporary database:

```bash
xvfb-run -a -s '-screen 0 1600x1200x24' python -m tools.capture_database
```

[Default-size screenshot](screenshots/database-crud-wide.png) · [Compact screenshot](screenshots/database-crud-compact.png)

Tests cover persistence, all CRUD methods, filter binding/injection resistance, schema constraints, dates/blobs/defaults, bulk rollback, nested savepoints, foreign-key enforcement on worker connections, upserts, concurrent read-modify-write operations, close-during-transaction behavior, standalone copied imports, real GUI CRUD, and GUI responsiveness under a database lock.
