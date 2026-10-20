"""Small, validated SQLite schema definitions; no ORM model base class."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import date, datetime
import math
import re

UNSET = object()
_TYPES = {str: "TEXT", int: "INTEGER", float: "REAL", bytes: "BLOB", bool: "INTEGER"}


def identifier(name: str) -> str:
    if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
        raise ValueError(f"Invalid SQL identifier: {name!r}; use letters, numbers, and underscores")
    return '"' + name + '"'


def value(item):
    if isinstance(item, (datetime, date)):
        return item.isoformat()
    if isinstance(item, float) and not math.isfinite(item):
        raise ValueError("SQLite values must be finite; use None for SQL NULL")
    if item is None or isinstance(item, (str, int, float, bytes, bytearray, memoryview)):
        return item
    raise TypeError(f"Unsupported SQLite value: {type(item).__name__}")


def literal(item):
    item = value(item)
    if item is None:
        return "NULL"
    if isinstance(item, str):
        if "\x00" in item:
            raise ValueError("Schema defaults cannot contain NUL characters")
        return "'" + item.replace("'", "''") + "'"
    if isinstance(item, (bytes, bytearray, memoryview)):
        return "X'" + bytes(item).hex() + "'"
    return str(int(item)) if isinstance(item, bool) else str(item)


@dataclass(frozen=True)
class ForeignKey:
    table: str
    column: str = "id"
    on_delete: str = "RESTRICT"
    on_update: str = "RESTRICT"

    def sql(self):
        actions = {"RESTRICT", "CASCADE", "SET NULL", "SET DEFAULT", "NO ACTION"}
        delete, update = self.on_delete.upper(), self.on_update.upper()
        if delete not in actions or update not in actions:
            raise ValueError("Unsupported foreign-key action")
        return f"REFERENCES {identifier(self.table)} ({identifier(self.column)}) ON DELETE {delete} ON UPDATE {update}"


@dataclass(frozen=True)
class Column:
    type: type | str = str
    nullable: bool = True
    default: object = UNSET
    unique: bool = False
    primary_key: bool = False
    references: ForeignKey | None = None

    def sql(self):
        kind = _TYPES.get(self.type, self.type.upper() if isinstance(self.type, str) else None)
        if kind not in {"TEXT", "INTEGER", "REAL", "BLOB", "NUMERIC"}:
            raise ValueError(f"Unsupported SQLite column type: {self.type!r}")
        parts = [kind]
        if self.primary_key:
            parts.append("PRIMARY KEY")
        if not self.nullable or self.primary_key and kind != "INTEGER":
            parts.append("NOT NULL")
        if self.unique:
            parts.append("UNIQUE")
        if self.default is not UNSET:
            parts.extend(("DEFAULT", literal(self.default)))
        if self.references is not None:
            parts.append(self.references.sql())
        return " ".join(parts)
