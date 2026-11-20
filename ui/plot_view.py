"""Allotment plot management page."""
import tkinter as tk
from tkinter import messagebox, ttk

from models import AVAILABLE, OCCUPIED
from ui.widgets import BaseView, ChoiceFilter, DataTable, Field, FormDialog


class PlotView(BaseView):
    title = "Plots"
    subtitle = "Manage individual plots and review which are occupied or available."

    def __init__(self, parent, app, window):
        super().__init__(parent, app, window)
        self.add_buttons([("Add Plot", self.add_plot), ("Edit Plot", self.edit_plot), ("Delete Plot", self.delete_plot)])
        self.site_filter = ChoiceFilter(self.toolbar, "Site:", self.refresh, "All sites")
        self.site_filter.pack(side="left", padx=(20, 8))
        self.status_filter = ChoiceFilter(self.toolbar, "Status:", self.refresh, "All plots", width=12)
        self.status_filter.pack(side="left")
        self.table = DataTable(self.body, [("id", "Plot ID", 90), ("site", "Site", 220), ("size", "Size (sqm)", 100),
                                           ("location", "Location in site", 200), ("status", "Status", 100)],
                               height=16, empty_text="No plots match the current filters.")
        self.table.pack(fill="both", expand=True)

    def refresh(self):
        service = self.app.allotment
        self.site_filter.set_choices([(s.site_id, s.name) for s in service.list_sites()])
        self.status_filter.set_choices([(AVAILABLE, AVAILABLE), (OCCUPIED, OCCUPIED)])
        plots = service.list_plots(self.site_filter.value or None, self.status_filter.value or None)
        rows = [(p.plot_id, (p.plot_id, service.get_site(p.site_id).name, p.size, p.location_within_site, p.occupancy_status)) for p in plots]
        self.table.set_rows(rows)

    def _site_choices(self):
        return [(s.site_id, f"{s.site_id} - {s.name}") for s in self.app.allotment.list_sites()]

    def add_plot(self):
        fields = [Field("plot_id", "Plot ID", hint="blank = auto"), Field("site_id", "Site", "choice", self._site_choices()),
                  Field("size", "Size (sqm)"), Field("location_within_site", "Location in site")]
        FormDialog(self, "Add Plot", fields, self._save_new, {"plot_id": self.app.allotment.suggest_plot_id()})

    def _save_new(self, values):
        self.app.allotment.add_plot(values["site_id"], values["size"], values["location_within_site"], values["plot_id"])
        self.refresh()
        self.window.notify_success("Plot added successfully.")

    def edit_plot(self):
        plot_id = self.table.selected_id()
        if not self.need_selection(plot_id, "plot"):
            return
        plot = self.app.allotment.get_plot(plot_id)
        fields = [Field("plot_id", "Plot ID", readonly=True), Field("site_id", "Site", "choice", self._site_choices(), True),
                  Field("size", "Size (sqm)"), Field("location_within_site", "Location in site")]
        initial = {"plot_id": plot.plot_id, "site_id": plot.site_id, "size": str(plot.size),
                   "location_within_site": plot.location_within_site}
        FormDialog(self, "Edit Plot", fields, lambda v: self._save_edit(plot_id, v), initial)

    def _save_edit(self, plot_id, values):
        self.app.allotment.update_plot(plot_id, values["size"], values["location_within_site"])
        self.refresh()
        self.window.notify_success("Plot updated successfully.")

    def delete_plot(self):
        plot_id = self.table.selected_id()
        if not self.need_selection(plot_id, "plot"):
            return
        if messagebox.askyesno("Confirm deletion", f"Delete plot {plot_id}? This cannot be undone.", parent=self):
            self.run(lambda: self.app.allotment.delete_plot(plot_id), "Plot deleted.")
