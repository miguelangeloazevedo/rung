"""UC42 Results and evidence (decisions Round 24, U12): the read-out leads with the outcome and verified
behaviours, then what the newest run changed, the checks run, the manual review left and the code basis; how to
try the result is declared in settings and never run; evidence is collapsed and labelled; the export names open
obligations, optional checks and evidence that no longer applies."""

import json
from pathlib import Path

import harness as H
from rung_engine.runner import run_loop
from rung_engine.workers import StubWorker


def test_out01_out02_out03_out04_results_and_evidence(rung, page, tmp_path):
    e = rung.engine
    e.create_sample()
    proj = e.project("sample")
    folder = Path(proj["folder"])
    count = (folder / "wordcount" / "count.py").read_text()
    stub = tmp_path / "stub"
    att = stub / "S-1.1" / "attempt-1"
    (att / "wordcount").mkdir(parents=True)
    (att / "wordcount" / "count.py").write_text(count + "\n# counts words split on any whitespace\n")
    (att / "NOTES.md").write_text("Word counts split on any whitespace.\n")
    run = e.start_run("sample", "S-1.1", profile=proj["profiles"][0])
    run_loop(e, run["id"], worker=StubWorker(str(stub), delay=0))
    assert e.need_completeness("sample", "N-1", fresh=True)["complete"]

    # 2. Declare how to try it in project settings; nothing runs.
    marker = tmp_path / "tried"
    H.open_rung(page)
    page.evaluate("window.__rungNavigate('project-settings', {})")
    H.wait_view(page, "project-settings")
    box = page.locator(".rung [data-testid=try-settings]")
    try:
        H.wait_until(lambda: box.count() == 1, msg=lambda: page.locator(".rung [data-rung-view]").first.inner_text()[:600])
    except AssertionError:
        page.screenshot(path="/tmp/uc42-fail.png")
        raise
    box.locator("input[name=try_instruction]").fill("Count the words in any text file")
    box.locator("input[name=try_command]").fill(f"touch {marker}")
    box.locator("[data-testid=save-try]").click()
    H.wait_until(lambda: e.try_it("sample")["command"] == f"touch {marker}", msg="try saved")

    # 1. The read-out leads with the result.
    page.evaluate("window.__rungNavigate('readout', {need: 'N-1'})")
    H.wait_view(page, "readout")
    res = page.locator(".rung [data-testid=readout-result]")
    errs = []
    page.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
    try:
        H.wait_until(lambda: res.count() == 1, msg=lambda: str(errs)[:900])
    except AssertionError:
        page.screenshot(path="/tmp/uc42-fail.png")
        raise
    ro = page.locator(".rung [data-testid=readout]")
    order = ro.evaluate("""el => [...el.querySelectorAll('[data-testid^=readout-]')].map(x => x.dataset.testid)""")
    assert order[0] == "readout-result", order
    text = res.inner_text()
    assert e.rung("sample", "N-1")["text"] in text
    rows = ["result-verified", "result-changed", "result-checks", "result-manual", "result-basis"]
    tops = [res.locator(f"[data-testid={r}]").bounding_box()["y"] for r in rows]
    assert tops == sorted(tops), tops
    assert res.locator("[data-verified='S-1.1']").count() == 1
    for f in ("wordcount/count.py", "NOTES.md"):
        assert res.locator(f"[data-testid=result-changed] [data-file='{f}']").count() == 1, res.inner_text()
    assert res.locator("[data-testid=result-checks] [data-check='T-1.1a']").count() == 1
    assert e.result("sample", "N-1")["basis"] in res.locator("[data-testid=result-basis]").inner_text()
    assert res.locator("[data-testid=try-instruction]").inner_text() == "Count the words in any text file"
    assert res.locator("[data-testid=try-command]").inner_text() == f"touch {marker}"
    assert not marker.exists()

    # 3. Evidence: collapsed, then labelled lines with commands, profiles and times.
    tog = res.locator("[data-testid=evidence-toggle]")
    assert tog.get_attribute("aria-expanded") == "false"
    assert res.locator("[data-testid=evidence-lines]").count() == 0
    tog.click()
    lines = res.locator("[data-testid=evidence-lines] [data-label]")
    H.wait_until(lambda: lines.count() >= 2, msg=lambda: res.inner_text())
    labels = {lines.nth(i).get_attribute("data-label") for i in range(lines.count())}
    assert labels <= {"automated", "manual", "model"} and "automated" in labels and "model" in labels, labels
    ev = res.locator("[data-testid=evidence-lines]").inner_text()
    assert "python3 -m unittest -q" in ev
    assert proj["profiles"][0] in ev
    H.evidence(page, 42)

    # 4. Export: open obligations, optional checks and evidence that no longer applies, readable alone.
    (folder / "wordcount" / "extra.py").write_text("X = 1\n")
    page.locator(".rung [data-testid=export]").click()
    path = page.locator(".rung [data-testid=export-path]")
    H.wait_until(lambda: path.count() == 1, msg="exported")
    out = e.export_readout("sample", "N-1")
    md = Path(out["path"]).read_text() if out.get("path") else out["markdown"]
    for head in ("Open obligations:", "Optional checks:", "Evidence that no longer applies:", "## Result"):
        assert head in md, head
    assert "T-1.1a #" in md.split("Evidence that no longer applies:")[1]
    assert not marker.exists()
