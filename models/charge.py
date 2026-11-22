"""Maintenance charge. Payment status and balance are derived, never set directly."""
from datetime import date
from decimal import Decimal

from validation import BusinessRuleError, ValidationError, parse_date, require_text, to_money

UNPAID = "Unpaid"
PARTIALLY_PAID = "Partially Paid"
PAID = "Paid"


class MaintenanceCharge:
    def __init__(self, charge_id, allocation_id, plot_id, holder_id, period, plot_size,
                 base_amount, discount_rate, discount_amount, total_amount, calculation_date=None):
        self._charge_id = require_text(charge_id, "Charge ID", "charge_id", 30)
        self.allocation_id = require_text(allocation_id, "Allocation", "allocation_id", 30)
        self.plot_id = require_text(plot_id, "Plot", "plot_id", 30)
        self.holder_id = require_text(holder_id, "Plot holder", "holder_id", 30)
        self.period = require_text(period, "Charging period", "period", 30)
        self.plot_size = plot_size
        self.base_amount = to_money(base_amount, "Base charge")
        self.discount_rate = Decimal(str(discount_rate))
        self.discount_amount = to_money(discount_amount, "Discount")
        self.total_amount = to_money(total_amount, "Total charge")
        if self.total_amount <= 0:
            raise ValidationError("The total charge must be greater than zero.")
        if self.total_amount != self.base_amount - self.discount_amount:
            raise ValidationError("Total charge must equal the base charge minus the discount.")
        self.calculation_date = parse_date(calculation_date or date.today(), "Calculation date")
        self._amount_paid = Decimal("0.00")

    @property
    def charge_id(self):
        return self._charge_id

    @property
    def amount_paid(self):
        return self._amount_paid

    @property
    def outstanding_balance(self):
        return self.total_amount - self._amount_paid

    @property
    def payment_status(self):
        if self._amount_paid <= 0:
            return UNPAID
        return PAID if self.outstanding_balance == 0 else PARTIALLY_PAID

    def set_amount_paid(self, amount):
        """Called by FinanceService with the sum of successful payments."""
        amount = to_money(amount, "Amount paid")
        if amount < 0 or amount > self.total_amount:
            raise BusinessRuleError("The amount paid cannot be negative or exceed the total charge.")
        self._amount_paid = amount
