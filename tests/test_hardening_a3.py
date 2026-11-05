"""Hardening round A3: findings from a review of the CLI, the doctor and the agent tools, each pinned by a test."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from rung_engine.doctor import run_checks

ROOT = Path(__file__).resolve().parents[1]


def _cli(store, *args, home=None):
    env = dict(os.environ, RUNG_STORE=str(store))
    if home:
        env["HERMES_HOME"] = str(home)
    return subprocess.run([sys.executable, "-m", "rung_engine.cli", *args], cwd=ROOT, env=env, capture_output=True,
                          text=True)


@pytest.fixture
def tools_on(seeded, monkeypatch):
    monkeypatch.setenv("RUNG_STORE", seeded.path)
    from rung_engine import host, tools
    host._SERVICES.clear()
    yield lambda name, args: json.loads(tools.HANDLERS[name](args))
    host._SERVICES.clear()


def test_a_specification_under_a_retired_need_is_not_released(seeded, tools_on):
    assert seeded.check("csvtidy", "S-2.1")["ok"]
    seeded.retire_need("csvtidy", "N-1", "Out of scope")
    res = seeded.check("csvtidy", "S-2.1")
    assert not res["ok"] and res["blockers"] == ["S-2.1 is under a retired need"]
    assert _cli(seeded.path, "check", "S-2.1").returncode == 1
    assert tools_on("rung_check", {"spec": "S-2.1"})["ok"] is False


@pytest.mark.parametrize("args", [["projects"], ["projects", "--archived"], ["tree"], ["tree", "--retired"],
                                  ["where"], ["status"], ["check", "S-2.1"], ["check", "--all"], ["run", "S-2.1"],
                                  ["readout", "N-1"], ["archive", "nope"], ["retire", "N-1", "--reason", "Gone"]])
def test_json_output_is_json_for_every_command(seeded, args):
    r = _cli(seeded.path, "--json", *args)
    json.loads(r.stdout)


def test_the_cli_lists_retired_needs_and_archived_projects(seeded):
    seeded.retire_need("csvtidy", "N-1", "Out of scope")
    retired = json.loads(_cli(seeded.path, "--json", "tree", "--retired").stdout)
    assert "N-1" in [n["id"] for n in retired]
    assert "N-1" not in [n["id"] for n in json.loads(_cli(seeded.path, "--json", "tree").stdout)]
    seeded.archive_project("csvtidy")
    assert "csvtidy" in [p["name"] for p in json.loads(_cli(seeded.path, "--json", "projects", "--archived").stdout)]
    assert "no archived projects" not in _cli(seeded.path, "projects", "--archived").stdout


@pytest.mark.parametrize("name,args,field", [
    ("rung_propose", {}, "parent"), ("rung_propose", {"parent": "N-1"}, "text"),
    ("rung_propose", {"parent": "N-1", "text": 5}, "text"),
    ("rung_propose", {"parent": "N-1", "text": "x", "detail": ["x"]}, "detail"),
    ("rung_run_tests", {}, "spec"), ("rung_check", {"all": "false"}, "all"), ("rung_check", {"spec": 7}, "spec"),
    ("rung_status", {"project": 3}, "project"),
])
def test_agent_tools_refuse_bad_arguments_clearly(tools_on, name, args, field):
    out = tools_on(name, args)
    assert out["code"] == "bad_request" and out["field"] == field, out


def test_the_doctor_fails_a_read_only_store(seeded, tmp_path):
    os.chmod(seeded.path, 0o444)
    try:
        checks = {c["name"]: c for c in run_checks(Path(seeded.path), sys.executable)}
        assert not checks["store writable"]["ok"]
    finally:
        os.chmod(seeded.path, 0o644)


def test_the_doctor_checks_profiles_modes_and_each_test_command(seeded, tmp_path):
    seeded.update_project("csvtidy", test_command="no-such-test-runner-xyz --all")
    checks = {c["name"]: c for c in run_checks(Path(seeded.path), sys.executable)}
    assert checks["profiles"]["ok"] and checks["worker"]["ok"] and checks["drafting"]["ok"]
    assert not checks["project csvtidy test command"]["ok"]
    assert "no-such-test-runner-xyz not found" in checks["project csvtidy test command"]["detail"]
    seeded.update_project("csvtidy", test_command="python3 -m pytest")
    checks = {c["name"]: c for c in run_checks(Path(seeded.path), sys.executable)}
    assert checks["project csvtidy test command"]["ok"]
