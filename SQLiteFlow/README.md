# SQLiteFlow

A copyable folder of SQLite helpers for Python 3.10+. Uses only the standard library and works independently of TkFlow/Tkinter.

Copy `SQLiteFlow/` beside your application's Python modules:

```python
from SQLiteFlow import Database, Column, Q

with Database("data/app.sqlite3") as db:
    contacts = db.create_table("contacts", {
        "name": Column(str, nullable=False),
        "email": Column(str, unique=True),
        "age": int,
    })
    # An integer primary key named id is added automatically.
    identity = contacts.insert(name="Ada", email="ada@example.com", age=30)
    person = contacts.get(identity)                    # dict or None
    people = contacts.find({"age__gte":18}, order_by="name")
    contacts.update(identity, age=31)                  # changed-row count
    contacts.delete(identity)                         # deleted-row count
```

Existing tables: `contacts = db.table("contacts")`. Form data: `contacts.insert(form_values_dictionary)`. Compound filters: `Q(age__gte=18) & Q(name__contains="Ada")`. Data values are bound parameters, and identifiers are validated and quoted.

`with db.transaction():` groups operations atomically. Nested transactions use savepoints. `insert_many` is atomic. Foreign keys are enabled on every connection. File databases use WAL by default. Connections are created on the calling thread, so the handle can be shared with TkFlow background Commands.

Use `update_where`/`delete_where` for bulk changes. Unfiltered bulk mutations require `allow_all=True`. `upsert(data, conflict="unique_column")` uses an existing uniqueness constraint. `db.query(sql, parameters)` and `db.execute(sql, parameters)` support trusted SQL for more advanced operations.

See [the full guide](../docs/sqlite.md) and [the real TkFlow CRUD example](../examples/database_crud.py). In this repository run `python -m examples.database_crud`.
