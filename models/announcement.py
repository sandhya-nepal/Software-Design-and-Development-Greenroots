"""Site-specific announcement."""
from datetime import date

from validation import parse_date, require_text


class Announcement:
    def __init__(self, announcement_id, site_id, title, description, publication_date=None):
        self._announcement_id = require_text(announcement_id, "Announcement ID", "announcement_id", 30)
        self._site_id = require_text(site_id, "Site", "site_id", 30)
        self.update(title, description, publication_date)

    @property
    def announcement_id(self):
        return self._announcement_id

    @property
    def site_id(self):
        return self._site_id

    def update(self, title, description, publication_date=None):
        checked = (require_text(title, "Title", "title"),
                   require_text(description, "Description", "description", 2000),
                   parse_date(publication_date or date.today(), "Publication date", "publication_date"))
        self.title, self.description, self.publication_date = checked
