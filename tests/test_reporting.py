"""Dashboard, site summaries and integrity checks, always computed from live data."""
from models import FAILED
from tests.base import D, AppTestCase


class DashboardTests(AppTestCase):
    def test_empty_application(self):
        stats = self.reporting.dashboard_stats()
        for key, value in stats.items():
            self.assertEqual(value, 0, key)
        self.assertEqual(self.reporting.all_site_summaries(), [])
        self.assertEqual(self.reporting.outstanding_balances(), [])

    def test_statistics_follow_the_data(self):
        site = self.make_site()
        _, _, allocation = self.make_allocation(size="100", site=site)
        self.make_plot(site)
        charge = self.finance.generate_charge(allocation.allocation_id, "2026")
        self.finance.record_payment(charge.charge_id, "20", "Cash")
        self.finance.record_payment(charge.charge_id, "5", "Simulated Card Payment", outcome=FAILED)
        s = self.reporting.dashboard_stats()
        self.assertEqual((s["total_sites"], s["total_plots"], s["occupied_plots"], s["available_plots"]), (1, 2, 1, 1))
        self.assertEqual((s["total_holders"], s["active_allocations"]), (1, 1))
        self.assertEqual((s["total_charges"], s["total_payments"], s["total_outstanding"]), (D("50.00"), D("20.00"), D("30.00")))
        self.allocation.remove_allocation  # statistics must change when data changes
        self.finance.record_payment(charge.charge_id, "30", "Cash")
        self.allocation.remove_allocation(allocation.allocation_id)
        s = self.reporting.dashboard_stats()
        self.assertEqual((s["occupied_plots"], s["available_plots"], s["active_allocations"], s["total_outstanding"]),
                         (0, 2, 0, D("0.00")))

    def test_occupied_plus_available_equals_total(self):
        for _ in range(4):
            self.make_allocation()
        self.make_plot()
        s = self.reporting.dashboard_stats()
        self.assertEqual(s["occupied_plots"] + s["available_plots"], s["total_plots"])


class SiteSummaryTests(AppTestCase):
    def test_empty_site(self):
        site = self.make_site()
        r = self.reporting.site_summary(site.site_id)
        self.assertEqual((r["total_plots"], r["occupied_plots"], r["available_plots"], r["occupancy_percentage"]), (0, 0, 0, D("0.0")))
        self.assertEqual((r["total_charges"], r["total_payments"], r["outstanding_balance"]), (D("0.00"),) * 3)

    def test_all_available_and_all_occupied(self):
        free, full = self.make_site(), self.make_site()
        for _ in range(3):
            self.make_plot(free)
            self.make_allocation(site=full)
        self.assertEqual(self.reporting.site_summary(free.site_id)["occupancy_percentage"], D("0.0"))
        r = self.reporting.site_summary(full.site_id)
        self.assertEqual((r["occupied_plots"], r["available_plots"], r["occupancy_percentage"], r["holders_with_allocations"]),
                         (3, 0, D("100.0"), 3))

    def test_percentage_rounding(self):
        site = self.make_site()
        self.make_allocation(site=site)
        self.make_plot(site)
        self.make_plot(site)
        self.assertEqual(self.reporting.site_summary(site.site_id)["occupancy_percentage"], D("33.3"))

    def test_sites_are_summarised_separately(self):
        a, b = self.make_site(), self.make_site()
        _, _, alc_a = self.make_allocation("100", site=a)
        _, _, alc_b = self.make_allocation("50", site=b)
        ca = self.finance.generate_charge(alc_a.allocation_id, "2026")
        cb = self.finance.generate_charge(alc_b.allocation_id, "2026")
        self.finance.record_payment(ca.charge_id, "50", "Cash")
        self.finance.record_payment(cb.charge_id, "5", "Cash")
        ra, rb = (self.reporting.site_summary(s.site_id) for s in (a, b))
        self.assertEqual((ra["total_charges"], ra["total_payments"], ra["outstanding_balance"]), (D("50.00"), D("50.00"), D("0.00")))
        self.assertEqual((rb["total_charges"], rb["total_payments"], rb["outstanding_balance"]), (D("25.00"), D("5.00"), D("20.00")))
        total = self.reporting.dashboard_stats()
        self.assertEqual(total["total_charges"], ra["total_charges"] + rb["total_charges"])

    def test_holder_counted_once_per_site(self):
        site, holder = self.make_site(), self.make_holder()
        for _ in range(2):
            self.allocation.create_allocation(self.make_plot(site).plot_id, holder.holder_id, "2026-01-01")
        self.assertEqual(self.reporting.site_summary(site.site_id)["holders_with_allocations"], 1)

    def test_announcement_count_is_per_site(self):
        a, b = self.make_site(), self.make_site()
        self.announcements.create_announcement(a.site_id, "T", "D")
        self.assertEqual((self.reporting.site_summary(a.site_id)["announcement_count"],
                          self.reporting.site_summary(b.site_id)["announcement_count"]), (1, 0))


class HolderAndOccupancyReportTests(AppTestCase):
    def test_holder_overview_and_records(self):
        _, holder, allocation, charge = self.make_charge("100")
        self.finance.record_payment(charge.charge_id, "10", "Cash")
        row = self.reporting.holder_overview()[0]
        self.assertEqual((row["active_plots"], row["total_charges"], row["total_paid"], row["outstanding"]),
                         (1, D("50.00"), D("10.00"), D("40.00")))
        records = self.reporting.holder_records(holder.holder_id)
        self.assertEqual((len(records["allocations"]), len(records["charges"]), len(records["payments"])), (1, 1, 1))

    def test_empty_holder_list(self):
        self.assertEqual(self.reporting.holder_overview(), [])

    def test_plot_occupancy_and_outstanding(self):
        plot, holder, _, charge = self.make_charge()
        free = self.make_plot()
        rows = {r["plot"].plot_id: r for r in self.reporting.plot_occupancy()}
        self.assertEqual(rows[plot.plot_id]["holder"], holder)
        self.assertIsNone(rows[free.plot_id]["holder"])
        self.assertEqual([r["charge"] for r in self.reporting.outstanding_balances()], [charge])
        self.finance.record_payment(charge.charge_id, charge.total_amount, "Cash")
        self.assertEqual(self.reporting.outstanding_balances(), [])


class IntegrityTests(AppTestCase):
    def test_clean_data_has_no_issues(self):
        _, _, _, charge = self.make_charge()
        self.finance.record_payment(charge.charge_id, "10", "Cash")
        self.finance.record_payment(charge.charge_id, "5", "Simulated Card Payment", outcome=FAILED)
        self.assertEqual(self.reporting.verify_integrity(), [])

    def test_detects_occupancy_mismatch(self):
        plot, _, _ = self.make_allocation()
        plot.mark_available()  # simulate corruption
        self.assertTrue(any("occupancy" in issue for issue in self.reporting.verify_integrity()))

    def test_detects_balance_mismatch_and_missing_receipt(self):
        _, _, _, charge = self.make_charge()
        payment = self.finance.record_payment(charge.charge_id, "10", "Cash")
        charge.set_amount_paid("3")
        del self.app.store.receipts[self.finance.get_receipt_for_payment(payment.payment_id).receipt_id]
        text = " ".join(self.reporting.verify_integrity())
        self.assertIn("successful payments total", text)
        self.assertIn("exactly one receipt", text)
