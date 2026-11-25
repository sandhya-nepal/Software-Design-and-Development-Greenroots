"""Service tests for site, plot and holder CRUD, validation and safe deletion."""
from models import ConcessionaryMember, StandardMember
from tests.base import D, AppTestCase, GOOD_PHONE
from validation import BusinessRuleError, DuplicateError, NotFoundError, ValidationError


class SiteServiceTests(AppTestCase):
    def test_add_get_list_update_delete(self):
        site = self.make_site("Riverside", "River Road")
        self.assertIs(self.allotment.get_site(site.site_id), site)
        self.assertEqual(self.allotment.list_sites(), [site])
        self.allotment.update_site(site.site_id, "Riverside 2", "New Road", "d", "New Mgr", "", "", "A, B")
        self.assertEqual((site.name, site.location, site.facilities), ("Riverside 2", "New Road", ["A", "B"]))
        self.allotment.delete_site(site.site_id)
        self.assertEqual(self.allotment.list_sites(), [])
        with self.assertRaises(NotFoundError):
            self.allotment.get_site(site.site_id)

    def test_generated_ids_are_unique_and_sequential(self):
        ids = [self.make_site().site_id for _ in range(3)]
        self.assertEqual(ids, ["SITE-001", "SITE-002", "SITE-003"])

    def test_duplicate_id_and_duplicate_name_rejected(self):
        self.allotment.add_site("A", "Road", "", "M", site_id="S-X")
        with self.assertRaises(DuplicateError):
            self.allotment.add_site("B", "Other", "", "M", site_id="S-X")
        with self.assertRaises(DuplicateError):
            self.allotment.add_site("a", "road", "", "M")
        self.assertEqual(len(self.app.store.sites), 1)

    def test_required_fields(self):
        with self.assertRaises(ValidationError):
            self.allotment.add_site("", "Road", "", "M")
        with self.assertRaises(ValidationError):
            self.allotment.add_site("Name", "Road", "", "")
        self.assertEqual(self.app.store.sites, {})

    def test_failed_update_keeps_original(self):
        site = self.make_site("Keep", "Here")
        with self.assertRaises(ValidationError):
            self.allotment.update_site(site.site_id, "Changed", "", "", "M")
        self.assertEqual((site.name, site.location), ("Keep", "Here"))

    def test_site_with_plots_cannot_be_deleted(self):
        plot = self.make_plot()
        with self.assertRaises(BusinessRuleError):
            self.allotment.delete_site(plot.site_id)
        self.assertIn(plot.site_id, self.app.store.sites)

    def test_empty_site_with_announcement_cannot_be_deleted(self):
        site = self.make_site()
        self.announcements.create_announcement(site.site_id, "T", "D")
        with self.assertRaises(BusinessRuleError):
            self.allotment.delete_site(site.site_id)

    def test_search(self):
        self.make_site("Riverside", "River Road")
        self.make_site("Meadow", "Field Lane")
        self.assertEqual([s.name for s in self.allotment.list_sites("meadow")], ["Meadow"])
        self.assertEqual([s.name for s in self.allotment.list_sites("river")], ["Riverside"])
        self.assertEqual(self.allotment.list_sites("zzz"), [])


class PlotServiceTests(AppTestCase):
    def test_add_links_plot_to_site(self):
        site = self.make_site()
        plot = self.allotment.add_plot(site.site_id, "75", "North")
        self.assertEqual(site.plot_ids, (plot.plot_id,))
        self.assertEqual(plot.site_id, site.site_id)

    def test_plot_must_belong_to_existing_site(self):
        with self.assertRaises(NotFoundError):
            self.allotment.add_plot("SITE-404", "50", "North")
        with self.assertRaises(ValidationError):
            self.allotment.add_plot("", "50", "North")
        self.assertEqual(self.app.store.plots, {})

    def test_invalid_plot_does_not_touch_site(self):
        site = self.make_site()
        for size in ("0", "-1"):
            with self.assertRaises(ValidationError):
                self.allotment.add_plot(site.site_id, size, "North")
        with self.assertRaises(ValidationError):
            self.allotment.add_plot(site.site_id, "50", "")
        self.assertEqual(site.plot_ids, ())
        self.assertEqual(self.app.store.plots, {})

    def test_duplicate_plot_id(self):
        site = self.make_site()
        self.allotment.add_plot(site.site_id, "50", "N", "P-1")
        with self.assertRaises(DuplicateError):
            self.allotment.add_plot(site.site_id, "60", "S", "P-1")
        self.assertEqual(len(site.plot_ids), 1)

    def test_plot_ids_unique_across_sites(self):
        a, b = self.make_site(), self.make_site()
        self.allotment.add_plot(a.site_id, "50", "N", "P-1")
        with self.assertRaises(DuplicateError):
            self.allotment.add_plot(b.site_id, "50", "N", "P-1")

    def test_update_and_filters(self):
        site_a, site_b = self.make_site(), self.make_site()
        p1, p2 = self.make_plot(site_a), self.make_plot(site_b)
        self.allotment.update_plot(p1.plot_id, "80", "East")
        self.assertEqual((p1.size, p1.location_within_site), (D("80.00"), "East"))
        self.assertEqual(self.allotment.list_plots(site_id=site_a.site_id), [p1])
        self.assertEqual(self.allotment.list_plots(site_id=site_b.site_id), [p2])
        self.assertEqual(len(self.allotment.list_plots(status="Available")), 2)
        self.assertEqual(self.allotment.list_plots(status="Occupied"), [])

    def test_failed_plot_update_keeps_original(self):
        plot = self.make_plot(size="60")
        with self.assertRaises(ValidationError):
            self.allotment.update_plot(plot.plot_id, "-5", "Somewhere")
        self.assertEqual((plot.size, plot.location_within_site), (D("60.00"), "North"))

    def test_delete_removes_plot_and_site_reference(self):
        plot = self.make_plot()
        site = self.allotment.get_site(plot.site_id)
        self.allotment.delete_plot(plot.plot_id)
        self.assertEqual(site.plot_ids, ())
        self.assertNotIn(plot.plot_id, self.app.store.plots)

    def test_allocated_plot_cannot_be_deleted(self):
        plot, _, _ = self.make_allocation()
        with self.assertRaises(BusinessRuleError):
            self.allotment.delete_plot(plot.plot_id)
        self.assertIn(plot.plot_id, self.app.store.plots)


class HolderServiceTests(AppTestCase):
    def test_register_view_update_delete(self):
        holder = self.make_holder(name="Ann Lee")
        self.assertIsInstance(holder, StandardMember)
        self.allotment.update_holder(holder.holder_id, "Standard Member", "Ann Lee-Jones", "2 St", "ann@x.com", GOOD_PHONE)
        self.assertEqual(self.allotment.get_holder(holder.holder_id).full_name, "Ann Lee-Jones")
        self.allotment.delete_holder(holder.holder_id)
        with self.assertRaises(NotFoundError):
            self.allotment.get_holder(holder.holder_id)

    def test_membership_change_swaps_class_but_keeps_id(self):
        holder = self.make_holder(name="Ann Lee")
        updated = self.allotment.update_holder(holder.holder_id, "Concessionary Member", "Ann Lee", "1 St", "a@b.com", GOOD_PHONE)
        self.assertIsInstance(updated, ConcessionaryMember)
        self.assertIs(self.allotment.get_holder(holder.holder_id), updated)

    def test_failed_update_with_category_change_keeps_original(self):
        holder = self.make_holder(name="Ann Lee")
        with self.assertRaises(ValidationError):
            self.allotment.update_holder(holder.holder_id, "Concessionary Member", "Ann Lee", "1 St", "bad-email", GOOD_PHONE)
        self.assertIsInstance(self.allotment.get_holder(holder.holder_id), StandardMember)

    def test_validation_and_duplicates(self):
        self.allotment.add_holder("Standard Member", "Ann Lee", "1 St", "a@b.com", GOOD_PHONE, "H-1")
        with self.assertRaises(DuplicateError):
            self.allotment.add_holder("Standard Member", "Bob Ray", "1 St", "b@b.com", GOOD_PHONE, "H-1")
        for kwargs in ({"full_name": ""}, {"email": "nope"}, {"phone": "12"}, {"category": "VIP"}):
            args = dict(category="Standard Member", full_name="Bob Ray", address="1 St", email="b@b.com", phone=GOOD_PHONE)
            args.update(kwargs)
            with self.subTest(kwargs=kwargs), self.assertRaises(ValidationError):
                self.allotment.add_holder(**args)
        self.assertEqual(len(self.app.store.holders), 1)

    def test_search_and_category_filter(self):
        a = self.make_holder("Standard Member", "Alice Morgan")
        b = self.make_holder("Concessionary Member", "Bernard Cole")
        self.assertEqual(self.allotment.list_holders("alice"), [a])
        self.assertEqual(self.allotment.list_holders(b.holder_id.lower()), [b])
        self.assertEqual(self.allotment.list_holders(category="Concessionary Member"), [b])
        self.assertEqual(self.allotment.list_holders("nobody"), [])

    def test_holder_with_allocation_cannot_be_deleted(self):
        _, holder, _ = self.make_allocation()
        with self.assertRaises(BusinessRuleError):
            self.allotment.delete_holder(holder.holder_id)
        self.assertIn(holder.holder_id, self.app.store.holders)

    def test_empty_holder_list(self):
        self.assertEqual(self.allotment.list_holders(), [])


class ExtremeValueTests(AppTestCase):
    """Regression tests for a defect found during Day 6 probing: huge numbers crashed with decimal.InvalidOperation."""

    def test_huge_plot_sizes_give_validation_errors(self):
        site = self.make_site()
        for size in ("1e400", "1e30", "99999999999999999999999999999999", "10000.01"):
            with self.subTest(size=size), self.assertRaises(ValidationError):
                self.allotment.add_plot(site.site_id, size, "North")
        self.assertEqual(self.app.store.plots, {})
        self.assertEqual(self.allotment.add_plot(site.site_id, "10000", "North").size, D("10000.00"))
