"""A small task stays small (decisions Round 24, B11): one card over the ordinary ladder."""

import pytest

from rung_engine import RungError
from rung_engine.api import handle
from rung_engine.runner import run_loop

CHECKS = [{"type": "command", "command": "python3 -c \"print('trim ok')\""},
          {"type": "manual", "steps": ["Open the cleaned file", "Every row has no trailing spaces"]}]


def _card(e):
    return e.quick_task("csvtidy", "Trailing spaces are removed from every cell", CHECKS, "coder")


def _versions(card):
    return {r["id"]: r["version"] for r in card["rungs"]}


def test_tsk01_tsk02_save_writes_the_ordinary_rungs_as_drafts(seeded):
    e = seeded
    before = len(e.tree("csvtidy"))
    with pytest.raises(RungError):  # nothing stored on a refused save
        e.quick_task("csvtidy", "x", [])
    with pytest.raises(RungError):
        e.quick_task("csvtidy", "x", [CHECKS[0]] * 6)
    with pytest.raises(RungError):
        e.quick_task("csvtidy", "", CHECKS)
    assert len(e.tree("csvtidy")) == before
    card = _card(e)
    kinds = [r["kind"] for r in card["rungs"]]
    assert kinds == ["need", "requirement", "specification", "test", "test"]
    assert [r["status"] for r in card["rungs"][1:]] == ["draft"] * 4
    assert all(r["text"] for r in card["rungs"])  # the card shows every text it created
    assert card["profile"] == "coder" and not card["approved"]
    assert len(e.tree("csvtidy")) == before + 1


def test_tsk03_approve_takes_exactly_the_versions_shown(seeded):
    e = seeded
    card = _card(e)
    seen = _versions(card)
    req = card["rungs"][1]["id"]
    e.edit("csvtidy", req, text="Trailing and leading spaces are removed")  # someone changed it meanwhile
    with pytest.raises(RungError) as ex:
        e.quick_approve("csvtidy", card["need"], seen)
    assert ex.value.status == 409 and req in str(ex.value)
    assert all(r["status"] != "approved" for r in e.quick("csvtidy", card["need"])["rungs"][1:])  # nothing approved
    fresh = e.quick("csvtidy", card["need"])
    done = e.quick_approve("csvtidy", card["need"], _versions(fresh))
    assert done["approved"] and all(r["status"] == "approved" for r in done["rungs"])
    with pytest.raises(RungError):  # a missing id is not an approval of it
        e.quick_approve("csvtidy", card["need"], {card["need"]: 1})


def test_tsk04_build_and_verify_is_the_ordinary_run(seeded, svc):
    e = seeded
    card = _card(e)
    st, out = handle(svc, "POST", f"/projects/csvtidy/quick/{card['need']}/build", {})
    assert st == 409 and "approve" in out["detail"]
    card = e.quick_approve("csvtidy", card["need"], _versions(card))
    run = e.start_run("csvtidy", card["spec"], profile=card["profile"])
    assert run_loop(e, run["id"])["status"] == "passed"
    card = e.quick("csvtidy", card["need"])
    assert card["run"]["status"] == "passed" and card["verification"]["verification"] == "awaiting_manual"
    manual = card["checks"][1]["id"]
    n = e.record_manual("csvtidy", manual, "pass", "checked")["n"]
    e.approve_result("csvtidy", manual, n)
    assert e.quick("csvtidy", card["need"])["verification"]["verification"] == "verified"


def test_tsk05_full_ladder_holds_the_same_rungs_and_no_specification_word(seeded, svc):
    e = seeded
    card = _card(e)
    [node] = [n for n in e.tree("csvtidy") if n["id"] == card["need"]]
    ids = [node["id"]]
    walk = list(node["children"])
    while walk:
        x = walk.pop(0)
        ids.append(x["id"])
        walk = list(x.get("children", [])) + walk
    assert ids == [r["id"] for r in card["rungs"]]
    st, rest = handle(svc, "GET", f"/projects/csvtidy/quick/{card['need']}")
    assert st == 200 and rest["rungs"] == card["rungs"]
    st, _ = handle(svc, "GET", "/projects/csvtidy/quick/N-1")
    assert st == 404  # an ordinary need is not a quick task


def test_tsk06_editing_an_approved_check_voids_its_approval_and_evidence(seeded):
    e = seeded
    card = _card(e)
    card = e.quick_approve("csvtidy", card["need"], _versions(card))
    cmd = card["checks"][0]["id"]
    assert e.run_test("csvtidy", cmd)["status"] == "pass"
    e.edit_test("csvtidy", cmd, {"command": "python3 -c \"print('trim ok again')\""})
    card = e.quick("csvtidy", card["need"])
    assert not card["approved"] and card["checks"][0]["status"] == "draft"
    assert card["verification"]["verification"] != "verified"
    assert not e.executions("csvtidy", cmd)[0]["counts"]
