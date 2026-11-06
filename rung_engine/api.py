"""Framework-free REST routing for Rung. `dashboard/plugin_api.py` mounts it under /api/plugins/rung/.

Every request from the Desktop pane acts as the human at the keyboard. Agents never come in
through here; they use the Rung tools, which act as agents and cannot approve.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Callable

from .core import HUMAN, Actor, NotFound, RungError
from .service import Service

ROUTES: list[tuple[str, re.Pattern, Callable]] = []


def route(method: str, pattern: str):
    rx = re.compile("^" + re.sub(r"\{(\w+)\}", r"(?P<\1>[^/]+)", pattern) + "$")

    def deco(fn):
        ROUTES.append((method, rx, fn))
        return fn

    return deco


def _flag(body: dict, key: str, required: bool = False) -> bool:
    """A yes or no field: true or false only, so the text "false" never approves anything."""
    if key not in body or body[key] is None:
        if required:
            raise ApiError(400, f"{key} is required", "bad_request")
        return False
    v = body[key]
    if not isinstance(v, bool):
        raise ApiError(400, f"{key} is true or false", "bad_request")
    return v


class ApiError(Exception):
    def __init__(self, status: int, detail: str, code: str = "error"):
        super().__init__(detail)
        self.status = status
        self.detail = detail
        self.code = code


def handle(svc: Service, method: str, path: str, body: Any = None, human: Actor | None = None) -> tuple[int, Any]:
    """Return (status, json). Never raises for expected refusals."""
    path = "/" + path.strip("/")
    human = human or HUMAN
    for m, rx, fn in ROUTES:
        if m != method.upper():
            continue
        mt = rx.match(path)
        if not mt:
            continue
        if body is not None and not isinstance(body, dict):
            return 400, {"detail": "the request body is an object", "code": "bad_request"}
        try:
            return 200, fn(svc, human, body or {}, **mt.groupdict())
        except NotFound as exc:
            return 404, {"detail": str(exc), "code": exc.code}
        except RungError as exc:
            out = {"detail": str(exc), "code": exc.code}
            if getattr(exc, "field", None):
                out["field"] = exc.field
            return exc.status, out
        except ApiError as exc:
            return exc.status, {"detail": exc.detail, "code": exc.code}
        except (AttributeError, KeyError, TypeError, ValueError) as exc:
            return 400, {"detail": f"bad request: {exc}", "code": "bad_request"}
    return 404, {"detail": f"no route {method} {path}", "code": "not_found"}


def _int_path(value, field: str) -> int:
    """A number in the path; anything else is a 400 naming it."""
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    raise RungError(f"{field} is a whole number, 0 or more", code="bad_request", status=400, field=field)


def _known_profiles(svc, names) -> None:
    """The pane offers only the profiles Rung lists; a name it does not list is refused, not created."""
    if not isinstance(names, list):
        return  # absent, or wrong-typed: the engine names the field
    known = {p["name"] for p in svc.engine.profiles()}
    unknown = [n for n in names if isinstance(n, str) and n.strip() and n.strip() not in known]
    if unknown:
        raise RungError(f"no profile {unknown[0]}", code="bad_request", status=400, field="profiles")


def _need(body, key):
    if key not in body:
        raise ApiError(400, f"{key} is required", "bad_request")
    return body[key]


# ------------------------------------------------------------------ overview


@route("GET", "/rev")
def _rev(svc, human, body):
    return {"rev": svc.engine.rev()}


@route("GET", "/state")
def _state(svc, human, body):
    e = svc.engine
    cur = e.current_project()
    out = {"rev": e.rev(), "current": cur, "projects": e.projects(), "settings": e.settings(),
           "profiles": e.profiles(), "needs_you": 0, "running": 0, "onboarding": e.onboarding(),
           "archived": len(e.projects(archived=True))}
    if cur:
        t = e.tiles(cur)
        out["needs_you"] = t["needs_you"]
        out["running"] = t["running"]
        out["current_archived"] = t["archived"]
        out["claims"] = len(e.claims(cur))
    return out


@route("POST", "/projects")
def _create_project(svc, human, body):
    """Only the folder is required; the rest fill in from it (POST /projects/defaults shows the values)."""
    _known_profiles(svc, body.get("profiles"))
    return svc.engine.create_project(body.get("name", ""), body.get("folder", ""), body.get("test_command", ""),
                                     body.get("profiles"))


@route("POST", "/projects/defaults")
def _project_defaults(svc, human, body):
    folder = body.get("folder", "")
    if not isinstance(folder, str):
        raise RungError("folder is text", code="bad_request", status=400, field="folder")
    return svc.engine.project_defaults(folder)


@route("GET", "/projects/archived")
def _archived(svc, human, body):
    return svc.engine.projects(archived=True)


@route("POST", "/projects/{project}/update")
def _update_project(svc, human, body, project):
    _known_profiles(svc, body.get("profiles"))
    return svc.engine.update_project(project, new_name=body.get("name"), folder=body.get("folder"),
                                     test_command=body.get("test_command"),
                                     profiles=body.get("profiles"), actor=human)


@route("POST", "/projects/{project}/archive")
def _archive(svc, human, body, project):
    return svc.engine.archive_project(project, human)


@route("POST", "/projects/{project}/restore")
def _restore(svc, human, body, project):
    return svc.engine.restore_project(project, human)


@route("POST", "/projects/{project}/delete")
def _delete(svc, human, body, project):
    return svc.engine.delete_project(project, body.get("confirm", ""), human)


@route("GET", "/projects/{project}/events")
def _events(svc, human, body, project):
    return svc.engine.events(project)


@route("GET", "/projects/{project}/first-green")
def _first_green(svc, human, body, project):
    return svc.engine.first_green(project)


@route("POST", "/sample")
def _sample(svc, human, body):
    return svc.engine.create_sample(human)


@route("POST", "/sample/reset")
def _sample_reset(svc, human, body):
    return svc.engine.reset_sample(human)


@route("GET", "/onboarding")
def _onboarding(svc, human, body):
    return svc.engine.onboarding()


@route("POST", "/onboarding")
def _set_onboarding(svc, human, body):
    return svc.engine.set_onboarding(start_dismissed=body.get("start_dismissed"),
                                     checklist_hidden=body.get("checklist_hidden"))


@route("POST", "/projects/{project}/open")
def _open(svc, human, body, project):
    return svc.engine.open_project(project)


@route("GET", "/projects/{project}/home")
def _home(svc, human, body, project):
    e = svc.engine
    h = e.home(project)
    h["tree"] = e.tree(project)
    h["retired"] = len(e.tree(project, retired=True))
    h["rev"] = e.rev()
    focus = body.get("focus") if isinstance(body, dict) else None
    h["allocation"] = _allocation_focus(svc, project, focus)
    return h


def _allocation_focus(svc, project, focus=None):
    e = svc.engine
    spec = _spec_for(e.tree(project), focus) if focus else None
    if not spec:
        for item in e.needs_you(project):
            if item["kind"] == "specification":
                spec = item["id"]
                break
    if not spec:
        for n in e.tree(project):
            for r in n["children"]:
                for s in r["children"]:
                    if s["status"] in ("approved", "stale") and not s.get("released"):  # nothing to allocate once done
                        spec = s["id"]
                        break
                if spec:
                    break
            if spec:
                break
    if not spec:
        return None
    try:
        return e.suggest(project, spec)
    except RungError:
        return None


def _spec_for(tree, rid):
    """The specification a rung's view is about: itself, its parent for a test, the first one below otherwise."""
    def first_spec(n):
        if n.get("kind") == "specification":
            return n["id"]
        for c in n.get("children", []):
            if c.get("status") in ("dismissed", "proposed"):
                continue
            s = first_spec(c)
            if s:
                return s
        return None

    def walk(nodes, parent_spec=None):
        for n in nodes:
            spec = n["id"] if n.get("kind") == "specification" else parent_spec
            if n["id"] == rid:
                return spec if n.get("kind") == "test" else first_spec(n)
            hit = walk(n.get("children", []), spec)
            if hit:
                return hit
        return None

    return walk(tree)


@route("GET", "/projects/{project}/tree")
def _tree(svc, human, body, project):
    return svc.engine.tree(project)


@route("GET", "/projects/{project}/retired")
def _retired(svc, human, body, project):
    return svc.engine.tree(project, retired=True)


@route("POST", "/projects/{project}/needs/{rid}/retire")
def _retire(svc, human, body, project, rid):
    return svc.engine.retire_need(project, rid, body.get("reason", ""), human)


@route("POST", "/projects/{project}/needs/{rid}/restore")
def _restore_need(svc, human, body, project, rid):
    return svc.engine.restore_need(project, rid, human)


@route("GET", "/projects/{project}/needs/{rid}/readout")
def _readout(svc, human, body, project, rid):
    return svc.engine.readout(project, rid)


@route("POST", "/projects/{project}/needs/{rid}/readout/export")
def _export_readout(svc, human, body, project, rid):
    return svc.engine.export_readout(project, rid)


@route("GET", "/projects/{project}/needs-you")
def _needs_you(svc, human, body, project):
    return svc.engine.needs_you(project)


# ------------------------------------------------------------------ rungs


@route("GET", "/projects/{project}/rungs/{rid}")
def _rung(svc, human, body, project, rid):
    e = svc.engine
    r = e.rung(project, rid)
    rid = r["id"]  # the stored id: every lookup below (tree, history, executions) is keyed by it
    tree_index = {}

    def walk(nodes):
        for n in nodes:
            tree_index[n["id"]] = n
            walk(n.get("children", []))

    walk(e.tree(project))
    walk(e.tree(project, retired=True))
    node = tree_index.get(rid)
    r["children"] = node["children"] if node else []
    for k in ("coverage", "released", "blockers", "carried_by", "result", "seen_failing", "retired",
              "retired_reason", "retired_at"):
        if node and k in node:
            r[k] = node[k]
    r["history"] = e.history(project, rid)
    r["changes"] = e.changes(project, rid)
    if r["status"] == "stale" or any(c["stale"] for c in r["changes"]):
        r["change"] = e.change_for(project, rid)
    path = []
    cur = r
    while cur.get("parent"):
        cur = e.rung(project, cur["parent"])
        path.insert(0, {"id": cur["id"], "text": cur["text"], "kind": cur["kind"], "status": cur["status"]})
    r["path"] = path
    top = path[0]["id"] if path else rid
    r["read_only"] = e.project(project)["archived"] or bool(tree_index.get(top, {}).get("retired"))
    if r["kind"] == "need":
        r["flow"] = e.flow(project, rid)
        r["suggestions"] = e.suggestions(project, rid, "requirement")
    if r["kind"] == "requirement":
        r["suggestions"] = e.suggestions(project, rid, "edit")
    if r["kind"] == "specification":
        r["allocation"] = e.suggest(project, rid)
        r["runs"] = e.runs(project, rid)
        r["claims"] = e.claims(project, rid, open_only=False)
        r["ai_derived"] = e.ai_derived(project, rid)
        req = e.rung(project, r["parent"]) if r.get("parent") else None
        r["authoring"] = (req or {}).get("authoring")  # the requirement's mode, which its control writes
        ok, why = e.develop_available(project, rid)
        r["develop"] = {"available": ok, "blocked_by": why or None}
    if r["kind"] == "test":
        r["executions"] = e.executions(project, rid)
        r["defects"] = [d for d in e.defects(project) if d["test"] == rid]
    return r


@route("POST", "/projects/{project}/needs/suggest")
def _suggest_reqs(svc, human, body, project):
    return {"suggestions": svc.suggest_requirements(project, _need(body, "text"))}


@route("POST", "/projects/{project}/needs")
def _create_need(svc, human, body, project):
    need = svc.engine.create_need(project, _need(body, "text"), human, list(body.get("requirements", [])))
    more = body.get("more_suggestions")
    if more is None:
        try:
            d = svc.drafter(project)
            more = d.table.get("more_requirements", {}).get(need["text"], []) if hasattr(d, "table") else []
        except Exception:
            more = []
    if more:
        svc.engine.add_suggestions(project, need["id"], "requirement", more)
    return need


@route("POST", "/projects/{project}/rungs/{rid}/edit")
def _edit(svc, human, body, project, rid):
    # Text and detail only: a rung's data (gates, draft state, a test's command) changes through its own route.
    return svc.engine.edit(project, rid, text=body.get("text"), detail=body.get("detail"), actor=human,
                           approve=_flag(body, "approve"), expect_version=body.get("version"))


@route("POST", "/projects/{project}/rungs/{rid}/approve")
def _approve(svc, human, body, project, rid):
    return svc.engine.approve(project, rid, human)


@route("POST", "/projects/{project}/rungs/{rid}/dismiss")
def _dismiss(svc, human, body, project, rid):
    svc.engine.dismiss(project, rid, human)
    return {"ok": True}


@route("POST", "/projects/{project}/needs/{rid}/requirements")
def _add_req(svc, human, body, project, rid):
    return svc.engine.add_requirement(project, rid, _need(body, "text"), human, body.get("detail", ""))


@route("POST", "/projects/{project}/needs/{rid}/approve-requirements")
def _approve_reqs(svc, human, body, project, rid):
    return {"approved": svc.engine.approve_requirements(project, rid, human)}


@route("GET", "/projects/{project}/needs/{rid}/flow")
def _flow(svc, human, body, project, rid):
    return svc.engine.flow(project, rid)


@route("POST", "/projects/{project}/needs/{rid}/approve-drafted")
def _approve_drafted(svc, human, body, project, rid):
    approved = svc.engine.approve_drafted(project, rid, human)
    proposed = svc.propose_tests(project, rid)
    return {"approved": approved, "proposed_tests": [t["id"] for t in proposed]}


@route("POST", "/projects/{project}/needs/{rid}/propose-tests")
def _propose_tests(svc, human, body, project, rid):
    return {"proposed_tests": [t["id"] for t in svc.propose_tests(project, rid)]}


@route("POST", "/projects/{project}/needs/{rid}/approve-tests")
def _approve_tests(svc, human, body, project, rid):
    svc.engine.approve_tests(project, rid, human)
    return svc.engine.flow(project, rid)


@route("POST", "/projects/{project}/rungs/{rid}/authoring")
def _authoring(svc, human, body, project, rid):
    spec = svc.set_authoring(project, rid, _need(body, "mode"), human)
    return {"spec": spec}


@route("POST", "/projects/{project}/rungs/{rid}/regenerate")
def _regenerate(svc, human, body, project, rid):
    return svc.regenerate(project, rid, human)


@route("POST", "/projects/{project}/rungs/{rid}/spec")
def _write_spec(svc, human, body, project, rid):
    return svc.engine.write_spec(project, rid, _need(body, "text"), body.get("detail", ""), human,
                                 tags=body.get("tags"), required_tags=body.get("required_tags"),
                                 suggestion=body.get("suggestion"))


@route("GET", "/projects/{project}/rungs/{rid}/support")
def _support(svc, human, body, project, rid):
    return {"suggestion": svc.support(project, rid, body.get("draft", "") if isinstance(body, dict) else "")}


@route("POST", "/projects/{project}/rungs/{rid}/suggest-edits")
def _suggest_edits(svc, human, body, project, rid):
    return {"suggestions": svc.suggest_edits(project, rid)}


@route("POST", "/projects/{project}/suggestions/{sid}")
def _resolve_suggestion(svc, human, body, project, sid):
    made = svc.engine.resolve_suggestion(project, int(sid), _flag(body, "accept", required=True), human)
    return {"made": made}


@route("POST", "/projects/{project}/changes/{cid}/revert")
def _revert(svc, human, body, project, cid):
    return svc.engine.revert_change(project, _int_path(cid, "change"), human)


@route("GET", "/projects/{project}/changes")
def _changes(svc, human, body, project):
    return svc.engine.changes(project)


# ------------------------------------------------------------------ tests and executions


@route("POST", "/projects/{project}/specs/{rid}/tests")
def _add_test(svc, human, body, project, rid):
    fields = dict(body.get("fields") or body)
    return svc.engine.add_test(project, rid, fields, human, status="approved" if _flag(body, "accept") else "draft")


@route("POST", "/projects/{project}/tests/{rid}")
def _edit_test(svc, human, body, project, rid):
    fields = dict(body.get("fields") or body)
    out = svc.engine.edit_test(project, rid, fields, human)
    return out


@route("POST", "/projects/{project}/tests/{rid}/run")
def _run_test(svc, human, body, project, rid):
    n = svc.run_test(project, rid, carried_by="engine", once_by=human if _flag(body, "once") else None)
    return {"n": n}


@route("POST", "/projects/{project}/specs/{rid}/run-tests")
def _run_spec_tests(svc, human, body, project, rid):
    ns = []
    for t in svc.engine.command_tests(project, rid):
        ns.append({"test": t["id"], "n": svc.run_test(project, t["id"], carried_by="engine")})
    return {"started": ns}


@route("GET", "/projects/{project}/tests/{rid}/executions")
def _executions(svc, human, body, project, rid):
    return svc.engine.executions(project, rid)


@route("GET", "/projects/{project}/tests/{rid}/executions/{n}")
def _execution(svc, human, body, project, rid, n):
    out = svc.engine.execution(project, rid, int(n))
    t = svc.engine.rung(project, rid)
    out["timeout"] = t.get("timeout")
    out["test_status"] = t["status"]
    out["spec"] = t["parent"]
    s = svc.engine.rung(project, t["parent"])
    out["requirement"] = s["parent"]
    out["coverage"] = svc.engine.coverage(project, s["parent"])
    return out


@route("POST", "/projects/{project}/tests/{rid}/executions/{n}/cancel")
def _cancel_exec(svc, human, body, project, rid, n):
    x = svc.engine.execution(project, rid, _int_path(n, "n"))
    if x["status"] != "running":
        raise RungError(f"{rid} #{x['n']} is not running ({x['status']})", code="not_running")
    svc.engine.cancel_execution(project, rid, x["n"])
    return svc.engine.execution(project, rid, x["n"])


@route("POST", "/projects/{project}/tests/{rid}/record")
def _record(svc, human, body, project, rid):
    return svc.engine.record_manual(project, rid, _need(body, "result"), body.get("note", ""), human)


@route("POST", "/projects/{project}/tests/{rid}/executions/{n}/approve")
def _approve_result(svc, human, body, project, rid, n):
    return svc.engine.approve_result(project, rid, int(n), human)


@route("POST", "/projects/{project}/tests/{rid}/defects")
def _raise_defect(svc, human, body, project, rid):
    return svc.engine.raise_defect(project, rid, list(_need(body, "executions")), _need(body, "title"),
                                   body.get("note", ""), human, category=body.get("category") or "Implementation")


@route("GET", "/projects/{project}/defects")
def _defects(svc, human, body, project):
    return svc.engine.defects(project)


# ------------------------------------------------------------------ allocation and develop


@route("GET", "/projects/{project}/specs/{rid}/suggest")
def _suggest(svc, human, body, project, rid):
    return svc.engine.suggest(project, rid)


@route("POST", "/projects/{project}/specs/{rid}/pick")
def _pick(svc, human, body, project, rid):
    # The body key is "agent", not "profile": Hermes's dashboard auth reserves a top-level
    # "profile" key in JSON bodies for profile scoping and refuses requests that carry another one.
    agent = _need(body, "agent")
    if not isinstance(agent, str):
        raise RungError("agent is a profile name", code="bad_request", status=400, field="agent")
    return svc.engine.pick(project, rid, agent, human)


@route("POST", "/projects/{project}/specs/{rid}/send")
def _send(svc, human, body, project, rid):
    return svc.send(project, rid, human, body.get("agent"))


@route("POST", "/projects/{project}/specs/{rid}/allocation")
def _set_allocation(svc, human, body, project, rid):
    allowed = {"required_tools", "independent", "human_only"}
    unknown = sorted(set(body) - allowed)
    if unknown:
        raise ApiError(400, "unknown field " + ", ".join(unknown), "bad_request")
    return svc.engine.set_allocation(project, rid, required_tools=body.get("required_tools"),
                                     independent=body.get("independent"), human_only=body.get("human_only"),
                                     actor=human)


@route("GET", "/projects/{project}/exclusions")
def _exclusions(svc, human, body, project):
    return svc.engine.exclusions(project)


@route("GET", "/projects/{project}/claims")
def _claims(svc, human, body, project):
    return svc.engine.claims(project, open_only=False)


@route("POST", "/projects/{project}/specs/{rid}/claims/release")
def _release_claim(svc, human, body, project, rid):
    return svc.engine.release_claim(project, rid, human)


@route("GET", "/projects/{project}/runs")
def _runs(svc, human, body, project):
    return svc.engine.runs(project)


@route("GET", "/runs/{run_id}")
def _run(svc, human, body, run_id):
    return svc.engine.run(int(run_id))


@route("POST", "/runs/{run_id}/cancel")
def _cancel_run(svc, human, body, run_id):
    r = svc.engine.run(_int_path(run_id, "run"))
    if r["status"] not in ("queued", "running"):
        raise RungError(f"run {r['id']} is not running ({r['status']})", code="not_running")
    return svc.cancel(r["id"])


@route("GET", "/projects/{project}/check/{rid}")
def _check(svc, human, body, project, rid):
    return svc.engine.check(project, rid)


@route("GET", "/projects/{project}/check")
def _check_all(svc, human, body, project):
    return svc.engine.check_all(project)


# ------------------------------------------------------------------ settings


@route("GET", "/settings")
def _settings(svc, human, body):
    return {"settings": svc.engine.settings(), "profiles": svc.engine.profiles()}


@route("POST", "/settings")
def _save_settings(svc, human, body):
    profiles = body.get("profiles") if "profiles" in body else None
    if isinstance(profiles, list):  # Settings lists the profiles Rung has; it never creates one
        _known_profiles(svc, [p.get("name") for p in profiles if isinstance(p, dict)])
    svc.engine.save_settings(body.get("settings"), profiles)
    return {"settings": svc.engine.settings(), "profiles": svc.engine.profiles()}


@route("GET", "/doctor")
def _doctor(svc, human, body):
    from .doctor import run_checks
    from .host import hermes_bin
    checks = run_checks(Path(svc.engine.path), hermes_bin())
    return {"ok": all(c["ok"] for c in checks), "checks": checks}


@route("GET", "/profiles")
def _profiles(svc, human, body):
    return svc.engine.profiles()
