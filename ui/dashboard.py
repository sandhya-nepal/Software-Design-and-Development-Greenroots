"""Management dashboard: every figure comes from ReportingService."""
from tkinter import ttk

from ui.widgets import BaseView, DataTable, StatCard, fmt_money

CARDS = [("total_sites", "Total sites", None), ("total_plots", "Total plots", None),
         ("occupied_plots", "Occupied plots", None), ("available_plots", "Available plots", None),
         ("total_holders", "Plot holders", None), ("active_allocations", "Active allocations", None),
         ("total_charges", "Total maintenance charges", "money"), ("total_payments", "Total successful payments", "money"),
         ("total_outstanding", "Total outstanding balance", "money")]


class DashboardView(BaseView):
    title = "Dashboard"
    subtitle = "A live overview of sites, occupancy and finances."

    def __init__(self, parent, app, window):
        super().__init__(parent, app, window)
        grid = ttk.Frame(self.body)
        grid.pack(fill="x")
        self.cards = {}
        for index, (key, label, kind) in enumerate(CARDS):
            card = StatCard(grid, label)
            card.grid(row=index // 3, column=index % 3, sticky="ew", padx=6, pady=6)
            grid.columnconfigure(index % 3, weight=1)
            self.cards[key] = (card, kind)
        ttk.Label(self.body, text="Site occupancy", font=("Segoe UI", 13, "bold")).pack(anchor="w", pady=(18, 6))
        self.table = DataTable(self.body, [("site", "Site", 240), ("total", "Plots", 80), ("occupied", "Occupied", 90),
                                           ("available", "Available", 90), ("percent", "Occupancy", 100)],
                               height=6, empty_text="No sites registered yet.")
        self.table.pack(fill="x")

    def refresh(self):
        stats = self.app.reporting.dashboard_stats()
        for key, (card, kind) in self.cards.items():
            card.set(fmt_money(stats[key]) if kind == "money" else stats[key])
        summaries = self.app.reporting.all_site_summaries()
        self.table.set_rows([(s["site_id"], (s["site_name"], s["total_plots"], s["occupied_plots"], s["available_plots"],
                                             f"{s['occupancy_percentage']}%")) for s in summaries])
