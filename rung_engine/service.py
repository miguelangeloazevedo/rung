"""Service layer: the engine plus the things that take time (drafting jobs, test runs, develop runs).

Used by the REST API, the agent tools, the slash command and the CLI, so every door shares
one set of rules. Long work happens in background threads (drafting, single test runs) or in a
separate runner process (develop loops).
"""

from __future__ import annotations

import os
import subprocess
import sys
import threading
from pathlib import Path

from .core import HUMAN, Actor, Engine, RungError
from .drafting import make_drafter, pause

PLUGIN_ROOT = Path(__file__).resolve().parent.parent


def pid_alive(pid: int) -> bool:
    try:
        os.kill(int(pid), 0)
    except (OSError, ValueError):
        return False
    return True


class Service:
    def __init__(self, engine: Engine, hermes_bin: str = "hermes", python: str | None = None,
                 log_dir: str | Path | None = None, inline_runs: bool = False):
        self.engine = engine
        self.hermes_bin = hermes_bin
        self.python = python or sys.executable
        self.log_dir = Path(log_dir) if log_dir else Path(engine.path).parent / "logs"
        self.inline_runs = inline_runs
        self._threads: list[threading.Thread] = []

    # ------------------------------------------------------------ helpers

    def _bg(self, fn, *args):
        t = threading.Thread(target=fn, args=args, daemon=True)
        t.start()
        self._threads.append(t)
        self._threads = [x for x in self._threads if x.is_alive()]
        return t

    def wait_idle(self, timeout: float = 30):
        for t in list(self._threads):
            t.join(timeout)

    def drafter(self, project: str):
        return make_drafter(self.engine.settings(), self.engine.project(project), self.hermes_bin)

    # ------------------------------------------------------------ needs and requirements

    def suggest_requirements(self, project: str, need_text: str) -> list[str]:
        d = self.drafter(project)
        pause(d)
        return d.suggest_requirements(need_text, self.engine.project(project))

    def suggest_edits(self, project: str, req_rid: str) -> list[dict]:
        r = self.engine.rung(project, req_rid)
        existing = self.engine.suggestions(project, req_rid, "edit") + \
            self.engine.suggestions(project, req_rid, "edit", status="accepted") + \
            self.engine.suggestions(project, req_rid, "edit", status="dismissed")
        if not existing:
            texts = self.drafter(project).suggest_edits(r["text"], self.engine.project(project))
            self.engine.add_suggestions(project, req_rid, "edit", texts)
        return self.engine.suggestions(project, req_rid, "edit")

    # ------------------------------------------------------------ specifications

    def set_authoring(self, project: str, req_rid: str, mode: str, actor: Actor = HUMAN, wait: bool = False):
        spec = self.engine.set_authoring(project, req_rid, mode, actor)
        if mode == "ai" and spec is not None:
            t = self._bg(self._draft_spec, project, req_rid, spec["id"])
            if wait:
                t.join()
        return spec

    def regenerate(self, project: str, spec_rid: str, actor: Actor = HUMAN, wait: bool = False) -> dict:
        spec = self.engine.mark_drafting(project, spec_rid, actor)
        t = self._bg(self._draft_spec, project, spec["parent"], spec_rid)
        if wait:
            t.join()
        return spec

    def _draft_spec(self, project: str, req_rid: str, spec_rid: str):
        try:
            req = self.engine.rung(project, req_rid)
            need = self.engine.rung(project, req["parent"])
            d = self.drafter(project)
            pause(d)
            got = d.derive_spec(need["text"], req["text"], self.engine.project(project))
            self.engine.finish_draft(project, spec_rid, got["text"], got.get("detail", ""), got.get("tags", []),
                                     got.get("required_tags", []),
                                     drafted_by=getattr(d, "profile", "drafting"))
        except Exception as exc:
            if getattr(exc, "code", None) == "not_drafting":
                return  # the specification stopped being drafted meanwhile; a late draft is dropped
            try:
                self.engine.fail_draft(project, spec_rid, str(exc))
            except RungError:
                pass

    def support(self, project: str, req_rid: str, draft: str = "") -> str:
        req = self.engine.rung(project, req_rid)
        need = self.engine.rung(project, req["parent"])
        return self.drafter(project).support_spec(need["text"], req["text"], draft, self.engine.project(project))

    # ------------------------------------------------------------ tests

    def propose_tests(self, project: str, need_rid: str) -> list[dict]:
        """Fill in proposed tests for every specification of the need that has none yet."""
        flow = self.engine.flow(project, need_rid)
        if not flow["steps"]["tests"]["available"]:
            raise RungError("the Tests step is locked", code="locked")
        made = []
        proj = self.engine.project(project)
        d = self.drafter(project)
        for need in self.engine.tree(project):
            if need["id"] != need_rid:
                continue
            for req in need["children"]:
                for spec in req["children"]:
                    if spec["children"] or spec["status"] != "approved":
                        continue
                    for fields in d.propose_tests(spec["text"], req["text"], proj):
                        made.append(self.engine.add_test(project, spec["id"], fields,
                                                         Actor("agent", getattr(d, "profile", "drafting"))))
        return made

    def run_test(self, project: str, test_rid: str, carried_by: str = "engine", wait: bool = False,
                 once_by=None) -> int:
        n = self.engine.begin_execution(project, test_rid, carried_by, once_by=once_by)
        t = self._bg(self.engine.perform_execution, project, test_rid, n)
        if wait:
            t.join()
        return n

    # ------------------------------------------------------------ develop

    def send(self, project: str, spec_rid: str, actor: Actor = HUMAN, profile: str | None = None) -> dict:
        run = self.engine.start_run(project, spec_rid, actor, profile)
        if self.inline_runs:
            from .runner import run_loop
            t = self._bg(run_loop, self.engine, run["id"], None, self.hermes_bin)
            run["_thread"] = t
            return run
        self.log_dir.mkdir(parents=True, exist_ok=True)
        log = self.log_dir / f"run-{run['id']}.log"
        env = dict(os.environ)
        env["PYTHONPATH"] = str(PLUGIN_ROOT) + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
        try:
            with open(log, "ab") as fh:
                proc = subprocess.Popen([self.python, "-m", "rung_engine.runner", "--db", self.engine.path,
                                         "--run", str(run["id"]), "--hermes", self.hermes_bin],
                                        cwd=str(PLUGIN_ROOT), stdout=fh, stderr=subprocess.STDOUT,
                                        stdin=subprocess.DEVNULL, env=env, start_new_session=True)
        except OSError as exc:
            self.engine.interrupt_run(run["id"], f"the runner could not start: {exc}", attempts=("queued", "running"))
            raise RungError(f"the runner could not start: {exc}", code="error", status=500)
        # Reap the runner when it ends, so a finished run never lingers as a zombie of this process.
        threading.Thread(target=proc.wait, name=f"rung-reap-{run['id']}", daemon=True).start()
        self.engine.set_run(run["id"], pid=proc.pid, log_path=str(log))
        return self.engine.run(run["id"])

    def cancel(self, run_id: int) -> dict:
        r = self.engine.cancel_run(run_id)
        return r

    def reconcile(self) -> list[int]:
        return self.engine.reconcile_runs(pid_alive)
