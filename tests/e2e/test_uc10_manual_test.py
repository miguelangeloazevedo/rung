"""UC10 A manual test is released only by human approval."""

import pytest

import harness as H
from rung_engine import HUMAN, Actor, RungError
from support import seed


def test_man01_man02_man03_manual_test(rung, csvtidy, page):
    e = rung.engine
    seed.seed_csvtidy(e, csvtidy)
    e.open_project("csvtidy")
    assert H.node(e, "csvtidy", "T-2.1a")["result"] == "pass"
    # Command tests gate automatically; an unrun manual test does not hold the gate, a recorded result does.
    assert H.node(e, "csvtidy", "T-2.1b")["result"] == "not_run"
    H.open_rung(page)
    H.wait_view(page, "home")
    page.locator(".rung [data-testid=rail]").get_by_text("T-2.1b", exact=False).first.click()
    H.wait_view(page, "rung")
    card = page.locator(".rung [data-testid=manual-test]")
    card.wait_for()

    # 1. Steps, Pass and Fail, and an evidence note.
    for step in ("Run csvtidy on samples/dates.csv", "Open the output in a spreadsheet", "Sort by the date column"):
        assert step in card.inner_text()
    assert H.button(page, "Pass", card).is_visible() and H.button(page, "Fail", card).is_visible()
    assert card.locator("textarea[name=evidence]").is_visible()

    # 2. Record Fail with a note: the test shows Fail, the specification is not released.
    H.button(page, "Fail", card).click()
    card.locator("textarea[name=evidence]").fill("Dates sort as text, 01/02 before 12/01")
    H.button(page, "Record", card).click()
    H.wait_until(lambda: H.node(e, "csvtidy", "T-2.1b")["result"] == "fail", msg="fail recorded")
    H.wait_until(lambda: "Fail" in card.locator("[data-testid=crumbs]").locator("xpath=..").inner_text(), msg="Fail badge")
    assert not H.node(e, "csvtidy", "S-2.1")["released"]

    # 3. Record Pass: pending until a human approves it.
    H.button(page, "Pass", card).click()
    card.locator("textarea[name=evidence]").fill("Sorted 40 rows, all dates in order")
    H.button(page, "Record", card).click()
    pending = card.locator("[data-testid=pending]")
    pending.wait_for()
    assert "waiting for approval" in pending.inner_text()
    assert H.node(e, "csvtidy", "T-2.1b")["result"] == "pending"
    # the Fail still counts: the pending pass does not count before approval
    assert not H.node(e, "csvtidy", "S-2.1")["released"], "a recorded pass must not count before approval"
    # an agent cannot approve it
    n = e.executions("csvtidy", "T-2.1b")[0]["n"]
    with pytest.raises(RungError):
        e.approve_result("csvtidy", "T-2.1b", n, Actor("agent", "coder"))
    assert not H.node(e, "csvtidy", "S-2.1")["released"]
    H.button(page, "Approve result", card).click()
    H.wait_until(lambda: H.node(e, "csvtidy", "T-2.1b")["result"] == "pass", msg="pass counts after approval")
    assert H.node(e, "csvtidy", "S-2.1")["released"]
    H.wait_until(lambda: card.locator("[data-testid=pending]").count() == 0, msg="pending cleared")

    # 4. Stored state: both recordings with note, time and recorder.
    rows = H.stored(rung.store, "SELECT e.n, e.status, e.note, e.recorder, e.started_at, e.approved_by FROM executions e "
                                "JOIN rungs t ON t.pk=e.test_pk WHERE t.rid='T-2.1b' ORDER BY e.n")
    assert [r["status"] for r in rows] == ["fail", "pass"]
    assert rows[0]["note"] == "Dates sort as text, 01/02 before 12/01"
    assert rows[1]["note"] == "Sorted 40 rows, all dates in order"
    assert all(r["recorder"] == HUMAN.name and r["started_at"] for r in rows)
    assert rows[1]["approved_by"] == HUMAN.name
    H.evidence(page, 10)
