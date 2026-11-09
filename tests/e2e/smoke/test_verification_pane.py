"""The pane reads the engine's one verification result (decisions Round 22): a pass on code that changed shows
Out of date with Run tests as the next action, Home lists it under Next with Check again, and a test whose files
changed since approval shows them with Accept changed files. Run: .venv/bin/python -m pytest -q tests/e2e/smoke"""

import harness as H
from support import seed


def test_out_of_date_next_action_and_protected_files(rung, csvtidy, page):
    e = rung.engine
    seed.seed_csvtidy(e, csvtidy, with_history=False)
    e.open_project("csvtidy")
    assert e.run_test("csvtidy", "T-2.1a")["status"] == "pass"
    assert e.check("csvtidy", "S-2.1")["ok"]
    seed.break_dates(csvtidy)  # the code changes; no ladder text does
    assert e.check("csvtidy", "S-2.1")["codes"] == ["out_of_date"]

    H.open_rung(page)
    H.wait_view(page, "home")
    nxt = page.locator(".rung [data-testid=next]")
    H.wait_until(lambda: nxt.count() == 1 and "S-2.1" in nxt.inner_text(), msg="S-2.1 under Next")
    assert "Out of date" in nxt.inner_text()
    assert page.locator(".rung [data-testid=recheck]").inner_text() == "Check again (1)"

    H.click_text(page, "S-2.1", nxt, exact=True)
    H.wait_view(page, "rung")
    ver = page.locator(".rung [data-testid=verification]")
    H.wait_until(lambda: ver.count() == 1 and ver.get_attribute("data-verification") == "out_of_date",
                 msg=f"verification out of date: {ver.inner_text()[:300] if ver.count() else 'none'}")
    assert "on code that has changed since" in ver.inner_text()
    assert ver.locator("[data-testid=next-action]").inner_text() == "Run tests"
    ver.locator("[data-testid=next-action]").click()
    H.wait_view(page, "exec")
    H.wait_until(lambda: e.executions("csvtidy", "T-2.1a")[0]["status"] == "fail", msg="rerun fails on the new code")
    assert e.check("csvtidy", "S-2.1")["codes"] == ["failed"]

    # A change to the test file a person approved: it runs, its pass counts for nothing, the file is named, a
    # person accepts it.
    (csvtidy / "tests" / "test_dates.py").write_text("def test_ambiguous_locale():\n    assert True\n")
    assert e.run_test("csvtidy", "T-2.1a")["status"] == "pass"
    assert e.check("csvtidy", "S-2.1")["codes"] == ["verification_changed"]
    page.evaluate("window.__rungNavigate('rung', { rid: 'T-2.1a' })")
    prot = page.locator(".rung [data-testid=protected]")
    H.wait_until(lambda: prot.count() == 1 and prot.locator("[data-changed='tests/test_dates.py']").count() == 1,
                 msg=f"changed test file shown: {prot.inner_text()[:300] if prot.count() else 'none'}")
    assert "pass · files changed" in page.locator(".rung [data-testid=executions]").inner_text()
    prot.locator("[data-testid=accept-files]").click()
    H.wait_until(lambda: e.protected("csvtidy", "T-2.1a")["changed"] == [], msg="change accepted")
    H.wait_until(lambda: prot.locator("[data-testid=accept-files]").count() == 0, msg="accept button gone")
