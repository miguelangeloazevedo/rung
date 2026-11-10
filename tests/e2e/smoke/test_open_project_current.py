"""Opening a project names it current at once, before /state refetches (UC18 archived the previous project when
Project settings opened inside that window)."""

import harness as H
from support import seed


def test_open_project_is_current_before_state_refetch(rung, csvtidy, page):
    e = rung.engine
    seed.seed_csvtidy(e, csvtidy)
    seed.seed_notes_sync(e, H.copy_fixture("notes-sync", rung.work))
    e.open_project("csvtidy")
    H.open_rung(page)
    H.wait_view(page, "home")
    page.evaluate("window.__rungNavigate('projects')")
    H.wait_view(page, "projects")
    # /state cannot refetch, so only the open itself can name the project current.
    page.evaluate("window.__rungRefuse(['/state'])")
    try:
        page.locator(".rung [data-testid=project-list]").get_by_text("notes-sync", exact=True).first.click()
        page.wait_for_function("window.__rungNav().view === 'home'")
        assert page.evaluate("window.__rungNav().project") == "notes-sync"
    finally:
        page.evaluate("window.__rungRefuse([])")
