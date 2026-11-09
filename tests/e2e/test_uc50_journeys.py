"""UC50 Journeys (SYS-07, decisions Round 24): a milestone lists its journeys in or out of scope; an in-scope
journey without a check blocks it, named; out-of-scope journeys are exported as such, never counted as passed."""

import harness as H
import msys


def test_jrn01_jrn02_jrn03_journeys(rung, tmp_path, page):
    e = rung.engine
    msys.linkpair(e, tmp_path)
    mid = msys.milestone(e)
    state = msys.open_milestone(H, page, mid)
    sec = page.locator(".rung [data-testid=milestone-journeys]")
    sec.locator("input[name=journey_name]").fill("shorten and follow")
    sec.locator("[data-testid=add-journey]").click()
    H.wait_until(lambda: sec.locator("[data-journey='shorten and follow']").count() == 1, msg=lambda: sec.inner_text())
    sec.locator("input[name=journey_name]").fill("bulk import")
    sec.locator("input[name=journey_in_scope]").click()
    sec.locator("input[name=journey_reason]").fill("not in this release")
    sec.locator("[data-testid=add-journey]").click()
    out = sec.locator("[data-journey='bulk import']")
    H.wait_until(lambda: out.count() == 1, msg=lambda: sec.inner_text())
    assert out.get_attribute("data-scope") == "out" and "not in this release" in out.inner_text()
    nxt = page.locator(".rung [data-testid=next-action]")
    nxt.click()  # Approve
    H.wait_until(lambda: state.get_attribute("data-state") != "draft", msg="approved")
    e.run_milestone("linkpair", mid)
    H.wait_until(lambda: "journey shorten and follow has no check" in msys.blockers(page), msg=lambda: msys.blockers(page))
    assert state.get_attribute("data-state") != "verified"
    H.evidence(page, 50)
    sec.locator("[data-journey='shorten and follow'] select[name=journey_check]").select_option(f"{mid}.a")
    H.wait_until(lambda: state.get_attribute("data-state") == "draft", msg="a new version")
    nxt.click()
    H.wait_until(lambda: state.get_attribute("data-state") != "draft", msg="approved again")
    e.run_milestone("linkpair", mid)
    H.wait_until(lambda: state.get_attribute("data-state") == "verified", msg=lambda: msys.blockers(page))
    md = e.milestone_markdown("linkpair", mid)
    assert "bulk import: out of scope (not in this release), not counted as passed" in md
