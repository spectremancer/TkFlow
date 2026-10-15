"""A scrolling schema-driven Form. Run: python -m examples.dynamic_form."""
from types import SimpleNamespace
from TkFlow import App, Form, Label, Menu


def build_app() -> App:
    app = App("TkFlow • registration form", height=640, width=720)
    form = Form(app, "Team registration", expand=True, fill="both")
    form.add_label("Enter contact details below. Use the scrollbar for additional fields.", wraplength=560)
    form.add_text("name", "Full name", required=True)
    form.add_text("email", "Email", required=True,
                  validator=lambda value: None if "@" in value else "Enter an email address containing @")
    form.add_dropdown("role", "Role", ["Developer", "Designer", "Team lead"])
    form.add_checkbox("newsletter", "Receive release notes", value=True)
    for name, label in (("team", "Team"), ("company", "Company"), ("city", "City"),
                        ("timezone", "Time zone"), ("website", "Website")):
        form.add_text(name, label)
    status = Label(app, "Required fields are validated before work starts.")

    def save(values):
        # values is an independent dictionary, captured on the GUI thread.
        if app.stop_event.wait(0.2):
            return "Cancelled"
        return f"Registered {values['name']} as {values['role']} ({len(values)} fields)"

    submit = form.add_submit("Register", save, on_result=status.set,
                             on_error=lambda error: status.set(str(error)))
    form.add_button("Reset", form.reset)
    extra_number = 0

    def add_extra():
        nonlocal extra_number
        extra_number += 1
        form.add_text(f"extra_{extra_number}", f"Extra field {extra_number}")

    form.add_button("Add another field", add_extra)
    file = Menu(app).dropdown("Form")
    file.add_command("Reset", form.reset)
    file.add_command("Close", app.close)
    app.demo = SimpleNamespace(form=form, status=status, submit=submit, add_extra=add_extra)
    return app


if __name__ == "__main__":
    build_app().run()
