"""UC27 Revert and fresh draft in the pane: `Revert change` from R-2's `View change` (REQ-06), and
`Fresh draft` of an approved AI-derived specification (SPC-05)."""

import harness as H
from support import seed

R2_NEW = "Normalise every date to ISO 8601 with a time zone"


def main(page):
    return page.locator(".rung [data-testid=main]").first


def test_pne01_pne02_revert_and_fresh_draft(rung, csvtidy, page):
    e = rung.engine
    seed.seed_csvtidy(e, csvtidy)
    H.configure_stubs(e, csvtidy, delay=2.0)
    e.open_project("csvtidy")
    old = e.rung("csvtidy", "R-2")

    # 1. Edit R-2's text and approve; from its View change, Revert.
    e.edit("csvtidy", "R-2", text=R2_NEW, approve=True)
    assert e.rung("csvtidy", "S-2.1")["status"] == "stale"
    H.open_rung(page)
    page.evaluate("window.__rungNavigate('rung', {rid: 'R-2'})")
    link = page.locator(".rung [data-testid=view-change]").first
    link.wait_for(timeout=20000)
    link.click()
    page.locator(".rung [data-testid=change]").first.wait_for(timeout=20000)
    stale_section = page.locator(".rung [data-testid=now-stale]").first
    assert "S-2.1" in stale_section.inner_text()
    page.locator(".rung [data-testid=revert]").first.click()
    H.wait_until(lambda: e.rung("csvtidy", "R-2")["text"] == old["text"], msg="R-2's earlier text back")
    now = e.rung("csvtidy", "R-2")
    assert now["version"] == old["version"] + 2 and now["status"] == "approved"
    chs = e.changes("csvtidy", "R-2")
    assert [c["after"] for c in chs[:2]] == [old["text"], R2_NEW], chs
    H.wait_until(lambda: page.locator(".rung input[name=req-text]").first.input_value() == old["text"],
                 msg=f"R-2 shows its earlier text: {H.view(page)} {page.locator('.rung input[name=req-text]').evaluate_all('els => els.map(e => e.value)')}")
    # What went stale is shown as for any change: S-2.1 stays stale until a person looks at it again.
    assert e.rung("csvtidy", "S-2.1")["status"] == "stale"
    page.locator(".rung [data-testid=view-change]").first.click()
    page.locator(".rung [data-testid=change]").first.wait_for(timeout=20000)
    assert f"Change to R-2" in main(page).inner_text()
    assert R2_NEW in page.locator(".rung [data-testid=before]").first.inner_text()
    assert old["text"] in page.locator(".rung [data-testid=after]").first.inner_text()

    # 2. Setup: R-1 in AI derives mode, its AI-derived S-1.1 approved. Fresh draft on S-1.1.
    from rung_engine.service import Service
    e.approve_requirements("csvtidy", "N-1")
    Service(e, inline_runs=True).set_authoring("csvtidy", "R-1", "ai", wait=True)
    s11 = e.rung("csvtidy", "S-1.1")
    assert s11["status"] == "approved"
    page.evaluate("window.__rungNavigate('rung', {rid: 'S-1.1'})")
    fresh = page.locator(".rung [data-testid=fresh-draft]").first
    fresh.wait_for(timeout=20000)
    fresh.click()
    H.wait_until(lambda: "Drafting" in main(page).inner_text(), timeout=10, msg="shows drafting")
    H.wait_until(lambda: e.rung("csvtidy", "S-1.1")["draft_state"] == "drafted", timeout=30, msg="the new draft")
    got = e.rung("csvtidy", "S-1.1")
    assert got["version"] == s11["version"] + 1 and got["status"] == "draft"
    H.wait_until(lambda: got["text"] in main(page).inner_text(), msg="the new draft in the pane")
    assert page.locator(".rung [data-testid=approve]").first.is_enabled()
    hist = e.history("csvtidy", "S-1.1")
    assert hist[-2]["version"] == s11["version"] and hist[-2]["text"] == s11["text"]
    H.evidence(page, 27)
