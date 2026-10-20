"""Dictionary-based CRUD helpers backed exclusively by bound SQL values."""
from __future__ import annotations
from collections.abc import Mapping
from .schema import identifier
from .query import predicate


def _data(data, fields):
    if data is not None and not isinstance(data, Mapping):
        raise TypeError("Row data must be a mapping")
    result = dict(data or {})
    overlap = result.keys() & fields.keys()
    if overlap:
        raise ValueError(f"Fields supplied twice: {sorted(overlap)}")
    result.update(fields)
    for name in result:
        identifier(name)
    return result


def _nonnegative(item, name):
    if isinstance(item, bool) or not isinstance(item, int) or item < 0:
        raise ValueError(f"{name} must be a nonnegative integer")
    return item


class Table:
    """A cheap table handle; share it across workers with its Database."""
    def __init__(self, database, name, *, primary_key="id"):
        identifier(name)
        if primary_key is not None:
            identifier(primary_key)
        self.database, self.name, self.primary_key = database, name, primary_key

    @property
    def _sql_name(self):
        return identifier(self.name)

    def _identity(self, identity):
        if self.primary_key is None:
            raise ValueError("This table has no single primary key; use where-based methods")
        return {self.primary_key: identity}

    def insert(self, data=None, **fields):
        """Return the supplied primary key, or SQLite's generated rowid."""
        data = _data(data, fields)
        if data:
            columns = ", ".join(identifier(name) for name in data)
            result = self.database.execute(f"INSERT INTO {self._sql_name} ({columns}) VALUES ({', '.join('?' for _ in data)})",
                                           tuple(data.values()))
        else:
            result = self.database.execute(f"INSERT INTO {self._sql_name} DEFAULT VALUES")
        return data[self.primary_key] if self.primary_key in data and data[self.primary_key] is not None else result.lastrowid

    def insert_many(self, rows):
        """Insert atomically; return primary keys/rowids in input order."""
        with self.database.transaction():
            return [self.insert(row) for row in rows]

    def find(self, where=None, *, order_by=None, limit=None, offset=0, columns=None) -> list[dict]:
        clause, parameters, _ = predicate(where)
        if columns is None:
            selected = "*"
        else:
            columns = [columns] if isinstance(columns, str) else list(columns)
            if not columns:
                raise ValueError("Select at least one column")
            selected = ", ".join(identifier(column) for column in columns)
        sql = f"SELECT {selected} FROM {self._sql_name} WHERE {clause}"
        if order_by:
            ordering = [order_by] if isinstance(order_by, str) else list(order_by)
            sql += " ORDER BY " + ", ".join(identifier(column[1:] if column.startswith("-") else column) +
                                            (" DESC" if column.startswith("-") else " ASC") for column in ordering)
        _nonnegative(offset, "offset")
        if limit is not None:
            sql += " LIMIT ?"
            parameters.append(_nonnegative(limit, "limit"))
        elif offset:
            sql += " LIMIT -1"
        if offset:
            sql += " OFFSET ?"
            parameters.append(offset)
        return self.database.query(sql, parameters)

    def first(self, where=None, *, order_by=None, columns=None) -> dict | None:
        rows = self.find(where, order_by=order_by, columns=columns, limit=1)
        return rows[0] if rows else None

    def get(self, identity) -> dict | None:
        return self.first(self._identity(identity))

    def count(self, where=None) -> int:
        clause, parameters, _ = predicate(where)
        return self.database.query(f"SELECT COUNT(*) AS count FROM {self._sql_name} WHERE {clause}", parameters)[0]["count"]

    def exists(self, where=None) -> bool:
        clause, parameters, _ = predicate(where)
        return bool(self.database.query(f"SELECT 1 FROM {self._sql_name} WHERE {clause} LIMIT 1", parameters))

    def update(self, identity, data=None, **fields) -> int:
        return self.update_where(_data(data, fields), where=self._identity(identity))

    def update_where(self, data, *, where=None, allow_all=False) -> int:
        data = _data(data, {})
        if not data:
            raise ValueError("Update needs at least one field")
        clause, parameters, constant = predicate(where)
        if constant is True and not allow_all:
            raise ValueError("Refusing unfiltered update; supply where or explicitly set allow_all=True")
        assignments = ", ".join(f"{identifier(column)} = ?" for column in data)
        return self.database.execute(f"UPDATE {self._sql_name} SET {assignments} WHERE {clause}",
                                     [*data.values(), *parameters]).rowcount

    def delete(self, identity) -> int:
        return self.delete_where(where=self._identity(identity))

    def delete_where(self, *, where=None, allow_all=False) -> int:
        clause, parameters, constant = predicate(where)
        if constant is True and not allow_all:
            raise ValueError("Refusing unfiltered delete; supply where or explicitly set allow_all=True")
        return self.database.execute(f"DELETE FROM {self._sql_name} WHERE {clause}", parameters).rowcount

    def upsert(self, data, *, conflict, update=None) -> int:
        """Insert or update using an existing unique constraint; return rowcount."""
        data = _data(data, {})
        conflict = [conflict] if isinstance(conflict, str) else list(conflict)
        if not data or not conflict:
            raise ValueError("Upsert needs data and conflict columns")
        if set(conflict) - data.keys():
            raise ValueError("Conflict columns must be supplied in data")
        updates = [column for column in data if column not in conflict and column != self.primary_key] if update is None else ([update] if isinstance(update, str) else list(update))
        if set(updates) - data.keys():
            raise ValueError("Update columns must be supplied in data")
        columns = ", ".join(identifier(column) for column in data)
        sql = f"INSERT INTO {self._sql_name} ({columns}) VALUES ({', '.join('?' for _ in data)}) ON CONFLICT ({', '.join(identifier(column) for column in conflict)}) "
        sql += ("DO UPDATE SET " + ", ".join(f"{identifier(column)} = excluded.{identifier(column)}" for column in updates)) if updates else "DO NOTHING"
        return self.database.execute(sql, tuple(data.values())).rowcount
