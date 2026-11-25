"""End-to-end workflows across all services, plus the bundled sample data."""
from datetime import date

from models import FAILED
from services.application_service import ApplicationService
from tests.base import D, AppTestCase
from validation import BusinessRuleError, GreenRootsError


class WorkflowTests(AppTestCase):
    def test_complete_management_workflow(self):
        site = self.allotment.add_site("Hilltop", "Hill Road", "", "Sam Gray", "", "", "Tap")
        plot = self.allotment.add_plot(site.site_id, "100", "North")
        holder = self.allotment.add_holder("Concessionary Member", "Ann Lee", "1 St", "ann@example.com", "01632 960000")
        allocation = self.allocation.create_allocation(plot.plot_id, holder.holder_id, "2026-01-01")
        charge = self.finance.generate_charge(allocation.allocation_id, "2026")
        self.assertEqual((charge.base_amount, charge.discount_amount, charge.total_amount), (D("50.00"), D("12.50"), D("37.50")))
        first = self.finance.record_payment(charge.charge_id, "20", "Cash")
        self.assertEqual((charge.payment_status, charge.outstanding_balance), ("Partially Paid", D("17.50")))
        self.assertEqual(self.finance.get_receipt_for_payment(first.payment_id).remaining_balance, D("17.50"))
        self.finance.record_payment(charge.charge_id, "17.50", "Bank Transfer")
        self.assertEqual(charge.payment_status, "Paid")
        self.assertEqual(len(self.finance.list_payments(holder_id=holder.holder_id)), 2)
        stats = self.reporting.dashboard_stats()
        self.assertEqual((stats["total_charges"], stats["total_payments"], stats["total_outstanding"]), (D("37.50"), D("37.50"), D("0.00")))
        self.announcements.create_announcement(site.site_id, "Hello", "Welcome")
        summary = self.reporting.site_summary(site.site_id)
        self.assertEqual((summary["occupancy_percentage"], summary["announcement_count"], summary["total_payments"]), (D("100.0"), 1, D("37.50")))
        self.assertEqual(self.reporting.verify_integrity(), [])

    def test_register_allocate_charge(self):
        _, holder, allocation, charge = self.make_charge("150", "Standard Member")
        self.assertEqual(charge.total_amount, D("75.00"))
        self.assertEqual(charge.holder_id, holder.holder_id)

    def test_remove_then_reallocate_keeps_everything_consistent(self):
        plot, holder, allocation, charge = self.make_charge()
        self.finance.record_payment(charge.charge_id, charge.total_amount, "Cash")
        self.allocation.remove_allocation(allocation.allocation_id)
        other = self.make_holder("Concessionary Member")
        new_allocation = self.allocation.create_allocation(plot.plot_id, other.holder_id, "2026-06-01")
        new_charge = self.finance.generate_charge(new_allocation.allocation_id, "2026")
        self.assertEqual(new_charge.total_amount, D("37.50"))
        self.assertEqual(charge.payment_status, "Paid")
        self.assertEqual(self.reporting.verify_integrity(), [])

    def test_failed_operations_never_leave_partial_state(self):
        plot, holder, allocation, charge = self.make_charge()
        before = (dict(self.app.store.allocations), dict(self.app.store.payments), dict(self.app.store.charges), charge.amount_paid)
        attempts = [lambda: self.allocation.create_allocation(plot.plot_id, holder.holder_id),
                    lambda: self.finance.record_payment(charge.charge_id, "999", "Cash"),
                    lambda: self.finance.generate_charge(allocation.allocation_id, "2026"),
                    lambda: self.allocation.remove_allocation(allocation.allocation_id),
                    lambda: self.allotment.delete_plot(plot.plot_id)]
        for attempt in attempts:
            with self.assertRaises(GreenRootsError):
                attempt()
        after = (dict(self.app.store.allocations), dict(self.app.store.payments), dict(self.app.store.charges), charge.amount_paid)
        self.assertEqual(before, after)
        self.assertEqual(self.reporting.verify_integrity(), [])

    def test_unique_ids_across_many_records(self):
        for _ in range(5):
            self.make_charge()
        store = self.app.store
        for collection in (store.sites, store.plots, store.holders, store.allocations, store.charges):
            self.assertEqual(len(collection), 5)
            self.assertEqual(len(set(collection)), 5)


class SampleDataTests(AppTestCase):
    def setUp(self):
        self.app = ApplicationService()  # loads the bundled sample data
        self.store = self.app.store

    def test_sample_data_is_consistent(self):
        self.assertEqual(self.app.reporting.verify_integrity(), [])

    def test_sample_data_contents(self):
        self.assertEqual({s.name for s in self.store.sites.values()},
                         {"Riverside Allotments", "Greenfield Allotments", "Meadow View Allotments"})
        stats = self.app.reporting.dashboard_stats()
        self.assertGreater(stats["occupied_plots"], 0)
        self.assertGreater(stats["available_plots"], 0)
        self.assertEqual({h.membership_category for h in self.store.holders.values()}, {"Standard Member", "Concessionary Member"})
        self.assertEqual({c.payment_status for c in self.store.charges.values()}, {"Unpaid", "Partially Paid", "Paid"})
        per_charge = {}
        for p in self.store.payments.values():
            if p.is_successful:
                per_charge[p.charge_id] = per_charge.get(p.charge_id, 0) + 1
        self.assertTrue(any(n > 1 for n in per_charge.values()))
        self.assertTrue(any(not p.is_successful for p in self.store.payments.values()))
        self.assertGreaterEqual(len(self.store.announcements), 3)
        self.assertTrue(all(a.allocation_date <= date.today() for a in self.store.allocations.values()))

    def test_sample_dashboard_matches_records(self):
        stats = self.app.reporting.dashboard_stats()
        self.assertEqual(stats["total_charges"], sum(c.total_amount for c in self.store.charges.values()))
        self.assertEqual(stats["total_payments"], sum(p.amount for p in self.store.payments.values() if p.is_successful))
        self.assertEqual(stats["total_outstanding"], stats["total_charges"] - stats["total_payments"])

    def test_sample_sites_not_deletable(self):
        with self.assertRaises(BusinessRuleError):
            self.app.allotment.delete_site("SITE-001")
