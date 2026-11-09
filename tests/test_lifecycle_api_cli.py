"""Round 5 capabilities through the API (the pane's seam) and the CLI (the terminal's seam)."""

import os
import subprocess
import sys
from pathlib import Path

from rung_engine import api
from rung_engine.service import Service
from support import seed

ROOT = Path(__file__).resolve().parent.parent


def call(svc, method, path, body=None):
    return api.handle(svc, method, path, body or {})


def _cli(store, *args, home=None):
    env = dict(os.environ, RUNG_STORE=str(store))
    if home:
        env["HERMES_HOME"] = str(home)
    return subprocess.run([sys.executable, "-m", "rung_engine.cli", *args], cwd=ROOT, env=env, capture_output=True,
                          text=True)


def test_prj01_prj02_api_create_from_folder_with_field_errors(engine, csv_folder, tmp_path):
    seed.seed_profiles(engine)
    svc = Service(engine, inline_runs=True)
    st, d = call(svc, "POST", "/projects/defaults", {"folder": str(csv_folder)})
    assert st == 200 and d["name"] == "csvtidy" and d["test_command"] == "pytest"
    st, body = call(svc, "POST", "/projects", {"folder": str(tmp_path / "nope")})
    assert st == 400 and body["field"] == "folder"
    st, p = call(svc, "POST", "/projects", {"folder": str(csv_folder)})
    assert st == 200 and p["name"] == "csvtidy"
    st, body = call(svc, "POST", "/projects", {"folder": str(csv_folder)})
    assert st == 409 and body["field"] == "name"


def test_prj05_prj06_prj07_api_project_lifecycle(seeded):
    svc = Service(seeded, inline_runs=True)
    st, p = call(svc, "POST", "/projects/notes-sync/update", {"test_command": "pytest -q"})
    assert st == 200 and p["test_command"] == "pytest -q"
    st, ev = call(svc, "GET", "/projects/notes-sync/events")
    assert ev[-1]["kind"] == "project_changed"
    assert call(svc, "POST", "/projects/notes-sync/archive")[0] == 200
    st, body = call(svc, "GET", "/state")
    assert [x["name"] for x in body["projects"]] == ["csvtidy"] and body["archived"] == 1
    st, arch = call(svc, "GET", "/projects/archived")
    assert [x["name"] for x in arch] == ["notes-sync"]
    st, body = call(svc, "POST", "/projects/notes-sync/needs", {"text": "x"})
    assert st == 409 and body["code"] == "read_only"
    st, r = call(svc, "GET", "/projects/notes-sync/rungs/N-1")
    assert st == 200 and r["read_only"] is True
    assert call(svc, "POST", "/projects/notes-sync/restore")[0] == 200
    st, body = call(svc, "POST", "/projects/notes-sync/delete", {"confirm": "wrong"})
    assert st == 400 and body["field"] == "confirm"
    st, body = call(svc, "POST", "/projects/notes-sync/delete", {"confirm": "notes-sync"})
    assert st == 200 and body["deleted"] == "notes-sync"


def test_ned03_ned04_ned05_ned06_api_retire_restore_readout(seeded):
    svc = Service(seeded, inline_runs=True)
    st, body = call(svc, "POST", "/projects/csvtidy/needs/N-1/retire", {})
    assert st == 400 and body["field"] == "reason"
    st, _ = call(svc, "POST", "/projects/csvtidy/needs/N-1/retire", {"reason": "Replaced"})
    assert st == 200
    st, r = call(svc, "GET", "/projects/csvtidy/rungs/N-1")
    assert r["retired"] is True and r["retired_reason"] == "Replaced" and r["read_only"] is True
    st, gone = call(svc, "GET", "/projects/csvtidy/retired")
    assert [n["id"] for n in gone] == ["N-1"]
    assert call(svc, "POST", "/projects/csvtidy/needs/N-1/restore")[0] == 200
    st, ro = call(svc, "GET", "/projects/csvtidy/needs/N-1/readout")
    assert st == 200 and ro["proven"] == 2 and ro["total"] == 3
    st, ex = call(svc, "POST", "/projects/csvtidy/needs/N-1/readout/export")
    assert st == 200 and Path(ex["path"]).read_text() == ex["markdown"]


def test_onb01_onb02_onb03_onb04_api_onboarding(engine):
    seed.seed_profiles(engine)
    svc = Service(engine, inline_runs=True)
    st, body = call(svc, "GET", "/state")
    assert body["onboarding"]["start"] is True
    st, p = call(svc, "POST", "/sample")
    assert st == 200 and p["sample"] is True
    st, fg = call(svc, "GET", "/projects/sample/first-green")
    assert (fg["done"], fg["total"]) == (4, 5)
    st, ob = call(svc, "POST", "/onboarding", {"checklist_hidden": True})
    assert ob["checklist_hidden"] is True
    st, body = call(svc, "GET", "/state")
    assert body["onboarding"]["start"] is False


def test_res03_api_edit_with_old_version_conflicts(seeded):
    svc = Service(seeded, inline_runs=True)
    v = seeded.rung("csvtidy", "R-3")["version"]
    assert call(svc, "POST", "/projects/csvtidy/rungs/R-3/edit", {"text": "A", "version": v})[0] == 200
    st, body = call(svc, "POST", "/projects/csvtidy/rungs/R-3/edit", {"text": "B", "version": v})
    assert st == 409 and body["code"] == "conflict"


def test_gte07_gte08_cli_demo_reset_doctor_readout(seeded, tmp_path):
    store = seeded.path
    seeded.close()
    r = _cli(store, "demo", "reset")
    assert r.returncode == 0, r.stderr
    assert "sample project reset" in r.stdout
    r = _cli(store, "projects")
    assert "sample:" in r.stdout and "csvtidy:" in r.stdout
    r = _cli(store, "doctor")
    assert "store: " in r.stdout and "desktop pane" in r.stdout and "rung doctor:" in r.stdout
    names = [line.split(":")[0].split()[-1] for line in r.stdout.splitlines() if line.startswith(("ok", "FAIL"))]
    assert "python" in names
    r = _cli(store, "--project", "csvtidy", "readout", "N-1")
    assert r.returncode == 0 and r.stdout.startswith("# N-1 results and evidence")
    r = _cli(store, "--project", "csvtidy", "retire", "N-1", "--reason", "Replaced")
    assert r.returncode == 0
    r = _cli(store, "--project", "csvtidy", "check", "--all")
    assert "S-1.1" not in r.stdout  # a retired need leaves the gate; nothing approved is left to pass
    r = _cli(store, "archive", "notes-sync")
    assert r.returncode == 0
    r = _cli(store, "projects")
    assert "notes-sync" not in r.stdout


def test_gte08_doctor_names_a_failing_check_with_its_fix(seeded):
    folder = Path(seeded.project("notes-sync")["folder"])
    store = seeded.path
    seeded.close()
    import shutil
    shutil.rmtree(folder)
    r = _cli(store, "doctor")
    assert r.returncode == 1
    assert "FAIL  project notes-sync folder" in r.stdout
    assert "fix: restore the folder, or change it" in r.stdout
    assert r.stdout.strip().endswith("rung doctor: FAIL (1)") or "rung doctor: FAIL" in r.stdout
