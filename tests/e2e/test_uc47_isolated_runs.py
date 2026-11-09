"""UC47 Isolated runs (SYS-05, B12; decisions Round 24): set in project settings; a run works in its own
workspace and its passes are local; integrating applies its files, a second run on the same file is refused as a
conflict naming it, and two runs that are green alone can still break the journey together."""

from pathlib import Path

import harness as H
from rung_engine.runner import run_loop
from rung_engine.workers import StubWorker
from support import seed


def _run(e, tmp_path, spec, files, tag):
    stub = tmp_path / f"stub-{tag}"
    att = stub / spec / "attempt-1"
    for rel, text in files.items():
        (att / rel).parent.mkdir(parents=True, exist_ok=True)
        (att / rel).write_text(text)
    run = e.start_run("linkpair", spec, profile=e.project("linkpair")["profiles"][0])
    return run_loop(e, run["id"], worker=StubWorker(str(stub), delay=0))


def _open_run(page, rid):
    page.evaluate(f"window.__rungNavigate('run', {{run: {rid}}})")
    H.wait_view(page, "run")
    box = page.locator(".rung [data-testid=workspace]")
    H.wait_until(lambda: box.count() == 1, msg=lambda: page.locator(".rung [data-rung-view]").inner_text()[:500])
    return box


def test_iso01_iso02_iso03_iso04_isolated_runs(rung, tmp_path, page):
    e = rung.engine
    folder = tmp_path / "linkpair"
    folder.mkdir()
    seed.seed_linkpair(e, folder)
    seed.fix_linkpair(folder)
    e.accept_test_files("linkpair", "T-2.1a")
    e.open_project("linkpair")
    m = e.create_milestone("linkpair", "Share a short link", "Create a link and see it", ["S-1.1", "S-2.1"])
    e.add_milestone_check("linkpair", m["id"], {"type": "command", "command": "pytest -q journey/test_journey.py"})
    e.approve_milestone("linkpair", m["id"])

    # 1. Isolated, set in settings.
    H.open_rung(page)
    page.evaluate("window.__rungNavigate('project-settings', {})")
    H.wait_view(page, "project-settings")
    sec = page.locator(".rung [data-testid=run-mode]")
    sec.wait_for()
    sec.locator("input[value=isolated]").click()
    H.wait_until(lambda: e.project("linkpair")["run_mode"] == "isolated", msg="isolated saved")
    api = (folder / "shortly" / "api.py").read_text()
    page_py = (folder / "shortly" / "page.py").read_text()
    r1 = _run(e, tmp_path, "S-1.1", {"shortly/api.py": api + "\n# one\n"}, "a")
    assert r1["status"] == "passed" and (folder / "shortly" / "api.py").read_text() == api
    assert e.executions("linkpair", "T-1.1a") == [] and r1["attempts"][0]["local"][0]["status"] == "pass"
    box = _open_run(page, r1["id"])
    assert box.locator("[data-file='shortly/api.py']").count() == 1 and "Local" in box.inner_text()

    # 2. A second run on the same file: the first integrates, the second is refused naming the file.
    r2 = _run(e, tmp_path, "S-2.1", {"shortly/api.py": api + "\n# two\n"}, "b")
    assert r2["status"] == "passed"
    page.locator(".rung [data-testid=integrate]").click()
    H.wait_until(lambda: (folder / "shortly" / "api.py").read_text().endswith("# one\n"), msg="first applied")
    H.wait_until(lambda: "Integrated" in page.locator(".rung [data-testid=workspace]").inner_text(), msg="integrated shown")
    box = _open_run(page, r2["id"])
    H.wait_until(lambda: box.locator("[data-conflict='1'][data-file='shortly/api.py']").count() == 1, msg=lambda: box.inner_text())
    page.locator(".rung [data-testid=integrate]").click()
    err = page.locator(".rung [data-testid=error]")
    H.wait_until(lambda: err.count() == 1 and "shortly/api.py" in err.inner_text() and "nothing was applied" in err.inner_text(),
                 msg=lambda: err.all_inner_texts())
    assert (folder / "shortly" / "api.py").read_text().endswith("# one\n")
    H.evidence(page, 47)

    # 3. Different files, each green alone, together they break the journey.
    cur = (folder / "shortly" / "api.py").read_text()
    strict = cur.replace("    def do_POST(self):\n", "    def do_POST(self):\n        if self.path != \"/links\":\n"
                         "            self.send_error(404)\n            return\n")
    ra = _run(e, tmp_path, "S-1.1", {"shortly/api.py": strict}, "c")
    rb = _run(e, tmp_path, "S-2.1", {"shortly/page.py": page_py.replace('base + "/links"', 'base + "/v2/links"')}, "d")
    assert ra["status"] == rb["status"] == "passed"
    for r in (ra, rb):
        _open_run(page, r["id"])
        page.locator(".rung [data-testid=integrate]").click()
        H.wait_until(lambda: e.run(r["id"])["workspace"]["integrated_at"], msg=f"run {r['id']} integrated")
    assert Path(folder / "shortly" / "page.py").read_text().count("/v2/links") == 1
    H.wait_until(lambda: e.check("linkpair", "S-1.1")["ok"] and e.check("linkpair", "S-2.1")["ok"], msg="each checked")
    [res] = e.run_milestone("linkpair", m["id"])
    assert res["status"] == "fail" and not e.milestone("linkpair", m["id"])["ok"]
