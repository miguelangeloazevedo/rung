"""Allocation labels (decisions Round 24, R11): every score part says what it measures; no part reads as money or
a chance of success; a suggestion names the inputs behind the top profile and why each excluded one is excluded;
independent means a different profile from the author."""

from rung_engine import allocation
from rung_engine.allocation import Needs, ProfileFacts


def test_alo01_each_part_has_a_plain_description():
    assert set(allocation.PART_HELP) == {"tags", "load", "reliability", "cost"}
    h = allocation.PART_HELP
    assert "not a chance of success" in h["reliability"] and "completed" in h["reliability"]
    assert "not money spent" in h["cost"] and "preference" in h["cost"]
    for text in h.values():
        assert "%" not in text and "\u20ac" not in text and "probab" not in text.lower()


def test_alo02_suggestion_names_its_inputs():
    a = ProfileFacts("coder", ("python", "cli"), 2, True, running=1, completed=5, total=6)
    b = ProfileFacts("writer", ("docs",), 0, True)
    ranked = allocation.rank([a, b], ["python", "tests"], needs=Needs(required_tags=()))
    top = ranked[0].as_dict()
    assert top["profile"] == "coder"
    assert top["why"] == ["carries 1 of 2 tags: python", "carries 1 run or claims now",
                          "5 of 6 past command executions completed", "cost preference band 2"]
    assert ranked[1].as_dict()["why"][2] == "no past command executions"


def test_alo02_alo03_engine_suggest_explains_and_independent_means_another_profile(seeded):
    e = seeded
    s = e.set_allocation("csvtidy", "S-2.1", independent=True)
    assert s["parts_help"] == allocation.PART_HELP
    assert s["independent_help"] == allocation.INDEPENDENT_HELP
    assert "different profile" in s["independent_help"] and "model" not in s["independent_help"]
    for x in s["suggestions"]:
        assert len(x["why"]) == 5 and x["why"][-1] == "a different profile from the author"
    for x in s["excluded"]:
        assert x["reason"]
    if len(s["suggestions"]) > 1:  # override with another eligible profile
        other = s["suggestions"][1]["profile"]
        e.pick("csvtidy", "S-2.1", other)
        assert e.suggest("csvtidy", "S-2.1")["pick"]["profile"] == other
