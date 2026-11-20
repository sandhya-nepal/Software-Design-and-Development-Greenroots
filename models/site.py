"""Allotment site and site manager."""
from validation import ValidationError, require_text, validate_email, validate_phone


class SiteManager:
    """The person responsible for overseeing a site."""

    def __init__(self, name, email="", phone=""):
        self.name = require_text(name, "Site manager name", "manager_name")
        self.email = validate_email(email, "Site manager email", "manager_email", required=False)
        self.phone = validate_phone(phone, "Site manager phone", "manager_phone", required=False)

    def __str__(self):
        return self.name


class AllotmentSite:
    """A site containing plots (held by ID) and shared facilities."""

    def __init__(self, site_id, name, location, description, manager, facilities=None):
        self._site_id = require_text(site_id, "Site ID", "site_id", 30)
        self._plot_ids = []
        self.update(name, location, description, manager, facilities)

    @property
    def site_id(self):
        return self._site_id

    @property
    def plot_ids(self):
        return tuple(self._plot_ids)

    def update(self, name, location, description, manager, facilities=None):
        """Validate everything first so a failed update changes nothing."""
        if not isinstance(manager, SiteManager):
            raise ValidationError("A site manager is required.", "manager_name")
        checked = (
            require_text(name, "Site name", "name"),
            require_text(location, "Location", "location"),
            (description or "").strip(),
            manager,
            [f.strip() for f in (facilities or []) if f and f.strip()],
        )
        self.name, self.location, self.description, self.manager, self.facilities = checked

    def add_plot_id(self, plot_id):
        if plot_id not in self._plot_ids:
            self._plot_ids.append(plot_id)

    def remove_plot_id(self, plot_id):
        if plot_id in self._plot_ids:
            self._plot_ids.remove(plot_id)

    def __str__(self):
        return f"{self.site_id} - {self.name}"
