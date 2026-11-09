"""UC43 Allocation labels (decisions Round 24, R11): each score part says what it measures on focus and hover;
the suggestion names the inputs behind the top profile and why each excluded profile is excluded; independent
means a different profile from the author, and the profile stays overridable."""

import harness as H
from rung_engine import allocation
from support import seed


def spec_row(page, spec):
    return page.locator(f".rung [data-testid=develop-table] [data-spec=\"{spec}\"]")


def test_alo01_alo02_alo03_allocation_labels(rung, csvtidy, page):
    e = rung.engine
    seed.seed_merge(e, csvtidy, upto="develop")
    e.save_profiles([dict(p, enabled=p["name"] != "researcher") for p in seed.PROFILES])
    H.open_rung(page)
    H.wait_view(page, "home")
    page.evaluate("window.__rungNavigate('build', {need: 'N-2', step: 'develop'})")
    page.locator(".rung [data-testid=develop-table]").wait_for()

    # 1. Focus each score part: its description says what it measures; nothing reads as money or a chance.
    row = spec_row(page, "S-4.1")
    parts = row.locator("[data-testid=carried-by] [data-part]")
    H.wait_until(lambda: parts.count() == 4, msg=lambda: row.inner_text())
    for i in range(4):
        p = parts.nth(i)
        p.focus()
        k = p.get_attribute("data-part")
        assert page.evaluate("document.activeElement.dataset.part") == k
        assert p.get_attribute("title") == allocation.PART_HELP[k]
        assert allocation.PART_HELP[k] in p.get_attribute("aria-label")
        txt = p.inner_text()
        assert "%" not in txt and "\u20ac" not in txt and "$" not in txt, txt
    assert "not a chance of success" in parts.nth(2).get_attribute("title")
    assert "not money spent" in parts.nth(3).get_attribute("title")

    # 2. Why the top profile fits (its inputs) and why each excluded profile is excluded.
    top = e.suggest("csvtidy", "S-4.1")["suggestions"][0]
    why = row.locator("[data-testid=carried-by] [data-testid=why-fits]")
    assert why.inner_text() == " · ".join(top["why"])
    assert any("past command executions" in w for w in top["why"]) and any("tags" in w for w in top["why"])
    s5 = spec_row(page, "S-5.1")
    ex = e.suggest("csvtidy", "S-5.1")["excluded"]
    assert ex, "S-5.1 leaves profiles out"
    for x in ex:
        assert s5.locator(f"[data-excluded='{x['profile']}'] [data-reason]").inner_text() == x["reason"]

    # 3. Independent: a different profile from the author; override with another eligible profile.
    page.evaluate("window.__rungNavigate('rung', {rid: 'S-4.1'})")
    H.wait_view(page, "rung")
    car = page.locator(".rung [data-testid=carrier]")
    car.wait_for()
    car.locator("[data-testid=independent]").click()
    H.wait_until(lambda: e.suggest("csvtidy", "S-4.1")["independent"], msg="independent set")
    label = car.locator("[data-help]")
    H.wait_until(lambda: label.count() == 1, msg=lambda: car.inner_text())
    label.focus()
    assert label.get_attribute("title") == allocation.INDEPENDENT_HELP
    assert "different profile" in label.get_attribute("title")
    s = e.suggest("csvtidy", "S-4.1")
    authors = {x["profile"] for x in s["excluded"] if x["reason"].startswith("author of")}
    eligible = [x["profile"] for x in s["suggestions"]]
    assert not authors & set(eligible)
    page.evaluate("window.__rungNavigate('build', {need: 'N-2', step: 'develop'})")
    page.locator(".rung [data-testid=develop-table]").wait_for()
    row = spec_row(page, "S-4.1")
    H.wait_until(lambda: row.locator("[data-testid=why-fits]").count() == 1 and
                 "a different profile from the author" in row.locator("[data-testid=why-fits]").inner_text(),
                 msg=lambda: row.inner_text())
    H.evidence(page, 43)
    if len(eligible) > 1:
        other = eligible[1]
        row.locator("[data-testid=carried-by]").click()
        row.locator(f"[data-pick={other}]").click()
        H.wait_until(lambda: e.suggest("csvtidy", "S-4.1")["pick"] and
                     e.suggest("csvtidy", "S-4.1")["pick"]["profile"] == other, msg="override")
        H.wait_until(lambda: row.locator("[data-testid=carried-by]").inner_text().startswith(other), msg="shown")
