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

# Per session: todo id -> what that id has carried in the session's todo_list calls: every content it was
# given (an id that once named a specification keeps counting, whatever it says later) and the content
# it had when it was last let through as completed. In memory only: the hook never writes. Bounded so a
# long-lived process cannot grow it without limit.
_TODOS: dict[str, dict[str, dict]] = {}
_MAX_TEXTS = 20
_TODOS_LOCK = threading.Lock()
_MAX_SESSIONS = 500


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
    todos = args.get("todos") if isinstance(args, dict) else None
    return [t for t in todos if isinstance(t, dict)] if isinstance(todos, list) else []


def _content(t: dict) -> str:
    c = t.get("content")
    return c.strip() if isinstance(c, str) else ""


def _completed(t: dict) -> bool:
    return str(t.get("status", "")).strip().lower() == "completed"


def _remember(session_id: str, items: list[dict], allowed: bool) -> None:
    """Record the contents each id carried; when the call was let through, also what it completed."""
    with _TODOS_LOCK:
        if session_id not in _TODOS and len(_TODOS) >= _MAX_SESSIONS:
            _TODOS.pop(next(iter(_TODOS)))
        seen = _TODOS.setdefault(session_id, {})
        for t in items:
            tid = str(t.get("id", "")).strip()
            if not tid:
                continue
            rec = seen.setdefault(tid, {"texts": [], "done": None})
            text = _content(t)
            if text and text not in rec["texts"]:
                rec["texts"] = (rec["texts"] + [text])[-_MAX_TEXTS:]
            if allowed:
                rec["done"] = (text or (rec["done"] or "")) if _completed(t) else None


def _completing(session_id: str, items: list[dict]) -> list[tuple[str, str]]:
    """(id, text) of each item this call declares completed, text being its id, its content now and
    every content the id carried earlier in the session. An item re-sent completed with the same content
    it had when it was let through declares nothing new and is left out."""
    with _TODOS_LOCK:
        seen = {k: {"texts": list(v["texts"]), "done": v["done"]} for k, v in _TODOS.get(session_id, {}).items()}
    out = []
    for t in items:
        if not _completed(t):
            continue
        tid = str(t.get("id", "")).strip()
        rec = seen.get(tid, {"texts": [], "done": None})
        now = _content(t)
        if rec["done"] is not None and now in ("", rec["done"]):
            continue
        out.append((tid, " ".join(x for x in [tid, now, *rec["texts"]] if x)))
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
    claims, current = _session_claims(session_id, store)
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
            hit = [c for c in failing if _names(text, c["spec"])]
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
        else:
            _TODOS.pop(session_id, None)
