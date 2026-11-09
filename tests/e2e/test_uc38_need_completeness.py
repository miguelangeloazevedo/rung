"""UC38 Need completeness (decisions Round 24, B14): the need view, Home and `rung verify N-1` give one verdict."""

import json
import subprocess
import sys

import harness as H
from support import seed


def _verify(rung):
    env = {"RUNG_STORE": str(rung.store), "PATH": str(H.ROOT / ".venv" / "bin") + ":/usr/bin:/bin"}
    out = subprocess.run([sys.executable, "-m", "rung_engine.cli", "--project", "csvtidy", "--json", "verify", "N-1"],
                         cwd=H.ROOT, env=env, capture_output=True, text=True)
    return out.returncode, json.loads(out.stdout)


def _open_rows(page):
    return page.locator(".rung [data-testid=need-completeness] [data-open]")


def test_cmp01_cmp02_cmp03_need_completeness(rung, csvtidy, page):
    e = rung.engine
    seed.seed_completeness(e, csvtidy)
    e.open_project("csvtidy")
    H.open_rung(page)
    page.evaluate("window.__rungNavigate('rung', {rid: 'N-1'})")
    H.wait_view(page, "rung")
    box = page.locator(".rung [data-testid=need-completeness]")
    box.wait_for()

    # 1. R-1 verified, R-2 approved with no specification: not complete, R-2 listed with its reason.
    badge = box.locator("[data-testid=need-complete]")
    H.wait_until(lambda: badge.inner_text() == "Not complete", msg=lambda: box.inner_text())
    rows = _open_rows(page)
    H.wait_until(lambda: rows.count() == 1 and rows.first.get_attribute("data-open") == "R-2", msg=lambda: box.inner_text())
    assert "No specification" in rows.first.inner_text()

    # 2. A specification under R-2 with no passing test: R-2 listed as S-2.1 not verified.
    e.write_spec("csvtidy", "R-2", "Parse dates by locale")
    e.approve("csvtidy", "S-2.1")
    H.wait_until(lambda: "R-2 · S-2.1" in box.inner_text() and "Not verified" in box.inner_text(), msg=lambda: box.inner_text())
    code, res = _verify(rung)
    assert code == 1 and [(o["rung"], o.get("spec"), o["code"]) for o in res["open"]] == [("R-2", "S-2.1", "not_verified")]

    # 3. Home and the CLI give the same verdict and list as the need view.
    page.evaluate("window.__rungNavigate('home')")
    H.wait_view(page, "home")
    card = page.locator(".rung [data-testid=home-need]").first
    H.wait_until(lambda: "Not complete" in card.inner_text() and "S-2.1 not verified" in card.inner_text(),
                 msg=lambda: card.inner_text())
    [home] = [n for n in e.home("csvtidy")["needs"] if n["id"] == "N-1"]
    assert home["open"] == res["open"] and home["complete"] == res["complete"]
    card.click()
    H.wait_view(page, "rung")
    box.wait_for()
    H.wait_until(lambda: rows.count() == 1, msg=lambda: box.inner_text())
    H.evidence(page, 38)  # the need with its open list

    # Out of scope with a reason: listed, never dropped; the need is complete once R-1's specification is verified.
    rows.first.locator("[data-testid=out-of-scope]").click()
    dialog = page.locator(".rung [data-testid=scope-dialog]")
    dialog.wait_for()
    assert dialog.locator("[data-testid=scope-confirm]").is_disabled()
    dialog.locator("textarea[name=reason]").fill("Date handling moves to the next release")
    dialog.locator("[data-testid=scope-confirm]").click()
    H.wait_until(lambda: badge.inner_text() == "Complete", msg=lambda: box.inner_text())
    out = box.locator("[data-out=R-2]")
    assert "Date handling moves to the next release" in out.inner_text() and "Out of scope" in out.inner_text()
    assert rows.count() == 0
    code, res = _verify(rung)
    assert code == 0 and res["complete"] and res["out_of_scope"][0]["rung"] == "R-2"

    # Back in scope: the open row returns.
    out.locator("[data-testid=back-in-scope]").click()
    H.wait_until(lambda: badge.inner_text() == "Not complete", msg=lambda: box.inner_text())
    assert rows.count() == 1
