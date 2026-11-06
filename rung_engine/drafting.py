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

    def derive_spec(self, need_text: str, req_text: str, project: dict) -> dict:
        raise NotImplementedError

    def support_spec(self, need_text: str, req_text: str, draft: str, project: dict) -> str:
        raise NotImplementedError

    def propose_tests(self, spec_text: str, req_text: str, project: dict) -> list[dict]:
        raise NotImplementedError

    def suggest_edits(self, req_text: str, project: dict) -> list[str]:
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

    def derive_spec(self, need_text, req_text, project):
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

    def propose_tests(self, spec_text, req_text, project):
        got = self._get("tests", spec_text.strip(), None)
        if got is None:
            got = [{"type": "command", "command": project.get("test_command") or "pytest"}]
        return [dict(t) for t in got]

    def suggest_edits(self, req_text, project):
        return list(self._get("edits", req_text.strip(), []))


class ProfileDrafter(Drafter):
    """Asks a Hermes profile for JSON. One short non-interactive chat per request."""

    def __init__(self, profile: str, hermes_bin: str = "hermes", timeout: int = 180):
        self.profile = profile
        self.hermes_bin = hermes_bin
        self.timeout = timeout

    def _ask(self, instruction: str, project: dict):
        prompt = (instruction + "\nReply with JSON only, no prose, no code fence.")
        out = subprocess.run(
            [self.hermes_bin, "-p", self.profile, "chat", "-Q", "-q", prompt, "--max-turns", "3"],
            cwd=str(Path(project["folder"]).expanduser()), capture_output=True, text=True, timeout=self.timeout,
            env=scrubbed_env(),
        )
        text = out.stdout.strip()
        m = re.search(r"(\{.*\}|\[.*\])", text, re.S)
        if not m:
            raise ValueError("drafting profile returned no JSON")
        return json.loads(m.group(1))

    def suggest_requirements(self, need_text, project):
        got = self._ask(f"List three short requirements (one sentence each) for this need: {need_text!r}. "
                        "JSON array of strings.", project)
        return [str(x) for x in got][:5]

    def derive_spec(self, need_text, req_text, project):
        got = self._ask(f"Need: {need_text!r}. Requirement: {req_text!r}. Write one implementable specification. "
                        'JSON object {"text": one line, "detail": approach, "tags": capability tags}.', project)
        return {"text": str(got.get("text", "")), "detail": str(got.get("detail", "")),
                "tags": list(got.get("tags", [])), "required_tags": []}

    def support_spec(self, need_text, req_text, draft, project):
        got = self._ask(f"Requirement: {req_text!r}. Draft specification: {draft!r}. Suggest one improvement. "
                        'JSON object {"suggestion": text}.', project)
        return str(got.get("suggestion", ""))

    def propose_tests(self, spec_text, req_text, project):
        got = self._ask(f"Specification: {spec_text!r}. Propose tests. Test command of the project: "
                        f"{project.get('test_command')!r}. JSON array of objects with type command|manual, "
                        "command for command tests, steps for manual tests.", project)
        return [dict(t) for t in got if isinstance(t, dict)]

    def suggest_edits(self, req_text, project):
        got = self._ask(f"Suggest up to two sharper acceptance criteria for: {req_text!r}. JSON array of strings.", project)
        return [str(x) for x in got][:3]


def scrubbed_env() -> dict:
    """Environment for child Hermes processes: no Rung or calling-session variables leak in, and no
    approval bypass: a child never inherits YOLO mode from the process that started it, so its flagged
    actions resolve under Hermes's single-query approval rules."""
    env = dict(os.environ)
    for k in list(env):
        if k.startswith("RUNG_") or k.startswith("HERMES_SESSION") or k in (
                "HERMES_GOAL", "PYTEST_CURRENT_TEST", "HERMES_YOLO_MODE"):
            env.pop(k, None)
    return env


def make_drafter(settings: dict, project: dict, hermes_bin: str = "hermes") -> Drafter:
    d = settings.get("drafting") or {}
    if d.get("kind") == "profile" and d.get("profile"):
        return ProfileDrafter(d["profile"], hermes_bin=hermes_bin)
    stub = StubDrafter.for_project(project, d.get("stub_file", ""), d.get("delay", 0), d.get("fail", ""))
    if d.get("profile"):
        stub.profile = str(d["profile"])  # the stub stands in for that profile: drafts are attributed to it
    return stub


def pause(drafter: Drafter):
    if drafter.delay:
        time.sleep(drafter.delay)
