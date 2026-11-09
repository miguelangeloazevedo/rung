"""Integration milestones (decisions Round 23): the pieces passed, the application does not work together.

The fixture's API answers {"short_url": ...} and its page reads "url". Each piece passes its own tests; only the
milestone's check across the real HTTP boundary fails. The sequence follows the M0 acceptance steps.
"""

import pytest

from rung_engine import Actor, RungError
from support import seed

AGENT = Actor("agent", "coder")


@pytest.fixture
def pair(engine, tmp_path):
    folder = tmp_path / "linkpair"
    folder.mkdir()
    seed.seed_linkpair(engine, folder)
    engine.open_project("linkpair")
    return engine, folder


def _milestone(e):
    m = e.create_milestone("linkpair", "Share a short link", "Paste a long link, get a short one, see it on the page",
                           ["S-1.1", "S-2.1"], architecture="docs/architecture.md (API returns JSON, page fetches it)")
    e.add_milestone_check("linkpair", m["id"], {"type": "command", "command": "pytest -q journey/test_journey.py",
                                                "text": "Create a link through the API and see it on the page"})
    return m["id"]


def test_local_green_system_red_then_repaired_then_out_of_date(pair):
    e, folder = pair
    # 1. Real local passes for both pieces.
    assert e.run_test("linkpair", "T-1.1a")["status"] == "pass"
    assert e.run_test("linkpair", "T-2.1a")["status"] == "pass"
    assert e.check("linkpair", "S-1.1")["ok"] and e.check("linkpair", "S-2.1")["ok"]
    # 2. The milestone is not verified: a draft first, then ready with its check never run.
    mid = _milestone(e)
    assert e.milestone("linkpair", mid)["state"] == "draft"
    e.approve_milestone("linkpair", mid)
    v = e.milestone("linkpair", mid)
    assert v["state"] == "ready" and not v["ok"] and v["next_action"]["kind"] == "run_checks"
    # 3-4. The journey across the boundary fails; both specifications stay green, the milestone does not.
    [r] = e.run_milestone("linkpair", mid)
    assert r["status"] == "fail"
    assert "KeyError: 'url'" in e.milestone_runs("linkpair", mid, f"{mid}.a")[0]["output"]  # the mismatch itself
    v = e.milestone("linkpair", mid)
    assert v["state"] == "integration_failed" and [b["code"] for b in v["blockers"]] == ["failed"]
    assert v["next_action"] == {"kind": "repair", "check": f"{mid}.a"}
    assert all(s["ok"] for s in v["scope"])
    # 5. Repair the mismatch. The page's own test changed, so its old pass no longer applies and its files need
    # a person; the milestone is Not ready until the piece is verified again.
    seed.fix_linkpair(folder)
    v = e.milestone("linkpair", mid)
    assert v["state"] == "not_ready" and {b["rung"] for b in v["blockers"]} == {"S-1.1", "S-2.1"}
    assert e.run_test("linkpair", "T-2.1a")["status"] == "error"  # its approved test file changed
    e.accept_test_files("linkpair", "T-2.1a")
    assert e.run_test("linkpair", "T-2.1a")["status"] == "pass"
    assert e.run_test("linkpair", "T-1.1a")["status"] == "pass"
    assert e.milestone("linkpair", mid)["state"] == "out_of_date"  # the failed run was on other code
    # 6. A genuine integration pass.
    [r] = e.run_milestone("linkpair", mid)
    assert r["status"] == "pass"
    v = e.milestone("linkpair", mid)
    assert v["state"] == "verified" and v["ok"] and v["blockers"] == []
    # 7. Change an included artifact: out of date, history kept.
    api = folder / "shortly" / "api.py"
    api.write_text(api.read_text().replace('"/r/" + code', '"/s/" + code'))
    v = e.milestone("linkpair", mid)
    assert v["state"] == "not_ready"
    assert [x["status"] for x in e.milestone_runs("linkpair", mid, f"{mid}.a")] == ["pass", "fail"]
    # 8. The report names scope, basis and the actual evidence.
    md = e.milestone_markdown("linkpair", mid)
    assert "State: Not ready for integration" in md and "Code basis: " in md and "S-1.1" in md
    assert "pytest -q journey/test_journey.py (#2 out of date" in md


def test_a_changed_contract_invalidates_and_needs_approval_again(pair):
    e, _ = pair
    e.run_test("linkpair", "T-1.1a")
    e.run_test("linkpair", "T-2.1a")
    mid = _milestone(e)
    e.approve_milestone("linkpair", mid)
    seed.fix_linkpair(pair[1])
    e.accept_test_files("linkpair", "T-2.1a")
    e.run_test("linkpair", "T-1.1a")
    e.run_test("linkpair", "T-2.1a")
    e.run_milestone("linkpair", mid)
    assert e.milestone("linkpair", mid)["state"] == "verified"
    e.edit_milestone("linkpair", mid, {"journey": "Paste a long link and open the short one"})
    v = e.milestone("linkpair", mid)
    assert v["state"] == "draft" and v["version"] == 3  # created 1, its check 2, the new journey 3
    e.approve_milestone("linkpair", mid)
    v = e.milestone("linkpair", mid)
    assert v["state"] == "ready" and v["checks"][0]["state"] == "missing"  # a run on version 1 does not count


def test_required_manual_acceptance_and_its_limits(pair):
    e, folder = pair
    seed.fix_linkpair(folder)
    e.accept_test_files("linkpair", "T-2.1a")
    e.run_test("linkpair", "T-1.1a")
    e.run_test("linkpair", "T-2.1a")
    mid = _milestone(e)
    e.add_milestone_check("linkpair", mid, {"type": "manual", "steps": ["Open the page", "Paste a link",
                                                                         "Open the short link"]})
    e.approve_milestone("linkpair", mid)
    e.run_milestone("linkpair", mid)
    v = e.milestone("linkpair", mid)
    assert v["state"] == "awaiting_manual" and v["next_action"] == {"kind": "record_manual_result", "check": f"{mid}.b"}
    with pytest.raises(RungError):
        e.record_milestone_manual("linkpair", mid, f"{mid}.b", "pass", actor=AGENT)
    e.record_milestone_manual("linkpair", mid, f"{mid}.b", "pass", "opened the bakery page")
    assert e.milestone("linkpair", mid)["state"] == "verified"


def test_only_a_person_shapes_a_milestone_and_scope_is_checked(pair):
    e, _ = pair
    with pytest.raises(RungError):
        e.create_milestone("linkpair", "x", "y", ["S-1.1"], actor=AGENT)
    with pytest.raises(RungError):
        e.create_milestone("linkpair", "x", "y", ["R-1"])  # a requirement is not a specification
    with pytest.raises(RungError):
        e.create_milestone("linkpair", "x", "", ["S-1.1"])
    m = e.create_milestone("linkpair", "x", "y", ["s-1.1"])
    assert [s["id"] for s in m["scope"]] == ["S-1.1"]
    with pytest.raises(RungError) as err:
        e.approve_milestone("linkpair", m["id"])  # no command check yet
    assert err.value.code == "no_checks"
    with pytest.raises(RungError):
        e.approve_milestone("linkpair", m["id"], actor=AGENT)


def test_a_check_whose_files_changed_does_not_run(pair):
    e, folder = pair
    seed.fix_linkpair(folder)
    e.accept_test_files("linkpair", "T-2.1a")
    e.run_test("linkpair", "T-1.1a")
    e.run_test("linkpair", "T-2.1a")
    mid = _milestone(e)
    e.approve_milestone("linkpair", mid)
    (folder / "journey" / "test_journey.py").write_text("def test_create_a_link_and_see_it():\n    pass\n")
    e.run_test("linkpair", "T-1.1a")
    e.run_test("linkpair", "T-2.1a")
    [r] = e.run_milestone("linkpair", mid)
    assert r["status"] == "error" and r["reason"] == "verification_changed"
    v = e.milestone("linkpair", mid)
    assert v["state"] == "could_not_verify" and v["next_action"]["kind"] == "review_check_files"
    e.accept_check_files("linkpair", mid, f"{mid}.a")
    [r] = e.run_milestone("linkpair", mid)
    assert r["status"] == "pass"


def test_integration_waits_for_a_develop_run(pair):
    e, _ = pair
    e.run_test("linkpair", "T-1.1a")
    e.run_test("linkpair", "T-2.1a")
    mid = _milestone(e)
    e.approve_milestone("linkpair", mid)
    p = e._project_row("linkpair")
    with e._tx() as c:
        c.execute("INSERT INTO runs(project_pk, spec_pk, profile, picked_by, status, max_attempts, timeout_s, "
                  "created_at) SELECT ?, pk, 'coder', 'human', 'running', 1, 60, 0 FROM rungs "
                  "WHERE project_pk=? AND rid='S-1.1'", (p["pk"], p["pk"]))
    with pytest.raises(RungError) as err:
        e.run_milestone("linkpair", mid)
    assert err.value.code == "busy"


def test_no_develop_run_starts_while_integration_runs(pair):
    e, _ = pair
    e.run_test("linkpair", "T-1.1a")
    e.run_test("linkpair", "T-2.1a")
    mid = _milestone(e)
    e.approve_milestone("linkpair", mid)
    ch = e._q1("SELECT pk FROM milestone_checks")
    with e._tx() as c:
        c.execute("INSERT INTO milestone_runs(check_pk, n, version, status, started_at) VALUES (?,?,?,?,?)",
                  (ch["pk"], 1, 2, "running", 0))
    with pytest.raises(RungError) as err:
        e.start_run("linkpair", "S-1.1", profile="coder")
    assert err.value.code == "busy"
    with pytest.raises(RungError) as err:
        e.run_milestone("linkpair", mid)
    assert err.value.code == "busy"
    assert e.milestone("linkpair", mid)["state"] == "verifying"


def test_rest_doors(pair):
    from rung_engine import api
    from rung_engine.service import Service
    e, folder = pair
    svc = Service(e, inline_runs=True)
    seed.fix_linkpair(folder)
    e.accept_test_files("linkpair", "T-2.1a")
    e.run_test("linkpair", "T-1.1a")
    e.run_test("linkpair", "T-2.1a")
    st, m = api.handle(svc, "POST", "/projects/linkpair/milestones", {"title": "Share", "journey": "Create and see",
                                                                      "scope": ["S-1.1", "S-2.1"]})
    assert st == 200 and m["state"] == "draft"
    st, _ = api.handle(svc, "POST", "/projects/linkpair/milestones/M-1/run", {})
    assert st == 409
    st, _ = api.handle(svc, "POST", "/projects/linkpair/milestones/M-1/checks",
                       {"type": "command", "command": "pytest -q journey/test_journey.py"})
    assert st == 200
    assert api.handle(svc, "POST", "/projects/linkpair/milestones/M-1/approve", {})[0] == 200
    assert api.handle(svc, "POST", "/projects/linkpair/milestones/M-1/run", {})[0] == 200
    st, v = api.handle(svc, "GET", "/projects/linkpair/milestones/m-1")
    assert st == 200 and v["state"] == "verified" and v["checks"][0]["runs"][0]["status"] == "pass"
    st, x = api.handle(svc, "POST", "/projects/linkpair/milestones/M-1/export", {})
    assert st == 200 and "State: Verified" in x["markdown"]
    assert api.handle(svc, "GET", "/projects/linkpair/milestones/M-9")[0] == 404


def test_cli_milestone_is_a_gate(tmp_path):
    import subprocess
    import sys
    from pathlib import Path
    from rung_engine import Engine
    root = Path(__file__).resolve().parent.parent
    store = tmp_path / "rung.db"
    e = Engine(str(store))
    folder = tmp_path / "linkpair"
    folder.mkdir()
    seed.seed_linkpair(e, folder)
    e.open_project("linkpair")
    e.run_test("linkpair", "T-1.1a")
    e.run_test("linkpair", "T-2.1a")
    _milestone(e)
    e.approve_milestone("linkpair", "M-1")
    env = {**__import__("os").environ, "RUNG_STORE": str(store), "PYTHONPATH": str(root)}

    def cli(*a):
        return subprocess.run([sys.executable, "-m", "rung_engine.cli", *a], capture_output=True, text=True,
                              env=env, cwd=root)
    r = cli("milestone")
    assert r.returncode == 0 and "M-1" in r.stdout and "ready" in r.stdout, r.stdout + r.stderr
    r = cli("milestone", "M-1", "--run")
    assert r.returncode == 1 and "M-1.a #1: fail" in r.stdout and "integration_failed" in r.stdout, r.stdout + r.stderr
    assert "next: repair M-1.a" in r.stdout
    r = cli("enforcement", "no-such-session")
    assert r.returncode == 0 and "unbound (no open claim)" in r.stdout, r.stdout + r.stderr
