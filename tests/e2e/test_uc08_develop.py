"""UC8 Develop until green: supervised attempts, live, and coverage."""

import harness as H
from support import seed


def test_develop_until_green(rung, csvtidy, page):
    e = rung.engine
    seed.seed_merge(e, csvtidy, upto="develop")
    H.configure_stubs(e, csvtidy, worker_delay=3.0)
    covered0 = e.tiles("csvtidy")["covered"]
    assert e.coverage("csvtidy", "R-4") != "covered"
    H.open_rung(page)
    H.wait_view(page, "home")
    marker = page.evaluate("window.__rungMarker = Math.random()")
    page.evaluate("window.__rungNavigate('build', {need: 'N-2', step: 'develop'})")
    row = page.locator(".rung [data-testid=develop-table] [data-spec=\"S-4.1\"]")
    row.wait_for()
    carrier = e.suggest("csvtidy", "S-4.1")["suggestions"][0]["profile"]
    max_attempts = {p["name"]: p["max_runs"] for p in e.profiles()}[carrier]

    # 1. Send starts a supervised run; the row and home show it under Running.
    H.button(page, "Send", row).click()
    H.wait_view(page, "run")
    runs = e.runs("csvtidy", "S-4.1")
    assert len(runs) == 1 and runs[0]["profile"] == carrier
    run_id = runs[0]["id"]
    assert e.run(run_id)["pid"], "the run is a supervised process of its own"
    page.evaluate("window.__rungNavigate('build', {need: 'N-2', step: 'develop'})")
    H.wait_until(lambda: H.button(page, "Running", row).is_visible(), msg="row shows Running")
    page.locator("[data-testid=rung-status-chip]").click()
    H.wait_view(page, "home")
    item = page.locator(".rung [data-testid=running] [data-testid=running-item]")
    H.wait_until(lambda: item.count() == 1 and "S-4.1" in item.first.inner_text(), msg="home Running")
    item.first.click()
    H.wait_view(page, "run")

    # 2. Attempt 1 fails, attempt 2 passes; both shown live.
    attempts = page.locator(".rung [data-testid=attempts] [data-attempt]")
    H.wait_until(lambda: "Attempt 1 · fail" in page.locator(".rung [data-testid=attempts]").inner_text(), timeout=60,
                 msg="attempt 1 failed, live")
    assert "Running" in page.locator(".rung [data-testid=run-time]").inner_text()
    H.wait_until(lambda: e.run(run_id)["status"] == "passed", timeout=90, msg="run passed")
    # 3. It ends on its own on the first pass, within the profile's max attempts.
    H.wait_until(lambda: "Finished in" in page.locator(".rung [data-testid=run-time]").inner_text(), msg="result view")
    assert page.evaluate("window.__rungMarker") == marker, "the page reloaded"
    r = e.run(run_id)
    assert [a["status"] for a in r["attempts"]] == ["fail", "pass"]
    assert len(r["attempts"]) <= max_attempts
    assert page.locator(".rung [data-testid=attempt-count]").inner_text() == f"2 of {max_attempts}"
    assert attempts.count() == 2
    assert "Attempt 2 · pass" in attempts.nth(1).inner_text()
    ex = e.executions("csvtidy", "T-4.1a")
    assert [x["status"] for x in ex] == ["pass", "fail"]

    # 5. Coverage for R-4 is Covered; the tiles updated without a reload.
    assert "Covered" in page.locator(".rung [data-testid=run-coverage]").inner_text()
    assert e.coverage("csvtidy", "R-4") == "covered"
    H.wait_until(lambda: page.locator(".rung [data-testid=tile-covered-value]").inner_text() == str(covered0 + 1),
                 msg="covered tile")
    assert page.evaluate("window.__rungMarker") == marker

    # 4. Details on attempt 1: files changed, commands, test output, what was fed to attempt 2.
    H.click_text(page, "Details", attempts.nth(0))
    H.wait_view(page, "attempt")
    files = page.locator(".rung [data-testid=files-changed]").inner_text()
    assert "csvtidy/merge.py" in files
    a1 = r["attempts"][0]
    assert page.locator(".rung").get_by_text("pytest tests/test_merge.py::test_join_key", exact=True).count() >= 1
    out = page.locator(".rung [data-testid=test-output]").inner_text()
    assert "test_join_key" in out or "FAILED" in out or "assert" in out
    fed = page.locator(".rung [data-testid=fed-forward]").inner_text()
    assert "sent to attempt 2" in page.locator(".rung [data-testid=attempt]").inner_text().lower()
    assert "T-4.1a" in fed
    assert r["attempts"][1]["fed_in"] == a1["fed_forward"]
    H.evidence(page, 8)
