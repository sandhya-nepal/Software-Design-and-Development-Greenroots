"""Receipt issued for a successful payment."""
from models.payment import SIMULATED_CARD, SUCCESSFUL
from validation import ValidationError, parse_date, require_text, to_money


class PaymentReceipt:
    HEADING = "GreenRoots Community Association"

    def __init__(self, receipt_id, payment_id, transaction_reference, holder_id, holder_name, charge_id,
                 amount, payment_date, payment_method, remaining_balance, transaction_status):
        if transaction_status != SUCCESSFUL:
            raise ValidationError("A receipt can only be issued for a successful payment.")
        self._receipt_id = require_text(receipt_id, "Receipt number", "receipt_id", 30)
        self.payment_id = require_text(payment_id, "Payment", None, 30)
        self.transaction_reference = require_text(transaction_reference, "Transaction reference", None, 40)
        self.holder_id = require_text(holder_id, "Plot holder", None, 30)
        self.holder_name = require_text(holder_name, "Holder name")
        self.charge_id = require_text(charge_id, "Charge", None, 30)
        self.amount = to_money(amount, "Payment amount")
        self.payment_date = parse_date(payment_date, "Payment date")
        self.payment_method = require_text(payment_method, "Payment method")
        self.remaining_balance = to_money(remaining_balance, "Remaining balance")
        self.transaction_status = transaction_status

    @property
    def receipt_id(self):
        return self._receipt_id

    def render(self):
        line = "=" * 46
        lines = [line, self.HEADING.center(46), "PAYMENT RECEIPT".center(46), line,
                 f"Receipt number:        {self.receipt_id}",
                 f"Transaction reference: {self.transaction_reference}",
                 f"Holder name:           {self.holder_name}",
                 f"Holder ID:             {self.holder_id}",
                 f"Charge ID:             {self.charge_id}",
                 f"Payment amount:        £{self.amount}",
                 f"Payment method:        {self.payment_method}",
                 f"Payment date:          {self.payment_date.isoformat()}",
                 f"Remaining balance:     £{self.remaining_balance}",
                 f"Transaction status:    {self.transaction_status}", line]
        if self.payment_method == SIMULATED_CARD:
            lines.append("Simulated card payment: no real money was transferred.")
        return "\n".join(lines)
