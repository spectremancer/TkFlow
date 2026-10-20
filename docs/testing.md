# Testing and visual review

## Behavioral tests

From the repository root:

```bash
python -m unittest discover -s tests -v
# On headless Linux:
xvfb-run -a python -m unittest discover -s tests -v
```

The suite contains 74 tests and creates real Tk widgets. They verify state propagation and unsubscription, keyboard activation, shared-command busy state, queue saturation, coalesced progress, debounce, cancellation, owner destruction, table operations, typed and conditional forms, navigation hooks, dialogs, notifications, and each runnable example. Existing copied-folder import tests run in isolated child projects without installed packages.

Example test pattern:

```python
from TkFlow import App, Button, Label
from TkFlow.devtools import capture_errors, invoke, pump_until

app = App()
try:
    with capture_errors(app) as errors:
        status = Label(app, "Ready")
        job = app.command(lambda: "Done", on_result=status.set)
        button = Button(app, "Run", job)
        invoke(button)
        pump_until(app, lambda: status.get() == "Done")
        assert not errors
finally:
    app.close()
```

Use explicit gates or Events to test in-flight behavior. Avoid sleeps as evidence that an operation completed. Pump until the relevant rendered value holds. A LogView buffer can flush after its worker finishes; wait for the expected log content, not just a Future. Capture callback errors so a passing assertion does not conceal a failed Tk callback.

## Screenshots

Pillow is an **optional developer dependency**, not a TkFlow runtime requirement. With Pillow installed, capture native X11 windows under a virtual display:

```bash
xvfb-run -a -s '-screen 0 1600x1200x24' python -m tools.capture_screenshots
```

In the prepared cloud workspace, add `/workspace/.tkflow-env/root/usr/bin` to PATH first. Captures go to `docs/screenshots/`, with a JSON manifest recording capture names and client dimensions. The tool includes native menu-bar space above the Tk client area. It captures all workbench screens and gallery pages at default and compact sizes, a dialog, a notification, and each earlier example.

Review actual screenshots for:

- Text clipping, missing glyphs, empty canvas content, and controls hidden behind siblings.
- Buttons clipped by small cells or a short window.
- Incorrect scroll regions or action buttons lost inside scrolling content.
- Table headings/selection visibility and spacing consistency.
- Busy, disabled, focused, validation-error, dialog, and notification states.

Visual review caught canvas content behind its sibling canvas, overflow into form actions after validation, and compact grid clipping. Canvas content now has the correct native parent, and compact spacing was corrected before screenshots were regenerated. Regression tests check hit-testing of a form input and compact gallery bounds as well as geometry and behavior. Behavioral assertions alone did not reveal the original stacking problem.

[Workbench overview](screenshots/workbench-overview-wide.png) · [Compact form](screenshots/workbench-forms-compact.png) · [Busy command](screenshots/workbench-tasks-wide.png) · [Grid](screenshots/gallery-grid-compact.png) · [Input dialog](screenshots/input-dialog.png)

Screenshots and tests demonstrate the checked Linux sizes/states. They do not establish absence of every visual issue on every OS, DPI, font installation, theme, or developer-defined layout. Test native Windows/macOS, high-DPI scaling, keyboard traversal, and assistive technology when those are deployment requirements. Tables are not virtualized, dates are entered as ISO text, and grid column counts are explicit.

## Recorded review

The checked-in manifest contains 26 captures: five workbench screens at 1120×780 and 820×620 client sizes, three gallery tabs at 960×650 and 720×500, the input dialog, notification, validation-error state, selected/filtered table, and the six earlier examples. The captures were opened and visually inspected after the layout fixes. Native menu-bar height is included in image bounds in addition to client height.

The shutdown tests also force cyclic garbage collection on a worker after disposing multiple applications. Managed variables release on the GUI thread and interpreter handles are retained until final release can happen there; this prevents native Tcl finalization from being triggered on the wrong thread by a completed worker's callback graph.
