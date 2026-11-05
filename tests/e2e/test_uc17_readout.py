"""UC17 The need read-out and its export."""

from pathlib import Path

import harness as H
from support import seed


def test_ned05_ned06_readout_and_export(rung, csvtidy, page):
    e = rung.engine
    seed.seed_csvtidy(e, csvtidy)
    e.open_project("csvtidy")
    H.open_rung(page)
    H.wait_view(page, "home")
    page.locator(".rung [data-testid=rail]").get_by_text("N-1", exact=False).first.click()
    H.wait_view(page, "rung")
    H.button(page, "Read-out").click()
    H.wait_view(page, "readout")
    ro = page.locator(".rung [data-testid=readout]")
    ro.wait_for()
    stored = e.readout("csvtidy", "N-1")
    # 1. Intent, Plan, Delivered.
    assert page.locator(".rung [data-testid=intent-text]").inner_text() == stored["need"]["text"]
    assert f"version {stored['need']['version']}" in page.locator(".rung [data-testid=intent-version]").inner_text()
    for req in stored["plan"]:
        assert req["id"] in page.locator(f".rung [data-testid=plan-{req['id']}]").inner_text()
    # 2. Every number and status equals the stored state.
    assert page.locator(".rung [data-testid=proven-count]").inner_text() == f"{stored['proven']} of {stored['total']} proven"
    for d in stored["delivered"]:
        row = page.locator(f".rung [data-testid=delivered-{d['id']}]").inner_text()
        if d["proven"]:
            p = d["proof"]
            assert f"{p['test']} #{p['n']}" in row and p["carried_by"] in row and "Proven" in row
        else:
            assert d["reason"] in row and "Not proven" in row
    # 3. Export writes a markdown file matching the view and shows its path.
    H.button(page, "Export").click()
    shown = page.locator(".rung [data-testid=export-path]")
    shown.wait_for()
    files = list((rung.store.parent / "exports").glob("*.md"))
    assert len(files) == 1
    text = files[0].read_text()
    assert files[0].name in shown.inner_text()
    assert "\u2014" not in text
    assert stored["need"]["text"] in text
    for d in stored["delivered"]:
        assert d["id"] in text
    assert f"{stored['proven']} of {stored['total']} requirements proven" in text
    assert not any(Path(csvtidy).rglob("*-N-1.md")), "the export never lands in the project folder"
    H.evidence(page, 17)
