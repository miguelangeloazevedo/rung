"""UC36 Suggest: three possibly missing requirements from the best placed profile, naming it and why
(BOT-06), chosen by the allocation rules (BOT-07); with no eligible profile nothing runs (BOT-08); a running
Suggest can be cancelled (BOT-09); each item has Accept and Dismiss (BOT-10); a result older than the
requirements is marked Changed since (BOT-11); the check and the done hook never read a bot action (BOT-12)."""

import time

import harness as H
from rung_engine import hook

N1 = "Clean up messy CSV exports from the bank before importing them"
R1 = "Detect the delimiter of each file"
R2 = "Normalise every date to ISO 8601"


def panel(page):
    return page.locator(".rung [data-testid=bot-suggest]").first


def ladder(e):
    return sorted((r["rid"], r["status"], r["text"]) for r in e._q("SELECT rid, status, text FROM rungs"))


def answers(e, store):
    todo = {"todos": [{"id": "1", "content": "S-1.1 done", "status": "completed"}]}
    return (e.check_all("csvtidy"), e.check("csvtidy", "S-1.1"), hook.decide("todo", todo, "uc36-session", store=store))


def stub(e, delay):
    d = dict(e.settings()["drafting"])
    d.update({"delay": delay, "fail": "", "profile": ""})
    e.set_setting("drafting", d)


def items(page):
    return panel(page).locator("[data-suggestion]")


def wait_done(page, timeout=20):
    H.wait_until(lambda: items(page).count() == 3, timeout=timeout, msg=lambda: f"three suggestions: {panel(page).inner_text()}")


def test_bot06_bot07_bot08_bot09_bot10_bot11_bot12_suggest(rung, csvtidy, page):
    e = rung.engine
    e.create_project("csvtidy", str(csvtidy), "pytest", ["coder", "reviewer", "writer", "researcher"])
    H.configure_stubs(e, csvtidy)
    stub(e, 1.0)
    # Setup: N-1's requirements were drafted by the stub as writer and approved.
    e.create_need("csvtidy", N1, requirements=[R1, R2], drafter="writer")
    e.approve_requirements("csvtidy", "N-1")
    e.write_spec("csvtidy", "R-1", "Sniff the delimiter from the first 4 KB", tags=["python", "cli", "tests"])
    e.open_project("csvtidy")
    first = answers(e, rung.store)

    # 1. Suggest on N-1: writer excluded as author of R-1, researcher disabled; the best ranked eligible runs.
    H.open_rung(page)
    page.evaluate("window.__rungNavigate('rung', {rid: 'N-1'})")
    panel(page).wait_for(timeout=20000)
    H.button(page, "Suggest", scope=panel(page)).click()
    panel(page).locator("[data-testid=bot-running]").wait_for(timeout=10000)
    wait_done(page)
    job = e._q("SELECT * FROM bot_jobs WHERE kind='suggest' ORDER BY pk DESC LIMIT 1")[0]
    choice = e.suggest_choice("csvtidy", "N-1")
    assert job["profile"] == choice["chosen"]["profile"] == choice["ranked"][0]["profile"]
    assert job["profile"] in ("coder", "reviewer")
    who = panel(page).locator("[data-testid=suggest-profile]").first.inner_text()
    assert job["profile"] in who and "ranked 1 of 2" in who and "score" in who, who
    excluded = panel(page).locator("[data-testid=suggest-excluded]").first
    assert "author of R-1" in excluded.locator("[data-profile=writer]").inner_text()
    assert "disabled" in excluded.locator("[data-profile=researcher]").inner_text()
    H.evidence(page, 36)
    assert answers(e, rung.store) == first

    # 2. Accept one, Dismiss one, the third stays proposed; nothing else in the ladder changes.
    before = ladder(e)
    texts = [items(page).nth(i).get_attribute("data-suggestion") for i in range(3)]
    H.button(page, f"Accept {texts[0]}", scope=panel(page)).click()
    H.wait_until(lambda: items(page).nth(0).get_attribute("data-mark") == "accepted", msg="accepted")
    H.button(page, f"Dismiss {texts[1]}", scope=panel(page)).click()
    H.wait_until(lambda: items(page).nth(1).get_attribute("data-mark") == "dismissed", msg="dismissed")
    assert items(page).nth(2).get_attribute("data-mark") == "open"
    after = ladder(e)
    added = [r for r in after if r not in before]
    assert len(added) == 1 and added[0][1] == "draft" and added[0][2] == texts[0], added
    assert [r for r in before if r not in after] == []
    new = e.rung("csvtidy", added[0][0])
    assert new["parent"] == "N-1"
    H.wait_until(lambda: page.locator(f".rung [data-req='{new['id']}']").count() == 1, msg="the draft under N-1")
    assert answers(e, rung.store) == first

    # 3. A requirement added while a slow Suggest runs: Changed since; an item can still be accepted.
    stub(e, 4.0)
    H.button(page, "Suggest", scope=panel(page)).click()
    panel(page).locator("[data-testid=bot-running]").wait_for(timeout=10000)
    e.add_requirement("csvtidy", "N-1", "Keep the header row")
    H.wait_until(lambda: panel(page).locator("[data-testid=bot-running]").count() == 0, timeout=20, msg="the slow Suggest ends")
    wait_done(page)
    H.wait_until(lambda: "Changed since" in panel(page).inner_text(), msg=lambda: f"Changed since: {panel(page).inner_text()}")
    third = items(page).nth(2).get_attribute("data-suggestion")
    H.button(page, f"Accept {third}", scope=panel(page)).click()
    H.wait_until(lambda: items(page).nth(2).get_attribute("data-mark") == "accepted", msg="accepted after the change")
    assert answers(e, rung.store) == first

    # 4. A slow Suggest counts toward At once while it runs, and Cancel stops it within 5 seconds.
    e.save_profiles([{"name": "researcher", "enabled": True, "at_once": 1}])
    stub(e, 30.0)
    H.button(page, "Suggest", scope=panel(page)).click()
    panel(page).locator("[data-testid=bot-running]").wait_for(timeout=10000)
    run = e._q("SELECT * FROM bot_jobs WHERE kind='suggest' ORDER BY pk DESC LIMIT 1")[0]
    assert run["profile"] == "researcher" and run["status"] == "running"
    assert {"profile": "researcher", "reason": "at capacity 1 of 1"} in e.suggest_choice("csvtidy", "N-1")["excluded"]
    t0 = time.time()
    panel(page).locator("[data-testid=bot-cancel]").first.click()
    panel(page).locator("[data-testid=bot-cancelled]").wait_for(timeout=5000)
    assert time.time() - t0 < 5
    got = e._q("SELECT status, result FROM bot_jobs WHERE pk=?", (run["pk"],))[0]
    assert got["status"] == "cancelled" and got["result"] is None
    assert items(page).count() == 0
    assert answers(e, rung.store) == first

    # 5. Every eligible profile disabled: Suggest says so, lists each profile with its reason, runs nothing.
    e.save_profiles([{"name": "researcher", "enabled": False}])
    jobs = e._q("SELECT COUNT(*) AS n FROM bot_jobs")[0]["n"]
    stub(e, 0.2)
    H.button(page, "Suggest", scope=panel(page)).click()
    none = panel(page).locator("[data-testid=suggest-none]").first
    none.wait_for(timeout=10000)
    assert "No profile can suggest" in none.inner_text()
    listed = panel(page).locator("[data-testid=suggest-excluded] [data-profile]")
    H.wait_until(lambda: listed.count() == 4, msg=lambda: f"each profile listed: {panel(page).inner_text()}")
    reasons = {listed.nth(i).get_attribute("data-profile"): listed.nth(i).inner_text() for i in range(4)}
    assert "author of R-1" in reasons["writer"] and "disabled" in reasons["researcher"]
    assert all("author of" in reasons[p] for p in ("coder", "reviewer")), reasons
    time.sleep(1)
    assert e._q("SELECT COUNT(*) AS n FROM bot_jobs")[0]["n"] == jobs

    # 6. The check and the done hook gave the same answer at every step.
    assert answers(e, rung.store) == first
