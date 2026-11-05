"""Rung tools for agents. Agents may read, propose, run tests and check; they can never approve."""

from __future__ import annotations

import json

from .core import RungError

STATUS = {
    "name": "rung_status",
    "description": (
        "Read the Rung design-control ladder of the current project: needs, requirements, "
        "specifications and tests with their status and coverage, plus what needs a human. "
        "Use it before working on code that a Rung specification covers."
    ),
    "parameters": {"type": "object", "properties": {
        "project": {"type": "string", "description": "Project name; default is the last opened project."},
    }},
}

PROPOSE = {
    "name": "rung_propose",
    "description": (
        "Propose a new rung (a requirement under a need, a specification under a requirement, or a test "
        "under a specification). It waits under Needs you until a human accepts or dismisses it. "
        "You cannot approve it yourself."
    ),
    "parameters": {"type": "object", "properties": {
        "parent": {"type": "string", "description": "Id of the parent rung, for example N-1 or R-2."},
        "text": {"type": "string", "description": "One sentence: the proposed rung."},
        "detail": {"type": "string", "description": "Optional detail or rationale."},
        "project": {"type": "string"},
    }, "required": ["parent", "text"]},
}

CHECK = {
    "name": "rung_check",
    "description": (
        "Ask Rung whether a specification is released: approved, nothing upstream stale, and every gating "
        "test has a counting pass. This is the done condition. Pass all=true for every specification."
    ),
    "parameters": {"type": "object", "properties": {
        "spec": {"type": "string", "description": "Specification id, for example S-2.1."},
        "all": {"type": "boolean"},
        "project": {"type": "string"},
    }},
}

RUN_TESTS = {
    "name": "rung_run_tests",
    "description": (
        "Have Rung run the command tests of a specification and record the executions. The engine runs the "
        "commands itself; the result is evidence, not a claim."
    ),
    "parameters": {"type": "object", "properties": {
        "spec": {"type": "string"},
        "project": {"type": "string"},
    }, "required": ["spec"]},
}

SCHEMAS = [STATUS, PROPOSE, CHECK, RUN_TESTS]


def _svc():
    from .host import service
    return service()


def _project(svc, args):
    name = args.get("project") or svc.engine.current_project()
    if not name:
        raise RungError("no Rung project yet")
    return name


def _source_chat(session_id: str = "", user_task: str = "") -> str:
    title = ""
    if session_id:
        try:
            from hermes_state import SessionDB
            title = SessionDB().get_session_title(session_id) or ""
        except Exception:
            title = ""
    if not title and user_task:
        title = " ".join(str(user_task).split())[:80]
    return title or (f"chat {session_id[:8]}" if session_id else "a chat")


PROFILE = {"name": ""}


def _proposer() -> str:
    """The Hermes profile this agent runs as (set at registration from ctx.profile_name)."""
    if PROFILE["name"]:
        return PROFILE["name"]
    import os
    from pathlib import Path
    home = os.environ.get("HERMES_HOME", "")
    if home and Path(home).parent.name == "profiles":
        return Path(home).name
    return "default"


def _wrap(fn):
    def handler(args, session_id: str = "", user_task: str = "", **kwargs):
        try:
            return json.dumps(fn(args or {}, session_id=session_id, user_task=user_task))
        except RungError as exc:
            return json.dumps({"error": str(exc), "code": exc.code})
        except Exception as exc:  # tools always answer with JSON
            return json.dumps({"error": f"{type(exc).__name__}: {exc}"})
    return handler


def status(args, **kw):
    svc = _svc()
    p = _project(svc, args)
    e = svc.engine

    def slim(nodes):
        return [{"id": n["id"], "status": n["status"], "text": n["text"],
                 **({"coverage": n["coverage"]} if "coverage" in n else {}),
                 **({"result": n["result"]} if "result" in n else {}),
                 "children": slim(n.get("children", []))} for n in nodes]

    return {"project": p, "tiles": e.tiles(p), "needs_you": e.needs_you(p), "ladder": slim(e.tree(p))}


def propose(args, session_id="", user_task="", **kw):
    svc = _svc()
    p = _project(svc, args)
    e = svc.engine
    parent = e.rung(p, args["parent"])
    from .core import CHILD_KIND
    kind = CHILD_KIND.get(parent["kind"])
    if not kind:
        raise RungError(f"nothing can be proposed under {args['parent']}")
    r = e.propose(p, args["parent"], kind, args["text"], proposer=_proposer(),
                  source_chat=_source_chat(session_id, user_task), detail=args.get("detail", ""))
    return {"proposed": r["id"], "status": r["status"], "note": "A human must accept it in Rung."}


def check(args, **kw):
    svc = _svc()
    p = _project(svc, args)
    if args.get("all"):
        return svc.engine.check_all(p)
    if not args.get("spec"):
        raise RungError("spec or all is required")
    return svc.engine.check(p, args["spec"])


def run_tests(args, **kw):
    svc = _svc()
    p = _project(svc, args)
    out = []
    for t in svc.engine.command_tests(p, args["spec"]):
        r = svc.engine.run_test(p, t["id"], carried_by=_proposer())
        out.append({"test": t["id"], "n": r["n"], "status": r["status"], "exit_code": r["exit_code"],
                    "output_tail": (r.get("output") or "")[-1500:]})
    return {"spec": args["spec"], "executions": out, "check": svc.engine.check(p, args["spec"])}


HANDLERS = {"rung_status": _wrap(status), "rung_propose": _wrap(propose), "rung_check": _wrap(check),
            "rung_run_tests": _wrap(run_tests)}


def slash(raw_args: str = "", **kwargs) -> str:
    """`/rung` in any chat: the Needs you count and list. `/rung check S-2.1` runs the gate."""
    svc = _svc()
    e = svc.engine
    parts = (raw_args or "").split()
    try:
        p = e.current_project()
        if not p:
            return "Rung: no project yet. Open the Rung pane to create one."
        if parts and parts[0] == "check":
            res = e.check_all(p) if len(parts) < 2 or parts[1] == "--all" else e.check(p, parts[1])
            if "results" in res:
                bad = [r["id"] for r in res["results"] if not r["ok"]]
                return "Rung check: PASS" if res["ok"] else "Rung check: FAIL (" + ", ".join(bad) + ")"
            return (f"Rung check {res['id']}: PASS" if res["ok"]
                    else f"Rung check {res['id']}: FAIL, blocked by " + "; ".join(res["blockers"]))
        t = e.tiles(p)
        lines = [f"Rung {p}: {t['needs_you']} needs you, {t['running']} running, "
                 f"covered {t['covered']} of {t['requirements']}"]
        for item in e.needs_you(p):
            lines.append(f"- {item['type']}: {item['id']} {item['text']}")
        return "\n".join(lines)
    except RungError as exc:
        return f"Rung: {exc}"
