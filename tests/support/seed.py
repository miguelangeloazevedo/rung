"""Synthetic demo state, built through the engine the same way a user would build it.

Failing history is real: the copy of the fixture is broken for a moment, the test is run by the
engine and fails, and the copy is restored. Nothing is written into the store behind the engine.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from rung_engine import HUMAN, Actor, Engine

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"

PROFILES = [
    {"name": "coder", "labels": ["python", "cli", "tests"], "cost": 5, "max_runs": 5, "enabled": True},
    {"name": "reviewer", "labels": ["review", "python"], "cost": 4, "max_runs": 3, "enabled": True},
    {"name": "writer", "labels": ["docs", "specs"], "cost": 3, "max_runs": 3, "enabled": True},
    {"name": "researcher", "labels": ["research"], "cost": 6, "max_runs": 3, "enabled": True},
]

N1 = "Clean a messy CSV export without opening a spreadsheet"
R1 = "Detect the delimiter automatically"
R2 = "Normalise every date to ISO 8601"
R2_OLD = "Normalise every date to YYYY-MM-DD"
R3 = "Never drop a row without reporting it"
S11 = "Sniff the delimiter from the first 20 lines"
S21 = "Parse day-first and month-first dates with a --locale flag"
S31 = "Count dropped rows and print the count to stderr"


def copy_fixture(name: str, dest: Path) -> Path:
    target = Path(dest) / name
    shutil.copytree(FIXTURES / name, target, ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache"))
    subprocess.run(["git", "init", "-q"], cwd=target, check=True)
    subprocess.run(["git", "add", "-A"], cwd=target, check=True)
    subprocess.run(["git", "-c", "user.name=Rung Demo", "-c", "user.email=demo@example.invalid", "commit", "-qm",
                    "fixture"], cwd=target, check=True)
    return target


def seed_profiles(engine: Engine):
    engine.save_profiles(PROFILES)


def seed_csvtidy(engine: Engine, folder: Path, with_history: bool = True, r2: str = R2, r2_detail: str = "") -> None:
    seed_profiles(engine)
    engine.create_project("csvtidy", str(folder), "pytest", [p["name"] for p in PROFILES])
    engine.set_setting("drafting", {"kind": "stub", "delay": 0.0})
    engine.set_setting("worker", {"kind": "stub", "delay": 0.2})
    engine.create_need("csvtidy", N1, HUMAN)
    engine.add_requirement("csvtidy", "N-1", R1, HUMAN)
    engine.add_requirement("csvtidy", "N-1", r2, HUMAN, r2_detail)
    engine.approve_requirements("csvtidy", "N-1", HUMAN)
    engine.write_spec("csvtidy", "R-1", S11, tags=["python", "cli", "tests"])
    engine.write_spec("csvtidy", "R-2", S21, tags=["python", "cli", "tests"],
                      detail="Read --locale, default en_US. Day-first for en_GB, de_DE, fr_FR.")
    engine.approve_drafted("csvtidy", "N-1", HUMAN)
    engine.add_test("csvtidy", "S-1.1", {"type": "command", "command": "pytest tests/test_sniff.py"}, HUMAN, status="approved")
    engine.add_test("csvtidy", "S-2.1", {"type": "command", "command": "pytest tests/test_dates.py::test_ambiguous_locale"},
                    HUMAN, status="approved")
    # Optional (Round 22): verification does not wait for it, but a recorded failure blocks S-2.1.
    engine.add_test("csvtidy", "S-2.1", {"type": "manual", "required": False,
                                          "text": "Manual: open output in a spreadsheet, dates sort correctly",
                                          "steps": ["Run csvtidy on samples/dates.csv", "Open the output in a spreadsheet",
                                                    "Sort by the date column"]}, HUMAN, status="approved")
    engine.approve_tests("csvtidy", "N-1", HUMAN)
    engine.add_requirement("csvtidy", "N-1", R3, HUMAN)
    if with_history:
        dates = folder / "csvtidy" / "dates.py"
        good = dates.read_text()
        dates.write_text(good.replace("day, month = a, b", "month, day = a, b  # swapped"))
        try:
            engine.run_test("csvtidy", "T-2.1a", carried_by="coder")
            engine.run_test("csvtidy", "T-2.1a", carried_by="coder")
        finally:
            dates.write_text(good)
        engine.run_test("csvtidy", "T-2.1a", carried_by="coder")
        engine.run_test("csvtidy", "T-1.1a", carried_by="coder")


def seed_completeness(engine: Engine, folder: Path) -> None:
    """csvtidy N-1 with R-1 verified (S-1.1, T-1.1a passing) and R-2 approved with no specification (Round 24)."""
    seed_profiles(engine)
    engine.create_project("csvtidy", str(folder), "pytest", [p["name"] for p in PROFILES])
    engine.set_setting("drafting", {"kind": "stub", "delay": 0.0})
    engine.set_setting("worker", {"kind": "stub", "delay": 0.2})
    engine.create_need("csvtidy", N1, HUMAN)
    engine.add_requirement("csvtidy", "N-1", R1, HUMAN)
    engine.add_requirement("csvtidy", "N-1", R2, HUMAN)
    engine.approve_requirements("csvtidy", "N-1", HUMAN)
    engine.write_spec("csvtidy", "R-1", S11, tags=["python", "cli", "tests"])
    engine.approve("csvtidy", "S-1.1", HUMAN)
    engine.add_test("csvtidy", "S-1.1", {"type": "command", "command": "pytest tests/test_sniff.py"}, HUMAN, status="approved")
    engine.run_test("csvtidy", "T-1.1a", carried_by="coder")


def seed_needs_you(engine: Engine, folder: Path) -> None:
    """csvtidy with one of each Needs you item (Round 24, U04): R-1 changed (S-1.1 stale), a proposed requirement,
    a recorded manual pass waiting for approval, a test that could not run, and a run that asked a question."""
    import json

    from rung_engine.runner import run_loop
    from rung_engine.workers import StubWorker
    seed_csvtidy(engine, folder)
    engine.add_test("csvtidy", "S-2.1", {"type": "command", "command": "sleep 5", "timeout": 1}, HUMAN, status="approved")
    engine.run_test("csvtidy", "T-2.1c", carried_by="coder")  # timed out: could not run
    engine.record_manual("csvtidy", "T-2.1b", "pass", "Sorted by date, all rows in order")
    engine.propose("csvtidy", "N-1", "requirement", "Keep the header row untouched", "coder")
    stub = folder / ".outcome-stub" / "S-2.1"
    stub.mkdir(parents=True, exist_ok=True)
    (stub / "attempt-1.json").write_text(json.dumps({"outcome": "needs_input", "reason": "Which locale is the default?"}))
    run = engine.start_run("csvtidy", "S-2.1", profile="coder")
    run_loop(engine, run["id"], worker=StubWorker(str(folder / ".outcome-stub"), delay=0))
    engine.edit("csvtidy", "R-1", text="Sniff the delimiter, then confirm it on the whole file")


def break_dates(folder: Path):
    """Swap day and month in the fixture's date parser; returns the function that puts it back."""
    dates = Path(folder) / "csvtidy" / "dates.py"
    good = dates.read_text()
    dates.write_text(good.replace("day, month = a, b", "month, day = a, b  # swapped"))
    return lambda: dates.write_text(good)


def seed_failing(engine: Engine, folder: Path):
    """csvtidy with S-2.1 approved and its command test failing now. Returns the restore function; once
    called, the next run of T-2.1a passes."""
    seed_csvtidy(engine, folder)
    engine.open_project("csvtidy")
    restore = break_dates(folder)
    engine.run_test("csvtidy", "T-2.1a", carried_by="coder")
    return restore


def seed_notes_sync(engine: Engine, folder: Path) -> None:
    seed_profiles(engine)
    engine.create_project("notes-sync", str(folder), "pytest", ["coder", "reviewer"])
    engine.create_need("notes-sync", "Keep two note folders in sync", HUMAN)
    engine.add_requirement("notes-sync", "N-1", "Copy notes that exist on one side only", HUMAN)
    engine.add_requirement("notes-sync", "N-1", "Ignore identical files", HUMAN)
    engine.approve_requirements("notes-sync", "N-1", HUMAN)
    engine.write_spec("notes-sync", "R-1", "Plan copies in both directions", tags=["python"])
    engine.write_spec("notes-sync", "R-2", "Skip notes whose text is unchanged", tags=["python"])
    engine.approve_drafted("notes-sync", "N-1", HUMAN)
    engine.add_test("notes-sync", "S-1.1", {"type": "command", "command": "pytest tests/test_sync.py::test_copies_new_notes"},
                    HUMAN, status="approved")
    engine.add_test("notes-sync", "S-2.1", {"type": "command", "command": "pytest tests/test_sync.py::test_skips_identical"},
                    HUMAN, status="approved")
    engine.approve_tests("notes-sync", "N-1", HUMAN)
    engine.run_test("notes-sync", "T-1.1a", carried_by="coder")
    engine.run_test("notes-sync", "T-2.1a", carried_by="coder")


AGENT = Actor("agent", "coder")


def seed_demo(engine: Engine, folder: Path) -> None:
    """The state the approved prototype shows on Home: R-2 edited, S-2.1 stale, one proposal waiting."""
    seed_csvtidy(engine, folder, r2=R2_OLD, r2_detail="Month-first input")
    engine.open_project("csvtidy")
    engine.edit("csvtidy", "R-2", text=R2, detail="Day-first and month-first input", approve=True)
    engine.propose("csvtidy", "N-1", "requirement", "Accept a two-digit year only with --century", "coder",
                   source_chat="Fix date parsing in csvtidy")


def seed_built(engine: Engine, folder: Path) -> None:
    """Every step of N-1 approved, R-3 included: the state the Develop step shows."""
    seed_csvtidy(engine, folder)
    engine.open_project("csvtidy")
    engine.approve("csvtidy", "R-3", HUMAN)
    engine.write_spec("csvtidy", "R-3", S31, tags=["python", "cli", "tests"],
                      detail="Track each skipped row while parsing\nPrint dropped=N to stderr at exit\nExit code 2 when N is above 0")
    engine.approve_drafted("csvtidy", "N-1", HUMAN)
    engine.add_test("csvtidy", "S-3.1", {"type": "command", "command": "pytest tests/test_dropped.py"}, HUMAN,
                    status="approved")
    engine.approve_tests("csvtidy", "N-1", HUMAN)


MERGE_NEED = "Merge two CSV exports by a shared key"


def seed_merge(engine: Engine, folder: Path, upto: str = "develop") -> None:
    """csvtidy plus N-2 carried through the build flow with the drafting stub, up to `upto`:
    "requirements" (approved), "specifications" (approved), "tests" (proposed, not accepted)
    or "develop" (every test accepted, Tests step approved)."""
    from rung_engine.service import Service
    seed_csvtidy(engine, folder)
    engine.open_project("csvtidy")
    svc = Service(engine, inline_runs=True)
    texts = svc.suggest_requirements("csvtidy", MERGE_NEED)
    engine.create_need("csvtidy", MERGE_NEED, HUMAN, requirements=texts)
    engine.approve_requirements("csvtidy", "N-2", HUMAN)
    if upto == "requirements":
        return
    svc.set_authoring("csvtidy", "R-4", "ai", wait=True)
    svc.set_authoring("csvtidy", "R-5", "ai", wait=True)
    engine.write_spec("csvtidy", "R-6", "Preserve column order from the first file")
    engine.approve_drafted("csvtidy", "N-2", HUMAN)
    if upto == "specifications":
        return
    made = svc.propose_tests("csvtidy", "N-2")
    if upto == "tests":
        return
    for t in made:
        engine.approve("csvtidy", t["id"], HUMAN)
    engine.approve_tests("csvtidy", "N-2", HUMAN)


def seed_large(engine: Engine, folder: Path, name: str = "bigladder", needs: int = 20, reqs: int = 8,
               executions: int = 2000, text=None) -> dict:
    """A project of needs x (1 + 3 x reqs) rungs (500 by default) and `executions` recorded results, built through
    the same engine calls as the demo. `text(kind, i)` overrides the wording (the worst-case fixture uses it)."""
    say = text or (lambda kind, i: f"{kind} {i}")
    seed_profiles(engine)
    engine.create_project(name, str(folder), "true", [p["name"] for p in PROFILES])
    engine.set_setting("drafting", {"kind": "stub", "delay": 0.0})
    tests = []
    for n in range(1, needs + 1):
        need = engine.create_need(name, say("Need", n), HUMAN)["id"]
        rids = [engine.add_requirement(name, need, say("Requirement", f"{n}.{r}"), HUMAN)["id"]
                for r in range(1, reqs + 1)]
        engine.approve_requirements(name, need, HUMAN)
        specs = [engine.write_spec(name, rid, say("Specification", rid), tags=["python"])["id"] for rid in rids]
        engine.approve_drafted(name, need, HUMAN)
        for spec in specs:
            tests.append(engine.add_test(name, spec, {"type": "manual", "text": say("Test", spec),
                                                      "steps": ["Open the output", "Compare with the sample"]},
                                         HUMAN, status="approved")["id"])
        engine.approve_tests(name, need, HUMAN)
    for i in range(executions):
        t = tests[i % len(tests)]
        engine.record_manual(name, t, "fail" if i % 7 == 3 else "pass", f"round {i // len(tests) + 1}")
    return {"rungs": needs * (1 + 3 * reqs), "executions": executions, "tests": tests}


# Two pieces that each pass their own tests but disagree on the interface between them (decisions Round 23):
# the API answers {"short_url": ...}, the page reads "url". Only a check across the HTTP boundary sees it.
LINKPAIR = {
    "shortly/__init__.py": "",
    "shortly/api.py": """import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

LINKS = {}


def create(url):
    code = format(len(LINKS) + 1, "x").rjust(4, "0")
    LINKS[code] = url
    return {"code": code, "short_url": "/r/" + code}


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        out = json.dumps(create(body["url"])).encode()
        self.send_response(201)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(out)

    def log_message(self, *a):
        pass


def serve():
    srv = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv
""",
    "shortly/page.py": """import json
import urllib.request


def render(link):
    return '<p>Your link: <a href="{0}">{0}</a></p>'.format(link["url"])


def shorten(base, url):
    req = urllib.request.Request(base + "/links", data=json.dumps({"url": url}).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=5) as r:
        return render(json.loads(r.read()))
""",
    "tests/__init__.py": "",
    "tests/test_api.py": """from shortly import api


def test_create_returns_a_short_url():
    out = api.create("https://bakery.example/rye")
    assert out["short_url"].startswith("/r/")
""",
    "tests/test_page.py": """from shortly import page


def test_render_shows_the_link():
    assert '<a href="/r/0001">' in page.render({"url": "/r/0001"})
""",
    "journey/__init__.py": "",
    "journey/test_journey.py": """from shortly import api, page


def test_create_a_link_and_see_it():
    srv = api.serve()
    try:
        html = page.shorten("http://127.0.0.1:%d" % srv.server_address[1], "https://bakery.example/rye")
    finally:
        srv.shutdown()
    assert '<a href="/r/' in html
""",
}


def seed_linkpair(engine: Engine, folder: Path) -> None:
    folder = Path(folder)
    for rel, text in LINKPAIR.items():
        (folder / rel).parent.mkdir(parents=True, exist_ok=True)
        (folder / rel).write_text(text)
    (folder / ".gitignore").write_text("__pycache__/\n.pytest_cache/\n")
    seed_profiles(engine)
    engine.create_project("linkpair", str(folder), "pytest", [p["name"] for p in PROFILES])
    engine.create_need("linkpair", "Share shorter links", HUMAN)
    engine.add_requirement("linkpair", "N-1", "The API creates a short link for a long one", HUMAN)
    engine.add_requirement("linkpair", "N-1", "The page shows the short link it got", HUMAN)
    engine.approve_requirements("linkpair", "N-1", HUMAN)
    engine.write_spec("linkpair", "R-1", "POST /links answers 201 with the short link", tags=["python"])
    engine.write_spec("linkpair", "R-2", "The page renders the short link as a link", tags=["python"])
    engine.approve_drafted("linkpair", "N-1", HUMAN)
    engine.add_test("linkpair", "S-1.1", {"type": "command", "command": "pytest -q tests/test_api.py"}, HUMAN,
                    status="approved")
    engine.add_test("linkpair", "S-2.1", {"type": "command", "command": "pytest -q tests/test_page.py"}, HUMAN,
                    status="approved")
    engine.approve_tests("linkpair", "N-1", HUMAN)


def fix_linkpair(folder: Path) -> None:
    """The repair: the page reads the field the API sends."""
    page = Path(folder) / "shortly" / "page.py"
    page.write_text(page.read_text().replace('link["url"]', 'link["short_url"]'))
    test = Path(folder) / "tests" / "test_page.py"
    test.write_text(test.read_text().replace('{"url": "/r/0001"}', '{"short_url": "/r/0001"}'))
