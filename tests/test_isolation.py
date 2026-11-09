"""Isolated runs (SYS-05, B12; decisions Round 24): a run works in its own copy; its passes are local; integration
applies its changes unless a file changed in the project since, then checks the affected work on the project."""

import json

import pytest

from rung_engine import Actor, RungError
from rung_engine.runner import run_loop
from rung_engine.workers import StubWorker
from support import seed

AGENT = Actor("agent", "coder")


@pytest.fixture
def pair(engine, tmp_path):
    folder = tmp_path / "linkpair"
    folder.mkdir()
    seed.seed_linkpair(engine, folder)
    engine.open_project("linkpair")
    return engine, folder


def _run(e, tmp_path, spec, files, tag):
    stub = tmp_path / f"stub-{tag}"
    att = stub / spec / "attempt-1"
    for rel, text in files.items():
        (att / rel).parent.mkdir(parents=True, exist_ok=True)
        (att / rel).write_text(text)
    run = e.start_run("linkpair", spec, profile="coder")
    return run_loop(e, run["id"], worker=StubWorker(str(stub), delay=0))


def test_sys05_isolated_runs_are_local_until_integrated(pair, tmp_path):
    e, folder = pair
    with pytest.raises(RungError):
        e.set_run_mode("linkpair", "isolated", actor=AGENT)
    e.set_run_mode("linkpair", "isolated")
    api = (folder / "shortly" / "api.py").read_text()
    # 1. Own workspace; the project folder is unchanged; its passes are local.
    r1 = _run(e, tmp_path, "S-1.1", {"shortly/api.py": api + "\n# one\n"}, "a")
    assert r1["status"] == "passed" and "locally" in r1["reason"], r1["reason"]
    assert (folder / "shortly" / "api.py").read_text() == api
    assert e.executions("linkpair", "T-1.1a") == []
    assert r1["attempts"][0]["local"][0]["status"] == "pass"
    assert r1["workspace"]["changed"] == ["shortly/api.py"] and r1["workspace"]["path"] != str(folder)
    assert not e.check("linkpair", "S-1.1")["ok"]  # nothing ran on the project
    # 2. A second run changes the same file: the first integrates, the second is refused naming the file.
    r2 = _run(e, tmp_path, "S-2.1", {"shortly/api.py": api + "\n# two\n"}, "b")
    assert r2["status"] == "passed"
    with pytest.raises(RungError):
        e.integrate_run("linkpair", r1["id"], actor=AGENT)
    out = e.integrate_run("linkpair", r1["id"])
    assert out["applied"] == ["shortly/api.py"] and (folder / "shortly" / "api.py").read_text().endswith("# one\n")
    assert {"test": "T-1.1a", "status": "pass"} in out["checked"] and e.check("linkpair", "S-1.1")["ok"]
    with pytest.raises(RungError) as x:
        e.integrate_run("linkpair", r2["id"])
    assert x.value.code == "conflict" and "shortly/api.py" in str(x.value) and "nothing was applied" in str(x.value)
    assert (folder / "shortly" / "api.py").read_text().endswith("# one\n")
    with pytest.raises(RungError):
        e.integrate_run("linkpair", r1["id"])  # once


def test_sys05_two_local_greens_break_the_journey_together(pair, tmp_path):
    e, folder = pair
    seed.fix_linkpair(folder)
    e.accept_test_files("linkpair", "T-2.1a")
    m = e.create_milestone("linkpair", "Share a short link", "Create a link and see it", ["S-1.1", "S-2.1"])
    e.add_milestone_check("linkpair", m["id"], {"type": "command", "command": "pytest -q journey/test_journey.py"})
    e.approve_milestone("linkpair", m["id"])
    e.set_run_mode("linkpair", "isolated")
    api = (folder / "shortly" / "api.py").read_text()
    page = (folder / "shortly" / "page.py").read_text()
    strict = api.replace("    def do_POST(self):\n",
                         "    def do_POST(self):\n        if self.path != \"/links\":\n            self.send_error(404)\n"
                         "            return\n")
    moved = page.replace('base + "/links"', 'base + "/v2/links"')
    ra = _run(e, tmp_path, "S-1.1", {"shortly/api.py": strict}, "a")
    rb = _run(e, tmp_path, "S-2.1", {"shortly/page.py": moved}, "b")
    assert ra["status"] == rb["status"] == "passed"
    a = e.integrate_run("linkpair", ra["id"])
    b = e.integrate_run("linkpair", rb["id"])
    assert a["verification"] == "verified" and b["verification"] == "verified"  # each piece still green
    [res] = e.run_milestone("linkpair", m["id"])
    assert res["status"] == "fail" and e.milestone("linkpair", m["id"])["state"] == "integration_failed"


def test_sys05_shared_mode_is_unchanged(pair, tmp_path):
    e, folder = pair
    api = (folder / "shortly" / "api.py").read_text()
    r = _run(e, tmp_path, "S-1.1", {"shortly/api.py": api + "\n# shared\n"}, "s")
    assert r["status"] == "passed" and r["workspace"] is None
    assert (folder / "shortly" / "api.py").read_text().endswith("# shared\n")
    with pytest.raises(RungError):
        e.integrate_run("linkpair", r["id"])
    assert json.loads(json.dumps(e.run(r["id"])))  # serialisable
