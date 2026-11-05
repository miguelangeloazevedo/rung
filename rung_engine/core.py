"""The Rung engine: structure, links, gates, staleness, coverage, executions and allocation.

Everything here is deterministic. Model output only ever arrives as text handed in by a caller
(a drafting provider or a worker); the engine never calls a model and never asks one whether
work is done. A specification is released by its tests' executions and nothing else.
"""

from __future__ import annotations

import json
import string
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from . import allocation, db
from .execute import context_line, git_commit, run_command

KINDS = ("need", "requirement", "specification", "test")
CHILD_KIND = {"need": "requirement", "requirement": "specification", "specification": "test"}
PARENT_KIND = {v: k for k, v in CHILD_KIND.items()}
TEST_TYPES = ("command", "manual", "ai_judged")
GATING_TYPES = ("command", "manual")
FINAL_EXEC = ("pass", "fail")
LIVE_RUN = ("queued", "running")
STEPS = ("need", "requirements", "specifications", "tests", "develop")

DEFAULT_SETTINGS = {
    "last_project": None,
    "drafting": {"kind": "stub", "profile": "", "stub_file": "", "delay": 1.0},
    "worker": {"kind": "hermes", "stub_dir": "", "max_turns": 30},
    "test_timeout": 120,
    "output_limit": 64000,
    "run_timeout_min": 20,
    "colours": {"needs_you": "theme", "pass": "theme", "fail": "theme", "stale": "theme", "draft": "theme"},
}


class RungError(ValueError):
    """A refused operation. `code` is stable for the API layer."""

    def __init__(self, message: str, code: str = "refused", status: int = 409):
        super().__init__(message)
        self.code = code
        self.status = status


class NotFound(RungError):
    def __init__(self, message: str):
        super().__init__(message, code="not_found", status=404)


@dataclass(frozen=True)
class Actor:
    kind: str = "human"  # human | agent | engine
    name: str = "you"

    @property
    def is_human(self) -> bool:
        return self.kind == "human"

    @property
    def label(self) -> str:
        return self.name


HUMAN = Actor("human", "you")
ENGINE = Actor("engine", "engine")


def _j(v) -> str:
    return json.dumps(v, sort_keys=True)


def _l(s, default=None):
    if s is None or s == "":
        return default
    return json.loads(s)


def _letter(k: int) -> str:
    letters = string.ascii_lowercase
    return letters[k - 1] if 1 <= k <= 26 else f"z{k}"


class Engine:
    def __init__(self, path: str | Path, clock=time.time):
        self.path = str(path)
        self.conn = db.connect(path)
        self.clock = clock
        self._lock = threading.RLock()

    def close(self):
        try:
            self.conn.close()
        except Exception:
            pass

    # ------------------------------------------------------------------ plumbing

    @contextmanager
    def _tx(self):
        with self._lock:
            self.conn.execute("BEGIN IMMEDIATE")
            try:
                yield self.conn
            except BaseException:
                self.conn.execute("ROLLBACK")
                raise
            else:
                self.conn.execute(
                    "UPDATE meta SET value = CAST(value AS INTEGER) + 1 WHERE key = 'rev'"
                )
                self.conn.execute("COMMIT")

    def _q(self, sql, args=()):
        with self._lock:
            return self.conn.execute(sql, args).fetchall()

    def _q1(self, sql, args=()):
        with self._lock:
            return self.conn.execute(sql, args).fetchone()

    def _next_seq(self, c) -> int:
        c.execute("UPDATE meta SET value = CAST(value AS INTEGER) + 1 WHERE key = 'seq'")
        return int(c.execute("SELECT value FROM meta WHERE key = 'seq'").fetchone()[0])

    def rev(self) -> int:
        return int(self._q1("SELECT value FROM meta WHERE key = 'rev'")[0])

    def _touch_project(self, c, project_pk: int):
        c.execute("UPDATE projects SET last_activity = ? WHERE pk = ?", (self.clock(), project_pk))

    # ------------------------------------------------------------------ settings

    def get_setting(self, key: str):
        row = self._q1("SELECT value FROM settings WHERE key = ?", (key,))
        default = DEFAULT_SETTINGS.get(key)
        if row is None:
            return json.loads(json.dumps(default))
        value = json.loads(row[0])
        if isinstance(default, dict) and isinstance(value, dict):
            merged = dict(default)
            merged.update(value)
            return merged
        return value

    def settings(self) -> dict:
        return {k: self.get_setting(k) for k in DEFAULT_SETTINGS}

    def set_setting(self, key: str, value):
        if key not in DEFAULT_SETTINGS:
            raise RungError(f"unknown setting {key}", code="bad_request", status=400)
        with self._tx() as c:
            c.execute("INSERT OR REPLACE INTO settings(key, value) VALUES (?, ?)", (key, _j(value)))

    # ------------------------------------------------------------------ profiles

    def sync_profiles(self, names) -> None:
        """Make sure every Hermes profile has a Rung row. Existing rows are left alone."""
        with self._tx() as c:
            for n in names:
                c.execute("INSERT OR IGNORE INTO profiles(name) VALUES (?)", (n,))

    def profiles(self) -> list[dict]:
        return [self._profile_dict(r) for r in self._q("SELECT * FROM profiles ORDER BY name")]

    def profile(self, name: str) -> dict:
        r = self._q1("SELECT * FROM profiles WHERE name = ?", (name,))
        if not r:
            raise NotFound(f"no profile {name}")
        return self._profile_dict(r)

    @staticmethod
    def _profile_dict(r) -> dict:
        return {"name": r["name"], "labels": _l(r["labels"], []), "cost": r["cost"],
                "max_runs": r["max_runs"], "enabled": bool(r["enabled"])}

    def save_profiles(self, rows: list[dict]) -> None:
        """Save several profiles at once (the settings Save button)."""
        clean = []
        for row in rows:
            name = str(row.get("name", "")).strip()
            if not name:
                raise RungError("profile name missing", code="bad_request", status=400)
            labels = [str(x).strip() for x in row.get("labels", []) if str(x).strip()]
            labels = list(dict.fromkeys(labels))
            cost = int(row.get("cost", 5))
            max_runs = int(row.get("max_runs", 5))
            if not 0 <= cost <= 10:
                raise RungError("cost must be 0 to 10", code="bad_request", status=400)
            if not 1 <= max_runs <= 50:
                raise RungError("max runs must be 1 to 50", code="bad_request", status=400)
            clean.append((name, _j(labels), cost, max_runs, 1 if row.get("enabled", True) else 0))
        with self._tx() as c:
            for name, labels, cost, max_runs, enabled in clean:
                c.execute(
                    "INSERT INTO profiles(name, labels, cost, max_runs, enabled) VALUES (?,?,?,?,?) "
                    "ON CONFLICT(name) DO UPDATE SET labels=excluded.labels, cost=excluded.cost, "
                    "max_runs=excluded.max_runs, enabled=excluded.enabled",
                    (name, labels, cost, max_runs, enabled),
                )

    # ------------------------------------------------------------------ projects

    def create_project(self, name: str, folder: str, test_command: str, profiles: list[str]) -> dict:
        name = (name or "").strip()
        folder = (folder or "").strip()
        test_command = (test_command or "").strip()
        profiles = [p for p in dict.fromkeys(profiles or []) if p]
        if not name:
            raise RungError("name is required", code="bad_request", status=400)
        if not folder:
            raise RungError("folder is required", code="bad_request", status=400)
        if not test_command:
            raise RungError("test command is required", code="bad_request", status=400)
        if not profiles:
            raise RungError("tick at least one profile", code="bad_request", status=400)
        if self._q1("SELECT 1 FROM projects WHERE name = ?", (name,)):
            raise RungError(f"a project named {name} exists", code="conflict")
        now = self.clock()
        with self._tx() as c:
            for p in profiles:
                c.execute("INSERT OR IGNORE INTO profiles(name) VALUES (?)", (p,))
            cur = c.execute(
                "INSERT INTO projects(name, folder, test_command, profiles, created_at, last_activity) "
                "VALUES (?,?,?,?,?,?)", (name, folder, test_command, _j(profiles), now, now),
            )
            c.execute("INSERT OR REPLACE INTO settings(key, value) VALUES ('last_project', ?)", (_j(name),))
        return self.project(name)

    def _project_row(self, name_or_pk):
        if isinstance(name_or_pk, int):
            r = self._q1("SELECT * FROM projects WHERE pk = ?", (name_or_pk,))
        else:
            r = self._q1("SELECT * FROM projects WHERE name = ?", (name_or_pk,))
        if not r:
            raise NotFound(f"no project {name_or_pk}")
        return r

    def project(self, name: str) -> dict:
        r = self._project_row(name)
        return {"name": r["name"], "folder": r["folder"], "test_command": r["test_command"],
                "profiles": _l(r["profiles"], []), "created_at": r["created_at"],
                "last_activity": r["last_activity"]}

    def projects(self) -> list[dict]:
        out = []
        for r in self._q("SELECT name FROM projects ORDER BY last_activity DESC, name"):
            p = self.project(r["name"])
            p["stats"] = self.tiles(r["name"])
            out.append(p)
        return out

    def open_project(self, name: str) -> dict:
        self._project_row(name)
        self.set_setting("last_project", name)
        return self.project(name)

    def current_project(self) -> str | None:
        name = self.get_setting("last_project")
        if name and self._q1("SELECT 1 FROM projects WHERE name = ?", (name,)):
            return name
        r = self._q1("SELECT name FROM projects ORDER BY last_activity DESC LIMIT 1")
        return r["name"] if r else None

    # ------------------------------------------------------------------ rung access

    def _rung_row(self, project: str, rid: str):
        p = self._project_row(project)
        r = self._q1("SELECT * FROM rungs WHERE project_pk = ? AND rid = ?", (p["pk"], rid))
        if not r:
            raise NotFound(f"no {rid} in {project}")
        return r

    def _rung_by_pk(self, pk: int):
        return self._q1("SELECT * FROM rungs WHERE pk = ?", (pk,))

    def _children_rows(self, pk: int, include_dismissed=False):
        rows = self._q("SELECT * FROM rungs WHERE parent_pk = ? ORDER BY num", (pk,))
        return [r for r in rows if include_dismissed or r["status"] != "dismissed"]

    def _descendants(self, pk: int) -> list:
        out = []
        stack = [pk]
        while stack:
            cur = stack.pop()
            for r in self._q("SELECT * FROM rungs WHERE parent_pk = ? ORDER BY num", (cur,)):
                out.append(r)
                stack.append(r["pk"])
        return out

    def _rid_of(self, pk):
        if pk is None:
            return None
        r = self._rung_by_pk(pk)
        return r["rid"] if r else None

    def rung(self, project: str, rid: str) -> dict:
        return self._rung_dict(self._rung_row(project, rid))

    def _rung_dict(self, r) -> dict:
        data = _l(r["data"], {})
        d = {
            "id": r["rid"], "kind": r["kind"], "parent": self._rid_of(r["parent_pk"]),
            "text": r["text"], "detail": r["detail"], "status": r["status"], "version": r["version"],
            "author": {"kind": r["author_kind"], "name": r["author_name"]},
            "approved_by": r["approved_by"], "approved_at": r["approved_at"],
            "proposer": r["proposer"], "source_chat": r["source_chat"],
            "created_at": r["created_at"], "updated_at": r["updated_at"],
        }
        d.update(data)
        return d

    def tree(self, project: str) -> list[dict]:
        """The whole ladder, nested, without dismissed rungs."""
        p = self._project_row(project)

        def build(row):
            d = self._rung_dict(row)
            kids = self._children_rows(row["pk"])
            d["children"] = [build(k) for k in kids if k["status"] != "proposed"]
            if row["kind"] == "requirement":
                d["coverage"] = self._req_coverage(row)
            if row["kind"] == "specification":
                ok, blockers = self._released(row)
                d["released"] = ok
                d["blockers"] = blockers
                d["carried_by"] = self._carried_by(row)
            if row["kind"] == "test":
                d["result"] = self._test_result(row)
            return d

        needs = self._q(
            "SELECT * FROM rungs WHERE project_pk = ? AND kind = 'need' AND status NOT IN ('dismissed','proposed') "
            "ORDER BY num", (p["pk"],),
        )
        return [build(n) for n in needs]

    # ------------------------------------------------------------------ creation

    def _insert_rung(self, c, project_pk, kind, parent_row, text, detail, status, actor: Actor,
                     data=None, proposer=None, source_chat=None) -> int:
        text = (text or "").strip()
        if kind != "test" and not text:
            raise RungError(f"{kind} text is required", code="bad_request", status=400)
        if kind == "need":
            if parent_row is not None:
                raise RungError("a need has no parent", code="bad_request", status=400)
            num = (c.execute("SELECT COALESCE(MAX(num),0) FROM rungs WHERE project_pk=? AND kind='need'",
                             (project_pk,)).fetchone()[0]) + 1
            rid = f"N-{num}"
        else:
            if parent_row is None or parent_row["kind"] != PARENT_KIND[kind]:
                raise RungError(f"a {kind} needs a {PARENT_KIND[kind]} parent", code="bad_request", status=400)
            if parent_row["status"] in ("dismissed", "proposed"):
                raise RungError(f"{parent_row['rid']} is not on the ladder", code="refused")
            if kind == "requirement":
                num = (c.execute("SELECT COALESCE(MAX(num),0) FROM rungs WHERE project_pk=? AND kind='requirement'",
                                 (project_pk,)).fetchone()[0]) + 1
                rid = f"R-{num}"
            elif kind == "specification":
                num = (c.execute("SELECT COALESCE(MAX(num),0) FROM rungs WHERE parent_pk=?",
                                 (parent_row["pk"],)).fetchone()[0]) + 1
                rid = f"S-{parent_row['num']}.{num}"
            else:
                num = (c.execute("SELECT COALESCE(MAX(num),0) FROM rungs WHERE parent_pk=?",
                                 (parent_row["pk"],)).fetchone()[0]) + 1
                rid = f"T-{parent_row['rid'][2:]}{_letter(num)}"
        now = self.clock()
        approved_by = actor.name if status == "approved" else None
        approved_at = now if status == "approved" else None
        cur = c.execute(
            "INSERT INTO rungs(project_pk, rid, kind, parent_pk, num, text, detail, status, version, "
            "author_kind, author_name, approved_by, approved_at, proposer, source_chat, data, created_at, updated_at) "
            "VALUES (?,?,?,?,?,?,?,?,1,?,?,?,?,?,?,?,?,?)",
            (project_pk, rid, kind, parent_row["pk"] if parent_row is not None else None, num, text,
             (detail or "").strip(), status, actor.kind, actor.name, approved_by, approved_at, proposer,
             source_chat, _j(data or {}), now, now),
        )
        pk = cur.lastrowid
        c.execute(
            "INSERT INTO rung_versions(rung_pk, version, text, detail, data, at, by_name, by_kind) "
            "VALUES (?,?,?,?,?,?,?,?)", (pk, 1, text, (detail or "").strip(), _j(data or {}), now,
                                       actor.name, actor.kind),
        )
        self._touch_project(c, project_pk)
        return pk

    def create_need(self, project: str, text: str, actor: Actor = HUMAN,
                    requirements: list[str] | None = None) -> dict:
        """A need written by a human is approved on creation (the Create need press)."""
        if not actor.is_human:
            raise RungError("agents propose needs, they cannot create them", code="forbidden", status=403)
        p = self._project_row(project)
        with self._tx() as c:
            pk = self._insert_rung(c, p["pk"], "need", None, text, "", "approved", actor)
            need = c.execute("SELECT * FROM rungs WHERE pk = ?", (pk,)).fetchone()
            for t in requirements or []:
                self._insert_rung(c, p["pk"], "requirement", need, t, "", "draft", Actor("agent", "drafting"),
                                  data={"origin": "suggested"})
        return self._rung_dict(self._rung_by_pk(pk))

    def add_requirement(self, project: str, need_rid: str, text: str, actor: Actor = HUMAN,
                        detail: str = "") -> dict:
        need = self._rung_row(project, need_rid)
        if need["kind"] != "need":
            raise RungError(f"{need_rid} is not a need", code="bad_request", status=400)
        if need["status"] != "approved":
            raise RungError(f"{need_rid} must be approved first", code="locked")
        with self._tx() as c:
            pk = self._insert_rung(c, need["project_pk"], "requirement", need, text, detail, "draft", actor)
        return self._rung_dict(self._rung_by_pk(pk))

    def propose(self, project: str, parent_rid: str, kind: str, text: str, proposer: str,
                source_chat: str = "", detail: str = "") -> dict:
        """An agent proposes a rung. It waits under Needs you until a human accepts or dismisses it."""
        parent = self._rung_row(project, parent_rid)
        if CHILD_KIND.get(parent["kind"]) != kind:
            raise RungError(f"a {kind} cannot sit under {parent_rid}", code="bad_request", status=400)
        with self._tx() as c:
            pk = self._insert_rung(c, parent["project_pk"], kind, parent, text, detail, "proposed",
                                   Actor("agent", proposer), proposer=proposer, source_chat=source_chat)
        return self._rung_dict(self._rung_by_pk(pk))

    def dismiss(self, project: str, rid: str, actor: Actor = HUMAN) -> None:
        """Dismiss a proposal or an unapproved draft. A dismissed proposal leaves no rung."""
        if not actor.is_human:
            raise RungError("only a human can dismiss", code="forbidden", status=403)
        r = self._rung_row(project, rid)
        if r["status"] not in ("proposed", "draft"):
            raise RungError(f"{rid} is {r['status']}; only proposals and drafts can be dismissed")
        if self._q("SELECT 1 FROM rungs WHERE parent_pk = ?", (r["pk"],)):
            raise RungError(f"{rid} has rungs below it")
        with self._tx() as c:
            c.execute("DELETE FROM rungs WHERE pk = ?", (r["pk"],))
            self._touch_project(c, r["project_pk"])

    # ------------------------------------------------------------------ suggestions

    def add_suggestions(self, project: str, parent_rid: str | None, target: str, texts: list[str]) -> list[dict]:
        p = self._project_row(project)
        parent_pk = self._rung_row(project, parent_rid)["pk"] if parent_rid else None
        now = self.clock()
        with self._tx() as c:
            for t in texts:
                t = (t or "").strip()
                if not t:
                    continue
                dup = c.execute(
                    "SELECT 1 FROM suggestions WHERE project_pk=? AND parent_pk IS ? AND target=? AND text=?",
                    (p["pk"], parent_pk, target, t)).fetchone()
                if not dup:
                    c.execute("INSERT INTO suggestions(project_pk, parent_pk, target, text, created_at) "
                              "VALUES (?,?,?,?,?)", (p["pk"], parent_pk, target, t, now))
        return self.suggestions(project, parent_rid, target)

    def suggestions(self, project: str, parent_rid: str | None, target: str, status="open") -> list[dict]:
        p = self._project_row(project)
        parent_pk = self._rung_row(project, parent_rid)["pk"] if parent_rid else None
        rows = self._q("SELECT * FROM suggestions WHERE project_pk=? AND parent_pk IS ? AND target=? AND status=? "
                       "ORDER BY pk", (p["pk"], parent_pk, target, status))
        return [{"id": r["pk"], "text": r["text"], "status": r["status"], "target": r["target"]} for r in rows]

    def resolve_suggestion(self, project: str, suggestion_id: int, accept: bool, actor: Actor = HUMAN) -> dict | None:
        if not actor.is_human:
            raise RungError("only a human can accept or dismiss suggestions", code="forbidden", status=403)
        p = self._project_row(project)
        s = self._q1("SELECT * FROM suggestions WHERE pk = ? AND project_pk = ?", (suggestion_id, p["pk"]))
        if not s or s["status"] != "open":
            raise NotFound(f"no open suggestion {suggestion_id}")
        made = None
        with self._tx() as c:
            c.execute("UPDATE suggestions SET status = ? WHERE pk = ?", ("accepted" if accept else "dismissed", s["pk"]))
            if accept and s["target"] == "requirement":
                parent = c.execute("SELECT * FROM rungs WHERE pk = ?", (s["parent_pk"],)).fetchone()
                pk = self._insert_rung(c, p["pk"], "requirement", parent, s["text"], "", "draft",
                                       Actor("agent", "drafting"), data={"origin": "suggested"})
                made = pk
            elif accept and s["target"] == "edit":
                r = c.execute("SELECT * FROM rungs WHERE pk = ?", (s["parent_pk"],)).fetchone()
                detail = (r["detail"] + "\n" if r["detail"] else "") + s["text"]
                c.execute("UPDATE rungs SET detail = ?, updated_at = ? WHERE pk = ?", (detail, self.clock(), r["pk"]))
        return self._rung_dict(self._rung_by_pk(made)) if made else None

    # ------------------------------------------------------------------ edit, approve, staleness

    def edit(self, project: str, rid: str, text: str | None = None, detail: str | None = None,
             actor: Actor = HUMAN, approve: bool = False, data: dict | None = None) -> dict:
        """Change a rung's text. If it changes after approval, everything that hangs below goes stale."""
        r = self._rung_row(project, rid)
        if not actor.is_human:
            raise RungError("agents cannot edit rungs; propose instead", code="forbidden", status=403)
        if r["status"] == "proposed":
            raise RungError(f"{rid} is a proposal; accept or dismiss it first")
        if r["kind"] == "specification":
            st = _l(r["data"], {}).get("draft_state")
            if st == "drafting":
                raise RungError(f"{rid} is still drafting", code="locked")
        new_text = r["text"] if text is None else text.strip()
        new_detail = r["detail"] if detail is None else detail.strip()
        new_data = _l(r["data"], {})
        if data:
            new_data.update(data)
        if r["kind"] != "test" and not new_text:
            raise RungError("text is required", code="bad_request", status=400)
        changed = (new_text != r["text"]) or (new_detail != r["detail"])
        data_changed = new_data != _l(r["data"], {})
        now = self.clock()
        stale_rids: list[str] = []
        with self._tx() as c:
            version = r["version"]
            if changed or data_changed:
                version += 1
                c.execute("INSERT INTO rung_versions(rung_pk, version, text, detail, data, at, by_name, by_kind) "
                          "VALUES (?,?,?,?,?,?,?,?)", (r["pk"], version, new_text, new_detail, _j(new_data), now,
                                                       actor.name, actor.kind))
            was_approved = r["status"] in ("approved", "stale") and r["approved_at"] is not None
            if changed and was_approved:
                seq = self._next_seq(c)
                stale_rids = self._mark_downstream_stale(c, r, seq, f"{rid} edited")
                if r["kind"] == "test":
                    c.execute("UPDATE rungs SET valid_from = ? WHERE pk = ?", (seq, r["pk"]))
                c.execute(
                    "INSERT INTO changes(project_pk, rung_pk, seq, before_text, after_text, before_detail, "
                    "after_detail, from_version, to_version, stale, at, by_name) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                    (r["project_pk"], r["pk"], seq, r["text"], new_text, r["detail"], new_detail, r["version"],
                     version, _j(stale_rids), now, actor.name),
                )
            if approve:
                status, ab, at = "approved", actor.name, now
            elif changed or data_changed:
                status, ab, at = ("draft", None, None) if r["status"] != "stale" else ("stale", r["approved_by"], r["approved_at"])
                if r["kind"] == "test" and r["status"] == "approved":
                    status, ab, at = "draft", None, None
            else:
                status, ab, at = r["status"], r["approved_by"], r["approved_at"]
            if r["kind"] == "specification" and (changed or approve):
                new_data["draft_state"] = "drafted" if new_text else new_data.get("draft_state")
            c.execute("UPDATE rungs SET text=?, detail=?, data=?, version=?, status=?, approved_by=?, approved_at=?, "
                      "updated_at=? WHERE pk=?", (new_text, new_detail, _j(new_data), version, status, ab, at, now, r["pk"]))
            self._touch_project(c, r["project_pk"])
        return self._rung_dict(self._rung_by_pk(r["pk"]))

    def _mark_downstream_stale(self, c, root, seq: int, reason: str) -> list[str]:
        out = []
        for d in self._descendants(root["pk"]):
            data = _l(d["data"], {})
            if d["kind"] == "test":
                has_exec = c.execute("SELECT 1 FROM executions WHERE test_pk = ? LIMIT 1", (d["pk"],)).fetchone()
                data["invalidated_by"] = reason
                c.execute("UPDATE rungs SET valid_from = ?, data = ? WHERE pk = ?", (seq, _j(data), d["pk"]))
                if d["status"] == "approved" and has_exec:
                    c.execute("UPDATE rungs SET status='stale', updated_at=? WHERE pk=?", (self.clock(), d["pk"]))
                    out.append(d["rid"])
            elif d["status"] == "approved":
                data["stale_reason"] = reason
                c.execute("UPDATE rungs SET status='stale', data=?, updated_at=? WHERE pk=?",
                          (_j(data), self.clock(), d["pk"]))
                out.append(d["rid"])
        return out

    def approve(self, project: str, rid: str, actor: Actor = HUMAN) -> dict:
        """Human approval. Agents never approve, including their own proposals."""
        if not actor.is_human:
            raise RungError("only a human can approve", code="forbidden", status=403)
        r = self._rung_row(project, rid)
        if r["status"] == "approved":
            return self._rung_dict(r)
        if r["status"] not in ("draft", "proposed", "stale"):
            raise RungError(f"{rid} is {r['status']}")
        if r["parent_pk"] is not None:
            parent = self._rung_by_pk(r["parent_pk"])
            if parent["status"] in ("proposed", "dismissed"):
                raise RungError(f"{parent['rid']} is not on the ladder")
        data = _l(r["data"], {})
        if r["kind"] == "specification":
            if data.get("draft_state") == "drafting":
                raise RungError(f"{rid} is still drafting", code="locked")
            if not r["text"]:
                raise RungError(f"{rid} has no text yet", code="locked")
        if r["kind"] == "test":
            self._validate_test(r["text"], data)
        now = self.clock()
        with self._tx() as c:
            data.pop("stale_reason", None)
            c.execute("UPDATE rungs SET status='approved', approved_by=?, approved_at=?, data=?, updated_at=? WHERE pk=?",
                      (actor.name, now, _j(data), now, r["pk"]))
            if r["kind"] == "specification" and r["status"] == "stale":
                # Approved as still valid: its tests are still the right tests, but their old results
                # keep not counting (valid_from was moved when the upstream change happened).
                for t in self._children_rows(r["pk"]):
                    if t["status"] == "stale":
                        c.execute("UPDATE rungs SET status='approved', updated_at=? WHERE pk=?", (now, t["pk"]))
            self._touch_project(c, r["project_pk"])
        return self._rung_dict(self._rung_by_pk(r["pk"]))

    def history(self, project: str, rid: str) -> list[dict]:
        r = self._rung_row(project, rid)
        return [{"version": v["version"], "text": v["text"], "detail": v["detail"], "at": v["at"],
                 "by": v["by_name"], "by_kind": v["by_kind"]}
                for v in self._q("SELECT * FROM rung_versions WHERE rung_pk = ? ORDER BY version", (r["pk"],))]

    def changes(self, project: str, rid: str | None = None) -> list[dict]:
        p = self._project_row(project)
        if rid:
            r = self._rung_row(project, rid)
            rows = self._q("SELECT * FROM changes WHERE rung_pk = ? ORDER BY seq DESC", (r["pk"],))
        else:
            rows = self._q("SELECT * FROM changes WHERE project_pk = ? ORDER BY seq DESC", (p["pk"],))
        return [self._change_dict(x) for x in rows]

    def _change_dict(self, x) -> dict:
        stale = _l(x["stale"], [])
        return {"id": x["pk"], "rung": self._rid_of(x["rung_pk"]), "before": x["before_text"],
                "after": x["after_text"], "before_detail": x["before_detail"], "after_detail": x["after_detail"],
                "from_version": x["from_version"], "to_version": x["to_version"], "stale": stale,
                "at": x["at"], "by": x["by_name"]}

    def change_for(self, project: str, rid: str) -> dict | None:
        """The upstream change that made this rung stale (the latest change above it)."""
        r = self._rung_row(project, rid)
        chain = []
        cur = r
        while cur is not None:
            chain.append(cur["pk"])
            cur = self._rung_by_pk(cur["parent_pk"]) if cur["parent_pk"] else None
        rows = self._q(f"SELECT * FROM changes WHERE rung_pk IN ({','.join('?' * len(chain))}) ORDER BY seq DESC",
                       tuple(chain))
        for x in rows:
            if rid in _l(x["stale"], []) or x["rung_pk"] == r["pk"]:
                return self._change_dict(x)
        return self._change_dict(rows[0]) if rows else None

    # ------------------------------------------------------------------ specifications

    def set_authoring(self, project: str, req_rid: str, mode: str, actor: Actor = HUMAN) -> dict | None:
        """Per requirement: 'ai' (AI derives) or 'human' (I write, AI supports).

        AI mode creates a specification in draft state 'drafting'; a drafting job fills it in.
        """
        if mode not in ("ai", "human"):
            raise RungError("mode is ai or human", code="bad_request", status=400)
        req = self._rung_row(project, req_rid)
        if req["kind"] != "requirement":
            raise RungError(f"{req_rid} is not a requirement", code="bad_request", status=400)
        need = self._rung_by_pk(req["parent_pk"])
        self._require_step(project, need["rid"], "specifications")
        existing = [s for s in self._children_rows(req["pk"]) if s["status"] != "proposed"]
        data = _l(req["data"], {})
        with self._tx() as c:
            data["authoring"] = mode
            c.execute("UPDATE rungs SET data = ? WHERE pk = ?", (_j(data), req["pk"]))
            spec_pk = None
            if not existing:
                if mode == "ai":
                    spec_pk = self._insert_rung(c, req["project_pk"], "specification", req, "(drafting)", "", "draft",
                                                Actor("agent", "drafting"),
                                                data={"draft_state": "drafting", "author_role": "agent", "tags": [],
                                                      "required_tags": []})
                    c.execute("UPDATE rungs SET text = '' WHERE pk = ?", (spec_pk,))
            elif mode == "ai":
                for s in existing:
                    sd = _l(s["data"], {})
                    if s["status"] == "draft" and not s["text"]:
                        sd["draft_state"] = "drafting"
                        c.execute("UPDATE rungs SET data = ? WHERE pk = ?", (_j(sd), s["pk"]))
                        spec_pk = s["pk"]
        return self._rung_dict(self._rung_by_pk(spec_pk)) if spec_pk else None

    def finish_draft(self, project: str, spec_rid: str, text: str, detail: str = "", tags=None,
                     required_tags=None, drafted_by: str = "drafting") -> dict:
        """A drafting provider delivers the text of an AI-derived specification."""
        r = self._rung_row(project, spec_rid)
        if r["kind"] != "specification":
            raise RungError(f"{spec_rid} is not a specification", code="bad_request", status=400)
        data = _l(r["data"], {})
        data.update({"draft_state": "drafted", "author_role": "agent", "drafted_by": drafted_by})
        if tags is not None:
            data["tags"] = list(tags)
        if required_tags is not None:
            data["required_tags"] = list(required_tags)
        now = self.clock()
        with self._tx() as c:
            c.execute("UPDATE rungs SET text=?, detail=?, data=?, author_kind='agent', author_name=?, updated_at=? "
                      "WHERE pk=?", (text.strip(), (detail or "").strip(), _j(data), drafted_by, now, r["pk"]))
            c.execute("UPDATE rung_versions SET text=?, detail=?, data=? WHERE rung_pk=? AND version=?",
                      (text.strip(), (detail or "").strip(), _j(data), r["pk"], r["version"]))
            self._touch_project(c, r["project_pk"])
        return self._rung_dict(self._rung_by_pk(r["pk"]))

    def fail_draft(self, project: str, spec_rid: str, reason: str) -> None:
        r = self._rung_row(project, spec_rid)
        data = _l(r["data"], {})
        data.update({"draft_state": "failed", "draft_error": reason[:500]})
        with self._tx() as c:
            c.execute("UPDATE rungs SET data=? WHERE pk=?", (_j(data), r["pk"]))

    def write_spec(self, project: str, req_rid: str, text: str, detail: str = "", actor: Actor = HUMAN,
                   tags=None, required_tags=None, suggestion: str | None = None) -> dict:
        """The human-written specification for a requirement in 'I write, AI supports' mode."""
        if not actor.is_human:
            raise RungError("agents draft through AI derives", code="forbidden", status=403)
        req = self._rung_row(project, req_rid)
        need = self._rung_by_pk(req["parent_pk"])
        self._require_step(project, need["rid"], "specifications")
        existing = [s for s in self._children_rows(req["pk"]) if s["status"] != "proposed"]
        data = {"draft_state": "drafted", "author_role": "human", "tags": list(tags or []),
                "required_tags": list(required_tags or [])}
        if suggestion is not None:
            data["suggestion"] = suggestion
        if existing:
            return self.edit(project, existing[0]["rid"], text=text, detail=detail, actor=actor,
                             data=data)
        with self._tx() as c:
            pk = self._insert_rung(c, req["project_pk"], "specification", req, text, detail, "draft", actor, data=data)
        return self._rung_dict(self._rung_by_pk(pk))

    def approve_drafted(self, project: str, need_rid: str, actor: Actor = HUMAN) -> list[str]:
        """The Specifications step's approve button. Locked while anything drafts or is missing."""
        flow = self.flow(project, need_rid)
        st = flow["steps"]["specifications"]
        if not st["available"]:
            raise RungError("the Specifications step is locked", code="locked")
        if not st["can_approve"]:
            raise RungError(st["blocked_by"] or "specifications are not ready", code="locked")
        out = []
        for req in self._active_reqs(self._rung_row(project, need_rid)["pk"]):
            for s in self._children_rows(req["pk"]):
                if s["status"] == "draft":
                    self.approve(project, s["rid"], actor)
                    out.append(s["rid"])
        return out

    # ------------------------------------------------------------------ tests

    def _validate_test(self, text, data):
        t = data.get("type", "command")
        if t not in TEST_TYPES:
            raise RungError(f"test type {t} unknown", code="bad_request", status=400)
        if t == "command" and not (data.get("command") or "").strip():
            raise RungError("a command test needs a command", code="bad_request", status=400)
        if t == "manual" and not [s for s in data.get("steps", []) if str(s).strip()]:
            raise RungError("a manual test needs steps", code="bad_request", status=400)

    def _test_data(self, project_row, spec_row, fields: dict, base: dict | None = None) -> dict:
        d = dict(base or {})
        settings_timeout = self.get_setting("test_timeout")
        settings_limit = self.get_setting("output_limit")
        t = fields.get("type", d.get("type", "command"))
        d["type"] = t
        if t == "manual":
            d["steps"] = [str(s).strip() for s in fields.get("steps", d.get("steps", [])) if str(s).strip()]
            for k in ("command", "folder", "pass_rule", "timeout", "output_limit"):
                d.pop(k, None)
        else:
            d["command"] = (fields.get("command", d.get("command", "")) or "").strip()
            d["folder"] = (fields.get("folder", d.get("folder", ".")) or ".").strip()
            d["pass_rule"] = fields.get("pass_rule", d.get("pass_rule", {"kind": "exit_code", "value": 0}))
            d["timeout"] = int(fields.get("timeout", d.get("timeout", settings_timeout)))
            d["output_limit"] = int(fields.get("output_limit", d.get("output_limit", settings_limit)))
            d.pop("steps", None)
            if t == "ai_judged":
                d["releases_gate"] = False
        if t != "ai_judged":
            d.pop("releases_gate", None)
        return d

    def add_test(self, project: str, spec_rid: str, fields: dict, actor: Actor = HUMAN,
                 status: str = "draft") -> dict:
        spec = self._rung_row(project, spec_rid)
        if spec["kind"] != "specification":
            raise RungError(f"{spec_rid} is not a specification", code="bad_request", status=400)
        if status == "approved" and not actor.is_human:
            raise RungError("only a human can accept a test", code="forbidden", status=403)
        p = self._project_row(spec["project_pk"])
        data = self._test_data(p, spec, fields)
        self._validate_test(fields.get("text", ""), data)
        text = (fields.get("text") or "").strip()
        if not text:
            text = data.get("command") or ("Manual: " + "; ".join(data.get("steps", []))[:120])
        with self._tx() as c:
            pk = self._insert_rung(c, spec["project_pk"], "test", spec, text, "", status, actor, data=data)
        return self._rung_dict(self._rung_by_pk(pk))

    def edit_test(self, project: str, test_rid: str, fields: dict, actor: Actor = HUMAN) -> dict:
        r = self._rung_row(project, test_rid)
        if r["kind"] != "test":
            raise RungError(f"{test_rid} is not a test", code="bad_request", status=400)
        p = self._project_row(r["project_pk"])
        spec = self._rung_by_pk(r["parent_pk"])
        data = self._test_data(p, spec, fields, base=_l(r["data"], {}))
        self._validate_test(fields.get("text", r["text"]), data)
        text = (fields.get("text") or "").strip()
        if not text:
            old = _l(r["data"], {})
            auto_old = old.get("command") or ""
            text = r["text"] if r["text"] and r["text"] != auto_old else (
                data.get("command") or ("Manual: " + "; ".join(data.get("steps", []))[:120]))
        # A different command or type makes earlier results of this test stop counting.
        old = _l(r["data"], {})
        semantic = any(old.get(k) != data.get(k) for k in ("type", "command", "folder", "pass_rule", "steps"))
        out = self.edit(project, test_rid, text=text, actor=actor, data=data, approve=False)
        if semantic and self._q1("SELECT 1 FROM executions WHERE test_pk = ?", (r["pk"],)):
            with self._tx() as c:
                seq = self._next_seq(c)
                d = _l(self._rung_by_pk(r["pk"])["data"], {})
                d["invalidated_by"] = f"{test_rid} edited"
                c.execute("UPDATE rungs SET valid_from=?, data=? WHERE pk=?", (seq, _j(d), r["pk"]))
            out = self.rung(project, test_rid)
        return out

    def approve_tests(self, project: str, need_rid: str, actor: Actor = HUMAN) -> None:
        """The Tests step's approve button. Locked until every test is accepted."""
        if not actor.is_human:
            raise RungError("only a human can approve", code="forbidden", status=403)
        flow = self.flow(project, need_rid)
        st = flow["steps"]["tests"]
        if not st["available"]:
            raise RungError("the Tests step is locked", code="locked")
        if not st["can_approve"]:
            raise RungError(st["blocked_by"] or "tests are not all accepted", code="locked")
        need = self._rung_row(project, need_rid)
        data = _l(need["data"], {})
        data["tests_approved"] = True
        data["tests_approved_by"] = actor.name
        with self._tx() as c:
            c.execute("UPDATE rungs SET data=? WHERE pk=?", (_j(data), need["pk"]))
            self._touch_project(c, need["project_pk"])

    def approve_requirements(self, project: str, need_rid: str, actor: Actor = HUMAN) -> list[str]:
        """The Requirements step's Approve all."""
        flow = self.flow(project, need_rid)
        st = flow["steps"]["requirements"]
        if not st["available"]:
            raise RungError("the Requirements step is locked", code="locked")
        need = self._rung_row(project, need_rid)
        reqs = self._active_reqs(need["pk"])
        if not reqs:
            raise RungError("add a requirement first", code="locked")
        out = []
        for r in reqs:
            if r["status"] in ("draft", "stale"):
                self.approve(project, r["rid"], actor)
                out.append(r["rid"])
        return out

    # ------------------------------------------------------------------ build flow (the five-step strip)

    def _active_reqs(self, need_pk: int):
        return [r for r in self._children_rows(need_pk) if r["status"] not in ("proposed", "dismissed")]

    def flow(self, project: str, need_rid: str) -> dict:
        need = self._rung_row(project, need_rid)
        if need["kind"] != "need":
            raise RungError(f"{need_rid} is not a need", code="bad_request", status=400)
        steps = {}
        need_ok = need["status"] == "approved"
        steps["need"] = {"available": True, "done": need_ok, "can_approve": need["status"] in ("draft", "stale"),
                         "blocked_by": None if need_ok else f"{need_rid} is {need['status']}"}
        reqs = self._active_reqs(need["pk"])
        reqs_ok = need_ok and bool(reqs) and all(r["status"] == "approved" for r in reqs)
        unapproved = [r["rid"] for r in reqs if r["status"] != "approved"]
        steps["requirements"] = {
            "available": need_ok, "done": reqs_ok, "can_approve": need_ok and bool(reqs),
            "blocked_by": None if reqs_ok else ("no requirements yet" if not reqs else
                                                "not approved: " + ", ".join(unapproved)),
        }
        specs_avail = reqs_ok
        drafting, missing, pending, all_specs = [], [], [], []
        for r in reqs:
            ss = [s for s in self._children_rows(r["pk"]) if s["status"] != "proposed"]
            mode = _l(r["data"], {}).get("authoring")
            if not ss:
                missing.append(r["rid"])
            for s in ss:
                all_specs.append(s)
                st = _l(s["data"], {}).get("draft_state")
                if st == "drafting":
                    drafting.append(s["rid"])
                elif not s["text"]:
                    missing.append(r["rid"])
                if s["status"] != "approved":
                    pending.append(s["rid"])
            if mode is None and not ss:
                pass
        specs_ok = specs_avail and not missing and not drafting and not pending and bool(all_specs)
        can_approve_specs = specs_avail and not missing and not drafting and bool(all_specs)
        blocked = None
        if drafting:
            blocked = "drafting: " + ", ".join(drafting)
        elif missing:
            blocked = "no specification for " + ", ".join(dict.fromkeys(missing))
        elif pending:
            blocked = "not approved: " + ", ".join(pending)
        steps["specifications"] = {"available": specs_avail, "done": specs_ok, "can_approve": can_approve_specs,
                                   "blocked_by": None if specs_ok else (blocked or "locked")}
        tests_avail = specs_ok
        no_tests, unaccepted = [], []
        for s in all_specs:
            ts = [t for t in self._children_rows(s["pk"]) if t["status"] != "proposed"]
            if not ts:
                no_tests.append(s["rid"])
            unaccepted += [t["rid"] for t in ts if t["status"] not in ("approved", "stale")]
        can_approve_tests = tests_avail and not no_tests and not unaccepted
        tests_flag = bool(_l(need["data"], {}).get("tests_approved"))
        tests_ok = can_approve_tests and tests_flag
        tb = None
        if unaccepted:
            tb = "not accepted: " + ", ".join(unaccepted)
        elif no_tests:
            tb = "no tests for " + ", ".join(no_tests)
        steps["tests"] = {"available": tests_avail, "done": tests_ok, "can_approve": can_approve_tests,
                          "blocked_by": None if tests_ok else (tb or ("locked" if not tests_avail else "press Approve tests"))}
        steps["develop"] = {"available": tests_ok, "done": False, "can_approve": False,
                            "blocked_by": None if tests_ok else "locked"}
        current = next((k for k in STEPS if steps[k]["available"] and not steps[k]["done"]), "develop")
        return {"need": need_rid, "steps": steps, "current": current, "order": list(STEPS)}

    def _require_step(self, project: str, need_rid: str, step: str):
        f = self.flow(project, need_rid)
        if not f["steps"][step]["available"]:
            raise RungError(f"the {step.capitalize()} step is locked", code="locked")

    def _need_of(self, row):
        cur = row
        while cur is not None and cur["kind"] != "need":
            cur = self._rung_by_pk(cur["parent_pk"]) if cur["parent_pk"] else None
        return cur

    # ------------------------------------------------------------------ executions

    def _exec_dict(self, e, test_row=None) -> dict:
        test_row = test_row or self._rung_by_pk(e["test_pk"])
        counts = e["seq"] > test_row["valid_from"] and e["status"] in FINAL_EXEC
        d = {k: e[k] for k in ("n", "kind", "status", "exit_code", "output", "command", "carried_by", "attempt",
                               "context", "note", "recorder", "approved_by", "approved_at", "started_at", "ended_at")}
        d["commit"] = e["commit_ref"]
        d["test"] = test_row["rid"]
        d["counts"] = bool(counts)
        d["invalidated"] = e["seq"] <= test_row["valid_from"] and e["status"] in FINAL_EXEC + ("pending",)
        d["invalidated_by"] = _l(test_row["data"], {}).get("invalidated_by") if d["invalidated"] else None
        d["run"] = e["run_pk"]
        d["duration"] = (e["ended_at"] - e["started_at"]) if e["ended_at"] else None
        return d

    def executions(self, project: str, test_rid: str) -> list[dict]:
        t = self._rung_row(project, test_rid)
        rows = self._q("SELECT * FROM executions WHERE test_pk = ? ORDER BY n DESC", (t["pk"],))
        return [self._exec_dict(e, t) for e in rows]

    def execution(self, project: str, test_rid: str, n: int) -> dict:
        t = self._rung_row(project, test_rid)
        e = self._q1("SELECT * FROM executions WHERE test_pk = ? AND n = ?", (t["pk"], int(n)))
        if not e:
            raise NotFound(f"no execution #{n} of {test_rid}")
        return self._exec_dict(e, t)

    def begin_execution(self, project: str, test_rid: str, carried_by: str = "engine", run_pk=None,
                        attempt=None) -> int:
        """Create a running command execution and return its number. perform_execution runs it."""
        t = self._rung_row(project, test_rid)
        data = _l(t["data"], {})
        if data.get("type") == "manual":
            raise RungError("a manual test is recorded by a human, not run", code="bad_request", status=400)
        if t["status"] not in ("approved", "stale", "draft"):
            raise RungError(f"{test_rid} is {t['status']}")
        p = self._project_row(t["project_pk"])
        folder = Path(p["folder"]).expanduser() / data.get("folder", ".")
        with self._tx() as c:
            n = c.execute("SELECT COALESCE(MAX(n),0)+1 FROM executions WHERE test_pk=?", (t["pk"],)).fetchone()[0]
            seq = self._next_seq(c)
            c.execute("INSERT INTO executions(test_pk, n, seq, kind, status, command, carried_by, run_pk, attempt, "
                      "context, commit_ref, started_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                      (t["pk"], n, seq, data.get("type", "command"), "running", data.get("command", ""), carried_by,
                       run_pk, attempt, context_line(), git_commit(folder), self.clock()))
            self._touch_project(c, t["project_pk"])
        return n

    def perform_execution(self, project: str, test_rid: str, n: int, should_cancel=None, env=None) -> dict:
        t = self._rung_row(project, test_rid)
        data = _l(t["data"], {})
        p = self._project_row(t["project_pk"])
        folder = Path(p["folder"]).expanduser() / data.get("folder", ".")
        e = self._q1("SELECT * FROM executions WHERE test_pk = ? AND n = ?", (t["pk"], n))

        def push(text):
            with self._lock:
                self.conn.execute("UPDATE executions SET output = ? WHERE pk = ?", (text, e["pk"]))
                self.conn.execute("UPDATE meta SET value = CAST(value AS INTEGER) + 1 WHERE key = 'rev'")

        def cancelled():
            row = self._q1("SELECT status FROM executions WHERE pk = ?", (e["pk"],))
            if row and row["status"] == "cancelled":
                return True
            return bool(should_cancel and should_cancel())

        if not folder.is_dir():
            res_exit, res_out, status = None, f"folder not found: {folder}", "error"
        else:
            res = run_command(data.get("command", ""), folder, timeout=data.get("timeout", 120),
                              output_limit=data.get("output_limit", 64000), on_output=push,
                              should_cancel=cancelled, env=env)
            res_exit, res_out = res.exit_code, res.output
            if res.cancelled:
                status = "cancelled"
            elif res.timed_out or res.launch_error:
                status = "error"
            else:
                rule = data.get("pass_rule") or {"kind": "exit_code", "value": 0}
                status = "pass" if self._passes(rule, res.exit_code, res.output) else "fail"
            if data.get("type") == "ai_judged" and status == "pass":
                status = "pass"  # recorded, but never releases a gate (see _released)
        with self._tx() as c:
            c.execute("UPDATE executions SET status=?, exit_code=?, output=?, ended_at=? WHERE pk=?",
                      (status, res_exit, res_out, self.clock(), e["pk"]))
            self._touch_project(c, t["project_pk"])
        return self.execution(project, test_rid, n)

    @staticmethod
    def _passes(rule: dict, exit_code, output: str) -> bool:
        kind = rule.get("kind", "exit_code")
        if kind == "exit_code":
            return exit_code == int(rule.get("value", 0))
        if kind == "output_contains":
            return exit_code == 0 and str(rule.get("value", "")) in (output or "")
        return False

    def run_test(self, project: str, test_rid: str, carried_by: str = "engine", run_pk=None, attempt=None,
                 env=None) -> dict:
        n = self.begin_execution(project, test_rid, carried_by, run_pk, attempt)
        return self.perform_execution(project, test_rid, n, env=env)

    def cancel_execution(self, project: str, test_rid: str, n: int) -> None:
        t = self._rung_row(project, test_rid)
        with self._tx() as c:
            c.execute("UPDATE executions SET status='cancelled', ended_at=? WHERE test_pk=? AND n=? AND status='running'",
                      (self.clock(), t["pk"], n))

    def record_manual(self, project: str, test_rid: str, result: str, note: str, actor: Actor = HUMAN) -> dict:
        """A human records a manual result. A pass waits for a human approval before it counts."""
        if not actor.is_human:
            raise RungError("only a human records a manual test", code="forbidden", status=403)
        if result not in ("pass", "fail"):
            raise RungError("result is pass or fail", code="bad_request", status=400)
        t = self._rung_row(project, test_rid)
        if _l(t["data"], {}).get("type") != "manual":
            raise RungError(f"{test_rid} is not a manual test", code="bad_request", status=400)
        now = self.clock()
        with self._tx() as c:
            n = c.execute("SELECT COALESCE(MAX(n),0)+1 FROM executions WHERE test_pk=?", (t["pk"],)).fetchone()[0]
            seq = self._next_seq(c)
            c.execute("INSERT INTO executions(test_pk, n, seq, kind, status, carried_by, context, note, recorder, "
                      "started_at, ended_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                      (t["pk"], n, seq, "manual", "fail" if result == "fail" else "pending", actor.name,
                       "manual", (note or "").strip(), actor.name, now, now))
            self._touch_project(c, t["project_pk"])
        return self.execution(project, test_rid, n)

    def approve_result(self, project: str, test_rid: str, n: int, actor: Actor = HUMAN) -> dict:
        if not actor.is_human:
            raise RungError("only a human approves a manual result", code="forbidden", status=403)
        t = self._rung_row(project, test_rid)
        e = self._q1("SELECT * FROM executions WHERE test_pk=? AND n=?", (t["pk"], int(n)))
        if not e or e["status"] != "pending":
            raise RungError(f"#{n} of {test_rid} is not waiting for approval")
        with self._tx() as c:
            c.execute("UPDATE executions SET status='pass', approved_by=?, approved_at=? WHERE pk=?",
                      (actor.name, self.clock(), e["pk"]))
            self._touch_project(c, t["project_pk"])
        return self.execution(project, test_rid, n)

    # ------------------------------------------------------------------ release, coverage, check

    def _counting(self, test_row):
        return self._q("SELECT * FROM executions WHERE test_pk=? AND seq>? AND status IN ('pass','fail') ORDER BY n DESC",
                       (test_row["pk"], test_row["valid_from"]))

    def _test_result(self, t) -> str:
        """pass | fail | pending | running | stale | not_run (for display)."""
        if t["status"] == "stale":
            return "stale"
        running = self._q1("SELECT 1 FROM executions WHERE test_pk=? AND status='running'", (t["pk"],))
        if running:
            return "running"
        pend = self._q1("SELECT 1 FROM executions WHERE test_pk=? AND seq>? AND status='pending'", (t["pk"], t["valid_from"]))
        rows = self._counting(t)
        if rows:
            return rows[0]["status"]
        if pend:
            return "pending"
        return "not_run"

    def _released(self, spec) -> tuple[bool, list[str]]:
        blockers = []
        if spec["status"] == "stale":
            blockers.append(f"{spec['rid']} is stale")
        elif spec["status"] != "approved":
            blockers.append(f"{spec['rid']} is not approved")
        cur = self._rung_by_pk(spec["parent_pk"]) if spec["parent_pk"] else None
        while cur is not None:
            if cur["status"] == "stale":
                blockers.append(f"{cur['rid']} is stale")
            cur = self._rung_by_pk(cur["parent_pk"]) if cur["parent_pk"] else None
        tests = [t for t in self._children_rows(spec["pk"]) if t["status"] in ("approved", "stale")]
        passing = 0
        if not tests:
            blockers.append(f"{spec['rid']} has no accepted tests")
        for t in tests:
            ttype = _l(t["data"], {}).get("type", "command")
            if t["status"] == "stale":
                blockers.append(f"{t['rid']} is stale")
                continue
            rows = self._counting(t)
            latest = rows[0]["status"] if rows else None
            if ttype == "command":
                if latest == "pass":
                    passing += 1
                elif latest == "fail":
                    blockers.append(f"{t['rid']} failed (#{rows[0]['n']})")
                else:
                    blockers.append(f"{t['rid']} has not passed since the last upstream change")
            elif ttype == "manual":
                if latest == "pass":
                    passing += 1
                elif latest == "fail":
                    blockers.append(f"{t['rid']} failed (#{rows[0]['n']})")
            elif ttype == "ai_judged":
                if latest == "fail":
                    blockers.append(f"{t['rid']} failed (#{rows[0]['n']}), AI judged")
        if tests and passing == 0 and not any("has not passed" in b or "failed" in b for b in blockers):
            blockers.append(f"{spec['rid']} has no passing test that can release it")
        return (not blockers), blockers

    def check(self, project: str, rid: str) -> dict:
        """The goal gate. Pure engine computation; never calls a model."""
        r = self._rung_row(project, rid)
        if r["kind"] != "specification":
            raise RungError(f"{rid} is not a specification", code="bad_request", status=400)
        ok, blockers = self._released(r)
        return {"id": rid, "ok": ok, "blockers": blockers}

    def check_all(self, project: str) -> dict:
        p = self._project_row(project)
        specs = self._q("SELECT * FROM rungs WHERE project_pk=? AND kind='specification' AND status IN ('approved','stale') "
                        "ORDER BY rid", (p["pk"],))
        results = []
        for s in specs:
            ok, blockers = self._released(s)
            results.append({"id": s["rid"], "ok": ok, "blockers": blockers})
        return {"ok": bool(results) and all(x["ok"] for x in results), "results": results,
                "blockers": [b for x in results for b in x["blockers"]] or ([] if results else ["no approved specifications"])}

    def _req_coverage(self, req) -> str:
        """covered | stale | failing | draft | open"""
        if req["status"] == "stale":
            return "stale"
        if req["status"] in ("draft", "proposed"):
            return "draft"
        specs = [s for s in self._children_rows(req["pk"]) if s["status"] in ("approved", "stale")]
        if any(s["status"] == "stale" for s in specs):
            return "stale"
        if not specs:
            return "open"
        results = [self._released(s) for s in specs]
        if all(ok for ok, _ in results):
            return "covered"
        if any(any("failed" in b for b in bl) for _, bl in results):
            return "failing"
        return "open"

    def coverage(self, project: str, rid: str) -> str:
        return self._req_coverage(self._rung_row(project, rid))

    def _carried_by(self, spec) -> str | None:
        r = self._q1("SELECT profile FROM runs WHERE spec_pk=? ORDER BY pk DESC LIMIT 1", (spec["pk"],))
        if r:
            return r["profile"]
        pick = self._q1("SELECT profile FROM picks WHERE spec_pk=? ORDER BY pk DESC LIMIT 1", (spec["pk"],))
        return pick["profile"] if pick else None

    # ------------------------------------------------------------------ tiles, needs you, home

    def needs_you(self, project: str) -> list[dict]:
        p = self._project_row(project)
        items = []
        stale = self._q("SELECT * FROM rungs WHERE project_pk=? AND status='stale' ORDER BY kind, num", (p["pk"],))
        stale_pks = {r["pk"] for r in stale}
        order = {k: i for i, k in enumerate(KINDS)}
        for r in sorted(stale, key=lambda r: (order[r["kind"]], r["rid"])):
            if r["parent_pk"] in stale_pks:
                continue
            ch = self.change_for(project, r["rid"])
            items.append({"type": "stale", "id": r["rid"], "kind": r["kind"], "text": r["text"],
                          "parent": self._rid_of(r["parent_pk"]), "change": ch})
        for r in self._q("SELECT * FROM rungs WHERE project_pk=? AND status='proposed' ORDER BY pk", (p["pk"],)):
            items.append({"type": "proposed", "id": r["rid"], "kind": r["kind"], "text": r["text"],
                          "parent": self._rid_of(r["parent_pk"]), "proposer": r["proposer"],
                          "source_chat": r["source_chat"]})
        for e in self._q("SELECT e.*, r.rid AS trid FROM executions e JOIN rungs r ON r.pk = e.test_pk "
                         "WHERE r.project_pk=? AND e.status='pending' AND e.seq > r.valid_from ORDER BY e.pk", (p["pk"],)):
            items.append({"type": "approval", "id": e["trid"], "kind": "test", "n": e["n"],
                          "text": f"{e['trid']} #{e['n']} recorded pass", "recorder": e["recorder"], "note": e["note"]})
        return items

    def tiles(self, project: str) -> dict:
        p = self._project_row(project)
        reqs = self._q("SELECT * FROM rungs WHERE project_pk=? AND kind='requirement' AND status IN ('draft','approved','stale')",
                       (p["pk"],))
        covered = sum(1 for r in reqs if self._req_coverage(r) == "covered")
        stale = self._q1("SELECT COUNT(*) FROM rungs WHERE project_pk=? AND status='stale'", (p["pk"],))[0]
        failing = 0
        for t in self._q("SELECT * FROM rungs WHERE project_pk=? AND kind='test' AND status IN ('approved','stale')", (p["pk"],)):
            if t["status"] == "approved":
                rows = self._counting(t)
                if rows and rows[0]["status"] == "fail":
                    failing += 1
        running = self._q1("SELECT COUNT(*) FROM runs WHERE project_pk=? AND status IN ('queued','running')", (p["pk"],))[0]
        running += self._q1("SELECT COUNT(*) FROM executions e JOIN rungs r ON r.pk=e.test_pk WHERE r.project_pk=? "
                            "AND e.status='running' AND e.run_pk IS NULL", (p["pk"],))[0]
        return {"covered": covered, "requirements": len(reqs), "stale": stale, "failing": failing,
                "needs_you": len(self.needs_you(project)), "running": running, "last_activity": p["last_activity"]}

    def home(self, project: str) -> dict:
        p = self._project_row(project)
        running = [self._run_dict(r) for r in self._q(
            "SELECT * FROM runs WHERE project_pk=? AND status IN ('queued','running') ORDER BY pk", (p["pk"],))]
        live_execs = []
        for e in self._q("SELECT e.*, r.rid AS trid FROM executions e JOIN rungs r ON r.pk=e.test_pk WHERE r.project_pk=? "
                         "AND e.status='running' AND e.run_pk IS NULL ORDER BY e.pk", (p["pk"],)):
            live_execs.append({"test": e["trid"], "n": e["n"], "started_at": e["started_at"]})
        done, draft = [], []
        for s in self._q("SELECT * FROM rungs WHERE project_pk=? AND kind='specification' ORDER BY num, rid", (p["pk"],)):
            if s["status"] == "approved":
                ok, _ = self._released(s)
                if ok:
                    tests = [{"id": t["rid"], "result": self._test_result(t)} for t in self._children_rows(s["pk"])]
                    done.append({"id": s["rid"], "text": s["text"], "tests": tests})
            elif s["status"] == "draft":
                draft.append({"id": s["rid"], "text": s["text"], "kind": "specification",
                              "parent": self._rid_of(s["parent_pk"])})
        for r in self._q("SELECT * FROM rungs WHERE project_pk=? AND kind='requirement' AND status='draft' ORDER BY num", (p["pk"],)):
            specs = [s["rid"] for s in self._children_rows(r["pk"])]
            draft.append({"id": r["rid"], "text": r["text"], "kind": "requirement", "specs": specs,
                          "parent": self._rid_of(r["parent_pk"])})
        needs = [{"id": n["rid"], "text": n["text"], "status": n["status"]} for n in self._q(
            "SELECT * FROM rungs WHERE project_pk=? AND kind='need' ORDER BY num", (p["pk"],))]
        return {"project": self.project(project), "tiles": self.tiles(project), "needs_you": self.needs_you(project),
                "running": running, "running_tests": live_execs, "done": done, "draft": draft, "needs": needs}

    # ------------------------------------------------------------------ allocation and picks

    def _profile_facts(self, name: str) -> allocation.ProfileFacts:
        prof = self.profile(name)
        running = self._q1("SELECT COUNT(*) FROM runs WHERE profile=? AND status IN ('queued','running')", (name,))[0]
        total = self._q1("SELECT COUNT(*) FROM executions WHERE carried_by=? AND kind='command' AND status IN "
                         "('pass','fail','error')", (name,))[0]
        completed = self._q1("SELECT COUNT(*) FROM executions WHERE carried_by=? AND kind='command' AND status IN "
                             "('pass','fail')", (name,))[0]
        return allocation.ProfileFacts(name=name, labels=tuple(prof["labels"]), cost=prof["cost"],
                                       enabled=prof["enabled"], running=running, completed=completed, total=total)

    def suggest(self, project: str, spec_rid: str) -> dict:
        s = self._rung_row(project, spec_rid)
        if s["kind"] != "specification":
            raise RungError(f"{spec_rid} is not a specification", code="bad_request", status=400)
        p = self._project_row(s["project_pk"])
        data = _l(s["data"], {})
        tests = [t for t in self._children_rows(s["pk"]) if t["status"] in ("approved", "stale", "draft")]
        human_only = bool(tests) and all(_l(t["data"], {}).get("type") == "manual" for t in tests)
        names = [n for n in _l(p["profiles"], []) if self._q1("SELECT 1 FROM profiles WHERE name=?", (n,))]
        facts = [self._profile_facts(n) for n in names]
        ranked = [] if human_only else allocation.rank(facts, data.get("tags", []), data.get("required_tags", []))
        pick = self._q1("SELECT * FROM picks WHERE spec_pk=? ORDER BY pk DESC LIMIT 1", (s["pk"],))
        excluded = []
        for f in facts:
            ok, why = allocation.eligible(f, data.get("required_tags", []))
            if not ok:
                excluded.append({"profile": f.name, "reason": why})
        return {"spec": spec_rid, "human_only": human_only, "suggestions": [x.as_dict() for x in ranked],
                "excluded": excluded,
                "pick": {"profile": pick["profile"], "picked_by": pick["picked_by"], "at": pick["at"]} if pick else None,
                "tests": {"command": sum(1 for t in tests if _l(t["data"], {}).get("type") == "command"),
                          "manual": sum(1 for t in tests if _l(t["data"], {}).get("type") == "manual"),
                          "ai_judged": sum(1 for t in tests if _l(t["data"], {}).get("type") == "ai_judged")}}

    def pick(self, project: str, spec_rid: str, profile: str, actor: Actor = HUMAN) -> dict:
        if not actor.is_human:
            raise RungError("only a human picks a carrier", code="forbidden", status=403)
        s = self._rung_row(project, spec_rid)
        sug = self.suggest(project, spec_rid)
        if profile not in [x["profile"] for x in sug["suggestions"]]:
            raise RungError(f"{profile} is not eligible for {spec_rid}")
        with self._tx() as c:
            c.execute("INSERT INTO picks(spec_pk, profile, picked_by, at) VALUES (?,?,?,?)",
                      (s["pk"], profile, actor.name, self.clock()))
        return self.suggest(project, spec_rid)

    # ------------------------------------------------------------------ develop runs

    def start_run(self, project: str, spec_rid: str, actor: Actor = HUMAN, profile: str | None = None) -> dict:
        """Create a develop run for a specification. The caller launches the runner process."""
        s = self._rung_row(project, spec_rid)
        if s["kind"] != "specification":
            raise RungError(f"{spec_rid} is not a specification", code="bad_request", status=400)
        if s["status"] not in ("approved",):
            raise RungError(f"{spec_rid} is {s['status']}; approve it first", code="locked")
        self._require_develop(project, s)
        if self._q1("SELECT 1 FROM runs WHERE spec_pk=? AND status IN ('queued','running')", (s["pk"],)):
            raise RungError(f"{spec_rid} is already running", code="conflict")
        cmd_tests = [t for t in self._children_rows(s["pk"]) if t["status"] == "approved" and
                     _l(t["data"], {}).get("type") == "command"]
        if not cmd_tests:
            raise RungError(f"{spec_rid} has no accepted command test to develop against", code="locked")
        sug = self.suggest(project, spec_rid)
        picked_by = "suggestion"
        if profile:
            if profile not in [x["profile"] for x in sug["suggestions"]]:
                raise RungError(f"{profile} is not eligible for {spec_rid}")
            if actor.is_human and (not sug["pick"] or sug["pick"]["profile"] != profile):
                self.pick(project, spec_rid, profile, actor)
            picked_by = actor.name
        elif sug["pick"] and sug["pick"]["profile"] in [x["profile"] for x in sug["suggestions"]]:
            profile = sug["pick"]["profile"]
            picked_by = sug["pick"]["picked_by"]
        elif sug["suggestions"]:
            profile = sug["suggestions"][0]["profile"]
        else:
            raise RungError(f"no eligible profile for {spec_rid}", code="locked")
        prof = self.profile(profile)
        worker = self.get_setting("worker")
        timeout_s = int(self.get_setting("run_timeout_min")) * 60
        with self._tx() as c:
            cur = c.execute("INSERT INTO runs(project_pk, spec_pk, profile, picked_by, status, max_attempts, timeout_s, "
                            "worker, created_at) VALUES (?,?,?,?,?,?,?,?,?)",
                            (s["project_pk"], s["pk"], profile, picked_by, "queued", int(prof["max_runs"]), timeout_s,
                             _j(worker), self.clock()))
            self._touch_project(c, s["project_pk"])
        return self.run(cur.lastrowid)

    def _require_develop(self, project: str, s) -> None:
        """Develop opens once the need's Tests step was approved, and only for a fully accepted spec."""
        need = self._need_of(s)
        if need is None or not _l(need["data"], {}).get("tests_approved"):
            raise RungError("the Develop step is locked", code="locked")
        req = self._rung_by_pk(s["parent_pk"])
        for r in (need, req):
            if r["status"] != "approved":
                raise RungError(f"{r['rid']} is {r['status']}", code="locked")
        tests = [t for t in self._children_rows(s["pk"]) if t["status"] != "proposed"]
        unaccepted = [t["rid"] for t in tests if t["status"] not in ("approved", "stale")]
        if unaccepted:
            raise RungError("not accepted: " + ", ".join(unaccepted), code="locked")

    def develop_available(self, project: str, spec_rid: str) -> tuple[bool, str]:
        try:
            s = self._rung_row(project, spec_rid)
            if s["status"] != "approved":
                return False, f"{spec_rid} is {s['status']}"
            self._require_develop(project, s)
        except RungError as exc:
            return False, str(exc)
        return True, ""

    def _run_dict(self, r) -> dict:
        spec = self._rung_by_pk(r["spec_pk"])
        project = self._project_row(r["project_pk"])
        attempts = []
        for a in self._q("SELECT * FROM attempts WHERE run_pk=? ORDER BY n", (r["pk"],)):
            ex = self._q("SELECT e.*, t.rid AS trid FROM executions e JOIN rungs t ON t.pk=e.test_pk "
                         "WHERE e.run_pk=? AND e.attempt=? ORDER BY e.pk", (r["pk"], a["n"]))
            attempts.append({
                "n": a["n"], "status": a["status"], "files_changed": _l(a["files_changed"], []),
                "commands": _l(a["commands"], []), "worker_output": a["worker_output"], "fed_in": a["fed_in"],
                "fed_forward": a["fed_forward"], "started_at": a["started_at"], "ended_at": a["ended_at"],
                "executions": [{"test": e["trid"], "n": e["n"], "status": e["status"], "exit_code": e["exit_code"],
                                "output": e["output"], "command": e["command"],
                                "duration": (e["ended_at"] - e["started_at"]) if e["ended_at"] else None}
                               for e in ex],
            })
        return {"id": r["pk"], "project": project["name"], "spec": spec["rid"], "spec_text": spec["text"],
                "profile": r["profile"], "picked_by": r["picked_by"], "status": r["status"],
                "max_attempts": r["max_attempts"], "timeout_s": r["timeout_s"], "pid": r["pid"],
                "commit": r["commit_ref"], "reason": r["reason"], "created_at": r["created_at"],
                "started_at": r["started_at"], "ended_at": r["ended_at"], "attempts": attempts,
                "requirement": self._rid_of(spec["parent_pk"]),
                "coverage": self._req_coverage(self._rung_by_pk(spec["parent_pk"]))}

    def run(self, run_id: int) -> dict:
        r = self._q1("SELECT * FROM runs WHERE pk=?", (int(run_id),))
        if not r:
            raise NotFound(f"no run {run_id}")
        return self._run_dict(r)

    def runs(self, project: str, spec_rid: str | None = None) -> list[dict]:
        p = self._project_row(project)
        if spec_rid:
            s = self._rung_row(project, spec_rid)
            rows = self._q("SELECT * FROM runs WHERE spec_pk=? ORDER BY pk DESC", (s["pk"],))
        else:
            rows = self._q("SELECT * FROM runs WHERE project_pk=? ORDER BY pk DESC", (p["pk"],))
        return [self._run_dict(r) for r in rows]

    def set_run(self, run_id: int, **fields) -> None:
        allowed = {"status", "pid", "log_path", "commit_ref", "reason", "started_at", "ended_at", "cancel"}
        bad = set(fields) - allowed
        if bad:
            raise ValueError(f"cannot set {bad}")
        if not fields:
            return
        cols = ", ".join(f"{k} = ?" for k in fields)
        with self._tx() as c:
            c.execute(f"UPDATE runs SET {cols} WHERE pk = ?", (*fields.values(), int(run_id)))
            pk = c.execute("SELECT project_pk FROM runs WHERE pk=?", (int(run_id),)).fetchone()
            if pk:
                self._touch_project(c, pk[0])

    def cancel_run(self, run_id: int) -> dict:
        r = self.run(run_id)
        if r["status"] not in LIVE_RUN:
            return r
        self.set_run(run_id, cancel=1)
        if r["status"] == "queued":
            self.set_run(run_id, status="cancelled", ended_at=self.clock(), reason="cancelled before start")
        return self.run(run_id)

    def run_cancelled(self, run_id: int) -> bool:
        r = self._q1("SELECT cancel FROM runs WHERE pk=?", (int(run_id),))
        return bool(r and r["cancel"])

    def begin_attempt(self, run_id: int, n: int, prompt: str, fed_in: str) -> None:
        with self._tx() as c:
            c.execute("INSERT INTO attempts(run_pk, n, status, prompt, fed_in, started_at) VALUES (?,?,?,?,?,?)",
                      (int(run_id), n, "running", prompt, fed_in, self.clock()))

    def end_attempt(self, run_id: int, n: int, status: str, files_changed, commands, worker_output: str,
                    fed_forward: str = "") -> None:
        with self._tx() as c:
            c.execute("UPDATE attempts SET status=?, files_changed=?, commands=?, worker_output=?, fed_forward=?, "
                      "ended_at=? WHERE run_pk=? AND n=?",
                      (status, _j(files_changed), _j(commands), worker_output[-20000:], fed_forward, self.clock(),
                       int(run_id), n))

    def update_attempt(self, run_id: int, n: int, **fields) -> None:
        allowed = {"files_changed", "commands", "worker_output"}
        vals = {k: (_j(v) if k != "worker_output" else v) for k, v in fields.items() if k in allowed}
        if not vals:
            return
        cols = ", ".join(f"{k} = ?" for k in vals)
        with self._tx() as c:
            c.execute(f"UPDATE attempts SET {cols} WHERE run_pk=? AND n=?", (*vals.values(), int(run_id), n))

    def reconcile_runs(self, alive) -> list[int]:
        """Mark runs whose runner process is gone as interrupted. `alive(pid)` checks a pid."""
        out = []
        for r in self._q("SELECT * FROM runs WHERE status='running'"):
            if not r["pid"] or not alive(r["pid"]):
                self.set_run(r["pk"], status="interrupted", ended_at=self.clock(), reason="runner process ended")
                with self._tx() as c:
                    c.execute("UPDATE attempts SET status='interrupted', ended_at=? WHERE run_pk=? AND status='running'",
                              (self.clock(), r["pk"]))
                    c.execute("UPDATE executions SET status='error', ended_at=? WHERE run_pk=? AND status='running'",
                              (self.clock(), r["pk"]))
                out.append(r["pk"])
        return out

    def command_tests(self, project: str, spec_rid: str) -> list[dict]:
        s = self._rung_row(project, spec_rid)
        return [self._rung_dict(t) for t in self._children_rows(s["pk"])
                if t["status"] == "approved" and _l(t["data"], {}).get("type") == "command"]

    # ------------------------------------------------------------------ defects

    def raise_defect(self, project: str, test_rid: str, executions: list[int], title: str, note: str = "",
                     actor: Actor = HUMAN) -> dict:
        """Only ever called by a human press. Links the test, its specification and the chosen runs."""
        if not actor.is_human:
            raise RungError("defects are raised by a human", code="forbidden", status=403)
        t = self._rung_row(project, test_rid)
        if t["kind"] != "test":
            raise RungError(f"{test_rid} is not a test", code="bad_request", status=400)
        title = (title or "").strip()
        if not title:
            raise RungError("title is required", code="bad_request", status=400)
        ns = sorted({int(n) for n in executions or []})
        if not ns:
            raise RungError("link at least one execution", code="bad_request", status=400)
        for n in ns:
            if not self._q1("SELECT 1 FROM executions WHERE test_pk=? AND n=?", (t["pk"], n)):
                raise NotFound(f"no execution #{n} of {test_rid}")
        with self._tx() as c:
            k = c.execute("SELECT COUNT(*)+1 FROM defects WHERE project_pk=?", (t["project_pk"],)).fetchone()[0]
            did = f"D-{k}"
            c.execute("INSERT INTO defects(project_pk, did, title, note, test_pk, spec_pk, executions, created_by, at) "
                      "VALUES (?,?,?,?,?,?,?,?,?)", (t["project_pk"], did, title, (note or "").strip(), t["pk"],
                                                     t["parent_pk"], _j(ns), actor.name, self.clock()))
            self._touch_project(c, t["project_pk"])
        return self.defect(project, did)

    def defect(self, project: str, did: str) -> dict:
        p = self._project_row(project)
        d = self._q1("SELECT * FROM defects WHERE project_pk=? AND did=?", (p["pk"], did))
        if not d:
            raise NotFound(f"no defect {did}")
        return {"id": d["did"], "title": d["title"], "note": d["note"], "test": self._rid_of(d["test_pk"]),
                "spec": self._rid_of(d["spec_pk"]), "executions": _l(d["executions"], []),
                "created_by": d["created_by"], "at": d["at"]}

    def defects(self, project: str) -> list[dict]:
        p = self._project_row(project)
        return [self.defect(project, d["did"]) for d in self._q("SELECT did FROM defects WHERE project_pk=? ORDER BY pk",
                                                                  (p["pk"],))]
