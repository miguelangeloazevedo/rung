"""Workers do the development work of one attempt. Rung supervises them; it never trusts their report.

`stub` is deterministic: for attempt N of specification S it copies `<stub_dir>/<S>/attempt-N/`
over the project folder (and does nothing if that folder does not exist). A file
`<stub_dir>/<S>/attempt-N.json` selects an outcome instead: `{"outcome": "needs_input", "reason": ...}`,
`{"outcome": "partial", "capability": ...}` or `{"outcome": "unknown"}` (the worker vanishes). `hermes` runs
`hermes -p <profile> chat -Q -q <prompt> --max-turns N` in the project folder.
Either way the engine then runs the specification's command tests itself.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import signal
import subprocess
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

from .drafting import scrubbed_env


@dataclass
class AttemptContext:
    folder: Path
    spec: str
    n: int
    prompt: str
    profile: str
    deadline: float
    should_cancel: object = None
    on_output: object = None


@dataclass
class WorkerResult:
    commands: list = field(default_factory=list)
    output: str = ""
    exit_code: int | None = 0
    cancelled: bool = False
    outcome: str = ""      # "" (work done, tests decide) | needs_input | partial
    reason: str = ""       # needs_input: what the worker needs from a human
    capability: str = ""   # partial: the missing capability, filed as a proposed rung
    vanished: bool = False  # the worker ended without reporting a result: Unknown


REPORT = re.compile(r"^RUNG (NEEDS INPUT|MISSING CAPABILITY):\s*(.+)$", re.M)


def parse_report(output: str) -> tuple[str, str]:
    """The last report line a worker printed, as (outcome, text). Workers are told the format."""
    found = REPORT.findall(output or "")
    if not found:
        return "", ""
    kind, text = found[-1]
    return ("needs_input" if kind == "NEEDS INPUT" else "partial"), text.strip()[:500]


class StubWorker:
    def __init__(self, stub_dir: str = "", delay: float = 0.5):
        self.stub_dir = stub_dir
        self.delay = delay

    def attempt(self, ctx: AttemptContext) -> WorkerResult:
        root = Path(self.stub_dir).expanduser() if self.stub_dir else ctx.folder / ".rung-stub"
        src = root / ctx.spec / f"attempt-{ctx.n}"
        end = time.time() + self.delay
        while time.time() < end:  # the delay stands in for work, so a cancel cuts it short like a real worker
            if ctx.should_cancel and ctx.should_cancel():
                return WorkerResult(output="cancelled", exit_code=None, cancelled=True)
            time.sleep(min(0.2, max(0.0, end - time.time())))
        plan = root / ctx.spec / f"attempt-{ctx.n}.json"
        if plan.is_file():
            try:
                spec = json.loads(plan.read_text())
            except (OSError, ValueError):
                spec = {}
            outcome = spec.get("outcome", "")
            if outcome == "unknown":
                return WorkerResult(output="", exit_code=None, vanished=True)
            text = spec.get("reason", "") if outcome == "needs_input" else spec.get("capability", "")
            line = f"RUNG {'NEEDS INPUT' if outcome == 'needs_input' else 'MISSING CAPABILITY'}: {text}"
            if ctx.on_output:
                ctx.on_output(line)
            return WorkerResult(output=line, exit_code=0, outcome=outcome,
                                reason=text if outcome == "needs_input" else "",
                                capability=text if outcome == "partial" else "")
        cmds, lines = [], []
        if src.is_dir():
            for p in sorted(src.rglob("*")):
                if p.is_file():
                    rel = p.relative_to(src)
                    dest = ctx.folder / rel
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(p, dest)
                    cmds.append(f"edit {rel.as_posix()}")
                    lines.append(f"wrote {rel.as_posix()}")
        else:
            lines.append("no change prepared for this attempt")
        if ctx.on_output:
            ctx.on_output("\n".join(lines))
        return WorkerResult(commands=cmds, output="\n".join(lines), exit_code=0)


class HermesWorker:
    def __init__(self, hermes_bin: str = "hermes", max_turns: int = 30):
        self.hermes_bin = hermes_bin
        self.max_turns = max_turns

    def attempt(self, ctx: AttemptContext) -> WorkerResult:
        argv = [self.hermes_bin, "-p", ctx.profile, "chat", "-Q", "-q", ctx.prompt, "--max-turns", str(self.max_turns)]
        shown = f"hermes -p {ctx.profile} chat -Q -q <prompt> --max-turns {self.max_turns}"
        proc = subprocess.Popen(argv, cwd=str(ctx.folder), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                stdin=subprocess.DEVNULL, env=scrubbed_env(ctx.folder), start_new_session=True, text=True,
                                errors="replace", bufsize=1)
        out_lines: list[str] = []
        lock = threading.Lock()

        def pump():
            # Blocking line reads on a thread; the loop below only polls. (A non-blocking pipe read through
            # a text wrapper fails as soon as no output is buffered.)
            assert proc.stdout is not None
            for line in proc.stdout:
                with lock:
                    out_lines.append(line)

        reader = threading.Thread(target=pump, daemon=True)
        reader.start()
        cancelled = False
        seen = 0
        while True:
            with lock:
                n = len(out_lines)
                text = "".join(out_lines)[-20000:] if n != seen else None
            if text is not None:
                seen = n
                if ctx.on_output:
                    ctx.on_output(text)
            if proc.poll() is not None:
                break
            if (ctx.should_cancel and ctx.should_cancel()) or time.time() > ctx.deadline:
                cancelled = bool(ctx.should_cancel and ctx.should_cancel())
                try:
                    os.killpg(proc.pid, signal.SIGTERM)
                except Exception:
                    proc.kill()
                try:
                    proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    os.killpg(proc.pid, signal.SIGKILL)
                    proc.wait(timeout=10)
                break
            time.sleep(0.3)
        reader.join(timeout=5)
        output = "".join(out_lines)[-20000:]
        outcome, text = parse_report(output)
        # Killed by a signal we did not send, or exited with an error and said nothing: no result to read.
        vanished = not cancelled and not outcome and (proc.returncode is None or proc.returncode < 0 or
                                                       (proc.returncode != 0 and not output.strip()))
        return WorkerResult(commands=[shown], output=output, exit_code=proc.returncode, cancelled=cancelled,
                            outcome=outcome, reason=text if outcome == "needs_input" else "",
                            capability=text if outcome == "partial" else "", vanished=vanished)


def make_worker(worker_cfg: dict, hermes_bin: str = "hermes"):
    kind = (worker_cfg or {}).get("kind", "hermes")
    if kind == "stub":
        return StubWorker(worker_cfg.get("stub_dir", ""), float(worker_cfg.get("delay", 0.5)))
    return HermesWorker(hermes_bin, int(worker_cfg.get("max_turns", 30)))
