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


def seed_csvtidy(engine: Engine, folder: Path, with_history: bool = True) -> None:
    seed_profiles(engine)
    engine.create_project("csvtidy", str(folder), "pytest", [p["name"] for p in PROFILES])
    engine.set_setting("drafting", {"kind": "stub", "delay": 0.0})
    engine.set_setting("worker", {"kind": "stub", "delay": 0.2})
    engine.create_need("csvtidy", N1, HUMAN)
    for text in (R1, R2):
        engine.add_requirement("csvtidy", "N-1", text, HUMAN)
    engine.approve_requirements("csvtidy", "N-1", HUMAN)
    engine.write_spec("csvtidy", "R-1", S11, tags=["python", "cli", "tests"])
    engine.write_spec("csvtidy", "R-2", S21, tags=["python", "cli", "tests"],
                      detail="Read --locale, default en_US. Day-first for en_GB, de_DE, fr_FR.")
    engine.approve_drafted("csvtidy", "N-1", HUMAN)
    engine.add_test("csvtidy", "S-1.1", {"type": "command", "command": "pytest tests/test_sniff.py"}, HUMAN, status="approved")
    engine.add_test("csvtidy", "S-2.1", {"type": "command", "command": "pytest tests/test_dates.py::test_ambiguous_locale"},
                    HUMAN, status="approved")
    engine.add_test("csvtidy", "S-2.1", {"type": "manual", "text": "Manual: open output in a spreadsheet, dates sort correctly",
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
