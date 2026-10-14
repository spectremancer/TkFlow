"""A small form with a background command and GUI-thread completion callbacks."""
import time
from TkFlow import App, Button, Checkbox, Dropdown, Label, Menu, TextInput


def prepare_profile(name: str, role: str, notifications: bool) -> str:
    # Simulate blocking work. This function never touches widgets.
    time.sleep(0.5)
    return f"Saved {name or 'Guest'} ({role}), notifications: {'on' if notifications else 'off'}"


def build_app() -> App:
    app = App("Profile", height=390, width=560)
    menu = Menu(app)
    menu.dropdown("File").add_command("Quit", app.close)
    menu.dropdown("Help").add_command("About", lambda: app.message("TkFlow 0.1.0"))
    details = app.section("Profile details")
    Label(details, "Name")
    name = TextInput(details)
    row = details.row(padding=0)
    role = Dropdown(row, ["Developer", "Designer", "Other"], expand=True)
    notifications = Checkbox(row, "Notifications", value=True)
    status = Label(app, "Ready")

    def complete(result: str) -> None:
        status.set(result)
        save.enable()

    def failed(error: Exception) -> None:
        status.set(f"Save failed: {error}")
        save.enable()

    def submit() -> None:
        # Capture widget values on the main thread before starting the worker.
        values = (name.get(), role.get(), notifications.get())
        save.disable()
        status.set("Saving…")
        app.run_in_thread(prepare_profile, *values, on_result=complete, on_error=failed)

    save = Button(app, "Save profile", command=submit)
    return app


if __name__ == "__main__":
    build_app().run()
