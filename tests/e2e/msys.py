"""Shared setup for the milestone system use cases (UC50 to UC56): the synthetic linkpair project, repaired so
every piece and the journey pass, and a milestone over both specifications."""

from support import seed

JOURNEY = "pytest -q journey/test_journey.py"


def linkpair(e, tmp_path, fixed=True):
    folder = tmp_path / "linkpair"
    folder.mkdir()
    seed.seed_linkpair(e, folder)
    if fixed:
        seed.fix_linkpair(folder)
        e.accept_test_files("linkpair", "T-2.1a")
    e.open_project("linkpair")
    rerun(e)
    return folder


def rerun(e):
    assert e.run_test("linkpair", "T-1.1a")["status"] == "pass"
    assert e.run_test("linkpair", "T-2.1a")["status"] == "pass"


def milestone(e, title="Share a short link", check=JOURNEY, scope=("S-1.1", "S-2.1")):
    m = e.create_milestone("linkpair", title, "Create a link and see it", list(scope))
    e.add_milestone_check("linkpair", m["id"], {"type": "command", "command": check})
    return m["id"]


def open_milestone(H, page, mid):
    H.open_rung(page)
    page.evaluate(f"window.__rungNavigate('milestone', {{mid: '{mid}'}})")
    H.wait_view(page, "milestone")
    state = page.locator(".rung [data-testid=milestone-state]")
    H.wait_until(lambda: state.count() == 1, msg="milestone shown")
    return state


def blockers(page):
    b = page.locator(".rung [data-testid=milestone-blockers]")
    return b.inner_text() if b.count() else ""


def codes(page):
    return page.eval_on_selector_all(".rung [data-testid=milestone-blockers] [data-code]",
                                     "els => els.map(e => e.getAttribute('data-code'))")
