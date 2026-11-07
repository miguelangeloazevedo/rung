"""UC13 First run and the sample project."""

import harness as H


def _items(page):
    fg = page.locator(".rung [data-testid=first-green]")
    fg.wait_for()
    return {li.get_attribute("data-item"): li.get_attribute("data-done") == "1" for li in fg.locator("li").all()}


def _home(page):
    page.locator("[data-testid=rung-status-chip]").first.click()
    H.wait_view(page, "home")


def test_onb01_onb02_onb04_onb05_sample_to_first_green(rung, page):
    e = rung.engine
    H.open_rung(page)
    H.wait_view(page, "start")
    actions = 0
    # 1. Try the sample project: one project copied into Rung's data folder, its home opens.
    H.button(page, "Try the sample project").click()
    actions += 1
    H.wait_view(page, "home")
    rows = H.stored(rung.store, "SELECT name, folder FROM projects")
    assert [r["name"] for r in rows] == ["sample"]
    assert rows[0]["folder"].startswith(str(rung.store.parent / "samples"))
    kinds = H.stored(rung.store, "SELECT kind, status FROM rungs ORDER BY pk")
    assert [k["kind"] for k in kinds] == ["need", "requirement", "specification", "test"]
    assert {k["status"] for k in kinds} == {"approved"}
    assert H.stored(rung.store, "SELECT COUNT(*) AS n FROM executions")[0]["n"] == 0
    # 2. First green: five labelled items, four ticked from stored state.
    items = _items(page)
    assert list(items) == ["write_need", "approve_requirements", "approve_specifications", "approve_tests", "first_green"]
    assert list(items.values()) == [True, True, True, True, False]
    text = page.locator(".rung [data-testid=first-green]").inner_text()
    for label in ("Write a need", "Approve requirements", "Approve specifications", "Approve tests", "First green test"):
        assert label in text
    assert "4 of 5" in text
    # 4. Dismiss hides it, also after a reload; Settings shows it again.
    page.locator(".rung [data-testid=first-green-dismiss]").click()
    H.wait_until(lambda: page.locator(".rung [data-testid=first-green]").count() == 0, msg="checklist hidden")
    H.open_rung(page)
    H.wait_view(page, "home")
    page.locator(".rung [data-testid=tile-needs-you]").wait_for()
    assert page.locator(".rung [data-testid=first-green]").count() == 0
    page.locator(".rung [data-testid=rail]").get_by_text("Allocation:", exact=False).first.click()
    H.wait_view(page, "settings")
    toggle = page.locator(".rung [data-testid=show-first-green]")
    H.wait_until(lambda: toggle.get_attribute("aria-checked") == "false", msg="toggle shows hidden")
    toggle.click()
    H.wait_until(lambda: toggle.get_attribute("aria-checked") == "true", msg="toggle on")
    _home(page)
    _items(page)
    # 3. Run the test from the home: it turns green and ticks First green test.
    page.locator(".rung [data-testid=rail]").get_by_text("T-1.1a", exact=False).first.click()
    actions += 1
    H.wait_view(page, "rung")
    H.button(page, "Run tests").click()
    actions += 1
    H.wait_view(page, "exec")
    ex = page.locator(".rung [data-testid=execution]")
    H.wait_until(lambda: ex.get_attribute("data-exec-status") == "pass", timeout=60, msg="sample test passes")
    assert e.first_green("sample")["done"] == 5
    _home(page)
    H.wait_until(lambda: _items(page)["first_green"], msg="First green test ticked")
    assert all(_items(page).values())
    assert "5 of 5" in page.locator(".rung [data-testid=first-green]").inner_text()
    assert actions <= 10, actions
    H.evidence(page, 13)


def test_onb03_fst02_onb06_close_start_and_empty_lists(rung, page):
    e = rung.engine
    # 5. Superseded by FST-02 (acceptance 4): the cross leaves Rung for the view the person came from,
    # creates nothing, and the start screen shows again on the next open.
    page.evaluate("location.hash = '#/'")
    H.reload(page)
    page.evaluate("location.hash = '#/artifacts'")
    H.wait_until(lambda: page.evaluate("location.hash") == "#/artifacts", msg="artifacts view")
    H.open_rung(page, fresh=False)
    H.wait_view(page, "start")
    page.locator(".rung [data-testid=start-dismiss]").click()
    H.wait_until(lambda: page.evaluate("location.hash") == "#/artifacts", msg="back where the person came from")
    assert H.stored(rung.store, "SELECT COUNT(*) AS n FROM projects")[0]["n"] == 0
    assert H.stored(rung.store, "SELECT COUNT(*) AS n FROM rungs")[0]["n"] == 0
    assert not (rung.store.parent / "samples").exists()
    H.open_rung(page)
    H.wait_view(page, "start")
    # 6. Empty lists show a label and at most one primary action.
    folder = H.copy_fixture("csvtidy", rung.work)
    e.create_project(folder=str(folder))
    e.open_project("csvtidy")
    H.open_rung(page)
    H.wait_view(page, "home")
    empty = page.locator(".rung [data-testid=empty-project]")
    empty.wait_for()
    assert "No needs yet" in empty.inner_text()
    assert empty.locator("button.bg-needs").count() == 1
    e.create_need("csvtidy", "Clean a messy CSV export without opening a spreadsheet")
    e.approve("csvtidy", "N-1")
    H.open_rung(page)
    H.wait_view(page, "home")
    main = H.main_area(page)
    H.wait_until(lambda: "Nothing needs you" in main.inner_text(), msg="Needs you empty label")
    assert "Nothing running" in main.inner_text()
    page.locator(".rung [data-testid=rail]").get_by_text("N-1", exact=False).first.click()
    H.wait_view(page, "rung")
    H.wait_until(lambda: "No requirements" in H.main_area(page).inner_text(), msg="empty requirements label")
    page.locator(".rung [data-testid=project-name]").first.click()
    H.wait_view(page, "projects")
    page.locator(".rung input[name=search]").fill("zzz")
    H.wait_until(lambda: page.locator(".rung [data-testid=empty]").inner_text() == "No matching projects",
                 msg="empty projects label")
