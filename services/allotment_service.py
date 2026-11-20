"""CRUD and relationship management for sites, plots and plot holders."""
from models import AllotmentPlot, AllotmentSite, SiteManager, create_holder
from validation import BusinessRuleError, DuplicateError, NotFoundError, ValidationError


def split_list(value):
    """Accept a comma-separated string or an iterable and return a clean list."""
    if value is None:
        return []
    items = value.split(",") if isinstance(value, str) else list(value)
    return [item.strip() for item in items if item and item.strip()]


class AllotmentService:
    """Business rules for sites, plots and holders."""

    def __init__(self, store, ids):
        self._store = store
        self._ids = ids

    # ------------------------------------------------------------- sites
    def suggest_site_id(self):
        return self._ids.suggest("SITE", self._store.sites)

    def add_site(self, name, location, description, manager_name, manager_email="",
                 manager_phone="", facilities=None, site_id=None):
        manager = SiteManager(manager_name, manager_email, manager_phone)
        site_id = (site_id or "").strip() or self._ids.next_id("SITE", self._store.sites)
        if site_id in self._store.sites:
            raise DuplicateError(f"Site ID '{site_id}' already exists.", "site_id")
        site = AllotmentSite(site_id, name, location, description, manager, split_list(facilities))
        self._reject_duplicate_site_name(site.name, site.location)
        self._store.sites[site.site_id] = site
        return site

    def _reject_duplicate_site_name(self, name, location, ignore_id=None):
        for other in self._store.sites.values():
            if other.site_id != ignore_id and other.name.lower() == name.lower() \
                    and other.location.lower() == location.lower():
                raise DuplicateError(f"A site called '{name}' already exists at {location}.", "name")

    def get_site(self, site_id):
        try:
            return self._store.sites[site_id]
        except KeyError:
            raise NotFoundError(f"Site '{site_id}' does not exist.")

    def list_sites(self, search=""):
        term = (search or "").strip().lower()
        sites = [s for s in self._store.sites.values()
                 if not term or term in s.name.lower() or term in s.site_id.lower() or term in s.location.lower()]
        return sorted(sites, key=lambda s: s.site_id)

    def update_site(self, site_id, name, location, description, manager_name, manager_email="",
                    manager_phone="", facilities=None):
        site = self.get_site(site_id)
        manager = SiteManager(manager_name, manager_email, manager_phone)
        self._reject_duplicate_site_name((name or "").strip(), (location or "").strip(), site_id)
        site.update(name, location, description, manager, split_list(facilities))
        return site

    def delete_site(self, site_id):
        site = self.get_site(site_id)
        reasons = self.site_blockers(site)
        if reasons:
            raise BusinessRuleError(f"Site '{site.name}' cannot be deleted: {'; '.join(reasons)}.")
        del self._store.sites[site_id]

    def site_blockers(self, site):
        reasons = []
        if site.plot_ids:
            reasons.append(f"it still contains {len(site.plot_ids)} plot(s)")
        return reasons

    # ------------------------------------------------------------- plots
    def suggest_plot_id(self):
        return self._ids.suggest("PLOT", self._store.plots)

    def add_plot(self, site_id, size, location_within_site, plot_id=None):
        site = self.get_site(site_id) if site_id else None
        if site is None:
            raise ValidationError("Please choose a site for the plot.", "site_id")
        plot_id = (plot_id or "").strip() or self._ids.next_id("PLOT", self._store.plots)
        if plot_id in self._store.plots:
            raise DuplicateError(f"Plot ID '{plot_id}' already exists.", "plot_id")
        plot = AllotmentPlot(plot_id, site.site_id, size, location_within_site)
        self._store.plots[plot.plot_id] = plot
        site.add_plot_id(plot.plot_id)
        return plot

    def get_plot(self, plot_id):
        try:
            return self._store.plots[plot_id]
        except KeyError:
            raise NotFoundError(f"Plot '{plot_id}' does not exist.")

    def list_plots(self, site_id=None, status=None, search=""):
        term = (search or "").strip().lower()
        plots = [p for p in self._store.plots.values()
                 if (not site_id or p.site_id == site_id)
                 and (not status or p.occupancy_status == status)
                 and (not term or term in p.plot_id.lower() or term in p.location_within_site.lower())]
        return sorted(plots, key=lambda p: p.plot_id)

    def update_plot(self, plot_id, size, location_within_site):
        plot = self.get_plot(plot_id)
        plot.update(size, location_within_site)
        return plot

    def delete_plot(self, plot_id):
        plot = self.get_plot(plot_id)
        reasons = self.plot_blockers(plot)
        if reasons:
            raise BusinessRuleError(f"Plot '{plot_id}' cannot be deleted: {'; '.join(reasons)}.")
        del self._store.plots[plot_id]
        self.get_site(plot.site_id).remove_plot_id(plot_id)

    def plot_blockers(self, plot):
        return []

    # ----------------------------------------------------------- holders
    def suggest_holder_id(self):
        return self._ids.suggest("HLD", self._store.holders)

    def add_holder(self, category, full_name, address, email, phone, holder_id=None):
        holder_id = (holder_id or "").strip() or self._ids.next_id("HLD", self._store.holders)
        if holder_id in self._store.holders:
            raise DuplicateError(f"Holder ID '{holder_id}' already exists.", "holder_id")
        holder = create_holder(category, holder_id, full_name, address, email, phone)
        self._store.holders[holder.holder_id] = holder
        return holder

    def get_holder(self, holder_id):
        try:
            return self._store.holders[holder_id]
        except KeyError:
            raise NotFoundError(f"Plot holder '{holder_id}' does not exist.")

    def list_holders(self, search="", category=None):
        term = (search or "").strip().lower()
        holders = [h for h in self._store.holders.values()
                   if (not category or h.membership_category == category)
                   and (not term or term in h.full_name.lower() or term in h.holder_id.lower())]
        return sorted(holders, key=lambda h: h.holder_id)

    def update_holder(self, holder_id, category, full_name, address, email, phone):
        """Replace the holder object so a membership change swaps the subclass."""
        current = self.get_holder(holder_id)
        replacement = create_holder(category, holder_id, full_name, address, email, phone)
        if type(replacement) is type(current):
            current.update(full_name, address, email, phone)
            return current
        self._store.holders[holder_id] = replacement
        return replacement

    def delete_holder(self, holder_id):
        holder = self.get_holder(holder_id)
        reasons = self.holder_blockers(holder)
        if reasons:
            raise BusinessRuleError(f"Holder '{holder.full_name}' cannot be deleted: {'; '.join(reasons)}.")
        del self._store.holders[holder_id]

    def holder_blockers(self, holder):
        return []
