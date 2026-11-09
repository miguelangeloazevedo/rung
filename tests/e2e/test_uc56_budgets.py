"""UC56 Budgets and recovery (SYS-13, decisions Round 24): a plan budget of 2 attempts stops the plan once used and
says so; verified work stays verified; model usage reads unavailable when no worker reports it; a run in progress
at a restart reads Interrupted, never passed, and Start ready work then starts only the work not verified."""

import harness as H
from test_system import _fake_run, _third
from support import seed


def test_bud01_bud02_bud03_budgets_and_recovery(rung, tmp_path, page):
    e = rung.engine
    folder = tmp_path / "linkpair"
    folder.mkdir()
    seed.seed_linkpair(e, folder)
    e.open_project("linkpair")
    _third(e, folder)
    assert e.run_test("linkpair", "T-3.1a")["status"] == "pass"

    H.open_rung(page)
    page.evaluate("window.__rungNavigate('plan', {})")
    H.wait_view(page, "plan")
    items = page.locator(".rung [data-testid=plan-item]")
    H.wait_until(lambda: items.count() == 3, msg=lambda: page.locator(".rung [data-rung-view]").inner_text()[:500])

    def st(spec):
        return page.locator(f".rung [data-testid=plan-item][data-spec='{spec}']").get_attribute("data-state")

    assert st("S-3.1") == "verified"
    page.locator(".rung input[name=budget]").fill("2")
    page.locator(".rung input[name=budget_minutes]").fill("60")
    page.locator(".rung [data-testid=save-budget]").click()
    line = page.locator(".rung [data-testid=budget-line]")
    H.wait_until(lambda: "0 of 2 attempts used" in line.inner_text(), msg=lambda: line.inner_text())
    assert "0 of 60 minutes used" in line.inner_text()
    assert "Model usage unavailable" in line.inner_text()

    # two attempts start (the plan's runs are faked as in progress), then the budget is used
    out = e.start_ready("linkpair", launch=lambda proj, rid: _fake_run(e, proj, rid))
    started = {x["spec"]: x["run"] for x in out["started"]}
    assert "S-3.1" not in started and "S-1.1" in started
    ex = page.locator(".rung [data-testid=budget-exhausted]")
    H.wait_until(lambda: ex.count() == 1, msg=lambda: line.inner_text())
    assert "budget of 2 attempts is used" in ex.inner_text()
    assert page.locator(".rung [data-testid=start-ready]").is_disabled()
    assert st("S-3.1") == "verified" and e.check("linkpair", "S-3.1")["ok"]
    H.evidence(page, 56)

    # a restart: the run in progress is Interrupted, never passed
    for run in started.values():
        e.interrupt_run(run, "the runner process ended")
    reason = page.locator(".rung [data-testid=plan-item][data-spec='S-1.1'] [data-testid=plan-reason]")
    H.wait_until(lambda: reason.count() == 1 and "was interrupted" in reason.inner_text(),
                 msg=lambda: page.locator(".rung [data-testid=plan-item][data-spec='S-1.1']").inner_text())
    assert not e.check("linkpair", "S-1.1")["ok"] and st("S-3.1") == "verified"

    # resuming starts only the work not verified
    page.locator(".rung input[name=budget]").fill("10")
    page.locator(".rung [data-testid=save-budget]").click()
    start = page.locator(".rung [data-testid=start-ready]")
    H.wait_until(lambda: not start.is_disabled(), msg=lambda: line.inner_text())
    start.click()
    note = page.locator(".rung [data-testid=plan-note]")
    H.wait_until(lambda: note.count() == 1 and "S-1.1" in note.inner_text(), msg="started")
    assert "S-3.1" not in note.inner_text()
    H.wait_until(lambda: all(r["status"] not in ("queued", "running") for s in ("S-1.1", "S-2.1")
                             for r in e.runs("linkpair", s)[:1]), timeout=120, msg="runs end")
    assert e.check("linkpair", "S-3.1")["ok"]
