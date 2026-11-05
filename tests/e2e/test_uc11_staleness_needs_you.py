"""UC11 An upstream change makes rungs stale, an agent in an ordinary chat proposes a rung,
and the Needs you count stays identical in the status bar, the tile and the list."""

import pytest

import harness as H
from rung_engine import Actor, RungError
from support import seed

R2_NEW = "Normalise every date to ISO 8601 with a time zone"
PROPOSAL_1 = "Accept a two-digit year only with --century"
PROPOSAL_2 = "Ignore rows that have no date at all"


def counts(page, n, msg):
    H.wait_until(lambda: H.needs_you_counts(page) == (n, n, n), timeout=30, msg=f"Needs you {n} everywhere ({msg})")


def go_home(page):
    page.locator("[data-testid=rung-status-chip]").click()
    H.wait_view(page, "home")


def chat(page, text):
    """Say something in an ordinary Hermes chat (the Desktop composer, not Rung)."""
    page.evaluate("location.hash = '#/'")
    box = page.locator("[contenteditable=true][aria-label=Message]").first
    box.wait_for(timeout=30000)
    box.click()
    page.keyboard.type(text)
    page.keyboard.press("Enter")


def test_chg01_chg02_chg03_chg04_chg05_chg06_chg07_exe05_staleness_and_needs_you(rung, csvtidy, page):
    e = rung.engine
    seed.seed_csvtidy(e, csvtidy)
    e.open_project("csvtidy")
    assert e.coverage("csvtidy", "R-2") == "covered"
    covered0 = e.tiles("csvtidy")["covered"]
    H.open_rung(page)
    H.wait_view(page, "home")
    counts(page, 0, "start")

    # 1. Edit R-2's text.
    page.locator(".rung [data-testid=rail]").get_by_text("R-2", exact=True).first.click()
    H.wait_view(page, "rung")
    page.locator(".rung input[name=req-text]").fill(R2_NEW)
    H.button(page, "Approve").click()
    H.wait_until(lambda: e.rung("csvtidy", "S-2.1")["status"] == "stale", msg="S-2.1 stale")
    assert e.rung("csvtidy", "T-2.1a")["status"] == "stale"
    assert e.coverage("csvtidy", "R-2") != "covered"
    # T-2.1a's last pass is still in history but no longer counts.
    page.locator(".rung [data-testid=rail]").get_by_text("T-2.1a", exact=False).first.click()
    H.wait_view(page, "rung")
    last_pass = page.locator(".rung [data-exec=\"T-2.1a#3\"]")
    last_pass.wait_for()
    assert "Stale" in last_pass.inner_text()
    assert "line-through" in last_pass.get_attribute("class")
    # 4. The pass's own view shows its result struck through as no longer counting.
    last_pass.click()
    H.wait_view(page, "exec")
    voided = page.locator(".rung [data-testid=voided-result]")
    voided.wait_for()
    assert voided.inner_text() == "Pass" and "line-through" in voided.get_attribute("class")
    assert "No longer counts" in page.locator(".rung [data-testid=no-longer-counts]").inner_text()
    assert [x["status"] for x in e.executions("csvtidy", "T-2.1a")][0] == "pass"

    # 2. Needs you rises by one, identical in all three places; coverage drops.
    go_home(page)
    counts(page, 1, "after the edit")
    assert page.locator(".rung [data-testid=tile-covered-value]").inner_text() == str(covered0 - 1)
    item = page.locator(".rung [data-testid=needs-you-item]").first
    assert "S-2.1" in item.inner_text() and "Stale" in item.inner_text()

    # 3. View change: before, after, and what went stale.
    item.get_by_text("R-2 · ", exact=False).first.click()
    H.wait_view(page, "change")
    assert "Normalise every date to ISO 8601" in page.locator(".rung [data-testid=before]").inner_text()
    assert R2_NEW in page.locator(".rung [data-testid=after]").inner_text().replace("\n", " ")
    stale = page.locator(".rung [data-testid=now-stale] [data-stale]")
    H.wait_until(lambda: stale.count() >= 2, msg="stale list")
    ids = {stale.nth(i).get_attribute("data-stale") for i in range(stale.count())}
    assert {"S-2.1", "T-2.1a"} <= ids

    # 4. Approve S-2.1 as still valid: it leaves Needs you; T-2.1a needs a fresh run.
    go_home(page)
    H.button(page, "Approve", page.locator(".rung [data-testid=needs-you-item]").first).click()
    counts(page, 0, "after approving S-2.1")
    assert e.rung("csvtidy", "S-2.1")["status"] == "approved"
    assert H.node(e, "csvtidy", "T-2.1a")["result"] == "not_run"
    assert e.coverage("csvtidy", "R-2") != "covered"
    assert not e.check("csvtidy", "S-2.1")["ok"]
    page.locator(".rung [data-testid=rail]").get_by_text("T-2.1a", exact=False).first.click()
    H.wait_view(page, "rung")
    H.button(page, "Run tests").click()
    H.wait_view(page, "exec")
    H.wait_until(lambda: e.coverage("csvtidy", "R-2") == "covered", timeout=60, msg="R-2 covered after a fresh pass")

    # 5. An agent in an ordinary chat proposes a requirement through a Rung tool.
    chat(page, f"Propose requirement under N-1: {PROPOSAL_1}")
    H.wait_until(lambda: [i for i in e.needs_you("csvtidy") if i["type"] == "proposed"], timeout=90, msg="proposal stored")
    prop = [i for i in e.needs_you("csvtidy") if i["type"] == "proposed"][0]
    assert prop["text"] == PROPOSAL_1 and prop["proposer"] == "default" and prop["source_chat"]
    H.open_rung(page, fresh=False)
    go_home(page)
    counts(page, 1, "after the proposal")
    card = page.locator(f".rung [data-proposed=\"{prop['id']}\"]")
    assert "Proposed" in card.text_content()
    source = card.locator("[data-testid=proposal-source]").inner_text()
    assert source.startswith("by default · from chat \"") and prop["source_chat"].rstrip("…")[:20] in source
    # The agent cannot approve its own proposal.
    with pytest.raises(RungError):
        e.approve("csvtidy", prop["id"], Actor("agent", "default"))
    H.button(page, "Accept", card).click()
    counts(page, 0, "after Accept")
    assert e.rung("csvtidy", prop["id"])["status"] == "approved"
    assert any(c["id"] == prop["id"] for c in H.node(e, "csvtidy", "N-1")["children"])

    # A second proposal is dismissed and leaves no rung.
    chat(page, f"Propose requirement under N-1: {PROPOSAL_2}")
    H.wait_until(lambda: [i for i in e.needs_you("csvtidy") if i["type"] == "proposed"], timeout=90, msg="second proposal")
    prop2 = [i for i in e.needs_you("csvtidy") if i["type"] == "proposed"][0]
    H.open_rung(page, fresh=False)
    go_home(page)
    counts(page, 1, "after the second proposal")
    card2 = page.locator(f".rung [data-proposed=\"{prop2['id']}\"]")
    H.button(page, "Dismiss", card2).click()
    counts(page, 0, "after Dismiss")
    live = H.stored(rung.store, "SELECT rid FROM rungs WHERE text=? AND status NOT IN ('dismissed')", (PROPOSAL_2,))
    assert live == []
    assert all(c["text"] != PROPOSAL_2 for c in H.node(e, "csvtidy", "N-1")["children"])
    H.evidence(page, 11)
