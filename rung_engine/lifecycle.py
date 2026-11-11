# pyright: reportAttributeAccessIssue=false
"""Project and need lifecycle, onboarding, the sample project and the need read-out.

A mixin of `Engine`: every write here still goes through `Engine._tx`, so the engine stays the
single write path for the pane, the CLI and the agent tools.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from . import evidence

SAMPLE_NAME = "sample"
SAMPLE_SRC = Path(__file__).resolve().parent / "sample" / "wordcount"
SAMPLE_NEED = "Count the words in a text file"
SAMPLE_REQ = "Count words separated by any whitespace"
SAMPLE_SPEC = "Split on runs of spaces, tabs and newlines; an empty text has zero words"
SAMPLE_TEST = "python3 -m unittest -q"

CHECKLIST = (
    ("write_need", "Write a need"),
    ("approve_requirements", "Approve requirements"),
    ("approve_specifications", "Approve specifications"),
    ("approve_tests", "Approve tests"),
    ("first_green", "First green test"),
)


def _j(v) -> str:
    return json.dumps(v, separators=(",", ":"), sort_keys=True)


class LifecycleMixin:
    # ------------------------------------------------------------------ read only guard and log

    def _check_writable(self, project: str, rid: str | None = None) -> None:
        from .core import RungError
        p = self._project_row(project)
        if p["archived_at"] is not None:
            raise RungError(f"{p['name']} is archived; restore it to change it", code="read_only")
        if rid:
            from .claims import _canon
            r = self._q1("SELECT * FROM rungs WHERE project_pk = ? AND rid = ?", (p["pk"], _canon(rid)))
            need = self._need_of(r) if r is not None else None
            if need is not None and need["retired_at"] is not None:
                raise RungError(f"{need['rid']} is retired; restore it to change it", code="read_only")

    def _log(self, c, project_pk, kind: str, data: dict, by: str) -> None:
        c.execute("INSERT INTO events(project_pk, kind, data, by_name, at) VALUES (?,?,?,?,?)",
                  (project_pk, kind, _j(data), by, self.clock()))

    def events(self, project: str | None = None) -> list[dict]:
        if project is None:
            rows = self._q("SELECT * FROM events WHERE project_pk IS NULL ORDER BY pk")
        else:
            rows = self._q("SELECT * FROM events WHERE project_pk = ? ORDER BY pk", (self._project_row(project)["pk"],))
        return [{"kind": r["kind"], "data": json.loads(r["data"]), "by": r["by_name"], "at": r["at"]} for r in rows]

    # ------------------------------------------------------------------ projects

    def update_project(self, name: str, new_name: str | None = None, folder: str | None = None,
                       test_command: str | None = None, profiles: list[str] | None = None, env_vars=None,
                       actor=None) -> dict:
        from .core import HUMAN, RungError
        actor = actor or HUMAN
        if not actor.is_human:
            raise RungError("only a human changes a project", code="forbidden", status=403)
        self._check_writable(name)
        p = self._project_row(name)
        before = {"name": p["name"], "folder": p["folder"], "test_command": p["test_command"],
                  "profiles": json.loads(p["profiles"] or "[]"), "env_vars": self._env_vars(p)}
        from .core import FieldErrors, _env_var_list, _profile_list, _text_field
        after = dict(before)
        errs = FieldErrors()
        if new_name is not None:
            after["name"] = _text_field(new_name, "name")
            errs.check(self._check_name, after["name"], p["pk"])
        if folder is not None:
            after["folder"] = _text_field(folder, "folder")
            errs.check(self._check_folder, after["folder"])
            after["folder"] = str(Path(after["folder"]).expanduser())
        if test_command is not None:
            after["test_command"] = _text_field(test_command, "test_command")  # may be cleared: it is optional
        if profiles is not None:
            after["profiles"] = errs.check(_profile_list, profiles) or []
            if not after["profiles"] and "profiles" not in errs.errors:
                errs.errors.setdefault("profiles", "tick at least one profile")
        if env_vars is not None:
            after["env_vars"] = errs.check(_env_var_list, env_vars)
        errs.raise_any()
        changed = {k: {"before": before[k], "after": after[k]} for k in before if before[k] != after[k]}
        if not changed:
            return self.project(name)
        with self._tx() as c:
            if after["name"] != before["name"]:
                # A develop run, a draft being written and a running test address the project by name.
                self._refuse_while_busy(p["pk"], before["name"], claims=False)
            gone = [x for x in before["profiles"] if x not in after["profiles"]]
            held = self._q1("SELECT c.profile, s.rid FROM claims c JOIN rungs s ON s.pk = c.spec_pk WHERE c.status='open' "
                            f"AND s.project_pk = ? AND c.profile IN ({','.join('?' * len(gone))})",
                            (p["pk"], *gone)) if gone else None
            if held is not None:
                raise RungError(f"{held['profile']} holds the claim on {held['rid']}; release it first",
                                field="profiles")
            c.execute("UPDATE projects SET name=?, folder=?, test_command=?, profiles=?, env_vars=?, last_activity=? "
                      "WHERE pk=?", (after["name"], after["folder"], after["test_command"], _j(after["profiles"]),
                                     _j(after["env_vars"]), self.clock(), p["pk"]))
            self._log(c, p["pk"], "project_changed", changed, actor.name)
            if self.get_setting("last_project") == name:
                c.execute("INSERT OR REPLACE INTO settings(key, value) VALUES ('last_project', ?)", (_j(after["name"]),))
        return self.project(after["name"])

    def _refuse_while_busy(self, project_pk, what: str, pks=None, claims: bool = True) -> None:
        """Archive, delete and retire wait for work in flight: a develop run, a draft being written or a test
        execution still running would otherwise land in a read-only or removed ladder."""
        from .core import RungError
        scope, args = ("project_pk = ?", [project_pk]) if pks is None else \
            (f"pk IN ({','.join('?' * len(pks))})", list(pks))
        if self._q1(f"SELECT 1 FROM runs WHERE status IN ('queued','running') AND "
                    f"{'project_pk = ?' if pks is None else 'spec_pk IN (' + ','.join('?' * len(pks)) + ')'}", args):
            raise RungError(f"{what} has a running develop run; stop it first")
        if self._q1(f"SELECT 1 FROM rungs WHERE {scope} AND kind='specification' AND "
                    "json_extract(data, '$.draft_state') = 'drafting'", args):
            raise RungError(f"{what} has a specification being drafted; wait for the draft first")
        if self._q1(f"SELECT 1 FROM executions e JOIN rungs t ON t.pk = e.test_pk WHERE e.status = 'running' AND "
                    f"{'t.project_pk = ?' if pks is None else 't.pk IN (' + ','.join('?' * len(pks)) + ')'}", args):
            raise RungError(f"{what} has a test running; wait for it first")
        # An open claim is work in flight too: in a read-only ladder its chat could never report it and
        # the done hook would hold that chat's completions for good.
        if claims and self._q1(f"SELECT 1 FROM claims WHERE status = 'open' AND "
                    f"{'project_pk = ?' if pks is None else 'spec_pk IN (' + ','.join('?' * len(pks)) + ')'}", args):
            raise RungError(f"{what} has an open claim; release it first")

    def archive_project(self, name: str, actor=None) -> dict:
        from .core import HUMAN, RungError
        actor = actor or HUMAN
        if not actor.is_human:
            raise RungError("only a human archives a project", code="forbidden", status=403)
        p = self._project_row(name)
        if p["archived_at"] is not None:
            raise RungError(f"{name} is already archived")
        with self._tx() as c:
            # Checked inside the write transaction: no claim, run or draft can start in between.
            self._refuse_while_busy(p["pk"], name)
            c.execute("UPDATE projects SET archived_at=? WHERE pk=?", (self.clock(), p["pk"]))
            self._log(c, p["pk"], "project_archived", {}, actor.name)
        return self.project(name)

    def restore_project(self, name: str, actor=None) -> dict:
        from .core import HUMAN, RungError
        actor = actor or HUMAN
        if not actor.is_human:
            raise RungError("only a human restores a project", code="forbidden", status=403)
        p = self._project_row(name)
        if p["archived_at"] is None:
            raise RungError(f"{name} is not archived")
        with self._tx() as c:
            c.execute("UPDATE projects SET archived_at=NULL, last_activity=? WHERE pk=?", (self.clock(), p["pk"]))
            self._log(c, p["pk"], "project_restored", {}, actor.name)
        return self.project(name)

    def delete_project(self, name: str, confirm: str, actor=None) -> dict:
        """Remove the project's Rung data. The project folder is never touched."""
        from .core import HUMAN, RungError
        actor = actor or HUMAN
        if not actor.is_human:
            raise RungError("only a human deletes a project", code="forbidden", status=403)
        p = self._project_row(name)
        if (confirm or "") != p["name"]:
            raise RungError("type the project name to delete it", code="bad_request", status=400, field="confirm")
        with self._tx() as c:
            self._refuse_while_busy(p["pk"], name)
            c.execute("DELETE FROM projects WHERE pk=?", (p["pk"],))
            self._log(c, None, "project_deleted", {"name": p["name"], "folder": p["folder"]}, actor.name)
            if self.get_setting("last_project") == name:
                c.execute("DELETE FROM settings WHERE key='last_project'")
        return {"deleted": p["name"], "folder_kept": p["folder"], "current": self.current_project()}

    # ------------------------------------------------------------------ retire and restore a need

    def retire_need(self, project: str, rid: str, reason: str, actor=None) -> dict:
        from .core import HUMAN, RungError
        actor = actor or HUMAN
        if not actor.is_human:
            raise RungError("only a human retires a need", code="forbidden", status=403)
        self._check_writable(project)
        n = self._rung_row(project, rid)
        if n["kind"] != "need":
            raise RungError(f"{rid} is not a need", code="bad_request", status=400)
        if n["retired_at"] is not None:
            raise RungError(f"{rid} is already retired")
        reason = (reason or "").strip()
        if not reason:
            raise RungError("a reason is required", code="bad_request", status=400, field="reason")
        sub = [n["pk"]] + [r["pk"] for r in self._descendants(n["pk"])]
        marks = ",".join("?" * len(sub))
        with self._tx() as c:
            self._refuse_while_busy(n["project_pk"], rid, sub)
            c.execute("UPDATE rungs SET retired_at=?, retired_reason=?, retired_by=? WHERE pk=?",
                      (self.clock(), reason[:500], actor.name, n["pk"]))
            self._log(c, n["project_pk"], "need_retired", {"need": rid, "reason": reason[:500]}, actor.name)
            self._touch_project(c, n["project_pk"])
        return self.rung(project, rid)

    def restore_need(self, project: str, rid: str, actor=None) -> dict:
        """Statuses are never changed by retiring, so restoring brings back exactly what was there."""
        from .core import HUMAN, RungError
        actor = actor or HUMAN
        if not actor.is_human:
            raise RungError("only a human restores a need", code="forbidden", status=403)
        self._check_writable(project)
        n = self._rung_row(project, rid)
        if n["kind"] != "need" or n["retired_at"] is None:
            raise RungError(f"{rid} is not a retired need")
        with self._tx() as c:
            c.execute("UPDATE rungs SET retired_at=NULL, retired_reason=NULL, retired_by=NULL WHERE pk=?", (n["pk"],))
            self._log(c, n["project_pk"], "need_restored", {"need": rid}, actor.name)
            self._touch_project(c, n["project_pk"])
        return self.rung(project, rid)

    # ------------------------------------------------------------------ onboarding

    def onboarding(self) -> dict:
        st = self.get_setting("onboarding")
        any_project = self._q1("SELECT 1 FROM projects") is not None
        return {"start": not any_project and not st.get("start_dismissed"),
                "start_dismissed": bool(st.get("start_dismissed")),
                "checklist_hidden": bool(st.get("checklist_hidden"))}

    def set_onboarding(self, start_dismissed: bool | None = None, checklist_hidden: bool | None = None) -> dict:
        st = self.get_setting("onboarding")
        if start_dismissed is not None:
            st["start_dismissed"] = bool(start_dismissed)
        if checklist_hidden is not None:
            st["checklist_hidden"] = bool(checklist_hidden)
        self.set_setting("onboarding", st)
        return self.onboarding()

    def first_green(self, project: str) -> dict:
        """The First green checklist, every tick computed from stored state."""
        p = self._project_row(project)
        gone = self._retired_pks(p["pk"])

        def any_row(sql, args=()):
            return any(r["pk"] not in gone for r in self._q(sql, (p["pk"], *args)))

        done = {
            "write_need": any_row("SELECT pk FROM rungs WHERE project_pk=? AND kind='need' AND status='approved'"),
            "approve_requirements": any_row("SELECT pk FROM rungs WHERE project_pk=? AND kind='requirement' "
                                            "AND status='approved'"),
            "approve_specifications": any_row("SELECT pk FROM rungs WHERE project_pk=? AND kind='specification' "
                                              "AND status='approved'"),
            "approve_tests": any(r["pk"] not in gone and json.loads(r["data"] or "{}").get("tests_approved")
                                 for r in self._q("SELECT pk, data FROM rungs WHERE project_pk=? AND kind='need'",
                                                  (p["pk"],))),
            "first_green": any_row("SELECT t.pk FROM executions e JOIN rungs t ON t.pk=e.test_pk WHERE t.project_pk=? "
                                   "AND e.kind='command' AND e.status='pass'"),
        }
        items = [{"key": k, "label": label, "done": bool(done[k])} for k, label in CHECKLIST]
        return {"items": items, "done": sum(1 for i in items if i["done"]), "total": len(items),
                "hidden": bool(self.get_setting("onboarding").get("checklist_hidden"))}

    # ------------------------------------------------------------------ sample project

    def samples_dir(self) -> Path:
        return Path(self.path).expanduser().resolve().parent / "samples"

    def _is_sample(self, row) -> bool:
        try:
            folder = Path(row["folder"]).expanduser().resolve()
        except (OSError, RuntimeError):
            return False
        return row["name"] == SAMPLE_NAME and folder.parent == self.samples_dir().resolve()

    def create_sample(self, actor=None) -> dict:
        """Copy the bundled synthetic sample into Rung's data folder and build its ladder through the
        ordinary engine calls: one need, approved down to its command test, which has never run."""
        from .core import HUMAN, RungError
        actor = actor or HUMAN
        if not actor.is_human:
            raise RungError("only a human creates the sample", code="forbidden", status=403)
        if self._q1("SELECT 1 FROM projects WHERE name=?", (SAMPLE_NAME,)):
            raise RungError(f"a project named {SAMPLE_NAME} exists", code="conflict", field="name")
        folder = self.samples_dir() / SAMPLE_NAME
        if folder.exists():
            shutil.rmtree(folder)
        folder.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(SAMPLE_SRC, folder, ignore=shutil.ignore_patterns("__pycache__"))
        profiles = [p["name"] for p in self.profiles() if p["enabled"]] or ["default"]
        self.create_project(SAMPLE_NAME, str(folder), SAMPLE_TEST, profiles)
        self.create_need(SAMPLE_NAME, SAMPLE_NEED, actor)
        self.add_requirement(SAMPLE_NAME, "N-1", SAMPLE_REQ, actor)
        self.approve_requirements(SAMPLE_NAME, "N-1", actor)
        self.write_spec(SAMPLE_NAME, "R-1", SAMPLE_SPEC, actor=actor, tags=["python", "tests"])
        self.approve_drafted(SAMPLE_NAME, "N-1", actor)
        self.add_test(SAMPLE_NAME, "S-1.1", {"type": "command", "command": SAMPLE_TEST}, actor, status="approved")
        self.approve_tests(SAMPLE_NAME, "N-1", actor)
        self.open_project(SAMPLE_NAME)
        return self.project(SAMPLE_NAME)

    def reset_sample(self, actor=None) -> dict:
        """`hermes rung demo reset`: recreate the sample. Only a project that is the sample (its name and its
        folder inside Rung's samples folder) is removed; any other project is never touched."""
        from .core import HUMAN, RungError
        actor = actor or HUMAN
        row = self._q1("SELECT * FROM projects WHERE name=?", (SAMPLE_NAME,))
        if row is not None:
            if not self._is_sample(row):
                raise RungError(f"the project named {SAMPLE_NAME} is not Rung's sample; rename it first",
                                code="conflict", field="name")
            self.delete_project(SAMPLE_NAME, SAMPLE_NAME, actor)
        last = self.get_setting("last_project")
        made = self.create_sample(actor)
        if last and last != SAMPLE_NAME and self._q1("SELECT 1 FROM projects WHERE name=?", (last,)):
            self.set_setting("last_project", last)
        return made

    # ------------------------------------------------------------------ answer the worker (Round 24, U04)

    def answer_run(self, project: str, run_id: int, answer: str, actor=None) -> dict:
        """A person answers the question a develop run stopped on. The answer is stored with the question and given
        to the next run of that specification (`run_answer`); the caller starts that run."""
        from .core import HUMAN, RungError
        actor = actor or HUMAN
        if not actor.is_human:
            raise RungError("only a human answers the worker", code="forbidden", status=403)
        answer = (answer or "").strip() if isinstance(answer, str) else ""
        if not answer:
            raise RungError("the answer is empty", code="bad_request", status=400, field="answer")
        with self._lock:
            p = self._project_row(project)
            r = self._q1("SELECT r.*, s.rid AS srid FROM runs r JOIN rungs s ON s.pk = r.spec_pk "
                         "WHERE r.pk=? AND r.project_pk=?", (int(run_id), p["pk"]))
            if r is None:
                raise RungError(f"no run {run_id} in {project}", code="not_found", status=404)
            if r["status"] != "needs_input":
                raise RungError(f"run {run_id} is not waiting for an answer", code="conflict", status=409)
            if self._q1("SELECT 1 FROM runs WHERE spec_pk=? AND pk>?", (r["spec_pk"], r["pk"])):
                raise RungError(f"a newer run of {r['srid']} exists", code="conflict", status=409)
            with self._tx() as c:
                self._log(c, p["pk"], "run_answered", {"run": r["pk"], "spec": r["srid"], "question": r["reason"] or "",
                                                        "answer": answer[:2000]}, actor.name)
                self._touch_project(c, p["pk"])
        return {"run": r["pk"], "spec": r["srid"], "profile": r["profile"], "question": r["reason"] or "", "answer": answer}

    def run_answer(self, project: str, spec_rid: str) -> dict | None:
        """The latest question a run of this specification asked and the person's answer, or None."""
        p = self._project_row(project)
        for e in reversed(self._q("SELECT * FROM events WHERE project_pk=? AND kind='run_answered' ORDER BY pk",
                                  (p["pk"],))):
            d = json.loads(e["data"])
            if d.get("spec") == spec_rid:
                return {"question": d.get("question", ""), "answer": d.get("answer", ""), "by": e["by_name"]}
        return None

    # ------------------------------------------------------------------ break and repair the sample (Round 24, U02)

    SAMPLE_FILE = "wordcount/count.py"
    SAMPLE_BREAK = ("return len(text.split())", "return len(text.split(\" \"))")

    def _sample_folder(self) -> Path:
        from .core import RungError
        row = self._q1("SELECT * FROM projects WHERE name=?", (SAMPLE_NAME,))
        if row is None or not self._is_sample(row):
            raise RungError("there is no sample project", code="not_found", status=404)
        if row["archived_at"] is not None:
            raise RungError("the sample is archived", code="read_only", status=409)
        return Path(row["folder"]).expanduser().resolve()

    def sample_state(self) -> dict | None:
        """Whether the sample's code is as bundled or broken by `Break the sample`; None when there is no sample."""
        row = self._q1("SELECT * FROM projects WHERE name=?", (SAMPLE_NAME,))
        if row is None or not self._is_sample(row):
            return None
        target = Path(row["folder"]).expanduser() / self.SAMPLE_FILE
        try:
            broken = target.read_text() != (SAMPLE_SRC / self.SAMPLE_FILE).read_text()
        except OSError:
            broken = True
        return {"broken": broken, "file": self.SAMPLE_FILE}

    def break_sample(self, actor=None) -> dict:
        """Change one line of the sample's code, as a person or an agent might: no bot runs, nothing else is
        touched. Its passing test is then Out of date until checked again on the new code."""
        return self._sample_write(actor, broken=True)

    def repair_sample(self, actor=None) -> dict:
        """Put the sample's file back as bundled. No bot runs."""
        return self._sample_write(actor, broken=False)

    def _sample_write(self, actor, broken: bool) -> dict:
        from . import evidence
        from .core import HUMAN, RungError
        actor = actor or HUMAN
        if not actor.is_human:
            raise RungError("only a human breaks or repairs the sample", code="forbidden", status=403)
        with self._lock:
            folder = self._sample_folder()
            target = (folder / self.SAMPLE_FILE).resolve()
            if not target.is_relative_to(folder):  # a symlink planted in the sample never leads outside it
                raise RungError("the sample file is outside the sample folder", code="forbidden", status=403)
            good = (SAMPLE_SRC / self.SAMPLE_FILE).read_text()
            target.write_text(good.replace(*self.SAMPLE_BREAK) if broken else good)
            evidence.forget(folder)
            p = self._project_row(SAMPLE_NAME)
            with self._tx() as c:
                self._log(c, p["pk"], "sample_broken" if broken else "sample_repaired", {"file": self.SAMPLE_FILE},
                          actor.name)
                self._touch_project(c, p["pk"])
        return {"broken": broken, "file": self.SAMPLE_FILE, "bot": False}

    # ------------------------------------------------------------------ need read-out

    def readout(self, project: str, rid: str) -> dict:
        """Intent, plan and delivered for one need, every value read from the store."""
        from .core import RungError
        n = self._rung_row(project, rid)
        if n["kind"] != "need":
            raise RungError(f"{rid} is not a need", code="bad_request", status=400)
        plan, delivered = [], []
        for req in self._children_rows(n["pk"]):
            if req["status"] in ("proposed",):
                continue
            specs = []
            proof, reasons = None, []
            for s in self._children_rows(req["pk"]):
                if s["status"] == "proposed":
                    continue
                tests = []
                for t in self._children_rows(s["pk"]):
                    if t["status"] == "proposed":
                        continue
                    data = json.loads(t["data"] or "{}")
                    ttype = data.get("type", "command")
                    result = self._test_result(t)
                    seen = self._seen_failing(t)
                    tests.append({"id": t["rid"], "type": ttype, "text": t["text"], "command": data.get("command", ""),
                                  "status": t["status"], "result": result, "seen_failing": seen})
                    if t["status"] not in ("approved", "stale"):
                        continue
                    counting = self._counting(t)
                    if counting and counting[0]["status"] == "pass" and t["status"] == "approved" and ttype != "ai_judged":
                        e = counting[0]
                        cand = {"test": t["rid"], "n": e["n"], "status": "pass", "at": e["ended_at"] or e["started_at"],
                                "carried_by": e["carried_by"], "seen_failing": seen, "kind": e["kind"],
                                "basis": evidence.short(e["basis_end"] or e["basis_start"])}
                        if proof is None or cand["at"] > proof["at"]:
                            proof = cand
                    reasons.append({"stale": "stale", "fail": "failing", "error": "error", "pending": "manual pending",
                                    "not_run": "not run", "running": "running", "out_of_date": "out of date"}.get(result, ""))
                specs.append({"id": s["rid"], "text": s["text"], "status": s["status"], "tests": tests})
            plan.append({"id": req["rid"], "text": req["text"], "status": req["status"], "specifications": specs})
            coverage = self._req_coverage(req)
            row = {"id": req["rid"], "text": req["text"], "coverage": coverage}
            if coverage == "covered" and proof is not None:
                row.update({"proven": True, "proof": proof, "reason": ""})
            else:
                why = "stale" if coverage == "stale" else "not approved" if coverage == "draft" else next(
                    (r for r in ("failing", "error", "manual pending", "out of date", "running", "not run") if r in reasons),
                    "no specification" if not specs else "not run")
                row.update({"proven": False, "proof": None, "reason": why})
            delivered.append(row)
        return {
            "project": self._project_row(n["project_pk"])["name"],
            "need": {"id": n["rid"], "text": n["text"], "version": n["version"], "status": n["status"],
                     "approved_by": n["approved_by"], "approved_at": n["approved_at"],
                     "retired": n["retired_at"] is not None, "retired_reason": n["retired_reason"]},
            "plan": plan,
            "delivered": delivered,
            "proven": sum(1 for d in delivered if d["proven"]),
            "total": len(delivered),
        }

    # ------------------------------------------------------------------ result first (Round 24, U12)

    def set_try(self, project: str, instruction: str = "", command: str = "", actor=None) -> dict:
        """Declare how a person tries the result: an instruction and an optional command. Rung shows both and
        never runs the command."""
        from .core import HUMAN, RungError
        actor = actor or HUMAN
        if not actor.is_human:
            raise RungError("only a human declares how to try the result", code="forbidden", status=403)
        if not isinstance(instruction, str) or not isinstance(command, str):
            raise RungError("instruction and command are text", code="bad_request", status=400)
        self._check_writable(project)
        value = {"instruction": instruction.strip()[:2000], "command": command.strip()[:500]}
        p = self._project_row(project)
        with self._tx() as c:
            c.execute("UPDATE projects SET try_it=? WHERE pk=?", (json.dumps(value, sort_keys=True), p["pk"]))
            self._log(c, p["pk"], "try_declared", value, actor.name)
            self._touch_project(c, p["pk"])
        return value

    def try_it(self, project: str) -> dict:
        p = self._project_row(project)
        v = json.loads(p["try_it"] or "{}") if "try_it" in p.keys() else {}
        return {"instruction": v.get("instruction", ""), "command": v.get("command", "")}

    def result(self, project: str, rid: str) -> dict:
        """The read-out's first part: the outcome and its verified behaviours, what the newest run changed, the
        checks run, the manual review left, the code basis, how to try it, and the labelled evidence. Every
        verdict is `verification()`'s; nothing here runs anything."""
        from .core import RungError
        n = self._rung_row(project, rid)
        if n["kind"] != "need":
            raise RungError(f"{rid} is not a need", code="bad_request", status=400)
        p = self._project_row(n["project_pk"])
        cur = self._root_basis(p["pk"], fresh=True)
        verified, checks, manual, optional, gone_stale, evidence_lines = [], [], [], [], [], []
        spec_pks = []
        for req in self._children_rows(n["pk"]):
            if req["status"] not in ("approved", "stale", "draft") or json.loads(req["data"] or "{}").get("out_of_scope"):
                continue
            for s in self._children_rows(req["pk"]):
                if s["status"] not in ("approved", "stale"):
                    continue
                spec_pks.append(s["pk"])
                v = self._verify(s, cur)
                if v["ok"]:
                    verified.append({"spec": s["rid"], "text": s["text"], "requirement": req["rid"]})
                for st in v["tests"]:
                    t = self._rung_row(project, st["test"])
                    data = json.loads(t["data"] or "{}")
                    if st["type"] == "manual" and not st["required"]:
                        optional.append({"test": st["test"], "text": t["text"], "state": st["state"]})
                    if st["type"] == "manual" and st["state"] != "satisfied":
                        manual.append({"test": st["test"], "text": t["text"], "required": st["required"],
                                       "state": st["state"]})
                    e = self._q1("SELECT * FROM executions WHERE test_pk=? AND status NOT IN ('running','cancelled') "
                                 "ORDER BY seq DESC LIMIT 1", (t["pk"],))
                    if e is None:
                        continue
                    label = "manual" if e["kind"] == "manual" else "model" if st["type"] == "ai_judged" else "automated"
                    row = {"test": st["test"], "spec": s["rid"], "n": e["n"], "status": e["status"], "label": label,
                           "what": data.get("command") if label != "manual" else t["text"],
                           "by": e["recorder"] or e["carried_by"], "at": e["ended_at"] or e["started_at"],
                           "basis": evidence.short(e["basis_end"] or e["basis_start"]), "state": st["state"]}
                    checks.append(row)
                    if st["state"] == "out_of_date":
                        gone_stale.append({"test": st["test"], "n": e["n"], "basis": row["basis"]})
                    evidence_lines.append({"label": label, "text": f"{st['test']} #{e['n']} {e['status']}: {row['what']}",
                                           "by": row["by"], "at": row["at"]})
                    if e["note"]:
                        evidence_lines.append({"label": "manual", "text": f"{st['test']} #{e['n']} note: {e['note']}",
                                               "by": e["recorder"] or "", "at": row["at"]})
        changed = None
        if spec_pks:
            run = self._q1(f"SELECT r.*, s.rid AS srid FROM runs r JOIN rungs s ON s.pk = r.spec_pk WHERE r.spec_pk IN "
                           f"({','.join('?' * len(spec_pks))}) ORDER BY r.pk DESC LIMIT 1", tuple(spec_pks))
            if run is not None:
                files = []
                for a in self._q("SELECT * FROM attempts WHERE run_pk=? ORDER BY n", (run["pk"],)):
                    for f in json.loads(a["files_changed"] or "[]"):
                        f = f.get("path", "") if isinstance(f, dict) else str(f)
                        if f and f not in files:
                            files.append(f)
                    out = (a["worker_output"] or "").strip().splitlines()
                    if out:
                        evidence_lines.append({"label": "model", "text": f"run {run['pk']} attempt {a['n']}: {out[-1][:300]}",
                                               "by": run["profile"], "at": a["ended_at"] or a["started_at"]})
                changed = {"run": run["pk"], "spec": run["srid"], "profile": run["profile"], "status": run["status"],
                           "files": files}
        comp = self.need_completeness(project, n["rid"], fresh=True)
        evidence_lines.sort(key=lambda x: x["at"] or 0)
        return {"need": n["rid"], "outcome": n["text"], "complete": comp["complete"], "verified": verified,
                "what_changed": changed, "checks": checks, "manual": manual, "optional": optional,
                "no_longer_applies": gone_stale, "obligations": comp["open"], "basis": evidence.short(cur),
                "try": self.try_it(project), "evidence": evidence_lines}

    def readout_markdown(self, project: str, rid: str) -> str:
        r = self.readout(project, rid)
        need = r["need"]

        def seen(v):
            return "" if v is None else (" · Seen failing" if v else " · Not seen failing")

        out = [f"# {need['id']} results and evidence", "", f"Project: {r['project']}", "", "## Intent", "",
               f"{need['text']}", "", f"Version {need['version']}"]
        if need["retired"]:
            out += ["", f"Retired: {need['retired_reason']}"]
        out += ["", "## Plan", ""]
        for req in r["plan"]:
            out.append(f"- {req['id']} {req['text']} ({req['status']})")
            for s in req["specifications"]:
                out.append(f"  - {s['id']} {s['text']} ({s['status']})")
                for t in s["tests"]:
                    what = t["command"] if t["type"] != "manual" else t["text"]
                    out.append(f"    - {t['id']} {t['type']}: {what} ({t['result'].replace('_', ' ')}){seen(t['seen_failing'])}")
        out += ["", "## Delivered", "", f"{r['proven']} of {r['total']} requirements proven", ""]
        for d in r["delivered"]:
            if d["proven"]:
                p = d["proof"]
                out.append(f"- {d['id']} {d['text']}: proven by {p['test']} #{p['n']} pass, assigned profile "
                           f"{p['carried_by']}, at {_stamp(p['at'])}" + (f", on code {p['basis']}" if p.get("basis") else "")
                           + seen(p['seen_failing']))
            else:
                out.append(f"- {d['id']} {d['text']}: not proven, {d['reason']}")
        res = self.result(project, rid)
        out += ["", "## Result", "", f"Outcome: {res['outcome']}", f"Complete: {'yes' if res['complete'] else 'no'}",
                f"Code basis: {res['basis']}", "", "Verified behaviours:"]
        out += [f"- {v['spec']} {v['text']}" for v in res["verified"]] or ["- none"]
        wc = res["what_changed"]
        out += ["", "What changed:"]
        out += ([f"- run {wc['run']} of {wc['spec']} by {wc['profile']} ({wc['status']}): " + (", ".join(wc["files"]) or "no files")]
                if wc else ["- no develop run"])
        out += ["", "Open obligations:"]
        out += [f"- {o['rung']}{' ' + o['spec'] if o.get('spec') else ''}: {o['text']}" for o in res["obligations"]] or ["- none"]
        out += ["", "Optional checks:"]
        out += [f"- {o['test']} {o['text']} ({o['state'].replace('_', ' ')})" for o in res["optional"]] or ["- none"]
        out += ["", "Evidence that no longer applies:"]
        out += [f"- {g['test']} #{g['n']} passed on code {g['basis']}, not the code as it is now" for g in res["no_longer_applies"]] or ["- none"]
        if res["try"]["instruction"] or res["try"]["command"]:
            out += ["", "Try it:", res["try"]["instruction"]] + ([f"Command (a person runs it): {res['try']['command']}"] if res["try"]["command"] else [])
        out += ["", "Evidence:"]
        out += [f"- [{x['label']}] {x['text']} ({x['by']}, {_stamp(x['at'])})" for x in res["evidence"]] or ["- none"]
        return "\n".join(out).replace("\u2014", "-") + "\n"

    def export_readout(self, project: str, rid: str) -> dict:
        """Write the read-out to Rung's data folder (never the project folder) and return its path."""
        text = self.readout_markdown(project, rid)
        folder = Path(self.path).expanduser().resolve().parent / "exports"
        folder.mkdir(parents=True, exist_ok=True)
        safe = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in project)
        path = folder / f"{safe}-{rid}.md"
        path.write_text(text, encoding="utf-8")
        return {"path": str(path), "markdown": text}


def _stamp(ts) -> str:
    import time
    if not ts:
        return ""
    return time.strftime("%Y-%m-%d %H:%M", time.localtime(ts))
