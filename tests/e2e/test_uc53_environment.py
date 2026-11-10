"""UC53 Environment (SYS-10, decisions Round 24): probes and a migration run before the checks; a probe the machine
does not satisfy makes the run Could not verify `environment_mismatch`, a failed migration blocks
`migration_failed`; a satisfied setup records what each probe printed."""

import harness as H
import msys


def test_env01_env02_env03_environment(rung, tmp_path, page):
    e = rung.engine
    msys.linkpair(e, tmp_path)
    mid = msys.milestone(e)
    state = msys.open_milestone(H, page, mid)
    sec = page.locator(".rung [data-testid=milestone-environment]")
    sec.locator("[name=probe_command]").fill("python3 --version")
    sec.locator("[name=probe_contains]").fill("Python 9")
    sec.locator("[data-testid=add-probe]").click()
    H.wait_until(lambda: sec.locator("[data-probe='python3 --version']").count() == 1, msg=lambda: sec.inner_text())
    page.locator(".rung [data-testid=next-action]").click()  # Approve
    H.wait_until(lambda: state.get_attribute("data-state") != "draft", msg="approved")
    nxt = page.locator(".rung [data-testid=next-action]")
    H.wait_until(lambda: nxt.inner_text().strip() == "Run checks", msg=lambda: nxt.inner_text())
    nxt.click()  # Run checks
    H.wait_until(lambda: "environment_mismatch" in msys.codes(page), timeout=60, msg=lambda: msys.blockers(page))
    assert state.get_attribute("data-state") == "could_not_verify"
    assert "probe python3 --version must print Python 9" in msys.blockers(page)
    H.evidence(page, 53)
    probe = [{"command": "python3 --version", "contains": "Python 3"}]
    e.set_milestone_system("linkpair", mid, "environment", {"probes": probe, "migration": "python3 -c 'raise SystemExit(3)'"})
    e.approve_milestone("linkpair", mid)
    e.run_milestone("linkpair", mid)
    H.wait_until(lambda: "migration_failed" in msys.codes(page), msg=lambda: msys.blockers(page))
    e.set_milestone_system("linkpair", mid, "environment", {"probes": probe, "migration": "true"})
    e.approve_milestone("linkpair", mid)
    e.run_milestone("linkpair", mid)
    H.wait_until(lambda: state.get_attribute("data-state") == "verified", msg=lambda: msys.blockers(page))
    out = sec.locator("[data-testid=probe-output]")
    assert out.inner_text().startswith("Python 3")
    setup = e.milestone("linkpair", mid)["env_run"]["setup"]
    e.run_milestone("linkpair", mid)
    assert e.milestone("linkpair", mid)["env_run"]["setup"] == setup
