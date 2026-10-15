# Commands, threads, queues, and shutdown

## Choose where work runs

Quick operations that read or update widgets belong on the GUI thread. Blocking I/O, sleeps, and long computations belong outside GUI handlers. Tk cannot reliably identify whether an arbitrary function will block, so execution policy is explicit:

| API | Default execution | Typical use |
| --- | --- | --- |
| `Button(..., command=function)` / `Menu.add_command(..., function)` | GUI thread | Open a window, clear text, show a dialog |
| `Command(app, function)` / `app.command(function)` | Worker pool | Load, save, analyze, contact a service |
| `Form.add_submit(..., function)` | Worker pool after GUI validation | Submit captured form values |
| `background=True` on a basic control callback | Worker pool | Simple work with already captured inputs |

Do not automatically put widget operations in a worker. Even **reading** an Entry or StringVar in a worker is unsafe. Command solves this by separating input preparation from work and result handling.

## Reusable Command

```python
from TkFlow import Button, Menu


def fetch_report(project):
    # Blocking work, no widget reads/writes. Set timeouts on external I/O.
    return f"Report for {project}"

load = app.command(
    fetch_report,
    prepare=lambda: (project_input.get(),),
    on_result=report_label.set,
    on_error=lambda error: report_label.set(f"Failed: {error}"),
)
Button(app, "Load report", load)
Menu(app).dropdown("Reports").add_command("Load report", load)
```

The sequence is:

1. The GUI calls `load()`.
2. `prepare(*incoming_args)` runs on the GUI thread and returns a **tuple** of positional worker arguments.
3. The bounded pool executes `fetch_report(*prepared_args)`.
4. `on_result(value)` or `on_error(exception)` is queued for the GUI thread.
5. While the App remains open, `on_done()` runs on the GUI thread, including on preparation failure and queued cancellation. Shutdown suppresses all later delivery.

Without `prepare`, incoming arguments pass straight to the function. Buttons and menu items supply no arguments; Checkbox and Dropdown callbacks supply the selected value. An event handler receives a Tk event: discard it in preparation (e.g. `prepare=lambda event: (input.get(),)`) rather than passing Tk objects to a worker.

A single Command instance suppresses overlap: another invocation while `running` is true returns the current `future`. Preparation is not repeated. Sharing a Command between a menu and a button therefore also shares its busy policy. Different Command instances can run concurrently. `running` stays true through GUI delivery, not only through worker completion. The app's event loop must run for delivery and busy-state reset.

Pass a Command directly to controls. Do not also set `background=True` on the control; that would attempt to run the Command's GUI preparation inside another worker.

`background=False` on Command runs the function and its handlers on the GUI thread, useful for sharing quick GUI-only actions. Blocking operations remain inappropriate in this mode.

Optional handler failures are reported through normal Tk callback exception handling when invoked by Tk or the delivery queue. If you invoke a synchronous Command directly from Python, errors raised by its handlers can propagate to that caller. Without `on_error`, worker and preparation errors use `app.root.report_callback_exception`; they are not silently ignored. `on_done` is for quick cleanup such as re-enabling a button. A result handler cannot immediately restart the same busy Command; defer that with `app.after(0, command)` if needed.

## Pool limits and queue behavior

`App(max_workers=4, max_pending=64)` creates a lazily started pool of daemon threads. At most `max_workers` worker functions execute concurrently, with at most `max_pending` tasks waiting. Threads are reused. A full task queue raises `RuntimeError` immediately; the GUI never waits for a queue slot. Command routes submission errors to `on_error`. The simple `run_in_thread` API raises them to its caller.

The GUI callback queue is drained in batches of at most 100 callbacks and a 5 ms budget per polling cycle. This prevents a stream of small callbacks from monopolizing the event loop. The budget cannot interrupt a **single slow callback**. Keep preparation, validation, GUI completion handlers, and normal button callbacks short.

`app.call_soon(function, *args)` is thread-safe and uses the general delivery queue. This queue is unbounded to retain completion callbacks; do not stream unthrottled logs or millions of progress messages through it. Use LogView's separate bounded buffer for logs. Coalesce/rate-limit progress updates in application code when needed. Bound external operations and returned data sizes as well: a worker pool does not bound an individual operation's memory use or execution time.

## Direct worker submission

```python
future = app.run_in_thread(
    fetch_report, "My project",
    on_result=report_label.set,
    on_error=lambda error: report_label.set(str(error)),
)
```

`run_in_thread(function, *args, on_result=None, on_error=None, **kwargs)` returns a `concurrent.futures.Future`. Unlike Command, repeated submissions are separate tasks. The Future represents the worker's completion; GUI delivery can occur later. Never wait on `future.result()` or `thread.join()` in a GUI callback. For complex pipelines, chain work with result handlers.

`app.after(milliseconds, callback, *args)` schedules a GUI callback. It must itself be called on the GUI thread. `app.call_soon(callback, *args)` can be called from workers and is ignored after shutdown.

## Cancellation and closing

`command.cancel()` attempts to cancel queued work and returns a bool. A running function cannot be killed by Future cancellation. Use a `threading.Event` checked by the function:

```python
import threading

cancel = threading.Event()


def work():
    for item in items:
        if app.stop_event.is_set() or cancel.is_set():
            return "Cancelled"
        process_one_item(item)  # Must itself have a sensible time limit.
    return "Done"

def prepare():
    cancel.clear()
    return ()


start = app.command(work, prepare=prepare, on_result=status.set)
Button(app, "Start", start)
Button(app, "Cancel", cancel.set)
```

`app.stop_event` is set when closing the app. Workers may check that Event; it has no Tk dependency. Shutdown cancels queued tasks, stops idle workers, discards queued GUI deliveries, and destroys windows. Running daemon workers may continue until they finish or the process exits. Critical writes need application-level shutdown coordination; never assume a worker finishes after the window is closed.

App shutdown suppresses completion delivery. Destroying a **particular widget or secondary window** while the app remains open does not automatically cancel unrelated Command objects: guard result handlers or coordinate that lifetime. Form's own submission helper suppresses its user result/error handlers when that Form is destroyed.

For CPU-heavy workloads, Python threads may still contend for the GIL. Use a process or a separately managed service, with a GUI-safe delivery bridge and timeouts, if genuine CPU parallelism is required. TkFlow does not provide a process pool.
