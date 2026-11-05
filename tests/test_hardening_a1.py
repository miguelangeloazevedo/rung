"""Hardening round A1: findings from a review of the engine, each pinned by a test."""

import sys

import pytest

from rung_engine import NotFound, RungError
from rung_engine.execute import run_command
from rung_engine.service import Service


def test_generic_edit_of_a_test_command_stops_its_old_pass_counting(seeded):
    e = seeded
    assert e.executions("csvtidy", "T-2.1a")[0]["counts"]
    e.edit("csvtidy", "T-2.1a", data={"command": "false"}, approve=True)
    ex = e.executions("csvtidy", "T-2.1a")[0]
    assert ex["status"] == "pass" and not ex["counts"] and ex["invalidated"]
    assert not e.check("csvtidy", "S-2.1")["ok"]


def test_accepting_an_edit_suggestion_is_a_versioned_edit_with_staleness(seeded):
    e = seeded
    v = e.rung("csvtidy", "R-2")["version"]
    [sug] = e.add_suggestions("csvtidy", "R-2", "edit", ["Keep the time zone when present"])
    e.resolve_suggestion("csvtidy", sug["id"], accept=True)
    r = e.rung("csvtidy", "R-2")
    assert r["version"] == v + 1 and r["detail"].endswith("Keep the time zone when present")
    assert e.rung("csvtidy", "S-2.1")["status"] == "stale"
    assert e.history("csvtidy", "R-2")[-1]["detail"].endswith("Keep the time zone when present")


def test_a_draft_lands_only_on_a_specification_being_drafted(seeded):
    e = seeded
    before = e.rung("csvtidy", "S-2.1")
    with pytest.raises(RungError) as err:
        e.finish_draft("csvtidy", "S-2.1", "Overwritten by a late draft")
    assert err.value.code == "not_drafting"
    with pytest.raises(RungError):
        e.fail_draft("csvtidy", "S-2.1", "late failure")
    after = e.rung("csvtidy", "S-2.1")
    assert (after["text"], after["status"], after["version"]) == (before["text"], before["status"], before["version"])


@pytest.mark.parametrize("rule", [{"kind": "exit_code", "value": "notanint"}, {"kind": "exit_code", "value": True},
                                  {"kind": "output_contains", "value": ""}, {"kind": "nope"}, "exit 0", None])
def test_a_bad_pass_rule_is_refused_when_saved(seeded, rule):
    e = seeded
    with pytest.raises(RungError) as err:
        e.add_test("csvtidy", "S-2.1", {"type": "command", "command": "true", "pass_rule": rule})
    assert err.value.field == "pass_rule"
    with pytest.raises(RungError):
        e.edit_test("csvtidy", "T-2.1a", {"pass_rule": rule})
    with pytest.raises(RungError):
        e.edit("csvtidy", "T-2.1a", data={"pass_rule": rule})


def test_a_good_pass_rule_is_kept(seeded):
    t = seeded.add_test("csvtidy", "S-2.1", {"type": "command", "command": "echo hello",
                                             "pass_rule": {"kind": "output_contains", "value": "hello"}},
                        status="approved")
    assert seeded.run_test("csvtidy", t["id"])["status"] == "pass"


def test_a_queued_run_whose_runner_never_started_is_reconciled(seeded):
    e = seeded
    run = e.start_run("csvtidy", "S-2.1")
    assert e.run(run["id"])["status"] == "queued"
    assert e.reconcile_runs(lambda pid: False) == []  # inside the grace period it may still start
    t0 = e.clock()
    e.clock = lambda: t0 + 60
    assert e.reconcile_runs(lambda pid: False) == [run["id"]]
    assert e.run(run["id"])["status"] == "unknown"
    e.start_run("csvtidy", "S-2.1")  # the specification is free again


def test_a_runner_that_cannot_start_ends_its_run_unknown(seeded, tmp_path):
    svc = Service(seeded, python=str(tmp_path / "no-such-python"), log_dir=tmp_path / "logs")
    with pytest.raises(RungError):
        svc.send("csvtidy", "S-2.1")
    assert [r["status"] for r in seeded.runs("csvtidy")][-1] == "unknown"


def test_the_output_cap_keeps_a_true_prefix_of_a_long_line(tmp_path):
    cmd = f"{sys.executable} -c \"print('NEEDLE' + 'x' * 200000)\""
    res = run_command(cmd, tmp_path, timeout=30, output_limit=64000)
    assert res.output.startswith("NEEDLE") and "[output truncated at 64000 characters]" in res.output
    assert len(res.output) < 64000 + 100


def test_defects_link_whole_execution_numbers_only(seeded):
    with pytest.raises(RungError) as err:
        seeded.raise_defect("csvtidy", "T-2.1a", [1.5], "Wrong row count")
    assert err.value.field == "executions"


def test_an_unknown_execution_is_not_found(seeded):
    with pytest.raises(NotFound):
        seeded.perform_execution("csvtidy", "T-2.1a", 999)
