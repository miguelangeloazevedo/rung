"""The ladder in the dock and the rail reads the amendment B16 words (verified, checks satisfied) while
data-label keeps the stored keys (released, covered). Found recording the demo: the dock still read
"released" beside a verified specification."""

import chatting as C
import harness as H
from support import seed


def test_dock_and_rail_ladder_read_the_b16_words(rung, csvtidy, page):
    e = rung.engine
    seed.seed_csvtidy(e, csvtidy)
    e.open_project("csvtidy")
    assert H.node(e, "csvtidy", "S-1.1")["released"]
    H.open_rung(page)
    page.evaluate("location.hash = '#/'")
    H.dismiss_toasts(page)
    page.locator(C.COMPOSER).first.wait_for(timeout=30000)
    try:
        page.evaluate("window.__rungDock(true)")
        dock = page.locator("[data-testid=rung-dock]").first
        dock.wait_for(timeout=30000)
        row = dock.locator("[data-rung='S-1.1']").first
        H.wait_until(lambda: row.count() and row.get_attribute("data-label") == "released", timeout=30,
                     msg="S-1.1 in the dock ladder")
        assert row.locator(".dk-tr-label").inner_text() == "verified"
        req = dock.locator("[data-rung='R-1']").first
        assert req.get_attribute("data-label") == "covered"
        assert req.locator(".dk-tr-label").inner_text() == "checks satisfied"
        assert "released" not in dock.inner_text() and "covered" not in dock.inner_text().replace(
            "uncovered", "")
    finally:
        page.evaluate("window.__rungDock && window.__rungDock(false)")
    # The rail beside the full page: the words screen readers hear follow the same table.
    H.open_rung(page)
    page.evaluate("window.__rungNavigate('home')")
    rail = page.locator(".rung [data-rung='S-1.1'][data-label='released']").first
    rail.wait_for(timeout=30000)
    assert rail.locator(".sr-only").first.text_content() == "verified"
