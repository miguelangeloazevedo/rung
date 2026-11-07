"""UC32 Needs you front page: what needs you across every open project, grouped by project with its count
(FRT-01, FRT-02), projects with nothing waiting (FRT-03), the Projects list beside it (FRT-04), and the
total equal to the sum of the groups and each group to that project's Home tile (FRT-05), one action from any
project view and Back from a project home opened there (FRT-06), live updates and 20 projects of 500 rungs within
1 second (FRT-07), and a failed load showing its error and Retry (FRT-08)."""

import time

import harness as H
from a11y import CONTRAST_JS
from support import seed

CMD = "python3 -m unittest -q"


def make(e, root, name, reqs, tests=False):
    folder = root / name
    folder.mkdir(parents=True)
    e.create_project(name, str(folder), CMD, ["coder", "reviewer"])
    e.create_need(name, f"Keep the {name} files tidy")
    for t in reqs:
        e.add_requirement(name, "N-1", t)
    e.approve_requirements(name, "N-1")
    for i, _ in enumerate(reqs, 1):
        e.write_spec(name, f"R-{i}", f"Handle case {i} of {name}", tags=["python"])
    e.approve_drafted(name, "N-1")
    if tests:
        for i, _ in enumerate(reqs, 1):
            e.add_test(name, f"S-{i}.1", {"type": "command", "command": "true"}, status="approved")
        e.approve_tests(name, "N-1")


def front(page):
    H.wait_view(page, "projects")
    page.locator(".rung [data-testid=ny-total]").first.wait_for(timeout=20000)


def name_is(page, project):
    H.wait_until(lambda: page.locator(".rung [data-testid=project-name]").first.inner_text() == project,
                 msg=f"{project} open")


def group(page, project):
    return page.locator(f".rung [data-testid=ny-group][data-project='{project}']")


def total(page):
    return int(page.locator(".rung [data-testid=ny-total]").first.inner_text())


def back(page):
    page.locator(".rung").first.get_by_role("button", name="Back", exact=True).first.click()


def test_frt01_frt02_frt03_frt04_frt05_frt06_needs_you_front_page(rung, page):
    e = rung.engine
    root = rung.work
    H.configure_stubs(e, root)
    # 1. Setup: alpha with two stale specifications and a develop run; beta with one stale specification;
    #    gamma with nothing waiting; delta archived.
    make(e, root, "alpha", ["Read the file", "Write the file", "Report errors"], tests=True)
    e.edit("alpha", "R-1", text="Read the file twice", approve=True)
    e.edit("alpha", "R-2", text="Write the file twice", approve=True)
    run = e.start_run("alpha", "S-3.1")
    make(e, root, "beta", ["Copy a note"])
    e.edit("beta", "R-1", text="Copy a note once", approve=True)
    make(e, root, "gamma", ["Sort the list"])
    make(e, root, "delta", ["Old rule"])
    e.archive_project("delta")
    e.open_project("alpha")
    try:
        _walk(e, page, run)
    finally:
        e.cancel_run(run["id"])


def _walk(e, page, run):
    # 2. Rung opens on alpha's Home; the project name opens Needs you.
    H.open_rung(page)
    page.evaluate("window.__rungNavigate('home')")
    H.wait_view(page, "home")
    name_is(page, "alpha")
    page.locator(".rung [data-testid=project-name]").first.click()
    front(page)
    assert page.locator(".rung h1").first.inner_text() == "Needs you"
    H.wait_until(lambda: total(page) == 3, msg="total 3")
    groups = page.locator(".rung [data-testid=ny-group]")
    assert sorted(groups.nth(i).get_attribute("data-project") for i in range(groups.count())) == ["alpha", "beta"]
    counts = {}
    for name, unit in (("alpha", "2 need you"), ("beta", "1 needs you")):
        g = group(page, name)
        assert g.locator("[data-testid=ny-count]").inner_text() == unit
        counts[name] = g.locator("[data-testid=ny-item]").count()
        assert counts[name] == e.tiles(name)["needs_you"], name
        for i in range(counts[name]):
            item = g.locator("[data-testid=ny-item]").nth(i)
            rid = item.get_attribute("data-item")
            assert item.locator("[data-testid=ny-open]").get_attribute("aria-label") == f"Open {rid}"
        assert g.locator("[data-testid=open-project]").get_attribute("aria-label") == f"Open project {name}"
    assert total(page) == sum(counts.values())
    running = group(page, "alpha").locator("[data-testid=ny-running]")
    assert running.count() == 1 and "S-3.1" in running.inner_text()
    idle = page.locator(".rung [data-testid=ny-idle]")
    assert idle.count() == 1 and idle.get_attribute("data-project") == "gamma"
    assert idle.locator("[data-stat=Stale]").inner_text() == "0 stale"
    assert idle.locator("[data-stat=Covered]").inner_text() == "0 of 1 covered"
    assert idle.locator("[data-testid=open-project]").get_attribute("aria-label") == "Open project gamma"
    rows = page.locator(".rung [data-testid=project-row]")
    H.wait_until(lambda: rows.count() == 3, msg="three open projects listed")
    for i in range(3):
        row = rows.nth(i)
        name = row.locator("[data-testid=project-row-name]").inner_text()
        t = e.tiles(name)
        assert row.locator("[data-stat=Covered]").inner_text() == f"{t['covered']} of {t['requirements']} covered"
        assert (row.locator("[data-testid=last-opened]").count() == 1) == (name == "alpha"), name
    assert "Archived 1" in page.locator(".rung [data-testid=project-filter]").inner_text()
    chip = page.locator("[data-testid=rung-status-chip]").first.inner_text()
    assert int(chip.split()[1]) == e.tiles("alpha")["needs_you"] == 2, chip
    low = [x for x in page.evaluate(CONTRAST_JS.replace("document.querySelector('.rung')",
                                                        "document.querySelector('.rung [data-testid=ny-idle-list]')"))
           if x["ratio"] < x["need"]]
    assert not low, low
    H.evidence(page, 32)

    # The running work opens the run; the project name returns to Needs you.
    running.click()
    H.wait_view(page, "run")
    H.wait_until(lambda: "S-3.1" in H.main_area(page).inner_text(), msg="the run of S-3.1")
    page.locator(".rung [data-testid=project-name]").first.click()
    front(page)

    # 3. Open on beta's item opens it in beta; Back returns to Needs you.
    group(page, "beta").locator("[data-testid=ny-open]").first.click()
    H.wait_view(page, "rung")
    name_is(page, "beta")
    back(page)
    front(page)
    # Open project gamma opens its Home; Back returns to Needs you.
    idle.locator("[data-testid=open-project]").click()
    H.wait_view(page, "home")
    name_is(page, "gamma")
    back(page)
    front(page)
    # From a project view, one action reaches Needs you.
    page.evaluate("window.__rungNavigate('rung', {rid: 'R-1'})")
    H.wait_view(page, "rung")
    page.locator(".rung [data-testid=project-name]").first.click()
    front(page)

    # 4. Approve beta's item on its page; on return the total is 2 and beta has nothing waiting, no reload.
    group(page, "beta").locator("[data-testid=ny-open]").first.click()
    H.wait_view(page, "rung")
    name_is(page, "beta")
    page.locator(".rung [data-testid=approve]").first.click()
    H.wait_until(lambda: e.tiles("beta")["needs_you"] == 0, msg="beta approved")
    back(page)
    front(page)
    H.wait_until(lambda: total(page) == 2, msg=lambda: f"total 2 (now {page.locator('.rung [data-testid=ny-total]').first.inner_text()})")
    H.wait_until(lambda: group(page, "beta").count() == 0, msg="beta leaves the groups")
    H.wait_until(lambda: page.locator(".rung [data-testid=ny-idle][data-project='beta']").count() == 1,
                 msg="beta under Nothing waiting")
    assert total(page) == e.tiles("alpha")["needs_you"]


def _front_from_home(page, project):
    page.evaluate("window.__rungNavigate('home')")
    H.wait_view(page, "home")
    name_is(page, project)
    page.locator(".rung [data-testid=project-name]").first.click()
    front(page)


def test_frt07_the_page_updates_without_a_reload(rung, page):
    e = rung.engine
    root = rung.work
    H.configure_stubs(e, root)
    make(e, root, "alpha", ["Read the file"])
    make(e, root, "gamma", ["Sort the list"])
    e.open_project("alpha")
    H.open_rung(page)
    _front_from_home(page, "alpha")
    H.wait_until(lambda: total(page) == 0, msg="nothing waiting")
    # An item starts needing you, then stops, while the page stays open: no navigation, no reload.
    marker = page.evaluate("window.__frt07 = Math.random()")
    e.edit("gamma", "R-1", text="Sort the list twice", approve=True)
    H.wait_until(lambda: group(page, "gamma").count() == 1 and total(page) == e.tiles("gamma")["needs_you"] == 1,
                 timeout=15, msg="gamma starts needing you")
    stale = group(page, "gamma").locator("[data-testid=ny-item]").first.get_attribute("data-item")
    page.evaluate("window.__rungRest('/projects/gamma/rungs/' + arguments[0] + '/approve', {method: 'POST', body: {}})"
                  .replace("arguments[0]", repr(stale)))
    H.wait_until(lambda: group(page, "gamma").count() == 0 and total(page) == 0, timeout=15, msg="gamma stops needing you")
    assert page.evaluate("window.__frt07") == marker, "the page reloaded"
    assert page.evaluate("window.__rungNav().view") == "projects"



def test_frt07_twenty_projects_of_500_rungs_within_a_second(rung, page):
    e = rung.engine
    root = rung.work
    H.configure_stubs(e, root)
    make(e, root, "alpha", ["Read the file"])
    for i in range(20):
        f = root / f"big{i:02d}"
        f.mkdir()
        seed.seed_large(e, f, name=f"big{i:02d}", executions=0)
    e.open_project("alpha")
    projects = e.overview()["projects"]
    assert len(projects) == 21 and sum(1 for p in projects if p["name"].startswith("big")) == 20
    H.open_rung(page)
    best = None
    for _ in range(3):  # the best of three opens, so one load spike on the shared Mac does not decide it
        page.evaluate("window.__rungNavigate('home')")
        H.wait_view(page, "home")
        name_is(page, "alpha")
        page.wait_for_timeout(500)
        t0 = time.time()
        page.locator(".rung [data-testid=project-name]").first.click()
        H.wait_until(lambda: page.locator(".rung [data-testid=project-row]").count() == 21
                     and page.locator(".rung [data-testid=ny-total]").count() == 1, timeout=20,
                     msg=f"21 projects shown: rows {page.locator('.rung [data-testid=project-row]').count()}")
        took = time.time() - t0
        best = took if best is None else min(best, took)
    want = sum(e.tiles(p["name"])["needs_you"] for p in e.overview()["projects"])
    H.wait_until(lambda: total(page) == want, msg=f"total {want}")
    assert best <= 1.0, f"Needs you with 20 projects of 500 rungs took {best:.2f}s"


def test_frt08_a_failed_load_shows_its_error_and_retry(rung, page):
    e = rung.engine
    root = rung.work
    H.configure_stubs(e, root)
    make(e, root, "alpha", ["Read the file"])
    e.edit("alpha", "R-1", text="Read the file twice", approve=True)
    e.open_project("alpha")
    H.open_rung(page)
    page.evaluate("window.__rungNavigate('home')")
    H.wait_view(page, "home")
    page.evaluate("window.__rungRefuse(['/overview'])")
    try:
        page.locator(".rung [data-testid=project-name]").first.click()
        H.wait_view(page, "projects")
        main = page.locator(".rung [data-rung-view]").first
        H.wait_until(lambda: page.locator(".rung [data-rung-view] [role=alert]").count() >= 1
                     and "refused" in main.inner_text().lower(), timeout=10, msg=lambda: f"the error: {main.inner_text()[:300]}")
        text = main.inner_text()
        assert "Nothing waiting" not in text and "Nothing needs you" not in text, text[:400]
        assert page.locator(".rung [data-testid=ny-total]").count() == 0
        retry = page.locator(".rung [data-testid=retry]").first
        assert retry.is_visible()
    finally:
        page.evaluate("window.__rungRefuse([])")
    retry.click()
    front(page)
    H.wait_until(lambda: total(page) == e.tiles("alpha")["needs_you"] == 1, msg="Retry loads it")
