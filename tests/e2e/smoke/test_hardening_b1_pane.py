"""Hardening round 1, the pane findings: Settings saves what it
shows, an uncovered requirement reads `open` on every surface, and a person-written draft offers no
Regenerate."""

import harness as H
from rung_engine import HUMAN
from support import seed


def settings_row(page, name):
    return page.locator(f".rung tr[data-profile={name}]").first


def test_r1_pane_settings_labels_and_regenerate(rung, csvtidy, page):
    e = rung.engine
    seed.seed_csvtidy(e, csvtidy)
    e.open_project("csvtidy")
    before = e.profile("writer")

    # Settings: a value that is not a number is refused on save, not replaced by a default.
    H.open_rung(page)
    page.evaluate("window.__rungNavigate('settings')")
    settings_row(page, "writer").wait_for(timeout=20000)
    settings_row(page, "writer").locator("input[name=at_once]").fill("")
    H.button(page, "Save").click()
    err = page.locator(".rung [data-testid=error]")
    H.wait_until(lambda: err.count() > 0 and "concurrent tasks" in err.first.inner_text().lower(), msg="an error on Concurrent tasks")
    assert e.profile("writer") == before

    # An approved requirement with no specification reads `open` in the need view and on the rail.
    e.approve("csvtidy", "R-3", HUMAN)
    assert e.coverage("csvtidy", "R-3") == "open"
    page.evaluate("window.__rungNavigate('rung', {rid: 'N-1'})")
    badge = page.locator(".rung [data-status]").filter(has_text="Open")
    H.wait_until(lambda: badge.count() > 0, msg="R-3 badge")
    assert page.locator(".rung [data-rung='R-3']").first.get_attribute("data-label") == "open"

    # A person-written draft specification: Approve, but no Regenerate.
    e.write_spec("csvtidy", "R-3", seed.S31)
    page.evaluate("window.__rungNavigate('rung', {rid: 'S-3.1'})")
    page.locator(".rung [data-testid=approve]").first.wait_for(timeout=20000)
    assert page.locator(".rung [data-testid=regenerate]").count() == 0
