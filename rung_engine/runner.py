"""The supervised develop loop. Runs as its own process so it survives a closed app or a gateway restart.

    python -m rung_engine.runner --db <store> --run <id>

Loop: dispatch the worker, measure what it changed, run the specification's command tests
through the engine, stop on the first attempt where every test passes, otherwise feed the
failure evidence to the next attempt. Never more attempts than the run's budget.
"""

from __future__ import annotations

import argparse
import os
import signal
import sys
import time
from pathlib import Path

from .core import Engine
from .execute import changed_files, git_commit, snapshot
from .workers import AttemptContext, WorkerResult, make_worker

FED_LIMIT = 4000


def build_prompt(engine: Engine, project: str, spec: str, n: int, max_attempts: int, fed: str) -> str:
    s = engine.rung(project, spec)
    req = engine.rung(project, s["parent"])
    need = engine.rung(project, req["parent"])
    tests = engine.command_tests(project, spec)
    lines = [
        f"You are developing specification {spec} of project {project}.",
        f"Need {need['id']}: {need['text']}",
        f"Requirement {req['id']}: {req['text']}",
        f"Specification {spec}: {s['text']}",
    ]
    if s.get("detail"):
        lines.append(f"Approach: {s['detail']}")
    lines.append("The work is done only when these commands pass (Rung runs them itself after you finish):")
    for t in tests:
        lines.append(f"  {t['id']}: {t['command']}")
    lines.append(f"This is attempt {n} of {max_attempts}. Change the code in the current folder. Do not edit the tests.")
    lines.append("If you cannot continue without an answer from a person, print one line: RUNG NEEDS INPUT: <question>")
    lines.append("If the work needs a capability outside this specification, do not build it here; print one line: "
                 "RUNG MISSING CAPABILITY: <capability>")
    if fed:
        lines.append("The previous attempt failed. Test output:")
        lines.append(fed)
    return "\n".join(lines)


def failure_summary(results: list[dict]) -> str:
    parts = []
    for r in results:
        if r["status"] != "pass":
            out = (r.get("output") or "").strip().splitlines()
            tail = "\n".join(out[-30:])
            parts.append(f"{r['test']} #{r['n']} {r['status']} (exit {r['exit_code']}): {r['command']}\n{tail}")
    return "\n\n".join(parts)[-FED_LIMIT:]


def run_loop(engine: Engine, run_id: int, worker=None, hermes_bin: str = "hermes") -> dict:
    run = engine.run(run_id)
    if run["status"] not in ("queued",):
        return run
    project = run["project"]
    spec = run["spec"]
    folder = Path(engine.project(project)["folder"]).expanduser()
    if worker is None:
        import json
        row = engine._q1("SELECT worker FROM runs WHERE pk=?", (run_id,))
        worker = make_worker(json.loads(row["worker"] or "{}"), hermes_bin)
    started = time.time()
    engine.set_run(run_id, status="running", started_at=started, pid=os.getpid())
    deadline = started + run["timeout_s"]
    fed = ""
    max_attempts = run["max_attempts"]
    tests = engine.command_tests(project, spec)
    final = None
    reason = None

    def cancelled():
        return engine.run_cancelled(run_id)

    tested_once = False
    for n in range(1, max_attempts + 1):
        if cancelled():
            final, reason = "cancelled", "cancelled"
            break
        if time.time() > deadline:
            final, reason = "failed", "time budget spent"
            break
        prompt = build_prompt(engine, project, spec, n, max_attempts, fed)
        engine.begin_attempt(run_id, n, prompt, fed)
        before = snapshot(folder)
        ctx = AttemptContext(folder=folder, spec=spec, n=n, prompt=prompt, profile=run["profile"], deadline=deadline,
                             should_cancel=cancelled,
                             on_output=lambda text, n=n: engine.update_attempt(run_id, n, worker_output=text[-20000:]))
        try:
            res = worker.attempt(ctx)
        except Exception as exc:  # a worker crash is recorded as Unknown, never read as a pass or a fail
            res = WorkerResult(output=f"worker error: {exc}", exit_code=None, vanished=True)
        commands, wout = list(res.commands), res.output
        files = changed_files(before, snapshot(folder))
        engine.update_attempt(run_id, n, files_changed=files, commands=commands, worker_output=wout)
        if res.cancelled or cancelled():
            engine.end_attempt(run_id, n, "cancelled", files, commands, wout)
            final, reason = "cancelled", "cancelled"
            break
        if res.vanished:
            reason = "the worker ended without a result"
            engine.end_attempt(run_id, n, "unknown", files, commands, wout, reason=reason)
            final = "unknown"
            break
        if res.outcome == "needs_input":
            reason = res.reason or "the worker needs input"
            engine.end_attempt(run_id, n, "needs_input", files, commands, wout, reason=reason)
            final = "needs_input"
            break
        if res.outcome == "partial":
            cap = res.capability or "an unnamed capability"
            req = engine.rung(project, spec)["parent"]
            prop = engine.propose(project, req, "specification", cap, proposer=run["profile"],
                                  source_chat=f"run {run_id}")
            reason = f"missing capability filed as {prop['id']}: {cap}"
            engine.end_attempt(run_id, n, "partial", files, commands, wout, reason=reason)
            final = "partial"
            break
        if not files and tested_once:
            # Nothing changed since the tests last ran: re-running them would read as work that did not happen.
            engine.end_attempt(run_id, n, "no_change", files, commands, wout, fed_forward=fed,
                               reason="no file changed")
            continue
        results = []
        for t in tests:
            k = engine.begin_execution(project, t["id"], carried_by=run["profile"], run_pk=run_id, attempt=n)
            results.append(engine.perform_execution(project, t["id"], k, should_cancel=cancelled))
        tested_once = True
        for r in results:
            if r["command"] and r["command"] not in commands:
                commands.append(r["command"])
        if any(r["status"] == "cancelled" for r in results) or cancelled():
            engine.end_attempt(run_id, n, "cancelled", files, commands, wout)
            final, reason = "cancelled", "cancelled"
            break
        if results and all(r["status"] == "pass" for r in results):
            engine.end_attempt(run_id, n, "pass", files, commands, wout)
            final, reason = "passed", f"passed on attempt {n}"
            break
        errors = [r for r in results if r["status"] == "error"]
        if errors and not any(r["status"] == "fail" for r in results):
            first = (errors[0].get("output") or "").strip().splitlines()
            reason = f"{errors[0]['test']} could not run: {first[-1] if first else 'no output'}"
            engine.end_attempt(run_id, n, "error", files, commands, wout, reason=reason)
            final = "error"
            break
        fed = failure_summary(results)
        if not files:
            engine.end_attempt(run_id, n, "no_change", files, commands, wout, fed_forward=fed, reason="no file changed")
            continue
        engine.end_attempt(run_id, n, "fail", files, commands, wout, fed_forward=fed)
    else:
        final, reason = "failed", f"no pass in {max_attempts} attempts"
    engine.set_run(run_id, status=final, ended_at=time.time(), reason=reason, commit_ref=git_commit(folder), pid=None)
    return engine.run(run_id)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="rung-runner")
    ap.add_argument("--db", required=True)
    ap.add_argument("--run", type=int, required=True)
    ap.add_argument("--hermes", default="hermes")
    a = ap.parse_args(argv)
    engine = Engine(a.db)

    stopped = []

    def on_term(signum, frame):
        # Stopped from outside (the backend or the machine shutting down), not cancelled by a person:
        # stop the worker the same way a cancel does, then record the run as Unknown.
        try:
            stopped.append(engine.run_cancelled(a.run))  # True when a person had already pressed Stop
            engine.set_run(a.run, cancel=1)
        except Exception:
            pass

    signal.signal(signal.SIGTERM, on_term)
    try:
        r = run_loop(engine, a.run, hermes_bin=a.hermes)
    except Exception as exc:
        engine.set_run(a.run, status="unknown", ended_at=time.time(), reason=f"runner error: {exc}", pid=None)
        raise
    if stopped and not stopped[0]:
        engine.interrupt_run(a.run, "the runner was stopped before the run ended", attempts=("running", "cancelled"))
        r = engine.run(a.run)
    print(f"run {a.run}: {r['status']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
