"""UC35 Draft on New forms: `Draft` fills empty fields from the parent chain and names the profile (BOT-04);
it asks Replace or Keep before touching typed text, can be cancelled and saves nothing (BOT-05); a failing
draft shows its reason, keeps what was typed and offers Retry (BOT-13)."""

import harness as H
from support import seed


def rungs(e):
    return e._q("SELECT COUNT(*) AS n FROM rungs")[0]["n"]


def bar(page):
    return page.locator(".rung [data-testid=draft-bar]").first


def draft(page):
    H.button(page, "Draft", scope=bar(page)).click()


def drafted(page, profile="writer"):
    H.wait_until(lambda: bar(page).locator("[data-testid=drafted-by]").count()
                 and bar(page).locator("[data-testid=drafted-by]").first.inner_text() == f"Drafted by {profile}",
                 msg=f"drafted by {profile}: {bar(page).inner_text()}")


def stub(e, **kw):
    d = dict(e.settings()["drafting"])
    d.update({"profile": "writer", "delay": 0.2, "fail": ""}, **kw)
    e.set_setting("drafting", d)


def test_bot04_bot05_bot13_draft_fills_new_forms(rung, csvtidy, page):
    e = rung.engine
    seed.seed_csvtidy(e, csvtidy, with_history=False)
    H.configure_stubs(e, csvtidy)
    stub(e)
    e.open_project("csvtidy")
    before = rungs(e)
    H.open_rung(page)

    # 1. Each New form: Draft fills the empty fields and names the profile.
    page.evaluate("window.__rungNavigate('need-new')")
    H.wait_view(page, "need-new")
    draft(page)
    drafted(page)
    assert page.locator(".rung textarea[name=need]").first.input_value().strip()
    H.button(page, "Cancel").click()

    page.evaluate("window.__rungNavigate('req-new', {need: 'N-1'})")
    H.wait_view(page, "req-new")
    draft(page)
    drafted(page)
    assert page.locator(".rung input[name=req-text]").first.input_value().strip()
    assert page.locator(".rung textarea[name=req-detail]").first.input_value().strip()

    # 2. Typed text: Draft asks; Keep leaves the typed text and fills only the empty fields.
    page.locator(".rung input[name=req-text]").first.fill("Keep the header row as it is")
    page.locator(".rung textarea[name=req-detail]").first.fill("")
    draft(page)
    ask = page.locator(".rung [data-testid=draft-ask]").first
    ask.wait_for(timeout=10000)
    assert H.button(page, "Replace", scope=ask).is_visible()
    H.button(page, "Keep", scope=ask).click()
    H.wait_until(lambda: page.locator(".rung textarea[name=req-detail]").first.input_value().strip(), msg="the empty field filled")
    assert page.locator(".rung input[name=req-text]").first.input_value() == "Keep the header row as it is"
    assert rungs(e) == before
    H.button(page, "Cancel", scope=page.locator(".rung [data-testid=req-editor]").first).click()

    page.evaluate("window.__rungNavigate('test-edit', {spec: 'S-1.1'})")
    H.wait_view(page, "test-edit")
    page.locator(".rung [data-testid=draft-bar]").first.wait_for(timeout=20000)
    draft(page)
    drafted(page)
    assert page.locator(".rung input[name=command]").first.input_value().strip()
    H.button(page, "Cancel", scope=page.locator(".rung [data-testid=test-editor]").first).click()

    # 3. A slow draft: Cancel stops it and the form keeps what was typed. A failing draft shows its reason and Retry.
    stub(e, delay=8.0)
    page.evaluate("window.__rungNavigate('req-new', {need: 'N-1'})")
    H.wait_view(page, "req-new")
    page.locator(".rung input[name=req-text]").first.fill("Typed before drafting")
    draft(page)
    H.button(page, "Keep", scope=page.locator(".rung [data-testid=draft-ask]").first).click()
    bar(page).locator("[data-testid=bot-running]").wait_for(timeout=10000)
    page.locator(".rung [data-testid=draft-bar] [data-testid=bot-cancel]").first.click()
    bar(page).locator("[data-testid=bot-cancelled]").wait_for(timeout=5000)
    assert page.locator(".rung input[name=req-text]").first.input_value() == "Typed before drafting"
    assert page.locator(".rung textarea[name=req-detail]").first.input_value() == ""
    job = e._q("SELECT status FROM bot_jobs ORDER BY pk DESC LIMIT 1")[0]
    assert job["status"] == "cancelled"
    stub(e, delay=0.1, fail="writer did not answer within 120 s")
    draft(page)
    H.button(page, "Keep", scope=page.locator(".rung [data-testid=draft-ask]").first).click()
    failure = bar(page).locator("[data-testid=bot-failure]").first
    failure.wait_for(timeout=10000)
    assert "writer did not answer within 120 s" in failure.inner_text()
    assert H.button(page, "Retry", scope=bar(page)).is_visible()
    assert page.locator(".rung input[name=req-text]").first.input_value() == "Typed before drafting"
    stub(e, delay=0.1)
    H.button(page, "Retry", scope=bar(page)).click()
    drafted(page)
    assert page.locator(".rung input[name=req-text]").first.input_value() == "Typed before drafting"
    assert rungs(e) == before
    H.button(page, "Cancel", scope=page.locator(".rung [data-testid=req-editor]").first).click()

    # 4. A drafted New specification with its profile (the evidence).
    e.approve_requirements("csvtidy", "N-1")
    page.evaluate("window.__rungNavigate('spec-edit', {req: 'R-3'})")
    H.wait_view(page, "spec-edit")
    page.locator(".rung [data-testid=draft-bar]").first.wait_for(timeout=20000)
    draft(page)
    drafted(page)
    assert page.locator(".rung input[name=spec-text]").first.input_value().strip()
    assert rungs(e) == before
    H.evidence(page, 35)
