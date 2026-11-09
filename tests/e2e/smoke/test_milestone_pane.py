"""Integration milestones in the pane (decisions Round 23): created from Home, the check fails across the HTTP
boundary while both specifications stay verified, the pane shows Integration failed and the failing run, and after
the repair Run checks again turns it Verified; Back returns where the person came from. Run: .venv/bin/python -m pytest -q tests/e2e/smoke"""

import harness as H
from support import seed


def test_milestone_from_home_to_verified(rung, tmp_path, page):
    e = rung.engine
    folder = tmp_path / "linkpair"
    folder.mkdir()
    seed.seed_linkpair(e, folder)
    e.open_project("linkpair")
    assert e.run_test("linkpair", "T-1.1a")["status"] == "pass"
    assert e.run_test("linkpair", "T-2.1a")["status"] == "pass"

    H.open_rung(page)
    page.evaluate("window.__rungNavigate('home')")
    H.wait_view(page, "home")
    sec = page.locator(".rung [data-testid=home-milestones]")
    H.wait_until(lambda: sec.count() == 1 and "No milestones" in sec.inner_text(), msg="Milestones section on Home")
    sec.locator("[data-testid=milestone-new]").click()
    H.wait_view(page, "milestone-new")
    form = page.locator(".rung [data-testid=milestone-form]")
    form.locator("[name=title]").fill("Share a short link")
    form.locator("[name=journey]").fill("Paste a long link, get a short one, see it on the page")
    H.wait_until(lambda: form.locator("input[name=scope]").count() == 2, msg="both specifications offered")
    form.locator("input[name=scope][value='S-1.1']").check()
    form.locator("input[name=scope][value='S-2.1']").check()
    form.locator("[name=command]").fill("pytest -q journey/test_journey.py")
    form.locator("[data-testid=save]").click()
    H.wait_view(page, "milestone")

    state = page.locator(".rung [data-testid=milestone-state]")
    H.wait_until(lambda: state.get_attribute("data-state") == "draft", msg="draft first")
    nxt = page.locator(".rung [data-testid=next-action]")
    assert nxt.inner_text() == "Approve"
    nxt.click()
    H.wait_until(lambda: state.get_attribute("data-state") == "ready", msg="ready after approval")
    assert nxt.inner_text() == "Run checks"
    nxt.click()
    H.wait_until(lambda: state.get_attribute("data-state") == "integration_failed",
                 msg=f"integration failed: {page.locator('.rung [data-testid=milestone]').inner_text()[:400]}")
    scope = page.locator(".rung [data-testid=milestone-scope]")
    assert scope.inner_text().count("Verified") == 2  # both pieces green, the system red
    assert "M-1.a failed (#1)" in page.locator(".rung [data-testid=milestone-blockers]").inner_text()

    seed.fix_linkpair(folder)
    e.accept_test_files("linkpair", "T-2.1a")
    e.run_test("linkpair", "T-1.1a")
    e.run_test("linkpair", "T-2.1a")
    H.wait_until(lambda: state.get_attribute("data-state") == "out_of_date", msg="earlier failure is out of date")
    nxt.click()
    H.wait_until(lambda: state.get_attribute("data-state") == "verified", msg="verified after the repair")
    assert page.locator(".rung [data-testid=next-action]").count() == 0
    page.locator(".rung [data-testid=export]").click()
    H.wait_until(lambda: page.locator(".rung [data-testid=export-path]").count() == 1, msg="exported")

    # Back goes where the person came from, skipping the form (Home here); Home lists the milestone.
    page.keyboard.press("Escape")
    H.wait_view(page, "home")
    H.wait_until(lambda: "Verified" in sec.inner_text() and "M-1" in sec.inner_text(), msg="Home shows it verified")
    sec.locator("[data-testid=all-milestones]").click()
    H.wait_view(page, "milestones")
    row = page.locator(".rung [data-testid=milestone-row]")
    H.wait_until(lambda: row.count() == 1 and "Verified" in row.inner_text(), msg="listed as verified")
    page.keyboard.press("Escape")
    H.wait_view(page, "home")

    # A missing id recovers (NAV-07); a typed form asks before it is left (NAV-05).
    page.evaluate("window.__rungNavigate('milestone', {mid: 'M-9'})")
    H.wait_until(lambda: page.locator(".rung [data-testid=missing]").count() == 1,
                 msg=f"missing page: {page.locator('.rung [data-rung-view]').inner_text()[:300]}")
    page.evaluate("window.__rungNavigate('milestones')")
    H.wait_view(page, "milestones")
    page.locator(".rung [data-testid=milestone-new]").click()
    H.wait_view(page, "milestone-new")
    page.locator(".rung [data-testid=milestone-form] [name=title]").fill("Half typed")
    page.keyboard.press("Escape")
    H.wait_until(lambda: page.get_by_role("button", name="Keep editing").count() == 1, msg="leave question")
    page.get_by_role("button", name="Keep editing").click()
    assert page.locator(".rung [data-testid=milestone-form] [name=title]").input_value() == "Half typed"
    page.locator(".rung [data-testid=milestone-form] [data-testid=cancel]").click()
    H.wait_view(page, "milestones")
