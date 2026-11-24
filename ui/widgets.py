"""Reusable Tkinter building blocks shared by every page."""
import sys
import tkinter as tk
import traceback
from collections import namedtuple
from tkinter import messagebox, ttk

from validation import GreenRootsError

COLORS = {
    "sidebar": "#1f4d2c", "sidebar_hover": "#2e7d46", "sidebar_text": "#f0f7f1",
    "page": "#f4f8f4", "card": "#ffffff", "accent": "#2e7d46", "text": "#1d2b20",
    "muted": "#5c6b60", "danger": "#b3261e", "border": "#d3ded5",
}
FONT = ("Segoe UI", 10)
FONT_BOLD = ("Segoe UI", 10, "bold")
FONT_TITLE = ("Segoe UI", 20, "bold")


def report_unexpected(parent, error):
    """Last-resort handler so an unexpected bug never crashes the window."""
    traceback.print_exception(type(error), error, error.__traceback__, file=sys.stderr)
    messagebox.showerror("Unexpected problem", "Something went wrong and the operation could not be completed. "
                         "Please check your entries and try again.", parent=parent)


def fmt_money(amount):
    return f"£{amount:,.2f}"


def apply_theme(root):
    root.configure(bg=COLORS["page"])
    style = ttk.Style(root)
    style.theme_use("clam")
    style.configure(".", font=FONT, background=COLORS["page"], foreground=COLORS["text"])
    style.configure("TFrame", background=COLORS["page"])
    style.configure("Card.TFrame", background=COLORS["card"], relief="solid", borderwidth=1)
    style.configure("TLabel", background=COLORS["page"])
    style.configure("Title.TLabel", font=FONT_TITLE, foreground=COLORS["sidebar"])
    style.configure("Muted.TLabel", foreground=COLORS["muted"])
    style.configure("Error.TLabel", foreground=COLORS["danger"])
    style.configure("TButton", padding=(12, 6))
    style.configure("Accent.TButton", background=COLORS["accent"], foreground="white")
    style.map("Accent.TButton", background=[("active", COLORS["sidebar"])])
    style.configure("Treeview", rowheight=26, font=FONT, fieldbackground=COLORS["card"])
    style.configure("Treeview.Heading", font=FONT_BOLD)
    style.map("Treeview", background=[("selected", COLORS["accent"])], foreground=[("selected", "white")])


class StatCard(tk.Frame):
    """A dashboard summary card showing one live figure."""

    def __init__(self, parent, title, accent=None):
        super().__init__(parent, bg=COLORS["card"], highlightbackground=COLORS["border"], highlightthickness=1,
                         padx=16, pady=12)
        tk.Label(self, text=title, bg=COLORS["card"], fg=COLORS["muted"], font=FONT).pack(anchor="w")
        self.value_label = tk.Label(self, text="-", bg=COLORS["card"], fg=accent or COLORS["sidebar"],
                                    font=("Segoe UI", 22, "bold"))
        self.value_label.pack(anchor="w")

    def set(self, value):
        self.value_label.configure(text=str(value))


class DataTable(ttk.Frame):
    """A Treeview with a scrollbar and an empty-state message."""

    def __init__(self, parent, columns, empty_text="No records to display.", height=10,
                 on_select=None, on_activate=None):
        super().__init__(parent)
        self._empty_text = empty_text
        self.tree = ttk.Treeview(self, columns=[c[0] for c in columns], show="headings",
                                 height=height, selectmode="browse")
        for key, heading, width in columns:
            self.tree.heading(key, text=heading)
            self.tree.column(key, width=width, anchor="w", stretch=True)
        scroll = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        scroll.grid(row=0, column=1, sticky="ns")
        self.empty_label = ttk.Label(self, text="", style="Muted.TLabel")
        self.empty_label.grid(row=1, column=0, columnspan=2, sticky="w", pady=(4, 0))
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        if on_select:
            self.tree.bind("<<TreeviewSelect>>", lambda event: on_select(self.selected_id()))
        if on_activate:
            self.tree.bind("<Double-1>", lambda event: on_activate(self.selected_id()))

    def set_rows(self, rows, empty_text=None):
        keep = self.selected_id()
        self.tree.delete(*self.tree.get_children())
        for iid, values in rows:
            self.tree.insert("", "end", iid=str(iid), values=values)
        self.empty_label.configure(text="" if rows else (empty_text or self._empty_text))
        if keep and self.tree.exists(keep):
            self.tree.selection_set(keep)

    def selected_id(self):
        selection = self.tree.selection()
        return selection[0] if selection else None


class ChoiceFilter(ttk.Frame):
    """A labelled drop-down whose entries map display text to a value."""

    def __init__(self, parent, label, on_change, all_label="All", width=28):
        super().__init__(parent)
        self._all_label = all_label
        self._map = {all_label: ""}
        ttk.Label(self, text=label).pack(side="left", padx=(0, 6))
        self.var = tk.StringVar(value=all_label)
        self.combo = ttk.Combobox(self, textvariable=self.var, state="readonly", width=width)
        self.combo.pack(side="left")
        self.combo.bind("<<ComboboxSelected>>", lambda event: on_change())
        self.set_choices([])

    def set_choices(self, choices):
        current = self.value
        self._map = {self._all_label: ""}
        self._map.update({label: value for value, label in choices})
        self.combo.configure(values=list(self._map))
        self.var.set(next((l for l, v in self._map.items() if v == current), self._all_label))

    @property
    def value(self):
        return self._map.get(self.var.get(), "")


Field = namedtuple("Field", "key label kind choices readonly hint", defaults=("text", None, False, ""))


class FormDialog(tk.Toplevel):
    """Modal form built from Field definitions. on_submit(values) may raise GreenRootsError."""

    def __init__(self, parent, title, fields, on_submit, initial=None, submit_text="Save", note=""):
        super().__init__(parent)
        self.title(title)
        self.configure(bg=COLORS["page"])
        self.transient(parent.winfo_toplevel())
        self.resizable(False, False)
        self._fields, self._on_submit = fields, on_submit
        self._inputs = {}
        initial = initial or {}
        body = ttk.Frame(self, padding=18)
        body.pack(fill="both", expand=True)
        offset = 0
        if note:
            ttk.Label(body, text=note, style="Muted.TLabel", wraplength=480).grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 8))
            offset = 1
        for index, field in enumerate(fields):
            row = index + offset
            ttk.Label(body, text=field.label).grid(row=row, column=0, sticky="nw", padx=(0, 12), pady=6)
            widget = self._build_input(body, field, initial.get(field.key, ""))
            widget.grid(row=row, column=1, sticky="ew", pady=6)
            if field.hint:
                ttk.Label(body, text=field.hint, style="Muted.TLabel").grid(row=row, column=2, sticky="w", padx=(8, 0))
        buttons = ttk.Frame(body)
        buttons.grid(row=len(fields) + offset, column=0, columnspan=3, sticky="e", pady=(14, 0))
        ttk.Button(buttons, text="Cancel", command=self.destroy).pack(side="right", padx=(8, 0))
        ttk.Button(buttons, text=submit_text, style="Accent.TButton", command=self._submit).pack(side="right")
        self.bind("<Escape>", lambda event: self.destroy())
        self.update_idletasks()
        x = parent.winfo_toplevel().winfo_rootx() + 120
        y = parent.winfo_toplevel().winfo_rooty() + 60
        self.geometry(f"+{x}+{y}")
        self.grab_set()

    def _build_input(self, parent, field, initial):
        if field.kind == "multiline":
            widget = tk.Text(parent, width=38, height=3, font=FONT, wrap="word")
            widget.insert("1.0", initial)
            self._inputs[field.key] = ("multiline", widget, None)
            return widget
        if field.kind == "choice":
            mapping = {label: value for value, label in (field.choices or [])}
            variable = tk.StringVar(value=next((l for l, v in mapping.items() if v == initial), ""))
            widget = ttk.Combobox(parent, textvariable=variable, values=list(mapping), width=36,
                                  state="disabled" if field.readonly else "readonly")
            self._inputs[field.key] = ("choice", variable, mapping)
            return widget
        variable = tk.StringVar(value=str(initial))
        widget = ttk.Entry(parent, textvariable=variable, width=40, state="readonly" if field.readonly else "normal")
        self._inputs[field.key] = ("text", variable, None)
        return widget

    def values(self):
        result = {}
        for key, (kind, source, mapping) in self._inputs.items():
            if kind == "multiline":
                result[key] = source.get("1.0", "end").strip()
            elif kind == "choice":
                result[key] = mapping.get(source.get(), "")
            else:
                result[key] = source.get().strip()
        return result

    def _submit(self):
        try:
            self._on_submit(self.values())
        except GreenRootsError as error:
            messagebox.showerror("Cannot save", str(error), parent=self)
            return
        except Exception as error:
            report_unexpected(self, error)
            return
        self.destroy()


class BaseView(ttk.Frame):
    """Common page layout (heading, toolbar, body) and error-safe action runner."""

    title = ""
    subtitle = ""

    def __init__(self, parent, app, window):
        super().__init__(parent, padding=(24, 18))
        self.app, self.window = app, window
        ttk.Label(self, text=self.title, style="Title.TLabel").pack(anchor="w")
        ttk.Label(self, text=self.subtitle, style="Muted.TLabel").pack(anchor="w", pady=(0, 12))
        self.toolbar = ttk.Frame(self)
        self.toolbar.pack(fill="x", pady=(0, 10))
        self.body = ttk.Frame(self)
        self.body.pack(fill="both", expand=True)

    def add_buttons(self, buttons):
        for text, command in buttons:
            ttk.Button(self.toolbar, text=text, command=command).pack(side="left", padx=(0, 8))

    def refresh(self):
        """Reload data from the services. Overridden by each page."""

    def run(self, action, success_message=None):
        """Run a service action, showing friendly errors. Returns True on success."""
        try:
            action()
        except GreenRootsError as error:
            self.window.set_status(str(error), error=True)
            messagebox.showerror("Action not completed", str(error), parent=self)
            return False
        except Exception as error:
            report_unexpected(self, error)
            return False
        self.window.refresh_all()
        if success_message:
            self.window.notify_success(success_message)
        return True

    def need_selection(self, selected, noun):
        if not selected:
            messagebox.showinfo("Select a record", f"Please select a {noun} from the table first.", parent=self)
            return False
        return True
