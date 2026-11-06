"""Hardening round 3, the pane: Settings marks the field a save
refused, the dock's Running lists a running test execution like the full page, and a released
specification's Latest run shows every test of that run's last attempt."""

import harness as H
import test_uc25_dock as D
from support import seed


def test_r3_pane_settings_field_dock_running_tests_latest_run(rung, csvtidy, page):
    e = rung.engine
    seed.seed_merge(e, csvtidy, upto="develop")
    H.configure_stubs(e, csvtidy, worker_delay=0.5)

    # 1. Settings: the field the route refused is marked, on its own row.
    H.open_rung(page)
    page.evaluate("window.__rungNavigate('settings')")
    row = page.locator(".rung tr[data-profile=writer]").first
    row.wait_for(timeout=20000)
    row.locator("input[name=at_once]").fill("0")
    H.button(page, "Save").click()
    bad = row.locator("input[name=at_once][aria-invalid=true]")
    H.wait_until(lambda: bad.count() == 1, msg="At once on the writer row marked invalid")
    assert page.locator(".rung input[aria-invalid=true]").count() == 1
    H.button(page, "Cancel").click()

    # 2. A test execution running on its own shows in the dock's Running, counted.
    n = e.begin_execution("csvtidy", "T-2.1a")
    try:
        D.chat_route(page)
        D.palette_dock(page, True)
        d = D.dock(page)
        test_row = d.locator(f"[data-testid=dock-test][data-exec='T-2.1a#{n}']")
        H.wait_until(lambda: test_row.count() == 1, msg=f"dock Running: {d.inner_text()[:300]}")
        assert "in progress" in test_row.inner_text()
        assert d.locator("[data-testid=dock-running] [data-testid=dock-count]").inner_text() == "1"
        D.palette_dock(page, False)
    finally:
        e.cancel_execution("csvtidy", "T-2.1a", n)

    # 3. Develop S-4.1 to green; its page's Latest run lists every test of the passing attempt.
    H.open_rung(page)
    page.evaluate("window.__rungNavigate('build', {need: 'N-2', step: 'develop'})")
    dev = page.locator(".rung [data-testid=develop-table] [data-spec=\"S-4.1\"]")
    dev.wait_for(timeout=20000)
    H.button(page, "Send", dev).click()
    H.wait_until(lambda: e.runs("csvtidy", "S-4.1") and e.runs("csvtidy", "S-4.1")[0]["status"] == "passed",
                 timeout=120, msg="run passed")
    run = e.run(e.runs("csvtidy", "S-4.1")[0]["id"])
    want = {f"{x['test']}#{x['n']}" for x in run["attempts"][-1]["executions"]}
    assert want
    page.evaluate("window.__rungNavigate('rung', {rid: 'S-4.1'})")
    shown = lambda: set(page.evaluate(
        "[...document.querySelectorAll('.rung [data-testid=spec] [data-exec]')].map(x => x.getAttribute('data-exec'))"))
    H.wait_until(lambda: shown() == want, msg=f"Latest run rows {shown()} vs {want}")
