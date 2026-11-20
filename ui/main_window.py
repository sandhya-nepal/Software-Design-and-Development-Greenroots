"""Main application window: sidebar navigation and content area."""
import tkinter as tk
from tkinter import messagebox, ttk

from ui.dashboard import DashboardView
from ui.holder_view import HolderView
from ui.plot_view import PlotView
from ui.site_view import SiteView
from ui.widgets import COLORS, FONT, FONT_BOLD, apply_theme

NAV_ITEMS = [
    ("dashboard", "Dashboard", DashboardView),
    ("sites", "Allotment Sites", SiteView),
    ("plots", "Plots", PlotView),
    ("holders", "Plot Holders", HolderView),
]


class MainWindow(tk.Tk):
    def __init__(self, app):
        super().__init__()
        self.app = app
        self.title("GreenRoots Allotment Management")
        self.geometry("1280x780")
        self.minsize(1000, 640)
        apply_theme(self)
        self.pages, self._nav_buttons = {}, {}
        self._build_layout()
        self.show_page("dashboard")

    def _build_layout(self):
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)
        sidebar = tk.Frame(self, bg=COLORS["sidebar"], width=230)
        sidebar.grid(row=0, column=0, sticky="ns")
        sidebar.pack_propagate(False)
        tk.Label(sidebar, text="GreenRoots", bg=COLORS["sidebar"], fg="white",
                 font=("Segoe UI", 18, "bold")).pack(anchor="w", padx=20, pady=(24, 2))
        tk.Label(sidebar, text="Community Association", bg=COLORS["sidebar"], fg="#b7d3bd",
                 font=FONT).pack(anchor="w", padx=20, pady=(0, 24))
        content = ttk.Frame(self)
        content.grid(row=0, column=1, sticky="nsew")
        content.rowconfigure(0, weight=1)
        content.columnconfigure(0, weight=1)
        for key, label, view_class in NAV_ITEMS:
            button = tk.Button(sidebar, text=label, anchor="w", relief="flat", bd=0, padx=20, pady=10,
                               bg=COLORS["sidebar"], fg=COLORS["sidebar_text"], font=FONT,
                               activebackground=COLORS["sidebar_hover"], activeforeground="white",
                               command=lambda k=key: self.show_page(k))
            button.pack(fill="x")
            self._nav_buttons[key] = button
            page = view_class(content, self.app, self)
            page.grid(row=0, column=0, sticky="nsew")
            self.pages[key] = page
        self.status_var = tk.StringVar(value="Ready")
        self.status_label = tk.Label(self, textvariable=self.status_var, anchor="w", bg="#e3ede5",
                                     fg=COLORS["text"], font=FONT, padx=12, pady=4)
        self.status_label.grid(row=1, column=0, columnspan=2, sticky="ew")

    def show_page(self, key):
        for name, button in self._nav_buttons.items():
            button.configure(bg=COLORS["sidebar_hover"] if name == key else COLORS["sidebar"], font=FONT_BOLD if name == key else FONT)
        self.pages[key].refresh()
        self.pages[key].tkraise()

    def set_status(self, message, error=False):
        self.status_var.set(message)
        self.status_label.configure(fg=COLORS["danger"] if error else COLORS["text"])

    def notify_success(self, message):
        self.set_status(message)
        messagebox.showinfo("Success", message, parent=self)
