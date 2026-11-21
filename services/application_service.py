"""Central coordinator: owns the in-memory collections and the services."""
from .allocation_service import AllocationService
from .allotment_service import AllotmentService
from .id_generator import IdGenerator


class DataStore:
    """All application data lives in these in-memory dictionaries."""

    def __init__(self):
        self.sites = {}
        self.plots = {}
        self.holders = {}
        self.allocations = {}


class ApplicationService:
    def __init__(self, load_sample_data=True):
        self.store = DataStore()
        self.ids = IdGenerator()
        self.allotment = AllotmentService(self.store, self.ids)
        self.allocation = AllocationService(self.store, self.ids)
        if load_sample_data:
            from .sample_data import populate
            populate(self)
