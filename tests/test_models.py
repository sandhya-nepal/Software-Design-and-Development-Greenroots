"""Model-level tests: creation, membership behaviour and invalid data."""
import unittest
from datetime import date, timedelta
from decimal import Decimal

from models import (AllotmentPlot, AllotmentSite, Announcement, ConcessionaryMember, MaintenanceCharge, Payment,
                    PaymentReceipt, PlotAllocation, SiteManager, StandardMember, create_holder,
                    PAID, PARTIALLY_PAID, UNPAID, AVAILABLE, OCCUPIED, ACTIVE, ENDED)
from validation import BusinessRuleError, ValidationError

D = Decimal


def make_charge(total="50.00", discount="0.00"):
    base = D(total) + D(discount)
    return MaintenanceCharge("CHG-1", "ALC-1", "PLOT-1", "HLD-1", "2026", D("100"), base, D("0"), D(discount), D(total))


class SiteModelTests(unittest.TestCase):
    def test_site_creation_stores_details(self):
        site = AllotmentSite("S1", "Riverside", "River Road", "desc", SiteManager("Ann Lee"), ["Tap", " Shed "])
        self.assertEqual((site.site_id, site.name, site.location), ("S1", "Riverside", "River Road"))
        self.assertEqual(site.facilities, ["Tap", "Shed"])
        self.assertEqual(site.manager.name, "Ann Lee")
        self.assertEqual(site.plot_ids, ())

    def test_plot_ids_are_not_modifiable_from_outside(self):
        site = AllotmentSite("S1", "Riverside", "River Road", "", SiteManager("Ann Lee"))
        site.add_plot_id("P1")
        site.add_plot_id("P1")
        self.assertEqual(site.plot_ids, ("P1",))
        self.assertIsInstance(site.plot_ids, tuple)

    def test_invalid_site_data_rejected(self):
        for kwargs in ({"name": ""}, {"location": "  "}):
            args = {"name": "N", "location": "L"}
            args.update(kwargs)
            with self.assertRaises(ValidationError):
                AllotmentSite("S1", args["name"], args["location"], "", SiteManager("M"))
        with self.assertRaises(ValidationError):
            AllotmentSite("", "N", "L", "", SiteManager("M"))
        with self.assertRaises(ValidationError):
            SiteManager("")

    def test_failed_update_changes_nothing(self):
        site = AllotmentSite("S1", "Riverside", "River Road", "", SiteManager("Ann Lee"))
        with self.assertRaises(ValidationError):
            site.update("New name", "", "", SiteManager("Bob"))
        self.assertEqual((site.name, site.location, site.manager.name), ("Riverside", "River Road", "Ann Lee"))


class PlotModelTests(unittest.TestCase):
    def test_plot_creation_defaults_to_available(self):
        plot = AllotmentPlot("P1", "S1", "75", "North row")
        self.assertEqual(plot.size, D("75.00"))
        self.assertEqual(plot.occupancy_status, AVAILABLE)
        self.assertTrue(plot.is_available)

    def test_occupancy_changes_only_through_methods(self):
        plot = AllotmentPlot("P1", "S1", "75", "North")
        plot.mark_occupied()
        self.assertEqual(plot.occupancy_status, OCCUPIED)
        plot.mark_available()
        self.assertTrue(plot.is_available)
        with self.assertRaises(AttributeError):
            plot.occupancy_status = OCCUPIED

    def test_invalid_sizes_rejected(self):
        for bad in ("0", "-5", "abc", "", "NaN", "10001"):
            with self.subTest(size=bad), self.assertRaises(ValidationError):
                AllotmentPlot("P1", "S1", bad, "North")

    def test_minimum_valid_size(self):
        self.assertEqual(AllotmentPlot("P1", "S1", "0.01", "North").size, D("0.01"))


class HolderModelTests(unittest.TestCase):
    def test_membership_categories_and_discounts(self):
        standard = create_holder("Standard Member", "H1", "Ann Lee", "1 St", "a@b.com", "0123456789")
        concession = create_holder("Concessionary Member", "H2", "Bob Ray", "2 St", "b@b.com", "0123456789")
        self.assertIsInstance(standard, StandardMember)
        self.assertIsInstance(concession, ConcessionaryMember)
        self.assertEqual(standard.discount_rate, D("0.00"))
        self.assertEqual(concession.discount_rate, D("0.25"))
        self.assertEqual(concession.membership_category, "Concessionary Member")

    def test_unknown_category_rejected(self):
        with self.assertRaises(ValidationError):
            create_holder("Gold", "H1", "Ann Lee", "1 St", "a@b.com", "0123456789")

    def test_invalid_holder_data(self):
        good = dict(holder_id="H1", full_name="Ann Lee", address="1 St", email="a@b.com", phone="0123456789")
        for field, bad in (("full_name", ""), ("full_name", "1234"), ("address", ""), ("email", "not-an-email"),
                           ("email", "a@b"), ("phone", "abc"), ("phone", "123"), ("holder_id", "")):
            with self.subTest(field=field, value=bad), self.assertRaises(ValidationError) as ctx:
                StandardMember(**{**good, field: bad})
            self.assertEqual(ctx.exception.field, field)

    def test_phone_formats_accepted(self):
        for phone in ("01632 960123", "+44 1632 960123", "(016) 3296-0123"):
            StandardMember("H1", "Ann Lee", "1 St", "a@b.com", phone)


class AllocationModelTests(unittest.TestCase):
    def test_allocation_creation_and_end(self):
        a = PlotAllocation("A1", "P1", "H1", "2026-01-15")
        self.assertEqual((a.status, a.allocation_date), (ACTIVE, date(2026, 1, 15)))
        a.end()
        self.assertEqual(a.status, ENDED)
        self.assertFalse(a.is_active)
        self.assertEqual(a.end_date, date.today())

    def test_invalid_dates(self):
        for bad in ("2026-13-01", "15/01/2026", "", "yesterday", (date.today() + timedelta(days=1)).isoformat()):
            with self.subTest(date=bad), self.assertRaises(ValidationError):
                PlotAllocation("A1", "P1", "H1", bad)


class ChargeModelTests(unittest.TestCase):
    def test_new_charge_is_unpaid(self):
        c = make_charge("50.00")
        self.assertEqual((c.amount_paid, c.outstanding_balance, c.payment_status), (D("0"), D("50.00"), UNPAID))

    def test_status_follows_amount_paid(self):
        c = make_charge("50.00")
        c.set_amount_paid("0.01")
        self.assertEqual(c.payment_status, PARTIALLY_PAID)
        c.set_amount_paid("50.00")
        self.assertEqual((c.payment_status, c.outstanding_balance), (PAID, D("0.00")))

    def test_negative_balance_prevented(self):
        c = make_charge("50.00")
        for bad in ("-1", "50.01"):
            with self.assertRaises(BusinessRuleError):
                c.set_amount_paid(bad)
        self.assertEqual(c.amount_paid, D("0.00"))

    def test_inconsistent_totals_rejected(self):
        with self.assertRaises(ValidationError):
            MaintenanceCharge("C", "A", "P", "H", "2026", D("100"), "50.00", D("0.25"), "12.50", "40.00")
        with self.assertRaises(ValidationError):
            MaintenanceCharge("C", "A", "P", "H", "2026", D("1"), "0.00", D("0"), "0.00", "0.00")


class PaymentAndReceiptModelTests(unittest.TestCase):
    def payment(self, **overrides):
        args = dict(payment_id="PAY-1", transaction_reference="TXN-1", charge_id="CHG-1", holder_id="H1",
                    payment_date="2026-02-01", amount="10", payment_method="Cash", transaction_status="Successful")
        args.update(overrides)
        return Payment(**args)

    def test_payment_record(self):
        p = self.payment(amount="10.005")
        self.assertEqual(p.amount, D("10.01"))
        self.assertTrue(p.is_successful)
        self.assertFalse(self.payment(transaction_status="Failed").is_successful)

    def test_invalid_payments(self):
        for overrides in ({"amount": "0"}, {"amount": "-3"}, {"amount": "x"}, {"payment_method": "Bitcoin"},
                          {"transaction_status": "Pending"}, {"transaction_reference": ""}):
            with self.subTest(overrides=overrides), self.assertRaises(ValidationError):
                self.payment(**overrides)

    def receipt(self, status="Successful", method="Cash"):
        return PaymentReceipt("RCP-1", "PAY-1", "TXN-1", "H1", "Ann Lee", "CHG-1", "10.00", "2026-02-01", method, "5.00", status)

    def test_receipt_contents(self):
        text = self.receipt().render()
        for expected in ("GreenRoots Community Association", "RCP-1", "TXN-1", "Ann Lee", "H1", "CHG-1", "£10.00",
                         "Cash", "2026-02-01", "£5.00", "Successful"):
            self.assertIn(expected, text)
        self.assertNotIn("no real money", text)
        self.assertIn("no real money", self.receipt(method="Simulated Card Payment").render())

    def test_receipt_only_for_successful_payment(self):
        for status in ("Failed", "Cancelled"):
            with self.assertRaises(ValidationError):
                self.receipt(status)


class AnnouncementModelTests(unittest.TestCase):
    def test_creation_and_default_date(self):
        a = Announcement("N1", "S1", "Title", "Body")
        self.assertEqual((a.site_id, a.title, a.publication_date), ("S1", "Title", date.today()))

    def test_invalid_announcements(self):
        for kwargs in ({"title": ""}, {"description": " "}, {"publication_date": "31-12-2026"}):
            args = dict(title="T", description="D", publication_date="2026-01-01")
            args.update(kwargs)
            with self.subTest(kwargs=kwargs), self.assertRaises(ValidationError):
                Announcement("N1", "S1", **args)


if __name__ == "__main__":
    unittest.main()
