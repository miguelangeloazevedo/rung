"""End-to-end fixtures: a fresh Rung store per test and the real Desktop pane over CDP."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import harness as H  # noqa: E402


@pytest.fixture
def rung(tmp_path):
    store = tmp_path / "store" / "rung.db"
    engine = H.use_store(store)
    H.standard_profiles(engine)
    ns = SimpleNamespace(engine=engine, store=store, tmp=tmp_path, work=tmp_path / "work")
    yield ns
    try:
        engine.close()
    finally:
        H.release_store()


@pytest.fixture
def csvtidy(rung):
    folder = H.copy_fixture("csvtidy", rung.work)
    H.configure_stubs(rung.engine, folder)
    return folder


@pytest.fixture
def page():
    with H.desktop() as pg:
        yield pg
