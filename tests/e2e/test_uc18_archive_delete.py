"""UC18 Project archive, restore and delete."""


import harness as H
from support import seed


def tree_bytes(folder):
    return {str(p.relative_to(folder)): p.read_bytes() for p in sorted(folder.rglob("*")) if p.is_file()}


def two_projects(rung, csvtidy):
    e = rung.engine
    seed.seed_csvtidy(e, csvtidy)
    notes = H.copy_fixture("notes-sync", rung.work)
    seed.seed_notes_sync(e, notes)
    e.open_project("csvtidy")
    return notes


def test_prj06_archive_restore(rung, csvtidy, page):
    e = rung.engine
    two_projects(rung, csvtidy)
    before = e.tree("notes-sync")
    H.open_rung(page)
    H.wait_view(page, "home")
    # 1. Archive notes-sync from its project settings.
    page.evaluate("window.__rungNavigate('projects')")
    H.wait_view(page, "projects")
    page.locator(".rung [data-testid=project-list]").get_by_text("notes-sync", exact=True).first.click()
    H.wait_view(page, "home")
    page.evaluate("window.__rungNavigate('project-settings')")
    H.wait_view(page, "project-settings")
    H.button(page, "Archive").click()
    H.wait_view(page, "projects")
    archived = page.locator(".rung [data-testid=archived-list]")
    archived.wait_for()
    assert "notes-sync" in archived.inner_text()
    page.locator(".rung [data-testid=project-filter]").get_by_role("radio", name="Active").click()
    names = page.locator(".rung [data-testid=project-list] [data-testid=project-row-name]").all_inner_texts()
    assert "notes-sync" not in names and "csvtidy" in names
    # An archived project opens read only.
    page.locator(".rung [data-testid=project-filter]").get_by_role("radio", name="Archived 1").click()
    H.button(page, "Open", page.locator(".rung [data-testid=archived-row]").first).click()
    H.wait_view(page, "home")
    page.locator(".rung [data-testid=archived-bar]").wait_for()
    assert page.locator(".rung [data-testid=read-only]").is_visible()
    assert page.locator(".rung").get_by_role("button", name="New need", exact=True).count() == 0
    # 2. Restore brings it back with all its data.
    H.button(page, "Restore", page.locator(".rung [data-testid=archived-bar]")).click()
    H.wait_until(lambda: page.locator(".rung [data-testid=archived-bar]").count() == 0, msg="restored")
    assert e.tree("notes-sync") == before
    assert H.stored(rung.store, "SELECT archived_at FROM projects WHERE name='notes-sync'")[0]["archived_at"] is None
    H.evidence(page, 18)


def test_prj07_delete_keeps_the_folder(rung, csvtidy, page):
    e = rung.engine
    notes = two_projects(rung, csvtidy)
    e.open_project("notes-sync")
    files = tree_bytes(notes)
    other = e.tree("csvtidy")
    H.open_rung(page)
    H.wait_view(page, "home")
    page.evaluate("window.__rungNavigate('project-settings')")
    H.wait_view(page, "project-settings")
    # 3. Delete asks for the name; the button stays disabled until it matches.
    H.button(page, "Delete").click()
    dialog = page.locator(".rung [data-testid=delete-dialog]")
    dialog.wait_for()
    confirm = dialog.get_by_role("button", name="Delete", exact=True)
    assert confirm.is_disabled()
    dialog.locator("input[name=confirm]").fill("notes")
    assert confirm.is_disabled()
    dialog.locator("input[name=confirm]").fill("notes-sync")
    assert confirm.is_enabled()
    confirm.click()
    # 4. The last opened project is gone: the picker opens, never an error.
    H.wait_view(page, "projects")
    assert [r["name"] for r in H.stored(rung.store, "SELECT name FROM projects")] == ["csvtidy"]
    assert tree_bytes(notes) == files
    assert e.tree("csvtidy") == other
    assert "notes-sync" not in page.locator(".rung [data-testid=project-list]").inner_text()


def test_prj07_deleting_the_only_project_opens_the_start_or_picker(rung, csvtidy, page):
    e = rung.engine
    seed.seed_csvtidy(e, csvtidy)
    e.open_project("csvtidy")
    e.set_onboarding(start_dismissed=True)
    H.open_rung(page)
    H.wait_view(page, "home")
    page.evaluate("window.__rungNavigate('project-settings')")
    H.wait_view(page, "project-settings")
    H.button(page, "Delete").click()
    dialog = page.locator(".rung [data-testid=delete-dialog]")
    dialog.locator("input[name=confirm]").fill("csvtidy")
    dialog.get_by_role("button", name="Delete", exact=True).click()
    H.wait_until(lambda: H.view(page) in ("start", "project-new", "projects"), msg="start or picker")
    assert "Rung backend unavailable" not in page.locator(".rung").first.inner_text()
    assert (csvtidy / "csvtidy").is_dir()
