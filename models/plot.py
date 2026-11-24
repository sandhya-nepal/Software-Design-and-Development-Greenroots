"""Allotment plot."""
from decimal import Decimal

from validation import ValidationError, positive_decimal, require_text

AVAILABLE = "Available"
OCCUPIED = "Occupied"
MAX_PLOT_SIZE = Decimal("10000")


class AllotmentPlot:
    """An individual plot. Occupancy is changed only through the mark_* methods."""

    def __init__(self, plot_id, site_id, size, location_within_site):
        self._plot_id = require_text(plot_id, "Plot ID", "plot_id", 30)
        self._site_id = require_text(site_id, "Site", "site_id", 30)
        self._occupancy_status = AVAILABLE
        self.update(size, location_within_site)

    @property
    def plot_id(self):
        return self._plot_id

    @property
    def site_id(self):
        return self._site_id

    @property
    def occupancy_status(self):
        return self._occupancy_status

    @property
    def is_available(self):
        return self._occupancy_status == AVAILABLE

    def update(self, size, location_within_site):
        checked_size = positive_decimal(size, "Plot size", "size")
        if checked_size > MAX_PLOT_SIZE:
            raise ValidationError(f"Plot size cannot exceed {MAX_PLOT_SIZE:,} sqm.", "size")
        checked_location = require_text(location_within_site, "Location within site", "location_within_site")
        self.size, self.location_within_site = checked_size, checked_location

    def mark_occupied(self):
        self._occupancy_status = OCCUPIED

    def mark_available(self):
        self._occupancy_status = AVAILABLE

    def __str__(self):
        return f"{self.plot_id} ({self.size} sqm)"
