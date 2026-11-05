"""UC14 Error states: drafting and test launch."""

import shutil

import harness as H
from support import seed


def badge(page, spec):
    loc = page.locator(f".rung [data-spec=\"{spec}\"]")
    return loc.inner_text() if loc.count() else ""


def drafting(e, folder, fail=""):
    cfg = {"kind": "stub", "profile": "", "stub_file": str(folder / ".rung-stub" / "drafts.json"), "delay": 0.4}
    if fail:
        cfg["fail"] = fail
    e.set_setting("drafting", cfg)


def test_spc06_failed_draft_retry_and_i_write(rung, csvtidy, page):
    e = rung.engine
    seed.seed_merge(e, csvtidy, upto="requirements")
    drafting(e, csvtidy, fail="the drafting profile timed out")
    H.open_rung(page)
    H.wait_view(page, "home")
    page.evaluate("window.__rungNavigate('build', {need: 'N-2', step: 'specs'})")
    page.locator(".rung [data-testid=spec-step]").wait_for()
    approve = H.button(page, "Approve drafted")
    # 1. AI derives ends in Draft failed with the reason.
    for r in ("R-4", "R-5"):
        page.locator(f".rung [data-req={r}] [data-testid=authoring]").get_by_role("radio", name="AI derives").click()
    H.wait_until(lambda: "Draft failed" in badge(page, "S-4.1") and "Draft failed" in badge(page, "S-5.1"), timeout=30,
                 msg="Draft failed shown")
    assert "the drafting profile timed out" in badge(page, "S-4.1")
    assert e.rung("csvtidy", "S-4.1")["draft_error"] == "the drafting profile timed out"
    # the gate counts a failed draft as missing
    assert approve.is_disabled()
    # Retry drafts again
    drafting(e, csvtidy)
    H.button(page, "Retry", page.locator(".rung [data-spec=\"S-4.1\"]")).click()
    H.wait_until(lambda: "Drafted" in badge(page, "S-4.1"), timeout=30, msg="retry drafted")
    assert "draft_error" not in e.rung("csvtidy", "S-4.1")
    # I write switches that requirement to human authoring, on the same specification
    H.button(page, "I write", page.locator(".rung [data-spec=\"S-5.1\"]")).click()
    H.wait_view(page, "spec-edit")
    page.locator(".rung input[name=spec-text]").fill("Report keys found in only one file, per file")
    H.button(page, "Save and approve").click()
    H.wait_view(page, "build")
    s = e.rung("csvtidy", "S-5.1")
    assert s["text"] == "Report keys found in only one file, per file" and s["author_role"] == "human"
    # 4. Nothing else on the step is blocked: R-6 can still be written.
    page.locator(".rung [data-req=R-6] [data-testid=authoring]").get_by_role("radio", name="I write, AI supports").click()
    H.button(page, "Write", page.locator(".rung [data-req=R-6]")).click()
    H.wait_view(page, "spec-edit")
    page.locator(".rung input[name=spec-text]").fill("Preserve column order from the first file")
    H.button(page, "Save and approve").click()
    H.wait_view(page, "build")
    H.wait_until(lambda: approve.is_enabled(), msg="Approve drafted enabled")
    H.evidence(page, 14)


def test_exe04_command_that_cannot_start_is_error(rung, csvtidy, page):
    e = rung.engine
    seed.seed_csvtidy(e, csvtidy)
    e.open_project("csvtidy")
    e.edit_test("csvtidy", "T-1.1a", {"command": "csvtidy-no-such-command"})
    e.approve("csvtidy", "T-1.1a")
    H.open_rung(page)
    H.wait_view(page, "home")
    page.locator(".rung [data-testid=rail]").get_by_text("T-1.1a", exact=False).first.click()
    H.wait_view(page, "rung")
    # 2. The command cannot start: Error with the reason, neither pass nor fail.
    H.button(page, "Run tests").click()
    H.wait_view(page, "exec")
    ex = page.locator(".rung [data-testid=execution]")
    H.wait_until(lambda: ex.get_attribute("data-exec-status") == "error", timeout=30, msg="Error recorded")
    assert "could not start" in ex.inner_text()
    rows = H.stored(rung.store, "SELECT e.n, e.status, e.exit_code FROM executions e JOIN rungs t ON t.pk=e.test_pk "
                                "WHERE t.rid='T-1.1a' ORDER BY e.n")
    err = rows[-1]
    assert err["status"] == "error" and err["exit_code"] is None
    assert not e.check("csvtidy", "S-1.1")["ok"]
    # enters Needs you, not Failing
    page.locator("[data-testid=rung-status-chip]").first.click()
    H.wait_view(page, "home")
    item = page.locator(".rung [data-testid=needs-you-item]").filter(has_text="T-1.1a")
    H.wait_until(lambda: item.count() == 1 and "Error" in item.first.inner_text(), msg="Error in Needs you")
    chip, tile, items = H.agreed_needs_you(page)
    assert chip == tile == items
    assert page.locator(".rung [data-testid=tile-failing-value]").inner_text() == "0"
    # 3. Fix the cause and run again: a new execution, the Error stays in history.
    e.edit_test("csvtidy", "T-1.1a", {"command": "pytest tests/test_sniff.py"})
    e.approve("csvtidy", "T-1.1a")
    H.button(page, "Open", item.first).click()
    H.wait_view(page, "exec")
    H.button(page, "Run again").click()
    H.wait_until(lambda: ex.get_attribute("data-exec-status") == "pass", timeout=60, msg="new execution passes")
    rows2 = H.stored(rung.store, "SELECT e.n, e.status FROM executions e JOIN rungs t ON t.pk=e.test_pk "
                                 "WHERE t.rid='T-1.1a' ORDER BY e.n")
    assert rows2[:-1] == [{"n": r["n"], "status": r["status"]} for r in rows]
    assert rows2[-1]["status"] == "pass" and rows2[-1]["n"] == err["n"] + 1
    # 4. A way back from every error view.
    assert H.button(page, "Back to test").is_visible()


def test_exe04_missing_project_folder_is_error(rung, csvtidy, page):
    e = rung.engine
    seed.seed_csvtidy(e, csvtidy)
    notes = H.copy_fixture("notes-sync", rung.work)
    seed.seed_notes_sync(e, notes)
    e.open_project("notes-sync")
    shutil.rmtree(notes)
    H.open_rung(page)
    H.wait_view(page, "home")
    page.locator(".rung [data-testid=rail]").get_by_text("T-1.1a", exact=False).first.click()
    H.wait_view(page, "rung")
    H.button(page, "Run tests").click()
    H.wait_view(page, "exec")
    ex = page.locator(".rung [data-testid=execution]")
    H.wait_until(lambda: ex.get_attribute("data-exec-status") == "error", timeout=30, msg="Error recorded")
    assert "folder not found" in ex.inner_text()
    assert H.button(page, "Back to test").is_visible()
