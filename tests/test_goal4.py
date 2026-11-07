"""Stage 4 (Rounds 12 to 16): the front page and bot help, below the pane.

Test names carry the use-case IDs of docs/use-cases-4.md.
"""

import time
from pathlib import Path

import pytest

from rung_engine import HUMAN, api
from rung_engine.service import Service

ROOT = Path(__file__).resolve().parents[1]


def _wait(svc, job_id, timeout=10):
    end = time.time() + timeout
    while time.time() < end:
        j = svc.engine.bot_job(job_id)
        if j["status"] != "running":
            return j
        time.sleep(0.05)
    raise AssertionError(f"job {job_id} still running")


def _rungs(e):
    return e._q("SELECT COUNT(*) AS n FROM rungs")[0]["n"]


@pytest.fixture
def bot(seeded):
    """csvtidy (N-1 with R-1, R-2 approved, S-1.1 and S-2.1 approved) and notes-sync, stub drafting."""
    svc = Service(seeded, inline_runs=True)
    yield svc
    for row in seeded._q("SELECT pk FROM bot_jobs WHERE status='running'"):
        seeded.cancel_bot(row["pk"])
    svc.wait_idle()


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


def test_bot01_bot02_place_names_kind_parent_and_why(bot):
    before = _rungs(bot.engine)
    j = bot.place("csvtidy", "Accept a two-digit year only with --century", wait=True)
    r = j["result"]
    assert j["status"] == "done" and r["kind"] == "requirement" and r["parent"] == "N-1" and r["why"]
    assert r["valid"] is True and r["reason"] == ""
    assert j["profile"] == "drafting"
    assert _rungs(bot.engine) == before  # placing stores no rung


def test_bot02_place_under_retired_or_wrong_parent_is_not_offered(bot):
    e = bot.engine
    assert e.check_place("csvtidy", "requirement", "N-1") == ""
    assert "cannot sit under" in e.check_place("csvtidy", "test", "R-1")
    assert "not in csvtidy" in e.check_place("csvtidy", "requirement", "N-9")
    assert e.check_place("csvtidy", "need", None) == ""
    assert "is not a rung kind" in e.check_place("csvtidy", "epic", None)
    e.create_need("csvtidy", "Export the cleaned file as JSON")
    e.retire_need("csvtidy", "N-2", "Out of scope")
    assert "retired" in e.check_place("csvtidy", "requirement", "N-2")
    assert all(t["id"] != "N-2" for t in e.place_targets("csvtidy"))


def test_bot03_check_place_route_for_a_chosen_kind_and_parent(bot):
    status, data = api.handle(bot, "POST", "/projects/csvtidy/bot/check-place", {"kind": "specification", "parent": "R-1"})
    assert status == 200 and data == {"valid": True, "reason": ""}
    status, data = api.handle(bot, "POST", "/projects/csvtidy/bot/check-place", {"kind": "specification", "parent": "N-1"})
    assert data["valid"] is False


def test_bot04_draft_fills_fields_from_the_parent_chain(bot):
    bot.engine.set_setting("drafting", {"kind": "stub", "delay": 0.0, "profile": "writer"})
    before = _rungs(bot.engine)
    for kind, parent in (("need", None), ("requirement", "N-1"), ("specification", "R-1"), ("test", "S-1.1")):
        j = bot.draft("csvtidy", kind, parent, {}, wait=True)
        assert j["status"] == "done" and j["profile"] == "writer", j
        f = j["result"]["fields"]
        assert (f.get("text") if kind != "test" else f.get("command")), (kind, f)
    assert _rungs(bot.engine) == before


def test_bot05_draft_can_be_cancelled_and_saves_nothing(bot):
    bot.engine.set_setting("drafting", {"kind": "stub", "delay": 5.0})
    before = _rungs(bot.engine)
    j = bot.draft("csvtidy", "requirement", "N-1", {"text": "typed"})
    t0 = time.time()
    bot.cancel_bot(j["id"])
    j = _wait(bot, j["id"])
    assert j["status"] == "cancelled" and j["result"] is None and time.time() - t0 < 2
    assert _rungs(bot.engine) == before


def test_bot06_bot10_suggest_three_from_the_best_profile_accept_and_dismiss(bot):
    e = bot.engine
    out = bot.suggest("csvtidy", "N-1", wait=True)
    j = out["job"]
    assert j["status"] == "done" and j["profile"] == out["choice"]["chosen"]["profile"]
    assert out["choice"]["chosen"] == out["choice"]["ranked"][0]
    items = j["result"]["items"]
    assert len(items) == 3 and all(i["status"] == "open" for i in items)
    assert out["choice"]["ranked"][0]["parts"]
    before = [r["id"] for r in e.tree("csvtidy")[0]["children"]]
    got = e.resolve_suggest("csvtidy", j["id"], 0, True)
    assert got["rung"]["status"] == "draft" and got["rung"]["parent"] == "N-1"
    e.resolve_suggest("csvtidy", j["id"], 1, False)
    after = [r["id"] for r in e.tree("csvtidy")[0]["children"]]
    assert after == before + [got["rung"]["id"]]
    assert [i["status"] for i in e.bot_job(j["id"])["result"]["items"]] == ["accepted", "dismissed", "open"]
    with pytest.raises(Exception):
        e.resolve_suggest("csvtidy", j["id"], 0, True)  # nothing lands twice


def test_bot07_suggest_excludes_authors_and_profiles_at_capacity(bot):
    e = bot.engine
    out = bot.suggest("csvtidy", "N-1", wait=True)
    first, second = [r["profile"] for r in out["choice"]["ranked"][:2]]
    made = e.resolve_suggest("csvtidy", out["job"]["id"], 0, True)["rung"]["id"]
    choice = e.suggest_choice("csvtidy", "N-1")
    assert {"profile": first, "reason": f"author of {made}"} in choice["excluded"]
    assert choice["chosen"]["profile"] == second
    # A running Suggest counts toward At once.
    e.save_profiles([{"name": second, "at_once": 1}])
    e.set_setting("drafting", {"kind": "stub", "delay": 5.0})
    run = bot.suggest("csvtidy", "N-1")["job"]
    assert run["profile"] == second
    assert any(x["profile"] == second and x["reason"] == "at capacity 1 of 1" for x in e.suggest_choice("csvtidy", "N-1")["excluded"])
    bot.cancel_bot(run["id"])


def test_bot08_bot09_no_eligible_profile_runs_nothing_and_cancel_proposes_nothing(bot):
    e = bot.engine
    e.set_setting("drafting", {"kind": "stub", "delay": 5.0})
    run = bot.suggest("csvtidy", "N-1")["job"]
    t0 = time.time()
    bot.cancel_bot(run["id"])
    run = _wait(bot, run["id"])
    assert run["status"] == "cancelled" and run["result"] is None and time.time() - t0 < 5
    e.save_profiles([{"name": n, "enabled": False} for n in ("coder", "reviewer", "writer", "researcher")])
    jobs = e._q("SELECT COUNT(*) AS n FROM bot_jobs")[0]["n"]
    out = bot.suggest("csvtidy", "N-1")
    assert out["job"] is None and out["choice"]["chosen"] is None
    assert {x["profile"] for x in out["choice"]["excluded"]} == {"coder", "reviewer", "writer", "researcher"}
    assert all(x["reason"] == "disabled" for x in out["choice"]["excluded"])
    assert e._q("SELECT COUNT(*) AS n FROM bot_jobs")[0]["n"] == jobs


def test_bot11_result_older_than_the_requirements_is_changed_since(bot):
    e = bot.engine
    j = bot.suggest("csvtidy", "N-1", wait=True)["job"]
    assert e.bot_job(j["id"])["changed_since"] is False
    e.add_requirement("csvtidy", "N-1", "Keep the header row", HUMAN)
    assert e.bot_job(j["id"])["changed_since"] is True
    assert e.resolve_suggest("csvtidy", j["id"], 2, True)["rung"]["status"] == "draft"


def test_bot12_no_bot_action_is_read_by_check_or_the_done_hook(bot):
    e = bot.engine
    before = [e.check("csvtidy", s) for s in ("S-1.1", "S-2.1")]
    bot.place("csvtidy", "Run pytest and expect exit code 0", wait=True)
    bot.draft("csvtidy", "test", "S-1.1", {}, wait=True)
    j = bot.suggest("csvtidy", "N-1", wait=True)["job"]
    e.resolve_suggest("csvtidy", j["id"], 1, False)
    assert [e.check("csvtidy", s) for s in ("S-1.1", "S-2.1")] == before
    for f in ("hook.py", "claims.py"):
        src = (ROOT / "rung_engine" / f).read_text()
        assert "bot_jobs" not in src and "drafting" not in src and "from .bot" not in src, f


def test_bot13_a_bot_failure_shows_its_reason(bot):
    bot.engine.set_setting("drafting", {"kind": "stub", "delay": 0.0, "fail": "the profile timed out"})
    for j in (bot.place("csvtidy", "Something", wait=True), bot.draft("csvtidy", "requirement", "N-1", {}, wait=True),
              bot.suggest("csvtidy", "N-1", wait=True)["job"]):
        assert j["status"] == "failed" and j["error"] == "the profile timed out"


def test_bot_routes(bot):
    status, data = api.handle(bot, "POST", "/projects/csvtidy/bot/place", {"text": ""})
    assert status == 400 and data["field"] == "text"
    status, data = api.handle(bot, "POST", "/projects/csvtidy/needs/N-1/suggest-missing", {})
    assert status == 200 and data["job"]["status"] in ("running", "done")
    bot.wait_idle()
    status, data = api.handle(bot, "GET", "/projects/csvtidy/needs/N-1/suggest-latest", None)
    assert data["job"]["id"] and len(data["job"]["result"]["items"]) == 3
    status, data = api.handle(bot, "POST", f"/projects/csvtidy/bot/{data['job']['id']}/items/0", {"accept": True})
    assert status == 200 and data["rung"]["status"] == "draft"
    assert api.handle(bot, "GET", "/bot/99999", None)[0] == 404


def test_bot09_profile_drafter_stops_the_child_on_cancel(tmp_path):
    from rung_engine.drafting import DraftFailed, ProfileDrafter
    fake = tmp_path / "hermes"
    fake.write_text("#!/bin/sh\nsleep 30\necho '[\"a\", \"b\", \"c\"]'\n")
    fake.chmod(0o755)
    d = ProfileDrafter("writer", hermes_bin=str(fake), timeout=60)
    t0 = time.time()
    d.should_cancel = lambda: time.time() - t0 > 0.5
    with pytest.raises(DraftFailed, match="cancelled"):
        d.suggest_missing("Need", [], {"folder": str(tmp_path)})
    assert time.time() - t0 < 5


def test_bot06_profile_drafter_reads_three_requirements(tmp_path):
    from rung_engine.drafting import ProfileDrafter
    fake = tmp_path / "hermes"
    fake.write_text("#!/bin/sh\necho 'Here: [\"One\", \"Two\", \"Three\"]'\n")
    fake.chmod(0o755)
    assert ProfileDrafter("writer", hermes_bin=str(fake)).suggest_missing("Need", [], {"folder": str(tmp_path)}) == ["One", "Two", "Three"]


def test_bot07_accepted_suggestions_are_written_by_the_drafting_profile(bot):
    e = bot.engine
    e.set_setting("drafting", {"kind": "stub", "delay": 0.0, "profile": "researcher"})
    status, need = api.handle(bot, "POST", "/projects/csvtidy/needs", {"text": "Merge two exports", "requirements": ["Keep both headers"]})
    assert status == 200
    req = e.rung("csvtidy", need["children"][0]["id"]) if need.get("children") else e.tree("csvtidy")[-1]["children"][0]
    assert any(x["profile"] == "researcher" and x["reason"].startswith("author of") for x in e.suggest_choice("csvtidy", need["id"])["excluded"]), req


def test_nav10_a_refused_project_names_every_field(tmp_path):
    from rung_engine import Engine, RungError
    e = Engine(tmp_path / "r.db")
    e.save_profiles([{"name": "coder"}])
    (tmp_path / "p").mkdir()
    e.create_project("p", str(tmp_path / "p"), "true", ["coder"])
    with pytest.raises(RungError) as got:
        e.create_project("p", str(tmp_path / "missing"), "", [])
    assert set(got.value.fields) == {"name", "folder", "test_command", "profiles"}
    svc = Service(e)
    status, body = api.handle(svc, "POST", "/projects", {"name": "p", "folder": str(tmp_path / "missing"), "test_command": "true", "profiles": ["coder"]})
    assert status in (400, 409) and set(body["fields"]) == {"name", "folder"} and body["field"] in body["fields"]
    with pytest.raises(RungError) as got:
        e.update_project("p", new_name="", folder=str(tmp_path / "missing"), test_command="")
    assert set(got.value.fields) == {"name", "folder", "test_command"}
    e.close()
