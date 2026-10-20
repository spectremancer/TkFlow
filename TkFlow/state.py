"""Observable application state owned by the thread that creates it."""
from __future__ import annotations
import threading
from typing import Callable, Generic, TypeVar

T = TypeVar("T")


class State(Generic[T]):
    """A shared value with explicit subscriptions; mutate on its owning GUI thread."""

    def __init__(self, value: T):
        self._value = value
        self._thread = threading.get_ident()
        self._subscribers = {}
        self._next = 0

    def _check(self):
        if threading.get_ident() != self._thread:
            raise RuntimeError("State belongs to its creating thread; use app.call_soon(state.set, value)")

    def get(self) -> T:
        self._check()
        return self._value

    def set(self, value: T):
        self._check()
        if value != self._value:
            self._value = value
            for callback in tuple(self._subscribers.values()):
                callback(value)
        return self

    def update(self, function: Callable[[T], T]):
        return self.set(function(self.get()))

    def subscribe(self, callback, *, immediate=True):
        self._check()
        if not callable(callback):
            raise TypeError("callback must be callable")
        token = self._next
        self._next += 1
        self._subscribers[token] = callback
        try:
            if immediate:
                callback(self._value)
        except Exception:
            self._subscribers.pop(token, None)
            raise
        def unsubscribe():
            self._check()
            self._subscribers.pop(token, None)
        return unsubscribe
