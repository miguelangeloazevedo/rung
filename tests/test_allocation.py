import pytest

from rung_engine import RungError, allocation


def test_score_parts():
    p = allocation.ProfileFacts("coder", ("python", "cli", "tests"), cost=5, enabled=True)
    s = allocation.rank([p], ["python", "cli", "tests"])[0]
    assert s.parts == {"tags": 40, "load": 20, "reliability": 15, "cost": 5}
    assert s.score == 80


def test_filters_and_order():
    ps = [
        allocation.ProfileFacts("b", ("python",), 5, True),
        allocation.ProfileFacts("a", ("python",), 5, True),
        allocation.ProfileFacts("off", ("python",), 0, False),
        allocation.ProfileFacts("notag", ("docs",), 0, True),
    ]
    r = allocation.rank(ps, ["python"], ["python"])
    assert [x.profile for x in r] == ["a", "b"]


def test_suggest_and_pick(seeded):
    e = seeded
    sug = e.suggest("csvtidy", "S-2.1")
    names = [s["profile"] for s in sug["suggestions"]]
    assert names[0] == "coder"
    assert all(isinstance(s["score"], int) for s in sug["suggestions"])
    assert set(sug["suggestions"][0]["parts"]) == {"tags", "load", "reliability", "cost"}
    e.save_profiles([{**e.profile("researcher"), "enabled": False}])
    assert "researcher" not in [s["profile"] for s in e.suggest("csvtidy", "S-2.1")["suggestions"]]
    e.edit("csvtidy", "S-2.1", data={"required_tags": ["python"]}, approve=True)
    sug = e.suggest("csvtidy", "S-2.1")
    assert "writer" not in [s["profile"] for s in sug["suggestions"]]
    assert {"profile": "writer", "reason": "missing tag python"} in sug["excluded"]
    second = sug["suggestions"][1]["profile"]
    e.pick("csvtidy", "S-2.1", second)
    assert e.suggest("csvtidy", "S-2.1")["pick"]["profile"] == second
    assert e.suggest("csvtidy", "S-2.1")["pick"]["picked_by"] == "you"
    with pytest.raises(RungError):
        e.pick("csvtidy", "S-2.1", "writer")


def test_settings_change_ranking(seeded):
    e = seeded
    before = {s["profile"]: s for s in e.suggest("csvtidy", "S-2.1")["suggestions"]}
    rev = e.profile("reviewer")
    e.save_profiles([{**rev, "labels": rev["labels"] + ["cli"], "cost": 1}])
    after = {s["profile"]: s for s in e.suggest("csvtidy", "S-2.1")["suggestions"]}
    assert after["reviewer"]["parts"]["tags"] > before["reviewer"]["parts"]["tags"]
    assert after["reviewer"]["parts"]["cost"] == 9
    assert e.profile("reviewer")["labels"] == ["review", "python", "cli"]
    with pytest.raises(RungError):
        e.save_profiles([{**rev, "cost": 99}])
