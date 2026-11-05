"""UC3 Add a need, iterate requirements, then modify the need and re-approve what went stale."""

import pytest

import harness as H
from rung_engine import RungError
from support import seed

NEED = "Merge two CSV exports by a shared key"
NEED2 = "Merge two or more CSV exports by a shared key"
SUGGESTED = ["Match rows by a chosen key column", "Report keys found in only one file", "Keep the first file's column order"]
R5_EDITED = "Report keys found in only one of the two files"


def strip_steps(page):
    strip = page.locator(".rung [data-testid=build-strip]")
    steps = strip.locator("[data-step]")
    return [(steps.nth(i).get_attribute("data-step"), steps.nth(i).get_attribute("data-locked") == "1")
            for i in range(steps.count())]


def test_need_and_requirements(rung, csvtidy, page):
    e = rung.engine
    seed.seed_csvtidy(e, csvtidy)
    e.open_project("csvtidy")
    H.open_rung(page)
    H.wait_view(page, "home")

    # 1. New need opens the build flow on step Need, later steps locked.
    H.button(page, "New need").click()
    H.wait_view(page, "need-new")
    steps = strip_steps(page)
    assert [s for s, _ in steps] == ["Need", "Requirements", "Specifications", "Tests", "Develop"]
    assert [locked for _, locked in steps] == [False, True, True, True, True]
    assert " · ".join(s for s, _ in steps) == "Need · Requirements · Specifications · Tests · Develop"

    # 2. The drafting stub suggests three; accept two, dismiss one.
    page.locator(".rung textarea[name=need]").fill(NEED)
    sugg = page.locator(".rung [data-testid=suggested] [data-suggestion]")
    H.wait_until(lambda: sugg.count() == 3, timeout=15, msg="three suggestions")
    assert [sugg.nth(i).get_attribute("data-suggestion") for i in range(3)] == SUGGESTED
    for text in SUGGESTED[:2]:
        row = page.locator(f".rung [data-suggestion=\"{text}\"]")
        H.button(page, "Accept", row).click()
        H.wait_until(lambda: row.get_attribute("data-mark") == "accepted", msg="accepted mark")
    row = page.locator(f".rung [data-suggestion=\"{SUGGESTED[2]}\"]")
    H.button(page, "Dismiss", row).click()
    H.wait_until(lambda: row.get_attribute("data-mark") == "dismissed", msg="dismissed mark")
    H.button(page, "Create need").click()
    H.wait_view(page, "build")
    reqs = page.locator(".rung [data-testid=requirements] [data-req]")
    H.wait_until(lambda: reqs.count() == 2, msg="two requirements")
    assert e.rung("csvtidy", "N-2")["text"] == NEED
    # ... and add the dismissed one back with New requirement.
    H.button(page, "New requirement").click()
    H.wait_view(page, "req-new")
    page.locator(".rung input[name=req-text]").fill(SUGGESTED[2])
    H.button(page, "Approve").click()
    H.wait_view(page, "build")
    H.wait_until(lambda: reqs.count() == 3, msg="three requirements")

    # 3. Edit R-5's text in the requirement editor; Approve returns to the step with the new text.
    H.button(page, "Edit", page.locator(".rung [data-req=R-5]")).click()
    H.wait_view(page, "rung")
    page.locator(".rung [data-testid=req-editor]").wait_for()
    inp = page.locator(".rung input[name=req-text]")
    assert inp.input_value() == SUGGESTED[1]
    inp.fill(R5_EDITED)
    H.button(page, "Approve").click()
    H.wait_view(page, "build")
    H.wait_until(lambda: page.locator(".rung [data-req=R-5] [data-testid=req-text]").inner_text() == R5_EDITED,
                 msg="edited R-5 on the step")

    # 4. Specifications stays locked until Approve all; the URL and the API cannot skip it.
    assert dict(strip_steps(page))["Specifications"] is True
    page.evaluate("window.__rungNavigate('build', {need: 'N-2', step: 'specs'})")
    page.locator(".rung [data-testid=locked-step]").wait_for()
    with pytest.raises(RungError):
        e.set_authoring("csvtidy", "R-4", "ai")
    H.button(page, "Back").click()
    H.wait_until(lambda: page.locator(".rung [data-testid=requirements]").count() == 1, msg="back on Requirements")
    H.button(page, "Approve all").click()
    H.wait_until(lambda: page.locator(".rung [data-testid=spec-step]").count() == 1, msg="Specifications opened")
    assert dict(strip_steps(page))["Specifications"] is False

    # 5. Stored state.
    rows = H.stored(rung.store, "SELECT r.rid, r.text, r.status, p.rid AS parent FROM rungs r JOIN rungs p ON p.pk=r.parent_pk "
                                "WHERE r.kind='requirement' AND p.rid='N-2' ORDER BY r.num")
    assert rows == [
        {"rid": "R-4", "text": SUGGESTED[0], "status": "approved", "parent": "N-2"},
        {"rid": "R-5", "text": R5_EDITED, "status": "approved", "parent": "N-2"},
        {"rid": "R-6", "text": SUGGESTED[2], "status": "approved", "parent": "N-2"},
    ]

    # 6. Modify the need: its requirements go stale and enter Needs you.
    page.locator(".rung [data-testid=rail]").get_by_text("N-2", exact=True).first.click()
    H.wait_view(page, "rung")
    page.locator(".rung [data-testid=need-title]").click()
    page.locator(".rung input[name=need-text]").fill(NEED2)
    H.button(page, "Save and approve").click()
    H.wait_until(lambda: page.locator(".rung [data-testid=need-title]").inner_text() == NEED2, msg="need saved")
    H.wait_until(lambda: all(e.rung("csvtidy", r)["status"] == "stale" for r in ("R-4", "R-5", "R-6")), msg="stale reqs")
    for r in ("R-4", "R-5", "R-6"):
        H.wait_until(lambda: page.locator(f".rung [data-req={r}]").get_attribute("data-req") == r and
                     "Stale" in page.locator(f".rung [data-req={r}]").inner_text(), msg=f"{r} shows Stale")
    # The need's change view shows before and after and what went stale.
    page.locator(".rung [data-testid=view-change]").click()
    H.wait_view(page, "change")
    assert NEED in page.locator(".rung [data-testid=before]").inner_text()
    assert NEED2 in page.locator(".rung [data-testid=after]").inner_text().replace("\n", " ")
    stale_rows = page.locator(".rung [data-testid=now-stale] [data-stale]")
    H.wait_until(lambda: stale_rows.count() == 3, msg="three stale rows")
    # They are in Needs you, the same count in all three places.
    page.locator(".rung [data-testid=project-name]").wait_for()
    page.locator("[data-testid=rung-status-chip]").click()
    H.wait_view(page, "home")
    H.wait_until(lambda: H.needs_you_counts(page) == (3, 3, 3), msg="needs you 3 everywhere")
    # Re-approving each requirement clears it.
    for i, r in enumerate(("R-4", "R-5", "R-6")):
        item = page.locator(".rung [data-testid=needs-you-item]").filter(has_text=r).first
        H.button(page, "Approve", item).click()
        H.wait_until(lambda: H.needs_you_counts(page) == (2 - i, 2 - i, 2 - i), msg=f"needs you after {r}")
    assert all(e.rung("csvtidy", r)["status"] == "approved" for r in ("R-4", "R-5", "R-6"))
    hist = H.stored(rung.store, "SELECT v.text FROM rung_versions v JOIN rungs r ON r.pk=v.rung_pk WHERE r.rid='N-2' ORDER BY v.version")
    assert [h["text"] for h in hist][:1] == [NEED] and hist[-1]["text"] == NEED2
    ch = H.stored(rung.store, "SELECT before_text, after_text FROM changes c JOIN rungs r ON r.pk=c.rung_pk WHERE r.rid='N-2'")
    assert ch == [{"before_text": NEED, "after_text": NEED2}]
    H.evidence(page, 3)
