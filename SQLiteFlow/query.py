"""Composable parameterized predicates for CRUD operations."""
from __future__ import annotations
from collections.abc import Mapping
from .schema import identifier, value


class Q:
    """AND keyword conditions; combine with &, |, and ~. Parenthesize combinations."""
    def __init__(self, **conditions):
        self.kind, self.conditions, self.children = "conditions", conditions, ()

    def _combine(self, kind, other=None):
        if kind != "not" and not isinstance(other, Q):
            return NotImplemented
        result = Q()
        result.kind, result.children = kind, (self,) if other is None else (self, other)
        return result

    def __bool__(self):
        raise TypeError("Combine Q predicates with &, |, and ~, not and/or/not")

    def __and__(self, other):
        return self._combine("and", other)

    def __or__(self, other):
        return self._combine("or", other)

    def __invert__(self):
        return self._combine("not")

    def compile(self):
        """Return (SQL, positional parameters, constant truth or None)."""
        if self.kind != "conditions":
            items = [child.compile() for child in self.children]
            if self.kind == "not":
                sql, parameters, constant = items[0]
                return f"NOT ({sql})", parameters, None if constant is None else not constant
            sql = f" {self.kind.upper()} ".join(f"({item[0]})" for item in items)
            constants = [item[2] for item in items]
            if self.kind == "and":
                constant = False if False in constants else True if all(v is True for v in constants) else None
            else:
                constant = True if True in constants else False if all(v is False for v in constants) else None
            return sql, [p for item in items for p in item[1]], constant
        parts, parameters, constants = [], [], []
        operators = {"eq":"=", "ne":"!=", "gt":">", "gte":">=", "lt":"<", "lte":"<="}
        for expression, item in self.conditions.items():
            pieces = expression.rsplit("__", 1)
            name, operator = pieces if len(pieces) == 2 else (expression, "eq")
            column = identifier(name)
            constant = None
            if operator in ("eq", "ne") and item is None:
                sql = f"{column} IS {'NOT ' if operator == 'ne' else ''}NULL"
            elif operator == "is_null":
                if not isinstance(item, bool):
                    raise TypeError("is_null requires a bool")
                sql = f"{column} IS {'' if item else 'NOT '}NULL"
            elif operator in operators:
                sql = f"{column} {operators[operator]} ?"
                parameters.append(value(item))
            elif operator in ("in", "not_in"):
                if isinstance(item, (str, bytes, Mapping)):
                    raise TypeError("in/not_in requires an iterable of values")
                items = list(item)
                if not items:
                    constant = operator == "not_in"
                    sql = "1" if constant else "0"
                else:
                    sql = f"{column} {'NOT IN' if operator == 'not_in' else 'IN'} ({', '.join('?' for _ in items)})"
                    parameters.extend(value(entry) for entry in items)
            elif operator in ("like", "contains", "startswith", "endswith"):
                if not isinstance(item, str):
                    raise TypeError("Text predicates require a string")
                if operator != "like":
                    item = item.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
                    item = ("%" if operator in ("contains", "endswith") else "") + item + ("%" if operator in ("contains", "startswith") else "")
                sql = f"{column} LIKE ? ESCAPE '\\'"
                parameters.append(item)
            else:
                raise ValueError(f"Unknown filter operator: {operator}")
            parts.append(sql)
            constants.append(constant)
        constant = False if False in constants else True if all(v is True for v in constants) else None
        return " AND ".join(parts) or "1", parameters, constant


def predicate(where):
    if where is None:
        return Q().compile()
    if isinstance(where, Mapping):
        return Q(**where).compile()
    if isinstance(where, Q):
        return where.compile()
    raise TypeError("where must be a mapping, Q, or None; use db.query for raw SQL")
