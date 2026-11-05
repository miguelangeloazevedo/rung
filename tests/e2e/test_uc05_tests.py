"""UC5 Tests: accept, edit, add; the step stays locked until every test is accepted."""

import harness as H
from support import seed

NEW_CMD = "pytest tests/test_merge.py::test_unmatched -q"


def row(page, tid):
    return page.locator(f".rung [data-test=\"{tid}\"]")


def test_tests_step(rung, csvtidy, page):
    e = rung.engine
    seed.seed_merge(e, csvtidy, upto="tests")
    H.open_rung(page)
    H.wait_view(page, "home")
    page.evaluate("window.__rungNavigate('build', {need: 'N-2', step: 'tests'})")
    step = page.locator(".rung [data-testid=test-step]")
    step.wait_for()
    approve = H.button(page, "Approve tests")

    # 1. Proposed tests per specification, with type and pass rule.
    for spec, tid, word in (("S-4.1", "T-4.1a", "Command test"), ("S-5.1", "T-5.1a", "Command test"), ("S-6.1", "T-6.1a", "Manual test")):
        r = page.locator(f".rung [data-spec=\"{spec}\"] [data-test=\"{tid}\"]")
        r.wait_for()
        assert word in r.inner_text()
        assert r.get_attribute("data-status") == "draft"
    assert row(page, "T-4.1a").locator("[data-testid=pass-rule]").inner_text() == "exit code 0 · timeout 120s"
    assert row(page, "T-6.1a").locator("[data-testid=pass-rule]").count() == 0

    # 2. Locked until every test is accepted.
    assert approve.is_disabled()
    H.button(page, "Accept", row(page, "T-4.1a")).click()
    H.wait_until(lambda: row(page, "T-4.1a").get_attribute("data-status") == "approved", msg="T-4.1a accepted")
    assert approve.is_disabled()

    # 3. Edit a proposed test, change its command, save; the earlier acceptance is kept.
    H.button(page, "Edit", row(page, "T-5.1a")).click()
    H.wait_view(page, "test-edit")
    cmd = page.locator(".rung input[name=command]")
    cmd.fill(NEW_CMD)
    H.button(page, "Save test").click()
    H.wait_view(page, "build")
    step.wait_for()
    H.wait_until(lambda: row(page, "T-5.1a").locator("[data-testid=test-command]").inner_text() == NEW_CMD, msg="new command")
    assert row(page, "T-4.1a").get_attribute("data-status") == "approved"
    assert e.rung("csvtidy", "T-5.1a")["command"] == NEW_CMD

    # 4. Add test: a Manual test with steps; Manual hides the command fields.
    H.button(page, "Add test", page.locator(".rung [data-spec=\"S-4.1\"]")).click()
    H.wait_view(page, "test-edit")
    page.locator(".rung input[name=command]").wait_for()
    page.locator(".rung [data-testid=test-type]").get_by_role("radio", name="Manual").click()
    page.locator(".rung textarea[name=steps]").wait_for()
    assert page.locator(".rung input[name=command]").count() == 0
    assert page.locator(".rung select[name=rule]").count() == 0
    page.locator(".rung textarea[name=steps]").fill("Merge samples/a.csv and samples/b.csv\nCheck the row count of the output")
    H.button(page, "Save test").click()
    H.wait_view(page, "build")
    H.wait_until(lambda: row(page, "T-4.1b").count() == 1, msg="manual T-4.1b")
    assert "Manual test" in row(page, "T-4.1b").inner_text()
    assert e.rung("csvtidy", "T-4.1b")["steps"] == ["Merge samples/a.csv and samples/b.csv", "Check the row count of the output"]

    # 5. An AI-judged test can be added, marked as unable to release a gate.
    H.button(page, "Add test", page.locator(".rung [data-spec=\"S-4.1\"]")).click()
    H.wait_view(page, "test-edit")
    page.locator(".rung input[name=command]").wait_for()
    page.locator(".rung [data-testid=test-type]").get_by_role("radio", name="AI judged").click()
    assert page.locator(".rung [data-testid=no-gate]").inner_text() == "Cannot release a gate"
    page.locator(".rung input[name=text]").fill("The merge report is readable")
    page.locator(".rung input[name=command]").fill("python -m csvtidy --help")
    H.button(page, "Save test").click()
    H.wait_view(page, "build")
    H.wait_until(lambda: row(page, "T-4.1c").count() == 1, msg="AI judged T-4.1c")
    assert "AI judged test" in row(page, "T-4.1c").inner_text()
    assert row(page, "T-4.1c").locator("[data-testid=no-gate]").inner_text() == "Cannot release a gate"
    assert e.rung("csvtidy", "T-4.1c")["releases_gate"] is False

    # 6. Accept the rest; Approve tests opens Develop.
    for tid in ("T-5.1a", "T-6.1a", "T-4.1b", "T-4.1c"):
        assert approve.is_disabled()
        H.button(page, "Accept", row(page, tid)).click()
        H.wait_until(lambda: row(page, tid).get_attribute("data-status") == "approved", msg=f"{tid} accepted")
    H.wait_until(lambda: approve.is_enabled(), msg="Approve tests enabled")
    approve.click()
    page.locator(".rung [data-testid=develop-table]").wait_for()
    assert e.flow("csvtidy", "N-2")["steps"]["tests"]["done"]
    H.evidence(page, 5)
