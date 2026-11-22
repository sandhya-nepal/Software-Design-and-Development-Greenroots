"""Payment transaction record."""
from datetime import date

from validation import ValidationError, parse_date, require_text, to_money

CASH = "Cash"
BANK_TRANSFER = "Bank Transfer"
SIMULATED_CARD = "Simulated Card Payment"
PAYMENT_METHODS = (CASH, BANK_TRANSFER, SIMULATED_CARD)

SUCCESSFUL = "Successful"
FAILED = "Failed"
CANCELLED = "Cancelled"
TRANSACTION_STATUSES = (SUCCESSFUL, FAILED, CANCELLED)


class Payment:
    def __init__(self, payment_id, transaction_reference, charge_id, holder_id, payment_date,
                 amount, payment_method, transaction_status, payment_type=""):
        self._payment_id = require_text(payment_id, "Payment ID", "payment_id", 30)
        self.transaction_reference = require_text(transaction_reference, "Transaction reference", "transaction_reference", 40)
        self.charge_id = require_text(charge_id, "Charge", "charge_id", 30)
        self.holder_id = require_text(holder_id, "Plot holder", "holder_id", 30)
        self.payment_date = parse_date(payment_date or date.today(), "Payment date", "payment_date", allow_future=False)
        self.amount = to_money(amount, "Payment amount", "amount")
        if self.amount <= 0:
            raise ValidationError("Payment amount must be greater than zero.", "amount")
        if payment_method not in PAYMENT_METHODS:
            raise ValidationError("Please choose a valid payment method.", "payment_method")
        if transaction_status not in TRANSACTION_STATUSES:
            raise ValidationError("Invalid transaction status.", "transaction_status")
        self.payment_method = payment_method
        self.transaction_status = transaction_status
        self.payment_type = payment_type

    @property
    def payment_id(self):
        return self._payment_id

    @property
    def is_successful(self):
        return self.transaction_status == SUCCESSFUL
