"""Fictional sample data, created through the service layer."""
from datetime import date, timedelta


def ago(days):
    """Dates are relative to today so the sample data is always valid (never in the future)."""
    return (date.today() - timedelta(days=days)).isoformat()


def populate(app):
    allotment = app.allotment
    sites = {
        "riverside": allotment.add_site(
            "Riverside Allotments", "Riverside Road", "Flat, sunny site beside the river.",
            "Margaret Ellis", "margaret.ellis@greenroots.example", "01632 960101",
            "Water taps, Tool shed, Compost bins", site_id="SITE-001"),
        "greenfield": allotment.add_site(
            "Greenfield Allotments", "Greenfield Lane", "Sheltered site with raised beds.",
            "Tom Hargreaves", "tom.hargreaves@greenroots.example", "01632 960102",
            "Water taps, Greenhouse, Car park", site_id="SITE-002"),
        "meadow": allotment.add_site(
            "Meadow View Allotments", "Meadow View Road", "Large site with wildflower borders.",
            "Priya Nair", "priya.nair@greenroots.example", "01632 960103",
            "Water taps, Picnic area, Tool shed", site_id="SITE-003"),
    }
    layout = {
        "riverside": [("50", "North row"), ("75", "North row"), ("100", "Centre"), ("125", "South row"), ("150", "South row")],
        "greenfield": [("50", "East corner"), ("75", "Lane side"), ("100", "Lane side"), ("125", "Orchard edge")],
        "meadow": [("75", "Gate side"), ("100", "Gate side"), ("125", "Wildflower border"), ("150", "Far field")],
    }
    for key, plots in layout.items():
        for size, place in plots:
            allotment.add_plot(sites[key].site_id, size, place)
    people = [
        ("Standard Member", "Alice Morgan", "12 Oak Street", "alice.morgan@example.com", "07700 900111"),
        ("Concessionary Member", "Bernard Cole", "4 Mill Lane", "bernard.cole@example.com", "07700 900222"),
        ("Standard Member", "Chloe Patel", "88 Station Road", "chloe.patel@example.com", "07700 900333"),
        ("Concessionary Member", "David Okafor", "21 Elm Close", "david.okafor@example.com", "07700 900444"),
        ("Standard Member", "Eleni Papas", "7 Rose Avenue", "eleni.papas@example.com", "07700 900555"),
        ("Standard Member", "Frank Weston", "30 High Street", "frank.weston@example.com", "07700 900666"),
    ]
    for person in people:
        allotment.add_holder(*person)
    allocations = [
        ("PLOT-001", "HLD-001", ago(300)), ("PLOT-003", "HLD-002", ago(280)),
        ("PLOT-004", "HLD-001", ago(250)), ("PLOT-006", "HLD-003", ago(290)),
        ("PLOT-008", "HLD-004", ago(220)), ("PLOT-010", "HLD-005", ago(270)),
        ("PLOT-012", "HLD-002", ago(190)),
    ]
    for plot_id, holder_id, when in allocations:
        app.allocation.create_allocation(plot_id, holder_id, when)
