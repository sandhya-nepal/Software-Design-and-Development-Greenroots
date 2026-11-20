"""Plot holder registration page."""
import tkinter as tk
from tkinter import messagebox, ttk

from models import MEMBERSHIP_TYPES
from ui.widgets import BaseView, ChoiceFilter, DataTable, Field, FormDialog


class HolderView(BaseView):
    title = "Plot Holders"
    subtitle = "Register and maintain plot holders and their membership category."

    def __init__(self, parent, app, window):
        super().__init__(parent, app, window)
        self.add_buttons([("Register Holder", self.add_holder), ("Edit Holder", self.edit_holder), ("Delete Holder", self.delete_holder)])
        ttk.Label(self.toolbar, text="Search name or ID:").pack(side="left", padx=(20, 6))
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *args: self.refresh())
        ttk.Entry(self.toolbar, textvariable=self.search_var, width=22).pack(side="left", padx=(0, 10))
        self.category_filter = ChoiceFilter(self.toolbar, "Membership:", self.refresh, "All categories", width=22)
        self.category_filter.pack(side="left")
        self.table = DataTable(self.body, [("id", "Holder ID", 90), ("name", "Full name", 180), ("category", "Membership", 160),
                                           ("email", "Email", 220), ("phone", "Phone", 120), ("address", "Address", 220)],
                               height=16, empty_text="No plot holders found.")
        self.table.pack(fill="both", expand=True)

    def refresh(self):
        self.category_filter.set_choices([(c, c) for c in MEMBERSHIP_TYPES])
        holders = self.app.allotment.list_holders(self.search_var.get(), self.category_filter.value or None)
        self.table.set_rows([(h.holder_id, (h.holder_id, h.full_name, h.membership_category, h.email, h.phone, h.address)) for h in holders])

    def _fields(self, editing):
        categories = [(c, c) for c in MEMBERSHIP_TYPES]
        return [Field("holder_id", "Holder ID", readonly=editing, hint="blank = auto"), Field("full_name", "Full name"),
                Field("category", "Membership", "choice", categories), Field("address", "Address"),
                Field("email", "Email"), Field("phone", "Phone")]

    def add_holder(self):
        initial = {"holder_id": self.app.allotment.suggest_holder_id(), "category": "Standard Member"}
        FormDialog(self, "Register Plot Holder", self._fields(False), self._save_new, initial)

    def _save_new(self, v):
        self.app.allotment.add_holder(v["category"], v["full_name"], v["address"], v["email"], v["phone"], v["holder_id"])
        self.refresh()
        self.window.notify_success("Plot holder registered successfully.")

    def edit_holder(self):
        holder_id = self.table.selected_id()
        if not self.need_selection(holder_id, "holder"):
            return
        h = self.app.allotment.get_holder(holder_id)
        initial = {"holder_id": h.holder_id, "full_name": h.full_name, "category": h.membership_category,
                   "address": h.address, "email": h.email, "phone": h.phone}
        FormDialog(self, "Edit Plot Holder", self._fields(True), lambda v: self._save_edit(holder_id, v), initial)

    def _save_edit(self, holder_id, v):
        self.app.allotment.update_holder(holder_id, v["category"], v["full_name"], v["address"], v["email"], v["phone"])
        self.refresh()
        self.window.notify_success("Plot holder updated successfully.")

    def delete_holder(self):
        holder_id = self.table.selected_id()
        if not self.need_selection(holder_id, "holder"):
            return
        if messagebox.askyesno("Confirm deletion", f"Delete holder {holder_id}? This cannot be undone.", parent=self):
            self.run(lambda: self.app.allotment.delete_holder(holder_id), "Plot holder deleted.")
