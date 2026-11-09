"""Architecture baseline (SYS-02) and dependencies (SYS-03), decisions Round 24.

Components and contracts are versioned and approved by a person; an approved contract change puts the
specifications and milestones touching its components out of date until they are checked (or approved) again.
A specification may require others; cycles are refused and a develop run waits for its prerequisites."""

import pytest

from rung_engine import HUMAN, Actor, RungError
from support import seed

AGENT = Actor("agent", "coder")


@pytest.fixture
def pair(engine, tmp_path):
    folder = tmp_path / "linkpair"
    folder.mkdir()
    seed.seed_linkpair(engine, folder)
    engine.open_project("linkpair")
    return engine, folder


def _arch(e):
    e.save_arch("linkpair", "component", "api", {"responsibility": "Creates short links", "paths": ["shortly/api.py"]})
    e.save_arch("linkpair", "component", "page", {"responsibility": "Shows the link", "paths": ["shortly/page.py"]})
    e.approve_arch("linkpair", "component", "api")
    e.approve_arch("linkpair", "component", "page")
    e.save_arch("linkpair", "contract", "short link JSON", {"kind": "api", "producer": "api", "consumers": ["page"],
                                                            "text": "POST /links answers {\"short_url\": ...}"})
    return e.approve_arch("linkpair", "contract", "short link JSON")


def test_sys02_components_and_contracts_are_versioned_and_approved(pair):
    e, _ = pair
    with pytest.raises(RungError) as x:
        e.save_arch("linkpair", "component", "api", {}, actor=AGENT)
    assert x.value.code == "forbidden"
    with pytest.raises(RungError):  # a contract between components that do not exist
        e.save_arch("linkpair", "contract", "c", {"producer": "nope", "consumers": ["page"]})
    with pytest.raises(RungError):
        e.save_arch("linkpair", "component", "x", {"paths": ["../outside"]})
    c = _arch(e)
    assert c["current"]["version"] == 1 and c["draft"] is None and c["affected"] == {"specifications": [],
                                                                                     "milestones": []}
    a = e.architecture("linkpair")
    assert [x["name"] for x in a["components"]] == ["api", "page"]
    assert a["contracts"][0]["current"]["producer"] == "api"
    # a draft changes nothing until it is approved; history keeps every approved version
    e.save_arch("linkpair", "contract", "short link JSON", {"text": "POST /links answers {\"url\": ...}"})
    c = e.arch_item("linkpair", "contract", "short link JSON")
    assert c["current"]["version"] == 1 and c["draft"]["version"] == 2
    e.approve_arch("linkpair", "contract", "short link JSON")
    c = e.arch_item("linkpair", "contract", "short link JSON")
    assert [(h["version"], h["status"]) for h in c["history"]] == [(1, "superseded"), (2, "approved")]
    with pytest.raises(RungError) as x:
        e.set_spec_components("linkpair", "S-1.1", ["missing"])
    assert x.value.status == 400


def test_sys02_a_contract_change_puts_its_work_out_of_date(pair):
    e, folder = pair
    _arch(e)
    assert e.run_test("linkpair", "T-1.1a")["status"] == "pass"
    assert e.run_test("linkpair", "T-2.1a")["status"] == "pass"
    e.set_spec_components("linkpair", "S-1.1", ["api"])
    e.set_spec_components("linkpair", "S-2.1", ["page"])
    m = e.create_milestone("linkpair", "Share a short link", "Create a link and see it", ["S-1.1", "S-2.1"])
    e.add_milestone_check("linkpair", m["id"], {"type": "command", "command": "true"})
    e.set_milestone_components("linkpair", m["id"], ["api", "page"])
    e.approve_milestone("linkpair", m["id"])
    # naming components changes what the evidence is judged on (SYS-11): the tests run again
    assert e.check("linkpair", "S-1.1")["verification"] == "out_of_date"
    e.run_test("linkpair", "T-1.1a"); e.run_test("linkpair", "T-2.1a")
    assert e.check("linkpair", "S-1.1")["ok"]
    e.save_arch("linkpair", "contract", "short link JSON", {"text": "POST /links answers {\"link\": ...}"})
    assert e.check("linkpair", "S-1.1")["ok"]  # a draft changes nothing
    out = e.approve_arch("linkpair", "contract", "short link JSON")
    assert out["affected"] == {"specifications": ["S-1.1", "S-2.1"], "milestones": [m["id"]]}
    for rid in ("S-1.1", "S-2.1"):
        v = e.check("linkpair", rid)
        assert not v["ok"] and v["verification"] == "out_of_date" and "contract_changed" in v["codes"], v
    mv = e.milestone("linkpair", m["id"])
    assert mv["state"] == "out_of_date" and "contract_changed" in [b["code"] for b in mv["blockers"]]
    # checked again: the specification is verified; approved again: the milestone no longer names the change
    e.run_test("linkpair", "T-1.1a")
    e.run_test("linkpair", "T-2.1a")
    assert e.check("linkpair", "S-1.1")["ok"] and e.check("linkpair", "S-2.1")["ok"]
    e.approve_milestone("linkpair", m["id"])
    assert "contract_changed" not in [b["code"] for b in e.milestone("linkpair", m["id"])["blockers"]]


def test_sys03_dependencies_refuse_cycles_and_wait_for_prerequisites(pair):
    e, folder = pair
    d = e.add_dependency("linkpair", "S-2.1", "S-1.1")
    assert [r["id"] for r in d["requires"]] == ["S-1.1"]
    assert e.dependencies("linkpair", "S-1.1")["required_by"] == ["S-2.1"]
    with pytest.raises(RungError) as x:
        e.add_dependency("linkpair", "S-1.1", "S-2.1")
    assert x.value.code == "cycle" and "S-1.1 requires S-2.1 requires S-1.1" in str(x.value)
    for bad in ("S-1.1", "S-9.9", "other:S-1.1"):
        with pytest.raises(RungError):
            e.add_dependency("linkpair", "S-1.1" if bad != "S-1.1" else "S-1.1", bad)
    with pytest.raises(RungError):
        e.add_dependency("linkpair", "S-2.1", "S-1.1", actor=AGENT)
    # S-1.1 fails: S-2.1 does not start, naming the path
    (folder / "tests" / "test_api.py").write_text("def test_x():\n    assert False\n")
    e.accept_test_files("linkpair", "T-1.1a")
    assert e.run_test("linkpair", "T-1.1a")["status"] == "fail"
    with pytest.raises(RungError) as x:
        e.start_run("linkpair", "S-2.1", profile="coder")
    assert x.value.code == "blocked" and "S-2.1 waits for S-1.1: Failed" in str(x.value)
    # a specification without prerequisites starts
    run = e.start_run("linkpair", "S-1.1", profile="coder")
    assert run["status"] in ("queued", "running")
    e.remove_dependency("linkpair", "S-2.1", "S-1.1")
    assert e.dependencies("linkpair", "S-2.1")["requires"] == []


def test_sys02_sys03_rest(pair, svc):
    e, _ = pair
    from rung_engine.api import handle
    for body in ({"kind": "component", "name": "api", "paths": ["shortly"]},
                 {"kind": "component", "name": "page", "paths": ["shortly/page.py"]}):
        assert handle(svc, "POST", "/projects/linkpair/architecture", body)[0] == 200
        assert handle(svc, "POST", "/projects/linkpair/architecture/approve", {"kind": "component",
                                                                              "name": body["name"]})[0] == 200
    st, out = handle(svc, "POST", "/projects/linkpair/architecture", {"kind": "contract", "name": "short link JSON",
                     "contract_kind": "api", "producer": "api", "consumers": ["page"]})
    assert st == 200 and out["draft"]["kind"] == "api"
    assert handle(svc, "POST", "/projects/linkpair/architecture", {"kind": "component", "name": "x", "bogus": 1})[0] == 400
    st, out = handle(svc, "GET", "/projects/linkpair/architecture")
    assert st == 200 and len(out["components"]) == 2 and out["contracts"][0]["draft"]
    assert handle(svc, "POST", "/projects/linkpair/rungs/S-1.1/components", {"components": ["api"]})[0] == 200
    assert e.rung("linkpair", "S-1.1")["components"] == ["api"]
    st, out = handle(svc, "POST", "/projects/linkpair/rungs/S-2.1/dependencies", {"requires": "S-1.1"})
    assert st == 200 and out["requires"][0]["id"] == "S-1.1"
    st, out = handle(svc, "POST", "/projects/linkpair/rungs/S-1.1/dependencies", {"requires": "S-2.1"})
    assert st == 400 and "cycle" in str(out)
    st, out = handle(svc, "GET", "/projects/linkpair/rungs/S-1.1/dependencies")
    assert out["required_by"] == ["S-2.1"]


def _third(e, folder):
    (folder / "tests" / "test_docs.py").write_text("def test_docs():\n    assert True\n")
    e.add_requirement("linkpair", "N-1", "The docs describe the API", HUMAN)
    e.approve_requirements("linkpair", "N-1", HUMAN)
    e.write_spec("linkpair", "R-3", "The README names the endpoint", tags=["python"])
    e.approve_drafted("linkpair", "N-1", HUMAN)
    e.add_test("linkpair", "S-3.1", {"type": "command", "command": "pytest -q tests/test_docs.py"}, HUMAN,
               status="approved")
    e.approve_tests("linkpair", "N-1", HUMAN)


def test_sys04_plan_starts_ready_work_only(pair):
    e, folder = pair
    _third(e, folder)
    e.add_dependency("linkpair", "S-2.1", "S-1.1")
    pl = {i["spec"]: i for i in e.plan("linkpair")["items"]}
    assert (pl["S-1.1"]["state"], pl["S-2.1"]["state"], pl["S-3.1"]["state"]) == ("ready", "blocked", "ready")
    assert pl["S-2.1"]["blocked_by"] == ["S-1.1"]
    with pytest.raises(RungError):
        e.start_ready("linkpair", actor=AGENT)
    out = e.start_ready("linkpair")
    assert [x["spec"] for x in out["started"]] == ["S-1.1", "S-3.1"]
    pl = {i["spec"]: i for i in out["plan"]["items"]}
    assert pl["S-2.1"]["state"] == "blocked" and pl["S-1.1"]["state"] == "running"
    assert out["plan"]["model_usage"] == "unavailable"


def test_sys04_budget_stops_the_plan(pair):
    e, folder = pair
    _third(e, folder)
    e.set_plan_budget("linkpair", 1)
    out = e.start_ready("linkpair", launch=lambda proj, rid: _fake_run(e, proj, rid))
    assert [x["spec"] for x in out["started"]] == ["S-1.1"] and "budget of 1 attempts is used" in out["stopped"]
    assert out["plan"]["budget"]["exhausted"]
    with pytest.raises(RungError):
        e.set_plan_budget("linkpair", 0)


def _fake_run(e, proj, rid):
    run = e.start_run(proj, rid, profile="coder")
    e.start_running(run["id"], e.clock(), 0)
    e.begin_attempt(run["id"], 1, "p", "")
    return run


def test_sys04_plan_waits_for_capacity_and_orders_by_dependency(pair):
    e, folder = pair
    _third(e, folder)
    e.add_dependency("linkpair", "S-1.1", "S-3.1")
    order = [i["spec"] for i in e.plan("linkpair")["items"]]
    assert order.index("S-3.1") < order.index("S-1.1")
    e.remove_dependency("linkpair", "S-1.1", "S-3.1")
    e.save_profiles([{"name": p["name"], "at_once": 1, "enabled": p["name"] == "coder"} for p in e.profiles()])
    out = e.start_ready("linkpair", launch=lambda proj, rid: _fake_run(e, proj, rid))
    assert [x["spec"] for x in out["started"]] == ["S-1.1"]
    assert [r["spec"] for r in out["refused"]] == ["S-2.1", "S-3.1"]
    assert all("at capacity" in r["reason"] for r in out["refused"])
    states = {i["spec"]: i["state"] for i in out["plan"]["items"]}
    assert states == {"S-1.1": "running", "S-2.1": "waiting", "S-3.1": "waiting"}, states


CHECK = "python3 -c \"from shortly import api, page; page.render(api.create('https://x.example'))\""


def _contract(e):
    for n, paths in (("api", ["shortly/api.py"]), ("page", ["shortly/page.py"])):
        e.save_arch("linkpair", "component", n, {"paths": paths})
        e.approve_arch("linkpair", "component", n)
    e.save_arch("linkpair", "contract", "short link JSON", {"contract_kind": "api", "producer": "api",
                                                            "consumers": ["page"], "artifacts": ["shortly/api.py"]})
    e.approve_arch("linkpair", "contract", "short link JSON")


def test_sys06_contract_check_catches_the_mismatch(pair):
    e, folder = pair
    _contract(e)
    assert e.run_test("linkpair", "T-1.1a")["status"] == "pass" and e.run_test("linkpair", "T-2.1a")["status"] == "pass"
    m = e.create_milestone("linkpair", "Share", "Create and see", ["S-1.1", "S-2.1"])
    e.set_milestone_components("linkpair", m["id"], ["api", "page"])
    e.add_milestone_check("linkpair", m["id"], {"type": "command", "command": "true"})
    e.approve_milestone("linkpair", m["id"])
    e.run_milestone("linkpair", m["id"])
    assert e.milestone("linkpair", m["id"])["ok"]  # no contract check yet
    e.add_contract_check("linkpair", "short link JSON", CHECK, actor=AGENT)  # an agent proposes
    assert e.milestone("linkpair", m["id"])["ok"]  # a draft counts for nothing
    with pytest.raises(RungError):
        e.approve_contract_check("linkpair", "short link JSON", "CC-1", actor=AGENT)
    e.approve_contract_check("linkpair", "short link JSON", "CC-1")
    v = e.milestone("linkpair", m["id"])
    assert not v["ok"] and v["blockers"][0]["code"] == "contract_not_run"
    out = e.run_contract_checks("linkpair", "short link JSON")
    assert out["state"] == "failed" and out["checks"][0]["contract_version"] == 1
    v = e.milestone("linkpair", m["id"])
    assert v["state"] == "integration_failed" and "contract short link JSON check CC-1 failed" in v["blockers"][0]["text"]
    assert e.check("linkpair", "S-1.1")["ok"] and e.check("linkpair", "S-2.1")["ok"]  # each side's tests pass
    # repair the producer: it also sends the field the consumer reads
    api = folder / "shortly" / "api.py"
    api.write_text(api.read_text().replace('return {"code": code, "short_url": "/r/" + code}',
                                           'return {"code": code, "short_url": "/r/" + code, "url": "/r/" + code}'))
    assert e.run_contract_checks("linkpair", "short link JSON")["state"] == "satisfied"
    e.run_test("linkpair", "T-1.1a"); e.run_test("linkpair", "T-2.1a"); e.run_milestone("linkpair", m["id"])
    assert e.milestone("linkpair", m["id"])["ok"]
    # a code change: out of date
    (folder / "shortly" / "extra.py").write_text("X = 1\n")
    st = e.contract_checks("linkpair", "short link JSON")
    assert st["state"] == "out_of_date" and "changed since" in st["checks"][0]["why"]
    e.run_contract_checks("linkpair", "short link JSON")
    # a new contract version: out of date too
    e.save_arch("linkpair", "contract", "short link JSON", {"text": "v2"})
    e.approve_arch("linkpair", "contract", "short link JSON")
    st = e.contract_checks("linkpair", "short link JSON")
    assert st["state"] == "out_of_date" and "contract v1, now v2" in st["checks"][0]["why"]


def test_bud01_bud02_bud03_budgets_and_recovery(pair):
    e, folder = pair
    _third(e, folder)
    assert e.run_test("linkpair", "T-3.1a")["status"] == "pass" and e.check("linkpair", "S-3.1")["ok"]
    with pytest.raises(RungError):
        e.set_plan_budget("linkpair", None, minutes=0)
    with pytest.raises(RungError):
        e.set_plan_budget("linkpair", 2, actor=AGENT)
    out = e.set_plan_budget("linkpair", 2, minutes=60)
    assert out["budget"]["minutes"] == 60 and out["budget"]["minutes_used"] == 0
    out = e.start_ready("linkpair", launch=lambda proj, rid: _fake_run(e, proj, rid))
    started = {x["spec"]: x["run"] for x in out["started"]}
    assert "S-3.1" not in started and "S-1.1" in started  # verified work is not started again
    pl = out["plan"]
    assert pl["model_usage"] == "unavailable"
    if len(started) == 2:
        assert pl["budget"]["exhausted"] and "budget of 2 attempts is used" in pl["budget"]["stopped"]
    # a restart: the run in progress is Interrupted, never passed
    e.interrupt_run(started["S-1.1"], "the runner process ended")
    items = {i["spec"]: i for i in e.plan("linkpair")["items"]}
    assert items["S-1.1"]["state"] == "ready" and "was interrupted" in items["S-1.1"]["reason"]
    assert not e.check("linkpair", "S-1.1")["ok"] and items["S-3.1"]["state"] == "verified"
    e.set_plan_budget("linkpair", 5)
    again = e.start_ready("linkpair", launch=lambda proj, rid: _fake_run(e, proj, rid))
    assert [x["spec"] for x in again["started"]][:1] == ["S-1.1"]
    assert "S-3.1" not in [x["spec"] for x in again["started"]] and e.check("linkpair", "S-3.1")["ok"]
    # an elapsed-minutes budget stops the plan too
    e.set_plan_budget("linkpair", None, minutes=1)
    p = e._plan_row(e._project_row("linkpair"))
    run = again["started"][0]["run"]
    e.conn.execute("UPDATE runs SET started_at=? WHERE pk=?", (e.clock() - 120, run))
    e.conn.commit()
    p["runs"] = [run]
    e.conn.execute("UPDATE projects SET plan=? WHERE name='linkpair'", (__import__("json").dumps(p),))
    e.conn.commit()
    b = e.plan("linkpair")["budget"]
    assert b["exhausted"] and "budget of 1 minutes is used" in b["stopped"] and b["minutes_used"] >= 2
