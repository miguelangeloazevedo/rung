"""Quick task views and the navigation contract (decisions Round 24): a missing task recovers, a typed card asks
before it is left, Cancel does not, Back from the card returns where the person came from.
Run: .venv/bin/python -m pytest -q tests/e2e/smoke"""

import harness as H
from support import seed


def test_quick_views_keep_the_navigation_contract(rung, csvtidy, page):
    e = rung.engine
    seed.seed_csvtidy(e, csvtidy)
    e.open_project("csvtidy")
    H.open_rung(page)
    page.evaluate("window.__rungNavigate('quick', {need: 'N-9'})")
    H.wait_until(lambda: page.locator(".rung [data-testid=missing]").count() == 1,
                 msg=lambda: page.locator(".rung [data-rung-view]").inner_text()[:300])
    page.evaluate("window.__rungNavigate('quick', {need: 'N-1'})")  # an ordinary need is not a quick task
    H.wait_until(lambda: page.locator(".rung [data-testid=missing]").count() == 1, msg="not a quick task")

    page.evaluate("window.__rungNavigate('home')")
    H.wait_view(page, "home")
    page.locator(".rung [data-testid=quick-task]").click()
    H.wait_view(page, "quick-new")
    form = page.locator(".rung [data-testid=quick-form]")
    form.locator("[name=outcome]").fill("Half typed")
    page.keyboard.press("Escape")
    H.wait_until(lambda: page.get_by_role("button", name="Keep editing").count() == 1, msg="leave question")
    page.get_by_role("button", name="Keep editing").click()
    assert form.locator("[name=outcome]").input_value() == "Half typed"
    form.locator("[data-testid=cancel]").click()
    H.wait_view(page, "home")

    page.locator(".rung [data-testid=quick-task]").click()
    H.wait_view(page, "quick-new")
    form.locator("[name=outcome]").fill("Dates sort by value")
    form.locator("[name=check-command-0]").fill("python3 -c pass")
    form.locator("[data-testid=save]").click()
    H.wait_view(page, "quick")
    page.keyboard.press("Escape")  # the form is never a return destination
    H.wait_view(page, "home")
