"""Creating, modifying and removing plot allocations while keeping occupancy consistent."""
from datetime import date

from models import PlotAllocation
from validation import BusinessRuleError, DuplicateError, NotFoundError, ValidationError, parse_date


class AllocationService:
    def __init__(self, store, ids):
        self._store = store
        self._ids = ids

    def suggest_allocation_id(self):
        return self._ids.suggest("ALC", self._store.allocations)

    # ---------------------------------------------------------- lookups
    def _holder(self, holder_id):
        if not holder_id:
            raise ValidationError("Please choose a plot holder.", "holder_id")
        if holder_id not in self._store.holders:
            raise NotFoundError(f"Plot holder '{holder_id}' is not registered.")
        return self._store.holders[holder_id]

    def _plot(self, plot_id):
        if not plot_id:
            raise ValidationError("Please choose a plot.", "plot_id")
        if plot_id not in self._store.plots:
            raise NotFoundError(f"Plot '{plot_id}' does not exist.")
        return self._store.plots[plot_id]

    def get_allocation(self, allocation_id):
        try:
            return self._store.allocations[allocation_id]
        except KeyError:
            raise NotFoundError(f"Allocation '{allocation_id}' does not exist.")

    def active_allocation_for_plot(self, plot_id):
        return next((a for a in self._store.allocations.values() if a.plot_id == plot_id and a.is_active), None)

    def is_plot_available(self, plot_id):
        plot = self._plot(plot_id)
        return plot.is_available and self.active_allocation_for_plot(plot_id) is None

    def list_available_plots(self):
        return [p for p in sorted(self._store.plots.values(), key=lambda p: p.plot_id) if self.is_plot_available(p.plot_id)]

    def list_allocations(self, holder_id=None, site_id=None, status=None, search=""):
        term = (search or "").strip().lower()
        result = []
        for a in self._store.allocations.values():
            plot, holder = self._store.plots[a.plot_id], self._store.holders[a.holder_id]
            if holder_id and a.holder_id != holder_id:
                continue
            if site_id and plot.site_id != site_id:
                continue
            if status and a.status != status:
                continue
            if term and term not in holder.full_name.lower() and term not in a.plot_id.lower() \
                    and term not in a.allocation_id.lower() and term not in holder.holder_id.lower():
                continue
            result.append(a)
        return sorted(result, key=lambda a: a.allocation_id)

    def plots_for_holder(self, holder_id, active_only=True):
        return [self._store.plots[a.plot_id] for a in self.list_allocations(holder_id=holder_id,
                status="Active" if active_only else None)]

    def allocation_details(self, allocation_id):
        a = self.get_allocation(allocation_id)
        plot = self._store.plots[a.plot_id]
        return {"allocation": a, "plot": plot, "holder": self._store.holders[a.holder_id],
                "site": self._store.sites[plot.site_id]}

    def _charges_for(self, allocation_id):
        return [c for c in self._store.charges.values() if c.allocation_id == allocation_id]

    # ------------------------------------------------------- operations
    def create_allocation(self, plot_id, holder_id, allocation_date=None, allocation_id=None):
        holder = self._holder(holder_id)
        plot = self._plot(plot_id)
        if not self.is_plot_available(plot.plot_id):
            raise BusinessRuleError(f"Plot '{plot.plot_id}' is already allocated and cannot be allocated again.")
        allocation_id = (allocation_id or "").strip() or self._ids.next_id("ALC", self._store.allocations)
        if allocation_id in self._store.allocations:
            raise DuplicateError(f"Allocation ID '{allocation_id}' already exists.", "allocation_id")
        allocation = PlotAllocation(allocation_id, plot.plot_id, holder.holder_id,
                                    allocation_date or date.today())  # validates the date
        self._store.allocations[allocation.allocation_id] = allocation
        plot.mark_occupied()
        return allocation

    def modify_allocation(self, allocation_id, plot_id, holder_id, allocation_date):
        allocation = self.get_allocation(allocation_id)
        if not allocation.is_active:
            raise BusinessRuleError("Only active allocations can be modified.")
        holder, new_plot = self._holder(holder_id), self._plot(plot_id)
        old_plot = self._store.plots[allocation.plot_id]
        changing_plot = new_plot.plot_id != old_plot.plot_id
        if changing_plot and not self.is_plot_available(new_plot.plot_id):
            raise BusinessRuleError(f"Plot '{new_plot.plot_id}' is already allocated.")
        parse_date(allocation_date, "Allocation date", "allocation_date", allow_future=False)
        if (changing_plot or holder.holder_id != allocation.holder_id) and self._charges_for(allocation_id):
            raise BusinessRuleError("The plot or holder cannot be changed because maintenance charges already exist "
                                    "for this allocation. Only the allocation date can be edited.")
        allocation.update(new_plot.plot_id, holder.holder_id, allocation_date)
        if changing_plot:
            old_plot.mark_available()
            new_plot.mark_occupied()
        return allocation

    def remove_allocation(self, allocation_id):
        """End the allocation and free the plot. The record itself is kept as history."""
        allocation = self.get_allocation(allocation_id)
        if not allocation.is_active:
            raise BusinessRuleError("This allocation has already been removed.")
        unpaid = [c for c in self._charges_for(allocation_id) if c.outstanding_balance > 0]
        if unpaid:
            raise BusinessRuleError(f"Allocation {allocation_id} has {len(unpaid)} charge(s) with an outstanding balance. "
                                    "Settle them before removing the allocation; financial records are always kept.")
        allocation.end()
        self._store.plots[allocation.plot_id].mark_available()
        return allocation
