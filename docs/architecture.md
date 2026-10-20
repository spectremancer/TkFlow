# Designing applications with TkFlow

## Suggested project structure

```text
project/
    TkFlow/                    # Copy the whole folder; no install step.
    app/
        __init__.py
        main.py                # Compose App, Theme, navigation and shared services.
        model.py               # State values and plain domain records.
        services.py            # Blocking work with no widget access.
        views/
            __init__.py
            dashboard.py       # Component subclasses or build functions.
            settings.py
        components/
            __init__.py
            project_card.py
    tests/
        test_services.py
        test_views.py
```

Run `python -m app.main` from the project root. Keep I/O in services, State on the main thread, and widgets in components. Avoid having background services import views or read Tk variables. `examples/workbench.py` is a runnable composition of these patterns in one file so it is easy to explore; split it into modules as an application grows.

## Ownership model

An App owns its windows, bounded worker pool, dispatch queue, root shortcuts, and application cleanup hooks. A container owns its child wrappers. A wrapper owns subscriptions, native bindings, and owner-scoped timers. A Command can be associated with a Widget or Window, so work is cancelled cooperatively and late UI delivery is suppressed when that owner dies.

Hiding is not destruction. A hidden tab, disclosure, or screen retains state and resources. Navigating away does not cancel work automatically; make that policy explicit in `on_hide`. Destruction propagates through wrapper children and runs cleanup hooks. Native widgets created directly through escape hatches are outside the wrapper tree; their external resources require your cleanup registration.

Do not destroy `control.widget` directly if you want wrapper cleanup. Call `control.destroy()`. Managed Tk variables are explicitly released during disposal and must not be used afterward. Tcl interpreter final release is marshalled back to the GUI thread even when a worker triggers cyclic garbage collection. Native handles are intended for configuration and specialized behavior, with lifetime responsibility still belonging to the wrapper.

## Service and command boundary

A good service signature accepts plain captured data and, if needed, CommandContext. The prepare callback reads controls on the GUI thread; the service performs blocking work; result/error handlers update views. Share a Command when multiple triggers represent the same operation. Use separate commands for independently concurrent operations.

Use application-level coordination for critical writes and orderly shutdown. Daemon workers cannot guarantee completion after process exit. A cancellation request is cooperative and must be checked between bounded operations; sockets and file/service calls need their own timeouts. CPU-heavy services may require processes outside TkFlow's thread pool.

A Future becoming done does not mean that all rendering has completed. Command result delivery, State observers, and LogView batch insertion have separate scheduling steps. Tests should wait for the actual visible outcome they intend to assert.

## Extending controls

Subclass an existing control where possible. For a new native control, subclass Widget and call `_attach(parent, native_widget, **placement)` only after initializing the widget. For value controls, `_ValueWidget` supplies get/set for a Tk variable and cleanup. Preserve the thread guard, get/set conventions, explicit callback arguments, and layout ownership.

These underscore methods are internal extension points, not a frozen third-party plugin ABI. A custom Form control needs get/set and an edit bridge for dirty tracking. Test empty input, invalid programmatic values, user edits, state binding, disabled behavior, and disposal.

## Compatibility notes for existing TkFlow applications

The project remains a plain copyable folder with relative imports. Existing App, Menu, layouts, controls, and basic background callbacks remain supported. New behavior to account for:

- Buttons backed by a Command now disable automatically while busy. Opt out with `disable_while_running=False` if you manage this yourself.
- Form submit buttons display `Working...` while busy. Set `busy_text` to customize it.
- `Command.cancel()` also signals cooperative cancellation and cancels debounce; it still returns only the Future cancellation result.
- DateInput is ISO text input with typed date access, not a calendar popup.
- `Form.snapshot()` applies converters and omits conditionally inactive fields. `get()` remains raw and includes those values.
- Hidden rows manually removed from layout retain the original validation behavior. Use `visible_when` when conditional submission is required.
- Built-in captions use ASCII ellipses/disclosure markers for environments with limited X11 fonts.

## Choosing the right abstraction

| Need | Use |
| --- | --- |
| A shared value in several controls | State and `bind=` |
| A short UI action | Ordinary callback or synchronous Command |
| Blocking work | Command with prepare/result/error handlers |
| Progress and cancellation | CommandContext |
| Search while typing | Debounced Command; be deliberate about stale/in-flight results |
| Repeatable UI structure | Component |
| Retained multi-screen views | ScreenStack |
| Dynamic validated input | Form and schema dictionaries |
| Moderate data browsing | Table/ListView |
| High-rate output | LogView, not one `call_soon` per line |
| Native functionality not wrapped | `.widget`, `.text`, `.tree`, or `.root`, with lifecycle care |
