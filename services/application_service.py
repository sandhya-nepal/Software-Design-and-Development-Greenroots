"""Central coordinator: owns the in-memory collections and the services."""
from .allocation_service import AllocationService
from .announcement_service import AnnouncementService
from .allotment_service import AllotmentService
from .finance_service import FinanceService
from .id_generator import IdGenerator
from .reporting_service import ReportingService


class DataStore:
    """All application data lives in these in-memory dictionaries."""

    def __init__(self):
        self.sites = {}
        self.plots = {}
        self.holders = {}
        self.allocations = {}
        self.charges = {}
        self.payments = {}
        self.receipts = {}
        self.announcements = {}

    def payments_by_reference(self):
        return {p.transaction_reference: p for p in self.payments.values()}


class ApplicationService:
    def __init__(self, load_sample_data=True, card_simulator=None):
        self.store = DataStore()
        self.ids = IdGenerator()
        self.allotment = AllotmentService(self.store, self.ids)
        self.allocation = AllocationService(self.store, self.ids)
        self.finance = FinanceService(self.store, self.ids, card_simulator)
        self.announcements = AnnouncementService(self.store, self.ids)
        self.reporting = ReportingService(self.store)
        if load_sample_data:
            from .sample_data import populate
            populate(self)
