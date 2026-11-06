"""UC28 Cancel from the pane: an execution (EXE-06) and a develop run (RUN-04), each recorded as
cancelled, never as pass or fail."""

import time

import harness as H
from support import seed


def test_pne03_pne04_cancel_execution_and_run(rung, csvtidy, page):
    e = rung.engine
    seed.seed_merge(e, csvtidy, upto="develop")
    H.configure_stubs(e, csvtidy, worker_delay=40)
    e.open_project("csvtidy")
    t = e.add_test("csvtidy", "S-1.1", {"type": "command", "command": "sleep 30"}, status="approved")["id"]
    counted = e.check("csvtidy", "S-1.1")

    # 1. Run it from the pane; Cancel on the execution.
    H.open_rung(page)
    page.evaluate(f"window.__rungNavigate('rung', {{rid: '{t}'}})")
    page.locator(".rung [data-testid=run-tests]").first.wait_for(timeout=20000)
    page.locator(".rung [data-testid=run-tests]").first.click()
    cancel = page.locator(".rung [data-testid=cancel]").first
    cancel.wait_for(timeout=20000)
    H.wait_until(lambda: e.executions("csvtidy", t) and e.executions("csvtidy", t)[0]["status"] == "running",
                 msg="the execution runs")
    t0 = time.time()
    cancel.click()
    H.wait_until(lambda: e.executions("csvtidy", t)[0]["status"] != "running", timeout=5, every=0.1,
                 msg="stopped within 5 seconds")
    assert time.time() - t0 < 5
    x = e.executions("csvtidy", t)[0]
    assert x["status"] == "cancelled" and x["status"] not in ("pass", "fail")
    assert not x.get("counts", False)
    assert e.check("csvtidy", "S-1.1")["ok"] == counted["ok"]
    H.wait_until(lambda: "cancelled" in page.locator(".rung [data-testid=main]").first.inner_text().lower(),
                 msg="the pane shows it cancelled")
    shot_route = page.evaluate("location.hash")

    # 2. A develop run with the slow worker stub; Cancel on the run.
    page.evaluate("window.__rungDock(true)")
    page.evaluate("window.__rungNavigate('build', {need: 'N-2', step: 'develop'})")
    row = page.locator(".rung [data-testid=develop-table] [data-spec=\"S-4.1\"]")
    row.first.wait_for(timeout=20000)
    H.button(page, "Send", row).click()
    H.wait_view(page, "run")
    run_id = e.runs("csvtidy", "S-4.1")[0]["id"]
    dock_run = page.locator("[data-testid=rung-dock] [data-testid=dock-run]")
    H.wait_until(lambda: dock_run.count() == 1, timeout=20, msg="the run in the dock")
    t0 = time.time()
    page.locator(".rung [data-testid=stop]").first.click()
    H.wait_until(lambda: e.run(run_id)["status"] not in ("queued", "running"), timeout=5, every=0.1,
                 msg="run stopped within 5 seconds")
    assert time.time() - t0 < 5 and e.run(run_id)["status"] == "cancelled", e.run(run_id)
    H.wait_until(lambda: dock_run.count() == 0, msg="it leaves Running in the dock")
    page.evaluate("window.__rungNavigate('home')")
    H.wait_view(page, "home")
    H.wait_until(lambda: page.locator(".rung [data-testid=running] [data-testid=running-item]").count() == 0,
                 msg="it leaves Running on home")
    page.evaluate("window.__rungDock(false)")

    # 3. The cancelled execution.
    page.evaluate(f"window.__rungNavigate('exec', {{test: '{t}', n: {x['n']}}})")
    H.wait_until(lambda: "cancelled" in page.locator(".rung [data-testid=main]").first.inner_text().lower(),
                 msg="cancelled execution view")
    H.evidence(page, 28)
