"""Readiness smoke checks: a develop run carried by a real Hermes profile, worst-case data in every view, agent
and draft text shown as text, and a test run once from its editor. Run: .venv/bin/python -m pytest -q tests/e2e/smoke"""

import json
import os
import subprocess
import sys
import time

import harness as H
from support import seed

HERMES_BIN = os.path.expanduser("~/.hermes/hermes-agent/venv/bin/hermes")
MARKUP = '<img src=x onerror="window.__rungPwned=1"><b data-x="1">bold</b>'


def test_run10_real_hermes_profile_records_an_outcome(tmp_path):
    """One develop run whose worker is a real `hermes -p default chat` process in the isolated e2e home (its model
    is the deterministic stub). Whatever the profile does, the run ends recorded."""
    from rung_engine import Engine
    H.ensure_env()
    store = tmp_path / "store" / "rung.db"
    store.parent.mkdir(parents=True)
    e = Engine(str(store))
    e.save_profiles([{"name": "default", "labels": ["python", "cli", "tests"], "cost": 2, "max_runs": 2, "enabled": True}])
    folder = seed.copy_fixture("csvtidy", tmp_path / "work")
    e.set_setting("drafting", {"kind": "stub", "profile": "", "stub_file": str(folder / ".rung-stub" / "drafts.json"),
                               "delay": 0})
    seed.seed_merge(e, folder, upto="develop")
    with e._tx() as c:
        c.execute("UPDATE projects SET profiles=? WHERE name='csvtidy'", (json.dumps(["default"]),))
    e.set_setting("worker", {"kind": "hermes", "max_turns": 4})
    run = e.start_run("csvtidy", "S-4.1", profile="default")
    env = dict(os.environ, HERMES_HOME=str(H.HOME), PATH=str(H.ROOT / ".venv" / "bin") + os.pathsep + os.environ["PATH"])
    env.pop("PYTHONPATH", None)
    proc = subprocess.run([sys.executable, "-m", "rung_engine.runner", "--db", str(store), "--run", str(run["id"]),
                           "--hermes", HERMES_BIN], cwd=str(H.ROOT), env=env, capture_output=True, text=True, timeout=600)
    r = e.run(run["id"])
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert r["status"] not in ("queued", "running"), r["status"]
    assert r["attempts"] and all(a["status"] not in ("running", "") for a in r["attempts"])
    assert any("hermes -p default chat" in c for a in r["attempts"] for c in (a.get("commands") or [])) or \
        "hermes -p default chat" in json.dumps(r["attempts"])
    e.close()


def _weird(kind, i):
    """Worst-case wording, through the same seams as the demo: long, unicode, right-to-left, markup."""
    n = str(i)
    if n.endswith("1"):
        return f"{kind} {n} " + "very long text that keeps going without a natural break " * 12
    if n.endswith("2"):
        return f"{kind} {n} 日本語のテキスト Ünïcödé émoji 🧪✅ مرحبا بالعالم"
    if n.endswith("3"):
        return f"{kind} {n} {MARKUP}"
    if n.endswith("4"):
        return f"{kind} {n} " + "x" * 300  # one unbroken word
    return f"{kind} {n}"


VIEWS = [("home", {}), ("rung", {"rid": "N-1"}), ("rung", {"rid": "R-3"}), ("rung", {"rid": "S-1.1"}),
         ("rung", {"rid": "T-1.1a"}), ("readout", {"need": "N-1"}), ("projects", {}), ("settings", {}),
         ("build", {"need": "N-1", "step": "develop"}), ("build", {"need": "N-1", "step": "tests"})]


def _overflow(page):
    """Elements wider than the window, or text spilling out of its own box past the pane."""
    return page.evaluate("""() => {
        const W = window.innerWidth, bad = []
        for (const el of document.querySelectorAll('.rung *')) {
            const r = el.getBoundingClientRect()
            if (r.width && r.right > W + 1) bad.push((el.getAttribute('data-testid') || el.tagName) + ' ' + Math.round(r.right)
                + ' ' + (el.className || '').toString().slice(0, 70) + ' | ' + (el.closest('[data-testid]') || {}).getAttribute?.('data-testid'))
        }
        return bad.slice(0, 10)
    }""")


def test_res07_sec03_worst_case_data_breaks_no_view(rung, page):
    e = rung.engine
    folder = rung.work / "worstcase"
    folder.mkdir(parents=True)
    # 20 needs x 52 rungs: 1,040 rows in the tree, plus one empty project and one with a single need.
    big = seed.seed_large(e, folder, name="worstcase", needs=20, reqs=17, executions=1200, text=_weird)
    assert big["rungs"] > 1000
    empty = rung.work / "empty"
    empty.mkdir()
    e.create_project(folder=str(empty), test_command="true")
    one = rung.work / "one"
    one.mkdir()
    e.create_project(folder=str(one), test_command="true")
    e.create_need("one", "Ünïcödé " + MARKUP)
    e.open_project("worstcase")
    H.open_rung(page)
    H.wait_view(page, "home")
    page.locator(".rung [data-testid=tile-needs-you]").wait_for()
    # The 1,040-row home with its full rail renders within two seconds of opening it.
    page.evaluate("window.__rungNavigate('projects')")
    H.wait_view(page, "projects")
    t0 = time.monotonic()
    page.evaluate("window.__rungNavigate('home')")
    H.wait_until(lambda: page.locator(".rung [data-rung]").count() >= big["rungs"], timeout=10, msg="full rail")
    assert time.monotonic() - t0 < 2.0, time.monotonic() - t0
    broken = {}
    for project in ("worstcase", "one", "empty"):
        e.open_project(project)
        page.evaluate("window.__rungNavigate('home')")
        H.wait_until(lambda: page.locator(".rung [data-testid=project-name]").first.inner_text() == project,
                     msg=f"project {project}")
        for view, params in VIEWS:
            if project != "worstcase" and view not in ("home", "projects", "settings"):
                continue
            page.evaluate("([v, p]) => window.__rungNavigate(v, p)", [view, params])
            H.wait_view(page, view)
            page.wait_for_timeout(500)
            text = page.locator(".rung").first.inner_text()
            problems = []
            if "Rung backend unavailable" in text or "Something went wrong" in text:
                problems.append("error shown")
            if page.evaluate("() => !!window.__rungPwned"):
                problems.append("markup executed")
            if page.locator(".rung b[data-x]").count():
                problems.append("markup rendered")
            spill = _overflow(page)
            if spill:
                problems.append(f"overflow {spill}")
            if problems:
                broken[f"{project} {view} {params}"] = problems
        page.evaluate("window.__rungNavigate('home')")
    assert not broken, broken
    # The markup is on screen as the text it is.
    e.open_project("one")
    page.evaluate("window.__rungNavigate('home')")
    H.wait_until(lambda: page.locator(".rung [data-testid=project-name]").first.inner_text() == "one", msg="project one")
    page.evaluate("window.__rungNavigate('rung', {rid: 'N-1'})")
    H.wait_view(page, "rung")
    title = page.locator(".rung [data-testid=need-title]")
    H.wait_until(lambda: MARKUP in title.inner_text(), msg=f"markup as text in {page.locator('.rung').first.inner_text()[:300]!r}")


def test_tst07_run_once_from_the_test_view_and_return(rung, csvtidy, page):
    e = rung.engine
    seed.seed_csvtidy(e, csvtidy)
    e.open_project("csvtidy")
    before = len(e.executions("csvtidy", "T-1.1a"))
    H.open_rung(page)
    H.wait_view(page, "home")
    page.evaluate("window.__rungNavigate('rung', {rid: 'T-1.1a'})")
    H.wait_view(page, "rung")
    H.button(page, "Run tests").click()
    H.wait_view(page, "exec")
    ex = page.locator(".rung [data-testid=execution]")
    H.wait_until(lambda: ex.get_attribute("data-exec-status") == "pass", timeout=60, msg="ran once")
    assert len(e.executions("csvtidy", "T-1.1a")) == before + 1
    H.button(page, "Back to test").click()
    H.wait_view(page, "rung")
    assert "T-1.1a" in H.main_area(page).inner_text()
