"""Stage 4 (Rounds 12 to 16): the front page and bot help, below the pane.

Test names carry the use-case IDs of docs/use-cases-4.md.
"""

from rung_engine import api
from rung_engine.service import Service


def test_frt_01_02_05_overview_groups_needs_you_by_project(seeded):
    ov = seeded.overview()
    names = [g["name"] for g in ov["projects"]]
    assert set(names) == {p["name"] for p in seeded.projects()}
    for g in ov["projects"]:
        # Each group equals that project's Home tile (FRT-05).
        assert len(g["items"]) == seeded.home(g["name"])["tiles"]["needs_you"]
        for item in g["items"]:
            assert item["id"] and "type" in item and "text" in item
    assert ov["total"] == sum(len(g["items"]) for g in ov["projects"])
    assert ov["current"] == "csvtidy"


def test_frt_03_04_overview_stats_and_archived_count(seeded):
    seeded.archive_project("notes-sync")
    ov = seeded.overview()
    assert [g["name"] for g in ov["projects"]] == ["csvtidy"]
    assert ov["archived"] == 1
    st = ov["projects"][0]["stats"]
    assert {"stale", "covered", "requirements"} <= set(st)


def test_overview_is_read_only(seeded):
    before = seeded._q("SELECT COUNT(*) AS n FROM events")[0]["n"]
    seeded.overview()
    assert seeded._q("SELECT COUNT(*) AS n FROM events")[0]["n"] == before


def test_overview_route(seeded):
    status, data = api.handle(Service(seeded), "GET", "/overview", None)
    assert status == 200 and data["total"] == sum(len(g["items"]) for g in data["projects"])
