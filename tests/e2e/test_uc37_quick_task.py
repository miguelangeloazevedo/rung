"""UC37 Quick task (decisions Round 24, B11): one card for outcome, checks and profile over the same ladder."""

import harness as H
from support import seed

CMD = "python3 -c \"import pathlib,sys; sys.exit(0 if pathlib.Path('TRIMMED').exists() else 1)\""


def test_tsk01_tsk02_tsk03_tsk04_tsk05_tsk06_quick_task(rung, csvtidy, page):
    e = rung.engine
    seed.seed_csvtidy(e, csvtidy)
    H.configure_stubs(e, csvtidy)
    e.open_project("csvtidy")
    needs_before = len(e.tree("csvtidy"))

    H.open_rung(page)
    page.evaluate("window.__rungNavigate('home')")
    H.wait_view(page, "home")
    page.locator(".rung [data-testid=quick-task]").click()
    H.wait_view(page, "quick-new")
    form = page.locator(".rung [data-testid=quick-form]")
    form.locator("[name=outcome]").fill("Trailing spaces are removed from every cell")
    form.locator("[name=check-command-0]").fill(CMD)
    form.locator("[data-testid=quick-add-check]").click()
    form.locator("[name=check-type-1]").select_option("manual")
    form.locator("[name=check-steps-1]").fill("Open the cleaned file\nNo cell ends with a space")
    form.locator("[name=profile]").select_option("coder")
    assert len(e.tree("csvtidy")) == needs_before  # nothing stored before Save
    form.locator("[data-testid=save]").click()

    # 1. One new need, requirement, specification and two tests, all drafts below the need; the card shows each.
    H.wait_view(page, "quick")
    card = page.locator(".rung [data-testid=quick-card]")
    rows = page.locator(".rung [data-testid=quick-rungs] li")
    H.wait_until(lambda: rows.count() == 5, msg=f"five rungs on the card: {card.inner_text()[:300]}")
    need = e.quick_tasks("csvtidy")[-1]["need"]
    c = e.quick("csvtidy", need)
    assert [r["kind"] for r in c["rungs"]] == ["need", "requirement", "specification", "test", "test"]
    assert [r["status"] for r in c["rungs"][1:]] == ["draft"] * 4
    stored = H.stored(rung.store, "SELECT kind, status FROM rungs WHERE rid IN (%s)" % ",".join("?" * 5),
                      [r["id"] for r in c["rungs"]])
    assert len(stored) == 5
    text = card.inner_text()
    for r in c["rungs"]:
        assert f"{r['id']} v1" in text
    spec = c["spec"]
    (csvtidy / ".rung-stub" / spec / "attempt-1").mkdir(parents=True, exist_ok=True)
    (csvtidy / ".rung-stub" / spec / "attempt-1" / "TRIMMED").write_text("done\n")

    # 2. A change after the card loaded refuses Approve and reloads; then Approve names each id and version.
    req = c["rungs"][1]["id"]
    e.edit("csvtidy", req, text="Trailing spaces are removed from every cell, headers included")
    card.locator("[data-testid=quick-approve]").click()
    H.wait_until(lambda: "changed since the card loaded" in card.inner_text(), msg="approval refused")
    assert all(r["status"] != "approved" for r in e.quick("csvtidy", need)["rungs"][1:])
    H.wait_until(lambda: f"{req} v2" in card.inner_text(), msg="card reloaded with the new version")
    card.locator("[data-testid=quick-approve]").click()
    H.wait_until(lambda: e.quick("csvtidy", need)["approved"], msg="approved")
    names = ", ".join(f"{r['id']} v{r['version']}" for r in e.quick("csvtidy", need)["rungs"])
    H.wait_until(lambda: names in page.locator(".rung.relative").inner_text(), msg=f"result line names {names}")

    # 3. Build and verify starts the ordinary run; Verified once both checks pass and the manual result is approved.
    build = card.locator("[data-testid=quick-build]")
    H.wait_until(lambda: build.count() == 1 and build.get_attribute("data-locked") is None, msg="Build and verify")
    build.click()
    H.wait_until(lambda: (e.quick("csvtidy", need)["run"] or {}).get("status") == "passed", timeout=60, msg="run passed")
    assert e.quick("csvtidy", need)["run"]["profile"] == "coder"
    state = card.locator("[data-testid=quick-state]")
    H.wait_until(lambda: state.inner_text() == "Waiting for you", msg="waiting for the manual check")
    card.locator("[data-testid=quick-record]").click()
    H.wait_view(page, "rung")
    manual = page.locator(".rung [data-testid=manual-test]")
    manual.wait_for()
    H.button(page, "Pass", manual).click()
    manual.locator("textarea[name=evidence]").fill("Opened the file, no cell ends with a space")
    H.button(page, "Record", manual).click()
    manual.locator("[data-testid=pending]").wait_for()
    H.button(page, "Approve result", manual).click()
    H.wait_until(lambda: e.quick("csvtidy", need)["verification"]["verification"] == "verified", msg="verified")
    page.keyboard.press("Escape")  # Back returns to the card it came from
    H.wait_until(lambda: H.view(page) == "quick", msg=lambda: str(page.evaluate("window.__rungNav()")))
    H.wait_until(lambda: state.inner_text() == "Verified", msg="card shows Verified")
    H.evidence(page, 37)

    # 4. Show full ladder: the same rungs, no copies; the card never says specification.
    assert "specification" not in card.inner_text().lower()
    card.locator("[data-testid=quick-ladder]").click()
    H.wait_view(page, "rung")
    node = H.node(e, "csvtidy", need)
    ids, walk = [node["id"]], list(node["children"])
    while walk:
        x = walk.pop(0)
        ids.append(x["id"])
        walk = list(x.get("children", [])) + walk
    assert ids == [r["id"] for r in e.quick("csvtidy", need)["rungs"]]
    assert len(e.tree("csvtidy")) == needs_before + 1
    page.keyboard.press("Escape")
    H.wait_view(page, "quick")

    # Editing a check from the card resets its approval; the card no longer shows Verified.
    cmd_row = card.locator("[data-testid=quick-check-row]").first
    cmd_row.locator("[data-testid=quick-edit-check]").click()
    edit = card.locator("[data-testid=quick-edit]")
    edit.locator("[name=edit-command]").fill(CMD + " && echo again")
    edit.locator("[data-testid=quick-edit-save]").click()
    H.wait_until(lambda: not e.quick("csvtidy", need)["approved"], msg="approval reset")
    first = e.quick("csvtidy", need)["checks"][0]
    assert first["status"] == "draft" and not e.executions("csvtidy", first["id"])[0]["counts"]
    H.wait_until(lambda: state.inner_text() != "Verified", msg="card no longer Verified")
    assert card.locator("[data-testid=quick-approve]").count() == 1
