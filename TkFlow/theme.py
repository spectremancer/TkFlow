"""Centralized typography, spacing and semantic ttk styles."""
from dataclasses import dataclass
from tkinter import font


@dataclass(frozen=True)
class Theme:
    accent: str = "#2156bd"
    background: str = "#f4f6fa"
    surface: str = "#ffffff"
    text: str = "#172b4d"
    muted: str = "#526581"
    danger: str = "#b42318"
    font_size: int = 10
    spacing: int = 8

    def apply(self, app):
        app._check_thread()
        # Use available system fonts rather than assume one OS-specific family.
        default = font.nametofont("TkDefaultFont", root=app.root)
        default.configure(size=self.font_size)
        style = app.style
        if "clam" in style.theme_names():
            style.theme_use("clam")
        style.configure(".", font=default, background=self.background, foreground=self.text)
        style.configure("TFrame", background=self.background)
        style.configure("TLabelframe", background=self.background, padding=self.spacing)
        style.configure("TLabelframe.Label", foreground=self.text, background=self.background)
        style.configure("TButton", padding=(12, 7))
        style.configure("Primary.TButton", background=self.accent, foreground="#ffffff")
        style.map("Primary.TButton", background=[("disabled", "#c5cfdf"), ("active", "#194697")],
                  foreground=[("disabled", "#526581")])
        style.configure("Danger.TButton", foreground=self.danger)
        style.configure("Muted.TLabel", foreground=self.muted)
        style.configure("Title.TLabel", font=(default.actual("family"), self.font_size + 8, "bold"))
        style.configure("Heading.TLabel", font=(default.actual("family"), self.font_size + 2, "bold"))
        style.configure("Error.TLabel", foreground=self.danger)
        style.configure("Treeview", rowheight=30, background=self.surface, fieldbackground=self.surface)
        style.configure("Treeview.Heading", padding=8)
        app.root.configure(background=self.background)
        app.appearance = self
        return self
