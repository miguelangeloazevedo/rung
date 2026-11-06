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

CLAIM = {
    "name": "rung_claim",
    "description": (
        "Take an approved Rung specification for this chat before working on it. Rung refuses one that is "
        "not approved, is human only, is held by another chat, or that this profile may not carry, and says why. "
        "While you hold it, Rung blocks declaring it done (rung_report, kanban_complete, a todo marked "
        "completed that names it) until its tests pass."
    ),
    "parameters": {"type": "object", "properties": {
        "spec": {"type": "string", "description": "Specification id, for example S-2.1."},
        "project": {"type": "string"},
    }, "required": ["spec"]},
}

REPORT = {
    "name": "rung_report",
    "description": (
        "Declare a specification you claimed done. Rung refuses while its check fails and names the blocking "
        "rung; the claim then stays open. Once the check passes the claim closes as reported with the passing "
        "executions. A report is never an approval."
    ),
    "parameters": {"type": "object", "properties": {
        "spec": {"type": "string", "description": "Specification id, for example S-2.1."},
        "project": {"type": "string"},
    }, "required": ["spec"]},
}

SCHEMAS = [STATUS, PROPOSE, CHECK, RUN_TESTS, CLAIM, REPORT]


def _svc():
    from .host import service
    return service()


def _arg(args, key: str, required: bool = True, default=None):
    """A text argument: present when required, and text. A clear refusal instead of a crash."""
    v = args.get(key)
    if v is None or v == "":
        if required:
            raise RungError(f"{key} is required", code="bad_request", status=400, field=key)
        return default
    if not isinstance(v, str):
        raise RungError(f"{key} is text", code="bad_request", status=400, field=key)
    return v


def _flag(args, key: str) -> bool:
    v = args.get(key)
    if v is None:
        return False
    if not isinstance(v, bool):
        raise RungError(f"{key} is true or false", code="bad_request", status=400, field=key)
    return v


def _project(svc, args):
    if not isinstance(args, dict):
        raise RungError("arguments are an object", code="bad_request", status=400)
    name = _arg(args, "project", required=False) or svc.engine.current_project()
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


PROFILE = {"ctx": None}


def _proposer() -> str:
    """The Hermes profile this call runs for, read at call time. One gateway process serves several
    profiles, each turn under its own Hermes home, so the name read at registration would label every
    later turn with whichever profile registered last."""
    ctx = PROFILE["ctx"]
    if ctx is not None:
        try:
            name = ctx.profile_name
        except Exception:
            name = ""
        if name and name != "custom":
            return name
    from .host import hermes_home
    home = hermes_home()
    return home.name if home.parent.name == "profiles" else "default"


def _wrap(fn):
    def handler(args, session_id: str = "", user_task: str = "", **kwargs):
        try:
            return json.dumps(fn(args or {}, session_id=session_id, user_task=user_task))
        except RungError as exc:
            return json.dumps({"error": str(exc), "code": exc.code, **({"field": exc.field} if exc.field else {})})
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
    parent_id, text = _arg(args, "parent"), _arg(args, "text")
    detail = _arg(args, "detail", required=False, default="")
    parent = e.rung(p, parent_id)
    from .core import CHILD_KIND
    kind = CHILD_KIND.get(parent["kind"])
    if not kind:
        raise RungError(f"nothing can be proposed under {parent_id}")
    r = e.propose(p, parent_id, kind, text, proposer=_proposer(),
                  source_chat=_source_chat(session_id, user_task), detail=detail)
    return {"proposed": r["id"], "status": r["status"], "note": "A human must accept it in Rung."}


def check(args, **kw):
    svc = _svc()
    p = _project(svc, args)
    if _flag(args, "all"):
        return svc.engine.check_all(p)
    if not args.get("spec"):
        raise RungError("spec or all is required", code="bad_request", status=400, field="spec")
    return svc.engine.check(p, _arg(args, "spec"))


def run_tests(args, **kw):
    svc = _svc()
    p = _project(svc, args)
    spec = _arg(args, "spec")
    out = []
    for t in svc.engine.command_tests(p, spec):
        r = svc.engine.run_test(p, t["id"], carried_by=_proposer())
        out.append({"test": t["id"], "n": r["n"], "status": r["status"], "exit_code": r["exit_code"],
                    "output_tail": (r.get("output") or "")[-1500:]})
    return {"spec": spec, "executions": out, "check": svc.engine.check(p, spec)}


def claim(args, session_id="", user_task="", **kw):
    svc = _svc()
    p = _project(svc, args)
    spec = _arg(args, "spec")
    if not session_id:
        raise RungError("rung_claim needs a chat session", code="bad_request", status=400)
    c = svc.engine.claim(p, spec, session_id, _source_chat(session_id, user_task), _proposer())
    return {"claimed": c["spec"], "project": c["project"], "profile": c["profile"], "chat": c["chat"],
            "check": svc.engine.check(p, spec)}


def report(args, session_id="", **kw):
    svc = _svc()
    p = _project(svc, args)
    spec = _arg(args, "spec")
    c = svc.engine.report(p, spec, session_id)
    return {"reported": c["spec"], "project": c["project"], "proof": c["proof"],
            "note": "Reported done. This is not an approval."}


HANDLERS = {"rung_status": _wrap(status), "rung_propose": _wrap(propose), "rung_check": _wrap(check),
            "rung_run_tests": _wrap(run_tests), "rung_claim": _wrap(claim), "rung_report": _wrap(report)}


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
