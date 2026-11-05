"""UC15 Honest attempt outcomes, each produced by a worker stub mode selected through Rung's settings."""

import json
import shutil

import harness as H
from support import seed


def plan(folder, n, outcome=None):
    d = folder / ".rung-stub" / "S-4.1"
    for p in d.glob("attempt-*.json"):
        p.unlink()
    if outcome is None:  # no change: the worker writes nothing for any attempt
        for p in d.glob("attempt-*"):
            if p.is_dir():
                shutil.rmtree(p)
        return
    (d / f"attempt-{n}.json").write_text(json.dumps(outcome))


def send(page):
    page.evaluate("window.__rungNavigate('build', {need: 'N-2', step: 'develop'})")
    row = page.locator(".rung [data-testid=develop-table] [data-spec=\"S-4.1\"]")
    row.wait_for()
    H.button(page, "Send", row).click()
    H.wait_view(page, "run")


def ended(e, before):
    runs = e.runs("csvtidy", "S-4.1")
    return runs[0] if len(runs) > before and runs[0]["status"] not in ("queued", "running") else None


def attempts_text(page):
    return page.locator(".rung [data-testid=attempts]").inner_text()


def details(page, n=1):
    page.locator(f".rung [data-testid=attempts] [data-attempt=\"{n}\"]").click()
    H.wait_view(page, "attempt")
    return page.locator(".rung [data-testid=attempt]").inner_text()


def test_run05_run06_run07_run08_attempt_outcomes(rung, csvtidy, page):
    e = rung.engine
    seed.seed_merge(e, csvtidy, upto="develop")
    H.configure_stubs(e, csvtidy, worker_delay=1.0)
    H.open_rung(page)
    H.wait_view(page, "home")

    # 1. Needs input: the run stops with the worker's reason and enters Needs you; Run again starts a new run.
    plan(csvtidy, 1, {"outcome": "needs_input", "reason": "Which column is the key when both files name it id?"})
    send(page)
    H.wait_until(lambda: "needs input" in attempts_text(page), timeout=60, msg="Needs input live")
    r = H.wait_until(lambda: ended(e, 0), timeout=30, msg="run ended")
    assert r["status"] == "needs_input"
    assert "Which column is the key" in page.locator(".rung [data-testid=run-reason]").inner_text()
    assert "Which column is the key" in details(page)
    page.locator("[data-testid=rung-status-chip]").first.click()
    H.wait_view(page, "home")
    item = page.locator(".rung [data-testid=needs-you-item]").filter(has_text="Needs input")
    H.wait_until(lambda: item.count() == 1, msg="Needs input in Needs you")
    chip, tile, items = H.agreed_needs_you(page)
    assert chip == tile == items
    plan(csvtidy, 1, {"outcome": "unknown"})
    H.button(page, "Run again", item.first).click()
    H.wait_view(page, "run")

    # 3. Unknown: the worker ends without a result; never Pass or Fail, never Running forever.
    r = H.wait_until(lambda: ended(e, 1), timeout=60, msg="unknown run ended")
    assert r["status"] == "unknown"
    H.wait_until(lambda: "unknown" in attempts_text(page), msg="Unknown shown")
    text = details(page)
    assert "Unknown" in text and "Pass" not in text.split("Files changed")[0] and "Fail" not in text.split("Files changed")[0]
    assert H.stored(rung.store, "SELECT COUNT(*) AS n FROM runs WHERE status IN ('queued','running')")[0]["n"] == 0

    # 4. Partial: the missing capability is filed as a Proposed rung naming the run; the spec is not claimed.
    plan(csvtidy, 1, {"outcome": "partial", "capability": "A streaming CSV reader for files over 1 GB"})
    send(page)
    r = H.wait_until(lambda: ended(e, 2), timeout=60, msg="partial run ended")
    assert r["status"] == "partial"
    H.wait_until(lambda: "partial" in attempts_text(page), msg="Partial shown")
    assert "Partial" in details(page)
    page.locator("[data-testid=rung-status-chip]").first.click()
    H.wait_view(page, "home")
    stored = [i for i in e.needs_you("csvtidy") if i["type"] == "proposed"]
    assert len(stored) == 1 and stored[0]["text"] == "A streaming CSV reader for files over 1 GB"
    assert stored[0]["source_chat"] == f"run {r['id']}"
    card = page.locator(f".rung [data-proposed=\"{stored[0]['id']}\"]")
    H.wait_until(lambda: card.count() == 1, msg="proposed rung shown")
    assert "Proposed" in card.text_content() and "A streaming CSV reader" in card.text_content()
    assert f"run {r['id']}" in card.text_content()
    assert e.rung("csvtidy", "S-4.1")["status"] == "approved"
    assert e.coverage("csvtidy", "R-4") != "covered"

    # 2. No change: nothing changes on disk; shown as No change, its tests are not re-run as if work happened.
    plan(csvtidy, 1, None)
    send(page)
    r = H.wait_until(lambda: ended(e, 3), timeout=90, msg="no change run ended")
    H.wait_until(lambda: "no change" in attempts_text(page), msg="No change shown")
    full = e.run(r["id"])
    assert {a["status"] for a in full["attempts"]} == {"no_change"}
    assert full["attempts"][-1]["executions"] == [] or len(full["attempts"]) == 1
    assert "No change" in details(page)

    # 5. Stored state: every outcome, its reason and the attempt it belongs to.
    rows = H.stored(rung.store, "SELECT r.pk AS run, r.status AS run_status, a.n, a.status, a.reason FROM attempts a "
                                "JOIN runs r ON r.pk=a.run_pk ORDER BY r.pk, a.n")
    by_run = {}
    for row in rows:
        by_run.setdefault(row["run"], []).append(row)
    statuses = [[a["status"] for a in v] for v in by_run.values()]
    assert statuses[0] == ["needs_input"] and statuses[1] == ["unknown"] and statuses[2] == ["partial"]
    assert set(statuses[3]) == {"no_change"}
    assert by_run[min(by_run)][0]["reason"].startswith("Which column is the key")
    assert all(a["reason"] for v in list(by_run.values())[1:3] for a in v)
    H.evidence(page, 15)
