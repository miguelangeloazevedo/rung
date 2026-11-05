"""UC19 Retire and restore a need."""

import subprocess
import sys

import harness as H
from support import seed


def test_ned03_ned04_retire_and_restore(rung, csvtidy, page):
    e = rung.engine
    seed.seed_merge(e, csvtidy, upto="tests")
    statuses = {r["rid"]: r["status"] for r in H.stored(rung.store, "SELECT rid, status FROM rungs")}
    H.open_rung(page)
    H.wait_view(page, "home")
    chip0, tile0, items0 = H.needs_you_counts(page)
    page.locator(".rung [data-testid=rail]").get_by_text("N-2", exact=False).first.click()
    H.wait_view(page, "rung")
    # 1. Retire asks for a reason.
    H.button(page, "Retire").click()
    dialog = page.locator(".rung [data-testid=retire-dialog]")
    dialog.wait_for()
    go = dialog.get_by_role("button", name="Retire", exact=True)
    assert go.is_disabled()
    dialog.locator("textarea[name=reason]").fill("Merging moves to a separate tool")
    go.click()
    H.wait_view(page, "home")
    # N-2 and its rungs leave the home, tiles, Needs you and the gate; the count matches everywhere.
    H.wait_until(lambda: "N-2" not in page.locator(".rung [data-testid=rail]").inner_text(), msg="N-2 gone from rail")
    chip, tile, items = H.needs_you_counts(page)
    assert chip == tile == items
    assert all("N-2" not in t and "R-4" not in t for t in page.locator(".rung [data-testid=needs-you-item]").all_inner_texts())
    assert e.tiles("csvtidy")["requirements"] == 3
    env = {"RUNG_STORE": str(rung.store), "PATH": str(H.ROOT / ".venv" / "bin") + ":/usr/bin:/bin"}
    out = subprocess.run([sys.executable, "-m", "rung_engine.cli", "--project", "csvtidy", "check", "--all"],
                         cwd=H.ROOT, env=env, capture_output=True, text=True)
    assert "S-4.1" not in out.stdout and "S-5.1" not in out.stdout
    # 2. The Retired filter shows N-2 with its reason, read only, history intact.
    page.locator(".rung [data-testid=retired-link]").first.click()
    H.wait_view(page, "retired")
    row = page.locator(".rung [data-testid=retired-row]")
    H.wait_until(lambda: row.count() == 1, msg="retired row")
    assert "N-2" in row.inner_text() and "Merging moves to a separate tool" in row.inner_text()
    row.click()
    H.wait_view(page, "rung")
    page.locator(".rung [data-testid=retired-bar]").wait_for()
    assert page.locator(".rung").get_by_role("button", name="Retire", exact=True).count() == 0
    assert page.locator(".rung").get_by_role("button", name="New requirement", exact=True).count() == 0
    # 3. Restore returns N-2 and its rungs with the statuses they had.
    H.button(page, "Restore", page.locator(".rung [data-testid=retired-bar]")).click()
    H.wait_until(lambda: page.locator(".rung [data-testid=retired-bar]").count() == 0, msg="restored")
    assert {r["rid"]: r["status"] for r in H.stored(rung.store, "SELECT rid, status FROM rungs")} == statuses
    page.locator("[data-testid=rung-status-chip]").first.click()
    H.wait_view(page, "home")
    H.wait_until(lambda: H.needs_you_counts(page) == (chip0, tile0, items0), msg="counts back")
    H.evidence(page, 19)
