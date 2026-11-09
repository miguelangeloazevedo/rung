"""UC6 Pick an agent from the ranked suggestions."""

import harness as H
from support import seed


def spec_row(page, spec):
    return page.locator(f".rung [data-testid=develop-table] [data-spec=\"{spec}\"]")


def menu_rows(page, spec):
    row = spec_row(page, spec)
    row.locator("[data-testid=carried-by]").click()
    menu = row.locator("[data-testid=pick-menu]")
    menu.wait_for()
    picks = menu.locator("[data-pick]")
    out = []
    for i in range(picks.count()):
        name = picks.nth(i).get_attribute("data-pick")
        out.append((name, picks.nth(i).inner_text()))
    return out


def test_agt01_agt02_agt03_pick_agent(rung, csvtidy, page):
    e = rung.engine
    seed.seed_merge(e, csvtidy, upto="develop")
    e.save_profiles([dict(p, enabled=p["name"] != "researcher") for p in seed.PROFILES])
    H.open_rung(page)
    H.wait_view(page, "home")
    page.evaluate("window.__rungNavigate('build', {need: 'N-2', step: 'develop'})")
    page.locator(".rung [data-testid=develop-table]").wait_for()

    # 1. Per specification: ranked profiles, whole-number score and its four parts.
    for spec in ("S-4.1", "S-5.1"):
        want = e.suggest("csvtidy", spec)["suggestions"]
        got = menu_rows(page, spec)
        assert [g[0] for g in got] == [w["profile"] for w in want], spec
        for (name, text), w in zip(got, want):
            p = w["parts"]
            assert isinstance(w["score"], int)
            assert text.replace("\n", " ") == (f"{name} {w['score']} · tags {p['tags']} · load {p['load']} "
                                                f"· history {p['reliability']} · cost pref {p['cost']}"), text
            assert w["score"] == p["tags"] + p["load"] + p["reliability"] + p["cost"]
        scores = [w["score"] for w in want]
        assert scores == sorted(scores, reverse=True)
        page.keyboard.press("Escape")
        spec_row(page, spec).locator("[data-testid=carried-by]").click()  # close the menu again
    # The top suggestion with its parts is shown on each row.
    top = e.suggest("csvtidy", "S-4.1")["suggestions"][0]
    assert spec_row(page, "S-4.1").locator("[data-testid=carried-by]").inner_text().startswith(f"{top['profile']} {top['score']}")

    # 2. Disabled profiles and profiles missing a required tag are not suggested.
    s4 = [g[0] for g in menu_rows(page, "S-4.1")]
    spec_row(page, "S-4.1").locator("[data-testid=carried-by]").click()
    assert "researcher" not in s4  # disabled
    assert set(s4) == {"coder", "reviewer", "writer"}
    s5 = [g[0] for g in menu_rows(page, "S-5.1")]
    spec_row(page, "S-5.1").locator("[data-testid=carried-by]").click()
    assert s5 == ["coder"]  # S-5.1 requires the cli tag

    # 3. Pick a profile that is not the top suggestion: shown as picked by you.
    second = e.suggest("csvtidy", "S-4.1")["suggestions"][1]["profile"]
    assert second != top["profile"]
    spec_row(page, "S-4.1").locator("[data-testid=carried-by]").click()
    spec_row(page, "S-4.1").locator(f"[data-pick={second}]").click()
    H.wait_until(lambda: spec_row(page, "S-4.1").locator("[data-testid=picked-by]").count() == 1, msg="picked by")
    assert spec_row(page, "S-4.1").locator("[data-testid=picked-by]").inner_text() == "picked by you"
    assert spec_row(page, "S-4.1").locator("[data-testid=carried-by]").inner_text().startswith(second)
    picks = H.stored(rung.store, "SELECT p.profile, p.picked_by FROM picks p JOIN rungs s ON s.pk=p.spec_pk WHERE s.rid='S-4.1'")
    assert picks == [{"profile": second, "picked_by": "you"}]

    # 4. After the run, the execution is carried by the picked profile.
    H.button(page, "Send", spec_row(page, "S-4.1")).click()
    H.wait_view(page, "run")
    run_id = e.runs("csvtidy")[0]["id"]
    H.wait_until(lambda: e.run(run_id)["status"] not in ("queued", "running"), timeout=90, msg="run ends")
    assert e.run(run_id)["profile"] == second
    ex = e.executions("csvtidy", "T-4.1a")
    assert ex and all(x["carried_by"] == second for x in ex)
    H.wait_until(lambda: page.locator(".rung [data-testid=run]").inner_text().count(second) >= 1, msg="run shows profile")
    H.evidence(page, 6)
