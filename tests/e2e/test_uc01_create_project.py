"""UC1 Create a project."""

import harness as H


def test_create_project(rung, page):
    folder = H.copy_fixture("csvtidy", rung.work)
    H.open_rung(page)
    # 1. With no projects, Rung opens on the new project form.
    H.wait_view(page, "project-new")
    form = page.locator(".rung [data-testid=new-project]")
    assert form.is_visible()
    # 2. Fill it in and create.
    form.locator("input[name=name]").fill("csvtidy")
    form.locator("input[name=folder]").fill(str(folder))
    form.locator("input[name=test_command]").fill("pytest")
    form.locator("input[name=profile][value=coder]").check()
    H.button(page, "Create project", form).click()
    # 3. The empty project view, its one action.
    H.wait_view(page, "home")
    empty = page.locator(".rung [data-testid=empty-project]")
    empty.wait_for(state="visible")
    assert H.button(page, "Write the first need", empty).is_visible()
    assert page.locator(".rung [data-testid=project-name]").inner_text() == "csvtidy"
    H.evidence(page, 1)
    # 4. Stored state.
    rows = H.stored(rung.store, "SELECT name, folder, test_command, profiles FROM projects")
    assert rows == [{"name": "csvtidy", "folder": str(folder), "test_command": "pytest", "profiles": '["coder"]'}]
