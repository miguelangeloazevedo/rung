"""Result first (decisions Round 24, U12): the read-out leads with the outcome and verified behaviours, then what
the newest run changed, the checks run, the manual review left and the code basis; how to try it is declared and
never run; evidence lines are labelled; the export names open obligations, optional checks and stale evidence."""

from rung_engine.api import handle


def test_out01_out03_result_leads_with_the_outcome(seeded, csv_folder, svc):
    e = seeded
    r = e.result("csvtidy", "N-1")
    assert r["outcome"] == e.rung("csvtidy", "N-1")["text"]
    assert [v["spec"] for v in r["verified"]] == [x["spec"] for x in r["verified"]]
    assert r["basis"] and isinstance(r["checks"], list)
    for c in r["checks"]:
        assert c["label"] in ("automated", "manual", "model") and c["by"] and c["at"]
    for x in r["evidence"]:
        assert x["label"] in ("automated", "manual", "model")
    st, out = handle(svc, "GET", "/projects/csvtidy/needs/N-1/result")
    assert st == 200 and out["outcome"] == r["outcome"]
    st, out = handle(svc, "GET", "/projects/csvtidy/needs/S-1.1/result")
    assert st == 400


def test_out02_try_is_declared_and_never_run(seeded, csv_folder, svc):
    e = seeded
    marker = csv_folder / "tried"
    st, out = handle(svc, "POST", "/projects/csvtidy/try",
                     {"instruction": "Run it on samples/dates.csv", "command": f"touch {marker}"})
    assert st == 200
    r = e.result("csvtidy", "N-1")
    assert r["try"] == {"instruction": "Run it on samples/dates.csv", "command": f"touch {marker}"}
    e.export_readout("csvtidy", "N-1")
    assert not marker.exists()  # declared, shown, never run by Rung
    st, out = handle(svc, "POST", "/projects/csvtidy/try", {"run": True})
    assert st == 400


def test_out01_out04_export_names_obligations_optional_and_stale_evidence(seeded, csv_folder):
    e = seeded
    (csv_folder / "csvtidy" / "extra.py").write_text("X = 1\n")  # the code moves on: earlier passes no longer apply
    text = e.export_readout("csvtidy", "N-1")["markdown"]
    for head in ("## Result", "Verified behaviours:", "What changed:", "Open obligations:", "Optional checks:",
                 "Evidence that no longer applies:", "Evidence:", "Code basis:"):
        assert head in text, head
    r = e.result("csvtidy", "N-1")
    assert r["no_longer_applies"], r
    for g in r["no_longer_applies"]:
        assert f"{g['test']} #{g['n']} passed on code" in text
    assert "T-2.1b" in text.split("Optional checks:")[1].split("Evidence that")[0]
    assert any(o["rung"] == "R-3" for o in r["obligations"])
