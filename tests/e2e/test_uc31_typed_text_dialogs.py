"""UC31 Typed text, dialogs and results: leaving a form or editor with typed text asks (NAV-05), dialogs
ask before dropping text and hold focus (NAV-06), a refused save marks its fields (NAV-10), and every
action shows its result line as a status on the view it lands on (NAV-11)."""

import harness as H
from support import seed

TYPED = "Typed and not saved"

FORMS = [
    # (view, params, field, Cancel scope)
    ("need-new", "{}", "textarea[name=need]", None),
    ("req-new", "{need: 'N-1'}", "input[name=req-text]", "[data-testid=req-editor]"),
    ("rung", "{rid: 'R-3'}", "input[name=req-text]", "[data-testid=req-editor]"),
    ("spec-edit", "{spec: 'S-1.1'}", "input[name=spec-text]", "[data-testid=spec-editor]"),
    ("test-edit", "{test: 'T-1.1a'}", "input[name=command]", "[data-testid=test-editor]"),
]


def leave_dialog(page):
    return page.locator(".rung [data-testid=leave-dialog]")


def open_form(page, view, params, field):
    page.evaluate(f"window.__rungNavigate('home')")
    H.wait_view(page, "home")
    page.evaluate(f"window.__rungNavigate('{view}', {params})")
    H.wait_view(page, view)
    f = page.locator(f".rung {field}").first
    f.wait_for(timeout=20000)
    return f


ROUTES = {
    "rail": lambda page: page.locator(".rung [data-testid=rail]").get_by_text("N-1", exact=True).first.click(),
    "header": lambda page: page.locator(".rung [data-testid=project-name]").first.click(),
    "dock": lambda page: page.locator("[data-testid=rung-dock] [data-testid=dock-open]").first.click(),
    "chip": lambda page: page.locator("[data-testid=rung-status-chip]").first.click(),
}


def notice(page, words):
    st = page.locator(".rung [role=status][data-testid=notice]")
    H.wait_until(lambda: st.count() and words in st.first.inner_text(), msg=f"result line {words!r}: "
                 f"{st.first.inner_text() if st.count() else 'none'}")


def test_nav05_nav06_nav10_nav11_typed_text_dialogs_results(rung, csvtidy, page):
    e = rung.engine
    restore = seed.seed_failing(e, csvtidy)
    restore()
    H.open_rung(page)
    page.evaluate("window.__rungDock(true)")

    # 1. Each New form and editor: every route out asks; Keep editing keeps the text; Discard leaves.
    for view, params, field, scope in FORMS:
        for route, go in ROUTES.items():
            f = open_form(page, view, params, field)
            f.fill(TYPED)
            go(page)
            H.wait_until(lambda: leave_dialog(page).count() == 1, timeout=10,
                         msg=f"{view} by {route} asks (now {H.view(page)})")
            H.button(page, "Keep editing", leave_dialog(page)).click()
            H.wait_until(lambda: leave_dialog(page).count() == 0, msg="the question closes")
            assert H.view(page) == view, (view, route)
            assert page.locator(f".rung {field}").first.input_value() == TYPED, (view, route)
            go(page)
            H.button(page, "Discard", leave_dialog(page)).click()
            H.wait_until(lambda: H.view(page) != view or page.locator(f".rung {field}").count() == 0,
                         msg=f"{view} left by {route}")
        # Cancel leaves without asking.
        f = open_form(page, view, params, field)
        f.fill(TYPED)
        sc = page.locator(f".rung {scope}").first if scope else None
        H.button(page, "Cancel", sc).click()
        H.wait_until(lambda: H.view(page) != view or page.locator(f".rung {field}").count() == 0, msg=f"Cancel leaves {view}")
        assert leave_dialog(page).count() == 0
    # The question over a typed requirement (the evidence).
    f = open_form(page, "req-new", "{need: 'N-1'}", "input[name=req-text]")
    f.fill("Report rows that could not be parsed")
    ROUTES["header"](page)
    leave_dialog(page).wait_for(timeout=10000)
    H.evidence(page, 31)
    H.button(page, "Keep editing", leave_dialog(page)).click()
    # 5. Save moves on without asking and shows its result line: add and approve a requirement.
    H.button(page, "Approve", page.locator(".rung [data-testid=req-editor]").first).click()
    H.wait_until(lambda: H.view(page) != "req-new", msg="saved and moved on")
    assert leave_dialog(page).count() == 0
    notice(page, "R-4")

    # 2. Retire: typed reason; Escape, the cross and a click outside each ask; Cancel does not.
    page.evaluate("window.__rungNavigate('rung', {rid: 'N-1'})")
    H.wait_view(page, "rung")
    dlg = page.locator(".rung [data-testid=retire-dialog]")
    for how in ("escape", "cross", "outside"):
        opener = H.button(page, "Retire")
        opener.click()
        dlg.wait_for(timeout=10000)
        # The rest of the pane is inert while the dialog is open.
        assert page.evaluate("""() => { const d = document.querySelector('.rung [data-testid=retire-dialog]');
            const h1 = document.querySelector('.rung h1'); return !!h1 && !!h1.closest('[inert]') && !d.closest('[inert]') }"""), how
        dlg.locator("textarea, input").first.fill("No longer needed")
        if how == "escape":
            page.keyboard.press("Escape")
        elif how == "cross":
            dlg.get_by_role("button", name="Close").click()
        else:
            dlg.locator("xpath=..").click(position={"x": 4, "y": 4})
        leave_dialog(page).wait_for(timeout=10000)
        H.button(page, "Keep editing", leave_dialog(page)).click()
        assert dlg.count() == 1 and dlg.locator("textarea, input").first.input_value() == "No longer needed", how
        # Tab stays inside the dialog.
        for _ in range(6):
            page.keyboard.press("Tab")
            assert page.evaluate("!!document.activeElement.closest('[data-testid=retire-dialog]')"), how
        H.button(page, "Cancel", dlg).click()
        H.wait_until(lambda: dlg.count() == 0, msg="Cancel closes")
        assert leave_dialog(page).count() == 0
        # Focus returns to the opener.
        H.wait_until(lambda: page.evaluate("(document.activeElement.innerText || '').trim()") == "Retire",
                     msg=f"focus back on Retire: {page.evaluate('document.activeElement.outerHTML.slice(0, 120)')}")
    # 4. Focus on the backdrop: Escape still closes, asking first when the dialog holds text.
    H.button(page, "Retire").click()
    dlg.wait_for(timeout=10000)
    dlg.locator("textarea, input").first.fill("Moved to another tool")
    page.evaluate("document.activeElement.blur(); document.querySelector('.rung [data-testid=retire-dialog]').parentElement.focus()")
    page.keyboard.press("Escape")
    leave_dialog(page).wait_for(timeout=10000)
    H.button(page, "Keep editing", leave_dialog(page)).click()
    # Retire confirmed from the need page: focus on the h1 of the view it lands on; the result line shows.
    page.locator(".rung [data-testid=retire-confirm]").click()
    H.wait_until(lambda: H.stored(rung.store, "SELECT retired_at FROM rungs WHERE rid='N-1'")[0]["retired_at"],
                 msg=f"N-1 retired: {dlg.inner_text() if dlg.count() else H.view(page)}")
    notice(page, "Retired N-1")
    H.wait_until(lambda: page.evaluate("document.activeElement && document.activeElement.hasAttribute('data-page-title')"),
                 msg="focus on the h1")
    page.evaluate("window.__rungNavigate('rung', {rid: 'N-1'})")
    page.locator(".rung [data-testid=restore-need]").first.click()
    notice(page, "Restored N-1")

    # Raise defect on the failing execution: typed title; Escape asks; Cancel does not.
    page.evaluate("window.__rungNavigate('rung', {rid: 'T-2.1a'})")
    H.wait_view(page, "rung")
    H.button(page, "Raise defect").click()
    modal = page.locator(".rung [role=dialog]").last
    modal.wait_for(timeout=10000)
    modal.locator("input").first.fill("Day and month swapped")
    page.keyboard.press("Escape")
    leave_dialog(page).wait_for(timeout=10000)
    H.button(page, "Keep editing", leave_dialog(page)).click()
    modal = page.locator(".rung [role=dialog]").last
    for _ in range(8):
        page.keyboard.press("Tab")
        assert page.evaluate("!!document.activeElement.closest('[role=dialog]')")
    modal.locator("[data-testid=raise]").click()
    notice(page, "Raised")

    # 3. New project with an existing name and a missing folder: each field marked, focus on the first.
    page.evaluate("window.__rungNavigate('project-new')")
    H.wait_view(page, "project-new")
    form = page.locator(".rung [data-testid=new-project]")
    form.locator("input[name=folder]").fill(str(rung.work / "no-such-folder"))
    form.locator("input[name=name]").fill("csvtidy")
    form.locator("input[name=test_command]").fill("python3 -m unittest -q")
    H.button(page, "Create project", form).click()
    for name in ("name", "folder"):
        inp = form.locator(f"input[name={name}]")
        H.wait_until(lambda: inp.get_attribute("aria-invalid") == "true", msg=f"{name} marked invalid")
        described = inp.get_attribute("aria-describedby")
        assert described and page.locator(f"#{described}").inner_text().strip(), name
    assert page.evaluate("document.activeElement.name") == "name"
    H.button(page, "Cancel", form).click()

    # 5. The remaining result lines.
    page.evaluate("window.__rungNavigate('rung', {rid: 'T-2.1b'})")
    H.wait_view(page, "rung")
    card = page.locator(".rung [data-testid=manual-test]")
    card.wait_for(timeout=20000)
    H.button(page, "Pass", card).click()
    card.locator("textarea[name=evidence]").fill("Sorted correctly")
    H.button(page, "Record", card).click()
    notice(page, "Recorded")
    e.edit("csvtidy", "R-1", text="Detect the delimiter of every file", approve=True)
    page.evaluate("window.__rungNavigate('rung', {rid: 'S-1.1'})")
    H.wait_view(page, "rung")
    page.locator(".rung [data-testid=approve]").first.click()
    notice(page, "Approved S-1.1")
    page.evaluate("window.__rungNavigate('rung', {rid: 'R-1'})")
    H.wait_view(page, "rung")
    page.locator(".rung [data-testid=view-change]").first.click()
    H.wait_view(page, "change")
    page.locator(".rung [data-testid=revert]").first.click()
    confirm = page.locator(".rung [role=dialog]")
    if confirm.count():
        H.button(page, "Revert", confirm.last).click()
    notice(page, "Reverted")
    e.create_need("csvtidy", "Merge two exports", requirements=["Match rows by key"])
    page.evaluate("window.__rungNavigate('build', {need: 'N-2', step: 'reqs'})")
    page.locator(".rung [data-testid=requirements]").wait_for(timeout=20000)
    H.button(page, "Approve all").click()
    notice(page, "Approved the requirements of N-2")
    page.evaluate("window.__rungNavigate('project-settings')")
    H.wait_view(page, "project-settings")
    H.button(page, "Archive").click()
    dlg = page.locator(".rung [role=dialog]")
    if dlg.count():
        H.button(page, "Archive", dlg.last).click()
    notice(page, "Archived csvtidy")
    page.locator(".rung [data-testid=archived-row] [data-testid=restore]").first.click()
    notice(page, "Restored csvtidy")
    e.open_project("csvtidy")
    page.evaluate("window.__rungNavigate('project-settings')")
    H.wait_view(page, "project-settings")
    H.button(page, "Archive").click()
    if page.locator(".rung [role=dialog]").count():
        H.button(page, "Archive", page.locator(".rung [role=dialog]").last).click()
    notice(page, "Archived csvtidy")
    page.evaluate("window.__rungNavigate('projects', {tab: 'archived'})")
    H.wait_view(page, "projects")
    page.locator(".rung [data-testid=archived-row] [data-testid=delete]").first.click()
    dlg = page.locator(".rung [data-testid=delete-dialog]")
    dlg.locator("input").first.fill("csvtidy")
    dlg.locator("[data-testid=delete-confirm]").click()
    notice(page, "Deleted csvtidy")
    page.evaluate("window.__rungDock(false)")
