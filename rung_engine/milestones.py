# pyright: reportAttributeAccessIssue=false
"""Integration milestones (decisions Round 23): the smallest system-level control.

A milestone names an outcome and a user journey, includes approved specifications, and carries its own approved
cross-component checks. Its verdict is separate from each specification's: the included work must be verified
now (the same evaluator as the gate), then every required milestone check must pass on the project's current
code basis, as approved. Pure engine computation; no model call. A mixin of `Engine`.

States (machine codes; the pane maps them to words):
    draft           the scope is not approved
    not_ready       an included specification is not verified now (Not ready for integration)
    ready           the included work is verified; a required check has not run on this basis or scope
    verifying       a milestone check is running
    integration_failed  a required check failed
    could_not_verify    a required check could not run, or its files changed since approval
    awaiting_manual a required manual acceptance has no approved pass
    out_of_date     a required check passed on code that has changed since
    verified        every required check passed on the current basis and scope
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path

from . import evidence
from .execute import run_command

MID = "M-"


def _j(x):
    return json.dumps(x, sort_keys=True)


def _l(x, default=None):
    try:
        return json.loads(x) if x else default
    except (TypeError, ValueError):
        return default


class MilestonesMixin:
    # ------------------------------------------------------------------ rows

    def _milestone_row(self, project: str, mid: str):
        from .core import RungError
        p = self._project_row(project)
        mid = str(mid or "").strip().upper()
        if mid and not mid.startswith(MID):
            mid = MID + mid.lstrip("M").lstrip("-")
        r = self._q1("SELECT * FROM milestones WHERE project_pk=? AND mid=?", (p["pk"], mid))
        if r is None:
            raise RungError(f"no milestone {mid} in {p['name']}", code="not_found", status=404)
        return r

    def _check_rows(self, m):
        return self._q("SELECT * FROM milestone_checks WHERE milestone_pk=? AND status!='removed' ORDER BY cid", (m["pk"],))

    def _scope_rows(self, m):
        out = []
        for rid in _l(m["scope"], []):
            r = self._q1("SELECT * FROM rungs WHERE project_pk=? AND rid=?", (m["project_pk"], rid))
            out.append((rid, r))
        return out

    # ------------------------------------------------------------------ writes

    def _require_human(self, actor, what: str):
        from .core import RungError
        if not actor.is_human:
            raise RungError(f"only a human {what}", code="forbidden", status=403)

    def _scope_ids(self, project: str, scope) -> list[str]:
        from .core import RungError
        ids = []
        for rid in scope or []:
            r = self._rung_row(project, str(rid))
            if r["kind"] != "specification":
                raise RungError(f"{r['rid']} is not a specification", code="bad_request", status=400, field="scope")
            if r["rid"] not in ids:
                ids.append(r["rid"])
        if not ids:
            raise RungError("a milestone includes at least one specification", code="bad_request", status=400,
                            field="scope")
        return ids

    def create_milestone(self, project: str, title: str, journey: str, scope: list, architecture: str = "",
                         actor=None) -> dict:
        from .core import HUMAN, RungError
        actor = actor or HUMAN
        self._require_human(actor, "creates a milestone")
        with self._lock:
            self._check_writable(project, None)
            p = self._project_row(project)
            title, journey = (title or "").strip(), (journey or "").strip()
            if not title:
                raise RungError("a milestone needs an outcome", code="bad_request", status=400, field="title")
            if not journey:
                raise RungError("a milestone needs a user journey", code="bad_request", status=400, field="journey")
            ids = self._scope_ids(project, scope)
            now = self.clock()
            with self._tx() as c:
                n = c.execute("SELECT COALESCE(MAX(num),0)+1 FROM milestones WHERE project_pk=?", (p["pk"],)).fetchone()[0]
                c.execute("INSERT INTO milestones(project_pk, mid, num, title, journey, architecture, scope, status, "
                          "version, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                          (p["pk"], f"{MID}{n}", n, title, journey, (architecture or "").strip(), _j(ids), "draft", 1,
                           now, now))
                self._log(c, p["pk"], "milestone_created", {"milestone": f"{MID}{n}"}, actor.name)
                self._touch_project(c, p["pk"])
        return self.milestone(project, f"{MID}{n}")

    def _bump(self, c, m, now):
        """Any change to scope, journey or checks is a new contract: back to draft, version up. History stays."""
        c.execute("UPDATE milestones SET status='draft', version=version+1, approved_by=NULL, approved_at=NULL, "
                  "updated_at=? WHERE pk=?", (now, m["pk"]))

    def edit_milestone(self, project: str, mid: str, fields: dict, actor=None) -> dict:
        from .core import HUMAN
        actor = actor or HUMAN
        self._require_human(actor, "edits a milestone")
        with self._lock:
            self._check_writable(project, None)
            m = self._milestone_row(project, mid)
            sets = {}
            for k in ("title", "journey", "architecture"):
                if k in fields and str(fields[k] or "").strip() != (m[k] or ""):
                    sets[k] = str(fields[k] or "").strip()
            if "scope" in fields:
                ids = self._scope_ids(project, fields["scope"])
                if ids != _l(m["scope"], []):
                    sets["scope"] = _j(ids)
            if sets:
                now = self.clock()
                with self._tx() as c:
                    for k, v in sets.items():
                        c.execute(f"UPDATE milestones SET {k}=? WHERE pk=?", (v, m["pk"]))
                    self._bump(c, m, now)
                    self._log(c, m["project_pk"], "milestone_edited", {"milestone": m["mid"], "fields": sorted(sets)},
                              actor.name)
                    self._touch_project(c, m["project_pk"])
        return self.milestone(project, mid)

    def add_milestone_check(self, project: str, mid: str, fields: dict, actor=None) -> dict:
        from .core import HUMAN, RungError
        actor = actor or HUMAN
        self._require_human(actor, "adds a milestone check")
        ttype = fields.get("type", "command")
        if ttype not in ("command", "manual"):
            raise RungError("a milestone check is a command or a manual check", code="bad_request", status=400,
                            field="type")
        data = {"type": ttype, "required": fields.get("required", True) is not False}
        if ttype == "command":
            cmd = str(fields.get("command") or "").strip()
            if not cmd:
                raise RungError("a command check needs a command", code="bad_request", status=400, field="command")
            data.update({"command": cmd, "folder": str(fields.get("folder") or ".").strip() or ".",
                         "timeout": int(fields.get("timeout") or 300),
                         "pass_rule": fields.get("pass_rule") or {"kind": "exit_code", "value": 0}})
        else:
            steps = [str(s).strip() for s in fields.get("steps") or [] if str(s).strip()]
            if not steps:
                raise RungError("a manual check needs steps", code="bad_request", status=400, field="steps")
            data["steps"] = steps
        if fields.get("quality"):
            data["quality"] = self._clean_quality(fields["quality"], ttype)
        text = str(fields.get("text") or "").strip() or (data.get("command") or "; ".join(data.get("steps", [])))
        with self._lock:
            self._check_writable(project, None)
            m = self._milestone_row(project, mid)
            now = self.clock()
            with self._tx() as c:
                k = c.execute("SELECT COUNT(*) FROM milestone_checks WHERE milestone_pk=?", (m["pk"],)).fetchone()[0]
                cid = f"{m['mid']}.{chr(ord('a') + k) if k < 26 else k + 1}"
                c.execute("INSERT INTO milestone_checks(milestone_pk, cid, text, data, status, created_at) "
                          "VALUES (?,?,?,?,?,?)", (m["pk"], cid, text, _j(data), "active", now))
                self._bump(c, m, now)
                self._log(c, m["project_pk"], "milestone_check_added", {"milestone": m["mid"], "check": cid}, actor.name)
                self._touch_project(c, m["project_pk"])
        return self.milestone(project, mid)

    def remove_milestone_check(self, project: str, mid: str, cid: str, actor=None) -> dict:
        from .core import HUMAN, RungError
        actor = actor or HUMAN
        self._require_human(actor, "removes a milestone check")
        with self._lock:
            self._check_writable(project, None)
            m = self._milestone_row(project, mid)
            ch = self._q1("SELECT * FROM milestone_checks WHERE milestone_pk=? AND cid=? AND status!='removed'",
                          (m["pk"], str(cid).strip()))
            if ch is None:
                raise RungError(f"no check {cid} on {m['mid']}", code="not_found", status=404)
            now = self.clock()
            with self._tx() as c:
                c.execute("UPDATE milestone_checks SET status='removed' WHERE pk=?", (ch["pk"],))
                self._bump(c, m, now)
                self._log(c, m["project_pk"], "milestone_check_removed", {"milestone": m["mid"], "check": ch["cid"]},
                          actor.name)
                self._touch_project(c, m["project_pk"])
        return self.milestone(project, mid)

    def approve_milestone(self, project: str, mid: str, actor=None) -> dict:
        """A person approves the scope, the journey and every check. Records each command check's files."""
        from .core import HUMAN, RungError
        actor = actor or HUMAN
        self._require_human(actor, "approves a milestone")
        with self._lock:
            self._check_writable(project, None)
            m = self._milestone_row(project, mid)
            checks = self._check_rows(m)
            if not any(_l(ch["data"], {}).get("type") == "command" and _l(ch["data"], {}).get("required", True)
                       for ch in checks):
                raise RungError(f"{m['mid']} needs at least one required command check across its pieces before "
                                "it is approved", code="no_checks")
            root = Path(self._project_row(m["project_pk"])["folder"]).expanduser()
            now = self.clock()
            with self._tx() as c:
                for ch in checks:
                    d = _l(ch["data"], {})
                    if d.get("type") == "command":
                        files = evidence.protected_files(d["command"], root / d.get("folder", "."), root)
                        c.execute("UPDATE milestone_checks SET assets=? WHERE pk=?",
                                  (_j(evidence.digest_files(root, files)), ch["pk"]))
                c.execute("UPDATE milestones SET status='approved', approved_by=?, approved_at=?, updated_at=? "
                          "WHERE pk=?", (actor.name, now, now, m["pk"]))
                self._log(c, m["project_pk"], "milestone_approved", {"milestone": m["mid"], "version": m["version"]},
                          actor.name)
                self._touch_project(c, m["project_pk"])
        return self.milestone(project, mid)

    # ------------------------------------------------------------------ running checks

    def _busy_folder(self, c, project_pk: int) -> str | None:
        r = c.execute("SELECT pk FROM runs WHERE project_pk=? AND status IN ('queued','running')", (project_pk,)).fetchone()
        if r:
            return f"develop run {r[0]} is changing the project folder"
        r = c.execute("SELECT mc.cid FROM milestone_runs mr JOIN milestone_checks mc ON mc.pk=mr.check_pk JOIN milestones "
                      "m ON m.pk=mc.milestone_pk WHERE m.project_pk=? AND mr.status='running'", (project_pk,)).fetchone()
        if r:
            return f"milestone check {r[0]} is running"
        return None

    def integration_running(self, c, project_pk: int) -> str | None:
        """The milestone check running in this project, if any: no develop run starts while one does."""
        r = c.execute("SELECT mc.cid FROM milestone_runs mr JOIN milestone_checks mc ON mc.pk=mr.check_pk JOIN milestones "
                      "m ON m.pk=mc.milestone_pk WHERE m.project_pk=? AND mr.status='running'", (project_pk,)).fetchone()
        return r[0] if r else None

    def milestone_runnable(self, project: str, mid: str) -> None:
        from .core import RungError
        m = self._milestone_row(project, mid)
        if m["status"] != "approved":
            raise RungError(f"{m['mid']} is not approved", code="not_approved")
        with self._tx() as c:
            busy = self._busy_folder(c, m["project_pk"])
        if busy:
            raise RungError(f"{m['mid']} cannot run now: {busy}", code="busy")

    def run_milestone(self, project: str, mid: str, carried_by: str = "engine", env=None) -> list[dict]:
        """Run every command check of an approved milestone, one after another, on the code as it is now. Every
        run is reserved in one write transaction with the busy check, so no develop run or second integration
        starts in between: integration is judged on one state of the folder."""
        from .core import RungError
        m = self._milestone_row(project, mid)
        if m["status"] != "approved":
            raise RungError(f"{m['mid']} is not approved", code="not_approved")
        p = self._project_row(m["project_pk"])
        root = Path(p["folder"]).expanduser()
        sysd = _l(m["system"], {}) or {}
        base = sysd.get("baseline") or {}
        for b in base.get("milestones", []):  # SYS-08: the earlier journeys run on the same code
            br = self._q1("SELECT * FROM milestones WHERE project_pk=? AND mid=? AND status='approved'",
                          (m["project_pk"], b))
            if br is not None:
                self.run_milestone(project, b, carried_by=carried_by, env=env)
        envd = sysd.get("environment")
        if envd and (envd.get("probes") or envd.get("migration")):  # SYS-10: probes and migration first
            rec = self._run_environment(m, root, envd)
            sysd["env_run"] = rec
            with self._tx() as c:
                c.execute("UPDATE milestones SET system=? WHERE pk=?", (_j(sysd), m["pk"]))
                self._log(c, m["project_pk"], "milestone_environment_run", {"milestone": m["mid"], "ok": rec["ok"],
                                                                          "code": rec["code"]}, carried_by)
            if not rec["ok"]:
                return [{"environment": rec["code"], "status": "error"}]
        if base.get("command"):
            res = run_command(base["command"], root, timeout=600, output_limit=8000, env=env)
            evidence.forget(root)
            sysd["baseline_run"] = {"command": base["command"], "exit_code": res.exit_code,
                                    "status": "pass" if res.exit_code == 0 else "fail",
                                    "basis": evidence.basis(root, fresh=True), "output": (res.output or "")[-4000:]}
            with self._tx() as c:
                c.execute("UPDATE milestones SET system=? WHERE pk=?", (_j(sysd), m["pk"]))
        checks = [ch for ch in self._check_rows(m) if _l(ch["data"], {}).get("type") == "command"]
        start = self._scope_cur(m["project_pk"], self._m_comps(m), evidence.basis(root, fresh=True))
        now = self.clock()
        reserved = []
        with self._tx() as c:
            busy = self._busy_folder(c, m["project_pk"])
            if busy:
                raise RungError(f"{m['mid']} cannot run now: {busy}", code="busy")
            for ch in checks:
                n = c.execute("SELECT COALESCE(MAX(n),0)+1 FROM milestone_runs WHERE check_pk=?", (ch["pk"],)).fetchone()[0]
                c.execute("INSERT INTO milestone_runs(check_pk, n, version, status, command, carried_by, basis_start, "
                          "started_at) VALUES (?,?,?,?,?,?,?,?)", (ch["pk"], n, m["version"], "running",
                                                                  _l(ch["data"], {})["command"], carried_by, start, now))
                reserved.append((ch, n, c.execute("SELECT pk FROM milestone_runs WHERE check_pk=? AND n=?",
                                                  (ch["pk"], n)).fetchone()[0]))
            self._touch_project(c, m["project_pk"])
        out = []
        try:
            for i, (ch, n, pk) in enumerate(reserved):
                out.append(self._run_check(m, ch, n, pk, carried_by, env))
        finally:
            # Anything still reserved (an exception mid-way) ends as could not run, never stays running.
            with self._tx() as c:
                c.execute("UPDATE milestone_runs SET status='error', output='not run: integration stopped', ended_at=? "
                          f"WHERE status='running' AND pk IN ({','.join('?' * len(reserved)) or 'NULL'})",
                          (self.clock(), *[pk for _, _, pk in reserved]))
        return out

    def _run_check(self, m, ch, n, pk, carried_by, env):
        p = self._project_row(m["project_pk"])
        d = _l(ch["data"], {})
        root = Path(p["folder"]).expanduser()
        folder = (root / d.get("folder", ".")).expanduser()
        reason = ""
        base = _l(ch["assets"], {}) or {}
        files = sorted(set(base) | set(evidence.protected_files(d["command"], folder, root))) if folder.is_dir() else []
        moved = evidence.changed(base, evidence.digest_files(root, files)) if base else []
        before = evidence.manifest(root)
        if not folder.is_dir() or not folder.resolve().is_relative_to(root.resolve()):
            status, code, output = "error", None, f"folder not found inside the project: {folder}"
        else:  # run even when its files changed, so the person sees what they say; that result never counts
            res = run_command(d["command"], folder, timeout=d.get("timeout", 300), output_limit=64000, env=env)
            code, output = res.exit_code, res.output
            if res.timed_out or res.launch_error or res.exit_code in (126, 127):
                status = "error"
            else:
                status = "pass" if self._passes(d.get("pass_rule") or {}, res.exit_code, res.output) else "fail"
        after = evidence.manifest(root)
        evidence.forget(root)
        if status in ("pass", "fail") and evidence.modified(before, after):
            reason = "changed_during_check"
        if moved:
            reason = "verification_changed"
            output = ("judged by files changed since the check was approved: "
                      + ", ".join(f"{x['path']} ({x['change']})" for x in moved) + "\n\n" + (output or ""))
        with self._tx() as c:
            end = self._scoped_digest(m["project_pk"], self._m_comps(m), after) or evidence.digest(after)
            c.execute("UPDATE milestone_runs SET status=?, exit_code=?, output=?, reason=?, basis_end=?, ended_at=? "
                      "WHERE pk=?", (status, code, output, reason, end, self.clock(), pk))
            self._log(c, m["project_pk"], "milestone_check_run", {"milestone": m["mid"], "check": ch["cid"], "n": n,
                                                                  "status": status}, carried_by)
            self._touch_project(c, m["project_pk"])
        return {"check": ch["cid"], "n": n, "status": status, "exit_code": code, "reason": reason}

    def accept_check_files(self, project: str, mid: str, cid: str, actor=None) -> dict:
        from .core import HUMAN, RungError
        actor = actor or HUMAN
        self._require_human(actor, "accepts changes to a milestone check's files")
        m = self._milestone_row(project, mid)
        ch = self._q1("SELECT * FROM milestone_checks WHERE milestone_pk=? AND cid=? AND status!='removed'",
                      (m["pk"], str(cid).strip()))
        if ch is None:
            raise RungError(f"no check {cid} on {m['mid']}", code="not_found", status=404)
        d = _l(ch["data"], {})
        root = Path(self._project_row(m["project_pk"])["folder"]).expanduser()
        files = evidence.protected_files(d.get("command", ""), root / d.get("folder", "."), root)
        with self._tx() as c:
            c.execute("UPDATE milestone_checks SET assets=? WHERE pk=?", (_j(evidence.digest_files(root, files)), ch["pk"]))
            self._log(c, m["project_pk"], "milestone_check_files_accepted", {"milestone": m["mid"], "check": ch["cid"]},
                      actor.name)
        return self.milestone(project, mid)

    def record_milestone_manual(self, project: str, mid: str, cid: str, result: str, note: str = "",
                                actor=None) -> dict:
        """A person records the manual acceptance of the integrated journey. A pass recorded by a person counts at
        once (the recorder is the approver here; an agent cannot record one)."""
        from .core import HUMAN, RungError
        actor = actor or HUMAN
        self._require_human(actor, "records a manual acceptance")
        if result not in ("pass", "fail"):
            raise RungError("result is pass or fail", code="bad_request", status=400, field="result")
        m = self._milestone_row(project, mid)
        ch = self._q1("SELECT * FROM milestone_checks WHERE milestone_pk=? AND cid=? AND status!='removed'",
                      (m["pk"], str(cid).strip()))
        if ch is None or _l(ch["data"], {}).get("type") != "manual":
            raise RungError(f"{cid} is not a manual check of {m['mid']}", code="bad_request", status=400)
        b = self._scope_cur(m["project_pk"], self._m_comps(m),
                            evidence.basis(self._project_row(m["project_pk"])["folder"], fresh=True))
        now = self.clock()
        with self._tx() as c:
            n = c.execute("SELECT COALESCE(MAX(n),0)+1 FROM milestone_runs WHERE check_pk=?", (ch["pk"],)).fetchone()[0]
            c.execute("INSERT INTO milestone_runs(check_pk, n, version, status, carried_by, note, basis_start, basis_end, "
                      "started_at, ended_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                      (ch["pk"], n, m["version"], result, actor.name, (note or "").strip(), b, b, now, now))
            self._log(c, m["project_pk"], "milestone_manual", {"milestone": m["mid"], "check": ch["cid"], "n": n,
                                                               "result": result}, actor.name)
            self._touch_project(c, m["project_pk"])
        return self.milestone(project, mid)

    # ------------------------------------------------------------------ the verdict

    def _check_state(self, m, ch, cur: str) -> dict:
        d = _l(ch["data"], {})
        out = {"check": ch["cid"], "type": d.get("type", "command"), "required": d.get("required", True) is not False,
               "text": ch["text"], "command": d.get("command", ""), "steps": d.get("steps", []), "run": None}
        if d.get("quality"):
            out["quality"] = d["quality"]  # declared before any run, shown with the check
        r = self._q1("SELECT * FROM milestone_runs WHERE check_pk=? AND version=? ORDER BY n DESC LIMIT 1",
                     (ch["pk"], m["version"]))
        if r is None:
            out["state"] = "missing"
            return out
        out["run"] = r["n"]
        out["basis"] = evidence.short(r["basis_end"] or r["basis_start"])
        b = r["basis_end"] or r["basis_start"]
        if r["status"] == "running":
            out["state"] = "checking"
        elif r["status"] == "error" or r["reason"] == "verification_changed":
            out["state"] = "could_not_verify"  # could not run, or judged by files no person approved
            out["reason"] = r["reason"] or "error"
        elif cur == evidence.UNKNOWN or b == evidence.UNKNOWN:
            out["state"] = "could_not_verify"  # the code cannot be read: no positive result
            out["reason"] = "basis_unknown"
        elif r["reason"] == "changed_during_check" or b != cur:
            # A pass or a failure on other code says nothing about this code: run it again (still blocking).
            out["state"] = "out_of_date"
            out["was"] = r["status"]
        elif r["status"] == "fail":
            out["state"] = "failed"
        else:
            out["state"] = "satisfied"
        q = d.get("quality")
        if q:
            out["quality"] = q
            if q.get("measure") and out["state"] == "satisfied":
                found = re.findall(q["measure"], r["output"] or "")
                if not found:
                    out["state"], out["reason"] = "could_not_verify", "no_measurement"
                else:
                    val = float(found[-1] if isinstance(found[-1], str) else found[-1][0])
                    unit = q.get("unit", "")
                    ok = val <= q["threshold"] if q.get("direction", "max") == "max" else val >= q["threshold"]
                    out["measured"] = val
                    out["measured_text"] = (f"{val:g}{' ' + unit if unit else ''} against {q['threshold']:g} under "
                                            f"{q.get('workload') or 'no stated workload'}")
                    if not ok:
                        out["state"] = "quality_unmet"
        return out

    QUALITY = ("security", "performance", "resilience", "accessibility", "other")

    def _clean_quality(self, q, ttype) -> dict:
        from .core import RungError
        if not isinstance(q, dict):
            raise RungError("quality is an object", code="bad_request", status=400, field="quality")
        cat = str(q.get("category") or "").strip()
        if cat not in self.QUALITY:
            raise RungError("the category is security, performance, resilience, accessibility or other",
                            code="bad_request", status=400, field="category")
        out = {"category": cat, "workload": str(q.get("workload") or "").strip(),
               "environment": str(q.get("environment") or "").strip()}
        if ttype == "manual":  # a required human review
            out["review"] = True
            return out
        measure = str(q.get("measure") or "").strip()
        try:
            rx = re.compile(measure)
        except re.error as exc:
            raise RungError(f"the measure is not a valid pattern: {exc}", code="bad_request", status=400,
                            field="measure")
        if not measure or rx.groups != 1:
            raise RungError("the measure is a pattern with one group, the number", code="bad_request", status=400,
                            field="measure")
        try:
            threshold = float(q.get("threshold"))
        except (TypeError, ValueError):
            raise RungError("the threshold is a number", code="bad_request", status=400, field="threshold")
        direction = q.get("direction", "max")
        if direction not in ("max", "min"):
            raise RungError("direction is max or min", code="bad_request", status=400, field="direction")
        out.update({"measure": measure, "threshold": threshold, "direction": direction,
                    "unit": str(q.get("unit") or "").strip()})
        return out

    # ------------------------------------------------------------------ journeys, regression, environment

    def set_milestone_system(self, project: str, mid: str, field: str, value, actor=None) -> dict:
        """Journeys (SYS-07), regression baseline (SYS-08) or environment (SYS-10) of a milestone. Each changes
        what the milestone is judged on, so it makes a new version a person approves."""
        from .core import HUMAN, RungError
        actor = actor or HUMAN
        self._require_human(actor, "sets a milestone's " + str(field))
        with self._lock:
            self._check_writable(project, None)
            m = self._milestone_row(project, mid)
            sysd = _l(m["system"], {}) or {}
            if field == "journeys":
                sysd["journeys"] = self._clean_journeys(m, value)
            elif field == "baseline":
                sysd["baseline"] = self._clean_baseline(m, value)
            elif field == "environment":
                sysd["environment"] = self._clean_env(value)
            else:
                raise RungError("field is journeys, baseline or environment", code="bad_request", status=400)
            now = self.clock()
            with self._tx() as c:
                c.execute("UPDATE milestones SET system=? WHERE pk=?", (_j(sysd), m["pk"]))
                self._bump(c, m, now)
                self._log(c, m["project_pk"], "milestone_" + field + "_set", {"milestone": m["mid"]}, actor.name)
                self._touch_project(c, m["project_pk"])
        return self.milestone(project, mid)

    def _clean_journeys(self, m, value) -> list:
        from .core import RungError
        if not isinstance(value, list):
            raise RungError("journeys is a list", code="bad_request", status=400, field="journeys")
        cids = {ch["cid"] for ch in self._check_rows(m)}
        out, seen = [], set()
        for j in value:
            if not isinstance(j, dict):
                raise RungError("each journey is an object", code="bad_request", status=400, field="journeys")
            name = str(j.get("name") or "").strip()
            if not name or name in seen:
                raise RungError("each journey has its own name", code="bad_request", status=400, field="name")
            seen.add(name)
            ins = j.get("in_scope", True) is not False
            reason = str(j.get("reason") or "").strip()
            if not ins and not reason:
                raise RungError(f"journey {name} is out of scope: say why", code="bad_request", status=400,
                                field="reason")
            chk = str(j.get("check") or "").strip() or None
            if chk and chk not in cids:
                raise RungError(f"no check {chk} on {m['mid']}", code="bad_request", status=400, field="check")
            out.append({"name": name, "in_scope": ins, "reason": "" if ins else reason, "check": chk if ins else None})
        return out

    def _clean_baseline(self, m, value) -> dict:
        from .core import RungError
        value = value if isinstance(value, dict) else {"milestones": value}
        mids = value.get("milestones") or []
        if not isinstance(mids, list):
            raise RungError("milestones is a list", code="bad_request", status=400, field="milestones")
        out = []
        for x in mids:
            r = self._q1("SELECT * FROM milestones WHERE project_pk=? AND mid=?", (m["project_pk"], str(x).strip().upper()))
            if r is None:
                raise RungError(f"no milestone {x}", code="bad_request", status=400, field="milestones")
            if r["num"] >= m["num"]:
                raise RungError(f"{r['mid']} is not an earlier milestone than {m['mid']}", code="bad_request",
                                status=400, field="milestones")
            if r["mid"] not in out:
                out.append(r["mid"])
        return {"milestones": out, "command": str(value.get("command") or "").strip()}

    def _clean_env(self, value) -> dict:
        from .core import RungError
        if not isinstance(value, dict):
            raise RungError("environment is an object", code="bad_request", status=400, field="environment")
        probes = []
        for pr in value.get("probes") or []:
            cmd, want = str((pr or {}).get("command") or "").strip(), str((pr or {}).get("contains") or "")
            if not cmd or not want:
                raise RungError("each probe has a command and the output it must contain", code="bad_request",
                                status=400, field="probes")
            probes.append({"command": cmd, "contains": want})
        return {"probes": probes, "migration": str(value.get("migration") or "").strip()}

    def _setup_key(self, env) -> str:
        return _j(env or {})

    def _run_environment(self, m, root, env) -> dict:
        """Probes, then the migration, on the project folder. Records what each printed; nothing else."""
        rec = {"setup": self._setup_key(env), "at": self.clock(), "probes": [], "migration": None, "ok": True,
               "code": ""}
        for pr in env.get("probes", []):
            res = run_command(pr["command"], root, timeout=60, output_limit=4000)
            out = (res.output or "").strip()
            ok = res.exit_code == 0 and pr["contains"] in out
            rec["probes"].append({**pr, "output": out, "exit_code": res.exit_code, "ok": ok})
            if not ok and rec["ok"]:
                rec["ok"], rec["code"] = False, "environment_mismatch"
        if rec["ok"] and env.get("migration"):
            res = run_command(env["migration"], root, timeout=300, output_limit=8000)
            rec["migration"] = {"command": env["migration"], "exit_code": res.exit_code,
                                "output": (res.output or "")[-4000:], "ok": res.exit_code == 0}
            if res.exit_code != 0:
                rec["ok"], rec["code"] = False, "migration_failed"
        return rec

    def _system_blockers(self, m, cur: str) -> list[dict]:
        """Journeys, regression baseline and environment of an approved milestone, as blockers."""
        sysd = _l(m["system"], {}) or {}
        out = []
        env = sysd.get("environment")
        if env and (env.get("probes") or env.get("migration")):
            rec = sysd.get("env_run")
            if not rec or rec.get("setup") != self._setup_key(env):
                out.append({"code": "environment_not_checked", "text": f"{m['mid']}'s environment has not been checked"})
            elif rec.get("code") == "environment_mismatch":
                bad = next(p for p in rec["probes"] if not p["ok"])
                out.append({"code": "environment_mismatch", "text": f"probe {bad['command']} must print "
                            f"{bad['contains']}; it printed {bad['output'][:120] or 'nothing'}", "probe": bad["command"]})
            elif rec.get("code") == "migration_failed":
                out.append({"code": "migration_failed", "text": f"migration {rec['migration']['command']} exited "
                            f"{rec['migration']['exit_code']}"})
        checks = {ch["cid"]: ch for ch in self._check_rows(m)}
        for j in sysd.get("journeys", []):
            if j["in_scope"] and (not j.get("check") or j["check"] not in checks):
                out.append({"code": "journey_unchecked", "text": f"journey {j['name']} has no check", "journey": j["name"]})
        base = sysd.get("baseline") or {}
        for b in base.get("milestones", []):
            br = self._q1("SELECT * FROM milestones WHERE project_pk=? AND mid=?", (m["project_pk"], b))
            if br is None:
                continue
            vb = self._milestone_verdict(br, fresh=False)
            if vb["ok"]:
                continue
            first = vb["blockers"][0]["text"] if vb["blockers"] else vb["state"]
            if vb["state"] in ("integration_failed", "obligation_unmet"):
                out.append({"code": "regression_failed", "text": f"regression: {b} fails on this code: {first}",
                            "milestone": b})
            else:
                out.append({"code": "regression_not_verified", "text": f"regression: {b} is not verified on this code: "
                            f"{first}", "milestone": b})
        if base.get("command"):
            br = sysd.get("baseline_run")
            if not br or br.get("command") != base["command"]:
                out.append({"code": "regression_not_run", "text": f"baseline command {base['command']} has not run"})
            elif br.get("basis") != cur:
                out.append({"code": "out_of_date", "text": f"baseline command {base['command']} ran on code that has "
                            "changed since"})
            elif br.get("status") != "pass":
                out.append({"code": "regression_failed", "text": f"regression: baseline command {base['command']} "
                            f"exited {br.get('exit_code')}"})
        return out

    def _m_comps(self, m) -> list:
        return (_l(m["system"], {}) or {}).get("components", []) if "system" in m.keys() else []

    def _milestone_verdict(self, m, fresh: bool = True) -> dict:
        p = self._project_row(m["project_pk"])
        cur = evidence.basis(p["folder"], fresh=fresh)
        mcur = self._scope_cur(m["project_pk"], self._m_comps(m), cur)  # SYS-11: judged on its components' paths
        blockers = []

        def block(code, text, **kw):
            blockers.append({"code": code, "text": text, **kw})

        comps = _l(m["system"], {}).get("components", []) if "system" in m.keys() else []
        scope = []
        for rid, r in self._scope_rows(m):
            if r is None or r["status"] in ("dismissed", "proposed"):
                scope.append({"id": rid, "verification": "missing", "ok": False})
                block("scope_missing", f"{rid} is no longer in the ladder", rung=rid)
                continue
            v = self._verify(r, cur)
            scope.append({"id": rid, "text": r["text"], "verification": v["verification"], "ok": v["ok"],
                          "basis": evidence.short(v["basis"])})
            if not v["ok"]:
                first = v["blockers"][0]["text"] if v["blockers"] else ""
                block("not_ready", f"{rid} is not verified: {first}", rung=rid, cause=(v["next_action"] or {}))
        checks = [self._check_state(m, ch, mcur) for ch in self._check_rows(m)]
        comps = _l(m["system"], {}).get("components", []) if "system" in m.keys() else []
        if m["status"] == "approved":
            for ch in self._contract_changes(m["project_pk"], comps):  # SYS-02: approve the milestone again
                if (m["approved_at"] or 0) < (ch["at"] or 0):
                    block("contract_changed", f"contract {ch['contract']} v{ch['version']} was approved after "
                                              f"{m['mid']} was approved", contract=ch["contract"])
        if m["status"] != "approved":
            state = "draft"
            block("draft", f"{m['mid']} is not approved", milestone=m["mid"])
        elif any(b["code"] == "contract_changed" for b in blockers):
            state = "out_of_date"
        elif any(b["code"] in ("not_ready", "scope_missing") for b in blockers):
            stale = [s for s in scope if not s["ok"]]
            # SYS-11: a milestone judged on its components' paths, whose unverified specifications are only out
            # of date, is Out of date (a change inside its paths); otherwise Not ready, as before
            scoped = self._scope_paths(m["project_pk"], comps) is not None
            state = ("out_of_date" if scoped and stale and all(s["verification"] == "out_of_date" for s in stale)
                     else "not_ready")
        else:
            blockers.extend(self._contract_check_blockers(m["project_pk"], comps, cur))  # SYS-06
            blockers.extend(self._system_blockers(m, cur))  # SYS-07, SYS-08, SYS-10
            jname = {j.get("check"): j["name"] for j in (_l(m["system"], {}) or {}).get("journeys", []) if j.get("check")}
            for ch in checks:
                if not ch["required"] and ch["state"] != "failed":
                    continue
                s, cid, n = ch["state"], ch["check"], ch["run"]
                if s == "satisfied":
                    continue
                if s == "quality_unmet":
                    block("quality_unmet", f"{cid} {ch['quality']['category']}: measured {ch['measured_text']}",
                          check=cid, run=n)
                    continue
                text = {"missing": f"{cid} has not run on this scope",
                        "checking": f"{cid} is running (#{n})",
                        "could_not_verify": f"{cid} could not run (#{n})",
                        "failed": f"{cid} failed (#{n})",
                        "out_of_date": f"{cid} {'failed' if ch.get('was') == 'fail' else 'passed'} (#{n}) on code "
                                       "that has changed since"}[s]
                if s == "missing" and ch["type"] == "manual":
                    text = f"{cid} is a required manual acceptance with no result yet"
                if s == "could_not_verify" and ch.get("reason") == "no_measurement":
                    text = f"{cid} printed no measurement matching {ch['quality']['measure']} (#{n})"
                if cid in jname:
                    text = f"journey {jname[cid]}: {text}"
                block({"missing": "manual_missing" if ch["type"] == "manual" else "not_run",
                       "checking": "checking", "could_not_verify": ch.get("reason") if ch.get("reason") ==
                       "verification_changed" else "could_not_verify", "failed": "failed",
                       "out_of_date": "out_of_date"}[s], text, check=cid, run=n)
            codes = {b["code"] for b in blockers}
            if not blockers:
                state = "verified"
            elif "contract_changed" in codes:
                state = "out_of_date"
            elif codes & {"failed", "contract_failed", "regression_failed", "migration_failed"}:
                state = "integration_failed"
            elif "quality_unmet" in codes:
                state = "obligation_unmet"
            elif "checking" in codes:
                state = "verifying"
            elif codes & {"could_not_verify", "verification_changed", "environment_mismatch"}:
                state = "could_not_verify"
            elif codes & {"out_of_date", "contract_out_of_date"}:
                state = "out_of_date"
            elif codes == {"manual_missing"}:
                state = "awaiting_manual"
            else:
                state = "ready"
        nxt = None
        if blockers:
            b = blockers[0]
            nxt = {"draft": {"kind": "approve_milestone"}, "not_ready": {"kind": "verify_scope", "rung": b.get("rung")},
                   "scope_missing": {"kind": "edit_milestone"}, "manual_missing": {"kind": "record_manual_result",
                                                                                     "check": b.get("check")},
                   "verification_changed": {"kind": "review_check_files", "check": b.get("check")},
                   "checking": {"kind": "wait"}, "failed": {"kind": "repair", "check": b.get("check")},
                   "contract_changed": {"kind": "approve_milestone"},
                   "contract_failed": {"kind": "repair_contract", "contract": b.get("contract")},
                   "journey_unchecked": {"kind": "edit_milestone"},
                   "environment_mismatch": {"kind": "repair_environment", "probe": b.get("probe")},
                   "migration_failed": {"kind": "repair_environment"},
                   "regression_failed": {"kind": "repair", "milestone": b.get("milestone")},
                   "quality_unmet": {"kind": "repair", "check": b.get("check")},
                   "contract_out_of_date": {"kind": "run_contract_checks", "contract": b.get("contract")},
                   "contract_not_run": {"kind": "run_contract_checks", "contract": b.get("contract")},
                   "could_not_verify": {"kind": "repair_check_setup", "check": b.get("check")}}.get(
                b["code"], {"kind": "run_checks"})
        return {"milestone": m["mid"], "ok": not blockers, "state": state, "basis": evidence.short(mcur),
                "judged_on": self.scope_line(p["name"], self._m_comps(m)),
                "version": m["version"], "scope": scope, "checks": checks, "blockers": blockers, "next_action": nxt}

    def set_milestone_components(self, project: str, mid: str, components, actor=None) -> dict:
        """The components a milestone touches (SYS-02). Naming them changes no checks, so no new version."""
        from .core import HUMAN
        actor = actor or HUMAN
        self._require_human(actor, "names a milestone's components")
        with self._lock:
            self._check_writable(project, None)
            m = self._milestone_row(project, mid)
            names = self._component_names(m["project_pk"], components)
            sysd = _l(m["system"], {}) or {}
            if sysd.get("components", []) != names:
                sysd["components"] = names
                with self._tx() as c:
                    c.execute("UPDATE milestones SET system=?, updated_at=? WHERE pk=?", (_j(sysd), self.clock(), m["pk"]))
                    self._log(c, m["project_pk"], "milestone_components_set", {"milestone": m["mid"], "components": names},
                              actor.name)
                    self._touch_project(c, m["project_pk"])
        return self.milestone(project, mid)

    def _milestone_dict(self, m, fresh: bool = True) -> dict:
        v = self._milestone_verdict(m, fresh)
        return {"id": m["mid"], "title": m["title"], "journey": m["journey"], "architecture": m["architecture"],
                "components": (_l(m["system"], {}) or {}).get("components", []) if "system" in m.keys() else [],
                "journeys": (_l(m["system"], {}) or {}).get("journeys", []),
                "baseline": (_l(m["system"], {}) or {}).get("baseline") or {"milestones": [], "command": ""},
                "environment": (_l(m["system"], {}) or {}).get("environment") or {"probes": [], "migration": ""},
                "env_run": (_l(m["system"], {}) or {}).get("env_run"),
                "status": m["status"], "version": m["version"], "approved_by": m["approved_by"],
                "approved_at": m["approved_at"], "created_at": m["created_at"], **v}

    def milestone(self, project: str, mid: str) -> dict:
        return self._milestone_dict(self._milestone_row(project, mid))

    def milestones(self, project: str, fresh: bool = False) -> list[dict]:
        """Every milestone of a project with its verdict. Lists read the cached code basis (one second)."""
        p = self._project_row(project)
        return [self._milestone_dict(m, fresh) for m in self._q("SELECT * FROM milestones WHERE project_pk=? ORDER BY num",
                                                          (p["pk"],))]

    def milestone_runs(self, project: str, mid: str, cid: str) -> list[dict]:
        m = self._milestone_row(project, mid)
        ch = self._q1("SELECT * FROM milestone_checks WHERE milestone_pk=? AND cid=?", (m["pk"], str(cid).strip()))
        if ch is None:
            return []
        return [{k: r[k] for k in ("n", "version", "status", "exit_code", "output", "reason", "note", "carried_by",
                                   "started_at", "ended_at")} | {"basis": evidence.short(r["basis_end"] or r["basis_start"]),
                                                                  "current_scope": r["version"] == m["version"]}
                for r in self._q("SELECT * FROM milestone_runs WHERE check_pk=? ORDER BY n DESC", (ch["pk"],))]

    def milestone_markdown(self, project: str, mid: str) -> str:
        v = self.milestone(project, mid)
        word = {"draft": "Draft", "not_ready": "Not ready for integration", "ready": "Ready for integration",
                "verifying": "Verifying", "integration_failed": "Integration failed", "could_not_verify":
                "Could not verify", "awaiting_manual": "Awaiting manual acceptance", "out_of_date": "Out of date",
                "verified": "Verified", "obligation_unmet": "Obligation not met"}[v["state"]]
        stamp = time.strftime("%Y-%m-%d %H:%M", time.localtime(self.clock()))
        out = [f"# {v['id']} {v['title']}", "", f"State: {word}", f"Project: {self._project_row(project)['name']}",
               f"Code basis: {v['basis']}", f"Contract version: {v['version']}"
               + (f", approved by {v['approved_by']}" if v["approved_by"] else ", not approved"),
               f"Written: {stamp}", "", "## Journey", "", v["journey"], ""]
        if v["architecture"]:
            out += ["## Architecture and constraints (reference, not checked by Rung)", "", v["architecture"], ""]
        out += ["## Included work", ""]
        out += [f"- {s['id']} {s.get('text', '')}: {s['verification'].replace('_', ' ')}"
                + (f", on code {s['basis']}" if s.get("basis") else "") for s in v["scope"]]
        out += ["", "## Checks", ""]
        for ch in v["checks"]:
            what = ch["command"] or "; ".join(ch["steps"])
            res = f"#{ch['run']} {ch['state'].replace('_', ' ')}" if ch["run"] else "not run"
            out.append(f"- {ch['check']} {ch['type']}{'' if ch['required'] else ' (optional)'}: {what} ({res}"
                       + (f", on code {ch['basis']}" if ch.get("basis") else "") + ")")
        if v["journeys"]:
            out += ["", "## Journeys", ""]
            out += [f"- {j['name']}: " + (f"in scope, check {j['check'] or 'none'}" if j["in_scope"] else
                                          f"out of scope ({j['reason']}), not counted as passed") for j in v["journeys"]]
        qual = [ch for ch in v["checks"] if ch.get("quality")]
        if qual:
            out += ["", "## Quality obligations", ""]
            for ch in qual:
                q = ch["quality"]
                out.append(f"- {ch['check']} {q['category']}: " + (
                    "required human review" if q.get("review") else
                    f"{'at most' if q['direction'] == 'max' else 'at least'} {q['threshold']:g} {q.get('unit', '')}"
                    f" under {q.get('workload') or 'no stated workload'}, environment {q.get('environment') or 'not stated'}")
                    + (f"; measured {ch['measured_text']}" if ch.get("measured_text") else f"; {ch['state'].replace('_', ' ')}"))
        if v["environment"]["probes"] or v["environment"]["migration"]:
            out += ["", "## Environment", ""]
            rec = v.get("env_run") or {}
            for pr in v["environment"]["probes"]:
                got = next((x for x in rec.get("probes", []) if x["command"] == pr["command"]), None)
                out.append(f"- probe {pr['command']} must print {pr['contains']}: "
                           + (f"printed {got['output'][:80]}" if got else "not run"))
            if v["environment"]["migration"]:
                mg = rec.get("migration")
                out.append(f"- migration {v['environment']['migration']}: "
                           + (f"exited {mg['exit_code']}" if mg else "not run"))
        if v["baseline"]["milestones"] or v["baseline"]["command"]:
            out += ["", "## Regression baseline", ""]
            out += [f"- {b}" for b in v["baseline"]["milestones"]]
            if v["baseline"]["command"]:
                out.append(f"- command {v['baseline']['command']}")
        out += ["", "## Blockers", ""]
        out += [f"- {b['text']}" for b in v["blockers"]] or ["- none"]
        out += ["", "Rung verifies the declared journey against the current code basis. It does not check "
                    "architecture conformance, performance or deployment.", ""]
        return "\n".join(out)

    def export_milestone(self, project: str, mid: str) -> dict:
        text = self.milestone_markdown(project, mid)
        m = self._milestone_row(project, mid)
        folder = Path(self.path).expanduser().resolve().parent / "exports"
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"{self._project_row(project)['name']}-{m['mid']}.md"
        path.write_text(text, encoding="utf-8")
        return {"markdown": text, "path": str(path)}
