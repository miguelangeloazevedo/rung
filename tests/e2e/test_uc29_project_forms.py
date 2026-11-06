"""UC29 Project form and Project settings in the pane: field errors that store nothing (PRJ-02), and
saving name, folder and test command (PRJ-05)."""

import os
import shutil

import harness as H
from support import seed


def field_error(page, field):
    loc = page.locator(f".rung [data-testid=field-error][data-field={field}]")
    return loc.first.inner_text() if loc.count() else ""


def test_pne05_pne06_project_form_and_settings(rung, csvtidy, page):
    e = rung.engine
    seed.seed_csvtidy(e, csvtidy)
    e.open_project("csvtidy")
    names = lambda: sorted(p["name"] for p in e.projects())
    before = names()
    locked = rung.tmp / "locked"
    locked.mkdir()
    os.chmod(locked, 0)
    try:
        # 1. New project: a missing folder, an unreadable folder, an existing name.
        H.open_rung(page)
        page.evaluate("window.__rungNavigate('project-new')")
        form = page.locator(".rung [data-testid=new-project]").first
        form.wait_for(timeout=20000)

        def attempt(name, folder, field):
            form.locator("input[name=name]").fill(name)
            form.locator("input[name=folder]").fill(folder)
            form.locator("input[name=test_command]").fill("python3 -m unittest -q")
            form.locator("[data-testid=create-project]").click()
            H.wait_until(lambda: field_error(page, field), msg=f"an error on {field}")
            assert names() == before
            return field_error(page, field)

        assert attempt("ghost", str(rung.tmp / "nowhere"), "folder")
        assert attempt("locked", str(locked), "folder")
        other = H.copy_fixture("notes-sync", rung.tmp / "other")
        assert attempt("csvtidy", str(other), "name")
        assert names() == before
    finally:
        os.chmod(locked, 0o755)

    # 2. Project settings: name, folder (a copy of the fixture), test command; Save, reload.
    copy = rung.tmp / "copy" / "csvtidy"
    shutil.copytree(csvtidy, copy)
    page.evaluate("window.__rungNavigate('project-settings')")
    sec = page.locator(".rung [data-testid=project-settings]").first
    sec.wait_for(timeout=20000)
    sec.locator("input[name=name]").fill("csvtidy-two")
    sec.locator("input[name=folder]").fill(str(copy))
    sec.locator("input[name=test_command]").fill("python3 -m unittest -q")
    sec.locator("[data-testid=save-project]").click()
    H.wait_until(lambda: "csvtidy-two" in names(), msg="renamed")
    p = e.project("csvtidy-two")
    assert p["folder"] == str(copy) and p["test_command"] == "python3 -m unittest -q"
    H.open_rung(page)  # reloads the window first
    H.wait_until(lambda: page.locator(".rung [data-testid=project-name]").first.inner_text().strip() == "csvtidy-two",
                 msg="the picker shows the new name")
    page.evaluate("window.__rungNavigate('project-settings')")
    sec = page.locator(".rung [data-testid=project-settings]").first
    sec.wait_for(timeout=20000)
    assert sec.locator("input[name=name]").input_value() == "csvtidy-two"
    assert sec.locator("input[name=folder]").input_value() == str(copy)
    assert sec.locator("input[name=test_command]").input_value() == "python3 -m unittest -q"
    hist = page.locator(".rung [data-testid=project-history]").first
    H.wait_until(lambda: all(w in hist.inner_text() for w in ("name", "folder", "test command")), msg="history")
    page.evaluate("window.__rungNavigate('projects')")
    H.wait_until(lambda: "csvtidy-two" in page.locator(".rung [data-testid=project-list]").first.inner_text(),
                 msg="the project list shows the new name")
    page.evaluate("window.__rungNavigate('project-settings')")
    page.locator(".rung [data-testid=project-settings]").first.wait_for(timeout=20000)
    H.evidence(page, 29)
