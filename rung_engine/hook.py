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

# Per session: todo id -> (content, status), as seen in that session's todo_list calls. In memory only:
# the hook never writes. Bounded so a long-lived process cannot grow it without limit.
_TODOS: dict[str, dict[str, tuple[str, str]]] = {}
_TODOS_LOCK = threading.Lock()
_MAX_SESSIONS = 500


def _store() -> Path | None:
    try:
        from .host import store_path
        return store_path()
    except Exception:
        return None


def _session_claims(session_id: str, store: Path | None = None) -> list[dict]:
    """Open claims of the session with their checks, from a read-only view of the store."""
    path = store if store is not None else _store()
    if path is None or not Path(path).is_file():
        return []
    from .core import Engine
    eng = Engine(path, readonly=True)
    try:
        return eng.session_claims(session_id)
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


def _remember(session_id: str, items: list[dict], statuses: bool) -> None:
    with _TODOS_LOCK:
        if session_id not in _TODOS and len(_TODOS) >= _MAX_SESSIONS:
            _TODOS.pop(next(iter(_TODOS)))
        seen = _TODOS.setdefault(session_id, {})
        for t in items:
            tid = str(t.get("id", "")).strip()
            if not tid:
                continue
            content, status = seen.get(tid, ("", ""))
            if isinstance(t.get("content"), str) and t["content"].strip():
                content = t["content"]
            if statuses and isinstance(t.get("status"), str):
                status = t["status"].strip().lower()
            seen[tid] = (content, status)


def _completing(session_id: str, items: list[dict]) -> list[tuple[str, str]]:
    """(id, text) of each item this call moves to completed, text being its id plus every content seen."""
    with _TODOS_LOCK:
        seen = dict(_TODOS.get(session_id, {}))
    out = []
    for t in items:
        if str(t.get("status", "")).strip().lower() != "completed":
            continue
        tid = str(t.get("id", "")).strip()
        before = seen.get(tid, ("", ""))
        if before[1] == "completed":
            continue  # already completed earlier: rewriting it declares nothing new
        text = " ".join(x for x in (tid, t.get("content") if isinstance(t.get("content"), str) else "", before[0]) if x)
        out.append((tid, text))
    return out


def decide(tool_name: str, args, session_id: str = "", store: Path | None = None) -> str | None:
    """The block message for this call, or None to let it run."""
    if tool_name not in WATCHED or not session_id:
        return None
    items = _todo_items(args) if tool_name == "todo_list" else []
    completing: list[tuple[str, str]] = []
    if tool_name == "todo_list":
        _remember(session_id, items, statuses=False)
        completing = _completing(session_id, items)
        if not completing:
            _remember(session_id, items, statuses=True)
            return None
    claims = _session_claims(session_id, store)
    failing = [c for c in claims if not c["check"].get("ok")]
    block = None
    if tool_name == "rung_report":
        spec = args.get("spec") if isinstance(args, dict) else None
        hit = [c for c in failing if c["spec"] == spec and (not args.get("project") or c["project"] == args.get("project"))]
        block = _message(hit[0]) if hit else None
    elif tool_name == "kanban_complete":
        block = _message(failing[0]) if failing else None
    else:
        for _tid, text in completing:
            hit = [c for c in failing if _names(text, c["spec"])]
            if hit:
                block = _message(hit[0])
                break
        if block is None:
            _remember(session_id, items, statuses=True)
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
