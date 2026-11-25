"""Charge calculation, payments, balances and receipts."""
from datetime import date, timedelta

from models import CANCELLED, FAILED, PAID, PARTIALLY_PAID, SUCCESSFUL, UNPAID
from services.application_service import ApplicationService
from tests.base import D, AppTestCase
from validation import BusinessRuleError, DuplicateError, NotFoundError, ValidationError


class ChargeCalculationTests(AppTestCase):
    def test_specification_examples_for_100_sqm(self):
        _, _, _, standard = self.make_charge("100", "Standard Member")
        _, _, _, concession = self.make_charge("100", "Concessionary Member")
        self.assertEqual((standard.base_amount, standard.discount_amount, standard.total_amount), (D("50.00"), D("0.00"), D("50.00")))
        self.assertEqual((concession.base_amount, concession.discount_amount, concession.total_amount), (D("50.00"), D("12.50"), D("37.50")))
        self.assertEqual(concession.discount_rate, D("0.25"))

    def test_base_rate_scales_with_size(self):
        for size, expected in (("50", "25.00"), ("75", "37.50"), ("125", "62.50"), ("150", "75.00")):
            with self.subTest(size=size):
                self.assertEqual(self.make_charge(size)[3].total_amount, D(expected))

    def test_rounding_to_two_decimal_places(self):
        # 125 sqm -> base 62.50, discount 15.625 -> 15.63, final 46.87
        charge = self.make_charge("125", "Concessionary Member")[3]
        self.assertEqual((charge.base_amount, charge.discount_amount, charge.total_amount), (D("62.50"), D("15.63"), D("46.87")))
        self.assertEqual(charge.total_amount, charge.base_amount - charge.discount_amount)

    def test_smallest_valid_charge(self):
        for category in ("Standard Member", "Concessionary Member"):
            charge = self.make_charge("0.01", category)[3]
            self.assertEqual(charge.total_amount, D("0.01"))
            self.assertGreater(charge.total_amount, 0)

    def test_charge_records_relationships_and_snapshot(self):
        plot, holder, allocation, charge = self.make_charge("80")
        self.assertEqual((charge.allocation_id, charge.plot_id, charge.holder_id), (allocation.allocation_id, plot.plot_id, holder.holder_id))
        self.allotment.update_plot(plot.plot_id, "200", "North")
        self.assertEqual(charge.total_amount, D("40.00"))  # an issued charge is a snapshot

    def test_breakdown(self):
        charge = self.make_charge("100", "Concessionary Member")[3]
        b = self.finance.charge_breakdown(charge.charge_id)
        self.assertEqual((b["base_amount"], b["discount_amount"], b["total_amount"], b["outstanding_balance"]),
                         (D("50.00"), D("12.50"), D("37.50"), D("37.50")))
        text = self.finance.breakdown_text(charge.charge_id)
        for expected in ("£0.50", "£50.00", "£12.50", "£37.50", "25%", "Unpaid"):
            self.assertIn(expected, text)

    def test_same_allocation_and_period_cannot_be_charged_twice(self):
        _, _, allocation, _ = self.make_charge(period="2026")
        with self.assertRaises(BusinessRuleError):
            self.finance.generate_charge(allocation.allocation_id, "2026")
        second = self.finance.generate_charge(allocation.allocation_id, "2027")
        self.assertEqual(len(self.finance.list_charges()), 2)
        self.assertNotEqual(second.charge_id, "CHG-001")

    def test_invalid_charge_requests(self):
        with self.assertRaises(NotFoundError):
            self.finance.generate_charge("ALC-404", "2026")
        with self.assertRaises(NotFoundError):
            self.finance.generate_charge("", "2026")
        _, _, allocation = self.make_allocation()
        for period in ("20x6", "26", "2026-27", "twenty"):
            with self.subTest(period=period), self.assertRaises(ValidationError):
                self.finance.generate_charge(allocation.allocation_id, period)
        self.assertEqual(self.app.store.charges, {})

    def test_cannot_charge_ended_allocation(self):
        _, _, allocation = self.make_allocation()
        self.allocation.remove_allocation(allocation.allocation_id)
        with self.assertRaises(BusinessRuleError):
            self.finance.generate_charge(allocation.allocation_id, "2026")


class PaymentTests(AppTestCase):
    def setUp(self):
        super().setUp()
        _, self.holder, _, self.charge = self.make_charge("100")  # standard, 50.00 due

    def pay(self, amount, method="Cash", **kwargs):
        return self.finance.record_payment(self.charge.charge_id, amount, method, **kwargs)

    def test_full_one_off_payment(self):
        payment = self.pay("50.00")
        self.assertEqual((payment.transaction_status, payment.payment_type), (SUCCESSFUL, "Full payment"))
        self.assertEqual((self.charge.amount_paid, self.charge.outstanding_balance, self.charge.payment_status),
                         (D("50.00"), D("0.00"), PAID))

    def test_partial_then_instalments_until_paid(self):
        self.pay("10")
        self.assertEqual((self.charge.payment_status, self.charge.outstanding_balance), (PARTIALLY_PAID, D("40.00")))
        self.pay("15.50", "Bank Transfer")
        self.assertEqual(self.charge.outstanding_balance, D("24.50"))
        last = self.pay("24.50", "Simulated Card Payment")
        self.assertEqual(last.payment_type, "Instalment")
        self.assertEqual((self.charge.payment_status, self.charge.outstanding_balance), (PAID, D("0.00")))
        self.assertEqual(len(self.finance.list_payments(self.charge.charge_id)), 3)

    def test_boundaries(self):
        self.pay("0.01")  # smallest partial payment
        self.assertEqual((self.charge.payment_status, self.charge.outstanding_balance), (PARTIALLY_PAID, D("49.99")))
        self.pay("49.99")  # final instalment equals remaining balance exactly
        self.assertEqual((self.charge.payment_status, self.charge.outstanding_balance), (PAID, D("0.00")))

    def test_amount_rounding_boundary(self):
        with self.assertRaises(ValidationError):
            self.pay("0.004")  # rounds to zero
        self.assertEqual(self.pay("0.005").amount, D("0.01"))

    def test_invalid_amounts_rejected_without_side_effects(self):
        for bad in ("0", "-5", "abc", "", "NaN", "Infinity"):
            with self.subTest(amount=bad), self.assertRaises(ValidationError):
                self.pay(bad)
        self.assertEqual(self.app.store.payments, {})
        self.assertEqual(self.charge.amount_paid, D("0.00"))

    def test_payment_cannot_exceed_outstanding_balance(self):
        with self.assertRaises(BusinessRuleError):
            self.pay("50.01")
        self.pay("40")
        with self.assertRaises(BusinessRuleError):
            self.pay("10.01")
        self.assertEqual(self.charge.outstanding_balance, D("10.00"))
        self.assertEqual(len(self.app.store.payments), 1)

    def test_paid_charge_accepts_no_more_payments(self):
        self.pay("50")
        with self.assertRaises(BusinessRuleError):
            self.pay("0.01")

    def test_invalid_charge_and_method(self):
        for charge_id in ("CHG-404", "", None):
            with self.subTest(charge=charge_id), self.assertRaises(NotFoundError):
                self.finance.record_payment(charge_id, "5", "Cash")
        with self.assertRaises(ValidationError):
            self.pay("5", "Bitcoin")
        self.assertEqual(self.app.store.payments, {})

    def test_failed_and_cancelled_payments_do_not_change_balances(self):
        for outcome in (FAILED, CANCELLED):
            payment = self.pay("20", "Simulated Card Payment", outcome=outcome)
            self.assertEqual(payment.transaction_status, outcome)
            self.assertEqual((self.charge.amount_paid, self.charge.payment_status), (D("0.00"), UNPAID))
            self.assertIsNone(self.finance.get_receipt_for_payment(payment.payment_id))
        self.assertEqual(len(self.finance.list_payments(self.charge.charge_id)), 2)  # history kept
        self.assertEqual(self.app.store.receipts, {})
        self.pay("50")  # the failed attempts did not use up the balance
        self.assertEqual(self.charge.payment_status, PAID)

    def test_card_simulator_decides_card_outcome_only(self):
        app = ApplicationService(load_sample_data=False, card_simulator=lambda amount: FAILED)
        site = app.allotment.add_site("S", "L", "", "M")
        plot = app.allotment.add_plot(site.site_id, "100", "N")
        holder = app.allotment.add_holder("Standard Member", "Ann Lee", "1 St", "a@b.com", "0123456789")
        allocation = app.allocation.create_allocation(plot.plot_id, holder.holder_id, "2026-01-01")
        charge = app.finance.generate_charge(allocation.allocation_id, "2026")
        self.assertEqual(app.finance.record_payment(charge.charge_id, "10", "Simulated Card Payment").transaction_status, FAILED)
        self.assertEqual(app.finance.record_payment(charge.charge_id, "10", "Cash").transaction_status, SUCCESSFUL)
        self.assertEqual(charge.amount_paid, D("10.00"))

    def test_transaction_references_are_unique(self):
        refs = [self.pay("1").transaction_reference for _ in range(3)]
        self.assertEqual(len(set(refs)), 3)
        self.pay("1", transaction_reference="BANK-001")
        with self.assertRaises(DuplicateError):
            self.pay("1", transaction_reference="BANK-001")
        self.assertEqual(self.charge.amount_paid, D("4.00"))

    def test_malformed_transaction_reference(self):
        with self.assertRaises(ValidationError):
            self.pay("1", transaction_reference="a b")
        self.assertEqual(self.app.store.payments, {})

    def test_future_payment_date_rejected(self):
        with self.assertRaises(ValidationError):
            self.pay("1", payment_date=(date.today() + timedelta(days=1)).isoformat())

    def test_amount_paid_always_derived_from_successful_payments(self):
        self.pay("5")
        self.pay("7", "Simulated Card Payment", outcome=FAILED)
        self.pay("3")
        total = sum(p.amount for p in self.app.store.payments.values() if p.is_successful)
        self.assertEqual((self.charge.amount_paid, total), (D("8.00"), D("8.00")))

    def test_payment_history_filters(self):
        _, other_holder, _, other_charge = self.make_charge("50")
        self.pay("5")
        self.finance.record_payment(other_charge.charge_id, "5", "Cash")
        self.pay("5", "Simulated Card Payment", outcome=FAILED)
        self.assertEqual(len(self.finance.list_payments(charge_id=self.charge.charge_id)), 2)
        self.assertEqual(len(self.finance.list_payments(holder_id=other_holder.holder_id)), 1)
        self.assertEqual(len(self.finance.list_payments(status=FAILED)), 1)

    def test_no_payment_history(self):
        self.assertEqual(self.finance.list_payments(), [])
        self.assertEqual(self.finance.list_payments(charge_id=self.charge.charge_id), [])


class ReceiptTests(AppTestCase):
    def setUp(self):
        super().setUp()
        _, self.holder, _, self.charge = self.make_charge("100", "Concessionary Member")  # 37.50

    def test_successful_payment_generates_receipt_with_remaining_balance(self):
        p1 = self.finance.record_payment(self.charge.charge_id, "10", "Cash")
        p2 = self.finance.record_payment(self.charge.charge_id, "27.50", "Bank Transfer")
        r1, r2 = (self.finance.get_receipt_for_payment(p.payment_id) for p in (p1, p2))
        self.assertEqual((r1.remaining_balance, r2.remaining_balance), (D("27.50"), D("0.00")))
        self.assertEqual((r1.holder_name, r1.holder_id, r1.charge_id), (self.holder.full_name, self.holder.holder_id, self.charge.charge_id))
        self.assertEqual(r1.transaction_reference, p1.transaction_reference)
        self.assertEqual(self.finance.get_receipt(r1.receipt_id), r1)
        self.assertNotEqual(r1.receipt_id, r2.receipt_id)

    def test_receipt_is_issued_once_per_payment(self):
        payment = self.finance.record_payment(self.charge.charge_id, "10", "Cash")
        self.assertIs(self.finance.generate_receipt(payment.payment_id), self.finance.generate_receipt(payment.payment_id))
        self.assertEqual(len(self.finance.list_receipts()), 1)

    def test_no_receipt_for_failed_payment(self):
        payment = self.finance.record_payment(self.charge.charge_id, "10", "Simulated Card Payment", outcome=FAILED)
        with self.assertRaises(BusinessRuleError):
            self.finance.generate_receipt(payment.payment_id)
        self.assertEqual(self.finance.list_receipts(), [])

    def test_unknown_receipt_and_payment(self):
        with self.assertRaises(NotFoundError):
            self.finance.get_receipt("RCP-404")
        with self.assertRaises(NotFoundError):
            self.finance.generate_receipt("PAY-404")
        self.assertIsNone(self.finance.get_receipt_for_payment("PAY-404"))


class ExtremeAmountTests(AppTestCase):
    """Regression tests for the Day 6 defect: huge amounts raised decimal.InvalidOperation."""

    def test_huge_payment_amounts_give_validation_or_rule_errors(self):
        _, _, _, charge = self.make_charge("100")
        for amount in ("1e400", "1e30", "99999999999999999999999999999999"):
            with self.subTest(amount=amount), self.assertRaises((ValidationError, BusinessRuleError)):
                self.finance.record_payment(charge.charge_id, amount, "Cash")
        self.assertEqual(self.app.store.payments, {})
        self.assertEqual(charge.amount_paid, D("0.00"))
