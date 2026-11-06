"""Hardening round 2: one regression per defect found."""

import os
import threading
from pathlib import Path

import pytest

from rung_engine import Engine, RungError, api, hook
from rung_engine.claims import rids_in, ClaimsMixin
from rung_engine.service import Service
from support import seed
from test_hardening_b1 import _ai_spec, _decide, _fresh_hook, _todo, failing, tool  # noqa: F401  (fixtures)


# ------------------------------------------------------------------ the done hook


def test_r2_an_id_never_forgets_the_spec_it_named_however_often_it_is_reworded(failing, tool):
    e, _ = failing
    tool("rung_claim", {"spec": "S-2.1"})
    assert _decide(e, "todo_list", _todo(("t1", "Ship S-2.1", "pending"))) is None
    for i in range(60):  # round 1 kept the last 20 contents
        assert _decide(e, "todo_list", _todo(("t1", f"filler {i}", "pending"), merge=True)) is None
    assert _decide(e, "todo_list", {"todos": [{"id": "t1", "status": "completed"}], "merge": True})


def test_r2_a_bare_id_completion_is_checked_even_after_an_earlier_allowed_one(failing, tool):
    e, _ = failing
    assert _decide(e, "todo_list", _todo(("t1", "Ship S-2.1", "pending"))) is None
    assert _decide(e, "todo_list", _todo(("t1", "Do laundry", "completed"))) is None  # no claim yet
    tool("rung_claim", {"spec": "S-2.1"})
    assert _decide(e, "todo_list", {"todos": [{"id": "t1", "status": "completed"}], "merge": True})


def test_r2_other_sessions_do_not_push_out_a_session_that_named_a_spec(failing, tool, monkeypatch):
    e, _ = failing
    monkeypatch.setattr(hook, "_MAX_SESSIONS", 50)
    assert _decide(e, "todo_list", _todo(("t1", "Ship S-2.1", "pending"))) is None
    for i in range(200):
        _decide(e, "todo_list", _todo(("x", "chores", "pending")), session=f"other-{i}")
    tool("rung_claim", {"spec": "S-2.1"})
    assert _decide(e, "todo_list", {"todos": [{"id": "t1", "status": "completed"}], "merge": True})


@pytest.mark.parametrize("content", ["Ship S\u20112.1", "Ship S\u20132.1", "Ship S\u22122.1", "ＳＨＩＰ Ｓ-２.１"])
def test_r2_any_dash_or_full_width_form_names_the_spec(failing, tool, content):
    e, _ = failing
    tool("rung_claim", {"spec": "S-2.1"})
    assert _decide(e, "todo_list", _todo(("t1", content, "completed")))


def test_r2_todos_as_json_text_and_content_that_is_not_text_are_read_like_the_todo_tool(failing, tool):
    import json
    e, _ = failing
    tool("rung_claim", {"spec": "S-2.1"})
    assert _decide(e, "todo_list", {"todos": json.dumps([{"id": "t1", "content": "Ship S-2.1",
                                                           "status": "completed"}])})
    assert _decide(e, "todo_list", _todo(("t2", ["Ship", "S-2.1"], "completed")))
    assert _decide(e, "todo_list", _todo(("t3", "Ship S-2.1", "COMPLETED")))


def test_r2_rids_in_reads_every_id_in_ladder_form():
    assert rids_in("ship s 2.1, T-2.1A and S\u20112.11; S-2.1.3") == ["S-2.1", "T-2.1a", "S-2.11", "S-2.1.3"]
    assert not ClaimsMixin.names_spec("S-2.1a", "S-2.1")


@pytest.mark.parametrize("bad", ["mode000", "not a database"])
def test_r2_an_unreadable_store_never_raises_from_decide(failing, tool, tmp_path, bad):
    e, _ = failing
    store = tmp_path / "rung.db"
    if bad == "mode000":
        store.write_bytes(Path(e.path).read_bytes())
        os.chmod(store, 0)
    else:
        store.write_text("hello")
    try:
        assert hook.decide("kanban_complete", {}, "sess-1", store=store) is None
        assert hook.decide("todo_list", _todo(("t1", "Ship S-2.1", "completed")), "sess-1", store=store) is None
    finally:
        os.chmod(store, 0o600)


# ------------------------------------------------------------------ claims and carriers


def test_r2_report_and_release_say_a_test_is_not_a_specification(failing):
    e, _ = failing
    e.claim("csvtidy", "S-2.1", "sess-1", "chat", "coder")
    for call in (lambda: e.report("csvtidy", "T-2.1a", "sess-1"), lambda: e.release_claim("csvtidy", "T-2.1a")):
        with pytest.raises(RungError, match="not a specification"):
            call()


def test_r2_release_takes_the_id_in_any_case_and_spacing(failing):
    e, _ = failing
    e.claim("csvtidy", "S-2.1", "sess-1", "chat", "coder")
    e.release_claim("csvtidy", " s 2.1 ")
    assert e.claims("csvtidy") == []


def test_r2_a_blank_spec_argument_is_a_missing_one(failing, tool):
    out = tool("rung_claim", {"spec": "   "})
    assert "spec" in out["error"] and "no  in" not in out["error"]


def test_r2_a_claim_is_not_load_against_its_own_spec(failing):
    e, _ = failing
    e.save_profiles([{"name": "coder", "at_once": 1}])
    e.claim("csvtidy", "S-2.1", "sess-1", "chat", "coder")
    assert not any(x["profile"] == "coder" for x in e.suggest("csvtidy", "S-2.1")["excluded"])
    assert e.exclusion("csvtidy", "S-2.1", "coder") == ""
    assert "S-2.1" not in [x["spec"] for x in e.exclusions("csvtidy")["profiles"]["coder"]]
    assert "at capacity" in e.exclusion("csvtidy", "S-1.1", "coder")  # still full for other work


def test_r2_two_engines_never_start_two_runs_past_at_once(engine, tmp_path):
    e = engine
    seed.seed_built(e, seed.copy_fixture("csvtidy", tmp_path / "b"))
    e.save_profiles([{"name": "coder", "at_once": 1}])
    others = [Engine(e.path) for _ in range(4)]
    wins, errors = [], []

    def go(i, eng):
        try:
            eng.start_run("csvtidy", "S-1.1", profile="coder")
            wins.append(i)
        except RungError as exc:
            errors.append(exc.code)

    ths = [threading.Thread(target=go, args=(i, x)) for i, x in enumerate(others)]
    [t.start() for t in ths]
    [t.join() for t in ths]
    [x.close() for x in others]
    assert len(wins) == 1 and errors and "ok" not in errors
    assert len([r for r in e.runs("csvtidy") if r["status"] in ("queued", "running")]) == 1


def test_r2_a_run_and_a_claim_from_two_engines_never_both_land(engine, tmp_path):
    e = engine
    seed.seed_built(e, seed.copy_fixture("csvtidy", tmp_path / "b"))
    a, b = Engine(e.path), Engine(e.path)
    res = []

    def run():
        try:
            a.start_run("csvtidy", "S-1.1", profile="coder")
            res.append("run")
        except RungError:
            pass

    def claim():
        try:
            b.claim("csvtidy", "S-1.1", "sess-1", "chat", "coder")
            res.append("claim")
        except RungError:
            pass

    ths = [threading.Thread(target=run), threading.Thread(target=claim)]
    [t.start() for t in ths]
    [t.join() for t in ths]
    a.close(), b.close()
    assert len(res) == 1, res


def test_r2_develop_is_unavailable_when_no_profile_may_carry_the_spec(engine, tmp_path):
    e = engine
    seed.seed_built(e, seed.copy_fixture("csvtidy", tmp_path / "b"))
    e.set_allocation("csvtidy", "S-1.1", required_tools=["no-such-tool"])
    ok, why = e.develop_available("csvtidy", "S-1.1")
    assert not ok and "missing tool no-such-tool" in why


def test_r2_wrong_typed_agent_is_refused_on_its_field(engine, tmp_path):
    seed.seed_built(engine, seed.copy_fixture("csvtidy", tmp_path / "b"))
    svc = Service(engine, inline_runs=True)
    for path in ("/projects/csvtidy/specs/S-1.1/pick", "/projects/csvtidy/specs/S-1.1/send"):
        st, out = api.handle(svc, "POST", path, {"agent": ["coder"]})
        assert st == 400 and out.get("field") == "agent", (path, out)


def test_r2_required_tools_errors_name_their_field(failing):
    e, _ = failing
    with pytest.raises(RungError) as exc:
        e.set_allocation("csvtidy", "S-2.1", required_tools=[7])
    assert exc.value.field == "required_tools"


# ------------------------------------------------------------------ fresh drafts


def test_r2_editing_an_open_fresh_draft_invalidates_results(engine, csv_folder):
    svc = _ai_spec(engine, csv_folder)
    before = engine.rung("csvtidy", "S-2.1")
    engine.mark_drafting("csvtidy", "S-2.1")
    engine.finish_draft("csvtidy", "S-2.1", before["text"], before["detail"], drafted_by="coder")  # unchanged
    engine.edit("csvtidy", "S-2.1", text="Dates are rejected, never parsed", approve=True)
    assert engine.rung("csvtidy", "T-2.1a")["invalidated_by"]
    assert engine.changes("csvtidy", "S-2.1")[0]["before"] == before["text"]
    svc.wait_idle()


def test_r2_every_drafting_profile_stays_an_author(engine, csv_folder):
    svc = _ai_spec(engine, csv_folder)
    before = engine.rung("csvtidy", "S-2.1")
    engine.mark_drafting("csvtidy", "S-2.1")
    engine.finish_draft("csvtidy", "S-2.1", before["text"] + " too", before["detail"], drafted_by="writer")
    engine.mark_drafting("csvtidy", "S-2.1")
    engine.finish_draft("csvtidy", "S-2.1", before["text"] + " as well", before["detail"], drafted_by="reviewer")
    engine.set_allocation("csvtidy", "S-2.1", independent=True)
    excluded = {x["profile"] for x in engine.suggest("csvtidy", "S-2.1")["excluded"]}
    assert {"writer", "reviewer"} <= excluded  # the earlier drafter stays an author
    svc.wait_idle()


# ------------------------------------------------------------------ settings and projects


@pytest.mark.parametrize("colours", [{"pass": "green"}, {"glow": "#00ff00"}, {"pass": 3}])
def test_r2_colours_are_theme_or_hex_for_known_keys(seeded, colours):
    svc = Service(seeded, inline_runs=True)
    st, out = api.handle(svc, "POST", "/settings", {"settings": {"colours": colours}})
    assert st == 400 and out.get("field") == "colours", out


def test_r2_settings_errors_name_the_profile_row_and_refuse_duplicates(seeded):
    svc = Service(seeded, inline_runs=True)
    st, out = api.handle(svc, "POST", "/settings", {"profiles": [{"name": "writer", "at_once": 0}]})
    assert st == 400 and out["detail"].startswith("writer:"), out
    st, out = api.handle(svc, "POST", "/settings", {"profiles": [{"name": "coder", "at_once": 4},
                                                                {"name": "coder", "at_once": 5}]})
    assert st == 400 and "twice" in out["detail"], out


@pytest.mark.parametrize("name", ["a#b", "a?b", "50%", ".", "..", "tab\there"])
def test_r2_project_names_that_break_a_route_are_refused(seeded, csv_folder, name):
    svc = Service(seeded, inline_runs=True)
    st, out = api.handle(svc, "POST", "/projects", {"name": name, "folder": str(csv_folder),
                                                    "test_command": "pytest", "profiles": ["coder"]})
    assert st == 400 and out.get("field") == "name", out


def test_r2_the_pane_encodes_project_names_in_every_route():
    import re
    root = Path(__file__).resolve().parents[1] / "desktop" / "src"
    raw = [f"{p.name}: {m}" for p in root.glob("*.js") for m in re.findall(r"/projects/\$\{project\}", p.read_text())]
    assert raw == []
