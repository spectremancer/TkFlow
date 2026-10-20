"""An offline chat screen with safely queued replies. Run: python -m examples.chat."""
from types import SimpleNamespace
from TkFlow import App, Button, Label, Menu, TextArea, TextInput


def build_app() -> App:
    app = App("TkFlow - local chat", height=560, width=740)
    transcript = TextArea(app, readonly=True, max_lines=1000, expand=True, fill="both")
    transcript.text.tag_configure("you", foreground="#175cd3")
    transcript.text.tag_configure("assistant", foreground="#067647")
    transcript.append("Local assistant: Hello! This demo uses simulated replies, no API key.\n\n", tag="assistant")
    composer = app.row(padding=0)
    message = TextInput(composer, expand=True)
    status = Label(app, "Ready")

    def prepare():
        text = message.get().strip()
        if not text:
            raise ValueError("Type a message first")
        transcript.append(f"You: {text}\n\n", tag="you")
        message.set("")
        status.set("Preparing reply... You can still resize and scroll.")
        send.disable()
        return (text,)

    def reply(text):
        if app.stop_event.wait(0.25):
            return None
        return f"You said: {text}. Replace reply() with your service call (with a timeout)."

    def received(text):
        if text is not None:
            transcript.append(f"Local assistant: {text}\n\n", tag="assistant")
            status.set("Ready")

    action = app.command(reply, prepare=prepare, on_result=received,
                         on_error=lambda error: status.set(str(error)), on_done=lambda: send.enable())
    send = Button(composer, "Send", action)

    def enter(event):
        send.invoke()
        return "break"

    message.bind("<Return>", enter)
    conversation = Menu(app).dropdown("Conversation")
    conversation.add_command("Clear transcript", transcript.clear)
    conversation.add_command("Close", app.close)
    message.widget.focus_set()
    app.demo = SimpleNamespace(transcript=transcript, message=message, status=status, send=send, action=action)
    return app


if __name__ == "__main__":
    build_app().run()
