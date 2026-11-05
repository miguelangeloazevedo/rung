"""UC21 Resilience: restarts, a second writer, the previous release's store, and a large project."""

import shutil
import sqlite3

import harness as H
from rung_engine.host import pid_alive
from support import seed

NEED = "Merge two CSV exports by a shared key"
V1 = H.ROOT / "tests" / "fixtures" / "store-v1" / "rung.db"


def rows(db, sql):
    c = sqlite3.connect(db)
    c.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in c.execute(sql)]
    finally:
        c.close()


def test_res01_res02_survives_a_full_restart(rung, csvtidy):
    e = rung.engine
    seed.seed_merge(e, csvtidy, upto="develop")
    H.configure_stubs(e, csvtidy, worker_delay=30.0)
    with H.desktop() as page:
        H.open_rung(page)
        H.wait_view(page, "home")
        # 1. Data entered in the pane.
        H.button(page, "New need").click()
        H.wait_view(page, "need-new")
        page.locator(".rung [name=need]").fill("Split a large CSV into files of a chosen size")
        H.button(page, "Create need").click()
        H.wait_view(page, "build")
        # 2. A develop run in progress.
        page.evaluate("window.__rungNavigate('build', {need: 'N-2', step: 'develop'})")
        row = page.locator(".rung [data-testid=develop-table] [data-spec=\"S-4.1\"]")
        row.wait_for()
        H.button(page, "Send", row).click()
        H.wait_view(page, "run")
        run = H.wait_until(lambda: (e.runs("csvtidy", "S-4.1") or [None])[0], msg="run created")
        H.wait_until(lambda: e.run(run["id"])["status"] == "running" and e.run(run["id"])["pid"], timeout=30,
                     msg="runner started")
    pid = e.run(run["id"])["pid"]
    H.restart_all()
    H.wait_until(lambda: not pid_alive(pid), timeout=30, msg="runner stopped with the backend")
    with H.desktop() as page:
        H.open_rung(page)
        H.wait_view(page, "home")
        rail = page.locator(".rung [data-testid=rail]")
        H.wait_until(lambda: "N-3" in rail.inner_text(), msg="need entered before the restart is shown")
        assert [r["text"] for r in H.stored(rung.store, "SELECT text FROM rungs WHERE rid='N-3'")] == \
            ["Split a large CSV into files of a chosen size"]
        r = e.run(run["id"])
        assert r["status"] == "unknown", r["status"]
        assert H.stored(rung.store, "SELECT COUNT(*) AS n FROM runs WHERE status='running'")[0]["n"] == 0
        page.evaluate(f"window.__rungNavigate('run', {{run: {run['id']}}})")
        H.wait_view(page, "run")
        card = page.locator(".rung [data-testid=run]")
        H.wait_until(lambda: "Unknown" in card.inner_text(), msg="run shown Unknown")
        assert r["reason"] in ("the runner was stopped before the run ended", "the runner process ended")
        assert r["reason"] in card.inner_text()


def test_res03_second_writer_is_refused(rung, csvtidy, page):
    e = rung.engine
    seed.seed_csvtidy(e, csvtidy)
    e.open_project("csvtidy")
    H.open_rung(page)
    H.wait_view(page, "home")
    page.evaluate("window.__rungNavigate('rung', {rid: 'R-1'})")
    H.wait_view(page, "rung")
    editor = page.locator(".rung [data-testid=req-editor]")
    editor.wait_for()
    page.locator(".rung [name=req-text]").fill("Detect the delimiter from the header line")
    # Meanwhile a second window changes R-1 and the pane refreshes its data.
    e.edit("csvtidy", "R-1", text="Detect the delimiter, also for semicolons")
    other = e.rung("csvtidy", "R-1")
    H.button(page, "Approve").click()
    alert = page.locator(".rung [data-testid=conflict]")
    alert.wait_for()
    assert alert.get_attribute("role") == "alert" and alert.inner_text().strip()
    reload = alert.get_by_role("button", name="Reload")
    assert reload.is_visible()
    # Trying again without reloading is still refused: nothing silently overwritten.
    H.button(page, "Approve").click()
    page.wait_for_timeout(500)
    assert e.rung("csvtidy", "R-1")["text"] == other["text"]
    assert e.rung("csvtidy", "R-1")["version"] == other["version"]
    reload.click()
    H.wait_until(lambda: page.locator(".rung [name=req-text]").input_value() == other["text"],
                 msg="the editor shows the other window's text")
    assert page.locator(".rung [data-testid=conflict]").count() == 0
    H.evidence(page, 21)


def test_res04_previous_release_store_opens_intact(rung, page):
    before = {t: rows(V1, f"SELECT * FROM {t}") for t in ("projects", "rungs", "executions", "picks")}
    copy = rung.tmp / "v1" / "rung.db"
    copy.parent.mkdir(parents=True)
    shutil.copy(V1, copy)
    H.release_store()
    H.pointer_file().write_text(str(copy) + "\n")  # the backend, not the test, opens and migrates it
    try:
        H.open_rung(page)
        H.wait_until(lambda: H.view(page) in ("home", "projects"), msg="store opens")
        page.evaluate("window.__rungNavigate('projects')")
        H.wait_view(page, "projects")
        listed = page.locator(".rung [data-testid=project-list]").inner_text()
        for p in before["projects"]:
            assert p["name"] in listed
        assert rows(copy, "SELECT value FROM meta WHERE key='schema_version'")[0]["value"] == "2"
        after = {t: rows(copy, f"SELECT * FROM {t}") for t in before}
        for t, old in before.items():
            assert len(after[t]) == len(old), t
            for o, n in zip(old, after[t]):
                assert {k: n[k] for k in o} == o, (t, o)
        page.locator(".rung [data-testid=project-list]").get_by_text("csvtidy", exact=True).first.click()
        H.wait_view(page, "home")
        page.evaluate("window.__rungNavigate('rung', {rid: 'T-2.1a'})")
        H.wait_view(page, "rung")
        execs = [x for x in before["executions"] if x["test_pk"] == next(
            r["pk"] for r in before["rungs"] if r["rid"] == "T-2.1a" and r["project_pk"] == before["projects"][0]["pk"])]
        H.wait_until(lambda: f"#{max(x['n'] for x in execs)}" in H.main_area(page).inner_text(), msg="history shown")
    finally:
        H.release_store()


def _timed(page, nav_js, ready_js):
    return page.evaluate(f"""async () => {{
        const ready = () => {{ try {{ return !!({ready_js}) }} catch (_) {{ return false }} }}
        const t0 = performance.now()
        {nav_js}
        while (!ready()) {{
            await new Promise(r => requestAnimationFrame(r))
            if (performance.now() - t0 > 10000) return -1
        }}
        return performance.now() - t0
    }}""")


def test_res05_large_project_renders_quickly(rung, page):
    e = rung.engine
    folder = rung.work / "bigladder"
    folder.mkdir(parents=True)
    seed.seed_large(e, folder)
    e.open_project("bigladder")
    assert H.stored(rung.store, "SELECT COUNT(*) AS n FROM rungs")[0]["n"] == 500
    assert H.stored(rung.store, "SELECT COUNT(*) AS n FROM executions")[0]["n"] == 2000
    H.open_rung(page)
    H.wait_until(lambda: H.view(page) is not None, msg="pane open")
    page.evaluate("window.__rungNavigate('settings')")
    H.wait_view(page, "settings")
    page.wait_for_timeout(500)
    home_ms = _timed(page, "window.__rungNavigate('home')",
                     "document.querySelector('.rung [data-testid=tile-needs-you-value]') && "
                     "document.querySelector('.rung [data-testid=rail]').innerText.includes('N-20')")
    ladder_ms = _timed(page, "window.__rungNavigate('rung', {rid: 'N-20'})",
                       "document.querySelector('.rung [data-testid=need]') && "
                       "document.querySelector('.rung [data-testid=need]').innerText.includes('R-160')")
    print(f"home {home_ms:.0f} ms, ladder {ladder_ms:.0f} ms")
    assert 0 <= home_ms < 1000, home_ms
    assert 0 <= ladder_ms < 1000, ladder_ms
