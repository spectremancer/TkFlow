"""Persistent contact CRUD with SQLiteFlow and TkFlow. Run: python -m examples.database_crud."""
from pathlib import Path
from types import SimpleNamespace
from SQLiteFlow import Database, Column, Q
from TkFlow import App, Button, Form, Grid, Label, Menu, SplitPane, State, Table, TextInput, Theme


def build_app(path=None, *, seed=True):
    path = Path(__file__).resolve().parent / "data" / "contacts.sqlite3" if path is None else path
    fresh = str(path) == ":memory:" or not Path(path).exists()
    db = Database(path)
    app = App("TkFlow + SQLiteFlow - contacts", height=700, width=1000, min_height=580, min_width=820)
    Theme().apply(app)
    app.on_dispose(db.close)
    Label(app, "Contacts database", style="Title.TLabel")
    Label(app, "Create, select, edit and delete contacts. All SQL runs in a background command.",
          style="Muted.TLabel", wraplength=900)
    split = SplitPane(app, expand=True, fill="both")
    listing = split.add("contacts", weight=2, padding=4)
    editor = split.add("editor", weight=1, padding=4)
    search_row = listing.row(padding=0)
    search = TextInput(search_row, expand=True)
    table = Table(listing, {"name":"Name", "email":"Email", "role":"Role", "active":"Active"},
                  key="id", height=6, expand=True, fill="both")
    for column, width, minimum in (("name",150,140), ("email",230,210), ("role",110,90), ("active",65,60)):
        table.tree.column(column, width=width, minwidth=minimum)
    selected = State(None)
    selection_text = State("No contact selected - fill out the form to add one.")
    Label(listing, bind=selection_text, style="Muted.TLabel", wraplength=400)
    form = Form(editor, "Contact details", expand=True, fill="both", padding=8)
    form.add_text("name", "Name", required=True)
    form.add_text("email", "Email", required=True,
                  validator=lambda text: None if "@" in text else "Include an @ in the email")
    form.add_dropdown("role", "Role", ["Developer", "Designer", "Other"])
    form.add_checkbox("active", "Active contact", value=True)
    status = State("Opening database...")
    ready = State(False)
    Label(app, bind=status, wraplength=900)

    def prepare(operation):
        status.set("Working...")
        payload = {"operation": operation}
        if operation in ("create", "update"):
            payload["values"] = form.snapshot()
        if operation in ("update", "delete"):
            if selected.get() is None:
                raise ValueError("Select a contact first")
            payload["id"] = selected.get()
        payload["search"] = search.get().strip() if operation == "refresh" else ""
        return (payload,)

    def perform(payload):
        # This function touches only SQLiteFlow and plain captured data.
        operation = payload["operation"]
        with db.transaction(immediate=operation != "refresh"):
            if operation == "initialize":
                contacts = db.create_table("contacts", {
                    "name": Column(str, nullable=False),
                    "email": Column(str, nullable=False, unique=True),
                    "role": Column(str, nullable=False, default="Other"),
                    "active": Column(bool, nullable=False, default=True),
                })
                db.create_index("contacts", "name")
                if seed and fresh:
                    contacts.insert_many([
                        {"name":"Ada Lovelace", "email":"ada@example.com", "role":"Developer"},
                        {"name":"Grace Hopper", "email":"grace@example.com", "role":"Developer"},
                        {"name":"Katherine Johnson", "email":"katherine@example.com", "role":"Other"},
                    ])
            else:
                contacts = db.table("contacts")
            identity = None
            if operation == "create":
                identity = contacts.insert(payload["values"])
            elif operation == "update":
                if contacts.update(payload["id"], payload["values"]) != 1:
                    raise ValueError("That contact no longer exists; refresh the table")
                identity = payload["id"]
            elif operation == "delete":
                contacts.delete(payload["id"])
            query = payload["search"]
            where = (Q(name__contains=query) | Q(email__contains=query)) if query else None
            return {"operation":operation, "rows":contacts.find(where, order_by="name"),
                    "id":identity, "search":query}

    def render(result):
        table.set_rows(result["rows"])
        selected.set(None)
        selection_text.set("No contact selected - fill out the form to add one.")
        if result["operation"] != "refresh":
            search.set("")
            form.reset()
        if result["id"] is not None:
            table.select(result["id"])
        ready.set(True)
        verb = {"initialize":"Loaded", "refresh":"Found", "create":"Created contact; showing",
                "update":"Updated contact; showing", "delete":"Deleted contact; showing"}[result["operation"]]
        status.set(f"{verb} {len(result['rows'])} contacts")

    action = app.command(perform, prepare=prepare, on_result=render,
                         on_error=lambda error: status.set(f"Could not complete operation: {error}"))
    request = action
    buttons = {}
    action_grid = Grid(form.actions, columns=2, padding=0, spacing=4, expand=True)
    for operation, caption in (("create","Add contact"), ("update","Save selected"), ("delete","Delete selected")):
        buttons[operation] = Button(action_grid, caption, lambda operation=operation: request(operation),
                                             style="Primary.TButton" if operation == "create" else "TButton")
    buttons["refresh"] = Button(search_row, "Search / refresh", lambda: request("refresh"))
    Button(action_grid, "New / clear", lambda: (table.tree.selection_remove(*table.tree.selection()), form.reset()))

    def selection_changed(rows):
        identity = rows[0]["id"] if rows else None
        selected.set(identity)
        if rows:
            row = rows[0]
            form.set({"name":row["name"], "email":row["email"], "role":row["role"], "active":bool(row["active"])})
            form.mark_clean()
            selection_text.set(f"Editing contact #{identity}: {row['name']}")
        else:
            selection_text.set("No contact selected - fill out the form to add one.")
    table.on_select = selection_changed

    def update_buttons(_=None):
        for operation, button in buttons.items():
            enabled = not action.running and (operation not in ("update", "delete") or selected.get() is not None)
            button.enable() if enabled else button.disable()
    app.on_dispose(action.busy.subscribe(update_buttons))
    app.on_dispose(selected.subscribe(update_buttons))
    file = Menu(app).dropdown("Database")
    file.add_command("Refresh", lambda: request("refresh"))
    file.add_command("Close", app.close)
    app.shortcut("<Control-r>", lambda: request("refresh"))
    app.demo = SimpleNamespace(db=db, form=form, table=table, selected=selected, search=search,
                               action=action, request=request, status=status, ready=ready, buttons=buttons)
    request("initialize")
    return app


if __name__ == "__main__":
    build_app().run()
