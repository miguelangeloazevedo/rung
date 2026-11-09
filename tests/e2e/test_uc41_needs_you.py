"""UC41 Needs you as a decision surface (decisions Round 24, U04): every item names its outcome, why, what changed or
failed and one recommended action; a run still retrying is the agent's; an empty list names the work left."""

import harness as H
from support import seed

VERBS = {"stale": "Review change", "proposed": "Review proposal", "approval": "Approve result",
         "error": "Repair test setup", "needs_input": "Answer the worker"}


def test_nyd01_nyd02_nyd03_nyd04_needs_you_decisions(rung, csvtidy, page):
    e = rung.engine
    seed.seed_needs_you(e, csvtidy)
    e.open_project("csvtidy")
    H.open_rung(page)
    H.wait_view(page, "home")
    ny = page.locator(".rung [data-testid=needs-you]")
    cards = ny.locator("[data-testid=needs-you-item]")
    items = e.needs_you("csvtidy")
    H.wait_until(lambda: cards.count() == len(items) == 5, msg=lambda: ny.inner_text()[:600])

    # 1. Each item: outcome, why, what, and its one recommended action with its own verb; Open stays secondary.
    verbs = []
    for i in range(cards.count()):
        c = cards.nth(i)
        assert c.locator("[data-testid=decision-outcome]").count() == 1, c.inner_text()
        assert c.locator("[data-testid=decision-why]").inner_text().strip(), c.inner_text()
        assert c.locator("[data-testid=decision-what]").inner_text().strip(), c.inner_text()
        rec = c.locator(".r-rec")
        assert rec.count() == 1, c.inner_text()
        verbs.append(rec.inner_text().strip())
    assert sorted(verbs) == sorted(VERBS[i["type"]] for i in items), verbs
    for i in items:
        assert i["outcome"]["text"] in ny.inner_text()

    # 2. A develop run retrying within its budget is not in Needs you; Home shows it as Agent still working.
    e.save_profiles([{**p, "max_runs": 3} if p["name"] == "coder" else p for p in seed.PROFILES])
    # The person ran S-2.1 again: the new run is retrying within its budget, so the agent holds it, not you.
    run = e.start_run("csvtidy", "S-2.1", profile="coder")
    e.start_running(run["id"], 0.0, 0)
    try:
        row = page.locator(".rung [data-testid=running] [data-testid=running-item]")
        H.wait_until(lambda: row.count() == 1, msg=lambda: page.locator(".rung [data-testid=running]").inner_text())
        assert row.locator("[data-testid=running-state]").inner_text() == "Agent still working"
        H.wait_until(lambda: cards.count() == 4, msg=lambda: ny.inner_text()[:400])
        assert all(i.get("run") != run["id"] and i["type"] != "needs_input" for i in e.needs_you("csvtidy"))
        H.evidence(page, 41)
    finally:
        e.interrupt_run(run["id"], "test over", attempts=("queued", "running"))

    # 3. Approve the recorded result through its action: the item leaves; chip, tile and list agree.
    ap = ny.locator("[data-testid=needs-you-item]:has([data-testid=approve-result])")
    ap.locator(".r-rec").click()
    H.wait_until(lambda: cards.count() == 3, msg=lambda: ny.inner_text()[:400])
    chip = page.locator("text=/Rung: \\d+ needs you/").first
    H.wait_until(lambda: chip.inner_text().split()[1] == "3" and e.tiles("csvtidy")["needs_you"] == 3,
                 msg=lambda: chip.inner_text())

    # 4. Every item resolved: the empty state names the unfinished work left and where.
    for i in e.needs_you("csvtidy"):
        if i["type"] == "proposed":
            e.dismiss("csvtidy", i["id"])
        elif i["type"] == "stale":
            e.approve("csvtidy", i["id"])
        elif i["type"] == "error":
            e.edit_test("csvtidy", i["id"], {"command": "true", "timeout": 30})  # the setup repaired
            e.approve("csvtidy", i["id"])
        elif i["type"] == "needs_input":
            e.answer_run("csvtidy", i["run"], "en_US")
            r2 = e.start_run("csvtidy", i["id"], profile="coder")
            e.interrupt_run(r2["id"], "test over", attempts=("queued", "running"))
    H.wait_until(lambda: e.needs_you("csvtidy") == [], msg=lambda: str(e.needs_you("csvtidy")))
    empty = ny.locator("[data-testid=nothing-needs-you]")
    H.wait_until(lambda: empty.count() == 1, msg=lambda: ny.inner_text())
    left = e.home("csvtidy")["unfinished"]
    assert left["open"] > 0
    H.wait_until(lambda: f"{left['open']} open" in empty.inner_text(), msg=lambda: empty.inner_text())
    for n in left["needs"]:
        assert empty.locator(f"[data-need='{n['id']}']").count() == 1
