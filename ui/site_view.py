"""Allotment site management page."""
import tkinter as tk
from tkinter import messagebox, ttk

from ui.widgets import BaseView, DataTable, Field, FormDialog
from validation import NotFoundError


class SiteView(BaseView):
    title = "Allotment Sites"
    subtitle = "Manage sites, their managers and shared facilities."

    def __init__(self, parent, app, window):
        super().__init__(parent, app, window)
        self.add_buttons([("Add Site", self.add_site), ("Edit Site", self.edit_site), ("Delete Site", self.delete_site)])
        ttk.Label(self.toolbar, text="Search:").pack(side="left", padx=(20, 6))
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *args: self.refresh())
        ttk.Entry(self.toolbar, textvariable=self.search_var, width=28).pack(side="left")
        self.table = DataTable(self.body, [("id", "Site ID", 90), ("name", "Name", 220), ("location", "Location", 170),
                                           ("manager", "Manager", 160), ("plots", "Plots", 60)],
                               height=7, on_select=self.show_details, empty_text="No sites found. Use 'Add Site' to create one.")
        self.table.pack(fill="x")
        lower = ttk.Frame(self.body)
        lower.pack(fill="both", expand=True, pady=(12, 0))
        lower.columnconfigure(1, weight=1)
        self.details = tk.Text(lower, width=46, height=10, font=("Segoe UI", 10), state="disabled", bg="white", relief="solid", bd=1)
        self.details.grid(row=0, column=0, sticky="ns", padx=(0, 12))
        self.plot_table = DataTable(lower, [("id", "Plot ID", 90), ("size", "Size (sqm)", 90), ("location", "Location in site", 160),
                                            ("status", "Status", 90)], height=8, empty_text="Select a site to see its plots.")
        self.plot_table.grid(row=0, column=1, sticky="nsew")

    def refresh(self):
        sites = self.app.allotment.list_sites(self.search_var.get())
        self.table.set_rows([(s.site_id, (s.site_id, s.name, s.location, s.manager.name, len(s.plot_ids))) for s in sites])
        self.show_details(self.table.selected_id())

    def show_details(self, site_id):
        text, plots = "", []
        try:
            site = self.app.allotment.get_site(site_id) if site_id else None
        except NotFoundError:
            site = None
        if site:
            text = (f"{site.name}\n{site.location}\n\nDescription:\n{site.description or '-'}\n\n"
                    f"Site manager: {site.manager.name}\nEmail: {site.manager.email or '-'}\nPhone: {site.manager.phone or '-'}\n\n"
                    f"Facilities: {', '.join(site.facilities) or '-'}")
            plots = self.app.allotment.list_plots(site_id=site.site_id)
        self.details.configure(state="normal")
        self.details.delete("1.0", "end")
        self.details.insert("1.0", text or "Select a site to see its details.")
        self.details.configure(state="disabled")
        self.plot_table.set_rows([(p.plot_id, (p.plot_id, p.size, p.location_within_site, p.occupancy_status)) for p in plots],
                                 empty_text="This site has no plots." if site else "Select a site to see its plots.")

    def _fields(self, editing):
        return [Field("site_id", "Site ID", readonly=editing, hint="blank = auto"),
                Field("name", "Site name"), Field("location", "Location"),
                Field("description", "Description", "multiline"),
                Field("manager_name", "Site manager"), Field("manager_email", "Manager email"),
                Field("manager_phone", "Manager phone"),
                Field("facilities", "Facilities", hint="comma separated")]

    def add_site(self):
        initial = {"site_id": self.app.allotment.suggest_site_id()}
        FormDialog(self, "Add Allotment Site", self._fields(False), self._save_new, initial)

    def _save_new(self, values):
        self.app.allotment.add_site(values["name"], values["location"], values["description"], values["manager_name"],
                                    values["manager_email"], values["manager_phone"], values["facilities"], values["site_id"])
        self.refresh()
        self.window.notify_success("Site added successfully.")

    def edit_site(self):
        site_id = self.table.selected_id()
        if not self.need_selection(site_id, "site"):
            return
        site = self.app.allotment.get_site(site_id)
        initial = {"site_id": site.site_id, "name": site.name, "location": site.location, "description": site.description,
                   "manager_name": site.manager.name, "manager_email": site.manager.email,
                   "manager_phone": site.manager.phone, "facilities": ", ".join(site.facilities)}
        FormDialog(self, "Edit Allotment Site", self._fields(True), lambda v: self._save_edit(site_id, v), initial)

    def _save_edit(self, site_id, values):
        self.app.allotment.update_site(site_id, values["name"], values["location"], values["description"],
                                       values["manager_name"], values["manager_email"], values["manager_phone"], values["facilities"])
        self.refresh()
        self.window.notify_success("Site updated successfully.")

    def delete_site(self):
        site_id = self.table.selected_id()
        if not self.need_selection(site_id, "site"):
            return
        if messagebox.askyesno("Confirm deletion", f"Delete site {site_id}? This cannot be undone.", parent=self):
            self.run(lambda: self.app.allotment.delete_site(site_id), "Site deleted.")
