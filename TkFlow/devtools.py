"""Small standard-library development and application-testing helpers."""
from contextlib import contextmanager
import time


def inspect_tree(owner):
    """Return a JSON-serializable wrapper tree with native geometry and state."""
    widget = owner.widget
    return {"type": type(owner).__name__, "path": str(widget),
            "mapped": bool(widget.winfo_ismapped()),
            "size": [widget.winfo_width(), widget.winfo_height()],
            "children": [inspect_tree(child) for child in getattr(owner, "_children", [])]}


@contextmanager
def capture_errors(app):
    """Temporarily collect Tk callback errors, restoring the original reporter."""
    original = app.root.report_callback_exception
    errors = []
    app.root.report_callback_exception = lambda kind, error, traceback: errors.append(error)
    try:
        yield errors
    finally:
        app.root.report_callback_exception = original


def pump_until(app, predicate, *, timeout=3):
    """Test helper: pump real GUI delivery until a condition holds, or raise."""
    deadline = time.monotonic() + timeout
    while not predicate():
        if time.monotonic() >= deadline:
            raise TimeoutError("Timed out waiting for GUI condition")
        app.root.update()
        time.sleep(0.005)
    app.root.update_idletasks()


def invoke(control):
    """Trigger a button-like wrapper using its public API."""
    return control.invoke()
