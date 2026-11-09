"""Journeys (SYS-07), regression (SYS-08), quality obligations (SYS-09), environment (SYS-10) and change
impact (SYS-11) on milestones (decisions Round 24)."""

import pytest

from rung_engine import Actor, RungError
from support import seed

AGENT = Actor("agent", "coder")


@pytest.fixture
def pair(engine, tmp_path, monkeypatch):
    import os
    import sys
    from pathlib import Path
    monkeypatch.setenv("PATH", str(Path(sys.executable).parent) + os.pathsep + os.environ["PATH"])
    folder = tmp_path / "linkpair"
    folder.mkdir()
    seed.seed_linkpair(engine, folder)
    seed.fix_linkpair(folder)
    engine.accept_test_files("linkpair", "T-2.1a")
    engine.open_project("linkpair")
    engine.run_test("linkpair", "T-1.1a")
    engine.run_test("linkpair", "T-2.1a")
    return engine, folder


def _m(e, title="Share", check="pytest -q journey/test_journey.py", scope=("S-1.1", "S-2.1")):
    m = e.create_milestone("linkpair", title, "Create a link and see it", list(scope))
    e.add_milestone_check("linkpair", m["id"], {"type": "command", "command": check})
    return m["id"]


def test_jrn01_jrn02_jrn03_journeys(pair):
    e, folder = pair
    mid = _m(e)
    with pytest.raises(RungError):
        e.set_milestone_system("linkpair", mid, "journeys", [{"name": "bulk import", "in_scope": False}])
    with pytest.raises(RungError):
        e.set_milestone_system("linkpair", mid, "journeys", [{"name": "x"}], actor=AGENT)
    e.set_milestone_system("linkpair", mid, "journeys", [
        {"name": "shorten and follow", "in_scope": True},
        {"name": "bulk import", "in_scope": False, "reason": "not in this release"}])
    e.approve_milestone("linkpair", mid)
    e.run_milestone("linkpair", mid)
    v = e.milestone("linkpair", mid)
    assert not v["ok"] and "journey shorten and follow has no check" in [b["text"] for b in v["blockers"]]
    e.set_milestone_system("linkpair", mid, "journeys", [
        {"name": "shorten and follow", "check": f"{mid}.a"},
        {"name": "bulk import", "in_scope": False, "reason": "not in this release"}])
    e.approve_milestone("linkpair", mid)
    e.run_milestone("linkpair", mid)
    assert e.milestone("linkpair", mid)["ok"]
    md = e.milestone_markdown("linkpair", mid)
    assert "bulk import: out of scope (not in this release), not counted as passed" in md


def test_rgr01_rgr02_regression_baseline(pair):
    e, folder = pair
    m1 = _m(e)
    e.approve_milestone("linkpair", m1)
    e.run_milestone("linkpair", m1)
    assert e.milestone("linkpair", m1)["ok"]
    m2 = _m(e, "Page only", "pytest -q tests/test_page.py", scope=("S-2.1",))
    with pytest.raises(RungError):
        e.set_milestone_system("linkpair", m1, "baseline", [m2])  # not earlier
    e.set_milestone_system("linkpair", m2, "baseline", [m1])
    e.approve_milestone("linkpair", m2)
    # the API now wraps its answer: every unit test passes, the earlier journey breaks
    api = folder / "shortly" / "api.py"
    api.write_text(api.read_text().replace('out = json.dumps(create(body["url"])).encode()',
                                           'out = json.dumps({"link": create(body["url"])}).encode()'))
    e.run_test("linkpair", "T-2.1a")
    e.run_test("linkpair", "T-1.1a")
    e.run_milestone("linkpair", m2)
    v = e.milestone("linkpair", m2)
    assert v["state"] == "integration_failed" and v["blockers"][0]["code"] == "regression_failed", v["blockers"]
    assert e.milestone("linkpair", m2)["checks"][0]["state"] == "satisfied"  # its own check passes


def test_qlt01_qlt02_quality_obligation(pair):
    e, folder = pair
    mid = _m(e)
    (folder / "perf.py").write_text("import os\nprint('p95_ms=' + os.environ.get('P95', open('p95.txt').read().strip()))\n")
    (folder / "p95.txt").write_text("350")
    e.run_test("linkpair", "T-1.1a"); e.run_test("linkpair", "T-2.1a")
    with pytest.raises(RungError):
        e.add_milestone_check("linkpair", mid, {"command": "python3 perf.py", "quality": {"category": "speed"}})
    e.add_milestone_check("linkpair", mid, {"command": "python3 perf.py", "quality": {
        "category": "performance", "measure": r"p95_ms=(\d+)", "threshold": 200, "unit": "ms",
        "workload": "100 requests of 10 links", "environment": "laptop, Python 3"}})
    e.approve_milestone("linkpair", mid)
    e.run_milestone("linkpair", mid)
    v = e.milestone("linkpair", mid)
    assert v["state"] == "obligation_unmet"
    assert "350 ms against 200 under 100 requests of 10 links" in v["blockers"][0]["text"]
    (folder / "p95.txt").write_text("120")
    e.run_test("linkpair", "T-1.1a"); e.run_test("linkpair", "T-2.1a")
    e.run_milestone("linkpair", mid)
    v = e.milestone("linkpair", mid)
    assert v["ok"], v["blockers"]
    md = e.milestone_markdown("linkpair", mid)
    assert "measured 120 ms against 200" in md and "fast" not in md.lower() and "secure" not in md.lower()


def test_env01_env02_env03_environment(pair):
    e, folder = pair
    mid = _m(e)
    e.set_milestone_system("linkpair", mid, "environment", {"probes": [{"command": "python3 --version",
                                                                         "contains": "Python 9"}]})
    e.approve_milestone("linkpair", mid)
    e.run_milestone("linkpair", mid)
    v = e.milestone("linkpair", mid)
    assert v["state"] == "could_not_verify" and v["blockers"][0]["code"] == "environment_mismatch"
    assert "python3 --version" in v["blockers"][0]["text"]
    e.set_milestone_system("linkpair", mid, "environment", {"probes": [{"command": "python3 --version",
                                                                         "contains": "Python 3"}],
                                                            "migration": "python3 -c 'raise SystemExit(3)'"})
    e.approve_milestone("linkpair", mid)
    e.run_milestone("linkpair", mid)
    v = e.milestone("linkpair", mid)
    assert v["blockers"][0]["code"] == "migration_failed" and v["state"] == "integration_failed"
    e.set_milestone_system("linkpair", mid, "environment", {"probes": [{"command": "python3 --version",
                                                                         "contains": "Python 3"}],
                                                            "migration": "true"})
    e.approve_milestone("linkpair", mid)
    e.run_milestone("linkpair", mid)
    v = e.milestone("linkpair", mid)
    assert v["ok"], v["blockers"]
    assert v["env_run"]["probes"][0]["output"].startswith("Python 3")
    e.run_milestone("linkpair", mid)
    assert e.milestone("linkpair", mid)["env_run"]["setup"] == v["env_run"]["setup"]


def test_imp01_imp02_imp03_change_impact(pair):
    e, folder = pair
    (folder / "docs").mkdir()
    (folder / "docs" / "guide.md").write_text("guide\n")
    for n, paths in (("api", ["shortly/api.py"]), ("page", ["shortly/page.py"]), ("docs", ["docs"])):
        e.save_arch("linkpair", "component", n, {"paths": paths})
        e.approve_arch("linkpair", "component", n)
    e.set_spec_components("linkpair", "S-1.1", ["api"])
    e.set_spec_components("linkpair", "S-2.1", ["page"])
    mid = _m(e)
    e.set_milestone_components("linkpair", mid, ["api", "page"])
    e.approve_milestone("linkpair", mid)
    e.run_test("linkpair", "T-1.1a"); e.run_test("linkpair", "T-2.1a")
    e.run_milestone("linkpair", mid)
    assert e.milestone("linkpair", mid)["ok"]
    assert e.milestone("linkpair", mid)["judged_on"] == ("Judged on: shortly/api.py, shortly/page.py and files "
                                                         "outside every component")
    (folder / "docs" / "guide.md").write_text("guide, longer\n")
    assert e.milestone("linkpair", mid)["ok"]  # outside its paths
    assert e.check("linkpair", "S-1.1")["ok"]
    api = folder / "shortly" / "api.py"
    api.write_text(api.read_text() + "\n# touched\n")
    v = e.milestone("linkpair", mid)
    assert v["state"] == "out_of_date" and "S-1.1 is not verified" in v["blockers"][0]["text"], v["blockers"]
    assert not e.check("linkpair", "S-1.1")["ok"] and e.check("linkpair", "S-2.1")["ok"]  # page evidence stays
    out = e.check_everything("linkpair")
    assert {t["test"] for t in out["tests"]} == {"T-1.1a", "T-2.1a"} and out["milestones"][0]["milestone"] == mid
    assert e.milestone("linkpair", mid)["ok"]


def test_rep01_rep02_system_report(pair):
    e, folder = pair
    r = e.system_report("linkpair")
    assert not r["accepted"] and r["open"] == ["no milestone is defined"]
    mid = _m(e)
    e.set_milestone_system("linkpair", mid, "journeys", [
        {"name": "shorten and follow", "check": f"{mid}.a"},
        {"name": "bulk import", "in_scope": False, "reason": "not in this release"}])
    e.add_milestone_check("linkpair", mid, {"type": "manual", "steps": ["Open the page", "Click the link"]})
    e.approve_milestone("linkpair", mid)
    e.run_milestone("linkpair", mid)
    r = e.system_report("linkpair")
    assert r["verdict"] == "Not accepted" and r["open"][0].startswith(f"{mid}: {mid}.b")
    e.record_milestone_manual("linkpair", mid, f"{mid}.b", "pass", "looked right")
    r = e.system_report("linkpair")
    assert r["verdict"] == "Accepted", r["open"]
    md = e.system_report_markdown("linkpair")
    for want in ("Verdict: Accepted", "bulk import: out of scope (not in this release)", "Manual decisions:",
                 f"{mid}.b: satisfied by"):
        assert want in md, md
    (folder / "shortly" / "page.py").write_text((folder / "shortly" / "page.py").read_text() + "\n# later\n")
    r = e.system_report("linkpair")
    assert not r["accepted"] and r["open"] and r["open"][0].startswith(mid)

