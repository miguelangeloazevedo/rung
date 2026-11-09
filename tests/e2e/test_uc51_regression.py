"""UC51 Regression baseline (SYS-08, decisions Round 24): M-2 names M-1 as its baseline; a change that passes
M-2's own check but breaks M-1's journey blocks M-2 `regression_failed`."""

import harness as H
import msys


def test_rgr01_rgr02_regression_baseline(rung, tmp_path, page):
    e = rung.engine
    folder = msys.linkpair(e, tmp_path)
    m1 = msys.milestone(e)
    e.approve_milestone("linkpair", m1)
    e.run_milestone("linkpair", m1)
    assert e.milestone("linkpair", m1)["ok"]
    m2 = msys.milestone(e, "Page only", "pytest -q tests/test_page.py", scope=("S-2.1",))
    state = msys.open_milestone(H, page, m2)
    sec = page.locator(".rung [data-testid=milestone-baseline]")
    H.wait_until(lambda: sec.locator(f"input[name=baseline][value='{m1}']").count() == 1, msg="M-1 offered")
    sec.locator(f"input[name=baseline][value='{m1}']").click()
    H.wait_until(lambda: e.milestone("linkpair", m2)["baseline"]["milestones"] == [m1], msg="baseline saved")
    page.locator(".rung [data-testid=next-action]").click()  # Approve
    H.wait_until(lambda: state.get_attribute("data-state") != "draft", msg="approved")
    api = folder / "shortly" / "api.py"
    api.write_text(api.read_text().replace('out = json.dumps(create(body["url"])).encode()',
                                           'out = json.dumps({"link": create(body["url"])}).encode()'))
    msys.rerun(e)
    page.locator(".rung [data-testid=next-action]").click()  # Run checks: M-1's run too
    H.wait_until(lambda: "regression_failed" in msys.codes(page), timeout=90, msg=lambda: msys.blockers(page))
    assert state.get_attribute("data-state") == "integration_failed"
    assert f"regression: {m1} fails on this code" in msys.blockers(page)
    assert e.milestone("linkpair", m2)["checks"][0]["state"] == "satisfied"  # its own check passes
    H.evidence(page, 51)
