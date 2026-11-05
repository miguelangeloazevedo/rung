import pytest

from rung_engine import Actor, RungError


def _result(e, rid):
    stack = list(e.tree("csvtidy"))
    while stack:
        n = stack.pop()
        if n["id"] == rid:
            return n["result"]
        stack.extend(n.get("children", []))
    raise KeyError(rid)


def test_failed_runs_and_defect(seeded):
    e = seeded
    ex = e.executions("csvtidy", "T-2.1a")
    assert [x["status"] for x in ex] == ["pass", "fail", "fail"]
    one = e.execution("csvtidy", "T-2.1a", 1)
    assert one["exit_code"] == 1 and "test_ambiguous_locale" in one["output"]
    assert e.defects("csvtidy") == []
    n = e.run_test("csvtidy", "T-2.1a")["n"]
    assert n == 4
    assert [x["status"] for x in e.executions("csvtidy", "T-2.1a")][1:] == ["pass", "fail", "fail"]
    with pytest.raises(RungError):
        e.raise_defect("csvtidy", "T-2.1a", [1, 2], "Day-first dates parsed as month-first", actor=Actor("agent", "coder"))
    d = e.raise_defect("csvtidy", "T-2.1a", [1, 2], "Day-first dates parsed as month-first")
    assert d == {**d, "id": "D-1", "test": "T-2.1a", "spec": "S-2.1", "executions": [1, 2], "created_by": "you"}


def test_manual_needs_human_approval(seeded):
    e = seeded
    f = e.record_manual("csvtidy", "T-2.1b", "fail", "dates sort as text")
    assert f["status"] == "fail" and f["counts"]
    chk = e.check("csvtidy", "S-2.1")
    assert not chk["ok"] and any("T-2.1b failed" in b for b in chk["blockers"])
    p = e.record_manual("csvtidy", "T-2.1b", "pass", "Sorted 120 rows, order correct")
    assert p["status"] == "pending" and not p["counts"]
    assert any(i["type"] == "approval" for i in e.needs_you("csvtidy"))
    assert not e.check("csvtidy", "S-2.1")["ok"]  # latest counting manual result is still the fail
    assert _result(e, "T-2.1b") == "pending"  # shown as pending, still not counted
    with pytest.raises(RungError):
        e.approve_result("csvtidy", "T-2.1b", p["n"], Actor("agent", "coder"))
    a = e.approve_result("csvtidy", "T-2.1b", p["n"])
    assert a["status"] == "pass" and a["counts"]
    assert e.check("csvtidy", "S-2.1")["ok"]
    assert _result(e, "T-2.1b") == "pass"
    hist = e.executions("csvtidy", "T-2.1b")
    assert [(h["status"], h["note"], h["recorder"]) for h in hist] == [
        ("pass", "Sorted 120 rows, order correct", "you"), ("fail", "dates sort as text", "you")]
    assert all(h["started_at"] for h in hist)


def test_ai_judged_never_releases(seeded):
    e = seeded
    e.add_test("csvtidy", "S-1.1", {"type": "ai_judged", "command": "false", "text": "Output reads well"}, status="approved")
    e.run_test("csvtidy", "T-1.1b")
    chk = e.check("csvtidy", "S-1.1")
    assert not chk["ok"] and any("AI judged" in b for b in chk["blockers"])


def test_exe06_cancel_running_execution(seeded):
    e = seeded
    e.add_test("csvtidy", "S-1.1", {"type": "command", "command": "sleep 5", "timeout": 30}, status="approved")
    import threading
    n = e.begin_execution("csvtidy", "T-1.1b")
    t = threading.Thread(target=e.perform_execution, args=("csvtidy", "T-1.1b", n))
    t.start()
    import time
    time.sleep(0.5)
    e.cancel_execution("csvtidy", "T-1.1b", n)
    t.join(10)
    assert e.execution("csvtidy", "T-1.1b", n)["status"] == "cancelled"


def test_timeout_is_an_error_not_a_fail(seeded):
    e = seeded
    e.add_test("csvtidy", "S-1.1", {"type": "command", "command": "sleep 5", "timeout": 1}, status="approved")
    r = e.run_test("csvtidy", "T-1.1b", carried_by="coder")
    assert r["status"] == "error" and "timed out" in r["output"]
