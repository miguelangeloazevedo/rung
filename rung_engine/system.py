# pyright: reportAttributeAccessIssue=false
"""System controls beyond one specification (decisions Round 24, SYS-02 onward). A mixin of `Engine`.

Architecture baseline (SYS-02): a project holds components (name, responsibility, paths) and contracts (kind,
producer, consumers, artifact paths, text). Each is versioned: a change is a new draft version a person approves;
approved versions stay in history. Specifications and milestones name the components they touch. Approving a
changed contract (version 2 onward) makes every specification and milestone touching its producer or consumers
Out of date (`contract_changed`) until it is checked again (a specification) or approved again (a milestone).

Dependencies (SYS-03): a specification may require other specifications to be verified first. The edge is kept
on the specification's data, separate from the ladder. Cycles, self edges, unknown ids and ids of another project
are refused, naming the path. A develop run whose prerequisite is not verified is refused with the blocked path.

Isolated runs (SYS-05, B12): with the project's run mode Isolated, a develop run works in its own copy of the
project files (the basis: .gitignore and .rungignore apply). Its test results are local: kept on the attempt,
never an execution of the project, so nothing it does counts until it is integrated. Integrating applies the
run's changed files to the project folder when none of them changed there since the copy was made; otherwise it
is refused, naming the files, with nothing applied. After integration the run's specification and every test
the change made out of date are checked on the project folder.

The plan (SYS-04): every approved specification in scope with its state now (Verified, Running, Blocked by a
prerequisite, Ready to start, or Not ready: tests not approved); `Start ready work` starts only the Ready ones.
An optional budget counts the attempts of the runs the plan started; once used, the plan starts nothing more and
says so. Model usage is reported only when a worker reports it; otherwise it reads unavailable.

Contract checks (SYS-06): a contract carries checks, commands an agent may propose and a person approves, run
on the project folder against the producer's real output. Each result records the contract version and the code
basis. A check's state is Satisfied only for a pass on the current contract version and the current code; a
result from an older version or other code is Out of date; a failure is Failed. A milestone touching the
producer or a consumer is blocked by any approved check that is not Satisfied.

Change impact (SYS-11): a specification or milestone that names components with declared paths judges its
evidence on those paths plus the files outside every component, so a change elsewhere leaves its evidence
current, and a change inside them makes it out of date. Without components, or with components that declare
no paths, the whole project is the basis. `Check everything` reruns every check regardless.

Pure engine computation; no model call.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from . import evidence

KINDS = ("component", "contract")
CONTRACT_KINDS = ("api", "event", "file", "schema", "cli", "other")
WORDS = {"verified": "Verified", "failed": "Failed", "out_of_date": "Out of date", "could_not_verify":
         "Could not verify", "checking": "Checking", "awaiting_manual": "Awaiting manual check", "contract":
         "Not approved", "unverified": "Not verified"}


def _j(x):
    return json.dumps(x, sort_keys=True)


def _l(x, default=None):
    try:
        return json.loads(x) if x else default
    except (TypeError, ValueError):
        return default


def _names(v, field):
    from .core import RungError
    if v is None:
        return []
    if not isinstance(v, list) or not all(isinstance(x, str) for x in v):
        raise RungError(f"{field} is a list of names", code="bad_request", status=400, field=field)
    out = []
    for x in v:
        x = x.strip()
        if x and x not in out:
            out.append(x)
    return out


class SystemMixin:
    # ------------------------------------------------------------------ architecture (SYS-02)

    def _arch_row(self, project_pk: int, kind: str, name: str):
        return self._q1("SELECT * FROM arch WHERE project_pk=? AND kind=? AND name=?", (project_pk, kind, name))

    def _arch_versions(self, arch_pk: int):
        return self._q("SELECT * FROM arch_versions WHERE arch_pk=? ORDER BY version", (arch_pk,))

    def _arch_current(self, arch_pk: int):
        return self._q1("SELECT * FROM arch_versions WHERE arch_pk=? AND status='approved' ORDER BY version DESC LIMIT 1",
                        (arch_pk,))

    def _arch_fields(self, project_pk: int, kind: str, f: dict, base: dict) -> dict:
        from .core import RungError
        d = dict(base)
        if kind == "component":
            for k in ("responsibility",):
                if k in f:
                    d[k] = str(f.get(k) or "").strip()
            if "paths" in f:
                d["paths"] = [p.strip().strip("/") for p in _names(f.get("paths"), "paths") if p.strip().strip("/")]
                for p in d["paths"]:
                    if p.startswith("..") or p.startswith("/") or "/../" in f"/{p}/":
                        raise RungError(f"{p} is outside the project", code="bad_request", status=400, field="paths")
            d.setdefault("responsibility", "")
            d.setdefault("paths", [])
        else:
            if "kind" in f:
                d["kind"] = str(f.get("kind") or "other").strip() or "other"
                if d["kind"] not in CONTRACT_KINDS:
                    raise RungError(f"a contract kind is one of {', '.join(CONTRACT_KINDS)}", code="bad_request",
                                    status=400, field="kind")
            if "producer" in f:
                d["producer"] = str(f.get("producer") or "").strip()
            if "consumers" in f:
                d["consumers"] = _names(f.get("consumers"), "consumers")
            if "artifacts" in f:
                d["artifacts"] = _names(f.get("artifacts"), "artifacts")
            if "text" in f:
                d["text"] = str(f.get("text") or "").strip()
            d.setdefault("kind", "other")
            d.setdefault("producer", "")
            d.setdefault("consumers", [])
            d.setdefault("artifacts", [])
            d.setdefault("text", "")
            known = {r["name"] for r in self._q("SELECT name FROM arch WHERE project_pk=? AND kind='component'",
                                               (project_pk,))}
            for who in [d["producer"], *d["consumers"]]:
                if not who:
                    raise RungError("a contract names its producer and at least one consumer", code="bad_request",
                                    status=400, field="producer")
                if who not in known:
                    raise RungError(f"no component {who}", code="bad_request", status=400, field="producer")
            if not d["consumers"]:
                raise RungError("a contract names at least one consumer", code="bad_request", status=400,
                                field="consumers")
        return d

    def save_arch(self, project: str, kind: str, name: str, fields: dict, actor=None) -> dict:
        """Create a component or contract, or write a new draft version of it. A draft changes nothing until a
        person approves it."""
        from .core import HUMAN, RungError
        actor = actor or HUMAN
        if not actor.is_human:
            raise RungError("only a human changes the architecture", code="forbidden", status=403)
        if kind not in KINDS:
            raise RungError("kind is component or contract", code="bad_request", status=400, field="kind")
        name = str(name or "").strip()
        if not name or len(name) > 80:
            raise RungError("a name is 1 to 80 characters", code="bad_request", status=400, field="name")
        if not isinstance(fields, dict):
            raise RungError("fields is an object", code="bad_request", status=400)
        with self._lock:
            self._check_writable(project, None)
            p = self._project_row(project)
            row = self._arch_row(p["pk"], kind, name)
            now = self.clock()
            if row is None:
                data = self._arch_fields(p["pk"], kind, fields, {})
                with self._tx() as c:
                    c.execute("INSERT INTO arch(project_pk, kind, name, created_at) VALUES (?,?,?,?)",
                              (p["pk"], kind, name, now))
                    apk = c.execute("SELECT pk FROM arch WHERE project_pk=? AND kind=? AND name=?",
                                    (p["pk"], kind, name)).fetchone()[0]
                    c.execute("INSERT INTO arch_versions(arch_pk, version, data, status, by_name, created_at) "
                              "VALUES (?,?,?,?,?,?)", (apk, 1, _j(data), "draft", actor.name, now))
                    self._log(c, p["pk"], "arch_created", {"kind": kind, "name": name}, actor.name)
                    self._touch_project(c, p["pk"])
            else:
                vs = self._arch_versions(row["pk"])
                last = vs[-1]
                data = self._arch_fields(p["pk"], kind, fields, _l(last["data"], {}))
                if data == _l(last["data"], {}) and last["status"] in ("draft", "approved"):
                    return self.arch_item(project, kind, name)
                with self._tx() as c:
                    if last["status"] == "draft":
                        c.execute("UPDATE arch_versions SET data=?, by_name=?, created_at=? WHERE pk=?",
                                  (_j(data), actor.name, now, last["pk"]))
                    else:
                        c.execute("INSERT INTO arch_versions(arch_pk, version, data, status, by_name, created_at) "
                                  "VALUES (?,?,?,?,?,?)", (row["pk"], last["version"] + 1, _j(data), "draft",
                                                           actor.name, now))
                    self._log(c, p["pk"], "arch_revised", {"kind": kind, "name": name}, actor.name)
                    self._touch_project(c, p["pk"])
        return self.arch_item(project, kind, name)

    def approve_arch(self, project: str, kind: str, name: str, actor=None) -> dict:
        """Approve the draft version. Earlier approved versions stay as history. A changed contract returns the
        specifications and milestones it puts out of date."""
        from .core import HUMAN, RungError
        actor = actor or HUMAN
        if not actor.is_human:
            raise RungError("only a human approves the architecture", code="forbidden", status=403)
        with self._lock:
            self._check_writable(project, None)
            p = self._project_row(project)
            row = self._arch_row(p["pk"], kind, str(name or "").strip())
            if row is None:
                raise RungError(f"no {kind} {name}", code="not_found", status=404)
            last = self._arch_versions(row["pk"])[-1]
            if last["status"] != "draft":
                raise RungError(f"{kind} {name} has no draft to approve", code="conflict", status=409)
            now = self.clock()
            with self._tx() as c:
                c.execute("UPDATE arch_versions SET status='superseded' WHERE arch_pk=? AND status='approved'",
                          (row["pk"],))
                c.execute("UPDATE arch_versions SET status='approved', approved_by=?, approved_at=? WHERE pk=?",
                          (actor.name, now, last["pk"]))
                self._log(c, p["pk"], "arch_approved", {"kind": kind, "name": row["name"], "version": last["version"]},
                          actor.name)
                self._touch_project(c, p["pk"])
        out = self.arch_item(project, kind, row["name"])
        out["affected"] = self.contract_affected(project, row["name"]) if kind == "contract" and last["version"] > 1 \
            else {"specifications": [], "milestones": []}
        return out

    def _arch_dict(self, row) -> dict:
        vs = self._arch_versions(row["pk"])
        cur = next((v for v in reversed(vs) if v["status"] == "approved"), None)
        draft = vs[-1] if vs and vs[-1]["status"] == "draft" else None

        def vd(v):
            return {"version": v["version"], "status": v["status"], "by": v["by_name"], "approved_by": v["approved_by"],
                    "approved_at": v["approved_at"], "created_at": v["created_at"], **_l(v["data"], {})}
        return {"kind": row["kind"], "name": row["name"], "current": vd(cur) if cur else None,
                "draft": vd(draft) if draft else None, "history": [vd(v) for v in vs]}

    def arch_item(self, project: str, kind: str, name: str) -> dict:
        from .core import RungError
        p = self._project_row(project)
        row = self._arch_row(p["pk"], kind, str(name or "").strip())
        if row is None:
            raise RungError(f"no {kind} {name}", code="not_found", status=404)
        return self._arch_dict(row)

    def architecture(self, project: str) -> dict:
        p = self._project_row(project)
        rows = self._q("SELECT * FROM arch WHERE project_pk=? ORDER BY kind, name", (p["pk"],))
        comps = [self._arch_dict(r) for r in rows if r["kind"] == "component"]
        cons = []
        for r in rows:
            if r["kind"] == "contract":
                d = self._arch_dict(r)
                d["affected"] = self.contract_affected(project, r["name"])
                d["checks"] = self.contract_checks(project, r["name"], fresh=False)  # SYS-06
                cons.append(d)
        return {"components": comps, "contracts": cons}

    def _approved_components(self, project_pk: int) -> dict:
        out = {}
        for r in self._q("SELECT * FROM arch WHERE project_pk=? AND kind='component'", (project_pk,)):
            cur = self._arch_current(r["pk"])
            if cur is not None:
                out[r["name"]] = _l(cur["data"], {})
        return out

    def _component_names(self, project_pk: int, names, field="components") -> list[str]:
        from .core import RungError
        names = _names(names, field)
        known = self._approved_components(project_pk)
        for n in names:
            if n not in known:
                raise RungError(f"no approved component {n}", code="bad_request", status=400, field=field)
        return names

    def set_spec_components(self, project: str, rid: str, components, actor=None) -> dict:
        """The components a specification touches. A person's setting; no new version of the text."""
        from .core import HUMAN, RungError, _canon
        actor = actor or HUMAN
        if not actor.is_human:
            raise RungError("only a human names a specification's components", code="forbidden", status=403)
        with self._lock:
            self._check_writable(project, None)
            s = self._rung_row(project, _canon(rid))
            if s["kind"] != "specification":
                raise RungError(f"{s['rid']} is not a specification", code="bad_request", status=400)
            names = self._component_names(s["project_pk"], components)
            data = _l(s["data"], {})
            if data.get("components", []) == names:
                return self.rung(project, s["rid"])
            data["components"] = names
            with self._tx() as c:
                c.execute("UPDATE rungs SET data=?, updated_at=? WHERE pk=?", (_j(data), self.clock(), s["pk"]))
                self._log(c, s["project_pk"], "components_set", {"spec": s["rid"], "components": names}, actor.name)
                self._touch_project(c, s["project_pk"])
        return self.rung(project, s["rid"])

    def _contract_changes(self, project_pk: int, components) -> list[dict]:
        """Approved changes (version 2 onward) of contracts whose producer or consumers include one of these
        components, newest approval per contract."""
        comps = set(components or [])
        if not comps:
            return []
        out = []
        for r in self._q("SELECT * FROM arch WHERE project_pk=? AND kind='contract'", (project_pk,)):
            cur = self._arch_current(r["pk"])
            if cur is None or cur["version"] < 2:
                continue
            d = _l(cur["data"], {})
            if comps & ({d.get("producer")} | set(d.get("consumers", []))):
                out.append({"contract": r["name"], "version": cur["version"], "at": cur["approved_at"]})
        return out

    def contract_affected(self, project: str, name: str) -> dict:
        p = self._project_row(project)
        row = self._arch_row(p["pk"], "contract", name)
        cur = self._arch_current(row["pk"]) if row else None
        latest = _l((cur or (self._arch_versions(row["pk"])[-1] if row else None) or {"data": "{}"})["data"], {})
        comps = {latest.get("producer")} | set(latest.get("consumers", []))
        specs = []
        for s in self._q("SELECT * FROM rungs WHERE project_pk=? AND kind='specification' AND status IN "
                         "('approved','stale','draft') ORDER BY pk", (p["pk"],)):
            if comps & set(_l(s["data"], {}).get("components", [])):
                specs.append(s["rid"])
        ms = [m["mid"] for m in self._q("SELECT * FROM milestones WHERE project_pk=? ORDER BY num", (p["pk"],))
              if comps & set(_l(m["system"], {}).get("components", []))]
        return {"specifications": specs, "milestones": ms}

    def _spec_contract_blockers(self, spec) -> list[dict]:
        """A specification checked before an approved contract change is out of date until its tests run again."""
        changes = self._contract_changes(spec["project_pk"], _l(spec["data"], {}).get("components", []))
        if not changes:
            return []
        out = []
        tests = [t for t in self._children_rows(spec["pk"]) if t["status"] in ("approved", "stale")]
        for ch in changes:
            stale = []
            for t in tests:
                if _l(t["data"], {}).get("type") == "manual":
                    continue
                e = self._q1("SELECT ended_at FROM executions WHERE test_pk=? AND status IN ('pass','fail') "
                             "ORDER BY seq DESC LIMIT 1", (t["pk"],))
                if e is not None and (e["ended_at"] or 0) < ch["at"]:
                    stale.append(t["rid"])
            if stale:
                out.append({"code": "contract_changed", "contract": ch["contract"],
                            "text": f"contract {ch['contract']} v{ch['version']} was approved after "
                                    f"{', '.join(stale)} last ran", "test": stale[0]})
        return out

    # ------------------------------------------------------------------ dependencies (SYS-03)

    def _requires(self, spec) -> list[str]:
        return list(_l(spec["data"], {}).get("requires", []))

    def _dep_path(self, project_pk: int, start: str, goal: str) -> list[str] | None:
        """A path start -> ... -> goal along `requires` edges, or None."""
        seen, stack = set(), [(start, [start])]
        while stack:
            rid, path = stack.pop()
            if rid == goal:
                return path
            if rid in seen:
                continue
            seen.add(rid)
            r = self._q1("SELECT * FROM rungs WHERE project_pk=? AND rid=?", (project_pk, rid))
            for nxt in self._requires(r) if r is not None else []:
                stack.append((nxt, path + [nxt]))
        return None

    def add_dependency(self, project: str, rid: str, requires: str, actor=None) -> dict:
        from .core import HUMAN, NotFound, RungError, _canon
        actor = actor or HUMAN
        if not actor.is_human:
            raise RungError("only a human adds a dependency", code="forbidden", status=403)
        raw = str(requires or "").strip()
        if ":" in raw or "/" in raw:
            raise RungError(f"{raw} is in another project; a dependency stays inside {project}", code="bad_request",
                            status=400, field="requires")
        with self._lock:
            self._check_writable(project, None)
            s = self._rung_row(project, _canon(rid))
            try:
                t = self._rung_row(project, _canon(raw))
            except NotFound:
                raise RungError(f"no specification {raw} in {project}", code="bad_request", status=400,
                                field="requires") from None
            for r in (s, t):
                if r["kind"] != "specification":
                    raise RungError(f"{r['rid']} is not a specification", code="bad_request", status=400,
                                    field="requires")
            if s["pk"] == t["pk"]:
                raise RungError(f"{s['rid']} cannot require itself", code="bad_request", status=400, field="requires")
            back = self._dep_path(s["project_pk"], t["rid"], s["rid"])
            if back:
                raise RungError("a cycle: " + " requires ".join([s["rid"], *back]), code="cycle", status=400,
                                field="requires")
            data = _l(s["data"], {})
            req = list(data.get("requires", []))
            if t["rid"] not in req:
                req.append(t["rid"])
                data["requires"] = req
                with self._tx() as c:
                    c.execute("UPDATE rungs SET data=?, updated_at=? WHERE pk=?", (_j(data), self.clock(), s["pk"]))
                    self._log(c, s["project_pk"], "dependency_added", {"spec": s["rid"], "requires": t["rid"]},
                              actor.name)
                    self._touch_project(c, s["project_pk"])
        return self.dependencies(project, s["rid"])

    def remove_dependency(self, project: str, rid: str, requires: str, actor=None) -> dict:
        from .core import HUMAN, RungError, _canon
        actor = actor or HUMAN
        if not actor.is_human:
            raise RungError("only a human removes a dependency", code="forbidden", status=403)
        with self._lock:
            self._check_writable(project, None)
            s = self._rung_row(project, _canon(rid))
            data = _l(s["data"], {})
            req = [x for x in data.get("requires", []) if x != _canon(str(requires or ""))]
            if req != data.get("requires", []):
                data["requires"] = req
                with self._tx() as c:
                    c.execute("UPDATE rungs SET data=?, updated_at=? WHERE pk=?", (_j(data), self.clock(), s["pk"]))
                    self._log(c, s["project_pk"], "dependency_removed", {"spec": s["rid"], "requires": requires},
                              actor.name)
                    self._touch_project(c, s["project_pk"])
        return self.dependencies(project, s["rid"])

    def dependencies(self, project: str, rid: str) -> dict:
        from .core import _canon
        s = self._rung_row(project, _canon(rid))
        req = []
        for x in self._requires(s):
            r = self._q1("SELECT * FROM rungs WHERE project_pk=? AND rid=?", (s["project_pk"], x))
            v = self._verify(r) if r is not None else None
            req.append({"id": x, "text": r["text"] if r else "", "verification": v["verification"] if v else "missing",
                        "ok": bool(v and v["ok"])})
        by = [r["rid"] for r in self._q("SELECT * FROM rungs WHERE project_pk=? AND kind='specification' "
                                         "AND status NOT IN ('dismissed') ORDER BY pk", (s["project_pk"],))
              if s["rid"] in self._requires(r)]
        return {"spec": s["rid"], "requires": req, "required_by": by}

    def blocked_by(self, spec) -> str | None:
        """Why a develop run of this specification cannot start yet: the first prerequisite not verified, with
        the path to it (`S-3.1 waits for S-2.1: Failed`)."""
        seen = set()

        def walk(r, path):
            for x in self._requires(r):
                if x in seen:
                    continue
                seen.add(x)
                pre = self._q1("SELECT * FROM rungs WHERE project_pk=? AND rid=?", (r["project_pk"], x))
                if pre is None:
                    return f"{' waits for '.join(path + [x])}: missing"
                v = self._verify(pre)
                if not v["ok"]:
                    return f"{' waits for '.join(path + [x])}: {WORDS.get(v['verification'], v['verification'])}"
                deeper = walk(pre, path + [x])
                if deeper:
                    return deeper
            return None
        return walk(spec, [spec["rid"]])

    # ------------------------------------------------------------------ isolated runs (SYS-05, B12)

    RUN_MODES = ("shared", "isolated")

    def set_run_mode(self, project: str, mode: str, actor=None) -> dict:
        from .core import HUMAN, RungError
        actor = actor or HUMAN
        if not actor.is_human:
            raise RungError("only a human sets how runs work", code="forbidden", status=403)
        if mode not in self.RUN_MODES:
            raise RungError("run mode is shared or isolated", code="bad_request", status=400, field="mode")
        self._check_writable(project, None)
        p = self._project_row(project)
        with self._tx() as c:
            c.execute("UPDATE projects SET run_mode=? WHERE pk=?", (mode, p["pk"]))
            self._log(c, p["pk"], "run_mode_set", {"mode": mode}, actor.name)
            self._touch_project(c, p["pk"])
        return {"mode": mode}

    def run_mode(self, project: str) -> str:
        p = self._project_row(project)
        return (p["run_mode"] if "run_mode" in p.keys() else "shared") or "shared"

    def _workspace(self, run_row) -> dict:
        return _l(run_row["workspace"], {}) if "workspace" in run_row.keys() else {}

    def prepare_workspace(self, run_id: int) -> Path | None:
        """For an isolated run: copy the project's files into the run's own folder and record what was copied.
        Returns the folder the run works in, or None for a shared run."""
        r = self._q1("SELECT * FROM runs WHERE pk=?", (int(run_id),))
        ws = self._workspace(r)
        if ws.get("path"):
            return Path(ws["path"])
        p = self._project_row(r["project_pk"])
        if (p["run_mode"] if "run_mode" in p.keys() else "shared") != "isolated":
            return None
        root = Path(p["folder"]).expanduser()
        base = evidence.manifest(root) or {}
        dest = Path(self.path).expanduser().resolve().parent / "workspaces" / f"{p['name']}-run-{r['pk']}"
        if dest.exists():
            shutil.rmtree(dest)
        for rel in base:
            (dest / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(root / rel, dest / rel)
        dest.mkdir(parents=True, exist_ok=True)
        if (root / ".gitignore").is_file() and not (dest / ".gitignore").exists():
            shutil.copy2(root / ".gitignore", dest / ".gitignore")
        evidence.forget(dest)
        ws = {"path": str(dest), "base": base, "created_at": self.clock()}
        with self._tx() as c:
            c.execute("UPDATE runs SET workspace=? WHERE pk=?", (_j(ws), r["pk"]))
        return dest

    def run_local(self, project: str, test_rid: str, root: Path, should_cancel=None, env=None) -> dict:
        """Run an approved command test in a run's workspace. The result is local: returned, never stored as an
        execution, so it cannot count for the project."""
        from .core import RungError
        from .execute import run_command
        t = self._rung_row(project, test_rid)
        data = _l(t["data"], {})
        if data.get("type") == "manual":
            raise RungError("a manual test is recorded by a human, not run", code="bad_request", status=400)
        root = Path(root)
        folder = root / data.get("folder", ".")
        moved = self._protected_change(t, data, root, folder) if folder.is_dir() else []
        if not folder.is_dir():
            return {"test": t["rid"], "status": "error", "exit_code": None, "output": f"folder not found: {folder}",
                    "command": data.get("command", ""), "local": True}
        res = run_command(data.get("command", ""), folder, timeout=data.get("timeout", 120),
                          output_limit=data.get("output_limit", 64000), should_cancel=should_cancel, env=env)
        if res.cancelled:
            status = "cancelled"
        elif res.timed_out or res.launch_error or res.exit_code in (126, 127):
            status = "error"
        else:
            status = "pass" if self._passes(data.get("pass_rule") or {"kind": "exit_code", "value": 0}, res.exit_code,
                                            res.output) else "fail"
        out = {"test": t["rid"], "status": status, "exit_code": res.exit_code, "output": res.output,
               "command": data.get("command", ""), "local": True}
        if moved and status in ("pass", "fail", "error"):
            out["reason"] = "verification_changed"
            out["output"] = ("not run: judged by files changed since the test was approved: "
                             + ", ".join(f"{x['path']} ({x['change']})" for x in moved))
        return out

    def record_local(self, run_id: int, n: int, results: list) -> None:
        with self._tx() as c:
            c.execute("UPDATE attempts SET local_results=? WHERE run_pk=? AND n=?",
                      (_j([{k: v for k, v in r.items() if k != "output"} | {"output": (r.get("output") or "")[-4000:]}
                           for r in results]), int(run_id), int(n)))

    def workspace_changes(self, run_id: int) -> dict:
        """What an isolated run changed against its copy, and which of those files changed in the project since."""
        r = self._q1("SELECT * FROM runs WHERE pk=?", (int(run_id),))
        ws = self._workspace(r)
        if not ws.get("path"):
            return {"isolated": False}
        base = ws.get("base", {})
        now = evidence.manifest(ws["path"]) or {}
        changed = sorted(f for f in set(base) | set(now) if base.get(f) != now.get(f))
        root = Path(self._project_row(r["project_pk"])["folder"]).expanduser()
        conflicts = [f for f in changed if evidence.file_sha(root / f) != base.get(f)
                     and evidence.file_sha(root / f) != now.get(f)]
        return {"isolated": True, "path": ws["path"], "changed": changed, "conflicts": conflicts,
                "integrated_at": ws.get("integrated_at"), "integrated_by": ws.get("integrated_by")}

    def integrate_run(self, project: str, run_id: int, actor=None, carried_by: str = "engine") -> dict:
        """Apply an isolated run's changes to the project folder. Refused, with nothing applied, when one of its
        files changed in the project since the copy; then the affected specifications are checked there."""
        from .core import HUMAN, RungError
        actor = actor or HUMAN
        if not actor.is_human:
            raise RungError("only a human integrates a run", code="forbidden", status=403)
        with self._lock:
            self._check_writable(project, None)
            r = self._q1("SELECT * FROM runs WHERE pk=?", (int(run_id),))
            if r is None or r["project_pk"] != self._project_row(project)["pk"]:
                raise RungError(f"no run {run_id} in {project}", code="not_found", status=404)
            ws = self._workspace(r)
            if not ws.get("path"):
                raise RungError(f"run {run_id} worked in the project folder; there is nothing to integrate",
                                code="bad_request", status=400)
            if ws.get("integrated_at"):
                raise RungError(f"run {run_id} is already integrated", code="conflict", status=409)
            if r["status"] in ("queued", "running"):
                raise RungError(f"run {run_id} is still running", code="busy", status=409)
            with self._tx() as c:
                busy = self._busy_folder(c, r["project_pk"])
            if busy:
                raise RungError(f"run {run_id} cannot be integrated now: {busy}", code="busy", status=409)
            ch = self.workspace_changes(run_id)
            if ch["conflicts"]:
                raise RungError(f"run {run_id} conflicts with the project folder: " + ", ".join(ch["conflicts"])
                                + " changed there since the run started; nothing was applied", code="conflict",
                                status=409, field="files")
            root = Path(self._project_row(r["project_pk"])["folder"]).expanduser()
            src = Path(ws["path"])
            for rel in ch["changed"]:
                if (src / rel).is_file():
                    (root / rel).parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src / rel, root / rel)
                elif (root / rel).is_file():
                    (root / rel).unlink()
            evidence.forget(root)
            ws.update({"integrated_at": self.clock(), "integrated_by": actor.name, "applied": ch["changed"]})
            with self._tx() as c:
                c.execute("UPDATE runs SET workspace=? WHERE pk=?", (_j(ws), r["pk"]))
                self._log(c, r["project_pk"], "run_integrated", {"run": r["pk"], "files": ch["changed"]}, actor.name)
                self._touch_project(c, r["project_pk"])
        spec = self._rung_by_pk(r["spec_pk"])
        checked = []
        for t in self.command_tests(project, spec["rid"]):
            checked.append(self.run_test(project, t["id"], carried_by=carried_by))
        checked += self.recheck(project, carried_by=carried_by, skip=tuple(x["test"] for x in checked if "test" in x))
        return {"run": r["pk"], "applied": ch["changed"], "checked": [{"test": x.get("test"), "status": x.get("status")}
                                                                      for x in checked],
                "verification": self.verification(project, spec["rid"], fresh=True)["verification"]}

    # ------------------------------------------------------------------ the plan (SYS-04)

    def _plan_row(self, p) -> dict:
        return (_l(p["plan"], {}) if "plan" in p.keys() else {}) or {}

    def set_plan_budget(self, project: str, attempts, actor=None, minutes=None) -> dict:
        """A budget of attempts and/or elapsed minutes (SYS-13). Setting one starts counting afresh."""
        from .core import HUMAN, RungError
        actor = actor or HUMAN
        if not actor.is_human:
            raise RungError("only a human sets the plan's budget", code="forbidden", status=403)
        for val, field, unit in ((attempts, "attempts", "attempts"), (minutes, "minutes", "minutes")):
            if val is not None and (not isinstance(val, int) or isinstance(val, bool) or val < 1):
                raise RungError(f"the budget is a whole number of {unit}, or none", code="bad_request", status=400,
                                field=field)
        self._check_writable(project, None)
        p = self._project_row(project)
        plan = self._plan_row(p)
        on = attempts is not None or minutes is not None
        plan.update({"budget": attempts, "minutes": minutes, "runs": [] if on else plan.get("runs", [])})
        with self._tx() as c:
            c.execute("UPDATE projects SET plan=? WHERE pk=?", (_j(plan), p["pk"]))
            self._log(c, p["pk"], "plan_budget", {"attempts": attempts, "minutes": minutes}, actor.name)
            self._touch_project(c, p["pk"])
        return self.plan(project)

    def _plan_used(self, plan) -> int:
        runs = [int(x) for x in plan.get("runs", [])]
        if not runs:
            return 0
        return self._q1(f"SELECT COUNT(*) AS n FROM attempts WHERE run_pk IN ({','.join('?' * len(runs))})",
                        tuple(runs))["n"]

    def _plan_minutes(self, plan) -> float:
        """Elapsed minutes of the runs the plan started: each run from its start to its end (or now)."""
        runs = [int(x) for x in plan.get("runs", [])]
        if not runs:
            return 0.0
        now = self.clock()
        rows = self._q(f"SELECT started_at, created_at, ended_at FROM runs WHERE pk IN ({','.join('?' * len(runs))})",
                       tuple(runs))
        return sum(max(0.0, (r["ended_at"] or now) - (r["started_at"] or r["created_at"])) for r in rows) / 60.0

    def _plan_stop(self, plan) -> str | None:
        """Why the plan starts nothing more, or None."""
        if plan.get("budget") is not None and self._plan_used(plan) >= plan["budget"]:
            return f"the plan's budget of {plan['budget']} attempts is used"
        if plan.get("minutes") is not None and self._plan_minutes(plan) >= plan["minutes"]:
            return f"the plan's budget of {plan['minutes']} minutes is used"
        return None

    def plan(self, project: str, need: str | None = None) -> dict:
        p = self._project_row(project)
        items = []
        for n in self._q("SELECT * FROM rungs WHERE project_pk=? AND kind='need' AND retired_at IS NULL AND status NOT IN "
                         "('dismissed','proposed') ORDER BY num", (p["pk"],)):
            if need and n["rid"] != need:
                continue
            for req in self._children_rows(n["pk"]):
                if req["status"] not in ("approved", "stale") or _l(req["data"], {}).get("out_of_scope"):
                    continue
                for s in self._children_rows(req["pk"]):
                    if s["kind"] != "specification" or s["status"] not in ("approved", "stale"):
                        continue
                    v = self._verify(s)
                    running = self._q1("SELECT pk FROM runs WHERE spec_pk=? AND status IN ('queued','running')",
                                       (s["pk"],))
                    waits = self.blocked_by(s)
                    ok, why = self.develop_available(project, s["rid"])
                    last = self._q1("SELECT pk, status, reason FROM runs WHERE spec_pk=? ORDER BY pk DESC LIMIT 1",
                                    (s["pk"],))
                    person = [t["test"] for t in v.get("tests", []) if t.get("required") and t["type"] != "command"
                              and t.get("state") != "satisfied"]
                    commands_pass = all(t.get("state") == "satisfied" for t in v.get("tests", [])
                                        if t.get("required") and t["type"] == "command")
                    if v["ok"]:
                        state, reason = "verified", ""
                    elif running:
                        state, reason = "running", f"run {running['pk']}"
                    elif person and commands_pass:
                        # Another run cannot help: the commands pass on this code and only a person's check is left
                        # (found recording the demo: Start ready work kept restarting it and starved the next one).
                        state, reason = "needs_you", f"commands pass; {', '.join(person)} needs a person"
                    elif waits:
                        state, reason = "blocked", waits
                    elif ok and s["status"] == "approved":
                        state, reason = "ready", ""
                        if last is not None and last["status"] == "unknown":  # SYS-13: interrupted, never passed
                            reason = f"run {last['pk']} was interrupted: {last['reason'] or 'unknown outcome'}"
                    elif s["status"] == "approved" and why.startswith("no eligible profile") and "at capacity" in why:
                        state, reason = "waiting", why
                    else:
                        state, reason = "not_ready", why or f"{s['rid']} is {s['status']}"
                    blocked_by = waits.split(": ")[0].split(" waits for ")[1:2] if state == "blocked" else []
                    items.append({"spec": s["rid"], "text": s["text"], "need": n["rid"], "requirement": req["rid"],
                                  "state": state, "reason": reason, "requires": self._requires(s),
                                  "blocked_by": blocked_by,
                                  "verification": v["verification"], "run": running["pk"] if running else None,
                                  "last_run": ({"run": last["pk"], "status": last["status"]} if last is not None
                                               else None)})
        # dependency order: a prerequisite before the specifications that require it, otherwise as listed
        pos = {it["spec"]: i for i, it in enumerate(items)}
        done, ordered = set(), []

        def visit(it, stack=()):
            if it["spec"] in done or it["spec"] in stack:
                return
            for x in it["requires"]:
                if x in pos:
                    visit(items[pos[x]], stack + (it["spec"],))
            done.add(it["spec"])
            ordered.append(it)
        for it in items:
            visit(it)
        items = ordered
        plan = self._plan_row(p)
        used = self._plan_used(plan)
        budget = plan.get("budget")
        mins = plan.get("minutes")
        spent = round(self._plan_minutes(plan), 1)
        stop = self._plan_stop(plan)
        return {"items": items, "budget": {"attempts": budget, "used": used,
                                           "left": None if budget is None else max(0, budget - used),
                                           "minutes": mins, "minutes_used": spent,
                                           "exhausted": stop is not None, "stopped": stop},
                "model_usage": "unavailable"}

    def start_ready(self, project: str, need: str | None = None, actor=None, launch=None) -> dict:
        """Start every Ready specification of the plan (`launch(project, rid)` starts one and returns the run),
        until the budget is used. Verified, running and blocked work is left as it is."""
        from .core import HUMAN, RungError
        actor = actor or HUMAN
        if not actor.is_human:
            raise RungError("only a human starts the plan", code="forbidden", status=403)
        launch = launch or (lambda proj, rid: self.start_run(proj, rid, actor))
        started, refused, stopped = [], [], None
        for it in self.plan(project, need)["items"]:
            if it["state"] != "ready":
                continue
            p = self._project_row(project)
            plan = self._plan_row(p)
            stopped = self._plan_stop(plan)
            if stopped:
                break
            ok, why = self.develop_available(project, it["spec"])
            if not ok:  # within each profile's limits: one started above may have filled the last place
                refused.append({"spec": it["spec"], "reason": why})
                continue
            try:
                run = launch(project, it["spec"])
            except RungError as exc:
                refused.append({"spec": it["spec"], "reason": str(exc)})
                continue
            started.append({"spec": it["spec"], "run": run["id"]})
            plan.setdefault("runs", []).append(run["id"])
            with self._tx() as c:
                c.execute("UPDATE projects SET plan=? WHERE pk=?", (_j(plan), p["pk"]))
        with self._tx() as c:
            self._log(c, self._project_row(project)["pk"], "plan_started",
                      {"started": [x["spec"] for x in started], "stopped": stopped}, actor.name)
        return {"started": started, "refused": refused, "stopped": stopped, "plan": self.plan(project, need)}

    # ------------------------------------------------------------------ contract checks (SYS-06)

    def _contract_row(self, project: str, name: str):
        from .core import RungError
        p = self._project_row(project)
        row = self._arch_row(p["pk"], "contract", str(name or "").strip())
        if row is None:
            raise RungError(f"no contract {name}", code="not_found", status=404)
        return p, row

    def add_contract_check(self, project: str, contract: str, command: str, timeout: int = 120, actor=None) -> dict:
        """Propose a check (agents may); a person approves it before it counts."""
        from .core import HUMAN, RungError
        actor = actor or HUMAN
        command = str(command or "").strip()
        if not command:
            raise RungError("a contract check needs a command", code="bad_request", status=400, field="command")
        self._check_writable(project, None)
        p, row = self._contract_row(project, contract)
        with self._tx() as c:
            n = c.execute("SELECT COUNT(*) FROM contract_checks WHERE arch_pk=?", (row["pk"],)).fetchone()[0] + 1
            cid = f"CC-{n}"
            status = "draft"
            c.execute("INSERT INTO contract_checks(arch_pk, cid, command, timeout, status, by_name, created_at) "
                      "VALUES (?,?,?,?,?,?,?)", (row["pk"], cid, command, int(timeout or 120), status, actor.name,
                                                 self.clock()))
            self._log(c, p["pk"], "contract_check_added", {"contract": row["name"], "check": cid}, actor.name)
            self._touch_project(c, p["pk"])
        return self.contract_checks(project, contract)

    def approve_contract_check(self, project: str, contract: str, cid: str, actor=None) -> dict:
        from .core import HUMAN, RungError
        actor = actor or HUMAN
        if not actor.is_human:
            raise RungError("only a human approves a contract check", code="forbidden", status=403)
        self._check_writable(project, None)
        p, row = self._contract_row(project, contract)
        with self._tx() as c:
            n = c.execute("UPDATE contract_checks SET status='approved', approved_by=?, approved_at=? WHERE arch_pk=? "
                          "AND cid=? AND status='draft'", (actor.name, self.clock(), row["pk"], str(cid).strip())).rowcount
            if not n:
                raise RungError(f"no draft check {cid} on {row['name']}", code="not_found", status=404)
            self._log(c, p["pk"], "contract_check_approved", {"contract": row["name"], "check": cid}, actor.name)
            self._touch_project(c, p["pk"])
        return self.contract_checks(project, contract)

    def _contract_check_state(self, ch, version: int, cur: str) -> dict:
        out = {"check": ch["cid"], "command": ch["command"], "status": ch["status"], "by": ch["by_name"],
               "approved_by": ch["approved_by"], "run": None}
        r = self._q1("SELECT * FROM contract_runs WHERE check_pk=? ORDER BY n DESC LIMIT 1", (ch["pk"],))
        if r is None:
            out["state"] = "missing"
            return out
        out.update({"run": r["n"], "result": r["status"], "contract_version": r["contract_version"],
                    "basis": evidence.short(r["basis"]), "output": (r["output"] or "")[-2000:]})
        if r["status"] == "error":
            out["state"] = "could_not_verify"
        elif cur == evidence.UNKNOWN or r["basis"] == evidence.UNKNOWN:
            out["state"] = "could_not_verify"
        elif r["contract_version"] != version:
            out["state"], out["why"] = "out_of_date", f"recorded on contract v{r['contract_version']}, now v{version}"
        elif r["basis"] != cur:
            out["state"], out["why"] = "out_of_date", "recorded on code that has changed since"
        elif r["status"] == "fail":
            out["state"] = "failed"
        else:
            out["state"] = "satisfied"
        return out

    def _contract_comps(self, cur_v) -> list:
        d = _l(cur_v["data"], {}) if cur_v is not None else {}
        return [x for x in [d.get("producer")] + list(d.get("consumers", [])) if x]

    def contract_checks(self, project: str, contract: str, fresh: bool = True) -> dict:
        p, row = self._contract_row(project, contract)
        cur_v = self._arch_current(row["pk"])
        version = cur_v["version"] if cur_v else 0
        cur = self._scope_cur(p["pk"], self._contract_comps(cur_v), evidence.basis(p["folder"], fresh=fresh))
        checks = [self._contract_check_state(ch, version, cur) for ch in
                  self._q("SELECT * FROM contract_checks WHERE arch_pk=? AND status!='removed' ORDER BY pk", (row["pk"],))]
        req = [x for x in checks if x["status"] == "approved"]
        state = ("none" if not req else "failed" if any(x["state"] == "failed" for x in req)
                 else "satisfied" if all(x["state"] == "satisfied" for x in req)
                 else "out_of_date" if any(x["state"] == "out_of_date" for x in req)
                 else "could_not_verify" if any(x["state"] == "could_not_verify" for x in req) else "not_run")
        return {"contract": row["name"], "version": version, "checks": checks, "state": state,
                "basis": evidence.short(cur)}

    def run_contract_checks(self, project: str, contract: str, carried_by: str = "engine", env=None) -> dict:
        """Run every approved check of a contract on the project folder, recording version and basis."""
        from .core import RungError
        from .execute import run_command
        p, row = self._contract_row(project, contract)
        cur_v = self._arch_current(row["pk"])
        if cur_v is None:
            raise RungError(f"contract {row['name']} has no approved version", code="not_approved", status=409)
        with self._tx() as c:
            busy = self._busy_folder(c, p["pk"])
        if busy:
            raise RungError(f"contract {row['name']} cannot be checked now: {busy}", code="busy", status=409)
        root = Path(p["folder"]).expanduser()
        for ch in self._q("SELECT * FROM contract_checks WHERE arch_pk=? AND status='approved' ORDER BY pk", (row["pk"],)):
            start = self.clock()
            if not root.is_dir():
                status, code, output = "error", None, f"folder not found: {root}"
            else:
                res = run_command(ch["command"], root, timeout=ch["timeout"], output_limit=64000, env=env)
                code, output = res.exit_code, res.output
                status = ("error" if res.timed_out or res.launch_error or res.exit_code in (126, 127)
                          else "pass" if res.exit_code == 0 else "fail")
            evidence.forget(root)
            b = self._scope_cur(p["pk"], self._contract_comps(cur_v), evidence.basis(root, fresh=True))
            with self._tx() as c:
                n = c.execute("SELECT COALESCE(MAX(n),0)+1 FROM contract_runs WHERE check_pk=?", (ch["pk"],)).fetchone()[0]
                c.execute("INSERT INTO contract_runs(check_pk, n, contract_version, status, exit_code, output, basis, "
                          "carried_by, started_at, ended_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                          (ch["pk"], n, cur_v["version"], status, code, output or "", b, carried_by, start, self.clock()))
                self._log(c, p["pk"], "contract_check_run", {"contract": row["name"], "check": ch["cid"], "n": n,
                                                             "status": status}, carried_by)
                self._touch_project(c, p["pk"])
        return self.contract_checks(project, contract)

    def _contract_check_blockers(self, project_pk: int, components, cur: str) -> list[dict]:
        """For a milestone: every approved contract check of a contract touching these components that is not
        Satisfied, as a blocker."""
        comps = set(components or [])
        out = []
        if not comps:
            return out
        for r in self._q("SELECT * FROM arch WHERE project_pk=? AND kind='contract' ORDER BY name", (project_pk,)):
            cur_v = self._arch_current(r["pk"])
            if cur_v is None:
                continue
            d = _l(cur_v["data"], {})
            if not comps & ({d.get("producer")} | set(d.get("consumers", []))):
                continue
            ccur = self._scope_cur(project_pk, self._contract_comps(cur_v), cur)
            for ch in self._q("SELECT * FROM contract_checks WHERE arch_pk=? AND status='approved' ORDER BY pk",
                              (r["pk"],)):
                st = self._contract_check_state(ch, cur_v["version"], ccur)
                if st["state"] == "satisfied":
                    continue
                what = {"missing": "has not run", "failed": f"failed (#{st['run']})",
                        "out_of_date": f"is out of date: {st.get('why', '')}",
                        "could_not_verify": f"could not run (#{st['run']})"}[st["state"]]
                code = {"missing": "contract_not_run", "failed": "contract_failed", "out_of_date": "contract_out_of_date",
                        "could_not_verify": "could_not_verify"}[st["state"]]
                out.append({"code": code, "text": f"contract {r['name']} check {ch['cid']} {what}",
                            "contract": r["name"], "check": ch["cid"]})
        return out

    # ------------------------------------------------------------------ change impact (SYS-11)

    def _scope_paths(self, project_pk: int, comps) -> tuple[list, list] | None:
        """(paths of these components, paths of every approved component), or None when the scope is the whole
        project (no components named, or none of them declares paths)."""
        comps = list(comps or [])
        if not comps:
            return None
        known = self._approved_components(project_pk)
        own = sorted({x.strip("/") for c in comps for x in (known.get(c, {}).get("paths") or []) if x.strip("/")})
        if not own:
            return None
        allp = sorted({x.strip("/") for d in known.values() for x in (d.get("paths") or []) if x.strip("/")})
        return own, allp

    @staticmethod
    def _under(rel: str, paths) -> bool:
        return any(rel == x or rel.startswith(x + "/") for x in paths)

    def _scoped_digest(self, project_pk: int, comps, m: dict | None) -> str | None:
        sc = self._scope_paths(project_pk, comps)
        if sc is None:
            return None
        if m is None:
            return evidence.UNKNOWN
        own, allp = sc
        return evidence.digest({k: v for k, v in m.items() if self._under(k, own) or not self._under(k, allp)})

    def _scope_cur(self, project_pk: int, comps, cur: str) -> str:
        """The basis this scope is judged on, for the project basis `cur` (cached per project basis)."""
        if not comps or cur == evidence.UNKNOWN:
            return cur
        sc = self._scope_paths(project_pk, comps)
        if sc is None:
            return cur
        cache = getattr(self, "_scache", None)
        if cache is None or len(cache) > 512:
            cache = self._scache = {}
        key = (project_pk, cur, tuple(sc[0]), tuple(sc[1]))
        hit = cache.get(key)
        if hit is None:
            root = self._project_row(project_pk)["folder"]
            hit = cache[key] = self._scoped_digest(project_pk, comps, evidence.manifest(root)) or cur
        return hit

    def _spec_comps(self, spec) -> list:
        return _l(spec["data"], {}).get("components", []) if spec is not None else []

    def _spec_cur(self, spec, cur: str) -> str:
        return self._scope_cur(spec["project_pk"], self._spec_comps(spec), cur)

    def scope_line(self, project: str, comps) -> str:
        """The limit of selection, as data: what a scope's evidence is judged on."""
        p = self._project_row(project)
        sc = self._scope_paths(p["pk"], comps)
        if sc is None:
            return "Judged on: every project file"
        return "Judged on: " + ", ".join(sc[0]) + " and files outside every component"

    def check_everything(self, project: str, carried_by: str = "engine") -> dict:
        """Rerun every approved command test, every contract check and every approved milestone's checks,
        regardless of impact."""
        from .core import RungError
        p = self._project_row(project)
        tests = []
        for s in self._q("SELECT * FROM rungs WHERE project_pk=? AND kind='specification' AND status='approved' "
                         "ORDER BY num, rid", (p["pk"],)):
            for t in self.command_tests(project, s["rid"]):
                tests.append(self.run_test(project, t["id"], carried_by=carried_by))
        contracts = []
        for r in self._q("SELECT * FROM arch WHERE project_pk=? AND kind='contract' ORDER BY name", (p["pk"],)):
            if self._arch_current(r["pk"]) is not None and self._q1(
                    "SELECT pk FROM contract_checks WHERE arch_pk=? AND status='approved'", (r["pk"],)):
                contracts.append(self.run_contract_checks(project, r["name"], carried_by=carried_by))
        ms = []
        for m in self._q("SELECT * FROM milestones WHERE project_pk=? AND status='approved' ORDER BY num", (p["pk"],)):
            try:
                ms.append({"milestone": m["mid"], "checks": self.run_milestone(project, m["mid"], carried_by=carried_by)})
            except RungError as exc:
                ms.append({"milestone": m["mid"], "error": str(exc)})
        return {"tests": [{"test": x.get("test"), "status": x.get("status")} for x in tests],
                "contracts": [{"contract": c["contract"], "state": c["state"]} for c in contracts], "milestones": ms}

    # ------------------------------------------------------------------ system report (SYS-12)

    def system_report(self, project: str) -> dict:
        """Every milestone with its journeys, quality obligations, dependencies, environment, exclusions and
        manual decisions. Accepted only when there is at least one milestone and every one is approved and
        verified now; anything else is named."""
        p = self._project_row(project)
        ms, open_items = [], []
        for m in self._q("SELECT * FROM milestones WHERE project_pk=? ORDER BY num", (p["pk"],)):
            v = self.milestone(project, m["mid"])
            deps = []
            for rid in v.get("scope_ids") or [x["id"] for x in v["scope"]]:
                try:
                    for d in self.dependencies(project, rid)["requires"]:
                        deps.append(f"{rid} requires {d['id']}")
                except Exception:  # noqa: BLE001 - a missing specification is already a blocker
                    pass
            manual = []
            for ch in v["checks"]:
                if ch["type"] != "manual":
                    continue
                by = ""
                if ch["run"]:
                    row = self._q1("SELECT r.carried_by FROM milestone_runs r JOIN milestone_checks k ON k.pk=r.check_pk "
                                   "WHERE k.milestone_pk=? AND k.cid=? AND r.n=?", (m["pk"], ch["check"], ch["run"]))
                    by = row["carried_by"] if row is not None else ""
                manual.append({"check": ch["check"], "state": ch["state"], "by": by})
            ms.append({"milestone": m["mid"], "title": v["title"], "state": v["state"], "ok": v["ok"],
                       "journeys": v["journeys"], "quality": [ch for ch in v["checks"] if ch.get("quality")],
                       "dependencies": deps, "environment": v["environment"], "env_run": v.get("env_run"),
                       "exclusions": [j for j in v["journeys"] if not j["in_scope"]], "manual": manual,
                       "blockers": v["blockers"]})
            if not v["ok"]:
                first = v["blockers"][0]["text"] if v["blockers"] else v["state"]
                open_items.append(f"{m['mid']}: {first}")
        out_scope = []
        for n in self._q("SELECT * FROM rungs WHERE project_pk=? AND kind='need' AND retired_at IS NULL", (p["pk"],)):
            for r in self._children_rows(n["pk"]):
                d = _l(r["data"], {})
                if d.get("out_of_scope"):
                    out_scope.append({"id": r["rid"], "text": r["text"],
                                      "reason": (d["out_of_scope"] or {}).get("reason", "")
                                      if isinstance(d["out_of_scope"], dict) else ""})
        accepted = bool(ms) and not open_items
        if not ms:
            open_items.append("no milestone is defined")
        return {"project": p["name"], "accepted": accepted, "verdict": "Accepted" if accepted else "Not accepted",
                "open": open_items, "milestones": ms, "out_of_scope": out_scope, "basis": evidence.short(
                    evidence.basis(p["folder"], fresh=True))}

    def system_report_markdown(self, project: str) -> str:
        r = self.system_report(project)
        out = [f"# System report: {r['project']}", "", f"Verdict: {r['verdict']}", f"Code basis: {r['basis']}", ""]
        if r["open"]:
            out += ["## Not accepted because", ""] + [f"- {x}" for x in r["open"]] + [""]
        for m in r["milestones"]:
            out += [f"## {m['milestone']} {m['title']}", "", f"State: {m['state'].replace('_', ' ')}", ""]
            if m["journeys"]:
                out += ["Journeys:"] + [f"- {j['name']}: " + (f"in scope, check {j['check'] or 'none'}" if j["in_scope"]
                                                             else f"out of scope ({j['reason']})")
                                       for j in m["journeys"]] + [""]
            if m["quality"]:
                out.append("Quality obligations:")
                for ch in m["quality"]:
                    q = ch["quality"]
                    out.append(f"- {ch['check']} {q['category']}: " + (
                        ch["measured_text"] if ch.get("measured_text") else ch["state"].replace("_", " ")))
                out.append("")
            if m["dependencies"]:
                out += ["Dependencies:"] + [f"- {d}" for d in m["dependencies"]] + [""]
            env = m["environment"]
            if env.get("probes") or env.get("migration"):
                out.append("Environment:")
                rec = m.get("env_run") or {}
                for pr in env.get("probes", []):
                    got = next((x for x in rec.get("probes", []) if x["command"] == pr["command"]), None)
                    out.append(f"- probe {pr['command']}: " + (f"printed {got['output'][:80]}" if got else "not run"))
                if env.get("migration"):
                    out.append(f"- migration {env['migration']}: "
                               + (f"exited {rec['migration']['exit_code']}" if rec.get("migration") else "not run"))
                out.append("")
            if m["manual"]:
                out += ["Manual decisions:"] + [f"- {x['check']}: {x['state'].replace('_', ' ')}"
                                               + (f" by {x['by']}" if x["by"] else "") for x in m["manual"]] + [""]
        if r["out_of_scope"]:
            out += ["## Out of scope", ""] + [f"- {x['id']} {x['text']}" + (f" ({x['reason']})" if x["reason"] else "")
                                              for x in r["out_of_scope"]] + [""]
        return "\n".join(out)
