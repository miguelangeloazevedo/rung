"""Hardening round 1: one regression per defect found."""

import json
import threading
import types
from pathlib import Path

import pytest

from rung_engine import HUMAN, Engine, RungError, api, hook
from rung_engine.claims import canonical_rid, _rx_for
from rung_engine.service import Service
from support import seed


@pytest.fixture
def failing(engine, csv_folder):
    restore = seed.seed_failing(engine, csv_folder)
    yield engine, restore
    restore()


@pytest.fixture
def tool(engine, monkeypatch):
    monkeypatch.setenv("RUNG_STORE", engine.path)
    from rung_engine import host, tools
    host._SERVICES.clear()
    monkeypatch.setitem(tools.PROFILE, "ctx", types.SimpleNamespace(profile_name="coder"))

    def call(name, args, session="sess-1", title="Fix date parsing", profile="coder"):
        tools.PROFILE["ctx"] = types.SimpleNamespace(profile_name=profile)
        return json.loads(tools.HANDLERS[name](args, session_id=session, user_task=title))

    yield call
    host._SERVICES.clear()


@pytest.fixture(autouse=True)
def _fresh_hook():
    hook.forget()
    yield
    hook.forget()


def _decide(engine, name, args, session="sess-1"):
    return hook.decide(name, args, session, store=Path(engine.path))


def _todo(*items, merge=False):
    return {"todos": [dict(zip(("id", "content", "status"), i)) for i in items], "merge": merge}


# ------------------------------------------------------------------ the done hook


def test_r1_todo_ids_are_matched_in_any_case_and_spacing_but_not_inside_longer_ids():
    rx = _rx_for("S-2.1")
    for text in ("Ship S-2.1", "ship s-2.1", "S 2.1 done", "S2.1 done", "(s-2.1)"):
        assert rx.search(text), text
    for text in ("S-2.11", "S-2.1a", "T-2.1a", "S-2.1.3", "XS-2.1"):
        assert not rx.search(text), text
    assert canonical_rid(" s-2.1 ") == "S-2.1" and canonical_rid("t 2.1A") == "T-2.1a"
    assert canonical_rid("nonsense") == "nonsense"


def test_r1_lower_case_todo_naming_the_claim_is_blocked(failing, tool):
    e, _ = failing
    tool("rung_claim", {"spec": "S-2.1"})
    assert _decide(e, "todo_list", _todo(("t1", "Ship s-2.1", "completed")))
    assert _decide(e, "todo_list", _todo(("t2", "Ship S-2.1a", "completed"))) is None


def test_r1_rewording_an_id_does_not_forget_the_spec_it_named(failing, tool):
    e, _ = failing
    tool("rung_claim", {"spec": "S-2.1"})
    assert _decide(e, "todo_list", _todo(("t1", "Fix S-2.1", "pending"))) is None
    assert _decide(e, "todo_list", _todo(("t1", "Tidy up", "pending"), merge=True)) is None
    assert _decide(e, "todo_list", _todo(("t1", "Tidy up", "completed"), merge=True))
    assert _decide(e, "todo_list", {"todos": [{"id": "t1", "status": "completed"}], "merge": True})


def test_r1_a_reused_completed_id_with_new_content_is_checked_again(failing, tool):
    e, _ = failing
    assert _decide(e, "todo_list", _todo(("1", "Read the docs", "completed"))) is None  # no claim yet
    tool("rung_claim", {"spec": "S-2.1"})
    # re-sending it unchanged declares nothing new
    assert _decide(e, "todo_list", _todo(("1", "Read the docs", "completed"))) is None
    # the same id now names the claim: blocked
    assert _decide(e, "todo_list", _todo(("1", "Ship S-2.1", "completed")))


def test_r1_report_hook_matches_the_project_the_tool_acts_on(failing, tool, tmp_path):
    e, _ = failing
    tool("rung_claim", {"spec": "S-2.1"})
    assert _decide(e, "rung_report", {"spec": "s-2.1"})  # no project: the open project, and any case
    assert _decide(e, "rung_report", {"spec": "S-2.1", "project": "notes-sync"}) is None


# ------------------------------------------------------------------ claims


def test_r1_claims_from_two_engines_never_both_hold_one_spec(failing):
    e, _ = failing
    others = [Engine(e.path) for _ in range(4)]
    wins, errors = [], []

    def go(i, eng):
        try:
            eng.claim("csvtidy", "S-2.1", f"sess-{i}", f"chat {i}", "coder")
            wins.append(i)
        except RungError as exc:
            errors.append(exc.code)

    ths = [threading.Thread(target=go, args=(i, x)) for i, x in enumerate(others)]
    [t.start() for t in ths]
    [t.join() for t in ths]
    [x.close() for x in others]
    assert len(wins) == 1 and set(errors) == {"conflict"}
    assert len(e.claims("csvtidy")) == 1


def test_r1_report_never_overwrites_a_release(failing):
    e, restore = failing
    e.claim("csvtidy", "S-2.1", "sess-1", "chat", "coder")
    restore()
    e.run_test("csvtidy", "T-2.1a")
    e.release_claim("csvtidy", "S-2.1")
    with pytest.raises(RungError) as exc:
        e.report("csvtidy", "S-2.1", "sess-1")
    assert exc.value.code == "no_claim"
    assert [c["status"] for c in e.claims("csvtidy", open_only=False)] == ["released"]


def test_r1_claim_names_every_reason_and_rechecks_its_own_claim(failing, tool):
    e, _ = failing
    e.set_allocation("csvtidy", "S-1.1", human_only=True, required_tools=["browser"])
    out = tool("rung_claim", {"spec": "S-1.1"})
    assert out["code"] == "human_only" and "S-1.1 is human only" in out["error"]
    why = e.exclusion("csvtidy", "S-1.1", "coder")
    assert "missing tool browser" in why and why in out["error"]
    # a claim already held is checked again: since marked human only, claiming again is refused
    tool("rung_claim", {"spec": "S-2.1"})
    e.set_allocation("csvtidy", "S-2.1", human_only=True)
    assert tool("rung_claim", {"spec": "S-2.1"})["code"] == "human_only"


def test_r1_claim_and_develop_run_exclude_each_other(engine, tmp_path):
    e = engine
    seed.seed_built(e, seed.copy_fixture("csvtidy", tmp_path / "b"))
    e.claim("csvtidy", "S-1.1", "sess-1", "chat", "coder")
    with pytest.raises(RungError, match="held by chat"):
        e.start_run("csvtidy", "S-1.1", profile="coder")
    e.release_claim("csvtidy", "S-1.1")
    e.start_run("csvtidy", "S-1.1", profile="coder")
    with pytest.raises(RungError, match="develop run"):
        e.claim("csvtidy", "S-1.1", "sess-2", "chat", "coder")


def test_r1_all_manual_tests_name_human_only_on_send(engine, tmp_path):
    e = engine
    seed.seed_built(e, seed.copy_fixture("csvtidy", tmp_path / "b"))
    e.edit_test("csvtidy", "T-1.1a", {"type": "manual", "text": "Look at it", "steps": ["Open the file"]})
    e.approve("csvtidy", "T-1.1a", HUMAN)  # accepted again: the only gate left is the filters
    assert e.suggest("csvtidy", "S-1.1")["human_only_reason"] == "all tests manual"
    with pytest.raises(RungError, match="human only"):  # not "no accepted command test"
        e.start_run("csvtidy", "S-1.1")


def test_r1_independence_names_the_rung_the_profile_wrote(seeded):
    e = seeded
    e.propose("csvtidy", "S-2.1", "test", "pytest tests/test_dates.py", "reviewer")
    e.set_allocation("csvtidy", "S-2.1", independent=True)
    reasons = {x["profile"]: x["reason"] for x in e.suggest("csvtidy", "S-2.1")["excluded"]}
    assert reasons["reviewer"] == "author of T-2.1c"


def test_r1_required_tools_compare_without_case(seeded):
    e = seeded
    e.save_profiles([{**e.profile("coder"), "tools": ["terminal"]}])
    e.set_allocation("csvtidy", "S-2.1", required_tools=["Terminal"])
    assert e.exclusion("csvtidy", "S-2.1", "coder") == ""


def test_r1_archive_and_retire_wait_for_open_claims(failing):
    e, _ = failing
    e.claim("csvtidy", "S-2.1", "sess-1", "chat", "coder")
    with pytest.raises(RungError, match="open claim"):
        e.archive_project("csvtidy")
    e.release_claim("csvtidy", "S-2.1")
    e.archive_project("csvtidy")
    with pytest.raises(RungError):
        e.release_claim("csvtidy", "S-2.1")  # read only, like claim and report


def test_r1_a_spec_in_an_archived_project_can_still_be_read(failing):
    e, _ = failing
    svc = Service(e, inline_runs=True)
    e.archive_project("csvtidy")
    st, r = api.handle(svc, "GET", "/projects/csvtidy/rungs/S-2.1", None)
    assert st == 200 and r["id"] == "S-2.1"


# ------------------------------------------------------------------ fresh draft and revert


def _ai_spec(engine, csv_folder):
    seed.seed_csvtidy(engine, csv_folder, with_history=False)
    engine.set_setting("drafting", {"kind": "stub", "delay": 0.0, "profile": "coder"})
    svc = Service(engine, inline_runs=True)
    engine.approve_requirements("csvtidy", "N-1")
    svc.set_authoring("csvtidy", "R-2", "ai", wait=True)
    engine.approve("csvtidy", "S-2.1")
    return svc


def test_r1_fresh_draft_refused_on_a_person_written_draft(engine, csv_folder):
    seed.seed_csvtidy(engine, csv_folder, with_history=False)
    engine.approve_requirements("csvtidy", "N-1")
    engine.write_spec("csvtidy", "R-3", seed.S31)
    with pytest.raises(RungError, match="written by you"):
        engine.mark_drafting("csvtidy", "S-3.1")


def test_r1_a_fresh_draft_changing_only_detail_invalidates_results(engine, csv_folder):
    svc = _ai_spec(engine, csv_folder)
    before = engine.rung("csvtidy", "S-2.1")
    engine.mark_drafting("csvtidy", "S-2.1")
    engine.finish_draft("csvtidy", "S-2.1", before["text"], detail="New detail", drafted_by="writer")
    assert engine.rung("csvtidy", "T-2.1a")["invalidated_by"] == "S-2.1 redrafted"
    hist = engine.history("csvtidy", "S-2.1")
    assert hist[-1]["by"] == "writer"  # the new version's words are the drafting profile's
    svc.wait_idle()


def test_r1_a_second_fresh_draft_still_invalidates(engine, csv_folder):
    svc = _ai_spec(engine, csv_folder)
    before = engine.rung("csvtidy", "S-2.1")
    engine.mark_drafting("csvtidy", "S-2.1")
    n = len(engine.changes("csvtidy", "S-2.1"))
    engine.finish_draft("csvtidy", "S-2.1", before["text"], before["detail"], drafted_by="coder")  # unchanged
    assert len(engine.changes("csvtidy", "S-2.1")) == n
    engine.mark_drafting("csvtidy", "S-2.1")
    engine.finish_draft("csvtidy", "S-2.1", before["text"] + " and time zones", before["detail"], drafted_by="coder")
    ch = engine.changes("csvtidy", "S-2.1")
    assert len(ch) == n + 1 and ch[0]["before"] == before["text"]
    assert engine.rung("csvtidy", "T-2.1a")["invalidated_by"] == "S-2.1 redrafted"
    svc.wait_idle()


def test_r1_revert_refuses_a_change_with_a_later_edit_on_top(seeded):
    e = seeded
    e.edit("csvtidy", "R-2", text="Parse dates in ISO and day-first formats", actor=HUMAN)
    first = e.changes("csvtidy", "R-2")[0]
    e.edit("csvtidy", "R-2", text="Parse dates in every common format", actor=HUMAN)
    with pytest.raises(RungError, match="changed again"):
        e.revert_change("csvtidy", first["id"], HUMAN)
    assert e.rung("csvtidy", "R-2")["text"] == "Parse dates in every common format"


def test_r1_revert_keeps_a_stale_rung_stale(seeded):
    e = seeded
    e.edit("csvtidy", "S-2.1", text="Parse ISO dates, reject the rest", actor=HUMAN, approve=True)
    ch = e.changes("csvtidy", "S-2.1")[0]
    e.edit("csvtidy", "R-2", text="Parse dates in every common format", actor=HUMAN)
    assert e.rung("csvtidy", "S-2.1")["status"] == "stale"
    e.revert_change("csvtidy", ch["id"], HUMAN)
    assert e.rung("csvtidy", "S-2.1")["status"] == "stale"


# ------------------------------------------------------------------ REST: cancels, forms, settings


def test_r1_cancelling_what_is_not_running_is_refused(failing):
    e, _ = failing
    svc = Service(e, inline_runs=True)
    n = e.executions("csvtidy", "T-2.1a")[0]["n"]
    st, out = api.handle(svc, "POST", f"/projects/csvtidy/tests/T-2.1a/executions/{n}/cancel", {})
    assert st == 409 and out["code"] == "not_running"
    st, out = api.handle(svc, "POST", "/projects/csvtidy/tests/T-2.1a/executions/x/cancel", {})
    assert st in (400, 404)
    st, out = api.handle(svc, "POST", "/runs/99999/cancel", {})
    assert st == 404


@pytest.mark.parametrize("body,field", [
    ({"profiles": "coder"}, "profiles"),
    ({"profiles": [123]}, "profiles"),
    ({"profiles": []}, "profiles"),
    ({"profiles": ["nobody"]}, "profiles"),
    ({"name": 7}, "name"),
    ({"test_command": ["pytest"]}, "test_command"),
    ({"folder": 3}, "folder"),
])
def test_r1_new_project_refuses_wrong_typed_fields_on_their_field(seeded, csv_folder, body, field):
    svc = Service(seeded, inline_runs=True)
    before = len(seeded.projects())
    full = {"name": "fresh", "folder": str(csv_folder), "test_command": "pytest", **body}
    st, out = api.handle(svc, "POST", "/projects", full)
    assert st == 400 and out.get("field") == field, out
    assert len(seeded.projects()) == before


def test_r1_project_names_differing_only_in_case_are_duplicates(seeded, csv_folder):
    with pytest.raises(RungError) as exc:
        seeded.create_project("CSVTIDY", str(csv_folder), "pytest", ["coder"])
    assert exc.value.field == "name"


def test_r1_project_settings_refuse_a_string_of_profiles(seeded):
    svc = Service(seeded, inline_runs=True)
    st, out = api.handle(svc, "POST", "/projects/csvtidy/update", {"profiles": "coder"})
    assert st == 400 and out["field"] == "profiles"


@pytest.mark.parametrize("body,field", [
    ({"settings": {"test_timeout": "ten"}}, "test_timeout"),
    ({"settings": {"output_limit": -5}}, "output_limit"),
    ({"profiles": [{"name": "coder", "at_once": 0}]}, "at_once"),
    ({"profiles": [{"name": "coder", "cost": "5"}]}, "cost"),
    ({"profiles": [{"name": "coder", "labels": "python"}]}, "labels"),
    ({"profiles": [{"name": "ghost"}]}, "profiles"),
    ({"profiles": "coder"}, "profiles"),
])
def test_r1_settings_save_is_all_or_nothing_and_names_the_field(seeded, body, field):
    svc = Service(seeded, inline_runs=True)
    before = (seeded.settings(), seeded.profiles())
    full = {"settings": {"test_timeout": 30, **body.get("settings", {})}}
    if "profiles" in body:
        full["profiles"] = body["profiles"]
    st, out = api.handle(svc, "POST", "/settings", full)
    assert st == 400 and out.get("field") == field, out
    assert (seeded.settings(), seeded.profiles()) == before


def test_r1_a_partial_profile_row_keeps_the_other_fields(seeded):
    e = seeded
    e.save_profiles([{**e.profile("writer"), "enabled": False, "cost": 7}])
    e.save_profiles([{"name": "writer", "at_once": 3}])
    w = e.profile("writer")
    assert (w["at_once"], w["enabled"], w["cost"], w["labels"]) == (3, False, 7, ["docs", "specs"])
