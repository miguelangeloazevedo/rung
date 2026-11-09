"""Needs you as a decision surface (decisions Round 24, U04): each item names its outcome, why, what changed or
failed and one recommended verb; a run still retrying is the agent's; an empty list names the work left."""

from support import seed

VERBS = {"stale": "Review change", "proposed": "Review proposal", "approval": "Approve result",
         "error": "Repair test setup", "needs_input": "Answer the worker"}


def test_nyd01_every_item_names_outcome_why_what_and_one_verb(engine, csv_folder):
    e = engine
    seed.seed_needs_you(e, csv_folder)
    items = e.needs_you("csvtidy")
    assert {i["type"] for i in items} == set(VERBS), [i["type"] for i in items]
    for i in items:
        assert i["outcome"] and i["outcome"]["id"] and i["outcome"]["text"], i
        assert i["why"] and i["what"], i
        assert i["action"]["verb"] == VERBS[i["type"]]
    [ap] = [i for i in items if i["type"] == "approval"]
    assert ap["outcome"]["id"].startswith("R-") and "recorded pass" in ap["what"]


def test_nyd02_an_error_inside_a_live_run_is_not_yours(engine, csv_folder):
    e = engine
    seed.seed_needs_you(e, csv_folder)
    before = [i for i in e.needs_you("csvtidy") if i["type"] == "error"]
    run = e._q1("SELECT pk FROM runs ORDER BY pk DESC LIMIT 1")[0]
    t = e._q1("SELECT pk FROM rungs WHERE rid=?", (before[0]["id"],))[0]
    with e._tx() as c:
        c.execute("UPDATE runs SET status='running' WHERE pk=?", (run,))
        c.execute("UPDATE executions SET run_pk=? WHERE test_pk=? AND status='error'", (run, t))
    assert [i for i in e.needs_you("csvtidy") if i["type"] == "error"] == []


def test_nyd03_empty_needs_you_names_the_work_left(seeded):
    e = seeded
    h = e.home("csvtidy")
    assert h["unfinished"]["open"] == sum(len(n["open"]) for n in h["needs"])
    assert [n["id"] for n in h["unfinished"]["needs"]] == [n["id"] for n in h["needs"] if not n["complete"]]



def test_nyd04_recommended_actions_resolve_their_item(engine, csv_folder, svc):
    from rung_engine.api import handle
    from rung_engine.runner import build_prompt
    e = engine
    seed.seed_needs_you(e, csv_folder)
    [ni] = [i for i in e.needs_you("csvtidy") if i["type"] == "needs_input"]
    st, out = handle(svc, "POST", f"/projects/csvtidy/runs/{ni['run']}/answer", {"answer": ""})
    assert st == 400
    st, out = handle(svc, "POST", f"/projects/csvtidy/runs/{ni['run']}/answer", {"answer": "en_US unless --locale says otherwise"})
    assert st == 200, out
    svc.wait_idle() if hasattr(svc, "wait_idle") else None
    assert out["id"] != ni["run"] and out["profile"] == ni["profile"]
    assert e.run_answer("csvtidy", "S-2.1") == {"question": "Which locale is the default?",
                                                 "answer": "en_US unless --locale says otherwise", "by": "you"}
    prompt = build_prompt(e, "csvtidy", "S-2.1", 1, 3, "")
    assert "A person answered: en_US unless --locale says otherwise" in prompt
    assert not [i for i in e.needs_you("csvtidy") if i["type"] == "needs_input" and i["run"] == ni["run"]]
    st, out = handle(svc, "POST", f"/projects/csvtidy/runs/{ni['run']}/answer", {"answer": "again"})
    assert st == 409  # answered once; a newer run exists

    [ap] = [i for i in e.needs_you("csvtidy") if i["type"] == "approval"]
    st, _ = handle(svc, "POST", f"/projects/csvtidy/tests/{ap['id']}/executions/{ap['n']}/approve", {})
    assert st == 200
    items = e.needs_you("csvtidy")
    assert not [i for i in items if i["type"] == "approval"]
    assert e.tiles("csvtidy")["needs_you"] == len(items) == len(e.home("csvtidy")["needs_you"])
