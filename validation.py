"""Shared exception types and input-validation helpers used by every layer."""
import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

CENT = Decimal("0.01")
_EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9\-]+(\.[A-Za-z0-9\-]+)*\.[A-Za-z]{2,}$")
_PHONE_RE = re.compile(r"^\+?[0-9 ()\-]+$")


class GreenRootsError(Exception):
    """Base class for all expected application errors."""


class ValidationError(GreenRootsError):
    """Invalid user input. ``field`` names the offending field when known."""

    def __init__(self, message, field=None):
        super().__init__(message)
        self.message = message
        self.field = field


class DuplicateError(ValidationError):
    """An identifier or unique value already exists."""


class NotFoundError(GreenRootsError):
    """A referenced record does not exist."""


class BusinessRuleError(GreenRootsError):
    """An operation was refused because it would break a business rule."""


def require_text(value, label, field=None, max_length=200):
    text = ("" if value is None else str(value)).strip()
    if not text:
        raise ValidationError(f"{label} is required.", field)
    if len(text) > max_length:
        raise ValidationError(f"{label} must be at most {max_length} characters.", field)
    return text


def validate_email(value, label="Email", field="email", required=True):
    text = ("" if value is None else str(value)).strip()
    if not text:
        if required:
            raise ValidationError(f"{label} is required.", field)
        return ""
    if not _EMAIL_RE.match(text):
        raise ValidationError(f"{label} is not a valid email address.", field)
    return text


def validate_phone(value, label="Phone", field="phone", required=True):
    text = ("" if value is None else str(value)).strip()
    if not text:
        if required:
            raise ValidationError(f"{label} is required.", field)
        return ""
    digits = sum(ch.isdigit() for ch in text)
    if not _PHONE_RE.match(text) or not 7 <= digits <= 15:
        raise ValidationError(f"{label} must contain 7 to 15 digits.", field)
    return text


def to_money(value, label="Amount", field=None):
    """Convert to a Decimal rounded to two places (half-up)."""
    try:
        if isinstance(value, float):
            value = repr(value)
        amount = Decimal(str(value).strip())
    except (InvalidOperation, ValueError):
        raise ValidationError(f"{label} must be a number.", field)
    if not amount.is_finite():
        raise ValidationError(f"{label} must be a number.", field)
    return amount.quantize(CENT, rounding=ROUND_HALF_UP)


def positive_decimal(value, label, field=None):
    """Parse a strictly positive number (used for plot sizes)."""
    try:
        number = Decimal(str(value).strip())
    except (InvalidOperation, ValueError):
        raise ValidationError(f"{label} must be a number.", field)
    if not number.is_finite():
        raise ValidationError(f"{label} must be a number.", field)
    if number <= 0:
        raise ValidationError(f"{label} must be greater than zero.", field)
    return number.quantize(CENT, rounding=ROUND_HALF_UP)


def parse_date(value, label="Date", field=None, allow_future=True):
    if isinstance(value, datetime):
        value = value.date()
    if not isinstance(value, date):
        text = ("" if value is None else str(value)).strip()
        try:
            value = datetime.strptime(text, "%Y-%m-%d").date()
        except ValueError:
            raise ValidationError(f"{label} must be a valid date in YYYY-MM-DD format.", field)
    if not allow_future and value > date.today():
        raise ValidationError(f"{label} cannot be in the future.", field)
    return value
