# Example walkthroughs

Run every example from the repository root with `python -m examples.NAME`. No installation, external service, or credential is required. On headless Linux use `xvfb-run -a python -m examples.NAME`.

| Module | Demonstrates |
| --- | --- |
| `examples.greeting` | Minimal App, a menu, a named input, and a button callback |
| `examples.form` | Small hand-built form and explicit background submission |
| `examples.menus` | Five top-level menus, nested menus, themes, transformations, keyboard shortcuts, and a shared background Command |
| `examples.chat` | Tagged transcript, Enter-to-send composer, busy state, and queued offline replies |
| `examples.logging_gui` | Worker logging, print-like output, batched GUI insertion, and cooperative cancellation |
| `examples.workbench` | Five complete screens combining state, components, tables, typed forms, progress/cancellation, dialogs, shortcuts, and themes |
| `examples.layout_gallery` | Resizable grids, tabs, split panes, scrolling content, and collapsible sections |
| `examples.dynamic_form` | Scrolling Form, validation, dropdowns/checkboxes, dynamic fields, reset, and submission |

## Menu workspace

[Source](../examples/menus.py)

File contains sample documents and a close command. Edit routes native text-editing events to the editor. View offers installed themes, window sizes, and status visibility. Tools contains text transformations and a background document analysis. Help opens a secondary window or a dialog.

The analysis Command is shared by the Tools menu and the Analyze button. Preparation reads the editor on the GUI thread; analysis receives a string and returns a summary. Clicking either trigger again while busy does not start duplicate analysis. Transformations and dialog commands remain synchronous because they only perform quick GUI operations.

Sample documents are built in and there is no implicit disk write. The analysis delay stands in for an external operation. Add real file dialogs on the GUI thread, then perform file work on captured paths with proper error handlers. Displayed accelerator labels do not bind keys; the Ctrl+N binding is installed explicitly.

## Chat screen

[Source](../examples/chat.py)

The transcript uses readonly TextArea with sender tags. TextInput and Send are placed in a Row. Enter and the button invoke the same Command. Preparation checks for empty text, appends the local message, clears the composer, and disables Send. The worker sees only the captured string. Result delivery appends the reply and restores the button through `on_done`.

The assistant is deliberately offline and simulated. Replace `reply(text)` with your own transport or service function and set connection/read timeouts. Do not read widgets in that function. If you add streaming, use a bounded/coalesced stream buffer rather than scheduling one GUI callback per token. This example allows one outstanding reply, preserving conversation order. Closing the app sets its stop Event and suppresses late delivery.

## GUI logging and print-like output

[Source](../examples/logging_gui.py)

The job monitor uses a named logger attached to a LogView. Start can be triggered from either the menu or a button with one shared Command. The background job emits records and calls `output.print` without accessing Tk. LogView collects chunks in a bounded queue, joins a batch, and performs one text insertion on each timer tick.

Cancel sets a worker-visible Event. The worker checks between bounded steps, emits a cancellation message, and returns status. The global App stop Event is also checked during shutdown. The handler is detached when the view is disposed, avoiding a logger retaining dead GUI references. Clear empties displayed and pending logs. Use `dropped_messages` to monitor overflow and lower the production rate or increase the limits where appropriate; this is a live viewer, not a durable audit log.

## Dynamic registration form

[Source](../examples/dynamic_form.py)

The registration form contains required name/email fields, a role dropdown, a notification checkbox, a collection of optional text fields, and three buttons. Add Another Field inserts named fields at runtime; the scrollable body grows while the action buttons stay visible.

Local validation runs before submission. Error messages appear inline and the status line also receives the validation exception. Submit sends a captured dictionary to a worker; changing fields during the simulated save does not mutate that dictionary. Reset restores all currently registered fields to their defaults.

This example simulates saving and does not persist anything. To add persistence, replace the worker with a function that receives the values dictionary and writes data safely, with cancellation/shutdown behavior appropriate to your storage system.

## Automated validation

From the repository root:

```bash
python -m unittest discover -s tests -v
# Headless Linux:
xvfb-run -a python -m unittest discover -s tests -v
```

The tests instantiate real Tk widgets, trigger example actions, wait for queued results while pumping the event loop, and assert visible output and values. They cover queue saturation, cancellation, shutdown, form validation/snapshot isolation, scrolling, log retention, and copied-folder imports. Dialog routing is mocked to keep tests noninteractive. Linux is validated in this environment; native macOS/Windows behavior still requires platform testing.

## Complete workbench and layout gallery

[Workbench source](../examples/workbench.py) · [Layout gallery source](../examples/layout_gallery.py)

The workbench has Overview, Data, Forms, Tasks, and Controls screens with retained values and back navigation. Data demonstrates stable row IDs, sorting/filtering and selection. Forms combines grouped, typed, conditionally visible fields, a scrolling body, dirty tracking and a busy submit button. Tasks demonstrates cancellation-aware work and coalesced progress. Controls connects multiple widgets to the same State and opens a nonblocking input dialog. Keyboard shortcuts include Ctrl+1/Ctrl+2 navigation and Escape cancellation.

The gallery isolates each layout so it is easy to copy a small pattern. Grid uses a wide spanning header and evenly resizing cards; Split panes uses a selected list and detail column; Scrollable content places disclosures in an independently scrollable body. Compact layouts are captured and inspected in the [screenshot workflow](testing.md).

These examples are intentionally service-free. Move domain work into separate service modules when adapting them, and keep GUI operations on the main thread. The [architecture guide](architecture.md) shows a suggested module structure.
