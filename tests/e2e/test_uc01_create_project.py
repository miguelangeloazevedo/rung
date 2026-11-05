"""UC1 Create a project."""

import harness as H


def test_onb01_prj01_create_project(rung, page):
    folder = H.copy_fixture("csvtidy", rung.work)
    H.open_rung(page)
    # 1. With no projects, Rung opens on the start screen; New project opens the form.
    H.wait_view(page, "start")
    start = page.locator(".rung [data-testid=start]")
    assert H.button(page, "Try the sample project", start).is_visible()
    assert H.button(page, "New project", start).is_visible()
    assert start.get_by_role("button", name="Dismiss").is_visible()
    H.button(page, "New project", start).click()
    H.wait_view(page, "project-new")
    form = page.locator(".rung [data-testid=new-project]")
    assert form.is_visible()
    # 2. Choose the folder: name, test command and profiles fill in and stay editable.
    form.locator("input[name=folder]").fill(str(folder))
    form.locator("input[name=folder]").blur()
    H.wait_until(lambda: form.locator("input[name=name]").input_value() == "csvtidy", msg="name filled in")
    assert form.locator("input[name=test_command]").input_value() == "pytest"
    ticked = sorted(form.locator("input[name=profile]:checked").evaluate_all("els => els.map(e => e.value)"))
    assert ticked == ["coder", "reviewer", "writer"]
    form.locator("input[name=profile][value=reviewer]").uncheck()
    form.locator("input[name=profile][value=writer]").uncheck()
    assert form.locator("input[name=name]").is_editable() and form.locator("input[name=test_command]").is_editable()
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
