"""Site-specific announcements."""
from datetime import date

from tests.base import AppTestCase
from validation import DuplicateError, NotFoundError, ValidationError


class AnnouncementServiceTests(AppTestCase):
    def test_create_get_update_delete(self):
        site = self.make_site()
        a = self.announcements.create_announcement(site.site_id, "Closure", "Shed closed", "2026-11-01")
        self.assertEqual((a.site_id, a.title, a.publication_date), (site.site_id, "Closure", date(2026, 11, 1)))
        self.announcements.update_announcement(a.announcement_id, "Reopened", "Shed open", "2026-11-05")
        self.assertEqual((self.announcements.get_announcement(a.announcement_id).title, a.publication_date), ("Reopened", date(2026, 11, 5)))
        self.announcements.delete_announcement(a.announcement_id)
        with self.assertRaises(NotFoundError):
            self.announcements.get_announcement(a.announcement_id)

    def test_filter_by_site_never_mixes_sites(self):
        s1, s2 = self.make_site(), self.make_site()
        a1 = self.announcements.create_announcement(s1.site_id, "One", "x", "2026-11-01")
        a2 = self.announcements.create_announcement(s2.site_id, "Two", "y", "2026-11-02")
        self.assertEqual(self.announcements.list_announcements(s1.site_id), [a1])
        self.assertEqual(self.announcements.list_announcements(s2.site_id), [a2])
        self.assertEqual(set(self.announcements.list_announcements()), {a1, a2})

    def test_newest_first(self):
        site = self.make_site()
        old = self.announcements.create_announcement(site.site_id, "Old", "x", "2026-01-01")
        new = self.announcements.create_announcement(site.site_id, "New", "x", "2026-06-01")
        self.assertEqual(self.announcements.list_announcements(), [new, old])

    def test_invalid_announcements_are_rejected_and_not_stored(self):
        site = self.make_site()
        cases = [dict(site_id="", title="T", description="D"), dict(site_id=site.site_id, title="", description="D"),
                 dict(site_id=site.site_id, title="T", description=" "),
                 dict(site_id=site.site_id, title="T", description="D", publication_date="2026-99-99")]
        for kwargs in cases:
            with self.subTest(kwargs=kwargs), self.assertRaises(ValidationError):
                self.announcements.create_announcement(**kwargs)
        with self.assertRaises(NotFoundError):
            self.announcements.create_announcement("SITE-404", "T", "D")
        self.assertEqual(self.app.store.announcements, {})

    def test_failed_update_keeps_original(self):
        site = self.make_site()
        a = self.announcements.create_announcement(site.site_id, "Keep", "Original", "2026-11-01")
        with self.assertRaises(ValidationError):
            self.announcements.update_announcement(a.announcement_id, "", "New", "2026-11-02")
        self.assertEqual((a.title, a.description, a.publication_date), ("Keep", "Original", date(2026, 11, 1)))

    def test_duplicate_id(self):
        site = self.make_site()
        self.announcements.create_announcement(site.site_id, "T", "D", announcement_id="N-1")
        with self.assertRaises(DuplicateError):
            self.announcements.create_announcement(site.site_id, "T2", "D2", announcement_id="N-1")

    def test_no_announcements(self):
        site = self.make_site()
        self.assertEqual(self.announcements.list_announcements(), [])
        self.assertEqual(self.announcements.list_announcements(site.site_id), [])
