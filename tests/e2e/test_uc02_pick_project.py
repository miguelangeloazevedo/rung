"""UC2 Pick an ongoing project."""

import time

import harness as H
from support import seed


def _ago_ok(text, ts):
    return text.strip() != "" and ts is not None


def test_prj03_prj04_pick_project(rung, page):
    e = rung.engine
    seed.seed_csvtidy(e, H.copy_fixture("csvtidy", rung.work))
    seed.seed_notes_sync(e, H.copy_fixture("notes-sync", rung.work))
    e.open_project("csvtidy")
    H.open_rung(page)
    H.wait_view(page, "home")
    assert page.locator(".rung [data-testid=project-name]").inner_text() == "csvtidy"
    # 1. The header project name opens the picker.
    page.locator(".rung [data-testid=project-name]").click()
    H.wait_view(page, "projects")
    rows = page.locator(".rung [data-testid=project-row]")
    H.wait_until(lambda: rows.count() == 2, msg="two picker rows")
    # 2. Every row's numbers equal the stored state.
    for i in range(rows.count()):
        row = rows.nth(i)
        name = row.locator("[data-testid=project-row-name]").inner_text()
        t = e.tiles(name)
        stat = lambda label: row.locator(f"[data-stat='{label}']").inner_text()
        assert stat("Needs you") == f"Needs you {t['needs_you']}", name
        assert stat("Running") == f"Running {t['running']}", name
        assert stat("Stale") == f"Stale {t['stale']}", name
        assert stat("Covered") == f"Covered {t['covered']} of {t['requirements']}", name
        assert _ago_ok(stat("Last activity"), t["last_activity"])
    # 3. notes-sync opens its own home.
    rows.filter(has_text="notes-sync").first.click()
    H.wait_view(page, "home")
    H.wait_until(lambda: page.locator(".rung [data-testid=project-name]").inner_text() == "notes-sync", msg="notes-sync home")
    main = H.main_area(page)
    t = e.tiles("notes-sync")
    H.wait_until(lambda: page.locator(".rung [data-testid=tile-needs-you-value]").inner_text() == str(t["needs_you"]), msg="notes tiles")
    assert page.locator(".rung [data-testid=tile-stale-value]").inner_text() == str(t["stale"])
    assert page.locator(".rung [data-testid=tile-covered-value]").inner_text() == str(t["covered"])
    body = page.locator(".rung").first.inner_text()
    assert "csvtidy" not in body and "Clean a messy CSV export" not in body
    # 4. Reopening Rung opens the last project.
    assert e.current_project() == "notes-sync"
    H.open_rung(page)
    H.wait_view(page, "home")
    H.wait_until(lambda: page.locator(".rung [data-testid=project-name]").inner_text() == "notes-sync", msg="reopened on notes-sync")
    H.evidence(page, 2)
