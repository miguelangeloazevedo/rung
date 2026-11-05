"""Claims: a chat session takes a specification, and reports it done only once Rung's check passes.

A claim is held by one chat session (its Hermes session id) running as one profile. It closes as
reported (with the executions that prove the specification released) or as released by a person.
Claims never expire on their own. Every step is kept in the project's log.
"""

from __future__ import annotations

import json


def _rx_for(rid: str):
    import re
    return re.compile(r"(?<![A-Za-z0-9])" + re.escape(rid) + r"(?![0-9])")


class ClaimsMixin:
    """Mixed into Engine. Uses its _q/_q1/_tx/_log/_rung_row/_project_row helpers."""

    def _claim_dict(self, c) -> dict:
        spec = self._rung_by_pk(c["spec_pk"])
        project = self._project_row(c["project_pk"])
        return {"id": c["pk"], "project": project["name"], "spec": spec["rid"] if spec else None,
                "spec_text": spec["text"] if spec else "", "session": c["session_id"], "chat": c["chat"],
                "profile": c["profile"], "status": c["status"], "opened_at": c["opened_at"],
                "closed_at": c["closed_at"], "closed_by": c["closed_by"], "proof": json.loads(c["proof"] or "[]")}

    def claims(self, project: str | None = None, spec_rid: str | None = None, open_only: bool = True) -> list[dict]:
        sql, args = "SELECT * FROM claims WHERE 1=1", []
        if project is not None:
            sql += " AND project_pk=?"
            args.append(self._project_row(project)["pk"])
        if spec_rid is not None:
            sql += " AND spec_pk=?"
            args.append(self._rung_row(project, spec_rid)["pk"])
        if open_only:
            sql += " AND status='open'"
        sql += " ORDER BY pk"
        return [self._claim_dict(c) for c in self._q(sql, tuple(args))]

    def session_claims(self, session_id: str) -> list[dict]:
        """The open claims of one chat session, each with its current check. Read only."""
        if not session_id:
            return []
        out = []
        for c in self._q("SELECT * FROM claims WHERE session_id=? AND status='open' ORDER BY pk", (session_id,)):
            d = self._claim_dict(c)
            try:
                d["check"] = self.check(d["project"], d["spec"])
            except Exception as exc:  # a vanished specification never blocks anything
                d["check"] = {"id": d["spec"], "ok": True, "blockers": [], "error": str(exc)}
            out.append(d)
        return out

    def claim(self, project: str, spec_rid: str, session_id: str, chat: str, profile: str) -> dict:
        from .core import RungError
        with self._lock:
            self._check_writable(project, spec_rid)
            if not isinstance(session_id, str) or not session_id.strip():
                raise RungError("a claim needs a chat session", code="bad_request", status=400, field="session")
            s = self._rung_row(project, spec_rid)
            if s["kind"] != "specification":
                raise RungError(f"{spec_rid} is not a specification", code="bad_request", status=400)
            held = self._q1("SELECT * FROM claims WHERE spec_pk=? AND status='open' ORDER BY pk LIMIT 1", (s["pk"],))
            if held is not None and held["session_id"] == session_id:
                return self._claim_dict(held)
            if s["status"] != "approved":
                raise RungError(f"{spec_rid} is {s['status']}; only an approved specification can be claimed",
                                code="locked")
            needs, why_human = self._needs_of(s)
            if why_human:
                raise RungError(f"{spec_rid} is human only", code="human_only")
            if held is not None:
                raise RungError(f"{spec_rid} is held by {held['chat'] or 'another chat'} ({held['profile']})",
                                code="conflict")
            why = self.exclusion(project, spec_rid, profile)
            if why:
                raise RungError(f"{profile} is not eligible for {spec_rid}: {why}", code="excluded")
            with self._tx() as c:
                cur = c.execute("INSERT INTO claims(project_pk, spec_pk, session_id, chat, profile, status, opened_at) "
                                "VALUES (?,?,?,?,?,?,?)",
                                (s["project_pk"], s["pk"], session_id, (chat or "")[:200], profile, "open",
                                 self.clock()))
                self._log(c, s["project_pk"], "claim", {"spec": spec_rid, "chat": chat, "profile": profile}, profile)
                self._touch_project(c, s["project_pk"])
            return self._claim_dict(self._q1("SELECT * FROM claims WHERE pk=?", (cur.lastrowid,)))

    def _proof(self, s) -> list[str]:
        """The executions that make a released specification released: each gating test's counting pass."""
        out = []
        for t in self._children_rows(s["pk"]):
            if t["status"] not in ("approved", "stale"):
                continue
            rows = self._counting(t)
            if rows and rows[0]["status"] == "pass":
                out.append(f"{t['rid']} #{rows[0]['n']}")
        return out

    def report(self, project: str, spec_rid: str, session_id: str) -> dict:
        """A session declares its claimed specification done. Refused while the check fails; the claim
        then stays open. A report is never an approval."""
        from .core import RungError
        with self._lock:
            self._check_writable(project, spec_rid)
            s = self._rung_row(project, spec_rid)
            mine = self._q1("SELECT * FROM claims WHERE spec_pk=? AND session_id=? AND status='open' ORDER BY pk "
                            "LIMIT 1", (s["pk"], session_id or ""))
            if mine is None:
                raise RungError(f"this chat holds no open claim on {spec_rid}; claim it first", code="no_claim")
            chk = self.check(project, spec_rid)
            if not chk["ok"]:
                raise RungError(f"{spec_rid} is not released: " + "; ".join(chk["blockers"]), code="not_released")
            proof = self._proof(s)
            with self._tx() as c:
                c.execute("UPDATE claims SET status='reported', closed_at=?, closed_by=?, proof=? WHERE pk=?",
                          (self.clock(), mine["profile"], json.dumps(proof), mine["pk"]))
                self._log(c, s["project_pk"], "claim_reported", {"spec": spec_rid, "chat": mine["chat"],
                                                                 "proof": proof}, mine["profile"])
                self._touch_project(c, s["project_pk"])
            out = self._claim_dict(self._q1("SELECT * FROM claims WHERE pk=?", (mine["pk"],)))
            out["check"] = chk
            return out

    def release_claim(self, project: str, spec_rid: str, actor=None) -> list[dict]:
        """A person lets go of every open claim on a specification. It closes as released."""
        from .core import HUMAN, RungError
        actor = actor or HUMAN
        if not actor.is_human:
            raise RungError("only a human releases a claim", code="forbidden", status=403)
        with self._lock:
            s = self._rung_row(project, spec_rid)
            rows = self._q("SELECT * FROM claims WHERE spec_pk=? AND status='open'", (s["pk"],))
            if not rows:
                raise RungError(f"no open claim on {spec_rid}", code="no_claim")
            with self._tx() as c:
                for r in rows:
                    c.execute("UPDATE claims SET status='released', closed_at=?, closed_by=? WHERE pk=?",
                              (self.clock(), actor.name, r["pk"]))
                    self._log(c, s["project_pk"], "claim_released", {"spec": spec_rid, "chat": r["chat"],
                                                                     "profile": r["profile"]}, actor.name)
                self._touch_project(c, s["project_pk"])
            return [self._claim_dict(self._q1("SELECT * FROM claims WHERE pk=?", (r["pk"],))) for r in rows]

    @staticmethod
    def names_spec(text: str, rid: str) -> bool:
        return bool(text) and bool(_rx_for(rid).search(text))
