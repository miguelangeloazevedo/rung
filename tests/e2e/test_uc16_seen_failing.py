"""UC16 Seen failing first."""


import harness as H
from support import seed


def test_tst06_seen_failing_marker(rung, csvtidy, page):
    e = rung.engine
    seed.seed_csvtidy(e, csvtidy)
    e.open_project("csvtidy")
    released = {s: e.check("csvtidy", s)["ok"] for s in ("S-1.1", "S-2.1")}
    H.open_rung(page)
    H.wait_view(page, "home")
    # 2. T-2.1a failed twice before its first pass: Seen failing, on the test and in its execution list.
    page.locator(".rung [data-testid=rail]").get_by_text("T-2.1a", exact=False).first.click()
    H.wait_view(page, "rung")
    marks = page.locator(".rung [data-testid=seen-failing]")
    H.wait_until(lambda: marks.count() >= 2, msg="marker on the test and its execution list")
    assert {m.inner_text() for m in marks.all()} == {"Seen failing"}
    # 1. T-1.1a passed on its first execution: Not seen failing.
    page.locator(".rung [data-testid=rail]").get_by_text("T-1.1a", exact=False).first.click()
    H.wait_until(lambda: {m.inner_text() for m in marks.all()} == {"Not seen failing"}, msg="Not seen failing")
    # 3. In the read-out too, and release is unchanged.
    page.evaluate("window.__rungNavigate('readout', {need: 'N-1'})")
    H.wait_view(page, "readout")
    plan = page.locator(".rung [data-testid=readout-plan]")
    H.wait_until(lambda: "Seen failing" in plan.locator("[data-plan-test=\"T-2.1a\"]").inner_text(), msg="read-out plan")
    assert "Not seen failing" in plan.locator("[data-plan-test=\"T-1.1a\"]").inner_text()
    assert "Seen failing" in page.locator(".rung [data-testid=delivered-R-2]").inner_text()
    assert {s: e.check("csvtidy", s)["ok"] for s in ("S-1.1", "S-2.1")} == released
    H.evidence(page, 16)
