"""Allocation rules, occupancy consistency and history preservation."""
from datetime import date, timedelta

from tests.base import AppTestCase
from validation import BusinessRuleError, DuplicateError, NotFoundError, ValidationError


class AllocationCreationTests(AppTestCase):
    def test_create_updates_occupancy(self):
        plot, holder, allocation = self.make_allocation()
        self.assertEqual((allocation.plot_id, allocation.holder_id, allocation.status), (plot.plot_id, holder.holder_id, "Active"))
        self.assertEqual(plot.occupancy_status, "Occupied")
        self.assertFalse(self.allocation.is_plot_available(plot.plot_id))

    def test_default_date_is_today(self):
        plot, holder = self.make_plot(), self.make_holder()
        self.assertEqual(self.allocation.create_allocation(plot.plot_id, holder.holder_id).allocation_date, date.today())

    def test_occupied_plot_cannot_be_allocated_again(self):
        plot, _, _ = self.make_allocation()
        other = self.make_holder()
        with self.assertRaises(BusinessRuleError):
            self.allocation.create_allocation(plot.plot_id, other.holder_id)
        self.assertEqual(len(self.app.store.allocations), 1)

    def test_same_holder_cannot_double_allocate_same_plot(self):
        plot, holder, _ = self.make_allocation()
        with self.assertRaises(BusinessRuleError):
            self.allocation.create_allocation(plot.plot_id, holder.holder_id)

    def test_nonexistent_holder_and_plot(self):
        plot, holder = self.make_plot(), self.make_holder()
        with self.assertRaises(NotFoundError):
            self.allocation.create_allocation(plot.plot_id, "HLD-404")
        with self.assertRaises(NotFoundError):
            self.allocation.create_allocation("PLOT-404", holder.holder_id)
        with self.assertRaises(ValidationError):
            self.allocation.create_allocation("", holder.holder_id)
        self.assertTrue(plot.is_available)
        self.assertEqual(self.app.store.allocations, {})

    def test_invalid_dates_leave_plot_available(self):
        plot, holder = self.make_plot(), self.make_holder()
        for bad in ("2026-02-30", "not a date", (date.today() + timedelta(days=2)).isoformat()):
            with self.subTest(date=bad), self.assertRaises(ValidationError):
                self.allocation.create_allocation(plot.plot_id, holder.holder_id, bad)
        self.assertTrue(plot.is_available)
        self.assertEqual(self.app.store.allocations, {})

    def test_duplicate_allocation_id(self):
        plot, holder = self.make_plot(), self.make_holder()
        plot2 = self.make_plot()
        self.allocation.create_allocation(plot.plot_id, holder.holder_id, "2026-01-01", "ALC-X")
        with self.assertRaises(DuplicateError):
            self.allocation.create_allocation(plot2.plot_id, holder.holder_id, "2026-01-01", "ALC-X")
        self.assertTrue(plot2.is_available)

    def test_holder_may_hold_multiple_plots(self):
        holder = self.make_holder()
        for _ in range(3):
            self.allocation.create_allocation(self.make_plot().plot_id, holder.holder_id, "2026-01-01")
        self.assertEqual(len(self.allocation.plots_for_holder(holder.holder_id)), 3)


class AllocationModificationTests(AppTestCase):
    def test_changing_plot_updates_old_and_new(self):
        old_plot, holder, allocation = self.make_allocation()
        new_plot = self.make_plot()
        self.allocation.modify_allocation(allocation.allocation_id, new_plot.plot_id, holder.holder_id, "2026-02-01")
        self.assertTrue(old_plot.is_available)
        self.assertFalse(new_plot.is_available)
        self.assertEqual(allocation.plot_id, new_plot.plot_id)
        self.assertEqual(allocation.allocation_date, date(2026, 2, 1))

    def test_changing_holder_only(self):
        plot, _, allocation = self.make_allocation()
        other = self.make_holder()
        self.allocation.modify_allocation(allocation.allocation_id, plot.plot_id, other.holder_id, "2026-01-15")
        self.assertEqual(allocation.holder_id, other.holder_id)
        self.assertFalse(plot.is_available)

    def test_cannot_move_to_occupied_plot(self):
        _, holder, allocation = self.make_allocation()
        taken, _, _ = self.make_allocation()
        with self.assertRaises(BusinessRuleError):
            self.allocation.modify_allocation(allocation.allocation_id, taken.plot_id, holder.holder_id, "2026-01-15")
        self.assertNotEqual(allocation.plot_id, taken.plot_id)

    def test_failed_modification_changes_nothing(self):
        old_plot, holder, allocation = self.make_allocation()
        new_plot = self.make_plot()
        with self.assertRaises(ValidationError):
            self.allocation.modify_allocation(allocation.allocation_id, new_plot.plot_id, holder.holder_id, "bad-date")
        self.assertEqual(allocation.plot_id, old_plot.plot_id)
        self.assertFalse(old_plot.is_available)
        self.assertTrue(new_plot.is_available)
        with self.assertRaises(NotFoundError):
            self.allocation.modify_allocation(allocation.allocation_id, new_plot.plot_id, "HLD-404", "2026-01-15")
        self.assertTrue(new_plot.is_available)

    def test_ended_allocation_cannot_be_modified(self):
        plot, holder, allocation = self.make_allocation()
        self.allocation.remove_allocation(allocation.allocation_id)
        with self.assertRaises(BusinessRuleError):
            self.allocation.modify_allocation(allocation.allocation_id, plot.plot_id, holder.holder_id, "2026-01-15")


class AllocationRemovalTests(AppTestCase):
    def test_removal_restores_availability_and_keeps_record(self):
        plot, holder, allocation = self.make_allocation()
        self.allocation.remove_allocation(allocation.allocation_id)
        self.assertTrue(plot.is_available)
        self.assertTrue(self.allocation.is_plot_available(plot.plot_id))
        self.assertEqual(self.allocation.get_allocation(allocation.allocation_id).status, "Ended")
        self.assertEqual(self.allocation.plots_for_holder(holder.holder_id), [])
        self.assertEqual(len(self.allocation.plots_for_holder(holder.holder_id, active_only=False)), 1)

    def test_plot_can_be_reallocated_after_removal(self):
        plot, _, allocation = self.make_allocation()
        self.allocation.remove_allocation(allocation.allocation_id)
        new_holder = self.make_holder()
        again = self.allocation.create_allocation(plot.plot_id, new_holder.holder_id, "2026-03-01")
        self.assertTrue(again.is_active)
        self.assertEqual(len([a for a in self.app.store.allocations.values() if a.is_active and a.plot_id == plot.plot_id]), 1)

    def test_cannot_remove_twice(self):
        _, _, allocation = self.make_allocation()
        self.allocation.remove_allocation(allocation.allocation_id)
        with self.assertRaises(BusinessRuleError):
            self.allocation.remove_allocation(allocation.allocation_id)

    def test_unknown_allocation(self):
        with self.assertRaises(NotFoundError):
            self.allocation.remove_allocation("ALC-404")

    def test_removal_with_outstanding_charge_is_blocked_and_records_kept(self):
        plot, _, allocation, charge = self.make_charge()
        with self.assertRaises(BusinessRuleError):
            self.allocation.remove_allocation(allocation.allocation_id)
        self.assertFalse(plot.is_available)
        self.assertIn(charge.charge_id, self.app.store.charges)

    def test_removal_after_full_payment_keeps_financial_history(self):
        plot, _, allocation, charge = self.make_charge()
        payment = self.finance.record_payment(charge.charge_id, charge.total_amount, "Cash")
        self.allocation.remove_allocation(allocation.allocation_id)
        self.assertTrue(plot.is_available)
        self.assertIn(charge.charge_id, self.app.store.charges)
        self.assertIn(payment.payment_id, self.app.store.payments)
        self.assertIsNotNone(self.finance.get_receipt_for_payment(payment.payment_id))
        self.assertEqual(self.reporting.verify_integrity(), [])

    def test_holder_and_plot_with_history_cannot_be_deleted(self):
        plot, holder, allocation = self.make_allocation()
        self.allocation.remove_allocation(allocation.allocation_id)
        with self.assertRaises(BusinessRuleError):
            self.allotment.delete_plot(plot.plot_id)
        with self.assertRaises(BusinessRuleError):
            self.allotment.delete_holder(holder.holder_id)

    def test_charged_allocation_cannot_change_plot_or_holder(self):
        plot, holder, allocation, _ = self.make_charge()
        other_plot, other_holder = self.make_plot(), self.make_holder()
        with self.assertRaises(BusinessRuleError):
            self.allocation.modify_allocation(allocation.allocation_id, other_plot.plot_id, holder.holder_id, "2026-01-15")
        with self.assertRaises(BusinessRuleError):
            self.allocation.modify_allocation(allocation.allocation_id, plot.plot_id, other_holder.holder_id, "2026-01-15")
        self.allocation.modify_allocation(allocation.allocation_id, plot.plot_id, holder.holder_id, "2026-01-20")
        self.assertEqual(allocation.allocation_date, date(2026, 1, 20))


class AllocationQueryTests(AppTestCase):
    def test_filters_by_holder_site_status_and_search(self):
        site_a, site_b = self.make_site(), self.make_site()
        p1, h1, a1 = self.make_allocation(site=site_a)
        p2, h2, a2 = self.make_allocation(site=site_b)
        self.allocation.remove_allocation(a2.allocation_id)
        self.assertEqual(self.allocation.list_allocations(holder_id=h1.holder_id), [a1])
        self.assertEqual(self.allocation.list_allocations(site_id=site_b.site_id), [a2])
        self.assertEqual(self.allocation.list_allocations(status="Active"), [a1])
        self.assertEqual(self.allocation.list_allocations(search=h2.full_name.lower()), [a2])
        self.assertEqual(self.allocation.list_allocations(search="zzz"), [])

    def test_details_and_available_plots(self):
        plot, holder, allocation = self.make_allocation()
        free = self.make_plot()
        details = self.allocation.allocation_details(allocation.allocation_id)
        self.assertEqual((details["plot"], details["holder"]), (plot, holder))
        self.assertEqual(details["site"].site_id, plot.site_id)
        self.assertEqual(self.allocation.list_available_plots(), [free])
