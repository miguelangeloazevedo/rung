"""Hardening round A2: findings from a review of the REST seam, each pinned by a test."""

import json

import pytest

from rung_engine import api
from rung_engine.service import Service


def call(svc, method, path, body=None):
    return api.handle(svc, method, path, body)


@pytest.fixture
def svc(seeded):
    return Service(seeded, inline_runs=True)


def test_the_edit_route_changes_text_and_detail_only(svc):
    e = svc.engine
    data = lambda rid: json.loads(e._rung_row("csvtidy", rid)["data"] or "{}")  # noqa: E731
    before = {rid: data(rid) for rid in ("N-1", "S-2.1", "T-2.1a")}
    text = e.rung("csvtidy", "N-1")["text"]
    for rid, injected in (("N-1", {"tests_approved": True}), ("S-2.1", {"draft_state": "drafting"}),
                          ("T-2.1a", {"command": "false"})):
        st, _ = call(svc, "POST", f"/projects/csvtidy/rungs/{rid}/edit",
                     {"text": text if rid == "N-1" else None, "data": injected})
        assert st == 200
        assert data(rid) == before[rid], rid


@pytest.mark.parametrize("body", [{"text": 5}, {"text": ["a"]}, {"detail": {"x": 1}}])
def test_a_wrong_type_is_a_bad_request_not_a_crash(svc, body):
    st, out = call(svc, "POST", "/projects/csvtidy/rungs/R-2/edit", body)
    assert st == 400 and out["code"] == "bad_request"


@pytest.mark.parametrize("value", ["false", "true", 0, 1, "yes"])
def test_yes_or_no_fields_take_true_or_false_only(svc, value):
    v = svc.engine.rung("csvtidy", "R-2")["version"]
    st, _ = call(svc, "POST", "/projects/csvtidy/rungs/R-2/edit", {"text": "Normalise dates", "approve": value})
    assert st == 400
    assert svc.engine.rung("csvtidy", "R-2")["version"] == v
    st, _ = call(svc, "POST", "/projects/csvtidy/specs/S-2.1/tests",
                 {"fields": {"type": "command", "command": "true"}, "accept": value})
    assert st == 400
