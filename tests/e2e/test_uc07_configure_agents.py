"""UC7 Configure agents: labels, cost, max runs, enabled; the ranking follows."""

import harness as H
from support import seed


def prof(page, name):
    return page.locator(f".rung tr[data-profile={name}]")


def labels(page, name):
    chips = prof(page, name).locator("[data-label]")
    return [chips.nth(i).get_attribute("data-label") for i in range(chips.count())]


def open_settings(page):
    page.locator(".rung [data-testid=rail]").get_by_text("Allocation:", exact=False).first.click()
    H.wait_view(page, "settings")
    prof(page, "coder").wait_for()


def ranking(page, spec="S-4.1"):
    page.evaluate("window.__rungNavigate('build', {need: 'N-2', step: 'develop'})")
    row = page.locator(f".rung [data-testid=develop-table] [data-spec=\"{spec}\"]")
    row.wait_for()
    row.locator("[data-testid=carried-by]").click()
    menu = row.locator("[data-testid=pick-menu]")
    menu.wait_for()
    picks = menu.locator("[data-pick]")
    out = {picks.nth(i).get_attribute("data-pick"): picks.nth(i).inner_text().replace("\n", " ") for i in range(picks.count())}
    order = [picks.nth(i).get_attribute("data-pick") for i in range(picks.count())]
    row.locator("[data-testid=carried-by]").click()
    return order, out


def parts(text):
    # "<name> <score> · tags T · load L · rel R · cost C"
    bits = text.split(" · ")
    return {b.split()[0]: int(b.split()[1]) for b in bits[1:]}


def test_agt04_agt05_agt06_configure_agents(rung, csvtidy, page):
    e = rung.engine
    seed.seed_merge(e, csvtidy, upto="develop")
    H.open_rung(page)
    H.wait_view(page, "home")
    order0, before = ranking(page)
    assert set(order0) == {"coder", "reviewer", "writer", "researcher"}
    assert parts(before["writer"])["tags"] == 0 and parts(before["reviewer"])["tags"] == 20
    assert parts(before["coder"])["cost"] == 5

    # 1. Settings lists profiles with label chips, cost, max runs and an enabled toggle.
    open_settings(page)
    for p in seed.PROFILES:
        row = prof(page, p["name"])
        assert labels(page, p["name"]) == p["labels"]
        assert row.locator("input[name=cost]").input_value() == str(p["cost"])
        assert row.locator("input[name=max_runs]").input_value() == str(p["max_runs"])
        assert row.locator("[data-testid=enabled]").get_attribute("aria-checked") == "true"

    # 5. Cancel discards unsaved edits.
    prof(page, "coder").locator("input[name=cost]").fill("9")
    prof(page, "writer").locator("[data-testid=enabled]").click()
    H.button(page, "Cancel").click()
    H.wait_view(page, "home")
    open_settings(page)
    assert prof(page, "coder").locator("input[name=cost]").input_value() == "5"
    assert prof(page, "writer").locator("[data-testid=enabled]").get_attribute("aria-checked") == "true"
    assert {p["name"]: p["cost"] for p in e.profiles()}["coder"] == 5

    # 2. Add a label, remove a label, change a cost, change max runs, disable a profile; Save.
    prof(page, "writer").locator("[data-add-label=writer]").click()
    inp = prof(page, "writer").locator("[data-testid=label-input]")
    inp.fill("python")
    inp.press("Enter")
    prof(page, "reviewer").locator("[data-remove=python]").click()
    prof(page, "coder").locator("input[name=cost]").fill("1")
    prof(page, "coder").locator("input[name=max_runs]").fill("4")
    prof(page, "researcher").locator("[data-testid=enabled]").click()
    assert labels(page, "writer") == ["docs", "specs", "python"]
    assert labels(page, "reviewer") == ["review"]
    H.button(page, "Save").click()
    H.wait_view(page, "home")

    # 3. Reload: the values persist.
    H.open_rung(page)
    H.wait_view(page, "home")
    open_settings(page)
    assert labels(page, "writer") == ["docs", "specs", "python"]
    assert labels(page, "reviewer") == ["review"]
    assert prof(page, "coder").locator("input[name=cost]").input_value() == "1"
    assert prof(page, "coder").locator("input[name=max_runs]").input_value() == "4"
    assert prof(page, "researcher").locator("[data-testid=enabled]").get_attribute("aria-checked") == "false"
    stored = {p["name"]: p for p in e.profiles()}
    assert stored["writer"]["labels"] == ["docs", "specs", "python"] and stored["researcher"]["enabled"] is False
    assert stored["coder"]["cost"] == 1 and stored["coder"]["max_runs"] == 4
    H.button(page, "Cancel").click()
    H.wait_view(page, "home")

    # 4. The ranking follows: the disabled profile is gone, parts reflect the new labels and cost.
    order1, after = ranking(page)
    assert "researcher" not in order1
    assert parts(after["writer"])["tags"] == 20
    assert parts(after["reviewer"])["tags"] == 0
    assert parts(after["coder"])["cost"] == 9
    assert order1 == [s["profile"] for s in e.suggest("csvtidy", "S-4.1")["suggestions"]]
    assert order1 != order0
    row = page.locator(".rung [data-testid=develop-table] [data-spec=\"S-4.1\"]")
    row.locator("[data-testid=carried-by]").click()
    row.locator("[data-testid=pick-menu]").wait_for()
    H.evidence(page, 7)
