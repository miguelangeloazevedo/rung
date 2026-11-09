"""UC54 Change impact (SYS-11, decisions Round 24): a milestone over components with paths is judged on those
paths; a change under `docs` leaves it Verified, a change under `api` makes it Out of date with the reason;
Check everything reruns every check; the view states what it is judged on."""

import harness as H
import msys


def test_imp01_imp02_imp03_change_impact(rung, tmp_path, page):
    e = rung.engine
    folder = msys.linkpair(e, tmp_path)
    (folder / "docs").mkdir()
    (folder / "docs" / "guide.md").write_text("guide\n")
    for n, paths in (("api", ["shortly/api.py"]), ("page", ["shortly/page.py"]), ("docs", ["docs"])):
        e.save_arch("linkpair", "component", n, {"paths": paths})
        e.approve_arch("linkpair", "component", n)
    e.set_spec_components("linkpair", "S-1.1", ["api"])
    e.set_spec_components("linkpair", "S-2.1", ["page"])
    mid = msys.milestone(e)
    e.set_milestone_components("linkpair", mid, ["api", "page"])
    e.approve_milestone("linkpair", mid)
    msys.rerun(e)
    e.run_milestone("linkpair", mid)
    state = msys.open_milestone(H, page, mid)
    H.wait_until(lambda: state.get_attribute("data-state") == "verified", msg=lambda: msys.blockers(page))
    judged = page.locator(".rung [data-testid=judged-on]").inner_text()
    assert "Judged on: shortly/api.py, shortly/page.py and files outside every component" in judged
    (folder / "docs" / "guide.md").write_text("guide, longer\n")
    page.wait_for_timeout(2500)
    assert state.get_attribute("data-state") == "verified" and e.milestone("linkpair", mid)["ok"]
    api = folder / "shortly" / "api.py"
    api.write_text(api.read_text() + "\n# touched\n")
    H.wait_until(lambda: state.get_attribute("data-state") == "out_of_date", msg=lambda: msys.blockers(page))
    assert "S-1.1 is not verified" in msys.blockers(page)
    H.evidence(page, 54)
    page.locator(".rung [data-testid=check-everything]").click()
    H.wait_until(lambda: state.get_attribute("data-state") == "verified", timeout=90, msg=lambda: msys.blockers(page))
