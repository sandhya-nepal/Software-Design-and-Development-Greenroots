"""Plot allocation: the link between a plot holder and a plot."""
from datetime import date

from validation import parse_date, require_text

ACTIVE = "Active"
ENDED = "Ended"


class PlotAllocation:
    """Holds plot and holder by ID. Ended allocations are kept as history."""

    def __init__(self, allocation_id, plot_id, holder_id, allocation_date):
        self._allocation_id = require_text(allocation_id, "Allocation ID", "allocation_id", 30)
        self.update(plot_id, holder_id, allocation_date)
        self.status = ACTIVE
        self.end_date = None

    @property
    def allocation_id(self):
        return self._allocation_id

    @property
    def is_active(self):
        return self.status == ACTIVE

    def update(self, plot_id, holder_id, allocation_date):
        checked = (require_text(plot_id, "Plot", "plot_id", 30),
                   require_text(holder_id, "Plot holder", "holder_id", 30),
                   parse_date(allocation_date, "Allocation date", "allocation_date", allow_future=False))
        self.plot_id, self.holder_id, self.allocation_date = checked

    def end(self, end_date=None):
        self.status = ENDED
        self.end_date = end_date or date.today()

    def __str__(self):
        return f"{self.allocation_id}: {self.plot_id} -> {self.holder_id} ({self.status})"
