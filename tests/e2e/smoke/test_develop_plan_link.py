"""The Develop step opens the Plan (decisions Round 27): before anything is verified Home has no milestones section,
so the Develop step is the way to the Plan; Back returns to the Develop step."""

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
