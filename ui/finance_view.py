"""Maintenance charge and payment pages."""
import tkinter as tk
from datetime import date
from tkinter import messagebox, ttk

from models import (CANCELLED, FAILED, PARTIALLY_PAID, PAID, PAYMENT_METHODS, SUCCESSFUL,
                    TRANSACTION_STATUSES, UNPAID)
from ui.widgets import BaseView, ChoiceFilter, DataTable, Field, FormDialog, fmt_money

SIMULATION_NOTE = "Payments are simulated. No real money is transferred."


def open_payment_form(view, charge_id=None):
    """Shared by the charges and payments pages."""
    finance = view.app.finance
    charges = finance.charges_with_balance()
    if not charges:
        messagebox.showinfo("Nothing to pay", "There are no charges with an outstanding balance.", parent=view)
        return
    holders = view.app.store.holders
    choices = [(c.charge_id, f"{c.charge_id} - {holders[c.holder_id].full_name}, {c.plot_id}, owes {fmt_money(c.outstanding_balance)}")
               for c in charges]
    fields = [Field("charge_id", "Charge", "choice", choices),
              Field("amount", "Amount (£)", hint="full or part payment"),
              Field("payment_method", "Method", "choice", [(m, m) for m in PAYMENT_METHODS]),
              Field("payment_date", "Payment date", hint="YYYY-MM-DD"),
              Field("outcome", "Simulated outcome", "choice",
                    [("", "Automatic"), (FAILED, "Force failure"), (CANCELLED, "Force cancellation")]),
              Field("transaction_reference", "Reference", hint="optional, must be unique")]
    initial = {"charge_id": charge_id or "", "payment_method": PAYMENT_METHODS[0],
               "payment_date": date.today().isoformat(), "outcome": ""}
    if charge_id and charge_id in view.app.store.charges:
        initial["amount"] = str(view.app.store.charges[charge_id].outstanding_balance)

    def save(v):
        payment = finance.record_payment(v["charge_id"], v["amount"], v["payment_method"], v["payment_date"],
                                         v["outcome"] or None, v["transaction_reference"])
        view.refresh()
        if payment.is_successful:
            charge = finance.get_charge(payment.charge_id)
            view.window.notify_success(f"Payment {payment.transaction_reference} recorded ({payment.payment_type}). "
                                       f"Remaining balance: {fmt_money(charge.outstanding_balance)}.")
        else:
            view.window.set_status(f"Transaction {payment.transaction_reference} {payment.transaction_status.lower()}.", error=True)
            messagebox.showwarning("Transaction not completed", f"The simulated transaction {payment.transaction_reference} "
                                   f"{payment.transaction_status.lower()}. No balance was changed.", parent=view)

    FormDialog(view, "Record Payment", fields, save, initial, "Pay", note=SIMULATION_NOTE)


class ChargesView(BaseView):
    title = "Maintenance Charges"
    subtitle = "Generate charges (£0.50 per sqm, 25% concessionary discount) and track balances."

    def __init__(self, parent, app, window):
        super().__init__(parent, app, window)
        self.add_buttons([("Generate Charge", self.generate_charge), ("View Breakdown", self.show_breakdown),
                          ("Make Payment", self.make_payment)])
        ttk.Label(self.toolbar, text="Search:").pack(side="left", padx=(20, 6))
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *args: self.refresh())
        ttk.Entry(self.toolbar, textvariable=self.search_var, width=18).pack(side="left", padx=(0, 8))
        self.status_filter = ChoiceFilter(self.toolbar, "Status:", self.refresh, "All statuses", width=14)
        self.status_filter.pack(side="left")
        self.table = DataTable(self.body, [("id", "Charge", 80), ("period", "Period", 70), ("plot", "Plot", 80),
                                           ("holder", "Plot holder", 160), ("base", "Base", 80), ("discount", "Discount", 80),
                                           ("total", "Final", 80), ("paid", "Paid", 80), ("due", "Outstanding", 90),
                                           ("status", "Status", 110)],
                               height=16, empty_text="No charges found. Use 'Generate Charge' to create one.")
        self.table.pack(fill="both", expand=True)

    def refresh(self):
        self.status_filter.set_choices([(s, s) for s in (UNPAID, PARTIALLY_PAID, PAID)])
        charges = self.app.finance.list_charges(status=self.status_filter.value or None, search=self.search_var.get())
        holders = self.app.store.holders
        self.table.set_rows([(c.charge_id, (c.charge_id, c.period, c.plot_id, holders[c.holder_id].full_name,
                                            fmt_money(c.base_amount), fmt_money(c.discount_amount), fmt_money(c.total_amount),
                                            fmt_money(c.amount_paid), fmt_money(c.outstanding_balance), c.payment_status))
                             for c in charges])

    def generate_charge(self):
        store = self.app.store
        choices = [(a.allocation_id, f"{a.allocation_id} - {store.holders[a.holder_id].full_name}, {a.plot_id}")
                   for a in self.app.allocation.list_allocations(status="Active")]
        fields = [Field("allocation_id", "Allocation", "choice", choices),
                  Field("period", "Charging period", hint="e.g. 2026")]
        FormDialog(self, "Generate Maintenance Charge", fields, self._save_charge,
                   {"period": str(date.today().year)}, "Generate")

    def _save_charge(self, v):
        charge = self.app.finance.generate_charge(v["allocation_id"], v["period"])
        self.refresh()
        self.window.notify_success(f"Charge {charge.charge_id} generated: {fmt_money(charge.total_amount)}.")

    def show_breakdown(self):
        charge_id = self.table.selected_id()
        if self.need_selection(charge_id, "charge"):
            messagebox.showinfo("Charge breakdown", self.app.finance.breakdown_text(charge_id), parent=self)

    def make_payment(self):
        charge_id = self.table.selected_id()
        if self.need_selection(charge_id, "charge"):
            open_payment_form(self, charge_id)


class PaymentsView(BaseView):
    title = "Payments and Receipts"
    subtitle = "Record simulated payments and review the payment history."

    def __init__(self, parent, app, window):
        super().__init__(parent, app, window)
        self.add_buttons([("Record Payment", lambda: open_payment_form(self))])
        self.charge_filter = ChoiceFilter(self.toolbar, "Charge:", self.refresh, "All charges", width=14)
        self.charge_filter.pack(side="left", padx=(20, 8))
        self.status_filter = ChoiceFilter(self.toolbar, "Status:", self.refresh, "All statuses", width=12)
        self.status_filter.pack(side="left")
        ttk.Label(self.body, text=SIMULATION_NOTE, style="Muted.TLabel").pack(anchor="w", pady=(0, 6))
        self.table = DataTable(self.body, [("id", "Payment", 80), ("ref", "Transaction ref", 110), ("charge", "Charge", 80),
                                           ("holder", "Plot holder", 160), ("date", "Date", 95), ("amount", "Amount", 80),
                                           ("method", "Method", 150), ("status", "Status", 90), ("type", "Type", 100)],
                               height=16, empty_text="No payments recorded yet.")
        self.table.pack(fill="both", expand=True)

    def refresh(self):
        self.charge_filter.set_choices([(c.charge_id, c.charge_id) for c in self.app.finance.list_charges()])
        self.status_filter.set_choices([(s, s) for s in TRANSACTION_STATUSES])
        payments = self.app.finance.list_payments(self.charge_filter.value or None, None, self.status_filter.value or None)
        holders = self.app.store.holders
        self.table.set_rows([(p.payment_id, (p.payment_id, p.transaction_reference, p.charge_id, holders[p.holder_id].full_name,
                                             p.payment_date.isoformat(), fmt_money(p.amount), p.payment_method,
                                             p.transaction_status, p.payment_type)) for p in payments])
