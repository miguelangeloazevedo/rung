"""UC52 Quality obligations (SYS-09, decisions Round 24): a performance obligation reads a measured value from the
check's output; above the threshold the milestone is not verified and says the number, threshold and workload."""

import harness as H
import msys


def test_qlt01_qlt02_quality_obligation(rung, tmp_path, page):
    e = rung.engine
    folder = msys.linkpair(e, tmp_path)
    (folder / "perf.py").write_text("print('p95_ms=' + open('p95.txt').read().strip())\n")
    (folder / "p95.txt").write_text("350")
    msys.rerun(e)
    mid = msys.milestone(e)
    state = msys.open_milestone(H, page, mid)
    form = page.locator(".rung [data-testid=obligation-form]")
    form.locator("[name=q_command]").fill("python3 perf.py")
    form.locator("[name=q_measure]").fill(r"p95_ms=(\d+)")
    form.locator("[name=q_threshold]").fill("200")
    form.locator("[name=q_unit]").fill("ms")
    form.locator("[name=q_workload]").fill("100 requests of 10 links")
    form.locator("[name=q_environment]").fill("laptop, Python 3")
    form.locator("[data-testid=add-obligation]").click()
    ob = page.locator(".rung [data-testid=milestone-quality] [data-obligation]")
    H.wait_until(lambda: ob.count() == 1, msg=lambda: page.locator(".rung [data-testid=milestone]").inner_text()[-600:])
    page.locator(".rung [data-testid=next-action]").click()  # Approve
    H.wait_until(lambda: state.get_attribute("data-state") != "draft", msg="approved")
    page.locator(".rung [data-testid=next-action]").click()  # Run checks
    H.wait_until(lambda: state.get_attribute("data-state") == "obligation_unmet", timeout=60, msg=lambda: msys.blockers(page))
    assert "350 ms against 200 under 100 requests of 10 links" in msys.blockers(page)
    card = page.locator(".rung [data-testid=milestone]").inner_text().lower()
    assert "fast" not in card and "secure" not in card
    H.evidence(page, 52)
    (folder / "p95.txt").write_text("120")
    msys.rerun(e)
    e.run_milestone("linkpair", mid)
    H.wait_until(lambda: state.get_attribute("data-state") == "verified", msg=lambda: msys.blockers(page))
    assert "120 ms against 200" in page.locator(".rung [data-testid=measured]").inner_text()
