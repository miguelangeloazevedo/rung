"""The way to the system views (decisions Round 27): the Develop step opens the Plan, and Home's Milestones section
opens the Plan, Architecture and System report before any milestone exists; Back returns where the person was."""

import harness as H
from support import seed


def test_develop_step_opens_the_plan(rung, tmp_path, page):
    e = rung.engine
    folder = tmp_path / "linkpair"
    folder.mkdir()
    seed.seed_linkpair(e, folder)
    e.open_project("linkpair")

    H.open_rung(page)
    page.evaluate("window.__rungNavigate('build', {need: 'N-1', step: 'develop'})")
    H.wait_view(page, "build")
    btn = page.locator(".rung [data-testid=develop-plan]")
    H.wait_until(lambda: btn.count() == 1, msg=lambda: page.locator(".rung [data-rung-view]").inner_text()[:400])
    btn.click()
    H.wait_view(page, "plan")
    items = page.locator(".rung [data-testid=plan-item]")
    H.wait_until(lambda: items.count() == 2, msg=lambda: page.locator(".rung [data-rung-view]").inner_text()[:400])
    page.keyboard.press("Escape")
    H.wait_view(page, "build")
    H.wait_until(lambda: page.locator(".rung [data-testid=develop-table]").count() == 1, msg="back on the Develop step")


def test_home_opens_the_system_views_before_any_milestone(rung, tmp_path, page):
    e = rung.engine
    folder = tmp_path / "linkpair"
    folder.mkdir()
    seed.seed_linkpair(e, folder)
    e.open_project("linkpair")
    assert e.run_test("linkpair", "T-1.1a")["status"] == "pass"  # one verified specification: Done shows

    H.open_rung(page)
    for testid, view in (("open-plan", "plan"), ("open-architecture", "architecture"), ("open-report", "system-report")):
        page.evaluate("window.__rungNavigate('home')")
        H.wait_view(page, "home")
        sec = page.locator(".rung [data-testid=home-milestones]")
        H.wait_until(lambda: sec.count() == 1 and "No milestones" in sec.inner_text(), msg="Milestones section, empty")
        sec.locator(f"[data-testid={testid}]").click()
        H.wait_view(page, view)
        page.keyboard.press("Escape")
        H.wait_view(page, "home")
