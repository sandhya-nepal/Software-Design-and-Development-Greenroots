"""Site-specific announcements."""
from models import Announcement
from validation import DuplicateError, NotFoundError, ValidationError


class AnnouncementService:
    def __init__(self, store, ids):
        self._store = store
        self._ids = ids

    def suggest_announcement_id(self):
        return self._ids.suggest("ANN", self._store.announcements)

    def create_announcement(self, site_id, title, description, publication_date=None, announcement_id=None):
        if not site_id:
            raise ValidationError("Please choose a site for the announcement.", "site_id")
        if site_id not in self._store.sites:
            raise NotFoundError(f"Site '{site_id}' does not exist.")
        announcement_id = (announcement_id or "").strip() or self._ids.next_id("ANN", self._store.announcements)
        if announcement_id in self._store.announcements:
            raise DuplicateError(f"Announcement ID '{announcement_id}' already exists.", "announcement_id")
        announcement = Announcement(announcement_id, site_id, title, description, publication_date)
        self._store.announcements[announcement.announcement_id] = announcement
        return announcement

    def get_announcement(self, announcement_id):
        try:
            return self._store.announcements[announcement_id]
        except KeyError:
            raise NotFoundError(f"Announcement '{announcement_id}' does not exist.")

    def list_announcements(self, site_id=None):
        items = [a for a in self._store.announcements.values() if not site_id or a.site_id == site_id]
        return sorted(items, key=lambda a: (a.publication_date, a.announcement_id), reverse=True)

    def update_announcement(self, announcement_id, title, description, publication_date=None):
        self.get_announcement(announcement_id).update(title, description, publication_date)
        return self._store.announcements[announcement_id]

    def delete_announcement(self, announcement_id):
        self.get_announcement(announcement_id)
        del self._store.announcements[announcement_id]
