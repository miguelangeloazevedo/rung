"""Stage 3 (Round 7): claims, the done hook and the allocation filters, below the pane.

Test names carry the use-case IDs of docs/use-cases-3.md.
"""

import json
import os
import socket
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from rung_engine import HUMAN, Actor, Engine, RungError, allocation, db
from rung_engine import hook
from support import seed

ROOT = Path(__file__).resolve().parents[1]
CODER = Actor("agent", "coder")


@pytest.fixture
def failing(engine, csv_folder):
    """csvtidy with S-2.1 approved and T-2.1a failing now."""
    restore = seed.seed_failing(engine, csv_folder)
    yield engine, restore
    restore()


@pytest.fixture
def tool(engine, monkeypatch):
    """Call a Rung agent tool as profile `coder` from a chat session."""
    monkeypatch.setenv("RUNG_STORE", engine.path)
    from rung_engine import host, tools
    host._SERVICES.clear()
    monkeypatch.setitem(tools.PROFILE, "name", "coder")

    def call(name, args, session="sess-1", title="Fix date parsing in csvtidy"):
        return json.loads(tools.HANDLERS[name](args, session_id=session, user_task=title))

    yield call
    host._SERVICES.clear()


@pytest.fixture(autouse=True)
def _fresh_hook():
    hook.forget()
    yield
    hook.forget()


def _cli(store, *args):
    env = dict(os.environ, RUNG_STORE=str(store))
    return subprocess.run([sys.executable, "-m", "rung_engine.cli", *args], cwd=ROOT, env=env, capture_output=True,
                          text=True)


def _decide(engine, name, args, session="sess-1"):
    return hook.decide(name, args, session, store=Path(engine.path))


# ------------------------------------------------------------------ CLM claims and the done gate


def test_clm01_claim_shows_with_profile_and_chat(failing, tool):
    e, _ = failing
    out = tool("rung_claim", {"spec": "S-2.1"})
    assert out["claimed"] == "S-2.1" and out["profile"] == "coder"
    assert out["check"]["ok"] is False
    claims = e.claims("csvtidy")
    assert [(c["spec"], c["profile"], c["chat"], c["status"]) for c in claims] == [
        ("S-2.1", "coder", "Fix date parsing in csvtidy", "open")]
    assert e.home("csvtidy")["claims"][0]["spec"] == "S-2.1"
    # claiming again from the same chat is the same claim, not a second one
    tool("rung_claim", {"spec": "S-2.1"})
    assert len(e.claims("csvtidy")) == 1


def test_clm02_claim_refusals_name_their_reason(failing, tool):
    e, _ = failing
    tool("rung_claim", {"spec": "S-2.1"})
    other = tool("rung_claim", {"spec": "S-2.1"}, session="sess-2", title="Another chat")
    assert other["code"] == "conflict" and "held by Fix date parsing in csvtidy (coder)" in other["error"]
    e.approve("csvtidy", "R-3", HUMAN)
    e.write_spec("csvtidy", "R-3", seed.S31)
    draft = tool("rung_claim", {"spec": "S-3.1"}, session="sess-3")
    assert draft["code"] == "locked" and "S-3.1 is draft" in draft["error"]
    e.set_allocation("csvtidy", "S-1.1", human_only=True)
    human = tool("rung_claim", {"spec": "S-1.1"}, session="sess-4")
    assert human["code"] == "human_only" and "S-1.1 is human only" in human["error"]
    e.set_allocation("csvtidy", "S-1.1", human_only=False, required_tools=["browser"])
    excluded = tool("rung_claim", {"spec": "S-1.1"}, session="sess-5")
    assert excluded["code"] == "excluded" and "missing tool browser" in excluded["error"]
    assert len(e.claims("csvtidy", open_only=False)) == 1  # nothing stored for the refusals
    assert tool("rung_claim", {}, session="sess-6")["field"] == "spec"
    assert "chat session" in tool("rung_claim", {"spec": "S-1.1"}, session="")["error"]


def test_clm03_report_refused_while_failing(failing, tool):
    e, _ = failing
    tool("rung_claim", {"spec": "S-2.1"})
    out = tool("rung_report", {"spec": "S-2.1"})
    assert out["code"] == "not_released" and "T-2.1a" in out["error"]
    assert e.claims("csvtidy")[0]["status"] == "open"
    no_claim = tool("rung_report", {"spec": "S-2.1"}, session="sess-9")
    assert no_claim["code"] == "no_claim"


def test_clm04_report_closes_claim_with_proof_and_is_not_an_approval(failing, tool):
    e, restore = failing
    tool("rung_claim", {"spec": "S-2.1"})
    before = e.rung("csvtidy", "S-2.1")
    restore()
    run = e.run_test("csvtidy", "T-2.1a", carried_by="coder")
    out = tool("rung_report", {"spec": "S-2.1"})
    assert out["reported"] == "S-2.1" and out["proof"] == [f"T-2.1a #{run['n']}"]
    c = e.claims("csvtidy", open_only=False)[0]
    assert c["status"] == "reported" and c["proof"] == [f"T-2.1a #{run['n']}"] and c["closed_by"] == "coder"
    after = e.rung("csvtidy", "S-2.1")
    assert (after["approved_by"], after["approved_at"], after["version"]) == (
        before["approved_by"], before["approved_at"], before["version"])


def test_clm05_hook_blocks_each_completion_naming_the_rung(failing, tool):
    e, _ = failing
    tool("rung_claim", {"spec": "S-2.1"})
    msg = _decide(e, "rung_report", {"spec": "S-2.1"})
    assert msg and "S-2.1" in msg and "T-2.1a" in msg
    assert "S-2.1" in _decide(e, "kanban_complete", {"summary": "done"})
    todo = {"todos": [{"id": "t9", "content": "Finish S-2.1 date parsing", "status": "completed"}]}
    assert "T-2.1a" in _decide(e, "todo_list", todo)


def test_clm05_hook_entry_point_blocks_through_the_store(failing, tool, monkeypatch):
    e, _ = failing
    tool("rung_claim", {"spec": "S-2.1"})
    monkeypatch.setenv("RUNG_STORE", e.path)
    d = hook.pre_tool_call(tool_name="kanban_complete", args={"summary": "x"}, session_id="sess-1", task_id="t")
    assert d["action"] == "block" and "S-2.1" in d["message"] and "T-2.1a" in d["message"]


def test_clm06_todo_completed_by_id_only_is_blocked(failing, tool):
    e, _ = failing
    tool("rung_claim", {"spec": "S-2.1"})
    create = {"todos": [{"id": "t1", "content": "Finish S-2.1 date parsing", "status": "pending"}]}
    assert _decide(e, "todo_list", create) is None
    by_id = {"todos": [{"id": "t1", "status": "completed"}], "merge": True}
    assert "S-2.1" in _decide(e, "todo_list", by_id)
    # still blocked on a retry: the blocked call did not mark it completed
    assert "S-2.1" in _decide(e, "todo_list", by_id)
    # another session never saw t1 name S-2.1 and holds no claim
    assert _decide(e, "todo_list", by_id, session="sess-other") is None


def test_clm07_calls_go_through_once_the_check_passes(failing, tool):
    e, restore = failing
    tool("rung_claim", {"spec": "S-2.1"})
    _decide(e, "todo_list", {"todos": [{"id": "t1", "content": "Finish S-2.1", "status": "pending"}]})
    restore()
    e.run_test("csvtidy", "T-2.1a", carried_by="coder")
    assert _decide(e, "rung_report", {"spec": "S-2.1"}) is None
    assert _decide(e, "kanban_complete", {}) is None
    assert _decide(e, "todo_list", {"todos": [{"id": "t1", "status": "completed"}], "merge": True}) is None


def test_clm08_unrelated_calls_and_sessions_without_claims_pass(failing, tool):
    e, _ = failing
    tool("rung_claim", {"spec": "S-2.1"})
    assert _decide(e, "todo_list", {"todos": [{"id": "x", "content": "Tidy README", "status": "completed"}]}) is None
    assert _decide(e, "rung_status", {}) is None
    assert _decide(e, "terminal", {"command": "echo S-2.1 done"}) is None
    assert _decide(e, "todo_list", {"todos": [{"id": "t", "content": "S-2.10 done", "status": "completed"}]}) is None
    assert _decide(e, "kanban_complete", {}, session="sess-none") is None
    assert _decide(e, "todo_list", {"todos": [{"id": "y", "content": "Finish S-2.1", "status": "completed"}]},
                   session="sess-none") is None
    assert _decide(e, "kanban_complete", {}, session="") is None


def test_clm09_hook_is_read_only_makes_no_model_call_and_fails_open(failing, tool, monkeypatch, tmp_path):
    e, _ = failing
    tool("rung_claim", {"spec": "S-2.1"})
    rev = e.rev()
    size = Path(e.path).stat().st_size

    def no(*a, **k):
        raise AssertionError("the hook must not start a process or open a connection")

    monkeypatch.setattr(subprocess, "run", no)
    monkeypatch.setattr(subprocess, "Popen", no)
    monkeypatch.setattr(socket, "create_connection", no)
    assert _decide(e, "kanban_complete", {})
    assert e.rev() == rev and Path(e.path).stat().st_size == size
    # a read-only engine cannot write even if asked
    ro = Engine(e.path, readonly=True)
    with pytest.raises(sqlite3.OperationalError):
        ro.conn.execute("UPDATE meta SET value='0' WHERE key='rev'")
    ro.close()
    # an unreadable or missing store lets the call through
    assert hook.decide("kanban_complete", {}, "sess-1", store=tmp_path / "missing.db") is None
    bad = tmp_path / "bad.db"
    bad.write_text("not a database")
    monkeypatch.setenv("RUNG_STORE", str(bad))
    assert hook.pre_tool_call(tool_name="kanban_complete", args={}, session_id="sess-1") is None


def test_clm10_person_releases_a_claim(failing, tool):
    e, _ = failing
    tool("rung_claim", {"spec": "S-2.1"})
    with pytest.raises(RungError):
        e.release_claim("csvtidy", "S-2.1", CODER)
    rows = e.release_claim("csvtidy", "S-2.1", HUMAN)
    assert rows[0]["status"] == "released" and rows[0]["closed_by"] == "you"
    assert _decide(e, "kanban_complete", {}) is None
    with pytest.raises(RungError):
        e.release_claim("csvtidy", "S-2.1", HUMAN)
    # released, so another chat may take it now
    assert tool("rung_claim", {"spec": "S-2.1"}, session="sess-2")["claimed"] == "S-2.1"


def test_clm11_cli_lists_and_releases_claims(failing, tool):
    e, _ = failing
    tool("rung_claim", {"spec": "S-2.1"})
    r = _cli(e.path, "claims")
    assert r.returncode == 0 and "S-2.1" in r.stdout and "coder" in r.stdout
    r = _cli(e.path, "--json", "claims")
    assert json.loads(r.stdout)[0]["spec"] == "S-2.1"
    r = _cli(e.path, "--json", "claims", "release", "S-2.1")
    assert r.returncode == 0 and json.loads(r.stdout)[0]["status"] == "released"
    r = _cli(e.path, "claims")
    assert "no open claims" in r.stdout
    r = _cli(e.path, "--json", "claims", "--all")
    assert [c["status"] for c in json.loads(r.stdout)] == ["released"]
    r = _cli(e.path, "--json", "claims", "release", "S-2.1")
    assert r.returncode == 2 and json.loads(r.stdout)["code"] == "no_claim"


def test_clm12_claims_kept_in_history_and_survive_restart(failing, tool):
    e, _ = failing
    tool("rung_claim", {"spec": "S-2.1"})
    e.release_claim("csvtidy", "S-2.1")
    tool("rung_claim", {"spec": "S-2.1"}, session="sess-2")
    path = e.path
    e2 = Engine(path)
    rows = e2.claims("csvtidy", "S-2.1", open_only=False)
    assert [c["status"] for c in rows] == ["released", "open"]
    kinds = [x["kind"] for x in e2.events("csvtidy") if x["kind"].startswith("claim")]
    assert kinds == ["claim", "claim_released", "claim"]
    from rung_engine import api
    from rung_engine.service import Service
    st, r = api.handle(Service(e2, inline_runs=True), "GET", "/projects/csvtidy/rungs/S-2.1")
    assert st == 200 and [c["status"] for c in r["claims"]] == ["released", "open"]
    e2.close()


# ------------------------------------------------------------------ ALC allocation filters


def test_alc01_profile_tools_prefilled_from_hermes_then_editable(tmp_path):
    e = Engine(tmp_path / "s.db")
    e.tool_source = lambda name: {"coder": ["terminal", "file", "todo"]}.get(name)
    e.sync_profiles(["coder", "writer"])
    assert e.profile("coder")["tools"] == ["terminal", "file", "todo"]
    assert e.profile("writer")["tools"] == []
    e.save_profiles([{**e.profile("coder"), "tools": ["file", "terminal", "file", " "]}])
    assert e.profile("coder")["tools"] == ["file", "terminal"]
    # a save that does not send tools keeps them; the source is read once, when the profile is first listed
    e.tool_source = lambda name: ["web"]
    e.save_profiles([{"name": "coder", "labels": [], "cost": 5, "max_runs": 5, "enabled": True}])
    assert e.profile("coder")["tools"] == ["file", "terminal"]
    e.sync_profiles(["coder"])
    assert e.profile("coder")["tools"] == ["file", "terminal"]
    e.save_profiles([{"name": "newbie"}])
    assert e.profile("newbie")["tools"] == ["web"]
    for bad in ("terminal", [1], ["no spaces"]):
        with pytest.raises(RungError):
            e.save_profiles([{"name": "coder", "tools": bad}])
    e.close()


def test_alc02_missing_tool_excludes(seeded):
    e = seeded
    e.save_profiles([{**e.profile("coder"), "tools": ["terminal"]}, {**e.profile("reviewer"), "tools": ["file"]}])
    e.set_allocation("csvtidy", "S-2.1", required_tools=["terminal"])
    sug = e.suggest("csvtidy", "S-2.1")
    assert [s["profile"] for s in sug["suggestions"]] == ["coder"]
    assert {"profile": "reviewer", "reason": "missing tool terminal"} in sug["excluded"]
    assert sug["required_tools"] == ["terminal"]
    e.set_allocation("csvtidy", "S-2.1", required_tools=[])
    assert e.suggest("csvtidy", "S-2.1")["excluded"] == []


def test_alc03_at_once_is_a_hard_concurrency_filter(seeded, svc, tmp_path):
    e = seeded
    e.save_profiles([{**e.profile("writer"), "at_once": 1}])
    assert e.profile("writer")["at_once"] == 1 and e.profile("coder")["at_once"] == 2
    for bad in (0, 11, "2", True):
        with pytest.raises(RungError):
            e.save_profiles([{**e.profile("writer"), "at_once": bad}])
    e.claim("csvtidy", "S-1.1", "sess-w", "Docs chat", "writer")
    sug = e.suggest("csvtidy", "S-2.1")
    assert {"profile": "writer", "reason": "at capacity 1 of 1"} in sug["excluded"]
    assert "writer" not in [s["profile"] for s in sug["suggestions"]]
    e.release_claim("csvtidy", "S-1.1")
    assert "writer" in [s["profile"] for s in e.suggest("csvtidy", "S-2.1")["suggestions"]]
    # develop runs count too: two queued runs fill coder's default limit of 2
    seed.seed_built(e2 := Engine(tmp_path / "b" / "s.db"), seed.copy_fixture("csvtidy", tmp_path / "b"))
    e2.start_run("csvtidy", "S-1.1", profile="coder")
    e2.start_run("csvtidy", "S-2.1", profile="coder")
    sug = e2.suggest("csvtidy", "S-3.1")
    assert {"profile": "coder", "reason": "at capacity 2 of 2"} in sug["excluded"]
    with pytest.raises(RungError, match="at capacity 2 of 2"):
        e2.start_run("csvtidy", "S-3.1", profile="coder")
    e2.close()


def test_alc04_independent_carrier_excludes_authors(seeded):
    e = seeded
    e.propose("csvtidy", "S-2.1", "test", "pytest tests/test_dates.py", "reviewer")
    e.set_allocation("csvtidy", "S-2.1", independent=True)
    sug = e.suggest("csvtidy", "S-2.1")
    assert {"profile": "reviewer", "reason": "author of S-2.1"} in sug["excluded"]
    assert "coder" in [s["profile"] for s in sug["suggestions"]]
    # the drafting profile of an AI-derived specification is an author too
    e.approve("csvtidy", "R-3", HUMAN)
    e.set_authoring("csvtidy", "R-3", "ai")
    e.finish_draft("csvtidy", "S-3.1", seed.S31, drafted_by="coder")
    e.set_allocation("csvtidy", "S-3.1", independent=True)
    assert {"profile": "coder", "reason": "author of S-3.1"} in e.suggest("csvtidy", "S-3.1")["excluded"]
    e.set_allocation("csvtidy", "S-3.1", independent=False)
    assert all(x["profile"] != "coder" for x in e.suggest("csvtidy", "S-3.1")["excluded"])


def test_alc05_human_only_offers_no_profile(seeded):
    e = seeded
    e.set_allocation("csvtidy", "S-1.1", human_only=True)
    sug = e.suggest("csvtidy", "S-1.1")
    assert sug["human_only"] and sug["human_only_reason"] == "marked" and sug["suggestions"] == []
    assert sorted(x["profile"] for x in sug["excluded"]) == ["coder", "researcher", "reviewer", "writer"]
    assert all(x["reason"] == "human only" for x in sug["excluded"])
    with pytest.raises(RungError, match="human only"):
        e.pick("csvtidy", "S-1.1", "coder")
    e.set_allocation("csvtidy", "S-1.1", human_only=False)
    assert e.suggest("csvtidy", "S-1.1")["suggestions"]
    # every test manual: human only without a mark
    t = e.rung("csvtidy", "T-1.1a")
    e.edit_test("csvtidy", "T-1.1a", {"type": "manual", "text": "Look at it", "steps": ["Open the file"]})
    sug = e.suggest("csvtidy", "S-1.1")
    assert sug["human_only"] and sug["human_only_reason"] == "all tests manual"
    assert t["id"] == "T-1.1a"


def test_alc06_develop_lists_every_exclusion_with_reason(seeded, svc):
    from rung_engine import api
    e = seeded
    e.save_profiles([{**e.profile("researcher"), "enabled": False}, {**e.profile("coder"), "tools": ["terminal"]}])
    e.set_allocation("csvtidy", "S-2.1", required_tools=["terminal"])
    st, r = api.handle(svc, "GET", "/projects/csvtidy/rungs/S-2.1")
    ex = {x["profile"]: x["reason"] for x in r["allocation"]["excluded"]}
    assert ex == {"researcher": "disabled; missing tool terminal", "reviewer": "missing tool terminal",
                  "writer": "missing tool terminal"}
    assert [s["profile"] for s in r["allocation"]["suggestions"]] == ["coder"]


def test_alc07_settings_shows_exclusions_per_profile(seeded, svc):
    from rung_engine import api
    e = seeded
    e.set_allocation("csvtidy", "S-1.1", human_only=True)
    e.save_profiles([{**e.profile("writer"), "enabled": False}])
    st, r = api.handle(svc, "GET", "/projects/csvtidy/exclusions")
    assert st == 200
    assert r["profiles"]["coder"] == [{"spec": "S-1.1", "text": seed.S11, "reason": "human only"}]
    assert [x["spec"] for x in r["profiles"]["writer"]] == ["S-1.1", "S-2.1"]
    assert r["profiles"]["writer"][1]["reason"] == "disabled"


def test_alc08_every_door_refuses_an_excluded_profile_with_the_same_reason(seeded, svc, tool):
    from rung_engine import api
    e = seeded
    e.set_allocation("csvtidy", "S-2.1", required_tools=["terminal"])
    reason = "missing tool terminal"
    st, r = api.handle(svc, "POST", "/projects/csvtidy/specs/S-2.1/pick", {"agent": "coder"})
    assert st == 409 and reason in r["detail"] and r["code"] == "excluded"
    st, r = api.handle(svc, "POST", "/projects/csvtidy/specs/S-2.1/send", {"agent": "coder"})
    assert st == 409 and reason in r["detail"]
    r = _cli(e.path, "send", "S-2.1", "--profile", "coder")
    assert r.returncode == 2 and reason in r.stderr
    out = tool("rung_claim", {"spec": "S-2.1"})
    assert out["code"] == "excluded" and reason in out["error"]
    st, r = api.handle(svc, "POST", "/projects/csvtidy/specs/S-2.1/pick", {"agent": "nobody"})
    assert st == 409 and "not a profile of csvtidy" in r["detail"]
    st, r = api.handle(svc, "POST", "/projects/csvtidy/specs/S-2.1/allocation", {"human_only": "yes"})
    assert st == 400 and r["field"] == "human_only"
    st, r = api.handle(svc, "POST", "/projects/csvtidy/specs/S-2.1/allocation", {"approve": True})
    assert st == 400 and "unknown field" in r["detail"]


def test_alc09_filters_and_ranking_are_deterministic(seeded, monkeypatch):
    e = seeded
    e.set_allocation("csvtidy", "S-2.1", required_tools=["terminal"], independent=True)

    def no(*a, **k):
        raise AssertionError("no process or network for allocation")

    monkeypatch.setattr(subprocess, "run", no)
    monkeypatch.setattr(socket, "create_connection", no)
    first = e.suggest("csvtidy", "S-2.1")
    for _ in range(5):
        assert e.suggest("csvtidy", "S-2.1") == first
    p = allocation.ProfileFacts("a", (), 0, False, tools=(), at_once=1, running=1, claims=1)
    n = allocation.Needs(spec="S-9.9", required_tags=("x",), required_tools=("t",), independent=True,
                         authors=frozenset({"a"}), human_only=True)
    assert allocation.reasons(p, n) == ["disabled", "human only", "missing tag x", "missing tool t",
                                        "author of S-9.9", "at capacity 2 of 1"]


def test_alc10_goal2_store_migrates(tmp_path):
    path = tmp_path / "old.db"
    Engine(path).close()
    # make it the store stage 2 wrote: profiles without tools and at_once, no claims, schema 2
    conn = sqlite3.connect(path)
    conn.execute("DROP TABLE profiles")
    conn.execute("CREATE TABLE profiles (name TEXT PRIMARY KEY, labels TEXT NOT NULL DEFAULT '[]', cost INTEGER "
                 "NOT NULL DEFAULT 5, max_runs INTEGER NOT NULL DEFAULT 5, enabled INTEGER NOT NULL DEFAULT 1)")
    conn.execute("INSERT INTO profiles(name, labels) VALUES ('coder', '[\"python\"]')")
    conn.execute("DROP TABLE claims")
    conn.execute("UPDATE meta SET value='2' WHERE key='schema_version'")
    conn.commit()
    conn.close()
    e = Engine(path)
    assert db.schema_version(e.conn) == 3
    assert e.profile("coder") == {"name": "coder", "labels": ["python"], "cost": 5, "max_runs": 5, "enabled": True,
                                  "tools": [], "at_once": 2}
    assert e.claims() == []
    e.close()


def test_alc10_specifications_of_a_goal2_store_require_nothing(seeded):
    sug = seeded.suggest("csvtidy", "S-2.1")
    assert sug["required_tools"] == [] and sug["independent"] is False and sug["marked_human_only"] is False
    assert sug["excluded"] == []


def test_clm01_a_profile_without_a_store_claims_in_its_root_ladder(tmp_path, monkeypatch):
    from rung_engine import host
    root = tmp_path / "home"
    coder_home = root / "profiles" / "coder"
    (root / "plugin-data" / "rung").mkdir(parents=True)
    coder_home.mkdir(parents=True)
    shared = tmp_path / "elsewhere" / "rung.db"
    (root / "plugin-data" / "rung" / "store").write_text(str(shared) + "\n")
    monkeypatch.delenv("RUNG_STORE", raising=False)
    monkeypatch.setenv("HERMES_HOME", str(coder_home))
    monkeypatch.setattr(host, "hermes_home", lambda: coder_home)
    monkeypatch.setattr(host, "_default_store", lambda: coder_home / "plugin-data" / "rung" / "rung.db")
    assert host.store_path() == shared
    # the root without a pointer: its own store, when there is one
    (root / "plugin-data" / "rung" / "store").unlink()
    assert host.store_path() == coder_home / "plugin-data" / "rung" / "rung.db"
    (root / "plugin-data" / "rung" / "rung.db").write_bytes(b"")
    assert host.store_path() == root / "plugin-data" / "rung" / "rung.db"
    # a profile with its own store keeps it
    own = coder_home / "plugin-data" / "rung"
    own.mkdir(parents=True)
    (own / "rung.db").write_bytes(b"")
    assert host.store_path() == own / "rung.db"
    # the root home itself is never redirected
    monkeypatch.setattr(host, "hermes_home", lambda: root)
    monkeypatch.setattr(host, "_default_store", lambda: root / "plugin-data" / "rung" / "rung.db")
    assert host.store_path() == root / "plugin-data" / "rung" / "rung.db"


def test_pne02_fresh_draft_of_an_approved_ai_spec_is_a_new_version(engine, csv_folder):
    from rung_engine.service import Service
    seed.seed_csvtidy(engine, csv_folder, with_history=False)
    e = engine
    e.set_setting("drafting", {"kind": "stub", "delay": 0.0, "profile": "coder"})
    svc = Service(e, inline_runs=True)
    # A person-written approved specification is edited, never redrafted.
    with pytest.raises(RungError, match="written by you"):
        e.mark_drafting("csvtidy", "S-2.1")
    # R-2 switched to AI derives: S-2.1 can be redrafted.
    e.approve_requirements("csvtidy", "N-1")
    svc.set_authoring("csvtidy", "R-2", "ai", wait=True)
    before = e.rung("csvtidy", "S-2.1")
    assert before["status"] == "approved"
    marked = svc.regenerate("csvtidy", "S-2.1")
    assert marked["draft_state"] == "drafting" and marked["status"] == "draft"
    assert marked["version"] == before["version"] + 1
    svc.wait_idle()
    after = e.rung("csvtidy", "S-2.1")
    assert after["draft_state"] == "drafted" and after["drafted_by"] == "coder" and after["status"] == "draft"
    hist = e.history("csvtidy", "S-2.1")
    assert [v["version"] for v in hist][-2:] == [before["version"], before["version"] + 1]
    assert hist[-2]["text"] == before["text"]
    if after["text"] != before["text"]:
        # approved text changed: the change is recorded and earlier results of its tests stop counting
        ch = e.changes("csvtidy", "S-2.1")[0]
        assert ch["before"] == before["text"] and ch["after"] == after["text"]
        assert e.rung("csvtidy", "T-2.1a")["invalidated_by"] == "S-2.1 redrafted"
    # Approving the fresh draft makes the coder its author (independence, ALC-04).
    e.approve("csvtidy", "S-2.1")
    sug = e.suggest("csvtidy", "S-2.1")
    e.set_allocation("csvtidy", "S-2.1", independent=True)
    sug = e.suggest("csvtidy", "S-2.1")
    assert {"profile": "coder", "reason": "author of S-2.1"} in [{"profile": x["profile"], "reason": x["reason"]} for x in sug["excluded"]]
    # Still drafting cannot be asked twice.
    e.mark_drafting("csvtidy", "S-2.1")
    with pytest.raises(RungError, match="still drafting"):
        e.mark_drafting("csvtidy", "S-2.1")
