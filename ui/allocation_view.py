"""Plot allocation page."""
import tkinter as tk
from datetime import date
from tkinter import messagebox, ttk

from models import ACTIVE, ENDED
from ui.widgets import BaseView, ChoiceFilter, DataTable, Field, FormDialog


class AllocationView(BaseView):
    title = "Allocations"
    subtitle = "Assign available plots to registered holders and manage existing allocations."

    def __init__(self, parent, app, window):
        super().__init__(parent, app, window)
        self.add_buttons([("New Allocation", self.new_allocation), ("Modify", self.modify_allocation),
                          ("Remove Allocation", self.remove_allocation),
                          ("Generate Charge", self.generate_charge)])
        ttk.Label(self.toolbar, text="Search:").pack(side="left", padx=(20, 6))
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *args: self.refresh())
        ttk.Entry(self.toolbar, textvariable=self.search_var, width=18).pack(side="left", padx=(0, 8))
        self.site_filter = ChoiceFilter(self.toolbar, "Site:", self.refresh, "All sites", width=22)
        self.site_filter.pack(side="left", padx=(0, 8))
        self.status_filter = ChoiceFilter(self.toolbar, "Status:", self.refresh, "All statuses", width=12)
        self.status_filter.pack(side="left")
        self.table = DataTable(self.body, [("id", "Allocation", 90), ("plot", "Plot", 80), ("site", "Site", 190),
                                           ("holder", "Plot holder", 170), ("category", "Membership", 150),
                                           ("date", "Allocated", 95), ("status", "Status", 80)],
                               height=11, on_select=self.show_details, empty_text="No allocations match the current filters.")
        self.table.pack(fill="x")
        self.details = tk.Text(self.body, height=8, font=("Segoe UI", 10), state="disabled", bg="white", relief="solid", bd=1)
        self.details.pack(fill="x", pady=(12, 0))

    def refresh(self):
        service, allotment = self.app.allocation, self.app.allotment
        self.site_filter.set_choices([(s.site_id, s.name) for s in allotment.list_sites()])
        self.status_filter.set_choices([(ACTIVE, ACTIVE), (ENDED, ENDED)])
        allocations = service.list_allocations(None, self.site_filter.value or None, self.status_filter.value or None,
                                               self.search_var.get())
        rows = []
        for a in allocations:
            d = service.allocation_details(a.allocation_id)
            rows.append((a.allocation_id, (a.allocation_id, a.plot_id, d["site"].name, d["holder"].full_name,
                                           d["holder"].membership_category, a.allocation_date.isoformat(), a.status)))
        self.table.set_rows(rows)
        self.show_details(self.table.selected_id())

    def show_details(self, allocation_id):
        text = "Select an allocation to see its details."
        if allocation_id and allocation_id in self.app.store.allocations:
            d = self.app.allocation.allocation_details(allocation_id)
            a, plot, holder, site = d["allocation"], d["plot"], d["holder"], d["site"]
            text = (f"Allocation {a.allocation_id} ({a.status})\n"
                    f"Plot: {plot.plot_id} - {plot.size} sqm, {plot.location_within_site} ({plot.occupancy_status})\n"
                    f"Site: {site.name}, {site.location}\n"
                    f"Holder: {holder.holder_id} - {holder.full_name} ({holder.membership_category})\n"
                    f"Allocated on: {a.allocation_date.isoformat()}"
                    + (f"\nEnded on: {a.end_date.isoformat()}" if a.end_date else ""))
        self.details.configure(state="normal")
        self.details.delete("1.0", "end")
        self.details.insert("1.0", text)
        self.details.configure(state="disabled")

    def _plot_choices(self, include=None):
        plots = list(self.app.allocation.list_available_plots())
        if include and include not in [p.plot_id for p in plots]:
            plots.append(self.app.allotment.get_plot(include))
        return [(p.plot_id, f"{p.plot_id} - {self.app.allotment.get_site(p.site_id).name}, {p.size} sqm, {p.location_within_site}")
                for p in sorted(plots, key=lambda p: p.plot_id)]

    def _holder_choices(self):
        return [(h.holder_id, f"{h.full_name} ({h.holder_id}, {h.membership_category})") for h in self.app.allotment.list_holders()]

    def new_allocation(self):
        fields = [Field("allocation_id", "Allocation ID", hint="blank = auto"),
                  Field("plot_id", "Available plot", "choice", self._plot_choices()),
                  Field("holder_id", "Plot holder", "choice", self._holder_choices()),
                  Field("allocation_date", "Allocation date", hint="YYYY-MM-DD")]
        initial = {"allocation_id": self.app.allocation.suggest_allocation_id(), "allocation_date": date.today().isoformat()}
        FormDialog(self, "New Allocation", fields, self._save_new, initial, "Allocate")

    def _save_new(self, v):
        self.app.allocation.create_allocation(v["plot_id"], v["holder_id"], v["allocation_date"], v["allocation_id"])
        self.window.refresh_all()
        self.window.notify_success("Plot allocated successfully.")

    def modify_allocation(self):
        allocation_id = self.table.selected_id()
        if not self.need_selection(allocation_id, "allocation"):
            return
        a = self.app.allocation.get_allocation(allocation_id)
        fields = [Field("allocation_id", "Allocation ID", readonly=True),
                  Field("plot_id", "Plot", "choice", self._plot_choices(a.plot_id)),
                  Field("holder_id", "Plot holder", "choice", self._holder_choices()),
                  Field("allocation_date", "Allocation date", hint="YYYY-MM-DD")]
        initial = {"allocation_id": a.allocation_id, "plot_id": a.plot_id, "holder_id": a.holder_id,
                   "allocation_date": a.allocation_date.isoformat()}
        FormDialog(self, "Modify Allocation", fields, lambda v: self._save_edit(allocation_id, v), initial)

    def _save_edit(self, allocation_id, v):
        self.app.allocation.modify_allocation(allocation_id, v["plot_id"], v["holder_id"], v["allocation_date"])
        self.window.refresh_all()
        self.window.notify_success("Allocation updated successfully.")

    def generate_charge(self):
        allocation_id = self.table.selected_id()
        if not self.need_selection(allocation_id, "allocation"):
            return
        fields = [Field("period", "Charging period", hint="e.g. 2026")]
        FormDialog(self, f"Generate Charge for {allocation_id}", fields,
                   lambda v: self._save_charge(allocation_id, v), {"period": str(date.today().year)}, "Generate")

    def _save_charge(self, allocation_id, v):
        charge = self.app.finance.generate_charge(allocation_id, v["period"])
        self.window.refresh_all()
        self.window.notify_success(f"Charge {charge.charge_id} generated for {charge.plot_id}: £{charge.total_amount}.")

    def remove_allocation(self):
        allocation_id = self.table.selected_id()
        if not self.need_selection(allocation_id, "allocation"):
            return
        if messagebox.askyesno("Confirm removal", f"Remove allocation {allocation_id}? The plot will become available.", parent=self):
            self.run(lambda: self.app.allocation.remove_allocation(allocation_id), "Allocation removed.")
