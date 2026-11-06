"""Hardening round 3: one regression per defect found."""

import os
import types
from pathlib import Path

import pytest

from rung_engine import Engine, RungError, api, core, hook
from rung_engine.claims import canonical_rid, rids_in
from rung_engine.service import Service
from support import seed
from test_hardening_b1 import _ai_spec, _decide, _fresh_hook, _todo, failing, tool  # noqa: F401  (fixtures)

SRC = Path(__file__).resolve().parents[1] / "desktop" / "src"


# ------------------------------------------------------------------ the done hook


@pytest.mark.parametrize("content", ["Ship S\u200b-2.1", "Ship S-\u200d2.1", "Ship S\u00ad2.1", "Ship \ufeffS-2.1"])
def test_r3_an_invisible_character_inside_the_id_still_names_the_spec(failing, tool, content):
    e, _ = failing
    tool("rung_claim", {"spec": "S-2.1"})
    assert _decide(e, "todo_list", _todo(("t1", content, "completed")))


def test_r3_every_door_reads_invisible_and_full_width_forms():
    assert canonical_rid("S\u200b-2.1") == "S-2.1"
    assert canonical_rid("\uff33\u20112.1") == "S-2.1"
    assert rids_in("Ship S\u00ad2.1") == ["S-2.1"]


def test_r3_a_short_todo_id_is_not_read_into_its_content(failing, tool):
    e, _ = failing
    tool("rung_claim", {"spec": "S-2.1"})
    assert _decide(e, "todo_list", _todo(("S", "2.1 percent more coffee", "completed"))) is None


def test_r3_an_id_past_the_memory_limit_still_counts_as_naming_the_spec(failing, tool, monkeypatch):
    e, _ = failing
    monkeypatch.setattr(hook, "_MAX_RIDS", 5)
    tool("rung_claim", {"spec": "S-2.1"})
    assert _decide(e, "todo_list", _todo(("t1", "S-9.1 S-9.2 S-9.3 S-9.4 S-9.5", "pending"))) is None
    assert _decide(e, "todo_list", _todo(("t1", "Ship S-2.1", "pending"), merge=True)) is None
    assert _decide(e, "todo_list", {"todos": [{"id": "t1", "status": "completed"}], "merge": True})


def test_r3_a_completion_let_through_while_the_store_was_unreadable_is_judged_once_it_reads(failing, tool, tmp_path):
    e, _ = failing
    tool("rung_claim", {"spec": "S-2.1"})
    bad = tmp_path / "rung.db"
    bad.write_text("not a database")
    done = _todo(("t1", "Ship S-2.1", "completed"))
    assert hook.decide("todo_list", done, "sess-1", store=bad) is None  # fail open
    assert _decide(e, "todo_list", done)  # the same completion, judged now the store reads


# ------------------------------------------------------------------ claims, carriers, ids


def test_r3_claiming_again_as_another_profile_is_refused(failing, tool):
    tool("rung_claim", {"spec": "S-2.1"}, profile="coder")
    out = tool("rung_claim", {"spec": "S-2.1"}, profile="writer")
    assert "held by this chat as coder" in out["error"]


def test_r3_a_run_is_not_load_against_its_own_spec(failing):
    e, _ = failing
    e.save_profiles([{"name": "coder", "at_once": 1}])
    e.start_run("csvtidy", "S-2.1", profile="coder")
    assert not any(x["profile"] == "coder" for x in e.suggest("csvtidy", "S-2.1")["excluded"])
    assert e.exclusion("csvtidy", "S-2.1", "coder") == ""
    assert "at capacity" in e.exclusion("csvtidy", "S-1.1", "coder")


@pytest.mark.parametrize("rid", ["s-2.1", " S 2.1 ", "S\u20112.1", "S2.1"])
def test_r3_every_engine_door_reads_the_id_one_way(failing, rid):
    e, _ = failing
    assert e.rung("csvtidy", rid)["id"] == "S-2.1"
    assert e.suggest("csvtidy", rid) is not None
    r = e.start_run("csvtidy", rid, profile="coder")
    assert r["spec"] == "S-2.1"


def test_r3_the_api_reads_the_id_one_way(failing):
    e, _ = failing
    svc = Service(e, inline_runs=True)
    st, out = api.handle(svc, "GET", "/projects/csvtidy/rungs/s-2.1")
    assert st == 200 and out["id"] == "S-2.1"


def test_r3_a_custom_hermes_home_is_not_the_default_profile(tmp_path, monkeypatch):
    from rung_engine import tools
    home = tmp_path / "elsewhere"
    home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(home))
    monkeypatch.setitem(tools.PROFILE, "ctx", types.SimpleNamespace(profile_name="custom"))
    assert tools._proposer() == "custom"
    prof = tmp_path / "profiles" / "writer"
    prof.mkdir(parents=True)
    monkeypatch.setenv("HERMES_HOME", str(prof))
    assert tools._proposer() == "writer"


# ------------------------------------------------------------------ cancellation


def test_r3_a_cancel_landing_as_the_command_finishes_is_never_a_pass(failing, monkeypatch):
    e, restore = failing
    restore()
    n = e.begin_execution("csvtidy", "T-2.1a")
    real = core.run_command

    def finish_then_cancel(*a, **k):
        res = real(*a, **k)
        e.cancel_execution("csvtidy", "T-2.1a", n)  # the person's Cancel lands now
        return res

    monkeypatch.setattr(core, "run_command", finish_then_cancel)
    x = e.perform_execution("csvtidy", "T-2.1a", n)
    assert x["status"] == "cancelled"
    assert e.executions("csvtidy", "T-2.1a")[0]["status"] == "cancelled"


def test_r3_a_cancel_before_start_sticks(failing):
    e, _ = failing
    r = e.start_run("csvtidy", "S-2.1", profile="coder")
    assert r["status"] == "queued"
    assert e.cancel_run(r["id"])["status"] == "cancelled"
    assert e.start_running(r["id"], 1.0, os.getpid()) is False
    assert e.run(r["id"])["status"] == "cancelled"


def test_r3_a_cancel_while_running_wins_over_the_result(failing):
    e, _ = failing
    r = e.start_run("csvtidy", "S-2.1", profile="coder")
    assert e.start_running(r["id"], 1.0, os.getpid())
    e.begin_attempt(r["id"], 1, "prompt", "")
    e.cancel_run(r["id"])  # accepted while running: the flag only
    assert e.run(r["id"])["status"] == "running"
    e.end_attempt(r["id"], 1, "pass", [], [], "done")
    e.finish_run(r["id"], "passed", "all tests pass", None, 1)
    out = e.run(r["id"])
    assert out["status"] == "cancelled"
    assert out["attempts"][-1]["status"] == "cancelled"


# ------------------------------------------------------------------ drafts, rename, revert


def test_r3_a_fresh_draft_of_a_stale_spec_keeps_the_approved_version(engine, csv_folder):
    svc = _ai_spec(engine, csv_folder)
    approved = engine.rung("csvtidy", "S-2.1")
    engine.edit("csvtidy", "R-2", text="Parse dates in every common format")
    assert engine.rung("csvtidy", "S-2.1")["status"] == "stale"
    engine.mark_drafting("csvtidy", "S-2.1")
    engine.finish_draft("csvtidy", "S-2.1", "Parse every common date format", approved["detail"], drafted_by="writer")
    hist = engine.history("csvtidy", "S-2.1")
    assert hist[0]["text"] == approved["text"] and len(hist) >= 2
    assert engine.rung("csvtidy", "S-2.1")["text"] == "Parse every common date format"
    assert engine.rung("csvtidy", "T-2.1a")["invalidated_by"]
    svc.wait_idle()


def test_r3_renaming_waits_for_a_draft_being_written(engine, csv_folder):
    svc = _ai_spec(engine, csv_folder)
    engine.mark_drafting("csvtidy", "S-2.1")
    with pytest.raises(RungError, match="being drafted"):
        engine.update_project("csvtidy", new_name="renamed")
    engine.update_project("csvtidy", test_command="pytest -q")  # other fields still save
    assert engine.project("csvtidy")["name"] == "csvtidy"
    svc.wait_idle()


def test_r3_revert_with_a_bad_change_id_names_the_field(seeded):
    svc = Service(seeded, inline_runs=True)
    st, out = api.handle(svc, "POST", "/projects/csvtidy/changes/x/revert", {})
    assert st == 400 and out.get("field") == "change" and "invalid literal" not in str(out)


# ------------------------------------------------------------------ the pane


def _src(name):
    return (SRC / name).read_text()


def test_r3_dock_running_lists_test_executions_like_the_full_page():
    dock = _src("70-dock.js")
    assert "d.running_tests" in dock and "DockTestRow" in dock
    assert "runs.length + claims.length + tests.length" in dock


def test_r3_dock_run_chip_uses_the_full_page_label():
    assert "'in progress'" in _src("70-dock.js")
    assert "? 'queued' : 'run')" not in _src("70-dock.js")


def test_r3_dock_need_picker_has_its_full_value_on_hover():
    dock = _src("70-dock.js")
    i = dock.index("id: 'rung-dock-need'")
    assert "title:" in dock[i:i + 300]


def test_r3_settings_marks_the_field_a_save_refused():
    home = _src("20-home.js")
    assert "'aria-invalid'" in home and "res.field" in home
    for field in ("cost", "max_runs", "at_once", "test_timeout", "output_limit"):
        assert f"mark(" in home and f"'{field}')" in home, field


def test_r3_latest_run_shows_every_test_of_that_runs_last_attempt():
    det = _src("40-detail.js")
    assert "h(SpecExecs, { tests, run: lastRun })" in det
    assert "/tests/${first}/executions" not in det


def test_r3_fresh_draft_offered_on_a_stale_ai_spec():
    assert "(r.status === 'approved' || r.status === 'stale') && r.ai_derived" in _src("40-detail.js")
