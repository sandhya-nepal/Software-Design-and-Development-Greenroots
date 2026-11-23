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
