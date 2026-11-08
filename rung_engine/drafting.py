"""Drafting providers. They only produce text; the engine decides what the text is allowed to do.

`stub` is deterministic: it reads a JSON table (a fixture project ships one in
`.rung-stub/drafts.json`) and falls back to fixed templates. `profile` asks a Hermes profile.
Which one runs is Rung's own `drafting` setting, the same seam a user changes.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import time
from pathlib import Path


class Drafter:
    delay = 0.0

    def suggest_requirements(self, need_text: str, project: dict) -> list[str]:
        raise NotImplementedError

    def derive_spec(self, need_text: str, req_text: str, project: dict, others: tuple = ()) -> dict:
        """`others`: the need's other requirements, which get specifications of their own."""
        raise NotImplementedError

    def support_spec(self, need_text: str, req_text: str, draft: str, project: dict) -> str:
        raise NotImplementedError

    def propose_tests(self, spec_text: str, req_text: str, project: dict, others: tuple = ()) -> list[dict]:
        """`others`: the need's other specifications, which get tests of their own."""
        raise NotImplementedError

    def suggest_edits(self, req_text: str, project: dict) -> list[str]:
        raise NotImplementedError

    # Bot help (Round 13): each only proposes; the engine checks and a person saves.

    def place(self, text: str, ladder: list[dict], project: dict) -> dict:
        """Which rung a pasted text is and where it goes: {kind, parent, why}. `ladder` lists the rungs
        it may go under ({id, kind, text})."""
        raise NotImplementedError

    def draft(self, kind: str, chain: list[dict], fields: dict, project: dict) -> dict:
        """Fields for a new rung of `kind` under the parent chain (need first)."""
        raise NotImplementedError

    def suggest_missing(self, need_text: str, req_texts: list[str], project: dict) -> list[str]:
        """Requirements the need may still be missing (three are kept)."""
        raise NotImplementedError


class DraftFailed(RuntimeError):
    pass


class StubDrafter(Drafter):
    def __init__(self, table: dict | None = None, delay: float = 0.0, fail: str = ""):
        self.table = table or {}
        self.delay = float(delay or 0)
        self.fail = fail or ""

    @classmethod
    def for_project(cls, project: dict, stub_file: str = "", delay: float = 0.0, fail: str = "") -> "StubDrafter":
        path = Path(stub_file).expanduser() if stub_file else Path(project["folder"]).expanduser() / ".rung-stub" / "drafts.json"
        table = {}
        if path.is_file():
            try:
                table = json.loads(path.read_text())
            except (OSError, ValueError):
                table = {}
        return cls(table, delay, fail)

    def _get(self, section, key, default):
        return self.table.get(section, {}).get(key, default)

    def suggest_requirements(self, need_text, project):
        return list(self._get("requirements", need_text.strip(), []))

    def derive_spec(self, need_text, req_text, project, others=()):
        if self.fail:  # the stub's failure mode, selected through the drafting setting
            raise DraftFailed(self.fail)
        got = self._get("specifications", req_text.strip(), None)
        if isinstance(got, str):
            got = {"text": got}
        if not got:
            got = {"text": f"Implement: {req_text.strip()}"}
        return {"text": got.get("text", ""), "detail": got.get("detail", ""), "tags": got.get("tags", []),
                "required_tags": got.get("required_tags", [])}

    def support_spec(self, need_text, req_text, draft, project):
        return self._get("support", req_text.strip(), "State the exact command-line flag and the exit code on error.")

    def propose_tests(self, spec_text, req_text, project, others=()):
        got = self._get("tests", spec_text.strip(), None)
        if got is None:
            got = [{"type": "command", "command": project.get("test_command") or "pytest"}]
        return [dict(t) for t in got]

    def suggest_edits(self, req_text, project):
        return list(self._get("edits", req_text.strip(), []))

    def _bot_fail(self):
        if self.fail:
            raise DraftFailed(self.fail)

    def place(self, text, ladder, project):
        self._bot_fail()
        got = self._get("place", text.strip(), None)
        if got:
            return {"kind": got.get("kind", ""), "parent": got.get("parent"), "why": got.get("why", "")}
        low = text.strip().lower()
        first = lambda kind: next((r["id"] for r in ladder if r["kind"] == kind), None)  # noqa: E731
        if low.startswith(("run ", "check ", "test ")) or "exit code" in low or "exits 0" in low:
            return {"kind": "test", "parent": first("specification"), "why": "It says how to check a result."}
        if low.startswith(("implement", "add a ", "use ", "write a ")):
            return {"kind": "specification", "parent": first("requirement"), "why": "It says how to build something."}
        if " must " in f" {low} " or " should " in f" {low} " or low.startswith(("accept", "reject", "report", "keep")):
            return {"kind": "requirement", "parent": first("need"), "why": "It states one thing the result must do."}
        return {"kind": "need", "parent": None, "why": "It states a problem a person has."}

    def draft(self, kind, chain, fields, project):
        self._bot_fail()
        parent = chain[-1]["text"] if chain else ""
        got = self._get("draft", kind, None)
        if isinstance(got, dict):
            got = got.get(parent.strip(), got.get("*"))
        if got:
            return dict(got)
        if kind == "need":
            return {"text": f"Work with {project.get('name', 'this project')} without manual steps"}
        if kind == "requirement":
            return {"text": f"Do this reliably: {parent}", "detail": "One observable result per requirement."}
        if kind == "specification":
            need = chain[0]["text"] if chain else ""
            got = dict(self.derive_spec(need, parent, project))
            if not got.get("detail"):
                got["detail"] = f"Read the input, apply the rule, write the output: {parent}"
            return got
        if kind == "test":
            t = (self.propose_tests(parent, chain[-2]["text"] if len(chain) > 1 else "", project) or [{}])[0]
            if not t.get("command") and not t.get("steps"):
                t = {"type": "command", "command": "python3 -m pytest -q"}
            return {"type": t.get("type", "command"), "command": t.get("command", ""), "steps": t.get("steps", "")}
        return {}

    def suggest_missing(self, need_text, req_texts, project):
        self._bot_fail()
        got = self._get("suggest", need_text.strip(), None)
        if got is not None:
            return [str(x) for x in got]
        pool = [f"Handle empty input: {need_text.strip()}", "Report each error with the line it came from",
                "Leave the input file unchanged", "Finish a 10 MB input within 5 seconds",
                "Exit with a non-zero code when any row fails", "Print a summary of rows changed"]
        have = {t.strip().lower() for t in req_texts}
        return [t for t in pool if t.lower() not in have][:3]


# Drafts are read on screen and approved by a person: short, grounded in the project, one rung each.
HERE = "The project's files are in the current folder."


def _test_fields(t: dict) -> dict:
    """A drafted test as the engine takes it: a pass rule of the wrong shape is left out (exit code 0)."""
    t = dict(t)
    rule = t.get("pass_rule")
    ok = isinstance(rule, dict) and (
        rule.get("kind") == "exit_code" and isinstance(rule.get("value", 0), int)
        or rule.get("kind") == "output_contains" and isinstance(rule.get("value"), str) and rule["value"].strip())
    if not ok:
        t.pop("pass_rule", None)
    return t


def _others(kind: str, texts) -> str:
    """The siblings a draft must agree with (same names, formats and markers) without covering them."""
    texts = [t for t in texts if t]
    if not texts:
        return ""
    return (f" The need's other {kind}, drafted separately, which this one must agree with (same names, formats and "
            f"markers) but not cover: {json.dumps(texts)}.")


class ProfileDrafter(Drafter):
    """Asks a Hermes profile for JSON. One short non-interactive chat per request."""

    def __init__(self, profile: str, hermes_bin: str = "hermes", timeout: int = 180):
        self.profile = profile
        self.hermes_bin = hermes_bin
        self.timeout = timeout

    should_cancel = None  # set by a cancellable bot job: a callable that turns true when the person cancels

    def _ask(self, instruction: str, project: dict):
        prompt = (instruction + "\nReply with JSON only, no prose, no code fence.")
        proc = subprocess.Popen(
            [self.hermes_bin, "-p", self.profile, "chat", "-Q", "-q", prompt, "--max-turns", "3"],
            cwd=str(Path(project["folder"]).expanduser()), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            stdin=subprocess.DEVNULL, text=True, env=scrubbed_env(project["folder"]), start_new_session=True,
        )
        end = time.monotonic() + self.timeout
        while True:
            try:
                stdout, _ = proc.communicate(timeout=0.25)
                break
            except subprocess.TimeoutExpired:
                if (self.should_cancel and self.should_cancel()) or time.monotonic() > end:
                    # The whole process group: Hermes's own children hold the output pipe open otherwise.
                    try:
                        os.killpg(proc.pid, 9)
                    except OSError:
                        proc.kill()
                    proc.communicate()
                    if time.monotonic() > end:
                        raise DraftFailed(f"{self.profile} did not answer within {self.timeout} s")
                    raise DraftFailed("cancelled")
        text = (stdout or "").strip()
        m = re.search(r"(\{.*\}|\[.*\])", text, re.S)
        if not m:
            raise ValueError("drafting profile returned no JSON")
        return json.loads(m.group(1))

    def suggest_requirements(self, need_text, project):
        got = self._ask(f"Need: {need_text!r}. {HERE} List three requirements for this need: one short sentence "
                        "each (under 15 words), each one thing a person can check. JSON array of strings.", project)
        return [str(x) for x in got][:5]

    def derive_spec(self, need_text, req_text, project, others=()):
        got = self._ask(f"Need: {need_text!r}. Requirement: {req_text!r}. {HERE}{_others('requirements', others)} "
                        "Write one implementable specification for this requirement only. "
                        'JSON object {"text": one sentence under 25 words, "detail": the approach in at most two '
                        'sentences, "tags": up to three capability tags}.', project)
        return {"text": str(got.get("text", "")), "detail": str(got.get("detail", "")),
                "tags": list(got.get("tags", [])), "required_tags": []}

    def support_spec(self, need_text, req_text, draft, project):
        got = self._ask(f"Requirement: {req_text!r}. Draft specification: {draft!r}. Suggest one improvement. "
                        'JSON object {"suggestion": text}.', project)
        return str(got.get("suggestion", ""))

    def propose_tests(self, spec_text, req_text, project, others=()):
        # A person approves every test: a command reads like what they would type to try it themselves.
        got = self._ask(f"Specification: {spec_text!r}. Requirement: {req_text!r}. {HERE}"
                        f"{_others('specifications', others)} Its test command: "
                        f"{project.get('test_command')!r}. Propose one or two tests that prove this specification. "
                        "A command test is what a person would type to try it, run from the project folder: the "
                        "project's own commands joined with &&, under 160 characters, no shell scripting. Start from "
                        "a clean state each run and keep any data it writes out of the project folder (the project's "
                        "files say how). Its pass_rule is {\"kind\": \"output_contains\", \"value\": text the output "
                        "shows only when it works}, or {\"kind\": \"exit_code\", \"value\": 0} for a test runner. Add a "
                        "manual test only for what a command cannot check, with at most four short steps. JSON array "
                        "of objects with type command|manual, command and pass_rule for command tests, steps for "
                        "manual tests.", project)
        return [_test_fields(t) for t in got if isinstance(t, dict)]

    def suggest_edits(self, req_text, project):
        got = self._ask(f"Suggest up to two sharper acceptance criteria for: {req_text!r}. JSON array of strings.", project)
        return [str(x) for x in got][:3]

    def place(self, text, ladder, project):
        rows = "\n".join(f"{r['id']} ({r['kind']}): {r['text']}" for r in ladder[:200])
        got = self._ask("A design ladder goes Need, Requirement, Specification, Test. Its rungs:\n" + rows +
                        f"\nWhich kind of rung is this text, and under which rung id does it go? Text: {text!r}. "
                        'JSON object {"kind": "need"|"requirement"|"specification"|"test", '
                        '"parent": rung id or null for a need, "why": one short line}.', project)
        return {"kind": str(got.get("kind", "")).lower(), "parent": got.get("parent"), "why": str(got.get("why", ""))}

    def draft(self, kind, chain, fields, project):
        above = "; ".join(f"{c['kind']} {c['id']}: {c['text']!r}" for c in chain) or "none"
        shape = {"need": '{"text": one sentence}',
                 "requirement": '{"text": one sentence, "detail": acceptance in one line}',
                 "specification": '{"text": one line, "detail": approach, "tags": capability tags}',
                 "test": '{"type": "command"|"manual", "command": shell command, "steps": manual steps}'}[kind]
        got = self._ask(f"Draft a new {kind}. Above it: {above}. Already typed: {json.dumps(fields)}. "
                        f"JSON object {shape}.", project)
        return {k: v for k, v in dict(got).items() if isinstance(v, (str, list))}

    def suggest_missing(self, need_text, req_texts, project):
        got = self._ask(f"Need: {need_text!r}. Its requirements: {json.dumps(req_texts)}. List exactly three "
                        "requirements this need may still be missing, one sentence each, none repeating the "
                        "existing ones. JSON array of three strings.", project)
        return [str(x.get("text", "")) if isinstance(x, dict) else str(x) for x in got]


def scrubbed_env(folder=None) -> dict:
    """Environment for child Hermes processes: no Rung or calling-session variables leak in, and no
    approval bypass: a child never inherits YOLO mode from the process that started it, so its flagged
    actions resolve under Hermes's single-query approval rules.

    `folder`: the project folder the child works in. Hermes's file and terminal tools anchor to
    TERMINAL_CWD before the process cwd, so a value inherited from the parent (the gateway's, often the
    home folder) would send the child's searches and edits there; the child gets the project folder."""
    env = dict(os.environ)
    for k in list(env):
        if k.startswith("RUNG_") or k.startswith("HERMES_SESSION") or k in (
                "HERMES_GOAL", "PYTEST_CURRENT_TEST", "HERMES_YOLO_MODE", "TERMINAL_CWD"):
            env.pop(k, None)
    if folder:
        env["TERMINAL_CWD"] = str(Path(folder).expanduser().resolve())
    return env


def make_drafter(settings: dict, project: dict, hermes_bin: str = "hermes", profile: str | None = None) -> Drafter:
    """The drafting provider. `profile` asks a named profile instead of the drafting profile (Suggest
    asks the profile allocation chose); the stub then stands in for that profile."""
    d = dict(settings.get("drafting") or {})
    if profile:
        d["profile"] = profile
    if d.get("kind") == "profile" and d.get("profile"):
        return ProfileDrafter(d["profile"], hermes_bin=hermes_bin)
    stub = StubDrafter.for_project(project, d.get("stub_file", ""), d.get("delay", 0), d.get("fail", ""))
    if d.get("profile"):
        stub.profile = str(d["profile"])  # the stub stands in for that profile: drafts are attributed to it
    return stub


def pause(drafter: Drafter, should_cancel=None):
    """The stub's simulated drafting time; it stops early when the job is cancelled."""
    if not drafter.delay:
        return
    end = time.monotonic() + drafter.delay
    while time.monotonic() < end:
        if should_cancel and should_cancel():
            raise DraftFailed("cancelled")
        time.sleep(0.05)
