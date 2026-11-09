import json
import os
import subprocess
import sys
from pathlib import Path

from rung_engine import api
from rung_engine.service import Service
from support import seed

ROOT = Path(__file__).resolve().parent.parent


def call(svc, method, path, body=None):
    return api.handle(svc, method, path, body)


def test_state_and_create_project(engine, tmp_path):
    svc = Service(engine, inline_runs=True)
    engine.sync_profiles(["coder"])  # what the host does with the Hermes profiles before serving
    st, body = call(svc, "GET", "/state")
    assert st == 200 and body["projects"] == [] and body["current"] is None
    st, body = call(svc, "POST", "/projects", {"name": "csvtidy", "folder": str(tmp_path), "test_command": "pytest",
                                                "profiles": ["coder"]})
    assert st == 200 and body["name"] == "csvtidy"
    st, body = call(svc, "POST", "/projects", {"name": "", "folder": str(tmp_path / "missing"),
                                                "test_command": "pytest", "profiles": ["coder"]})
    assert st == 400 and body["field"] == "folder"
    st, body = call(svc, "GET", "/nope")
    assert st == 404


def test_locked_steps_refused_through_api(seeded):
    svc = Service(seeded, inline_runs=True)
    st, need = call(svc, "POST", "/projects/csvtidy/needs", {"text": "Merge two CSV exports by a shared key",
                                                            "requirements": ["Match rows by a chosen key column"]})
    assert st == 200
    st, body = call(svc, "POST", f"/projects/csvtidy/rungs/R-4/authoring", {"mode": "ai"})
    assert st == 409 and body["code"] == "locked"
    st, body = call(svc, "POST", f"/projects/csvtidy/needs/{need['id']}/approve-tests")
    assert st == 409
    st, body = call(svc, "POST", "/projects/csvtidy/specs/S-1.1/send", {})
    assert st == 200 and body["status"] == "queued"
    svc.wait_idle()


def test_home_and_rung_views(seeded):
    svc = Service(seeded, inline_runs=True)
    st, home = call(svc, "GET", "/projects/csvtidy/home")
    assert st == 200
    assert home["tiles"]["needs_you"] == len(home["needs_you"])
    assert home["allocation"] is None  # every specification is released: nothing to allocate (home-notes.html)
    st, focused = call(svc, "GET", "/projects/csvtidy/home", {"focus": "T-2.1a"})
    assert st == 200 and focused["allocation"]["spec"] == "S-2.1"
    st, s = call(svc, "GET", "/projects/csvtidy/rungs/S-2.1")
    assert st == 200 and s["kind"] == "specification" and s["path"][0]["id"] == "N-1"
    assert [c["id"] for c in s["children"]] == ["T-2.1a", "T-2.1b"]
    st, t = call(svc, "GET", "/projects/csvtidy/rungs/T-2.1a")
    assert len(t["executions"]) == 3
    st, x = call(svc, "GET", "/projects/csvtidy/tests/T-2.1a/executions/1")
    assert x["exit_code"] == 1 and x["spec"] == "S-2.1"


def _cli(store, *args):
    env = dict(os.environ, RUNG_STORE=str(store))
    return subprocess.run([sys.executable, "-m", "rung_engine.cli", *args], cwd=ROOT, env=env, capture_output=True,
                          text=True)


def test_cli_check_is_a_gate(seeded):
    store = seeded.path
    r = _cli(store, "check", "S-2.1")
    assert r.returncode == 0, r.stdout + r.stderr
    seeded.edit("csvtidy", "R-2", text="Normalise every date to ISO 8601, keeping the time", approve=True)
    r = _cli(store, "check", "S-2.1")
    assert r.returncode == 1 and "S-2.1 is stale" in r.stdout
    r = _cli(store, "check", "--all")
    assert r.returncode == 1
    seeded.approve("csvtidy", "S-2.1")
    r = _cli(store, "check", "S-2.1")
    assert r.returncode == 1 and "T-2.1a" in r.stdout
    seeded.run_test("csvtidy", "T-2.1a")
    assert _cli(store, "check", "S-2.1").returncode == 0
    assert _cli(store, "check", "--all").returncode == 0
    r = _cli(store, "--json", "status")
    assert json.loads(r.stdout)["tiles"]["needs_you"] == 0


def test_cli_verify_and_recheck(seeded):
    store = seeded.path
    folder = Path(seeded.project("csvtidy")["folder"])
    assert _cli(store, "check", "S-2.1").returncode == 0
    restore = seed.break_dates(folder)
    r = _cli(store, "verify", "S-2.1")
    assert r.returncode == 1 and "out_of_date" in r.stdout and "next: run_tests T-2.1a" in r.stdout, r.stdout
    r = _cli(store, "--json", "verify", "S-2.1")
    assert json.loads(r.stdout)["verification"] == "out_of_date"
    r = _cli(store, "recheck")
    assert r.returncode == 1 and "T-2.1a" in r.stdout and "fail" in r.stdout, r.stdout
    restore()
    r = _cli(store, "recheck")
    assert r.returncode == 0 and "T-2.1a" in r.stdout and "pass" in r.stdout, r.stdout
    assert _cli(store, "verify", "S-2.1").returncode == 0
    assert "nothing out of date" in _cli(store, "recheck").stdout


def test_tools_propose_and_refuse_approval(seeded, monkeypatch):
    monkeypatch.setenv("RUNG_STORE", seeded.path)
    from rung_engine import host, tools
    host._SERVICES.clear()
    out = json.loads(tools.HANDLERS["rung_propose"]({"parent": "N-1", "text": "Accept two-digit years with --century"},
                                                     session_id="", user_task="Fix date parsing in csvtidy"))
    assert out["proposed"] == "R-4"
    item = [i for i in seeded.needs_you("csvtidy") if i["type"] == "proposed"][0]
    assert item["source_chat"] == "Fix date parsing in csvtidy"
    chk = json.loads(tools.HANDLERS["rung_check"]({"spec": "S-2.1"}))
    assert chk["ok"] is True
    assert "1 needs you" in tools.slash("")
    host._SERVICES.clear()
