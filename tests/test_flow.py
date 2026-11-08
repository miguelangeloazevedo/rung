import pytest

from rung_engine import Actor, HUMAN, RungError

NEED = "Merge two CSV exports by a shared key"


def _new_need(svc, project="csvtidy"):
    texts = svc.suggest_requirements(project, NEED)
    assert texts == ["Match rows by a chosen key column", "Report keys found in only one file",
                     "Keep the first file\'s column order"]
    need = svc.engine.create_need(project, NEED, HUMAN, requirements=texts[:2])
    return need, texts


def test_build_flow_locks_and_gates(seeded, svc):
    e = seeded
    need, texts = _new_need(svc)
    assert need["id"] == "N-2" and need["status"] == "approved"
    f = e.flow("csvtidy", "N-2")
    assert f["current"] == "requirements"
    assert not f["steps"]["specifications"]["available"]
    # the dismissed suggestion comes back as a new requirement
    r6 = e.add_requirement("csvtidy", "N-2", texts[2])
    assert [r["id"] for r in (e.rung("csvtidy", "R-4"), e.rung("csvtidy", "R-5"), r6)] == ["R-4", "R-5", "R-6"]
    # skipping ahead through the API is refused
    with pytest.raises(RungError) as ex:
        svc.set_authoring("csvtidy", "R-4", "ai")
    assert ex.value.code == "locked"
    with pytest.raises(RungError):
        e.approve_tests("csvtidy", "N-2")
    e.edit("csvtidy", "R-5", text="Report keys found in only one of the files", approve=True)
    assert e.rung("csvtidy", "R-5")["status"] == "approved"
    assert not e.flow("csvtidy", "N-2")["steps"]["specifications"]["available"]
    assert e.approve_requirements("csvtidy", "N-2") == ["R-4", "R-6"]
    reqs = [e.rung("csvtidy", r) for r in ("R-4", "R-5", "R-6")]
    assert all(r["status"] == "approved" and r["parent"] == "N-2" for r in reqs)
    assert reqs[1]["text"] == "Report keys found in only one of the files"
    assert e.flow("csvtidy", "N-2")["steps"]["specifications"]["available"]


def _specs_step(svc):
    e = svc.engine
    need, texts = _new_need(svc)
    e.add_requirement("csvtidy", "N-2", texts[2])
    e.approve_requirements("csvtidy", "N-2")
    return e


def test_specifications_ai_and_human(seeded, svc):
    e = _specs_step(svc)
    e.set_setting("drafting", {"kind": "stub", "delay": 0.3})
    s4 = svc.set_authoring("csvtidy", "R-4", "ai")
    s5 = svc.set_authoring("csvtidy", "R-5", "ai")
    assert s4["id"] == "S-4.1" and s4["draft_state"] == "drafting"
    assert svc.set_authoring("csvtidy", "R-6", "human") is None
    st = e.flow("csvtidy", "N-2")["steps"]["specifications"]
    assert not st["can_approve"] and "drafting" in st["blocked_by"]
    with pytest.raises(RungError):
        e.approve_drafted("csvtidy", "N-2")
    svc.wait_idle()
    assert e.rung("csvtidy", "S-4.1")["draft_state"] == "drafted"
    assert e.rung("csvtidy", "S-4.1")["text"] == "Join on --key with a hash map"
    assert e.rung("csvtidy", "S-5.1")["text"] == "Print unmatched keys to stderr"
    st = e.flow("csvtidy", "N-2")["steps"]["specifications"]
    assert not st["can_approve"] and "R-6" in st["blocked_by"]
    sugg = svc.support("csvtidy", "R-6")
    assert "second file" in sugg
    e.write_spec("csvtidy", "R-6", "Preserve column order from the first file", detail=sugg)
    assert e.approve_drafted("csvtidy", "N-2") == ["S-4.1", "S-5.1", "S-6.1"]
    assert e.flow("csvtidy", "N-2")["current"] == "tests"
    assert e.rung("csvtidy", "S-4.1")["author"]["kind"] == "agent"
    assert e.rung("csvtidy", "S-6.1")["author"]["kind"] == "human"
    assert e.rung("csvtidy", "S-6.1")["author_role"] == "human"
    assert e.rung("csvtidy", "S-4.1")["parent"] == "R-4"


def _tests_step(svc):
    e = _specs_step(svc)
    svc.set_authoring("csvtidy", "R-4", "ai", wait=True)
    svc.set_authoring("csvtidy", "R-5", "ai", wait=True)
    e.write_spec("csvtidy", "R-6", "Preserve column order from the first file")
    e.approve_drafted("csvtidy", "N-2")
    made = svc.propose_tests("csvtidy", "N-2")
    return e, made


def test_tests_step(seeded, svc):
    e, made = _tests_step(svc)
    assert [t["id"] for t in made] == ["T-4.1a", "T-5.1a", "T-6.1a"]
    assert made[0]["command"] == "pytest tests/test_merge.py::test_join_key"
    assert made[2]["type"] == "manual"
    st = e.flow("csvtidy", "N-2")["steps"]["tests"]
    assert not st["can_approve"]
    e.approve("csvtidy", "T-4.1a")
    e.edit_test("csvtidy", "T-5.1a", {"command": "pytest tests/test_merge.py::test_unmatched -q"})
    assert e.rung("csvtidy", "T-5.1a")["command"] == "pytest tests/test_merge.py::test_unmatched -q"
    assert e.rung("csvtidy", "T-4.1a")["status"] == "approved"
    manual = e.add_test("csvtidy", "S-4.1", {"type": "manual", "steps": ["Merge two samples", "Check row count"]})
    assert manual["type"] == "manual" and "command" not in manual
    judged = e.add_test("csvtidy", "S-4.1", {"type": "ai_judged", "command": "pytest -q", "text": "Readable merge report"})
    assert judged["releases_gate"] is False
    with pytest.raises(RungError):
        e.approve_tests("csvtidy", "N-2")
    with pytest.raises(RungError):
        e.start_run("csvtidy", "S-4.1")
    for t in ("T-5.1a", "T-6.1a", manual["id"], judged["id"]):
        e.approve("csvtidy", t)
    e.approve_tests("csvtidy", "N-2")
    assert e.flow("csvtidy", "N-2")["current"] == "develop"
    assert e.develop_available("csvtidy", "S-4.1")[0]


def test_agent_cannot_approve_or_create(seeded):
    agent = Actor("agent", "coder")
    with pytest.raises(RungError):
        seeded.approve("csvtidy", "R-3", agent)
    with pytest.raises(RungError):
        seeded.create_need("csvtidy", "x", agent)
    with pytest.raises(RungError):
        seeded.edit("csvtidy", "R-3", text="x", actor=agent)



def test_approve_drafted_drafts_tests_in_the_background(engine, csv_folder, svc, monkeypatch):
    """Approve drafted answers at once; the tests are drafted in the background (a drafting profile takes
    seconds per specification, longer than the Desktop waits). A failure shows on the flow; Retry drafts
    again in the background, and Approve tests waits while it runs."""
    import threading
    from rung_engine import api
    from rung_engine.drafting import StubDrafter
    from support import seed
    e = engine
    seed.seed_merge(e, csv_folder, upto="requirements")
    svc.set_authoring("csvtidy", "R-4", "ai", wait=True)
    svc.set_authoring("csvtidy", "R-5", "ai", wait=True)
    e.write_spec("csvtidy", "R-6", "Preserve column order from the first file")
    real = StubDrafter.propose_tests

    def boom(self, *a, **k):
        raise RuntimeError("writer did not answer within 180 s")
    monkeypatch.setattr(StubDrafter, "propose_tests", boom)
    flow = lambda: api.handle(svc, "GET", "/projects/csvtidy/needs/N-2/flow", None)[1]  # noqa: E731
    st, got = api.handle(svc, "POST", "/projects/csvtidy/needs/N-2/approve-drafted", {})
    assert st == 200 and got["proposing"]["state"] == "drafting"
    svc.wait_idle()
    assert flow()["proposing"] == {"state": "failed", "error": "writer did not answer within 180 s"}

    gate = threading.Event()
    monkeypatch.setattr(StubDrafter, "propose_tests", lambda self, *a, **k: (gate.wait(10), real(self, *a, **k))[1])
    rev0 = api.handle(svc, "GET", "/rev", None)[1]["rev"]
    st, got = api.handle(svc, "POST", "/projects/csvtidy/needs/N-2/propose-tests", {"background": True})
    assert st == 200 and got["proposing"]["state"] == "drafting"
    f = flow()
    assert f["proposing"]["state"] == "drafting" and not f["steps"]["tests"]["can_approve"]
    assert f["steps"]["tests"]["blocked_by"] == "tests are being drafted"
    assert api.handle(svc, "GET", "/rev", None)[1]["rev"] != rev0, "the pane hears about it"
    assert api.handle(svc, "POST", "/projects/csvtidy/needs/N-2/approve-tests", {})[0] == 409
    gate.set()
    svc.wait_idle()
    assert flow()["proposing"] is None
    specs = [s for r in next(n for n in e.tree("csvtidy") if n["id"] == "N-2")["children"] for s in r["children"]]
    assert specs and all(s["children"] for s in specs)
