"""UC49 Contract checks (SYS-06, decisions Round 24): a contract check runs the real API output through the
consumer; it fails while both sides' own tests pass and blocks the milestone; repairing the producer satisfies
it; a code change or a new contract version makes it Out of date."""

import harness as H
from support import seed

CHECK = "python3 -c \"from shortly import api, page; page.render(api.create('https://x.example'))\""


def test_con01_con02_con03_contract_checks(rung, tmp_path, page):
    e = rung.engine
    folder = tmp_path / "linkpair"
    folder.mkdir()
    seed.seed_linkpair(e, folder)
    e.open_project("linkpair")
    for n, paths in (("api", ["shortly/api.py"]), ("page", ["shortly/page.py"])):
        e.save_arch("linkpair", "component", n, {"paths": paths})
        e.approve_arch("linkpair", "component", n)
    e.save_arch("linkpair", "contract", "short link JSON", {"contract_kind": "api", "producer": "api",
                                                            "consumers": ["page"], "artifacts": ["shortly/api.py"]})
    e.approve_arch("linkpair", "contract", "short link JSON")
    assert e.run_test("linkpair", "T-1.1a")["status"] == "pass" and e.run_test("linkpair", "T-2.1a")["status"] == "pass"
    m = e.create_milestone("linkpair", "Share a short link", "Create a link and see it", ["S-1.1", "S-2.1"])
    e.set_milestone_components("linkpair", m["id"], ["api", "page"])
    e.add_milestone_check("linkpair", m["id"], {"type": "command", "command": "true"})
    e.approve_milestone("linkpair", m["id"])

    # 1. Add, approve and run the check in the Architecture view: it fails, M-1 is blocked by it.
    H.open_rung(page)
    page.evaluate("window.__rungNavigate('architecture', {})")
    H.wait_view(page, "architecture")
    con = page.locator(".rung [data-testid=arch-contract][data-name='short link JSON']")
    con.wait_for()
    cc = con.locator("[data-testid=contract-checks]")
    cc.locator("input[name=contract_check]").fill(CHECK)
    cc.locator("[data-testid=add-contract-check]").click()
    H.wait_until(lambda: cc.locator("[data-testid=approve-contract-check]").count() == 1, msg=lambda: cc.inner_text())
    cc.locator("[data-testid=approve-contract-check]").click()
    H.wait_until(lambda: cc.locator("[data-testid=run-contract-checks]").count() == 1, msg=lambda: cc.inner_text())
    cc.locator("[data-testid=run-contract-checks]").click()
    H.wait_until(lambda: cc.get_attribute("data-state") == "failed", timeout=60, msg=lambda: cc.inner_text())
    assert "Failed" in cc.locator("[data-check='CC-1']").inner_text() and "v1" in cc.inner_text()
    assert e.check("linkpair", "S-1.1")["ok"] and e.check("linkpair", "S-2.1")["ok"]
    e.run_milestone("linkpair", m["id"])
    v = e.milestone("linkpair", m["id"])
    assert v["state"] == "integration_failed" and v["blockers"][0]["code"] == "contract_failed", v["blockers"]
    H.evidence(page, 49)

    # 2. Repair the producer: the check passes and M-1 verifies.
    api = folder / "shortly" / "api.py"
    api.write_text(api.read_text().replace('return {"code": code, "short_url": "/r/" + code}',
                                           'return {"code": code, "short_url": "/r/" + code, "url": "/r/" + code}'))
    cc.locator("[data-testid=run-contract-checks]").click()
    H.wait_until(lambda: cc.get_attribute("data-state") == "satisfied", timeout=60, msg=lambda: cc.inner_text())
    e.run_test("linkpair", "T-1.1a")
    e.run_test("linkpair", "T-2.1a")
    e.run_milestone("linkpair", m["id"])
    assert e.milestone("linkpair", m["id"])["ok"], e.milestone("linkpair", m["id"])["blockers"]

    # 3. A code change: the contract check is Out of date, never current.
    (folder / "shortly" / "extra.py").write_text("X = 1\n")
    H.wait_until(lambda: cc.get_attribute("data-state") == "out_of_date", timeout=30, msg=lambda: cc.inner_text())
    assert "changed since" in cc.locator("[data-testid=check-why]").inner_text()
    assert not e.milestone("linkpair", m["id"])["ok"]
