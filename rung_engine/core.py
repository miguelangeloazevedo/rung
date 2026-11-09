"""The Rung engine: structure, links, gates, staleness, coverage, executions and allocation.

Everything here is deterministic. Model output only ever arrives as text handed in by a caller
(a drafting provider or a worker); the engine never calls a model and never asks one whether
work is done. A specification is released by its tests' executions and nothing else.
"""

from __future__ import annotations

import functools
import json
import os
import posixpath
import re
import string
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Callable
from pathlib import Path

from . import allocation, db, evidence
from .execute import context_line, git_commit, run_command
from .claims import ClaimsMixin, _canon
from .lifecycle import LifecycleMixin
from .bot import BotMixin
from .milestones import MilestonesMixin
from .quick import QuickMixin
from .system import SystemMixin

KINDS = ("need", "requirement", "specification", "test")
CHILD_KIND = {"need": "requirement", "requirement": "specification", "specification": "test"}
PARENT_KIND = {v: k for k, v in CHILD_KIND.items()}
TEST_TYPES = ("command", "manual", "ai_judged")
QUEUED_GRACE_S = 30  # a runner marks its run running within seconds of being started
# A change to any of these makes a test a different test: its earlier results stop counting.
TEST_SEMANTIC = ("type", "command", "folder", "pass_rule", "steps")


def _is_int(v) -> bool:
    return isinstance(v, int) and not isinstance(v, bool) or isinstance(v, str) and v.strip().lstrip("-").isdigit()
DEFECT_CATEGORIES = ("Implementation", "Specification", "Requirement", "Test")
GATING_TYPES = ("command", "manual")
FINAL_EXEC = ("pass", "fail")
LIVE_RUN = ("queued", "running")
# pass and fail come from the tests; the others are what the worker or the runner reported, shown as such.
ATTEMPT_OUTCOMES = ("pass", "fail", "needs_input", "no_change", "unknown", "partial", "error", "cancelled")
STEPS = ("need", "requirements", "specifications", "tests", "develop")

DEFAULT_SETTINGS = {
    "last_project": None,
    "drafting": {"kind": "stub", "profile": "", "stub_file": "", "delay": 1.0},
    "worker": {"kind": "hermes", "stub_dir": "", "max_turns": 30},
    "test_timeout": 120,
    "output_limit": 64000,
    "run_timeout_min": 20,
    "colours": {"needs_you": "theme", "pass": "theme", "fail": "theme", "stale": "theme", "draft": "theme"},
    "onboarding": {"start_dismissed": False, "checklist_hidden": False},
}


def detect_test_command(folder: Path) -> str:
    """A best guess from the files in the folder; the form shows it and the person can change it."""
    has = lambda *names: any((folder / n).exists() for n in names)  # noqa: E731
    if has("pytest.ini", "conftest.py", "tox.ini") or (has("pyproject.toml", "setup.py", "setup.cfg") and has("tests")):
        return "pytest"
    if has("package.json"):
        return "npm test"
    if has("Cargo.toml"):
        return "cargo test"
    if has("go.mod"):
        return "go test ./..."
    if has("Makefile"):
        return "make test"
    if has("tests", "test"):
        return "python3 -m unittest -q"
    return ""


def writes(rid: bool = True):
    """Mark an Engine method that changes a project. Archived projects and retired needs are read only;
    every write from the pane, the CLI and the agent tools passes through here."""
    def deco(fn):
        @functools.wraps(fn)
        def wrapper(self, project, *args, **kwargs):
            # One write at a time per engine: what a write reads and checks is still true when it commits.
            with self._lock:
                self._check_writable(project, args[0] if rid and args and isinstance(args[0], str) else None)
                return fn(self, project, *args, **kwargs)
        wrapper.writes = True
        return wrapper
    return deco


class RungError(ValueError):
    """A refused operation. `code` is stable for the API layer."""

    def __init__(self, message: str, code: str = "refused", status: int = 409, field: str | None = None,
                 fields: dict | None = None):
        super().__init__(message)
        self.code = code
        self.status = status
        self.field = field
        self.fields = fields  # every field a refused form names, field -> message


class FieldErrors:
    """Collects each field's refusal so a form is told about every field at once, not the first only."""

    def __init__(self):
        self.errors: dict[str, str] = {}
        self.first: RungError | None = None  # its status and code answer for the form (a taken name stays 409)

    def check(self, fn, *args):
        try:
            return fn(*args)
        except RungError as exc:
            if not exc.field:
                raise
            self.errors.setdefault(exc.field, str(exc))
            self.first = self.first or exc
            return None

    def raise_any(self):
        if self.errors:
            field, message = next(iter(self.errors.items()))
            code, status = (self.first.code, self.first.status) if self.first and self.first.field == field \
                else ("bad_request", 400)
            raise RungError(message, code=code, status=status, field=field, fields=dict(self.errors))


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


NAME_RX = re.compile(r"^[A-Za-z0-9_.:-]{1,64}$")


def _int_field(value, field: str, lo: int, hi: int) -> int:
    """A whole number from lo to hi; text, decimals and true/false are refused on that field."""
    if isinstance(value, bool) or not isinstance(value, int) or not lo <= value <= hi:
        raise RungError(f"{field.replace('_', ' ')} must be {lo} to {hi}", code="bad_request", status=400, field=field)
    return value


# The settings a person changes, with their ranges. Other keys (drafting, worker, onboarding, colours,
# last_project) keep their own shape: an object, or a project name.
_SETTING_RANGES = {"test_timeout": (1, 86400), "output_limit": (1000, 50_000_000), "run_timeout_min": (1, 1440)}


def _setting_value(key, value):
    if key not in DEFAULT_SETTINGS:
        raise RungError(f"unknown setting {key}", code="bad_request", status=400, field=str(key))
    if key in _SETTING_RANGES:
        return _int_field(value, key, *_SETTING_RANGES[key])
    if key == "last_project":
        if value is not None and not isinstance(value, str):
            raise RungError("last project is a project name", code="bad_request", status=400, field=key)
        return value
    if not isinstance(value, dict):
        raise RungError(f"{key} is an object", code="bad_request", status=400, field=key)
    if key == "colours":
        for k, v in value.items():
            if k not in DEFAULT_SETTINGS["colours"]:
                raise RungError(f"no colour {k}", code="bad_request", status=400, field="colours")
            if not (v == "theme" or (isinstance(v, str) and re.fullmatch(r"#[0-9a-fA-F]{6}", v))):
                raise RungError(f"{k} is theme or a #rrggbb colour", code="bad_request", status=400, field="colours")
        return {**DEFAULT_SETTINGS["colours"], **value}
    return value


def _text_field(value, field: str) -> str:
    """A form's text field, trimmed. Not sent is empty; anything but text is refused on that field."""
    if value is None:
        return ""
    if not isinstance(value, str):
        raise RungError(f"{field.replace('_', ' ')} is text", code="bad_request", status=400, field=field)
    return value.strip()


def _profile_list(values) -> list[str]:
    """The profiles ticked on a form: a list of names, without duplicates or blanks."""
    if not isinstance(values, list) or not all(isinstance(v, str) for v in values):
        raise RungError("profiles is a list of profile names", code="bad_request", status=400, field="profiles")
    return [v for v in dict.fromkeys(x.strip() for x in values) if v]


def _clean_names(values, what: str, field: str | None = None) -> list[str]:
    """Toolset names: text, trimmed, no duplicates, letters digits and _ . : - only."""
    out = []
    for v in values:
        if not isinstance(v, str):
            raise RungError(f"a {what} name is text", code="bad_request", status=400, field=field or what + "s")
        v = v.strip()
        if not v:
            continue
        if not NAME_RX.match(v):
            raise RungError(f"{v[:40]!r} is not a {what} name", code="bad_request", status=400,
                            field=field or what + "s")
        if v.lower() not in {x.lower() for x in out}:
            out.append(v)
    return out


def _letter(k: int) -> str:
    letters = string.ascii_lowercase
    return letters[k - 1] if 1 <= k <= 26 else f"z{k}"


class Engine(LifecycleMixin, ClaimsMixin, BotMixin, MilestonesMixin, QuickMixin, SystemMixin):
    # A callable profile name -> list of Hermes toolset names, or None. Set by the host so a profile's
    # tools are pre-filled from its Hermes configuration the first time Rung lists it.
    tool_source: "Callable[[str], list[str] | None] | None" = None

    def __init__(self, path: str | Path, clock=time.time, readonly: bool = False):
        self.path = str(path)
        self.readonly = readonly
        self.conn = db.connect_readonly(path) if readonly else db.connect(path)
        self.clock = clock
        self._lock = threading.RLock()

    def close(self):
        with self._lock:
            try:
                self.conn.close()
            except Exception:
                pass

    # ------------------------------------------------------------------ plumbing

    @contextmanager
    def _tx(self):
        """One write transaction. Re-entrant on the same thread: a write made inside another one (pick
        inside start_run) joins it, and commits or rolls back with it."""
        with self._lock:
            if getattr(self, "_tx_depth", 0):
                self._tx_depth += 1
                try:
                    yield self.conn
                finally:
                    self._tx_depth -= 1
                return
            self.conn.execute("BEGIN IMMEDIATE")
            self._tx_depth = 1
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
            finally:
                self._tx_depth = 0

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
        value = _setting_value(key, value)
        with self._tx() as c:
            c.execute("INSERT OR REPLACE INTO settings(key, value) VALUES (?, ?)", (key, _j(value)))

    # ------------------------------------------------------------------ profiles

    def sync_profiles(self, names) -> None:
        """Make sure every Hermes profile has a Rung row. Existing rows are left alone; a new row's tools
        are pre-filled from the profile's Hermes toolsets."""
        new = [n for n in names if not self._q1("SELECT 1 FROM profiles WHERE name=?", (n,))]
        tools = {n: self._source_tools(n) for n in new}
        with self._tx() as c:
            for n in new:
                c.execute("INSERT OR IGNORE INTO profiles(name, tools) VALUES (?, ?)", (n, _j(tools[n])))

    def _source_tools(self, name: str) -> list[str]:
        src = self.tool_source
        if src is None:
            return []
        try:
            got = src(name)
        except Exception:
            return []
        return _clean_names(got or [], "tool") if isinstance(got, (list, tuple, set)) else []

    def fill_profile_tools(self, name: str, tools) -> bool:
        """Pre-fill a profile's tools that Hermes resolved late; a row that already has tools keeps them."""
        clean = _clean_names(list(tools or []), "tool")
        if not clean:
            return False
        with self._tx() as c:
            return c.execute("UPDATE profiles SET tools = ? WHERE name = ? AND tools = ?",
                             (_j(clean), name, _j([]))).rowcount > 0

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
                "max_runs": r["max_runs"], "enabled": bool(r["enabled"]), "tools": _l(r["tools"], []),
                "at_once": r["at_once"]}

    def save_profiles(self, rows: list[dict]) -> None:
        """Save several profiles at once. A field a row leaves out keeps the profile's current value."""
        clean = self._clean_profiles(rows)
        with self._tx() as c:
            self._write_profiles(c, clean)

    def save_settings(self, settings: dict | None, profiles: list[dict] | None = None) -> None:
        """The settings Save button: every value is checked first, then all of it is saved in one
        transaction, so a refused field saves nothing."""
        if settings is not None and not isinstance(settings, dict):
            raise RungError("settings is an object", code="bad_request", status=400, field="settings")
        values = {k: _setting_value(k, v) for k, v in (settings or {}).items()}
        clean = self._clean_profiles(profiles) if profiles is not None else []
        with self._tx() as c:
            for k, v in values.items():
                c.execute("INSERT OR REPLACE INTO settings(key, value) VALUES (?, ?)", (k, _j(v)))
            self._write_profiles(c, clean)

    def _clean_profiles(self, rows) -> list[tuple]:
        if not isinstance(rows, list) or not all(isinstance(r, dict) for r in rows):
            raise RungError("profiles is a list of profiles", code="bad_request", status=400, field="profiles")
        clean, seen = [], set()
        for row in rows:
            name = row.get("name")
            if not isinstance(name, str) or not name.strip():
                raise RungError("profile name missing", code="bad_request", status=400, field="name")
            name = name.strip()
            if name in seen:
                raise RungError(f"{name} is listed twice", code="bad_request", status=400, field="profiles")
            seen.add(name)
            try:
                clean.append(self._clean_profile(name, row))
            except RungError as exc:
                exc.args = (f"{name}: {exc}",)  # Settings shows one line: say which row
                raise
        return clean

    def _clean_profile(self, name: str, row: dict) -> tuple:
        old = self._q1("SELECT * FROM profiles WHERE name=?", (name,))
        od = self._profile_dict(old) if old else {"labels": [], "cost": 5, "max_runs": 5, "enabled": True,
                                                   "at_once": 2}
        labels = row.get("labels", od["labels"])
        if not isinstance(labels, list) or not all(isinstance(x, str) for x in labels):
            raise RungError("labels is a list of text", code="bad_request", status=400, field="labels")
        labels = list(dict.fromkeys(x.strip() for x in labels if x.strip()))
        cost = _int_field(row.get("cost", od["cost"]), "cost", 0, 10)
        max_runs = _int_field(row.get("max_runs", od["max_runs"]), "max_runs", 1, 50)
        at_once = _int_field(row.get("at_once", od["at_once"]), "at_once", 1, 10)
        enabled = row.get("enabled", od["enabled"])
        if not isinstance(enabled, bool):
            raise RungError("enabled is true or false", code="bad_request", status=400, field="enabled")
        if "tools" in row:
            if not isinstance(row["tools"], list):
                raise RungError("tools is a list of toolset names", code="bad_request", status=400, field="tools")
            tools = _clean_names(row["tools"], "tool")
        else:  # not sent: keep what the profile has, or pre-fill a new one from Hermes
            tools = _l(old["tools"], []) if old else self._source_tools(name)
        return (name, _j(labels), cost, max_runs, 1 if enabled else 0, _j(tools), at_once)

    @staticmethod
    def _write_profiles(c, clean: list[tuple]) -> None:
        for row in clean:
            c.execute(
                "INSERT INTO profiles(name, labels, cost, max_runs, enabled, tools, at_once) VALUES (?,?,?,?,?,?,?) "
                "ON CONFLICT(name) DO UPDATE SET labels=excluded.labels, cost=excluded.cost, "
                "max_runs=excluded.max_runs, enabled=excluded.enabled, tools=excluded.tools, "
                "at_once=excluded.at_once",
                row,
            )

    # ------------------------------------------------------------------ projects

    def create_project(self, name: str = "", folder: str = "", test_command: str = "",
                       profiles: list[str] | None = None) -> dict:
        """Only the folder is required. Name, test command and profiles default from it (project_defaults)
        and every value stays the caller's to change. Errors name the field they belong to."""
        name, folder, test_command = (_text_field(v, f) for v, f in
                                      ((name, "name"), (folder, "folder"), (test_command, "test_command")))
        errs = FieldErrors()
        errs.check(self._check_folder, folder)
        folder = str(Path(folder).expanduser())  # stored as the folder tests run in
        defaults = self.project_defaults(folder)
        name = name or defaults["name"]
        test_command = test_command or defaults["test_command"]
        # Not sent: the enabled profiles. Sent: exactly what was ticked, so an empty list is refused.
        profiles = defaults["profiles"] if profiles is None else errs.check(_profile_list, profiles)
        errs.check(self._check_name, name)
        # The test command is optional: detected when the folder shows one, else left for the person to add later.
        if profiles is not None and not profiles:
            errs.errors.setdefault("profiles", "tick at least one profile")
        errs.raise_any()
        now = self.clock()
        with self._tx() as c:
            for p in profiles:
                c.execute("INSERT OR IGNORE INTO profiles(name) VALUES (?)", (p,))
            c.execute(
                "INSERT INTO projects(name, folder, test_command, profiles, created_at, last_activity) "
                "VALUES (?,?,?,?,?,?)", (name, folder, test_command, _j(profiles), now, now),
            )
            c.execute("INSERT OR REPLACE INTO settings(key, value) VALUES ('last_project', ?)", (_j(name),))
        return self.project(name)

    def project_defaults(self, folder: str) -> dict:
        """What the new project form pre-fills for a folder: its name, a detected test command, enabled profiles."""
        path = Path((folder or "").strip()).expanduser()
        name = path.name if (folder or "").strip() else ""
        return {"name": name, "test_command": detect_test_command(path) if path.is_dir() else "",
                "profiles": [p["name"] for p in self.profiles() if p["enabled"]]}

    @staticmethod
    def _check_folder(folder: str) -> None:
        if not folder:
            raise RungError("folder is required", code="bad_request", status=400, field="folder")
        path = Path(folder).expanduser()
        if not path.exists():
            raise RungError(f"folder not found: {folder}", code="bad_request", status=400, field="folder")
        if not path.is_dir():
            raise RungError(f"not a folder: {folder}", code="bad_request", status=400, field="folder")
        if not os.access(path, os.R_OK | os.X_OK):
            raise RungError(f"folder not readable: {folder}", code="bad_request", status=400, field="folder")

    def _check_name(self, name: str, current_pk: int | None = None) -> None:
        if not name:
            raise RungError("name is required", code="bad_request", status=400, field="name")
        if len(name) > 80 or any(ch in name for ch in "/#?%") or name.strip() != name or \
                any(ord(ch) < 32 for ch in name) or name in (".", ".."):
            raise RungError("a name is up to 80 characters, without / # ? or %", code="bad_request", status=400,
                            field="name")
        # Names differing only in case read as one in the picker: refuse them as a duplicate too.
        row = self._q1("SELECT pk, name FROM projects WHERE name = ? COLLATE NOCASE AND pk IS NOT ?", (name, current_pk))
        if row:
            raise RungError(f"a project named {row['name']} exists", code="conflict", field="name")

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
                "last_activity": r["last_activity"], "archived": r["archived_at"] is not None,
                "archived_at": r["archived_at"], "sample": self._is_sample(r),
                "run_mode": (r["run_mode"] if "run_mode" in r.keys() else "shared") or "shared"}

    def projects(self, archived: bool = False) -> list[dict]:
        """The picker: active projects, or with `archived` the archived ones."""
        out = []
        for r in self._q(f"SELECT name FROM projects WHERE archived_at IS {'NOT ' if archived else ''}NULL "
                         "ORDER BY last_activity DESC, name"):
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
        r = self._q1("SELECT name FROM projects WHERE archived_at IS NULL ORDER BY last_activity DESC LIMIT 1")
        return r["name"] if r else None

    # ------------------------------------------------------------------ rung access

    def _rung_row(self, project: str, rid: str):
        p = self._project_row(project)
        if isinstance(rid, str):
            from .claims import canonical_rid
            rid = canonical_rid(rid)  # every door reads s-2.1, ' S 2.1 ' or S\u20112.1 as S-2.1
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
        if r["kind"] == "test" and data.get("type") == "manual":
            d["required"] = self._required(data)  # what the evaluator reads, also for a test stored without the key
        return d

    def tree(self, project: str, retired: bool = False) -> list[dict]:
        """The whole ladder, nested, without dismissed rungs. `retired` lists the retired needs instead."""
        p = self._project_row(project)

        def build(row):
            d = self._rung_dict(row)
            kids = self._children_rows(row["pk"])
            d["children"] = [build(k) for k in kids if k["status"] != "proposed"]
            if row["kind"] == "requirement":
                d["coverage"] = "out_of_scope" if d.get("out_of_scope") else self._req_coverage(row)
            if row["kind"] == "specification":
                v = self._verify(row)
                d["released"] = v["ok"]
                d["blockers"] = [b["text"] for b in v["blockers"]]
                d["verification"] = v["verification"]
                d["codes"] = [b["code"] for b in v["blockers"]]
                d["next_action"] = v["next_action"]
                d["carried_by"] = self._carried_by(row)
            if row["kind"] == "test":
                d["result"] = self._test_result(row)
                d["seen_failing"] = self._seen_failing(row)
            if row["kind"] == "need":
                d["retired"] = row["retired_at"] is not None
                d["retired_reason"] = row["retired_reason"]
                d["retired_at"] = row["retired_at"]
            return d

        needs = self._q(
            "SELECT * FROM rungs WHERE project_pk = ? AND kind = 'need' AND status NOT IN ('dismissed','proposed') "
            f"AND retired_at IS {'NOT ' if retired else ''}NULL ORDER BY num", (p["pk"],),
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

    @writes(rid=False)
    def create_need(self, project: str, text: str, actor: Actor = HUMAN,
                    requirements: list[str] | None = None, drafter: str = "drafting") -> dict:
        """A need written by a human is approved on creation (the Create need press)."""
        if not actor.is_human:
            raise RungError("agents propose needs, they cannot create them", code="forbidden", status=403)
        p = self._project_row(project)
        with self._tx() as c:
            pk = self._insert_rung(c, p["pk"], "need", None, text, "", "approved", actor)
            need = c.execute("SELECT * FROM rungs WHERE pk = ?", (pk,)).fetchone()
            for t in requirements or []:
                # Accepted suggestions are written by the profile that drafted them (an author, Round 7).
                self._insert_rung(c, p["pk"], "requirement", need, t, "", "draft", Actor("agent", drafter or "drafting"),
                                  data={"origin": "suggested", **({"drafted_by": drafter} if drafter and drafter != "drafting" else {})})
        return self._rung_dict(self._rung_by_pk(pk))

    @writes()
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

    @writes()
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

    @writes()
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

    @writes()
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

    @writes(rid=False)
    def resolve_suggestion(self, project: str, suggestion_id: int, accept: bool, actor: Actor = HUMAN) -> dict | None:
        if not actor.is_human:
            raise RungError("only a human can accept or dismiss suggestions", code="forbidden", status=403)
        p = self._project_row(project)
        s = self._q1("SELECT * FROM suggestions WHERE pk = ? AND project_pk = ?", (suggestion_id, p["pk"]))
        if not s or s["status"] != "open":
            raise NotFound(f"no open suggestion {suggestion_id}")
        made = None
        if accept and s["target"] == "edit":
            # The same path as a person's edit: a new version, a change record and staleness below.
            r = self._rung_by_pk(s["parent_pk"])
            self.edit(project, r["rid"], detail=(r["detail"] + "\n" if r["detail"] else "") + s["text"], actor=actor)
        with self._tx() as c:
            c.execute("UPDATE suggestions SET status = ? WHERE pk = ?", ("accepted" if accept else "dismissed", s["pk"]))
            if accept and s["target"] == "requirement":
                parent = c.execute("SELECT * FROM rungs WHERE pk = ?", (s["parent_pk"],)).fetchone()
                pk = self._insert_rung(c, p["pk"], "requirement", parent, s["text"], "", "draft",
                                       Actor("agent", "drafting"), data={"origin": "suggested"})
                made = pk
        return self._rung_dict(self._rung_by_pk(made)) if made else None

    # ------------------------------------------------------------------ edit, approve, staleness

    @writes()
    def edit(self, project: str, rid: str, text: str | None = None, detail: str | None = None,
             actor: Actor = HUMAN, approve: bool = False, data: dict | None = None,
             expect_version: int | None = None) -> dict:
        """Change a rung's text. If it changes after approval, everything that hangs below goes stale.
        `expect_version` is the version the editor loaded; a newer one refuses the edit (no silent overwrite)."""
        r = self._rung_row(project, rid)
        self._check_version(r, expect_version)
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
        old_data = _l(r["data"], {})
        semantic = r["kind"] == "test" and any(old_data.get(k) != new_data.get(k) for k in TEST_SEMANTIC)
        if semantic:
            self._validate_test(new_text, new_data)
        now = self.clock()
        stale_rids: list[str] = []
        with self._tx() as c:
            self._still_version(c, r)
            version = r["version"]
            if changed or data_changed:
                version += 1
                c.execute("INSERT INTO rung_versions(rung_pk, version, text, detail, data, at, by_name, by_kind) "
                          "VALUES (?,?,?,?,?,?,?,?)", (r["pk"], version, new_text, new_detail, _j(new_data), now,
                                                       actor.name, actor.kind))
            # A draft opened by a fresh draft still stands for approved text (fresh_from): changing it
            # records the change and stops old results counting, as for an approved rung.
            was_approved = (r["status"] in ("approved", "stale") and r["approved_at"] is not None) or (
                r["kind"] == "specification" and r["status"] == "draft" and old_data.get("fresh_from") is not None)
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
            if semantic and c.execute("SELECT 1 FROM executions WHERE test_pk = ?", (r["pk"],)).fetchone():
                new_data["invalidated_by"] = f"{rid} edited"
                c.execute("UPDATE rungs SET valid_from = ? WHERE pk = ?", (self._next_seq(c), r["pk"]))
            if approve:
                status, ab, at = "approved", actor.name, now
                new_data.pop("fresh_from", None)
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

    @staticmethod
    def _still_version(c, r) -> None:
        """Inside the write transaction: refuse when another process changed the rung since it was read."""
        now = c.execute("SELECT version FROM rungs WHERE pk = ?", (r["pk"],)).fetchone()
        if now is not None and now[0] != r["version"]:
            raise RungError(f"{r['rid']} changed since it was opened (version {now[0]}, edited {r['version']})",
                            code="conflict", status=409)

    @staticmethod
    def _check_version(r, expect_version) -> None:
        if expect_version is not None and int(expect_version) != r["version"]:
            raise RungError(f"{r['rid']} changed since it was opened (version {r['version']}, edited {expect_version})",
                            code="conflict", status=409)

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

    @writes()
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
            data.pop("fresh_from", None)  # approved: a fresh draft, if any, is over
            c.execute("UPDATE rungs SET status='approved', approved_by=?, approved_at=?, data=?, updated_at=? WHERE pk=?",
                      (actor.name, now, _j(data), now, r["pk"]))
            if r["kind"] == "test":
                self._baseline(c, r["pk"], data, now)
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

    @writes(rid=False)
    def revert_change(self, project: str, change_id: int, actor: Actor = HUMAN) -> dict:
        """Put a rung's text back to what it was before a change. This is a new change of its own:
        whatever went stale stays stale until a person looks at it again."""
        if not actor.is_human:
            raise RungError("agents cannot revert changes", code="forbidden", status=403)
        p = self._project_row(project)
        x = self._q1("SELECT * FROM changes WHERE pk=? AND project_pk=?", (int(change_id), p["pk"]))
        if not x:
            raise NotFound(f"no change {change_id}")
        rid = self._rid_of(x["rung_pk"])
        r = self._rung_row(project, rid)
        if (r["text"], r["detail"]) != (x["after_text"], x["after_detail"]):
            # A later change landed on top: reverting this one would silently undo that one too.
            raise RungError(f"{rid} changed again after this change; revert the later change first", code="conflict")
        # The earlier text was approved; it stays approved only if the rung still is. A rung that went stale
        # from above stays stale: its parent changed since that text was approved.
        return self.edit(project, rid, text=x["before_text"], detail=x["before_detail"], actor=actor,
                         approve=r["status"] == "approved")

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

    @writes()
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
            else:  # I write: an unwritten AI draft (failed or not) becomes the person's to write
                for s in existing:
                    sd = _l(s["data"], {})
                    if s["status"] == "draft" and not s["text"]:
                        sd.pop("draft_error", None)
                        sd.update({"draft_state": "", "author_role": "human"})
                        c.execute("UPDATE rungs SET data = ? WHERE pk = ?", (_j(sd), s["pk"]))
        return self._rung_dict(self._rung_by_pk(spec_pk)) if spec_pk else None

    def ai_derived(self, project: str, spec_rid: str) -> bool:
        """An AI-derived specification: drafted by an agent, or under a requirement in AI derives mode."""
        r = self._rung_row(project, spec_rid)
        if r["kind"] != "specification":
            return False
        if _l(r["data"], {}).get("author_role") == "agent":
            return True
        req = self._rung_by_pk(r["parent_pk"]) if r["parent_pk"] else None
        return bool(req) and _l(req["data"], {}).get("authoring") == "ai"

    @writes()
    def mark_drafting(self, project: str, spec_rid: str, actor: Actor = HUMAN) -> dict:
        """Ask the drafting provider for a new draft of an AI-derived specification (SPC-05). An open
        draft is drafted again in place; an approved one gets a new version waiting for approval, and
        its approved version stays in its history."""
        if not actor.is_human:
            raise RungError("only a human asks for a new draft", code="forbidden", status=403)
        r = self._rung_row(project, spec_rid)
        if r["kind"] != "specification" or r["status"] not in ("draft", "stale", "approved"):
            raise RungError(f"{spec_rid} is not an open draft", code="refused")
        data = _l(r["data"], {})
        if data.get("draft_state") == "drafting":
            raise RungError(f"{spec_rid} is still drafting", code="locked")
        if not self.ai_derived(project, spec_rid):
            raise RungError(f"{spec_rid} is written by you; edit it instead", code="refused")
        # An approved specification, or one gone stale since its approval: either way its approved text is
        # kept as a version and the fresh draft is compared with it.
        fresh = r["status"] == "approved" or (r["status"] == "stale" and r["approved_at"] is not None)
        data["draft_state"] = "drafting"
        data.pop("draft_error", None)
        if r["status"] != "draft":
            data.pop("fresh_from", None)  # an earlier fresh draft that was approved since is over
        with self._tx() as c:
            if fresh:
                self._still_version(c, r)
                data["fresh_from"] = r["version"]
                version = r["version"] + 1
                now = self.clock()
                c.execute("INSERT INTO rung_versions(rung_pk, version, text, detail, data, at, by_name, by_kind) "
                          "VALUES (?,?,?,?,?,?,?,?)", (r["pk"], version, r["text"], r["detail"], _j(data), now,
                                                       actor.name, actor.kind))
                c.execute("UPDATE rungs SET data=?, version=?, status='draft', approved_by=NULL, approved_at=NULL, "
                          "updated_at=? WHERE pk=?", (_j(data), version, now, r["pk"]))
            else:
                c.execute("UPDATE rungs SET data = ? WHERE pk = ?", (_j(data), r["pk"]))
            self._touch_project(c, r["project_pk"])
        return self.rung(project, spec_rid)

    def finish_draft(self, project: str, spec_rid: str, text: str, detail: str = "", tags=None,
                     required_tags=None, drafted_by: str = "drafting") -> dict:
        """A drafting provider delivers the text of an AI-derived specification."""
        r = self._rung_row(project, spec_rid)
        if r["kind"] != "specification":
            raise RungError(f"{spec_rid} is not a specification", code="bad_request", status=400)
        self._require_drafting(r)
        data = _l(r["data"], {})
        data.update({"draft_state": "drafted", "author_role": "agent", "drafted_by": drafted_by,
                     # every profile that drafted this rung stays its author, whoever drafted last
                     "drafters": list(dict.fromkeys([*data.get("drafters", []), *([data["drafted_by"]] if
                                                     data.get("drafted_by") else []), drafted_by]))})
        # Kept until the specification is approved again: a second fresh draft of the same open version
        # still counts as a change of approved text.
        fresh_from = data.get("fresh_from")
        if tags is not None:
            data["tags"] = list(tags)
        if required_tags is not None:
            data["required_tags"] = list(required_tags)
        now = self.clock()
        with self._tx() as c:
            if fresh_from is not None and (text.strip(), (detail or "").strip()) != (r["text"], r["detail"]):
                # A fresh draft of an approved specification changes approved text: what hangs below
                # goes stale and the change is recorded, as for an edit.
                seq = self._next_seq(c)
                stale_rids = self._mark_downstream_stale(c, r, seq, f"{r['rid']} redrafted")
                c.execute(
                    "INSERT INTO changes(project_pk, rung_pk, seq, before_text, after_text, before_detail, "
                    "after_detail, from_version, to_version, stale, at, by_name) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                    (r["project_pk"], r["pk"], seq, r["text"], text.strip(), r["detail"], (detail or "").strip(),
                     fresh_from, r["version"], _j(stale_rids), now, drafted_by))
            c.execute("UPDATE rungs SET text=?, detail=?, data=?, author_kind='agent', author_name=?, updated_at=? "
                      "WHERE pk=?", (text.strip(), (detail or "").strip(), _j(data), drafted_by, now, r["pk"]))
            # The version's words are the drafting profile's, whoever asked for them.
            c.execute("UPDATE rung_versions SET text=?, detail=?, data=?, by_name=?, by_kind='agent' "
                      "WHERE rung_pk=? AND version=?",
                      (text.strip(), (detail or "").strip(), _j(data), drafted_by, r["pk"], r["version"]))
            self._touch_project(c, r["project_pk"])
        return self._rung_dict(self._rung_by_pk(r["pk"]))

    def fail_draft(self, project: str, spec_rid: str, reason: str) -> None:
        r = self._rung_row(project, spec_rid)
        self._require_drafting(r)
        data = _l(r["data"], {})
        data.update({"draft_state": "failed", "draft_error": reason[:500]})
        with self._tx() as c:
            c.execute("UPDATE rungs SET data=? WHERE pk=?", (_j(data), r["pk"]))

    @staticmethod
    def _require_drafting(r) -> None:
        """A drafting result lands only on a specification that is being drafted: never over approved text."""
        if _l(r["data"], {}).get("draft_state") != "drafting":
            raise RungError(f"{r['rid']} is not being drafted", code="not_drafting", status=409)

    @writes()
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

    @writes()
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
        if t != "manual":
            rule = data.get("pass_rule")
            kind = rule.get("kind") if isinstance(rule, dict) else None
            ok = kind == "exit_code" and _is_int(rule.get("value", 0)) or \
                kind == "output_contains" and isinstance(rule.get("value"), str) and rule["value"] != ""
            if not ok:
                raise RungError("the pass rule is an exit code (a whole number) or text the output contains",
                                code="bad_request", status=400, field="pass_rule")

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
            # Required by default (Round 22): an approved manual check has to be performed and approved before
            # its specification is verified. Optional: not needed, but a recorded failure still blocks.
            # A manual test stored before Round 22 has no key: optional, and an edit keeps that unless asked.
            legacy = base is not None and base.get("type") == "manual" and "required" not in base
            d["required"] = fields.get("required", d.get("required", not legacy)) is not False
        else:
            d["command"] = (fields.get("command", d.get("command", "")) or "").strip()
            d["folder"] = (fields.get("folder", d.get("folder", ".")) or ".").strip()
            norm = posixpath.normpath(d["folder"].replace("\\", "/"))
            if posixpath.isabs(norm) or norm == ".." or norm.startswith("../") or d["folder"].startswith("~"):
                raise RungError("the folder is inside the project folder, for example . or tests",
                                code="bad_request", status=400, field="folder")
            d["folder"] = norm
            d["pass_rule"] = fields.get("pass_rule", d.get("pass_rule", {"kind": "exit_code", "value": 0}))
            d["timeout"] = int(fields.get("timeout", d.get("timeout", settings_timeout)))
            d["output_limit"] = int(fields.get("output_limit", d.get("output_limit", settings_limit)))
            d.pop("steps", None)
            d.pop("required", None)  # a command test is always required
            if t == "ai_judged":
                d["releases_gate"] = False
        if t != "ai_judged":
            d.pop("releases_gate", None)
        return d

    @writes()
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
            if status == "approved":
                at = c.execute("SELECT approved_at FROM rungs WHERE pk=?", (pk,)).fetchone()[0]
                self._baseline(c, pk, data, at)
        return self._rung_dict(self._rung_by_pk(pk))

    @writes()
    def edit_test(self, project: str, test_rid: str, fields: dict, actor: Actor = HUMAN) -> dict:
        r = self._rung_row(project, test_rid)
        if r["kind"] != "test":
            raise RungError(f"{test_rid} is not a test", code="bad_request", status=400)
        fields = dict(fields)
        self._check_version(r, fields.pop("version", None))
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
        # edit() makes earlier results stop counting when the command, type, folder, pass rule or steps change.
        return self.edit(project, test_rid, text=text, actor=actor, data=data, approve=False,
                         expect_version=r["version"])

    @writes()
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

    @writes()
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
        """Requirements the need still asks for: on the ladder and not retired (Round 24)."""
        return [r for r in self._children_rows(need_pk) if r["status"] not in ("proposed", "dismissed")
                and not _l(r["data"], {}).get("out_of_scope")]

    # ------------------------------------------------------------------ need completeness (Round 24, B14)

    @writes()
    def retire_requirement(self, project: str, req_rid: str, reason: str, actor: Actor = HUMAN) -> dict:
        """Take a requirement out of scope with a reason. It stays visible, never silently dropped."""
        if not actor.is_human:
            raise RungError("only a human can retire a requirement", code="forbidden", status=403)
        r = self._rung_row(project, req_rid)
        if r["kind"] != "requirement":
            raise RungError(f"{req_rid} is not a requirement", code="bad_request", status=400)
        reason = (reason or "").strip()
        if not reason:
            raise RungError("say why it is out of scope", code="bad_request", status=400, field="reason")
        data = _l(r["data"], {})
        data["out_of_scope"] = {"reason": reason, "by": actor.name, "at": self.clock()}
        with self._tx() as c:
            c.execute("UPDATE rungs SET data=?, updated_at=? WHERE pk=?", (_j(data), self.clock(), r["pk"]))
            self._touch_project(c, r["project_pk"])
        return self._rung_dict(self._rung_by_pk(r["pk"]))

    @writes()
    def restore_requirement(self, project: str, req_rid: str, actor: Actor = HUMAN) -> dict:
        if not actor.is_human:
            raise RungError("only a human can restore a requirement", code="forbidden", status=403)
        r = self._rung_row(project, req_rid)
        data = _l(r["data"], {})
        data.pop("out_of_scope", None)
        with self._tx() as c:
            c.execute("UPDATE rungs SET data=?, updated_at=? WHERE pk=?", (_j(data), self.clock(), r["pk"]))
            self._touch_project(c, r["project_pk"])
        return self._rung_dict(self._rung_by_pk(r["pk"]))

    def need_completeness(self, project: str, need_rid: str, fresh: bool = False) -> dict:
        """Complete only when every requirement the need asks for is approved, has a specification, and every
        specification under it is verified now (the one evaluator). Everything else is listed by id."""
        need = self._rung_row(project, need_rid)
        if need["kind"] != "need":
            raise RungError(f"{need_rid} is not a need", code="bad_request", status=400)
        cur = self._root_basis(need["project_pk"], fresh=fresh)
        open_, out, verified = [], [], []
        reqs = [r for r in self._children_rows(need["pk"]) if r["status"] not in ("proposed", "dismissed")]
        for r in reqs:
            ret = _l(r["data"], {}).get("out_of_scope")
            if ret:
                out.append({"rung": r["rid"], "reason": ret.get("reason", "")})
                continue
            if r["status"] != "approved":
                open_.append({"rung": r["rid"], "code": "not_approved", "text": f"{r['rid']} is {r['status']}"})
                continue
            specs = [s for s in self._children_rows(r["pk"]) if s["status"] not in ("proposed", "dismissed")]
            if not specs:
                open_.append({"rung": r["rid"], "code": "no_specification", "text": f"{r['rid']} has no specification"})
                continue
            for s in specs:
                v = self._verify(s, cur)
                if v["ok"]:
                    verified.append(s["rid"])
                else:
                    open_.append({"rung": r["rid"], "spec": s["rid"], "code": "not_verified",
                                  "verification": v["verification"],
                                  "text": f"{r['rid']}: {s['rid']} not verified ({v['verification']})"})
        if need["status"] != "approved":
            open_.insert(0, {"rung": need["rid"], "code": "not_approved", "text": f"{need['rid']} is {need['status']}"})
        if not open_ and not verified:
            open_.append({"rung": need["rid"], "code": "no_requirements", "text": f"{need['rid']} has no requirement in scope"})
        return {"need": need["rid"], "complete": not open_, "open": open_, "out_of_scope": out, "verified": verified}

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
        # What the result applies to (Round 22). A pass recorded on other code no longer counts for verification.
        b = e["basis_end"] or e["basis_start"]
        d["basis"] = evidence.short(b)
        d["reason"] = e["reason"]
        d["out_of_date"] = False
        if d["counts"] and e["status"] == "pass" and b:
            cur = self._spec_cur(self._rung_by_pk(test_row["parent_pk"]), self._root_basis(test_row["project_pk"]))
            d["out_of_date"] = e["reason"] == "changed_during_check" or (evidence.UNKNOWN not in (b, cur) and b != cur)
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

    @writes()
    def begin_execution(self, project: str, test_rid: str, carried_by: str = "engine", run_pk=None,
                        attempt=None, once_by: Actor | None = None) -> int:
        """Create a running command execution and return its number. perform_execution runs it.
        Only approved commands run; `once_by` is a person pressing Run once on the command in the editor."""
        t = self._rung_row(project, test_rid)
        data = _l(t["data"], {})
        if data.get("type") == "manual":
            raise RungError("a manual test is recorded by a human, not run", code="bad_request", status=400)
        trial = once_by is not None and once_by.is_human and t["status"] == "draft"
        if not trial and (t["status"] not in ("approved", "stale") or t["approved_at"] is None):
            raise RungError(f"{test_rid} is {t['status']}; a person approves a test before it runs",
                            code="not_approved", status=409)
        p = self._project_row(t["project_pk"])
        folder = Path(p["folder"]).expanduser() / data.get("folder", ".")
        with self._tx() as c:
            n = c.execute("SELECT COALESCE(MAX(n),0)+1 FROM executions WHERE test_pk=?", (t["pk"],)).fetchone()[0]
            seq = self._next_seq(c)
            c.execute("INSERT INTO executions(test_pk, n, seq, kind, status, command, carried_by, run_pk, attempt, "
                      "context, commit_ref, basis_start, started_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                      (t["pk"], n, seq, data.get("type", "command"), "running", data.get("command", ""), carried_by,
                       run_pk, attempt, context_line(), git_commit(folder),
                       self._spec_cur(self._rung_by_pk(t["parent_pk"]), evidence.basis(p["folder"], fresh=True)),
                       self.clock()))
            self._touch_project(c, t["project_pk"])
        return n

    def perform_execution(self, project: str, test_rid: str, n: int, should_cancel=None, env=None) -> dict:
        t = self._rung_row(project, test_rid)
        data = _l(t["data"], {})
        p = self._project_row(t["project_pk"])
        folder = Path(p["folder"]).expanduser() / data.get("folder", ".")
        e = self._q1("SELECT * FROM executions WHERE test_pk = ? AND n = ?", (t["pk"], n))
        if e is None:
            raise NotFound(f"{test_rid} has no execution {n}")

        def push(text):
            with self._tx() as c:
                c.execute("UPDATE executions SET output = ? WHERE pk = ?", (text, e["pk"]))

        def cancelled():
            row = self._q1("SELECT status FROM executions WHERE pk = ?", (e["pk"],))
            if row and row["status"] == "cancelled":
                return True
            return bool(should_cancel and should_cancel())

        root = Path(p["folder"]).expanduser()
        reason = ""
        moved = self._protected_change(t, data, root, folder) if folder.is_dir() else []
        before = evidence.manifest(root)
        if not folder.is_dir():
            res_exit, res_out, status = None, f"folder not found: {folder}", "error"
        elif not folder.resolve().is_relative_to(root.resolve()):
            res_exit, res_out, status = None, f"the test folder is outside the project folder: {folder}", "error"
        else:
            # Files this test is judged by that are not the ones a person approved do not stop it running: the
            # person sees what the changed test says. Its result proves nothing until they accept the files.
            res = run_command(data.get("command", ""), folder, timeout=data.get("timeout", 120),
                              output_limit=data.get("output_limit", 64000), on_output=push,
                              should_cancel=cancelled, env=env)
            res_exit, res_out = res.exit_code, res.output
            if res.cancelled:
                status = "cancelled"
            else:
                rule = data.get("pass_rule") or {"kind": "exit_code", "value": 0}
                # The shell answers 127 (not found) and 126 (not executable) when the command never started.
                unstarted = res.exit_code in (126, 127)
                if res.timed_out or res.launch_error or unstarted:
                    status = "error"
                    if unstarted:
                        res_out = (res_out or "") + f"\ncould not start: the shell exited {res.exit_code}"
                        res_exit = None
                else:
                    status = "pass" if self._passes(rule, res.exit_code, res.output) else "fail"
            if data.get("type") == "ai_judged" and status == "pass":
                status = "pass"  # recorded, but never releases a gate (see _released)
        after = evidence.manifest(root)
        spec_row = self._rung_by_pk(t["parent_pk"])
        end_basis = self._scoped_digest(t["project_pk"], self._spec_comps(spec_row), after) or evidence.digest(after)
        evidence.forget(root)
        if status in ("pass", "fail") and evidence.modified(before, after):
            reason = "changed_during_check"  # a file the check ran against changed under it: it applies to neither
        if moved and status in ("pass", "fail", "error"):
            reason = "verification_changed"  # judged by files no person approved: never counts, either way
            res_out = ("judged by files changed since the test was approved: "
                       + ", ".join(f"{m['path']} ({m['change']})" for m in moved) + "\n\n" + (res_out or ""))
        with self._tx() as c:
            # Only a running execution takes its result: a cancel that landed while the command finished
            # stands (the output is kept with it), so a cancelled execution never turns into a pass.
            cur = c.execute("UPDATE executions SET status=?, exit_code=?, output=?, ended_at=?, basis_end=?, reason=? "
                            "WHERE pk=? AND status='running'",
                            (status, res_exit, res_out, self.clock(), end_basis, reason, e["pk"]))
            if not cur.rowcount:
                c.execute("UPDATE executions SET exit_code=?, output=? WHERE pk=?", (res_exit, res_out, e["pk"]))
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

    @writes()
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
        b = self._spec_cur(self._rung_by_pk(t["parent_pk"]),
                           evidence.basis(self._project_row(t["project_pk"])["folder"], fresh=True))
        with self._tx() as c:
            n = c.execute("SELECT COALESCE(MAX(n),0)+1 FROM executions WHERE test_pk=?", (t["pk"],)).fetchone()[0]
            seq = self._next_seq(c)
            c.execute("INSERT INTO executions(test_pk, n, seq, kind, status, carried_by, context, note, recorder, "
                      "basis_start, basis_end, started_at, ended_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                      (t["pk"], n, seq, "manual", "fail" if result == "fail" else "pending", actor.name,
                       "manual", (note or "").strip(), actor.name, b, b, now, now))
            self._touch_project(c, t["project_pk"])
        return self.execution(project, test_rid, n)

    @writes()
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

    # ------------------------------------------------------------------ evidence (Round 22)

    def _baseline(self, c, test_pk: int, data: dict, approved_at) -> None:
        """Record the content of the files a command test is judged by, as the person approved it."""
        if data.get("type", "command") == "manual":
            return
        row = c.execute("SELECT r.*, p.folder AS pfolder FROM rungs r JOIN projects p ON p.pk = r.project_pk "
                        "WHERE r.pk=?", (test_pk,)).fetchone()
        root = Path(row["pfolder"]).expanduser()
        files = evidence.protected_files(data.get("command", ""), root / data.get("folder", "."), root)
        c.execute("UPDATE rungs SET assets=? WHERE pk=?",
                  (_j({"at": approved_at, "files": evidence.digest_files(root, files)}), test_pk))

    def _protected_change(self, t, data: dict, root: Path, folder: Path) -> list[dict]:
        """Protected files that changed since the person approved this test; [] when nothing changed."""
        if t["status"] not in ("approved", "stale") or t["approved_at"] is None:
            return []
        base = _l(t["assets"], None) if "assets" in t.keys() else None
        if not base or base.get("at") != t["approved_at"]:
            # Approved before protected files were recorded (an older store): this approval's files are recorded
            # now, and the first result after it is judged against them.
            with self._tx() as c:
                self._baseline(c, t["pk"], data, t["approved_at"])
            return []
        files = sorted(set(base.get("files", {})) | set(evidence.protected_files(data.get("command", ""), folder, root)))
        return evidence.changed(base.get("files", {}), evidence.digest_files(root, files))

    def protected(self, project: str, test_rid: str) -> dict:
        """The files a command test is judged by, and which of them changed since it was approved."""
        t = self._rung_row(project, test_rid)
        data = _l(t["data"], {})
        if t["kind"] != "test" or data.get("type", "command") == "manual":
            return {"test": t["rid"], "files": [], "changed": []}
        root = Path(self._project_row(t["project_pk"])["folder"]).expanduser()
        base = _l(t["assets"], None) or {}
        recorded = base.get("files", {}) if base.get("at") == t["approved_at"] else {}
        files = sorted(set(recorded) | set(evidence.protected_files(data.get("command", ""),
                                                                      root / data.get("folder", "."), root)))
        moved = evidence.changed(recorded, evidence.digest_files(root, files)) if recorded else []
        return {"test": t["rid"], "files": files, "changed": moved, "recorded": bool(recorded)}

    @writes()
    def accept_test_files(self, project: str, test_rid: str, actor: Actor = HUMAN) -> dict:
        """A person looked at the changed files a test is judged by and accepts them as the approved test."""
        if not actor.is_human:
            raise RungError("only a human accepts changes to a test's files", code="forbidden", status=403)
        t = self._rung_row(project, test_rid)
        data = _l(t["data"], {})
        if t["kind"] != "test" or data.get("type", "command") == "manual":
            raise RungError(f"{test_rid} is not a command test", code="bad_request", status=400)
        if t["status"] not in ("approved", "stale"):
            raise RungError(f"{test_rid} is {t['status']}; approve it first")
        with self._tx() as c:
            self._baseline(c, t["pk"], data, t["approved_at"])
            self._log(c, t["project_pk"], "test_files_accepted", {"test": t["rid"]}, actor.name)
            self._touch_project(c, t["project_pk"])
        return self.protected(project, test_rid)

    @staticmethod
    def _required(data: dict) -> bool:
        ttype = data.get("type", "command")
        if ttype == "command":
            return True
        if ttype == "manual":
            # Every manual test written since Round 22 stores the key; one without it predates the rule and
            # keeps its old meaning, optional. Stored values are never rewritten on upgrade (RES-04).
            return data.get("required", False) is not False
        return False  # AI judged: advisory, never verifies (TST-04)

    def _root_basis(self, project_pk: int, fresh: bool = False) -> str:
        return evidence.basis(self._project_row(project_pk)["folder"], fresh=fresh)

    def _test_state(self, t, cur: str) -> dict:
        """One test's contribution to verification, from its latest result that applies to this test version.

        state: satisfied | failed | missing | checking | could_not_verify | manual_pending | out_of_date | stale.
        A cancelled execution leaves no evidence; the result before it still has to match the current code."""
        cur = self._spec_cur(self._rung_by_pk(t["parent_pk"]), cur)  # SYS-11: judged on its components' paths
        data = _l(t["data"], {})
        ttype = data.get("type", "command")
        d = {"test": t["rid"], "type": ttype, "required": self._required(data), "execution": None,
             "flags": [], "historical_pass": None}
        if t["status"] == "stale":
            d["state"] = "stale"
            return d
        rows = self._q("SELECT * FROM executions WHERE test_pk=? AND seq>? AND status!='cancelled' ORDER BY seq DESC",
                       (t["pk"], t["valid_from"]))
        last_pass = next((e for e in rows if e["status"] == "pass"), None)
        if last_pass is not None:
            d["historical_pass"] = {"execution": last_pass["n"], "basis": last_pass["basis_end"] or last_pass["basis_start"]}
        if not rows:
            d["state"] = "missing"
            return d
        e = rows[0]
        d["execution"] = e["n"]
        if ttype == "manual" and not d["required"]:
            # Optional: only a decided result matters, and only a failure blocks.
            decided = next((x for x in rows if x["status"] in ("pass", "fail")), None)
            if decided is None:
                d["state"] = "missing" if e["status"] != "pending" else "manual_pending"
                return d
            d["execution"] = decided["n"]
            e = decided
        if e["status"] == "running":
            d["state"] = "checking"
        elif e["reason"] == "verification_changed":
            d["state"] = "could_not_verify"  # pass or fail, it was judged by files no person approved
            d["reason"] = "verification_changed"
        elif e["status"] == "error":
            d["state"] = "could_not_verify"
            d["reason"] = e["reason"] or "error"
        elif e["status"] == "pending":
            d["state"] = "manual_pending"
        elif e["status"] == "fail":
            d["state"] = "failed"  # a failure blocks whatever code it ran on; a recheck runs it again on this code
            b = e["basis_end"] or e["basis_start"]
            d["recheck"] = bool(b) and evidence.UNKNOWN not in (b, cur) and (b != cur or e["reason"] == "changed_during_check")
        else:
            b = e["basis_end"] or e["basis_start"]
            d["basis"] = b
            if e["reason"] == "changed_during_check":
                d["state"] = "out_of_date"
                d["reason"] = "changed_during_check"
            elif not b:
                d["state"] = "satisfied"
                d["flags"].append("legacy")  # recorded before results carried a basis
            elif cur == evidence.UNKNOWN:
                d["state"] = "could_not_verify"  # the code as it is now cannot be read: no positive result
                d["reason"] = "basis_unknown"
            elif b == evidence.UNKNOWN:
                d["state"] = "out_of_date"  # recorded when the code could not be read: it proves nothing now
                d["reason"] = "code_changed"
            elif b != cur:
                d["state"] = "out_of_date"
                d["reason"] = "code_changed"
            else:
                d["state"] = "satisfied"
        return d

    def _test_result(self, t) -> str:
        """pass | fail | pending | running | error | out_of_date | stale | not_run (for display): the newest
        result of this test version, read by the same evaluator as the gate."""
        if t["status"] == "stale":
            return "stale"
        if self._q1("SELECT 1 FROM executions WHERE test_pk=? AND status='running'", (t["pk"],)):
            return "running"
        st = self._test_state(t, self._root_basis(t["project_pk"]))
        newest = self._q1("SELECT status FROM executions WHERE test_pk=? AND seq>? AND status!='cancelled' "
                          "ORDER BY seq DESC LIMIT 1", (t["pk"], t["valid_from"]))
        if newest and newest["status"] == "pending":
            return "pending"
        return {"satisfied": "pass", "failed": "fail", "missing": "not_run", "checking": "running",
                "could_not_verify": "error", "manual_pending": "pending", "out_of_date": "out_of_date",
                "stale": "stale"}[st["state"]]

    def _seen_failing(self, t) -> bool | None:
        """For a command test: True if this version of it failed before its first pass, False if its first result
        was a pass, None while it has never passed. A Could not run is not a failure; it never changes verification."""
        if _l(t["data"], {}).get("type", "command") != "command":
            return None
        first_pass = self._q1("SELECT n FROM executions WHERE test_pk=? AND seq>? AND status='pass' ORDER BY n LIMIT 1",
                              (t["pk"], t["valid_from"]))
        if not first_pass:
            return None
        return bool(self._q1("SELECT 1 FROM executions WHERE test_pk=? AND seq>? AND status='fail' AND n<?",
                             (t["pk"], t["valid_from"], first_pass["n"])))

    def _retired_pks(self, project_pk: int) -> set[int]:
        """Every rung under a retired need, the need included."""
        return {r[0] for r in self._q(
            "WITH RECURSIVE sub(pk) AS (SELECT pk FROM rungs WHERE project_pk=? AND kind='need' AND retired_at IS NOT NULL "
            "UNION ALL SELECT r.pk FROM rungs r JOIN sub ON r.parent_pk = sub.pk) SELECT pk FROM sub", (project_pk,))}

    def outdated_tests(self, project: str) -> list[str]:
        """Approved command tests whose newest result was recorded on code that has changed since (a pass that no
        longer applies, or a failure that may no longer hold): running them again is how they apply to this code."""
        p = self._project_row(project)
        gone = self._retired_pks(p["pk"])
        cur = evidence.basis(p["folder"], fresh=True)
        out = []
        for t in self._q("SELECT t.* FROM rungs t JOIN rungs s ON s.pk = t.parent_pk WHERE t.project_pk=? AND "
                         "t.kind='test' AND t.status='approved' AND s.status='approved' ORDER BY s.num, t.rid", (p["pk"],)):
            if t["pk"] in gone or _l(t["data"], {}).get("type", "command") != "command":
                continue
            st = self._test_state(t, cur)
            if st["state"] == "out_of_date" or st.get("recheck"):
                out.append(t["rid"])
        return out

    def recheck(self, project: str, carried_by: str = "engine", skip: tuple = ()) -> list[dict]:
        """Run every out-of-date command test again (no model involved). Returns the new executions."""
        return [self.run_test(project, rid, carried_by=carried_by) for rid in self.outdated_tests(project)
                if rid not in skip]

    def verification(self, project: str, rid: str, fresh: bool = False) -> dict:
        """The one verification result every surface reads (Round 22): state, typed blockers, basis, next action."""
        r = self._rung_row(project, rid)
        if r["kind"] != "specification":
            raise RungError(f"{rid} is not a specification", code="bad_request", status=400)
        return self._verify(r, self._root_basis(r["project_pk"], fresh=fresh))

    def _verify(self, spec, cur: str | None = None) -> dict:
        """The verdict, memoised per specification for one state of the store and one code basis: a page asks
        for the same specification from its tiles, coverage, tree and lists. Any commit, by this connection
        (`total_changes`) or another (`PRAGMA data_version`), and any change to the files, gives a new key.
        Callers read the result; none changes it."""
        cur = cur if cur is not None else self._root_basis(spec["project_pk"])
        try:
            state = (self.conn.execute("PRAGMA data_version").fetchone()[0], self.conn.total_changes)
        except Exception:
            return self._verify_now(spec, cur)
        cache = getattr(self, "_vcache", None)
        if cache is None or cache[0] != state:
            cache = self._vcache = (state, {})
        key = (spec["pk"], cur)
        hit = cache[1].get(key)
        if hit is None:
            hit = cache[1][key] = self._verify_now(spec, cur)
        return hit

    def _verify_now(self, spec, cur: str) -> dict:
        blockers = []

        def block(code, text, **kw):
            blockers.append({"code": code, "text": text, **kw})

        if spec["status"] == "stale":
            block("stale", f"{spec['rid']} is stale", rung=spec["rid"])
        elif spec["status"] != "approved":
            block("not_approved", f"{spec['rid']} is not approved", rung=spec["rid"])
        node = self._rung_by_pk(spec["parent_pk"]) if spec["parent_pk"] else None
        while node is not None:
            if node["status"] == "stale":
                block("stale", f"{node['rid']} is stale", rung=node["rid"])
            node = self._rung_by_pk(node["parent_pk"]) if node["parent_pk"] else None
        tests = [t for t in self._children_rows(spec["pk"]) if t["status"] in ("approved", "stale")]
        states, passing, flags = [], 0, set()
        if not tests:
            block("no_tests", f"{spec['rid']} has no accepted tests")
        for t in tests:
            st = self._test_state(t, cur)
            states.append(st)
            rid, n, state = t["rid"], st["execution"], st["state"]
            flags.update(st["flags"])
            if state == "satisfied" and st["type"] != "ai_judged":
                passing += 1
                continue
            if state == "stale":
                block("stale", f"{rid} is stale", test=rid)
            elif state == "failed":
                if st["type"] == "ai_judged":
                    block("failed", f"{rid} failed (#{n}), AI judged", test=rid, execution=n)
                else:
                    block("failed", f"{rid} failed (#{n})", test=rid, execution=n)
            elif not st["required"]:
                continue  # optional or AI judged: not needed, and nothing failed
            elif state == "missing":
                if st["type"] == "manual":
                    block("manual_missing", f"{rid} is a required manual check with no result yet", test=rid)
                else:
                    block("not_run", f"{rid} has not passed since the last upstream change", test=rid)
            elif state == "checking":
                block("checking", f"{rid} is running (#{n})", test=rid, execution=n)
            elif state == "could_not_verify":
                if st.get("reason") == "verification_changed":
                    block("verification_changed", f"{rid} #{n} was judged by files changed since it was approved",
                          test=rid, execution=n)
                elif st.get("reason") != "basis_unknown":  # named once for the whole project below
                    block("could_not_verify", f"{rid} could not run (#{n})", test=rid, execution=n)
            elif state == "manual_pending":
                block("manual_pending", f"{rid} #{n} is waiting for a person to approve it", test=rid, execution=n)
            elif state == "out_of_date":
                if st.get("reason") == "changed_during_check":
                    block("out_of_date", f"{rid} passed (#{n}) while files changed under it", test=rid, execution=n)
                else:
                    block("out_of_date", f"{rid} passed (#{n}) on code that has changed since", test=rid, execution=n)
        for cb in self._spec_contract_blockers(spec):  # SYS-02: an approved contract change since the last run
            block(cb.pop("code"), cb.pop("text"), **cb)
        if cur == evidence.UNKNOWN and tests:
            block("basis_unknown", "the project's files cannot be read whole (the folder is missing, or it holds "
                  f"more than {evidence.MAX_FILES} files after .gitignore and .rungignore)")
        if tests and passing == 0 and not blockers:
            block("no_passing", f"{spec['rid']} has no passing test that can release it")
        required = [s for s in states if s["required"]]
        ok = not blockers
        if ok:
            state = "verified"
        elif any(b["code"] in ("stale", "not_approved", "no_tests") for b in blockers):
            state = "contract"
        elif any(b["code"] == "failed" for b in blockers):
            state = "failed"
        elif any(b["code"] == "checking" for b in blockers):
            state = "checking"
        elif any(b["code"] in ("manual_pending", "manual_missing") for b in blockers) and \
                all(b["code"] in ("manual_pending", "manual_missing") for b in blockers):
            state = "awaiting_manual"
        elif any(b["code"] in ("out_of_date", "contract_changed") for b in blockers):
            state = "out_of_date"
        elif any(b["code"] in ("could_not_verify", "verification_changed", "basis_unknown") for b in blockers):
            state = "could_not_verify"
        else:
            state = "unverified"
        return {"spec": spec["rid"], "ok": ok, "verification": state, "basis": cur,
                "required_checks": {"total": len(required), "satisfied": sum(1 for s in required if s["state"] == "satisfied")},
                "tests": states, "blockers": blockers, "flags": sorted(flags), "next_action": self._next_action(blockers)}

    @staticmethod
    def _next_action(blockers: list[dict]) -> dict | None:
        order = ["stale", "not_approved", "no_tests", "basis_unknown", "verification_changed", "manual_pending", "failed",
                 "could_not_verify", "out_of_date", "contract_changed", "not_run", "manual_missing", "checking",
                 "no_passing"]
        kinds = {"stale": "review_change", "not_approved": "approve", "no_tests": "add_test",
                 "verification_changed": "review_test_files", "manual_pending": "approve_manual_result",
                 "failed": "repair", "could_not_verify": "repair_test_setup", "out_of_date": "run_tests",
                 "not_run": "run_tests", "manual_missing": "record_manual_result", "checking": "wait",
                 "no_passing": "run_tests", "basis_unknown": "repair_project_folder", "contract_changed": "run_tests"}
        for code in order:
            b = next((x for x in blockers if x["code"] == code), None)
            if b:
                return {"kind": kinds[code], **{k: v for k, v in b.items() if k in ("test", "rung", "execution")}}
        return None

    def _released(self, spec, cur: str | None = None) -> tuple[bool, list[str]]:
        v = self._verify(spec, cur)
        return v["ok"], [b["text"] for b in v["blockers"]]

    def check(self, project: str, rid: str) -> dict:
        """The goal gate. Pure engine computation; never calls a model. Judged against the code as it is now."""
        rid = _canon(rid)  # one id form at every door, echoed back as stored
        r = self._rung_row(project, rid)
        if r["kind"] != "specification":
            raise RungError(f"{rid} is not a specification", code="bad_request", status=400)
        if r["pk"] in self._retired_pks(r["project_pk"]):
            # A retired need leaves every active view and count, the gate included (NED-03).
            return {"id": rid, "ok": False, "blockers": [f"{rid} is under a retired need"]}
        v = self._verify(r, self._root_basis(r["project_pk"], fresh=True))
        return {"id": rid, "ok": v["ok"], "blockers": [b["text"] for b in v["blockers"]], "verification": v["verification"],
                "codes": [b["code"] for b in v["blockers"]], "basis": evidence.short(v["basis"]),
                "next_action": v["next_action"]}

    def check_all(self, project: str) -> dict:
        p = self._project_row(project)
        specs = self._q("SELECT * FROM rungs WHERE project_pk=? AND kind='specification' AND status IN ('approved','stale') "
                        "ORDER BY rid", (p["pk"],))
        results = []
        gone = self._retired_pks(p["pk"])
        cur = evidence.basis(p["folder"], fresh=True)
        for s in specs:
            if s["pk"] in gone:
                continue
            ok, blockers = self._released(s, cur)
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
        if pick:
            return pick["profile"]
        ex = self._q1("SELECT e.carried_by FROM executions e JOIN rungs t ON t.pk=e.test_pk WHERE t.parent_pk=? "
                      "AND e.status IN ('pass','fail') AND e.carried_by NOT IN ('engine','') ORDER BY e.pk DESC LIMIT 1",
                      (spec["pk"],))
        return ex["carried_by"] if ex else None

    # ------------------------------------------------------------------ tiles, needs you, home

    def needs_you(self, project: str) -> list[dict]:
        p = self._project_row(project)
        items = []
        gone = self._retired_pks(p["pk"])
        stale = [r for r in self._q("SELECT * FROM rungs WHERE project_pk=? AND status='stale' ORDER BY kind, num",
                                    (p["pk"],)) if r["pk"] not in gone]
        stale_pks = {r["pk"] for r in stale}
        order = {k: i for i, k in enumerate(KINDS)}
        for r in sorted(stale, key=lambda r: (order[r["kind"]], r["rid"])):
            if r["parent_pk"] in stale_pks:
                continue
            ch = self.change_for(project, r["rid"])
            items.append({"type": "stale", "id": r["rid"], "kind": r["kind"], "text": r["text"],
                          "parent": self._rid_of(r["parent_pk"]), "change": ch})
        for r in self._q("SELECT * FROM rungs WHERE project_pk=? AND status='proposed' ORDER BY pk", (p["pk"],)):
            if r["parent_pk"] in gone:
                continue
            items.append({"type": "proposed", "id": r["rid"], "kind": r["kind"], "text": r["text"],
                          "parent": self._rid_of(r["parent_pk"]), "proposer": r["proposer"],
                          "source_chat": r["source_chat"]})
        for e in self._q("SELECT e.*, r.rid AS trid FROM executions e JOIN rungs r ON r.pk = e.test_pk "
                         "WHERE r.project_pk=? AND e.status='pending' AND e.seq > r.valid_from ORDER BY e.pk", (p["pk"],)):
            if e["test_pk"] in gone:
                continue
            items.append({"type": "approval", "id": e["trid"], "kind": "test", "n": e["n"],
                          "text": f"{e['trid']} #{e['n']} recorded pass", "recorder": e["recorder"], "note": e["note"]})
        # A test whose latest result is Error: it could not run, which is neither a pass nor a fail.
        for e in self._q("SELECT e.*, r.rid AS trid FROM executions e JOIN rungs r ON r.pk = e.test_pk "
                         "WHERE r.project_pk=? AND e.status='error' AND e.seq > r.valid_from "
                         # a develop run still retrying within its budget is the agent's, not yours (U04)
                         "AND NOT EXISTS (SELECT 1 FROM runs u WHERE u.pk = e.run_pk AND u.status IN ('queued','running')) "
                         "AND r.status IN ('approved','stale','draft') AND NOT EXISTS (SELECT 1 FROM executions x "
                         "WHERE x.test_pk = e.test_pk AND x.seq > e.seq AND x.status IN ('pass','fail','error','pending')) "
                         "ORDER BY e.pk", (p["pk"],)):
            if e["test_pk"] in gone:
                continue
            lines = (e["output"] or "").strip().splitlines()
            items.append({"type": "error", "id": e["trid"], "kind": "test", "n": e["n"],
                          "text": f"{e['trid']} #{e['n']} could not run", "reason": lines[-1] if lines else ""})
        # A develop run that stopped for an answer, until a newer run of that specification exists.
        for r in self._q("SELECT r.*, s.rid AS srid FROM runs r JOIN rungs s ON s.pk = r.spec_pk WHERE r.project_pk=? "
                         "AND r.status='needs_input' AND NOT EXISTS (SELECT 1 FROM runs x WHERE x.spec_pk = r.spec_pk "
                         "AND x.pk > r.pk) ORDER BY r.pk", (p["pk"],)):
            if r["spec_pk"] in gone:
                continue
            items.append({"type": "needs_input", "id": r["srid"], "kind": "specification", "run": r["pk"],
                          "text": r["reason"] or "", "profile": r["profile"]})
        return [self._decision(p["pk"], i) for i in items]

    # Needs you as a decision surface (decisions Round 24, U04): each item names the outcome it affects, why it
    # needs a person, what changed or failed, and one recommended action with its own verb. Data only.
    ACTIONS = {"stale": "Review change", "proposed": "Review proposal", "approval": "Approve result",
               "error": "Repair test setup", "needs_input": "Answer the worker"}
    WHY = {"stale": "Changed upstream", "proposed": "Proposed", "approval": "Result recorded",
           "error": "Could not run", "needs_input": "Worker asked"}

    def _decision(self, project_pk: int, item: dict) -> dict:
        r = self._q1("SELECT * FROM rungs WHERE project_pk=? AND rid=?", (project_pk, item["id"]))
        outcome = None
        while r is not None:  # the nearest requirement above the item; a requirement or need names its need
            if r["kind"] == "need" or (r["kind"] == "requirement" and r["rid"] != item["id"]):
                outcome = {"id": r["rid"], "text": r["text"]}
                break
            r = self._q1("SELECT * FROM rungs WHERE pk=?", (r["parent_pk"],)) if r["parent_pk"] else None
        t = item["type"]
        if t == "stale":
            ch = item.get("change")
            what = f"{ch['rung']} changed: {ch['after']}" if ch else f"{item['id']} is stale"
        elif t == "proposed":
            what = f"{item['id']} by {item.get('proposer') or 'an agent'}: {item['text']}"
        elif t == "approval":
            what = f"{item['id']} #{item['n']} recorded pass by {item.get('recorder') or 'you'}"
        elif t == "error":
            what = item.get("reason") or item["text"]
        else:
            what = item["text"] or f"run {item.get('run')} stopped"
        return {**item, "outcome": outcome, "why": self.WHY[t], "what": what,
                "action": {"verb": self.ACTIONS[t], "type": t}}

    def tiles(self, project: str) -> dict:
        p = self._project_row(project)
        gone = self._retired_pks(p["pk"])
        reqs = [r for r in self._q("SELECT * FROM rungs WHERE project_pk=? AND kind='requirement' AND status IN "
                                   "('draft','approved','stale')", (p["pk"],))
                if r["pk"] not in gone and not _l(r["data"], {}).get("out_of_scope")]
        covered = sum(1 for r in reqs if self._req_coverage(r) == "covered")
        stale = sum(1 for r in self._q("SELECT pk FROM rungs WHERE project_pk=? AND status='stale'", (p["pk"],))
                    if r["pk"] not in gone)
        failing = 0
        for t in self._q("SELECT * FROM rungs WHERE project_pk=? AND kind='test' AND status IN ('approved','stale')", (p["pk"],)):
            if t["status"] == "approved" and t["pk"] not in gone:
                rows = self._counting(t)
                if rows and rows[0]["status"] == "fail":
                    failing += 1
        running = self._q1("SELECT COUNT(*) FROM runs WHERE project_pk=? AND status IN ('queued','running')", (p["pk"],))[0]
        running += self._q1("SELECT COUNT(*) FROM executions e JOIN rungs r ON r.pk=e.test_pk WHERE r.project_pk=? "
                            "AND e.status='running' AND e.run_pk IS NULL", (p["pk"],))[0]
        # Open claims are work in flight too (DCK-04): the picker, the dock and home count the same set.
        running += self._q1("SELECT COUNT(*) FROM claims c JOIN rungs s ON s.pk=c.spec_pk WHERE s.project_pk=? "
                            "AND c.status='open'", (p["pk"],))[0]
        return {"covered": covered, "requirements": len(reqs), "stale": stale, "failing": failing,
                "needs_you": len(self.needs_you(project)), "running": running, "last_activity": p["last_activity"],
                "archived": p["archived_at"] is not None}

    def overview(self) -> dict:
        """Needs you across every open project (Round 12, 16): each project's items and the work in flight.

        Read-only. Each group's count is `needs_you(project)`, so it equals that project's Home tile."""
        groups = []
        for proj in self.projects():
            name = proj["name"]
            p = self._project_row(name)
            items = [{k: v for k, v in i.items() if k in ("type", "id", "kind", "text", "n", "run", "parent")}
                     for i in self.needs_you(name)]
            running = [{"kind": "run", "run": r["pk"], "id": self._rid_of(r["spec_pk"]), "profile": r["profile"],
                        "status": r["status"]}
                       for r in self._q("SELECT * FROM runs WHERE project_pk=? AND status IN ('queued','running') "
                                        "ORDER BY pk", (p["pk"],))]
            running += [{"kind": "exec", "id": e["trid"], "n": e["n"]}
                        for e in self._q("SELECT e.n, r.rid AS trid FROM executions e JOIN rungs r ON r.pk=e.test_pk "
                                         "WHERE r.project_pk=? AND e.status='running' AND e.run_pk IS NULL ORDER BY e.pk",
                                         (p["pk"],))]
            groups.append({"name": name, "folder": proj["folder"], "stats": proj["stats"], "items": items,
                           "running": running})
        return {"projects": groups, "current": self.current_project(),
                "total": sum(len(g["items"]) for g in groups),
                "archived": len(self.projects(archived=True))}

    def home(self, project: str) -> dict:
        p = self._project_row(project)
        running = [self._run_dict(r) for r in self._q(
            "SELECT * FROM runs WHERE project_pk=? AND status IN ('queued','running') ORDER BY pk", (p["pk"],))]
        live_execs = []
        for e in self._q("SELECT e.*, r.rid AS trid FROM executions e JOIN rungs r ON r.pk=e.test_pk WHERE r.project_pk=? "
                         "AND e.status='running' AND e.run_pk IS NULL ORDER BY e.pk", (p["pk"],)):
            live_execs.append({"test": e["trid"], "n": e["n"], "started_at": e["started_at"]})
        done, draft, nxt = [], [], []
        gone = self._retired_pks(p["pk"])
        busy = {r["spec_pk"] for r in self._q("SELECT spec_pk FROM runs WHERE project_pk=? AND status IN "
                                              "('queued','running')", (p["pk"],))}
        busy |= {r["spec_pk"] for r in self._q("SELECT c.spec_pk FROM claims c JOIN rungs s ON s.pk=c.spec_pk WHERE "
                                               "s.project_pk=? AND c.status='open'", (p["pk"],))}
        cur = evidence.basis(p["folder"])
        for s in self._q("SELECT * FROM rungs WHERE project_pk=? AND kind='specification' ORDER BY num, rid", (p["pk"],)):
            if s["pk"] in gone:
                continue
            if s["status"] == "approved":
                v = self._verify(s, cur)
                if v["ok"]:
                    tests = [{"id": t["rid"], "result": self._test_result(t)} for t in self._children_rows(s["pk"])]
                    done.append({"id": s["rid"], "text": s["text"], "tests": tests})
                elif s["pk"] not in busy and v["verification"] != "checking":
                    # Approved, not verified, nobody on it: the next move, from the same evaluator (U05).
                    nxt.append({"id": s["rid"], "text": s["text"], "verification": v["verification"],
                                "next_action": v["next_action"], "blocker": v["blockers"][0]["text"] if v["blockers"] else ""})
            elif s["status"] == "draft":
                draft.append({"id": s["rid"], "text": s["text"], "kind": "specification",
                              "parent": self._rid_of(s["parent_pk"])})
        for r in self._q("SELECT * FROM rungs WHERE project_pk=? AND kind='requirement' AND status='draft' ORDER BY num", (p["pk"],)):
            if r["pk"] in gone:
                continue
            specs = [s["rid"] for s in self._children_rows(r["pk"])]
            draft.append({"id": r["rid"], "text": r["text"], "kind": "requirement", "specs": specs,
                          "parent": self._rid_of(r["parent_pk"])})
        needs = []
        for n in self._q("SELECT * FROM rungs WHERE project_pk=? AND kind='need' AND retired_at IS NULL ORDER BY num",
                         (p["pk"],)):
            comp = self.need_completeness(project, n["rid"])
            needs.append({"id": n["rid"], "text": n["text"], "status": n["status"], "complete": comp["complete"],
                          "open": comp["open"], "out_of_scope": comp["out_of_scope"]})
        # What is left when nothing needs you (U04): how many open items and under which needs, never "all done".
        unfinished = {"open": sum(len(n["open"]) for n in needs),
                      "needs": [{"id": n["id"], "open": len(n["open"])} for n in needs if not n["complete"]]}
        return {"project": self.project(project), "tiles": self.tiles(project), "needs_you": self.needs_you(project),
                "unfinished": unfinished, "running": running, "running_tests": live_execs, "done": done, "draft": draft, "needs": needs,
                "next": nxt, "out_of_date": self.outdated_tests(project),
                "milestones": [{"id": m["id"], "title": m["title"], "state": m["state"],
                                "verified": sum(1 for x in m["scope"] if x["ok"]), "total": len(m["scope"]),
                                "blocker": m["blockers"][0]["text"] if m["blockers"] else ""}
                               for m in self.milestones(project)],
                "claims": [{**c, "check": self.check(project, c["spec"])} for c in self.claims(project)]}

    # ------------------------------------------------------------------ allocation and picks

    def _profile_facts(self, name: str, ignore_claim: int | None = None) -> allocation.ProfileFacts:
        prof = self.profile(name)
        running = self._q1("SELECT COUNT(*) FROM runs WHERE profile=? AND status IN ('queued','running')", (name,))[0]
        running += self.bot_running(name)  # a running Suggest counts toward At once (Round 13)
        total = self._q1("SELECT COUNT(*) FROM executions WHERE carried_by=? AND kind='command' AND status IN "
                         "('pass','fail','error')", (name,))[0]
        completed = self._q1("SELECT COUNT(*) FROM executions WHERE carried_by=? AND kind='command' AND status IN "
                             "('pass','fail')", (name,))[0]
        claims = self._q1("SELECT COUNT(*) FROM claims WHERE profile=? AND status='open' AND pk IS NOT ?",
                          (name, ignore_claim))[0]
        return allocation.ProfileFacts(name=name, labels=tuple(prof["labels"]), cost=prof["cost"],
                                       enabled=prof["enabled"], running=running, completed=completed, total=total,
                                       tools=tuple(prof["tools"]), at_once=int(prof["at_once"]), claims=claims)

    def _authors(self, s) -> dict[str, list[str]]:
        """Every profile that wrote this specification or one of its tests (the agent author of any
        version, the drafting profile, the proposer), each with the rungs it wrote."""
        out: dict[str, list[str]] = {}

        def add(name, rid):
            if name and rid not in out.setdefault(name, []):
                out[name].append(rid)
        rows = [s] + [t for t in self._children_rows(s["pk"]) if t["status"] != "dismissed"]
        for r in rows:
            if r["author_kind"] == "agent":
                add(r["author_name"], r["rid"])
            add(r["proposer"], r["rid"])
            for d in [_l(r["data"], {})] + [_l(v["data"], {}) for v in
                                             self._q("SELECT data FROM rung_versions WHERE rung_pk=?", (r["pk"],))]:
                add(d.get("drafted_by"), r["rid"])
                for name in d.get("drafters") or []:
                    add(name, r["rid"])
            for v in self._q("SELECT by_name, by_kind FROM rung_versions WHERE rung_pk=?", (r["pk"],)):
                if v["by_kind"] == "agent":
                    add(v["by_name"], r["rid"])
        return out

    def _needs_of(self, s) -> tuple[allocation.Needs, str]:
        """What a specification asks of its carrier, and why it is human only ('' when it is not)."""
        data = _l(s["data"], {})
        tests = [t for t in self._children_rows(s["pk"]) if t["status"] in ("approved", "stale", "draft")]
        why_human = ""
        if data.get("human_only"):
            why_human = "marked"
        elif tests and all(_l(t["data"], {}).get("type") == "manual" for t in tests):
            why_human = "all tests manual"
        independent = bool(data.get("independent"))
        authors = self._authors(s) if independent else {}
        needs = allocation.Needs(
            spec=s["rid"], required_tags=tuple(data.get("required_tags", []) or ()),
            required_tools=tuple(data.get("required_tools", []) or ()), independent=independent,
            authors=frozenset(authors), human_only=bool(why_human),
            authored=tuple((n, rid) for n, rids in authors.items() for rid in rids))
        return needs, why_human

    def _project_facts(self, p) -> list[allocation.ProfileFacts]:
        names = [n for n in _l(p["profiles"], []) if self._q1("SELECT 1 FROM profiles WHERE name=?", (n,))]
        return [self._profile_facts(n) for n in names]

    def _facts_for(self, facts: list, spec_pk: int) -> list:
        """The facts as they stand for one specification: the claim on that specification is the work
        itself, not load against it, so its holder is not at capacity for it."""
        held = self._q1("SELECT profile FROM claims WHERE spec_pk=? AND status='open' LIMIT 1", (spec_pk,))
        run = self._q1("SELECT profile FROM runs WHERE spec_pk=? AND status IN ('queued','running') LIMIT 1",
                       (spec_pk,))
        if held is None and run is None:
            return facts
        import dataclasses
        out = []
        for f in facts:
            if held is not None and f.name == held["profile"]:
                f = dataclasses.replace(f, claims=max(0, f.claims - 1))
            if run is not None and f.name == run["profile"]:
                f = dataclasses.replace(f, running=max(0, f.running - 1))
            out.append(f)
        return out

    def exclusion(self, project: str, spec_rid: str, profile: str, ignore_claim: int | None = None) -> str:
        """Why a profile may not carry a specification ('' when it may). The one check behind pick, Send,
        start run, the API, the CLI and rung_claim."""
        spec_rid = _canon(spec_rid)  # one id form at every door, echoed back as stored
        s = self._rung_row(project, spec_rid)
        p = self._project_row(s["project_pk"])
        if profile not in _l(p["profiles"], []) or not self._q1("SELECT 1 FROM profiles WHERE name=?", (profile,)):
            return f"not a profile of {p['name']}"
        needs, _ = self._needs_of(s)
        facts = self._facts_for([self._profile_facts(profile, ignore_claim)], s["pk"]) if ignore_claim is None \
            else [self._profile_facts(profile, ignore_claim)]
        return "; ".join(allocation.reasons(facts[0], needs))

    def exclusions(self, project: str) -> dict:
        """Per profile of the project, the specifications it is excluded from, each with its reason."""
        p = self._project_row(project)
        facts = self._project_facts(p)
        gone = self._retired_pks(p["pk"])
        out = {f.name: [] for f in facts}
        for s in self._q("SELECT * FROM rungs WHERE project_pk=? AND kind='specification' AND status IN "
                         "('draft','approved','stale') ORDER BY num, rid", (p["pk"],)):
            if s["pk"] in gone:
                continue
            needs, _ = self._needs_of(s)
            for f in self._facts_for(facts, s["pk"]):
                why = allocation.reasons(f, needs)
                if why:
                    out[f.name].append({"spec": s["rid"], "text": s["text"], "reason": "; ".join(why)})
        return {"project": p["name"], "profiles": out}

    @writes()
    def set_allocation(self, project: str, spec_rid: str, required_tools=None, independent=None, human_only=None,
                       actor: Actor = HUMAN) -> dict:
        """What a specification asks of its carrier: required tools, an independent carrier, human only.
        A person's setting; it changes no text, makes no new version and stales nothing."""
        spec_rid = _canon(spec_rid)  # one id form at every door, echoed back as stored
        if not actor.is_human:
            raise RungError("only a human sets what a specification requires", code="forbidden", status=403)
        s = self._rung_row(project, spec_rid)
        if s["kind"] != "specification":
            raise RungError(f"{spec_rid} is not a specification", code="bad_request", status=400)
        if s["status"] in ("dismissed", "proposed"):
            raise RungError(f"{spec_rid} is {s['status']}", code="refused")
        data = _l(s["data"], {})
        before = {k: data.get(k) for k in ("required_tools", "independent", "human_only")}
        if required_tools is not None:
            if not isinstance(required_tools, list):
                raise RungError("required tools is a list", code="bad_request", status=400, field="required_tools")
            data["required_tools"] = _clean_names(required_tools, "tool", "required_tools")
        for key, v in (("independent", independent), ("human_only", human_only)):
            if v is not None:
                if not isinstance(v, bool):
                    raise RungError(f"{key} is true or false", code="bad_request", status=400, field=key)
                data[key] = v
        after = {k: data.get(k) for k in ("required_tools", "independent", "human_only")}
        with self._tx() as c:
            c.execute("UPDATE rungs SET data=?, updated_at=? WHERE pk=?", (_j(data), self.clock(), s["pk"]))
            if before != after:
                self._log(c, s["project_pk"], "allocation", {"spec": spec_rid, "before": before, "after": after},
                          actor.name)
            self._touch_project(c, s["project_pk"])
        return self.suggest(project, spec_rid)

    def suggest(self, project: str, spec_rid: str) -> dict:
        spec_rid = _canon(spec_rid)  # one id form at every door, echoed back as stored
        s = self._rung_row(project, spec_rid)
        if s["kind"] != "specification":
            raise RungError(f"{spec_rid} is not a specification", code="bad_request", status=400)
        p = self._project_row(s["project_pk"])
        data = _l(s["data"], {})
        tests = [t for t in self._children_rows(s["pk"]) if t["status"] in ("approved", "stale", "draft")]
        needs, why_human = self._needs_of(s)
        facts = self._facts_for(self._project_facts(p), s["pk"])
        ranked = allocation.rank(facts, data.get("tags", []), needs=needs)
        pick = self._q1("SELECT * FROM picks WHERE spec_pk=? ORDER BY pk DESC LIMIT 1", (s["pk"],))
        excluded = []
        for f in facts:
            why = allocation.reasons(f, needs)
            if why:
                excluded.append({"profile": f.name, "reason": "; ".join(why)})
        return {"spec": spec_rid, "human_only": bool(why_human), "human_only_reason": why_human,
                "required_tools": list(needs.required_tools), "independent": needs.independent,
                "marked_human_only": bool(data.get("human_only")),
                "suggestions": [x.as_dict() for x in ranked], "excluded": excluded,
                "parts_help": dict(allocation.PART_HELP), "independent_help": allocation.INDEPENDENT_HELP,
                "pick": {"profile": pick["profile"], "picked_by": pick["picked_by"], "at": pick["at"]} if pick else None,
                "tests": {"command": sum(1 for t in tests if _l(t["data"], {}).get("type") == "command"),
                          "manual": sum(1 for t in tests if _l(t["data"], {}).get("type") == "manual"),
                          "ai_judged": sum(1 for t in tests if _l(t["data"], {}).get("type") == "ai_judged")}}

    @writes()
    def pick(self, project: str, spec_rid: str, profile: str, actor: Actor = HUMAN) -> dict:
        spec_rid = _canon(spec_rid)  # one id form at every door, echoed back as stored
        if not actor.is_human:
            raise RungError("only a human picks a carrier", code="forbidden", status=403)
        s = self._rung_row(project, spec_rid)
        why = self.exclusion(project, spec_rid, profile)
        if why:
            raise RungError(f"{profile} is not eligible for {spec_rid}: {why}", code="excluded")
        with self._tx() as c:
            c.execute("INSERT INTO picks(spec_pk, profile, picked_by, at) VALUES (?,?,?,?)",
                      (s["pk"], profile, actor.name, self.clock()))
        return self.suggest(project, spec_rid)

    # ------------------------------------------------------------------ develop runs

    @writes()
    def start_run(self, project: str, spec_rid: str, actor: Actor = HUMAN, profile: str | None = None) -> dict:
        """Create a develop run for a specification. The caller launches the runner process. Every check
        and the insert run in one write transaction, so another process cannot start a second run, claim
        the specification or fill the profile's At once in between."""
        spec_rid = _canon(spec_rid)  # one id form at every door, echoed back as stored
        if profile is not None and not isinstance(profile, str):
            raise RungError("agent is a profile name", code="bad_request", status=400, field="agent")
        with self._tx() as c:
            run_pk = self._start_run(c, project, spec_rid, actor, profile)
        return self.run(run_pk)

    def _start_run(self, c, project, spec_rid, actor, profile) -> int:
        s = self._rung_row(project, spec_rid)
        if s["kind"] != "specification":
            raise RungError(f"{spec_rid} is not a specification", code="bad_request", status=400)
        if s["status"] not in ("approved",):
            raise RungError(f"{spec_rid} is {s['status']}; approve it first", code="locked")
        self._require_develop(project, s)
        if self._q1("SELECT 1 FROM runs WHERE spec_pk=? AND status IN ('queued','running')", (s["pk"],)):
            raise RungError(f"{spec_rid} is already running", code="conflict")
        waits = self.blocked_by(s)
        if waits:
            raise RungError(f"{spec_rid} cannot start: {waits}", code="blocked")
        integrating = self.integration_running(c, s["project_pk"])
        if integrating:
            # Integration is judged on one state of the folder (Round 23): no work changes it meanwhile.
            raise RungError(f"milestone check {integrating} is running; start {spec_rid} when it ends", code="busy")
        held = self._q1("SELECT chat, profile FROM claims WHERE spec_pk=? AND status='open' LIMIT 1", (s["pk"],))
        if held is not None:
            raise RungError(f"{spec_rid} is held by {held['chat'] or 'a chat'} ({held['profile']}); release the claim "
                            "first", code="conflict")
        sug = self.suggest(project, spec_rid)
        picked_by = "suggestion"
        if profile:
            why = self.exclusion(project, spec_rid, profile)
            if why:
                raise RungError(f"{profile} is not eligible for {spec_rid}: {why}", code="excluded")
            if actor.is_human and (not sug["pick"] or sug["pick"]["profile"] != profile):
                self.pick(project, spec_rid, profile, actor)
            picked_by = actor.name
        elif sug["pick"] and sug["pick"]["profile"] in [x["profile"] for x in sug["suggestions"]]:
            profile = sug["pick"]["profile"]
            picked_by = sug["pick"]["picked_by"]
        elif sug["suggestions"]:
            profile = sug["suggestions"][0]["profile"]
        else:
            why = "; ".join(f"{x['profile']} {x['reason']}" for x in sug["excluded"])
            raise RungError(f"no eligible profile for {spec_rid}" + (f" ({why})" if why else ""), code="locked")
        # After the filters, so a specification whose tests are all manual names the same reason (human only)
        # here as everywhere else.
        cmd_tests = [t for t in self._children_rows(s["pk"]) if t["status"] == "approved" and
                     _l(t["data"], {}).get("type") == "command"]
        if not cmd_tests:
            raise RungError(f"{spec_rid} has no accepted command test to develop against", code="locked")
        prof = self.profile(profile)
        worker = self.get_setting("worker")
        timeout_s = int(self.get_setting("run_timeout_min")) * 60
        cur = c.execute("INSERT INTO runs(project_pk, spec_pk, profile, picked_by, status, max_attempts, timeout_s, "
                        "worker, created_at) VALUES (?,?,?,?,?,?,?,?,?)",
                        (s["project_pk"], s["pk"], profile, picked_by, "queued", int(prof["max_runs"]), timeout_s,
                         _j(worker), self.clock()))
        self._touch_project(c, s["project_pk"])
        return cur.lastrowid

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
            sug = self.suggest(project, spec_rid)
        except RungError as exc:
            return False, str(exc)
        if not sug["suggestions"]:  # the reason Send would give
            why = "; ".join(f"{x['profile']} {x['reason']}" for x in sug["excluded"])
            return False, f"no eligible profile for {spec_rid}" + (f" ({why})" if why else "")
        return True, ""

    def _run_dict(self, r) -> dict:
        spec = self._rung_by_pk(r["spec_pk"])
        project = self._project_row(r["project_pk"])
        attempts = []
        for a in self._q("SELECT * FROM attempts WHERE run_pk=? ORDER BY n", (r["pk"],)):
            ex = self._q("SELECT e.*, t.rid AS trid FROM executions e JOIN rungs t ON t.pk=e.test_pk "
                         "WHERE e.run_pk=? AND e.attempt=? ORDER BY e.pk", (r["pk"], a["n"]))
            attempts.append({
                "n": a["n"], "status": a["status"], "reason": a["reason"], "files_changed": _l(a["files_changed"], []),
                "commands": _l(a["commands"], []), "worker_output": a["worker_output"], "fed_in": a["fed_in"],
                "fed_forward": a["fed_forward"], "started_at": a["started_at"], "ended_at": a["ended_at"],
                "local": _l(a["local_results"], []) if "local_results" in a.keys() else [],
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
                "coverage": self._req_coverage(self._rung_by_pk(spec["parent_pk"])),
                "workspace": self.workspace_changes(r["pk"]) if self._workspace(r).get("path") else None}

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
        """One transaction: the flag, and a run not started yet recorded cancelled. The runner starts a run
        only while it is still queued and not cancelled (start_running), so a cancel before start sticks."""
        with self._tx() as c:
            row = c.execute("SELECT status, project_pk FROM runs WHERE pk=?", (int(run_id),)).fetchone()
            if row is not None and row["status"] in LIVE_RUN:
                c.execute("UPDATE runs SET cancel=1 WHERE pk=?", (int(run_id),))
                c.execute("UPDATE runs SET status='cancelled', ended_at=?, reason='cancelled before start' "
                          "WHERE pk=? AND status='queued'", (self.clock(), int(run_id)))
                self._touch_project(c, row["project_pk"])
        return self.run(run_id)

    def start_running(self, run_id: int, started_at: float, pid: int) -> bool:
        """Queued to running, only if the run is still queued and nobody cancelled it."""
        with self._tx() as c:
            cur = c.execute("UPDATE runs SET status='running', started_at=?, pid=? WHERE pk=? AND status='queued' "
                            "AND cancel=0", (started_at, pid, int(run_id)))
            return bool(cur.rowcount)

    def finish_run(self, run_id: int, final: str, reason: str, commit_ref, last_attempt: int | None) -> None:
        """The run's end, in one transaction with the cancel flag: a cancel accepted while the run was still
        running wins over the result the runner reached, and the attempt it ended is recorded cancelled."""
        with self._tx() as c:
            row = c.execute("SELECT status, cancel, project_pk FROM runs WHERE pk=?", (int(run_id),)).fetchone()
            if row is None or row["status"] not in LIVE_RUN:
                return
            if row["cancel"] and final != "cancelled":
                final, reason = "cancelled", "cancelled"
                if last_attempt is not None:
                    c.execute("UPDATE attempts SET status='cancelled' WHERE run_pk=? AND n=? AND status IN "
                              "('pass','fail','no_change','error','running')", (int(run_id), last_attempt))
            c.execute("UPDATE runs SET status=?, ended_at=?, reason=?, commit_ref=?, pid=NULL WHERE pk=?",
                      (final, self.clock(), reason, commit_ref, int(run_id)))
            self._touch_project(c, row["project_pk"])

    def run_cancelled(self, run_id: int) -> bool:
        r = self._q1("SELECT cancel FROM runs WHERE pk=?", (int(run_id),))
        return bool(r and r["cancel"])

    def begin_attempt(self, run_id: int, n: int, prompt: str, fed_in: str) -> None:
        with self._tx() as c:
            c.execute("INSERT INTO attempts(run_pk, n, status, prompt, fed_in, started_at) VALUES (?,?,?,?,?,?)",
                      (int(run_id), n, "running", prompt, fed_in, self.clock()))

    def end_attempt(self, run_id: int, n: int, status: str, files_changed, commands, worker_output: str,
                    fed_forward: str = "", reason: str = "") -> None:
        if status not in ATTEMPT_OUTCOMES:
            raise ValueError(f"attempt outcome {status} unknown")
        with self._tx() as c:
            c.execute("UPDATE attempts SET status=?, files_changed=?, commands=?, worker_output=?, fed_forward=?, "
                      "reason=?, ended_at=? WHERE run_pk=? AND n=?",
                      (status, _j(files_changed), _j(commands), worker_output[-20000:], fed_forward, reason or "",
                       self.clock(), int(run_id), n))

    def update_attempt(self, run_id: int, n: int, **fields) -> None:
        allowed = {"files_changed", "commands", "worker_output"}
        vals = {k: (_j(v) if k != "worker_output" else v) for k, v in fields.items() if k in allowed}
        if not vals:
            return
        cols = ", ".join(f"{k} = ?" for k in vals)
        with self._tx() as c:
            c.execute(f"UPDATE attempts SET {cols} WHERE run_pk=? AND n=?", (*vals.values(), int(run_id), n))

    def interrupt_run(self, run_id: int, reason: str, attempts=("running",)) -> None:
        """End a run nobody cancelled and nobody finished: Unknown, never Pass, Fail or Cancelled."""
        now = self.clock()
        self.set_run(run_id, status="unknown", ended_at=now, reason=reason, cancel=0)
        marks = ",".join("?" * len(attempts))
        with self._tx() as c:
            c.execute(f"UPDATE attempts SET status='unknown', reason=?, ended_at=? WHERE run_pk=? AND status IN ({marks})",
                      (reason, now, int(run_id), *attempts))
            c.execute("UPDATE executions SET status='error', ended_at=? WHERE run_pk=? AND status='running'",
                      (now, int(run_id)))

    def reconcile_runs(self, alive) -> list[int]:
        """Mark runs whose runner process is gone as interrupted. `alive(pid)` checks a pid."""
        out = []
        for r in self._q("SELECT * FROM runs WHERE status='running'"):
            if not r["pid"] or not alive(r["pid"]):
                self.interrupt_run(r["pk"], "the runner process ended")
                out.append(r["pk"])
        # A queued run whose runner died before starting, or never got one, would block its specification forever.
        for r in self._q("SELECT * FROM runs WHERE status='queued'"):
            if (r["pid"] and not alive(r["pid"])) or (not r["pid"] and self.clock() - r["created_at"] > QUEUED_GRACE_S):
                self.interrupt_run(r["pk"], "the runner never started", attempts=("queued", "running"))
                out.append(r["pk"])
        return out

    def command_tests(self, project: str, spec_rid: str) -> list[dict]:
        s = self._rung_row(project, spec_rid)
        return [self._rung_dict(t) for t in self._children_rows(s["pk"])
                if t["status"] == "approved" and _l(t["data"], {}).get("type") == "command"]

    # ------------------------------------------------------------------ defects

    @writes()
    def raise_defect(self, project: str, test_rid: str, executions: list[int], title: str, note: str = "",
                     actor: Actor = HUMAN, category: str = "Implementation") -> dict:
        """Only ever called by a human press. Links the test, its specification and the chosen runs."""
        if not actor.is_human:
            raise RungError("defects are raised by a human", code="forbidden", status=403)
        t = self._rung_row(project, test_rid)
        if t["kind"] != "test":
            raise RungError(f"{test_rid} is not a test", code="bad_request", status=400)
        title = (title or "").strip()
        if not title:
            raise RungError("title is required", code="bad_request", status=400)
        if any(not _is_int(n) for n in executions or []):
            raise RungError("executions are numbers such as 3", code="bad_request", status=400, field="executions")
        ns = sorted({int(n) for n in executions or []})
        if not ns:
            raise RungError("link at least one execution", code="bad_request", status=400)
        for n in ns:
            ex = self._q1("SELECT status FROM executions WHERE test_pk=? AND n=?", (t["pk"], n))
            if not ex:
                raise NotFound(f"no execution #{n} of {test_rid}")
            if ex["status"] != "fail":
                raise RungError(f"#{n} of {test_rid} is {ex['status']}; a defect links failed runs only",
                                code="bad_request", status=400)
        with self._tx() as c:
            k = c.execute("SELECT COUNT(*)+1 FROM defects WHERE project_pk=?", (t["project_pk"],)).fetchone()[0]
            did = f"D-{k}"
            if category not in DEFECT_CATEGORIES:
                raise RungError(f"category {category} unknown", code="bad_request", status=400)
            c.execute("INSERT INTO defects(project_pk, did, title, note, category, test_pk, spec_pk, executions, "
                      "created_by, at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                      (t["project_pk"], did, title, (note or "").strip(), category, t["pk"], t["parent_pk"], _j(ns),
                       actor.name, self.clock()))
            self._touch_project(c, t["project_pk"])
        return self.defect(project, did)

    def defect(self, project: str, did: str) -> dict:
        p = self._project_row(project)
        d = self._q1("SELECT * FROM defects WHERE project_pk=? AND did=?", (p["pk"], did))
        if not d:
            raise NotFound(f"no defect {did}")
        return {"id": d["did"], "title": d["title"], "note": d["note"], "category": d["category"],
                "test": self._rid_of(d["test_pk"]),
                "spec": self._rid_of(d["spec_pk"]), "executions": _l(d["executions"], []),
                "created_by": d["created_by"], "at": d["at"]}

    def defects(self, project: str) -> list[dict]:
        p = self._project_row(project)
        return [self.defect(project, d["did"]) for d in self._q("SELECT did FROM defects WHERE project_pk=? ORDER BY pk",
                                                                  (p["pk"],))]
