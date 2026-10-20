# TkFlow documentation

TkFlow is a folder of cooperating Python classes. Copy `TkFlow/` into a project; there is no package installation step or external runtime dependency. Python 3.10+ and a working Tkinter installation are required.

Read the guides in this order, or jump to a specific task:

1. [Getting started and project layout](getting-started.md): imports, main functions, layout, styling, and native access.
2. [Class reference](reference.md): window, menu, container, control, text, and logging APIs.
3. [Commands, threads, queues, and shutdown](commands.md): background work without touching Tk from workers.
4. [Building forms](forms.md): dynamic fields, validation, scrolling, snapshots, reset, and submission.
5. [Expanded toolkit API](toolkit.md): state binding, all new layouts/controls, tables, navigation, command lifecycle, and richer forms.
6. [Application architecture](architecture.md): project structure, ownership, service boundaries, extension points, and compatibility.
7. [Testing and visual review](testing.md): real-widget tests, developer helpers, screenshot reproduction, and review scope.
8. [SQLiteFlow CRUD and database integration](sqlite.md): schemas, dictionary CRUD, filters, transactions, thread-safe connections, and a persistent contacts app.
9. [Example walkthroughs](examples.md): menus, chat, GUI logs, and a schema-driven form.

TkFlow controls, native Tkinter widgets, and Tk variables belong to the main thread. `Command` provides the capture → worker → GUI callback sequence for blocking operations. Queued logging has a separate bounded buffer so high-volume logs do not require a GUI callback for every record.

The supported scope includes menus, automatic row/column layouts, common single-line controls, multiline text, reusable forms, and optional background operations. Virtualized tables, network transports, process pools, persistence, and authentication remain application concerns. DateInput is validated ISO text input, not a popup calendar.
