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
from .drafting import DraftFailed, make_drafter, pause
from .bot import KINDS, SUGGEST_COUNT

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

    def drafter(self, project: str, profile: str | None = None):
        return make_drafter(self.engine.settings(), self.engine.project(project), self.hermes_bin, profile)

    # ------------------------------------------------------------ bot help (Round 13): proposals only

    def _bot(self, job_id: int, d, work, wait: bool):
        """Run one bot job in the background: the drafter stops when the person cancels, and a result
        that arrives after a cancel is dropped by the engine's conditional write."""
        cancelled = lambda: self.engine.bot_cancelled(job_id)  # noqa: E731
        d.should_cancel = cancelled

        def go():
            try:
                pause(d, cancelled)
                self.engine.finish_bot(job_id, work(d))
            except Exception as exc:
                if not cancelled():
                    self.engine.fail_bot(job_id, str(exc) or exc.__class__.__name__)
        t = self._bg(go)
        if wait:
            t.join()
        return self.engine.bot_job(job_id)

    def _drafter_name(self, d) -> str:
        return getattr(d, "profile", "") or "drafting"

    def place(self, project: str, text: str, wait: bool = False) -> dict:
        """Which rung a pasted text is and where it goes. The engine checks the answer; an invalid one is
        returned with its reason and offered to no one."""
        text = (text or "").strip()
        if not text:
            raise RungError("paste the text to place", code="bad_request", status=400, field="text")
        d = self.drafter(project)
        targets = self.engine.place_targets(project)
        job = self.engine.begin_bot(project, "place", None, self._drafter_name(d), {"text": text})

        def work(d):
            got = d.place(text, targets, self.engine.project(project))
            kind = str(got.get("kind") or "").strip().lower()
            parent = got.get("parent") or None
            if parent:
                try:
                    parent = self.engine.rung(project, str(parent))["id"]
                except RungError:
                    pass
            why_not = self.engine.check_place(project, kind, parent)
            return {"kind": kind, "parent": parent, "why": str(got.get("why") or "").strip(),
                    "valid": not why_not, "reason": why_not, "text": text}
        return self._bot(job, d, work, wait)

    def draft(self, project: str, kind: str, parent: str | None = None, fields: dict | None = None,
              wait: bool = False) -> dict:
        """Fields for a new rung from its parent chain. The form fills only empty fields; nothing is saved."""
        if kind not in KINDS:
            raise RungError(f"{kind} is not a rung kind", code="bad_request", status=400)
        why_not = self.engine.check_place(project, kind, parent) if (kind != "need" or parent) else ""
        if why_not:
            raise RungError(why_not, code="bad_request", status=400)
        d = self.drafter(project)
        chain = self.engine.chain(project, parent) if parent else []
        typed = {k: v for k, v in (fields or {}).items() if isinstance(v, str)}
        job = self.engine.begin_bot(project, "draft", parent, self._drafter_name(d), {"kind": kind, "fields": typed})

        def work(d):
            got = d.draft(kind, chain, typed, self.engine.project(project))
            return {"kind": kind, "parent": parent,
                    "fields": {k: (v if isinstance(v, str) else list(v)) for k, v in dict(got).items()}}
        return self._bot(job, d, work, wait)

    def suggest(self, project: str, need_rid: str, wait: bool = False) -> dict:
        """Three requirements the need may be missing, from the best placed profile. With no eligible
        profile nothing runs and each profile is listed with its reason."""
        choice = self.engine.suggest_choice(project, need_rid)
        if choice["chosen"] is None:
            return {"job": None, "choice": choice}
        need = self.engine.rung(project, need_rid)
        if need["status"] != "approved":
            raise RungError(f"{need['id']} must be approved first", code="locked")
        profile = choice["chosen"]["profile"]
        reqs = [r for r in self.engine.chain_children(project, need["id"])]
        d = self.drafter(project, profile)
        need_pk = self.engine._rung_row(project, need["id"])["pk"]
        job = self.engine.begin_bot(project, "suggest", need["id"], profile, {"choice": choice},
                                    self.engine._req_basis(need_pk))

        def work(d):
            got = [t.strip() for t in d.suggest_missing(need["text"], [r["text"] for r in reqs],
                                                        self.engine.project(project)) if str(t).strip()]
            have = {r["text"].strip().lower() for r in reqs}
            got = [t for t in dict.fromkeys(got) if t.lower() not in have]
            if len(got) < SUGGEST_COUNT:
                raise DraftFailed(f"{profile} returned {len(got)} new requirements, not {SUGGEST_COUNT}")
            return {"items": [{"text": t, "status": "open"} for t in got[:SUGGEST_COUNT]], "choice": choice}
        return {"job": self._bot(job, d, work, wait), "choice": choice}

    def cancel_bot(self, job_id: int) -> dict:
        return self.engine.cancel_bot(job_id)

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
