"""Use cases without their own view: reverting a change, a fresh draft, the command boundary, the CLI and agent
tools matching what the pane reads."""

import json
import os
import subprocess
import sys

import pytest

from rung_engine import HUMAN, Actor, RungError, api
from rung_engine.service import Service
from support import seed

from test_api_cli import ROOT, call

AGENT = Actor("agent", "coder")


def _cli(store, *args):
    env = dict(os.environ, RUNG_STORE=str(store))
    return subprocess.run([sys.executable, "-m", "rung_engine.cli", "--project", "csvtidy", *args], cwd=ROOT, env=env,
                          capture_output=True, text=True, timeout=120)


def test_req06_revert_a_change_and_recompute_stale(seeded):
    e = seeded
    before = e.rung("csvtidy", "R-2")["text"]
    e.edit("csvtidy", "R-2", text="Normalise every date to ISO 8601 with a time zone", approve=True)
    assert e.rung("csvtidy", "S-2.1")["status"] == "stale"
    change = e.change_for("csvtidy", "R-2")
    e.approve("csvtidy", "S-2.1")
    assert e.rung("csvtidy", "S-2.1")["status"] == "approved"
    e.revert_change("csvtidy", change["id"])
    assert e.rung("csvtidy", "R-2")["text"] == before
    # The revert is a change of its own: what it makes stale is worked out again from the ladder as it is now.
    latest = e.change_for("csvtidy", "R-2")
    assert latest is not None and latest["id"] != change["id"] and latest["after"] == before
    assert "S-2.1" in latest["stale"] and e.rung("csvtidy", "S-2.1")["status"] == "stale"
    with pytest.raises(RungError):
        e.revert_change("csvtidy", change["id"], AGENT)


def test_spc05_fresh_draft_of_an_ai_derived_specification(engine, csv_folder):
    seed.seed_csvtidy(engine, csv_folder, with_history=False)
    e = engine
    need = e.create_need("csvtidy", "Merge two CSV exports by a shared key")["id"]
    req = e.add_requirement("csvtidy", need, "Match rows by a chosen key column")["id"]
    e.approve_requirements("csvtidy", need)
    svc = Service(e, inline_runs=True)
    spec = svc.set_authoring("csvtidy", req, "ai", wait=True)["id"]
    assert e.rung("csvtidy", spec)["draft_state"] == "drafted"
    marked = svc.regenerate("csvtidy", spec)
    # Asked again: drafting, so the step cannot be approved until the fresh draft lands on the same specification.
    assert marked["id"] == spec and marked["draft_state"] == "drafting"
    svc.wait_idle()
    again = e.rung("csvtidy", spec)
    assert again["draft_state"] == "drafted" and again["author_role"] == "agent" and again["text"]
    assert e.flow("csvtidy", need)["steps"]["specifications"]["can_approve"]


def test_sec01_only_human_approved_commands_run(seeded):
    e = seeded
    # An agent cannot change a test; it can only propose.
    with pytest.raises(RungError):
        e.edit_test("csvtidy", "T-1.1a", {"command": "rm -rf ."}, AGENT)
    # A changed command goes back to draft: develop and the agent tool skip it until a person approves it again.
    e.edit_test("csvtidy", "T-1.1a", {"command": "pytest tests/test_sniff.py -q"})
    assert e.rung("csvtidy", "T-1.1a")["status"] == "draft"
    assert "T-1.1a" not in [t["id"] for t in e.command_tests("csvtidy", "S-1.1")]
    assert not e.check("csvtidy", "S-1.1")["ok"]
    with pytest.raises(RungError):
        e.approve("csvtidy", "T-1.1a", AGENT)
    e.approve("csvtidy", "T-1.1a", HUMAN)
    assert "T-1.1a" in [t["id"] for t in e.command_tests("csvtidy", "S-1.1")]


@pytest.mark.parametrize("folder", ["../..", "..", "/etc", "~", "tests/../../.."])
def test_sec02_test_folder_stays_inside_the_project(seeded, folder):
    with pytest.raises(RungError) as err:
        seeded.add_test("csvtidy", "S-1.1", {"type": "command", "command": "pwd", "folder": folder})
    assert err.value.field == "folder"


def test_sec02_api_paths_cannot_leave_the_store(seeded, tmp_path):
    svc = Service(seeded, inline_runs=True)
    for method, path in [("GET", "/projects/..%2F..%2Fetc/home"), ("GET", "/projects/../../etc/passwd"),
                         ("GET", "/projects/csvtidy/rungs/..%2F..%2Fx"), ("POST", "/projects/../evil/archive")]:
        status, _ = call(svc, method, path, {})
        assert status == 404, (method, path)
    with pytest.raises(RungError):
        seeded.create_project("../evil", str(tmp_path), "true", ["coder"])
    # A symlink that leads out of the project is refused when the command would run.
    t = seeded.add_test("csvtidy", "S-1.1", {"type": "command", "command": "pwd", "folder": "out"}, status="approved")
    project = seeded.project("csvtidy")["folder"]
    os.symlink(str(tmp_path), os.path.join(project, "out"))
    ex = seeded.run_test("csvtidy", t["id"])
    assert ex["status"] == "error" and "outside the project folder" in ex["output"]


def test_gte05_cli_matches_what_the_pane_reads(seeded):
    store = seeded.path
    svc = Service(seeded, inline_runs=True)
    _, home = call(svc, "GET", "/projects/csvtidy/home")
    status = json.loads(_cli(store, "--json", "status").stdout)
    assert status["tiles"] == home["tiles"]
    assert [i["id"] for i in status["needs_you"]] == [i["id"] for i in home["needs_you"]]
    tree = _cli(store, "tree").stdout
    for n in home["tree"]:
        assert n["id"] in tree
    projects = _cli(store, "projects").stdout
    assert "csvtidy" in projects and "notes-sync" in projects
    assert _cli(store, "where").stdout.strip() == str(store)
    before = len(seeded.executions("csvtidy", "T-1.1a"))
    r = _cli(store, "run", "S-1.1")
    assert r.returncode == 0, r.stdout + r.stderr
    assert len(seeded.executions("csvtidy", "T-1.1a")) == before + 1
    r = _cli(store, "send", "S-2.1", "--profile", "coder")
    assert r.returncode == 0, r.stdout + r.stderr
    run = seeded.runs("csvtidy", "S-2.1")[0]
    assert r.stdout.strip() == f"run {run['id']} started for S-2.1 with coder"
    _, shown = call(svc, "GET", f"/runs/{run['id']}")
    assert shown["id"] == run["id"] and shown["profile"] == "coder"
    seeded.cancel_run(run["id"])

def test_gte06_agent_reads_runs_and_checks_through_the_tools(seeded, monkeypatch):
    monkeypatch.setenv("RUNG_STORE", seeded.path)
    from rung_engine import host, tools
    host._SERVICES.clear()
    try:
        st = json.loads(tools.HANDLERS["rung_status"]({}))
        assert st["project"] == "csvtidy" and st["tiles"] == seeded.tiles("csvtidy")
        before = len(seeded.executions("csvtidy", "T-1.1a"))
        run = json.loads(tools.HANDLERS["rung_run_tests"]({"spec": "S-1.1"}))
        assert run["executions"][0]["test"] == "T-1.1a" and run["executions"][0]["status"] == "pass"
        assert len(seeded.executions("csvtidy", "T-1.1a")) == before + 1
        chk = json.loads(tools.HANDLERS["rung_check"]({"spec": "S-1.1"}))
        assert chk["ok"] is True
        refused = json.loads(tools.HANDLERS["rung_check"]({}))
        assert "error" in refused
    finally:
        host._SERVICES.clear()

