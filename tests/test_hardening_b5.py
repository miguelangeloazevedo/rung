"""Hardening round 5: one regression per defect found."""

from pathlib import Path

from rung_engine import api
from rung_engine.service import Service
from support import seed
from test_hardening_b1 import _ai_spec  # noqa: F401

SRC = Path(__file__).resolve().parents[1] / "desktop" / "src"


def test_r5_a_body_that_is_not_an_object_is_refused_as_such(seeded):
    svc = Service(seeded, inline_runs=True)
    for body in ([1], ["required_tools"], "x", 5):
        st, out = api.handle(svc, "POST", "/projects/csvtidy/specs/S-2.1/allocation", body)
        assert st == 400 and out["detail"] == "the request body is an object", body


def test_r5_a_folder_typed_with_a_tilde_is_stored_as_the_folder_it_names(engine, tmp_path, monkeypatch):
    home = tmp_path / "home"
    (home / "proj").mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))
    seed.seed_profiles(engine)
    p = engine.create_project("tilde", "~/proj", "true", ["coder"])
    assert p["folder"] == str(home / "proj")
    (home / "other").mkdir()
    assert engine.update_project("tilde", folder="~/other")["folder"] == str(home / "other")


def test_r5_the_spec_page_shows_the_mode_its_requirement_is_in(engine, csv_folder):
    svc = _ai_spec(engine, csv_folder)
    st, out = api.handle(svc, "GET", "/projects/csvtidy/rungs/S-2.1")
    assert st == 200 and out["authoring"] == "ai"
    svc.engine.set_authoring("csvtidy", "R-2", "human")
    assert api.handle(svc, "GET", "/projects/csvtidy/rungs/S-2.1")[1]["authoring"] == "human"
    det = (SRC / "40-detail.js").read_text()
    assert "value: r.authoring || (r.author_role === 'human' ? 'human' : 'ai')" in det
    svc.wait_idle()


def test_r5_the_dock_path_keeps_the_whole_chain_on_hover():
    dock = (SRC / "70-dock.js").read_text()
    assert "full: up.join(' › ')" in dock and "title: fullPath || path" in dock


def test_r5_fresh_draft_is_refused_on_an_archived_project_and_a_retired_need(tmp_path, csv_folder):
    from rung_engine import Engine
    for i, restrict in enumerate(("archive", "retire")):
        engine = Engine(str(tmp_path / f"s{i}.db"))
        svc = _ai_spec(engine, csv_folder)
        before = engine.rung("csvtidy", "S-2.1")
        if restrict == "archive":
            assert api.handle(svc, "POST", "/projects/csvtidy/archive", {})[0] == 200
        else:
            assert api.handle(svc, "POST", "/projects/csvtidy/needs/N-1/retire", {"reason": "dropped"})[0] == 200
        st, _ = api.handle(svc, "POST", "/projects/csvtidy/rungs/S-2.1/regenerate", {})
        svc.wait_idle()
        after = engine.rung("csvtidy", "S-2.1")
        assert st == 409, restrict
        assert (after["status"], after["version"], after["text"]) == (before["status"], before["version"], before["text"])
        engine.close()


def test_r5_an_alternative_id_reads_the_same_tree_fields(engine, csv_folder):
    svc = _ai_spec(engine, csv_folder)
    exact = api.handle(svc, "GET", "/projects/csvtidy/rungs/S-2.1")[1]
    for alt in ("s-2.1", "S2.1", " S 2.1 "):
        st, r = api.handle(svc, "GET", f"/projects/csvtidy/rungs/{alt}")
        assert st == 200 and r["id"] == "S-2.1", alt
        for k in ("children", "coverage", "released", "blockers", "read_only", "history"):
            assert r.get(k) == exact.get(k), (alt, k)
    svc.wait_idle()


def test_r5_develop_falls_back_to_an_eligible_profile_when_the_pick_is_excluded():
    build = (SRC / "30-build.js").read_text()
    assert "(a.pick && a.suggestions.find(x => x.profile === a.pick.profile)) || a.suggestions[0] || null" in build
