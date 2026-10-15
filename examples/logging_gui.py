"""Worker logs and print-like output. Run: python -m examples.logging_gui."""
import logging
import threading
from types import SimpleNamespace
from TkFlow import App, Button, Dropdown, Label, LogView, Menu


def build_app() -> App:
    app = App("TkFlow • job monitor", height=520, width=840, max_workers=2)
    controls = app.row(padding=0)
    count = Dropdown(controls, ["10", "50", "200"], value="10")
    status = Label(app, "Choose a job length, then start.")
    output = LogView(app, expand=True, fill="both", max_lines=500, max_pending=500)
    logger = logging.getLogger(f"TkFlow.job-monitor.{id(app)}")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    output.attach_logger(logger)
    cancel_event = threading.Event()

    def prepare():
        cancel_event.clear()
        status.set("Working…")
        return (int(count.get()),)

    def run_job(steps):
        logger.info("Starting %s steps", steps)
        for step in range(steps):
            if app.stop_event.is_set() or cancel_event.wait(0.02):
                logger.warning("Stopped after %s steps", step)
                return "Cancelled"
            logger.info("Step %s/%s completed", step + 1, steps)
        output.print("Print-like output also works directly from this worker.")
        return f"Completed {steps} steps"

    start = app.command(run_job, prepare=prepare, on_result=status.set,
                        on_error=lambda error: logger.error("Job failed: %s", error))
    Button(controls, "Start job", start)
    Button(controls, "Cancel running job", cancel_event.set)
    Button(controls, "Clear output", output.clear)
    job = Menu(app).dropdown("Job")
    job.add_command("Start", start)
    job.add_command("Cancel", cancel_event.set)
    job.separator()
    job.add_command("Close", app.close)
    output.print("Ready. Logs are buffered and inserted in batches.")
    app.demo = SimpleNamespace(output=output, start=start, cancel=cancel_event, status=status, logger=logger)
    return app


if __name__ == "__main__":
    build_app().run()
