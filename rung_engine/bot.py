"""Bot help (decisions Round 13): Place, Draft and Suggest.

Every bot action asks a Hermes profile through the drafting seam and only proposes. The engine
checks what comes back (a place must exist, be live and fit the kind), keeps the job so it can be
cancelled and read back, and never stores anything as approved: a placed or drafted text lands only
when a person saves the form, a suggested requirement only when a person accepts it, and then as a
draft that is approved like any other. `rung check`, the done hook and test results never read a job.
A running Suggest counts toward its profile's `At once`, as a develop run does.
"""

from __future__ import annotations

import json

KINDS = ("need", "requirement", "specification", "test")
PARENT_KIND = {"requirement": "need", "specification": "requirement", "test": "specification"}
SUGGEST_COUNT = 3


class BotMixin:
    """Mixed into Engine. Uses its _q/_q1/_tx/_rung_row/_project_row helpers."""

    # ------------------------------------------------------------------ jobs

    def _job_row(self, job_id: int):
        from .core import NotFound
        try:
            job_id = int(job_id)
        except (TypeError, ValueError):
            raise NotFound(f"no bot job {job_id}")
        j = self._q1("SELECT * FROM bot_jobs WHERE pk = ?", (job_id,))
        if j is None:
            raise NotFound(f"no bot job {job_id}")
        return j

    def bot_job(self, job_id: int) -> dict:
        j = self._job_row(job_id)
        p = self._project_row(j["project_pk"])
        r = self._rung_by_pk(j["rung_pk"]) if j["rung_pk"] else None
        out = {"id": j["pk"], "project": p["name"], "kind": j["kind"], "rung": r["rid"] if r else None,
               "profile": j["profile"], "status": j["status"], "input": json.loads(j["input"] or "{}"),
               "result": json.loads(j["result"]) if j["result"] else None, "error": j["error"],
               "created_at": j["created_at"], "finished_at": j["finished_at"]}
        if j["kind"] == "suggest" and r is not None:
            # A result read against requirements that changed since it was asked is marked, never hidden.
            out["changed_since"] = json.loads(j["basis"] or "[]") != self._req_basis(r["pk"])
        return out

    def begin_bot(self, project: str, kind: str, rung_rid: str | None = None, profile: str = "",
                  data: dict | None = None, basis: list | None = None) -> int:
        self._check_writable(project, rung_rid)
        p = self._project_row(project)
        rung_pk = self._rung_row(project, rung_rid)["pk"] if rung_rid else None
        with self._tx() as c:
            cur = c.execute("INSERT INTO bot_jobs(project_pk, kind, rung_pk, profile, input, basis, created_at) "
                            "VALUES (?,?,?,?,?,?,?)", (p["pk"], kind, rung_pk, profile or "",
                                                       json.dumps(data or {}), json.dumps(basis or []), self.clock()))
            return int(cur.lastrowid)

    def finish_bot(self, job_id: int, result) -> bool:
        """Keep the result only while the job still runs: a job cancelled meanwhile stays cancelled."""
        with self._tx() as c:
            n = c.execute("UPDATE bot_jobs SET status='done', result=?, finished_at=? WHERE pk=? AND status='running'",
                          (json.dumps(result), self.clock(), int(job_id))).rowcount
        return bool(n)

    def fail_bot(self, job_id: int, error: str) -> bool:
        with self._tx() as c:
            n = c.execute("UPDATE bot_jobs SET status='failed', error=?, finished_at=? WHERE pk=? AND status='running'",
                          (str(error)[:500], self.clock(), int(job_id))).rowcount
        return bool(n)

    def cancel_bot(self, job_id: int) -> dict:
        j = self._job_row(job_id)
        with self._tx() as c:
            c.execute("UPDATE bot_jobs SET status='cancelled', finished_at=? WHERE pk=? AND status='running'",
                      (self.clock(), j["pk"]))
        return self.bot_job(j["pk"])

    def bot_cancelled(self, job_id: int) -> bool:
        j = self._q1("SELECT status FROM bot_jobs WHERE pk=?", (int(job_id),))
        return j is None or j["status"] == "cancelled"

    def bot_running(self, profile: str) -> int:
        """Suggest jobs a profile is running now: load toward its `At once`."""
        return self._q1("SELECT COUNT(*) FROM bot_jobs WHERE profile=? AND kind='suggest' AND status='running'",
                        (profile,))[0]

    # ------------------------------------------------------------------ Place

    def place_targets(self, project: str) -> list[dict]:
        """Every live rung a new rung may go under ({id, kind, text}), in ladder order."""
        p = self._project_row(project)
        gone = self._retired_pks(p["pk"])
        rows = self._q("SELECT * FROM rungs WHERE project_pk=? AND kind IN ('need','requirement','specification') "
                       "AND status NOT IN ('proposed','dismissed') ORDER BY num, rid", (p["pk"],))
        order = {"need": 0, "requirement": 1, "specification": 2}
        out = [{"id": r["rid"], "kind": r["kind"], "text": r["text"]} for r in rows if r["pk"] not in gone]
        return sorted(out, key=lambda r: (order[r["kind"]],))

    def check_place(self, project: str, kind: str, parent: str | None) -> str:
        """Why a new `kind` cannot go under `parent` ('' when it can): the engine's check of a placement."""
        from .core import RungError
        if kind not in KINDS:
            return f"{kind or 'that'} is not a rung kind"
        if kind == "need":
            return "" if not parent else "a need sits under no rung"
        if not parent:
            return f"a {kind} needs a {PARENT_KIND[kind]} above it"
        try:
            r = self._rung_row(project, str(parent))
        except RungError:
            return f"{parent} is not in {self._project_row(project)['name']}"
        if r["kind"] != PARENT_KIND[kind]:
            return f"a {kind} cannot sit under {r['rid']}, a {r['kind']}"
        if r["pk"] in self._retired_pks(r["project_pk"]):
            return f"{r['rid']} is retired"
        if r["status"] in ("proposed", "dismissed"):
            return f"{r['rid']} is {r['status']}"
        if kind == "requirement" and r["status"] != "approved":
            return f"{r['rid']} must be approved first"
        return ""

    def chain(self, project: str, rid: str | None) -> list[dict]:
        """The rung and everything above it, need first ({id, kind, text})."""
        out = []
        r = self._rung_row(project, rid) if rid else None
        while r is not None:
            out.append({"id": r["rid"], "kind": r["kind"], "text": r["text"]})
            r = self._rung_by_pk(r["parent_pk"]) if r["parent_pk"] else None
        return list(reversed(out))

    def chain_children(self, project: str, need_rid: str) -> list[dict]:
        """The need's current requirements ({id, text}), the ones Suggest reads."""
        need = self._rung_row(project, need_rid)
        return [{"id": r["rid"], "text": r["text"]} for r in self._q(
            "SELECT rid, text FROM rungs WHERE parent_pk=? AND kind='requirement' AND status NOT IN "
            "('proposed','dismissed') ORDER BY num, rid", (need["pk"],))]

    # ------------------------------------------------------------------ Suggest

    def _req_basis(self, need_pk: int) -> list:
        return [[r["rid"], r["version"]] for r in self._q(
            "SELECT rid, version FROM rungs WHERE parent_pk=? AND kind='requirement' AND status NOT IN "
            "('proposed','dismissed') ORDER BY num, rid", (need_pk,))]

    def suggest_choice(self, project: str, need_rid: str) -> dict:
        """Which profile Suggest asks for a need, by the Round 7 allocation rules: disabled, at capacity and
        author of any requirement of the need exclude a profile; the eligible rank as Develop ranks."""
        from . import allocation
        from .core import RungError
        need = self._rung_row(project, need_rid)
        if need["kind"] != "need":
            raise RungError(f"{need['rid']} is not a need", code="bad_request", status=400)
        authored: list[tuple[str, str]] = []
        for r in self._q("SELECT * FROM rungs WHERE parent_pk=? AND kind='requirement' AND status NOT IN "
                         "('proposed','dismissed') ORDER BY num, rid", (need["pk"],)):
            for name in self._authors_of(r):
                if (name, r["rid"]) not in authored:
                    authored.append((name, r["rid"]))
        needs = allocation.Needs(spec="", independent=True, authors=frozenset(n for n, _ in authored),
                                 authored=tuple(authored))
        facts = self._project_facts(self._project_row(need["project_pk"]))
        excluded = [{"profile": f.name, "reason": "; ".join(allocation.reasons(f, needs))}
                    for f in facts if allocation.reasons(f, needs)]
        ranked = [s.as_dict() for s in allocation.rank(facts, needs=needs)]
        return {"need": need["rid"], "chosen": ranked[0] if ranked else None, "ranked": ranked, "excluded": excluded}

    def _authors_of(self, r) -> list[str]:
        """Every profile that wrote this rung: an agent author of any version, its drafter, its proposer."""
        out: list[str] = []

        def add(name):
            if name and name not in out:
                out.append(name)
        if r["author_kind"] == "agent":
            add(r["author_name"])
        add(r["proposer"])
        for d in [json.loads(r["data"] or "{}")] + [json.loads(v["data"] or "{}") for v in
                                                    self._q("SELECT data FROM rung_versions WHERE rung_pk=?", (r["pk"],))]:
            add(d.get("drafted_by"))
            for name in d.get("drafters") or []:
                add(name)
        for v in self._q("SELECT by_name, by_kind FROM rung_versions WHERE rung_pk=?", (r["pk"],)):
            if v["by_kind"] == "agent":
                add(v["by_name"])
        return [n for n in out if n not in ("drafting", "engine")]

    def suggest_items(self, project: str, job_id: int) -> list[dict]:
        j = self.bot_job(job_id)
        if j["project"] != self._project_row(project)["name"] or j["kind"] != "suggest":
            from .core import NotFound
            raise NotFound(f"no Suggest {job_id} in {project}")
        return (j["result"] or {}).get("items", [])

    def resolve_suggest(self, project: str, job_id: int, index: int, accept: bool, actor=None) -> dict:
        """Accept adds the item as a draft requirement under the need, written by the suggesting profile
        and approved like any other; Dismiss only marks it. Nothing else in the ladder changes."""
        from .core import HUMAN, Actor, RungError
        actor = actor or HUMAN
        if not actor.is_human:
            raise RungError("only a person accepts or dismisses a suggestion", code="forbidden", status=403)
        j = self._job_row(job_id)
        need = self._rung_by_pk(j["rung_pk"])
        self._check_writable(project, need["rid"])
        if j["project_pk"] != self._project_row(project)["pk"] or j["kind"] != "suggest" or j["status"] != "done":
            raise RungError(f"Suggest {job_id} has no result to accept", code="refused")
        result = json.loads(j["result"])
        items = result.get("items", [])
        if not (0 <= int(index) < len(items)):
            raise RungError(f"Suggest {job_id} has no item {index}", code="bad_request", status=400)
        item = items[int(index)]
        if item.get("status") != "open":
            raise RungError(f"that suggestion is already {item.get('status')}")
        if accept and need["status"] != "approved":
            raise RungError(f"{need['rid']} must be approved first", code="locked")
        made = None
        with self._tx() as c:
            if accept:
                made = self._insert_rung(c, need["project_pk"], "requirement", need, item["text"], "", "draft",
                                         Actor("agent", j["profile"] or "drafting"),
                                         data={"origin": "suggested", "drafted_by": j["profile"]})
            item["status"] = "accepted" if accept else "dismissed"
            if made:
                item["rung"] = c.execute("SELECT rid FROM rungs WHERE pk=?", (made,)).fetchone()[0]
            c.execute("UPDATE bot_jobs SET result=? WHERE pk=?", (json.dumps(result), j["pk"]))
            self._touch_project(c, need["project_pk"])
        return {"job": self.bot_job(j["pk"]), "rung": self._rung_dict(self._rung_by_pk(made)) if made else None}
