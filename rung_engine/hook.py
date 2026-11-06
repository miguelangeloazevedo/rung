"""The done hook: a `pre_tool_call` hook that refuses to let a chat declare a claimed specification done
while Rung's check for it fails.

Blocked, while a claimed specification of the calling session is not released:
    rung_report for that specification;
    kanban_complete from the session (it holds a failing claim);
    todo_list setting an item to completed whose id or content names that specification, or whose id
    named it in an earlier todo_list call of the same session.

Everything else passes untouched. No model call: the hook opens the store read only and asks the engine's
check. Any failure to read the store lets the call through; the doctor reports the store.
"""

from __future__ import annotations

import threading
from pathlib import Path

WATCHED = frozenset({"rung_report", "kanban_complete", "todo_list"})

# Per session: todo id -> what that id has carried in the session's todo_list calls: every rung id any of
# its contents named (an id that once named a specification keeps counting, whatever it says later; adding
# more never pushes one out) and the content it had when it was last let through as completed. In memory
# only: the hook never writes. Sessions are kept most recently used first; past the limit the least
# recently used session goes, one that has held a claim only when no other is left.
_TODOS: dict[str, dict[str, dict]] = {}
_HELD: set[str] = set()  # sessions seen holding a claim
_MAX_RIDS = 500
ALL = "\u0000every specification"  # an id past _MAX_RIDS names every specification
_TODOS_LOCK = threading.Lock()
_MAX_SESSIONS = 5000


def _store() -> Path | None:
    try:
        from .host import store_path
        return store_path()
    except Exception:
        return None


def _session_claims(session_id: str, store: Path | None = None) -> tuple[list[dict], str]:
    """Open claims of the session with their checks, and the open project (what a tool call without a
    project acts on), from a read-only view of the store."""
    path = store if store is not None else _store()
    if path is None or not Path(path).is_file():
        return [], ""
    from .core import Engine
    eng = Engine(path, readonly=True)
    try:
        return eng.session_claims(session_id), eng.current_project() or ""
    finally:
        eng.close()


def _message(claim: dict) -> str:
    blockers = claim["check"].get("blockers") or []
    return (f"Blocked by Rung: {claim['spec']} is not released. " + "; ".join(blockers)
            + f". Claimed in {claim['project']}; run its tests and check again before declaring it done.")


def _names(text: str, rid: str) -> bool:
    from .claims import ClaimsMixin
    return ClaimsMixin.names_spec(text or "", rid)


def _todo_items(args) -> list[dict]:
    """The todo items as the todo tool will read them: Hermes turns a JSON text into a list after this
    hook has run, so a text is read the same way here."""
    todos = args.get("todos") if isinstance(args, dict) else None
    if isinstance(todos, str):
        import json
        try:
            todos = json.loads(todos)
        except ValueError:
            return []
    return [t for t in todos if isinstance(t, dict)] if isinstance(todos, list) else []


def _content(t: dict) -> str:
    """The content as the todo tool stores it: text as is, anything else as its text form."""
    c = t.get("content")
    if c is None:
        return ""
    return (c if isinstance(c, str) else str(c)).strip()


def _completed(t: dict) -> bool:
    return str(t.get("status", "")).strip().lower() == "completed"


def _session(session_id: str) -> dict:
    """The session's record, moved to most recently used. Called with the lock held."""
    seen = _TODOS.pop(session_id, None)
    if seen is None:
        seen = {}
        while len(_TODOS) >= _MAX_SESSIONS:
            # least recently used first; a session whose todos named no rung before one that did, and a
            # session never seen holding a claim before one that was
            idle = next((k for k in _TODOS if k not in _HELD and not any(r["rids"] for r in _TODOS[k].values())),
                        None) or next((k for k in _TODOS if k not in _HELD), None) or next(iter(_TODOS))
            _TODOS.pop(idle)
            _HELD.discard(idle)
    _TODOS[session_id] = seen
    return seen


def _remember(session_id: str, items: list[dict], allowed: bool) -> None:
    """Record the ids each todo named; when the call was let through, also what it completed."""
    from .claims import rids_in
    with _TODOS_LOCK:
        seen = _session(session_id)
        for t in items:
            tid = str(t.get("id", "")).strip()
            if not tid:
                continue
            rec = seen.setdefault(tid, {"rids": [], "done": None})
            text = _content(t)
            for rid in rids_in(text):
                if rid not in rec["rids"]:
                    if len(rec["rids"]) < _MAX_RIDS:
                        rec["rids"].append(rid)
                    else:
                        rec["all"] = True  # past the limit the id counts as naming every specification
            if allowed:
                rec["done"] = (text or None) if _completed(t) else None


def _completing(session_id: str, items: list[dict]) -> list[tuple[str, str]]:
    """(id, text) of each item this call declares completed, text being its id, its content now and every
    rung id the id named earlier in the session. An item re-sent completed with the same, non-empty content
    it had when it was let through declares nothing new and is left out; a bare id always counts (CLM-06)."""
    with _TODOS_LOCK:
        seen = {k: {"rids": list(v["rids"]), "done": v["done"], "all": v.get("all", False)}
                for k, v in _TODOS.get(session_id, {}).items()}
    out = []
    for t in items:
        if not _completed(t):
            continue
        tid = str(t.get("id", "")).strip()
        rec = seen.get(tid, {"rids": [], "done": None, "all": False})
        now = _content(t)
        if now and rec["done"] is not None and now == rec["done"]:
            continue
        # Each part is read on its own (joined by a separator no id spans): a short id followed by
        # content starting with a number does not read as one id.
        out.append((tid, " | ".join(x for x in [tid, now, *rec["rids"], ALL if rec["all"] else ""] if x)))
    return out


def decide(tool_name: str, args, session_id: str = "", store: Path | None = None) -> str | None:
    """The block message for this call, or None to let it run."""
    if tool_name not in WATCHED or not session_id:
        return None
    items = _todo_items(args) if tool_name == "todo_list" else []
    completing: list[tuple[str, str]] = []
    if tool_name == "todo_list":
        completing = _completing(session_id, items)  # judged on what the session held before this call
        if not completing:
            _remember(session_id, items, allowed=True)
            return None
    try:
        claims, current = _session_claims(session_id, store)
    except Exception:  # an unreadable or locked store never blocks a tool
        if tool_name == "todo_list":
            # Let through unjudged: what the items named is kept, but not as completions that were let
            # through, so the same items sent again once the store reads are judged then.
            _remember(session_id, items, allowed=False)
        return None
    if claims:
        with _TODOS_LOCK:
            _HELD.add(session_id)
    failing = [c for c in claims if not c["check"].get("ok")]
    block = None
    if tool_name == "rung_report":
        from .claims import canonical_rid
        spec = args.get("spec") if isinstance(args, dict) else None
        spec = canonical_rid(spec) if isinstance(spec, str) else spec
        project = args.get("project") if isinstance(args, dict) and isinstance(args.get("project"), str) \
            and args.get("project").strip() else current  # the project the tool itself will act on
        hit = [c for c in failing if c["spec"] == spec and c["project"] == project]
        block = _message(hit[0]) if hit else None
    elif tool_name == "kanban_complete":
        block = _message(failing[0]) if failing else None
    else:
        for _tid, text in completing:
            hit = [c for c in failing if ALL in text or _names(text, c["spec"])]
            if hit:
                block = _message(hit[0])
                break
        _remember(session_id, items, allowed=block is None)
    return block


def pre_tool_call(tool_name: str = "", args=None, session_id: str = "", **kwargs):
    """Hermes `pre_tool_call` hook. Fails open: an error here never blocks a tool."""
    try:
        msg = decide(tool_name, args or {}, session_id or "")
    except Exception:
        return None
    return {"action": "block", "message": msg} if msg else None


def forget(session_id: str | None = None) -> None:
    with _TODOS_LOCK:
        if session_id is None:
            _TODOS.clear()
            _HELD.clear()
        else:
            _TODOS.pop(session_id, None)
            _HELD.discard(session_id)
