"""Architecture review findings A1 to A6, each pinned by a test (docs/reviews/architecture.md)."""

import hashlib
import shutil
import sqlite3
import threading

import pytest

from rung_engine import Engine, RungError, db
from rung_engine.service import Service


def test_a1_concurrent_edits_cannot_both_win(seeded):
    """Two writers that loaded the same version race: exactly one edit lands, the other is a conflict."""
    v = seeded.rung("csvtidy", "R-3")["version"]
    start = threading.Barrier(2)
    results = []

    def writer(text):
        start.wait()
        try:
            seeded.edit("csvtidy", "R-3", text=text, expect_version=v)
            results.append("ok")
        except RungError as e:
            results.append(e.code)

    threads = [threading.Thread(target=writer, args=(f"Never drop a row, writer {i}",)) for i in range(2)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert sorted(results) == ["conflict", "ok"]
    assert seeded.rung("csvtidy", "R-3")["version"] == v + 1


def test_a1_a_second_process_cannot_overwrite(seeded):
    """Another engine on the same store changes the rung between this engine's read and its write."""
    other = Engine(seeded.path)
    r = seeded._rung_row("csvtidy", "R-3")
    other.edit("csvtidy", "R-3", text="Changed from the command line")
    with pytest.raises(RungError) as err:
        with seeded._tx() as c:
            seeded._still_version(c, r)
    assert err.value.code == "conflict"
    other.close()


def test_a2_a_draft_command_never_runs(seeded):
    svc = Service(seeded, inline_runs=True)
    t = seeded.add_test("csvtidy", "S-1.1", {"type": "command", "command": "touch ran.txt"})
    assert seeded.rung("csvtidy", t["id"])["status"] == "draft"
    with pytest.raises(RungError) as err:
        svc.run_test("csvtidy", t["id"])
    assert err.value.code == "not_approved"
    assert not seeded.executions("csvtidy", t["id"])
    from rung_engine import Actor
    # Through the pane's API: refused, unless a person presses Run once in the editor.
    from test_api_cli import call
    assert call(svc, "POST", f"/projects/csvtidy/tests/{t['id']}/run", {})[0] == 409
    with pytest.raises(RungError):
        svc.run_test("csvtidy", t["id"], once_by=Actor("agent", "coder"))
    assert call(svc, "POST", f"/projects/csvtidy/tests/{t['id']}/run", {"once": True})[0] == 200
    svc.wait_idle()
    assert seeded.executions("csvtidy", t["id"])[0]["status"] == "pass"


@pytest.mark.parametrize("code", [126, 127])
def test_a3_a_command_that_cannot_start_is_error_whatever_the_rule(seeded, code):
    t = seeded.add_test("csvtidy", "S-1.1", {"type": "command", "command": "no-such-command-anywhere" if code == 127
                                             else "./not-executable", "pass_rule": {"kind": "exit_code",
                                                                                     "value": code}},
                        status="approved")
    if code == 126:
        import os
        open(os.path.join(seeded.project("csvtidy")["folder"], "not-executable"), "w").write("x")
    ex = seeded.run_test("csvtidy", t["id"])
    assert ex["status"] == "error"


def test_a4_archive_waits_for_a_draft(engine, csv_folder):
    from support import seed
    seed.seed_csvtidy(engine, csv_folder, with_history=False)
    e = engine
    need = e.create_need("csvtidy", "Merge two CSV exports by a shared key")["id"]
    req = e.add_requirement("csvtidy", need, "Match rows by a chosen key column")["id"]
    e.approve_requirements("csvtidy", need)
    spec = e.set_authoring("csvtidy", req, "ai")["id"]
    assert e.rung("csvtidy", spec)["draft_state"] == "drafting"
    with pytest.raises(RungError, match="being drafted"):
        e.archive_project("csvtidy")
    with pytest.raises(RungError, match="being drafted"):
        e.delete_project("csvtidy", confirm="csvtidy")
    e.fail_draft("csvtidy", spec, "stopped")
    assert e.archive_project("csvtidy")["archived"]


def test_a5_a_newer_store_is_refused_unchanged(tmp_path):
    path = tmp_path / "rung.db"
    Engine(str(path)).close()
    conn = sqlite3.connect(str(path))
    conn.execute("UPDATE meta SET value='99' WHERE key='schema_version'")
    conn.execute("DROP INDEX rungs_parent")
    conn.commit()
    conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    conn.close()
    for extra in ("-wal", "-shm"):
        p = tmp_path / f"rung.db{extra}"
        if p.exists():
            p.unlink()
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    with pytest.raises(db.StoreTooNew):
        Engine(str(path))
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before
    conn = sqlite3.connect(str(path))
    assert not conn.execute("SELECT 1 FROM sqlite_master WHERE name='rungs_parent'").fetchone()
    conn.close()


def test_a6_streamed_output_moves_the_revision(seeded):
    t = seeded.add_test("csvtidy", "S-1.1", {"type": "command", "command": "for i in 1 2 3; do echo line $i; "
                                             "sleep 0.3; done"}, status="approved")
    revs = []
    stop = threading.Event()

    def watch():
        while not stop.is_set():
            revs.append(seeded.rev())
            stop.wait(0.05)

    w = threading.Thread(target=watch)
    w.start()
    ex = seeded.run_test("csvtidy", t["id"])
    stop.set()
    w.join()
    assert ex["status"] == "pass" and "line 3" in ex["output"]
    assert len(set(revs)) >= 3
