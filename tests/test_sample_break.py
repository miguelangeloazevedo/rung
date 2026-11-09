"""Break and repair the sample (decisions Round 24, U02): one line of the sample's own code changes, no bot runs,
no other project is touched, and the verdict moves Verified, Out of date, Failed, Verified on the one evaluator."""

import hashlib

import pytest

from rung_engine.api import handle
from rung_engine.core import RungError


def _tree(folder):
    return {p.relative_to(folder).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(folder.rglob("*")) if p.is_file()}


def test_str02_str03_break_and_repair_move_the_one_verdict(engine, csv_folder):
    e = engine
    e.create_project("csvtidy", str(csv_folder), "pytest", ["coder"])
    other = _tree(csv_folder)
    e.create_sample()
    spec = "S-1.1"
    [t] = [r["id"] for r in e.tree("sample")[0]["children"][0]["children"][0]["children"]]
    e.run_test("sample", t)
    assert e.verification("sample", spec)["verification"] == "verified"
    assert e.sample_state()["broken"] is False

    out = e.break_sample()
    assert out == {"broken": True, "file": "wordcount/count.py", "bot": False}
    assert e.sample_state()["broken"] is True
    assert e.verification("sample", spec)["verification"] == "out_of_date"
    e.run_test("sample", t)
    assert e.verification("sample", spec)["verification"] == "failed"

    e.repair_sample()
    assert e.sample_state()["broken"] is False
    assert e.verification("sample", spec)["verification"] != "verified"  # the latest result is still the failure
    e.run_test("sample", t)
    assert e.verification("sample", spec)["verification"] == "verified"
    assert _tree(csv_folder) == other  # another project's folder, byte for byte
    kinds = [x["kind"] for x in e.events("sample")]
    assert "sample_broken" in kinds and "sample_repaired" in kinds


def test_str02_no_sample_no_break_and_agents_cannot(engine, svc):
    with pytest.raises(RungError):
        engine.break_sample()
    assert engine.sample_state() is None
    st, out = handle(svc, "POST", "/sample/break", {})
    assert st == 404
    engine.create_sample()
    from rung_engine.core import Actor
    with pytest.raises(RungError):
        engine.break_sample(Actor(kind="agent", name="coder"))
    st, out = handle(svc, "POST", "/sample/break", {})
    assert st == 200 and out["bot"] is False
    st, out = handle(svc, "GET", "/sample/state")
    assert st == 200 and out["broken"] is True
    st, out = handle(svc, "POST", "/sample/repair", {})
    assert st == 200 and out["broken"] is False
