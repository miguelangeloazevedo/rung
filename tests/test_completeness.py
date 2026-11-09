"""Need-level completeness (decisions Round 24, B14): a need is complete only when every requirement it asks
for is specified and every specification under it is verified now; nothing is silently dropped."""

import pytest

from rung_engine import RungError
from rung_engine.api import handle
import os
import subprocess
import sys
from pathlib import Path
from support import seed

ROOT = Path(__file__).resolve().parents[1]


def _cli(store, *args):
    env = dict(os.environ, RUNG_STORE=str(store))
    return subprocess.run([sys.executable, "-m", "rung_engine.cli", *args], cwd=ROOT, env=env, capture_output=True,
                          text=True)


@pytest.fixture
def comp(engine, csv_folder):
    seed.seed_completeness(engine, csv_folder)
    return engine


def _codes(res):
    return [(o["rung"], o["code"]) for o in res["open"]]


def test_cmp01_cmp02_open_requirements_are_listed_by_id_with_their_reason(comp):
    e = comp
    res = e.need_completeness("csvtidy", "N-1")
    assert not res["complete"] and _codes(res) == [("R-2", "no_specification")]
    assert res["verified"] == ["S-1.1"]
    e.write_spec("csvtidy", "R-2", "Parse dates by locale")
    e.approve("csvtidy", "S-2.1")
    res = e.need_completeness("csvtidy", "N-1")
    assert [(o["rung"], o.get("spec"), o["code"]) for o in res["open"]] == [("R-2", "S-2.1", "not_verified")]
    assert "S-2.1 not verified" in res["open"][0]["text"]
    with pytest.raises(RungError):
        e.retire_requirement("csvtidy", "R-2", "  ")
    e.retire_requirement("csvtidy", "R-2", "Dates move to a later release")
    res = e.need_completeness("csvtidy", "N-1")
    assert res["complete"] and res["out_of_scope"] == [{"rung": "R-2", "reason": "Dates move to a later release"}]
    e.restore_requirement("csvtidy", "R-2")
    assert not e.need_completeness("csvtidy", "N-1")["complete"]


def test_cmp01_a_failing_or_drifted_specification_keeps_the_need_open(comp, csv_folder):
    e = comp
    e.retire_requirement("csvtidy", "R-2", "later")
    assert e.need_completeness("csvtidy", "N-1")["complete"]
    (csv_folder / "csvtidy" / "reader.py").write_text((csv_folder / "csvtidy" / "reader.py").read_text() + "\n# changed\n")
    res = e.need_completeness("csvtidy", "N-1", fresh=True)
    assert not res["complete"] and res["open"][0]["spec"] == "S-1.1"
    e.add_requirement("csvtidy", "N-1", "A draft requirement")
    assert ("R-3", "not_approved") in _codes(e.need_completeness("csvtidy", "N-1"))


def test_cmp03_need_view_home_and_cli_agree(comp, svc):
    e = comp
    e.open_project("csvtidy")
    st, need = handle(svc, "GET", "/projects/csvtidy/rungs/N-1")
    assert st == 200
    [home] = [n for n in e.home("csvtidy")["needs"] if n["id"] == "N-1"]
    st, rest = handle(svc, "GET", "/projects/csvtidy/needs/N-1/completeness")
    assert need["completeness"] == rest
    assert home["complete"] == rest["complete"] and home["open"] == rest["open"]
    r = _cli(e.path, "--json", "verify", "N-1")
    assert r.returncode == 1 and '"no_specification"' in r.stdout, r.stdout + r.stderr
    st, out = handle(svc, "POST", "/projects/csvtidy/requirements/R-2/retire", {"reason": "later"})
    assert st == 200
    r = _cli(e.path, "verify", "N-1")
    assert r.returncode == 0 and "N-1: complete" in r.stdout and "out_of_scope" in r.stdout, r.stdout + r.stderr
    st, _ = handle(svc, "GET", "/projects/csvtidy/needs/R-1/completeness")
    assert st == 400
