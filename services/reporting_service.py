"""Read-only calculations over the live in-memory data. Nothing here is hardcoded."""
from decimal import Decimal

ZERO = Decimal("0.00")


def _percentage(part, whole):
    return Decimal("0.0") if not whole else (Decimal(part) * 100 / Decimal(whole)).quantize(Decimal("0.1"))


class ReportingService:
    def __init__(self, store):
        self._store = store

    # ----------------------------------------------------------- helpers
    def _site_of_charge(self, charge):
        return self._store.plots[charge.plot_id].site_id

    def _successful_payments(self):
        return [p for p in self._store.payments.values() if p.is_successful]

    def _total_charges(self, charges):
        return sum((c.total_amount for c in charges), ZERO)

    # --------------------------------------------------------- dashboard
    def dashboard_stats(self):
        plots = list(self._store.plots.values())
        occupied = sum(1 for p in plots if not p.is_available)
        charges = list(self._store.charges.values())
        return {
            "total_sites": len(self._store.sites),
            "total_plots": len(plots),
            "occupied_plots": occupied,
            "available_plots": len(plots) - occupied,
            "total_holders": len(self._store.holders),
            "active_allocations": sum(1 for a in self._store.allocations.values() if a.is_active),
            "total_charges": self._total_charges(charges),
            "total_payments": sum((p.amount for p in self._successful_payments()), ZERO),
            "total_outstanding": sum((c.outstanding_balance for c in charges), ZERO),
        }

    # -------------------------------------------------------- site views
    def site_summary(self, site_id):
        site = self._store.sites[site_id]
        plots = [self._store.plots[i] for i in site.plot_ids]
        occupied = sum(1 for p in plots if not p.is_available)
        plot_ids = {p.plot_id for p in plots}
        holders = {a.holder_id for a in self._store.allocations.values() if a.is_active and a.plot_id in plot_ids}
        charges = [c for c in self._store.charges.values() if c.plot_id in plot_ids]
        charge_ids = {c.charge_id for c in charges}
        paid = sum((p.amount for p in self._successful_payments() if p.charge_id in charge_ids), ZERO)
        return {
            "site_id": site.site_id, "site_name": site.name, "total_plots": len(plots), "occupied_plots": occupied,
            "available_plots": len(plots) - occupied, "occupancy_percentage": _percentage(occupied, len(plots)),
            "holders_with_allocations": len(holders), "total_charges": self._total_charges(charges),
            "total_payments": paid, "outstanding_balance": sum((c.outstanding_balance for c in charges), ZERO),
            "announcement_count": sum(1 for a in self._store.announcements.values() if a.site_id == site_id),
        }

    def all_site_summaries(self):
        return [self.site_summary(s) for s in sorted(self._store.sites)]

    def plot_occupancy(self, site_id=None):
        """Plots with their current holder (if any)."""
        active = {a.plot_id: a for a in self._store.allocations.values() if a.is_active}
        rows = []
        for plot in sorted(self._store.plots.values(), key=lambda p: p.plot_id):
            if site_id and plot.site_id != site_id:
                continue
            holder = self._store.holders[active[plot.plot_id].holder_id] if plot.plot_id in active else None
            rows.append({"plot": plot, "site": self._store.sites[plot.site_id], "holder": holder})
        return rows

    # ------------------------------------------------------ holder views
    def holder_overview(self):
        rows = []
        for holder in sorted(self._store.holders.values(), key=lambda h: h.holder_id):
            plots = [a for a in self._store.allocations.values() if a.holder_id == holder.holder_id and a.is_active]
            charges = [c for c in self._store.charges.values() if c.holder_id == holder.holder_id]
            rows.append({"holder": holder, "active_plots": len(plots), "total_charges": self._total_charges(charges),
                         "total_paid": sum((c.amount_paid for c in charges), ZERO),
                         "outstanding": sum((c.outstanding_balance for c in charges), ZERO)})
        return rows

    def holder_records(self, holder_id):
        """Allocations, charges and payments belonging to one holder."""
        return {
            "allocations": [a for a in self._store.allocations.values() if a.holder_id == holder_id],
            "charges": [c for c in self._store.charges.values() if c.holder_id == holder_id],
            "payments": [p for p in self._store.payments.values() if p.holder_id == holder_id],
        }

    def outstanding_balances(self):
        rows = []
        for c in sorted(self._store.charges.values(), key=lambda c: c.charge_id):
            if c.outstanding_balance > 0:
                rows.append({"charge": c, "holder": self._store.holders[c.holder_id],
                             "site": self._store.sites[self._site_of_charge(c)]})
        return rows

    # ----------------------------------------------------------- integrity
    def verify_integrity(self):
        """Return a list of human-readable problems. An empty list means everything is consistent."""
        st, issues = self._store, []
        for site in st.sites.values():
            for plot_id in site.plot_ids:
                plot = st.plots.get(plot_id)
                if plot is None:
                    issues.append(f"Site {site.site_id} lists missing plot {plot_id}.")
                elif plot.site_id != site.site_id:
                    issues.append(f"Plot {plot_id} is listed by {site.site_id} but belongs to {plot.site_id}.")
        active = {}
        for plot in st.plots.values():
            site = st.sites.get(plot.site_id)
            if site is None:
                issues.append(f"Plot {plot.plot_id} belongs to missing site {plot.site_id}.")
            elif plot.plot_id not in site.plot_ids:
                issues.append(f"Plot {plot.plot_id} is not listed by its site {site.site_id}.")
        for a in st.allocations.values():
            if a.plot_id not in st.plots or a.holder_id not in st.holders:
                issues.append(f"Allocation {a.allocation_id} refers to a missing plot or holder.")
            if a.is_active:
                active.setdefault(a.plot_id, []).append(a.allocation_id)
        for plot_id, ids in active.items():
            if len(ids) > 1:
                issues.append(f"Plot {plot_id} has {len(ids)} active allocations: {', '.join(ids)}.")
        for plot in st.plots.values():
            if (not plot.is_available) != (plot.plot_id in active):
                issues.append(f"Plot {plot.plot_id} occupancy ({plot.occupancy_status}) does not match its allocations.")
        for c in st.charges.values():
            allocation = st.allocations.get(c.allocation_id)
            if allocation is None:
                issues.append(f"Charge {c.charge_id} refers to missing allocation {c.allocation_id}.")
            elif (allocation.plot_id, allocation.holder_id) != (c.plot_id, c.holder_id):
                issues.append(f"Charge {c.charge_id} does not match the plot/holder of its allocation.")
            paid = sum((p.amount for p in st.payments.values() if p.charge_id == c.charge_id and p.is_successful), ZERO)
            if paid != c.amount_paid:
                issues.append(f"Charge {c.charge_id} records £{c.amount_paid} paid but successful payments total £{paid}.")
            if c.outstanding_balance < 0:
                issues.append(f"Charge {c.charge_id} has a negative balance.")
        receipts_per_payment = {}
        for p in st.payments.values():
            charge = st.charges.get(p.charge_id)
            if charge is None or charge.holder_id != p.holder_id:
                issues.append(f"Payment {p.payment_id} does not match a valid charge and holder.")
        for r in st.receipts.values():
            payment = st.payments.get(r.payment_id)
            if payment is None or not payment.is_successful:
                issues.append(f"Receipt {r.receipt_id} is not linked to a successful payment.")
            receipts_per_payment[r.payment_id] = receipts_per_payment.get(r.payment_id, 0) + 1
        for p in st.payments.values():
            if p.is_successful and receipts_per_payment.get(p.payment_id, 0) != 1:
                issues.append(f"Successful payment {p.payment_id} should have exactly one receipt.")
        for a in st.announcements.values():
            if a.site_id not in st.sites:
                issues.append(f"Announcement {a.announcement_id} refers to missing site {a.site_id}.")
        return issues
