"""Workers do the development work of one attempt. Rung supervises them; it never trusts their report.

`stub` is deterministic: for attempt N of specification S it copies `<stub_dir>/<S>/attempt-N/`
over the project folder (and does nothing if that folder does not exist). `hermes` runs
`hermes -p <profile> chat -Q -q <prompt> --max-turns N` in the project folder.
Either way the engine then runs the specification's command tests itself.
"""

from __future__ import annotations

import os
import shutil
import signal
import subprocess
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


class StubWorker:
    def __init__(self, stub_dir: str = "", delay: float = 0.5):
        self.stub_dir = stub_dir
        self.delay = delay

    def attempt(self, ctx: AttemptContext) -> WorkerResult:
        root = Path(self.stub_dir).expanduser() if self.stub_dir else ctx.folder / ".rung-stub"
        src = root / ctx.spec / f"attempt-{ctx.n}"
        time.sleep(self.delay)
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
                                stdin=subprocess.DEVNULL, env=scrubbed_env(), start_new_session=True, text=True)
        out_lines: list[str] = []
        cancelled = False
        assert proc.stdout is not None
        os.set_blocking(proc.stdout.fileno(), False)
        while True:
            chunk = proc.stdout.read()
            if chunk:
                out_lines.append(chunk)
                if ctx.on_output:
                    ctx.on_output("".join(out_lines)[-20000:])
            if proc.poll() is not None:
                rest = proc.stdout.read() or ""
                out_lines.append(rest)
                break
            if (ctx.should_cancel and ctx.should_cancel()) or time.time() > ctx.deadline:
                cancelled = bool(ctx.should_cancel and ctx.should_cancel())
                try:
                    os.killpg(proc.pid, signal.SIGTERM)
                except Exception:
                    proc.kill()
                proc.wait(timeout=10)
                break
            time.sleep(0.3)
        return WorkerResult(commands=[shown], output="".join(out_lines)[-20000:], exit_code=proc.returncode,
                            cancelled=cancelled)


def make_worker(worker_cfg: dict, hermes_bin: str = "hermes"):
    kind = (worker_cfg or {}).get("kind", "hermes")
    if kind == "stub":
        return StubWorker(worker_cfg.get("stub_dir", ""), float(worker_cfg.get("delay", 0.5)))
    return HermesWorker(hermes_bin, int(worker_cfg.get("max_turns", 30)))
