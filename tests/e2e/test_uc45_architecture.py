"""UC45 Architecture baseline (SYS-02, decisions Round 24): components and contracts are drafted and approved in
the Architecture view; specifications and a milestone name the components they touch; approving a new contract
version lists the affected work, which is Out of date (contract_changed) until checked again or approved again."""

import harness as H
from support import seed


def test_arc01_arc02_arc03_architecture_baseline(rung, tmp_path, page):
    e = rung.engine
    folder = tmp_path / "linkpair"
    folder.mkdir()
    seed.seed_linkpair(e, folder)
    e.open_project("linkpair")
    assert e.run_test("linkpair", "T-1.1a")["status"] == "pass"
    assert e.run_test("linkpair", "T-2.1a")["status"] == "pass"
    m = e.create_milestone("linkpair", "Share a short link", "Create a link and see it on the page", ["S-1.1", "S-2.1"])
    e.add_milestone_check("linkpair", m["id"], {"type": "command", "command": "true"})

    # 1. Components and the contract, each saved as a draft and approved.
    H.open_rung(page)
    page.evaluate("window.__rungNavigate('architecture', {})")
    H.wait_view(page, "architecture")
    form = page.locator(".rung [data-testid=arch-form]")
    form.wait_for()
    for name, paths in (("api", "shortly/api.py"), ("page", "shortly/page.py")):
        form.locator("input[name=arch_kind][value=component]").check()
        form.locator("input[name=arch_name]").fill(name)
        form.locator("input[name=paths]").fill(paths)
        form.locator("[data-testid=save-arch]").click()
        item = page.locator(f".rung [data-testid=arch-component][data-name='{name}']")
        H.wait_until(lambda: item.count() == 1, msg=lambda: page.locator(".rung [data-rung-view]").inner_text()[:800])
        item.locator("[data-testid=approve-arch]").click()
        H.wait_until(lambda: item.locator("[data-testid=approve-arch]").count() == 0, msg=f"{name} approved")
    form.locator("input[name=arch_kind][value=contract]").check()
    form.locator("input[name=arch_name]").fill("short link JSON")
    form.locator("select[name=contract_kind]").select_option("api")
    H.wait_until(lambda: form.locator("select[name=producer] option[value=api]").count() == 1, msg="producers offered")
    form.locator("select[name=producer]").select_option("api")
    form.locator("input[name=consumers][value=page]").check()
    form.locator("input[name=artifacts]").fill("shortly/api.py")
    form.locator("textarea[name=text]").fill('POST /links answers {"short_url": "/r/0001"}')
    form.locator("[data-testid=save-arch]").click()
    con = page.locator(".rung [data-testid=arch-contract][data-name='short link JSON']")
    H.wait_until(lambda: con.count() == 1, msg="contract drafted")
    con.locator("[data-testid=approve-arch]").click()
    H.wait_until(lambda: e.arch_item("linkpair", "contract", "short link JSON")["current"] is not None, msg="approved")
    assert e.arch_item("linkpair", "contract", "short link JSON")["current"]["artifacts"] == ["shortly/api.py"]

    # 2. S-1.1 names api, S-2.1 names page, M-1 names both.
    for rid, comp in (("S-1.1", "api"), ("S-2.1", "page")):
        page.evaluate(f"window.__rungNavigate('rung', {{rid: '{rid}'}})")
        H.wait_view(page, "rung")
        box = page.locator(".rung [data-testid=spec-components]")
        H.wait_until(lambda: box.locator(f"input[value={comp}]").count() == 1, msg=lambda: box.inner_text() if box.count() else "")
        box.locator(f"input[value={comp}]").click()
        H.wait_until(lambda: e.rung("linkpair", rid).get("components") == [comp], msg=f"{rid} names {comp}")
    page.evaluate(f"window.__rungNavigate('milestone', {{mid: '{m['id']}'}})")
    H.wait_view(page, "milestone")
    mc = page.locator(".rung [data-testid=milestone-components]")
    H.wait_until(lambda: mc.locator("input[value=page]").count() == 1, msg="milestone components offered")
    mc.locator("input[value=api]").click()
    H.wait_until(lambda: e.milestone("linkpair", m["id"])["components"] == ["api"], msg="api named")
    mc.locator("input[value=page]").click()
    H.wait_until(lambda: e.milestone("linkpair", m["id"])["components"] == ["api", "page"], msg="both named")
    e.approve_milestone("linkpair", m["id"])
    e.run_test("linkpair", "T-1.1a")  # the evidence is now judged on the named components' paths (SYS-11)
    e.run_test("linkpair", "T-2.1a")
    assert e.check("linkpair", "S-1.1")["ok"] and e.check("linkpair", "S-2.1")["ok"]

    # 3. A new contract version: the affected work is listed and out of date.
    page.evaluate("window.__rungNavigate('architecture', {})")
    H.wait_view(page, "architecture")
    con = page.locator(".rung [data-testid=arch-contract][data-name='short link JSON']")
    con.wait_for()
    con.locator("[data-testid=revise-contract]").click()
    con.locator("textarea[name=contract_text]").fill('POST /links answers {"link": "/r/0001"}')
    con.locator("[data-testid=save-contract]").click()
    H.wait_until(lambda: con.locator("[data-testid=approve-arch]").count() == 1, msg="version 2 drafted")
    assert e.check("linkpair", "S-1.1")["ok"]  # a draft changes nothing
    con.locator("[data-testid=approve-arch]").click()
    aff = con.locator("[data-testid=affected]")
    H.wait_until(lambda: {aff.locator("[data-affected]").nth(i).get_attribute("data-affected")
                          for i in range(aff.locator("[data-affected]").count())} == {"S-1.1", "S-2.1", m["id"]},
                 msg=lambda: aff.inner_text())
    for rid in ("S-1.1", "S-2.1"):
        v = e.check("linkpair", rid)
        assert v["verification"] == "out_of_date" and "contract_changed" in v["codes"], v
    assert e.milestone("linkpair", m["id"])["state"] == "out_of_date"
    hist = e.arch_item("linkpair", "contract", "short link JSON")
    assert hist["current"]["version"] == 2 and [x["version"] for x in hist["history"]][:2] in ([1, 2], [2, 1])
    H.evidence(page, 45)
    aff.locator("[data-affected='S-1.1']").click()
    H.wait_view(page, "rung")
    ver = page.locator(".rung [data-testid=verification]")
    H.wait_until(lambda: ver.count() == 1 and "contract short link JSON" in ver.inner_text(), msg=lambda: ver.inner_text() if ver.count() else "")
    # checked again (S-1.1) and approved again (M-1)
    e.run_test("linkpair", "T-1.1a")
    e.run_test("linkpair", "T-2.1a")
    assert e.check("linkpair", "S-1.1")["ok"] and e.check("linkpair", "S-2.1")["ok"]
    page.evaluate(f"window.__rungNavigate('milestone', {{mid: '{m['id']}'}})")
    H.wait_view(page, "milestone")
    nxt = page.locator(".rung [data-testid=next-action]")
    H.wait_until(lambda: nxt.count() == 1 and nxt.inner_text() == "Approve", msg="approve again offered")
    nxt.click()
    H.wait_until(lambda: "contract_changed" not in [b["code"] for b in e.milestone("linkpair", m["id"])["blockers"]],
                 msg="approved again")
