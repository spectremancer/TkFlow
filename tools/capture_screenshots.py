"""Capture real Tk windows. Run under Xvfb: python -m tools.capture_screenshots.

Pillow is an optional developer dependency; the TkFlow folder does not import it.
"""
from pathlib import Path
import json
from PIL import ImageGrab
from TkFlow.devtools import capture_errors, pump_until

DESTINATION = Path(__file__).resolve().parents[1] / "docs" / "screenshots"


def capture(owner, name, manifest):
    root = owner.root
    root.update()
    root.lift()
    root.update_idletasks()
    # Native menu bars are above Tk's client root on X11. Include that region.
    bounds = (root.winfo_x(), root.winfo_y(),
              root.winfo_rootx() + root.winfo_width(), root.winfo_rooty() + root.winfo_height())
    for child in root.tk.call("winfo", "children", str(root)):
        if root.tk.call("winfo", "class", child) == "Menu" and root.tk.call("winfo", "ismapped", child):
            bounds = (bounds[0], min(bounds[1], int(root.tk.call("winfo", "rooty", child))), bounds[2], bounds[3])
    ImageGrab.grab(bbox=bounds).save(DESTINATION / f"{name}.png")
    manifest.append({"name": name, "width": root.winfo_width(), "height": root.winfo_height()})


def main():
    DESTINATION.mkdir(parents=True, exist_ok=True)
    manifest = []
    from examples.workbench import build_app
    app = build_app()
    try:
        with capture_errors(app) as errors:
            for width, height, suffix in ((1120, 780, "wide"), (820, 620, "compact")):
                app.set_size(height, width)
                for name in app.demo.pages:
                    app.demo.stack.show_screen(name)
                    app.root.update()
                    if name == "Tasks":
                        app.demo.task()
                        pump_until(app, lambda: app.demo.progress.get() >= 25 or not app.demo.task.running)
                    capture(app, f"workbench-{name.lower()}-{suffix}", manifest)
                    if app.demo.task.running:
                        pump_until(app, lambda: not app.demo.task.running)
            app.demo.stack.show_screen("Forms")
            app.demo.form.set({"name": "", "email": "invalid"})
            app.demo.form.validate()
            capture(app, "form-validation", manifest)
            app.demo.form.reset()
            app.demo.stack.show_screen("Data")
            app.demo.search.set("Ada")
            pump_until(app, lambda: len(app.demo.table.rows()) == 1)
            app.demo.table.select(1)
            capture(app, "table-selection", manifest)
            from TkFlow import InputDialog
            dialog = InputDialog(app, "Choose a workspace name", value="Explorer", modal=False)
            capture(dialog, "input-dialog", manifest)
            dialog.close()
            app.demo.stack.show_screen("Overview")
            toast = app.notify("Settings saved successfully", kind="success", duration=0)
            capture(app, "notification", manifest)
            toast.destroy()
            assert not errors, errors
    finally:
        app.close()
    from examples.layout_gallery import build_app
    app = build_app()
    try:
        with capture_errors(app) as errors:
            for width, height, suffix in ((960, 650, "wide"), (720, 500, "compact")):
                app.set_size(height, width)
                for name in app.demo.tabs.pages:
                    app.demo.tabs.select(name)
                    capture(app, f"gallery-{name.lower().replace(' ', '-')}-{suffix}", manifest)
            assert not errors, errors
    finally:
        app.close()
    import importlib
    for name in ("greeting", "form", "menus", "chat", "logging_gui", "dynamic_form"):
        app = importlib.import_module(f"examples.{name}").build_app()
        try:
            with capture_errors(app) as errors:
                capture(app, f"example-{name}", manifest)
                assert not errors, errors
        finally:
            app.close()
    (DESTINATION / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"Captured {len(manifest)} screenshots in {DESTINATION}")


if __name__ == "__main__":
    main()
