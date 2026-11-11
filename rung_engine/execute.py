"""Running command tests and measuring what a worker changed. Standard library only."""

from __future__ import annotations

import codecs
import difflib
import hashlib
import os
import platform
import re
import signal
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

SKIP_DIRS = {".git", "__pycache__", ".pytest_cache", ".venv", "node_modules", ".mypy_cache", ".rung-stub"}
MAX_SNAPSHOT_FILES = 4000
MAX_DIFF_BYTES = 512 * 1024


@dataclass
class CommandResult:
    exit_code: int | None
    output: str
    timed_out: bool = False
    cancelled: bool = False
    launch_error: str = ""
    duration: float = 0.0


def context_line() -> str:
    os_name = {"Darwin": "macOS", "Linux": "Linux"}.get(platform.system(), platform.system())
    return f"python {sys.version_info.major}.{sys.version_info.minor} · {os_name}"


def git_commit(folder: str | Path) -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"], cwd=str(folder), capture_output=True,
            text=True, timeout=5, env=command_env(),  # git reads the project's config: no inherited keys either
        )
        return out.stdout.strip() if out.returncode == 0 else ""
    except Exception:
        return ""


# A command a person approved runs code from the project being edited, so it gets only what a shell needs, never
# the environment Rung runs in (that holds every Hermes provider key). A project passes more by name only: the
# variables a person lists in its settings.
BASE_ENV = ("PATH", "HOME", "LANG", "TMPDIR")
ENV_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,127}$")


def project_venv(folder) -> Path | None:
    """The project's own virtual environment: VIRTUAL_ENV when it lies inside the project, else .venv or venv."""
    if folder is None:
        return None
    root = Path(folder).expanduser()
    try:
        root_r = root.resolve()
        active = os.environ.get("VIRTUAL_ENV")
        if active and Path(active).resolve().is_relative_to(root_r) and (Path(active) / "pyvenv.cfg").is_file():
            return Path(active)
        for name in (".venv", "venv"):
            if (root / name / "pyvenv.cfg").is_file():
                return root / name
    except OSError:
        return None
    return None


def command_env(folder=None, allow=()) -> dict:
    """The whole environment of a project command: PATH, HOME, LANG, LC_*, TMPDIR, the project's own virtual
    environment, and the variables named in `allow`. Nothing else is inherited."""
    src = os.environ
    env = {k: src[k] for k in BASE_ENV if k in src}
    env.update({k: v for k, v in src.items() if k.startswith("LC_")})
    venv = project_venv(folder)
    if venv is not None:
        env["VIRTUAL_ENV"] = str(venv)
        env["PATH"] = str(venv / "bin") + (os.pathsep + env["PATH"] if env.get("PATH") else "")
    for k in allow or ():
        if isinstance(k, str) and ENV_NAME.match(k) and k in src:
            env[k] = src[k]
    return env


def run_command(
    command: str,
    cwd: str | Path,
    timeout: float = 120,
    output_limit: int = 64_000,
    on_output=None,
    should_cancel=None,
    env: dict | None = None,
) -> CommandResult:
    """Run one shell command, stream its combined output, cap it, honour timeout and cancel."""
    started = time.time()
    run_env = dict(command_env() if env is None else env)  # never the inherited environment
    run_env.setdefault("PYTHONUNBUFFERED", "1")
    # Workers can rewrite a file twice in one second with the same size; never trust cached bytecode.
    run_env.setdefault("PYTHONDONTWRITEBYTECODE", "1")
    try:
        proc = subprocess.Popen(
            command, shell=True, cwd=str(cwd), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL, env=run_env, start_new_session=True,
        )
    except Exception as exc:  # launch failure is an infrastructure error, not a test failure
        return CommandResult(None, f"could not start: {exc}", launch_error=str(exc))

    chunks: list[str] = []
    size = [0]
    truncated = [False]
    lock = threading.Lock()

    def reader():
        # Bounded reads: memory never grows past the limit, and what is kept is a true prefix of the output,
        # even when one line is longer than the whole limit.
        assert proc.stdout is not None
        fd = proc.stdout.fileno()
        dec = codecs.getincrementaldecoder("utf-8")("replace")
        while True:
            raw = os.read(fd, 65536)
            text = dec.decode(raw, final=not raw)
            with lock:
                room = output_limit - size[0]
                if len(text) > room:
                    truncated[0] = True
                    text = text[:max(room, 0)]
                if text:
                    chunks.append(text)
                    size[0] += len(text)
            if not raw:
                break
        proc.stdout.close()

    t = threading.Thread(target=reader, daemon=True)
    t.start()
    timed_out = cancelled = False
    last_push = 0.0
    while True:
        rc = proc.poll()
        now = time.time()
        if on_output and now - last_push > 0.4:
            with lock:
                on_output("".join(chunks))
            last_push = now
        if rc is not None:
            break
        if now - started > timeout:
            timed_out = True
            _kill(proc)
            break
        if should_cancel and should_cancel():
            cancelled = True
            _kill(proc)
            break
        time.sleep(0.1)
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        _kill(proc, hard=True)
    t.join(timeout=5)
    with lock:
        text = "".join(chunks)
    if truncated[0]:
        text += f"\n[output truncated at {output_limit} characters]\n"
    if timed_out:
        text += f"\n[timed out after {int(timeout)}s]\n"
    if cancelled:
        text += "\n[cancelled]\n"
    if on_output:
        on_output(text)
    return CommandResult(
        None if (timed_out or cancelled) else proc.returncode, text, timed_out=timed_out,
        cancelled=cancelled, duration=time.time() - started,
    )


def _kill(proc, hard: bool = False):
    try:
        os.killpg(proc.pid, signal.SIGKILL if hard else signal.SIGTERM)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass


# --- what changed in a folder -------------------------------------------------------------


@dataclass
class Snapshot:
    files: dict = field(default_factory=dict)  # relpath -> (sha1, text or None)


def snapshot(folder: str | Path) -> Snapshot:
    root = Path(folder)
    files = {}
    count = 0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        for name in sorted(filenames):
            if name.endswith((".pyc", ".db", ".db-wal", ".db-shm")):
                continue
            p = Path(dirpath) / name
            rel = p.relative_to(root).as_posix()
            try:
                raw = p.read_bytes()
            except OSError:
                continue
            text = None
            if len(raw) <= MAX_DIFF_BYTES:
                try:
                    text = raw.decode("utf-8")
                except UnicodeDecodeError:
                    text = None
            files[rel] = (hashlib.sha1(raw).hexdigest(), text)
            count += 1
            if count >= MAX_SNAPSHOT_FILES:
                return Snapshot(files)
    return Snapshot(files)


def changed_files(before: Snapshot, after: Snapshot) -> list[dict]:
    """Files added, removed or modified, with added and removed line counts."""
    out = []
    for rel in sorted(set(before.files) | set(after.files)):
        a = before.files.get(rel)
        b = after.files.get(rel)
        if a and b and a[0] == b[0]:
            continue
        a_lines = (a[1] or "").splitlines() if a else []
        b_lines = (b[1] or "").splitlines() if b else []
        plus = minus = 0
        for line in difflib.unified_diff(a_lines, b_lines, lineterm="", n=0):
            if line.startswith("+++") or line.startswith("---"):
                continue
            if line.startswith("+"):
                plus += 1
            elif line.startswith("-"):
                minus += 1
        out.append({"path": rel, "added": plus, "removed": minus,
                    "state": "added" if not a else ("removed" if not b else "modified")})
    return out
