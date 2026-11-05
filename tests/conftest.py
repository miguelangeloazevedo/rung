import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
# Test commands in the fixture run `pytest`; make the interpreter running this suite provide it.
os.environ["PATH"] = str(Path(sys.executable).parent) + os.pathsep + os.environ.get("PATH", "")

from rung_engine import Engine  # noqa: E402
from rung_engine.service import Service  # noqa: E402
from support import seed  # noqa: E402


@pytest.fixture
def engine(tmp_path):
    e = Engine(tmp_path / "store" / "data.db")
    yield e
    e.close()


@pytest.fixture
def csv_folder(tmp_path):
    return seed.copy_fixture("csvtidy", tmp_path / "work")


@pytest.fixture
def seeded(engine, csv_folder, tmp_path):
    seed.seed_csvtidy(engine, csv_folder)
    seed.seed_notes_sync(engine, seed.copy_fixture("notes-sync", tmp_path / "work"))
    engine.open_project("csvtidy")
    return engine


@pytest.fixture
def svc(engine):
    s = Service(engine, inline_runs=True)
    yield s
    s.wait_idle()
