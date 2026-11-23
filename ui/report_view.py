"""Management reports: site summaries, holder overview and outstanding balances."""
from tkinter import ttk

from ui.widgets import BaseView, DataTable, fmt_money


class ReportView(BaseView):
    title = "Reports"
    subtitle = "Management summaries calculated from the current records."

    def __init__(self, parent, app, window):
        super().__init__(parent, app, window)
        self.add_buttons([("Refresh", self.refresh)])
        notebook = ttk.Notebook(self.body)
        notebook.pack(fill="both", expand=True)
        tabs = {}
        for key, label in (("sites", "Site summaries"), ("holders", "Plot holder overview"), ("balances", "Outstanding balances")):
            frame = ttk.Frame(notebook, padding=8)
            notebook.add(frame, text=label)
            tabs[key] = frame
        self.site_table = DataTable(tabs["sites"], [("site", "Site", 190), ("plots", "Plots", 55), ("occ", "Occupied", 70),
                                                    ("avail", "Available", 70), ("pct", "Occupancy", 80), ("holders", "Holders", 65),
                                                    ("charges", "Charges", 90), ("paid", "Payments", 90), ("due", "Outstanding", 95)],
                                    height=14, empty_text="No sites registered.")
        self.holder_table = DataTable(tabs["holders"], [("id", "Holder ID", 80), ("name", "Name", 170), ("cat", "Membership", 150),
                                                        ("plots", "Active plots", 90), ("charges", "Charged", 90),
                                                        ("paid", "Paid", 90), ("due", "Outstanding", 95)],
                                      height=14, empty_text="No plot holders registered.")
        self.balance_table = DataTable(tabs["balances"], [("charge", "Charge", 80), ("holder", "Plot holder", 160), ("plot", "Plot", 80),
                                                          ("site", "Site", 170), ("total", "Final charge", 95), ("paid", "Paid", 85),
                                                          ("due", "Outstanding", 95), ("status", "Status", 100)],
                                       height=14, empty_text="No outstanding balances.")
        for table in (self.site_table, self.holder_table, self.balance_table):
            table.pack(fill="both", expand=True)

    def refresh(self):
        reports = self.app.reporting
        self.site_table.set_rows([(s["site_id"], (s["site_name"], s["total_plots"], s["occupied_plots"], s["available_plots"],
                                                  f"{s['occupancy_percentage']}%", s["holders_with_allocations"],
                                                  fmt_money(s["total_charges"]), fmt_money(s["total_payments"]),
                                                  fmt_money(s["outstanding_balance"]))) for s in reports.all_site_summaries()])
        self.holder_table.set_rows([(r["holder"].holder_id, (r["holder"].holder_id, r["holder"].full_name,
                                                             r["holder"].membership_category, r["active_plots"],
                                                             fmt_money(r["total_charges"]), fmt_money(r["total_paid"]),
                                                             fmt_money(r["outstanding"]))) for r in reports.holder_overview()])
        self.balance_table.set_rows([(r["charge"].charge_id, (r["charge"].charge_id, r["holder"].full_name, r["charge"].plot_id,
                                                             r["site"].name, fmt_money(r["charge"].total_amount),
                                                             fmt_money(r["charge"].amount_paid),
                                                             fmt_money(r["charge"].outstanding_balance), r["charge"].payment_status))
                                     for r in reports.outstanding_balances()])
