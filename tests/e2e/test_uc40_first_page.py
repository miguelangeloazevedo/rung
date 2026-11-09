"""UC40 First page and sample (decisions Round 24, U02): the start screen says what Rung does and previews three
states; the sample's Break and Repair move its one verdict Verified, Out of date, Failed, Verified with no bot, and
no other project's folder changes."""

import hashlib

import harness as H


def _tree(folder):
    return {p.relative_to(folder).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(folder.rglob("*")) if p.is_file()}


def _notice(page, words):
    st = page.locator(".rung [role=status][data-testid=notice]")
    H.wait_until(lambda: words in st.inner_text(), msg=lambda: f"notice {words!r} (now {st.inner_text()!r})")
    return st.inner_text()


def _check(page, want):
    sec = page.locator(".rung [data-testid=verification]")
    H.wait_until(lambda: sec.count() == 1, msg=lambda: page.locator(".rung").inner_text()[:500])
    page.locator(".rung [data-testid=run-tests]").first.click()
    H.wait_view(page, "exec")  # one test: the run opens its execution, then back to the specification
    page.evaluate("window.__rungNavigate('rung', {rid: 'S-1.1'})")
    H.wait_view(page, "rung")

    def state():
        return sec.get_attribute("data-verification", timeout=2000) if sec.count() else None
    try:
        H.wait_until(lambda: state() == want, timeout=60, msg=lambda: f"{want} (now {state()})")
    except AssertionError:
        page.screenshot(path="/tmp/uc40-fail.png")
        raise


def test_str01_str02_str03_first_page_and_sample(rung, csvtidy, page):
    e = rung.engine
    other = _tree(csvtidy)
    H.open_rung(page)

    # 1. The start screen: one sentence and the three-state preview.
    H.wait_view(page, "start")
    start = page.locator(".rung [data-testid=start]")
    assert "only tests passing on the code as it is now count as done" in start.locator("[data-testid=start-sentence]").inner_text()
    states = start.locator("[data-testid=start-preview] [data-state]")
    assert [states.nth(i).get_attribute("data-state") for i in range(states.count())] == ["requested", "blocked", "verified"]
    preview = start.locator("[data-testid=start-preview]").inner_text().lower()
    for word in ("requested", "blocked", "verified"):
        assert word in preview

    # 2. Try the sample, run its test: Verified. Break: no bot ran, Out of date; check again: Failed.
    e.create_project("csvtidy", str(csvtidy), "pytest", ["coder"])  # a second project, created after the start screen
    H.button(page, "Try the sample project").click()
    H.wait_view(page, "home")
    bar = page.locator(".rung [data-testid=sample-bar]")
    bar.wait_for()
    assert bar.locator("[data-testid=sample-label]").inner_text().lower() == "sample"
    page.evaluate("window.__rungNavigate('rung', {rid: 'S-1.1'})")
    H.wait_view(page, "rung")
    _check(page, "verified")

    page.evaluate("window.__rungNavigate('home')")
    H.wait_view(page, "home")
    assert bar.locator("[data-testid=sample-repair]").count() == 0
    bar.locator("[data-testid=sample-break]").click()
    assert "no bot ran" in _notice(page, "Sample broken")
    H.wait_until(lambda: bar.get_attribute("data-broken") == "true", msg="broken")
    assert H.stored(rung.store, "SELECT COUNT(*) AS n FROM runs")[0]["n"] == 0  # no bot ran
    page.evaluate("window.__rungNavigate('rung', {rid: 'S-1.1'})")
    H.wait_view(page, "rung")
    sec = page.locator(".rung [data-testid=verification]")
    H.wait_until(lambda: sec.count() == 1, msg=lambda: page.locator(".rung").inner_text()[:600])
    H.wait_until(lambda: sec.get_attribute("data-verification") == "out_of_date", msg=lambda: sec.inner_text()[:300])
    _check(page, "failed")

    # 3. Repair, check again: Verified. The other project's folder is byte for byte unchanged.
    page.evaluate("window.__rungNavigate('home')")
    H.wait_view(page, "home")
    bar.locator("[data-testid=sample-repair]").click()
    assert "no bot ran" in _notice(page, "Sample repaired")
    H.wait_until(lambda: bar.get_attribute("data-broken") == "false", msg="repaired")
    page.evaluate("window.__rungNavigate('rung', {rid: 'S-1.1'})")
    H.wait_view(page, "rung")
    _check(page, "verified")
    assert _tree(csvtidy) == other
    assert H.stored(rung.store, "SELECT COUNT(*) AS n FROM runs")[0]["n"] == 0
    assert e.verification("sample", "S-1.1")["verification"] == "verified"

    # 4. The sample home after the repair.
    page.evaluate("window.__rungNavigate('home')")
    H.wait_view(page, "home")
    bar.wait_for()
    need = page.locator(".rung [data-testid=home-need]").first
    H.wait_until(lambda: "Not complete" not in need.inner_text() and "Complete" in need.inner_text(),
                 msg=lambda: need.inner_text())
    H.evidence(page, 40)
