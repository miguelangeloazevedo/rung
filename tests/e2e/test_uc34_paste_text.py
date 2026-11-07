"""UC34 Paste text: Place names the kind, the parent and why (BOT-01); the engine checks the place and an
invalid one is not offered (BOT-02); `Open as new <kind>` opens that kind's New form under the parent,
prefilled and unsaved (BOT-03)."""

import json

import harness as H
from support import seed

TEXT_A = "Accept a two-digit year only with --century"
TEXT_B = "Write the cleaned rows as a JSON array"


def rungs(e):
    return e._q("SELECT COUNT(*) AS n FROM rungs")[0]["n"]


def dialog(page):
    return page.locator(".rung [data-testid=paste-dialog]").first


def paste_and_place(page, text):
    H.button(page, "Paste text").click()
    dialog(page).wait_for(timeout=10000)
    dialog(page).locator("textarea[name=paste]").fill(text)
    H.button(page, "Place", scope=dialog(page)).click()
    dialog(page).locator("[data-testid=placed]").wait_for(timeout=20000)


def test_bot01_bot02_bot03_paste_text_places_and_opens_a_new_form(rung, csvtidy, page):
    e = rung.engine
    seed.seed_csvtidy(e, csvtidy, with_history=False)
    H.configure_stubs(e, csvtidy, delay=0.3)
    stub = csvtidy / ".rung-stub" / "drafts.json"
    table = json.loads(stub.read_text())
    table["place"] = {TEXT_B: {"kind": "requirement", "parent": "N-2", "why": "It states one output the tool must give."}}
    stub.write_text(json.dumps(table))
    d = e.settings()["drafting"]
    e.set_setting("drafting", {**d, "profile": "writer"})
    e.create_need("csvtidy", "Export the cleaned file as JSON")
    e.retire_need("csvtidy", "N-2", "Out of scope")
    e.open_project("csvtidy")
    before = rungs(e)

    # 1. Place a requirement-shaped sentence on the project home.
    H.open_rung(page)
    page.evaluate("window.__rungNavigate('home')")
    H.wait_view(page, "home")
    paste_and_place(page, TEXT_A)
    placed = dialog(page).locator("[data-testid=placed-as]").first
    H.wait_until(lambda: "Requirement" in placed.inner_text() and "N-1" in placed.inner_text(), msg=f"placed: {placed.inner_text()}")
    assert "writer" in placed.inner_text()
    assert dialog(page).locator("[data-testid=placed-why]").first.inner_text().strip()
    assert TEXT_A in dialog(page).locator("[data-testid=placed-text]").first.inner_text()
    H.evidence(page, 34)
    assert rungs(e) == before
    H.button(page, "Open as new requirement", scope=dialog(page)).click()
    H.wait_view(page, "req-new")
    field = page.locator(".rung input[name=req-text]").first
    H.wait_until(lambda: field.input_value() == TEXT_A, msg="the form holds the placed text")
    assert "N-1" in page.locator(".rung [data-testid=req-editor]").first.inner_text()
    assert rungs(e) == before

    # 3. Leaving the form with its text asks first; Cancel leaves without asking and stores nothing.
    page.locator(".rung [data-testid=project-name]").first.click()
    page.locator(".rung [data-testid=leave-dialog]").first.wait_for(timeout=10000)
    H.button(page, "Keep editing").click()
    assert H.view(page) == "req-new" and field.input_value() == TEXT_A
    H.button(page, "Cancel", scope=page.locator(".rung [data-testid=req-editor]").first).click()
    H.wait_until(lambda: H.view(page) != "req-new", msg="Cancel leaves")
    assert page.locator(".rung [data-testid=leave-dialog]").count() == 0
    assert rungs(e) == before

    # 2. A place under a retired need is not offered; choose N-1, then a specification under R-1.
    page.evaluate("window.__rungNavigate('home')")
    H.wait_view(page, "home")
    paste_and_place(page, TEXT_B)
    refused = dialog(page).locator("[data-testid=place-refused]").first
    H.wait_until(lambda: refused.count() and "retired" in refused.inner_text(), msg="the retired parent is refused")
    open_btn = dialog(page).locator("[data-testid=open-as-new]").first
    assert open_btn.get_attribute("aria-disabled") == "true"
    dialog(page).locator("select[name=parent]").select_option("N-1")
    H.wait_until(lambda: open_btn.get_attribute("aria-disabled") is None, msg="N-1 is offered")
    dialog(page).locator("select[name=kind]").select_option("specification")
    dialog(page).locator("select[name=parent]").select_option("R-1")
    H.wait_until(lambda: open_btn.inner_text() == "Open as new specification" and open_btn.get_attribute("aria-disabled") is None,
                 msg=f"specification under R-1: {open_btn.inner_text()}")
    open_btn.click()
    H.wait_view(page, "spec-edit")
    spec = page.locator(".rung input[name=spec-text]").first
    H.wait_until(lambda: spec.input_value() == TEXT_B, msg="the specification form holds the text")
    assert "R-1" in page.locator(".rung [data-testid=spec-editor]").first.inner_text()
    assert rungs(e) == before
    H.button(page, "Cancel", scope=page.locator(".rung [data-testid=spec-editor]").first).click()
    H.wait_until(lambda: H.view(page) != "spec-edit", msg="Cancel leaves the specification form")

    # 3. Cancel in the dialog stores nothing.
    page.evaluate("window.__rungNavigate('home')")
    H.wait_view(page, "home")
    H.button(page, "Paste text").click()
    dialog(page).locator("textarea[name=paste]").fill(TEXT_A)
    H.button(page, "Cancel", scope=dialog(page)).click()
    H.wait_until(lambda: dialog(page).count() == 0, msg="the dialog closes")
    assert rungs(e) == before
    assert not e._q("SELECT 1 FROM bot_jobs WHERE status='running'")
