# pyright: reportAttributeAccessIssue=false
"""A small task stays small (decisions Round 24, B11): one card over the ordinary ladder.

`Quick task` writes one need, one requirement, one specification and one to five tests through the same rows
and rules as the full ladder. The card is a view of those rungs, not a second store: Approve approves exactly
the versions the card showed, Build and verify starts the ordinary develop run, and verification is the one
evaluator. A mixin of `Engine`.
"""

from __future__ import annotations

import json

MAX_CHECKS = 5


def _j(x):
    return json.dumps(x, sort_keys=True)


def _l(x, default=None):
    try:
        return json.loads(x) if x else default
    except (TypeError, ValueError):
        return default


class QuickMixin:

    def _quick_checks(self, checks) -> list[dict]:
        from .core import RungError
        if not isinstance(checks, list) or not checks:
            raise RungError("add at least one check", code="bad_request", status=400, field="checks")
        if len(checks) > MAX_CHECKS:
            raise RungError(f"at most {MAX_CHECKS} checks", code="bad_request", status=400, field="checks")
        out = []
        for c in checks:
            if not isinstance(c, dict):
                raise RungError("a check is a command or manual steps", code="bad_request", status=400, field="checks")
            t = c.get("type", "command")
            if t == "manual":
                steps = c.get("steps")
                if isinstance(steps, str):
                    steps = [s for s in steps.splitlines()]
                out.append({"type": "manual", "steps": steps or [], "text": c.get("text", "")})
            elif t == "command":
                f = {"type": "command", "command": c.get("command", ""), "text": c.get("text", "")}
                if c.get("pass_rule") is not None:
                    f["pass_rule"] = c["pass_rule"]
                out.append(f)
            else:
                raise RungError(f"check type {t} unknown", code="bad_request", status=400, field="checks")
        return out

    def quick_task(self, project: str, outcome: str, checks, profile: str | None = None, actor=None) -> dict:
        """One need, requirement, specification and tests, all written in one transaction. The need is the
        person's own text (approved on creation, as Create need); the rest are drafts until Approve."""
        from .core import HUMAN, RungError
        actor = actor or HUMAN
        if not actor.is_human:
            raise RungError("agents propose, they cannot create a task", code="forbidden", status=403)
        outcome = (outcome or "").strip()
        if not outcome:
            raise RungError("say what should work", code="bad_request", status=400, field="outcome")
        fields = self._quick_checks(checks)
        if profile:
            self.profile(profile)  # an unknown profile is refused before anything is stored
        with self._lock:
            self._check_writable(project, None)
            return self._quick_task(project, outcome, fields, profile, actor)

    def _quick_task(self, project, outcome, fields, profile, actor) -> dict:
        p = self._project_row(project)
        datas = []
        for f in fields:
            d = self._test_data(p, None, f)
            self._validate_test(f.get("text", ""), d)
            datas.append((f, d))
        with self._tx() as c:
            need_pk = self._insert_rung(c, p["pk"], "need", None, outcome, "", "approved", actor,
                                        data={"quick": {"profile": profile or None}})
            need = c.execute("SELECT * FROM rungs WHERE pk = ?", (need_pk,)).fetchone()
            req_pk = self._insert_rung(c, p["pk"], "requirement", need, outcome, "", "draft", actor,
                                       data={"origin": "quick"})
            req = c.execute("SELECT * FROM rungs WHERE pk = ?", (req_pk,)).fetchone()
            spec_pk = self._insert_rung(c, p["pk"], "specification", req, outcome, "", "draft", actor,
                                        data={"draft_state": "drafted", "author_role": "human", "tags": [],
                                              "required_tags": []})
            spec = c.execute("SELECT * FROM rungs WHERE pk = ?", (spec_pk,)).fetchone()
            for f, d in datas:
                text = (f.get("text") or "").strip() or d.get("command") or (
                    "Manual: " + "; ".join(d.get("steps", []))[:120])
                self._insert_rung(c, p["pk"], "test", spec, text, "", "draft", actor, data=d)
        return self.quick(project, need["rid"])

    def _quick_rows(self, project: str, need_rid: str):
        from .core import RungError
        need = self._rung_row(project, need_rid)
        if need["kind"] != "need" or "quick" not in (_l(need["data"], {}) or {}):
            raise RungError(f"{need_rid} is not a quick task", code="not_found", status=404)
        reqs = self._active_reqs(need["pk"])
        req = reqs[0] if reqs else None
        specs = [s for s in self._children_rows(req["pk"]) if s["status"] != "proposed"] if req else []
        spec = specs[0] if specs else None
        tests = [t for t in self._children_rows(spec["pk"]) if t["status"] != "proposed"] if spec else []
        return need, req, spec, tests

    def quick(self, project: str, need_rid: str) -> dict:
        """The card: every rung it stands for with its version, the checks, the run and the verdict."""
        need, req, spec, tests = self._quick_rows(project, need_rid)
        rows = [r for r in (need, req, spec) if r is not None] + list(tests)
        flag = bool(_l(need["data"], {}).get("tests_approved"))
        approved = all(r["status"] == "approved" for r in rows) and flag and spec is not None and bool(tests)
        checks = []
        for t in tests:
            d = self._rung_dict(t)
            last = self._q1("SELECT * FROM executions WHERE test_pk = ? ORDER BY n DESC LIMIT 1", (t["pk"],))
            checks.append({"id": t["rid"], "version": t["version"], "status": t["status"], "text": t["text"],
                           "type": d.get("type"), "command": d.get("command"), "steps": d.get("steps", []),
                           "required": d.get("required", True), "result": self._test_result(t),
                           "last": self._exec_dict(last, t) if last else None})
        verification = self.verification(project, spec["rid"]) if spec is not None else None
        runs = self.runs(project, spec["rid"]) if spec is not None else []
        ok, why = self.develop_available(project, spec["rid"]) if spec is not None and approved else (False, "")
        return {
            "need": need["rid"], "outcome": need["text"], "profile": (_l(need["data"], {})["quick"] or {}).get("profile"),
            "spec": spec["rid"] if spec is not None else None,
            "rungs": [{"id": r["rid"], "kind": r["kind"], "version": r["version"], "status": r["status"],
                       "text": r["text"]} for r in rows],
            "checks": checks, "approved": approved, "verification": verification,
            "run": runs[0] if runs else None, "can_build": ok, "build_blocked_by": why,
        }

    def quick_approve(self, project: str, need_rid: str, versions, actor=None) -> dict:
        """Approve exactly what the card showed: every rung id with the version seen. Anything changed since,
        added or missing refuses the whole approval; nothing is approved."""
        from .core import HUMAN, RungError
        actor = actor or HUMAN
        if not actor.is_human:
            raise RungError("only a human can approve", code="forbidden", status=403)
        if not isinstance(versions, dict) or not versions:
            raise RungError("name each id and the version you saw", code="bad_request", status=400, field="versions")
        with self._lock:
            self._check_writable(project, need_rid)
            return self._quick_approve(project, need_rid, versions, actor)

    def _quick_approve(self, project, need_rid, versions, actor) -> dict:
        from .core import RungError
        need, req, spec, tests = self._quick_rows(project, need_rid)
        rows = [r for r in (need, req, spec) if r is not None] + list(tests)
        if spec is None or req is None or not tests:
            raise RungError(f"{need_rid} has nothing to approve", code="locked")
        seen = {str(k): v for k, v in versions.items()}
        now = {r["rid"]: r["version"] for r in rows}
        changed = sorted(rid for rid in now if rid not in seen or str(seen[rid]) != str(now[rid]))
        extra = sorted(set(seen) - set(now))
        if changed or extra:
            raise RungError("changed since the card loaded: " + ", ".join(changed + extra), code="conflict", status=409)
        for r in (need, req, spec):
            if r["status"] != "approved":
                self.approve(project, r["rid"], actor)
        for t in tests:
            if t["status"] != "approved":
                self.approve(project, t["rid"], actor)
        if not _l(self._rung_row(project, need_rid)["data"], {}).get("tests_approved"):
            self.approve_tests(project, need_rid, actor)
        return self.quick(project, need_rid)

    def quick_tasks(self, project: str) -> list[dict]:
        p = self._project_row(project)
        out = []
        for n in self._q("SELECT * FROM rungs WHERE project_pk = ? AND kind = 'need' AND retired_at IS NULL "
                         "AND status NOT IN ('dismissed','proposed') ORDER BY num", (p["pk"],)):
            if "quick" in (_l(n["data"], {}) or {}):
                out.append({"need": n["rid"], "outcome": n["text"]})
        return out
