"""Plot holders and membership categories (inheritance + polymorphism)."""
from abc import ABC, abstractmethod
from decimal import Decimal

from validation import ValidationError, require_text, validate_email, validate_phone


class PlotHolder(ABC):
    """A registered allotment user. Subclasses define the membership category."""

    @property
    @abstractmethod
    def membership_category(self):
        """Display name of the membership category."""

    @property
    @abstractmethod
    def discount_rate(self):
        """Fraction discounted from the base maintenance charge."""

    def __init__(self, holder_id, full_name, address, email, phone):
        self._holder_id = require_text(holder_id, "Holder ID", "holder_id", 30)
        self.update(full_name, address, email, phone)

    @property
    def holder_id(self):
        return self._holder_id

    def update(self, full_name, address, email, phone):
        full_name = require_text(full_name, "Full name", "full_name")
        if not any(ch.isalpha() for ch in full_name):
            raise ValidationError("Full name must contain letters.", "full_name")
        checked = (
            full_name,
            require_text(address, "Address", "address", 300),
            validate_email(email),
            validate_phone(phone),
        )
        self.full_name, self.address, self.email, self.phone = checked

    def __str__(self):
        return f"{self.holder_id} - {self.full_name}"


class StandardMember(PlotHolder):
    membership_category = "Standard Member"
    discount_rate = Decimal("0.00")


class ConcessionaryMember(PlotHolder):
    membership_category = "Concessionary Member"
    discount_rate = Decimal("0.25")


MEMBERSHIP_TYPES = {cls.membership_category: cls for cls in (StandardMember, ConcessionaryMember)}


def create_holder(category, holder_id, full_name, address, email, phone):
    """Factory returning the right PlotHolder subclass for a category name."""
    try:
        holder_class = MEMBERSHIP_TYPES[category]
    except KeyError:
        raise ValidationError("Please choose a valid membership category.", "category")
    return holder_class(holder_id, full_name, address, email, phone)
