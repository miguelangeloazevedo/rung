"""Project commands never inherit the environment Rung runs in (catalog review of 3928b7ae).

Tests, contract checks, milestone checks, the regression baseline, environment probes and migrations run code
from the project being edited, so each gets PATH, HOME, LANG, LC_*, TMPDIR, the project's own virtual
environment and the variables a person named in the project's settings. Nothing else, and never a provider key.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

from rung_engine import Actor, RungError
from rung_engine import execute
from rung_engine.api import handle
from rung_engine.execute import command_env, run_command
from rung_engine.service import Service
from support import seed

AGENT = Actor("agent", "coder")
SECRETS = {"OPENAI_API_KEY": "sk-test-not-real", "OPENROUTER_API_KEY": "sk-or-not-real",
           "HERMES_FAKE_TOKEN": "not-real", "RUNG_FAKE_PROVIDER_KEY": "not-real"}
BASE = {"PATH", "HOME", "LANG", "TMPDIR", "VIRTUAL_ENV", "PYTHONUNBUFFERED", "PYTHONDONTWRITEBYTECODE"}


@pytest.fixture
def secrets(monkeypatch):
    for k, v in SECRETS.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("LC_ALL", "C.UTF-8")


@pytest.fixture
def launched(monkeypatch):
    """Every environment a project command was started with."""
    seen = []
    real = subprocess.Popen

    def spy(*args, **kwargs):
        assert kwargs.get("env") is not None, f"inherits the environment: {args[0]}"
        if isinstance(args[0], str):  # a project command (git asking for the commit is checked by the assert)
            seen.append(dict(kwargs["env"]))
        return real(*args, **kwargs)

    monkeypatch.setattr(execute.subprocess, "Popen", spy)
    return seen


@pytest.fixture
def pair(engine, tmp_path, monkeypatch, secrets):
    monkeypatch.setenv("PATH", str(Path(sys.executable).parent) + os.pathsep + os.environ["PATH"])
    folder = tmp_path / "linkpair"
    folder.mkdir()
    seed.seed_linkpair(engine, folder)
    seed.fix_linkpair(folder)
    engine.accept_test_files("linkpair", "T-2.1a")
    engine.open_project("linkpair")
    return engine, folder


def _only_the_minimal_set(envs, allowed=()):
    assert envs, "no command ran"
    for env in envs:
        extra = {k for k in env if k not in BASE and not k.startswith("LC_") and k not in allowed}
        assert not extra, f"inherited: {sorted(extra)}"
        assert not set(SECRETS) & set(env) - set(allowed)


def test_the_default_is_the_minimal_environment_not_the_inherited_one(secrets, tmp_path):
    out = run_command(f"{sys.executable} -c \"import os; print(sorted(os.environ))\"", tmp_path, timeout=30).output
    for k in SECRETS:
        assert k not in out
    assert "'PATH'" in out and "'HOME'" in out and "'LC_ALL'" in out
    env = command_env()
    assert env["PATH"] == os.environ["PATH"] and env["HOME"] == os.environ["HOME"]


def test_every_kind_of_project_command_runs_without_provider_keys(pair, launched):
    e, folder = pair
    assert e.run_test("linkpair", "T-1.1a")["status"] == "pass"
    assert e.run_test("linkpair", "T-2.1a")["status"] == "pass"
    assert e.run_local("linkpair", "T-1.1a", folder)["status"] == "pass"  # an isolated run's local result
    for n, paths in (("api", ["shortly/api.py"]), ("page", ["shortly/page.py"])):
        e.save_arch("linkpair", "component", n, {"paths": paths})
        e.approve_arch("linkpair", "component", n)
    e.save_arch("linkpair", "contract", "short link JSON", {"contract_kind": "api", "producer": "api",
                                                            "consumers": ["page"], "artifacts": ["shortly/api.py"]})
    e.approve_arch("linkpair", "contract", "short link JSON")
    e.add_contract_check("linkpair", "short link JSON", "true")
    e.approve_contract_check("linkpair", "short link JSON", "CC-1")
    e.run_contract_checks("linkpair", "short link JSON")
    m1 = e.create_milestone("linkpair", "First", "Create a link", ["S-1.1"])["id"]
    e.add_milestone_check("linkpair", m1, {"type": "command", "command": "true"})
    e.approve_milestone("linkpair", m1)
    m = e.create_milestone("linkpair", "Share", "Create a link and see it", ["S-1.1", "S-2.1"])["id"]
    e.add_milestone_check("linkpair", m, {"type": "command", "command": "true"})
    e.set_milestone_system("linkpair", m, "environment", {"probes": [{"command": "python3 --version",
                                                                       "contains": "Python"}],
                                                          "migration": "true"})
    e.set_milestone_system("linkpair", m, "baseline", {"milestones": [m1], "command": "true"})
    e.approve_milestone("linkpair", m)
    launched.clear()
    e.run_milestone("linkpair", m)
    # the earlier journey, the probe, the migration, the baseline command and the check itself
    assert len(launched) == 5, len(launched)
    _only_the_minimal_set(launched)


def test_a_command_sees_no_provider_key_in_its_output(pair):
    e, folder = pair
    (folder / "show_env.py").write_text("import os\nprint('KEYS', sorted(os.environ))\n")
    p = e._project_row("linkpair")
    out = run_command("python3 show_env.py", folder, timeout=30, env=e.command_env(p)).output
    assert "KEYS" in out and not any(k in out for k in SECRETS)


def test_a_person_passes_named_variables_and_an_agent_cannot(pair, launched, monkeypatch):
    e, folder = pair
    monkeypatch.setenv("DATABASE_URL", "sqlite:///demo.db")
    assert e.project("linkpair")["env_vars"] == []
    with pytest.raises(RungError):
        e.update_project("linkpair", env_vars=["DATABASE_URL"], actor=AGENT)
    for bad in (["1BAD"], ["A=B"], ["ok", "has space"], [3], "x" * 200):
        with pytest.raises(RungError) as err:
            e.update_project("linkpair", env_vars=bad)
        assert err.value.field == "env_vars"
    p = e.update_project("linkpair", env_vars="DATABASE_URL, NOT_SET_ANYWHERE DATABASE_URL")
    assert p["env_vars"] == ["DATABASE_URL", "NOT_SET_ANYWHERE"]
    assert e.events("linkpair")[-1]["data"]["env_vars"] == {"before": [], "after": ["DATABASE_URL",
                                                                                     "NOT_SET_ANYWHERE"]}
    launched.clear()
    e.run_test("linkpair", "T-1.1a")
    _only_the_minimal_set(launched, allowed={"DATABASE_URL"})
    assert launched[0]["DATABASE_URL"] == "sqlite:///demo.db" and "NOT_SET_ANYWHERE" not in launched[0]
    assert "OPENAI_API_KEY" not in launched[0]
    e.update_project("linkpair", env_vars=[])
    launched.clear()
    e.run_test("linkpair", "T-1.1a")
    assert "DATABASE_URL" not in launched[0]


def test_the_settings_door_takes_the_list(pair):
    e, folder = pair
    svc = Service(e)
    status, body = handle(svc, "POST", "/projects/linkpair/update", {"env_vars": ["DATABASE_URL"]})
    assert status == 200 and body["env_vars"] == ["DATABASE_URL"], body
    status, body = handle(svc, "POST", "/projects/linkpair/update", {"env_vars": ["no-dash"]})
    assert status == 400 and body.get("field") == "env_vars", body


def test_the_projects_own_virtual_environment_is_used(tmp_path, monkeypatch, secrets):
    monkeypatch.delenv("VIRTUAL_ENV", raising=False)
    (tmp_path / ".venv" / "bin").mkdir(parents=True)
    (tmp_path / ".venv" / "pyvenv.cfg").write_text("home = /usr/bin\n")
    env = command_env(tmp_path)
    assert env["VIRTUAL_ENV"] == str(tmp_path / ".venv")
    assert env["PATH"].split(os.pathsep)[0] == str(tmp_path / ".venv" / "bin")
    # an active virtual environment outside the project is Rung's, not the project's
    monkeypatch.setenv("VIRTUAL_ENV", str(Path(sys.prefix)))
    assert command_env(tmp_path / "elsewhere").get("VIRTUAL_ENV") is None
