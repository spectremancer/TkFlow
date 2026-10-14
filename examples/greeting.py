"""Run from the project root: python -m examples.greeting."""
from TkFlow import App, Button, Label, Menu, TextInput


def build_app() -> App:
    app = App("Hello from TkFlow", height=260, width=440)
    file = Menu(app).dropdown("File")
    file.add_command("Quit", app.close)
    section = app.section("Say hello")
    Label(section, "Your name")
    name = TextInput(section, "World")
    greeting = Label(section, "Welcome!")
    Button(section, "Greet", command=lambda: greeting.set(f"Hello, {name.get()}!"))
    return app


if __name__ == "__main__":
    build_app().run()
