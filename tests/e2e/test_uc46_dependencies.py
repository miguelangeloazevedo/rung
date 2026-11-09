"""UC46 Dependencies (SYS-03, decisions Round 24): S-2.1 requires S-1.1, shown on both; a cycle, a self edge and
an unknown id are refused; with S-1.1 failing, S-2.1 does not start and says why; S-1.1 starts."""

import harness as H
from support import seed


def test_dep01_dep02_dep03_dependencies(rung, tmp_path, page):
    e = rung.engine
    folder = tmp_path / "linkpair"
    folder.mkdir()
    seed.seed_linkpair(e, folder)
    e.open_project("linkpair")
    H.open_rung(page)

    def open_spec(rid):
        page.evaluate(f"window.__rungNavigate('rung', {{rid: '{rid}'}})")
        H.wait_view(page, "rung")
        box = page.locator(".rung [data-testid=spec-system]")
        box.wait_for()
        return box

    def add(box, rid):
        box.locator("input[name=requires]").fill(rid)
        box.locator("[data-testid=add-dependency]").click()

    # 1. The edge shows on both specifications.
    box = open_spec("S-2.1")
    add(box, "S-1.1")
    H.wait_until(lambda: box.locator("[data-testid=requires] [data-dep='S-1.1']").count() == 1, msg="requires shown")
    box = open_spec("S-1.1")
    H.wait_until(lambda: box.locator("[data-testid=required-by] [data-dep='S-2.1']").count() == 1, msg="required by shown")

    # 2. A cycle, a self edge and an unknown id are refused, each named.
    err = page.locator(".rung [data-testid=error-line], .rung [role=alert]")
    for rid, says in (("S-2.1", "S-1.1 requires S-2.1 requires S-1.1"), ("S-1.1", "cannot require itself"),
                      ("S-9.9", "no specification S-9.9")):
        add(box, rid)
        H.wait_until(lambda: says in page.locator(".rung [data-rung-view]").inner_text(), msg=lambda: f"{rid}: {err.all_inner_texts()}")
    assert e.dependencies("linkpair", "S-1.1")["requires"] == []

    # 3. S-1.1 fails: starting S-2.1 is refused with the blocked path; S-1.1 itself starts.
    (folder / "tests" / "test_api.py").write_text("def test_x():\n    assert False\n")
    e.accept_test_files("linkpair", "T-1.1a")
    assert e.run_test("linkpair", "T-1.1a")["status"] == "fail"
    box = open_spec("S-2.1")
    wf = box.locator("[data-testid=waits-for]")
    H.wait_until(lambda: wf.count() == 1 and wf.inner_text() == "S-2.1 waits for S-1.1: Failed",
                 msg=lambda: wf.all_inner_texts())
    dev = page.locator(".rung [data-testid=develop]")
    dev.click()
    H.wait_until(lambda: "S-2.1 cannot start: S-2.1 waits for S-1.1: Failed" in page.locator(".rung [data-rung-view]").inner_text(),
                 msg=lambda: page.locator(".rung [data-rung-view]").inner_text()[:600])
    assert not e.runs("linkpair", "S-2.1")
    H.evidence(page, 46)
    run = e.start_run("linkpair", "S-1.1", profile=e.project("linkpair")["profiles"][0])
    assert run["status"] in ("queued", "running")
    e.cancel_run(run["id"]) if hasattr(e, "cancel_run") else None
