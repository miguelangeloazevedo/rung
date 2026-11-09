"""Evidence semantics (decisions Round 22): one evaluator decides whether a specification is verified now.

Each test here is one of the false greens an outside assessment reproduced against the engine, or a rule that
keeps the fix honest. Every one of them failed (the gate said ok) before Round 22.
"""

import json
import shutil
import sqlite3

from rung_engine import Engine, evidence
from rung_engine.runner import run_loop
from rung_engine.workers import WorkerResult
from support import seed


def _fresh(engine, folder):
    seed.seed_csvtidy(engine, folder, with_history=False)
    engine.open_project("csvtidy")
    first = engine.run_test("csvtidy", "T-2.1a")
    assert first["status"] == "pass"
    assert engine.check("csvtidy", "S-2.1")["ok"]


def test_required_manual_check_never_run_blocks(engine, csv_folder):
    _fresh(engine, csv_folder)
    m = engine.add_test("csvtidy", "S-2.1", {"type": "manual", "steps": ["Open the output", "Sort by date"]},
                        status="approved")
    assert engine.rung("csvtidy", m["id"])["required"] is True
    chk = engine.check("csvtidy", "S-2.1")
    assert not chk["ok"] and "manual_missing" in chk["codes"]
    assert chk["verification"] == "awaiting_manual"
    assert chk["next_action"]["kind"] == "record_manual_result"


def test_required_manual_pass_waiting_for_approval_blocks(engine, csv_folder):
    _fresh(engine, csv_folder)
    m = engine.add_test("csvtidy", "S-2.1", {"type": "manual", "steps": ["Open the output"]}, status="approved")
    ex = engine.record_manual("csvtidy", m["id"], "pass", "dates sort")
    chk = engine.check("csvtidy", "S-2.1")
    assert not chk["ok"] and chk["codes"] == ["manual_pending"]
    engine.approve_result("csvtidy", m["id"], ex["n"])
    assert engine.check("csvtidy", "S-2.1")["ok"]


def test_optional_manual_check_does_not_block_but_its_failure_does(engine, csv_folder):
    _fresh(engine, csv_folder)  # the fixture's T-2.1b is optional and has never run
    assert engine.rung("csvtidy", "T-2.1b")["required"] is False
    assert engine.check("csvtidy", "S-2.1")["ok"]
    engine.record_manual("csvtidy", "T-2.1b", "fail", "dates sort wrong")
    chk = engine.check("csvtidy", "S-2.1")
    assert not chk["ok"] and chk["codes"] == ["failed"]


def test_code_changed_after_a_pass_is_out_of_date(engine, csv_folder):
    _fresh(engine, csv_folder)
    restore = seed.break_dates(csv_folder)
    chk = engine.check("csvtidy", "S-2.1")
    assert not chk["ok"] and chk["codes"] == ["out_of_date"]
    assert chk["next_action"]["kind"] == "run_tests"
    ex = engine.executions("csvtidy", "T-2.1a")[0]
    assert ex["status"] == "pass" and ex["out_of_date"]  # history keeps the pass; it no longer applies
    assert engine.run_test("csvtidy", "T-2.1a")["status"] == "fail"
    restore()
    # The same content again is the same basis: the newest result (the fail) decides now.
    assert engine.check("csvtidy", "S-2.1")["codes"] == ["failed"]


def test_an_uncommitted_change_counts_and_rungignore_declares_what_does_not(engine, csv_folder):
    _fresh(engine, csv_folder)
    (csv_folder / "NOTES.md").write_text("scratch\n")  # untracked, not ignored: part of the basis
    assert engine.check("csvtidy", "S-2.1")["codes"] == ["out_of_date"]
    (csv_folder / ".rungignore").write_text("NOTES.md\n.rungignore\n")
    assert engine.check("csvtidy", "S-2.1")["ok"]
    (csv_folder / "out.log").write_text("runtime output\n")  # runtime files are never part of the basis
    assert engine.check("csvtidy", "S-2.1")["ok"]


def test_a_newer_error_displaces_an_older_pass(engine, csv_folder, tmp_path):
    _fresh(engine, csv_folder)
    moved = tmp_path / "moved"
    shutil.move(str(csv_folder), moved)
    try:
        assert engine.run_test("csvtidy", "T-2.1a")["status"] == "error"
        chk = engine.check("csvtidy", "S-2.1")
        assert not chk["ok"] and chk["codes"] == ["could_not_verify", "basis_unknown"]  # the error and the unreadable folder
        assert chk["verification"] == "could_not_verify"  # not relabelled as a behaviour failure
    finally:
        shutil.move(str(moved), csv_folder)


def test_a_running_check_is_not_a_fresh_pass(engine, csv_folder):
    _fresh(engine, csv_folder)
    n = engine.begin_execution("csvtidy", "T-2.1a")
    chk = engine.check("csvtidy", "S-2.1")
    assert not chk["ok"] and chk["codes"] == ["checking"]
    engine.cancel_execution("csvtidy", "T-2.1a", n)


def test_a_cancelled_rerun_leaves_no_evidence_and_the_earlier_pass_must_still_match_the_code(engine, csv_folder):
    _fresh(engine, csv_folder)
    n = engine.begin_execution("csvtidy", "T-2.1a")
    engine.cancel_execution("csvtidy", "T-2.1a", n)
    assert engine.check("csvtidy", "S-2.1")["ok"]  # the code is what the earlier pass ran on
    restore = seed.break_dates(csv_folder)
    try:
        assert engine.check("csvtidy", "S-2.1")["codes"] == ["out_of_date"]
    finally:
        restore()


class WeakeningWorker:
    """Changes only the acceptance test, not the broken code."""

    def attempt(self, ctx):
        (ctx.folder / "tests" / "test_dates.py").write_text("def test_ambiguous_locale():\n    assert True\n")
        return WorkerResult(output="test changed; implementation unchanged", exit_code=0)


def test_a_worker_that_weakens_its_test_does_not_get_a_pass(engine, csv_folder):
    _fresh(engine, csv_folder)
    seed.break_dates(csv_folder)
    run = engine.start_run("csvtidy", "S-2.1", profile="coder")
    res = run_loop(engine, run["id"], worker=WeakeningWorker())
    assert res["status"] == "needs_input", res
    assert "tests/test_dates.py (changed)" in res["reason"]
    chk = engine.check("csvtidy", "S-2.1")
    assert not chk["ok"] and "verification_changed" in chk["codes"]
    assert chk["next_action"]["kind"] == "review_test_files"
    newest = engine.executions("csvtidy", "T-2.1a")[0]
    # It ran (the person sees what the changed test says) and passed; that pass counts for nothing.
    assert newest["status"] == "pass" and newest["reason"] == "verification_changed"
    assert newest["output"].startswith("judged by files changed since the test was approved: tests/test_dates.py")
    assert engine.protected("csvtidy", "T-2.1a")["changed"] == [{"path": "tests/test_dates.py", "change": "changed"}]
    # A person can still accept the change deliberately; the next result is then judged by the new test.
    engine.accept_test_files("csvtidy", "T-2.1a")
    assert engine.protected("csvtidy", "T-2.1a")["changed"] == []
    assert engine.run_test("csvtidy", "T-2.1a")["status"] == "pass"


def test_runner_configuration_is_protected_too(engine, csv_folder):
    _fresh(engine, csv_folder)
    (csv_folder / "conftest.py").write_text("collect_ignore = ['tests']\n")
    engine.run_test("csvtidy", "T-2.1a")
    newest = engine.executions("csvtidy", "T-2.1a")[0]
    assert newest["reason"] == "verification_changed" and "conftest.py (created)" in newest["output"]
    assert "verification_changed" in engine.check("csvtidy", "S-2.1")["codes"]


def test_a_file_changed_while_the_check_ran_does_not_count(engine, csv_folder):
    _fresh(engine, csv_folder)
    engine.edit_test("csvtidy", "T-2.1a", {"command": "pytest tests/test_dates.py::test_ambiguous_locale && "
                                                      "echo x >> csvtidy/__init__.py"})
    engine.approve("csvtidy", "T-2.1a")
    ex = engine.run_test("csvtidy", "T-2.1a")
    assert ex["status"] == "pass" and ex["reason"] == "changed_during_check" and ex["out_of_date"]
    assert engine.check("csvtidy", "S-2.1")["codes"] == ["out_of_date"]


def test_a_check_that_writes_its_own_output_file_still_counts(engine, csv_folder):
    _fresh(engine, csv_folder)
    engine.edit_test("csvtidy", "T-2.1a", {"command": "pytest tests/test_dates.py::test_ambiguous_locale && "
                                                      "echo done > report.txt"})
    engine.approve("csvtidy", "T-2.1a")
    ex = engine.run_test("csvtidy", "T-2.1a")
    assert ex["status"] == "pass" and ex["reason"] == "" and not ex["out_of_date"]
    assert engine.check("csvtidy", "S-2.1")["ok"]


def test_seen_failing_is_for_this_version_of_the_test(engine, csv_folder):
    seed.seed_csvtidy(engine, csv_folder)  # history: two fails, then a pass
    engine.open_project("csvtidy")
    tree = {r["id"]: r for r in _walk(engine.tree("csvtidy"))}
    assert tree["T-2.1a"]["seen_failing"] is True
    engine.edit_test("csvtidy", "T-2.1a", {"command": "pytest tests/test_dates.py"})
    engine.approve("csvtidy", "T-2.1a")
    engine.run_test("csvtidy", "T-2.1a")
    tree = {r["id"]: r for r in _walk(engine.tree("csvtidy"))}
    assert tree["T-2.1a"]["seen_failing"] is False  # the old failures were of a different test


def test_a_develop_run_rechecks_the_passes_it_made_out_of_date(engine, csv_folder):
    seed.seed_built(engine, csv_folder)
    assert engine.check("csvtidy", "S-1.1")["ok"]

    class Touching:
        def attempt(self, ctx):
            (ctx.folder / "csvtidy" / "dropped.py").write_text("def count(rows):\n    return 0\n")
            return WorkerResult(output="wrote dropped.py", exit_code=0)

    engine.edit_test("csvtidy", "T-3.1a", {"command": "true"})
    engine.approve("csvtidy", "T-3.1a")
    run = engine.start_run("csvtidy", "S-3.1", profile="coder")
    res = run_loop(engine, run["id"], worker=Touching())
    assert res["status"] == "passed", res
    assert "checked again" in res["reason"]
    assert engine.check("csvtidy", "S-1.1")["ok"] and engine.check("csvtidy", "S-2.1")["ok"]
    assert engine.executions("csvtidy", "T-1.1a")[0]["carried_by"] == "engine"


def test_one_evaluator_for_gate_tree_tiles_and_check_all(engine, csv_folder):
    _fresh(engine, csv_folder)
    seed.break_dates(csv_folder)
    evidence.forget()
    spec = next(r for r in _walk(engine.tree("csvtidy")) if r["id"] == "S-2.1")
    assert spec["released"] is False and spec["verification"] == "out_of_date"
    assert engine.coverage("csvtidy", "R-2") == "open"
    assert not engine.check_all("csvtidy")["ok"]
    assert engine.check("csvtidy", "S-2.1")["ok"] is False


def test_a_store_from_before_round_22_keeps_its_meaning(tmp_path, csv_folder):
    path = tmp_path / "old.db"
    e = Engine(path)
    seed.seed_csvtidy(e, csv_folder, with_history=False)
    e.open_project("csvtidy")
    e.run_test("csvtidy", "T-2.1a")
    e.close()
    con = sqlite3.connect(path)
    # Make it look like a schema 3 store: no required flag, results without a basis.
    con.execute("UPDATE rungs SET data = json_remove(data, '$.required') WHERE kind = 'test'")
    con.execute("UPDATE executions SET basis_start = '', basis_end = ''")
    con.execute("UPDATE meta SET value = '3' WHERE key = 'schema_version'")
    con.commit()
    before = con.execute("SELECT pk, data FROM rungs ORDER BY pk").fetchall()
    con.close()
    e = Engine(path)
    try:
        # RES-04: the upgrade rewrites no stored value; the old manual test reads as optional without a key.
        assert [(r["pk"], r["data"]) for r in e._q("SELECT pk, data FROM rungs ORDER BY pk")] == before
        assert e.rung("csvtidy", "T-2.1b")["required"] is False
        e.edit_test("csvtidy", "T-2.1b", {"steps": ["Open the output", "Sort by date"]})
        assert e.rung("csvtidy", "T-2.1b")["required"] is False  # an edit keeps the old meaning unless asked
        v = e.verification("csvtidy", "S-2.1")
        assert v["ok"] and "legacy" in v["flags"]
    finally:
        e.close()


def test_the_protected_files_of_a_command(tmp_path):
    root = tmp_path / "p"
    (root / "tests").mkdir(parents=True)
    (root / "app").mkdir()
    (root / "tests" / "test_a.py").write_text("x")
    (root / "tests" / "helper.py").write_text("x")
    (root / "app" / "core.py").write_text("x")
    (root / "pytest.ini").write_text("[pytest]\n")
    f = evidence.protected_files("pytest tests/test_a.py::test_one -q", root, root)
    assert f == ["pytest.ini", "tests/test_a.py"]
    f = evidence.protected_files("python3 -c \"from tests.helper import x; print(x)\"", root, root)
    assert "tests/helper.py" in f and "app/core.py" not in f
    assert "tests/helper.py" in evidence.protected_files("pytest", root, root)
    assert "tests/new_test.py" in evidence.protected_files("python3 tests/new_test.py", root, root)


def _walk(nodes):
    for n in nodes:
        yield n
        yield from _walk(n.get("children", []))


def test_the_basis_honours_gitignore_without_starting_git(tmp_path, monkeypatch):
    import subprocess
    root = tmp_path / "p"
    (root / "src").mkdir(parents=True)
    (root / "out").mkdir()
    (root / "src" / "app.py").write_text("x = 1\n")
    (root / "src" / "secret.env").write_text("k\n")
    (root / "out" / "big.bin").write_text("data\n")
    (root / ".gitignore").write_text("out/\n*.env\n")
    (root / "src" / ".gitignore").write_text("local.py\n")
    (root / "src" / "local.py").write_text("y\n")

    def no_process(*a, **k):
        raise AssertionError("the basis must not start a process")
    monkeypatch.setattr(subprocess, "run", no_process)
    monkeypatch.setattr(subprocess, "Popen", no_process)
    assert evidence.project_files(root) == [".gitignore", "src/.gitignore", "src/app.py"]
    before = evidence.basis(root, fresh=True)
    (root / "out" / "big.bin").write_text("changed\n")
    assert evidence.basis(root, fresh=True) == before
    (root / "src" / "app.py").write_text("x = 2\n")
    assert evidence.basis(root, fresh=True) != before


def test_an_option_before_a_named_file_does_not_protect_the_whole_suite(tmp_path):
    root = tmp_path / "p"
    (root / "tests").mkdir(parents=True)
    for n in ("test_api.py", "test_page.py"):
        (root / "tests" / n).write_text("def test_x():\n    pass\n")
    assert evidence.protected_files("pytest -q tests/test_api.py", root, root) == ["tests/test_api.py"]
    assert evidence.protected_files("pytest -q", root, root) == ["tests/test_api.py", "tests/test_page.py"]


def test_no_positive_result_when_the_code_cannot_be_read(engine, csv_folder, monkeypatch):
    _fresh(engine, csv_folder)
    monkeypatch.setattr(evidence, "MAX_FILES", 3)  # the project is now too large to read whole
    evidence.forget()
    chk = engine.check("csvtidy", "S-2.1")
    assert not chk["ok"] and chk["codes"] == ["basis_unknown"] and chk["verification"] == "could_not_verify"
    assert chk["next_action"]["kind"] == "repair_project_folder"
    monkeypatch.setattr(evidence, "MAX_FILES", 20000)
    evidence.forget()
    assert engine.check("csvtidy", "S-2.1")["ok"]


def test_a_missing_project_folder_never_verifies(engine, csv_folder):
    _fresh(engine, csv_folder)
    shutil.move(str(csv_folder), str(csv_folder) + "-moved")
    evidence.forget()
    try:
        chk = engine.check("csvtidy", "S-2.1")
        assert not chk["ok"] and "basis_unknown" in chk["codes"]
    finally:
        shutil.move(str(csv_folder) + "-moved", str(csv_folder))


def test_enforcement_is_reported_apart_from_verification(engine, csv_folder, tmp_path):
    """R05: a session with no claim is unbound, a claim is enforced (and names whether it is verified now), an
    unreadable store is degraded; none of these is a verification result."""
    from pathlib import Path
    from rung_engine import hook
    store = Path(engine.path)
    assert hook.status("", store)["enforcement"] == "unbound"
    assert hook.status("s-1", store) == {"session": "s-1", "enforcement": "unbound", "reason": "no open claim",
                                         "claims": []}
    _fresh(engine, csv_folder)
    engine.claim("csvtidy", "S-2.1", "s-1", "chat", "coder")
    st = hook.status("s-1", store)
    assert st["enforcement"] == "enforced" and st["claims"][0]["spec"] == "S-2.1" and st["claims"][0]["verified"]
    seed.break_dates(csv_folder)
    evidence.forget()
    st = hook.status("s-1", store)
    assert st["enforcement"] == "enforced" and not st["claims"][0]["verified"]
    assert hook.status("s-1", tmp_path / "missing.db")["enforcement"] == "degraded"
    garbage = tmp_path / "garbage.db"
    garbage.write_text("not a database")
    assert hook.status("s-1", garbage)["enforcement"] == "degraded"
    # the hook itself lets an unrelated tool through whatever the store says
    assert hook.decide("terminal", {}, "s-1", garbage) is None


def test_the_verdict_memo_sees_a_commit_from_another_process(engine, csv_folder):
    """The runner writes from its own connection; the pane's engine must not keep an old verdict."""
    _fresh(engine, csv_folder)
    assert engine.check("csvtidy", "S-2.1")["ok"]
    other = Engine(engine.path)
    try:
        other.record_manual("csvtidy", "T-2.1b", "fail", "broken on en_GB")
    finally:
        other.close()
    assert not engine.check("csvtidy", "S-2.1")["ok"]
    assert engine.tree("csvtidy")  # and the cached path agrees with the fresh one
    assert [s for n in engine.tree("csvtidy") for r in n["children"] for s in r["children"]
            if s["id"] == "S-2.1"][0]["released"] is False
