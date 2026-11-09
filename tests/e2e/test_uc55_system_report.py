"""UC55 System report (SYS-12, decisions Round 24): every milestone with journeys, obligations, dependencies,
environment, exclusions and manual decisions; Accepted only when everything required is verified now."""

import harness as H
import msys


def test_rep01_rep02_system_report(rung, tmp_path, page):
    e = rung.engine
    msys.linkpair(e, tmp_path)
    mid = msys.milestone(e)
    e.set_milestone_system("linkpair", mid, "journeys", [
        {"name": "shorten and follow", "check": f"{mid}.a"},
        {"name": "bulk import", "in_scope": False, "reason": "not in this release"}])
    e.set_milestone_system("linkpair", mid, "environment", {"probes": [{"command": "python3 --version",
                                                                         "contains": "Python 3"}]})
    e.add_milestone_check("linkpair", mid, {"type": "manual", "steps": ["Open the page", "Click the link"]})
    e.approve_milestone("linkpair", mid)
    e.run_milestone("linkpair", mid)
    H.open_rung(page)
    page.evaluate("window.__rungNavigate('milestones', {})")
    H.wait_view(page, "milestones")
    page.locator(".rung [data-testid=open-report]").click()
    H.wait_view(page, "system-report")
    verdict = page.locator(".rung [data-testid=report-verdict]")
    H.wait_until(lambda: verdict.count() == 1, msg="report shown")
    assert verdict.get_attribute("data-accepted") == "false"
    assert f"{mid}: {mid}.b" in page.locator(".rung [data-testid=report-open]").inner_text()
    md = page.locator(".rung [data-testid=report-markdown]").inner_text()
    for want in ("Journeys:", "bulk import: out of scope (not in this release)", "Environment:", "Manual decisions:"):
        assert want in md, md
    H.evidence(page, 55)
    e.record_milestone_manual("linkpair", mid, f"{mid}.b", "pass", "looked right")
    H.wait_until(lambda: verdict.get_attribute("data-accepted") == "true", msg=lambda: page.locator(".rung [data-testid=system-report]").inner_text()[:400])
    assert "Verdict: Accepted" in page.locator(".rung [data-testid=report-markdown]").inner_text()
