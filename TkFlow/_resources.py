"""Keep Tcl interpreter final release on the GUI thread, including cyclic GC.

A completed worker can be the last Python owner of a callback capturing an App.
Its garbage collection must not delete the Tcl interpreter from that worker.
Only the interpreter handle is retained here, not the App or its widget tree.
"""
import queue
import threading
import weakref

_pending = queue.SimpleQueue()
_interpreters = {}


def retain(app):
    token = object()
    _interpreters[token] = app.root.tk
    weakref.finalize(app, _pending.put, token)


def drain():
    if threading.current_thread() is not threading.main_thread():
        raise RuntimeError("Tcl resource cleanup must run on the GUI thread")
    while True:
        try:
            token = _pending.get_nowait()
        except queue.Empty:
            break
        _interpreters.pop(token, None)
