"""Maintenance charges, simulated payments and balances."""
import random
from datetime import date
from decimal import Decimal

from models import (BANK_TRANSFER, CANCELLED, CASH, FAILED, PAYMENT_METHODS, SIMULATED_CARD, SUCCESSFUL,
                    MaintenanceCharge, Payment)
from validation import (CENT, BusinessRuleError, DuplicateError, NotFoundError, ValidationError,
                        parse_date, require_text, to_money)
from decimal import ROUND_HALF_UP

BASE_RATE_PER_SQM = Decimal("0.50")


def random_card_simulator(amount):
    """Local simulation only: roughly 1 in 7 card attempts fail. No real money moves."""
    return SUCCESSFUL if random.random() > 0.15 else FAILED


class FinanceService:
    def __init__(self, store, ids, card_simulator=None):
        self._store = store
        self._ids = ids
        self._card_simulator = card_simulator or random_card_simulator

    # ----------------------------------------------------------- charges
    @staticmethod
    def calculate_amounts(plot_size, holder):
        """Return (base, discount, final) using the fixed policy of GBP 0.50 per sqm."""
        base = (Decimal(plot_size) * BASE_RATE_PER_SQM).quantize(CENT, rounding=ROUND_HALF_UP)
        discount = (base * holder.discount_rate).quantize(CENT, rounding=ROUND_HALF_UP)
        return base, discount, base - discount

    def generate_charge(self, allocation_id, period=None, charge_id=None):
        allocation = self._store.allocations.get(allocation_id or "")
        if allocation is None:
            raise NotFoundError("Please choose an existing allocation to charge.")
        if not allocation.is_active:
            raise BusinessRuleError("Charges can only be generated for active allocations.")
        period = require_text(period or str(date.today().year), "Charging period", "period", 30)
        if any(c.allocation_id == allocation_id and c.period.lower() == period.lower()
               for c in self._store.charges.values()):
            raise BusinessRuleError(f"A charge for period '{period}' has already been generated for allocation {allocation_id}.")
        charge_id = (charge_id or "").strip() or self._ids.next_id("CHG", self._store.charges)
        if charge_id in self._store.charges:
            raise DuplicateError(f"Charge ID '{charge_id}' already exists.", "charge_id")
        plot = self._store.plots[allocation.plot_id]
        holder = self._store.holders[allocation.holder_id]
        base, discount, final = self.calculate_amounts(plot.size, holder)
        charge = MaintenanceCharge(charge_id, allocation_id, plot.plot_id, holder.holder_id, period, plot.size,
                                   base, holder.discount_rate, discount, final)
        self._store.charges[charge.charge_id] = charge
        return charge

    def suggest_charge_id(self):
        return self._ids.suggest("CHG", self._store.charges)

    def get_charge(self, charge_id):
        try:
            return self._store.charges[charge_id]
        except KeyError:
            raise NotFoundError(f"Charge '{charge_id}' does not exist.")

    def list_charges(self, holder_id=None, site_id=None, status=None, search=""):
        term = (search or "").strip().lower()
        result = []
        for c in self._store.charges.values():
            holder = self._store.holders[c.holder_id]
            if holder_id and c.holder_id != holder_id:
                continue
            if site_id and self._store.plots[c.plot_id].site_id != site_id:
                continue
            if status and c.payment_status != status:
                continue
            if term and term not in c.charge_id.lower() and term not in c.plot_id.lower() \
                    and term not in holder.full_name.lower() and term not in holder.holder_id.lower():
                continue
            result.append(c)
        return sorted(result, key=lambda c: c.charge_id)

    def charges_with_balance(self):
        return [c for c in self.list_charges() if c.outstanding_balance > 0]

    def charge_breakdown(self, charge_id):
        c = self.get_charge(charge_id)
        holder = self._store.holders[c.holder_id]
        return {
            "charge_id": c.charge_id, "period": c.period, "plot_id": c.plot_id, "plot_size": c.plot_size,
            "holder_name": holder.full_name, "holder_id": holder.holder_id,
            "membership": holder.membership_category, "rate_per_sqm": BASE_RATE_PER_SQM,
            "base_amount": c.base_amount, "discount_rate": c.discount_rate, "discount_amount": c.discount_amount,
            "total_amount": c.total_amount, "amount_paid": c.amount_paid,
            "outstanding_balance": c.outstanding_balance, "status": c.payment_status,
        }

    def breakdown_text(self, charge_id):
        b = self.charge_breakdown(charge_id)
        return (f"Charge {b['charge_id']} - period {b['period']}\n"
                f"Holder: {b['holder_name']} ({b['holder_id']}, {b['membership']})\n"
                f"Plot: {b['plot_id']} ({b['plot_size']} sqm)\n\n"
                f"Base charge: {b['plot_size']} sqm x £{b['rate_per_sqm']} = £{b['base_amount']}\n"
                f"Discount ({b['discount_rate'] * 100:.0f}%): -£{b['discount_amount']}\n"
                f"Final charge: £{b['total_amount']}\n\n"
                f"Amount paid: £{b['amount_paid']}\n"
                f"Outstanding balance: £{b['outstanding_balance']}\n"
                f"Status: {b['status']}")

    # ---------------------------------------------------------- payments
    def get_payment(self, payment_id):
        try:
            return self._store.payments[payment_id]
        except KeyError:
            raise NotFoundError(f"Payment '{payment_id}' does not exist.")

    def list_payments(self, charge_id=None, holder_id=None, status=None):
        result = [p for p in self._store.payments.values()
                  if (not charge_id or p.charge_id == charge_id)
                  and (not holder_id or p.holder_id == holder_id)
                  and (not status or p.transaction_status == status)]
        return sorted(result, key=lambda p: p.payment_id)

    def record_payment(self, charge_id, amount, method, payment_date=None, outcome=None, transaction_reference=None):
        """Record a simulated payment. Only successful payments change the charge balance."""
        charge = self._store.charges.get(charge_id or "")
        if charge is None:
            raise NotFoundError("Please choose an existing charge to pay.")
        if method not in PAYMENT_METHODS:
            raise ValidationError("Please choose a valid payment method.", "payment_method")
        amount = to_money(amount, "Payment amount", "amount")
        if amount <= 0:
            raise ValidationError("Payment amount must be greater than zero.", "amount")
        if charge.outstanding_balance <= 0:
            raise BusinessRuleError(f"Charge {charge.charge_id} is already fully paid.")
        if amount > charge.outstanding_balance:
            raise BusinessRuleError(f"Payment of £{amount} exceeds the outstanding balance of £{charge.outstanding_balance}.")
        payment_date = parse_date(payment_date or date.today(), "Payment date", "payment_date", allow_future=False)
        reference = (transaction_reference or "").strip() or self._ids.next_id("TXN", self._store.payments_by_reference(), 6)
        if reference in self._store.payments_by_reference():
            raise DuplicateError(f"Transaction reference '{reference}' has already been used.", "transaction_reference")
        status = outcome or (self._card_simulator(amount) if method == SIMULATED_CARD else SUCCESSFUL)
        kind = "Full payment" if amount == charge.total_amount else "Instalment"
        payment = Payment(self._ids.next_id("PAY", self._store.payments), reference, charge.charge_id,
                          charge.holder_id, payment_date, amount, method, status, kind)
        self._store.payments[payment.payment_id] = payment
        if payment.is_successful:
            self._recalculate(charge)
        return payment

    def _recalculate(self, charge):
        total = sum((p.amount for p in self._store.payments.values()
                     if p.charge_id == charge.charge_id and p.is_successful), Decimal("0.00"))
        charge.set_amount_paid(total)
