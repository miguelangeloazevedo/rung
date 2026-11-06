"""Hardening round 2, the pane: a Rung action that finishes after the
person went to a chat leaves them in the chat."""

import chatting as C
import harness as H
from support import seed


def test_r2_a_late_rung_action_does_not_pull_the_app_off_a_chat(rung, csvtidy, page):
    e = rung.engine
    seed.seed_csvtidy(e, csvtidy)
    e.open_project("csvtidy")
    H.open_rung(page)
    page.evaluate("window.__rungNavigate('rung', {rid: 'S-2.1'})")
    page.locator(".rung [data-testid=run-tests]").first.wait_for(timeout=20000)

    # The person goes to a chat; then the view change a finished Run tests makes arrives.
    page.evaluate("location.hash = '#/'")
    H.wait_until(lambda: "rung" not in C.route(page), msg="left Rung")
    page.evaluate("window.__rungView('exec', {test: 'T-2.1a', n: 1})")
    page.wait_for_timeout(1500)
    assert "rung" not in C.route(page), C.route(page)

    # Opening Rung from outside it (the status bar chip) still moves the app, to that view.
    page.locator("[data-testid=rung-status-chip]").first.click()
    H.wait_until(lambda: "rung" in C.route(page), msg="the chip opens Rung")
