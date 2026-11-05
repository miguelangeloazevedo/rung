import time

import pytest

from rung_engine import RungError
from rung_engine.runner import run_loop
from rung_engine.service import Service

from test_flow import _tests_step


def ready_to_develop(svc):
    e, made = _tests_step(svc)
    for t in made:
        e.approve("csvtidy", t["id"])
    e.approve_tests("csvtidy", "N-2")
    return e


def test_develop_until_green_with_pick(seeded, svc):
    e = ready_to_develop(svc)
    sug = e.suggest("csvtidy", "S-4.1")["suggestions"]
    second = sug[1]["profile"]
    run = e.start_run("csvtidy", "S-4.1", profile=second)
    assert run["status"] == "queued" and run["profile"] == second
    assert e.home("csvtidy")["running"][0]["spec"] == "S-4.1"
    out = run_loop(e, run["id"])
    assert out["status"] == "passed"
    assert len(out["attempts"]) == 2
    a1, a2 = out["attempts"]
    assert a1["status"] == "fail" and a2["status"] == "pass"
    assert a1["files_changed"][0]["path"] == "csvtidy/merge.py"
    assert "test_join_key" in a1["fed_forward"]
    assert a2["fed_in"] == a1["fed_forward"]
    assert a1["executions"][0]["status"] == "fail" and a2["executions"][0]["status"] == "pass"
    assert any("pytest tests/test_merge.py::test_join_key" in c for c in a1["commands"])
    ex = e.executions("csvtidy", "T-4.1a")
    assert [x["carried_by"] for x in ex] == [second, second]
    assert e.coverage("csvtidy", "R-4") == "covered"
    assert e.suggest("csvtidy", "S-4.1")["pick"]["picked_by"] == "you"
    assert e.home("csvtidy")["running"] == []


def test_budget_never_exceeded(seeded, svc):
    e = ready_to_develop(svc)
    e.save_profiles([{**e.profile("coder"), "max_runs": 1}])
    run = e.start_run("csvtidy", "S-4.1", profile="coder")
    out = run_loop(e, run["id"])
    assert out["status"] == "failed" and len(out["attempts"]) == 1


def test_cannot_send_twice_or_when_locked(seeded, svc):
    e = seeded
    with pytest.raises(RungError):
        e.start_run("csvtidy", "S-1.1x")
    e.start_run("csvtidy", "S-2.1")
    with pytest.raises(RungError):
        e.start_run("csvtidy", "S-2.1")


def test_runner_process_and_cancel(seeded, tmp_path):
    e = seeded
    e.add_test("csvtidy", "S-1.1", {"type": "command", "command": "sleep 20", "timeout": 60}, status="approved")
    svc = Service(e, log_dir=tmp_path / "logs")
    run = svc.send("csvtidy", "S-1.1")
    assert run["pid"]
    deadline = time.time() + 20
    while time.time() < deadline and not any(
            x["status"] == "running" for x in e.executions("csvtidy", "T-1.1b")):
        time.sleep(0.2)
    svc.cancel(run["id"])
    while time.time() < deadline and e.run(run["id"])["status"] == "running":
        time.sleep(0.2)
    assert e.run(run["id"])["status"] == "cancelled"
    assert e.executions("csvtidy", "T-1.1b")[0]["status"] == "cancelled"


def test_reconcile_marks_dead_runner(seeded):
    e = seeded
    run = e.start_run("csvtidy", "S-2.1")
    e.set_run(run["id"], status="running", pid=999999)
    assert e.reconcile_runs(lambda pid: False) == [run["id"]]
    assert e.run(run["id"])["status"] == "interrupted"
