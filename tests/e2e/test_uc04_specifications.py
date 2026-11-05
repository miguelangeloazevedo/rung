"""UC4 Specifications: AI derives, or I write with AI support."""

import harness as H
from support import seed

S6 = "Preserve column order from the first file"
SUPPORT = "Columns from the second file follow, in their own order, after the first file's columns."


def badge(page, spec):
    loc = page.locator(f".rung [data-spec=\"{spec}\"]")
    return loc.inner_text() if loc.count() else ""


def test_specifications(rung, csvtidy, page):
    e = rung.engine
    seed.seed_merge(e, csvtidy, upto="requirements")
    H.configure_stubs(e, csvtidy, delay=2.0)
    H.open_rung(page)
    H.wait_view(page, "home")
    page.evaluate("window.__rungNavigate('build', {need: 'N-2', step: 'specs'})")
    step = page.locator(".rung [data-testid=spec-step]")
    step.wait_for()
    approve = H.button(page, "Approve drafted")

    # 1. AI derives for two requirements, I write for one.
    for r in ("R-4", "R-5"):
        page.locator(f".rung [data-req={r}] [data-testid=authoring]").get_by_role("radio", name="AI derives").click()
    page.locator(".rung [data-req=R-6] [data-testid=authoring]").get_by_role("radio", name="I write, AI supports").click()

    # 2. Drafting, then Drafted, without a reload. 3. Approve drafted is locked meanwhile.
    marker = page.evaluate("window.__rungMarker = Math.random()")
    H.wait_until(lambda: "Drafting" in badge(page, "S-4.1") and "Drafting" in badge(page, "S-5.1"), msg="Drafting shown")
    assert approve.is_disabled()
    H.wait_until(lambda: "Drafted" in badge(page, "S-4.1") and "Drafted" in badge(page, "S-5.1"), timeout=30, msg="Drafted shown")
    assert page.evaluate("window.__rungMarker") == marker, "the page reloaded"
    assert "Join on --key with a hash map" in badge(page, "S-4.1")
    # the human-written one is still missing
    assert approve.is_disabled()

    # 4. Write the third in the editor, accept the supporting suggestion.
    H.button(page, "Write", page.locator(".rung [data-req=R-6]")).click()
    H.wait_view(page, "spec-edit")
    page.locator(".rung input[name=spec-text]").fill(S6)
    support = page.locator(".rung [data-testid=support]")
    support.wait_for(timeout=15000)
    assert SUPPORT in support.inner_text()
    H.button(page, "Accept", support).click()
    assert SUPPORT in page.locator(".rung textarea[name=spec-detail]").input_value()
    H.button(page, "Save and approve").click()
    H.wait_view(page, "build")
    step.wait_for()
    H.wait_until(lambda: S6 in badge(page, "S-6.1"), msg="S-6.1 on the step")

    # 5. Approve drafted unlocks and opens the Tests step.
    H.wait_until(lambda: approve.is_enabled(), msg="Approve drafted enabled")
    approve.click()
    page.locator(".rung [data-testid=test-step]").wait_for()
    rows = H.stored(rung.store, "SELECT s.rid, s.status, s.author_kind, r.rid AS req FROM rungs s JOIN rungs r ON r.pk=s.parent_pk "
                                "WHERE s.kind='specification' AND r.rid IN ('R-4','R-5','R-6') ORDER BY s.rid")
    assert rows == [
        {"rid": "S-4.1", "status": "approved", "author_kind": "agent", "req": "R-4"},
        {"rid": "S-5.1", "status": "approved", "author_kind": "agent", "req": "R-5"},
        {"rid": "S-6.1", "status": "approved", "author_kind": "human", "req": "R-6"},
    ]
    detail = H.stored(rung.store, "SELECT detail FROM rungs WHERE rid='S-6.1'")[0]["detail"]
    assert SUPPORT in detail
    H.evidence(page, 4)
