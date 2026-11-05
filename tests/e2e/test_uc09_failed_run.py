"""UC9 A run fails: detail, run again, raise a defect."""

import json

import harness as H
from support import seed


def test_exe01_exe02_exe03_failed_run(rung, csvtidy, page):
    e = rung.engine
    seed.seed_csvtidy(e, csvtidy)
    e.open_project("csvtidy")
    # Setup on the synthetic copy: the date fix regresses again, and the test takes a few seconds,
    # so the new execution can be watched while it runs.
    dates = csvtidy / "csvtidy" / "dates.py"
    dates.write_text(dates.read_text().replace("day, month = a, b", "month, day = a, b  # swapped"))
    tfile = csvtidy / "tests" / "test_dates.py"
    tfile.write_text("import time\n" + tfile.read_text().replace(
        "def test_ambiguous_locale():\n", "def test_ambiguous_locale():\n    time.sleep(4)\n"))
    before = H.stored(rung.store, "SELECT e.n, e.status, e.exit_code, e.output, e.started_at FROM executions e "
                                  "JOIN rungs t ON t.pk=e.test_pk WHERE t.rid='T-2.1a' ORDER BY e.n")
    assert [b["status"] for b in before] == ["fail", "fail", "pass"]

    H.open_rung(page)
    H.wait_view(page, "home")
    marker = page.evaluate("window.__rungMarker = Math.random()")
    page.locator(".rung [data-testid=rail]").get_by_text("T-2.1a", exact=False).first.click()
    H.wait_view(page, "rung")
    page.locator(".rung [data-testid=command-test]").wait_for()

    # 1. A failed execution shows its log with the exit code and the failing lines.
    page.locator(".rung [data-exec=\"T-2.1a#2\"]").click()
    H.wait_view(page, "exec")
    ex = page.locator(".rung [data-testid=execution]")
    ex.wait_for()
    assert ex.get_attribute("data-exec-status") == "fail"
    assert page.locator(".rung [data-fact=\"Exit code\"]").inner_text() == "1"
    failing = page.locator(".rung [data-testid=output] .text-fail")
    assert failing.count() >= 1
    assert any("test_ambiguous_locale" in t or "assert" in t for t in failing.all_inner_texts())

    # 2. Run again: a new execution shown live, ending in a new history entry.
    H.button(page, "Run again").click()
    H.wait_until(lambda: ex.get_attribute("data-exec-status") == "running", timeout=10, msg="new execution running")
    assert "Execution #4" in page.locator(".rung").first.inner_text()
    assert page.locator(".rung [data-testid=output]").is_visible()
    H.wait_until(lambda: ex.get_attribute("data-exec-status") == "fail", timeout=60, msg="new execution ends")
    assert page.evaluate("window.__rungMarker") == marker, "the page reloaded"
    after = H.stored(rung.store, "SELECT e.n, e.status, e.exit_code, e.output, e.started_at FROM executions e "
                                 "JOIN rungs t ON t.pk=e.test_pk WHERE t.rid='T-2.1a' ORDER BY e.n")
    assert after[:3] == before
    assert after[3]["n"] == 4 and after[3]["status"] == "fail"

    # 3. Raise defect opens the form with the failing runs linked; 4. nothing is stored without Raise.
    H.button(page, "Back to test").click()
    page.locator(".rung [data-testid=command-test]").wait_for()
    H.button(page, "Raise defect").click()
    modal = page.locator(".rung [data-testid=defect-modal]")
    modal.wait_for()
    boxes = modal.locator("input[type=checkbox]")
    linked = {int(boxes.nth(i).get_attribute("data-exec")): boxes.nth(i).is_checked() for i in range(boxes.count())}
    assert linked == {1: True, 2: True, 4: True}
    H.button(page, "Cancel", modal).click()
    assert H.stored(rung.store, "SELECT COUNT(*) AS n FROM defects")[0]["n"] == 0
    H.button(page, "Raise defect").click()
    modal.wait_for()
    modal.locator("input[name=defect-title]").fill("Day-first dates swapped again under en_GB")
    assert H.stored(rung.store, "SELECT COUNT(*) AS n FROM defects")[0]["n"] == 0
    H.button(page, "Raise", modal).click()
    modal.wait_for(state="detached")
    rows = H.stored(rung.store, "SELECT d.title, d.executions, t.rid AS test, s.rid AS spec FROM defects d "
                                "JOIN rungs t ON t.pk=d.test_pk JOIN rungs s ON s.pk=d.spec_pk")
    assert len(rows) == 1
    assert rows[0]["test"] == "T-2.1a" and rows[0]["spec"] == "S-2.1"
    assert sorted(json.loads(rows[0]["executions"])) == [1, 2, 4]
    H.wait_until(lambda: page.locator(".rung [data-testid=defects]").count() == 1, msg="defect shown on the test")
    H.evidence(page, 9)
