"""Shared fixtures. Every test gets a brand-new, empty in-memory application."""
import unittest
from decimal import Decimal

from models import SUCCESSFUL
from services.application_service import ApplicationService

D = Decimal
GOOD_PHONE = "01632 960000"


class AppTestCase(unittest.TestCase):
    def setUp(self):
        self.app = ApplicationService(load_sample_data=False, card_simulator=lambda amount: SUCCESSFUL)
        self.allotment = self.app.allotment
        self.allocation = self.app.allocation
        self.finance = self.app.finance
        self.reporting = self.app.reporting
        self.announcements = self.app.announcements
        self._counter = 0

    def _next(self):
        self._counter += 1
        return self._counter

    def make_site(self, name=None, location="Test Road"):
        n = self._next()
        return self.allotment.add_site(name or f"Test Site {n}", location, "A test site", "Manager One",
                                       "manager@example.com", GOOD_PHONE, "Tap, Shed")

    def make_plot(self, site=None, size="100", place="North"):
        site = site or self.make_site()
        return self.allotment.add_plot(site.site_id, size, place)

    def make_holder(self, category="Standard Member", name=None):
        n = self._next()
        return self.allotment.add_holder(category, name or f"Holder Number{n}", "1 Test Street",
                                         f"holder{n}@example.com", GOOD_PHONE)

    def make_allocation(self, size="100", category="Standard Member", site=None, date="2026-01-15"):
        plot = self.make_plot(site, size)
        holder = self.make_holder(category)
        return plot, holder, self.allocation.create_allocation(plot.plot_id, holder.holder_id, date)

    def make_charge(self, size="100", category="Standard Member", period="2026"):
        plot, holder, allocation = self.make_allocation(size, category)
        return plot, holder, allocation, self.finance.generate_charge(allocation.allocation_id, period)
