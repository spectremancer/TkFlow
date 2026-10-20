"""Capture the SQLiteFlow example without touching persistent example data."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from TkFlow.devtools import capture_errors, pump_until
from examples.database_crud import build_app
from .capture_screenshots import capture, DESTINATION


def main():
    DESTINATION.mkdir(parents=True, exist_ok=True)
    manifest = []
    with TemporaryDirectory() as directory:
        app = build_app(Path(directory) / "contacts.sqlite3")
        try:
            with capture_errors(app) as errors:
                pump_until(app, lambda: app.demo.ready.get() and not app.demo.action.running)
                app.demo.table.select(1)
                pump_until(app, lambda: app.demo.selected.get() == 1)
                capture(app, "database-crud-wide", manifest)
                app.set_size(height=580, width=820)
                capture(app, "database-crud-compact", manifest)
                assert not errors, errors
        finally:
            app.close()
    (DESTINATION / "database-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print("Captured database example at default and compact sizes")


if __name__ == "__main__":
    main()
