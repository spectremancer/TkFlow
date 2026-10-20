"""Connection-per-operation SQLite access and thread-local transactions."""
from __future__ import annotations
from collections.abc import Mapping
from contextlib import contextmanager
from dataclasses import dataclass
import math
from pathlib import Path
import sqlite3
import threading
import uuid
from .schema import Column, UNSET, identifier, value


@dataclass(frozen=True)
class WriteResult:
    rowcount: int
    lastrowid: int | None


class Database:
    """Share this handle across workers; each operation owns its own connection.

    transaction() reuses one connection on its calling thread. close() prevents
    new operations and lets already-started operations/transactions finish.
    """
    def __init__(self, path, *, timeout=5.0, wal=True, create_parent=True):
        if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or timeout < 0:
            raise ValueError("timeout must be a finite nonnegative number of seconds")
        self.timeout, self.wal = float(timeout), bool(wal)
        self._local = threading.local()
        self._lock, self._setup_lock = threading.Lock(), threading.Lock()
        self._closed, self._active, self._initialized = False, 0, False
        self._anchor = None
        self._memory = str(path) == ":memory:"
        if self._memory:
            self.path = ":memory:"
            self._target = f"file:sqliteflow_{uuid.uuid4().hex}?mode=memory&cache=shared"
            # Anchor keeps the shared in-memory DB alive; never used for queries.
            self._anchor = sqlite3.connect(self._target, uri=True, check_same_thread=False)
        else:
            self.path = str(Path(path).expanduser().resolve())
            self._target = self.path
            if create_parent:
                Path(self.path).parent.mkdir(parents=True, exist_ok=True)

    def _acquire(self):
        with self._lock:
            if self._closed:
                raise RuntimeError("Database is closed")
            self._active += 1

    def _release(self):
        with self._lock:
            self._active -= 1
            if self._closed and self._active == 0 and self._anchor is not None:
                self._anchor.close()
                self._anchor = None

    def _connect(self):
        connection = sqlite3.connect(self._target, uri=self._memory, timeout=self.timeout)
        try:
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys = ON")
            with self._setup_lock:
                if not self._initialized:
                    if self.wal and not self._memory:
                        mode = connection.execute("PRAGMA journal_mode = WAL").fetchone()[0]
                        if mode.lower() != "wal":
                            raise sqlite3.OperationalError("This database cannot enable WAL; use wal=False explicitly")
                    self._initialized = True
            return connection
        except BaseException:
            connection.close()
            raise

    @contextmanager
    def _connection(self):
        connection = getattr(self._local, "connection", None)
        if connection is not None:
            yield connection
            return
        self._acquire()
        connection = None
        try:
            connection = self._connect()
            with connection:
                yield connection
        finally:
            if connection is not None:
                connection.close()
            self._release()

    @contextmanager
    def transaction(self, *, immediate=False):
        """Atomic block; nested blocks use savepoints on this same thread only."""
        connection = getattr(self._local, "connection", None)
        if connection is not None:
            savepoint = "sp_" + uuid.uuid4().hex
            connection.execute(f'SAVEPOINT "{savepoint}"')
            try:
                yield self
                connection.execute(f'RELEASE SAVEPOINT "{savepoint}"')
            except BaseException:
                connection.execute(f'ROLLBACK TO SAVEPOINT "{savepoint}"')
                connection.execute(f'RELEASE SAVEPOINT "{savepoint}"')
                raise
            return
        self._acquire()
        connection = None
        try:
            connection = self._connect()
            connection.execute("BEGIN IMMEDIATE" if immediate else "BEGIN")
            self._local.connection = connection
            try:
                yield self
                connection.commit()
            except BaseException:
                connection.rollback()
                raise
        finally:
            self._local.connection = None
            if connection is not None:
                connection.close()
            self._release()

    @staticmethod
    def _parameters(parameters):
        if isinstance(parameters, Mapping):
            return {name: value(item) for name, item in parameters.items()}
        if isinstance(parameters, (str, bytes)):
            raise TypeError("parameters must be a sequence or mapping, not SQL text")
        return tuple(value(item) for item in parameters)

    def execute(self, sql: str, parameters=()) -> WriteResult:
        """Trusted SQL escape hatch. Supply data as parameters, never f-strings.

        Do not issue BEGIN/COMMIT/ROLLBACK here; use transaction().
        """
        with self._connection() as connection:
            cursor = connection.execute(sql, self._parameters(parameters))
            try:
                return WriteResult(cursor.rowcount, cursor.lastrowid)
            finally:
                cursor.close()

    def query(self, sql: str, parameters=()) -> list[dict]:
        with self._connection() as connection:
            cursor = connection.execute(sql, self._parameters(parameters))
            try:
                return [dict(row) for row in cursor.fetchall()]
            finally:
                cursor.close()

    def create_table(self, name, columns=None, *, add_id=True, if_not_exists=True):
        from .table import Table
        columns = dict(columns or {})
        identifier(name)
        definitions = {key: spec if isinstance(spec, Column) else Column(spec) for key, spec in columns.items()}
        keys = [key for key, spec in definitions.items() if spec.primary_key]
        if len(keys) > 1:
            raise ValueError("Column schemas support a single primary key; use SQL for composite keys")
        if add_id and not keys and "id" not in definitions:
            definitions = {"id": Column(int, primary_key=True), **definitions}
            keys = ["id"]
        if not definitions:
            raise ValueError("A table needs at least one column")
        sql = ", ".join(f"{identifier(key)} {spec.sql()}" for key, spec in definitions.items())
        self.execute(f"CREATE TABLE {'IF NOT EXISTS ' if if_not_exists else ''}{identifier(name)} ({sql})")
        return Table(self, name, primary_key=keys[0] if keys else None)

    def table(self, name, *, primary_key=UNSET):
        from .table import Table
        identifier(name)
        if primary_key is UNSET:
            columns = self.query(f"PRAGMA table_info({identifier(name)})")
            if not columns:
                raise ValueError(f"Table or view {name!r} does not exist")
            keys = [column["name"] for column in columns if column["pk"]]
            primary_key = keys[0] if len(keys) == 1 else None
        return Table(self, name, primary_key=primary_key)

    def create_index(self, table, columns, *, name=None, unique=False):
        columns = [columns] if isinstance(columns, str) else list(columns)
        if not columns:
            raise ValueError("An index needs columns")
        name = name or f"idx_{table}_{'_'.join(columns)}"
        self.execute(f"CREATE {'UNIQUE ' if unique else ''}INDEX IF NOT EXISTS {identifier(name)} ON {identifier(table)} ({', '.join(identifier(column) for column in columns)})")

    def close(self):
        with self._lock:
            self._closed = True
            if self._active == 0 and self._anchor is not None:
                self._anchor.close()
                self._anchor = None

    def __enter__(self):
        with self._lock:
            if self._closed:
                raise RuntimeError("Database is closed")
        return self

    def __exit__(self, *exc):
        self.close()
