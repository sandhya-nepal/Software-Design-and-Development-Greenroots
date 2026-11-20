"""Landing page. Reporting arrives in a later stage; for now it orients the user."""
from tkinter import ttk

from ui.widgets import BaseView


class DashboardView(BaseView):
    title = "Dashboard"
    subtitle = "Welcome to the GreenRoots Allotment Management System."

    def __init__(self, parent, app, window):
        super().__init__(parent, app, window)
        intro = [
            "Use the sidebar to work through the core records:",
            "  - Allotment Sites: register sites, managers and shared facilities.",
            "  - Plots: add plots to sites and review their occupancy status.",
            "  - Plot Holders: register standard and concessionary members.",
        ]
        for line in intro:
            ttk.Label(self.body, text=line).pack(anchor="w", pady=2)
