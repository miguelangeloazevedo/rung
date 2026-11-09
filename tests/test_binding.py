"""The dock leads with the focused chat's task (decisions Round 24, B18): what the chat holds, or not bound;
a person binds a chat only by confirming, through the same claim rules."""

from rung_engine.api import handle


def test_dok02_an_unknown_chat_is_not_bound(seeded):
    assert seeded.chat_binding("sess-x") == {"session": "sess-x", "bound": False, "tasks": []}
    assert seeded.chat_binding("")["bound"] is False


def test_dok01_dok03_bind_opens_one_claim_for_that_chat_and_profile(seeded, svc):
    e = seeded
    st, out = handle(svc, "POST", "/projects/csvtidy/rungs/S-2.1/bind", {"session": "", "agent": "coder"})
    assert st == 400 and not e.claims("csvtidy")
    st, out = handle(svc, "POST", "/projects/csvtidy/rungs/S-2.1/bind", {"session": "sess-1", "agent": ""})
    assert st == 400 and not e.claims("csvtidy")
    st, out = handle(svc, "POST", "/projects/csvtidy/rungs/S-2.1/bind",
                     {"session": "sess-1", "chat": "Dates chat", "agent": "coder"})
    assert st == 200, out
    [c] = e.claims("csvtidy")
    assert (c["session"], c["chat"], c["profile"], c["spec"]) == ("sess-1", "Dates chat", "coder", "S-2.1")
    st, b = handle(svc, "GET", "/sessions/sess-1/binding")
    assert st == 200 and b["bound"]
    [t] = b["tasks"]
    v = e.verification("csvtidy", "S-2.1")
    assert t["spec"] == "S-2.1" and t["outcome"] == e.rung("csvtidy", "S-2.1")["text"]
    assert t["verification"] == v["verification"] and t["next_action"] == v["next_action"]
    # Another chat cannot take it: the claim rules are the agent's own.
    st, out = handle(svc, "POST", "/projects/csvtidy/rungs/S-2.1/bind", {"session": "sess-2", "agent": "coder"})
    assert st == 409 and "held by Dates chat" in out["detail"]


def test_dok04_a_failing_check_is_the_blocker(seeded, csv_folder):
    from support import seed
    e = seeded
    e.claim("csvtidy", "S-2.1", "sess-1", "Dates chat", "coder")
    restore = seed.break_dates(csv_folder)
    try:
        e.run_test("csvtidy", "T-2.1a", carried_by="coder")
    finally:
        restore()
    [t] = e.chat_binding("sess-1")["tasks"]
    assert t["verification"] == "failed" and not t["verified"] and "T-2.1a" in t["blocker"]["text"]
