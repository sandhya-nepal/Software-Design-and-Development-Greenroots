"""Site announcements page."""
import tkinter as tk
from datetime import date
from tkinter import messagebox

from ui.widgets import BaseView, ChoiceFilter, DataTable, Field, FormDialog


class AnnouncementView(BaseView):
    title = "Announcements"
    subtitle = "Publish notices for individual allotment sites."

    def __init__(self, parent, app, window):
        super().__init__(parent, app, window)
        self.add_buttons([("New Announcement", self.add_announcement), ("Edit", self.edit_announcement),
                          ("Delete", self.delete_announcement)])
        self.site_filter = ChoiceFilter(self.toolbar, "Site:", self.refresh, "All sites")
        self.site_filter.pack(side="left", padx=(20, 0))
        self.table = DataTable(self.body, [("date", "Published", 100), ("site", "Site", 200), ("title", "Title", 380)],
                               height=10, on_select=self.show_details, empty_text="No announcements to display.")
        self.table.pack(fill="x")
        self.details = tk.Text(self.body, height=8, font=("Segoe UI", 10), state="disabled", bg="white", relief="solid", bd=1, wrap="word")
        self.details.pack(fill="x", pady=(12, 0))

    def refresh(self):
        sites = self.app.allotment.list_sites()
        self.site_filter.set_choices([(s.site_id, s.name) for s in sites])
        items = self.app.announcements.list_announcements(self.site_filter.value or None)
        names = {s.site_id: s.name for s in sites}
        self.table.set_rows([(a.announcement_id, (a.publication_date.isoformat(), names[a.site_id], a.title)) for a in items])
        self.show_details(self.table.selected_id())

    def show_details(self, announcement_id):
        text = "Select an announcement to read it."
        if announcement_id and announcement_id in self.app.store.announcements:
            a = self.app.announcements.get_announcement(announcement_id)
            site = self.app.allotment.get_site(a.site_id)
            text = f"{a.title}\n{site.name} - published {a.publication_date.isoformat()}\n\n{a.description}"
        self.details.configure(state="normal")
        self.details.delete("1.0", "end")
        self.details.insert("1.0", text)
        self.details.configure(state="disabled")

    def _site_choices(self):
        return [(s.site_id, s.name) for s in self.app.allotment.list_sites()]

    def add_announcement(self):
        fields = [Field("announcement_id", "Announcement ID", hint="blank = auto"), Field("site_id", "Site", "choice", self._site_choices()),
                  Field("title", "Title"), Field("description", "Description", "multiline"),
                  Field("publication_date", "Publication date", hint="YYYY-MM-DD")]
        initial = {"announcement_id": self.app.announcements.suggest_announcement_id(),
                   "publication_date": date.today().isoformat(), "site_id": self.site_filter.value}
        FormDialog(self, "New Announcement", fields, self._save_new, initial, "Publish")

    def _save_new(self, v):
        self.app.announcements.create_announcement(v["site_id"], v["title"], v["description"], v["publication_date"], v["announcement_id"])
        self.refresh()
        self.window.notify_success("Announcement published.")

    def edit_announcement(self):
        announcement_id = self.table.selected_id()
        if not self.need_selection(announcement_id, "announcement"):
            return
        a = self.app.announcements.get_announcement(announcement_id)
        fields = [Field("announcement_id", "Announcement ID", readonly=True), Field("site_id", "Site", "choice", self._site_choices(), True),
                  Field("title", "Title"), Field("description", "Description", "multiline"),
                  Field("publication_date", "Publication date", hint="YYYY-MM-DD")]
        initial = {"announcement_id": a.announcement_id, "site_id": a.site_id, "title": a.title,
                   "description": a.description, "publication_date": a.publication_date.isoformat()}
        FormDialog(self, "Edit Announcement", fields, lambda v: self._save_edit(announcement_id, v), initial)

    def _save_edit(self, announcement_id, v):
        self.app.announcements.update_announcement(announcement_id, v["title"], v["description"], v["publication_date"])
        self.refresh()
        self.window.notify_success("Announcement updated.")

    def delete_announcement(self):
        announcement_id = self.table.selected_id()
        if not self.need_selection(announcement_id, "announcement"):
            return
        if messagebox.askyesno("Confirm deletion", "Delete this announcement? This cannot be undone.", parent=self):
            self.run(lambda: self.app.announcements.delete_announcement(announcement_id), "Announcement deleted.")
