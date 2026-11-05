"""Round 5 capabilities at the engine level: project and need lifecycle, onboarding and the sample,
error states, honest attempt outcomes, seen failing, the read-out, conflicts and migration.
Test names carry the use-case IDs of docs/use-cases.md they prove."""

import json
import shutil
import sqlite3
from pathlib import Path

import pytest

from rung_engine import Actor, Engine, RungError
from rung_engine import db
from rung_engine.lifecycle import SAMPLE_NAME
from rung_engine.runner import run_loop
from rung_engine.workers import StubWorker
from support import seed

ROOT = Path(__file__).resolve().parent.parent
AGENT = Actor("agent", "coder")


def tree_bytes(folder: Path) -> dict:
    return {str(p.relative_to(folder)): p.read_bytes() for p in sorted(folder.rglob("*")) if p.is_file()}


# ------------------------------------------------------------------ projects


def test_prj01_defaults_fill_from_the_folder(engine, csv_folder):
    seed.seed_profiles(engine)
    d = engine.project_defaults(str(csv_folder))
    assert d["name"] == "csvtidy" and d["test_command"] == "pytest"
    assert d["profiles"] == [p["name"] for p in engine.profiles() if p["enabled"]]
    p = engine.create_project(folder=str(csv_folder))
    assert (p["name"], p["test_command"], p["profiles"]) == ("csvtidy", "pytest", d["profiles"])


def test_prj02_bad_folder_or_duplicate_name_stores_nothing(engine, tmp_path, csv_folder):
    seed.seed_profiles(engine)
    for folder in (str(tmp_path / "missing"), str(csv_folder / "README.md")):
        with pytest.raises(RungError) as exc:
            engine.create_project("x", folder, "pytest", ["coder"])
        assert exc.value.field == "folder"
    assert engine.projects() == []
    engine.create_project("a", str(csv_folder), "pytest", ["coder"])
    with pytest.raises(RungError) as exc:
        engine.create_project("a", str(csv_folder), "pytest", ["coder"])
    assert exc.value.field == "name" and len(engine.projects()) == 1


def test_prj05_project_change_is_recorded(seeded, tmp_path):
    other = tmp_path / "elsewhere"
    other.mkdir()
    p = seeded.update_project("csvtidy", new_name="csvtidy2", folder=str(other), test_command="pytest -q")
    assert (p["name"], p["folder"], p["test_command"]) == ("csvtidy2", str(other), "pytest -q")
    ev = seeded.events("csvtidy2")[-1]
    assert ev["kind"] == "project_changed" and ev["by"] == "you"
    assert ev["data"]["test_command"] == {"before": "pytest", "after": "pytest -q"}
    assert ev["data"]["name"]["before"] == "csvtidy"
    assert seeded.current_project() == "csvtidy2"
    with pytest.raises(RungError):
        seeded.update_project("csvtidy2", test_command="pytest", actor=AGENT)


def test_prj06_archive_is_read_only_and_restore_keeps_data(seeded):
    before = seeded.tree("notes-sync")
    seeded.archive_project("notes-sync")
    assert [p["name"] for p in seeded.projects()] == ["csvtidy"]
    assert [p["name"] for p in seeded.projects(archived=True)] == ["notes-sync"]
    assert seeded.tree("notes-sync") == before  # readable
    with pytest.raises(RungError) as exc:
        seeded.create_need("notes-sync", "Anything")
    assert exc.value.code == "read_only"
    with pytest.raises(RungError):
        seeded.run_test("notes-sync", "T-1.1a")
    seeded.restore_project("notes-sync")
    assert seeded.tree("notes-sync") == before
    assert {p["name"] for p in seeded.projects()} == {"csvtidy", "notes-sync"}


def test_prj07_delete_removes_rung_data_only(seeded):
    folder = Path(seeded.project("notes-sync")["folder"])
    files = tree_bytes(folder)
    seeded.open_project("notes-sync")
    with pytest.raises(RungError) as exc:
        seeded.delete_project("notes-sync", "notes")
    assert exc.value.field == "confirm"
    out = seeded.delete_project("notes-sync", "notes-sync")
    assert out["deleted"] == "notes-sync" and out["current"] == "csvtidy"
    assert tree_bytes(folder) == files
    assert [p["name"] for p in seeded.projects()] == ["csvtidy"]
    for table in ("rungs", "executions", "runs", "defects", "changes"):
        rows = seeded._q(f"SELECT COUNT(*) FROM {table}")[0][0]
        assert rows >= 0
    assert not seeded._q("SELECT 1 FROM rungs r LEFT JOIN projects p ON p.pk=r.project_pk WHERE p.pk IS NULL")
    assert seeded.events()[-1]["kind"] == "project_deleted"


# ------------------------------------------------------------------ needs


def test_ned03_ned04_retire_and_restore_a_need(seeded):
    e = seeded
    e.edit("csvtidy", "R-2", text="Normalise every date to ISO 8601 with a time zone")
    statuses = {r["rid"]: r["status"] for r in e._q("SELECT rid, status FROM rungs")}
    assert e.tiles("csvtidy")["needs_you"] == 1 and e.tiles("csvtidy")["stale"] >= 1
    with pytest.raises(RungError):
        e.retire_need("csvtidy", "N-1", "")
    e.retire_need("csvtidy", "N-1", "Superseded by the new importer")
    t = e.tiles("csvtidy")
    assert (t["needs_you"], t["stale"], t["requirements"], t["covered"], t["failing"]) == (0, 0, 0, 0, 0)
    assert e.needs_you("csvtidy") == [] and e.tree("csvtidy") == []
    assert e.home("csvtidy")["needs"] == [] and e.home("csvtidy")["done"] == []
    assert e.check_all("csvtidy")["results"] == []
    retired = e.tree("csvtidy", retired=True)
    assert retired[0]["id"] == "N-1" and retired[0]["retired_reason"] == "Superseded by the new importer"
    with pytest.raises(RungError) as exc:
        e.approve("csvtidy", "S-2.1")
    assert exc.value.code == "read_only"
    e.restore_need("csvtidy", "N-1")
    assert {r["rid"]: r["status"] for r in e._q("SELECT rid, status FROM rungs")} == statuses
    assert e.tiles("csvtidy")["needs_you"] == 1
    assert [x["kind"] for x in e.events("csvtidy")][-2:] == ["need_retired", "need_restored"]


def test_ned05_ned06_tst06_readout_and_export(seeded):
    r = seeded.readout("csvtidy", "N-1")
    assert r["need"]["text"] == seed.N1 and r["need"]["version"] == 1
    assert [p["id"] for p in r["plan"]] == ["R-1", "R-2", "R-3"]
    rows = {d["id"]: d for d in r["delivered"]}
    assert rows["R-2"]["proven"] and rows["R-2"]["proof"]["test"] == "T-2.1a"
    assert rows["R-2"]["proof"]["n"] == 3 and rows["R-2"]["proof"]["seen_failing"] is True
    assert rows["R-1"]["proof"]["seen_failing"] is False
    assert not rows["R-3"]["proven"] and rows["R-3"]["reason"] == "not approved"
    assert (r["proven"], r["total"]) == (2, 3)
    seeded.edit("csvtidy", "R-2", text="Normalise every date to ISO 8601 with a time zone")
    assert {d["id"]: d["reason"] for d in seeded.readout("csvtidy", "N-1")["delivered"]}["R-2"] == "not approved"
    seeded.approve("csvtidy", "R-2")
    assert {d["id"]: d["reason"] for d in seeded.readout("csvtidy", "N-1")["delivered"]}["R-2"] == "stale"
    out = seeded.export_readout("csvtidy", "N-1")
    path = Path(out["path"])
    assert path.is_file() and path.read_text() == out["markdown"]
    assert path.parent == Path(seeded.path).parent / "exports"
    assert "\u2014" not in out["markdown"]
    assert "## Intent" in out["markdown"] and "## Plan" in out["markdown"] and "## Delivered" in out["markdown"]
    assert "R-2 Normalise every date to ISO 8601 with a time zone: not proven, stale" in out["markdown"]
    assert "proven by T-1.1a" in out["markdown"]


def test_tst06_seen_failing_never_changes_release(seeded):
    tests = {t["id"]: t for n in seeded.tree("csvtidy") for r in n["children"] for s in r["children"]
             for t in s["children"]}
    assert tests["T-2.1a"]["seen_failing"] is True
    assert tests["T-1.1a"]["seen_failing"] is False
    assert tests["T-2.1b"]["seen_failing"] is None
    assert seeded.check("csvtidy", "S-1.1")["ok"] and seeded.check("csvtidy", "S-2.1")["ok"]


# ------------------------------------------------------------------ onboarding and the sample


def test_onb01_onb03_start_screen_until_dismissed_or_a_project(engine, csv_folder):
    assert engine.onboarding()["start"] is True
    engine.set_onboarding(start_dismissed=True)
    assert engine.onboarding()["start"] is False and engine.projects() == []
    assert engine._q("SELECT COUNT(*) FROM rungs")[0][0] == 0


def test_onb02_onb04_sample_project_and_first_green(engine):
    seed.seed_profiles(engine)
    p = engine.create_sample()
    assert p["name"] == SAMPLE_NAME and p["sample"]
    assert Path(p["folder"]).parent == Path(engine.path).parent / "samples"
    assert engine.current_project() == SAMPLE_NAME
    fg = engine.first_green(SAMPLE_NAME)
    assert [i["done"] for i in fg["items"]] == [True, True, True, True, False]
    assert engine.executions(SAMPLE_NAME, "T-1.1a") == []
    x = engine.run_test(SAMPLE_NAME, "T-1.1a")
    assert x["status"] == "pass", x["output"]
    assert engine.first_green(SAMPLE_NAME)["done"] == 5
    assert engine.check(SAMPLE_NAME, "S-1.1")["ok"]
    engine.set_onboarding(checklist_hidden=True)
    assert engine.first_green(SAMPLE_NAME)["hidden"] is True
    engine.set_onboarding(checklist_hidden=False)
    assert engine.first_green(SAMPLE_NAME)["hidden"] is False


def test_gte07_sec04_demo_reset_touches_only_the_sample(seeded):
    seed.seed_profiles(seeded)
    seeded.create_sample()
    seeded.run_test(SAMPLE_NAME, "T-1.1a")
    seeded.open_project("csvtidy")
    others = {n: seeded.tree(n) for n in ("csvtidy", "notes-sync")}
    seeded.reset_sample()
    assert seeded.executions(SAMPLE_NAME, "T-1.1a") == []
    assert seeded.first_green(SAMPLE_NAME)["done"] == 4
    assert {n: seeded.tree(n) for n in ("csvtidy", "notes-sync")} == others
    assert seeded.current_project() == "csvtidy"


def test_sec04_demo_reset_refuses_a_project_that_only_shares_the_name(engine, csv_folder):
    seed.seed_profiles(engine)
    engine.create_project(SAMPLE_NAME, str(csv_folder), "pytest", ["coder"])
    with pytest.raises(RungError):
        engine.reset_sample()
    assert engine.project(SAMPLE_NAME)["folder"] == str(csv_folder)


# ------------------------------------------------------------------ error states


def test_spc06_failed_draft_counts_as_missing_and_can_be_retried(engine, csv_folder):
    from rung_engine.service import Service
    seed.seed_csvtidy(engine, csv_folder, with_history=False)
    engine.set_setting("drafting", {"kind": "stub", "delay": 0.0, "fail": "the drafting profile timed out"})
    e = engine
    need = e.create_need("csvtidy", "Merge two CSV exports by a shared key")["id"]
    ra = e.add_requirement("csvtidy", need, "Match rows by a chosen key column")["id"]
    rb = e.add_requirement("csvtidy", need, "Report keys found in only one file")["id"]
    e.approve_requirements("csvtidy", need)
    svc = Service(e, inline_runs=True)
    sa = svc.set_authoring("csvtidy", ra, "ai", wait=True)["id"]
    s = e.rung("csvtidy", sa)
    assert s["draft_state"] == "failed" and s["draft_error"] == "the drafting profile timed out"
    st = e.flow("csvtidy", need)["steps"]["specifications"]
    assert not st["can_approve"]
    e.set_setting("drafting", {"kind": "stub", "delay": 0.0})
    svc.regenerate("csvtidy", sa, wait=True)
    assert e.rung("csvtidy", sa)["draft_state"] == "drafted" and "draft_error" not in e.rung("csvtidy", sa)
    # I write instead: the other requirement is written by hand
    e.set_authoring("csvtidy", rb, "human")
    sb = e.write_spec("csvtidy", rb, "Written by hand")
    assert sb["text"] == "Written by hand"


def test_exe04_command_that_cannot_start_records_error(seeded, csv_folder):
    e = seeded
    e.edit_test("csvtidy", "T-1.1a", {"command": "definitely-not-a-command-rung"})
    e.approve("csvtidy", "T-1.1a")
    x = e.run_test("csvtidy", "T-1.1a")
    assert x["status"] == "error" and x["exit_code"] is None
    t = {t["id"]: t for n in e.tree("csvtidy") for r in n["children"] for s in r["children"] for t in s["children"]}
    assert t["T-1.1a"]["result"] == "error"
    assert not e.check("csvtidy", "S-1.1")["ok"]
    items = [i for i in e.needs_you("csvtidy") if i["type"] == "error"]
    assert items and items[0]["id"] == "T-1.1a" and items[0]["n"] == x["n"]
    assert e.tiles("csvtidy")["failing"] == 0
    with pytest.raises(RungError):
        e.raise_defect("csvtidy", "T-1.1a", [x["n"]], "cannot start")
    # fix the cause, run again: a new entry, the Error stays in history
    e.edit_test("csvtidy", "T-1.1a", {"command": "pytest tests/test_sniff.py"})
    e.approve("csvtidy", "T-1.1a")
    y = e.run_test("csvtidy", "T-1.1a")
    assert y["status"] == "pass" and y["n"] == x["n"] + 1
    assert [z["status"] for z in e.executions("csvtidy", "T-1.1a")][:2] == ["pass", "error"]
    assert not [i for i in e.needs_you("csvtidy") if i["type"] == "error"]


def test_exe04_missing_project_folder_records_error(seeded):
    folder = Path(seeded.project("notes-sync")["folder"])
    shutil.rmtree(folder)
    x = seeded.run_test("notes-sync", "T-1.1a")
    assert x["status"] == "error" and "folder not found" in x["output"]


# ------------------------------------------------------------------ honest attempt outcomes


def _outcome_run(e, csv_folder, plans: dict, max_runs: int = 2):
    stub = csv_folder / ".outcome-stub"
    for n, plan in plans.items():
        d = stub / "S-2.1"
        d.mkdir(parents=True, exist_ok=True)
        if isinstance(plan, dict):
            (d / f"attempt-{n}.json").write_text(json.dumps(plan))
    e.save_profiles([{**p, "max_runs": max_runs} if p["name"] == "coder" else p for p in seed.PROFILES])
    e.edit("csvtidy", "R-2", text="Normalise every date to ISO 8601 with a time zone")
    for rid in ("R-2", "S-2.1", "T-2.1a", "T-2.1b"):
        if e.rung("csvtidy", rid)["status"] in ("stale", "draft"):
            e.approve("csvtidy", rid)
    run = e.start_run("csvtidy", "S-2.1", profile="coder")
    return run_loop(e, run["id"], worker=StubWorker(str(stub), delay=0))


def test_run05_needs_input_stops_and_enters_needs_you(seeded, csv_folder):
    r = _outcome_run(seeded, csv_folder, {1: {"outcome": "needs_input", "reason": "Which locale is the default?"}})
    assert r["status"] == "needs_input" and r["reason"] == "Which locale is the default?"
    assert [(a["status"], a["reason"]) for a in r["attempts"]] == [("needs_input", "Which locale is the default?")]
    assert r["attempts"][0]["executions"] == []
    item = [i for i in seeded.needs_you("csvtidy") if i["type"] == "needs_input"]
    assert item and item[0]["run"] == r["id"] and item[0]["text"] == "Which locale is the default?"
    seeded.start_run("csvtidy", "S-2.1")
    assert not [i for i in seeded.needs_you("csvtidy") if i["type"] == "needs_input"]


def test_run06_no_change_after_failing_tests_skips_rerun(seeded, csv_folder):
    dates = csv_folder / "csvtidy" / "dates.py"
    dates.write_text(dates.read_text().replace("day, month = a, b", "month, day = a, b  # swapped"))
    r = _outcome_run(seeded, csv_folder, {1: None, 2: None})
    a1, a2 = r["attempts"]
    assert a1["status"] == "no_change" and [x["status"] for x in a1["executions"]] == ["fail"]
    assert a2["status"] == "no_change" and a2["executions"] == [] and a2["reason"] == "no file changed"
    assert r["status"] == "failed"


def test_run07_vanished_worker_is_unknown(seeded, csv_folder):
    r = _outcome_run(seeded, csv_folder, {1: {"outcome": "unknown"}})
    assert r["status"] == "unknown" and r["attempts"][0]["status"] == "unknown"
    assert r["attempts"][0]["reason"] == "the worker ended without a result"
    assert r["attempts"][0]["executions"] == []


def test_run08_partial_files_a_proposed_rung(seeded, csv_folder):
    r = _outcome_run(seeded, csv_folder, {1: {"outcome": "partial", "capability": "A time zone database"}})
    assert r["status"] == "partial" and r["attempts"][0]["status"] == "partial"
    prop = [i for i in seeded.needs_you("csvtidy") if i["type"] == "proposed"]
    assert prop and prop[0]["text"] == "A time zone database" and prop[0]["parent"] == "R-2"
    assert prop[0]["proposer"] == "coder" and prop[0]["source_chat"] == f"run {r['id']}"
    assert prop[0]["id"] in r["reason"]
    assert seeded.rung("csvtidy", "S-2.1")["status"] == "approved"


def test_res02_dead_runner_leaves_the_run_unknown(seeded):
    run = seeded.start_run("csvtidy", "S-2.1")
    seeded.set_run(run["id"], status="running", pid=999999)
    seeded.begin_attempt(run["id"], 1, "p", "")
    assert seeded.reconcile_runs(lambda pid: False) == [run["id"]]
    r = seeded.run(run["id"])
    assert r["status"] == "unknown" and r["attempts"][0]["status"] == "unknown"


# ------------------------------------------------------------------ conflicts and migration


def test_res03_stale_edit_from_a_second_window_is_refused(seeded):
    v = seeded.rung("csvtidy", "R-3")["version"]
    seeded.edit("csvtidy", "R-3", text="Never drop a row silently", expect_version=v)
    with pytest.raises(RungError) as exc:
        seeded.edit("csvtidy", "R-3", text="Something else", expect_version=v)
    assert exc.value.code == "conflict" and exc.value.status == 409
    assert seeded.rung("csvtidy", "R-3")["text"] == "Never drop a row silently"
    tv = seeded.rung("csvtidy", "T-1.1a")["version"]
    seeded.edit_test("csvtidy", "T-1.1a", {"command": "pytest -q tests/test_sniff.py", "version": tv})
    with pytest.raises(RungError):
        seeded.edit_test("csvtidy", "T-1.1a", {"command": "pytest", "version": tv})


def test_res04_store_v1_opens_intact(tmp_path):
    src = ROOT / "tests" / "fixtures" / "store-v1" / "rung.db"
    path = tmp_path / "rung.db"
    shutil.copyfile(src, path)
    raw = sqlite3.connect(str(path))
    counts = {t: raw.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
              for t in ("projects", "rungs", "executions", "picks", "rung_versions")}
    rows = raw.execute("SELECT rid, status, text, version FROM rungs ORDER BY pk").fetchall()
    raw.close()
    e = Engine(path)
    try:
        assert db.schema_version(e.conn) == db.SCHEMA_VERSION
        for t, n in counts.items():
            assert e._q(f"SELECT COUNT(*) FROM {t}")[0][0] == n
        assert [tuple(r) for r in e._q("SELECT rid, status, text, version FROM rungs ORDER BY pk")] == rows
        assert {p["name"] for p in e.projects()} == {"csvtidy", "notes-sync"}
        assert [x["status"] for x in e.executions("csvtidy", "T-2.1a")] == ["pass", "fail", "fail"]
        assert e.suggest("csvtidy", "S-2.1")["pick"]["profile"] == "writer"
        assert e.current_project() == "csvtidy"
    finally:
        e.close()
    e2 = Engine(path)  # a second open migrates nothing and loses nothing
    assert e2._q("SELECT COUNT(*) FROM rungs")[0][0] == counts["rungs"]
    e2.close()


def test_res04_newer_store_is_refused(tmp_path):
    path = tmp_path / "rung.db"
    Engine(path).close()
    c = sqlite3.connect(str(path))
    c.execute("UPDATE meta SET value='99' WHERE key='schema_version'")
    c.commit()
    c.close()
    with pytest.raises(db.StoreTooNew):
        Engine(path)
