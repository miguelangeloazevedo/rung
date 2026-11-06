"""The real-profile worker, driven against a fake `hermes` executable (no model call)."""

import stat
import time
from pathlib import Path

from rung_engine.workers import AttemptContext, HermesWorker, StubWorker

FAKE = """#!/bin/sh
# argv: -p <profile> chat -Q -q <prompt> --max-turns N
echo "profile $2"
sleep 0.6
echo "writing merge.py"
printf 'def merge(a, b, key):\\n    return [], {}\\n' > csvtidy_merge.py
sleep "${FAKE_SLEEP:-0.2}"
echo done
"""


def _fake(tmp_path: Path) -> str:
    p = tmp_path / "hermes"
    p.write_text(FAKE)
    p.chmod(p.stat().st_mode | stat.S_IEXEC)
    return str(p)


def test_hermes_worker_streams_output_and_edits(tmp_path):
    folder = tmp_path / "proj"
    folder.mkdir()
    seen = []
    ctx = AttemptContext(folder=folder, spec="S-4.1", n=1, prompt="go", profile="coder",
                         deadline=time.time() + 30, on_output=seen.append)
    r = HermesWorker(_fake(tmp_path)).attempt(ctx)
    assert r.exit_code == 0 and not r.cancelled
    assert "profile coder" in r.output and r.output.rstrip().endswith("done")
    assert (folder / "csvtidy_merge.py").exists()
    assert seen and "profile coder" in seen[0]
    assert r.commands == ["hermes -p coder chat -Q -q <prompt> --max-turns 30"]


def test_hermes_worker_cancel(tmp_path, monkeypatch):
    monkeypatch.setenv("FAKE_SLEEP", "30")
    folder = tmp_path / "proj"
    folder.mkdir()
    t0 = time.time()
    ctx = AttemptContext(folder=folder, spec="S-4.1", n=1, prompt="go", profile="coder",
                         deadline=time.time() + 60, should_cancel=lambda: time.time() - t0 > 1.5)
    r = HermesWorker(_fake(tmp_path)).attempt(ctx)
    assert r.cancelled
    assert time.time() - t0 < 15


def test_stub_worker_delay_honours_cancel(tmp_path):
    t0 = time.time()
    ctx = AttemptContext(folder=tmp_path, spec="S-4.1", n=1, prompt="go", profile="coder",
                         deadline=time.time() + 60, should_cancel=lambda: time.time() - t0 > 0.5)
    r = StubWorker(delay=30).attempt(ctx)
    assert r.cancelled and time.time() - t0 < 3


def test_child_hermes_never_inherits_yolo(tmp_path, monkeypatch):
    """A develop run's Hermes child resolves approvals under Hermes's own single-query rules: YOLO mode
    of the process that started it is not passed on."""
    monkeypatch.setenv("HERMES_YOLO_MODE", "1")
    fake = tmp_path / "hermes"
    fake.write_text('#!/bin/sh\necho "yolo=${HERMES_YOLO_MODE:-unset}"\n')
    fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
    folder = tmp_path / "proj"
    folder.mkdir()
    ctx = AttemptContext(folder=folder, spec="S-4.1", n=1, prompt="go", profile="coder",
                         deadline=time.time() + 30)
    r = HermesWorker(str(fake)).attempt(ctx)
    assert "yolo=unset" in r.output
