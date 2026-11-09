"""Claims: a chat session takes a specification, and reports it done only once Rung's check passes.

A claim is held by one chat session (its Hermes session id) running as one profile. It closes as
reported (with the executions that prove the specification released) or as released by a person.
Claims never expire on their own. Every step is kept in the project's log.
"""

from __future__ import annotations

import json


def _rx_for(rid: str):
    """How a free text names a rung id: any case, with a hyphen, a space or nothing after the letter
    (`S-2.1`, `s-2.1`, `S 2.1`, `S2.1`), and not as part of a longer id (`S-2.11`, `S-2.1a`, `T-2.1a`)."""
    import re
    m = re.match(r"^([A-Za-z])-(.+)$", rid)
    body = (re.escape(m.group(1)) + r"[-\s]?" + re.escape(m.group(2))) if m else re.escape(rid)
    return re.compile(r"(?<![A-Za-z0-9.])" + body + r"(?![A-Za-z0-9]|\.[0-9])", re.IGNORECASE)


_DASHES = dict.fromkeys(map(ord, "\u2010\u2011\u2012\u2013\u2014\u2015\u2212\ufe58\ufe63\uff0d"), "-")


def normalise(text: str) -> str:
    """Text as the id match reads it: compatibility forms folded (full-width letters and digits), every
    dash and hyphen character read as `-`."""
    import unicodedata
    text = unicodedata.normalize("NFKC", text).translate(_DASHES)
    # Characters with no glyph are dropped: format characters (zero-width space and joiners, soft
    # hyphen, BOM) and the rest of Unicode's Default_Ignorable_Code_Point set (variation selectors, the
    # combining grapheme joiner, Mongolian selectors, Hangul fillers, tags). An id with one inside reads
    # the same to a person.
    return "".join(ch for ch in text if unicodedata.category(ch) != "Cf" and not _ignorable(ord(ch)))


_IGNORABLE = ((0x034F, 0x034F), (0x115F, 0x1160), (0x17B4, 0x17B5), (0x180B, 0x180F), (0x2060, 0x206F),
              (0x3164, 0x3164), (0xFE00, 0xFE0F), (0xFFA0, 0xFFA0), (0xFFF0, 0xFFF8), (0x1BCA0, 0x1BCA3),
              (0x1D173, 0x1D17A), (0xE0000, 0xE0FFF))


def _ignorable(cp: int) -> bool:
    return any(lo <= cp <= hi for lo, hi in _IGNORABLE)


def _canon(rid):
    return canonical_rid(rid) if isinstance(rid, str) else rid


def rids_in(text: str) -> list[str]:
    """Every rung id a text names, in the ladder's form (`ship s 2.1` names `S-2.1`)."""
    import re
    out = []
    for m in re.finditer(r"(?<![A-Za-z0-9.])([A-Za-z])[-\s]?(\d+(?:\.\d+)*)([A-Za-z]*)(?![0-9]|\.[0-9])",
                         normalise(text or "")):
        rid = f"{m.group(1).upper()}-{m.group(2)}{m.group(3).lower()}"
        if rid not in out:
            out.append(rid)
    return out


def canonical_rid(value: str) -> str:
    """An id as an agent may type it (`s-2.1`, ` S 2.1 `) in the form the ladder stores (`S-2.1`).
    Anything that does not look like an id is returned trimmed, for the lookup to refuse by name."""
    import re
    m = re.match(r"^\s*([A-Za-z])[-\s]?(\d+(?:\.\d+)*)([A-Za-z]*)\s*$", normalise(value or ""))
    if not m:
        return (value or "").strip()
    return f"{m.group(1).upper()}-{m.group(2)}{m.group(3).lower()}"


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

    def chat_binding(self, session_id: str) -> dict:
        """What the dock leads with for one chat (decisions Round 24, B18): the specifications this chat holds,
        each with the one verification result (outcome, state, first blocker, next action), or not bound."""
        rows = []
        found = self._q("SELECT * FROM claims WHERE session_id=? AND status='open' ORDER BY pk", (session_id,)) \
            if session_id else []
        for c in map(self._claim_dict, found):
            try:
                v = self.verification(c["project"], c["spec"])
            except Exception:  # a vanished specification: listed, never verified
                v = {"verification": "could_not_verify", "blockers": [], "next_action": None, "ok": False}
            rows.append({"claim": c["id"], "project": c["project"], "spec": c["spec"], "outcome": c["spec_text"],
                         "profile": c["profile"], "chat": c["chat"], "verification": v["verification"],
                         "verified": bool(v.get("ok")), "blocker": v["blockers"][0] if v["blockers"] else None,
                         "next_action": v.get("next_action")})
        return {"session": session_id, "bound": bool(rows), "tasks": rows}

    def claim(self, project: str, spec_rid: str, session_id: str, chat: str, profile: str) -> dict:
        spec_rid = _canon(spec_rid)  # one id form at every door, echoed back as stored
        from .core import RungError
        if not isinstance(session_id, str) or not session_id.strip():
            raise RungError("a claim needs a chat session", code="bad_request", status=400, field="session")
        # Everything below is read and written in one write transaction: another process (the CLI, the
        # Desktop backend, a second gateway) cannot claim the same specification, or fill the profile's
        # At once, between this check and the insert.
        with self._lock, self._tx() as c:
            self._check_writable(project, spec_rid)
            s = self._rung_row(project, spec_rid)
            if s["kind"] != "specification":
                raise RungError(f"{spec_rid} is not a specification", code="bad_request", status=400)
            held = self._q1("SELECT * FROM claims WHERE spec_pk=? AND status='open' ORDER BY pk LIMIT 1", (s["pk"],))
            if s["status"] != "approved":
                raise RungError(f"{spec_rid} is {s['status']}; only an approved specification can be claimed",
                                code="locked")
            if held is not None and held["session_id"] == session_id and held["profile"] != profile:
                raise RungError(f"{spec_rid} is held by this chat as {held['profile']}", code="conflict")
            if held is not None and held["session_id"] != session_id:
                raise RungError(f"{spec_rid} is held by {held['chat'] or 'another chat'} ({held['profile']})",
                                code="conflict")
            run = self._q1("SELECT pk, profile FROM runs WHERE spec_pk=? AND status IN ('queued','running') LIMIT 1",
                           (s["pk"],))
            if run is not None:
                raise RungError(f"{spec_rid} is in develop run {run['pk']} ({run['profile']})", code="conflict")
            # The same reason Send, pick, the API and the CLI give. Claiming again from the holding chat
            # is checked too (the specification may have become human only since), its own claim aside.
            why = self.exclusion(project, spec_rid, profile, ignore_claim=held["pk"] if held is not None else None)
            if why:
                if "human only" in why.split("; "):
                    raise RungError(f"{spec_rid} is human only ({profile} is not eligible: {why})", code="human_only")
                raise RungError(f"{profile} is not eligible for {spec_rid}: {why}", code="excluded")
            if held is not None:
                return self._claim_dict(held)
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
        spec_rid = _canon(spec_rid)  # one id form at every door, echoed back as stored
        from .core import RungError
        # Check and close in one write transaction: no execution can land, and no person can release the
        # claim, between the check that passed and the claim closing as reported.
        with self._lock, self._tx() as c:
            self._check_writable(project, spec_rid)
            s = self._rung_row(project, spec_rid)
            if s["kind"] != "specification":
                raise RungError(f"{spec_rid} is not a specification", code="bad_request", status=400)
            mine = self._q1("SELECT * FROM claims WHERE spec_pk=? AND session_id=? AND status='open' ORDER BY pk "
                            "LIMIT 1", (s["pk"], session_id or ""))
            if mine is None:
                raise RungError(f"this chat holds no open claim on {spec_rid}; claim it first", code="no_claim")
            # Independence holds at the report too: a holder who wrote one of the spec's tests while it
            # held the claim is now an author, and an author does not report an independent spec done.
            why = self.exclusion(project, spec_rid, mine["profile"], ignore_claim=mine["pk"])
            wrote = [x for x in why.split("; ") if x.startswith("author of ")]
            if wrote:
                raise RungError(f"{spec_rid} needs a different profile from the author and {mine['profile']} is now the "
                                f"{wrote[0]}", code="excluded")
            chk = self.check(project, spec_rid)
            if not chk["ok"]:
                raise RungError(f"{spec_rid} is not verified: " + "; ".join(chk["blockers"]), code="not_released")
            proof = self._proof(s)
            c.execute("UPDATE claims SET status='reported', closed_at=?, closed_by=?, proof=? WHERE pk=? "
                      "AND status='open'",
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
        spec_rid = canonical_rid(spec_rid) if isinstance(spec_rid, str) else spec_rid
        with self._lock, self._tx() as c:
            self._check_writable(project, spec_rid)
            s = self._rung_row(project, spec_rid)
            if s["kind"] != "specification":
                raise RungError(f"{spec_rid} is not a specification", code="bad_request", status=400)
            rows = self._q("SELECT * FROM claims WHERE spec_pk=? AND status='open'", (s["pk"],))
            if not rows:
                raise RungError(f"no open claim on {spec_rid}", code="no_claim")
            for r in rows:
                c.execute("UPDATE claims SET status='released', closed_at=?, closed_by=? WHERE pk=? "
                          "AND status='open'",
                          (self.clock(), actor.name, r["pk"]))
                self._log(c, s["project_pk"], "claim_released", {"spec": spec_rid, "chat": r["chat"],
                                                                 "profile": r["profile"]}, actor.name)
            self._touch_project(c, s["project_pk"])
            return [self._claim_dict(self._q1("SELECT * FROM claims WHERE pk=?", (r["pk"],))) for r in rows]

    @staticmethod
    def names_spec(text: str, rid: str) -> bool:
        return bool(text) and bool(_rx_for(rid).search(normalise(text)))
