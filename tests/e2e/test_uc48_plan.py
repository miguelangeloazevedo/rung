"""UC48 Plan (SYS-04, decisions Round 24): the plan lists each specification's state now; Start ready work starts
the Ready ones only; a failing prerequisite keeps its dependant Blocked while independent work goes on."""

import harness as H
from rung_engine import HUMAN
from support import seed


def test_pln01_pln02_pln03_plan(rung, tmp_path, page):
    e = rung.engine
    folder = tmp_path / "linkpair"
    folder.mkdir()
    seed.seed_linkpair(e, folder)
    (folder / "tests" / "test_docs.py").write_text("def test_docs():\n    assert True\n")
    e.add_requirement("linkpair", "N-1", "The docs describe the API", HUMAN)
    e.approve_requirements("linkpair", "N-1", HUMAN)
    e.write_spec("linkpair", "R-3", "The README names the endpoint", tags=["python"])
    e.approve_drafted("linkpair", "N-1", HUMAN)
    e.add_test("linkpair", "S-3.1", {"type": "command", "command": "pytest -q tests/test_docs.py"}, HUMAN,
               status="approved")
    e.approve_tests("linkpair", "N-1", HUMAN)
    e.add_dependency("linkpair", "S-2.1", "S-1.1")
    # S-1.1's own test fails whatever the worker does: its run ends failed.
    (folder / "tests" / "test_api.py").write_text("def test_x():\n    assert False\n")
    e.accept_test_files("linkpair", "T-1.1a")
    e.open_project("linkpair")
    H.configure_stubs(e, folder)

    H.open_rung(page)
    page.evaluate("window.__rungNavigate('plan', {})")
    H.wait_view(page, "plan")
    items = page.locator(".rung [data-testid=plan-item]")
    H.wait_until(lambda: items.count() == 3, msg=lambda: page.locator(".rung [data-rung-view]").inner_text()[:500])

    def states():
        return {items.nth(i).get_attribute("data-spec"): items.nth(i).get_attribute("data-state") for i in range(items.count())}

    assert states() == {"S-1.1": "ready", "S-2.1": "blocked", "S-3.1": "ready"}
    blk = page.locator(".rung [data-testid=plan-item][data-spec='S-2.1'] [data-testid=blocked-by]")
    assert blk.inner_text() == "by S-1.1"
    H.evidence(page, 48)

    page.locator(".rung [data-testid=start-ready]").click()
    note = page.locator(".rung [data-testid=plan-note]")
    H.wait_until(lambda: note.count() == 1, msg="started")
    assert note.inner_text().startswith("Started S-1.1, S-3.1")
    assert not e.runs("linkpair", "S-2.1")
    H.wait_until(lambda: states().get("S-3.1") == "verified", timeout=120, msg=lambda: str(states()))
    H.wait_until(lambda: all(r["status"] not in ("queued", "running") for r in e.runs("linkpair", "S-1.1")),
                 timeout=120, msg="S-1.1 run ends")
    assert e.runs("linkpair", "S-1.1")[0]["status"] != "passed"
    H.wait_until(lambda: states().get("S-2.1") == "blocked", msg=lambda: str(states()))
    assert not e.runs("linkpair", "S-2.1")
